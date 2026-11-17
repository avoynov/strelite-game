"""Infantry squad: five riflemen advancing in a loose wedge, about 2.4 m across
(bg: „Пехота“). PLACEHOLDER enemy for style В. Grey field uniforms, steel
helmets, packs; one man carries a rocket launcher.

The squad faces local +Y; render_sprites.py --enemy turns the whole group.
Returns (root, root).
"""
import math
import random

from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit

SPRITE_FRAME_M = 5.6
LENGTH_M = 2.4
RADIUS_M = 1.2
SQUAD = [  # x, y, yaw (deg), stride (+1 left foot forward), height scale, rocket launcher
    (0.0, 0.85, 0, 1, 1.0, False),
    (-0.95, 0.15, 8, -1, 0.97, False),
    (0.9, 0.25, -6, -1, 1.02, True),
    (-0.5, -0.85, 4, 1, 1.0, False),
    (0.55, -0.75, -10, 1, 0.96, False),
]


def build(style, level=1):
    k = Kit(style)
    root = k.empty("infantry")
    mp.set_reference(root)
    rnd = random.Random(5)
    for i, (x, y, yaw, stride, s, rpg) in enumerate(SQUAD):
        man = k.empty(f"soldier{i}", (x, y, 0), parent=root)
        man.rotation_euler = (0, 0, math.radians(yaw))
        man.scale = (s, s, s)
        _soldier(k, man, stride, rpg, rnd)
    return root, root


def _ellipsoid(k, name, centre, rx, ry, rz, mat, parent, segs=16):
    prof = [(-1.0 * math.cos(math.pi * i / 8), math.sin(math.pi * i / 8)) for i in range(9)]
    o = k.lathe(name, prof, mat, segs=segs, loc=centre, rot=(math.pi / 2, 0, 0), parent=parent)
    o.scale = (rx, rz, ry)               # lathe axis (local Y) stands upright
    return o


def _limb(k, name, a, b, r0, r1, mat, parent):
    k.tube(name, a, b, r0, mat, radius_end=r1, parent=parent, segs=10, bevel=False)
    _ellipsoid(k, name + "_joint", b, r1, r1, r1, mat, parent, segs=10)


def _soldier(k, m, stride, rpg, rnd):
    U, SK = "uniform", "skin"
    f = 0.2 * stride
    # legs, mid-stride
    for side in (-1, 1):
        fwd = f * (-side)                               # +: this foot is in front
        hip = Vector((side * 0.1, 0.0, 0.93))
        knee = Vector((side * 0.11, 0.06 + fwd * 0.55, 0.5))
        ankle = Vector((side * 0.11, fwd * 1.15, 0.1 + max(0.0, -fwd) * 0.12))
        _limb(k, "thigh", hip, knee, 0.085, 0.065, U, m)
        _limb(k, "shin", knee, ankle, 0.062, 0.05, U, m)
        boot = k.box("boot", (0.11, 0.27, 0.1), ankle + Vector((0, 0.06, -0.04)), "boot", parent=m,
                     rot=(-0.25 if fwd < 0 else 0.0, 0, 0), bevel=0.015)
        boot.location.z = max(boot.location.z, 0.05)
    # body leaning forward a little
    k.box("pelvis", (0.34, 0.21, 0.2), (0, 0.0, 0.96), U, parent=m, bevel=0.04)
    k.beam("torso", (0, 0.0, 0.98), (0, 0.07, 1.46), (0.36, 0.22), U, section_end=(0.42, 0.24), parent=m,
           bevel=0.05)
    k.box("belt", (0.38, 0.24, 0.06), (0, 0.01, 1.02), "webbing", parent=m, bevel=False)
    for sx in (-1, 1):
        k.box("pouch", (0.1, 0.06, 0.1), (sx * 0.1, 0.13, 1.06), "webbing", parent=m, bevel=0.01)
        k.tube("strap", (sx * 0.12, 0.13, 1.05), (sx * 0.12, 0.12, 1.45), 0.012, "webbing", parent=m,
               segs=6, bevel=False)
    k.box("pack", (0.3, 0.17, 0.36), (0, -0.17, 1.28), "canvas", parent=m, bevel=0.04)
    k.box("bedroll", (0.36, 0.11, 0.11), (0, -0.19, 1.5), "canvas", parent=m, bevel=0.03)
    k.tube("entrenching_tool", (0.13, -0.24, 1.12), (0.13, -0.24, 1.36), 0.025, "wood", parent=m, segs=6)
    # head and helmet
    k.tube("neck", (0, 0.07, 1.46), (0, 0.08, 1.55), 0.05, SK, parent=m, segs=10, bevel=False)
    _ellipsoid(k, "head", (0, 0.09, 1.63), 0.085, 0.1, 0.11, SK, m)
    helm = [(0.0, 0.16), (0.012, 0.165), (0.03, 0.14), (0.07, 0.13), (0.12, 0.1), (0.16, 0.05), (0.175, 0.0)]
    k.lathe("helmet", helm, "paint_enemy", segs=24, loc=(0, 0.08, 1.63), rot=(math.pi / 2, 0, 0), parent=m)
    # parallel-world faction: brass spike and an oxblood band on the helmet, a brass gorget
    k.cylinder("helm_spike", 0.022, 0.09, (0, 0.08, 1.785), "brass", segs=10, radius_top=0.004, parent=m,
               bevel=False)
    k.torus("helm_band", 0.168, 0.014, (0, 0.08, 1.665), "paint_faction_red", parent=m, segs=24, tube_segs=5)
    k.box("gorget", (0.16, 0.02, 0.08), (0, 0.2, 1.38), "brass", rot=(-0.25, 0, 0), parent=m, bevel=0.005)
    # arms carrying the rifle at the ready
    sh_r, sh_l = Vector((0.22, 0.06, 1.42)), Vector((-0.22, 0.06, 1.42))
    hand_r, hand_l = Vector((0.1, 0.32, 1.13)), Vector((-0.06, 0.55, 1.22))
    el_r, el_l = Vector((0.27, 0.12, 1.15)), Vector((-0.22, 0.32, 1.17))
    _limb(k, "upper_arm", sh_r, el_r, 0.06, 0.05, U, m)
    _limb(k, "forearm", el_r, hand_r, 0.05, 0.04, U, m)
    _limb(k, "upper_arm", sh_l, el_l, 0.06, 0.05, U, m)
    _limb(k, "forearm", el_l, hand_l, 0.05, 0.04, U, m)
    _ellipsoid(k, "hand", hand_r, 0.045, 0.05, 0.04, SK, m, segs=10)
    _ellipsoid(k, "hand", hand_l, 0.045, 0.05, 0.04, SK, m, segs=10)
    # rifle: stock at the hip, muzzle forward and a little up
    butt, grip, muzzle = Vector((0.13, 0.02, 1.05)), Vector((0.08, 0.36, 1.14)), Vector((-0.08, 1.02, 1.3))
    k.beam("stock", butt, grip, (0.05, 0.11), "wood", section_end=(0.045, 0.07), parent=m, bevel=False)
    k.beam("receiver", grip, grip.lerp(muzzle, 0.45), (0.05, 0.08), "gunmetal", parent=m, bevel=False)
    k.beam("handguard", grip.lerp(muzzle, 0.3), grip.lerp(muzzle, 0.75), (0.055, 0.06), "wood", parent=m,
           bevel=False)
    k.tube("barrel", grip.lerp(muzzle, 0.7), muzzle, 0.013, "gunmetal", parent=m, segs=8, bevel=False)
    k.box("magazine", (0.04, 0.09, 0.2), grip.lerp(muzzle, 0.32) + Vector((0, 0, -0.1)), "gunmetal",
          rot=(0.35, 0, 0), parent=m, bevel=False)
    if rpg:                                             # launcher slung across the back
        k.tube("launcher", (0.28, -0.28, 0.95), (-0.25, -0.24, 1.75), 0.045, "paint_enemy_worn", parent=m,
               segs=12)
        k.cylinder("warhead", 0.07, 0.24, (-0.25, -0.24, 1.75), "paint_enemy", segs=14,
                   rot=(0.05, -0.58, 0), parent=m, radius_top=0.02)
