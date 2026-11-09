"""Read UE 4.27 zen packages that use tagged properties (Lightyear Frontier's cooked format) and patch numbers.

Every parsed value remembers its byte offset in the package, so a number can be changed in place without
re-serialising anything. Only fixed-size numeric values (int, float, bool, raw byte) are patchable, which
keeps the package byte-for-byte identical apart from the edited values.

Paths address values inside a DataTable row, for example:
    MaxHauling                                  plain field
    Stats[Tag=Upgrade.Hauling.Capacity].Value   array element whose Tag equals the text, then a field
    Stats[2].Value                              array element by index
    Cost[IronFrame]                             map value by key
    Cost[*]                                     every value of a map (or every element of an array)
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass

GUID_SUFFIX = re.compile(r"_\d+_[0-9A-F]{32}$")      # blueprint struct members: Name_12_<guid>
PATCH_FORMATS = {"int32": "<i", "uint32": "<I", "int64": "<q", "int16": "<h", "uint16": "<H",
                 "uint8": "<B", "bool": "<B", "float": "<f", "double": "<d"}
NATIVE_STRUCTS = {"Vector": "<3f", "Vector2D": "<2f", "Vector4": "<4f", "Rotator": "<3f", "Quat": "<4f",
                  "LinearColor": "<4f", "Color": "<4B", "IntPoint": "<2i", "IntVector": "<3i", "Guid": "<4I",
                  "Box2D": "<4fB", "Box": "<6fB", "DateTime": "<q", "Timespan": "<q"}


@dataclass
class Leaf:
    kind: str
    offset: int
    value: object

    def __repr__(self) -> str:
        return repr(self.value)


class MapNode(dict):
    """A parsed map (behaves like a dict) that remembers where it lives, so entries can be added."""
    size_offset = count_offset = end_offset = -1
    key_type = value_type = ""


class StructNode(dict):
    """A parsed tagged struct. Keys are field names without blueprint GUID suffixes; `raw` keeps the real
    property names (for example `MaxHauling_18_F30C...`), which runtime scripts need."""

    def __init__(self):
        super().__init__()
        self.raw: dict[str, str] = {}


class ZenPackage:
    """Header of a UE 4.27 IoStore package: name map, export map, where export data starts."""

    def __init__(self, data: bytes):
        (_n0, _n1, _s0, _s1, self.flags, _cooked, nm_off, _nm_size, _nh_off, nh_size,
         _imp_off, exp_off, eb_off, gd_off, gd_size, _pad) = struct.unpack_from("<IIIIIIiiiiiiiiii", data, 0)
        self.names = _name_batch(data, nm_off, nh_size // 8 - 1)
        self.header_end = gd_off + gd_size
        self.exports = []
        for i in range((eb_off - exp_off) // 72):
            ser_off, ser_size = struct.unpack_from("<QQ", data, exp_off + 72 * i)
            name_idx, = struct.unpack_from("<I", data, exp_off + 72 * i + 16)
            self.exports.append((self.names[name_idx & 0x3FFFFFFF], ser_size))
        if self.flags & 0x2000:
            raise ValueError("package uses unversioned properties; this tool only reads tagged properties")


def export_properties(data: bytes) -> dict:
    """Tagged properties of every export of a zen package, keyed by export name (plain values).

    Export data follows the header in export-bundle order, not export-map order. UE 4.27 writes all bundle headers
    {FirstEntryIndex, EntryCount} and then the entries {LocalExportIndex, Command}; every export has a Create and a
    Serialize entry, so the number of headers follows from the region's size."""
    pkg = ZenPackage(data)
    _imp_off, exp_off, eb_off, gd_off = struct.unpack_from("<iiii", data, 40)
    nexp = len(pkg.exports)
    nbundles = (gd_off - eb_off - 16 * nexp) // 8
    entries = eb_off + 8 * nbundles
    pos, out = pkg.header_end, {}
    for b in range(nbundles):
        first, count = struct.unpack_from("<II", data, eb_off + 8 * b)
        for k in range(count):
            idx, command = struct.unpack_from("<II", data, entries + 8 * (first + k))
            if command != 1:                              # 1 = Serialize
                continue
            name, size = pkg.exports[idx]
            try:
                out[name] = plain(_Reader(data, pkg.names, pos).tagged_struct())
            except Exception as ex:  # noqa: BLE001 - report, don't stop: other exports may still read
                out[name] = {"<unreadable>": str(ex)}
            pos += size
    return out


def _name_batch(d: bytes, p: int, count: int) -> list[str]:
    names = []
    for _ in range(count):
        b0, b1 = d[p], d[p + 1]
        p += 2
        length = ((b0 & 0x7F) << 8) | b1
        if b0 & 0x80:
            names.append(d[p:p + 2 * length].decode("utf-16-le")); p += 2 * length
        else:
            names.append(d[p:p + length].decode("latin-1")); p += length
    return names


class _Reader:
    def __init__(self, data: bytes, names: list[str], pos: int):
        self.d, self.names, self.p = data, names, pos

    def take(self, fmt: str):
        v = struct.unpack_from(fmt, self.d, self.p)
        self.p += struct.calcsize(fmt)
        return v[0] if len(v) == 1 else v

    def name(self) -> str:
        idx, num = struct.unpack_from("<II", self.d, self.p)
        self.p += 8
        base = self.names[idx & 0x3FFFFFFF]
        return base if num == 0 else f"{base}_{num - 1}"

    def fstr(self) -> str:
        n = self.take("<i")
        if n == 0:
            return ""
        if n > 0:
            s = self.d[self.p:self.p + n - 1].decode("latin-1"); self.p += n
        else:
            s = self.d[self.p:self.p - 2 * n - 2].decode("utf-16-le"); self.p += -2 * n
        return s

    def text(self) -> str | None:
        self.take("<I")
        history = self.take("<b")
        if history == -1:
            return self.fstr() if self.take("<i") else ""
        if history == 0:
            self.fstr(); self.fstr()
            return self.fstr()
        if history == 11:
            table = self.name()
            return f"<string table {table}:{self.fstr()}>"
        return None

    # -- tagged properties
    def tagged_struct(self) -> dict:
        out = StructNode()
        while True:
            pname = self.name()
            if pname == "None":
                return out
            ptype = self.name()
            size_pos = self.p
            size, index = self.take("<i"), self.take("<i")
            tag: dict = {"size_pos": size_pos}
            if ptype == "StructProperty":
                tag["struct"] = self.name(); self.p += 16
            elif ptype == "BoolProperty":
                tag["bool"] = Leaf("bool", self.p, self.d[self.p] != 0); self.p += 1
            elif ptype in ("ByteProperty", "EnumProperty"):
                tag["enum"] = self.name()
            elif ptype in ("ArrayProperty", "SetProperty"):
                tag["inner"] = self.name()
            elif ptype == "MapProperty":
                tag["inner"], tag["value"] = self.name(), self.name()
            self.p += 17 if self.d[self.p] else 1          # optional property GUID
            start = self.p
            try:
                node = self.value(ptype, size, tag)
            except Exception:  # noqa: BLE001 - keep going; the size field lets us skip anything unexpected
                node = Leaf("unparsed", start, None)
            self.p = start + size
            key = GUID_SUFFIX.sub("", pname)
            key = f"{key}[{index}]" if index else key
            out[key] = node
            out.raw[key] = pname

    def value(self, ptype: str, size: int, tag: dict):
        p = self.p
        simple = {"IntProperty": ("int32", "<i"), "UInt32Property": ("uint32", "<I"), "Int64Property": ("int64", "<q"),
                  "Int16Property": ("int16", "<h"), "UInt16Property": ("uint16", "<H"), "FloatProperty": ("float", "<f"),
                  "DoubleProperty": ("double", "<d")}
        if ptype in simple:
            kind, fmt = simple[ptype]
            return Leaf(kind, p, self.take(fmt))
        if ptype == "BoolProperty":
            return tag.get("bool") or Leaf("bool", p, self.take("<B") != 0)
        if ptype == "ByteProperty":
            return Leaf("uint8", p, self.take("<B")) if size == 1 else Leaf("enum", p, self.name())
        if ptype == "EnumProperty":
            return Leaf("enum", p, self.name())
        if ptype == "NameProperty":
            return Leaf("name", p, self.name())
        if ptype == "StrProperty":
            return Leaf("str", p, self.fstr())
        if ptype == "TextProperty":
            return Leaf("text", p, self.text())
        if ptype in ("ObjectProperty", "ClassProperty", "InterfaceProperty", "WeakObjectProperty", "LazyObjectProperty"):
            return Leaf("object", p, self.take("<i"))
        if ptype in ("SoftObjectProperty", "SoftClassProperty"):
            path = self.name()
            sub = self.fstr()
            return Leaf("softpath", p, path + (":" + sub if sub else ""))
        if ptype == "StructProperty":
            return self.struct_value(tag["struct"])
        if ptype == "ArrayProperty":
            return self.array(tag["inner"], size)
        if ptype == "SetProperty":
            self.take("<i")
            return [self.element(tag["inner"]) for _ in range(self.take("<i"))]
        if ptype == "MapProperty":
            for _ in range(self.take("<i")):                    # keys to remove (always 0 in cooked data)
                self.element(tag["inner"])
            out = MapNode()
            out.size_offset, out.count_offset = tag.get("size_pos", -1), self.p
            out.key_type, out.value_type = tag["inner"], tag["value"]
            for _ in range(self.take("<i")):
                k = self.element(tag["inner"])
                out[display(k)] = self.element(tag["value"])
            out.end_offset = p + size
            return out
        return Leaf("raw", p, None)

    def struct_value(self, struct_name: str):
        p = self.p
        if struct_name in NATIVE_STRUCTS:
            return Leaf("struct", p, self.take(NATIVE_STRUCTS[struct_name]))
        if struct_name == "GameplayTagContainer":
            return Leaf("tags", p, [self.name() for _ in range(self.take("<i"))])
        if struct_name in ("SoftObjectPath", "SoftClassPath"):
            path = self.name()
            self.fstr()
            return Leaf("softpath", p, path)
        return self.tagged_struct()

    def array(self, inner: str, size: int):
        n = self.take("<i")
        if inner == "StructProperty":
            self.name(); self.name(); self.take("<i"); self.take("<i")     # inner tag: name, type, size, index
            struct_name = self.name()
            self.p += 16
            self.p += 17 if self.d[self.p] else 1
            return [self.struct_value(struct_name) for _ in range(n)]
        if inner == "ByteProperty" and n and (size - 4) // n == 1:
            return [Leaf("uint8", self.p + i, self.d[self.p + i]) for i in range(n)]
        return [self.element(inner) for _ in range(n)]

    def element(self, ptype: str):
        """A value inside an array, set or map (no per-element tag)."""
        if ptype == "StructProperty":
            return self.tagged_struct()
        if ptype in ("ByteProperty", "EnumProperty"):
            return Leaf("enum", self.p, self.name())
        if ptype == "BoolProperty":
            return Leaf("bool", self.p, self.take("<B") != 0)
        return self.value(ptype, 0, {})


def display(node) -> str:
    """Text used to match selectors: leaves show their value, single-field structs show that field."""
    if isinstance(node, Leaf):
        return str(node.value)
    if isinstance(node, dict) and len(node) == 1:
        return display(next(iter(node.values())))
    return repr(node)


def plain(node):
    """Convert a parsed node into plain Python values for printing."""
    if isinstance(node, Leaf):
        return node.value
    if isinstance(node, dict):
        return {k: plain(v) for k, v in node.items()}
    if isinstance(node, list):
        return [plain(v) for v in node]
    return node


@dataclass
class DataTable:
    package: ZenPackage
    rows: dict[str, dict]


def read_datatable(data: bytes) -> DataTable:
    pkg = ZenPackage(data)
    if len(pkg.exports) != 1:
        raise ValueError(f"expected a single-export DataTable package, found {len(pkg.exports)} exports")
    r = _Reader(data, pkg.names, pkg.header_end)
    r.tagged_struct()                    # UDataTable's own properties (RowStruct)
    if r.take("<i"):                     # object GUID present?
        r.p += 16
    rows = {}
    for _ in range(r.take("<i")):
        row_name = r.name()
        rows[row_name] = r.tagged_struct()
    expected_end = pkg.header_end + pkg.exports[0][1]
    if r.p != expected_end:
        raise ValueError(f"DataTable parse ended at {r.p}, expected {expected_end}; refusing to patch")
    return DataTable(pkg, rows)


def _split_path(path: str) -> list[str]:
    parts, depth, cur = [], 0, ""
    for ch in path:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        if ch == "." and depth == 0:
            parts.append(cur); cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts


_SEGMENT = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)(?:\[([^\]]+)\])?")


def resolve_node(row: dict, path: str):
    """Resolve a path that must point at exactly one node (a value, struct, array or map)."""
    hits = resolve_all(row, path, leaves_only=False)
    if len(hits) != 1:
        raise KeyError(f"'{path}' matches {len(hits)} nodes")
    return hits[0][1]


def resolve_all(row: dict, path: str, leaves_only: bool = True) -> list[tuple[str, Leaf]]:
    """Resolve a path to (concrete path, value) pairs. `[*]` selects every element of an array or map."""
    return [(c, n) for c, n, _s in resolve_steps(row, path, leaves_only)]


def _field_step(node: dict, fld: str) -> tuple:
    return ("field", node.raw.get(fld, fld) if isinstance(node, StructNode) else fld)


def resolve_steps(row: dict, path: str, leaves_only: bool = True) -> list[tuple[str, object, list[tuple]]]:
    """Like resolve_all, but each hit also carries machine steps for runtime scripts:
    ("field", real property name), ("select", field, inner field or None, text), ("index", i), ("key", text)."""
    current: list[tuple[str, object, list]] = [("", row, [])]
    for seg in _split_path(path):
        m = _SEGMENT.fullmatch(seg)
        if not m:
            raise KeyError(f"bad path segment '{seg}' in '{path}'")
        fld, sel = m.groups()
        nxt: list[tuple[str, object, list]] = []
        for prefix, node, steps in current:
            here = f"{prefix}.{fld}" if prefix else fld
            if not isinstance(node, dict) or fld not in node:
                have = ", ".join(node) if isinstance(node, dict) else type(node).__name__
                raise KeyError(f"'{fld}' not found (available: {have})")
            fsteps = steps + [_field_step(node, fld)]
            node = node[fld]
            if sel is None:
                nxt.append((here, node, fsteps))
            elif sel == "*":
                if isinstance(node, list):
                    nxt.extend((f"{here}[{i}]", el, fsteps + [("index", i)]) for i, el in enumerate(node))
                elif isinstance(node, dict):
                    nxt.extend((f"{here}[{k}]", v, fsteps + [("key", k)]) for k, v in node.items())
                else:
                    raise KeyError(f"'{fld}' is not an array or map")
            elif isinstance(node, list):
                if "=" in sel:
                    key, want = sel.split("=", 1)
                    hits = [el for el in node if isinstance(el, dict) and key in el and display(el[key]) == want]
                    if len(hits) != 1:
                        raise KeyError(f"{len(hits)} elements of '{fld}' have {key} = {want}")
                    sub = hits[0][key]
                    inner = None
                    if isinstance(sub, dict) and len(sub) == 1:
                        only = next(iter(sub))
                        inner = sub.raw.get(only, only) if isinstance(sub, StructNode) else only
                    raw_key = hits[0].raw.get(key, key) if isinstance(hits[0], StructNode) else key
                    nxt.append((f"{here}[{sel}]", hits[0], fsteps + [("select", raw_key, inner, want)]))
                else:
                    nxt.append((f"{here}[{sel}]", node[int(sel)], fsteps + [("index", int(sel))]))
            elif isinstance(node, dict):
                if sel not in node:
                    raise KeyError(f"key '{sel}' not in '{fld}' (keys: {', '.join(node)})")
                nxt.append((f"{here}[{sel}]", node[sel], fsteps + [("key", sel)]))
            else:
                raise KeyError(f"'{fld}' is not an array or map")
        current = nxt
    for concrete, node, _steps in current:
        if leaves_only and not isinstance(node, Leaf):
            raise KeyError(f"'{concrete}' points at a struct, not a value: {plain(node)}")
    return current


def resolve(row: dict, path: str) -> Leaf:
    hits = resolve_all(row, path)
    if len(hits) != 1:
        raise KeyError(f"'{path}' matches {len(hits)} values; use a single-value path")
    return hits[0][1]


def leaves(node, prefix: str = ""):
    """Yield (path, Leaf) for every value inside a parsed node."""
    if isinstance(node, Leaf):
        yield prefix, node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from leaves(v, f"{prefix}.{k}" if prefix else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from leaves(v, f"{prefix}[{i}]")


def patch(buf: bytearray, leaf: Leaf, new_value) -> None:
    fmt = PATCH_FORMATS.get(leaf.kind)
    if fmt is None:
        raise TypeError(f"can only patch numbers; this value is a {leaf.kind} ({leaf.value!r})")
    if leaf.kind in ("float", "double"):
        new_value = float(new_value)
    elif leaf.kind == "bool":
        new_value = 1 if new_value else 0
    elif isinstance(new_value, float) and not new_value.is_integer():
        raise TypeError(f"{leaf.kind} needs a whole number, got {new_value}")
    else:
        new_value = int(new_value)
    struct.pack_into(fmt, buf, leaf.offset, new_value)
