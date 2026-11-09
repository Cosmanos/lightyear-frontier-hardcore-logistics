"""Export a building model from its .blend for tools/cook_art.py (run inside Blender, e.g. through the Blender MCP):

    exec(compile(open(r"<repo>/art/export_model.py").read(), "export_model.py", "exec"), {"MODEL": "LogisticsHub"})

The .blend lives in art/<folder>/ and holds:
  collection <MODEL>      the parts, each with a flat material (Principled BSDF: Base Color, Roughness, Metallic;
                          Emission Color x Emission Strength for parts that glow) and two custom properties:
                          hl_kind  paint (default), paintable, metal, wood, glow or screen: how the bake wears it
                                   (paintable: the game's paint colour shows there, see the paint mask below)
                          hl_wear  0..1, how much a paint's edges are chipped down to bare metal
                          hl_pattern  optional: "diagonal" adds fine diagonal ribs (about 2.5 cm apart) to the normal
                                   map, like the panels of the game's metal chest (Storage Box II)
                          Parts named Plinth* reach below the ground (for slopes) and stay out of the icon.
  collection Collision    boxes named UBX_SM_<MODEL>_NN: the building's collision in the game. Boxes only: the game
                          runs Chaos physics and cannot read the PhysX data Unreal 4.27 cooks for convex (UCX_) or
                          per-triangle collision, while a box is plain numbers it builds itself
  collection Preview      camera and light for the icon

Before anything is written, every pair of parts is checked for faces in the same plane that face the same way and
overlap (more than 1 cm²): the game draws both at the same depth and they flicker. Set ALLOW_COPLANAR to skip that.

The parts are merged into one mesh (smooth shading, edges sharper than 35 degrees kept hard), unwrapped (Smart UV
Project), and their materials are baked in Cycles into TEXTURE px textures. The bake shaders wear each material the
way the game's buildings look:
  paint   colour varies in large blotches; edges (where a bevelled normal leaves the true one) chip down to bare metal,
          broken up by noise; crevices darken (ambient occlusion within the mesh); dirt rises from the ground
  metal   blotchy, brighter at the edges, grime and dirt the same
  wood    grain along each part's length (its longest side), lighter worn edges, grime and dirt
  glow, screen   clean, with their emission
The normal map carries the rounded edges (a bevel shader), in Unreal's convention (green down, "DirectX").

Written next to the .blend:
  SM_<MODEL>.fbx           the merged mesh with one material slot, its UVs and tangents, plus the collision boxes
  T_<MODEL>_Albedo.png     base colour (sRGB)
  T_<MODEL>_ORM.png        R ambient occlusion, G roughness, B metallic (linear)
  T_<MODEL>_Emissive.png   the glow (sRGB), black where nothing glows
  T_<MODEL>_Normal.png     tangent-space normal map (linear, green down)
  T_<MODEL>_Mask.png       paint mask: where the construct's paint colour replaces the albedo (the game's construct
                           master lerps from the albedo to its Paint Color by it). Black, 8 x 8, when no part is
                           paintable (the hub); baked at TEXTURE px when some are (the Drone Stations, whose paint is
                           their link channel): white on paintable parts, falling off where their paint is chipped or
                           dirty, so the albedo there (bare metal, dirt) shows through
  T_<MODEL>Icon.png        build-menu icon, 128 x 128 like the game's (the wheel shows icons at their own size),
                           a 3/4 view from the front left of the baked mesh, framed to fill the square, transparent
A focus-panel status icon is not this script's: the game's are flat glyphs, drawn per model (for the hub,
art/logistics_hub/status_icon.py).

The game material (the Animal Overviewer's, see cook_art.py) samples those textures with UV 0.
Blender's -Y (the front) becomes Unreal's +Y on import; 1 Blender metre = 100 Unreal units.
"""
import math
import os
import struct
import zlib

import bmesh
import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

MODEL = globals().get("MODEL", "LogisticsHub")
CHECK_RENDER = globals().get("CHECK_RENDER")       # optional: also render the baked mesh here (with the plinth)
CHECK_FRAMED = globals().get("CHECK_FRAMED", False)  # frame that render on the model (small models), not the hub's view
PAINT_PREVIEW = globals().get("PAINT_PREVIEW", (0.0723, 0.0908, 0.0908))   # paint colour in renders: the game's Gray
ALLOW_COPLANAR = globals().get("ALLOW_COPLANAR", False)   # export even with overlapping coplanar faces (they flicker)
TEXTURE = globals().get("TEXTURE", 2048)           # baked texture size (the game's buildings use 2048)
BAKE_SAMPLES = 32
ICON_SIZE = 128
ICON_FILL = 0.94                                    # the model's larger side covers this much of the icon
ICON_DIRECTION = Vector((-0.55, -0.78, 0.36)).normalized()   # from the model towards the camera: front left, above
ICON_EXPOSURE = 0.6                                 # stops brighter than the scene: the game's icons are bright
SHARP_DEGREES = 35
BARE_METAL = (0.33, 0.34, 0.36)                     # what chipped paint shows
DIRT = (0.10, 0.075, 0.05)
PRIMER = (0.045, 0.042, 0.04)                       # under a paintable part's paint (the game's albedo is near-black there)


def write_png(path: str, w: int, h: int, pixels: bytes, channels: int) -> None:
    """8-bit RGB (channels 3) or RGBA (4) PNG, rows top to bottom."""
    row = w * channels
    raw = b"".join(b"\0" + pixels[y * row:(y + 1) * row] for y in range(h))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    color_type = 2 if channels == 3 else 6
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, color_type, 0, 0, 0))
                 + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def collection(name: str, create: bool = False):
    col = bpy.data.collections.get(name)
    if col is None and create:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def layer_collection(name: str, root=None):
    root = root or bpy.context.view_layer.layer_collection
    if root.collection.name == name:
        return root
    for child in root.children:
        found = layer_collection(name, child)
        if found:
            return found
    return None


# ---------------------------------------------------------------- the flicker check
def _signed_area(poly) -> float:
    """Shoelace: positive for a counter-clockwise polygon."""
    return 0.5 * sum(poly[k - 1][0] * poly[k][1] - poly[k][0] * poly[k - 1][1] for k in range(len(poly)))


def _clip(subject, clipper):
    """Sutherland-Hodgman: the part of polygon `subject` inside convex polygon `clipper` (both counter-clockwise)."""
    out = subject
    for k in range(len(clipper)):
        a, b = clipper[k], clipper[(k + 1) % len(clipper)]
        inp, out = out, []
        if not inp:
            break

        def inside(p):
            return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= -1e-12

        def cross(p, q):
            den = (p[0] - q[0]) * (a[1] - b[1]) - (p[1] - q[1]) * (a[0] - b[0])
            if abs(den) < 1e-15:
                return q
            t = ((p[0] - a[0]) * (a[1] - b[1]) - (p[1] - a[1]) * (a[0] - b[0])) / den
            return (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))

        s = inp[-1]
        for e in inp:
            if inside(e):
                if not inside(s):
                    out.append(cross(s, e))
                out.append(e)
            elif inside(s):
                out.append(cross(s, e))
            s = e
    return out


def _overlap_area(pa, pb, n) -> float:
    u = n.orthogonal().normalized()
    v = n.cross(u)
    a = [(p.dot(u), p.dot(v)) for p in pa]
    b = [(p.dot(u), p.dot(v)) for p in pb]
    if (max(x for x, _ in a) <= min(x for x, _ in b) or max(x for x, _ in b) <= min(x for x, _ in a)
            or max(y for _, y in a) <= min(y for _, y in b) or max(y for _, y in b) <= min(y for _, y in a)):
        return 0.0
    if _signed_area(a) < 0:
        a.reverse()
    if _signed_area(b) < 0:
        b.reverse()
    clipped = _clip(a, b)
    return abs(_signed_area(clipped)) if len(clipped) >= 3 else 0.0


def coplanar_overlaps(parts, min_area: float = 1e-4) -> list:
    """Pairs of parts with faces in the same plane, facing the same way, overlapping by more than min_area m²
    (1 cm²): the game draws both at the same depth and they flicker (z-fighting). Faces are bucketed by plane:
    normal to 0.01, distance to 2 mm (neighbouring distance buckets are compared too)."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    faces, buckets = [], {}
    for o in parts.objects:
        if o.type != "MESH":
            continue
        ev = o.evaluated_get(depsgraph)
        me = ev.to_mesh()
        mw = ev.matrix_world
        nm = mw.to_3x3().inverted().transposed()
        verts = [mw @ v.co for v in me.vertices]
        for p in me.polygons:
            n = nm @ p.normal
            if n.length < 1e-6:
                continue
            n.normalize()
            pts = [verts[i] for i in p.vertices]
            d = n.dot(pts[0])
            buckets.setdefault((round(n.x * 100), round(n.y * 100), round(n.z * 100), round(d * 500)),
                               []).append(len(faces))
            faces.append((o.name, n, d, pts))
        ev.to_mesh_clear()
    pairs = {}
    for key, idxs in buckets.items():
        near = list(idxs) + buckets.get(key[:3] + (key[3] - 1,), []) + buckets.get(key[:3] + (key[3] + 1,), [])
        for i in idxs:
            name_i, n_i, d_i, pts_i = faces[i]
            for j in near:
                if j <= i:
                    continue
                name_j, n_j, d_j, pts_j = faces[j]
                if name_j == name_i or n_i.dot(n_j) < 0.9995 or abs(d_i - d_j) > 0.0015:
                    continue
                a = _overlap_area(pts_i, pts_j, n_i)
                if a > min_area:
                    k = tuple(sorted((name_i, name_j)))
                    pairs[k] = pairs.get(k, 0.0) + a
    return sorted(pairs.items(), key=lambda kv: -kv[1])


# ---------------------------------------------------------------- merge
def long_axis(o) -> Vector:
    """The world direction of a part's longest side (wood grain runs along it)."""
    dims = [o.dimensions.x, o.dimensions.y, o.dimensions.z]
    k = max(range(3), key=lambda i: dims[i])
    axis = Vector((1.0 if k == 0 else 0.0, 1.0 if k == 1 else 0.0, 1.0 if k == 2 else 0.0))
    return (o.matrix_world.to_3x3() @ axis).normalized()


def merged_mesh(parts, mats: list):
    """One mesh of every part (modifiers applied, world space): one material slot per source material (for the bake),
    a face layer naming the part (plinths are left out of the icon), and a corner colour "grain" with each part's
    long axis (x 0.5 + 0.5), which the wood bake reads."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    names = [m.name for m in mats]
    part_names = []
    for o in parts.objects:
        if o.type != "MESH":
            continue
        ev = o.evaluated_get(depsgraph)
        me = ev.to_mesh()
        me.transform(o.matrix_world)
        slots = [names.index(m.name) if m else 0 for m in me.materials] or [0]
        for p in me.polygons:
            p.material_index = slots[min(p.material_index, len(slots) - 1)]
        before = len(bm.faces)
        bm.from_mesh(me)
        ev.to_mesh_clear()
        bm.faces.ensure_lookup_table()
        part_layer = bm.faces.layers.int.get("part") or bm.faces.layers.int.new("part")
        grain = bm.loops.layers.float_color.get("grain") or bm.loops.layers.float_color.new("grain")
        a = long_axis(o)
        col = (a.x * 0.5 + 0.5, a.y * 0.5 + 0.5, a.z * 0.5 + 0.5, 1.0)
        for f in bm.faces[before:]:
            f[part_layer] = len(part_names)
            for loop in f.loops:
                loop[grain] = col
        part_names.append(o.name)
    for layer in list(bm.loops.layers.uv.values()):
        bm.loops.layers.uv.remove(layer)
    bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        f.smooth = True
    sharp = math.radians(SHARP_DEGREES)
    for e in bm.edges:                                # bevels read as rounded, box edges stay crisp
        e.smooth = len(e.link_faces) == 2 and e.calc_face_angle(math.pi) < sharp
    old = bpy.data.objects.get(f"SM_{MODEL}")
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    old_mesh = bpy.data.meshes.get(f"SM_{MODEL}")
    if old_mesh:
        bpy.data.meshes.remove(old_mesh)
    mesh = bpy.data.meshes.new(f"SM_{MODEL}")
    bm.to_mesh(mesh)
    bm.free()
    return mesh, part_names


# ---------------------------------------------------------------- bake shaders
class Graph:
    """A small helper to build shader node graphs: constants or sockets for every input."""

    def __init__(self, mat):
        mat.use_nodes = True
        self.nt = mat.node_tree
        self.nt.nodes.clear()

    def node(self, kind, **props):
        n = self.nt.nodes.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def put(self, socket, value):
        if isinstance(value, bpy.types.NodeSocket):
            self.nt.links.new(value, socket)
        else:
            socket.default_value = value

    def math(self, op, a, b=0.0, clamp=False):
        n = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        self.put(n.inputs[0], a)
        self.put(n.inputs[1], b)
        return n.outputs[0]

    def vec(self, op, a, b=(0.0, 0.0, 0.0)):
        n = self.node("ShaderNodeVectorMath", operation=op)
        self.put(n.inputs[0], a)
        self.put(n.inputs[1], b)
        return n.outputs["Value"] if op == "DOT_PRODUCT" else n.outputs["Vector"]

    def scale(self, v, f):
        n = self.node("ShaderNodeVectorMath", operation="SCALE")
        self.put(n.inputs[0], v)
        self.put(n.inputs["Scale"], f)
        return n.outputs["Vector"]

    def mix(self, a, b, f):
        """a + (b - a) * f, for colours as vectors."""
        return self.vec("ADD", a, self.scale(self.vec("SUBTRACT", b, a), f))

    def lerp(self, a, b, f):
        return self.math("ADD", a, self.math("MULTIPLY", self.math("SUBTRACT", b, a), f))

    def noise(self, coord, scale, detail, roughness):
        n = self.node("ShaderNodeTexNoise")
        self.put(n.inputs["Vector"], coord)
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = roughness
        return n.outputs["Fac"]


def bake_material(src):
    """A copy of a part material whose shader wears it (see the module docstring). Returns (material, nodes): the
    Principled BSDF, the output, an emission shader for passes baked through emission (metallic, occlusion), and the
    metallic and occlusion values to feed it."""
    v = next(n for n in src.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs
    base = tuple(v["Base Color"].default_value)[:3]
    rough, metal = v["Roughness"].default_value, v["Metallic"].default_value
    strength = min(v["Emission Strength"].default_value, 1.0)
    emit = tuple(c * strength for c in tuple(v["Emission Color"].default_value)[:3])
    kind = src.get("hl_kind", "paint")
    wear = float(src.get("hl_wear", 1.0))
    pattern = src.get("hl_pattern", "")

    mat = bpy.data.materials.get(f"Bake_{src.name}") or bpy.data.materials.new(f"Bake_{src.name}")
    g = Graph(mat)
    out = g.node("ShaderNodeOutputMaterial")
    bsdf = g.node("ShaderNodeBsdfPrincipled")
    emission = g.node("ShaderNodeEmission")
    g.put(emission.inputs["Strength"], 1.0)
    p = g.node("ShaderNodeTexCoord").outputs["Object"]
    geo = g.node("ShaderNodeNewGeometry").outputs["Normal"]
    bevel = g.node("ShaderNodeBevel", samples=8)      # rounded edges for the normal map
    bevel.inputs["Radius"].default_value = 0.025
    bev = bevel.outputs["Normal"]
    wide = g.node("ShaderNodeBevel", samples=8)       # a wider rounding finds edges across modelled bevels too
    wide.inputs["Radius"].default_value = 0.05
    ao_node = g.node("ShaderNodeAmbientOcclusion", only_local=True, samples=16)
    ao_node.inputs["Distance"].default_value = 0.35
    ao = ao_node.outputs["AO"]
    n1 = g.noise(p, 2.5, 4.0, 0.5)                    # large blotches
    n2 = g.noise(p, 14.0, 8.0, 0.65)                  # breaks up the chips
    n3 = g.noise(p, 45.0, 2.0, 0.5)                   # fine speckle
    n4 = g.noise(p, 22.0, 6.0, 0.6)                   # scattered chips away from the edges
    edge = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, g.vec("DOT_PRODUCT", wide.outputs["Normal"], geo)), 12.0,
                  clamp=True)
    grime = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, ao), 1.6, clamp=True)
    z = g.node("ShaderNodeSeparateXYZ")
    g.put(z.inputs[0], p)
    dirt = g.math("MULTIPLY", g.math("MULTIPLY", g.math("SUBTRACT", 0.6, z.outputs["Z"]), 1.8, clamp=True),
                  g.math("ADD", 0.5, g.math("MULTIPLY", n1, 0.5)))

    mask = 0.0                                        # the paint mask's value (paintable parts set it below)

    def finish(col, r, m):
        col = g.scale(col, g.math("SUBTRACT", 1.0, g.math("MULTIPLY", grime, 0.6)))
        col = g.mix(col, DIRT, g.math("MULTIPLY", dirt, 0.55))
        r = g.lerp(r, 0.92, g.math("MULTIPLY", dirt, 0.5))
        r = g.math("ADD", r, g.math("MULTIPLY", g.math("SUBTRACT", n3, 0.5), 0.08), clamp=True)
        return col, r, m

    if kind in ("glow", "screen"):
        col, r, m = base, rough, 0.0
        g.put(bsdf.inputs["Emission Color"], (*emit, 1.0))
        g.put(bsdf.inputs["Emission Strength"], 1.0)
    elif kind == "metal":
        col = g.scale(base, g.math("ADD", 0.8, g.math("MULTIPLY", n1, 0.4)))
        col = g.mix(col, g.scale(base, 1.6), g.math("MULTIPLY", edge, 0.5))
        col, r, m = finish(col, g.math("ADD", rough, g.math("MULTIPLY", g.math("SUBTRACT", n2, 0.5), 0.15)), metal)
    elif kind == "wood":
        attr = g.node("ShaderNodeAttribute", attribute_name="grain")
        axis = g.vec("NORMALIZE", g.vec("SUBTRACT", g.scale(attr.outputs["Color"], 2.0), (1.0, 1.0, 1.0)))
        along = g.vec("DOT_PRODUCT", p, axis)
        across = g.vec("SUBTRACT", p, g.scale(axis, along))
        coord = g.vec("ADD", g.scale(across, 40.0), g.scale(axis, g.math("MULTIPLY", along, 1.5)))
        lines = g.math("MULTIPLY", g.math("SUBTRACT", g.noise(coord, 1.0, 3.0, 0.5), 0.45), 4.0, clamp=True)
        col = g.mix(g.scale(base, 0.6), g.scale(base, 1.3), lines)
        col = g.scale(col, g.math("ADD", 0.9, g.math("MULTIPLY", n1, 0.2)))
        worn = g.math("ADD", g.math("MULTIPLY", edge, 0.9), g.math("MULTIPLY", g.math("SUBTRACT", n2, 0.5), 0.6),
                      clamp=True)
        col = g.mix(col, g.scale(base, 1.7), g.math("MULTIPLY", worn, 0.6))
        col, r, m = finish(col, g.math("ADD", rough, g.math("MULTIPLY", g.math("SUBTRACT", n1, 0.5), 0.1)), 0.0)
    else:                                              # paint, and paintable (chipped the same way)
        chips = g.math("ADD", g.math("MULTIPLY", edge, 1.5), g.math("MULTIPLY", g.math("SUBTRACT", n2, 0.5), 1.2))
        chips = g.math("MULTIPLY", g.math("SUBTRACT", chips, 0.45), 4.0, clamp=True)
        spots = g.math("MULTIPLY", g.math("SUBTRACT", n4, 0.74), 8.0, clamp=True)
        chips = g.math("MULTIPLY", g.math("MAXIMUM", chips, g.math("MULTIPLY", spots, 0.8)), wear)
        bare = g.scale(BARE_METAL, g.math("ADD", 0.8, g.math("MULTIPLY", n2, 0.4)))
        if kind == "paintable":
            # the game paints these in the construct's paint colour; the albedo is what shows where the paint is gone
            # (a dark primer, chipped to bare metal), and the mask falls off at the chips and under the dirt
            primer = g.scale(PRIMER, g.math("ADD", 0.85, g.math("MULTIPLY", n1, 0.3)))
            col = g.mix(primer, bare, chips)
            mask = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, chips),
                          g.math("SUBTRACT", 1.0, g.math("MULTIPLY", dirt, 0.55)), clamp=True)
        else:
            paint = g.scale(g.scale(base, g.math("ADD", 0.78, g.math("MULTIPLY", n1, 0.34))),
                            g.math("ADD", 0.95, g.math("MULTIPLY", n3, 0.1)))
            col = g.mix(paint, bare, chips)
        col, r, m = finish(col, g.lerp(rough, 0.33, chips), g.lerp(metal * 0.6, 0.95, chips))
    g.put(bsdf.inputs["Base Color"], col if isinstance(col, bpy.types.NodeSocket) else (*col, 1.0))
    g.put(bsdf.inputs["Roughness"], r)
    g.put(bsdf.inputs["Metallic"], m)
    normal = bev
    if pattern == "diagonal":
        # bands along x + y + z: diagonal on every face of a box; Blender's diagonal bands repeat every
        # 2 pi / (10 x scale) of x + y + z, which across a face (x + z grows by s * sqrt 2) is about 2.5 cm at 18
        wave = g.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="DIAGONAL", wave_profile="SIN")
        g.put(wave.inputs["Vector"], p)
        wave.inputs["Scale"].default_value = 18.0
        wave.inputs["Distortion"].default_value = 0.0
        wave.inputs["Detail"].default_value = 0.0
        bump = g.node("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.45
        bump.inputs["Distance"].default_value = 0.0015
        g.nt.links.new(wave.outputs["Fac"], bump.inputs["Height"])
        g.nt.links.new(bev, bump.inputs["Normal"])
        normal = bump.outputs["Normal"]
    elif pattern:
        raise RuntimeError(f"material {src.name}: unknown hl_pattern {pattern!r} (only 'diagonal')")
    g.nt.links.new(normal, bsdf.inputs["Normal"])
    g.nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    target = g.node("ShaderNodeTexImage", name="BakeTarget")
    g.nt.nodes.active = target
    return mat, {"bsdf": bsdf, "out": out, "emission": emission, "metal": m, "ao": ao, "mask": mask,
                 "target": target}


# ---------------------------------------------------------------- unwrap and bake
def unwrap(obj) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.hide_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.004, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def pixels(img) -> np.ndarray:
    a = np.empty(len(img.pixels), dtype=np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(-1, 4)


def bake(obj, mats_nodes: list, folder: str) -> dict:
    """Bake every pass into TEXTURE px images and write the PNGs. Returns {pass: path}."""
    scene = bpy.context.scene
    prefs = bpy.context.preferences.addons["cycles"].preferences
    saved = (scene.render.engine, scene.cycles.samples, scene.cycles.device, prefs.compute_device_type)
    images = {}
    paintable = any(isinstance(n["mask"], bpy.types.NodeSocket) for _m, n in mats_nodes)

    def image(name, colorspace):
        img = bpy.data.images.get(name)
        if img is not None:
            bpy.data.images.remove(img)
        img = bpy.data.images.new(name, TEXTURE, TEXTURE, alpha=False, float_buffer=False)
        img.colorspace_settings.name = colorspace
        images[name] = img
        return img

    def connect(nt, socket, value):
        for link in list(socket.links):
            nt.links.remove(link)
        if isinstance(value, bpy.types.NodeSocket):
            nt.links.new(value, socket)
        else:
            socket.default_value = (float(value),) * 3 + (1.0,)

    def run(img, kind, through=None, **kw):
        for mat, nodes in mats_nodes:
            nodes["target"].image = img
            mat.node_tree.nodes.active = nodes["target"]
            links = mat.node_tree.links
            if through is not None:                    # bake a value (a socket or a constant) through emission
                connect(mat.node_tree, nodes["emission"].inputs["Color"], through(nodes))
                links.new(nodes["emission"].outputs["Emission"], nodes["out"].inputs["Surface"])
            else:
                links.new(nodes["bsdf"].outputs["BSDF"], nodes["out"].inputs["Surface"])
        bpy.ops.object.bake(type=kind, margin=8, margin_type="EXTEND", use_clear=True, **kw)

    try:
        prefs.compute_device_type = "OPTIX"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type == "OPTIX"
        if not any(d.use for d in prefs.devices):
            prefs.compute_device_type = "NONE"
        scene.render.engine = "CYCLES"
        scene.cycles.device = "GPU" if prefs.compute_device_type != "NONE" else "CPU"
        scene.cycles.samples = BAKE_SAMPLES
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        albedo = image(f"T_{MODEL}_Albedo", "sRGB")
        run(albedo, "DIFFUSE", pass_filter={"COLOR"})
        rough = image(f"Bake_{MODEL}_Rough", "Non-Color")
        run(rough, "ROUGHNESS")
        metal = image(f"Bake_{MODEL}_Metal", "Non-Color")
        run(metal, "EMIT", through=lambda n: n["metal"])
        occl = image(f"Bake_{MODEL}_AO", "Non-Color")
        run(occl, "EMIT", through=lambda n: n["ao"])
        emissive = image(f"T_{MODEL}_Emissive", "sRGB")
        run(emissive, "EMIT")
        normal = image(f"T_{MODEL}_Normal", "Non-Color")
        run(normal, "NORMAL", normal_space="TANGENT", normal_r="POS_X", normal_g="NEG_Y", normal_b="POS_Z")
        if paintable:                                  # sRGB, as the game samples its paint masks: it decodes back
            mask = image(f"T_{MODEL}_Mask", "sRGB")   # to the baked value
            run(mask, "EMIT", through=lambda n: n["mask"])
        for mat, nodes in mats_nodes:                  # back to the BSDF for renders
            mat.node_tree.links.new(nodes["bsdf"].outputs["BSDF"], nodes["out"].inputs["Surface"])
    finally:
        scene.render.engine, scene.cycles.samples, scene.cycles.device = saved[0], saved[1], saved[2]
        prefs.compute_device_type = saved[3]           # the user's own device choice stays theirs

    orm = image(f"T_{MODEL}_ORM", "Non-Color")
    px = np.ones((TEXTURE * TEXTURE, 4), dtype=np.float32)
    px[:, 0] = pixels(occl)[:, 0]
    px[:, 1] = pixels(rough)[:, 0]
    px[:, 2] = pixels(metal)[:, 0]
    orm.pixels.foreach_set(px.ravel())
    paths = {}
    written = [("Albedo", albedo), ("ORM", orm), ("Emissive", emissive), ("Normal", normal)]
    if paintable:
        written.append(("Mask", mask))
    for key, img in written:
        path = os.path.join(folder, f"T_{MODEL}_{key}.png")
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
        paths[key] = path
    if not paintable:
        write_png(os.path.join(folder, f"T_{MODEL}_Mask.png"), 8, 8, bytes([0, 0, 0] * 64), 3)
        paths["Mask"] = os.path.join(folder, f"T_{MODEL}_Mask.png")
    for name in (f"Bake_{MODEL}_Rough", f"Bake_{MODEL}_Metal", f"Bake_{MODEL}_AO"):
        bpy.data.images.remove(images[name])
    return paths


def preview_material(folder: str):
    """MI_<MODEL> in Blender: the baked textures, so renders of the merged mesh look like the game."""
    mat = bpy.data.materials.get(f"MI_{MODEL}") or bpy.data.materials.new(f"MI_{MODEL}")
    g = Graph(mat)
    out = g.node("ShaderNodeOutputMaterial")
    bsdf = g.node("ShaderNodeBsdfPrincipled")
    g.nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    def image(key, colorspace):
        name = f"T_{MODEL}_{key}"
        img = bpy.data.images.get(name)
        path = os.path.join(folder, f"{name}.png")
        if img is None:
            img = bpy.data.images.load(path)
        img.filepath = path
        img.reload()
        img.colorspace_settings.name = colorspace
        node = g.node("ShaderNodeTexImage")
        node.image = img
        return node

    albedo = image("Albedo", "sRGB").outputs["Color"]
    msep = g.node("ShaderNodeSeparateColor")           # the game's paint (PAINT_PREVIEW here) where the mask is
    g.nt.links.new(image("Mask", "sRGB").outputs["Color"], msep.inputs["Color"])
    g.nt.links.new(g.mix(albedo, PAINT_PREVIEW, msep.outputs["Red"]), bsdf.inputs["Base Color"])
    sep = g.node("ShaderNodeSeparateColor")
    g.nt.links.new(image("ORM", "Non-Color").outputs["Color"], sep.inputs["Color"])
    g.nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    g.nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    g.nt.links.new(image("Emissive", "sRGB").outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 1.0
    nsep = g.node("ShaderNodeSeparateColor")       # Unreal's green-down normal map back to Blender's green-up
    g.nt.links.new(image("Normal", "Non-Color").outputs["Color"], nsep.inputs["Color"])
    comb = g.node("ShaderNodeCombineColor")
    g.nt.links.new(nsep.outputs["Red"], comb.inputs["Red"])
    g.put(comb.inputs["Green"], g.math("SUBTRACT", 1.0, nsep.outputs["Green"]))
    g.nt.links.new(nsep.outputs["Blue"], comb.inputs["Blue"])
    nmap = g.node("ShaderNodeNormalMap")
    g.nt.links.new(comb.outputs["Color"], nmap.inputs["Color"])
    g.nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


# ---------------------------------------------------------------- renders
def aim(obj, target) -> None:
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def frame_icon_camera(cam, points, size: int) -> None:
    """Place the camera along ICON_DIRECTION so the model fills ICON_FILL of a square frame, centred by lens shift."""
    scene = bpy.context.scene
    scene.render.resolution_x = scene.render.resolution_y = size
    lo = Vector([min(p[k] for p in points) for k in range(3)])
    hi = Vector([max(p[k] for p in points) for k in range(3)])
    centre = (lo + hi) / 2
    cam.data.lens = 70
    cam.data.shift_x = cam.data.shift_y = 0.0
    dist = (hi - lo).length * 2.5
    for _ in range(4):
        cam.location = centre + ICON_DIRECTION * dist
        aim(cam, centre)
        bpy.context.view_layer.update()
        ndc = [world_to_camera_view(scene, cam, p) for p in points]
        xs, ys = [c.x for c in ndc], [c.y for c in ndc]
        span = max(max(xs) - min(xs), max(ys) - min(ys))
        dist *= span / ICON_FILL
    cam.location = centre + ICON_DIRECTION * dist
    aim(cam, centre)
    bpy.context.view_layer.update()
    ndc = [world_to_camera_view(scene, cam, p) for p in points]
    xs, ys = [c.x for c in ndc], [c.y for c in ndc]
    cam.data.shift_x = (max(xs) + min(xs)) / 2 - 0.5
    cam.data.shift_y = (max(ys) + min(ys)) / 2 - 0.5


def render(path: str, size: int, transparent: bool, show: list, hide: list, frame_points=None) -> None:
    scene = bpy.context.scene
    cam = scene.camera
    saved = (scene.render.resolution_x, scene.render.resolution_y, scene.render.film_transparent,
             scene.render.filepath, cam.location.copy(), cam.rotation_euler.copy(), cam.data.lens,
             cam.data.shift_x, cam.data.shift_y, scene.view_settings.exposure)
    states = {c: c.hide_render for c in show + hide}
    try:
        for c in show:
            c.hide_render = False
        for c in hide:
            c.hide_render = True
        scene.render.film_transparent = transparent
        if frame_points:
            frame_icon_camera(cam, frame_points, size)
            scene.view_settings.exposure = saved[-1] + ICON_EXPOSURE
        else:
            scene.render.resolution_x = scene.render.resolution_y = size
            cam.location = (-6.2, -8.4, 4.4)
            aim(cam, (0.0, 0.0, 2.7))
            cam.data.lens = 42
            cam.data.shift_x = cam.data.shift_y = 0.0
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
    finally:
        (scene.render.resolution_x, scene.render.resolution_y, scene.render.film_transparent,
         scene.render.filepath, cam.location, cam.rotation_euler, cam.data.lens,
         cam.data.shift_x, cam.data.shift_y, scene.view_settings.exposure) = saved
        for c, v in states.items():
            c.hide_render = v


def icon_copy(obj, part_names: list, export):
    """A temporary copy of the baked mesh without the plinth faces (below the ground)."""
    me = obj.data.copy()
    bm = bmesh.new()
    bm.from_mesh(me)
    layer = bm.faces.layers.int.get("part")
    drop = {i for i, n in enumerate(part_names) if n.startswith("Plinth")}
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f[layer] in drop], context="FACES")
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(f"{obj.name}_Icon", me)
    export.objects.link(o)
    return o


# ---------------------------------------------------------------- main
def main() -> dict:
    if not bpy.data.filepath:
        raise RuntimeError("save the .blend into art/<folder>/ first: the export goes next to it")
    folder = os.path.dirname(bpy.data.filepath)
    parts = collection(MODEL)
    if parts is None:
        raise RuntimeError(f"no collection {MODEL}")
    export = collection("Export", create=True)
    coll = collection("Collision", create=True)
    convex = [o.name for o in coll.objects if o.name.startswith("UCX_")]
    if convex:
        raise RuntimeError(f"Collision holds convex shapes {convex}: the game cannot use them (Chaos physics); "
                           f"use boxes named UBX_SM_{MODEL}_NN")
    boxes = [o for o in coll.objects if o.name.startswith(f"UBX_SM_{MODEL}_")]
    if not boxes:
        raise RuntimeError(f"collection Collision has no UBX_SM_{MODEL}_NN boxes")
    for o in boxes:
        if o.type != "MESH" or len(o.data.vertices) != 8:
            raise RuntimeError(f"{o.name} is not a box (8 vertices)")
    overlaps = coplanar_overlaps(parts)
    if overlaps and not ALLOW_COPLANAR:
        raise RuntimeError("these parts share a face plane where they overlap, which flickers in the game (move one "
                           "a few millimetres): " + "; ".join(f"{a} / {b} ({area * 1e4:.1f} cm²)"
                                                           for (a, b), area in overlaps[:20]))

    mats = sorted({s.material for o in parts.objects if o.type == "MESH" for s in o.material_slots if s.material},
                  key=lambda m: m.name)
    mesh, part_names = merged_mesh(parts, mats)
    mats_nodes = [bake_material(m) for m in mats]
    for mat, _nodes in mats_nodes:
        mesh.materials.append(mat)
    hub = bpy.data.objects.new(f"SM_{MODEL}", mesh)
    export.objects.link(hub)

    # the merged mesh and the boxes must be visible, selectable and renderable (alone) to unwrap, bake and export
    lcs = [layer_collection("Export"), layer_collection("Collision")]
    saved = [(c.hide_viewport, c.exclude, c.collection.hide_viewport, c.collection.hide_select) for c in lcs]
    render_states = {c: c.hide_render for c in (export, coll, parts)}
    try:
        for c in lcs:
            c.exclude = False
            c.hide_viewport = False
            c.collection.hide_viewport = False
            c.collection.hide_select = False
        export.hide_render, coll.hide_render, parts.hide_render = False, True, True
        bpy.context.view_layer.update()
        unwrap(hub)
        textures = bake(hub, mats_nodes, folder)

        # one material slot for the game: the baked textures
        preview = preview_material(folder)
        mesh.materials.clear()
        mesh.materials.append(preview)
        for p in mesh.polygons:
            p.material_index = 0
        for name in ("grain",):
            if name in mesh.color_attributes:
                mesh.color_attributes.remove(mesh.color_attributes[name])

        bpy.ops.object.select_all(action="DESELECT")
        for o in [hub] + boxes:
            o.hide_set(False)
            o.select_set(True)
        bpy.context.view_layer.objects.active = hub
        fbx = os.path.join(folder, f"SM_{MODEL}.fbx")
        bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, object_types={"MESH"}, use_mesh_modifiers=True,
                                 mesh_smooth_type="FACE", use_tspace=True, apply_unit_scale=True,
                                 apply_scale_options="FBX_SCALE_UNITS", add_leaf_bones=False, bake_anim=False,
                                 axis_forward="-Z", axis_up="Y")
        bpy.ops.object.select_all(action="DESELECT")

        icon = icon_copy(hub, part_names, export)
        hub.hide_render = True
        try:
            pts = [v.co.copy() for v in icon.data.vertices]
            render(os.path.join(folder, f"T_{MODEL}Icon.png"), ICON_SIZE, True, show=[export], hide=[parts, coll],
                   frame_points=pts)
        finally:
            hub.hide_render = False
            bpy.data.objects.remove(icon, do_unlink=True)
        if CHECK_RENDER:
            frame = [v.co.copy() for v in mesh.vertices if v.co.z > -0.01] if CHECK_FRAMED else None
            render(CHECK_RENDER, 1000, False, show=[export], hide=[parts, coll], frame_points=frame)
    finally:
        for c, (hv, ex, chv, chs) in zip(lcs, saved):
            c.exclude, c.hide_viewport = ex, hv
            c.collection.hide_viewport, c.collection.hide_select = chv, chs
        for c, v in render_states.items():
            c.hide_render = v
    export.hide_render = coll.hide_render = True
    parts.hide_render = False
    bpy.ops.wm.save_mainfile()

    lo = [min(v.co[k] for v in mesh.vertices) for k in range(3)]
    hi = [max(v.co[k] for v in mesh.vertices) for k in range(3)]
    return {"fbx": fbx, "textures": textures, "triangles": sum(len(p.vertices) - 2 for p in mesh.polygons),
            "materials": {m.name: m.get("hl_kind", "paint") for m in mats}, "collision_boxes": len(boxes),
            "bounds_m": [[round(x, 3) for x in lo], [round(x, 3) for x in hi]]}


result = main()
