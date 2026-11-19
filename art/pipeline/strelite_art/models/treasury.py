"""Treasury of the player's base (bg: „Хазна“), 2 x 2 tiles (8 x 8 m), 5 levels.

Holds the gold; in the game its level protects part of the gold from raiders,
and the motorcycle raiders go for it first. The silhouette stays: a squat,
heavy, square strongroom with a low pyramid or dome roof and a pile of gold
in front of a barred door, so it never reads as the long halls (muster,
arsenal) or the tall HQ. Each level changes the building's material and adds
one new kind of securing mechanism:

  L1  log strongroom on stone pads; an iron-bound chest with a big
      padlock and hasp                                                  (raw logs, iron)
  L2  rubble stone, iron bars on the windows, a plank door with iron
      straps; a beam balance for weighing gold under a little roof      (stone, forged iron)
  L3  thick buttressed vault of dressed stone; a round steel vault door
      with a spoked handwheel, standing open                            (ashlar, steel)
  L4  black iron plated vault, riveted; a clockwork time lock: brass
      gears behind a glazed case on the front                           (black iron, brass)
  L5  pale marble with gilded columns and a gilded dome; a screw coin
      press with a weighted balance arm                                 (pale stone, gold)

The gold pile by the door grows with the level: coin sacks, a chest,
ingots, stacked ingots and coin heaps.
Front faces: -Y (screen lower left, the door) and +X (screen lower right).
Static object: one frame per level (render_buildings.py).
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
NAMES = {"bg": "Хазна", "en": "Treasury"}


def build(style, level=1):
    k = Kit(style)
    root = k.empty("treasury")
    mp.set_reference(root)
    rnd = bd.rnd_for(800 + level)
    {1: _l1, 2: _l2, 3: _l3, 4: _l4, 5: _l5}[level](k, root, rnd)
    _gold(k, root, level, rnd)
    return root, root


def ground(level):
    from ..terrain import Patch
    return Patch(r_solid=4.3, r_out=5.2, r_bare=4.0, seed=81 + level, ragged=0.5)


# ---------------------------------------------------------------------------
def sack(k, root, loc, r=0.22, mat="burlap", tie="rope"):
    loc = Vector(loc)
    prof = [(0, 0.0), (0.0, r * 0.8), (r * 0.5, r), (r * 1.2, r * 0.9), (r * 1.6, r * 0.45), (r * 1.75, r * 0.2),
            (r * 2.05, r * 0.3), (r * 2.1, 0.0)]
    k.lathe("sack", prof, mat, segs=16, loc=loc, rot=(math.pi / 2, 0, 0), parent=root)
    k.torus("sack_tie", r * 0.22, 0.015, loc + Vector((0, 0, r * 1.75)), tie, parent=root, segs=12, tube_segs=4)


def ingot(k, root, loc, yaw=0.0, mat="gold_trim"):
    loc = Vector(loc)
    v = [(-0.14, -0.06, 0), (0.14, -0.06, 0), (0.14, 0.06, 0), (-0.14, 0.06, 0),
         (-0.11, -0.04, 0.07), (0.11, -0.04, 0.07), (0.11, 0.04, 0.07), (-0.11, 0.04, 0.07)]
    f = [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    o = k.mesh("ingot", v, f)
    o.location = loc
    o.rotation_euler = (0, 0, yaw)
    k._finish(o, mat, bevel=0.006, parent=root)


def coin_heap(k, root, loc, r, h, mat="gold_trim"):
    k.lathe("coin_heap", [(0, 0.0), (0.0, r), (h * 0.3, r * 0.75), (h * 0.7, r * 0.4), (h, 0.0)], mat, segs=24,
            loc=Vector(loc), rot=(math.pi / 2, 0, 0), parent=root)


def chest(k, root, loc, size, yaw, wood, band, lock="iron_black", open_=False):
    loc = Vector(loc)
    sx, sy, sz = size
    k.box("chest", (sx, sy, sz), loc + Vector((0, 0, sz / 2)), wood, rot=(0, 0, yaw), parent=root, bevel=0.015)
    lid = loc + Vector((0, 0, sz))
    if open_:
        k.box("chest_lid", (sx, 0.05, sy * 0.9), lid + Vector((0, 0, 0)) + Vector((-math.sin(yaw), math.cos(yaw), 0)) * sy * 0.5
              + Vector((0, 0, sy * 0.45)), wood, rot=(0.2, 0, yaw), parent=root, bevel=0.01)
        coin_heap(k, root, lid - Vector((0, 0, 0.05)), min(sx, sy) * 0.45, 0.18)
    else:
        k.cylinder("chest_lid", sy / 2, sx, lid + Vector((-math.cos(yaw), -math.sin(yaw), 0)) * (sx / 2), wood,
                   segs=16, rot=(0, math.pi / 2, yaw), parent=root, bevel=0.01)
    d = Vector((math.cos(yaw), math.sin(yaw), 0))
    for t in (-0.38, 0.38):
        k.box("chest_band", (0.06, sy + 0.02, sz + 0.02), loc + d * (t * sx) + Vector((0, 0, sz / 2)), band,
              rot=(0, 0, yaw), parent=root, bevel=False)
    front = Vector((math.sin(yaw), -math.cos(yaw), 0))
    k.box("hasp", (0.08, 0.03, 0.18), loc + front * (sy / 2 + 0.02) + Vector((0, 0, sz - 0.05)), band,
          rot=(0, 0, yaw), parent=root, bevel=False)
    k.box("padlock", (0.14, 0.06, 0.14), loc + front * (sy / 2 + 0.05) + Vector((0, 0, sz - 0.2)), lock,
          rot=(0, 0, yaw), parent=root, bevel=0.01)
    k.torus("padlock_shackle", 0.05, 0.012, loc + front * (sy / 2 + 0.05) + Vector((0, 0, sz - 0.11)), lock,
            rot=(math.pi / 2, 0, yaw), parent=root, segs=12, tube_segs=4)


def _gold(k, root, level, rnd):
    """Gold pile on the camera side, bigger and brighter with the level (the treasury's mark)."""
    base = Vector((-2.6, -3.0, 0))
    sacks = {1: 3, 2: 4, 3: 3, 4: 2, 5: 2}[level]
    spots = ((0.0, 0.3), (0.55, 0.45), (0.3, 0.85), (-0.3, 0.75))
    for dx, dy in spots[:sacks]:
        sack(k, root, base + Vector((dx + 0.6, dy, 0)), r=0.27)
    heap = {1: (0.28, 0.14), 2: (0.4, 0.22), 3: (0.5, 0.28), 4: (0.6, 0.34), 5: (0.75, 0.42)}[level]
    coin_heap(k, root, base + Vector((-0.2, -0.15, 0)), *heap)
    if level >= 3:
        chest(k, root, base + Vector((-0.75, 0.75, 0)), (0.9, 0.55, 0.5), 0.35, "timber_oak" if level < 5 else
              "timber_red", "iron_black" if level < 5 else "gold_trim", open_=True)
    if level >= 4:                                     # ingots stacked crosswise
        st = base + Vector((0.45, -0.25, 0))
        for L in range(3 if level == 4 else 5):
            for i in range(3):
                if L % 2 == 0:
                    ingot(k, root, st + Vector((0, -0.13 + 0.13 * i, 0.072 * L)), 0.0)
                else:
                    ingot(k, root, st + Vector((-0.13 + 0.13 * i, 0, 0.072 * L)), math.pi / 2)
    if level == 5:
        coin_heap(k, root, base + Vector((-0.95, -0.25, 0)), 0.45, 0.25)


def _bars(k, root, centre, normal, w, h, mat="iron_forged", n=4):
    n_ = Vector(normal).normalized()
    t = Vector((-n_.y, n_.x, 0))
    c = Vector(centre) + n_ * 0.05
    for i in range(n):
        o = t * (-w / 2 + w * (i + 0.5) / n)
        k.tube("bar", c + o - Vector((0, 0, h / 2)), c + o + Vector((0, 0, h / 2)), 0.018, mat, parent=root, segs=8,
               bevel=False)
    for z in (-h / 4, h / 4):
        k.box("bar_cross", (0.03, 0.03, 0.03), c, mat, parent=root, bevel=False)
        k.tube("bar_flat", c - t * (w / 2) + Vector((0, 0, z)), c + t * (w / 2) + Vector((0, 0, z)), 0.015, mat,
               parent=root, segs=6, bevel=False)


def _pyramid_roof(k, root, x0, x1, y0, y1, z, rise, mat, rnd, over=0.3, unit=(0.3, 0.22), finial="iron_forged"):
    """Hipped (pyramid) roof of shingles or slates over a square plan."""
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hx, hy = (x1 - x0) / 2 + over, (y1 - y0) / 2 + over
    rows = int(math.hypot(hx, rise) / unit[1])
    for side in range(4):
        for r in range(rows):
            t = (r + 0.5) / rows
            half = (hx if side % 2 == 0 else hy) * (1 - t)
            dist = (hy if side % 2 == 0 else hx) * (1 - t)
            zz = z + rise * t - over * rise / max(hx, hy) * (1 - t) * 0.0
            n = max(1, int(2 * half / unit[0]))
            off = rnd.uniform(0, unit[0]) if r % 2 else 0
            for i in range(n):
                s = -half + (i + 0.5) * 2 * half / n + off * 0
                if side == 0:
                    loc, rot = (cx + s, cy - dist, zz), (math.atan2(rise, hy), 0, 0)
                elif side == 2:
                    loc, rot = (cx - s, cy + dist, zz), (-math.atan2(rise, hy), 0, 0)
                elif side == 1:
                    loc, rot = (cx + dist, cy + s, zz), (0, math.atan2(rise, hx), 0)
                else:
                    loc, rot = (cx - dist, cy - s, zz), (0, -math.atan2(rise, hx), 0)
                size = (2 * half / n - 0.012, math.hypot(dist / rows * 0 + (hy if side % 2 == 0 else hx), rise) / rows
                        * 1.5, 0.03)
                if side % 2:
                    size = (size[1], size[0], size[2])
                k.box("shingle", size, loc, mat, rot=(rot[0] + rnd.uniform(-0.02, 0.02),
                                                      rot[1] + rnd.uniform(-0.02, 0.02), 0), parent=root, bevel=0.005)
    # deck under the covering, so gaps read dark
    v = [(cx - hx, cy - hy, z - 0.05), (cx + hx, cy - hy, z - 0.05), (cx + hx, cy + hy, z - 0.05),
         (cx - hx, cy + hy, z - 0.05), (cx, cy, z + rise - 0.05)]
    o = k.mesh("roof_deck", v, [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4), (3, 2, 1, 0)])
    k._finish(o, "timber_tarred", bevel=False, parent=root)
    k.cylinder("finial", 0.1, 0.5, (cx, cy, z + rise - 0.1), finial, segs=12, radius_top=0.02, parent=root,
               bevel=False)
    return z + rise


# ---------------------------------------------------------------------------
X0, X1, Y0, Y1 = -2.4, 2.0, -1.8, 2.4       # square-ish strongroom
DOOR_S = 2.6                                 # door centre along the front wall


def _l1(k, root, rnd):
    x0, x1, y0, y1 = X0 + 0.3, X1 - 0.3, Y0 + 0.3, Y1 - 0.3
    h, r = 2.2, 0.14
    for (xa, ya) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        k.box("pad", (0.45, 0.45, 0.2), (xa, ya, 0.1), "stone", parent=root, bevel=0.03)
    ds = (DOOR_S - 0.6 - 0.45, DOOR_S - 0.6 + 0.45, 0, 1.75)
    bd.logs(k, root, (x0, y0), (x1, y0), 0.2, h, r, rnd, skip=(ds,), phase=0)
    bd.logs(k, root, (x0, y1), (x1, y1), 0.2, h, r, rnd, phase=0)
    bd.logs(k, root, (x1, y0), (x1, y1), 0.33, h, r, rnd, phase=0)
    bd.logs(k, root, (x0, y0), (x0, y1), 0.33, h, r, rnd, phase=0)
    k.box("core", (x1 - x0 - 0.1, y1 - y0 - 0.1, h), ((x0 + x1) / 2, (y0 + y1) / 2, 0.2 + h / 2), "dirt_fill",
          parent=root, bevel=False)
    bd.door(k, root, (x0 + DOOR_S - 0.6, y0 - 0.14, 0.2), bd.FRONT, 0.8, 1.6, mat="timber_raw", strap="iron_forged")
    for z in (0.6, 1.3):                                   # iron bar across the door in its brackets
        pass
    k.box("door_bar", (1.2, 0.08, 0.1), (x0 + DOOR_S - 0.6, y0 - 0.22, 1.1), "iron_forged", parent=root, bevel=0.01)
    _pyramid_roof(k, root, x0, x1, y0, y1, 0.2 + h, 1.3, "timber_raw", rnd, over=0.35, unit=(0.3, 0.4))
    # the L1 mechanism: an iron-bound chest with a big padlock and hasp beside the door
    chest(k, root, (x0 + 3.0, y0 - 1.0, 0), (1.1, 0.65, 0.6), 0.2, "timber_raw", "iron_forged", "iron_black")
    k.flag("pennant", 0.7, 0.3, (x0 + 0.0, y0 - 0.0, 0.2 + h + 1.4), "paint_blue", parent=root, waves=2, amp=0.04)


def _l2(k, root, rnd):
    x0, x1, y0, y1 = X0, X1, Y0, Y1
    h = 2.8
    ds = (DOOR_S - 0.5, DOOR_S + 0.5, 0, 2.1)
    ws = ((1.8, 2.5, 1.2, 2.0),)
    for p0, p1, sk in (((x0, y0), (x1, y0), (ds,)), ((x1, y0), (x1, y1), ws), ((x1, y1), (x0, y1), ()),
                       ((x0, y1), (x0, y0), ())):
        bd.masonry(k, root, p0, p1, 0, h, 0.6, rnd, mat="stone", course=0.28, unit=(0.3, 0.7), rough=0.05, skip=sk)
    k.box("core", (x1 - x0 - 0.5, y1 - y0 - 0.5, h), ((x0 + x1) / 2, (y0 + y1) / 2, h / 2), "iron_black", parent=root,
          bevel=False)
    bd.door(k, root, (x0 + DOOR_S, y0 - 0.27, 0.0), bd.FRONT, 0.9, 2.0, mat="timber_tarred", strap="iron_forged")
    c = Vector((x1 + 0.3, y0 + 2.15, 1.6))
    k.box("win_dark", (0.05, 0.7, 0.8), c + Vector((-0.04, 0, 0)), "iron_black", parent=root, bevel=False)
    _bars(k, root, c, (1, 0, 0), 0.7, 0.8)
    rz = _pyramid_roof(k, root, x0, x1, y0, y1, h, 1.5, "timber_tarred", rnd, over=0.35, unit=(0.3, 0.26))
    defender.emblem(k, root, (x0 + DOOR_S, y0 - 0.32, 2.45), (0, -1, 0), h=0.6)
    # beam balance under a little roof (L2 mechanism)
    b = Vector((1.6, -2.9, 0))
    for sx in (-1, 1):
        k.box("canopy_post", (0.12, 0.12, 2.3), b + Vector((sx * 0.9, 0, 1.15)), "timber_tarred", parent=root,
              bevel=0.01)
    k.box("canopy", (2.2, 1.0, 0.06), b + Vector((0, 0, 2.35)), "timber_tarred", rot=(0.15, 0, 0), parent=root,
          bevel=0.01)
    k.box("bench", (1.6, 0.6, 0.08), b + Vector((0, 0.1, 0.8)), "timber_oak", parent=root, bevel=0.01)
    for sx in (-0.7, 0.7):
        k.box("bench_leg", (0.08, 0.5, 0.8), b + Vector((sx, 0.1, 0.4)), "timber_oak", parent=root, bevel=0.005)
    k.tube("balance_post", b + Vector((0, 0.1, 0.84)), b + Vector((0, 0.1, 1.6)), 0.03, "iron_forged", parent=root,
           segs=10)
    k.beam("balance_beam", b + Vector((-0.55, 0.1, 1.62)), b + Vector((0.55, 0.1, 1.55)), (0.04, 0.04),
           "iron_forged", parent=root)
    for sx, dz in ((-0.55, 0.0), (0.55, -0.07)):
        p = b + Vector((sx, 0.1, 1.6 + dz))
        for a in range(3):
            ang = 2 * math.pi * a / 3
            k.tube("pan_chain", p, p + Vector((math.cos(ang) * 0.14, math.sin(ang) * 0.14, -0.45)), 0.005,
                   "iron_forged", parent=root, segs=4, bevel=False)
        k.cylinder("pan", 0.17, 0.04, p + Vector((0, 0, -0.5)), "brass", segs=20, radius_top=0.19, parent=root,
                   bevel=False)
    coin_heap(k, root, b + Vector((0.55, 0.1, 1.07)), 0.1, 0.06)
    k.box("ledger", (0.35, 0.25, 0.04), b + Vector((-0.2, 0.15, 0.86)), "leather", parent=root, bevel=0.005)
    bd.flag_mast(k, root, (x0 - 0.45, y0 - 0.45, 0), 5.6, mat="timber_tarred", finial="iron_forged")


def _vault_body(k, root, rnd, h, mat, course, unit, rough, buttress=True):
    x0, x1, y0, y1 = X0, X1, Y0, Y1
    ds = (DOOR_S - 0.85, DOOR_S + 0.85, 0, 2.2)
    for p0, p1, sk in (((x0, y0), (x1, y0), (ds,)), ((x1, y0), (x1, y1), ()), ((x1, y1), (x0, y1), ()),
                       ((x0, y1), (x0, y0), ())):
        bd.masonry(k, root, p0, p1, 0, h, 0.8, rnd, mat=mat, course=course, unit=unit, rough=rough, skip=sk)
    k.box("core", (x1 - x0 - 0.7, y1 - y0 - 0.7, h), ((x0 + x1) / 2, (y0 + y1) / 2, h / 2), "iron_black",
          parent=root, bevel=False)
    k.box("plinth_course", (x1 - x0 + 0.5, y1 - y0 + 0.5, 0.4), ((x0 + x1) / 2, (y0 + y1) / 2, 0.2), mat,
          parent=root, bevel=0.03)
    if buttress:
        for (xa, ya) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            for sx, sy in ((1, 0), (0, 1)):
                nx = -1 if xa < 0 else 1
                ny = -1 if ya < 0 else 1
                if sx:
                    p0 = Vector((xa, ya + ny * 0.25, 0))
                    out = Vector((0, ny, 0))
                else:
                    p0 = Vector((xa + nx * 0.25, ya, 0))
                    out = Vector((nx, 0, 0))
                k.beam("buttress", p0 + out * 0.6, p0 + out * 0.1 + Vector((0, 0, h - 0.3)), (0.6, 0.6), mat,
                       section_end=(0.5, 0.25), parent=root)
    return x0, x1, y0, y1


def _vault_door(k, root, c, normal, r, mat="steel_worn", wheel="brass", open_=1.0):
    """Round vault door standing open on its hinge, with a spoked handwheel and bolts."""
    n = Vector(normal).normalized()
    t = Vector((-n.y, n.x, 0))
    c = Vector(c)
    k.cylinder("vault_frame", r + 0.18, 0.2, c - n * 0.15, "steel_worn", segs=40,
               rot=n.to_track_quat("Z", "Y").to_euler(), parent=root, bevel=0.01)
    k.cylinder("vault_hole", r, 0.22, c - n * 0.16, "iron_black", segs=40,
               rot=n.to_track_quat("Z", "Y").to_euler(), parent=root, bevel=False)
    hinge = c + t * (r + 0.1) + n * 0.05
    d = (n * math.sin(open_) + t * math.cos(open_)).normalized()
    dc = hinge + d * r
    face = Vector((d.y, -d.x, 0)) if d.cross(n).z > 0 else Vector((-d.y, d.x, 0))
    face = n if face.dot(n) < 0 else face
    k.cylinder("vault_door", r, 0.35, dc - face * 0.175, mat, segs=40, rot=face.to_track_quat("Z", "Y").to_euler(),
               parent=root, bevel=0.015)
    k.cylinder("vault_bolt_ring", r * 0.75, 0.06, dc + face * 0.17, "steel_worn", segs=40,
               rot=face.to_track_quat("Z", "Y").to_euler(), parent=root, bevel=0.005)
    for i in range(10):
        a = 2 * math.pi * i / 10
        u = face.cross(Vector((0, 0, 1))).normalized()
        p = dc + (u * math.cos(a) + Vector((0, 0, 1)) * math.sin(a)) * (r - 0.06)
        k.tube("vault_bolt", p, p + d * 0.0 - face * 0.0 + (p - dc).normalized() * 0.1, 0.035, "chrome", parent=root,
               segs=8, bevel=False)
    w = dc + face * 0.25
    k.torus("handwheel", r * 0.45, 0.03, w, wheel, rot=face.to_track_quat("Z", "Y").to_euler(), parent=root, segs=28,
            tube_segs=6)
    u = face.cross(Vector((0, 0, 1))).normalized()
    for i in range(3):
        a = math.pi * i / 3
        e = (u * math.cos(a) + Vector((0, 0, 1)) * math.sin(a)) * r * 0.45
        k.tube("wheel_spoke", w - e, w + e, 0.022, wheel, parent=root, segs=8, bevel=False)
    k.cylinder("wheel_hub", 0.08, 0.1, w - face * 0.05, wheel, segs=16, rot=face.to_track_quat("Z", "Y").to_euler(),
               parent=root, bevel=False)
    for z in (-0.5, 0.5):
        k.cylinder("hinge_pin", 0.08, 0.3, hinge + Vector((0, 0, z * r - 0.15)), "steel_worn", segs=12, parent=root,
                   bevel=False)


def _l3(k, root, rnd):
    h = 3.2
    x0, x1, y0, y1 = _vault_body(k, root, rnd, h, "stone_dressed", 0.36, (0.5, 1.0), 0.01)
    k.box("roof_slab", (x1 - x0 + 0.4, y1 - y0 + 0.4, 0.25), ((x0 + x1) / 2, (y0 + y1) / 2, h + 0.12),
          "stone_dressed", parent=root, bevel=0.03)
    _pyramid_roof(k, root, x0 + 0.2, x1 - 0.2, y0 + 0.2, y1 - 0.2, h + 0.25, 1.7, "slate", rnd, over=0.1,
                  unit=(0.3, 0.2))
    _vault_door(k, root, (x0 + DOOR_S, y0 - 0.45, 1.2), (0, -1, 0), 0.95, open_=0.9)
    defender.emblem(k, root, (x1 + 0.45, (y0 + y1) / 2, 2.2), (1, 0, 0), h=0.8)
    bd.flag_mast(k, root, (x0 - 0.65, y0 - 0.65, 0), 6.0, mat="timber_oak", finial="brass")


def _gear(k, root, c, normal, r, teeth, mat, w=0.06):
    n = Vector(normal).normalized()
    rot = n.to_track_quat("Z", "Y").to_euler()
    k.cylinder("gear", r, w, Vector(c), mat, segs=max(24, teeth * 2), rot=rot, parent=root, bevel=False)
    u = n.cross(Vector((0, 0, 1))).normalized()
    v = n.cross(u).normalized()
    for i in range(teeth):
        a = 2 * math.pi * i / teeth
        p = Vector(c) + (u * math.cos(a) + v * math.sin(a)) * (r + 0.02) + n * (w / 2)
        k.box("gear_tooth", (0.04, 0.04, w), p, mat, rot=rot, parent=root, bevel=False)
    k.cylinder("gear_hub", r * 0.25, w + 0.04, Vector(c) - n * 0.02, "steel_worn", segs=16, rot=rot, parent=root,
               bevel=False)


def _l4(k, root, rnd):
    h = 3.5
    x0, x1, y0, y1 = _vault_body(k, root, rnd, h, "stone_dressed", 0.36, (0.6, 1.1), 0.006, buttress=False)
    for p0, p1, n in (((x0, y0), (x1, y0), (0, -1)), ((x1, y0), (x1, y1), (1, 0))):   # riveted iron cladding
        d = Vector((p1[0] - p0[0], p1[1] - p0[1], 0))
        L = d.length
        d.normalize()
        nn = Vector((n[0], n[1], 0))
        for i in range(int(L / 1.1)):
            s = (i + 0.5) * L / int(L / 1.1)
            if n == (0, -1) and abs(s - DOOR_S) < 1.2:
                continue
            c = Vector((p0[0], p0[1], 0)) + d * s + nn * 0.44
            k.box("iron_panel", (abs(d.x) * (L / int(L / 1.1) - 0.04) + abs(nn.x) * 0.05,
                                 abs(d.y) * (L / int(L / 1.1) - 0.04) + abs(nn.y) * 0.05, h - 0.5),
                  c + Vector((0, 0, h / 2 + 0.2)), "iron_black", parent=root, bevel=0.004)
            for z in [0.6 + 0.4 * j for j in range(int((h - 0.8) / 0.4) + 1)]:
                for o in (-0.4, 0.4):
                    k.cylinder("rivet", 0.022, 0.03, c + d * o + nn * 0.03 + Vector((0, 0, z)), "iron_black", segs=8,
                               rot=nn.to_track_quat("Z", "Y").to_euler(), parent=root, bevel=False)
    k.box("roof_slab", (x1 - x0 + 0.5, y1 - y0 + 0.5, 0.3), ((x0 + x1) / 2, (y0 + y1) / 2, h + 0.15), "iron_black",
          parent=root, bevel=0.02)
    _pyramid_roof(k, root, x0 + 0.1, x1 - 0.1, y0 + 0.1, y1 - 0.1, h + 0.3, 1.5, "iron_black", rnd, over=0.1,
                  unit=(0.5, 0.3), finial="brass")
    _vault_door(k, root, (x0 + DOOR_S, y0 - 0.55, 1.25), (0, -1, 0), 1.0, mat="iron_black", open_=0.8)
    # clockwork time lock: brass gears behind a glazed case beside the door (L4 mechanism)
    cc = Vector((x0 + DOOR_S + 1.65, y0 - 0.5, 2.0))
    k.box("lock_case", (1.0, 0.18, 1.2), cc, "iron_black", parent=root, bevel=0.01)
    k.box("lock_back", (0.85, 0.02, 1.05), cc + Vector((0, -0.08, 0)), "enamel_white", parent=root, bevel=False)
    for (dx, dz, r, t) in ((-0.15, 0.2, 0.22, 18), (0.2, 0.15, 0.14, 12), (0.05, -0.25, 0.18, 14),
                           (-0.25, -0.3, 0.1, 9)):
        _gear(k, root, cc + Vector((dx, -0.12, dz)), (0, -1, 0), r, t, "brass", w=0.04)
    k.box("lock_glass", (0.9, 0.02, 1.1), cc + Vector((0, -0.2, 0)), "glass", parent=root, bevel=False)
    k.cylinder("dial", 0.12, 0.03, cc + Vector((0, -0.2, 0.75)), "brass", segs=20, rot=(math.pi / 2, 0, 0),
               parent=root, bevel=False)
    defender.emblem(k, root, (x1 + 0.5, (y0 + y1) / 2, 2.4), (1, 0, 0), h=0.9)
    bd.flag_mast(k, root, (x0 - 0.65, y0 - 0.65, 0), 6.6, mat="iron_black", finial="brass")


def _l5(k, root, rnd):
    h = 3.8
    x0, x1, y0, y1 = _vault_body(k, root, rnd, h, "stone_pale", 0.4, (0.7, 1.2), 0.003, buttress=False)
    for (xa, ya) in ((x0, y0), (x1, y0), (x1, y1)):                 # gilded corner columns
        k.cylinder("column", 0.25, h, (xa + (0.25 if xa > 0 else -0.25), ya + (0.25 if ya > 0 else -0.25), 0),
                   "stone_pale", segs=20, parent=root, bevel=0.01)
        for z in (0.0, h - 0.18):
            k.box("column_gold", (0.6, 0.6, 0.18), (xa + (0.25 if xa > 0 else -0.25),
                                                     ya + (0.25 if ya > 0 else -0.25), z + 0.09), "gold_trim",
                  parent=root, bevel=0.01)
    k.box("cornice", (x1 - x0 + 0.8, y1 - y0 + 0.8, 0.3), ((x0 + x1) / 2, (y0 + y1) / 2, h + 0.15), "stone_pale",
          parent=root, bevel=0.03)
    k.box("cornice_gold", (x1 - x0 + 0.84, y1 - y0 + 0.84, 0.07), ((x0 + x1) / 2, (y0 + y1) / 2, h + 0.04),
          "gold_trim", parent=root, bevel=0.005)
    c = Vector(((x0 + x1) / 2, (y0 + y1) / 2, h + 0.3))
    k.cylinder("drum", 1.5, 0.6, c, "stone_pale", segs=48, parent=root, bevel=0.02)
    dome = [(0, 1.5), (0.4, 1.4), (0.8, 1.12), (1.05, 0.75), (1.22, 0.35), (1.28, 0.0)]
    k.lathe("dome", dome, "gold_trim", segs=48, loc=c + Vector((0, 0, 0.6)), rot=(math.pi / 2, 0, 0), parent=root)
    for i in range(12):
        a = 2 * math.pi * i / 12
        pts = [c + Vector((r * math.cos(a), r * math.sin(a), 0.6 + y)) for y, r in dome]
        k.hose("dome_rib", pts, 0.03, "bronze_old", parent=root)
    k.lathe("lantern", [(0, 0.0), (0.0, 0.22), (0.35, 0.18), (0.5, 0.05), (0.7, 0.0)], "gold_trim", segs=20,
            loc=c + Vector((0, 0, 1.85)), rot=(math.pi / 2, 0, 0), parent=root)
    _vault_door(k, root, (x0 + DOOR_S, y0 - 0.55, 1.3), (0, -1, 0), 1.05, mat="steel_worn", wheel="gold_trim",
                open_=0.8)
    defender.emblem(k, root, (x0 + DOOR_S, y0 - 0.48, 3.1), (0, -1, 0), h=0.8)
    defender.emblem(k, root, (x1 + 0.5, (y0 + y1) / 2, 2.4), (1, 0, 0), h=1.0)
    # screw coin press with a weighted balance arm (L5 mechanism)
    p = Vector((3.1, -1.4, 0))
    k.box("press_base", (1.0, 0.8, 0.4), p + Vector((0, 0, 0.2)), "stone_pale", parent=root, bevel=0.02)
    for sx in (-1, 1):
        k.box("press_cheek", (0.16, 0.35, 1.5), p + Vector((sx * 0.35, 0, 1.15)), "bronze_old", parent=root,
              bevel=0.02)
    k.box("press_head", (0.95, 0.4, 0.3), p + Vector((0, 0, 2.0)), "bronze_old", parent=root, bevel=0.02)
    k.tube("press_screw", p + Vector((0, 0, 1.1)), p + Vector((0, 0, 2.5)), 0.07, "steel_worn", parent=root, segs=14)
    for i in range(8):
        k.torus("screw_thread", 0.075, 0.012, p + Vector((0, 0, 1.25 + i * 0.1)), "steel_worn", parent=root, segs=16,
                tube_segs=4)
    arm = p + Vector((0, 0, 2.45))
    k.tube("press_arm", arm + Vector((-1.2, -0.25, 0)), arm + Vector((1.2, 0.25, 0)), 0.04, "iron_black", parent=root,
           segs=10)
    for sx in (-1, 1):
        k.lathe("arm_ball", [(-0.16, 0.0)] + [(-0.16 * math.cos(math.pi * i / 8), 0.16 * math.sin(math.pi * i / 8))
                                               for i in range(1, 8)] + [(0.16, 0.0)], "gold_trim", segs=16,
                loc=arm + Vector((sx * 1.3, sx * 0.27, 0)), parent=root)
    k.cylinder("die", 0.1, 0.12, p + Vector((0, 0, 0.98)), "steel_worn", segs=16, parent=root, bevel=False)
    k.cylinder("anvil_die", 0.14, 0.2, p + Vector((0, 0, 0.4)), "steel_worn", segs=16, parent=root, bevel=False)
    bd.flag_mast(k, root, (x0 - 0.75, y0 - 0.75, 0), 7.0, mat="iron_black", finial="gold_trim")
