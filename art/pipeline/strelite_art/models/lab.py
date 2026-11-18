"""Laboratory of the player's base (bg: „Лаборатория“), 2 x 2 tiles (8 x 8 m), 5 levels.

The defenders' research workshop grows from a smithy into a scientific institute.
The silhouette stays: a long workshop with a tall chimney at its back-left corner.
Each level changes the building's material and adds one new kind of research
machine (a higher lab opens deeper research in the game):

  L1  plank workshop on posts; open forge with hand bellows, anvil       (raw timber)
  L2  rubble ground floor, tarred timber upper; riveted steam boiler
      with an iron stack and copper pipes into the wall                 (stone, iron)
  L3  dressed stone hall, sawtooth glass roof on iron trusses; a steam
      engine with a big flywheel and a belt into the hall               (ashlar, glass)
  L4  observatory tower with a verdigris dome, shutter slit, telescope;
      copper stills with coils by the wall                              (stone, copper)
  L5  pale stone and a brass-ribbed glass dome; two Tesla towers
      with glowing toroids, gold trim                                   (pale stone, brass, gold)

Front faces: -Y (screen lower left, the door) and +X (screen lower right).
"""
import math

from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit
from . import building as bd
from . import defender

LEVELS = (1, 2, 3, 4, 5)
TILES = 2
FOOTPRINT_M = 4.0
SPRITE_WH_M = (15.0, 19.0)
ANCHOR_FROM_BOTTOM_M = 4.6
NAMES = {"bg": "Лаборатория", "en": "Laboratory"}


def build(style, level=1):
    k = Kit(style)
    root = k.empty("lab")
    mp.set_reference(root)
    rnd = bd.rnd_for(500 + level)
    {1: _l1, 2: _l2, 3: _l3, 4: _l4, 5: _l5}[level](k, root, rnd)
    return root, root


def ground(level):
    from ..terrain import Patch
    return Patch(r_solid=4.3, r_out=5.2, r_bare=4.0, seed=41 + level, ragged=0.5)


def _chimney(k, root, rnd, x, y, z0, h, mat="stone", cap="stone", w=0.8):
    bd.masonry(k, root, (x - w / 2, y - w / 2), (x + w / 2, y - w / 2), z0, h, w, rnd, mat=mat, course=0.25,
               unit=(0.22, 0.4), rough=0.02)
    k.box("chimney_cap", (w + 0.15, w + 0.15, 0.12), (x, y, z0 + h + 0.06), cap, parent=root, bevel=0.02)


def _shell(k, root, rnd, x0, x1, y0, y1, h, mat, door_x, wins_f, wins_s, course=0.32, unit=(0.45, 0.95), rough=0.03):
    skf = ((door_x - 0.6, door_x + 0.6, 0, 2.3),) + tuple((s - 0.45, s + 0.45, za, za + 1.2) for s, za in wins_f)
    sks = tuple((s - 0.45, s + 0.45, za, za + 1.2) for s, za in wins_s)
    for p0, p1, sk in (((x0, y0), (x1, y0), skf), ((x1, y0), (x1, y1), sks), ((x1, y1), (x0, y1), ()),
                       ((x0, y1), (x0, y0), ())):
        bd.masonry(k, root, p0, p1, 0, h, 0.5, rnd, mat=mat, course=course, unit=unit, rough=rough, skip=sk)
    for s, za in wins_f:
        bd.window(k, root, (x0 + s, y0 - 0.22, za + 0.6), bd.FRONT, 0.7, 1.1, frame="timber_oak", sill=mat,
                  panes=(2, 3))
    for s, za in wins_s:
        bd.window(k, root, (x1 + 0.22, y0 + s, za + 0.6), bd.SIDE, 0.7, 1.1, frame="timber_oak", sill=mat,
                  panes=(2, 3))
    k.box("core", (x1 - x0 - 0.4, y1 - y0 - 0.4, h), (0, 0, h / 2), "slate", parent=root, bevel=False)


def _l1(k, root, rnd):
    x0, x1, y0, y1 = -2.6, 1.4, -1.8, 2.0
    wall_h = 2.4
    for p0, p1, sk in (((x0, y0), (x1, y0), ((1.8, 2.7, 0, 2.0),)), ((x1, y0), (x1, y1), ((1.2, 2.2, 1.0, 1.8),)),
                       ((x1, y1), (x0, y1), ()), ((x0, y1), (x0, y0), ())):
        bd.planks(k, root, p0, p1, 0.05, wall_h, 0.05, rnd, mat="timber_raw", w=0.24, skip=sk)
    k.box("core", (x1 - x0 - 0.1, y1 - y0 - 0.1, wall_h), (0, 0, wall_h / 2), "slate", parent=root, bevel=False)
    for (xa, ya) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        k.box("post", (0.16, 0.16, wall_h + 0.1), (xa, ya, wall_h / 2), "timber_raw", parent=root, bevel=0.015)
    bd.door(k, root, (x0 + 2.25, y0 - 0.05, 0.0), bd.FRONT, 0.8, 1.9, mat="timber_raw", strap="iron_forged")
    k.box("hatch", (0.04, 1.0, 0.7), (x1 + 0.04, y0 + 1.7, 1.4), "iron_black", parent=root, bevel=False)
    rz = bd.gable_roof(k, root, x0, x1, y0, y1, wall_h, 1.0, rnd, "timber_raw", unit=(0.28, 0.3), over=0.3,
                       along="x")
    bd.gable_ends(k, root, x0 - 0.04, x1 + 0.04, y0, y1, wall_h, rz - 0.05, "timber_raw", along="x")
    # open lean-to on the +X side: forge, bellows, anvil (L1 machine)
    lx0, lx1 = x1, 3.5
    for y in (y0 + 0.2, y1 - 0.2):
        k.box("lean_post", (0.14, 0.14, 2.1), (lx1, y, 1.05), "timber_raw", parent=root, bevel=0.012)
    k.box("lean_roof", (lx1 - lx0 + 0.5, y1 - y0, 0.05), ((lx0 + lx1) / 2 + 0.15, (y0 + y1) / 2, 2.25),
          "timber_raw", rot=(0, 0.18, 0), parent=root, bevel=0.01)
    f = Vector((2.6, 1.0, 0))
    bd.masonry(k, root, (f.x - 0.6, f.y - 0.5), (f.x + 0.6, f.y - 0.5), 0, 0.85, 1.0, rnd, mat="stone", course=0.28,
               unit=(0.25, 0.45), rough=0.04)
    k.box("forge_coals", (0.8, 0.6, 0.08), f + Vector((0, -0.05, 0.88)), "ember", parent=root, bevel=0.02)
    _chimney(k, root, rnd, f.x, f.y + 0.35, 0.85, 3.2, w=0.6)
    b = f + Vector((0.0, -1.1, 0.75))                         # hand bellows: leather between two boards
    k.box("bellows_top", (0.5, 0.8, 0.04), b + Vector((0, 0, 0.12)), "timber_raw", rot=(0.12, 0, 0), parent=root)
    k.box("bellows_bot", (0.5, 0.8, 0.04), b, "timber_raw", parent=root)
    k.box("bellows_leather", (0.46, 0.7, 0.1), b + Vector((0, 0, 0.06)), "leather", parent=root, bevel=0.03)
    k.tube("bellows_nozzle", b + Vector((0, 0.4, 0.05)), f + Vector((0, -0.45, 0.6)), 0.03, "iron_forged",
           parent=root, segs=8)
    for dy in (-0.3, 0.3):
        k.box("bellows_leg", (0.06, 0.06, 0.75), b + Vector((0, dy, -0.38)), "timber_raw", parent=root)
    a = Vector((2.7, -1.0, 0))
    k.cylinder("anvil_stump", 0.3, 0.55, a, "log", segs=16, parent=root)
    k.box("anvil", (0.18, 0.5, 0.16), a + Vector((0, 0, 0.63)), "iron_black", parent=root, bevel=0.02)
    k.cylinder("anvil_horn", 0.08, 0.25, a + Vector((0, 0.25, 0.65)), "iron_black", segs=12, radius_top=0.01,
               rot=(-math.pi / 2, 0, 0), parent=root)
    bd.barrel(k, root, (-2.2, -2.5, 0), mat="timber_raw")
    bd.crate(k, root, (-1.4, -2.5, 0.22), (0.6, 0.45, 0.44), 0.2, mat="timber_raw")


def _l2(k, root, rnd):
    x0, x1, y0, y1 = -2.6, 2.2, -2.2, 2.2
    plinth, wall_h = 1.4, 2.0
    for p0, p1, sk in (((x0, y0), (x1, y0), ((2.4, 3.3, 0, 2.2),)), ((x1, y0), (x1, y1), ((1.3, 2.3, 0.7, 1.4),)),
                       ((x1, y1), (x0, y1), ()), ((x0, y1), (x0, y0), ())):
        bd.masonry(k, root, p0, p1, 0, plinth, 0.55, rnd, mat="stone", course=0.28, unit=(0.3, 0.6), rough=0.05,
                   skip=sk)
    z = plinth
    k.box("core", (x1 - x0 - 0.2, y1 - y0 - 0.2, plinth + wall_h), (0, 0, (plinth + wall_h) / 2), "slate",
          parent=root, bevel=False)
    wf = ((0.6, 1.6, 0.3, 1.5), (3.6, 4.6, 0.3, 1.5))
    ws = ((0.7, 1.7, 0.3, 1.5), (2.7, 3.7, 0.3, 1.5))
    bd.planks(k, root, (x0, y0 - 0.02), (x1, y0 - 0.02), z, wall_h, 0.06, rnd, skip=tuple((a, b, za + z, zb + z) for a, b, za, zb in wf))
    bd.planks(k, root, (x1 + 0.02, y0), (x1 + 0.02, y1), z, wall_h, 0.06, rnd, skip=tuple((a, b, za + z, zb + z) for a, b, za, zb in ws))
    bd.planks(k, root, (x1, y1 + 0.02), (x0, y1 + 0.02), z, wall_h, 0.06, rnd)
    bd.planks(k, root, (x0 - 0.02, y1), (x0 - 0.02, y0), z, wall_h, 0.06, rnd)
    for s in (1.1, 4.1):
        bd.window(k, root, (x0 + s, y0 - 0.08, z + 0.9), bd.FRONT, 0.8, 1.0, frame="timber_tarred", sill="timber_tarred")
    for s in (1.2, 3.2):
        bd.window(k, root, (x1 + 0.08, y0 + s, z + 0.9), bd.SIDE, 0.8, 1.0, frame="timber_tarred", sill="timber_tarred")
    bd.door(k, root, (x0 + 2.85, y0 - 0.28, 0.0), bd.FRONT, 0.9, 2.1, mat="timber_tarred")
    rz = bd.gable_roof(k, root, x0, x1, y0, y1, z + wall_h, 1.3, rnd, "timber_red", unit=(0.26, 0.24), over=0.35,
                       along="y")
    bd.gable_ends(k, root, x0, x1, y0 - 0.04, y1 + 0.04, z + wall_h, rz - 0.04, "timber_tarred", along="y")
    defender.emblem(k, root, (x0 + 2.85, y0 - 0.33, 2.55), (0, -1, 0), h=0.6)
    # steam boiler beside the +X wall (L2 machine)
    b = Vector((3.05, 0.4, 0))
    k.box("boiler_bed", (1.3, 2.6, 0.4), b + Vector((0, 0, 0.2)), "stone", parent=root, bevel=0.03)
    k.cylinder("boiler", 0.6, 2.3, b + Vector((0, -1.15, 1.0)), "iron_black", segs=32, rot=(-math.pi / 2, 0, 0),
               parent=root)
    for i in range(6):
        k.torus("boiler_seam", 0.61, 0.018, b + Vector((0, -1.0 + i * 0.4, 1.0)), "iron_forged",
                rot=(math.pi / 2, 0, 0), parent=root, segs=32, tube_segs=4)
    k.cylinder("firebox_door", 0.25, 0.05, b + Vector((0, -1.18, 0.9)), "iron_forged", segs=20,
               rot=(math.pi / 2, 0, 0), parent=root)
    k.box("firebox_glow", (0.2, 0.02, 0.06), b + Vector((0, -1.24, 0.8)), "ember", parent=root, bevel=False)
    k.tube("stack", b + Vector((0, 0.8, 1.5)), b + Vector((0, 0.8, 7.0)), 0.22, "iron_black", radius_end=0.18,
           parent=root, segs=20)
    for zz in (3.0, 5.0):
        k.torus("stack_band", 0.21, 0.02, b + Vector((0, 0.8, zz)), "iron_forged", parent=root, segs=20, tube_segs=4)
    k.hose("stack_stay", [b + Vector((0, 0.8, 6.0)), b + Vector((-0.8, 1.4, 4.4)), Vector((x1, 1.6, rz - 0.3))], 0.01,
           "steel_cable", parent=root)
    dome = b + Vector((0, -0.2, 1.6))
    k.cylinder("steam_dome", 0.22, 0.3, dome, "brass", segs=20, parent=root)
    k.tube("steam_pipe", dome + Vector((0, 0, 0.25)), Vector((x1 + 0.05, -0.2, 2.6)), 0.05, "copper", parent=root, segs=10)
    k.cylinder("gauge", 0.09, 0.04, dome + Vector((0.25, -0.3, 0.1)), "brass", segs=16, rot=(0, math.pi / 2, 0), parent=root)
    k.cylinder("gauge_face", 0.07, 0.01, dome + Vector((0.29, -0.3, 0.1)), "enamel_white", segs=16,
               rot=(0, math.pi / 2, 0), parent=root, bevel=False)
    k.box("coal_heap", (0.9, 0.7, 0.35), Vector((2.6, -2.7, 0.15)), "iron_black", rot=(0, 0, 0.3), parent=root, bevel=0.15)
    bd.barrel(k, root, (-2.2, -2.8, 0), mat="timber_tarred")


def _l3(k, root, rnd):
    x0, x1, y0, y1 = -2.8, 2.4, -2.4, 2.4
    h = 3.4
    _shell(k, root, rnd, x0, x1, y0, y1, h, "stone_dressed", 2.6, ((1.2, 1.0), (4.0, 1.0)), ((1.2, 1.0), (3.6, 1.0)),
           course=0.34, unit=(0.55, 1.0), rough=0.008)
    bd.door(k, root, (x0 + 2.6, y0 - 0.22, 0.0), bd.FRONT, 1.0, 2.2, mat="timber_oak")
    defender.emblem(k, root, (x0 + 2.6, y0 - 0.28, 2.75), (0, -1, 0), h=0.7)
    # sawtooth roof: four glass north lights on iron trusses
    k.box("roof_base", (x1 - x0 + 0.3, y1 - y0 + 0.3, 0.18), (0, 0, h + 0.09), "slate", parent=root, bevel=0.01)
    n = 4
    dy = (y1 - y0) / n
    for i in range(n):
        ya = y0 + i * dy
        L = math.hypot(dy, 1.02)
        ang = math.atan2(1.02, dy)
        k.box("roof_back", (x1 - x0, L, 0.04), (( x0 + x1) / 2, ya + dy / 2, h + 0.18 + 0.51), "slate",
              rot=(-ang, 0, 0), parent=root, bevel=0.005)
        k.box("north_glass", (x1 - x0 - 0.1, 0.03, 1.0), ((x0 + x1) / 2, ya + 0.02, h + 0.69), "glass", parent=root,
              bevel=False)
        for j in range(9):
            xx = x0 + 0.05 + j * (x1 - x0 - 0.1) / 8
            k.box("glazing_bar", (0.04, 0.05, 1.02), (xx, ya, h + 0.69), "iron_black", parent=root, bevel=False)
        k.box("glazing_rail", (x1 - x0, 0.06, 0.06), ((x0 + x1) / 2, ya, h + 1.2), "iron_black", parent=root, bevel=False)
    # steam engine with flywheel and belt into the hall (L3 machine)
    e = Vector((3.2, -0.6, 0))
    k.box("engine_bed", (1.1, 2.4, 0.5), e + Vector((0, 0.2, 0.25)), "stone_dressed", parent=root, bevel=0.03)
    k.cylinder("engine_cyl", 0.25, 0.9, e + Vector((0, -0.9, 0.75)), "iron_black", segs=24, rot=(-math.pi / 2, 0, 0),
               parent=root)
    k.tube("piston_rod", e + Vector((0, 0.0, 0.75)), e + Vector((0, 0.6, 0.75)), 0.03, "chrome", parent=root, segs=10)
    k.box("crosshead_guide", (0.2, 0.7, 0.12), e + Vector((0, 0.3, 0.75)), "iron_forged", parent=root, bevel=0.01)
    fw = e + Vector((0, 0.9, 1.25))
    k.cylinder("flywheel_rim", 1.05, 0.18, fw + Vector((-0.09, 0, 0)), "iron_black", segs=40, rot=(0, math.pi / 2, 0),
               parent=root)
    k.cylinder("flywheel_hole", 0.92, 0.2, fw + Vector((-0.1, 0, 0)), "slate", segs=40, rot=(0, math.pi / 2, 0),
               parent=root, bevel=False)
    for i in range(6):
        a = 2 * math.pi * i / 6
        k.beam("spoke", fw, fw + Vector((0, 0.95 * math.cos(a), 0.95 * math.sin(a))), (0.07, 0.05), "iron_black",
               parent=root)
    k.cylinder("hub", 0.15, 0.3, fw + Vector((-0.15, 0, 0)), "brass", segs=16, rot=(0, math.pi / 2, 0), parent=root)
    for sx in (-1, 1):
        k.box("pedestal", (0.15, 0.3, 1.0), fw + Vector((sx * 0.3, 0, -0.7)), "iron_forged", parent=root, bevel=0.01)
    pul = Vector((x1 + 0.1, 0.9, 2.9))
    for dz in (-1.05, 1.05):
        k.tube("belt", fw + Vector((0.12, 0, dz * 0.98)), pul + Vector((0.12, 0, dz * 0.15)), 0.02, "leather",
               parent=root, segs=6)
    k.cylinder("pulley", 0.2, 0.2, pul + Vector((0.02, 0, 0)), "iron_forged", segs=20, rot=(0, math.pi / 2, 0), parent=root)
    k.cylinder("governor", 0.04, 0.5, e + Vector((0, -0.4, 1.0)), "brass", segs=10, parent=root)
    for sx in (-1, 1):
        k.tube("governor_arm", e + Vector((0, -0.4, 1.45)), e + Vector((sx * 0.18, -0.4, 1.25)), 0.012, "brass",
               parent=root, segs=6)
        bd_ball = e + Vector((sx * 0.2, -0.4, 1.22))
        k.cylinder("governor_ball", 0.05, 0.08, bd_ball, "brass", segs=12, parent=root)
    _chimney(k, root, rnd, x0 + 0.6, y1 - 0.6, h - 0.5, 3.4, mat="stone_dressed", w=0.7)


def _l4(k, root, rnd):
    x0, x1, y0, y1 = -2.9, 2.5, -2.5, 2.5
    h = 3.6
    _shell(k, root, rnd, x0, x1, y0, y1, h, "stone_dressed", 3.6, ((1.2, 1.0), (5.0, 1.0)), ((1.4, 1.0), (3.6, 1.0)),
           course=0.36, unit=(0.6, 1.1), rough=0.006)
    bd.door(k, root, (x0 + 3.6, y0 - 0.22, 0.0), bd.FRONT, 1.1, 2.3, mat="timber_oak", strap="bronze_old")
    k.box("roof", (x1 - x0 + 0.3, y1 - y0 + 0.3, 0.25), (0, 0, h + 0.12), "copper", parent=root, bevel=0.02)
    k.box("roof_patina", (x1 - x0, y1 - y0, 0.06), (0, 0, h + 0.27), "verdigris", parent=root, bevel=0.01)
    defender.emblem(k, root, (x0 + 3.6, y0 - 0.28, 2.85), (0, -1, 0), h=0.8)
    # observatory tower with a verdigris dome, shutter slit and telescope (L4 machine)
    t = Vector((-1.0, 0.6, 0))
    r, th = 1.5, h + 2.4
    for i in range(int(th / 0.36)):
        z = i * 0.36
        nseg = 18
        off = (i % 2) * 0.5
        for j in range(nseg):
            a0 = 2 * math.pi * (j + off) / nseg
            a1 = 2 * math.pi * (j + 1 + off) / nseg
            am = (a0 + a1) / 2
            k.box("tower_block", (2 * r * math.sin(math.pi / nseg) - 0.02, 0.45, 0.34),
                  t + Vector((r * math.cos(am), r * math.sin(am), z + 0.18)), "stone_dressed",
                  rot=(0, 0, am + math.pi / 2), parent=root, bevel=0.015)
    k.cylinder("tower_core", r - 0.2, th, t, "slate", segs=32, parent=root, bevel=False)
    k.cylinder("dome_ring", r + 0.1, 0.18, t + Vector((0, 0, th)), "copper", segs=48, parent=root)
    dome = [(0, r), (0.4, r * 0.95), (0.8, r * 0.8), (1.1, r * 0.55), (1.3, r * 0.25), (1.36, 0.0)]
    k.lathe("dome", dome, "verdigris", segs=48, loc=t + Vector((0, 0, th + 0.15)), rot=(math.pi / 2, 0, 0),
            parent=root)
    sa = math.radians(-60)                                      # shutter slit toward the camera side
    d = Vector((math.cos(sa), math.sin(sa), 0))
    for sx in (-1, 1):
        side = d.cross(Vector((0, 0, 1))) * sx * 0.32
        pts = [t + side * (1 - 0.0) + d * rr + Vector((0, 0, th + 0.15 + y)) for y, rr in dome[:-1]]
        k.hose("slit_rail", pts, 0.04, "copper", parent=root)
    for y, rr in dome[1:-1]:
        k.box("slit_dark", (0.6, 0.05, 0.3), t + d * (rr + 0.02) + Vector((0, 0, th + 0.15 + y)), "iron_black",
              rot=(math.atan2(y, rr) * 0, 0, sa + math.pi / 2), parent=root, bevel=False)
    tel = t + d * 0.6 + Vector((0, 0, th + 0.6))
    k.tube("telescope", tel - d * 0.4 - Vector((0, 0, 0.3)), tel + d * 1.3 + Vector((0, 0, 0.9)), 0.12, "brass",
           radius_end=0.15, parent=root, segs=16)
    k.torus("telescope_band", 0.14, 0.015, tel + d * 0.7 + Vector((0, 0, 0.55)), "iron_black",
            rot=(0, math.radians(60), sa), parent=root, segs=16, tube_segs=4)
    for i in range(3):                                          # windows round the tower
        a = sa + math.radians(-40 + 40 * i) + 0.35
        n = Vector((math.cos(a), math.sin(a), 0))
        bd.window(k, root, t + n * (r + 0.25) + Vector((0, 0, h + 1.2)), n, 0.5, 0.9, frame="bronze_old",
                  sill="stone_dressed", panes=(1, 2))
    # copper stills with coil condensers by the +X wall
    for i, yy in enumerate((-1.2, 0.4)):
        s = Vector((x1 + 0.9, yy, 0))
        k.cylinder("still_fire", 0.45, 0.5, s, "stone", segs=20, parent=root)
        k.lathe("still_pot", [(0, 0), (0, 0.4), (0.3, 0.48), (0.7, 0.35), (0.95, 0.12), (1.3, 0.08), (1.3, 0)],
                "copper", segs=24, loc=s + Vector((0, 0, 0.5)), rot=(math.pi / 2, 0, 0), parent=root)
        top = s + Vector((0, 0, 1.8))
        coil = s + Vector((0.3, 0.75, 0.0))
        k.tube("swan_neck", top, coil + Vector((0, 0, 1.5)), 0.04, "copper", parent=root, segs=10)
        k.cylinder("worm_tub", 0.3, 1.0, coil + Vector((0, 0, 0.0)), "timber_oak", segs=20, parent=root)
        for j in range(6):
            k.torus("worm", 0.2, 0.025, coil + Vector((0, 0, 1.05 + j * 0.07)), "copper", parent=root, segs=20,
                    tube_segs=5)


def _l5(k, root, rnd):
    x0, x1, y0, y1 = -3.0, 2.6, -2.6, 2.6
    h = 4.0
    _shell(k, root, rnd, x0, x1, y0, y1, h, "stone_pale", 3.0, ((1.2, 1.2), (4.8, 1.2)), ((1.3, 1.2), (3.9, 1.2)),
           course=0.4, unit=(0.7, 1.2), rough=0.003)
    bd.door(k, root, (x0 + 3.0, y0 - 0.22, 0.0), bd.FRONT, 1.2, 2.5, mat="timber_oak", strap="gold_trim")
    for sx in (-1, 1):
        k.cylinder("column", 0.15, 2.8, (x0 + 3.0 + sx * 0.95, y0 - 0.4, 0.0), "stone_pale", segs=20, parent=root)
        k.box("column_cap", (0.4, 0.4, 0.12), (x0 + 3.0 + sx * 0.95, y0 - 0.4, 2.86), "gold_trim", parent=root,
              bevel=0.01)
    k.box("gate_lintel", (2.4, 0.45, 0.3), (x0 + 3.0, y0 - 0.35, 3.07), "stone_pale", parent=root, bevel=0.03)
    k.box("cornice", (x1 - x0 + 0.4, y1 - y0 + 0.4, 0.28), (0, 0, h + 0.14), "iron_black", parent=root, bevel=0.02)
    k.box("cornice_gold", (x1 - x0 + 0.44, y1 - y0 + 0.44, 0.06), (0, 0, h + 0.04), "gold_trim", parent=root,
          bevel=0.005)
    k.box("roof", (x1 - x0, y1 - y0, 0.2), (0, 0, h + 0.38), "slate", parent=root, bevel=0.01)
    defender.emblem(k, root, (x0 + 3.0, y0 - 0.6, 3.6), (0, -1, 0), h=1.0)
    defender.emblem(k, root, (x1 + 0.25, 0.0, 3.2), (1, 0, 0), h=1.0)
    # brass-ribbed glass dome
    c = Vector((-0.4, 0.4, h + 0.48))
    k.cylinder("dome_base", 2.0, 0.35, c, "brass", segs=56, parent=root)
    dome = [(0, 1.9), (0.5, 1.82), (1.0, 1.55), (1.4, 1.15), (1.68, 0.6), (1.78, 0.0)]
    k.lathe("dome_glass", dome, "glass", segs=56, loc=c + Vector((0, 0, 0.35)), rot=(math.pi / 2, 0, 0), parent=root)
    for i in range(20):
        a = 2 * math.pi * i / 20
        pts = [c + Vector(((rr + 0.015) * math.cos(a), (rr + 0.015) * math.sin(a), 0.35 + y)) for y, rr in dome]
        k.hose("dome_rib", pts, 0.03, "brass", parent=root)
    for y, rr in dome[1:-1]:
        k.torus("dome_hoop", rr + 0.015, 0.022, c + Vector((0, 0, 0.35 + y)), "brass", parent=root, segs=56,
                tube_segs=4)
    k.lathe("lantern", [(0, 0.0), (0, 0.3), (0.35, 0.25), (0.5, 0.0)], "gold_trim", segs=24,
            loc=c + Vector((0, 0, 2.1)), rot=(math.pi / 2, 0, 0), parent=root)
    # two Tesla towers with glowing toroids (L5 machine)
    for tx, ty in ((x1 + 0.9, -1.6), (x1 + 0.9, 1.4)):
        b = Vector((tx, ty, 0))
        k.cylinder("tesla_plinth", 0.5, 0.4, b, "stone_pale", segs=24, parent=root)
        k.cylinder("tesla_coil", 0.22, 2.0, b + Vector((0, 0, 0.4)), "porcelain", segs=24, parent=root)
        for j in range(12):
            k.torus("tesla_wind", 0.23, 0.012, b + Vector((0, 0, 0.55 + j * 0.15)), "copper", parent=root, segs=24,
                    tube_segs=4)
        k.torus("tesla_toroid", 0.38, 0.12, b + Vector((0, 0, 2.55)), "brass", parent=root, segs=32, tube_segs=12)
        k.lathe("tesla_glow", [(0, 0), (0, 0.1), (0.12, 0.13), (0.24, 0.0)], "arc_glow", segs=16,
                loc=b + Vector((0, 0, 2.62)), rot=(math.pi / 2, 0, 0), parent=root)
        k.cylinder("tesla_gold", 0.52, 0.06, b + Vector((0, 0, 0.4)), "gold_trim", segs=24, parent=root)
    _chimney(k, root, rnd, x0 + 0.6, y1 - 0.5, h - 0.4, 2.6, mat="stone_pale", cap="gold_trim", w=0.6)
