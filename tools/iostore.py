"""Read Lightyear Frontier's IoStore containers and write small mod containers.

The game is Unreal Engine 4.27: assets live in IoStore containers (.utoc table of contents + .ucas data),
each paired with a .pak file. The game's containers are Oodle-compressed but not encrypted or signed.

Mod containers are written in the same layout retoc produces (the tool the Nexus mods for this game use):
uncompressed 64 KiB blocks, one chunk per package aligned to a block boundary, a directory index, a
container header chunk, and a stub .pak with an empty index. Install them as
FarMech/Content/Paks/~mods/<Name>_P.{pak,utoc,ucas}; the _P suffix makes them override the base game.
"""
from __future__ import annotations

import ctypes
import glob
import hashlib
import os
import struct
from dataclasses import dataclass, field

DEFAULT_GAME_DIR = r"C:\Program Files (x86)\Steam\steamapps\common\Lightyear Frontier"
OODLE_GLOBS = [
    r"D:\UE_*\Engine\Binaries\DotNET\AutomationTool\oo2core_9_win64.dll",
    r"C:\Program Files\Epic Games\UE_*\Engine\Binaries\DotNET\AutomationTool\oo2core_9_win64.dll",
    r"D:\Epic Games\UE_*\Engine\Binaries\DotNET\AutomationTool\oo2core_9_win64.dll",
]

TOC_MAGIC = b"-==--==--==--==-"
TOC_VERSION = 3                # UE 4.27 ("PartitionSize")
BLOCK_SIZE = 64 * 1024         # what retoc writes for mods
FLAG_INDEXED = 0x08
FLAG_ENCRYPTED = 0x02
CHUNK_EXPORT_BUNDLE_DATA = 2
CHUNK_CONTAINER_HEADER = 10
NAME_HASH_VERSION = 0xC1640000
MOUNT_POINT = "../../../"
NONE32 = 0xFFFFFFFF


def game_dir() -> str:
    return os.environ.get("LF_GAME_DIR", DEFAULT_GAME_DIR)


def paks_dir() -> str:
    return os.path.join(game_dir(), "FarMech", "Content", "Paks")


# ---------------------------------------------------------------- Oodle (read side only)

_oodle_fn = None


def _oodle():
    global _oodle_fn
    if _oodle_fn is None:
        path = os.environ.get("LF_OODLE_DLL")
        if not path:
            for pattern in OODLE_GLOBS:
                hits = sorted(glob.glob(pattern))
                if hits:
                    path = hits[-1]
                    break
        if not path or not os.path.exists(path):
            raise RuntimeError("oo2core_9_win64.dll not found. It ships with Unreal Engine under "
                               r"Engine\Binaries\DotNET\AutomationTool; set LF_OODLE_DLL to its full path.")
        fn = ctypes.CDLL(path).OodleLZ_Decompress
        fn.restype = ctypes.c_ssize_t
        fn.argtypes = [ctypes.c_void_p, ctypes.c_ssize_t, ctypes.c_void_p, ctypes.c_ssize_t,
                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_ssize_t,
                       ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ssize_t, ctypes.c_int]
        _oodle_fn = fn
    return _oodle_fn


def oodle_decompress(src: bytes, raw_len: int) -> bytes:
    out = ctypes.create_string_buffer(raw_len)
    n = _oodle()(src, len(src), out, raw_len, 1, 0, 0, None, 0, None, None, None, 0, 3)
    if n != raw_len:
        raise RuntimeError(f"Oodle decompression failed ({n} of {raw_len} bytes)")
    return out.raw


# ---------------------------------------------------------------- small helpers

def read_fstring(d: bytes, p: int) -> tuple[str, int]:
    n, = struct.unpack_from("<i", d, p)
    p += 4
    if n == 0:
        return "", p
    if n > 0:
        return d[p:p + n - 1].decode("latin-1"), p + n
    return d[p:p - 2 * n - 2].decode("utf-16-le"), p - 2 * n


def fstring(s: str) -> bytes:
    raw = s.encode("ascii") + b"\0"
    return struct.pack("<i", len(raw)) + raw


def sha1(b: bytes) -> bytes:
    return hashlib.sha1(b).digest()


# ---------------------------------------------------------------- container header

@dataclass
class StoreEntry:
    """FPackageStoreEntry (UE 4.27): 32 bytes plus the list of imported package ids."""
    bundles_size: int
    export_count: int
    bundle_count: int
    load_order: int
    imports: list[int] = field(default_factory=list)


@dataclass
class ContainerHeader:
    container_id: int
    package_ids: list[int]
    entries: dict[int, StoreEntry]
    redirects: list[tuple[int, int]]

    @staticmethod
    def parse(blob: bytes) -> "ContainerHeader":
        p = 0
        cid, count = struct.unpack_from("<QI", blob, p); p += 12
        n, = struct.unpack_from("<i", blob, p); p += 4 + n            # Names (unused here)
        n, = struct.unpack_from("<i", blob, p); p += 4 + n            # NameHashes
        n, = struct.unpack_from("<i", blob, p); p += 4
        ids = list(struct.unpack_from(f"<{n}Q", blob, p)); p += 8 * n
        n, = struct.unpack_from("<i", blob, p); p += 4
        store = blob[p:p + n]; p += n
        entries = {}
        for i in range(count):
            bsize, exp, bund, order, _pad, inum, ioff = struct.unpack_from("<QiiIIII", store, 32 * i)
            imports = list(struct.unpack_from(f"<{inum}Q", store, 32 * i + 24 + ioff)) if inum else []
            entries[ids[i]] = StoreEntry(bsize, exp, bund, order, imports)
        culture, = struct.unpack_from("<i", blob, p); p += 4
        if culture:
            raise ValueError("culture package maps are not supported")
        n, = struct.unpack_from("<i", blob, p); p += 4
        redirects = [struct.unpack_from("<QQ", blob, p + 16 * i) for i in range(n)]
        return ContainerHeader(cid, ids, entries, redirects)

    def build(self) -> bytes:
        entries = bytearray()
        imports = bytearray()
        count = len(self.package_ids)
        for i, pid in enumerate(self.package_ids):
            e = self.entries[pid]
            import_pos = 32 * count + len(imports)          # absolute offset inside StoreEntries
            rel = (import_pos - (32 * i + 24)) if e.imports else 0
            entries += struct.pack("<QiiIIII", e.bundles_size, e.export_count, e.bundle_count, e.load_order, 0,
                                   len(e.imports), rel)
            imports += b"".join(struct.pack("<Q", x) for x in e.imports)
        store = bytes(entries + imports)
        out = bytearray()
        out += struct.pack("<QI", self.container_id, count)
        out += struct.pack("<i", 0)                                     # Names: none
        out += struct.pack("<iQ", 8, NAME_HASH_VERSION)                 # NameHashes: just the algorithm version
        out += struct.pack("<i", count) + b"".join(struct.pack("<Q", x) for x in self.package_ids)
        out += struct.pack("<i", len(store)) + store
        out += struct.pack("<i", 0)                                     # CulturePackageMap: empty
        out += struct.pack("<i", len(self.redirects)) + b"".join(struct.pack("<QQ", a, b) for a, b in self.redirects)
        out += b"\0" * (-len(out) % 16)                                 # retoc pads the chunk to 16 bytes
        return bytes(out)


# ---------------------------------------------------------------- reading

class IoStoreContainer:
    """A .utoc/.ucas pair. Files are addressed like 'FarMech/Content/DataTables/DT_Modules.uasset'."""

    def __init__(self, utoc_path: str):
        d = open(utoc_path, "rb").read()
        if d[:16] != TOC_MAGIC:
            raise ValueError(f"not an IoStore table of contents: {utoc_path}")
        self.version = d[16]
        n, nblocks = struct.unpack_from("<II", d, 24)
        method_count, method_len, self.block_size, dir_size = struct.unpack_from("<IIII", d, 36)
        self.container_id, = struct.unpack_from("<Q", d, 56)
        if d[80] & FLAG_ENCRYPTED:
            raise ValueError("encrypted containers are not supported")
        p = 144
        self.chunk_ids = [d[p + 12 * i:p + 12 * i + 12] for i in range(n)]
        p += 12 * n
        self.offsets = [(int.from_bytes(d[p + 10 * i:p + 10 * i + 5], "big"),
                         int.from_bytes(d[p + 10 * i + 5:p + 10 * i + 10], "big")) for i in range(n)]
        p += 10 * n
        self.blocks = []
        for i in range(nblocks):
            b = d[p + 12 * i:p + 12 * i + 12]
            self.blocks.append((int.from_bytes(b[0:5], "little"), int.from_bytes(b[5:8], "little"),
                                int.from_bytes(b[8:11], "little"), b[11]))
        p += 12 * nblocks
        self.methods = [None] + [d[p + i * method_len:p + (i + 1) * method_len].split(b"\0")[0].decode()
                                 for i in range(method_count)]
        p += method_count * method_len
        self.files = _read_directory_index(d, p) if dir_size else {}
        self._ucas = open(utoc_path[:-5] + ".ucas", "rb")

    def read_chunk(self, index: int) -> bytes:
        off, length = self.offsets[index]
        first, last = off // self.block_size, (off + length - 1) // self.block_size
        out = bytearray()
        for bi in range(first, last + 1):
            boff, csize, usize, method = self.blocks[bi]
            self._ucas.seek(boff)
            raw = self._ucas.read(csize)
            if method == 0:
                out += raw[:usize]
            elif self.methods[method] == "Oodle":
                out += oodle_decompress(raw, usize)
            else:
                raise ValueError(f"unsupported compression method {self.methods[method]}")
        start = off - first * self.block_size
        return bytes(out[start:start + length])

    def read_file(self, path: str) -> bytes:
        return self.read_chunk(self.files[path])

    def chunk_id(self, path: str) -> bytes:
        return self.chunk_ids[self.files[path]]

    def header(self) -> ContainerHeader:
        for i, cid in enumerate(self.chunk_ids):
            if cid[11] == CHUNK_CONTAINER_HEADER:
                return ContainerHeader.parse(self.read_chunk(i))
        raise ValueError("container has no header chunk")


def _read_directory_index(d: bytes, p: int) -> dict[str, int]:
    mount, p = read_fstring(d, p)
    n, = struct.unpack_from("<I", d, p); p += 4
    dirs = [struct.unpack_from("<4I", d, p + 16 * i) for i in range(n)]; p += 16 * n
    n, = struct.unpack_from("<I", d, p); p += 4
    files = [struct.unpack_from("<3I", d, p + 12 * i) for i in range(n)]; p += 12 * n
    n, = struct.unpack_from("<I", d, p); p += 4
    strings = []
    for _ in range(n):
        s, p = read_fstring(d, p)
        strings.append(s)
    out: dict[str, int] = {}
    stack = [(0, mount)]
    while stack:
        di, parent = stack.pop()
        name, child, sibling, first_file = dirs[di]
        here = parent + (strings[name] + "/" if name != NONE32 else "")
        fi = first_file
        while fi != NONE32:
            fname, nxt, toc_index = files[fi]
            out[(here + strings[fname]).replace(MOUNT_POINT, "", 1)] = toc_index
            fi = nxt
        if sibling != NONE32:
            stack.append((sibling, parent))
        if child != NONE32:
            stack.append((child, here))
    return out


def open_game_container() -> IoStoreContainer:
    return IoStoreContainer(os.path.join(paks_dir(), "FarMech-WindowsNoEditor.utoc"))


# ---------------------------------------------------------------- writing

def _directory_index(paths: list[str]) -> bytes:
    """FIoDirectoryIndexResource for files given as 'FarMech/Content/.../X.uasset' (user data = TOC index)."""
    strings: list[str] = []
    string_ids: dict[str, int] = {}

    def sid(s: str) -> int:
        if s not in string_ids:
            string_ids[s] = len(strings)
            strings.append(s)
        return string_ids[s]

    dirs = [[NONE32, NONE32, NONE32, NONE32]]      # name, first child, next sibling, first file
    files: list[list[int]] = []                    # name, next file, user data
    for toc_index, path in enumerate(paths):
        *folders, fname = path.split("/")
        cur = 0
        for folder in folders:
            name = sid(folder)
            child, last = dirs[cur][1], NONE32
            while child != NONE32 and dirs[child][0] != name:
                last, child = child, dirs[child][2]
            if child == NONE32:
                dirs.append([name, NONE32, NONE32, NONE32])
                child = len(dirs) - 1
                if last == NONE32:
                    dirs[cur][1] = child
                else:
                    dirs[last][2] = child
            cur = child
        files.append([sid(fname), NONE32, toc_index])
        new = len(files) - 1
        if dirs[cur][3] == NONE32:
            dirs[cur][3] = new
        else:
            f = dirs[cur][3]
            while files[f][1] != NONE32:
                f = files[f][1]
            files[f][1] = new
    out = bytearray(fstring(MOUNT_POINT))
    out += struct.pack("<I", len(dirs)) + b"".join(struct.pack("<4I", *e) for e in dirs)
    out += struct.pack("<I", len(files)) + b"".join(struct.pack("<3I", *e) for e in files)
    out += struct.pack("<I", len(strings)) + b"".join(fstring(s) for s in strings)
    return bytes(out)


def stub_pak() -> bytes:
    """The empty v11 .pak that accompanies an IoStore container (byte-identical to retoc's)."""
    path_hash_index = b"\0" * 8      # empty path-hash map + empty pruned directory map
    full_dir_index = b"\0" * 4       # empty directory map
    primary_len = 14 + 4 + 8 + 4 + 36 + 4 + 36 + 4 + 4
    primary = (fstring(MOUNT_POINT) + struct.pack("<iQ", 0, 0)
               + struct.pack("<Iqq", 1, primary_len, len(path_hash_index)) + sha1(path_hash_index)
               + struct.pack("<Iqq", 1, primary_len + len(path_hash_index), len(full_dir_index)) + sha1(full_dir_index)
               + struct.pack("<ii", 0, 0))
    assert len(primary) == primary_len
    footer = (b"\0" * 16 + b"\0" + struct.pack("<Iiqq", 0x5A6F12E1, 11, 0, len(primary))
              + sha1(primary) + b"\0" * 160)
    return primary + path_hash_index + full_dir_index + footer


def container_id_for(name: str) -> int:
    cid = int.from_bytes(sha1(name.lower().encode("utf-16-le"))[:8], "little")
    return cid if cid != 0xFFFFFFFFFFFFFFFF else cid - 1


@dataclass
class ModFile:
    path: str            # e.g. FarMech/Content/DataTables/DT_Modules.uasset
    chunk_id: bytes      # 12-byte FIoChunkId, copied from the game's container
    data: bytes
    entry: StoreEntry    # package store entry, copied from the game's container header


def write_mod_container(out_dir: str, name: str, files: list[ModFile]) -> list[str]:
    """Write <name>.utoc/.ucas/.pak (name should end in _P). Returns the written paths."""
    cid = container_id_for(name)
    package_ids = [struct.unpack_from("<Q", f.chunk_id)[0] for f in files]
    header = ContainerHeader(cid, package_ids, {pid: f.entry for pid, f in zip(package_ids, files)},
                             [(pid, pid) for pid in package_ids]).build()
    chunks = [(f.chunk_id, f.data) for f in files] + [(struct.pack("<QHBB", cid, 0, 0, CHUNK_CONTAINER_HEADER), header)]

    ucas = bytearray()
    blocks, offsets, metas = [], [], []
    virtual = 0
    for chunk_id, data in chunks:
        offsets.append((virtual, len(data)))
        for i in range(0, len(data), BLOCK_SIZE):
            piece = data[i:i + BLOCK_SIZE]
            blocks.append((len(ucas), len(piece), len(piece)))
            ucas += piece
        virtual += -(-len(data) // BLOCK_SIZE) * BLOCK_SIZE
        metas.append(sha1(data) + b"\0" * 12 + b"\0")
    dir_index = _directory_index([f.path for f in files])

    toc = bytearray(TOC_MAGIC)
    toc += struct.pack("<BBH", TOC_VERSION, 0, 0)
    toc += struct.pack("<9I", 144, len(chunks), len(blocks), 12, 0, 32, BLOCK_SIZE, len(dir_index), 1)
    toc += struct.pack("<Q", cid) + b"\0" * 16
    toc += struct.pack("<BBHI", FLAG_INDEXED, 0, 0, 0)
    toc += struct.pack("<Q", 0xFFFFFFFFFFFFFFFF) + b"\0" * 48
    assert len(toc) == 144
    toc += b"".join(c for c, _ in chunks)
    toc += b"".join(o.to_bytes(5, "big") + n.to_bytes(5, "big") for o, n in offsets)
    toc += b"".join(o.to_bytes(5, "little") + c.to_bytes(3, "little") + u.to_bytes(3, "little") + b"\0"
                    for o, c, u in blocks)
    toc += dir_index
    toc += b"".join(metas)

    os.makedirs(out_dir, exist_ok=True)
    written = []
    for ext, blob in ((".utoc", toc), (".ucas", ucas), (".pak", stub_pak())):
        path = os.path.join(out_dir, name + ext)
        with open(path, "wb") as fh:
            fh.write(blob)
        written.append(path)
    return written
