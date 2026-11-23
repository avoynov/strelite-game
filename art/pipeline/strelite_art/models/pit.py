"""Яма (trap id pit): a spike pit dug in the road, one tile. Three armed looks (base and two
research levels, Game.trapLevel 1-3) and the spent look once something fell in. Nothing turns.

Looks:
  1  a pit covered with crossed branches, leaves and a little soil
  2  a plank trapdoor in a timber frame on iron hinges; iron-tipped stakes show at the gaps
  3  an iron-bound sprung trapdoor, a spring and a release lever at the side; steel spikes
     (Caesar's lilia) glint through the slots
  4  spent: the cover fallen in; the pit is dug into the ground itself (ground() digs it),
     stakes on its floor, branches fallen in (LEVEL 4 here is the spent look)
Built a little larger than life (SCALE) so it reads on a 4 m tile.
"""
import math
import random

from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit
from .trebuchet import _ball

LEVELS = (1, 2, 3, 4)
FRAME_M = 4.0
TARGET_Z = 0.2
SPRITE_FRAME_M = 4.5
FOOTPRINT_M = 1.7
SCALE = 1.2
HALF = 1.0               # half the pit's side
DEPTH = 0.75             # the open pit's depth (model units)


def build(style, level=1):
    k = Kit(style)
    root = k.empty("pit")
    root.scale = (SCALE, SCALE, SCALE)
    turret = k.empty("turret", (0, 0, 0), parent=root)     # nothing turns; kept for the renderer
    turret["node"] = "turret"
    mp.set_reference(root)
    rnd = random.Random(10 + level)
    _rim(k, root, rnd, torn=level == 4)
    (_branches, _planks, _iron, _spent)[level - 1](k, root, rnd)
    return root, turret


def ground(level):
    from ..terrain import Patch
    p = Patch(r_solid=1.8, r_out=2.2, r_bare=2.2, seed=50 + level, ragged=0.3)
    if level == 4:                               # a real hole: the ground itself is dug out
        p.square_pit(HALF * SCALE - 0.05, DEPTH * SCALE)
    return p


def _rim(k, root, rnd, torn=False):
    """Dug soil round the edge."""
    for i in range(22 if torn else 14):
        a = 2 * math.pi * i / (22 if torn else 14) + rnd.uniform(-0.1, 0.1)
        d = HALF * rnd.uniform(1.05, 1.35 if torn else 1.2) / max(abs(math.cos(a)), abs(math.sin(a))) ** 0.35
        c = _ball(k, root, (d * math.cos(a), d * math.sin(a), 0.0), rnd.uniform(0.07, 0.13 if torn else 0.1),
                  "dirt_fill", subdiv=1)
        c.scale = (1.4, 1.0, 0.5)
        c.rotation_euler = (0, 0, a)


def _stakes(k, root, rnd, mat_shaft, mat_tip, n=9, h=0.25, tip=0.1, spread=0.75):
    for i in range(n):
        x = rnd.uniform(-spread, spread)
        y = rnd.uniform(-spread, spread)
        lean = Vector((rnd.uniform(-0.05, 0.05), rnd.uniform(-0.05, 0.05), 1)).normalized()
        b = Vector((x, y, -0.05))
        k.tube("stake", b, b + lean * h, 0.035, mat_shaft, parent=root, segs=8)
        k.tube("stake_tip", b + lean * h, b + lean * (h + tip), 0.035, mat_tip, radius_end=0.003, parent=root, segs=8,
               bevel=False)


def _branches(k, root, rnd):
    k.box("cover_soil", (2 * HALF, 2 * HALF, 0.02), (0, 0, 0.01), "dirt", parent=root, bevel=False)
    for i in range(14):                         # crossed branches
        a = rnd.uniform(0, math.pi)
        off = rnd.uniform(-0.7, 0.7)
        d = Vector((math.cos(a), math.sin(a), 0))
        n = Vector((-d.y, d.x, 0))
        p0 = n * off - d * 1.15 + Vector((0, 0, 0.05 + 0.02 * (i % 3)))
        p1 = n * off + d * 1.15 + Vector((0, 0, 0.05 + 0.02 * ((i + 1) % 3)))
        k.tube("branch", p0, p1, rnd.uniform(0.022, 0.04), "timber_raw", radius_end=0.012, parent=root, segs=7)
        m = p0.lerp(p1, rnd.uniform(0.3, 0.7))   # a twig off it
        k.tube("twig", m, m + (d * 0.25 + n * 0.25 * rnd.choice((-1, 1))), 0.012, "timber_raw", radius_end=0.004,
               parent=root, segs=5)
    for i in range(40):                         # leaves and grass tufts over the top
        p = (rnd.uniform(-HALF, HALF), rnd.uniform(-HALF, HALF), 0.1)
        lf = k.cylinder("leaf", rnd.uniform(0.05, 0.09), 0.006, p, "grass" if i % 3 else "dirt_fill", segs=6,
                        parent=root, bevel=False)
        lf.scale = (1.0, 0.55, 1.0)
        lf.rotation_euler = (rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), rnd.uniform(0, math.pi))


def _planks(k, root, rnd):
    for sx in (-1, 1):                          # frame
        k.box("frame", (0.12, 2 * HALF + 0.24, 0.1), (sx * (HALF + 0.06), 0, 0.05), "timber_oak", parent=root)
        k.box("frame", (2 * HALF + 0.24, 0.12, 0.1), (0, sx * (HALF + 0.06), 0.05), "timber_oak", parent=root)
    _stakes(k, root, rnd, "timber_raw", "iron_forged", n=11, h=0.08, tip=0.06)
    for i in range(7):                          # planks with gaps
        x = -HALF + 0.14 + i * (2 * HALF - 0.28) / 6
        k.box("plank", (0.24, 2 * HALF, 0.05), (x, 0, 0.09 + 0.004 * (i % 2)), "timber_raw",
              rot=(0, rnd.uniform(-0.02, 0.02), 0), parent=root, bevel=0.006)
    for sy in (-1, 1):                          # cross battens and iron hinges
        k.box("batten", (2 * HALF - 0.1, 0.12, 0.04), (0, sy * 0.6, 0.135), "timber_raw", parent=root, bevel=0.004)
        for x in (-0.5, 0.5):
            k.box("hinge", (0.06, 0.28, 0.015), (x, sy * (HALF - 0.08), 0.125), "iron_black", parent=root, bevel=False)
    for i in range(12):                         # a dusting of soil
        c = _ball(k, root, (rnd.uniform(-0.9, 0.9), rnd.uniform(-0.9, 0.9), 0.11), rnd.uniform(0.04, 0.07),
                  "dirt_fill", subdiv=1)
        c.scale = (1.5, 1.0, 0.35)


def _iron(k, root, rnd):
    for sx in (-1, 1):                          # iron frame
        k.box("frame", (0.1, 2 * HALF + 0.2, 0.08), (sx * (HALF + 0.05), 0, 0.04), "iron_black", parent=root)
        k.box("frame", (2 * HALF + 0.2, 0.1, 0.08), (0, sx * (HALF + 0.05), 0.04), "iron_black", parent=root)
    for y in (-0.5, 0.0, 0.5):                  # steel spikes standing up through the slots
        for x in (-0.75, -0.45, -0.15, 0.15, 0.45, 0.75):
            b = Vector((x + rnd.uniform(-0.04, 0.04), y, 0.0))
            k.tube("spike", b, b + Vector((0, 0, 0.11)), 0.022, "steel_worn", parent=root, segs=8)
            k.tube("spike_tip", b + Vector((0, 0, 0.11)), b + Vector((0, 0, 0.2)), 0.022, "iron_clean",
                   radius_end=0.002, parent=root, segs=8, bevel=False)
    for sx in (-1, 1):                          # two leaves meeting in the middle, slots between the boards
        for j in range(4):
            y = -HALF + 0.25 + j * 0.5
            k.box("leaf_board", (HALF - 0.04, 0.4, 0.04), (sx * HALF / 2, y, 0.1), "timber_oak", parent=root,
                  bevel=0.004)
        k.box("leaf_band", (0.08, 2 * HALF, 0.02), (sx * 0.08, 0, 0.13), "iron_black", parent=root, bevel=False)
        k.box("leaf_band", (0.08, 2 * HALF, 0.02), (sx * (HALF - 0.1), 0, 0.13), "iron_black", parent=root, bevel=False)
        for y in (-0.6, 0.0, 0.6):
            for x in (0.08, HALF - 0.1):
                _ball(k, root, (sx * x, y, 0.145), 0.018, "iron_clean", subdiv=1)
    p = Vector((HALF + 0.22, -0.3, 0.0))        # the spring and release lever at the side
    k.box("spring_post", (0.14, 0.14, 0.4), p + Vector((0, 0, 0.2)), "iron_black", parent=root)
    pts = []
    for i in range(41):
        t = i / 40
        pts.append((p.x + 0.08 * math.cos(t * 14 * math.pi), p.y + 0.28 + 0.08 * math.sin(t * 14 * math.pi),
                    0.05 + 0.32 * t))
    k.hose("spring", pts, 0.012, "iron_clean", parent=root)
    k.beam("lever", p + Vector((0, 0, 0.4)), p + Vector((-0.5, 0.45, 0.22)), (0.05, 0.04), "iron_black", parent=root)
    _ball(k, root, p + Vector((-0.5, 0.45, 0.22)), 0.04, "iron_clean", subdiv=2)


def _spent(k, root, rnd):
    """The ground is dug out (ground() digs the pit); stakes stand on its floor, the cover's
    branches have fallen in, one hangs over the edge."""
    for i in range(14):                         # stakes on the floor of the pit
        b = Vector((rnd.uniform(-0.7, 0.7), rnd.uniform(-0.7, 0.7), -DEPTH))
        lean = Vector((rnd.uniform(-0.08, 0.08), rnd.uniform(-0.08, 0.08), 1)).normalized()
        k.tube("stake", b, b + lean * 0.45, 0.04, "timber_raw", parent=root, segs=8)
        k.tube("stake_tip", b + lean * 0.45, b + lean * 0.6, 0.04, "iron_forged", radius_end=0.003, parent=root,
               segs=8, bevel=False)
    for i in range(7):                          # fallen branches on the stakes and the floor
        a = rnd.uniform(0, math.pi)
        d = Vector((math.cos(a), math.sin(a), 0))
        c = Vector((rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), -DEPTH + rnd.uniform(0.1, 0.45)))
        k.tube("fallen_branch", c - d * 0.7, c + d * 0.7 + Vector((0, 0, rnd.uniform(-0.15, 0.15))),
               0.03, "timber_raw", radius_end=0.012, parent=root, segs=7)
    for i in range(3):                          # branches still lying across the edge, sagging in
        a = rnd.uniform(0, 2 * math.pi)
        p0 = Vector((math.cos(a), math.sin(a), 0)) * (HALF + 0.25) + Vector((0, 0, 0.04))
        p1 = Vector((math.cos(a), math.sin(a), 0)) * 0.3 + Vector((0, 0, -0.35))
        k.tube("broken_branch", p0, p1, 0.03, "timber_raw", radius_end=0.012, parent=root, segs=7)
