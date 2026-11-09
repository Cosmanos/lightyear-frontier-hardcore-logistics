"""Import the building models into the art project (unreal/HLArt.uproject) and cook them for the game.

    python tools/cook_art.py

Every building in mod_config.json hub.buildings or drone_stations.buildings with a "model" gets one. The model's
files are in art/<folder>/
(the model name in snake_case: LogisticsHub -> art/logistics_hub), exported from its .blend by art/export_model.py.
Unreal Engine 4.27, the game's version, imports them (unreal/Scripts/import_art.py) and cooks them for
WindowsNoEditor, unversioned like the game's own packages. The cooked packages of /Game/HardcoreLogistics land in
dist/art/FarMech/Content/HardcoreLogistics/, where build_buildings.py packs them. Nothing else from the cook is
copied: the material stand-ins at the game's own paths must never ship.

The material is a child of the game's MI_AnimalOverviewer: the same construct master as the Water Tower (masked, paint)
with the glow switched on, and no blinking. Only its five textures and its Emissive Color change, so it renders with the
game's compiled shader. Collision is boxes only (see import_art.py): the game runs Chaos physics and cannot read the
PhysX data this engine cooks. The empty PhysX header 4.27 still writes is patched out of the cooked mesh, and a mesh
whose cooked collision holds any shape is refused (fix_collision).

The project's Content and cooked output are rebuilt from scratch every run. Logs: dist/art/import.log, cook.log.
Engine: D:/UE_4.27, or set LF_UE427 to the engine folder.
"""
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time

TOOLS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TOOLS)
PROJECT_DIR = os.path.join(REPO, "unreal")
PROJECT = os.path.join(PROJECT_DIR, "HLArt.uproject")
SCRIPT = os.path.join(PROJECT_DIR, "Scripts", "import_art.py")
OUT = os.path.join(REPO, "dist", "art")
DEST_ROOT = "/Game/HardcoreLogistics/Art"
GAME_MATERIALS = "/Game/Graphics/Constructs/AnimalOverviewer/AnimalOverviewer_Materials"
PARENT = f"{GAME_MATERIALS}/MI_AnimalOverviewer"     # the game's; a stand-in here
STUB_MASTER = "/Game/CookStubs/M_ConstructStub"
STUB_TEXTURES = {k: f"{GAME_MATERIALS}/T_AnimalOverviewer_{k}" for k in ("Albedo", "Emissive", "Normal", "ORM", "Mask")}
EMISSIVE_COLOR = (1.0, 1.0, 1.0, 1.0)               # multiplies the emissive palette
SOURCES = ("SM_{m}.fbx", "T_{m}_Albedo.png", "T_{m}_ORM.png", "T_{m}_Emissive.png", "T_{m}_Normal.png",
           "T_{m}_Mask.png", "T_{m}Icon.png")
COOKED = ("SM_{m}", "MI_{m}", "T_{m}_Albedo", "T_{m}_ORM", "T_{m}_Emissive", "T_{m}_Normal", "T_{m}_Mask",
          "T_{m}Icon")
UE_FLAGS = "-unattended -nopause -nosplash -stdout -FullStdOutLogOutput -NoLogTimes"


def snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def models() -> list[dict]:
    """{name, folder, status_icon or None} per model named by a new building (hub.buildings, drone_stations.buildings).
    A status icon (a focus-panel icon, art/<folder>/<icon>.png) is cooked straight into
    /Game/HardcoreLogistics/Art/<icon>: its soft path has to be as long as the one it replaces in the template's
    bytecode."""
    with open(os.path.join(REPO, "mod_config.json"), encoding="utf-8") as fh:
        cfg = json.load(fh)
    out = {}
    for b in cfg.get("hub", {}).get("buildings", []) + cfg.get("drone_stations", {}).get("buildings", []):
        m = b.get("model")
        if not m:
            continue
        if not m.isidentifier():
            raise SystemExit(f"building {b.get('row')}: model must be a plain name (got {m!r})")
        entry = out.setdefault(m, {"name": m, "folder": os.path.join(REPO, "art", snake(m)), "status_icon": None})
        if b.get("status_icon"):
            entry["status_icon"] = b["status_icon"]
    return list(out.values())


def model_sources(m: dict) -> list[str]:
    extra = [f"{m['status_icon']}.png"] if m.get("status_icon") else []
    return [os.path.join(m["folder"], s.format(m=m["name"])) for s in list(SOURCES) + extra]


def extra_dir() -> str:
    """Where textures cooked straight into /Game/HardcoreLogistics/Art (status icons) land."""
    return os.path.join(OUT, "FarMech", "Content", *DEST_ROOT[len("/Game/"):].split("/"))


def cooked_dir(model: str) -> str:
    return os.path.join(OUT, "FarMech", "Content", *DEST_ROOT[len("/Game/"):].split("/"), model)


def engine_cmd() -> str:
    root = os.environ.get("LF_UE427") or r"D:\UE_4.27"
    exe = os.path.join(root, "Engine", "Binaries", "Win64", "UE4Editor-Cmd.exe")
    if not os.path.isfile(exe):
        raise SystemExit(f"Unreal Engine 4.27 not found at {root} (set LF_UE427 to the engine folder)")
    with open(os.path.join(root, "Engine", "Build", "Build.version"), encoding="utf-8") as fh:
        v = json.load(fh)
    if (v["MajorVersion"], v["MinorVersion"]) != (4, 27):
        raise SystemExit(f"{root} is Unreal {v['MajorVersion']}.{v['MinorVersion']}; the game needs 4.27")
    return exe


def run_ue(exe: str, args: str, log_name: str, env: dict | None = None) -> tuple[int, str]:
    # one command-line string: Unreal reads -script="..." itself, and the repo path has spaces
    cmd = f'"{exe}" "{PROJECT}" {args} {UE_FLAGS}'
    log_path = os.path.join(OUT, log_name)
    t0 = time.time()
    with open(log_path, "w", encoding="utf-8", errors="replace") as log:
        res = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, timeout=3600)
    with open(log_path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    print(f"  {log_name}: exit {res.returncode} after {time.time() - t0:.0f} s")
    return res.returncode, text


def log_problems(text: str, limit: int = 15) -> list[str]:
    lines = [ln for ln in text.splitlines() if re.search(r"\bError\b|: Error:|Fatal", ln) and "Warning" not in ln]
    return lines[:limit]


def main() -> None:
    todo = models()
    if not todo:
        print("no hub building has a model; nothing to cook")
        return
    missing = [p for m in todo for p in model_sources(m) if not os.path.isfile(p)]
    if missing:
        raise SystemExit("missing model files (export them with art/export_model.py):\n  " + "\n  ".join(missing))
    exe = engine_cmd()
    os.makedirs(OUT, exist_ok=True)
    for d in (os.path.join(PROJECT_DIR, "Content"), os.path.join(PROJECT_DIR, "Saved", "Cooked"),
              os.path.join(OUT, "FarMech")):
        shutil.rmtree(d, ignore_errors=True)
    os.makedirs(os.path.join(PROJECT_DIR, "Content"), exist_ok=True)

    spec = {"models": [{"name": m["name"], "folder": m["folder"], "status_icon": m["status_icon"]} for m in todo],
            "dest_root": DEST_ROOT,
            "parent": PARENT, "stub_master": STUB_MASTER, "stub_textures": STUB_TEXTURES,
            "emissive_color": EMISSIVE_COLOR, "report": os.path.join(OUT, "import_report.json")}
    spec_path = os.path.join(OUT, "import_spec.json")
    with open(spec_path, "w", encoding="utf-8") as fh:
        json.dump(spec, fh, indent=1)
    if os.path.exists(spec["report"]):
        os.remove(spec["report"])

    # the Python commandlet splits its -script value at spaces (and runs it as code when the first piece is not a
    # file), so it runs a copy from a folder whose path has none; the script finds everything else through the spec
    script_dir = os.path.join(tempfile.gettempdir(), "hl_art")
    if " " in script_dir:
        raise SystemExit(f"the temp folder {script_dir} has spaces; set TEMP to a folder without")
    os.makedirs(script_dir, exist_ok=True)
    script = os.path.join(script_dir, "import_art.py")
    shutil.copy2(SCRIPT, script)
    print(f"importing {', '.join(m['name'] for m in todo)} into {PROJECT}")
    code, text = run_ue(exe, f'-run=pythonscript -script={script.replace(os.sep, "/")}', "import.log",
                        dict(os.environ, HL_ART_SPEC=spec_path))
    report = {}
    if os.path.exists(spec["report"]):
        with open(spec["report"], encoding="utf-8") as fh:
            report = json.load(fh)
    if not report.get("ok"):
        raise SystemExit("import failed (dist/art/import.log):\n" + (report.get("error") or
                         "\n".join(log_problems(text)) or text[-3000:]))
    for name, info in report["models"].items():
        print(f"  {name}: {json.dumps(info)}")

    print("cooking for WindowsNoEditor (unversioned)")
    code, text = run_ue(exe, "-run=cook -targetplatform=WindowsNoEditor -unversioned", "cook.log")
    if code != 0:
        raise SystemExit("cook failed (dist/art/cook.log):\n" + "\n".join(log_problems(text)) + "\n" + text[-2000:])
    cooked_root = os.path.join(PROJECT_DIR, "Saved", "Cooked", "WindowsNoEditor", "HLArt", "Content")
    others = []
    for dirpath, _dirs, files in os.walk(cooked_root):
        rel = os.path.relpath(dirpath, cooked_root).replace("\\", "/")
        if not rel.startswith("HardcoreLogistics"):
            others += [f"{rel}/{f}" for f in files if f.endswith(".uasset")]
    for m in todo:
        src = os.path.join(cooked_root, *DEST_ROOT[len("/Game/"):].split("/"), m["name"])
        dst = cooked_dir(m["name"])
        if not os.path.isdir(src):
            raise SystemExit(f"the cook wrote nothing for {m['name']} ({src})")
        shutil.copytree(src, dst)
        want = [f"{c.format(m=m['name'])}{ext}" for c in COOKED for ext in (".uasset", ".uexp")]
        lost = [w for w in want if not os.path.isfile(os.path.join(dst, w))]
        if lost:
            raise SystemExit(f"cooked {m['name']} is missing {lost}")
        files = sorted(os.listdir(dst))
        size = sum(os.path.getsize(os.path.join(dst, f)) for f in files)
        print(f"  {m['name']}: {len(files)} cooked files, {size:,} bytes -> {dst}")
        for line in check_references(dst):
            print(f"    uses the game's {line}")
        fix_collision(dst, m["name"])
        if m.get("status_icon"):
            icon_src = os.path.join(cooked_root, *DEST_ROOT[len("/Game/"):].split("/"), m["status_icon"])
            copied = [icon_src + ext for ext in (".uasset", ".uexp", ".ubulk") if os.path.isfile(icon_src + ext)]
            if len(copied) < 2:
                raise SystemExit(f"the cook wrote no {m['status_icon']} ({icon_src}.uasset)")
            for f in copied:
                shutil.copy2(f, extra_dir())
            print(f"    status icon {m['status_icon']}: {sum(os.path.getsize(f) for f in copied):,} bytes")
    print(f"  not copied (stand-ins and engine content the game already has): {len(others)} packages, e.g. "
          + ", ".join(o for o in others if "Graphics" in o or "CookStubs" in o))


def body_setup_tail(pkg):
    """(export, its bytes, offset of bCooked) of a cooked mesh's BodySetup. After the tagged properties come the
    UObject has-GUID flag (and GUID), BodySetupGuid, then bool bCooked, bool bHasCookedCollisionData and the format
    container: int32 count, then per format an FName and an inline FByteBulkData (uint32 flags, int32 count,
    int32 size, int64 offset, payload)."""
    from uasset import _Reader
    body = next(e for e in pkg.export_entries() if e["name"].startswith("BodySetup"))
    start = body["offset"] - pkg.total_header_size
    data = pkg.uexp[start:start + body["size"]]
    r = _Reader(data, pkg.names, 0)
    r.tagged_struct()
    has_guid, = struct.unpack_from("<i", data, r.p)
    return body, data, r.p + 4 + (16 if has_guid else 0) + 16


def fix_collision(folder: str, model: str) -> None:
    """Leave the cooked mesh without cooked physics data.

    The game runs Chaos physics; this engine cooks PhysX data, which the game cannot read (0.12.0's convex hulls gave
    no collision at all). Box collision needs no cooked data, but 4.27 still writes an empty PhysX header (0 convex,
    0 mirrored, 0 triangle meshes) for every mesh. This patch clears bHasCookedCollisionData and drops that payload,
    so the game takes its own path for a mesh without cooked data and builds the boxes from their numbers. It refuses
    a payload that holds any shape."""
    sys.path.insert(0, TOOLS)
    from legacy_package import load
    base = os.path.join(folder, f"SM_{model}")
    pkg = load(base)
    body, data, q = body_setup_tail(pkg)
    cooked, has_data, nformats = struct.unpack_from("<iii", data, q)
    if cooked != 1:
        raise SystemExit(f"SM_{model}: unexpected BodySetup layout (bCooked {cooked})")
    if has_data or nformats:
        if nformats != 1:
            raise SystemExit(f"SM_{model}: {nformats} cooked physics formats, expected 1")
        fmt = pkg.names[struct.unpack_from("<i", data, q + 12)[0]]
        flags, _count, size = struct.unpack_from("<Iii", data, q + 20)
        if flags & 0x2001:                               # 64-bit sizes or payload elsewhere: not this layout
            raise SystemExit(f"SM_{model}: unexpected bulk data flags {flags:#x}")
        payload_at = q + 20 + 4 + 4 + 4 + 8
        _le, convex, mirrored, trimeshes = struct.unpack_from("<Biii", data, payload_at)
        if (convex, mirrored, trimeshes) != (0, 0, 0):
            raise SystemExit(f"SM_{model}: the cooked {fmt} collision holds {convex} convex, {mirrored} mirrored and "
                             f"{trimeshes} triangle meshes; the game cannot read them (use UBX_ boxes only)")
        pkg.replace_export_data(body, data[:q + 4] + struct.pack("<ii", 0, 0) + data[payload_at + size:])
        ua, ue = pkg.build()
        with open(base + ".uasset", "wb") as fh:
            fh.write(ua)
        with open(base + ".uexp", "wb") as fh:
            fh.write(ue)
        print(f"    collision: dropped the empty {fmt} header ({size} bytes); the game builds the boxes itself")
    pkg = load(base)
    _body, data, q = body_setup_tail(pkg)
    if struct.unpack_from("<iii", data, q) != (1, 0, 0):
        raise SystemExit(f"SM_{model}: the BodySetup still carries cooked physics data")


def check_references(folder: str) -> list[str]:
    """Everything a cooked package imports from outside /Game/HardcoreLogistics must exist in the game."""
    sys.path.insert(0, TOOLS)
    from iostore import open_game_container
    from legacy_package import LegacyPackage
    game = set(open_game_container().files)
    used = []
    for f in sorted(os.listdir(folder)):
        if not f.endswith(".uasset"):
            continue
        base = os.path.join(folder, f[:-len(".uasset")])
        with open(base + ".uasset", "rb") as a, open(base + ".uexp", "rb") as e:
            pkg = LegacyPackage(a.read(), e.read())
        for imp in pkg.import_entries():
            name = imp["name"]
            if imp["class"] != "Package" or imp["outer"] != 0 or name.startswith(("/Script/", DEST_ROOT + "/")):
                continue
            root, rest = name[1:].split("/", 1)
            path = ("FarMech/Content/" if root == "Game" else f"{root}/Content/") + rest + ".uasset"
            if path not in game:
                raise SystemExit(f"cooked {f} references {name}, which the game does not have")
            used.append(f"{name.rsplit('/', 1)[1]} (from {f[:-len('.uasset')]})")
    return used


if __name__ == "__main__":
    main()
