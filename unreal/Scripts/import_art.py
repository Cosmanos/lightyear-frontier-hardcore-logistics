"""Import the building models (art/<folder>/, written by art/export_model.py) into this project, set up for the game.

Run by tools/cook_art.py through the Python commandlet of Unreal Engine 4.27:
    UE4Editor-Cmd HLArt.uproject -run=pythonscript -script="<this file>"     with HL_ART_SPEC=<spec.json>

Per model <M>, in /Game/HardcoreLogistics/Art/<M>/:
  T_<M>_Albedo, _ORM, _Emissive, _Normal, _Mask   the baked textures, set like the game's construct textures
                                                  (default compression with mipmaps, normal map as normal map); the
                                                  mesh comes with its tangents, so the normal map lines up
  MI_<M>        material instance whose parent is one of the game's own construct materials (spec "parent": the Animal
                Overviewer's, masked, with paint and glow): it only swaps that material's textures and sets its
                Emissive Color, so it renders with the game's compiled shader and no shader code ships
  SM_<M>        the static mesh, one material slot (MI_<M>). Collision: the UBX boxes only, used for traces too
                (CTF_UseSimpleAsComplex); the game's navmesh takes the same boxes (see import_mesh). The game runs
                Chaos physics and cannot read the PhysX data this engine cooks for convex or per-triangle
                collision; boxes need no cooked data
  T_<M>Icon     build-menu icon (the game's icon settings: default compression with mipmaps), never streamed

To cook against the game's material this project needs something at its path: a stand-in material instance at the
parent's path whose parent, /Game/CookStubs/M_ConstructStub, has the same parameter names, with stand-ins of the
parent's textures as defaults (an instance also references its parents' default textures, and those exist in the
game). None of them may ever ship: the game's real assets must be the ones loaded. cook_art.py copies
/Game/HardcoreLogistics only and checks that everything the cooked packages reference outside it exists in the game;
build_buildings.py refuses a container with anything else in it.

MaterialEditingLibrary's set_material_instance_*_parameter_value return False in 4.27 even when they work, so every
override is checked in the instance's parameter arrays instead (and written there if missing). Without them the
building would show the parent's own textures in the game.

Python 3.7 (the engine's).
"""
import json
import os
import traceback

import unreal

SPEC = json.load(open(os.environ["HL_ART_SPEC"], encoding="utf-8"))
REPORT = {"ok": False, "models": {}}

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary

TEX_PARAMS = [  # name in the game's material, file suffix, sampler type in the stand-in master
    ("Albedo", "Albedo", unreal.MaterialSamplerType.SAMPLERTYPE_COLOR),
    ("Emissive Map", "Emissive", unreal.MaterialSamplerType.SAMPLERTYPE_COLOR),
    ("Normal Map", "Normal", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL),
    ("OcclusionRoughnessMetallic Map", "ORM", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR),
    ("Paint Mask", "Mask", unreal.MaterialSamplerType.SAMPLERTYPE_COLOR),
]
EMISSIVE_COLOR = "Emissive Color"


def log(msg):
    unreal.log("HLArt: " + msg)


def import_file(filename, dest_path, dest_name, options=None):
    if not os.path.isfile(filename):
        raise RuntimeError("missing source file " + filename)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", filename)
    task.set_editor_property("destination_path", dest_path)
    task.set_editor_property("destination_name", dest_name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    if options is not None:
        task.set_editor_property("options", options)
    asset_tools.import_asset_tasks([task])
    asset = eal.load_asset(dest_path + "/" + dest_name)
    if asset is None:
        raise RuntimeError("import failed: " + filename)
    return asset


def texture(source, dest, asset_name, srgb, compression, group, mips):
    tex = import_file(source, dest, asset_name)
    tex.set_editor_property("srgb", srgb)
    tex.set_editor_property("compression_settings", compression)
    tex.set_editor_property("lod_group", group)
    tex.set_editor_property("never_stream", True)
    tex.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_FROM_TEXTURE_GROUP if mips
                            else unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    return tex


T = unreal.TextureCompressionSettings
G = unreal.TextureGroup
TEX_SETTINGS = {  # suffix: (sRGB, compression, group), as the game's own construct textures are set
    "Albedo": (True, T.TC_DEFAULT, G.TEXTUREGROUP_WORLD),
    "ORM": (False, T.TC_DEFAULT, G.TEXTUREGROUP_WORLD),
    "Emissive": (True, T.TC_DEFAULT, G.TEXTUREGROUP_WORLD),
    "Normal": (False, T.TC_NORMALMAP, G.TEXTUREGROUP_WORLD_NORMAL_MAP),
    "Mask": (True, T.TC_DEFAULT, G.TEXTUREGROUP_WORLD),
}


def png_width(path):
    """A PNG's width, from its IHDR chunk."""
    with open(path, "rb") as fh:
        head = fh.read(24)
    return int.from_bytes(head[16:20], "big")


def model_textures(folder, dest, name):
    """The baked textures (art/export_model.py), with mipmaps; a blank 8 px paint mask (a model nothing on which takes
    the paint colour) has none, a baked one (a model with paintable parts, the Drone Stations) has them."""
    out = {}
    for _pname, key, _sampler in TEX_PARAMS:
        srgb, compression, group = TEX_SETTINGS[key]
        path = os.path.join(folder, "T_%s_%s.png" % (name, key))
        out[key] = texture(path, dest, "T_%s_%s" % (name, key), srgb, compression, group,
                           key != "Mask" or png_width(path) > 8)
    return out


def stub_textures(folder, name):
    """Stand-ins at the parent's texture paths (the stand-in master's defaults), each a copy of a model file."""
    out = {}
    for key, path in SPEC["stub_textures"].items():
        srgb, _compression, group = TEX_SETTINGS[key]
        src = "Normal" if key == "Normal" else "Mask"
        dest, asset = path.rsplit("/", 1)
        out[key] = texture(os.path.join(folder, "T_%s_%s.png" % (name, src)), dest, asset, srgb,
                           T.TC_NORMALMAP if key == "Normal" else T.TC_DEFAULT, group, False)
    return out


def create(path, cls, factory):
    folder, name = path.rsplit("/", 1)
    if eal.does_asset_exist(path):
        eal.delete_asset(path)
    asset = asset_tools.create_asset(name, folder, cls, factory)
    if asset is None:
        raise RuntimeError("could not create " + path)
    return asset


def stub_master(path, textures):
    """A stand-in for the game's construct master material: the same parameter names, never shipped."""
    mat = create(path, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    nodes = {}
    y = -300
    for pname, key, sampler in TEX_PARAMS:
        e = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSampleParameter2D, -1100, y)
        e.set_editor_property("parameter_name", pname)
        e.set_editor_property("texture", textures[key])
        e.set_editor_property("sampler_type", sampler)
        nodes[key] = e
        y += 300
    paint = mel.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -1100, y)
    paint.set_editor_property("parameter_name", "Paint Color")
    lerp = mel.create_material_expression(mat, unreal.MaterialExpressionLinearInterpolate, -600, -200)
    mel.connect_material_expressions(nodes["Albedo"], "RGB", lerp, "A")
    mel.connect_material_expressions(paint, "", lerp, "B")
    mel.connect_material_expressions(nodes["Mask"], "R", lerp, "Alpha")
    use_paint = mel.create_material_expression(mat, unreal.MaterialExpressionStaticSwitchParameter, -300, -250)
    use_paint.set_editor_property("parameter_name", "Use Paint")
    mel.connect_material_expressions(lerp, "", use_paint, "True")
    mel.connect_material_expressions(nodes["Albedo"], "RGB", use_paint, "False")
    glow = mel.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -1100, y + 300)
    glow.set_editor_property("parameter_name", EMISSIVE_COLOR)
    mult = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -600, 100)
    mel.connect_material_expressions(nodes["Emissive"], "RGB", mult, "A")
    mel.connect_material_expressions(glow, "", mult, "B")
    black = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -600, 300)
    use_glow = mel.create_material_expression(mat, unreal.MaterialExpressionStaticSwitchParameter, -300, 100)
    use_glow.set_editor_property("parameter_name", "Use Emissive")
    mel.connect_material_expressions(mult, "", use_glow, "True")
    mel.connect_material_expressions(black, "", use_glow, "False")
    P = unreal.MaterialProperty
    mel.connect_material_property(use_paint, "", P.MP_BASE_COLOR)
    mel.connect_material_property(use_glow, "", P.MP_EMISSIVE_COLOR)
    mel.connect_material_property(nodes["Albedo"], "A", P.MP_OPACITY_MASK)
    mel.connect_material_property(nodes["Normal"], "RGB", P.MP_NORMAL)
    mel.connect_material_property(nodes["ORM"], "R", P.MP_AMBIENT_OCCLUSION)
    mel.connect_material_property(nodes["ORM"], "G", P.MP_ROUGHNESS)
    mel.connect_material_property(nodes["ORM"], "B", P.MP_METALLIC)
    mel.recompile_material(mat)
    return mat


def stub_instance(path, master):
    mi = create(path, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, master)
    mel.update_material_instance(mi)
    return mi


def param_info(name):
    info = unreal.MaterialParameterInfo()
    info.set_editor_property("name", name)
    info.set_editor_property("association", unreal.MaterialParameterAssociation.GLOBAL_PARAMETER)
    info.set_editor_property("index", -1)
    return info


def texture_overrides(mi):
    return {str(v.get_editor_property("parameter_info").get_editor_property("name")):
            v.get_editor_property("parameter_value") for v in mi.get_editor_property("texture_parameter_values")}


def vector_overrides(mi):
    out = {}
    for v in mi.get_editor_property("vector_parameter_values"):
        c = v.get_editor_property("parameter_value")
        out[str(v.get_editor_property("parameter_info").get_editor_property("name"))] = [
            round(c.r, 4), round(c.g, 4), round(c.b, 4), round(c.a, 4)]
    return out


def model_instance(path, parent, textures):
    mi = create(path, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, parent)
    mel.update_material_instance(mi)
    want = {pname: textures[key] for pname, key, _sampler in TEX_PARAMS}
    for pname, tex in want.items():
        mel.set_material_instance_texture_parameter_value(mi, pname, tex)   # returns False even when it works
    if texture_overrides(mi) != want:
        values = []
        for pname, tex in want.items():
            v = unreal.TextureParameterValue()
            v.set_editor_property("parameter_info", param_info(pname))
            v.set_editor_property("parameter_value", tex)
            values.append(v)
        mi.set_editor_property("texture_parameter_values", values)
    glow = [float(c) for c in SPEC["emissive_color"]]
    colour = unreal.LinearColor(glow[0], glow[1], glow[2], glow[3])
    mel.set_material_instance_vector_parameter_value(mi, EMISSIVE_COLOR, colour)
    if vector_overrides(mi).get(EMISSIVE_COLOR) != [round(c, 4) for c in glow]:
        v = unreal.VectorParameterValue()
        v.set_editor_property("parameter_info", param_info(EMISSIVE_COLOR))
        v.set_editor_property("parameter_value", colour)
        mi.set_editor_property("vector_parameter_values", [v])
    mel.update_material_instance(mi)
    got = texture_overrides(mi)
    if got != want:
        raise RuntimeError("%s: texture overrides are %s, not %s" % (path, got, want))
    for pname, tex in want.items():
        if mel.get_material_instance_texture_parameter_value(mi, pname) != tex:
            raise RuntimeError("%s: %s does not read back as %s" % (path, pname, tex.get_name()))
    if vector_overrides(mi).get(EMISSIVE_COLOR) != [round(c, 4) for c in glow]:
        raise RuntimeError("%s: %s is %s, not %s" % (path, EMISSIVE_COLOR, vector_overrides(mi), glow))
    if mi.get_editor_property("parent") != parent:
        raise RuntimeError(path + ": parent not set")
    return mi


def import_mesh(folder, dest, name, material):
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_as_skeletal", False)
    ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("import_animations", False)
    ui.set_editor_property("automated_import_should_detect_type", False)
    sm = ui.get_editor_property("static_mesh_import_data")
    sm.set_editor_property("combine_meshes", True)
    sm.set_editor_property("auto_generate_collision", False)     # the UBX boxes are the collision
    sm.set_editor_property("generate_lightmap_u_vs", False)      # constructs are spawned at runtime: no lightmaps
    sm.set_editor_property("remove_degenerates", True)
    # Blender's own tangents, so the baked normal map lines up exactly
    sm.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS)
    sm.set_editor_property("convert_scene", True)
    # Blender writes metres and says so (UnitScaleFactor 100); without this the importer reads them as centimetres
    sm.set_editor_property("convert_scene_unit", True)
    sm.set_editor_property("import_uniform_scale", 1.0)
    ui.set_editor_property("static_mesh_import_data", sm)
    mesh = import_file(os.path.join(folder, "SM_%s.fbx" % name), dest, "SM_" + name, ui)
    if not isinstance(mesh, unreal.StaticMesh):
        raise RuntimeError("SM_%s imported as %s, not a static mesh" % (name, type(mesh).__name__))
    slots = mesh.get_editor_property("static_materials")
    for s in slots:
        s.set_editor_property("material_interface", material)
    mesh.set_editor_property("static_materials", slots)
    mesh.set_editor_property("light_map_coordinate_index", 0)

    # collision: boxes only, for physics and traces alike, and the same boxes for navigation
    body = mesh.get_editor_property("body_setup")
    if body is None:
        raise RuntimeError("SM_%s has no body setup" % name)
    agg = body.get_editor_property("agg_geom")
    boxes = list(agg.get_editor_property("box_elems"))
    others = {k: len(agg.get_editor_property(k)) for k in ("convex_elems", "sphere_elems", "sphyl_elems",
                                                           "tapered_capsule_elems")}
    if not boxes:
        raise RuntimeError("SM_%s has no collision boxes: the FBX needs its UBX_SM_%s_NN boxes" % (name, name))
    if any(others.values()):
        raise RuntimeError("SM_%s has collision shapes other than boxes %s; the game cannot use convex ones"
                           % (name, others))
    body.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_SIMPLE_AS_COMPLEX)
    # navigation: the nav collision keeps its defaults (4.27 Python cannot reach UNavCollision's settings, and a config
    # default would leave them unsaved, so the game's default would misread the package). Its cooked data is filed
    # under this engine's format name, which the game (Chaos) never looks up, so the game exports the physics
    # collision, the boxes, to the navmesh instead
    nav = mesh.get_editor_property("nav_collision")

    bounds = mesh.get_bounds()
    if not 50 <= max(bounds.box_extent.x, bounds.box_extent.y) <= 2000:
        raise RuntimeError("SM_%s is %.1f x %.1f cm across: imported at the wrong scale"
                           % (name, 2 * bounds.box_extent.x, 2 * bounds.box_extent.y))

    def box_info(b):
        c = b.get_editor_property("center")
        return {"center": [round(c.x), round(c.y), round(c.z)],
                "size": [round(b.get_editor_property(k)) for k in ("x", "y", "z")]}

    return mesh, {
        "slots": [str(s.get_editor_property("material_slot_name")) for s in slots],
        "collision_boxes": [box_info(b) for b in boxes],
        "collision_trace": str(body.get_editor_property("collision_trace_flag")),
        "navigation": "physics boxes (the game ignores this engine's nav data)" if nav is not None
                      else "no nav collision object",
        "vertices": unreal.EditorStaticMeshLibrary.get_number_verts(mesh, 0),
        "bounds_cm": {"origin": [round(v, 1) for v in (bounds.origin.x, bounds.origin.y, bounds.origin.z)],
                      "extent": [round(v, 1) for v in (bounds.box_extent.x, bounds.box_extent.y, bounds.box_extent.z)]},
    }


def main():
    stub_parent = None
    for m in SPEC["models"]:
        name, folder = m["name"], m["folder"]
        dest = SPEC["dest_root"] + "/" + name
        log("importing %s from %s" % (name, folder))
        textures = model_textures(folder, dest, name)
        if stub_parent is None:
            master = stub_master(SPEC["stub_master"], stub_textures(folder, name))
            stub_parent = stub_instance(SPEC["parent"], master)
        mi = model_instance(dest + "/MI_" + name, stub_parent, textures)
        mesh, info = import_mesh(folder, dest, name, mi)
        icon = texture(os.path.join(folder, "T_%sIcon.png" % name), dest, "T_%sIcon" % name, True, T.TC_DEFAULT,
                       G.TEXTUREGROUP_WORLD, True)
        info["icon_size"] = [icon.blueprint_get_size_x(), icon.blueprint_get_size_y()]
        status = m.get("status_icon")
        if status:   # a focus-panel icon, set like the game's T_WaterIcon (one mip, never streamed)
            st = texture(os.path.join(folder, status + ".png"), SPEC["dest_root"], status, True, T.TC_DEFAULT,
                         G.TEXTUREGROUP_WORLD, False)
            info["status_icon"] = [status, st.blueprint_get_size_x(), st.blueprint_get_size_y()]
        info["material_parent"] = mi.get_editor_property("parent").get_path_name()
        info["material_overrides"] = {k: v.get_name() for k, v in texture_overrides(mi).items()}
        info["material_vectors"] = vector_overrides(mi)
        REPORT["models"][name] = info
        log("%s: %s" % (name, json.dumps(info)))
    for path in [SPEC["stub_master"], SPEC["parent"]] + list(SPEC["stub_textures"].values()):
        if not eal.save_asset(path, only_if_is_dirty=False):
            raise RuntimeError("could not save " + path)
    for m in SPEC["models"]:
        paths = list(eal.list_assets(SPEC["dest_root"] + "/" + m["name"], recursive=True, include_folder=False))
        if m.get("status_icon"):
            paths.append(SPEC["dest_root"] + "/" + m["status_icon"])
        for path in paths:
            if not eal.save_asset(path, only_if_is_dirty=False):
                raise RuntimeError("could not save " + path)
    REPORT["assets"] = sorted(str(p) for p in eal.list_assets(SPEC["dest_root"], recursive=True, include_folder=False))
    REPORT["ok"] = True


try:
    main()
except Exception:  # report it to cook_art.py, which reads the report rather than the exit code
    REPORT["error"] = traceback.format_exc()
    unreal.log_error("HLArt: " + REPORT["error"])
finally:
    with open(SPEC["report"], "w", encoding="utf-8") as fh:
        json.dump(REPORT, fh, indent=1)
