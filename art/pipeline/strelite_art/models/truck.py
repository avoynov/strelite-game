"""Three-axle army cargo truck, generic type (bg: „Камион“). PLACEHOLDER enemy for
style В, built at real size: 6.6 m long, 2.4 m wide, bonnet cab, cargo bed under a
canvas tilt, dark grey paint.

The vehicle faces local +Y; render_sprites.py --enemy turns the whole model.
Returns (root, root).
"""
import math

from .. import materials_photoreal as mp
from ..geo import Kit
from . import vehicle

SPRITE_FRAME_M = 8.6
LENGTH_M = 6.6
RADIUS_M = 3.3
G, WORN = "paint_enemy", "paint_enemy_worn"
R_WHEEL, TRACK_X = 0.55, 0.92


def build(style, level=1):
    k = Kit(style)
    root = k.empty("truck")
    mp.set_reference(root)
    for y in (2.15, -1.05, -2.35):
        for sx in (-1, 1):
            vehicle.tyre_wheel(k, root, (sx * TRACK_X, y, R_WHEEL), R_WHEEL, 0.36, WORN)
        k.tube("axle", (-0.8, y, R_WHEEL), (0.8, y, R_WHEEL), 0.06, "gunmetal", parent=root, segs=12)
    _chassis(k, root)
    _cab(k, root)
    _bed(k, root)
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
    k.box("grille", (1.0, 0.03, 0.55), (0, 3.16, 1.3), "gunmetal", parent=root, bevel=False)
    for i in range(7):
        k.box("grille_bar", (0.9, 0.035, 0.03), (0, 3.18, 1.08 + i * 0.07), WORN, parent=root, bevel=False)
    for sx in (-1, 1):
        # front wings over the wheels and headlights on them
        k.plate("wing", [(1.55, 1.12), (2.85, 1.12), (2.95, 1.25), (2.6, 1.42), (1.75, 1.42)], 0.46,
                sx * 0.88, G, parent=root, bevel=0.012)
        k.cylinder("headlight", 0.1, 0.12, (sx * 0.86, 2.8, 1.52), G, segs=16, rot=(-math.pi / 2, 0, 0),
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
    k.tube("exhaust", (0.98, 0.7, 1.3), (0.98, 0.7, 2.8), 0.05, "steel_worn", parent=root, segs=12)


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
