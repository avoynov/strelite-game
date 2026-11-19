"""Damage states for any built model (buildings and guns), applied to the scene after
build() and before materials_photoreal.stamp():

  damaged  a shell breach in one upper front corner: every part above a bowl-shaped
           cut surface around the hit is removed (blocks, planks and roof pieces are
           really cut, the cut faces capped), glass in the breach is gone, wood near
           the hit is charred, and the fallen material lies in a heap below the hole.
  rubble   the whole object is cut down to a ragged stump 0.2 to 1.3 m high; what was
           above lies around it as a heap of the same materials (stone chunks, broken
           planks and beams, bent plates), with ash and charred timber.
  wreck    the rubble state for a gun: a lower ragged cut that keeps the carriage and
           the base, the turret knocked askew first (pass `tilt`).

The heap is built from the materials of the parts that were removed, in proportion to
their volume, so a stone hall leaves stone rubble and a log hut leaves charred logs.
Everything is deterministic for a seed. Uses only Kit primitives for the heap.
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from .geo import Kit

WOOD = ("timber", "log", "wood", "plank")
GLASSY = ("glass", "screen", "arc_glow", "ember")
CLOTH = ("canvas", "flag", "burlap", "cloth", "rope", "hemp", "webbing", "leather", "uniform")


def _mat_name(obj):
    if obj.type == "CURVE":
        mats = obj.data.materials
    else:
        mats = obj.data.materials
    if not mats or mats[0] is None:
        return "stone"
    return mats[0].name.split("__")[0]


def _curves_to_meshes(scene):
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    for obj in [o for o in scene.objects if o.type == "CURVE"]:
        me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
        new = bpy.data.objects.new(obj.name, me)
        for coll in obj.users_collection:
            coll.objects.link(new)
        new.parent = obj.parent
        new.matrix_parent_inverse = obj.matrix_parent_inverse.copy()
        new.matrix_basis = obj.matrix_basis.copy()
        for poly in me.polygons:
            poly.use_smooth = True
        bpy.data.objects.remove(obj)
    bpy.context.view_layer.update()


class _Noise:
    """Smooth 2D value noise from a few seeded sines (no numpy needed)."""

    def __init__(self, rnd, n=6, scale=1.0):
        self.w = [(rnd.uniform(0.6, 2.2) / scale, rnd.uniform(0, 2 * math.pi), rnd.uniform(0, 2 * math.pi),
                   rnd.uniform(0.5, 1.0)) for _ in range(n)]
        self.norm = sum(a for *_, a in self.w)

    def __call__(self, x, y):
        s = 0.0
        for f, a, p, amp in self.w:
            s += amp * math.sin(f * (x * math.cos(a) + y * math.sin(a)) + p)
        return s / self.norm


def _world_bbox(obj):
    mw = obj.matrix_world
    vs = [mw @ v.co for v in obj.data.vertices]
    if not vs:
        return None
    lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
    hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    return lo, hi


def _cut(obj, co, no):
    """Remove the part of the mesh above the plane (co, no in world space); cap the cut."""
    inv = obj.matrix_world.inverted()
    lco = inv @ co
    lno = (inv.to_3x3().transposed().inverted() @ no) if False else (obj.matrix_world.to_3x3().transposed() @ no)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    res = bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=lco, plane_no=lno.normalized(),
                                 clear_outer=True)
    cut_edges = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
    if cut_edges:
        try:
            bmesh.ops.holes_fill(bm, edges=cut_edges, sides=0)
        except Exception:
            pass
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def apply(scene, state, seed=1, footprint=4.0, hit=None, tilt=None, style="photoreal", heap_scale=1.0,
          keep=()):
    """Damage everything in the scene (except terrain) in place. Returns the heap root."""
    rnd = random.Random(seed)
    _curves_to_meshes(scene)
    objs = [o for o in scene.objects if o.type == "MESH" and not o.get("terrain") and o.name not in keep]
    if tilt is not None:                        # knock a turret askew before cutting (guns)
        node, rot = tilt
        node.rotation_euler = (node.rotation_euler[0] + rot[0], node.rotation_euler[1] + rot[1],
                               node.rotation_euler[2] + rot[2])
        bpy.context.view_layer.update()
    boxes = {o: _world_bbox(o) for o in objs}
    boxes = {o: b for o, b in boxes.items() if b is not None}
    if not boxes:
        return None
    zmax = max(b[1].z for b in boxes.values())
    noise = _Noise(rnd, scale=1.2)
    noise2 = _Noise(rnd, scale=0.4)

    if state == "damaged":
        if hit is None:                         # an upper corner on the camera side
            xs = [b[1].x for b in boxes.values()]
            ys = [b[0].y for b in boxes.values()]
            hx = sorted(xs)[int(len(xs) * 0.85)]
            hy = sorted(ys)[int(len(ys) * 0.15)]
            hit = Vector((hx - 0.6 + rnd.uniform(-0.3, 0.3), hy + 0.6, zmax * 0.75))
        hit = Vector(hit)
        R = max(1.8, min(3.2, zmax * 0.6))

        def cut_z(x, y):
            d = math.hypot(x - hit.x, y - hit.y) / R
            if d >= 1.0:
                return 1e9
            depth = (1.0 - d * d) * (hit.z * 0.75) * (1 + 0.25 * noise2(x, y))
            return hit.z + 0.6 - depth
    else:
        lo_z, hi_z = (0.2, 1.3) if state == "rubble" else (0.15, 0.7)

        def cut_z(x, y):
            t = 0.5 + 0.5 * noise(x, y) + 0.25 * noise2(x, y)
            return lo_z + (hi_z - lo_z) * max(0.0, min(1.0, t))

    removed = []                                # (material, volume, centre, size)
    for o, (lo, hi) in list(boxes.items()):
        c = (lo + hi) / 2
        mat = _mat_name(o)
        if state == "damaged" and any(g in mat for g in GLASSY):
            if math.hypot(c.x - hit.x, c.y - hit.y) < R * 1.1:
                bpy.data.objects.remove(o)
            continue
        z = cut_z(c.x, c.y)
        if lo.z >= z:
            size = hi - lo
            removed.append((mat, size.x * size.y * size.z, c, size))
            bpy.data.objects.remove(o)
            continue
        if hi.z <= z:
            continue
        # gradient of the cut surface gives the plane's tilt (ragged, not flat)
        e = 0.15
        gx = (cut_z(c.x + e, c.y) - cut_z(c.x - e, c.y)) / (2 * e)
        gy = (cut_z(c.x, c.y + e) - cut_z(c.x, c.y - e)) / (2 * e)
        gx = max(-2.5, min(2.5, gx)) if abs(gx) < 1e8 else 0.0
        gy = max(-2.5, min(2.5, gy)) if abs(gy) < 1e8 else 0.0
        no = Vector((-gx, -gy, 1.0)).normalized()
        jag = Vector((rnd.uniform(-0.25, 0.25), rnd.uniform(-0.25, 0.25), 0))
        no = (no + jag).normalized()
        size = hi - lo
        frac = (hi.z - z) / max(size.z, 1e-3)
        removed.append((mat, size.x * size.y * size.z * frac, Vector((c.x, c.y, z)), size))
        _cut(o, Vector((c.x, c.y, z)), no)
        if any(w in mat for w in WOOD) and rnd.random() < (0.85 if state != "damaged" else 0.5):
            o.data.materials[0] = _material("timber_charred", style)

    if state == "damaged":                      # char the wood around the breach
        for o in [o for o in scene.objects if o.type == "MESH" and not o.get("terrain")]:
            if not o.data.materials or o.data.materials[0] is None:
                continue
            mat = _mat_name(o)
            if any(w in mat for w in WOOD):
                b = _world_bbox(o)
                if b and ((b[0] + b[1]) / 2 - hit).length < R * 1.15 and rnd.random() < 0.7:
                    o.data.materials[0] = _material("timber_charred", style)

    return _heap(scene, state, removed, rnd, footprint, hit, style, heap_scale)


def _material(name, style):
    from . import materials
    return materials.get(name, style)


def _heap(scene, state, removed, rnd, footprint, hit, style, heap_scale):
    """Lay the removed volume on the ground as rubble of the same materials."""
    k = Kit(style)
    root = k.empty("rubble_heap")
    root["damage"] = state
    vol = {}
    where = {}
    for mat, v, c, size in removed:
        if any(g in mat for g in GLASSY):
            continue
        key = "timber_charred" if (any(w in mat for w in WOOD) and rnd.random() < 0.6) else mat
        if any(cl in mat for cl in CLOTH):
            key = "ash" if rnd.random() < 0.5 else mat
        vol[key] = vol.get(key, 0.0) + v
        where.setdefault(key, []).append(c)
    total = sum(vol.values())
    if total <= 0:
        return root
    # the heap is shallower than the solid volume (debris is loose) and kept inside the footprint
    budget = 900 if state == "rubble" else 260
    if state == "damaged":
        centre = Vector((hit.x, hit.y - 0.2, 0))
        spread = 1.6
    else:
        centre = Vector((0, 0, 0))
        spread = footprint * 0.85
    # earth and ash mound under the chunks
    if state != "damaged":
        mr = spread * 0.9
        mh = min(1.0, 0.25 + total ** (1 / 3) * 0.12) * heap_scale
        k.lathe("rubble_mound", [(0, 0.0), (0, mr), (mh * 0.25, mr * 0.75), (mh * 0.6, mr * 0.45), (mh, mr * 0.12),
                                 (mh, 0.0)], "dirt_fill", segs=40, loc=centre, rot=(math.pi / 2, 0, 0), parent=root)
        k.lathe("ash_bed", [(0, 0.0), (0, mr * 1.08), (0.04, mr * 1.0), (0.05, 0.0)], "ash", segs=40,
                loc=centre, rot=(math.pi / 2, 0, 0), parent=root)
    else:
        mr, mh = spread, 0.35 * heap_scale
        k.lathe("rubble_mound", [(0, 0.0), (0, mr), (mh * 0.4, mr * 0.6), (mh, 0.0)], "dirt_fill", segs=28,
                loc=centre, rot=(math.pi / 2, 0, 0), parent=root)

    def mound_z(x, y):
        d = math.hypot(x - centre.x, y - centre.y) / mr
        return max(0.0, mh * (1 - d * d)) if d < 1 else 0.0

    for mat, v in sorted(vol.items(), key=lambda kv: -kv[1]):
        n = max(3, int(budget * v / total))
        pts = where[mat]
        wood = any(w in mat for w in WOOD) or mat == "timber_charred"
        metal = any(m in mat for m in ("iron", "steel", "brass", "bronze", "copper", "gold", "silver", "gunmetal",
                                       "chrome", "paint"))
        for i in range(n):
            src = pts[rnd.randrange(len(pts))]
            if state == "damaged":
                ang = rnd.uniform(0, 2 * math.pi)
                r = spread * math.sqrt(rnd.random())
                x, y = centre.x + math.cos(ang) * r, centre.y + math.sin(ang) * r
            else:
                x = src.x * 0.6 + rnd.gauss(0, 0.7)
                y = src.y * 0.6 + rnd.gauss(0, 0.7)
                lim = footprint - 0.4
                x, y = max(-lim, min(lim, x)), max(-lim, min(lim, y))
            z = mound_z(x, y)
            rot = (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), rnd.uniform(0, math.pi))
            if wood:
                L = rnd.uniform(0.5, 2.2)
                w = rnd.uniform(0.06, 0.2)
                k.box("debris_beam", (L, w, w * rnd.uniform(0.4, 1.0)), (x, y, z + w * 0.4), mat,
                      rot=(rnd.uniform(-0.25, 0.25), rnd.uniform(-0.35, 0.35), rnd.uniform(0, math.pi)),
                      parent=root, bevel=0.01)
            elif metal:
                s = rnd.uniform(0.2, 0.7)
                k.box("debris_plate", (s, s * rnd.uniform(0.4, 1.0), 0.03), (x, y, z + 0.05), mat,
                      rot=(rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5), rnd.uniform(0, math.pi)), parent=root,
                      bevel=0.005)
            else:
                s = rnd.uniform(0.12, 0.42)
                k.box("debris_chunk", (s, s * rnd.uniform(0.6, 1.1), s * rnd.uniform(0.5, 0.9)),
                      (x, y, z + s * 0.25), mat, rot=rot, parent=root, bevel=0.02 + s * 0.05)
    return root
