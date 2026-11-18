"""Three-axle army cargo truck, generic type (bg: „Камион“). PLACEHOLDER enemy for
style В, built at real size: 6.6 m long, 2.4 m wide, bonnet cab, cargo bed under a
canvas tilt, dark grey paint.

The vehicle faces local +Y; render_sprites.py --enemy turns the whole model.
Returns (root, root).
"""
import math

from .. import materials_photoreal as mp
from ..geo import Kit
from . import faction as fx
from . import vehicle

SPRITE_FRAME_M = 8.6
LENGTH_M = 6.6
RADIUS_M = 3.3
G, WORN = "paint_enemy", "paint_enemy_worn"
R_WHEEL, TRACK_X = 0.55, 0.92


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
    for y in (2.15, -1.05, -2.35):
        for sx in (-1, 1):
            vehicle.lug_wheel(k, root, _MOTION, (sx * TRACK_X, y, R_WHEEL), R_WHEEL, 0.36, WORN, holes=HOLES)
        k.tube("axle", (-0.8, y, R_WHEEL), (0.8, y, R_WHEEL), 0.06, "gunmetal", parent=root, segs=12)
        k.lathe("diff", [(-0.2, 0.0), (-0.2, 0.12), (0.0, 0.2), (0.2, 0.12), (0.2, 0.0)], "gunmetal", segs=20,
                loc=(0, y, R_WHEEL), parent=root)
        for sx in (-1, 1):                                  # leaf spring pack and U-bolts
            for i in range(4):
                ln = 1.1 - 0.18 * i
                k.box("leaf", (0.07, ln, 0.022), (sx * 0.48, y, R_WHEEL + 0.1 + 0.024 * i), "steel_worn",
                      rot=(0, 0, 0), parent=root, bevel=False)
            for dy in (-0.07, 0.07):
                k.box("u_bolt", (0.1, 0.02, 0.2), (sx * 0.48, y + dy, R_WHEEL + 0.06), "iron_black", parent=root,
                      bevel=False)
    k.tube("propshaft", (0, 2.0, R_WHEEL + 0.1), (0, -1.05, R_WHEEL + 0.05), 0.045, "gunmetal", parent=root, segs=10)
    k.tube("propshaft", (0, -1.05, R_WHEEL + 0.05), (0, -2.35, R_WHEEL + 0.05), 0.045, "gunmetal", parent=root, segs=10)
    _chassis(k, root)
    _extras(k, root)
    _cab(k, root)
    _bed(k, root)
    # parallel-world faction marks: emblem on the tilt roof and doors, brass fittings
    fx.emblem(k, root, (0, -1.35, 3.12), (0, 0, 1), r=0.55)
    for sx in (-1, 1):
        fx.emblem(k, root, (sx * 1.09, 1.35, 1.55), (sx, 0, 0), r=0.22)
        fx.band(k, root, (sx * 1.11, 0.78, 1.4), (sx * 1.11, 1.95, 1.4), (0.02, 0.1))
    fx.gauge(k, root, (0.6, 3.17, 1.65), (0, 1, 0.2), r=0.06)
    return root, root


def _chassis(k, root):
    for sx in (-1, 1):
        k.box("frame_rail", (0.12, 6.2, 0.24), (sx * 0.48, -0.15, 0.92), "gunmetal", parent=root)
        k.box("fuel_tank", (0.42, 0.9, 0.42), (sx * 0.88, 0.25, 0.86), G, parent=root, bevel=0.03)
        # mudguards over the rear tandem
        k.box("mudguard", (0.44, 2.3, 0.03), (sx * TRACK_X, -1.7, 1.22), WORN, parent=root, bevel=False)
    k.box("bumper", (2.3, 0.16, 0.22), (0, 3.22, 0.78), WORN, parent=root, bevel=0.01)
    k.box("spare_carrier", (0.3, 0.6, 0.6), (-0.6, 0.62, 0.95), "gunmetal", parent=root)


def _cab(k, root):
    # bonnet: engine cover with a grille in front
    k.plate("bonnet", [(1.95, 1.0), (3.15, 1.0), (3.15, 1.62), (2.95, 1.72), (1.95, 1.75)], 1.24, 0.0,
            G, parent=root, bevel=0.02)
    k.box("grille", (1.0, 0.03, 0.55), (0, 3.16, 1.3), "brass", parent=root, bevel=False)
    for i in range(7):
        k.box("grille_bar", (0.9, 0.035, 0.03), (0, 3.18, 1.08 + i * 0.07), WORN, parent=root, bevel=False)
    for sx in (-1, 1):
        # front wings over the wheels and headlights on them
        k.plate("wing", [(1.55, 1.12), (2.85, 1.12), (2.95, 1.25), (2.6, 1.42), (1.75, 1.42)], 0.46,
                sx * 0.88, G, parent=root, bevel=0.012)
        k.cylinder("headlight", 0.1, 0.12, (sx * 0.86, 2.8, 1.52), "brass", segs=16, rot=(-math.pi / 2, 0, 0),
                   parent=root)
        k.cylinder("lens", 0.085, 0.01, (sx * 0.86, 2.925, 1.52), "glass", segs=16,
                   rot=(-math.pi / 2, 0, 0), parent=root, bevel=False)
        k.box("mirror", (0.04, 0.2, 0.28), (sx * 1.25, 1.9, 2.05), "gunmetal", parent=root, bevel=False)
        k.tube("mirror_arm", (sx * 1.05, 1.85, 2.0), (sx * 1.24, 1.9, 2.05), 0.012, "gunmetal",
               parent=root, segs=6, bevel=False)
        k.box("step", (0.36, 0.5, 0.04), (sx * 1.0, 1.25, 0.82), WORN, parent=root, bevel=False)
    # cab: closed steel box, windscreen in two panes, side windows
    k.plate("cab", [(0.75, 1.0), (1.95, 1.0), (1.95, 1.75), (1.82, 2.48), (0.78, 2.5)], 2.15, 0.0, G,
            parent=root, bevel=0.025)
    for sx in (-1, 1):
        g = k.box("windscreen", (0.86, 0.02, 0.56), (sx * 0.48, 1.9, 2.1), "glass", rot=(-0.18, 0, 0),
                  parent=root, bevel=False)
        g.location.y += 0.01
        k.box("side_window", (0.02, 0.6, 0.42), (sx * 1.08, 1.35, 2.12), "glass", parent=root, bevel=False)
        k.box("door_handle", (0.03, 0.12, 0.03), (sx * 1.085, 1.0, 1.72), "steel_worn", parent=root,
              bevel=False)
    k.box("roof_hatch", (0.6, 0.6, 0.04), (0.3, 1.25, 2.52), WORN, parent=root, bevel=0.01)
    fx.stack(k, root, (0.98, 0.7, 1.3), 1.5, r=0.06)


def _bed(k, root):
    y0, y1, floor = -3.3, 0.6, 1.3
    k.box("bed_floor", (2.4, y1 - y0, 0.1), (0, (y0 + y1) / 2, floor - 0.05), "wood", parent=root,
          bevel=0.006)
    for sx in (-1, 1):
        k.box("bed_side", (0.05, y1 - y0, 0.55), (sx * 1.18, (y0 + y1) / 2, floor + 0.27), "wood",
              parent=root, bevel=0.008)
        for i in range(5):
            y = y0 + 0.1 + i * (y1 - y0 - 0.2) / 4
            k.box("stake", (0.07, 0.07, 0.6), (sx * 1.215, y, floor + 0.27), G, parent=root, bevel=False)
    k.box("tailboard", (2.4, 0.05, 0.55), (0, y0 - 0.02, floor + 0.27), "wood", parent=root, bevel=0.008)
    k.box("front_board", (2.4, 0.05, 0.55), (0, y1, floor + 0.27), "wood", parent=root, bevel=0.008)
    _tilt(k, root, y0, y1 + 0.02, floor + 0.55, 1.22, 1.25)


def _tilt(k, root, y0, y1, z_eave, half_w, rise):
    """Canvas tilt over the bed: straight sides, rounded roof, sagging a little between the hoops."""
    nu, nv = 18, 24
    verts, faces = [], []
    prof = []
    for i in range(nu + 1):
        t = i / nu
        if t < 0.18:                                       # left side wall
            prof.append((-half_w, z_eave - 0.55 + 0.55 * t / 0.18))
        elif t > 0.82:
            prof.append((half_w, z_eave - 0.55 * (t - 0.82) / 0.18))
        else:
            a = math.pi * (1 - (t - 0.18) / 0.64)
            prof.append((half_w * math.cos(a), z_eave + rise * math.sin(a) ** 0.8))
    for j in range(nv + 1):
        y = y0 + (y1 - y0) * j / nv
        sag = 0.035 * abs(math.sin(math.pi * 4 * j / nv))  # cloth hangs between four hoops
        for (x, z) in prof:
            inward = 1.0 if z > z_eave else 0.3
            verts.append((x * (1 - sag * 0.3 * inward), y, z - sag * inward))
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            faces.append((a, a + 1, a + nu + 2, a + nu + 1))
    # end panels (front closed, rear rolled half way)
    for end, yy in ((0, y0), (nv, y1)):
        ring = [end * (nu + 1) + i for i in range(nu + 1)]
        verts.append((0, yy, z_eave - 0.55))
        c = len(verts) - 1
        for i in range(nu):
            faces.append((c, ring[i + 1], ring[i]) if end == 0 else (c, ring[i], ring[i + 1]))
    obj = k.mesh("tilt", verts, faces)
    k._finish(obj, "canvas", bevel=False, parent=root)
    for sx in (-1, 1):                                     # lashing ropes along the bottom edge
        k.tube("rope", (sx * (half_w + 0.01), y0, z_eave - 0.45), (sx * (half_w + 0.01), y1, z_eave - 0.45),
               0.012, "rope", parent=root, segs=6, bevel=False)


def _extras(k, root):
    """Kit a real front-line truck carries: spare wheel, jerrycans, tools, lights, hooks."""
    for i, y in enumerate((-0.4, -0.9, -1.4)):              # jerrycans in a rack on the bed side
        k.box("jerrycan", (0.16, 0.36, 0.48), (1.32, y, 1.55), WORN if i % 2 else G, parent=root, bevel=0.02)
        k.box("can_handle", (0.17, 0.12, 0.04), (1.32, y, 1.81), "steel_worn", parent=root, bevel=False)
    k.box("can_rack", (0.05, 1.5, 0.05), (1.4, -0.9, 1.42), "iron_black", parent=root, bevel=False)
    k.box("toolbox", (0.5, 0.9, 0.35), (-0.95, -0.4, 0.85), "paint_enemy_worn", parent=root, bevel=0.015)
    k.tube("pick_haft", (-1.3, -2.8, 1.45), (-1.3, -1.6, 1.45), 0.02, "wood", parent=root, segs=8)
    k.box("pick_head", (0.05, 0.05, 0.5), (-1.3, -2.75, 1.45), "iron_black", parent=root, bevel=False)
    k.tube("shovel_haft", (-1.3, -1.4, 1.38), (-1.3, -0.2, 1.38), 0.02, "wood", parent=root, segs=8)
    k.box("shovel_blade", (0.03, 0.28, 0.22), (-1.3, -0.1, 1.38), "steel_worn", parent=root, bevel=False)
    for sx in (-1, 1):
        k.box("tail_light", (0.12, 0.05, 0.08), (sx * 0.95, -3.37, 1.05), "paint_faction_red", parent=root,
              bevel=False)
        k.torus("tow_hook", 0.07, 0.018, (sx * 0.6, 3.32, 0.72), "iron_black", rot=(0, math.pi / 2, 0),
                parent=root, segs=12, tube_segs=4)
    k.lathe("steam_whistle", [(0, 0.0), (0, 0.04), (0.18, 0.035), (0.2, 0.05), (0.26, 0.0)], "brass", segs=14,
            loc=(0.98, 0.7, 2.85), rot=(math.pi / 2, 0, 0), parent=root)
