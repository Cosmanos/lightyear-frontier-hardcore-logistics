-- Hardcore Logistics: Drone Stations, wireless pipes between bases (0.15.0).
--
-- Two buildings (tools/build_buildings.py, copies of Storage Box II): a Drone Input Station keeps only its input
-- port, a Drone Output Station only its output port. Both are storages, so the game's pipes do the local work: pipes
-- fill an input station (its Resource Filter picks what they bring) and take from an output station (whatever the
-- machines and storages behind it ask for). This script carries the items in between.
--
-- Pairing is by paint colour: a construct's AuthPaintColorName (BP_Construct), which the game saves with it.
-- Unpainted stations keep their default colour, Gray, so Gray is a channel like any other and the first pair works
-- without paint. Every input station of a colour sends to every output station of that colour.
--
-- One drone per input station. When the station holds items and an output station of its colour has room, the drone
-- flies to the one with the most free room (nearest on a tie): distance / speed seconds, at least min_trip_s / 2 each
-- way. On arrival it unloads up to load_kg, then flies back the same time. Items move only on arrival: they are added
-- to the output first, then taken from the input in the exact number the output took (counted with
-- GetNumItemsWithName), and taken back from the output if the input could not give them all. Nothing is lost or
-- doubled, also across a save: drones are not saved, and after a load every drone starts at home. Liquids are never
-- carried. Only the host moves items (the inventory calls are Server_ functions).
--
-- Energy (0.15.3, the user's balance): each station costs energy on the game's Energy Meter, its DT_EnergyValues row
-- (the container adds one per station). The template (Storage Box II) has no energy handler, so this script gives
-- each station the game's own, BPC_EnergyHandler, with AActor::AddComponentByClass when it first finds the station
-- (after every world load, as handlers added this way are not saved). The handler's BeginPlay reads its cost from that
-- row by construct name (scaled by the playstyle) and registers with the game state; its EndPlay unregisters when the
-- station is demolished. Drones only take off while the grid is Energized (available minus used at 0 or above), as
-- the Logistics Hub only links then; a drone already flying finishes its trip. When the meter cannot be read, drones
-- fly (and the readout says why).
--
-- The setting (0.15.7, the user's wish): the stations belong to a feature of their own, cfg.feature ('drones', the
-- settings row "Hardcore Logistics: Delivery Drone Stations"), apart from local storage. The container ships both
-- rows hidden and outside their milestone's rewards; main.lua shows them in worlds that load with the feature, as it
-- does the Logistics Hub with local storage (the build menu follows on the next load after a switch). This script
-- follows the setting at once: while it is off no drone flies and no station gets an energy handler, and when it is
-- switched off the handlers come back off (their EndPlay unregisters them, as when a station is demolished), so placed
-- stations are plain storage. A drone in the air then is dropped with its trip: items only move on arrival, so
-- nothing is lost.
--
-- Cost: the stations are found through the whole object table (FindAllOf) every rescan_s seconds and by their paths in
-- between (StaticFindObject); a check reads each station's colour, place and inventory weight; a trip calls a few
-- inventory functions. `hardcore timing` shows the loop's cost.
--
-- Console:  hardcore drones   the setting, the stations by colour, each drone's state, and what the drones carried

local STATICS = "/Script/Engine.Default__GameplayStatics"
local ITEM_SOURCE = 0            -- EItemSource::Unknown, for Server_AddItemStack
local DETAIL_LOGS = 6            -- the first trips are logged one by one
local LIST_ROWS = 12             -- "hardcore drones" lists this many stations per colour
local EMPTY_SEARCH_S = 5         -- while no station was found, search this often (rescan_s otherwise)
local ENERGY_AVAILABLE = "AvailableEnergy_2_C5BC05CA40C1AA7BF131B098C2D8D79F"   -- BP_FarMechGameState.EnergyStatus
local ENERGY_USED = "UsedEnergy_4_35D438EE42AEF8A0E3B7AFA935BF8C81"
local IDENTITY = { Rotation = { X = 0, Y = 0, Z = 0, W = 1 }, Translation = { X = 0, Y = 0, Z = 0 },
                   Scale3D = { X = 1, Y = 1, Z = 1 } }

return function(api)
    local log, asText, makeName = api.log, api.asText, api.makeName
    local cfg = api.drones or {}
    local KINDS = {}             -- class short name -> {role, name}
    local CLASSES = {}
    for _, s in ipairs(cfg.stations or {}) do
        local short = type(s.class) == "string" and s.class:match("%.([^%.]+)$") or nil   -- /Game/P/BP_X.BP_X_C
        if short and (s.role == "input" or s.role == "output") then
            KINDS[short] = { role = s.role, name = type(s.name) == "string" and s.name or s.row,
                             energy = tonumber(s.energy) or 0 }
            CLASSES[#CLASSES + 1] = short
        end
    end
    if #CLASSES == 0 then return end
    local LOAD_G = math.max(1, tonumber(cfg.load_kg) or 100) * 1000
    local SPEED_CM = math.max(0.1, tonumber(cfg.speed_mps) or 20) * 100
    local MIN_LEG_S = math.max(0, tonumber(cfg.min_trip_s) or 2) / 2
    local CHECK_MS = math.max(100, tonumber(cfg.check_ms) or 1000)
    local RESCAN_S = math.max(1, tonumber(cfg.rescan_s) or 15)
    local HANDLER_CLASS = type(cfg.energy_handler_class) == "string" and cfg.energy_handler_class ~= ""
        and cfg.energy_handler_class or nil       -- the game's energy handler, added to each station (nil: no energy)
    local GRAMS = cfg.item_grams or {}
    local FEATURE = type(cfg.feature) == "string" and cfg.feature ~= "" and cfg.feature or nil   -- nil: always on
    local LABEL = FEATURE
    for _, f in ipairs(api.features or {}) do
        if f.id == FEATURE and type(f.label) == "string" then LABEL = f.label end
    end
    local LIQUID = {}
    for _, n in ipairs(cfg.liquids or {}) do LIQUID[n] = true end

    local paths = {}                 -- station paths from the last search
    local lastSearch = -math.huge    -- clock time of that search
    local clock = 0                  -- seconds this world has run checks (when the world time cannot be read)
    local drones = {}                -- input station path -> {phase, target, untilT, leg, dist}
    local totals = { trips = 0, grams = 0, items = {}, refused = 0, mismatches = 0, empty = 0 }
    local detail = 0
    local last = { inputs = 0, outputs = 0, client = false, power = nil, powerError = nil, grounded = 0 }
    local handled = {}               -- station path -> "found" | "added" | "failed": its energy handler, this world
    local handlers = { found = 0, added = 0, failed = 0, removed = 0, error = nil }
    local off = nil                  -- true while the feature is off in this world, false while on, nil: not seen yet

    local ensureHandler               -- defined below, used by survey()

    local function valid(o)
        if o == nil then return false end
        local ok, v = pcall(function() return o:IsValid() end)
        return ok and v == true
    end

    -- true while the loaded world runs with the stations' feature (live: a switch counts at once)
    local function enabled()
        return FEATURE == nil or api.isActive(FEATURE) == true
    end

    local function fullName(o)
        local ok, s = pcall(function() return o:GetFullName() end)
        return ok and tostring(s) or ""
    end

    -- read a field of a UE4SS struct or object, directly or through :get()
    local function field(o, name)
        local ok, v = pcall(function() return o[name] end)
        if ok and v ~= nil then return v end
        ok, v = pcall(function() return o:get()[name] end)
        if ok then return v end
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

    local function call(o, fname, ...)
        local args = { ... }
        local ok, v = pcall(function() return o[fname](o, table.unpack(args)) end)
        if ok then return v end
        return nil
    end

    local function worldTime(ctx)
        local ok, t = pcall(function() return StaticFindObject(STATICS):GetTimeSeconds(ctx) end)
        t = ok and num(t) or nil
        return t or clock
    end

    -- the stations: found through the object table every RESCAN_S seconds (EMPTY_SEARCH_S while there are none), by
    -- their paths in between; a missing one makes the next check search again
    local function findStations()
        if clock - lastSearch >= (#paths == 0 and EMPTY_SEARCH_S or RESCAN_S) then
            local list, ps, seen = {}, {}, {}
            for _, cls in ipairs(CLASSES) do
                local ok, found = pcall(FindAllOf, cls)
                if ok and type(found) == "table" then
                    for _, o in ipairs(found) do
                        local name = valid(o) and fullName(o) or ""
                        local p = name:match("^%S+ (.+)$")
                        if p and not seen[p] and not p:find("Default__", 1, true) then
                            seen[p] = true
                            list[#list + 1] = o
                            ps[#ps + 1] = p
                        end
                    end
                end
            end
            paths, lastSearch = ps, clock
            return list
        end
        local list = {}
        for _, p in ipairs(paths) do
            local ok, o = pcall(StaticFindObject, p)
            if ok and valid(o) then list[#list + 1] = o end
        end
        if #list < #paths then lastSearch = -math.huge end
        return list
    end

    local function colorOf(o)
        local c = asText(field(o, "AuthPaintColorName"))
        if c == nil or c == "" or c == "None" then c = asText(field(o, "DefaultPaintColorName")) end
        if c == nil or c == "" or c == "None" then c = "Gray" end
        return c
    end

    local function locationOf(o)
        local v = call(o, "K2_GetActorLocation")
        if v == nil then return nil end
        local x, y, z = num(field(v, "X")), num(field(v, "Y")), num(field(v, "Z"))
        if not (x and y and z) then return nil end
        return { x, y, z }
    end

    local function distance(a, b)
        if not a or not b then return 0 end
        local dx, dy, dz = a[1] - b[1], a[2] - b[2], a[3] - b[3]
        return math.sqrt(dx * dx + dy * dy + dz * dz)
    end

    local function weightOf(inv) return num(call(inv, "GetWeightGrams")) or 0 end
    local function freeOf(inv)
        local max = num(call(inv, "GetMaxWeightGrams"))
        if not max then return 0 end
        return math.max(0, max - weightOf(inv))
    end
    local function countOf(inv, fname) return num(call(inv, "GetNumItemsWithName", fname)) or 0 end

    -- the inventory's stacks as {name, quality, size, maxSize}; the list comes back as a Lua table or a TArray, and its
    -- elements as structs read directly or through :get()
    local function stacksOf(inv)
        local out = {}
        local arr = call(inv, "GetAllItemStacks")
        if arr == nil then return out end
        local function add(e)
            local name = asText(field(e, "Name"))
            local size = num(field(e, "Size")) or 0
            if name and name ~= "None" and size > 0 then
                out[#out + 1] = { name = name, quality = num(field(e, "Quality")) or 0, size = size,
                                  maxSize = num(field(e, "MaxSize")) or size }
            end
        end
        if type(arr) == "table" then
            for _, e in ipairs(arr) do add(e) end
        else
            pcall(function() arr:ForEach(function(_, e) add(e:get()) end) end)
        end
        return out
    end

    local function carriable(stacks)
        for _, s in ipairs(stacks) do
            if not LIQUID[s.name] then return true end
        end
        return false
    end

    local function stack(fname, s, size)
        return { Name = fname, Quality = s.quality, Size = size, MaxSize = s.maxSize }
    end

    -- unload at dst what src holds, up to LOAD_G and dst's free weight: add first, then take what dst took
    local function deliver(src, dst)
        local budget = math.min(LOAD_G, freeOf(dst.inv))
        local moved, grams = {}, 0
        if budget <= 0 then return moved, grams end
        for _, s in ipairs(stacksOf(src.inv)) do
            if budget <= 0 then break end
            if not LIQUID[s.name] then
                local g = math.max(1, tonumber(GRAMS[s.name]) or 1)
                local n = math.min(s.size, math.floor(budget / g))
                if n > 0 then
                    local fname = makeName(s.name)
                    local before, w0 = countOf(dst.inv, fname), weightOf(dst.inv)
                    pcall(function() dst.inv:Server_AddItemStack(stack(fname, s, n), ITEM_SOURCE) end)
                    local added = countOf(dst.inv, fname) - before
                    if added > 0 then
                        local have = countOf(src.inv, fname)
                        pcall(function() src.inv:Server_RemoveItemStack(stack(fname, s, added)) end)
                        local taken = have - countOf(src.inv, fname)
                        if taken < added then        -- the input could not give them all: take the rest back
                            pcall(function() dst.inv:Server_RemoveItemStack(stack(fname, s, added - taken)) end)
                            totals.mismatches = totals.mismatches + 1
                            added = math.max(0, taken)
                        end
                        if added > 0 then
                            moved[s.name] = (moved[s.name] or 0) + added
                            local dw = weightOf(dst.inv) - w0
                            local used = dw > 0 and dw or added * g
                            budget, grams = budget - used, grams + used
                        end
                    else
                        totals.refused = totals.refused + 1      -- the output took none (no free slot, its filter)
                    end
                end
            end
        end
        return moved, grams
    end

    local function describeMoved(moved)
        local parts = {}
        for name, n in pairs(moved) do parts[#parts + 1] = string.format("%s %d", name, n) end
        table.sort(parts)
        return #parts > 0 and table.concat(parts, ", ") or "nothing"
    end

    -- give a station the game's energy handler unless it has one (once per station and world; a failure is not retried
    -- until the next world load, and the readout names it)
    ensureHandler = function(st)
        if not HANDLER_CLASS or handled[st.path] then return end
        local okC, cls = pcall(StaticFindObject, HANDLER_CLASS)
        if not okC or not valid(cls) then
            handlers.error = "the energy handler class is not loaded (" .. HANDLER_CLASS .. ")"
            return
        end
        local have = call(st.obj, "GetComponentByClass", cls)
        if valid(have) then
            handled[st.path] = "found"
            handlers.found = handlers.found + 1
            return
        end
        local ok, comp = pcall(function() return st.obj:AddComponentByClass(cls, false, IDENTITY, false) end)
        if ok and valid(comp) then
            handled[st.path] = "added"
            handlers.added = handlers.added + 1
            if handlers.added <= DETAIL_LOGS then
                log(string.format("drone stations: %s got its energy handler (%d energy before the playstyle)",
                    st.kind.name, st.kind.energy))
            end
        else
            handled[st.path] = "failed"
            handlers.failed = handlers.failed + 1
            handlers.error = "AddComponentByClass: " .. tostring(comp)
            log("drone stations: could not add the energy handler to " .. st.kind.name .. ": " .. tostring(comp))
        end
    end

    -- take the energy handlers back off every station (the feature is off in this world): destroying the component
    -- runs its EndPlay, which unregisters it from the game state, as when a station is demolished. Host only, like
    -- adding them. Returns how many came off; the stations get them again when the feature is back on.
    local function removeHandlers()
        handled = {}
        if not HANDLER_CLASS then return 0 end
        local okC, cls = pcall(StaticFindObject, HANDLER_CLASS)
        if not okC or not valid(cls) then return 0 end
        lastSearch = -math.huge                  -- a fresh search: every station placed so far
        local removed = 0
        for _, o in ipairs(findStations()) do
            if call(o, "HasAuthority") ~= false then
                local comp = call(o, "GetComponentByClass", cls)
                if valid(comp) and pcall(function() comp:K2_DestroyComponent(comp) end) then removed = removed + 1 end
            end
        end
        handlers.removed = handlers.removed + removed
        return removed
    end

    -- the Energy Meter: true (Energized), false (Overloaded) or nil (unreadable), plus available and used
    local function power(ctx)
        local ok, gs = pcall(function() return StaticFindObject(STATICS):GetGameState(ctx) end)
        if not ok or not valid(gs) then return nil, "no game state" end
        local okE, st = pcall(function() return gs.EnergyStatus end)
        if not okE or st == nil then return nil, "the game state has no EnergyStatus" end
        local okS, a, u = pcall(function() return num(st[ENERGY_AVAILABLE]), num(st[ENERGY_USED]) end)
        if not okS then return nil, "EnergyStatus unreadable: " .. tostring(a) end
        if a == nil or u == nil then return nil, "EnergyStatus has no available/used members" end
        return a - u >= 0, nil, a, u
    end

    -- read every station: {obj, path, kind, role, color, inv, loc}; nil when this machine is not the host
    local function survey()
        local list = findStations()
        local all, byPath = {}, {}
        for _, o in ipairs(list) do
            local name = fullName(o)
            local kind = KINDS[name:match("^(%S+)") or ""]
            local inv = field(o, "Input")
            if kind and inv ~= nil then
                if call(o, "HasAuthority") == false then
                    last.client = true
                    return nil
                end
                local st = { obj = o, path = name:match("^%S+ (.+)$"), kind = kind, role = kind.role, color = colorOf(o),
                             inv = inv, loc = locationOf(o) }
                if enabled() then ensureHandler(st) end
                all[#all + 1] = st
                byPath[st.path] = st
            end
        end
        last.client = false
        return all, byPath
    end

    local function tick()
        clock = clock + CHECK_MS / 1000
        if api.worldLoaded and not api.worldLoaded() then return end
        if not enabled() then
            if off ~= true then              -- once per world load, and at each switch off
                local switched = off == false
                off, drones = true, {}
                local removed = removeHandlers()
                last.inputs, last.outputs, last.power, last.powerError, last.grounded = 0, 0, nil, nil, 0
                log(string.format("drone stations: %s in this world (%s): no drones fly%s", switched and "switched off"
                    or "off", LABEL, removed > 0 and string.format(", %d energy handlers taken off", removed) or ""))
            end
            return
        end
        if off == true then
            log("drone stations: switched on in this world (" .. LABEL .. "); drones fly again")
            lastSearch = -math.huge          -- stations placed while it was off count at once
        end
        off = false
        local all, byPath = survey()
        if not all then return end
        local outputs, inputs = {}, {}
        for _, st in ipairs(all) do
            if st.role == "output" then
                outputs[st.color] = outputs[st.color] or {}
                table.insert(outputs[st.color], st)
            else
                inputs[#inputs + 1] = st
            end
        end
        last.inputs, last.outputs = #inputs, #all - #inputs
        if #inputs == 0 then drones = {}; return end
        local now = worldTime(all[1].obj)
        local energized = true
        if HANDLER_CLASS then
            local p, err, a, u = power(all[1].obj)
            if p ~= last.power and p ~= nil and last.power ~= nil then
                log(string.format("drone stations: the grid is %s (available %d, used %d); drones %s", p and "Energized"
                    or "Overloaded", a, u, p and "fly again" or "stay home until it is back at 0 or above"))
            end
            last.power, last.powerError, last.available, last.used = p, err, a, u
            energized = p ~= false
        end
        last.grounded = 0
        local alive = {}
        for _, src in ipairs(inputs) do
            alive[src.path] = true
            local d = drones[src.path]
            if d and d.phase == "outbound" and now >= d.untilT then
                local dst = byPath[d.target]
                if dst and dst.color == src.color then
                    local moved, grams = deliver(src, dst)
                    totals.trips = totals.trips + 1
                    totals.grams = totals.grams + grams
                    for name, n in pairs(moved) do totals.items[name] = (totals.items[name] or 0) + n end
                    if next(moved) == nil then totals.empty = totals.empty + 1 end
                    if detail < DETAIL_LOGS then
                        detail = detail + 1
                        log(string.format("drone (%s): %s to %s %.0f m away, %.1f kg: %s", src.color,
                            src.kind.name, dst.kind.name, d.dist / 100, grams / 1000, describeMoved(moved)))
                    end
                end
                d.phase, d.untilT = "returning", now + d.leg
            elseif d and d.phase == "returning" and now >= d.untilT then
                drones[src.path], d = nil, nil
            end
            if d == nil then
                -- at home: take off when there is something to carry and an output of this colour has room
                local best, bestFree, bestDist = nil, 0, math.huge
                if weightOf(src.inv) > 0 then
                    for _, dst in ipairs(outputs[src.color] or {}) do
                        local free, dist = freeOf(dst.inv), distance(src.loc, dst.loc)
                        if free > bestFree or (free == bestFree and free > 0 and dist < bestDist) then
                            best, bestFree, bestDist = dst, free, dist
                        end
                    end
                end
                if best and not energized then
                    last.grounded = last.grounded + 1          -- the grid is Overloaded: the drone waits
                elseif best and carriable(stacksOf(src.inv)) then
                    local leg = math.max(MIN_LEG_S, bestDist / SPEED_CM)
                    drones[src.path] = { phase = "outbound", target = best.path, untilT = now + leg, leg = leg,
                                         dist = bestDist }
                end
            end
        end
        for p in pairs(drones) do
            if not alive[p] then drones[p] = nil end      -- the station is gone
        end
    end

    local function totalsLine()
        return string.format("%d trips, %.1f kg carried (%s); %d empty, %d refused by a full or filtered output, "
            .. "%d mismatches", totals.trips, totals.grams / 1000, describeMoved(totals.items), totals.empty,
            totals.refused, totals.mismatches)
    end

    local function energyLine()
        if not HANDLER_CLASS then return "no energy cost" end
        local meter = last.power == nil and ("meter unreadable" .. (last.powerError and (": " .. last.powerError) or ""))
            or string.format("meter %d / %d, %s", last.available or 0, last.used or 0,
                last.power and "Energized" or ("Overloaded, " .. last.grounded .. " drones waiting"))
        return string.format("energy handlers: %d added, %d already there, %d failed%s; %s", handlers.added,
            handlers.found, handlers.failed, handlers.error and (" (" .. handlers.error .. ")") or "", meter)
    end

    -- the build menu follows the tables the world loaded with (main.lua isLoadedWith); the drones follow the setting
    local function menuLine()
        if not FEATURE or not api.isLoadedWith then return nil end
        local shown, on = api.isLoadedWith(FEATURE), enabled()
        if shown and on then return "build menu: shown in this world" end
        if not shown and not on then return "build menu: hidden in this world, and no milestone reward" end
        if shown then return "build menu: still shown until the world loads again (the setting was switched off)" end
        return "build menu: hidden until the world loads again (the setting was switched on): save and reload"
    end

    local function offLine()
        return string.format("drone stations: off in this world (%s): no drones fly and the stations use no energy; "
            .. "placed stations hold their items like any storage (%d energy handlers taken off this session)", LABEL,
            handlers.removed)
    end

    api.addReport(function(out)
        if not enabled() then out(offLine()); return end
        out(string.format("drone stations: %d input, %d output%s; %s; %s", last.inputs, last.outputs,
            last.client and " (not the host: the host moves the items)" or "", totalsLine(), energyLine()))
    end)

    -- "hardcore drones": the stations by colour, each drone, the totals, and where the setting and build menu stand
    api.addCommand("drones", function(out)
        local menu = menuLine()
        if not enabled() then
            out(offLine())
            if menu then out(menu) end
            return
        end
        local all = survey()
        if not all then out("drone stations: this machine is not the host; the host moves the items"); return end
        local now = #all > 0 and worldTime(all[1].obj) or clock
        out(string.format("drone stations: %d (load %.0f kg per trip, %.0f m/s, at least %.0f s per trip)", #all,
            LOAD_G / 1000, SPEED_CM / 100, MIN_LEG_S * 2))
        local colors, byColor = {}, {}
        for _, st in ipairs(all) do
            if not byColor[st.color] then byColor[st.color] = { input = {}, output = {} }; colors[#colors + 1] = st.color end
            table.insert(byColor[st.color][st.role], st)
        end
        table.sort(colors)
        for _, c in ipairs(colors) do
            local g = byColor[c]
            local state = #g.input == 0 and "no input station: nothing is sent"
                or #g.output == 0 and "no output station: nothing is sent" or "linked"
            out(string.format("  %s: %d input, %d output (%s)", c, #g.input, #g.output, state))
            local rows = 0
            for _, role in ipairs({ "input", "output" }) do
                for _, st in ipairs(g[role]) do
                    rows = rows + 1
                    if rows <= LIST_ROWS then
                        local d = role == "input" and drones[st.path] or nil
                        local where = st.loc and string.format("at %.0f, %.0f", st.loc[1] / 100, st.loc[2] / 100) or ""
                        local dline = role ~= "input" and "" or (d == nil and "; drone at home"
                            or string.format("; drone %s, %.0f m, %.0f s left", d.phase, d.dist / 100,
                                math.max(0, d.untilT - now)))
                        out(string.format("    %s %s: %.1f / %.0f kg%s", st.kind.name, where, weightOf(st.inv) / 1000,
                            (weightOf(st.inv) + freeOf(st.inv)) / 1000, dline))
                    end
                end
            end
            if rows > LIST_ROWS then out(string.format("    ... and %d more", rows - LIST_ROWS)) end
        end
        out("carried so far: " .. totalsLine())
        out(energyLine())
        if menu then out(menu) end
    end)

    local function forgetWorld()
        paths, lastSearch, drones, handled, off = {}, -math.huge, {}, {}, nil
        last.inputs, last.outputs, last.power, last.powerError = 0, 0, nil, nil
    end
    api.onMapLoaded(forgetWorld)
    if api.onMapLeaving then api.onMapLeaving(forgetWorld) end

    api.loop(CHECK_MS, "drone stations", function()
        local ok, err = pcall(tick)
        if not ok then log("drone stations: " .. tostring(err)) end
    end)
    log(string.format("drone stations ready (%d station types, load %.0f kg, %.0f m/s%s)", #CLASSES, LOAD_G / 1000,
        SPEED_CM / 100, FEATURE and (", only where '" .. FEATURE .. "' runs") or ""))
end
