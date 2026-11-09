-- Hardcore Logistics: an extra playstyle card on the new-game screen, after the base preset's card (Challenging).
--
-- The card is an instance of the game's own card widget (Widget_DifficultySelectorButton). The screen only listens
-- to its own placed cards, so this script drives ours:
--   * Choosing it (moving the focus onto it, or clicking it) calls the screen's own handler as if the base card had
--     been chosen, so the game applies the real base preset (Challenging). Then the "selected" frame moves from the
--     base card to ours and every feature is switched on for the world about to be created.
--   * Choosing another card switches the features off again; the game handles that card itself.
--   * When the game moves the focus by itself (back from Customize it focuses the card of the selected preset, the
--     base card), the focus goes back to our card.
--   * While Customize is open our card is hidden like the game's cards. Customize itself stays the game's screen:
--     its Playstyle row shows the base preset (Challenging), and the feature rows are where a player changes the
--     features by hand. (0.7.1 relabelled the row and the preset artwork; the game redraws both, so it was removed.)
--   * Back from Customize with a different preset (changed in its Playstyle row), the game focuses that preset's
--     card: our card is no longer chosen, and the features stay as set in Customize.
-- Opening the new-game screen starts with every feature off (until the card or the Customize rows say otherwise).
--
-- Focus changes are seen by polling the screen's UINavigation selection (hooks on the screen's blueprint functions
-- never fire in this game). A native hook on NavigateTo marks the focus moves the game's blueprints make, and a
-- native hook on UINavButton:OnClick reports clicks on our card.

local MENU_CLASS = "Widget_FirstTimeSettingsBase_C"
local CARD_CLASS = "/Game/Widgets/MainMenu/Widget_DifficultySelectorButton.Widget_DifficultySelectorButton_C"
local NAV_WIDGET = "/Script/UINavigation.UINavWidget"
local NAV_BUTTON = "/Script/UINavigation.UINavButton"
local GAME_CARDS = { "Creative", "Relaxed", "Balanced", "Challenging", "Custom" }    -- widget names on the screen
local CARD_FOR_PRESET = { Balanced = "Balanced", Challenge = "Challenging", Creative = "Creative", Relaxed = "Relaxed" }
local CARD_GAP = 5             -- the game puts 5-wide spacers between its cards
local POLL_MS = 150
local SEARCH_EVERY = 3         -- look for a new screen every 3rd poll (~0.45 s)

return function(api)
    local log, mode = api.log, api.mode
    local baseCardName = CARD_FOR_PRESET[mode.base_preset] or "Challenging"
    local state = nil          -- the live new-game screen and our card on it
    local progTarget = nil     -- focus index a blueprint (or this script) just moved the screen to with NavigateTo
    local done = {}            -- screen full name -> true once handled
    local hooked = false
    local tick = 0
    local diagLeft = 30

    local function valid(o) return o ~= nil and o:IsValid() end

    local function prop(obj, name)
        local ok, v = pcall(function() return obj[name] end)
        if ok then return v end
        return nil
    end

    local function navIndex(w)
        local ok, v = pcall(function() return w.NavButton.ButtonIndex end)
        return ok and v or nil
    end

    local function text(s)
        local ok, t = pcall(function() return FText(s) end)
        if ok and t then return t end
        return StaticFindObject("/Script/Engine.Default__KismetTextLibrary"):Conv_StringToText(s)
    end

    local function diag(fmt, ...)
        if diagLeft > 0 then
            diagLeft = diagLeft - 1
            log("card debug: " .. string.format(fmt, ...))
        end
    end

    -- name of the game card with this focus index, if any
    local function gameCardAt(menu, idx)
        for _, name in ipairs(GAME_CARDS) do
            local w = prop(menu, name)
            if valid(w) and navIndex(w) == idx then return name end
        end
        return nil
    end

    local function selectedPreset(menu)
        return api.asText(prop(menu, "SelectedPreset"))
    end

    -- the gold "selected" frame: on our card instead of the base card, or off our card
    local function frameOnOurs(on)
        if on then
            pcall(function() state.base:DeselectThis() end)
            pcall(function() state.card:SelectThis() end)
        else
            pcall(function() state.card:DeselectThis() end)
        end
    end

    -- the player chose our card: apply the base preset through the screen's own handler, switch every feature on
    local function choose(how)
        api.setAllFeatures(true, "playstyle card")
        local handler = (how == "click") and "HandlePresetClicked" or "HandlePresetNaviagtedTo"
        local ok, err = pcall(function() state.menu[handler](state.menu, api.makeName(mode.base_preset)) end)
        if not ok then log("playstyle card: " .. handler .. " failed: " .. tostring(err)) end
        local wasChosen = state.chosen
        state.chosen = true
        frameOnOurs(true)
        if not wasChosen then
            log(string.format("playstyle card chosen (%s): preset %s (screen now on %s), every feature on", how,
                mode.base_preset, tostring(selectedPreset(state.menu))))
        end
    end

    local function unchoose(reason, keepFeatures)
        state.chosen = false
        frameOnOurs(false)
        if not keepFeatures then api.setAllFeatures(false, "playstyle card") end
        log("playstyle card no longer chosen: " .. reason .. (keepFeatures and " (features kept)" or " (features off)"))
    end

    -- ------------------------------------------------------------ hooks
    local function registerHooks()
        if hooked then return end
        hooked = true
        local function hook(path, pre, post)
            local ok, err = pcall(RegisterHook, path, pre or function() end, post or function() end)
            log("card hook " .. path:match("[^%.]+$") .. ": " .. (ok and "ok" or (tostring(err):match("^[^\n]*") or "?")))
        end
        -- focus moves made through the UFunction (blueprints, this script); player input calls it from C++ and
        -- does not pass through here
        hook(NAV_WIDGET .. ":NavigateTo", nil, function(ctx)
            local menu = ctx:get()
            if state and valid(menu) and valid(state.menu) and menu:GetFullName() == state.menu:GetFullName() then
                progTarget = prop(menu, "ButtonIndex")
            end
        end)
        hook(NAV_BUTTON .. ":OnClick", nil, function(ctx)
            if not state or not valid(state.card) then return end
            local ok, ours = pcall(function() return ctx:get():GetFullName() == state.card.NavButton:GetFullName() end)
            if ok and ours then state.pendingClick = true end         -- handled on the next poll
        end)
    end

    -- ------------------------------------------------------------ building the card
    local function inject(menu)
        local base = prop(menu, baseCardName)
        if not valid(base) then return false, "no " .. baseCardName .. " card on the screen" end
        local custom = prop(menu, "Custom")
        local box = base:GetParent()
        if not valid(box) then return false, "the cards have no parent panel" end
        local cls = StaticFindObject(CARD_CLASS)
        if not valid(cls) then return false, "the card class is not loaded" end
        local pc = nil
        pcall(function() pc = menu:GetOwningPlayer() end)
        local card = StaticFindObject("/Script/UMG.Default__WidgetBlueprintLibrary"):Create(menu, cls, pc)
        if not valid(card) then return false, "could not create the card" end

        card.Title = text(mode.title)
        card.DescriptionText = text(mode.description)
        card.Preset = api.makeName(mode.base_preset)
        pcall(function() card.Icon = (valid(custom) and custom.Icon) or base.Icon end)    -- the hidden Custom card's art
        for _, p in ipairs({ "HoveredWidth", "UnhoveredWidth", "SelectedUnohoveredWidth", "ReziseSpeed" }) do
            pcall(function() card[p] = base[p] end)
        end

        -- appended to the cards' row: everything between the base card and the end is collapsed on this screen
        local okAdd, addErr = pcall(function() box:AddChild(card) end)
        if not okAdd then return false, "could not add the card: " .. tostring(addErr) end
        pcall(function()
            local s, bs = card.Slot, base.Slot
            s:SetPadding({ Left = CARD_GAP, Top = 0, Right = 0, Bottom = 0 })
            pcall(function() s:SetSize(bs.Size) end)
            pcall(function() s:SetHorizontalAlignment(bs.HorizontalAlignment) end)
            pcall(function() s:SetVerticalAlignment(bs.VerticalAlignment) end)
        end)

        -- UINavigation: right after the base card in its grid, so the arrow keys reach it next. The cards are plain
        -- UINavComponents (no ParentWidget; that belongs to the horizontal rows); the screen itself is their
        -- UINavigation widget, which is checked before anything is registered.
        local navOwner, ourIndex = nil, nil
        local okNav, navMsg = pcall(function()
            local parent = menu
            local bIdx = base.NavButton.ButtonIndex
            local owns = false
            pcall(function() owns = parent:GetButtonAtIndex(bIdx):GetFullName() == base.NavButton:GetFullName() end)
            if not owns then error("the screen does not hold the " .. baseCardName .. " card's button " .. tostring(bIdx)) end
            local grid = parent:GetButtonGridIndex(bIdx)
            local inGrid = parent:GetButtonIndexInGrid(bIdx)
            local before = #parent.UINavButtons
            parent:AddUINavComponent(card, grid, inGrid + 1)
            local after = #parent.UINavButtons
            ourIndex = card.NavButton.ButtonIndex
            local facts = string.format("grid %s, place %s, button %s, menu buttons %d->%d", tostring(grid),
                tostring(inGrid + 1), tostring(ourIndex), before, after)
            if not (after == before + 1 and type(ourIndex) == "number" and ourIndex >= 0) then
                error("AddUINavComponent did not register the card: " .. facts)
            end
            navOwner = parent
            return facts
        end)
        if not okNav then
            if navOwner and ourIndex then pcall(function() navOwner:DeleteUINavElement(ourIndex, false) end) end
            pcall(function() card:RemoveFromParent() end)       -- never leave an unregistered card that crashes on use
            return false, "could not register the card with the screen's navigation: " .. tostring(navMsg)
        end

        state = { menu = menu, card = card, base = base, chosen = false, hidden = false,
                  lastIdx = prop(menu, "ButtonIndex") }
        api.setAllFeatures(false, "new-game screen opened")
        registerHooks()
        return true, navMsg
    end

    -- ------------------------------------------------------------ every poll
    local function findScreen()
        local list = FindAllOf(MENU_CLASS)
        for _, menu in ipairs(list or {}) do
            if menu:IsValid() then
                local name = menu:GetFullName()
                if not done[name] and name:find("/Engine/Transient", 1, true) then
                    local base = prop(menu, baseCardName)
                    if valid(base) and (navIndex(base) or -1) >= 0 then     -- the screen has set up its navigation
                        done[name] = true
                        local ok, msg = inject(menu)
                        log((ok and "added the " .. mode.title .. " card (" or "no playstyle card: ") .. tostring(msg) ..
                            (ok and ")" or ""))
                        return
                    end
                end
            end
        end
    end

    local function poll()
        tick = tick + 1
        if state and not (valid(state.menu) and valid(state.card)) then state = nil end
        if not state then
            if tick % SEARCH_EVERY == 0 then findScreen() end
            return
        end
        local menu, card = state.menu, state.card

        -- Customize open: hide our card like the game's cards
        local customize = false
        pcall(function() customize = menu.SizeBox_Settings:GetVisibility() ~= 1 end)     -- 1 = Collapsed
        if customize ~= state.hidden then
            state.hidden = customize
            pcall(function() card:SetVisibility(customize and 1 or 0) end)
        end

        -- focus changes
        local idx = prop(menu, "ButtonIndex")
        if idx ~= state.lastIdx then
            local programmatic = progTarget ~= nil and idx == progTarget
            state.lastIdx = idx
            local ours = navIndex(card)
            local other = gameCardAt(menu, idx)
            diag("focus %s -> %s%s, preset %s", tostring(idx), idx == ours and "our card" or tostring(other or "not a card"),
                programmatic and " (by the game)" or "", tostring(selectedPreset(menu)))
            if idx == ours then
                if not programmatic and not state.chosen then choose("focus") end
            elseif other and state.chosen then
                if not programmatic then
                    unchoose("the player chose " .. other, false)
                elseif other == baseCardName and selectedPreset(menu) == mode.base_preset then
                    state.reassert = true          -- back from Customize: the game focused the base card
                else
                    unchoose("the game focused " .. other .. " (preset now " .. tostring(selectedPreset(menu)) .. ")", true)
                end
            end
        end

        if state.reassert then
            state.reassert = false
            pcall(function() menu:NavigateTo(navIndex(card), false, true) end)
            state.lastIdx = prop(menu, "ButtonIndex")
            frameOnOurs(true)
        end
        if state.pendingClick then
            state.pendingClick = false
            choose("click")
        end
        -- a blueprint focus move is always seen by the first poll after it; never let the marker go stale
        progTarget = nil
    end

    api.loop(POLL_MS, "playstyle card poll", poll)
    log("playstyle card ready (" .. mode.title .. ", base preset " .. mode.base_preset .. ")")
end
