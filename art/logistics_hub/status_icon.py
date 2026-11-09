"""Draw the Logistics Hub's focus-panel status icon: art/logistics_hub/T_HubIcon.png.

    python art/logistics_hub/status_icon.py

The game's status-line icons are flat glyphs in one golden yellow on a transparent background (its EnergyIconCOLOR:
sRGB about 255, 186, 8, soft anti-aliased edges, no outline, about two thirds of the square). This one is the hub's
logo, a drone carrying a crate: two rotors on arms, the drone's body, a tether, and a crate with its lid and a latch.
128 x 128 like the game's T_WaterIcon (the icon this one replaces), drawn at 8 x and averaged down for smooth edges.
Plain Python, no Blender; tools/cook_art.py cooks the PNG to /Game/HardcoreLogistics/Art/T_HubIcon.
"""
import os
import struct
import zlib

SIZE, SS = 128, 8                       # output size, supersampling per axis
COLOR = (255, 184, 8)                   # sRGB, like the game's coloured status icons
# filled shapes in icon units (0..1, y down): x0, y0, x1, y1, corner radius
SHAPES = [
    (0.13, 0.13, 0.43, 0.19, 0.03),     # left rotor
    (0.57, 0.13, 0.87, 0.19, 0.03),     # right rotor
    (0.255, 0.17, 0.31, 0.265, 0.0),    # left arm
    (0.69, 0.17, 0.745, 0.265, 0.0),    # right arm
    (0.24, 0.25, 0.76, 0.335, 0.035),   # drone body
    (0.465, 0.32, 0.535, 0.44, 0.0),    # tether
    (0.20, 0.43, 0.80, 0.545, 0.03),    # crate lid
    (0.20, 0.595, 0.80, 0.87, 0.035),   # crate body
]
CUTOUTS = [
    (0.455, 0.595, 0.545, 0.675, 0.015),  # the latch, cut into the crate body's top edge
]


def inside(px: float, py: float, shape) -> bool:
    x0, y0, x1, y1, r = shape
    if not (x0 <= px <= x1 and y0 <= py <= y1):
        return False
    cx = min(max(px, x0 + r), x1 - r)
    cy = min(max(py, y0 + r), y1 - r)
    return (px - cx) ** 2 + (py - cy) ** 2 <= r * r + 1e-12


def coverage() -> list:
    """SIZE x SIZE alpha (0..1): the share of each pixel's SS x SS samples inside a shape and outside every cutout."""
    n = SIZE * SS
    alpha = [0.0] * (SIZE * SIZE)
    step = 1.0 / n
    for sy in range(n):
        py = (sy + 0.5) * step
        row = (sy // SS) * SIZE
        for shape in SHAPES:
            if not (shape[1] <= py <= shape[3]):
                continue
            for sx in range(int(shape[0] * n), min(n, int(shape[2] * n) + 1)):
                px = (sx + 0.5) * step
                if inside(px, py, shape) and not any(inside(px, py, c) for c in CUTOUTS) \
                        and not any(inside(px, py, s) for s in SHAPES[:SHAPES.index(shape)]):
                    alpha[row + sx // SS] += 1.0 / (SS * SS)
    return alpha


def write_png(path: str, w: int, h: int, rgba: bytes) -> None:
    raw = b"".join(b"\0" + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                 + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def main() -> str:
    alpha = coverage()
    rgba = bytearray()
    for a in alpha:
        rgba += bytes((*COLOR, int(round(min(a, 1.0) * 255))))
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "T_HubIcon.png")
    write_png(path, SIZE, SIZE, bytes(rgba))
    print(f"wrote {path} ({sum(1 for a in alpha if a > 0.5)} solid pixels of {SIZE * SIZE})")
    return path


if __name__ == "__main__":
    main()
