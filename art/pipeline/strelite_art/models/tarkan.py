"""Таркански топ (game id tarkan): a light, quick steppe gun throwing small balls, ground only.
It picks the toughest enemy it can still kill. A horsetail standard (бунчук) stands beside it
and grows with the level; the Pliska rosette (seven flared blunt rays, two cut signs on each,
the IYI disc on the back; drawn from the find) is cast on it. Front is local +Y.

Look per level (sketch v5 approved 2026-11-22; looks of 2 and 3 swapped the same day, LOOK):
  1  bronze falconet on a swivel post in a ring of stones, a felt wrap, a tiller; one dark tail
  2  removable breech chamber and wedge lock; hide-covered shield; a timber platform
  3  thicker barrel on a tall two-wheel steppe cart (arba) with a wedge for elevation
  4  blackened iron and bronze: a revolving drum of six chambers; two big rosette handwheels
     (the rosette itself is the wheel); a log platform with an iron turntable
  5  gilded bronze: a ball hopper over the breech; golden rosette wheels; a white stone
     octagon with a gilded rosette; five white tails and a gilded spear finial
Barrel thicker from level 3; the standard grows with the level.
Ammo: a leather sack of balls, a wicker basket of iron balls, spare breech chambers on a rack,
ornamented cartridge crates, a lacquered chest of gilded balls.

Returns (root, turret). The base and the standard are static; the gun and its carriage turn.
Firing animation: recoil of the barrel; on level 4 the drum turns one chamber.
"""
import math

import bpy
from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit
from .trebuchet import _ball

LEVELS = (1, 2, 3, 4, 5)
FRAME_M = 8.0
TARGET_Z = 1.2
SPRITE_FRAME_M = 9.0
SWEEP_M = 2.1
FOOTPRINT_M = 3.0        # 2x2 tiles of 4 m
EL = math.radians(10)

STYLE = {
    1: dict(gun="bronze_old", wood="timber_raw", iron="iron_forged", tail="hair", pole="timber_raw",
            star="bronze_old"),
    2: dict(gun="bronze_old", wood="timber_tarred", iron="iron_forged", tail="hair", pole="timber_tarred",
            star="bronze_old"),
    3: dict(gun="iron_forged", wood="timber_tarred", iron="iron_black", tail="horsehair_brown", pole="timber_oak",
            star="bronze_old"),
    4: dict(gun="iron_black", wood="timber_oak", iron="bronze_old", tail="hair", pole="bronze_old",
            star="bronze_old"),
    5: dict(gun="gold_trim", wood="stone_pale", iron="gold_trim", tail="horsehair_white", pole="gold_trim",
            star="gold_trim"),
}
# metals per level (user 2026-11-22 14:25): gun, fittings, rosette (stone on level 1, user 14:53)
METAL = {1: ("iron_worn", "iron_worn", "stone"), 2: ("iron_forged", "iron_black", "bronze_old"),
         3: ("iron_forged", "iron_black", "bronze_old"), 4: ("iron_clean", "iron_clean", "iron_black"),
         5: ("gold_trim", "gold_trim", "gold_trim")}
LOOK = {1: 1, 2: 3, 3: 2, 4: 4, 5: 5}   # looks of 2 and 3 swapped (user 2026-11-22); thickness and standard follow level
FIRE = [-0.16, -0.11, -0.06, -0.03, -0.01, 0.0]       # barrel recoil (m) per frame
FIRE_FRAMES = len(FIRE)
RELEASE_FRAME = 1
RELOAD_FROM = 3
FIRE_FPS = 16
LOOP = False
_RIG = {}

ROT_Y = (-math.pi / 2, 0, 0)         # Kit cylinder (+Z) turned to point along +Y
ROT_TY = (math.pi / 2, 0, 0)         # Kit torus (around Z) turned to ring the +Y axis


def build(style, level=1):
    k = Kit(style)
    lk = LOOK[level]
    s = dict(STYLE[lk])
    s["gun"], s["iron"], s["star"] = METAL[level]
    s["level"] = level
    _RIG.clear()
    root = k.empty("tarkan")
    zb = _base(k, root, lk, s)
    _bunchuk(k, root, level, s, Vector((-1.0, -0.85, 0)))
    _ammo(k, root, lk, s)
    turret = k.empty("turret", (0, 0, 0), parent=root)
    turret["node"] = "turret"
    mp.set_reference(turret)
    t = 1.4 if level >= 3 else 1.0
    zc = _carriage(k, turret, lk, s, zb, t)
    elev = k.empty("elevating", (0, 0, zc), parent=turret)
    elev["node"] = "elevating"
    elev.rotation_euler = (EL, 0, 0)
    slide = k.empty("recoil", (0, 0, 0), parent=elev)
    slide["node"] = "recoil"
    _RIG["slide"] = slide
    tip = _barrel(k, slide, lk, s, t)
    m = k.empty("muzzle", (0, tip, 0), parent=slide)
    m["marker"] = "muzzle"
    if level >= 4:
        for sx in (-1, 1):                       # the rosette handwheels on both sides of the cradle
            k.tube("wheel_shaft", (sx * 0.22, -0.25, -0.18), (sx * 0.62, -0.25, -0.18), 0.035, s["iron"], parent=elev,
                   segs=10, bevel=False)
            e = k.empty("handwheel", (sx * 0.66, -0.25, -0.18), parent=elev)
            pliska(k, e, Vector((0, 0, 0)), sx, 0.5 if level == 4 else 0.58, s["star"], wheel=True)
            _gear(e, 0.0, 1.5)                   # traverse handwheels: they turn as the gun turns
    set_fire_frame(0)
    return root, turret


def ground(level):
    from ..terrain import Patch
    return Patch(r_solid=FOOTPRINT_M, r_out=FOOTPRINT_M + 0.6, r_bare=2.4, seed=83, ragged=0.5)


# -- the Pliska rosette --------------------------------------------------------------------------
# Drawn from the find (bronze, 38 mm, Pliska, 7th-9th c.; photo of both faces and the sign drawing
# by I. T. Ivanov, protobulgarians.com): seven flat rays that widen outward with blunt straight ends,
# round notches between them, a flat centre with a rectangular hole on the face, a raised round
# disc with the IYI sign on the back. Two cut signs on each ray of the face, one above the other.
# Glyphs: polylines in a cell of x -1..1 (to the right), y -1..1 (outward along the ray).


def _arc(cx, cy, r, a0, a1, n=10):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


_SIGNS = [   # clockwise from the top ray, as (inner sign, outer sign)
    # Sun: a Zh-like sign under a cross
    ([[(-0.6, 1), (0, 0.35), (0.6, 1)], [(0, 0.35), (0, -0.9)], [(-0.6, 0.2), (0.6, 0.2)],
      [(-0.6, 0.2), (-0.6, -0.9)], [(0.6, 0.2), (0.6, -0.9)]],
     [[(0, -1), (0, 1)], [(-0.7, 0.35), (0.7, 0.35)]]),
    # Mars: two triangles tip to tip, then a circle with horns
    ([[(-0.6, -1), (0.6, -1), (-0.6, 1), (0.6, 1), (-0.6, -1)]],
     [_arc(0, -0.3, 0.5, 0, 360, 16), _arc(0, 0.8, 0.6, 200, 340, 8)]),
    # Jupiter: a b-like sign, then a forked stem with an arc
    ([_arc(0.2, -0.5, 0.4, 0, 360, 14), [(-0.2, -0.5), (-0.2, 1), (0.3, 1)]],
     [[(-0.6, 1), (0, 0.2), (0.6, 1)], [(0, 0.2), (0, -0.9)], [(-0.35, -0.9), (0.35, -0.9)],
      _arc(0.2, 0.1, 0.7, -60, 60, 8)]),
    # Saturn: V, then a reversed E
    ([[(-0.6, 1), (0, -1), (0.6, 1)]],
     [_arc(0, 0, 0.75, -120, 120, 14), [(-0.1, 0), (0.75, 0)]]),
    # Moon: a stem with a flag and a bar, then a bracket with serifs
    ([[(0, -1), (0, 1)], [(0, 1), (0.6, 0.55), (0, 0.1)], [(-0.5, -0.4), (0.5, -0.4)]],
     [[(-0.4, 0.6), (-0.4, 0.85), (0.35, 0.85), (0.35, -0.85), (-0.4, -0.85), (-0.4, -0.6)]]),
    # Mercury: a triangle on a crossed stem, then a forked stem with a bar
    ([[(-0.55, 1), (0.55, 1), (0, 0.3), (-0.55, 1)], [(0, 0.3), (0, -1)], [(-0.55, -0.25), (0.55, -0.25)],
      [(-0.3, -1), (0.3, -1)]],
     [[(-0.6, 1), (0, 0.25), (0.6, 1)], [(0, 0.25), (0, -1)], [(-0.25, -0.45), (0.25, -0.45)]]),
    # Venus: V with a serif, then Y
    ([[(-0.6, 1), (0, -1), (0.6, 1)], [(-0.8, 1), (-0.45, 1)]],
     [[(-0.65, 1), (0, 0.15), (0.65, 1)], [(0, 0.15), (0, -1)]]),
]
_IYI = [[(-0.6, -0.8), (-0.6, 0.8)], [(0.6, -0.8), (0.6, 0.8)], [(0, -0.8), (0, 0.35)],
        [(0, 0.35), (-0.25, 0.9)], [(0, 0.35), (0.25, 0.9)]]


def _outline(R):
    """Seven rays widening outward with straight blunt ends, round notches between them."""
    rr, w0, w1, rv = 0.52 * R, 0.125 * R, 0.2 * R, 0.45 * R
    pts = []
    for i in range(7):
        a = math.pi / 2 - 2 * math.pi * i / 7
        d, q = (math.cos(a), math.sin(a)), (math.sin(a), -math.cos(a))      # q: clockwise side

        def P(u, v):
            return (d[0] * u + q[0] * v, d[1] * u + q[1] * v)
        pts += [P(rr, -w0), P(R, -w1), P(R, w1), P(rr, w0)]
        an = a - math.pi / 7                                                    # notch to the next ray
        A, B = P(rr, w0), None
        a2 = a - 2 * math.pi / 7
        d2, q2 = (math.cos(a2), math.sin(a2)), (math.sin(a2), -math.cos(a2))
        B = (d2[0] * rr - q2[0] * w0, d2[1] * rr - q2[1] * w0)
        C = (rv * math.cos(an), rv * math.sin(an))
        for j in range(1, 6):                                                   # quadratic curve A-C-B
            t = j / 6
            pts.append(((1 - t) ** 2 * A[0] + 2 * t * (1 - t) * (2 * C[0] - (A[0] + B[0]) / 2) + t * t * B[0],
                        (1 - t) ** 2 * A[1] + 2 * t * (1 - t) * (2 * C[1] - (A[1] + B[1]) / 2) + t * t * B[1]))
    return pts[::-1]                                                            # counter-clockwise


def _strokes(k, parent, c, side, face_x, R, glyph, centre, up, scale, mat):
    """Cut lines of one sign on the face at face_x; `up` is the in-plane direction of the cell's y."""
    w = Vector((0, up[0], up[1]))
    r = Vector((0, up[1], -up[0])) * side                       # the cell's x, as the viewer sees it
    for line in glyph:
        for (x0, y0), (x1, y1) in zip(line, line[1:]):
            p0 = centre + r * (x0 * scale) + w * (y0 * scale)
            p1 = centre + r * (x1 * scale) + w * (y1 * scale)
            e = p1 - p0
            if e.length < 1e-6:
                continue
            m = (p0 + p1) / 2
            k.box("pliska_sign", (0.003, R * 0.024, e.length + R * 0.02), (face_x, c.y + m.y, c.z + m.z), mat,
                  rot=(math.atan2(-e.y, e.z), 0, 0), parent=parent, bevel=False)


def pliska(k, parent, c, side, R, mat, wheel=False, t=None):
    """The rosette in the YZ plane at c, face toward +X (side 1) or -X (side -1), Sun ray up.
    As a wheel: the IYI disc on the back, a hub behind it and a grip on one ray."""
    c = Vector(c)
    t = t or max(0.02, R * 0.08)
    pts = [(c.y + y, c.z + z) for y, z in _outline(R)]
    k.plate("pliska_star", pts, t, c.x, mat, parent=parent, bevel=False)
    face = c.x + side * (t / 2 + 0.0012)
    cut = "iron_black"
    k.box("pliska_hole", (0.003, R * 0.16, R * 0.26), (face, c.y, c.z), "bore", parent=parent, bevel=False)
    s = 0.11 * R
    for i, (inner, outer) in enumerate(_SIGNS):
        a = math.pi / 2 - side * 2 * math.pi * i / 7         # clockwise as the viewer sees the face
        up = (math.cos(a), math.sin(a))
        for g, u in ((inner, 0.62), (outer, 0.86)):
            _strokes(k, parent, c, side, face, R, g, Vector((0, up[0], up[1])) * (u * R), up, s, cut)
    if wheel:
        back = c.x - side * t / 2
        k.cylinder("pliska_disc", R * 0.4, R * 0.05, (back, c.y, c.z), mat, segs=28,
                   rot=(0, -side * math.pi / 2, 0), parent=parent)
        _strokes(k, parent, c, -side, back - side * (R * 0.05 + 0.0012), R, _IYI, Vector((0, 0, 0)), (0, 1),
                 0.22 * R, cut)
        k.cylinder("wheel_hub", 0.045, 0.12, (back - side * R * 0.05, c.y, c.z), "iron_black", segs=16,
                   rot=(0, -side * math.pi / 2, 0), parent=parent)
        a = math.pi / 2 - side * 2 * math.pi * 2 / 7
        g = Vector((face, c.y + R * 0.9 * math.cos(a), c.z + R * 0.9 * math.sin(a)))
        k.tube("wheel_grip", g, g + Vector((side * 0.18, 0, 0)), 0.03, "timber_oak", parent=parent, segs=10)


# -- static base ------------------------------------------------------------------------------
def _base(k, root, level, s):
    if level == 1:                               # ring of stones round a swivel post, felt wrap
        import random
        rnd = random.Random(3)
        for i in range(9):
            a = 2 * math.pi * i / 9
            b = _ball(k, root, (0.6 * math.cos(a), 0.6 * math.sin(a), 0.05), 0.15, "stone", subdiv=2)
            b.scale = (rnd.uniform(1.0, 1.35), rnd.uniform(0.9, 1.2), rnd.uniform(0.55, 0.75))
        k.cylinder("swivel_post", 0.14, 0.92, (0, 0, 0), "log", segs=14, parent=root)
        k.cylinder("felt_wrap", 0.165, 0.12, (0, 0, 0.6), "cloth_oxblood", segs=16, parent=root)
        star = k.empty("post_rosette", (0, 0, 0.8), parent=root)   # flat, round the post, its rays under
        star.rotation_euler = (0, -math.pi / 2, 0)                  # the gun's rosettes like a crown gear
        pliska(k, star, Vector((0, 0, 0)), 1, 0.46, s["star"], t=0.05)
        return 0.92
    if level == 2:                               # a low timber turntable the cart stands on
        k.cylinder("turntable", 0.95, 0.12, (0, 0, 0), "timber_tarred", segs=36, parent=root)
        return 0.12
    if level == 3:                               # an iron turntable flush with the ground in a timber curb
        k.torus("curb", 0.86, 0.07, (0, 0, 0.02), "timber_tarred", parent=root, segs=40, tube_segs=6)
        k.cylinder("turntable", 0.78, 0.06, (0, 0, 0.0), "iron_black", segs=40, parent=root)
        return 0.06
    if level == 4:                               # log platform, iron turntable with bronze studs
        for i in range(5):
            y = -0.8 + 0.4 * i
            k.tube("log", (-0.85, y, 0.13), (0.85, y, 0.13), 0.13, "log", parent=root, segs=12)
        k.cylinder("turntable", 0.64, 0.14, (0, 0, 0.26), "iron_black", segs=36, parent=root)
        for i in range(8):
            a = 2 * math.pi * i / 8
            _ball(k, root, (0.56 * math.cos(a), 0.56 * math.sin(a), 0.4), 0.035, "bronze_old", subdiv=2)
        return 0.4
    # 5: white stone octagon with a gilded rosette on top
    k.cylinder("plinth", 1.05, 0.36, (0, 0, 0), "stone_pale", segs=8, parent=root)
    star = k.empty("base_rosette", (0, 0, 0.365), parent=root)
    star.rotation_euler = (0, -math.pi / 2, 0)            # lay the star (YZ plane, facing +X) flat, facing up
    pliska(k, star, Vector((0, 0, 0)), 1, 0.82, "gold_trim", t=0.012)
    k.cylinder("turntable", 0.34, 0.12, (0, 0, 0.36), "gold_trim", segs=32, parent=root)
    return 0.48


# -- the horsetail standard ---------------------------------------------------------------------
def _bunchuk(k, root, level, s, at):
    top = at + Vector((0, 0, 1.85 + 0.08 * level))
    k.tube("bunchuk_pole", at, top, 0.035, s["pole"], parent=root, segs=10)
    k.cylinder("bunchuk_cap", 0.07, 0.1, top - Vector((0, 0, 0.22)), s["pole"] if level > 1 else "leather", segs=14,
               parent=root)
    tails = {1: 1, 2: 1, 3: 3, 4: 3, 5: 5}[level]
    for i in range(tails):
        a = 2 * math.pi * i / max(tails, 1)
        off = Vector((math.cos(a), math.sin(a), 0)) * (0.045 if tails > 1 else 0.0)
        prof = [(0.0, 0.05), (-0.12, 0.085), (-0.45, 0.1), (-0.8, 0.085), (-1.05, 0.05), (-1.2, 0.012)]
        tl = k.lathe("horsetail", prof, s["tail"], segs=14, loc=top - Vector((0, 0, 0.2)) + off,
                     rot=(math.pi / 2, 0, 0), parent=root)
        tl.rotation_euler = (math.pi / 2 + 0.06 * math.cos(a) * (tails > 1), 0.06 * math.sin(a) * (tails > 1), 0)
    if level >= 2:                               # finial: crescent iron spear, gilded on 5
        k.tube("finial", top, top + Vector((0, 0, 0.32)), 0.05, "steel_worn" if level < 5 else "gold_trim",
               radius_end=0.004, parent=root, segs=8)
    if level >= 3:
        k.torus("finial_ring", 0.085, 0.015, top - Vector((0, 0, 0.12)), "paint_red" if level < 5 else "gold_trim",
                parent=root, segs=20, tube_segs=4)


# -- carriage (turns) -------------------------------------------------------------------------
def _carriage(k, t, level, s, zb, thick=1.0):
    if level == 1:                               # iron swivel fork on the post
        zc = zb + 0.18
        k.cylinder("swivel_pin", 0.06, 0.08, (0, 0, zb), s["iron"], segs=12, parent=t)
        k.box("fork_base", (0.5, 0.1, 0.05), (0, 0, zb + 0.05), s["iron"], parent=t, bevel=False)
        for sx in (-1, 1):
            k.box("fork_arm", (0.04, 0.08, 0.2), (sx * 0.23, 0, zb + 0.13), s["iron"], parent=t, bevel=False)
        return zc
    if level == 2:                               # arba: two tall spoked wheels, a bed, a trail
        zc = 0.95
        k.box("cart_bed", (1.0, 0.75, 0.16), (0, 0, 0.62), s["wood"], parent=t, bevel=0.01)
        k.tube("axle", (-0.75, 0, 0.62), (0.75, 0, 0.62), 0.045, s["iron"], parent=t, segs=10, bevel=False)
        for sx in (-1, 1):
            _wheel(k, t, Vector((sx * 0.68, 0, 0.62)), 0.6, s["wood"], tyre="iron_clean")
            for z in (0.5, 0.74):                # clean iron straps on the bed and the hub
                k.box("bed_strap", (0.04, 0.8, 0.04), (sx * 0.47, 0, z - 0.0), "iron_clean", parent=t, bevel=False)
            k.cylinder("hub_band", 0.115, 0.05, (sx * 0.68 - sx * 0.12, 0, 0.62), "iron_clean", segs=16,
                       rot=(0, math.pi / 2, 0), parent=t)
            k.box("cheek", (0.08, 0.5, 0.3), (sx * (0.19 * thick + 0.11), 0.02, 0.84), s["wood"], parent=t,
                  bevel=0.01)
        k.beam("trail", (0, -0.3, 0.6), (0, -1.45, 0.12), (0.14, 0.12), s["wood"], parent=t)
        for f in (0.15, 0.5, 0.85):              # clean iron bands round the trail
            p0 = Vector((0, -0.3, 0.6)).lerp(Vector((0, -1.45, 0.12)), f)
            k.box("trail_band", (0.17, 0.05, 0.15), p0, "iron_clean", rot=(math.atan2(0.48, 1.15), 0, 0), parent=t,
                  bevel=False)
        k.box("quoin", (0.2, 0.32, 0.08), (0, -0.4, 0.74), "timber_oak", rot=(math.radians(-14), 0, 0), parent=t,
              bevel=0.005)
        return zc
    if level == 3:                               # pedestal box, hide-covered shield at the front
        zc = zb + 0.6
        k.box("pedestal", (0.62, 0.55, 0.42), (0, 0, zb + 0.21), s["wood"], parent=t, bevel=0.015)
        for sx in (-1, 1):
            k.box("cheek", (0.08, 0.5, 0.3), (sx * (0.19 * thick + 0.11), 0, zb + 0.5), s["iron"], parent=t,
                  bevel=0.008)
        z0 = zb + 0.08                           # hide-covered shield with a notch for the barrel
        out = [(-0.68, 0), (0.68, 0), (0.68, 0.85), (0.32, 0.85), (0.32, 0.38), (-0.32, 0.38), (-0.32, 0.85),
               (-0.68, 0.85)]
        k.prism("shield", [(x, z0 + z) for x, z in out], 0.06, "leather", y=0.62, parent=t, bevel=False)
        for x in (-0.68, -0.32, 0.32, 0.68):
            k.box("shield_post", (0.06, 0.07, 0.88), (x, 0.6, z0 + 0.44), s["wood"], parent=t, bevel=False)
        k.box("shield_frame", (1.42, 0.07, 0.06), (0, 0.6, z0 + 0.02), s["wood"], parent=t, bevel=False)
        for sx in (-1, 1):
            k.beam("shield_strut", (sx * 0.3, 0.2, zb + 0.05), (sx * 0.5, 0.58, zb + 0.35), (0.05, 0.05), s["wood"],
                   parent=t, bevel=False)
        _rosette_train(k, t, zb, zc, s)
        return zc
    zc = zb + 0.62                               # 4, 5: a pedestal with cheeks
    k.box("pedestal", (0.55, 0.5, 0.42), (0, 0, zb + 0.21), s["iron"] if level == 4 else "gold_trim", parent=t,
          bevel=0.02)
    for sx in (-1, 1):
        k.box("cheek", (0.08, 0.55, 0.34), (sx * (0.19 * thick + 0.11), 0, zb + 0.52), s["iron"],
              parent=t, bevel=0.01)
    return zc


def _rosette_train(k, t, zb, zc, s):
    """Level 2: a train of rosettes meshing like gears down each side, the last one sunk into
    a slot in the turntable, as if a mechanism under the ground turns them."""
    x = 0.42
    pitch = 2 * math.pi / 7
    gears = [(0.2, Vector((0, -0.55, zc - 0.02)), math.radians(-115))]   # radius, centre, toward the next
    radii = [0.2, 0.16, 0.21]
    want = [math.radians(-115), math.radians(-62)]
    theta = want[0]
    phases = [theta - math.pi / 2]                                    # a tooth of gear 0 toward gear 1
    centres = [gears[0][1]]
    for i in range(1, len(radii)):
        back = theta + math.pi
        phases.append(back + pitch / 2 - math.pi / 2)                  # a gap of gear i toward gear i-1
        d = radii[i - 1] + radii[i] - 0.07
        centres.append(centres[i - 1] + Vector((0, math.cos(theta), math.sin(theta))) * d)
        if i < len(radii) - 1:                                         # the tooth of gear i nearest the way on
            base = back + pitch / 2
            k_ = round((want[i] - base) / pitch)
            theta = base + k_ * pitch
    speeds = [0.0] * len(radii)                   # turns per turn of the gun: the last is driven from below,
    speeds[-1] = 1.6                              # each turns the one above it the other way
    for i in range(len(radii) - 2, -1, -1):
        speeds[i] = -speeds[i + 1] * radii[i + 1] / radii[i]
    for sx in (-1, 1):                            # one train on each side
        k.box("train_plate", (0.025, 0.5, zc - zb + 0.05), (sx * (x - 0.06), -0.6, (zb + zc) / 2), s["iron"],
              parent=t, bevel=0.004)
        for R, c, ph, w in zip(radii, centres, phases, speeds):
            e = k.empty("train_rosette", (sx * x, c.y, c.z), parent=t)
            _gear(e, ph, w)
            pliska(k, e, Vector((0, 0, 0)), sx, R, s["star"], t=0.025)
            k.cylinder("train_axle", 0.03, 0.1, (sx * (x - 0.07), c.y, c.z), s["iron"], segs=10,
                       rot=(0, sx * math.pi / 2, 0), parent=t)
        last = centres[-1]                        # the slot it sinks into
        k.box("train_slot", (0.09, radii[-1] * 2.3, 0.006), (sx * x, last.y, zb + 0.002), "bore", parent=t,
              bevel=False)
        for sy in (-1, 1):
            k.box("slot_lip", (0.13, 0.03, 0.025), (sx * x, last.y + sy * radii[-1] * 1.18, zb + 0.012), s["iron"],
                  parent=t, bevel=False)


def _wheel(k, parent, c, r, mat, tyre="iron_forged"):
    k.torus("tyre", r, 0.04, c, tyre, rot=(0, math.pi / 2, 0), parent=parent, segs=36, tube_segs=6)
    k.torus("felloe", r - 0.055, 0.045, c, mat, rot=(0, math.pi / 2, 0), parent=parent, segs=36, tube_segs=6)
    k.cylinder("hub", 0.1, 0.24, c - Vector((0.12, 0, 0)), mat, segs=14, rot=(0, math.pi / 2, 0), parent=parent)
    for i in range(12):
        a = 2 * math.pi * i / 12
        k.beam("spoke", c, c + Vector((0, math.cos(a), math.sin(a))) * (r - 0.06), (0.035, 0.035), mat,
               parent=parent, bevel=False)


# -- the gun (on the recoil slide) -------------------------------------------------------------
def _barrel(k, p, level, s, t):
    g = s["gun"]
    y0, y1 = -0.7, 1.25
    rb, rc = 0.19 * t, 0.14 * t
    prof = [(y0 - 0.02, rb * 0.6), (y0, rb * 0.95), (y0 + 0.05, rb), (y0 + 0.8, rb * 0.97), (y0 + 0.84, rb * 1.06),
            (y0 + 0.9, rc * 1.05), (y1 - 0.18, rc), (y1 - 0.12, rc * 1.18), (y1, rc * 1.12)]
    k.lathe("barrel", prof, g, segs=28, parent=p)
    k.cylinder("bore", rc * 0.55, 0.02, (0, y1 - 0.01, 0), "bore", segs=20, rot=ROT_Y, parent=p, bevel=False)
    _ball(k, p, (0, y0 - 0.1, 0), rb * 0.45, g, subdiv=2)                 # cascabel
    for sx in (-1, 1):
        k.cylinder("trunnion", 0.05 * t, 0.1, (sx * (rb * 0.95), 0, 0), g, segs=12, rot=(0, sx * math.pi / 2, 0),
                   parent=p)
    if s.get("level") == 3:                      # obvious clean iron hoops on the dark barrel
        for i in range(6):                       # evenly spaced; the rosettes ride over them
            y = y0 + 0.1 + i * (y1 - 0.25 - y0 - 0.1) / 5
            r = next(p0[1] + (p1[1] - p0[1]) * (y - p0[0]) / (p1[0] - p0[0])
                     for p0, p1 in zip(prof, prof[1:]) if p0[0] <= y <= p1[0])
            k.torus("hoop", r + 0.012, 0.024, (0, y, 0), "iron_clean", rot=ROT_TY, parent=p, segs=28, tube_segs=6)
    if level <= 3:                               # the rosette cast on the breech side
        for sx in (-1, 1):
            lift = 0.04 if s.get("level") == 3 else 0.006         # over the hoops on level 3
            e = k.empty("barrel_rosette", (sx * (rb + lift), y0 + 0.3, 0.0), parent=p)
            pliska(k, e, Vector((0, 0, 0)), sx, 0.2 * t, s["star"],
                   t=0.03 if s.get("level") == 1 else 0.014)         # stone on level 1, thicker
            if s.get("level") == 1:              # rolls on the crown rosette of the post as the gun turns
                _gear(e, 0.0, 2.0)
            if lift > 0.01:
                k.cylinder("rosette_mount", 0.06, lift, (sx * rb * 0.98, y0 + 0.3, 0), s["gun"], segs=14,
                           rot=(0, sx * math.pi / 2, 0), parent=p)
    if level == 1:                               # tiller
        k.beam("tiller", (0, y0 - 0.12, 0), (0.05, y0 - 0.85, -0.3), (0.06, 0.06), "timber_raw", parent=p)
    if level == 3:                               # removable breech chamber with a wedge lock and a handle
        k.cylinder("chamber", 0.2, 0.34, (0, y0 - 0.38, 0), g, segs=24, rot=ROT_Y, parent=p)
        k.torus("chamber_handle", 0.08, 0.015, (0, y0 - 0.25, 0.22), "iron_black", rot=(0, math.pi / 2, 0),
                parent=p, segs=14, tube_segs=4)
        k.box("wedge", (0.5, 0.06, 0.1), (0, y0 - 0.02, 0.0), "timber_oak", parent=p, bevel=0.005)
    if level == 4:                               # revolving drum of six chambers, an index lever
        drum = k.empty("drum", (0, y0 - 0.22, 0), parent=p)
        _RIG["drum"] = drum
        k.cylinder("drum_body", 0.38, 0.42, (0, -0.21, 0), s["gun"], segs=36, rot=ROT_Y, parent=drum)
        k.torus("drum_band", 0.385, 0.02, (0, 0.0, 0), "iron_black", rot=ROT_TY, parent=drum, segs=36, tube_segs=4)
        for i in range(6):
            a = 2 * math.pi * i / 6
            k.cylinder("chamber_mouth", 0.075, 0.02, (0.24 * math.cos(a), -0.225, 0.24 * math.sin(a)), "bore", segs=14,
                       rot=ROT_Y, parent=drum, bevel=False)
            k.box("drum_flute", (0.05, 0.4, 0.03), (0.38 * math.cos(a + 0.52), 0, 0.38 * math.sin(a + 0.52)),
                  "iron_black", rot=(0, -(a + 0.52), 0), parent=drum, bevel=False)
        k.beam("index_lever", (0.3, y0 - 0.3, -0.12), (0.55, y0 - 0.5, -0.4), (0.04, 0.04), "iron_black", parent=p,
               bevel=False)
    if level == 5:                               # ball hopper over the breech, a crank
        hz = rb + 0.05
        prof = [(0.0, 0.07), (0.25, 0.08), (0.45, 0.22), (0.5, 0.23), (0.5, 0.2)]
        k.lathe("hopper", prof, "gold_trim", segs=24, loc=(0, y0 + 0.2, hz), rot=(-math.pi / 2, 0, 0), parent=p)
        for i in range(6):
            a = 2 * math.pi * i / 6
            _ball(k, p, (0.1 * math.cos(a), y0 + 0.2 + 0.1 * math.sin(a), hz + 0.47), 0.06, "gold_trim", subdiv=2)
        k.beam("hopper_crank", (0.24, y0 + 0.2, hz + 0.2), (0.4, y0 + 0.05, hz + 0.35), (0.03, 0.03), "gold_trim",
               parent=p, bevel=False)
    return y1


# -- ammo pile --------------------------------------------------------------------------------
def _ammo(k, root, level, s):
    g = Vector((1.4, 1.05, 0))
    if level == 1:                               # leather sack of balls, a few spilled
        b = _ball(k, root, g + Vector((0, 0, 0.18)), 0.24, "leather", subdiv=3)
        b.scale = (1.0, 0.9, 0.8)
        k.tube("sack_neck", g + Vector((0, 0, 0.34)), g + Vector((0.02, 0, 0.46)), 0.06, "leather", radius_end=0.03,
               parent=root, segs=10)
        for d in ((0.32, 0.12), (0.4, -0.05), (0.28, -0.2)):
            _ball(k, root, g + Vector((d[0], d[1], 0.06)), 0.06, "stone", subdiv=2)
    elif level == 2:                             # wicker basket of iron balls
        k.cylinder("basket", 0.28, 0.32, g, "wicker", segs=20, parent=root, radius_top=0.3)
        for i in range(7):
            a = 2 * math.pi * i / 7
            _ball(k, root, g + Vector((0.14 * math.cos(a), 0.14 * math.sin(a), 0.34)), 0.065, "iron_forged", subdiv=2)
    elif level == 3:                             # rack of spare breech chambers
        k.box("chamber_rack", (0.85, 0.35, 0.12), g + Vector((0, 0, 0.06)), "timber_oak", parent=root, bevel=0.01)
        for i in range(4):
            k.cylinder("spare_chamber", 0.09, 0.32, g + Vector((-0.3 + 0.2 * i, 0, 0.12)), "iron_forged", segs=16,
                       parent=root)
    elif level == 4:                             # cartridge crates with a bronze ornament band
        k.box("crate", (0.7, 0.45, 0.32), g + Vector((0, 0, 0.16)), "timber_oak", parent=root, bevel=0.01)
        k.box("crate", (0.7, 0.45, 0.32), g + Vector((0.05, 0.05, 0.48)), "timber_oak", parent=root, bevel=0.01)
        k.box("crate_band", (0.72, 0.47, 0.05), g + Vector((0.05, 0.05, 0.52)), "bronze_old", parent=root,
              bevel=False)
    else:                                        # lacquered chest of gilded balls
        k.box("chest", (0.8, 0.5, 0.28), g + Vector((0, 0, 0.14)), "timber_varnish", parent=root, bevel=0.015)
        k.box("chest_trim", (0.84, 0.54, 0.03), g + Vector((0, 0, 0.295)), "gold_trim", parent=root, bevel=0.005)
        for i in range(5):
            _ball(k, root, g + Vector((-0.24 + 0.12 * i, 0.04 * (i % 2), 0.35)), 0.06, "gold_trim", subdiv=2)


# -- rosettes that turn with the gun ------------------------------------------------------------
def _gear(empty, phase, ratio):
    """Register a rosette that turns about local X by `ratio` times the gun's yaw (see set_aim).
    Ratios keep one direction step (11.25 deg) under half a tooth (25.7 deg) so the turn reads."""
    _RIG.setdefault("gears", []).append((empty, phase, ratio))
    empty.rotation_euler = (phase, 0, 0)


def set_aim(yaw):
    """Called by the renderer for each aim direction: the geared rosettes turn with the yaw."""
    for e, phase, ratio in _RIG.get("gears", ()):
        e.rotation_euler = (phase + ratio * yaw, 0, 0)


# -- round and animation ---------------------------------------------------------------------------
def build_round(k, parent, level):
    """The small ball of this level, centred on `parent`."""
    mat = {1: "stone", 2: "iron_forged", 3: "iron_forged", 4: "iron_black", 5: "gold_trim"}[level]
    _ball(k, parent, (0, 0, 0), 0.07, mat, subdiv=3)


def key_fire_animation(scene):
    prefs = bpy.context.preferences.edit
    old = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = "LINEAR"
    for f in range(FIRE_FRAMES + 1):
        set_fire_frame(f)
        _RIG["slide"].keyframe_insert("location", frame=f)
        if "drum" in _RIG:
            _RIG["drum"].keyframe_insert("rotation_euler", frame=f)
    prefs.keyframe_new_interpolation_type = old
    scene.frame_set(0)


def set_fire_frame(f, scene=None):
    if scene is not None and _RIG["slide"].animation_data is not None:
        scene.frame_set(f)
    else:
        _RIG["slide"].location = (0, 0.0 if f == 0 else FIRE[f - 1], 0)
        if "drum" in _RIG:                       # one chamber on (60 deg) from the shot to the reload
            turn = 0.0 if f <= RELEASE_FRAME else min(1.0, (f - RELEASE_FRAME) / (RELOAD_FROM - RELEASE_FRAME + 1))
            _RIG["drum"].rotation_euler = (0, math.radians(60) * turn, 0)
    bpy.context.view_layer.update()
