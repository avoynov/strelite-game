"""Eight-wheeled armoured personnel carrier of the Iron Concord (bg: „БТР“), built to
the guns' standard at real size: 7.6 x 2.9 m boat-shaped hull on four axles, 2.4 m to
the turret roof, small cone turret with a heavy machine gun and a coaxial gun, side
doors and roof hatches for the squad it carries (four infantry jump out when it dies).

Armour is faceted plate, welded: lower hull sloped in under the sides, upper sides
sloped in to the roof, a long glacis and a sharp swimming bow with a folded trim vane.
Concord touches: brass periscopes, vision-block rims and hatch hinges, twin brass
spark-arrester stacks at the rear, the oxblood turret band and emblem.

What makes it unmistakable at game zoom: a long low boat hull on eight big tyres, the
small turret a third of the way back with its long gun, the pointed bow.

Movement: wheels roll (4 frames; the disc pattern repeats every 1/8 turn).
The vehicle faces local +Y; render_sprites.py --enemy turns it. Returns (root, root).
"""
import math

from .. import materials_photoreal as mp
from ..geo import Kit
from . import faction as fx
from . import vehicle

SPRITE_FRAME_M = 10.0
LENGTH_M = 7.6
RADIUS_M = 3.8
G, WORN = "paint_enemy", "paint_enemy_worn"
R_WHEEL, WHEEL_X, WHEEL_W = 0.55, 1.2, 0.36
AXLES = (2.35, 0.95, -0.85, -2.25)

HOLES = 8
MOVE_FRAMES = 4
MOVE_KIND = "wheels"
MOVE_CYCLE_M = 2 * math.pi * R_WHEEL / HOLES
_MOTION = vehicle.Motion(MOVE_FRAMES, MOVE_CYCLE_M)


def set_move_frame(f, scene=None):
    _MOTION.set(f)


def build(style, level=1):
    global _MOTION
    _MOTION = vehicle.Motion(MOVE_FRAMES, MOVE_CYCLE_M)
    k = Kit(style)
    root = k.empty("apc")
    mp.set_reference(root)
    for y in AXLES:
        for sx in (-1, 1):
            vehicle.lug_wheel(k, root, _MOTION, (sx * WHEEL_X, y, R_WHEEL), R_WHEEL, WHEEL_W, WORN, holes=HOLES)
    _hull(k, root)
    _deck(k, root)
    _turret(k, root)
    _stowage(k, root)
    return root, root


# half profiles: bottom centre, bottom edge, lower side, waist (fender line), roof edge, roof centre
def _sec(zb, xb, xl, zl, xw, zw, xu, zu, zr):
    return [(0.0, zb), (xb, zb), (xl, zl), (xw, zw), (xu, zu), (0.0, zr)]


def _hull(k, root):
    sections = [
        (-3.78, _sec(0.62, 0.8, 1.2, 0.9, 1.3, 1.32, 1.05, 1.92, 1.95)),
        (-3.55, _sec(0.5, 0.92, 1.33, 0.92, 1.43, 1.36, 1.1, 2.02, 2.04)),
        (2.15, _sec(0.5, 0.92, 1.33, 0.92, 1.43, 1.36, 1.1, 2.02, 2.04)),
        (2.95, _sec(0.6, 0.86, 1.3, 0.98, 1.4, 1.36, 1.0, 1.66, 1.68)),
        (3.62, _sec(0.98, 0.7, 1.08, 1.1, 1.2, 1.3, 0.75, 1.34, 1.36)),
        (3.86, _sec(1.16, 0.5, 0.82, 1.19, 0.86, 1.23, 0.5, 1.25, 1.26)),
    ]
    vehicle.hull(k, "hull", sections, G, root)
    for sx in (-1, 1):
        # fender over the wheels along the waist
        k.box("fender", (0.3, 6.9, 0.03), (sx * 1.48, -0.3, 1.34), WORN, parent=root, bevel=False)
        for y in AXLES:
            k.box("mud_flap", (0.26, 0.02, 0.22), (sx * 1.46, y - 0.62, 1.2), "rubber", parent=root, bevel=False)
        # side door between the 2nd and 3rd axles, on the upper sloped side
        tilt = math.atan2(1.43 - 1.1, 2.02 - 1.36)
        door = k.empty("door", (sx * 1.27, 0.05, 1.7), parent=root)
        door.rotation_euler = (0, -sx * tilt, 0)
        k.box("door_plate", (0.04, 0.8, 0.58), (sx * 0.02, 0, 0), WORN, parent=door, bevel=0.008)
        for dz in (-0.18, 0.18):
            k.cylinder("door_hinge", 0.025, 0.12, (sx * 0.04, -0.42, dz), "brass", segs=10, parent=door, bevel=False)
        k.box("door_handle", (0.03, 0.12, 0.03), (sx * 0.05, 0.3, 0.05), "steel_worn", parent=door, bevel=False)
        # firing ports and vision blocks along the upper side
        for y in (1.75, -1.0, -1.7, -2.6):
            port = k.empty("firing_port", (sx * 1.26, y, 1.72), parent=root)
            port.rotation_euler = (0, -sx * tilt, 0)
            k.cylinder("port_ball", 0.075, 0.05, (sx * 0.02, 0, 0), "gunmetal", segs=14, rot=(0, math.pi / 2, 0),
                       parent=port, bevel=0.01)
            k.box("vision_block", (0.04, 0.2, 0.07), (sx * 0.02, 0, 0.17), "glass", parent=port, bevel=False)
            k.box("vision_rim", (0.03, 0.24, 0.1), (sx * 0.005, 0, 0.17), "brass", parent=port, bevel=False)
        fx.rivets(k, root, (sx * 1.425, -3.5, 1.38), (sx * 1.425, 2.2, 1.38), 22, (sx, 0, 0), r=0.016)
        fx.emblem(k, root, (sx * 1.3, -2.05, 1.72), (sx, 0, 0.5), r=0.24)
        # headlamps behind guards on the bow
        lx = sx * 0.88
        k.lathe("headlamp", [(-0.1, 0.0), (-0.08, 0.075), (0.0, 0.1), (0.03, 0.0)], "brass", segs=20,
                loc=(lx, 3.42, 1.42), rot=(-0.2, 0, 0), parent=root)
        k.cylinder("lamp_glass", 0.085, 0.01, (lx, 3.455, 1.428), "glass", segs=20, rot=(-math.pi / 2 - 0.2, 0, 0),
                   parent=root, bevel=False)
        for i in range(3):
            k.box("lamp_guard", (0.008, 0.012, 0.2), (lx - 0.05 + i * 0.05, 3.5, 1.43), "iron_black", parent=root,
                  bevel=False)
        k.torus("tow_hook", 0.07, 0.02, (sx * 0.55, 3.8, 1.02), "iron_black", rot=(0, math.pi / 2, 0),
                parent=root, segs=12, tube_segs=4)
    # trim vane folded on the glacis, driver's and commander's vision blocks
    k.box("trim_vane", (2.0, 0.05, 0.5), (0, 3.25, 1.52), WORN, rot=(-1.15, 0, 0), parent=root, bevel=0.008)
    for i in range(4):
        k.box("vane_rib", (0.04, 0.05, 0.48), (-0.75 + i * 0.5, 3.21, 1.55), WORN, rot=(-1.15, 0, 0),
              parent=root, bevel=False)
    for sx in (-1, 1):
        k.box("screen_hatch", (0.7, 0.04, 0.42), (sx * 0.45, 2.6, 1.86), WORN, rot=(-0.95, 0, 0), parent=root,
              bevel=0.006)
        for i in range(3):
            k.box("periscope", (0.14, 0.1, 0.08), (sx * (0.22 + i * 0.22), 2.28, 2.06), "brass", parent=root,
                  bevel=False)
            k.box("periscope_glass", (0.11, 0.012, 0.05), (sx * (0.22 + i * 0.22), 2.335, 2.065), "glass",
                  parent=root, bevel=False)


def _deck(k, root):
    """Roof: troop hatches, commander's and driver's round hatches, engine deck at the rear."""
    for x, y in ((-0.5, 1.95), (0.5, 1.95)):
        k.cylinder("crew_hatch", 0.3, 0.05, (x, y, 2.07), WORN, segs=24, parent=root, bevel=0.01)
        k.cylinder("hatch_hinge", 0.03, 0.2, (x, y - 0.28, 2.1), "brass", segs=10, rot=(0, math.pi / 2, 0),
                   parent=root, bevel=False)
        k.torus("hatch_handle", 0.05, 0.008, (x, y + 0.1, 2.11), "steel_worn", parent=root, segs=12, tube_segs=4)
    for x, y in ((-0.48, -0.75), (0.48, -0.75)):
        k.box("troop_hatch", (0.62, 0.75, 0.05), (x, y, 2.07), WORN, parent=root, bevel=0.01)
        k.cylinder("hatch_hinge", 0.025, 0.55, (x, y + 0.37, 2.1), "brass", segs=10, rot=(0, math.pi / 2, 0),
                   parent=root, bevel=False)
    # engine deck: louvred grilles, access plates with bolt heads
    for sx in (-1, 1):
        for i in range(9):
            k.box("engine_louvre", (0.55, 0.06, 0.03), (sx * 0.45, -2.25 - i * 0.14, 2.06), "iron_black",
                  rot=(0.5, 0, 0), parent=root, bevel=False)
    k.box("access_plate", (0.8, 0.6, 0.03), (0, -1.6, 2.06), WORN, parent=root, bevel=0.006)
    fx.rivets(k, root, (-0.36, -1.33, 2.08), (0.36, -1.33, 2.08), 6, (0, 0, 1), r=0.014)
    fx.rivets(k, root, (-0.36, -1.87, 2.08), (0.36, -1.87, 2.08), 6, (0, 0, 1), r=0.014)
    for sx in (-1, 1):
        fx.stack(k, root, (sx * 0.95, -3.45, 2.0), 0.6, r=0.07)
    fx.emblem(k, root, (0, 0.0, 2.06), (0, 0, 1), r=0.3)
    # oxblood identification band round the roof and the upper sides, behind the turret
    tilt = math.atan2(1.43 - 1.1, 2.02 - 1.36)
    for sx in (-1, 1):
        k.box("faction_band", (1.1, 0.32, 0.012), (sx * 0.55, 0.6, 2.037), fx.RED, rot=(0, sx * 0.018, 0),
              parent=root, bevel=False)
        k.box("faction_band", (0.012, 0.32, 0.74), (sx * (1.265 + 0.007), 0.6, 1.69 + 0.004), fx.RED,
              rot=(0, -sx * tilt, 0), parent=root, bevel=False)
    # canvas tarpaulin rolled and strapped across the rear deck, pennant on the right rear corner
    k.cylinder("tarp_roll", 0.15, 1.5, (0, -3.42, 2.19), "canvas", segs=20, rot=(0, math.pi / 2, 0),
               parent=root, bevel=0.03)
    for x in (-0.45, 0.45):
        k.torus("tarp_strap", 0.155, 0.012, (x, -3.42, 2.19), "leather", rot=(0, math.pi / 2, 0), parent=root,
                segs=16, tube_segs=4)
    fx.pennant(k, root, (1.0, -3.15, 2.04), h=1.5, w=0.5)
    k.tube("antenna", (-0.95, -3.0, 2.04), (-1.0, -3.15, 3.9), 0.007, "gunmetal", parent=root, segs=6, bevel=False)
    k.cylinder("antenna_base", 0.05, 0.1, (-0.95, -3.0, 2.08), "brass", segs=12, parent=root, bevel=False)


def _turret(k, root):
    t = k.empty("turret", (0, 1.05, 2.04), parent=root)
    k.lathe("turret_cone", [(0.0, 0.66), (0.08, 0.64), (0.34, 0.52), (0.44, 0.36), (0.47, 0.0)], G, segs=10,
            rot=(math.pi / 2, 0, 0), parent=t)
    k.cylinder("turret_band", 0.665, 0.06, (0, 0, 0.03), "paint_faction_red", segs=40, parent=t, bevel=False)
    k.cylinder("turret_ring", 0.7, 0.04, (0, 0, -0.01), "gunmetal", segs=40, parent=t, bevel=False)
    k.box("mantlet", (0.42, 0.2, 0.3), (0, 0.6, 0.24), G, parent=t, bevel=0.03)
    k.tube("hmg_barrel", (0.04, 0.68, 0.27), (0.04, 2.25, 0.3), 0.032, "gunmetal", parent=t, segs=14)
    k.tube("hmg_jacket", (0.04, 0.68, 0.27), (0.04, 1.35, 0.285), 0.055, "gunmetal", parent=t, segs=14)
    for i in range(5):
        k.torus("jacket_rib", 0.058, 0.007, (0.04, 0.78 + i * 0.12, 0.274 + i * 0.002), "brass",
                rot=(math.pi / 2, 0, 0), parent=t, segs=16, tube_segs=4)
    k.lathe("flash_hider", [(0.0, 0.035), (0.12, 0.045), (0.14, 0.03)], "iron_black", segs=14,
            loc=(0.04, 2.25, 0.3), parent=t)
    k.tube("coax", (-0.15, 0.68, 0.25), (-0.15, 1.3, 0.26), 0.016, "gunmetal", parent=t, segs=8)
    k.box("gunsight", (0.12, 0.2, 0.14), (-0.2, 0.32, 0.52), "brass", parent=t, bevel=0.01)
    k.box("sight_glass", (0.09, 0.012, 0.08), (-0.2, 0.425, 0.53), "glass", parent=t, bevel=False)
    k.cylinder("turret_hatch", 0.2, 0.04, (0.12, -0.1, 0.65), WORN, segs=20, parent=t, bevel=0.008)
    fx.band(k, t, (0.04, 1.9, 0.3), (0.04, 2.0, 0.3), (0.075, 0.075))


def _stowage(k, root):
    """Tools and kit on the hull: tow cable, shovel, axe, jerrycans, spare wheel."""
    for sx in (-1, 1):
        k.hose("tow_cable", [(sx * 1.43, 2.0, 1.44), (sx * 1.44, 0.5, 1.45), (sx * 1.44, -1.5, 1.45),
                             (sx * 1.43, -3.2, 1.44)], 0.022, "steel_worn", parent=root)
        k.box("stowage_box", (0.32, 0.8, 0.24), (sx * 1.3, -1.25, 1.48), G, parent=root, bevel=0.012)
        k.box("box_lid", (0.34, 0.82, 0.03), (sx * 1.3, -1.25, 1.61), WORN, parent=root, bevel=0.006)
    k.tube("shovel_haft", (1.12, 1.4, 1.52), (1.12, 0.3, 1.52), 0.018, "wood", parent=root, segs=8)
    k.box("shovel_blade", (0.03, 0.26, 0.2), (1.12, 0.17, 1.52), "steel_worn", parent=root, bevel=False)
    k.tube("axe_haft", (-1.12, 1.4, 1.52), (-1.12, 0.6, 1.52), 0.018, "wood", parent=root, segs=8)
    k.box("axe_head", (0.03, 0.08, 0.18), (-1.12, 1.42, 1.56), "iron_black", parent=root, bevel=False)
    for i, x in enumerate((-0.75, -0.4)):
        k.box("jerrycan", (0.16, 0.34, 0.46), (x, -3.92, 1.5), WORN if i else G, rot=(math.pi / 2, 0, 0),
              parent=root, bevel=0.02)
    k.box("can_rack", (0.6, 0.05, 0.05), (-0.58, -3.88, 1.3), "iron_black", parent=root, bevel=False)
    w = vehicle.lug_wheel(k, root, vehicle.Motion(1, 1.0), (0.6, -3.92, 1.45), R_WHEEL * 0.95, WHEEL_W * 0.9, WORN,
                          holes=HOLES)
    w.rotation_euler = (0, 0, math.pi / 2)
