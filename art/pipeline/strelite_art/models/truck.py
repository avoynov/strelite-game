"""Six-wheel army cargo truck of the Iron Concord (bg: „Камион“), built to the guns'
standard at real size: 6.7 m long, 2.4 m wide, 3.0 m to the top of the tilt.

The look is a 1930s-40s 6x6 (bonnet cab, rounded pressed-steel wings, tandem rear
axles under a canvas tilt) with the Concord's light steampunk: a brass radiator shell
and filler, a spark-arrester stack and steam whistle behind the cab, a brass ring
mount with a light machine gun on the cab roof, a winch on the front bumper.

What makes it unmistakable at game zoom: long bonnet and rounded wings in front, the
pale canvas tilt with the oxblood-and-black emblem on its roof, six big lugged tyres,
the ring mount over the cab.

Construction (real parts, real sizes): ladder frame of C-channel rails and five
crossmembers; beam front axle and two driven rear axles on leaf springs with U-bolts;
propshafts; 1.1 m military tyres with chevron lugs on eight-hole pressed discs; closed
steel cab with split windscreen, visor, doors with hinges and handles; planked
cargo bed with stake pockets, rub rails, tailboard on chains; tilt over five bows.

Movement: wheels roll (4 frames, the disc pattern repeats every 1/8 turn).
The vehicle faces local +Y; render_sprites.py --enemy turns the whole model.
Returns (root, root).
"""
import math

from .. import human as hu
from .. import materials_photoreal as mp
from ..geo import Kit
from . import faction as fx
from . import vehicle
from .vehicle import arc_yz

SPRITE_FRAME_M = 8.6
LENGTH_M = 6.7
RADIUS_M = 3.3
G, WORN = "paint_enemy", "paint_enemy_worn"
R_WHEEL, TRACK_X, TYRE_W = 0.55, 0.93, 0.36
Y_FRONT, Y_REAR = (2.25,), (-1.0, -2.3)
FRAME_Z = 1.02                       # top of the frame rails

HOLES = 8
MOVE_FRAMES = 4
MOVE_KIND = "wheels"
MOVE_CYCLE_M = 2 * math.pi * R_WHEEL / HOLES      # the wheel pattern repeats every 1/8 turn
_MOTION = vehicle.Motion(MOVE_FRAMES, MOVE_CYCLE_M)


def set_move_frame(f, scene=None):
    _MOTION.set(f)


def build(style, level=1):
    global _MOTION
    _MOTION = vehicle.Motion(MOVE_FRAMES, MOVE_CYCLE_M)
    k = Kit(style)
    root = k.empty("truck")
    mp.set_reference(root)
    _running_gear(k, root)
    _frame(k, root)
    _front(k, root)
    _cab(k, root)
    _bed(k, root)
    _extras(k, root)
    fx.emblem(k, root, (0, -1.4, 2.715), (0, 0, 1), r=0.55)
    for sx in (-1, 1):
        fx.emblem(k, root, (sx * 1.075, 1.28, 1.62), (sx, 0, 0), r=0.2)
    return root, root


# ---------------------------------------------------------------------------
def _running_gear(k, root):
    for y in Y_FRONT + Y_REAR:
        for sx in (-1, 1):
            vehicle.lug_wheel(k, root, _MOTION, (sx * TRACK_X, y, R_WHEEL), R_WHEEL, TYRE_W, WORN, holes=HOLES)
            # leaf spring pack, shackles and U-bolts
            for i in range(5):
                ln = 1.2 - 0.18 * i
                k.box("leaf", (0.075, ln, 0.02), (sx * 0.45, y, R_WHEEL + 0.17 - 0.022 * i), "steel_worn",
                      parent=root, bevel=False)
            for dy in (-0.07, 0.07):
                k.box("u_bolt", (0.11, 0.022, 0.24), (sx * 0.45, y + dy, R_WHEEL + 0.08), "iron_black",
                      parent=root, bevel=False)
            for dy in (-0.6, 0.6):
                k.box("shackle", (0.05, 0.05, 0.16), (sx * 0.45, y + dy, R_WHEEL + 0.25), "iron_black",
                      parent=root, bevel=False)
            k.cylinder("brake_drum", 0.3, 0.12, (sx * (TRACK_X - TYRE_W / 2 - 0.07), y, R_WHEEL), "iron_black",
                       segs=24, rot=(0, math.pi / 2, 0), parent=root, bevel=0.008)
        k.tube("axle", (-0.75, y, R_WHEEL), (0.75, y, R_WHEEL), 0.055, "gunmetal", parent=root, segs=12)
        if y in Y_REAR:
            k.lathe("diff", [(-0.17, 0.0), (-0.17, 0.11), (-0.02, 0.21), (0.14, 0.15), (0.2, 0.05), (0.2, 0.0)],
                    "gunmetal", segs=24, loc=(0, y, R_WHEEL), parent=root)
    k.tube("propshaft", (0, 1.7, 0.72), (0, -0.9, 0.62), 0.045, "gunmetal", parent=root, segs=10)
    k.tube("propshaft", (0, -1.1, 0.62), (0, -2.2, 0.62), 0.045, "gunmetal", parent=root, segs=10)
    k.box("gearbox", (0.36, 0.55, 0.32), (0, 1.75, 0.82), "gunmetal", parent=root, bevel=0.02)
    k.box("transfer_case", (0.42, 0.3, 0.3), (0, 1.3, 0.72), "gunmetal", parent=root, bevel=0.02)


def _frame(k, root):
    for sx in (-1, 1):                                # C-channel rails: web and two flanges
        k.box("rail_web", (0.012, 6.45, 0.22), (sx * 0.47, -0.05, FRAME_Z - 0.11), "gunmetal", parent=root,
              bevel=False)
        for dz in (0.0, -0.22):
            k.box("rail_flange", (0.08, 6.45, 0.012), (sx * 0.44, -0.05, FRAME_Z + dz), "gunmetal",
                  parent=root, bevel=False)
        fx.rivets(k, root, (sx * 0.478, 3.0, FRAME_Z - 0.06), (sx * 0.478, -3.1, FRAME_Z - 0.06), 24, (sx, 0, 0),
                  r=0.014)
    for y in (3.1, 1.95, 0.45, -1.65, -3.15):
        k.box("crossmember", (0.94, 0.09, 0.16), (0, y, FRAME_Z - 0.1), "gunmetal", parent=root, bevel=0.006)


def _front(k, root):
    # bumper with a winch between the dumb-irons, tow hooks
    k.box("bumper", (2.25, 0.16, 0.24), (0, 3.3, 0.8), WORN, parent=root, bevel=0.012)
    fx.rivets(k, root, (-1.05, 3.385, 0.86), (1.05, 3.385, 0.86), 12, (0, 1, 0), r=0.016)
    k.cylinder("winch_drum", 0.13, 0.5, (0, 3.22, 1.05), "iron_black", segs=20, rot=(0, math.pi / 2, 0),
               parent=root, bevel=0.01)
    for i in range(9):
        k.torus("winch_cable", 0.14, 0.012, (-0.2 + i * 0.05, 3.22, 1.05), "steel_worn",
                rot=(0, math.pi / 2, 0), parent=root, segs=16, tube_segs=4)
    for sx in (-1, 1):
        k.cylinder("winch_cheek", 0.17, 0.02, (sx * 0.27, 3.22, 1.05), "brass", segs=20, rot=(0, math.pi / 2, 0),
                   parent=root, bevel=0.004)
        k.torus("tow_hook", 0.075, 0.02, (sx * 0.72, 3.42, 0.76), "iron_black", rot=(0, math.pi / 2, 0),
                parent=root, segs=14, tube_segs=5)
    # radiator: brass shell, black vertical bars, filler cap, starting-handle hole
    rz0, rz1, rw = 1.05, 1.86, 0.8
    for x0, x1, z0, z1 in ((-rw / 2, rw / 2, rz1, rz1), (-rw / 2, rw / 2, rz0, rz0),
                           (-rw / 2, -rw / 2, rz0, rz1), (rw / 2, rw / 2, rz0, rz1)):
        k.beam("radiator_shell", (x0, 3.04, z0), (x1, 3.04, z1) if (x0, z0) != (x1, z1) else (x1, 3.04, z1 + 0.01),
               (0.07, 0.07), "brass", parent=root, bevel=0.012)
    k.box("radiator_core", (rw - 0.05, 0.08, rz1 - rz0 - 0.05), (0, 3.0, (rz0 + rz1) / 2), "iron_black",
          parent=root, bevel=False)
    for i in range(17):
        x = -rw / 2 + 0.05 + i * (rw - 0.1) / 16
        k.box("grille_bar", (0.016, 0.03, rz1 - rz0 - 0.06), (x, 3.06, (rz0 + rz1) / 2), WORN, parent=root,
              bevel=False)
    k.lathe("filler_cap", [(0.0, 0.05), (0.03, 0.05), (0.05, 0.04), (0.07, 0.0)], "brass", segs=16,
            loc=(0, 2.98, rz1 + 0.02), rot=(-math.pi / 2, 0, 0), parent=root)
    fx.emblem(k, root, (0, 3.085, rz1 - 0.12), (0, 1, 0), r=0.07)
    # bonnet: rounded hood in two halves on a centre hinge, louvres in the sides, clasps
    st = [dict(c=(0, y, 1.42), rx=0.44, ry=0.43, p=3.2) for y in (1.96, 2.4, 2.98)]
    hood = hu.loft(k, "bonnet", st, G, root, segs=28, caps=(False, False), subsurf=0)
    hood.modifiers.new("Solidify", "SOLIDIFY").thickness = 0.012
    for p in hood.data.polygons:
        p.use_smooth = True
    k.tube("bonnet_hinge", (0, 1.95, 1.855), (0, 3.0, 1.855), 0.012, "brass", parent=root, segs=8, bevel=False)
    for sx in (-1, 1):
        for i in range(7):
            k.box("louvre", (0.02, 0.07, 0.2), (sx * 0.442, 2.15 + i * 0.1, 1.42), "iron_black", rot=(0, 0, 0),
                  parent=root, bevel=False)
            k.box("louvre_lip", (0.025, 0.012, 0.21), (sx * 0.452, 2.18 + i * 0.1, 1.42), G,
                  rot=(0, 0, sx * 0.5), parent=root, bevel=False)
        k.box("bonnet_clasp", (0.03, 0.06, 0.05), (sx * 0.45, 2.45, 1.12), "steel_worn", parent=root, bevel=False)
    # front wings: from the bumper over the wheel and down onto the running board
    for sx in (-1, 1):
        path = [(3.22, 0.9), (3.1, 0.98)] + arc_yz(Y_FRONT[0], R_WHEEL, 0.71, 35, 140, 12) + \
            [(1.45, 0.92), (1.3, 0.9), (0.62, 0.9)]
        vehicle.sheet(k, "front_wing", path, sx * TRACK_X, 0.56, G, root, lip=0.05, outward=sx)
        # headlight on the wing: brass bowl, glass, guard, with a convoy lamp
        hx, hy, hz = sx * 0.78, 2.78, 1.42
        k.tube("lamp_stalk", (hx, hy, 1.24), (hx, hy, hz - 0.05), 0.02, "iron_black", parent=root, segs=8,
               bevel=False)
        k.lathe("headlamp", [(-0.12, 0.0), (-0.1, 0.09), (-0.02, 0.12), (0.02, 0.125), (0.03, 0.0)], "brass",
                segs=24, loc=(hx, hy, hz), parent=root)
        k.cylinder("lamp_glass", 0.105, 0.012, (hx, hy + 0.035, hz), "glass", segs=24, rot=(-math.pi / 2, 0, 0),
                   parent=root, bevel=False)
        for i in range(3):
            k.box("lamp_guard", (0.008, 0.012, 0.22), (hx - 0.06 + i * 0.06, hy + 0.06, hz), "iron_black",
                  parent=root, bevel=False)
        k.cylinder("convoy_lamp", 0.035, 0.05, (sx * 0.55, 3.08, 1.08), "paint_faction_red", segs=12,
                   rot=(-math.pi / 2, 0, 0), parent=root, bevel=False)
        k.box("running_board", (0.36, 0.72, 0.03), (sx * 0.98, 0.98, 0.88), "iron_black", parent=root,
              bevel=False)
        for i in range(6):
            k.box("tread_strip", (0.32, 0.02, 0.012), (sx * 0.98, 0.7 + i * 0.11, 0.9), "steel_worn",
                  parent=root, bevel=False)


def _cab(k, root):
    """Closed steel cab: rounded corners, split windscreen under a visor, doors with
    hinges and handles, rear window, ring mount on the roof."""
    y0, y1, z0, z1, hw = 0.68, 1.95, 1.02, 2.42, 1.04
    prof = [(y0, z0), (y1, z0), (y1, 1.86), (y1 - 0.14, z1 - 0.02), (y0 + 0.04, z1)]
    k.plate("cab_shell", prof, 2 * hw, 0.0, G, parent=root, bevel=0.06)
    k.box("roof_gutter", (2 * hw + 0.03, y1 - y0 - 0.1, 0.025), (0, (y0 + y1) / 2 - 0.04, z1 - 0.06), WORN,
          parent=root, bevel=False)
    # windscreen: two panes in frames, tipped back with the cab front
    tilt = math.atan2(0.14, z1 - 1.86)
    for sx in (-1, 1):
        cx, cy, cz = sx * 0.47, y1 - 0.07 + 0.006, 2.13
        k.box("windscreen", (0.82, 0.012, 0.44), (cx, cy + 0.006, cz), "glass", rot=(tilt, 0, 0), parent=root,
              bevel=False)
        for dz in (-0.235, 0.235):
            k.box("screen_frame", (0.86, 0.03, 0.03), (cx, cy + 0.02, cz + dz), "iron_black", rot=(tilt, 0, 0),
                  parent=root, bevel=False)
        for dx in (-0.425, 0.425):
            k.box("screen_frame", (0.03, 0.03, 0.5), (cx + dx, cy + 0.02, cz), "iron_black", rot=(tilt, 0, 0),
                  parent=root, bevel=False)
        k.tube("wiper", (cx - 0.1, cy + 0.035, 1.93), (cx + 0.2, cy + 0.0, 2.25), 0.006, "iron_black",
               parent=root, segs=6, bevel=False)
        # door: seams, hinges, handle, window with frame
        x = sx * (hw + 0.004)
        for (ya, za, yb, zb) in ((0.82, 1.06, 0.82, 2.2), (1.72, 1.06, 1.72, 2.2), (0.82, 1.06, 1.72, 1.06)):
            k.box("door_seam", (0.006, max(abs(yb - ya), 0.008), max(abs(zb - za), 0.008)),
                  (x, (ya + yb) / 2, (za + zb) / 2), "iron_black", parent=root, bevel=False)
        for z in (1.3, 1.95):
            k.cylinder("hinge", 0.02, 0.1, (x, 1.7, z), "steel_worn", segs=8, parent=root, bevel=False)
        k.box("door_handle", (0.03, 0.13, 0.03), (x + sx * 0.02, 0.95, 1.68), "brass", parent=root, bevel=False)
        k.box("side_window", (0.014, 0.66, 0.4), (x, 1.25, 2.04), "glass", parent=root, bevel=False)
        for dz in (-0.21, 0.21):
            k.box("window_frame", (0.02, 0.7, 0.025), (x + sx * 0.004, 1.25, 2.04 + dz), "iron_black",
                  parent=root, bevel=False)
        for dy in (-0.345, 0.345):
            k.box("window_frame", (0.02, 0.025, 0.44), (x + sx * 0.004, 1.25 + dy, 2.04), "iron_black",
                  parent=root, bevel=False)
        k.box("mirror", (0.035, 0.18, 0.24), (sx * 1.27, 1.9, 2.02), "gunmetal", parent=root, bevel=0.01)
        k.tube("mirror_arm", (sx * 1.04, 1.86, 1.95), (sx * 1.25, 1.9, 2.0), 0.012, "iron_black", parent=root,
               segs=6, bevel=False)
    k.box("visor", (2.0, 0.22, 0.025), (0, y1 + 0.02, z1 - 0.05), G, rot=(-0.2, 0, 0), parent=root, bevel=0.006)
    k.box("rear_window", (0.8, 0.012, 0.3), (0, y0 - 0.002, 2.05), "glass", parent=root, bevel=False)
    # steering wheel seen through the screen
    k.torus("steering_wheel", 0.2, 0.014, (0.45, 1.62, 1.82), "iron_black", rot=(1.0, 0, 0), parent=root,
            segs=24, tube_segs=5)
    # brass ring mount with a light machine gun on the roof
    rz = z1 + 0.18
    k.torus("ring_mount", 0.42, 0.028, (0.25, 1.25, rz), "brass", parent=root, segs=40, tube_segs=6)
    for a in (40, 140, 220, 320):
        ar = math.radians(a)
        k.tube("ring_post", (0.25 + 0.42 * math.cos(ar), 1.25 + 0.42 * math.sin(ar), z1 - 0.01),
               (0.25 + 0.42 * math.cos(ar), 1.25 + 0.42 * math.sin(ar), rz), 0.018, "iron_black", parent=root,
               segs=8, bevel=False)
    k.box("mg_carriage", (0.1, 0.16, 0.08), (0.25, 1.67, rz + 0.05), "iron_black", parent=root, bevel=0.01)
    k.box("mg_receiver", (0.09, 0.42, 0.12), (0.25, 1.78, rz + 0.15), "gunmetal", parent=root, bevel=0.01)
    k.tube("mg_jacket", (0.25, 1.98, rz + 0.16), (0.25, 2.55, rz + 0.12), 0.034, "gunmetal", parent=root, segs=14)
    for i in range(6):
        k.torus("jacket_rib", 0.036, 0.006, (0.25, 2.02 + i * 0.09, rz + 0.157 - i * 0.004), "brass",
                rot=(math.pi / 2 - 0.07, 0, 0), parent=root, segs=14, tube_segs=4)
    k.tube("mg_muzzle", (0.25, 2.55, rz + 0.12), (0.25, 2.66, rz + 0.115), 0.016, "iron_black", parent=root,
           segs=10, bevel=False)
    k.box("ammo_box", (0.14, 0.25, 0.18), (0.4, 1.78, rz + 0.12), G, parent=root, bevel=0.01)
    k.box("mg_grips", (0.04, 0.08, 0.12), (0.25, 1.55, rz + 0.12), "wood", parent=root, bevel=0.01)


def _bed(k, root):
    y0, y1, floor, hw = -3.35, 0.5, FRAME_Z + 0.16, 1.18
    k.box("bed_bearer", (0.12, y1 - y0, 0.1), (-0.45, (y0 + y1) / 2, FRAME_Z + 0.05), "wood", parent=root,
          bevel=False)
    k.box("bed_bearer", (0.12, y1 - y0, 0.1), (0.45, (y0 + y1) / 2, FRAME_Z + 0.05), "wood", parent=root,
          bevel=False)
    for i in range(9):                                # floor planks across the bed
        x = -hw + 0.13 + i * (2 * hw - 0.26) / 8
        k.box("floor_plank", (0.25, y1 - y0, 0.05), (x, (y0 + y1) / 2, floor - 0.025), "wood", parent=root,
              bevel=0.004)
    for sx in (-1, 1):
        for j in range(3):                            # side boards: three planks with gaps
            k.box("side_plank", (0.045, y1 - y0, 0.15), (sx * hw, (y0 + y1) / 2, floor + 0.09 + j * 0.165),
                  "wood", parent=root, bevel=0.006)
        k.box("rub_rail", (0.06, y1 - y0 + 0.04, 0.05), (sx * (hw + 0.03), (y0 + y1) / 2, floor + 0.02), WORN,
              parent=root, bevel=0.006)
        for i in range(6):                            # stake pockets and stakes
            y = y0 + 0.15 + i * (y1 - y0 - 0.3) / 5
            k.box("stake", (0.06, 0.07, 0.55), (sx * (hw + 0.045), y, floor + 0.25), "iron_black", parent=root,
                  bevel=0.004)
        # rear mudguard over the tandem: one curved sheet
        path = arc_yz(Y_REAR[0], R_WHEEL, 0.68, 20, 90, 5)[:-1] + [(Y_REAR[0], 1.23), (Y_REAR[1], 1.23)] + \
            arc_yz(Y_REAR[1], R_WHEEL, 0.68, 90, 160, 5)[1:]
        vehicle.sheet(k, "rear_wing", path, sx * TRACK_X, 0.46, WORN, root, lip=0.03, outward=sx)
    for j in range(3):
        k.box("tailboard", (2 * hw, 0.045, 0.15), (0, y0 - 0.02, floor + 0.09 + j * 0.165), "wood", parent=root,
              bevel=0.006)
        k.box("front_board", (2 * hw, 0.045, 0.15), (0, y1, floor + 0.09 + j * 0.165), "wood", parent=root,
              bevel=0.006)
    for sx in (-1, 1):
        k.box("tail_strap", (0.06, 0.05, 0.5), (sx * 0.8, y0 - 0.05, floor + 0.25), "iron_black", parent=root,
              bevel=False)
        k.hose("tail_chain", [(sx * 1.15, y0 - 0.02, floor + 0.48), (sx * 1.1, y0 - 0.08, floor + 0.3),
                              (sx * 1.0, y0 - 0.05, floor + 0.45)], 0.01, "steel_worn", parent=root)
        k.box("tail_light", (0.12, 0.05, 0.09), (sx * 0.95, y0 - 0.08, FRAME_Z - 0.05), "paint_faction_red",
              parent=root, bevel=0.01)
    _tilt(k, root, y0 + 0.02, y1 + 0.02, floor + 0.52, hw + 0.02, 1.0)
    # cargo seen through the open rear: ammunition crates, sacks, a fuel drum
    for i, (x, y, z, sz, rz) in enumerate(((-0.6, -3.0, 0, (0.7, 0.45, 0.4), 0.05), (0.15, -3.05, 0, (0.7, 0.45, 0.4), -0.04),
                                           (-0.25, -2.95, 0.4, (0.7, 0.45, 0.35), 0.12), (0.8, -2.6, 0, (0.5, 0.6, 0.45), 0.3))):
        k.box("cargo_crate", sz, (x, y, floor + z + sz[2] / 2), "wood" if i % 2 else "timber_tarred", rot=(0, 0, rz),
              parent=root, bevel=0.01)
        k.box("crate_band", (sz[0] + 0.01, 0.03, sz[2] + 0.01), (x, y, floor + z + sz[2] / 2), "iron_black",
              rot=(0, 0, rz), parent=root, bevel=False)
    k.cylinder("fuel_drum", 0.29, 0.88, (-0.75, -2.35, floor + 0.44), G, segs=24, parent=root, bevel=0.02)
    for dz in (-0.25, 0.25):
        k.torus("drum_rib", 0.292, 0.01, (-0.75, -2.35, floor + 0.44 + dz), WORN, parent=root, segs=24, tube_segs=4)


def _tilt(k, root, y0, y1, z_eave, half_w, rise):
    """Canvas tilt over five bows: straight sides, rounded roof sagging between the bows,
    rear flap rolled up, lashing ropes along the bottom edge."""
    nu, nv, bows = 20, 32, 5
    verts, faces = [], []
    prof = []
    for i in range(nu + 1):
        t = i / nu
        if t < 0.16:
            prof.append((-half_w, z_eave - 0.5 + 0.5 * t / 0.16))
        elif t > 0.84:
            prof.append((half_w, z_eave - 0.5 * (t - 0.84) / 0.16))
        else:
            a = math.pi * (1 - (t - 0.16) / 0.68)
            prof.append((half_w * math.cos(a), z_eave + rise * math.sin(a) ** 0.7))
    for j in range(nv + 1):
        y = y0 + (y1 - y0) * j / nv
        sag = 0.04 * abs(math.sin(math.pi * (bows - 1) * j / nv))
        for (x, z) in prof:
            inward = 1.0 if z > z_eave else 0.25
            verts.append((x * (1 - sag * 0.25 * inward), y, z - sag * inward))
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            faces.append((a, a + 1, a + nu + 2, a + nu + 1))
    ring = [nv * (nu + 1) + i for i in range(nu + 1)]          # front end closed
    verts.append((0, y1, z_eave - 0.5))
    c = len(verts) - 1
    for i in range(nu):
        faces.append((c, ring[i], ring[i + 1]))
    obj = k.mesh("tilt", verts, faces)
    k._finish(obj, "canvas", bevel=False, parent=root)
    obj.modifiers.new("Solidify", "SOLIDIFY").thickness = 0.01
    for p in obj.data.polygons:
        p.use_smooth = True
    # bows showing at the open rear and the rolled flap above it
    pts = [(x, y0 + 0.05, z) for x, z in prof]
    k.hose("bow", pts, 0.022, "wood", parent=root)
    k.cylinder("rolled_flap", 0.09, 2 * half_w * 0.62, (0, y0 - 0.04, z_eave + rise - 0.12), "canvas", segs=16,
               rot=(0, math.pi / 2, 0), parent=root, bevel=0.03)
    for sx in (-1, 1):
        k.torus("flap_strap", 0.095, 0.008, (sx * 0.4, y0 - 0.04, z_eave + rise - 0.12), "leather",
                rot=(0, math.pi / 2, 0), parent=root, segs=14, tube_segs=4)
        k.tube("rope", (sx * (half_w + 0.012), y0, z_eave - 0.42), (sx * (half_w + 0.012), y1, z_eave - 0.42),
               0.012, "rope", parent=root, segs=6, bevel=False)
        for i in range(8):
            y = y0 + 0.2 + i * (y1 - y0 - 0.4) / 7
            k.torus("rope_tie", 0.035, 0.008, (sx * (half_w + 0.02), y, z_eave - 0.47), "rope",
                    rot=(0, math.pi / 2, 0), parent=root, segs=10, tube_segs=4)


def _extras(k, root):
    """Kit a real front-line truck carries: spare wheel, fuel tank, battery box, jerrycans,
    tools; the Concord's spark-arrester stack and steam whistle."""
    w = vehicle.lug_wheel(k, root, vehicle.Motion(1, 1.0), (1.02, 0.12, 0.78), R_WHEEL * 0.97, TYRE_W * 0.95, WORN,
                          holes=HOLES)
    w.rotation_euler = (0, 0, 0)
    k.box("spare_carrier", (0.08, 0.5, 0.08), (0.8, 0.12, 0.78), "iron_black", parent=root, bevel=False)
    k.cylinder("fuel_tank", 0.21, 0.7, (-0.92, 1.0, 0.68), G, segs=24, rot=(math.pi / 2, 0, 0), parent=root,
               bevel=0.02)
    for dy in (-0.22, 0.22):
        k.torus("tank_strap", 0.215, 0.01, (-0.92, 1.0 + dy, 0.68), "iron_black", rot=(math.pi / 2, 0, 0),
                parent=root, segs=24, tube_segs=4)
    k.lathe("tank_cap", [(0.0, 0.035), (0.03, 0.035), (0.04, 0.0)], "brass", segs=12, loc=(-0.92, 1.0, 0.9),
            rot=(-math.pi / 2, 0, 0), parent=root)
    k.box("battery_box", (0.4, 0.5, 0.3), (-0.95, -0.2, 0.8), WORN, parent=root, bevel=0.015)
    for i, y in enumerate((-0.45, -0.85, -1.25)):        # jerrycans in a rack on the right side of the bed
        k.box("jerrycan", (0.16, 0.34, 0.46), (1.32, y - 1.0, 1.42), WORN if i % 2 else G, parent=root, bevel=0.02)
        k.box("can_handle", (0.17, 0.1, 0.04), (1.32, y - 1.0, 1.67), "steel_worn", parent=root, bevel=False)
    k.box("can_rack", (0.05, 1.4, 0.05), (1.4, -1.85, 1.3), "iron_black", parent=root, bevel=False)
    k.tube("pick_haft", (-1.27, -2.9, 1.5), (-1.27, -1.7, 1.5), 0.02, "wood", parent=root, segs=8)
    k.box("pick_head", (0.05, 0.05, 0.5), (-1.27, -2.85, 1.5), "iron_black", parent=root, bevel=False)
    k.tube("shovel_haft", (-1.27, -1.5, 1.42), (-1.27, -0.4, 1.42), 0.02, "wood", parent=root, segs=8)
    k.box("shovel_blade", (0.03, 0.28, 0.22), (-1.27, -0.3, 1.42), "steel_worn", parent=root, bevel=False)
    fx.stack(k, root, (0.85, 0.6, FRAME_Z), 1.85, r=0.065)
    k.lathe("steam_whistle", [(0, 0.0), (0, 0.04), (0.18, 0.035), (0.2, 0.05), (0.26, 0.0)], "brass", segs=14,
            loc=(0.85, 0.6, 2.95), rot=(math.pi / 2, 0, 0), parent=root)
    fx.gauge(k, root, (-0.55, 3.1, 1.78), (0, 1, 0.3), r=0.05)
