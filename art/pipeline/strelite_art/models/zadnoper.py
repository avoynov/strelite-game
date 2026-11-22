"""Rear-striking air spear thrower (bg: „Заднопер“): it lobs a long spear in a high arc at
the rearmost enemy of a wave. Built at game size for a 2x2 site (the gun 3.1 m long,
0.58 m back radius, fixed at 35 degrees; the drop-weight tower 2.75 m tall). Front is
local +Y. No powder: no muzzle flash, an air puff at the mouth is an effect.

How it works (every part must make sense, user 2026-11-22):
  * The gun is a cone with its WIDE END AT THE BACK (user's own description). The cone is
    an air chamber wrapped round a narrow bore that runs through it from the gate in the
    back plate to the mouth. The chamber is big at the back where the air is let into the
    bore behind the spear, and slim at the front where only the bore continues.
  * The air comes from the drop-weight ram on the tower beside the gun: a heavy weight is
    hauled up the tower, then dropped onto a piston in the air cylinder at its foot; the
    blast goes through a hose into the chamber and throws the spear. Range comes from how
    high the weight falls, not from elevation, so the gun stays at 35 degrees.
  * Spears come up out of an underground magazine along the line of the bore, pointing the
    way they will fly, on an open ramp behind the gun. The ramp's foot goes down through a
    ring slot round the turntable, so it can go all the way round with the gun. An endless
    chain with dogs runs up the ramp over a head sprocket (crank, gears or steam) and pushes
    each spear into the gate.
  * The loaded spear waits with its head out of the mouth (user 2026-11-22); at level 1 it
    lies on a sled riding a slotted air pipe, open to view. Spears are chained nose to tail (user's idea): when the spear in the bore is
    thrown, its tail chain draws the waiting spear up through the gate and the next one up
    behind it; the catch at the gate trips the hook so the thrown spear lets go. Straight in
    line, because a rigid 1.9 m spear cannot ride a curved guide.

Levels (siege ladder of materials; a new kind of mechanism each level):
  1  prototype: an open cage of pale pine staves and rope-lashed hoops round a leather air
     bag and a wooden bore; the stone drop weight on a pine tower; the chain feed.
  2  closed tarred staves with forged iron hoops; a hand lever rammer at the gate seats the
     spear past the gate seal.
  3  riveted copper chamber; a riveted copper air receiver sphere with a gauge stores the
     air between drops, so the crew can haul the weight while the gun waits.
  4  blackened steel with bronze bands; twin sprockets on the chute with a gear train and a
     crank draw the chain up, so the next spear is in the gate before the weight is back up.
  5  silver with gold; a small steam compressor with a boiler and chimney charges the
     receiver and drives the sprockets.
Traverse: a log crib round the well (1), a plank platform and a tiller bar (2), a toothed
ring and crank (3), rollers on a ring rail (4), a turntable on a gilded ball race (5).
Ammo: a tied bundle of pine spears, iron-tipped spears in a basket, barbed spears in a
crate, fletched steel spears on a rack, gilded spears in a lacquered case.

Unmistakable: a fat cone tilted up with the wide end low at the back, and a tall tower with
a hanging block beside it. No other gun has either.

Returns (root, turret). The base and the well are static; everything else turns.
Firing animation: the weight drops (frames 1-2), the spear leaves at RELEASE_FRAME, the
chain draws the next spear up into the gate (3-5), then the weight is hauled up again.
"""
import math

import bpy
from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit
from . import defender
from . import faction as fx
from .ballista import _keep_world
from .trebuchet import _ball, _rock

LEVELS = (1, 2, 3, 4, 5)
FRAME_M = 9.0
TARGET_Z = 1.5
SPRITE_FRAME_M = 10.0
SWEEP_M = 3.5
FOOTPRINT_M = 3.0        # 2x2 tiles of 4 m
ROUND_DIRS = 32          # the flying spear is drawn per heading
ROUND_FRAME_M = 2.6

TILT = math.radians(35)
D = Vector((0, math.cos(TILT), math.sin(TILT)))         # along the bore, toward the mouth
N = Vector((0, -math.sin(TILT), math.cos(TILT)))        # up, square to the bore
GL = 2.9                 # gun length, back plate to mouth
RB, RM = 0.55, 0.15      # cone radius at the back and at the mouth
HOLE = Vector((0, -1.37, 0))  # where the line of the bore meets the ground, in the ring slot
FEED_L = 2.45            # feed ramp from the slot up to the gate, along the bore line
SLOT = (1.27, 1.5)       # ring slot in the ground round the turntable: the magazine runs below it
GATE = HOLE + D * FEED_L # the gate (centre of the back plate)
TRUN = 0.55              # trunnions this far along the bore (near the heavy wide end)
SPEAR_L = 1.9
GAP = 0.14               # chain between one spear's tail and the next one's nose
TAIL_READY = GL + 0.55 - SPEAR_L   # loaded spear's tail along the bore: its head 0.55 m out of the mouth
SLED_STOP = GL - 0.3 - TAIL_READY   # how far the sled runs forward before the stop at the mouth
ON_PIPE = 0.1            # level 1: the spear lies on top of the slotted air pipe, this far off its axis
DECK = {1: 0.38, 2: 0.32, 3: 0.33, 4: 0.35, 5: 0.37}    # deck top over the ground
CARRIAGE_Y = 1.8         # front transom of the carriage under the cheeks
TOWER = Vector((1.12, -0.4, 0))                         # foot of the drop-weight tower (turret space)
DROP_M = 1.0             # how far the weight falls

STYLE = {
    1: dict(wood="timber_raw", fit="iron_forged", body=None, band="timber_raw", rope="hemp", weight="stone",
            cyl="timber_raw", deck="log", shaft="timber_raw", head="iron_forged"),
    2: dict(wood="timber_tarred", fit="iron_forged", body="timber_tarred", band="iron_forged", rope="hemp",
            weight="stone", cyl="timber_tarred", deck="timber_tarred", shaft="timber_tarred", head="iron_forged"),
    3: dict(wood="timber_oak", fit="iron_black", body="copper", band="iron_black", rope="hemp", weight="iron_black",
            cyl="copper", deck="timber_oak", shaft="timber_oak", head="steel_worn"),
    4: dict(wood="iron_black", fit="bronze_old", body="iron_black", band="bronze_old", rope="steel_cable",
            weight="iron_black", cyl="iron_black", deck="iron_black", shaft="iron_black", head="steel_worn"),
    5: dict(wood="silver_satin", fit="gold_trim", body="silver_satin", band="gold_trim", rope="steel_cable",
            weight="silver_satin", cyl="silver_satin", deck="silver_satin", shaft="silver_satin", head="gold_trim"),
}

# Firing animation, one row per frame: weight drop (0 top .. 1 bottom); feed (0 rest .. 1 the
# conveyor has pushed the waiting spear into the gate and the next one into its place); the
# sled/loaded spear along the bore (0 ready with the head out of the mouth, + toward the
# stop at the mouth, - back toward the gate); whether the loaded spear is shown.
FIRE = [(0.45, 0.0, 0.0, True), (1.0, 0.0, 1.0, False), (1.0, 0.5, 0.0, False), (1.0, 1.0, -1.0, False),
        (0.85, 0.0, -0.5, True), (0.6, 0.0, 0.0, True), (0.35, 0.0, 0.0, True), (0.1, 0.0, 0.0, True)]
FIRE_FRAMES = len(FIRE)
RELEASE_FRAME = 2
RELOAD_FROM = 3
FIRE_FPS = 12
LOOP = False
_RIG = {}


def _gate(level):
    return GATE.copy()


def _along(level, sv, radial=None):
    p = _gate(level) + D * sv
    return p + radial if radial is not None else p


def _r(sv):
    return RB + (RM - RB) * sv / GL


def _radial(a):
    """Unit vector square to the bore at angle a (0 = +X, 90 deg = up)."""
    return Vector((math.cos(a), 0, 0)) + N * math.sin(a)


ROT_D = (TILT, 0, 0)                                      # lathe +Y -> along the bore
ROT_Z_TO_D = (-(math.pi / 2 - TILT), 0, 0)                # cylinder/torus +Z -> along the bore


def build(style, level=1):
    k = Kit(style)
    s = STYLE[level]
    _RIG.clear()
    root = k.empty("zadnoper")
    _well(k, root, level, s)
    _base(k, root, level, s)
    _ammo(k, root, level, s)
    turret = k.empty("turret", (0, 0, 0), parent=root)
    turret["node"] = "turret"
    mp.set_reference(turret)
    _deck(k, turret, level, s)
    _gun(k, turret, level, s)
    _cheeks(k, turret, level, s)
    _feed(k, turret, level, s)
    _tower(k, turret, level, s)
    if level >= 2:
        _rammer(k, turret, level, s)
    if level >= 3:
        _receiver(k, turret, level, s)
    if level >= 5:
        _compressor(k, turret, level, s)
    m = k.empty("muzzle", _along(level, GL + 0.06), parent=turret)
    m["marker"] = "muzzle"
    set_fire_frame(0)
    return root, turret


def ground(level):
    from ..terrain import Patch
    return Patch(r_solid=FOOTPRINT_M, r_out=FOOTPRINT_M + 0.6, r_bare=2.6, seed=53, ragged=0.5)


# -- the spear ------------------------------------------------------------------------------
HEAD_L = 0.44            # blade length; the socket adds 0.12 behind it


def _blade(half):
    """Closed (y, z) outline of a flat blade from half-widths [(y, w), ...] along its length."""
    right = [(y, -w) for y, w in half]
    left = [(y, w) for y, w in reversed(half) if w > 0]
    return right + left


# Head shapes per level, as half-widths along the blade (user 2026-11-22: a beautiful head
# that shows out of the mouth before the throw).
HEADS = {
    1: [(0.0, 0.026), (0.07, 0.058), (0.2, 0.066), (0.33, 0.04), (0.44, 0.0)],                 # leaf blade
    2: [(0.0, 0.028), (0.05, 0.05), (0.16, 0.07), (0.3, 0.05), (0.38, 0.024), (0.46, 0.0)],     # long leaf
    3: [(0.0, 0.03), (0.01, 0.11), (0.09, 0.066), (0.2, 0.07), (0.34, 0.035), (0.46, 0.0)],     # broad barbed
    4: [(0.0, 0.03), (0.08, 0.05), (0.32, 0.03), (0.46, 0.0)],                                  # four-flanged bodkin
    5: [(0.0, 0.03), (0.04, 0.06), (0.12, 0.085), (0.22, 0.078), (0.35, 0.04), (0.48, 0.0)],    # gilded leaf
}


def _spear(k, parent, tail, d, level, s, length=SPEAR_L):
    """A throwing spear from its tail along d: shaft, socket and a flat forged blade made to
    read at game zoom (leaf 1, long leaf 2, barbed 3, four-flanged bodkin 4, gilded leaf 5),
    fletching from 4. Returns the objects."""
    tail, d = Vector(tail), Vector(d).normalized()
    side = d.cross(Vector((0, 0, 1)))
    if side.length < 0.1:
        side = Vector((1, 0, 0))
    side.normalize()
    up = side.cross(d).normalized()
    h0 = tail + d * (length - HEAD_L)
    objs = [k.tube("spear_shaft", tail, h0 - d * 0.06, 0.028, s["shaft"], parent=parent, segs=10, bevel=False)]
    sock = {1: "iron_forged", 2: "iron_forged", 3: "copper", 4: "bronze_old", 5: "gold_trim"}[level]
    rot = d.to_track_quat("Y", "Z").to_euler()
    rz = d.to_track_quat("Z", "Y").to_euler()
    objs.append(k.lathe("spear_socket", [(-0.13, 0.03), (-0.02, 0.036), (0.0, 0.03), (0.0, 0.0), (-0.13, 0.0)], sock,
                        segs=12, loc=h0, rot=rot, parent=parent))
    if level == 1:                                        # the socket lashed to the shaft
        objs.append(k.torus("spear_lash", 0.032, 0.008, h0 - d * 0.1, "hemp", rot=rz, parent=parent, segs=10,
                            tube_segs=4))
    else:
        objs.append(k.torus("spear_ring", 0.037, 0.01, h0 - d * 0.115, sock, rot=rz, parent=parent, segs=12,
                            tube_segs=4))
    # the blade: a flat plate built in a frame whose Y runs along the spear and X is "up"
    planes = [up] if level != 4 else [up, side]
    for n_ in planes:
        hf = k.empty("spear_headframe", h0, parent=parent)
        m = d.to_track_quat("Y", "X") if n_ is up else d.to_track_quat("Y", "Z")
        hf.rotation_euler = m.to_euler()
        bm = s["head"] if level < 5 else "silver_satin"
        objs.append(k.plate("spear_blade", _blade(HEADS[level]), 0.016, 0.0, bm, parent=hf, bevel=False))
        objs.append(hf)
        if level in (2, 5):                               # a raised mid-rib
            objs.append(k.plate("spear_rib", _blade([(0.0, 0.012), (0.3, 0.008), (0.42, 0.0)]), 0.03, 0.0,
                                bm if level == 2 else "gold_trim", parent=hf, bevel=False))
        if level == 5:                                    # gold edging and two little wings at the socket
            objs.append(k.plate("spear_gilt", _blade([(0.02, 0.07), (0.12, 0.093), (0.22, 0.086), (0.35, 0.047),
                                                      (0.5, 0.0)]), 0.008, 0.0, "gold_trim", parent=hf, bevel=False))
            objs.append(k.plate("spear_wings", _blade([(-0.1, 0.03), (-0.06, 0.09), (-0.03, 0.06), (0.0, 0.03)]),
                                0.012, 0.0, "gold_trim", parent=hf, bevel=False))
    if level >= 4:                                        # three vanes at the tail
        for i in range(3):
            a = 2 * math.pi * i / 3
            v = side * math.cos(a) + up * math.sin(a)
            objs.append(k.beam("spear_vane", tail + d * 0.04 + v * 0.05, tail + d * 0.3 + v * 0.045, (0.006, 0.08),
                               "bronze_old" if level == 4 else "gold_trim", parent=parent, bevel=False))
    return objs


# -- static: the well and the base ------------------------------------------------------------
def _annulus(k, parent, name, r0, r1, z0, h, mat, segs=48):
    return k.lathe(name, [(0.0, r0), (0.0, r1), (h, r1), (h, r0), (0.0, r0)], mat, segs=segs, loc=(0, 0, z0),
                   rot=(math.pi / 2, 0, 0), parent=parent)


def _well(k, root, level, s):
    """The magazine is underground; the feed ramp comes up through a ring slot round the
    turntable, so the ramp's foot can go all the way round with the gun. Dark slot, curbs."""
    r0, r1 = SLOT
    _annulus(k, root, "slot_dark", r0, r1, 0.0, 0.012, "bore", segs=96)
    if level == 1:                                        # short logs pegged round the outer edge
        n = 22
        for i in range(n):
            a = 2 * math.pi * i / n
            c = Vector((math.cos(a), math.sin(a), 0)) * (r1 + 0.08)
            tg = Vector((-math.sin(a), math.cos(a), 0)) * 0.21
            k.tube("slot_log", c - tg + Vector((0, 0, 0.07)), c + tg + Vector((0, 0, 0.07)), 0.075, "log", parent=root,
                   segs=10)
        return
    lining = {2: "timber_tarred", 3: "stone", 4: "stone", 5: "stone"}[level]
    _annulus(k, root, "slot_curb", r1, r1 + 0.1, 0.0, 0.1, lining, segs=96)
    _annulus(k, root, "slot_curb", r0 - 0.08, r0, 0.0, 0.1, lining, segs=96)
    if level == 5:
        _annulus(k, root, "slot_gilt", r1 + 0.1, r1 + 0.13, 0.0, 0.1, "gold_trim", segs=96)


def _floor(k, root, r, h, mat):
    """Static floor inside the slot that the turntable turns on."""
    k.cylinder("floor", r, h, (0, 0, 0), mat, segs=64, parent=root)


def _base(k, root, level, s):
    z = DECK[level]
    r0 = SLOT[0] - 0.08
    if level == 1:                                        # a log crib inside the slot; the frame turns on it
        for sy in (-1, 1):
            k.tube("crib_log", (-0.9, sy * 0.82, 0.1), (0.9, sy * 0.82, 0.1), 0.1, "log", parent=root, segs=12)
        for sx in (-1, 1):
            k.tube("crib_log", (sx * 0.82, -0.9, 0.12), (sx * 0.82, 0.9, 0.12), 0.1, "log", parent=root, segs=12)
        for sx in (-1, 1):                                # pegs where the logs cross
            for sy in (-1, 1):
                k.cylinder("crib_peg", 0.03, 0.1, (sx * 0.82, sy * 0.82, 0.2), "timber_raw", segs=8, parent=root)
        k.cylinder("pivot_post", 0.16, z - 0.2, (0, 0, 0), "log", segs=16, parent=root)
        return
    if level == 2:                                        # a round plank floor inside the slot
        for i in range(12):
            y = -1.1 + i * 0.2
            w = 2 * math.sqrt(max(r0 ** 2 - (abs(y) + 0.1) ** 2, 0.01))
            k.box("plank", (w, 0.19, 0.06), (0, y, 0.03), "timber_tarred", parent=root, bevel=0.005)
        _annulus(k, root, "pivot_ring", 0.3, 1.08, 0.06, z - 0.16, "timber_tarred")
        return
    if level == 3:                                        # stone floor and outer platform, toothed ring outside
        _floor(k, root, r0, 0.1, "stone")
        _annulus(k, root, "platform", SLOT[1] + 0.1, 2.15, 0.0, 0.1, "stone", segs=64)
        _annulus(k, root, "pivot_ring", 0.3, 1.1, 0.1, z - 0.18, "timber_oak")
        R = 1.78
        _annulus(k, root, "gear_ring", R - 0.08, R, 0.1, 0.1, "iron_black", segs=96)
        for i in range(84):
            a = 2 * math.pi * i / 84
            k.box("gear_tooth", (0.05, 0.035, 0.08), (math.cos(a) * (R + 0.02), math.sin(a) * (R + 0.02), 0.14),
                  "iron_black", rot=(0, 0, a), parent=root, bevel=False)
        return
    if level == 4:                                        # ring rail for the carriage rollers
        _floor(k, root, r0, 0.1, "stone")
        _annulus(k, root, "platform", SLOT[1] + 0.1, 2.15, 0.0, 0.1, "stone", segs=64)
        _annulus(k, root, "pivot_ring", 0.3, 1.1, 0.1, z - 0.2, "iron_black")
        _annulus(k, root, "rail", 1.82, 1.9, 0.1, 0.07, "steel_worn", segs=96)
        for i in range(24):
            a = 2 * math.pi * i / 24
            k.box("rail_chair", (0.14, 0.2, 0.04), (math.cos(a) * 1.86, math.sin(a) * 1.86, 0.1), "iron_black",
                  rot=(0, 0, a), parent=root, bevel=0.004)
        return
    # level 5: polished stone, a gilded ring and a ball race
    _floor(k, root, r0, 0.12, "stone")
    _annulus(k, root, "platform", SLOT[1] + 0.13, 2.15, 0.0, 0.12, "stone", segs=64)
    _annulus(k, root, "pivot_ring", 0.3, 1.12, 0.12, z - 0.26, "silver_satin", segs=64)
    _annulus(k, root, "gilded_ring", 1.12, 1.2, 0.12, z - 0.26, "gold_trim", segs=64)
    _annulus(k, root, "race", 1.82, 1.9, 0.12, 0.05, "gold_trim", segs=96)   # outer race for the carriage roller
    for i in range(36):
        a = 2 * math.pi * i / 36
        _ball(k, root, (math.cos(a) * 1.16, math.sin(a) * 1.16, z - 0.11), 0.045, "chrome", subdiv=2)


def _ammo(k, root, level, s):
    """Spare spears on the ground toward the camera."""
    from .trebuchet import ground_spot
    c = ground_spot(2.75, -40)
    yaw = math.atan2(c.y, c.x) + math.pi / 2
    g = k.empty("ammo", c, parent=root)
    g.rotation_euler = (0, 0, yaw)
    if level == 1:                                        # a tied bundle on the ground
        for i in range(5):
            x = -0.12 + i * 0.06
            _spear(k, g, (x, -0.95, 0.04 + 0.03 * (i % 2)), (0, 1, 0), 1, s)
        for y in (-0.4, 0.3):
            k.torus("bundle_tie", 0.16, 0.018, (0, y, 0.07), "hemp", rot=(math.pi / 2, 0, 0), parent=g, segs=16,
                    tube_segs=5)
    elif level == 2:                                      # a basket of iron-tipped spears, standing
        k.cylinder("basket", 0.24, 0.42, (0, 0, 0), "timber_raw", segs=20, parent=g, radius_top=0.28)
        for z in (0.1, 0.25, 0.4):
            k.torus("basket_hoop", 0.25 + z * 0.08, 0.015, (0, 0, z), "hemp", parent=g, segs=20, tube_segs=5)
        for i in range(5):
            a = 2 * math.pi * i / 5
            _spear(k, g, (math.cos(a) * 0.12, math.sin(a) * 0.12, 0.05), (math.cos(a) * 0.12, math.sin(a) * 0.12, 1),
                   2, s)
    elif level == 3:                                      # a plank crate, barbed spears lying in it
        k.box("crate", (0.5, 2.0, 0.22), (0, 0, 0.11), "timber_oak", parent=g, bevel=0.01)
        for y in (-0.9, 0.0, 0.9):
            k.box("crate_band", (0.52, 0.05, 0.23), (0, y, 0.115), "iron_black", parent=g, bevel=False)
        for i in range(4):
            _spear(k, g, (-0.15 + i * 0.1, -0.95, 0.25), (0, 1, 0), 3, s)
    elif level == 4:                                      # an iron rack, fletched spears leaning
        for sy in (-1, 1):
            for sx in (-1, 1):
                k.beam("rack_leg", (sx * 0.25, sy * 0.45, 0), (0, sy * 0.45, 0.8), (0.04, 0.04), "iron_black",
                       parent=g, bevel=False)
        k.beam("rack_bar", (0, -0.5, 0.8), (0, 0.5, 0.8), (0.05, 0.05), "iron_black", parent=g, bevel=False)
        for i in range(5):
            y = -0.36 + i * 0.18
            _spear(k, g, (0.45, y, 0.0), (-0.4, 0, 1.0), 4, s)
    else:                                                 # a lacquered case with gilded spears
        k.box("case", (0.55, 2.1, 0.2), (0, 0, 0.1), "timber_varnish", parent=g, bevel=0.012)
        k.box("case_lining", (0.47, 2.0, 0.02), (0, 0, 0.19), "cloth_oxblood", parent=g, bevel=False)
        for sx in (-1, 1):
            for sy in (-1, 1):
                k.box("case_corner", (0.08, 0.08, 0.21), (sx * 0.25, sy * 1.03, 0.105), "gold_trim", parent=g,
                      bevel=0.004)
        for i in range(4):
            _spear(k, g, (-0.15 + i * 0.1, -0.95, 0.23), (0, 1, 0), 5, s)


# -- turning parts ---------------------------------------------------------------------------
def _deck(k, t, level, s):
    """The turning deck round the well opening; level-specific traverse parts on it."""
    z = DECK[level]
    if level == 1:                                        # a long frame of squared logs on the crib
        for sx in (-1, 1):
            k.beam("deck_beam", (sx * 0.86, -1.0, z - 0.08), (sx * 0.86, CARRIAGE_Y + 0.1, z - 0.08), (0.2, 0.16),
                   "timber_raw", parent=t, bevel=0.01)
        for y in (-0.92, CARRIAGE_Y):
            k.beam("deck_beam", (-1.0, y, z - 0.08), (TOWER.x + 0.15 if y < 0 else 1.0, y, z - 0.08), (0.2, 0.16),
                   "timber_raw", parent=t, bevel=0.01)
        for sx in (-1, 1):
            for y in (-0.92, CARRIAGE_Y):
                k.torus("deck_lash", 0.13, 0.022, (sx * 0.86, y, z - 0.08), "hemp",
                        rot=(0, math.pi / 2, math.pi / 4), parent=t, segs=14, tube_segs=5)
        k.beam("tower_sill", (TOWER.x, -1.0, z - 0.08), (TOWER.x, 0.15, z - 0.08), (0.2, 0.16), "timber_raw",
               parent=t, bevel=0.01)
        k.beam("tower_sill", (0.86, 0.1, z - 0.08), (TOWER.x + 0.1, 0.1, z - 0.08), (0.18, 0.14), "timber_raw",
               parent=t, bevel=0.01)
        # the front of the frame is dragged round on a log skid
        k.tube("skid", (-0.95, CARRIAGE_Y, 0.11), (0.95, CARRIAGE_Y, 0.11), 0.11, "log", parent=t, segs=12)
        for sx in (-1, 1):
            k.box("skid_block", (0.16, 0.16, z - 0.26), (sx * 0.86, CARRIAGE_Y, 0.2 + (z - 0.26) / 2), "timber_raw",
                  parent=t, bevel=0.008)
        return
    mat = s["deck"]
    k.cylinder("deck_hub", 0.32, 0.12, (0, 0, z - 0.12), mat, segs=24, parent=t)
    n = 30
    for i in range(n):                                    # radial deck boards, a gap at the back for the ramp
        a = 2 * math.pi * (i + 0.5) / n
        if abs(math.atan2(math.sin(a + math.pi / 2), math.cos(a + math.pi / 2))) < math.radians(13):
            continue
        d = Vector((math.cos(a), math.sin(a), 0))
        k.box("deck_board", (0.95, 0.27, 0.12), d * 0.78 + Vector((0, 0, z - 0.06)), mat, rot=(0, 0, a), parent=t,
              bevel=0.006)
    _carriage(k, t, level, s)
    if level == 2:                                        # tiller bar at the back to push it round
        a, b = Vector((-0.25, -1.15, z + 0.05)), Vector((-0.3, -2.25, z + 0.35))
        k.beam("tiller", a, b, (0.12, 0.12), "timber_tarred", parent=t, bevel=0.008)
        k.tube("tiller_grip", b + Vector((-0.25, 0, 0)), b + Vector((0.25, 0, 0)), 0.035, "timber_raw", parent=t,
               segs=10)
        k.box("tiller_strap", (0.16, 0.14, 0.16), a.lerp(b, 0.1), "iron_forged", parent=t, bevel=0.005)
    if level == 3:                                        # crank and pinion on the toothed ring
        p = Vector((-0.95, -0.95, z))
        k.cylinder("pinion_post", 0.06, 0.4, p - Vector((0, 0, 0.5)), "iron_black", segs=12, parent=t)
        k.cylinder("pinion", 0.1, 0.08, (math.cos(math.radians(225)) * 1.86, math.sin(math.radians(225)) * 1.86, 0.12),
                   "iron_black", segs=12, parent=t)
        k.beam("pinion_arm", p + Vector((0, 0, -0.1)), (math.cos(math.radians(225)) * 1.86,
                                                         math.sin(math.radians(225)) * 1.86, 0.24), (0.06, 0.06),
               "iron_black", parent=t, bevel=False)
        k.tube("crank_shaft", p + Vector((0, 0, -0.1)), p + Vector((0, 0, 0.55)), 0.03, "iron_black", parent=t, segs=10)
        k.beam("crank_arm", p + Vector((0, 0, 0.55)), p + Vector((-0.25, 0, 0.55)), (0.04, 0.04), "iron_black",
               parent=t, bevel=False)
        k.tube("crank_grip", p + Vector((-0.25, 0, 0.55)), p + Vector((-0.25, 0, 0.72)), 0.025, "wood", parent=t,
               segs=8)
    if level == 5:
        k.torus("deck_trim", 1.25, 0.025, (0, 0, z), "gold_trim", parent=t, segs=64, tube_segs=6)
        k.torus("deck_trim", 0.32, 0.02, (0, 0, z), "gold_trim", parent=t, segs=40, tube_segs=6)


def _carriage(k, t, level, s):
    """Levels 2-5: two sills run forward from the deck under the cheeks to a transom; its
    roller carries the front of the gun round (a wheel on the ground, then on a rail)."""
    z = DECK[level]
    W = s["deck"]
    for sx in (-1, 1):
        k.beam("sill", (sx * 0.86, 0.2, z - 0.08), (sx * 0.86, CARRIAGE_Y + 0.08, z - 0.08), (0.2, 0.16), W, parent=t,
               bevel=0.008)
    k.beam("transom", (-0.98, CARRIAGE_Y, z - 0.08), (0.98, CARRIAGE_Y, z - 0.08), (0.2, 0.16), W, parent=t,
           bevel=0.008)
    on_rail = level >= 4
    r = 0.15
    zr = {2: 0.0, 3: 0.1, 4: 0.17, 5: 0.17}[level] + r     # wheel centre: on the ground, platform or rail
    yw = math.sqrt(max(1.86 ** 2 - 0.5 ** 2, 0)) if on_rail else CARRIAGE_Y
    for sx in ((-1, 1) if on_rail else (0,)):
        x = sx * 0.5
        c = Vector((x, yw, zr))
        rim = {2: "timber_tarred", 3: "iron_black", 4: "bronze_old", 5: "gold_trim"}[level]
        k.cylinder("carriage_wheel", r, 0.1, c - Vector((0.05, 0, 0)), rim, segs=24, rot=(0, math.pi / 2, 0), parent=t)
        k.cylinder("wheel_hub", 0.05, 0.16, c - Vector((0.08, 0, 0)), s["fit"], segs=12, rot=(0, math.pi / 2, 0),
                   parent=t)
        for sxx in (-1, 1):
            k.beam("wheel_fork", c + Vector((sxx * 0.09, 0, 0)), Vector((x + sxx * 0.09, CARRIAGE_Y, z - 0.16)),
                   (0.04, 0.08), s["fit"], parent=t, bevel=0.004)


def _gun(k, t, level, s):
    """The cone: air chamber round the bore, wide end (the back plate and the gate) low at
    the back. Level 1 is an open cage round a leather air bag."""
    G = _gate(level)
    B = s["band"]
    # back plate and the gate in its centre
    back = s["wood"] if level == 1 else (s["body"] if level >= 3 else "timber_tarred")
    if level == 1:                                        # open back: a ring with four spokes to the gate
        k.torus("back_ring", RB - 0.04, 0.04, G - D * 0.04, back, rot=ROT_Z_TO_D, parent=t, segs=36, tube_segs=6)
        for i in range(4):
            a = math.pi / 4 + i * math.pi / 2
            k.beam("back_spoke", G - D * 0.04 + _radial(a) * 0.1, G - D * 0.04 + _radial(a) * (RB - 0.05),
                   (0.05, 0.04), back, parent=t, bevel=0.004)
    else:
        k.lathe("back_plate", [(-0.09, 0.0), (-0.09, RB), (0.0, RB), (0.0, 0.0)], back, segs=40, loc=G, rot=ROT_D,
                parent=t)
    k.box("gate", (0.26, 0.06, 0.26), G - D * 0.11, s["fit"], rot=ROT_D, parent=t, bevel=0.01)
    k.box("gate_hinge", (0.06, 0.08, 0.3), G - D * 0.11 + Vector((-0.14, 0, 0)), s["fit"], rot=ROT_D, parent=t,
          bevel=0.006)
    k.box("gate_catch", (0.08, 0.1, 0.06), G - D * 0.15 - N * 0.1, s["fit"], rot=ROT_D, parent=t, bevel=0.004)
    if level == 1:
        _cage(k, t, level, s)
    else:
        k.lathe("chamber", [(0.0, 0.0), (0.0, RB), (0.08, RB - 0.004), (GL - 0.1, RM), (GL - 0.1, 0.0)], s["body"],
                segs=48, loc=G, rot=ROT_D, parent=t)
        bands = {2: (0.12, 0.6, 1.1, 1.65, 2.25, 2.85), 3: (0.06, 1.55, 2.9), 4: (0.12, 0.95, 1.8, 2.6),
                 5: (0.08, 1.4, 2.75)}[level]
        for sv in bands:
            rr = _r(sv)
            k.torus("hoop", rr + 0.008, 0.025 if level != 3 else 0.03, _along(level, sv), B, rot=ROT_Z_TO_D,
                    parent=t, segs=40, tube_segs=6)
        if level == 2:                                    # stave seams
            for i in range(14):
                a = 2 * math.pi * i / 14
                k.beam("stave_seam", _along(level, 0.04, _radial(a) * (RB + 0.002)),
                       _along(level, GL - 0.12, _radial(a) * (RM + 0.002)), (0.008, 0.008), "timber_raw", parent=t,
                       bevel=False)
        if level == 3:                                    # rivet rows along the seams
            for i in range(6):
                a = 2 * math.pi * i / 6 + 0.26
                fx.rivets(k, t, _along(level, 0.15, _radial(a) * (_r(0.15) + 0.004)),
                          _along(level, 2.8, _radial(a) * (_r(2.8) + 0.004)), 14, _radial(a), r=0.022)
        if level == 5:                                    # gold scroll lines along the top
            for a in (math.radians(70), math.radians(110)):
                k.beam("gilt_line", _along(level, 0.2, _radial(a) * (_r(0.2) + 0.004)),
                       _along(level, 2.6, _radial(a) * (_r(2.6) + 0.004)), (0.02, 0.006), "gold_trim", parent=t,
                       bevel=False)
    # the bore and its mouth ring
    if level == 1:
        k.torus("mouth_ring", RM + 0.01, 0.026, _along(level, GL - 0.04), "iron_forged", rot=ROT_Z_TO_D, parent=t,
                segs=28, tube_segs=6)
        k.lathe("mouth_bore", [(GL + 0.001, 0.0), (GL + 0.001, 0.05), (GL + 0.003, 0.05), (GL + 0.003, 0.0)], "bore",
                segs=16, loc=G, rot=ROT_D, parent=t)
    else:
        k.lathe("mouth", [(GL - 0.14, 0.0), (GL - 0.14, RM + 0.035), (GL + 0.04, RM + 0.035), (GL + 0.04, 0.0)],
                s["fit"], segs=28, loc=G, rot=ROT_D, parent=t)
        k.lathe("mouth_bore", [(GL + 0.041, 0.0), (GL + 0.041, 0.07), (GL + 0.043, 0.07), (GL + 0.043, 0.0)], "bore",
                segs=20, loc=G, rot=ROT_D, parent=t)
    _bore_spear(k, t, level, s)
    if level >= 4:                                        # a crown on the mouth
        k.lathe("mouth_crown", [(GL - 0.02, RM + 0.035), (GL + 0.08, RM + 0.06), (GL + 0.1, RM + 0.04),
                                (GL + 0.1, 0.075), (GL + 0.04, 0.075)], s["band"], segs=28, loc=G, rot=ROT_D, parent=t)
    # the trunnion band
    rt = _r(TRUN)
    k.torus("trunnion_band", rt + 0.02, 0.045, _along(level, TRUN), s["fit"] if level > 1 else "hemp", rot=ROT_Z_TO_D,
            parent=t, segs=40, tube_segs=8)
    for sx in (-1, 1):
        k.tube("trunnion", _along(level, TRUN) + Vector((sx * (rt - 0.02), 0, 0)),
               _along(level, TRUN) + Vector((sx * 0.8, 0, 0)), 0.06, s["fit"] if level > 1 else "iron_forged",
               parent=t, segs=14)


def _cage(k, t, level, s):
    """Level 1, left open so the works show (user 2026-11-22): six thin pine staves and three
    hoops give the funnel; inside, a leather air chest at the wide end feeds a slotted wooden
    air pipe; a sled rides on the pipe with a web down through the slot (sealed by a leather
    flap, like an atmospheric railway), and the spear lies on the sled and on the pipe."""
    G = _gate(level)
    for i in range(6):
        a = 2 * math.pi * i / 6
        k.beam("cage_stave", _along(level, 0.0, _radial(a) * (RB - 0.04)),
               _along(level, GL - 0.06, _radial(a) * (RM - 0.01)), (0.045, 0.04), "timber_raw", parent=t, bevel=0.005)
    for sv in (0.04, 1.3, 2.4):
        rr = _r(sv)
        k.torus("cage_hoop", rr - 0.02, 0.026, _along(level, sv), "timber_raw", rot=ROT_Z_TO_D, parent=t, segs=36,
                tube_segs=6)
        for i in range(6):                                # lashings where staves cross the hoops
            a = 2 * math.pi * i / 6
            k.torus("lash", 0.04, 0.011, _along(level, sv, _radial(a) * (rr - 0.03)), "hemp", rot=ROT_D, parent=t,
                    segs=10, tube_segs=4)
    # the leather air chest at the wide end, tapering into the pipe
    k.lathe("air_chest", [(0.02, 0.06), (0.04, 0.2), (0.14, 0.24), (0.36, 0.2), (0.5, 0.09), (0.55, 0.06)],
            "leather", segs=24, loc=G, rot=ROT_D, parent=t)
    for sv in (0.1, 0.3):
        k.torus("chest_tie", 0.235 if sv < 0.2 else 0.22, 0.014, _along(level, sv), "hemp",
                rot=ROT_Z_TO_D, parent=t, segs=24, tube_segs=4)
    # the slotted air pipe (the bore) and its leather flap over the slot
    k.tube("air_pipe", _along(level, 0.5), _along(level, GL), 0.06, "timber_oak", parent=t, segs=16)
    k.beam("pipe_flap", _along(level, 0.6, N * 0.061), _along(level, GL - 0.05, N * 0.061), (0.045, 0.008),
           "leather", parent=t, bevel=False)
    for sv in (0.7, 1.15, 1.9, 2.6):                      # half straps under the pipe (the slot stays clear)
        k.lathe("pipe_strap", [(sv, 0.0), (sv, 0.068), (sv + 0.05, 0.068), (sv + 0.05, 0.0)], "iron_forged", segs=16,
                loc=G, rot=ROT_D, parent=t)
    # a fork at the mouth end of the pipe: the stop that catches the sled
    k.box("sled_stop", (0.12, 0.05, 0.08), _along(level, GL - 0.18, N * 0.09), "iron_forged", rot=ROT_D, parent=t,
          bevel=0.004)


def _bore_spear(k, t, level, s):
    """The loaded spear in the bore, its head out of the mouth until the throw, on its sled.
    Level 1 shows the sled riding the pipe; higher levels hide it inside the chamber."""
    bore = k.empty("bore_carrier", (0, 0, 0), parent=t)
    _RIG["bore"] = bore
    off = N * ON_PIPE if level == 1 else Vector((0, 0, 0))
    before = set(bpy.data.objects)
    _spear(k, t, _along(level, TAIL_READY) + off, D, level, s)
    spear = set(bpy.data.objects) - before
    _RIG["bore_spear"] = list(spear)
    if level == 1:                                        # the sled: a saddle on the pipe with a fork for the tail
        c = _along(level, TAIL_READY + 0.1, N * 0.075)
        sled = [k.box("sled", (0.13, 0.32, 0.04), c, "timber_oak", rot=ROT_D, parent=t, bevel=0.006)]
        for sx in (-1, 1):
            sled.append(k.beam("sled_fork", c + X * sx * 0.045 - D * 0.1, c + X * sx * 0.045 - D * 0.1 + N * 0.07,
                               (0.02, 0.04), "iron_forged", parent=t, bevel=False))
        sled.append(k.box("sled_web", (0.02, 0.24, 0.05), c - N * 0.03, "iron_forged", rot=ROT_D, parent=t,
                          bevel=False))
        sled.append(k.box("sled_heel", (0.1, 0.03, 0.09), c - D * 0.16 + N * 0.04, "iron_forged", rot=ROT_D, parent=t,
                          bevel=False))
        spear |= set(sled)
    for o in spear:
        _keep_world(o, bore)


def _cheeks(k, t, level, s):
    z = DECK[level]
    T = _along(level, TRUN)
    W = s["wood"]
    out = [(T.y - 0.75, z), (T.y + 0.55, z), (T.y + 0.16, T.z + 0.14), (T.y - 0.16, T.z + 0.14)]
    for sx in (-1, 1):
        k.plate("cheek", out, 0.1, sx * 0.86, W, parent=t, bevel=0.01)
        k.cylinder("cheek_cap", 0.1, 0.05, T + Vector((sx * 0.91, 0, 0)), s["fit"] if level > 1 else "iron_forged",
                   segs=16, rot=(0, sx * math.pi / 2, 0), parent=t)
        if level == 1:
            k.torus("cheek_lash", 0.12, 0.02, (sx * 0.86, T.y - 0.1, z + 0.3), "hemp", rot=(0, math.pi / 2, 0),
                    parent=t, segs=14, tube_segs=5)
        else:
            fx.rivets(k, t, (sx * 0.915, T.y - 0.55, z + 0.08), (sx * 0.915, T.y + 0.35, z + 0.08), 6, (sx, 0, 0),
                      r=0.02)
        if level >= 2:
            defender.emblem(k, t, (sx * 0.915, T.y - 0.25, z + 0.55), (sx, 0, 0), h=0.34)


def _F(sv):
    """A point on the feed line, sv metres up from the hole toward the gate."""
    return HOLE + D * sv


X = Vector((1, 0, 0))


CH = 0.085               # conveyor chain runs this far under the spear line
RS = 0.12                # head sprocket radius


def _feed(k, t, level, s):
    """The feed, left open so the lift reads (user 2026-11-22): the spears come up out of the
    well along the line of the bore, pointing the way they will fly, chained nose to tail.
    An endless chain runs up the run under them and over a head sprocket below the gate;
    a dog on the chain behind each spear's tail pushes it up into the gate. The crew turns
    the sprocket with a crank (1-3), through gears (4), or the steam engine drives it (5).
    Run: peeled poles (1), an open tarred trough (2), open rails on cross ties (3-5)."""
    sv0, sv1 = -0.3, FEED_L - 0.14
    p0, p1 = _F(sv0), _F(sv1)
    zc = DECK[level] - 0.08                               # cross bar on the deck that carries the run
    svc = (zc + 0.08) / math.sin(TILT)
    wood = {1: "timber_raw", 2: "timber_tarred"}.get(level, s["fit"])
    if level == 1:
        for sx in (-1, 1):
            off = X * sx * 0.065 - N * 0.05
            k.tube("feed_pole", p0 + off, p1 + off, 0.03, "timber_raw", parent=t, segs=10)
            for sv in (svc, sv1 - 0.1):
                k.torus("feed_lash", 0.05, 0.012, _F(sv) + off, "hemp", rot=ROT_Z_TO_D, parent=t, segs=10,
                        tube_segs=4)
        k.beam("feed_hanger", _F(sv1 - 0.1) - N * 0.08, _gate(level) - N * (RB - 0.02) - D * 0.02, (0.1, 0.05),
               "timber_raw", parent=t, bevel=0.004)
    elif level == 2:
        k.beam("trough_floor", p0 - N * 0.11, p1 - N * 0.11, (0.24, 0.03), "timber_tarred", parent=t, bevel=0.004)
        for sx in (-1, 1):
            k.beam("trough_side", p0 + X * sx * 0.11 - N * 0.04, p1 + X * sx * 0.11 - N * 0.04, (0.03, 0.14),
                   "timber_tarred", parent=t, bevel=0.003)
        for sv in (0.15, 0.6, sv1 - 0.06):
            k.beam("trough_band", _F(sv) - N * 0.045, _F(sv + 0.05) - N * 0.045, (0.27, 0.16), "iron_forged",
                   parent=t, bevel=False)
    else:
        rail = {3: "iron_black", 4: "iron_black", 5: "silver_satin"}[level]
        for sx in (-1, 1):
            k.beam("feed_rail", p0 + X * sx * 0.075 - N * 0.055, p1 + X * sx * 0.075 - N * 0.055, (0.035, 0.05),
                   rail, parent=t, bevel=0.003)
            k.tube("feed_guide", p0 + X * sx * 0.1 + N * 0.04 + D * 0.3, p1 + X * sx * 0.1 + N * 0.04, 0.014,
                   s["band"], parent=t, segs=8, bevel=False)
        n = 5
        for i in range(n):
            sv = 0.05 + i * (sv1 - 0.15) / (n - 1)
            k.beam("feed_tie", _F(sv) - N * 0.1, _F(sv + 0.05) - N * 0.1, (0.3, 0.04), s["wood"] if level == 3 else
                   s["body"], parent=t, bevel=0.003)
            for sx in (-1, 1):                            # little posts holding the guide rods
                k.beam("guide_post", _F(sv) + X * sx * 0.1 - N * 0.08, _F(sv) + X * sx * 0.1 + N * 0.04,
                       (0.016, 0.016), s["band"], parent=t, bevel=False)
    k.beam("feed_bar", (-0.86, _F(svc).y, zc), (0.86, _F(svc).y, zc), (0.13, 0.12), wood, parent=t, bevel=0.006)
    # the endless chain: up under the spears, over the head sprocket, back down into the well
    sv_top = sv1 - 0.22
    O = _F(sv_top) - N * (CH + RS)
    up_strand = [_F(sv0) - N * CH, _F(sv_top) - N * CH]
    arc = [O + (N * math.cos(a) + D * math.sin(a)) * RS for a in [i * math.pi / 6 for i in range(7)]]
    down_strand = [O - N * RS, _F(sv0) - N * (CH + 2 * RS)]
    _links(k, t, [up_strand[0], up_strand[1]] + arc[1:] + [down_strand[1]])
    sm = {1: "timber_raw", 2: "iron_forged", 3: "iron_black", 4: "bronze_old", 5: "gold_trim"}[level]
    k.cylinder("head_sprocket", RS - 0.02, 0.05, O - X * 0.025, sm, segs=24, rot=(0, math.pi / 2, 0), parent=t)
    for i in range(10):
        a = 2 * math.pi * i / 10
        v = N * math.cos(a) + D * math.sin(a)
        if level == 1:
            k.tube("sprocket_peg", O + v * (RS - 0.03) - X * 0.04, O + v * (RS - 0.03) + X * 0.04, 0.014,
                   "timber_oak", parent=t, segs=6, bevel=False)
        else:
            k.beam("sprocket_tooth", O + v * (RS - 0.03), O + v * (RS + 0.01), (0.03, 0.04), sm, parent=t, bevel=False)
    xs = 0.42 if level == 4 else 0.3
    k.tube("sprocket_shaft", O - X * 0.24, O + X * xs, 0.025, "steel_worn" if level > 1 else "timber_oak", parent=t,
           segs=10)
    zd = DECK[level]
    for sx in (-0.2, 0.2):                                # bearing posts down to a bar on the deck
        k.beam("sprocket_post", O + X * sx, Vector((O.x + sx, O.y, zd)), (0.07, 0.07), wood, parent=t, bevel=0.004)
    k.beam("sprocket_bar", (-0.86, O.y, zd - 0.06), (0.86, O.y, zd - 0.06), (0.12, 0.12), wood, parent=t,
           bevel=0.006)
    if level <= 3:                                        # a hand crank on the shaft
        e = O + X * xs
        k.beam("crank_arm", e, e + N * 0.26, (0.035, 0.03), "timber_raw" if level == 1 else s["fit"], parent=t,
               bevel=False)
        k.tube("crank_grip", e + N * 0.26, e + N * 0.26 + X * 0.16, 0.022, "timber_oak", parent=t, segs=8)
    else:
        g = O + X * 0.4                                   # drive gear and pinion
        k.cylinder("drive_gear", 0.2, 0.05, g - X * 0.025, s["fit"], segs=32, rot=(0, math.pi / 2, 0), parent=t)
        for i in range(18):
            a = 2 * math.pi * i / 18
            v = N * math.cos(a) + D * math.sin(a)
            k.beam("gear_tooth", g + v * 0.19, g + v * 0.23, (0.05, 0.035), s["fit"], parent=t, bevel=False)
        pn = g - D * 0.28 + N * 0.02
        k.cylinder("drive_pinion", 0.08, 0.05, pn - X * 0.025, s["band"], segs=14, rot=(0, math.pi / 2, 0), parent=t)
        k.beam("gear_bracket", pn + X * 0.06, Vector((pn.x + 0.06, pn.y, zd)), (0.05, 0.08), s["fit"], parent=t,
               bevel=False)
        if level == 4:
            k.beam("crank_arm", pn + X * 0.08, pn + X * 0.08 + N * 0.24, (0.035, 0.035), s["fit"], parent=t,
                   bevel=False)
            k.tube("crank_grip", pn + X * 0.08 + N * 0.24, pn + X * 0.22 + N * 0.24, 0.022, "timber_oak", parent=t,
                   segs=8)
        else:
            _RIG["sprocket_drive"] = pn + X * 0.1
    # the chained spears: the waiting one in the run, the next below it in the well, a dog
    # on the conveyor behind each tail
    carrier = k.empty("feed_carrier", (0, 0, 0), parent=t)
    _RIG["carrier"] = carrier
    before = set(bpy.data.objects)
    nose = _gate(level) - D * 0.13
    tail = nose - D * SPEAR_L
    for i in range(2):
        _spear(k, t, tail, D, level, s)
        k.beam("conveyor_dog", tail - D * 0.04 - N * (CH - 0.01), tail - D * 0.04 + N * 0.03, (0.05, 0.05),
               "steel_worn", parent=t, bevel=False)
        _chain(k, t, tail, tail - D * GAP, 2)
        tail = tail - D * (SPEAR_L + GAP)
    for o in set(bpy.data.objects) - before:
        _keep_world(o, carrier)


def _links(k, t, pts, pitch=0.07):
    """Forged chain links along a polyline."""
    i = 0
    for a, b in zip(pts[:-1], pts[1:]):
        L = (b - a).length
        if L < 1e-4:
            continue
        d = (b - a) / L
        q = d.to_track_quat("Y", "Z")
        n = max(1, round(L / pitch))
        for j in range(n):
            p = a + d * (L * (j + 0.5) / n)
            e = q.to_euler()
            e.rotate_axis("Y", math.pi / 2 * (i % 2))
            o = k.torus("chain_link", 0.026, 0.008, p, "steel_worn", parent=t, segs=8, tube_segs=4)
            o.rotation_euler = e
            o.scale = (1.0, 1.5, 1.0)
            i += 1


def _chain(k, t, a, b, n):
    """n forged links from a to b, alternating planes."""
    a, b = Vector(a), Vector(b)
    d = (b - a).normalized()
    q = d.to_track_quat("Y", "Z")
    for i in range(n):
        p = a.lerp(b, (i + 0.5) / n)
        e = q.to_euler()
        e.rotate_axis("Y", math.pi / 2 * (i % 2))
        o = k.torus("chain_link", 0.04, 0.011, p, "steel_worn", rot=(0, 0, 0), parent=t, segs=10, tube_segs=4)
        o.rotation_euler = e
        o.scale = (1.0, 1.6, 1.0)          # oval links along the chain


def _tower(k, t, level, s):
    """The drop-weight air ram: two posts, a pulley, the weight on a piston rod, and the air
    cylinder at the foot with a hose to the chamber."""
    z = DECK[level]
    W = s["wood"]
    P = Vector((TOWER.x, TOWER.y, z))
    H = 2.75
    for sy in (-1, 1):
        k.beam("tower_post", P + Vector((0, sy * 0.3, -0.04)), P + Vector((0, sy * 0.3, H)), (0.14, 0.14), W, parent=t,
               bevel=0.008)
        k.beam("tower_brace", P + Vector((-0.5, sy * 0.3, 0.0)), P + Vector((0, sy * 0.3, 1.2)), (0.09, 0.09), W,
               parent=t, bevel=0.006)
    k.beam("tower_head", P + Vector((0, -0.42, H)), P + Vector((0, 0.42, H)), (0.16, 0.16), W, parent=t, bevel=0.008)
    if level == 1:
        for sy in (-1, 1):
            k.torus("head_lash", 0.11, 0.02, P + Vector((0, sy * 0.3, H - 0.02)), "hemp", parent=t, segs=12,
                    tube_segs=4)
    else:
        for sy in (-1, 1):
            k.box("head_strap", (0.18, 0.04, 0.3), P + Vector((0, sy * 0.3, H - 0.08)), s["fit"], parent=t, bevel=0.004)
    k.cylinder("pulley", 0.1, 0.05, P + Vector((-0.025, 0, H + 0.14)), s["fit"] if level > 1 else "timber_raw",
               segs=18, rot=(0, math.pi / 2, 0), parent=t)
    k.box("pulley_block", (0.08, 0.1, 0.16), P + Vector((0, 0, H + 0.1)), s["fit"] if level > 1 else "timber_raw",
          parent=t, bevel=0.004)
    # air cylinder at the foot
    cyl_h = 0.95
    k.cylinder("air_cyl", 0.2, cyl_h, P, s["cyl"], segs=24, parent=t)
    for zz in (0.05, 0.5, 0.9):
        k.torus("cyl_hoop", 0.205, 0.018, P + Vector((0, 0, zz)), "hemp" if level == 1 else s["band"], parent=t,
                segs=24, tube_segs=5)
    k.cylinder("cyl_cap", 0.22, 0.05, P + Vector((0, 0, cyl_h)), s["fit"] if level > 1 else "timber_raw", segs=24,
               parent=t)
    # the hose into the chamber beside the gate
    G = _gate(level)
    hose = "leather" if level <= 2 else "hose"
    k.hose("air_hose", [P + Vector((-0.2, 0.0, 0.15)), P + Vector((-0.55, 0.05, 0.25)),
                        G + Vector((0.42, 0.05, -0.15)), G + Vector((0.28, 0.0, 0.0)) + D * 0.12], 0.05 if level < 3
           else 0.04, hose, parent=t)
    # the weight on its piston rod, hauled to the top (cocked)
    wt = k.empty("weight", P, parent=t)
    _RIG["weight"] = wt
    _RIG["weight_rest"] = wt.location.copy()
    top = P + Vector((0, 0, 2.05))
    objs = [k.tube("piston_rod", P + Vector((0, 0, cyl_h - 0.1)), top, 0.035, "steel_worn" if level > 1 else "wood",
                   parent=t, segs=10)]
    if level == 1:
        objs.append(_rock(k, t, top + Vector((0, 0, 0.26)), 0.3, seed=71))
        objs.append(k.box("weight_board", (0.5, 0.5, 0.05), top + Vector((0, 0, 0.0)), "timber_raw", parent=t,
                          bevel=0.004))
        for a in (0.0, math.pi / 2):
            objs.append(k.torus("weight_sling", 0.3, 0.02, top + Vector((0, 0, 0.26)), "hemp", rot=(math.pi / 2, 0, a),
                                parent=t, segs=16, tube_segs=4))
    else:
        mat = {2: "stone", 3: "iron_black", 4: "iron_black", 5: "silver_satin"}[level]
        objs.append(k.box("weight_block", (0.46, 0.46, 0.44), top + Vector((0, 0, 0.24)), mat, parent=t, bevel=0.02))
        for zz in (0.08, 0.4):
            objs.append(k.box("weight_strap", (0.48, 0.48, 0.05), top + Vector((0, 0, zz)),
                              {2: "iron_forged", 3: "iron_forged", 4: "bronze_old", 5: "gold_trim"}[level], parent=t,
                              bevel=0.004))
        for sy in (-1, 1):                                # guide shoes riding the posts
            objs.append(k.box("weight_shoe", (0.1, 0.06, 0.3), top + Vector((0, sy * 0.25, 0.24)), s["fit"], parent=t,
                              bevel=0.004))
    for o in objs:
        _keep_world(o, wt)
    rope = k.cylinder("haul_rope", 0.016, 1.0, (0, 0, 0), s["rope"], segs=6, parent=t, bevel=False)
    _RIG["rope"] = (rope, top + Vector((0, 0, 0.5)), P + Vector((0, 0, H + 0.14)))
    # rope down the post to a cleat (level 1) or a windlass drum (2+)
    k.tube("haul_rope_fall", P + Vector((0.1, 0, H + 0.1)), P + Vector((0.1, -0.22, 1.0)), 0.014, s["rope"], parent=t,
           segs=6, bevel=False)
    if level == 1:
        k.box("cleat", (0.06, 0.2, 0.05), P + Vector((0.1, -0.24, 0.95)), "timber_raw", parent=t, bevel=0.004)
    else:
        c = P + Vector((0.12, -0.36, 0.85))
        k.cylinder("winch_drum", 0.08, 0.2, c - Vector((0.1, 0, 0)), s["wood"], segs=16, rot=(0, math.pi / 2, 0),
                   parent=t)
        k.beam("winch_crank", c + Vector((0.12, 0, 0)), c + Vector((0.12, 0.0, 0.22)), (0.03, 0.03), s["fit"],
               parent=t, bevel=False)
    _RIG["drop"] = DROP_M


def _rammer(k, t, level, s):
    """Level 2+: a hand lever beside the gate drives a ram rod that seats the spear past the
    gate seal once the chain has pulled it in."""
    G = _gate(level)
    piv = G + Vector((-0.42, 0, 0)) - D * 0.25
    k.box("rammer_bracket", (0.1, 0.16, 0.16), piv, s["fit"], rot=ROT_D, parent=t, bevel=0.005)
    handle = piv + Vector((-0.08, -0.55, 0.75))
    k.beam("rammer_lever", piv, handle, (0.05, 0.05), s["fit"] if level > 2 else "timber_tarred", parent=t,
           bevel=False)
    k.tube("rammer_grip", handle, handle + Vector((-0.12, 0, 0.0)), 0.03, "wood" if level < 5 else "gold_trim",
           parent=t, segs=8)
    k.tube("ram_rod", piv + Vector((0.05, 0, 0)), G - D * 0.3 - N * 0.08 + Vector((-0.12, 0, 0)), 0.022, "steel_worn",
           parent=t, segs=8)


def _receiver(k, t, level, s):
    """Level 3+: riveted air receiver sphere on the deck at the back left, with a gauge;
    the ram fills it, it feeds the chamber."""
    z = DECK[level]
    c = Vector((-0.95, -0.2, z + 0.5))
    R = 0.34
    mat = {3: "copper", 4: "iron_black", 5: "silver_satin"}[level]
    _ball(k, t, c, R, mat, subdiv=4)
    for a in (0.0, math.pi / 2):
        k.torus("sphere_seam", R + 0.004, 0.012, c, s["band"], rot=(math.pi / 2, 0, a), parent=t, segs=32,
                tube_segs=4)
    for i in range(3):
        a = 2 * math.pi * i / 3 + 0.4
        d = Vector((math.cos(a), math.sin(a), 0))
        k.beam("sphere_leg", c + d * R * 0.6 + Vector((0, 0, -R * 0.6)), c + d * (R + 0.08) + Vector((0, 0, -0.5)),
               (0.05, 0.05), s["fit"], parent=t, bevel=False)
    fx.gauge(k, t, c + Vector((0.05, 0.25, 0.22)), (0.15, 0.8, 0.6), r=0.07)
    k.tube("receiver_valve", c + Vector((0, 0, R)), c + Vector((0, 0, R + 0.12)), 0.035, "brass", parent=t, segs=10)
    G = _gate(level)
    k.hose("receiver_pipe", [c + Vector((0.3, 0.1, 0.0)), c + Vector((0.55, 0.15, 0.25)),
                             G + Vector((-0.3, 0, 0.0)) + D * 0.12], 0.035, s["band"], parent=t)


def _compressor(k, t, level, s):
    """Level 5: a small vertical boiler and a steam compressor on the deck, front left."""
    z = DECK[level]
    b = Vector((0.22, -0.98, z))
    k.cylinder("boiler", 0.24, 0.85, b, "silver_satin", segs=28, parent=t)
    k.cylinder("boiler_dome", 0.24, 0.12, b + Vector((0, 0, 0.85)), "gold_trim", segs=28, parent=t, radius_top=0.12)
    for zz in (0.2, 0.55):
        k.torus("boiler_band", 0.245, 0.015, b + Vector((0, 0, zz)), "gold_trim", parent=t, segs=28, tube_segs=4)
    k.tube("chimney", b + Vector((0, 0, 0.95)), b + Vector((0, 0, 1.7)), 0.05, "silver_satin", parent=t, segs=12)
    k.cylinder("chimney_cap", 0.08, 0.06, b + Vector((0, 0, 1.7)), "gold_trim", segs=12, parent=t, radius_top=0.05)
    k.box("firebox_door", (0.18, 0.03, 0.14), b + Vector((0.0, 0.24, 0.12)), "gold_trim", parent=t, bevel=0.004)
    k.box("firebox_glow", (0.12, 0.02, 0.07), b + Vector((0.0, 0.255, 0.12)), "ember", parent=t, bevel=False)
    cp = b + Vector((-0.34, 0.0, 0.3))
    k.tube("compressor", cp, cp + Vector((-0.5, 0.0, 0.0)), 0.1, "silver_satin", parent=t, segs=18)
    for sx in (0.0, -0.5):
        k.beam("compressor_foot", cp + Vector((sx, 0, -0.05)), cp + Vector((sx, 0, -0.3)), (0.06, 0.12),
               "gold_trim", parent=t, bevel=False)
    k.tube("compressor_rod", cp + Vector((-0.5, 0, 0)), cp + Vector((-0.72, 0.05, 0.08)), 0.025, "chrome", parent=t,
           segs=8)
    k.hose("steam_pipe", [b + Vector((-0.12, 0.05, 0.8)), cp + Vector((0.02, 0.0, 0.25)), cp + Vector((-0.05, 0, 0.1))],
           0.025, "gold_trim", parent=t)
    k.hose("air_pipe", [cp + Vector((-0.45, 0.0, 0.1)), Vector((-0.95, -0.55, z + 0.4)), Vector((-0.95, -0.4, z + 0.5))],
           0.025, "gold_trim", parent=t)
    if "sprocket_drive" in _RIG:                          # a drive shaft up to the sprocket gearing
        k.hose("drive_shaft", [b + Vector((0.0, 0.2, 0.45)), b + Vector((0.1, 0.6, 0.45)), _RIG["sprocket_drive"]],
               0.03, "chrome", parent=t)
    fx.gauge(k, t, b + Vector((0.0, 0.24, 0.6)), (0, 1, 0.2), r=0.06)


# -- animation -------------------------------------------------------------------------------
def _pose(f):
    if f == 0:
        return 0.0, 0.0, 0.0, True
    return FIRE[f - 1]


def _apply(drop, feed, pos, shown):
    wt = _RIG["weight"]
    wt.location = _RIG["weight_rest"] + Vector((0, 0, -drop * _RIG["drop"]))
    rope, top0, pulley = _RIG["rope"]
    top = top0 + Vector((0, 0, -drop * _RIG["drop"]))
    d = pulley - top
    rope.location = top
    rope.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    rope.scale = (1, 1, max(d.length, 0.01))
    _RIG["carrier"].location = D * feed * (SPEAR_L + GAP)
    _RIG["bore"].location = D * (pos * (SLED_STOP if pos > 0 else TAIL_READY))


def key_fire_animation(scene):
    prefs = bpy.context.preferences.edit
    old = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = "LINEAR"
    for f in range(FIRE_FRAMES + 1):
        _apply(*_pose(f))
        for o in (_RIG["weight"], _RIG["carrier"], _RIG["bore"]):
            o.keyframe_insert("location", frame=f)
        for p in ("location", "rotation_euler", "scale"):
            _RIG["rope"][0].keyframe_insert(p, frame=f)
    prefs.keyframe_new_interpolation_type = old


def set_fire_frame(f, scene=None):
    pose = _pose(f)
    if scene is not None and _RIG["weight"].animation_data is not None:
        scene.frame_set(f)
    else:
        _apply(*pose)
    for o in _RIG["bore_spear"]:
        o.hide_render = not pose[3]
    bpy.context.view_layer.update()


def build_round(k, parent, level):
    """The flying spear of this level, centred on `parent`, pointing along +Y."""
    _spear(k, parent, (0, -SPEAR_L / 2, 0), (0, 1, 0), level, STYLE[level])
