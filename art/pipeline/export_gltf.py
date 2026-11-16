"""Export a photoreal model as a game-ready GLB for real-time 3D (three.js).

The path-traced look lives in procedural Cycles materials, which no game engine
can run. This script turns it into plain PBR textures:

  1. build the model without geometric bevels (they go into the normal map),
  2. join the parts into two bake sets: "gun" (everything that rotates) and
     "static" (props, fortifications), each with one UV atlas,
  3. bake base colour, roughness, metallic, normal and ambient occlusion,
  4. split the gun again into the nodes the game animates:
        turret     yaw around the vertical axis at the tower centre
        elevating  pitch about the trunnions (child of turret)
        recoil     barrel + breech, slides along the bore axis (child of elevating)
  5. write one .glb: 1 unit = 1 m, +Y up, the gun points along -Z at yaw 0.

Usage: python3 export_gltf.py --model howitzer --level 1 --size 2048 --out ../../public/assets/towers
"""
import argparse
import importlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import bmesh  # noqa: E402,I001  (needs bpy loaded first)
import numpy as np  # noqa: E402

from strelite_art import geo, materials, materials_photoreal as mp, scene as stage  # noqa: E402

GUN_NODES = ("turret", "elevating", "recoil")


def log(msg):
    print(f"[export] {msg}", flush=True)


def node_of(obj):
    """(node name, node empty) an object belongs to; ("static", None) if it never moves."""
    o = obj
    while o is not None:
        if "node" in o.keys():
            return o["node"], o
        o = o.parent
    return "static", None


def select_only(objs, active=None):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def realise(scene, objs, part_index, name):
    """World-space copies with modifiers applied, joined into one mesh object.
    Every face remembers its node in the int attribute "part"."""
    dg = bpy.context.evaluated_depsgraph_get()
    copies = []
    for obj in objs:
        me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg), preserve_all_data_layers=True,
                                             depsgraph=dg)
        me.transform(obj.matrix_world)
        if obj.matrix_world.determinant() < 0:
            me.flip_normals()
        if _signed_volume(me) < -1e-9:
            log(f"WARNING: {obj.name} is inside-out (normals point inwards)")
        a = me.attributes.new("part", "INT", "FACE")
        a.data.foreach_set("value", np.full(len(me.polygons), part_index[obj], np.int32))
        c = bpy.data.objects.new(name, me)
        scene.collection.objects.link(c)
        copies.append(c)
    select_only(copies)
    bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    joined.name = name
    return joined


def _signed_volume(me):
    """> 0 for a closed mesh whose normals point outwards."""
    n = len(me.vertices)
    co = np.empty(n * 3, np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    me.calc_loop_triangles()
    tri = np.empty(len(me.loop_triangles) * 3, np.int32)
    me.loop_triangles.foreach_get("vertices", tri)
    a, b, c = (co[tri.reshape(-1, 3)[:, i]] for i in range(3))
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)


def unwrap(obj, margin):
    select_only([obj])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=margin, area_weight=0.0)
    bpy.ops.object.mode_set(mode="OBJECT")


def bake_set(scene, obj, size, samples, out_dir, tag):
    """Bake the five maps of one joined object. Returns {key: image}."""
    mats = [s.material for s in obj.material_slots if s.material]
    targets = {}
    for m in mats:
        n = m.node_tree.nodes.new("ShaderNodeTexImage")
        n.name = "BAKE_TARGET"
        targets[m] = n

    def point_at(img):
        for m, n in targets.items():
            n.image = img
            for other in m.node_tree.nodes:
                other.select = False
            n.select = True
            m.node_tree.nodes.active = n

    def new_image(key, data):
        img = bpy.data.images.new(f"{tag}_{key}", size, size, alpha=False)
        if data:
            img.colorspace_settings.name = "Non-Color"
        return img

    def run(kind):
        t = time.time()
        select_only([obj])
        bpy.ops.object.bake(type=kind, margin=max(4, size // 256), use_clear=True)
        log(f"{tag}: baked {kind} in {time.time() - t:.0f}s")

    images = {}
    scene.cycles.samples = samples
    # Channels of the Principled BSDF are baked one at a time through an emission shader:
    # this captures the exact value fed to the socket, with no lighting in it.
    for key, sock_name, data in (("base", "Base Color", False), ("rough", "Roughness", True),
                                 ("metal", "Metallic", True)):
        img = images[key] = new_image(key, data)
        point_at(img)
        undo = []
        for m in mats:
            nt = m.node_tree
            out = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
            old = out.inputs["Surface"].links[0].from_socket
            em = nt.nodes.new("ShaderNodeEmission")
            pbr = nt.nodes.get("PBR")
            if pbr is None:
                em.inputs["Color"].default_value = (0.02, 0.02, 0.02, 1)
            else:
                src = pbr.inputs[sock_name]
                if src.is_linked:
                    nt.links.new(src.links[0].from_socket, em.inputs["Color"])
                elif sock_name == "Base Color":
                    em.inputs["Color"].default_value = tuple(src.default_value)
                else:
                    v = float(src.default_value)
                    em.inputs["Color"].default_value = (v, v, v, 1)
            nt.links.new(em.outputs[0], out.inputs["Surface"])
            undo.append((nt, out, old, em))
        run("EMIT")
        for nt, out, old, em in undo:
            nt.links.new(old, out.inputs["Surface"])
            nt.nodes.remove(em)
    images["normal"] = new_image("normal", True)
    point_at(images["normal"])
    run("NORMAL")
    images["ao"] = new_image("ao", True)
    point_at(images["ao"])
    scene.cycles.samples = samples * 2
    run("AO")
    for m, n in targets.items():
        m.node_tree.nodes.remove(n)

    def pixels(img):
        a = np.empty(size * size * 4, np.float32)
        img.pixels.foreach_get(a)
        return a.reshape(size, size, 4)

    # glTF packs occlusion (R), roughness (G), metallic (B) into one texture.
    orm = np.ones((size, size, 4), np.float32)
    # the AO bake is taken at few samples; a 1-texel blur hides the grain
    ao = pixels(images["ao"])[..., 0]
    ao = (ao + np.roll(ao, 1, 0) + np.roll(ao, -1, 0) + np.roll(ao, 1, 1) + np.roll(ao, -1, 1)) / 5.0
    orm[..., 0] = ao
    orm[..., 1] = pixels(images["rough"])[..., 0]
    orm[..., 2] = pixels(images["metal"])[..., 0]
    images["orm"] = new_image("orm", True)
    images["orm"].pixels.foreach_set(orm.ravel())
    os.makedirs(out_dir, exist_ok=True)
    for key in ("base", "orm", "normal"):
        img = images[key]
        img.filepath_raw = os.path.join(out_dir, f"{tag}_{key}.png")
        img.file_format = "PNG"
        img.save()
    return images


def occlusion_group():
    """The node group Blender's glTF exporter reads the occlusion texture from."""
    name = "glTF Material Output"
    grp = bpy.data.node_groups.get(name)
    if grp is None:
        grp = bpy.data.node_groups.new(name, "ShaderNodeTree")
        grp.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    return grp


def game_material(name, images):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.use_backface_culling = True               # exported as single-sided
    nt = m.node_tree
    pbr = nt.nodes["Principled BSDF"]
    tb = nt.nodes.new("ShaderNodeTexImage")
    tb.image = images["base"]
    nt.links.new(tb.outputs["Color"], pbr.inputs["Base Color"])
    to = nt.nodes.new("ShaderNodeTexImage")
    to.image = images["orm"]
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(to.outputs["Color"], sep.inputs[0])
    nt.links.new(sep.outputs[1], pbr.inputs["Roughness"])
    nt.links.new(sep.outputs[2], pbr.inputs["Metallic"])
    occ = nt.nodes.new("ShaderNodeGroup")
    occ.node_tree = occlusion_group()
    nt.links.new(sep.outputs[0], occ.inputs["Occlusion"])
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = images["normal"]
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], pbr.inputs["Normal"])
    return m


def decal_material(src):
    """Stencil decal for the game: flat off-white paint, alpha from the stencil image."""
    name = "decal_" + src.name.split("__")[0]
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    tex = next(n for n in src.node_tree.nodes if n.bl_idname == "ShaderNodeTexImage")
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    pbr = nt.nodes["Principled BSDF"]
    pbr.inputs["Base Color"].default_value = (0.57, 0.55, 0.48, 1)
    pbr.inputs["Roughness"].default_value = 0.7
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = tex.image
    nt.links.new(t.outputs["Color"], pbr.inputs["Alpha"])
    m.surface_render_method = "BLENDED"
    return m


def split_part(scene, joined, idx, name, material):
    """Faces of one node, as a new object still in world space."""
    me = joined.data.copy()
    bm = bmesh.new()
    bm.from_mesh(me)
    layer = bm.faces.layers.int["part"]
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f[layer] != idx], context="FACES")
    bm.to_mesh(me)
    bm.free()
    me.materials.clear()
    me.materials.append(material)
    for a in ("part", "pcoord", "ocoord", "rnd"):
        if a in me.attributes:
            me.attributes.remove(me.attributes[a])
    obj = bpy.data.objects.new(name, me)
    scene.collection.objects.link(obj)
    return obj


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="howitzer")
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--size", type=int, default=2048, help="texture size of each atlas")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "..", "public",
                                                  "assets", "towers"))
    ap.add_argument("--tex-dir", default=os.path.join(os.path.dirname(__file__), "..", "out", "bake"))
    a = ap.parse_args(argv)
    t0 = time.time()

    geo.OPTIONS["bevel"] = False
    mp.OPTIONS["bevel_normal"] = True
    materials.clear_cache()
    scene = stage.reset_scene()
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.render.bake.use_selected_to_active = False
    model = importlib.import_module(f"strelite_art.models.{a.model}")
    root, turret = model.build("photoreal", a.level)
    mp.stamp(scene)
    bpy.context.view_layer.update()
    tag = f"{a.model}_L{a.level}"

    # --- sort the parts
    node_world = {"static": None}
    sets = {"gun": [], "static": []}
    decals = []
    part_index = {}
    order = ("static",) + GUN_NODES
    for obj in [o for o in scene.objects if o.type == "MESH"]:
        name, empty = node_of(obj)
        if empty is not None:
            node_world[name] = empty.matrix_world.copy()
        part_index[obj] = order.index(name)
        if obj.name.startswith("decal"):
            decals.append((obj, name))
        else:
            sets["gun" if name in GUN_NODES else "static"].append(obj)
    originals = [o for o in scene.objects if o.type == "MESH"]

    # --- join, unwrap, bake
    ground = bpy.data.objects.new("ground", bpy.data.meshes.new("ground"))
    ground.data.from_pydata([(-30, -30, -0.002), (30, -30, -0.002), (30, 30, -0.002),
                             (-30, 30, -0.002)], [], [(0, 1, 2, 3)])
    scene.collection.objects.link(ground)
    world = bpy.data.worlds.new("bake")
    world.light_settings.distance = 2.0        # ambient occlusion reach, metres
    scene.world = world
    joined, images = {}, {}
    for key in ("gun", "static"):
        if sets[key]:
            joined[key] = realise(scene, sets[key], part_index, f"{tag}_{key}")
            unwrap(joined[key], 0.0025)
            log(f"{key}: {len(joined[key].data.polygons)} faces, "
                f"{sum(len(p.vertices) - 2 for p in joined[key].data.polygons)} triangles")
    for o in originals:
        o.hide_render = True
    for key, obj in joined.items():
        for other in joined.values():
            other.hide_render = other is not obj       # occlusion: only itself and the ground
        images[key] = bake_set(scene, obj, a.size, a.samples, a.tex_dir, f"{tag}_{key}")
    ground.hide_render = True

    # --- rebuild as a clean game hierarchy
    dg = bpy.context.evaluated_depsgraph_get()
    decal_meshes = {}
    for obj, name in decals:
        me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
        me.transform(obj.matrix_world)
        for attr in ("pcoord", "ocoord", "rnd"):
            if attr in me.attributes:
                me.attributes.remove(me.attributes[attr])
        mat = decal_material(obj.material_slots[0].material)
        me.materials.clear()
        me.materials.append(mat)
        decal_meshes.setdefault((name, mat.name), []).append(me)
    for o in list(scene.objects):                       # the build scene is no longer needed
        if o not in joined.values():
            bpy.data.objects.remove(o)
    exp_root = bpy.data.objects.new(tag, None)
    scene.collection.objects.link(exp_root)
    export = [exp_root]
    nodes = {}
    if "static" in joined:
        st = split_part(scene, joined["static"], 0, "static", game_material(f"{tag}_static", images["static"]))
        st.parent = exp_root
        nodes["static"] = st
        export.append(st)
    gun_mat = game_material(f"{tag}_gun", images["gun"])
    parent = exp_root
    for name in GUN_NODES:
        o = split_part(scene, joined["gun"], order.index(name), name, gun_mat)
        m = node_world[name]
        o.data.transform(m.inverted())
        o.parent = parent
        o.matrix_world = m
        nodes[name] = o
        export.append(o)
        parent = o
        bpy.context.view_layer.update()
    for (name, mat_name), meshes in decal_meshes.items():
        parts = []
        for me in meshes:
            d = bpy.data.objects.new(f"{name}_{mat_name}", me)
            scene.collection.objects.link(d)
            parts.append(d)
        select_only(parts)
        bpy.ops.object.join()
        d = bpy.context.view_layer.objects.active
        host = nodes[name]
        d.data.transform(host.matrix_world.inverted())
        d.parent = host
        export.append(d)
    for o in joined.values():
        bpy.data.objects.remove(o)
    bpy.context.view_layer.update()

    os.makedirs(a.out, exist_ok=True)
    path = os.path.abspath(os.path.join(a.out, f"{tag}.glb"))
    select_only(export, exp_root)
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True,
                              export_image_format="WEBP", export_image_quality=90,
                              export_yup=True, export_apply=False, export_tangents=False,
                              export_animations=False, export_extras=False)
    tris = sum(len(p.vertices) - 2 for o in export if o.type == "MESH" for p in o.data.polygons)
    log(f"wrote {path}: {os.path.getsize(path) / 1e6:.1f} MB, {tris} triangles, "
        f"{time.time() - t0:.0f}s total")


if __name__ == "__main__":
    main()
