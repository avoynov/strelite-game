"""Ракети (game id rockets): anti-air fireworks. A bundle of rockets raised to the sky on a
fork; it fires only at flyers, the rockets wobble up and burst. Front is local +Y.

Look per level (sketch v4, approved 2026-11-22):
  1  a few open paper rockets on bamboo sticks tied together with rope, resting in a raw
     timber fork; three logs and a ring of stones
  2  the same open bundle with bigger rockets; a stone drum with a tarred turntable
  3  a bigger bundle bound with chain inside an open iron cage (two bands, four riveted
     bars) on a planed oak fork with trunnions; an iron turntable on timber feet
  4  the cask: an olive steel cask full of tubes, every rocket standing proud of its
     mouth; a toothed elevation quadrant with a crank and an AA ring sight; a sandbag nest
  5  blackened steel and gold; two brass sound-locator horns and electric firing from a
     battery box; a marble octagon with a brass rail
Ammo pile: a wicker basket of stick rockets, a crate in straw, a leaning rack, stencilled
crates, a lacquered case of gilded rockets.

Returns (root, turret). The base is static; the fork and the bundle turn.
Firing animation: a short kick of the bundle and the next rocket gone from its place; it is
back from RELOAD_FROM. The flying rocket is the projectile (build_round).
"""
import math
import random

import bpy
from mathutils import Vector

from .. import materials_photoreal as mp
from .. import fort
from ..geo import Kit
from .trebuchet import _ball

LEVELS = (1, 2, 3, 4, 5)
FRAME_M = 8.0
TARGET_Z = 1.2
SPRITE_FRAME_M = 9.0
SWEEP_M = 2.0
FOOTPRINT_M = 3.0        # 2x2 tiles of 4 m
ROUND_DIRS = 32          # the flying rocket is drawn per heading
ROUND_FRAME_M = 2.0
EL = math.radians(50)    # the bundle looks up at the sky

STYLE = {
    1: dict(fork="timber_raw", fit="iron_forged", stick="bamboo", band="hemp"),
    2: dict(fork="timber_tarred", fit="iron_forged", stick="timber_raw", band="hemp"),
    3: dict(fork="timber_oak", fit="iron_black", stick="timber_raw", band="iron_black"),
    4: dict(fork="paint_olive", fit="steel_worn", cask="paint_olive", hoop="gunmetal", tube="gunmetal",
            body="paint_olive", cap="paint_red"),
    5: dict(fork="iron_black", fit="gold_trim", cask="iron_black", hoop="gold_trim", tube="gold_trim",
            body="iron_black", cap="gold_trim"),
}
BUNDLE = {1: (0.075, 0.85, 7), 2: (0.115, 1.15, 10), 3: (0.12, 1.25, 13)}   # rocket radius, length, count
PAPER = ["paper_red", "paper_ochre", "paper_cream", "paper_blue", "paper_red", "paper_green", "paper_ochre",
         "paper_cream", "paper_red", "paper_blue", "paper_green", "paper_ochre", "paper_red"]
CAPS = ["paper_red", "paper_ochre", "paper_blue", "paper_green"]
R_CASK = {4: 0.58, 5: 0.6}
DECK_Z = {1: 0.42, 2: 0.5, 3: 0.45, 4: 0.62, 5: 0.5}

FIRE = [(-0.07, False), (-0.05, False), (-0.03, False), (-0.015, False), (0.0, True), (0.0, True)]
FIRE_FRAMES = len(FIRE)
RELEASE_FRAME = 1
RELOAD_FROM = 5
FIRE_FPS = 12
LOOP = False
_RIG = {}

ROT_Y = (-math.pi / 2, 0, 0)         # Kit cylinder (+Z) turned to point along +Y
ROT_TY = (math.pi / 2, 0, 0)         # Kit torus (around Z) turned to ring the +Y axis


def build(style, level=1):
    k = Kit(style)
    s = STYLE[level]
    _RIG.clear()
    _RIG["next"] = []
    root = k.empty("rockets")
    zb = _base(k, root, level)
    _ammo(k, root, level, s)
    turret = k.empty("turret", (0, 0, 0), parent=root)
    turret["node"] = "turret"
    mp.set_reference(turret)
    zc = zb + {1: 0.85, 2: 0.95, 3: 1.0, 4: 0.95, 5: 0.95}[level]
    if level <= 3:
        rr, ln, n = BUNDLE[level]
        R = rr * (3.3 if level < 3 else 3.75)
        fx = R + 0.12
    else:
        R = R_CASK[level]
        fx = R + 0.16
    _fork(k, turret, level, s, zb, zc, fx)
    elev = k.empty("elevating", (0, 0, zc), parent=turret)
    elev["node"] = "elevating"
    _RIG["elev"] = elev
    if level <= 3:
        front = _bundle(k, elev, level, s, R, fx)
    else:
        front = _cask(k, elev, level, s, R, fx)
    m = k.empty("muzzle", (0, front, 0), parent=elev)
    m["marker"] = "muzzle"
    elev.rotation_euler = (EL, 0, 0)
    if level == 5:
        _battery(k, turret, zb, fx)
    set_fire_frame(0)
    return root, turret


def ground(level):
    from ..terrain import Patch
    return Patch(r_solid=FOOTPRINT_M, r_out=FOOTPRINT_M + 0.6, r_bare=2.4, seed=73, ragged=0.5)


# -- one rocket ----------------------------------------------------------------------------------
def _rocket(k, parent, tail, d, ln, r, body, cap, stick=None, stick_len=0.0):
    """A rocket from `tail` along unit `d`: paper body, cone nose, optional guide stick."""
    tail, d = Vector(tail), Vector(d).normalized()
    out = [k.tube("rocket_body", tail, tail + d * ln, r, body, parent=parent, segs=14, bevel=False)]
    out.append(k.tube("rocket_nose", tail + d * ln, tail + d * (ln + 0.08 + r * 1.7), r * 1.04, cap,
                      radius_end=0.004, parent=parent, segs=14, bevel=False))
    out.append(k.tube("rocket_band", tail + d * (ln * 0.12), tail + d * (ln * 0.17), r * 1.03, cap, parent=parent,
                      segs=14, bevel=False))
    if stick:
        side = d.cross(Vector((1, 0, 0)))
        side = side.normalized() if side.length > 1e-6 else Vector((0, 0, 1))
        s0 = tail + d * (ln * 0.35) - side * r * 1.1
        out.append(k.beam("rocket_stick", s0, s0 - d * stick_len, (0.022, 0.022), stick, parent=parent, bevel=False))
    return out


# -- static base ------------------------------------------------------------------------------
def _base(k, root, level):
    z = DECK_Z[level]
    if level == 1:                                        # three logs, a ring of stones, a pivot post
        for a in (90, 210, 330):
            r = math.radians(a)
            k.tube("foot_log", (0.15 * math.cos(r), 0.15 * math.sin(r), 0.12),
                   (1.25 * math.cos(r), 1.25 * math.sin(r), 0.1), 0.11, "log", parent=root, segs=12)
        rnd = random.Random(5)
        for i in range(10):
            a = 2 * math.pi * i / 10 + 0.15
            b = _ball(k, root, (0.82 * math.cos(a), 0.82 * math.sin(a), 0.04), 0.14, "stone", subdiv=2)
            b.scale = (rnd.uniform(1.0, 1.4), rnd.uniform(0.9, 1.2), rnd.uniform(0.5, 0.7))
            b.rotation_euler = (0, 0, rnd.uniform(0, 3))
        k.cylinder("pivot_post", 0.2, z, (0, 0, 0), "log", segs=14, parent=root)
        return z
    if level == 2:                                        # stone drum, tarred turntable
        k.cylinder("drum", 0.72, 0.4, (0, 0, 0), "stone_dressed", segs=28, parent=root)
        k.cylinder("turntable", 0.8, 0.1, (0, 0, 0.4), "timber_tarred", segs=32, parent=root)
        for i in range(6):
            a = math.pi * i / 6
            d = Vector((math.cos(a), math.sin(a), 0))
            k.box("plank_seam", (1.58, 0.015, 0.012), Vector((0, 0, 0.5)), "timber_oak", rot=(0, 0, a), parent=root,
                  bevel=False)
        return z
    if level == 3:                                        # iron turntable on a timber frame and feet
        for sx in (-1, 1):
            for sy in (-1, 1):
                k.box("foot", (0.4, 0.4, 0.3), (sx * 0.75, sy * 0.75, 0.15), "timber_oak", parent=root, bevel=0.01)
        for sy in (-1, 1):
            k.box("frame_beam", (1.9, 0.22, 0.18), (0, sy * 0.75, 0.21), "timber_oak", parent=root, bevel=0.01)
            k.box("frame_beam", (0.22, 1.9, 0.18), (sy * 0.75, 0, 0.21), "timber_oak", parent=root, bevel=0.01)
        k.cylinder("turntable", 0.78, 0.15, (0, 0, 0.3), "iron_forged", segs=36, parent=root)
        for i in range(20):
            a = 2 * math.pi * i / 20
            k.cylinder("rivet", 0.025, 0.02, (0.7 * math.cos(a), 0.7 * math.sin(a), 0.45), "iron_forged", segs=6,
                       parent=root, bevel=False)
        return z
    if level == 4:                                        # sandbag nest, steel pedestal, traverse handwheel
        fort.sandbag_wall(k, root, 1.05, [(0, 360)], courses=3, seed=7, double_until=1)
        k.cylinder("pedestal", 0.3, 0.55, (0, 0, 0), "paint_olive_worn", segs=24, parent=root)
        k.cylinder("pedestal_cap", 0.5, 0.07, (0, 0, 0.55), "paint_olive_worn", segs=32, parent=root)
        hw = Vector((0.55, 0.2, 0.42))
        k.tube("handwheel_shaft", (0.25, 0.1, 0.42), hw, 0.02, "steel_worn", parent=root, segs=8, bevel=False)
        k.torus("handwheel", 0.16, 0.018, hw, "iron_black", rot=(0, math.pi / 2, 0), parent=root, segs=24,
                tube_segs=6)
        for i in range(4):
            a = math.pi * i / 4
            k.beam("handwheel_spoke", hw + Vector((0, 0.16 * math.cos(a), 0.16 * math.sin(a))),
                   hw - Vector((0, 0.16 * math.cos(a), 0.16 * math.sin(a))), (0.015, 0.015), "iron_black",
                   parent=root, bevel=False)
        return z
    # 5: marble octagon, brass rail, gilded azimuth ring
    k.cylinder("plinth", 1.1, 0.4, (0, 0, 0), "stone_pale", segs=8, parent=root)
    k.torus("azimuth_ring", 0.85, 0.035, (0, 0, 0.41), "gold_trim", parent=root, segs=64, tube_segs=6)
    for i in range(24):
        a = 2 * math.pi * i / 24
        d = Vector((math.cos(a), math.sin(a), 0))
        k.box("tick", (0.1, 0.025, 0.02), d * 0.96 + Vector((0, 0, 0.41)), "gold_trim", rot=(0, 0, a), parent=root,
              bevel=False)
    rail = []
    for i in range(8):
        a = math.pi / 8 + i * math.pi / 4
        p = Vector((1.0 * math.cos(a), 1.0 * math.sin(a), 0.4))
        if i in (2, 3):                                   # an opening at the back
            continue
        k.tube("rail_post", p, p + Vector((0, 0, 0.42)), 0.022, "brass", parent=root, segs=8)
        rail.append(p + Vector((0, 0, 0.42)))
    for a_, b_ in zip(rail[2:] + rail[:2], (rail[2:] + rail[:2])[1:]):
        k.tube("rail", a_, b_, 0.02, "brass", parent=root, segs=8)
    k.cylinder("turntable", 0.55, 0.1, (0, 0, 0.4), "gold_trim", segs=40, parent=root)
    return z


# -- fork ----------------------------------------------------------------------------------------
def _fork(k, t, level, s, zb, zc, fx):
    k.box("yoke", (2 * fx + 0.24, 0.4, 0.12), (0, 0, zb + 0.06), s["fork"], parent=t, bevel=0.015)
    for sx in (-1, 1):
        k.box("fork_arm", (0.15, 0.26, zc - zb + 0.12), (sx * (fx + 0.05), 0, zb + (zc - zb + 0.12) / 2), s["fork"],
              parent=t, bevel=0.015)
        k.cylinder("trunnion_cap", 0.1, 0.1, (sx * (fx + 0.13), 0, zc), s["fit"], segs=16, rot=(0, math.pi / 2, 0),
                   parent=t)


# -- L1-3: the open bundle -----------------------------------------------------------------------
def _bundle(k, e, level, s, R, fx):
    rr, ln, n = BUNDLE[level]
    offs = [(0.0, 0.0)] + [(math.cos(a), math.sin(a)) for a in [math.pi / 6 + i * math.pi / 3 for i in range(6)]]
    offs += [(1.73 * math.cos(a), 1.73 * math.sin(a)) for a in [i * math.pi / 3 for i in range(6)]]
    offs = offs[:n]
    stick_len = ln * (1.05 if level == 1 else 0.85)
    for i, (x, z) in enumerate(offs):
        tail = Vector((x * rr * 2.1, -ln / 2, z * rr * 2.1))
        parts = _rocket(k, e, tail, (0, 1, 0), ln, rr, PAPER[i % len(PAPER)], CAPS[(i + 1) % 4], s["stick"],
                        stick_len)
        if i == 0:
            _RIG["next"] += parts
    if level <= 2:                                        # rope lashings, a cradle under the bundle
        for f in (0.25, 0.7):
            k.torus("lashing", R, 0.025, (0, ln * (f - 0.5), 0), "hemp", rot=ROT_TY, parent=e, segs=32, tube_segs=6)
            k.torus("lashing", R, 0.025, (0, ln * (f - 0.5) + 0.05, 0), "hemp", rot=ROT_TY, parent=e, segs=32,
                    tube_segs=6)
        for sx in (-1, 1):
            k.box("cradle_cheek", (0.08, 0.6, 0.14), (sx * (R + 0.04), 0, -R * 0.35), s["fork"], parent=e, bevel=0.01)
        k.box("cradle_bar", (2 * R + 0.16, 0.12, 0.1), (0, -0.2, -R - 0.03), s["fork"], parent=e, bevel=0.01)
        k.box("cradle_bar", (2 * R + 0.16, 0.12, 0.1), (0, 0.2, -R - 0.03), s["fork"], parent=e, bevel=0.01)
        k.tube("pin", (-fx - 0.1, 0, 0), (fx + 0.1, 0, 0), 0.035, "iron_forged", parent=e, segs=10, bevel=False)
        return ln / 2 + 0.2
    # L3: chain wrapped twice round the bundle, an open iron cage, trunnion pins
    for f in (0.3, 0.68):
        _chain(k, e, ln * (f - 0.5), rr * 3.35)
    Rc = R
    for y in (-ln * 0.42, ln * 0.35):
        k.torus("cage_band", Rc, 0.032, (0, y, 0), "iron_black", rot=ROT_TY, parent=e, segs=40, tube_segs=6)
    for i in range(4):
        a = math.pi / 4 + i * math.pi / 2
        d = Vector((math.cos(a), 0, math.sin(a)))
        k.beam("cage_bar", d * (Rc + 0.005) + Vector((0, -ln * 0.45, 0)), d * (Rc + 0.005) + Vector((0, ln * 0.38, 0)),
               (0.07, 0.02), "iron_black", parent=e, bevel=False)
        for y in (-ln * 0.3, 0.0, ln * 0.22):
            k.cylinder("rivet", 0.016, 0.02, d * (Rc + 0.016) + Vector((0, y, 0)), "iron_black", segs=6,
                       parent=e, bevel=False)
    for sx in (-1, 1):
        k.cylinder("cage_trunnion", 0.07, fx - Rc + 0.12, (sx * Rc, 0, 0), "iron_black", segs=12,
                   rot=(0, sx * math.pi / 2, 0), parent=e)
    return ln / 2 + 0.25


def _chain(k, e, y, r):
    n = int(2 * math.pi * r / 0.055)
    for i in range(n):
        a = 2 * math.pi * i / n
        p = Vector((r * math.cos(a), y, r * math.sin(a)))
        if i % 2:
            axis = Vector((0, 1, 0))
        else:
            axis = Vector((math.cos(a), 0, math.sin(a)))
        rot = Vector((0, 0, 1)).rotation_difference(axis).to_euler()
        k.torus("chain_link", 0.032, 0.008, p, "iron_black", rot=rot, parent=e, segs=10, tube_segs=4)


# -- L4-5: the cask ------------------------------------------------------------------------------
def _cask(k, e, level, s, R, fx):
    half = 0.72
    prof = []
    for i in range(9):
        f = i / 8
        prof.append((-half + 2 * half * f, R * (0.86 + 0.14 * math.sin(math.pi * f))))
    prof += [(half, R * 0.8), (half - 0.03, R * 0.8)]
    k.lathe("cask", prof, s["cask"], segs=40, parent=e)
    hoops = (0.08, 0.92) if level == 4 else (0.1, 0.5, 0.9)
    for f in hoops:
        k.torus("hoop", R * (0.86 + 0.14 * math.sin(math.pi * f)) + 0.012, 0.024, (0, -half + 2 * half * f, 0),
                s["hoop"], rot=ROT_TY, parent=e, segs=44, tube_segs=6)
    Rf = R * 0.8
    k.cylinder("face", Rf, 0.02, (0, half - 0.03, 0), "iron_black", segs=40, rot=ROT_Y, parent=e, bevel=False)
    rt = 0.075 if level == 4 else 0.072
    tubes = []
    for j in range(-4, 5):
        for i in range(-5, 6):
            x = (i + 0.5 * (j % 2)) * rt * 2.15
            z = j * rt * 1.86
            if x * x + z * z <= (Rf - rt * 1.05) ** 2:
                tubes.append((x, z))
    for n_, (x, z) in enumerate(tubes):
        k.cylinder("tube_mouth", rt, 0.05, (x, half - 0.02, z), s["tube"], segs=12, rot=ROT_Y, parent=e, bevel=False)
        stand = 0.2 + 0.06 * ((n_ * 5) % 3)
        parts = _rocket(k, e, (x, half - 0.25, z), (0, 1, 0), stand + 0.25, rt * 0.62, s["body"], s["cap"])
        if (x, z) == min(tubes, key=lambda q: q[0] ** 2 + q[1] ** 2):
            _RIG["next"] += parts
    k.torus("face_rim", Rf, 0.03, (0, half, 0), s["hoop"], rot=ROT_TY, parent=e, segs=40, tube_segs=6)
    for sx in (-1, 1):
        k.cylinder("cask_trunnion", 0.08, fx - R + 0.14, (sx * (R - 0.02), 0, 0), s["fit"], segs=14,
                   rot=(0, sx * math.pi / 2, 0), parent=e)
    # toothed elevation quadrant with a pinion and a crank on the near side
    qx = fx + 0.15
    teeth = []
    for i in range(13):
        a = math.radians(200 + i * 10)
        teeth.append(Vector((qx, 0.55 * math.cos(a), 0.55 * math.sin(a))))
    for a_, b_ in zip(teeth, teeth[1:]):
        k.beam("quadrant", a_, b_, (0.04, 0.05), s["fit"] if level == 5 else "steel_worn", parent=e, bevel=False)
    for p in teeth:
        k.beam("quadrant_tooth", p, p * 1.0 + Vector((0, p.y * 0.12, p.z * 0.12)), (0.035, 0.03), "steel_worn",
               parent=e, bevel=False)
    k.beam("quadrant_spoke", Vector((qx, 0, 0)), teeth[0], (0.04, 0.04), "steel_worn", parent=e, bevel=False)
    k.beam("quadrant_spoke", Vector((qx, 0, 0)), teeth[-1], (0.04, 0.04), "steel_worn", parent=e, bevel=False)
    pin = Vector((qx + 0.02, 0.66 * math.cos(math.radians(250)), 0.66 * math.sin(math.radians(250))))
    k.cylinder("pinion", 0.09, 0.05, pin, "steel_worn", segs=14, rot=(0, math.pi / 2, 0), parent=e)
    k.beam("crank_arm", pin + Vector((0.06, 0, 0)), pin + Vector((0.06, 0.14, -0.12)), (0.03, 0.03), "iron_black",
           parent=e, bevel=False)
    k.tube("crank_handle", pin + Vector((0.06, 0.14, -0.12)), pin + Vector((0.2, 0.14, -0.12)), 0.022, "timber_oak",
           parent=e, segs=8, bevel=False)
    if level == 4:                                        # AA ring sight on a stalk off the far side
        st0 = Vector((-R - 0.02, 0.1, R * 0.55))
        sc = Vector((-R - 0.18, 0.45, R * 0.55 + 0.22))
        k.tube("sight_stalk", st0, sc - Vector((0, 0.02, 0)), 0.015, "iron_black", parent=e, segs=6, bevel=False)
        for rr_ in (0.08, 0.16, 0.24):
            k.torus("ring_sight", rr_, 0.006, sc, "iron_black", rot=ROT_TY, parent=e, segs=28, tube_segs=4)
        k.beam("sight_cross", sc - Vector((0.24, 0, 0)), sc + Vector((0.24, 0, 0)), (0.008, 0.008), "iron_black",
               parent=e, bevel=False)
        k.beam("sight_cross", sc - Vector((0, 0, 0.24)), sc + Vector((0, 0, 0.24)), (0.008, 0.008), "iron_black",
               parent=e, bevel=False)
        k.tube("sight_bead", Vector((-R * 0.95, half - 0.05, R * 0.3)), Vector((-R * 0.95, half - 0.05, R * 0.3 + 0.12)),
               0.01, "iron_black", parent=e, segs=6, bevel=False)
    if level == 5:                                        # paired brass sound-locator horns
        for sx in (-1, 1):
            h0 = Vector((sx * (R + 0.6), -0.4, 0.05))
            k.beam("horn_arm", Vector((sx * (fx + 0.12), 0, 0)), h0 + Vector((0, 0.05, 0)), (0.05, 0.05), "iron_black",
                   parent=e, bevel=False)
            prof = [(0.0, 0.05), (0.2, 0.07), (0.38, 0.12), (0.5, 0.2), (0.55, 0.25), (0.55, 0.23), (0.48, 0.17),
                    (0.3, 0.08), (0.05, 0.035)]
            k.lathe("horn", prof, "brass", segs=28, loc=h0, parent=e)
            k.torus("horn_rim", 0.25, 0.015, h0 + Vector((0, 0.55, 0)), "gold_trim", rot=ROT_TY, parent=e, segs=28,
                    tube_segs=4)
        k.hose("firing_cable", [(0.1, -half - 0.02, -0.1), (0.3, -half - 0.25, -0.35), (0.5, -half - 0.1, -0.7)],
               0.018, "rubber", parent=e)
    return half + 0.45


def _battery(k, t, zb, fx):
    p = Vector((0.0, -0.75, zb + 0.12))
    k.box("battery_box", (0.45, 0.35, 0.32), p + Vector((0, 0, 0.16)), "iron_black", parent=t, bevel=0.015)
    for i in range(2):
        k.cylinder("terminal", 0.035, 0.06, p + Vector((-0.1 + 0.2 * i, 0, 0.32)), "gold_trim", segs=10, parent=t,
                   bevel=False)
    k.box("battery_shelf", (0.6, 0.5, 0.06), p + Vector((0, 0, -0.03)), "iron_black", parent=t, bevel=0.01)
    k.beam("battery_strut", p + Vector((0, 0.2, 0)), Vector((0, -0.18, zb + 0.06)), (0.06, 0.06), "iron_black",
           parent=t, bevel=False)


# -- ammo pile --------------------------------------------------------------------------------
def _ammo(k, root, level, s):
    g = Vector((1.55, 1.2, 0))
    up = Vector((0, 0, 1))
    if level == 1:                                        # wicker basket of stick rockets
        k.cylinder("basket", 0.3, 0.42, g, "wicker", segs=20, parent=root, radius_top=0.33)
        for i in range(6):
            a = 2 * math.pi * i / 6
            d = Vector((0.12 * math.cos(a), 0.12 * math.sin(a), 1)).normalized()
            _rocket(k, root, g + Vector((0.12 * math.cos(a), 0.12 * math.sin(a), 0.62)), d, 0.32, 0.04,
                    PAPER[i], CAPS[i % 4], "bamboo", 0.55)
    elif level == 2:                                      # crate of rockets in straw
        k.box("rocket_crate", (0.85, 0.6, 0.36), g + Vector((0, 0, 0.18)), "timber_raw", parent=root, bevel=0.01)
        k.box("straw", (0.78, 0.52, 0.05), g + Vector((0, 0, 0.36)), "hemp", parent=root, bevel=0.01)
        for i in range(4):
            _rocket(k, root, g + Vector((-0.3, -0.18 + 0.12 * i, 0.43)), (1, 0.1, 0.05), 0.4, 0.055, PAPER[i],
                    CAPS[i % 4])
    elif level == 3:                                      # A-frame rack, rockets leaning
        for y in (-0.3, 0.3):
            k.beam("rack_leg", g + Vector((-0.3, y, 0)), g + Vector((0, y, 0.8)), (0.06, 0.06), "timber_oak",
                   parent=root, bevel=False)
            k.beam("rack_leg", g + Vector((0.3, y, 0)), g + Vector((0, y, 0.8)), (0.06, 0.06), "timber_oak",
                   parent=root, bevel=False)
        k.beam("rack_top", g + Vector((0, -0.36, 0.8)), g + Vector((0, 0.36, 0.8)), (0.06, 0.06), "timber_oak",
               parent=root, bevel=False)
        for i in range(5):
            _rocket(k, root, g + Vector((-0.42, -0.25 + 0.12 * i, 0.03)), (0.38, 0, 1), 0.6, 0.06, PAPER[i],
                    "copper")
    elif level == 4:                                      # stencilled crates, one open with rockets
        k.box("crate", (0.75, 0.45, 0.32), g + Vector((0, 0, 0.16)), "paint_crate", parent=root, bevel=0.01)
        k.box("crate", (0.75, 0.45, 0.32), g + Vector((0.05, 0.05, 0.48)), "paint_crate", parent=root, bevel=0.01)
        k.box("crate_stripe", (0.6, 0.005, 0.05), g + Vector((0.05, 0.28, 0.55)), "paint_white", parent=root,
              bevel=False)
        o = g + Vector((-0.2, -0.75, 0))
        k.box("crate_open", (0.75, 0.45, 0.25), o + Vector((0, 0, 0.125)), "paint_crate", parent=root, bevel=0.01)
        for i in range(4):
            _rocket(k, root, o + Vector((-0.28 + 0.17 * i, -0.2, 0.27)), (0.05, 1, 0.08), 0.32, 0.045, "paint_olive",
                    "paint_red")
    else:                                                 # lacquered case, gilded rockets standing
        k.box("rocket_case", (0.85, 0.5, 0.3), g + Vector((0, 0, 0.15)), "timber_varnish", parent=root, bevel=0.015)
        k.box("case_trim", (0.89, 0.54, 0.03), g + Vector((0, 0, 0.315)), "gold_trim", parent=root, bevel=0.005)
        for i in range(5):
            _rocket(k, root, g + Vector((-0.3 + 0.15 * i, 0.05 * (i % 2), 0.33)), up, 0.45, 0.045, "iron_black",
                    "gold_trim")


# -- round and animation ---------------------------------------------------------------------------
def build_round(k, parent, level):
    """The flying rocket of this level, centred on `parent`, pointing along +Y."""
    s = STYLE[level]
    if level <= 3:
        rr, ln, _ = BUNDLE[level]
        _rocket(k, parent, (0, -ln / 2, 0), (0, 1, 0), ln, rr, PAPER[0], CAPS[1], s["stick"],
                ln * (1.05 if level == 1 else 0.85))
    else:
        _rocket(k, parent, (0, -0.25, 0), (0, 1, 0), 0.5, 0.045, s["body"], s["cap"])


def key_fire_animation(scene):
    prefs = bpy.context.preferences.edit
    old = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = "CONSTANT"
    for f in range(FIRE_FRAMES + 1):
        set_fire_frame(f)
        _RIG["elev"].keyframe_insert("location", frame=f)
        for o in _RIG["next"]:
            o.keyframe_insert("hide_render", frame=f)
    prefs.keyframe_new_interpolation_type = old
    scene.frame_set(0)


def set_fire_frame(f, scene=None):
    e = _RIG["elev"]
    if scene is not None and e.animation_data is not None:
        scene.frame_set(f)
    else:
        kick, shown = (0.0, True) if f == 0 else FIRE[f - 1]
        z0 = e.location.z
        d = Vector((0, math.cos(EL), math.sin(EL)))
        e.location = Vector((0, 0, _RIG.setdefault("z0", z0))) + d * kick
        for o in _RIG["next"]:
            o.hide_render = not shown
    bpy.context.view_layer.update()
