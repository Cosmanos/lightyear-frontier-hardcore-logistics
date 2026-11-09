-- Hardcore Logistics: local storage (feature "storage", a live feature: it switches on and off at once).
-- In the game, everything stored anywhere in a base can be used from anywhere in that base: crafting, building,
-- deliveries and tasks all draw on the whole base. With this on, a storage counts only within reach_cm of where it is
-- used (the station, the build spot, the delivery cannon). Anything stored further away has to be brought over first,
-- by mech, trailer or pipe.
--
-- How it works (checked against the 1.0 game exe):
--   * Whatever uses "the base inventory" asks UMultiInventoryHandler::GetReachableInventoryContainer(player, location).
--     It returns the player's mech inventory plus, when the location is inside a home area, every storage construct
--     in that area (MultiInventorySettings.StorageConstructClass, BP_StorageConstruct), nearest first. Outside home
--     areas it is the mech inventory alone. Crafting, quick craft, deliveries, task progress, NPC collections and chip
--     crafting call it from native code (15 call sites), which a Lua hook does not see.
--   * It leaves out every storage whose actor has the tag NoRemoteInventoryAccess (AActor::ActorHasTag). The game
--     gives that tag to its generators (BP_EnergyGeneratorPARENTConstruct), so their fuel is not base inventory.
--   * Every menu and station first asks for the base inventory from a Blueprint (GetReachableInventoryContainer or
--     ListenToReachableInventoryContainerAt), which a hook does see. On each such request this script gives that tag
--     to every storage further than reach_cm from the spot asked about, and takes it off the ones within reach, before
--     the game reads them; the native code that follows (the craft, the delivery) uses the same tags. Nothing runs
--     between requests. Distances are flat (X and Y). A storage already in reach leaves it only past reach_cm +
--     HYSTERESIS_CM. Storages are listed the way the game lists them: each home area's
--     GetConstructsOfClassInArea(BP_StorageConstruct). A storage whose class carries the tag (a generator) is never
--     touched. Switching the feature off takes the tag off every other storage.
--   * A tagged storage still opens and works normally, and pipes still move items in and out of it.
--   * The tags are written by setting the actor's Tags array from a Lua table. If UE4SS refuses that, they are copied
--     from an array that already holds the wanted tags: the storage class's own default, or a generator's.
--   * "hardcore storages" measures from the players, found through their player controllers. Co-op has not been
--     tried.

local TAG = "NoRemoteInventoryAccess"
local PC_CLASS = "BP_FarMechPlayerController_C"
local AREA_CLASSES = { "BP_HomeAreaComponent_C", "HomeAreaComponent" }   -- the second only if the first finds none
local DEFAULT_STORAGE_CLASS = "/Game/Blueprints/Constructs/BP_StorageConstruct.BP_StorageConstruct_C"
local GENERATOR_DEFAULT = "/Game/Blueprints/Constructs/BP_EnergyGeneratorPARENTConstruct."
    .. "Default__BP_EnergyGeneratorPARENTConstruct_C"
local HYSTERESIS_CM = 100        -- a storage in reach leaves it only this much past reach_cm
local DETAIL_LOGS = 8            -- the first tag changes are logged one by one
local LIST_ROWS = 15             -- "hardcore storages" lists this many storages, nearest first
local WRITE_FAILS_TO_STOP = 5    -- this many failed writes before any succeeded: stop trying for the session
-- Cost per check (these checks run inside a game frame; 0.11.0 stuttered every half second): players and home areas
-- are looked up through the whole object table (FindAllOf) only every REFRESH_TICKS checks, and found again by their
-- paths in between (StaticFindObject, a quick lookup); only the paths are kept between checks. A storage's name,
-- class, place and tags are read every CACHE_TICKS checks and remembered in between, keyed by its address; the mod
-- keeps the remembered tags up to date with what it writes. The storages themselves are listed every check.
local REFRESH_TICKS = 10
local CACHE_TICKS = 30

return function(api)
    local log = api.log
    local cfg = api.storage or {}
    local REACH = tonumber(cfg.reach_cm) or 1500
    local CHECK_MS = math.max(50, tonumber(cfg.check_ms) or 1000)
    local STORAGE_CLASS = (type(cfg.storage_class) == "string" and cfg.storage_class ~= "") and cfg.storage_class
        or DEFAULT_STORAGE_CLASS
    -- the Logistics Hub buildings (tools/build_buildings.py): a base holding any of them keeps every storage in its
    -- base inventory. HUBS: {row, class, name} per building. Their unlock in older worlds is unlocks.lua's job; they
    -- show in the build menu only in worlds loaded with hubCfg.feature on (main.lua applies those table changes).
    local hubCfg = api.hub or {}
    local HUBS = {}
    for _, h in ipairs(hubCfg.hubs or {}) do
        if type(h.row) == "string" and h.row ~= "" and type(h.class) == "string" and h.class ~= "" then
            HUBS[#HUBS + 1] = { row = h.row, class = h.class, energy = tonumber(h.energy) or 0,
                                name = type(h.display_name) == "string" and h.display_name or h.row }
        end
    end
    local HUB_NAME = HUBS[1] and HUBS[1].name or "Logistics Hub"
    -- Energy: the game's Energy Meter is one pool for the world, BP_FarMechGameState.EnergyStatus (a Blueprint struct:
    -- its members keep their GUID suffixes). A hub with an energy cost (its DT_EnergyValues row, so the meter counts
    -- it) links its base only while the grid is Energized: available minus used at 0 or above. Below 0 the game calls
    -- the grid Overloaded. When the meter cannot be read, hubs keep working (and "hardcore hub" says why).
    local ENERGY_AVAILABLE = "AvailableEnergy_2_C5BC05CA40C1AA7BF131B098C2D8D79F"
    local ENERGY_USED = "UsedEnergy_4_35D438EE42AEF8A0E3B7AFA935BF8C81"

    local stats = { added = 0, removed = 0, errors = 0, storages = 0, areas = 0, inReach = 0,
                    outOfReach = 0, generators = 0, unplaced = 0, writeOk = 0, writeFails = 0,
                    hubs = 0, linkedAreas = 0, linkedStorages = 0, unpowered = 0, power = nil }
    local energyError = nil       -- why the Energy Meter could not be read, when it could not
    local lastEnergized = nil     -- the grid state last seen, to log when it changes
    local wasActive = false
    local paths = { pcs = {}, areas = {} }                 -- object paths found by the last full lookup
    local lastFound = { pcs = -math.huge, areas = -math.huge }
    local cache = {}              -- storage address -> {name, class, generator, loc, tags, tagged, read, seen}
    local vanillaByClass = {}     -- class full name -> true when the class default already carries the tag
    local writeWay = nil          -- how tags were last written: "a Lua table" or "copied from <object>"
    local broken = false          -- tags could not be written at all: stop trying
    local detailLeft = DETAIL_LOGS
    local errorLeft = 20
    local classMissingLogged = false
    local tickCount = 0

    -- ------------------------------------------------------------------ small helpers

    local function valid(o)
        if o == nil then return false end
        local ok, v = pcall(function() return o:IsValid() end)
        return ok and v == true
    end

    -- an object, or an object wrapped the way UE4SS hands back array elements (:get())
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

    local function fullName(o)
        local ok, s = pcall(function() return o:GetFullName() end)
        return ok and tostring(s) or "?"
    end

    local function shortName(o)
        local ok, s = pcall(function() return o:GetFName():ToString() end)
        return ok and tostring(s) or "?"
    end

    local function className(o)
        local ok, s = pcall(function() return o:GetClass():GetFName():ToString() end)
        return ok and tostring(s) or "?"
    end

    local function fail(err)
        stats.errors = stats.errors + 1
        if errorLeft > 0 or stats.errors % 100 == 0 then
            errorLeft = errorLeft - 1
            log("local storage: " .. tostring(err))
        end
    end

    local function flatDistance(a, b)
        local dx, dy = a.X - b.X, a.Y - b.Y
        return math.sqrt(dx * dx + dy * dy)
    end

    -- ------------------------------------------------------------------ tags

    local function nameText(n)
        if type(n) == "string" then return n end
        local ok, s = pcall(function() return n:ToString() end)
        if ok and s ~= nil then return tostring(s) end
        ok, s = pcall(function() return n:get():ToString() end)
        if ok and s ~= nil then return tostring(s) end
        return tostring(n)
    end

    -- an object's tags, as plain strings
    local function tagsOf(o)
        local list = {}
        local tags = nil
        pcall(function() tags = o.Tags end)
        local ok, err = pcall(each, tags, function(n) list[#list + 1] = nameText(n) end)
        if not ok then fail("could not read the tags of " .. shortName(o) .. ": " .. tostring(err)) end
        return list
    end

    local function has(list, s)
        for _, v in ipairs(list) do if v == s then return true end end
        return false
    end

    local function same(a, b)
        if #a ~= #b then return false end
        for i = 1, #a do if a[i] ~= b[i] then return false end end
        return true
    end

    -- true when the storage's class already gives it the tag (the game's generators): never touched
    local function classHasTag(s)
        local cls = nil
        pcall(function() cls = s:GetClass() end)
        if not valid(cls) then return false end
        local key = fullName(cls)
        if vanillaByClass[key] == nil then
            local cdo = nil
            pcall(function() cdo = cls:GetCDO() end)
            vanillaByClass[key] = valid(cdo) and has(tagsOf(cdo), TAG) or false
        end
        return vanillaByClass[key]
    end

    -- objects whose Tags array holds exactly `want`, to copy from when a Lua table cannot be written
    local function templates(s, want)
        local out = {}
        local cdo = nil
        pcall(function() cdo = s:GetClass():GetCDO() end)
        if valid(cdo) and same(tagsOf(cdo), want) then out[#out + 1] = cdo end
        local ok, gen = pcall(StaticFindObject, GENERATOR_DEFAULT)
        if ok and valid(gen) and same(tagsOf(gen), want) then out[#out + 1] = gen end
        return out
    end

    -- set a storage's tags to `want` (a list of strings); true when they read back as wanted
    local function writeTags(s, want)
        local list = {}
        for i, t in ipairs(want) do list[i] = api.makeName(t) end
        local ok, err = pcall(function() s.Tags = list end)
        if ok and same(tagsOf(s), want) then
            writeWay = "a Lua table"
            return true
        end
        if ok then err = "they read back as {" .. table.concat(tagsOf(s), ", ") .. "}" end
        for _, src in ipairs(templates(s, want)) do
            local okCopy, copyErr = pcall(function() s.Tags = src.Tags end)
            if okCopy and same(tagsOf(s), want) then
                writeWay = "copied from " .. shortName(src)
                return true
            end
            if not okCopy then err = tostring(err) .. "; copying from " .. shortName(src) .. ": " .. tostring(copyErr) end
        end
        fail(string.format("could not set the tags of %s to {%s}: %s", shortName(s), table.concat(want, ", "),
            tostring(err)))
        return false
    end

    -- ------------------------------------------------------------------ the game's objects

    -- "Class /Game/Path.Object:Sub" -> "/Game/Path.Object:Sub", what StaticFindObject takes
    local function pathOf(o)
        return fullName(o):match("^%S+ (.+)$")
    end

    local function addressOf(o)
        local ok, a = pcall(function() return o:GetAddress() end)
        return ok and a or nil
    end

    -- Objects of `classes` that `keep` accepts. The whole object table is searched (FindAllOf) only every
    -- REFRESH_TICKS checks (every 3 while none was found, or when `force`); in between they are found again by the
    -- paths that search gave. `firstOnly`: try the next class only when the first finds none.
    local function findCached(kind, classes, keep, force, firstOnly)
        local due = #paths[kind] == 0 and 3 or REFRESH_TICKS
        if force or tickCount - lastFound[kind] >= due then
            local list, seen, ps = {}, {}, {}
            for _, cls in ipairs(classes) do
                if firstOnly and #list > 0 then break end
                local ok, found = pcall(FindAllOf, cls)
                if ok and type(found) == "table" then
                    for _, o in ipairs(found) do
                        local p = valid(o) and pathOf(o) or nil
                        if p and not seen[p] and keep(o, p) then
                            seen[p] = true
                            list[#list + 1] = o
                            ps[#ps + 1] = p
                        end
                    end
                end
            end
            paths[kind], lastFound[kind] = ps, tickCount
            return list
        end
        local list = {}
        for _, p in ipairs(paths[kind]) do
            local ok, o = pcall(StaticFindObject, p)
            if ok and valid(o) then list[#list + 1] = o end
        end
        if #list < #paths[kind] then lastFound[kind] = -math.huge end   -- one is gone: search again next check
        return list
    end

    -- where each player is: {loc, who}, from each player controller's pawn (the mech, or the pilot on foot)
    local function playerSpots(force)
        local spots = {}
        local pcs = findCached("pcs", { PC_CLASS }, function(_, p) return not p:find("Default__", 1, true) end, force)
        for _, pc in ipairs(pcs) do
            local pawn = nil
            pcall(function() pawn = pc.Pawn end)
            if not valid(pawn) then pcall(function() pawn = pc:K2_GetPawn() end) end
            if valid(pawn) then
                local loc = nil
                pcall(function() loc = vec(pawn:K2_GetActorLocation()) end)
                if loc then spots[#spots + 1] = { loc = loc, who = shortName(pawn) } end
            end
        end
        return spots
    end

    -- the home areas placed in the world: one per base. Templates inside Blueprint classes are left out (their names
    -- are not in a level), since the game never asks them for storages.
    local function homeAreas(force)
        return findCached("areas", AREA_CLASSES, function(_, p)
            return p:find("/Game/Levels/", 1, true) ~= nil and not p:find("Default__", 1, true)
        end, force, true)
    end

    local function storageClass()
        local ok, cls = pcall(StaticFindObject, STORAGE_CLASS)
        if ok and valid(cls) then return cls end
        return nil
    end

    -- the hub classes that are loaded (a placed hub loads its class; none while no hub is placed): {hub, cls}
    local function hubClasses()
        local out = {}
        for _, h in ipairs(HUBS) do
            local ok, cls = pcall(StaticFindObject, h.class)
            if ok and valid(cls) then out[#out + 1] = { hub = h, cls = cls } end
        end
        return out
    end

    -- the Energy Meter: {available, used, net, energized}, or nil (energyError says why). The game state comes from
    -- a player controller found by path (no object-table walk).
    local function energyState()
        local pcs = findCached("pcs", { PC_CLASS }, function(_, p) return not p:find("Default__", 1, true) end)
        local pc = pcs[1]
        if not pc then energyError = "no player controller"; return nil end
        local ok, gs = pcall(function()
            return StaticFindObject("/Script/Engine.Default__GameplayStatics"):GetGameState(pc)
        end)
        if not ok or not valid(gs) then energyError = "no game state"; return nil end
        local okS, a, u = pcall(function()
            local st = gs.EnergyStatus
            return num(st[ENERGY_AVAILABLE]), num(st[ENERGY_USED])
        end)
        if not okS then energyError = "EnergyStatus unreadable: " .. tostring(a); return nil end
        if a == nil or u == nil then energyError = "EnergyStatus has no available/used members"; return nil end
        energyError = nil
        local s = { available = a, used = u, net = a - u, energized = a - u >= 0 }
        if lastEnergized ~= nil and lastEnergized ~= s.energized then
            log(string.format("energy: the grid is %s (available %d, used %d); %s with an energy cost %s",
                s.energized and "Energized" or "Overloaded", a, u, HUB_NAME,
                s.energized and "link their bases again" or "link nothing until it is back at 0 or above"))
        end
        lastEnergized = s.energized
        return s
    end

    -- {area index -> true} for the areas holding a working Logistics Hub, the placed hubs' names, the Energy Meter
    -- (read only when a placed hub has an energy cost) and how many hubs are off for lack of energy
    local function hubAreas(areas)
        local linked, hubs, power, readPower, unpowered = {}, {}, nil, false, 0
        for _, hc in ipairs(hubClasses()) do
            local needs = (hc.hub.energy or 0) > 0
            for i, area in ipairs(areas) do
                local ok, found = pcall(function() return area:GetConstructsOfClassInArea(hc.cls) end)
                if ok then
                    each(found, function(v)
                        local h = asObject(v)
                        if h then
                            if needs and not readPower then power, readPower = energyState(), true end
                            local works = not needs or power == nil or power.energized
                            if works then linked[i] = true else unpowered = unpowered + 1 end
                            hubs[fullName(h)] = shortName(h) .. (works and "" or " (no energy)")
                        end
                    end)
                end
            end
        end
        return linked, hubs, power, unpowered
    end

    -- every storage in a home area, each once: {obj, cache, name, class, generator, tags, tagged, loc, linked}.
    -- linked: one of its areas holds a Logistics Hub. `fresh`: read every storage now instead of what is remembered.
    local function storageRows(areas, cls, linkedAreas, fresh)
        local rows, seen = {}, {}
        for i, area in ipairs(areas) do
            local ok, found = pcall(function() return area:GetConstructsOfClassInArea(cls) end)
            if ok then
                each(found, function(v)
                    local s = asObject(v)
                    if s then
                        local key = addressOf(s) or fullName(s)
                        if seen[key] then
                            seen[key].linked = seen[key].linked or linkedAreas[i] == true
                        else
                            local c = cache[key]
                            if fresh or c == nil or tickCount - c.read >= CACHE_TICKS then
                                c = { name = shortName(s), class = className(s), generator = classHasTag(s),
                                      read = tickCount }
                                c.tags = tagsOf(s)
                                c.tagged = has(c.tags, TAG)
                                pcall(function() c.loc = vec(s:K2_GetActorLocation()) end)
                                cache[key] = c
                            end
                            c.seen = tickCount
                            local r = { obj = s, cache = c, name = c.name, class = c.class, generator = c.generator,
                                        tags = c.tags, tagged = c.tagged, loc = c.loc, linked = linkedAreas[i] == true }
                            rows[#rows + 1] = r
                            seen[key] = r
                        end
                    end
                end)
            else
                fail("GetConstructsOfClassInArea failed: " .. tostring(found))
            end
        end
        return rows
    end

    -- forget storages not listed for a while (demolished)
    local function pruneCache()
        for key, c in pairs(cache) do
            if tickCount - (c.seen or 0) > REFRESH_TICKS then cache[key] = nil end
        end
    end

    -- the storages with the nearest player's distance: {rows, areas, linked (areas with a hub), hubs (names)};
    -- nil when the storage class is not loaded. `fresh`: search for areas and read every storage now.
    local function survey(spots, fresh)
        local cls = storageClass()
        if not cls then return nil end
        local areas = homeAreas(fresh)
        local linked, hubs, power, unpowered = hubAreas(areas)
        local rows = storageRows(areas, cls, linked, fresh)
        for _, r in ipairs(rows) do
            if r.loc then
                for _, p in ipairs(spots) do
                    local d = flatDistance(p.loc, r.loc)
                    if r.dist == nil or d < r.dist then r.dist, r.who = d, p.who end
                end
            end
        end
        local nlinked, nhubs = 0, 0
        for _ in pairs(linked) do nlinked = nlinked + 1 end
        for _ in pairs(hubs) do nhubs = nhubs + 1 end
        return { rows = rows, areas = #areas, linked = nlinked, hubs = nhubs, hubNames = hubs, power = power,
                 unpowered = unpowered }
    end

    local function powerText(p, unpowered)
        if p == nil then return "" end
        return string.format("; Energy Meter %+d (%s)%s", p.net, p.energized and "Energized" or "Overloaded",
            (unpowered or 0) > 0 and string.format(", %d hubs off for lack of energy", unpowered) or "")
    end

    -- ------------------------------------------------------------------ the rule

    local function describeChange(r, on)
        if on then
            return string.format("%s (%s) is %.1f m from %s: left out of the base inventory", r.name, r.class,
                (r.dist or 0) / 100, r.who or "where the game asked")
        end
        if r.dist then
            return string.format("%s (%s) is %.1f m from %s: back in the base inventory", r.name, r.class, r.dist / 100,
                r.who or "a player")
        end
        return string.format("%s (%s): back in the base inventory", r.name, r.class)
    end

    local function setTag(r, on)
        local want = {}
        for _, t in ipairs(r.tags) do
            if t ~= TAG then want[#want + 1] = t end
        end
        if on then want[#want + 1] = TAG end
        if not writeTags(r.obj, want) then
            stats.writeFails = stats.writeFails + 1
            if stats.writeOk == 0 and stats.writeFails >= WRITE_FAILS_TO_STOP and not broken then
                broken = true
                log("local storage: the storages' tags cannot be written in this UE4SS build (see the errors above), "
                    .. "so local storage is not working; every storage stays part of the base inventory")
            end
            return false
        end
        stats.writeOk = stats.writeOk + 1
        r.tags, r.tagged = want, on
        if r.cache then r.cache.tags, r.cache.tagged = want, on end
        if on then stats.added = stats.added + 1 else stats.removed = stats.removed + 1 end
        if detailLeft > 0 then
            detailLeft = detailLeft - 1
            log("local storage: " .. describeChange(r, on))
        end
        return true
    end

    -- in reach: in a base with a Logistics Hub, within reach_cm of a player, or within reach_cm + HYSTERESIS_CM while
    -- it is already in. A storage that cannot be placed stays in. A reach of 0 leaves every other storage out, as
    -- outside a base.
    local function inReach(r)
        if r.linked then return true end
        if r.loc == nil or r.dist == nil then return true end
        if REACH <= 0 then return false end
        if r.tagged then return r.dist <= REACH end
        return r.dist <= REACH + HYSTERESIS_CM
    end

    -- the rule, measured from `points` ({loc, who}): tag the storages out of reach, untag the ones in reach
    local function applyRule(points)
        local s = survey(points)
        if s == nil then
            if not classMissingLogged then
                classMissingLogged = true
                log("local storage: the storage class " .. STORAGE_CLASS .. " is not loaded yet")
            end
            return
        end
        local near, far, generators, unplaced, linked = 0, 0, 0, 0, 0
        for _, r in ipairs(s.rows) do
            if r.generator then
                generators = generators + 1
            else
                local keep = inReach(r)
                if r.loc == nil then unplaced = unplaced + 1 end
                if r.linked then linked = linked + 1 end
                if keep then near = near + 1 else far = far + 1 end
                if keep and r.tagged then
                    setTag(r, false)
                elseif not keep and not r.tagged then
                    setTag(r, true)
                end
            end
        end
        stats.areas, stats.hubs, stats.linkedAreas = s.areas, s.hubs, s.linked
        stats.power, stats.unpowered = s.power, s.unpowered
        stats.storages, stats.inReach, stats.outOfReach = #s.rows, near, far
        stats.generators, stats.unplaced, stats.linkedStorages = generators, unplaced, linked
    end

    -- ------------------------------------------------------------------ when the game asks for the base inventory

    -- Every menu and station that uses the base inventory asks UMultiInventoryHandler for it from a Blueprint first
    -- (46 Blueprints call GetReachableInventoryContainer: crafting and conversion menus, the build menu and holograms,
    -- deliveries, upgrades, storage menus, NPC collections; 12 call ListenToReachableInventoryContainerAt). A hook on
    -- both applies the rule just before the game reads the storages, measured from the spot it asks about (the
    -- station, the build spot, the cannon). Nothing runs in between: 0.9.0-0.11.1 checked every 500-1000 ms, inside
    -- game frames, and the game stuttered. The native callers (crafting, deliveries) run after their menu has asked.
    -- The same spot asking again is re-checked at most every QUERY_REFRESH_S seconds, so a menu that asks every frame
    -- costs almost nothing; a spot QUERY_MOVE_CM away is checked at once.
    local QUERY_FUNCTIONS = { "/Script/FarMech.MultiInventoryHandler:GetReachableInventoryContainer",
                              "/Script/FarMech.MultiInventoryHandler:ListenToReachableInventoryContainerAt" }
    local QUERY_MOVE_CM, QUERY_REFRESH_S = 200, 3
    local queries = { seen = 0, applied = 0, lastLoc = nil, lastTime = -math.huge, hooks = {} }

    local function onQuery(sourceLocation)
        if broken or not api.isActive("storage") then return end
        local loc = vec(sourceLocation)
        if not loc then return end
        queries.seen = queries.seen + 1
        local now = os.clock()
        if queries.lastLoc and flatDistance(queries.lastLoc, loc) < QUERY_MOVE_CM
            and now - queries.lastTime < QUERY_REFRESH_S then
            return
        end
        queries.lastLoc, queries.lastTime = loc, now
        queries.applied = queries.applied + 1
        tickCount = tickCount + 1               -- the remembered storage details age by updates
        applyRule({ { loc = loc, who = "the spot the game asked about" } })
        if api.recordTiming then api.recordTiming("local storage update (on an inventory request)",
            (os.clock() - now) * 1000) end
    end

    for _, fn in ipairs(QUERY_FUNCTIONS) do
        local ok, err = pcall(RegisterHook, fn, function(_context, _who, sourceLocation)
            local okQ, errQ = pcall(onQuery, sourceLocation)
            if not okQ then fail(errQ) end
        end)
        queries.hooks[#queries.hooks + 1] = (fn:match(":(.+)$") or fn) .. (ok and "" or (" (no hook: " .. tostring(err) .. ")"))
        if not ok then log("local storage: could not hook " .. fn .. ": " .. tostring(err)) end
    end

    -- The loop only notices the feature being switched off (every storage back in the base inventory), and forgets
    -- storages no longer listed. It touches no game object while the feature stays on or off.
    local function tick()
        local active = api.isActive("storage") and not broken
        if active then
            if not wasActive then
                wasActive = true
                log(string.format("local storage on: a storage counts only within %.1f m of where a menu or station asks "
                    .. "for the base inventory, except in a base with a %s", REACH / 100, HUB_NAME))
            end
            if queries.applied > 0 and queries.applied % REFRESH_TICKS == 0 then pruneCache() end
            return
        end
        if not wasActive then return end
        wasActive = false
        local removed = 0
        local s = survey({}, true)
        for _, r in ipairs(s and s.rows or {}) do
            if r.tagged and not r.generator and setTag(r, false) then removed = removed + 1 end
        end
        queries.lastLoc = nil
        log(string.format("local storage off: every storage is part of the base inventory again (%d tags taken off)",
            removed))
    end

    -- ------------------------------------------------------------------ readout and console

    local function summary()
        local last = queries.lastLoc and string.format("last at (%.0f, %.0f), %.0f s ago", queries.lastLoc.X,
            queries.lastLoc.Y, os.clock() - queries.lastTime) or "none yet"
        return string.format("local storage %s for this world (reach %.1f m): %d inventory requests from menus and "
            .. "stations, %d checked (%s); %d storages in %d home areas, %d in reach (%d through a %s; %d hubs in %d "
            .. "bases%s), %d out of reach, %d generators left to the game; %d tags added, %d taken off, %d errors%s%s",
            api.isActive("storage") and "ON" or "off", REACH / 100, queries.seen, queries.applied, last, stats.storages,
            stats.areas, stats.inReach, stats.linkedStorages, HUB_NAME, stats.hubs, stats.linkedAreas,
            powerText(stats.power, stats.unpowered), stats.outOfReach,
            stats.generators, stats.added, stats.removed, stats.errors,
            writeWay and ("; tags written as " .. writeWay) or "", broken and "; STOPPED: tags cannot be written" or "")
    end

    api.addReport(function(out) out(summary()) end)

    -- "hardcore storages": every storage in a base, nearest first, and whether it counts as base inventory now
    api.addCommand("storages", function(out)
        out(summary())
        out("inventory requests come through: " .. table.concat(queries.hooks, ", ")
            .. ". The states below are from the last request; distances are from you.")
        local spots = playerSpots(true)
        for _, p in ipairs(spots) do
            out(string.format("player %s at (%.0f, %.0f, %.0f)", p.who, p.loc.X, p.loc.Y, p.loc.Z))
        end
        if #spots == 0 then out("no player found") end
        local s = survey(spots, true)
        if s == nil then
            out("the storage class " .. STORAGE_CLASS .. " is not loaded")
            return
        end
        local rows = s.rows
        table.sort(rows, function(a, b) return (a.dist or math.huge) < (b.dist or math.huge) end)
        out(string.format("%d storages in %d home areas (%d with a %s), nearest first:", #rows, s.areas, s.linked,
            HUB_NAME))
        for i = 1, math.min(#rows, LIST_ROWS) do
            local r = rows[i]
            local state
            if r.generator then
                state = "a generator: the game keeps it out of the base inventory"
            elseif r.tagged then
                state = "out of the base inventory"
            elseif r.linked then
                state = "in the base inventory (its base has a " .. HUB_NAME .. ")"
            else
                state = "in the base inventory"
            end
            local extra = {}
            for _, t in ipairs(r.tags) do
                if t ~= TAG then extra[#extra + 1] = t end
            end
            out(string.format("  %s (%s): %s, %s%s", r.name, r.class,
                r.dist and string.format("%.1f m", r.dist / 100) or "? m", state,
                #extra > 0 and (" (other tags: " .. table.concat(extra, ", ") .. ")") or ""))
        end
        if #rows > LIST_ROWS then out(string.format("  ... and %d more", #rows - LIST_ROWS)) end
    end)

    -- "hardcore hub": each Logistics Hub building's unlock and build-menu row, and the hubs placed; "hardcore hub
    -- unlock" unlocks them now, whatever the milestones (to try them out). Unlocking is unlocks.lua's.
    api.addCommand("hub", function(out, arg)
        if #HUBS == 0 then out("no Logistics Hub is set up in mod_config.json"); return end
        local hubRows = {}
        for _, h in ipairs(HUBS) do hubRows[#hubRows + 1] = h.row end
        if arg == "unlock" then
            if not api.unlockConstructs then out("the building unlock script (unlocks.lua) is not loaded"); return end
            out("Logistics Hubs: " .. (api.unlockConstructs(hubRows, true)))
            return
        end
        local st = api.constructStatus and api.constructStatus() or {}
        local unlocked, rows = st.unlocked, st.rows
        local loaded = {}
        for _, hc in ipairs(hubClasses()) do loaded[hc.hub.row] = true end
        out(string.format("Logistics Hubs: %s milestones done (they unlock at %s)", tostring(st.milestones),
            tostring(hubCfg.milestone)))
        local feature = type(hubCfg.feature) == "string" and hubCfg.feature or nil
        if feature and api.isLoadedWith then
            out(api.isLoadedWith(feature)
                and string.format("build menu: shown in this world (it loaded with %s on)", feature)
                or string.format("build menu: hidden in this world, and no milestone reward (it loaded with %s off; "
                    .. "placed hubs stay)", feature))
        end
        local missing = false
        local needsEnergy = false
        for _, h in ipairs(HUBS) do
            local u = unlocked and unlocked[h.row]
            if unlocked and not u then missing = true end
            if h.energy > 0 then needsEnergy = true end
            out(string.format("  %s (row %s): %s; build-menu row %s; class %s%s", h.name, h.row,
                unlocked == nil and "unlock unknown" or (u and "unlocked" or "not unlocked"),
                rows == nil and "unknown" or (rows[h.row] and "in DT_Constructs"
                    or "MISSING from DT_Constructs (the hubs' container is not mounted)"),
                loaded[h.row] and "loaded" or "not loaded (none placed yet)",
                h.energy > 0 and string.format("; uses %d energy", h.energy) or ""))
        end
        if needsEnergy then
            local p = energyState()
            if p then
                out(string.format("Energy Meter: available %d, used %d, so %+d: %s", p.available, p.used, p.net,
                    p.energized and "Energized, hubs with an energy cost work"
                    or "Overloaded, hubs with an energy cost link nothing until it is back at 0 or above"))
            else
                out("Energy Meter: could not read it (" .. tostring(energyError) .. "); hubs work regardless")
            end
        end
        local s = survey(playerSpots(true), true)
        if s then
            local placed = {}
            for _, n in pairs(s.hubNames) do placed[#placed + 1] = n end
            table.sort(placed)
            out(string.format("%d hubs placed, in %d of %d bases%s", s.hubs, s.linked, s.areas,
                #placed > 0 and (": " .. table.concat(placed, ", ")) or ""))
        end
        if missing then out("type  hardcore hub unlock  to unlock them now") end
    end)

    -- a new map has new storages (untagged: saves do not keep tags): start over
    local function forgetWorld()
        wasActive, vanillaByClass = false, {}
        lastEnergized, energyError, stats.power, stats.unpowered = nil, nil, nil, 0
        cache, paths = {}, { pcs = {}, areas = {} }
        lastFound = { pcs = -math.huge, areas = -math.huge }
        queries.lastLoc, queries.lastTime = nil, -math.huge
        stats.storages, stats.areas, stats.inReach, stats.outOfReach = 0, 0, 0, 0
        stats.generators, stats.unplaced = 0, 0
    end
    api.onMapLoaded(forgetWorld)
    if api.onMapLeaving then api.onMapLeaving(forgetWorld) end

    api.loop(CHECK_MS, "local storage check", function()
        local ok, err = pcall(tick)
        if not ok then fail(err) end
    end)
    log(string.format("local storage ready (reach %.1f m, every %.0f ms)", REACH / 100, CHECK_MS))
end
