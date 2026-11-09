# Hardcore Logistics (Lightyear Frontier mod)

Version 0.15.6, the first public release (Nexus Mods). Players: the release zip carries its own short read-me (`release/README.txt`); this file is the full documentation, for players who want the details and for anyone building the mod from source. MIT license (`LICENSE`).

Mod for Lightyear Frontier 1.0 (Unreal Engine 4.27). It changes seven things:

1. **Cargo:** the mech carries fewer Large Objects, so trailers become the way to move bulk cargo.
2. **Delivery tasks:** planet deliveries ask for real batches of components, so production throughput
   matters.
3. **Crop trampling:** the mech crushes the crops it walks over, so fields need paths.
4. **Local storage:** only the storage near you counts for crafting, building and deliveries, so where you
   store things matters. To make up for it, storages hold twice as much.
5. **Workshop Shed:** the cut Workshop Shed is back, buildable from your first delivery, so the first machines
   have a quick home.
6. **Logistics Hub:** a new building, from Milestone 10, that shares all the storage in its base again, as long as
   the Energy Meter has room for it. It comes with local storage: worlds without it never see the hub.
7. **Drone Stations:** two new buildings, from Milestone 8, that work like a pipe between bases: pipes fill an
   input station, its drone flies the items to the output stations painted the same colour, and pipes take
   them on from there.

### Cargo

Capacity is counted in units: a mineral chunk such as an Iron Chunk takes 2 units (`StackUnits` on the chunk
blueprints).

| Arm (in-game name)            | Vanilla | Mod |
|-------------------------------|--------:|----:|
| Mech Arms Mk. 1 (Farmech)     | 4       | 2   |
| Mech Arms Mk. 2 (Underframe)  | 6       | 4   |
| Mech Arms Mk. 3 (Hot Rod)     | 8       | 6   |
| Mech Arms Mk. 4 (Vintage)     | 10      | 8   |
| Mech Arms Mk. 5 (FM-04)       | 14      | 10  |
| Mech Arms Mk. 6 (Power Armor) | 18      | 14  |
| Mech Arms Mk. 7 (Hauler)      | 24      | 18  |

| Hauling Capacity chip | Vanilla | Mod |
|-----------------------|--------:|----:|
| Lv. 1                 | +2      | +1  |
| Lv. 2                 | +3      | +2  |
| Lv. 3                 | +4      | +3  |

The chips' description text still shows the vanilla numbers. Trailer capacities (16 / 32 / 48 units) are
unchanged for now.

### Delivery tasks

All 15 planet delivery lines (tiers 1-10 each) share one component ladder. The mod raises it:

| Tier | Component | Vanilla | Mod |
|-----:|-----------|--------:|----:|
| 2 | Copper Wire | 1 | 5 |
| 3 | Copper Wire | 5 | 15 |
| 4 | Bronze Frame | 1 | 5 |
| 5 | Bronze Frame | 2 | 10 |
| 6 | Iron Frame | 1 | 10 |
| 7 | Iron Frame | 2 | 20 |
| 8 | Steel Frame | 1 | 15 |
| 9 | Steel Frame | 2 | 25 |
| 10 | Fractalite Frame | 1 | 10 |

Crop amounts and the endgame cannon deliveries are unchanged (Wheat tier 6: 750 Wheat + 300 Mutated Wheat +
10 Iron Frames instead of 1). A delivery takes the full amount at once from what you have stored in the base
(there is no partial contribution). `dist/HardcoreLogistics_P_changes.txt` lists every changed value after a
build.

From tier 4 up, each planet also asks for one extra component of its own, climbing with the tier:

| Planet | T4 / T5 | T6 / T7 | T8 / T9 | T10 |
|---|---|---|---|---|
| Hewstone | Bronze Parts 3 / 5 | Iron Parts 5 / 10 | Steel Parts 8 / 12 | Fractalite Parts 5 |
| Tempest | Bronze Electronics 3 / 5 | Iron Electronics 5 / 10 | Steel Electronics 8 / 12 | Fractalite Electronics 5 |
| Wildernest | Clear Glass 5 / 10 | Clear Lens 5 / 10 | Clear Lens 8 / 12 | Clear Lens 5 |
| Cryolis | Polymer 5 / 10 | Cloth 10 / 20 | Concrete 15 / 25 | Concrete 10 |
| Verdemere | Bronze Bar 5 / 10 | Iron Bar 10 / 20 | Steel Bar 15 / 25 | Fractalite Bar 10 |

Every extra item unlocks no later than the frame the game already asks at that tier, so the player can
always craft it (see the 0.3.0 entry in the changelog for the unlock milestones).

### Crop trampling

A planted crop dies when the mech's body passes over it. The mound stays, empty and ready to re-seed; its
mulch, fertilizer and water start fresh. This needs the runtime mode (UE4SS); the static pak cannot do it.

- On legs the body is a circle 150 cm around the mech's centre (its collision capsule's radius), at its lower foot,
  plus 75 cm around each foot, wherever the stride puts it. 150 cm is one mound tile, since mounds sit 150 cm apart.
  A 2-tile path between beds is safe with a little room to spare; walking a 1-tile path crushes the rows on both
  sides.
- In car and tractor mode the body is the vehicle: the box around its wheels, turned to its heading. Everything
  under it is crushed, the wheel tracks and the ground between them. The car's box is about 4.7 × 3.5 m. Turning
  on the spot crushes what the box newly covers.
- Every mode counts: legs, car, and tractor with the attachment raised or lowered. Tractor attachments don't
  crush, but the tracks do, so tractor work in a planted field needs tramlines, gaps the tracks can drive along.
- A mech jumping or flying more than 120 cm above a mound passes over it. A parked mech crushes nothing, so
  planting next to it is safe.
- Empty mounds, mounds being harvested and Mound Plot mounds are left alone.
- Crushing plays the sound of a bush breaking, two at a time and up to eight overlapping. A third may start during
  the oldest's last 750 ms, a fourth during its last 500 ms, and a fifth to an eighth during its last 400, 300,
  200 and 100 ms.
- The sound is heard from the camera. In car, tractor and flight mode the chase camera drops back as you speed
  up: in car mode the crushed mounds were about 6 m from it standing still and 17–18.5 m at speed (on legs,
  about 5.5 m). So there, a crunch further than 10 m from the camera plays 10 m from it, in the same direction.
  On legs it plays on the mound. In the console:
  - `hardcore sound` plays it at your mech, and says how far that is from the camera.
  - `hardcore sound camera` plays it right at the camera. If that is heard and the plain command is not, the
    sound is too far from the listener in that mode.
  - `hardcore sound plough` (or `bigbush`, `weed`, `noxious`, `bush`) tries another one for the rest of the
    session.
  - `hardcore check` counts the crunches by mode (legs, car, tractor), and by the window that let each one in.
    It also shows how far the camera was from the crushed mounds in each mode, and the top speed.
  - The first 3 crunches in each mode are logged with their speed and their distance from the mech and from the
    camera.
- The numbers and the sound are in `mod_config.json` under `trampling`.

### Local storage

In the game, everything in any storage of a base counts everywhere in that base: crafting, building,
deliveries and tasks all draw on the whole base. Outside a base, only the mech's own inventory counts. With
local storage on, a storage counts only within 15 m of where it is used: the station you craft at, the spot you
build on, the delivery cannon. Distances are measured flat. This needs the runtime mode (UE4SS).

- Anything stored further away has to be brought over first: carried in the mech, hauled by trailer, or piped.
- A delivery takes its items from your mech and the storages within 15 m of you at the cannon, so keep a depot
  of storage next to it.
- A storage out of reach still opens normally, and pipes still move items in and out of it.
- Generators are left alone: the game already keeps their fuel out of the base inventory.
- **Storages hold twice as much** while local storage is on, since each spot now needs more room:

  | Storage | Vanilla | Mod |
  |---|---:|---:|
  | Burlap Sacks | 100 kg | 200 kg |
  | Storage Box | 150 kg | 300 kg |
  | Wooden Crate | 200 kg | 400 kg |
  | Barrel | 300 kg | 600 kg |
  | Storage Box II | 600 kg | 1,200 kg |
  | Small Shed | 1,200 kg | 2,400 kg |
  | Storage Shed | 3,000 kg | 6,000 kg |
  | Storage Shed II | 10,000 kg | 20,000 kg |
  | Silo | 5,000 kg | 10,000 kg |
  | Silo II | 15,000 kg | 30,000 kg |
  | Silo III | 25,000 kg | 50,000 kg |

  - **Placed storages grow too:** every storage takes its size from the game's `DT_StorageCapacities` table
    whenever the world loads, and the build menu shows the new sizes.
  - **Unchanged:** silos still hold one item type each. Storage trailers, generators, feed troughs and the
    obsolete Automators keep their sizes.
  - **When it applies:** the sizes change as the world loads, like the other table changes. Switching local storage
    in a loaded world changes the storage rule at once and the sizes on the next load.
  - **Switching it off with full storages (tested in game):** a storage holding more than its vanilla size keeps
    everything and shows itself over capacity, for example a Wooden Crate at 3,963 / 2,000 kg. The game copes, as it
    does when its own Item Weight setting changes.
- How it works: the game skips every storage that carries its `NoRemoteInventoryAccess` tag, which it gives its
  generators. Every menu and station asks the game for the base inventory before it uses it. The mod hooks that
  request and, just before the game answers, tags the storages more than 15 m from the spot it asks about and
  untags the ones within reach. Nothing runs between requests, so there is no steady cost. Switching the feature
  off takes every such tag off.
- `hardcore storages` (console) lists the storages in each base, nearest first, with their distance and whether
  they count right now.
- The reach and timing are in `mod_config.json` under `storage`. A `reach_cm` of 0 makes a base work like the
  land outside one: only the mech's inventory counts.

### Logistics Hub

A new building that brings back the shared base inventory for its own base:

- **What it does:** with local storage on, every storage in a base holding a hub counts from anywhere in that base,
  as in vanilla. Other bases stay local, and demolishing the hub makes its base local again.
- **Energy:** it uses 100 on the game's Energy Meter, like any machine with an energy cost (Diesel Generator II
  makes 250). The playstyle's "Construct Energy Costs" setting scales it like every machine's:
  - Balanced: 100
  - Relaxed: 50
  - Creative: 0
  - Challenging: 200

  The meter is one pool for the whole world. While it is at 0 or above, the grid is Energized and the hub links its
  base. Below 0 the grid is Overloaded: machines run at normal speed, and the hub links nothing until there is
  enough energy again. When the mod can't read the meter, the hub keeps working, and `hardcore hub` says why.
- **Focus panel:** looking at the hub shows its name, its energy cost, and "Securing base logistics" with a flat
  golden drone-and-crate icon in the game's own status-icon style (`art/logistics_hub/status_icon.py`), in place of
  the reservoir's water line.
- **No E action:** it is built on the game's Water Reservoir, a plain construct with an energy handler, and has no
  menu of its own. The Water Tower base of 0.12.x had an "Open" action, and an opened building counted as in use, so
  it could not be recycled.
- **Only with local storage:** the hub belongs to the "Hardcore Logistics: Local Storage" setting. A world loaded with it off has
  no hub in the build menu, and Milestone 10 neither lists nor announces it. Hubs already placed stay, and keep
  using energy; recycle them if you play that world without local storage. Switching the setting in a loaded world
  changes this on the next load, like the storage sizes.
  - How: the buildings container ships the hub's row with the game's `Features.Legacy` flag, which the build wheel
    leaves out (the game hides its retired Automators this way, and placed ones still load). The flag only decides
    what the wheel shows. As a world with local storage loads, the runtime clears the flag and adds the hub to
    Milestone 10's rewards.
  - `hardcore check` shows the hub row's flag and Milestone 10's rewards; `hardcore hub` says whether this world
    shows the hub.
- **Unlock:** Milestone 10 ("Steel Technology"). A world already past it gets the hub when it loads with local
  storage on.
- **Build menu:** the Constructs tab, with the storage buildings.
- **Cost:** 10 Steel Frames, 10 Iron Electronics and 20 Concrete.
- **Look:** its own model, made in Blender (`art/logistics_hub/`, version 3, after a concept art, "Logistics
  Station"):
  - a metal platform with cyan corner lights;
  - a blue hut with orange bands, a framed screen with a glowing drone-and-crate logo under an orange awning, a side
    vent, a back grille and a side door;
  - a two-tier roof with the orange logo sign, vents and a corner beacon;
  - a lattice tower with a white dish and an orange beacon;
  - an open canopy over shelved wooden crates in the game's own crate style, and blue pipes with orange couplings
    beside a cyan indicator.

  The textures are baked with wear, like the game's buildings: chipped paint showing bare metal at the edges, grime
  in the crevices, dirt near the ground, and wood grain. It has its own build-menu icon, 128 px like the game's,
  which the wheel shows at their own size. It is 3.9 × 3.9 m and 6.8 m tall, with a plinth under the ground that
  fills the gap on slopes. It renders with one of the game's own glowing construct materials, fed with the baked
  textures, so no shader code ships with the mod. Its collision is six boxes, which the game builds itself; the
  hub also places by them.
- **Reservoir parts switched off:** the water surface, the silo foundation and the pipe connectors lose their
  meshes. The connectors and the water-gun capsule move 100 m underground. The tank holds 0.01 L.
- **Console:** `hardcore hub` shows the hub's unlock, the hubs placed and the Energy Meter; `hardcore hub unlock`
  unlocks it now.
- **Install:** it lives in the mod's buildings container, built by `python tools/build_buildings.py install` (see
  Commands).

### Workshop Shed

The game ships a Workshop Shed but hides it (it is cut content, behind the `Features.Limbo` flag). The mod makes it
buildable again:

- **Unlock:** Milestone 1, your first delivery, alongside the Oil Presser. Worlds already past it get it when they
  load.
- **Build menu:** the Constructs tab, in the same group as the Oil Presser and Seed Extractor.
- **Cost:** 10 Wood and 5 Stone.
- **Why:** a quick building to put the first machines in, without designing one from scratch.
- **Your saves:** it uses the game's own row and Blueprint, so placed sheds stay valid even without the mod. It is
  in every world, not tied to a settings row.
- **Credit:** a mod on Nexus does the same, and it is credited in the Nexus description.
- **Settings:** `mod_config.json` under `cut_buildings` holds its name, description, cost and milestone.
- **Console:** `hardcore unlock` lists the mod's buildings and whether each is unlocked; `hardcore unlock all` (or a
  row name) unlocks them now.

### Drone Stations

Two new buildings that act as a wireless pipe between bases, so an outpost can feed the main base without laying
pipes across the map:

- **Drone Input Station:** keeps only the green input port. Pipes fill it: machines push their output in, and to pull
  from a storage, mark the items Desired in the station's Resource Filter (the game's own pipe rules).
- **Drone Output Station:** keeps only the orange output port. Pipes take from it whatever the machines and storages
  behind it ask for.
- **Linking: by paint colour.** Every input station sends to every output station painted the same colour. Stations
  start unpainted, Gray, which is a channel like any other, so the first pair works without paint. Paint stations
  to make more channels: the game has 20 paints (Color Refiner from Milestone 5, Color Mixer from Milestone 8). The
  colour is saved with the building, so links need no save of their own.
- **Drones:** each input station has one drone. When the station holds items, an output station of its colour has
  room and the grid is Energized, the drone flies to the one with the most free room (the nearest on a tie). It flies
  at 20 m/s, unloads up to 50 kg and flies back. A trip takes at least 2 s.

  | Distance between stations | Round trip | Throughput |
  |---|---|---|
  | 20 m or less | 2 s | 25 kg/s |
  | 100 m | 10 s | 5 kg/s |
  | 200 m | 20 s | 2.5 kg/s |
  | 500 m | 50 s | 1 kg/s |
  | 1 km | 100 s | 0.5 kg/s |

  More input stations of one colour add their own drones.
- **Nothing is lost:** items leave the input station only when the drone arrives. They go into the output first, then
  exactly as many leave the input. If the input can't give them all, the surplus is taken back from the output.
  Drones are not saved: after a load every drone starts at home, and the items are still in their station.
- **Not carried:** liquids. Large objects aren't items either, so they still need the mech or a trailer.
- **Unlock:** Milestone 8 ("Drones & Roads"), with the game's Watering Drone Station. Worlds already past it get the
  stations when they load. They are in every world, not tied to a settings row.
- **Build menu:** the Constructs tab, with the automation pipes.
- **Cost:** 6 Iron Frames, 4 Iron Electronics and 4 Red Crystals each, double the Watering Drone Station's.
- **Look (0.15.2):** their own models, built in Blender by `art/drone_stations/build_station.py`, styled after the
  user's concept art:
  - **The body is like Storage Box II's chest**, because it gets painted:
    - framed panels with the chest's fine diagonal ribbing;
    - the chest's thin orange stripe at lid height;
    - a row of bolts above the stripe, and two steel latches on each long side.
  - **The panels take the station's paint colour**, so you can see its channel. The exporter bakes a paint mask for
    them (`paintable` parts in `art/export_model.py`). Unpainted they are the game's Gray.
  - **The station's logo** on a screen on the right side, from the user's concept: a cube with an arrow between
    signal arcs, in cyan. The arrow points up on the input station (it sends by drone) and down on the output station
    (it receives). The focus panel can't show it: the storage template has no icon line there to swap.
  - **The role colour:** green on the input station, orange on the output station, like the game's pipe rings. It's
    on the chevrons, the beacons, the antenna and the drone's lights. The chevrons point down into an input station
    and up out of an output station.
  - **The concept's details:**
    - cyan light strips on the base's corners;
    - a landing pad with a yellow ring, beacons and an antenna mast;
    - an orange cargo drone with cyan-glowing rotor guards and an orange slatted crate.
  - **The pipe port:** the game's own ring sits on a port socket, at the back of the input station and the front of
    the output station.
  - **Icons and interaction:** own build-menu icons, and an interaction box that covers the whole station.
  - **Size:** 1.9 x 1.6 m, about 1.85 m tall with the drone (2.1 m to the top of the antenna).

  The logic is still Storage Box II's: 600 kg each, its Resource Filter, its save.
- **Energy:** 50 each on the game's Energy Meter, scaled by the playstyle like every machine's (100 on Challenging),
  so a linked pair costs what a Logistics Hub costs.
  - Drones only take off while the grid is Energized (the meter at 0 or above), as the hub only links then. A drone
    already flying finishes its trip.
  - How: Storage Box II has no energy handler, so the drone script gives each station the game's own,
    `BPC_EnergyHandler`, as the world loads. The handler reads the station's `DT_EnergyValues` row and registers with
    the game state, and unregisters when the station is demolished.
  - For scale: the Watering Drone Station uses 20, and the Diesel Generator II from the same milestone makes 250.
  - `hardcore drones` shows the meter and how many stations have their handler.
- **Console:** `hardcore drones` lists the stations by colour, how full each is, each drone's trip, and what the
  drones carried so far. The first six trips are also logged.
- **Settings:** `mod_config.json` under `drone_stations` holds the names, costs, milestone, load, speed and timings.
- **Tested in game (0.15.0):**
  - An unpainted input and output station passed items between pipe networks.
  - Painting one of them black stopped the transfers. With another station painted black too, items went to both.
  - An output station moved away from the base still received items, more slowly.
  - The own models (0.15.2) look and work right, and the energy cost (0.15.3) shows on the Energy Meter.
  - Not tried yet: saving and reloading with items in a station.

[CHANGELOG.md](CHANGELOG.md) records each version, what was tested in game and what we learned about the game
along the way.

## Runtime mode (per world, needs UE4SS)

The mod can run in two ways, both built from the same `mod_config.json`:

- **Static pak** (`install`): the changed tables are packed into `Paks\~mods`. Every world is hardcore.
- **Runtime** (`install-runtime`, current setup): a UE4SS Lua mod applies the same changes in memory, per
  feature and per world. Each feature is switched on or off for each world; worlds without it stay vanilla,
  and moving between worlds restores or re-applies the changes. `install-runtime` removes the static pak so
  the two never stack.

The build tool resolves all patterns, planet rules and overrides against the installed game and writes a
flat list of concrete edits (`edits.lua`), each tagged with its feature; the Lua mod
(`runtime/HardcoreLogistics/Scripts/main.lua`) only applies that list and keeps undo records.

Features (defined in `mod_config.json` under `features`, one settings row each):

| Feature | Row in the playstyle settings | Tables |
|---|---|---|
| `cargo` | Hardcore Logistics: Mech Cargo | `DT_Modules`, `DT_CoreUpgrades` |
| `deliveries` | Hardcore Logistics: Deliveries | `DT_Deliveries` |
| `trampling` | Hardcore Logistics: Crop Trampling | none: a live script (`Scripts/trample.lua`) |
| `storage` | Hardcore Logistics: Local Storage | `DT_StorageCapacities` (the storage sizes); `DT_Constructs` and `DT_DeliveryMilestones` (the Logistics Hub's build-menu flag and Milestone 10 reward, from the buildings' config); plus a live script (`Scripts/storage.lua`) |

Switching features per world:

- The **Hardcore Logistics** card on the new-game screen, after Challenging: it applies the game's Challenging
  preset and switches every feature on for the new world. Choosing another card switches them off again.
  Customize stays the game's screen (its Playstyle row shows Challenging); change settings there by hand.
- The rows at the end of the playstyle settings list. On the new-game Customize screen they set the world you
  are about to create; in a loaded world's Settings menu they change that world.
- `ue4ss\Mods\HardcoreLogistics\worlds.txt`: one line per save slot listing the features that are on
  (`World_3=cargo,deliveries`, `World_4=off`; an older `World_3=on` line means every feature). The slots are
  the `World_N.sav` files in `%LOCALAPPDATA%\FarMech\Saved\SaveGames`.
- With the world loaded, open the console with `~` or `F10` and type `hardcore cargo on`,
  `hardcore trampling off`, `hardcore storage on`, `hardcore on` / `hardcore off` (every feature), or
  `hardcore` (status).

A world runs with the features it was loaded with. The mod applies the table features just before the world
loads, because the game's delivery system copies the delivery table while a world loads. A change to one of
them in a loaded world is saved and applies the next time the world loads. Until then, a line right under the
changed row in the Settings menu says "Save and reload the world to apply this change." (the list scrolls to
show it). Crop trampling and local storage are scripts, so switching them applies at once, and crop trampling's
row has no such line. Local storage also owns tables, the storage sizes and the Logistics Hub's flag and reward:
like every table, they change as a world loads, so after a switch in a loaded world they follow on the next load.
Its row's line says "Save and reload the world to finish applying this change.", and `hardcore storage on` says
to reload.

`hardcore timing` shows how long each script loop takes (they run inside game frames, so a slow one shows as a
stutter at its interval). A run of 8 ms or more is also logged.

`hardcore check` (console) prints what the game is using right now: the saved and running features, the live
table values, the deliveries the delivery system is asking for, what trampling has done so far, and how many
storages are in and out of reach. The same readout goes to the log 5 s after every world load. `hardcore mounds` shows where the mod thinks each mech
meets the ground, and the heights it chose that from. It then lists the mounds around each mech (plant,
distance, height, and whether it is under the mech), for tuning the trampling numbers.

UE4SS (v3.0.1-1217, from github.com/UE4SS-RE/RE-UE4SS) lives in `FarMech\Binaries\Win64` as `dwmapi.dll` plus
the `ue4ss` folder; deleting those two removes it. Its log, `ue4ss\UE4SS.log`, shows every line from this mod
(prefixed `[HardcoreLogistics]`).

The scripts run their polls on the game thread through UE4SS's game-thread timers (`api.loop` in `main.lua`).
`LoopAsync` runs Lua on a second thread at the same time as the game thread, and that crashed the game in 0.8.2.
For the same reason, never read the arrays UE4SS returns through out-parameters (such as `GetAttachedActors`): they
point into memory the game has already freed. Use return values and properties instead. Don't keep a game object from
one check to the next either: find it again each time, and keep only names or numbers in between. Objects that can
vanish (sound components, actors of players leaving, anything in an unloaded map) are freed by the game, and
touching them crashed it in 0.8.9.

```bash
python tools/build_mod.py install-runtime
```

```bash
python tools/build_mod.py disable-runtime
```

`runtime` and `install-runtime` first check the Lua scripts with `tools/check_lua.py`: it compiles them with
Lua 5.4 (the version UE4SS embeds) and flags unknown global names, which in Lua are usually typos or a local
function called above its declaration and would otherwise only fail in the game. A failed check stops the
install. The check needs the `lupa` package in a repo-local venv (one-time setup; without it the check is
skipped with a note):

```bash
uv venv .venv
```

```bash
uv pip install --python .venv/Scripts/python.exe lupa
```

## Removing the mod from a world you keep

What happens to a world when the mod goes (the runtime mod, the buildings container, or both):

- **Table changes and settings:** they live in memory and in `worlds.txt`, never in the save, so the world is
  vanilla again: mech cargo, deliveries and storage sizes.
- **Full storages:** a storage holding more than its vanilla size keeps everything and shows itself over capacity
  (tested in game with local storage switched off).
- **Local storage tags:** the save does not keep them (checked in 0.9.0), so every storage counts across the base
  again.
- **Unlocks:** the save's list of unlocked buildings keeps the mod's names. The game ignores names it has no
  building row for: World 3 kept loading after the test hubs II and III were removed in 0.13.2 while still in its
  list.
- **Workshop Shed:** it is the game's own building, so placed sheds stay. It just leaves the build menu again.
- **Placed Logistics Hubs: not tested yet.** The save stores placed buildings by their Blueprint class, and the
  hub's Blueprint ships only with the mod. What the game does with a saved building whose class is gone is
  unknown: it might skip it or fail to load the world. Until that is tested, recycle every hub first, save, and keep
  a copy of the `World_N.sav` file (in `%LOCALAPPDATA%\FarMech\Saved\SaveGames`) from before.

## How it works

`tools/build_mod.py` reads the tables straight out of the installed game, changes only the numbers (and adds
only the map entries) listed in `mod_config.json`, checks that nothing else changed, and writes an IoStore mod container
(`HardcoreLogistics_P.pak/.utoc/.ucas`, the same layout retoc produces). Because it always starts from the
installed game's tables, a game update never gets reverted by a stale copy: just run `install` again.

Requirements: Python 3.10+ and Epic's `oo2core_9_win64.dll` (ships with every Unreal Engine install under
`Engine\Binaries\DotNET\AutomationTool`; found automatically under `D:\UE_*` or set `LF_OODLE_DLL`).
Set `LF_GAME_DIR` if the game is not in the default Steam folder.

## Commands

```bash
python tools/build_mod.py show DT_Modules RightArm
```

```bash
python tools/build_mod.py show DT_Deliveries Polyberry_ --modded
```

```bash
python tools/build_mod.py install
```

```bash
python tools/build_mod.py uninstall
```

`show` prints a table's current values (row filter optional); with `--modded` it prints the values in your
last build instead, so you can check a change before launching the game. `install` builds into `dist/` and
copies the three files to `FarMech\Content\Paks\~mods`, `uninstall` removes them again.

```bash
python tools/build_buildings.py install
```

`build_buildings.py` builds the mod's buildings into their own container, `HardcoreLogisticsBuildings_P`, and copies
it to `Paks\~mods` (close the game first). It handles two kinds:

- **New buildings** (`mod_config.json` under `hub`, the Logistics Hub): it copies a template construct's Blueprint
  into a new class (`legacy_package.py`) and adds a new row to `DT_Constructs` (`legacy_table.py`).
- **Cut buildings** (under `cut_buildings`, the Workshop Shed): it changes the building's own row, dropping the
  `Features.Limbo` flag and setting its name, description and cost.

Each building goes into its milestone's reward list. The build then verifies the result: every other row must match
the game's.

It needs retoc (github.com/trumank/retoc, v0.1.5) in `modding_tools\retoc\v0.1.5\` next to the repo, or set
`LF_RETOC`. `build` only writes `dist/buildings/`. `uninstall` removes it from `~mods`, together with the container's
earlier name, `HardcoreLogisticsHub_P`.

### Building models (Blender to the game)

A new building with a `model` in `mod_config.json` (the Logistics Hub) gets its own mesh and icon instead of its
template's. Three steps, each repeatable:

1. **Blender:** `art/<model>/` holds the `.blend`, and for the hub also `build_hub.py`, which rebuilds the parts
   from code. The `.blend` has three collections:
   - `<Model>`: the parts, with flat materials. Emission marks what glows. Each material's `hl_kind` (paint, metal,
     wood, glow, screen) and `hl_wear` say how the bake wears it.
   - `Collision`: the `UBX_SM_<Model>_NN` boxes.
   - `Preview`: the camera and light.

   Running `art/export_model.py` inside Blender (the docstring shows the one-liner) does three things:
   - **Flicker check:** it first checks that no two parts have faces in the same plane, facing the same way, where
     they overlap. The game draws such faces at the same depth and they flicker, which is what 0.12.1's crates did.
   - **Merge and bake:** it merges the parts, unwraps them, and bakes their materials in Cycles at 2048 px.
     - Paint: colour blotches, edges chipped down to bare metal plus scattered chips, crevice grime, and dirt near
       the ground.
     - Metal: blotches, brighter edges, grime and dirt.
     - Wood: grain along each part's length, lighter worn edges.
     - Glow: clean.
     - Normal map: rounded edges, in Unreal's convention.
   - **Writes next to the `.blend`:**
     - `SM_<Model>.fbx`: the merged mesh, with one material slot, UVs and tangents, plus the boxes.
     - `T_<Model>_Albedo/ORM/Emissive/Normal.png`, and a black paint mask.
     - `T_<Model>Icon.png`: a 128 px render of the baked mesh (parts named `Plinth*` left out), framed to fill the
       square, on a transparent background.
2. **Unreal 4.27** (the game's version, `D:\UE_4.27` or `LF_UE427`): `python tools/cook_art.py` rebuilds the
   project's content from scratch.
   - **Import:** it imports the files into the art project `unreal/HLArt.uproject` (`unreal/Scripts/import_art.py`).
   - **Material:** `MI_<Model>` is a material instance of the game's own `MI_AnimalOverviewer`. That is the
     Water Tower's master material with paint and glow switched on and no blinking. Only its five textures and its
     `Emissive Color` change, so it renders with the game's compiled shader and no shader code ships.
   - **Cook:** it cooks for WindowsNoEditor, unversioned like the game, into `dist/art/`.
   - **Stand-ins:** to cook against the game's material, the project holds stand-ins at the game's own paths
     (`MI_AnimalOverviewer` and its textures) and a stand-in master (`/Game/CookStubs`). These are never copied. The
     tool also checks that everything the cooked packages reference outside `/Game/HardcoreLogistics` exists in the
     game.
   - **Collision:** boxes only, because **the game runs Chaos physics**, and this engine cooks PhysX data the game
     cannot read. 0.12.0's convex hulls left the hub with no collision at all, so the recycle tool could not select
     it. Boxes are plain numbers the game turns into shapes itself, and they are used for traces too. 4.27 still
     writes an empty PhysX header into every mesh; the tool patches it out, and it refuses a mesh whose cooked
     collision holds any shape.
3. **Pack:** `python tools/build_buildings.py install`.
   - **Mesh and icon:** it points the mesh the template's StaticMesh component shows at `SM_<Model>` and the row's
     `Icon` at `T_<Model>Icon`, then packs the cooked files with the rest.
   - **Template edits:** `template_edits` rewrites values the template's components already set, in place. The hub
     uses it to switch off the reservoir's water parts.
   - **Energy:** `energy` adds a `DT_EnergyValues` row and sets the template's energy handler.
   - **Status text:** `function_edits` swaps literals in one of the template's Blueprint functions without moving any
     other bytecode.
     - A string-table text (`texts`) becomes our own text, sized to the same in-memory length. Jump offsets count in
       memory; only the on-disk script size grows by 4.
     - A string (`strings`) becomes another of the same length.
     - The hub uses it for its focus panel: `StatusConditions`. `status_icon` is the icon cooked for it.
   - **Checks:** the container may hold nothing outside `/Game/HardcoreLogistics` except the tables. The verify step
     reads the Blueprint's zen import map to confirm it imports the new mesh and not the template's. It reads every
     edited value back from the packed Blueprint, and checks the energy row.
   - **Stale cook:** it warns when the art changed after the last cook.

A model should fit its template's footprint. The Water Reservoir places by the model's own collision boxes. In
Blender the front faces −Y, which becomes +Y in Unreal, and 1 Blender metre is 100 Unreal units.

## Releasing

```bash
python tools/release.py
```

It builds both parts fresh, so each runs its own checks: the runtime mod (`build_mod.py`) and the buildings container
(`build_buildings.py`). Then it packs `dist/release/HardcoreLogistics-<version>.zip`, laid out like the game folder so
players extract it into the game's install folder:

- `FarMech/Content/Paks/~mods/HardcoreLogisticsBuildings_P.pak`, `.utoc`, `.ucas`: the buildings.
- `FarMech/Binaries/Win64/ue4ss/Mods/HardcoreLogistics/Scripts/*.lua`: the UE4SS mod, `edits.lua` included.
- `FarMech/Binaries/Win64/ue4ss/Mods/HardcoreLogistics/enabled.txt`: UE4SS 3.0.1 loads a mod folder holding this file,
  so players don't edit `mods.txt`.
- `Hardcore Logistics - Read me.txt`: `release/README.txt`, with the version filled in.

Not packed:
- **Each player's `worlds.txt`:** the mod writes it the first time a choice is made, and reads a missing one as
  "every feature off".
- **Players' own UE4SS:** players install UE4SS v3.0.1 themselves.

The version is `mod_config.json` `"version"`. The runtime logs it at load ("loaded version ..." in
`ue4ss/UE4SS.log`).

The Nexus page text, a summary and the BBCode description, is in `release/nexus_description.bbcode`. Fill in the
Workshop Shed credit before posting.

## Editing values

`features` lists the settings rows: an id (lower case, used in `worlds.txt` and the console), the row's
label, and the tables it owns. Every table in `tables` belongs to exactly one feature; the build stops
otherwise. A new feature gets its own row automatically, and the playstyle card switches it on too. A live
feature (`"live": true`) owns no tables: it is a script that checks whether the loaded world runs with it, and
switching it applies at once. `trampling` and `storage` are the live ones.

`storage` holds its numbers:

- `reach_cm` (1500): how close to the spot a menu or station asks about a storage must be to count, measured
  flat. A storage already in reach leaves it only 1 m further out, so a spot at the edge doesn't flip it. `0`: no
  storage counts, only the mech's inventory, as outside a base.
- `check_ms` (1000): how often the script looks whether the feature was switched off. It touches nothing in
  between: the storages are checked only when a menu or station asks for the base inventory. The same spot asking
  again is checked at most every 3 s, and a spot 2 m away at once.
- `storage_class` (optional): the storage class the game lists,
  `/Game/Blueprints/Constructs/BP_StorageConstruct.BP_StorageConstruct_C`.

`trampling` holds its numbers:

- `radius_cm` (150): on legs, how far from the mech's centre a crop dies.
- `foot_radius_cm` (75): on legs, how far from each foot a crop dies.
- `sound`: the FMOD event played at each crushed mound, or `""` for none. The default is a bush breaking
  (`/Game/FMOD/Events/Break/Break_Bush`); the Field Plow's removal sound is
  `/Game/FMOD/Events/TransformModes/Plough/Crops/Plough_Remove_Tile_Crop`.
- `sounds_at_once` (2): how many crush sounds may play together. FMOD cuts off the oldest copy of a sound when too
  many start, which turns them into clicks.
- `sound_gap_ms` (0): the shortest time between two crush sounds.
- `sound_cut_ms` (`[750, 500, 400, 300, 200, 100]`): a list of windows in ms (one number also works). Past
  `sounds_at_once`, each window lets one more crunch start over the oldest one's ending:
  - `[750, 500, 400, 300, 200, 100]` lets a 3rd start once the oldest has at most 750 ms left, a 4th at 500 ms,
    and so on to an 8th at 100 ms, so at most 8 play at once.
  - The most at once is `sounds_at_once` plus the number of windows.
  - The oldest is never stopped; it plays out (or FMOD trims its tail).
  - `[]` or `0` means never more than `sounds_at_once`.
  - The bush crunch is about 1.4 s long.
  - `hardcore check` counts how many crunches each window let in.
- `vehicle_sound_max_cm` (1000): in car, tractor and flight mode, a crunch further than this from the camera
  plays this far from it instead, in the same direction. `0` turns this off. On legs the crunch always plays on
  its mound.
- `max_height_cm` (120): how high above a mound the mech's feet can be and still crush it.
- `min_move_cm` (10): how far the mech must move before it tramples.
- `check_ms` (100): how often each mech is checked.

`mode` is the playstyle card: its `title`, `description`, and `base_preset`, the game preset it applies
(`Balanced`, `Challenge`, `Creative` or `Relaxed`; the card sits after that preset's card).

Each entry in `tables` is `table -> row -> value path -> new value`.

Rows are exact names (`HaulerRightArm`) or patterns (`*_6` = every row ending in `_6`), optionally with a
condition on a field (`*_6 [PlanetName=Hewstone]`). Pattern rows that don't have the path are skipped, but
each entry must change at least one value.

Paths:

- `MaxHauling` a plain field
- `Stats[Tag=Upgrade.Hauling.Capacity].Value` the array element whose `Tag` matches, then its field
- `Cost[IronFrame]` a map entry by key
- `Cost[*]` every entry of a map (or every element of an array)
- `Cost[+IronElectronics]` adds a new map entry (item names must be rows of `DT_Items`)

Values are numbers, or a multiplier like `"x1.5"` (whole numbers are rounded, to the nearest 5 from 50 up).
Keys starting with `_` are notes and are ignored. Numbers can be changed and map entries added; removing
entries, new rows and text edits are not supported yet.

Entries apply in file order, so a later entry overrides an earlier one for the same value, including entries
an earlier rule added. That gives three levels of control for deliveries: set a tier-wide rule, then a planet
rule, then fine-tune single tasks at the end of the table:

```json
"*_8":                         { "Cost[SteelFrame]": 15 },
"*_8 [PlanetName=Wildernest]": { "Cost[+ClearLens]": 8 },
"Polyberry_8":                 { "Cost[ClearLens]": 20, "Cost[SteelFrame]": 30, "Cost[+Concrete]": 10 }
```

Delivery rows are named `<Line>_<tier>`: `Wheat`, `Rabbage`, `Chromaize` (Hewstone), `Polyberry`, `Caroot`,
`Papristalk` (Wildernest), `Honeybottle`, `CottonCrop`, `Feather` (Cryolis), `Lumbloom`, `Zappertwig`,
`GloFruit` (Tempest), `Coilvine`, `Quartznip`, `AmberFragments` (Verdemere), tiers 1-10. Use the item IDs from
`DT_Items` (for example `IronMechanicalParts` is Iron Parts, `CubeMetalRefined` is Fractalite Bar); the build
stops on an unknown ID.

## Notes

- Other mods that replace the same tables (`DT_Modules`, `DT_CoreUpgrades`, `DT_Deliveries`) conflict with
  this one; the last-loaded wins.
- Unload hauled Large Objects before loading a save with the mod if you carry more than the new capacity.
- Crop trampling needs authority over the crops: in co-op it runs on the host's copy of the mod and covers every
  player's mech there. A client's copy does nothing.
- Local storage measures from every player the host's copy can see. It has not been tried in co-op.

## Roadmap

From the design doc ([../Lightyear_Frontier_Hardcore_Mod_Design_and_Discussion-1.md](../Lightyear_Frontier_Hardcore_Mod_Design_and_Discussion-1.md)).
Its three releases: Phase 1, physical constraints (cargo rebalance, no shared inventory, crop trampling);
Phase 2, industrial progression (bigger later requirements, production rates, throughput info); Phase 3,
advanced logistics. Done so far (0.8.0): the mech cargo rebalance and crop trampling from Phase 1, the bigger
deliveries from Phase 2, and the per-world settings rows and playstyle card every feature plugs into.

| # | Feature | Status | Approach |
|---|---|---|---|
| 2 | Cargo rebalance | Mech side done (0.1.0). Trailers and chip Power costs left as is for now | Data (this tool) |
| - | Selectable mode | Done and tested: per-world runtime switch (0.4.0), settings rows on the new-game Customize screen and in the Settings menu (0.5.0), one row per feature with a reload line under the changed row (0.6.0, 0.6.1). A 5th playstyle card, Hardcore Logistics, tested (0.7.1, 0.7.2) | UE4SS Lua |
| 7 | Bigger task quantities | Component amounts done and tested (0.2.0). Planet-themed extra components done and tested (0.3.0). Research deliveries (`DT_ResearchDeliveryPools`) unchanged | Data (this tool) |
| 1 | Crop trampling | Done and tested (0.8.1–0.8.16): legs (body circle and feet), tractor, car, the immediate mound return, the crash fixes and the crush sound (a bush breaking, up to 8 overlapping, within 10 m of the camera in vehicles). The sound still needs some tuning; kept as is for now. The mech's body kills the plants it passes over, in every mode; the mounds stay. Trailer wheels not included | UE4SS Lua calling the crop manager |
| 8 | Drone Logistics Stations | Done and tested (0.15.0): an input and an output station (Storage Box II copies, one port each; own models in 0.15.1, restyled after the user's concept in 0.15.2, tested), linked by paint colour; one drone per input station carries up to 50 kg per trip at 20 m/s; 50 energy each, double cost (0.15.3, tested); Milestone 8 | Copied Blueprints with template edits (`build_buildings.py`); transfer script (`drones.lua`) using the inventory's own functions |
| 3 | Local base inventory | Done and tested (0.9.0): a storage counts only while a player is within 15 m of it. Storages hold twice as much while it is on (0.14.0, tested: switching it off leaves full storages over capacity, which the game allows) | UE4SS Lua, using the game's own `NoRemoteInventoryAccess` storage tag; no native hook needed |
| 4 | Logistics Hub | Done and tested (0.10.0–0.13.1), final cost set (0.13.2): a new building, unlocked at Milestone 10, that keeps its base's storage shared. Its own Blender model with baked wear, wooden crates and icon; built on the Water Reservoir (no E action); uses 100 energy (200 on Challenging) and only works while Energized; its own focus-panel line and icon. Costs 10 Steel Frames, 10 Iron Electronics and 20 Concrete. Only in worlds with local storage on (0.14.1, not yet tested in game) | Copied Blueprint + new `DT_Constructs` row + milestone reward (`build_buildings.py`, retoc); model: Blender export, Unreal 4.27 cook (`cook_art.py`) with the game's own material; Lua for the effect |
| - | Workshop Shed | Built (0.11.0), not yet tested in game: the cut Workshop Shed, buildable from Milestone 1 for 10 Wood and 5 Stone | Its own row un-hidden + milestone reward (`build_buildings.py`) |
| 5 | Two-event crop rotation | Not started | Script + own save file |
| 6 | Rotation UI | Not started | Item text + custom widget |
