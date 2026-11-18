"""Infantry squad of the Iron Concord (bg: „Пехота“): five riflemen advancing at a
combat jog in a loose wedge, about 2.4 m across. Built to the guns' standard
(SOP "Human figures"): skinned bodies on a real skeleton (strelite_art.human),
faces, gloved hands closed on the rifle, full field gear, and a running cycle.

Real sizes: men 1.70 to 1.86 m; rifle 1.15 m (a long bolt-action of the
1900s-1940s kind, 4 kg); pack 0.30 x 0.14 x 0.32 m; helmet bowl 0.25 m.

What makes them unmistakable at game zoom: five upright figures, slate tunics, a
crested steel helmet with an oxblood band and brass goggles, rifles held forward at
the low ready, rolled blankets on their packs, and the NCO's oxblood pennant.

Faction kit: slate uniform (the Concord's grey), oxblood scarf and helmet band,
brass gorget, crest, buttons, goggles and rifle bands, faction emblem on the left
sleeve and on the NCO's pennant.

Movement: a 12-frame running cycle driven by distance (MOVE_CYCLE_M metres per
loop, so feet stay planted at any game speed). Each man runs with his own phase,
so the squad never marches in step. The squad faces local +Y; render_sprites.py
--enemy turns the whole group.
"""
import math
import random

from mathutils import Quaternion, Vector

from .. import human as hu
from .. import materials_photoreal as mp
from ..geo import Kit
from . import faction

SPRITE_FRAME_M = 5.6
LENGTH_M = 2.4
RADIUS_M = 1.2
MOVE_FRAMES = 12
MOVE_KIND = "walk"
MOVE_CYCLE_M = 2.6            # metres per cycle: the stance foot moves back 0.22 m a frame (tools/figure_test.py --gait)
GAIT = "run"

SQUAD = [  # x, y, yaw deg, height m, phase, skin, face, role
    (0.0, 0.85, 0, 1.80, 0.00, "skin", dict(nose=1.1), "nco"),
    (-0.95, 0.15, 6, 1.74, 0.55, "skin_fair", dict(jaw=1.08), "rifle"),
    (0.9, 0.25, -5, 1.84, 0.27, "skin_olive", dict(nose=1.2, brow=1.3), "rifle"),
    (-0.5, -0.85, 3, 1.77, 0.80, "skin_dark", dict(jaw=1.05), "rifle"),
    (0.55, -0.75, -8, 1.71, 0.40, "skin", dict(nose=0.9), "rifle"),
]
_RIGS = []          # (rig, phase) per man, set by build()


def build(style, level=1, only=None):
    k = Kit(style)
    root = k.empty("infantry")
    mp.set_reference(root)
    _RIGS.clear()
    rnd = random.Random(5)
    for i, (x, y, yaw, h, ph, skin, face, role) in enumerate(SQUAD):
        if only is not None and i not in only:
            continue
        man = k.empty(f"soldier{i}", (x, y, 0) if only is None else (0, 0, 0), parent=root)
        man.rotation_euler = (0, 0, math.radians(yaw))
        rig = soldier(k, man, h, skin, face, role, rnd)
        _RIGS.append((rig, ph))
    set_move_frame(0)
    return root, root


def set_move_frame(f, scene=None):
    for rig, ph in _RIGS:
        hu.pose_gait(rig, (f / MOVE_FRAMES + ph) % 1.0, GAIT)


# ---------------------------------------------------------------------------
def _ik(shoulder, wrist, a, b, pole):
    """Elbow of a two-bone arm from shoulder to wrist (bone lengths a, b) bending toward pole."""
    d = wrist - shoulder
    L = min(d.length, (a + b) * 0.999)
    u = d.normalized()
    x = (a * a - b * b + L * L) / (2 * L)
    h = math.sqrt(max(a * a - x * x, 0.0))
    p = Vector(pole) - u * Vector(pole).dot(u)
    return shoulder + u * x + p.normalized() * h


def soldier(k, man, height, skin, face, role, rnd):
    rig = hu.Rig(k, man, height=height)
    s = rig.s
    hu.torso(k, rig, man)
    hu.legs(k, rig, man)
    hu.neck_head(k, rig, man, skin=skin, face=dict(face, moustache=(role == "nco")))
    _hair(k, rig, man)

    # rifle at the low ready: grip by the right hip, muzzle forward, a little left and down
    grip = rig.p((0.11, 0.23, 1.14))
    fwd = Vector((-0.13, 1.0, 0.07)).normalized()
    right = fwd.cross(hu.Z).normalized()
    up = right.cross(fwd)
    rifle_q = fwd.to_track_quat("Y", "Z")
    rf = k.empty("rifle", grip, parent=man)
    rf.rotation_euler = rifle_q.to_euler()
    rf.scale = (s, s, s)
    _rifle(k, rf)
    rig.attach(rf, "chest")

    # hands on the rifle, arms solved from the shoulders
    hs = 0.09 * s
    bar_r = grip - up * 0.035 * s
    ga_r, pd_r = -up, fwd
    fw_r = (pd_r - ga_r * pd_r.dot(ga_r)).normalized()
    wrist_r = bar_r - fw_r * hs + ga_r.cross(fw_r) * 0.025 * s
    bar_l = grip + fwd * 0.31 * s - up * 0.005 * s
    ga_l, pd_l = fwd, right
    fw_l = (pd_l - ga_l * pd_l.dot(ga_l)).normalized()
    wrist_l = bar_l - fw_l * hs + ga_l.cross(fw_l) * 0.025 * s
    for sd, sx, wr, ga, pd, pole in (("R", 1, wrist_r, ga_r, pd_r, (1.0, -0.6, -0.5)),
                                     ("L", -1, wrist_l, ga_l, pd_l, (-1.0, -0.2, -0.9))):
        sh = rig.p((sx * 0.185, 0.0, 1.425))
        el = _ik(sh, wr, 0.285 * s, 0.255 * s, pole)
        hu.arm(k, rig, man, sh / s, el / s, wr / s)
        hu.grip_hand(k, rig, man, wr / s, ga, pd, mat="glove")
        _epaulette(k, rig, man, sx, role)
        if sd == "L":                                # faction emblem on the outside of the left sleeve
            out = (el - sh).cross(Vector((0, 0, 1))).normalized()
            if out.x > 0:
                out = -out
            faction.emblem(k, man, sh.lerp(el, 0.3) + out * 0.064 * s, out, r=0.03 * s)
            for o in [c for c in man.children if c.name.startswith("emblem")]:
                rig.attach(o, "chest")
    _helmet(k, rig, man)
    _gear(k, rig, man, role, rnd)
    return rig


def _hair(k, rig, man):
    s = rig.s
    # cropped hair showing under the helmet at the back and sides
    h = hu.loft(k, "hair", [dict(c=(0, -0.01 * s, 1.64 * s), rx=0.07 * s, ry=0.085 * s),
                            dict(c=(0, -0.005 * s, 1.70 * s), rx=0.081 * s, ry=0.098 * s),
                            dict(c=(0, -0.003 * s, 1.74 * s), rx=0.082 * s, ry=0.1 * s)],
                "hair", man, segs=16, caps=(True, True), subsurf=1)
    h.scale = (1, 1, 1)
    for v in h.data.vertices:                    # keep it off the face
        if v.co.y > 0.05 * s:
            v.co.y = 0.05 * s + (v.co.y - 0.05 * s) * 0.2
            v.co.z = max(v.co.z, 1.70 * s)
    rig.attach(h, "head")


def _epaulette(k, rig, man, sx, role):
    s = rig.s
    mat = "brass" if role == "nco" else "uniform"
    e = k.box("shoulder_strap", (0.06 * s, 0.13 * s, 0.012 * s), (sx * 0.15 * s, 0.0, 1.475 * s), mat,
              rot=(0, sx * 0.42, 0), parent=man, bevel=0.004)
    rig.attach(e, "chest")
    b = k.cylinder("button", 0.009 * s, 0.006 * s, (sx * 0.12 * s, 0.0, 1.49 * s), "brass", segs=10,
                   rot=(0, sx * 0.42, 0), parent=man, bevel=False)
    rig.attach(b, "chest")


def _helmet(k, rig, man):
    """Crested steel helmet of the Concord: deep bowl, front and back peak, brass comb,
    oxblood band, brass goggles pushed up on the front, leather chin strap."""
    s = rig.s
    c = Vector((0, 0.008, 1.735)) * s
    g = k.empty("helmet", c, parent=man)
    g.scale = (0.93 * s, 0.93 * s * 1.12, 0.93 * s)
    bowl = [(0.0, 0.123), (0.035, 0.124), (0.07, 0.115), (0.1, 0.095), (0.125, 0.06), (0.138, 0.025),
            (0.141, 0.0)]
    k.lathe("helmet_bowl", bowl, "paint_enemy_worn", segs=32, rot=(math.pi / 2, 0, 0), parent=g)
    k.cylinder("helmet_brim", 0.158, 0.012, (0, 0, -0.004), "paint_enemy_worn", segs=36, radius_top=0.122,
               parent=g, bevel=0.003)
    k.torus("helm_band", 0.124, 0.011, (0, 0, 0.022), "paint_faction_red", parent=g, segs=32, tube_segs=6)
    crest = [(-0.11, 0.06), (-0.06, 0.125), (0.0, 0.152), (0.06, 0.13), (0.11, 0.07), (0.1, 0.05), (0.0, 0.135),
             (-0.1, 0.045)]
    k.plate("helm_crest", crest, 0.012, 0.0, "brass", parent=g, bevel=0.002)
    for sx in (-1, 1):                               # goggles on the front of the bowl
        k.cylinder("goggle", 0.022, 0.018, (sx * 0.032, 0.112, 0.055), "brass", segs=16,
                   rot=(-math.pi / 2 + 0.35, 0, 0), parent=g, bevel=0.002)
        k.cylinder("goggle_lens", 0.016, 0.004, (sx * 0.032, 0.129, 0.061), "glass", segs=16,
                   rot=(-math.pi / 2 + 0.35, 0, 0), parent=g, bevel=False)
        k.box("chin_strap", (0.008, 0.016, 0.1), (sx * 0.112, 0.02, -0.06), "leather", rot=(0.15, 0, 0),
              parent=g, bevel=False)
    k.torus("goggle_strap", 0.126, 0.006, (0, 0, 0.05), "leather", rot=(0.06, 0, 0), parent=g, segs=32,
            tube_segs=5)
    rig.attach(g, "head")


def _rifle(k, rf):
    """Bolt-action rifle, origin at the pistol grip, barrel along +Y, built at 1:1."""
    stock = [(-0.38, -0.112), (-0.30, -0.095), (-0.08, -0.042), (-0.025, -0.075), (0.02, -0.07), (0.04, -0.03),
             (0.44, -0.024), (0.465, -0.01), (0.465, 0.01), (0.04, 0.016), (-0.04, 0.008), (-0.12, 0.016),
             (-0.38, 0.03)]
    k.plate("stock", stock, 0.04, 0.0, "wood", parent=rf, bevel=0.006)
    k.box("butt_plate", (0.042, 0.008, 0.145), (0, -0.384, -0.041), "brass", rot=(-0.06, 0, 0), parent=rf,
          bevel=0.002)
    k.box("receiver", (0.03, 0.2, 0.034), (0, 0.13, 0.032), "gunmetal", parent=rf, bevel=0.003)
    k.box("magazine", (0.028, 0.075, 0.04), (0, 0.15, -0.04), "gunmetal", parent=rf, bevel=0.003)
    k.torus("trigger_guard", 0.022, 0.004, (0, 0.06, -0.04), "brass", rot=(0, math.pi / 2, 0), parent=rf,
            segs=16, tube_segs=5)
    k.tube("bolt", (0.0, 0.05, 0.046), (0.0, 0.2, 0.046), 0.008, "steel_worn", parent=rf, segs=10, bevel=False)
    k.tube("bolt_handle", (0.006, 0.06, 0.046), (0.05, 0.05, 0.025), 0.005, "steel_worn", parent=rf, segs=8,
           bevel=False)
    k.cylinder("bolt_knob", 0.011, 0.016, (0.05, 0.05, 0.017), "steel_worn", segs=12, parent=rf, bevel=False)
    k.tube("barrel", (0, 0.2, 0.03), (0, 0.775, 0.03), 0.0095, "gunmetal", radius_end=0.0085, parent=rf, segs=14,
           bevel=False)
    k.beam("handguard", (0, 0.22, 0.04), (0, 0.42, 0.04), (0.03, 0.02), "wood", parent=rf, bevel=0.004)
    for y in (0.24, 0.43):
        k.box("band", (0.044, 0.016, 0.07), (0, y, 0.0), "brass", parent=rf, bevel=0.004)
    k.box("front_sight", (0.006, 0.012, 0.022), (0, 0.76, 0.048), "gunmetal", parent=rf, bevel=False)
    k.box("rear_sight", (0.026, 0.05, 0.012), (0, 0.24, 0.06), "gunmetal", parent=rf, bevel=False)
    k.box("bayonet_lug", (0.012, 0.03, 0.014), (0, 0.75, 0.014), "gunmetal", parent=rf, bevel=False)
    k.hose("sling", [(0.024, 0.43, -0.01), (0.03, 0.2, -0.17), (0.03, -0.05, -0.2), (0.024, -0.28, -0.1)],
           0.006, "leather", parent=rf)


def _gear(k, rig, man, role, rnd):
    s = rig.s
    P = lambda *v: Vector(v) * s  # noqa: E731
    # belt and buckle
    belt = hu.loft(k, "belt", [dict(c=P(0, 0.008, 1.03), rx=0.172 * s, ry=0.113 * s, p=2.4),
                               dict(c=P(0, 0.008, 1.08), rx=0.17 * s, ry=0.112 * s, p=2.4)],
                   "leather", man, segs=20, caps=(False, False), subsurf=1)
    rig.attach(belt, "pelvis")
    rig.attach(k.box("buckle", (0.065 * s, 0.012 * s, 0.05 * s), P(0, 0.122, 1.055), "brass", parent=man,
                     bevel=0.003), "pelvis")
    # ammunition pouches on the front of the belt
    for sx in (-1, 1):
        for i, x in enumerate((0.065, 0.13)):
            yy = 0.11 - 0.035 * i
            p = k.box("pouch", (0.06 * s, 0.035 * s, 0.07 * s), P(sx * x, yy, 1.045), "leather",
                      rot=(0, 0, -sx * 0.3 * i), parent=man, bevel=0.007)
            f = k.box("pouch_flap", (0.064 * s, 0.04 * s, 0.022 * s), P(sx * x, yy + 0.002, 1.08), "leather",
                      rot=(0, 0, -sx * 0.3 * i), parent=man, bevel=0.005)
            b = k.cylinder("stud", 0.006 * s, 0.005 * s, P(sx * x, yy + 0.022, 1.07), "brass", segs=8,
                           rot=(-math.pi / 2, 0, 0), parent=man, bevel=False)
            for o in (p, f, b):
                rig.attach(o, "pelvis")
    # Y-straps over the shoulders
    for sx in (-1, 1):
        a, b, c, d = P(sx * 0.1, 0.112, 1.09), P(sx * 0.115, 0.11, 1.38), P(sx * 0.11, 0.0, 1.5), P(sx * 0.08, -0.12, 1.3)
        for p0, p1 in ((a, b), (b, c), (c, d)):
            rig.attach(k.beam("y_strap", p0, p1, (0.035 * s, 0.006 * s), "webbing", parent=man, bevel=False), "chest")
    # tunic front: brass buttons, breast pockets with flaps, hip pockets
    for z, y in ((1.13, 0.118), (1.2, 0.126), (1.27, 0.133), (1.34, 0.139)):
        rig.attach(k.cylinder("button", 0.009 * s, 0.006 * s, P(0, y, z), "brass", segs=10,
                              rot=(-math.pi / 2, 0, 0), parent=man, bevel=False), "chest" if z > 1.25 else "spine")
    for sx in (-1, 1):
        rig.attach(k.box("breast_pocket", (0.085 * s, 0.014 * s, 0.1 * s), P(sx * 0.095, 0.124, 1.31), "uniform",
                         rot=(-0.12, 0, -sx * 0.18), parent=man, bevel=0.006), "chest")
        rig.attach(k.box("pocket_flap", (0.092 * s, 0.018 * s, 0.035 * s), P(sx * 0.095, 0.133, 1.36), "uniform",
                         rot=(-0.12, 0, -sx * 0.18), parent=man, bevel=0.006), "chest")
        rig.attach(k.box("hip_pocket", (0.1 * s, 0.014 * s, 0.11 * s), P(sx * 0.11, 0.115, 0.9), "uniform",
                         rot=(0.05, 0, -sx * 0.3), parent=man, bevel=0.006), "pelvis")
    # gorget and scarf
    rig.attach(k.box("gorget", (0.12 * s, 0.012 * s, 0.06 * s), P(0, 0.1, 1.44), "brass", rot=(-0.2, 0, 0),
                     parent=man, bevel=0.004), "chest")
    scarf = hu.loft(k, "scarf", [dict(c=P(0, 0.005, 1.475), rx=0.08 * s, ry=0.075 * s),
                                 dict(c=P(0, 0.01, 1.52), rx=0.064 * s, ry=0.066 * s)],
                    "cloth_oxblood", man, segs=14, caps=(False, False), subsurf=1)
    rig.attach(scarf, "chest")
    rig.attach(k.box("scarf_knot", (0.04 * s, 0.03 * s, 0.05 * s), P(0.0, 0.075, 1.465), "cloth_oxblood",
                     rot=(-0.3, 0, 0.2), parent=man, bevel=0.012), "chest")
    # pack, blanket roll, mess tin, entrenching tool
    pk = k.empty("pack", P(0, -0.19, 1.27), parent=man)
    k.box("pack_body", (0.3 * s, 0.13 * s, 0.31 * s), (0, 0, 0), "canvas", parent=pk, bevel=0.035)
    k.box("pack_flap", (0.31 * s, 0.07 * s, 0.13 * s), (0, -0.04 * s, 0.1 * s), "canvas", rot=(0.12, 0, 0),
          parent=pk, bevel=0.025)
    for sx in (-1, 1):
        k.box("pack_strap", (0.03 * s, 0.14 * s, 0.006 * s), (sx * 0.08 * s, -0.005 * s, 0.03 * s), "leather",
              rot=(math.pi / 2, 0, 0), parent=pk, bevel=False)
        k.box("pack_buckle", (0.03 * s, 0.006 * s, 0.02 * s), (sx * 0.08 * s, -0.072 * s, -0.03 * s), "brass",
              parent=pk, bevel=False)
    k.cylinder("blanket_roll", 0.055 * s, 0.38 * s, (-0.19 * s, 0.0, 0.2 * s), "uniform", segs=18,
               rot=(0, math.pi / 2, 0), parent=pk, bevel=0.02)
    for sx in (-1, 1):
        k.torus("roll_strap", 0.058 * s, 0.005 * s, (sx * 0.1 * s, 0.0, 0.2 * s), "leather",
                rot=(0, math.pi / 2, 0), parent=pk, segs=18, tube_segs=4)
    k.cylinder("mess_tin", 0.065 * s, 0.04 * s, (0.0, -0.065 * s, -0.08 * s), "steel_worn", segs=20,
               rot=(math.pi / 2, 0, 0), parent=pk, bevel=0.004)
    k.tube("shovel_haft", (0.17 * s, 0.0, -0.14 * s), (0.17 * s, 0.0, 0.12 * s), 0.014 * s, "wood", parent=pk, segs=8)
    k.box("shovel_blade", (0.012 * s, 0.13 * s, 0.17 * s), (0.17 * s, 0.0, -0.22 * s), "steel_worn", parent=pk,
          bevel=0.004)
    if role == "nco":                                # oxblood pennant on a brass mast from the pack
        faction.pennant(k, pk, (-0.12 * s, -0.04 * s, 0.1 * s), h=0.75 * s, w=0.32 * s)
    rig.attach(pk, "chest")
    # canteen and bayonet on the left hip
    cn = k.empty("canteen", P(-0.175, -0.05, 0.93), parent=man)
    k.lathe("canteen_body", [(-0.04, 0.0), (-0.04, 0.06), (-0.03, 0.075), (0.03, 0.075), (0.04, 0.06), (0.04, 0.0)],
            "canvas", segs=18, rot=(0, 0, math.pi / 2), parent=cn).scale = (s, s * 0.55, s * 1.3)
    k.cylinder("canteen_cap", 0.016 * s, 0.03 * s, (0, 0, 0.095 * s), "brass", segs=10, parent=cn, bevel=False)
    rig.attach(cn, "pelvis")
    rig.attach(k.tube("scabbard", P(-0.15, -0.1, 1.0), P(-0.17, -0.16, 0.7), 0.017 * s, "leather", radius_end=0.01 * s,
                      parent=man, segs=10), "pelvis")
