"""Treasury of the player's base (bg: „Хазна“), 2 x 2 tiles (8 x 8 m), 5 levels.

Holds the gold; in the game its level protects part of the gold from raiders,
and the motorcycle raiders go for it first. The silhouette stays: one big open
trough heaped with gold coins, the mound rising above the rim and growing with
the level, so the player reads "gold store" at a glance. It is low and wide,
never a hall (muster, arsenal) or a tower (HQ). Each level changes the
trough's material and adds one new kind of securing or handling mechanism:

  L1  plank trough on log sleepers, rope lashed; a padlocked chest and
      a wooden shovel in the gold                                       (raw timber, rope)
  L2  tarred staves in forged iron bands on stone pads; a beam balance
      under a little roof for weighing the gold                        (tarred timber, iron)
  L3  dressed stone basin with an iron coping; a hinged iron grille
      raised at the back on two chains                                 (ashlar, forged iron)
  L4  riveted black iron tank with brass corners on a stone plinth; a
      clockwork time lock in a glazed case on the front                (black iron, brass)
  L5  pale marble basin with gilded rim and corner finials on a stepped
      plinth; a screw coin press with a weighted balance arm           (pale stone, gold)

Front faces: -Y (screen lower left) and +X (screen lower right).
Static object: one frame per level (render_buildings.py).
"""
import math
import random

from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit
from . import building as bd
from . import defender

LEVELS = (1, 2, 3, 4, 5)
TILES = 2
FOOTPRINT_M = 4.0
SPRITE_WH_M = (15.0, 19.0)
ANCHOR_FROM_BOTTOM_M = 4.6
NAMES = {"bg": "Хазна", "en": "Treasury"}

X0, X1, Y0, Y1 = -2.9, 2.5, -1.6, 2.4       # trough outer plan (5.4 x 4.0 m)
# level: (rim height, mound peak above the rim, wall thickness)
TROUGH = {1: (1.3, 0.8, 0.12), 2: (1.5, 1.0, 0.14), 3: (1.7, 1.2, 0.5), 4: (1.9, 1.4, 0.12),
          5: (2.0, 1.7, 0.45)}


def build(style, level=1):
    k = Kit(style)
    root = k.empty("treasury")
    mp.set_reference(root)
    rnd = bd.rnd_for(800 + level)
    {1: _l1, 2: _l2, 3: _l3, 4: _l4, 5: _l5}[level](k, root, rnd)
    rim, peak, t = TROUGH[level]
    k.box("core", (X1 - X0 - 2 * t - 0.04, Y1 - Y0 - 2 * t - 0.04, rim - 0.4), ((X0 + X1) / 2, (Y0 + Y1) / 2,
          0.2 + (rim - 0.4) / 2), "dirt_fill", parent=root, bevel=False)
    coins = _hoard(k, root, level, rnd)
    _gold(k, root, level, rnd)
    import bpy
    scene = bpy.context.scene
    scene["treasury_level"] = level
    _drop(scene, coins)
    return root, root


def ground(level):
    from ..terrain import Patch
    return Patch(r_solid=4.3, r_out=5.2, r_bare=4.0, seed=81 + level, ragged=0.5)


# ---------------------------------------------------------------------------
def sack(k, root, loc, r=0.22, mat="burlap", tie="rope"):
    loc = Vector(loc)
    prof = [(0, 0.0), (0.0, r * 0.8), (r * 0.5, r), (r * 1.2, r * 0.9), (r * 1.6, r * 0.45), (r * 1.75, r * 0.2),
            (r * 2.05, r * 0.3), (r * 2.1, 0.0)]
    k.lathe("sack", prof, mat, segs=16, loc=loc, rot=(math.pi / 2, 0, 0), parent=root)
    k.torus("sack_tie", r * 0.22, 0.015, loc + Vector((0, 0, r * 1.75)), tie, parent=root, segs=12, tube_segs=4)


def ingot(k, root, loc, yaw=0.0, mat="gold_trim"):
    loc = Vector(loc)
    v = [(-0.14, -0.06, 0), (0.14, -0.06, 0), (0.14, 0.06, 0), (-0.14, 0.06, 0),
         (-0.11, -0.04, 0.07), (0.11, -0.04, 0.07), (0.11, 0.04, 0.07), (-0.11, 0.04, 0.07)]
    f = [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    o = k.mesh("ingot", v, f)
    o.location = loc
    o.rotation_euler = (0, 0, yaw)
    k._finish(o, mat, bevel=0.006, parent=root)


def coin_heap(k, root, loc, r, h, mat="gold_coins"):
    k.lathe("coin_heap", [(0, 0.0), (0.0, r), (h * 0.3, r * 0.75), (h * 0.7, r * 0.4), (h, 0.0)], mat, segs=24,
            loc=Vector(loc), rot=(math.pi / 2, 0, 0), parent=root)


def chest(k, root, loc, size, yaw, wood, band, lock="iron_black", open_=False):
    loc = Vector(loc)
    sx, sy, sz = size
    k.box("chest", (sx, sy, sz), loc + Vector((0, 0, sz / 2)), wood, rot=(0, 0, yaw), parent=root, bevel=0.015)
    lid = loc + Vector((0, 0, sz))
    if open_:
        k.box("chest_lid", (sx, 0.05, sy * 0.9), lid + Vector((0, 0, 0)) + Vector((-math.sin(yaw), math.cos(yaw), 0)) * sy * 0.5
              + Vector((0, 0, sy * 0.45)), wood, rot=(0.2, 0, yaw), parent=root, bevel=0.01)
        coin_heap(k, root, lid - Vector((0, 0, 0.05)), min(sx, sy) * 0.45, 0.18)
    else:
        k.cylinder("chest_lid", sy / 2, sx, lid + Vector((-math.cos(yaw), -math.sin(yaw), 0)) * (sx / 2), wood,
                   segs=16, rot=(0, math.pi / 2, yaw), parent=root, bevel=0.01)
    d = Vector((math.cos(yaw), math.sin(yaw), 0))
    for t in (-0.38, 0.38):
        k.box("chest_band", (0.06, sy + 0.02, sz + 0.02), loc + d * (t * sx) + Vector((0, 0, sz / 2)), band,
              rot=(0, 0, yaw), parent=root, bevel=False)
    front = Vector((math.sin(yaw), -math.cos(yaw), 0))
    k.box("hasp", (0.08, 0.03, 0.18), loc + front * (sy / 2 + 0.02) + Vector((0, 0, sz - 0.05)), band,
          rot=(0, 0, yaw), parent=root, bevel=False)
    k.box("padlock", (0.14, 0.06, 0.14), loc + front * (sy / 2 + 0.05) + Vector((0, 0, sz - 0.2)), lock,
          rot=(0, 0, yaw), parent=root, bevel=0.01)
    k.torus("padlock_shackle", 0.05, 0.012, loc + front * (sy / 2 + 0.05) + Vector((0, 0, sz - 0.11)), lock,
            rot=(math.pi / 2, 0, yaw), parent=root, segs=12, tube_segs=4)



def _gear(k, root, c, normal, r, teeth, mat, w=0.06):
    n = Vector(normal).normalized()
    rot = n.to_track_quat("Z", "Y").to_euler()
    k.cylinder("gear", r, w, Vector(c), mat, segs=max(24, teeth * 2), rot=rot, parent=root, bevel=False)
    u = n.cross(Vector((0, 0, 1))).normalized()
    v = n.cross(u).normalized()
    for i in range(teeth):
        a = 2 * math.pi * i / teeth
        p = Vector(c) + (u * math.cos(a) + v * math.sin(a)) * (r + 0.02) + n * (w / 2)
        k.box("gear_tooth", (0.04, 0.04, w), p, mat, rot=rot, parent=root, bevel=False)
    k.cylinder("gear_hub", r * 0.25, w + 0.04, Vector(c) - n * 0.02, "steel_worn", segs=16, rot=rot, parent=root,
               bevel=False)



# ---------------------------------------------------------------------------
# the gold: one solid heap of coins filling the trough and pouring over the rim, with a skin of
# loose coins laid on it by ray casting (each coin rests on the surface under it, nothing floats)
SPILLS = {1: (("f", 0.2),), 2: (("f", 0.2), ("r", 1.0)), 3: (("f", 0.2), ("r", 1.0)),
          4: (("f", 0.2), ("r", 0.3), ("r", 1.8)), 5: (("f", 0.3), ("r", 0.0), ("r", 1.6))}


def _waves(rnd, n=6, amp=(0.03, 0.07), f=7.0):
    return [(rnd.uniform(*amp), rnd.uniform(-f, f), rnd.uniform(-f, f), rnd.uniform(0, 6.3)) for _ in range(n)]


def _wave(w, x, y):
    return sum(a * math.sin(fx * x + fy * y + ph) for a, fx, fy, ph in w)


def _solid_grid(k, root, name, x0, x1, y0, y1, zf, nx, ny, mat="gold_coins"):
    """A heightfield z = zf(x, y) closed down to the ground on all four sides (a solid, never a sheet)."""
    vs, fs = [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            x, y = x0 + (x1 - x0) * i / nx, y0 + (y1 - y0) * j / ny
            vs.append((x, y, zf(x, y)))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            fs.append((a, a + 1, a + nx + 2, a + nx + 1))
    edge = [(i, 0) for i in range(nx)] + [(nx, j) for j in range(ny)] + [(i, ny) for i in range(nx, 0, -1)] + \
           [(0, j) for j in range(ny, 0, -1)]
    base = len(vs)
    for i, j in edge:
        x, y, _ = vs[j * (nx + 1) + i]
        vs.append((x, y, -0.05))
    m = len(edge)
    for a in range(m):
        (i0, j0), (i1, j1) = edge[a], edge[(a + 1) % m]
        fs.append((j1 * (nx + 1) + i1, j0 * (nx + 1) + i0, base + a, base + (a + 1) % m))
    fs.append(tuple(range(base + m - 1, base - 1, -1)))
    o = k.mesh(name, vs, fs)
    k._finish(o, mat, smooth=True, bevel=False, parent=root)
    return o


def _spill_sources(level, blob=None):
    """(apex x, y, outward normal, along-wall direction) of every overflow, minus walls that are gone."""
    out = []
    for side, s in SPILLS[level]:
        if side == "f":
            p, n, t = Vector((s, Y0, 0)), Vector((0, -1, 0)), Vector((1, 0, 0))
        else:
            p, n, t = Vector((X1, s, 0)), Vector((1, 0, 0)), Vector((0, 1, 0))
        if blob is not None and blob.value(p + Vector((0, 0, TROUGH[level][0]))) < 1.15:
            continue
        out.append((p, n, t))
    return out


def _hoard(k, root, level, rnd, state="normal", info=None):
    """The gold: a solid heap filling the trough (its hidden body) and, for the physics to drop on it, a
    cloud of loose coins over the heap, columns of coins over the rim where it overflows, and in a damaged
    trough a pour of coins at the breach. Returns the coins; the caller lets them fall (rigid bodies) so
    every coin lands, rolls and settles on the heap, the rim, the ground or other coins."""
    rim, peak, t = TROUGH[level]
    ix0, ix1, iy0, iy1 = X0 + t, X1 - t, Y0 + t, Y1 - t
    cx, cy, hx, hy = (ix0 + ix1) / 2, (iy0 + iy1) / 2, (ix1 - ix0) / 2, (iy1 - iy0) / 2
    w = _waves(rnd)
    blob = info["blob"] if info else None
    z0 = rim - 0.12
    peak *= 0.5                                  # the solid body is low; the coins dropped on it build the heap
    if state == "rubble":                        # the trough is broken down; the gold lies low
        z0, peak = min(0.5, rim * 0.35), peak * 0.4
    sources = _spill_sources(level, blob if state == "damaged" else None)
    half = 0.4 + 0.05 * level
    slump, bp, bn = None, None, None
    if state == "damaged" and blob is not None:
        hit = info["hit"]
        bp = Vector((min(max(hit.x, X0), X1), min(max(hit.y, Y0), Y1), 0))
        bn = Vector((0, -1, 0)) if abs(bp.y - Y0) < abs(bp.x - X1) else Vector((1, 0, 0))
        zb = 0.04

        def slump(x, y, z):
            return min(z, zb + 0.5 * math.hypot(x - bp.x, y - bp.y))

    def mound_z(x, y):
        u, v = (x - cx) / hx, (y - cy) / hy
        d = (abs(u) ** 4 + abs(v) ** 4) ** 0.25
        z = z0 + peak * max(0.0, 1.0 - d * d) ** 0.85 + _wave(w, x, y) * min(1.0, max(0.0, (1.0 - d) * 4))
        if state != "rubble":
            for p, n, a in sources:                  # full to the brim where it runs over
                q = Vector((x - p.x, y - p.y, 0))
                din, lat = -q.dot(n) - t, abs(q.dot(a))
                if lat < half * 1.3 and din < 1.2:
                    z = max(z, rim + 0.04 - 0.12 * max(0.0, din) - 0.2 * max(0.0, lat - half))
        if slump:
            z = slump(x, y, z)
        return z

    _solid_grid(k, root, "gold_mound", ix0, ix1, iy0, iy1,
                lambda x, y: mound_z(x, y) + 0.025 * math.sin(23 * x + 3 * y) * math.sin(19 * y - 2 * x), 80, 60)

    pts = []
    sp = 0.205                                   # a loose layer of coins over the whole heap
    nx, ny = int((ix1 - ix0) / sp), int((iy1 - iy0) / sp)
    for j in range(ny):
        for i in range(nx):
            x = ix0 + (i + 0.5) * (ix1 - ix0) / nx + rnd.uniform(-0.02, 0.02)
            y = iy0 + (j + 0.5) * (iy1 - iy0) / ny + rnd.uniform(-0.02, 0.02)
            u, v = (x - cx) / hx, (y - cy) / hy
            layers = 2 + round((3 + level * 0.6) * max(0.0, 1 - (u * u + v * v)) ** 0.7)
            for layer in range(layers):
                pts.append((x + 0.1 * (layer % 2), y + 0.1 * (layer % 2),
                            mound_z(x, y) + 0.05 + 0.23 * ((i + 2 * j) % 3) + 0.7 * layer))
    cap_z = 0.15 if state == "rubble" else rim
    for p, n, a in sources:                      # columns of coins pouring over the rim
        count = (60 if state == "rubble" else 90) + 25 * level
        lats = [(-half + 0.11) + 0.22 * m for m in range(max(1, int(2 * half / 0.22)))]
        outs = (-t * 0.5, 0.14, 0.38)
        z, placed = cap_z + 0.2, 0
        while placed < count:
            for o in outs:
                for la in lats:
                    q = p + n * o + a * (la + rnd.uniform(-0.03, 0.03))
                    pts.append((q.x, q.y, z + rnd.uniform(-0.02, 0.02)))
                    placed += 1
            z += 0.23
    if bp is not None:                           # gold pouring out of the breach
        a = Vector((-bn.y, bn.x, 0))
        z = max(0.6, rim * 0.5)
        for m in range(14):
            for la in (-0.55, -0.33, -0.11, 0.11, 0.33, 0.55):
                for o in (-0.9, -0.66, -0.42):
                    q = bp + bn * o + a * la
                    pts.append((q.x, q.y, z + rnd.uniform(-0.02, 0.02)))
            z += 0.23
    coins = []
    for x, y, z in pts:
        o = k.cylinder("coin", 0.1, 0.022, (x, y, z), "gold_coins", segs=12,
                       rot=(rnd.uniform(0, 6.3), rnd.uniform(0, 6.3), rnd.uniform(0, 6.3)), parent=root, bevel=False)
        o["rb_mass"] = 0.4
        o["rb_friction"] = 1.0
        o["rb_damping"] = 0.85
        coins.append(o)
    return coins


def _drop(scene, coins):
    """Let the coins fall onto the heap, the trough and the ground, and settle."""
    from ..damage import _simulate
    keep = set(coins)
    passive = [o for o in scene.objects if o.type == "MESH" and o not in keep and not o.get("terrain")
               and not o.hide_render and len(o.data.polygons)]
    _simulate(scene, coins, passive, frames=120)
    import bpy
    for o in coins:
        if o.name in bpy.data.objects and (o.matrix_world.translation.z < -0.2
                                           or o.matrix_world.translation.xy.length > 5.2):
            bpy.data.objects.remove(o)


def damage_hook(scene, state, info, phase):
    """Rebuild the gold for a damage state (the coins fall with the debris): it pours out of the breach
    instead of being cut."""
    import bpy
    if phase != "structure":
        return None
    level = int(scene.get("treasury_level", 1))
    root = next((o for o in scene.objects if o.name.startswith("treasury") and o.type == "EMPTY"), None)
    rnd = random.Random(level * 31 + (7 if state == "damaged" else 13))
    for o in [o for o in scene.objects if o.name.startswith(("gold_", "coin")) and not o.name.startswith("coin_heap")]:
        bpy.data.objects.remove(o)
    return _hoard(info["kit"], root, level, rnd, state, info)

def _gold(k, root, level, rnd):
    """Sacks, an open chest and ingots stacked by the trough, more with the level."""
    base = Vector((1.4, -3.0, 0))
    for dx, dy in ((0.0, 0.3), (0.55, 0.45), (0.3, 0.9), (-0.3, 0.75))[:{1: 2, 2: 3, 3: 3, 4: 4, 5: 4}[level]]:
        sack(k, root, base + Vector((dx + 0.6, dy, 0)), r=0.27)
    if level >= 3:
        chest(k, root, base + Vector((2.1, 1.0, 0)), (0.9, 0.55, 0.5), 0.9, "timber_oak" if level < 5 else
              "timber_red", "iron_black" if level < 5 else "gold_trim", open_=True)
    if level >= 4:                                       # ingots stacked crosswise
        st = Vector((2.9, -2.75, 0))
        for L in range(3 if level == 4 else 5):
            for i in range(3):
                if L % 2 == 0:
                    ingot(k, root, st + Vector((0, -0.13 + 0.13 * i, 0.072 * L)), 0.0)
                else:
                    ingot(k, root, st + Vector((-0.13 + 0.13 * i, 0, 0.072 * L)), math.pi / 2)


def _bands(k, root, zs, t, mat, w=0.08):
    """Flat bands round the trough at heights zs (just proud of the walls)."""
    for z in zs:
        for (p0, p1) in (((X0, Y0), (X1, Y0)), ((X1, Y0), (X1, Y1)), ((X1, Y1), (X0, Y1)), ((X0, Y1), (X0, Y0))):
            a, b = Vector((p0[0], p0[1], z)), Vector((p1[0], p1[1], z))
            d = (b - a).normalized()
            n = Vector((d.y, -d.x, 0))
            k.box("band", ((b - a).length + 0.04 if abs(d.x) else 0.025, (b - a).length + 0.04 if abs(d.y) else 0.025,
                           w), (a + b) / 2 + n * 0.012, mat, rot=(0, 0, 0), parent=root, bevel=False)


def _stave_walls(k, root, rnd, z0, h, t, mat):
    for p0, p1 in (((X0, Y0 + t / 2), (X1, Y0 + t / 2)), ((X1 - t / 2, Y0), (X1 - t / 2, Y1)),
                   ((X1, Y1 - t / 2), (X0, Y1 - t / 2)), ((X0 + t / 2, Y1), (X0 + t / 2, Y0))):
        bd.planks(k, root, p0, p1, z0, h, t, rnd, mat=mat, w=0.24)


def _shovel(k, root, loc, lean):
    loc = Vector(loc)
    top = loc + Vector((lean[0], lean[1], 1.3))
    k.tube("shovel_haft", loc, top, 0.025, "timber_raw", parent=root, segs=8)
    k.box("shovel_grip", (0.22, 0.04, 0.04), top, "timber_raw", parent=root, bevel=0.005)
    k.box("shovel_blade", (0.28, 0.03, 0.34), loc - Vector((lean[0], lean[1], 0.0)) * 0.12, "timber_raw",
          rot=(0.15, 0, 0), parent=root, bevel=0.01)


def _l1(k, root, rnd):
    rim, _, t = TROUGH[1]
    z0 = 0.3
    for y in (Y0 + 0.5, Y1 - 0.5):                       # log sleepers
        k.cylinder("sleeper", 0.16, X1 - X0 + 0.6, (X0 - 0.3, y, 0.16), "log", segs=14, rot=(0, math.pi / 2, 0),
                   parent=root, bevel=0.01)
    k.box("trough_floor", (X1 - X0, Y1 - Y0, 0.08), ((X0 + X1) / 2, (Y0 + Y1) / 2, z0 - 0.04), "timber_raw",
          parent=root, bevel=0.005)
    _stave_walls(k, root, rnd, z0, rim - z0, t, "timber_raw")
    for (xa, ya) in ((X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)):  # corner posts, lashed
        k.box("corner_post", (0.18, 0.18, rim + 0.1), (xa, ya, (rim + 0.1) / 2), "log", parent=root, bevel=0.02)
        for z in (0.6, rim - 0.2):
            k.torus("lashing", 0.13, 0.02, (xa, ya, z), "rope", parent=root, segs=12, tube_segs=4)
    _shovel(k, root, (0.6, 0.2, rim + 0.25), (0.35, 0.25))
    chest(k, root, (-1.8, -2.7, 0), (1.1, 0.65, 0.6), 0.2, "timber_raw", "iron_forged", "iron_black")
    k.flag("pennant", 0.7, 0.3, (X0 - 0.0, Y1 - 0.0, rim + 1.2), "paint_blue", parent=root, waves=2, amp=0.04)
    k.tube("pennant_pole", (X0, Y1, rim), (X0, Y1, rim + 1.5), 0.03, "timber_raw", parent=root, segs=8)


def _balance(k, root, b):
    b = Vector(b)
    for sx in (-1, 1):
        k.box("canopy_post", (0.12, 0.12, 2.3), b + Vector((sx * 0.9, 0, 1.15)), "timber_tarred", parent=root,
              bevel=0.01)
    k.box("canopy", (2.2, 1.0, 0.06), b + Vector((0, 0, 2.35)), "timber_tarred", rot=(0.15, 0, 0), parent=root,
          bevel=0.01)
    k.box("bench", (1.6, 0.6, 0.08), b + Vector((0, 0.1, 0.8)), "timber_oak", parent=root, bevel=0.01)
    for sx in (-0.7, 0.7):
        k.box("bench_leg", (0.08, 0.5, 0.8), b + Vector((sx, 0.1, 0.4)), "timber_oak", parent=root, bevel=0.005)
    k.tube("balance_post", b + Vector((0, 0.1, 0.84)), b + Vector((0, 0.1, 1.6)), 0.03, "iron_forged", parent=root,
           segs=10)
    k.beam("balance_beam", b + Vector((-0.55, 0.1, 1.62)), b + Vector((0.55, 0.1, 1.55)), (0.04, 0.04),
           "iron_forged", parent=root)
    for sx, dz in ((-0.55, 0.0), (0.55, -0.07)):
        p = b + Vector((sx, 0.1, 1.6 + dz))
        for a in range(3):
            ang = 2 * math.pi * a / 3
            k.tube("pan_chain", p, p + Vector((math.cos(ang) * 0.14, math.sin(ang) * 0.14, -0.45)), 0.005,
                   "iron_forged", parent=root, segs=4, bevel=False)
        k.cylinder("pan", 0.17, 0.04, p + Vector((0, 0, -0.5)), "brass", segs=20, radius_top=0.19, parent=root,
                   bevel=False)
    coin_heap(k, root, b + Vector((0.55, 0.1, 1.07)), 0.1, 0.06)
    k.box("ledger", (0.35, 0.25, 0.04), b + Vector((-0.2, 0.15, 0.86)), "leather", parent=root, bevel=0.005)


def _l2(k, root, rnd):
    rim, _, t = TROUGH[2]
    z0 = 0.25
    for (xa, ya) in ((X0 + 0.4, Y0 + 0.4), (X1 - 0.4, Y0 + 0.4), (X1 - 0.4, Y1 - 0.4), (X0 + 0.4, Y1 - 0.4),
                     ((X0 + X1) / 2, Y0 + 0.4), ((X0 + X1) / 2, Y1 - 0.4)):
        k.box("pad", (0.5, 0.5, z0), (xa, ya, z0 / 2), "stone", parent=root, bevel=0.03)
    k.box("trough_floor", (X1 - X0, Y1 - Y0, 0.08), ((X0 + X1) / 2, (Y0 + Y1) / 2, z0 + 0.04), "timber_tarred",
          parent=root, bevel=0.005)
    _stave_walls(k, root, rnd, z0, rim - z0, t, "timber_tarred")
    _bands(k, root, (z0 + 0.2, (z0 + rim) / 2, rim - 0.15), t, "iron_forged")
    for (xa, ya) in ((X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)):  # iron corner straps
        k.box("corner_strap", (0.2, 0.2, rim - z0 + 0.04), (xa, ya, (z0 + rim) / 2), "iron_forged", parent=root,
              bevel=0.01)
    defender.emblem(k, root, ((X0 + X1) / 2, Y0 - 0.03, (z0 + rim) / 2 + 0.05), (0, -1, 0), h=0.55)
    _balance(k, root, (-1.6, -2.9, 0))
    bd.flag_mast(k, root, (X0 - 0.3, Y1 + 0.3, 0), 5.0, mat="timber_tarred", finial="iron_forged")


def _grille(k, root, rim, mat, ang=1.75):
    """Hinged iron grille lid raised at the back on its hinge line (y = Y1), held by two chains."""
    W, D = X1 - X0 - 0.2, (Y1 - Y0) * 0.42
    hinge = Vector(((X0 + X1) / 2, Y1 - 0.05, rim + 0.05))
    up = Vector((0, -math.cos(ang), math.sin(ang)))      # from the hinge toward the free edge
    n_bars = 11
    for i in range(n_bars):
        x = -W / 2 + W * i / (n_bars - 1)
        a = hinge + Vector((x, 0, 0))
        k.tube("grille_bar", a, a + up * D, 0.022, mat, parent=root, segs=8, bevel=False)
    for s in (0.0, 0.33, 0.66, 1.0):
        a = hinge + up * (D * s)
        k.box("grille_rail", (W + 0.06, 0.05, 0.05), a, mat, rot=(ang - math.pi / 2, 0, 0), parent=root, bevel=False)
    for sx in (-1, 1):
        k.cylinder("grille_hinge", 0.06, 0.25, hinge + Vector((sx * W * 0.4 - 0.125, 0, 0)), mat, segs=12,
                   rot=(0, math.pi / 2, 0), parent=root, bevel=False)
        top = hinge + up * D + Vector((sx * W * 0.45, 0, 0))
        post = Vector((hinge.x + sx * (W / 2 + 0.05), Y1 + 0.15, rim + 0.05))
        k.tube("grille_chain", top, post, 0.012, "iron_black", parent=root, segs=6, bevel=False)


def _l3(k, root, rnd):
    rim, _, t = TROUGH[3]
    for p0, p1 in (((X0, Y0 + t / 2), (X1, Y0 + t / 2)), ((X1 - t / 2, Y0), (X1 - t / 2, Y1)),
                   ((X1, Y1 - t / 2), (X0, Y1 - t / 2)), ((X0 + t / 2, Y1), (X0 + t / 2, Y0))):
        bd.masonry(k, root, p0, p1, 0, rim - 0.12, t, rnd, mat="stone_dressed", course=0.4, unit=(0.6, 1.1),
                   rough=0.01)
    for p0, p1 in (((X0, Y0 + t / 2), (X1, Y0 + t / 2)), ((X1 - t / 2, Y0), (X1 - t / 2, Y1)),
                   ((X1, Y1 - t / 2), (X0, Y1 - t / 2)), ((X0 + t / 2, Y1), (X0 + t / 2, Y0))):
        a, b = Vector((p0[0], p0[1], rim - 0.06)), Vector((p1[0], p1[1], rim - 0.06))
        d = b - a
        k.box("coping", (abs(d.x) + t + 0.1 if abs(d.x) else t + 0.1, abs(d.y) + t + 0.1 if abs(d.y) else t + 0.1,
                         0.14), (a + b) / 2, "stone_dressed", parent=root, bevel=0.02)
    _bands(k, root, (rim - 0.2,), t, "iron_forged", w=0.06)
    _grille(k, root, rim, "iron_forged")
    defender.emblem(k, root, ((X0 + X1) / 2, Y0 - 0.03, rim * 0.5), (0, -1, 0), h=0.7)
    defender.emblem(k, root, (X1 + 0.03, (Y0 + Y1) / 2, rim * 0.5), (1, 0, 0), h=0.7)
    bd.flag_mast(k, root, (X0 - 0.4, Y1 + 0.4, 0), 5.6, mat="timber_oak", finial="brass")


def _iron_tank(k, root, z0, rim):
    """Riveted black iron plate walls with brass corner angles."""
    for p0, p1, n in (((X0, Y0), (X1, Y0), (0, -1)), ((X1, Y0), (X1, Y1), (1, 0)), ((X1, Y1), (X0, Y1), (0, 1)),
                      ((X0, Y1), (X0, Y0), (-1, 0))):
        d = Vector((p1[0] - p0[0], p1[1] - p0[1], 0))
        L = d.length
        d.normalize()
        nn = Vector((n[0], n[1], 0))
        m = max(1, int(L / 1.1))
        for i in range(m):
            s = (i + 0.5) * L / m
            c = Vector((p0[0], p0[1], 0)) + d * s - nn * 0.06
            k.box("iron_panel", (abs(d.x) * (L / m - 0.03) + abs(nn.x) * 0.12,
                                 abs(d.y) * (L / m - 0.03) + abs(nn.y) * 0.12, rim - z0),
                  c + Vector((0, 0, (z0 + rim) / 2)), "iron_black", parent=root, bevel=0.004)
            if n[0] < 0 or n[1] > 0:
                continue                                     # rivets only on the faces the camera sees
            for z in [z0 + 0.15 + 0.3 * j for j in range(int((rim - z0 - 0.2) / 0.3) + 1)]:
                for o in (-L / m / 2 + 0.06, L / m / 2 - 0.06):
                    k.cylinder("rivet", 0.022, 0.03, c + d * o + nn * 0.07 + Vector((0, 0, z)), "iron_black",
                               segs=8, rot=nn.to_track_quat("Z", "Y").to_euler(), parent=root, bevel=False)
    for (xa, ya) in ((X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)):
        k.box("corner_angle", (0.2, 0.2, rim - z0 + 0.06), (xa, ya, (z0 + rim) / 2 + 0.03), "brass", parent=root,
              bevel=0.01)
    k.box("rim_angle", (X1 - X0 + 0.1, 0.1, 0.08), ((X0 + X1) / 2, Y0, rim), "brass", parent=root, bevel=0.005)
    k.box("rim_angle", (0.1, Y1 - Y0 + 0.1, 0.08), (X1, (Y0 + Y1) / 2, rim), "brass", parent=root, bevel=0.005)
    k.box("rim_angle", (X1 - X0 + 0.1, 0.1, 0.08), ((X0 + X1) / 2, Y1, rim), "iron_black", parent=root, bevel=0.005)
    k.box("rim_angle", (0.1, Y1 - Y0 + 0.1, 0.08), (X0, (Y0 + Y1) / 2, rim), "iron_black", parent=root, bevel=0.005)


def _l4(k, root, rnd):
    rim, _, t = TROUGH[4]
    z0 = 0.4
    k.box("plinth", (X1 - X0 + 0.4, Y1 - Y0 + 0.4, z0), ((X0 + X1) / 2, (Y0 + Y1) / 2, z0 / 2), "stone_dressed",
          parent=root, bevel=0.03)
    _iron_tank(k, root, z0, rim)
    _grille(k, root, rim, "iron_black", ang=1.9)
    # clockwork time lock: brass gears behind a glazed case on the front wall
    cc = Vector((X0 + 1.2, Y0 - 0.16, (z0 + rim) / 2 + 0.05))
    k.box("lock_case", (1.0, 0.18, 1.0), cc, "iron_black", parent=root, bevel=0.01)
    k.box("lock_back", (0.85, 0.02, 0.85), cc + Vector((0, -0.08, 0)), "enamel_white", parent=root, bevel=False)
    for (dx, dz, r, tt) in ((-0.15, 0.15, 0.2, 18), (0.2, 0.12, 0.13, 12), (0.05, -0.22, 0.16, 14),
                            (-0.25, -0.25, 0.09, 9)):
        _gear(k, root, cc + Vector((dx, -0.12, dz)), (0, -1, 0), r, tt, "brass", w=0.04)
    k.box("lock_glass", (0.9, 0.02, 0.9), cc + Vector((0, -0.2, 0)), "glass", parent=root, bevel=False)
    k.hose("lock_rod", [cc + Vector((0.5, 0, 0.3)), Vector((X0 + 2.0, Y0 - 0.1, rim + 0.05)),
                        Vector((X0 + 2.4, Y0 + 0.3, rim + 0.08))], 0.02, "brass", parent=root)
    defender.emblem(k, root, (X0 + 3.4, Y0 - 0.08, (z0 + rim) / 2 + 0.05), (0, -1, 0), h=0.75)
    defender.emblem(k, root, (X1 + 0.08, (Y0 + Y1) / 2, (z0 + rim) / 2 + 0.05), (1, 0, 0), h=0.8)
    bd.flag_mast(k, root, (X0 - 0.45, Y1 + 0.45, 0), 6.2, mat="iron_black", finial="brass")


def _press(k, root, p):
    p = Vector(p)
    k.box("press_base", (1.0, 0.8, 0.4), p + Vector((0, 0, 0.2)), "stone_pale", parent=root, bevel=0.02)
    for sx in (-1, 1):
        k.box("press_cheek", (0.16, 0.35, 1.5), p + Vector((sx * 0.35, 0, 1.15)), "bronze_old", parent=root,
              bevel=0.02)
    k.box("press_head", (0.95, 0.4, 0.3), p + Vector((0, 0, 2.0)), "bronze_old", parent=root, bevel=0.02)
    k.tube("press_screw", p + Vector((0, 0, 1.1)), p + Vector((0, 0, 2.5)), 0.07, "steel_worn", parent=root, segs=14)
    for i in range(8):
        k.torus("screw_thread", 0.075, 0.012, p + Vector((0, 0, 1.25 + i * 0.1)), "steel_worn", parent=root, segs=16,
                tube_segs=4)
    arm = p + Vector((0, 0, 2.45))
    k.tube("press_arm", arm + Vector((-1.0, -0.25, 0)), arm + Vector((1.0, 0.25, 0)), 0.04, "iron_black", parent=root,
           segs=10)
    for sx in (-1, 1):
        k.lathe("arm_ball", [(-0.16, 0.0)] + [(-0.16 * math.cos(math.pi * i / 8), 0.16 * math.sin(math.pi * i / 8))
                                               for i in range(1, 8)] + [(0.16, 0.0)], "gold_trim", segs=16,
                loc=arm + Vector((sx * 1.1, sx * 0.27, 0)), parent=root)
    k.cylinder("die", 0.1, 0.12, p + Vector((0, 0, 0.98)), "steel_worn", segs=16, parent=root, bevel=False)
    k.cylinder("anvil_die", 0.14, 0.2, p + Vector((0, 0, 0.4)), "steel_worn", segs=16, parent=root, bevel=False)


def _l5(k, root, rnd):
    rim, _, t = TROUGH[5]
    for i, (pad, h) in enumerate(((0.7, 0.2), (0.35, 0.2))):     # stepped plinth
        k.box("plinth", (X1 - X0 + 2 * pad, Y1 - Y0 + 2 * pad, h), ((X0 + X1) / 2, (Y0 + Y1) / 2, 0.2 * i + h / 2),
              "stone_pale", parent=root, bevel=0.02)
    for p0, p1 in (((X0, Y0 + t / 2), (X1, Y0 + t / 2)), ((X1 - t / 2, Y0), (X1 - t / 2, Y1)),
                   ((X1, Y1 - t / 2), (X0, Y1 - t / 2)), ((X0 + t / 2, Y1), (X0 + t / 2, Y0))):
        bd.masonry(k, root, p0, p1, 0.4, rim - 0.5, t, rnd, mat="stone_pale", course=0.4, unit=(0.8, 1.3),
                   rough=0.003)
        a, b = Vector((p0[0], p0[1], rim - 0.05)), Vector((p1[0], p1[1], rim - 0.05))
        d = b - a
        sx = abs(d.x) + t + 0.16 if abs(d.x) else t + 0.16
        sy = abs(d.y) + t + 0.16 if abs(d.y) else t + 0.16
        k.box("rim_gold", (sx, sy, 0.1), (a + b) / 2 + Vector((0, 0, 0.05)), "gold_trim", parent=root, bevel=0.01)
        k.box("rim_stone", (sx - 0.04, sy - 0.04, 0.12), (a + b) / 2 - Vector((0, 0, 0.06)), "stone_pale",
              parent=root, bevel=0.02)
    for (xa, ya) in ((X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)):     # gilded corner finials
        k.box("finial_pier", (0.6, 0.6, rim + 0.2 - 0.4), (xa, ya, 0.4 + (rim - 0.2) / 2), "stone_pale",
              parent=root, bevel=0.02)
        k.box("finial_cap", (0.66, 0.66, 0.1), (xa, ya, rim + 0.25), "gold_trim", parent=root, bevel=0.01)
        k.lathe("finial_ball", [(0.0, 0.0), (0.02, 0.18), (0.15, 0.24), (0.32, 0.18), (0.42, 0.06), (0.6, 0.02),
                                (0.62, 0.0)], "gold_trim", segs=20, loc=(xa, ya, rim + 0.3), rot=(math.pi / 2, 0, 0),
                parent=root)
    defender.emblem(k, root, ((X0 + X1) / 2, Y0 - 0.04, (0.4 + rim) / 2), (0, -1, 0), h=0.8)
    defender.emblem(k, root, (X1 + 0.04, (Y0 + Y1) / 2, (0.4 + rim) / 2), (1, 0, 0), h=0.85)
    _press(k, root, (-1.6, -2.7, 0))
    bd.flag_mast(k, root, (X0 - 0.5, Y1 + 0.5, 0), 6.8, mat="iron_black", finial="gold_trim")
