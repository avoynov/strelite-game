"""Towed 155 mm howitzer, M777 type (bg: „Гаубица“). PLACEHOLDER model for the
style В preview: built at real size from public dimensions (barrel 5.1 m,
firing length ~9 m, width 3.7 m), in firing position: wheels lifted, two front
stabilisers, two rear trails with spades, low saddle, four-tube cradle.

Level 1: the gun on bare soil, olive drab paint, a few ammunition crates.

Returns (root, turret). `turret` (the whole gun) rotates around Z to aim;
crates and ground stay still. Frame +Y is the direction of fire.
"""
import math
import os
import tempfile

import bpy
from mathutils import Matrix, Vector
from PIL import Image, ImageDraw, ImageFont

from .. import materials_photoreal as mp
from ..geo import Kit

LEVELS = (1,)
STYLES = ("photoreal",)
FRAME_M = 12.0          # real metres across the sprite frame (3.2 tiles)
TARGET_Z = 0.9          # height the camera is centred on
HERO_DIR = 12           # of 16: barrel toward screen lower-right, sunlit side to camera
ELEVATION_DEG = 20.0

OLIVE, WORN, STEEL = "paint_olive", "paint_olive_worn", "gunmetal"


def build(style, level=1):
    k = Kit(style)
    root = k.empty("howitzer")
    turret = k.empty("turret", parent=root)
    mp.set_reference(turret)

    _carriage(k, turret)
    _saddle(k, turret)
    _elevating_mass(k, turret)
    _props(k, root)
    return root, turret


# --------------------------------------------------------------------------
def _bolts(k, pts, axis, parent, r=0.017, mat=OLIVE):
    """Hex bolt heads at pts, sticking out along `axis`."""
    rot = Vector(axis).to_track_quat("Z", "Y").to_euler()
    for i, p in enumerate(pts):
        k.cylinder("bolt", r, 0.014, p, mat, segs=6, rot=rot, parent=parent, bevel=False,
                   smooth=False, outline=False)


def _carriage(k, t):
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
        k.beam("stab", a, b, (0.17, 0.2), OLIVE, section_end=(0.12, 0.13), parent=t, bevel=0.01)
        k.tube("stab_foot", b + Vector((0, 0, 0.03)), (b.x, b.y, 0.04), 0.045, STEEL, parent=t)
        k.cylinder("stab_pad", 0.21, 0.045, (b.x, b.y, 0.0), WORN, segs=28, parent=t,
                   radius_top=0.19)
        k.tube("stab_pin", (sx * 0.4, 1.05, 0.5), (sx * 0.58, 1.05, 0.5), 0.06, STEEL, parent=t)

        # --- rear trail with self-digging spade
        a, b = Vector((sx * 0.42, -0.45, 0.5)), Vector((sx * 1.3, -4.25, 0.36))
        k.beam("trail", a, b, (0.26, 0.3), OLIVE, section_end=(0.17, 0.2), parent=t, bevel=0.012)
        k.tube("trail_pin", (sx * 0.3, -0.5, 0.5), (sx * 0.6, -0.5, 0.5), 0.075, STEEL, parent=t)
        d = (b - a).normalized()
        side = Vector((sx * d.y, -sx * d.x, 0)).normalized()       # outward normal
        for f in (0.3, 0.62):                                       # lifting handles
            p = a.lerp(b, f) + Vector((0, 0, 0.13))
            k.tube("h1", p, p + Vector((0, 0, 0.1)), 0.012, STEEL, parent=t, segs=8, bevel=False)
            k.tube("h2", p + d * 0.22, p + d * 0.22 + Vector((0, 0, 0.1)), 0.012, STEEL, parent=t,
                   segs=8, bevel=False)
            k.tube("h3", p + Vector((0, 0, 0.1)), p + d * 0.22 + Vector((0, 0, 0.1)), 0.012, STEEL,
                   parent=t, segs=8, bevel=False)
        _bolts(k, [a.lerp(b, f) + side * 0.11 * (1.15 - 0.4 * f) + Vector((0, 0, dz))
                   for f in (0.08, 0.14, 0.5, 0.56, 0.9) for dz in (-0.06, 0.06)], side, t)
        for f0, f1 in ((0.05, 0.42), (0.5, 0.82)):                   # pressed stiffening ribs
            for dz in (-0.07, 0.07):
                w0, w1 = 0.13 * (1.0 - 0.33 * f0), 0.13 * (1.0 - 0.33 * f1)
                k.beam("trail_rib", a.lerp(b, f0) + side * (w0 + 0.004) + Vector((0, 0, dz * (1 - 0.3 * f0))),
                       a.lerp(b, f1) + side * (w1 + 0.004) + Vector((0, 0, dz * (1 - 0.3 * f1))),
                       (0.02, 0.035), OLIVE, parent=t, bevel=False)
        k.hose("trail_cable", [a.lerp(b, f) + Vector((0, 0, 0.16 - 0.05 * f)) - side * 0.05
                               for f in (0.02, 0.2, 0.45, 0.7, 0.93)], 0.012, "hose", parent=t)
        # spade: blade dug into the soil, braces, damper
        sp = b + d * 0.25
        k.box("spade", (0.78, 0.05, 0.62), (sp.x, sp.y, 0.1), WORN,
              rot=(math.radians(-28), 0, math.atan2(-d.x, d.y)), parent=t, bevel=0.01)
        k.box("spade_lip", (0.78, 0.2, 0.04), (sp.x - d.x * 0.02, sp.y - d.y * 0.02, 0.4), WORN,
              rot=(math.radians(-28), 0, math.atan2(-d.x, d.y)), parent=t)
        for s2 in (-1, 1):
            k.beam("spade_brace", a.lerp(b, 0.86) + side * s2 * 0.06, sp + side * s2 * 0.3
                   + Vector((0, 0, -0.2)) - d * 0.06, (0.04, 0.12), WORN, parent=t, bevel=False)
        k.tube("damper", a.lerp(b, 0.7) + Vector((0, 0, 0.14)), sp + Vector((0, 0, 0.22)), 0.04,
               OLIVE, parent=t)
        k.tube("damper_rod", a.lerp(b, 0.62) + Vector((0, 0, 0.15)),
               a.lerp(b, 0.7) + Vector((0, 0, 0.14)), 0.02, "chrome", parent=t, segs=12)

        # --- road wheel, lifted off the ground on its suspension arm
        hub = Vector((sx * 1.3, 0.95, 0.66))
        k.beam("arm", (sx * 0.55, 0.3, 0.5), (sx * 0.98, 0.93, 0.64), (0.13, 0.22), OLIVE,
               section_end=(0.11, 0.16), parent=t, bevel=0.01)
        k.tube("axle", (sx * 0.9, 0.95, 0.66), hub, 0.06, STEEL, parent=t)
        k.tube("gas_strut", (sx * 0.56, 0.75, 0.62), (sx * 0.95, 0.6, 0.58), 0.045, OLIVE, parent=t)
        _wheel(k, t, hub, sx)


def _wheel(k, t, hub, sx):
    w = k.empty("wheel", hub, parent=t)
    w.rotation_euler = (0, 0, -math.pi / 2)     # local Y = axle
    tyre = [(-0.085, 0.0), (-0.085, 0.31), (-0.15, 0.35), (-0.158, 0.44), (-0.13, 0.5),
            (-0.07, 0.52), (0.07, 0.52), (0.13, 0.5), (0.158, 0.44), (0.15, 0.35),
            (0.085, 0.31), (0.085, 0.0)]
    k.lathe("tyre", tyre, "rubber", segs=48, parent=w)
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
                  (0.522 * math.cos(a), row * 0.068, 0.522 * math.sin(a)), "rubber",
                  rot=(0, -a, row * 0.25), parent=w, bevel=False)


def _saddle(k, t):
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
        _decal(k, "decal_number", "Б-217", t, centre=(sx * 0.4465, -0.2, 0.88),
               u=(0, sx, 0), v=(0, 0, 1), height=0.12)


def _elevating_mass(k, t):
    piv = k.empty("elevating", (0, -0.7, 1.08), parent=t)
    el = math.radians(ELEVATION_DEG)
    piv.rotation_euler = (el, 0, 0)
    z0 = 0.12                                               # bore axis above the trunnions

    def to_turret(p):                                       # local (pivot) -> turret space
        return Vector((0, -0.7, 1.08)) + Matrix.Rotation(el, 3, "X") @ Vector(p)

    k.tube("trunnion", (-0.42, 0, 0), (0.42, 0, 0), 0.075, STEEL, parent=piv)

    # --- barrel: chamber, taper, tube
    barrel = [(-0.5, 0.0), (-0.5, 0.185), (0.4, 0.185), (0.55, 0.165), (1.3, 0.15),
              (1.62, 0.118), (4.55, 0.098), (4.55, 0.0)]
    k.lathe("barrel", barrel, "paint_barrel", segs=40, loc=(0, 0, z0), parent=piv)
    for y0, y1 in ((3.45, 3.57), (3.66, 3.72)):             # faction rings (crimson)
        r = 0.118 + (0.098 - 0.118) * ((y0 + y1) / 2 - 1.62) / 2.93 + 0.0025
        k.lathe("ring", [(y0, 0.0), (y0, r), (y1, r), (y1, 0.0)], "paint_red", segs=40,
                loc=(0, 0, z0), parent=piv)

    # --- muzzle brake: collar, two baffles, top/bottom bars, towing eye
    k.lathe("brake_collar", [(4.5, 0.0), (4.5, 0.125), (4.6, 0.14), (4.66, 0.14), (4.66, 0.0)],
            "paint_barrel", segs=32, loc=(0, 0, z0), parent=piv)
    k.lathe("brake_core", [(4.6, 0.0), (4.6, 0.108), (5.14, 0.108), (5.14, 0.0)], "paint_soot", segs=32,
            loc=(0, 0, z0), parent=piv)
    for y in (4.84, 5.1):
        k.box("baffle", (0.5, 0.06, 0.3), (0, y, z0), "paint_soot", parent=piv, bevel=0.012)
    for s in (-1, 1):
        k.box("brake_bar", (0.2, 0.56, 0.035), (0, 4.86, z0 + s * 0.155), "paint_soot",
              parent=piv, bevel=0.008)
    k.cylinder("bore", 0.078, 0.01, (0, 5.141, z0), "bore", segs=24, rot=(-math.pi / 2, 0, 0),
               parent=piv, bevel=False)
    k.box("eye_lug", (0.06, 0.16, 0.1), (0, 5.0, z0 - 0.21), "paint_barrel", parent=piv)
    k.torus("tow_eye", 0.085, 0.024, (0, 5.0, z0 - 0.33), STEEL, rot=(0, math.pi / 2, 0),
            parent=piv, segs=28, tube_segs=10)

    # --- breech ring, screw block, operating lever
    k.box("breech_ring", (0.5, 0.5, 0.5), (0, -0.62, z0), WORN, parent=piv, bevel=0.02)
    k.cylinder("breech_block", 0.16, 0.14, (0, -1.0, z0), STEEL, segs=28,
               rot=(-math.pi / 2, 0, 0), parent=piv)
    k.box("carrier", (0.16, 0.2, 0.36), (0.3, -0.9, z0), STEEL, parent=piv, bevel=0.012)
    k.tube("lever", (0.3, -0.95, z0 + 0.1), (0.42, -1.2, z0 + 0.34), 0.016, STEEL, parent=piv,
           segs=10)
    k.cylinder("lever_knob", 0.03, 0.07, (0.42, -1.2, z0 + 0.32), "rubber", segs=12, parent=piv)

    # --- cradle: body around the trunnions + four tubes + yokes
    k.box("cradle", (0.68, 1.05, 0.46), (0, 0.22, 0.08), OLIVE, parent=piv, bevel=0.015)
    k.box("cradle_top", (0.4, 0.8, 0.06), (0, 0.25, 0.34), OLIVE, parent=piv)
    for sx in (-1, 1):
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
    for y, wdt, hgt in ((1.45, 0.76, 0.66), (2.4, 0.74, 0.64)):
        k.box("yoke", (wdt, 0.07, hgt), (0, y, 0.12), OLIVE, parent=piv, bevel=0.012)
        _bolts(k, [(x, y + 0.036, zz) for x in (-0.33, 0.0, 0.33) for zz in (-0.16, 0.4)]
               + [(x, y + 0.036, 0.12) for x in (-0.34, 0.34)], (0, 1, 0), piv)

    # --- gunner's sight (left), assistant's quadrant (right)
    k.box("sight_mount", (0.12, 0.22, 0.3), (-0.42, 0.05, 0.42), OLIVE, parent=piv)
    k.tube("scope", (-0.44, -0.08, 0.62), (-0.44, 0.3, 0.64), 0.04, STEEL, parent=piv, segs=16)
    k.cylinder("scope_lens", 0.034, 0.004, (-0.44, 0.301, 0.64), "glass", segs=16,
               rot=(-math.pi / 2, 0, 0), parent=piv, bevel=False)
    k.box("pantel", (0.1, 0.1, 0.2), (-0.44, -0.12, 0.7), STEEL, parent=piv)
    k.box("quadrant", (0.1, 0.24, 0.16), (0.41, 0.0, 0.38), OLIVE, parent=piv)
    # loading tray, swung clear to the left of the breech
    k.box("tray", (0.26, 0.9, 0.04), (-0.5, -1.25, -0.02), WORN, parent=piv)
    for s in (-1, 1):
        k.box("tray_wall", (0.025, 0.9, 0.08), (-0.5 + s * 0.125, -1.25, 0.02), WORN, parent=piv)
    k.beam("tray_arm", (-0.38, -0.5, -0.05), (-0.5, -0.9, -0.03), (0.06, 0.08), OLIVE, parent=piv)

    # --- hydraulic hoses and a cable
    k.hose("hose1", [to_turret(p) for p in ((0.36, 0.3, -0.3), (0.5, 0.0, -0.3), (0.48, -0.3, 0.0),
                                             (0.36, -0.1, 0.2))], 0.014, "hose", parent=t)
    k.hose("hose2", [(0.3, 0.9, 0.62), (0.38, 0.75, 0.82), (0.5, 0.55, 0.95), (0.52, 0.42, 0.9)],
           0.012, "hose", parent=t)
    k.hose("hose3", [to_turret(p) for p in ((-0.3, 0.72, 0.3), (-0.33, 1.1, 0.46), (-0.3, 1.44, 0.4),
                                            (-0.26, 2.0, 0.47), (-0.26, 2.38, 0.46))], 0.011, "hose",
           parent=t)
    for sx in (-1, 1):
        _decal(k, "decal_calibre", "155 ММ", piv, centre=(sx * 0.3415, 0.25, 0.08),
               u=(0, sx, 0), v=(0, 0, 1), height=0.1)


def _props(k, root):
    """Level 1 kit: a few ammunition crates and ready rounds (static, on the soil)."""
    def crate(name, loc, yaw, size=(0.42, 0.98, 0.3), lid_open=False):
        e = k.empty(name, loc, parent=root)
        e.rotation_euler = (0, 0, yaw)
        sx, sy, sz = size
        k.box("crate", size, (0, 0, sz / 2), "paint_crate", parent=e, bevel=0.006)
        for y in (-sy * 0.33, sy * 0.33):                       # battens
            k.box("batten", (sx + 0.03, 0.07, sz + 0.02), (0, y, sz / 2), "wood", parent=e)
        for s in (-1, 1):                                       # rope handles
            k.hose("handle", [(-0.09, s * (sy / 2 + 0.002), sz * 0.62),
                              (-0.05, s * (sy / 2 + 0.06), sz * 0.45),
                              (0.05, s * (sy / 2 + 0.06), sz * 0.45),
                              (0.09, s * (sy / 2 + 0.002), sz * 0.62)], 0.011, "rope", parent=e)
        _decal(k, "decal_crate", "155 ОФ  2 БР.", e, centre=(sx / 2 + 0.0015, 0, sz * 0.5),
               u=(0, 1, 0), v=(0, 0, 1), height=0.075)
        _decal(k, "decal_crate", "155 ОФ  2 БР.", e, centre=(0, 0, sz + 0.0015),
               u=(0, 1, 0), v=(-1, 0, 0), height=0.075)
        return e

    crate("crate_a", (-1.9, -4.3, 0.0), math.radians(52))
    crate("crate_b", (-1.86, -4.34, 0.3), math.radians(47))
    crate("crate_c", (-2.75, -3.75, 0.0), math.radians(8))
    crate("crate_d", (-0.9, -5.0, 0.0), math.radians(74))

    # ready rounds standing on a board
    k.box("board", (0.5, 1.25, 0.035), (0.25, -4.45, 0.02), "wood", rot=(0, 0, math.radians(60)),
          parent=root)
    body = [(0.0, 0.0), (0.0, 0.068), (0.035, 0.0775), (0.44, 0.0775), (0.58, 0.066),
            (0.69, 0.042), (0.69, 0.0)]
    fuze = [(0.69, 0.0), (0.69, 0.04), (0.73, 0.033), (0.79, 0.012), (0.795, 0.0)]
    c, s = math.cos(math.radians(60)), math.sin(math.radians(60))
    for i in range(5):
        d = (i - 2) * 0.2
        e = k.empty("round", (0.25 - s * d, -4.45 + c * d, 0.04), parent=root)
        e.rotation_euler = (math.pi / 2 + (0.02 if i % 2 else -0.015), 0, i * 1.3)
        k.lathe("shell", body, "paint_shell", segs=28, parent=e)
        k.lathe("band", [(0.05, 0.0), (0.05, 0.0795), (0.085, 0.0795), (0.085, 0.0)], "copper",
                segs=28, parent=e)
        k.lathe("stripe", [(0.36, 0.0), (0.36, 0.0782), (0.39, 0.0782), (0.39, 0.0)], "paint_yellow",
                segs=28, parent=e)
        k.lathe("fuze", fuze, "steel_worn", segs=20, parent=e)
    # spent propellant canisters, tossed aside
    for i, (x, y, yaw) in enumerate(((-3.5, -1.9, 0.4), (-3.9, -2.5, 1.9), (-3.1, -2.9, 2.6),
                                      (-4.3, -1.5, 1.2))):
        e = k.empty("canister", (x, y, 0.085), parent=root)
        e.rotation_euler = (0, 0, yaw)
        k.lathe("can", [(-0.42, 0.0), (-0.42, 0.085), (0.42, 0.085), (0.42, 0.075), (0.4, 0.075),
                        (0.4, 0.0)], "paint_shell", segs=20, parent=e)
        k.lathe("can_rim", [(-0.43, 0.0), (-0.43, 0.092), (-0.39, 0.092), (-0.39, 0.0)], "steel_worn",
                segs=20, parent=e)
    # jerrycans
    for x, y, yaw in ((-2.6, -4.75, 0.5), (-2.95, -4.6, 0.75)):
        e = k.empty("jerrycan", (x, y, 0.0), parent=root)
        e.rotation_euler = (0, 0, yaw)
        k.box("can", (0.17, 0.35, 0.42), (0, 0, 0.21), WORN, parent=e, bevel=0.03)
        k.box("can_top", (0.05, 0.2, 0.05), (0, -0.03, 0.445), WORN, parent=e, bevel=0.012)
        k.cylinder("can_cap", 0.03, 0.05, (0, 0.13, 0.42), STEEL, segs=12, parent=e)
    # shovel and pick against the crates, aiming posts planted in front
    k.tube("shovel_shaft", (-2.25, -4.1, 0.02), (-1.98, -4.2, 0.95), 0.019, "wood", parent=root, segs=10)
    k.box("shovel_blade", (0.2, 0.012, 0.28), (-2.29, -4.085, 0.0), "steel_worn",
          rot=(0.28, 0, -1.2), parent=root, bevel=False)
    for (x, y) in ((3.2, -5.6),):
        for i in range(5):
            k.cylinder("aiming_post", 0.016, 0.3, (x, y, i * 0.3), "paint_red" if i % 2 else "paint_white",
                       segs=10, parent=root, bevel=False)
    # rammer staff lying by the trail
    k.tube("rammer", (1.1, -3.3, 0.05), (-0.55, -5.9, 0.07), 0.022, "wood", parent=root, segs=12)
    k.cylinder("rammer_head", 0.07, 0.12, (1.1, -3.3, 0.05), "rubber", segs=16,
               rot=Vector((1.65, 2.6, -0.02)).to_track_quat("Z", "Y").to_euler(), parent=root)


# --------------------------------------------------------------------------
_decal_dir = tempfile.mkdtemp(prefix="strelite_decals_")


def _decal(k, name, text, parent, centre, u, v, height):
    """White stencilled text on a flat face. u = reading direction, v = up."""
    key = f"{name}"
    path = os.path.join(_decal_dir, key + ".png")
    if not os.path.exists(path):
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 120)
        w = int(font.getlength(text)) + 40
        img = Image.new("L", (w, 170), 0)
        d = ImageDraw.Draw(img)
        d.text((20, 10), text, font=font, fill=255)
        for x in range(20 + 36, w, 72):                     # stencil bridges
            d.line([(x, 0), (x, 170)], fill=0, width=7)
        img.convert("RGB").save(path)
        mp.register_decal(key, path)
    with Image.open(path) as im:
        aspect = im.width / im.height
    u, v, c = Vector(u).normalized(), Vector(v).normalized(), Vector(centre)
    hw, hh = height * aspect / 2, height / 2
    verts = [c - u * hw - v * hh, c + u * hw - v * hh, c + u * hw + v * hh, c - u * hw + v * hh]
    me = bpy.data.meshes.new("decal")
    me.from_pydata([tuple(p) for p in verts], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name="UVMap")
    for i, co in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[i].uv = co
    obj = bpy.data.objects.new("decal", me)
    k.collection.objects.link(obj)
    from .. import materials
    obj.data.materials.append(materials.get(key, k.style))
    obj.parent = parent
    obj.visible_shadow = False
    return obj
