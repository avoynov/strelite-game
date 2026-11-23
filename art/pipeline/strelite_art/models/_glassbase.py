"""Parts box for Дяволско стъкло (models/glass.py): lens and crystal shapes, runes, horns, the
ammo pile, the patch and the firing glow (FIRE, _RIG, set_fire_frame). Its own build() is the first,
rejected tower design and is not rendered.
"""
import math
import random

from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit
from .trebuchet import _ball

LEVELS = (1, 2, 3, 4, 5)
FRAME_M = 9.0
TARGET_Z = 2.0
SPRITE_FRAME_M = 10.5
SWEEP_M = 1.7
FOOTPRINT_M = 3.0        # 2x2 tiles of 4 m

TOP = {1: 2.0, 2: 2.3, 3: 2.5, 4: 2.7, 5: 2.9}       # deck height
LR = {1: 0.72, 2: 0.78, 3: 0.84, 4: 0.95, 5: 1.0}         # lens radius / armillary radius     # lens radius
FW, TW = 1.3, 0.85                                   # tower half width at the foot and at the deck
EL = -0.3                                            # the lens looks a little down the road
ROT_Y = (-math.pi / 2, 0, 0)                         # Kit cylinder (+Z) turned to point along +Y
ROT_TY = (math.pi / 2, 0, 0)                         # Kit torus turned to ring the +Y axis

STYLE = {
    1: dict(lens="glass_green", rim="timber_raw", yoke="timber_raw", fit="rope", mirror="mirror_bronze", horn="horn"),
    2: dict(lens="glass_clear", rim="iron_black", yoke="timber_oak", fit="iron_black", mirror="mirror",
            horn="iron_black"),
    3: dict(lens="glass_spirit", rim="bronze_old", yoke="bronze_old", fit="iron_black", mirror="mirror",
            horn="bronze_old"),
    4: dict(lens="crystal_violet", rim="iron_black", yoke="iron_black", fit="iron_forged", horn="iron_black",
            rune="rune_glow"),
    5: dict(lens="crystal", rim="gold_trim", yoke="gold_trim", fit="gold_trim", horn="gold_trim", rune="rune_gold"),
}

FIRE = [0.7, 1.0, 0.85, 1.0]        # lens glow per frame
FIRE_FRAMES = len(FIRE)
RELEASE_FRAME = 1
RELOAD_FROM = 4
FIRE_FPS = 12
LOOP = True
_RIG = {}


def build(style, level=1):
    k = Kit(style)
    s = STYLE[level]
    _RIG.clear()
    _RIG["glow"] = []
    root = k.empty("glass")
    (_scaffold, _timber_tower, _stone_tower, _dark_tower, _white_tower)[level - 1](k, root, TOP[level])
    _ammo(k, root, level)
    turret = k.empty("turret", (0, 0, 0), parent=root)
    turret["node"] = "turret"
    mp.set_reference(turret)
    _head(k, turret, level, s)
    set_fire_frame(0)
    return root, turret


def ground(level):
    from ..terrain import Patch
    return Patch(r_solid=FOOTPRINT_M, r_out=FOOTPRINT_M + 0.6, r_bare=2.4, seed=91, ragged=0.5)


def _hw(z, top):
    return FW + (TW - FW) * z / top


# -- sorcery ---------------------------------------------------------------------------------------
_STROKES = [((0, -1), (0, 1)), ((-1, -1), (1, 1)), ((-1, 1), (1, -1)), ((-1, 0), (1, 0)), ((0, 1), (1, 0)),
            ((0, 1), (-1, 0)), ((-1, -1), (0, 1)), ((1, -1), (0, 1))]


def _glyph(k, parent, size, mat, rnd, depth=0.012):
    """One rune of 2-3 strokes in the parent's XZ plane (seen from -Y)."""
    for a, b in rnd.sample(_STROKES, rnd.choice((2, 3))):
        p0 = Vector((a[0] * size / 2, 0, a[1] * size / 2))
        p1 = Vector((b[0] * size / 2, 0, b[1] * size / 2))
        k.beam("rune", p0, p1, (size * 0.14, depth), mat, parent=parent, bevel=False)


def _glyph_band(k, root, z, radius_at, n, mat, seed, size=0.2):
    """A ring of runes cut into a round tower at height z, glowing."""
    rnd = random.Random(seed)
    for i in range(n):
        a = 2 * math.pi * i / n
        r = radius_at(z) + 0.004
        e = k.empty("rune_slot", (r * math.cos(a), r * math.sin(a), z), parent=root)
        e.rotation_euler = (0, 0, a + math.pi / 2)
        _glyph(k, e, size, mat, rnd)


def _glyph_ring(k, parent, R, y, n, mat, seed, size=0.07):
    """Runes round a ring that faces +Y (lens rim, armillary)."""
    rnd = random.Random(seed)
    for i in range(n):
        a = 2 * math.pi * i / n
        e = k.empty("rim_rune", (R * math.cos(a), y, R * math.sin(a)), parent=parent)
        e.rotation_euler = (0, -a + math.pi / 2, math.pi)
        _glyph(k, e, size, mat, rnd, depth=0.008)


def _horn(k, parent, base, side, length, r0, mat, curl=1.0):
    """A curved horn: out to the side, up, and its tip turning forward."""
    pts = []
    for i in range(9):
        t = i / 8
        pts.append(Vector(base) + Vector((side * length * 0.75 * math.sin(t * 1.6),
                                          length * (0.35 * curl * t ** 2.2 - 0.18 * t),
                                          length * 0.75 * math.sin(t * 1.35))))
    for i in range(8):
        k.tube("horn", pts[i], pts[i + 1], r0 * (1 - i / 8) + 0.004, mat, radius_end=r0 * (1 - (i + 1) / 8) + 0.002,
               parent=parent, segs=10, bevel=False)
        if i < 7:
            _ball(k, parent, pts[i + 1], r0 * (1 - (i + 1) / 8) + 0.002, mat, subdiv=1)


def _charms(k, root, top):
    """Talismans hung on cords from the deck: clay discs, bone and a ram's skull with horns."""
    rnd = random.Random(7)
    for i, (x, y) in enumerate(((1.0, 0.6), (1.0, -0.4), (-1.0, 0.5), (-1.0, -0.6), (0.4, 1.0), (-0.5, 1.0))):
        L = rnd.uniform(0.35, 0.7)
        k.tube("cord", (x, y, top), (x, y, top - L), 0.008, "rope", parent=root, segs=5, bevel=False)
        if i % 2:
            k.cylinder("charm_disc", 0.08, 0.02, (x, y, top - L - 0.08), "clay", segs=14, rot=(math.pi / 2, 0, 0.6 * i),
                       parent=root, bevel=False)
        else:
            k.tube("charm_bone", (x, y - 0.06, top - L - 0.02), (x, y + 0.06, top - L - 0.12), 0.018, "plaster",
                   parent=root, segs=6)
    c = Vector((0, 1.12, top - 0.25))                # ram's skull on the front
    _ball(k, root, c, 0.13, "plaster", subdiv=2).scale = (0.9, 1.3, 0.85)
    for sx in (-1, 1):
        _horn(k, root, c + Vector((sx * 0.08, 0.02, 0.08)), sx, 0.32, 0.045, "horn", curl=-0.6)


def _pennants(k, root, top):
    for sx in (-1, 1):
        base = Vector((sx * 0.85, -0.85, top + 0.05))
        k.tube("pennant_pole", base, base + Vector((0, 0, 1.7)), 0.03, "timber_oak", parent=root, segs=8)
        f = k.flag("pennant", 0.75, 0.32, base + Vector((0, 0, 1.5)), "cloth_oxblood", parent=root, waves=1.5, amp=0.08)
        f.rotation_euler = (0, 0, math.pi / 2 + sx * 0.5)
        k.cylinder("pennant_finial", 0.04, 0.08, base + Vector((0, 0, 1.7)), "iron_black", segs=8, radius_top=0.002,
                   parent=root, bevel=False)
    rnd = random.Random(3)
    for sx in (-1, 1):                               # painted runes on the posts
        for z in (0.7, 1.5):
            h = _hw(z, top)
            e = k.empty("rune_paint", (sx * (h + 0.105), -h, z), parent=root)
            e.rotation_euler = (0, 0, math.pi / 2)
            _glyph(k, e, 0.16, "paint_red", rnd, depth=0.006)


# -- towers (static) ------------------------------------------------------------------------------
def _ladder(k, root, top, mat, y, rung_mat=None, hoops=False):
    for x in (-0.24, 0.24):
        k.beam("ladder_rail", (x, y - 0.45, 0.0), (x, y, top), (0.06, 0.05), mat, parent=root)
    n = int(top / 0.32)
    for i in range(1, n):
        t = i / n
        k.tube("rung", (-0.24, y - 0.45 * (1 - t), top * t), (0.24, y - 0.45 * (1 - t), top * t), 0.022,
               rung_mat or mat, parent=root, segs=8)
    if hoops:
        for z in (top * 0.55, top * 0.75, top * 0.95):
            t = z / top
            k.torus("ladder_hoop", 0.36, 0.015, (0, y - 0.45 * (1 - t) - 0.25, z), mat, rot=(0, 0, 0), parent=root,
                    segs=20, tube_segs=6)


def _scaffold(k, root, top):
    """Four raked poles lashed with rope, two rings of cross poles, X-braces, a plank deck."""
    for sx in (-1, 1):
        for sy in (-1, 1):
            k.tube("pole", (sx * 1.32, sy * 1.32, -0.1), (sx * 0.8, sy * 0.8, top + 0.2), 0.085, "log",
                   parent=root, segs=12)
    for z in (0.7, 1.4, top - 0.06):
        h = _hw(z, top) + 0.02
        for sx in (-1, 1):
            k.tube("cross_pole", (sx * (h + 0.09), -h - 0.2, z), (sx * (h + 0.09), h + 0.2, z), 0.055, "log",
                   parent=root, segs=10)
            k.tube("cross_pole", (-h - 0.2, sx * (h + 0.09), z + 0.1), (h + 0.2, sx * (h + 0.09), z + 0.1), 0.055,
                   "log", parent=root, segs=10)
            for sy in (-1, 1):                       # rope lashings at the joints
                k.torus("lashing", 0.11, 0.022, (sx * h, sy * h, z + 0.05), "rope", parent=root, segs=14,
                        tube_segs=6)
    for sx in (-1, 1):                               # X-braces on the side faces
        for a, b in ((0.05, 1.4), (1.4, 0.05)):
            ha, hb = _hw(a, top), _hw(b, top)
            k.tube("brace", (sx * (ha + 0.12), -ha, a + 0.05), (sx * (hb + 0.12), hb, b), 0.04, "timber_raw",
                   parent=root, segs=8)
    for i in range(8):                               # plank deck
        x = -0.88 + i * 0.25
        k.box("deck_plank", (0.23, 1.95, 0.05), (x, 0, top + 0.03 + 0.008 * (i % 2)), "timber_raw",
              rot=(0, 0, 0.02 * ((i * 7) % 3 - 1)), parent=root, bevel=0.006)
    _ladder(k, root, top, "timber_raw", -1.25)
    k.torus("rope_coil", 0.22, 0.03, (1.25, 1.55, 0.04), "rope", parent=root, segs=18, tube_segs=6)
    _charms(k, root, top)


def _timber_tower(k, root, top):
    """Square framed tower of sawn timber: corner posts, girts, X-braces, bolted iron plates."""
    for sx in (-1, 1):
        for sy in (-1, 1):
            k.beam("post", (sx * FW, sy * FW, 0), (sx * TW, sy * TW, top), (0.2, 0.2), "timber_tarred", parent=root)
            k.box("footing", (0.42, 0.42, 0.16), (sx * FW, sy * FW, 0.05), "stone", parent=root, bevel=0.02)
    levels = (0.15, top * 0.5, top - 0.1)
    for z in levels:
        h = _hw(z, top)
        for sx in (-1, 1):
            k.box("girt", (0.14, 2 * h + 0.1, 0.18), (sx * h, 0, z), "timber_tarred", parent=root, bevel=0.01)
            k.box("girt", (2 * h + 0.1, 0.14, 0.18), (0, sx * h, z), "timber_tarred", parent=root, bevel=0.01)
            for sy in (-1, 1):
                k.box("bolt_plate", (0.2, 0.2, 0.02), (sx * (h + 0.08), sy * (h - 0.05), z), "iron_black",
                      rot=(0, math.pi / 2, 0), parent=root, bevel=False)
    for (z0, z1) in ((levels[0], levels[1]), (levels[1], levels[2])):
        h0, h1 = _hw(z0, top), _hw(z1, top)
        for sx in (-1, 1):
            for a in (-1, 1):
                k.beam("brace", (sx * (h0 + 0.02), a * h0, z0), (sx * (h1 + 0.02), -a * h1, z1), (0.08, 0.12),
                       "timber_tarred", parent=root)
                k.beam("brace", (a * h0, sx * (h0 + 0.02), z0), (-a * h1, sx * (h1 + 0.02), z1), (0.12, 0.08),
                       "timber_tarred", parent=root)
    for i in range(8):
        x = -0.9 + i * 0.257
        k.box("deck_plank", (0.24, 2.0, 0.06), (x, 0, top + 0.03), "timber_oak", parent=root, bevel=0.006)
    for sx in (-1, 1):
        k.box("deck_edge", (0.1, 2.1, 0.14), (sx * 1.0, 0, top), "timber_tarred", parent=root, bevel=0.008)
    _ladder(k, root, top, "timber_tarred", -1.35)
    _pennants(k, root, top)


def _stone_tower(k, root, top):
    """Round dry-stone tower with coursed bands, corbels and a projecting top slab; a door."""
    k.cylinder("tower", 1.3, top - 0.25, (0, 0, 0), "stone", segs=32, radius_top=1.08, parent=root)
    k.cylinder("plinth", 1.42, 0.35, (0, 0, 0), "stone_dressed", segs=32, radius_top=1.36, parent=root)
    for z in (0.95, 1.65):
        r = 1.3 + (1.08 - 1.3) * z / (top - 0.25)
        k.cylinder("course", r + 0.03, 0.12, (0, 0, z), "stone_dressed", segs=32, parent=root)
    for i in range(16):                              # corbels under the top slab
        a = 2 * math.pi * i / 16
        k.box("corbel", (0.16, 0.3, 0.2), (1.12 * math.cos(a), 1.12 * math.sin(a), top - 0.35), "stone_dressed",
              rot=(0, 0, a + math.pi / 2), parent=root, bevel=0.015)
    k.cylinder("top_slab", 1.28, 0.25, (0, 0, top - 0.25), "stone_dressed", segs=32, parent=root)
    k.box("door", (0.62, 0.1, 1.05), (0, -1.27, 0.88), "timber_oak", parent=root, bevel=0.01)
    for z in (0.6, 1.15):
        k.box("door_band", (0.66, 0.03, 0.06), (0, -1.33, z), "iron_black", parent=root, bevel=False)
    for i in range(7):                               # arch stones over the door
        a = math.pi * i / 6
        k.box("voussoir", (0.16, 0.2, 0.14), (0.38 * math.cos(a), -1.3, 1.42 + 0.3 * math.sin(a)), "stone_dressed",
              rot=(0, -a + math.pi / 2, 0), parent=root, bevel=0.012)
    k.box("slit", (0.08, 0.12, 0.42), (0.95, -0.62, 1.6), "rune_glow", rot=(0, 0, 0.58), parent=root, bevel=False)
    _glyph_band(k, root, 1.3, lambda z: 1.3 + (1.08 - 1.3) * z / (top - 0.25), 22, "rune_glow", 3, size=0.17)


def _dark_tower(k, root, top):
    """Dark stone sorcerer's tower: spiked buttresses, glowing slit windows, a band of runes."""
    k.cylinder("plinth", 1.45, 0.3, (0, 0, 0), "stone_dark", segs=24, radius_top=1.38, parent=root)
    k.cylinder("tower", 1.25, top - 0.3, (0, 0, 0.3), "stone_dark", segs=24, radius_top=0.98, parent=root)
    for i in range(4):                               # buttresses ending in spikes
        a = math.pi / 2 * i + math.pi / 4
        d = Vector((math.cos(a), math.sin(a), 0))
        k.beam("buttress", d * 1.62, d * 1.08 + Vector((0, 0, 1.75)), (0.3, 0.26), "stone_dark",
               section_end=(0.22, 0.16), parent=root)
        tip = d * 1.08 + Vector((0, 0, 1.75))
        k.tube("spike", tip, tip + d * 0.22 + Vector((0, 0, 0.5)), 0.09, "iron_black", radius_end=0.004,
               parent=root, segs=8)
    for i in range(16):                              # corbelled crown
        a = 2 * math.pi * i / 16
        k.box("corbel", (0.14, 0.26, 0.18), (1.0 * math.cos(a), 1.0 * math.sin(a), top - 0.33), "stone_dark",
              rot=(0, 0, a + math.pi / 2), parent=root, bevel=0.012)
    k.cylinder("top_slab", 1.16, 0.24, (0, 0, top - 0.24), "stone_dark", segs=24, parent=root)
    for a in (0.5, 2.1, 3.6, 5.0):                   # glowing slit windows
        r = 1.25 + (0.98 - 1.25) * (1.25 - 0.3) / (top - 0.3)
        k.box("slit", (0.06, 0.1, 0.5), (r * math.cos(a), r * math.sin(a), 1.25), "rune_glow", rot=(0, 0, a),
              parent=root, bevel=False)
    _glyph_band(k, root, 0.66, lambda z: 1.25 + (0.98 - 1.25) * (z - 0.3) / (top - 0.3), 20, "rune_glow", 4)
    k.box("door", (0.6, 0.1, 1.0), (0, -1.24, 0.8), "iron_black", parent=root, bevel=0.01)
    for i in range(9):                               # pointed arch over the door
        a = math.pi * i / 8
        k.box("voussoir", (0.13, 0.18, 0.12), (0.36 * math.cos(a), -1.23, 1.3 + 0.42 * math.sin(a) ** 0.7),
              "stone_dark", rot=(0, -a + math.pi / 2, 0), parent=root, bevel=0.01)


def _white_tower(k, root, top):
    """Octagonal white-stone tower with gold bands, gold sun medallions and a gilded cornice."""
    k.cylinder("plinth", 1.55, 0.32, (0, 0, 0), "stone_dressed", segs=8, radius_top=1.48, parent=root)
    k.cylinder("tower", 1.36, top - 0.32, (0, 0, 0.32), "stone_dressed", segs=8, radius_top=1.14, parent=root)
    for z in (0.32, 1.35, top - 0.42):
        r = 1.36 + (1.14 - 1.36) * (z - 0.32) / (top - 0.32)
        k.cylinder("gold_band", r + 0.025, 0.07, (0, 0, z), "gold_trim", segs=8, parent=root, bevel=0.004)
    k.cylinder("cornice", 1.22, 0.14, (0, 0, top - 0.3), "stone_dressed", segs=8, radius_top=1.34, parent=root)
    k.cylinder("cornice_top", 1.34, 0.16, (0, 0, top - 0.16), "stone_dressed", segs=8, parent=root)
    k.cylinder("cornice_gold", 1.36, 0.04, (0, 0, top - 0.06), "gold_trim", segs=8, parent=root, bevel=0.003)
    for i in range(4):                               # gold sun medallions on four faces
        a = math.pi / 2 * i + math.pi / 8 + math.pi / 4
        a = math.pi / 2 * i
        r = 1.36 + (1.14 - 1.36) * (1.9 - 0.32) / (top - 0.32)
        e = k.empty("face", (0, 0, 0), parent=root)
        e.rotation_euler = (0, 0, a)
        n = math.cos(math.pi / 8) * r
        k.cylinder("sun_disc", 0.2, 0.04, (n, 0, 1.92), "gold_trim", segs=28, rot=(0, math.pi / 2, 0), parent=e)
        for j in range(12):                          # rays
            b = 2 * math.pi * j / 12
            k.box("sun_ray", (0.02, 0.05, 0.14), (n + 0.01, 0.29 * math.cos(b), 1.92 + 0.29 * math.sin(b)),
                  "gold_trim", rot=(b - math.pi / 2, 0, 0), parent=e, bevel=False)
    k.box("door", (0.6, 0.1, 1.1), (0, -1.3, 0.87), "timber_varnish", parent=root, bevel=0.01)
    k.box("door_frame", (0.72, 0.08, 1.2), (0, -1.27, 0.88), "gold_trim", parent=root, bevel=0.006)
    rnd = random.Random(5)
    for i in range(8):                               # golden runes on every face, under the cornice
        a = 2 * math.pi * i / 8 + math.pi / 8
        z = top - 0.62
        r = (1.36 + (1.14 - 1.36) * (z - 0.32) / (top - 0.32)) * math.cos(math.pi / 8) + 0.004
        for j in (-1, 0, 1):
            e = k.empty("rune_slot", (r * math.cos(a) - j * 0.22 * math.sin(a), r * math.sin(a) + j * 0.22 * math.cos(a),
                                      z), parent=root)
            e.rotation_euler = (0, 0, a + math.pi / 2)
            _glyph(k, e, 0.15, "rune_gold", rnd)


# -- turning head ---------------------------------------------------------------------------------
def _lens(k, parent, R, tc, te, mat, segs=40, rings=8, y=0.0):
    """Biconvex lens round the local +Y axis: centre thickness tc, edge thickness te."""
    prof = []
    for i in range(rings + 1):
        r = R * i / rings
        prof.append((y + te / 2 + (tc - te) / 2 * (1 - (r / R) ** 2), r))
    for i in range(rings, -1, -1):
        r = R * i / rings
        prof.append((y - te / 2 - (tc - te) / 2 * (1 - (r / R) ** 2), r))
    return k.lathe("lens", prof, mat, segs=segs, parent=parent)


def _head(k, turret, level, s):
    top, R = TOP[level], LR[level]
    zl = top + R + 0.42
    k.cylinder("turntable", 0.82, 0.08, (0, 0, top + 0.05), {1: "timber_raw", 2: "timber_oak", 3: "bronze_old",
               4: "iron_black", 5: "gold_trim"}[level], segs=36, parent=turret)
    if level >= 3:
        for i in range(12):
            a = 2 * math.pi * i / 12
            _ball(k, turret, (0.74 * math.cos(a), 0.74 * math.sin(a), top + 0.135), 0.02, s["fit"], subdiv=1)
    yx = R + 0.14
    for sx in (-1, 1):                               # yoke cheeks up to the trunnions
        if level == 1:
            k.beam("yoke", (sx * yx, 0, top + 0.1), (sx * yx, 0, zl + 0.08), (0.11, 0.13), s["yoke"], parent=turret)
            k.torus("lashing", 0.09, 0.02, (sx * yx, 0, top + 0.35), "rope", parent=turret, segs=12, tube_segs=6)
        else:
            k.beam("yoke", (sx * (yx + 0.12), 0, top + 0.1), (sx * yx, 0, zl), (0.12, 0.3), s["yoke"],
                   section_end=(0.09, 0.16), parent=turret)
            k.beam("yoke_brace", (sx * (yx + 0.1), -0.25, top + 0.1), (sx * yx, 0, zl - 0.3), (0.06, 0.06),
                   s["yoke"], parent=turret)
        k.tube("trunnion", (sx * (R + 0.02), 0, zl), (sx * (yx + 0.1), 0, zl), 0.045, s["fit"] if level > 1
               else "timber_raw", parent=turret, segs=12)
    if level >= 2:
        k.box("yoke_foot", (2 * yx + 0.3, 0.36, 0.08), (0, 0, top + 0.13), s["yoke"], parent=turret, bevel=0.01)
    head = k.empty("head", (0, 0, zl), parent=turret)
    head["node"] = "elevating"
    head.rotation_euler = (EL, 0, 0)
    if level <= 3:
        tip = _lens_head(k, head, turret, level, s, R, top, zl)
    else:
        tip = _crystal_head(k, head, turret, level, s, R, top, zl)
    m = k.empty("muzzle", (0, tip, 0), parent=head)
    m["marker"] = "muzzle"


def _lens_head(k, head, turret, level, s, R, top, zl):
    tc = {1: 0.16, 2: 0.17, 3: 0.24}[level]
    _lens(k, head, R, tc, 0.05, s["lens"])
    rim_t = {1: 0.06, 2: 0.05, 3: 0.08}[level]
    k.torus("rim", R + 0.02, rim_t, (0, 0, 0), s["rim"], rot=ROT_TY, parent=head, segs=40, tube_segs=10)
    glow = k.cylinder("lens_glow", R * 0.55, 0.01, (0, -0.005, 0), "lamp_glow", segs=28, rot=ROT_Y, parent=head,
                      bevel=False)
    _RIG["glow"].append((glow, tuple(glow.scale), 0.0))
    if level == 1:
        for i in range(6):                           # rope bindings round the wooden ring
            a = 2 * math.pi * i / 6
            k.torus("binding", 0.07, 0.02, ((R + 0.02) * math.cos(a), 0, (R + 0.02) * math.sin(a)), "rope",
                    rot=(0, a, 0), parent=head, segs=12, tube_segs=6)
    if level == 2:                                   # painted runes on the iron rim
        _glyph_ring(k, head, R + 0.02, rim_t + 0.005, 12, "paint_red", 2, size=0.075)
    if level == 3:                                   # glowing runes round the bronze rim, filler cap
        _glyph_ring(k, head, R + 0.02, rim_t + 0.005, 14, "rune_glow", 3, size=0.08)
        k.cylinder("filler", 0.06, 0.12, (0.3, 0, R - 0.02), "bronze_old", segs=14, parent=head)
        k.cylinder("filler_cap", 0.08, 0.04, (0.3, 0, R + 0.1), "bronze_old", segs=14, parent=head)
    for sx in (-1, 1):                               # the devil's horns on top of the rim
        a = math.pi / 2 - sx * 0.42
        _horn(k, head, ((R + 0.02) * math.cos(a), 0, (R + 0.02) * math.sin(a)), sx, 0.3 + 0.06 * level,
              0.045 + 0.006 * level, s["horn"])
    if level >= 2:
        _second_lens(k, head, level, s, R)
    _mirror(k, turret, level, s, top, zl)
    if level == 3:
        _clepsydra(k, turret, top, R)
    return 1.3 if level >= 2 else tc / 2 + 0.05


def _crystal(k, parent, c, axis, L, r, mat, back=0.25):
    """A six-sided crystal along axis: a prism with a long point forward and a short one behind."""
    c, axis = Vector(c), Vector(axis).normalized()
    p0, p1 = c - axis * L * back, c + axis * L * (0.62 - back)
    k.tube("crystal", p0, p1, r, mat, parent=parent, segs=6, bevel=False)
    k.tube("crystal_point", p1, c + axis * L * (1 - back), r, mat, radius_end=0.004, parent=parent, segs=6,
           bevel=False)
    k.tube("crystal_heel", p0, p0 - axis * r * 0.9, r, mat, radius_end=0.004, parent=parent, segs=6, bevel=False)
    return c + axis * L * (1 - back)


def _crystal_head(k, head, turret, level, s, R, top, zl):
    """No lens: a crystal hangs in the middle of armillary rings without touching them."""
    L, r = (1.75, 0.3) if level == 4 else (1.9, 0.33)
    tip = _crystal(k, head, (0, 0, 0), (0, 1, 0), L, r, s["lens"], back=0.42)
    core = _crystal(k, head, (0, 0.05, 0), (0, 1, 0), L * 0.55, r * 0.38, "crystal_core", back=0.45)
    core = [o for o in head.children if o.name.startswith("crystal") and o.data.materials[0].name.startswith(
        "crystal_core")]
    for o in core:
        _RIG["glow"].append((o, tuple(o.scale), 1.0))
    if level == 5:                                   # a cluster: smaller crystals round the main one
        for i in range(6):
            a = 2 * math.pi * i / 6 + 0.3
            d = Vector((math.cos(a) * 0.32, 0.9, math.sin(a) * 0.32)).normalized()
            _crystal(k, head, Vector((math.cos(a) * 0.3, -0.25, math.sin(a) * 0.3)), d, 0.85, 0.12, "crystal",
                     back=0.3)
    ring = s["rim"]
    k.torus("armillary_front", R, 0.035, (0, 0, 0), ring, rot=ROT_TY, parent=head, segs=48, tube_segs=8)
    k.torus("armillary_tilt", R * 0.93, 0.03, (0, 0, 0), ring, rot=(0.5, 0, 0.6), parent=head, segs=48, tube_segs=8)
    k.torus("armillary_side", R * 0.86, 0.03, (0, 0, 0), ring, rot=(0, math.pi / 2, 0), parent=head, segs=48,
            tube_segs=8)
    _glyph_ring(k, head, R, 0.04, 18, s["rune"], 4, size=0.075)
    for sx in (-1, 1):                               # horns on the front ring
        a = math.pi / 2 - sx * 0.42
        _horn(k, head, (R * math.cos(a), 0, R * math.sin(a)), sx, 0.6 if level == 4 else 0.66, 0.07, s["horn"])
    for sx in (-1, 1):                               # ring pivots on the trunnions
        _ball(k, head, (sx * R, 0, 0), 0.07, s["fit"], subdiv=2)
    rnd = random.Random(40 + level)                  # shards circling the head
    for i in range(5 if level == 4 else 7):
        a = 2 * math.pi * i / (5 if level == 4 else 7) + 0.4
        c = Vector(((R + 0.45) * math.cos(a), (R + 0.45) * math.sin(a), zl + rnd.uniform(-0.35, 0.45)))
        d = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(0.3, 1))).normalized()
        _crystal(k, turret, c, d, rnd.uniform(0.22, 0.34), rnd.uniform(0.04, 0.06), s["lens"], back=0.4)
    if level == 5:
        _mirror_crown(k, head, R)
    return L * 0.58 + 0.05


def _second_lens(k, head, level, s, R):
    """A smaller lens held out in front on two rods: it tightens the beam."""
    y, r = 1.15, 0.26 + 0.02 * (level - 2)
    arm = {2: "iron_black", 3: "bronze_old"}[level]
    for sx in (-1, 1):
        k.tube("lens_arm", (sx * (R * 0.72), 0.02, -R * 0.68), (sx * (r + 0.02), y, -0.02), 0.022, arm, parent=head,
               segs=10)
    k.tube("lens_arm", (0, 0.02, R + 0.02), (0, y, r + 0.03), 0.02, arm, parent=head, segs=10)
    _lens(k, head, r, 0.1, 0.03, s["lens"], segs=28, rings=5, y=y)
    k.torus("rim2", r + 0.01, 0.03, (0, y, 0), arm, rot=ROT_TY, parent=head, segs=28, tube_segs=8)


def _mirror(k, turret, level, s, top, zl):
    """A flat mirror behind the lens, tilted up to catch the sun."""
    y0 = -1.05
    zc = top + 1.05
    tilt = 0.75
    if level == 1:                                   # round bronze mirror on a post, a handle to aim it by
        k.beam("mirror_post", (0, y0 - 0.05, top + 0.06), (0, y0, zc - 0.1), (0.08, 0.08), "timber_raw",
               parent=turret)
        m = k.cylinder("mirror", 0.5, 0.03, (0, y0, zc), s["mirror"], segs=32, rot=(tilt - math.pi / 2, 0, 0),
                       parent=turret)
        k.cylinder("mirror_back", 0.52, 0.03, (0, y0 - 0.03, zc - 0.025), "timber_raw", segs=32,
                   rot=(tilt - math.pi / 2, 0, 0), parent=turret)
        k.tube("aim_handle", (0, y0 - 0.1, zc - 0.05), (0.05, y0 - 0.75, zc - 0.55), 0.03, "timber_raw",
               parent=turret, segs=8)
        return m
    w, h = {2: (1.15, 0.95), 3: (1.2, 1.0)}[level]
    frame = {2: "timber_oak", 3: "bronze_old"}[level]
    e = k.empty("mirror_mount", (0, y0, zc), parent=turret)
    e.rotation_euler = (tilt - math.pi / 2 + math.pi / 2, 0, 0)
    k.box("mirror", (w, 0.025, h), (0, 0.015, 0), s["mirror"], parent=e, bevel=0.003)
    for sz in (-1, 1):
        k.box("mirror_frame", (w + 0.1, 0.06, 0.06), (0, 0, sz * (h / 2 + 0.03)), frame, parent=e, bevel=0.005)
        k.box("mirror_frame", (0.06, 0.06, h + 0.06), (sz * (w / 2 + 0.03), 0, 0), frame, parent=e, bevel=0.005)
    for sx in (-1, 1):                               # fork and pivot under the mirror
        k.beam("mirror_fork", (sx * (w / 2 + 0.08), y0 + 0.1, top + 0.1), (sx * (w / 2 + 0.07), y0, zc), (0.06, 0.06),
               frame, parent=turret)
    return e


def _clepsydra(k, turret, top, R):
    """Water clock: a bowl drips into a tall jar; the float rises and, by a chain, tips the mirror
    to follow the sun."""
    x = R + 0.38
    k.box("clock_bracket", (0.5, 0.36, 0.06), (x - 0.1, -0.35, top + 0.12), "iron_black", parent=turret, bevel=0.004)
    k.cylinder("jar", 0.15, 0.62, (x, -0.35, top + 0.15), "bronze_old", segs=20, radius_top=0.17, parent=turret)
    k.cylinder("jar_lip", 0.19, 0.03, (x, -0.35, top + 0.77), "bronze_old", segs=20, parent=turret)
    k.cylinder("jar_water", 0.165, 0.01, (x, -0.35, top + 0.765), "crystal_core", segs=20, parent=turret, bevel=False)
    k.cylinder("bowl_water", 0.18, 0.01, (x + 0.08, -0.35, top + 1.19), "crystal_core", segs=20, parent=turret,
               bevel=False)
    k.tube("bowl_post", (x + 0.2, -0.35, top + 0.15), (x + 0.2, -0.35, top + 1.08), 0.025, "iron_black",
           parent=turret, segs=8)
    k.cylinder("bowl", 0.11, 0.16, (x + 0.08, -0.35, top + 1.05), "bronze_old", segs=20, radius_top=0.2,
               parent=turret)
    k.tube("drip", (x + 0.02, -0.35, top + 1.05), (x + 0.0, -0.35, top + 0.82), 0.012, "bronze_old", parent=turret,
           segs=6)
    k.tube("float_rod", (x - 0.04, -0.35, top + 0.7), (x - 0.04, -0.35, top + 1.25), 0.014, "brass", parent=turret,
           segs=8)
    k.hose("chain", [(x - 0.04, -0.35, top + 1.25), (x - 0.3, -0.6, top + 1.32), (0.6, -1.05, top + 1.3)], 0.01,
           "iron_black", parent=turret)


def _mirror_crown(k, head, R):
    """A crown of small round mirrors on gold stalks behind the crystal, all turned to its heart."""
    for i in range(10):
        a = 2 * math.pi * i / 10
        d = Vector((math.cos(a), 0, math.sin(a)))
        base = d * R * 0.98 + Vector((0, -0.05, 0))
        tip = d * (R + 0.3) + Vector((0, -0.42, 0))
        k.tube("mirror_stalk", base, tip, 0.016, "gold_trim", parent=head, segs=8)
        n = (-tip).normalized()
        rot = Vector((0, 0, 1)).rotation_difference(n).to_euler()
        k.cylinder("small_mirror", 0.12, 0.018, tip, "mirror", segs=20, rot=rot, parent=head)
        k.torus("small_mirror_rim", 0.125, 0.012, tip, "gold_trim", rot=rot, parent=head, segs=20, tube_segs=6)


# -- ammo pile ------------------------------------------------------------------------------------
def _ammo(k, root, level):
    rnd = random.Random(30 + level)
    p = Vector((1.85, -1.55, 0.0))
    if level == 1:                                   # glass blanks in a wicker basket
        k.cylinder("basket", 0.34, 0.3, p, "wicker", segs=20, radius_top=0.4, parent=root)
        for i in range(5):
            k.cylinder("blank", 0.15, 0.05, p + Vector((rnd.uniform(-0.15, 0.15), rnd.uniform(-0.15, 0.15),
                       0.3 + 0.03 * i)), "glass_green", segs=20, rot=(rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3),
                       0), parent=root, bevel=0.01)
        for i in range(3):
            k.cylinder("blank", 0.15, 0.05, p + Vector((0.5 + 0.08 * i, 0.15 - 0.2 * i, 0.0)), "glass_green", segs=20,
                       parent=root, bevel=0.01)
    elif level == 2:                                 # a straw-packed crate of lenses standing in slots
        k.box("crate", (0.8, 0.5, 0.36), p + Vector((0, 0, 0.18)), "timber_raw", parent=root, bevel=0.01)
        k.box("straw", (0.74, 0.44, 0.04), p + Vector((0, 0, 0.35)), "hemp", parent=root, bevel=False)
        for i in range(5):
            _lens(k, root, 0.16, 0.05, 0.015, "glass_clear", segs=24, rings=4).location = \
                p + Vector((-0.3 + 0.15 * i, 0, 0.42))
        k.box("crate_lid", (0.82, 0.52, 0.03), p + Vector((0.55, 0.35, 0.015)), "timber_raw", rot=(0, 0, 0.4),
              parent=root, bevel=0.006)
    elif level == 3:                                 # a rack of round flasks of spirit
        k.box("rack", (0.9, 0.42, 0.06), p + Vector((0, 0, 0.3)), "timber_oak", parent=root, bevel=0.008)
        for sx in (-1, 1):
            for sy in (-1, 1):
                k.box("rack_leg", (0.05, 0.05, 0.3), p + Vector((sx * 0.4, sy * 0.17, 0.15)), "timber_oak",
                      parent=root, bevel=0.005)
        for i in range(4):
            for j in range(2):
                q = p + Vector((-0.32 + 0.21 * i, -0.1 + 0.2 * j, 0.33))
                _ball(k, root, q + Vector((0, 0, 0.09)), 0.09, "glass_spirit", subdiv=2)
                k.tube("neck", q + Vector((0, 0, 0.16)), q + Vector((0, 0, 0.28)), 0.025, "glass_spirit", parent=root,
                       segs=10, bevel=False)
                k.cylinder("cork", 0.028, 0.04, q + Vector((0, 0, 0.27)), "timber_raw", segs=8, parent=root,
                           bevel=False)
    elif level == 4:                                 # a heap of raw quartz points
        for i in range(14):
            b = p + Vector((rnd.uniform(-0.4, 0.4), rnd.uniform(-0.3, 0.3), 0.0))
            d = Vector((rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), 1)).normalized()
            L, r = rnd.uniform(0.18, 0.36), rnd.uniform(0.04, 0.08)
            k.tube("quartz", b, b + d * L, r, "crystal_violet", parent=root, segs=6, bevel=False)
            k.tube("quartz_tip", b + d * L, b + d * (L + r * 1.6), r, "crystal_violet", radius_end=0.003, parent=root, segs=6,
                   bevel=False)
        for i in range(6):
            _ball(k, root, p + Vector((rnd.uniform(-0.5, 0.5), rnd.uniform(-0.4, 0.4), 0.03)), rnd.uniform(0.05, 0.09),
                  "stone", subdiv=1)
    else:                                            # cut crystals on red cloth in a lacquered case
        k.box("case", (0.8, 0.55, 0.22), p + Vector((0, 0, 0.11)), "timber_varnish", parent=root, bevel=0.01)
        k.box("case_cloth", (0.72, 0.47, 0.03), p + Vector((0, 0, 0.215)), "cloth_oxblood", parent=root, bevel=False)
        k.box("case_lid", (0.8, 0.04, 0.55), p + Vector((0, 0.3, 0.36)), "timber_varnish", rot=(-0.35, 0, 0),
              parent=root, bevel=0.008)
        for sx in (-1, 1):
            k.box("case_corner", (0.06, 0.56, 0.06), p + Vector((sx * 0.39, 0, 0.2)), "gold_trim", parent=root,
                  bevel=0.004)
        for i in range(3):
            for j in range(2):
                q = p + Vector((-0.24 + 0.24 * i, -0.1 + 0.2 * j, 0.24))
                d = Vector((1, 0, 0.0))
                k.tube("cut_crystal", q - d * 0.08, q + d * 0.04, 0.05, "crystal", parent=root, segs=6, bevel=False)
                k.tube("cut_crystal_tip", q + d * 0.04, q + d * 0.11, 0.05, "crystal", radius_end=0.003, parent=root,
                       segs=6, bevel=False)


# -- firing ---------------------------------------------------------------------------------------
def key_fire_animation(scene):
    import bpy
    prefs = bpy.context.preferences.edit
    old = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = "LINEAR"
    for f in range(FIRE_FRAMES + 1):
        set_fire_frame(f)
        for o, _, _ in _RIG["glow"]:
            o.keyframe_insert("scale", frame=f)
    prefs.keyframe_new_interpolation_type = old
    scene.frame_set(0)


def set_fire_frame(f, scene=None):
    """Lens glow: off at rest, on when firing. Crystal heart: always lit, flares when firing."""
    import bpy
    if scene is not None and _RIG["glow"] and _RIG["glow"][0][0].animation_data is not None:
        scene.frame_set(f)
    else:
        g = 0.0 if f == 0 else FIRE[f - 1]
        for o, s0, rest in _RIG["glow"]:
            m = max(0.001, g) if rest == 0.0 else 1.0 + 0.45 * g
            o.scale = tuple(v * m for v in s0)
    bpy.context.view_layer.update()
