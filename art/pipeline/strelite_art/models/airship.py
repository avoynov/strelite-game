"""Armoured airship (bg: „Дирижабъл“): the flying enemy of the parallel world, in place of
the drone. A 14 m rigid envelope in doped canvas over visible ring frames, an armoured
nose cap, oxblood bands and the faction emblem on top and on both flanks; under it a
riveted gondola with brass-framed windows, two engine pods with pusher propellers, a
cruciform tail and a machine gun in a chin turret.

FLYING: rendered alone without a ground shadow; the game draws it at its flight height
and puts a dark ellipse on the ground below it.
The airship faces local +Y; render_sprites.py --enemy turns it. Returns (root, root).
"""
import math

from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit
from . import faction as fx

SPRITE_FRAME_M = 16.0
LENGTH_M = 14.0
RADIUS_M = 4.0
FLYING = True
FLIGHT_HEIGHT_M = 10.0
G, WORN = "paint_enemy", "paint_enemy_worn"
R = 2.15                 # envelope radius


def _r(y):
    """Envelope radius at y (nose +7, tail -7): a blunt nose and a long taper aft."""
    t = (y + 7.0) / 14.0
    if t > 0.8:
        return R * math.sqrt(max(0.0, 1 - ((t - 0.8) / 0.2) ** 2)) ** 0.9
    return R * math.sin(min(1.0, t / 0.8) * math.pi / 2) ** 0.75


def build(style, level=1):
    k = Kit(style)
    root = k.empty("airship")
    mp.set_reference(root)
    body = k.empty("body", (0, 0, 0), parent=root)
    body.rotation_euler = (math.radians(2), math.radians(3), 0)
    ys = [-7.0 + 14.0 * i / 40 for i in range(41)]
    prof = [(y, max(_r(y), 0.0)) for y in ys]
    k.lathe("envelope", prof, "canvas", segs=40, parent=body)
    for y in (-4.5, -2.0, 0.5, 3.0):                       # ring frames show through the cloth
        k.torus("frame_ring", _r(y) + 0.01, 0.025, (0, y, 0), G, rot=(math.pi / 2, 0, 0), parent=body,
                segs=40, tube_segs=5)
    for sx in (-1, 0, 1):                                  # gores: seams along the envelope
        a = math.pi / 2 + sx * 0.6
        pts = [(math.cos(a) * (_r(y) + 0.012), y, math.sin(a) * (_r(y) + 0.012)) for y in
               [-6.2 + 11.4 * i / 16 for i in range(17)]]
        if sx:
            k.hose("seam", pts, 0.03, G, parent=body)
        else:                                              # red spine stripe, broken by the emblem
            k.hose("spine_stripe", [p for p in pts if p[1] < -0.55], 0.09, "paint_faction_red", parent=body)
            k.hose("spine_stripe", [p for p in pts if p[1] > 1.55], 0.09, "paint_faction_red", parent=body)
    for y in (4.6, 4.9):                                   # oxblood bands ahead of the nose cap
        k.torus("band", _r(y) + 0.015, 0.06, (0, y, 0), "paint_faction_red", rot=(math.pi / 2, 0, 0),
                parent=body, segs=40, tube_segs=6)
    nose = [(y, _r(y) + 0.03) for y in [5.3 + 1.75 * i / 10 for i in range(11)]]
    k.lathe("nose_cap", nose, G, segs=40, parent=body)
    k.cylinder("nose_boss", 0.18, 0.12, (0, 7.0, 0), "brass", segs=20, rot=(-math.pi / 2, 0, 0), parent=body)
    fx.rivets(k, body, (0, 5.4, _r(5.4) + 0.02), (0, 6.6, _r(6.6) + 0.02), 6, (0, 0.3, 1))
    # faction emblem on top and on both flanks
    fx.emblem(k, body, (0, 0.5, R + 0.01), (0, 0, 1), r=0.85)
    for sx in (-1, 1):
        fx.emblem(k, body, (sx * (R + 0.01), 1.2, 0.15), (sx, 0, 0.1), r=0.6)
    # cruciform tail: one fin outline turned four times about the long axis
    fin = [(-4.4, _r(-4.4) - 0.08), (-5.9, 2.85), (-6.6, 2.85), (-6.75, _r(-6.75) - 0.05)]
    for i in range(4):
        o = k.plate("fin", fin, 0.08, 0.0, G, parent=body, bevel=0.01)
        o.rotation_euler = (0, math.pi / 2 * i, 0)
        r = k.plate("rudder", [(-6.6, 1.6), (-6.6, 2.7), (-7.1, 2.6), (-7.1, 1.7)], 0.06, 0.0, WORN, parent=body,
                    bevel=False)
        r.rotation_euler = (0, math.pi / 2 * i, 0)
    # gondola: riveted car with brass windows
    gz = -R - 0.55
    k.box("gondola", (1.3, 4.2, 0.9), (0, 0.8, gz), G, parent=body, bevel=0.12)
    k.box("gondola_keel", (0.5, 3.8, 0.12), (0, 0.8, gz - 0.48), WORN, parent=body, bevel=0.02)
    for sx in (-1, 1):
        for i in range(6):
            c = Vector((sx * 0.66, -0.6 + i * 0.55, gz + 0.12))
            k.cylinder("porthole", 0.12, 0.04, c, "brass", segs=16, rot=(0, sx * math.pi / 2, 0), parent=body)
            k.cylinder("porthole_glass", 0.09, 0.01, c + Vector((sx * 0.04, 0, 0)), "glass", segs=16,
                       rot=(0, sx * math.pi / 2, 0), parent=body, bevel=False)
        fx.rivets(k, body, (sx * 0.66, -1.2, gz - 0.3), (sx * 0.66, 2.8, gz - 0.3), 12, (sx, 0, 0))
        for y in (-0.7, 2.3):                              # struts up to the envelope
            k.tube("strut", (sx * 0.5, y, gz + 0.4), (sx * 0.9, y + 0.2, -R + 0.25), 0.04, "steel_worn",
                   parent=body, segs=8, bevel=False)
        # engine pods with pusher propellers
        pc = Vector((sx * 2.0, -1.2, gz + 0.55))
        k.tube("pod_arm", (sx * 0.62, -1.0, gz + 0.3), pc + Vector((-sx * 0.3, 0, 0)), 0.07, G, parent=body, segs=10)
        k.lathe("engine_pod", [(-0.9, 0.0), (-0.8, 0.22), (0.3, 0.32), (0.75, 0.22), (0.9, 0.0)], G, segs=20,
                loc=pc, parent=body)
        k.torus("pod_band", 0.33, 0.025, pc + Vector((0, 0.1, 0)), "brass", rot=(math.pi / 2, 0, 0), parent=body,
                segs=20, tube_segs=5)
        fx.stack(k, body, pc + Vector((0, 0.3, 0.25)), 0.35, r=0.04)
        for a in (0.3, 0.3 + math.pi):
            d = Vector((math.cos(a), 0, math.sin(a)))
            k.beam("blade", pc + Vector((0, -0.95, 0)) + d * 0.08, pc + Vector((0, -0.95, 0)) + d * 0.85,
                   (0.14, 0.025), "wood", section_end=(0.08, 0.02), parent=body, bevel=False)
        k.cylinder("spinner", 0.1, 0.18, pc + Vector((0, -0.9, 0)), "brass", segs=14, rot=(math.pi / 2, 0, 0),
                   parent=body, radius_top=0.02)
    # chin turret with a machine gun, gauges on the bridge
    tc = Vector((0, 3.0, gz - 0.35))
    k.lathe("chin_turret", [(0.0, 0.35), (0.15, 0.3), (0.3, 0.0)], "brass", segs=20, loc=tc,
            rot=(-math.pi / 2, 0, 0), parent=body)
    k.tube("mg", tc + Vector((0, 0.2, -0.1)), tc + Vector((0, 1.2, -0.2)), 0.03, "gunmetal", parent=body, segs=8)
    k.box("bridge_window", (1.0, 0.03, 0.3), (0, 2.91, gz + 0.15), "glass", rot=(-0.3, 0, 0), parent=body,
          bevel=False)
    fx.pennant(k, body, (0, -6.3, 2.2), h=0.5, w=1.2)
    return root, root
