"""Armoured airship of the Iron Concord (bg: „Дирижабъл“): the flying enemy, built to
the guns' standard at real size. A 14 m rigid airship: a 24-sided envelope of doped
slate canvas in alternating gores over ring frames and longitudinal girders, an
armoured riveted nose cap with oxblood bands, a catwalk and a machine-gun nest on top,
a cruciform tail with rudders and elevators; under it a streamlined control car with a
glazed nose and a band of brass-framed windows, a rack of four bombs, two engine pods
on outriggers and an aft engine car, each with a four-bladed wooden pusher propeller.

Concord touches: oxblood nose bands, spine stripe and fin stripes, emblems on top and on
both flanks, brass rails, frames, spinners, stacks and the gun ring; a pennant on the
tail.

What makes it unmistakable at game zoom: a long slate cigar with oxblood bands and the
emblem on top, propellers turning beside it.

FLYING: rendered alone without a ground shadow; the game draws it at its flight height
and puts a dark ellipse on the ground below it.
Movement: the propellers turn (MOVE_FRAMES frames per quarter turn, played at MOVE_FPS
whatever the speed). The airship faces local +Y; render_sprites.py --enemy turns it.
Returns (root, root).
"""
import math

from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit
from . import faction as fx
from . import vehicle

SPRITE_FRAME_M = 16.0
LENGTH_M = 14.0
RADIUS_M = 4.0
FLYING = True
FLIGHT_HEIGHT_M = 10.0
G, WORN = "paint_enemy", "paint_enemy_worn"
R = 2.15                 # envelope radius
SIDES = 24               # the envelope is a 24-sided polygon in section, like a real rigid ship
MOVE_FRAMES = 4
MOVE_KIND = "props"
MOVE_CYCLE_M = None
MOVE_FPS = 20
_MOTION = vehicle.Motion(MOVE_FRAMES)


def set_move_frame(f, scene=None):
    _MOTION.set(f)


def _r(y):
    """Envelope radius at y (nose +7, tail -7): a blunt nose and a long taper aft."""
    t = (y + 7.0) / 14.0
    if t > 0.8:
        return R * math.sqrt(max(0.0, 1 - ((t - 0.8) / 0.2) ** 2)) ** 0.9
    return R * math.sin(min(1.0, t / 0.8) * math.pi / 2) ** 0.75


def _on(y, a, out=0.0):
    """Point on the envelope surface at y, angle a (0 = right, pi/2 = top), on a facet corner."""
    r = _r(y) + out
    return Vector((r * math.cos(a), y, r * math.sin(a)))


def build(style, level=1):
    global _MOTION
    _MOTION = vehicle.Motion(MOVE_FRAMES)
    k = Kit(style)
    root = k.empty("airship")
    mp.set_reference(root)
    body = k.empty("body", (0, 0, 0), parent=root)
    body.rotation_euler = (math.radians(2), math.radians(3), 0)
    _envelope(k, body)
    _top(k, body)
    _tail(k, body)
    gz = _car(k, body)
    _engines(k, body, gz)
    return root, root


def _envelope(k, body):
    ys = [-7.0 + 14.0 * i / 48 for i in range(49)]
    env = k.lathe("envelope", [(y, max(_r(y), 0.0)) for y in ys], "canvas_doped", segs=SIDES, parent=body)
    env.data.materials.append(k.material("canvas_doped_dark"))
    ring_faces = (len(ys) - 1) * SIDES
    for poly in env.data.polygons:
        poly.use_smooth = False
        poly.material_index = (poly.index % SIDES) % 2 if poly.index < ring_faces else 0
    # ring frames and longitudinal girders standing proud of the cloth
    for y in (-5.2, -3.4, -1.6, 0.2, 2.0, 3.8):
        r = _r(y)
        vehicle.ring_lathe(k, "frame_ring", [(y - 0.05, r - 0.01), (y - 0.05, r + 0.025), (y + 0.05, r + 0.025),
                                             (y + 0.05, r - 0.01)], G, segs=SIDES, parent=body)
    for i in range(SIDES):
        a = 2 * math.pi * i / SIDES
        if math.sin(a) < -0.3:
            continue
        k.hose("girder", [_on(y, a, 0.012) for y in [-6.3 + 11.3 * j / 14 for j in range(15)]], 0.018, G,
               parent=body)
    # armoured nose cap with rivets, oxblood bands behind it, brass mooring boss
    nose = [(y, _r(y) + 0.03) for y in [5.3 + 1.75 * i / 12 for i in range(13)]]
    cap = k.lathe("nose_cap", nose, G, segs=SIDES, parent=body)
    for poly in cap.data.polygons:
        poly.use_smooth = False
    for y in (4.55, 4.95):
        r = _r(y)
        vehicle.ring_lathe(k, "nose_band", [(y - 0.12, r - 0.01), (y - 0.12, r + 0.018), (y + 0.12, r + 0.018),
                                            (y + 0.12, r - 0.01)], fx.RED, segs=SIDES, parent=body)
    k.cylinder("nose_boss", 0.2, 0.14, (0, 7.0, 0), "brass", segs=20, rot=(-math.pi / 2, 0, 0), parent=body)
    for j in range(8):
        a = 2 * math.pi * j / 8 + math.pi / 8
        fx.rivets(k, body, _on(5.45, a, 0.04), _on(6.55, a, 0.04), 6, (math.cos(a), 0.3, math.sin(a)), r=0.03)
    # faction emblems on the flanks
    for sx in (-1, 1):
        fx.emblem(k, body, (sx * (R + 0.02), 0.9, 0.0), (sx, 0, 0), r=0.62)


def _top(k, body):
    """Spine: oxblood stripe, catwalk with brass rails, emblem, machine-gun nest."""
    top = math.pi / 2
    k.hose("spine_stripe", [_on(y, top, 0.015) for y in [-6.0 + 4.6 * j / 8 for j in range(9)]], 0.12, fx.RED,
           parent=body)
    fx.emblem(k, body, _on(0.2, top, 0.02), (0, 0, 1), r=0.85)
    for j in range(16):                                  # catwalk planks ahead of the emblem
        y = 1.3 + j * 0.17
        k.box("catwalk_plank", (0.5, 0.14, 0.03), _on(y, top, 0.03), "timber_tarred", parent=body, bevel=False)
    for sx in (-1, 1):
        rail = [_on(y, top, 0.0) + Vector((sx * 0.3, 0, 0.45)) for y in (1.25, 2.2, 3.15, 4.0)]
        k.hose("hand_rail", rail, 0.014, "brass", parent=body)
        for y in (1.25, 2.2, 3.15, 4.0):
            p = _on(y, top, 0.0) + Vector((sx * 0.3, 0, 0))
            k.tube("stanchion", p, p + Vector((0, 0, 0.45)), 0.012, "iron_black", parent=body, segs=6, bevel=False)
    nest = _on(4.3, top, 0.0)
    k.cylinder("gun_nest", 0.42, 0.28, nest - Vector((0, 0, 0.05)), G, segs=24, parent=body, bevel=0.02)
    k.torus("nest_ring", 0.42, 0.03, nest + Vector((0, 0, 0.25)), "brass", parent=body, segs=24, tube_segs=6)
    k.tube("nest_mg", nest + Vector((0, 0.0, 0.45)), nest + Vector((0, 0.9, 0.5)), 0.025, "gunmetal", parent=body,
           segs=10)
    k.box("nest_shield", (0.36, 0.03, 0.22), nest + Vector((0, 0.3, 0.45)), WORN, rot=(0.2, 0, 0), parent=body,
          bevel=0.006)
    k.box("mg_drum", (0.1, 0.12, 0.12), nest + Vector((0, -0.05, 0.42)), "gunmetal", parent=body, bevel=0.02)


def _tail(k, body):
    """Cruciform tail: four fins with hinged rudders/elevators and oxblood stripes."""
    fin = [(-4.4, _r(-4.4) - 0.08), (-5.9, 2.85), (-6.5, 2.85), (-6.7, _r(-6.7) - 0.05)]
    for i in range(4):
        rot = (0, math.pi / 2 * i, 0)
        k.plate("fin", fin, 0.08, 0.0, G, parent=body, bevel=0.01).rotation_euler = rot
        k.plate("rudder", [(-6.52, 1.35), (-6.52, 2.84), (-7.1, 2.74), (-7.1, 1.45)], 0.06, 0.0, WORN, parent=body,
                bevel=0.006).rotation_euler = rot
        k.plate("fin_stripe", [(-5.95, 2.4), (-5.95, 2.78), (-6.45, 2.78), (-6.45, 2.4)], 0.09, 0.0, fx.RED,
                parent=body, bevel=False).rotation_euler = rot
        k.plate("fin_rib", [(-4.6, _r(-4.6) + 0.02), (-5.95, 2.6), (-5.95, 2.68), (-4.6, _r(-4.6) + 0.1)], 0.1, 0.0,
                WORN, parent=body, bevel=False).rotation_euler = rot
    fx.pennant(k, body, (0, -6.6, 2.85), h=0.5, w=1.2)


def _car(k, body):
    """Control car under the envelope: streamlined hull, glazed nose, window band, struts,
    bomb rack. Returns the car's mid height."""
    gz = -R - 0.6

    def s(w, zb, zt):
        return [(0.0, zb), (w * 0.55, zb), (w, zb + 0.28), (w, zt - 0.18), (w * 0.75, zt), (0.0, zt)]
    vehicle.hull(k, "control_car", [
        (-1.7, s(0.3, gz - 0.12, gz + 0.38)),
        (-1.2, s(0.62, gz - 0.42, gz + 0.48)),
        (2.0, s(0.68, gz - 0.45, gz + 0.5)),
        (2.8, s(0.55, gz - 0.32, gz + 0.46)),
    ], G, body, bevel=0.02)
    for sx in (-1, 1):
        k.box("window_band", (0.05, 2.0, 0.22), (sx * 0.665, 1.0, gz + 0.22), "glass", parent=body, bevel=False)
        for i in range(7):
            k.box("window_mullion", (0.06, 0.04, 0.26), (sx * 0.67, 0.0 + i * 0.333, gz + 0.22), "brass",
                  parent=body, bevel=False)
        k.box("window_sill", (0.06, 2.05, 0.03), (sx * 0.67, 1.0, gz + 0.1), "brass", parent=body, bevel=False)
        fx.rivets(k, body, (sx * 0.69, -1.0, gz - 0.12), (sx * 0.69, 2.0, gz - 0.12), 12, (sx, 0, 0), r=0.025)
        for y in (-0.8, 1.6):                            # struts up to the envelope
            k.tube("strut", (sx * 0.45, y, gz + 0.45), (sx * 0.95, y + 0.25, -_r(y) * 0.92), 0.04, "steel_worn",
                   parent=body, segs=8, bevel=False)
    # glazed nose: glass panes between brass frames
    prof = [(2.78, 0.54), (2.98, 0.5), (3.14, 0.4), (3.27, 0.23), (3.32, 0.0)]
    zc, sz = gz + 0.07, 0.72
    k.lathe("nose_glazing", prof, "glass", segs=24, loc=(0, 0, zc), parent=body).scale = (1, 1, sz)
    for a in (-1.2, -0.4, 0.4, 1.2, math.pi / 2):
        k.hose("glazing_frame", [Vector((r * math.cos(a), y, zc + sz * r * math.sin(a))) * 1.0 +
                                 Vector((0.012 * math.cos(a), 0, 0.012 * math.sin(a))) for y, r in prof[:-1]],
               0.014, "brass", parent=body)
    # bomb rack under the keel
    k.box("bomb_rack", (0.5, 1.5, 0.06), (0, 0.4, gz - 0.48), "iron_black", parent=body, bevel=False)
    for i in range(4):
        y = -0.15 + i * 0.37
        for sx in (-1, 1):
            if (i + (sx > 0)) % 2:
                continue
            c = Vector((sx * 0.14, y, gz - 0.66))
            k.lathe("bomb", [(-0.24, 0.0), (-0.2, 0.06), (0.05, 0.1), (0.18, 0.08), (0.24, 0.0)], G, segs=16,
                    loc=c, parent=body)
            k.cylinder("bomb_band", 0.101, 0.05, c + Vector((0, 0.1, 0)), fx.RED, segs=16, rot=(-math.pi / 2, 0, 0),
                       parent=body, bevel=False)
            for q in range(4):
                a = q * math.pi / 2
                k.box("bomb_fin", (0.1, 0.12, 0.006), c + Vector((0.06 * math.cos(a), -0.22, 0.06 * math.sin(a))),
                      WORN, rot=(0, -a, 0), parent=body, bevel=False)
    return gz


def _prop(k, body, hub, r=0.9):
    """Four-bladed wooden pusher propeller on a brass spinner, turning about Y."""
    p = k.empty("propeller", hub, parent=body)
    for q in range(4):
        a = q * math.pi / 2 + math.pi / 4
        d = Vector((math.cos(a), 0, math.sin(a)))
        k.beam("blade", d * 0.1, d * r, (0.16, 0.03), "timber_honey", section_end=(0.09, 0.02), parent=p,
               bevel=False)
        k.beam("blade_tip", d * (r - 0.08), d * r, (0.095, 0.024), "brass", parent=p, bevel=False)
    k.cylinder("spinner", 0.13, 0.22, (0, 0, 0), "brass", segs=16, rot=(math.pi / 2, 0, 0), parent=p,
               radius_top=0.02)
    _MOTION.prop(p, axis=1, symmetry=4)
    return p


def _engines(k, body, gz):
    """Two engine pods on outriggers and an aft engine car, each with a pusher propeller."""
    for sx in (-1, 1):
        pc = Vector((sx * 2.35, -1.3, gz + 0.5))
        k.beam("outrigger", (sx * 0.62, -1.1, gz + 0.1), pc + Vector((-sx * 0.3, 0, -0.05)), (0.1, 0.08), G,
               parent=body, bevel=0.01)
        k.tube("pod_strut", pc + Vector((-sx * 0.1, 0, 0.3)), _on(-1.1, -math.pi / 2 + sx * 0.62, -0.05), 0.035,
               "steel_worn", parent=body, segs=8, bevel=False)
        k.lathe("engine_pod", [(-0.9, 0.0), (-0.85, 0.2), (-0.3, 0.33), (0.4, 0.34), (0.8, 0.24), (0.95, 0.0)], G,
                segs=24, loc=pc, parent=body)
        k.torus("pod_band", 0.34, 0.025, pc + Vector((0, 0.15, 0)), fx.RED, rot=(math.pi / 2, 0, 0), parent=body,
                segs=24, tube_segs=5)
        k.box("radiator", (0.4, 0.06, 0.3), pc + Vector((0, 0.96, 0.0)), "iron_black", parent=body, bevel=0.01)
        fx.stack(k, body, pc + Vector((0, 0.2, 0.28)), 0.3, r=0.04)
        _prop(k, body, pc + Vector((0, -1.02, 0)))
    # aft engine car under the tail
    ac = Vector((0, -3.9, -_r(-3.9) - 0.55))
    k.lathe("aft_car", [(-0.8, 0.0), (-0.7, 0.22), (0.2, 0.36), (0.8, 0.3), (1.0, 0.0)], G, segs=24, loc=ac,
            parent=body)
    for sx in (-1, 1):
        k.tube("aft_strut", ac + Vector((sx * 0.2, 0.3, 0.28)), _on(-3.6, -math.pi / 2 + sx * 0.3, -0.05), 0.035,
               "steel_worn", parent=body, segs=8, bevel=False)
    fx.stack(k, body, ac + Vector((0, 0.1, 0.3)), 0.25, r=0.04)
    _prop(k, body, ac + Vector((0, -0.92, 0)), r=0.8)
