"""Siphon of Greek fire (bg: „Гръцки огън“): a pressure vessel of burning oil, a pump and a
long siphon tube with a nozzle on a turning carriage. Short range, a ramping stream of fire
(the stream itself is an effect, see render_effects.py). Front is local +Y.

Every level adds a new kind of mechanism that explains a hotter, longer stream:
  1  clay jars of oil in a wooden rack, a hand pump with one lever, a leather hose,
     a plain iron nozzle
  2  a copper cauldron heated over a brazier (hot oil flows farther), copper piping
  3  a bronze vessel and a double-acting pump on a rocking beam; a flared bronze bell nozzle
  4  an armoured iron tank with bellows on the fire, a gauge and a safety valve; a hooded
     nozzle with a pilot flame
  5  silver and gold: a bank of pressure flasks feeds the tank; a gold dragon-head nozzle
The traverse changes too: a swivel post (1), an iron ring with push bars (2), wheels on a
round plank track (3), a toothed ring and crank (4, 5).

Returns (root, turret). The platform is static; the carriage turns.

Firing animation: the pump lever (or rocking beam) works up and down while the stream
flows; LOOP it while a target is in range. set_fire_frame(f) poses frame f (0 = rest).
"""
import math

import bpy
from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit
from . import faction as fx
from .ballista import _beam, _keep_world
from .trebuchet import _ball

LEVELS = (1, 2, 3, 4, 5)
FRAME_M = 7.0
TARGET_Z = 0.9
SPRITE_FRAME_M = 8.0
SWEEP_M = 2.4
FOOTPRINT_M = 3.0        # 2x2 tiles of 4 m
DECK_Z = 0.42

STYLE = {
    1: dict(wood="timber_raw", fit="iron_forged", pipe="hose", nozzle="iron_forged", vessel="clay",
            rope="hemp", plat="timber_raw"),
    2: dict(wood="timber_varnish", fit="iron_forged", pipe="copper", nozzle="copper", vessel="copper",
            rope="hemp", plat="timber_varnish"),                 # copper and lacquered wood (user 2026-11-22)
    3: dict(wood="timber_oak", fit="bronze_old", pipe="bronze_old", nozzle="bronze_old", vessel="bronze_old",
            rope="hemp", plat="timber_oak"),
    4: dict(wood="timber_oak", fit="iron_black", pipe="bronze_old", nozzle="iron_black", vessel="iron_black",
            rope="hemp", plat="timber_oak"),
    5: dict(wood="silver_satin", fit="gold_trim", pipe="gold_trim", nozzle="gold_trim", vessel="silver_satin",
            rope="steel_cable", plat="timber_oak"),
}

FIRE = [24 * math.sin(2 * math.pi * i / 8) for i in range(1, 9)]     # lever angle (deg) per frame
FIRE_FRAMES = len(FIRE)
RELEASE_FRAME = 1        # the stream flows from the first frame
RELOAD_FROM = FIRE_FRAMES
FIRE_FPS = 16
LOOP = True
_RIG = {}


def build(style, level=1):
    k = Kit(style)
    s = STYLE[level]
    root = k.empty("greekfire")
    _platform(k, root, level, s)
    _fuel_pile(k, root, level, s)
    turret = k.empty("turret", (0, 0, 0), parent=root)
    turret["node"] = "turret"
    mp.set_reference(turret)
    _carriage(k, turret, level, s)
    _vessel(k, turret, level, s)
    tip = _siphon(k, turret, level, s)
    m = k.empty("muzzle", tip, parent=turret)
    m["marker"] = "muzzle"
    _pump(k, turret, level, s)
    set_fire_frame(0)
    return root, turret


def ground(level):
    from ..terrain import Patch
    return Patch(r_solid=FOOTPRINT_M, r_out=FOOTPRINT_M + 0.6, r_bare=2.5, seed=83, ragged=0.5)


# -- static platform and traverse ------------------------------------------------------------
def _platform(k, root, level, s):
    W = s["plat"]
    for i in range(7):                                   # a square plank floor on two sleepers
        x = -1.2 + i * 0.4
        k.box("plank", (0.38, 2.6, 0.08), (x, 0, 0.16), W, parent=root, bevel=0.008)
    for y in (-1.0, 1.0):
        k.box("sleeper", (2.8, 0.22, 0.14), (0, y, 0.07), W, parent=root, bevel=0.01)
    k.cylinder("swivel_post", 0.16, 0.2, (0, 0, 0.2), s["fit"] if level > 1 else W, segs=16, parent=root)
    if level == 2:                                       # iron ring the carriage slides on
        k.torus("slide_ring", 0.9, 0.035, (0, 0, 0.22), "iron_forged", parent=root, segs=48, tube_segs=6)
    if level >= 3:                                       # round plank track for the carriage wheels
        k.torus("track", 1.05, 0.05, (0, 0, 0.22), s["fit"] if level > 3 else "iron_forged", parent=root, segs=56,
                tube_segs=6)
    if level >= 4:                                       # toothed ring on the post
        m = s["fit"]
        k.cylinder("traverse_ring", 0.42, 0.05, (0, 0, 0.21), m, segs=40, parent=root)
        for i in range(30):
            a = 2 * math.pi * i / 30
            d = Vector((math.cos(a), math.sin(a), 0))
            k.box("tooth", (0.05, 0.03, 0.05), d * 0.44 + Vector((0, 0, 0.235)), m, rot=(0, 0, a), parent=root,
                  bevel=False)


def _fuel_pile(k, root, level, s):
    """Spare fuel on the ground beside the machine, in this level's vessels."""
    from .trebuchet import ground_spot
    c = ground_spot(2.55, -40)
    for i, off in enumerate(((0, 0), (0.42, 0.1), (-0.36, 0.2), (0.1, 0.42))):
        p = c + Vector((off[0], off[1], 0.0))
        if level == 1:                                   # clay amphorae, one lying down
            o = _amphora(k, root, p, 0.17, "clay")
            if i == 3:
                o.rotation_euler = (1.45, 0, 0.6)
                o.location.z = 0.18
        elif level <= 3:                                 # banded casks
            k.cylinder("cask", 0.2, 0.5, p, s["wood"], segs=20, parent=root, radius_top=0.2)
            for z in (0.08, 0.42):
                k.cylinder("cask_band", 0.208, 0.04, p + Vector((0, 0, z)), s["fit"], segs=20, parent=root,
                           bevel=False)
        else:                                            # metal canisters with a cap
            k.cylinder("canister", 0.17, 0.55, p, s["vessel"], segs=20, parent=root)
            k.cylinder("canister_cap", 0.07, 0.06, p + Vector((0, 0, 0.55)), s["fit"], segs=12, parent=root)
            k.cylinder("canister_band", 0.175, 0.04, p + Vector((0, 0, 0.3)), "paint_red" if level == 4
                       else "gold_trim", segs=20, parent=root, bevel=False)


def _amphora(k, parent, base, r, mat):
    prof = [(0.0, 0.0), (0.04, r * 0.5), (0.25, r), (0.5, r * 0.95), (0.7, r * 0.55), (0.82, r * 0.3),
            (0.95, r * 0.32), (1.0, r * 0.25)]
    prof = [(z * r * 5, rr) for z, rr in prof]
    return k.lathe("amphora", prof, mat, segs=20, loc=base, rot=(math.pi / 2, 0, 0), parent=parent)


# -- the turning carriage ------------------------------------------------------------------
def _carriage(k, t, level, s):
    W = s["wood"] if level < 5 else "timber_oak"
    for sx in (-1, 1):
        k.box("cheek", (0.14, 2.3, 0.22), (sx * 0.7, -0.1, DECK_Z - 0.12), W, parent=t, bevel=0.01)
    k.box("deck", (1.6, 2.3, 0.08), (0, -0.1, DECK_Z), W, parent=t, bevel=0.008)
    k.cylinder("hub", 0.2, 0.12, (0, 0, 0.36), s["fit"] if level > 1 else W, segs=16, parent=t)
    if level >= 5:
        for sx in (-1, 1):
            k.box("deck_trim", (0.04, 2.3, 0.06), (sx * 0.8, -0.1, DECK_Z + 0.02), "gold_trim", parent=t, bevel=False)
    if level == 2:                                       # push bars to swing the carriage
        for sy in (-1, 1):
            k.tube("push_bar", (0.75, sy * 0.6 - 0.1, DECK_Z - 0.1), (1.3, sy * 0.75 - 0.1, DECK_Z - 0.05), 0.03, W,
                   parent=t, segs=8, bevel=False)
    if level >= 3:                                       # wheels on the track
        for a in (45, 135, 225, 315):
            d = Vector((math.cos(math.radians(a)), math.sin(math.radians(a)), 0))
            c = d * 1.05 + Vector((0, 0, 0.36))
            tang = Vector((-d.y, d.x, 0))
            k.cylinder("track_wheel", 0.12, 0.08, c - tang * 0.04, s["fit"], segs=16,
                       rot=tang.to_track_quat("Z", "Y").to_euler(), parent=t)
            _beam(k, t, "wheel_arm", d * 0.75 + Vector((0, 0, DECK_Z - 0.1)), c + Vector((0, 0, 0.05)), (0.08, 0.08), W)
    if level >= 4:                                       # crank on the toothed ring
        c = Vector((-0.5, 0.0, 0.25))
        k.cylinder("traverse_pinion", 0.07, 0.06, c, s["fit"], segs=10, parent=t)
        k.tube("pinion_shaft", c, c + Vector((0, 0, 0.55)), 0.02, s["fit"], parent=t, segs=8, bevel=False)
        k.beam("crank", c + Vector((0, 0, 0.55)), c + Vector((-0.2, 0, 0.55)), (0.035, 0.03), s["fit"], parent=t,
               bevel=False)
        k.tube("crank_knob", c + Vector((-0.2, 0, 0.55)), c + Vector((-0.2, 0, 0.66)), 0.02, "wood", parent=t,
               segs=6, bevel=False)


def _vessel(k, t, level, s):
    """What holds the fuel, and what drives it out."""
    z0 = DECK_Z + 0.04
    if level == 1:                                       # clay jars in a rack, a keg feeding the pump
        for i, x in enumerate((-0.4, 0.0, 0.4)):
            _amphora(k, t, (x, -0.85, z0), 0.16, "clay")
        for x in (-0.6, 0.6):
            _beam(k, t, "rack_post", (x, -0.85, z0), (x, -0.85, z0 + 0.6), (0.06, 0.06), s["wood"])
        _beam(k, t, "rack_bar", (-0.62, -0.85, z0 + 0.45), (0.62, -0.85, z0 + 0.45), (0.05, 0.05), s["wood"])
        k.cylinder("keg", 0.24, 0.5, (0, -0.25, z0), s["wood"], segs=20, parent=t, radius_top=0.22)
        for z in (0.08, 0.42):
            k.torus("keg_rope", 0.235, 0.015, (0, -0.25, z0 + z), s["rope"], parent=t, segs=20, tube_segs=5)
        _RIG["feed"] = Vector((0, -0.25, z0 + 0.5))
        return
    if level <= 3:                                       # cauldron over a brazier
        c = Vector((0, -0.65, z0 + 0.45))
        r = 0.5 if level == 2 else 0.55
        prof = [(-0.35, 0.0), (-0.32, r * 0.55), (-0.15, r * 0.95), (0.1, r), (0.3, r * 0.92), (0.42, r * 0.7),
                (0.5, r * 0.45 if level == 3 else r * 0.75), (0.58, 0.0 if level == 3 else r * 0.75)]
        k.lathe("cauldron", prof, s["vessel"], segs=32, loc=c, rot=(math.pi / 2, 0, 0), parent=t)
        if level == 3:
            k.cylinder("lid_knob", 0.06, 0.1, c + Vector((0, 0, 0.55)), "bronze_old", segs=12, parent=t)
        for a in (90, 210, 330):                         # iron legs
            d = Vector((math.cos(math.radians(a)), math.sin(math.radians(a)), 0))
            _beam(k, t, "cauldron_leg", c + d * 0.4 + Vector((0, 0, -0.1)), c + d * 0.6 + Vector((0, 0, -0.45)),
                  (0.05, 0.05), "iron_forged")
        _brazier(k, t, c + Vector((0, 0, -0.45)), 0.38)
        _RIG["feed"] = c + Vector((0, 0.45, 0.1))
        return
    # levels 4 and 5: a horizontal armoured tank, fired from below
    c = Vector((0, -0.75, z0 + 0.62))
    k.tube("tank", c - Vector((0.62, 0, 0)), c + Vector((0.62, 0, 0)), 0.36, s["vessel"], parent=t, segs=32)
    for sx in (-1, 1):
        k.lathe("tank_end", [(0.0, 0.36), (0.08, 0.33), (0.16, 0.2), (0.2, 0.0)], s["vessel"], segs=32,
                loc=c + Vector((sx * 0.62, 0, 0)), rot=(0, 0, -sx * math.pi / 2), parent=t)
        k.box("cradle", (0.12, 0.7, 0.3), c + Vector((sx * 0.45, 0, -0.42)), s["fit"], parent=t, bevel=0.01)
    for x in (-0.4, 0.0, 0.4):
        k.torus("tank_band", 0.365, 0.02, c + Vector((x, 0, 0)), "gold_trim" if level == 5 else "steel_worn",
                rot=(0, math.pi / 2, 0), parent=t, segs=32, tube_segs=5)
    fx.rivets(k, t, c + Vector((-0.55, 0, 0.365)), c + Vector((0.55, 0, 0.365)), 10, (0, 0, 1), r=0.025)
    fx.gauge(k, t, c + Vector((0.25, 0.3, 0.25)), (0, 1, 0.6), r=0.08)
    k.tube("safety_valve", c + Vector((-0.25, 0, 0.36)), c + Vector((-0.25, 0, 0.6)), 0.03, "brass", parent=t,
           segs=10)
    k.cylinder("valve_weight", 0.06, 0.08, c + Vector((-0.25, 0, 0.6)), "brass", segs=12, parent=t)
    _brazier(k, t, c + Vector((0, 0, -0.6)), 0.3)
    # bellows on the fire
    b = c + Vector((0.75, 0.25, -0.45))
    k.box("bellows_board", (0.42, 0.26, 0.03), b + Vector((0, 0, 0.12)), s["wood"] if level == 4 else "silver_satin",
          rot=(0.0, -0.25, 0), parent=t, bevel=0.005)
    k.box("bellows_board", (0.42, 0.26, 0.03), b + Vector((0, 0, -0.04)), s["wood"] if level == 4 else "silver_satin",
          parent=t, bevel=0.005)
    k.box("bellows_leather", (0.36, 0.22, 0.12), b + Vector((0.02, 0, 0.04)), "leather", parent=t, bevel=0.02)
    k.tube("bellows_nozzle", b + Vector((-0.22, 0, 0.0)), c + Vector((0.2, 0, -0.55)), 0.025, "brass", parent=t,
           segs=8, bevel=False)
    if level == 5:                                       # bank of pressure flasks
        for i, x in enumerate((-0.45, -0.15, 0.15, 0.45)):
            p = Vector((x, -1.18, z0))
            k.cylinder("flask", 0.11, 0.7, p, "silver", segs=20, parent=t)
            k.cylinder("flask_cap", 0.05, 0.08, p + Vector((0, 0, 0.7)), "gold_trim", segs=12, parent=t)
            k.tube("flask_pipe", p + Vector((0, 0, 0.76)), c + Vector((x * 0.6, -0.2, 0.3)), 0.015, "gold_trim",
                   parent=t, segs=6, bevel=False)
    _RIG["feed"] = c + Vector((0, 0.36, 0.0))


def _brazier(k, t, c, r):
    k.lathe("brazier", [(0.0, 0.0), (0.02, r * 0.6), (0.14, r), (0.16, r * 0.96)], "iron_forged", segs=24,
            loc=c, rot=(math.pi / 2, 0, 0), parent=t)
    k.cylinder("coals", r * 0.9, 0.06, c + Vector((0, 0, 0.1)), "ember", segs=24, parent=t, bevel=False)
    for i in range(7):
        a = 2 * math.pi * i / 7
        _ball(k, t, c + Vector((math.cos(a) * r * 0.5, math.sin(a) * r * 0.5, 0.17)), 0.06, "ember", subdiv=1)


def _siphon(k, t, level, s):
    """The siphon tube on its post and the nozzle; returns the nozzle mouth."""
    W = s["wood"] if level < 5 else "silver_satin"
    post = Vector((0, 0.55, DECK_Z))
    _beam(k, t, "nozzle_post", post, post + Vector((0, 0, 0.95)), (0.18, 0.18), W)
    top = post + Vector((0, 0, 1.02))
    for sx in (-1, 1):
        k.box("yoke", (0.04, 0.14, 0.2), top + Vector((sx * 0.1, 0, 0.05)), s["fit"], parent=t, bevel=0.004)
    a = top + Vector((0, -0.55, -0.02))
    b = top + Vector((0, 1.45, 0.08))
    k.tube("siphon", a, b, 0.09 if level > 1 else 0.075, s["pipe"] if level > 1 else "iron_forged", parent=t,
           segs=16)
    for f in (0.15, 0.5, 0.85):
        k.torus("siphon_band", 0.098, 0.016, a.lerp(b, f), s["fit"], rot=((b - a).to_track_quat("Z", "Y").to_euler()),
                parent=t, segs=16, tube_segs=4)
    k.tube("handle", a + Vector((0, 0.05, 0)), a + Vector((0, -0.35, -0.12)), 0.03, "wood", parent=t, segs=8,
           bevel=False)
    # feed line from the vessel to the back of the siphon
    feed = _RIG["feed"]
    if level == 1:
        k.hose("feed", [feed, feed + Vector((0, 0.3, 0.25)), a + Vector((0, -0.2, 0.05)), a], 0.045, "leather",
               parent=t)
    else:
        k.hose("feed", [feed, feed + Vector((0, 0.25, 0.15)), a + Vector((0, -0.15, 0.0)), a], 0.04, s["pipe"],
               parent=t)
    d = (b - a).normalized()
    before = set(bpy.data.objects)
    tip = _nozzle(k, t, level, s, b, d)
    for o in set(bpy.data.objects) - before:           # grow the head so it reads at game zoom
        o.location = b + (o.location - b) * 1.5
        o.scale = o.scale * 1.5
    return b + (tip - b) * 1.5


def _nozzle(k, t, level, s, b, d):
    if level <= 2:                                       # plain nozzle
        k.cylinder("nozzle", 0.1, 0.25, b, s["nozzle"], segs=16, rot=d.to_track_quat("Z", "Y").to_euler(),
                   parent=t, radius_top=0.05)
        return b + d * 0.25
    rot = d.to_track_quat("Z", "Y").to_euler()
    if level == 3:                                       # flared bronze bell: a wider sheet of fire
        k.lathe("bell", [(0.0, 0.07), (0.12, 0.075), (0.22, 0.1), (0.3, 0.16), (0.34, 0.2)], s["nozzle"], segs=24,
                loc=b, rot=d.to_track_quat("Y", "Z").to_euler(), parent=t)
        k.torus("bell_rim", 0.2, 0.018, b + d * 0.34, "brass", rot=rot, parent=t, segs=24, tube_segs=5)
        return b + d * 0.34
    # level 4: armoured nozzle with a pilot flame that lights the stream
    k.cylinder("nozzle", 0.11, 0.3, b, s["nozzle"], segs=16, rot=rot, parent=t, radius_top=0.075)
    k.cylinder("hood", 0.16, 0.12, b + d * 0.24, s["nozzle"], segs=16, rot=rot, parent=t, radius_top=0.14)
    pilot = b + d * 0.36 + Vector((0, 0, -0.13))
    k.tube("pilot_line", b + Vector((0, 0, -0.12)), pilot, 0.016, "brass", parent=t, segs=6, bevel=False)
    _ball(k, t, pilot, 0.035, "ember", subdiv=1)
    fx.gauge(k, t, b + Vector((0.12, -0.05, 0.05)), (1, 0, 0.4), r=0.05)
    return b + d * 0.36
    # level 5: dragon head
    h = b + d * 0.05
    k.lathe("dragon_skull", [(0.0, 0.0), (0.05, 0.12), (0.2, 0.16), (0.42, 0.11), (0.55, 0.07), (0.58, 0.0)],
            "gold_trim", segs=20, loc=h, rot=d.to_track_quat("Y", "Z").to_euler(), parent=t)
    k.beam("dragon_jaw", h + d * 0.1 + Vector((0, 0, -0.1)), h + d * 0.55 + Vector((0, 0, -0.16)), (0.16, 0.05),
           "gold_trim", section_end=(0.08, 0.03), parent=t, bevel=0.004)
    for sx in (-1, 1):
        k.tube("horn", h + Vector((sx * 0.08, 0, 0.12)), h + Vector((sx * 0.16, -0.32, 0.34)), 0.035, "silver",
               radius_end=0.008, parent=t, segs=8, bevel=False)
        _ball(k, t, h + d * 0.3 + Vector((sx * 0.1, 0, 0.08)), 0.03, "ember", subdiv=1)
        k.beam("frill", h + Vector((sx * 0.12, -0.05, 0.0)), h + Vector((sx * 0.32, -0.2, -0.05)), (0.03, 0.14),
               "silver", parent=t, bevel=False, section_end=(0.02, 0.05))
    return h + d * 0.58 + Vector((0, 0, -0.06))


def _pump(k, t, level, s):
    """The pump: one lever (1, 2) or a rocking beam over two cylinders (3 and up)."""
    W = s["wood"] if level < 5 else "silver_satin"
    fit = s["fit"]
    base = Vector((0.45, -0.1, DECK_Z + 0.04))
    piv = k.empty("lever_pivot", base + Vector((0, 0, 0.75)), parent=t)
    if level <= 2:
        k.cylinder("pump_barrel", 0.09, 0.6, base, fit if level > 1 else "iron_forged", segs=16, parent=t)
        _beam(k, t, "pump_post", base + Vector((0.14, 0, 0)), base + Vector((0.14, 0, 0.8)), (0.07, 0.07), W)
        parts = [k.beam("lever", piv.location + Vector((0, 0.25, 0)), piv.location + Vector((0, -0.95, 0.1)),
                        (0.05, 0.06), W, parent=t, bevel=0.004),
                 k.tube("lever_grip", piv.location + Vector((-0.12, -0.95, 0.1)), piv.location + Vector((0.12, -0.95, 0.1)),
                        0.025, "leather", parent=t, segs=8, bevel=False),
                 k.tube("pump_rod", piv.location + Vector((0, 0.18, 0)), base + Vector((0, 0, 0.55)), 0.02, fit,
                        parent=t, segs=6, bevel=False)]
    else:
        for y in (0.45, -0.75):                          # two pump cylinders
            k.cylinder("pump_barrel", 0.1, 0.55, base + Vector((0, y, 0)), fit, segs=16, parent=t)
            k.cylinder("barrel_cap", 0.12, 0.05, base + Vector((0, y, 0.55)), "brass", segs=16, parent=t)
        _beam(k, t, "pump_post", base + Vector((0, -0.15, 0)), base + Vector((0, -0.15, 0.78)), (0.09, 0.09), W)
        piv.location = base + Vector((0, -0.15, 0.82))
        p = piv.location
        parts = [k.beam("rocking_beam", p + Vector((0, 0.95, 0)), p + Vector((0, -1.05, 0)), (0.07, 0.1), W, parent=t,
                        bevel=0.005)]
        for y in (0.6, -0.6):
            parts.append(k.tube("pump_rod", p + Vector((0, y, 0)), p + Vector((0, y, -0.25)), 0.02, fit, parent=t,
                                segs=6, bevel=False))
        for y in (0.95, -1.05):
            parts.append(k.tube("beam_grip", p + Vector((-0.15, y, 0)), p + Vector((0.15, y, 0)), 0.025, "leather",
                                parent=t, segs=8, bevel=False))
        if level >= 5:
            parts.append(k.box("beam_trim", (0.08, 1.9, 0.02), p + Vector((0, -0.05, 0.06)), "gold_trim", parent=t,
                               bevel=False))
    for o in parts:
        _keep_world(o, piv)
    _RIG["lever"] = piv


def key_fire_animation(scene):
    prefs = bpy.context.preferences.edit
    old = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = "LINEAR"
    for f in range(FIRE_FRAMES + 1):
        set_fire_frame(f)
        _RIG["lever"].keyframe_insert("rotation_euler", frame=f)
    prefs.keyframe_new_interpolation_type = old
    scene.frame_set(0)


def set_fire_frame(f, scene=None):
    if scene is not None and _RIG["lever"].animation_data is not None:
        scene.frame_set(f)
    else:
        a = 0.0 if f == 0 else FIRE[f - 1]
        _RIG["lever"].rotation_euler = (math.radians(a), 0, 0)
    bpy.context.view_layer.update()
