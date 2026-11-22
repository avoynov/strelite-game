"""76 mm divisional field gun, ZIS-3 type (bg: „Дивизионно оръдие“), built at real size
from public dimensions (length 6.1 m, width 1.65 m, line of fire 0.88 m, barrel 3.4 m):
split tubular trails with spades, disc wheels, angular shield, recoil brake under the
barrel and recuperator above it. A defenders' gun of the parallel world: the white tower
on a blue shield on its shield, light steampunk accents.

Each level changes the paint and adds a new kind of mechanism, and the ground under the
gun changes with it (2026-11-17 plan):
Level 1: worn green, open iron sights, spades dug into bare soil.
Level 2: fresh green, brass panoramic sight and elevation quadrant; a plank firing deck.
Level 3: camouflage, hydraulic accumulator with a gauge feeding the recoil brake; the trails
         ride on rollers over a timber track, spades stowed.
Level 4: grey steel, bigger shield with appliqué and wings, three-baffle muzzle brake; a
         toothed traverse ring around the deck with a pinion from the handwheel.
Level 5: black steel and brass, pneumatic rammer behind the breech fed from an air bottle;
         steel turntable on a ball race, rail track.

Returns (root, turret). `turret` (the whole gun) rotates around Z to aim.
"""
import math

import bpy
from mathutils import Vector

from .. import fort
from .. import materials_photoreal as mp
from ..fort import pol
from ..geo import Kit
from . import defender
from .ballista import _gear
from .howitzer import _bolts

LEVELS = (1, 2, 3, 4, 5)
STYLES = ("photoreal",)
FRAME_M = 9.5           # photo-style preview frame
TARGET_Z = 0.7
SPRITE_FRAME_M = 14.0   # game sprites: metres across the render
GUN_SHIFT = 1.0         # the gun sits this far forward of the rotation centre
SWEEP_M = 2.8           # ground-level parts (spades) turn inside this radius
FOOTPRINT_M = 4.0       # all static art stays inside this radius (2x2 tiles of 4 m)
AMMO_DEG = (-140, -72)  # sector of the ammunition point, toward the camera
ELEVATION_DEG = 12.0
HERO_DIR = 12
DECK_R = 1.55           # plank deck / turntable under the wheels
RING_R = 1.62           # toothed traverse ring (level 4+)
TRACK_R = 2.45          # trail roller track (level 3+)

STYLE = {
    1: dict(g="paint_sand_worn", worn="paint_sand_worn", barrel="paint_sand_barrel", soot="paint_sand_soot",
            steel="gunmetal", trim="gunmetal", ring="paint_red", deck=0.0),
    2: dict(g="paint_4bo", worn="paint_4bo_worn", barrel="paint_4bo_barrel", soot="paint_4bo_soot",
            steel="gunmetal", trim="brass", ring="paint_red", deck=0.05),
    3: dict(g="paint_camo", worn="paint_4bo_worn", barrel="paint_4bo_barrel", soot="paint_4bo_soot",
            steel="gunmetal", trim="brass", ring="paint_red", deck=0.05),
    4: dict(g="paint_steel", worn="steel_worn", barrel="gunmetal", soot="paint_4bo_soot",
            steel="gunmetal", trim="brass", ring="paint_red", deck=0.05),
    5: dict(g="iron_black", worn="iron_forged", barrel="iron_black", soot="iron_black",
            steel="gunmetal", trim="brass", ring="brass", deck=0.07),
}
G, WORN, BARREL, SOOT, STEEL, TRIM = "paint_4bo", "paint_4bo_worn", "paint_4bo_barrel", "paint_4bo_soot", "gunmetal", \
    "brass"
TRUNNION = Vector((0, -0.1, 0.87))
FIRE = [-0.42, -0.36, -0.27, -0.18, -0.1, -0.04]       # recoil slide (m) per frame
FIRE_FRAMES = len(FIRE)
RELEASE_FRAME = 1
RELOAD_FROM = 2
FIRE_FPS = 16
LOOP = False
_RIG = {}


def build(style, level=1):
    global G, WORN, BARREL, SOOT, STEEL, TRIM
    s = STYLE[level]
    G, WORN, BARREL, SOOT, STEEL, TRIM = s["g"], s["worn"], s["barrel"], s["soot"], s["steel"], s["trim"]
    k = Kit(style)
    root = k.empty("zis3")
    turret = k.empty("turret", parent=root)
    turret["node"] = "turret"
    gun = k.empty("gun", (0, GUN_SHIFT, s["deck"]), parent=turret)
    mp.set_reference(gun)
    _carriage(k, gun, level)
    _traverse_gun(k, gun, level)
    _shield(k, gun, level)
    _elevating_mass(k, gun, level)
    _traverse_ground(k, root, level)
    _props(k, root, level)
    return root, turret


def ground(level):
    from ..terrain import Patch
    return Patch(r_solid=FOOTPRINT_M, r_out=FOOTPRINT_M + 0.7, r_bare=SWEEP_M + 0.4 + 0.1 * (level - 1), seed=23,
                 ragged=0.5)


def key_fire_animation(scene):
    prefs = bpy.context.preferences.edit
    old = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = "LINEAR"
    for f in range(FIRE_FRAMES + 1):
        set_fire_frame(f)
        for o in _RIG["slide"]:
            o.keyframe_insert("location", frame=f)
    prefs.keyframe_new_interpolation_type = old
    scene.frame_set(0)


def set_fire_frame(f, scene=None):
    rec = _RIG["slide"][0]
    if scene is not None and rec.animation_data is not None:
        scene.frame_set(f)
    else:
        d = 0.0 if f == 0 else FIRE[f - 1]
        rec.location = (0, d, 0)
        for o in _RIG["slide"][1:]:                       # rammer rod rides back with the breech
            o.location = (0, d, 0)
    bpy.context.view_layer.update()


# --------------------------------------------------------------------------
def _wheel(k, t, hub):
    w = k.empty("wheel", hub, parent=t)
    w.rotation_euler = (0, 0, -math.pi / 2)     # local Y = axle
    tyre = [(-0.06, 0.0), (-0.06, 0.27), (-0.085, 0.3), (-0.092, 0.38), (-0.07, 0.42),
            (-0.03, 0.432), (0.03, 0.432), (0.07, 0.42), (0.092, 0.38), (0.085, 0.3),
            (0.06, 0.27), (0.06, 0.0)]
    k.lathe("tyre", tyre, "rubber", segs=44, parent=w)
    rim = [(-0.05, 0.0), (-0.05, 0.09), (-0.022, 0.25), (-0.06, 0.275), (0.06, 0.275),
           (0.022, 0.25), (0.05, 0.09), (0.05, 0.0)]
    k.lathe("rim", rim, G, segs=36, parent=w)
    for s in (-1, 1):
        k.cylinder("hubcap", 0.065, 0.05, (0, s * 0.05, 0), WORN, segs=18,
                   rot=(-s * math.pi / 2, 0, 0), parent=w)
        for i in range(6):                              # lightening holes of the stamped disc
            a = 2 * math.pi * i / 6
            k.cylinder("disc_hole", 0.036, 0.012, (0.175 * math.cos(a), s * 0.034, 0.175 * math.sin(a)),
                       "bore", segs=12, rot=(-s * math.pi / 2, 0, 0), parent=w, bevel=False)
        for i in range(6):
            a = 2 * math.pi * (i + 0.5) / 6
            k.cylinder("lug", 0.012, 0.02, (0.1 * math.cos(a), s * 0.05, 0.1 * math.sin(a)), STEEL,
                       segs=6, rot=(-s * math.pi / 2, 0, 0), parent=w, bevel=False, smooth=False)
    n = 52                                              # tread blocks
    for i in range(n):
        a = 2 * math.pi * i / n
        k.box("tread", (0.016, 0.15, 0.022), (0.43 * math.cos(a), 0, 0.43 * math.sin(a)), "rubber",
              rot=(0, -a, 0.3 if i % 2 else -0.3), parent=w, bevel=False)


def _carriage(k, t, level):
    lift = 0.24 if level >= 3 else 0.0                  # spades stowed once the trails ride rollers
    for sx in (-1, 1):
        _wheel(k, t, Vector((sx * 0.72, 0, 0.43)))
    k.tube("axle", (-0.66, 0, 0.43), (0.66, 0, 0.43), 0.045, G, parent=t)
    k.box("lower", (0.5, 0.56, 0.2), (0, -0.05, 0.5), G, parent=t, bevel=0.012)
    k.cylinder("pintle", 0.2, 0.06, (0, -0.1, 0.6), STEEL, segs=28, parent=t)
    cheek = [(-0.5, 0.64), (0.25, 0.64), (0.25, 0.8), (0.02, 0.97), (-0.22, 0.97), (-0.5, 0.82)]
    for sx in (-1, 1):
        k.plate("cheek", cheek, 0.03, sx * 0.17, G, parent=t, bevel=0.006)
        k.cylinder("trunnion_cap", 0.06, 0.04, (sx * 0.185, -0.1, 0.87), STEEL, segs=18,
                   rot=(0, sx * math.pi / 2, 0), parent=t)
        _bolts(k, [(sx * 0.187, y, 0.69) for y in (-0.42, -0.2, 0.02, 0.18)], (sx, 0, 0), t, r=0.012, mat=G)
        # spring equilibrator column
        k.tube("equil", (sx * 0.26, 0.12, 0.56), (sx * 0.26, 0.3, 1.0), 0.05, G, parent=t, segs=16)
        k.tube("equil_cap", (sx * 0.26, 0.3, 1.0), (sx * 0.26, 0.31, 1.03), 0.035, STEEL, parent=t, segs=12)

        if level == 1:          # level 1 has one small single trail instead (user 2026-11-22)
            continue
        # --- split tubular trail with spade
        a, b = Vector((sx * 0.26, -0.3, 0.52)), Vector((sx * 1.38, -3.2, 0.17))
        d = (b - a).normalized()
        side = Vector((sx * d.y, -sx * d.x, 0)).normalized()
        k.tube("hinge", (a.x, a.y, 0.4), (a.x, a.y, 0.64), 0.085, G, parent=t, segs=18)
        k.tube("trail", a, b, 0.066, G, radius_end=0.058, parent=t, segs=18, bevel=False)
        for f in (0.2, 0.55, 0.86):                         # riveted joint bands
            p = a.lerp(b, f)
            k.tube("band", p - d * 0.035, p + d * 0.035, 0.072, WORN, parent=t, segs=18, bevel=False)
        for f in (0.7, 0.9):                                # lifting handles
            p = a.lerp(b, f) + Vector((0, 0, 0.06))
            q = p + d * 0.2
            k.tube("h1", p, p + Vector((0, 0, 0.09)), 0.011, STEEL, parent=t, segs=8, bevel=False)
            k.tube("h2", q, q + Vector((0, 0, 0.09)), 0.011, STEEL, parent=t, segs=8, bevel=False)
            k.tube("h3", p + Vector((0, 0, 0.09)), q + Vector((0, 0, 0.09)), 0.011, STEEL, parent=t,
                   segs=8, bevel=False)
        sp = b + d * 0.12
        yaw = math.atan2(-d.x, d.y)
        k.box("spade", (0.4, 0.03, 0.42), (sp.x, sp.y, 0.06 + lift), WORN, rot=(math.radians(-25), 0, yaw),
              parent=t, bevel=0.006)
        k.box("spade_top", (0.4, 0.16, 0.025), (sp.x - d.x * 0.03, sp.y - d.y * 0.03, 0.26 + lift), WORN,
              rot=(math.radians(-25), 0, yaw), parent=t)
        for s2 in (-1, 1):
            k.beam("spade_web", b - d * 0.25 + side * s2 * 0.03, sp + side * s2 * 0.16 + Vector((0, 0, -0.1 + lift)),
                   (0.02, 0.1), WORN, parent=t, bevel=False)
        if sx < 0:      # towing eye on the left trail, cleaning rod sections on the right
            k.torus("lunette", 0.06, 0.02, b + d * 0.3 + Vector((0, 0, 0.06)), STEEL, parent=t,
                    segs=20, tube_segs=8)
            k.tube("lunette_arm", b, b + d * 0.25 + Vector((0, 0, 0.06)), 0.03, STEEL, parent=t, segs=10)
        else:
            for off in (-0.035, 0.035):
                k.tube("rod", a.lerp(b, 0.12) + Vector((0, 0, 0.085)) + side * off,
                       a.lerp(b, 0.62) + Vector((0, 0, 0.08)) + side * off, 0.014, "wood", parent=t,
                       segs=8, bevel=False)
            for f in (0.15, 0.58):
                p = a.lerp(b, f) + Vector((0, 0, 0.075))
                k.box("rod_clip", (0.12, 0.03, 0.03), p, STEEL, rot=(0, 0, yaw), parent=t, bevel=False)

    if level == 1:              # a single short box trail with a small spade
        a, b = Vector((0, -0.32, 0.5)), Vector((0, -2.1, 0.16))
        d = (b - a).normalized()
        k.beam("trail", a, b, (0.16, 0.13), G, section_end=(0.12, 0.1), parent=t, bevel=0.01)
        for f in (0.25, 0.6, 0.9):
            p = a.lerp(b, f)
            k.beam("band", p - d * 0.03, p + d * 0.03, (0.18, 0.15), WORN, parent=t, bevel=False)
        sp = b + d * 0.1
        k.box("spade", (0.3, 0.03, 0.3), (0, sp.y, 0.08), WORN, rot=(math.radians(-25), 0, 0), parent=t, bevel=0.006)
        k.torus("lunette", 0.06, 0.02, b + d * 0.22 + Vector((0, 0, 0.08)), STEEL, parent=t, segs=20, tube_segs=8)
    # elevation and traverse handwheels, both on the gunner's (left) side
    for y, z, r in ((-0.42, 0.9, 0.11), (-0.64, 0.74, 0.1)):
        k.torus("handwheel", r, 0.012, (-0.34, y, z), STEEL, rot=(0, math.pi / 2, 0), parent=t,
                segs=24, tube_segs=8)
        k.tube("hw_shaft", (-0.19, y, z), (-0.35, y, z), 0.016, STEEL, parent=t, segs=8)
        for a in (0, 2.1, 4.2):
            k.tube("hw_spoke", (-0.34, y, z), (-0.34, y + r * math.cos(a), z + r * math.sin(a)),
                   0.007, STEEL, parent=t, segs=6, bevel=False)
    k.box("gearbox", (0.1, 0.3, 0.16), (-0.24, -0.5, 0.78), G, parent=t, bevel=0.01)


def _shield(k, t, level):
    """Angular shield, leaning back 10 deg; hinged flap below the axle line."""
    sh = k.empty("shield", (0, 0.3, 0.47), parent=t)
    sh.rotation_euler = (math.radians(10), 0, 0)
    th = 0.012
    for sx in (-1, 1):
        panel = [(sx * 0.80, 0.0), (sx * 0.15, 0.0), (sx * 0.15, 0.80), (sx * 0.15, 0.93),
                 (sx * 0.60, 0.93), (sx * 0.80, 0.72)]
        k.prism("shield_panel", panel, th, G, parent=sh, bevel=False)
        # stiffening angle along the edge of the slot + rivets
        k.box("slot_edge", (0.03, 0.03, 0.8), (sx * 0.165, -0.02, 0.4), G, parent=sh, bevel=False)
        _bolts(k, [(sx * x, th / 2, z) for x, z in ((0.76, 0.06), (0.76, 0.36), (0.76, 0.64), (0.2, 0.1),
                                                     (0.2, 0.45), (0.2, 0.86), (0.48, 0.89), (0.5, 0.05))],
               (0, 1, 0), sh, r=0.012, mat=G)
        # stay from the shield back to the carriage
        k.tube("stay", (sx * 0.5, -0.01, 0.6), (sx * 0.18, -0.52, 0.34), 0.014, G, parent=sh, segs=8,
               bevel=False)
    k.prism("shield_bridge", [(-0.15, 0.80), (0.15, 0.80), (0.15, 0.93), (-0.15, 0.93)], th, G, parent=sh,
            bevel=False)
    top = k.empty("shield_top", (0, 0, 0.93), parent=sh)                # upper strip, folded back
    top.rotation_euler = (math.radians(28), 0, 0)
    k.prism("shield_top", [(-0.60, 0.0), (0.60, 0.0), (0.54, 0.13), (-0.54, 0.13)], th, G, parent=top,
            bevel=False)
    # sight port with its flap, on the gunner's side
    k.box("port_frame", (0.2, 0.012, 0.16), (-0.42, 0.012, 0.66), WORN, parent=sh, bevel=False)
    k.box("port", (0.14, 0.004, 0.1), (-0.42, 0.02, 0.66), "bore", parent=sh, bevel=False)
    flap = k.box("port_flap", (0.2, 0.01, 0.16), (-0.42, 0.06, 0.8), G, parent=sh, bevel=False)
    flap.rotation_euler = (math.radians(-55), 0, 0)
    # lower flap between the wheels, swung down
    k.box("lower_flap", (1.0, th, 0.27), (0, 0.3, 0.33), WORN, parent=t, bevel=False)
    for x in (-0.4, 0.0, 0.4):
        k.cylinder("flap_hinge", 0.012, 0.08, (x - 0.04, 0.3, 0.468), STEEL, segs=8,
                   rot=(0, math.pi / 2, 0), parent=t, bevel=False)
    fort.decal(k, "decal_zis_no", "Б-103", sh, centre=(0.47, th / 2 + 0.002, 0.24), u=(-1, 0, 0),
               v=(0, 0, 1), height=0.11)
    yf = 0.066 if level >= 4 else th / 2 + 0.002          # in front of the appliqué from level 4
    defender.emblem(k, sh, (0.47, yf, 0.6), (0, 1, 0), h=0.3)
    defender.emblem(k, sh, (0.47, -th / 2 - 0.002, 0.6), (0, -1, 0), h=0.3)

    if level >= 4:      # appliqué armour on spacers, a taller crest and folding side wings
        crest = k.empty("shield_crest", (0, 0.0, 0.93), parent=sh)
        crest.rotation_euler = (math.radians(28), 0, 0)
        k.prism("crest_plate", [(-0.6, 0.12), (0.6, 0.12), (0.5, 0.36), (-0.5, 0.36)], th * 1.4, WORN, y=0.02,
                parent=crest, bevel=False)
        _bolts(k, [(x, 0.03, 0.18) for x in (-0.45, -0.15, 0.15, 0.45)], (0, 1, 0), crest, r=0.014, mat=TRIM)
        for sx in (-1, 1):
            plate = [(sx * 0.77, 0.05), (sx * 0.2, 0.05), (sx * 0.2, 0.86), (sx * 0.58, 0.86),
                     (sx * 0.77, 0.67)]
            k.prism("applique", plate, 0.016, "steel_worn" if sx > 0 else WORN, y=0.05, parent=sh,
                    bevel=False)
            _bolts(k, [(sx * x, 0.058, z) for x, z in ((0.7, 0.12), (0.7, 0.6), (0.27, 0.12), (0.27, 0.78),
                                                        (0.5, 0.8), (0.48, 0.42))],
                   (0, 1, 0), sh, r=0.018, mat=STEEL)
            wing = k.empty("wing", (sx * 0.8, 0, 0.0), parent=sh)
            wing.rotation_euler = (0, 0, -sx * math.radians(38))
            k.prism("wing_plate", [(0.0, 0.02), (sx * 0.34, 0.02), (sx * 0.34, 0.56), (0.0, 0.7)], th, WORN,
                    parent=wing, bevel=False)
            for z in (0.12, 0.4, 0.62):
                k.cylinder("wing_hinge", 0.014, 0.07, (0, 0, z - 0.035), STEEL, segs=8, parent=wing,
                           bevel=False)


def _elevating_mass(k, t, level):
    piv = k.empty("elevating", TRUNNION, parent=t)
    piv["node"] = "elevating"
    piv.rotation_euler = (math.radians(ELEVATION_DEG), 0, 0)
    rec = k.empty("recoil", parent=piv)
    rec["node"] = "recoil"
    _RIG["slide"] = [rec]

    k.tube("trunnion", (-0.17, 0, 0), (0.17, 0, 0), 0.05, STEEL, parent=piv)
    # trough cradle with the recoil brake under the barrel, recuperator above it
    k.box("cradle", (0.21, 1.55, 0.15), (0, 0.3, -0.14), G, parent=piv, bevel=0.01)
    k.tube("brake_cyl", (0, -0.42, -0.19), (0, 1.12, -0.19), 0.068, G, parent=piv, segs=18)
    k.tube("brake_cap", (0, 1.12, -0.19), (0, 1.17, -0.19), 0.045, STEEL, parent=piv, segs=8)
    zr = 0.16 if level < 3 else 0.24
    k.tube("recup", (0, -0.3, zr), (0, 1.32, zr), 0.07, G, parent=piv, segs=20)
    k.tube("recup_cap", (0, 1.32, zr), (0, 1.37, zr), 0.05, STEEL, parent=piv, segs=8)
    for y in (-0.22, 0.98):
        k.box("yoke", (0.25, 0.07, 0.46), (0, y, 0.0), G, parent=piv, bevel=0.01)
        _bolts(k, [(x, y + 0.036, z) for x in (-0.09, 0.09) for z in (-0.18, 0.18)], (0, 1, 0), piv,
               r=0.012, mat=G)
    for sx in (-1, 1):
        _bolts(k, [(sx * 0.106, y, -0.12) for y in (-0.3, 0.1, 0.5, 0.85)], (sx, 0, 0), piv, r=0.011, mat=G)

    # --- barrel with the double-baffle brake
    BR = 1.5 if level >= 3 else 1.0                         # thicker barrel from level 3 (user 2026-11-22)
    barrel = [(y, r * BR) for y, r in [(-0.62, 0.0), (-0.62, 0.088), (0.15, 0.088), (0.32, 0.074), (0.9, 0.062),
                                       (2.72, 0.05), (2.72, 0.0)]]
    k.lathe("barrel", barrel, BARREL, segs=32, parent=rec)
    for i in range(level):                                  # crimson rings: one per level
        y0, y1 = 2.0 - i * 0.14, 2.07 - i * 0.14
        r = (0.062 + (0.05 - 0.062) * ((y0 + y1) / 2 - 0.9) / 1.82) * BR + 0.0025
        k.lathe("ring", [(y0, 0.0), (y0, r), (y1, r), (y1, 0.0)], STYLE[level]["ring"], segs=32, parent=rec)
    if level >= 4:      # bigger three-baffle brake
        ys, rb, end = (2.79, 2.92, 3.05), 0.108 * BR, 3.13
    else:
        ys, rb, end = (2.8, 2.93), 0.086 * BR, 3.03
    k.lathe("brake", [(2.68, 0.0), (2.68, 0.056 * BR), (2.74, rb), (end - 0.03, rb), (end, rb * 0.72),
                      (end, 0.0)], SOOT, segs=28, parent=rec)
    for sx in (-1, 1):
        for y in ys:
            k.box("brake_port", (0.012, 0.085, rb), (sx * (rb - 0.003), y, 0), "bore", parent=rec, bevel=False)
    if level == 5:
        for y in (2.71, end - 0.015):
            k.lathe("brake_band", [(y - 0.012, 0.0), (y - 0.012, rb + 0.006), (y + 0.012, rb + 0.006),
                                   (y + 0.012, 0.0)], TRIM, segs=28, parent=rec)
    k.cylinder("bore", 0.04 * BR, 0.008, (0, end + 0.001, 0), "bore", segs=20, rot=(-math.pi / 2, 0, 0),
               parent=rec, bevel=False)
    muzzle = k.empty("muzzle", (0, end + 0.02, 0), parent=rec)
    muzzle["marker"] = "muzzle"

    # --- breech ring with a vertical sliding block, lever on the right
    k.box("breech_ring", (0.27, 0.3, 0.3), (0, -0.74, 0), WORN, parent=rec, bevel=0.015)
    k.box("breech_block", (0.13, 0.1, 0.2), (0, -0.87, -0.02), STEEL, parent=rec, bevel=0.008)
    k.tube("lever", (0.15, -0.72, 0.02), (0.22, -0.92, 0.14), 0.012, STEEL, parent=rec, segs=8)
    k.cylinder("lever_knob", 0.02, 0.05, (0.22, -0.92, 0.12), "rubber", segs=10, parent=rec)
    k.box("guard", (0.02, 0.5, 0.2), (0.15, -0.95, -0.06), G, parent=piv, bevel=False)    # recoil guard

    _sights(k, t, piv, level)
    if level >= 3:
        _hydraulics(k, piv, level)
    if level >= 5:
        _rammer(k, t, piv)


def _sights(k, t, piv, level):
    if level == 1:          # plain telescope on two brackets
        k.tube("tele", (-0.2, -0.5, 0.2), (-0.2, 0.15, 0.2), 0.024, STEEL, parent=piv, segs=12)
        k.tube("tele_hood", (-0.2, 0.15, 0.2), (-0.2, 0.22, 0.2), 0.03, STEEL, parent=piv, segs=12)
        for y in (-0.3, 0.0):
            k.box("tele_bracket", (0.06, 0.04, 0.12), (-0.16, y, 0.13), G, parent=piv, bevel=False)
        return
    # brass panoramic sight on the left of the cradle
    k.box("sight_mount", (0.07, 0.16, 0.2), (-0.16, -0.28, 0.02), G, parent=piv)
    k.tube("sight_stem", (-0.2, -0.28, 0.1), (-0.2, -0.28, 0.42), 0.022, TRIM, parent=piv, segs=12)
    k.cylinder("sight_drum", 0.05, 0.05, (-0.2, -0.28, 0.3), TRIM, segs=18, parent=piv)
    k.box("sight_head", (0.06, 0.08, 0.07), (-0.2, -0.28, 0.45), TRIM, parent=piv)
    k.cylinder("sight_lens", 0.02, 0.004, (-0.2, -0.239, 0.45), "glass", segs=12,
               rot=(-math.pi / 2, 0, 0), parent=piv, bevel=False)
    k.tube("sight_eyepiece", (-0.2, -0.36, 0.38), (-0.2, -0.46, 0.36), 0.016, "rubber", parent=piv, segs=10)
    k.box("sight_box", (0.1, 0.12, 0.1), (-0.2, -0.36, 0.14), G, parent=piv)
    # brass elevation quadrant on the left cheek, a pointer on the cradle sweeps over it
    c = TRUNNION
    fan = [(c.y, c.z)] + [(c.y - 0.34 * math.cos(math.radians(a)), c.z + 0.34 * math.sin(math.radians(a)))
                          for a in range(-25, 50, 5)]
    k.plate("quadrant", fan, 0.012, -0.212, TRIM, parent=t, bevel=False)
    for a in range(-20, 50, 10):
        r0 = 0.3
        p = Vector((-0.22, c.y - r0 * math.cos(math.radians(a)), c.z + r0 * math.sin(math.radians(a))))
        k.box("quadrant_tick", (0.004, 0.006, 0.04), p, "iron_black", rot=(math.radians(-a) + math.pi / 2, 0, 0),
              parent=t, bevel=False)
    k.beam("quadrant_pointer", (-0.21, 0, 0), (-0.21, -0.33, 0.0), (0.012, 0.02), "iron_black", parent=piv,
           bevel=False)


def _hydraulics(k, piv, level):
    """Level 3+: a hydraulic accumulator beside the recuperator with a pressure gauge and
    copper lines down to the recoil brake: the gun runs out faster, so it fires faster."""
    from . import faction as fx
    x, z = 0.155, 0.2
    k.tube("accumulator", (x, -0.12, z), (x, 0.72, z), 0.055, G, parent=piv, segs=18)
    for y in (-0.12, 0.72):
        k.cylinder("acc_cap", 0.06, 0.03, (x, y - 0.015, z), TRIM, segs=18, rot=(-math.pi / 2, 0, 0), parent=piv)
    for y in (0.1, 0.5):
        k.tube("acc_strap", (x, y - 0.02, z), (x, y + 0.02, z), 0.062, TRIM, parent=piv, segs=18, bevel=False)
        k.box("acc_clamp", (0.06, 0.04, 0.03), (x - 0.06, y, z - 0.03), STEEL, parent=piv, bevel=False)
    fx.gauge(k, piv, (x + 0.02, -0.16, z + 0.07), (0.2, -0.6, 1.0), r=0.06)
    k.hose("hyd_line", [(x, 0.75, z), (x + 0.02, 0.85, 0.12), (0.09, 0.98, -0.08), (0.05, 1.08, -0.17)], 0.014,
           "copper", parent=piv)
    k.hose("hyd_line", [(x - 0.03, 0.74, z + 0.02), (0.07, 0.95, 0.2), (0.03, 1.2, 0.18)], 0.011, "copper",
           parent=piv)
    k.cylinder("hyd_valve", 0.025, 0.06, (x, 0.3, z + 0.05), TRIM, segs=12, parent=piv)
    if level >= 4:          # a second, bigger reservoir: the line now runs to both cylinders
        k.tube("reservoir", (-x, 0.2, z - 0.02), (-x, 0.7, z - 0.02), 0.045, G, parent=piv, segs=16)
        k.cylinder("res_cap", 0.05, 0.02, (-x, 0.7, z - 0.02), TRIM, segs=16, rot=(-math.pi / 2, 0, 0),
                   parent=piv)
        k.hose("hyd_line", [(-x, 0.72, z - 0.02), (-0.08, 0.9, -0.05), (-0.05, 1.05, -0.17)], 0.012, "copper",
               parent=piv)


def _rammer(k, t, piv):
    """Level 5: a pneumatic rammer behind the breech, fed from an air bottle on the trail."""
    x, z = 0.3, 0.06
    k.tube("rammer_cyl", (x, -0.55, z), (x, -1.45, z), 0.055, G, parent=piv, segs=18)
    for y in (-0.55, -1.45):
        k.tube("rammer_cap", (x, y - 0.02, z), (x, y + 0.02, z), 0.064, TRIM, parent=piv, segs=18, bevel=False)
    k.box("rammer_bracket", (0.16, 0.08, 0.06), (0.21, -0.6, z - 0.02), G, parent=piv, bevel=False)
    k.tube("rammer_rod", (x, -1.45, z), (x, -1.62, z), 0.018, "chrome", parent=piv, segs=10)
    k.beam("rammer_arm", (x, -1.62, z), (0.0, -1.62, -0.02), (0.04, 0.05), G, parent=piv, bevel=False)
    k.box("rammer_tray", (0.17, 0.5, 0.02), (0.0, -1.62, -0.1), TRIM, parent=piv, bevel=False)
    for sx in (-1, 1):
        k.box("tray_lip", (0.012, 0.5, 0.05), (sx * 0.085, -1.62, -0.08), TRIM, parent=piv, bevel=False)
    k.box("tray_hanger", (0.03, 0.03, 0.18), (0.0, -1.38, -0.03), G, parent=piv, bevel=False)
    # air bottle on saddles above the right trail, with a brass valve and gauge
    a, b = Vector((0.26, -0.3, 0.52)), Vector((1.38, -3.2, 0.17))
    d = (b - a).normalized()
    p0, p1 = a.lerp(b, 0.3) + Vector((0.05, 0, 0.24)), a.lerp(b, 0.58) + Vector((0.05, 0, 0.21))
    k.tube("air_bottle", p0, p1, 0.085, "iron_black", parent=t, segs=18)
    for f in (0.0, 1.0):
        k.tube("bottle_band", p0.lerp(p1, f) - d * 0.02, p0.lerp(p1, f) + d * 0.02, 0.09, TRIM, parent=t, segs=18,
               bevel=False)
    for f in (0.2, 0.8):
        q = p0.lerp(p1, f)
        k.box("bottle_saddle", (0.14, 0.05, 0.16), q - Vector((0, 0, 0.1)), G, rot=(0, 0, math.atan2(-d.x, d.y)),
              parent=t, bevel=False)
    k.cylinder("bottle_valve", 0.03, 0.07, p0 - d * 0.02, TRIM, segs=12, parent=t)
    k.hose("air_line", [p0 - d * 0.03 + Vector((0, 0, 0.07)), Vector((0.36, -1.0, 0.85)),
                        Vector((0.32, -1.58, 0.62))], 0.013, "rubber", parent=t)


def _traverse_gun(k, gun, level):
    """Parts that turn with the gun: trail rollers (L3+), the traverse pinion (L4+)."""
    deck = STYLE[level]["deck"]
    c0 = Vector((0, -GUN_SHIFT, 0))
    if level >= 3:
        for sx in (-1, 1):
            a, b = Vector((sx * 0.26, -0.3, 0.52)), Vector((sx * 1.38, -3.2, 0.17))
            d = (b - a).normalized()
            p = b - d * 0.16
            u = Vector((p.x - c0.x, p.y - c0.y, 0)).normalized()
            rc = Vector((p.x, p.y, 0.07 - deck + 0.085))
            k.tube("trail_roller", rc - u * 0.05, rc + u * 0.05, 0.085, STEEL if level < 5 else TRIM, parent=gun,
                   segs=20)
            k.tube("roller_axle", rc - u * 0.09, rc + u * 0.09, 0.018, STEEL, parent=gun, segs=8, bevel=False)
            for s2 in (-1, 1):
                k.beam("roller_fork", p + u * s2 * 0.08, rc + u * s2 * 0.08, (0.03, 0.06), G, parent=gun, bevel=False)
    if level >= 4:
        q = Vector((-0.99, -2.19, 0)) - c0
        u = Vector((q.x, q.y, 0)).normalized()
        pc = c0 + u * (RING_R + 0.1)
        z0 = 0.03 - deck
        k.cylinder("pinion", 0.08, 0.07, (pc.x, pc.y, z0), STEEL, segs=20, parent=gun)
        for i in range(10):
            ang = 2 * math.pi * i / 10
            k.box("pinion_tooth", (0.04, 0.03, 0.07), (pc.x + 0.085 * math.cos(ang), pc.y + 0.085 * math.sin(ang),
                                                       z0 + 0.035), STEEL, rot=(0, 0, ang), parent=gun, bevel=False)
        top = Vector((pc.x, pc.y, 0.42))
        k.tube("pinion_shaft", (pc.x, pc.y, z0 + 0.07), top, 0.025, STEEL, parent=gun, segs=10)
        k.box("bevel_box", (0.14, 0.14, 0.12), top, G, parent=gun, bevel=0.01)
        k.tube("drive_shaft", top + Vector((0.05, 0.04, 0.02)), Vector((-0.28, -0.62, 0.72)), 0.02, TRIM, parent=gun,
               segs=10)
        k.beam("pinion_bracket", top + Vector((0.03, 0, 0)), Vector((-0.82, -1.85, 0.36)), (0.05, 0.04), G,
               parent=gun, bevel=False)


def _traverse_ground(k, root, level, deck_r=DECK_R, ring_r=RING_R, track_r=TRACK_R, deck_kind="planks",
                     trim=None):
    """The ground under the gun: bare soil, a plank deck, a roller track, a toothed ring,
    a steel turntable on a ball race."""
    deck = STYLE[level]["deck"]
    TRIM = trim or globals()["TRIM"]
    DECK_R, RING_R, TRACK_R = deck_r, ring_r, track_r
    if 2 <= level <= 4 and deck_kind == "stone":     # flagstones laid in rings
        _flagstones(k, root, deck_r, deck, level)
    elif 2 <= level <= 4:     # plank deck, boards across, two bearers showing at the edge
        w = 0.24
        n = int(2 * DECK_R / w)
        for i in range(n):
            x = -DECK_R + (i + 0.5) * (2 * DECK_R / n)
            hl = math.sqrt(max(DECK_R ** 2 - x ** 2, 0.04))
            k.box("deck_plank", (2 * DECK_R / n - 0.012, 2 * hl, deck), (x, (i % 3 - 1) * 0.02, deck / 2),
                  {2: "timber_honey", 3: "timber_red", 4: "timber_oak"}[level],
                  rot=(0, 0, 0.0), parent=root, bevel=0.004)
        for y in (-0.7, 0.7):
            k.box("deck_bearer", (2 * math.sqrt(DECK_R ** 2 - y ** 2) + 0.1, 0.12, 0.04), (0, y, 0.0), "timber_tarred",
                  parent=root, bevel=False)
    if level == 5:          # steel turntable riding on a visible ball race, brass rim
        k.cylinder("turntable", DECK_R, deck, (0, 0, 0), "iron_black", segs=64, parent=root)
        k.torus("turntable_rim", DECK_R, 0.02, (0, 0, deck - 0.01), TRIM, parent=root, segs=64, tube_segs=6)
        k.torus("race_ring", DECK_R + 0.1, 0.03, (0, 0, 0.02), "steel_worn", parent=root, segs=64, tube_segs=6)
        for i in range(48):
            ang = 2 * math.pi * i / 48
            k.cylinder("race_ball", 0.025, 0.04, (math.cos(ang) * (DECK_R + 0.045), math.sin(ang) * (DECK_R + 0.045), 0.0),
                       "chrome", segs=10, parent=root, bevel=False)
        for i in range(24):
            ang = 2 * math.pi * (i + 0.5) / 24
            k.cylinder("deck_rivet", 0.02, 0.012, (math.cos(ang) * (DECK_R - 0.08), math.sin(ang) * (DECK_R - 0.08), deck),
                       TRIM, segs=8, parent=root, bevel=False)
        k.cylinder("centre_boss", 0.22, 0.03, (0, 0, deck), TRIM, segs=24, parent=root)
    if level >= 3:          # roller track for the trails: sleepers, a rail from level 4
        n = int(2 * math.pi * TRACK_R / 0.35)
        for i in range(n):
            ang = 2 * math.pi * i / n
            k.box("sleeper", (0.42, 0.13, 0.05), (math.cos(ang) * TRACK_R, math.sin(ang) * TRACK_R, 0.025),
                  "timber_tarred" if level >= 4 else "timber_raw", rot=(0, 0, ang), parent=root, bevel=0.004)
        if level == 3:
            for i in range(n):
                a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
                k.beam("track_plank", (math.cos(a0) * TRACK_R, math.sin(a0) * TRACK_R, 0.06),
                       (math.cos(a1) * TRACK_R, math.sin(a1) * TRACK_R, 0.06), (0.2, 0.02), "timber_honey",
                       parent=root, bevel=False)
        else:
            for dr in (-0.07, 0.07):
                k.torus("rail", TRACK_R + dr, 0.018, (0, 0, 0.068), "steel_worn" if level == 4 else "chrome",
                        parent=root, segs=max(96, int(TRACK_R * 40)), tube_segs=6)
    if level >= 4:          # toothed traverse ring the pinion walks around
        k.torus("gear_ring", RING_R, 0.03, (0, 0, 0.04), "iron_black", parent=root, segs=80, tube_segs=6)
        n = int(2 * math.pi * RING_R / 0.1)
        for i in range(n):
            ang = 2 * math.pi * i / n
            k.box("ring_tooth", (0.05, 0.03, 0.06), (math.cos(ang) * (RING_R + 0.035), math.sin(ang) * (RING_R + 0.035),
                                                     0.04), "steel_worn", rot=(0, 0, ang), parent=root, bevel=False)


def _flagstones(k, root, r, top, level):
    """Dressed stone slabs in concentric rings: a heavier gun's platform."""
    mat = "stone"
    rings = int(r / 0.55)
    k.cylinder("mortar_bed", r + 0.04, top * 0.6, (0, 0, 0), "iron_black", segs=64, parent=root, bevel=False)
    k.cylinder("stone_core", 0.28, top, (0, 0, 0), mat, segs=16, parent=root)
    for i in range(1, rings + 1):
        r0, r1 = 0.3 + (i - 1) * (r - 0.3) / rings, 0.3 + i * (r - 0.3) / rings
        n = max(6, int(2 * math.pi * (r0 + r1) / 2 / 0.6))
        off = 0.5 * (i % 2)
        for j in range(n):
            g = 0.025 / ((r0 + r1) / 2)                  # 5 cm joints
            a0 = 2 * math.pi * (j + off) / n + g
            a1 = 2 * math.pi * (j + 1 + off) / n - g
            pts = [(r0 + 0.025, a0), (r1 - 0.025, a0), (r1 - 0.025, a1), (r0 + 0.025, a1)]
            h = top * (0.9 + 0.2 * ((i * 7 + j * 13) % 5) / 4)
            outline = [(rr * math.cos(aa), rr * math.sin(aa)) for rr, aa in pts]
            e = k.empty("flag", (0, 0, 0), parent=root)
            e.rotation_euler = (math.pi / 2, 0, 0)          # prism: x,z outline -> ground plane
            k.prism("flagstone", outline, h, mat, y=h / 2, parent=e, bevel=0.01)


# --------------------------------------------------------------------------
def _round76(k, parent, loc, rot, shell="paint_shell"):
    """76 mm unitary round, 0.72 m long. Local +Y = nose."""
    e = k.empty("round76", loc, parent=parent)
    e.rotation_euler = rot
    k.lathe("case", [(0.0, 0.0), (0.0, 0.05), (0.012, 0.05), (0.014, 0.045), (0.33, 0.043),
                     (0.385, 0.0392), (0.385, 0.0)], "brass", segs=20, parent=e)
    k.lathe("shell76", [(0.385, 0.0), (0.385, 0.0385), (0.6, 0.0385), (0.69, 0.02), (0.69, 0.0)],
            shell, segs=20, parent=e)
    k.lathe("band76", [(0.4, 0.0), (0.4, 0.04), (0.42, 0.04), (0.42, 0.0)], "copper", segs=20, parent=e)
    k.lathe("fuze76", [(0.69, 0.0), (0.69, 0.02), (0.72, 0.008), (0.722, 0.0)], "steel_worn", segs=14,
            parent=e)
    return e


def _spent_case(k, parent, loc, yaw, roll=0.0):
    e = k.empty("spent_case", loc, parent=parent)
    e.rotation_euler = (0, roll, yaw)
    k.lathe("case", [(0.0, 0.0), (0.0, 0.05), (0.012, 0.05), (0.014, 0.045), (0.33, 0.043),
                     (0.385, 0.0392), (0.385, 0.034), (0.02, 0.036), (0.02, 0.0)], "brass", segs=18,
            parent=e)


def _props(k, root, level):
    """Ammunition point on the sunny side toward the camera; it grows and changes with the
    level: wooden crates, more crates, a ready rack, steel lockers, black lockers with brass."""
    crate_mat = {1: ("wood", "wood"), 2: ("wood", "wood"), 3: ("wood", "timber_tarred"),
                 4: ("paint_steel", "steel_worn"), 5: ("iron_black", "brass")}[level]
    crate76 = dict(size=(0.38, 0.86, 0.26), text="76 ОФ  5 БР.", mat=crate_mat[0], batten=crate_mat[1],
                   decal_name="decal_crate76")
    r0 = 3.5
    stacks = {1: [(-116, 1), (-100, 1)],
              2: [(-122, 2), (-106, 2), (-90, 1)],
              3: [(-130, 3), (-114.5, 3), (-99, 2), (-83.5, 2)],           # more from level 3 (user 2026-11-22)
              4: [(-130, 3), (-114.5, 3), (-99, 3), (-83.5, 2), (-68, 2)],
              5: [(-130, 4), (-114.5, 3), (-99, 3), (-83.5, 3), (-68, 2)]}[level]
    shell = "paint_shell" if level < 3 else "paint_shell_dark"   # darker rounds from level 3
    for i, (deg, high) in enumerate(stacks):
        for j in range(high):
            p = pol(r0 + 0.02 * (j % 2), deg + (1.0 if j % 2 else 0), 0.26 * j)
            fort.crate(k, root, f"crate_{i}_{j}", p, math.radians(deg) + (0.07 if j % 2 else -0.04),
                       **crate76)
    deg0, top = stacks[0][0], 0.26 * stacks[0][1]
    for i in range(3 if level < 3 else 6):
        p = pol(r0 - 0.1 + 0.1 * (i % 3), deg0 + (15.5 if i >= 3 else 0),
                (top if i < 3 else 0.26 * stacks[1][1]) + 0.045)
        _round76(k, root, p - pol(0.36, deg0 + (15.5 if i >= 3 else 0) + 90),
                 (0, 0, math.radians(deg0 + (15.5 if i >= 3 else 0))), shell)
    if level <= 2:
        for i, dd in enumerate((-9.5, -7.5)):
            _round76(k, root, pol(r0 + 0.06 * i, deg0 + dd), (math.pi / 2, 0, i * 1.1))
    else:       # ready rack: rounds standing nose up in a frame
        rack_mat = {3: "timber_honey", 4: "paint_steel", 5: "iron_black"}[level]
        c = pol(r0 - 0.05, deg0 - 13.5)
        yaw = math.radians(deg0 - 13.5)
        rk = k.empty("ready_rack", c, parent=root)
        rk.rotation_euler = (0, 0, yaw)
        k.box("rack_base", (0.3, 0.9, 0.05), (0, 0, 0.025), rack_mat, parent=rk, bevel=0.005)
        for z in (0.25, 0.5):
            k.box("rack_rail", (0.3, 0.9, 0.03), (0, 0, z), rack_mat, parent=rk, bevel=0.004)
        for sy in (-1, 1):
            k.box("rack_post", (0.3, 0.04, 0.55), (0, sy * 0.45, 0.275), rack_mat, parent=rk, bevel=0.004)
        for i in range(6):
            _round76(k, rk, Vector((0.0, -0.36 + i * 0.145, 0.05)), (math.pi / 2, 0, 0), shell)
        if level == 5:
            k.box("rack_trim", (0.32, 0.92, 0.012), (0, 0, 0.51), "brass", parent=rk, bevel=False)
    # spent cases thrown clear to the far left; the heap grows with the level
    heap = [(0.0, 172, 25, 0.0), (0.22, 177, -18, 0.0), (0.05, 183, 60, 0.0), (0.3, 168, 5, 0.0),
            (0.16, 188, -40, 0.0), (0.1, 193, 15, 0.0), (0.28, 181, 80, 0.0), (0.02, 164, -10, 0.0),
            (0.12, 176, 40, 0.2), (0.34, 186, -70, 0.0), (0.06, 159, 30, 0.0), (0.2, 196, -5, 0.0),
            (0.38, 173, 55, 0.0), (0.09, 169, -60, 0.2)]
    for i, (dr, deg, skew, roll) in enumerate(heap[:3 + 2 * level]):
        c = pol(3.45 + dr * 0.7, deg)
        c.z = 0.05 + (0.08 if roll else 0.0)
        _spent_case(k, root, c, math.radians(deg + skew), roll)
    # entrenching shovel stuck in the ground, bucket
    a = pol(r0 + 0.28, -158)
    k.tube("shovel_shaft", a + Vector((0, 0, 0.12)), a + Vector((0.08, 0.05, 1.05)), 0.018, "wood",
           parent=root, segs=10)
    k.box("shovel_blade", (0.19, 0.012, 0.26), a + Vector((0, 0, 0.1)), "steel_worn",
          rot=(0.06, 0, 0.9), parent=root, bevel=False)
    b = pol(r0 + 0.25, -70)
    k.cylinder("bucket", 0.11, 0.26, b, "steel_worn", segs=20, parent=root, radius_top=0.14)
    k.torus("bucket_rim", 0.14, 0.008, (b.x, b.y, 0.26), "steel_worn", parent=root, segs=20, tube_segs=6)
