"""People for style В on Blender's Rigify Human meta-rig.

How a person is made (SOP "Human figures"):
  1. Body: the MakeHuman hm08 base mesh (CC0, assets/makehuman), morphed by its own
     targets (ancestry mix, muscle, weight, height, ideal proportions). A real human
     topology with a proper face, hands and feet, about 13 000 quads.
  2. Skeleton: the Rigify "Human" meta-rig (face bones removed), its bones fitted to
     the MakeHuman joint centres of that very body, then generated into a full
     Rigify control rig (IK legs and arms, spine, fingers).
  3. Skin: Blender's automatic weights (bone heat) bind the body to the DEF bones.
  4. Clothes are shells grown out of the body itself (same vertices, pushed out along
     the normals and smoothed), so they carry the body's weights and never cut
     through it; the skin they cover is removed.
  5. Rigid gear is parented to the bone it hangs from.
  6. Motion: the Rigify controls are posed per frame (feet on IK on a planted path,
     hands on IK on the rifle, torso, hips and chest for bob, lean and twist).

The rig object is Rigify's: it faces -Y. `Person` turns it 180 degrees under its
parent, so in the parent's space the person faces +Y like every other model.
Metres, Z up.
"""
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(HERE, "assets", "makehuman")
FACE_PREFIX = ("face", "lip", "nose", "brow", "cheek", "jaw", "chin", "ear", "lid", "forehead", "temple",
               "tongue", "teeth", "eye", "breast")
_BASE = None


def _base():
    global _BASE
    if _BASE is None:
        d = np.load(os.path.join(ASSETS, "hm08.npz"))
        _BASE = {k: d[k] for k in d.files}
    return _BASE


def _target(name):
    t = np.load(os.path.join(ASSETS, "targets", name + ".npz"))
    return t["idx"], t["delta"]


# ---------------------------------------------------------------------------
# body shape
def morph(ancestry=None, muscle=0.5, weight=0.5, height=0.5, proportions=1.0):
    """Vertices of the morphed base mesh, in MakeHuman units (decimetres, y up, z front).
    ancestry: weights of african/asian/caucasian (sum 1); muscle, weight, height in 0..1
    (0.5 = average)."""
    b = _base()
    v = b["verts"].astype(np.float64).copy()
    anc = ancestry or {"caucasian": 1.0}
    tot = sum(anc.values())
    for a, w in anc.items():
        i, d = _target(f"{a}-male-young")
        v[i] += (w / tot) * d
    # muscle / weight: corners max-muscle, min-weight around the average
    m = (muscle - 0.5) * 2.0
    wt = (weight - 0.5) * 2.0
    if m > 0 and wt >= 0:
        i, d = _target("universal-male-young-maxmuscle-averageweight")
        v[i] += m * d
    if m > 0 and wt < 0:
        i, d = _target("universal-male-young-maxmuscle-minweight")
        v[i] += min(m, -wt) * d
        i, d = _target("universal-male-young-maxmuscle-averageweight")
        v[i] += max(m + wt, 0) * d
        i, d = _target("universal-male-young-averagemuscle-minweight")
        v[i] += max(-wt - m, 0) * d
    if m <= 0 and wt < 0:
        i, d = _target("universal-male-young-averagemuscle-minweight")
        v[i] += -wt * d
    h = (height - 0.5) * 2.0
    if h:
        i, d = _target("male-young-averagemuscle-averageweight-" + ("maxheight" if h > 0 else "minheight"))
        v[i] += abs(h) * d
    if proportions:
        i, d = _target("male-young-averagemuscle-averageweight-idealproportions")
        v[i] += proportions * d
    return v


def to_blender(v):
    """MakeHuman (x, y up, z front) decimetres -> Blender metres facing -Y (Rigify)."""
    return np.stack([v[:, 0], -v[:, 2], v[:, 1]], 1) * 0.1


class Body:
    """Morphed body in Blender space (facing -Y, soles on z = 0), with joint centres."""

    def __init__(self, height_m=1.78, **shape):
        b = _base()
        self.faces = b["faces:body"]
        self.used = np.unique(self.faces)
        v = to_blender(morph(**shape))
        v[:, 2] -= v[self.used, 2].min()
        s = height_m / v[self.used, 2].max()
        self.verts = v * s
        self.scale = s
        self.height = height_m
        self.joint = {k[6:]: Vector(self.verts[b[k]].mean(0)) for k in b if k.startswith("joint:")}
        self.eyes = {sd: (self.verts, b[f"faces:helper-{sd}-eye"]) for sd in ("l", "r")}
        # heel: the rearmost sole point under each ankle
        for sd, sx in (("l", 1), ("r", -1)):
            a = self.joint[f"{sd}-ankle"]
            vv = self.verts[self.used]
            m = (np.abs(vv[:, 0] - a.x) < 0.04) & (vv[:, 2] < 0.04)
            back = vv[m][:, 1].max()
            self.joint[f"{sd}-heel"] = Vector((a.x, back, 0.0))

    def J(self, name):
        return self.joint[name].copy()


# ---------------------------------------------------------------------------
# meta-rig fitting
def _mid(a, b, t=0.5):
    return a.lerp(b, t)


def _fit_metarig(mr, body):
    """Move the Rigify Human meta-rig bones onto this body's joints."""
    J = body.J
    eb = mr.data.edit_bones
    for b in list(eb):
        if b.name.startswith(FACE_PREFIX):
            eb.remove(b)
    # remember the meta-rig's own Z axes (world), used to set rolls after moving
    old_z = {b.name: b.z_axis.copy() for b in eb}
    pos = {}
    up = Vector((0, 0, 1))
    pelvis, neck, head, top = J("pelvis"), J("neck"), J("head"), J("head-2")
    hips = _mid(J("l-upper-leg"), J("r-upper-leg"))
    spine0 = Vector((0, hips.y + 0.01, hips.z - 0.01))
    pos["spine"] = (spine0, J("spine-3"))
    pos["spine.001"] = (J("spine-3"), J("spine-2"))
    pos["spine.002"] = (J("spine-2"), J("spine-1"))
    pos["spine.003"] = (J("spine-1"), neck)
    pos["spine.004"] = (neck, _mid(neck, head, 0.55))
    pos["spine.005"] = (_mid(neck, head, 0.55), head)
    pos["spine.006"] = (head, Vector((0, head.y, top.z + 0.06 * body.scale)))
    for sd, S in (("l", "L"), ("r", "R")):
        sx = 1 if sd == "l" else -1
        cl, sh, el, wr = J(f"{sd}-clavicle"), J(f"{sd}-shoulder"), J(f"{sd}-elbow"), J(f"{sd}-hand")
        pos[f"shoulder.{S}"] = (Vector((sx * 0.02, cl.y - 0.03, cl.z + 0.03)), sh.lerp(cl, 0.15) + Vector((0, 0, 0.03)))
        pos[f"upper_arm.{S}"] = (sh, el)
        pos[f"forearm.{S}"] = (el, wr)
        mk = {n: J(f"{sd}-finger-{i}-1") for i, n in ((2, "index"), (3, "middle"), (4, "ring"), (5, "pinky"))}
        pos[f"hand.{S}"] = (wr, wr.lerp(mk["middle"], 0.35))
        for i, n in ((1, "index"), (2, "middle"), (3, "ring"), (4, "pinky")):
            k = mk[n]
            pos[f"palm.0{i}.{S}"] = (wr.lerp(k, 0.3) + (k - mk["middle"]) * 0.3, k)
            f = [J(f"{sd}-finger-{i + 1}-{j}") for j in (1, 2, 3, 4)]
            for j in range(3):
                pos[f"f_{n}.0{j + 1}.{S}"] = (f[j], f[j + 1])
        t = [J(f"{sd}-finger-1-{j}") for j in (1, 2, 3, 4)]
        for j in range(3):
            pos[f"thumb.0{j + 1}.{S}"] = (t[j], t[j + 1])
        hp, kn, an = J(f"{sd}-upper-leg"), J(f"{sd}-knee"), J(f"{sd}-ankle")
        ball, tip, heel = J(f"{sd}-foot-1"), J(f"{sd}-foot-2"), J(f"{sd}-heel")
        pos[f"pelvis.{S}"] = (spine0, Vector((sx * 0.11, hips.y + 0.05, hips.z + 0.15)) * 1.0)
        pos[f"thigh.{S}"] = (hp, kn)
        pos[f"shin.{S}"] = (kn, an)
        pos[f"foot.{S}"] = (an, ball)
        pos[f"toe.{S}"] = (ball, Vector((ball.x, tip.y, ball.z)))
        pos[f"heel.02.{S}"] = (Vector((an.x - 0.04, heel.y, 0.0)), Vector((an.x + 0.04, heel.y, 0.0)))
    connected = {b.name: b.use_connect for b in eb}
    for b in eb:
        b.use_connect = False
    for n, (h, t) in pos.items():
        b = eb[n]
        b.head, b.tail = h, t
    for b in eb:                                # the meta-rig's own chains, as they were
        b.use_connect = connected[b.name]
    # rolls: Z toward the inside of the bend for limbs, palm-ward for fingers, as the meta-rig
    for sd, S in (("l", "L"), ("r", "R")):
        sh, el, wr = J(f"{sd}-shoulder"), J(f"{sd}-elbow"), J(f"{sd}-hand")
        inside = (sh.lerp(wr, 0.5) - el)
        for n in (f"upper_arm.{S}", f"forearm.{S}"):
            eb[n].align_roll(inside)
        hp, kn, an = J(f"{sd}-upper-leg"), J(f"{sd}-knee"), J(f"{sd}-ankle")
        inside = (hp.lerp(an, 0.5) - kn)
        if inside.length < 1e-3 or inside.y < 0:
            inside = Vector((0, 1, 0))
        for n in (f"thigh.{S}", f"shin.{S}"):
            eb[n].align_roll(inside)
        # hand frame: y to the middle knuckle, radial (index side) and palm-ward normal
        i1, p1 = J(f"{sd}-finger-2-1"), J(f"{sd}-finger-5-1")
        hy = (J(f"{sd}-finger-3-1") - wr).normalized()
        radial = (i1 - p1)
        radial = (radial - hy * radial.dot(hy)).normalized()
        sgn = 1 if sd == "l" else -1
        dorsal = sgn * (i1 - wr).cross(p1 - wr).normalized()
        volar = -dorsal
        eb[f"hand.{S}"].align_roll(radial)
        for n in ("index", "middle", "ring", "pinky"):
            for j in (1, 2, 3):
                eb[f"f_{n}.0{j}.{S}"].align_roll(volar)
        for j in (1, 2, 3, 4):
            eb[f"palm.0{j}.{S}"].align_roll(volar)
        # thumb: curls across the palm toward the little finger, nail outward
        for j in (1, 2, 3):
            b = eb[f"thumb.0{j}.{S}"]
            b.align_roll(-radial * 0.7 + volar * 0.7)
        for n in (f"foot.{S}", f"toe.{S}", f"heel.02.{S}", f"shoulder.{S}", f"pelvis.{S}"):
            eb[n].align_roll(old_z[n])
    for n in ("spine", "spine.001", "spine.002", "spine.003", "spine.004", "spine.005", "spine.006"):
        eb[n].align_roll(Vector((0, -1, 0)))
    return pos


def build_rig(body, name="rig"):
    """Rigify Human meta-rig fitted to `body`, generated. Returns (rig, metarig)."""
    import addon_utils
    addon_utils.enable("rigify", default_set=True)
    from rigify import generate
    from rigify.metarigs import human as rh

    arm = bpy.data.armatures.new(name + "_meta")
    mr = bpy.data.objects.new(name + "_meta", arm)
    bpy.context.scene.collection.objects.link(mr)
    for o in bpy.context.scene.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = mr
    mr.select_set(True)
    rh.create(mr)                         # leaves the meta-rig in edit mode
    if mr.mode != "EDIT":
        bpy.ops.object.mode_set(mode="EDIT")
    _fit_metarig(mr, body)
    bpy.ops.object.mode_set(mode="OBJECT")
    mr.data.rigify_rig_basename = name
    generate.generate_rig(bpy.context, mr)
    rig = bpy.data.objects[name] if name in bpy.data.objects else \
        [o for o in bpy.data.objects if o.type == "ARMATURE" and o is not mr and o.data.get("rig_id")][-1]
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    # quiet the rig for rendering: no stretch, IK everywhere, clean pose
    for pb in rig.pose.bones:
        if "IK_Stretch" in pb:
            pb["IK_Stretch"] = 0.0
        if "IK_FK" in pb:
            pb["IK_FK"] = 0.0
    bpy.data.objects.remove(mr)
    for o in list(bpy.data.objects):          # Rigify's widget objects are not rendered
        if o.name.startswith("WGT-"):
            bpy.data.objects.remove(o)
    for c in list(bpy.data.collections):
        if c.name.startswith("WGTS") and not c.objects:
            bpy.data.collections.remove(c)
    return rig


# ---------------------------------------------------------------------------
# meshes
def mesh_obj(name, verts, faces, coll, smooth=True):
    me = bpy.data.meshes.new(name)
    fl = [tuple(f) if f[3] != f[2] else tuple(f[:3]) for f in faces]
    me.from_pydata([tuple(v) for v in verts], [], fl)
    me.update()
    if smooth:
        me.shade_smooth()
    obj = bpy.data.objects.new(name, me)
    coll.objects.link(obj)
    return obj


def bind_auto(rig, objs):
    """Parent with automatic weights (bone heat) to the rig's DEF bones."""
    for o in bpy.context.scene.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    for o in objs:
        o.select_set(False)


# ---------------------------------------------------------------------------
# mesh helpers (numpy, on the body's vertex indices)
def vertex_normals(verts, faces):
    tri = np.concatenate([faces[:, [0, 1, 2]], faces[:, [0, 2, 3]]])
    tri = tri[(tri[:, 0] != tri[:, 1]) & (tri[:, 1] != tri[:, 2]) & (tri[:, 0] != tri[:, 2])]
    a, b, c = verts[tri[:, 0]], verts[tri[:, 1]], verts[tri[:, 2]]
    fn = np.cross(b - a, c - a)
    n = np.zeros_like(verts)
    for i in range(3):
        np.add.at(n, tri[:, i], fn)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    return n / np.maximum(ln, 1e-12)


def neighbours(nv, faces):
    """Vertex adjacency as (rows, cols) edge arrays, both directions, no duplicates."""
    e = []
    for i in range(4):
        a, b = faces[:, i], faces[:, (i + 1) % 4]
        e.append(np.stack([a, b], 1))
    e = np.concatenate(e)
    e = e[e[:, 0] != e[:, 1]]
    e = np.unique(np.concatenate([e, e[:, ::-1]]), axis=0)
    return e[:, 0], e[:, 1]


def smooth(verts, faces, iters, move=None, lam=0.5, mu=-0.53):
    """Taubin smoothing (no shrink). `move`: per-vertex 0..1 freedom (0 = pinned)."""
    v = verts.copy()
    r, c = neighbours(len(v), faces)
    deg = np.bincount(r, minlength=len(v)).astype(np.float64)
    deg[deg == 0] = 1
    m = np.ones(len(v)) if move is None else move
    for _ in range(iters):
        for f in (lam, mu):
            acc = np.zeros_like(v)
            np.add.at(acc, r, v[c])
            lap = acc / deg[:, None] - v
            v = v + f * m[:, None] * lap
    return v


def boundary_verts(faces):
    e = np.concatenate([np.stack([faces[:, i], faces[:, (i + 1) % 4]], 1) for i in range(4)])
    e = e[e[:, 0] != e[:, 1]]
    e = np.sort(e, 1)
    u, cnt = np.unique(e, axis=0, return_counts=True)
    return np.unique(u[cnt == 1])


def _cut(me, cuts):
    """Bisect `me` along planes (point, normal, radius) and drop what lies beyond each.
    Vertex weights on the new edge points are interpolated by bmesh."""
    bm = bmesh.new()
    bm.from_mesh(me)
    for co, no, rad in cuts:
        co, no = Vector(co), Vector(no).normalized()
        geom = [f for f in bm.faces if (f.calc_center_median() - co).length < rad]
        if not geom:
            continue
        edges = {e for f in geom for e in f.edges}
        verts = {v for f in geom for v in f.verts}
        bmesh.ops.bisect_plane(bm, geom=list(verts) + list(edges) + geom, plane_co=co, plane_no=no,
                               clear_outer=False, clear_inner=False, dist=1e-5)
        dead = [f for f in bm.faces if (f.calc_center_median() - co).length < rad * 1.05
                and (f.calc_center_median() - co).dot(no) > 0]
        bmesh.ops.delete(bm, geom=dead, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(me)
    bm.free()
    me.update()


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------------------
class Person:
    """One person: MakeHuman body, Rigify rig, clothes grown from the body, rigid gear.

    In the parent's space the person stands at the origin facing +Y. `self.g` is an
    empty in that same space (front +Y, right +X) for gear built with the Kit;
    `attach(obj, bone)` binds such a part to a DEF bone of the rig."""

    def __init__(self, k, parent, name="man", height=1.78, shape=None, skin="skin"):
        self.k, self.name = k, name
        self.body = body = Body(height, **(shape or {}))
        self.s = height / 1.78
        self.rig = rig = build_rig(body, name)
        coll = k.collection
        if coll is not bpy.context.scene.collection:
            for c in list(rig.users_collection):
                c.objects.unlink(rig)
            coll.objects.link(rig)
        self.nrm = vertex_normals(body.verts, body.faces)
        self.skin_obj = mesh_obj(name + "_skin", body.verts, body.faces, coll)
        bind_auto(rig, [self.skin_obj])
        self.weights = self._read_weights(self.skin_obj)
        self.skin_obj.data.materials.append(k.material(skin))
        rig.parent = parent
        rig.rotation_euler = (0, 0, math.pi)
        self.g = k.empty(name + "_space", parent=rig)
        self.g.rotation_euler = (0, 0, math.pi)
        self.covered = np.zeros(len(body.verts), bool)
        self.shells = {}
        self.lift = 0.0

    # -- coordinates -----------------------------------------------------
    def J(self, name):
        """Joint in person space (front +Y, right +X)."""
        j = self.body.J(name)
        return Vector((-j.x, -j.y, j.z))

    def to_arm(self, p):
        """Person space -> armature space (the rig faces -Y)."""
        return Vector((-p[0], -p[1], p[2]))

    # -- weights -----------------------------------------------------------
    @staticmethod
    def _read_weights(obj):
        names = {g.index: g.name for g in obj.vertex_groups}
        out = {}
        for v in obj.data.vertices:
            for ge in v.groups:
                if ge.weight > 1e-4:
                    out.setdefault(names[ge.group], ([], []))
                    out[names[ge.group]][0].append(v.index)
                    out[names[ge.group]][1].append(ge.weight)
        return {n: (np.array(i), np.array(w)) for n, (i, w) in out.items()}

    def _skin_shell(self, obj, body_idx):
        """Give a mesh made from body vertices `body_idx` the body's weights."""
        remap = -np.ones(len(self.body.verts), int)
        remap[body_idx] = np.arange(len(body_idx))
        for n, (i, w) in self.weights.items():
            sel = remap[i] >= 0
            if not sel.any():
                continue
            vg = obj.vertex_groups.new(name=n)
            for vi, ww in zip(remap[i[sel]], w[sel]):
                vg.add([int(vi)], float(ww), "REPLACE")
        self.bind(obj)

    def bind(self, obj):
        m = obj.modifiers.new("Armature", "ARMATURE")
        m.object = self.rig
        while obj.modifiers.find("Armature") > 0:
            obj.modifiers.move(obj.modifiers.find("Armature"), 0)

    def attach(self, obj, bone):
        """Rigid part (and its children) rides on DEF bone `bone`."""
        if obj.type == "MESH":
            vg = obj.vertex_groups.get(bone) or obj.vertex_groups.new(name=bone)
            vg.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
            if "Armature" not in obj.modifiers:
                self.bind(obj)
        for c in obj.children:
            self.attach(c, bone)

    def _kd(self):
        if getattr(self, "_kdt", None) is None:
            from mathutils.kdtree import KDTree
            V = self.body.verts
            t = KDTree(len(V))
            for i in self.body.used:
                t.insert(V[i], int(i))
            t.balance()
            self._kdt = t
            dom = {}
            for n, (i, w) in self.weights.items():
                for vi, ww in zip(i, w):
                    if ww > dom.get(vi, ("", 0.0))[1]:
                        dom[vi] = (n, ww)
            self._dom = dom
        return self._kdt

    def bone_at(self, p_person):
        """The DEF bone that moves the body at this rest point (person space)."""
        kd = self._kd()
        _, i, _ = kd.find(self.to_arm(p_person))
        return self._dom[i][0]

    ARMS = ("DEF-upper_arm", "DEF-forearm", "DEF-hand", "DEF-f_", "DEF-thumb", "DEF-palm")

    def skin_near(self, obj, k=4, exclude=ARMS):
        """Weights for a part lying on the body: blended from the nearest body vertices,
        so straps, belt and collar bend with the cloth under them. Body vertices moved
        mainly by `exclude` bones are skipped (a belt must not follow the hands that
        hang beside it in the rest pose)."""
        kd = self._kd()
        bpy.context.view_layer.update()
        M = self.rig.matrix_world.inverted() @ obj.matrix_world
        acc = {}
        for v in obj.data.vertices:
            pa = M @ v.co
            near = [c for c in kd.find_n(pa, k * 6) if not self._dom[c[1]][0].startswith(exclude)][:k] \
                if exclude else []
            near = near or kd.find_n(pa, k)
            tot = 0.0
            ws = {}
            for co, i, d in near:
                f = 1.0 / max(d, 1e-4)
                tot += f
                for n, (ii, ww) in self._vw(i).items():
                    ws[n] = ws.get(n, 0.0) + f * ww
            for n, w in ws.items():
                acc.setdefault(n, []).append((v.index, w / tot))
        for n, lst in acc.items():
            vg = obj.vertex_groups.get(n) or obj.vertex_groups.new(name=n)
            for vi, w in lst:
                if w > 1e-3:
                    vg.add([vi], w, "REPLACE")
        if "Armature" not in obj.modifiers:
            self.bind(obj)

    def _vw(self, i):
        if getattr(self, "_vwmap", None) is None:
            m = {}
            for n, (ii, ww) in self.weights.items():
                for vi, w in zip(ii, ww):
                    m.setdefault(int(vi), {})[n] = (int(vi), float(w))
            self._vwmap = m
        return {n: (vi, w) for n, (vi, w) in self._vwmap.get(int(i), {}).items()}

    # -- clothes -------------------------------------------------------------
    def shell(self, name, vmask, mat, offset, iters=0, move=None, cover=True, subsurf=1, post=None, cuts=()):
        """Clothing shell over the body vertices in `vmask`: pushed out by `offset`
        (metres, scalar or per body vertex), Taubin-smoothed `iters` times.
        `cuts`: (point, normal, radius) planes in armature space; the shell is cut clean
        along each plane and the part on the normal's side (within radius) removed, so
        hems, cuffs and boot tops are straight instead of following the body's quads."""
        body = self.body
        if cuts:        # take a ring of faces more, the planes trim it back
            grow = vmask[body.faces].any(1)
            vmask = vmask.copy()
            vmask[np.unique(body.faces[grow])] = True
        F = body.faces[vmask[body.faces].all(1)]
        used = np.unique(F)
        remap = -np.ones(len(body.verts), int)
        remap[used] = np.arange(len(used))
        Fl = remap[F]
        off = offset if np.ndim(offset) == 0 else offset[used]
        V = body.verts[used] + self.nrm[used] * (np.asarray(off)[..., None] if np.ndim(off) else off)
        if iters:
            mv = np.ones(len(used)) if move is None else move[used]
            mv[boundary_verts(Fl)] *= 0.25
            V = smooth(V, Fl, iters, mv)
        if post is not None:
            V = post(V, used)
        obj = mesh_obj(f"{self.name}_{name}", V, Fl, self.k.collection)
        obj.data.materials.append(self.k.material(mat))
        obj.parent = self.rig
        self._skin_shell(obj, used)
        if cuts:
            _cut(obj.data, cuts)
        if subsurf:
            m = obj.modifiers.new("Subsurf", "SUBSURF")
            m.levels, m.render_levels = 0, subsurf
        if cover:
            self.covered[used] = True
        self.shells[name] = (obj, used)
        return obj

    def hide_covered(self, keep=None):
        """Remove the skin faces that clothes cover completely."""
        hide = self.covered.copy()
        if keep is not None:
            hide &= ~keep
        me = self.skin_obj.data
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.verts.ensure_lookup_table()
        dead = [f for f in bm.faces if all(hide[v.index] for v in f.verts)]
        bmesh.ops.delete(bm, geom=dead, context="FACES_ONLY")
        loose = [v for v in bm.verts if not v.link_faces]
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
        bm.to_mesh(me)
        bm.free()
        me.update()

    def finish_skin(self, subsurf=1):
        m = self.skin_obj.modifiers.new("Subsurf", "SUBSURF")
        m.levels, m.render_levels = 0, subsurf

    def eyes(self, white="eye_white", iris="eye_iris"):
        """Eyeballs from the MakeHuman helpers: white, with a dark iris facing forward."""
        b = _base()
        out = []
        for sd in ("l", "r"):
            F = b[f"faces:helper-{sd}-eye"]
            used = np.unique(F)
            remap = -np.ones(len(self.body.verts), int)
            remap[used] = np.arange(len(used))
            V = self.body.verts[used]
            c = V.mean(0)
            V = c + (V - c) * 0.97
            obj = mesh_obj(f"{self.name}_eye_{sd}", V, remap[F], self.k.collection)
            obj.data.materials.append(self.k.material(white))
            obj.data.materials.append(self.k.material(iris))
            for p in obj.data.polygons:
                n = Vector(p.center) - Vector(c)
                p.material_index = 1 if n.normalized().y < -0.82 else 0
            obj.parent = self.rig
            self.attach(obj, "DEF-spine.006")
            out.append(obj)
        return out

    # -- surface queries in person space (rest pose) ----------------------------
    def surface(self, names=None):
        """BVH of the clothed rest surface (shells `names`, default all) in person space."""
        vs, fs, off = [], [], 0
        for n, (obj, used) in self.shells.items():
            if names and n not in names:
                continue
            me = obj.data
            V = np.array([(-v.co.x, -v.co.y, v.co.z) for v in me.vertices])
            vs.append(V)
            fs += [[i + off for i in p.vertices] for p in me.polygons]
            off += len(V)
        V = np.concatenate(vs)
        return BVHTree.FromPolygons([tuple(v) for v in V], fs)

    @staticmethod
    def hit(bvh, origin, direction):
        """First surface point along the ray; if it misses, the ray is moved toward the
        body's axis until it hits."""
        o, d = Vector(origin), Vector(direction).normalized()
        for _ in range(8):
            loc, nrm, _, _ = bvh.ray_cast(o, d)
            if loc is not None:
                return loc, nrm
            side = o - d * o.dot(d)                 # offset across the ray
            o = o - Vector((side.x, side.y, 0)) * 0.3
        raise ValueError(f"no surface along {tuple(origin)} {tuple(direction)}")


# ---------------------------------------------------------------------------
# outfits
def _wsum(p, *prefixes):
    out = np.zeros(len(p.body.verts))
    for n, (i, w) in p.weights.items():
        if n.startswith(prefixes):
            out[i] += w
    return out


def _bump(x, c, w):
    return np.exp(-((x - c) / w) ** 2)


def boot_foot(p, sd, leather="boot_leather", sole="rubber", sole_h=0.022):
    """The foot of a laced field boot: a last-shaped loft from heel to toe (rounded toe
    box, high instep, narrow heel), a sole and a heel block, skinned to foot and toe."""
    from . import human as hu
    b = p.body
    a, ball, tip, heel = b.J(f"{sd}-ankle"), b.J(f"{sd}-foot-1"), b.J(f"{sd}-foot-2"), b.J(f"{sd}-heel")
    s = p.s
    x0 = 0.5 * (a.x + ball.x)
    yb, yt = heel.y + 0.012 * s, tip.y - 0.018 * s           # armature space: toes toward -Y
    L = yb - yt
    # (t from heel to toe, half width, height above the sole, x shift toward the big toe)
    st = [(0.0, 0.032, 0.085, 0.0), (0.06, 0.042, 0.11, 0.0), (0.22, 0.046, 0.125, 0.0),
          (0.45, 0.05, 0.10, 0.004), (0.66, 0.054, 0.072, 0.007), (0.82, 0.05, 0.058, 0.008),
          (0.94, 0.038, 0.048, 0.008), (1.0, 0.018, 0.036, 0.006)]
    inward = -1 if sd == "l" else 1                           # big toe side: toward the midline
    stations = []
    for t, hw, h, dx in st:
        y = yb - t * L
        stations.append(dict(c=(x0 + inward * dx * s, y, 0.004 + h * s / 2), rx=hw * s, ry=h * s / 2,
                             p=2.6 if t < 0.9 else 2.2))
    foot = hu.loft(p.k, f"{p.name}_boot_{sd}", stations, leather, p.rig, segs=20, subsurf=1)
    p.skin_near(foot)
    sl = [dict(c=(x0 + inward * dx * s, yb - t * L, 0.004 - sole_h / 2), rx=hw * s + 0.004, ry=sole_h / 2,
               p=5.0) for t, hw, h, dx in st[1:] + [(1.012, 0.012, 0, 0.005)]]
    sl.insert(0, dict(c=(x0, yb + 0.004, 0.004 - sole_h / 2), rx=0.03 * s, ry=sole_h / 2, p=5.0))
    so = hu.loft(p.k, f"{p.name}_sole_{sd}", sl, sole, p.rig, segs=20, subsurf=1)
    p.skin_near(so)
    return foot, so


def field_uniform(p, cloth="tunic_slate", lower="breeches_dark", boots="boot_leather", sole="boot_sole",
                  gloves="glove", hair="hair", hem=0.10, flare=0.035, breeches_flare=0.022, boot_top=0.075):
    """Tunic with a short skirt below the belt, flared breeches, high laced boots,
    gauntlet gloves, cropped hair. Heights follow this body's joints."""
    b = p.body
    V = b.verts
    x, y, z = V[:, 0], V[:, 1], V[:, 2]
    J = b.J
    side = np.sign(x)
    neck_z = J("neck").z
    waist_z = J("spine-3").z + 0.01 * p.s
    hip_z = J("l-upper-leg").z
    hem_z = hip_z - hem * p.s
    knee_z = J("l-knee").z
    top_z = knee_z - boot_top * p.s
    head_w = _wsum(p, "DEF-spine.004", "DEF-spine.005", "DEF-spine.006")
    hand_w = _wsum(p, "DEF-hand", "DEF-f_", "DEF-thumb", "DEF-palm")
    arm_w = _wsum(p, "DEF-upper_arm", "DEF-forearm") + hand_w
    leg_w = _wsum(p, "DEF-thigh", "DEF-shin", "DEF-foot", "DEF-toe")
    # forearm coordinate: 0 at the elbow, 1 at the wrist
    t = np.zeros(len(V))
    for sd, sx in (("l", 1), ("r", -1)):
        el, wr = np.array(J(f"{sd}-elbow")), np.array(J(f"{sd}-hand"))
        d = wr - el
        tt = (V - el) @ d / d.dot(d)
        t = np.where(side == sx, tt, t)
    armish = arm_w > 0.5
    head = (head_w > 0.35) & (z > neck_z - 0.025 * p.s)
    glove = (hand_w > 0.5) | (armish & (t > 0.80))
    # tunic: torso and sleeves down to the cuff, hem below the hips
    tunic = ~head & (z > hem_z) & ~((hand_w > 0.5) | (armish & (t > 0.95)))
    below_belt = smoothstep(waist_z, hem_z, z)
    off = 0.021 * p.s + flare * p.s * below_belt + 0.004 * p.s * (armish & (t < 0.6)) - 0.006 * p.s * armish
    cuts = [((0, 0, hem_z), (0, 0, -1), 0.7), ((0, J("neck").y, neck_z - 0.03 * p.s), (0, -0.6, 1), 0.15)]
    for sd in ("l", "r"):
        el, wr = J(f"{sd}-elbow"), J(f"{sd}-hand")
        cuts.append((el.lerp(wr, 0.94), wr - el, 0.13))
    p.shell("tunic", tunic, cloth, off, iters=22, cuts=cuts)
    # breeches: from the waist to below the knee, flared on the outside of the thigh
    br = (z < waist_z + 0.03 * p.s) & (z > top_z - 0.03 * p.s) & (arm_w < 0.3)
    outward = np.clip(p.nrm[:, 0] * side, 0, 1) ** 0.7 + 0.35 * np.clip(-p.nrm[:, 1], 0, 1)
    thigh_c = 0.5 * (hip_z + knee_z) + 0.03 * p.s
    off = 0.008 * p.s + breeches_flare * p.s * _bump(z, thigh_c, 0.10 * p.s) * np.clip(outward, 0, 1) \
        + 0.008 * p.s * smoothstep(top_z + 0.1 * p.s, top_z, z)
    p.shell("breeches", br, lower, off, iters=12)
    # boots: leather shaft grown from the shin, foot built as a boot last (no toes),
    # thick sole and heel; all of it bends with the ankle and the ball of the foot
    an_z = J("l-ankle").z
    bt = (z < top_z + 0.01 * p.s) & (leg_w > 0.5)
    shaft = bt & (z > an_z - 0.035 * p.s)
    off = 0.011 * p.s + 0.007 * p.s * smoothstep(top_z - 0.12 * p.s, top_z, z)
    p.shell("boots", shaft, boots, off, iters=10, cuts=[((0, 0, top_z), (0, 0, 1), 0.6)])
    p.covered[bt] = True
    sole_h = 0.022 * p.s
    for sd in ("l", "r"):
        boot_foot(p, sd, boots, sole, sole_h)
    p.lift = sole_h - 0.004
    # gauntlet gloves over the cuffs
    cuts = []
    for sd in ("l", "r"):
        el, wr = J(f"{sd}-elbow"), J(f"{sd}-hand")
        cuts.append((el.lerp(wr, 0.80), el - wr, 0.13))
    p.shell("gloves", glove, gloves, 0.0035 * p.s + 0.006 * p.s * (t < 0.95) * armish, iters=1, cuts=cuts)
    # cropped hair under the helmet
    ey = J("l-eye")
    hd = J("head")
    # hairline: a plane from the temples (eye height, behind the eyes) down to the nape
    y0, z0 = ey.y + 0.07 * p.s, ey.z + 0.005 * p.s
    y1, z1 = hd.y + 0.10 * p.s, neck_z + 0.035 * p.s
    k = (z1 - z0) / (y1 - y0)
    above = z > z0 + k * (y - y0)
    forehead = (y < ey.y + 0.05 * p.s) & (z < ey.z + 0.075 * p.s)
    scalp = (head_w > 0.5) & above & ~forehead
    p.shell("hair", scalp, hair, 0.0035 * p.s, iters=3, cover=False,
            cuts=[((0, y0, z0), (0, k, -1), 0.3)])
    brows = (head_w > 0.5) & (np.abs(np.abs(x) - abs(ey.x) - 0.002) < 0.026 * p.s) & \
        (z > ey.z + 0.013 * p.s) & (z < ey.z + 0.026 * p.s) & (y < ey.y + 0.01)
    if brows.sum() > 6:
        p.shell("brows", brows, hair, 0.0015 * p.s, cover=False, subsurf=1)
    p.hide_covered()
    p.finish_skin()
    p.eyes()
    p.rig.location = (0, 0, p.lift)


# ---------------------------------------------------------------------------
# motion
def _q_local(pb, R):
    """Local pose quaternion for a world-axis rotation R (3x3, armature space, rest frame)."""
    M = pb.bone.matrix_local.to_3x3()
    return (M.inverted() @ R @ M).to_quaternion()


def _periodic(keys, x):
    """Smooth periodic interpolation through (x, value) keys on [0, 1) (Catmull-Rom)."""
    ks = sorted(keys)
    n = len(ks)
    x = x % 1.0
    for i in range(n):
        x0, v0 = ks[i]
        x1, v1 = ks[(i + 1) % n]
        if x1 <= x0:
            x1 += 1.0
        xx = x if x >= x0 else x + 1.0
        if x0 <= xx < x1:
            xm, vm = ks[(i - 1) % n]
            x2, v2 = ks[(i + 2) % n]
            t = (xx - x0) / (x1 - x0)
            t2, t3 = t * t, t * t * t
            m0 = 0.5 * (v1 - vm)
            m1 = 0.5 * (v2 - v0)
            return (2 * t3 - 3 * t2 + 1) * v0 + (t3 - 2 * t2 + t) * m0 + (-2 * t3 + 3 * t2) * v1 + (t3 - t2) * m1
    return ks[0][1]


def _ease(s):
    return 0.5 - 0.5 * math.cos(math.pi * min(max(s, 0.0), 1.0))


class Runner:
    """Combat jog on the Rigify controls. Feet on IK follow a planted path: the stance
    foot moves back exactly `cycle_m` per cycle (the game advances frames by distance
    travelled, so it stays put on the ground); the swing foot lifts, kicks back, drives
    forward and lands. Hips bob, lean, turn with the legs; the chest counter-turns."""

    def __init__(self, person, cycle_m=1.85, stance=0.375, kick=0.20, lean=0.12, track=0.09,
                 toe_out=0.10, yaw=0.12, bob=0.022):
        self.p, self.C, self.D = person, cycle_m, stance
        self.kick, self.lean, self.track, self.toe_out, self.yaw, self.bob = kick, lean, track, toe_out, yaw, bob
        rig = person.rig
        B = rig.pose.bones
        L = rig.data.bones
        self.rest = {}
        for sd in ("L", "R"):
            fik = L[f"foot_ik.{sd}"]
            self.rest[sd] = dict(
                ankle=fik.head_local.copy(), ball=L[f"toe_ik.{sd}"].head_local.copy(),
                heel=person.body.J(f"{'l' if sd == 'L' else 'r'}-heel"),
                hip=L[f"ORG-thigh.{sd}"].head_local.copy(),
                leg=L[f"ORG-thigh.{sd}"].length + L[f"ORG-shin.{sd}"].length,
                thigh=L[f"ORG-thigh.{sd}"].length, shin=L[f"ORG-shin.{sd}"].length)
        for pb in B:
            if pb.name in ("torso", "hips", "chest", "head", "neck") or pb.name.startswith(
                    ("foot_ik", "toe_ik", "hand_ik", "f_", "thumb")):
                pb.rotation_mode = "QUATERNION"
        s = person.s
        # geometry of the stride (armature space: forward is -Y)
        r = self.rest["L"]
        a2b = (r["ball"] - r["ankle"])
        self.f_contact = 0.20 * s                  # ankle ahead of the hip at heel strike
        self.ball_contact = self.f_contact + (-a2b.y)
        self.ball_off = self.ball_contact - self.D * self.C
        self.hip_z = self._hip_heights()

    # -- the hip height that the legs can reach --------------------------------
    def _reach_z(self, dx, dy, az, knee):
        r = self.rest["L"]
        a, b = r["thigh"], r["shin"]
        L = math.sqrt(a * a + b * b + 2 * a * b * math.cos(knee))
        h = L * L - dx * dx - dy * dy
        return az + math.sqrt(max(h, 0.0))

    def _hip_heights(self):
        r = self.rest["L"]
        hx = r["hip"].x
        ax = self.track * self.p.s
        a_z = r["ankle"].z
        contact = self._reach_z(hx - ax, self.f_contact, a_z, math.radians(16))
        mid = self._reach_z(hx - ax, 0.0, a_z, math.radians(32))
        toe = self._foot_stance(self.D - 1e-4, "L")[0]
        toe_off = self._reach_z(hx - ax, toe.y - r["hip"].y, toe.z, math.radians(14))
        top = max(contact, toe_off) + self.bob * self.p.s
        return dict(contact=contact, mid=mid, toe_off=toe_off, top=top)

    # -- one foot ----------------------------------------------------------------
    def _foot_stance(self, ph, sd):
        """Ankle position and heel-up pitch while the foot is on the ground."""
        r = self.rest[sd]
        sx = 1 if sd == "L" else -1
        s = ph / self.D
        f_ball = self.ball_contact - s * self.D * self.C           # forward distance of the ball
        ball = Vector((sx * self.track * self.p.s, -f_ball, r["ball"].z))
        heel_up = math.radians(48) * _ease((s - 0.52) / 0.48) if s > 0.52 else 0.0
        toe_up = math.radians(7) * (1 - _ease(s / 0.16)) if s < 0.16 else 0.0
        a_rel = r["ankle"] - r["ball"]
        if heel_up > 0:
            ankle = ball + Matrix.Rotation(heel_up, 3, "X") @ a_rel
            pitch = heel_up
        else:
            h_rel = Vector((0, r["heel"].y - r["ball"].y, r["heel"].z - r["ball"].z))
            heel = ball + h_rel
            ankle = heel + Matrix.Rotation(-toe_up, 3, "X") @ (a_rel - h_rel)
            pitch = -toe_up
        return ankle, pitch

    def foot(self, ph, sd):
        """(ankle, pitch, toe_flat) at phase ph of this foot (0 = its heel strike)."""
        ph %= 1.0
        if ph < self.D:
            a, pitch = self._foot_stance(ph, sd)
            return a, pitch, True
        s = (ph - self.D) / (1 - self.D)
        a0, p0 = self._foot_stance(self.D - 1e-4, sd)
        a1, p1 = self._foot_stance(0.0, sd)
        e = _ease(s ** 0.9)
        a = a0.lerp(a1, e)
        a.z = a0.z + (a1.z - a0.z) * e + self.kick * self.p.s * (s * (1 - s) ** 1.5) / 0.1859
        a.y += 0.04 * self.p.s * math.sin(math.pi * s) ** 2 * (1 if s < 0.5 else 0)   # heel trails a little
        pitch = _periodic([(0.0, p0), (0.22, math.radians(72)), (0.55, math.radians(28)),
                           (0.82, math.radians(-2)), (0.999, p1)], s * 0.999) if s < 0.999 else p1
        return a, pitch, False

    # -- whole body ----------------------------------------------------------------
    def stage_body(self, ph):
        p, rig = self.p, self.p.rig
        B = rig.pose.bones
        for pb in B:
            if pb.name.startswith(("foot_ik", "toe_ik", "hand_ik", "f_", "thumb", "torso", "hips", "chest", "head")):
                pb.location = (0, 0, 0)
                pb.rotation_quaternion = (1, 0, 0, 0)
        hz = self.hip_z
        D2 = self.D * 2          # stance share of one step
        keys = [(0.0, hz["contact"]), (D2 * 0.5, hz["mid"]), (D2, hz["toe_off"]),
                (D2 + (1 - D2) * 0.5, hz["top"])]
        step = (ph * 2) % 1.0
        z = _periodic(keys, step)
        r = self.rest["L"]
        dz = z - r["hip"].z
        stance_l = math.sin(2 * math.pi * ph)            # +: left foot under the body
        sway = 0.012 * p.s * stance_l
        tor = B["torso"]
        M = tor.bone.matrix_local.to_3x3()
        tor.location = M.inverted() @ Vector((sway, 0.0, dz))
        tor.rotation_quaternion = _q_local(tor, Matrix.Rotation(self.lean, 3, "X"))
        yaw = -self.yaw * math.cos(2 * math.pi * ph)     # left hip forward at the left heel strike
        roll = math.radians(3.5) * stance_l
        B["hips"].rotation_quaternion = _q_local(B["hips"], Matrix.Rotation(yaw, 3, "Z") @ Matrix.Rotation(-roll, 3, "Y"))
        B["chest"].rotation_quaternion = _q_local(B["chest"], Matrix.Rotation(-0.45 * yaw, 3, "Z") @
                                                  Matrix.Rotation(0.03 + 0.02 * math.cos(4 * math.pi * ph), 3, "X"))
        # eyes on the way ahead: the head takes back most of the lean of torso and chest
        head = B["head"]
        head.rotation_quaternion = _q_local(head, Matrix.Rotation(-0.9 * (self.lean + 0.03) - 0.12, 3, "X"))
        for sd, off in (("L", 0.0), ("R", 0.5)):
            a, pitch, flat = self.foot(ph + off, sd)
            sx = 1 if sd == "L" else -1
            R = Matrix.Rotation(pitch, 3, "X") @ Matrix.Rotation(sx * self.toe_out, 3, "Z")
            pb = B[f"foot_ik.{sd}"]
            Mr = pb.bone.matrix_local.to_3x3()
            pb.location = Mr.inverted() @ (a - self.rest[sd]["ankle"])
            pb.rotation_quaternion = _q_local(pb, R)
            toe = B[f"toe_ik.{sd}"]
            bend = -pitch if (flat and pitch > 0) else (-0.35 * pitch if pitch > 0 else 0.0)
            toe.rotation_quaternion = _q_local(toe, Matrix.Rotation(bend, 3, "X"))

    def stage_hands(self, grips):
        """grips: {"L"/"R": (point, finger_dir, thumb_dir)} in armature rest space, carried by
        the chest; hand_ik is set so the palm closes round each point."""
        close_hands(self.p, grips, carry="DEF-spine.003")


def close_hands(person, grips, carry=None):
    """Set hand_ik so each palm closes round a grip {"L"/"R": (point, finger_dir,
    thumb_dir)} given in armature rest space; `carry` is a bone that carries the grips
    (the chest for a rifle), None for grips fixed to the parent (handlebars)."""
    rig = person.rig
    B = rig.pose.bones
    if carry:
        cb = B[carry]
        Mc = cb.matrix @ cb.bone.matrix_local.inverted()
    else:
        Mc = Matrix.Identity(4)
    for sd, (pt, fy, fz) in grips.items():
        P = Mc @ Vector(pt)
        y = (Mc.to_3x3() @ Vector(fy)).normalized()
        z = (Mc.to_3x3() @ Vector(fz))
        z = (z - y * z.dot(y)).normalized()
        x = y.cross(z)
        volar = x if sd == "L" else -x
        wrist = P - y * 0.075 * person.s - volar * 0.028 * person.s
        F = Matrix((x, y, z)).transposed().to_4x4()
        F.translation = wrist
        hand_rest = rig.data.bones[f"ORG-hand.{sd}"].matrix_local
        ik = B[f"hand_ik.{sd}"]
        ik.matrix = F @ hand_rest.inverted() @ ik.bone.matrix_local
        for n, a in (("f_index", (1.25, 1.35, 0.8)), ("f_middle", (1.35, 1.4, 0.8)),
                     ("f_ring", (1.4, 1.4, 0.8)), ("f_pinky", (1.45, 1.35, 0.8))):
            for j, ang in enumerate(a):
                fb = B[f"{n}.0{j + 1}.{sd}"]
                fb.rotation_quaternion = _q_local(fb, Matrix.Rotation(ang, 3, fb.bone.x_axis))
        for j, ang in enumerate((0.25, 0.5, 0.45)):
            tb = B[f"thumb.0{j + 1}.{sd}"]
            tb.rotation_quaternion = _q_local(tb, Matrix.Rotation(ang, 3, tb.bone.x_axis))


class Rider:
    """Seated on a machine (motorcycle, horse, cart): the pelvis on the saddle, the feet
    on the pegs, the hands on the bars, all on the Rigify IK controls. A still pose;
    the machine's wheels carry the movement. Points are in person space (front +Y)."""

    def __init__(self, person, seat, pegs, bars, lean=0.55, chest=0.1, toe_out=0.12, foot_pitch=0.1):
        self.p, self.seat, self.pegs, self.bars = person, Vector(seat), pegs, bars
        self.lean, self.chest, self.toe_out, self.foot_pitch = lean, chest, toe_out, foot_pitch

    def _a(self, v):
        """Person-space point -> armature space (the rig stands `lift` up on its soles)."""
        return self.p.to_arm(Vector(v) - Vector((0, 0, self.p.rig.location.z)))

    def pose(self):
        p, rig = self.p, self.p.rig
        B = rig.pose.bones
        L = rig.data.bones
        for pb in B:
            if pb.name in ("torso", "hips", "chest", "head", "neck") or pb.name.startswith(
                    ("foot_ik", "toe_ik", "hand_ik", "f_", "thumb")):
                pb.rotation_mode = "QUATERNION"
                pb.location = (0, 0, 0)
                pb.rotation_quaternion = (1, 0, 0, 0)
        tor = B["torso"]
        M = tor.bone.matrix_local.to_3x3()
        tor.rotation_quaternion = _q_local(tor, Matrix.Rotation(self.lean, 3, "X"))
        B["chest"].rotation_quaternion = _q_local(B["chest"], Matrix.Rotation(self.chest, 3, "X"))
        B["head"].rotation_quaternion = _q_local(B["head"], Matrix.Rotation(-0.85 * (self.lean + self.chest), 3, "X"))
        bpy.context.view_layer.update()
        pelvis = 0.5 * (B["ORG-thigh.L"].head + B["ORG-thigh.R"].head)
        tor.location = M.inverted() @ (self._a(self.seat) - pelvis)
        for sd in ("L", "R"):
            sx = 1 if sd == "L" else -1
            pb = B[f"foot_ik.{sd}"]
            Mr = pb.bone.matrix_local.to_3x3()
            pb.location = Mr.inverted() @ (self._a(self.pegs[sd]) - L[f"foot_ik.{sd}"].head_local)
            pb.rotation_quaternion = _q_local(pb, Matrix.Rotation(self.foot_pitch, 3, "X") @
                                              Matrix.Rotation(sx * self.toe_out, 3, "Z"))
        bpy.context.view_layer.update()
        close_hands(p, {sd: (self._a(pt), p.to_arm(fy), p.to_arm(fz)) for sd, (pt, fy, fz) in self.bars.items()})
        bpy.context.view_layer.update()


def pose_group(runners, phases, grips=None):
    """Pose several runners at once (two depsgraph updates in all)."""
    for r, ph in zip(runners, phases):
        r.stage_body(ph)
    bpy.context.view_layer.update()
    if grips:
        for r, g in zip(runners, grips):
            if g:
                r.stage_hands(g)
        bpy.context.view_layer.update()


def moustache(p, mat="hair"):
    """A full moustache over the upper lip (NCOs)."""
    V, n = p.body.verts, p.nrm
    ey = p.body.J("l-eye")
    m = (np.abs(V[:, 0]) < 0.034 * p.s) & (V[:, 2] > ey.z - 0.068 * p.s) & (V[:, 2] < ey.z - 0.047 * p.s) & \
        (n[:, 1] < -0.35) & (V[:, 1] < ey.y)
    if m.sum() > 6:
        p.shell("moustache", m, mat, 0.003 * p.s, iters=2, cover=False)
