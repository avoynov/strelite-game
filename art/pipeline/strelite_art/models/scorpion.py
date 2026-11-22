"""Heavy bolt thrower (bg: „Скорпион“): the long-range sniper of the siege line. One long
armour-piercing bolt per shot, drawn back slowly by two spoked handwheels. Built a little
larger than history so it reads at game zoom: four arms in a cross, two from upright
skeins (left and right) and two from level skeins (up and down), with two bowstrings that
meet at the claw in the middle, where the bolt sits; a 3.6 m stock on a yoke that turns on
a tall four-legged trestle. Front is local +Y.

It must never be mistaken for the самострел: the cross of four arms and two strings, four
legs instead of a tripod, no hopper, big handwheels at the back.

Levels (each adds what a sniper would want):
  1  pale rough timber lashed with rope, wooden handwheels; a plain iron-tipped bolt
  2  tarred timber shod with forged iron, a front sight post and ring; a long iron bodkin
  3  dark oak, longer arms, a brass range quadrant with a plumb line and a rear peep sight
  4  blackened steel with bronze, a small front shield with a sighting window for the aimer
  5  silver with gold: gilded shield with a sunburst, gold finials; a gold-headed bolt

The draw grows stronger with each level, and the machine shows why: handwheels straight
on the axle (1), a ratchet and pawl (2), a reduction gear (3), worm screws that twist the
skeins tighter (4), a block and tackle on the winch rope (5). The traverse under it changes
too: a plain pivot (1), an iron index ring with a locking pin (2), a trail wheel on a ground
rail (3), a worm-driven gear ring (4), a ball race under the yoke (5).

Returns (root, turret). The trestle is static; the turret (yoke and machine) turns.

Firing animation: set_fire_frame(f) poses frame f of FIRE (1-based; 0 = cocked). The arms
snap forward and the bolt leaves at RELEASE_FRAME, the slider runs forward, hooks the
string and the handwheels wind it back; the next bolt is laid in on the last frame. Play
once per shot. Call only after materials_photoreal.stamp(), which must see it cocked.
"""
import math

import bpy
from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit
from .ballista import _beam, _gear, _keep_world
from .trebuchet import _band, _ball

LEVELS = (1, 2, 3, 4, 5)
FRAME_M = 9.0
TARGET_Z = 1.9
SPRITE_FRAME_M = 10.0
SWEEP_M = 2.7
FOOTPRINT_M = 3.0        # 2x2 tiles of 4 m
Z = 2.3                  # line of the bolt
H = Z - 1.7              # how much taller the trestle is than a plain one
SKEIN_X, FRAME_Y = 0.55, 1.15
SKEIN_V = 0.78           # level skeins above and below the line of the bolt
COCK_DEG = 38
CLAW_Y0 = -1.45
TILT = math.radians(4)

STYLE = {
    1: dict(wood="timber_raw", arm="timber_raw", fit="iron_forged", rope="hemp", skein="hemp",
            bolt=None, band_w=0.08, head="iron_forged", shaft="timber_raw", fletch="leather",
            wheel="timber_raw", arm_l=1.65, arm_v=1.25),
    2: dict(wood="timber_tarred", arm="timber_tarred", fit="iron_forged", rope="hemp", skein="hemp",
            bolt="iron_forged", band_w=0.09, head="iron_forged", shaft="timber_tarred", fletch="leather",
            wheel="iron_forged", arm_l=1.65, arm_v=1.25, sight=True),
    3: dict(wood="timber_oak", arm="timber_oak", fit="iron_forged", rope="hemp", skein="hemp",
            bolt="iron_black", band_w=0.12, head="iron_black", shaft="timber_oak", fletch="leather",
            wheel="iron_black", arm_l=2.0, arm_v=1.4, sight=True, quadrant="bronze_old"),
    4: dict(wood="iron_black", arm="iron_black", fit="bronze_old", rope="steel_cable", skein="hemp",
            bolt="bronze_old", band_w=0.1, head="iron_black", shaft="timber_oak", fletch="bronze_old",
            wheel="bronze_old", arm_l=2.0, arm_v=1.4, sight=True, quadrant="bronze_old", shield="iron_black"),
    5: dict(wood="silver_satin", arm="silver_satin", fit="gold_trim", rope="steel_cable",
            skein="steel_cable", bolt="gold_trim", band_w=0.09, head="gold_trim", shaft="silver_satin",
            fletch="gold_trim", wheel="gold_trim", arm_l=2.0, arm_v=1.4, sight=True, quadrant="gold_trim",
            shield="silver_satin", ornament=True, tackle=True),
}

# Firing animation, one row per frame: arm sweep (deg back; COCK_DEG = cocked), slider shift
# forward (m), string on the claw, bolt shift forward (m, None = gone), handwheel turn (deg).
FIRE = [
    (6, 0.0, False, 1.1, 0),       # 1  loosed: arms flying forward, bolt leaving
    (-14, 0.0, False, None, 0),    # 2  release: the bolt is away
    (-8, 0.8, False, None, 0),     # 3  the slider runs forward
    (-4, 1.55, True, None, 0),     # 4  the claw takes the string
    (6, 1.3, True, None, 45),      # 5  winding back
    (14, 1.05, True, None, 90),
    (21, 0.8, True, None, 135),
    (27, 0.57, True, None, 180),
    (32, 0.36, True, None, 225),
    (36, 0.16, True, None, 270),
    (38, 0.0, True, None, 315),    # 11 cocked
    (38, 0.0, True, 0.0, 360),     # 12 the next bolt laid in
]
FIRE_FRAMES = len(FIRE)
RELEASE_FRAME = 2
RELOAD_FROM = 3
FIRE_FPS = 12
LOOP = False
BOLT_LEN = 1.75
ROUND_DIRS = 32          # the flying bolt is drawn per heading, not tumbling
ROUND_FRAME_M = 2.2
_RIG = {}


def build(style, level=1):
    k = Kit(style)
    s = STYLE[level]
    root = k.empty("scorpion")
    _trestle(k, root, level, s)
    _bolt_rack(k, root, level, s)
    turret = k.empty("turret", (0, 0, 0), parent=root)
    turret["node"] = "turret"
    mp.set_reference(turret)
    _yoke(k, turret, level, s)
    _stock(k, turret, level, s)
    _capitulum(k, turret, level, s)
    _sights(k, turret, level, s)
    if level >= 3:
        _feed(k, root, turret, level, s)
    if level >= 2:
        _loader(k, turret, level, s)
    m = k.empty("muzzle", (0, FRAME_Y + 0.4, _z(FRAME_Y + 0.4) + 0.12), parent=turret)
    m["marker"] = "muzzle"
    _rig(k, turret, level, s)
    return root, turret


def ground(level):
    from ..terrain import Patch
    return Patch(r_solid=FOOTPRINT_M, r_out=FOOTPRINT_M + 0.6, r_bare=2.6, seed=71, ragged=0.5)


def _z(y):
    return Z + y * math.tan(TILT)


# -- static trestle -------------------------------------------------------------------------
def _trestle(k, root, level, s):
    W = s["wood"]
    top = 1.2 + H
    _beam(k, root, "column", (0, 0, 0.0), (0, 0, top), (0.28, 0.28), W)
    if level == 1:                                        # prototype: one post set in the ground, wedged
        for i in range(4):
            a = math.radians(45 + 90 * i)
            d = Vector((math.cos(a), math.sin(a), 0))
            _beam(k, root, "wedge", d * 0.17 + Vector((0, 0, 0.0)), d * 0.36 + Vector((0, 0, -0.02)), (0.12, 0.08), W)
    for i in range(4 if level > 1 else 0):
        a = math.radians(45 + 90 * i)
        foot = Vector((1.25 * math.cos(a), 1.25 * math.sin(a), 0.07))
        knee = Vector((0, 0, 0.85 + H))
        _beam(k, root, "leg", foot, knee, (0.15, 0.15), W)
        _beam(k, root, "sill", foot * 0.12, foot + Vector((0, 0, -0.03)), (0.13, 0.11), W)
        _band(k, root, knee + (foot - knee) * 0.08, foot - knee, (0.15, 0.15), level, s)
        if level > 1:
            k.box("foot_shoe", (0.2, 0.2, 0.04), foot + Vector((0, 0, -0.02)), s["fit"], parent=root,
                  bevel=0.004)
    for i in range(4 if level > 1 else 0):                # a square of braces between the legs
        a0, a1 = math.radians(45 + 90 * i), math.radians(135 + 90 * i)
        p0 = Vector((0.88 * math.cos(a0), 0.88 * math.sin(a0), 0.24))
        p1 = Vector((0.88 * math.cos(a1), 0.88 * math.sin(a1), 0.24))
        _beam(k, root, "brace", p0, p1, (0.07, 0.07), W)
    _band(k, root, (0, 0, top - 0.12), (0, 0, 1), (0.28, 0.28), level, s, width=0.12)
    k.cylinder("turn_plate", 0.26, 0.05, (0, 0, top), s["fit"] if level > 1 else "iron_forged", segs=24,
               parent=root)
    # -- the traverse, a new kind per level
    if level in (2, 3):                                   # index ring: holes for the locking pin
        k.cylinder("index_ring", 0.46, 0.04, (0, 0, top - 0.06), s["fit"], segs=40, parent=root)
        for i in range(16):
            a = 2 * math.pi * i / 16
            k.cylinder("index_hole", 0.025, 0.01, (0.4 * math.cos(a), 0.4 * math.sin(a), top - 0.02),
                       "gunmetal", segs=8, parent=root, bevel=False)
    if level >= 3:                                        # ground rail for the trail wheel
        R = 2.05
        k.torus("rail", R, 0.035, (0, 0, 0.07), s["fit"] if level > 3 else "iron_forged", parent=root, segs=96,
                tube_segs=6)
        for i in range(24):
            a = 2 * math.pi * i / 24
            d = Vector((math.cos(a), math.sin(a), 0))
            k.box("sleeper", (0.34, 0.1, 0.05), d * R + Vector((0, 0, 0.025)), "timber_oak" if level < 5 else
                  "timber_oak", rot=(0, 0, a), parent=root, bevel=0.004)
    if level >= 4:                                        # gear ring for the worm traverse
        m = s["fit"]
        k.cylinder("traverse_ring", 0.5, 0.06, (0, 0, top - 0.1), m, segs=48, parent=root)
        for i in range(36):
            a = 2 * math.pi * i / 36
            d = Vector((math.cos(a), math.sin(a), 0))
            k.box("tooth", (0.05, 0.03, 0.06), d * 0.52 + Vector((0, 0, top - 0.07)), m, rot=(0, 0, a),
                  parent=root, bevel=False)
    if level >= 5:                                        # ball race: silver balls under the yoke
        for i in range(18):
            a = 2 * math.pi * i / 18
            _ball(k, root, (0.3 * math.cos(a), 0.3 * math.sin(a), top + 0.08), 0.05, "silver", subdiv=2)


def _bolt_rack(k, root, level, s):
    """Spare bolts on the ground: a rope-tied bundle (1) or a small two-trestle rack."""
    from .trebuchet import ground_spot
    c = ground_spot(2.95, -42)
    rot = Vector((c.x, c.y, 0)).to_track_quat("Y", "Z").to_euler()
    g = k.empty("rack", c, parent=root)
    g.rotation_euler = (0, 0, rot.z + math.pi / 2)
    zb = 0.05
    if level > 1:
        for y in (-0.5, 0.5):
            for sx in (-1, 1):
                _beam(k, g, "rack_leg", (sx * 0.3, y, 0.0), (0, y, 0.32), (0.05, 0.05), s["wood"])
            _beam(k, g, "rack_bar", (-0.3, y, 0.3), (0.3, y, 0.3), (0.06, 0.06), s["wood"])
        zb = 0.36
    for i in range(5):
        x = -0.16 + i * 0.08
        z = zb + (0.05 if i % 2 else 0.0)
        _bolt(k, g, (x, -0.85, z), (0, 1, 0), level, s)
    if level == 1:
        for y in (-0.35, 0.35):
            k.torus("bundle_rope", 0.22, 0.016, (0, y, zb + 0.03), s["rope"], rot=(math.pi / 2, 0, 0), parent=g,
                    segs=16, tube_segs=5)


# -- turret --------------------------------------------------------------------------------
def _yoke(k, t, level, s):
    W = s["wood"]
    hz = 1.24 + H
    k.cylinder("yoke_hub", 0.22, 0.12, (0, 0, hz), W, segs=18, parent=t)
    for sx in (-1, 1):
        _beam(k, t, "yoke_cheek", (sx * 0.22, -0.05, hz + 0.02), (sx * 0.22, -0.05, Z - 0.12), (0.09, 0.34), W)
        k.cylinder("trunnion", 0.065, 0.06, (sx * 0.3, -0.05, Z - 0.22), s["fit"] if level > 1 else W, segs=12,
                   rot=(0, math.pi / 2, 0), parent=t)
    _beam(k, t, "yoke_bar", (-0.26, -0.05, hz + 0.04), (0.26, -0.05, hz + 0.04), (0.12, 0.1), W)
    p0 = Vector((0, -0.15, hz + 0.04))
    p1 = Vector((0, -1.3, Z - 0.2))
    if level >= 3:                                        # elevation screw
        k.tube("elev_screw", p0, p1, 0.035, s["fit"], parent=t, segs=10)
        d = (p1 - p0).normalized()
        for i in range(9):
            k.torus("thread", 0.045, 0.01, p0.lerp(p1, 0.1 + i * 0.09), s["fit"],
                    rot=d.to_track_quat("Z", "Y").to_euler(), parent=t, segs=12, tube_segs=4)
    else:
        _beam(k, t, "elev_prop", p0, p1, (0.08, 0.08), W)
    if level in (2, 3):                                   # the locking pin for the index ring
        c = Vector((0, -0.4, hz))
        k.box("pin_bracket", (0.12, 0.2, 0.06), c + Vector((0, 0.12, 0.02)), s["fit"], parent=t, bevel=0.004)
        k.tube("lock_pin", c + Vector((0, 0, -0.16)), c + Vector((0, 0, 0.18)), 0.022, s["fit"], parent=t, segs=8)
        k.torus("pin_ring", 0.05, 0.01, c + Vector((0, 0, 0.23)), s["fit"], rot=(math.pi / 2, 0, 0), parent=t,
                segs=12, tube_segs=4)
    if level >= 3:                                        # trail wheel under the stock, on the ground rail
        yw = -2.05
        wc = Vector((0, yw, 0.18))
        zst = _z(yw) - 0.25
        for sx in (-1, 1):
            _beam(k, t, "trail_leg", (sx * 0.16, yw + 0.05, zst), (sx * 0.1, yw, wc.z), (0.07, 0.07), s["wood"])
        _beam(k, t, "trail_brace", (0, yw + 0.05, zst - 0.3), (0, -1.1, hz + 0.08), (0.06, 0.06), s["wood"])
        k.cylinder("trail_wheel", 0.15, 0.08, wc - Vector((0.04, 0, 0)), s["wheel"], segs=20,
                   rot=(0, math.pi / 2, 0), parent=t)
        k.tube("trail_axle", (-0.12, yw, wc.z), (0.12, yw, wc.z), 0.025, s["fit"], parent=t, segs=8, bevel=False)
    if level >= 4:                                        # worm and handwheel on the traverse ring
        m = s["fit"]
        wy = -0.6
        zw = hz - 0.2
        _beam(k, t, "worm_bracket", (0, -0.15, hz - 0.02), (0, wy, zw + 0.08), (0.08, 0.06), W)
        k.tube("traverse_worm", (-0.2, wy, zw), (0.38, wy, zw), 0.05, "steel_worn" if level == 4 else "silver",
               parent=t, segs=10, bevel=False)
        for i in range(6):
            k.torus("worm_thread", 0.055, 0.013, (-0.12 + i * 0.05, wy, zw), m, rot=(0.25, math.pi / 2, 0),
                    parent=t, segs=12, tube_segs=4)
        hw = Vector((0.42, wy, zw))
        k.torus("traverse_wheel", 0.17, 0.022, hw, m, rot=(0, math.pi / 2, 0), parent=t, segs=20, tube_segs=5)
        for i in range(4):
            a = math.pi / 4 + i * math.pi / 2
            r = Vector((0, math.cos(a), math.sin(a)))
            k.beam("tw_spoke", hw + r * 0.03, hw + r * 0.16, (0.02, 0.02), m, parent=t, bevel=False)
        k.tube("tw_handle", hw + Vector((0, 0, 0.17)), hw + Vector((0.12, 0, 0.17)), 0.016, W, parent=t, segs=6,
               bevel=False)


def _stock(k, t, level, s):
    W = s["wood"]
    y0, y1 = -2.25, FRAME_Y + 0.5
    _beam(k, t, "case", (0, y0, _z(y0) - 0.15), (0, y1, _z(y1) - 0.15), (0.3, 0.2), W)
    for sx in (-1, 1):
        _beam(k, t, "rail", (sx * 0.12, y0 + 0.05, _z(y0) - 0.03), (sx * 0.12, y1, _z(y1) - 0.03), (0.06, 0.05), W)
    for f in (0.1, 0.42, 0.75):
        p = Vector((0, y0 + (y1 - y0) * f, _z(y0 + (y1 - y0) * f) - 0.15))
        _band(k, t, p, (0, 1, 0), (0.3, 0.2), level, s)
    # the winch: cheeks and the axle; the wheels turn (see _rig)
    y = -2.0
    for sx in (-1, 1):
        _beam(k, t, "winch_cheek", (sx * 0.2, y - 0.15, _z(y) - 0.32), (sx * 0.2, y + 0.15, _z(y) - 0.32),
              (0.07, 0.36), W)
    k.empty("wheel_axis", (0, y, _z(y) - 0.12), parent=t)["rig_name"] = "wheels"
    k.cylinder("ratchet", 0.1, 0.04, (-0.17, -1.6, _z(-1.6) - 0.08), s["fit"] if level > 1 else "iron_forged",
               segs=12, rot=(0, math.pi / 2, 0), parent=t)


def _feed(k, root, t, level, s):
    """Levels 3-5: a closed bolt feed from a magazine under the ground (user 2026-11-22). A thick
    boxed duct rises from a hatch beside the trestle to a rotary collar round the column; a
    second chute on the turret carries the bolts from the collar to the claw. Bolts are not seen."""
    W, F = s["wood"], s["fit"]
    top = 1.2 + H
    hatch = Vector((1.05, 0.0, 0.0))
    k.box("feed_hatch", (0.62, 0.62, 0.34), hatch + Vector((0, 0, 0.17)), W, parent=root, bevel=0.02)
    k.box("feed_hatch_lid", (0.66, 0.66, 0.05), hatch + Vector((0, 0, 0.36)), F, parent=root, bevel=0.01)
    p0, p1 = hatch + Vector((-0.05, 0, 0.36)), Vector((0.34, 0.0, top - 0.42))
    k.beam("feed_duct", p0, p1, (0.34, 0.34), W, parent=root, bevel=0.015)
    d = p1 - p0
    for f in (0.12, 0.45, 0.78):                          # bands round the duct
        c = p0 + d * f
        k.beam("feed_band", c, c + d.normalized() * 0.06, (0.38, 0.38), F, parent=root, bevel=0.005)
    k.cylinder("feed_collar", 0.36, 0.2, (0, 0, top - 0.5), F, segs=32, parent=root)
    k.cylinder("feed_collar_cap", 0.38, 0.04, (0, 0, top - 0.3), W, segs=32, parent=root)
    # on the turret: from the collar up to the side of the stock behind the claw
    q0, q1 = Vector((0.3, -0.15, top - 0.28)), Vector((0.24, CLAW_Y0 + 0.55, _z(CLAW_Y0 + 0.55) - 0.12))
    k.beam("feed_chute", q0, q1, (0.26, 0.26), W, parent=t, bevel=0.012)
    e = q1 - q0
    for f in (0.2, 0.7):
        c = q0 + e * f
        k.beam("feed_band", c, c + e.normalized() * 0.05, (0.3, 0.3), F, parent=t, bevel=0.005)
    k.box("feed_gate", (0.3, 0.3, 0.2), q1 + Vector((-0.04, 0, 0.06)), F, parent=t, bevel=0.01)


LOADER = Vector((1.4, -1.0, 0))     # foot of the loading crane (turret space, beside the stock)


def _loader(k, t, level, s):
    """Levels 2-5: a separate pincer crane standing on the ground beside the scorpion (user
    2026-11-22). It rolls round with the gun on its own little carriage, keeps a few bolts in
    a rack on its column, and lays the next bolt in the channel; shown holding it above.
    Pine and iron (2), iron and brass (3), bronze (4), silver and gold (5)."""
    col, J, F = {2: ("timber_tarred", "iron_forged", "iron_forged"), 3: ("iron_black", "brass", "steel_worn"),
                 4: ("iron_black", "bronze_old", "bronze_old"), 5: ("silver_satin", "gold_trim", "silver_satin")}[level]
    P = LOADER
    # its carriage on the ground: a cross of runners on small wheels (a skid at 2)
    for a in (0.6, 0.6 + math.pi / 2):
        d = Vector((math.cos(a), math.sin(a), 0)) * 0.28
        k.beam("loader_runner", P - d + Vector((0, 0, 0.09)), P + d + Vector((0, 0, 0.09)), (0.09, 0.09), col,
               parent=t, bevel=0.006)
        if level >= 3:
            for e in (-1, 1):
                c = P + d * e + Vector((0, 0, 0.06))
                k.cylinder("loader_castor", 0.06, 0.04, c - Vector((0, 0, 0)) + d.normalized().cross(Vector((0, 0, 1)))
                           * 0.02, J, segs=14, rot=(math.pi / 2, 0, a + math.pi / 2), parent=t)
    k.cylinder("loader_foot", 0.15, 0.08, P + Vector((0, 0, 0.13)), J, segs=20, parent=t)
    H = _z(P.y) + 0.65
    if col.startswith("timber"):
        _beam(k, t, "loader_column", P + Vector((0, 0, 0.18)), P + Vector((0, 0, H)), (0.14, 0.14), col)
    else:
        k.cylinder("loader_column", 0.07, H - 0.18, P + Vector((0, 0, 0.18)), col, segs=16, parent=t)
    for f in (0.3, 0.7):
        k.cylinder("loader_collar", 0.095, 0.05, P + Vector((0, 0, 0.18 + (H - 0.18) * f)), J, segs=16, parent=t)
    for sx in (-1, 1):                                   # struts from the carriage up the column
        a = 0.6 + (math.pi / 2 if sx > 0 else 0)
        d = Vector((math.cos(a), math.sin(a), 0)) * 0.3
        k.beam("loader_strut", P + d + Vector((0, 0, 0.14)), P + Vector((0, 0, 0.9)), (0.04, 0.05), F, parent=t,
               bevel=False)
    # a small rack of bolts on the column, tips up
    for i in range(3):
        a = math.pi * 0.9 + i * 0.35
        b0 = P + Vector((math.cos(a) * 0.13, math.sin(a) * 0.13, 0.35))
        _bolt(k, t, b0, Vector((0, 0, 1)), level, s, length=1.2)
    k.torus("rack_band", 0.16, 0.015, P + Vector((0, 0, 0.6)), J, parent=t, segs=20, tube_segs=4)
    # the slewing head, the boom over the stock, the drop link and the pincer
    top = P + Vector((0, 0, H))
    k.cylinder("loader_head", 0.11, 0.14, top - Vector((0, 0, 0.04)), J, segs=18, parent=t)
    ym = CLAW_Y0 + 0.9
    zbolt = _z(ym) + 0.42
    el = Vector((0.34, ym, zbolt + 0.5))
    k.beam("loader_boom", top + Vector((0, 0, 0.06)), el, (0.08, 0.1), col if not col.startswith("timber") else F,
           parent=t, bevel=0.008)
    k.beam("loader_tie", P + Vector((0, 0, H - 0.5)), top.lerp(el, 0.6), (0.035, 0.035), F, parent=t, bevel=False)
    k.tube("loader_elbow", el + Vector((0, -0.07, 0)), el + Vector((0, 0.07, 0)), 0.06, J, parent=t, segs=14)
    wr = Vector((el.x, ym, zbolt + 0.17))
    k.beam("loader_drop", el, wr, (0.05, 0.06), F, parent=t, bevel=0.006)
    k.box("loader_wrist", (0.13, 0.18, 0.07), wr, J, parent=t, bevel=0.008)
    for sx in (-1, 1):                                   # the pincer jaws closed round the bolt
        k.beam("loader_jaw", wr + Vector((sx * 0.055, 0, -0.03)), Vector((el.x + sx * 0.03, ym, zbolt - 0.06)),
               (0.03, 0.09), F, parent=t, bevel=0.004)
    d = Vector((0, 1, math.tan(TILT))).normalized()
    tail = Vector((el.x, ym, zbolt)) - d * (BOLT_LEN * 0.5)
    _bolt(k, t, tail, d, level, s)


def _vsides(level):
    """Level skeins and arms: the prototype (1) has only the lower one, no upper arm sticking up
    like an antenna (user 2026-11-21)."""
    return (-1,) if level == 1 else (-1, 1)


def _capitulum(k, t, level, s):
    """The torsion frame: two skeins of rope in a tall frame, wide apart."""
    W = s["wood"]
    y = FRAME_Y
    zt, zb = _z(y) + 0.52, _z(y) - 0.44
    for z in (zt, zb):
        _beam(k, t, "frame_beam", (-0.88, y, z), (0.88, y, z), (0.22, 0.14), W)
    zc = _z(y)
    for x in (-0.82, 0.82):
        _beam(k, t, "stile", (x, y, zb - 0.07), (x, y, zt + 0.07), (0.12, 0.16), W)
    for x in (-0.24, 0.24):                               # centre stiles run on to hold the level skeins
        _beam(k, t, "stile", (x, y, zc - SKEIN_V - 0.2), (x, y, zc + (SKEIN_V + 0.2 if level > 1 else 0.1)),
              (0.12, 0.16), W)
    for sv in _vsides(level):
        zv = zc + sv * SKEIN_V
        k.cylinder("skein", 0.12, 0.36, (-0.18, y, zv), s["skein"], segs=16, rot=(0, math.pi / 2, 0), parent=t,
                   bevel=False)
        for i in range(3):
            k.torus("skein_coil", 0.122, 0.012, (-0.1 + i * 0.1, y, zv), s["skein"], rot=(0, math.pi / 2, 0),
                    parent=t, segs=16, tube_segs=5)
        for sx in (-1, 1):
            k.cylinder("washer", 0.15, 0.05, (sx * 0.3 - (0.05 if sx < 0 else 0), y, zv), s["fit"] if level > 1 else W,
                       segs=20, rot=(0, math.pi / 2, 0), parent=t)
            _beam(k, t, "washer_lever", (sx * 0.33, y, zv - 0.18), (sx * 0.33, y, zv + 0.18), (0.045, 0.045),
                  s["fit"] if level > 1 else "iron_forged")
        _beam(k, t, "cap_beam", (-0.3, y, zv + sv * 0.2), (0.3, y, zv + sv * 0.2), (0.14, 0.16), W)
    for sx in (-1, 1):
        x = sx * SKEIN_X
        k.cylinder("skein", 0.12, zt - zb - 0.06, (x, y, zb + 0.03), s["skein"], segs=16, parent=t, bevel=False)
        for i in range(6):
            k.torus("skein_coil", 0.122, 0.012, (x, y, zb + 0.1 + i * (zt - zb - 0.2) / 5), s["skein"],
                    parent=t, segs=16, tube_segs=5)
        for z, sg in ((zt + 0.07, 1), (zb - 0.07, -1)):
            k.cylinder("washer", 0.16, 0.05, (x, y, z - (0.05 if sg < 0 else 0)), s["fit"] if level > 1 else W,
                       segs=20, parent=t)
            _beam(k, t, "washer_lever", (x - 0.19, y, z + sg * 0.03), (x + 0.19, y, z + sg * 0.03), (0.045, 0.045),
                  s["fit"] if level > 1 else "iron_forged")
        if level > 1:
            for z in (zt, zb):
                k.box("corner_iron", (0.24, 0.03, 0.2), (sx * 0.82, y + 0.09, z), s["fit"], parent=t, bevel=0.004)
    if level >= 4:                                        # worm screws that twist the skeins tighter
        m = s["fit"]
        for sx in (-1, 1):
            x = sx * SKEIN_X
            for z in (zt + 0.12, zb - 0.17):
                c = Vector((x, y, z))
                k.cylinder("worm_wheel", 0.2, 0.05, c, m, segs=32, parent=t, bevel=0.003)
                for i in range(20):
                    a = 2 * math.pi * i / 20
                    d = Vector((math.cos(a), math.sin(a), 0))
                    k.box("tooth", (0.04, 0.025, 0.05), c + d * 0.215 + Vector((0, 0, 0.025)), m,
                          rot=(0, 0, a), parent=t, bevel=False)
                wy = y - 0.27                            # the worm runs across behind the wheel
                k.tube("worm", (x - 0.22, wy, z + 0.025), (x + 0.22, wy, z + 0.025), 0.045, "steel_worn" if level == 4
                       else "silver", parent=t, segs=10, bevel=False)
                for i in range(7):
                    k.torus("worm_thread", 0.05, 0.012, (x - 0.15 + i * 0.05, wy, z + 0.025), m,
                            rot=(0.25, math.pi / 2, 0), parent=t, segs=12, tube_segs=4)
                k.box("worm_key", (0.06, 0.06, 0.06), (x + sx * 0.25, wy, z + 0.025), m, parent=t, bevel=0.005)
    if s.get("shield"):                                   # front shield with the aimer's window
        sy = y + 0.13
        for x0, x1 in ((-0.95, -0.12), (0.12, 0.95)):
            k.box("shield", (x1 - x0, 0.03, zt - zb + 0.12), ((x0 + x1) / 2, sy, (zt + zb) / 2), s["shield"],
                  parent=t, bevel=0.006)
        k.box("shield", (0.24, 0.03, zt - zb - 0.62), (0, sy, zt - (zt - zb - 0.62) / 2 + 0.06), s["shield"],
              parent=t, bevel=0.006)
        k.box("shield_sill", (0.24, 0.03, 0.18), (0, sy, zb + 0.03), s["shield"], parent=t, bevel=0.006)
        rim = "bronze_old" if level == 4 else "gold_trim"
        for z in (zt + 0.06, zb - 0.06):
            k.box("shield_rim", (1.94, 0.045, 0.05), (0, sy + 0.01, z), rim, parent=t, bevel=0.004)
        for sx in (-1, 1):
            k.box("shield_rim", (0.05, 0.045, zt - zb + 0.12), (sx * 0.96, sy + 0.01, (zt + zb) / 2), rim, parent=t,
                  bevel=0.004)
            for z in (zt - 0.08, zb + 0.08):
                k.cylinder("shield_rivet", 0.03, 0.025, (sx * 0.85, sy + 0.025, z), rim, segs=8,
                           rot=(math.pi / 2, 0, 0), parent=t, bevel=False)
        if s.get("ornament"):                             # a gold sunburst on each wing of the shield
            for sx in (-1, 1):
                c = Vector((sx * 0.55, sy + 0.025, (zt + zb) / 2))
                k.cylinder("sun", 0.11, 0.02, c, "gold_trim", segs=24, rot=(math.pi / 2, 0, 0), parent=t)
                for i in range(12):
                    a = 2 * math.pi * i / 12
                    d = Vector((math.cos(a), 0, math.sin(a)))
                    k.beam("ray", c + d * 0.12, c + d * (0.22 if i % 2 else 0.28), (0.025, 0.012), "gold_trim",
                           parent=t, bevel=False, section_end=(0.006, 0.01))
    if s.get("ornament"):
        for x in (-0.82, 0.82):
            _ball(k, t, (x, y, zt + 0.2), 0.075, "gold_trim", subdiv=2)
        for x in (-0.3, 0.3):
            _ball(k, t, (x, y, zc + SKEIN_V + 0.36), 0.075, "gold_trim", subdiv=2)


def _sights(k, t, level, s):
    if not s.get("sight"):
        return
    fit = s["fit"]
    y = FRAME_Y + 0.45
    zt = _z(y) - 0.05
    # front sight: a post at the nose of the stock with a ring
    _beam(k, t, "sight_post", (0, y, zt), (0, y, zt + 0.3), (0.04, 0.04), fit)
    k.torus("sight_ring", 0.06, 0.012, (0, y, zt + 0.36), fit, rot=(math.pi / 2, 0, 0), parent=t, segs=16,
            tube_segs=5)
    if s.get("quadrant"):
        q = s["quadrant"]
        # range quadrant on the left of the stock, with a plumb line
        c = Vector((-0.22, -0.9, _z(-0.9) - 0.12))
        k.torus("quadrant_arc", 0.42, 0.018, c, q, rot=(0, math.pi / 2, 0), parent=t, segs=32, tube_segs=5)
        _beam(k, t, "quadrant_bar", c, c + Vector((0, 0, -0.42)), (0.03, 0.03), q)
        _beam(k, t, "quadrant_bar", c, c + Vector((0, -0.42, 0)), (0.03, 0.03), q)
        k.tube("plumb_line", c, c + Vector((0, -0.05, -0.36)), 0.004, "hemp", parent=t, segs=4, bevel=False)
        _ball(k, t, c + Vector((0, -0.05, -0.38)), 0.03, q, subdiv=2)
        # rear peep sight
        yr = -1.95
        _beam(k, t, "peep_post", (0, yr, _z(yr) + 0.05), (0, yr, _z(yr) + 0.45), (0.035, 0.035), fit)
        k.cylinder("peep", 0.05, 0.02, (0, yr, _z(yr) + 0.5), fit, segs=14, rot=(math.pi / 2, 0, 0), parent=t)


def _bolt(k, t, tail, d, level, s, length=BOLT_LEN):
    """A long bolt from its tail along d: a slim shaft, a long bodkin head and three vanes."""
    d = Vector(d).normalized()
    tail = Vector(tail)
    hl = (0.22, 0.32, 0.36, 0.38, 0.36)[level - 1]
    tip = tail + d * length
    k.tube("bolt_shaft", tail, tip - d * (hl - 0.04), 0.024, s["shaft"], parent=t, segs=8, bevel=False)
    rot = d.to_track_quat("Z", "Y").to_euler()
    k.cylinder("bolt_head", 0.04, hl, tip - d * hl, s["head"], segs=4, rot=rot, parent=t, radius_top=0.002,
               bevel=False)
    if level > 1:
        k.cylinder("bolt_socket", 0.032, 0.08, tip - d * (hl + 0.06), s["bolt"] or s["head"], segs=8, rot=rot,
                   parent=t, bevel=False)
    up = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
    side = d.cross(up).normalized()
    for i in range(3):
        a = 2 * math.pi * i / 3
        n = (side * math.cos(a) + d.cross(side) * math.sin(a)).normalized()
        k.beam("vane", tail + d * 0.05 + n * 0.045, tail + d * 0.38 + n * 0.04, (0.008, 0.08), s["fletch"],
               parent=t, bevel=False, section_end=(0.006, 0.055))


# -- the moving parts and the firing animation ----------------------------------------------
def _arm_dir(sx, sweep_deg):
    a = math.radians(sweep_deg)
    return Vector((sx * math.cos(a), -math.sin(a), 0.0))


def _tip(sx, sweep_deg, arm_l):
    return Vector((sx * SKEIN_X, FRAME_Y, _z(FRAME_Y))) + _arm_dir(sx, sweep_deg) * arm_l


def _vdir(sv, sweep_deg):
    a = math.radians(sweep_deg)
    return Vector((0.0, -math.sin(a), sv * math.cos(a)))


def _vtip(sv, sweep_deg, arm_v):
    return Vector((0, FRAME_Y, _z(FRAME_Y) + sv * SKEIN_V)) + _vdir(sv, sweep_deg) * arm_v


def _arm_parts(k, t, level, s, a0, d, L):
    W = s["arm"]
    parts = [k.beam("arm", a0 + d * 0.05, a0 + d * L, (0.14, 0.2), W, parent=t, bevel=0.01,
                    section_end=(0.08, 0.1)),
             k.box("arm_tip", (0.09, 0.09, 0.12), a0 + d * (L - 0.02), s["fit"] if level > 1 else "iron_forged",
                   parent=t, bevel=0.006)]
    if level > 1:
        for f in (0.35, 0.65):
            parts.append(k.beam("arm_band", a0 + d * (L * f), a0 + d * (L * f + 0.07), (0.15, 0.2), s["fit"],
                                parent=t, bevel=0.003))
    if s.get("ornament"):
        parts.append(_ball(k, t, a0 + d * (L + 0.06), 0.06, "gold_trim", subdiv=2))
    return parts


def _rig(k, t, level, s):
    W, L = s["arm"], s["arm_l"]
    zc = _z(FRAME_Y)
    arms = {}
    for sx in (-1, 1):
        piv = k.empty(f"arm_pivot_{'L' if sx < 0 else 'R'}", (sx * SKEIN_X, FRAME_Y, zc), parent=t)
        d = _arm_dir(sx, COCK_DEG)
        a0 = Vector((sx * SKEIN_X, FRAME_Y, zc))
        for o in _arm_parts(k, t, level, s, a0, d, L):
            _keep_world(o, piv)
        arms[sx] = piv
    varms = {}
    for sv in _vsides(level):                             # the upper and lower arms
        a0 = Vector((0, FRAME_Y, zc + sv * SKEIN_V))
        piv = k.empty(f"arm_pivot_{'D' if sv < 0 else 'U'}", a0, parent=t)
        for o in _arm_parts(k, t, level, s, a0, _vdir(sv, COCK_DEG), s["arm_v"]):
            _keep_world(o, piv)
        varms[sv] = piv
    slider = k.empty("slider", (0, 0, 0), parent=t)
    zs = _z(CLAW_Y0) + 0.06
    for o in (k.beam("slider_bar", (0, CLAW_Y0 - 0.45, zs - 0.03), (0, FRAME_Y + 0.45, _z(FRAME_Y + 0.45) + 0.03),
                     (0.16, 0.07), W, parent=t, bevel=0.006),
              k.box("claw", (0.11, 0.15, 0.13), (0, CLAW_Y0 - 0.05, zs + 0.07), s["fit"] if level > 1 else "iron_forged",
                    parent=t, bevel=0.01),
              k.tube("trigger", (0.07, CLAW_Y0 - 0.12, zs + 0.02), (0.16, CLAW_Y0 - 0.38, zs - 0.12), 0.02,
                     s["fit"] if level > 1 else "iron_forged", parent=t, segs=6, bevel=False)):
        _keep_world(o, slider)
    # handwheels on the winch axle
    axis = next(o for o in t.children if o.get("rig_name") == "wheels")
    y, z = axis.location.y, axis.location.z
    parts = [k.tube("winch_axle", (-0.45, y, z), (0.45, y, z), 0.05, W, parent=t, segs=12)]
    gears = []
    for sx in (-1, 1):
        x, wc, wp = sx * 0.4, Vector((sx * 0.4, y, z)), axis
        if level == 2:                                   # ratchet and pawl
            parts += _gear(k, t, (sx * 0.27, y, z), 0.17, 14, 0.05, s["fit"], saw=True)
            p0 = Vector((sx * 0.27, y + 0.36, z + 0.22))
            k.beam("pawl", p0, Vector((sx * 0.27, y + 0.1, z + 0.15)), (0.04, 0.035), s["fit"], parent=t, bevel=0.004)
        if level >= 3:                                   # reduction gear: the wheels move up onto a pinion
            ra = 0.3
            parts += _gear(k, t, (sx * 0.3, y, z), ra, 24, 0.05, s["fit"] if level > 3 else "iron_forged")
            c1 = Vector((sx * 0.3, y, z)) + Vector((0, -0.35, 0.94)).normalized() * (ra + 0.11)
            wp = k.empty("pinion", c1, parent=t)
            gears.append((wp, -ra / 0.1))
            for o in _gear(k, t, c1, 0.1, 9, 0.06, s["fit"] if level > 3 else "iron_forged"):
                _keep_world(o, wp)
            k.beam("bearing", Vector((sx * 0.21, c1.y, z - 0.2)), Vector((sx * 0.21, c1.y, c1.z + 0.05)),
                   (0.06, 0.08), W, parent=t, bevel=0.005)
            x = sx * 0.48
            wc = Vector((x, c1.y, c1.z))
            _keep_world(k.tube("pinion_axle", (sx * 0.2, c1.y, c1.z), wc, 0.03, s["fit"], parent=t, segs=8,
                               bevel=False), wp)
        rw = 0.34 if level < 3 else 0.28
        wheel = [k.torus("wheel_rim", rw, 0.035, wc, s["wheel"], rot=(0, math.pi / 2, 0), parent=t,
                         segs=28, tube_segs=6),
                 k.cylinder("wheel_hub", 0.08, 0.1, wc - Vector((0.05, 0, 0)), s["fit"] if level > 1 else W, segs=12,
                            rot=(0, math.pi / 2, 0), parent=t)]
        for i in range(6):
            a = 2 * math.pi * i / 6 + 0.3
            r = Vector((0, math.cos(a), math.sin(a)))
            wheel.append(k.beam("spoke", wc + r * 0.06, wc + r * (rw - 0.01), (0.035, 0.035),
                                W if level < 4 else s["wheel"], parent=t, bevel=False))
            if i % 2 == 0:                               # handles round the rim
                h = wc + r * rw
                wheel.append(k.tube("wheel_handle", h, h + Vector((sx * 0.14, 0, 0)), 0.02, W, parent=t, segs=6,
                                    bevel=False))
        if wp is axis:
            parts += wheel
        else:
            for o in wheel:
                _keep_world(o, wp)
    for o in parts:
        _keep_world(o, axis)
    # winch rope from the axle to the claw
    # the winch rope runs to the claw (posed per frame, it follows the slider)
    ropes = []
    claw0 = Vector((0, CLAW_Y0, zs + 0.1))
    if s.get("tackle"):                                   # block and tackle: four strands, four times the pull
        fb = Vector((0, -1.9, _z(-1.9) + 0.02))
        mb = claw0 + Vector((0, -0.32, -0.06))
        for c, nm in ((fb, "block_fixed"), (mb, "block_moving")):
            o = k.box(nm, (0.14, 0.12, 0.22), c, s["fit"], parent=t, bevel=0.02)
            sh = k.cylinder("sheave", 0.08, 0.16, c - Vector((0.08, 0, 0)), "silver", segs=16,
                            rot=(0, math.pi / 2, 0), parent=t)
            if nm == "block_moving":
                _keep_world(o, slider)
                _keep_world(sh, slider)
        k.tube("winch_rope", (0, y, z + 0.05), fb, 0.014, s["rope"], parent=t, segs=6, bevel=False)
        for dx, dz in ((-0.035, 0.06), (0.035, 0.06), (-0.035, -0.06), (0.035, -0.06)):
            o = k.cylinder("tackle_rope", 0.011, 1.0, (0, 0, 0), s["rope"], segs=5, parent=t, bevel=False)
            ropes.append((o, fb + Vector((dx, 0.06, dz)), mb - claw0 + Vector((dx, -0.06, dz))))
    else:
        o = k.cylinder("winch_rope", 0.014, 1.0, (0, 0, 0), s["rope"], segs=6, parent=t, bevel=False)
        ropes.append((o, Vector((0, y, z + 0.05)), Vector((0, -0.3, -0.08))))
    carrier = k.empty("bolt_carrier", (0, 0, 0), parent=t)
    before = set(bpy.data.objects)
    _bolt(k, t, (0, CLAW_Y0 - 0.02, zs + 0.09), (0, 1, math.tan(TILT)), level, s)
    for o in set(bpy.data.objects) - before:
        _keep_world(o, carrier)
    strings, vstrings = [], []
    for sx in (-1, 1):
        o = k.cylinder("string", 0.022, 1.0, (0, 0, 0), s["rope"], segs=6, parent=t, bevel=False)
        strings.append((sx, o))
        if sx in _vsides(level):
            o = k.cylinder("string", 0.022, 1.0, (0, 0, 0), s["rope"], segs=6, parent=t, bevel=False)
            vstrings.append((sx, o))
    _RIG.update(t=t, arms=arms, slider=slider, wheels=axis, carrier=carrier, strings=strings, zs=zs, arm_l=L,
                varms=varms, vstrings=vstrings, arm_v=s["arm_v"], zc=zc,
                ropes=ropes,
                gears=gears)
    set_fire_frame(0)


def _pose(f):
    if f == 0:
        return COCK_DEG, 0.0, True, 0.0, 0
    return FIRE[f - 1]


def _apply(sweep, slide, hooked, bolt, wheel_deg):
    for sx, piv in _RIG["arms"].items():
        piv.rotation_euler = (0, 0, sx * math.radians(sweep - COCK_DEG) * -1)
    for sv, piv in _RIG["varms"].items():
        piv.rotation_euler = (sv * math.radians(sweep - COCK_DEG), 0, 0)
    _RIG["slider"].location = (0, slide, slide * math.tan(TILT))
    _RIG["wheels"].rotation_euler = (math.radians(-wheel_deg), 0, 0)
    for p, ratio in _RIG["gears"]:
        p.rotation_euler = (math.radians(-wheel_deg * ratio), 0, 0)
    _RIG["carrier"].location = (0, bolt or 0.0, (bolt or 0.0) * math.tan(TILT))
    claw = Vector((0, CLAW_Y0 + slide, _RIG["zs"] + 0.1 + slide * math.tan(TILT)))
    for sx, o in _RIG["strings"]:
        tip = _tip(sx, sweep, _RIG["arm_l"])
        end = claw if hooked else Vector((0, tip.y, tip.z))
        d = end - tip
        o.location = tip
        o.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
        o.scale = (1, 1, max(d.length, 0.01))
    for sv, o in _RIG["vstrings"]:
        tip = _vtip(sv, sweep, _RIG["arm_v"])
        end = claw if hooked else Vector((0, tip.y, _RIG["zc"]))
        d = end - tip
        o.location = tip
        o.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
        o.scale = (1, 1, max(d.length, 0.01))
    for o, anchor, off in _RIG["ropes"]:
        d = claw + off - anchor
        o.location = anchor
        o.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
        o.scale = (1, 1, max(d.length, 0.01))


def key_fire_animation(scene):
    prefs = bpy.context.preferences.edit
    old = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = "LINEAR"
    for f in range(FIRE_FRAMES + 1):
        _apply(*_pose(f))
        for piv in list(_RIG["arms"].values()) + list(_RIG["varms"].values()):
            piv.keyframe_insert("rotation_euler", frame=f)
        for o, p in ((_RIG["slider"], "location"), (_RIG["wheels"], "rotation_euler"),
                     (_RIG["carrier"], "location")) + tuple((p, "rotation_euler") for p, _ in _RIG["gears"]):
            o.keyframe_insert(p, frame=f)
        for o in [o for _, o in _RIG["strings"] + _RIG["vstrings"]] + [r[0] for r in _RIG["ropes"]]:
            for p in ("location", "rotation_euler", "scale"):
                o.keyframe_insert(p, frame=f)
    prefs.keyframe_new_interpolation_type = old
    scene.frame_set(0)


def set_fire_frame(f, scene=None):
    sweep, slide, hooked, bolt, wheel_deg = _pose(f)
    if scene is not None and _RIG["slider"].animation_data is not None:
        scene.frame_set(f)
    else:
        _apply(sweep, slide, hooked, bolt, wheel_deg)
    for o in _RIG["carrier"].children:
        o.hide_render = bolt is None
    bpy.context.view_layer.update()


def build_round(k, parent, level):
    """The flying bolt of this level, centred on `parent`, pointing along +Y."""
    _bolt(k, parent, (0, -BOLT_LEN / 2, 0), (0, 1, 0), level, STYLE[level])
