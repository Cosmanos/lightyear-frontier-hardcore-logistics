# Changelog

## 0.15.7 (2026-11-10): clearer settings rows, and a row of its own for the Drone Stations

The user asked for row names that say what each part does, and for the drones to have "a separate setting ... not
be included in the local storage. No change to how they work", named "delivery drone stations".

- **Row names** (`mod_config.json` feature labels). The setting IDs stay, so saved choices are kept:
  - "Hardcore Logistics: Lower Mech Cargo" (was "Mech Cargo");
  - "Hardcore Logistics: Bigger Material Deliveries" (was "Deliveries");
  - "Hardcore Logistics: Local Base Storage" (was "Local Storage");
  - "Hardcore Logistics: Crop Trampling" as before.
- **A fifth row, "Hardcore Logistics: Delivery Drone Stations"** (feature `drones`, live, on with the Hardcore
  Logistics card). The stations work as before while it is on.
  - **Build menu:** it works like the Logistics Hub with local storage. The container ships both station rows with
    `Features.Legacy` and outside Milestone 8's rewards (`drone_stations.feature`). `build_buildings.py` now ties any
    building group that has a feature, not only the hubs. Before a world with the row on loads, the runtime clears the
    flags and adds the stations to Milestone 8. Worlds without it never see them, and earned stations unlock on load
    only in worlds with it.
  - **Drones (`drones.lua`):** they follow the row at once. While it is off, no drone flies and no station gets an
    energy handler. Switching it off destroys the handlers (`K2_DestroyComponent`; their EndPlay unregisters them),
    so placed stations are plain storage. A drone in the air is dropped with its trip, and its load stays in the
    input station.
  - **After a switch in a loaded world:** the build menu follows on the next load, and the row shows the "finish
    applying" reload line.
  - **Console:** `hardcore drones` says when the row is off, and whether this world's build menu shows the stations.
    `hardcore drones on|off` switches the row. `main.lua` now handles `<feature> on|off` before the scripts' own
    commands, since this feature and the readout share the name.
- **Existing worlds:** `worlds.txt` lists the features that are on, so every world starts with the new row off.
  Placed stations stay, as plain storage, until the row is turned on.

The runtime and container are rebuilt and installed. All eight mocked runs pass, with new cases:
- `smoke_drones`: off, switched on, switched off mid-flight, on again, and a new world.
- `smoke_hub_visibility`: stations shown only in worlds with `drones`, both features' table entries applied and
  restored apart, and the console order.

Tested in game (2026-11-10): the user reported "Seems to be working".

## 0.15.6 (2026-11-09): the settings rows say "Hardcore Logistics"

The user kept the mod's name and the card title, Hardcore Logistics ("leave it like it is"), and asked for the
settings rows to carry the full name "to be clear they are from the mod".

- **The four rows** (`mod_config.json` feature labels): "Hardcore Logistics: Mech Cargo", "Hardcore Logistics:
  Deliveries", "Hardcore Logistics: Crop Trampling" and "Hardcore Logistics: Local Storage". They were "Hardcore Mech
  Cargo" and so on.
- **The colon:** it makes the prefix read as a group name in the game's settings list.
- **Saved choices are kept:** the labels are display text only. The rows' setting IDs (`HardcoreLogistics_<feature>`)
  and each world's saved values (`worlds.txt`) use the feature IDs, so no choice resets.
- **README:** its mentions of the rows follow the new names.

The runtime mod is rebuilt and installed, and all eight mocked runs pass. Not yet seen in game: check that the longer
names fit beside the row's Off / On arrows.

### The first public release

0.15.6 is the version released on Nexus Mods. The user: "I want to release it to nexus tonight"; they kept 0.15.6
over 1.0.0.

- **`tools/release.py`:** builds both parts fresh and packs `dist/release/HardcoreLogistics-0.15.6.zip`, 15.5 MB with
  13 files.
  - Layout: the buildings container for `Paks/~mods`, and the UE4SS mod with an `enabled.txt`, so players don't edit
    `mods.txt`. `UE4SS.dll` 3.0.1 checks for that file.
  - It also holds `release/README.txt` as "Hardcore Logistics - Read me.txt". It never holds a `worlds.txt`.
- **`release/nexus_description.bbcode`:** the Nexus summary and description, with one placeholder for the Workshop
  Shed credit.
- **`mod_config.json` `"version"`:** written into `edits.lua`. `main.lua` logs it at load.
- **Source:** published on GitHub, public, as Cosmanos/lightyear-frontier-hardcore-logistics, under the MIT license
  (`LICENSE`).

## 0.15.5 (2026-11-09): the playstyle card's description in the game's voice

The user, showing the game's own cards:
- Challenging: "For those seeking a challenge. Damage is increased, items are permanently lost on knockout, and fuel is
  more scarce."
- Balanced: "The standard Lightyear Frontier experience. Recommended for new players."
- Relaxed: "A low-pressure experience for those who want to take their time. No damage taken and days are longer."

Their request: "Focus on making the game more difficult or something. Do not mention the changes directly and take
the game's style for those."

- **Hardcore Logistics card** (`mod_config.json` `mode.description`): "A reworked and rebalanced modded experience for
  players who like a planning challenge."
- **How we got there:**
  - My first draft didn't land ("I still dont really like it"): "For seasoned pioneers who want the frontier to push
    back. Getting things where they need to be is half the battle."
  - The user gave their own line, "Reworked and rebalanced moded experience for players who like planning
    challenges".
  - They picked the version closest to it from four drafts. The others echoed the Balanced card, said "Recommended
    for experienced players", or built on Challenging.
- **Was:** "Challenging, plus hardcore logistics: the mech hauls less cargo, deliveries ask for more components, the
  mech tramples crops and only nearby storage counts (storages hold twice as much)."
- **The changes are listed in the README instead.**

The runtime mod is rebuilt and installed, and the card and main mocked runs pass. Not yet seen in game.

## 0.15.4 (2026-11-09): short building descriptions

The user, after confirming the energy cost works ("Ok power works"): "The description for the buildings we made are
too lengthy". They suggested something like "carries items over long distances. Use paint to channel, works only when
powered", and "something again more vague and short" for the Logistics Hub.

So the descriptions now follow the game's own: one plain line, plus "Requires ... to operate." like the Watering Drone
Station's "Requires water to operate.". The build menu shows the energy cost on its own line, and the README explains
the rest.
- **Logistics Hub:** "Links all storage within the Home Area. Requires power to operate."
- **Drone Input Station:** "Sends items over long distances by drone. Paint it to set its channel. Requires power to
  operate."
- **Drone Output Station:** "Receives items sent over long distances by drone. Paint it to set its channel. Requires
  power to operate."

The buildings container is rebuilt and installed. The build check passes, and the three descriptions were read back
from it.

## 0.15.3 (2026-11-09): Drone Station balance, half the load, double the cost, an energy cost

The user's report on 0.15.2: "they look good and they work well". Then their balance:
- "Drones should be at least half what they carry now. They should cost double to build."
- Energy "would fit the theme and be another cost to them".
- "Milestone 8 seems to fit."

Tested in game by the user the same day: "The power works everything seems fine". The stations' energy shows on the
Energy Meter, so the handler the script adds registers like a built-in one.

Before that test, every check passed:
- the container's build check: the stations' energy rows and costs;
- the Lua check;
- all eight mocked runs, with the drone run extended for energy.

### Changed

- **Load:** 50 kg per trip (was 100), so throughput halves. 200 m: 2.5 kg/s; 1 km: 0.5 kg/s.
- **Cost:** 6 Iron Frames, 4 Iron Electronics and 4 Red Crystals per station (was 3, 2, 2).
- **Energy:** 50 per station on the Energy Meter, scaled by the playstyle (Challenging x2). A linked pair costs what
  a hub costs.
  - Drones only take off while the grid is Energized. A drone in flight finishes its trip.
  - When the meter can't be read, drones fly, and the readout says why.
- **Unlock:** stays at Milestone 8.

### How the stations get an energy cost without one in their template

- **The handler's logic** (`BPC_EnergyHandler`, decoded for this):
  - BeginPlay calls `SetValues`, which reads the owner's `DT_EnergyValues` row by construct name, scaled by
    `PlaystyleSettings.GetScaledConstructEnergyCost`.
  - Unless the owner is virtual, it then binds the save-loaded and playstyle-changed events and, when
    `ActiveOnSpawn` is true (its default), calls `ToggleActiveState(true)`, which runs
    `GameState.Server_RegisterEnergyHandler(self, true)`.
  - EndPlay for Destroyed or RemovedFromWorld unregisters it.
- **Adding it at runtime:** `drones.lua` gives each station one with `AActor::AddComponentByClass(handler class,
  false, identity, false)`, which exists in this build.
  - It does this once per station and world, after checking `GetComponentByClass`.
  - Handlers added this way aren't saved, so the script adds them after every load.
  - A failure is logged once and shown in `hardcore drones`.
- **The builder** (`build_buildings.py`): `drone_stations.energy_handler: "runtime"` gives the stations their
  `DT_EnergyValues` rows without asking the template for a handler. A row is copied from any existing one when the
  template has none.
- **For scale** (`DT_EnergyValues`):
  - Watering Drone Station I / II / III: 20 / 75 / 125;
  - machines at Milestones 7-10: 15-50;
  - Diesel Generator I / II / III: +50 / +250 / +600.

## 0.15.2 (2026-11-09): the Drone Stations restyled after the user's concept art

The user's concept art (made with ChatGPT): "Drone Station - Input / Output" sheets and a third image with a screen
logo, plus two notes:
- "The body should be like the chest body because again this will be painted";
- "make the orange band similar to the one from the chest, so smaller than the concept art".

They picked the third image's symbols as the stations' logo, and reminded me of the hub's lessons: wear, and the
building image (the 128 px wheel icon, a flat logo rather than a 3D one).

Tested in game by the user: "they look good and they work well" (their report on 0.15.3's entry).

The checks that ran before:
- both models exported, after one flicker fix (the logo's arrowhead);
- the cook;
- the container's build check.

### Changed

- **The body is like Storage Box II's chest** (`art/drone_stations/build_station.py`, version 2):
  - the chest's thin orange stripe (2.2 cm) round the housing at lid height, in place of the wide glowing role band;
  - a row of steel bolts above it, and two steel latches with hinges on each long side;
  - the panels keep the game's paint (paintable, Gray unpainted) and get the chest's fine diagonal ribbing.
- **From the concept:**
  - cyan light strips on the base's four corner feet;
  - the drone's body and crate in orange, the crate slatted with dark corners and bands;
  - the rotor guards with a cyan glow ring.
- **The chevrons** are a little smaller and lower, between the port plate and the stripe.
- **The station's logo** on a framed dark screen on the right side (+x), from the concept's third image:
  - a cube (a hexagon with its three inner edges) under an arrow, between two signal arcs on each side, in cyan;
  - the arrow points up on the input station (it sends by drone) and down on the output station (it receives);
  - the strokes are square bars, stepped 2 mm in depth wherever they meet. The arrowhead's two strokes meet at about
    74 degrees: at exactly 90 each stroke's end face lay in the other's side plane, and the exporter's flicker check
    refused it.
- **No logo in the focus panel:** the storage template's focus panel has no icon line to swap. The template chain
  (`BP_Construct` to `BP_StorageConstruct`) holds no icon literal.

### Added

- **`hl_pattern`** in `art/export_model.py`: `"diagonal"` bakes fine diagonal ribs into a part's normal map, like the
  chest's panels.
  - **How:** a sine wave of bands along x + y + z (diagonal on every face of a box), about 2.5 cm apart, through a Bump
    node on top of the bevel normal.

## 0.15.1 (2026-11-09): the Drone Stations' own models

The user's request after testing 0.15.0 ("It works"): start the stations' own models, the drone-pad look planned for
after the transfers worked. Not yet tested in game. The buildings container is installed. The checks that ran:
- both models exported with no coplanar faces;
- the cook, with collision boxes only;
- the container's build check: both meshes retargeted, the template edits, own icons, and every other row the game's.

### Added

- **Two models from one Blender script** (`art/drone_stations/build_station.py`, `ROLE` input or output), each in its
  own `.blend`, started from a copy of the hub's for the same icon camera, light and render settings. Each has:
  - a skid base on an underground plinth, and a housing whose panels are paintable, in a dark frame;
  - a band of light in the role colour, and chevrons: down for an input, up for an output;
  - a port socket where the game's ring sits, a vent grille and an access hatch;
  - a landing pad with a yellow ring, role-coloured beacons and an antenna mast;
  - a cargo drone (white body, four guarded rotors, skids, a wooden crate on straps).

  Each is 1.9 x 1.6 m, about 7,050 triangles, with 2 collision boxes.
  - **Input station:** green, port at the back (where the game's input ring faces).
  - **Output station:** the game's orange, deepened from a first try that read as yellow next to the pad's ring.
- **A `paintable` material kind** in `art/export_model.py`, because the stations' paint is their channel and has to
  show:
  - **Albedo:** a dark primer chipped to bare metal, like the game's own paintable albedo (near-black under the
    mask).
  - **Mask:** baked at 2048 in sRGB, as the game samples it: white on paintable parts, falling off at chips and dirt.
    Models without paintable parts keep the 8 px black mask, so the hub's export is unchanged.
  - **Renders:** icons and check renders show the game's Gray where the mask is (`PAINT_PREVIEW`).
  - **`CHECK_FRAMED`:** frames the check render on a small model.
- **`import_art.py`:** gives a baked mask mipmaps; the 8 px one still has none.
- **`cook_art.py`:** also cooks models named by `drone_stations` buildings.

### Changed

- **Station config** (`mod_config.json`): `model` on both stations.
  - **Rings:** moved onto the sockets with template edits, input `[0, -75, 62]` and output `[0, 75, 62]`.
  - **Interaction box:** scaled to the station (`RelativeLocation [0, 0, 92]`, `RelativeScale3D [2.98, 2.64, 2.9]`).
  - **Why those coordinates:** the rings and the interaction box are children of the StaticMesh component, so they
    are in the model's own space: Unreal cm, Blender `x, -y, z`. Storage Box II's StaticMesh component is turned by
    -90 degrees of yaw, which turns them with it.

### How the game paints a construct (found for this)

- **Material:** Storage Box II's mesh (`SM_MetalChest`) uses `M_Constructs_Paintable_Inst`, an instance of
  `M_Constructs_Paintable`, with the switches `Use Paint` and `Multiply with AO` on.
- **Parameters:** Albedo, Normal Map, ORM Map, Paint Mask and Paint Color. The default Paint Color is the Gray paint.
- **Its textures:** the albedo is near-black where the mask is white, and the mask has worn edges. So the paint
  colour replaces the albedo by the mask, and the AO darkens it.
- **The hub:** its material (a child of `MI_AnimalOverviewer`) has Use Paint on too, but its mask is black.

## 0.15.0 (2026-11-09): Drone Stations, wireless pipes between bases

The user's request: the design doc's Feature 8, "the hardest feature" of this release. Build a Drone Input Station
and a Drone Output Station: pipes feed the input, the items come out of the output.
- **The user's choices:**
  - link stations by paint colour ("it uses the game mechanics, it might be clunky but it fits");
  - every input of a colour feeds every output of that colour;
  - unpainted Gray is a channel;
  - drone trips get slower with distance;
  - Storage Box II copies first, own models later.
- **The user also noticed:** the 0.14.1 hub hiding works.

Tested in game by the user the same day ("It works"):
- an unpainted input and output station passed items between pipe networks;
- painting one of them black stopped the transfers, and with another station painted black too, items went to both;
- an output moved away from the base still received items, more slowly;
- not tried yet: saving and reloading with items in a station.

Before that test, every check passed:
- the container's build check: both stations, their template edits, a save type like Storage Box II's, and the
  Milestone 8 reward;
- the static build and the Lua check;
- the seven earlier mocked runs;
- a new mocked run for the drones.

### Added

- **Two buildings** (`mod_config.json` `drone_stations`, built by `build_buildings.py` like the hub): Drone Input
  Station and Drone Output Station.
  - **Template:** copies of Storage Box II, so the game's pipes and Resource Filter work on them unchanged.
  - **Input station:** `HasOutputPort` off. The storage then registers no output port and hides its mesh. The output
    ring's mesh is also cleared and moved away.
  - **Output station:** its input port moves 100 m underground, as the hub's water connectors did.
  - **Unlock:** Milestone 8 ("Drones & Roads") in every world, from the milestone's rewards and `unlocks.lua` for
    worlds past it.
  - **Build menu:** the pipe group.
  - **Cost:** 3 Iron Frames, 2 Iron Electronics, 2 Red Crystals.
- **`drones.lua`:**
  - **Linking:** stations pair by `AuthPaintColorName`, falling back to `DefaultPaintColorName` (Gray).
  - **Trips:** one drone per input station flies to the same-colour output with the most free room (nearest on a
    tie), taking distance / 20 m/s each way and at least 1 s. It unloads up to 100 kg on arrival.
  - **No loss or doubling:** items are added to the output first (`Server_AddItemStack`), then taken from the input
    in the exact number the output took (`GetNumItemsWithName`). If the input could not give them, they are taken
    back from the output.
  - **Not carried:** liquids.
  - **Host only.**
  - **Finding stations:** through the object table every 15 s, by path in between.
  - **Console:** `hardcore drones`.
- **Template edits can set true/false values now,** and `ClassDefault` names the copy's class default object
  (`legacy_package.iter_tags` points a BoolProperty at its value byte).

### Changed

- **Save type:** new building rows keep their template's `SaveType` unless they are hubs. Storages use type 0, which
  presumably saves their contents. The hub's row keeps type 1, like decorations.
- **Variant family:** new rows get no `VariantFamily`. Storage Box II's would have made the stations variants in its
  wheel entry.
- **Empty tag value:** `empty_tag_value` finds an empty GameplayTag in any row, not only the template's.

### How the game's pipes and storages work (found for this)

- **Pipes:**
  - Native `UPipeSubsystem` routes payloads (Item, Recipe, Liquid) by demand.
  - Machines push their output (`BPC_PipeSendingHandler`).
  - Storages pull what their Resource Filter marks Desired (`UInventoryComponent` `ItemFilterOverrides`, states
    Neutral / Desired / Blocked).
  - A construct receives through `ReceiveItemsFromPipe`.
- **Ports:**
  - `BP_StorageConstruct` owns a native `PipeConnectable` component and the components `InputConnectionPoint` /
    `OutputConnectionPoint`.
  - Each point is a child of its ring mesh, `InputConnectionMesh` (green) / `OutputConnectionMesh` (orange).
  - BeginPlay always registers the input point, and the output point only when `HasOutputPort` is true.
  - The Combustion Generator has only an input port, but its parent burns fuel. The Automated Water Pump has only an
    output port, but it pumps water and must stand in water. So a storage copy is the better template for both
    stations.
- **The retired Automator** (Features.Legacy) moved items wirelessly to up to 10 constructs
  (`UConstructAutomationComponent`: ConnectedConstructIds, bDrivesRemoteConstructs). 1.0 replaced it with pipes.
- **Inventory functions:** `GetAllItemStacks` (FItemStack: Name, Quality, Size, MaxSize), `GetNumItemsWithName`,
  `GetWeightGrams`, `GetMaxWeightGrams`, `Server_AddItemStack(stack, source)`, `Server_RemoveItemStack(stack)`.
  Item weights in `DT_Items` are grams (Wheat 10, Iron Ore 5,000). Water is the only liquid item.
- **Paint:**
  - `BP_Construct.AuthPaintColorName` (replicated and saved) starts as `DefaultPaintColorName`.
  - `DT_Paints` has 20 colours, none free.
  - The mech's paint gun applies them.
- **Storage size without a row:** `SetInputValue` skips a construct with no `DT_StorageCapacities` row. The stations
  keep Storage Box II's 600 kg.

## 0.14.1 (2026-11-09): the Logistics Hub only comes with local storage

The user's report after testing 0.14.0: the doubling works, and switching local storage off did not crash. The game
let full storages stay over capacity (a Wooden Crate at 3,963 / 2,000 kg). But the Logistics Hub was still in the
build menu with local storage off. The user also raised what removing the mod does to a world.

Not yet tested in game. Both the buildings container and the runtime mod are installed, and every check passes:
- the container's build check: the hub row ships with `Features.Legacy`, Milestone 10 ships vanilla, and every other
  row matches the game;
- the static build and the Lua check;
- the six earlier mocked runs, with the unlock run extended;
- a new mocked run for the hub (47 checks): menu, worlds with and without local storage, switches mid-world,
  undo, no duplicate reward, and the `hardcore check` lines.

### Changed

- **The hub belongs to local storage now** (`mod_config.json` `hub.feature = "storage"`). A world loaded with local
  storage off:
  - has no hub in the build wheel;
  - doesn't list or announce it at Milestone 10;
  - keeps any hubs already placed. They still use energy, so recycle them if you play without local storage.
- **How:**
  - The buildings container ships the hub row with the feature flag `Features.Legacy`, and leaves the hub out of
    Milestone 10's `ConstructRewards`.
  - Just before a world with local storage loads, the runtime clears the flag and adds the hub to the rewards. For
    any other world it restores both.
  - Two new kinds of table change do this in `main.lua`: `names` sets a name field, and `lists` adds names to a list
    of names. Both are generated by `build_buildings.py feature_tables` and undone like the others.
  - A switch in a loaded world follows on the next load, like the storage sizes.
- **Unlocks wait for the reload:** `unlocks.lua` now unlocks the hub only in a world loaded with local storage's
  table changes (new `api.isLoadedWith`). Otherwise switching local storage on mid-world would play the "New
  Construct" message for a hub that does not show yet.
- **Settings menu:** local storage's row now has a reload line too, "Save and reload the world to finish applying
  this change.", because its sizes and the hub follow on the next load. Crop trampling's row still has none.
- **Readouts:** `hardcore check` prints the hub row's flag and Milestone 10's rewards. `hardcore hub` says whether
  this world shows the hub.

### How the build wheel hides a building (found for this)

- **The wheel's filter:** `Widget_BuildingsSelectRadial` (`GetConstructsOfType`, `SetupTabData`) shows a
  `DT_Constructs` row only when its `FeatureFlag` is empty or switched on: `HasFeatureFlag(flag) or not
  IsGameplayTagValid(flag)`.
- **Which flags are on:** `GeneratedGame.ini` lists the enabled groups. `Limbo` (cut content), `Legacy`, `Beta` and
  `Zoop` are not among them.
- **Why `Legacy` is safe for placed buildings:** the game hides its retired Automators with `Features.Legacy`, and
  placed ones from older saves still load.
- **Who else reads a construct's flag:** only `BP_FarMechGameState.CheckForRecipeUnlocks` (construct recipes in
  `DT_RecipeUnlocks`, which the hub is not in) and the debug menu.
- **The milestone screens** (`Widget_MilestoneOverviewBase`, `Widget_ResourceDeliveryBase`,
  `Widget_TotalMilestoneTrack`, `Widget_CropDeliveryBase`) list `ConstructRewards` without checking flags. That's
  why the reward has to follow the setting too.
- **The tables stay loaded:** `DT_Constructs` and `DT_DeliveryMilestones` are both in the game instance's import
  graph.
- **The delivery system reads milestone rewards from the table** (`ADeliverySystem.DeliveryMilestonesTable`). It
  keeps no copy, unlike deliveries.

### Removing the mod (looked at, not tested)

- **Safe:**
  - table changes and settings (memory and `worlds.txt` only);
  - full storages (tested above);
  - local storage tags (saves don't keep them);
  - unlock entries for buildings that no longer exist (World 3 kept loading after the test hubs were removed in
    0.13.2);
  - the Workshop Shed (the game's own Blueprint).
- **Unknown: placed Logistics Hubs.**
  - The save keys placed buildings by class (a map whose key is an object property, seen in the 1.0 exe's construct
    loader).
  - The hub's class ships only with the mod. What the loader does with a missing class was not traced.
  - The README now says to recycle hubs and keep a save backup before removing the mod.

## 0.14.0 (2026-11-09): storages hold twice as much with local storage

The user's request: with no shared base inventory, storage room becomes a problem, so double the storages' sizes.
Not yet tested in game. The runtime mod is installed, and every check passes:
- the static build, which verifies every table it rebuilds;
- the Lua check;
- all five mocked runs;
- a new mocked run for the storage sizes (35 checks).

### Added

- **Twice the size for every storage** while local storage is on: Burlap Sacks, Storage Box and Box II, Wooden
  Crate, Barrel, Small Shed, Storage Shed and Shed II, and Silo I–III (`mod_config.json`, `DT_StorageCapacities`,
  `"MaxWeight": "x2"`). For example, the Storage Box goes from 150 to 300 kg and Silo III from 25,000 to 50,000 kg.
- **Left as they are:**
  - silos' one-item-type limit (a Blueprint setting);
  - the storage trailers;
  - the generators (fuel) and feed troughs;
  - the obsolete Automators.

### How the game sizes a storage (found for this)

- **The table wins:** each storage Blueprint has a size of its own (the `MaxWeight` of its Input and Output
  inventories), but the game overwrites it on every load. The storages' parent class, `BP_ConstructHandler`,
  calls `SetInputValue` from BeginPlay. That function reads the construct's `DT_StorageCapacities` row and calls
  `Input.Server_SetMaxWeight`, on the host only.
- **Evidence:** some Blueprint sizes are older numbers than the table's (Storage Shed II 3,000 kg, Silo III
  15,000 kg), and the game shows the table's.
- **So placed storages grow too.** The build menu's capacity line reads the same table.
- **The table stays loaded:** the game instance's import graph reaches it, so it stays in memory for the session.
  Editing it before a world loads is safe.
- **The Input inventory is the one that counts:** `GetStorageInventory` returns it, and the weight limit is
  `Input.MaxWeight`.
- **How this was read:** a small disassembler for the cooked Blueprint bytecode. It needed one size fix: a name
  in the script takes 12 bytes in memory and 8 on disk.

### Changed

- **A live feature can own tables now** (`build_mod.py`, `main.lua`). Local storage owns `DT_StorageCapacities`.
  - **When it applies:** the table changes just before a world loads, like every table. Switching local storage
    in a loaded world applies the storage rule at once and the sizes on the next load.
  - **Messages:** the console says to reload, and the log line says the table changes follow.
  - **Settings menu:** local storage's row still has no reload line.
- **The playstyle card's description** adds "(storages hold twice as much)".

## 0.13.2 (2026-11-09): the Logistics Hub's final cost, and the test versions are gone

The user approved 0.13.1 in game ("better than expected") and asked to finalize the hub. The build verifies and is
installed, the buildings container and the runtime mod both.

### Changed

- **Cost:** 10 Steel Frames, 10 Iron Electronics and 20 Concrete, the cost planned since 0.10.0, in place of the
  1 Wood used while testing. The build checks every item against `DT_Items`.
- **Logistics Hub II and III removed.** They borrowed the cut Workshop Shed and Barn to test more buildings in one
  wheel (0.10.3); the wheel coped. The user's saves were checked first: no save has either one placed (World_3 has one
  Logistics Hub, and II and III only in its unlock list), so no placed building loses its class. The build menu, the
  milestone reward and `hardcore hub` now list the one hub.

## 0.13.1 (2026-11-09): the hub's own status line, and an energy cost that scales with the playstyle

0.13.0's test (the user):
- **What worked:** the style "does feel like part of the game now"; no flickering; the hub works, validated in game.
- **Water line:** the focus panel still showed the reservoir's water line, "0/0L (Pumping 0.5L/s)".
- **Energy:** the cost read 400 instead of 200.

### Changed

- **Energy cost 100 at Balanced.** The 400 was the game's playstyle setting "Construct Energy Costs"
  (`DT_PlaystyleSettings` ConstructEnergyCost: Balanced ×1, Relaxed ×0.5, Creative ×0, Challenging ×2). It scales
  every machine's cost the same way, and the user's world is Challenging. The user chose 100 at Balanced, so 200 on
  Challenging; Relaxed and Creative show 50 and 0. The Energy Meter `storage.lua` reads is already scaled.
- **"Securing base logistics" on the focus panel**, with the hub's logo sign as its icon, in place of the reservoir's
  water line.
  - **Where the line comes from:** the reservoir's `StatusConditions` builds it from a string-table text
    (`CommonWords/AmountAndPumpingFormat`, shared with every reservoir, so the table can't change) and a soft path
    to `T_WaterIcon`.
  - **`function_edits`** (`build_buildings.py`) swaps both in the hub copy's bytecode without moving any other byte:
    - **The text:** the string-table literal becomes our own text literal of the same in-memory size (91 bytes).
      Jump offsets count in memory. On disk it is 4 bytes longer, because the old one held a 4-byte package index
      for an 8-byte pointer, so the function's serialized script size grows by 4. In memory 2,421 bytes, on disk
      3,837 → 3,841: since 4.25 a property reference is a 16+ byte field path on disk and an 8-byte pointer in
      memory. The script-size fields are found by their arithmetic (the script must end, on `EX_EndOfScript`,
      exactly where the function's last 12 bytes begin).
    - **The icon:** the soft path becomes `/Game/HardcoreLogistics/Art/T_HubIcon.T_HubIcon`, exactly as long as the
      water icon's.
  - **Tested offline:** only the two size bytes and the two literals change, and no other export.
  - **Verify:** reads the packed Blueprint for the new literals and the absence of the old ones.
- **The status icon:**
  - **Look:** a flat golden drone carrying a crate, like the game's own status-line glyphs. The game's coloured ones
    (for example `EnergyIconCOLOR`) are one flat yellow, sRGB about 255, 186, 8, with soft edges and no outline.
    `art/logistics_hub/status_icon.py` draws it in plain Python: 128 px, 8× supersampled, on transparent.
  - **Earlier version:** the first one, a 3D render of the hub's logo sign, stood out next to the game's flat icons
    (the user, testing it). `export_model.py` no longer renders status icons.
  - **Cook:** `cook_art.py` cooks it straight into `/Game/HardcoreLogistics/Art`, set like the game's T_WaterIcon:
    default compression, one mip, never streamed.
- **Tested in game:** the focus panel reads "Logistics Hub", "−200 Energy" (Challenging) and "Securing base
  logistics" with the flat drone-and-crate icon, and the hub works. The user: "the whole thing turned out better than
  expected".

## 0.13.0 (2026-11-09): the hub runs on energy, is built on the Water Reservoir, and wears like the game's buildings

Not yet tested in game. The build verifies and is installed: the buildings container, plus the runtime mod for the
energy rule. The Lua check passes, and so do all five mocked runs, the local-storage run with new energy cases.

0.12.1's test (the user):
- **What worked:** the building works, has collision now, and the recycle tool selects it.
- **E action:** the "Open" action (the Water Tower's leftover machine menu) left the building "in use", and then it
  could not be recycled.
- **Look:** the colours were too flat next to the game's worn assets (compared with the cannon).
- **Flicker:** parts of the model flickered (the user's guess: shapes sharing a surface).
- **Requests:** wooden crates like the game's; base the hub on the Water Reservoir, which has no E action; and give it
  an energy requirement of about 200.

### Changed

- **Built on the Water Reservoir instead of the Water Tower.** The reservoir is a plain `BP_Construct` child: no
  machine menu, so no E action and no "in use" lock. It also carries the game's energy handler (`BPC_EnergyHandler`).
  Its water parts are switched off by rewriting values its components already set, in place (the new
  `template_edits`):
  - **Meshes cleared:** the water surface, the silo foundation it borrows, and both pipe connectors (with their pipe
    attach points, moved 100 m underground).
  - **Water-gun capsule:** shrunk to 1 cm and moved 100 m underground.
  - **Tank:** 0.01 L, so no rain collection and nothing for drones or pipes. Not 0, which its Blueprint might divide
    by.
  - **Mesh swap:** found through the template's StaticMesh component override, since the reservoir imports five
    meshes. A check makes sure no other component shows the same mesh.
  - **Placement:** the reservoir has no custom placement box, so the hub places by its own collision boxes, and the
    12 cm shift for the Water Tower's off-centre box is gone.
- **Energy: the hub uses 200 and only works while the grid is Energized.** How the game's energy works, from its
  Blueprints and tutorial text:
  - **The meter:** `BP_FarMechGameState.EnergyStatus` (Available, Used) is one Energy Meter for the whole world. Every
    building with a `BPC_EnergyHandler` registers its cost, read from `DT_EnergyValues` by construct name (for
    example the Water Reservoir 25, Auto Water Pump 250, Drone Station III 125; generators make 50 / 250 / 600, the
    Free Generator 1500).
  - **Energized:** at 0 or above every machine with a cost is Energized (crafting 2.5× faster, pumping and drones 2×).
    Below 0 the grid is Overloaded and they run at normal speed.
  - **The hub's cost:** `build_buildings.py` adds a `LogisticsHub` row (200) to `DT_EnergyValues` (new `energy`
    option) and sets the handler, so the meter counts the hub like any machine.
  - **The rule:** `storage.lua` lets a hub with an energy cost link its base only while available − used ≥ 0. When the
    grid flips it logs "the grid is Energized/Overloaded". When the meter can't be read, hubs keep working.
  - **Console:** `hardcore hub` prints the meter ("available A, used U, so +N: Energized ..."); `hardcore storages`
    and the readout add it.
- **The model, version 3** (`build_hub.py`):
  - **Crates:** wooden crates in the game's own style replace the blue and orange ones: a dark frame (corner posts,
    top and bottom rims), recessed planks, a diagonal brace on each side, bolts, and a dark core behind the plank gaps.
  - **Plinth:** a plinth 1 m under the ground fills the gap on slopes, now that the reservoir's foundation mesh is
    off. It stays out of the icon.
  - **Size:** 402 parts, 16,924 triangles.
- **Worn textures, baked** (`export_model.py`): the flat palette is gone. The merged mesh is unwrapped (Smart UV
  Project) and its materials are baked in Cycles at 2048 px, on the GPU (OptiX) while baking only. The bake shaders:
  - **paint** (`hl_kind`, with `hl_wear`): colour blotches; edges chipped down to bare metal, found where a 5 cm
    bevel normal leaves the true one, so modelled bevels count; scattered small chips; crevice grime (ambient
    occlusion within the mesh); dirt rising from the ground.
  - **metal:** blotches, brighter edges, grime and dirt.
  - **wood:** grain along each part's longest side (a corner colour carries the axis), and lighter worn edges.
  - **glow and screen:** clean.

  The textures: albedo; ORM (occlusion, roughness, metallic); glow; and a tangent-space normal map with the rounded
  edges, green down for Unreal. Unreal imports them like the game's construct textures (default compression with
  mipmaps), and takes the mesh's own tangents so the normal map lines up. The icon is rendered from the baked mesh.

### Fixed

- **Flicker** (z-fighting): faces of different parts in the same plane, facing the same way and overlapping. The game
  draws them at the same depth.
  - **The check:** `export_model.py` now refuses an export with any such pair over 1 cm². It buckets faces by plane
    and clips each candidate pair (Sutherland–Hodgman). It was proven on a synthetic case after its first version
    found nothing: an inverted shoelace sign.
  - **What it found in 0.12.1:**
    - each crate's lid band flush with the crate's top;
    - the canopy trim flush with the roof edge;
    - the corner bumpers, tower rings, crate rims, pipe caps and flanges, dish feed arm, and hut corner posts flush
      with their neighbours;
    - the new crate braces, which my `bar()` helper had turned 90°: Blender's track quaternion turns the "up" axis
      to world Z.

    All 160 pairs are fixed, and the model passes.

### Found on the way

- **Long MCP calls:** a Blender MCP call times out after about a minute, while the script keeps running. The 2048 px
  bake takes about 1.5 minutes, so the export now runs from a Blender timer and finishes on its own.
- **Python reach:** UE 4.27's Python can't reach `UNavCollision`'s settings: only `NavCollisionBase` is exposed and
  `NavCollisionBox` is missing. This doesn't matter, because the game never finds this engine's nav data under its own
  format name and falls back to the physics boxes.

## 0.12.1 (2026-11-09): the hub's second model, after the concept art; real collision, glow, and a game-sized icon

Not yet tested in game. It builds, verifies and is installed (only the buildings container changed).

0.12.0's test (the user): the mesh looks good, and the building works and looks as advertised. Three problems:
- **No collision:** the player walked through the walls.
- **No selection:** the recycle tool could not select the hub to remove it.
- **Wheel icon:** the build-wheel picture looked odd, spilling out of its circle.

The user also asked for a model after a ChatGPT concept art ("Logistics Station"), taking elements from it.

### Fixed

- **Collision, and selecting the hub:** the game runs **Chaos physics**.
  - **Evidence:** its Water Tower mesh's cooked collision is Chaos-serialized. It opens with a float-size field, 4,
    then implicit-object type 8 (convex), then raw floats matching the hull bounds. Its package names include
    `NavCollision_Chaos`.
  - **Cause:** Unreal 4.27 cooks PhysX data, which the game cannot read. The hub's convex hulls therefore never became
    shapes, so the player had nothing to collide with and the recycle tool's trace had nothing to hit.
  - **Fix:** collision is now six boxes (`UBX_`): platform, hut and roof, canopy, tower, pipes, sign. A box is plain
    numbers the game builds into a shape itself. Traces use the same boxes (`CTF_UseSimpleAsComplex`), and so does the
    navmesh, which takes the physics collision when the mesh's nav data isn't in the game's format.
  - **Patch:** 4.27 still writes an empty 25-byte PhysX header into every cooked mesh. `cook_art.py` clears
    `bHasCookedCollisionData` and drops it, so the game takes its own path for a mesh without cooked data. It refuses
    a mesh whose cooked collision holds any shape.
- **Wheel icon:** the wheel shows icons at their texture size, and the game's are 128 px; 0.12.0's was 256, so it showed
  at twice the size. The icon is now 128 px, framed to fill the square (lens shift centres it) and rendered 0.6 stops
  brighter, like the game's.

### Changed

- **The hub's model, version 2** (`art/logistics_hub/build_hub.py` rebuilds it in Blender from code; version 1 is
  kept in the `.blend`'s excluded `Archive_v1` collection). It takes these elements from the concept:
  - a dark metal platform with plates, corner bumpers and cyan light strips;
  - a blue hut with orange base and top bands and dark corner posts;
  - a framed screen with a glowing drone-and-crate logo, between double chevrons, under an orange awning;
  - a louvred side vent, a back grille, and a side door towards the crates;
  - a two-tier roof with the orange logo sign, a vent row and a corner beacon;
  - a lattice tower with an orange top, an orange beacon and a white dish with an orange feed;
  - an open canopy with a sloped roof over a shelf of blue and orange crates;
  - blue pipes with orange couplings and a valve beside a cyan indicator.

  It has 275 parts and 11,624 triangles, with bevelled edges shaded smooth. It is 12 cm off centre like the Water
  Tower's placement box, so it stays inside it (Unreal y −208…184 cm against the box's −213…188).
- **Glow:** the material's parent is now the game's `MI_AnimalOverviewer`. It is the same construct master as the
  Water Tower (masked, with paint), with "Use Emissive" on and no blinking (the Assembler's material blinks). A fifth
  palette, `T_<M>_Emissive`, lights the cyan strips, the logo, the beacons and the screen's faint teal. `Emissive Color`
  is set to white.
- **Blender export:** smooth shading with edges sharper than 35° kept hard. It refuses `UCX_` (convex) collision.

## 0.12.0 (2026-11-09): the Logistics Hub has its own model, made in Blender

Not yet tested in game. The build verifies and is installed (only the buildings container changed; the runtime mod is
the same). The first run of the whole flow: Blender model → Unreal 4.27 cook → the game's build wheel.

### Added

- **The Logistics Hub model** (`art/logistics_hub/LogisticsHub.blend`):
  - **Look:** a blue control hut on a wooden deck, with a crate rack, a pipe manifold, and a lattice mast with a dish
    and a beacon.
  - **Size:** 92 parts, 4,888 triangles, 3.9 × 3.9 m and 6.5 m tall: the Water Tower's slot, whose placement box and
    interaction area the hub keeps.
  - **Collision:** 5 boxes (deck, hut, rack, pipes, mast).
  - **Icon:** its own build-menu icon, a 3/4 render on a transparent background like the game's (checked against the
    decoded Water Tower and Barn icons).
- **`art/export_model.py`** (runs in Blender):
  - Merges a model's parts into one mesh with one material slot.
  - Writes the colours as a 4 × 4 palette texture plus a roughness/metallic one; each face's UVs sit inside its
    material's cell.
  - Exports the FBX with the collision boxes, and renders the icon.
- **`tools/cook_art.py` and the art project `unreal/HLArt.uproject`** (Unreal 4.27.2, the game's version, at
  `D:\UE_4.27`):
  - **Run:** one command imports the exports (`unreal/Scripts/import_art.py`, through the Python commandlet), then
    cooks them for WindowsNoEditor, unversioned. A clean run takes about 10 s.
  - **Material:** a child instance of the game's own `MI_WaterTower` that swaps its four textures (Albedo, Normal Map,
    OcclusionRoughnessMetallic Map, Paint Mask, black). The hub therefore uses the game's compiled masked/paint
    shader, and no shader code ships.
  - **Stand-ins:** to cook against it, the project holds stand-ins at the game's paths, which are never copied.
  - **Reference check:** everything the cooked packages reference outside the mod's folder must exist in the game:
    `MI_WaterTower` and its four `T_WaterTower_*` textures.
- **`build_buildings.py`, the `model` option:**
  - Points the Blueprint copy's one static-mesh import (and its package) at the model (`LegacyPackage.set_import_name`).
  - Sets the row's `Icon`.
  - Packs the cooked art.
  - Checks:
    - The verify step reads the Blueprint's zen import map (CityHash64 import IDs, checked against the game's own
      values) to confirm the swap.
    - The container is refused if it holds anything outside `/Game/HardcoreLogistics` besides the two tables.
    - It warns when the art changed after the last cook.

### Found on the way (Unreal 4.27 Python)

- **`-script=` and spaces:** the commandlet splits the path at spaces and then runs the pieces as Python code, so
  `cook_art.py` runs a copy of the script from a temp folder.
- **The texture-override setter:** `MaterialEditingLibrary.set_material_instance_texture_parameter_value` returns
  False even when it works. The overrides are checked in `TextureParameterValues` instead. Without them the hub would
  show the Water Tower's textures in game.
- **Units:** Blender's FBX declares metres (`UnitScaleFactor` 100). Without `convert_scene_unit` the importer reads
  them as centimetres, which made the first import 4 cm wide. The import now fails on a wrong scale.
- **Logging:** `unreal.log` lines only reach stdout with `-FullStdOutLogOutput`.

## 0.11.2 (2026-11-09): local storage checks only when a menu or station asks; trampling finds mechs cheaply

Tested in game: smooth, no stutter noticed. Passes the Lua check and all five mocked runs; the local-storage run is
rewritten around requests. The timing log of that session:

| Work | Runs | Average | Longest |
|---|---|---|---|
| Local storage update, on a request from a menu or station | 12 in about 3 minutes | 30.7 ms | 38 ms |
| Trampling check, every 100 ms | 2,081 | 0.24 ms | 6 ms |
| Building unlock check and local storage loop, every 1000 ms | 215 each | 0.01 ms / 0.00 ms | 1 ms |
| Settings rows scan (500 ms) and playstyle card poll (150 ms), menus | 428 / 1,403 | 0.22 / 0.08 ms | 4 / 1 ms |

- **The hooks fire in game:** the tags change with "N m from the spot the game asked about".
- **The stutter, explained:** one local-storage update costs about 30 ms. 0.9.0–0.11.1 ran it every 500–1000 ms,
  inside game frames, which was the stutter. Now it runs only when a menu or station asks.
- **Still to do:** where those 30 ms go is not measured yet. Likely candidates are the native
  `GetConstructsOfClassInArea` calls, one for storages and one per placed hub class, in a big base, and UE4SS
  handling the 41 storages. Cutting it would make opening a menu hitch-free too.

### Changed

- **Local storage runs only when a menu or station asks for the base inventory** (the user's idea: you only take
  things out of the base by interacting with a station).
  - 46 Blueprints ask `UMultiInventoryHandler::GetReachableInventoryContainer` first, and 12 use
    `ListenToReachableInventoryContainerAt`. They cover every crafting and conversion menu, the build menu and
    holograms, deliveries, upgrades, the storage menus, NPC collections, and the HUD's pinned recipe.
  - Hooks on both functions apply the rule just before the game reads the storages, measured from the spot it asks
    about (the station, the build spot, the cannon), not from the player. The native code that follows (the craft,
    the delivery) uses the same tags.
  - The same spot asking again is checked at most every 3 s, so a menu that asks every frame costs only a count; a
    spot 2 m away is checked at once. Nothing runs between requests.
  - The loop that remains only notices the feature being switched off, and touches no game object otherwise.
  - The check for tags a save kept is gone: saves don't keep them (0.9.0 test).
- **Trampling searches the object table for mechs once a second instead of every 100 ms**, and finds them by path
  in between. A new mech (a player joining, a respawn) is caught at once through UE4SS's `NotifyOnNewObject`.
- **The timing log** now logs a slow run at most every 10 s per loop (was every minute, which hid every slow run
  after the first one in a short session). Work a hook starts is timed too: `api.recordTiming` shows in
  `hardcore timing` as "(when asked)".

### Tested in game (0.11.1)

- Still a stutter. The only timing line was the local storage check's first run, 17 ms, on the splash screen.
  The once-a-minute limit hid any later slow runs.

## 0.11.1 (2026-11-09): no more stutter every half second; every script loop is timed

Tested in game: the stutter remained (see 0.11.2). Passes the Lua check and all five mocked runs (with new cost checks).

### Fixed

- **A stutter every second and every half second (0.11.0 test).** The script loops run inside game frames. Two of
  them did expensive lookups on every run.
  - **Every second, the building unlock check** asked `getActiveSlot()` whether a world was loaded. That calls
    `FindFirstOf` for several classes, and each call walks the game's whole object table until it finds one. It now
    uses `main.lua`'s own world-loaded flag (`api.worldLoaded`), which costs nothing.
  - **Every half second, the local storage check:**
    - It searched the whole object table twice (`FindAllOf` for the players and the home areas).
    - For each of World_3's 41 storages it built full names and class names, read the tag array and the location.

    Now it searches only every 10 checks and finds the players and areas again by their paths in between
    (`StaticFindObject`, a quick lookup). It remembers each storage's name, class, place and tags, keyed by its
    address, and reads them again every 30 checks; it keeps the tags it writes up to date. It runs once a second
    (`storage.check_ms` 1000, was 500).
  - **`hardcore storages` and `hardcore hub`** still read everything fresh.
- **The buildings container was not the cause**, so it stays: it adds rows and assets and runs no code. Removing it
  would also drop the placed Logistics Hubs from World_3 the next time it saves, since their class would be
  missing.

### Added

- **Every script loop is timed.**
  - A run of 8 ms or more is logged with its length, at most once a minute per loop.
  - `hardcore timing` lists each loop: its interval, runs, average, longest and last run, and how many took 8 ms or
    more. `hardcore timing reset` clears the counters.

### Tests

- **Storage mock:** in 20 checks, only 4 full searches; a storage's place is read again only after 30 checks;
  moving still updates at once; a demolished storage leaves the list at once; a base that is gone triggers a new
  search.
- **Unlocks mock:** the check never calls `getActiveSlot`.
- **Main mock:** a 12 ms run is logged once, and `hardcore timing` lists it.

## 0.11.0 (2026-11-09): the Workshop Shed is back; one place unlocks the mod's buildings

Tested in game: the Workshop Shed unlocked and was built. Found a stutter every second and every half second,
fixed in 0.11.1. Passes the Lua check, all five mocked runs (a new one for the unlocks) and the
buildings build's own check: apart from the changes below, every row of both tables still matches the game's.

### Added

- **Workshop Shed, the game's own cut building, made buildable.**
  - Unlock: Milestone 1, the first delivery, alongside the Oil Presser.
  - Build menu: the Constructs tab, in the Oil Presser and Seed Extractor's group.
  - Cost: 10 Wood and 5 Stone.
  - Why: the first machines get a quick home without building one from scratch.
  - Its row loses the `Features.Limbo` flag and gets the name "Workshop Shed" (was "Workshop Shed WIP"), a
    description and the cost. It keeps the game's Blueprint, so placed sheds stay valid even without the mod. It is
    in every world.
  - A mod on Nexus does the same, and it is credited in the Nexus description.
- **`unlocks.lua`** unlocks the mod's buildings in worlds already past their milestone, once the world's milestone
  count is known.
  - The Workshop Shed unlocks in every world; the Logistics Hubs only in worlds with local storage on. Switching
    local storage on looks again.
  - `hardcore unlock` lists each building: whether it is unlocked, its milestone, and its build-menu row.
  - `hardcore unlock all` (or a row name) unlocks them now.

### Changed

- **Renames:** the buildings container is now `HardcoreLogisticsBuildings_P`, built by `tools/build_buildings.py`
  (was `HardcoreLogisticsHub_P` and `build_hub.py`). Installing removes the old container.
- **Cut buildings:** a new `cut_buildings` section in `mod_config.json` restores the game's own hidden rows, next
  to `hub` for new buildings. Each building may have its own milestone.
- **Hubs:** `storage.lua` no longer unlocks the hubs itself; `hardcore hub unlock` asks `unlocks.lua`.

### Tested in game (0.10.3)

- All three hub versions show in Constructs → Storage, in the right spot, with the right names.
- The Workshop Shed and Barn bodies show no interaction prompt when looked at. They are walk-in workshop buildings
  with no interactable part; the Water Tower has one, which is where its "(Busy)" comes from.

## 0.10.3 (2026-11-09): three Logistics Hub versions, to test more buildings in one wheel

Tested in game: all three appear in the Storage wheel, correctly placed and named. Passes the Lua check, all four mocked runs and the hub build's own check: every
other row of both tables still matches the game's.

### Added

- **Logistics Hub II and III**, as a test of how the build wheel copes with more buildings than the game ships. All
  three versions are in Constructs → Storage, so that wheel holds 12 entries instead of 9 plus one. Each version
  is its own class, row, icon and unlock, at a cost of 1 Wood.

  | Version | Body (cut construct) | Its Blueprint |
  |---|---|---|
  | Logistics Hub | Water Tower | no code of its own, 12 exports |
  | Logistics Hub II | Workshop Shed WIP | no code, 24 exports |
  | Logistics Hub III | Barn WIP | its own event graph (begin play, built, destroyed, demolish), interior volumes and audio zones; 72 exports, so the most likely to misbehave |
- **Any of them is a hub:** each makes its base's storage count from anywhere in the base.
- **Console:** `hardcore hub` lists each version's unlock, build-menu row and class; `hardcore hub unlock` unlocks
  all of them.

### Changed

- **`mod_config.json` `hub`** now holds a `buildings` list: row, template, display name, description and cost per
  building, sharing one milestone.
- **`menu_group_from`** sets every new row's build-menu tab and group. The Barn's and Workshop Shed's rows sit in a
  different group, so without it they would land elsewhere.
- **`build_hub.py`** loops over the buildings and verifies each one: class, row, icon, group, milestone reward.

### Fixed

- **The automatic unlock gave up too early.** Right after a world loads, the delivery system reports 0 milestones,
  and 0.10.0–0.10.2 settled the question on that first look ("not yet: 0 of 10" in the log). Now a count of 0 or
  none means "not known yet", and it looks again 20 checks (10 s) later.

### Tested in game (0.10.2)

- The hub is in the Constructs → Storage wheel. Unlocking it plays the game's own "New Construct" animation. It can
  be placed and built.
- **Small issue:** looking at it shows "(Busy)" under its name. That comes from the Water Tower Blueprint it is
  copied from.
- The storage effect still needs a `hardcore storages` next to a built hub: the log has no readout after the hub
  was built.

## 0.10.2 (2026-11-09): the hub costs 1 Wood while testing

Tested in game: the hub was built for 1 Wood.

### Changed

- **Cost:** the Logistics Hub costs 1 Wood for now (`hub.cost`). World_3 has no steel yet, so the hub could be
  placed but not built. The intended cost, 10 Steel Frames, 10 Iron Electronics and 20 Concrete, is kept in
  `hub._cost_note`.
- **Check:** `build_hub.py` now refuses a cost item that is not a row of `DT_Items`.

## 0.10.1 (2026-11-09): the hub unlock no longer refuses wrongly

Tested in game: `hardcore hub unlock` unlocked the hub, and it could be placed in World_3. Passes the Lua check and
all four mocked runs.

### Fixed

- **`hardcore hub unlock` refused with "the hub's container ... is not installed"**, although the container was in
  `~mods` (0.10.0 test in World_3, at 9 of 10 milestones).
  - **Why:** the check used UE4SS's `LoadAsset`, which looks assets up in the game's asset registry. That registry
    ships with the game and lists no package a mod adds. The game itself loads a construct's class by its path, so
    the check was wrong, not the container.
  - **Now:** it checks whether `DT_Constructs` has the `LogisticsHub` row, which comes in the same container.

### Added

- `hardcore hub` says whether the build-menu row is in `DT_Constructs`. If it is missing, the game did not mount
  the hub's container.

## 0.10.0 (2026-11-09): Logistics Hub, a new building (Water Tower look for now)

Installed, not yet tested in game. Passes the Lua check, all four mocked runs (the local-storage run now covers the
hub), and the hub build's own check: it reads the finished container back, and every other row of both tables must
match the game's.

### Added

- **Logistics Hub, a new building in the build menu.**
  - Where: the Constructs tab, with the storage buildings.
  - Cost: 10 Steel Frames, 10 Iron Electronics, 20 Concrete.
  - Unlock: Milestone 10 ("Steel Technology"), in the milestone's own reward list.
  - Effect: with local storage on, every storage in a base holding a hub counts from anywhere in that base, as in
    vanilla. Other bases stay local. Demolishing the hub makes the base local again.
  - Look: for now, the game's cut Water Tower. The model made in Blender replaces it next.
- **Unlocking in existing worlds.** A world past Milestone 10 never sees that reward, so with local storage on it
  gets the hub when it loads.
- **Console:**
  - `hardcore hub` shows whether the hub is unlocked, the milestones done, and the hubs placed.
  - `hardcore hub unlock` unlocks it now, whatever the milestones, to try it out.
  - `hardcore storages` and `hardcore check` say which bases have a hub.
- **`tools/build_hub.py install`** builds the building into its own container, `HardcoreLogisticsHub_P` in
  `Paks/~mods`. It needs retoc (`modding_tools/retoc` next to the repo).

### How the building is made

- **retoc** converts three packages from the installed game to the older legacy package format:
  - the template construct's Blueprint (`hub.template`: the Water Tower);
  - `DT_Constructs`;
  - `DT_DeliveryMilestones`.

  It reads a temporary folder of hard links to the game's own containers only, so an installed copy of this
  container is never read back.
- **The Blueprint copy** (`tools/legacy_package.py`) renames:
  - the package, to `/Game/HardcoreLogistics/Constructs/BP_LogisticsHubConstruct`;
  - its class and class default;
  - its `ConstructName`, to `LogisticsHub`.

  Imports, exports and their data refer to names by index, so only the name map and the header offsets change. The
  Water Tower's Blueprint has no code of its own, only parts and settings.
- **The new row** (`tools/legacy_table.py`) starts as a copy of the Water Tower's. Its name, texts, class, cost and
  save type change, and the `Features.Limbo` flag that hides cut content is dropped. Its category, wheel group and
  icon stay the Water Tower's.
- **The milestone:** `Milestone10.ConstructRewards` gets `LogisticsHub`.
- **Packing:** retoc packs the three packages back (UE 4.27).

### What we learned about the game

- **Saves keep placed constructs by Blueprint class path**, not by build-menu row (checked in `World_3.sav`, a
  zlib stream after a 20-byte `FarMech!` header). So a new building needs its own class: a new row reusing an
  existing Blueprint would come back as the old building after a reload.
- The same save, made with local storage on, holds no `NoRemoteInventoryAccess`, which confirms the tags aren't
  saved.
- **A construct's identity is its Blueprint:** the class default's `ConstructName`, returned by
  `AConstructBase::GetConstructName`.
- **Cut buildings with real art are still in the files**, behind `Features.Limbo`: Water Tower, Barn, Workshop
  Shed, and the homestead variants.
- **Unlocking:** `AFarMechGameStateBase::Server_UnlockConstruct(FName)` unlocks a construct, and
  `AcquiredConstructBlueprints.Constructs` lists the unlocked ones.
- **retoc v0.1.5** round-trips the game's packages faithfully: same exports, properties and public export hashes.
  Only the header layout differs from the game's cooker.

### To check in game

- After `hardcore hub unlock`: the hub is in the Constructs tab and can be built, with its cost taken.
- It survives save and reload.
- Its base's storages count from anywhere in the base (`hardcore storages`), and demolishing it makes the base
  local again.
- The Milestone 10 screen lists it.

### Known

- The Milestone 10 reward is in every world, vanilla ones too, since a pak can't tell worlds apart. In a world
  without local storage the hub does nothing.
- Its name and description are English only: they aren't in the game's translations.

### Tests

- The local-storage mock run now covers:
  - a base with a hub: all its storages count, a storage listed by two bases counts too, and base 2 stays local;
  - demolishing the hub;
  - no unlock before the milestone (logged once);
  - the unlock for a world past it (once, and not again after a reload);
  - the hub container not being installed;
  - `hardcore hub` and `hardcore hub unlock`.

## 0.9.0 (2026-11-09): local storage

Tested in game: it seems to work. No errors and no crash. Passes the Lua check, the new local-storage mock
run and the three existing mocked runs. What the log shows:

- Switched on from its Settings row in World_3, it found 40 storages in the one base. 5 were generators and
  were left alone.
- UE4SS took the tags as a Lua table on the first try.
- After quitting to the menu and reloading, none of the 35 tagged storages still carried the tag. So the save
  does not seem to keep it.
- The 15 m reach stays.

### Added

- **Local storage (feature `storage`, settings row "Hardcore Local Storage").** A storage counts for crafting,
  building, deliveries and tasks only while a player is within 15 m of it (`storage.reach_cm`), measured flat
  from the mech, or from the pilot on foot. Further away it is left out of the base inventory until someone
  comes back.
  - It is off in existing worlds. Switch it on with its row in the Settings menu or `hardcore storage on`. The
    Hardcore Logistics card switches it on for new worlds.
  - `hardcore storages` lists the storages in each base, nearest first, with their distance and whether they
    count. `hardcore check` sums it up.

### What we learned about the game (from the exe)

- **How the shared base inventory works.** Everything that uses "the base inventory" calls
  `UMultiInventoryHandler::GetReachableInventoryContainer(player, location)`.
  - It returns the mech's inventory plus, when the location is inside a home area, every storage construct in
    that area (`MultiInventorySettings.StorageConstructClass`, `BP_StorageConstruct`), nearest first.
  - Outside home areas it returns the mech's inventory alone.
  - "Inside" is a shape test against each base's home area (`AHomeAreaManager::GetHomeAreaAt`).
- **Native code calls it 15 times:** crafting, quick craft, deliveries, task progress, NPC collection turn-ins
  and chip crafting. A Lua hook on the function would only catch the calls from Blueprints.
- **The game already has an off switch per storage.** The function skips any storage whose actor has the tag
  `NoRemoteInventoryAccess`.
  - In vanilla only the generators (`BP_EnergyGeneratorPARENTConstruct`) carry it, so their fuel stays out of
    the base inventory.
  - Actor tags can be written from Lua, so this needed no native hook, although the roadmap had expected one.
- `MultiInventorySettings.MaxDistanceToStorageConstructs` (5500 in DefaultGame.ini) is not used by this
  function.
- Each base's `BP_HomeAreaComponent` lists its constructs through `GetConstructsOfClassInArea(Class)`, the same
  call the inventory code makes. The mod uses it to list storages.

### How it works

- **Every 500 ms** the script:
  - finds the players through their controllers' pawns;
  - lists the storages in each base;
  - tags every storage further than `reach_cm` from every player, and untags it once a player comes within
    reach.
- **Edge:** a storage already in reach leaves only past `reach_cm` + 1 m, so standing at the edge doesn't flip
  it every check.
- **Untouched:** generators, whose class default carries the tag. Switching the feature off removes every tag
  the mod gave; a storage's other tags stay.
- **Writing tags:** the script sets the actor's `Tags` array from a Lua table (this UE4SS build can set an array
  property from a table). If that is refused, it copies an array that already holds the wanted tags. After 5
  failed writes, with none that worked, it stops and says so in the log.
- **Save check:** when a world loads, the log names every storage that already carries the tag without being a
  generator. That would mean the save keeps the tag. With the feature off, those tags are taken off.

### Still to check in game

- Whether a menu that is already open updates when you walk up to a storage.
- Co-op.

### Tests

- New mock run (`smoke_storage.py`), with UE4SS-style `TArray` tags. It checks that:
  - storages past 15 m are tagged and a storage's own tags are kept;
  - the generator is never written;
  - a storage listed by two bases counts once;
  - the Blueprint template of the home area is never asked;
  - the 1 m edge holds both ways;
  - nothing changes without a player;
  - switching off removes every tag the mod gave;
  - a leftover tag at world load is reported and removed;
  - copying works when tables are refused, and writing stops when nothing works;
  - reach 0 leaves every storage out;
  - the `hardcore storages` listing is correct.
- The main mock registers the new module.

## 0.8.16 (2026-11-09): car crunches play within 10 m of the camera

Tested in game: the sound still needs some work, but it is kept like this for now. No crash. Passes the Lua check
and all three mocked runs. What the log shows:

- **The chase camera does drop back with speed.** With the car standing still, the crushed mound was 6.1 m from the
  camera. At 36–38 km/h it was 17.0–17.7 m away, so those crunches played 10 m from it.
- **On legs, crunches were 5.4–5.9 m from the camera.** So a moved car crunch still plays nearly twice as far away
  as a legs one. A `vehicle_sound_max_cm` of about 600 would bring it as close.

### Fixed

- **No crunch when driving the car fast (0.8.14 and 0.8.15 tests).** Slowly the crunch was heard; at speed it was
  not.
  - **What the 0.8.15 log shows:** the first car crunches played 18.2–18.5 m from the camera, while only 4 m from
    the car.
  - **Why that matters:** UE4 puts the audio listener at the camera, and the bush crunch is a short-range sound. At
    18 m it is near the edge of hearing, and at speed the car's noise is louder and the chase camera may drop
    further back. That the camera moves back with speed is not measured yet; this version logs it.
  - **Now:** in car, tractor and flight mode, a crunch further than `vehicle_sound_max_cm` (1,000 cm) from the
    camera plays that far from it, in the same direction.
  - On legs nothing changes: the crunch plays on its mound.
  - `hardcore sound` follows the same rule, so in car mode it now plays 10 m from the camera too.

### Added

- `hardcore check` shows, per mode, how far the camera was from the crushed mounds and the top speed. Example:
  "camera to crushed mound: car 17.7-20.5 m (up to 54 km/h), legs 8.9-10.5 m".
  - This shows the legs distance to match `vehicle_sound_max_cm` against.
  - It also shows whether the car camera really drops back at speed.
- The first 3 crunches in each mode also log the speed and whether the crunch was moved, for example "(played
  10.0 m from it)".

### Tests

- In the trampling mock, the camera now sits 18 m behind and 6 m up in car mode, and 8 m behind and 4 m up on legs.
  The mech and its car module report a velocity, and the long drive runs at 54 km/h.
- Checks:
  - every car crunch played at most 10 m from the camera (36 crunches);
  - the far ones say they were moved;
  - on legs every crunch played exactly on its mound;
  - the readout shows the distances and the 54 km/h top speed.

## 0.8.15 (2026-11-09): 3rd crunch at 750 ms; finding out why the car is silent

Tested in game: the car crunch was heard when driving slowly but not at speed. The first car crunches played
18.2–18.5 m from the camera. The `hardcore sound` A/B test was not run. Passes the Lua check and all three mocked
runs.

### Changed

- `trampling.sound_cut_ms` goes from `[900, 500, 400, 300, 200, 100]` to `[750, 500, 400, 300, 200, 100]`. In game,
  900 felt too much: the 3rd crunch now waits until the oldest has at most 750 ms left.

### Investigating: no crunch heard in car mode (0.8.14 test)

- **What the log shows:** the car crushed 10 Caroot plants in 0.7 s at 10:12:19. The legs crunches had ended
  30 s before.
- **What the code shows:** car and legs go through the same `checkMech` → `playCrushSound` path. So crunches were
  most likely started, but not heard.
- **Suspects:**
  - The audio listener sits at the camera, which in car mode is further back.
  - The car's own noise masks the crunch.
  - An audio mix the game applies in car mode.
- **New, to tell them apart:**
  - `hardcore check` counts the crunches by mode (legs, car, tractor).
  - The first 3 crunches in each mode are logged with their distance from the mech and from the camera.
  - `hardcore sound` says how far it played from the camera.
  - `hardcore sound camera` plays the crunch right at the camera. If that is heard in car mode and the plain
    command is not, the crunch is too far from the listener there. If neither is heard, it is masking or the
    game's car-mode mix.
- **Possible fixes once that is known:** the game exposes FMOD's `MinimumDistance` and `MaximumDistance` event
  overrides, `SetVolume`, and `FindEventInstances`.

### Fixed

- `hardcore check` (and `hardcore mounds`) prints the crunch counts. Since 0.8.12 these notes said
  `hardcore status`, which only prints the short status line.

### Tests

- The trampling mock's camera trails the last mech placed, 8 m behind and 4 m up. It checks that:
  - the first 3 crunches in each mode are logged with a distance;
  - `hardcore sound camera` plays 0.0 m from the camera;
  - the readout counts crunches by mode.

## 0.8.14 (2026-11-09): up to 8 crunches at once

Tested in game: the 3rd crunch's 900 ms felt too much (0.8.15 moved it to 750 ms), and the car played no crunch.
Passes the Lua check and all three mocked runs.

### Changed

- `trampling.sound_cut_ms` goes from `[900, 500]` to `[900, 500, 400, 300, 200, 100]`.
  - The 3rd and 4th crunches keep their 900 ms and 500 ms windows.
  - A 5th to an 8th may start in the oldest's last 400, 300, 200 and 100 ms, so at most 8 play at once.
  - With 4 or fewer playing, nothing changes.
- The log and `hardcore check` say "an 8th", not "a 8th".

### Expected sound

- In a full field, the 5th to 8th crunches have only the oldest's last 500 ms to start in, so they come in a quick
  run, 100 ms apart. After that, 7 or 8 play at once, and a new crunch starts every 100 to 500 ms.
- Simulated over 30 s with 1,392 ms crunches:

  | Crush offered | 0.8.13 `[900, 500]` | 0.8.14 |
  |---|---|---|
  | At every check (driving through a full field) | 2.9 a second, at most 4 | 5.4 a second, 8 at once about half the time |
  | At 40% of checks (walking past crops) | 2.3 a second | 3.4 a second, 5 or more playing about half the time |

- An evenly spread alternative, `[1200, 1000, 800, 600, 400, 200]`, gives a steady crunch about every 200 ms in a
  full field (5.7 a second), but makes the 3rd and 4th start earlier.
- If clicks come back, FMOD probably holds fewer than 8 copies of the bush crunch. The game has
  `FindEventInstances`, which could measure that limit.

### Tests

- The trampling mock now has six windows, given unsorted.
- It adds a long drive through a full field: 180 mounds over 64 checks. In that drive:
  - every crunch past the 2nd started inside its window;
  - all six windows were used, and there was never a 9th;
  - 20 crunches started as the 8th, once the stack was full.
- The first-crunch log names the windows in order, up to "an 8th".

## 0.8.13 (2026-11-09): wider windows, 900 and 500 ms

Installed. A config change; it passes the Lua check and all three mocked runs. Followed by 0.8.14 before an
in-game report.

### Changed

- `trampling.sound_cut_ms` goes from `[500, 250]` to `[900, 500]`.
  - A 3rd crunch may start once the oldest has at most 900 ms left, about half a second into the 1.4 s bush crunch.
  - A 4th may start once the oldest has at most 500 ms left.
  - Still at most 4 at once.
- The script's fallback, used only when the config has no `sound_cut_ms`, is the same.
- Simulated with a crush at every check for 20 s and 1,392 ms crunches:
  - 2.9 crunches a second (0.8.12: 2.5).
  - Starts are spaced 100, 400, 400, then 500 ms, a steadier patter than 0.8.12's 300, 200, then 700 ms.

## 0.8.12 (2026-11-09): a 4th crunch in the oldest's last 250 ms

Tested in game: it was "starting to sound right", and the windows were widened next (0.8.13). Passes the Lua check
and all three mocked runs.

### Changed

- `trampling.sound_cut_ms` is now a list of windows, `[500, 250]`. One number still works, and `[]` or `0` means
  never more than `sounds_at_once`.
  - Past `sounds_at_once` (2), each window lets one more crunch start over the oldest one's ending.
  - A 3rd may start once the oldest has at most 500 ms left, and a 4th once it has at most 250 ms left, so at most 4
    play at once.
  - The oldest is never stopped; it plays out.
- The first-crunch log line names the windows. `hardcore check` counts how many crunches each window let in, in
  place of 0.8.11's single "started in an older one's last moments" count.
- `tools/build_mod.py` accepts a list for `sound_cut_ms`.

### Fixed

- **0.8.10 and 0.8.11 lost count of the oldest crunch.**
  - **The bug:** when a crunch started in the oldest's tail, the mod dropped the oldest from its count, though the
    oldest was still playing.
  - **The effect:** the next crunch could then start in the following one's tail as well. Up to 4 overlapped, which
    was not the intent of a single window.
  - **Now:** the oldest stays counted until its end.
- How the two compare: a simulation crushed a mound at every check for 20 s, with 1,392 ms crunches.

  | Version | Crunches per second | Most at once | Spacing between starts |
  |---|---|---|---|
  | 0.8.11, the version tested in game | 2.3 | 4 | 100 ms, then 800 ms quiet |
  | 0.8.12 | 2.5 | 4 | 300, 200, then 700 ms |

- The mocked run now uses sounds about as long as the bush crunch: 1,292 to 1,492 ms, chosen so none ends exactly
  on a check. A tie there is decided by float rounding.
  - It checks that no more than 4 ever play at once, a 3rd starts only in the oldest's last 500 ms, and a 4th starts
    only in its last 250 ms.
  - Result: 11 crunches; 3 started as a 3rd and 3 as a 4th.

## 0.8.11 (2026-11-09): a new crunch may start in the last 500 ms

Installed. A config-only change.

### Changed

- `trampling.sound_cut_ms` goes from 50 to 500.
  - The bush crunch is 1,392 ms long (FMOD's `GetLength`, logged on the first crunch), so 50 ms was under 4% of it,
    and the overlap almost never happened.
  - Now, with 2 crunches playing, a new one may start once the oldest is in its last 500 ms, likely its quiet
    debris tail.
  - In the mocked run with short sounds, that gave 18 crunches instead of 14, 7 of them starting in an older one's
    tail.
- If clicks come back, FMOD is cutting tails it refuses to overlap. Lower the value again.

## 0.8.10 (2026-11-09): crash fix: no game object is kept from one check to the next

Tested in game: a short session (about 45 s, with crushing on legs) ended normally, with no crash report.

Before that, it was installed but not yet tested in game. Passes the Lua check and all three mocked runs. The trampling mock now refuses any
call on an audio component after the check that made it, and any `Stop()`.

### Fixed

- **The game crashed 40 s in (0.8.9 test).** The report shows `EXCEPTION_ACCESS_VIOLATION` reading
  `0xffffffffffffffff`, inside UE4SS while it ran our Lua.
  - **What failed:** a metamethod lookup on a UE4SS object, reached through its function dispatcher, then a struct
    destructor.
  - **The cause:** since 0.8.8 the mod kept the FMOD audio components it started, and on later crushes called
    `IsPlaying`, `GetLength`, `GetTimelinePosition` and `Stop` on them. A component destroys itself when its sound
    ends, and the game frees it soon after (often, with level streaming), so a later call reads freed memory.
    0.8.9's settings (2 at once, no gap, the early cut) made those calls frequent.
  - **Sounds now:** each sound's length is read once, in the check that starts it. Its end time is kept as a
    number, and the component is never touched again.
  - **The early start:** with 2 playing and the oldest in its last 50 ms (by those end times), the new crunch starts
    at once. The oldest ends on its own, or FMOD trims its tail. It's no longer stopped by the mod.
- The same rule now holds everywhere in `trample.lua`:
  - The crush sound's FMOD event and FMOD's statics are looked up for each play, not cached.
  - A pending empty mound keeps its mech's name and looks the mech and its controller up fresh on each pass.
  - The cached crop manager and every per-world list are dropped before a map unloads. `main.lua` gained an
    `onMapLeaving` hook, called from the load-map pre hook.

## 0.8.9 (2026-11-09): two crunches at once, and the oldest cut a little early now and then

Tested in game: crashed 40 s in (fixed in 0.8.10).

Before that, it was installed but not yet heard in game. Passes the Lua check and the mocked runs. With sounds of 430–510 ms, 14 sounds
played. There were never more than 2 at one moment, and one early cut trimmed a sound by 10 ms.

### Changed

- The user's tuning:
  - **`sounds_at_once` 2:** two crunches can play together.
  - **`sound_gap_ms` 0:** no minimum time between them.
  - **New `sound_cut_ms` (50):** when 2 are playing and the oldest has at most 50 ms left, it is stopped that much
    early and the new crunch starts right away.
- How the early cut works:
  - It uses the audio component's `GetLength` minus `GetTimelinePosition`, then FMOD's own `Stop`, which keeps the
    event's fade, not FMOD's hard cut.
  - It only happens when a crush lands in that last stretch, so it comes now and then, not every time.
  - Crushes at other moments wait until a sound finishes.
- The first crunch's log line includes the sound's length. `hardcore check` counts the early cuts.

## 0.8.8 (2026-11-09): crush sounds one at a time

Tested in game: the clicks were gone, and the user asked for 2 at once, no gap and an occasional early cut (0.8.9).

Before that, it was installed but not yet heard in game. Passes the Lua check and the mocked runs. With sounds lasting 0.5 s, a run of
19 crush events played 9 sounds, each only after the previous one ended, and skipped 10.

### Fixed

- **Walking through several crops turned the crush sound into clicks (0.8.7 test).** The first sounds were fine. The
  mod then started up to 3 sounds per check, 30 a second. FMOD lets only a few copies of an event play together and
  cuts the oldest off when another starts, so every sound was cut right after it began and only its click was left.
  - Now one crush sound plays per check, at the middle crushed mound.
  - It plays only once the previous crush sound has finished: the mod asks the audio component `IsPlaying`.
  - At least 300 ms separate two sounds.
  - Walking gives one whole crunch per step. Crushes while a sound is still playing stay silent.

### Changed

- `trampling.sounds_per_check` is replaced by:
  - `sounds_at_once` (1): how many crush sounds may play together.
  - `sound_gap_ms` (300): the shortest time between two.
- `hardcore check` counts the crush sounds skipped while one was playing.

## 0.8.7 (2026-11-09): the bush sound by default

Tested in game: the bush sound plays when crops are crushed, but it turned into clicks over several crops (fixed in
0.8.8).

A config-only change.

### Changed

- The crush sound defaults to a bush breaking (`/Game/FMOD/Events/Break/Break_Bush`), picked in game over the Field
  Plow's removal sound. The plow's sound is still one setting away (`hardcore sound plough` to hear it).

## 0.8.6 (2026-11-09): the crush sound is heard; `hardcore sound` to try it

Tested in game: `hardcore sound bush` plays the bush sound at the mech and uses it for crushed crops ("works like
expected"). That confirms `PlayEventAttached` reaches FMOD with the right position.

Before that, it passed the Lua check and the mocked runs. They check every argument of the new play call, and fail if
`PlayEventAtLocation` is used.

### Fixed

- **The crush sound was silent (0.8.5 test).** The log showed the event loaded and every play call returning
  without an error, yet nothing could be heard.
  - `PlayEventAtLocation` takes its transform as a const reference. The exe's reflection flags that parameter as an
    out-parameter, so UE4SS never reads the Lua table passed for it. Every sound played at the world origin, about
    1.7 km from the farm.
  - The sound is now played the way the Field Plow plays it: `PlayEventAttached` with the mound's world position
    as a plain vector (`EAttachLocation::KeepWorldPosition`). That gives an FMOD audio component on the crop
    manager's root, which destroys itself when the sound ends.
  - The game's blueprints confirm the event needs no parameters: `BP_Plough` plays it with no FMOD parameter calls.

### Added

- Console `hardcore sound` plays the crush sound at your mech right away, so you can hear it without trampling.
  - `hardcore sound bush` plays another sound and uses it for crushed crops for the rest of the session. The names
    are `plough`, `bush`, `bigbush`, `weed` and `noxious`, and any `/Game/FMOD/Events/...` path also works.
  - Set `trampling.sound` in `mod_config.json` to keep a choice.
  - Each play says whether FMOD made an audio component and whether it is playing. The first crush logs the same.

## 0.8.5 (2026-11-09): a crush sound

Tested in game: no sound was heard (fixed in 0.8.6). The log showed the event loaded and the play calls running. Passes the Lua check and the mocked runs: 38 sounds for 91 crushed plants, never
more than 3 in one check, the event loaded once.

### Added

- A crushed plant plays the game's own sound where its mound is.
  - **Default:** the Field Plow's Removal Mode sound, FMOD event `Plough_Remove_Tile_Crop`. It's the event
    `BP_Plough` plays as `PlantBaseDestroyedSound`.
  - **Calling it:** played through `FMODBlueprintStatics::PlayEventAtLocation`, fire and forget, positioned at the
    mound.
  - **Loading:** the event is found in memory, or loaded once.
  - **Cap:** at most `sounds_per_check` (3) sounds at once, spread over the crushed mounds, so a car crushing a row
    doesn't play a dozen together.
  - **Failures:** if the event or FMOD can't be found, or a play fails, the sound turns off for the session with
    one log line. Trampling carries on.
- `mod_config.json` `trampling` settings:
  - `sound` takes the FMOD event path, or `""` for none. A crunchier choice is `/Game/FMOD/Events/Break/Break_Bush`.
  - `sounds_per_check` sets the cap. The build checks both.
- `hardcore check` counts the crush sounds played.

The sound plays on the machine running the script, which is the host.

## 0.8.4 (2026-11-09): the walking mech's feet crush what they stand on

Tested in game: the feet crush the plants under them. The log shows plants crushed 25–58 cm from the left or right
foot, beside ones crushed by the body circle. No crash.

Before that, it passed the Lua check and the mocked runs: a striding foot crushed the plant under it, 188 cm from the
mech's centre, and left a plant beside the mech alone.

### Fixed

- **On legs, a foot could stand on a plant without crushing it (0.8.3 test).** The walking mech's footprint was only
  the 150 cm circle around its centre. The feet sit 125 cm to each side of the centre and reach forward and back
  in a stride, so a foot often lands 160–200 cm from the centre, outside the circle.
  - Each foot now also crushes what it stands on: a circle of `foot_radius_cm` (75 cm) at its position from the
    game's `GetFootLocation`.
  - A foot is checked when it moves, so turning on the spot counts. A parked mech's feet still crush nothing.
  - The body circle stays, so plants between the legs still die.

### Changed

- New setting `trampling.foot_radius_cm` (75) in `mod_config.json`.
- The log names what crushed each mound: "from the centre", "from the left foot" or "from the centre line" (the
  vehicles' box).
- `hardcore mounds` lists each foot's position and marks mounds under a foot.

## 0.8.3 (2026-11-09): crash fix

Tested in game: no crash in a longer session with the car and walking (about 3 minutes). Walking still missed a plant
under a striding foot (fixed in 0.8.4).

Before that, it passed the Lua check and all three mocked runs (trampling, worlds, card). The mocks now fail if a
script uses `LoopAsync`, `ExecuteWithDelay` or `GetAttachedActors`.

### Fixed

- **The game crashed about 30 s into driving the car through fields (0.8.2 test; 145 s after the game started).** The crash report
  (`EXCEPTION_ACCESS_VIOLATION` reading address 0) shows UE4SS's `FindAllOf` passing a NULL first argument to
  `strlen`. It was found by disassembling the crash stack:
  - `ucrtbase` `strlen` was called from UE4SS's argument reader, which calls `lua_tolstring(L, 1)` without
    checking the result.
  - The function that called the reader is registered as `FindAllOf`, according to its own error strings.
  - Every `FindAllOf` call in our scripts passes a constant class-name string. So the Lua stack changed under the
    call, which means two threads were in the same Lua state.
  - Two causes, both fixed:
    - **All repeating and delayed work now runs on the game thread.** `LoopAsync` and `ExecuteWithDelay` run their
      callback on a second thread, which queued the real work with `ExecuteInGameThread` while the game thread was
      running our scripts. Three loops did that: the settings rows, the card and trampling. Trampling added the most
      Lua work. They now use this UE4SS build's game-thread timers (`LoopInGameThreadWithDelay`,
      `ExecuteInGameThreadWithDelay`, driven by the engine tick, which the log shows hooked). The old pattern is
      only a fallback for builds without them, through one helper in `main.lua`, `api.loop`.
    - **No more reads from freed memory.** 0.8.2 built the empty mound's ignore list with `GetAttachedActors`. Its
      out-parameter array comes back as views into memory the game frees right after the call, and 0.8.2 read them
      about 30 times per crushed mound. The ignore list now uses only return values and live properties:
      - modules, tools, leg modules, held Large Objects and towed trailers;
      - each tractor attachment, from the treads module's `InstalledTractorAttachments`;
      - the pilot.

## 0.8.2 (2026-11-09): the car and the tractor crush what's under their wheels

Tested in game:
- **The car works.** Its box read 5.5–5.7 × 3.9–4.2 m from its 4 wheels. Mounds died up to 203 cm out from its
  centre line, and every empty mound went back at once.
- **The game crashed** after about 30 s of driving (fixed in 0.8.3).

Before that, it passed the Lua check and the mocked run:
- A car 4.7 × 3.5 m clears the rows under its wheels and the one between them, and leaves the rows 300 cm out alone.
- The same holds heading north.
- Turning on the spot crushes what the box newly covers.
- The empty mound goes back under the parked car.

### Fixed

- **The car cleared a strip between its wheels and left the plants in its wheel tracks (0.8.1 test).**
  - The crush area was still the 150 cm circle around the mech's centre. The car's wheels sit about that far out
    on each side, so their tracks fell on the circle's edge.
  - The 0.8.1 log also shows the car module's collision box reaching 55–82 cm below the ground. That's harmless
    within the 120 cm height limit, but it's no measure of where the car touches the ground.
  - In car and tractor mode the footprint is now the box around the vehicle's wheels, turned to its heading.
  - The wheels come from the leg module's movement component: the `WheelSetups` bones on its
    `SkeletalMeshComponent`, and each wheel class's radius. The car has 4 wheels (radius 85 cm); the tractor has 6
    tread wheels, 3 per side (radius 30 cm).
  - The box reaches one wheel radius past the end axles and 45 cm past the outer wheels' centres (half a tyre).
  - Its height is where the lowest wheel touches the ground: wheel centre minus radius.
  - Everything under the vehicle is crushed: the wheel tracks and the ground between them.
- A vehicle turning on the spot (10° or more) now crushes what its box newly covers.
- **The ignore list missed the attached actors.** UE4SS hands them back wrapped (16 entries in the 0.8.1 log), and
  those were dropped. They are unwrapped now. The legs test didn't need them, but the car or tractor may.

### Changed

- The log names the footprint, for example "car, 4.7 x 3.5 m around 4 wheels". For each crushed mound it gives the
  distance from the box's centre line, and it lists 6 mounds per event, then a count.
- When a vehicle's wheels are first read, the log lists each wheel bone and its radius.
- `hardcore mounds` shows the footprint, and marks a mound as under the mech when it's inside the box.

## 0.8.1 (2026-11-09): trampling on legs; the mound goes back at once

Tested in game:
- **Legs** works: the feet put the footprint within 8 cm of the mounds' height.
- **Tractor** works: the treads' bounds sit 3–19 cm under the mounds.
- **Empty mounds** went back at once.
- **The car** cleared a strip between its wheels and left the plants in its wheel tracks (fixed in 0.8.2).

### Fixed

- **Walking crushed nothing (0.8.0 test).** The sphere sat at the bottom of the mech's body capsule. In car mode
  that was about 108 cm above the mounds, just inside the 120 cm limit. On legs it was higher still, so every mound
  was filtered out as if the mech were jumping over it.
  - The mech walks on physics legs (`BipedalMovementComponent`), which hold the capsule well above the feet.
  - The sphere now sits under the mech's centre, at the height where it meets the ground. On legs that is the lower
    foot, from the game's `GetFootLocation` (the foot socket minus `FootRadius`). In a transform mode it is the
    bottom of the leg module's collision bounds (wheels or treads).
  - The capsule bottom is now only a fallback.
- **The mound came back late.** In 0.8.0 the plant and mound vanished together and the mound reappeared a few
  steps later. Five mounds never came back, because the mech stood on them past the 5 s retry window.
  - The empty-mound call traces the spot with the `BlockAllDynamic` collision profile. It refuses while anything not
    in its ignore list is there.
  - The list held only the mech, so the car or treads module, the tractor attachment, the pilot and trailers all
    blocked it. They are separate actors.
  - The list now holds the mech and everything that moves with it: attached actors, modules, leg modules, the
    pilot and towed trailers. The mound should go back in the same check, under the mech.
  - Retries still run for 5 s for anything else in the way.

### Changed

- The log details the first 6 trample events per mode (legs, car, tractor, flight) and says where the ground height
  came from (feet, module or capsule). The first empty mounds put back say whether that took retries.
- `hardcore mounds` prints each mech's ground point and the heights it was chosen from: actor, capsule bottom,
  lower foot and leg module bottom. It also shows how many actors move with the mech.
- `hardcore check` counts the empty mounds put back at once.

## 0.8.0 (2026-11-09): crop trampling

Tested in game:
- Car and tractor modes crushed crops; the log shows car events with mounds 82–149 cm from the path and about
  108 cm below the anchor.
- Walking on legs crushed nothing (fixed in 0.8.1).
- Crushed mounds were put back only after 3–4 checks, once the vehicle had moved on. Five were not put back at all
  (fixed in 0.8.1).

Before that, it passed the Lua check and a mocked run: a field of mounds; a mech walking, flying, parked, creeping,
driving fast and teleporting; a failed mound respawn; the feature off; a client game; the same world reloaded with
the mech elsewhere.

Design doc feature 1, with the user's decisions: one sphere around the mech's body (no per-leg simulation), only
the plant dies (the mound stays), and the tractor's tracks trample whether its attachment is raised or lowered.

### Added

- Feature `trampling`, row "Hardcore Crop Trampling" (`Scripts/trample.lua`). A planted crop dies when the mech's
  body passes over it, and the mound stays, empty and ready to re-seed. The mound's mulch, fertilizer and water
  start fresh.
  - The body is the mech's collision capsule, 150 cm around its centre. That is one mound tile: mounds sit 150 cm
    apart. A crop dies when its centre comes closer than that to the mech's path. A 2-tile path between beds is safe
    with a little room; walking a 1-tile path crushes the rows on both sides.
  - Every mode counts: legs, car, and tractor with the attachment raised or lowered. Tractor attachments don't
    crush; the tracks do. So tractor work in a planted field needs tramlines, gaps the tracks can drive along.
  - A mech whose feet are more than 120 cm above a mound (jumping, flying) passes over it. A mech that hasn't moved
    crushes nothing, so planting next to a parked mech is safe.
  - Empty mounds, mounds being harvested and Mound Plot mounds are left alone.
  - It applies at once. Switching the row in a loaded world's Settings menu needs no reload, and the row has no
    reload line. Existing worlds start with it off; the playstyle card switches it on for new worlds.
  - It runs on the host (or in single player) and covers every player's mech there.
- `mod_config.json`:
  - `features.trampling` has `"live": true`, the first feature with no tables.
  - A new `trampling` section holds `radius_cm`, `max_height_cm`, `min_move_cm` and `check_ms`.
  - The build checks both: a live feature can't own tables, and the numbers must be 0 or more.
- Console `hardcore mounds` lists the mounds around each mech: plant, distance, height, and whether it is under
  the mech. Use it for tuning. `hardcore check` (and the log 5 s after a world loads) adds a trampling line: events,
  plants crushed, empty mounds put back.
- The card's description mentions trampling.

### Changed

- `main.lua` keeps table features and live features apart:
  - Table features still apply just before a world loads.
  - A live feature applies the moment it's switched and never asks for a reload.
  - The console's "Save and reload" note now appears only when a table feature changed.

### How it works

- Every 100 ms, the mod checks each mech (`BP_TractorMechCharacter_C`) with the crop manager's
  `SphereOverlapCrops`, placed at the mech's feet (the bottom of its capsule).
  - That call is a 3D sphere test that adds the crop size (75 cm) to the radius.
  - It is repeated along the path since the last check, so a fast car doesn't skip mounds.
  - `FindCrop` then reads each mound: its plant, position, rotation and flags.
- A crushed plant's mound is removed with `Server_TryToDestroyCrops`, the call a Mound Plot makes when it's taken
  down; it doesn't harvest.
- An empty mound is then spawned in the same place and rotation with `Server_TryToSpawnEmptyCrop`. If the spot isn't
  free yet, it is retried for up to 5 s.

### Learned about the game (from the exe)

- **Destroying a planted mound harvests it first.** `ACropManager::Server_TryToDestroyCrop` (singular, the one the
  Field Plow's Removal Mode leads to) calls the crop manager's `Harvest(Player, CropId)` when the mound has a plant.
  Using it for trampling would turn it into a free harvest. The plural `Server_TryToDestroyCrops` skips that.
- **The game's plant-collision rule is dormant.** `AMechCharacter::CanDamagePlantsOnCollision` returns true on legs.
  In a transform mode it asks the leg module, and car, treads and the base module all return false. Nothing calls
  it: no blueprint names it, and the only native caller is its own UFunction thunk. It's a leftover, not a
  mechanic to switch on.
- **Crop grid.** Mounds are on a 150 cm grid (`TileSize` 150, `CropSize` 75). `FCropData.Rotation` is a byte
  (× 360/255 degrees). The crop calls need authority (`Role == ROLE_Authority`).
- **Collision sizes.**
  - The mech's capsule has a 150 cm radius and a 200 cm half-height.
  - Its leg capsules have a 40 cm radius and are 250 cm apart.
  - The tractor treads' box is 326 × 300 cm.
  - The car has four 150 cm foliage-deformation spheres.

### To test

- Load a world with planted crops, switch "Hardcore Crop Trampling" On in Settings > Playstyle, and walk the mech
  over a planted row. The plants should vanish and the mounds stay, empty.
- Walk along a 2-tile path between beds (no losses), then jump over a bed (no losses).
- Try the car and a tractor mode over planted mounds.
- Near a field, `hardcore mounds` in the console shows what the mod sees.

## 0.7.2 (2026-11-09): Customize screen left to the game

Installed. The card itself is tested (0.7.1); this version only removes code.

### Removed

- The Customize screen relabelling from 0.7.1 (the Playstyle row and the preset artwork showing "Hardcore
  Logistics"): in game the row showed our title at first, then the game redrew it as "Challenging". Customize is
  now the game's own screen; a player who wants other settings changes them there by hand, including the
  feature rows. Moving the Playstyle row no longer touches the features.
- Back from Customize with another preset picked in its Playstyle row, the game focuses that preset's card; the
  card is then no longer chosen and the features stay as set in Customize. With the preset unchanged
  (Challenging), the focus returns to the card as before.

## 0.7.1 (2026-11-09): the playstyle card registers with the screen; Playstyle row label

Tested in game: the fifth card shows after Challenging with the hidden Custom card's artwork (a mech hauling
logs with a trailer), title and description; hovering or clicking it chooses it (Challenging preset, every feature
on) and moving to another card un-chooses it (features off), as the log shows for about 30 focus changes; a new
world created with it got both features. On a 16:9 1080p screen the five cards look a little cramped (fine on the
user's ultrawide). The Playstyle row label did not stick (removed in 0.7.2).

### Fixed

- The card did not appear in 0.7.0: the script looked for the Challenging card's `ParentWidget` to register ours
  with UINavigation, found none, and (by design) added nothing. `ParentWidget` is declared on
  `UINavHorizontalComponent` (the settings rows), not on `UINavComponent` (the cards). The card is now registered
  with the screen itself, which is the cards' UINavigation widget; the script first checks that the screen holds
  the Challenging card's button (`GetButtonAtIndex`).

### Added

- While the card is chosen, the Customize screen's Playstyle row shows "Hardcore Logistics" in place of
  "Challenging". The row keeps the game's four options: the game's C++ maps the row position to a preset
  (`ApplyPlaystylePreset`, `GetMatchingPresetOptionIndex`), so a fifth option could reach it with a position it
  does not know. The label only changes on screen (`ChangeText`), so nothing is re-applied and tweaks made in
  Customize are kept. Moving the Playstyle row yourself un-chooses the card (features off); a label or artwork
  title the script set goes back to the game's text once the card is not chosen.

## 0.7.0 (2026-11-09): "Hardcore Logistics" playstyle card on the new-game screen

Tested in game: the card did not appear (see 0.7.1). Design roadmap step 3 (a 5th playstyle card).

### Added

- `Scripts/cards.lua`: a fifth card after Challenging on the new-game screen, an instance of the game's own card
  widget (`Widget_DifficultySelectorButton`) with the title and description from `mod_config.json` (`mode`) and
  the hidden Custom card's artwork. Choosing it calls the screen's own handler as if the Challenging card had been
  chosen (so the game applies the real Challenging preset), moves the gold "selected" frame to our card, and
  switches every feature on for the world about to be created. Choosing another card switches them off again.
- Back from Customize the game refocuses the selected preset's card (Challenging); the card takes the focus back.
  While Customize is open the card is hidden like the game's cards and the preset artwork shows "Hardcore
  Logistics".
- Opening the new-game screen starts with every feature off; the card or the Customize rows switch them on.
- `mod_config.json` has a `mode` section (title, description, base preset); the build checks it.
- The settings rows now follow changes made elsewhere (the card, the console) while the menu is open.

### How it works

- The screen keeps its four cards in a horizontal box (Creative, Relaxed, Balanced, Challenging, then the
  collapsed Custom card, Customize panel and preset artwork), so the card is appended at the end and still shows
  right after Challenging. It is registered with the screen's UINavigation grid right after the base card.
- The screen only listens to its own placed cards (`OnPresetClicked` / `OnPresetNavigatedTo` bound at setup),
  and hooks on its blueprint functions never fire in this game, so focus changes are read by polling the
  screen's `ButtonIndex` every 0.15 s. A native hook on `UINavWidget:NavigateTo` marks focus moves the game's
  blueprints make (player input calls it from C++ and does not pass through the hook), and a native hook on
  `UINavButton:OnClick` reports clicks on the card.

### Tested before installing

- `cards.lua` was run under Lua 5.4 against a mocked screen: focus on the card (Challenge preset, features on,
  frame on the card), focus on Balanced (features off), Customize open (card hidden, artwork retitled), back from
  Customize (focus returned to the card, features kept), click (the screen's click handler with Challenge),
  focus on the real Challenging card (features off).

## 0.6.1 (2026-11-09): reload line under the changed row

Tested in game (World_6): the reload line appears right under the row that was changed and disappears when the
row is set back; about two dozen changes in one menu session, no errors in the log. This completes the
settings integration: per-world features chosen on the new-game screen or in the Settings menu.

### Changed

- The reload notice is now one line per row, placed right under it, and shown only for features whose saved
  value differs from the one the world is running with. In 0.6.0 a single line sat under the last row, at the
  bottom edge of the list, where it was easy to miss.
- When the player's change makes a line appear, the settings list scrolls it into view (`ScrollWidgetIntoView`
  on the scroll box around the playstyle list: Widget_PlaystyleSettings, then the `Game` vertical box, then
  the tab's `ScrollBox`).
- The line uses the game's smaller caption style (`BB4`, Regular 14; the row titles use `B3`, Light 16),
  indented to start under the row titles. Text: "Save and reload the world to apply this change."

## 0.6.0 (2026-11-09): one settings row per feature, reload notice

Tested in game: both rows show on the new-game Customize screen and in the in-game Settings menu; a new world
started with Mech Cargo On and Deliveries Off (World_6) got only the cargo changes; changing the rows in the
world saved the choice, and reloading applied it; the reload notice appeared after a change.

### Changed

- Features: `mod_config.json` now has a `features` section, and each feature is its own Off / On row in the
  playstyle settings, stored per world. Two so far: **Hardcore Mech Cargo** (`cargo`: `DT_Modules`,
  `DT_CoreUpgrades`) and **Hardcore Deliveries** (`deliveries`: `DT_Deliveries`). The build checks that every
  table belongs to exactly one feature and tags each edit in `edits.lua` with it; the runtime applies and
  restores each feature on its own. The static pak still changes everything.
- `worlds.txt` lists the features that are on per world (`World_3=cargo,deliveries`, `World_4=off`). Older
  `World_3=on` lines still mean every feature and are rewritten in the new form on the next save.
- A world now runs with the features it was loaded with: a change made in a loaded world (settings row or
  console) is only saved, and applies the next time the world loads. Before, it changed the tables at once,
  which reached the mech but not the deliveries (the delivery system keeps its own copy from the load), a
  mixed state.
- Console: `hardcore <feature> on|off` changes one feature, `hardcore on|off` all of them; `hardcore` and
  `hardcore check` show the saved and running features.

### Added

- Reload notice: in a loaded world's Settings menu, a line under the rows ("Save and reload the world to apply
  the Hardcore changes.") is shown while the world's saved features differ from the ones it runs with. It is
  the game's own text widget (`Widget_TextElement`, style `B3` like the row titles), not a pop-up: the game's
  prompt (`Widget_DecidePromptTemplate`, which shows its "This setting requires a restart" message) is a
  UINavigation menu screen of its own, and opening one from outside the menu flow risks trapping keyboard and
  pad input.

### Tested before installing

- `main.lua` was run under Lua 5.4 (lupa) with mocked UE4SS functions: new-game choice saved for a new slot
  before it loads, in-world changes saved but not applied (`needsReload` true), applied on the next load
  (`needsReload` false), old `on` lines read as every feature, a stale pre-load slot corrected after the load,
  console per-feature and all-feature commands.

### Fixed

- The delivery readout in `hardcore check` (and in the log 5 s after a world loads) reads the deliveries now:
  UE4SS hands the array elements over as wrappers whose fields are read through `:get()`. In World_6 it listed
  the 28 available tier 1 deliveries (for example `Wheat_1: Wheat 0/10`), which the mod does not change.

## 0.5.0 (2026-11-08): "Hardcore Logistics" row in the playstyle settings

Design roadmap step 2 (Customize-menu rows). Tested in game (round 5): changing the row and reloading the world
gives the chosen settings.

### Added

- `Scripts/ui.lua`: watches for the game's playstyle settings list (new-game Customize screen and the in-game
  Settings menu) and inserts a **Hardcore Logistics** Off / On row at the end. The row is an instance of the
  game's own row widget (`Widget_SettingsMenuOptions_C`) with setting ID `HardcoreLogistics`; it borrows the
  localized Off / On labels and spacing from the game's "Disable Mech Without Fuel" row.
- In a loaded world, changing the row writes `worlds.txt` and applies or restores the table changes at once;
  deliveries pick the change up after saving and reloading the world (see "Fixed" below).
- On the new-game screen the choice is held and saved for the new world's slot when it first loads. A slot
  counts as new when it has no save file yet (`%LOCALAPPDATA%\FarMech\Saved\SaveGames\World_N.sav`) or had none
  when the choice was made. A new world without a choice is written as `off`, which also clears a stale entry
  left by a deleted world in the same slot.
- Console command `hardcore check`: prints the slot, the live table values with their memory address, and what
  the game's delivery system is asking for right now, with a count of deliveries showing hardcore vs vanilla
  amounts. The same readout is written to the UE4SS log 5 s after every world load.
- `tools/check_lua.py`: compiles the runtime scripts with Lua 5.4 (the version UE4SS embeds) and reads the
  bytecode to flag unknown globals (typos, or local functions called above their declaration). It runs
  automatically in `build_mod.py runtime` / `install-runtime` and stops the install on an error. Uses the
  `lupa` package in the repo's `.venv`.

### Fixed

- Deliveries could keep vanilla amounts in a hardcore world. The game's delivery system (`ADeliverySystem`)
  copies the delivery table into its own per-tier cache (`DeliveryGroups`, a non-reflected structure that Lua
  cannot edit) while a world loads. Applying the changes when the map has finished loading was early enough
  for the first world of a session (the 0.4.0 test) but too late for a world loaded after another one. The
  changes are now applied in a load-map pre hook, before the world starts loading, for the slot the game
  instance is about to load (`WorldSaveSlot`). This is safe because the three tables stay in memory for the
  whole session: the game instance class imports them (via `BPC_NotificationMarkerHandler`,
  `BP_DebugComponent` and `BPFL_Utility`). Restoring now also checks that each table is still the same object
  before writing to it.

### Test log

- Round 1: the row did not appear. `GetAllChildren()` came back empty under UE4SS, so no template row was
  found; switched to `GetChildrenCount()` / `GetChildAt()`.
- Round 2: the row appeared with the game's own Off / On labels, but changing it crashed the game (null read,
  only game frames on the stack). Cause: the row is a UINavigation option box, and option boxes call their
  menu (`ParentWidget`) on every change; a row added after the menu was built has none. Fix: register it with
  the menu's `AddUINavComponent` in the playstyle rows' navigation grid, and remove the row again if that
  fails, so an unregistered row can never be clicked.
- Round 3: the row was missing again: the safety check removed it because `AddUINavComponent` registers the
  row (menu buttons 23 -> 24) but leaves its `ParentWidget` empty. The mod now sets `ParentWidget` itself after a
  confirmed registration.
- Round 4: the row appeared in both menus and changing it no longer crashed, but no change was ever stored:
  the hooks on the row blueprint's `OnNavigateLeft/Right` registered but never reported a click, and the
  backup hooks pointed at `UINavOptionBox`, which does not declare `NavigateLeft/Right` (its base class
  `UINavHorizontalComponent` does). A new world created with the row On started vanilla (World_4, carry
  limit 4). World_3 (on) got all 145 table changes, yet its deliveries showed vanilla amounts: that is the
  delivery-cache timing fixed above (World_4 had been loaded first in that session).
- Round 5: works. The plugin's own `UINavHorizontalComponent:NavigateLeft/Right` are hooked with a pre hook,
  and the value the player moved to is worked out from the arrow direction and the value before the call
  (the game may refresh the row inside the same call and read our unknown ID as 0). A 0.5 s scan catches
  changes no hook reported: a change to On, or a change to Off while the row is the menu's selected item,
  counts as the player's; any other change is the game resetting the row, and the stored value is shown
  again. Log of the test: the native NavigateLeft/Right hooks fired on every click of our row; none of the
  blueprint hooks (row `OnNavigate*`, `Refresh`, `OnUpdated`, the menu's `UpdateSetting`,
  `GetConfirmedSettingValue`, `RefreshSlots`, the new-game `SelectPreset`) ever fired; the menu never reset
  the row. New worlds took the Customize choice before loading (World_4 on, World_5 off), the game instance's
  `WorldSaveSlot` named the right slot in every pre-load hook, and the three tables kept the same address
  across every load. Changing the row in World_5 and reloading gave the chosen settings.

### Why this works without the Unreal editor

- A row is pure configuration (`SettingID`, `SettingName`, `StringOptions`, `MaxRange`, `NeedsApply`); the
  game's rows were decoded from `Widget_PlaystyleSettings`.
- The game's settings code logs "Unhandled setting ID ... skipping" / "... returning 0" for unknown IDs, so the
  game ignores our row when applying and reads it as 0; `ui.lua` re-shows the stored value after the game
  refreshes the rows.
- The settings menu is created fresh each time it opens (a new `Widget_SettingsMenuBase_C` per open), so the
  row is re-added and shows the stored value every time.

## 0.4.0 (2026-11-08): runtime mode, per world

First step towards a selectable mode (design roadmap: per-world switch, then Customize-menu rows, then a
5th playstyle card). Tested in game: in World_3 the console reports hardcore ON, the mech's hauling capacity
and the delivery requirements use the mod's values; World_0 in the same session shows vanilla values
(Iron Frame 1 per delivery, Mk. 3 arms at 8).

### Changed

- The mod can now run as a UE4SS Lua mod that applies the changes in memory only while a world switched on
  in `worlds.txt` is loaded (`World_3` to start with). Vanilla worlds stay vanilla; switching worlds restores
  or re-applies the changes. The static pak was removed from `Paks\~mods` so the two never stack.
- Console command `hardcore` / `hardcore on` / `hardcore off` (console: `~` or `F10`).

### Installed

- UE4SS v3.0.1-1217 (`UE4SS_v3.0.1-1217-g4fb9b615.zip`, 8,759,304 bytes, SHA-256 `fbdacd0f...c38194f`
  matching GitHub's record) into `FarMech\Binaries\Win64`.

### Tool

- `runtime`, `install-runtime`, `disable-runtime` commands. The tool resolves `mod_config.json` against the
  game and writes `edits.lua`: 10 stat changes and 135 delivery cost lists (vanilla and target entries, 105
  added items), with exact field paths.

### Verified (UE4SS log)

- `SaveLoadComponent_C:GetActiveSaveSlot()` returns the world's slot (`World_3`) when the gameplay map
  loads; the mod applies all 145 changes at that moment (0 failed), before the mech reads its stats, so no
  re-equip is needed.
- Live readbacks after applying: Standard arm 2.0 (vanilla 4.0), chip Lv. 1 1.0 (vanilla 2.0), Wheat tier 2
  `{Wheat=25, CopperWire=5}`. Map reads (`ForEach`), `Empty` and `Add` all work from Lua.
- Returning to the main menu restores vanilla values; loading World_0 afterwards stays vanilla.
- The game instance holds a `WorldSaveSlot` string (it read `World_0` in the main menu), likely the slot a
  new world is created in; useful for the Customize-menu step.

### Fixed after the first test

- The "could not read the save slot" diagnostic now only runs on gameplay maps (it also fired on the
  splash screen, where there is no world).

## 0.3.0 (2026-11-08): planet-themed delivery components

Each planet's deliveries now ask for one extra component from tier 4 up, themed by planet and climbing with
the tier. Tested in game: the delivery panel shows the 4th row cleanly (Polyberry tier 8: Polyberry 2,000,
Mutated 800, Steel Frame 15, Clear Lens 8), and deliveries that include the new items go through.

### Added

| Planet (lines) | Theme | T4 / T5 | T6 / T7 | T8 / T9 | T10 |
|---|---|---|---|---|---|
| Hewstone (Wheat, Rabbage, Chromaize) | Machinery | Bronze Parts 3 / 5 | Iron Parts 5 / 10 | Steel Parts 8 / 12 | Fractalite Parts 5 |
| Tempest (Lumbloom, Zappertwig, GloFruit) | Electronics | Bronze Electronics 3 / 5 | Iron Electronics 5 / 10 | Steel Electronics 8 / 12 | Fractalite Electronics 5 |
| Wildernest (Polyberry, Caroot, Papristalk) | Optics | Clear Glass 5 / 10 | Clear Lens 5 / 10 | Clear Lens 8 / 12 | Clear Lens 5 |
| Cryolis (Honeybottle, Cloudbud, Feather) | Shelter | Polymer 5 / 10 | Cloth 10 / 20 | Concrete 15 / 25 | Concrete 10 |
| Verdemere (Coilvine, Quartznip, Amber) | Metal stock | Bronze Bar 5 / 10 | Iron Bar 10 / 20 | Steel Bar 15 / 25 | Fractalite Bar 10 |

- Craftability rule: an item only appears at a tier if its recipe unlocks no later than the frame the game
  already asks for there (tiers 4-5 Bronze Frame = Milestone 4, 6-7 Iron = M7, 8-9 Steel = M10, 10 Fractalite
  = M12). Unlocks used: Polymer M3; Bronze Parts / Electronics / Bar and Clear Glass M4; Clear Lens needs Clear
  Glass + Furnace (M4); Iron Parts / Electronics / Bar and Cloth M7; Concrete M8; Steel items M10; Fractalite
  items M12.
- Left out: items that unlock by discovery instead of milestone (silver, gold and aluminum items, colored
  lenses), since a player may not have found the ore yet.
- Amounts: complex items (Parts, Electronics, Lens) ask half the frame amount, simple materials (Glass,
  Polymer, Cloth, Concrete, Bars) the same as the frame amount.
- 105 new cost entries (15 lines x tiers 4-10). Crop amounts, tiers 1-3 and the endgame cannon are unchanged.

### Tool

- `Map[+Key]` adds a map entry. The table package is rebuilt around it: new item names go into its name map
  with the hash the engine expects (lowercase CityHash64), header offsets shift by a multiple of 8, and the
  export size is updated. Added names must be rows of `DT_Items`.
- Row selectors take a field condition: `*_6 [PlanetName=Hewstone]`.
- Rebuilt tables get a whole-table check: every value must match vanilla except the planned changes, and the
  only new values may be the planned entries.
- Later entries can override entries an earlier rule added (`Polyberry_8: Cost[ClearLens]` after a planet-wide
  `Cost[+ClearLens]`), so single tasks can be fine-tuned under tier and planet rules.
- `show TABLE FILTER --modded` prints the values in the last build, to check a change without the game.

### Verified

- Build checks, plus an independent decode of the installed file: 165 rows, 135 changed (tiers 2-10), the 30
  tier-1 and endgame rows identical, 99 / 99 name hashes correct (82 original + 17 new).

### Checked in game

- Vanilla never shows more than 3 resources per delivery; the 4th row fits the panel.
- Deliveries that include the new items are accepted.

## 0.2.0 (2026-11-08): bigger delivery tasks

Design doc feature 7, "Increase later progression task requirements", for planet deliveries (`DT_Deliveries`).
Tested in game: the delivery screen shows the new amounts (Polyberry tier 8 asks for 15 Steel Frames).

### Changed

All 15 delivery lines (Wheat, Rabbage, Chromaize, Polyberry, Caroot, Papristalk, Honeybottle, Cloudbud, Feather,
Lumbloom, Zappertwig, GloFruit, Coilvine, Quartznip, Amber) share one component ladder:

| Tier | Component | Vanilla | Now |
|-----:|---|---:|---:|
| 2 | Copper Wire | 1 | 5 |
| 3 | Copper Wire | 5 | 15 |
| 4 | Bronze Frame | 1 | 5 |
| 5 | Bronze Frame | 2 | 10 |
| 6 | Iron Frame | 1 | 10 |
| 7 | Iron Frame | 2 | 20 |
| 8 | Steel Frame | 1 | 15 |
| 9 | Steel Frame | 2 | 25 |
| 10 | Fractalite Frame (`CubeMetalFrame`) | 1 | 10 |

Crop and resource amounts are unchanged, as are tier 1 and the endgame cannon rows (`Endgame_*`, `Earth_*`).
A x1.5 crop multiplier from tier 4 was tried during testing and dropped: the goal is bigger component
batches, not more crop grinding. 135 values in total; a build writes the full list to
`dist/HardcoreLogistics_P_changes.txt`.

### Tool

- Rows can be patterns (`*_6`), paths can use `[*]` for every map or array entry, and values can be
  multipliers (`"x1.5"`). Entries apply in order, so a fixed value can override a multiplier.
- Each build writes a report of every changed value next to the mod files.

### Findings

- `MechPowerReward` (1-10 per tier) and the milestone thresholds (`DT_DeliveryMilestones.RequiredDeliveries`)
  are unchanged, so progression pacing only changes through the bigger costs.
- Deliveries are all at once: each counter shows how much of that resource you have right now (with the
  shared base inventory, everything stored in the base), and the delivery takes the full amount in one go.
  There is no partial contribution. (An earlier version of this entry claimed there was, based on the
  game's "Contribute to Delivery" text; testing showed otherwise.)
- Consequence for the local-inventory feature (design feature 3): without shared base inventory, every
  resource for a delivery would have to sit in storage the cannon can reach, so players would stock a depot
  next to the Delivery Cannon.
- New items can be added to a delivery's cost later: the package name map uses lowercase CityHash64 name
  hashes (verified against all 82 names in `DT_Deliveries` and all 1,447 in `DT_Items`), so new item names
  can be added with correct hashes.

## 0.1.0 (2026-11-08): mech cargo rebalance

Built and tested against Lightyear Frontier 1.0.2563 (Steam build 26458907, game files dated 2026-11-05).
This covers the mech side of design feature 2, "Rebalance large-object hauling". The mech carries less, so
trailers become the bulk-transport tool.

### Changed

| Mech Arms (in-game name) | Table row | Vanilla | Now |
|---|---|---:|---:|
| Mk. 1 (Farmech) | `DT_Modules` / `StandardRightArm` | 4 | 2 |
| Mk. 2 (Underframe) | `DT_Modules` / `NakedRightArm` | 6 | 4 |
| Mk. 3 (Hot Rod) | `DT_Modules` / `HotRodRightArm` | 8 | 6 |
| Mk. 4 (Vintage) | `DT_Modules` / `HermesRightArm` | 10 | 8 |
| Mk. 5 (FM-04) | `DT_Modules` / `FM04RightArm` | 14 | 10 |
| Mk. 6 (Power Armor) | `DT_Modules` / `PowerArmorRightArm` | 18 | 14 |
| Mk. 7 (Lightyear Hauler) | `DT_Modules` / `HaulerRightArm` | 24 | 18 |

| Hauling Capacity chip | Table row | Vanilla | Now |
|---|---|---:|---:|
| Lv. 1 | `DT_CoreUpgrades` / `HaulingCapacity0` | +2 | +1 |
| Lv. 2 | `DT_CoreUpgrades` / `HaulingCapacity1` | +3 | +2 |
| Lv. 3 | `DT_CoreUpgrades` / `HaulingCapacity2` | +4 | +3 |

All values are the `Upgrade.Hauling.Capacity` stat, in hauling units.

### Tested in game

- Arms at 0: large objects show "Pick up (Full)" and cannot be picked up. No crash.
- Arms and chips at 0: total hauling capacity 0.
- Final values: Mech Arms Mk. 4 shows Hauling Capacity 8, and each Lv. 2 chip adds +2 in both arm and leg
  slots (8 + 3 leg chips + 3 arm chips = 20 in the test loadout).

### Findings

- Capacity is counted in units. Mineral chunks (Iron Chunk and the other ores) cost 2 units each
  (`StackUnits = 2` on `BP_LargeItem_Mineral`), shown as "x2" on the pickup prompt. That is why the vanilla
  16-unit trailer holds 8 Iron Chunks.
- Only the 7 right-arm parts and the 3 chips carry `Upgrade.Hauling.Capacity`. Left arms, legs, body,
  cosmetic skins and loadouts add nothing of their own.
- Hauling Capacity chips fit arm and leg slots, so a dedicated hauling loadout can stack them until it runs
  out of Power. The chip text mentions a 40-unit cap; that cap is not in any data table, so it is enforced
  in code.
- Trailers are unchanged: Large Object Trailer 16 units (Milestone 3), II 32 units (Milestone 8, can chain
  to other trailers), III 48 units (Milestone 11).

### Known issues

- The chip descriptions still say "+2 / +3 / +4 units" because the build tool only changes numbers.
