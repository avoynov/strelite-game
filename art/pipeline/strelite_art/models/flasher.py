"""Шеметофар (game id flasher): a searchlight that blinds and stuns with a cone of light, no
damage. A lamp head on a fork, its face to the enemy, raised a little. Front is local +Y.

Look per level (sketch v4, approved 2026-11-22):
  1  one bare lime-light bulb in a light leather shade on a small iron lamp house; a log
     sledge with a plank turntable; leather gas bags strapped behind
  2  no shade: four open bulbs on a brass cross with a concave mirror behind them;
     a two-wheel cart with a drawbar
  3  the drum: a riveted olive drum with a Fresnel lens and louvre slats worked by a cam;
     cruciform outriggers on screw-jack feet
  4  blackened steel and bronze; a ring of six magnesium flash trays round the face;
     a low armoured pedestal
  5  silver and gold; a coloured filter wheel beside the face; a marble octagon with a
     gilded azimuth ring
Ammo pile beside it: lime and gas, gas bottles, carbon rods and accumulators, magnesium
ribbon and powder, a lacquered case of coloured glasses.

Returns (root, turret). The base is static; the fork and head turn.
Firing animation: the flash. The glowing parts swell for a frame and settle back; the light
cone itself is an effect.
"""
import math

import bpy
from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit
from .trebuchet import _ball

LEVELS = (1, 2, 3, 4, 5)
FRAME_M = 8.0
TARGET_Z = 1.2
SPRITE_FRAME_M = 9.0
SWEEP_M = 1.9
FOOTPRINT_M = 3.0        # 2x2 tiles of 4 m
EL = math.radians(12)    # the head looks a little up

STYLE = {
    1: dict(arm="timber_raw", fit="iron_forged", base="log", deck="timber_raw", band="iron_forged"),
    2: dict(arm="timber_tarred", fit="brass", base="timber_tarred", deck="brass", band="brass"),
    3: dict(arm="paint_olive", fit="steel_worn", base="paint_olive_worn", deck="paint_olive", band="steel_worn",
            drum="paint_olive"),
    4: dict(arm="iron_black", fit="bronze_old", base="iron_black", deck="bronze_old", band="bronze_old",
            drum="iron_black"),
    5: dict(arm="silver_satin", fit="gold_trim", base="stone_pale", deck="gold_trim", band="gold_trim",
            drum="silver_satin"),
}
R_DRUM = {3: 0.66, 4: 0.7, 5: 0.72}
DECK_Z = {1: 0.5, 2: 0.78, 3: 0.66, 4: 0.72, 5: 0.6}

FIRE = [1.9, 1.45, 1.15, 1.0]        # glow scale per frame after the trigger
FIRE_FRAMES = len(FIRE)
RELEASE_FRAME = 1
RELOAD_FROM = 3
FIRE_FPS = 12
LOOP = False
_RIG = {}

ROT_Y = (-math.pi / 2, 0, 0)         # Kit cylinder (+Z) turned to point along +Y
ROT_TY = (math.pi / 2, 0, 0)         # Kit torus (around Z) turned to ring the +Y axis


def build(style, level=1):
    k = Kit(style)
    s = STYLE[level]
    _RIG.clear()
    _RIG["glow"] = []
    root = k.empty("flasher")
    zb = _base(k, root, level, s)
    _ammo(k, root, level, s)
    turret = k.empty("turret", (0, 0, 0), parent=root)
    turret["node"] = "turret"
    mp.set_reference(turret)
    zc = zb + (1.05 if level <= 2 else 0.5 + R_DRUM[level] + 0.42)
    fx = {1: 0.6, 2: 0.82}.get(level, R_DRUM.get(level, 0.6) + 0.15)
    _fork(k, turret, level, s, zb, zc, fx)
    head = k.empty("head", (0, 0, zc), parent=turret)
    head["node"] = "elevating"
    head.rotation_euler = (EL, 0, 0)
    if level == 1:
        face = _shade_lamp(k, head, s)
    elif level == 2:
        face = _four_bulbs(k, head, s, fx)
    else:
        face = _drum(k, head, level, s)
    m = k.empty("muzzle", (0, face, 0), parent=head)
    m["marker"] = "muzzle"
    set_fire_frame(0)
    return root, turret


def ground(level):
    from ..terrain import Patch
    return Patch(r_solid=FOOTPRINT_M, r_out=FOOTPRINT_M + 0.6, r_bare=2.4, seed=61, ragged=0.5)


def _glow(o):
    _RIG["glow"].append((o, tuple(o.scale)))
    return o


# -- static base ------------------------------------------------------------------------------
def _base(k, root, level, s):
    z = DECK_Z[level]
    if level == 1:                                        # log sledge, plank turntable on a peg
        for x in (-0.72, 0.72):
            k.tube("runner", (x, -1.35, 0.15), (x, 1.25, 0.15), 0.15, "log", parent=root, segs=14)
            k.tube("runner_nose", (x, 1.25, 0.15), (x, 1.5, 0.32), 0.13, "log", parent=root, segs=14)
        for y in (-0.9, 0.0, 0.9):
            k.box("cross_log", (1.75, 0.2, 0.16), (0, y, 0.34), "timber_raw", parent=root, bevel=0.01)
        k.cylinder("peg", 0.12, 0.16, (0, 0, 0.3), "timber_raw", segs=12, parent=root)
        k.cylinder("turntable", 0.62, 0.06, (0, 0, z - 0.06), "timber_raw", segs=28, parent=root)
        k.box("drag_rope_ring", (0.08, 0.08, 0.08), (0, 1.55, 0.36), "iron_forged", parent=root, bevel=False)
        return z
    if level == 2:                                        # two-wheel cart, drawbar and a foot
        k.box("cart_bed", (1.6, 1.15, 0.12), (0, 0, 0.5), "timber_tarred", parent=root, bevel=0.01)
        for x in (-0.72, 0.72):
            k.box("cart_side", (0.1, 1.15, 0.22), (x, 0, 0.62), "timber_tarred", parent=root, bevel=0.008)
        k.tube("axle", (-1.0, 0, 0.45), (1.0, 0, 0.45), 0.04, "iron_forged", parent=root, segs=10, bevel=False)
        for x in (-0.94, 0.94):
            _wheel(k, root, (x, 0, 0.45), 0.45, "timber_tarred")
        k.beam("drawbar", (0, 0.55, 0.48), (0, 1.75, 0.16), (0.1, 0.1), "timber_tarred", parent=root)
        k.beam("prop_foot", (0, 1.65, 0.2), (0, 1.65, 0.0), (0.07, 0.07), "timber_tarred", parent=root)
        k.beam("rear_prop", (0, -0.5, 0.48), (0, -0.85, 0.0), (0.08, 0.08), "timber_tarred", parent=root)
        k.cylinder("turntable", 0.55, 0.08, (0, 0, z - 0.08), "brass", segs=32, parent=root)
        return z
    if level == 3:                                        # cruciform outriggers with screw-jack feet
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = Vector((d[0] * 0.35, d[1] * 0.35, 0.4)), Vector((d[0] * 1.5, d[1] * 1.5, 0.2))
            k.beam("outrigger", a, b, (0.14, 0.16), "paint_olive_worn", parent=root)
            k.cylinder("jack_pad", 0.16, 0.05, (b.x, b.y, 0), "steel_worn", segs=16, parent=root)
            k.tube("jack_screw", (b.x, b.y, 0.05), (b.x, b.y, 0.36), 0.03, "steel_worn", parent=root, segs=8)
            k.tube("jack_handle", (b.x - 0.12, b.y, 0.36), (b.x + 0.12, b.y, 0.36), 0.015, "iron_black",
                   parent=root, segs=6, bevel=False)
        k.cylinder("column", 0.45, 0.56, (0, 0, 0.0), "paint_olive_worn", segs=28, parent=root)
        k.cylinder("column_cap", 0.55, 0.1, (0, 0, 0.56), "steel_worn", segs=32, parent=root)
        return z
    if level == 4:                                        # low armoured pedestal, bronze bands, a step
        k.cylinder("pedestal", 0.85, 0.64, (0, 0, 0), "iron_black", segs=40, parent=root, radius_top=0.8)
        for zz in (0.12, 0.5):
            k.torus("pedestal_band", 0.85 - zz * 0.07, 0.03, (0, 0, zz), "bronze_old", parent=root, segs=48,
                    tube_segs=6)
        k.box("step", (0.5, 0.6, 0.24), (1.05, 0.3, 0.12), "iron_black", parent=root, bevel=0.02)
        k.cylinder("turntable", 0.62, 0.08, (0, 0, 0.64), "bronze_old", segs=40, parent=root)
        return z
    # 5: marble octagon plinth, gilded azimuth ring with ticks
    k.cylinder("plinth", 1.12, 0.45, (0, 0, 0), "stone_pale", segs=8, parent=root)
    k.torus("azimuth_ring", 0.86, 0.035, (0, 0, 0.46), "gold_trim", parent=root, segs=64, tube_segs=6)
    for i in range(24):
        a = 2 * math.pi * i / 24
        d = Vector((math.cos(a), math.sin(a), 0))
        k.box("tick", (0.12, 0.025, 0.02), d * 0.98 + Vector((0, 0, 0.455)), "gold_trim", rot=(0, 0, a), parent=root,
              bevel=False)
    k.cylinder("turntable", 0.56, 0.15, (0, 0, 0.45), "gold_trim", segs=40, parent=root)
    return z


def _wheel(k, parent, c, r, mat):
    c = Vector(c)
    k.torus("tyre", r, 0.045, c, "iron_forged", rot=(0, math.pi / 2, 0), parent=parent, segs=32, tube_segs=6)
    k.torus("felloe", r - 0.06, 0.04, c, mat, rot=(0, math.pi / 2, 0), parent=parent, segs=32, tube_segs=6)
    k.cylinder("hub", 0.09, 0.2, c - Vector((0.1, 0, 0)), mat, segs=12, rot=(0, math.pi / 2, 0), parent=parent)
    for i in range(10):
        a = 2 * math.pi * i / 10
        k.beam("spoke", c, c + Vector((0, math.cos(a), math.sin(a))) * (r - 0.06), (0.035, 0.035), mat,
               parent=parent, bevel=False)


# -- the fork -------------------------------------------------------------------------------------
def _fork(k, t, level, s, zb, zc, fx):
    k.box("yoke", (2 * fx + 0.2, 0.36, 0.12), (0, 0, zb + 0.06), s["arm"], parent=t, bevel=0.015)
    for sx in (-1, 1):
        k.box("fork_arm", (0.14, 0.24, zc - zb), (sx * fx, 0, zb + (zc - zb) / 2), s["arm"], parent=t, bevel=0.015)
        k.cylinder("trunnion", 0.1, 0.12, (sx * (fx + 0.07), 0, zc), s["fit"], segs=16,
                   rot=(0, math.pi / 2, 0), parent=t)
    if level == 1:                                        # leather gas bags strapped behind the lamp
        for x in (-0.32, 0.32):
            b = _ball(k, t, (x, -0.55, zb + 0.32), 0.3, "leather", subdiv=3)
            b.scale = (0.9, 0.75, 0.62)
            k.hose("gas_hose", [(x, -0.4, zb + 0.5), (x * 0.4, -0.45, zc - 0.25), (0, -0.4, zc - 0.05)], 0.018,
                   "leather", parent=t)
    if level == 3:                                        # cam on the near side, worked by a crank
        c = Vector((fx + 0.14, -0.15, zc - 0.32))
        k.cylinder("cam", 0.17, 0.05, c, "steel_worn", segs=20, rot=(0, math.pi / 2, 0), parent=t)
        k.box("cam_lobe", (0.05, 0.12, 0.08), c + Vector((0.02, 0.12, 0.08)), "steel_worn", parent=t, bevel=False)
        k.beam("cam_crank", c + Vector((0.06, 0, 0)), c + Vector((0.06, -0.12, -0.22)), (0.03, 0.03), "iron_black",
               parent=t, bevel=False)
        k.tube("cam_rod", c + Vector((0.04, 0.12, 0.08)), (fx + 0.05, 0.45, zc + 0.1), 0.015, "steel_worn",
               parent=t, segs=6, bevel=False)


# -- heads ------------------------------------------------------------------------------------------
def _shade_lamp(k, h, s):
    """L1: iron lamp house, a light leather shade flaring forward, one bare bulb inside."""
    k.cylinder("lamp_house", 0.17, 0.22, (0, -0.5, 0), "iron_forged", segs=18, rot=ROT_Y, parent=h)
    k.tube("lamp_vent", (0, -0.4, 0.12), (0, -0.42, 0.52), 0.04, "iron_forged", parent=h, segs=10)
    k.cylinder("vent_cap", 0.08, 0.04, (0, -0.42, 0.52), "iron_forged", segs=12, parent=h)
    y0, y1 = -0.3, 0.42
    shade = k.lathe("shade", [(y0, 0.21), (y0 + 0.25, 0.36), (y1, 0.66), (y1, 0.63), (y0 + 0.25, 0.33),
                              (y0 + 0.02, 0.18)], "leather_pale", segs=40, parent=h)
    shade.data.polygons.foreach_set("use_smooth", [True] * len(shade.data.polygons))
    k.torus("shade_rim", 0.655, 0.028, (0, y1, 0), "leather", rot=ROT_TY, parent=h, segs=40, tube_segs=6)
    k.torus("shade_seam", 0.36, 0.012, (0, y0 + 0.25, 0), "leather", rot=ROT_TY, parent=h, segs=32, tube_segs=4)
    for i in range(8):                                    # stitched gores
        a = 2 * math.pi * i / 8 + 0.2
        p0 = Vector((0.215 * math.cos(a), y0 + 0.02, 0.215 * math.sin(a)))
        p1 = Vector((0.665 * math.cos(a), y1 - 0.01, 0.665 * math.sin(a)))
        k.tube("gore_seam", p0, p1, 0.008, "leather", parent=h, segs=4, bevel=False)
    k.cylinder("socket", 0.07, 0.16, (0, -0.28, 0), "iron_forged", segs=12, rot=ROT_Y, parent=h)
    _glow(_ball(k, h, (0, -0.0, 0), 0.17, "lamp_glow", subdiv=3))
    for x in (-0.6, 0.6):                                # side straps to the trunnions
        k.beam("shade_strap", (x, 0, 0), (x * 0.5, 0.0, 0), (0.04, 0.05), "iron_forged", parent=h, bevel=False)
    return y1


def _four_bulbs(k, h, s, fx):
    """L2: a brass cross with four open bulbs, a small concave mirror behind them."""
    k.box("crossbar", (2 * fx, 0.12, 0.12), (0, -0.26, 0), "timber_tarred", parent=h, bevel=0.01)
    k.lathe("mirror_back", [(-0.16, 0.0), (-0.16, 0.6), (-0.04, 0.62), (-0.04, 0.0)], "brass", segs=40,
            parent=h)
    k.lathe("mirror", [(-0.035, 0.0), (-0.05, 0.0), (-0.05, 0.58), (-0.0, 0.58), (-0.06, 0.3), (-0.08, 0.001)],
            "chrome", segs=40, parent=h)
    k.torus("mirror_rim", 0.61, 0.025, (0, -0.02, 0), "brass", rot=ROT_TY, parent=h, segs=40, tube_segs=6)
    k.cylinder("hub", 0.09, 0.12, (0, -0.02, 0), "brass", segs=16, rot=ROT_Y, parent=h)
    for a in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
        d = Vector((math.cos(a), 0, math.sin(a)))
        tip = d * 0.58 + Vector((0, 0.1, 0))
        k.beam("cross_arm", Vector((0, 0.08, 0)), tip, (0.04, 0.04), "brass", parent=h, bevel=False)
        k.cylinder("socket", 0.055, 0.12, tip, "brass", segs=12, rot=ROT_Y, parent=h)
        _glow(_ball(k, h, tip + Vector((0, 0.27, 0)), 0.17, "lamp_glow", subdiv=3))
        k.torus("bulb_neck", 0.06, 0.015, tip + Vector((0, 0.13, 0)), "brass", rot=ROT_TY, parent=h, segs=12,
                tube_segs=4)
    return 0.5


def _drum(k, h, level, s):
    """L3-5: the drum, lens and louvres (3), flash trays (4), filter wheel (5)."""
    R = R_DRUM[level]
    d, band = s["drum"], s["band"]
    yb, yf = -0.5, 0.48
    k.lathe("drum", [(yb, R * 0.94), (yb + 0.04, R), (yf, R), (yf, R * 0.95), (yb + 0.08, R * 0.9)], d, segs=44,
            parent=h)
    k.cylinder("back_plate", R * 0.95, 0.04, (0, yb, 0), d, segs=40, rot=ROT_Y, parent=h)
    k.cylinder("lamp_house", R * 0.62, 0.34, (0, yb - 0.34, 0), d, segs=32, rot=ROT_Y, parent=h)
    k.tube("chimney", (0, yb - 0.17, R * 0.55), (0, yb - 0.17, R * 0.55 + 0.22 + 0.03 * level), 0.1 + 0.01 * level, d,
           parent=h, segs=16)
    k.cylinder("chimney_cap", 0.17 + 0.01 * level, 0.06, (0, yb - 0.17, R * 0.55 + 0.22 + 0.03 * level), band,
               segs=16, parent=h)
    for f in (0.15, 0.85):
        k.torus("drum_band", R + 0.012, 0.022, (0, yb + (yf - yb) * f, 0), band, rot=ROT_TY, parent=h, segs=48,
                tube_segs=6)
    if level == 3:                                        # rivet rows
        for f in (0.08, 0.92):
            for i in range(24):
                a = 2 * math.pi * i / 24
                k.cylinder("rivet", 0.018, 0.02, (R * math.cos(a), yb + (yf - yb) * f, R * math.sin(a)), "steel_worn",
                           segs=6, parent=h, bevel=False)
    # the face: lens with Fresnel rings and a bright core
    k.cylinder("lens", R * 0.95, 0.03, (0, yf - 0.05, 0), "lens_glass", segs=44, rot=ROT_Y, parent=h)
    for f in (0.42, 0.58, 0.74, 0.88):
        k.torus("fresnel", R * f, 0.008, (0, yf - 0.015, 0), "lens_glass", rot=ROT_TY, parent=h, segs=40,
                tube_segs=4)
    _glow(k.cylinder("core", R * 0.3, 0.015, (0, yf - 0.02, 0), "lamp_glow", segs=28, rot=ROT_Y, parent=h,
                     bevel=False))
    k.torus("face_rim", R + 0.01, 0.035, (0, yf, 0), band, rot=ROT_TY, parent=h, segs=48, tube_segs=6)
    if level >= 3:                                        # louvre slats across the face, on pivots
        for i in range(-3, 4):
            z = i * R * 0.26
            w = math.sqrt(max(R * R * 0.9 - z * z, 0.01))
            k.box("louvre", (2 * w, 0.03, 0.07), (0, yf + 0.03, z), s["arm"] if level < 5 else "silver_satin",
                  rot=(math.radians(28), 0, 0), parent=h, bevel=False)
        k.box("louvre_link", (0.03, 0.03, R * 1.6), (R * 0.93, yf + 0.05, 0), s["fit"], parent=h, bevel=False)
    if level >= 4:                                        # ring of magnesium flash trays round the face
        for i in range(6):
            a = math.pi / 2 + 2 * math.pi * i / 6
            dv = Vector((math.cos(a), 0, math.sin(a)))
            p = dv * (R + 0.2) + Vector((0, yf + 0.06, 0))
            k.beam("tray_arm", dv * R + Vector((0, yf - 0.05, 0)), p, (0.03, 0.03), band, parent=h, bevel=False)
            k.cylinder("tray", 0.11, 0.04, p, "silver_satin" if level == 4 else "gold_trim", segs=16,
                       rot=(math.radians(-60), 0, 0), parent=h)
            _glow(k.cylinder("tray_powder", 0.08, 0.02, p + Vector((0, 0.01, 0.02)), "plaster", segs=14,
                             rot=(math.radians(-60), 0, 0), parent=h, bevel=False))
    if level == 5:                                        # coloured filter wheel beside the face
        wc = Vector((R * 1.05, yf + 0.12, R * 0.2))
        k.torus("filter_wheel", R * 0.62, 0.03, wc, "gold_trim", rot=ROT_TY, parent=h, segs=40, tube_segs=6)
        k.cylinder("filter_hub", 0.07, 0.1, wc - Vector((0, 0.05, 0)), "gold_trim", segs=16, rot=ROT_Y, parent=h)
        cols = ["glass_blue", "glass_amber", "glass_red"] * 2
        for i, col in enumerate(cols):
            a = 2 * math.pi * i / 6
            p = wc + Vector((math.cos(a), 0, math.sin(a))) * R * 0.38
            k.cylinder("filter_glass", R * 0.22, 0.02, p, col, segs=24, rot=ROT_Y, parent=h, bevel=False)
            k.beam("filter_spoke", wc, p, (0.02, 0.02), "gold_trim", parent=h, bevel=False)
        k.beam("filter_bracket", Vector((R * 0.8, yf - 0.1, 0)), wc, (0.04, 0.04), "gold_trim", parent=h,
               bevel=False)
    return yf


# -- ammo pile --------------------------------------------------------------------------------
def _ammo(k, root, level, s):
    g = Vector((1.55, 1.15, 0))
    if level == 1:                                        # basket of quicklime blocks
        k.cylinder("basket", 0.32, 0.34, g, "wicker", segs=20, parent=root, radius_top=0.35)
        for i in range(4):
            k.box("lime_block", (0.14, 0.14, 0.12), g + Vector((-0.12 + 0.08 * i, -0.05 + 0.05 * (i % 2), 0.36)),
                  "plaster", rot=(0, 0, 0.3 * i), parent=root, bevel=0.01)
    elif level == 2:                                      # crate of lime, two gas bottles
        k.box("lime_crate", (0.7, 0.5, 0.35), g + Vector((0, 0, 0.175)), "timber_raw", parent=root, bevel=0.01)
        for i, (mat, x) in enumerate((("paint_blue", -1.2), ("paint_red", -1.52))):
            k.cylinder("gas_bottle", 0.13, 0.9, (x, 1.4, 0), mat, segs=16, parent=root)
            k.cylinder("bottle_valve", 0.05, 0.12, (x, 1.4, 0.9), "brass", segs=10, parent=root)
    elif level == 3:                                      # accumulator crate, rack of carbon rods
        k.box("accumulators", (0.8, 0.55, 0.42), g + Vector((0, 0, 0.21)), "paint_olive_worn", parent=root,
              bevel=0.015)
        for i in range(3):
            k.cylinder("terminal", 0.035, 0.06, g + Vector((-0.2 + 0.2 * i, 0, 0.42)), "copper", segs=8,
                       parent=root, bevel=False)
        k.beam("rod_rack", (-1.45, 1.2, 0.5), (-0.85, 1.2, 0.5), (0.06, 0.06), "paint_olive_worn", parent=root)
        for i in range(6):
            k.tube("carbon_rod", (-1.35 + 0.08 * i, 1.2, 0.02), (-1.33 + 0.08 * i, 1.22, 0.85), 0.018, "iron_black",
                   parent=root, segs=6, bevel=False)
    elif level == 4:                                      # magnesium ribbon reels, powder tins
        for i in range(3):
            c = g + Vector((-0.35 * i, 0.1 * i, 0.22))
            k.cylinder("ribbon_reel", 0.22, 0.12, c, "silver_satin", segs=24, rot=(math.pi / 2, 0, 0), parent=root)
        for i in range(3):
            k.cylinder("powder_tin", 0.11, 0.3, (-1.25 + 0.25 * i, 1.35, 0), "bronze_old", segs=16, parent=root)
    else:                                                 # lacquered case of coloured glasses
        k.box("glass_case", (0.9, 0.6, 0.2), g + Vector((0, 0, 0.1)), "timber_varnish", parent=root, bevel=0.015)
        k.box("case_trim", (0.94, 0.64, 0.03), g + Vector((0, 0, 0.215)), "gold_trim", parent=root, bevel=0.005)
        for i, col in enumerate(("glass_blue", "glass_amber", "glass_red")):
            k.cylinder("spare_glass", 0.11, 0.025, g + Vector((-0.25 + 0.25 * i, 0, 0.23)), col, segs=20,
                       parent=root, bevel=False)


# -- animation -------------------------------------------------------------------------------------
def key_fire_animation(scene):
    prefs = bpy.context.preferences.edit
    old = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = "LINEAR"
    for f in range(FIRE_FRAMES + 1):
        set_fire_frame(f)
        for o, _ in _RIG["glow"]:
            o.keyframe_insert("scale", frame=f)
    prefs.keyframe_new_interpolation_type = old
    scene.frame_set(0)


def set_fire_frame(f, scene=None):
    if scene is not None and _RIG["glow"] and _RIG["glow"][0][0].animation_data is not None:
        scene.frame_set(f)
    else:
        g = 1.0 if f == 0 else FIRE[f - 1]
        for o, s0 in _RIG["glow"]:
            o.scale = tuple(v * g for v in s0)
    bpy.context.view_layer.update()
