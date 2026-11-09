-- Hardcore Logistics: crop trampling (feature "trampling", a live feature: it switches on and off at once).
-- A planted crop dies when the mech's body passes over it; the mound stays, empty.
--
-- How it works (calls checked against the 1.0 game exe):
--   * Every check_ms, for each mech in the world (BP_TractorMechCharacter_C), the crop manager is asked which mounds
--     are near the mech's footprint (SphereOverlapCrops, a 3D test that adds the crop size, 75 cm, to the radius it
--     is given). The path since the last check is sampled, so a fast car does not skip mounds. A mound counts when
--     its centre comes inside the footprint on that path (on legs a circle of radius_cm: the mech's body capsule is
--     150 cm, one mound tile) and is within max_height_cm of the footprint's height, so a jumping or flying mech
--     passes over.
--   * The footprint sits where the mech meets the ground:
--     - On legs it is a circle of radius_cm under the mech's centre, at the lower foot, plus a circle of
--       foot_radius_cm under each foot. Both come from the game's GetFootLocation (the foot socket minus the foot
--       radius). The walking mech's body capsule floats well above its feet (BipedalMovementComponent holds it up on
--       physics legs), which is why 0.8.0, using the capsule's bottom, missed every crop on legs. The feet sit 125 cm
--       to each side of the centre and reach forward and back in a stride, outside the body circle, so 0.8.3 missed
--       plants a foot stood on.
--     - In car and tractor mode it is the box around the vehicle's wheels, turned to its heading. The wheels come
--       from the leg module's movement component (WheelSetups bones on its SkeletalMeshComponent, radius from each
--       wheel class). The box reaches a wheel radius past the end axles and TYRE_SIDE_CM past the outer wheels; its
--       height is where the lowest wheel touches the ground. A circle around the mech's centre missed the car's
--       wheel tracks (0.8.1): the car is wider than the circle, so it cleared a strip between its wheels.
--     - Otherwise (flight, or wheels that cannot be read) it is a circle at the bottom of the leg module, falling
--       back to the bottom of the body capsule. A vehicle turning on the spot sweeps its box too.
--   * Only the mech's own body counts, in every mode (legs, car, tractor raised or lowered); tractor attachments do
--     not. A mech that has not moved does not trample, so planting next to a parked mech is safe.
--   * A planted mound is removed with Server_TryToDestroyCrops, the call the game uses when a Mound Plot is taken
--     down, which does not harvest. (The single-crop Server_TryToDestroyCrop harvests the plant first, which would
--     make trampling a free harvest.) An empty mound is then spawned in its place (Server_TryToSpawnEmptyCrop), so
--     its mulch, fertilizer and water start fresh. That call traces the spot with the BlockAllDynamic profile and
--     refuses while anything not in its ignore list is there, so the list holds the mech and everything that moves
--     with it: attached actors, modules, leg modules (car, treads), tractor attachments, the pilot, towed trailers.
--     Empty mounds, mounds being harvested and Mound Plot mounds are left alone.
--   * Crushing plays one of the game's own sounds at the crushed mounds: one sound per check, while fewer than
--     sounds_at_once are playing, so each plays out whole. When that many are playing and the oldest is in its last
--     sound_cut_ms, the new crunch starts right away (the oldest ends on its own, or FMOD trims its tail). Sounds are
--     tracked by the end times worked out when they start; the audio components are never touched again. The default
--     (trampling.sound) is a bush breaking, FMOD event Break_Bush, picked in game over the Field Plow's removal
--     sound. It is played the way the Plow plays its sounds: FMODBlueprintStatics::PlayEventAttached at the
--     mound's world position. It plays on the machine running this script (the host). "hardcore sound [name]"
--     plays it, or another one, at your mech to try them out.
--   * The crop calls need authority: this runs on the host or in single player, and there it covers every
--     player's mech.
-- The game also has an unused AMechCharacter::CanDamagePlantsOnCollision (true on legs, false in every transform
-- mode); nothing in the game calls it, so it is not used here.

local MECH_CLASS = "BP_TractorMechCharacter_C"
local MANAGER_CLASS = "BP_CropManager_C"
local PC_CLASS = "BP_FarMechPlayerController_C"
local FMOD_STATICS = "/Script/FMODStudio.Default__FMODBlueprintStatics"   -- PlayEventAtLocation lives here
local CROP_EXTRA = 75            -- SphereOverlapCrops adds the crop size (75 cm) to the radius it is given
local DEG_PER_STEP = 360 / 255   -- FCropData.Rotation is a byte
local TELEPORT_CM = 3000         -- further than this between two checks is a respawn or fast travel, not a walk
local MAX_SAMPLES = 24           -- spheres along one check's path at most
local RETRY_SECONDS = 5          -- how long to keep trying to put an empty mound back
local RECENT_SECONDS = 3         -- a mound just trampled is not looked at again for this long
local DETAIL_LOGS = 6            -- per mode (legs, car, tractor, flight): the first events are logged in full
local SOUND_DETAIL_LOGS = 3      -- per mode: the first crunches are logged with how far they were from the camera
local PUT_BACK_LOGS = 3          -- per mode: the first empty mounds put back are logged
local DIAG_RADIUS = 450          -- "hardcore mounds" lists the mounds this close to each mech
local DEFAULT_WHEEL_RADIUS = 50  -- when a wheel class's radius cannot be read
local DEFAULT_SOUND_MS = 600     -- when FMOD cannot tell a crush sound's length
local TYRE_SIDE_CM = 45          -- a vehicle's footprint reaches this far past its outer wheels' centres
local TURN_COS = math.cos(math.rad(10))   -- a vehicle turning on the spot by 10 degrees sweeps its footprint
local MECH_SEARCH_TICKS = 10     -- search the whole object table for mechs only every this many checks (1 s)
local MECH_CLASS_PATH = "/Game/Blueprints/Player/Mechs/BP_TractorMechCharacter.BP_TractorMechCharacter_C"

return function(api)
    local log = api.log
    local cfg = api.trampling or {}
    local RADIUS = tonumber(cfg.radius_cm) or 150
    local HEIGHT = tonumber(cfg.max_height_cm) or 120
    local CHECK_MS = math.max(30, tonumber(cfg.check_ms) or 100)
    local MIN_MOVE = tonumber(cfg.min_move_cm) or 10
    local FOOT_RADIUS = tonumber(cfg.foot_radius_cm) or 75
    local SOUND = type(cfg.sound) == "string" and cfg.sound or ""
    local SOUNDS_AT_ONCE = math.floor(tonumber(cfg.sounds_at_once) or 2)
    local SOUND_GAP = (tonumber(cfg.sound_gap_ms) or 0) / 1000
    -- sound_cut_ms: a number or a list of milliseconds. Each window lets one more crunch start beyond sounds_at_once
    -- once the oldest playing crunch has at most that long left ({750, 500}: a 3rd in its last 750 ms, a 4th in its
    -- last 500 ms).
    local SOUND_CUTS = {}
    do
        local cuts = cfg.sound_cut_ms
        if cuts == nil then cuts = { 750, 500, 400, 300, 200, 100 } end
        if type(cuts) ~= "table" then cuts = { cuts } end
        for _, v in ipairs(cuts) do
            v = tonumber(v)
            if v and v > 0 then SOUND_CUTS[#SOUND_CUTS + 1] = v end
        end
        table.sort(SOUND_CUTS, function(a, b) return a > b end)
    end
    -- In car, tractor and flight mode, a crunch further than this from the camera plays this far from it instead, in
    -- the same direction (0: off). The chase camera trails far behind the vehicle.
    local VEHICLE_SOUND_MAX = tonumber(cfg.vehicle_sound_max_cm) or 1000
    local SPACING = math.max(25, RADIUS / 2)
    local FOOT_QUERY = math.max(0, math.sqrt(FOOT_RADIUS * FOOT_RADIUS + HEIGHT * HEIGHT) - CROP_EXTRA)

    local lastPoint = {}         -- mech full name -> its ground point at the last check that counted
    local lastFeet = {}          -- mech full name -> its feet where they were last checked (legs)
    local recent = {}            -- crop id -> clock time it was trampled
    local respawns = {}          -- empty mounds still to put back: {loc, yaw, mech, pc, since, tries}
    local stats = { events = 0, plants = 0, putBack = 0, putBackAtOnce = 0, lost = 0, errors = 0, sounds = 0,
                    soundsSkipped = 0, soundsExtra = {},    -- soundsExtra[i]: crunches let in by sound_cut_ms window i
                    soundsByMode = {},                      -- mode (legs, car, tractor) -> crunches started
                    camera = {} }                           -- mode -> {min, max} camera distance (m) at crunches, max km/h
    local soundOff = SOUND == ""
    -- Crush sounds still playing, as their end times (clock seconds), and the start time of the last one. Only plain
    -- numbers are kept between checks: the audio components destroy themselves when their sound ends and the game
    -- then frees them, so calling them in a later check reads freed memory (0.8.9 kept the components and called
    -- IsPlaying / GetLength / Stop on them later, and crashed the game within a minute).
    local playing, lastSound = {}, -math.huge
    local detailLeft = {}        -- mode -> detailed event logs left
    local soundDetailLeft = {}   -- mode -> crunch logs left (with the distance from the camera)
    local putBackLeft = {}       -- mode -> "empty mound put back" logs left
    local errorLeft, lostLeft, retryLogsLeft = 20, 10, 10
    local manager = nil
    local wasActive, clientLogged, shapeLogged, resultLogged = false, false, false, false
    local tickCount = 0

    -- ------------------------------------------------------------------ small helpers

    local function valid(o)
        if o == nil then return false end
        local ok, v = pcall(function() return o:IsValid() end)
        return ok and v == true
    end

    -- an object, or an object wrapped the way UE4SS hands back array elements and out parameters (:get())
    local function asObject(v)
        if v == nil then return nil end
        if valid(v) then return v end
        local ok, g = pcall(function() return v:get() end)
        if ok and valid(g) then return g end
        return nil
    end

    local function num(v)
        if type(v) == "number" then return v end
        if type(v) == "userdata" then
            local ok, x = pcall(function() return v:get() end)
            if ok and type(x) == "number" then return x end
        end
        return tonumber(v)
    end

    -- FVector values come back as Lua tables or as UE4SS struct objects; read either
    local function vec(v)
        if v == nil then return nil end
        local function read(s)
            local x, y, z = num(s.X), num(s.Y), num(s.Z)
            if x and y and z then return { X = x, Y = y, Z = z } end
            return nil
        end
        local ok, r = pcall(read, v)
        if ok and r then return r end
        ok, r = pcall(function() return read(v:get()) end)
        if ok and r then return r end
        return nil
    end

    -- arrays come back as Lua tables or as UE4SS TArray objects (elements read with :get())
    local function each(list, fn)
        if list == nil then return end
        if type(list) == "table" then
            for _, v in ipairs(list) do fn(v) end
        else
            list:ForEach(function(_, e) fn(e:get()) end)
        end
    end

    local function shape(t)
        if type(t) ~= "table" then return type(t) end
        local keys = {}
        for k, v in pairs(t) do
            keys[#keys + 1] = tostring(k) .. ":" .. type(v)
            if #keys >= 16 then break end
        end
        return "{" .. table.concat(keys, ", ") .. "}"
    end

    local function shortName(o)
        local ok, s = pcall(function() return o:GetFName():ToString() end)
        return ok and tostring(s) or "?"
    end

    local function fail(err)
        stats.errors = stats.errors + 1
        if errorLeft > 0 or stats.errors % 100 == 0 then
            errorLeft = errorLeft - 1
            log("trampling: " .. tostring(err))
        end
    end

    -- 2D distance from q to the segment a-b, and the segment's height at the closest point
    local function nearest(a, b, q)
        local abx, aby = b.X - a.X, b.Y - a.Y
        local len2 = abx * abx + aby * aby
        local t = 0
        if len2 > 0 then t = math.max(0, math.min(1, ((q.X - a.X) * abx + (q.Y - a.Y) * aby) / len2)) end
        local dx, dy = q.X - (a.X + abx * t), q.Y - (a.Y + aby * t)
        return math.sqrt(dx * dx + dy * dy), a.Z + (b.Z - a.Z) * t
    end

    -- ------------------------------------------------------------------ the game's objects

    local function getManager()
        if valid(manager) then return manager end
        manager = nil
        local ok, m = pcall(FindFirstOf, MANAGER_CLASS)
        if ok and valid(m) then manager = m end
        return manager
    end

    -- The mechs. The whole object table is searched (FindAllOf) only every MECH_SEARCH_TICKS checks (every check while
    -- none is known); in between they are found again by their paths (StaticFindObject, a quick lookup). Searching the
    -- whole table every 100 ms was a steady cost inside game frames. Only the paths are kept between checks.
    local mechPaths, mechSearchTick = {}, -math.huge
    local function mechs()
        local list = {}
        if #mechPaths == 0 or tickCount - mechSearchTick >= MECH_SEARCH_TICKS then
            mechPaths, mechSearchTick = {}, tickCount
            local ok, found = pcall(FindAllOf, MECH_CLASS)
            if ok and type(found) == "table" then
                for _, m in ipairs(found) do
                    if valid(m) then
                        local full = m:GetFullName()
                        local path = full:match("^%S+ (.+)$")
                        if path and not full:find("Default__", 1, true) then
                            list[#list + 1] = m
                            mechPaths[#mechPaths + 1] = path
                        end
                    end
                end
            end
            return list
        end
        for _, p in ipairs(mechPaths) do
            local ok, m = pcall(StaticFindObject, p)
            if ok and valid(m) then list[#list + 1] = m end
        end
        if #list < #mechPaths then mechSearchTick = -math.huge end   -- one is gone: search again next check
        return list
    end
    -- a new mech (a player joining, a respawn): search again at the next check. The callback only sets a number.
    pcall(NotifyOnNewObject, MECH_CLASS_PATH, function() mechSearchTick = -math.huge end)

    -- the crop calls take the player controller of whoever did it; a parked mech uses the host's
    local function controllerFor(mech)
        local pc = nil
        if mech then pcall(function() pc = mech.FMPlayerController end) end
        if valid(pc) then return pc end
        local ok, first = pcall(FindFirstOf, PC_CLASS)
        if ok and valid(first) then return first end
        return nil
    end

    -- where the player's camera is, or nil. FMOD hears from the camera unless the game moves its listener.
    local function cameraLocation(mech)
        local pc = controllerFor(mech)
        if not pc then return nil end
        local loc = nil
        pcall(function() loc = vec(pc.PlayerCameraManager:GetCameraLocation()) end)
        return loc
    end

    local function metresBetween(a, b)
        if not a or not b then return nil end
        local dx, dy, dz = a.X - b.X, a.Y - b.Y, a.Z - b.Z
        return math.sqrt(dx * dx + dy * dy + dz * dz) / 100
    end

    -- "2.1 m from the mech, 9.8 m from the camera"
    local function describeDistances(mech, loc)
        local mechLoc = nil
        pcall(function() mechLoc = vec(mech:K2_GetActorLocation()) end)
        local fromMech, fromCamera = metresBetween(loc, mechLoc), metresBetween(loc, cameraLocation(mech))
        return string.format("%s m from the mech, %s m from the camera",
            fromMech and string.format("%.1f", fromMech) or "?", fromCamera and string.format("%.1f", fromCamera) or "?")
    end

    local function isTransformed(mech)
        local ok, t = pcall(function() return mech:IsTransformed() end)
        return ok and t == true
    end

    local function legModule(mech)
        local ok, leg = pcall(function() return mech:GetEquippedLegModule() end)
        if ok and valid(leg) then return leg end
        return nil
    end

    local function modeOf(mech)
        if not isTransformed(mech) then return "legs" end
        local leg = legModule(mech)
        local name = leg and shortName(leg:GetClass()) or "?"
        if name:find("Car", 1, true) then return "car" end
        if name:find("Flight", 1, true) then return "flight" end
        if name:find("Treads", 1, true) or name:find("Plough", 1, true) or name:find("Harvester", 1, true)
            or name:find("Fertilizer", 1, true) or name:find("Pathmaker", 1, true) then
            return "tractor"
        end
        return name
    end

    -- ground speed in km/h: the mech's, or in a vehicle mode its leg module's if that is faster (nil if unknown)
    local function kmhOf(mech, mode)
        local best = nil
        local function speed(actor)
            local v = nil
            pcall(function() v = vec(actor:GetVelocity()) end)
            if v then
                local kmh = math.sqrt(v.X * v.X + v.Y * v.Y) * 0.036
                if not best or kmh > best then best = kmh end
            end
        end
        speed(mech)
        if mode ~= "legs" then
            local leg = legModule(mech)
            if leg then speed(leg) end
        end
        return best
    end

    -- Where a crunch at loc plays, how far loc is from the camera (m), and whether it was moved. The listener is at
    -- the camera, and in car mode the chase camera sat 18 m from the crushed mounds (0.8.15 test); driving fast there,
    -- no crunch was heard. So in a vehicle mode a crunch further than vehicle_sound_max_cm from the camera plays that
    -- far from it, in the same direction. On legs the crunch stays on the mound.
    local function soundSpot(mech, mode, loc)
        local cam = cameraLocation(mech)
        local d = metresBetween(loc, cam)
        if not d or mode == "legs" or VEHICLE_SOUND_MAX <= 0 or d * 100 <= VEHICLE_SOUND_MAX then
            return loc, d, false
        end
        local f = VEHICLE_SOUND_MAX / (d * 100)
        return { X = cam.X + (loc.X - cam.X) * f, Y = cam.Y + (loc.Y - cam.Y) * f, Z = cam.Z + (loc.Z - cam.Z) * f },
            d, true
    end

    local function capsuleBottom(mech, loc)
        local half = 0
        pcall(function() half = num(mech.CapsuleComponent:GetScaledCapsuleHalfHeight()) or 0 end)
        return loc.Z - half
    end

    -- where the walking mech's feet touch the ground: the game's GetFootLocation (foot socket minus foot radius)
    local function feetOf(mech)
        local feet = {}
        for _, right in ipairs({ false, true }) do
            local ok, f = pcall(function() return vec(mech:GetFootLocation(right)) end)
            if ok and f then
                f.side = right and "right" or "left"
                feet[#feet + 1] = f
            end
        end
        return feet
    end

    local function lowerFoot(mech, feet)
        local z = nil
        for _, f in ipairs(feet or feetOf(mech)) do
            if z == nil or f.Z < z then z = f.Z end
        end
        return z
    end

    local function moduleBottom(mech)
        local leg = legModule(mech)
        if not leg then return nil end
        local origin, extent = {}, {}
        local ok = pcall(function() leg:GetActorBounds(true, origin, extent, false) end)
        local o, e = vec(origin), vec(extent)
        if ok and o and e and e.Z > 0 then return o.Z - e.Z end
        return nil
    end

    -- a leg module's wheels, from its movement component's WheelSetups: the bone each wheel sits on and the wheel
    -- class's radius (car 85 cm, tractor treads 30 cm). Cached per leg module class; empty when it has none (flight).
    local wheelCache = {}
    local function wheelsOf(leg)
        local cls = shortName(leg:GetClass())
        if wheelCache[cls] then return wheelCache[cls] end
        local list = {}
        local ok, err = pcall(function()
            each(leg:GetMovementComponent().WheelSetups, function(s)
                local name = api.asText(s.BoneName)
                if name and name ~= "" and name ~= "None" then
                    local radius = DEFAULT_WHEEL_RADIUS
                    pcall(function()
                        local r = num(s.WheelClass:GetCDO().WheelRadius)
                        if r and r > 0 then radius = r end
                    end)
                    list[#list + 1] = { name = name, fname = api.makeName(name), radius = radius }
                end
            end)
        end)
        wheelCache[cls] = list
        local names = {}
        for _, w in ipairs(list) do names[#names + 1] = string.format("%s (radius %.0f)", w.name, w.radius) end
        log(string.format("trampling: %s has %d wheels%s%s", cls, #list,
            #list > 0 and (": " .. table.concat(names, ", ")) or "", ok and "" or (" (" .. tostring(err) .. ")")))
        return list
    end

    -- A vehicle's footprint: the box around its wheels, turned to its heading, reaching one wheel radius past the
    -- front and back axles and half a tyre past the outer wheels; its height is where the lowest wheel touches the
    -- ground (wheel centre minus radius).
    local function wheelBox(leg)
        local wheels = wheelsOf(leg)
        if #wheels < 2 then return nil end
        local mesh = asObject(leg.SkeletalMeshComponent)
        if not mesh then return nil end
        local pts, lowest, radius = {}, nil, 0
        for _, w in ipairs(wheels) do
            local ok, p = pcall(function() return vec(mesh:GetSocketLocation(w.fname)) end)
            if ok and p then
                pts[#pts + 1] = p
                if lowest == nil or p.Z - w.radius < lowest then lowest = p.Z - w.radius end
                radius = math.max(radius, w.radius)
            end
        end
        if #pts < 2 then return nil end
        local f = vec(leg:GetActorForwardVector())
        local len = f and math.sqrt(f.X * f.X + f.Y * f.Y) or 0
        if len < 1e-3 then return nil end
        local fx, fy = f.X / len, f.Y / len
        local cx, cy = 0, 0
        for _, p in ipairs(pts) do cx, cy = cx + p.X, cy + p.Y end
        cx, cy = cx / #pts, cy / #pts
        local hl, hw = 0, 0
        for _, p in ipairs(pts) do
            local dx, dy = p.X - cx, p.Y - cy
            hl = math.max(hl, math.abs(dx * fx + dy * fy))
            hw = math.max(hw, math.abs(dy * fx - dx * fy))
        end
        return { X = cx, Y = cy, Z = lowest, kind = "box", how = "wheels", fx = fx, fy = fy,
                 hl = hl + radius, hw = hw + TYRE_SIDE_CM, wheels = #pts }
    end

    -- Where and how the mech meets the ground. On legs: a circle of radius_cm under its centre, at its lower foot.
    -- In car or tractor mode: the box around its wheels. Otherwise (flight, or wheels that cannot be read): a circle
    -- at the bottom of the leg module, or of the body capsule as a last resort.
    local function footprint(mech)
        local loc = vec(mech:K2_GetActorLocation())
        if not loc then return nil end
        if isTransformed(mech) then
            local leg = legModule(mech)
            if leg then
                local box = wheelBox(leg)
                if box then return box end
                local z = moduleBottom(mech)
                if z then return { X = loc.X, Y = loc.Y, Z = z, kind = "circle", how = "module" } end
            end
        else
            local feet = feetOf(mech)
            local z = lowerFoot(mech, feet)
            if z then return { X = loc.X, Y = loc.Y, Z = z, kind = "circle", how = "feet", feet = feet } end
        end
        return { X = loc.X, Y = loc.Y, Z = capsuleBottom(mech, loc), kind = "circle", how = "capsule" }
    end

    local function describeFootprint(p)
        if p.kind == "box" then
            return string.format("%.1f x %.1f m around %d wheels", 2 * p.hl / 100, 2 * p.hw / 100, p.wheels)
        end
        if p.feet and #p.feet > 0 then
            return string.format("%.0f cm circle and %.0f cm under each foot", RADIUS, FOOT_RADIUS)
        end
        return string.format("%.0f cm circle, ground from the %s", RADIUS, p.how)
    end

    -- t in [0, 1] with |a - t * d| <= h, as an interval (nil when there is none)
    local function interval(a, d, h)
        if math.abs(d) < 1e-6 then
            if math.abs(a) <= h then return 0, 1 end
            return nil
        end
        local t1, t2 = (a - h) / d, (a + h) / d
        if t1 > t2 then t1, t2 = t2, t1 end
        t1, t2 = math.max(0, t1), math.min(1, t2)
        if t1 > t2 then return nil end
        return t1, t2
    end

    -- Is q inside box b (heading b.fx, b.fy; half length hl, half width hw) while its centre slides from a to b?
    -- Returns the point of the slide where it is (0..1) and q's distance from the box's centre line there.
    local function inSweptBox(a, b, q)
        local fx, fy = b.fx, b.fy
        local qx, qy, mx, my = q.X - a.X, q.Y - a.Y, b.X - a.X, b.Y - a.Y
        local l1, h1 = interval(qx * fx + qy * fy, mx * fx + my * fy, b.hl)
        if not l1 then return nil end
        local l2, h2 = interval(qy * fx - qx * fy, my * fx - mx * fy, b.hw)
        if not l2 then return nil end
        local lo, hi = math.max(l1, l2), math.min(h1, h2)
        if lo > hi then return nil end
        local t = (lo + hi) / 2
        local side = (qy - my * t) * fx - (qx - mx * t) * fy
        return t, math.abs(side)
    end

    -- The mech and everything that moves with it, for the empty-mound call's ignore list: its modules, tools, leg
    -- modules (car, treads) and their tractor attachments, the Large Objects it holds, its towed trailers and its
    -- pilot. Only return values and properties of live objects are read here. UE4SS hands an out-parameter array
    -- back as a view into memory the game frees right after the call: 0.8.2 read GetAttachedActors' out array that
    -- way, about 30 times per crushed mound, and crashed the game once that memory was reused.
    local function movingWith(mech)
        local list, seen = {}, {}
        local function add(a)
            a = asObject(a)
            if not a then return nil end
            local key = a:GetFullName()
            if not seen[key] then
                seen[key] = true
                list[#list + 1] = a
            end
            return a
        end
        local function addAll(getter)
            pcall(function() each(getter(), add) end)
        end
        add(mech)
        addAll(function() return mech:GetAllModulesAsActors() end)
        addAll(function() return mech:GetAllTools() end)
        addAll(function() return mech:GetHeldActors() end)
        addAll(function() return mech:GetTowedTrailers() end)
        local legs = {}
        pcall(function()
            each(mech:GetAllLegModules(), function(l)
                local a = add(l)
                if a then legs[#legs + 1] = a end
            end)
        end)
        local equipped = legModule(mech)
        if equipped then legs[#legs + 1] = add(equipped) end
        for _, leg in ipairs(legs) do      -- tractor attachments hang off the treads module (a live property)
            pcall(function() leg.InstalledTractorAttachments:ForEach(function(_, v) add(v:get()) end) end)
        end
        pcall(function() add(mech.PilotCharacter) end)
        return list
    end

    -- ids of the mounds within (radius + 75 cm) of point c, added to into (once each)
    local function overlap(mgr, c, radius, into, seen)
        local ids = mgr:SphereOverlapCrops(c, radius)
        each(ids, function(v)
            local id = num(v)
            if id and not seen[id] then
                seen[id] = true
                into[#into + 1] = id
            end
        end)
    end

    local function readCrop(mgr, id)
        local out = {}
        local found = mgr:FindCrop(id, out)
        if found == false then return nil end
        local plant = api.asText(out.PlantName)
        local loc = vec(out.Location)
        if plant == nil or loc == nil then
            if not shapeLogged then
                shapeLogged = true
                log("trampling: cannot read mound " .. tostring(id) .. " (FindCrop gave " .. shape(out) .. ")")
            end
            return nil
        end
        return {
            id = id, plant = plant, planted = plant ~= "" and plant ~= "None", loc = loc,
            yaw = (num(out.Rotation) or 0) * DEG_PER_STEP,
            plot = out.bIsPartOfPlot == true, harvesting = out.bIsHarvesting == true,
        }
    end

    -- ------------------------------------------------------------------ the crush sound

    -- short names for "hardcore sound <name>"; any /Game/FMOD/Events/... path works too
    local SOUND_NAMES = {
        plough = "/Game/FMOD/Events/TransformModes/Plough/Crops/Plough_Remove_Tile_Crop",
        bush = "/Game/FMOD/Events/Break/Break_Bush",
        bigbush = "/Game/FMOD/Events/Break/Break_Bush_Large",
        weed = "/Game/FMOD/Events/Harvest/Harvest_Weed",
        noxious = "/Game/FMOD/Events/Events/Noxious_Plant_Removal/Noxious_Plant_Removed",
    }
    local ATTACH_KEEP_WORLD = 1        -- EAttachLocation::KeepWorldPosition: Location is a world position
    local soundChecked = false

    local function soundName(path) return (path or ""):match("([^/.]+)$") or "?" end

    -- an FMOD event asset by path (/Game/FMOD/Events/...), found in memory or loaded
    local function loadEvent(path)
        if not path:match("%.[^/]+$") then path = path .. "." .. path:match("([^/]+)$") end
        local ev = StaticFindObject(path)
        if not valid(ev) then
            pcall(LoadAsset, path)
            ev = StaticFindObject(path)
        end
        return valid(ev) and ev or nil, path
    end

    -- The game's FMOD event for a crushed mound (trampling.sound; default Break_Bush) and FMOD's statics, looked up
    -- for every play (a hash lookup; the event is loaded if it is not in memory); nil when switched off or missing.
    -- Nothing is cached: an object kept from an earlier check may have been freed since.
    local function crushSound()
        if soundOff then return nil end
        local ev, path = loadEvent(SOUND)
        local statics = StaticFindObject(FMOD_STATICS)
        if not ev or not valid(statics) then
            soundOff = true
            log("trampling: no crush sound (" .. (ev and "FMOD is not loaded" or ("no FMOD event " .. path)) .. ")")
            return nil
        end
        return ev, statics
    end

    -- Play event ev at world position loc the way the Field Plow plays it: PlayEventAttached, an FMOD audio
    -- component attached to the crop manager's root at that world position, destroyed when the sound ends.
    -- (0.8.5 used PlayEventAtLocation, which takes its transform as a const reference: UE4SS treats that as an
    -- out-parameter and never read the Lua table, so every sound played at the world origin, out of earshot.)
    local function playAt(statics, ev, mgr, loc)
        local root = nil
        pcall(function() root = mgr:K2_GetRootComponent() end)
        if not valid(root) then pcall(function() root = mgr.RootComponent end) end
        if not valid(root) then error("the crop manager has no root component to attach the sound to") end
        return statics:PlayEventAttached(ev, root, api.makeName("None"), { X = loc.X, Y = loc.Y, Z = loc.Z },
            ATTACH_KEEP_WORLD, false, true, true)
    end

    -- A sound just started, read in the same check (the component certainly exists now): its length in ms (nil if
    -- unknown) and a line for the log.
    local function lengthOf(comp)
        local len = nil
        pcall(function() len = num(asObject(comp):GetLength()) end)
        if len and len > 0 then return len end
        return nil
    end

    local function describePlay(comp)
        local on = nil
        pcall(function() on = asObject(comp):IsPlaying() end)
        local len = lengthOf(comp)
        return string.format("audio component %s, playing %s, length %s ms", asObject(comp) and "made" or "missing",
            tostring(on), len and string.format("%.0f", len) or "?")
    end

    -- how many crush sounds are still playing, by the end times worked out when they started
    local function stillPlaying(now)
        local keep = {}
        for _, ends in ipairs(playing) do
            if now < ends then keep[#keep + 1] = ends end
        end
        playing = keep
        return #keep
    end

    -- "a 3rd", "a 4th", "an 8th", "an 11th"
    local function nth(n)
        local mod100 = n % 100
        local suffix = (mod100 >= 11 and mod100 <= 13) and "th" or (({ "st", "nd", "rd" })[n % 10] or "th")
        local article = (n == 8 or n == 11 or n == 18 or (n >= 80 and n <= 89)) and "an " or "a "
        return article .. n .. suffix
    end

    -- the sound_cut_ms windows in words: "a 3rd may start in the oldest's last 750 ms, a 4th in its last 500 ms"
    local function describeCuts()
        if #SOUND_CUTS == 0 then return "no more until one ends" end
        local parts = {}
        for i, cut in ipairs(SOUND_CUTS) do
            parts[i] = string.format(i == 1 and "%s may start in the oldest's last %.0f ms" or "%s in its last %.0f ms",
                nth(SOUNDS_AT_ONCE + i), cut)
        end
        return table.concat(parts, ", ")
    end

    -- One crush sound for the mounds crushed in this check, at the middle one, when fewer than sounds_at_once are
    -- playing and sound_gap_ms has passed. FMOD lets only a few copies of an event play together and cuts the oldest
    -- off when more start: 0.8.6 started up to 3 per check (30 a second), so each was cut off right after it began and
    -- walking through a field sounded like clicks. Past sounds_at_once, each sound_cut_ms window lets one more crunch
    -- start over the end of the oldest: with {750, 500}, a 3rd once the oldest has at most 750 ms left and a 4th once
    -- it has at most 500 ms left. That happens only some of the time: the crush has to land in the oldest's last
    -- stretch. The oldest is never stopped (its component may be gone by then); it simply plays out.
    local function playCrushSound(mgr, kill, now, mech, mode)
        if #kill == 0 or SOUNDS_AT_ONCE <= 0 then return end
        if now - lastSound < SOUND_GAP then
            stats.soundsSkipped = stats.soundsSkipped + 1
            return
        end
        local count = stillPlaying(now)
        local extra = count - SOUNDS_AT_ONCE + 1     -- which window this crunch needs, when it is past sounds_at_once
        if extra >= 1 then
            local cut = SOUND_CUTS[extra]
            if not cut or (playing[1] - now) * 1000 > cut then
                stats.soundsSkipped = stats.soundsSkipped + 1
                return
            end
        end
        local ev, statics = crushSound()
        if not ev then return end
        local c = kill[math.floor((#kill + 1) / 2)]
        local at, camDist, pulled = soundSpot(mech, mode, c.loc)
        local ok, comp = pcall(playAt, statics, ev, mgr, at)
        if not ok then
            soundOff = true
            log("trampling: the crush sound failed, so it is off for this session: " .. tostring(comp))
            return
        end
        lastSound = now
        playing[#playing + 1] = now + (lengthOf(comp) or DEFAULT_SOUND_MS) / 1000
        table.sort(playing)
        stats.sounds = stats.sounds + 1
        stats.soundsByMode[mode] = (stats.soundsByMode[mode] or 0) + 1
        local kmh = kmhOf(mech, mode)
        if camDist then
            local r = stats.camera[mode] or { min = camDist, max = camDist, kmh = 0 }
            r.min, r.max, r.kmh = math.min(r.min, camDist), math.max(r.max, camDist), math.max(r.kmh, kmh or 0)
            stats.camera[mode] = r
        end
        if extra >= 1 then stats.soundsExtra[extra] = (stats.soundsExtra[extra] or 0) + 1 end
        if not soundChecked then
            soundChecked = true
            log(string.format("trampling: crush sound %s (%d at a time, at least %.0f ms apart; %s): %s",
                soundName(SOUND), SOUNDS_AT_ONCE, SOUND_GAP * 1000, describeCuts(), describePlay(comp)))
        end
        soundDetailLeft[mode] = soundDetailLeft[mode] or SOUND_DETAIL_LOGS
        if soundDetailLeft[mode] > 0 then
            soundDetailLeft[mode] = soundDetailLeft[mode] - 1
            log(string.format("trampling: crunch in %s mode at %s km/h, %d playing now, %s%s: %s", mode,
                kmh and string.format("%.0f", kmh) or "?", #playing, describeDistances(mech, c.loc),
                pulled and string.format(" (played %.1f m from it)", VEHICLE_SOUND_MAX / 100) or "", describePlay(comp)))
        end
    end

    -- ------------------------------------------------------------------ trampling

    -- onlyNew: just the mounds crushed in this check (the others already had their try this check)
    -- A pending empty mound keeps only its mech's full name: the mech (and its controller) are looked up fresh on
    -- every pass, never kept from an earlier check (an object kept that long may have been freed since).
    local function putMoundsBack(mgr, now, onlyNew)
        local keep, ignoreFor, byName = {}, {}, nil   -- ignoreFor: mech name -> its ignore list, built once per pass
        for _, r in ipairs(respawns) do
            if onlyNew and not r.fresh then
                keep[#keep + 1] = r
                goto continue
            end
            r.fresh = false
            if not byName then
                byName = {}
                for _, m in ipairs(mechs()) do byName[m:GetFullName()] = m end
            end
            local mech = byName[r.mechName]
            local pc = controllerFor(mech)
            local ignore = {}
            if mech then
                ignoreFor[r.mechName] = ignoreFor[r.mechName] or movingWith(mech)
                ignore = ignoreFor[r.mechName]
            end
            local ok, res = false, nil
            if pc then ok, res = pcall(function() return mgr:Server_TryToSpawnEmptyCrop(pc, r.loc, r.yaw, ignore) end) end
            if ok and res == nil and not resultLogged then
                resultLogged = true
                log("trampling: the empty-mound call gave no result; counting it as done")
            end
            if ok and res ~= false then
                stats.putBack = stats.putBack + 1
                if r.tries == 0 then stats.putBackAtOnce = stats.putBackAtOnce + 1 end
                putBackLeft[r.mode] = putBackLeft[r.mode] or PUT_BACK_LOGS
                local logIt = false
                if putBackLeft[r.mode] > 0 then
                    putBackLeft[r.mode], logIt = putBackLeft[r.mode] - 1, true
                elseif r.tries > 0 and retryLogsLeft > 0 then
                    retryLogsLeft, logIt = retryLogsLeft - 1, true
                end
                if logIt then
                    log(string.format("trampling: empty mound put back %s (%s; ignoring %d actors that move with the mech)",
                        r.tries == 0 and "at once" or ("after " .. r.tries .. " retries"), r.mode, #ignore))
                end
            elseif now - r.since < RETRY_SECONDS then
                r.tries = r.tries + 1
                keep[#keep + 1] = r
            else
                stats.lost = stats.lost + 1
                if lostLeft > 0 then
                    lostLeft = lostLeft - 1
                    log(string.format("trampling: could not put an empty mound back at (%.0f, %.0f, %.0f)%s",
                        r.loc.X, r.loc.Y, r.loc.Z, ok and "" or (": " .. tostring(res))))
                end
            end
            ::continue::
        end
        respawns = keep
    end

    -- is the mound under the footprint p on its way from prev? returns its distance from the centre line (box) or the
    -- centre (circle) and its height above the footprint
    local function underFootprint(prev, p, loc)
        local d, z
        if p.kind == "box" then
            local t, side = inSweptBox(prev, p, loc)
            if not t then return nil end
            d, z = side, prev.Z + (p.Z - prev.Z) * t
        else
            d, z = nearest(prev, p, loc)
            if d >= RADIUS then return nil end
        end
        if math.abs(loc.Z - z) > HEIGHT then return nil end
        return d, loc.Z - z
    end

    -- planted mounds (not plots, not being harvested, not just crushed) among ids that test(loc) accepts; test returns
    -- the distance to show in the log and the mound's height above the footprint
    local function crushable(mgr, ids, now, where, test, into, taken)
        for _, id in ipairs(ids) do
            if not taken[id] and not (recent[id] and now - recent[id] < RECENT_SECONDS) then
                local crop = readCrop(mgr, id)
                if crop and crop.planted and not crop.plot and not crop.harvesting then
                    local d, dz = test(crop.loc)
                    if d then
                        crop.dist, crop.dz, crop.where = d, dz, where
                        taken[id] = true
                        into[#into + 1] = crop
                    end
                end
            end
        end
    end

    -- The body (legs: the circle under the mech's centre; car, tractor: the box around its wheels), swept along its
    -- path since the last check. Returns false when the mech jumped further than a walk (respawn, fast travel).
    local function bodyKills(mgr, key, p, now, into, taken)
        local prev = lastPoint[key]
        local dx, dy = p.X - prev.X, p.Y - prev.Y
        local moved = math.sqrt(dx * dx + dy * dy)
        local turned = p.kind == "box" and (p.fx * prev.fx + p.fy * prev.fy) < TURN_COS
        if moved < MIN_MOVE and not turned then return true end   -- keep the old point: slow creeping adds up
        lastPoint[key] = p
        if moved > TELEPORT_CM then return false end
        if moved < MIN_MOVE then
            prev = p                  -- turning on the spot: the footprint where it is now
            dx, dy, moved = 0, 0, 0
        end
        local reach, spacing = RADIUS, SPACING
        if p.kind == "box" then
            reach = math.sqrt(p.hl * p.hl + p.hw * p.hw)
            spacing = math.max(25, math.min(p.hl, p.hw))
        end
        local query = math.max(0, math.sqrt(reach * reach + HEIGHT * HEIGHT) - CROP_EXTRA)
        local samples = math.min(MAX_SAMPLES, math.max(1, math.ceil(moved / spacing)))
        local ids, seen = {}, {}
        for i = 1, samples do
            local t = i / samples
            overlap(mgr, { X = prev.X + dx * t, Y = prev.Y + dy * t, Z = prev.Z + (p.Z - prev.Z) * t }, query, ids, seen)
        end
        crushable(mgr, ids, now, p.kind == "box" and "centre line" or "centre",
            function(loc) return underFootprint(prev, p, loc) end, into, taken)
        return true
    end

    -- On legs, each foot crushes what it stands on: a circle of foot_radius_cm where the foot is now, checked once the
    -- foot has moved. A striding foot lands well outside the body circle (the feet are 125 cm to each side of the
    -- centre and reach forward and back), so the circle alone missed plants a foot was standing on (0.8.3 test).
    local function footKills(mgr, key, p, now, into, taken)
        local before = lastFeet[key] or {}
        local kept = {}
        for i, f in ipairs(p.feet) do
            local b = before[i]
            if b and math.sqrt((f.X - b.X) ^ 2 + (f.Y - b.Y) ^ 2) < MIN_MOVE then
                kept[i] = b              -- keep the old point: a slowly sliding foot still adds up
            else
                kept[i] = f
                if b then
                    local ids, seen = {}, {}
                    overlap(mgr, f, FOOT_QUERY, ids, seen)
                    crushable(mgr, ids, now, f.side .. " foot", function(loc)
                        local d = math.sqrt((loc.X - f.X) ^ 2 + (loc.Y - f.Y) ^ 2)
                        if d >= FOOT_RADIUS or math.abs(loc.Z - f.Z) > HEIGHT then return nil end
                        return d, loc.Z - f.Z
                    end, into, taken)
                end
            end
        end
        lastFeet[key] = kept
    end

    local function checkMech(mgr, mech, now)
        local key = mech:GetFullName()
        local p = footprint(mech)
        if not p then return end
        local prev = lastPoint[key]
        if not prev or prev.kind ~= p.kind or prev.how ~= p.how then
            lastPoint[key], lastFeet[key] = p, p.feet   -- first sight, or a new mode: start from here
            return
        end
        local kill, taken = {}, {}
        if not bodyKills(mgr, key, p, now, kill, taken) then
            lastFeet[key] = p.feet       -- a teleport: the feet start over too
            return
        end
        if p.feet then footKills(mgr, key, p, now, kill, taken) end
        if #kill == 0 then return end

        local pc = controllerFor(mech)
        if not pc then error("no player controller to give the crop manager") end
        local list = {}
        for _, c in ipairs(kill) do
            list[#list + 1] = c.id
            recent[c.id] = now
        end
        mgr:Server_TryToDestroyCrops(pc, list)
        stats.events, stats.plants = stats.events + 1, stats.plants + #kill
        local mode = modeOf(mech)
        playCrushSound(mgr, kill, now, mech, mode)
        for _, c in ipairs(kill) do
            respawns[#respawns + 1] = { loc = c.loc, yaw = c.yaw, mechName = key, since = now, tries = 0,
                                        fresh = true, mode = mode }
        end
        detailLeft[mode] = detailLeft[mode] or DETAIL_LOGS
        if detailLeft[mode] > 0 then
            detailLeft[mode] = detailLeft[mode] - 1
            local parts = {}
            for i, c in ipairs(kill) do
                if i > 6 then
                    parts[#parts + 1] = string.format("and %d more", #kill - 6)
                    break
                end
                parts[#parts + 1] = string.format("%s %.0f cm from the %s, %+.0f cm", c.plant, c.dist, c.where, c.dz)
            end
            log(string.format("trampling: %s (%s, %s) crushed %d: %s", shortName(mech), mode, describeFootprint(p),
                #kill, table.concat(parts, "; ")))
        end
    end

    local function tick()
        tickCount = tickCount + 1
        if not api.isActive("trampling") then
            if wasActive then
                wasActive = false
                lastPoint, lastFeet, respawns = {}, {}, {}
                log("trampling off")
            end
            return
        end
        local mgr = getManager()
        if not mgr then return end
        local okAuth, auth = pcall(function() return mgr:HasAuthority() end)
        if okAuth and auth == false then
            if not clientLogged then
                clientLogged = true
                log("trampling: this game is a client; the host's copy of the mod tramples the crops")
            end
            return
        end
        if not wasActive then
            wasActive = true
            log(string.format("trampling on: radius %.0f cm, height %.0f cm, checked every %.0f ms", RADIUS, HEIGHT,
                CHECK_MS))
        end
        local now = os.clock()
        -- retries first (a mound crushed in an earlier check), then the mounds crushed in this check, at once
        if #respawns > 0 then
            local ok, err = pcall(putMoundsBack, mgr, now, false)
            if not ok then fail(err) end
        end
        for _, mech in ipairs(mechs()) do
            local ok, err = pcall(checkMech, mgr, mech, now)
            if not ok then fail(err) end
        end
        if #respawns > 0 then
            local ok, err = pcall(putMoundsBack, mgr, now, true)
            if not ok then fail(err) end
        end
        if tickCount % 50 == 0 then
            for id, t in pairs(recent) do
                if now - t >= RECENT_SECONDS then recent[id] = nil end
            end
        end
    end

    -- ------------------------------------------------------------------ readouts

    -- "4 as a 3rd in the oldest's last 750 ms, 1 as a 4th in its last 500 ms"
    local function describeExtras()
        local parts = {}
        for i, cut in ipairs(SOUND_CUTS) do
            parts[i] = string.format(i == 1 and "%d as %s in the oldest's last %.0f ms" or "%d as %s in its last %.0f ms",
                stats.soundsExtra[i] or 0, nth(SOUNDS_AT_ONCE + i), cut)
        end
        return #parts > 0 and ", " .. table.concat(parts, ", ") or ""
    end

    -- "car 3, legs 12"
    local function describeByMode()
        local parts = {}
        for mode, n in pairs(stats.soundsByMode) do parts[#parts + 1] = mode .. " " .. n end
        table.sort(parts)
        return #parts > 0 and table.concat(parts, ", ") or "none yet"
    end

    -- "car 18.2-26.0 m (up to 61 km/h), legs 7.9-9.4 m (up to 9 km/h)": how far the camera was from the crushed mounds
    local function describeCameraRanges()
        local parts = {}
        for mode, r in pairs(stats.camera) do
            parts[#parts + 1] = string.format("%s %.1f-%.1f m (up to %.0f km/h)", mode, r.min, r.max, r.kmh)
        end
        table.sort(parts)
        return #parts > 0 and table.concat(parts, ", ") or "none yet"
    end

    local function summary()
        return string.format("trampling %s for this world (radius %.0f cm, height %.0f cm): %d events, %d plants crushed, "
            .. "%d empty mounds put back (%d at once), %d could not be, %d crush sounds%s (by mode: %s; %d skipped while "
            .. "others played%s), %d errors; camera to crushed mound: %s", api.isActive("trampling") and "ON" or "off",
            RADIUS, HEIGHT, stats.events, stats.plants, stats.putBack, stats.putBackAtOnce, stats.lost, stats.sounds,
            soundOff and " (sound off)" or "", describeByMode(), stats.soundsSkipped, describeExtras(), stats.errors,
            describeCameraRanges())
    end

    api.addReport(function(out) out(summary()) end)

    -- a new map (even the same world reloaded) has new mechs and mounds: forget positions and pending mounds
    local function forgetWorld()
        lastPoint, lastFeet, respawns, recent, manager, playing = {}, {}, {}, {}, nil, {}
        mechPaths, mechSearchTick = {}, -math.huge
    end
    api.onMapLoaded(forgetWorld)
    if api.onMapLeaving then api.onMapLeaving(forgetWorld) end   -- before the old map's objects are freed

    -- "hardcore sound [name | /Game/FMOD/Events/... path | camera]": play the crush sound at your mech now, to hear it
    -- without trampling anything. With a name (plough, bush, bigbush, weed, noxious) or an event path, that sound plays
    -- and is used for crushed crops for the rest of the session; set trampling.sound in mod_config.json to keep it.
    -- "camera" plays it right at the camera instead: if that is heard and the plain command is not, the sound is
    -- too far from the listener in that mode.
    api.addCommand("sound", function(out, arg)
        local mgr = getManager()
        if not mgr then out("no crop manager in this map"); return end
        local mech = mechs()[1]
        if not mech then out("no mech in this map"); return end
        local atCamera = arg == "camera"
        if atCamera then arg = nil end
        if arg and arg ~= "" then
            local ev, full = loadEvent(SOUND_NAMES[arg] or arg)
            if not ev then
                local names = {}
                for k in pairs(SOUND_NAMES) do names[#names + 1] = k end
                table.sort(names)
                out("no FMOD event " .. full .. "; names: " .. table.concat(names, ", "))
                return
            end
            SOUND, soundOff, soundChecked = SOUND_NAMES[arg] or arg, false, false
        end
        local ev, statics = crushSound()
        if not ev then
            out("no crush sound (" .. (SOUND == "" and "switched off in mod_config.json" or "see the log") .. ")")
            return
        end
        local mode = modeOf(mech)
        local spot, at, camDist, pulled   -- spot: where it happens; at: where it plays (a vehicle's is pulled in)
        if atCamera then
            spot = cameraLocation(mech)
            if not spot then out("could not find the camera"); return end
            at = spot
        else
            spot = footprint(mech) or vec(mech:K2_GetActorLocation())
            at, camDist, pulled = soundSpot(mech, mode, spot)
        end
        local ok, comp = pcall(playAt, statics, ev, mgr, at)
        if not ok then
            out("playing " .. soundName(SOUND) .. " failed: " .. tostring(comp))
            return
        end
        out(string.format("played %s %s (%s mode, %s%s): %s", soundName(SOUND),
            atCamera and "at the camera" or ("at " .. shortName(mech) .. "'s feet"), mode,
            describeDistances(mech, spot), pulled and string.format(" (played %.1f m from it)", VEHICLE_SOUND_MAX / 100) or "",
            describePlay(comp)))
    end)

    -- "hardcore mounds": where the mod thinks each mech meets the ground, and the mounds around it
    api.addCommand("mounds", function(out)
        out(summary())
        local mgr = getManager()
        if not mgr then out("no crop manager in this map"); return end
        for _, mech in ipairs(mechs()) do
            local p = footprint(mech)
            if p then
                local loc = vec(mech:K2_GetActorLocation())
                local function z(v) return v and string.format("%.0f", v) or "-" end
                out(string.format("%s (%s): footprint %s, centre (%.0f, %.0f, %.0f); heights: actor %s, capsule bottom "
                    .. "%s, lower foot %s, leg module bottom %s; %d actors move with it", shortName(mech), modeOf(mech),
                    describeFootprint(p), p.X, p.Y, p.Z, z(loc and loc.Z), z(loc and capsuleBottom(mech, loc)),
                    z(lowerFoot(mech)), z(moduleBottom(mech)), #movingWith(mech)))
                for _, f in ipairs(p.feet or {}) do
                    out(string.format("  %s foot at (%.0f, %.0f, %.0f), %.0f cm from the centre", f.side, f.X, f.Y, f.Z,
                        math.sqrt((f.X - p.X) ^ 2 + (f.Y - p.Y) ^ 2)))
                end
                local ids, seen, rows = {}, {}, {}
                overlap(mgr, p, DIAG_RADIUS, ids, seen)
                for _, id in ipairs(ids) do
                    local c = readCrop(mgr, id)
                    if c then
                        local d = math.sqrt((c.loc.X - p.X) ^ 2 + (c.loc.Y - p.Y) ^ 2)
                        local under = nil
                        if c.planted and not c.plot then
                            if underFootprint(p, p, c.loc) then under = "the mech" end
                            for _, f in ipairs(p.feet or {}) do
                                local fd = math.sqrt((c.loc.X - f.X) ^ 2 + (c.loc.Y - f.Y) ^ 2)
                                if not under and fd < FOOT_RADIUS and math.abs(c.loc.Z - f.Z) <= HEIGHT then
                                    under = "the " .. f.side .. " foot"
                                end
                            end
                        end
                        rows[#rows + 1] = { d = d, text = string.format("  mound %d: %s, %.0f cm away, %+.0f cm%s%s",
                            id, c.planted and c.plant or "empty", d, c.loc.Z - p.Z, c.plot and ", Mound Plot" or "",
                            under and ("  <- under " .. under) or "") }
                    end
                end
                table.sort(rows, function(a, b) return a.d < b.d end)
                if #rows == 0 then out("  no mounds within " .. DIAG_RADIUS .. " cm") end
                for i = 1, math.min(#rows, 10) do out(rows[i].text) end
            end
        end
    end)

    api.loop(CHECK_MS, "trampling check", function()
        local ok, err = pcall(tick)
        if not ok then fail(err) end
    end)
    log(string.format("crop trampling ready (radius %.0f cm, height %.0f cm, every %.0f ms)", RADIUS, HEIGHT, CHECK_MS))
end
