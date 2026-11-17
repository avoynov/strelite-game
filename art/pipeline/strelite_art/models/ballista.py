"""Repeating torsion ballista (bg: „Самострел“): light, cheap and as fast as a machine gun,
with little damage per bolt. A polybolos: bolts drop one by one from a hopper into the
trough, and turning the crank runs the slider forward, hooks the string, draws it back and
looses it, over and over. Built a little larger than history so it reads at game zoom:
two twisted rope skeins in a 1.5 m frame, arms 1.15 m, a 2.9 m stock, on a yoke that turns
on a tripod post. Front is local +Y.

Levels change the machine and its bolt, in the same language as the trebuchet:
  1  rough-hewn timber, rope lashings, hemp skeins, a plank hopper; iron-tipped bolts
  2  tarred timber with iron bands; iron heads, leather fletching
  3  dark oak under black iron straps, iron-capped skeins; long iron heads
  4  frame of blackened iron with bronze fittings and arm guards; barbed heads
  5  silver frame with gold fittings, silver-wire skeins; gold-headed bolts

Returns (root, turret). The tripod is static; the turret (yoke and machine) turns.

Firing animation: set_fire_frame(f) poses frame f of FIRE (1-based; 0 = cocked). One loop
is one shot: the arms snap forward and the bolt leaves at RELEASE_FRAME, the slider runs
forward, hooks the string and draws it back, and the next bolt drops from the hopper. Loop
it while a target is in range. Call only after materials_photoreal.stamp(), which must see
the machine cocked.
"""
import math

import bpy
from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit
from .trebuchet import _band, _ball  # noqa: F401  (same joint language as the trebuchet)

LEVELS = (1, 2, 3, 4, 5)
FRAME_M = 8.0
TARGET_Z = 1.2
SPRITE_FRAME_M = 9.0
SWEEP_M = 2.2
FOOTPRINT_M = 3.0        # 2x2 tiles of 4 m
Z = 1.55                 # height of the stock's top / line of the bolt
SKEIN_X, FRAME_Y = 0.46, 0.7
ARM_L = 1.15
COCK_DEG = 40            # arms swept back this much from straight out sideways
CLAW_Y0 = -1.15          # claw (and string) when cocked
TILT = math.radians(3)   # stock raised a little at the front

STYLE = {
    1: dict(wood="timber_raw", arm="timber_raw", fit="iron_forged", rope="hemp", skein="hemp",
            bolt=None, band_w=0.07, head="iron_forged", shaft="timber_raw", fletch="hemp", mag=True),
    2: dict(wood="timber_tarred", arm="timber_tarred", fit="iron_forged", rope="hemp", skein="hemp",
            bolt=None, band_w=0.07, head="iron_forged", shaft="timber_tarred", fletch="leather", mag=True),
    3: dict(wood="timber_oak", arm="timber_oak", fit="iron_black", rope="hemp", skein="hemp",
            bolt="iron_black", band_w=0.1, head="iron_black", shaft="timber_oak", fletch="leather",
            mag=True),
    4: dict(wood="iron_black", arm="timber_oak", fit="bronze_old", rope="hemp", skein="hemp",
            bolt="bronze_old", band_w=0.09, head="iron_black", shaft="timber_oak", fletch="bronze_old",
            mag=True),
    5: dict(wood="silver_satin", arm="silver_satin", fit="gold_trim", rope="steel_cable",
            skein="steel_cable", bolt="gold_trim", band_w=0.08, head="gold_trim", shaft="silver_satin",
            fletch="gold_trim", mag=True),
}

# Firing animation, one row per frame: arm sweep (deg back; 40 = cocked), slider shift
# forward (m), string on the claw, bolt shift forward (m, None = gone), windlass turn (deg).
FIRE = [
    (6, 0.0, False, 0.75, 60),     # 1  loosed: arms flying forward, bolt leaving
    (-12, 0.0, False, None, 120),  # 2  release: the bolt is away
    (-4, 0.92, True, None, 180),   # 3  crank runs the slider forward, claw over the string
    (14, 0.6, True, None, 240),    # 4  drawing back
    (28, 0.3, True, None, 300),    # 5
    (40, 0.0, True, 0.0, 360),     # 6  cocked, the next bolt dropped from the hopper
]
FIRE_FRAMES = len(FIRE)
RELEASE_FRAME = 2
RELOAD_FROM = 3
FIRE_FPS = 24            # one shot per loop: four shots a second
LOOP = True
BOLT_LEN = 1.15
ROUND_DIRS = 32          # the flying bolt is drawn per heading, not tumbling
ROUND_FRAME_M = 1.6
_RIG = {}


def build(style, level=1):
    k = Kit(style)
    s = STYLE[level]
    root = k.empty("ballista")
    _tripod(k, root, level, s)
    turret = k.empty("turret", (0, 0, 0), parent=root)
    turret["node"] = "turret"
    mp.set_reference(turret)
    _yoke(k, turret, level, s)
    _stock(k, turret, level, s)
    _capitulum(k, turret, level, s)
    _windlass(k, turret, level, s)
    _quiver(k, turret, level, s)
    m = k.empty("muzzle", (0, 1.25, Z + 0.12), parent=turret)
    m["marker"] = "muzzle"
    _rig(k, turret, level, s)
    return root, turret


def ground(level):
    from ..terrain import Patch
    return Patch(r_solid=FOOTPRINT_M, r_out=FOOTPRINT_M + 0.6, r_bare=2.5, seed=53, ragged=0.5)


def _tag(before, role):
    for o in set(bpy.data.objects) - before:
        o["rig"] = role


def _beam(k, t, name, p0, p1, sec, mat):
    return k.beam(name, p0, p1, sec, mat, parent=t, bevel=0.008)


# -- static tripod --------------------------------------------------------------------------
def _tripod(k, root, level, s):
    W = s["wood"]
    _beam(k, root, "post", (0, 0, 0.0), (0, 0, 1.08), (0.22, 0.22), W)
    for i in range(3):
        a = math.radians(90 + 120 * i)
        foot = Vector((1.25 * math.cos(a), 1.25 * math.sin(a), 0.06))
        _beam(k, root, "leg", foot, (0, 0, 0.75), (0.13, 0.13), W)
        _beam(k, root, "foot", foot * 0.15 + Vector((0, 0, 0.0)), foot + Vector((0, 0, -0.02)), (0.12, 0.1), W)
        _beam(k, root, "brace", foot * 0.55 + Vector((0, 0, 0.05)), (0, 0, 0.35), (0.08, 0.08), W)
        _band(k, root, Vector((0, 0, 0.75)) + (foot - Vector((0, 0, 0.75))) * 0.06, foot - Vector((0, 0, 0.75)),
              (0.13, 0.13), level, s)
    _band(k, root, (0, 0, 0.95), (0, 0, 1), (0.22, 0.22), level, s, width=0.1)
    k.cylinder("turn_plate", 0.2, 0.05, (0, 0, 1.06), s["fit"] if level > 1 else "iron_forged", segs=20,
               parent=root)


# -- turret --------------------------------------------------------------------------------
def _yoke(k, t, level, s):
    W = s["wood"]
    k.cylinder("yoke_hub", 0.17, 0.12, (0, 0, 1.1), W, segs=16, parent=t)
    for sx in (-1, 1):
        _beam(k, t, "yoke_cheek", (sx * 0.2, -0.05, 1.12), (sx * 0.2, -0.05, Z - 0.1), (0.08, 0.3), W)
        k.cylinder("trunnion", 0.06, 0.06, (sx * 0.27, -0.05, Z - 0.2), s["fit"] if level > 1 else W, segs=12,
                   rot=(0, math.pi / 2, 0), parent=t)
    _beam(k, t, "yoke_bar", (-0.24, -0.05, 1.14), (0.24, -0.05, 1.14), (0.12, 0.1), W)
    # prop from the hub to the rear of the stock, setting the elevation
    _beam(k, t, "elev_prop", (0, -0.1, 1.12), (0, -1.15, Z - 0.17), (0.07, 0.07), W)


def _z(y):
    return Z + y * math.tan(TILT)


def _stock(k, t, level, s):
    W = s["wood"]
    y0, y1 = -2.0, FRAME_Y + 0.25
    _beam(k, t, "case", (0, y0, _z(y0) - 0.14), (0, y1, _z(y1) - 0.14), (0.3, 0.2), W)
    for sx in (-1, 1):                                   # the slider runs between two rails
        _beam(k, t, "rail", (sx * 0.12, y0 + 0.05, _z(y0) - 0.02), (sx * 0.12, y1, _z(y1) - 0.02), (0.06, 0.05), W)
    for f in (0.12, 0.45, 0.8):
        p = Vector((0, y0 + (y1 - y0) * f, _z(y0 + (y1 - y0) * f) - 0.14))
        _band(k, t, p, (0, 1, 0), (0.3, 0.2), level, s)
    # ratchet at the rear
    k.cylinder("ratchet", 0.1, 0.04, (0.18, -1.75, _z(-1.75) - 0.05), s["fit"] if level > 1 else "iron_forged",
               segs=12, rot=(0, math.pi / 2, 0), parent=t)


def _capitulum(k, t, level, s):
    """The torsion frame: two skeins of twisted rope between top and bottom beams."""
    W = s["wood"]
    y = FRAME_Y
    zt, zb = _z(y) + 0.42, _z(y) - 0.36
    for z in (zt, zb):
        _beam(k, t, "frame_beam", (-0.78, y, z), (0.78, y, z), (0.2, 0.12), W)
    for x in (-0.72, -0.2, 0.2, 0.72):                   # four stiles
        _beam(k, t, "stile", (x, y, zb - 0.06), (x, y, zt + 0.06), (0.11, 0.14), W)
    for sx in (-1, 1):
        x = sx * SKEIN_X
        k.cylinder("skein", 0.11, zt - zb - 0.06, (x, y, zb + 0.03), s["skein"], segs=16, parent=t, bevel=False)
        for i in range(5):                               # the coils of the twisted rope
            k.torus("skein_coil", 0.112, 0.012, (x, y, zb + 0.1 + i * (zt - zb - 0.2) / 4), s["skein"],
                    parent=t, segs=16, tube_segs=5)
        for z, sg in ((zt + 0.06, 1), (zb - 0.06, -1)):  # washers and their levers
            k.cylinder("washer", 0.15, 0.05, (x, y, z - (0.05 if sg < 0 else 0)), s["fit"] if level > 1 else W,
                       segs=20, parent=t)
            _beam(k, t, "washer_lever", (x - 0.17, y, z + sg * 0.03), (x + 0.17, y, z + sg * 0.03), (0.04, 0.04),
                  s["fit"] if level > 1 else "iron_forged")
        if level >= 3:                                   # iron plates on the outer stiles
            k.box("frame_plate", (0.14, 0.03, 0.6), (sx * 0.72, y + 0.085, _z(y) + 0.03), s["fit"], parent=t,
                  bevel=0.005)
    if level >= 3:
        for z in (zt, zb):
            k.box("beam_plate", (1.6, 0.03, 0.08), (0, y + 0.075, z), s["fit"], parent=t, bevel=0.004)
    # breastwork in front: a curved guard for the arms on levels 4 and 5
    if level >= 4:
        for sx in (-1, 1):
            _beam(k, t, "guard", (sx * 0.2, y + 0.08, zt + 0.02), (sx * 1.25, y - 0.15, zt - 0.12), (0.05, 0.05),
                  s["fit"])


def _windlass(k, t, level, s):
    W = s["wood"]
    y = -1.78
    z = _z(y) - 0.08
    for sx in (-1, 1):
        _beam(k, t, "winch_cheek", (sx * 0.2, y - 0.12, z - 0.2), (sx * 0.2, y + 0.12, z - 0.2), (0.06, 0.32), W)
    k.empty("drum_pivot", (0, y, z), parent=t)["rig_name"] = "drum"


def _quiver(k, t, level, s):
    """Spare bolts in a box on the left of the stock, where the camera sees them."""
    W = s["wood"]
    c = Vector((-0.32, -0.75, _z(-0.75) - 0.3))
    k.box("quiver", (0.2, 0.5, 0.3), c, W, parent=t, bevel=0.01)
    if level > 1:
        k.box("quiver_band", (0.22, 0.04, 0.32), c + Vector((0, 0.15, 0)), s["fit"], parent=t, bevel=0.003)
    for i in range(4):
        p = c + Vector((-0.04 + 0.06 * (i % 2), -0.1 + 0.08 * (i // 2), 0.1))
        _bolt(k, t, p, Vector((0, 0.35, 1)).normalized(), level, s, length=0.9)


def _bolt(k, t, tail, d, level, s, length=BOLT_LEN):
    """A bolt from its tail along direction d: shaft, head and three vanes."""
    d = Vector(d).normalized()
    tail = Vector(tail)
    tip = tail + d * length
    k.tube("bolt_shaft", tail, tip - d * 0.16, 0.02, s["shaft"], parent=t, segs=8, bevel=False)
    rot = d.to_track_quat("Z", "Y").to_euler()
    hl = 0.2 if level < 3 else 0.26
    k.cylinder("bolt_head", 0.045 if level != 4 else 0.055, hl, tip - d * hl, s["head"], segs=4, rot=rot, parent=t,
               radius_top=0.002, bevel=False)
    if level == 4:                                       # barbs
        side = d.cross(Vector((0, 0, 1)))
        if side.length < 0.1:
            side = d.cross(Vector((1, 0, 0)))
        side.normalize()
        for sg in (-1, 1):
            k.tube("barb", tip - d * 0.2 + side * sg * 0.03, tip - d * 0.3 + side * sg * 0.09, 0.008, s["head"],
                   parent=t, segs=4, bevel=False)
    up = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
    for i in range(3):                                   # fletching vanes
        a = 2 * math.pi * i / 3
        side = d.cross(up).normalized()
        n = (side * math.cos(a) + d.cross(side) * math.sin(a)).normalized()
        k.beam("vane", tail + d * 0.05 + n * 0.04, tail + d * 0.32 + n * 0.035, (0.008, 0.07), s["fletch"],
               parent=t, bevel=False, section_end=(0.006, 0.05))


# -- the moving parts and the firing animation ----------------------------------------------
def _arm_dir(sx, sweep_deg):
    a = math.radians(sweep_deg)
    return Vector((sx * math.cos(a), -math.sin(a), 0.0))


def _tip(sx, sweep_deg):
    return Vector((sx * SKEIN_X, FRAME_Y, _z(FRAME_Y))) + _arm_dir(sx, sweep_deg) * ARM_L


def _rig(k, t, level, s):
    W = s["arm"]
    zc = _z(FRAME_Y)
    arms = {}
    for sx in (-1, 1):                                   # arms, built cocked, under their pivots
        piv = k.empty(f"arm_pivot_{'L' if sx < 0 else 'R'}", (sx * SKEIN_X, FRAME_Y, zc), parent=t)
        d = _arm_dir(sx, COCK_DEG)
        a0 = Vector((sx * SKEIN_X, FRAME_Y, zc))
        for o in (k.beam("arm", a0 + d * 0.05, a0 + d * ARM_L, (0.13, 0.18), W, parent=t, bevel=0.01,
                         section_end=(0.08, 0.1)),
                  k.box("arm_tip", (0.08, 0.08, 0.1), a0 + d * (ARM_L - 0.02), s["fit"] if level > 1 else "iron_forged",
                        parent=t, bevel=0.006)):
            _keep_world(o, piv)
        if level > 1:
            _keep_world(k.beam("arm_band", a0 + d * 0.45, a0 + d * 0.52, (0.12, 0.16), s["fit"], parent=t,
                               bevel=0.003), piv)
        arms[sx] = piv
    slider = k.empty("slider", (0, 0, 0), parent=t)
    zs = _z(CLAW_Y0) + 0.06
    for o in (k.beam("slider_bar", (0, CLAW_Y0 - 0.45, zs - 0.03), (0, FRAME_Y + 0.35, _z(FRAME_Y + 0.35) + 0.03),
                     (0.16, 0.07), W, parent=t, bevel=0.006),
              k.box("claw", (0.1, 0.14, 0.12), (0, CLAW_Y0 - 0.05, zs + 0.07), s["fit"] if level > 1 else "iron_forged",
                    parent=t, bevel=0.01),
              k.tube("trigger", (0.07, CLAW_Y0 - 0.12, zs + 0.02), (0.15, CLAW_Y0 - 0.35, zs - 0.12), 0.02,
                     s["fit"] if level > 1 else "iron_forged", parent=t, segs=6, bevel=False)):
        _keep_world(o, slider)
    _hopper(k, t, level, s, zs)
    drum = next(o for o in t.children if o.get("rig_name") == "drum")
    y, z = drum.location.y, drum.location.z
    parts = [k.tube("drum", (-0.17, y, z), (0.17, y, z), 0.09, W, parent=t, segs=14)]
    for sx in (-1, 1):                                   # a crank each side, and the drive sprocket
        a0 = 0.6 if sx > 0 else 0.6 + math.pi
        r = Vector((0, math.cos(a0), math.sin(a0)))
        hub = Vector((sx * 0.27, y, z))
        parts.append(k.tube("crank_axle", (sx * 0.17, y, z), hub, 0.03, s["fit"] if level > 1 else W, parent=t,
                            segs=8, bevel=False))
        parts.append(k.beam("crank", hub, hub + r * 0.36, (0.05, 0.05), s["fit"] if level > 1 else W, parent=t,
                            bevel=0.004))
        parts.append(k.tube("crank_handle", hub + r * 0.36, hub + r * 0.36 + Vector((sx * 0.22, 0, 0)), 0.028, W,
                            parent=t, segs=8, bevel=False))
        parts.append(k.cylinder("sprocket", 0.13, 0.04, (sx * 0.24 - 0.02, y, z), s["fit"] if level > 1 else W,
                                segs=5, rot=(0, math.pi / 2, 0), parent=t, bevel=0.004))
    for o in parts:
        _keep_world(o, drum)
    for sx in (-1, 1):                                   # front sprocket and the chain along the case
        yf = FRAME_Y - 0.3
        zf = _z(yf) - 0.08
        k.cylinder("sprocket", 0.1, 0.04, (sx * 0.2, yf, zf), s["fit"] if level > 1 else W, segs=5,
                   rot=(0, math.pi / 2, 0), parent=t, bevel=0.004)
        for dz in (0.11, -0.11):
            k.beam("chain", (sx * 0.2, y, z + dz), (sx * 0.2, yf, zf + dz * 0.8), (0.025, 0.02),
                   "iron_forged" if level < 5 else "gold_trim", parent=t, bevel=False)
    # the loaded bolt, on its own carrier so it can fly off
    carrier = k.empty("bolt_carrier", (0, 0, 0), parent=t)
    before = set(bpy.data.objects)
    _bolt(k, t, (0, CLAW_Y0 - 0.02, zs + 0.09), (0, 1, math.tan(TILT)), level, s)
    for o in set(bpy.data.objects) - before:
        _keep_world(o, carrier)
    # bowstring halves: unit tubes along local Z, posed per frame
    strings = []
    for sx in (-1, 1):
        o = k.cylinder("string", 0.021, 1.0, (0, 0, 0), s["rope"], segs=6, parent=t, bevel=False)
        strings.append((sx, o))
    _RIG.update(t=t, arms=arms, slider=slider, drum=drum, carrier=carrier, strings=strings, zs=zs)
    set_fire_frame(0)


def _hopper(k, t, level, s, zs):
    """The bolt hopper over the trough: bolts stacked one above the other, heads out at the
    front and fletching out at the back, so the stack reads from any side."""
    W = s["wood"]
    y0, y1 = CLAW_Y0 + 0.2, CLAW_Y0 + 0.95
    zb = zs + 0.24
    h = 0.5
    ym = (y0 + y1) / 2
    for sx in (-1, 1):
        k.box("hopper_side", (0.04, y1 - y0, h), (sx * 0.14, ym, _z(ym) - Z + zb + h / 2), W, parent=t, bevel=0.006)
        for yy in (y0 + 0.04, y1 - 0.04):
            k.box("hopper_post", (0.06, 0.06, h + 0.25), (sx * 0.14, yy, _z(yy) - Z + zb + h / 2 - 0.12), W, parent=t,
                  bevel=0.006)
    for yy in (y0 + 0.12, y1 - 0.12):
        if level == 1:
            k.torus("hopper_lashing", 0.17, 0.016, (0, yy, _z(yy) - Z + zb + h * 0.7), s["rope"],
                    rot=(math.pi / 2, 0, 0), parent=t, segs=16, tube_segs=5)
        else:
            k.box("hopper_band", (0.32, 0.05, 0.06), (0, yy, _z(yy) - Z + zb + h * 0.75), s["fit"], parent=t,
                  bevel=0.003)
    for i in range(5):                                   # the stack of bolts
        tail = Vector((0, CLAW_Y0 - 0.02, zb + 0.06 + i * 0.085))
        _bolt(k, t, tail, (0, 1, math.tan(TILT)), level, s)


def _keep_world(o, parent):
    bpy.context.view_layer.update()
    mw = o.matrix_world.copy()
    o.parent = parent
    o.matrix_world = mw


def _pose(f):
    if f == 0:
        return COCK_DEG, 0.0, True, 0.0, 0
    return FIRE[f - 1]


def _apply(sweep, slide, hooked, bolt, drum_deg):
    for sx, piv in _RIG["arms"].items():
        piv.rotation_euler = (0, 0, sx * math.radians(sweep - COCK_DEG) * -1)
    _RIG["slider"].location = (0, slide, slide * math.tan(TILT))
    _RIG["drum"].rotation_euler = (math.radians(-drum_deg), 0, 0)
    _RIG["carrier"].location = (0, bolt or 0.0, (bolt or 0.0) * math.tan(TILT))
    claw = Vector((0, CLAW_Y0 + slide, _RIG["zs"] + 0.1 + slide * math.tan(TILT)))
    for sx, o in _RIG["strings"]:
        tip = _tip(sx, sweep) + Vector((0, 0, 0.0))
        end = claw if hooked else Vector((0, tip.y, tip.z))
        d = end - tip
        o.location = tip
        o.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
        o.scale = (1, 1, max(d.length, 0.01))


def key_fire_animation(scene):
    prefs = bpy.context.preferences.edit
    old = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = "LINEAR"
    for f in range(FIRE_FRAMES + 1):
        _apply(*_pose(f))
        for piv in _RIG["arms"].values():
            piv.keyframe_insert("rotation_euler", frame=f)
        for o, paths in ((_RIG["slider"], ("location",)), (_RIG["drum"], ("rotation_euler",)),
                         (_RIG["carrier"], ("location",))):
            for p in paths:
                o.keyframe_insert(p, frame=f)
        for _, o in _RIG["strings"]:
            for p in ("location", "rotation_euler", "scale"):
                o.keyframe_insert(p, frame=f)
    prefs.keyframe_new_interpolation_type = old
    scene.frame_set(0)


def set_fire_frame(f, scene=None):
    sweep, slide, hooked, bolt, drum_deg = _pose(f)
    if scene is not None and _RIG["slider"].animation_data is not None:
        scene.frame_set(f)
    else:
        _apply(sweep, slide, hooked, bolt, drum_deg)
    for o in _RIG["carrier"].children:
        o.hide_render = bolt is None
    bpy.context.view_layer.update()


def build_round(k, parent, level):
    """The flying bolt of this level, centred on `parent`, pointing along +Y."""
    _bolt(k, parent, (0, -BOLT_LEN / 2, 0), (0, 1, 0), level, STYLE[level])
