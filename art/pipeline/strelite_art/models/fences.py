"""Siege-mode walls (bg: „Стени“), one material per level, built as pieces the game
assembles per 4 m tile: a centre `post` and four half-segments from the tile centre to
each tile edge. Thin walls, about 2 m high and 0.5-0.8 m thick.

Grid directions (render_fences.py keeps the enemy convention): grid +x = world +X,
grid +y = world -Y. So px runs to +X, nx to -X, py to -Y, ny to +Y.

Every pattern repeats with a period that divides 2 m, so a segment ending at the tile
edge meets its neighbour's segment without a seam.

  wood   timber palisade: sharpened stakes, two iron bands, a rail and braces inside.
  stone  dressed-stone wall: coursed blocks in mortar, a coping, a pillar as the post.
  steel  riveted steel wall: plates between ribs, a brass-trimmed top rail, a steam
         pipe along it; a round column with brass bands and a lamp as the post.
"""
import math
import random

from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit

MATERIALS = ("wood", "stone", "steel")
PIECES = ("post", "px", "nx", "py", "ny")
DIR = {"px": (1, 0), "nx": (-1, 0), "py": (0, -1), "ny": (0, 1)}
HALF = 2.0                      # tile centre to tile edge, metres
HEIGHT = {"wood": 2.2, "stone": 1.9, "steel": 2.0}
THICK = {"wood": 0.5, "stone": 0.65, "steel": 0.55}
NAMES = {"wood": {"bg": "Дървена палисада", "en": "Timber palisade"},
         "stone": {"bg": "Каменна стена", "en": "Stone wall"},
         "steel": {"bg": "Стоманена стена", "en": "Steel wall"}}


def build(material, piece):
    k = Kit("photoreal")
    root = k.empty("fence")
    mp.set_reference(root)
    if piece == "post":
        {"wood": _wood_post, "stone": _stone_post, "steel": _steel_post}[material](k, root)
    else:
        seg = k.empty("segment", parent=root)
        dx, dy = DIR[piece]
        seg.rotation_euler = (0, 0, math.atan2(dy, dx))       # local +X runs along the segment
        {"wood": _wood_seg, "stone": _stone_seg, "steel": _steel_seg}[material](k, seg, piece)
    return root


# --------------------------------------------------------------------------- wood
def _stake(k, parent, x, y, h, r, rnd):
    lean = (rnd.uniform(-0.03, 0.03), rnd.uniform(-0.03, 0.03))
    e = k.empty("stake", (x, y, 0), parent=parent)
    e.rotation_euler = (lean[0], lean[1], rnd.uniform(0, math.pi))
    k.cylinder("stake", r, h - r * 2.2, (0, 0, -0.3), "log", segs=10, parent=e)
    k.cylinder("stake_point", r, r * 2.2, (0, 0, h - r * 2.2 - 0.3), "timber_raw", segs=10, parent=e,
               radius_top=0.012)


def _wood_seg(k, seg, piece):
    rnd = random.Random(7)
    h = HEIGHT["wood"]
    for i in range(9):                                     # stakes at 0.3 .. 1.9 m, 0.2 m apart
        x = 0.3 + 0.2 * i
        _stake(k, seg, x, rnd.uniform(-0.03, 0.03), h + 0.3 + rnd.uniform(-0.15, 0.1), 0.1, rnd)
    for z in (0.55, 1.55):                                 # iron bands on the outer face
        k.box("band", (HALF - 0.15, 0.015, 0.07), ((HALF + 0.15) / 2, 0.105, z), "iron_forged", parent=seg,
              bevel=False)
        for i in range(4):
            k.cylinder("band_nail", 0.018, 0.02, (0.4 + 0.4 * i, 0.115, z), "iron_black", segs=6,
                       rot=(-math.pi / 2, 0, 0), parent=seg, bevel=False)
    k.box("rail", (HALF - 0.1, 0.12, 0.14), ((HALF + 0.1) / 2, -0.17, 1.2), "timber_raw", parent=seg, bevel=0.01)
    a, b = Vector((1.1, -0.15, 1.15)), Vector((1.1, -0.7, 0.0))     # one brace on the inner side
    k.beam("brace", a, b, (0.1, 0.1), "timber_raw", parent=seg, bevel=False)
    k.box("brace_foot", (0.2, 0.2, 0.06), (1.1, -0.7, 0.03), "stone", parent=seg)


def _wood_post(k, root):
    rnd = random.Random(3)
    h = HEIGHT["wood"]
    for i in range(5):
        a = 2 * math.pi * i / 5
        _stake(k, root, 0.1 * math.cos(a), 0.1 * math.sin(a), h + 0.55 + rnd.uniform(-0.1, 0.1), 0.11, rnd)
    _stake(k, root, 0, 0, h + 0.8, 0.13, rnd)
    for z in (0.5, 1.5):
        k.torus("post_band", 0.24, 0.025, (0, 0, z), "iron_forged", parent=root, segs=24, tube_segs=6)
    k.hose("post_rope", [(0.24 * math.cos(a), 0.24 * math.sin(a), 1.0 + 0.03 * math.sin(3 * a))
                         for a in [i * math.pi / 8 for i in range(17)]], 0.02, "hemp", parent=root)


# --------------------------------------------------------------------------- stone
def _stone_seg(k, seg, piece):
    rnd = random.Random(11)
    h, t = HEIGHT["stone"], THICK["stone"]
    k.box("mortar_core", (HALF, t - 0.04, h - 0.1), (HALF / 2, 0, (h - 0.1) / 2), "concrete", parent=seg,
          bevel=False)
    k.box("footing", (HALF, t + 0.12, 0.12), (HALF / 2, 0, 0.06), "stone", parent=seg, bevel=0.015)
    course, z, row = 0.28, 0.12, 0
    while z + course <= h - 0.12 + 1e-6:
        off = 0.25 if row % 2 else 0.0                    # running bond, 0.5 m blocks
        x = -off
        while x < HALF - 1e-6:
            x0, x1 = max(x, 0.0), min(x + 0.5, HALF)
            for sy in (-1, 1):
                k.box("block", (x1 - x0 - 0.025, 0.12, course - 0.025),
                      ((x0 + x1) / 2, sy * (t / 2 - 0.05 + rnd.uniform(-0.006, 0.006)), z + course / 2),
                      "stone", parent=seg, bevel=0.02)
            x += 0.5
        z += course
        row += 1
    for i in range(4):                                     # coping stones, a little proud
        k.box("coping", (0.475, t + 0.08, 0.12), (0.25 + 0.5 * i, 0, z + 0.06), "stone", parent=seg, bevel=0.02)


def _stone_post(k, root):
    h, w = HEIGHT["stone"] + 0.35, 0.9
    k.box("pillar_core", (w - 0.04, w - 0.04, h), (0, 0, h / 2), "concrete", parent=root, bevel=False)
    z, i = 0.0, 0
    while z < h - 0.3:
        hh = 0.3
        for sx, sy, lx, ly in ((1, 0, 0.06, w), (-1, 0, 0.06, w), (0, 1, w, 0.06), (0, -1, w, 0.06)):
            k.box("quoin", (lx + (0.02 if i % 2 else 0), ly, hh - 0.025),
                  (sx * (w / 2 - 0.03), sy * (w / 2 - 0.03), z + hh / 2), "stone", parent=root, bevel=0.02)
        z += hh
        i += 1
    k.box("pillar_cap", (w + 0.14, w + 0.14, 0.14), (0, 0, z + 0.07), "stone", parent=root, bevel=0.03)
    k.cylinder("pillar_ball", 0.2, 0.25, (0, 0, z + 0.14), "stone", segs=20, parent=root, radius_top=0.08)


# --------------------------------------------------------------------------- steel
def _steel_seg(k, seg, piece):
    h, t = HEIGHT["steel"], THICK["steel"]
    k.box("plate_back", (HALF, 0.03, h - 0.1), (HALF / 2, -t / 2 + 0.1, (h - 0.1) / 2), "paint_steel", parent=seg,
          bevel=False)
    for i in range(4):                                     # four 0.5 m plates on the outer face
        x = 0.25 + 0.5 * i
        k.box("plate", (0.48, 0.025, h - 0.25), (x, t / 2 - 0.1, (h - 0.1) / 2), "paint_steel", parent=seg,
              bevel=0.006)
        for z in (0.2, (h - 0.1) / 2, h - 0.3):
            for xr in (x - 0.19, x + 0.19):
                k.cylinder("rivet", 0.018, 0.012, (xr, t / 2 - 0.087, z), "steel_worn", segs=8,
                           rot=(-math.pi / 2, 0, 0), parent=seg, bevel=False)
        k.box("rib", (0.06, t - 0.1, h - 0.1), (0.5 * i + 0.5, 0, (h - 0.1) / 2), "iron_black", parent=seg,
              bevel=0.006)
    k.box("top_rail", (HALF, t, 0.1), (HALF / 2, 0, h - 0.05), "iron_black", parent=seg, bevel=0.01)
    k.box("top_trim", (HALF, 0.03, 0.03), (HALF / 2, t / 2 + 0.01, h - 0.05), "brass", parent=seg, bevel=False)
    k.box("foot_rail", (HALF, t + 0.06, 0.12), (HALF / 2, 0, 0.06), "iron_black", parent=seg, bevel=0.01)
    k.tube("steam_pipe", (0, -t / 2 - 0.02, 1.25), (HALF, -t / 2 - 0.02, 1.25), 0.05, "copper", parent=seg, segs=14)
    for x in (0.5, 1.5):
        k.cylinder("pipe_clamp", 0.06, 0.05, (x - 0.025, -t / 2 - 0.02, 1.25), "brass", segs=14,
                   rot=(0, math.pi / 2, 0), parent=seg, bevel=False)
    k.cylinder("pipe_flange", 0.075, 0.03, (HALF - 0.03, -t / 2 - 0.02, 1.25), "brass", segs=14,
               rot=(0, math.pi / 2, 0), parent=seg, bevel=False)


def _steel_post(k, root):
    from . import faction  # noqa: F401  (shared helpers live there; the lamp is drawn here)
    h = HEIGHT["steel"] + 0.4
    k.cylinder("column", 0.32, h, (0, 0, 0), "iron_black", segs=28, parent=root)
    k.cylinder("column_base", 0.42, 0.18, (0, 0, 0), "iron_black", segs=28, parent=root, radius_top=0.36)
    for z in (0.45, 1.25, h - 0.25):
        k.cylinder("column_band", 0.335, 0.06, (0, 0, z), "brass", segs=28, parent=root, bevel=False)
    k.cylinder("column_cap", 0.38, 0.1, (0, 0, h), "brass", segs=28, parent=root, radius_top=0.3)
    k.cylinder("lamp_stem", 0.04, 0.25, (0, 0, h + 0.1), "iron_black", segs=10, parent=root)
    k.cylinder("lamp_glass", 0.11, 0.2, (0, 0, h + 0.35), "glass", segs=16, parent=root)
    k.cylinder("lamp_cap", 0.15, 0.08, (0, 0, h + 0.55), "brass", segs=16, parent=root, radius_top=0.04)
    k.cylinder("lamp_glow", 0.06, 0.12, (0, 0, h + 0.39), "ember", segs=12, parent=root, bevel=False)
    for i in range(12):
        a = 2 * math.pi * i / 12
        k.cylinder("column_rivet", 0.02, 0.015, (0.33 * math.cos(a), 0.33 * math.sin(a), 0.85), "steel_worn",
                   segs=8, rot=(0, math.pi / 2, a), parent=root, bevel=False)
