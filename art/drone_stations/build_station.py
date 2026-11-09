"""Build a Drone Station model in Blender (run inside Blender, e.g. through the Blender MCP):

    exec(compile(open(r"<repo>/art/drone_stations/build_station.py").read(), "build_station.py", "exec"),
         {"ROLE": "input"})      # or "output"

Rebuilds collection <MODEL> (the parts) and the UBX_ boxes in collection Collision from scratch in the open .blend
(art/drone_input_station/DroneInputStation.blend or art/drone_output_station/DroneOutputStation.blend), then
art/export_model.py exports it. Version 2 (0.15.2), after the user's concept art ("Drone Station - Input /
Output") and their two notes: the body is like Storage Box II's chest, because it is painted (the paint is the link
channel), and the orange band is the chest's thin stripe, not the concept's wide one. Version 1 (0.15.1) was the
"drone pad" first draft. The parts:
  - a skid base on a plinth (1 m below the ground, for slopes);
  - a housing whose panels take the game's paint colour (material kind "paintable": the station's paint is its
    link channel, so the colour must show; unpainted it is the game's Gray), inside a dark frame with corner posts;
  - chest details on the housing: a thin orange stripe round it at lid height, a row of bolts above it, two steel
    latches over the stripe on each long side, and the chest's fine diagonal ribbing on the panels (export_model.py
    bakes it into the normal map: material property hl_pattern "diagonal");
  - chevrons in the role colour (green for input, orange for output, like the game's pipe rings) on the front and
    the port side: pointing down into the station for an input, up out of it for an output;
  - the station's logo on a screen on the right side, from the user's concept: a cube with an arrow (up for an input,
    which sends by drone; down for an output, which receives) between signal arcs, in glowing cyan;
  - cyan light strips on the base's corner feet;
  - the pipe port's plate on the side where the game's ring sits (the input ring faces the mesh's -Y, which is
    Blender's +Y, the back; the output ring faces Blender's -Y, the front), a vent grille, an access hatch;
  - a landing pad on top with a yellow ring, beacons in the role colour and an antenna mast, and a cargo drone on
    it: orange body, four rotors in guards with a cyan glow, skids, and an orange slatted crate slung under it.
1.9 x 1.6 m, about 1.85 m tall with the drone, front towards -Y, origin at the bottom centre. No two parts share a
face plane where they overlap (export_model.py refuses those: they flicker in the game).
"""
import math

import bmesh
import bpy
from mathutils import Euler, Vector

ROLE = globals().get("ROLE", "input")
if ROLE not in ("input", "output"):
    raise ValueError(f"ROLE must be input or output, not {ROLE!r}")
MODEL = "DroneInputStation" if ROLE == "input" else "DroneOutputStation"
COLLISION = "Collision"
MESH = f"SM_{MODEL}"
PORT_SIDE = 1 if ROLE == "input" else -1          # +Y (back) for the input ring, -Y (front) for the output ring
DOWN = ROLE == "input"                            # chevrons point into the station for an input


def collection(name):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


parts = collection(MODEL)
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


GRAY_PAINT = (0.0723, 0.0908, 0.0908)             # the game's Gray paint (DT_Paints), the stations' default colour
if ROLE == "input":
    ROLE_BASE, ROLE_EMIT = (0.12, 0.85, 0.22), (0.16, 0.95, 0.24)
else:
    ROLE_BASE, ROLE_EMIT = (0.95, 0.15, 0.01), (1.0, 0.13, 0.005)      # the orange of the game's output ring
BODY = material("DS_Body", GRAY_PAINT, 0.5, 0.25, kind="paintable", wear=0.9)
BODY["hl_pattern"] = "diagonal"                   # the chest's fine diagonal ribbing (export_model.py bakes it)
SLATE = material("DS_Slate", (0.03, 0.034, 0.045), 0.55, 0.3, wear=1.0)
PLATE = material("DS_Plate", (0.065, 0.068, 0.072), 0.6, 0.65, kind="metal")
STEEL = material("DS_Steel", (0.45, 0.47, 0.50), 0.35, 0.85, kind="metal")
BOLT = material("DS_Bolt", (0.06, 0.06, 0.065), 0.45, 0.8, kind="metal")
WHITE = material("DS_White", (0.72, 0.73, 0.74), 0.45, 0.05, wear=0.45)
YELLOW = material("DS_Yellow", (0.80, 0.55, 0.06), 0.55, 0.1, wear=0.8)
WOOD = material("DS_Wood", (0.16, 0.085, 0.045), 0.75, 0.0, kind="wood")
WOOD_DARK = material("DS_WoodDark", (0.07, 0.04, 0.024), 0.8, 0.0, kind="wood")
ORANGE = material("DS_Orange", (0.78, 0.30, 0.025), 0.5, 0.15, wear=0.6)       # the hub's and the chest's orange
CYAN = material("DS_Cyan", (0.08, 0.75, 0.90), 0.3, 0.0, (0.12, 0.85, 1.0), 1.0, kind="glow")
SCREEN = material("DS_Screen", (0.005, 0.02, 0.028), 0.15, 0.0, (0.0, 0.05, 0.07), 1.0, kind="screen")
ROLE_GLOW = material(f"DS_Glow_{ROLE}", ROLE_BASE, 0.3, 0.0, ROLE_EMIT, 1.0, kind="glow")
ROLE_PAINT = material(f"DS_Paint_{ROLE}", ROLE_BASE, 0.5, 0.1, wear=0.6)


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


def cyl(name, r, h, loc, mat, axis=(0, 0, 1), seg=20, bev=0.0):
    """A cylinder of radius r and length h centred on loc, along axis."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r, radius2=r, depth=h)
    o = _obj(name, bm, mat, loc)
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = Vector(axis).normalized().to_track_quat("Z", "Y")
    return bevel(o, bev) if bev > 0 else o


def bar(name, p0, p1, t, mat, width=None):
    """A bar from p0 to p1, t thick and `width` (default t) wide; its up axis turns towards world Z."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector((t, width or t, d.length)), verts=bm.verts)
    o = _obj(name, bm, mat, (p0 + p1) / 2)
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = d.normalized().to_track_quat("Z", "X" if abs(d.normalized().y) > 0.9 else "Y")
    return o


def ring(name, r, w, h, z, centre, mat, seg=24):
    """A flat ring (annulus) r outer radius, w wide, h high, its bottom at z, as one closed mesh."""
    bm = bmesh.new()
    outer_lo, outer_hi, inner_lo, inner_hi = [], [], [], []
    for k in range(seg):
        a = 2 * math.pi * k / seg
        c, s = math.cos(a), math.sin(a)
        outer_lo.append(bm.verts.new((r * c, r * s, 0)))
        outer_hi.append(bm.verts.new((r * c, r * s, h)))
        inner_lo.append(bm.verts.new(((r - w) * c, (r - w) * s, 0)))
        inner_hi.append(bm.verts.new(((r - w) * c, (r - w) * s, h)))
    for k in range(seg):
        j = (k + 1) % seg
        bm.faces.new((outer_lo[k], outer_lo[j], outer_hi[j], outer_hi[k]))
        bm.faces.new((inner_lo[j], inner_lo[k], inner_hi[k], inner_hi[j]))
        bm.faces.new((outer_hi[k], outer_hi[j], inner_hi[j], inner_hi[k]))
        bm.faces.new((outer_lo[j], outer_lo[k], inner_lo[k], inner_lo[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _obj(name, bm, mat, (centre[0], centre[1], z))


def chevrons(prefix, x0, y, z0, down, mat, count=2, size=0.11, gap=0.11, t=0.03):
    """Glowing chevrons on the plane y (facing outwards from the housing), pointing down (into the station) or up.
    Each stroke runs a little past the tip so the two meet in a clean point; they sit 2 mm apart in depth, so they
    never share a face plane where they cross."""
    side = 1 if y > 0 else -1
    for i in range(count):
        zc = z0 + i * gap
        tip_dz = -size * 0.75 if down else size * 0.75
        for k, sx in enumerate((-1, 1)):
            yy = y + side * 0.002 * k
            start = Vector((x0 + sx * size, yy, zc - tip_dz / 2))
            tip = Vector((x0, yy, zc + tip_dz / 2))
            end = tip + (tip - start).normalized() * t * 0.6
            bar(f"{prefix}{i}{'LR'[k]}", start, end, t, mat, width=t)


# ---------------------------------------------------------------- base (and the plinth below the ground)
W, D = 1.90, 1.60                                 # outer footprint (x, y)
CX, CY = 0.85, 0.70                               # housing core half sizes
BASE_TOP = 0.14
CORE_TOP = 1.24
box("Plinth", (W - 0.06, D - 0.06, 1.0), (0, 0, -0.5), SLATE)
box("Base_Skid", (W, D, BASE_TOP), (0, 0, BASE_TOP / 2), SLATE, 0.03)
for sx in (-1, 1):
    for sy in (-1, 1):
        # feet stand 6 mm proud of the skid's sides and 1 cm off the ground
        fx, fy = sx * (W / 2 - 0.124), sy * (D / 2 - 0.124)
        box(f"Base_Foot{sx:+d}{sy:+d}", (0.26, 0.26, 0.12), (fx, fy, 0.07), PLATE, 0.015)
        # cyan light strips on the foot's two outer faces, 4 mm proud
        box(f"Base_LightX{sx:+d}{sy:+d}", (0.012, 0.16, 0.028), (fx + sx * (0.13 + 0.002), fy, 0.07), CYAN)
        box(f"Base_LightY{sx:+d}{sy:+d}", (0.16, 0.012, 0.028), (fx, fy + sy * (0.13 + 0.002), 0.07), CYAN)

# ---------------------------------------------------------------- housing: paintable core inside a dark frame
box("Housing_Core", (2 * CX, 2 * CY, CORE_TOP - BASE_TOP), (0, 0, (CORE_TOP + BASE_TOP) / 2), BODY, 0.02)
POST = 0.12
PAD_Z = CORE_TOP + 0.06                            # the pad's underside: the posts' tops
for sx in (-1, 1):
    for sy in (-1, 1):
        box(f"Frame_Post{sx:+d}{sy:+d}", (POST, POST, PAD_Z - 0.12),
            (sx * (CX + 0.02 - POST / 2), sy * (CY + 0.02 - POST / 2), (PAD_Z + 0.12) / 2), SLATE, 0.012)
for sy in (-1, 1):                                 # rails along x: 1.5 cm proud, between the posts
    for zc, name in ((BASE_TOP + 0.05, "Low"), (PAD_Z - 0.003 - 0.035, "Top")):
        box(f"Frame_Rail{name}X{sy:+d}", (2 * CX - 2 * POST + 0.06, 0.08, 0.07),
            (0, sy * (CY + 0.015 - 0.04), zc), SLATE, 0.01)
for sx in (-1, 1):                                 # rails along y
    for zc, name in ((BASE_TOP + 0.05, "Low"), (PAD_Z - 0.003 - 0.035, "Top")):
        box(f"Frame_Rail{name}Y{sx:+d}", (0.08, 2 * CY - 2 * POST + 0.06, 0.07),
            (sx * (CX + 0.015 - 0.04), 0, zc), SLATE, 0.01)
# the chest's thin orange stripe round the housing at lid height, 6 mm proud of the core
STRIPE_Z = 1.115
for sy in (-1, 1):
    box(f"Stripe_X{sy:+d}", (2 * CX - 2 * POST + 0.04, 0.02, 0.022), (0, sy * (CY + 0.006 - 0.01), STRIPE_Z), ORANGE)
for sx in (-1, 1):
    box(f"Stripe_Y{sx:+d}", (0.02, 2 * CY - 2 * POST + 0.04, 0.022), (sx * (CX + 0.006 - 0.01), 0, STRIPE_Z), ORANGE)
# a row of bolts above the stripe (the chest's lid bolts), clear of the latches
BOLT_Z = 1.175
for sy in (-1, 1):
    for i, bx in enumerate((-0.70, -0.38, 0.0, 0.38, 0.70)):
        cyl(f"Lid_BoltX{sy:+d}_{i}", 0.012, 0.016, (bx, sy * (CY + 0.004), BOLT_Z), STEEL, axis=(0, 1, 0), seg=8)
for sx in (-1, 1):
    for i, by in enumerate((-0.48, -0.24, 0.0, 0.24, 0.48)):
        cyl(f"Lid_BoltY{sx:+d}_{i}", 0.012, 0.016, (sx * (CX + 0.004), by, BOLT_Z), STEEL, axis=(1, 0, 0), seg=8)
# two steel latches over the stripe on each long side (the chest's clasps)
for sy in (-1, 1):
    for k, lx in enumerate((-0.55, 0.55)):
        box(f"Latch{sy:+d}_{k}", (0.07, 0.035, 0.10), (lx, sy * (CY + 0.0275 - 0.0175), STRIPE_Z), STEEL, 0.006)
        box(f"Latch{sy:+d}_{k}_Hinge", (0.05, 0.03, 0.025), (lx, sy * (CY + 0.03 - 0.015), STRIPE_Z + 0.062), BOLT,
            0.004)

# ---------------------------------------------------------------- port side: the plate the game's pipe ring sits on
py = PORT_SIDE * CY
box("Port_Plate", (0.46, 0.03, 0.46), (0, py + PORT_SIDE * 0.012, 0.62), STEEL, 0.01)
cyl("Port_Socket", 0.17, 0.03, (0, py + PORT_SIDE * 0.035, 0.62), SLATE, axis=(0, 1, 0), seg=28)
for i, (bx, bz) in enumerate(((-0.19, 0.43), (0.19, 0.43), (-0.19, 0.81), (0.19, 0.81))):
    cyl(f"Port_Bolt{i}", 0.018, 0.016, (bx, py + PORT_SIDE * 0.031, bz), BOLT, axis=(0, 1, 0), seg=8)
chevrons("Port_Chevron", 0.0, py + PORT_SIDE * 0.016, 0.92, DOWN, ROLE_GLOW)

# ---------------------------------------------------------------- the other long side: chevrons over a vent grille
oy = -PORT_SIDE * CY
chevrons("Face_Chevron", 0.0, oy - PORT_SIDE * 0.016, 0.92, DOWN, ROLE_GLOW)
box("Vent_Frame", (0.80, 0.025, 0.42), (0, oy - PORT_SIDE * 0.010, 0.52), SLATE, 0.008)
for i in range(6):
    box(f"Vent_Slat{i}", (0.74, 0.03, 0.035), (0, oy - PORT_SIDE * 0.016, 0.35 + i * 0.068), BOLT, 0.004)

# ---------------------------------------------------------------- left side (-x): an access hatch with handles
hx = -CX
box("Hatch", (0.025, 0.62, 0.62), (hx - 0.008, -0.18, 0.66), SLATE, 0.01)
box("Hatch_Panel", (0.03, 0.54, 0.54), (hx - 0.012, -0.18, 0.66), BODY, 0.008)
for i, zc in enumerate((0.52, 0.80)):
    bar(f"Hatch_Handle{i}", (hx - 0.05, -0.33, zc), (hx - 0.05, -0.03, zc), 0.025, STEEL)
    for k, yy in enumerate((-0.33, -0.03)):
        bar(f"Hatch_HandlePost{i}{k}", (hx - 0.022, yy, zc), (hx - 0.0505, yy, zc), 0.022, STEEL)

# ---------------------------------------------------------------- right side (+x): the logo screen (user's concept)
def logo(prefix, cu, cz, x, up, mat, R=0.12, t=0.02):
    """The station's logo on the plane x, facing +x: a cube (a hexagon with its three inner edges), an arrow above it
    (pointing up: sends by drone; down: receives) and two signal arcs either side. Strokes are square bars t wide;
    each is extended by t/2 so joints close, and strokes that meet sit at different depths (2 mm steps), so no two
    share a face plane where they overlap."""
    def stroke(name, a, b, level):
        a, b = Vector((0, a[0], a[1])), Vector((0, b[0], b[1]))
        d = (b - a).normalized() * (t / 2)
        xx = x + 0.002 * level
        bar(f"{prefix}_{name}", Vector((xx, (a - d).y, (a - d).z)), Vector((xx, (b + d).y, (b + d).z)), t, mat, width=t)
    vert = [(cu + R * math.cos(math.radians(90 - 60 * k)), cz + R * math.sin(math.radians(90 - 60 * k)))
            for k in range(6)]
    for k in range(6):
        stroke(f"Hex{k}", vert[k], vert[(k + 1) % 6], k % 2)
    for i, k in enumerate((5, 1, 3)):                # the cube's three inner edges meet in the middle
        stroke(f"Edge{i}", (cu, cz), vert[k], 2 + i)
    top, tip = cz + R + 0.035, cz + R + 0.165         # the arrow above the cube
    # the head's two strokes meet at about 74 degrees, not 90: at a right angle each stroke's end face would lie in
    # the other's side plane (export_model.py refuses that: it flickers)
    hw, hh = 0.045, 0.06
    if up:
        stroke("Shaft", (cu, top), (cu, tip), 5)
        stroke("HeadL", (cu - hw, tip - hh), (cu, tip), 6)
        stroke("HeadR", (cu + hw, tip - hh), (cu, tip), 7)
    else:
        stroke("Shaft", (cu, tip), (cu, top), 5)
        stroke("HeadL", (cu - hw, top + hh), (cu, top), 6)
        stroke("HeadR", (cu + hw, top + hh), (cu, top), 7)
    for side in (-1, 1):                             # signal arcs: 4 segments each, alternating depth
        for j, r in enumerate((0.19, 0.25)):
            angles = [math.radians(a) for a in (-32, -11, 11, 32)]
            pts = [(cu + side * r * math.cos(a), cz + r * math.sin(a)) for a in angles]
            for k in range(3):
                stroke(f"Arc{'LR'[side > 0]}{j}{k}", pts[k], pts[k + 1], (k + j) % 2)


sx_face = CX
box("Screen_Frame", (0.025, 0.86, 0.56), (sx_face + 0.008, 0.0, 0.62), SLATE, 0.008)
box("Screen_Glass", (0.03, 0.78, 0.48), (sx_face + 0.012, 0.0, 0.62), SCREEN)
logo("Logo", 0.0, 0.55, sx_face + 0.027 + 0.006, ROLE == "input", CYAN)

# ---------------------------------------------------------------- landing pad on top
PAD_T = 0.06
PAD_TOP = PAD_Z + PAD_T
box("Pad", (W - 0.08, D - 0.08, PAD_T), (0, 0, PAD_Z + PAD_T / 2), PLATE, 0.015)
ring("Pad_Ring", 0.60, 0.07, 0.008, PAD_TOP - 0.002, (0, 0), YELLOW, seg=36)
MAST = (-1, 1)                                     # the back-left corner carries an antenna mast, not a post
for sx in (-1, 1):
    for sy in (-1, 1):
        cx, cy = sx * (W / 2 - 0.16), sy * (D / 2 - 0.16)
        if (sx, sy) == MAST:
            h = 0.72
            cyl("Mast", 0.026, h, (cx, cy, PAD_TOP + h / 2 - 0.004), SLATE, seg=10)
            for i, zc in enumerate((PAD_TOP + 0.42, PAD_TOP + 0.58)):
                bar(f"Mast_Arm{i}", (cx - 0.11, cy, zc), (cx + 0.11, cy, zc), 0.018, STEEL)
                for k, ex in enumerate((-0.11, 0.11)):
                    cyl(f"Mast_Tip{i}{k}", 0.014, 0.05, (cx + ex, cy, zc + 0.034), ROLE_GLOW, seg=8)
            cyl("Mast_Beacon", 0.045, 0.06, (cx, cy, PAD_TOP + h + 0.026), ROLE_GLOW, seg=12)
        else:
            cyl(f"Pad_Post{sx:+d}{sy:+d}", 0.03, 0.16, (cx, cy, PAD_TOP + 0.08 - 0.004), SLATE, seg=10)
            cyl(f"Pad_Beacon{sx:+d}{sy:+d}", 0.042, 0.05, (cx, cy, PAD_TOP + 0.16 + 0.021), ROLE_GLOW, seg=12)
        box(f"Pad_Stripe{sx:+d}{sy:+d}", (0.05, 0.21, 0.006), (cx - sx * 0.05, cy - sy * 0.155, PAD_TOP + 0.003),
            YELLOW)

# ---------------------------------------------------------------- the cargo drone
SKID_Z = PAD_TOP + 0.007                          # skids rest 1 mm above the ring's top
BODY_Z = SKID_Z + 0.30                            # the body's bottom
for sx in (-1, 1):
    bar(f"Drone_Skid{sx:+d}", (sx * 0.20, -0.24, SKID_Z + 0.015), (sx * 0.20, 0.24, SKID_Z + 0.015), 0.03, SLATE)
    for sy in (-1, 1):
        bar(f"Drone_Leg{sx:+d}{sy:+d}", (sx * 0.20, sy * 0.15, SKID_Z + 0.03), (sx * 0.15, sy * 0.12, BODY_Z + 0.005),
            0.025, SLATE)
# the crate, slung under the body on two straps
CRATE = 0.30
crate_z0 = SKID_Z + 0.035
box("Drone_Crate", (CRATE - 0.02, CRATE - 0.02, 0.22), (0, 0, crate_z0 + 0.11), ORANGE, 0.006)
for k, (dx, dy) in enumerate(((1, 1), (1, -1), (-1, 1), (-1, -1))):
    box(f"Drone_CrateCorner{k}", (0.03, 0.03, 0.232), (dx * (CRATE / 2 - 0.016), dy * (CRATE / 2 - 0.016),
                                                        crate_z0 + 0.11), SLATE, 0.004)
for k, zc in enumerate((crate_z0 + 0.03, crate_z0 + 0.19)):
    box(f"Drone_CrateBand{k}", (CRATE + 0.004, CRATE + 0.004, 0.024), (0, 0, zc), SLATE, 0.003)
for sy in (-1, 1):                                  # vent slats on the crate's two long faces
    for i in range(3):
        box(f"Drone_CrateSlat{sy:+d}_{i}", (0.20, 0.012, 0.02), (0, sy * (CRATE / 2 - 0.006), crate_z0 + 0.075 + i * 0.035),
            BOLT)
for k, sx in enumerate((-1, 1)):
    bar(f"Drone_Strap{k}", (sx * 0.07, 0, crate_z0 + 0.222), (sx * 0.07, 0, BODY_Z + 0.004), 0.018, STEEL)
box("Drone_Body", (0.42, 0.42, 0.10), (0, 0, BODY_Z + 0.05), ORANGE, 0.03)
box("Drone_Cap", (0.26, 0.26, 0.05), (0, 0, BODY_Z + 0.10 + 0.024), SLATE, 0.015)
box("Drone_Stripe", (0.30, 0.43, 0.022), (0, 0, BODY_Z + 0.05), SLATE, 0.004)
cyl("Drone_Eye", 0.035, 0.03, (0, -0.212, BODY_Z + 0.055), ROLE_GLOW, axis=(0, 1, 0), seg=12)
ROTOR = 0.36
for k, (dx, dy) in enumerate(((1, 1), (1, -1), (-1, 1), (-1, -1))):
    hub = Vector((dx * ROTOR, dy * ROTOR, BODY_Z + 0.075))
    bar(f"Drone_Arm{k}", (dx * 0.14, dy * 0.14, BODY_Z + 0.06), (hub.x, hub.y, hub.z), 0.035, SLATE)
    cyl(f"Drone_Motor{k}", 0.04, 0.07, (hub.x, hub.y, hub.z + 0.02), STEEL, seg=12)
    blade_z = hub.z + 0.06
    a = math.radians(25 + 40 * k)
    for b, ang in enumerate((a, a + math.pi / 2)):
        box(f"Drone_Blade{k}{b}", (0.30, 0.035, 0.007), (hub.x, hub.y, blade_z + 0.006 * b), BOLT, rot=(0, 0, ang))
    ring(f"Drone_Guard{k}", 0.185, 0.018, 0.03, blade_z - 0.018, (hub.x, hub.y), SLATE, seg=24)
    ring(f"Drone_GuardGlow{k}", 0.187, 0.004, 0.012, blade_z - 0.009, (hub.x, hub.y), CYAN, seg=24)
    off = 0.185 / math.sqrt(2)
    box(f"Drone_Light{k}", (0.03, 0.03, 0.022), (hub.x + dx * off, hub.y + dy * off, blade_z - 0.003), ROLE_GLOW)

# ---------------------------------------------------------------- collision: boxes only (the game cannot use convex)
for i, (size, loc) in enumerate((
        ((W, D, PAD_TOP), (0, 0, PAD_TOP / 2)),                      # base, housing and pad
        ((0.86, 0.86, 0.55), (0, 0, PAD_TOP + 0.275)),               # the drone and its crate
)):
    o = box(f"UBX_{MESH}_{i:02d}", size, loc, None, target=coll)
    o.display_type = "WIRE"
    o.hide_render = True

tris = 0
for o in parts.objects:
    dg = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = dg.to_mesh()
    tris += sum(len(p.vertices) - 2 for p in me.polygons)
    dg.to_mesh_clear()
lo = [min((o.matrix_world @ Vector(c))[k] for o in parts.objects if o.name != "Plinth" for c in o.bound_box)
      for k in range(3)]
hi = [max((o.matrix_world @ Vector(c))[k] for o in parts.objects if o.name != "Plinth" for c in o.bound_box)
      for k in range(3)]
result = {"model": MODEL, "role": ROLE, "parts": len(parts.objects), "triangles": tris,
          "boxes": len([o for o in coll.objects if o.name.startswith("UBX_")]),
          "bounds_m": [[round(x, 3) for x in lo], [round(x, 3) for x in hi]],
          "port_ring_mesh_space_cm": [0, round(-(PORT_SIDE * (CY + 0.05)) * 100, 1), 62.0]}
