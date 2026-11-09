Hardcore Logistics {version} for Lightyear Frontier 1.0
===================================================

A reworked and rebalanced modded experience for players who like a planning challenge.


WHAT IT CHANGES
---------------
- Lower mech cargo: the mech carries fewer large objects, so trailers become the way to move bulk
  cargo.
- Bigger material deliveries: planet deliveries ask for real batches of components.
- Crop trampling: the mech crushes the crops it walks over, so fields need paths.
- Local base storage: only the storage near you counts for crafting, building and deliveries.
  To make up for it, storages hold twice as much.
- Logistics Hub (Milestone 10, with local base storage on): links all storage in its Home Area
  again. Needs power.
- Delivery Drone Stations (Milestone 8, their own setting): an Input and an Output station carry
  items between bases by drone, like a pipe without the pipe. Stations painted the same colour are
  linked; unpainted ones share the Gray channel. Farther apart is slower. Need power.
- Workshop Shed (Milestone 1): the game's cut Workshop Shed, buildable again.


REQUIREMENTS
------------
- Lightyear Frontier 1.0 on Steam (version 1.0.2563).
- UE4SS v3.0.1: https://github.com/UE4SS-RE/RE-UE4SS/releases/tag/v3.0.1
  Install it into <game folder>\FarMech\Binaries\Win64 (dwmapi.dll and the ue4ss folder go there).


INSTALL
-------
1. Install UE4SS v3.0.1 (see above) if you haven't yet.
2. Close the game.
3. Extract this zip into the game's install folder: the folder that holds the FarMech folder.
   (Steam: right-click Lightyear Frontier > Manage > Browse local files.)
   It adds:
     FarMech\Content\Paks\~mods\HardcoreLogisticsBuildings_P.pak / .utoc / .ucas
     FarMech\Binaries\Win64\ue4ss\Mods\HardcoreLogistics
4. Start the game.


PLAYING
-------
- New world: pick the Hardcore Logistics card (after Challenging). It starts from Challenging and
  turns every part of the mod on.
- Any world: in Settings, the rows starting "Hardcore Logistics:" turn each part on or off for
  that world. Some changes need a save and reload; the menu tells you when.
- Worlds you already have start with the mod's settings off. Buildings you have already earned
  unlock when the world loads.


UNINSTALL
---------
- First recycle every Logistics Hub and Drone Station, and keep a backup of your save
  (%LOCALAPPDATA%\FarMech\Saved\SaveGames). What the game does with them once their files are
  gone has not been tested.
- Then delete FarMech\Content\Paks\~mods\HardcoreLogisticsBuildings_P.* and the folder
  FarMech\Binaries\Win64\ue4ss\Mods\HardcoreLogistics.
- Everything else goes back to normal: the mod's settings and numbers are not saved into your
  world, and storages that are fuller than normal keep their items.


GOOD TO KNOW
------------
- After a game update, remove the mod until it is updated too: it carries copies of some game
  tables (buildings, milestones, energy) made for version 1.0.2563.
- Other mods that replace the same tables (DT_Constructs, DT_DeliveryMilestones, DT_EnergyValues)
  conflict with this one.
- Co-op has not been tested.
- Console (~ or F10): "hardcore" shows the status; "hardcore check", "hardcore storages",
  "hardcore hub" and "hardcore drones" show details. UE4SS's log (ue4ss\UE4SS.log) has every line
  from the mod, starting with [HardcoreLogistics].


CREDITS
-------
Source code (MIT license): https://github.com/Cosmanos/lightyear-frontier-hardcore-logistics
UE4SS by the UE4SS team. retoc by trumank was used to build the buildings.
