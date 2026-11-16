"""Shared material library.

One palette (the game's colour identity) and two treatments of it:
- "stylized": saturated, soft, chunky, dark outline (Clash-of-Clans-like read).
- "realistic": same hues, physically based surfaces with grain, wear and bump.
Models never create materials themselves; they ask for one by name here.
"""
import bpy


def srgb(r, g, b):
    """Palette is written in sRGB (what a designer would pick); Blender wants linear."""
    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (lin(r), lin(g), lin(b), 1.0)


# name: (sRGB colour, metallic, base roughness, realistic noise scale)
PALETTE = {
    "wood":       ((0.62, 0.38, 0.20), 0.0, 0.70, 18.0),
    "wood_dark":  ((0.42, 0.25, 0.13), 0.0, 0.75, 18.0),
    "stone":      ((0.66, 0.64, 0.60), 0.0, 0.85, 6.0),
    "stone_dark": ((0.46, 0.45, 0.44), 0.0, 0.85, 6.0),
    "iron":       ((0.26, 0.27, 0.30), 1.0, 0.45, 30.0),
    "steel_dark": ((0.20, 0.23, 0.30), 1.0, 0.32, 30.0),
    "brass":      ((0.86, 0.62, 0.28), 1.0, 0.30, 30.0),
    "gold":       ((1.00, 0.78, 0.30), 1.0, 0.22, 30.0),
    "rope":       ((0.70, 0.56, 0.36), 0.0, 0.90, 40.0),
    # Faction accent: Strelite crimson. Used sparingly so it signals "ours".
    "accent":     ((0.78, 0.10, 0.12), 0.0, 0.65, 25.0),
    "bore":       ((0.02, 0.02, 0.02), 0.0, 0.90, 10.0),
}

OUTLINE_COLOR = srgb(0.10, 0.06, 0.05)

_cache = {}


def _nodes(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    return nt, nt.nodes, nt.links


def _stylized(name, color, metallic, rough):
    mat = bpy.data.materials.new(f"{name}__stylized")
    nt, N, L = _nodes(mat)
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    # Push saturation/brightness up a touch for the toy-like read.
    hsv = N.new("ShaderNodeHueSaturation")
    hsv.inputs["Saturation"].default_value = 1.2
    hsv.inputs["Value"].default_value = 1.05
    hsv.inputs["Color"].default_value = srgb(*color)
    # Ambient occlusion darkens crevices: cheap "hand-painted" depth.
    ao = N.new("ShaderNodeAmbientOcclusion")
    ao.inputs["Distance"].default_value = 0.15
    ao.samples = 8
    mix = N.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 0.55
    L.new(hsv.outputs["Color"], mix.inputs["A"])
    L.new(ao.outputs["AO"], mix.inputs["B"])
    L.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = metallic * 0.7
    bsdf.inputs["Roughness"].default_value = 0.42 if metallic else max(rough, 0.6)
    if metallic:
        bsdf.inputs["Coat Weight"].default_value = 0.15
        bsdf.inputs["Coat Roughness"].default_value = 0.3
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def _realistic(name, color, metallic, rough, scale):
    mat = bpy.data.materials.new(f"{name}__realistic")
    nt, N, L = _nodes(mat)
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    coord = N.new("ShaderNodeTexCoord")

    base = srgb(*color)
    # Large-scale colour variation (dirt, weathering).
    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale * 0.25
    noise.inputs["Detail"].default_value = 6
    L.new(coord.outputs["Object"], noise.inputs["Vector"])
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.3
    ramp.color_ramp.elements[0].color = tuple(c * 0.6 for c in base[:3]) + (1,)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = tuple(min(1, c * 1.0) for c in base[:3]) + (1,)
    L.new(noise.outputs["Fac"], ramp.inputs["Fac"])

    detail_src = noise
    if name.startswith("wood"):
        # Grain: stretched wave bands.
        wave = N.new("ShaderNodeTexWave")
        wave.inputs["Scale"].default_value = 6
        wave.inputs["Distortion"].default_value = 8
        wave.inputs["Detail"].default_value = 4
        wave.bands_direction = "Z"
        L.new(coord.outputs["Object"], wave.inputs["Vector"])
        mixw = N.new("ShaderNodeMix")
        mixw.data_type = "RGBA"
        mixw.blend_type = "MULTIPLY"
        mixw.inputs["Factor"].default_value = 0.35
        L.new(ramp.outputs["Color"], mixw.inputs["A"])
        L.new(wave.outputs["Color"], mixw.inputs["B"])
        L.new(mixw.outputs["Result"], bsdf.inputs["Base Color"])
        detail_src = wave
    elif name.startswith("stone"):
        vor = N.new("ShaderNodeTexVoronoi")
        vor.inputs["Scale"].default_value = scale
        L.new(coord.outputs["Object"], vor.inputs["Vector"])
        mixs = N.new("ShaderNodeMix")
        mixs.data_type = "RGBA"
        mixs.blend_type = "MULTIPLY"
        mixs.inputs["Factor"].default_value = 0.25
        L.new(ramp.outputs["Color"], mixs.inputs["A"])
        L.new(vor.outputs["Distance"], mixs.inputs["B"])
        L.new(mixs.outputs["Result"], bsdf.inputs["Base Color"])
        detail_src = vor
    else:
        L.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])

    # Roughness variation (scratches / patina).
    rnoise = N.new("ShaderNodeTexNoise")
    rnoise.inputs["Scale"].default_value = scale
    rnoise.inputs["Detail"].default_value = 8
    L.new(coord.outputs["Object"], rnoise.inputs["Vector"])
    rmap = N.new("ShaderNodeMapRange")
    rmap.inputs["To Min"].default_value = max(0.05, rough - 0.15)
    rmap.inputs["To Max"].default_value = min(1.0, rough + 0.2)
    L.new(rnoise.outputs["Fac"], rmap.inputs["Value"])
    L.new(rmap.outputs["Result"], bsdf.inputs["Roughness"])
    bsdf.inputs["Metallic"].default_value = metallic

    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25 if metallic else 0.5
    bump.inputs["Distance"].default_value = 0.01
    key = "Distance" if name.startswith("stone") else ("Color" if name.startswith("wood") else "Fac")
    src_out = detail_src.outputs[key] if key in detail_src.outputs else detail_src.outputs[0]
    L.new(src_out, bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def _bore(style):
    mat = bpy.data.materials.new(f"bore__{style}")
    nt, N, L = _nodes(mat)
    out = N.new("ShaderNodeOutputMaterial")
    em = N.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.005, 0.004, 0.004, 1)
    L.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat


def get(name, style):
    key = (name, style)
    if key in _cache and _cache[key].name in bpy.data.materials:
        return _cache[key]
    color, metallic, rough, scale = PALETTE[name]
    if name == "bore":
        mat = _bore(style)
    elif style == "stylized":
        mat = _stylized(name, color, metallic, rough)
    else:
        mat = _realistic(name, color, metallic, rough, scale)
    _cache[key] = mat
    return mat


def outline_material():
    """Inverted-hull outline: dark on hull back faces, invisible elsewhere and to shadows."""
    if "outline" in bpy.data.materials:
        return bpy.data.materials["outline"]
    mat = bpy.data.materials.new("outline")
    nt, N, L = _nodes(mat)
    out = N.new("ShaderNodeOutputMaterial")
    geo = N.new("ShaderNodeNewGeometry")
    lp = N.new("ShaderNodeLightPath")
    inv = N.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    L.new(lp.outputs["Is Camera Ray"], inv.inputs[1])
    mx = N.new("ShaderNodeMath")
    mx.operation = "MAXIMUM"
    L.new(geo.outputs["Backfacing"], mx.inputs[0])
    L.new(inv.outputs["Value"], mx.inputs[1])
    em = N.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = OUTLINE_COLOR
    tr = N.new("ShaderNodeBsdfTransparent")
    mix = N.new("ShaderNodeMixShader")
    L.new(mx.outputs["Value"], mix.inputs["Fac"])
    L.new(em.outputs["Emission"], mix.inputs[1])
    L.new(tr.outputs["BSDF"], mix.inputs[2])
    L.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


def clear_cache():
    _cache.clear()
