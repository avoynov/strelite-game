"""Human figures for style В: a skinned body on a real skeleton, so soldiers, riders and
crews walk, run and sit with proper joint motion instead of being frozen statues.

Method (see SOP section "Human figures"):
  * Body parts are lofts: rings of a superellipse along a chain of stations, each
    station with its own half-width, half-depth and bone weights. Catmull-Clark
    subdivision (render level 2) turns the rings into smooth cloth and skin.
  * One armature per figure (`Rig`). Every mesh, rigid gear included, is deformed by
    an Armature modifier, so gear rides on the bone it hangs from.
  * Proportions are those of a real 1.78 m man (head 1/7.5 of height, shoulders
    0.44 m, hips at 0.93 m, knees at 0.50 m) and scale with `height`.
  * Poses are set as hinge rotations about armature-space axes (`Rig.turn`), so a
    cycle is written in plain anatomy: hip flexion, knee flexion, ankle, twist.
  * `Rig.ground()` lowers the pelvis until the lowest sole touches z = 0, so feet
    never sink into or float above the ground at any frame.

Front is local +Y, up is +Z, metres. Everything here uses Kit materials only.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))


# ---------------------------------------------------------------------------
# lofts
def loft(k, name, stations, mat, parent, side=X, segs=16, power=2.0, subsurf=2, caps=(True, True), rig=None):
    """Smooth tube through `stations`: dicts with c (centre), rx, ry, optional p (power),
    rot (radians, turns the ring about the chain) and w {bone: weight}.
    rx lies along `side` projected into the ring plane, ry across it."""
    pts = [Vector(s["c"]) for s in stations]
    n = len(pts)
    verts, rings = [], []
    for i, s in enumerate(stations):
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        sd = s.get("side", side)
        ax = (Vector(sd) - t * Vector(sd).dot(t)).normalized()
        ay = t.cross(ax)
        r0 = s.get("rot", 0.0)
        pw = s.get("p", power)
        ring = []
        for j in range(segs):
            a = 2 * math.pi * j / segs + r0
            ca, sa = math.cos(a), math.sin(a)
            u = math.copysign(abs(ca) ** (2 / pw), ca) * s["rx"]
            v = math.copysign(abs(sa) ** (2 / pw), sa) * s["ry"]
            ring.append(len(verts))
            verts.append(pts[i] + ax * u + ay * v)
        rings.append(ring)
    faces = []
    for i in range(n - 1):
        for j in range(segs):
            jj = (j + 1) % segs
            faces.append((rings[i][j], rings[i][jj], rings[i + 1][jj], rings[i + 1][j]))
    caps_idx = []
    for end, ring in ((0, rings[0]), (1, rings[-1])):
        if caps[end]:
            c = sum((verts[i] for i in ring), Vector()) / segs
            ci = len(verts)
            verts.append(c)
            caps_idx.append((ci, end))
            for j in range(segs):
                faces.append((ring[j], ring[(j + 1) % segs], ci))
    obj = organic(k, name, verts, faces, mat, parent, subsurf)
    if rig is not None:
        for i, s in enumerate(stations):
            for b, w in s.get("w", {}).items():
                vg = rig.group(obj, b)
                vg.add(rings[i], w, "REPLACE")
        for ci, end in caps_idx:
            for b, w in stations[-1 if end else 0].get("w", {}).items():
                rig.group(obj, b).add([ci], w, "REPLACE")
        rig.bind(obj)
    return obj


def organic(k, name, verts, faces, mat, parent, subsurf=2):
    """Mesh with outward normals, smooth shading and render subdivision (no bevel)."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.update()
    obj = bpy.data.objects.new(name, me)
    k.collection.objects.link(obj)
    obj.data.materials.append(k.material(mat))
    for p in me.polygons:
        p.use_smooth = True
    if subsurf:
        m = obj.modifiers.new("Subsurf", "SUBSURF")
        m.levels = 1
        m.render_levels = subsurf
    obj.parent = parent
    return obj


def ellipsoid(k, name, c, r, mat, parent, rig=None, bone=None, segs=14, rings=8, rot=None):
    """Smooth ellipsoid (half-axes r = (rx, ry, rz)), optionally turned by a quaternion."""
    v, f = [], []
    for i in range(1, rings):
        th = math.pi * i / rings
        for j in range(segs):
            ph = 2 * math.pi * j / segs
            v.append(Vector((r[0] * math.sin(th) * math.cos(ph), r[1] * math.sin(th) * math.sin(ph),
                             r[2] * math.cos(th))))
    top, bot = len(v), len(v) + 1
    v += [Vector((0, 0, r[2])), Vector((0, 0, -r[2]))]
    for i in range(rings - 2):
        for j in range(segs):
            jj = (j + 1) % segs
            f.append((i * segs + j, i * segs + jj, (i + 1) * segs + jj, (i + 1) * segs + j))
    last = (rings - 2) * segs
    for j in range(segs):
        jj = (j + 1) % segs
        f.append((top, jj, j))
        f.append((bot, last + j, last + jj))
    if rot is not None:
        v = [rot @ p for p in v]
    v = [Vector(c) + p for p in v]
    obj = organic(k, name, v, f, mat, parent, subsurf=1)
    if rig is not None:
        rig.attach(obj, bone)
    return obj


def look(d, up=Z):
    """Euler that turns local +Y onto direction d (for Kit boxes along a limb)."""
    return Vector(d).to_track_quat("Y", "Z").to_euler()


# ---------------------------------------------------------------------------
# skeleton
BONES = {   # name: (head, tail, parent) for a 1.78 m man standing, front +Y
    "pelvis": ((0, 0.0, 0.95), (0, 0.0, 1.05), None),
    "spine": ((0, 0.0, 1.05), (0, 0.01, 1.27), "pelvis"),
    "chest": ((0, 0.01, 1.27), (0, 0.0, 1.50), "spine"),
    "neck": ((0, 0.0, 1.50), (0, 0.015, 1.60), "chest"),
    "head": ((0, 0.015, 1.60), (0, 0.015, 1.80), "neck"),
    "thigh.L": ((0.095, 0.0, 0.93), (0.10, 0.01, 0.51), "pelvis"),
    "shin.L": ((0.10, 0.01, 0.51), (0.10, -0.015, 0.09), "thigh.L"),
    "foot.L": ((0.10, -0.015, 0.09), (0.10, 0.125, 0.025), "shin.L"),
    "toe.L": ((0.10, 0.125, 0.025), (0.10, 0.205, 0.02), "foot.L"),
}
for _n in [b for b in BONES if b.endswith(".L")]:
    _h, _t, _p = BONES[_n]
    BONES[_n[:-2] + ".R"] = ((-_h[0], _h[1], _h[2]), (-_t[0], _t[1], _t[2]),
                             _p[:-2] + ".R" if _p.endswith(".L") else _p)
HEEL = Vector((0.0, -0.07, 0.0))   # sole points in rest pose, relative to the ankle on the ground
TIP = Vector((0.0, 0.215, 0.0))


class Rig:
    """Armature of one figure, scaled by `height` / 1.78."""

    def __init__(self, k, parent, name="rig", height=1.78):
        self.k, self.s = k, height / 1.78
        arm = bpy.data.armatures.new(name)
        self.obj = obj = bpy.data.objects.new(name, arm)
        k.collection.objects.link(obj)
        obj.parent = parent
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
        eb = {}
        for n, (h, t, p) in BONES.items():
            b = arm.edit_bones.new(n)
            b.head, b.tail = Vector(h) * self.s, Vector(t) * self.s
            b.roll = 0.0
            eb[n] = b
        for n, (_, _, p) in BONES.items():
            if p:
                eb[n].parent = eb[p]
        bpy.ops.object.mode_set(mode="OBJECT")
        for pb in obj.pose.bones:
            pb.rotation_mode = "QUATERNION"
        self.rest = {}

    def p(self, v):
        """A rest-pose point given for the 1.78 m man, scaled to this figure."""
        return Vector(v) * self.s

    def group(self, obj, bone):
        return obj.vertex_groups.get(bone) or obj.vertex_groups.new(name=bone)

    def bind(self, obj):
        if "Armature" in obj.modifiers:
            return
        m = obj.modifiers.new("Armature", "ARMATURE")
        m.object = self.obj
        while obj.modifiers.find("Armature") > 0:          # deform first, then bevel/subdivide
            obj.modifiers.move(obj.modifiers.find("Armature"), 0)

    def attach(self, obj, bone):
        """Rigid part: every vertex follows `bone`; children of obj are attached too."""
        if obj.type == "MESH":
            self.group(obj, bone).add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
            self.bind(obj)
        for c in obj.children:
            self.attach(c, bone)

    # -- posing ----------------------------------------------------------
    def reset(self):
        for pb in self.obj.pose.bones:
            pb.rotation_quaternion = Quaternion()
            pb.location = (0, 0, 0)

    def turn(self, bone, *axis_angles):
        """Rotate a bone by hinge rotations about armature-space axes (rest frame),
        applied in order, on top of what it already has."""
        pb = self.obj.pose.bones[bone]
        inv = pb.bone.matrix_local.to_3x3().inverted()
        q = pb.rotation_quaternion.copy()
        for axis, ang in axis_angles:
            q = q @ Quaternion(inv @ Vector(axis), ang)
        pb.rotation_quaternion = q

    def shift(self, bone, d):
        pb = self.obj.pose.bones[bone]
        pb.location = pb.bone.matrix_local.to_3x3().inverted() @ Vector(d)

    def point(self, bone, rest_pt):
        """Where a rest-pose point carried by `bone` is now (armature space)."""
        pb = self.obj.pose.bones[bone]
        return pb.matrix @ pb.bone.matrix_local.inverted() @ Vector(rest_pt)

    def soles(self):
        pts = []
        for sd in ("L", "R"):
            ank = Vector(BONES["foot." + sd][0]) * self.s
            g = Vector((ank.x, ank.y, 0.0))
            pts.append(("foot." + sd, self.point("foot." + sd, g + HEEL * self.s)))
            pts.append(("foot." + sd, self.point("foot." + sd, g + Vector((0, 0.11, 0)) * self.s)))
            pts.append(("toe." + sd, self.point("toe." + sd, g + TIP * self.s)))
        return pts

    def ground(self):
        bpy.context.view_layer.update()
        low = min(p.z for _, p in self.soles())
        pb = self.obj.pose.bones["pelvis"]
        cur = pb.bone.matrix_local.to_3x3() @ pb.location
        self.shift("pelvis", cur - Vector((0, 0, low)))
        bpy.context.view_layer.update()


# ---------------------------------------------------------------------------
# gait
def _bump(x, c, w):
    """Smooth periodic bump on the unit circle of phase: 1 at c, 0 beyond +-w."""
    d = (x - c + 0.5) % 1.0 - 0.5
    return 0.5 * (1 + math.cos(math.pi * d / w)) if abs(d) < w else 0.0


def leg_angles(ph, gait):
    """Hip flexion, knee flexion, ankle dorsiflexion (radians) at phase ph in [0, 1);
    ph = 0 is this foot's heel strike."""
    if gait == "run":
        hip = math.radians(-3 + 36 * math.cos(2 * math.pi * (ph + 0.06)))
        knee = math.radians(16 + 20 * _bump(ph, 0.14, 0.14) + 95 * _bump(ph, 0.66, 0.28))
        ank = math.radians(4 + 14 * _bump(ph, 0.18, 0.16) - 24 * _bump(ph, 0.42, 0.12) + 8 * _bump(ph, 0.85, 0.15))
    else:  # walk
        hip = math.radians(4 + 21 * math.cos(2 * math.pi * (ph - 0.03)))
        knee = math.radians(4 + 14 * _bump(ph, 0.12, 0.12) + 58 * _bump(ph, 0.7, 0.2))
        ank = math.radians(2 + 8 * _bump(ph, 0.35, 0.2) - 18 * _bump(ph, 0.6, 0.1))
    return hip, knee, ank


def pose_gait(rig, ph, gait="run", lean=0.16, twist=0.09, arms=None):
    """Pose `rig` at cycle phase ph (left heel strike at 0, right at 0.5), then ground it."""
    rig.reset()
    for sd, off in (("L", 0.0), ("R", 0.5)):
        hip, knee, ank = leg_angles((ph + off) % 1.0, gait)
        rig.turn("thigh." + sd, (X, hip))
        rig.turn("shin." + sd, (X, -knee))
        rig.turn("foot." + sd, (X, ank))
        toe = 0.35 * _bump((ph + off) % 1.0, 0.45, 0.1)
        rig.turn("toe." + sd, (X, toe))
    a = 2 * math.pi * ph
    rig.turn("pelvis", (Z, twist * math.cos(a)), (Y, 0.04 * math.sin(2 * a)))
    rig.turn("spine", (X, -lean * 0.6), (Z, -twist * 0.6 * math.cos(a)))
    rig.turn("chest", (X, -lean * 0.4), (Z, -twist * 0.5 * math.cos(a)))
    rig.turn("neck", (X, lean * 0.5))
    rig.turn("head", (X, lean * 0.4), (Z, twist * 0.2 * math.cos(a)))
    rig.ground()


# ---------------------------------------------------------------------------
# body
def _w(z, table):
    """Bone weights by height: table = [(z, {bone: w}), ...] ascending; linear between rows."""
    if z <= table[0][0]:
        return dict(table[0][1])
    for (z0, w0), (z1, w1) in zip(table, table[1:]):
        if z <= z1:
            t = (z - z0) / (z1 - z0)
            out = {}
            for b in set(w0) | set(w1):
                out[b] = w0.get(b, 0.0) * (1 - t) + w1.get(b, 0.0) * t
            return out
    return dict(table[-1][1])


TORSO_W = [(0.86, {"pelvis": 1.0}), (1.02, {"pelvis": 1.0}), (1.16, {"pelvis": 0.3, "spine": 0.7}),
           (1.28, {"spine": 0.6, "chest": 0.4}), (1.36, {"chest": 1.0})]


def torso(k, rig, parent, mat="uniform", hem=0.80, bulk=1.0, flare=1.0):
    """Tunic from the hem to the collar: chest, shoulder slope, waist, hip skirt."""
    s = rig.s
    rows = [  # z, rx, ry, dy, power
        (hem, 0.19 * flare, 0.135 * flare, 0.0, 2.3),
        (hem + 0.07, 0.183, 0.125, 0.0, 2.3),
        (0.96, 0.172, 0.113, 0.0, 2.4),
        (1.05, 0.162, 0.104, 0.008, 2.4),
        (1.14, 0.158, 0.103, 0.014, 2.4),
        (1.25, 0.172, 0.112, 0.02, 2.5),
        (1.34, 0.187, 0.118, 0.02, 2.6),
        (1.41, 0.197, 0.112, 0.008, 2.8),
        (1.46, 0.178, 0.098, -0.002, 2.6),
        (1.50, 0.12, 0.085, 0.0, 2.2),
        (1.53, 0.068, 0.066, 0.005, 2.0),
    ]
    st = [dict(c=(0, dy * s, z * s), rx=rx * s * bulk, ry=ry * s * bulk, p=pw, w=_w(z, TORSO_W))
          for z, rx, ry, dy, pw in rows]
    return loft(k, "tunic", st, mat, parent, segs=20, rig=rig, caps=(True, False))


def legs(k, rig, parent, mat="uniform", boot="boot_leather", bulk=1.0, boot_top=0.27):
    s = rig.s
    out = []
    for sd, sx in (("L", 1), ("R", -1)):
        th, sh, ft, to = "thigh." + sd, "shin." + sd, "foot." + sd, "toe." + sd
        LW = [(0.12, {sh: 1.0}), (0.46, {sh: 1.0}), (0.57, {th: 1.0}), (0.86, {th: 1.0}),
              (0.98, {th: 0.55, "pelvis": 0.45})]
        rows = [  # z, rx, ry, dy, dx
            (boot_top - 0.04, 0.05, 0.054, -0.012, 0.0),
            (boot_top + 0.02, 0.058, 0.06, -0.012, 0.0),       # trouser bloused over the boot
            (boot_top + 0.07, 0.056, 0.062, -0.018, 0.0),
            (0.37, 0.058, 0.066, -0.02, 0.0),                  # calf
            (0.45, 0.054, 0.06, -0.006, 0.0),
            (0.51, 0.057, 0.061, 0.01, 0.0),                    # knee
            (0.58, 0.064, 0.068, 0.012, 0.0),
            (0.70, 0.074, 0.078, 0.01, 0.0),
            (0.82, 0.084, 0.088, 0.004, -0.004),
            (0.92, 0.094, 0.10, -0.004, -0.012),
            (0.99, 0.10, 0.105, -0.006, -0.02),
        ]
        st = []
        for z, rx, ry, dy, dx in rows:
            xc = 0.095 + 0.005 * (1 - min(1, max(0, (z - 0.5) / 0.43)))
            st.append(dict(c=(sx * (xc + dx) * s, dy * s, z * s), rx=rx * s * bulk, ry=ry * s * bulk,
                           w=_w(z, LW)))
        out.append(loft(k, "trousers", st, mat, parent, segs=14, rig=rig))
        # boot: shaft, then the foot as a loft along +Y, a sole and a heel
        shaft = [dict(c=(sx * 0.10 * s, -0.012 * s, z * s), rx=r * s, ry=r * 1.08 * s, w={sh: 1.0})
                 for z, r in ((0.075, 0.047), (0.13, 0.046), (boot_top - 0.06, 0.049), (boot_top, 0.053))]
        loft(k, "boot_shaft", shaft, boot, parent, segs=14, rig=rig)
        fr = [  # y, rx, rz, zc
            (-0.075, 0.034, 0.036, 0.062), (-0.05, 0.044, 0.05, 0.068), (0.0, 0.048, 0.06, 0.07),
            (0.06, 0.05, 0.048, 0.06), (0.12, 0.05, 0.036, 0.048), (0.17, 0.046, 0.03, 0.043),
            (0.205, 0.034, 0.026, 0.04), (0.222, 0.016, 0.018, 0.04)]
        st = [dict(c=(sx * 0.10 * s, y * s, zc * s), rx=rx * s, ry=rz * s, side=X, p=2.4,
                   w={to: 1.0} if y > 0.15 else ({ft: 0.5, to: 0.5} if y > 0.1 else {ft: 1.0}))
              for y, rx, rz, zc in fr]
        loft(k, "boot_foot", st, boot, parent, segs=14, rig=rig)
        sole_f = k.box("sole", (0.1 * s, 0.13 * s, 0.024 * s), (sx * 0.10 * s, 0.15 * s, 0.014 * s), "iron_black",
                       parent=parent, bevel=0.008)
        sole_b = k.box("sole", (0.094 * s, 0.13 * s, 0.024 * s), (sx * 0.10 * s, 0.0, 0.014 * s), "iron_black",
                       parent=parent, bevel=0.008)
        heel = k.box("heel", (0.085 * s, 0.075 * s, 0.03 * s), (sx * 0.10 * s, -0.04 * s, 0.017 * s), "boot_leather",
                     parent=parent, bevel=0.006)
        rig.attach(sole_f, to)
        rig.attach(sole_b, ft)
        rig.attach(heel, ft)
        for i in range(3):                                   # lace hooks up the shaft front
            h = k.cylinder("hook", 0.006 * s, 0.01 * s, (sx * (0.10 * s), (0.04 + 0.002 * i) * s, (0.12 + 0.04 * i) * s),
                           "brass", segs=6, rot=(math.pi / 2, 0, 0), parent=parent, bevel=False)
            rig.attach(h, sh)
    return out


def neck_head(k, rig, parent, skin="skin", face=None):
    """Neck and head with a face: jaw, cheekbones, brow ridge, nose, ears, eye sockets.
    `face` tunes it: nose (length scale), jaw (width scale), brow, moustache."""
    s = rig.s
    f = dict(nose=1.0, jaw=1.0, brow=1.0, moustache=False)
    f.update(face or {})
    loft(k, "neck", [dict(c=(0, 0.0, 1.48 * s), rx=0.058 * s, ry=0.06 * s, w={"chest": 1.0}),
                     dict(c=(0, 0.01 * s, 1.55 * s), rx=0.052 * s, ry=0.055 * s, w={"neck": 1.0}),
                     dict(c=(0, 0.02 * s, 1.61 * s), rx=0.05 * s, ry=0.055 * s, w={"head": 1.0})],
         skin, parent, segs=12, rig=rig, caps=(False, False))
    j = f["jaw"]
    rows = [  # z, rx, ry, dy
        (1.565, 0.026 * j, 0.02, 0.078), (1.578, 0.05 * j, 0.044, 0.062), (1.60, 0.062 * j, 0.072, 0.034),
        (1.63, 0.068, 0.088, 0.02), (1.665, 0.074, 0.097, 0.012), (1.70, 0.078, 0.1, 0.006),
        (1.735, 0.079, 0.101, 0.0), (1.77, 0.073, 0.094, -0.006), (1.795, 0.058, 0.074, -0.01),
        (1.812, 0.03, 0.04, -0.012)]
    st = [dict(c=(0, (0.015 + dy) * s, z * s), rx=rx * s, ry=ry * s, p=2.15, w={"head": 1.0})
          for z, rx, ry, dy in rows]
    head = loft(k, "head", st, skin, parent, segs=18, rig=rig)
    fy = lambda z: 0.015 + 0.012 + 0.097  # noqa: E731  front of the face at cheek level
    parts = []
    # brow ridge, cheekbones, chin
    parts.append(ellipsoid(k, "brow", (0, (fy(0) - 0.01) * s, 1.712 * s), (0.06 * s, 0.022 * s, 0.014 * s * f["brow"]),
                           skin, parent))
    for sx in (-1, 1):
        parts.append(ellipsoid(k, "cheek", (sx * 0.045 * s, (fy(0) - 0.03) * s, 1.67 * s),
                               (0.026 * s, 0.02 * s, 0.018 * s), skin, parent))
        # eye: dark socket shadow then a small glossy eyeball under the brow
        parts.append(ellipsoid(k, "eye", (sx * 0.031 * s, (fy(0) - 0.012) * s, 1.694 * s),
                               (0.013 * s, 0.008 * s, 0.008 * s), "glass", parent))
        parts.append(ellipsoid(k, "ear", (sx * 0.079 * s, -0.0 * s, 1.68 * s), (0.012 * s, 0.024 * s, 0.032 * s),
                               skin, parent))
    parts.append(ellipsoid(k, "chin", (0, 0.09 * s, 1.578 * s), (0.026 * s, 0.018 * s, 0.017 * s), skin, parent))
    # nose: a wedge from the brow down to the tip
    nl = f["nose"]
    tip = Vector((0, (fy(0) + 0.022 * nl) * s, 1.655 * s))
    bridge = Vector((0, (fy(0) + 0.002) * s, 1.70 * s))
    parts.append(loft(k, "nose", [dict(c=bridge, rx=0.008 * s, ry=0.006 * s),
                                  dict(c=bridge.lerp(tip, 0.6), rx=0.011 * s, ry=0.01 * s),
                                  dict(c=tip, rx=0.016 * s, ry=0.011 * s),
                                  dict(c=tip + Vector((0, -0.012, -0.008)) * s, rx=0.012 * s, ry=0.006 * s)],
                      skin, parent, segs=10, side=X, subsurf=1))
    parts.append(k.box("mouth", (0.034 * s, 0.006 * s, 0.004 * s), (0, (fy(0) - 0.004) * s, 1.622 * s), "boot",
                       parent=parent, bevel=False))
    if f["moustache"]:
        for sx in (-1, 1):
            parts.append(ellipsoid(k, "moustache", (sx * 0.016 * s, (fy(0) + 0.002) * s, 1.634 * s),
                                   (0.02 * s, 0.009 * s, 0.007 * s), "boot", parent,
                                   rot=Quaternion(Y, sx * 0.25)))
    for p in parts:
        rig.attach(p, "head")
    return head


def arm(k, rig, parent, shoulder, elbow, wrist, mat="uniform", bone="chest", bulk=1.0):
    """Sleeve along a posed path (arms hold a weapon or a handlebar, so they ride on
    the chest bone as one piece), with a cuff. Points in metres for the 1.78 m man."""
    s = rig.s
    sh, el, wr = rig.p(shoulder), rig.p(elbow), rig.p(wrist)
    side = (sh - el).cross(wr - el)
    if side.length < 1e-6:
        side = X
    st = [dict(c=sh + (sh - el).normalized() * 0.025 * s, rx=0.062 * s * bulk, ry=0.07 * s * bulk),
          dict(c=sh.lerp(el, 0.12), rx=0.072 * s * bulk, ry=0.072 * s * bulk),     # deltoid
          dict(c=sh.lerp(el, 0.45), rx=0.058 * s * bulk, ry=0.062 * s * bulk),
          dict(c=sh.lerp(el, 0.85), rx=0.05 * s * bulk, ry=0.052 * s * bulk),
          dict(c=el, rx=0.048 * s * bulk, ry=0.05 * s * bulk),
          dict(c=el.lerp(wr, 0.28), rx=0.054 * s * bulk, ry=0.052 * s * bulk),     # forearm
          dict(c=el.lerp(wr, 0.75), rx=0.042 * s * bulk, ry=0.04 * s * bulk),
          dict(c=el.lerp(wr, 0.86), rx=0.048 * s * bulk, ry=0.047 * s * bulk),     # cuff
          dict(c=wr, rx=0.046 * s * bulk, ry=0.045 * s * bulk)]
    for d in st:
        d["w"] = {bone: 1.0}
    return loft(k, "sleeve", st, mat, parent, segs=12, side=side, rig=rig)


def grip_hand(k, rig, parent, wrist, grip_axis, palm_dir, mat="leather", bone="chest"):
    """Gloved hand closed round a bar: palm block, four curled fingers, thumb over the top.
    wrist: wrist point; grip_axis: direction of the bar through the fist;
    palm_dir: from the wrist toward the knuckles."""
    s = rig.s
    w = rig.p(wrist)
    ga = Vector(grip_axis).normalized()
    fwd = (Vector(palm_dir) - ga * Vector(palm_dir).dot(ga)).normalized()
    up = ga.cross(fwd)
    parts = [loft(k, "palm", [dict(c=w - fwd * 0.01 * s, rx=0.03 * s, ry=0.024 * s),
                              dict(c=w + fwd * 0.04 * s, rx=0.045 * s, ry=0.022 * s, p=3),
                              dict(c=w + fwd * 0.075 * s, rx=0.044 * s, ry=0.02 * s, p=3)],
                  mat, parent, segs=12, side=ga, subsurf=1)]
    bar = w + fwd * 0.09 * s - up * 0.025 * s                # centre of the bar held
    for i in range(4):
        off = ga * ((0.027 - 0.018 * i) * s)
        pts = []
        for a in (100, 40, -30, -95):                       # knuckle over the bar and round it
            r = math.radians(a)
            pts.append(bar + off + (fwd * math.cos(r) * 0.024 + up * math.sin(r) * 0.024) * s)
        st = [dict(c=p, rx=(0.0095 - 0.0015 * (i == 3)) * s, ry=0.009 * s) for p in pts]
        parts.append(loft(k, "finger", st, mat, parent, segs=8, side=ga, subsurf=1))
    th0 = w + (fwd * 0.03 + ga * 0.035 + up * 0.0) * s
    parts.append(loft(k, "thumb", [dict(c=th0, rx=0.013 * s, ry=0.012 * s),
                                   dict(c=bar + ga * 0.035 * s + up * 0.018 * s, rx=0.011 * s, ry=0.01 * s),
                                   dict(c=bar + ga * 0.02 * s + up * 0.026 * s + fwd * 0.01 * s, rx=0.01 * s,
                                        ry=0.009 * s)], mat, parent, segs=8, side=fwd, subsurf=1))
    for p in parts:
        rig.attach(p, bone)
    return parts
