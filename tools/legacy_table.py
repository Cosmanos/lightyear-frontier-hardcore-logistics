"""Add rows to a UE 4.27 DataTable in legacy form (see legacy_package.py).

A DataTable export is: the table's own tagged properties, an int32 "has object GUID" flag (and the GUID when set),
int32 NumRows, then NumRows times (FName row name, row struct as tagged properties ending in None). A new row is built from an existing one: its tags are kept in order
and chosen values are replaced with freshly serialized ones (property sizes are recomputed).

FPropertyTag (4.27): FName Name, FName Type, int32 Size, int32 ArrayIndex, type extras (StructProperty: FName
StructName + FGuid; BoolProperty: uint8 value; ByteProperty / EnumProperty / ArrayProperty / SetProperty: FName;
MapProperty: FName key type + FName value type), uint8 HasPropertyGuid (+ FGuid), then Size bytes of value.
"""
import struct

from legacy_package import LegacyPackage, _fstr


class Tag:
    def __init__(self, name: str, ptype: str, head: bytes, value: bytes):
        self.name, self.type, self.head, self.value = name, ptype, head, value

    def bytes(self) -> bytes:
        # head = everything from the name to the end of the tag, with Size at byte 16
        head = bytearray(self.head)
        struct.pack_into("<i", head, 16, len(self.value))
        return bytes(head) + self.value


class TableData:
    """The DataTable export of a LegacyPackage, split into rows of tags."""

    def __init__(self, pkg: LegacyPackage, export_index: int = 0):
        self.pkg = pkg
        self.export = pkg.export_entries()[export_index]
        self.start = self.export["offset"] - pkg.total_header_size
        self.data = pkg.uexp[self.start:self.start + self.export["size"]]
        p, self.table_tags = self._read_tags(0)
        has_guid, = struct.unpack_from("<i", self.data, p)   # UObject: "has an object GUID", then the GUID
        p += 4 + (16 if has_guid else 0)
        self.rows_offset = p                    # NumRows
        n, = struct.unpack_from("<i", self.data, p)
        p += 4
        self.rows: list[tuple[str, bytes, list[Tag]]] = []     # (name, its 8 bytes as stored, tags)
        for _ in range(n):
            row = self._name(p)
            tags_end, tags = self._read_tags(p + 8)
            self.rows.append((row, self.data[p:p + 8], tags))
            p = tags_end
        self.rows_end = p
        self.tail = self.data[p:]               # anything after the rows (normally nothing)

    def _name(self, p: int) -> str:
        idx, num = struct.unpack_from("<ii", self.data, p)
        base = self.pkg.names[idx]
        return base if num == 0 else f"{base}_{num - 1}"

    def _read_tags(self, p: int) -> tuple[int, list[Tag]]:
        tags = []
        while True:
            name = self._name(p)
            if name == "None":
                return p + 8, tags
            ptype = self._name(p + 8)
            size, = struct.unpack_from("<i", self.data, p + 16)
            q = p + 24
            if ptype == "StructProperty":
                q += 8 + 16
            elif ptype == "BoolProperty":
                q += 1
            elif ptype in ("ByteProperty", "EnumProperty", "ArrayProperty", "SetProperty"):
                q += 8
            elif ptype == "MapProperty":
                q += 16
            has_guid = self.data[q]
            q += 1 + (16 if has_guid else 0)
            tags.append(Tag(name, ptype, self.data[p:q], self.data[q:q + size]))
            p = q + size

    def row(self, name: str) -> list[Tag]:
        for r, _raw, tags in self.rows:
            if r == name:
                return tags
        raise KeyError(f"no row {name}")

    # -- value builders (names must be in the package's name map; add them with name_ref)
    def name_ref(self, s: str) -> bytes:
        if s not in self.pkg.names:
            self.pkg.names.append(s)
        return struct.pack("<ii", self.pkg.names.index(s), 0)

    def text_value(self, source: str, key: str, namespace: str = "", flags: int = 0) -> bytes:
        """FText with Base history: shown as `source` unless a localization table has namespace/key."""
        return struct.pack("<Ib", flags, 0) + _fstr(namespace) + _fstr(key) + _fstr(source)

    def soft_path_value(self, path: str) -> bytes:
        return self.name_ref(path) + _fstr("")

    def name_int_map_value(self, entries: dict[str, int]) -> bytes:
        out = struct.pack("<ii", 0, len(entries))
        for k, v in entries.items():
            out += self.name_ref(k) + struct.pack("<i", v)
        return out

    def add_row(self, name: str, tags: list[Tag]) -> None:
        if any(r == name for r, _raw, _tags in self.rows):
            raise ValueError(f"row {name} already exists")
        self.rows.append((name, self.name_ref(name), tags))

    def build(self) -> None:
        """Write the rows back into the package's export data."""
        out = bytearray(self.data[:self.rows_offset])
        out += struct.pack("<i", len(self.rows))
        none = self.name_ref("None")
        for _r, raw, tags in self.rows:
            out += raw
            for t in tags:
                out += t.bytes()
            out += none
        out += self.tail
        self.pkg.replace_export_data(self.export, bytes(out))
