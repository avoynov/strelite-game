"""Damage states for any built model (buildings and guns), applied to the scene after
build() and before materials_photoreal.stamp():

  damaged  a shell breach at the upper front-right corner (the side the camera sees).
  rubble   the building knocked down to ragged stumps, its roof fallen in.
  wreck    a gun torn open by a blast on one side, its turret knocked askew (`tilt`).

How it stays real rather than modelled:
  * The breach is a noisy blob (radial noise on a sphere), never a clean bowl. Small
    pieces (masonry blocks, planks, shingles, panels, gun parts: anything under
    UNIT_M) are taken out whole when their centre lies inside it, so masonry breaks
    along its joints and the edge is stepped. Big pieces (inner fills, long logs and
    beams, gables, decks) are cut by the same blob with a boolean, so their edges are
    as ragged as the blob.
  * The pieces taken out ARE the debris: stone blocks split in two or three along
    random planes, planks and beams snap into lengths with slanted ends, and then
    everything falls under rigid body physics (Bullet), pushed outward by a short
    blast, onto the ground, the floor inside and the remaining walls. Gravel and
    a ragged dust bed go with it. Nothing is placed in a heap by formula, nothing
    floats.
  * Shingles round the breach sag into it, two or three broken rafters fall in.
  * Soot fades with distance from the hit: stone to stone_soot, wood to
    timber_charred, paint to paint_soot.
  * A model can rebuild its own contents for a state with damage_hook(scene, state,
    info, phase) (the treasury's gold: it pours out of the breach rather than being cut).

Everything is deterministic for a seed.
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
STONE = ("stone", "brick", "concrete", "slate", "marble")
HIDDEN = ("core", "roof_deck", "mortar", "gate_dark", "door_recess", "win_dark", "lock_back")
ROOFING = ("shingle", "slate", "roof_tile")
UNIT_M = 1.5            # pieces up to this size come out whole; bigger ones are cut
KEEP = ("gold_", "coin")  # left to the model's damage_hook


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


# ---------------------------------------------------------------------------
# geometry helpers
def _local_dims(obj):
    vs = [v.co for v in obj.data.vertices]
    if not vs:
        return Vector((0, 0, 0)), Vector((0, 0, 0))
    lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
    hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    return lo, hi


def _long_axis(obj):
    """World direction and length of the object's longest local axis."""
    lo, hi = _local_dims(obj)
    d = hi - lo
    mw = obj.matrix_world.to_3x3()
    axes = [(mw.col[i] * d[i]) for i in range(3)]
    i = max(range(3), key=lambda j: axes[j].length)
    ln = [a.length for a in axes]
    return axes[i].normalized(), ln[i], sorted(ln)


def _manifold(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    ok = len(bm.faces) > 3 and all(e.is_manifold for e in bm.edges)
    bm.free()
    return ok


def _empty_mesh(obj):
    return obj.type == "MESH" and len(obj.data.polygons) == 0


def _split(obj, co, no):
    """Split a mesh object in two along a plane; returns the non-empty halves."""
    dup = obj.copy()
    dup.data = obj.data.copy()
    for coll in obj.users_collection:
        coll.objects.link(dup)
    _cut(obj, co, no)
    _cut(dup, co, -no)
    out = []
    for o in (obj, dup):
        if _empty_mesh(o):
            bpy.data.objects.remove(o)
        else:
            out.append(o)
    return out


def _unparent(obj):
    mw = obj.matrix_world.copy()
    obj.parent = None
    obj.matrix_world = mw


class _Blob:
    """A lumpy closed region round a centre: radius R with radial noise, stretched by S."""

    def __init__(self, rnd, centre, R, S=(1.0, 1.0, 1.0), amp=0.32):
        self.c = Vector(centre)
        self.R = R
        self.S = Vector(S)
        self.amp = amp
        self.w = [(Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized() * rnd.uniform(1.5, 5.0),
                   rnd.uniform(0, 2 * math.pi), rnd.uniform(0.4, 1.0)) for _ in range(9)]
        self.w += [(Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized() * rnd.uniform(6.0, 11.0),
                    rnd.uniform(0, 2 * math.pi), rnd.uniform(0.15, 0.3)) for _ in range(6)]
        self.norm = sum(a for *_, a in self.w)

    def shrunk(self, f):
        """The same lumpy shape at f times the size (cuts hidden layers just behind the visible edge)."""
        b = _Blob.__new__(_Blob)
        b.c, b.R, b.S, b.amp, b.w, b.norm = self.c, self.R * f, self.S, self.amp, self.w, self.norm
        return b

    def radius(self, d):
        s = sum(a * math.sin(k.dot(d) + p) for k, p, a in self.w) / self.norm
        return self.R * (1.0 + self.amp * s)

    def value(self, p):
        """< 1 inside, 1 on the surface."""
        q = Vector(p) - self.c
        q = Vector((q.x / self.S.x, q.y / self.S.y, q.z / self.S.z))
        if q.length < 1e-6:
            return 0.0
        return q.length / self.radius(q.normalized())

    def cutter(self, name="damage_cutter"):
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=4, radius=1.0)
        for v in bm.verts:
            d = v.co.normalized()
            r = self.radius(d)
            v.co = self.c + Vector((d.x * self.S.x, d.y * self.S.y, d.z * self.S.z)) * r
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        o = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(o)
        o.hide_render = True
        return o


def _height_cutter(cut_z, x0, x1, y0, y1, n=48, name="damage_cutter"):
    """Closed solid of everything above the surface z = cut_z(x, y) over a rectangle."""
    top = 40.0
    vs, fs = [], []
    for j in range(n + 1):
        for i in range(n + 1):
            x, y = x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * j / n
            vs.append((x, y, cut_z(x, y)))
    off = len(vs)
    for j in range(n + 1):
        for i in range(n + 1):
            x, y = x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * j / n
            vs.append((x, y, top))
    idx = lambda i, j, t=0: t + j * (n + 1) + i  # noqa: E731
    for j in range(n):
        for i in range(n):
            fs.append((idx(i, j), idx(i, j + 1), idx(i + 1, j + 1), idx(i + 1, j)))          # bottom (faces down)
            fs.append((idx(i, j, off), idx(i + 1, j, off), idx(i + 1, j + 1, off), idx(i, j + 1, off)))
    edge = [(i, 0) for i in range(n)] + [(n, j) for j in range(n)] + [(i, n) for i in range(n, 0, -1)] + \
           [(0, j) for j in range(n, 0, -1)]
    for a in range(len(edge)):
        (i0, j0), (i1, j1) = edge[a], edge[(a + 1) % len(edge)]
        fs.append((idx(i0, j0), idx(i1, j1), idx(i1, j1, off), idx(i0, j0, off)))
    me = bpy.data.meshes.new(name)
    me.from_pydata(vs, [], fs)
    me.validate()
    me.update()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.hide_render = True
    return o


def _boolean(obj, cutter):
    m = obj.modifiers.new("Damage", "BOOLEAN")
    m.operation = "DIFFERENCE"
    m.object = cutter
    m.solver = "EXACT"
    try:
        m.use_hole_tolerant = True
    except AttributeError:
        pass


def _bake_modifiers(objs):
    """Apply every modifier (bevel and the damage boolean) so physics and stamp see the result."""
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    for o in objs:
        if o.name not in bpy.data.objects or not o.modifiers:
            continue
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
        mats = [m for m in o.data.materials]
        o.modifiers.clear()
        o.data = me
        if not me.materials:
            for m in mats:
                me.materials.append(m)
        if len(me.polygons) == 0:
            bpy.data.objects.remove(o)


def _bed(k, name, centre, rx, ry, h, rnd, mat, n=40, sink=0.03):
    """A ragged low heightfield (dust bed, earth mound) with noisy edges, bottom below ground."""
    nz = _Noise(rnd, n=7, scale=0.35)
    nz2 = _Noise(rnd, n=5, scale=0.9)
    cx, cy = centre[0], centre[1]
    vs, fs = [], []
    for j in range(n + 1):
        for i in range(n + 1):
            u, v = -1 + 2 * i / n, -1 + 2 * j / n
            x, y = cx + u * rx, cy + v * ry
            d = math.hypot(u, v) * (1 + 0.35 * nz2(x, y))
            z = h * max(0.0, 1 - d * d) ** 0.9 * (0.7 + 0.3 * nz(x, y)) if d < 1 else 0.0
            vs.append((x, y, z - sink if z <= 1e-4 else z + rnd.uniform(-0.01, 0.01)))
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            fs.append((a, a + 1, a + n + 2, a + n + 1))
    o = k.mesh(name, vs, fs)
    k._finish(o, mat, bevel=False)
    return o


def _pebble(k, name, loc, s, mat, rnd):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
    sc = Vector((s, s * rnd.uniform(0.55, 1.0), s * rnd.uniform(0.4, 0.8)))
    for v in bm.verts:
        v.co = Vector((v.co.x * sc.x, v.co.y * sc.y, v.co.z * sc.z)) * rnd.uniform(0.8, 1.15)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (rnd.uniform(0, 6.3), rnd.uniform(0, 6.3), rnd.uniform(0, 6.3))
    o.data.materials.append(_material(mat, k.style))
    return o


# ---------------------------------------------------------------------------
# physics
def _simulate(scene, active, passive, blast=None, frames=72):  # noqa: C901
    """Drop `active` objects under gravity onto `passive` ones and the ground (Bullet rigid bodies),
    optionally pushed outward by a short blast (centre, strength, radius). Leaves the objects at
    their resting transforms with no simulation attached."""
    if not active:
        return
    ctx = bpy.context
    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    rbw = scene.rigidbody_world
    rbw.point_cache.frame_start = 1
    rbw.point_cache.frame_end = frames
    for attr, val in (("substeps_per_frame", 8), ("solver_iterations", 20)):
        if hasattr(rbw, attr):
            setattr(rbw, attr, val)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.25))
    ground = ctx.active_object
    ground.name = "damage_ground"
    ground.scale = (60, 60, 0.5)
    ground.hide_render = True

    def add(objs, typ):
        bpy.ops.object.select_all(action="DESELECT")
        for o in objs:
            o.select_set(True)
        ctx.view_layer.objects.active = objs[0]
        bpy.ops.rigidbody.objects_add(type=typ)

    for o in active:
        if o.parent is not None:
            _unparent(o)
    add([ground] + passive, "PASSIVE")
    ground.rigid_body.collision_shape = "BOX"
    for o in passive:
        rb = o.rigid_body
        if rb is None:
            continue
        big = max(o.dimensions) > UNIT_M or o.name.startswith(("dust_bed", "rubble_bed", "gold_"))
        rb.collision_shape = "MESH" if big else "CONVEX_HULL"
        if big:
            rb.mesh_source = "FINAL"
        rb.collision_margin = 0.002
        rb.friction = 0.9
    add(active, "ACTIVE")
    for o in active:
        rb = o.rigid_body
        d = o.dimensions
        rb.collision_shape = "CONVEX_HULL"
        rb.mass = o.get("rb_mass", max(0.02, d.x * d.y * d.z * 1.6))
        rb.friction = o.get("rb_friction", 0.85)
        rb.restitution = 0.02
        rb.linear_damping = 0.25
        rb.angular_damping = o.get("rb_damping", 0.45)
        rb.collision_margin = 0.002
    field = None
    if blast is not None:
        c, strength, radius = blast
        bpy.ops.object.effector_add(type="FORCE", location=c)
        field = ctx.active_object
        field.field.falloff_type = "SPHERE"
        field.field.use_max_distance = True
        field.field.distance_max = radius
        field.field.strength = strength
        field.keyframe_insert("field.strength", frame=1)
        field.keyframe_insert("field.strength", frame=3)
        field.field.strength = 0.0
        field.keyframe_insert("field.strength", frame=4)
    for f in range(1, frames + 1):
        scene.frame_set(f)
    rest = {o: o.matrix_world.copy() for o in active}
    bpy.ops.rigidbody.world_remove()
    if field is not None:
        bpy.data.objects.remove(field)
    bpy.data.objects.remove(ground)
    scene.frame_set(1)
    for o, mw in rest.items():
        o.matrix_world = mw
    bpy.context.view_layer.update()


# ---------------------------------------------------------------------------
def _info_hit(boxes, rnd):
    """The front-right upper corner of the main body (the corner the camera sees)."""
    walls = [b for o, b in boxes.items() if o.name.startswith("core")] or list(boxes.values())
    hx = max(b[1].x for b in walls)
    hy = min(b[0].y for b in walls)
    top = max(b[1].z for b in walls)
    return Vector((hx - 0.6 + rnd.uniform(-0.2, 0.2), hy + 0.6 + rnd.uniform(-0.2, 0.2), top * 0.95)), walls, top


def apply(scene, state, seed=1, footprint=4.0, hit=None, tilt=None, style="photoreal", heap_scale=1.0,
          keep=(), hook=None):
    """Damage everything in the scene (except terrain) in place."""
    rnd = random.Random(seed)
    k = Kit(style)
    _curves_to_meshes(scene)
    if tilt is not None:                        # knock a turret askew first (guns)
        node, rot = tilt
        node.rotation_euler = (node.rotation_euler[0] + rot[0], node.rotation_euler[1] + rot[1],
                               node.rotation_euler[2] + rot[2])
    bpy.context.view_layer.update()
    objs = [o for o in scene.objects if o.type == "MESH" and not o.get("terrain") and o.name not in keep
            and not o.name.startswith(KEEP)]
    boxes = {o: b for o, b in ((o, _world_bbox(o)) for o in objs) if b is not None}
    if not boxes:
        return None
    zmax = max(b[1].z for b in boxes.values())

    # --- the region that is destroyed -------------------------------------------------
    cut_z = None
    if state == "wreck":
        ang = rnd.uniform(0, 2 * math.pi)
        rr = footprint * rnd.uniform(0.35, 0.55)
        hit = Vector((math.cos(ang) * rr, math.sin(ang) * rr, max(0.9, zmax * 0.5)))
        R = max(1.0, min(2.0, footprint * 0.38))
        blob = _Blob(rnd, hit, R, (1.0, 1.0, 1.1))
        blob_hidden = blob
    elif state == "damaged":
        auto, walls, top = _info_hit(boxes, rnd)
        hit = Vector(hit) if hit is not None else auto
        R = max(1.7, min(2.5, top * 0.5))
        blob = _Blob(rnd, hit, R, (1.0, 1.0, 1.45), amp=0.5)
        blob_hidden = blob.shrunk(1.12)
    else:                                       # rubble
        noise, noise2, noise3 = _Noise(rnd, scale=1.2), _Noise(rnd, scale=0.45), _Noise(rnd, scale=0.18)
        cores = [b for o, b in boxes.items() if o.name.startswith("core")] or list(boxes.values())
        top = max(b[1].z for b in cores)
        cx0, cx1 = min(b[0].x for b in cores), max(b[1].x for b in cores)
        cy0, cy1 = min(b[0].y for b in cores), max(b[1].y for b in cores)
        corner = Vector((rnd.choice((cx0, cx1)), rnd.choice((cy0, cy1)), 0))
        bonus = top * rnd.uniform(0.35, 0.6)
        lo_z, hi_z = 0.25, min(1.6, 0.35 * top + 0.5)

        def cut_z(x, y):
            t = 0.5 + 0.5 * noise(x, y) + 0.3 * noise2(x, y)
            z = lo_z + (hi_z - lo_z) * max(0.0, min(1.0, t)) + 0.12 * noise3(x, y)
            d = math.hypot(x - corner.x, y - corner.y)
            return z + bonus * max(0.0, 1 - d / 2.6) ** 1.6

        hit = Vector(((cx0 + cx1) / 2, (cy0 + cy1) / 2, top * 0.5))
        R = footprint
        blob = blob_hidden = None

    blob_roof = None
    if state == "damaged":                      # the roof over the breach falls in, so light reaches the room
        blob_roof = _Blob(rnd, hit, R * 0.9, (1.0, 1.0, 5.0), amp=0.45)
    zones = {"main": blob, "hidden": blob_hidden, "roof": blob_roof or blob,
             "roof_hidden": (blob_roof or blob).shrunk(1.12) if blob is not None else None}

    def gone(p, key):
        if cut_z is not None:
            return p.z > cut_z(p.x, p.y) - (0.35 if "hidden" in key else 0.0)
        return zones[key].value(p) < 1.0

    # --- take pieces out, cut the big ones --------------------------------------------
    removed = []
    big = []
    cutters = {}
    for o, (lo, hi) in list(boxes.items()):
        c = (lo + hi) / 2
        mat = _mat_name(o)
        size = hi - lo
        hidden = o.name.startswith(HIDDEN)
        key = "roof" if o.name.startswith(ROOFING + ("roof", "ridge")) else "main"
        if hidden:
            key = "roof_hidden" if key == "roof" else "hidden"
        if state in ("rubble", "damaged") and o.name.startswith("core"):
            bpy.data.objects.remove(o)                       # the room inside shows; the walls close it
            continue
        if any(g in mat for g in GLASSY) and (state != "damaged" or blob.value(c) < 1.4):
            bpy.data.objects.remove(o)                       # glass shattered
            continue
        unit = max(size) <= UNIT_M and not hidden
        if unit or not _manifold(o):
            if gone(c, key):
                if hidden or any(cl in mat for cl in CLOTH) and state != "wreck":
                    bpy.data.objects.remove(o)               # hidden fill / burnt cloth: nothing falls
                else:
                    removed.append(o)
            continue
        # a big piece: does the region touch it at all?
        if cut_z is not None:
            touch = hi.z > min(cut_z(x, y) for x in (lo.x, c.x, hi.x) for y in (lo.y, c.y, hi.y)) - 0.4
        else:
            bl = zones[key]
            q = Vector((max(lo.x, min(bl.c.x, hi.x)), max(lo.y, min(bl.c.y, hi.y)), max(lo.z, min(bl.c.z, hi.z))))
            touch = (q - bl.c).length < bl.R * 1.4 * max(bl.S)
        if not touch:
            continue
        if key not in cutters:
            if cut_z is not None:
                off = 0.35 if "hidden" in key else 0.0
                cutters[key] = _height_cutter(lambda x, y, off=off: cut_z(x, y) - off, -12, 12, -12, 12)
            else:
                cutters[key] = zones[key].cutter("damage_cutter_" + key)
        _boolean(o, cutters[key])
        big.append(o)
    _bake_modifiers(big)
    for c in cutters.values():
        bpy.data.objects.remove(c)

    # --- roof round a breach sags into it; rafters fall in ------------------------------
    rafters = []
    if state == "damaged":
        for o in [o for o in scene.objects if o.type == "MESH" and o.name.startswith(ROOFING)]:
            c = o.matrix_world.translation
            v = blob.value(c)
            if 1.0 <= v < 1.4:
                t = (1.4 - v) / 0.4
                to = Vector((hit.x - c.x, hit.y - c.y, 0))
                if to.length > 1e-3:
                    axis = to.normalized().cross(Vector((0, 0, 1)))
                    mw = o.matrix_world.copy()
                    rot = Matrix.Rotation(-0.45 * t * rnd.uniform(0.6, 1.2), 4, axis)
                    loc = mw.translation.copy()
                    mw.translation = (0, 0, 0)
                    mw = rot @ mw
                    mw.translation = loc - Vector((0, 0, 0.35 * t))
                    o.matrix_world = mw
        if any(o.name.startswith(ROOFING + ("ridge", "roof")) for o in removed):
            for i in range(rnd.randint(2, 3)):
                L = rnd.uniform(1.8, 2.8)
                yaw = rnd.uniform(0, math.pi)
                p = hit + Vector((rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), 0.3 + 0.35 * i))
                b = k.box("rafter_broken", (L, 0.12, 0.16), p, "timber_charred",
                          rot=(rnd.uniform(-0.3, 0.3), rnd.uniform(-0.2, 0.2), yaw), bevel=0.01)
                rafters.append(b)

    # --- break the pieces that fell -----------------------------------------------------
    cap = {"damaged": 520, "rubble": 420, "wreck": 160}[state]
    rnd.shuffle(removed)
    if len(removed) > cap:
        for o in removed[cap:]:
            bpy.data.objects.remove(o)
        removed = removed[:cap]
    debris = []
    for o in removed:
        mat = _mat_name(o)
        axis, L, dims = _long_axis(o)
        pieces = [o]
        if any(w in mat for w in WOOD) and L > 0.7 and L > 3 * dims[1]:     # planks and beams snap
            n = min(3, max(1, int(L / 0.8)))
            ts = sorted(rnd.uniform(0.25, 0.75) for _ in range(n)) if n > 1 else [rnd.uniform(0.3, 0.7)]
            c = o.matrix_world.translation.copy()
            lo, hi = _local_dims(o)
            mid = o.matrix_world @ ((lo + hi) / 2)
            for t in ts:
                p = mid + axis * (t - 0.5) * L
                tilt_v = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))) * 0.55
                no = (axis + tilt_v).normalized()
                nxt = []
                for q in pieces:
                    nxt.extend(_split(q, p, no))
                pieces = nxt
        elif any(s_ in mat for s_ in STONE) and dims[2] > 0.15:           # blocks shatter unevenly
            for _ in range(rnd.choice((2, 2, 3))):
                nxt = []
                for q in pieces:
                    lo, hi = _local_dims(q)
                    mid = q.matrix_world @ ((lo + hi) / 2)
                    if max(q.dimensions) < 0.14:
                        nxt.append(q)
                        continue
                    no = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 0.8))).normalized()
                    off = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * 0.25 * min(q.dimensions)
                    nxt.extend(_split(q, mid + off, no))
                pieces = nxt
        debris.extend(pieces)

    # a ruin is not all of its material: much was carried off, burnt or blown away
    keep_frac = {"damaged": 0.5, "rubble": 0.4, "wreck": 0.6}[state]
    rnd.shuffle(debris)
    n_keep = int(len(debris) * keep_frac)
    for o in debris[n_keep:]:
        bpy.data.objects.remove(o)
    debris = debris[:n_keep]

    # --- what the debris lands on ------------------------------------------------------
    beds = []
    if state == "damaged":
        out = Vector((hit.x, hit.y, 0))
        beds.append(_bed(k, "dust_bed", out + Vector((0.4, -0.4, 0)), R * 0.95, R * 0.95, 0.18 * heap_scale, rnd,
                         "dirt_fill"))
    elif state == "rubble":
        mr = Vector(((cx1 - cx0) / 2 + 0.9, (cy1 - cy0) / 2 + 0.9, 0))
        mh = min(0.7, 0.15 + 0.11 * top) * heap_scale
        beds.append(_bed(k, "rubble_bed", ((cx0 + cx1) / 2, (cy0 + cy1) / 2), mr.x, mr.y, mh, rnd, "dirt_fill"))
        beds.append(_bed(k, "dust_bed", ((cx0 + cx1) / 2, (cy0 + cy1) / 2), mr.x + 0.7, mr.y + 0.7, 0.06, rnd, "ash",
                         n=30))
    else:
        beds.append(_bed(k, "dust_bed", (0, 0), footprint * 0.85, footprint * 0.85, 0.03, rnd, "ash", n=30))

    # gravel: small stones of the removed materials
    mats = [_mat_name(o) for o in debris] or ["stone"]
    n_gravel = {"damaged": 140, "rubble": 280, "wreck": 45}[state]
    for i in range(n_gravel):
        m = rnd.choice(mats)
        if any(w in m for w in WOOD):
            m = "timber_charred" if rnd.random() < 0.5 else m
        elif not any(s_ in m for s_ in STONE):
            m = "dirt_fill" if rnd.random() < 0.6 else "ash"
        if state == "rubble":
            p = Vector((rnd.uniform(cx0 - 0.5, cx1 + 0.5), rnd.uniform(cy0 - 0.5, cy1 + 0.5), rnd.uniform(1.0, 3.0)))
        else:
            d = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized() * rnd.uniform(0, R * 0.7)
            p = hit + d
            p.z = max(0.3, p.z)
        debris.append(_pebble(k, "gravel", p, rnd.uniform(0.02, 0.09), m, rnd))
    debris.extend(rafters)

    frames = 72
    if hook is not None:
        extra = hook(scene, state, {"hit": hit, "R": R, "blob": blob, "cut_z": cut_z, "rnd": rnd, "kit": k},
                     "structure")
        if extra:
            debris.extend(extra)
            frames = 120

    # --- soot and char fading out from the hit ------------------------------------------
    for o in [o for o in scene.objects if o.type == "MESH" and not o.get("terrain") and o.data.materials
              and o.data.materials[0] is not None and not o.name.startswith(KEEP)]:
        mat = _mat_name(o)
        c = o.matrix_world.translation
        if state == "rubble":
            p = 0.45
        else:
            d = blob.value(c)
            p = max(0.0, 1.0 - (d - 0.8) / 0.9) * 0.8
        if p <= 0 or rnd.random() > p:
            continue
        if any(w in mat for w in WOOD):
            o.data.materials[0] = _material("timber_charred", style)
        elif any(s_ in mat for s_ in STONE) and mat != "slate":
            o.data.materials[0] = _material("stone_soot", style)
        elif mat.startswith("paint_"):
            o.data.materials[0] = _material("paint_soot", style)
    if state == "wreck":                        # burnt right through: bright metal tarnished, cloth gone
        for o in [o for o in scene.objects if o.type == "MESH" and not o.get("terrain") and o.data.materials
                  and o.data.materials[0] is not None]:
            mat = _mat_name(o)
            if mat in ("silver", "silver_satin", "gold_trim", "chrome", "brass", "enamel_white") and rnd.random() < 0.6:
                o.data.materials[0] = _material("iron_black", style)
            elif any(cl in mat for cl in CLOTH) and mat not in ("rope", "leather") and rnd.random() < 0.8:
                if o in debris:
                    debris.remove(o)
                bpy.data.objects.remove(o)

    # --- let it fall -------------------------------------------------------------------
    active = [o for o in debris if o.name in bpy.data.objects]
    aset = set(active)
    reach = (R + 4.0) if state != "rubble" else footprint * 2
    passive = []
    for o in scene.objects:
        if o.type != "MESH" or o in aset or o.get("terrain") or o.hide_render or not o.data.polygons:
            continue
        if o.name.startswith(("mortar", "coin")):
            continue
        b = _world_bbox(o)
        if b is None:
            continue
        c = (b[0] + b[1]) / 2
        if (Vector((c.x, c.y, 0)) - Vector((hit.x, hit.y, 0))).length - max(b[1] - b[0]) / 2 < reach:
            passive.append(o)
    blast = None
    if state == "damaged":
        blast = (hit - Vector((0.6, -0.6, 0.2)), 14.0, R * 1.5)
    elif state == "wreck":
        blast = (hit * 0.6, 40.0, R * 2.0)
    _simulate(scene, active, passive, blast=blast, frames=frames)
    for o in active:                            # anything that fell through or flew off the patch
        if o.name not in bpy.data.objects:
            continue
        p = o.matrix_world.translation
        if p.z < -0.4 or p.xy.length > footprint + 1.0:
            bpy.data.objects.remove(o)

    if hook is not None:
        hook(scene, state, {"hit": hit, "R": R, "blob": blob, "cut_z": cut_z, "rnd": rnd, "kit": k}, "settled")
    return None


def _material(name, style):
    from . import materials
    return materials.get(name, style)


def occupy(scene, style="photoreal", seed=1):
    """The occupied look (an HQ taken by the Iron Concord): every defender emblem is
    replaced by the faction's cog-and-spear, blue flags and pennants turn oxblood,
    and faction pennants go up on the highest points. Call before apply()."""
    from .models import faction
    rnd = random.Random(seed)
    k = Kit(style)
    red = _material("paint_faction_red", style)
    bpy.context.view_layer.update()
    for e in [o for o in scene.objects if o.type == "EMPTY" and o.name.startswith("defender_emblem")]:
        mw = e.matrix_world.copy()
        loc = mw.translation.copy()
        normal = (mw.to_3x3() @ Vector((0, 1, 0))).normalized()
        scale = max((c.dimensions.z for c in e.children if c.type == "MESH"), default=0.6)
        stack = list(e.children)
        while stack:
            c = stack.pop()
            stack.extend(c.children)
            bpy.data.objects.remove(c)
        parent = e.parent
        bpy.data.objects.remove(e)
        faction.emblem(k, parent, loc + normal * 0.01, normal, r=max(0.25, scale * 0.42))
    for o in [o for o in scene.objects if o.type in ("MESH", "CURVE")]:
        mats = o.data.materials
        if mats and mats[0] is not None and mats[0].name.split("__")[0] == "paint_blue":
            mats[0] = red
    # a long oxblood banner with the faction emblem hung over the front wall (-Y), left of centre
    walls = [b for b in (_world_bbox(o) for o in scene.objects if o.type == "MESH" and o.name.startswith("core"))
             if b]
    if walls:
        lo = Vector((min(b[0].x for b in walls), min(b[0].y for b in walls), 0))
        hi = Vector((max(b[1].x for b in walls), 0, max(b[1].z for b in walls)))
        bx = lo.x + (hi.x - lo.x) * 0.25
        skin = [b for b in (_world_bbox(o) for o in scene.objects if o.type == "MESH"
                            and o.name.startswith(("block", "log", "plank")) and o.name[:5] != "quoin")
                if b and b[1].z > 1.0 and lo.x - 0.5 < (b[0].x + b[1].x) / 2 < hi.x + 0.5]
        by = (min(b[0].y for b in skin) if skin else lo.y - 0.4) - 0.04
        top = hi.z - 0.15
        L = min(2.6, top * 0.7)
        k.tube("banner_rod", (bx - 0.75, by, top), (bx + 0.75, by, top), 0.03, "brass", segs=8)
        k.box("banner", (1.2, 0.02, L), (bx, by - 0.02, top - L / 2 - 0.05), "cloth_oxblood", bevel=False)
        k.prism("banner_tail", [(bx - 0.6, top - L - 0.05), (bx + 0.6, top - L - 0.05), (bx, top - L - 0.4)], 0.02,
                "cloth_oxblood", y=by - 0.02)
        faction.emblem(k, None, (bx, by - 0.045, top - L * 0.4), (0, -1, 0), r=0.4)
    # faction pennants on the top of the tallest parts
    tops = []
    for o in [o for o in scene.objects if o.type == "MESH" and not o.get("terrain")]:
        b = _world_bbox(o)
        if b:
            tops.append((b[1].z, (b[0] + b[1]) / 2, b))
    tops.sort(key=lambda t: -t[0])
    placed = []
    for z, c, b in tops:
        if len(placed) >= 2:
            break
        if any((c.xy - p.xy).length < 2.0 for p in placed):
            continue
        p = Vector((c.x, c.y, z))
        faction.pennant(k, None, p, h=1.8, w=1.3)
        placed.append(p)
