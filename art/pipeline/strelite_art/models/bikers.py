"""Motorcycle raiders (bg: „Мотоциклисти“): three riders on light military motorcycles in a
loose, staggered group, about 3.4 m long overall. The fastest enemy. Dark grey machines,
grey uniforms and helmets like the infantry.

The group faces local +Y; render_sprites.py --enemy turns it. Returns (root, root).
"""
import math

from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit
from . import vehicle
from .infantry import _ellipsoid, _limb

SPRITE_FRAME_M = 6.0
LENGTH_M = 3.4
RADIUS_M = 1.4
G, WORN = "paint_enemy", "paint_enemy_worn"
GROUP = [(0.0, 0.7, 0), (-0.95, -0.55, 6), (0.9, -0.35, -5)]   # x, y, yaw (deg)


def build(style, level=1):
    k = Kit(style)
    root = k.empty("bikers")
    mp.set_reference(root)
    for i, (x, y, yaw) in enumerate(GROUP):
        b = k.empty(f"bike{i}", (x, y, 0), parent=root)
        b.rotation_euler = (0, 0, math.radians(yaw))
        _bike(k, b, i)
    return root, root


def _bike(k, b, i):
    R = 0.33
    yf, yr = 0.72, -0.68
    for y in (yf, yr):
        vehicle.tyre_wheel(k, b, (0, y, R), R, 0.13, "gunmetal", tread=False)
    lean = math.radians((-1) ** i * 3)
    b.rotation_euler.y = lean
    # frame, engine, tank, seat
    k.tube("fork", (0, yf, R), (0, yf - 0.22, 1.02), 0.025, "steel_worn", parent=b, segs=8)
    k.tube("downtube", (0, yf - 0.22, 1.0), (0, 0.05, 0.42), 0.03, G, parent=b, segs=8)
    k.tube("swingarm", (0, 0.0, 0.45), (0, yr, R), 0.025, G, parent=b, segs=8)
    k.box("engine", (0.24, 0.42, 0.32), (0, 0.08, 0.48), "gunmetal", parent=b, bevel=0.02)
    k.box("tank", (0.26, 0.48, 0.2), (0, 0.18, 0.86), G, rot=(0.12, 0, 0), parent=b, bevel=0.05)
    k.box("seat", (0.24, 0.5, 0.08), (0, -0.3, 0.86), "leather", parent=b, bevel=0.03)
    k.box("rear_fender", (0.16, 0.5, 0.03), (0, -0.62, 0.72), G, rot=(-0.2, 0, 0), parent=b, bevel=0.01)
    k.box("front_fender", (0.15, 0.36, 0.03), (0, 0.74, 0.7), G, rot=(0.15, 0, 0), parent=b, bevel=0.01)
    k.tube("handlebar", (-0.36, yf - 0.25, 1.06), (0.36, yf - 0.25, 1.06), 0.016, "steel_worn", parent=b, segs=8)
    k.cylinder("headlight", 0.08, 0.1, (0, yf - 0.13, 0.98), G, segs=14, rot=(-math.pi / 2, 0, 0), parent=b)
    k.tube("exhaust", (0.13, 0.15, 0.36), (0.16, -0.75, 0.55), 0.035, "steel_worn", parent=b, segs=10)
    k.box("pannier", (0.14, 0.34, 0.26), (-0.17, -0.48, 0.7), "canvas", parent=b, bevel=0.03)
    # rider, crouched over the bars
    U, SK = "uniform", "skin"
    hip = Vector((0, -0.28, 0.98))
    neck = Vector((0, 0.08, 1.48))
    k.beam("torso", hip, neck, (0.36, 0.22), U, section_end=(0.42, 0.24), parent=b, bevel=0.05)
    k.box("pack", (0.3, 0.16, 0.32), (0, -0.2, 1.32), "canvas", rot=(0.6, 0, 0), parent=b, bevel=0.04)
    _ellipsoid(k, "head", neck + Vector((0, 0.08, 0.13)), 0.085, 0.1, 0.11, SK, b)
    helm = [(0.0, 0.16), (0.012, 0.165), (0.03, 0.14), (0.07, 0.13), (0.12, 0.1), (0.16, 0.05), (0.175, 0.0)]
    k.lathe("helmet", helm, "paint_enemy", segs=24, loc=neck + Vector((0, 0.07, 0.14)), rot=(math.pi / 2, 0, 0),
            parent=b)
    for sx in (-1, 1):
        sh = Vector((sx * 0.2, 0.02, 1.42))
        el = Vector((sx * 0.3, 0.22, 1.2))
        hand = Vector((sx * 0.33, yf - 0.25, 1.07))
        _limb(k, "upper_arm", sh, el, 0.06, 0.05, U, b)
        _limb(k, "forearm", el, hand, 0.05, 0.04, U, b)
        knee = Vector((sx * 0.24, 0.1, 0.78))
        foot = Vector((sx * 0.2, -0.05, 0.4))
        _limb(k, "thigh", Vector((sx * 0.1, -0.25, 0.96)), knee, 0.085, 0.065, U, b)
        _limb(k, "shin", knee, foot, 0.062, 0.05, U, b)
        k.box("boot", (0.11, 0.26, 0.1), foot + Vector((0, 0.05, -0.03)), "boot", parent=b, bevel=0.015)
    # rifle slung across the back
    k.tube("rifle", (-0.22, -0.32, 1.12), (0.25, -0.1, 1.5), 0.022, "gunmetal", parent=b, segs=8)
