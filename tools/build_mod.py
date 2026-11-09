"""Build, install and remove the Hardcore Logistics data mod for Lightyear Frontier.

    python tools/build_mod.py show DT_Modules [ROW_FILTER]   print the game's current values for a table
    python tools/build_mod.py show DT_Deliveries Polyberry_ --modded
                                                             print the values in the last build (dist/) instead
    python tools/build_mod.py build                          patch the tables in mod_config.json into dist/
    python tools/build_mod.py install                        build, then copy the mod into Paks/~mods
    python tools/build_mod.py uninstall                      remove this mod from Paks/~mods

  Runtime (UE4SS) version, applied only to worlds switched on in worlds.txt:
    python tools/build_mod.py runtime                        write the UE4SS mod to dist/runtime/
    python tools/build_mod.py install-runtime                install it (and remove the static pak)
    python tools/build_mod.py disable-runtime                switch it off in UE4SS's mods.txt

Values are always patched into the tables of the game that is installed right now, so after a game
update you only need to run `install` again. Only the numbers listed in mod_config.json change.

mod_config.json maps table -> row -> value path -> new value:
  - a row can be an exact name or a pattern (`*_6` = every row ending in _6), optionally followed by a
    condition on a field (`*_6 [PlanetName=Hewstone]`); pattern rows that do not have the path are
    skipped, but every entry must change at least one value
  - a value is a number, or "x1.5" to multiply the current value (whole numbers are rounded, to the
    nearest 5 from 50 up)
  - `Map[+Key]` adds a new entry to a map (for example `Cost[+IronElectronics]`); added item names must
    be rows of DT_Items
  - entries apply in file order, so a later entry can override an earlier one for the same value,
    including entries an earlier rule added (`Polyberry_8: Cost[ClearLens]` after a planet-wide
    `Cost[+ClearLens]`)
"""
from __future__ import annotations

import dataclasses
import fnmatch
import json
import os
import re
import shutil
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from iostore import IoStoreContainer, ModFile, open_game_container, paks_dir, write_mod_container  # noqa: E402
from uasset import (PATCH_FORMATS, MapNode, display, leaves, patch, plain, read_datatable,  # noqa: E402
                    resolve_node, resolve_steps)
from zen_edit import PackageEditor  # noqa: E402

ROW_SELECTOR = re.compile(r"^(?P<pattern>\S+)(?:\s+\[(?P<field>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>[^\]]*)\])?$")
INSERT_PATH = re.compile(r"^(?P<map>.+)\[\+(?P<key>[^\]]+)\]$")
MAP_KEY_PATH = re.compile(r"^(?P<map>.+)\[(?P<key>[^\]+=*][^\]=]*)\]$")
VALUE_KINDS = {"IntProperty": "int32", "FloatProperty": "float", "Int64Property": "int64"}

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(REPO, "mod_config.json")
DIST = os.path.join(REPO, "dist")
EXTS = (".pak", ".utoc", ".ucas")


def table_path(table: str) -> str:
    return f"FarMech/Content/DataTables/{table}.uasset"


def load_config() -> dict:
    with open(CONFIG, encoding="utf-8") as fh:
        cfg = json.load(fh)
    cfg["tables"] = {t: {r: {p: v for p, v in edits.items() if not p.startswith("_")}
                         for r, edits in rows.items() if not r.startswith("_")}
                     for t, rows in cfg["tables"].items() if not t.startswith("_")}
    cfg["features"] = {f: spec for f, spec in cfg.get("features", {}).items() if not f.startswith("_")}
    cfg["mode"] = {k: v for k, v in cfg.get("mode", {}).items() if not k.startswith("_")}
    cfg["trampling"] = {k: v for k, v in cfg.get("trampling", {}).items() if not k.startswith("_")}
    cfg["storage"] = {k: v for k, v in cfg.get("storage", {}).items() if not k.startswith("_")}
    cfg["hub"] = {k: v for k, v in cfg.get("hub", {}).items() if not k.startswith("_")}
    cfg["cut_buildings"] = {k: v for k, v in cfg.get("cut_buildings", {}).items() if not k.startswith("_")}
    return cfg


def table_features(cfg: dict) -> dict[str, str]:
    """table -> feature id. Every table in the config must belong to exactly one feature. A live feature (a script
    that applies at once) may own tables too; the runtime applies those before a world loads, like any table."""
    owner: dict[str, str] = {}
    for fid, spec in cfg["features"].items():
        if not re.fullmatch(r"[a-z][a-z0-9_]*", fid):
            raise SystemExit(f"feature id '{fid}' must be lower-case letters, digits and _")
        if not spec.get("label"):
            raise SystemExit(f"feature '{fid}' needs a label (the text of its settings row)")
        for t in spec.get("tables", []):
            if t not in cfg["tables"]:
                raise SystemExit(f"feature '{fid}' lists table {t}, which is not in 'tables'")
            if t in owner:
                raise SystemExit(f"table {t} is listed by two features: {owner[t]} and {fid}")
            owner[t] = fid
    missing = [t for t in cfg["tables"] if t not in owner]
    if missing:
        raise SystemExit(f"tables without a feature: {', '.join(missing)} (add them to a feature in 'features')")
    return owner


def mod_name(cfg: dict) -> str:
    name = cfg["mod_name"]
    return name if name.endswith("_P") else name + "_P"


def new_value(kind: str, current, spec):
    """Turn a config value (a number or "x<factor>") into the value to write."""
    if isinstance(spec, str):
        if not spec.lower().startswith("x"):
            raise SystemExit(f"value '{spec}' must be a number or a multiplier like \"x1.5\"")
        value = current * float(spec[1:])
        if kind in ("float", "double"):
            return value
        value = round(value)
        if value >= 50:
            value = int(5 * round(value / 5))
        return max(1, int(value)) if current else 0
    return spec


def cmd_show(table: str, row_filter: str = "", modded: bool = False) -> None:
    source = open_game_container()
    if modded:
        utoc = os.path.join(DIST, mod_name(load_config()) + ".utoc")
        if not os.path.exists(utoc):
            raise SystemExit("no build in dist/ yet; run `build` first")
        mod = IoStoreContainer(utoc)
        if table_path(table) in mod.files:
            source = mod
        else:
            print(f"({table} is not changed by the mod; showing the game's values)")
    dt = read_datatable(source.read_file(table_path(table)))
    for row, data in dt.rows.items():
        if row_filter.lower() in row.lower():
            print(f"[{row}] {json.dumps(plain(data), ensure_ascii=False)}")


def select_rows(table: str, dt, selector: str) -> tuple[list[str], bool]:
    m = ROW_SELECTOR.match(selector)
    if not m:
        raise SystemExit(f"{table}: bad row selector '{selector}'")
    pattern, fld, want = m.group("pattern"), m.group("field"), m.group("value")
    is_pattern = any(c in pattern for c in "*?[") or fld is not None
    if not is_pattern:
        if pattern not in dt.rows:
            raise SystemExit(f"{table}: row '{pattern}' not found")
        return [pattern], False
    rows = [r for r in dt.rows if fnmatch.fnmatchcase(r, pattern)]
    if fld is not None:
        rows = [r for r in rows if fld in dt.rows[r] and display(dt.rows[r][fld]) == want]
    return rows, True


def plan_table(table: str, dt, rows_cfg: dict) -> tuple[dict[int, dict], list[dict]]:
    """Work out every change. Returns ({byte offset: value change}, [map entries to add]) in config order."""
    planned: dict[int, dict] = {}
    inserts: list[dict] = []
    for selector, edits in rows_cfg.items():
        rows, is_pattern = select_rows(table, dt, selector)
        for vpath, spec in edits.items():
            hits = 0
            ins = INSERT_PATH.match(vpath)
            for row in rows:
                if ins:
                    try:
                        hits_ = resolve_steps(dt.rows[row], ins.group("map"), leaves_only=False)
                        if len(hits_) != 1:
                            raise KeyError(f"'{ins.group('map')}' matches {len(hits_)} nodes")
                        _c, node, map_steps = hits_[0]
                    except KeyError as err:
                        if is_pattern:
                            continue
                        raise SystemExit(f"{table} [{row}] {vpath}: {err}")
                    key = ins.group("key")
                    if not isinstance(node, MapNode):
                        raise SystemExit(f"{table} [{row}] {vpath}: '{ins.group('map')}' is not a map")
                    if key in node:
                        raise SystemExit(f"{table} [{row}] {vpath}: '{key}' is already in the map; "
                                         f"use {ins.group('map')}[{key}] to change it")
                    if not isinstance(spec, (int, float)):
                        raise SystemExit(f"{table} [{row}] {vpath}: a new entry needs a number")
                    pending = _pending_insert(inserts, node, key)
                    if pending:                     # a later entry for the same new key overrides it
                        pending["new"] = spec
                    else:
                        inserts.append({"row": row, "map": node, "map_path": ins.group("map"), "key": key,
                                        "new": spec, "steps": map_steps})
                    hits += 1
                    continue
                try:
                    found = resolve_steps(dt.rows[row], vpath)
                except KeyError as err:
                    pending = _pending_for_path(dt.rows[row], vpath, inserts)
                    if pending:                     # changing an entry an earlier rule added
                        kind = VALUE_KINDS.get(pending["map"].value_type, "int32")
                        pending["new"] = new_value(kind, pending["new"], spec)
                        hits += 1
                        continue
                    if is_pattern:
                        continue
                    raise SystemExit(f"{table} [{row}] {vpath}: {err}")
                for concrete, leaf, steps in found:
                    if leaf.kind not in PATCH_FORMATS:
                        raise SystemExit(f"{table} [{row}] {concrete}: can only change numbers, this is a {leaf.kind}")
                    prev = planned.get(leaf.offset)
                    current = prev["new"] if prev else leaf.value
                    parent_map = None
                    if steps[-1][0] == "key":       # a map entry: remember its map for runtime scripts
                        parent_map = resolve_node(dt.rows[row], concrete[:concrete.rfind("[")])
                    planned[leaf.offset] = {"row": row, "path": concrete, "leaf": leaf, "steps": steps,
                                            "map": parent_map, "old": leaf.value,
                                            "new": new_value(leaf.kind, current, spec)}
                    hits += 1
            if hits == 0:
                raise SystemExit(f"{table} [{selector}] {vpath}: matched no values")
    return planned, inserts


def _pending_insert(inserts: list[dict], node, key: str) -> dict | None:
    return next((i for i in inserts if i["map"] is node and i["key"] == key), None)


def _pending_for_path(row_data: dict, vpath: str, inserts: list[dict]) -> dict | None:
    """If vpath is Map[Key] and an earlier rule is adding Key to that map, return that planned entry."""
    m = MAP_KEY_PATH.match(vpath)
    if not m:
        return None
    try:
        node = resolve_node(row_data, m.group("map"))
    except KeyError:
        return None
    return _pending_insert(inserts, node, m.group("key")) if isinstance(node, MapNode) else None


def flat_values(dt) -> dict[tuple[str, str], object]:
    return {(row, p): leaf.value for row, data in dt.rows.items() for p, leaf in leaves(data)}


def verify_rebuilt(table: str, dt, new_data: bytes, planned: dict, inserts: list) -> None:
    """Whole-table check for rebuilt packages: only the planned values changed, only the planned entries were added."""
    new_dt = read_datatable(new_data)                     # also checks the export ends exactly where it should
    old_flat, new_flat = flat_values(dt), flat_values(new_dt)
    by_offset = {leaf.offset: (row, p) for row, data in dt.rows.items() for p, leaf in leaves(data)}
    expected = dict(old_flat)
    for off, change in planned.items():
        expected[by_offset[off]] = change["new"]
    for i in inserts:
        expected[(i["row"], f"{i['map_path']}.{i['key']}")] = i["new"]
    if set(new_flat) != set(expected):
        diff = sorted(set(new_flat) ^ set(expected))[:5]
        raise SystemExit(f"verification failed for {table}: unexpected values {diff}")
    bad = [k for k in expected if not _same(new_flat[k], expected[k])]
    if bad:
        raise SystemExit(f"verification failed for {table}: wrong values at {bad[:5]}")


def _same(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= 1e-4
    return a == b


def build() -> list[str]:
    cfg = load_config()
    game = open_game_container()
    header = game.header()
    files, report = [], []
    item_names = None
    for table, rows_cfg in cfg["tables"].items():
        path = table_path(table)
        original = game.read_file(path)
        dt = read_datatable(original)
        planned, inserts = plan_table(table, dt, rows_cfg)
        buf = bytearray(original)
        for change in planned.values():
            patch(buf, change["leaf"], change["new"])
        chunk_id = game.chunk_id(path)
        package_id, = struct.unpack_from("<Q", chunk_id)
        entry = header.entries[package_id]

        if inserts:
            if item_names is None:
                item_names = set(read_datatable(game.read_file(table_path("DT_Items"))).rows)
            unknown = sorted({i["key"] for i in inserts} - item_names)
            if unknown:
                raise SystemExit(f"{table}: these names are not items in DT_Items: {', '.join(unknown)}")
            editor = PackageEditor(buf)
            for i in inserts:
                editor.add_map_entry(i["map"], i["key"], i["new"])
            new_data = editor.build()
            verify_rebuilt(table, dt, new_data, planned, inserts)
            entry = dataclasses.replace(entry, bundles_size=len(new_data))
        else:
            # verify: re-read the patched table; every planned value must read back, nothing else may move
            check = read_datatable(bytes(buf))
            after = {leaf.offset: leaf.value for row in check.rows.values() for _p, leaf in leaves(row)}
            allowed = set()
            for off, change in planned.items():
                if off not in after or abs(float(after[off]) - float(change["new"])) > 1e-4:
                    raise SystemExit(f"verification failed for {table} [{change['row']}] {change['path']}")
                allowed.update(range(off, off + struct.calcsize(PATCH_FORMATS[change["leaf"].kind])))
            stray = [i for i, (a, b) in enumerate(zip(original, buf)) if a != b and i not in allowed]
            if stray or len(original) != len(buf):
                raise SystemExit(f"verification failed for {table}: unexpected byte changes at {stray[:5]}")
            new_data = bytes(buf)

        files.append(ModFile(path, chunk_id, new_data, entry))
        report.extend((table, c["row"], c["path"], c["old"], c["new"]) for c in planned.values())
        report.extend((table, i["row"], f"{i['map_path']}[+{i['key']}]", None, i["new"]) for i in inserts)

    name = mod_name(cfg)
    if os.path.isdir(DIST):
        for f in os.listdir(DIST):
            if f.startswith(name) and f.endswith(EXTS):
                os.remove(os.path.join(DIST, f))
    written = write_mod_container(DIST, name, files)

    # read the finished container back and confirm every table round-trips
    out = IoStoreContainer(os.path.join(DIST, name + ".utoc"))
    out_header = out.header()
    for f in files:
        pid, = struct.unpack_from("<Q", f.chunk_id)
        if out.read_file(f.path) != f.data or out_header.entries[pid] != f.entry:
            raise SystemExit(f"round-trip failed for {f.path}")

    report_path = os.path.join(DIST, name + "_changes.txt")
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(f"{'table':<16} {'row':<24} {'value':<44} {'vanilla':>9}  new\n")
        for table, row, vpath, old, new in report:
            fh.write(f"{table:<16} {row:<24} {vpath:<44} {_num(old):>9}  {_num(new)}\n")
    print_summary(report)
    print(f"full list of {len(report)} changed values: {report_path}")
    for p in written:
        print(f"wrote {p} ({os.path.getsize(p):,} bytes)")
    return written


def print_summary(report: list) -> None:
    """One line per (table, value path, vanilla -> new), merging rows that changed the same way."""
    groups: dict[tuple, list[str]] = {}
    for table, row, vpath, old, new in report:
        groups.setdefault((table, vpath, old, new), []).append(row)
    lines = sorted(groups.items(), key=lambda kv: (kv[0][0], -len(kv[1])))
    shown = 0
    for (table, vpath, old, new), rows in lines:
        if shown == 40:
            print(f"... {len(lines) - shown} more groups in the report file")
            break
        where = rows[0] if len(rows) == 1 else f"{len(rows)} rows ({rows[0]}, {rows[1]}{', ...' if len(rows) > 2 else ''})"
        print(f"{table:<16} {vpath:<42} {_num(old):>7} -> {_num(new):<7} {where}")
        shown += 1


def _num(v) -> str:
    return "new" if v is None else f"{v:g}"


def cmd_install() -> None:
    written = build()
    target = os.path.join(paks_dir(), "~mods")
    os.makedirs(target, exist_ok=True)
    for p in written:
        shutil.copy2(p, target)
    print(f"installed into {target}")


def cmd_uninstall() -> None:
    name = mod_name(load_config())
    target = os.path.join(paks_dir(), "~mods")
    removed = 0
    for ext in EXTS:
        p = os.path.join(target, name + ext)
        if os.path.exists(p):
            os.remove(p)
            removed += 1
    print(f"removed {removed} file(s) from {target}")


# ---------------------------------------------------------------- runtime (UE4SS) mod

RUNTIME_NAME = "HardcoreLogistics"
RUNTIME_SRC = os.path.join(REPO, "runtime", RUNTIME_NAME)
RUNTIME_DIST = os.path.join(DIST, "runtime", RUNTIME_NAME)


def ue4ss_mods_dir() -> str:
    from iostore import game_dir
    return os.path.join(game_dir(), "FarMech", "Binaries", "Win64", "ue4ss", "Mods")


def _lua(v) -> str:
    if v is None:
        return "nil"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, str):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    if isinstance(v, (list, tuple)):
        return "{" + ", ".join(_lua(x) for x in v) + "}"
    if isinstance(v, dict):
        return "{" + ", ".join((f"{k} = " if str(k).isidentifier() else f"[{_lua(k)}] = ") + _lua(x) for k, x in v.items()) + "}"
    raise TypeError(f"cannot write {type(v).__name__} to Lua")


def _lua_steps(steps: list[tuple]) -> list[list]:
    return [[s[0], s[1], s[2] or "", s[3]] if s[0] == "select" else list(s) for s in steps]


def build_runtime() -> str:
    """Resolve mod_config.json against the installed game and write the UE4SS mod to dist/runtime/."""
    import datetime
    cfg = load_config()
    owner = table_features(cfg)
    game = open_game_container()
    tables, counts = [], {"values": 0, "maps": 0, "added": 0}
    for table, rows_cfg in cfg["tables"].items():
        dt = read_datatable(game.read_file(table_path(table)))
        planned, inserts = plan_table(table, dt, rows_cfg)
        values, groups = [], {}

        def group_for(row, steps, mapnode):
            if id(mapnode) not in groups:
                vanilla = [[k, leaf.value] for k, leaf in mapnode.items()]
                groups[id(mapnode)] = {"row": row, "steps": _lua_steps(steps), "vanilla": vanilla,
                                       "target": {k: v for k, v in vanilla}}
            return groups[id(mapnode)]

        for c in planned.values():
            if c["map"] is not None:
                group_for(c["row"], c["steps"][:-1], c["map"])["target"][c["steps"][-1][1]] = c["new"]
            else:
                values.append({"row": c["row"], "steps": _lua_steps(c["steps"]), "vanilla": c["old"], "value": c["new"]})
        for i in inserts:
            group_for(i["row"], i["steps"], i["map"])["target"][i["key"]] = i["new"]
            counts["added"] += 1
        maps = [{**g, "target": [[k, v] for k, v in g["target"].items()]} for g in groups.values()]
        base = table.rsplit("/", 1)[-1]
        tables.append({"name": table, "path": f"/Game/DataTables/{table}.{base}", "feature": owner[table],
                       "values": values, "maps": maps})
        counts["values"] += len(values)
        counts["maps"] += len(maps)

    features = [{"id": fid, "label": spec["label"], "live": bool(spec.get("live"))}
                for fid, spec in cfg["features"].items()]
    mode = cfg["mode"]
    if mode and not all(mode.get(k) for k in ("title", "description", "base_preset")):
        raise SystemExit("'mode' needs a title, a description and a base_preset (Balanced, Challenge, Creative or Relaxed)")
    trampling = cfg["trampling"]
    for k, v in trampling.items():
        if k == "sound":
            if not isinstance(v, str) or (v and not v.startswith("/Game/")):
                raise SystemExit(f"trampling.sound must be a /Game/... FMOD event path, or '' for none (got {v!r})")
        elif k == "sound_cut_ms" and isinstance(v, list):
            if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and x >= 0 for x in v):
                raise SystemExit(f"trampling.sound_cut_ms must be a number or a list of numbers of 0 or more (got {v!r})")
        elif not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0:
            raise SystemExit(f"trampling.{k} must be a number of 0 or more (got {v!r})")
    storage = cfg["storage"]
    for k, v in storage.items():
        if k == "storage_class":
            if not isinstance(v, str) or not v.startswith("/Game/"):
                raise SystemExit(f"storage.storage_class must be a /Game/... class path (got {v!r})")
        elif not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0:
            raise SystemExit(f"storage.{k} must be a number of 0 or more (got {v!r})")
    from build_buildings import runtime_settings
    buildings = runtime_settings() if (cfg.get("hub") or cfg.get("cut_buildings")) else {}
    # the buildings' own table changes (hubs tied to a feature: shown, and a milestone reward, only where it runs)
    shown_by = []
    for t in buildings.get("tables", []):
        if t["name"] in cfg["tables"]:
            raise SystemExit(f"{t['name']} is changed by the buildings (hub.feature) and listed in 'tables'; "
                             f"one table cannot take both")
        if t["feature"] not in cfg["features"]:
            raise SystemExit(f"the buildings' {t['name']} changes belong to an unknown feature {t['feature']!r}")
        tables.append(t)
        shown_by.append(f"{t['name']} ({t['feature']})")
    edits = {"generated": datetime.datetime.now().isoformat(timespec="seconds"), "version": cfg.get("version", ""),
             "features": features,
             "mode": mode or None, "trampling": trampling, "storage": storage, "hub": buildings.get("hub", {}),
             "drones": buildings.get("drones", {}), "unlocks": buildings.get("unlocks", []), "tables": tables}
    scripts = os.path.join(RUNTIME_DIST, "Scripts")
    os.makedirs(scripts, exist_ok=True)
    with open(os.path.join(scripts, "edits.lua"), "w", encoding="utf-8") as fh:
        fh.write("-- Generated by tools/build_mod.py from mod_config.json. Do not edit; edit the config and rebuild.\n")
        fh.write("return " + _lua(edits) + "\n")
    for f in os.listdir(os.path.join(RUNTIME_SRC, "Scripts")):
        if f.endswith(".lua"):
            shutil.copy2(os.path.join(RUNTIME_SRC, "Scripts", f), os.path.join(scripts, f))
    print(f"runtime mod: {counts['values']} value changes, {counts['maps']} cost lists rewritten "
          f"({counts['added']} added entries)"
          + (f"; the hubs shown through {', '.join(shown_by)}" if shown_by else "") + f" -> {RUNTIME_DIST}")
    from check_lua import run_check
    if not run_check([scripts]):
        raise SystemExit("Lua check failed; fix the scripts above (nothing was installed)")
    return RUNTIME_DIST


def _set_mods_txt(mods_dir: str, enabled: bool) -> None:
    path = os.path.join(mods_dir, "mods.txt")
    lines = open(path, encoding="utf-8").read().splitlines() if os.path.exists(path) else []
    entry = f"{RUNTIME_NAME} : {1 if enabled else 0}"
    for i, line in enumerate(lines):
        if line.split(":")[0].strip() == RUNTIME_NAME:
            lines[i] = entry
            break
    else:
        at = next((i for i, l in enumerate(lines) if l.startswith("; Built-in keybinds")), len(lines))
        lines.insert(at, entry)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def cmd_install_runtime() -> None:
    src = build_runtime()
    mods = ue4ss_mods_dir()
    if not os.path.isdir(mods):
        raise SystemExit(f"UE4SS is not installed (no {mods})")
    target = os.path.join(mods, RUNTIME_NAME)
    os.makedirs(os.path.join(target, "Scripts"), exist_ok=True)
    for f in os.listdir(os.path.join(src, "Scripts")):
        if f.endswith(".lua"):
            shutil.copy2(os.path.join(src, "Scripts", f), os.path.join(target, "Scripts", f))
    worlds = os.path.join(target, "worlds.txt")
    if not os.path.exists(worlds):
        with open(worlds, "w", encoding="utf-8") as fh:
            fh.write("# Hardcore Logistics: one line per world save slot, listing the features that are on, or off\n"
                     "# (for example World_3=cargo,deliveries or World_4=off).\n")
    _set_mods_txt(mods, True)
    print(f"installed runtime mod into {target} (worlds file kept: {worlds})")
    cmd_uninstall()      # the static pak would make every world hardcore


def cmd_disable_runtime() -> None:
    _set_mods_txt(ue4ss_mods_dir(), False)
    print(f"disabled {RUNTIME_NAME} in mods.txt")


def main(argv: list[str]) -> None:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    cmd, args = argv[0], argv[1:]
    if cmd == "show" and args:
        modded = "--modded" in args
        rest = [a for a in args if a != "--modded"]
        cmd_show(rest[0], rest[1] if len(rest) > 1 else "", modded)
    elif cmd == "build":
        build()
    elif cmd == "install":
        cmd_install()
    elif cmd == "uninstall":
        cmd_uninstall()
    elif cmd == "runtime":
        build_runtime()
    elif cmd == "install-runtime":
        cmd_install_runtime()
    elif cmd == "disable-runtime":
        cmd_disable_runtime()
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1:])
