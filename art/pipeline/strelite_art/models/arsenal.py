"""Arsenal of the player's base (bg: „Арсенал“), 2 x 2 tiles (8 x 8 m), 5 levels.

Where the unlocked guns are kept and issued (in the game: gun stats and „Построй“).
The silhouette stays: a broad, low gun shed with a wide double gate on the camera
side (-Y) and a lifting rig over the yard in front of it, with a gun barrel or a
round on its hook, so it never reads as the headquarters (a house with a flag) or
the laboratory (a workshop with a chimney). Each level changes the shed's own
material and adds one new kind of lifting or handling mechanism:

  L1  open raw-timber shed on posts, thatch of planks; a rack of spears and
      bolts; a windlass on a timber gallows lifts a crate              (raw timber, rope)
  L2  tarred plank shed on a rubble plinth, double doors with iron straps;
      a slewing jib crane with block and tackle                         (tarred timber, iron)
  L3  rubble-stone shed with an arched gate, slate roof; a narrow-gauge
      rail out of the gate with a flat car carrying a gun barrel         (stone, slate, iron)
  L4  dressed stone, black iron sliding doors on a top rail, riveted
      iron roof; an overhead gantry crane on two portal legs              (ashlar, black iron)
  L5  pale stone with a bronze gate and gold trim; a hydraulic
      accumulator tower with brass ram and gauges drives the crane       (pale stone, bronze, gold)

A pile of munitions by the gate changes per level: spear bundle, crates,
a pyramid of cast balls, shells in a rack, polished brass shells.
Front faces: -Y (screen lower left, the gate) and +X (screen lower right).
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
NAMES = {"bg": "Арсенал", "en": "Arsenal"}

X0, X1, Y0, Y1 = -3.4, 2.3, -1.2, 2.9        # shed plan; the yard is the strip in front (-Y)
GATE_S, GATE_W = 2.7, 2.4                    # gate centre along the front wall, gate width


def build(style, level=1):
    k = Kit(style)
    root = k.empty("arsenal")
    mp.set_reference(root)
    rnd = bd.rnd_for(700 + level)
    {1: _l1, 2: _l2, 3: _l3, 4: _l4, 5: _l5}[level](k, root, rnd)
    _munitions(k, root, level, rnd)
    return root, root


def ground(level):
    from ..terrain import Patch
    return Patch(r_solid=4.3, r_out=5.2, r_bare=4.0, seed=71 + level, ragged=0.5)


# ---------------------------------------------------------------------------
def _ball(k, root, c, r, mat):
    k.lathe("ball", [(-r, 0.0)] + [(-r * math.cos(a), r * math.sin(a)) for a in
                                    [math.pi * i / 10 for i in range(1, 10)]] + [(r, 0.0)],
            mat, segs=16, loc=c, parent=root)


def _shell(k, root, base, d, length, r, body, band="copper", tip=None):
    d = Vector(d).normalized()
    prof = [(0, r * 0.95), (0.02, r), (length * 0.6, r), (length * 0.8, r * 0.75), (length * 0.95, r * 0.25),
            (length, 0.0)]
    k.lathe("shell", prof, body, segs=16, loc=Vector(base), rot=d.to_track_quat("Y", "Z").to_euler(), parent=root)
    k.torus("shell_band", r + 0.004, 0.008, Vector(base) + d * length * 0.15, band,
            rot=d.to_track_quat("Z", "Y").to_euler(), parent=root, segs=16, tube_segs=4)


def _munitions(k, root, level, rnd):
    base = Vector((-2.4, -3.0, 0))
    if level == 1:                                      # bundle of spears and bolts lashed together
        for i in range(9):
            dy = (i % 3 - 1) * 0.06
            dz = 0.08 + (i // 3) * 0.07
            k.tube("spear", base + Vector((-0.9, dy, dz)), base + Vector((0.9, dy + rnd.uniform(-0.02, 0.02), dz)),
                   0.025, "timber_raw", parent=root, segs=6)
            k.cylinder("spear_head", 0.035, 0.22, base + Vector((0.9, dy, dz)), "iron_forged", segs=6,
                       radius_top=0.0, rot=(0, math.pi / 2, 0), parent=root, bevel=False)
        for x in (-0.5, 0.4):
            k.torus("lashing", 0.13, 0.015, base + Vector((x, 0, 0.15)), "rope", rot=(0, math.pi / 2, 0), parent=root,
                    segs=16, tube_segs=4)
        for sx in (-1, 1):
            k.beam("trestle", base + Vector((sx * 0.6, -0.2, 0)), base + Vector((sx * 0.6, 0.0, 0.05)), (0.06, 0.06),
                   "timber_raw", parent=root)
        return
    if level == 2:
        for i, (dx, dy, dz) in enumerate(((0, 0, 0.25), (0.75, 0.05, 0.25), (0.35, 0.0, 0.75))):
            bd.crate(k, root, base + Vector((dx, dy, dz)), (0.7, 0.5, 0.5), 0.1 * i, mat="paint_crate")
        return
    if level == 3:                                      # pyramid of cast balls on a plank frame
        k.box("ball_frame", (1.3, 1.0, 0.08), base + Vector((0.2, 0, 0.04)), "timber_oak", parent=root, bevel=0.01)
        r = 0.13
        for layer in range(3):
            n = 4 - layer
            for i in range(n):
                for j in range(n - 1):
                    c = base + Vector((0.2 + (i - (n - 1) / 2) * 2 * r, (j - (n - 2) / 2) * 2 * r,
                                       0.08 + r + layer * r * 1.42))
                    _ball(k, root, c, r, "iron_black")
        return
    # L4 and L5: shells standing in a rack
    body, band, rack = ("paint_olive", "copper", "iron_black") if level == 4 else ("brass", "gold_trim", "timber_oak")
    k.box("rack_base", (1.6, 0.6, 0.1), base + Vector((0.2, 0, 0.05)), rack, parent=root, bevel=0.01)
    k.box("rack_rail", (1.6, 0.05, 0.06), base + Vector((0.2, -0.22, 0.6)), rack, parent=root, bevel=False)
    for sx in (-1, 1):
        k.box("rack_end", (0.06, 0.6, 0.7), base + Vector((0.2 + sx * 0.78, 0, 0.4)), rack, parent=root, bevel=0.01)
    for i in range(7):
        for j in range(2):
            _shell(k, root, base + Vector((-0.4 + i * 0.2, -0.12 + j * 0.24, 0.1)), (0, 0, 1), 0.8, 0.075, body, band)


TROPHY = {1: ("timber_honey", "iron_forged"), 2: ("iron_forged", "iron_black"), 3: ("iron_black", "iron_forged"),
          4: ("bronze_old", "iron_black"), 5: ("gold_trim", "bronze_old")}


def trophy(k, root, centre, level, w=2.0, y_out=-1.0):
    """The arsenal's mark over the gate: two crossed gun barrels over a stack of shot,
    in relief on the front wall (-Y). Material climbs with the level."""
    mat, ball = TROPHY[level]
    c = Vector(centre)
    half = w / 2
    for sx in (-1, 1):
        a = math.radians(28) * sx
        d = Vector((math.cos(a), 0, math.sin(a)))
        p0 = c - d * half + Vector((0, y_out * 0.06 * (1 + sx) / 2, 0))
        prof = [(0, 0.15), (0.12, 0.17), (0.2, 0.13), (w * 0.8, 0.085), (w * 0.86, 0.11), (w * 0.93, 0.1),
                (w, 0.0)]
        k.lathe("trophy_barrel", prof, mat, segs=16, loc=p0, rot=d.to_track_quat("Y", "Z").to_euler(), parent=root)
        k.lathe("trophy_cascabel", [(-0.14, 0.0), (-0.1, 0.07), (0.0, 0.1)], mat, segs=12, loc=p0,
                rot=d.to_track_quat("Y", "Z").to_euler(), parent=root)
    r = 0.12
    for i, (dx, dz) in enumerate(((-r, 0), (r, 0), (0, r * 1.7))):
        _ball(k, root, c + Vector((dx, y_out * 0.1, -half * 0.55 + dz)), r, ball)


def _rack(k, root, x, y, n=6):
    """Wall rack of spears (inside the open L1 shed)."""
    k.beam("rack_bar", (x - 0.8, y, 1.4), (x + 0.8, y, 1.4), (0.06, 0.06), "timber_raw", parent=root)
    k.beam("rack_bar", (x - 0.8, y, 0.3), (x + 0.8, y, 0.3), (0.06, 0.06), "timber_raw", parent=root)
    for i in range(n):
        xx = x - 0.7 + 1.4 * i / (n - 1)
        k.tube("spear", (xx, y - 0.05, 0.05), (xx + 0.05, y - 0.08, 2.3), 0.025, "timber_raw", parent=root, segs=6)
        k.cylinder("spear_head", 0.035, 0.24, (xx + 0.05, y - 0.08, 2.3), "iron_forged", segs=6, radius_top=0.0,
                   parent=root, bevel=False)


def _l1(k, root, rnd):
    x0, x1, y0, y1 = X0, X1, Y0, Y1
    h = 2.6
    for x in (x0, (x0 + x1) / 2, x1):
        for y in (y0, y1):
            k.box("post", (0.2, 0.2, h + (0.4 if y == y1 else 0)), (x, y, (h + (0.4 if y == y1 else 0)) / 2),
                  "timber_raw", parent=root, bevel=0.015)
    for y, hh in ((y0, h), (y1, h + 0.4)):
        k.beam("plate", (x0 - 0.2, y, hh), (x1 + 0.2, y, hh), (0.18, 0.18), "timber_raw", parent=root)
    # back and side walls of planks, front open
    bd.planks(k, root, (x1, y1 + 0.02), (x0, y1 + 0.02), 0.05, h, 0.05, rnd, mat="timber_raw", w=0.25)
    bd.planks(k, root, (x0 - 0.02, y1), (x0 - 0.02, y0), 0.05, h, 0.05, rnd, mat="timber_raw", w=0.25)
    bd.planks(k, root, (x1 + 0.02, y0), (x1 + 0.02, y1), 0.05, h, 0.05, rnd, mat="timber_raw", w=0.25)
    # lean-to roof sloping toward the camera
    slope = math.atan2(0.4, y1 - y0)
    n = int((x1 - x0 + 0.6) / 0.28)
    for i in range(n):
        x = x0 - 0.3 + (i + 0.5) * (x1 - x0 + 0.6) / n
        k.box("roof_plank", ((x1 - x0 + 0.6) / n - 0.015, (y1 - y0) + 0.8, 0.04),
              (x, (y0 + y1) / 2, h + 0.3 + rnd.uniform(-0.01, 0.01)), "timber_raw",
              rot=(slope + rnd.uniform(-0.01, 0.01), 0, 0), parent=root, bevel=0.006)
    k.box("floor", (x1 - x0, y1 - y0, 0.04), ((x0 + x1) / 2, (y0 + y1) / 2, 0.02), "dirt_fill", parent=root,
          bevel=False)
    _rack(k, root, x0 + 1.4, y1 - 0.3)
    k.cylinder("cart_wheel", 0.55, 0.08, (x1 - 0.35, y1 - 0.6, 0.6), "timber_raw", segs=20,
               rot=(0, math.pi / 2 - 0.25, 0), parent=root, bevel=0.01)
    k.torus("wheel_tyre", 0.56, 0.02, (x1 - 0.3, y1 - 0.6, 0.6), "iron_forged", rot=(0, math.pi / 2 - 0.25, 0),
            parent=root, segs=24, tube_segs=4)
    # windlass on a timber gallows (L1 mechanism) lifting a crate
    g = Vector((1.2, -2.6, 0))
    for sx in (-1, 1):
        k.beam("gallows_leg", g + Vector((sx * 0.9, 0, 0)), g + Vector((sx * 0.7, 0, 3.4)), (0.2, 0.2),
               "timber_raw", parent=root)
        k.beam("gallows_strut", g + Vector((sx * 0.9, 0.7, 0)), g + Vector((sx * 0.75, 0, 2.4)), (0.08, 0.08),
               "timber_raw", parent=root)
    k.beam("gallows_beam", g + Vector((-1.1, 0, 3.45)), g + Vector((1.1, 0, 3.45)), (0.22, 0.22), "timber_raw",
           parent=root)
    k.cylinder("pulley", 0.12, 0.06, g + Vector((0, -0.03, 3.3)), "timber_honey", segs=16, rot=(math.pi / 2, 0, 0),
               parent=root, bevel=False)
    k.cylinder("windlass_drum", 0.1, 1.3, g + Vector((-0.65, 0, 1.0)), "timber_raw", segs=12,
               rot=(0, math.pi / 2, 0), parent=root)
    for sx in (-1, 1):
        k.beam("windlass_handle", g + Vector((sx * 0.68, 0, 1.0)), g + Vector((sx * 0.75, 0, 1.4)), (0.04, 0.04),
               "timber_raw", parent=root)
    k.hose("hoist_rope", [g + Vector((0, 0, 1.1)), g + Vector((0, -0.05, 3.2)), g + Vector((0, -0.12, 3.25)),
                          g + Vector((0, -0.12, 1.6))], 0.012, "rope", parent=root)
    bd.crate(k, root, g + Vector((0, -0.12, 1.3)), (0.6, 0.45, 0.5), 0.1, mat="timber_raw")
    k.box("sign_board", (2.4, 0.06, 0.9), (X0 + GATE_S, Y0 - 0.2, 2.25), "timber_raw", parent=root, bevel=0.01)
    trophy(k, root, (X0 + GATE_S, Y0 - 0.28, 2.3), 1, w=2.0)
    k.flag("pennant", 0.8, 0.35, g + Vector((1.0, 0, 3.55)), "paint_blue", parent=root, waves=2, amp=0.05)


def _doors(k, root, rnd, y, z0, w, h, mat, strap, open_=0.6):
    """Double doors on the front wall, the two leaves swung open toward the camera."""
    cx = X0 + GATE_S
    for sx in (-1, 1):
        hinge = Vector((cx + sx * w / 2, y - 0.04, z0))
        a = sx * open_
        d = Vector((-sx * math.cos(a), -math.sin(abs(a)), 0))
        leaf_c = hinge + d * (w / 4) + Vector((0, 0, h / 2))
        yaw = math.atan2(d.y, d.x)
        k.box("door_leaf", (w / 2, 0.07, h), leaf_c, mat, rot=(0, 0, yaw), parent=root, bevel=0.01)
        for zz in (0.35, h / 2, h - 0.35):
            k.box("door_strap", (w / 2 * 0.9, 0.085, 0.07), leaf_c + Vector((0, 0, zz - h / 2)), strap,
                  rot=(0, 0, yaw), parent=root, bevel=False)
    k.box("gate_dark", (w, 0.05, h), (cx, y + 0.12, z0 + h / 2), "iron_black", parent=root, bevel=False)


def _l2(k, root, rnd):
    x0, x1, y0, y1 = X0, X1, Y0, Y1
    plinth, h = 0.45, 2.6
    gs = (GATE_S - GATE_W / 2, GATE_S + GATE_W / 2, 0, 2.6)
    for p0, p1 in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        bd.masonry(k, root, p0, p1, 0, plinth, 0.55, rnd, mat="stone", course=0.22, unit=(0.3, 0.6), rough=0.05,
                   skip=(gs,) if p0 == (x0, y0) else ())
    k.box("core", (x1 - x0 - 0.2, y1 - y0 - 0.2, plinth + h), ((x0 + x1) / 2, (y0 + y1) / 2, (plinth + h) / 2),
          "timber_tarred", parent=root, bevel=False)
    bd.planks(k, root, (x0, y0 - 0.02), (x1, y0 - 0.02), plinth, h, 0.06, rnd, skip=((gs[0], gs[1], 0, h),))
    bd.planks(k, root, (x1 + 0.02, y0), (x1 + 0.02, y1), plinth, h, 0.06, rnd, skip=((1.6, 2.4, 0.9, 1.6),))
    bd.planks(k, root, (x1, y1 + 0.02), (x0, y1 + 0.02), plinth, h, 0.06, rnd)
    bd.planks(k, root, (x0 - 0.02, y1), (x0 - 0.02, y0), plinth, h, 0.06, rnd)
    bd.window(k, root, (x1 + 0.08, y0 + 2.0, plinth + 1.25), bd.SIDE, 0.8, 0.6, panes=(3, 1))
    for (xa, ya) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        k.box("corner_post", (0.2, 0.2, h + plinth), (xa, ya, (h + plinth) / 2), "timber_tarred", parent=root,
              bevel=0.015)
    k.beam("lintel", (X0 + gs[0] - 0.2, y0 - 0.08, 2.75), (X0 + gs[1] + 0.2, y0 - 0.08, 2.75), (0.22, 0.2),
           "timber_tarred", parent=root)
    _doors(k, root, rnd, y0, 0.0, GATE_W - 0.1, 2.65, "timber_tarred", "iron_forged")
    trophy(k, root, (X0 + GATE_S, y0 - 0.12, 3.35), 2, w=1.9)
    rz = bd.gable_roof(k, root, x0, x1, y0, y1, plinth + h, 1.4, rnd, "timber_tarred", unit=(0.26, 0.24), over=0.4,
                       along="x")
    bd.gable_ends(k, root, x0 - 0.04, x1 + 0.04, y0, y1, plinth + h, rz - 0.04, "timber_tarred", along="x")
    defender.emblem(k, root, (x1 + 0.12, (y0 + y1) / 2, plinth + h + 0.6), (1, 0, 0), h=0.7)
    # slewing jib crane with block and tackle (L2 mechanism)
    c = Vector((1.3, -2.4, 0))
    k.box("crane_foot", (0.7, 0.7, 0.3), c + Vector((0, 0, 0.15)), "stone", parent=root, bevel=0.03)
    k.tube("crane_post", c + Vector((0, 0, 0.3)), c + Vector((0, 0, 4.0)), 0.18, "timber_tarred", parent=root, segs=12)
    for z in (0.6, 3.8):
        k.torus("post_band", 0.14, 0.02, c + Vector((0, 0, z)), "iron_forged", parent=root, segs=20, tube_segs=4)
    tip = c + Vector((-1.6, -0.6, 3.8))
    k.beam("jib", c + Vector((0.3, 0.1, 3.85)), tip, (0.2, 0.24), "timber_tarred", parent=root)
    k.beam("jib_strut", c + Vector((0, 0, 1.9)), c + Vector((-1.0, -0.37, 3.75)), (0.14, 0.14), "timber_tarred",
           parent=root)
    k.cylinder("crane_winch", 0.12, 0.5, c + Vector((-0.25, 0.15, 1.2)), "iron_forged", segs=14,
               rot=(0, math.pi / 2, 0.35), parent=root)
    k.beam("winch_crank", c + Vector((0.28, 0.2, 1.2)), c + Vector((0.32, 0.2, 0.9)), (0.04, 0.04), "iron_forged",
           parent=root)
    k.cylinder("block", 0.1, 0.25, tip + Vector((0, 0, -1.35)), "timber_oak", segs=12, parent=root, bevel=0.01)
    for dx in (-0.03, 0.03):
        k.tube("tackle", tip + Vector((dx, 0, -0.05)), tip + Vector((dx, 0, -1.1)), 0.01, "rope", parent=root,
               segs=4, bevel=False)
    k.hose("crane_rope", [c + Vector((-0.2, 0.15, 1.3)), c + Vector((-0.1, 0.0, 3.7)), tip + Vector((0.1, 0, 0))],
           0.01, "rope", parent=root)
    k.hose("sling", [tip + Vector((0, 0, -1.35)), tip + Vector((-0.3, 0, -1.75)), tip + Vector((0.3, 0, -1.75)),
                     tip + Vector((0, 0, -1.35))], 0.012, "rope", parent=root)
    _shell(k, root, tip + Vector((-0.7, 0, -1.85)), (1, 0, 0), 1.4, 0.13, "iron_black", "iron_forged")


def _rail(k, root, a, b, sleepers_mat="timber_tarred"):
    a, b = Vector(a), Vector(b)
    d = (b - a).normalized()
    side = Vector((-d.y, d.x, 0))
    L = (b - a).length
    for i in range(int(L / 0.45) + 1):
        p = a + d * (i * 0.45)
        k.box("sleeper", (1.1, 0.16, 0.08), p + Vector((0, 0, 0.04)), sleepers_mat,
              rot=(0, 0, math.atan2(d.y, d.x) + math.pi / 2), parent=root, bevel=0.008)
    for s in (-0.3, 0.3):
        k.beam("rail", a + side * s + Vector((0, 0, 0.1)), b + side * s + Vector((0, 0, 0.1)), (0.05, 0.06),
               "steel_worn", parent=root)


def _l3(k, root, rnd):
    x0, x1, y0, y1 = X0, X1, Y0, Y1
    h = 3.6
    gs = (GATE_S - GATE_W / 2, GATE_S + GATE_W / 2, 0, 3.0)
    for p0, p1, sk in (((x0, y0), (x1, y0), (gs,)), ((x1, y0), (x1, y1), ((1.6, 2.6, 1.0, 2.2),)),
                       ((x1, y1), (x0, y1), ()), ((x0, y1), (x0, y0), ())):
        bd.masonry(k, root, p0, p1, 0, h, 0.6, rnd, mat="stone", course=0.3, unit=(0.35, 0.8), rough=0.05, skip=sk)
    k.box("core", (x1 - x0 - 0.5, y1 - y0 - 0.5, h), ((x0 + x1) / 2, (y0 + y1) / 2, h / 2), "iron_black", parent=root,
          bevel=False)
    # arched gate: voussoirs over the opening
    cx = x0 + GATE_S
    r = GATE_W / 2
    for i in range(9):
        a = math.pi * (i + 0.5) / 9
        p = Vector((cx + math.cos(a) * (r + 0.2), y0 - 0.02, 2.4 + math.sin(a) * (r * 0.6 + 0.2)))
        k.box("voussoir", (0.34, 0.66, 0.4), p, "stone", rot=(0, -(a - math.pi / 2), 0), parent=root, bevel=0.02)
    bd.window(k, root, (x1 + 0.27, y0 + 2.1, 1.6), bd.SIDE, 0.8, 1.0, frame="timber_oak")
    _doors(k, root, rnd, y0 - 0.25, 0.0, GATE_W - 0.1, 2.5, "timber_oak", "iron_black", open_=1.2)
    rz = bd.gable_roof(k, root, x0, x1, y0, y1, h, 1.5, rnd, "slate", unit=(0.3, 0.2), over=0.35, thick=0.025,
                       ridge_mat="iron_forged", along="x")
    bd.gable_ends(k, root, x0 + 0.05, x1 - 0.05, y0 + 0.05, y1 - 0.05, h, rz - 0.1, "stone", t=0.5, along="x")
    trophy(k, root, (cx, y0 - 0.34, 3.45), 3, w=2.2)
    # narrow-gauge rail out of the gate with a flat car carrying a gun barrel (L3 mechanism)
    _rail(k, root, (cx, y0 + 0.3, 0), (cx, -4.0, 0))
    car = Vector((cx, -2.75, 0))
    k.box("car_deck", (1.0, 1.6, 0.12), car + Vector((0, 0, 0.42)), "timber_oak", parent=root, bevel=0.01)
    k.box("car_frame", (0.9, 1.5, 0.12), car + Vector((0, 0, 0.3)), "iron_black", parent=root, bevel=0.005)
    for sy in (-0.5, 0.5):
        for sx in (-0.3, 0.3):
            k.cylinder("car_wheel", 0.17, 0.06, car + Vector((sx - 0.03 * (1 if sx > 0 else -1), sy, 0.27)),
                       "iron_black", segs=16, rot=(0, math.pi / 2, 0), parent=root, bevel=False)
    for sy in (-0.45, 0.45):
        k.box("chock", (0.6, 0.12, 0.12), car + Vector((0, sy, 0.54)), "timber_oak", parent=root, bevel=0.01)
    prof = [(0, 0.17), (0.25, 0.19), (0.3, 0.15), (1.9, 0.11), (2.1, 0.13), (2.2, 0.0)]
    k.lathe("barrel", prof, "gunmetal", segs=20, loc=car + Vector((0, -1.0, 0.72)), rot=(0, 0, 0), parent=root)
    k.cylinder("trunnion", 0.06, 0.5, car + Vector((-0.25, -0.35, 0.72)), "gunmetal", segs=10,
               rot=(0, math.pi / 2, 0), parent=root, bevel=False)
    k.hose("car_chain", [car + Vector((-0.45, -0.1, 0.48)), car + Vector((0, -0.1, 0.92)),
                         car + Vector((0.45, -0.1, 0.48))], 0.014, "steel_cable", parent=root)
    bd.flag_mast(k, root, (x0 - 0.45, y0 - 0.45, 0), 6.0, mat="timber_oak", finial="brass")


def _l4(k, root, rnd):
    x0, x1, y0, y1 = X0, X1, Y0, Y1
    h = 3.9
    gs = (GATE_S - GATE_W / 2 - 0.1, GATE_S + GATE_W / 2 + 0.1, 0, 3.2)
    for p0, p1, sk in (((x0, y0), (x1, y0), (gs,)), ((x1, y0), (x1, y1), ((1.6, 2.6, 1.1, 2.3),)),
                       ((x1, y1), (x0, y1), ()), ((x0, y1), (x0, y0), ())):
        bd.masonry(k, root, p0, p1, 0, h, 0.6, rnd, mat="stone_dressed", course=0.36, unit=(0.6, 1.1), rough=0.006,
                   skip=sk)
    k.box("core", (x1 - x0 - 0.5, y1 - y0 - 0.5, h), ((x0 + x1) / 2, (y0 + y1) / 2, h / 2), "iron_black", parent=root,
          bevel=False)
    cx = x0 + GATE_S
    k.box("gate_dark", (GATE_W + 0.2, 0.05, 3.2), (cx, y0 + 0.15, 1.6), "iron_black", parent=root, bevel=False)
    k.beam("door_track", (cx - 2.6, y0 - 0.38, 3.35), (cx + 1.6, y0 - 0.38, 3.35), (0.1, 0.14), "iron_black",
           parent=root)
    for i, off in enumerate((-1.9, 1.3)):                   # sliding doors, one rolled aside, one half shut
        dc = Vector((cx + off * (0.75 if i else 1.0), y0 - 0.42, 1.62))
        k.box("slide_door", (1.3, 0.08, 3.2), dc, "iron_black", parent=root, bevel=0.005)
        for z in (-1.2, 0.0, 1.2):
            k.box("door_rib", (1.3, 0.1, 0.08), dc + Vector((0, 0, z)), "iron_black", parent=root, bevel=0.005)
        for sx in (-0.4, 0.4):
            k.cylinder("door_roller", 0.08, 0.06, dc + Vector((sx, -0.05, 1.72)), "iron_forged", segs=12,
                       rot=(math.pi / 2, 0, 0), parent=root, bevel=False)
        for z in [-1.4 + 0.35 * j for j in range(9)]:
            for x in (-0.6, 0.6):
                k.cylinder("rivet", 0.022, 0.03, dc + Vector((x, -0.05, z)), "iron_black", segs=8,
                           rot=(math.pi / 2, 0, 0), parent=root, bevel=False)
    bd.window(k, root, (x1 + 0.27, y0 + 2.1, 1.7), bd.SIDE, 0.8, 1.0, frame="iron_black")
    # riveted iron barrel-vault roof
    yc, half = (y0 + y1) / 2, (y1 - y0) / 2 + 0.3
    n = 14
    for i in range(n):
        a0, a1 = math.pi * i / n, math.pi * (i + 1) / n
        am = (a0 + a1) / 2
        p = Vector(((x0 + x1) / 2, yc - math.cos(am) * half, h + math.sin(am) * half * 0.55))
        k.box("roof_plate", (x1 - x0 + 0.5, half * math.pi / n * 1.1, 0.04), p, "iron_black",
              rot=(math.atan2(0.55 * math.cos(am), math.sin(am)), 0, 0),
              parent=root, bevel=0.004)
    for x in (x0 - 0.2, x1 + 0.2):
        k.prism("vault_end",
                [(-half * math.cos(math.pi * j / 12), half * 0.55 * math.sin(math.pi * j / 12)) for j in range(13)],
                0.1, "stone_dressed", parent=root)
        o = [c for c in root.children if c.name.startswith("vault_end")][-1]
        o.rotation_euler = (0, 0, math.pi / 2)
        o.location = (x, yc, h)
    defender.emblem(k, root, (x1 + 0.32, yc, 2.9), (1, 0, 0), h=0.9)
    k.box("trophy_plate", (2.6, 0.08, 1.0), (cx, y0 - 0.32, h + 0.25), "iron_black", parent=root, bevel=0.01)
    trophy(k, root, (cx, y0 - 0.4, h + 0.3), 4, w=2.3)
    # overhead gantry crane over the yard (L4 mechanism)
    gx0, gx1, gy = x0 + 0.3, x1 + 0.6, -3.0
    for x in (gx0, gx1):
        for sy in (-1, 1):
            k.beam("gantry_leg", (x, gy + sy * 0.5, 0), (x, gy, 4.3), (0.2, 0.2), "iron_black", parent=root)
        k.beam("gantry_tie", (x, gy - 0.4, 1.0), (x, gy + 0.4, 1.0), (0.08, 0.08), "iron_black", parent=root)
        k.box("gantry_foot", (0.3, 1.3, 0.12), (x, gy, 0.06), "iron_black", parent=root, bevel=0.01)
    for dy in (-0.15, 0.15):
        k.beam("gantry_girder", (gx0 - 0.2, gy + dy, 4.4), (gx1 + 0.2, gy + dy, 4.4), (0.16, 0.4), "iron_black",
               parent=root)
    tr = Vector((cx, gy, 4.2))
    k.box("trolley", (0.6, 0.5, 0.25), tr, "iron_black", parent=root, bevel=0.01)
    k.cylinder("hoist_drum", 0.14, 0.45, tr + Vector((-0.22, 0, -0.3)), "steel_worn", segs=14,
               rot=(0, math.pi / 2, 0), parent=root)
    for dx in (-0.05, 0.05):
        k.tube("hoist_chain", tr + Vector((dx, 0, -0.3)), tr + Vector((dx, 0, -2.4)), 0.012, "steel_cable",
               parent=root, segs=4, bevel=False)
    k.box("hook_block", (0.2, 0.12, 0.3), tr + Vector((0, 0, -2.55)), "paint_yellow", parent=root, bevel=0.01)
    k.hose("sling", [tr + Vector((0, 0, -2.7)), tr + Vector((-0.7, 0, -3.2)), tr + Vector((0.7, 0, -3.2)),
                     tr + Vector((0, 0, -2.7))], 0.015, "steel_cable", parent=root)
    prof = [(0, 0.2), (0.3, 0.22), (0.35, 0.17), (2.4, 0.12), (2.6, 0.15), (2.75, 0.0)]
    k.lathe("barrel", prof, "paint_olive", segs=20, loc=tr + Vector((-1.35, 0, -3.3)), rot=(0, 0, -math.pi / 2),
            parent=root)
    bd.flag_mast(k, root, (x0 - 0.45, y0 - 0.45, 0), 6.6, mat="iron_black", finial="brass")


def _l5(k, root, rnd):
    x0, x1, y0, y1 = X0, X1, Y0, Y1
    h = 4.3
    gs = (GATE_S - GATE_W / 2 - 0.1, GATE_S + GATE_W / 2 + 0.1, 0, 3.3)
    for p0, p1, sk in (((x0, y0), (x1, y0), (gs,)), ((x1, y0), (x1, y1), ((1.6, 2.6, 1.2, 2.5),)),
                       ((x1, y1), (x0, y1), ()), ((x0, y1), (x0, y0), ())):
        bd.masonry(k, root, p0, p1, 0, h, 0.6, rnd, mat="stone_pale", course=0.4, unit=(0.7, 1.2), rough=0.003,
                   skip=sk)
    k.box("core", (x1 - x0 - 0.5, y1 - y0 - 0.5, h), ((x0 + x1) / 2, (y0 + y1) / 2, h / 2), "iron_black", parent=root,
          bevel=False)
    cx = x0 + GATE_S
    for sx in (-1, 1):
        k.cylinder("column", 0.2, 3.5, (cx + sx * (GATE_W / 2 + 0.45), y0 - 0.5, 0.0), "stone_pale", segs=20,
                   parent=root)
        k.box("column_cap", (0.5, 0.5, 0.16), (cx + sx * (GATE_W / 2 + 0.45), y0 - 0.5, 3.55), "gold_trim",
              parent=root, bevel=0.01)
        k.box("column_base", (0.5, 0.5, 0.16), (cx + sx * (GATE_W / 2 + 0.45), y0 - 0.5, 0.08), "stone_pale",
              parent=root, bevel=0.01)
    k.box("pediment_beam", (GATE_W + 1.6, 0.6, 0.4), (cx, y0 - 0.45, 3.83), "stone_pale", parent=root, bevel=0.03)
    k.prism("pediment", [(cx - GATE_W / 2 - 0.8, 4.03), (cx + GATE_W / 2 + 0.8, 4.03), (cx, 4.83)], 0.5,
            "stone_pale", y=y0 - 0.45, parent=root)
    k.box("pediment_gold", (GATE_W + 1.62, 0.62, 0.06), (cx, y0 - 0.45, 3.66), "gold_trim", parent=root, bevel=False)
    _doors(k, root, rnd, y0 - 0.25, 0.0, GATE_W, 3.1, "bronze_old", "gold_trim", open_=1.1)
    bd.window(k, root, (x1 + 0.27, y0 + 2.1, 1.85), bd.SIDE, 0.8, 1.2, frame="iron_black", sill="stone_pale")
    rz = bd.gable_roof(k, root, x0, x1, y0, y1, h, 1.3, rnd, "slate", unit=(0.3, 0.2), over=0.3, thick=0.025,
                       ridge_mat="gold_trim", along="x")
    bd.gable_ends(k, root, x0 + 0.05, x1 - 0.05, y0 + 0.05, y1 - 0.05, h, rz - 0.1, "stone_pale", t=0.5, along="x")
    k.box("cornice_gold", (x1 - x0 + 0.1, y1 - y0 + 0.1, 0.07), ((x0 + x1) / 2, (y0 + y1) / 2, h - 0.05),
          "gold_trim", parent=root, bevel=0.005)
    trophy(k, root, (cx, y0 - 0.74, 4.33), 5, w=1.9)
    defender.emblem(k, root, (x1 + 0.32, (y0 + y1) / 2, 3.2), (1, 0, 0), h=1.0)
    # hydraulic accumulator tower: brass ram under a weight case, pipes to the crane (L5 mechanism)
    a = Vector((2.9, -2.7, 0))
    k.box("acc_plinth", (1.1, 1.1, 0.4), a + Vector((0, 0, 0.2)), "stone_pale", parent=root, bevel=0.03)
    k.cylinder("acc_cylinder", 0.24, 2.4, a + Vector((0, 0, 0.4)), "bronze_old", segs=24, parent=root, bevel=0.01)
    k.cylinder("acc_ram", 0.16, 1.0, a + Vector((0, 0, 2.8)), "chrome", segs=24, parent=root, bevel=False)
    k.cylinder("acc_weight", 0.5, 1.2, a + Vector((0, 0, 3.6)), "iron_black", segs=28, parent=root, bevel=0.02)
    for z in (3.75, 4.6):
        k.torus("acc_band", 0.51, 0.025, a + Vector((0, 0, z)), "gold_trim", parent=root, segs=28, tube_segs=4)
    for sx in (-1, 1):
        k.tube("acc_guide", a + Vector((sx * 0.6, 0, 0.4)), a + Vector((sx * 0.6, 0, 5.2)), 0.05, "iron_black",
               parent=root, segs=10)
    k.box("acc_head", (1.4, 0.2, 0.15), a + Vector((0, 0, 5.25)), "iron_black", parent=root, bevel=0.01)
    g = a + Vector((0.25, -0.25, 1.4))
    k.cylinder("gauge", 0.12, 0.05, g, "brass", segs=20, rot=(math.pi / 2, 0, -0.7), parent=root, bevel=False)
    k.cylinder("gauge_face", 0.1, 0.01, g + Vector((0.03, -0.04, 0)), "enamel_white", segs=20,
               rot=(math.pi / 2, 0, -0.7), parent=root, bevel=False)
    # hydraulic jib crane at the gate, fed from the accumulator
    c = Vector((0.4, -2.9, 0))
    k.cylinder("crane_base", 0.45, 0.35, c, "stone_pale", segs=24, parent=root, bevel=0.02)
    k.cylinder("crane_post", 0.17, 3.6, c + Vector((0, 0, 0.35)), "bronze_old", segs=20, parent=root, bevel=0.01)
    tip = c + Vector((-1.7, -0.3, 3.9))
    k.beam("jib", c + Vector((0.4, 0.1, 3.9)), tip, (0.16, 0.2), "bronze_old", section_end=(0.1, 0.14), parent=root)
    k.tube("jib_ram", c + Vector((0, 0, 1.6)), c + Vector((-1.0, -0.18, 3.8)), 0.07, "chrome", parent=root, segs=12)
    k.hose("hyd_pipe", [a + Vector((-0.3, 0, 0.6)), a.lerp(c, 0.5) + Vector((0, 0.2, 0.15)), c + Vector((0.3, 0, 0.5))],
           0.04, "copper", parent=root)
    k.tube("crane_rope", tip, tip + Vector((0, 0, -1.6)), 0.012, "steel_cable", parent=root, segs=4, bevel=False)
    k.box("hook_block", (0.18, 0.12, 0.26), tip + Vector((0, 0, -1.7)), "brass", parent=root, bevel=0.01)
    k.hose("sling", [tip + Vector((0, 0, -1.8)), tip + Vector((-0.4, 0, -2.2)), tip + Vector((0.4, 0, -2.2)),
                     tip + Vector((0, 0, -1.8))], 0.012, "steel_cable", parent=root)
    _shell(k, root, tip + Vector((-0.8, 0, -2.32)), (1, 0, 0), 1.6, 0.15, "brass", "gold_trim")
    bd.flag_mast(k, root, (x0 - 0.45, y0 - 0.45, 0), 7.2, mat="iron_black", finial="gold_trim")
