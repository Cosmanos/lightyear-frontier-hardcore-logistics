"""Build the Nexus release of Hardcore Logistics.

    python tools/release.py

Builds the runtime mod (build_mod.py) and the buildings container (build_buildings.py) fresh, so both run their own
checks, then packs one zip laid out like the game folder, to extract into the game's install folder (the one that holds
FarMech):

  FarMech/Content/Paks/~mods/HardcoreLogisticsBuildings_P.pak, .utoc, .ucas     the buildings
  FarMech/Binaries/Win64/ue4ss/Mods/HardcoreLogistics/Scripts/*.lua             the UE4SS mod, edits.lua included
  FarMech/Binaries/Win64/ue4ss/Mods/HardcoreLogistics/enabled.txt               UE4SS loads the mod without a mods.txt line
  Hardcore Logistics - Read me.txt                                              release/README.txt, with the version

Never packed: worlds.txt, each player's own per-world choices (the mod writes it the first time a choice is made).
Output: dist/release/HardcoreLogistics-<version>.zip (mod_config.json "version"). The game must be installed: the
build reads its tables. The cooked art in dist/art must exist (tools/cook_art.py).
"""
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_buildings  # noqa: E402
import build_mod  # noqa: E402

REPO = build_mod.REPO
OUT = os.path.join(REPO, "dist", "release")
MODS = "FarMech/Binaries/Win64/ue4ss/Mods/" + build_mod.RUNTIME_NAME
PAKS = "FarMech/Content/Paks/~mods"
README = "Hardcore Logistics - Read me.txt"


def main() -> None:
    cfg = build_mod.load_config()
    version = cfg.get("version")
    if not version:
        raise SystemExit("mod_config.json has no \"version\"")
    runtime = build_mod.build_runtime()
    containers = build_buildings.build()
    scripts = os.path.join(runtime, "Scripts")
    lua = sorted(f for f in os.listdir(scripts) if f.endswith(".lua"))
    if "edits.lua" not in lua or "main.lua" not in lua:
        raise SystemExit(f"the runtime build in {scripts} is incomplete: {lua}")
    readme = open(os.path.join(REPO, "release", "README.txt"), encoding="utf-8").read().replace("{version}", version)

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"HardcoreLogistics-{version}.zip")
    if os.path.exists(path):
        os.remove(path)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in containers:
            z.write(f, f"{PAKS}/{os.path.basename(f)}")
        for f in lua:
            z.write(os.path.join(scripts, f), f"{MODS}/Scripts/{f}")
        z.writestr(f"{MODS}/enabled.txt", "")
        z.writestr(README, readme.replace("\n", "\r\n"))
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        bad = [n for n in names if n.lower().endswith("worlds.txt")]
        if bad:
            raise SystemExit(f"the zip holds a worlds file: {bad}")
        for n in names:
            print(f"  {z.getinfo(n).file_size:>12,}  {n}")
    print(f"release: {path} ({os.path.getsize(path):,} bytes, {len(names)} files)")


if __name__ == "__main__":
    main()
