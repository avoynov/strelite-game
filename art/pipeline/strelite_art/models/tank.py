"""Medium tank, generic post-war type (bg: „Танк“). PLACEHOLDER enemy for style В,
built at real size: hull 5.8 x 3.3 m, five road wheels a side, cast dome turret,
100 mm class gun (8.0 m long overall), dark grey paint.

The vehicle faces local +Y; render_sprites.py --enemy turns the whole model.
Returns (root, root).
"""
import math

from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit
from . import vehicle

SPRITE_FRAME_M = 11.0     # metres across the render: the gun overhangs the hull by 2.2 m
LENGTH_M = 8.0            # gun tip to rear plate
RADIUS_M = 3.0            # body (hull) half length, for collisions and spacing
G, WORN, TRACK = "paint_enemy", "paint_enemy_worn", "track_steel"


def build(style, level=1):
    k = Kit(style)
    root = k.empty("tank")
    mp.set_reference(root)
    _running_gear(k, root)
    _hull(k, root)
    _turret(k, root)
    return root, root


def _running_gear(k, root):
    for sx in (-1, 1):
        x = sx * 1.36
        for i in range(5):
            y = -2.05 + i * 1.02
            vehicle.road_wheel(k, root, (x, y, 0.46), 0.4, 0.44, G)
        vehicle.road_wheel(k, root, (x, -2.62, 0.62), 0.32, 0.4, G, sprocket=True)
        vehicle.road_wheel(k, root, (x, 2.62, 0.56), 0.3, 0.38, G)
        vehicle.track(k, root, x, y0=-2.62, y1=2.62, z=0.5, r=0.44, width=0.58, mat=TRACK)


def _hull(k, root):
    # lower hull between the tracks, with the sloped glacis
    k.plate("hull", [(-2.9, 0.42), (2.35, 0.42), (3.0, 0.98), (2.55, 1.44), (-2.92, 1.44), (-3.0, 0.8)],
            2.06, 0.0, G, parent=root, bevel=0.012)
    # deck over the tracks (fenders and sponsons)
    for sx in (-1, 1):
        k.plate("sponson", [(-2.95, 1.03), (2.98, 1.03), (2.82, 1.44), (-2.95, 1.44)], 0.66,
                sx * 1.36, G, parent=root, bevel=0.01)
        k.box("fender_front", (0.64, 0.42, 0.025), (sx * 1.36, 3.12, 1.02), WORN, rot=(0.35, 0, 0),
              parent=root, bevel=False)
        k.box("fender_rear", (0.64, 0.25, 0.025), (sx * 1.36, -3.05, 1.06), WORN, rot=(-0.3, 0, 0),
              parent=root, bevel=False)
        for i, y in enumerate((-1.9, -0.6, 0.7)):          # stowage boxes on the fenders
            k.box("stowage", (0.5, 0.95 if i else 0.8, 0.32), (sx * 1.38, y, 1.6), G, parent=root,
                  bevel=0.01)
        k.cylinder("headlight", 0.08, 0.1, (sx * 1.0, 2.84, 1.32), G, segs=14, rot=(-1.3, 0, 0),
                   parent=root)
        k.cylinder("lens", 0.065, 0.012, (sx * 1.0, 2.94, 1.35), "glass", segs=14,
                   rot=(-1.3, 0, 0), parent=root, bevel=False)
    # engine deck: grilles and louvres at the rear
    for i in range(6):
        k.box("louvre", (1.7, 0.06, 0.03), (0, -2.05 - i * 0.12, 1.455), "gunmetal", parent=root,
              bevel=False)
    k.box("grille", (1.9, 1.0, 0.02), (0, -1.0, 1.45), WORN, parent=root, bevel=False)
    for sx in (-1, 1):                                       # fuel drums on the rear plate
        k.cylinder("drum", 0.29, 0.86, (sx * 0.7 - 0.43, -3.18, 1.2), G, segs=22,
                   rot=(0, math.pi / 2, 0), parent=root)
    k.tube("exhaust", (1.05, -2.9, 1.0), (1.05, -3.12, 1.0), 0.07, "steel_worn", parent=root, segs=12)
    # tow cables along the hull sides and a hatch for the driver
    for sx in (-1, 1):
        k.hose("cable", [(sx * 1.02, 2.3, 1.47), (sx * 1.04, 0.5, 1.47), (sx * 1.03, -1.4, 1.47),
                         (sx * 0.95, -2.6, 1.47)], 0.022, "steel_worn", parent=root)
    k.cylinder("driver_hatch", 0.27, 0.05, (-0.62, 2.15, 1.43), G, segs=20, parent=root)
    k.box("tow_hook", (0.18, 0.2, 0.12), (0.7, 3.0, 0.6), "steel_worn", parent=root)
    k.box("tow_hook", (0.18, 0.2, 0.12), (-0.7, 3.0, 0.6), "steel_worn", parent=root)


def _turret(k, root):
    t = k.empty("turret", (0, 0.35, 1.44), parent=root)
    prof = [(0.0, 1.16), (0.06, 1.22), (0.3, 1.18), (0.52, 1.02), (0.7, 0.72), (0.8, 0.38), (0.83, 0.0)]
    dome = k.lathe("turret_cast", prof, G, segs=40, rot=(math.pi / 2, 0, 0), parent=t)
    dome.scale = (1.0, 1.0, 1.1)
    k.cylinder("turret_ring", 1.2, 0.08, (0, 0, -0.04), WORN, segs=40, parent=t)
    # gun: mantlet, barrel with a fume extractor
    k.cylinder("mantlet", 0.42, 0.62, (0, 1.05, 0.42), G, segs=26, rot=(-math.pi / 2, 0, 0),
               parent=t, radius_top=0.3)
    k.tube("barrel", (0, 1.6, 0.44), (0, 4.75, 0.44), 0.085, G, radius_end=0.075, parent=t, segs=22)
    k.tube("evacuator", (0, 3.85, 0.44), (0, 4.35, 0.44), 0.115, G, parent=t, segs=22)
    k.tube("muzzle", (0, 4.7, 0.44), (0, 4.8, 0.44), 0.088, WORN, parent=t, segs=22)
    k.cylinder("bore", 0.055, 0.02, (0, 4.795, 0.44), "bore", segs=16, rot=(-math.pi / 2, 0, 0),
               parent=t, bevel=False)
    # commander's cupola with a hatch and a machine gun, loader's hatch
    k.cylinder("cupola", 0.33, 0.2, (-0.48, -0.25, 0.74), G, segs=24, parent=t)
    k.cylinder("cupola_hatch", 0.3, 0.05, (-0.48, -0.25, 0.94), G, segs=24, parent=t)
    for i in range(6):
        a = 2 * math.pi * i / 6 + 0.3
        k.box("vision_block", (0.09, 0.05, 0.06), (-0.48 + 0.33 * math.cos(a), -0.25 + 0.33 * math.sin(a), 0.84),
              "glass", rot=(0, 0, a + math.pi / 2), parent=t, bevel=False)
    k.cylinder("loader_hatch", 0.28, 0.05, (0.5, -0.3, 0.76), G, segs=22, parent=t)
    k.box("mg_mount", (0.08, 0.2, 0.14), (0.5, 0.0, 0.86), "gunmetal", parent=t)
    k.tube("mg", (0.5, -0.05, 0.94), (0.5, 0.95, 0.94), 0.022, "gunmetal", parent=t, segs=10)
    k.box("mg_box", (0.12, 0.2, 0.14), (0.58, -0.05, 0.9), WORN, parent=t)
    # smoke dischargers and a stowage bin at the back
    for sx in (-1, 1):
        for i in range(3):
            p = Vector((sx * (0.86 + 0.08 * i), 0.55 - 0.12 * i, 0.5))
            k.tube("smoke", p, p + Vector((sx * 0.12, 0.22, 0.1)), 0.04, "gunmetal", parent=t, segs=10)
    k.box("bustle_bin", (1.5, 0.5, 0.36), (0, -1.33, 0.32), G, parent=t, bevel=0.012)
    k.tube("antenna", (0.62, -0.75, 0.75), (0.66, -0.85, 2.5), 0.006, "gunmetal", parent=t, segs=6,
           bevel=False)
