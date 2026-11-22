"""Towed 155 mm howitzer (bg: „Гаубица“), built at real size from public dimensions
(barrel 5.1 m, firing length ~9 m, width 3.7 m), in firing position: wheels lifted, two
front stabilisers, two rear trails with spades, low saddle, four-tube cradle. A defenders'
gun of the parallel world: the white tower on a blue shield on both cheeks.

Each level changes the paint and adds a new kind of mechanism; the ground under the gun
changes with it (2026-11-17 plan):
Level 1: worn olive, plain telescope; spades and pads dug into bare soil.
Level 2: fresh olive, brass dial sight and a brass aiming circle on a tripod; a stone
         platform under the gun.
Level 3: camouflage, hydraulic accumulators with gauges on the saddle; a ring rail under
         the pads and trails, which ride on flanged shoes, spades stowed.
Level 4: grey steel, longer barrel with a three-baffle brake and brass bands on the
         cradle tubes; a toothed traverse ring around the platform, pinion and drive shaft.
Level 5: black steel and brass, a steam crane with its own boiler lifts the shell to the
         breech; steel turntable on a ball race.

Returns (root, turret). `turret` (the whole gun) rotates around Z to aim;
crates and ground stay still. Frame +Y is the direction of fire.
"""
import math

import bpy
from mathutils import Matrix, Vector

from .. import fort
from .. import materials_photoreal as mp
from ..fort import pol
from ..geo import Kit
from . import defender

LEVELS = (1, 2, 3, 4, 5)
STYLES = ("photoreal",)
FRAME_M = 12.0          # real metres across the photo-style preview frame
TARGET_Z = 0.9          # height the preview camera is centred on
SPRITE_FRAME_M = 20.0   # game sprites: metres across the render (room for the barrel's shadow)
SWEEP_M = 3.9           # nothing static may stand inside this radius: the gun turns through it
FOOTPRINT_M = 6.0       # all static art stays inside this radius (one 12 m tile)
GUN_SHIFT = 0.9         # the gun sits this far forward of the rotation centre, so the
                        # spades and the stabiliser pads sweep the same 3.9 m circle
HERO_DIR = 12           # of 16: barrel toward screen lower-right, sunlit side to camera
ELEVATION_DEG = 20.0
DECK_R = 2.0            # stone platform / turntable
RING_R = 2.08           # toothed traverse ring (level 4+)
TRACK_R = 3.86          # ring rail under the pads and trail shoes (level 3+)

STYLE = {
    1: dict(g="paint_olive_worn", worn="paint_olive_worn", barrel="paint_barrel", soot="paint_soot",
            trim="gunmetal", ring="paint_red", deck=0.0),
    2: dict(g="paint_olive", worn="paint_olive_worn", barrel="paint_barrel", soot="paint_soot",
            trim="brass", ring="paint_red", deck=0.08),
    3: dict(g="paint_green_dark", worn="paint_olive_worn", barrel="paint_green_dark_barrel", soot="paint_soot",
            trim="brass", ring="paint_red", deck=0.08),
    4: dict(g="paint_steel", worn="steel_worn", barrel="gunmetal", soot="paint_soot",
            trim="brass", ring="paint_red", deck=0.08),
    5: dict(g="iron_black", worn="iron_forged", barrel="iron_black", soot="iron_black",
            trim="brass", ring="brass", deck=0.08),
}
OLIVE, WORN, STEEL, BARREL, SOOT, TRIM = "paint_olive", "paint_olive_worn", "gunmetal", "paint_barrel", \
    "paint_soot", "brass"
FIRE = [-0.85, -0.72, -0.54, -0.36, -0.2, -0.07]       # recoil slide (m) per frame
FIRE_FRAMES = len(FIRE)
RELEASE_FRAME = 1
RELOAD_FROM = 2
FIRE_FPS = 14
LOOP = False
_RIG = {}


def build(style, level=1):
    global OLIVE, WORN, BARREL, SOOT, TRIM
    st = STYLE[level]
    OLIVE, WORN, BARREL, SOOT, TRIM = st["g"], st["worn"], st["barrel"], st["soot"], st["trim"]
    k = Kit(style)
    root = k.empty("howitzer")
    # Node empties carry a "node" tag: the game export turns each into one mesh
    # node (turret yaws, elevating pitches about the trunnions, recoil slides).
    turret = k.empty("turret", parent=root)
    turret["node"] = "turret"
    gun = k.empty("gun", (0, GUN_SHIFT, st["deck"]), parent=turret)
    mp.set_reference(gun)

    _carriage(k, gun, level)
    _saddle(k, gun, level)
    _elevating_mass(k, gun, level)
    _traverse_gun(k, gun, level)
    if level >= 3:
        _hydraulics(k, gun, level)
    if level >= 5:
        _steam_crane(k, gun)
    from .zis3 import _traverse_ground
    _traverse_ground(k, root, level, deck_r=DECK_R, ring_r=RING_R, track_r=TRACK_R, deck_kind="stone",
                     trim=TRIM)
    _props(k, root, level)
    return root, turret


def ground(level):
    """The soil patch the tower sprite brings with it."""
    from ..terrain import Patch
    return Patch(r_solid=FOOTPRINT_M, r_out=FOOTPRINT_M + 0.8, r_bare=SWEEP_M + 0.6 + 0.15 * (level - 1))


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
    rec = _RIG["slide"]
    if scene is not None and rec.animation_data is not None:
        scene.frame_set(f)
    else:
        rec.location = (0, 0.0 if f == 0 else FIRE[f - 1], 0)
    bpy.context.view_layer.update()


# --------------------------------------------------------------------------
def _bolts(k, pts, axis, parent, r=0.017, mat=None):
    """Hex bolt heads at pts, sticking out along `axis`."""
    mat = mat or OLIVE
    rot = Vector(axis).to_track_quat("Z", "Y").to_euler()
    for i, p in enumerate(pts):
        k.cylinder("bolt", r, 0.014, p, mat, segs=6, rot=rot, parent=parent, bevel=False,
                   smooth=False, outline=False)


def _carriage(k, t, level=1):
    T = 1.4 if level >= 3 else 1.0             # thicker stabilisers and trails from level 3 (user 2026-11-22)
    lift = 0.3 if level >= 3 else 0.0          # spades stowed once the trails ride shoes on the rail
    # firing platform on the ground + pedestal
    k.cylinder("baseplate", 0.72, 0.07, (0, 0.25, 0.0), WORN, segs=40, parent=t, radius_top=0.66)
    k.cylinder("pedestal", 0.30, 0.26, (0, 0.25, 0.06), OLIVE, segs=28, parent=t)
    for i in range(8):
        a = 2 * math.pi * i / 8
        k.beam("rib", (0.3 * math.cos(a), 0.25 + 0.3 * math.sin(a), 0.07),
               (0.64 * math.cos(a), 0.25 + 0.64 * math.sin(a), 0.07), (0.03, 0.16), WORN,
               section_end=(0.03, 0.02), parent=t, bevel=False)
    # welded body (lower carriage)
    k.box("body", (1.06, 1.7, 0.3), (0, 0.25, 0.47), OLIVE, parent=t, bevel=0.012)
    k.box("body_top", (0.9, 1.3, 0.05), (0, 0.2, 0.635), OLIVE, parent=t)
    k.box("body_nose", (0.7, 0.3, 0.2), (0, 1.2, 0.45), OLIVE, parent=t, bevel=0.012)
    for sx in (-1, 1):
        k.box("lightening", (0.02, 0.5, 0.12), (sx * 0.535, -0.1, 0.47), WORN, parent=t)
        _bolts(k, [(sx * 0.535, y, z) for y in (-0.5, 0.35, 0.65, 0.95) for z in (0.37, 0.57)],
               (sx, 0, 0), t)

    for sx in (-1, 1):
        # --- front stabiliser with ground pad
        a, b = Vector((sx * 0.48, 1.05, 0.5)), Vector((sx * 1.5, 2.7, 0.22))
        k.beam("stab", a, b, (0.17 * T, 0.2 * T), OLIVE, section_end=(0.12 * T, 0.13 * T), parent=t, bevel=0.01)
        pz = 0.09 - STYLE[level]["deck"] if level >= 3 else 0.0      # pad on the rail
        k.tube("stab_foot", b + Vector((0, 0, 0.03)), (b.x, b.y, pz + 0.04), 0.045 * T, STEEL, parent=t)
        k.cylinder("stab_pad", 0.21, 0.045, (b.x, b.y, pz), WORN, segs=28, parent=t,
                   radius_top=0.19)
        k.tube("stab_pin", (sx * 0.4, 1.05, 0.5), (sx * 0.58, 1.05, 0.5), 0.06, STEEL, parent=t)

        # --- rear trail with self-digging spade
        a, b = Vector((sx * 0.42, -0.45, 0.5)), Vector((sx * 1.3, -4.25, 0.36))
        k.beam("trail", a, b, (0.26 * T, 0.3 * T), OLIVE, section_end=(0.17 * T, 0.2 * T), parent=t, bevel=0.012)
        k.tube("trail_pin", (sx * 0.3, -0.5, 0.5), (sx * 0.6, -0.5, 0.5), 0.075, STEEL, parent=t)
        d = (b - a).normalized()
        side = Vector((sx * d.y, -sx * d.x, 0)).normalized()       # outward normal
        for f in (0.3, 0.62):                                       # lifting handles
            p = a.lerp(b, f) + Vector((0, 0, 0.13 * T))
            k.tube("h1", p, p + Vector((0, 0, 0.1)), 0.012, STEEL, parent=t, segs=8, bevel=False)
            k.tube("h2", p + d * 0.22, p + d * 0.22 + Vector((0, 0, 0.1)), 0.012, STEEL, parent=t,
                   segs=8, bevel=False)
            k.tube("h3", p + Vector((0, 0, 0.1)), p + d * 0.22 + Vector((0, 0, 0.1)), 0.012, STEEL,
                   parent=t, segs=8, bevel=False)
        _bolts(k, [a.lerp(b, f) + side * 0.11 * T * (1.15 - 0.4 * f) + Vector((0, 0, dz))
                   for f in (0.08, 0.14, 0.5, 0.56, 0.9) for dz in (-0.06, 0.06)], side, t)
        for f0, f1 in ((0.05, 0.42), (0.5, 0.82)):                   # pressed stiffening ribs
            for dz in (-0.07, 0.07):
                w0, w1 = 0.13 * T * (1.0 - 0.33 * f0), 0.13 * T * (1.0 - 0.33 * f1)
                k.beam("trail_rib", a.lerp(b, f0) + side * (w0 + 0.004) + Vector((0, 0, dz * (1 - 0.3 * f0))),
                       a.lerp(b, f1) + side * (w1 + 0.004) + Vector((0, 0, dz * (1 - 0.3 * f1))),
                       (0.02, 0.035), OLIVE, parent=t, bevel=False)
        k.hose("trail_cable", [a.lerp(b, f) + Vector((0, 0, 0.16 - 0.05 * f)) - side * 0.05
                               for f in (0.02, 0.2, 0.45, 0.7, 0.93)], 0.012, "hose", parent=t)
        # spade: blade dug into the soil, braces, damper
        sp = b + d * 0.25
        k.box("spade", (0.78, 0.05, 0.62), (sp.x, sp.y, 0.1 + lift), WORN,
              rot=(math.radians(-28), 0, math.atan2(-d.x, d.y)), parent=t, bevel=0.01)
        k.box("spade_lip", (0.78, 0.2, 0.04), (sp.x - d.x * 0.02, sp.y - d.y * 0.02, 0.4 + lift), WORN,
              rot=(math.radians(-28), 0, math.atan2(-d.x, d.y)), parent=t)
        for s2 in (-1, 1):
            k.beam("spade_brace", a.lerp(b, 0.86) + side * s2 * 0.06, sp + side * s2 * 0.3
                   + Vector((0, 0, -0.2 + lift)) - d * 0.06, (0.04, 0.12), WORN, parent=t, bevel=False)
        k.tube("damper", a.lerp(b, 0.7) + Vector((0, 0, 0.14)), sp + Vector((0, 0, 0.22 + lift)), 0.04,
               OLIVE, parent=t)
        k.tube("damper_rod", a.lerp(b, 0.62) + Vector((0, 0, 0.15)),
               a.lerp(b, 0.7) + Vector((0, 0, 0.14)), 0.02, "chrome", parent=t, segs=12)

        # --- road wheel, lifted off the ground on its suspension arm
        hub = Vector((sx * 1.16, 0.95, 0.66))               # tyre's inner face sits on the arm's hub boss
        k.beam("arm", (sx * 0.55, 0.3, 0.5), (sx * 0.98, 0.93, 0.64), (0.13, 0.22), OLIVE,
               section_end=(0.11, 0.16), parent=t, bevel=0.01)
        k.tube("axle", (sx * 0.9, 0.95, 0.66), hub, 0.09, STEEL, parent=t)
        k.cylinder("hub_boss", 0.15, 0.08, (sx * 0.94, 0.95, 0.66), OLIVE, segs=20,
                   rot=(0, sx * math.pi / 2, 0), parent=t)
        k.tube("gas_strut", (sx * 0.56, 0.75, 0.62), (sx * 0.95, 0.6, 0.58), 0.045, OLIVE, parent=t)
        _wheel(k, t, hub, sx, "rubber_black" if level >= 3 else "rubber")


def _wheel(k, t, hub, sx, rubber="rubber"):
    w = k.empty("wheel", hub, parent=t)
    w.rotation_euler = (0, 0, -math.pi / 2)     # local Y = axle
    tyre = [(-0.085, 0.0), (-0.085, 0.31), (-0.15, 0.35), (-0.158, 0.44), (-0.13, 0.5),
            (-0.07, 0.52), (0.07, 0.52), (0.13, 0.5), (0.158, 0.44), (0.15, 0.35),
            (0.085, 0.31), (0.085, 0.0)]
    k.lathe("tyre", tyre, rubber, segs=48, parent=w)
    rim = [(-0.11, 0.0), (-0.11, 0.1), (-0.095, 0.24), (-0.125, 0.3), (-0.125, 0.318),
           (0.125, 0.318), (0.125, 0.3), (0.095, 0.24), (0.11, 0.1), (0.11, 0.0)]
    k.lathe("rim", rim, OLIVE, segs=40, parent=w)
    for s in (-1, 1):
        k.cylinder("hubcap", 0.085, 0.05, (0, s * 0.11, 0), STEEL, segs=20,
                   rot=(-s * math.pi / 2, 0, 0), parent=w)
        for i in range(8):
            a = 2 * math.pi * i / 8
            k.cylinder("lug", 0.018, 0.03, (0.15 * math.cos(a), s * 0.1, 0.15 * math.sin(a)),
                       STEEL, segs=6, rot=(-s * math.pi / 2, 0, 0), parent=w, bevel=False,
                       smooth=False)
    n = 44
    for i in range(n):
        for row, off in ((-1, 0.0), (1, 0.5)):
            a = 2 * math.pi * (i + off) / n
            k.box("lug_block", (0.03, 0.125, 0.048),
                  (0.522 * math.cos(a), row * 0.068, 0.522 * math.sin(a)), rubber,
                  rot=(row * 0.25, -a, 0), parent=w, bevel=False)   # chevron twist about the radial axis


def _saddle(k, t, level=1):
    k.cylinder("ring", 0.5, 0.08, (0, 0.0, 0.64), STEEL, segs=40, parent=t)
    k.cylinder("ring_top", 0.56, 0.04, (0, 0.0, 0.7), OLIVE, segs=40, parent=t)
    cheek = [(-1.05, 0.74), (0.5, 0.74), (0.56, 0.86), (-0.15, 1.0), (-0.48, 1.25),
             (-0.9, 1.25), (-1.05, 1.02)]
    for sx in (-1, 1):
        k.plate("cheek", cheek, 0.05, sx * 0.42, OLIVE, parent=t, bevel=0.008)
        k.cylinder("trunnion_cap", 0.11, 0.06, (sx * 0.445, -0.7, 1.08), STEEL, segs=24,
                   rot=(0, sx * math.pi / 2, 0), parent=t)
        _bolts(k, [(sx * 0.447, -0.7 + 0.16 * math.cos(a), 1.08 + 0.16 * math.sin(a))
                   for a in [i * math.pi / 4 for i in range(8)]], (sx, 0, 0), t)
        _bolts(k, [(sx * 0.447, y, 0.79) for y in (-0.95, -0.6, -0.25, 0.1, 0.42)], (sx, 0, 0), t)
        k.box("step", (0.24, 0.5, 0.03), (sx * 0.56, -0.75, 0.75), WORN, parent=t)
    k.box("saddle_floor", (0.84, 1.5, 0.06), (0, -0.27, 0.75), OLIVE, parent=t)
    k.box("saddle_rear", (0.84, 0.05, 0.3), (0, -1.02, 0.88), OLIVE, parent=t)
    # elevation and traverse handwheels on the gunner's (left) side
    for y, z, r in ((-0.15, 1.05, 0.14), (0.2, 0.92, 0.11)):
        k.torus("handwheel", r, 0.013, (-0.56, y, z), STEEL, rot=(0, math.pi / 2, 0), parent=t,
                segs=28, tube_segs=8)
        k.tube("hw_shaft", (-0.44, y, z), (-0.57, y, z), 0.02, STEEL, parent=t, segs=10)
        for a in (0, 2.1, 4.2):
            k.tube("hw_spoke", (-0.56, y, z), (-0.56, y + r * math.cos(a), z + r * math.sin(a)),
                   0.008, STEEL, parent=t, segs=6, bevel=False)
    # unit number, stencilled on both cheeks
    for sx in (-1, 1):
        _decal(k, "decal_number", "Б-217", t, centre=(sx * 0.4465, 0.25, 0.8),
               u=(0, sx, 0), v=(0, 0, 1), height=0.1)
        defender.emblem(k, t, (sx * 0.449, -0.45, 1.0), (sx, 0, 0), h=0.34)


def _elevating_mass(k, t, level=1):
    piv = k.empty("elevating", (0, -0.7, 1.08), parent=t)
    piv["node"] = "elevating"
    el = math.radians(ELEVATION_DEG)
    piv.rotation_euler = (el, 0, 0)
    rec = k.empty("recoil", parent=piv)                     # barrel + breech slide back on firing
    rec["node"] = "recoil"
    _RIG["slide"] = rec
    z0 = 0.12                                               # bore axis above the trunnions

    def to_turret(p):                                       # local (pivot) -> turret space
        return Vector((0, -0.7, 1.08)) + Matrix.Rotation(el, 3, "X") @ Vector(p)

    k.tube("trunnion", (-0.42, 0, 0), (0.42, 0, 0), 0.075, STEEL, parent=piv)

    # --- barrel: chamber, taper, tube (level 3: 52-calibre tube, 0.85 m longer)
    ext = 0.85 if level >= 4 else 0.0
    tip = 4.55 + ext
    barrel = [(-0.5, 0.0), (-0.5, 0.185), (0.4, 0.185), (0.55, 0.165), (1.3, 0.15),
              (1.62, 0.118), (tip, 0.098), (tip, 0.0)]
    k.lathe("barrel", barrel, BARREL, segs=40, loc=(0, 0, z0), parent=rec)
    for i in range(level):                                  # crimson rings: one per level
        y0, y1 = 3.72 - i * 0.2, 3.82 - i * 0.2
        r = 0.118 + (0.098 - 0.118) * ((y0 + y1) / 2 - 1.62) / (tip - 1.62) + 0.0025
        k.lathe("ring", [(y0, 0.0), (y0, r), (y1, r), (y1, 0.0)], STYLE[level]["ring"], segs=40,
                loc=(0, 0, z0), parent=rec)

    # --- muzzle: a plain swell on levels 1-2, a brake from level 3
    if level <= 2:
        end = tip
        k.lathe("muzzle_swell", [(tip - 0.28, 0.0), (tip - 0.28, 0.1), (tip - 0.1, 0.112), (tip, 0.112),
                                 (tip, 0.0)], BARREL, segs=32, loc=(0, 0, z0), parent=rec)
    else:
        _brake(k, rec, tip, z0, level)
    k.cylinder("bore", 0.078, 0.01, (0, end + 0.001, z0) if level <= 2 else (0, _brake.end + 0.001, z0), "bore",
               segs=24, rot=(-math.pi / 2, 0, 0), parent=rec, bevel=False)
    end = end if level <= 2 else _brake.end
    muzzle = k.empty("muzzle", (0, end + 0.02, z0), parent=rec)
    muzzle["marker"] = "muzzle"
    if level >= 3:
        k.box("eye_lug", (0.06, 0.16, 0.1), (0, tip + 0.45, z0 - 0.21), BARREL, parent=rec)
        k.torus("tow_eye", 0.085, 0.024, (0, tip + 0.45, z0 - 0.33), STEEL, rot=(0, math.pi / 2, 0),
                parent=rec, segs=28, tube_segs=10)
    _breech_and_cradle(k, t, piv, rec, z0, level, to_turret)


def _brake(k, rec, tip, z0, level):
    k.lathe("brake_collar", [(tip - 0.05, 0.0), (tip - 0.05, 0.125), (tip + 0.05, 0.14),
                             (tip + 0.11, 0.14), (tip + 0.11, 0.0)],
            BARREL, segs=32, loc=(0, 0, z0), parent=rec)
    if level < 4:       # two baffles, top/bottom bars
        end = tip + 0.59
        k.lathe("brake_core", [(tip + 0.05, 0.0), (tip + 0.05, 0.108), (end, 0.108), (end, 0.0)],
                SOOT, segs=32, loc=(0, 0, z0), parent=rec)
        for y in (tip + 0.29, tip + 0.55):
            k.box("baffle", (0.5, 0.06, 0.3), (0, y, z0), SOOT, parent=rec, bevel=0.012)
        for s in (-1, 1):
            k.box("brake_bar", (0.2, 0.56, 0.035), (0, tip + 0.31, z0 + s * 0.155), SOOT,
                  parent=rec, bevel=0.008)
    else:               # high-efficiency brake: three wide baffles in a boxed frame
        end = tip + 0.86
        k.lathe("brake_core", [(tip + 0.05, 0.0), (tip + 0.05, 0.112), (end, 0.112), (end, 0.0)],
                SOOT, segs=32, loc=(0, 0, z0), parent=rec)
        for y in (tip + 0.3, tip + 0.56, tip + 0.82):
            k.box("baffle", (0.62, 0.065, 0.34), (0, y, z0), SOOT, parent=rec, bevel=0.012)
        for s in (-1, 1):
            k.box("brake_bar", (0.26, 0.82, 0.04), (0, tip + 0.45, z0 + s * 0.175), SOOT,
                  parent=rec, bevel=0.008)
            k.box("brake_cheek", (0.035, 0.82, 0.1), (s * 0.3, tip + 0.45, z0), SOOT,
                  parent=rec, bevel=0.008)
    _brake.end = end


def _breech_and_cradle(k, t, piv, rec, z0, level, to_turret):
    # --- breech ring, screw block, operating lever
    k.box("breech_ring", (0.5, 0.5, 0.5), (0, -0.62, z0), WORN, parent=rec, bevel=0.02)
    k.cylinder("breech_block", 0.16, 0.14, (0, -1.0, z0), STEEL, segs=28,
               rot=(-math.pi / 2, 0, 0), parent=rec)
    k.box("carrier", (0.16, 0.2, 0.36), (0.3, -0.9, z0), STEEL, parent=rec, bevel=0.012)
    k.tube("lever", (0.3, -0.95, z0 + 0.1), (0.42, -1.2, z0 + 0.34), 0.016, STEEL, parent=rec,
           segs=10)
    k.cylinder("lever_knob", 0.03, 0.07, (0.42, -1.2, z0 + 0.32), "rubber", segs=12, parent=rec)

    # --- cradle: body around the trunnions + four tubes + yokes
    k.box("cradle", (0.68, 1.05, 0.46), (0, 0.22, 0.08), OLIVE, parent=piv, bevel=0.015)
    k.box("cradle_top", (0.4, 0.8, 0.06), (0, 0.25, 0.34), OLIVE, parent=piv)
    for sx in (-1, 1):
        if level < 2:   # bare cradle: the recoil gear sits inside it, no tubes along the barrel
            _bolts(k, [(sx * 0.345, y, z) for y in (-0.2, 0.15, 0.5, 0.68) for z in (-0.08, 0.26)],
                   (sx, 0, 0), piv)
            a, b = Vector((sx * 0.5, 0.42, 0.84)), to_turret((sx * 0.36, 0.68, -0.1))
            k.tube("equil", a, a.lerp(b, 0.62), 0.058, OLIVE, parent=t, segs=20)
            k.tube("equil_rod", a.lerp(b, 0.62), b, 0.03, "chrome", parent=t, segs=16)
            k.tube("equil_foot", a - Vector((sx * 0.1, 0, 0)), a + Vector((sx * 0.05, 0, 0)), 0.06, STEEL,
                   parent=t, segs=16)
            continue
        k.tube("recup", (sx * 0.255, 0.55, 0.37), (sx * 0.255, 2.75, 0.37), 0.082, OLIVE, parent=piv,
               segs=24)
        k.tube("recup_cap", (sx * 0.255, 2.75, 0.37), (sx * 0.255, 2.83, 0.37), 0.06, STEEL,
               parent=piv, segs=6)
        k.tube("buffer", (sx * 0.275, 0.3, -0.13), (sx * 0.275, 2.45, -0.13), 0.092, OLIVE,
               parent=piv, segs=24)
        k.tube("buffer_cap", (sx * 0.275, 2.45, -0.13), (sx * 0.275, 2.53, -0.13), 0.065, STEEL,
               parent=piv, segs=6)
        _bolts(k, [(sx * 0.345, y, z) for y in (-0.2, 0.15, 0.5, 0.68) for z in (-0.08, 0.26)],
               (sx, 0, 0), piv)
        # elevating / balancing cylinder: saddle -> cradle
        a, b = Vector((sx * 0.5, 0.42, 0.84)), to_turret((sx * 0.4, 1.75, -0.08))
        k.tube("equil", a, a.lerp(b, 0.62), 0.058, OLIVE, parent=t, segs=20)
        k.tube("equil_rod", a.lerp(b, 0.62), b, 0.03, "chrome", parent=t, segs=16)
        k.tube("equil_eye", b - Vector((sx * 0.07, 0, 0)), b + Vector((sx * 0.05, 0, 0)), 0.05, STEEL,
               parent=t, segs=16)
        k.tube("equil_foot", a - Vector((sx * 0.1, 0, 0)), a + Vector((sx * 0.05, 0, 0)), 0.06, STEEL,
               parent=t, segs=16)
    for y, wdt, hgt in ((1.45, 0.76, 0.66), (2.4, 0.74, 0.64)) if level >= 2 else ():
        k.box("yoke", (wdt, 0.07, hgt), (0, y, 0.12), OLIVE, parent=piv, bevel=0.012)
        _bolts(k, [(x, y + 0.036, zz) for x in (-0.33, 0.0, 0.33) for zz in (-0.16, 0.4)]
               + [(x, y + 0.036, 0.12) for x in (-0.34, 0.34)], (0, 1, 0), piv)

    # --- gunner's sight (left), assistant's quadrant (right)
    k.box("sight_mount", (0.12, 0.22, 0.3), (-0.42, 0.05, 0.42), OLIVE, parent=piv)
    sc = STEEL if level == 1 else TRIM
    k.tube("scope", (-0.44, -0.08, 0.62), (-0.44, 0.3, 0.64), 0.04, sc, parent=piv, segs=16)
    k.cylinder("scope_lens", 0.034, 0.004, (-0.44, 0.301, 0.64), "glass", segs=16,
               rot=(-math.pi / 2, 0, 0), parent=piv, bevel=False)
    if level >= 2:      # brass dial sight: graduated drum on a turret head, an eyepiece
        k.cylinder("dial_base", 0.09, 0.06, (-0.44, -0.12, 0.66), TRIM, segs=24, parent=piv)
        k.cylinder("dial", 0.075, 0.04, (-0.44, -0.12, 0.72), "paint_white", segs=24, parent=piv, bevel=False)
        k.box("dial_head", (0.1, 0.12, 0.14), (-0.44, -0.12, 0.83), TRIM, parent=piv)
        k.tube("dial_eyepiece", (-0.44, -0.2, 0.8), (-0.44, -0.33, 0.78), 0.022, "rubber", parent=piv, segs=10)
        k.cylinder("dial_lens", 0.03, 0.004, (-0.44, -0.059, 0.85), "glass", segs=12, rot=(-math.pi / 2, 0, 0),
                   parent=piv, bevel=False)
        k.box("quadrant", (0.1, 0.24, 0.16), (0.41, 0.0, 0.38), OLIVE, parent=piv)
        k.cylinder("quadrant_face", 0.07, 0.01, (0.465, 0.0, 0.4), TRIM, segs=20, rot=(0, math.pi / 2, 0),
                   parent=piv, bevel=False)
    else:
        k.box("pantel", (0.1, 0.1, 0.2), (-0.44, -0.12, 0.7), STEEL, parent=piv)
        k.box("quadrant", (0.1, 0.24, 0.16), (0.41, 0.0, 0.38), OLIVE, parent=piv)
    # loading tray, swung clear to the left of the breech
    k.box("tray", (0.26, 0.9, 0.04), (-0.5, -1.25, -0.02), WORN, parent=piv)
    for s in (-1, 1):
        k.box("tray_wall", (0.025, 0.9, 0.08), (-0.5 + s * 0.125, -1.25, 0.02), WORN, parent=piv)
    k.beam("tray_arm", (-0.38, -0.5, -0.05), (-0.5, -0.9, -0.03), (0.06, 0.08), OLIVE, parent=piv)

    if level >= 4:      # brass bands clamp the four cradle tubes
        for sx in (-1, 1):
            for y in (1.0, 1.95):
                k.tube("tube_band", (sx * 0.255, y, 0.37), (sx * 0.255, y + 0.06, 0.37), 0.088, TRIM, parent=piv,
                       segs=24, bevel=False)
                k.tube("tube_band", (sx * 0.275, y, -0.13), (sx * 0.275, y + 0.06, -0.13), 0.098, TRIM,
                       parent=piv, segs=24, bevel=False)

    # --- hydraulic hoses and a cable
    k.hose("hose1", [to_turret(p) for p in ((0.36, 0.3, -0.3), (0.5, 0.0, -0.3), (0.48, -0.3, 0.0),
                                             (0.36, -0.1, 0.2))], 0.014, "hose", parent=t)
    k.hose("hose2", [(0.3, 0.9, 0.62), (0.38, 0.75, 0.82), (0.5, 0.55, 0.95), (0.52, 0.42, 0.9)],
           0.012, "hose", parent=t)
    if level >= 2:
        k.hose("hose3", [to_turret(p) for p in ((-0.3, 0.72, 0.3), (-0.33, 1.1, 0.46), (-0.3, 1.44, 0.4),
                                                (-0.26, 2.0, 0.47), (-0.26, 2.38, 0.46))], 0.011, "hose",
               parent=t)
    for sx in (-1, 1):
        _decal(k, "decal_calibre", "155 ММ", piv, centre=(sx * 0.3415, 0.25, 0.08),
               u=(0, sx, 0), v=(0, 0, 1), height=0.1)


def _rounds(k, root, centre, yaw, n=5):
    """Ready rounds standing fuze-up on a board."""
    k.box("board", (0.5, 0.25 * n, 0.035), (centre.x, centre.y, 0.02), "wood", rot=(0, 0, yaw),
          parent=root)
    body = [(0.0, 0.0), (0.0, 0.068), (0.035, 0.0775), (0.44, 0.0775), (0.58, 0.066),
            (0.69, 0.042), (0.69, 0.0)]
    fuze = [(0.69, 0.0), (0.69, 0.04), (0.73, 0.033), (0.79, 0.012), (0.795, 0.0)]
    c, s = math.cos(yaw), math.sin(yaw)
    for i in range(n):
        d = (i - (n - 1) / 2) * 0.2
        e = k.empty("round", (centre.x - s * d, centre.y + c * d, 0.04), parent=root)
        e.rotation_euler = (math.pi / 2 + (0.02 if i % 2 else -0.015), 0, i * 1.3)
        k.lathe("shell", body, "paint_shell", segs=28, parent=e)
        k.lathe("band", [(0.05, 0.0), (0.05, 0.0795), (0.085, 0.0795), (0.085, 0.0)], "copper",
                segs=28, parent=e)
        k.lathe("stripe", [(0.36, 0.0), (0.36, 0.0782), (0.39, 0.0782), (0.39, 0.0)], "paint_yellow",
                segs=28, parent=e)
        k.lathe("fuze", fuze, "steel_worn", segs=20, parent=e)


def _props(k, root, level=1):
    """Static kit around the gun. Everything stands between SWEEP_M and FOOTPRINT_M.
    The ammunition point is on the sunny side toward the camera (around -105 deg);
    each level keeps what the previous one had and adds to it."""
    tang = lambda deg: math.radians(deg)          # yaw that lays a crate's long side along the ring
    r0 = 4.9                                      # first row of crates
    # --- ammunition crates (long side tangential): wood, more wood, tarred, steel, black with brass
    cm = {1: ("paint_crate", "wood"), 2: ("paint_crate", "wood"), 3: ("wood", "timber_tarred"),
          4: ("paint_steel", "steel_worn"), 5: ("iron_black", "brass")}[level]
    stacks = {1: [(-118, 2), (-104, 1)],
              2: [(-124, 2), (-112, 2), (-100, 1)],
              3: [(-124, 3), (-112, 2), (-100, 2), (-89, 1)],
              4: [(-124, 3), (-112, 3), (-100, 2), (-89, 1)],
              5: [(-124, 3), (-112, 3), (-100, 3), (-89, 2)]}[level]
    for i, (deg, high) in enumerate(stacks):
        for j in range(high):
            p = pol(r0 + 0.02 * (j % 2), deg + (1.2 if j % 2 else 0), 0.3 * j)
            fort.crate(k, root, f"crate_{i}_{j}", p, tang(deg) + (0.06 if j % 2 else -0.03), mat=cm[0],
                       batten=cm[1])
    if level == 1:
        fort.crate(k, root, "crate_x", pol(5.45, -111), tang(-111) + 0.5)
    # ready rounds on a board
    _rounds(k, root, pol(r0 + 0.1, -77 if level > 1 else -90), tang(-77 if level > 1 else -90))
    # jerrycans
    for r, deg, yaw in ((5.55, -133, 0.5), (5.6, -129.5, 0.75)):
        p = pol(r, deg)
        e = k.empty("jerrycan", p, parent=root)
        e.rotation_euler = (0, 0, yaw)
        k.box("can", (0.17, 0.35, 0.42), (0, 0, 0.21), WORN, parent=e, bevel=0.03)
        k.box("can_top", (0.05, 0.2, 0.05), (0, -0.03, 0.445), WORN, parent=e, bevel=0.012)
        k.cylinder("can_cap", 0.03, 0.05, (0, 0.13, 0.42), STEEL, segs=12, parent=e)
    # shovel leaning on the first stack
    a = pol(r0 + 0.45, -119.5, 0.02)
    b = pol(r0 + 0.2, -118.5, 0.62 if level == 1 else 0.92)
    k.tube("shovel_shaft", a, b, 0.019, "wood", parent=root, segs=10)
    k.box("shovel_blade", (0.2, 0.012, 0.28), a + Vector((0, 0, 0.1)), "steel_worn",
          rot=(0.25, 0, math.radians(-118.5 + 90)), parent=root, bevel=False)
    # spent propellant canisters, tossed in a heap on the far left; the heap grows with the level
    heap = [(0.0, 168, 20), (0.3, 173, -15), (0.02, 178, 8), (0.33, 163, 30), (0.05, 185, -20),
            (0.32, 180.5, 12), (0.16, 172, 3), (0.2, 158, -35), (0.4, 189, 50), (0.1, 194, -8),
            (0.45, 166, 15), (0.25, 152, 40)]
    for i, (dr, deg, skew) in enumerate(heap[:2 + 2 * level]):
        p = pol(5.2 + dr, deg, 0.085 + (0.16 if i == 6 else 0.0))
        e = k.empty("canister", p, parent=root)
        e.rotation_euler = (0, 0, math.radians(deg + skew))
        k.lathe("can", [(-0.42, 0.0), (-0.42, 0.085), (0.42, 0.085), (0.42, 0.075), (0.4, 0.075),
                        (0.4, 0.0)], "paint_shell" if level < 5 else "brass", segs=20, parent=e)
        k.lathe("can_rim", [(-0.43, 0.0), (-0.43, 0.092), (-0.39, 0.092), (-0.39, 0.0)], "steel_worn",
                segs=20, parent=e)
    if level >= 2:      # brass aiming circle on a wooden tripod
        _aiming_circle(k, root, pol(5.0, -62), level)
    # aiming post, planted to the right
    p = pol(5.6, 22)
    for i in range(5):
        k.cylinder("aiming_post", 0.016, 0.3, (p.x, p.y, i * 0.3), "paint_red" if i % 2 else "paint_white",
                   segs=10, parent=root, bevel=False)
    # rammer staff lying along the edge of the position
    a, b = pol(5.75, -68, 0.05), pol(5.7, -40, 0.07)
    k.tube("rammer", a, b, 0.022, "wood", parent=root, segs=12)
    k.cylinder("rammer_head", 0.07, 0.12, a, "rubber", segs=16,
               rot=(a - b).to_track_quat("Z", "Y").to_euler(), parent=root)



def _aiming_circle(k, root, c, level):
    """The battery's brass aiming circle: a squat theodolite on a wooden tripod."""
    top = Vector((c.x, c.y, 1.15))
    for i in range(3):
        a = 2 * math.pi * i / 3 + 0.4
        foot = Vector((c.x + 0.42 * math.cos(a), c.y + 0.42 * math.sin(a), 0.0))
        k.tube("tripod_leg", foot, top - Vector((0, 0, 0.04)), 0.02, "timber_honey", parent=root, segs=8)
        k.tube("tripod_shoe", foot, foot + (top - foot).normalized() * 0.12, 0.022, TRIM, parent=root, segs=8,
               bevel=False)
    k.cylinder("tripod_head", 0.1, 0.04, top - Vector((0, 0, 0.04)), TRIM, segs=20, parent=root)
    k.cylinder("circle_base", 0.09, 0.08, top, TRIM, segs=24, parent=root, radius_top=0.075)
    k.cylinder("circle_dial", 0.085, 0.012, top + Vector((0, 0, 0.08)), "paint_white", segs=24, parent=root,
               bevel=False)
    k.box("circle_standard", (0.04, 0.05, 0.14), top + Vector((0, 0, 0.16)), TRIM, parent=root)
    e = k.empty("circle_scope", top + Vector((0, 0, 0.24)), parent=root)
    e.rotation_euler = (0, 0, math.radians(-30))
    k.tube("circle_telescope", (0, -0.13, 0), (0, 0.13, 0), 0.028, TRIM, parent=e, segs=14)
    k.cylinder("circle_lens", 0.024, 0.004, (0, 0.131, 0), "glass", segs=12, rot=(-math.pi / 2, 0, 0), parent=e,
               bevel=False)


def _traverse_gun(k, gun, level):
    """Parts that turn with the gun: flanged trail shoes on the rail (L3+), the traverse
    pinion and its drive shaft from the handwheel (L4+)."""
    deck = STYLE[level]["deck"]
    c0 = Vector((0, -GUN_SHIFT, 0))
    if level >= 3:
        for sx in (-1, 1):
            a, b = Vector((sx * 0.42, -0.45, 0.5)), Vector((sx * 1.3, -4.25, 0.36))
            d = (b - a).normalized()
            p = b + d * 0.18
            u = Vector((p.x - c0.x, p.y - c0.y, 0)).normalized()
            rc = Vector((p.x, p.y, 0.09 - deck + 0.12))
            k.tube("shoe_wheel", rc - u * 0.07, rc + u * 0.07, 0.12, STEEL if level < 5 else TRIM, parent=gun,
                   segs=24)
            k.tube("shoe_flange", rc - u * 0.09, rc - u * 0.07, 0.15, STEEL, parent=gun, segs=24, bevel=False)
            k.tube("shoe_axle", rc - u * 0.14, rc + u * 0.14, 0.03, STEEL, parent=gun, segs=10, bevel=False)
            for s2 in (-1, 1):
                k.beam("shoe_fork", b - d * 0.1 + u * s2 * 0.13 + Vector((0, 0, 0.1)), rc + u * s2 * 0.13,
                       (0.04, 0.1), OLIVE, parent=gun, bevel=False)
    if level >= 4:
        q = Vector((-0.966, -2.81, 0)) - c0
        u = Vector((q.x, q.y, 0)).normalized()
        pc = c0 + u * (RING_R + 0.11)
        z0 = 0.03 - deck
        k.cylinder("pinion", 0.09, 0.08, (pc.x, pc.y, z0), STEEL, segs=22, parent=gun)
        for i in range(11):
            ang = 2 * math.pi * i / 11
            k.box("pinion_tooth", (0.045, 0.035, 0.08), (pc.x + 0.095 * math.cos(ang), pc.y + 0.095 * math.sin(ang),
                                                         z0 + 0.04), STEEL, rot=(0, 0, ang), parent=gun, bevel=False)
        top = Vector((pc.x, pc.y, 0.62))
        k.tube("pinion_shaft", (pc.x, pc.y, z0 + 0.08), top, 0.03, STEEL, parent=gun, segs=10)
        k.box("bevel_box", (0.17, 0.17, 0.15), top, OLIVE, parent=gun, bevel=0.012)
        k.tube("drive_shaft", top + Vector((0.06, 0.05, 0.03)), Vector((-0.6, 0.15, 0.85)), 0.022, TRIM,
               parent=gun, segs=10)
        k.beam("pinion_bracket", top - Vector((0, 0, 0.06)), Vector((-0.86, -2.4, 0.5)), (0.06, 0.05), OLIVE,
               parent=gun, bevel=False)


def _hydraulics(k, t, level):
    """Level 3+: two hydraulic accumulators on the carriage nose with gauges, copper lines
    up to the buffers: the barrel runs out faster, so the gun reloads faster."""
    from . import faction as fx
    for sx in (-1, 1):
        x = sx * 0.24
        k.tube("accumulator", (x, 0.55, 0.76), (x, 1.15, 0.76), 0.085, OLIVE, parent=t, segs=20)
        for y in (0.55, 1.15):
            k.tube("acc_cap", (x, y - 0.02, 0.76), (x, y + 0.02, 0.76), 0.092, TRIM, parent=t, segs=20, bevel=False)
        k.box("acc_cradle", (0.16, 0.5, 0.08), (x, 0.85, 0.67), OLIVE, parent=t, bevel=False)
        fx.gauge(k, t, (x, 0.85, 0.86), (sx * 0.3, 0.2, 1.0), r=0.07)
        k.hose("hyd_line", [(x, 0.52, 0.78), (x * 1.2, 0.3, 0.95), (sx * 0.3, 0.0, 1.08), (sx * 0.3, -0.18, 1.12)],
               0.016, "copper", parent=t)
    k.tube("hyd_manifold", (-0.24, 1.2, 0.76), (0.24, 1.2, 0.76), 0.03, "copper", parent=t, segs=10)
    k.cylinder("hyd_valve", 0.035, 0.08, (0, 1.2, 0.78), TRIM, segs=12, parent=t)


def _steam_crane(k, t):
    """Level 5: a small steam crane on the right trail, with its own vertical boiler, lifts
    the next shell to the breech."""
    from . import faction as fx
    bc = Vector((0.66, -1.3, 0.64))
    k.box("crane_deck", (0.6, 0.9, 0.04), bc + Vector((0, -0.15, -0.02)), "iron_black", parent=t, bevel=False)
    k.cylinder("boiler", 0.2, 0.75, bc, "iron_black", segs=24, parent=t)
    k.cylinder("boiler_crown", 0.2, 0.08, bc + Vector((0, 0, 0.75)), "iron_black", segs=24, parent=t,
               radius_top=0.12)
    for z in (0.08, 0.4, 0.7):
        k.cylinder("boiler_band", 0.208, 0.035, bc + Vector((0, 0, z)), TRIM, segs=24, parent=t, bevel=False)
    k.box("firebox_door", (0.02, 0.14, 0.14), bc + Vector((0.2, 0, 0.18)), TRIM, parent=t, bevel=False)
    fx.stack(k, t, bc + Vector((0, 0, 0.82)), 0.55, r=0.05)
    fx.gauge(k, t, bc + Vector((0.12, 0.12, 0.62)), (0.6, 0.4, 0.7), r=0.06)
    k.cylinder("safety_valve", 0.025, 0.1, bc + Vector((-0.08, 0.05, 0.85)), TRIM, segs=10, parent=t)
    post0, post1 = Vector((0.7, -1.85, 0.6)), Vector((0.7, -1.85, 2.15))
    k.tube("crane_post", post0, post1, 0.05, "iron_black", parent=t, segs=14)
    tip = Vector((0.0, -2.45, 2.08))
    k.beam("crane_jib", post1 - Vector((0, 0, 0.05)), tip, (0.08, 0.1), "iron_black", parent=t, bevel=False)
    k.tube("crane_brace", post0 + Vector((0, 0, 0.95)), post1.lerp(tip, 0.6) - Vector((0, 0, 0.04)), 0.025,
           "iron_black", parent=t, segs=8, bevel=False)
    k.cylinder("crane_cap", 0.07, 0.06, post1, TRIM, segs=14, parent=t)
    k.tube("winch_drum", (0.6, -1.85, 0.95), (0.8, -1.85, 0.95), 0.08, TRIM, parent=t, segs=18)
    k.box("winch_engine", (0.16, 0.2, 0.2), (0.7, -1.62, 0.85), "iron_black", parent=t, bevel=0.01)
    k.hose("steam_pipe", [bc + Vector((-0.05, -0.12, 0.7)), Vector((0.66, -1.55, 1.2)), Vector((0.7, -1.62, 0.96))],
           0.02, "copper", parent=t)
    k.hose("crane_chain", [Vector((0.7, -1.85, 1.0)), post1 + Vector((0, 0, -0.1)), post1.lerp(tip, 0.5),
                           tip, tip - Vector((0, 0, 0.45))], 0.008, "steel_cable", parent=t)
    e = k.empty("hoisted_shell", tip - Vector((0, 0.42, 0.55)), parent=t)
    body = [(0.0, 0.0), (0.0, 0.068), (0.035, 0.0775), (0.44, 0.0775), (0.58, 0.066),
            (0.69, 0.042), (0.69, 0.0)]
    k.lathe("shell", body, "paint_shell", segs=24, parent=e)
    k.lathe("band", [(0.05, 0.0), (0.05, 0.0795), (0.085, 0.0795), (0.085, 0.0)], "copper", segs=24, parent=e)
    k.lathe("fuze", [(0.69, 0.0), (0.69, 0.04), (0.73, 0.033), (0.79, 0.012), (0.795, 0.0)], TRIM, segs=16,
            parent=e)
    k.torus("shell_sling", 0.085, 0.012, tip - Vector((0, 0, 0.55)), "steel_cable", rot=(0, math.pi / 2, 0),
            parent=t, segs=16, tube_segs=6)


_decal = fort.decal
