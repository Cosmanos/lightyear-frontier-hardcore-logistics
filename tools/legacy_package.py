"""Read and rewrite UE 4.27 legacy (.uasset + .uexp) packages, as retoc's to-legacy writes them.

Only what cloning a Blueprint needs: rename entries of the name map (for example the class and package names), point
an import at another object (a different mesh), and write the package back with every header offset after the name
map shifted. Imports, exports and the export data refer to names by index, so renaming a name never touches them.

Header layout (cooked, unversioned, LegacyFileVersion -7): summary, name map, import map (28 bytes each), export map
(104 bytes each), depends map, asset registry data, preload dependencies; the export data follows in the .uexp, and
export SerialOffset values count from the start of the .uasset.
"""
import struct
import zlib

TAG = 0x9E2A83C1


def _crc_table_msb() -> list[int]:
    table = []
    for i in range(256):
        crc = i << 24
        for _ in range(8):
            crc = ((crc << 1) ^ 0x04C11DB7) if crc & 0x80000000 else (crc << 1)
        table.append(crc & 0xFFFFFFFF)
    return table


_TABLE_MSB = _crc_table_msb()


def name_hashes(name: str) -> tuple[int, int]:
    """(NonCasePreservingHash, CasePreservingHash) of a name-map entry: FCrc::Strihash_DEPRECATED and
    FCrc::StrCrc32, each cut to 16 bits."""
    h = 0
    for ch in name.upper():
        h = ((h >> 8) & 0x00FFFFFF) ^ _TABLE_MSB[(h ^ (ord(ch) & 0xFF)) & 0xFF]
    return h & 0xFFFF, zlib.crc32(name.encode("utf-32-le")) & 0xFFFF


class _R:
    def __init__(self, d: bytes, p: int = 0):
        self.d, self.p = d, p

    def i32(self) -> int:
        v, = struct.unpack_from("<i", self.d, self.p); self.p += 4; return v

    def u32(self) -> int:
        v, = struct.unpack_from("<I", self.d, self.p); self.p += 4; return v

    def i64(self) -> int:
        v, = struct.unpack_from("<q", self.d, self.p); self.p += 8; return v

    def raw(self, n: int) -> bytes:
        v = self.d[self.p:self.p + n]; self.p += n; return v

    def fstr(self) -> str:
        n = self.i32()
        if n == 0:
            return ""
        if n > 0:
            s = self.d[self.p:self.p + n - 1].decode("latin-1"); self.p += n
        else:
            s = self.d[self.p:self.p - 2 * n - 2].decode("utf-16-le"); self.p += -2 * n
        return s


def _fstr(s: str) -> bytes:
    if s == "":
        return struct.pack("<i", 0)
    try:
        b = s.encode("latin-1") + b"\0"
        return struct.pack("<i", len(b)) + b
    except UnicodeEncodeError:
        b = s.encode("utf-16-le") + b"\0\0"
        return struct.pack("<i", -(len(b) // 2)) + b


class LegacyPackage:
    def __init__(self, uasset: bytes, uexp: bytes):
        r = _R(uasset)
        if r.u32() != TAG:
            raise ValueError("not a UE package (bad tag)")
        self.legacy_version = r.i32()
        if self.legacy_version != -7:
            raise ValueError(f"unsupported legacy file version {self.legacy_version} (expected -7, UE 4.27)")
        self.ue3_version, self.ue4_version, self.licensee_version = r.i32(), r.i32(), r.i32()
        ncustom = r.i32()
        self.custom_versions = r.raw(20 * ncustom)
        self.custom_count = ncustom
        self.total_header_size = r.i32()
        self.folder_name = r.fstr()
        self.package_flags = r.u32()
        if not self.package_flags & 0x80000000:
            raise ValueError("only cooked packages (PKG_FilterEditorOnly) are supported")
        self.name_count, self.name_offset = r.i32(), r.i32()
        self.gatherable_count, self.gatherable_offset = r.i32(), r.i32()
        self.export_count, self.export_offset = r.i32(), r.i32()
        self.import_count, self.import_offset = r.i32(), r.i32()
        self.depends_offset = r.i32()
        self.soft_refs_count, self.soft_refs_offset = r.i32(), r.i32()
        self.searchable_names_offset = r.i32()
        self.thumbnail_offset = r.i32()
        self.guid = r.raw(16)
        ngen = r.i32()
        self.generations = [(r.i32(), r.i32()) for _ in range(ngen)]
        self.saved_by = r.raw(10) + _fstr(r.fstr())         # major, minor, patch (uint16), changelist, branch
        self.compatible_with = r.raw(10) + _fstr(r.fstr())
        self.compression_flags = r.u32()
        if r.i32() != 0:
            raise ValueError("compressed packages are not supported")
        self.package_source = r.u32()
        if r.i32() != 0:
            raise ValueError("AdditionalPackagesToCook is not empty")
        self.asset_registry_offset = r.i32()
        self.bulk_data_start = r.i64()
        self.world_tile_offset = r.i32()
        nchunks = r.i32()
        self.chunk_ids = [r.i32() for _ in range(nchunks)]
        self.preload_count, self.preload_offset = r.i32(), r.i32()
        if r.p != self.name_offset:
            raise ValueError(f"summary ends at {r.p}, but the name map starts at {self.name_offset}")
        self.names = []
        stored = []
        for _ in range(self.name_count):
            n = r.fstr()
            stored.append(r.raw(4))                          # the two 16-bit hashes
            self.names.append(n)
        # retoc's to-legacy leaves every hash at 0 (its to-zen does not read them); keep a package's convention
        self.zero_hashes = all(h == b"\0\0\0\0" for h in stored)
        if r.p != self.import_offset:
            raise ValueError(f"name map ends at {r.p}, but the import map starts at {self.import_offset}")
        # everything from the import map to the end of the header is kept as bytes; only the export map's
        # SerialOffset fields depend on the header size
        self.rest = bytearray(uasset[self.import_offset:self.total_header_size])
        self.uexp = uexp

    # -- names
    def rename(self, mapping: dict[str, str]) -> list[str]:
        """Rename name-map entries; returns the old names that were found."""
        found = []
        for i, n in enumerate(self.names):
            if n in mapping:
                self.names[i] = mapping[n]
                found.append(n)
        if "None" in mapping:
            raise ValueError("cannot rename None")
        return found

    def export_entries(self) -> list[dict]:
        base = self.export_offset - self.import_offset
        out = []
        for i in range(self.export_count):
            o = base + 104 * i
            cls, sup, tmpl, outer, nidx, nnum, flags = struct.unpack_from("<iiiiiiI", self.rest, o)
            size, off = struct.unpack_from("<qq", self.rest, o + 28)
            out.append({"name": self.names[nidx] + (f"_{nnum - 1}" if nnum else ""), "class": cls, "super": sup,
                        "outer": outer, "flags": flags, "size": size, "offset": off})
        return out

    def import_entries(self) -> list[dict]:
        out = []
        for i in range(self.import_count):
            cp, cpn, cn, cnn, outer, on, onn = struct.unpack_from("<iiiiiii", self.rest, 28 * i)
            out.append({"class_package": self.names[cp], "class": self.names[cn], "outer": outer,
                        "name": self.names[on] + (f"_{onn - 1}" if onn else "")})
        return out

    def set_import_name(self, index: int, name: str) -> None:
        """Point import `index` (0-based) at another object name, added to the name map if it is new. Other imports
        and exports that use the old name keep it."""
        if name not in self.names:
            self.names.append(name)
        struct.pack_into("<ii", self.rest, 28 * index + 20, self.names.index(name), 0)   # ObjectName

    def replace_export_data(self, export: dict, data: bytes) -> None:
        """Replace one export's serialized bytes (an entry from export_entries()); later exports move along."""
        start = export["offset"] - self.total_header_size
        old_size = export["size"]
        delta = len(data) - old_size
        self.uexp = self.uexp[:start] + data + self.uexp[start + old_size:]
        base = self.export_offset - self.import_offset
        for i in range(self.export_count):
            o = base + 104 * i
            size, off = struct.unpack_from("<qq", self.rest, o + 28)
            if off == export["offset"]:
                struct.pack_into("<q", self.rest, o + 28, len(data))
            elif off > export["offset"]:
                struct.pack_into("<q", self.rest, o + 36, off + delta)
        if self.bulk_data_start > export["offset"]:
            self.bulk_data_start += delta

    # -- writing
    def _summary(self, offsets: dict) -> bytes:
        s = struct.pack("<Iiiiii", TAG, self.legacy_version, self.ue3_version, self.ue4_version,
                        self.licensee_version, self.custom_count) + self.custom_versions
        s += struct.pack("<i", offsets["total"]) + _fstr(self.folder_name)
        s += struct.pack("<Iii", self.package_flags, len(self.names), offsets["names"])
        s += struct.pack("<ii", self.gatherable_count, offsets["gatherable"])
        s += struct.pack("<ii", self.export_count, offsets["exports"])
        s += struct.pack("<ii", self.import_count, offsets["imports"])
        s += struct.pack("<i", offsets["depends"])
        s += struct.pack("<ii", self.soft_refs_count, offsets["soft_refs"])
        s += struct.pack("<ii", offsets["searchable"], offsets["thumbnails"])
        s += self.guid + struct.pack("<i", len(self.generations))
        for exports, names in self.generations:
            s += struct.pack("<ii", exports, len(self.names) if names == self.name_count else names)
        s += self.saved_by + self.compatible_with
        s += struct.pack("<Ii", self.compression_flags, 0)
        s += struct.pack("<Ii", self.package_source, 0)
        s += struct.pack("<iqi", offsets["asset_registry"], offsets["bulk"], offsets["world_tile"])
        s += struct.pack("<i", len(self.chunk_ids)) + b"".join(struct.pack("<i", c) for c in self.chunk_ids)
        s += struct.pack("<ii", self.preload_count, offsets["preload"])
        return s

    def build(self) -> tuple[bytes, bytes]:
        name_map = b"".join(_fstr(n) + (b"\0\0\0\0" if self.zero_hashes else struct.pack("<HH", *name_hashes(n)))
                            for n in self.names)

        def shifted(v: int, delta: int) -> int:
            return v + delta if v > 0 else v

        # The summary's own size depends on the folder name only; work out the shift in two passes.
        probe = {k: 0 for k in ("total", "names", "gatherable", "exports", "imports", "depends", "soft_refs",
                                "searchable", "thumbnails", "asset_registry", "bulk", "world_tile", "preload")}
        summary_size = len(self._summary(probe))
        new_import_offset = summary_size + len(name_map)
        delta = new_import_offset - self.import_offset
        offsets = {
            "names": summary_size,
            "imports": new_import_offset,
            "exports": self.export_offset + delta,
            "depends": self.depends_offset + delta,
            "gatherable": shifted(self.gatherable_offset, delta),
            "soft_refs": shifted(self.soft_refs_offset, delta),
            "searchable": shifted(self.searchable_names_offset, delta),
            "thumbnails": shifted(self.thumbnail_offset, delta),
            "asset_registry": shifted(self.asset_registry_offset, delta),
            "world_tile": shifted(self.world_tile_offset, delta),
            "preload": shifted(self.preload_offset, delta),
            "total": self.total_header_size + delta,
            "bulk": self.bulk_data_start + delta,
        }
        rest = bytearray(self.rest)
        base = self.export_offset - self.import_offset
        for i in range(self.export_count):
            o = base + 104 * i + 36                           # SerialOffset
            off, = struct.unpack_from("<q", rest, o)
            struct.pack_into("<q", rest, o, off + delta)
        summary = self._summary(offsets)
        assert len(summary) == summary_size
        uasset = summary + name_map + bytes(rest)
        assert len(uasset) == offsets["total"], (len(uasset), offsets["total"])
        return uasset, self.uexp


def iter_tags(data: bytes, names: list[str], p: int = 0):
    """Yield (name, type, struct name or None, value offset, value size) for each property tag of a tagged property
    list starting at p, up to its None. FPropertyTag (4.27): FName Name, FName Type, int32 Size, int32 ArrayIndex,
    type extras (StructProperty: FName StructName + FGuid; BoolProperty: uint8; Byte/Enum/Array/SetProperty: FName;
    MapProperty: two FNames), uint8 HasPropertyGuid (+ FGuid), then Size bytes of value. A BoolProperty keeps its
    value in the tag itself (its Size is 0): for it the offset is that uint8 and the size 1."""
    while True:
        name = names[struct.unpack_from("<i", data, p)[0]]
        if name == "None":
            return
        ptype = names[struct.unpack_from("<i", data, p + 8)[0]]
        size, = struct.unpack_from("<i", data, p + 16)
        q = p + 24
        struct_name = None
        if ptype == "StructProperty":
            struct_name = names[struct.unpack_from("<i", data, q)[0]]
            q += 8 + 16
        elif ptype == "BoolProperty":
            q += 1
        elif ptype in ("ByteProperty", "EnumProperty", "ArrayProperty", "SetProperty"):
            q += 8
        elif ptype == "MapProperty":
            q += 16
        q += 1 + (16 if data[q] else 0)
        if ptype == "BoolProperty":
            yield name, ptype, struct_name, p + 24, 1
        else:
            yield name, ptype, struct_name, q, size
        p = q + size


def load(path_without_ext: str) -> LegacyPackage:
    with open(path_without_ext + ".uasset", "rb") as a, open(path_without_ext + ".uexp", "rb") as e:
        return LegacyPackage(a.read(), e.read())
