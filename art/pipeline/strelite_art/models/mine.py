"""Мина (trap id mine): a mine buried in the road, one tile. Four armed looks (base and three
research levels, Game.trapLevel 1-4) and the spent look after it went off. Nothing turns.

Looks (sketch v2, approved 2026-11-22):
  1  a clay pot of black powder under a pressure plank on two pegs, a fuse, pebbles
  2  a cast-iron shell half buried, a brass plunger under a wooden lid, a tripwire to a stake
  3  the same shell studded with copper spikes
  4  a pressed-steel plate mine, olive with a yellow band, a central fuze with a red cap,
     half covered with clods
  5  spent: a torn, lopsided hole with a ragged lip, heaved turf, clods, stones and splinters
     flung out unevenly, a patchy scorch (LEVEL 5 here is the spent look)
Built a little larger than life (SCALE) so it reads on a 4 m tile.
"""
import math
import random

import bpy
from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit
from .trebuchet import _ball

LEVELS = (1, 2, 3, 4, 5)
FRAME_M = 4.0
TARGET_Z = 0.2
SPRITE_FRAME_M = 4.5
FOOTPRINT_M = 1.6
SCALE = 1.35


def build(style, level=1):
    k = Kit(style)
    root = k.empty("mine")
    root.scale = (SCALE, SCALE, SCALE)
    turret = k.empty("turret", (0, 0, 0), parent=root)     # nothing turns; kept for the renderer
    turret["node"] = "turret"
    mp.set_reference(root)
    rnd = random.Random(level)
    if level == 5:
        _spent(k, root, rnd)
    else:
        _mound(k, root, 0.6, rnd)
        (_pot, _shell, _spiked, _plate)[level - 1](k, root, rnd)
    return root, turret


def ground(level):
    from ..terrain import Patch
    return Patch(r_solid=1.8, r_out=2.2, r_bare=2.2, seed=40 + level, ragged=0.3)


def _mound(k, root, r, rnd):
    m = _ball(k, root, (0, 0, -0.02), r, "dirt_fill", subdiv=3)
    m.scale = (1.0, 0.9, 0.16)
    for i in range(6):
        a = rnd.uniform(0, 2 * math.pi)
        d = rnd.uniform(r * 0.8, r * 1.15)
        c = _ball(k, root, (d * math.cos(a), d * math.sin(a), 0.0), rnd.uniform(0.04, 0.07), "dirt_fill", subdiv=1)
        c.scale = (1.2, 1.0, 0.7)


def _pot(k, root, rnd):
    k.lathe("pot_lip", [(0.0, 0.24), (0.06, 0.3), (0.09, 0.3), (0.09, 0.25), (0.0, 0.2)], "clay", segs=28,
            rot=(math.pi / 2, 0, 0), loc=(0, 0, 0.0), parent=root)
    k.cylinder("powder", 0.24, 0.02, (0, 0, 0.05), "slate", segs=24, parent=root, bevel=False)
    for x in (-0.3, 0.3):
        k.cylinder("peg", 0.03, 0.12, (x, 0.0, 0.0), "timber_raw", segs=8, parent=root)
    k.box("plank", (0.85, 0.22, 0.05), (0, 0.0, 0.14), "timber_raw", rot=(0, 0, 0.12), parent=root, bevel=0.008)
    k.hose("fuse", [(0.2, 0.12, 0.06), (0.45, 0.35, 0.03), (0.68, 0.3, 0.02)], 0.012, "hemp", parent=root)
    for x, y in ((-0.45, 0.28), (0.4, -0.32), (0.48, 0.18)):
        b = _ball(k, root, (x, y, 0.02), 0.05, "stone", subdiv=2)
        b.scale = (1.3, 1.0, 0.7)


def _shell_body(k, root):
    _ball(k, root, (0, 0, 0.0), 0.4, "iron_forged", subdiv=4)
    k.cylinder("plunger", 0.05, 0.06, (0, 0, 0.38), "brass", segs=12, parent=root)
    k.cylinder("lid", 0.2, 0.035, (0, 0, 0.44), "timber_oak", segs=20, parent=root)
    k.hose("tripwire", [(0.25, 0.15, 0.08), (0.55, 0.45, 0.05), (0.78, 0.48, 0.16)], 0.004, "steel_cable",
           parent=root)
    k.tube("stake", (0.78, 0.48, 0.0), (0.78, 0.48, 0.24), 0.02, "timber_raw", parent=root, segs=6)


def _shell(k, root, rnd):
    _shell_body(k, root)


def _spiked(k, root, rnd):
    _shell_body(k, root)
    for el, n in ((15, 9), (48, 6), (75, 3)):
        for i in range(n):
            az = 2 * math.pi * i / n + (0.35 if el > 30 else 0)
            d = Vector((math.cos(math.radians(el)) * math.cos(az), math.cos(math.radians(el)) * math.sin(az),
                        math.sin(math.radians(el))))
            if el > 70 and abs(az) < 0.1:
                continue
            b = d * 0.38
            k.tube("spike", b, b + d * 0.22, 0.04, "copper", radius_end=0.004, parent=root, segs=10, bevel=False)


def _plate(k, root, rnd):
    k.cylinder("plate_mine", 0.42, 0.1, (0, 0, -0.02), "paint_green_dark", segs=36, parent=root)
    for r in (0.32, 0.22):
        k.torus("rib", r, 0.012, (0, 0, 0.08), "paint_green_dark", parent=root, segs=32, tube_segs=4)
    k.torus("yellow_band", 0.425, 0.025, (0, 0, 0.045), "paint_yellow", parent=root, segs=36, tube_segs=4)
    k.cylinder("fuze", 0.09, 0.05, (0, 0, 0.08), "steel_worn", segs=16, parent=root)
    k.cylinder("safety_cap", 0.05, 0.02, (0, 0, 0.13), "paint_red", segs=12, parent=root)
    k.torus("handle", 0.07, 0.012, (-0.47, 0, 0.06), "iron_black", rot=(math.pi / 2, 0, 0), parent=root, segs=12,
            tube_segs=4)
    for x, y in ((0.3, 0.22), (-0.05, 0.35), (0.2, -0.3)):
        c = _ball(k, root, (x, y, 0.09), 0.08, "dirt_fill", subdiv=2)
        c.scale = (1.3, 1.0, 0.6)


def _spent(k, root, rnd):
    """A torn, uneven hole: ragged lip, lopsided bowl, a heaved slab, clods and stones flung out
    unevenly (more to one side), splinters, a patchy scorch."""
    cr = k.lathe("crater", [(0.0, 0.95), (0.08, 0.82), (0.2, 0.68), (0.13, 0.6), (0.04, 0.45), (0.008, 0.3), (0.006, 0.0)], "dirt",
                 rot=(math.pi / 2, 0, 0), segs=40, parent=root)
    for v in cr.data.vertices:                   # ragged lip and an off-centre, lumpy bowl
        r = math.hypot(v.co.x, v.co.z)
        if r < 1e-4:
            continue
        a = math.atan2(v.co.z, v.co.x)
        f = 1.0 + 0.16 * math.sin(3 * a + 0.7) + 0.08 * math.sin(7 * a + 2.1) + rnd.uniform(-0.07, 0.07)
        v.co.x *= f
        v.co.z *= f
        v.co.x += 0.06 * max(0.0, 1 - r / 0.95)
        if v.co.y > 0.02:
            v.co.y *= 1.0 + 0.6 * max(0.0, math.cos(a - 0.6)) + rnd.uniform(-0.3, 0.4)
    for i in range(3):                           # patchy scorch
        a = rnd.uniform(0, 2 * math.pi)
        d = rnd.uniform(0.0, 0.25)
        sc = k.cylinder("scorch", rnd.uniform(0.25, 0.4), 0.004, (d * math.cos(a), d * math.sin(a), 0.01 + 0.002 * i),
                        "slate", segs=14, parent=root, bevel=False)
        sc.scale = (1.0, rnd.uniform(0.55, 0.9), 1.0)
        sc.rotation_euler = (0, 0, rnd.uniform(0, math.pi))
    for i in range(3):                           # heaved slabs of turf tipped up on the lip
        a = 0.6 + rnd.uniform(-1.2, 1.2)
        d = rnd.uniform(0.72, 0.9)
        k.box("turf_slab", (rnd.uniform(0.2, 0.32), rnd.uniform(0.14, 0.22), 0.06),
              (d * math.cos(a), d * math.sin(a), 0.1), "dirt_fill", rot=(rnd.uniform(0.4, 0.9), 0, a), parent=root,
              bevel=0.01)
    for i in range(40):                          # clods: bigger near the lip, flung further on one side
        a = rnd.gauss(0.6, 1.3)
        d = rnd.uniform(0.75, 1.0) + abs(rnd.gauss(0, 0.35)) * (1.0 + max(0.0, math.cos(a - 0.6)))
        r = rnd.uniform(0.03, 0.1) * (1.25 - 0.35 * min(1.0, (d - 0.75) / 0.8))
        c = _ball(k, root, (d * math.cos(a), d * math.sin(a), r * 0.3), r, "dirt_fill", subdiv=1)
        c.scale = (rnd.uniform(0.9, 1.6), rnd.uniform(0.8, 1.2), rnd.uniform(0.5, 0.9))
        c.rotation_euler = (0, 0, rnd.uniform(0, math.pi))
    for i in range(7):                           # stones thrown out of the hole
        a = rnd.uniform(0, 2 * math.pi)
        d = rnd.uniform(0.5, 1.4)
        b = _ball(k, root, (d * math.cos(a), d * math.sin(a), 0.02), rnd.uniform(0.03, 0.06), "stone", subdiv=2)
        b.scale = (1.3, 1.0, 0.7)
    for i in range(4):                           # splinters
        a = rnd.uniform(0, 2 * math.pi)
        d = rnd.uniform(0.6, 1.2)
        p0 = Vector((d * math.cos(a), d * math.sin(a), 0.02))
        e = Vector((math.cos(a + 1.2), math.sin(a + 1.2), 0.05)) * rnd.uniform(0.12, 0.22)
        k.beam("splinter", p0, p0 + e, (0.025, 0.012), "timber_raw", parent=root, bevel=False)
