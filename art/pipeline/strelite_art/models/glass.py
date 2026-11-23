"""Дяволско стъкло (game id glass; approved 2026-11-22): a tall natural rock spire, like the
Belogradchik rocks, waisted in the middle and wider (not too wide) at the foot. On top, hands of
stone grow out of the rock and hold the burning glass; at levels 4-5 a crystal instead of a lens.
Mixed in from the three sketches: the devil's horns (idol), runes and floating stones (sanctuary),
rock roots, witch bottles and crystals bursting from the rock (tree).

Look per level (rock / top / extra):
  1  raw red rock / two rock prongs with a green lens lashed between them / rope ladder, charms
  2  red rock with steps cut spiralling up / two rough stone hands holding a clear lens in iron /
     witch bottles from the wrists, painted runes
  3  red rock splitting into root buttresses, glowing cracks and a band of runes / carved hands with
     bronze bracers gripping a spirit lens in a rune rim / small horns on the capital
  4  dark rock with amethyst bursting out / open stone hands with a floating amethyst crystal
     between them / stones circling in the air
  5  pale rock veined with gold / hands with gold bracers holding a crystal cluster before a stone
     ring with golden sun rays / circling stones, golden runes
Round it a ring of standing stones (flagstones from 2, glowing runes from 3, lifted stones at 4-5,
gold binding at 5), and two old mountain guns at its sides with their muzzles dipped to it, as if
bowing: bronze falconet on a block bed, bronze mountain howitzer, iron gun, steel gun with a shield,
gold-trimmed bronze on a red carriage.
The rock is static; the capital, hands and glass on top turn. Front is local +Y.
"""
import math

from mathutils import Matrix, Vector

from .. import materials_photoreal as mp
from ..geo import Kit
from . import _glassbase as G
from ._glasskit import (start, lens_optic, crystal_optic, limb, rock, stele, slab, _glyph, _glyph_ring, _horn, _ball,
                        _lens, rnd_for)
from ._glassbase import (key_fire_animation, set_fire_frame, FIRE, FIRE_FRAMES, RELEASE_FRAME, RELOAD_FROM,  # noqa: F401
                    FIRE_FPS, LOOP, ROT_TY)

LEVELS = (1, 2, 3, 4, 5)
FRAME_M = 10.0
TARGET_Z = 2.6
SPRITE_FRAME_M = 12.0
SPRITE_WH_M = (20.0, 17.0)         # the optical bench stands tall; its shadow runs far
ANCHOR_FROM_BOTTOM_M = 4.6
SWEEP_M = 2.6                      # the mirror boom swings this far out (high above the stones)
FOOTPRINT_M = 3.0
H = {1: 3.0, 2: 3.3, 3: 3.6, 4: 3.9, 5: 4.2}          # rock height
ROCK = {1: "stone_red", 2: "stone_red", 3: "stone_red", 4: "stone_dark", 5: "stone_white"}
EL = -0.65                                           # the glass looks down the road at the enemy


def build(style, level=1):
    k = Kit(style)
    start()
    root = k.empty("glass")
    rnd = rnd_for(90 + level)
    _spire(k, root, level, rnd)
    _sanctuary(k, root, level, rnd)
    for side in (-1, 1):
        _mountain_gun(k, root, level, side)
    G._ammo(k, root, level)
    turret = k.empty("turret", (0, 0, 0), parent=root)
    turret["node"] = "turret"
    mp.set_reference(turret)
    _top(k, turret, level, rnd)
    set_fire_frame(0)
    return root, turret


def ground(level):
    return G.ground(level)


# -- the rock -------------------------------------------------------------------------------------
def _radius(t, level):
    """Waisted profile: wide foot, thin waist a little above the middle, wider top."""
    foot = 0.92 + 0.03 * level
    waist, top = 0.4 + 0.02 * level, 0.86
    w = 0.55
    if t < w:
        r = waist + (foot - waist) * (1 - t / w) ** 2
    else:
        r = waist + (top - waist) * ((t - w) / (1 - w)) ** 1.6
    return r + 0.2 * math.exp(-t * 14)


def _rock_mesh(k, parent, level, rnd, mat, segs=11):
    h = H[level]
    n = int(h / 0.18)
    verts, faces = [], []
    for i in range(n + 1):
        t = i / n
        z = h * t + (rnd.uniform(-0.04, 0.04) if 0 < i < n else 0)
        r = _radius(t, level) * (1.1 if i % 4 == 2 else 1.0)           # ledges of harder rock
        rot = rnd.uniform(-0.05, 0.05)
        ox, oy = 0.07 * math.sin(t * 6 + level), 0.07 * math.cos(t * 5 + 2 * level)   # the rock meanders
        for j in range(segs):
            a = 2 * math.pi * j / segs + rot
            rr = r * (1 + rnd.uniform(-0.13, 0.13))
            verts.append((ox * (0 < i) + rr * math.cos(a), oy * (0 < i) + rr * math.sin(a), z if i else -0.15))
    for i in range(n):
        for j in range(segs):
            a, b = i * segs + j, i * segs + (j + 1) % segs
            faces.append((a, b, b + segs, a + segs))
    faces.append(tuple(reversed(range(segs))))
    faces.append(tuple(n * segs + j for j in range(segs)))
    o = k.mesh("rock_spire", verts, faces)
    return k._finish(o, mat, bevel=False, parent=parent)


def _surface(t, a, level, out=0.0):
    h = H[level]
    r = _radius(t, level) + out
    return Vector((r * math.cos(a), r * math.sin(a), h * t))


def _spire(k, root, level, rnd):
    mat = ROCK[level]
    h = H[level]
    _rock_mesh(k, root, level, rnd, mat)
    for i in range(9):                               # boulders fallen at the foot
        a = 2 * math.pi * i / 9 + rnd.uniform(-0.2, 0.2)
        d = 1.25 + rnd.uniform(0, 0.4)
        if abs((a + 0.7 + math.pi) % (2 * math.pi) - math.pi) < 0.45 or abs(math.cos(a)) > 0.8:
            continue
        rock(k, root, (d * math.cos(a), d * math.sin(a), 0.05), (rnd.uniform(0.12, 0.25),) * 2 + (0.13,), mat, rnd)
    if level >= 3:                                   # the foot splits into root buttresses
        for i in range(5):
            a = 2 * math.pi * i / 5 + 0.4
            d = Vector((math.cos(a), math.sin(a), 0))
            limb(k, root, [d * 0.75 + Vector((0, 0, 1.1)), d * 1.1 + Vector((0, 0, 0.45)),
                           d * 1.45 + Vector((0, 0, 0.05)), d * 1.62 + Vector((0, 0, -0.12))], 0.26, 0.07, mat, segs=7)
    if level == 1:                                   # a rope ladder up the back
        for x in (-0.18, 0.18):
            pts = [_surface(t, -math.pi / 2 + x, level, 0.05) for t in (0.0, 0.3, 0.55, 0.8, 0.98)]
            k.hose("ladder_rope", pts, 0.015, "rope", parent=root)
        for i in range(1, 14):
            t = i / 14
            p0, p1 = _surface(t, -math.pi / 2 - 0.18, level, 0.06), _surface(t, -math.pi / 2 + 0.18, level, 0.06)
            k.tube("rung", p0, p1, 0.02, "timber_raw", parent=root, segs=6, bevel=False)
    if level >= 2:                                   # steps cut spiralling up the rock
        for i in range(22):
            t = 0.05 + 0.9 * i / 22
            a = -math.pi / 2 + 4.6 * i / 22
            p = _surface(t, a, level, 0.12)
            k.box("step", (0.36, 0.2, 0.07), p, mat, rot=(0, 0, a + math.pi / 2), parent=root, bevel=0.015)
    if level == 2:
        for t, a in ((0.3, 1.2), (0.7, 2.0), (0.45, -0.2)):
            e = k.empty("rune_paint", _surface(t, a, level, 0.01), parent=root)
            e.rotation_euler = (0, 0, a + math.pi / 2)
            _glyph(k, e, 0.3, "paint_red", rnd, depth=0.008)
    if level in (3, 4):                              # glowing cracks
        for i in range(10):
            t = rnd.uniform(0.15, 0.9)
            a = rnd.uniform(0, 2 * math.pi)
            p = _surface(t, a, level, -0.01)
            k.beam("crack", p, p + Vector((rnd.uniform(-0.08, 0.08), rnd.uniform(-0.08, 0.08), rnd.uniform(0.25, 0.5))),
                   (0.035, 0.03), "rune_glow", parent=root, bevel=False)
    if level >= 3:                                   # a band of runes round the waist
        glow = {3: "rune_glow", 4: "rune_glow", 5: "rune_gold"}[level]
        for i in range(12):
            a = 2 * math.pi * i / 12
            e = k.empty("rune_slot", _surface(0.55, a, level, -0.005), parent=root)
            e.rotation_euler = (0, 0, a + math.pi / 2)
            _glyph(k, e, 0.17, glow, rnd)
    if level == 4:                                   # amethyst bursting from the rock
        for i in range(12):
            t = rnd.uniform(0.05, 0.85)
            a = rnd.uniform(0, 2 * math.pi)
            p = _surface(t, a, level, -0.1)
            d = Vector((math.cos(a), math.sin(a), rnd.uniform(0.1, 0.9))).normalized()
            G._crystal(k, root, p, d, rnd.uniform(0.3, 0.6), rnd.uniform(0.06, 0.11), "crystal_violet", back=0.1)
    if level == 5:                                   # gold veins and bands
        for i in range(5):
            a0 = 2 * math.pi * i / 5
            pts = [_surface(t, a0 + 0.5 * math.sin(t * 7 + i), level, 0.0) for t in (0.02, 0.2, 0.4, 0.6, 0.8, 0.97)]
            k.hose("gold_vein", pts, 0.022, "gold_trim", parent=root)
        for t in (0.3, 0.55):
            k.torus("gold_band", _radius(t, level) * 1.04, 0.04, (0, 0, H[level] * t), "gold_trim", parent=root,
                    segs=40, tube_segs=6)


# -- the sanctuary round the rock ----------------------------------------------------------------
def _sanctuary(k, root, level, rnd):
    """A ring of standing stones (left open at the two guns and the ammo pile), flagstones from
    level 2, glowing runes from 3, stones lifted into the air at 4-5, gold binding at 5."""
    mat = ROCK[level] if level != 1 else "stone"
    glow = {3: "rune_glow", 4: "rune_glow", 5: "rune_gold"}.get(level)
    n = 14
    for i in range(n):
        a = 2 * math.pi * i / n + 0.1
        if abs(math.cos(a)) > 0.72 or abs((a + 0.7 + math.pi) % (2 * math.pi) - math.pi) < 0.42:
            continue
        ht = rnd.uniform(0.85, 1.3) + 0.12 * (level - 1)
        lift = 0.3 if level >= 4 and i % 2 else 0.0
        p = Vector((2.4 * math.cos(a), 2.4 * math.sin(a), 0))
        stele(k, root, (p.x, p.y, -0.05 + lift), 0.24, 0.16, ht, mat, rnd, yaw=a)
        if lift:
            for j in range(3):                       # grit hanging under the lifted stone
                rock(k, root, (p.x + rnd.uniform(-0.15, 0.15), p.y + rnd.uniform(-0.15, 0.15), rnd.uniform(0.05, 0.25)),
                     (0.04, 0.04, 0.035), mat, rnd)
        if glow:
            e = k.empty("rune_slot", p * 0.93 + Vector((0, 0, 0.55 + lift)), parent=root)
            e.rotation_euler = (0, 0, a + math.pi / 2)
            _glyph(k, e, 0.2, glow, rnd)
        if level == 5:
            k.torus("gold_bind", 0.2, 0.02, (p.x, p.y, ht * 0.7 + lift), "gold_trim", parent=root, segs=20,
                    tube_segs=6)
    if level == 1:                                   # little cairns of offering stones
        for a in (1.2, 2.2, 4.2):
            c = Vector((1.75 * math.cos(a), 1.75 * math.sin(a), 0))
            for j, (dz, r) in enumerate(((0.06, 0.13), (0.17, 0.1), (0.26, 0.07))):
                rock(k, root, c + Vector((0, 0, dz)), (r, r, r * 0.7), "stone", rnd)
    if level >= 2:                                   # flagstones round the foot of the rock
        for i in range(18):
            a = 2 * math.pi * i / 18
            r = 1.45 + 0.25 * (i % 2)
            slab(k, root, (r * math.cos(a), r * math.sin(a), 0.03), (0.28, 0.22, 0.06), "stone_dressed", rnd, yaw=a)


# -- old mountain guns bowing to it ---------------------------------------------------------------
GUN = {   # barrel, carriage, wheel or None, fittings
    1: dict(barrel="bronze_old", cart="timber_raw", wheel=None, fit="iron_forged"),
    2: dict(barrel="bronze_old", cart="timber_tarred", wheel="timber_tarred", fit="iron_forged"),
    3: dict(barrel="iron_forged", cart="timber_oak", wheel="timber_oak", fit="iron_black"),
    4: dict(barrel="gunmetal", cart="paint_olive_worn", wheel="iron_black", fit="steel_worn"),
    5: dict(barrel="bronze_old", cart="timber_red", wheel="timber_red", fit="gold_trim"),
}


def _barrel_profile(level):
    L = {1: 0.85, 2: 0.95, 3: 1.1, 4: 1.3, 5: 1.2}[level]
    r = {1: 0.085, 2: 0.1, 3: 0.09, 4: 0.075, 5: 0.1}[level]
    if level == 4:                                   # a plain modern tube with a recoil block behind
        return [(-0.25, 0.0), (-0.25, r * 1.5), (0.05, r * 1.5), (0.05, r), (L, r * 0.9), (L, 0.0)], L
    prof = [(-0.22, 0.0), (-0.24, r * 0.5), (-0.2, r * 0.75), (-0.16, r * 0.55), (-0.12, r * 1.25),
            (0.15, r * 1.25), (0.17, r * 1.4), (0.21, r * 1.12), (L * 0.6, r * 0.98), (L * 0.62, r * 1.15),
            (L * 0.66, r * 0.95), (L - 0.07, r * 0.92), (L - 0.05, r * 1.3), (L, r * 1.2), (L, 0.0)]
    return prof, L


def _mountain_gun(k, root, level, side):
    g = GUN[level]
    e = k.empty("bowing_gun", (side * 2.0, 0.25, 0), parent=root)
    e.rotation_euler = (0, 0, side * math.pi / 2)     # local +Y faces the rock
    zt = 0.42 if g["wheel"] else 0.3                  # trunnion height
    if g["wheel"]:
        r = 0.4 if level < 4 else 0.38
        k.tube("axle", (-0.42, 0, r), (0.42, 0, r), 0.035, g["fit"], parent=e, segs=10, bevel=False)
        for sx in (-1, 1):
            _wheel_x(k, e, (sx * 0.42, 0, r), r, g["wheel"], g["fit"], level)
        for sx in (-1, 1):                            # trail cheeks running back to the ground
            k.beam("trail", (sx * 0.14, 0.15, zt), (sx * 0.06, -1.05, 0.06), (0.07, 0.14), g["cart"], parent=e)
        k.box("trail_spade", (0.3, 0.06, 0.16), (0, -1.08, 0.06), g["fit"], parent=e, bevel=0.005)
        if level == 4:                                # a small gun shield
            k.box("shield", (0.8, 0.03, 0.55), (0, 0.32, 0.62), g["cart"], rot=(-0.12, 0, 0), parent=e, bevel=0.006)
    else:                                             # level 1: a timber block bed on the ground, no wheels
        k.box("bed", (0.4, 1.0, 0.18), (0, -0.15, 0.09), g["cart"], parent=e, bevel=0.015)
        for sx in (-1, 1):
            k.box("cheek", (0.07, 0.4, 0.26), (sx * 0.17, 0.02, 0.27), g["cart"], parent=e, bevel=0.01)
        k.torus("rope", 0.12, 0.02, (0, -0.45, 0.2), "rope", rot=(0, math.pi / 2, 0), parent=e, segs=14, tube_segs=6)
    b = k.empty("barrel", (0, 0.05, zt + 0.06), parent=e)
    b.rotation_euler = (-0.38, 0, 0)                  # dipped low: the gun bows to the shrine
    prof, L = _barrel_profile(level)
    k.lathe("gun_barrel", prof, g["barrel"], segs=24, parent=b)
    k.tube("trunnion", (-0.17, 0, 0), (0.17, 0, 0), 0.03, g["barrel"], parent=b, segs=10, bevel=False)
    if level == 4:
        for sx in (-1, 1):
            k.tube("recoil", (sx * 0.06, -0.2, -0.1), (sx * 0.06, 0.5, -0.1), 0.035, g["fit"], parent=b, segs=10)
    if level == 5:                                    # gold rings and a gold muzzle crown
        for y in (0.15, L * 0.62, L - 0.05):
            k.torus("gold_ring", 0.13, 0.018, (0, y, 0), "gold_trim", rot=(math.pi / 2, 0, 0), parent=b, segs=24,
                    tube_segs=6)
        for i in range(8):
            a = 2 * math.pi * i / 8
            k.tube("crown_tooth", (0.12 * math.cos(a), L, 0.12 * math.sin(a)),
                   (0.15 * math.cos(a), L + 0.07, 0.15 * math.sin(a)), 0.018, "gold_trim", radius_end=0.003,
                   parent=b, segs=6, bevel=False)
    k.box("garland" if level >= 3 else "offering", (0.1, 0.1, 0.06), (0, 0.55, 0.02), "cloth_oxblood" if level >= 3
          else "clay", parent=e, bevel=0.01)


def _wheel_x(k, parent, c, r, mat, fit, level):
    """A spoked carriage wheel turning about local X."""
    c = Vector(c)
    k.torus("tyre", r, 0.035, c, fit if level != 5 else "iron_black", rot=(0, math.pi / 2, 0), parent=parent, segs=28,
            tube_segs=6)
    k.torus("felloe", r - 0.05, 0.035, c, mat, rot=(0, math.pi / 2, 0), parent=parent, segs=28, tube_segs=6)
    k.cylinder("hub", 0.07, 0.16, c - Vector((0.08, 0, 0)), fit if level == 5 else mat, segs=12,
               rot=(0, math.pi / 2, 0), parent=parent)
    n = 12 if level >= 3 else 10
    for i in range(n):
        a = 2 * math.pi * i / n
        k.beam("spoke", c, c + Vector((0, math.cos(a), math.sin(a))) * (r - 0.05), (0.03, 0.03),
               mat if level != 4 else fit, parent=parent, bevel=False)


# -- the turning top ------------------------------------------------------------------------------
def _hand(k, parent, side, R, mat, bracer=None, open_=False, s=1.0):
    """A stone hand from below gripping a ring of radius R (round the +Y axis) at its side."""
    x = side * (R + 0.2 * s)
    k.box("palm", (0.13 * s, 0.3 * s, 0.42 * s), (x, -0.02, -0.02), mat, rot=(0, side * 0.12, 0), parent=parent,
          bevel=0.03)
    for i, z in enumerate((0.15, 0.05, -0.05, -0.15)):         # fingers curling round the front of the rim
        z *= s
        if open_:
            pts = [(x - side * 0.02, 0.1 * s, z), (x - side * 0.05, 0.26 * s, z * 1.2),
                   (x - side * 0.15 * s, 0.34 * s, z * 1.25)]
        else:
            pts = [(x - side * 0.02, 0.1 * s, z), (side * (R + 0.1 * s), 0.17 * s, z), (side * (R - 0.04), 0.16 * s, z),
                   (side * (R - 0.11 * s), 0.07 * s, z)]
        limb(k, parent, pts, 0.042 * s * (1 - 0.1 * i), 0.03 * s, mat, segs=8)
    thumb = [(x, -0.14 * s, 0.12 * s), (side * (R + 0.08 * s), -0.2 * s, 0.24 * s), (side * (R - 0.05), -0.12 * s, 0.25 * s)]
    limb(k, parent, thumb, 0.05 * s, 0.033 * s, mat, segs=8)
    wrist = Vector((x + side * 0.03, -0.02, -0.25 * s))
    if bracer:
        k.cylinder("bracer", 0.13 * s, 0.16 * s, wrist + Vector((0, 0, -0.08 * s)), bracer, segs=14, parent=parent)
    return wrist


def _ribbed_lens(k, head, R, mat, rim_mat, rim_t, ribs):
    """A real magnifying glass facing +Y: thick in the middle, with rings of thicker glass standing
    proud on its face (as in a lighthouse lens). Returns the y of its front."""
    tc, te, hb = 0.3 * R, 0.06, 0.055 * R
    def base(r):
        return te / 2 + (tc - te) / 2 * (1 - (r / R) ** 2)
    prof, n = [], 90
    for i in range(n + 1):
        r = R * i / n
        rib = hb * (0.5 + 0.5 * math.cos(2 * math.pi * ribs * r / R)) ** 4 if r > R * 0.16 else 0.0
        prof.append((base(r) + rib, r))
    for i in range(n, -1, -1):
        r = R * i / n
        rib = hb * (0.5 + 0.5 * math.cos(2 * math.pi * ribs * r / R)) ** 4 if r > R * 0.16 else 0.0
        prof.append((-base(r) - rib, r))
    k.lathe("lens", prof, mat, segs=56, parent=head)
    k.torus("rim", R + 0.02, rim_t, (0, 0, 0), rim_mat, rot=ROT_TY, parent=head, segs=48, tube_segs=10)
    g = k.cylinder("lens_glow", R * 0.5, 0.01, (0, -0.005, 0), "lamp_glow", segs=28, rot=(-math.pi / 2, 0, 0),
                   parent=head, bevel=False)
    G._RIG["glow"].append((g, tuple(g.scale), 0.0))
    return tc / 2 + 0.05


_AIM = {}
# -- aiming: a heliostat mirror sends the sun down the lens axis, the lens focuses it on the target.
# Physics: a burning lens brings parallel light to a focus on the line through its centre along the
# light, at its focal length; tilting the lens does not steer the light. So the light must already
# travel toward the target when it reaches the lens: the mirror sits behind the lens on the line
# target -> lens, and its normal is the bisector of the sun direction and the lens axis (the law of
# reflection). The lens faces the light for a sharp focus. The sun is scene.sun_vector(), the same
# sun the photoreal sky lights the scene with, fixed on screen (upper left), whatever the aim.
AIM_DIST = 8.0           # m from the gun centre to the drawn focus (a target two tiles out)
TARGET_H = 0.8           # height of the focus: an enemy's body
RAYS = bool(int(__import__("os").environ.get("GLASS_RAYS", "0")))   # draw sun/beam lines (review only)


def _dip(zl):
    return math.atan2(zl - TARGET_H, AIM_DIST)


def _sun():
    from ..scene import sun_vector
    return Vector(sun_vector()).normalized()


def set_aim(yaw):
    """The top stays still (the renderer turns the turret by yaw, the top counter-turns). The optical
    bench (lens on its turning ring, boom, mirror fork) turns to the target; the mirror tilts in its
    fork so the sun is reflected down the lens axis."""
    top = _AIM.get("top")
    if top is None:
        return
    top.rotation_euler = (0, 0, -yaw)                  # top space == world space from here on
    bench = _AIM["bench"]
    bench.rotation_euler = (0, 0, yaw)                 # bench +Y = the target's direction
    f = Vector((-math.sin(yaw), math.cos(yaw), 0))
    L = Vector((0, 0, _AIM["zl"]))
    T = f * AIM_DIST + Vector((0, 0, TARGET_H))
    t = (T - L).normalized()                           # lens axis = the light's way to the target
    s = _sun()
    n = (s + t).normalized()                           # mirror normal: sun in, light out along t
    B = L - t * _AIM["d"]                              # mirror centre, on the axis behind the lens
    a = t.cross(n)
    a = a.normalized() if a.length > 1e-4 else Vector((math.cos(yaw), math.sin(yaw), 0))
    for name, y in (("fork", t), ("mirror", n)):
        o = _AIM.get(name)
        if o is None:
            continue
        m = Matrix((a, y, a.cross(y))).transposed()    # columns: X = trunnion axis, Y = axis / normal
        o.matrix_basis = Matrix.Translation(B) @ m.to_4x4()
    if RAYS and _AIM.get("rays"):
        for o, p0, p1 in zip(_AIM["rays"], (B + s * 5.0, B, L), (B, L, T)):
            d = p1 - p0
            o.matrix_basis = (Matrix.Translation(p0) @ d.to_track_quat("Y", "Z").to_matrix().to_4x4()
                              @ Matrix.Diagonal((1, d.length, 1, 1)))
        _AIM["spot"].location = Vector((T.x, T.y, 0.03))
    _AIM["normal"] = (L, t, B, n, s, T)


def _mirror(k, top, bench, level, R, Rm, d, t, u):
    """The heliostat: a round mirror on trunnions in a fork that turns round the lens axis. Lens levels:
    the fork's stem is carried by a boom from the lens rim, outside the light. Crystal levels: the
    mirror floats like the stones."""
    rim = {1: "timber_raw", 2: "iron_black", 3: "bronze_old", 4: "iron_black", 5: "gold_trim"}[level]
    face = "mirror_bronze" if level == 1 else "mirror_silver"
    mirror = k.empty("mirror", (0, 0, 0), parent=top)
    k.cylinder("mirror_back", Rm, 0.05, (0, -0.06, 0), rim, segs=40, rot=(-math.pi / 2, 0, 0), parent=mirror)
    k.cylinder("mirror_face", Rm * 0.93, 0.02, (0, -0.012, 0), face, segs=40, rot=(-math.pi / 2, 0, 0),
               parent=mirror, bevel=False)
    k.torus("mirror_rim", Rm, 0.035, (0, -0.01, 0), rim, rot=ROT_TY, parent=mirror, segs=40, tube_segs=8)
    _AIM["mirror"] = mirror
    if level >= 4:                                     # floating: a few runes on its back, no fork
        for j in range(6):
            b = 2 * math.pi * j / 6
            e = k.empty("rune_slot", (0.7 * Rm * math.cos(b), -0.09, 0.7 * Rm * math.sin(b)), parent=mirror)
            e.rotation_euler = (math.pi / 2, 0, 0)
            _glyph(k, e, 0.06, "rune_gold" if level == 5 else "rune_glow", rnd_for(7 + j))
        return
    for sx in (-1, 1):                                 # trunnion pins on the rim
        k.tube("trunnion", (sx * Rm, -0.01, 0), (sx * (Rm + 0.11), -0.01, 0), 0.03, rim, parent=mirror, segs=10)
    fork = k.empty("fork", (0, 0, 0), parent=top)
    _AIM["fork"] = fork
    w, back = Rm + 0.11, Rm + 0.18
    arm = {1: "timber_raw", 2: "iron_black", 3: "bronze_old"}[level]
    r = {1: 0.045, 2: 0.035, 3: 0.04}[level]
    k.tube("fork_base", (-w, -back, 0), (w, -back, 0), r, arm, parent=fork, segs=10)
    for sx in (-1, 1):
        k.tube("fork_arm", (sx * w, -back, 0), (sx * w, 0.0, 0), r, arm, parent=fork, segs=10)
        k.cylinder("fork_eye", r * 1.6, 0.06, (sx * (w - 0.03), -0.01, 0), arm, segs=12,
                   rot=(0, math.pi / 2, 0), parent=fork)
    k.cylinder("fork_hub", 0.09, 0.08, (0, -back - 0.08, 0), arm, segs=14, rot=(-math.pi / 2, 0, 0), parent=fork)
    # boom on the bench: rim top -> back along the axis, outside the light -> down to the fork's stem
    Rb = R + 0.2
    S = -t * (d + back + 0.3)
    pts = [u * (R + 0.03), u * Rb, u * Rb - t * (d + back + 0.3), S]
    for p0, p1 in zip(pts, pts[1:]):
        k.tube("boom", p0, p1, r * 1.3, arm, parent=bench, segs=10)
    for p in pts[1:-1]:
        _ball(k, bench, p, r * 1.5, arm, subdiv=2)
    k.tube("stem", S, -t * (d + back + 0.08), 0.06, "iron_black" if level > 1 else "timber_raw", parent=bench,
           segs=12)
    if level == 1:                                     # rope lashings at the boom's joints
        for p in pts[1:]:
            k.torus("lashing", r * 1.6, 0.018, p, "rope", parent=bench, segs=12, tube_segs=6)


def _top(k, turret, level, rnd):
    _AIM.clear()
    top = k.empty("top", (0, 0, 0), parent=turret)     # stands still: set_aim counter-turns it
    mat = ROCK[level]
    h = H[level]
    k.cylinder("capital", 0.9, 0.24, (0, 0, h - 0.04), mat, segs=11, radius_top=1.0, parent=top, bevel=0.03)
    if level <= 3:
        R = {1: 0.7, 2: 1.1, 3: 1.2}[level]
        zr = h + 0.75 + 0.15 * level                 # the ring in the hands
    else:
        R = 0.5
        zr = h + 1.2
    Ro = R + 0.3                                     # the fixed ring the hands hold
    zl = zr
    for _ in range(4):                               # lens levels: the lens stands in a yoke on the turning
        dip = _dip(zl)                               # ring, its lower rim clear of it
        zl = zr + (R * math.cos(dip) + 0.14 if level <= 3 else 0.9)   # crystal: floats above the palms
    dip = _dip(zl)
    t = Vector((0, math.cos(dip), -math.sin(dip)))   # bench space: lens axis to the target
    u = Vector((0, math.sin(dip), math.cos(dip)))    # the lens face's up
    Rm = {1: 0.55, 2: 0.8, 3: 0.88, 4: 0.5, 5: 0.55}[level]
    d = Rm + 0.4 if level <= 3 else 0.42 + Rm + 0.3  # lens centre -> mirror centre, clear of the lens
    bench = k.empty("bench", (0, 0, zl), parent=top)  # the optical bench: turns to the target
    zb = zr - zl                                     # the ring plane in bench space
    head = k.empty("head", (0, 0, 0), parent=bench)
    head["node"] = "elevating"
    head.rotation_euler = (-dip, 0, 0)               # head +Y = t
    _AIM.update(top=top, bench=bench, head=head, crystal=level >= 4, zl=zl, d=d)
    ring_mat = {1: "timber_raw", 2: "iron_black", 3: "bronze_old"}.get(level)
    if level <= 3:                                   # fixed ring in the hands; a turning ring inside it
        k.torus("holder_ring", Ro, 0.06 + 0.01 * level, (0, 0, zr), ring_mat, parent=top, segs=56, tube_segs=10)
        # the turning ring runs inside the held ring, rim on rim
        k.torus("turn_ring", R + 0.17, 0.045, (0, 0, zb), ring_mat, parent=bench, segs=56, tube_segs=8)
        yr = 0.045
        for sx in (-1, 1):                           # a yoke on the turning ring; the lens tilts on its pins
            k.tube("yoke", (sx * (R + 0.15), 0, zb), (sx * (R + 0.15), 0, 0.0), yr, ring_mat, parent=bench,
                   segs=10)
            _ball(k, bench, (sx * (R + 0.15), 0, 0), yr * 1.4, ring_mat, subdiv=2)
            k.tube("tilt_pin", (sx * (R + 0.03), 0, 0), (sx * (R + 0.15), 0, 0), 0.03, ring_mat, parent=bench,
                   segs=10)
    grip = k.empty("grip", (0, 0, zr), parent=top)    # hand space: the held ring lies flat
    grip.rotation_euler = (-math.pi / 2, 0, 0)
    GR = Matrix.Rotation(-math.pi / 2, 3, "X")
    if level == 1:                                   # two rock prongs with the ring lashed between them
        for sx in (-1, 1):
            base = Vector((sx * 0.4, 0, h + 0.1))
            limb(k, top, [base, Vector((sx * (Ro + 0.12), 0, zr - 0.35)), Vector((sx * (Ro + 0.05), 0, zr)),
                          Vector((sx * (Ro + 0.1), 0.02, zr + 0.14))], 0.17, 0.05, mat, segs=7)
            k.torus("lashing", 0.12, 0.025, (sx * Ro, 0, zr), "rope", rot=(0, math.pi / 2, 0), parent=top,
                    segs=14, tube_segs=6)
        for sx in (-1, 1):                           # charms hung from the prongs
            p = Vector((sx * (Ro + 0.15), 0.05, zr - 0.25))
            k.tube("cord", p, p + Vector((0, 0, -0.45)), 0.008, "rope", parent=top, segs=5, bevel=False)
            k.cylinder("charm", 0.07, 0.02, p + Vector((0, 0, -0.52)), "clay", segs=12, rot=(math.pi / 2, 0, 0),
                       parent=top, bevel=False)
    else:
        bracer = {2: "iron_black", 3: "bronze_old", 4: "iron_black", 5: "gold_trim"}[level]
        sc = {2: 1.9, 3: 2.0, 4: 1.6, 5: 1.65}[level]
        Rg = Ro if level <= 3 else 0.72
        for sx in (-1, 1):
            wrist = _hand(k, grip, sx, Rg, mat, bracer if level >= 3 else None, open_=level >= 4, s=sc)
            ww = Vector((0, 0, zr)) + GR @ wrist
            elbow = Vector((sx * (Rg * 0.8 + 0.5), ww.y - 0.15, (ww.z + h) / 2 - 0.1))
            foot = Vector((sx * 0.45, 0.0, h + 0.1))
            limb(k, top, [ww, elbow, foot], 0.12 * sc, 0.17 * sc, mat, segs=9)
            if level == 2:                           # witch bottles from the wrists
                p = ww + Vector((sx * 0.15, 0.05, 0.0))
                k.tube("cord", p, p + Vector((0, 0, -0.42)), 0.008, "rope", parent=top, segs=5, bevel=False)
                _ball(k, top, p + Vector((0, 0, -0.52)), 0.08, "glass_green", subdiv=2)
                k.tube("neck", p + Vector((0, 0, -0.46)), p + Vector((0, 0, -0.38)), 0.022, "glass_green",
                       parent=top, segs=8, bevel=False)
    if level == 3:                                   # little horns on the capital
        for sx in (-1, 1):
            _horn(k, top, (sx * 0.55, 0.45, h + 0.15), sx, 0.45, 0.07, "bronze_old", curl=0.8)
    if level <= 3:
        tip = _ribbed_lens(k, head, R, {1: "glass_green", 2: "glass_clear", 3: "glass_spirit"}[level],
                           ring_mat, 0.05 + 0.02 * (level > 1), {1: 3, 2: 5, 3: 6}[level])
        if level == 3:
            _glyph_ring(k, head, R + 0.02, -0.06, 14, "rune_glow", 3, size=0.07)
    else:
        mat_c = "crystal_violet" if level == 4 else "crystal"
        tip = crystal_optic(k, head, 1.4 if level == 4 else 1.5, 0.33 if level == 4 else 0.34, mat_c, back=0.42).y
        if level == 5:
            for i in range(6):
                a = 2 * math.pi * i / 6 + 0.3
                d = Vector((math.cos(a) * 0.32, 0.9, math.sin(a) * 0.32)).normalized()
                G._crystal(k, head, (math.cos(a) * 0.26, -0.2, math.sin(a) * 0.26), d, 0.75, 0.1, "crystal", back=0.3)
            ring = k.empty("halo", (0, 0, zr - 0.15), parent=top)          # a flat stone crown with golden rays
            k.torus("stone_ring", 1.05, 0.11, (0, 0, 0), mat, parent=ring, segs=40, tube_segs=8)
            for j in range(16):
                b = 2 * math.pi * j / 16
                L = 0.4 if j % 2 else 0.24
                k.box("sun_ray", (L, 0.05, 0.04), ((1.18 + L / 2) * math.cos(b), (1.18 + L / 2) * math.sin(b), 0),
                      "gold_trim", rot=(0, 0, b), parent=ring, bevel=False)
            for j in range(16):
                b = 2 * math.pi * j / 16
                e = k.empty("rune_slot", (1.05 * math.cos(b), 1.05 * math.sin(b), 0.115), parent=ring)
                e.rotation_euler = (math.pi / 2, 0, b + math.pi / 2)
                _glyph(k, e, 0.08, "rune_gold", rnd)
        for i in range(6):                           # stones circling in the air
            a = 2 * math.pi * i / 6 + 0.2
            c = (1.35 * math.cos(a), 1.35 * math.sin(a), zr - 0.5 + 0.3 * math.sin(3 * a))
            rock(k, top, c, (0.17, 0.14, 0.12), mat, rnd)
    _mirror(k, top, bench, level, R, Rm, d, t, u)
    if RAYS:                                         # review only: sun -> mirror -> lens -> target
        _AIM["rays"] = [k.tube("ray", (0, 0, 0), (0, 0, 1), 0.035, "lamp_glow", parent=top, segs=8,
                               bevel=False) for _ in range(3)]
        for o in _AIM["rays"]:                       # unit tube along +Y for set_aim to place
            o.data.transform(Matrix.Rotation(-math.pi / 2, 4, "X"))
        _AIM["spot"] = k.cylinder("focus_spot", 0.35, 0.02, (0, 0, 0), "lamp_glow", segs=24, parent=top,
                                  bevel=False)
    m = k.empty("muzzle", (0, tip, 0), parent=head)
    m["marker"] = "muzzle"
    set_aim(-math.pi / 2)
