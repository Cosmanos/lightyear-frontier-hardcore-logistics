"""Grow a UE 4.27 zen package: add names to its name map and insert bytes into its export data.

Used to add new entries to maps such as a delivery's `Cost`. The package header is rebuilt around the larger
name map (header offsets shift by a multiple of 8, so alignment is kept), new names get the hash the engine
expects (CityHash64 of the lowercase name), and the export's serial size is updated.
"""
from __future__ import annotations

import struct

from uasset import MapNode, ZenPackage

NAME_HASH_VERSION = 0xC1640000
_MASK = 0xFFFFFFFFFFFFFFFF
_K0, _K1, _K2 = 0xC3A5C85C97CB3127, 0xB492B66FBE98F273, 0x9AE16A3B2F90404F


# ---------------------------------------------------------------- CityHash64 (v1.1, as used by UE)

def _f64(s, i): return int.from_bytes(s[i:i + 8], "little")
def _f32(s, i): return int.from_bytes(s[i:i + 4], "little")
def _rot(v, r): return v if r == 0 else ((v >> r) | (v << (64 - r))) & _MASK
def _smix(v): return v ^ (v >> 47)
def _bswap(v): return int.from_bytes(v.to_bytes(8, "little"), "big")


def _h16(u, v, mul=0x9DDFEA08EB382D69):
    a = ((u ^ v) * mul) & _MASK
    a ^= a >> 47
    b = ((v ^ a) * mul) & _MASK
    b ^= b >> 47
    return (b * mul) & _MASK


def _len0to16(s):
    n = len(s)
    if n >= 8:
        mul = (_K2 + n * 2) & _MASK
        a = (_f64(s, 0) + _K2) & _MASK
        b = _f64(s, n - 8)
        return _h16((_rot(b, 37) * mul + a) & _MASK, ((_rot(a, 25) + b) * mul) & _MASK, mul)
    if n >= 4:
        mul = (_K2 + n * 2) & _MASK
        return _h16((n + (_f32(s, 0) << 3)) & _MASK, _f32(s, n - 4), mul)
    if n:
        y = (s[0] + (s[n >> 1] << 8)) & 0xFFFFFFFF
        z = (n + (s[n - 1] << 2)) & 0xFFFFFFFF
        return (_smix(((y * _K2) ^ (z * _K0)) & _MASK) * _K2) & _MASK
    return _K2


def _len17to32(s):
    n = len(s)
    mul = (_K2 + n * 2) & _MASK
    a = (_f64(s, 0) * _K1) & _MASK
    b = _f64(s, 8)
    c = (_f64(s, n - 8) * mul) & _MASK
    d = (_f64(s, n - 16) * _K2) & _MASK
    return _h16((_rot((a + b) & _MASK, 43) + _rot(c, 30) + d) & _MASK, (a + _rot((b + _K2) & _MASK, 18) + c) & _MASK, mul)


def _len33to64(s):
    n = len(s)
    mul = (_K2 + n * 2) & _MASK
    a = (_f64(s, 0) * _K2) & _MASK
    b, c, d = _f64(s, 8), _f64(s, n - 24), _f64(s, n - 32)
    e, f = (_f64(s, 16) * _K2) & _MASK, (_f64(s, 24) * 9) & _MASK
    g, h = _f64(s, n - 8), (_f64(s, n - 16) * mul) & _MASK
    u = (_rot((a + g) & _MASK, 43) + (_rot(b, 30) + c) * 9) & _MASK
    v = ((((a + g) & _MASK) ^ d) + f + 1) & _MASK
    w = (_bswap(((u + v) * mul) & _MASK) + h) & _MASK
    x = (_rot((e + f) & _MASK, 42) + c) & _MASK
    y = ((_bswap(((v + w) * mul) & _MASK) + g) * mul) & _MASK
    z = (e + f + c) & _MASK
    a = (_bswap(((x + z) * mul + y) & _MASK) + b) & _MASK
    b = (_smix(((z + a) * mul + d + h) & _MASK) * mul) & _MASK
    return (b + x) & _MASK


def _weak(s, i, a, b):
    w, x, y, z = _f64(s, i), _f64(s, i + 8), _f64(s, i + 16), _f64(s, i + 24)
    a = (a + w) & _MASK
    b = _rot((b + a + z) & _MASK, 21)
    c = a
    a = (a + x + y) & _MASK
    b = (b + _rot(a, 44)) & _MASK
    return (a + z) & _MASK, (b + c) & _MASK


def cityhash64(s: bytes) -> int:
    n = len(s)
    if n <= 16:
        return _len0to16(s)
    if n <= 32:
        return _len17to32(s)
    if n <= 64:
        return _len33to64(s)
    x = _f64(s, n - 40)
    y = (_f64(s, n - 16) + _f64(s, n - 56)) & _MASK
    z = _h16((_f64(s, n - 48) + n) & _MASK, _f64(s, n - 24))
    v = _weak(s, n - 64, n, z)
    w = _weak(s, n - 32, (y + _K1) & _MASK, x)
    x = (x * _K1 + _f64(s, 0)) & _MASK
    left, i = (n - 1) & ~63, 0
    while True:
        x = (_rot((x + y + v[0] + _f64(s, i + 8)) & _MASK, 37) * _K1) & _MASK
        y = (_rot((y + v[1] + _f64(s, i + 48)) & _MASK, 42) * _K1) & _MASK
        x ^= w[1]
        y = (y + v[0] + _f64(s, i + 40)) & _MASK
        z = (_rot((z + w[0]) & _MASK, 33) * _K1) & _MASK
        v = _weak(s, i, (v[1] * _K1) & _MASK, (x + w[0]) & _MASK)
        w = _weak(s, i + 32, (z + w[1]) & _MASK, (y + _f64(s, i + 16)) & _MASK)
        z, x = x, z
        i += 64
        left -= 64
        if left == 0:
            break
    return _h16((_h16(v[0], w[0]) + _smix(y) * _K1 + z) & _MASK, (_h16(v[1], w[1]) + x) & _MASK)


def name_hash(name: str) -> int:
    if name.isascii():
        return cityhash64(name.lower().encode("ascii"))
    return cityhash64(name.lower().encode("utf-16-le"))


def _encode_name(name: str) -> bytes:
    if name.isascii():
        raw = name.encode("ascii")
        return bytes([(len(raw) >> 8) & 0x7F, len(raw) & 0xFF]) + raw
    raw = name.encode("utf-16-le")
    n = len(raw) // 2
    return bytes([0x80 | ((n >> 8) & 0x7F), n & 0xFF]) + raw


# ---------------------------------------------------------------- package editing

class PackageEditor:
    """Collects map-entry insertions on top of an (already number-patched) single-export package."""

    def __init__(self, data: bytes | bytearray):
        self.buf = bytearray(data)
        self.pkg = ZenPackage(bytes(data))
        self.names = list(self.pkg.names)
        self._index = {n: i for i, n in enumerate(self.names)}
        self.inserts: list[tuple[int, bytes]] = []
        f = struct.unpack_from("<IIIIIIiiiiiiiiii", self.buf, 0)
        (self.nm_off, self.nm_size, self.nh_off, self.nh_size, self.imp_off, self.exp_off,
         self.eb_off, self.gd_off, self.gd_size) = f[6], f[7], f[8], f[9], f[10], f[11], f[12], f[13], f[14]
        if self.nm_off != 64 or self.imp_off != self.nh_off + self.nh_size or len(self.pkg.exports) != 1:
            raise ValueError("unexpected package layout; refusing to edit")
        stored = struct.unpack_from(f"<{len(self.names) + 1}Q", self.buf, self.nh_off)
        if stored[0] != NAME_HASH_VERSION or list(stored[1:]) != [name_hash(n) for n in self.names]:
            raise ValueError("name hashes do not match CityHash64(lowercase); refusing to add names")

    def name_ref(self, name: str) -> bytes:
        if name not in self._index:
            self._index[name] = len(self.names)
            self.names.append(name)
        return struct.pack("<II", self._index[name], 0)

    def add_map_entry(self, node: MapNode, key: str, value) -> None:
        if node.key_type not in ("NameProperty", "EnumProperty"):
            raise TypeError(f"can only add entries to maps keyed by names, not {node.key_type}")
        fmt = {"IntProperty": "<i", "FloatProperty": "<f", "Int64Property": "<q"}.get(node.value_type)
        if fmt is None:
            raise TypeError(f"can only add number values, not {node.value_type}")
        entry = self.name_ref(key) + struct.pack(fmt, value)
        self.inserts.append((node.end_offset, entry))
        for off, delta in ((node.size_offset, len(entry)), (node.count_offset, 1)):
            struct.pack_into("<i", self.buf, off, struct.unpack_from("<i", self.buf, off)[0] + delta)

    def build(self) -> bytes:
        names_blob = b"".join(_encode_name(n) for n in self.names)
        hashes = struct.pack("<Q", NAME_HASH_VERSION) + b"".join(struct.pack("<Q", name_hash(n)) for n in self.names)
        nh_off = 64 + len(names_blob) + (-(64 + len(names_blob)) % 8)
        imp_off = nh_off + len(hashes)
        delta = imp_off - self.imp_off
        header_end = self.gd_off + self.gd_size
        out = bytearray(self.buf[:64])
        struct.pack_into("<iiii", out, 24, 64, len(names_blob), nh_off, len(hashes))
        struct.pack_into("<iiii", out, 40, imp_off, self.exp_off + delta, self.eb_off + delta, self.gd_off + delta)
        out += names_blob
        out += b"\0" * (nh_off - len(out))
        out += hashes
        out += self.buf[self.imp_off:header_end]
        body = bytes(self.buf[header_end:])
        grown = bytearray()
        last = 0
        for off, data in sorted(self.inserts, key=lambda t: t[0]):
            rel = off - header_end
            grown += body[last:rel] + data
            last = rel
        grown += body[last:]
        added = len(grown) - len(body)
        size_pos = self.exp_off + delta + 8                      # export 0: CookedSerialSize
        struct.pack_into("<Q", out, size_pos, struct.unpack_from("<Q", out, size_pos)[0] + added)
        return bytes(out + grown)
