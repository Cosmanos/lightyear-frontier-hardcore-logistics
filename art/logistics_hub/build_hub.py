"""Build the Logistics Hub model in Blender (run inside Blender, e.g. through the Blender MCP):

    exec(compile(open(r"<repo>/art/logistics_hub/build_hub.py").read(), "build_hub.py", "exec"), {})

Rebuilds collection LogisticsHub (the parts) and the UBX_ boxes in collection Collision from scratch, then
art/export_model.py exports them. Version 3 (0.13.0):
  - after the concept art "Logistics Station": a metal platform with cyan corner lights, a blue hut with orange
    bands, a framed screen with a glowing drone-and-crate icon under an orange awning, a two-tier roof with the
    orange logo sign, vents and a corner beacon, a lattice tower with a white dish and an orange beacon, an open
    canopy over shelved wooden crates (the game's own crate style: dark frame, planks, a diagonal brace, bolts), and
    blue pipes with orange couplings beside a cyan indicator;
  - no two parts share a face plane where they overlap (export_model.py refuses those: they flicker in the game);
  - a plinth under the platform, 1 m below the ground, fills the gap on slopes (the Water Reservoir template's own
    foundation mesh is switched off).
3.9 x 3.9 m, 6.8 m tall above the ground, front towards -Y, origin at the bottom centre (the template places by the
model's own collision boxes). Materials: flat Principled BSDF colours plus two custom properties for the texture bake
in export_model.py: hl_kind (paint, metal, wood, glow, screen) and hl_wear (how much the paint is chipped, 0..1);
emission marks what glows in the game.
"""
import math

import bmesh
import bpy
from mathutils import Euler, Vector

PARTS = "LogisticsHub"
COLLISION = "Collision"
MODEL = "SM_LogisticsHub"


def collection(name):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


parts = collection(PARTS)
coll = collection(COLLISION)
for o in list(parts.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for o in list(coll.objects):
    if o.name.startswith("UBX_"):
        bpy.data.objects.remove(o, do_unlink=True)
for me in list(bpy.data.meshes):
    if me.users == 0:
        bpy.data.meshes.remove(me)


def material(name, base, rough, metal, emit=(0.0, 0.0, 0.0), strength=0.0, kind="paint", wear=1.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*base, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Emission Color"].default_value = (*emit, 1.0)
    b.inputs["Emission Strength"].default_value = strength
    m["hl_kind"] = kind
    m["hl_wear"] = wear
    return m


BLUE = material("HL_Blue", (0.035, 0.16, 0.45), 0.5, 0.2, wear=1.0)
BLUE_DARK = material("HL_BlueDark", (0.012, 0.05, 0.15), 0.5, 0.2, wear=0.8)
ORANGE = material("HL_Orange", (0.78, 0.30, 0.025), 0.5, 0.15, wear=0.9)
SLATE = material("HL_Slate", (0.035, 0.04, 0.055), 0.55, 0.3, wear=1.0)
PLATE = material("HL_Plate", (0.11, 0.09, 0.075), 0.65, 0.6, kind="metal")
STEEL = material("HL_Steel", (0.45, 0.47, 0.50), 0.35, 0.85, kind="metal")
BOLT = material("HL_Bolt", (0.06, 0.06, 0.065), 0.45, 0.8, kind="metal")
WHITE = material("HL_White", (0.72, 0.73, 0.74), 0.45, 0.05, wear=0.5)
WOOD = material("HL_Wood", (0.16, 0.085, 0.045), 0.75, 0.0, kind="wood")
WOOD_DARK = material("HL_WoodDark", (0.07, 0.04, 0.024), 0.8, 0.0, kind="wood")
SCREEN = material("HL_Screen", (0.005, 0.02, 0.028), 0.15, 0.0, (0.0, 0.05, 0.07), 1.0, kind="screen")
CYAN = material("HL_Cyan", (0.08, 0.75, 0.90), 0.3, 0.0, (0.12, 0.85, 1.0), 1.0, kind="glow")
BEACON = material("HL_Beacon", (1.0, 0.5, 0.08), 0.35, 0.0, (1.0, 0.42, 0.04), 1.0, kind="glow")


def _obj(name, bm, mat, loc=(0, 0, 0), rot=None, target=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    o.location = loc
    if rot is not None:
        o.rotation_euler = Euler(rot)
    if mat is not None:
        me.materials.append(mat)
    (target or parts).objects.link(o)
    return o


def bevel(o, width, segments=2):
    mod = o.modifiers.new("Bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(30)
    return o


def box(name, size, loc, mat, bev=0.0, rot=None, target=None):
    """A box of the given full size centred on loc (rotation in radians, XYZ Euler)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    o = _obj(name, bm, mat, loc, rot, target)
    return bevel(o, bev) if bev > 0 else o


def span(name, lo, hi, mat, bev=0.0):
    """A box from corner lo to corner hi."""
    lo, hi = Vector(lo), Vector(hi)
    return box(name, tuple(hi - lo), tuple((lo + hi) / 2), mat, bev)


def cyl(name, r, h, loc, mat, axis=(0, 0, 1), seg=16, bev=0.0):
    """A cylinder of radius r and length h centred on loc, along axis."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r, radius2=r, depth=h)
    o = _obj(name, bm, mat, loc)
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = Vector(axis).normalized().to_track_quat("Z", "Y")
    return bevel(o, bev) if bev > 0 else o


def bar(name, p0, p1, t, mat, width=None):
    """A bar from p0 to p1, t thick and `width` (default t) wide. The bar's up axis turns towards world Z, so for a
    bar lying in a vertical plane the width stays in that plane and t is the depth across it (along its normal)."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector((t, width or t, d.length)), verts=bm.verts)
    o = _obj(name, bm, mat, (p0 + p1) / 2)
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = d.normalized().to_track_quat("Z", "X" if abs(d.normalized().y) > 0.9 else "Y")
    return o


def dish(name, radius, depth, apex, facing, mat, seg=24, rings=5, thickness=0.035):
    """A parabolic dish whose bowl opens towards `facing`, its deepest point at apex."""
    bm = bmesh.new()
    top = bm.verts.new((0, 0, 0))
    ring = []
    for i in range(1, rings + 1):
        r = radius * i / rings
        z = depth * (i / rings) ** 2
        ring.append([bm.verts.new((r * math.cos(2 * math.pi * k / seg), r * math.sin(2 * math.pi * k / seg), z))
                     for k in range(seg)])
    for k in range(seg):
        bm.faces.new((top, ring[0][k], ring[0][(k + 1) % seg]))
    for i in range(rings - 1):
        a, b = ring[i], ring[i + 1]
        for k in range(seg):
            bm.faces.new((a[k], b[k], b[(k + 1) % seg], a[(k + 1) % seg]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = _obj(name, bm, mat, apex)
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = Vector(facing).normalized().to_track_quat("Z", "Y")
    sol = o.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = thickness
    sol.offset = -1.0
    return o


def icon(prefix, cx, cz, y, s, t):
    """The drone-and-crate logo in cyan, facing -Y on the plane y: a crate outline with its lid line, a drone above
    it on a tether, and double chevrons either side. s scales it (1 = screen size), t is the stroke. Strokes that
    cross overlap in volume but never share a face plane (the crossing ones are offset in depth)."""
    h = 0.13 * s
    box(f"{prefix}_CrateTop", (2 * h + t, t, t), (cx, y, cz + h), CYAN)
    box(f"{prefix}_CrateBottom", (2 * h + t, t, t), (cx, y, cz - h), CYAN)
    box(f"{prefix}_CrateLeft", (t, t * 0.8, 2 * h - t), (cx - h, y, cz), CYAN)
    box(f"{prefix}_CrateRight", (t, t * 0.8, 2 * h - t), (cx + h, y, cz), CYAN)
    box(f"{prefix}_CrateLid", (2 * h - t, t * 0.6, t * 0.7), (cx, y, cz + 0.45 * h), CYAN)
    box(f"{prefix}_Tether", (t * 0.7, t * 0.6, 0.06 * s - t), (cx, y, cz + h + 0.04 * s), CYAN)
    box(f"{prefix}_DroneBody", (0.22 * s, t, t * 1.2), (cx, y, cz + h + 0.085 * s), CYAN)
    for side in (-1, 1):
        box(f"{prefix}_DroneArm{side:+d}", (t * 0.7, t * 0.6, 0.05 * s), (cx + side * 0.1 * s, y, cz + h + 0.11 * s), CYAN)
        box(f"{prefix}_Rotor{side:+d}", (0.11 * s, t * 0.8, t * 0.8), (cx + side * 0.1 * s, y - 0.1 * t, cz + h + 0.14 * s), CYAN)
        for k in (0, 1):
            x0 = cx + side * (0.30 + 0.085 * k) * s
            tip = (x0 + side * 0.035 * s, y, cz)
            back = x0 - side * 0.035 * s
            bar(f"{prefix}_Chevron{side:+d}{k}a", (back, y, cz + 0.07 * s), tip, t, CYAN)
            bar(f"{prefix}_Chevron{side:+d}{k}b", (back, y - 0.2 * t, cz - 0.07 * s), (tip[0], y - 0.2 * t, tip[2]), t, CYAN)


# ---------------------------------------------------------------- platform (and the plinth below the ground)
box("Plinth", (3.84, 3.84, 1.0), (0, 0, -0.5), SLATE)
box("Platform_Base", (3.9, 3.9, 0.22), (0, 0, 0.11), SLATE, 0.05)
for sx in (-1, 1):
    for sy in (-1, 1):
        box(f"Platform_Plate{sx:+d}{sy:+d}", (1.86, 1.86, 0.06), (sx * 0.955, sy * 0.955, 0.25), PLATE, 0.012)
        # the bumpers stand 4 mm proud of the base's sides and 1 cm off the ground, so no face is flush with it
        box(f"Platform_Corner{sx:+d}{sy:+d}", (0.368, 0.368, 0.33), (sx * 1.774, sy * 1.774, 0.175), SLATE, 0.04)
        box(f"Platform_CornerLightX{sx:+d}{sy:+d}", (0.012, 0.22, 0.05), (sx * 1.964, sy * 1.774, 0.21), CYAN)
        box(f"Platform_CornerLightY{sx:+d}{sy:+d}", (0.22, 0.012, 0.05), (sx * 1.774, sy * 1.964, 0.21), CYAN)
for s in (-1, 1):
    box(f"Platform_EdgeLightFront{s:+d}", (0.6, 0.012, 0.045), (s * 0.9, -1.956, 0.12), CYAN)
    box(f"Platform_EdgeLightBack{s:+d}", (0.6, 0.012, 0.045), (s * 0.9, 1.956, 0.12), CYAN)
    box(f"Platform_EdgeLightSide{s:+d}", (0.012, 0.6, 0.045), (s * 1.956, 0.0, 0.12), CYAN)

# ---------------------------------------------------------------- hut
CX, CY, W, D = 0.675, 0.275, 2.15, 2.35                 # x -0.40..1.75, y -0.90..1.45
FRONT, BACK, LEFT, RIGHT = CY - D / 2, CY + D / 2, CX - W / 2, CX + W / 2
box("Hut_Band", (W + 0.06, D + 0.06, 0.20), (CX, CY, 0.38), ORANGE, 0.02)
box("Hut_Walls", (W, D, 1.96), (CX, CY, 1.46), BLUE, 0.03)
box("Hut_TopBand", (W + 0.04, D + 0.04, 0.10), (CX, CY, 2.42), ORANGE, 0.015)
for sx in (-1, 1):
    for sy in (-1, 1):    # from just above the band (as proud as the posts) and the walls' bottom
        box(f"Hut_Corner{sx:+d}{sy:+d}", (0.12, 0.12, 1.91), (CX + sx * (W / 2 - 0.03), CY + sy * (D / 2 - 0.03), 1.44),
            BLUE_DARK, 0.02)
box("Hut_SeamFront0", (0.04, 0.012, 1.86), (-0.12, FRONT - 0.006, 1.46), BLUE_DARK)
for i, x in enumerate((0.10, 1.25)):
    box(f"Hut_SeamBack{i}", (0.04, 0.012, 1.86), (x, BACK + 0.006, 1.46), BLUE_DARK)
for i, y in enumerate((-0.30, 0.95)):
    box(f"Hut_SeamRight{i}", (0.012, 0.04, 1.86), (RIGHT + 0.006, y, 1.46), BLUE_DARK)

# screen with the logo, under an orange awning
box("Screen_Frame", (1.30, 0.07, 0.92), (CX, FRONT - 0.02, 1.47), SLATE, 0.025)
box("Screen_Glass", (1.14, 0.02, 0.78), (CX, FRONT - 0.058, 1.47), SCREEN)
icon("Screen_Icon", CX, 1.42, FRONT - 0.075, 1.0, 0.024)
box("Screen_Awning", (1.46, 0.40, 0.07), (CX, FRONT - 0.17, 2.0), ORANGE, 0.02, rot=(math.radians(-14), 0, 0))
for s in (-1, 1):
    box(f"Screen_AwningBracket{s:+d}", (0.05, 0.30, 0.05), (CX + s * 0.62, FRONT - 0.13, 1.93), SLATE,
        rot=(math.radians(-14), 0, 0))

# side vent (right), back grille, side door (left, towards the crates)
box("Vent_Frame", (0.06, 0.82, 0.66), (RIGHT + 0.03, 0.30, 1.55), SLATE, 0.015)
for i in range(5):
    box(f"Vent_Slat{i}", (0.05, 0.74, 0.07), (RIGHT + 0.05, 0.30, 1.32 + i * 0.115), STEEL,
        rot=(0, math.radians(-30), 0))
box("Back_Frame", (0.95, 0.06, 0.75), (CX, BACK + 0.03, 1.45), SLATE, 0.015)
for i in range(6):
    box(f"Back_Slat{i}", (0.85, 0.05, 0.06), (CX, BACK + 0.05, 1.17 + i * 0.11), STEEL,
        rot=(math.radians(30), 0, 0))
box("Door_Frame", (0.06, 0.92, 1.78), (LEFT - 0.03, 0.55, 1.37), BLUE_DARK, 0.015)
box("Door_Panel", (0.04, 0.80, 1.68), (LEFT - 0.05, 0.55, 1.36), BLUE, 0.01)
box("Door_Window", (0.02, 0.40, 0.30), (LEFT - 0.075, 0.55, 1.82), SCREEN)
box("Door_Handle", (0.05, 0.16, 0.05), (LEFT - 0.09, 0.25, 1.30), ORANGE, 0.01)

# ---------------------------------------------------------------- roof
box("Roof_Lower", (W + 0.32, D + 0.32, 0.18), (CX, CY, 2.56), SLATE, 0.05)
box("Roof_Upper", (W - 0.05, D - 0.05, 0.17), (CX, CY, 2.735), SLATE, 0.045)
ROOF_FRONT, ROOF_RIGHT, ROOF_LEFT = CY - (D + 0.32) / 2, CX + (W + 0.32) / 2, CX - (W + 0.32) / 2
box("Roof_LightFront", (0.5, 0.012, 0.045), (1.45, ROOF_FRONT - 0.006, 2.56), CYAN)
box("Roof_LightRight", (0.012, 0.7, 0.045), (ROOF_RIGHT + 0.006, CY, 2.56), CYAN)
box("Roof_LightLeft", (0.012, 0.7, 0.045), (ROOF_LEFT - 0.006, CY, 2.56), CYAN)
box("Sign_Board", (1.05, 0.16, 0.50), (0.40, -0.70, 3.05), ORANGE, 0.035)
box("Sign_Panel", (0.72, 0.02, 0.32), (0.40, -0.787, 3.05), SLATE, 0.01)
icon("Sign_Icon", 0.40, 3.02, -0.80, 0.52, 0.016)
for i in range(5):
    box(f"Roof_Vent{i}", (0.07, 0.22, 0.11), (0.98 + i * 0.13, -0.55, 2.875), WHITE, 0.01)
cyl("Roof_BeaconPost", 0.035, 0.42, (1.58, -0.70, 3.03), SLATE, seg=12)
cyl("Roof_BeaconLamp", 0.075, 0.14, (1.58, -0.70, 3.31), BEACON)
cyl("Roof_BeaconCap", 0.085, 0.035, (1.58, -0.70, 3.395), SLATE)

# ---------------------------------------------------------------- tower, dish and top beacon
TX, TY, TH, Z0, Z1 = 0.60, 0.75, 0.30, 2.84, 6.36       # posts start inside the base plate (not flush with it)
box("Tower_Base", (0.80, 0.80, 0.06), (TX, TY, 2.85), SLATE, 0.01)
for sx in (-1, 1):
    for sy in (-1, 1):
        box(f"Tower_Post{sx:+d}{sy:+d}", (0.07, 0.07, Z1 - Z0), (TX + sx * TH, TY + sy * TH, (Z0 + Z1) / 2), SLATE)
levels = [3.05, 3.70, 4.35, 5.00, 5.65, 6.30]
for i, z in enumerate(levels):
    m = ORANGE if i == len(levels) - 1 else SLATE
    for s in (-1, 1):   # rings along X sit a little higher than those along Y, and end inside the posts
        box(f"Tower_RingX{i}{s:+d}", (2 * TH + 0.064, 0.045, 0.045), (TX, TY + s * TH, z + 0.004), m)
        box(f"Tower_RingY{i}{s:+d}", (0.042, 2 * TH + 0.064, 0.042), (TX + s * TH, TY, z - 0.004), m)
for i in range(len(levels) - 1):
    za, zb = levels[i] + 0.03, levels[i + 1] - 0.03
    for s in (-1, 1):
        y = TY + s * TH
        bar(f"Tower_BraceX{i}{s:+d}a", (TX - TH, y, za), (TX + TH, y, zb), 0.03, SLATE)
        bar(f"Tower_BraceX{i}{s:+d}b", (TX + TH, y + s * 0.012, za), (TX - TH, y + s * 0.012, zb), 0.03, SLATE)
        x = TX + s * TH
        bar(f"Tower_BraceY{i}{s:+d}a", (x, TY - TH, za), (x, TY + TH, zb), 0.03, SLATE)
        bar(f"Tower_BraceY{i}{s:+d}b", (x + s * 0.012, TY + TH, za), (x + s * 0.012, TY - TH, zb), 0.03, SLATE)
box("Tower_Top", (0.82, 0.82, 0.07), (TX, TY, 6.395), ORANGE, 0.015)
cyl("Tower_BeaconBase", 0.14, 0.10, (TX, TY, 6.48), SLATE)
cyl("Tower_BeaconLamp", 0.10, 0.20, (TX, TY, 6.63), BEACON)
cyl("Tower_BeaconCap", 0.115, 0.04, (TX, TY, 6.75), SLATE)

facing = Vector((-0.45, -0.85, 0.30)).normalized()
apex = Vector((0.02, 0.18, 5.15))
dish("Dish_Bowl", 0.62, 0.20, apex, facing, WHITE)
cyl("Dish_Mount", 0.09, 0.22, apex - facing * 0.11, SLATE, axis=facing)
bar("Dish_Arm", apex - facing * 0.18, (TX - TH, TY - TH, 5.15), 0.07, SLATE)
bar("Dish_FeedArm", apex + facing * 0.01, apex + facing * 0.45, 0.03, STEEL)     # starts inside the hub
cyl("Dish_Feed", 0.06, 0.10, apex + facing * 0.48, ORANGE, axis=facing)
cyl("Dish_Hub", 0.10, 0.05, apex + facing * 0.025, ORANGE, axis=facing)

# ---------------------------------------------------------------- canopy over shelved crates (left)
PX0, PX1, PY0, PY1, ZO, ZI = -1.86, -0.56, -1.55, 1.05, 1.95, 2.18     # posts; roof edge heights outside, inside
for x, z in ((PX0, ZO), (PX1, ZI)):
    for y in (PY0, PY1):
        box(f"Canopy_Post{x:+.2f}{y:+.2f}", (0.08, 0.08, z - 0.28), (x, y, (z + 0.28) / 2), SLATE, 0.01)
        box(f"Canopy_Bracket{x:+.2f}{y:+.2f}", (0.12, 0.12, 0.10), (x, y, z - 0.02), ORANGE, 0.01)
for y in (PY0, PY1):
    bar(f"Canopy_Beam{y:+.2f}", (PX0, y, ZO), (PX1, y, ZI), 0.07, SLATE)
bar("Canopy_BeamOut", (PX0, PY0, ZO + 0.004), (PX0, PY1, ZO + 0.004), 0.066, SLATE)
bar("Canopy_BeamIn", (PX1, PY0, ZI + 0.004), (PX1, PY1, ZI + 0.004), 0.066, SLATE)
slope = math.atan2(ZI - ZO, PX1 - PX0)
ROOF_Z = (ZO + ZI) / 2 + 0.06
box("Canopy_Roof", (1.56, 2.86, 0.05), ((PX0 + PX1) / 2, (PY0 + PY1) / 2, ROOF_Z), SLATE, 0.01, rot=(0, -slope, 0))
# the trim wraps the roof's front edge: 2 cm proud in front, 1.5 cm above and below it
box("Canopy_RoofTrim", (1.58, 0.04, 0.08), ((PX0 + PX1) / 2, (PY0 + PY1) / 2 - 1.43, ROOF_Z), ORANGE,
    rot=(0, -slope, 0))
box("Canopy_Shelf", (1.26, 2.50, 0.05), ((PX0 + PX1) / 2, (PY0 + PY1) / 2, 1.06), SLATE, 0.01)


def wood_crate(name, size, x, y, z0):
    """A wooden crate like the game's: a dark frame (corner posts, top and bottom rims), planks recessed between,
    a diagonal brace on each side, bolts at the front corners, and a dark core behind the plank gaps. Every pair of
    overlapping parts is offset by a few millimetres, so no faces share a plane."""
    sx, sy, h = size
    x0, x1, y0, y1, z1 = x - sx / 2, x + sx / 2, y - sy / 2, y + sy / 2, z0 + h
    t, proud, rec, gap = 0.06, 0.004, 0.012, 0.008
    span(f"{name}_Core", (x0 + 0.045, y0 + 0.045, z0 + 0.01), (x1 - 0.045, y1 - 0.045, z1 - 0.03), WOOD_DARK)
    for cx_, cy_ in ((x0, y0), (x1 - t, y0), (x0, y1 - t), (x1 - t, y1 - t)):
        span(f"{name}_Post{cx_:+.2f}{cy_:+.2f}", (cx_, cy_, z0 + proud), (cx_ + t, cy_ + t, z1 - proud), WOOD_DARK, 0.006)
    for zl in (z0, z1 - t):
        k = "Top" if zl > z0 else "Bottom"
        # front and back rims end 4 mm inside the posts' outer faces
        span(f"{name}_Rim{k}Front", (x0 + proud, y0 - proud, zl), (x1 - proud, y0 - proud + t, zl + t), WOOD_DARK, 0.006)
        span(f"{name}_Rim{k}Back", (x0 + proud, y1 + proud - t, zl), (x1 - proud, y1 + proud, zl + t), WOOD_DARK, 0.006)
        span(f"{name}_Rim{k}Left", (x0 - proud, y0 + t, zl), (x0 - proud + t, y1 - t, zl + t), WOOD_DARK, 0.006)
        span(f"{name}_Rim{k}Right", (x1 + proud - t, y0 + t, zl), (x1 + proud, y1 - t, zl + t), WOOD_DARK, 0.006)
    za, zb = z0 + t, z1 - t

    def planks(face, n=3):
        if face in ("front", "back"):
            a, b = x0 + t, x1 - t
        else:
            a, b = y0 + t, y1 - t
        w = (b - a - (n - 1) * gap) / n
        for k in range(n):
            u0 = a + k * (w + gap)
            if face == "front":
                span(f"{name}_PlankF{k}", (u0, y0 + rec, za), (u0 + w, y0 + rec + 0.025, zb), WOOD)
            elif face == "back":
                span(f"{name}_PlankB{k}", (u0, y1 - rec - 0.025, za), (u0 + w, y1 - rec, zb), WOOD)
            elif face == "left":
                span(f"{name}_PlankL{k}", (x0 + rec, u0, za), (x0 + rec + 0.025, u0 + w, zb), WOOD)
            else:
                span(f"{name}_PlankR{k}", (x1 - rec - 0.025, u0, za), (x1 - rec, u0 + w, zb), WOOD)

    for face in ("front", "back", "left", "right"):
        planks(face)
    # braces: in front of the planks, proud of the frame, corner to corner of the opening
    bw, bt = 0.07, 0.02
    bar(f"{name}_BraceF", (x0 + t, y0 + rec - bt / 2, za), (x1 - t, y0 + rec - bt / 2, zb), bt, WOOD_DARK, width=bw)
    bar(f"{name}_BraceB", (x1 - t, y1 - rec + bt / 2, za), (x0 + t, y1 - rec + bt / 2, zb), bt, WOOD_DARK, width=bw)
    bar(f"{name}_BraceL", (x0 + rec - bt / 2, y1 - t, za), (x0 + rec - bt / 2, y0 + t, zb), bt, WOOD_DARK, width=bw)
    bar(f"{name}_BraceR", (x1 - rec + bt / 2, y0 + t, za), (x1 - rec + bt / 2, y1 - t, zb), bt, WOOD_DARK, width=bw)
    # the lid: planks between the top rims, just below their tops
    n = 3
    w = (sx - 2 * t - (n - 1) * gap) / n
    for k in range(n):
        u0 = x0 + t + k * (w + gap)
        span(f"{name}_Lid{k}", (u0, y0 + t, z1 - rec - 0.025), (u0 + w, y1 - t, z1 - rec), WOOD)
    for bx in (x0 + t / 2, x1 - t / 2):
        for bz in (z0 + t / 2, z1 - t / 2):
            cyl(f"{name}_Bolt{bx:+.2f}{bz:+.2f}", 0.016, 0.012, (bx, y0 - proud - 0.006, bz), BOLT,
                axis=(0, 1, 0), seg=8)


wood_crate("Crate1", (0.86, 0.70, 0.60), -1.20, -0.95, 0.28)
wood_crate("Crate2", (0.80, 0.66, 0.52), -1.22, -0.07, 0.28)
wood_crate("Crate3", (0.66, 0.60, 0.46), -1.24, 0.72, 0.28)
wood_crate("Crate4", (0.76, 0.62, 0.46), -1.22, -0.93, 1.085)
wood_crate("Crate5", (0.60, 0.56, 0.40), -1.24, -0.12, 1.085)

# ---------------------------------------------------------------- pipes and the indicator (front right)
for i, px in enumerate((1.40, 1.58)):
    cyl(f"Pipe_WallFlange{i}", 0.09, 0.04, (px, FRONT - 0.02, 1.05), SLATE, axis=(0, 1, 0))
    cyl(f"Pipe_Out{i}", 0.06, 0.27, (px, FRONT - 0.145, 1.05), BLUE, axis=(0, 1, 0))     # starts inside the flange
    box(f"Pipe_Elbow{i}", (0.16, 0.16, 0.16), (px, FRONT - 0.30, 1.05), ORANGE, 0.03)
    cyl(f"Pipe_Down{i}", 0.06, 0.68, (px, FRONT - 0.30, 0.66), BLUE)
    cyl(f"Pipe_Ring{i}", 0.08, 0.06, (px, FRONT - 0.30, 0.60), ORANGE)
    cyl(f"Pipe_Flange{i}", 0.085, 0.05, (px, FRONT - 0.30, 0.305), SLATE)    # 18 cm apart: they must not touch
box("Pipe_Valve", (0.18, 0.16, 0.20), (1.40, FRONT - 0.30, 0.86), ORANGE, 0.02)
for s in (-1, 1):
    cyl(f"Pipe_ValveDot{s:+d}", 0.025, 0.02, (1.40 + s * 0.045, FRONT - 0.39, 0.88), SLATE, axis=(0, 1, 0), seg=10)
box("Indicator_Housing", (0.13, 0.13, 0.86), (1.76, FRONT - 0.18, 0.71), SLATE, 0.015)
box("Indicator_Light", (0.045, 0.02, 0.66), (1.76, FRONT - 0.25, 0.71), CYAN)

# ---------------------------------------------------------------- collision: boxes only (the game cannot use convex)
for i, (size, loc) in enumerate([
        ((3.90, 3.90, 0.30), (0.0, 0.0, 0.15)),                       # platform
        ((2.48, 2.67, 2.54), (CX, CY, 1.55)),                         # hut and roof
        ((1.52, 2.74, 1.85), (-1.16, -0.25, 1.225)),                  # canopy and crates
        ((0.68, 0.68, 3.95), (TX, TY, 4.795)),                        # tower
        ((0.52, 0.40, 0.85), (1.58, -1.10, 0.725)),                   # pipes and indicator
        ((1.06, 0.16, 0.50), (0.40, -0.70, 3.05)),                    # sign
]):
    o = box(f"UBX_{MODEL}_{i:02d}", size, loc, None, target=coll)
    o.display_type = "WIRE"
coll.hide_render = True

# the focus panel's status icon is a flat glyph drawn by status_icon.py, not a render: drop 0.13.1's settings for one
for key in ("hl_status_icon", "hl_status_parts"):
    if key in parts:
        del parts[key]

depsgraph = bpy.context.evaluated_depsgraph_get()
tris = 0
for o in parts.objects:
    ev = o.evaluated_get(depsgraph)
    me = ev.to_mesh()
    tris += sum(len(p.vertices) - 2 for p in me.polygons)
    ev.to_mesh_clear()
result = {"parts": len(parts.objects), "triangles": tris, "boxes": len([o for o in coll.objects if o.name.startswith("UBX_")])}
