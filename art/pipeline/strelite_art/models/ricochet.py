"""Рикошетен топ (game id ricochet): throws heavy discs flat out of a slot so they skip from
enemy to enemy. Ground only, small range, a big slow hit. A tall pedestal narrowing upward; on
top a turning housing with a flat slot mouth (+Y), two throwing wheels that spin against each
other (as in a clay-pigeon trap or Wallis' backspin drum), a stack of discs behind.
Thracian look (user 2026-11-22): bronze, silver and gold, running spirals and torque rings; the
discs are made like Thracian phalerae (a boss in the middle, a ring round it).

Look per level (sketch v2):
  1  raw timber housing on a log crib; the wheels worked by a hand crank and a leather belt;
     clay discs
  2  tarred timber with bronze spiral plaques; a tall gravity magazine of discs over the back;
     bronze discs
  3  bronze housing on cut-rock masonry; a mainspring barrel on the side; iron discs
  4  bronze and silver on dark slate ashlar with a bronze band of spirals; a small steam engine behind;
     silver phalerae
  5  gold on white stone with gold bands and medallions; a flyball governor on top; gold phalerae
Ammo pile: clay discs, a crate of bronze discs, a rack of iron discs, a coal bin and silver
phalerae, a lacquered chest of gold phalerae.

Returns (root, turret). The pedestal is static; the housing turns. Front is local +Y.
Firing animation: the wheels spin, the disc in the mouth shoots out, a new one drops in.
"""
import math

import bpy
from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit
from .trebuchet import _ball

LEVELS = (1, 2, 3, 4, 5)
FRAME_M = 12.0
TARGET_Z = 2.2
SPRITE_FRAME_M = 13.0
SWEEP_M = 1.9
FOOTPRINT_M = 5.6        # 3x3 tiles of 4 m

PH = 2.7                 # pedestal height
W0, W1 = 3.3, 1.75       # pedestal width at the foot and at the top
SLOPE = math.atan((W0 - W1) / 2 / PH)

STYLE = {
    1: dict(box="timber_raw", fit="iron_forged", orn="leather", disc="clay", wheel="timber_raw"),
    2: dict(box="timber_tarred", fit="bronze_old", orn="bronze_old", disc="bronze_old", wheel="timber_tarred"),
    3: dict(box="bronze_old", fit="iron_black", orn="copper", disc="iron_forged", wheel="iron_black"),
    4: dict(box="bronze_old", fit="silver", orn="silver", disc="silver", wheel="iron_black"),
    5: dict(box="gold_trim", fit="silver", orn="silver", disc="gold_trim", wheel="silver"),
}

HB = (1.8, 1.35, 0.7)    # housing size
HY = 0.1                 # housing centre, y
FIRE = [(0.6, 0.15), (1.3, 0.9), (2.0, None), (2.6, None), (3.0, -0.4), (3.2, 0.0)]   # wheel turn, disc y
FIRE_FRAMES = len(FIRE)
RELEASE_FRAME = 2
RELOAD_FROM = 5
FIRE_FPS = 16
LOOP = False
_RIG = {}


def build(style, level=1):
    k = Kit(style)
    s = STYLE[level]
    _RIG.clear()
    root = k.empty("ricochet")
    _pedestal(k, root, level)
    _ammo(k, root, level, s)
    turret = k.empty("turret", (0, 0, 0), parent=root)
    turret["node"] = "turret"
    mp.set_reference(turret)
    _thrower(k, turret, level, s)
    m = k.empty("muzzle", (0, HY + HB[1] / 2 + 0.05, PH + 0.1 + HB[2] / 2), parent=turret)
    m["marker"] = "muzzle"
    set_fire_frame(0)
    return root, turret


def ground(level):
    from ..terrain import Patch
    return Patch(r_solid=FOOTPRINT_M - 1.6, r_out=FOOTPRINT_M - 0.8, r_bare=3.0, seed=71, ragged=0.5)


# -- ornament helpers ------------------------------------------------------------------------------
def _spiral(k, parent, r, mat, turns=2.3, wire=None, name="spiral"):
    """A flat spiral in the parent's XZ plane (a plaque facing -Y... +Y), as a wire."""
    n = int(turns * 14)
    pts = []
    for i in range(n + 1):
        t = turns * 2 * math.pi * i / n
        rr = r * (0.12 + 0.88 * i / n)
        pts.append((rr * math.cos(t), 0.0, rr * math.sin(t)))
    return k.hose(name, pts, wire or max(0.008, r * 0.08), mat, parent=parent)


def _face_plaques(k, root, z, half, mat, r, disc_mat=None):
    """On each of the four sloped faces at height z: a spiral (on a round plaque if disc_mat)."""
    for i in range(4):
        yaw = math.pi / 2 * i
        e = k.empty("face", (0, 0, 0), parent=root)
        e.rotation_euler = (0, 0, yaw)
        p = k.empty("plaque", (0, half + 0.02, z), parent=e)
        p.rotation_euler = (SLOPE, 0, 0)
        if disc_mat:
            k.cylinder("medallion", r * 1.3, 0.04, (0, -0.02, 0), disc_mat, segs=28, rot=(-math.pi / 2, 0, 0),
                       parent=p)
            _spiral(k, p, r, mat).location = (0, 0.03, 0)
        else:
            _spiral(k, p, r, mat)


def _w(z):
    return W0 + (W1 - W0) * z / PH


def _frustum(k, root, name, z0, z1, mat, grow=0.0, bevel=True):
    r0 = (_w(z0) / 2 + grow) * math.sqrt(2)
    r1 = (_w(z1) / 2 + grow) * math.sqrt(2)
    return k.cylinder(name, r0, z1 - z0, (0, 0, z0), mat, segs=4, radius_top=r1, parent=root, bevel=bevel)


# -- static pedestal -------------------------------------------------------------------------------
def _pedestal(k, root, level):
    if level == 1:                                   # log crib: logs laid crosswise, ends sticking out
        _frustum(k, root, "crib_core", 0, PH, "timber_raw", grow=-0.12)
        n = 11
        for i in range(n):
            z = PH * (i + 0.5) / n
            h = _w(z) / 2
            for sgn in (-1, 1):
                if i % 2 == 0:
                    k.tube("crib_log", (-h - 0.12, sgn * (h - 0.1), z), (h + 0.12, sgn * (h - 0.1), z), 0.12, "log",
                           parent=root, segs=12)
                else:
                    k.tube("crib_log", (sgn * (h - 0.1), -h - 0.12, z), (sgn * (h - 0.1), h + 0.12, z), 0.12, "log",
                           parent=root, segs=12)
        return
    if level == 2:                                   # tarred timber frame with braces and bronze plaques
        _frustum(k, root, "pedestal", 0, PH, "timber_tarred")
        for z in (0.06, PH / 2, PH - 0.06):
            _frustum(k, root, "frame_band", z - 0.06, z + 0.06, "timber_tarred", grow=0.05, bevel=0.01)
        for i in range(4):
            e = k.empty("face", (0, 0, 0), parent=root)
            e.rotation_euler = (0, 0, math.pi / 2 * i)
            for a, b in (((-1, 0.1), (1, PH / 2 - 0.1)), ((1, 0.1), (-1, PH / 2 - 0.1)),
                         ((-1, PH / 2 + 0.1), (1, PH - 0.1)), ((1, PH / 2 + 0.1), (-1, PH - 0.1))):
                za, zb = a[1], b[1]
                pa = (a[0] * (_w(za) / 2 - 0.08), _w(za) / 2 + 0.04, za)
                pb = (b[0] * (_w(zb) / 2 - 0.08), _w(zb) / 2 + 0.04, zb)
                k.beam("brace", pa, pb, (0.1, 0.08), "timber_tarred", parent=e)
        _face_plaques(k, root, PH * 0.5, _w(PH * 0.5) / 2 + 0.05, "bronze_old", 0.16, disc_mat="bronze_old")
        return
    if level == 3:                                   # cut-rock masonry: big courses, a little uneven
        n = 5
        for i in range(n):
            z0, z1 = PH * i / n, PH * (i + 1) / n
            c = _frustum(k, root, "course", z0, z1, "stone", grow=0.03 * ((i * 7) % 3 - 1))
            c.rotation_euler = (0, 0, math.radians((i * 5) % 7 - 3))
        return
    if level == 4:                                   # ashlar with a bronze band of running spirals
        n = 7
        for i in range(n):
            _frustum(k, root, "course", PH * i / n, PH * (i + 1) / n, "slate", grow=0.012 * (i % 2))
        zb = PH * 0.62
        _frustum(k, root, "spiral_band", zb - 0.17, zb + 0.17, "bronze_old", grow=0.035, bevel=0.01)
        for i in range(4):
            e = k.empty("face", (0, 0, 0), parent=root)
            e.rotation_euler = (0, 0, math.pi / 2 * i)
            for j in range(-2, 3):
                p = k.empty("plaque", (j * _w(zb) / 5.5, _w(zb) / 2 + 0.06, zb), parent=e)
                p.rotation_euler = (SLOPE, 0, 0)
                _spiral(k, p, 0.12, "silver", wire=0.012)
        return
    # 5: white stone, gold bands, gold medallions with spirals
    _frustum(k, root, "pedestal", 0, PH, "stone_pale")
    for z in (0.15, PH * 0.55, PH - 0.1):
        _frustum(k, root, "gold_band", z - 0.06, z + 0.06, "gold_trim", grow=0.03, bevel=0.01)
    _face_plaques(k, root, PH * 0.3, _w(PH * 0.3) / 2 + 0.02, "silver", 0.22, disc_mat="gold_trim")


# -- the thrower (turns) ----------------------------------------------------------------------------
def _phalera(k, parent, loc, r, mat, rot=(0, 0, 0)):
    """A disc made like a Thracian phalera: a flat disc, a raised ring, a boss in the middle."""
    e = k.empty("phalera", loc, parent=parent)
    e.rotation_euler = rot
    k.cylinder("disc", r, r * 0.16, (0, 0, -r * 0.08), mat, segs=32, parent=e)
    k.torus("disc_ring", r * 0.62, r * 0.05, (0, 0, r * 0.08), mat, parent=e, segs=28, tube_segs=6)
    b = _ball(k, e, (0, 0, r * 0.07), r * 0.22, mat, subdiv=2)
    b.scale = (1, 1, 0.55)
    return e


def _thrower(k, t, level, s):
    z0 = PH + 0.1
    k.cylinder("turntable", 0.82, 0.1, (0, 0, PH), s["fit"], segs=40, parent=t)
    hx, hy, hz = HB
    k.box("housing", HB, (0, HY, z0 + hz / 2), s["box"], parent=t, bevel=0.02)
    for sx in (-1, 1):                               # corner straps
        for sy in (-1, 1):
            k.box("strap", (0.06, 0.06, hz + 0.02), (sx * (hx / 2 + 0.01), HY + sy * (hy / 2 + 0.01), z0 + hz / 2),
                  s["fit"], parent=t, bevel=False)
    yf = HY + hy / 2
    k.box("mouth", (1.35, 0.03, 0.2), (0, yf + 0.006, z0 + hz / 2), "bore", parent=t, bevel=False)
    for dz in (-1, 1):
        k.box("mouth_lip", (1.5, 0.06, 0.06), (0, yf + 0.02, z0 + hz / 2 + dz * 0.13), s["fit"], parent=t, bevel=False)
    d = _phalera(k, t, (0, yf - 0.1, z0 + hz / 2), 0.3, s["disc"])   # the disc in the mouth
    _RIG["disc"] = d
    _RIG["disc_y"] = d.location.y
    _RIG["wheels"] = []
    for sx in (-1, 1):                               # two throwing wheels, through the open top
        w = k.empty("wheel", (sx * 0.43, HY + 0.15, z0 + hz - 0.04), parent=t)
        _RIG["wheels"].append((w, sx))
        k.cylinder("wheel_body", 0.38, 0.12, (0, 0, 0), s["wheel"], segs=32, parent=w)
        k.torus("wheel_tyre", 0.38, 0.04, (0, 0, 0.06), "leather", parent=w, segs=32, tube_segs=6)
        for i in range(3):                           # spokes show the spin
            a = 2 * math.pi * i / 3
            k.box("wheel_spoke", (0.6, 0.05, 0.02), (0.15 * math.cos(a), 0.15 * math.sin(a), 0.13), s["fit"],
                  rot=(0, 0, a), parent=w, bevel=False)
        k.cylinder("wheel_hub", 0.07, 0.06, (0, 0, 0.12), s["fit"], segs=14, parent=w)
    if level >= 2:                                   # spirals on the housing sides
        for sx in (-1, 1):
            e = k.empty("side", (sx * (hx / 2 + 0.03), HY, z0 + hz / 2), parent=t)
            e.rotation_euler = (0, 0, -sx * math.pi / 2)
            _spiral(k, e, 0.2, s["orn"])
    if level >= 4:                                   # torque rings at the top corners
        for sx in (-1, 1):
            for sy in (-1, 1):
                k.torus("torque", 0.09, 0.022, (sx * hx / 2, HY + sy * hy / 2, z0 + hz + 0.02), s["orn"], parent=t,
                        segs=20, tube_segs=6)
    if level != 2:                                   # stack of discs behind on a post
        st = Vector((0, HY - hy / 2 - 0.42, z0))
        k.cylinder("stack_post", 0.05, 0.75, st, s["fit"], segs=10, parent=t)
        for i in range(7 if level < 5 else 8):
            _phalera(k, t, st + Vector((0, 0, 0.06 + 0.085 * i)), 0.3, s["disc"])
    _mechanism(k, t, level, s, z0)


def _mechanism(k, t, level, s, z0):
    hx, hy, hz = HB
    if level == 1:                                   # hand crank and a leather belt to the wheels
        p = Vector((hx / 2 + 0.2, HY - 0.15, z0 + 0.38))
        k.cylinder("pulley", 0.28, 0.08, p, "timber_raw", segs=24, rot=(0, math.pi / 2, 0), parent=t)
        k.tube("crank_axle", p - Vector((0.2, 0, 0)), p + Vector((0.14, 0, 0)), 0.035, s["fit"], parent=t, segs=10)
        k.beam("crank_arm", p + Vector((0.14, 0, 0)), p + Vector((0.14, 0.0, 0.32)), (0.05, 0.05), s["fit"], parent=t)
        k.tube("crank_handle", p + Vector((0.14, 0, 0.32)), p + Vector((0.4, 0, 0.32)), 0.035, "timber_raw",
               parent=t, segs=10)
        k.box("crank_bracket", (0.2, 0.1, 0.4), (hx / 2 + 0.1, HY - 0.15, z0 + 0.2), "timber_raw", parent=t)
        top = Vector((0.43, HY + 0.15, z0 + hz + 0.02))
        k.hose("belt", [p + Vector((0.04, 0, 0.28)), (hx / 2 + 0.1, HY, z0 + hz + 0.1), top + Vector((0.3, 0, 0))],
               0.03, "leather", parent=t)
    elif level == 2:                                 # tall gravity magazine over the back
        st = Vector((0, HY - hy / 2 + 0.3, z0 + hz))
        for i in range(14):
            _phalera(k, t, st + Vector((0, 0, 0.04 + 0.075 * i)), 0.3, s["disc"])
        for a in (0.6, 2.5, 4.3):
            q = st + Vector((0.36 * math.cos(a), 0.36 * math.sin(a), 0))
            k.tube("magazine_rod", q, q + Vector((0, 0, 1.15)), 0.025, "bronze_old", parent=t, segs=8)
        for dz in (0.0, 1.15):
            k.torus("magazine_ring", 0.36, 0.025, st + Vector((0, 0, dz)), "bronze_old", parent=t, segs=28,
                    tube_segs=6)
        e = k.empty("cap", st + Vector((0, 0.37, 1.0)), parent=t)
        _spiral(k, e, 0.12, "bronze_old")
    elif level == 3:                                 # mainspring barrel on the side, with a ratchet
        p = Vector((hx / 2 + 0.02, HY - 0.2, z0 + 0.42))
        k.cylinder("spring_barrel", 0.42, 0.32, p, "iron_black", segs=36, rot=(0, math.pi / 2, 0), parent=t)
        k.torus("barrel_rim", 0.42, 0.03, p + Vector((0.32, 0, 0)), "copper", rot=(0, math.pi / 2, 0), parent=t,
                segs=36, tube_segs=6)
        e = k.empty("spring_face", p + Vector((0.34, 0, 0)), parent=t)
        e.rotation_euler = (0, 0, -math.pi / 2)
        _spiral(k, e, 0.34, "copper", turns=3.2, wire=0.012)
        k.beam("ratchet_lever", p + Vector((0.36, 0, 0)), p + Vector((0.42, -0.35, -0.3)), (0.05, 0.05),
               "iron_black", parent=t)
    elif level == 4:                                 # small steam engine at the back
        b = Vector((0.62, HY - hy / 2 - 0.45, z0))
        k.cylinder("boiler", 0.34, 1.1, b, "copper", segs=28, parent=t)
        for dz in (0.2, 0.55, 0.9):
            k.torus("boiler_band", 0.345, 0.025, b + Vector((0, 0, dz)), "silver", parent=t, segs=28, tube_segs=6)
        k.cylinder("chimney", 0.07, 0.75, b + Vector((0, 0, 1.1)), "iron_black", segs=12, parent=t)
        k.cylinder("chimney_cap", 0.12, 0.06, b + Vector((0, 0, 1.85)), "iron_black", segs=12, parent=t)
        k.cylinder("steam_cyl", 0.1, 0.4, b + Vector((-0.2, 0.32, 0.55)), "silver", segs=16, rot=(-math.pi / 2, 0, 0),
                   parent=t)
        k.tube("piston_rod", b + Vector((-0.2, 0.72, 0.55)), Vector((0.43, HY - 0.2, z0 + hz - 0.05)), 0.025,
               "silver", parent=t, segs=8)
        k.tube("steam_pipe", b + Vector((-0.25, 0.1, 1.0)), b + Vector((-0.2, 0.32, 0.65)), 0.03, "copper", parent=t,
               segs=8)
    else:                                            # flyball governor on top, gilded
        g = Vector((0, HY - 0.25, z0 + hz))
        k.cylinder("gov_base", 0.14, 0.08, g, "gold_trim", segs=20, parent=t)
        k.tube("gov_spindle", g, g + Vector((0, 0, 0.95)), 0.03, "gold_trim", parent=t, segs=10)
        for sx in (-1, 1):
            arm = g + Vector((sx * 0.32, 0, 0.5))
            k.tube("gov_arm", g + Vector((0, 0, 0.9)), arm, 0.018, "gold_trim", parent=t, segs=8)
            k.tube("gov_link", g + Vector((0, 0, 0.35)), arm + Vector((-sx * 0.06, 0, -0.05)), 0.014, "gold_trim",
                   parent=t, segs=8)
            _ball(k, t, arm, 0.12, "silver", subdiv=3)
        _ball(k, t, g + Vector((0, 0, 0.98)), 0.06, "gold_trim", subdiv=2)


# -- ammo pile ------------------------------------------------------------------------------------
def _ammo(k, root, level, s):
    g = Vector((2.55, 1.9, 0))
    if level == 1:                                   # leaning stack of clay discs
        for i in range(5):
            _phalera(k, root, g + Vector((0.03 * i, 0, 0.05 + 0.05 * i)), 0.3, "clay")
    elif level == 2:                                 # crate of bronze discs
        k.box("crate", (0.85, 0.7, 0.4), g + Vector((0, 0, 0.2)), "timber_tarred", parent=root, bevel=0.01)
        for i in range(2):
            _phalera(k, root, g + Vector((-0.18 + 0.36 * i, 0, 0.44)), 0.24, "bronze_old")
    elif level == 3:                                 # iron discs standing in a rack
        k.box("rack", (1.2, 0.4, 0.12), g + Vector((0, 0, 0.06)), "timber_oak", parent=root, bevel=0.01)
        for i in range(5):
            _phalera(k, root, g + Vector((-0.44 + 0.22 * i, 0, 0.4)), 0.28, "iron_forged",
                     rot=(0, math.pi / 2, 0))
    elif level == 4:                                 # coal bin and silver phalerae
        k.box("coal_bin", (0.8, 0.65, 0.35), g + Vector((0, 0, 0.175)), "iron_black", parent=root, bevel=0.01)
        for i in range(9):
            b = _ball(k, root, g + Vector((-0.25 + 0.06 * i, 0.08 * ((i * 3) % 4 - 1.5), 0.36)), 0.07, "slate",
                      subdiv=1)
        h = g + Vector((-0.85, 0.5, 0))
        for i in range(4):
            _phalera(k, root, h + Vector((0, 0, 0.05 + 0.06 * i)), 0.26, "silver")
    else:                                            # lacquered chest of gold phalerae
        k.box("chest", (1.0, 0.7, 0.34), g + Vector((0, 0, 0.17)), "timber_varnish", parent=root, bevel=0.015)
        k.box("chest_trim", (1.04, 0.74, 0.04), g + Vector((0, 0, 0.355)), "gold_trim", parent=root, bevel=0.005)
        for i in range(3):
            _phalera(k, root, g + Vector((-0.3 + 0.3 * i, 0, 0.42)), 0.14, "gold_trim")


# -- round and animation -----------------------------------------------------------------------------
def build_round(k, parent, level):
    """The disc of this level, flat, centred on `parent`."""
    _phalera(k, parent, (0, 0, 0), 0.3, STYLE[level]["disc"])


def key_fire_animation(scene):
    prefs = bpy.context.preferences.edit
    old = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = "LINEAR"
    for f in range(FIRE_FRAMES + 1):
        set_fire_frame(f)
        for w, _ in _RIG["wheels"]:
            w.keyframe_insert("rotation_euler", frame=f)
        _RIG["disc"].keyframe_insert("location", frame=f)
        _RIG["disc"].keyframe_insert("scale", frame=f)
    prefs.keyframe_new_interpolation_type = old
    scene.frame_set(0)


def set_fire_frame(f, scene=None):
    if scene is not None and _RIG["disc"].animation_data is not None:
        scene.frame_set(f)
    else:
        turn, dy = (0.0, 0.0) if f == 0 else FIRE[f - 1]
        for w, sx in _RIG["wheels"]:                 # they turn against each other
            w.rotation_euler = (0, 0, sx * turn * 2 * math.pi)
        d = _RIG["disc"]
        if dy is None:
            d.scale = (0.001, 0.001, 0.001)
        else:
            d.scale = (1, 1, 1)
            d.location.y = _RIG["disc_y"] + dy
    bpy.context.view_layer.update()
