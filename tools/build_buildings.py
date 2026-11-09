"""Build the mod's buildings into their own IoStore container (HardcoreLogisticsBuildings_P).

    python tools/build_buildings.py build        write dist/buildings/HardcoreLogisticsBuildings_P.{utoc,ucas,pak}
    python tools/build_buildings.py install      build, then copy it into Paks/~mods (close the game first)
    python tools/build_buildings.py uninstall    remove it from Paks/~mods

Two kinds of building (mod_config.json):
  hub.buildings    new buildings: renamed copies of a cut construct's Blueprint, each with a new DT_Constructs row
                   (the Logistics Hubs)
  cut_buildings    buildings the game ships but hides: their own row loses the Features.Limbo flag and gets a name,
                   a description and a cost (the Barn)
Each goes into a milestone's ConstructRewards list, so reaching it unlocks the building the game's own way.

How:
  1. retoc converts DT_Constructs, DT_DeliveryMilestones and each template construct's Blueprint from the installed
     game to legacy packages. It reads a temporary folder of hard links to the game's own containers only, so a
     container already in ~mods (this one, after an install) is never read back.
  2. Each new building's Blueprint is renamed (legacy_package.py): package
     /Game/HardcoreLogistics/Constructs/BP_<row>Construct, its class and class default, and its ConstructName (the
     template's row name) become the new row's name. Saves keep placed constructs by class path, so each copy is a
     construct of its own.
  3. DT_Constructs (legacy_table.py) gets a row per new building, copied from its template's row with these changed:
     Name, DisplayName, Description, Class (the copy), ItemCost, SaveType (saved like other constructs), FeatureFlag
     (none; Features.Legacy, which hides the row from the build wheel, when hub.feature ties the hubs to a feature),
     and Category and Type (the build-menu tab and group) from hub.menu_group_from; the icon stays the template's. A
     cut building's own row changes DisplayName, Description, ItemCost and FeatureFlag only.
  4. Each milestone's ConstructRewards list gets its buildings, except hubs tied to a feature: before a world running
     that feature loads, the runtime clears their flag and adds them to the list (runtime_settings, main.lua).
  5. retoc packs everything into one container (UE4_27), and the result is read back and compared with the game:
     apart from the changes above, every row of both tables must be the game's.
A new building with a "model" (mod_config.json) gets its own look: the mesh its StaticMesh component override names
points at /Game/HardcoreLogistics/Art/<model>/SM_<model> and its row's Icon at T_<model>Icon. tools/cook_art.py cooks
those with Unreal 4.27 into dist/art; they go into the container as they are.
"template_edits" rewrites values the template's component overrides already set, in place (null clears a mesh, a
number sets an int or float, [x, y, z] a vector): the Logistics Hub switches off the Water Reservoir's water parts.
"energy" gives the building a cost on the game's Energy Meter: a DT_EnergyValues row (the template's energy handler
reads its cost there by construct name) and the same value on the handler itself.
The container may hold nothing outside /Game/HardcoreLogistics except the tables (DT_Constructs,
DT_DeliveryMilestones, DT_EnergyValues), so a stand-in for one of the game's own assets can never ship.
retoc: modding_tools/retoc/v0.1.5/retoc.exe next to this repo, or set LF_RETOC.
"""
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

from cook_art import COOKED, DEST_ROOT as ART_DIR, cooked_dir, snake  # noqa: E402
from iostore import IoStoreContainer, open_game_container, paks_dir  # noqa: E402
from legacy_package import _fstr, iter_tags, load  # noqa: E402
from legacy_table import TableData  # noqa: E402
from uasset import export_properties, plain, read_datatable  # noqa: E402
from zen_edit import cityhash64  # noqa: E402

NAME = "HardcoreLogisticsBuildings_P"
OLD_NAMES = ("HardcoreLogisticsHub_P",)     # earlier name of this container (0.10.x); removed on install
EXTS = (".pak", ".utoc", ".ucas")
OUT = os.path.join(REPO, "dist", "buildings")
PACKAGE_DIR = "/Game/HardcoreLogistics/Constructs"
GAME_CONTAINERS = ("global.utoc", "global.ucas", "FarMech-WindowsNoEditor.utoc", "FarMech-WindowsNoEditor.ucas",
                   "FarMech-WindowsNoEditor.pak")
CONSTRUCTS = "/Game/DataTables/DT_Constructs"
MILESTONES = "/Game/DataTables/DT_DeliveryMilestones"
ENERGY = "/Game/DataTables/DT_EnergyValues"
CONSTRUCTS_FILE = "FarMech/Content/DataTables/DT_Constructs.uasset"
MILESTONES_FILE = "FarMech/Content/DataTables/DT_DeliveryMilestones.uasset"
ENERGY_FILE = "FarMech/Content/DataTables/DT_EnergyValues.uasset"
TABLE_FILES = (CONSTRUCTS_FILE, MILESTONES_FILE, ENERGY_FILE)
MOD_CONTENT = "FarMech/Content/HardcoreLogistics/"      # the container's only folder besides the tables
MESH_COMPONENT = "StaticMesh_GEN_VARIABLE"              # BP_Construct's StaticMesh, as the template overrides it
ENERGY_COMPONENT = "BPC_EnergyHandler_GEN_VARIABLE"     # the game's energy handler, as the template sets it
# A feature flag the game never switches on (DefaultGame.ini groups it as "Legacy", GeneratedGame.ini's EnabledGroups
# leave that group out). The build wheel (Widget_BuildingsSelectRadial GetConstructsOfType / SetupTabData) shows a row
# only when its flag is empty or switched on, so a row with this flag is left out; the game hides its retired
# Automators this way, and placed ones still load. Hub rows tied to a feature ship with it, and the runtime clears it.
HIDDEN_FLAG = "Features.Legacy"


def retoc_exe() -> str:
    exe = os.environ.get("LF_RETOC") or os.path.join(os.path.dirname(REPO), "modding_tools", "retoc", "v0.1.5",
                                                     "retoc.exe")
    if not os.path.isfile(exe):
        raise SystemExit(f"retoc not found at {exe} (set LF_RETOC)")
    return exe


def retoc(*args: str) -> str:
    res = subprocess.run([retoc_exe(), *args], capture_output=True, text=True)
    if res.returncode != 0:
        raise SystemExit(f"retoc {' '.join(args[:2])} failed:\n{res.stdout}{res.stderr}")
    return res.stdout + res.stderr


def _check_cost(where: str, cost) -> None:
    if not isinstance(cost, dict) or not cost or not all(isinstance(v, int) and v > 0 for v in cost.values()):
        raise SystemExit(f"{where}.cost must map item IDs to whole numbers above 0")


DRONE_ROLES = ("input", "output")
DRONE_NUMBERS = ("load_kg", "speed_mps", "min_trip_s", "check_ms", "rescan_s")


def _check_building(where: str, b: dict, rows: set) -> None:
    """One new building of hub.buildings or drone_stations.buildings (a renamed Blueprint copy with its own row)."""
    for k in ("row", "template", "display_name", "description", "cost"):
        if not b.get(k):
            raise SystemExit(f"mod_config.json {where}.{k} is missing")
    if not b["row"].isidentifier() or b["row"] in rows:
        raise SystemExit(f"{where}.row must be a plain name, used once (got {b['row']!r})")
    if "model" in b and not str(b["model"]).isidentifier():
        raise SystemExit(f"{where}.model must be a plain name (got {b['model']!r})")
    if "energy" in b and not (isinstance(b["energy"], int) and b["energy"] > 0):
        raise SystemExit(f"{where}.energy must be a whole number above 0")
    if "status_icon" in b and not (str(b["status_icon"]).isidentifier() and b.get("model")):
        raise SystemExit(f"{where}.status_icon must be a plain name, on a building with a model")
    for fn, fe in (b.get("function_edits") or {}).items():
        if not isinstance(fe, dict) or set(fe) - {"texts", "strings"} or not all(
                isinstance(v, dict) and all(isinstance(x, str) and isinstance(y, str) for x, y in v.items())
                for v in fe.values()):
            raise SystemExit(f"{where}.function_edits.{fn}: texts and strings, each mapping text to text")
    for export, props in (b.get("template_edits") or {}).items():
        if export.startswith("_"):
            continue
        if not isinstance(props, dict):
            raise SystemExit(f"{where}.template_edits.{export} must map properties to values")
        for prop, value in props.items():
            if prop.startswith("_"):
                continue
            ok = value is None or isinstance(value, (bool, int, float)) or (
                isinstance(value, list) and len(value) == 3 and all(isinstance(v, (int, float)) for v in value))
            if not ok:
                raise SystemExit(f"{where}.template_edits.{export}.{prop}: null, true/false, a number or [x, y, z]")
    _check_cost(where, b["cost"])
    rows.add(b["row"])


def load_buildings_config() -> dict:
    """{"hub": {milestone, menu_group_from, feature, buildings}, "drones": {milestone, menu_group_from, feature,
    transfer numbers, buildings with a role}, "cut": {row: {display_name, description, cost, milestone}}}"""
    with open(os.path.join(REPO, "mod_config.json"), encoding="utf-8") as fh:
        cfg = json.load(fh)
    hub = {k: v for k, v in cfg.get("hub", {}).items() if not k.startswith("_")}
    if hub:
        for k in ("milestone", "menu_group_from", "buildings"):
            if not hub.get(k):
                raise SystemExit(f"mod_config.json hub.{k} is missing")
        features = {f for f in cfg.get("features", {}) if not f.startswith("_")}
        if "feature" in hub and hub["feature"] not in features:
            raise SystemExit(f"mod_config.json hub.feature must be one of the features ({', '.join(sorted(features))}), "
                             f"got {hub['feature']!r}")
    rows = set()
    for i, b in enumerate(hub.get("buildings", [])):
        _check_building(f"hub.buildings[{i}]", b, rows)
    drones = {k: v for k, v in cfg.get("drone_stations", {}).items() if not k.startswith("_")}
    if drones:
        for k in ("milestone", "menu_group_from", "buildings"):
            if not drones.get(k):
                raise SystemExit(f"mod_config.json drone_stations.{k} is missing")
        for k in DRONE_NUMBERS:
            v = drones.get(k)
            if not isinstance(v, (int, float)) or isinstance(v, bool) or v <= 0:
                raise SystemExit(f"mod_config.json drone_stations.{k} must be a number above 0 (got {v!r})")
        features = {f for f in cfg.get("features", {}) if not f.startswith("_")}
        if "feature" in drones and drones["feature"] not in features:
            raise SystemExit(f"mod_config.json drone_stations.feature must be one of the features "
                             f"({', '.join(sorted(features))}), got {drones['feature']!r}")
        if drones.get("energy_handler", "template") not in ("template", "runtime"):
            raise SystemExit("drone_stations.energy_handler must be 'template' (the template's own energy handler) or "
                             f"'runtime' (drones.lua adds the game's), got {drones['energy_handler']!r}")
        for i, b in enumerate(drones["buildings"]):
            _check_building(f"drone_stations.buildings[{i}]", b, rows)
            if b.get("role") not in DRONE_ROLES:
                raise SystemExit(f"drone_stations.buildings[{i}].role must be one of {DRONE_ROLES} (got {b.get('role')!r})")
        missing = set(DRONE_ROLES) - {b["role"] for b in drones["buildings"]}
        if missing:
            raise SystemExit(f"drone_stations needs a building for every role; none is {sorted(missing)}")
    cut = {k: v for k, v in cfg.get("cut_buildings", {}).items() if not k.startswith("_")}
    for row, b in cut.items():
        for k in ("display_name", "description", "cost", "milestone"):
            if not b.get(k):
                raise SystemExit(f"mod_config.json cut_buildings.{row}.{k} is missing")
        _check_cost(f"cut_buildings.{row}", b["cost"])
        if row in rows:
            raise SystemExit(f"cut_buildings.{row} is also a new building's row")
    return {"hub": hub, "drones": drones, "cut": cut}


def new_buildings(cfg: dict) -> list[tuple[dict, dict]]:
    """(group, building) for every new building: the hubs, then the drone stations. A group carries the milestone,
    the build-menu group (menu_group_from) and the feature its buildings belong to, if any."""
    return [(g, b) for g in (cfg["hub"], cfg["drones"]) for b in g.get("buildings", [])]


ENERGY_HANDLER_CLASS = "/Game/Blueprints/BPC_EnergyHandler.BPC_EnergyHandler_C"


def runtime_energy(cfg: dict, group: dict) -> bool:
    """Buildings whose energy handler the runtime adds (the template has none): the drone stations with
    energy_handler 'runtime'. They still get their DT_EnergyValues row, which the handler reads by construct name."""
    return group is cfg["drones"] and group.get("energy_handler") == "runtime"


def feature_tied(cfg: dict, group: dict) -> bool:
    """Buildings shown only where a feature runs: a group with a feature set (hub.feature: the hubs with 'storage';
    drone_stations.feature: the stations with 'drones')."""
    return bool(group.get("feature"))


def hub_class_path(row: str) -> str:
    """A copied Blueprint's class: /Game/HardcoreLogistics/Constructs/BP_<row>Construct.BP_<row>Construct_C"""
    return f"{PACKAGE_DIR}/BP_{row}Construct.BP_{row}Construct_C"


def model_assets(model: str) -> dict:
    """A model's cooked packages (tools/cook_art.py) and the paths the Blueprint copy and its row point at."""
    folder = f"{ART_DIR}/{model}"
    return {"mesh_package": f"{folder}/SM_{model}", "mesh": f"SM_{model}",
            "icon": f"{folder}/T_{model}Icon.T_{model}Icon", "cooked": cooked_dir(model),
            "source": os.path.join(REPO, "art", snake(model)),
            "files": [f"{MOD_CONTENT}Art/{model}/{p.format(m=model)}.uasset" for p in COOKED]}


def export_tags(bp, export_name: str):
    """(export, its bytes, {property: (type, struct name, value offset, size)}) of one export of a legacy package."""
    exp = next((e for e in bp.export_entries() if e["name"] == export_name), None)
    if exp is None:
        raise SystemExit(f"the template has no {export_name}")
    start = exp["offset"] - bp.total_header_size
    data = bytearray(bp.uexp[start:start + exp["size"]])
    return exp, data, {n: (t, s, o, z) for n, t, s, o, z in iter_tags(data, bp.names)}


def retarget_mesh(bp, assets: dict) -> str:
    """Point the template's main mesh (the StaticMesh its StaticMesh component override names) at the model: that
    mesh import and its package import get the model's names. Returns the old path. Other meshes stay (clear them
    with template_edits)."""
    imports = bp.import_entries()
    _exp, data, tags = export_tags(bp, MESH_COMPONENT)
    if tags.get("StaticMesh", ("",))[0] != "ObjectProperty":
        raise SystemExit(f"{MESH_COMPONENT} does not set a StaticMesh")
    ref, = struct.unpack_from("<i", data, tags["StaticMesh"][2])
    i = -ref - 1
    if ref >= 0 or imports[i]["class"] != "StaticMesh":
        raise SystemExit(f"{MESH_COMPONENT}'s StaticMesh is not an imported static mesh")
    outer = imports[i]["outer"]
    pkg = -outer - 1
    if outer >= 0 or imports[pkg]["class"] != "Package":
        raise SystemExit("the template's mesh import is not directly inside a package import")
    if sum(1 for imp in imports if imp["outer"] == outer) != 1:
        raise SystemExit(f"the Blueprint imports more than the mesh from {imports[pkg]['name']}")
    for e in bp.export_entries():                     # no other component may show the same mesh
        if e["name"].endswith("_GEN_VARIABLE") and e["name"] != MESH_COMPONENT:
            _e, d, t = export_tags(bp, e["name"])
            if t.get("StaticMesh", ("",))[0] == "ObjectProperty" and struct.unpack_from("<i", d, t["StaticMesh"][2])[0] == ref:
                raise SystemExit(f"{e['name']} uses the same mesh as {MESH_COMPONENT}")
    old = f"{imports[pkg]['name']}.{imports[i]['name']}"
    bp.set_import_name(pkg, assets["mesh_package"])
    bp.set_import_name(i, assets["mesh"])
    return old


def edit_template(bp, edits: dict) -> None:
    """Rewrite values a template's component overrides (or its class default) already set, in place: the export keeps
    its size, so nothing else moves. null clears an object reference (a mesh), true/false sets a bool, a number sets
    an int or float property, [x, y, z] a Vector. A property the template does not set cannot be added this way, and
    is refused."""
    for export_name, props in edits.items():
        if export_name.startswith("_"):
            continue
        exp, data, tags = export_tags(bp, export_name)
        for prop, value in props.items():
            if prop not in tags:
                raise SystemExit(f"{export_name} does not set {prop}; only values the template sets can change")
            ptype, struct_name, off, size = tags[prop]
            if ptype == "BoolProperty" and isinstance(value, bool):
                data[off] = 1 if value else 0               # the value lives in the tag (iter_tags points at it)
            elif ptype == "ObjectProperty" and value is None:
                struct.pack_into("<i", data, off, 0)
            elif ptype == "IntProperty" and isinstance(value, int):
                struct.pack_into("<i", data, off, value)
            elif ptype == "FloatProperty" and isinstance(value, (int, float)):
                struct.pack_into("<f", data, off, float(value))
            elif struct_name == "Vector" and size == 12 and isinstance(value, list):
                struct.pack_into("<fff", data, off, *map(float, value))
            else:
                raise SystemExit(f"{export_name}.{prop} is a {struct_name or ptype}; cannot set it to {value!r}")
        bp.replace_export_data(exp, bytes(data))


EX_TEXT_CONST, EX_STRING_CONST = 0x29, 0x1F      # Kismet bytecode: a text literal, an ANSI string literal
TEXT_STRING_TABLE, TEXT_LOCALIZED = 0x04, 0x01     # EBlueprintTextLiteralType
TEXT_NAMESPACE = b"HardcoreLogistics"


def script_size_fields(data: bytes) -> int:
    """Where a UFunction export keeps (BytecodeBufferSize, SerializedScriptSize): the script they describe ends exactly
    where the function's last fields begin (FunctionFlags, RepOffset if it replicates, EventGraphFunction,
    EventGraphCallOffset: 12 or 14 bytes), with EX_EndOfScript (0x53) as its last byte. The two sizes differ: an object
    pointer is 8 bytes in memory and 4 (a package index) on disk, a property reference 8 in memory and a 16+ byte
    field path on disk."""
    found = []
    for tail in (12, 14):
        end = len(data) - tail
        if end < 9 or data[end - 1] != 0x53:
            continue
        for o in range(end - 8):
            mem, disk = struct.unpack_from("<ii", data, o)
            if mem > 0 and disk > 0 and o + 8 + disk == end:
                found.append(o)
    if len(found) != 1:
        raise SystemExit(f"cannot tell where the function's script sizes are ({len(found)} candidates)")
    return found[0]


def patch_function(bp, export_name: str, texts: dict, strings: dict) -> None:
    """Swap literals in a Blueprint function's bytecode without moving any other byte the game reads by offset.

    texts: a string-table text (EX_TextConst StringTableEntry: package index, table id, key) becomes our own text
    (EX_TextConst LocalizedText: source, key, namespace), sized to the same number of bytes in memory, where jump
    offsets count, so BytecodeBufferSize stays. On disk it is 4 bytes longer (the old one held a 4-byte package index
    for an 8-byte pointer), so SerializedScriptSize grows by 4. The new key is unique, so the source text shows.
    strings: an ANSI string literal becomes another of the same length (an icon's soft path)."""
    exp = next((e for e in bp.export_entries() if e["name"] == export_name), None)
    if exp is None:
        raise SystemExit(f"the template has no function {export_name}")
    start = exp["offset"] - bp.total_header_size
    data = bytearray(bp.uexp[start:start + exp["size"]])
    fields = script_size_fields(data)
    mem, disk = struct.unpack_from("<ii", data, fields)
    s0 = fields + 8
    tail = len(data) - (s0 + disk)                     # the function's last fields, after the script

    def find_once(pat: bytes, what: str) -> int:
        script = bytes(data[s0:s0 + disk])
        first = script.find(pat)
        if first < 0 or script.find(pat, first + 1) >= 0:
            raise SystemExit(f"{export_name}: {what} must appear exactly once in the bytecode")
        return s0 + first

    for key, text in texts.items():
        if not (key.isascii() and text.isascii()):
            raise SystemExit(f"{export_name}: texts must be plain ASCII")
        kpat = bytes([EX_STRING_CONST]) + key.encode() + b"\0"
        k = find_once(kpat, f"the string-table key {key}")
        j = data.rfind(bytes([EX_TEXT_CONST, TEXT_STRING_TABLE]), s0, k)
        if j < 0 or data[j + 6] != EX_STRING_CONST or data.index(b"\0", j + 7) != k - 1:
            raise SystemExit(f"{export_name}: {key} is not a string-table text literal")
        old_len = k + len(kpat) - j
        mem_len = old_len + 4
        src = text.encode()
        key_len = mem_len - 8 - len(src) - len(TEXT_NAMESPACE)
        if key_len < 8:
            raise SystemExit(f"{export_name}: {text!r} is too long to replace {key} ({mem_len - 16 - len(TEXT_NAMESPACE)} "
                             f"characters at most)")
        new_key = (f"HL_{export_name}_{key}_" * 4).encode()[:key_len]
        new = (bytes([EX_TEXT_CONST, TEXT_LOCALIZED, EX_STRING_CONST]) + src + b"\0" + bytes([EX_STRING_CONST])
               + new_key + b"\0" + bytes([EX_STRING_CONST]) + TEXT_NAMESPACE + b"\0")
        assert len(new) == mem_len
        data[j:j + old_len] = new
        disk += len(new) - old_len
    for old, new in strings.items():
        if len(old) != len(new) or not (old.isascii() and new.isascii()):
            raise SystemExit(f"{export_name}: {new!r} must be plain ASCII and as long as {old!r} ({len(old)})")
        pos = find_once(bytes([EX_STRING_CONST]) + old.encode() + b"\0", f"the string {old}")
        data[pos + 1:pos + 1 + len(old)] = new.encode()
    struct.pack_into("<i", data, fields + 4, disk)
    if s0 + disk + tail != len(data) or struct.unpack_from("<i", data, fields)[0] != mem:
        raise SystemExit(f"{export_name}: script size bookkeeping is off")
    bp.replace_export_data(exp, bytes(data))


def function_markers(edits: dict) -> tuple[list[bytes], list[bytes]]:
    """Byte patterns the patched bytecode must hold, and ones it must no longer hold (for verify)."""
    present, absent = [], []
    for fn in edits.values():
        for key, text in fn.get("texts", {}).items():
            present.append(bytes([EX_TEXT_CONST, TEXT_LOCALIZED, EX_STRING_CONST]) + text.encode() + b"\0")
            absent.append(bytes([EX_STRING_CONST]) + key.encode() + b"\0")
        for old, new in fn.get("strings", {}).items():
            present.append(bytes([EX_STRING_CONST]) + new.encode() + b"\0")
            absent.append(bytes([EX_STRING_CONST]) + old.encode() + b"\0")
    return present, absent


def expected_edit(value):
    """What export_properties() reads back for an edited value."""
    if value is None:
        return 0
    if isinstance(value, list):
        return tuple(round(float(v), 3) for v in value)
    return value


def building_edits(b: dict, handler_in_template: bool = True) -> dict:
    """A building's template edits by export name, with its energy cost on the template's energy handler (unless the
    runtime adds the handler). The key ClassDefault names the copy's class default object
    (Default__BP_<row>Construct_C)."""
    edits = {}
    for k, v in (b.get("template_edits") or {}).items():
        if k.startswith("_"):
            continue
        name = f"Default__BP_{b['row']}Construct_C" if k == "ClassDefault" else k
        edits[name] = {p: x for p, x in v.items() if not p.startswith("_")}
    if b.get("energy") and handler_in_template:
        edits.setdefault(ENERGY_COMPONENT, {})["UsedEnergy"] = b["energy"]
    return edits


def copy_art(staging: str, model: str, assets: dict) -> None:
    src = assets["cooked"]
    if not os.path.isdir(src):
        raise SystemExit(f"no cooked art for model {model} in {src}: run tools/cook_art.py first")
    cooked = [os.path.join(src, f) for f in os.listdir(src)]
    sources = [os.path.join(assets["source"], f) for f in os.listdir(assets["source"])
               if f.endswith((".fbx", ".png")) and not f.startswith("preview")]
    if sources and max(map(os.path.getmtime, sources)) > min(map(os.path.getmtime, cooked)):
        print(f"warning: art/{snake(model)} changed after the last cook; run tools/cook_art.py to include it")
    shutil.copytree(src, os.path.join(staging, *MOD_CONTENT.rstrip("/").split("/"), "Art", model))


def copy_extra_art(staging: str, name: str) -> None:
    """A texture cook_art.py cooked straight into /Game/HardcoreLogistics/Art (a status icon)."""
    src = os.path.join(os.path.dirname(cooked_dir("x")), name)
    files = [src + ext for ext in (".uasset", ".uexp", ".ubulk") if os.path.isfile(src + ext)]
    if len(files) < 2:
        raise SystemExit(f"no cooked {name} in {os.path.dirname(src)}: run tools/cook_art.py first")
    dst = os.path.join(staging, *MOD_CONTENT.rstrip("/").split("/"), "Art")
    os.makedirs(dst, exist_ok=True)
    for f in files:
        shutil.copy2(f, dst)


def package_import_index(object_path: str) -> int:
    """FPackageObjectIndex of an imported object in a zen package (UE 4.27): type PackageImport (2) in the top two
    bits, then CityHash64 of the UTF-16 path, lowercase, with '.' and ':' as '/'."""
    s = object_path.lower().replace(".", "/").replace(":", "/")
    return (2 << 62) | (cityhash64(s.encode("utf-16-le")) & ~(3 << 62))


def zen_imports(data: bytes) -> set[int]:
    imp_off, exp_off = struct.unpack_from("<ii", data, 40)     # FPackageSummary ImportMapOffset, ExportMapOffset
    return set(struct.unpack_from(f"<{(exp_off - imp_off) // 8}Q", data, imp_off))


def milestone_number(name: str):
    digits = "".join(ch for ch in name if ch.isdigit())
    return int(digits) if digits else None


def runtime_settings() -> dict:
    """What the runtime scripts need (edits.lua): the hubs (storage.lua), the drone stations (drones.lua), every
    building's unlock (unlocks.lua), and, for buildings tied to a feature (the hubs, the drone stations), the table
    changes that show them in worlds running it (main.lua applies those before such a world loads, like the tables in
    mod_config.json, and restores them for any other)."""
    cfg = load_buildings_config()
    hub, cut = cfg["hub"], cfg["cut"]
    feature = hub.get("feature")
    hubs = [{"row": b["row"], "class": hub_class_path(b["row"]), "display_name": b["display_name"],
             "energy": b.get("energy", 0)} for b in hub.get("buildings", [])]
    unlocks = [{"row": b["row"], "name": b["display_name"], "milestone": hub["milestone"],
                "milestone_number": milestone_number(hub["milestone"]), "feature": feature}
               for b in hub.get("buildings", [])]
    drones = cfg["drones"]
    unlocks += [{"row": b["row"], "name": b["display_name"], "milestone": drones["milestone"],
                 "milestone_number": milestone_number(drones["milestone"]), "feature": drones.get("feature")}
                for b in drones.get("buildings", [])]
    unlocks += [{"row": row, "name": b["display_name"], "milestone": b["milestone"],
                 "milestone_number": milestone_number(b["milestone"])} for row, b in cut.items()]
    out = {"unlocks": unlocks, "tables": []}
    if hubs:
        out["hub"] = {"hubs": hubs, "milestone": hub["milestone"], "milestone_number": milestone_number(hub["milestone"]),
                      "feature": feature}
    for g in (hub, drones):
        if g.get("buildings") and g.get("feature"):
            out["tables"] += feature_tables(g, g["feature"])
    if drones.get("buildings"):
        out["drones"] = drone_settings(drones)
    return out


def drone_settings(drones: dict) -> dict:
    """What drones.lua needs: each station class and its role, the transfer numbers, and from the game's DT_Items each
    item's weight in grams (to size a load; the stations' own weights decide what fits) and the liquids (never
    carried: storages do not hold them)."""
    items = read_datatable(open_game_container().read_file("FarMech/Content/DataTables/DT_Items.uasset")).rows
    grams, liquids = {}, []
    for name, row in items.items():
        p = plain(row)
        grams[name] = int(p.get("Weight") or 0)
        if "EItemTag::Liquid" in (p.get("Tags") or []):
            liquids.append(name)
    out = {"stations": [{"row": b["row"], "class": hub_class_path(b["row"]), "role": b["role"],
                         "name": b["display_name"]} for b in drones["buildings"]],
           "item_grams": grams, "liquids": sorted(liquids)}
    out.update({k: drones[k] for k in DRONE_NUMBERS})
    if drones.get("energy_handler") == "runtime":
        out["energy_handler_class"] = ENERGY_HANDLER_CLASS
    out["feature"] = drones.get("feature")          # drones.lua flies drones, and powers the stations, only while on
    for st, b in zip(out["stations"], drones["buildings"]):
        st["energy"] = b.get("energy", 0)
    return out


def feature_tables(group: dict, feature: str) -> list[dict]:
    """The runtime edits (edits.lua tables) that show a feature-tied group's buildings (the hubs, the drone stations):
    each row's FeatureFlag cleared (shipped as HIDDEN_FLAG) and the rows added to the group's milestone's
    ConstructRewards (shipped without them). The property names come from the game's own tables (a Blueprint struct
    member keeps its GUID suffix). Each group gives its own pair of table entries, under its own feature."""
    from uasset import resolve_steps
    game = open_game_container()
    constructs = read_datatable(game.read_file(CONSTRUCTS_FILE)).rows
    milestones = read_datatable(game.read_file(MILESTONES_FILE)).rows
    if group["milestone"] not in milestones:
        raise SystemExit(f"DT_DeliveryMilestones has no row {group['milestone']} (the milestone of {feature!r}'s "
                         f"buildings)")
    rows = [b["row"] for b in group["buildings"]]
    (_p, _leaf, flag_steps), = resolve_steps(constructs[group["menu_group_from"]], "FeatureFlag.TagName")
    (_p, _node, reward_steps), = resolve_steps(milestones[group["milestone"]], "ConstructRewards", leaves_only=False)
    names = [{"row": r, "steps": [list(s) for s in flag_steps], "vanilla": HIDDEN_FLAG, "value": "None"} for r in rows]
    lists = [{"row": group["milestone"], "steps": [list(s) for s in reward_steps], "add": rows}]
    return [{"name": "DT_Constructs", "path": f"{CONSTRUCTS}.DT_Constructs", "feature": feature,
             "values": [], "maps": [], "names": names},
            {"name": "DT_DeliveryMilestones", "path": f"{MILESTONES}.DT_DeliveryMilestones", "feature": feature,
             "values": [], "maps": [], "lists": lists}]


def hidden_flag_value(table: TableData) -> bytes:
    """A FeatureFlag value holding HIDDEN_FLAG, copied from a game row that has it (the Automators)."""
    for row, _raw, tags in table.rows:
        flag = next((t for t in tags if base_name(t.name) == "FeatureFlag"), None)
        if flag is not None and tag_name_of(table, flag) == HIDDEN_FLAG:
            return flag.value
    raise SystemExit(f"no DT_Constructs row has the feature flag {HIDDEN_FLAG} to copy")


def check_items(cfg: dict) -> None:
    """Every cost item must be a DT_Items row, or the build menu shows a cost nobody can pay."""
    items = set(read_datatable(open_game_container().read_file("FarMech/Content/DataTables/DT_Items.uasset")).rows)
    costs = [(b["row"], b["cost"]) for _g, b in new_buildings(cfg)] + [(r, b["cost"]) for r, b in cfg["cut"].items()]
    for row, cost in costs:
        unknown = sorted(set(cost) - items)
        if unknown:
            raise SystemExit(f"building {row}: cost names items that are not in DT_Items: {unknown}")


def game_view() -> str:
    """A temporary folder holding hard links to the game's own containers (no ~mods)."""
    view = os.path.join(tempfile.gettempdir(), "lf_game_paks_view")
    shutil.rmtree(view, ignore_errors=True)
    os.makedirs(view)
    for f in GAME_CONTAINERS:
        src = os.path.join(paks_dir(), f)
        try:
            os.link(src, os.path.join(view, f))
        except OSError:
            shutil.copy2(src, os.path.join(view, f))   # another volume: copy instead
    return view


def legacy_path(root: str, game_path: str) -> str:
    """/Game/X/Y -> <root>/FarMech/Content/X/Y (no extension)."""
    return os.path.join(root, "FarMech", "Content", *game_path[len("/Game/"):].split("/"))


def base_name(prop: str) -> str:
    """Blueprint struct members are stored as Name_24_<guid>: keep the readable part."""
    parts = prop.split("_")
    return "_".join(parts[:-2]) if len(parts) >= 3 and parts[-2].isdigit() else prop


def tag_name_of(table: TableData, tag) -> str:
    """The TagName inside a GameplayTag struct value: its first tag must be TagName, a NameProperty."""
    names = table.pkg.names
    first, = struct.unpack_from("<i", tag.value, 0)
    ptype, = struct.unpack_from("<i", tag.value, 8)
    if names[first] != "TagName" or names[ptype] != "NameProperty":
        raise SystemExit(f"unexpected GameplayTag layout in {tag.name}")
    value, = struct.unpack_from("<i", tag.value, 25)          # after name, type, size, index, guid flag
    return names[value]


def template_class(table: TableData, template: str) -> tuple[str, str, str]:
    """(package, class, short name) of a construct row's Blueprint."""
    tags = {base_name(t.name): t for t in table.row(template)}
    idx, = struct.unpack_from("<i", tags["Class"].value, 0)
    package, cls = table.pkg.names[idx].split(".")
    return package, cls, package.rsplit("/", 1)[1]


def empty_tag_value(table: TableData, row: str) -> bytes:
    """A GameplayTag struct holding None: the row's own VariantFamily or FeatureFlag when one is empty, else the first
    empty one of any row (Storage Box II, a drone station's template, has a VariantFamily and a FeatureFlag)."""
    candidates = [table.row(row)] + [tags for _r, _raw, tags in table.rows]
    for tags in candidates:
        for t in tags:
            if base_name(t.name) in ("VariantFamily", "FeatureFlag") and tag_name_of(table, t) == "None":
                return t.value
    raise SystemExit("no DT_Constructs row has an empty GameplayTag to copy")


def build() -> list[str]:
    cfg = load_buildings_config()
    hub, cut = cfg["hub"], cfg["cut"]
    check_items(cfg)
    work = os.path.join(OUT, "work")
    shutil.rmtree(work, ignore_errors=True)
    src, staging = os.path.join(work, "game"), os.path.join(work, "staging")

    # 1. the tables, then every template's Blueprint
    view = game_view()
    pairs = new_buildings(cfg)                          # (group, building): the hubs, then the drone stations
    buildings = [b for _g, b in pairs]
    powered = [b for b in buildings if b.get("energy")]
    tables = ["--filter", "DT_Constructs", "--filter", "DT_DeliveryMilestones"]
    if powered:
        tables += ["--filter", "DT_EnergyValues"]
    retoc("to-legacy", "--no-shaders", *tables, view, src)
    constructs = load(legacy_path(src, CONSTRUCTS))
    table = TableData(constructs)
    energy_pkg = load(legacy_path(src, ENERGY)) if powered else None
    etable = TableData(energy_pkg) if powered else None
    templates = {b["template"]: template_class(table, b["template"]) for b in buildings}
    if templates:
        filters = []
        for _package, _cls, short in templates.values():
            filters += ["--filter", short]
        retoc("to-legacy", "--no-shaders", *filters, view, src)
    shutil.rmtree(view, ignore_errors=True)

    rewards: dict[str, list[str]] = {}
    retargets: dict[str, tuple[str, str]] = {}          # row: (template's mesh, model's mesh)
    menus = {id(g): {base_name(t.name): t for t in table.row(g["menu_group_from"])}
             for g in (cfg["hub"], cfg["drones"]) if g.get("buildings")}
    # buildings tied to a feature (hubs, drone stations) ship hidden and outside the milestone rewards; the runtime
    # shows them where the feature runs (feature_tables)
    hidden = hidden_flag_value(table) if any(feature_tied(cfg, g) for g, _b in pairs) else None
    for g, b in pairs:
        row, template, model = b["row"], b["template"], b.get("model")
        menu, tied = menus[id(g)], feature_tied(cfg, g)
        tmpl_package, tmpl_class, tmpl_short = templates[template]
        new_short = f"BP_{row}Construct"
        new_package = f"{PACKAGE_DIR}/{new_short}"

        # 2. the Blueprint copy (and its own mesh, from the cooked model)
        bp = load(legacy_path(src, tmpl_package))
        wanted = {tmpl_package: new_package, tmpl_class: f"{new_short}_C",
                  f"Default__{tmpl_class}": f"Default__{new_short}_C", template: row}
        missing = set(wanted) - set(bp.rename(wanted))
        if missing:
            raise SystemExit(f"{tmpl_short} does not have the names {sorted(missing)}; it cannot be copied this way")
        bp.folder_name = new_package
        if model:
            assets = model_assets(model)
            retargets[row] = (retarget_mesh(bp, assets), f"{assets['mesh_package']}.{assets['mesh']}")
            copy_art(staging, model, assets)
        in_template = not runtime_energy(cfg, g)
        edits = building_edits(b, in_template)
        if b.get("energy") and in_template and ENERGY_COMPONENT not in {e["name"] for e in bp.export_entries()}:
            raise SystemExit(f"{tmpl_short} has no energy handler; an energy cost needs a template with one "
                             f"(for example WaterReservoir)")
        edit_template(bp, edits)
        for fn, fe in (b.get("function_edits") or {}).items():
            patch_function(bp, fn, fe.get("texts", {}), fe.get("strings", {}))
        if b.get("status_icon"):
            copy_extra_art(staging, b["status_icon"])
        write_legacy(staging, new_package, bp)

        # 2b. its energy cost: a DT_EnergyValues row (the handler reads its cost there by construct name)
        if b.get("energy"):
            try:
                tmpl_row = etable.row(template) if not runtime_energy(cfg, g) else (
                    etable.row(template) if any(r == template for r, _x, _t in etable.rows) else etable.rows[0][2])
            except KeyError:
                raise SystemExit(f"DT_EnergyValues has no row {template} to copy for {row}") from None
            new_tags = []
            for t in tmpl_row:
                k = base_name(t.name)
                nt = type(t)(t.name, t.type, t.head, t.value)
                if k == "ConstructName":
                    nt.value = etable.name_ref(row)
                elif k == "UsedEnergy":
                    nt.value = struct.pack("<i", b["energy"])
                elif k == "GeneratedEnergy":
                    nt.value = struct.pack("<i", 0)
                new_tags.append(nt)
            etable.add_row(row, new_tags)

        # 3. its DT_Constructs row
        empty = empty_tag_value(table, template)
        new_tags = []
        for t in table.row(template):
            k = base_name(t.name)
            nt = type(t)(t.name, t.type, t.head, t.value)
            if k == "Name":
                nt.value = _fstr(row)
            elif k == "DisplayName":
                nt.value = table.text_value(b["display_name"], f"{row}_DisplayName", "DT_Constructs")
            elif k == "Description":
                nt.value = table.text_value(b["description"], f"{row}_Description", "DT_Constructs")
            elif k == "Class":
                nt.value = table.soft_path_value(hub_class_path(row))
            elif k == "ItemCost":
                nt.value = table.name_int_map_value(b["cost"])
            elif k == "SaveType" and g is hub:
                nt.value = table.name_ref("ConstructSaveType::NewEnumerator1")     # no contents to save
                # (a drone station keeps its template's SaveType: a storage's, so its contents save)
            elif k == "FeatureFlag":
                nt.value = hidden if tied else empty
            elif k == "VariantFamily":
                nt.value = empty            # its own wheel entry, not a variant of its template's family
            elif k in ("Category", "Type"):
                nt.head, nt.value = menu[k].head, menu[k].value    # the build-menu tab and group
            elif k == "Icon" and model:
                nt.value = table.soft_path_value(model_assets(model)["icon"])
            new_tags.append(nt)
        table.add_row(row, new_tags)
        if not tied:
            rewards.setdefault(g["milestone"], []).append(row)

    # 3b. the cut buildings' own rows
    for row, b in cut.items():
        tags = table.row(row)
        empty = empty_tag_value(table, row)
        for t in tags:
            k = base_name(t.name)
            if k == "DisplayName":
                t.value = table.text_value(b["display_name"], f"{row}_DisplayName", "DT_Constructs")
            elif k == "Description":
                t.value = table.text_value(b["description"], f"{row}_Description", "DT_Constructs")
            elif k == "ItemCost":
                t.value = table.name_int_map_value(b["cost"])
            elif k == "FeatureFlag":
                t.value = empty
        rewards.setdefault(b["milestone"], []).append(row)
    table.build()
    write_legacy(staging, CONSTRUCTS, constructs)

    # 4. the milestone rewards
    milestones = load(legacy_path(src, MILESTONES))
    mtable = TableData(milestones)
    for milestone, rows in rewards.items():
        tag = next(t for t in mtable.row(milestone) if base_name(t.name) == "ConstructRewards")
        count, = struct.unpack_from("<i", tag.value, 0)
        tag.value = struct.pack("<i", count + len(rows)) + tag.value[4:] + b"".join(mtable.name_ref(r) for r in rows)
    mtable.build()
    write_legacy(staging, MILESTONES, milestones)
    if etable is not None:
        etable.build()
        write_legacy(staging, ENERGY, energy_pkg)

    # 5. pack and check
    os.makedirs(OUT, exist_ok=True)
    for ext in EXTS:
        p = os.path.join(OUT, NAME + ext)
        if os.path.exists(p):
            os.remove(p)
    retoc("to-zen", "--version", "UE4_27", staging, os.path.join(OUT, NAME + ".utoc"))
    written = [os.path.join(OUT, NAME + ext) for ext in EXTS]
    verify(cfg, rewards, retargets)
    for p in written:
        print(f"wrote {p} ({os.path.getsize(p):,} bytes)")
    return written


def write_legacy(root: str, game_path: str, pkg) -> None:
    ua, ue = pkg.build()
    base = legacy_path(root, game_path)
    os.makedirs(os.path.dirname(base), exist_ok=True)
    with open(base + ".uasset", "wb") as fh:
        fh.write(ua)
    with open(base + ".uexp", "wb") as fh:
        fh.write(ue)


def verify(cfg: dict, rewards: dict[str, list[str]], retargets: dict[str, tuple[str, str]]) -> None:
    """Read the finished container back with this repo's own zen reader and compare it with the game."""
    hub, cut = cfg["hub"], cfg["cut"]
    c = IoStoreContainer(os.path.join(OUT, NAME + ".utoc"))
    files = set(c.files)
    stray = sorted(f for f in files if not f.startswith(MOD_CONTENT) and f not in TABLE_FILES)
    if stray:
        raise SystemExit(f"verification failed: the container holds files outside {MOD_CONTENT}: {stray[:5]}")
    game = open_game_container()
    rows = {k: plain(v) for k, v in read_datatable(c.read_file(CONSTRUCTS_FILE)).rows.items()}
    vanilla = {k: plain(v) for k, v in read_datatable(game.read_file(CONSTRUCTS_FILE)).rows.items()}
    pairs = new_buildings(cfg)
    buildings = [b for _g, b in pairs]
    new_rows = [b["row"] for b in buildings]
    lines = []
    for g, b in pairs:
        bp_file = "FarMech/Content" + hub_class_path(b["row"]).split(".")[0][len("/Game"):] + ".uasset"
        if bp_file not in files:
            raise SystemExit(f"verification failed: {bp_file} is not in the container")
        r = rows.get(b["row"])
        if r is None:
            raise SystemExit(f"verification failed: DT_Constructs has no row {b['row']}")
        menu_row = vanilla[g["menu_group_from"]]
        model = b.get("model")
        flag = HIDDEN_FLAG if feature_tied(cfg, g) else "None"
        save_type = "ConstructSaveType::NewEnumerator1" if g is hub else vanilla[b["template"]]["SaveType"]
        expect = {"Name": b["row"], "DisplayName": b["display_name"], "Description": b["description"],
                  "Class": hub_class_path(b["row"]), "ItemCost": b["cost"],
                  "SaveType": save_type, "FeatureFlag": {"TagName": flag}, "VariantFamily": {"TagName": "None"},
                  "Category": menu_row["Category"], "Type": menu_row["Type"],
                  "Icon": model_assets(model)["icon"] if model else vanilla[b["template"]]["Icon"]}
        bad = {k: (r.get(k), v) for k, v in expect.items() if r.get(k) != v}
        if bad:
            raise SystemExit(f"verification failed: row {b['row']} has {bad}")
        look = f"{b['template']} body"
        if model:
            lost = [f for f in model_assets(model)["files"] if f not in files]
            if lost:
                raise SystemExit(f"verification failed: model {model} is missing {lost} in the container")
            old, new = retargets[b["row"]]
            imports = zen_imports(c.read_file(bp_file))
            if package_import_index(new) not in imports or package_import_index(old) in imports:
                raise SystemExit(f"verification failed: {bp_file} does not import {new} in place of {old}")
            look = f"{b['template']} logic, model {model}"
        edits = building_edits(b, not runtime_energy(cfg, g))
        if edits:
            props = export_properties(c.read_file(bp_file))
            for export_name, values in edits.items():
                for prop, value in values.items():
                    got = props.get(export_name, {}).get(prop)
                    if isinstance(got, (tuple, list)):
                        got = tuple(round(float(v), 3) for v in got)
                    elif isinstance(got, float):
                        got = round(got, 3)
                    if got != expected_edit(value):
                        raise SystemExit(f"verification failed: {bp_file} {export_name}.{prop} is {got!r}, "
                                         f"not {expected_edit(value)!r}")
            look += f", {sum(len(v) for v in edits.values())} template values changed"
        if b.get("energy"):
            look += f", {b['energy']} energy"
        if b.get("function_edits"):
            raw = c.read_file(bp_file)
            present, absent = function_markers(b["function_edits"])
            if not all(p in raw for p in present) or any(a in raw for a in absent):
                raise SystemExit(f"verification failed: {bp_file} does not hold the patched function literals")
            look += f", {sum(len(v.get('texts', {})) + len(v.get('strings', {})) for v in b['function_edits'].values())} " \
                    f"function literals swapped"
        if b.get("status_icon"):
            icon_file = f"{MOD_CONTENT}Art/{b['status_icon']}.uasset"
            if icon_file not in files:
                raise SystemExit(f"verification failed: {icon_file} is not in the container")
        if feature_tied(cfg, g):
            look += f", hidden ({HIDDEN_FLAG}) and a {g['milestone']} reward only where '{g['feature']}' runs"
        if b.get("role"):
            look += f", drone {b['role']} station saved like {b['template']} ({save_type.rsplit(':', 1)[-1]})"
        lines.append(f"{b['row']} = {b['display_name']!r} ({look}, cost {b['cost']})")
    for row, b in cut.items():
        want = {**vanilla[row], "DisplayName": b["display_name"], "Description": b["description"],
                "ItemCost": b["cost"], "FeatureFlag": {"TagName": "None"}}
        if rows.get(row) != want:
            diff = {k: (rows.get(row, {}).get(k), v) for k, v in want.items() if rows.get(row, {}).get(k) != v}
            raise SystemExit(f"verification failed: cut building {row} differs: {diff}")
        lines.append(f"{row} = {b['display_name']!r} (cut building, cost {b['cost']})")
    changed = [k for k in vanilla if k not in cut and rows.get(k) != vanilla[k]]
    extra = [k for k in rows if k not in vanilla and k not in new_rows]
    if changed or extra:
        raise SystemExit(f"verification failed: DT_Constructs rows changed {changed[:5]}, added {extra[:5]}")
    ms = {k: plain(v) for k, v in read_datatable(c.read_file(MILESTONES_FILE)).rows.items()}
    ms_vanilla = {k: plain(v) for k, v in read_datatable(game.read_file(MILESTONES_FILE)).rows.items()}
    for k, v in ms_vanilla.items():
        want = {**v, "ConstructRewards": v["ConstructRewards"] + rewards.get(k, [])}
        if ms.get(k) != want:
            raise SystemExit(f"verification failed: milestone {k} is {ms.get(k)}")
    powered = {b["row"]: b["energy"] for b in buildings if b.get("energy")}
    if powered:
        ev = {k: plain(v) for k, v in read_datatable(c.read_file(ENERGY_FILE)).rows.items()}
        ev_vanilla = {k: plain(v) for k, v in read_datatable(game.read_file(ENERGY_FILE)).rows.items()}
        want = dict(ev_vanilla)
        for row, energy in powered.items():
            want[row] = {"ConstructName": row, "UsedEnergy": energy, "GeneratedEnergy": 0}
        if ev != want:
            diff = sorted(k for k in set(ev) | set(want) if ev.get(k) != want.get(k))
            raise SystemExit(f"verification failed: DT_EnergyValues differs at {diff[:5]}: "
                             f"{[(k, ev.get(k), want.get(k)) for k in diff[:2]]}")
        lines.append("energy: " + ", ".join(f"{r} uses {e}" for r, e in powered.items()))
    elif ENERGY_FILE in files:
        raise SystemExit("verification failed: DT_EnergyValues is in the container but no building has an energy cost")
    print(f"verified: {len(rows)} constructs; " + "; ".join(lines) + "; rewards: "
          + "; ".join(f"{m} + {r}" for m, r in rewards.items()))


def mods_dir() -> str:
    return os.path.join(paks_dir(), "~mods")


def _remove(names) -> int:
    removed = 0
    for name in names:
        for ext in EXTS:
            p = os.path.join(mods_dir(), name + ext)
            if os.path.exists(p):
                os.remove(p)
                removed += 1
    return removed


def cmd_install() -> None:
    written = build()
    os.makedirs(mods_dir(), exist_ok=True)
    old = _remove(OLD_NAMES)
    for p in written:
        shutil.copy2(p, mods_dir())
    print(f"installed into {mods_dir()}" + (f" (removed {old} files of the container's old name)" if old else ""))


def cmd_uninstall() -> None:
    print(f"removed {_remove((NAME,) + OLD_NAMES)} file(s) from {mods_dir()}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    {"build": build, "install": cmd_install, "uninstall": cmd_uninstall}.get(cmd, lambda: sys.exit(__doc__))()
