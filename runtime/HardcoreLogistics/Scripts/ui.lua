-- Hardcore Logistics: one Off / On row per feature (cargo, deliveries, ...) at the end of the game's playstyle
-- settings list, on the new-game Customize screen and in the in-game Settings menu. Each row is an instance of the
-- game's own row widget with a setting ID the game does not know; the game skips unknown IDs when applying and reads
-- them as 0, so this script stores and restores the values (main.lua keeps them per world).
--
-- In a loaded world's Settings menu each row has a line right under it that asks the player to save and reload the
-- world while that feature's saved value differs from the one the world was loaded with (changes apply on the
-- next load). When the player's change makes it appear, the menu's list scrolls it into view. Live features (crop
-- trampling) apply at once and get no such line, unless they also own tables (local storage: the storage sizes and
-- the Logistics Hub follow on the next load); their line asks to reload to finish applying the change.
--
-- Telling the player's changes apart from the game's:
--   * A navigation call on a row (arrow click) is the player's. The value they moved to is worked out from the
--     direction and the value before the call, not read back afterwards, because the game may refresh the row
--     inside that same call and its refresh reads our unknown setting ID as 0.
--   * Otherwise (a change no hook reported, such as keyboard or pad input): the game can only ever reset a row to
--     0 (Off), so a change to On is the player's, a change to Off while the row is the menu's selected item is the
--     player's, and any other change is the game resetting the row; the stored value is shown again.

local ROW_CLASS = "/Game/Widgets/GameMenus/SettingsMenu/Widget_SettingsMenuOptions.Widget_SettingsMenuOptions_C"
local TEXT_CLASS = "/Game/Widgets/CustomUMG/TextAssets/Widget_TextElement.Widget_TextElement_C"
local NAV_CLASS = "/Script/UINavigation.UINavHorizontalComponent"
local ID_PREFIX = "HardcoreLogistics"        -- row setting IDs are HardcoreLogistics_<feature>
local TEMPLATE_ID = "DisableNoFuelMech"      -- a game row with localized Off / On options
local NOTICE_TEXT = "Save and reload the world to apply this change."
local NOTICE_TEXT_LIVE = "Save and reload the world to finish applying this change."   -- live feature with tables
local NOTICE_STYLE = "BB4"                   -- DT_UITextPreset: Regular 14 (row titles use B3, Light 16)
local NOTICE_INDENT = 18                     -- extra left padding so the line starts under the row title
local RECENT_TICKS = 4                       -- scan ticks (0.5 s each) a navigation call counts as "just now"

return function(api)
    local log = api.log
    local ours = {}          -- row full name -> row object
    local rowFeature = {}    -- row full name -> feature id
    local navParent = {}     -- row full name -> the menu's UINav widget
    local notices = {}       -- row full name -> {widget, fid, scroll, visible}: the reload line under that row
    local done = {}          -- playstyle widget full name -> true
    local busy = false       -- true while this script changes a row itself
    local shown = {}         -- row full name -> index this script last displayed or stored
    local navTick = {}       -- row full name -> scan tick of the last navigation call on it
    local navBefore = {}     -- row full name -> option index when a native navigation call started
    local tick = 0

    -- ------------------------------------------------------------ diagnostics: which hooks fire, first few times
    local fired, diagLeft = {}, 40
    local function diag(name, ctx)
        local n = (fired[name] or 0) + 1
        fired[name] = n
        if n > 3 or diagLeft <= 0 then return end
        diagLeft = diagLeft - 1
        local who, mine, idx = "?", false, "-"
        pcall(function()
            local full = ctx:GetFullName()
            who = full:match("([^%.:]+)$") or full
            mine = ours[full] ~= nil
            idx = tostring(ctx.OptionIndex)
        end)
        log(string.format("debug: %s ran on %s%s, option index %s", name, who, mine and " (our row)" or "", idx))
    end

    -- ------------------------------------------------------------ helpers
    local function children(panel)
        local list = {}
        local okCount, n = pcall(function() return panel:GetChildrenCount() end)
        if okCount and type(n) == "number" then
            for i = 0, n - 1 do
                local okChild, c = pcall(function() return panel:GetChildAt(i) end)
                if okChild and c and c:IsValid() then list[#list + 1] = c end
            end
            if #list > 0 then return list end
        end
        local ok, res = pcall(function() return panel:GetAllChildren() end)      -- fallback
        if not ok or res == nil then return list end
        if type(res) == "table" then
            for _, c in ipairs(res) do list[#list + 1] = c end
        else
            pcall(function() res:ForEach(function(_, e) list[#list + 1] = e:get() end) end)
        end
        return list
    end

    local function settingId(w)
        local ok, v = pcall(function() return w.SettingID end)
        return ok and api.asText(v) or nil
    end

    local function makeText(s)
        local ok, t = pcall(function() return FText(s) end)
        if ok and t then return t end
        local lib = StaticFindObject("/Script/Engine.Default__KismetTextLibrary")
        return lib:Conv_StringToText(s)
    end

    local function desiredIndex(key)
        return api.featureValue(rowFeature[key]) and 1 or 0
    end

    local function showIndex(row, index)
        busy = true
        local ok = pcall(function() row:UpdateTextToIndex(index) end)
        if not ok then pcall(function() row.OptionIndex = index end) end
        busy = false
        shown[row:GetFullName()] = index
    end

    -- A row's reload line is visible while that feature's saved value differs from the one the world runs with.
    -- When the player's change on row changedKey makes its line appear, scroll the menu's list to show it.
    local function updateNotices(changedKey)
        for key, n in pairs(notices) do
            if not n.widget:IsValid() then
                notices[key] = nil
            else
                local show = api.needsReload(n.fid)
                pcall(function() n.widget:SetVisibility(show and 3 or 1) end)     -- HitTestInvisible / Collapsed
                if show and not n.visible and key == changedKey and n.scroll then
                    pcall(function() n.scroll:ScrollWidgetIntoView(n.widget, true, 0, 16.0) end)   -- 0 = IntoView
                end
                n.visible = show
            end
        end
    end

    -- the player set a row to index: show it and store it (for the loaded world, or the world about to be created)
    local function store(row, source, index)
        local key = row:GetFullName()
        if row.OptionIndex ~= index then showIndex(row, index) end
        shown[key] = index
        api.setFeature(rowFeature[key], index == 1, "menu (" .. source .. ")")
        updateNotices(key)
    end

    -- is the row the menu's selected item right now (where arrow keys and the pad act)?
    local function isSelected(key, row)
        local ok, res = pcall(function()
            local parent = navParent[key]
            return parent:IsValid() and parent.ButtonIndex == row.NavButton.ButtonIndex
        end)
        return ok and res == true
    end

    -- ------------------------------------------------------------ hook handlers
    local function onNavigateStart(row)
        if busy or not row or not row:IsValid() then return end
        local key = row:GetFullName()
        if ours[key] then navBefore[key] = row.OptionIndex end
    end

    -- side is "Left" or "Right"; native is true for the plugin's NavigateLeft/Right (which has a real pre hook)
    local function onNavigated(name, row, side, native)
        diag(name, row)
        if busy or not row or not row:IsValid() then return end
        local key = row:GetFullName()
        if not ours[key] then return end
        local before = navBefore[key] or shown[key] or 0
        if native then navBefore[key] = nil end
        local loop = false
        pcall(function() loop = row.bLoopOptions == true end)
        local index
        if loop then
            index = 1 - before                          -- two options: any step toggles
        else
            index = (side == "Right") and 1 or 0        -- no wrap: right is On, left is Off
        end
        navTick[key] = tick
        store(row, name, index)
    end

    -- the game's own refresh of a row reads our unknown ID as 0; show the stored value again right away
    local function onRowRefreshed(row)
        if busy or not row or not row:IsValid() then return end
        local key = row:GetFullName()
        if not ours[key] then return end
        local want = desiredIndex(key)
        if row.OptionIndex ~= want then showIndex(row, want) end
    end

    -- ------------------------------------------------------------ hooks (retried on later injections if missing)
    local registered, reported = {}, {}
    local function tryHook(path, pre, post)
        if registered[path] then return end
        local ok, err = pcall(RegisterHook, path, pre or function() end, post or function() end)
        if ok then
            registered[path] = true
            log("hook " .. (path:match("[^/]+$") or path) .. ": ok")
        elseif not reported[path] then
            reported[path] = true
            log("hook " .. (path:match("[^/]+$") or path) .. ": " .. (tostring(err):match("^[^\n]*") or "?"))
        end
    end

    -- Round 5 (2026-11-08): only the native NavigateLeft/Right hooks fired; the row blueprint's events never did.
    -- The blueprint hooks stay as a fallback; they cost nothing when silent.
    local function registerHooks()
        for _, side in ipairs({ "Left", "Right" }) do
            local native, event = "Navigate" .. side, "OnNavigate" .. side
            tryHook(NAV_CLASS .. ":" .. native, function(ctx) onNavigateStart(ctx:get()) end,
                function(ctx) onNavigated(native, ctx:get(), side, true) end)
            tryHook(ROW_CLASS .. ":" .. event, nil, function(ctx) onNavigated(event, ctx:get(), side, false) end)
        end
        tryHook(ROW_CLASS .. ":Refresh", nil, function(ctx) onRowRefreshed(ctx:get()) end)
    end

    -- every scan: catch changes no hook reported, and undo resets by the game
    local resetsLogged, resets = 0, {}
    local function poll()
        tick = tick + 1
        for key, row in pairs(ours) do
            if not row:IsValid() then
                ours[key], rowFeature[key], navParent[key], shown[key] = nil, nil, nil, nil
                navTick[key], navBefore[key], resets[key] = nil, nil, nil
            elseif not busy and shown[key] ~= nil then
                local index = row.OptionIndex
                if index == shown[key] then
                    -- the value was changed elsewhere (the playstyle card, the console): show it
                    local want = desiredIndex(key)
                    if want ~= index then
                        showIndex(row, want)
                        updateNotices(nil)
                    end
                elseif index ~= shown[key] then
                    local recent = navTick[key] ~= nil and tick - navTick[key] <= RECENT_TICKS
                    if not recent and (index == 1 or isSelected(key, row)) then
                        store(row, "scan", index)
                    elseif (resets[key] or 0) < 20 then        -- never fight the menu forever
                        resets[key] = (resets[key] or 0) + 1
                        if resetsLogged < 10 then
                            resetsLogged = resetsLogged + 1
                            log(string.format("the menu set the %s row to %s without player input; showing %s again",
                                tostring(rowFeature[key]), index == 1 and "On" or "Off", shown[key] == 1 and "On" or "Off"))
                        end
                        showIndex(row, shown[key])
                    end
                end
            end
        end
    end

    -- ------------------------------------------------------------ building the rows
    local function createWidget(owner, classPath)
        local cls = StaticFindObject(classPath)
        if not cls or not cls:IsValid() then return nil end
        local wbl = StaticFindObject("/Script/UMG.Default__WidgetBlueprintLibrary")
        local pc = nil
        pcall(function() pc = owner:GetOwningPlayer() end)
        local w = wbl:Create(owner, cls, pc)
        if not w or not w:IsValid() then return nil end
        return w
    end

    -- Add one feature row after the existing ones and register it with the menu's UINavigation widget. Rows added
    -- after the menu was built have no ParentWidget, and clicking one made the game call through a null pointer
    -- (crash), so the row is only kept once AddUINavComponent has registered it.
    local function addRow(widget, root, template, feature)
        local row = createWidget(widget, ROW_CLASS)
        if not row then return nil, "could not create the row widget" end
        row.SettingID = api.makeName(ID_PREFIX .. "_" .. feature.id)
        row.SettingName = makeText(feature.label)
        row.NeedsApply = false
        row.bUseNumberRange = false
        row.MaxRange = 2
        local copied = pcall(function()
            row.StringOptions:Empty()
            row.StringOptions[1] = template.StringOptions[1]
            row.StringOptions[2] = template.StringOptions[2]
        end)
        if not copied then
            pcall(function()
                row.StringOptions[1] = makeText("Off")
                row.StringOptions[2] = makeText("On")
            end)
        end
        local count = 0
        pcall(function() count = #row.StringOptions end)
        if count < 2 then                      -- could not fill the labels: fall back to a 0 / 1 number range
            row.bUseNumberRange = true
            row.MinRange = 0
            row.MaxRange = 1
            log("could not set the Off / On labels; the row shows 0 / 1 instead")
        end

        local okInsert, err = pcall(function() root:AddChild(row) end)
        if not okInsert then return nil, "could not add the row: " .. tostring(err) end
        pcall(function() row.Slot:SetPadding(template.Slot.Padding) end)

        local navOwner, navIndex = nil, nil
        local okNav, navMsg = pcall(function()
            local parent = template.ParentWidget
            if not parent or not parent:IsValid() then error("template row has no UINav parent") end
            local function countOf(arrName)
                local okC, n = pcall(function() return #parent[arrName] end)
                return okC and n or -1
            end
            local grid = parent:GetButtonGridIndex(template.NavButton.ButtonIndex)
            local before = countOf("UINavButtons")
            parent:AddUINavComponent(row, grid, -1)
            local after = countOf("UINavButtons")
            local ourIndex = row.NavButton.ButtonIndex
            local facts = string.format("grid %s, menu buttons %d->%d, button %s", tostring(grid), before, after,
                tostring(ourIndex))
            if not (after == before + 1 and type(ourIndex) == "number" and ourIndex >= 0) then
                error("AddUINavComponent did not register the row: " .. facts)
            end
            navOwner, navIndex = parent, ourIndex
            local rowParent = row.ParentWidget
            if not rowParent or not rowParent:IsValid() then
                row.ParentWidget = parent                  -- registered, but the parent link is not filled in
                pcall(function() row.ParentCollection = template.ParentCollection end)
                rowParent = row.ParentWidget
                if not rowParent or not rowParent:IsValid() then error("could not set ParentWidget: " .. facts) end
            end
            return facts
        end)
        if not okNav then
            if navOwner and navIndex then                     -- undo a half-finished registration first
                pcall(function() navOwner:DeleteUINavElement(navIndex, false) end)
            end
            pcall(function() row:RemoveFromParent() end)     -- never leave an unregistered row that crashes on click
            return nil, "could not register the row with the menu's navigation, removed it again: " .. tostring(navMsg)
        end

        local key = row:GetFullName()
        ours[key], rowFeature[key], navParent[key] = row, feature.id, navOwner
        showIndex(row, desiredIndex(key))
        return row, string.format("%s %s (%s)", feature.label, shown[key] == 1 and "On" or "Off", navMsg)
    end

    -- the scroll box the playstyle list sits in (Widget_PlaystyleSettings -> Game vertical box -> ScrollBox)
    local function findScrollBox(widget)
        local node = widget
        for _ = 1, 8 do
            local ok, parent = pcall(function() return node:GetParent() end)
            if not ok or not parent or not parent:IsValid() then return nil end
            local cls = ""
            pcall(function() cls = parent:GetClass():GetFName():ToString() end)
            if cls:find("ScrollBox", 1, true) then return parent end
            node = parent
        end
        return nil
    end

    -- a plain text line (the game's own text widget, in its smaller caption style) right under a row; starts hidden
    local function addNotice(widget, root, template, row, feature, scroll)
        local text = feature.live and NOTICE_TEXT_LIVE or NOTICE_TEXT
        local ok, err = pcall(function()
            local notice = createWidget(widget, TEXT_CLASS)
            if not notice then error("could not create the text widget") end
            pcall(function() notice.TextStyle.RowName = api.makeName(NOTICE_STYLE) end)
            pcall(function() notice.Text = makeText(text) end)
            pcall(function() notice:SetVisibility(1) end)                       -- Collapsed until needed
            root:AddChild(notice)
            local okPad = pcall(function()
                local p = template.Slot.Padding
                notice.Slot:SetPadding({ Left = p.Left + NOTICE_INDENT, Top = p.Top, Right = p.Right, Bottom = p.Bottom })
            end)
            if not okPad then pcall(function() notice.Slot:SetPadding(template.Slot.Padding) end) end
            pcall(function() notice:SetText(makeText(text)) end)
            notices[row:GetFullName()] = { widget = notice, fid = feature.id, scroll = scroll, visible = false }
        end)
        if not ok then log("could not add the reload line for " .. feature.id .. ": " .. tostring(err)) end
    end

    local attempts = {}
    local function inject(widget)
        local name = widget:GetFullName()
        local root = widget.WidgetTree and widget.WidgetTree.RootWidget
        if not root or not root:IsValid() then return false end
        local template = nil
        local kids = children(root)
        for _, c in ipairs(kids) do
            local id = settingId(c)
            if id and id:sub(1, #ID_PREFIX) == ID_PREFIX then done[name] = true; return true end   -- already there
            if id == TEMPLATE_ID then template = c end
        end
        if not template then
            attempts[name] = (attempts[name] or 0) + 1
            if attempts[name] < 10 then return false end              -- retry for ~5 s while the menu builds
            done[name] = true
            log(string.format("no '%s' row found in %s; its root %s has %d children:", TEMPLATE_ID, name,
                root:GetFullName(), #kids))
            for i, c in ipairs(kids) do
                if i > 25 then break end
                log(string.format("    %s  id=%s", c:GetFullName(), tostring(settingId(c))))
            end
            return false
        end
        done[name] = true
        local inWorld = api.getActiveSlot() ~= nil         -- reload lines only make sense in a loaded world
        local scroll = inWorld and findScrollBox(widget) or nil
        local added = {}
        for _, feature in ipairs(api.features) do
            local row, msg = addRow(widget, root, template, feature)
            if not row then
                log("row for " .. feature.id .. ": " .. tostring(msg))
                break
            end
            if inWorld and (not feature.live or feature.tables) then     -- right under its row
                addNotice(widget, root, template, row, feature, scroll)
            end
            added[#added + 1] = msg
        end
        if #added > 0 then
            registerHooks()
            updateNotices(nil)
            log(string.format("added %d rows to %s: %s%s", #added, name:match("([^%.]+%.[^%.]+)$") or name,
                table.concat(added, "; "), inWorld and (scroll and "; reload lines added" or
                "; reload lines added, no scroll box found") or ""))
        end
        return #added > 0
    end

    local skipped = {}
    local function scan()
        local list = FindAllOf("Widget_PlaystyleSettings_C")
        if list then
            for _, w in ipairs(list) do
                if w:IsValid() then
                    local name = w:GetFullName()
                    if not done[name] then
                        if name:find("/Engine/Transient", 1, true) then
                            local ok, err = pcall(inject, w)
                            if not ok then log("injection failed: " .. tostring(err)); done[name] = true end
                        elseif not skipped[name] then
                            skipped[name] = true
                            log("skipping (template, not a live menu): " .. name)
                        end
                    end
                end
            end
        end
        poll()
    end

    api.loop(500, "settings rows scan", scan)
    log(string.format("settings rows ready (%d features)", #api.features))
end
