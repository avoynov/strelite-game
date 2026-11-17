"""Counterweight trebuchet (bg: „Требушет“): the heavy, slow siege engine.

Built at real size for the game: frame 6.3 m long and 2.4 m wide on a turntable,
throwing arm 6.8 m (long end 5.2 m, short end 1.6 m) on an axle 4.3 m up, cocked
with the long end latched at the back and the sling laid forward in its trough.
The whole machine turns on the turntable to aim; front is local +Y.

The levels keep the silhouette and change the machine itself, and what it throws:
  1  rough-hewn timber, rope lashings, a plank box of field stones; throws a field stone
  2  tarred timber with forged iron bands, the stone box strapped with iron; an iron-bound stone
  3  dark oak under heavy iron straps and bolts, an iron-hooped chest; a cast-iron ball
  4  frame sheathed in blackened iron plate with bronze fittings, riveted iron counterweight,
     chain sling; a spiked iron ball
  5  polished silver frame with gold fittings, a cast silver counterweight; a silver orb banded in gold

Returns (root, turret). `turret` (the whole machine) rotates around Z to aim.

Firing animation: set_fire_frame(f) poses the built machine for frame f of FIRE (1-based;
frame 0 is the cocked machine of the aim sprites). The arm swings on its axle, the
counterweight hangs plumb from its pin, the sling whips round and lets the round go at
RELEASE_FRAME, the arm rocks to a stop, then the crew winches it back down (from
RELOAD_FROM on) and a new round is laid in the pouch on the last frame. Call it only
after materials_photoreal.stamp(), which must see the machine cocked.
"""
import math
import random

import bmesh
import bpy
from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit

LEVELS = (1, 2, 3, 4, 5)
FRAME_M = 14.0
TARGET_Z = 2.2
SPRITE_FRAME_M = 16.0
SWEEP_M = 4.15           # rear corners of the frame turn inside this radius
FOOTPRINT_M = 5.0        # 3x3 tiles of 4 m
PLATFORM_Z = 0.2         # top of the turntable
PIVOT = Vector((0.0, 0.0, 4.3))
LONG, SHORT = 5.2, 1.6
COCK = math.radians(45)  # long arm points back and down by this much
POUCH = Vector((0.0, -1.15, 0.56))     # pouch at rest, in the trough (turret space)

# Sprite frame: 18 m wide, 18 m tall, the tower's ground point 5 m above the bottom edge,
# so the sling at the top of its swing stays inside.
SPRITE_WH_M = (18.0, 18.0)
ANCHOR_FROM_BOTTOM_M = 5.0

# Firing animation, one row per frame: arm angle theta (deg; the long end points along
# (0, -cos, -sin), 45 = cocked), sling angle alpha (deg, absolute; 0 = forward, 90 = up),
# round still in the pouch, winch rope hooked on.
FIRE = [
    (30, -20, True, False),      # 1  latch tripped, the pouch slides back along the trough
    (10, -80, True, False),      # 2
    (-15, -130, True, False),    # 3
    (-45, -170, True, False),    # 4
    (-70, 150, True, False),     # 5
    (-90, 75, False, False),     # 6  release: the round leaves the pouch here
    (-110, 40, False, False),    # 7
    (-125, 0, False, False),     # 8
    (-132, -40, False, False),   # 9  arm at the end of its throw
    (-122, -70, False, False),   # 10
    (-112, -85, False, False),   # 11
    (-80, -90, False, True),     # 12 crew hooks the winch rope and hauls the arm down
    (-35, -90, False, True),     # 13
    (0, -90, False, True),       # 14
    (25, -90, False, True),      # 15
    (40, 0, True, True),         # 16 nearly cocked, a new round in the pouch
]
FIRE_FRAMES = len(FIRE)
RELEASE_FRAME = 6
RELOAD_FROM = 12
FIRE_FPS = 16
_RIG = {}

STYLE = {
    1: dict(wood="timber_raw", arm="timber_raw", fit="iron_forged", rope="hemp", cable="hemp",
            plat="timber_raw", rim=None, bolt=None, band_w=0.09),
    2: dict(wood="timber_tarred", arm="timber_tarred", fit="iron_forged", rope="hemp", cable="hemp",
            plat="timber_tarred", rim="iron_forged", bolt=None, band_w=0.09),
    3: dict(wood="timber_oak", arm="timber_oak", fit="iron_black", rope="hemp", cable="hemp",
            plat="timber_oak", rim="iron_black", bolt="iron_black", band_w=0.16),
    4: dict(wood="iron_black", arm="timber_oak", fit="bronze_old", rope="hemp", cable="iron_forged",
            plat="timber_oak", rim="bronze_old", bolt="bronze_old", band_w=0.14),
    5: dict(wood="silver_satin", arm="silver_satin", fit="gold_trim", rope="steel_cable",
            cable="steel_cable", plat="timber_oak", rim="silver", bolt="gold_trim", band_w=0.12),
}


def build(style, level=1):
    k = Kit(style)
    s = STYLE[level]
    root = k.empty("trebuchet")
    _platform(k, root, level, s)
    turret = k.empty("turret", (0, 0, PLATFORM_Z), parent=root)
    turret["node"] = "turret"
    mp.set_reference(turret)
    _frame(k, turret, level, s)
    _arm(k, turret, level, s)
    _windlass(k, turret, level, s)
    th, al = FIRE[RELEASE_FRAME - 1][:2]
    tip, pouch = _sling_pose(th, al)
    m = k.empty("muzzle", pouch, parent=turret)              # where the round leaves the sling
    m["marker"] = "muzzle"
    _rig(k, turret)
    return root, turret


# -- firing animation -----------------------------------------------------------------------
def _pv():
    return PIVOT - Vector((0, 0, PLATFORM_Z))


def _long_dir(theta_deg):
    t = math.radians(theta_deg)
    return Vector((0, -math.cos(t), -math.sin(t)))


TIP0 = PIVOT - Vector((0, 0, PLATFORM_Z)) + Vector((0, -math.cos(COCK), -math.sin(COCK))) * LONG
END0 = PIVOT - Vector((0, 0, PLATFORM_Z)) - Vector((0, -math.cos(COCK), -math.sin(COCK))) * SHORT
SLING_LEN = (POUCH - TIP0).length
ALPHA0 = math.atan2(POUCH.z - TIP0.z, POUCH.y - TIP0.y)


def _sling_pose(theta, alpha):
    """Arm tip and pouch (turret space) for arm angle theta and wanted sling angle alpha
    (degrees); a pouch that would go below its rest height slides along the trough instead."""
    tip = _pv() + _long_dir(theta) * LONG
    a = math.radians(alpha)
    if tip.z + SLING_LEN * math.sin(a) < POUCH.z:
        sn = max(-1.0, min(1.0, (POUCH.z - tip.z) / SLING_LEN))
        a = math.atan2(sn, math.copysign(math.sqrt(1 - sn * sn), math.cos(a)))
    return tip, tip + Vector((0, math.cos(a), math.sin(a))) * SLING_LEN


def _rig(k, t):
    """Hang the moving parts on three pivots: arm (axle), counterweight (its pin, under the
    arm) and sling (arm tip). Parts keep their place; only the pivots move later."""
    bpy.context.view_layer.update()
    arm = k.empty("arm_pivot", _pv(), parent=t)
    cw = k.empty("cw_pivot", END0 - _pv(), parent=arm)
    sling = k.empty("sling_pivot", TIP0, parent=t)
    bpy.context.view_layer.update()
    for o in list(t.children):
        role = o.get("rig")
        target = {"arm": arm, "cw": cw, "sling": sling}.get(role)
        if target is not None:
            mw = o.matrix_world.copy()
            o.parent = target
            o.matrix_world = mw
    _RIG.update(arm=arm, cw=cw, sling=sling, turret=t)


def _pose_values():
    """Per frame 0..FIRE_FRAMES: arm angle, sling root and sling angle, with the sling angle
    unwrapped so that it turns continuously (it whips all the way round)."""
    out, prev = [], None
    rows = [(45, math.degrees(ALPHA0), True, True)] + FIRE
    for theta, alpha, loaded, winch in rows:
        beta = math.radians(theta) - COCK
        tip, pouch = _sling_pose(theta, alpha)
        d = pouch - tip
        sa = math.atan2(d.z, d.y) - ALPHA0
        if prev is not None:
            sa = prev + (sa - prev + math.pi) % (2 * math.pi) - math.pi
        prev = sa
        out.append((beta, tip, sa, loaded, winch))
    return out


def key_fire_animation(scene):
    """Keyframe the pivots at scene frames 0..FIRE_FRAMES (linear), so Cycles can blur the
    motion of the fast frames. Frame 0 is the cocked pose."""
    prefs = bpy.context.preferences.edit
    old = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = "LINEAR"
    for f, (beta, tip, sa, _, _) in enumerate(_pose_values()):
        _RIG["arm"].rotation_euler = (beta, 0, 0)
        _RIG["cw"].rotation_euler = (-beta, 0, 0)
        _RIG["sling"].location = tip
        _RIG["sling"].rotation_euler = (sa, 0, 0)
        for o, path in ((_RIG["arm"], "rotation_euler"), (_RIG["cw"], "rotation_euler"),
                        (_RIG["sling"], "rotation_euler"), (_RIG["sling"], "location")):
            o.keyframe_insert(path, frame=f)
    prefs.keyframe_new_interpolation_type = old
    scene.frame_set(0)


def set_fire_frame(f, scene=None):
    """Pose the machine for animation frame f (0 = cocked, 1..FIRE_FRAMES)."""
    beta, tip, sa, loaded, winch = _pose_values()[f]
    if scene is not None and _RIG["arm"].animation_data is not None:
        scene.frame_set(f)
    else:
        _RIG["arm"].rotation_euler = (beta, 0, 0)
        _RIG["cw"].rotation_euler = (-beta, 0, 0)
        _RIG["sling"].location = tip
        _RIG["sling"].rotation_euler = (sa, 0, 0)
    stack = [_RIG["turret"]]
    while stack:
        o = stack.pop()
        stack.extend(o.children)
        if o.get("rig") == "round":
            o.hide_render = not loaded
        if o.name.startswith("winch_rope"):
            o.hide_render = not winch
    bpy.context.view_layer.update()


def _tag(before, role):
    for o in set(bpy.data.objects) - before:
        o["rig"] = role


def ground(level):
    from ..terrain import Patch
    return Patch(r_solid=FOOTPRINT_M, r_out=FOOTPRINT_M + 0.7, r_bare=3.6, seed=37, ragged=0.5)


# -- helpers -----------------------------------------------------------------------------
def _beam(k, t, name, p0, p1, sec, mat):
    return k.beam(name, p0, p1, sec, mat, parent=t, bevel=0.012)


def _band(k, t, p, d, sec, level, s, width=None):
    """What holds a joint together: rope lashing (1), forged iron band with bolts (2),
    heavier straps (3, 4), gold collar (5). d = direction of the member, sec = its section."""
    width = width or s["band_w"]
    d = Vector(d).normalized()
    p = Vector(p)
    if level == 1:
        rot = d.to_track_quat("Z", "Y").to_euler()
        r = max(sec) * 0.62
        for i in range(3):
            k.torus("lashing", r, 0.018, p + d * (i - 1) * 0.04, s["rope"], rot=rot, parent=t,
                    segs=20, tube_segs=6)
        return
    k.beam("band", p - d * width / 2, p + d * width / 2, (sec[0] + 0.03, sec[1] + 0.03), s["fit"],
           parent=t, bevel=0.004)
    if s["bolt"]:
        side = d.cross(Vector((0, 0, 1)))
        if side.length < 0.1:
            side = Vector((1, 0, 0))
        side.normalize()
        for sg in (-1, 1):
            q = p + side * sg * (sec[0] / 2 + 0.016)
            k.cylinder("bolt", 0.026, 0.02, q, s["bolt"], segs=6,
                       rot=(side * sg).to_track_quat("Z", "Y").to_euler(), parent=t, bevel=False,
                       smooth=False)


def _rock(k, parent, loc, r, seed, rounded=False):
    rnd = random.Random(seed)
    me = bpy.data.meshes.new("rock")
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=3 if rounded else 2, radius=r)
    if rounded:     # a picked, roughly dressed throwing stone
        sx, sy, sz, jit = rnd.uniform(0.95, 1.1), rnd.uniform(0.9, 1.05), rnd.uniform(0.82, 0.95), 0.07
    else:
        sx, sy, sz, jit = rnd.uniform(0.8, 1.2), rnd.uniform(0.75, 1.1), rnd.uniform(0.6, 0.9), 0.12
    lumps = [(Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))).normalized(), rnd.uniform(-0.2, 0.1))
             for _ in range(9)] if rounded else []
    for v in bm.verts:
        j = 1 + rnd.uniform(-jit, jit) * (0.4 if rounded else 1.0)
        n = v.co.normalized()
        for d, h in lumps:                 # broad flats and bulges instead of facets
            j += h * max(0.0, n.dot(d)) ** 4
        v.co.x *= sx * j
        v.co.y *= sy * j
        v.co.z *= sz * j
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new("rock", me)
    o.location = loc
    o.rotation_euler = (rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), rnd.uniform(0, 6.3))
    return k._finish(o, "stone", bevel=False, parent=parent)


# -- static turntable ----------------------------------------------------------------------
def _platform(k, root, level, s):
    R = 2.35
    n = 16
    for i in range(n):                                   # planks across the disc, ends cut round
        _plank(k, root, R, -R + i * 2 * R / n + 0.008, -R + (i + 1) * 2 * R / n - 0.008, s["plat"])
    if s["rim"]:
        k.torus("rim", R, 0.06, (0, 0, PLATFORM_Z * 0.55), s["rim"], parent=root, segs=64, tube_segs=8)
    k.cylinder("pivot", 0.22, 0.08, (0, 0, PLATFORM_Z), s["rim"] or "iron_forged", segs=20, parent=root)


def _plank(k, root, R, y0, y1, mat, m=5):
    """One floor plank between y0 and y1 whose ends follow the platform circle. Built with its
    length along local Z (the timber grain) and turned so that runs along world X."""
    from mathutils import Matrix
    ys = [y0 + (y1 - y0) * j / (m - 1) for j in range(m)]
    half = [math.sqrt(max(R * R - y * y, 0.0004)) for y in ys]
    outline = [(y, h) for y, h in zip(ys, half)] + [(y, -h) for y, h in zip(reversed(ys), reversed(half))]
    t = PLATFORM_Z
    verts = [(u, v, w) for v in (-t / 2, t / 2) for (u, w) in outline]
    n = len(outline)
    faces = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
    faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    obj = k.mesh("plank", verts, faces)
    obj.rotation_euler = Matrix(((0, 0, 1), (1, 0, 0), (0, 1, 0))).to_euler()
    obj.location = (0, 0, t / 2)
    return k._finish(obj, mat, bevel=0.01, parent=root)


# -- rotating frame ------------------------------------------------------------------------
def _frame(k, t, level, s):
    W = s["wood"]
    z = 0.16
    sill = (0.3, 0.3)
    for sx in (-1, 1):
        x = sx * 1.05
        _beam(k, t, "sill", (x, -3.95, z), (x, 2.45, z), sill, W)
        top = Vector((x, 0, PIVOT.z + 0.25))
        _beam(k, t, "post", (x, 0, z + 0.15), top, (0.3, 0.3), W)
        for y0 in (2.15, -2.25):                             # A-frame struts
            a, b = Vector((x, y0, z + 0.15)), Vector((x, math.copysign(0.14, y0), PIVOT.z - 0.15))
            _beam(k, t, "strut", a, b, (0.24, 0.24), W)
            _band(k, t, a.lerp(b, 0.06), b - a, (0.24, 0.24), level, s)
            _band(k, t, a.lerp(b, 0.93), b - a, (0.24, 0.24), level, s)
        for y0 in (1.3, -1.35):                              # X-bracing in the side frame
            a, b = Vector((x, y0, z + 0.2)), Vector((x, 0.0, 2.2))
            _beam(k, t, "brace", a, b, (0.16, 0.16), W)
        # outrigger and its raking prop
        o0, o1 = Vector((sx * 2.2, 0, z - 0.02)), Vector((sx * 1.2, 0, 2.55))
        _beam(k, t, "prop", o0 + Vector((0, 0, 0.12)), o1, (0.2, 0.2), W)
        _band(k, t, o0.lerp(o1, 0.85), o1 - o0, (0.2, 0.2), level, s)
        _band(k, t, (x, 0, PIVOT.z - 0.55), (0, 0, 1), (0.3, 0.3), level, s)
        _band(k, t, (x, 0, z + 0.45), (0, 0, 1), (0.3, 0.3), level, s)
        k.box("post_cap", (0.36, 0.36, 0.08), (x, 0, PIVOT.z + 0.29), s["fit"] if level > 1 else W, parent=t,
              bevel=0.01)
    _beam(k, t, "outrigger", (-2.25, 0, z - 0.02), (2.25, 0, z - 0.02), (0.24, 0.24), W)
    for y in (2.3, -2.5, -3.8):
        _beam(k, t, "tie", (-1.25, y, z + 0.02), (1.25, y, z + 0.02), (0.26, 0.26), W)
    for sx in (-1, 1):
        for y in (2.3, -2.5, -3.8):
            if level > 1:
                _band(k, t, (sx * 1.05, y, z), (0, 1, 0), (0.3, 0.3), level, s, width=0.34)
    # axle through both posts
    k.tube("axle", (-1.42, 0, PIVOT.z), (1.42, 0, PIVOT.z), 0.11, s["fit"] if level > 1 else W, parent=t,
           segs=20)
    for sx in (-1, 1):
        k.cylinder("axle_cap", 0.16, 0.06, (sx * 1.4, 0, PIVOT.z), s["fit"] if level > 1 else "iron_forged",
                   segs=18, rot=(0, sx * math.pi / 2, 0), parent=t)
    # trough for the sling and the latch that holds the cocked arm
    _beam(k, t, "trough", (0, -3.7, z + 0.2), (0, -0.2, z + 0.2), (0.75, 0.05), W)
    for sx in (-1, 1):
        _beam(k, t, "trough_side", (sx * 0.38, -3.7, z + 0.27), (sx * 0.38, -0.2, z + 0.27), (0.04, 0.16), W)
    k.box("latch_block", (0.5, 0.3, 0.35), (0, -3.82, z + 0.32), W, parent=t, bevel=0.012)
    k.tube("latch_pin", (0, -3.9, z + 0.6), (0, -3.6, z + 0.65), 0.035, s["fit"] if level > 1 else "iron_forged",
           parent=t, segs=10)


def _arm(k, t, level, s):
    W = s["arm"]
    before = set(bpy.data.objects)
    back = Vector((0, -math.cos(COCK), -math.sin(COCK)))
    pv = PIVOT - Vector((0, 0, PLATFORM_Z))
    tip, end = pv + back * LONG, pv - back * SHORT
    _beam(k, t, "arm", end, tip, (0.34, 0.42), W)
    # hub around the axle, bands along the arm
    k.box("hub", (0.5, 0.62, 0.62), pv, s["fit"] if level > 1 else W, rot=(COCK, 0, 0), parent=t,
          bevel=0.02)
    for f in (0.25, 0.5, 0.75, 0.92):
        _band(k, t, pv.lerp(tip, f), tip - pv, (0.3 - 0.1 * f, 0.38 - 0.12 * f), level, s)
    _band(k, t, pv.lerp(end, 0.7), end - pv, (0.34, 0.42), level, s)
    k.box("tip_cap", (0.24, 0.3, 0.26), tip + back * 0.05, s["fit"] if level > 1 else "iron_forged",
          rot=(COCK, 0, 0), parent=t, bevel=0.01)
    # counterweight hangs from a hinge pin at the short end
    k.tube("cw_pin", end + Vector((-0.42, 0, 0)), end + Vector((0.42, 0, 0)), 0.06, s["fit"] if level > 1 else
           "iron_forged", parent=t, segs=12)
    _tag(before, "arm")
    before = set(bpy.data.objects)
    box_top = end.z - 0.5
    for sx in (-1, 1):
        mat = s["fit"] if level > 1 else s["rope"]
        k.beam("hanger", end + Vector((sx * 0.36, 0, 0)), Vector((sx * 0.55, end.y, box_top)), (0.07, 0.03) if level > 1 else (0.05, 0.05), mat, parent=t, bevel=False)
    c = Vector((0, end.y, box_top - 0.55))
    if level <= 2:
        _stone_box(k, t, c, s, strapped=level == 2)
    elif level <= 4:
        _iron_chest(k, t, c, s)
    else:
        _silver_weight(k, t, c, s)
    _tag(before, "cw")
    before = set(bpy.data.objects)
    # sling: two lines from the arm tip forward along the trough to the pouch and its round
    pouch = POUCH
    for sx in (-1, 1):
        k.tube("sling", TIP0 + Vector((sx * 0.08, 0, 0)), pouch + Vector((sx * 0.3, 0, 0.04)),
               0.016 if level < 4 else 0.013, s["cable"], parent=t, segs=8, bevel=False)
    if level >= 4:
        for i in range(10):                                  # chain links on the metal sling
            p = TIP0.lerp(pouch, 0.12 + i * 0.07) + Vector((0.08, 0, 0.01))
            k.torus("link", 0.035, 0.008, p, s["cable"], rot=(0, math.pi / 2 * (i % 2), math.pi / 2),
                    parent=t, segs=10, tube_segs=5)
    po = k.lathe("pouch", [(-0.4, 0.0), (-0.36, 0.16), (-0.14, 0.3), (0.14, 0.3), (0.36, 0.16), (0.4, 0.0)],
                 "leather", segs=20, loc=pouch, parent=t)
    po.scale = (1.0, 1.0, 0.45)
    _tag(before, "sling")
    before = set(bpy.data.objects)
    _projectile(k, t, pouch + Vector((0, 0, 0.3)), PROJ_R, level, seed=1)
    _tag(before, "round")
    # spare rounds in a cradle at the front of the frame, where the camera sees them
    for sx in (-1, 1):
        k.beam("cradle", (sx * 0.85, 1.25, 0.32), (sx * 0.85, 1.95, 0.32), (0.16, 0.14), s["wood"], parent=t,
               bevel=0.01)
    for i, sx in enumerate((-0.42, 0.42)):
        _projectile(k, t, Vector((sx, 1.6, 0.39 + PROJ_R)), PROJ_R, level, seed=2 + i)


PROJ_R = 0.3     # radius of the round, m (larger than history so it reads at game zoom)


def _ball(k, parent, loc, r, mat, subdiv=3):
    me = bpy.data.meshes.new("ball")
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=r)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new("ball", me)
    o.location = loc
    return k._finish(o, mat, bevel=False, parent=parent)


def _projectile(k, t, c, r, level, seed):
    """What the machine throws: stone, iron-bound stone, cast-iron ball, spiked iron ball,
    silver orb banded in gold."""
    c = Vector(c)
    if level <= 2:
        _rock(k, t, c, r * 1.02, seed=40 + seed + level * 7, rounded=True)
        if level == 2:                                       # two crossed iron straps
            for a in (0.0, math.pi / 2):
                k.torus("strap", r * 0.9, 0.032, c, "iron_forged", rot=(math.pi / 2, 0, a), parent=t, segs=24,
                        tube_segs=6)
        return
    if level == 3:
        _ball(k, t, c, r, "iron_forged")
        k.torus("lug", 0.06, 0.016, c + Vector((0, 0, r + 0.04)), "iron_forged", rot=(math.pi / 2, 0, 0),
                parent=t, segs=12, tube_segs=5)
        return
    if level == 4:
        _ball(k, t, c, r * 0.92, "iron_black")
        k.torus("band", r * 0.92, 0.035, c, "bronze_old", parent=t, segs=28, tube_segs=6)
        rnd = random.Random(seed)
        for i in range(14):                                  # spikes, evenly spread on the sphere
            zf = 1 - 2 * (i + 0.5) / 14
            a = i * 2.39996 + rnd.uniform(-0.1, 0.1)
            d = Vector((math.sqrt(1 - zf * zf) * math.cos(a), math.sqrt(1 - zf * zf) * math.sin(a), zf))
            k.cylinder("spike", 0.055, 0.2, c + d * (r * 0.92 + 0.08), "iron_forged", segs=8, radius_top=0.004,
                       rot=d.to_track_quat("Z", "Y").to_euler(), parent=t, bevel=False)
        return
    _ball(k, t, c, r * 0.95, "silver_satin")
    for a in (0.0, math.pi / 2):
        k.torus("band", r * 0.96, 0.03, c, "gold_trim", rot=(math.pi / 2, 0, a), parent=t, segs=28, tube_segs=6)
    k.torus("band", r * 0.96, 0.03, c, "gold_trim", parent=t, segs=28, tube_segs=6)


def _stone_box(k, t, c, s, strapped=False):
    W = s["arm"]
    w, d, h = 1.3, 1.1, 1.1
    for i in range(5):                                       # plank walls, nailed to corner posts
        zz = c.z - h / 2 + (i + 0.5) * h / 5
        for sy in (-1, 1):
            k.beam("cw_plank", (-w / 2, c.y + sy * d / 2, zz), (w / 2, c.y + sy * d / 2, zz), (0.05, h / 5 - 0.012),
                   W, parent=t, bevel=0.006)
        for sx in (-1, 1):
            k.beam("cw_plank", (sx * w / 2, c.y - d / 2, zz), (sx * w / 2, c.y + d / 2, zz), (0.05, h / 5 - 0.012),
                   W, parent=t, bevel=0.006)
    for sx in (-1, 1):
        for sy in (-1, 1):
            k.beam("cw_corner", (sx * (w / 2 + 0.03), c.y + sy * (d / 2 + 0.03), c.z - h / 2 - 0.04),
                   (sx * (w / 2 + 0.03), c.y + sy * (d / 2 + 0.03), c.z + h / 2 + 0.04), (0.1, 0.1), W, parent=t,
                   bevel=0.008)
    if strapped:                                             # iron straps round the box
        for zz in (-0.36, 0.36):
            k.box("cw_strap", (w + 0.1, d + 0.1, 0.07), c + Vector((0, 0, zz)), "iron_forged", parent=t,
                  bevel=0.005)
    k.box("cw_fill", (w - 0.05, d - 0.05, 0.1), (c.x, c.y, c.z + h / 2 - 0.12), "dirt_fill", parent=t,
          bevel=False)
    rnd = random.Random(4)
    for i in range(16):                                      # field stones heaped on top
        p = Vector((rnd.uniform(-0.48, 0.48), c.y + rnd.uniform(-0.4, 0.4), c.z + h / 2 - 0.02))
        _rock(k, t, p, rnd.uniform(0.09, 0.17), seed=100 + i)


def _iron_chest(k, t, c, s):
    w, d, h = 1.3, 1.1, 1.1
    k.box("cw_chest", (w, d, h), c, s["wood"], parent=t, bevel=0.02)
    for zz in (-0.42, 0.0, 0.42):                            # iron hoops round the chest
        k.box("cw_hoop", (w + 0.03, d + 0.03, 0.08), c + Vector((0, 0, zz)), s["fit"], parent=t, bevel=0.005)
    for sx in (-1, 1):
        for sy in (-1, 1):
            k.box("cw_corner", (0.1, 0.1, h + 0.04), c + Vector((sx * w / 2, sy * d / 2, 0)), s["fit"], parent=t,
                  bevel=0.008)
            for zz in (-0.42, 0.0, 0.42):
                k.cylinder("rivet", 0.025, 0.02, c + Vector((sx * (w / 2 + 0.02), sy * 0.3, zz)), s["bolt"],
                           segs=8, rot=(0, sx * math.pi / 2, 0), parent=t, bevel=False)
    k.torus("cw_ring", 0.1, 0.02, c + Vector((0, 0, h / 2 + 0.02)), s["fit"], parent=t, segs=16, tube_segs=6)


def _silver_weight(k, t, c, s):
    w, d, h = 1.3, 1.1, 1.1
    k.box("cw_block", (w, d, h), c, "silver", parent=t, bevel=0.07)
    k.box("cw_band", (w + 0.03, d + 0.03, 0.12), c + Vector((0, 0, 0.32)), s["fit"], parent=t, bevel=0.01)
    k.box("cw_band", (w + 0.03, d + 0.03, 0.06), c + Vector((0, 0, -0.42)), s["fit"], parent=t, bevel=0.01)
    for sy in (-1, 1):                                       # crest on the faces the camera sees
        k.cylinder("crest", 0.22, 0.03, c + Vector((0, sy * (d / 2 + 0.005), -0.05)), s["fit"], segs=32,
                   rot=(-sy * math.pi / 2, 0, 0), parent=t)
        k.cylinder("crest_in", 0.15, 0.04, c + Vector((0, sy * (d / 2 + 0.01), -0.05)), "silver", segs=6,
                   rot=(-sy * math.pi / 2, 0, 0), parent=t)
    for sx in (-1, 1):
        k.cylinder("crest", 0.22, 0.03, c + Vector((sx * (w / 2 + 0.005), 0, -0.05)), s["fit"], segs=32,
                   rot=(0, sx * math.pi / 2, 0), parent=t)


def _windlass(k, t, level, s):
    W = s["wood"]
    y, z = -2.95, 0.72
    k.tube("drum", (-0.95, y, z), (0.95, y, z), 0.17, s["arm"], parent=t, segs=20)
    for sx in (-1, 1):
        x = sx * 1.32
        k.tube("hub", (sx * 0.9, y, z), (x + sx * 0.1, y, z), 0.07, s["fit"] if level > 1 else W, parent=t, segs=12)
        r = 0.5
        k.torus("wheel_rim", r, 0.045, (x, y, z), W if level == 1 else s["fit"], rot=(0, math.pi / 2, 0), parent=t,
                segs=32, tube_segs=8)
        for i in range(8):                                   # spokes that double as handles
            a = 2 * math.pi * i / 8
            d = Vector((0, math.cos(a), math.sin(a)))
            k.tube("spoke", Vector((x, y, z)), Vector((x, y, z)) + d * (r + 0.18), 0.028,
                   s["arm"], parent=t, segs=8, bevel=False)
    rope_mat = s["rope"]
    back = Vector((0, -math.cos(COCK), -math.sin(COCK)))
    tip = PIVOT - Vector((0, 0, PLATFORM_Z)) + back * LONG
    k.hose("winch_rope", [(0, y, z + 0.17), (0, y - 0.3, z + 0.2), (0, tip.y + 0.15, tip.z - 0.05)], 0.02,
           rope_mat, parent=t)


def build_round(k, parent, level):
    """The round of this level alone, centred on `parent` (for the flying-round sprites)."""
    _projectile(k, parent, Vector((0, 0, 0)), PROJ_R, level, seed=1)
