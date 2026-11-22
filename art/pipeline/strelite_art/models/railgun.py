"""Rail cannon (bg: „Релсотрон“): the one gun of the far future in a world of steam and
torsion. Two copper rails held apart by porcelain insulators throw an iron slug along a
straight line; the charge comes from a bank of glass capacitor jars fed by a dynamo.
Built on a turning pedestal. Front is local +Y.

Every level adds a new kind of mechanism that explains a stronger shot:
  1  the prototype: bare rails in a timber cradle, exposed cables, Leyden jars in a rack,
     a hand-cranked dynamo
  2  a closed iron housing around the rails and a capacitor cabinet; a flywheel dynamo
  3  armour, and a water jacket with cooling fins along the barrel so it can fire again
  4  a ring of glowing booster coils along the barrel (coil stages that add speed)
  5  white enamel and chrome with gold, a crown of discharge spheres over the breech
The traverse changes too: timber crib and pivot (1), iron pedestal (2), wheels on a ring
rail (3), a geared ring and handwheel (4), a ball race under a gilded ring (5).

Returns (root, turret). The base is static; the turret turns.

Firing animation: a short recoil of the barrel on its slide and back; the charge glow and
the beam are effects (render_effects.py).
"""
import math

import bpy
from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit
from . import faction as fx
from .ballista import _beam, _keep_world
from .trebuchet import _ball

LEVELS = (1, 2, 3, 4, 5)
FRAME_M = 9.0
TARGET_Z = 1.2
SPRITE_FRAME_M = 12.5     # room for the long barrel of levels 3-5
SWEEP_M = 5.4
FOOTPRINT_M = 3.0        # 2x2 tiles of 4 m
AXIS_Z = 1.75            # line of the rails

STYLE = {
    1: dict(body="timber_raw", fit="iron_forged", rail="copper", house=None, wheel="timber_raw"),
    2: dict(body="iron_forged", fit="iron_forged", rail="copper", house="paint_enemy_worn", wheel="iron_forged"),
    3: dict(body="iron_black", fit="steel_worn", rail="copper", house="iron_black", wheel="iron_black"),
    4: dict(body="iron_black", fit="bronze_old", rail="copper", house="iron_black", wheel="bronze_old"),
    5: dict(body="enamel_white", fit="gold_trim", rail="chrome", house="enamel_white", wheel="gold_trim"),
}

FIRE = [-0.55, -0.4, -0.26, -0.15, -0.07, -0.02]       # barrel slide (m) per frame
FIRE_FRAMES = len(FIRE)
RELEASE_FRAME = 1
RELOAD_FROM = 2
FIRE_FPS = 16
LOOP = False
_RIG = {}


def build(style, level=1):
    k = Kit(style)
    s = STYLE[level]
    root = k.empty("railgun")
    _base(k, root, level, s)
    _slug_pile(k, root, level, s)
    turret = k.empty("turret", (0, 0, 0), parent=root)
    turret["node"] = "turret"
    mp.set_reference(turret)
    _mount(k, turret, level, s)
    tip = _barrel(k, turret, level, s)
    m = k.empty("muzzle", tip, parent=turret)
    m["marker"] = "muzzle"
    _power(k, turret, level, s)
    set_fire_frame(0)
    return root, turret


def ground(level):
    from ..terrain import Patch
    return Patch(r_solid=FOOTPRINT_M, r_out=FOOTPRINT_M + 0.6, r_bare=2.6, seed=97, ragged=0.5)


# -- static base ----------------------------------------------------------------------------
def _base(k, root, level, s):
    if level == 1:                                       # timber crib
        for i, z in enumerate((0.1, 0.3, 0.5)):
            for sy in (-1, 1):
                if i % 2:
                    k.box("crib", (0.24, 2.2, 0.2), (sy * 0.85, 0, z), "timber_raw", parent=root, bevel=0.01)
                else:
                    k.box("crib", (2.2, 0.24, 0.2), (0, sy * 0.85, z), "timber_raw", parent=root, bevel=0.01)
        k.box("crib_top", (1.9, 1.9, 0.08), (0, 0, 0.64), "timber_raw", parent=root, bevel=0.01)
        k.cylinder("pivot", 0.18, 0.1, (0, 0, 0.68), "iron_forged", segs=16, parent=root)
        return
    # stone plinth and an iron pedestal
    k.cylinder("plinth", 1.2, 0.35, (0, 0, 0), "concrete", segs=40, parent=root)
    k.cylinder("pedestal", 0.55, 0.38, (0, 0, 0.35), s["fit"] if level < 5 else "enamel_white", segs=32, parent=root,
               radius_top=0.48)
    for i in range(16):
        a = 2 * math.pi * i / 16
        k.cylinder("bolt", 0.035, 0.04, (0.95 * math.cos(a), 0.95 * math.sin(a), 0.35), "steel_worn", segs=8,
                   parent=root, bevel=False)
    if level >= 3:                                       # ring rail
        k.torus("ring_rail", 1.55, 0.04, (0, 0, 0.06), "steel_worn", parent=root, segs=72, tube_segs=6)
        for i in range(20):
            a = 2 * math.pi * i / 20
            d = Vector((math.cos(a), math.sin(a), 0))
            k.box("sleeper", (0.34, 0.1, 0.05), d * 1.55 + Vector((0, 0, 0.025)), "timber_oak", rot=(0, 0, a),
                  parent=root, bevel=0.004)
    if level >= 4:                                       # geared ring
        m = s["fit"]
        k.cylinder("traverse_ring", 0.62, 0.06, (0, 0, 0.66), m, segs=48, parent=root)
        for i in range(40):
            a = 2 * math.pi * i / 40
            d = Vector((math.cos(a), math.sin(a), 0))
            k.box("tooth", (0.05, 0.03, 0.06), d * 0.64 + Vector((0, 0, 0.69)), m, rot=(0, 0, a), parent=root,
                  bevel=False)
    if level >= 5:
        for i in range(20):
            a = 2 * math.pi * i / 20
            _ball(k, root, (0.4 * math.cos(a), 0.4 * math.sin(a), 0.78), 0.05, "chrome", subdiv=2)


def _slug_pile(k, root, level, s):
    """Spare slugs on the ground: iron bolts in a box, brighter with each level."""
    from .trebuchet import ground_spot
    c = ground_spot(2.6, -40)
    rot = Vector((c.x, c.y, 0)).to_track_quat("Y", "Z").to_euler()
    g = k.empty("slug_box", c, parent=root)
    g.rotation_euler = (0, 0, rot.z + math.pi / 2)
    box = "timber_raw" if level == 1 else ("paint_enemy_worn" if level < 5 else "enamel_white")
    k.box("box_floor", (0.5, 0.8, 0.04), (0, 0, 0.02), box, parent=g, bevel=0.004)
    for sx in (-1, 1):
        k.box("box_side", (0.03, 0.8, 0.18), (sx * 0.25, 0, 0.1), box, parent=g, bevel=0.003)
        k.box("box_end", (0.5, 0.03, 0.18), (0, sx * 0.4, 0.1), box, parent=g, bevel=0.003)
    slug = ("iron_forged", "iron_forged", "steel_worn", "copper", "gold_trim")[level - 1]
    for i in range(6):
        x = -0.15 + (i % 3) * 0.15
        z = 0.1 + (i // 3) * 0.1
        k.tube("slug", (x, -0.3, z), (x, 0.3, z), 0.05, slug, parent=g, segs=12)
        if level >= 3:
            k.torus("slug_band", 0.052, 0.012, (x, 0.0, z), "copper" if level < 5 else "chrome",
                    rot=(math.pi / 2, 0, 0), parent=g, segs=12, tube_segs=4)


# -- turret ---------------------------------------------------------------------------------
def _mount(k, t, level, s):
    B = s["body"]
    z0 = 0.7 if level == 1 else 0.74
    k.cylinder("turntable", 0.95, 0.12, (0, 0, z0), B if level > 1 else "timber_raw", segs=40, parent=t)
    for sx in (-1, 1):                                   # trunnion cheeks
        k.prism("cheek", [(-0.7, z0 + 0.1), (0.5, z0 + 0.1), (0.25, AXIS_Z + 0.25), (-0.45, AXIS_Z + 0.25)], 0.12,
                B if level > 1 else "timber_raw", y=-sx * 0.42, parent=t).rotation_euler = (0, 0, math.pi / 2)
    if level == 2:
        for sy in (-1, 1):
            k.tube("traverse_bar", (0.9, sy * 0.4, z0 + 0.1), (1.4, sy * 0.55, z0 + 0.2), 0.03, "steel_worn",
                   parent=t, segs=8, bevel=False)
    if level >= 3:                                       # wheels on the ring rail
        for a in (45, 135, 225, 315):
            d = Vector((math.cos(math.radians(a)), math.sin(math.radians(a)), 0))
            c = d * 1.55 + Vector((0, 0, 0.17))
            tang = Vector((-d.y, d.x, 0))
            k.cylinder("rail_wheel", 0.13, 0.1, c - tang * 0.05, s["wheel"], segs=16,
                       rot=tang.to_track_quat("Z", "Y").to_euler(), parent=t)
            _beam(k, t, "wheel_arm", d * 0.85 + Vector((0, 0, z0)), c + Vector((0, 0, 0.08)), (0.1, 0.1), s["body"])
    if level >= 4:                                       # traverse handwheel on the geared ring
        c = Vector((-0.75, -0.55, z0 - 0.05))
        k.cylinder("pinion", 0.08, 0.08, c, s["fit"], segs=10, parent=t)
        k.tube("pinion_shaft", c, c + Vector((0, 0, 0.75)), 0.025, s["fit"], parent=t, segs=8, bevel=False)
        hw = c + Vector((0, 0, 0.78))
        k.torus("handwheel", 0.2, 0.022, hw, s["fit"], parent=t, segs=24, tube_segs=5)
        for i in range(4):
            a = i * math.pi / 2
            k.beam("hw_spoke", hw, hw + Vector((math.cos(a), math.sin(a), 0)) * 0.19, (0.02, 0.02), s["fit"], parent=t,
                   bevel=False)


def _barrel(k, t, level, s):
    """The rails (on a recoil slide) and whatever wraps them; returns the muzzle."""
    slide = k.empty("slide", (0, 0, 0), parent=t)
    y0, y1 = -1.6, (5.2 if level >= 3 else 3.4)       # levels 3-5: long barrel, coils stand apart (user 2026-11-22)
    z = AXIS_Z
    parts = []
    for sx in (-1, 1):                                   # the two rails
        parts.append(k.box("rail", (0.08, y1 - y0, 0.22), (sx * 0.1, (y0 + y1) / 2, z), s["rail"], parent=t,
                           bevel=0.006))
    n = 10 if level >= 3 else 7
    for i in range(n):                                   # porcelain insulators holding them apart
        y = y0 + 0.3 + i * (y1 - y0 - 0.5) / (n - 1)
        parts.append(k.box("clamp", (0.42, 0.1, 0.4), (0, y, z), s["fit"], parent=t, bevel=0.01))
        for sx in (-1, 1):
            parts.append(k.cylinder("insulator", 0.06, 0.16, (sx * 0.23, y, z + 0.1), "porcelain", segs=12,
                                    parent=t))
            for j in range(3):
                parts.append(k.cylinder("insulator_skirt", 0.075, 0.02, (sx * 0.23, y, z + 0.13 + j * 0.04),
                                        "porcelain", segs=12, parent=t, bevel=False))
    if s["house"]:                                       # closed housing (2+): an upper and lower shell
        for zz in (z + 0.24, z - 0.24):
            parts.append(k.box("housing", (0.5, y1 - y0 - 0.6, 0.08), (0, (y0 + y1) / 2 - 0.2, zz), s["house"],
                               parent=t, bevel=0.02))
        for sx in (-1, 1):
            parts.append(k.box("housing_side", (0.06, y1 - y0 - 0.6, 0.42), (sx * 0.26, (y0 + y1) / 2 - 0.2, z),
                               s["house"], parent=t, bevel=0.01))
            if level >= 2:
                fx.rivets(k, t, (sx * 0.29, y0 + 0.2, z + 0.15), (sx * 0.29, y1 - 0.8, z + 0.15), 12, (sx, 0, 0), r=0.025)
    if level >= 3:                                       # water jacket and cooling fins
        parts.append(k.tube("water_jacket", (0, y0 + 0.6, z + 0.42), (0, y1 - 1.2, z + 0.42), 0.12, s["fit"],
                            parent=t, segs=16))
        for i in range(14):
            y = y0 + 0.8 + i * 0.22
            parts.append(k.box("fin", (0.62, 0.025, 0.5), (0, y, z + 0.05), s["fit"] if level < 5 else "chrome",
                               parent=t, bevel=False))
    if level >= 4:                                       # booster coils
        for i in range(5):
            y = y1 - 2.55 + i * 0.6
            parts.append(k.torus("coil", 0.38, 0.08, (0, y, z), "copper", rot=(math.pi / 2, 0, 0), parent=t, segs=28,
                                 tube_segs=8))
            parts.append(k.torus("coil_glow", 0.38, 0.045, (0, y + 0.09, z), "arc_glow", rot=(math.pi / 2, 0, 0),
                                 parent=t, segs=28, tube_segs=6))
    if level >= 3:                                       # automatic sight: an angular armoured head, opaque
        ys, zs, G = -1.15, z + 0.72, 1.7                 # G: head scale, big enough to read at game zoom
        hm = s["house"]
        parts.append(k.cylinder("sight_post", 0.1, 0.4, (0, ys, zs - 0.36), s["fit"], segs=12, parent=t))
        parts.append(k.cylinder("sight_ring", 0.16, 0.05, (0, ys, zs - 0.02), s["fit"], segs=20, parent=t))
        prof = [(-0.42, 0.0), (0.28, 0.0), (0.46, 0.1), (0.34, 0.27), (-0.26, 0.3), (-0.44, 0.16)]
        parts.append(k.plate("sight_head", [(ys + a * G, zs + b * G) for a, b in prof], 0.36 * G, 0.0, hm, parent=t))
        for sx in (-1, 1):                               # sloped side cheeks make the head read as faceted
            cheek = [(-0.3, 0.03), (0.22, 0.03), (0.3, 0.12), (0.2, 0.24), (-0.22, 0.25), (-0.34, 0.14)]
            parts.append(k.plate("sight_cheek", [(ys + a * G, zs + b * G) for a, b in cheek], 0.06, sx * 0.21 * G, hm,
                                 parent=t))
        face = [(0.29, 0.03), (0.45, 0.1), (0.35, 0.25), (0.3, 0.24), (0.39, 0.11), (0.27, 0.06)]
        parts.append(k.plate("sight_face", [(ys + a * G, zs + b * G) for a, b in face], 0.26 * G, 0.0, "gunmetal",
                             parent=t))
        parts.append(k.box("sight_brow", (0.4 * G, 0.08, 0.05), (0, ys + 0.3 * G, zs + 0.29 * G), s["fit"], parent=t,
                           bevel=0.005))
        parts.append(k.hose("sight_cable", [(0.12, ys - 0.35, zs + 0.05), (0.2, ys - 0.6, z + 0.35),
                                            (0.2, y0 + 0.1, z + 0.28)], 0.02, "rubber", parent=t))
    # breech block with the cable terminals
    parts.append(k.box("breech", (0.6, 0.55, 0.6), (0, y0 - 0.15, z), s["body"] if level > 1 else "iron_forged",
                       parent=t, bevel=0.03))
    for sx in (-1, 1):
        parts.append(k.cylinder("terminal", 0.06, 0.18, (sx * 0.2, y0 - 0.25, z + 0.3), "copper", segs=12,
                                parent=t))
    parts.append(k.box("muzzle_cap", (0.42, 0.12, 0.42), (0, y1 + 0.02, z), s["fit"], parent=t, bevel=0.02))
    if level >= 5:                                       # discharge spheres over the breech
        for x in (-0.25, 0.25):
            parts.append(k.tube("sphere_post", (x, y0 - 0.1, z + 0.3), (x, y0 - 0.1, z + 0.75), 0.025, "gold_trim",
                                parent=t, segs=8, bevel=False))
            parts.append(_ball(k, t, (x, y0 - 0.1, z + 0.85), 0.11, "chrome", subdiv=3))
        parts.append(k.torus("crown", 0.3, 0.02, (0, y0 - 0.1, z + 0.62), "gold_trim", parent=t, segs=24,
                             tube_segs=5))
    for o in parts:
        if o is not None and o.parent is t:
            _keep_world(o, slide)
    # the slide's bed on the cheeks (static)
    k.box("cradle", (0.7, 2.4, 0.12), (0, -0.2, z - 0.36), s["body"] if level > 1 else "timber_raw", parent=t,
          bevel=0.01)
    _RIG["slide"] = slide
    return Vector((0, y1 + 0.1, z))


def _power(k, t, level, s):
    """Capacitors and the dynamo at the back, cabled to the breech."""
    B = s["body"]
    yb = -2.2
    if level == 1:                                       # Leyden jars in a rack, hand dynamo
        for i in range(6):
            p = Vector((-0.55 + (i % 3) * 0.32, yb + 0.05 - (i // 3) * 0.32, 0.82))
            k.cylinder("jar", 0.12, 0.38, p, "glass", segs=16, parent=t)
            k.cylinder("jar_foil", 0.122, 0.2, p, "copper", segs=16, parent=t, bevel=False)
            k.tube("jar_rod", p + Vector((0, 0, 0.38)), p + Vector((0, 0, 0.55)), 0.012, "brass", parent=t, segs=6,
                   bevel=False)
            _ball(k, t, p + Vector((0, 0, 0.57)), 0.03, "brass", subdiv=1)
        k.box("jar_rack", (1.1, 0.75, 0.06), (-0.23, yb - 0.11, 0.79), "timber_raw", parent=t, bevel=0.005)
        d = Vector((0.6, yb, 0.95))
        k.cylinder("dynamo", 0.2, 0.4, d - Vector((0.2, 0, 0)), "iron_forged", segs=20, rot=(0, math.pi / 2, 0),
                   parent=t)
        k.beam("dynamo_crank", d + Vector((0.22, 0, 0)), d + Vector((0.22, -0.1, 0.3)), (0.04, 0.04), "iron_forged",
               parent=t, bevel=False)
        k.tube("crank_handle", d + Vector((0.22, -0.1, 0.3)), d + Vector((0.4, -0.1, 0.3)), 0.025, "wood", parent=t,
               segs=6, bevel=False)
        for x in (-0.3, 0.3):
            k.hose("cable", [(x, yb + 0.1, 1.3), (x, yb + 0.5, 1.6), (x * 0.6, -1.85, AXIS_Z + 0.4)], 0.025, "rubber",
                   parent=t)
        return
    # capacitor cabinet
    cab = s["house"]
    k.box("cabinet", (1.4, 0.8, 1.0), (-0.1, yb, 1.3), cab, parent=t, bevel=0.03)
    for i in range(4):
        k.cylinder("cap_core", 0.07, 0.04, (-0.6 + i * 0.33, yb - 0.41, 1.45), "arc_glow" if level >= 4 else "glass",
                   segs=14, rot=(math.pi / 2, 0, 0), parent=t, bevel=False)
    fx.gauge(k, t, (0.35, yb - 0.41, 1.1), (0, -1, 0), r=0.08)
    fx.gauge(k, t, (0.1, yb - 0.41, 1.1), (0, -1, 0), r=0.06)
    for x in (-0.4, 0.2):
        k.hose("cable", [(x, yb + 0.35, 1.75), (x, yb + 0.7, 1.95), (x * 0.5, -1.85, AXIS_Z + 0.4)], 0.035, "rubber",
               parent=t)
    # flywheel dynamo beside it
    d = Vector((0.85, yb + 0.1, 1.2))
    k.cylinder("dynamo", 0.24, 0.5, d - Vector((0.25, 0, 0)), s["fit"], segs=24, rot=(0, math.pi / 2, 0), parent=t)
    for j in range(5):
        k.torus("dynamo_winding", 0.245, 0.015, d + Vector((-0.2 + j * 0.1, 0, 0)), "copper",
                rot=(0, math.pi / 2, 0), parent=t, segs=24, tube_segs=4)
    fw = d + Vector((0.32, 0, 0))
    k.torus("flywheel", 0.42, 0.05, fw, s["wheel"], rot=(0, math.pi / 2, 0), parent=t, segs=32, tube_segs=6)
    for i in range(6):
        a = 2 * math.pi * i / 6
        k.beam("fw_spoke", fw, fw + Vector((0, math.cos(a), math.sin(a))) * 0.4, (0.03, 0.04), s["wheel"], parent=t,
               bevel=False)
    k.box("dynamo_base", (0.6, 0.5, 0.35), (0.85, yb + 0.1, 0.9), B, parent=t, bevel=0.02)


def key_fire_animation(scene):
    prefs = bpy.context.preferences.edit
    old = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = "LINEAR"
    for f in range(FIRE_FRAMES + 1):
        set_fire_frame(f)
        _RIG["slide"].keyframe_insert("location", frame=f)
    prefs.keyframe_new_interpolation_type = old
    scene.frame_set(0)


def set_fire_frame(f, scene=None):
    if scene is not None and _RIG["slide"].animation_data is not None:
        scene.frame_set(f)
    else:
        _RIG["slide"].location = (0, 0.0 if f == 0 else FIRE[f - 1], 0)
    bpy.context.view_layer.update()
