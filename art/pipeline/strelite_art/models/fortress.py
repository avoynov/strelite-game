"""Land fortress of the Iron Concord (bg: „Крепост“), the boss: a land battleship 14.6 m
long and 8.1 m wide on four track units, built to the guns' standard at real size.

Layout from front to back: a wedge plough with teeth before the tracks, a long sloped
glacis, the main turret with twin long guns (fume extractors, muzzle brakes, oxblood
bands) and a brass-hooded rangefinder across its roof, the round conning tower with its
vision band, searchlight and mast, two raked funnels, and an aft turret with a short gun
covering the rear. A sloped, riveted casemate carries them all; the hull sides overhang
the tracks, and riveted skirt plates hide the top of the outer tracks.

Running gear: four tracks of 1.0 m (two a side), seven double road wheels each, idler
in front, sprocket behind, separate links with grousers; every part sized to wrap
(vehicle.TrackPlan), so the tracks run in MOVE_FRAMES frames per link.

Concord touches: oxblood turret bands, funnel bands and gun bands, a stripe along the
casemate, emblems on the glacis, the turret roof and the skirts, brass vents, rims,
gauges, rangefinder hoods, cupola ring, lamp; pennants on the mast and the turret.

What makes it unmistakable at game zoom: a huge tracked block with a twin-gun turret,
the conning tower and two funnels: a battleship on land.

The vehicle faces local +Y; render_sprites.py --enemy turns it. Returns (root, root).
"""
import math

from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit
from . import faction as fx
from . import vehicle

SPRITE_FRAME_M = 21.0
LENGTH_M = 17.3           # gun tips to the rear plate
RADIUS_M = 7.5
G, WORN, TRACK = "paint_enemy", "paint_enemy_worn", "track_steel"

TRACK_W = 1.0
TRACKS_X = (-3.45, -1.95, 1.95, 3.45)
PLAN = vehicle.TrackPlan(road_y=tuple(5.4 - 1.8 * i for i in range(7)), idler_yz=(6.55, 0.78),
                         sprocket_yz=(-6.55, 0.85), n_road=15, n_idler=13, n_sprocket=12, pitch=0.24, thick=0.09,
                         grouser=0.035)
MOVE_FRAMES = 4
MOVE_KIND = "tracks"
MOVE_CYCLE_M = PLAN.step
_MOTION = vehicle.Motion(MOVE_FRAMES, MOVE_CYCLE_M)
DECK = 3.05               # hull deck height
TOP = 4.35                # casemate roof


def set_move_frame(f, scene=None):
    _MOTION.set(f)


def build(style, level=1):
    global _MOTION
    _MOTION = vehicle.Motion(MOVE_FRAMES, MOVE_CYCLE_M)
    k = Kit(style)
    root = k.empty("fortress")
    mp.set_reference(root)
    for x in TRACKS_X:
        PLAN.build(k, root, _MOTION, x, TRACK_W, G, WORN, TRACK, horn=False, arms=abs(x) < 3)
    _hull(k, root)
    _plough(k, root)
    _casemate(k, root)
    _main_turret(k, root)
    _conning_tower(k, root)
    _funnels(k, root)
    _aft_turret(k, root)
    _deck(k, root)
    _plating(k, root)
    return root, root


# ---------------------------------------------------------------------------
def _sec(zb, zs, ze, zr):
    """Half profile: belly, belly chamfer, lower side between the inner tracks, sponson
    floor over the tracks, hull side, deck chamfer, deck centre."""
    return [(0.0, zb), (1.28, zb), (1.38, zb + 0.1), (1.38, zs), (4.05, zs), (4.05, ze), (3.75, zr - 0.04),
            (0.0, zr)]


def _hull(k, root):
    vehicle.hull(k, "hull", [
        (-7.25, _sec(1.05, 1.5, 2.45, 2.75)),
        (-7.0, _sec(0.62, 1.5, 2.6, DECK)),
        (5.0, _sec(0.62, 1.5, 2.6, DECK)),
        (6.6, _sec(0.62, 1.44, 2.05, 2.3)),
        (7.35, _sec(1.2, 1.32, 1.46, 1.62)),
    ], G, root, bevel=0.02)
    for sx in (-1, 1):
        # riveted skirt plates over the outer track, hanging below the hull side
        for i in range(6):
            y = -5.75 + i * 2.3
            k.box("skirt", (0.07, 2.22, 0.62), (sx * 4.07, y, 1.2), WORN if i % 2 else G,
                  rot=(0, sx * 0.04 * (1 if i % 3 else -1), 0), parent=root, bevel=0.012)
            fx.rivets(k, root, (sx * 4.11, y - 0.98, 1.44), (sx * 4.11, y + 0.98, 1.44), 8, (sx, 0, 0), r=0.025)
        fx.rivets(k, root, (sx * 4.07, -6.9, 2.52), (sx * 4.07, 4.9, 2.52), 30, (sx, 0, 0), r=0.03)
        fx.rivets(k, root, (sx * 3.95, -6.9, 2.88), (sx * 3.95, 4.9, 2.88), 30, (sx, 0, 0.4), r=0.03)
        fx.emblem(k, root, (sx * 4.12, -1.15, 1.22), (sx, 0, 0), r=0.27)
        fx.emblem(k, root, (sx * 4.06, 1.2, 2.06), (sx, 0, 0), r=0.4)
        # machine-gun sponsons in ball mounts on the hull sides
        for y in (3.4, -4.4):
            c = Vector((sx * 4.05, y, 2.05))
            k.lathe("sponson", [(0.0, 0.62), (0.22, 0.56), (0.42, 0.36), (0.5, 0.0)], G, segs=28, loc=c,
                    rot=(0, 0, -sx * math.pi / 2), parent=root)
            k.torus("sponson_rim", 0.62, 0.03, c + Vector((sx * 0.02, 0, 0)), "brass", rot=(0, math.pi / 2, 0),
                    parent=root, segs=28, tube_segs=5)
            k.tube("sponson_mg", c + Vector((sx * 0.42, 0, 0.02)), c + Vector((sx * 0.75, 0.95, 0.05)), 0.035,
                   "gunmetal", parent=root, segs=10)
        # big brass headlamps on the glacis corners, tow hooks
        _lamp(k, root, (sx * 3.25, 6.85, 2.1), (0, 1, 0.55), 0.2)
        k.torus("tow_hook", 0.16, 0.05, (sx * 1.0, 7.33, 1.3), "iron_black", rot=(0, math.pi / 2, 0), parent=root,
                segs=14, tube_segs=6)
    # glacis: emblem, driver's vision ports
    ang = math.atan2(DECK - 2.3, 1.6)
    fx.emblem(k, root, (0, 6.0, 2.6), (0, math.sin(ang), math.cos(ang)), r=0.5)
    for sx in (-1, 1):
        k.box("vision_port", (0.8, 0.14, 0.16), (sx * 1.5, 5.06, DECK + 0.03), "brass", parent=root, bevel=0.02)
        k.box("vision_slit", (0.66, 0.02, 0.05), (sx * 1.5, 5.135, DECK + 0.05), "glass", parent=root, bevel=False)
    # rear plate: engine louvres and doors
    for sx in (-1, 1):
        k.box("rear_door", (1.1, 0.06, 0.9), (sx * 0.75, -7.2, 1.9), WORN, rot=(-0.25, 0, 0), parent=root,
              bevel=0.012)
        for dz in (-0.25, 0.25):
            k.cylinder("door_hinge", 0.04, 0.16, (sx * 1.3, -7.24, 1.9 + dz), "brass", segs=10, parent=root,
                       bevel=False)


def _lamp(k, root, loc, normal, r):
    e = fx._frame(k, root, loc, normal, "headlamp")
    k.lathe("lamp_body", [(-r * 1.2, 0.0), (-r, r * 0.75), (0.0, r), (r * 0.2, 0.0)], "brass", segs=24,
            rot=(math.pi / 2, 0, 0), parent=e)
    k.cylinder("lamp_glass", r * 0.86, 0.01, (0, 0, r * 0.12), "glass", segs=24, parent=e, bevel=False)
    for i in range(3):
        k.box("lamp_guard", (0.015, r * 2.1, 0.02), (-r * 0.5 + i * r * 0.5, 0, r * 0.45), "iron_black", parent=e,
              bevel=False)
    return e


def _plough(k, root):
    """Wedge plough with teeth before the tracks, on two push beams to the nose."""
    tip, side = Vector((0, 7.95, 0.0)), Vector((3.95, 7.3, 0.0))
    for sx in (-1, 1):
        a = Vector((sx * side.x, side.y, 0))
        d = a - tip
        mid = (a + tip) / 2
        rot = (0, 0, math.atan2(d.y, d.x))
        k.box("plough_blade", (d.length + 0.1, 0.1, 1.05), (mid.x, mid.y, 0.85), "iron_black", rot=rot,
              parent=root, bevel=0.02)
        k.box("plough_rib", (d.length, 0.14, 0.08), (mid.x, mid.y - 0.03, 1.36), WORN, rot=rot, parent=root,
              bevel=0.01)
        n = 8
        for i in range(n):
            p = tip.lerp(a, (i + 0.5) / n)
            k.box("plough_tooth", (0.14, 0.22, 0.28), (p.x, p.y + 0.05, 0.3), "steel_worn", rot=rot, parent=root,
                  bevel=0.02)
        k.beam("push_beam", (sx * 1.6, 7.3, 1.15), (sx * 1.4, 7.75, 1.0), (0.22, 0.26), "iron_black", parent=root,
               bevel=0.02)
    fx.band(k, root, (-0.9, 7.82, 1.15), (0.9, 7.82, 1.15), (0.06, 0.22))


def _casemate(k, root):
    def s(zt, w):
        return [(0.0, DECK - 0.05), (w, DECK - 0.05), (w, DECK + 0.1), (w - 0.4, zt - 0.03), (0.0, zt)]
    vehicle.hull(k, "casemate", [
        (-6.1, s(TOP - 0.45, 2.6)),
        (-5.7, s(TOP, 2.95)),
        (3.4, s(TOP, 2.95)),
        (4.0, s(TOP - 0.5, 2.6)),
    ], G, root, bevel=0.02)
    for sx in (-1, 1):
        k.box("casemate_stripe", (0.012, 9.0, 0.22), (sx * 2.695, -1.15, TOP - 0.42), fx.RED,
              rot=(0, -sx * math.atan2(0.4, TOP - DECK - 0.13), 0), parent=root, bevel=False)
        fx.rivets(k, root, (sx * 2.55, -5.6, TOP + 0.0), (sx * 2.55, 3.3, TOP + 0.0), 26, (sx, 0, 1), r=0.028)
        fx.rivets(k, root, (sx * 2.97, -5.6, DECK + 0.12), (sx * 2.97, 3.3, DECK + 0.12), 26, (sx, 0, 0), r=0.028)
        # spare track links hung on the casemate sides
        for i in range(5):
            k.box("spare_link", (0.06, PLAN.step * 0.85, TRACK_W * 0.85), (sx * 2.86, -2.0 + i * 0.26, 3.75),
                  TRACK, rot=(0, sx * 0.33, 0), parent=root, bevel=0.01)


def _main_turret(k, root):
    t = k.empty("main_turret", (0, 1.25, TOP), parent=root)

    def s(zt, w):
        return [(0.0, 0.0), (w, 0.0), (w + 0.12, 0.3), (w, zt - 0.3), (w - 0.6, zt - 0.02), (0.0, zt)]
    vehicle.hull(k, "turret_body", [(-2.05, s(1.3, 1.25)), (-1.65, s(1.5, 1.6)), (1.2, s(1.5, 1.6)),
                                    (1.95, s(1.12, 1.3))], G, t, bevel=0.03)
    k.cylinder("turret_ring", 2.0, 0.14, (0, 0, -0.1), WORN, segs=48, parent=t, bevel=0.01)
    _band(k, t, [(-2.05, 1.25), (-1.65, 1.6), (1.2, 1.6), (1.95, 1.3)], 0.34, 0.52, "turret_band")
    k.box("mantlet", (2.4, 0.45, 0.95), (0, 1.98, 0.62), G, parent=t, bevel=0.12)
    for sx in (-1, 1):
        x = sx * 0.66
        k.lathe("gun", [(2.0, 0.0), (2.0, 0.3), (2.25, 0.23), (2.5, 0.2), (4.9, 0.18), (5.0, 0.25), (5.15, 0.26),
                        (5.8, 0.26), (5.95, 0.17), (8.05, 0.155), (8.1, 0.22), (8.55, 0.22), (8.6, 0.0)], G,
                segs=28, loc=(x, 0, 0.66), parent=t)
        for y in (8.18, 8.36):
            k.box("brake_slot", (0.46, 0.08, 0.1), (x, y, 0.66), "iron_black", parent=t, bevel=False)
        k.cylinder("bore", 0.11, 0.012, (x, 8.6, 0.66), "bore", segs=18, rot=(-math.pi / 2, 0, 0), parent=t,
                   bevel=False)
        k.tube("gun_band", (x, 7.0, 0.66), (x, 7.3, 0.66), 0.165, fx.RED, parent=t, segs=28, bevel=False)
        k.torus("breech_ring", 0.24, 0.04, (x, 2.32, 0.66), "brass", rot=(math.pi / 2, 0, 0), parent=t, segs=24,
                tube_segs=6)
    # rangefinder across the turret roof with brass hoods at the ends
    k.tube("rangefinder", (-2.15, -1.2, 1.62), (2.15, -1.2, 1.62), 0.13, G, parent=t, segs=18)
    for sx in (-1, 1):
        k.box("rangefinder_hood", (0.32, 0.36, 0.34), (sx * 2.15, -1.2, 1.64), "brass", parent=t, bevel=0.06)
        k.box("rf_window", (0.02, 0.2, 0.14), (sx * 2.315, -1.2, 1.66), "glass", parent=t, bevel=False)
        k.box("rf_post", (0.16, 0.16, 0.2), (sx * 0.9, -1.2, 1.5), WORN, parent=t, bevel=0.02)
    # commander's cupola with a brass ring, loader's hatch, vents, emblem and pennant
    k.cylinder("cupola", 0.42, 0.32, (-0.8, -0.3, 1.45), G, segs=24, parent=t, bevel=0.02)
    k.cylinder("cupola_ring", 0.44, 0.06, (-0.8, -0.3, 1.74), "brass", segs=24, parent=t, bevel=False)
    k.cylinder("cupola_hatch", 0.38, 0.06, (-0.8, -0.3, 1.8), WORN, segs=24, parent=t, bevel=0.01)
    k.cylinder("loader_hatch", 0.36, 0.05, (0.85, -0.2, 1.5), WORN, segs=22, parent=t, bevel=0.01)
    fx.emblem(k, t, (0.0, 0.75, 1.505), (0, 0, 1), r=0.45)
    fx.pennant(k, t, (-0.8, -0.3, 1.86), h=1.3, w=0.8)
    for sx in (-1, 1):
        fx.gauge(k, t, (sx * 1.4, 1.95, 0.62), (0, 1, 0), r=0.09)


def _band(k, t, widths, z0, z1, name, flare=0.12):
    """Oxblood band round a faceted turret built by vehicle.hull: (y, w) per section,
    proud of the sloped sides by 2 cm between heights z0 and z1."""
    vehicle.hull(k, name, [(y, [(0.0, z0), (w + flare + 0.02, z0), (w + flare + 0.02, z1), (0.0, z1)])
                           for y, w in widths], fx.RED, t, bevel=False)


def _conning_tower(k, root):
    c = Vector((0, -1.75, TOP))
    k.cylinder("conning_tower", 0.85, 1.55, c, G, segs=28, parent=root, bevel=0.03)
    k.cylinder("vision_band", 0.865, 0.16, c + Vector((0, 0, 1.12)), "brass", segs=28, parent=root, bevel=False)
    for i in range(10):
        a = 2 * math.pi * i / 10 + 0.3
        k.box("vision_slit", (0.26, 0.04, 0.06), c + Vector((0.875 * math.cos(a), 0.875 * math.sin(a), 1.2)), "glass",
              rot=(0, 0, a + math.pi / 2), parent=root, bevel=False)
    k.cylinder("tower_cap", 0.9, 0.12, c + Vector((0, 0, 1.55)), WORN, segs=28, parent=root, bevel=0.02,
               radius_top=0.78)
    k.cylinder("cap_rim", 0.91, 0.05, c + Vector((0, 0, 1.53)), "brass", segs=28, parent=root, bevel=False)
    _lamp(k, root, c + Vector((0, 0.35, 1.95)), (0, 1, 0.1), 0.32)
    k.box("lamp_platform", (0.8, 0.8, 0.08), c + Vector((0, 0.3, 1.68)), "iron_black", parent=root, bevel=0.01)
    # mast with yard, aerial wires and the pennant
    m0, m1 = c + Vector((0, -0.4, 1.67)), c + Vector((0, -0.55, 5.0))
    k.tube("mast", m0, m1, 0.07, WORN, radius_end=0.04, parent=root, segs=12)
    k.tube("yard", m0.lerp(m1, 0.7) + Vector((-1.1, 0, 0)), m0.lerp(m1, 0.7) + Vector((1.1, 0, 0)), 0.03, WORN,
           parent=root, segs=8)
    for sx in (-1, 1):
        k.tube("aerial", m0.lerp(m1, 0.7) + Vector((sx * 1.05, 0, 0)), Vector((sx * 1.4, -6.6, DECK + 0.1)), 0.008,
               "gunmetal", parent=root, segs=4, bevel=False)
    fx.pennant(k, root, m1 - Vector((0, 0, 0.1)), h=0.6, w=1.3)


def _funnels(k, root):
    for sx in (-1, 1):
        b = Vector((sx * 1.2, -3.55, TOP - 0.05))
        top = b + Vector((0, -0.45, 2.55))
        k.tube("funnel", b, top, 0.46, G, radius_end=0.42, parent=root, segs=24)
        d = (top - b).normalized()
        k.tube("funnel_band", b + d * 1.85, b + d * 2.15, 0.445, fx.RED, parent=root, segs=24, bevel=False)
        k.tube("funnel_ring", b + d * 1.5, b + d * 1.58, 0.455, "brass", parent=root, segs=24, bevel=False)
        k.tube("funnel_cap", top, top + d * 0.14, 0.47, "iron_black", parent=root, segs=24, bevel=False)
        k.tube("funnel_soot", top - d * 0.02, top + d * 0.15, 0.36, "bore", parent=root, segs=20, bevel=False)
        k.tube("funnel_foot", b - d * 0.02, b + d * 0.25, 0.56, WORN, radius_end=0.48, parent=root, segs=24)
        fx.gauge(k, root, b + Vector((0, 0.48, 0.6)), (0, 1, 0), r=0.1)
    k.tube("steam_pipe", (-1.2, -3.3, TOP + 0.7), (1.2, -3.3, TOP + 0.7), 0.07, "brass", parent=root, segs=12)


def _aft_turret(k, root):
    t = k.empty("aft_turret", (0, -5.1, TOP), parent=root)
    t.rotation_euler = (0, 0, math.pi)

    def s(zt, w):
        return [(0.0, 0.0), (w, 0.0), (w + 0.08, 0.22), (w, zt - 0.2), (w - 0.4, zt - 0.02), (0.0, zt)]
    vehicle.hull(k, "aft_turret_body", [(-0.95, s(0.9, 0.85)), (-0.7, s(1.05, 1.05)), (0.6, s(1.05, 1.05)),
                                        (1.05, s(0.8, 0.85))], G, t, bevel=0.025)
    k.cylinder("aft_ring", 1.2, 0.1, (0, 0, -0.08), WORN, segs=40, parent=t, bevel=0.01)
    _band(k, t, [(-0.95, 0.85), (-0.7, 1.05), (0.6, 1.05), (1.05, 0.85)], 0.25, 0.38, "aft_band", flare=0.08)
    k.box("aft_mantlet", (0.7, 0.3, 0.6), (0, 1.1, 0.48), G, parent=t, bevel=0.08)
    k.lathe("aft_gun", [(1.15, 0.0), (1.15, 0.2), (1.35, 0.15), (2.7, 0.13), (2.72, 0.17), (2.95, 0.17), (2.97, 0.0)],
            G, segs=24, loc=(0, 0, 0.5), parent=t)
    k.cylinder("cupola", 0.3, 0.22, (0.4, -0.3, 0.98), G, segs=20, parent=t, bevel=0.02)
    k.cylinder("cupola_ring", 0.32, 0.05, (0.4, -0.3, 1.18), "brass", segs=20, parent=t, bevel=False)


def _deck(k, root):
    """Vents, hatches, stowage and timber on the deck round the casemate."""
    for x, y in ((-2.0, 4.3), (2.0, 4.3), (-3.3, -6.3), (3.3, -6.3)):
        k.tube("vent_stem", (x, y, DECK), (x, y, DECK + 0.6), 0.1, WORN, parent=root, segs=14)
        k.lathe("vent_cowl", [(0.0, 0.0), (0.0, 0.26), (0.12, 0.24), (0.2, 0.12), (0.22, 0.0)], "brass", segs=20,
                loc=(x, y, DECK + 0.6), rot=(math.pi / 2, 0, 0), parent=root)
    for x in (-1.6, 1.6):
        k.cylinder("deck_hatch", 0.42, 0.06, (x, -6.6, DECK - 0.06), WORN, segs=24, parent=root, bevel=0.01)
    for i, (x, y) in enumerate(((-3.38, 0.5), (-3.38, 1.45), (3.38, 0.9), (3.38, 1.85))):
        k.box("crate", (0.6, 0.85, 0.5), (x, y, DECK + 0.25), "timber_tarred" if i % 3 else G,
              rot=(0, 0, 0.06 * (1 if i % 2 else -1)), parent=root, bevel=0.02)
    for i in range(2):
        k.cylinder("timber_beam", 0.15, 2.4, (3.45 - 0.0, 1.8 + i * 0.32 - 3.4, DECK + 0.15), "timber_tarred",
                   segs=14, rot=(math.pi / 2, 0, 0), parent=root, bevel=0.02)
        k.cylinder("timber_beam", 0.15, 2.4, (-3.45, 1.8 + i * 0.32 - 3.4, DECK + 0.15), "timber_tarred",
                   segs=14, rot=(math.pi / 2, 0, 0), parent=root, bevel=0.02)
    k.cylinder("cable_reel", 0.35, 0.5, (3.15, -5.0, DECK + 0.35), "iron_black", segs=24, rot=(0, math.pi / 2, 0),
               parent=root, bevel=0.02)
    k.cylinder("cable_coil", 0.3, 0.44, (3.18, -5.0, DECK + 0.35), "steel_worn", segs=24, rot=(0, math.pi / 2, 0),
               parent=root, bevel=0.02)


def _plating(k, root):
    """Armour plating: the big flat faces read as separate plates (alternating fresh and
    worn paint, joint strips with rivets), and the casemate carries lifebuoys and
    ladders like a ship."""
    for i in range(5):
        for j, sx in enumerate((-1, 1)):
            k.box("roof_plate", (2.4, 1.74, 0.03), (sx * 1.25, -5.0 + i * 1.82, TOP + 0.005),
                  WORN if (i + j) % 2 else G, parent=root, bevel=0.006)
    tilt = math.atan2(0.4, TOP - DECK - 0.13)
    for sx in (-1, 1):
        for i in range(5):
            y = -5.8 + i * 2.32
            k.box("deck_plate", (0.72, 2.24, 0.025), (sx * 3.37, y + 1.16, DECK - 0.022), G if i % 2 else WORN,
                  parent=root, bevel=0.005)
        for y in (-6.0, -3.7, -1.4, 0.9, 5.0):
            k.box("side_strip", (0.03, 0.14, 1.0), (sx * 4.065, y, 2.06), WORN, parent=root, bevel=0.005)
            fx.rivets(k, root, (sx * 4.085, y, 1.66), (sx * 4.085, y, 2.46), 5, (sx, 0, 0), r=0.022)
        for y in (-4.85, -2.6, -0.35, 1.9):
            k.box("casemate_strip", (0.03, 0.13, 1.18), (sx * 2.76, y, (DECK + TOP) / 2 + 0.04), WORN,
                  rot=(0, -sx * tilt, 0), parent=root, bevel=0.005)
        # lifebuoys and a ladder on the casemate sides
        for y in (-3.7, 2.6):
            c = Vector((sx * 2.86, y, 3.8))
            n = Vector((sx * math.cos(tilt), 0, math.sin(tilt)))
            e = fx._frame(k, root, c, n, "lifebuoy")
            k.torus("lifebuoy", 0.26, 0.07, (0, 0, 0.07), "paint_white", parent=e, segs=24, tube_segs=8)
            for q in range(4):
                a = math.pi / 4 + q * math.pi / 2
                pq = Vector((0.26 * math.cos(a), 0.26 * math.sin(a), 0.07))
                tq = Vector((-math.sin(a), math.cos(a), 0)) * 0.06
                k.tube("buoy_band", pq - tq, pq + tq, 0.074, fx.RED, parent=e, segs=10, bevel=False)
            k.hose("buoy_line", [(c.x, c.y - 0.3, c.z + 0.25), (c.x + sx * 0.12, c.y, c.z - 0.2),
                                 (c.x, c.y + 0.3, c.z + 0.25)], 0.012, "rope", parent=root)
        for i in range(6):
            z = DECK + 0.2 + i * 0.2
            x = 2.95 - 0.4 * (z - DECK - 0.1) / (TOP - DECK - 0.13) + 0.07
            k.tube("ladder_rung", (sx * x, -5.2, z), (sx * x, -4.75, z), 0.016, "brass", parent=root, segs=8,
                   bevel=False)
