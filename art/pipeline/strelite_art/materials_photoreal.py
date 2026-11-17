"""Materials for the "photoreal" style (style В).

Everything is authored at real-world scale (object coordinates are metres) and
values follow measured references (physicallybased.info): albedo of paint, soil
and rubber, dielectric F0 0.04, metals as metallic=1 with measured base colour.

Painted parts age in layers, the way a real object does:
  steel -> red-oxide primer -> matt paint (tone differs slightly per panel)
  -> chipped edges (primer, then bare metal on the most exposed ones)
  -> rust streaks running down vertical faces
  -> dust on upward faces, in cavities and near the ground.
Masks are geometry driven (edges via the Bevel node, cavities via AO, "up" via
the world normal), so no UVs and no texture files are needed. Photo textures can
later be mixed in per material through `PHOTO_TEXTURES`.
"""
import os

import bpy

from .materials import srgb

# Reference object whose space the 3D patterns of the rotating parts live in (the
# gun), so wear does not swim when the gun turns. Set by the model.
_ref = {"obj": None}
# Set True by the exporter: round the edges in the shading normal (Bevel node), so the
# baked normal map carries the chamfers and the game mesh can stay un-bevelled.
OPTIONS = {"bevel_normal": False}
# name -> image path for stencil decals (white paint through a stencil).
_decals = {}

DUST = (0.62, 0.53, 0.40)       # sRGB, dry soil dust; matches the terrain
PRIMER = (0.42, 0.17, 0.12)     # red-oxide primer
RUST = (0.33, 0.16, 0.08)
BARE_STEEL = (0.56, 0.57, 0.58)

# name: (builder, kwargs)
OLIVE = (0.34, 0.35, 0.24)      # FS 34087 olive drab
GREEN_4BO = (0.30, 0.37, 0.21)  # Soviet 4BO protective green
ENEMY_GREY = (0.15, 0.16, 0.16)  # the attackers' dark grey
SPEC = {
    "paint_olive":   ("painted", dict(color=OLIVE, rough=0.62)),
    "paint_olive_worn": ("painted", dict(color=OLIVE, rough=0.6, wear=1.8, dust=1.3)),
    "paint_barrel":  ("painted", dict(color=OLIVE, rough=0.58, wear=0.7, dust=0.6)),
    "paint_soot":    ("painted", dict(color=OLIVE, rough=0.7, wear=1.5, dust=0.4, soot=1.0)),
    "paint_red":     ("painted", dict(color=(0.62, 0.10, 0.09), rough=0.5, wear=1.2, dust=0.5)),
    "paint_white":   ("painted", dict(color=(0.80, 0.79, 0.74), rough=0.5, wear=1.2, dust=0.5)),
    "paint_yellow":  ("painted", dict(color=(0.80, 0.62, 0.10), rough=0.5, wear=0.6, dust=0.5)),
    "paint_shell":   ("painted", dict(color=(0.27, 0.30, 0.19), rough=0.42, wear=0.4, dust=0.5)),
    "paint_crate":   ("painted", dict(color=(0.30, 0.32, 0.21), rough=0.7, wear=1.6, dust=1.0,
                                      primer=(0.60, 0.46, 0.29), bare=None)),
    "gunmetal":      ("metal", dict(color=(0.17, 0.17, 0.18), rough=0.36, dust=0.5)),
    "steel_worn":    ("metal", dict(color=(0.42, 0.41, 0.40), rough=0.42, dust=1.2, rust=0.5)),
    "chrome":        ("metal", dict(color=(0.86, 0.87, 0.88), rough=0.10, dust=0.15)),
    "copper":        ("metal", dict(color=(0.86, 0.52, 0.36), rough=0.3, dust=0.3)),
    "rubber":        ("plain", dict(color=(0.045, 0.045, 0.045), rough=0.78, dust=1.4)),
    "hose":          ("plain", dict(color=(0.03, 0.03, 0.03), rough=0.45, dust=0.6)),
    "glass":         ("plain", dict(color=(0.02, 0.03, 0.03), rough=0.04, dust=0.3)),
    "wood":          ("wood", dict(color=(0.63, 0.48, 0.30))),
    "rope":          ("plain", dict(color=(0.55, 0.47, 0.33), rough=0.95, dust=0.6)),
    "stone":         ("stone", {}),
    "dirt":          ("dirt", {}),
    "grass":         ("grass", {}),
    "bore":          ("bore", {}),
    # --- field fortifications
    "dirt_fill":     ("dirt", dict(masks=False)),
    "burlap":        ("cloth", dict(color=(0.64, 0.56, 0.40), alt=(0.40, 0.43, 0.30))),
    "flag":          ("cloth", dict(color=(0.74, 0.07, 0.09), dust=0.0, translucent=0.35, wrinkle=6.0)),
    "geotextile":    ("geotextile", {}),
    "concrete":      ("concrete", {}),
    "log":           ("log", {}),
    "camo_net":      ("camo_net", {}),
    "screen":        ("screen", {}),
    # --- Soviet protective green 4BO (ZIS-3 type)
    "paint_4bo":      ("painted", dict(color=GREEN_4BO, rough=0.6, wear=1.2)),
    "paint_4bo_worn": ("painted", dict(color=GREEN_4BO, rough=0.6, wear=1.9, dust=1.3)),
    "paint_4bo_barrel": ("painted", dict(color=GREEN_4BO, rough=0.55, wear=0.8, dust=0.6)),
    "paint_4bo_soot": ("painted", dict(color=GREEN_4BO, rough=0.7, wear=1.5, dust=0.4, soot=1.0)),
    "brass":         ("metal", dict(color=(0.80, 0.66, 0.34), rough=0.28, dust=0.3)),
    # --- enemy vehicles and troops: dark grey, so they read on the pale road and the meadow
    "paint_enemy":      ("painted", dict(color=ENEMY_GREY, rough=0.55, wear=0.9, dust=0.5)),
    "paint_enemy_worn": ("painted", dict(color=ENEMY_GREY, rough=0.58, wear=1.6, dust=0.8)),
    "track_steel":   ("metal", dict(color=(0.20, 0.19, 0.18), rough=0.55, dust=1.8, rust=0.6)),
    "canvas":        ("cloth", dict(color=(0.27, 0.27, 0.22), alt=(0.23, 0.24, 0.20), dust=0.5, wrinkle=5.0)),
    "uniform":       ("cloth", dict(color=(0.20, 0.21, 0.20), alt=(0.17, 0.18, 0.17), dust=0.4, wrinkle=9.0)),
    "webbing":       ("plain", dict(color=(0.22, 0.22, 0.19), rough=0.8, dust=0.8)),
    "skin":          ("plain", dict(color=(0.66, 0.47, 0.37), rough=0.55, dust=0.2)),
    "boot":          ("plain", dict(color=(0.07, 0.065, 0.06), rough=0.6, dust=1.2)),
}


def set_reference(obj):
    _ref["obj"] = obj


def stamp(scene):
    """Write the pattern space into every mesh as vertex attributes:
      pcoord  position in metres in pattern space (gun space for parts under the
              reference object, world space for everything static),
      ocoord  position in the object's own space (wood grain, log rings, nets),
      rnd     one random number per object (tone differs from panel to panel).
    Materials read only these, never the object itself, so they give the same
    result when parts are joined and baked to textures for the game.
    Call once after the model is built, with the gun at yaw 0. Curves (hoses)
    are converted to meshes on the way. Terrain objects are skipped."""
    import random

    import numpy as np
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    for obj in [o for o in scene.objects if o.type == "CURVE"]:
        me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
        new = bpy.data.objects.new(obj.name, me)
        for coll in obj.users_collection:
            coll.objects.link(new)
        new.parent = obj.parent
        new.matrix_parent_inverse = obj.matrix_parent_inverse.copy()
        new.matrix_basis = obj.matrix_basis.copy()
        for poly in me.polygons:
            poly.use_smooth = True
        bpy.data.objects.remove(obj)
    bpy.context.view_layer.update()
    ref = _ref["obj"]
    gun = set()
    if ref is not None:
        stack = [ref]
        while stack:
            o = stack.pop()
            gun.add(o)
            stack.extend(o.children)
        ref_inv = ref.matrix_world.inverted()
    rng = random.Random(20261116)
    for obj in sorted(scene.objects, key=lambda o: o.name):
        if obj.type != "MESH" or obj.get("terrain"):
            continue
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        me = obj.data
        n = len(me.vertices)
        co = np.empty(n * 3, np.float32)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        m = np.array((ref_inv @ obj.matrix_world) if obj in gun else obj.matrix_world, np.float32)
        pc = co @ m[:3, :3].T + m[:3, 3]

        def put(name, kind, key, values):
            a = me.attributes.get(name) or me.attributes.new(name, kind, "POINT")
            a.data.foreach_set(key, values)
        put("pcoord", "FLOAT_VECTOR", "vector", pc.ravel())
        put("ocoord", "FLOAT_VECTOR", "vector", co.ravel())
        put("rnd", "FLOAT", "value", np.full(n, rng.random(), np.float32))


def register_decal(name, image_path):
    _decals[name] = image_path


def rgb(c):
    return srgb(*c)


class Graph:
    """Tiny helper so node graphs read like formulas."""

    def __init__(self, mat):
        mat.use_nodes = True
        self.nt = mat.node_tree
        for n in list(self.nt.nodes):
            self.nt.nodes.remove(n)
        self.N, self.L = self.nt.nodes, self.nt.links

    def node(self, kind, **props):
        n = self.N.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def set(self, sock, value):
        if isinstance(value, bpy.types.NodeSocket):
            self.L.new(value, sock)
        elif isinstance(value, (int, float)):
            sock.default_value = value
        else:
            sock.default_value = tuple(value) if len(value) == 4 or sock.type == "VECTOR" \
                else (*value, 1.0)

    def math(self, op, a, b=None, c=None, clamp=False):
        n = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        self.set(n.inputs[0], a)
        if b is not None:
            self.set(n.inputs[1], b)
        if c is not None:
            self.set(n.inputs[2], c)
        return n.outputs[0]

    def ramp(self, value, lo, hi):
        """Smooth 0..1 step between lo and hi (works for lo > hi too)."""
        n = self.node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
        self.set(n.inputs["Value"], value)
        n.inputs["From Min"].default_value = lo
        n.inputs["From Max"].default_value = hi
        return n.outputs["Result"]

    def mix(self, fac, a, b, blend="MIX"):
        n = self.node("ShaderNodeMix", data_type="RGBA", blend_type=blend)
        self.set(n.inputs["Factor"], fac)
        self.set(n.inputs["A"], a)
        self.set(n.inputs["B"], b)
        return n.outputs["Result"]

    def mixf(self, fac, a, b):
        n = self.node("ShaderNodeMix", data_type="FLOAT")
        self.set(n.inputs["Factor"], fac)
        self.set(n.inputs["A"], a)
        self.set(n.inputs["B"], b)
        return n.outputs["Result"]

    def noise(self, vec, scale, detail=4.0, rough=0.55, distortion=0.0):
        n = self.node("ShaderNodeTexNoise")
        self.L.new(vec, n.inputs["Vector"])
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough
        n.inputs["Distortion"].default_value = distortion
        return n.outputs["Fac"]

    def scale_vec(self, vec, s):
        n = self.node("ShaderNodeVectorMath", operation="MULTIPLY")
        self.L.new(vec, n.inputs[0])
        n.inputs[1].default_value = s
        return n.outputs["Vector"]

    def coords(self):
        """Pattern space in metres (vertex attribute written by `stamp`)."""
        return self.node("ShaderNodeAttribute", attribute_name="pcoord").outputs["Vector"]

    def own(self):
        """The object's own space in metres."""
        return self.node("ShaderNodeAttribute", attribute_name="ocoord").outputs["Vector"]

    def rnd(self):
        """One random number per object, 0..1."""
        return self.node("ShaderNodeAttribute", attribute_name="rnd").outputs["Fac"]

    def world(self):
        g = self.node("ShaderNodeNewGeometry")
        sep_n = self.node("ShaderNodeSeparateXYZ")
        self.L.new(g.outputs["Normal"], sep_n.inputs[0])
        sep_p = self.node("ShaderNodeSeparateXYZ")
        self.L.new(g.outputs["Position"], sep_p.inputs[0])
        return g, sep_n.outputs["Z"], sep_p.outputs["Z"]

    def finish(self, color, rough, metallic=0.0, height=None, bump=0.3, bump_dist=0.002,
               alpha=None, coat=0.0):
        out = self.node("ShaderNodeOutputMaterial")
        bsdf = self.node("ShaderNodeBsdfPrincipled")
        bsdf.name = "PBR"
        self.set(bsdf.inputs["Base Color"], color)
        self.set(bsdf.inputs["Roughness"], rough)
        self.set(bsdf.inputs["Metallic"], metallic)
        if coat:
            bsdf.inputs["Coat Weight"].default_value = coat
        if alpha is not None:
            self.set(bsdf.inputs["Alpha"], alpha)
        base_normal = None
        if OPTIONS["bevel_normal"]:
            bev = self.node("ShaderNodeBevel", samples=6)
            bev.inputs["Radius"].default_value = 0.012
            base_normal = bev.outputs["Normal"]
        if height is not None:
            b = self.node("ShaderNodeBump")
            b.inputs["Strength"].default_value = bump
            b.inputs["Distance"].default_value = bump_dist
            self.L.new(height, b.inputs["Height"])
            if base_normal is not None:
                self.L.new(base_normal, b.inputs["Normal"])
            self.L.new(b.outputs["Normal"], bsdf.inputs["Normal"])
        elif base_normal is not None:
            self.L.new(base_normal, bsdf.inputs["Normal"])
        self.L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
        return bsdf


def _dust_mask(g, P, amount):
    """Dust settles on upward faces, in cavities and near the ground (Hsu & Wong);
    dried mud is thrown up onto everything below knee height."""
    _, nz, pz = g.world()
    top = g.ramp(nz, 0.15, 0.95)
    low = g.ramp(pz, 1.5, 0.1)
    ao = g.node("ShaderNodeAmbientOcclusion", samples=4)
    ao.inputs["Distance"].default_value = 0.2
    cavity = g.ramp(ao.outputs["AO"], 0.8, 0.3)
    blotch = g.noise(P, 2.2, detail=7, rough=0.7)
    fine = g.noise(P, 30, detail=3)
    base = g.math("ADD", g.math("MULTIPLY", top, 0.5),
                  g.math("ADD", g.math("MULTIPLY", low, 0.4), g.math("MULTIPLY", cavity, 0.6)))
    var = g.math("ADD", g.math("MULTIPLY", blotch, 1.3), g.math("MULTIPLY", fine, 0.35))
    d = g.math("MULTIPLY", g.math("MULTIPLY", base, var), amount)
    splash = g.math("MULTIPLY", g.ramp(g.noise(P, 11, detail=6, rough=0.75), 0.52, 0.62),
                    g.math("MULTIPLY", g.ramp(pz, 0.95, 0.15), min(amount, 1.0)))
    d = g.math("MAXIMUM", d, g.math("MULTIPLY", splash, 0.9))
    return g.math("MINIMUM", d, 0.92), top, cavity


def _painted(name, color, rough, wear=1.0, dust=1.0, primer=PRIMER, bare=BARE_STEEL,
             soot=0.0):
    mat = bpy.data.materials.new(f"{name}__photoreal")
    g = Graph(mat)
    P = g.coords()
    geo = g.node("ShaderNodeNewGeometry")

    # --- paint: tone differs a little per panel and in large soft patches
    tone = g.math("ADD", 0.84, g.math("MULTIPLY", g.rnd(), 0.32))
    patch = g.math("ADD", 0.82, g.math("MULTIPLY", g.noise(P, 1.3, detail=5, rough=0.6), 0.36))
    paint = g.mix(1.0, rgb(color), g.math("MULTIPLY", tone, patch), "MULTIPLY")

    # --- exposed edges (convex and concave) via the Bevel node
    bev = g.node("ShaderNodeBevel", samples=4)
    bev.inputs["Radius"].default_value = 0.022
    dot = g.node("ShaderNodeVectorMath", operation="DOT_PRODUCT")
    g.L.new(bev.outputs["Normal"], dot.inputs[0])
    g.L.new(geo.outputs["Normal"], dot.inputs[1])
    edge = g.ramp(dot.outputs["Value"], 0.995, 0.86)

    chip_n = g.noise(P, 48, detail=7, rough=0.68)
    scratch = g.ramp(g.noise(P, 14, detail=9, rough=0.75, distortion=0.4), 0.71, 0.76)
    # wear raises edge and scratch damage; the chip noise itself stays put so a
    # heavily worn part is chipped harder, not uniformly stripped
    wearval = g.math("ADD", g.math("MULTIPLY", edge, 0.7 * wear),
                     g.math("ADD", g.math("MULTIPLY", chip_n, 0.75),
                            g.math("ADD", g.math("MULTIPLY", scratch, 0.22 * wear),
                                   0.05 * (wear - 1.0))))
    primer_m = g.ramp(wearval, 0.585, 0.635)
    bare_m = g.ramp(wearval, 0.78, 0.84) if bare else None

    # --- rust streaks: noise stretched along "down", only on steep faces
    _, nz, _ = g.world()
    steep = g.ramp(g.math("ABSOLUTE", nz), 0.75, 0.3)
    streak = g.ramp(g.noise(g.scale_vec(P, (26, 26, 1.4)), 1.0, detail=3), 0.56, 0.82)
    zone = g.ramp(g.noise(P, 0.8, detail=2), 0.48, 0.72)
    rust_m = g.math("MULTIPLY", g.math("MULTIPLY", streak, zone),
                    g.math("MULTIPLY", steep, 0.55 * min(wear, 1.5)))

    dust_m, top, cavity = _dust_mask(g, P, dust)
    if soot:
        paint = g.mix(g.math("MULTIPLY", g.math("ADD", 0.55, g.math("MULTIPLY", g.noise(P, 5, detail=5), 0.6)), soot),
                      paint, (0.012, 0.012, 0.013, 1))

    col = g.mix(rust_m, paint, rgb(RUST))
    # pale wash-down streaks where rain dragged dust down the sides
    wash = g.math("MULTIPLY", g.ramp(g.noise(g.scale_vec(P, (34, 34, 1.1)), 1.0, detail=4), 0.5, 0.75),
                  g.math("MULTIPLY", steep, 0.3 * min(dust, 1.2)))
    col = g.mix(wash, col, rgb(DUST))
    # oily grime collects in corners and around fittings
    grime = g.math("MULTIPLY", cavity, g.math("ADD", 0.3, g.math("MULTIPLY", g.noise(P, 7, detail=5), 0.5)))
    col = g.mix(grime, col, (0.025, 0.022, 0.018, 1))
    # sun fade: upward faces bleach a little
    col = g.mix(g.math("MULTIPLY", top, 0.12), col, (0.5, 0.5, 0.42, 1))
    col = g.mix(primer_m, col, rgb(primer))
    if bare:
        col = g.mix(bare_m, col, rgb(bare))
    col = g.mix(dust_m, col, rgb(DUST))

    r = g.math("ADD", rough, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(P, 38, detail=4), 0.5), 0.18))
    # places polished by hands and boots
    r = g.math("SUBTRACT", r, g.math("MULTIPLY", g.ramp(g.noise(P, 2.7, detail=2), 0.6, 0.8), 0.14))
    r = g.mixf(primer_m, r, 0.75)
    metallic = 0.0
    if bare:
        r = g.mixf(bare_m, r, 0.38)
        metallic = g.math("MULTIPLY", bare_m, g.math("SUBTRACT", 1.0, dust_m))
    r = g.mixf(dust_m, r, 0.95)

    # relief: chips are pits in the paint film, plus a faint orange peel
    h = g.math("SUBTRACT", g.math("MULTIPLY", g.noise(P, 160, detail=2), 0.12),
               g.math("MULTIPLY", primer_m, 0.5))
    g.finish(col, r, metallic, height=h, bump=0.35, bump_dist=0.0015)
    return mat


def _metal(name, color, rough, dust=0.5, rust=0.0):
    mat = bpy.data.materials.new(f"{name}__photoreal")
    g = Graph(mat)
    P = g.coords()
    smudge = g.noise(P, 9, detail=6, rough=0.7, distortion=0.6)
    col = g.mix(1.0, rgb(color), g.math("ADD", 0.82, g.math("MULTIPLY", smudge, 0.36)), "MULTIPLY")
    r = g.math("ADD", rough, g.math("MULTIPLY", g.math("SUBTRACT", smudge, 0.5), 0.3))
    metallic = 1.0
    dust_m, _, cavity = _dust_mask(g, P, dust)
    if rust:
        rm = g.math("MULTIPLY", g.ramp(g.noise(P, 6, detail=8, rough=0.7), 0.5, 0.68), rust)
        col = g.mix(rm, col, rgb(RUST))
        r = g.mixf(rm, r, 0.8)
        metallic = g.math("SUBTRACT", 1.0, g.math("MAXIMUM", rm, dust_m))
    else:
        metallic = g.math("SUBTRACT", 1.0, dust_m)
    col = g.mix(dust_m, col, rgb(DUST))
    r = g.mixf(dust_m, r, 0.95)
    g.finish(col, r, metallic, height=g.noise(P, 90, detail=3), bump=0.1, bump_dist=0.001)
    return mat


def _plain(name, color, rough, dust=1.0):
    mat = bpy.data.materials.new(f"{name}__photoreal")
    g = Graph(mat)
    P = g.coords()
    dust_m, _, cavity = _dust_mask(g, P, dust)
    var = g.math("ADD", 0.85, g.math("MULTIPLY", g.noise(P, 20, detail=4), 0.3))
    col = g.mix(dust_m, g.mix(1.0, rgb(color), var, "MULTIPLY"), rgb(DUST))
    g.finish(col, g.mixf(dust_m, rough, 0.95), 0.0, height=g.noise(P, 120, detail=3),
             bump=0.15, bump_dist=0.001)
    return mat


def _wood(name, color):
    """Raw sawn softwood (crate battens, tool handles). Grain runs along local Y."""
    mat = bpy.data.materials.new(f"{name}__photoreal")
    g = Graph(mat)
    off = g.node("ShaderNodeVectorMath", operation="ADD")
    g.L.new(g.own(), off.inputs[0])
    g.L.new(g.rnd(), off.inputs[1])
    P = off.outputs["Vector"]
    grain = g.noise(g.scale_vec(P, (90, 4, 90)), 1.0, detail=5, rough=0.6, distortion=1.5)
    rings = g.noise(g.scale_vec(P, (14, 1.2, 14)), 1.0, detail=2, distortion=3.0)
    v = g.math("ADD", 0.72, g.math("ADD", g.math("MULTIPLY", grain, 0.3), g.math("MULTIPLY", rings, 0.3)))
    col = g.mix(1.0, rgb(color), v, "MULTIPLY")
    # weathered grey on top, dust
    Pw = g.coords()
    dust_m, top, _ = _dust_mask(g, Pw, 0.9)
    col = g.mix(g.math("MULTIPLY", top, 0.25), col, (0.35, 0.33, 0.3, 1))
    col = g.mix(dust_m, col, rgb(DUST))
    g.finish(col, 0.82, 0.0, height=grain, bump=0.5, bump_dist=0.002)
    return mat


def _stone(name):
    mat = bpy.data.materials.new(f"{name}__photoreal")
    g = Graph(mat)
    tc = g.node("ShaderNodeTexCoord")
    info = g.node("ShaderNodeObjectInfo")
    P = tc.outputs["Object"]
    n = g.noise(P, 30, detail=6, rough=0.7)
    a = g.mix(info.outputs["Random"], rgb((0.60, 0.53, 0.42)), rgb((0.40, 0.36, 0.31)))
    col = g.mix(1.0, a, g.math("ADD", 0.7, g.math("MULTIPLY", n, 0.6)), "MULTIPLY")
    _, nz, _ = g.world()
    col = g.mix(g.ramp(nz, 0.9, -0.2), col, rgb(DUST))   # soil clings to the lower half
    g.finish(col, 0.9, 0.0, height=n, bump=0.6, bump_dist=0.004)
    return mat


def _dirt(name, masks=True):
    """Dry, compacted soil of a firing position. World-space, real scale.
    Vertex colour "masks": R wheel ruts, G trampled ground, B grass cover,
    A opacity (sprites carry a soil patch that fades out at its edge).
    masks=False: plain soil for heaps and barrier fill (no vertex data needed)."""
    mat = bpy.data.materials.new(f"{name}__photoreal")
    g = Graph(mat)
    geo = g.node("ShaderNodeNewGeometry")
    P = geo.outputs["Position"]
    rut = tramp = cover = 0.0
    alpha = None
    if masks:
        att = g.node("ShaderNodeAttribute", attribute_name="masks")
        sep = g.node("ShaderNodeSeparateColor")
        g.L.new(att.outputs["Color"], sep.inputs[0])
        rut, tramp, cover = sep.outputs[0], sep.outputs[1], sep.outputs[2]
        alpha = att.outputs["Alpha"]

    macro = g.noise(P, 0.16, detail=3, rough=0.5)
    large = g.noise(P, 0.55, detail=9, rough=0.72)
    med = g.noise(P, 3.1, detail=8, rough=0.7)
    fine = g.noise(P, 34, detail=6, rough=0.8)
    grit = g.noise(P, 170, detail=3, rough=0.8)
    dry, dark, pale = rgb((0.60, 0.50, 0.36)), rgb((0.40, 0.32, 0.22)), rgb((0.74, 0.66, 0.52))
    humus, red = rgb((0.27, 0.22, 0.14)), rgb((0.58, 0.42, 0.28))
    t = g.math("ADD", g.math("MULTIPLY", large, 0.6), g.math("MULTIPLY", med, 0.4))
    col = g.mix(g.ramp(t, 0.38, 0.62), dark, dry)
    col = g.mix(g.math("MULTIPLY", g.ramp(macro, 0.45, 0.7), 0.45), col, red)      # ochre areas
    col = g.mix(g.math("MULTIPLY", g.ramp(fine, 0.48, 0.75), 0.5), col, pale)
    # trampled ground: paler, powdery; turf: dark humus between the blades
    col = g.mix(g.math("MULTIPLY", tramp, g.math("ADD", 0.25, g.math("MULTIPLY", med, 0.5))), col, pale)
    col = g.mix(g.math("MULTIPLY", cover, 0.8), col, humus)
    # ruts: damp compacted earth
    col = g.mix(g.math("MULTIPLY", rut, 0.6), col, dark)
    # gravel: small light and dark grains
    vor = g.node("ShaderNodeTexVoronoi", feature="F1")
    g.L.new(P, vor.inputs["Vector"])
    vor.inputs["Scale"].default_value = 95
    pebble = g.math("MULTIPLY", g.ramp(vor.outputs["Distance"], 0.3, 0.14),
                    g.ramp(g.noise(P, 4.5, detail=4), 0.42, 0.62))
    sepv = g.node("ShaderNodeSeparateColor")
    g.L.new(vor.outputs["Color"], sepv.inputs[0])
    col = g.mix(g.math("MULTIPLY", pebble, 0.85), col,
                g.mix(sepv.outputs[0], rgb((0.30, 0.27, 0.23)), rgb((0.78, 0.72, 0.62))))
    # clods: crumbly relief with dark gaps between them
    clod = g.node("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
    g.L.new(P, clod.inputs["Vector"])
    clod.inputs["Scale"].default_value = 26
    gap = g.math("MULTIPLY", g.ramp(clod.outputs["Distance"], 0.06, 0.0),
                 g.ramp(g.noise(P, 2.2, detail=3), 0.4, 0.6))
    col = g.mix(g.math("MULTIPLY", gap, 0.45), col, dark)
    col = g.mix(1.0, col, g.math("ADD", 0.78, g.math("MULTIPLY", grit, 0.44)), "MULTIPLY")
    h = g.math("ADD", g.math("MULTIPLY", fine, 0.5),
               g.math("ADD", g.math("MULTIPLY", grit, 0.2),
                      g.math("SUBTRACT", g.math("MULTIPLY", pebble, 0.5), g.math("MULTIPLY", gap, 0.5))))
    g.finish(col, g.mixf(rut, 0.94, 0.72), 0.0, height=h, bump=1.0, bump_dist=0.025, alpha=alpha)
    return mat


def _grass(name):
    mat = bpy.data.materials.new(f"{name}__photoreal")
    g = Graph(mat)
    info = g.node("ShaderNodeObjectInfo")
    tc = g.node("ShaderNodeTexCoord")
    sep = g.node("ShaderNodeSeparateXYZ")
    g.L.new(tc.outputs["Object"], sep.inputs[0])
    green, straw = rgb((0.33, 0.40, 0.16)), rgb((0.70, 0.62, 0.36))
    col = g.mix(g.ramp(info.outputs["Random"], 0.2, 0.9), green, straw)
    col = g.mix(g.ramp(sep.outputs["Z"], 0.3, 1.0), col, straw)      # tips dry out first
    out = g.node("ShaderNodeOutputMaterial")
    bsdf = g.node("ShaderNodeBsdfPrincipled")
    g.L.new(col, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.6
    tr = g.node("ShaderNodeBsdfTranslucent")
    g.L.new(col, tr.inputs["Color"])
    mix = g.node("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.3
    g.L.new(bsdf.outputs["BSDF"], mix.inputs[1])
    g.L.new(tr.outputs["BSDF"], mix.inputs[2])
    g.L.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


def _bore(name):
    mat = bpy.data.materials.new(f"{name}__photoreal")
    g = Graph(mat)
    g.finish((0.004, 0.004, 0.004, 1), 0.9)
    return mat


def _decal(name):
    """White stencil paint: an image used as a mask, slightly worn and dusty."""
    mat = bpy.data.materials.new(f"{name}__photoreal")
    g = Graph(mat)
    tex = g.node("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(_decals[name])
    tex.extension = "CLIP"
    P = g.coords()
    worn = g.ramp(g.noise(P, 40, detail=6, rough=0.7), 0.38, 0.5)
    alpha = g.math("MULTIPLY", tex.outputs["Color"], g.math("MULTIPLY", worn, 0.9))
    g.finish(rgb((0.78, 0.77, 0.72)), 0.7, alpha=alpha)
    return mat



def _cloth(name, color, alt=None, dust=0.7, translucent=0.0, wrinkle=18.0):
    """Woven cloth (sandbag hessian, flags). Tone differs from piece to piece."""
    mat = bpy.data.materials.new(f"{name}__photoreal")
    g = Graph(mat)
    P = g.coords()
    rnd = g.rnd()
    tone = g.math("ADD", 0.72, g.math("MULTIPLY", rnd, 0.45))
    col = g.mix(1.0, rgb(color), tone, "MULTIPLY")
    if alt:     # every few pieces come from another batch: other dye, more weathered
        rnd2 = g.math("FRACT", g.math("MULTIPLY", rnd, 7.31))
        col = g.mix(g.ramp(rnd2, 0.62, 0.7), col, g.mix(1.0, rgb(alt), tone, "MULTIPLY"))
    stain = g.noise(P, 7, detail=5, rough=0.7)
    col = g.mix(g.math("MULTIPLY", g.ramp(stain, 0.5, 0.75), 0.35), col, (0.10, 0.08, 0.06, 1))
    _, nz, pz = g.world()
    if dust:
        damp = g.ramp(pz, 0.22, 0.02)                       # wicks moisture from the ground
        col = g.mix(g.math("MULTIPLY", damp, 0.45), col, rgb((0.30, 0.24, 0.17)))
        dust_m, _, _ = _dust_mask(g, P, dust)
        col = g.mix(dust_m, col, rgb(DUST))
    weave = g.noise(P, 220, detail=2)
    wr = g.noise(P, wrinkle, detail=4, rough=0.6)
    h = g.math("ADD", g.math("MULTIPLY", wr, 0.8), g.math("MULTIPLY", weave, 0.2))
    bsdf = g.finish(col, 0.92, 0.0, height=h, bump=0.5, bump_dist=0.012)
    bsdf.inputs["Sheen Weight"].default_value = 0.3
    if translucent:
        out = next(n for n in g.N if n.bl_idname == "ShaderNodeOutputMaterial")
        tr = g.node("ShaderNodeBsdfTranslucent")
        g.L.new(col, tr.inputs["Color"])
        mix = g.node("ShaderNodeMixShader")
        mix.inputs["Fac"].default_value = translucent
        g.L.new(bsdf.outputs["BSDF"], mix.inputs[1])
        g.L.new(tr.outputs["BSDF"], mix.inputs[2])
        g.L.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


def _geotextile(name):
    """HESCO-type barrier: felt liner behind a welded 76 mm galvanised mesh.
    Expects a 1 m wide unit centred on its own Z axis."""
    mat = bpy.data.materials.new(f"{name}__photoreal")
    g = Graph(mat)
    P = g.coords()
    felt = g.noise(P, 5, detail=6, rough=0.7)
    col = g.mix(1.0, rgb((0.68, 0.65, 0.57)), g.math("ADD", 0.76, g.math("MULTIPLY", felt, 0.42)),
                "MULTIPLY")
    _, nz, pz = g.world()
    low = g.ramp(pz, 0.6, 0.0)                              # soil splashed up from the ground
    col = g.mix(g.math("MULTIPLY", low, g.math("ADD", 0.25, g.math("MULTIPLY", felt, 0.7))), col,
                rgb((0.48, 0.40, 0.29)))
    streak = g.ramp(g.noise(g.scale_vec(P, (9, 9, 0.8)), 1.0, detail=3), 0.55, 0.8)
    col = g.mix(g.math("MULTIPLY", streak, 0.3), col, rgb((0.36, 0.30, 0.22)))
    sp = g.node("ShaderNodeSeparateXYZ")
    g.L.new(g.own(), sp.inputs[0])

    def wire(sock):
        fr = g.math("FRACT", g.math("ADD", g.math("MULTIPLY", sock, 13.12), 100.5))
        return g.math("LESS_THAN", fr, 0.09)
    # a side face is the one whose own x (or y) sits at the unit's skin
    on_x = g.math("GREATER_THAN", g.math("ABSOLUTE", sp.outputs["X"]), 0.44)
    upright = g.math("MAXIMUM", g.math("MULTIPLY", wire(sp.outputs["Y"]), on_x),
                     g.math("MULTIPLY", wire(sp.outputs["X"]), g.math("SUBTRACT", 1.0, on_x)))
    line = g.math("MAXIMUM", wire(sp.outputs["Z"]), upright)
    col = g.mix(line, col, rgb((0.43, 0.44, 0.45)))
    h = g.math("ADD", g.math("MULTIPLY", felt, 0.5), line)
    g.finish(col, g.mixf(line, 0.92, 0.45), g.math("MULTIPLY", line, 0.8), height=h, bump=0.5,
             bump_dist=0.006)
    return mat


def _concrete(name):
    """Cast concrete hardstanding: 2.5 m bays, joints, hairline cracks, oil, drifted soil."""
    mat = bpy.data.materials.new(f"{name}__photoreal")
    g = Graph(mat)
    geo = g.node("ShaderNodeNewGeometry")
    P = geo.outputs["Position"]
    sp = g.node("ShaderNodeSeparateXYZ")
    g.L.new(P, sp.inputs[0])
    large = g.noise(P, 0.35, detail=6, rough=0.65)
    med = g.noise(P, 4, detail=7, rough=0.7)
    speck = g.noise(P, 260, detail=2)
    v = g.math("ADD", 0.72, g.math("ADD", g.math("MULTIPLY", large, 0.3), g.math("MULTIPLY", med, 0.24)))
    col = g.mix(1.0, rgb((0.62, 0.61, 0.58)), v, "MULTIPLY")
    drift = g.ramp(g.noise(P, 0.9, detail=6, rough=0.72), 0.46, 0.74)
    col = g.mix(g.math("MULTIPLY", drift, 0.6), col, rgb(DUST))
    stain = g.ramp(g.noise(P, 1.6, detail=4, rough=0.6, distortion=0.8), 0.64, 0.74)
    col = g.mix(g.math("MULTIPLY", stain, 0.6), col, (0.03, 0.028, 0.025, 1))
    joint = None
    for axis in "XY":
        fr = g.math("FRACT", g.math("ADD", g.math("MULTIPLY", sp.outputs[axis], 0.4), 100.5))
        j = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", fr, 0.5)), 0.0042, 0.0018)
        joint = j if joint is None else g.math("MAXIMUM", joint, j)
    col = g.mix(g.math("MULTIPLY", joint, 0.85), col, (0.02, 0.02, 0.02, 1))
    vor = g.node("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
    warp = g.node("ShaderNodeVectorMath", operation="ADD")
    g.L.new(P, warp.inputs[0])
    wn = g.node("ShaderNodeTexNoise")
    g.L.new(P, wn.inputs["Vector"])
    wn.inputs["Scale"].default_value = 1.5
    g.L.new(wn.outputs["Color"], warp.inputs[1])
    g.L.new(warp.outputs["Vector"], vor.inputs["Vector"])
    vor.inputs["Scale"].default_value = 0.8
    crack = g.math("MULTIPLY", g.ramp(vor.outputs["Distance"], 0.007, 0.0),
                   g.ramp(g.noise(P, 0.45, detail=2), 0.45, 0.58))
    col = g.mix(g.math("MULTIPLY", crack, 0.75), col, (0.03, 0.03, 0.03, 1))
    col = g.mix(1.0, col, g.math("ADD", 0.9, g.math("MULTIPLY", speck, 0.2)), "MULTIPLY")
    h = g.math("SUBTRACT", g.math("ADD", g.math("MULTIPLY", speck, 0.3), g.math("MULTIPLY", med, 0.3)),
               g.math("ADD", joint, g.math("MULTIPLY", crack, 0.6)))
    g.finish(col, g.mixf(stain, 0.86, 0.5), 0.0, height=h, bump=0.6, bump_dist=0.004)
    return mat


def _log(name):
    """Round timber standing on end: furrowed bark on the side, growth rings on the cut."""
    mat = bpy.data.materials.new(f"{name}__photoreal")
    g = Graph(mat)
    P = g.coords()
    rnd = g.rnd()
    sp = g.node("ShaderNodeSeparateXYZ")
    g.L.new(g.own(), sp.inputs[0])
    _, nz, _ = g.world()                                    # logs stand upright
    bark = g.noise(g.scale_vec(P, (55, 55, 3.5)), 1.0, detail=5, rough=0.65, distortion=0.6)
    bcol = g.mix(g.ramp(bark, 0.35, 0.72), rgb((0.20, 0.15, 0.11)), rgb((0.47, 0.41, 0.33)))
    bcol = g.mix(1.0, bcol, g.math("ADD", 0.8, g.math("MULTIPLY", rnd, 0.4)), "MULTIPLY")
    r = g.math("SQRT", g.math("ADD", g.math("POWER", sp.outputs["X"], 2.0),
                              g.math("POWER", sp.outputs["Y"], 2.0)))
    rings = g.math("SINE", g.math("ADD", g.math("MULTIPLY", r, 230.0),
                                  g.math("MULTIPLY", g.noise(P, 20, detail=2), 5.0)))
    ecol = g.mix(g.ramp(rings, -0.4, 0.6), rgb((0.52, 0.40, 0.25)), rgb((0.76, 0.64, 0.44)))
    ecol = g.mix(g.math("MULTIPLY", rnd, 0.6), ecol, rgb((0.47, 0.45, 0.42)))
    end = g.ramp(g.math("ABSOLUTE", nz), 0.6, 0.9)
    col = g.mix(end, bcol, ecol)
    dust_m, _, _ = _dust_mask(g, P, 0.6)
    col = g.mix(dust_m, col, rgb(DUST))
    h = g.mixf(end, bark, g.math("MULTIPLY", rings, 0.15))
    g.finish(col, 0.9, 0.0, height=h, bump=0.9, bump_dist=0.012)
    return mat


def _camo_net(name):
    """Camouflage net: a 7 cm mesh garnished with leaf-cut scrim, about 60 % cover.
    Alpha cut-out, so the sun shines through and dapples whatever is underneath."""
    mat = bpy.data.materials.new(f"{name}__photoreal")
    g = Graph(mat)
    P = g.own()
    vor = g.node("ShaderNodeTexVoronoi", feature="F1", voronoi_dimensions="2D")
    g.L.new(P, vor.inputs["Vector"])
    vor.inputs["Scale"].default_value = 11.0
    sc = g.node("ShaderNodeSeparateColor")
    g.L.new(vor.outputs["Color"], sc.inputs[0])
    present = g.math("GREATER_THAN", sc.outputs[0], 0.25)
    leaf = g.ramp(vor.outputs["Distance"], 0.6, 0.48)
    torn = g.ramp(g.noise(P, 3.5, detail=3), 0.3, 0.42)
    garnish = g.math("MULTIPLY", g.math("MULTIPLY", present, leaf), torn)
    sp = g.node("ShaderNodeSeparateXYZ")
    g.L.new(P, sp.inputs[0])
    line = None
    for axis in "XY":
        fr = g.math("FRACT", g.math("ADD", g.math("MULTIPLY", sp.outputs[axis], 14.3), 100.0))
        on = g.math("LESS_THAN", fr, 0.08)
        line = on if line is None else g.math("MAXIMUM", line, on)
    alpha = g.math("MAXIMUM", garnish, g.math("MULTIPLY", line, 0.7))
    blot = g.noise(P, 0.9, detail=3, rough=0.5)
    c = g.mix(g.ramp(blot, 0.42, 0.5), rgb((0.17, 0.22, 0.12)), rgb((0.36, 0.37, 0.21)))
    c = g.mix(g.ramp(g.noise(P, 1.7, detail=2), 0.57, 0.63), c, rgb((0.37, 0.28, 0.18)))
    c = g.mix(1.0, c, g.math("ADD", 0.7, g.math("MULTIPLY", sc.outputs[1], 0.6)), "MULTIPLY")
    c = g.mix(g.math("MULTIPLY", line, g.math("SUBTRACT", 1.0, garnish)), c, rgb((0.10, 0.12, 0.08)))
    g.finish(c, 0.85, 0.0, alpha=alpha)
    return mat


def _screen(name):
    """Powered-on rugged display: dark glass with a faint green glow."""
    mat = bpy.data.materials.new(f"{name}__photoreal")
    g = Graph(mat)
    bsdf = g.finish((0.01, 0.02, 0.012, 1), 0.08)
    bsdf.inputs["Emission Color"].default_value = (0.25, 0.9, 0.4, 1)
    bsdf.inputs["Emission Strength"].default_value = 60.0
    return mat


_BUILDERS = {"painted": _painted, "metal": _metal, "plain": _plain, "wood": _wood,
             "stone": _stone, "dirt": _dirt, "grass": _grass, "bore": _bore, "cloth": _cloth,
             "geotextile": _geotextile, "concrete": _concrete, "log": _log, "camo_net": _camo_net,
             "screen": _screen}


def build(name):
    if name in _decals:
        return _decal(name)
    kind, kw = SPEC[name]
    return _BUILDERS[kind](name, **kw)
