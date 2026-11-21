"""Muster hall of the player's base (bg: „Военно свикване“), 2 x 2 tiles (8 x 8 m), 5 levels.

Where the defenders call up troops and set out on missions (in the game: the
strategic-point levels of „Път“ and the campaigns of „Дъга“). The silhouette
stays: a long low hall with a tall horn post at its front-right corner carrying
a big signal horn, the building's mark (the user asked for a military horn so
the player knows what the building is for). The horn grows from an ox horn to a
crown of gilded fanfares. Each level changes the building's own material and
adds one new kind of muster mechanism:

  L1  canvas recruiting tent on raw poles, trestle desk with a ledger;
      field drum on a stand; ox horn with brass mounts on a pole        (canvas, raw timber)
  L2  tarred plank barrack on a rubble plinth, shingle roof; brass bugle;
      counterweighted gate boom in front of the door                     (tarred timber, iron)
  L3  rubble-stone drill hall, slate roof; timber lookout tower with
      a ladder carries a long brass herald horn; parade flagpoles        (stone, slate, brass)
  L4  dressed stone with riveted black iron; the horn becomes a steam
      siren fed from a riveted boiler with a gauge and a pull chain      (ashlar, black iron)
  L5  pale stone with gold trim; a stone tower with a crown of four
      gilded fanfare horns hung with blue banners, fed by bellows and
      an air chest                                                       (pale stone, gold)

A pile of kit by the door grows with the level (bedrolls, packs, rifles in a stack).
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
NAMES = {"bg": "Военно свикване", "en": "Muster hall"}

HORN = Vector((2.75, 0.6, 0))          # horn post: on the +X side, clear of the door face


def build(style, level=1):
    k = Kit(style)
    root = k.empty("muster")
    mp.set_reference(root)
    rnd = bd.rnd_for(600 + level)
    {1: _l1, 2: _l2, 3: _l3, 4: _l4, 5: _l5}[level](k, root, rnd)
    return root, root


def ground(level):
    from ..terrain import Patch
    return Patch(r_solid=4.3, r_out=5.2, r_bare=4.0, seed=61 + level, ragged=0.5)


# ---------------------------------------------------------------------------
def along(k, name, profile, mat, p0, direction, parent, segs=28):
    """Lathe a (y, r) profile from p0 along `direction` (any 3D vector)."""
    d = Vector(direction).normalized()
    rot = d.to_track_quat("Y", "Z").to_euler()
    return k.lathe(name, profile, mat, segs=segs, loc=Vector(p0), rot=rot, parent=parent)


def horn_bell(length, r0, r1, flare=4, steps=10):
    """Profile of a horn: narrow mouthpiece, conical body, flared bell."""
    prof = []
    for i in range(steps + 1):
        t = i / steps
        r = r0 + (r1 - r0) * t ** flare
        prof.append((t * length, r))
    inner = [(length - 0.01, r1 * 0.82), (length * 0.8, r1 * 0.2)]
    return prof + inner


def ox_horn(k, root, base, length, mat="timber_honey", mount="brass"):
    """A curved horn built from short tapering segments, brass mouthpiece and rim."""
    pts = []
    for i in range(9):
        t = i / 8
        a = t * 1.3
        pts.append(base + Vector((math.sin(a) * length * 0.55, -0.15 * t, math.cos(a) * length * 0.25 - length * 0.25)))
    for i in range(8):
        r0 = 0.04 + 0.2 * (i / 8) ** 1.6
        r1 = 0.04 + 0.2 * ((i + 1) / 8) ** 1.6
        k.tube("horn", pts[i], pts[i + 1], r0, mat, radius_end=r1, segs=16, parent=root, bevel=False)
    k.torus("horn_rim", 0.245, 0.025, pts[-1], mount, rot=(Vector(pts[-1] - pts[-2]).to_track_quat("Z", "Y").to_euler()),
            parent=root, segs=24, tube_segs=6)
    for i in (2, 5):
        r = 0.04 + 0.2 * (i / 8) ** 1.6 + 0.01
        k.torus("horn_band", r, 0.012, pts[i], mount, rot=(Vector(pts[i + 1] - pts[i]).to_track_quat("Z", "Y").to_euler()),
                parent=root, segs=20, tube_segs=4)
    return pts


def kit_pile(k, root, level, rnd):
    """Recruits' kit by the door: bedrolls, packs, a rifle stack from L3."""
    base = Vector((-2.3, -3.25, 0))
    roll = {1: "canvas", 2: "burlap", 3: "canvas", 4: "webbing", 5: "webbing_pale"}[level]
    for i in range(1 + min(level, 3)):
        p = base + Vector((0.55 * i - 0.3, 0.1 * (i % 2), 0.16))
        k.tube("bedroll", p + Vector((-0.28, 0, 0)), p + Vector((0.28, 0, 0)), 0.15, roll, segs=16, parent=root)
        for dx in (-0.15, 0.15):
            k.torus("roll_strap", 0.155, 0.012, p + Vector((dx, 0, 0)), "leather", rot=(0, math.pi / 2, 0),
                    parent=root, segs=20, tube_segs=4)
    if level >= 2:
        for i in range(level - 1):
            bd.crate(k, root, base + Vector((-0.9, 0.5 + 0.0 * i, 0.22 + 0.44 * i)), (0.55, 0.45, 0.44),
                     0.15 * i, mat="paint_crate" if level < 4 else "paint_olive")
    if level >= 3:                                            # rifles stacked in a tripod
        c = base + Vector((1.9, -0.2, 0))
        for i in range(3):
            a = 2 * math.pi * i / 3 + 0.3
            foot = c + Vector((math.cos(a) * 0.35, math.sin(a) * 0.35, 0))
            top = c + Vector((0, 0, 1.15))
            k.tube("rifle_stock", foot, foot.lerp(top, 0.35), 0.03, "timber_oak", parent=root, segs=8)
            k.tube("rifle_barrel", foot.lerp(top, 0.35), top + (top - foot) * 0.08, 0.012, "gunmetal", parent=root,
                   segs=8)


# ---------------------------------------------------------------------------
def _l1(k, root, rnd):
    # canvas tent: ridge pole on two uprights, sloping canvas, open front with a desk
    x0, x1, y0, y1 = -2.6, 1.6, -1.6, 1.8
    h, ridge = 1.4, 2.6
    for x in (x0, x1):
        k.tube("tent_pole", (x, (y0 + y1) / 2, 0), (x, (y0 + y1) / 2, ridge + 0.1), 0.06, "timber_raw", parent=root,
               segs=10)
    k.tube("ridge_pole", (x0 - 0.15, (y0 + y1) / 2, ridge), (x1 + 0.15, (y0 + y1) / 2, ridge), 0.055,
           "timber_raw", parent=root, segs=10)
    yc = (y0 + y1) / 2
    for side, ye in ((-1, y0), (1, y1)):
        k.mesh  # (keep linters quiet)
        v = [(x0, ye, h), (x1, ye, h), (x1, yc, ridge), (x0, yc, ridge)]
        obj = k.mesh("tent_roof", v, [(0, 1, 2, 3) if side < 0 else (3, 2, 1, 0)])
        s = obj.modifiers.new("Thick", "SOLIDIFY")
        s.thickness = 0.02
        k._finish(obj, "canvas", bevel=False, parent=root)
        k.box("tent_wall", (x1 - x0, 0.02, h), ((x0 + x1) / 2, ye, h / 2), "canvas", parent=root, bevel=False) \
            if side > 0 else None
    k.prism("tent_end", [(y0, 0), (y1, 0), (y1, h), (yc, ridge), (y0, h)], 0.02, "canvas", y=0, parent=root)
    for o in [o for o in root.children if o.name.startswith("tent_end")]:
        o.rotation_euler = (0, 0, math.pi / 2)
        o.location = (x0, 0, 0)
    k.prism("tent_end", [(y0, 0), (y1, 0), (y1, h), (yc, ridge), (y0, h)], 0.02, "canvas", y=0, parent=root)
    last = [o for o in root.children if o.name.startswith("tent_end")][-1]
    last.rotation_euler = (0, 0, math.pi / 2)
    last.location = (x1, 0, 0)
    # front: canvas flap rolled up on the -Y side, posts and guy ropes
    k.tube("flap_roll", (x0 + 0.2, y0 - 0.04, h - 0.1), (x1 - 0.2, y0 - 0.04, h - 0.1), 0.09, "canvas", parent=root,
           segs=14)
    for x in (x0, (x0 + x1) / 2, x1):
        k.tube("front_pole", (x, y0, 0), (x, y0, h), 0.045, "timber_raw", parent=root, segs=8)
        peg = Vector((x, y0 - 1.0, 0))
        k.hose("guy", [Vector((x, y0, h)), Vector((x, y0 - 0.5, h * 0.5)), peg], 0.008, "rope", parent=root)
        k.cylinder("peg", 0.03, 0.18, peg - Vector((0, 0, 0.05)), "timber_raw", segs=6, parent=root, bevel=False)
    k.box("tent_floor", (x1 - x0, y1 - y0, 0.03), ((x0 + x1) / 2, yc, 0.015), "burlap", parent=root, bevel=False)
    # trestle desk with a ledger and an inkwell
    d = Vector((-0.6, y0 - 0.55, 0))
    k.box("desk_top", (1.6, 0.6, 0.05), d + Vector((0, 0, 0.78)), "timber_raw", parent=root, bevel=0.01)
    for sx in (-1, 1):
        for sy in (-1, 1):
            k.beam("trestle", d + Vector((sx * 0.65, sy * 0.25, 0)), d + Vector((sx * 0.6, 0, 0.76)), (0.05, 0.05),
                   "timber_raw", parent=root)
    k.box("ledger", (0.42, 0.3, 0.05), d + Vector((-0.2, 0, 0.83)), "leather", rot=(0, 0, 0.15), parent=root,
          bevel=0.006)
    k.box("ledger_page", (0.4, 0.28, 0.01), d + Vector((-0.2, 0, 0.86)), "canvas", rot=(0, 0, 0.15), parent=root,
          bevel=False)
    k.box("stool", (0.35, 0.35, 0.45), d + Vector((0.2, 0.55, 0.22)), "timber_raw", parent=root, bevel=0.01)
    # field drum on a stand (L1 mechanism): shell, hoops, tension cords, sticks
    dr = Vector((1.2, y0 - 0.9, 0))
    for i in range(3):
        a = 2 * math.pi * i / 3
        k.beam("drum_leg", dr + Vector((math.cos(a) * 0.32, math.sin(a) * 0.32, 0)), dr + Vector((0, 0, 0.62)),
               (0.035, 0.035), "timber_raw", parent=root)
    k.cylinder("drum_shell", 0.3, 0.42, dr + Vector((0, 0, 0.6)), "paint_blue", segs=28, parent=root, bevel=0.01)
    for z in (0.6, 1.0):
        k.torus("drum_hoop", 0.31, 0.025, dr + Vector((0, 0, z)), "timber_red", parent=root, segs=28, tube_segs=6)
    for i in range(10):
        a = 2 * math.pi * i / 10
        k.tube("drum_cord", dr + Vector((math.cos(a) * 0.31, math.sin(a) * 0.31, 0.62)),
               dr + Vector((math.cos(a + 0.3) * 0.31, math.sin(a + 0.3) * 0.31, 0.98)), 0.007, "rope", parent=root,
               segs=4, bevel=False)
    for sx in (-1, 1):
        k.tube("drum_stick", dr + Vector((sx * 0.08, -0.1, 1.03)), dr + Vector((sx * 0.25, -0.3, 1.08)), 0.012,
               "timber_honey", parent=root, segs=6, bevel=False)
    # horn post with an ox horn and a small blue pennant
    p = HORN
    k.tube("horn_post", p, p + Vector((0, 0, 3.6)), 0.08, "timber_raw", radius_end=0.06, parent=root, segs=10)
    k.beam("horn_arm", p + Vector((0, 0, 3.3)), p + Vector((-0.1, -0.9, 3.3)), (0.08, 0.08), "timber_raw",
           parent=root)
    k.beam("horn_brace", p + Vector((0, 0, 2.7)), p + Vector((-0.07, -0.6, 3.3)), (0.05, 0.05), "timber_raw",
           parent=root)
    for dy in (-0.3, -0.85):
        k.hose("horn_cord", [p + Vector((-0.1, dy, 3.28)), p + Vector((-0.1 + (0.9 if dy < -0.5 else 0.25), dy, 3.0))],
               0.012, "rope", parent=root)
    ox_horn(k, root, p + Vector((-0.9, -0.85, 2.95)), 2.2)
    k.flag("pennant", 0.8, 0.35, p + Vector((0.04, 0, 3.4)), "paint_blue", parent=root, waves=2, amp=0.05)
    kit_pile(k, root, 1, rnd)


def _bugle(k, root, base, d, length, r1, mat="brass"):
    along(k, "bugle", horn_bell(length, 0.025, r1, flare=5), mat, base, d, root)
    # one wrap of tubing like a real bugle (loop beside the bell)
    side = Vector(d).cross(Vector((0, 0, 1))).normalized()
    a = Vector(base) + Vector(d).normalized() * length * 0.25
    b = Vector(base) + Vector(d).normalized() * length * 0.7
    k.hose("bugle_loop", [a, a + side * 0.12 - Vector((0, 0, 0.12)), b + side * 0.12 - Vector((0, 0, 0.12)), b],
           0.035, mat, parent=root)
    k.hose("bugle_cord", [a, a.lerp(b, 0.5) - Vector((0, 0, 0.5)), b], 0.02, "paint_blue", parent=root)


def _l2(k, root, rnd):
    x0, x1, y0, y1 = -3.0, 2.0, -2.0, 2.0
    plinth, wall_h = 0.45, 2.4
    door_s = (2.0, 2.9, 0, 2.4)
    for p0, p1 in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        bd.masonry(k, root, p0, p1, 0, plinth, 0.55, rnd, mat="stone", course=0.22, unit=(0.3, 0.6), rough=0.05,
                   skip=((2.0, 2.9, 0.0, 1.0),) if p0 == (x0, y0) else ())
    z = plinth
    k.box("core", (x1 - x0 - 0.2, y1 - y0 - 0.2, wall_h), ((x0 + x1) / 2, 0, z + wall_h / 2), "timber_tarred",
          parent=root, bevel=False)
    wf = ((0.7, 1.5, 0.8, 1.8), (3.6, 4.4, 0.8, 1.8))
    ws = ((1.4, 2.4, 0.8, 1.8),)
    bd.planks(k, root, (x0, y0 - 0.02), (x1, y0 - 0.02), z, wall_h, 0.06, rnd, skip=(door_s,) + wf)
    bd.planks(k, root, (x1 + 0.02, y0), (x1 + 0.02, y1), z, wall_h, 0.06, rnd, skip=ws)
    bd.planks(k, root, (x1, y1 + 0.02), (x0, y1 + 0.02), z, wall_h, 0.06, rnd)
    bd.planks(k, root, (x0 - 0.02, y1), (x0 - 0.02, y0), z, wall_h, 0.06, rnd)
    for (xa, ya) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        k.box("corner_post", (0.2, 0.2, wall_h + 0.05), (xa, ya, z + wall_h / 2), "timber_tarred", parent=root,
              bevel=0.015)
    for s in (1.1, 4.0):
        bd.window(k, root, (x0 + s, y0 - 0.08, z + 1.3), bd.FRONT, 0.7, 0.9, shutters="paint_blue")
    bd.window(k, root, (x1 + 0.08, y0 + 1.9, z + 1.3), bd.SIDE, 0.7, 0.9, shutters="paint_blue")
    bd.door(k, root, (x0 + 2.45, y0 - 0.1, 0.45), bd.FRONT, 0.9, 2.0, mat="timber_tarred")
    for i in range(2):
        k.box("step", (1.2, 0.3, 0.22), (x0 + 2.45, y0 - 0.35 - 0.3 * i, 0.45 - 0.22 * (i + 1) + 0.11), "stone",
              parent=root, bevel=0.02)
    rz = bd.gable_roof(k, root, x0, x1, y0, y1, z + wall_h, 1.2, rnd, "timber_tarred", unit=(0.26, 0.24), over=0.4,
                       along="x")
    bd.gable_ends(k, root, x0 - 0.04, x1 + 0.04, y0, y1, z + wall_h, rz - 0.04, "timber_tarred", along="x")
    defender.emblem(k, root, (x1 + 0.12, 0.0, z + wall_h + 0.55), (1, 0, 0), h=0.65)
    # notice board with posters beside the door
    nb = Vector((x0 + 3.6, y0 - 0.35, 0))
    for sx in (-1, 1):
        k.tube("board_post", nb + Vector((sx * 0.45, 0, 0)), nb + Vector((sx * 0.45, 0, 1.8)), 0.04, "timber_tarred",
               parent=root, segs=8)
    k.box("board", (1.0, 0.04, 0.7), nb + Vector((0, 0, 1.35)), "timber_tarred", parent=root, bevel=0.01)
    for i, (dx, dz) in enumerate(((-0.25, 1.4), (0.2, 1.45), (0.0, 1.18))):
        k.box("poster", (0.3, 0.01, 0.38), nb + Vector((dx, -0.03, dz)), "canvas" if i != 1 else "paint_white",
              rot=(0, rnd.uniform(-0.08, 0.08), 0), parent=root, bevel=False)
    k.box("board_roof", (1.2, 0.3, 0.04), nb + Vector((0, 0, 1.78)), "timber_tarred", rot=(0.25, 0, 0), parent=root,
          bevel=0.01)
    # counterweighted gate boom in front of the door (L2 mechanism)
    g = Vector((x0 + 0.9, y0 - 1.55, 0))
    for sy in (-1, 1):
        k.box("boom_post", (0.16, 0.08, 1.15), g + Vector((0, sy * 0.1, 0.575)), "timber_tarred", parent=root,
              bevel=0.01)
    k.cylinder("boom_pin", 0.04, 0.3, g + Vector((0, -0.15, 1.0)), "iron_forged", segs=10, rot=(math.pi / 2, 0, 0),
               parent=root, bevel=False)
    tip = g + Vector((3.6, 0, 1.02))
    k.beam("boom", g + Vector((-0.7, 0, 1.0)), tip, (0.1, 0.1), "paint_white", section_end=(0.07, 0.07),
           parent=root)
    for i in range(5):
        a = g + Vector((0.4 + 0.65 * i, 0, 1.0)).lerp(tip, 0) if False else g + Vector((0.4 + 0.65 * i, 0, 1.007))
        k.box("boom_band", (0.3, 0.105, 0.105), a, "paint_red", parent=root, bevel=False)
    k.box("counterweight", (0.4, 0.3, 0.35), g + Vector((-0.65, 0, 0.9)), "stone", parent=root, bevel=0.03)
    k.box("cw_strap", (0.42, 0.32, 0.05), g + Vector((-0.65, 0, 0.9)), "iron_forged", parent=root, bevel=False)
    k.box("boom_rest", (0.1, 0.1, 1.0), tip + Vector((-0.05, 0, -0.5)), "timber_tarred", parent=root, bevel=0.01)
    # horn post: a brass bugle on a bracket, blue pennant
    p = HORN + Vector((0.1, 0.0, 0))
    k.tube("horn_post", p, p + Vector((0, 0, 4.4)), 0.09, "timber_tarred", radius_end=0.07, parent=root, segs=12)
    k.beam("horn_bracket", p + Vector((0, 0, 3.55)), p + Vector((-0.4, -0.9, 3.55)), (0.08, 0.08), "iron_forged",
           parent=root)
    k.beam("horn_brace", p + Vector((0, 0, 3.0)), p + Vector((-0.3, -0.65, 3.55)), (0.05, 0.05), "iron_forged",
           parent=root)
    _bugle(k, root, p + Vector((0.3, 0.2, 3.7)), (-0.45, -1.0, 0.0), 2.4, 0.38)
    k.flag("pennant", 1.0, 0.45, p + Vector((0.05, 0, 4.15)), "paint_blue", parent=root, waves=2, amp=0.06)
    kit_pile(k, root, 2, rnd)


def _l3(k, root, rnd):
    x0, x1, y0, y1 = -3.2, 1.6, -2.3, 2.3
    h = 3.4
    from .hq import _keep
    _keep(k, root, rnd, x0, x1, y0, y1, h, "stone", 0.3, (0.35, 0.8), 0.05, 2.6,
          ((1.0, 0.9), (4.1, 0.9)), ((1.3, 0.9), (3.4, 0.9)))
    bd.door(k, root, (x0 + 2.6, y0 - 0.25, 0.0), bd.FRONT, 1.4, 2.3, mat="timber_oak")
    rz = bd.gable_roof(k, root, x0, x1, y0, y1, h, 1.5, rnd, "slate", unit=(0.3, 0.2), over=0.35, thick=0.025,
                       ridge_mat="iron_forged", along="x")
    bd.gable_ends(k, root, x0 + 0.05, x1 - 0.05, y0 + 0.05, y1 - 0.05, h, rz - 0.1, "stone", t=0.5, along="x")
    defender.emblem(k, root, (x0 + 2.6, y0 - 0.32, 2.75), (0, -1, 0), h=0.8)
    # parade flagpoles along the front (L3 mechanism: halyards and cleats)
    for i, x in enumerate((x0 + 0.6, x0 + 4.4)):
        b = Vector((x, y0 - 1.0, 0))
        k.cylinder("flag_foot", 0.2, 0.3, b, "stone", segs=16, parent=root, bevel=0.02)
        bd.flag_mast(k, root, b + Vector((0, 0, 0.3)), 4.6, mat="timber_oak", flag="paint_blue", w=0.9, finial="brass")
        k.box("cleat", (0.04, 0.12, 0.05), b + Vector((0.07, 0, 1.4)), "brass", parent=root, bevel=False)
    # lookout tower carrying the herald horn
    t = Vector((2.9, 1.2, 0))
    s, top = 0.75, 5.2
    for sx in (-1, 1):
        for sy in (-1, 1):
            k.beam("tower_leg", t + Vector((sx * s, sy * s, 0)), t + Vector((sx * s * 0.6, sy * s * 0.6, top)),
                   (0.16, 0.16), "timber_oak", parent=root)
            k.box("tower_foot", (0.4, 0.4, 0.25), t + Vector((sx * s, sy * s, 0.12)), "stone", parent=root, bevel=0.02)
    for z0, z1 in ((0.3, 2.6), (2.6, 4.9)):
        f0, f1 = 1 - 0.4 * z0 / top, 1 - 0.4 * z1 / top
        for a, b in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
            k.beam("tower_brace", t + Vector((a[0] * s * f0, a[1] * s * f0, z0)),
                   t + Vector((b[0] * s * f1, b[1] * s * f1, z1)), (0.07, 0.07), "timber_oak", parent=root)
    k.box("tower_deck", (1.4, 1.4, 0.1), t + Vector((0, 0, top)), "timber_oak", parent=root, bevel=0.01)
    for a, b in (((-1, -1), (1, -1)), ((1, -1), (1, 1))):
        k.beam("tower_rail", t + Vector((a[0] * 0.68, a[1] * 0.68, top + 0.9)),
               t + Vector((b[0] * 0.68, b[1] * 0.68, top + 0.9)), (0.06, 0.06), "timber_oak", parent=root)
    for sx in (-1, 1):
        for sy in (-1, 1):
            k.tube("rail_post", t + Vector((sx * 0.68, sy * 0.68, top)), t + Vector((sx * 0.68, sy * 0.68, top + 0.9)),
                   0.035, "timber_oak", parent=root, segs=8)
    for i in range(int(top / 0.35)):                          # ladder on the camera side
        z = 0.3 + i * 0.35
        k.tube("ladder_rung", t + Vector((-0.25, -s - 0.1 + 0.3 * z / top, z)),
               t + Vector((0.25, -s - 0.1 + 0.3 * z / top, z)), 0.02, "timber_raw", parent=root, segs=6, bevel=False)
    for sx in (-1, 1):
        k.beam("ladder_side", t + Vector((sx * 0.27, -s - 0.1, 0)), t + Vector((sx * 0.27, -s * 0.6 - 0.1, top)),
               (0.05, 0.05), "timber_raw", parent=root)
    # the long brass herald horn on a crutch, mouth toward the camera
    hb = t + Vector((0.2, 0.3, top + 1.05))
    k.beam("horn_crutch", t + Vector((0.2, 0.3, top)), hb, (0.06, 0.06), "iron_forged", parent=root)
    along(k, "herald_horn", horn_bell(3.0, 0.04, 0.5, flare=5, steps=14), "brass", hb + Vector((0.9, 0.9, 0.25)),
          (-0.6, -1.0, -0.2), root, segs=32)
    k.torus("horn_rim", 0.51, 0.025, hb + Vector((0.9, 0.9, 0.25)) + Vector((-0.6, -1.0, -0.2)).normalized() * 3.0,
            "brass", rot=Vector((-0.6, -1.0, -0.2)).to_track_quat("Z", "Y").to_euler(), parent=root, segs=32,
            tube_segs=6)
    k.flag("horn_banner", 0.7, 0.5, hb + Vector((0.1, 0.0, -0.15)), "paint_blue", parent=root, waves=1, amp=0.03)
    kit_pile(k, root, 3, rnd)


def _l4(k, root, rnd):
    x0, x1, y0, y1 = -3.3, 1.7, -2.5, 2.5
    h = 3.8
    from .hq import _keep
    _keep(k, root, rnd, x0, x1, y0, y1, h, "stone_dressed", 0.36, (0.6, 1.1), 0.006, 2.7,
          ((1.0, 1.0), (4.2, 1.0)), ((1.3, 1.0), (3.7, 1.0)))
    bd.door(k, root, (x0 + 2.7, y0 - 0.25, 0.0), bd.FRONT, 1.5, 2.4, mat="timber_oak", strap="iron_black")
    rz = bd.gable_roof(k, root, x0, x1, y0, y1, h, 1.5, rnd, "iron_black", unit=(0.5, 0.25), over=0.3, thick=0.02,
                       ridge_mat="iron_black", along="x", jitter=0.004)
    bd.gable_ends(k, root, x0 + 0.05, x1 - 0.05, y0 + 0.05, y1 - 0.05, h, rz - 0.1, "stone_dressed", t=0.5, along="x")
    for x in (x0 + 0.3, x1 - 0.3):                        # riveted iron pilasters on the front
        k.box("pilaster", (0.45, 0.08, h - 0.2), (x, y0 - 0.32, h / 2), "iron_black", parent=root, bevel=0.005)
        for z in [0.4 + 0.45 * i for i in range(7)]:
            for o in (-0.15, 0.15):
                k.cylinder("rivet", 0.025, 0.03, (x + o, y0 - 0.37, z), "iron_black", segs=8, rot=(math.pi / 2, 0, 0),
                           parent=root, bevel=False)
    defender.emblem(k, root, (x0 + 2.7, y0 - 0.32, 2.95), (0, -1, 0), h=0.9)
    defender.emblem(k, root, (x1 + 0.32, 0.0, 2.6), (1, 0, 0), h=0.9)
    # riveted iron tower with the steam siren (L4 mechanism: boiler, pipe, gauge, pull chain)
    t = Vector((2.9, 1.2, 0))
    s4, th = 0.7, 5.0
    for sx in (-1, 1):                                    # riveted iron lattice tower
        for sy in (-1, 1):
            k.beam("tower_leg", t + Vector((sx * s4, sy * s4, 0)), t + Vector((sx * 0.4, sy * 0.4, th)),
                   (0.12, 0.12), "iron_black", parent=root)
            k.box("tower_foot", (0.35, 0.35, 0.2), t + Vector((sx * s4, sy * s4, 0.1)), "stone_dressed",
                  parent=root, bevel=0.02)
    for z0, z1 in ((0.2, 1.8), (1.8, 3.4), (3.4, 4.9)):
        f0, f1 = s4 - (s4 - 0.4) * z0 / th, s4 - (s4 - 0.4) * z1 / th
        for a_, b_ in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
            for u, v in ((a_, b_), (b_, a_)):
                k.beam("tower_lattice", t + Vector((u[0] * f0, u[1] * f0, z0)), t + Vector((v[0] * f1, v[1] * f1, z1)),
                       (0.05, 0.05), "iron_black", parent=root)
        k.box("tower_ring", (2 * f1 + 0.1, 2 * f1 + 0.1, 0.08), t + Vector((0, 0, z1)), "iron_black", parent=root,
              bevel=0.005) if z1 > 4 else None
    k.box("tower_deck", (1.0, 1.0, 0.12), t + Vector((0, 0, th + 0.06)), "iron_black", parent=root, bevel=0.01)
    bo = Vector((2.75, -1.4, 0))
    k.cylinder("boiler", 0.42, 1.2, bo + Vector((0, 0, 0.15)), "iron_black", segs=28, parent=root, bevel=0.02)
    k.lathe("boiler_top", [(0, 0.42), (0.12, 0.38), (0.24, 0.22), (0.28, 0.0)], "iron_black", segs=28,
            loc=bo + Vector((0, 0, 1.35)), rot=(math.pi / 2, 0, 0), parent=root)
    for z in (0.4, 0.8, 1.2):
        k.torus("boiler_band", 0.43, 0.02, bo + Vector((0, 0, z)), "brass", parent=root, segs=28, tube_segs=4)
    k.box("firebox", (0.5, 0.15, 0.3), bo + Vector((0, -0.43, 0.4)), "iron_forged", parent=root, bevel=0.01)
    k.box("fire_glow", (0.34, 0.02, 0.15), bo + Vector((0, -0.51, 0.4)), "ember", parent=root, bevel=False)
    k.tube("boiler_stack", bo + Vector((0.15, 0.15, 1.5)), bo + Vector((0.15, 0.15, 2.6)), 0.08, "iron_black",
           parent=root, segs=14)
    g = bo + Vector((0.32, -0.3, 1.0))
    k.cylinder("gauge", 0.11, 0.05, g, "brass", segs=20, rot=(math.pi / 2, 0, -0.6), parent=root, bevel=False)
    k.cylinder("gauge_face", 0.09, 0.01, g + Vector((0.03, -0.04, 0)), "enamel_white", segs=20,
               rot=(math.pi / 2, 0, -0.6), parent=root, bevel=False)
    top = t + Vector((0, 0, th + 0.12))
    k.hose("steam_pipe", [bo + Vector((-0.15, 0.1, 1.55)), bo + Vector((0.0, 1.2, 1.9)), t + Vector((0.1, -0.2, 2.0)),
                          t + Vector((0.05, 0, 4.0)), top + Vector((0, 0, 0.6))], 0.06, "copper", parent=root)
    k.cylinder("siren_valve", 0.12, 0.3, top + Vector((0, 0, 0.6)), "brass", segs=16, parent=root, bevel=0.01)
    along(k, "siren_horn", horn_bell(2.6, 0.08, 0.6, flare=3, steps=14), "brass", top + Vector((0.4, 0.6, 0.9)),
          (-0.55, -1.0, 0.0), root, segs=32)
    k.torus("siren_rim", 0.6, 0.03, top + Vector((0.4, 0.6, 0.9)) + Vector((-0.55, -1.0, 0)).normalized() * 2.6,
            "brass", rot=Vector((-0.55, -1.0, 0)).to_track_quat("Z", "Y").to_euler(), parent=root, segs=32,
            tube_segs=6)
    k.beam("valve_lever", top + Vector((0, 0, 0.85)), top + Vector((0.0, -0.7, 0.8)), (0.04, 0.04), "iron_forged",
           parent=root)
    k.hose("pull_chain", [top + Vector((0.0, -0.7, 0.8)), t + Vector((0.0, -0.85, 3.0)), t + Vector((0.0, -0.85, 1.2))],
           0.012, "steel_cable", parent=root)
    k.torus("chain_ring", 0.07, 0.012, t + Vector((0.0, -0.85, 1.1)), "brass", rot=(math.pi / 2, 0, 0), parent=root,
            segs=16, tube_segs=4)
    bd.flag_mast(k, root, (x0 - 0.45, y0 - 0.45, 0), 6.4, mat="iron_black", finial="brass")
    kit_pile(k, root, 4, rnd)


def _l5(k, root, rnd):
    x0, x1, y0, y1 = -3.3, 1.6, -2.6, 2.6
    h = 4.2
    from .hq import _keep
    _keep(k, root, rnd, x0, x1, y0, y1, h, "stone_pale", 0.4, (0.7, 1.2), 0.003, 2.7,
          ((1.0, 1.1), (4.3, 1.1)), ((1.3, 1.1), (3.9, 1.1)))
    bd.door(k, root, (x0 + 2.7, y0 - 0.25, 0.0), bd.FRONT, 1.5, 2.5, mat="timber_oak", strap="gold_trim")
    for sx in (-1, 1):
        k.cylinder("column", 0.16, 2.9, (x0 + 2.7 + sx * 1.1, y0 - 0.45, 0.0), "stone_pale", segs=20, parent=root)
        k.box("column_cap", (0.42, 0.42, 0.14), (x0 + 2.7 + sx * 1.1, y0 - 0.45, 2.95), "gold_trim", parent=root,
              bevel=0.01)
    k.box("gate_lintel", (2.7, 0.5, 0.35), (x0 + 2.7, y0 - 0.4, 3.2), "stone_pale", parent=root, bevel=0.03)
    rz = bd.gable_roof(k, root, x0, x1, y0, y1, h, 1.3, rnd, "slate", unit=(0.3, 0.2), over=0.3, thick=0.025,
                       ridge_mat="gold_trim", along="x")
    bd.gable_ends(k, root, x0 + 0.05, x1 - 0.05, y0 + 0.05, y1 - 0.05, h, rz - 0.1, "stone_pale", t=0.5, along="x")
    k.box("cornice_gold", (x1 - x0 + 0.1, y1 - y0 + 0.1, 0.07), ((x0 + x1) / 2, 0, h - 0.05), "gold_trim",
          parent=root, bevel=0.005)
    defender.emblem(k, root, (x0 + 2.7, y0 - 0.66, 3.75), (0, -1, 0), h=1.1)
    defender.emblem(k, root, (x1 + 0.32, 0.0, 2.8), (1, 0, 0), h=1.1)
    # round stone horn tower with a gilded crown of four fanfares (L5 mechanism: bellows and air chest)
    t = Vector((2.85, 1.1, 0))
    th = 5.6
    bd.masonry  # (tower is coursed ring masonry, built as stacked drums)
    for i in range(int(th / 0.4)):
        k.cylinder("tower_course", 0.95 - 0.005 * i, 0.39, t + Vector((0, 0, i * 0.4)), "stone_pale", segs=32,
                   parent=root, bevel=0.015)
    for z, w in ((1.2, 0.5), (3.2, 0.5)):
        k.box("tower_slit", (0.12, 0.05, w), t + Vector((0, -0.93, z)), "iron_black", parent=root, bevel=False)
    k.cylinder("tower_cornice", 1.12, 0.2, t + Vector((0, 0, th)), "stone_pale", segs=32, parent=root, bevel=0.02)
    k.torus("tower_gold", 1.12, 0.03, t + Vector((0, 0, th + 0.1)), "gold_trim", parent=root, segs=32, tube_segs=6)
    c = t + Vector((0, 0, th + 0.2))
    k.cylinder("air_chest", 0.45, 0.55, c, "brass", segs=24, parent=root, bevel=0.01)
    k.lathe("chest_cap", [(0, 0.45), (0.12, 0.38), (0.25, 0.18), (0.4, 0.04), (0.55, 0.0)], "gold_trim", segs=24,
            loc=c + Vector((0, 0, 0.55)), rot=(math.pi / 2, 0, 0), parent=root)
    for i in range(4):
        a = math.radians(-135 + 90 * i)                   # one fanfare pointing at the camera
        d = Vector((math.cos(a), math.sin(a), 0.18)).normalized()
        b = c + Vector((0, 0, 0.3)) + Vector((d.x, d.y, 0)) * 0.35
        along(k, "fanfare", horn_bell(2.3, 0.06, 0.38, flare=5, steps=14), "gold_trim", b, d, root, segs=28)
        k.torus("fanfare_rim", 0.38, 0.025, b + d * 2.3, "gold_trim", rot=d.to_track_quat("Z", "Y").to_euler(),
                parent=root, segs=28, tube_segs=6)
        bf = b + d * 0.9 - Vector((0, 0, 0.07))
        side = d.cross(Vector((0, 0, 1))).normalized()
        v = [bf - side * 0.0, bf + d * 0.8, bf + d * 0.8 - Vector((0, 0, 0.95)), bf + d * 0.4 - Vector((0, 0, 1.2)),
             bf - Vector((0, 0, 0.95))]
        obj = k.mesh("fanfare_banner", [tuple(p) for p in v], [(0, 1, 2, 3, 4)])
        s = obj.modifiers.new("Thick", "SOLIDIFY")
        s.thickness = 0.015
        k._finish(obj, "paint_blue", bevel=False, parent=root)
        k.hose("banner_fringe", [v[2] + Vector((0, 0, -0.01)), v[3] + Vector((0, 0, -0.01)),
                                 v[4] + Vector((0, 0, -0.01))], 0.012, "gold_trim", parent=root)
    # bellows on the roof feeding the chest by a copper pipe
    bl = Vector((0.9, -0.8, rz - 0.55))
    k.box("bellows_board", (0.9, 0.6, 0.05), bl + Vector((0, 0, 0.0)), "timber_oak", rot=(0, 0.1, 0), parent=root,
          bevel=0.01)
    k.box("bellows_leather", (0.8, 0.55, 0.3), bl + Vector((0, 0, 0.17)), "leather", rot=(0, 0.05, 0), parent=root,
          bevel=0.05)
    k.box("bellows_top", (0.9, 0.6, 0.05), bl + Vector((0, 0, 0.35)), "timber_oak", parent=root, bevel=0.01)
    k.hose("air_pipe", [bl + Vector((0.45, 0, 0.2)), bl + Vector((1.3, -0.3, 0.8)), c + Vector((-0.6, 0.3, -0.6)),
                        c + Vector((-0.4, 0.2, 0.2))], 0.05, "copper", parent=root)
    bd.flag_mast(k, root, (x0 - 0.45, y0 - 0.45, 0), 7.2, mat="iron_black", finial="gold_trim")
    kit_pile(k, root, 5, rnd)
