"""Land fortress (bg: „Крепост“), the boss: a giant tracked battle vehicle, 15 m long and
8 m wide on four track units, riveted armour, a twin-gun main turret, a secondary turret
at the back, machine-gun sponsons and smoke stacks. Dark grey, heavily worn.

The vehicle faces local +Y; render_sprites.py --enemy turns it. Returns (root, root).
"""
import math

from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit
from . import faction as fx
from . import vehicle

SPRITE_FRAME_M = 21.0
LENGTH_M = 17.5
RADIUS_M = 7.5
G, WORN, TRACK = "paint_enemy", "paint_enemy_worn", "track_steel"


def build(style, level=1):
    k = Kit(style)
    root = k.empty("fortress")
    mp.set_reference(root)
    for x in (-3.45, -2.05, 2.05, 3.45):                     # four track units
        for i in range(7):
            vehicle.road_wheel(k, root, (x, -5.4 + i * 1.8, 0.62), 0.55, 0.52, G)
        vehicle.road_wheel(k, root, (x, -6.6, 0.85), 0.5, 0.5, G, sprocket=True)
        vehicle.road_wheel(k, root, (x, 6.6, 0.8), 0.45, 0.48, G)
        vehicle.track(k, root, x, y0=-6.6, y1=6.6, z=0.75, r=0.62, width=1.1, mat=TRACK, pitch=0.24, thick=0.09)
    for sx in (-1, 1):                                       # skirts over the outer tracks
        k.box("skirt", (0.08, 13.6, 1.0), (sx * 4.12, 0, 1.25), G, parent=root, bevel=0.01)
        for i in range(14):
            k.cylinder("rivet", 0.04, 0.03, (sx * 4.17, -6.5 + i * 1.0, 1.6), WORN, segs=8,
                       rot=(0, sx * math.pi / 2, 0), parent=root, bevel=False)
    # hull in two steps
    k.plate("hull", [(-7.2, 1.0), (6.4, 1.0), (7.4, 1.9), (6.9, 2.9), (-7.2, 2.9)], 8.0, 0.0, G, parent=root,
            bevel=0.03)
    k.box("superstructure", (6.4, 9.0, 1.4), (0, -0.9, 3.6), G, parent=root, bevel=0.04)
    k.box("bridge", (3.2, 2.0, 1.2), (0, 3.0, 4.6), G, parent=root, bevel=0.05)
    for sx in (-1, 1):
        k.box("bridge_slit", (1.0, 0.04, 0.1), (sx * 0.8, 4.01, 4.9), "glass", parent=root, bevel=False)
        for i in range(8):
            for z in (2.4, 3.9):
                k.cylinder("rivet", 0.045, 0.03, (sx * (3.2 if z > 3 else 4.0) + sx * 0.01, -5.5 + i * 1.4, z), WORN,
                           segs=8, rot=(0, sx * math.pi / 2, 0), parent=root, bevel=False)
        # machine-gun sponsons
        s = k.empty("sponson", (sx * 3.3, 1.2, 3.4), parent=root)
        k.lathe("sponson_dome", [(0.0, 0.7), (0.35, 0.6), (0.6, 0.3), (0.65, 0.0)], G, segs=24,
                rot=(0, 0, sx * -math.pi / 2), parent=s)
        k.tube("mg", (sx * 0.5, 0.1, 0.0), (sx * 0.8, 1.6, 0.05), 0.04, "gunmetal", parent=s, segs=10)
        # smoke stacks at the back
        k.cylinder("stack", 0.32, 2.2, (sx * 1.6, -5.3, 4.2), WORN, segs=20, parent=root)
        k.cylinder("stack_cap", 0.38, 0.1, (sx * 1.6, -5.3, 6.4), "steel_worn", segs=20, parent=root)
    # main turret: twin guns
    t = k.empty("turret", (0, 0.4, 4.3), parent=root)
    k.lathe("turret_body", [(0.0, 2.3), (0.4, 2.25), (1.0, 2.0), (1.4, 1.4), (1.55, 0.0)], G, segs=40,
            rot=(math.pi / 2, 0, 0), parent=t).scale = (1.0, 1.15, 1.0)
    k.cylinder("turret_ring", 2.5, 0.15, (0, 0, -0.08), WORN, segs=48, parent=t)
    for sx in (-1, 1):
        k.box("mantlet", (0.7, 0.8, 0.8), (sx * 0.6, 2.2, 0.75), G, parent=t, bevel=0.05)
        k.tube("barrel", (sx * 0.6, 2.5, 0.78), (sx * 0.6, 8.2, 0.85), 0.17, G, radius_end=0.14, parent=t, segs=22)
        k.tube("muzzle_brake", (sx * 0.6, 8.0, 0.85), (sx * 0.6, 8.6, 0.86), 0.21, WORN, parent=t, segs=22)
    k.cylinder("cupola", 0.5, 0.35, (-0.9, -0.8, 1.45), G, segs=24, parent=t)
    k.cylinder("rangefinder", 0.16, 3.6, (-1.8, -0.2, 1.1), G, segs=16, rot=(0, math.pi / 2, 0), parent=t)
    # secondary turret at the back
    t2 = k.empty("turret2", (0, -3.8, 4.3), parent=root)
    k.lathe("turret2_body", [(0.0, 1.2), (0.35, 1.1), (0.7, 0.7), (0.8, 0.0)], G, segs=32,
            rot=(math.pi / 2, 0, 0), parent=t2)
    k.tube("barrel2", (0, 1.0, 0.45), (0, 3.6, 0.5), 0.1, G, parent=t2, segs=18)
    k.tube("antenna", (2.4, -6.0, 4.3), (2.5, -6.3, 7.8), 0.012, "gunmetal", parent=root, segs=6, bevel=False)
    k.box("deck_crates", (1.6, 1.0, 0.6), (-2.3, -6.6, 3.2), "canvas", parent=root, bevel=0.06)
    # parallel-world faction marks: emblems, oxblood bands, brass gauges, pennants
    fx.emblem(k, root, (0, 3.0, 5.205), (0, 0, 1), r=0.8)
    fx.emblem(k, root, (0, -6.0, 4.305), (0, 0, 1), r=0.7)
    for sx in (-1, 1):
        fx.emblem(k, root, (sx * 4.17, -1.5, 1.3), (sx, 0, 0), r=0.45)
        k.cylinder("stack_band", 0.34, 0.25, (sx * 1.6, -5.3, 5.6), "paint_faction_red", segs=20, parent=root,
                   bevel=False)
        k.cylinder("stack_ring", 0.34, 0.06, (sx * 1.6, -5.3, 5.0), "brass", segs=20, parent=root, bevel=False)
        fx.band(k, t, (sx * 0.6, 7.2, 0.83), (sx * 0.6, 7.45, 0.84), (0.36, 0.36))
        for i in range(3):
            fx.gauge(k, root, (sx * 1.0 + i * 0.25 * sx, 4.01, 4.35), (0, 1, 0), r=0.08)
    k.cylinder("turret_band", 2.27, 0.2, (0, 0, 0.35), "paint_faction_red", segs=48, parent=t,
               bevel=False).scale = (1.0, 1.15, 1.0)
    fx.pennant(k, root, (2.5, -6.3, 7.8), h=0.4, w=1.2)
    fx.pennant(k, t, (-0.9, -0.8, 1.8), h=1.4, w=0.9)
    return root, root
