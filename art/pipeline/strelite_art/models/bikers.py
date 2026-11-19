"""Motorcycle raiders of the Iron Concord (bg: „Мотоциклисти“): three riders on heavy
military motorcycles in a loose, staggered group, about 3.4 m long overall. The fastest
enemy. Built to the guns' standard (SOP "Human figures"): the riders are the infantry's
MakeHuman bodies on the Rigify Human meta-rig, seated by IK (pelvis on the saddle,
boots on the pegs, gloved hands closed on the grips), in the same field uniform,
helmet and webbing, carbines slung across their backs.

The machines, at 1:1 (2.1 m long, 1.42 m wheelbase, 19 inch wire wheels): a flat-twin
engine with finned cylinders standing out on both sides in front of the rider's shins
and brass rocker covers, twin cradle frame, telescopic fork, teardrop tank between the
knees with the oxblood band and the emblem, sprung solo saddle, high exhausts to
silencers, steel pannier boxes with the emblem, a brass headlamp and horn, knobbly tyres.
The leader carries the pennant.

What makes them unmistakable at game zoom: three hunched riders on dark machines with
the cylinders sticking out sideways, spread out in a staggered line.

Movement: the wheels roll (MOVE_FRAMES frames per heading; one cycle turns them by one
sixth, the repeat of the spoke lacing and the tread). The group faces local +Y;
render_sprites.py --enemy turns it. Returns (root, root).
"""
import math

from mathutils import Matrix, Vector

from .. import materials_photoreal as mp
from .. import mhuman as mh
from ..geo import Kit
from . import faction as fx
from . import infantry as inf
from . import vehicle

SPRITE_FRAME_M = 6.0
LENGTH_M = 3.4
RADIUS_M = 1.4
G, WORN = "paint_enemy", "paint_enemy_worn"
R_WHEEL = 0.34
YF, YR = 0.72, -0.70                     # axles
MOVE_FRAMES = 4
MOVE_KIND = "wheels"
MOVE_CYCLE_M = 2 * math.pi * R_WHEEL / 6
_MOTION = vehicle.Motion(MOVE_FRAMES, MOVE_CYCLE_M)

GROUP = [  # x, y, yaw deg, lean deg, rider height, skin, body shape
    (0.0, 0.75, 0, 2, 1.79, "skin", dict(ancestry={"caucasian": 0.8, "asian": 0.2}, muscle=0.55)),
    (-0.98, -0.55, 6, -2, 1.75, "skin_olive", dict(ancestry={"caucasian": 0.6, "african": 0.4}, muscle=0.5,
                                                  weight=0.45)),
    (0.95, -0.35, -5, 1.5, 1.82, "skin_fair", dict(ancestry={"caucasian": 1.0}, muscle=0.5, weight=0.5)),
]


def set_move_frame(f, scene=None):
    _MOTION.set(f)


def build(style, level=1, only=None):
    global _MOTION
    _MOTION = vehicle.Motion(MOVE_FRAMES, MOVE_CYCLE_M)
    k = Kit(style)
    root = k.empty("bikers")
    mp.set_reference(root)
    for i, (x, y, yaw, lean, h, skin, shape) in enumerate(GROUP):
        if only is not None and i not in only:
            continue
        b = k.empty(f"bike{i}", (x, y, 0) if only is None else (0, 0, 0), parent=root)
        b.rotation_euler = (0, math.radians(lean), math.radians(yaw))
        _machine(k, b, leader=(i == 0))
        _rider(k, b, i, h, skin, dict(shape, height=0.5 + (h - 1.78) * 2.0))
    return root, root


# ---------------------------------------------------------------------------
# the machine
AX = Vector((0, -0.405, 0.914))                  # steering axis, up the fork
AXLE_F = Vector((0, YF, R_WHEEL))
HEAD_B, HEAD_T = AXLE_F + AX * 0.45 + Vector((0, -0.03, 0)), AXLE_F + AX * 0.68 + Vector((0, -0.03, 0))
GRIP = Vector((0.33, 0.40, 1.05))                # right grip centre (mirror for the left)
SEAT = Vector((0, -0.30, 0.80))                  # top of the saddle
PEG = Vector((0.2, -0.04, 0.3))                  # right footpeg


def _machine(k, b, leader):
    for y in (YF, YR):
        vehicle.spoke_wheel(k, b, _MOTION, (0, y, R_WHEEL), R_WHEEL, 0.11, G)
    _frame(k, b)
    _engine(k, b)
    _cycle_parts(k, b)
    _tank_and_saddle(k, b)
    _rear(k, b, leader)


def _frame(k, b):
    # telescopic fork: sliders, stanchions under shrouds, crown and top yoke
    for sx in (-1, 1):
        x = sx * 0.075
        a, c = AXLE_F + Vector((x, 0, 0)), HEAD_B + Vector((x, 0, -0.02))
        k.tube("fork_slider", a, a.lerp(c, 0.45), 0.024, "steel_worn", parent=b, segs=12)
        k.tube("fork_shroud", a.lerp(c, 0.45), c + AX * 0.04, 0.03, G, parent=b, segs=12)
        k.cylinder("axle_nut", 0.018, 0.02, (sx * 0.1, YF, R_WHEEL), "steel_worn", segs=6,
                   rot=(0, sx * math.pi / 2, 0), parent=b, bevel=False)
    k.beam("fork_crown", HEAD_B + Vector((-0.11, 0, -0.01)), HEAD_B + Vector((0.11, 0, -0.01)), (0.05, 0.07), G,
           parent=b, bevel=0.01)
    k.beam("top_yoke", HEAD_T + Vector((-0.11, 0, 0)), HEAD_T + Vector((0.11, 0, 0)), (0.05, 0.04), G, parent=b,
           bevel=0.01)
    k.tube("steering_head", HEAD_B, HEAD_T, 0.035, G, parent=b, segs=14)
    # handlebar sweeping back to rubber grips, levers, brass horn
    gl = Vector((-GRIP.x, GRIP.y, GRIP.z))
    k.hose("handlebar", [gl + Vector((-0.02, -0.01, 0.0)), Vector((-0.2, 0.455, 1.01)), HEAD_T + Vector((0, 0, 0.04)),
                         Vector((0.2, 0.455, 1.01)), GRIP + Vector((0.02, -0.01, 0.0))], 0.012, "steel_worn",
           parent=b)
    for sx in (-1, 1):
        g = Vector((sx * GRIP.x, GRIP.y, GRIP.z))
        d = Vector((sx * 0.94, -0.3, 0.12)).normalized()
        k.tube("grip", g - d * 0.06, g + d * 0.055, 0.019, "rubber", parent=b, segs=12)
        k.tube("lever", g - d * 0.03 + Vector((0, 0.05, 0.01)), g + d * 0.07 + Vector((0, 0.07, -0.01)), 0.006,
               "steel_worn", parent=b, segs=6, bevel=False)
    # twin cradle frame: backbone under the tank, down tubes round the engine, seat stays
    k.hose("backbone", [HEAD_T + Vector((0, -0.02, -0.04)), Vector((0, 0.2, 0.8)), Vector((0, -0.2, 0.74)),
                        Vector((0, -0.36, 0.7))], 0.022, G, parent=b)
    for sx in (-1, 1):
        x = sx * 0.075
        k.hose("cradle", [HEAD_B + Vector((x * 0.5, -0.02, 0.02)), Vector((x, 0.42, 0.42)), Vector((x, 0.3, 0.18)),
                          Vector((x, -0.14, 0.18)), Vector((x, -0.3, 0.42)), Vector((x * 1.3, -0.36, 0.7))], 0.02, G,
               parent=b)
        k.hose("seat_stay", [Vector((x * 1.3, -0.36, 0.7)), Vector((sx * 0.1, -0.56, 0.48)),
                             Vector((sx * 0.11, YR, R_WHEEL))], 0.017, G, parent=b)
        k.tube("lower_stay", (x, -0.3, 0.42), (sx * 0.11, YR, R_WHEEL), 0.017, G, parent=b, segs=10)
        # footpeg with a rubber sleeve
        p = Vector((sx * PEG.x, PEG.y, PEG.z))
        k.tube("peg_arm", (x, PEG.y, 0.22), p + Vector((-sx * 0.06, 0, -0.02)), 0.014, "steel_worn", parent=b,
               segs=8)
        k.tube("footpeg", p - Vector((sx * 0.06, 0, 0)), p + Vector((sx * 0.07, 0, 0)), 0.018, "rubber", parent=b,
               segs=10)


def _engine(k, b):
    """Flat twin: crankcase, finned cylinders out to the sides, brass rocker covers,
    carburettors, gearbox, shaft drive to the rear hub, exhausts to the silencers."""
    k.box("crankcase", (0.24, 0.34, 0.26), (0, 0.08, 0.36), "steel_worn", parent=b, bevel=0.05)
    k.box("sump", (0.2, 0.28, 0.06), (0, 0.08, 0.22), "gunmetal", parent=b, bevel=0.02)
    for sx in (-1, 1):
        cy, cz = 0.13, 0.42
        k.tube("cylinder", (sx * 0.11, cy, cz), (sx * 0.31, cy, cz), 0.058, "gunmetal", parent=b, segs=18)
        for i in range(8):
            k.cylinder("fin", 0.084, 0.007, (sx * (0.14 + i * 0.022), cy, cz), "gunmetal", segs=20,
                       rot=(0, math.pi / 2, 0), parent=b, bevel=False)
        k.box("cyl_head", (0.06, 0.15, 0.15), (sx * 0.33, cy, cz), "gunmetal", parent=b, bevel=0.025)
        k.box("rocker_cover", (0.03, 0.13, 0.13), (sx * 0.37, cy, cz), "brass", parent=b, bevel=0.02)
        k.cylinder("carburettor", 0.03, 0.08, (sx * 0.2, cy - 0.12, cz + 0.06), "steel_worn", segs=12,
                   rot=(math.pi / 2, 0, 0), parent=b, bevel=0.005)
        k.hose("exhaust", [Vector((sx * 0.33, cy + 0.07, cz - 0.03)), Vector((sx * 0.3, cy + 0.12, cz - 0.14)),
                           Vector((sx * 0.2, 0.0, 0.2)), Vector((sx * 0.2, -0.4, 0.27))], 0.022, "steel_worn",
               parent=b)
        k.tube("silencer", (sx * 0.2, -0.4, 0.27), (sx * 0.2, -0.95, 0.38), 0.042, "iron_black", parent=b,
               radius_end=0.036, segs=14)
        k.cylinder("silencer_tip", 0.026, 0.05, (sx * 0.2, -0.95, 0.38), "brass", segs=12,
                   rot=(-math.pi / 2 + 0.2, 0, 0), parent=b, bevel=False)
    k.box("gearbox", (0.2, 0.2, 0.22), (0, -0.18, 0.44), "steel_worn", parent=b, bevel=0.04)
    k.tube("shaft_tube", (0.1, -0.24, 0.4), (0.11, YR, R_WHEEL), 0.032, G, parent=b, segs=12)
    k.cylinder("final_drive", 0.08, 0.06, (0.1, YR, R_WHEEL), "steel_worn", segs=18, rot=(0, math.pi / 2, 0),
               parent=b, bevel=0.01)
    k.cylinder("air_filter", 0.06, 0.1, (0, -0.08, 0.64), "gunmetal", segs=16, parent=b, bevel=0.01)


def _cycle_parts(k, b):
    """Mudguards, headlamp, horn."""
    vehicle.sheet(k, "front_mudguard", vehicle.arc_yz(YF, R_WHEEL, R_WHEEL + 0.05, -15, 125, 14), 0.0, 0.15, G, b,
                  lip=0.03, thick=0.006)
    vehicle.sheet(k, "rear_mudguard", vehicle.arc_yz(YR, R_WHEEL, R_WHEEL + 0.05, 55, 205, 14), 0.0, 0.16, G, b,
                  lip=0.03, thick=0.006)
    lamp = HEAD_B + Vector((0, 0.12, 0.08))
    k.lathe("headlamp", [(-0.11, 0.0), (-0.09, 0.07), (0.0, 0.095), (0.02, 0.0)], "brass", segs=24, loc=lamp,
            parent=b)
    k.cylinder("headlamp_glass", 0.085, 0.01, lamp + Vector((0, 0.012, 0)), "glass", segs=24,
               rot=(-math.pi / 2, 0, 0), parent=b, bevel=False)
    k.box("lamp_visor", (0.16, 0.06, 0.012), lamp + Vector((0, 0.03, 0.09)), "iron_black", rot=(0.2, 0, 0),
          parent=b, bevel=False)
    k.lathe("horn", [(-0.05, 0.0), (-0.04, 0.015), (0.03, 0.03), (0.04, 0.0)], "brass", segs=14,
            loc=lamp + Vector((0.08, 0.0, -0.11)), parent=b)


def _tank_and_saddle(k, b):
    prof = [(-0.16, 0.0), (-0.14, 0.07), (-0.08, 0.115), (0.08, 0.13), (0.26, 0.12), (0.38, 0.08), (0.44, 0.0)]
    t = k.lathe("fuel_tank", prof, G, segs=32, loc=(0, 0.0, 0.86), parent=b)
    t.scale = (0.98, 1.0, 0.82)
    band = k.lathe("tank_band", [(0.0, 0.0), (0.0, 0.1335), (0.07, 0.1335), (0.07, 0.0)], fx.RED, segs=32,
                   loc=(0, 0.02, 0.86), parent=b)
    band.scale = (0.99, 1.0, 0.83)
    k.cylinder("filler_cap", 0.035, 0.03, (0, 0.18, 0.96), "brass", segs=14, parent=b, bevel=0.004)
    k.cylinder("tank_gauge", 0.03, 0.02, (0, 0.3, 0.945), "glass", segs=14, rot=(0.25, 0, 0), parent=b, bevel=False)
    for sx in (-1, 1):
        k.box("knee_pad", (0.02, 0.14, 0.09), (sx * 0.122, -0.06, 0.84), "rubber", rot=(0, 0, sx * 0.12), parent=b,
              bevel=0.012)
        fx.emblem(k, b, (sx * 0.129, 0.17, 0.84), (sx, 0, 0.12), r=0.045)
    # sprung solo saddle on two brass coil springs
    k.box("saddle", (0.25, 0.3, 0.06), SEAT + Vector((0, -0.02, -0.03)), "leather", parent=b, bevel=0.028)
    k.box("saddle_nose", (0.11, 0.16, 0.05), SEAT + Vector((0, 0.17, -0.035)), "leather", rot=(0.12, 0, 0),
          parent=b, bevel=0.02)
    for sx in (-1, 1):
        for i in range(4):
            k.torus("saddle_spring", 0.028, 0.006, (sx * 0.08, SEAT.y - 0.12, SEAT.z - 0.15 + i * 0.03), "brass",
                    parent=b, segs=12, tube_segs=4)


def _rear(k, b, leader):
    """Rear rack with steel pannier boxes, a canvas roll, tail lamp; the leader's pennant."""
    for sx in (-1, 1):
        k.tube("rack_rail", (sx * 0.14, -0.45, 0.72), (sx * 0.14, -1.0, 0.72), 0.012, "iron_black", parent=b, segs=6)
        x = sx * 0.25
        k.box("pannier", (0.13, 0.36, 0.3), (x, -0.72, 0.57), G if sx < 0 else WORN, parent=b, bevel=0.02)
        k.box("pannier_lid", (0.14, 0.37, 0.03), (x, -0.72, 0.725), WORN if sx < 0 else G, parent=b, bevel=0.008)
        k.box("pannier_latch", (0.02, 0.04, 0.05), (x + sx * 0.068, -0.72, 0.68), "brass", parent=b, bevel=False)
        fx.emblem(k, b, (x + sx * 0.067, -0.72, 0.56), (sx, 0, 0), r=0.075)
    k.tube("rack_rail", (-0.14, -1.0, 0.72), (0.14, -1.0, 0.72), 0.012, "iron_black", parent=b, segs=6)
    k.cylinder("bedroll", 0.075, 0.34, (-0.17, -0.78, 0.8), "canvas", segs=16, rot=(0, math.pi / 2, 0), parent=b,
               bevel=0.02)
    k.box("tail_lamp", (0.06, 0.04, 0.05), (0, -1.02, 0.66), fx.RED, parent=b, bevel=0.01)
    if leader:
        fx.pennant(k, b, (-0.14, -0.98, 0.72), h=1.05, w=0.4)


# ---------------------------------------------------------------------------
# the rider
def _rider(k, b, i, h, skin, shape):
    p = mh.Person(k, b, f"rider{i}", h, shape, skin)
    mh.field_uniform(p)
    if i == 0:
        mh.moustache(p)
    s = p.s
    bvh = p.surface()
    tunic = p.surface(["tunic"])

    def front(x, z):
        return p.hit(tunic, (x, 1.0, z), (0, -1, 0))

    def back(x, z):
        return p.hit(tunic, (x, -1.0, z), (0, 1, 0))
    inf._helmet(k, p)
    inf._gear(k, p, "rifle", front, back, bvh, pack=False)
    # carbine slung low across the back, muzzle to the left
    zc = p.J("neck").z
    hb, _ = back(0.0, zc - 0.28 * s)
    u = Vector((-0.88, 0.0, 0.47)).normalized()
    rf = k.empty("carbine", hb + Vector((0.17 * s, -0.05, -0.07 * s)), parent=p.g)
    xa = Vector((0, -1, 0))
    rf.rotation_euler = Matrix((xa, u, xa.cross(u))).transposed().to_euler()
    inf._rifle(k, rf)
    rf.scale = (0.9, 0.9, 0.9)
    p.attach(rf, "DEF-spine.003")
    # seat the rider: pelvis just above the saddle, boots on the pegs, hands on the grips
    fwd_down = Vector((0, 0.55, -0.45)).normalized()
    seat = SEAT + Vector((0, 0.02, 0.105 * s))
    pegs = {"R": PEG + Vector((0, -0.02, 0.085)), "L": Vector((-PEG.x, PEG.y - 0.02, PEG.z + 0.085))}
    bars = {"R": (GRIP + Vector((0.0, 0.0, 0.0)), fwd_down, Vector((-1, 0.3, -0.1)).normalized()),
            "L": (Vector((-GRIP.x, GRIP.y, GRIP.z)), fwd_down, Vector((1, 0.3, -0.1)).normalized())}
    mh.Rider(p, seat, pegs, bars, lean=0.5, chest=0.12).pose()
    return p
