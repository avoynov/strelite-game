"""76 mm divisional field gun, ZIS-3 type (bg: „Дивизионно оръдие“). PLACEHOLDER
model for style В, built at real size from public dimensions (length 6.1 m,
width 1.65 m, line of fire 0.88 m, barrel 3.4 m with a double-baffle muzzle
brake): split tubular trails with spades, disc wheels, angular shield, recoil
brake under the barrel and recuperator above it. Soviet 4BO green.

Level 1: the gun on bare soil, two crates, a few rounds, spent cases.
Level 2: sandbag breastwork on the far half of the position, stacked wooden
         shell crates, unit pennant.
Level 3: the gun dug into a pit revetted with logs, spoil bank around it, extra
         armour plates and side wings on the shield, ammunition under a net.

Returns (root, turret). `turret` (the whole gun) rotates around Z to aim.
"""
import math

from mathutils import Matrix, Vector

from .. import fort
from .. import materials_photoreal as mp
from ..fort import pol
from ..geo import Kit
from .howitzer import _bolts

LEVELS = (1, 2, 3)
STYLES = ("photoreal",)
FRAME_M = 9.5           # photo-style preview frame
TARGET_Z = 0.7
SPRITE_FRAME_M = 14.0   # game sprites: metres across the render
GUN_SHIFT = 1.0         # the gun sits this far forward of the rotation centre
SWEEP_M = 2.8           # ground-level parts (spades) turn inside this radius
FOOTPRINT_M = 4.0       # all static art stays inside this radius (2x2 tiles of 4 m)
AMMO_DEG = (-140, -72)  # sector of the ammunition point, toward the camera
WALL_IN = 2.95          # inner face of the breastwork / the pit wall
PIT_DEPTH = 0.55
ELEVATION_DEG = 12.0
HERO_DIR = 12

G, WORN, BARREL, SOOT, STEEL = "paint_4bo", "paint_4bo_worn", "paint_4bo_barrel", "paint_4bo_soot", "gunmetal"
TRUNNION = Vector((0, -0.1, 0.87))


def build(style, level=1):
    k = Kit(style)
    root = k.empty("zis3")
    turret = k.empty("turret", parent=root)
    turret["node"] = "turret"
    gun = k.empty("gun", (0, GUN_SHIFT, -PIT_DEPTH if level >= 3 else 0.0), parent=turret)
    mp.set_reference(gun)
    _carriage(k, gun)
    _shield(k, gun, level)
    _elevating_mass(k, gun, level)
    _props(k, root, level)
    return root, turret


def ground(level):
    from ..terrain import Patch
    patch = Patch(r_solid=FOOTPRINT_M, r_out=FOOTPRINT_M + 0.7,
                  r_bare={1: SWEEP_M + 0.4, 2: 3.5, 3: 3.75}[level], seed=23, ragged=0.5)
    if level >= 3:
        patch.pit(WALL_IN + 0.07, PIT_DEPTH, bank=0.24, bank_width=0.75, gap=AMMO_DEG)
    return patch


# --------------------------------------------------------------------------
def _wheel(k, t, hub):
    w = k.empty("wheel", hub, parent=t)
    w.rotation_euler = (0, 0, -math.pi / 2)     # local Y = axle
    tyre = [(-0.06, 0.0), (-0.06, 0.27), (-0.085, 0.3), (-0.092, 0.38), (-0.07, 0.42),
            (-0.03, 0.432), (0.03, 0.432), (0.07, 0.42), (0.092, 0.38), (0.085, 0.3),
            (0.06, 0.27), (0.06, 0.0)]
    k.lathe("tyre", tyre, "rubber", segs=44, parent=w)
    rim = [(-0.05, 0.0), (-0.05, 0.09), (-0.022, 0.25), (-0.06, 0.275), (0.06, 0.275),
           (0.022, 0.25), (0.05, 0.09), (0.05, 0.0)]
    k.lathe("rim", rim, G, segs=36, parent=w)
    for s in (-1, 1):
        k.cylinder("hubcap", 0.065, 0.05, (0, s * 0.05, 0), WORN, segs=18,
                   rot=(-s * math.pi / 2, 0, 0), parent=w)
        for i in range(6):                              # lightening holes of the stamped disc
            a = 2 * math.pi * i / 6
            k.cylinder("disc_hole", 0.036, 0.012, (0.175 * math.cos(a), s * 0.034, 0.175 * math.sin(a)),
                       "bore", segs=12, rot=(-s * math.pi / 2, 0, 0), parent=w, bevel=False)
        for i in range(6):
            a = 2 * math.pi * (i + 0.5) / 6
            k.cylinder("lug", 0.012, 0.02, (0.1 * math.cos(a), s * 0.05, 0.1 * math.sin(a)), STEEL,
                       segs=6, rot=(-s * math.pi / 2, 0, 0), parent=w, bevel=False, smooth=False)
    n = 52                                              # tread blocks
    for i in range(n):
        a = 2 * math.pi * i / n
        k.box("tread", (0.016, 0.15, 0.022), (0.43 * math.cos(a), 0, 0.43 * math.sin(a)), "rubber",
              rot=(0, -a, 0.3 if i % 2 else -0.3), parent=w, bevel=False)


def _carriage(k, t):
    for sx in (-1, 1):
        _wheel(k, t, Vector((sx * 0.72, 0, 0.43)))
    k.tube("axle", (-0.66, 0, 0.43), (0.66, 0, 0.43), 0.045, G, parent=t)
    k.box("lower", (0.5, 0.56, 0.2), (0, -0.05, 0.5), G, parent=t, bevel=0.012)
    k.cylinder("pintle", 0.2, 0.06, (0, -0.1, 0.6), STEEL, segs=28, parent=t)
    cheek = [(-0.5, 0.64), (0.25, 0.64), (0.25, 0.8), (0.02, 0.97), (-0.22, 0.97), (-0.5, 0.82)]
    for sx in (-1, 1):
        k.plate("cheek", cheek, 0.03, sx * 0.17, G, parent=t, bevel=0.006)
        k.cylinder("trunnion_cap", 0.06, 0.04, (sx * 0.185, -0.1, 0.87), STEEL, segs=18,
                   rot=(0, sx * math.pi / 2, 0), parent=t)
        _bolts(k, [(sx * 0.187, y, 0.69) for y in (-0.42, -0.2, 0.02, 0.18)], (sx, 0, 0), t, r=0.012, mat=G)
        # spring equilibrator column
        k.tube("equil", (sx * 0.26, 0.12, 0.56), (sx * 0.26, 0.3, 1.0), 0.05, G, parent=t, segs=16)
        k.tube("equil_cap", (sx * 0.26, 0.3, 1.0), (sx * 0.26, 0.31, 1.03), 0.035, STEEL, parent=t, segs=12)

        # --- split tubular trail with spade
        a, b = Vector((sx * 0.26, -0.3, 0.52)), Vector((sx * 1.38, -3.2, 0.17))
        d = (b - a).normalized()
        side = Vector((sx * d.y, -sx * d.x, 0)).normalized()
        k.tube("hinge", (a.x, a.y, 0.4), (a.x, a.y, 0.64), 0.085, G, parent=t, segs=18)
        k.tube("trail", a, b, 0.066, G, radius_end=0.058, parent=t, segs=18, bevel=False)
        for f in (0.2, 0.55, 0.86):                         # riveted joint bands
            p = a.lerp(b, f)
            k.tube("band", p - d * 0.035, p + d * 0.035, 0.072, WORN, parent=t, segs=18, bevel=False)
        for f in (0.7, 0.9):                                # lifting handles
            p = a.lerp(b, f) + Vector((0, 0, 0.06))
            q = p + d * 0.2
            k.tube("h1", p, p + Vector((0, 0, 0.09)), 0.011, STEEL, parent=t, segs=8, bevel=False)
            k.tube("h2", q, q + Vector((0, 0, 0.09)), 0.011, STEEL, parent=t, segs=8, bevel=False)
            k.tube("h3", p + Vector((0, 0, 0.09)), q + Vector((0, 0, 0.09)), 0.011, STEEL, parent=t,
                   segs=8, bevel=False)
        sp = b + d * 0.12
        yaw = math.atan2(-d.x, d.y)
        k.box("spade", (0.4, 0.03, 0.42), (sp.x, sp.y, 0.06), WORN, rot=(math.radians(-25), 0, yaw),
              parent=t, bevel=0.006)
        k.box("spade_top", (0.4, 0.16, 0.025), (sp.x - d.x * 0.03, sp.y - d.y * 0.03, 0.26), WORN,
              rot=(math.radians(-25), 0, yaw), parent=t)
        for s2 in (-1, 1):
            k.beam("spade_web", b - d * 0.25 + side * s2 * 0.03, sp + side * s2 * 0.16 + Vector((0, 0, -0.1)),
                   (0.02, 0.1), WORN, parent=t, bevel=False)
        if sx < 0:      # towing eye on the left trail, cleaning rod sections on the right
            k.torus("lunette", 0.06, 0.02, b + d * 0.3 + Vector((0, 0, 0.06)), STEEL, parent=t,
                    segs=20, tube_segs=8)
            k.tube("lunette_arm", b, b + d * 0.25 + Vector((0, 0, 0.06)), 0.03, STEEL, parent=t, segs=10)
        else:
            for off in (-0.035, 0.035):
                k.tube("rod", a.lerp(b, 0.12) + Vector((0, 0, 0.085)) + side * off,
                       a.lerp(b, 0.62) + Vector((0, 0, 0.08)) + side * off, 0.014, "wood", parent=t,
                       segs=8, bevel=False)
            for f in (0.15, 0.58):
                p = a.lerp(b, f) + Vector((0, 0, 0.075))
                k.box("rod_clip", (0.12, 0.03, 0.03), p, STEEL, rot=(0, 0, yaw), parent=t, bevel=False)

    # elevation and traverse handwheels, both on the gunner's (left) side
    for y, z, r in ((-0.42, 0.9, 0.11), (-0.64, 0.74, 0.1)):
        k.torus("handwheel", r, 0.012, (-0.34, y, z), STEEL, rot=(0, math.pi / 2, 0), parent=t,
                segs=24, tube_segs=8)
        k.tube("hw_shaft", (-0.19, y, z), (-0.35, y, z), 0.016, STEEL, parent=t, segs=8)
        for a in (0, 2.1, 4.2):
            k.tube("hw_spoke", (-0.34, y, z), (-0.34, y + r * math.cos(a), z + r * math.sin(a)),
                   0.007, STEEL, parent=t, segs=6, bevel=False)
    k.box("gearbox", (0.1, 0.3, 0.16), (-0.24, -0.5, 0.78), G, parent=t, bevel=0.01)


def _shield(k, t, level):
    """Angular shield, leaning back 10 deg; hinged flap below the axle line."""
    sh = k.empty("shield", (0, 0.3, 0.47), parent=t)
    sh.rotation_euler = (math.radians(10), 0, 0)
    th = 0.012
    for sx in (-1, 1):
        panel = [(sx * 0.80, 0.0), (sx * 0.15, 0.0), (sx * 0.15, 0.80), (sx * 0.15, 0.93),
                 (sx * 0.60, 0.93), (sx * 0.80, 0.72)]
        k.prism("shield_panel", panel, th, G, parent=sh, bevel=False)
        # stiffening angle along the edge of the slot + rivets
        k.box("slot_edge", (0.03, 0.03, 0.8), (sx * 0.165, -0.02, 0.4), G, parent=sh, bevel=False)
        _bolts(k, [(sx * x, th / 2, z) for x, z in ((0.76, 0.06), (0.76, 0.36), (0.76, 0.64), (0.2, 0.1),
                                                     (0.2, 0.45), (0.2, 0.86), (0.48, 0.89), (0.5, 0.05))],
               (0, 1, 0), sh, r=0.012, mat=G)
        # stay from the shield back to the carriage
        k.tube("stay", (sx * 0.5, -0.01, 0.6), (sx * 0.18, -0.52, 0.34), 0.014, G, parent=sh, segs=8,
               bevel=False)
    k.prism("shield_bridge", [(-0.15, 0.80), (0.15, 0.80), (0.15, 0.93), (-0.15, 0.93)], th, G, parent=sh,
            bevel=False)
    top = k.empty("shield_top", (0, 0, 0.93), parent=sh)                # upper strip, folded back
    top.rotation_euler = (math.radians(28), 0, 0)
    k.prism("shield_top", [(-0.60, 0.0), (0.60, 0.0), (0.54, 0.13), (-0.54, 0.13)], th, G, parent=top,
            bevel=False)
    # sight port with its flap, on the gunner's side
    k.box("port_frame", (0.2, 0.012, 0.16), (-0.42, 0.012, 0.66), WORN, parent=sh, bevel=False)
    k.box("port", (0.14, 0.004, 0.1), (-0.42, 0.02, 0.66), "bore", parent=sh, bevel=False)
    flap = k.box("port_flap", (0.2, 0.01, 0.16), (-0.42, 0.06, 0.8), G, parent=sh, bevel=False)
    flap.rotation_euler = (math.radians(-55), 0, 0)
    # lower flap between the wheels, swung down
    k.box("lower_flap", (1.0, th, 0.27), (0, 0.3, 0.33), WORN, parent=t, bevel=False)
    for x in (-0.4, 0.0, 0.4):
        k.cylinder("flap_hinge", 0.012, 0.08, (x - 0.04, 0.3, 0.468), STEEL, segs=8,
                   rot=(0, math.pi / 2, 0), parent=t, bevel=False)
    fort.decal(k, "decal_zis_no", "Б-103", sh, centre=(0.47, th / 2 + 0.002, 0.42), u=(-1, 0, 0),
               v=(0, 0, 1), height=0.11)

    if level >= 3:      # appliqué armour on spacers + folding side wings
        for sx in (-1, 1):
            plate = [(sx * 0.77, 0.05), (sx * 0.2, 0.05), (sx * 0.2, 0.86), (sx * 0.58, 0.86),
                     (sx * 0.77, 0.67)]
            k.prism("applique", plate, 0.016, "steel_worn" if sx > 0 else WORN, y=0.05, parent=sh,
                    bevel=False)
            _bolts(k, [(sx * x, 0.058, z) for x, z in ((0.7, 0.12), (0.7, 0.6), (0.27, 0.12), (0.27, 0.78),
                                                        (0.5, 0.8), (0.48, 0.42))],
                   (0, 1, 0), sh, r=0.018, mat=STEEL)
            wing = k.empty("wing", (sx * 0.8, 0, 0.0), parent=sh)
            wing.rotation_euler = (0, 0, -sx * math.radians(38))
            k.prism("wing_plate", [(0.0, 0.02), (sx * 0.34, 0.02), (sx * 0.34, 0.56), (0.0, 0.7)], th, WORN,
                    parent=wing, bevel=False)
            for z in (0.12, 0.4, 0.62):
                k.cylinder("wing_hinge", 0.014, 0.07, (0, 0, z - 0.035), STEEL, segs=8, parent=wing,
                           bevel=False)


def _elevating_mass(k, t, level):
    piv = k.empty("elevating", TRUNNION, parent=t)
    piv["node"] = "elevating"
    piv.rotation_euler = (math.radians(ELEVATION_DEG), 0, 0)
    rec = k.empty("recoil", parent=piv)
    rec["node"] = "recoil"

    k.tube("trunnion", (-0.17, 0, 0), (0.17, 0, 0), 0.05, STEEL, parent=piv)
    # trough cradle with the recoil brake under the barrel, recuperator above it
    k.box("cradle", (0.21, 1.55, 0.15), (0, 0.3, -0.14), G, parent=piv, bevel=0.01)
    k.tube("brake_cyl", (0, -0.42, -0.19), (0, 1.12, -0.19), 0.068, G, parent=piv, segs=18)
    k.tube("brake_cap", (0, 1.12, -0.19), (0, 1.17, -0.19), 0.045, STEEL, parent=piv, segs=8)
    k.tube("recup", (0, -0.3, 0.16), (0, 1.32, 0.16), 0.07, G, parent=piv, segs=20)
    k.tube("recup_cap", (0, 1.32, 0.16), (0, 1.37, 0.16), 0.05, STEEL, parent=piv, segs=8)
    for y in (-0.22, 0.98):
        k.box("yoke", (0.25, 0.07, 0.46), (0, y, 0.0), G, parent=piv, bevel=0.01)
        _bolts(k, [(x, y + 0.036, z) for x in (-0.09, 0.09) for z in (-0.18, 0.18)], (0, 1, 0), piv,
               r=0.012, mat=G)
    for sx in (-1, 1):
        _bolts(k, [(sx * 0.106, y, -0.12) for y in (-0.3, 0.1, 0.5, 0.85)], (sx, 0, 0), piv, r=0.011, mat=G)

    # --- barrel with the double-baffle brake
    barrel = [(-0.62, 0.0), (-0.62, 0.088), (0.15, 0.088), (0.32, 0.074), (0.9, 0.062),
              (2.72, 0.05), (2.72, 0.0)]
    k.lathe("barrel", barrel, BARREL, segs=32, parent=rec)
    for i in range(level):                                  # crimson rings: one per level
        y0, y1 = 2.0 - i * 0.14, 2.07 - i * 0.14
        r = 0.062 + (0.05 - 0.062) * ((y0 + y1) / 2 - 0.9) / 1.82 + 0.0025
        k.lathe("ring", [(y0, 0.0), (y0, r), (y1, r), (y1, 0.0)], "paint_red", segs=32, parent=rec)
    k.lathe("brake", [(2.68, 0.0), (2.68, 0.056), (2.74, 0.086), (3.0, 0.086), (3.03, 0.062),
                      (3.03, 0.0)], SOOT, segs=28, parent=rec)
    for sx in (-1, 1):
        for y in (2.8, 2.93):
            k.box("brake_port", (0.012, 0.085, 0.085), (sx * 0.083, y, 0), "bore", parent=rec, bevel=False)
    k.cylinder("bore", 0.04, 0.008, (0, 3.031, 0), "bore", segs=20, rot=(-math.pi / 2, 0, 0),
               parent=rec, bevel=False)
    muzzle = k.empty("muzzle", (0, 3.05, 0), parent=rec)
    muzzle["marker"] = "muzzle"

    # --- breech ring with a vertical sliding block, lever on the right
    k.box("breech_ring", (0.27, 0.3, 0.3), (0, -0.74, 0), WORN, parent=rec, bevel=0.015)
    k.box("breech_block", (0.13, 0.1, 0.2), (0, -0.87, -0.02), STEEL, parent=rec, bevel=0.008)
    k.tube("lever", (0.15, -0.72, 0.02), (0.22, -0.92, 0.14), 0.012, STEEL, parent=rec, segs=8)
    k.cylinder("lever_knob", 0.02, 0.05, (0.22, -0.92, 0.12), "rubber", segs=10, parent=rec)
    k.box("guard", (0.02, 0.5, 0.2), (0.15, -0.95, -0.06), G, parent=piv, bevel=False)    # recoil guard

    # --- panoramic sight on the left of the cradle
    k.box("sight_mount", (0.07, 0.16, 0.2), (-0.16, -0.28, 0.02), G, parent=piv)
    k.tube("sight_stem", (-0.2, -0.28, 0.1), (-0.2, -0.28, 0.42), 0.022, STEEL, parent=piv, segs=12)
    k.box("sight_head", (0.06, 0.08, 0.07), (-0.2, -0.28, 0.45), STEEL, parent=piv)
    k.cylinder("sight_lens", 0.02, 0.004, (-0.2, -0.239, 0.45), "glass", segs=12,
               rot=(-math.pi / 2, 0, 0), parent=piv, bevel=False)
    k.box("sight_box", (0.1, 0.12, 0.1), (-0.2, -0.36, 0.14), G, parent=piv)


# --------------------------------------------------------------------------
def _round76(k, parent, loc, rot):
    """76 mm unitary round, 0.72 m long. Local +Y = nose."""
    e = k.empty("round76", loc, parent=parent)
    e.rotation_euler = rot
    k.lathe("case", [(0.0, 0.0), (0.0, 0.05), (0.012, 0.05), (0.014, 0.045), (0.33, 0.043),
                     (0.385, 0.0392), (0.385, 0.0)], "brass", segs=20, parent=e)
    k.lathe("shell76", [(0.385, 0.0), (0.385, 0.0385), (0.6, 0.0385), (0.69, 0.02), (0.69, 0.0)],
            "paint_shell", segs=20, parent=e)
    k.lathe("band76", [(0.4, 0.0), (0.4, 0.04), (0.42, 0.04), (0.42, 0.0)], "copper", segs=20, parent=e)
    k.lathe("fuze76", [(0.69, 0.0), (0.69, 0.02), (0.72, 0.008), (0.722, 0.0)], "steel_worn", segs=14,
            parent=e)
    return e


def _spent_case(k, parent, loc, yaw, roll=0.0):
    e = k.empty("spent_case", loc, parent=parent)
    e.rotation_euler = (0, roll, yaw)
    k.lathe("case", [(0.0, 0.0), (0.0, 0.05), (0.012, 0.05), (0.014, 0.045), (0.33, 0.043),
                     (0.385, 0.0392), (0.385, 0.034), (0.02, 0.036), (0.02, 0.0)], "brass", segs=18,
            parent=e)


def _props(k, root, level):
    """Static kit. The ammunition point is on the sunny side toward the camera."""
    crate76 = dict(size=(0.38, 0.86, 0.26), text="76 ОФ  5 БР.", mat="wood", batten="wood",
                   decal_name="decal_crate76")
    r0 = 3.5                        # crates stand between the gun's sweep and the footprint edge
    gz = ground(level).height if level >= 3 else (lambda x, y: 0.0)     # the pit's spoil bank
    stacks = [(-116, 1), (-100, 1)] if level == 1 else [(-130, 3), (-114.5, 3), (-99, 2), (-83.5, 2)]
    for i, (deg, high) in enumerate(stacks):
        for j in range(high):
            p = pol(r0 + 0.02 * (j % 2), deg + (1.0 if j % 2 else 0), 0.26 * j)
            fort.crate(k, root, f"crate_{i}_{j}", p, math.radians(deg) + (0.07 if j % 2 else -0.04),
                       **crate76)
    # ready rounds: a row lying on the first crate, two standing beside it
    deg0, top = stacks[0][0], 0.26 * stacks[0][1]
    for i in range(3):
        p = pol(r0 - 0.1 + 0.1 * i, deg0, top + 0.045)
        _round76(k, root, p - pol(0.36, deg0 + 90), (0, 0, math.radians(deg0)))
    for i, dd in enumerate((-9.5, -7.5)):
        _round76(k, root, pol(r0 + 0.06 * i, deg0 + dd), (math.pi / 2, 0, i * 1.1))
    # spent cases thrown clear to the far left
    rh = {1: 3.4, 2: 3.66, 3: 3.5}[level]
    heap = [(0.0, 172, 25, 0.0), (0.22, 177, -18, 0.0), (0.05, 183, 60, 0.0), (0.3, 168, 5, 0.0),
            (0.16, 188, -40, 0.0)]
    if level >= 2:
        heap += [(0.1, 193, 15, 0.0), (0.28, 181, 80, 0.0), (0.02, 164, -10, 0.0), (0.12, 176, 40, 0.2)]
    for i, (dr, deg, skew, roll) in enumerate(heap):
        c = pol(rh + dr * 0.7, deg)
        c.z = gz(c.x, c.y) + 0.05 + (0.08 if roll else 0.0)
        _spent_case(k, root, c, math.radians(deg + skew), roll)
    # entrenching shovel stuck in the ground, bucket
    a = pol(r0 + 0.28, -139)
    k.tube("shovel_shaft", a + Vector((0, 0, 0.12)), a + Vector((0.08, 0.05, 1.05)), 0.018, "wood",
           parent=root, segs=10)
    k.box("shovel_blade", (0.19, 0.012, 0.26), a + Vector((0, 0, 0.1)), "steel_worn",
          rot=(0.06, 0, 0.9), parent=root, bevel=False)
    b = pol(r0 + 0.25, -74)
    k.cylinder("bucket", 0.11, 0.26, b, "steel_worn", segs=20, parent=root, radius_top=0.14)
    k.torus("bucket_rim", 0.14, 0.008, (b.x, b.y, 0.26), "steel_worn", parent=root, segs=20, tube_segs=6)

    if level == 2:
        r_out, _ = fort.sandbag_wall(k, root, WALL_IN, [(20, 215)], courses=4, seed=8)
        fort.pennant(k, root, pol(r_out - 0.2, 222), height=2.2, yaw=0.5)
    elif level == 3:
        fort.log_wall(k, root, WALL_IN, [(150, 485)], z0=-PIT_DEPTH - 0.08, z1=0.2)
        fort.lean_to_net(k, root, r0 - 0.25, FOOTPRINT_M - 0.03, -133, -80, top_z=2.0, seed=4)
        flag = pol(3.55, 224)
        flag.z = gz(flag.x, flag.y) - 0.05
        fort.pennant(k, root, flag, height=2.25, yaw=0.5)
        # steps cut into the far side of the pit, faced with planks
        for i in range(3):
            p = pol(WALL_IN - 0.25 + 0.3 * i, 137.5, -PIT_DEPTH + 0.18 * (i + 1) - 0.02)
            k.box("step", (0.28, 1.1, 0.04), p, "wood", rot=(0, 0, math.radians(137.5)), parent=root)
