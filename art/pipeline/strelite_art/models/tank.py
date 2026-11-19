"""Medium tank of the Iron Concord (bg: „Танк“), built to the guns' standard at real
size: welded hull 6.5 x 2.84 m on two 0.58 m tracks (3.4 m over the fenders), cast dome
turret with a 100 mm class gun (8.0 m from the gun tip to the rear plate).

Running gear like the post-war medium tanks: five big double road wheels a side with
rubber tyres, the drive sprocket at the rear, the idler at the front, no return rollers
(the top run rests on the road wheels), separate cast links with grousers and guide
horns. Fenders carry external fuel tanks, stowage boxes and tools; the rear plate two
fuel drums and a timber unditching beam.

Concord touches: oxblood turret band and gun band, emblems on the turret and glacis,
brass cupola ring, AA machine-gun ring and jacket, searchlight, filler caps, twin brass
banded stacks on the engine deck, pennant on the antenna.

What makes it unmistakable at game zoom: the low dome turret with its very long gun
over a flat hull, and the tracks running on five big wheels.

Movement: tracks run and every wheel turns (MOVE_FRAMES frames per heading). One cycle
moves the belt by one link; the road wheels, sprocket and idler are sized so they turn
by exactly one repeat of their bolt or tooth pattern in that time, so the last frame
wraps onto the first. The vehicle faces local +Y; render_sprites.py --enemy turns it.
Returns (root, root).
"""
import math

from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit
from . import faction as fx
from . import vehicle

SPRITE_FRAME_M = 11.0     # metres across the render: the gun overhangs the hull by 1.5 m
LENGTH_M = 8.0            # gun tip to rear plate
RADIUS_M = 3.0            # body (hull) half length, for collisions and spacing
G, WORN, TRACK = "paint_enemy", "paint_enemy_worn", "track_steel"

TRACK_X, TRACK_W, THICK, GROUSER = 1.36, 0.58, 0.06, 0.026
ROAD_Y = (2.02, 1.0, -0.02, -1.04, -2.06)
IDLER_YZ, SPROCKET_YZ = (2.98, 0.5), (-2.98, 0.56)
N_ROAD, N_IDLER, N_SPROCKET = 16, 14, 13      # bolts / teeth: each turns one repeat per cycle
PITCH = 0.16                                  # target link pitch, metres

MOVE_FRAMES = 4
MOVE_KIND = "tracks"


def _radii(step):
    f = step / (2 * math.pi)
    return N_ROAD * f, N_IDLER * f, N_SPROCKET * f


def _circles(step):
    rr, ri, rs = _radii(step)
    zr = GROUSER + THICK + rr                 # road wheels stand on the inner face of the bottom run
    road = [(y, zr, rr + THICK / 2) for y in ROAD_Y]
    return ([(IDLER_YZ[0], IDLER_YZ[1], ri + THICK / 2)] + road +
            [(SPROCKET_YZ[0], SPROCKET_YZ[1], rs)] + list(reversed(road)))


def _layout():
    """Link step and count such that the belt closes on a whole number of links and
    the wheels are sized from that step (a few fixed-point rounds)."""
    step = PITCH
    for _ in range(8):
        total = _belt_length(_circles(step))
        n = max(1, round(total / PITCH))
        step = total / n
    return step, n


def _belt_length(circles):
    # same geometry as vehicle.belt, without mathutils (used at import time)
    cs = [((y, z), r) for y, z, r in circles]
    while True:
        m = len(cs)
        seg = []
        for i in range(m):
            (p1, r1), (p2, r2) = cs[i], cs[(i + 1) % m]
            dy, dz = p2[0] - p1[0], p2[1] - p1[1]
            ln = math.hypot(dy, dz)
            hy, hz = dy / ln, dz / ln
            a = (r1 - r2) / ln
            b = math.sqrt(max(0.0, 1 - a * a))
            ny, nz = hy * a - hz * b, hz * a + hy * b
            t1 = (p1[0] + ny * r1, p1[1] + nz * r1)
            t2 = (p2[0] + ny * r2, p2[1] + nz * r2)
            seg.append((t1, t2, (ny, nz)))
        total, drop = 0.0, None
        for i in range(m):
            a_in = math.atan2(seg[i - 1][2][1], seg[i - 1][2][0])
            a_out = math.atan2(seg[i][2][1], seg[i][2][0])
            sweep = (a_in - a_out) % (2 * math.pi)
            if sweep > 1.5 * math.pi:
                drop = i
                break
            total += cs[i][1] * sweep + math.hypot(seg[i][1][0] - seg[i][0][0], seg[i][1][1] - seg[i][0][1])
        if drop is None:
            return total
        cs.pop(drop)


STEP, N_LINKS = _layout()
MOVE_CYCLE_M = STEP
_MOTION = vehicle.Motion(MOVE_FRAMES, MOVE_CYCLE_M)


def set_move_frame(f, scene=None):
    _MOTION.set(f)


def build(style, level=1):
    global _MOTION
    _MOTION = vehicle.Motion(MOVE_FRAMES, MOVE_CYCLE_M)
    k = Kit(style)
    root = k.empty("tank")
    mp.set_reference(root)
    _running_gear(k, root)
    _hull(k, root)
    _glacis(k, root)
    _fenders(k, root)
    _deck(k, root)
    _rear(k, root)
    _turret(k, root)
    return root, root


# ---------------------------------------------------------------------------
# running gear
def _running_gear(k, root):
    rr, ri, rs = _radii(STEP)
    circles = _circles(STEP)
    path, total = vehicle.belt(circles)
    assert abs(total / N_LINKS - STEP) < 1e-6, (total, N_LINKS, STEP)
    zr = circles[1][1]
    for sx in (-1, 1):
        x = sx * TRACK_X
        for y in ROAD_Y:
            _road_wheel(k, root, (x, y, zr), rr, sx)
        _idler(k, root, (x, IDLER_YZ[0], IDLER_YZ[1]), ri, sx)
        _sprocket(k, root, (x, SPROCKET_YZ[0], SPROCKET_YZ[1]), rs, sx)
        vehicle.belt_links(k, root, _MOTION, x, path, total, N_LINKS, TRACK_W, TRACK, thick=THICK)
        # torsion-bar arms from the hull side to each road wheel hub
        for y in ROAD_Y:
            k.beam("road_arm", (sx * 1.0, y + 0.32, zr + 0.12), (sx * 1.12, y, zr), (0.08, 0.1), WORN,
                   parent=root, bevel=0.01)


def _road_wheel(k, root, loc, r, sx):
    w = k.empty("road_wheel", loc, parent=root)
    hw = 0.085
    for s in (-1, 1):
        cx = s * 0.16
        k.lathe("tyre", [(-hw, r * 0.78), (-hw, r * 0.95), (-hw + 0.015, r), (hw - 0.015, r), (hw, r * 0.95),
                         (hw, r * 0.78)], "rubber", segs=40, loc=(cx, 0, 0), rot=vehicle.AXLE_X, parent=w)
        face = cx + s * hw
        k.lathe("wheel_disc", [(0.0, 0.0), (0.0, r * 0.8), (s * 0.02, r * 0.76), (s * 0.04, r * 0.4),
                               (s * 0.07, r * 0.3), (s * 0.07, 0.0)], G, segs=40,
                loc=(face - s * 0.02, 0, 0), rot=vehicle.AXLE_X, parent=w)
    for i in range(N_ROAD):
        a = 2 * math.pi * i / N_ROAD
        k.cylinder("wheel_bolt", 0.016, 0.03, (sx * 0.254, r * 0.6 * math.cos(a), r * 0.6 * math.sin(a)),
                   "steel_worn", segs=6, rot=(0, sx * math.pi / 2, 0), parent=w, bevel=False)
    k.cylinder("hub_cap", r * 0.24, 0.07, (sx * 0.295, 0, 0), "gunmetal", segs=20, rot=(0, sx * math.pi / 2, 0),
               parent=w, radius_top=r * 0.2, bevel=0.008)
    k.cylinder("hub_nut", r * 0.07, 0.03, (sx * 0.365, 0, 0), "brass", segs=12, rot=(0, sx * math.pi / 2, 0),
               parent=w, bevel=False)
    _MOTION.wheel(w, r)
    return w


def _idler(k, root, loc, r, sx):
    w = k.empty("idler", loc, parent=root)
    for s in (-1, 1):
        k.lathe("idler_rim", [(-0.07, r * 0.8), (-0.07, r), (0.07, r), (0.07, r * 0.8)], "steel_worn", segs=40,
                loc=(s * 0.16, 0, 0), rot=vehicle.AXLE_X, parent=w)
        k.lathe("idler_disc", [(0.0, 0.0), (0.0, r * 0.82), (s * 0.03, r * 0.7), (s * 0.06, r * 0.3),
                               (s * 0.06, 0.0)], G, segs=40, loc=(s * 0.2, 0, 0), rot=vehicle.AXLE_X, parent=w)
    for i in range(N_IDLER):
        a = 2 * math.pi * i / N_IDLER
        k.cylinder("idler_bolt", 0.015, 0.03, (sx * 0.244, r * 0.52 * math.cos(a), r * 0.52 * math.sin(a)),
                   "steel_worn", segs=6, rot=(0, sx * math.pi / 2, 0), parent=w, bevel=False)
    k.cylinder("idler_hub", r * 0.26, 0.08, (sx * 0.26, 0, 0), "gunmetal", segs=18, rot=(0, sx * math.pi / 2, 0),
               parent=w, radius_top=r * 0.2, bevel=0.008)
    # crank arm of the track adjuster to the hull
    k.beam("idler_crank", (sx * 1.0, loc[1] - 0.35, loc[2] + 0.1), (sx * 1.13, loc[1], loc[2]), (0.1, 0.12), WORN,
           parent=root, bevel=0.01)
    _MOTION.wheel(w, r)
    return w


def _sprocket(k, root, loc, r, sx):
    w = k.empty("sprocket", loc, parent=root)
    for s in (-1, 1):
        k.lathe("sprocket_ring", [(-0.035, r * 0.6), (-0.035, r * 0.86), (0.035, r * 0.86), (0.035, r * 0.6)],
                WORN, segs=40, loc=(s * 0.13, 0, 0), rot=vehicle.AXLE_X, parent=w)
        for i in range(N_SPROCKET):
            a = 2 * math.pi * (i + 0.5) / N_SPROCKET
            k.box("sprocket_tooth", (0.07, 0.075, r * 0.3), (s * 0.13, r * 0.94 * math.cos(a), r * 0.94 * math.sin(a)),
                  TRACK, rot=(a - math.pi / 2, 0, 0), parent=w, bevel=0.01)
    k.lathe("sprocket_disc", [(0.0, 0.0), (0.0, r * 0.66), (sx * 0.05, r * 0.6), (sx * 0.1, r * 0.3),
                              (sx * 0.12, 0.0)], G, segs=40, loc=(sx * 0.17, 0, 0), rot=vehicle.AXLE_X, parent=w)
    for i in range(N_SPROCKET):
        a = 2 * math.pi * i / N_SPROCKET
        k.cylinder("sprocket_bolt", 0.016, 0.03, (sx * 0.253, r * 0.4 * math.cos(a), r * 0.4 * math.sin(a)),
                   "steel_worn", segs=6, rot=(0, sx * math.pi / 2, 0), parent=w, bevel=False)
    k.cylinder("sprocket_hub", r * 0.24, 0.06, (sx * 0.29, 0, 0), "brass", segs=18, rot=(0, sx * math.pi / 2, 0),
               parent=w, radius_top=r * 0.18, bevel=0.008)
    k.cylinder("final_drive", 0.3, 0.3, (0.88 if sx > 0 else -1.18, loc[1], loc[2]), WORN, segs=24, rot=(0, math.pi / 2, 0),
               parent=root, bevel=0.02)
    _MOTION.wheel(w, r)
    return w


# ---------------------------------------------------------------------------
# hull
def _sec(zb, zs, ze, zr):
    """Half profile: bottom centre, bottom chamfer, lower side, sponson floor over the
    track, upper side, roof edge chamfer, roof centre."""
    return [(0.0, zb), (0.97, zb), (1.03, zb + 0.06), (1.03, zs), (1.42, zs), (1.42, ze), (1.36, ze + 0.03),
            (0.0, zr)]


def _hull(k, root):
    sections = [
        (-3.25, _sec(0.68, 1.04, 1.40, 1.43)),
        (-3.08, _sec(0.42, 1.04, 1.48, 1.52)),
        (2.30, _sec(0.42, 1.04, 1.48, 1.52)),
        (2.85, _sec(0.42, 1.02, 1.19, 1.23)),
        (3.28, _sec(0.84, 0.9, 0.94, 0.98)),
    ]
    vehicle.hull(k, "hull", sections, G, root)
    for sx in (-1, 1):
        fx.rivets(k, root, (sx * 1.4, -3.0, 1.505), (sx * 1.4, 2.25, 1.505), 20, (sx, 0, 1), r=0.016)
        k.hose("tow_cable", [(sx * 1.3, 2.2, 1.55), (sx * 1.32, 0.9, 1.555), (sx * 1.32, -0.6, 1.555),
                             (sx * 1.3, -2.2, 1.55)], 0.022, "steel_worn", parent=root)
        for y in (2.2, -2.2):
            k.torus("cable_eye", 0.06, 0.016, (sx * 1.3, y + (0.06 if y > 0 else -0.06), 1.55), "steel_worn",
                    rot=(0, math.pi / 2, 0), parent=root, segs=12, tube_segs=4)


def _glacis(k, root):
    """Upper glacis: splash board, headlamps, driver's periscopes, emblem, tow hooks."""
    ang = math.atan2(1.52 - 1.23, 2.85 - 2.30)
    g = k.empty("glacis", (0, 2.30, 1.52), parent=root)
    g.rotation_euler = (-ang, 0, 0)
    arm = math.atan2(0.42, 0.85)
    for s in (-1, 1):
        k.box("splash_board", (0.95, 0.035, 0.08), (s * 0.425, 0.41, 0.04), WORN, rot=(0, 0, -s * arm), parent=g,
              bevel=0.006)
        _headlamp(k, g, (s * 1.12, 0.62, 0.08), ang)
    k.box("vision_hood", (0.5, 0.12, 0.1), (-0.72, 0.1, 0.05), G, parent=g, bevel=0.012)
    for dx in (-0.12, 0.12):
        k.box("periscope", (0.16, 0.05, 0.07), (-0.72 + dx, 0.17, 0.06), "brass", parent=g, bevel=False)
        k.box("periscope_glass", (0.13, 0.012, 0.045), (-0.72 + dx, 0.198, 0.062), "glass", parent=g, bevel=False)
    fx.emblem(k, g, (0.0, 0.86, 0.012), (0, 0, 1), r=0.19)
    fx.rivets(k, g, (-1.3, 0.02, 0.01), (1.3, 0.02, 0.01), 18, (0, 0, 1), r=0.016)
    k.cylinder("driver_hatch", 0.27, 0.05, (-0.72, 1.98, 1.52), G, segs=24, parent=root, bevel=0.01)
    k.cylinder("hatch_hinge", 0.03, 0.22, (-0.72, 1.7, 1.56), "brass", segs=10, rot=(0, math.pi / 2, 0),
               parent=root, bevel=False)
    for sx in (-1, 1):
        k.torus("tow_hook", 0.08, 0.025, (sx * 0.62, 3.3, 0.86), "iron_black", rot=(0, math.pi / 2, 0), parent=root,
                segs=12, tube_segs=5)


def _headlamp(k, g, loc, ang):
    """Brass headlamp facing forward on the glacis (frame g is tilted by -ang)."""
    n = Vector((0, math.cos(ang), math.sin(ang)))
    e = fx._frame(k, g, loc, n, "headlamp")
    k.cylinder("lamp_bracket", 0.03, 0.12, (0, -0.1, -0.12), "iron_black", segs=8, rot=(math.pi / 2, 0, 0),
               parent=e, bevel=False)
    k.lathe("lamp_body", [(-0.12, 0.0), (-0.1, 0.07), (0.0, 0.095), (0.02, 0.0)], "brass", segs=20,
            rot=(math.pi / 2, 0, 0), parent=e)
    k.cylinder("lamp_glass", 0.082, 0.01, (0, 0, 0.012), "glass", segs=20, parent=e, bevel=False)
    for i in range(3):
        k.box("lamp_guard", (0.008, 0.2, 0.012), (-0.05 + i * 0.05, 0, 0.05), "iron_black", parent=e, bevel=False)


def _fenders(k, root):
    """Fender shelves over the tracks: fuel tanks on the right, boxes and tools on the left."""
    for sx in (-1, 1):
        x = sx * 1.56
        k.box("fender", (0.3, 6.74, 0.02), (x, 0.05, 1.05), WORN, parent=root, bevel=False)
        k.box("fender_lip", (0.02, 6.74, 0.07), (sx * 1.705, 0.05, 1.03), WORN, parent=root, bevel=False)
        k.box("mudguard_front", (0.32, 0.36, 0.02), (x, 3.58, 0.97), WORN, rot=(-0.45, 0, 0), parent=root,
              bevel=False)
        k.box("mudguard_rear", (0.32, 0.22, 0.02), (x, -3.38, 1.0), WORN, rot=(0.45, 0, 0), parent=root, bevel=False)
    # right: three external fuel tanks with straps and brass caps, a stowage box
    for y in (0.95, 0.0, -0.95):
        k.box("fuel_tank", (0.27, 0.88, 0.38), (1.56, y, 1.25), G, parent=root, bevel=0.05)
        for dy in (-0.3, 0.3):
            k.box("tank_strap", (0.29, 0.04, 0.4), (1.56, y + dy, 1.25), "iron_black", parent=root, bevel=False)
        k.cylinder("filler_cap", 0.045, 0.04, (1.56, y + 0.38, 1.44), "brass", segs=12, parent=root, bevel=False)
    k.hose("fuel_pipe", [(1.45, 1.35, 1.46), (1.45, 0.0, 1.47), (1.45, -1.4, 1.46)], 0.014, "brass", parent=root)
    k.box("stowage_box", (0.27, 0.8, 0.32), (1.56, -1.95, 1.22), WORN, parent=root, bevel=0.012)
    k.box("box_lid", (0.29, 0.82, 0.03), (1.56, -1.95, 1.39), G, parent=root, bevel=0.006)
    # left: two stowage boxes, spare track links, an oil tank, shovel and crowbar
    for y, mat in ((1.6, G), (0.55, WORN)):
        k.box("stowage_box", (0.27, 0.9, 0.34), (-1.56, y, 1.23), mat, parent=root, bevel=0.012)
        k.box("box_lid", (0.29, 0.92, 0.03), (-1.56, y, 1.41), G if mat == WORN else WORN, parent=root, bevel=0.006)
        k.box("box_latch", (0.03, 0.06, 0.08), (-1.71, y, 1.33), "brass", parent=root, bevel=False)
    for i in range(3):
        k.box("spare_link", (0.06, STEP * 0.86, TRACK_W * 0.9), (-1.48 - i * 0.07, -0.4, 1.33), TRACK,
              rot=(0, 0, 0.0), parent=root, bevel=0.006)
    k.cylinder("oil_tank", 0.17, 0.95, (-1.56, -0.75, 1.24), G, segs=20, rot=(math.pi / 2, 0, 0), parent=root,
               bevel=0.02)
    k.cylinder("oil_cap", 0.04, 0.04, (-1.56, -1.2, 1.41), "brass", segs=12, parent=root, bevel=False)
    k.tube("shovel_haft", (-1.6, -1.85, 1.08), (-1.6, -2.75, 1.08), 0.018, "wood", parent=root, segs=8)
    k.box("shovel_blade", (0.2, 0.26, 0.02), (-1.6, -2.9, 1.08), "steel_worn", parent=root, bevel=False)
    k.tube("crowbar", (-1.5, -1.85, 1.08), (-1.5, -3.1, 1.08), 0.016, "iron_black", parent=root, segs=6)


def _deck(k, root):
    """Engine deck: louvred grilles, access plate, filler caps, twin brass-banded stacks."""
    for sx in (-1, 1):
        k.box("grille_frame", (0.92, 1.3, 0.03), (sx * 0.62, -1.95, 1.525), WORN, parent=root, bevel=0.006)
        for i in range(10):
            k.box("engine_louvre", (0.82, 0.07, 0.025), (sx * 0.62, -1.4 - i * 0.12, 1.55), "iron_black",
                  rot=(0.5, 0, 0), parent=root, bevel=False)
    k.box("access_plate", (0.28, 1.25, 0.03), (0, -1.95, 1.535), G, parent=root, bevel=0.006)
    fx.rivets(k, root, (0.0, -1.4, 1.555), (0.0, -2.5, 1.555), 6, (0, 0, 1), r=0.014)
    k.box("rear_grille", (2.3, 0.3, 0.03), (0, -2.85, 1.53), WORN, parent=root, bevel=0.006)
    for i in range(14):
        k.box("grille_bar", (0.025, 0.28, 0.03), (-1.05 + i * 2.1 / 13, -2.85, 1.555), "iron_black", parent=root,
              bevel=False)
    for sx in (-1, 1):
        fx.stack(k, root, (sx * 1.18, -2.98, 1.5), 0.62, r=0.075)
        k.cylinder("filler_cap", 0.07, 0.04, (sx * 0.95, -0.85, 1.53), "brass", segs=14, parent=root, bevel=False)
    fx.gauge(k, root, (0.55, -0.82, 1.56), (0, 0.4, 1), r=0.06)


def _rear(k, root):
    """Rear plate: two fuel drums on brackets, the timber unditching beam, tail lights."""
    for sx in (-1, 1):
        x = sx * 0.6
        k.cylinder("drum", 0.29, 0.86, (x - 0.43, -3.55, 1.02), G if sx < 0 else WORN, segs=26,
                   rot=(0, math.pi / 2, 0), parent=root, bevel=0.02)
        for dx in (0.18, 0.68):
            k.torus("drum_hoop", 0.292, 0.012, (x - 0.43 + dx, -3.55, 1.02), "iron_black", rot=(0, math.pi / 2, 0),
                    parent=root, segs=26, tube_segs=4)
        k.cylinder("drum_bung", 0.04, 0.02, (x + sx * 0.43, -3.55, 1.16), "brass", segs=10, rot=(0, math.pi / 2, 0),
                   parent=root, bevel=False)
        k.box("drum_bracket", (0.06, 0.32, 0.5), (x, -3.4, 0.92), "iron_black", parent=root, bevel=False)
        k.box("tail_light", (0.1, 0.04, 0.07), (sx * 1.2, -3.27, 1.3), "paint_faction_red", parent=root, bevel=False)
    k.cylinder("unditching_beam", 0.13, 3.0, (-1.5, -3.4, 1.48), "timber_tarred", segs=14, rot=(0, math.pi / 2, 0),
               parent=root, bevel=0.02)
    for x in (-1.1, 1.1):
        k.torus("beam_chain", 0.14, 0.012, (x, -3.4, 1.48), "iron_black", rot=(0, math.pi / 2, 0), parent=root,
                segs=16, tube_segs=4)


# ---------------------------------------------------------------------------
# turret
def _turret(k, root):
    t = k.empty("turret", (0, 0.62, 1.52), parent=root)
    prof = [(0.0, 1.13), (0.12, 1.12), (0.3, 1.06), (0.48, 0.94), (0.62, 0.76), (0.72, 0.52), (0.79, 0.26),
            (0.81, 0.0)]
    dome = k.lathe("turret_cast", prof, G, segs=48, rot=(math.pi / 2, 0, 0), parent=t)
    dome.scale = (1.0, 1.06, 1.0)
    band = k.cylinder("turret_band", 1.135, 0.08, (0, 0, 0.05), fx.RED, segs=48, parent=t, bevel=False)
    band.scale = (1.0, 1.06, 1.0)
    k.cylinder("turret_ring", 1.22, 0.07, (0, 0, -0.04), WORN, segs=48, parent=t, bevel=0.01)
    k.cylinder("ring_guard", 1.24, 0.03, (0, 0, -0.01), "gunmetal", segs=48, parent=t, bevel=False)
    # cast gun mantlet and the 100 mm gun with fume extractor and a muzzle ring
    k.lathe("mantlet", [(0.78, 0.0), (0.8, 0.38), (1.05, 0.33), (1.22, 0.24), (1.3, 0.19), (1.32, 0.0)], G, segs=28,
            loc=(0, 0, 0.42), parent=t)
    k.lathe("gun", [(1.28, 0.0), (1.28, 0.15), (1.42, 0.115), (1.7, 0.1), (2.8, 0.092), (2.86, 0.125),
                    (2.95, 0.132), (3.38, 0.132), (3.46, 0.09), (3.98, 0.086), (4.0, 0.098), (4.12, 0.098),
                    (4.12, 0.0)], G, segs=28, loc=(0, 0, 0.42), parent=t)
    k.cylinder("bore", 0.06, 0.012, (0, 4.122, 0.42), "bore", segs=18, rot=(-math.pi / 2, 0, 0), parent=t,
               bevel=False)
    k.tube("gun_band", (0, 2.5, 0.42), (0, 2.66, 0.42), 0.097, fx.RED, parent=t, segs=28, bevel=False)
    # searchlight on the right of the mantlet, gunner's sight hood on the left
    k.beam("light_arm", (0.42, 0.8, 0.5), (0.55, 0.9, 0.62), (0.05, 0.05), "iron_black", parent=t, bevel=False)
    fx.lamp(k, t, (0.55, 1.0, 0.65), (0, 1, 0.08), r=0.13)
    k.box("sight_hood", (0.2, 0.28, 0.16), (-0.42, 0.72, 0.6), G, parent=t, bevel=0.03)
    k.box("sight_glass", (0.14, 0.012, 0.08), (-0.42, 0.865, 0.61), "glass", parent=t, bevel=False)
    # commander's cupola (left rear): brass ring, vision blocks, hatch
    cx, cy = -0.45, -0.22
    k.cylinder("cupola", 0.34, 0.24, (cx, cy, 0.6), G, segs=28, parent=t, bevel=0.02)
    k.cylinder("cupola_ring", 0.36, 0.05, (cx, cy, 0.8), "brass", segs=28, parent=t, bevel=False)
    k.cylinder("cupola_hatch", 0.3, 0.06, (cx, cy, 0.85), WORN, segs=28, parent=t, bevel=0.01)
    for i in range(6):
        a = 2 * math.pi * i / 6 + 0.6
        k.box("vision_block", (0.1, 0.04, 0.07), (cx + 0.345 * math.cos(a), cy + 0.345 * math.sin(a), 0.72), "glass",
              rot=(0, 0, a + math.pi / 2), parent=t, bevel=False)
    # loader's hatch (right) with the AA heavy machine gun on a brass ring
    lx, ly = 0.46, -0.12
    k.cylinder("loader_hatch", 0.29, 0.05, (lx, ly, 0.74), WORN, segs=24, parent=t, bevel=0.01)
    k.torus("aa_ring", 0.31, 0.022, (lx, ly, 0.8), "brass", parent=t, segs=28, tube_segs=6)
    k.tube("aa_post", (lx + 0.3, ly + 0.2, 0.66), (lx + 0.3, ly + 0.2, 1.02), 0.025, "gunmetal", parent=t, segs=8)
    k.tube("hmg_barrel", (lx + 0.3, ly, 1.04), (lx + 0.3, ly + 1.35, 1.06), 0.022, "gunmetal", parent=t, segs=10)
    k.tube("hmg_jacket", (lx + 0.3, ly, 1.04), (lx + 0.3, ly + 0.65, 1.05), 0.04, "gunmetal", parent=t, segs=12)
    for i in range(4):
        k.torus("jacket_rib", 0.043, 0.006, (lx + 0.3, ly + 0.15 + i * 0.13, 1.045), "brass",
                rot=(math.pi / 2, 0, 0), parent=t, segs=14, tube_segs=4)
    k.box("hmg_receiver", (0.1, 0.36, 0.12), (lx + 0.3, ly - 0.15, 1.04), "gunmetal", parent=t, bevel=0.01)
    k.box("hmg_ammo_box", (0.12, 0.22, 0.16), (lx + 0.42, ly - 0.15, 0.98), WORN, parent=t, bevel=0.01)
    # stowage on the rear of the turret: rail, rolled tarpaulin and a box
    for sx in (-1, 1):
        k.tube("bustle_rail", (sx * 0.62, -0.92, 0.32), (sx * 0.62, -1.3, 0.32), 0.02, "iron_black", parent=t, segs=6)
    k.tube("bustle_rail", (-0.62, -1.3, 0.32), (0.62, -1.3, 0.32), 0.02, "iron_black", parent=t, segs=6)
    k.cylinder("tarp_roll", 0.15, 1.2, (-0.6, -1.12, 0.4), "canvas", segs=20, rot=(0, math.pi / 2, 0), parent=t,
               bevel=0.03)
    for x in (-0.35, 0.35):
        k.torus("tarp_strap", 0.155, 0.012, (x, -1.12, 0.4), "leather", rot=(0, math.pi / 2, 0), parent=t,
                segs=16, tube_segs=4)
    # grab rails, antenna with the pennant, emblems on the turret sides
    for sx in (-1, 1):
        k.hose("grab_rail", [(sx * 0.82, 0.3, 0.6), (sx * 0.86, -0.15, 0.6), (sx * 0.8, -0.55, 0.6)], 0.014,
               "iron_black", parent=t)
        fx.emblem(k, t, (sx * 1.03, -0.2, 0.36), (sx, 0, 0.67), r=0.24)
    k.cylinder("antenna_base", 0.05, 0.1, (-0.62, -0.72, 0.48), "brass", segs=12, parent=t, bevel=False)
    k.tube("antenna", (-0.62, -0.72, 0.56), (-0.66, -0.85, 2.55), 0.006, "gunmetal", parent=t, segs=6, bevel=False)
    fx.pennant(k, t, (-0.66, -0.85, 2.15), h=0.4, w=0.5)
