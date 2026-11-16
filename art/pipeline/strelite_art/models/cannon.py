"""Cannon tower (bg: „Оръдие“), upgrade levels 1-3.

Silhouette contract (must hold at every level so players recognise the gun):
- octagonal base on a 2x2 tile footprint (radius ~0.85 m),
- two carriage cheeks with a single long barrel pointing along +Y,
- barrel axis at roughly the same height.
Each level ADDS parts and upgrades materials; it never changes the outline.

Returns (root, turret): rotate `turret` around Z to aim.
"""
import math

import bmesh
import bpy

from ..geo import Kit

LEVELS = (1, 2, 3)


def build(style, level=1):
    k = Kit(style)
    root = k.empty("cannon")

    # ---------------- base (static) ----------------
    if level == 1:
        base_mat, base_h = "wood", 0.26
        k.cylinder("base", 0.85, base_h, (0, 0, 0), base_mat, segs=8, parent=root)
        k.cylinder("base_band", 0.865, 0.06, (0, 0, 0.04), "iron", segs=8, parent=root, bevel=False)
        # plank seams on the deck
        for i, x in enumerate((-0.42, 0.0, 0.42)):
            seam_len = 2 * math.sqrt(0.74 ** 2 - x ** 2)
            k.box(f"plank_seam{i}", (0.03, seam_len, 0.012), (x, 0, base_h), "wood_dark", parent=root,
                  bevel=False, outline=False)
        deck_mat, deck_r, deck_h = "wood_dark", 0.58, 0.08
    elif level == 2:
        base_mat, base_h = "stone", 0.36
        k.cylinder("base", 0.85, base_h, (0, 0, 0), base_mat, segs=8, parent=root,
                   radius_top=0.8)
        # stone blocks ring (crenel-like rhythm, low so it doesn't change silhouette)
        for i in range(8):
            a = 2 * math.pi * i / 8
            k.box(f"block{i}", (0.34, 0.2, 0.12),
                  (0.74 * math.cos(a), 0.74 * math.sin(a), base_h + 0.04), "stone_dark",
                  rot=(0, 0, a + math.pi / 2), parent=root)
        k.cylinder("base_band", 0.87, 0.07, (0, 0, 0.08), "brass", segs=8, parent=root, bevel=False)
        deck_mat, deck_r, deck_h = "wood", 0.6, 0.1
    else:
        base_mat, base_h = "stone", 0.42
        k.cylinder("base", 0.86, base_h, (0, 0, 0), base_mat, segs=8, parent=root,
                   radius_top=0.8)
        for i in range(8):
            a = 2 * math.pi * i / 8 + math.pi / 8
            k.box(f"armor{i}", (0.5, 0.06, 0.3),
                  (0.83 * math.cos(a), 0.83 * math.sin(a), 0.2), "steel_dark",
                  rot=(math.radians(-8), 0, a + math.pi / 2), parent=root)
            # gold rivet
            k.cylinder(f"rivet{i}", 0.035, 0.03, (0.87 * math.cos(a), 0.87 * math.sin(a), 0.22),
                       "gold", segs=10, rot=(math.pi / 2, 0, a + math.pi / 2), parent=root,
                       bevel=False, outline=False)
        k.cylinder("base_cap", 0.81, 0.06, (0, 0, base_h), "stone_dark", segs=8, parent=root)
        k.cylinder("gold_band", 0.875, 0.05, (0, 0, base_h - 0.02), "gold", segs=8, parent=root,
                   bevel=False)
        deck_mat, deck_r, deck_h = "steel_dark", 0.68, 0.1

    deck_z = base_h + (0.06 if level == 3 else 0)
    k.cylinder("deck", deck_r, deck_h, (0, 0, deck_z), deck_mat, segs=24, parent=root)
    top = deck_z + deck_h

    # ---------------- turret (rotates) ----------------
    turret = k.empty("turret", (0, 0, top), parent=root)

    cheek_mat = {1: "wood", 2: "wood", 3: "steel_dark"}[level]
    cheek_h = 0.36
    for side in (-1, 1):
        # Cheek: slanted top via a box tilted slightly back.
        k.box(f"cheek{side}", (0.12, 0.72, cheek_h), (side * 0.25, -0.05, cheek_h / 2),
              cheek_mat, parent=turret)
        if level >= 2:
            # iron corner caps
            k.box(f"cheek_cap{side}", (0.14, 0.16, 0.06), (side * 0.25, 0.27, cheek_h - 0.02),
                  "iron" if level == 2 else "gold", parent=turret)
        # wheels on the carriage (classic cannon read)
        wheel_mat = "wood_dark" if level < 3 else "iron"
        k.cylinder(f"wheel{side}", 0.15, 0.06, (side * 0.34, 0.18, 0.12), wheel_mat, segs=16,
                   rot=(0, math.pi / 2, 0), parent=turret)
        k.cylinder(f"wheel_hub{side}", 0.05, 0.08, (side * 0.35, 0.18, 0.12),
                   "iron" if level < 3 else "gold", segs=10, rot=(0, math.pi / 2, 0), parent=turret,
                   bevel=False, outline=False)
    k.box("axle", (0.46, 0.14, 0.1), (0, -0.05, 0.08), "wood_dark" if level < 3 else "iron",
          parent=turret)

    # Barrel pivot (slight upward pitch).
    barrel_z = cheek_h + 0.04
    pivot = k.empty("barrel_pivot", (0, 0, barrel_z), parent=turret)
    pivot.rotation_euler = (math.radians(9), 0, 0)

    trunnion_mat = {1: "iron", 2: "brass", 3: "gold"}[level]
    k.cylinder("trunnion", 0.06, 0.66, (-0.33, 0, 0), trunnion_mat, segs=12,
               rot=(0, math.pi / 2, 0), parent=pivot, bevel=False)

    if level == 1:
        profile = [(-0.5, 0.0), (-0.5, 0.06), (-0.44, 0.09), (-0.38, 0.07), (-0.34, 0.2),
                   (-0.2, 0.21), (0.45, 0.16), (0.55, 0.16), (0.58, 0.19), (0.68, 0.19),
                   (0.68, 0.0)]
        barrel_mat, band_mat, bands = "iron", "iron", [(-0.3, 0.215)]
        muzzle_y = 0.68
    elif level == 2:
        profile = [(-0.52, 0.0), (-0.52, 0.06), (-0.46, 0.1), (-0.4, 0.075), (-0.36, 0.215),
                   (-0.2, 0.225), (0.55, 0.165), (0.64, 0.165), (0.67, 0.2), (0.78, 0.2),
                   (0.78, 0.0)]
        barrel_mat, band_mat = "iron", "brass"
        bands = [(-0.3, 0.235), (0.05, 0.21), (0.38, 0.19)]
        muzzle_y = 0.78
    else:
        profile = [(-0.55, 0.0), (-0.55, 0.07), (-0.48, 0.11), (-0.42, 0.08), (-0.38, 0.24),
                   (-0.2, 0.25), (0.58, 0.185), (0.66, 0.185), (0.7, 0.23), (0.84, 0.215),
                   (0.86, 0.24), (0.88, 0.0)]
        barrel_mat, band_mat = "steel_dark", "gold"
        bands = [(-0.3, 0.26), (-0.05, 0.245), (0.2, 0.225), (0.45, 0.205)]
        muzzle_y = 0.88

    k.lathe("barrel", profile, barrel_mat, parent=pivot)
    for i, (y, r) in enumerate(bands):
        k.lathe(f"band{i}", [(y - 0.035, 0.0), (y - 0.035, r), (y + 0.035, r), (y + 0.035, 0.0)],
                band_mat, parent=pivot, outline=False)
    if level >= 2:
        # Bright muzzle ring
        k.lathe("muzzle_ring", [(muzzle_y - 0.1, 0.0), (muzzle_y - 0.1, profile[-2][1] + 0.012),
                                (muzzle_y - 0.0, profile[-2][1] + 0.012), (muzzle_y, 0.0)],
                band_mat, parent=pivot, outline=False)
    # Dark bore so the barrel reads as a tube from the front.
    k.cylinder("bore", profile[-2][1] * 0.55, 0.02, (0, muzzle_y - 0.005, 0), "bore", segs=16,
               rot=(-math.pi / 2, 0, 0), parent=pivot, bevel=False, outline=False)

    if level == 3:
        # Front shield plates either side of the barrel, with spikes.
        for side in (-1, 1):
            k.box(f"shield{side}", (0.26, 0.06, 0.4), (side * 0.32, 0.36, 0.3), "steel_dark",
                  rot=(math.radians(-12), 0, side * math.radians(-18)), parent=turret)
            k.box(f"shield_trim{side}", (0.28, 0.07, 0.05), (side * 0.32, 0.37, 0.5), "gold",
                  rot=(math.radians(-12), 0, side * math.radians(-18)), parent=turret)
            k.cylinder(f"spike{side}", 0.04, 0.16, (side * 0.4, 0.43, 0.32), "iron", segs=8,
                       radius_top=0.0, rot=(-math.pi / 2, 0, side * math.radians(-18)),
                       parent=turret, bevel=False)

    # Faction pennant: grows with level (identity marker, behind the gun).
    if level >= 2:
        pole_h = 0.75 if level == 2 else 1.0
        k.cylinder("pole", 0.025, pole_h, (-0.25, -0.42, 0), "wood_dark" if level == 2 else "gold",
                   segs=8, parent=turret, bevel=False)
        k.flag("pennant", 0.38 if level == 2 else 0.5, 0.2 if level == 2 else 0.26,
               (-0.25, -0.42, pole_h - 0.13), "accent", parent=turret)
    if level == 1:
        # Cannonball stack: cheap story detail.
        for i, (x, y, z) in enumerate([(0.5, -0.45, 0.07), (0.62, -0.38, 0.07), (0.56, -0.5, 0.07),
                                       (0.56, -0.44, 0.18)]):
            _ball(k, f"ball{i}", (x, y, base_h + z), root)

    return root, turret


def _ball(k, name, loc, parent):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=0.07)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    obj.location = loc
    return k._finish(obj, "iron", smooth=True, bevel=False, parent=parent)
