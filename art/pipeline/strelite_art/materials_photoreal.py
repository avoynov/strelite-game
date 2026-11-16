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

# Reference object whose space the 3D patterns live in (the rotating gun), so
# wear does not swim when the gun turns. Set by the model before materials are made.
_ref = {"obj": None}
# name -> image path for stencil decals (white paint through a stencil).
_decals = {}

DUST = (0.62, 0.53, 0.40)       # sRGB, dry soil dust; matches the terrain
PRIMER = (0.42, 0.17, 0.12)     # red-oxide primer
RUST = (0.33, 0.16, 0.08)
BARE_STEEL = (0.56, 0.57, 0.58)

# name: (builder, kwargs)
OLIVE = (0.34, 0.35, 0.24)      # FS 34087 olive drab
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
}


def set_reference(obj):
    _ref["obj"] = obj


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
        tc = self.node("ShaderNodeTexCoord")
        if _ref["obj"] is not None:
            tc.object = _ref["obj"]
        return tc.outputs["Object"]

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
        self.set(bsdf.inputs["Base Color"], color)
        self.set(bsdf.inputs["Roughness"], rough)
        self.set(bsdf.inputs["Metallic"], metallic)
        if coat:
            bsdf.inputs["Coat Weight"].default_value = coat
        if alpha is not None:
            self.set(bsdf.inputs["Alpha"], alpha)
        if height is not None:
            b = self.node("ShaderNodeBump")
            b.inputs["Strength"].default_value = bump
            b.inputs["Distance"].default_value = bump_dist
            self.L.new(height, b.inputs["Height"])
            self.L.new(b.outputs["Normal"], bsdf.inputs["Normal"])
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
    info = g.node("ShaderNodeObjectInfo")
    geo = g.node("ShaderNodeNewGeometry")

    # --- paint: tone differs a little per panel and in large soft patches
    tone = g.math("ADD", 0.84, g.math("MULTIPLY", info.outputs["Random"], 0.32))
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
    tc = g.node("ShaderNodeTexCoord")
    info = g.node("ShaderNodeObjectInfo")
    off = g.node("ShaderNodeVectorMath", operation="ADD")
    g.L.new(tc.outputs["Object"], off.inputs[0])
    g.L.new(info.outputs["Random"], off.inputs[1])
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


def _dirt(name):
    """Dry, compacted soil of a firing position. World-space, real scale.
    Vertex colour "masks": R wheel ruts, G trampled ground, B grass cover."""
    mat = bpy.data.materials.new(f"{name}__photoreal")
    g = Graph(mat)
    geo = g.node("ShaderNodeNewGeometry")
    P = geo.outputs["Position"]
    att = g.node("ShaderNodeAttribute", attribute_name="masks")
    sep = g.node("ShaderNodeSeparateColor")
    g.L.new(att.outputs["Color"], sep.inputs[0])
    rut, tramp, cover = sep.outputs[0], sep.outputs[1], sep.outputs[2]

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
    g.finish(col, g.mixf(rut, 0.94, 0.72), 0.0, height=h, bump=1.0, bump_dist=0.025)
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


_BUILDERS = {"painted": _painted, "metal": _metal, "plain": _plain, "wood": _wood,
             "stone": _stone, "dirt": _dirt, "grass": _grass, "bore": _bore}


def build(name):
    if name in _decals:
        return _decal(name)
    kind, kw = SPEC[name]
    return _BUILDERS[kind](name, **kw)
