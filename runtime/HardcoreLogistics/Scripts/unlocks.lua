-- Hardcore Logistics: the mod's buildings in worlds that are already past their milestone.
--
-- The buildings' container (tools/build_buildings.py) puts each building into a milestone's reward list, so the game
-- unlocks it when that milestone is reached. A world that reached the milestone before the building existed never
-- sees that reward. When a world loads, this script unlocks such buildings (AFarMechGameStateBase::
-- Server_UnlockConstruct; the game state lists unlocked ones in AcquiredConstructBlueprints.Constructs). It waits
-- until the game knows the world's milestone count: the delivery system reads 0 for a moment after a world loads, so
-- 0 means "look again later". An entry tied to a feature (the Logistics Hubs: "storage") is unlocked only in worlds
-- loaded with that feature's table changes (main.lua isLoadedWith), the ones that show it in the build menu and make
-- it a milestone reward: switching the feature on in a loaded world unlocks it after the next load, when it shows.
--
-- Console:  hardcore unlock               each building: unlocked or not, its milestone, its build-menu row
--           hardcore unlock all | <row>   unlock now, whatever the milestones and features (to try them out)
-- Other scripts: api.unlockConstructs(rows, force) and api.constructStatus().

local PC_CLASS = "BP_FarMechPlayerController_C"
local CONSTRUCTS_TABLE = "/Game/DataTables/DT_Constructs.DT_Constructs"
local CHECK_MS = 1000
local RETRY_TICKS = 10          -- while the milestones are not known yet, look again this many checks later

return function(api)
    local log = api.log
    local ENTRIES = {}          -- {row, name, milestone, number, feature}
    for _, e in ipairs(api.unlocks or {}) do
        if type(e.row) == "string" and e.row ~= "" then
            ENTRIES[#ENTRIES + 1] = {
                row = e.row, name = type(e.name) == "string" and e.name or e.row, milestone = e.milestone,
                number = tonumber(e.milestone_number),
                feature = type(e.feature) == "string" and e.feature ~= "" and e.feature or nil }
        end
    end
    if #ENTRIES == 0 then return end

    local settledFor = nil      -- the eligible rows (joined) whose unlock was settled since this map loaded
    local nextTick, tickCount = 0, 0
    local lastResult = "nothing yet"

    local function valid(o)
        if o == nil then return false end
        local ok, v = pcall(function() return o:IsValid() end)
        return ok and v == true
    end

    local function num(v)
        if type(v) == "number" then return v end
        if type(v) == "userdata" then
            local ok, x = pcall(function() return v:get() end)
            if ok and type(x) == "number" then return x end
        end
        return tonumber(v)
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

    local function nameText(n)
        if type(n) == "string" then return n end
        local ok, s = pcall(function() return n:ToString() end)
        if ok and s ~= nil then return tostring(s) end
        ok, s = pcall(function() return n:get():ToString() end)
        if ok and s ~= nil then return tostring(s) end
        return tostring(n)
    end

    local function gameState()
        local okPc, pc = pcall(FindFirstOf, PC_CLASS)
        if not okPc or not valid(pc) then return nil end
        local ok, gs = pcall(function()
            return StaticFindObject("/Script/Engine.Default__GameplayStatics"):GetGameState(pc)
        end)
        if ok and valid(gs) then return gs end
        return nil
    end

    local function completedMilestones()
        local ok, ds = pcall(FindFirstOf, "DeliverySystem")
        if not ok or not valid(ds) then return nil end
        local okN, n = pcall(function() return ds:GetAmountCompletedMilestones() end)
        return okN and num(n) or nil
    end

    -- {construct name -> true} for the constructs the game state lists as unlocked; nil when it cannot tell
    local function unlockedConstructs(gs)
        local set, readable = {}, false
        pcall(function()
            each(gs.AcquiredConstructBlueprints.Constructs, function(n) set[nameText(n)] = true end)
            readable = true
        end)
        return readable and set or nil
    end

    -- {row -> true} for the construct table's rows (the buildings' rows come in their container, so a missing one
    -- means that container is not installed or not mounted); nil when the table cannot be read. UE4SS's LoadAsset
    -- cannot tell: it looks assets up in the game's asset registry, which lists no package a mod adds.
    local function constructRows()
        local ok, dt = pcall(StaticFindObject, CONSTRUCTS_TABLE)
        if not ok or not valid(dt) then return nil end
        local okRows, rows = pcall(function() return dt:GetAllRows() end)
        if not okRows or type(rows) ~= "table" then return nil end
        local set = {}
        for _, entry in ipairs(rows) do set[nameText(entry.Name)] = true end
        return set
    end

    local function names(list)
        local out = {}
        for _, e in ipairs(list) do out[#out + 1] = e.name end
        return table.concat(out, ", ")
    end

    -- {unlocked = set or nil, rows = set or nil, milestones = number or nil}
    local function status()
        local gs = gameState()
        return { unlocked = gs and unlockedConstructs(gs) or nil, rows = constructRows(),
                 milestones = completedMilestones() }
    end

    -- Unlock the entries not unlocked yet; unless `force`, only those whose milestone is done. Returns a line for the
    -- log or the console, and whether that settles it (false while the game cannot tell yet).
    local function unlock(entries, force)
        local gs = gameState()
        if not gs then return "no game state yet", false end
        local unlocked = unlockedConstructs(gs) or {}
        local todo = {}
        for _, e in ipairs(entries) do
            if not unlocked[e.row] then todo[#todo + 1] = e end
        end
        if #todo == 0 then return "already unlocked", true end
        local done = completedMilestones()
        local due = todo
        if not force then
            if done == nil or done == 0 then return "the milestones are not known yet", false end
            due = {}
            for _, e in ipairs(todo) do
                if e.number and done >= e.number then due[#due + 1] = e end
            end
            if #due == 0 then return string.format("none due yet (%d milestones done)", done), true end
        end
        local rows = constructRows()
        local okList, missing = {}, {}
        for _, e in ipairs(due) do
            if rows and not rows[e.row] then
                missing[#missing + 1] = e
            else
                local ok, err = pcall(function() gs:Server_UnlockConstruct(api.makeName(e.row)) end)
                if not ok then return "unlocking " .. e.name .. " failed: " .. tostring(err), true end
                okList[#okList + 1] = e
            end
        end
        local parts = {}
        if #okList > 0 then parts[#parts + 1] = "unlocked " .. names(okList) end
        if #missing > 0 then
            parts[#parts + 1] = "the construct table has no row for " .. names(missing) .. ", so the buildings' "
                .. "container (HardcoreLogisticsBuildings_P in Paks/~mods) is not installed or not mounted"
        end
        return table.concat(parts, "; ") .. string.format(" (%s milestones done)", tostring(done)), true
    end

    api.unlockConstructs = function(rows, force)
        local list = {}
        for _, e in ipairs(ENTRIES) do
            for _, r in ipairs(rows) do
                if e.row == r then list[#list + 1] = e end
            end
        end
        return unlock(list, force)
    end
    api.constructStatus = status

    -- a feature-tied entry counts while the world runs with that feature's table changes (they show the building)
    local function featureOn(fid)
        if api.isLoadedWith then return api.isLoadedWith(fid) end
        return api.isActive(fid)
    end

    -- the entries for the world loaded now (features it runs), and a key telling when that set changes
    local function eligible()
        local list, keys = {}, {}
        for _, e in ipairs(ENTRIES) do
            if e.feature == nil or featureOn(e.feature) then
                list[#list + 1] = e
                keys[#keys + 1] = e.row
            end
        end
        return list, table.concat(keys, ",")
    end

    -- a world is loaded: main.lua's own flag, which costs nothing (getActiveSlot looks objects up through the whole
    -- object table, and doing that every second stuttered the game, 0.11.0)
    local function worldLoaded()
        if api.worldLoaded then return api.worldLoaded() end
        return api.getActiveSlot() ~= nil
    end

    local function tick()
        tickCount = tickCount + 1
        if not worldLoaded() then return end
        local list, key = eligible()
        if #list == 0 or settledFor == key or tickCount < nextTick then return end
        local result, settled = unlock(list, false)
        if settled then
            settledFor = key
            lastResult = result
            log("building unlocks: " .. result)
        else
            nextTick = tickCount + RETRY_TICKS
        end
    end

    api.addReport(function(out) out("building unlocks: " .. lastResult) end)

    -- "hardcore unlock": each building's state; "hardcore unlock all" or "hardcore unlock <row>": unlock it now
    api.addCommand("unlock", function(out, arg)
        if arg and arg ~= "" then
            local list = {}
            for _, e in ipairs(ENTRIES) do
                if arg == "all" or e.row:lower() == arg then list[#list + 1] = e end
            end
            if #list == 0 then
                local rows = {}
                for _, e in ipairs(ENTRIES) do rows[#rows + 1] = e.row end
                out("no building " .. arg .. "; type  hardcore unlock all  or one of: " .. table.concat(rows, ", "))
                return
            end
            out("building unlocks: " .. (unlock(list, true)))
            return
        end
        local s = status()
        out(string.format("the mod's buildings (%s milestones done):", tostring(s.milestones)))
        for _, e in ipairs(ENTRIES) do
            out(string.format("  %s (row %s): %s; unlocks at %s%s; build-menu row %s", e.name, e.row,
                s.unlocked == nil and "unlock unknown" or (s.unlocked[e.row] and "unlocked" or "not unlocked"),
                tostring(e.milestone), e.feature and (" (" .. e.feature .. " on)") or "",
                s.rows == nil and "unknown" or (s.rows[e.row] and "in DT_Constructs"
                    or "MISSING (the buildings' container is not mounted)")))
        end
        out("type  hardcore unlock all  (or a row name) to unlock them now")
    end)

    local function forgetWorld()
        settledFor, nextTick = nil, 0
    end
    api.onMapLoaded(forgetWorld)
    if api.onMapLeaving then api.onMapLeaving(forgetWorld) end

    api.loop(CHECK_MS, "building unlock check", function()
        local ok, err = pcall(tick)
        if not ok then log("building unlocks: " .. tostring(err)) end
    end)
    log(string.format("building unlocks ready (%d buildings)", #ENTRIES))
end
