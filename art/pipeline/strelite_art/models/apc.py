"""Eight-wheeled armoured personnel carrier, generic type (bg: „БТР“): boat-shaped hull
7.6 x 2.9 m on four axles, small turret with a heavy machine gun, side doors and roof
hatches for the squad it carries (four infantry jump out when it dies). Dark grey.

The vehicle faces local +Y; render_sprites.py --enemy turns it. Returns (root, root).
"""
import math

from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit
from . import faction as fx
from . import vehicle

SPRITE_FRAME_M = 10.0
LENGTH_M = 7.6
RADIUS_M = 3.8
G, WORN = "paint_enemy", "paint_enemy_worn"
R_WHEEL = 0.55


def build(style, level=1):
    k = Kit(style)
    root = k.empty("apc")
    mp.set_reference(root)
    for y in (2.35, 0.95, -0.85, -2.25):
        for sx in (-1, 1):
            vehicle.tyre_wheel(k, root, (sx * 1.22, y, R_WHEEL), R_WHEEL, 0.4, "gunmetal", tread=False)
    # lower hull: wedge nose, sloped sides
    k.plate("hull_low", [(-3.75, 0.55), (2.9, 0.55), (3.8, 1.1), (3.6, 1.35), (-3.8, 1.35)], 2.2, 0.0, G,
            parent=root, bevel=0.015)
    # upper hull with inward-sloped sides: two side plates and a roof
    for sx in (-1, 1):
        k.box("side_upper", (0.08, 6.9, 0.75), (sx * 1.3, -0.25, 1.7), G, rot=(0, sx * -0.38, 0), parent=root,
              bevel=0.01)
        k.box("fender", (0.5, 6.6, 0.04), (sx * 1.3, -0.1, 1.36), WORN, parent=root, bevel=False)
        k.box("door", (0.05, 0.75, 0.6), (sx * 1.42, -0.05, 1.65), WORN, rot=(0, sx * -0.38, 0), parent=root,
              bevel=0.006)
        for y in (2.0, -2.6):
            k.box("vision_port", (0.04, 0.22, 0.08), (sx * 1.35, y, 1.88), "glass", rot=(0, sx * -0.38, 0),
                  parent=root, bevel=False)
        k.box("tool_box", (0.3, 0.9, 0.2), (sx * 1.3, -2.2, 1.48), G, parent=root, bevel=0.01)
    k.box("roof", (2.2, 6.9, 0.08), (0, -0.25, 2.06), G, parent=root, bevel=0.01)
    k.plate("glacis", [(2.9, 1.35), (3.85, 1.35), (3.0, 2.06), (2.9, 2.06)], 2.6, 0.0, G, parent=root,
            bevel=0.012)
    k.box("trim_vane", (2.3, 0.06, 0.55), (0, 3.55, 1.45), WORN, rot=(-0.5, 0, 0), parent=root, bevel=0.006)
    for sx in (-1, 1):
        k.box("windscreen", (0.75, 0.04, 0.32), (sx * 0.5, 3.12, 1.82), "glass", rot=(-0.95, 0, 0), parent=root,
              bevel=False)
        k.cylinder("headlight", 0.09, 0.12, (sx * 0.95, 3.45, 1.45), G, segs=14, rot=(-1.2, 0, 0), parent=root)
    for x, y in ((-0.6, 1.1), (0.6, 1.1), (-0.6, -2.0), (0.6, -2.0)):
        k.box("hatch", (0.55, 0.7, 0.05), (x, y, 2.12), WORN, parent=root, bevel=0.01)
    k.box("rear_plate", (2.75, 0.08, 0.8), (0, -3.72, 1.7), G, parent=root, bevel=0.01)
    k.box("engine_grille", (1.6, 1.0, 0.03), (0, -3.1, 2.11), "gunmetal", parent=root, bevel=False)
    # turret with a heavy machine gun
    t = k.empty("turret", (0, 0.9, 2.1), parent=root)
    k.lathe("turret_cone", [(0.0, 0.62), (0.3, 0.55), (0.48, 0.32), (0.52, 0.0)], G, segs=28,
            rot=(math.pi / 2, 0, 0), parent=t)
    k.box("gun_mantlet", (0.3, 0.3, 0.28), (0, 0.55, 0.28), G, parent=t, bevel=0.02)
    k.tube("hmg", (0.0, 0.6, 0.3), (0.0, 2.2, 0.33), 0.04, "gunmetal", parent=t, segs=12)
    k.tube("hmg_coax", (0.14, 0.6, 0.28), (0.14, 1.4, 0.28), 0.018, "gunmetal", parent=t, segs=8)
    k.tube("antenna", (-0.8, -2.8, 2.1), (-0.85, -2.95, 3.9), 0.007, "gunmetal", parent=root, segs=6, bevel=False)
    k.box("spare_wheel_mount", (0.12, 0.6, 0.6), (0, -3.85, 1.45), "gunmetal", parent=root, bevel=False)
    # parallel-world faction marks
    fx.emblem(k, root, (0, -0.45, 2.105), (0, 0, 1), r=0.5)
    fx.band(k, t, (0, 1.6, 0.33), (0, 1.72, 0.33), (0.12, 0.12))
    k.cylinder("turret_band", 0.6, 0.06, (0, 0, 0.05), "paint_faction_red", segs=28, parent=t, bevel=False)
    for sx in (-1, 1):
        fx.emblem(k, root, (sx * 1.47, -1.5, 1.68), (sx, 0, 0.38), r=0.26)
        fx.rivets(k, root, (sx * 1.18, -3.5, 2.02), (sx * 1.18, 3.0, 2.02), 18, (sx, 0, 0.4))
        fx.stack(k, root, (sx * 0.95, -3.4, 2.1), 0.7, r=0.07)
        fx.lamp(k, root, (sx * 0.95, 3.5, 1.47), (0, 1, 0.3), r=0.09)
    return root, root
