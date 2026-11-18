"""Headquarters of the player's base (bg: „Щаб“), 2 x 2 tiles (8 x 8 m), 5 levels.

The defenders' command post grows from a field blockhouse into a citadel. The
silhouette stays: a rectangular house with the blue defender flag on a mast at
its front-left corner. Each level changes the building's own material and adds
one new kind of signalling mechanism that explains the wider command reach
(the HQ level widens the build zone in the game):

  L1  log blockhouse, plank roof; signal bell on a post             (raw timber)
  L2  tarred plank walls on a rubble plinth, shingle roof, shutters;
      field telephone pole with porcelain insulators and a wire drum (tarred timber, iron)
  L3  two-storey rubble-stone keep, slate roof, chimney;
      optical semaphore mast with two arms on the ridge               (stone, slate)
  L4  dressed-stone bastion, crenellated parapet, riveted black iron corners;
      armoured observation cupola with a brass rangefinder            (ashlar, black iron)
  L5  pale stone citadel, black steel cornice with gold trim, copper dome;
      wireless mast with brass coils and glowing discharge globes     (pale stone, gold)

A supply pile by the door grows with the level (crates and barrels).
Front faces: -Y (screen lower left, the door) and +X (screen lower right).
Static object: one frame per level (render_buildings.py).
"""
import math

from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit
from . import building as bd
from . import defender

LEVELS = (1, 2, 3, 4, 5)
TILES = 2
FOOTPRINT_M = 4.0                  # half the side of the 2 x 2 tile square
SPRITE_WH_M = (15.0, 19.0)         # metres across, metres tall in the game render
ANCHOR_FROM_BOTTOM_M = 4.6         # ground point of the tile centre above the frame bottom
NAMES = {"bg": "Щаб", "en": "Headquarters"}


def build(style, level=1):
    k = Kit(style)
    root = k.empty("hq")
    mp.set_reference(root)
    rnd = bd.rnd_for(400 + level)
    {1: _l1, 2: _l2, 3: _l3, 4: _l4, 5: _l5}[level](k, root, rnd)
    return root, root


def ground(level):
    from ..terrain import Patch
    return Patch(r_solid=4.3, r_out=5.2, r_bare=4.0, seed=31 + level, ragged=0.5)


def _supplies(k, root, level, rnd):
    """Supply pile beside the door, toward the camera (more and better with the level)."""
    base = Vector((-1.9, -3.2, 0))
    crate_mat = {1: "timber_raw", 2: "paint_crate", 3: "paint_crate", 4: "paint_olive", 5: "paint_olive"}[level]
    spots = [(0, 0, 0.0), (0.75, 0.05, 0.2), (0.35, 0.0, 0.0)]
    for i, (dx, dy, yaw) in enumerate(spots[:1 + (level + 1) // 2]):
        z = 0.25 if i < 2 else 0.75
        bd.crate(k, root, base + Vector((dx, dy + (0.05 if i == 2 else 0), z)), (0.7, 0.5, 0.5), yaw + 0.1 * i,
                 mat=crate_mat)
    for i in range(min(level, 3)):
        bd.barrel(k, root, base + Vector((-0.75 - 0.0 * i, 0.55 * i - 0.1, 0)), r=0.27,
                  mat="timber_oak" if level >= 3 else "timber_raw")


# ---------------------------------------------------------------------------
def _l1(k, root, rnd):
    x0, x1, y0, y1 = -2.3, 2.3, -1.9, 1.9
    wall_h, r = 2.2, 0.13
    door_s, win_s = (2.5, 3.4, 0, 1.9), (1.4, 2.4, 1.1, 1.45)
    # logs on all four sides, alternate courses so corners interlock
    bd.logs(k, root, (x0, y0), (x1, y0), 0, wall_h, r, rnd, skip=(door_s,), phase=0)       # front (-Y)
    bd.logs(k, root, (x0, y1), (x1, y1), 0, wall_h, r, rnd, phase=0)
    bd.logs(k, root, (x1, y0), (x1, y1), 0.12, wall_h, r, rnd, skip=(win_s,), phase=0)     # side (+X)
    bd.logs(k, root, (x0, y0), (x0, y1), 0.12, wall_h, r, rnd, phase=0)
    # infill behind the logs (chinking), so gaps read dark, not see-through
    k.box("core", (x1 - x0 - 0.1, y1 - y0 - 0.1, wall_h), (0, 0, wall_h / 2), "dirt_fill", parent=root, bevel=False)
    bd.door(k, root, ((x0 + 2.95), y0 - 0.12, 0.0), bd.FRONT, 0.8, 1.8, mat="timber_raw", strap="iron_forged")
    k.box("slit", (0.6, 0.05, 0.16), (x1 + 0.12, (y0 + 1.9), 1.28), "iron_black", rot=(0, 0, math.pi / 2),
          parent=root, bevel=False)
    rz = bd.gable_roof(k, root, x0, x1, y0, y1, wall_h, 0.9, rnd, "timber_raw", unit=(0.3, 0.42), over=0.35,
                       thick=0.04, along="x")
    bd.gable_ends(k, root, x0 - 0.05, x1 + 0.05, y0, y1, wall_h, rz - 0.05, "timber_raw", along="x")
    # signal bell on a post (L1 mechanism)
    post = Vector((x1 + 0.7, y0 - 0.5, 0))
    k.tube("bell_post", post, post + Vector((0, 0, 2.3)), 0.07, "timber_raw", parent=root, segs=10)
    k.beam("bell_arm", post + Vector((0, 0, 2.2)), post + Vector((0, -0.55, 2.2)), (0.08, 0.08), "timber_raw",
           parent=root)
    k.lathe("bell", [(0, 0.0), (0.0, 0.05), (0.1, 0.09), (0.22, 0.15), (0.24, 0.16)], "bronze_old", segs=20,
            loc=post + Vector((0, -0.5, 2.15)), rot=(math.pi / 2, 0, 0), parent=root).rotation_euler = (-math.pi / 2, 0, 0)
    k.hose("bell_rope", [post + Vector((0, -0.5, 1.92)), post + Vector((0.02, -0.48, 1.3)), post + Vector((0.03, -0.45, 1.0))],
           0.01, "rope", parent=root)
    bd.flag_mast(k, root, (x0 - 0.45, y0 - 0.45, 0), 5.2, mat="timber_raw")
    _supplies(k, root, 1, rnd)


def _l2(k, root, rnd):
    x0, x1, y0, y1 = -2.6, 2.6, -2.1, 2.1
    plinth, wall_h = 0.55, 2.6
    door_s = (2.6, 3.5, 0, 2.6)
    for p0, p1 in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        bd.masonry(k, root, p0, p1, 0, plinth, 0.6, rnd, mat="stone", course=0.28, unit=(0.3, 0.6), rough=0.05,
                   skip=((2.6, 3.5, 0.0, 1.0),) if p0 == (x0, y0) else ())
    z = plinth
    k.box("core", (x1 - x0 - 0.2, y1 - y0 - 0.2, wall_h), (0, 0, z + wall_h / 2), "timber_tarred", parent=root,
          bevel=False)
    wins_f = ((0.7, 1.7, 0.9, 2.1),)
    wins_s = ((0.6, 1.6, 0.9, 2.1), (2.6, 3.6, 0.9, 2.1))
    bd.planks(k, root, (x0, y0 - 0.02), (x1, y0 - 0.02), z, wall_h, 0.06, rnd, skip=(door_s,) + wins_f)
    bd.planks(k, root, (x1 + 0.02, y0), (x1 + 0.02, y1), z, wall_h, 0.06, rnd, skip=wins_s)
    bd.planks(k, root, (x1, y1 + 0.02), (x0, y1 + 0.02), z, wall_h, 0.06, rnd)
    bd.planks(k, root, (x0 - 0.02, y1), (x0 - 0.02, y0), z, wall_h, 0.06, rnd)
    for (xa, ya) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):            # corner posts with iron bands
        k.box("corner_post", (0.2, 0.2, wall_h + 0.05), (xa, ya, z + wall_h / 2), "timber_tarred", parent=root,
              bevel=0.015)
        for zz in (0.4, wall_h - 0.4):
            k.box("corner_band", (0.23, 0.23, 0.05), (xa, ya, z + zz), "iron_forged", parent=root, bevel=False)
    k.beam("sill_beam", (x0, y0 - 0.06, z + 0.06), (x1, y0 - 0.06, z + 0.06), (0.14, 0.12), "timber_tarred", parent=root)
    k.beam("sill_beam", (x1 + 0.06, y0, z + 0.06), (x1 + 0.06, y1, z + 0.06), (0.14, 0.12), "timber_tarred", parent=root)
    bd.window(k, root, (x0 + 1.2, y0 - 0.08, z + 1.5), bd.FRONT, 0.8, 1.0, shutters="timber_red")
    for s in (1.1, 3.1):
        bd.window(k, root, (x1 + 0.08, y0 + s, z + 1.5), bd.SIDE, 0.8, 1.0, shutters="timber_red")
    bd.door(k, root, (x0 + 3.05, y0 - 0.1, 0.55), bd.FRONT, 0.9, 2.0, mat="timber_red")
    for i in range(3):                                                     # steps up to the door
        k.box("step", (1.2, 0.3, 0.18), (x0 + 3.05, y0 - 0.35 - 0.3 * i, 0.55 - 0.18 * (i + 1) + 0.09), "stone",
              parent=root, bevel=0.02)
    rz = bd.gable_roof(k, root, x0, x1, y0, y1, z + wall_h, 1.3, rnd, "timber_tarred", unit=(0.26, 0.24), over=0.4,
                       along="x")
    bd.gable_ends(k, root, x0 - 0.04, x1 + 0.04, y0, y1, z + wall_h, rz - 0.04, "timber_tarred", along="x")
    defender.emblem(k, root, (x1 + 0.12, 0.0, z + wall_h + 0.6), (1, 0, 0), h=0.7)
    # field telephone: pole, cross-arm with insulators, wires into the wall, a wire drum (L2 mechanism)
    pole = Vector((x1 + 0.9, y0 - 0.7, 0))
    k.tube("tel_pole", pole, pole + Vector((0, 0, 4.4)), 0.09, "timber_tarred", radius_end=0.07, parent=root, segs=12)
    k.beam("tel_arm", pole + Vector((-0.6, 0, 4.1)), pole + Vector((0.6, 0, 4.1)), (0.1, 0.1), "timber_tarred",
           parent=root)
    for dx in (-0.45, -0.15, 0.15, 0.45):
        k.lathe("insulator", [(0, 0.0), (0, 0.04), (0.06, 0.05), (0.1, 0.03), (0.13, 0.0)], "porcelain", segs=14,
                loc=pole + Vector((dx, 0, 4.15)), rot=(math.pi / 2, 0, 0), parent=root)
    for dx in (-0.45, 0.45):
        a = pole + Vector((dx, 0, 4.25))
        b = Vector((x1 - 0.2, y0 + 0.6, z + wall_h - 0.2))
        k.hose("tel_wire", [a, a.lerp(b, 0.5) - Vector((0, 0, 0.35)), b], 0.008, "steel_cable", parent=root)
    k.box("tel_box", (0.3, 0.16, 0.4), (x1 + 0.1, y0 + 0.6, z + 1.6), "timber_oak", rot=(0, 0, math.pi / 2),
          parent=root, bevel=0.02)
    drum = Vector((x1 + 0.6, y0 + 1.6, 0.4))
    k.cylinder("wire_drum", 0.35, 0.5, drum + Vector((-0.25, 0, 0)), "steel_cable", segs=24, rot=(0, math.pi / 2, 0),
               parent=root)
    for sx in (-1, 1):
        k.cylinder("drum_flange", 0.42, 0.04, drum + Vector((sx * 0.27 - 0.02, 0, 0)), "iron_forged", segs=24,
                   rot=(0, math.pi / 2, 0), parent=root)
        k.beam("drum_leg", drum + Vector((sx * 0.3, 0, 0)), drum + Vector((sx * 0.3, 0.3, -0.4)), (0.06, 0.06),
               "timber_tarred", parent=root)
        k.beam("drum_leg", drum + Vector((sx * 0.3, 0, 0)), drum + Vector((sx * 0.3, -0.3, -0.4)), (0.06, 0.06),
               "timber_tarred", parent=root)
    bd.flag_mast(k, root, (x0 - 0.5, y0 - 0.5, 0), 6.2, mat="timber_tarred", finial="iron_forged")
    _supplies(k, root, 2, rnd)


def _keep(k, root, rnd, x0, x1, y0, y1, h, mat, course, unit, rough, door_x, wins_front, wins_side):
    skips_f = ((door_x - 0.55, door_x + 0.55, 0, 2.3),) + tuple((s - 0.45, s + 0.45, za, za + 1.2)
                                                               for s, za in wins_front)
    skips_s = tuple((s - 0.45, s + 0.45, za, za + 1.2) for s, za in wins_side)
    bd.masonry(k, root, (x0, y0), (x1, y0), 0, h, 0.6, rnd, mat=mat, course=course, unit=unit, rough=rough,
               skip=skips_f)
    bd.masonry(k, root, (x1, y0), (x1, y1), 0, h, 0.6, rnd, mat=mat, course=course, unit=unit, rough=rough,
               skip=skips_s)
    bd.masonry(k, root, (x1, y1), (x0, y1), 0, h, 0.6, rnd, mat=mat, course=course, unit=unit, rough=rough)
    bd.masonry(k, root, (x0, y1), (x0, y0), 0, h, 0.6, rnd, mat=mat, course=course, unit=unit, rough=rough)
    for (xa, ya) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):          # quoins: bigger corner stones
        for i in range(int(h / (course * 2))):
            z = i * course * 2
            long_x = i % 2 == 0
            k.box("quoin", (0.75 if long_x else 0.66, 0.66 if long_x else 0.75, course * 2 - 0.02),
                  (xa, ya, z + course), mat, parent=root, bevel=0.03)
    for s, za in wins_front:
        bd.window(k, root, (x0 + s, y0 - 0.27, za + 0.6), bd.FRONT, 0.7, 1.1, frame="timber_oak", sill=mat)
    for s, za in wins_side:
        bd.window(k, root, (x1 + 0.27, y0 + s, za + 0.6), bd.SIDE, 0.7, 1.1, frame="timber_oak", sill=mat)
    k.box("core", (x1 - x0 - 0.5, y1 - y0 - 0.5, h), (0, 0, h / 2), "iron_black", parent=root, bevel=False)


def _l3(k, root, rnd):
    x0, x1, y0, y1 = -2.8, 2.8, -2.5, 2.5
    h = 4.2
    _keep(k, root, rnd, x0, x1, y0, y1, h, "stone", 0.3, (0.35, 0.8), 0.05, 3.3,
          ((1.3, 0.9), (1.3, 2.6), (3.3, 2.6)), ((1.4, 0.9), (3.6, 0.9), (1.4, 2.6), (3.6, 2.6)))
    bd.door(k, root, (x0 + 3.3, y0 - 0.25, 0.0), bd.FRONT, 1.0, 2.2, mat="timber_oak")
    rz = bd.gable_roof(k, root, x0, x1, y0, y1, h, 1.6, rnd, "slate", unit=(0.3, 0.2), over=0.35, thick=0.025,
                       ridge_mat="iron_forged", along="x")
    bd.gable_ends(k, root, x0 + 0.05, x1 - 0.05, y0 + 0.05, y1 - 0.05, h, rz - 0.1, "stone", t=0.5, along="x")
    ch = Vector((-1.6, 1.0, 0))
    bd.masonry(k, root, (ch.x - 0.35, ch.y), (ch.x + 0.35, ch.y), rz - 1.2, 2.0, 0.6, rnd, mat="stone", course=0.25,
               unit=(0.25, 0.4), rough=0.03)
    k.box("chimney_cap", (0.85, 0.75, 0.1), (ch.x, ch.y, rz + 0.85), "stone", parent=root, bevel=0.02)
    defender.emblem(k, root, (x0 + 3.3, y0 - 0.32, 2.75), (0, -1, 0), h=0.8)
    # optical semaphore on the ridge: mast, regulator beam and two indicator arms (L3 mechanism)
    m = Vector((1.2, 0.0, rz))
    k.tube("sema_mast", m, m + Vector((0, 0, 3.4)), 0.08, "timber_oak", radius_end=0.06, parent=root, segs=12)
    for sx in (-1, 1):
        k.beam("sema_stay", m + Vector((0, 0, 2.2)), m + Vector((sx * 1.1, 0, -0.6)), (0.04, 0.04), "iron_forged",
               parent=root)
    top = m + Vector((0, -0.12, 3.2))
    k.beam("sema_regulator", top + Vector((-1.2, 0, -0.3)), top + Vector((1.2, 0, 0.3)), (0.12, 0.08), "timber_red",
           parent=root)
    for sx, ang in ((-1, 0.8), (1, -0.5)):
        e = top + Vector((sx * 1.2, 0, sx * 0.3))
        k.beam("sema_arm", e, e + Vector((sx * 0.1, 0, 0.0)) + Vector((math.sin(ang) * 0.9 * sx, 0, math.cos(ang) * 0.9)),
               (0.08, 0.05), "timber_red", parent=root)
        k.cylinder("sema_pivot", 0.06, 0.1, e + Vector((0, -0.08, 0)), "iron_forged", segs=12, rot=(math.pi / 2, 0, 0),
                   parent=root)
    k.cylinder("sema_hub", 0.1, 0.12, top + Vector((0, -0.08, 0)), "iron_forged", segs=14, rot=(math.pi / 2, 0, 0),
               parent=root)
    for i in range(2):
        k.hose("sema_cord", [top + Vector((0.3 * (1 - 2 * i), -0.1, 0.0)), m + Vector((0.1 - 0.2 * i, -0.12, 1.5)),
                             m + Vector((0.1 - 0.2 * i, -0.1, 0.4))], 0.008, "rope", parent=root)
    bd.flag_mast(k, root, (x0 - 0.55, y0 - 0.55, 0), 7.0, mat="timber_oak", finial="brass")
    _supplies(k, root, 3, rnd)


def _l4(k, root, rnd):
    x0, x1, y0, y1 = -3.0, 3.0, -2.7, 2.7
    h = 4.8
    _keep(k, root, rnd, x0, x1, y0, y1, h, "stone_dressed", 0.36, (0.6, 1.1), 0.006, 3.5,
          ((1.3, 1.0), (1.3, 2.9), (3.5, 2.9), (5.0, 1.0)), ((1.3, 1.0), (3.7, 1.0), (1.3, 2.9), (3.7, 2.9)))
    bd.door(k, root, (x0 + 3.5, y0 - 0.25, 0.0), bd.FRONT, 1.1, 2.3, mat="timber_oak", strap="iron_black")
    # flat roof with a crenellated parapet
    k.box("roof", (x1 - x0, y1 - y0, 0.2), (0, 0, h + 0.1), "iron_black", parent=root, bevel=0.01)
    k.box("roof_lead", (x1 - x0 - 0.6, y1 - y0 - 0.6, 0.05), (0, 0, h + 0.22), "steel_worn", parent=root, bevel=0.01)
    for p0, p1 in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        L = (Vector(p1) - Vector(p0)).length
        d = (Vector(p1) - Vector(p0)).normalized()
        n_m = int(L / 0.9)
        for i in range(n_m):
            if i % 2:
                continue
            c = Vector(p0) + d * ((i + 0.5) * L / n_m)
            k.box("merlon", (L / n_m if abs(d.x) > 0.5 else 0.5, L / n_m if abs(d.y) > 0.5 else 0.5, 0.7),
                  (c.x, c.y, h + 0.2 + 0.35), "stone_dressed", parent=root, bevel=0.02)
        k.box("parapet", (L if abs(d.x) > 0.5 else 0.5, L if abs(d.y) > 0.5 else 0.5, 0.3),
              ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, h + 0.2 + 0.15 - 0.15), "stone_dressed", parent=root,
              bevel=0.02)
    # riveted black iron corner plates
    for (xa, ya) in ((x0, y0), (x1, y0), (x1, y1)):
        for sx, sy in ((1, 0), (0, 1)):
            nx = -1 if xa < 0 else 1
            ny = -1 if ya < 0 else 1
            if sx:
                loc = (xa - nx * 0.45, ya + ny * 0.33, h / 2)
                size = (0.9, 0.04, h - 0.2)
            else:
                loc = (xa + nx * 0.33, ya - ny * 0.45, h / 2)
                size = (0.04, 0.9, h - 0.2)
            k.box("corner_plate", size, loc, "iron_black", parent=root, bevel=0.005)
            for zz in [0.3 + 0.45 * i for i in range(int((h - 0.6) / 0.45) + 1)]:
                for o in (-0.35, 0.35):
                    if sx:
                        rl = (loc[0] + o, loc[1] + ny * 0.03, zz)
                        rr = (math.pi / 2, 0, 0)
                    else:
                        rl = (loc[0] + nx * 0.03, loc[1] + o, zz)
                        rr = (0, math.pi / 2, 0)
                    k.cylinder("rivet", 0.025, 0.03, rl, "iron_black", segs=8, rot=rr, parent=root, bevel=False)
    defender.emblem(k, root, (x0 + 3.5, y0 - 0.32, 2.95), (0, -1, 0), h=0.9)
    defender.emblem(k, root, (x1 + 0.32, 0.0, 3.4), (1, 0, 0), h=0.9)
    # armoured observation cupola with a brass rangefinder (L4 mechanism)
    c = Vector((0.6, 0.4, h + 0.25))
    k.cylinder("cupola_ring", 1.1, 0.25, c, "iron_black", segs=40, parent=root, bevel=0.01)
    k.cylinder("cupola", 0.95, 0.75, c + Vector((0, 0, 0.25)), "iron_black", segs=40, radius_top=0.8, parent=root,
               bevel=0.02)
    k.lathe("cupola_dome", [(0, 0.8), (0.15, 0.75), (0.3, 0.55), (0.4, 0.3), (0.43, 0.0)], "iron_black", segs=40,
            loc=c + Vector((0, 0, 1.0)), rot=(math.pi / 2, 0, 0), parent=root)
    k.box("cupola_slit", (1.0, 0.05, 0.1), c + Vector((0.0, -0.82, 0.75)), "glass", parent=root, bevel=False)
    rf = c + Vector((0, 0, 1.55))
    k.tube("rangefinder", rf + Vector((-1.3, 0, 0)), rf + Vector((1.3, 0, 0)), 0.08, "brass", parent=root, segs=16)
    for sx in (-1, 1):
        k.cylinder("rf_hood", 0.12, 0.25, rf + Vector((sx * 1.3, 0.0, -0.12)), "brass", segs=16, parent=root,
                   bevel=0.01)
        k.cylinder("rf_lens", 0.08, 0.02, rf + Vector((sx * 1.3, -0.12, 0.0)), "glass", segs=16,
                   rot=(math.pi / 2, 0, 0), parent=root, bevel=False)
    k.cylinder("rf_post", 0.08, 0.15, c + Vector((0, 0, 1.4)), "brass", segs=12, parent=root, bevel=False)
    bd.flag_mast(k, root, (x0 - 0.55, y0 - 0.55, 0), 7.6, mat="iron_black", finial="brass")
    _supplies(k, root, 4, rnd)


def _l5(k, root, rnd):
    x0, x1, y0, y1 = -3.1, 3.1, -2.8, 2.8
    h = 5.2
    _keep(k, root, rnd, x0, x1, y0, y1, h, "stone_pale", 0.4, (0.7, 1.2), 0.003, 3.6,
          ((1.3, 1.1), (1.3, 3.2), (3.6, 3.2), (5.0, 1.1)), ((1.3, 1.1), (3.7, 1.1), (1.3, 3.2), (3.7, 3.2)))
    bd.door(k, root, (x0 + 3.6, y0 - 0.25, 0.0), bd.FRONT, 1.3, 2.5, mat="timber_oak", strap="gold_trim")
    for sx in (-1, 1):                                             # columns at the gate
        k.cylinder("column", 0.16, 2.9, (x0 + 3.6 + sx * 1.0, y0 - 0.45, 0.0), "stone_pale", segs=20, parent=root)
        k.box("column_cap", (0.42, 0.42, 0.14), (x0 + 3.6 + sx * 1.0, y0 - 0.45, 2.95), "gold_trim", parent=root,
              bevel=0.01)
    k.box("gate_lintel", (2.5, 0.5, 0.35), (x0 + 3.6, y0 - 0.4, 3.2), "stone_pale", parent=root, bevel=0.03)
    # black steel cornice with a gold band
    k.box("cornice", (x1 - x0 + 0.4, y1 - y0 + 0.4, 0.3), (0, 0, h + 0.15), "iron_black", parent=root, bevel=0.02)
    k.box("cornice_gold", (x1 - x0 + 0.44, y1 - y0 + 0.44, 0.06), (0, 0, h + 0.05), "gold_trim", parent=root,
          bevel=0.005)
    k.box("roof", (x1 - x0, y1 - y0, 0.2), (0, 0, h + 0.4), "slate", parent=root, bevel=0.01)
    for (xa, ya) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):     # corner urns
        k.lathe("urn", [(0, 0), (0, 0.18), (0.15, 0.12), (0.35, 0.22), (0.5, 0.15), (0.55, 0.0)], "gold_trim",
                segs=16, loc=(xa, ya, h + 0.3), rot=(math.pi / 2, 0, 0), parent=root)
    # copper dome on a drum
    c = Vector((0.3, 0.3, h + 0.5))
    k.cylinder("drum", 1.6, 1.0, c, "stone_pale", segs=48, parent=root, bevel=0.02)
    for i in range(12):
        a = 2 * math.pi * i / 12
        k.box("drum_pilaster", (0.14, 0.12, 1.0), c + Vector((1.62 * math.cos(a), 1.62 * math.sin(a), 0.5)),
              "stone_pale", rot=(0, 0, a + math.pi / 2), parent=root, bevel=0.01)
    k.cylinder("drum_band", 1.7, 0.12, c + Vector((0, 0, 1.0)), "gold_trim", segs=48, parent=root, bevel=0.01)
    dome = [(0, 1.62), (0.4, 1.52), (0.8, 1.25), (1.1, 0.9), (1.32, 0.45), (1.4, 0.0)]
    k.lathe("dome", dome, "copper", segs=48, loc=c + Vector((0, 0, 1.1)), rot=(math.pi / 2, 0, 0), parent=root)
    for i in range(16):                                            # dome ribs
        a = 2 * math.pi * i / 16
        pts = [c + Vector((r * math.cos(a), r * math.sin(a), 1.1 + y)) for y, r in dome]
        k.hose("dome_rib", pts, 0.025, "gold_trim", parent=root)
    defender.emblem(k, root, (x0 + 3.6, y0 - 0.66, 3.75), (0, -1, 0), h=1.1)
    defender.emblem(k, root, (x1 + 0.32, 0.0, 3.6), (1, 0, 0), h=1.1)
    # wireless mast: lattice tower, brass coils, discharge globes (L5 mechanism)
    m = c + Vector((0, 0, 2.5))
    for i in range(3):
        a = 2 * math.pi * i / 3
        k.tube("mast_leg", m + Vector((0.28 * math.cos(a), 0.28 * math.sin(a), 0)), m + Vector((0.06 * math.cos(a), 0.06 * math.sin(a), 3.6)),
               0.025, "iron_black", parent=root, segs=8)
    for z in (0.6, 1.2, 1.8, 2.4, 3.0):
        k.torus("mast_ring", 0.28 - z * 0.06, 0.015, m + Vector((0, 0, z)), "iron_black", parent=root, segs=16,
                tube_segs=4)
    for z, r in ((0.9, 0.24), (2.1, 0.17)):
        k.cylinder("coil", r, 0.45, m + Vector((0, 0, z)), "copper", segs=24, parent=root, bevel=False)
        for j in range(6):
            k.torus("coil_turn", r + 0.01, 0.012, m + Vector((0, 0, z + 0.05 + j * 0.07)), "brass", parent=root,
                    segs=20, tube_segs=4)
    k.lathe("top_globe", [(0, 0), (0.0, 0.14), (0.14, 0.2), (0.28, 0.14), (0.28, 0.0)], "arc_glow", segs=20,
            loc=m + Vector((0, 0, 3.6)), rot=(math.pi / 2, 0, 0), parent=root)
    for sx in (-1, 1):
        k.tube("aerial", m + Vector((0, 0, 3.5)), Vector((sx * 2.6 + 0.3, 0.3, h + 0.6)), 0.008, "steel_cable",
               parent=root, segs=4, bevel=False)
        k.lathe("insulator_globe", [(0, 0), (0.0, 0.08), (0.08, 0.1), (0.16, 0.0)], "porcelain", segs=14,
                loc=(sx * 2.6 + 0.3, 0.3, h + 0.5), rot=(math.pi / 2, 0, 0), parent=root)
    bd.flag_mast(k, root, (x0 - 0.55, y0 - 0.55, 0), 8.2, mat="iron_black", finial="gold_trim")
    _supplies(k, root, 5, rnd)
