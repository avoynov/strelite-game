"""Procedural geometry kit. All models are built from these primitives so that
bevels, outlines and shading treatment stay uniform across every asset."""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import materials

# Per-style treatment of edges.
# "photoreal" models are built at real-world size, so its bevel is a real 6 mm chamfer.
BEVEL = {"stylized": (0.035, 3), "realistic": (0.008, 2), "photoreal": (0.006, 2)}
OUTLINE_THICKNESS = 0.022  # metres; only used by "stylized"
# The game export switches geometric bevels off (the chamfers go into the baked
# normal map instead), which cuts the triangle count several times.
OPTIONS = {"bevel": True}


class Kit:
    def __init__(self, style, collection=None):
        self.style = style
        self.collection = collection or bpy.context.scene.collection

    def material(self, name):
        return materials.get(name, self.style)

    # -- low level ---------------------------------------------------------
    def _finish(self, obj, mat_name, smooth=False, bevel=True, parent=None, outline=True):
        self.collection.objects.link(obj)
        obj.data.materials.append(self.material(mat_name))
        photoreal = self.style == "photoreal"
        if photoreal:
            _smooth_by_angle(obj.data, math.radians(35))
        elif smooth:
            for p in obj.data.polygons:
                p.use_smooth = True
        if bevel and OPTIONS["bevel"]:
            width, segs = BEVEL[self.style]
            if not isinstance(bevel, bool):
                width = float(bevel)  # per-part override (metres)
            m = obj.modifiers.new("Bevel", "BEVEL")
            m.width = width
            m.segments = segs
            m.limit_method = "ANGLE"
            m.angle_limit = math.radians(35 if photoreal else 40)
            m.harden_normals = photoreal
        if self.style == "stylized" and outline:
            obj.data.materials.append(materials.outline_material())
            s = obj.modifiers.new("Outline", "SOLIDIFY")
            s.thickness = OUTLINE_THICKNESS
            s.offset = 1.0
            s.use_flip_normals = True
            s.use_rim = False
            s.material_offset = 1
        if parent is not None:
            obj.parent = parent
        return obj

    def mesh(self, name, verts, faces):
        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], faces)
        me.update()
        return bpy.data.objects.new(name, me)

    # -- primitives --------------------------------------------------------
    def box(self, name, size, loc, mat, rot=(0, 0, 0), parent=None, bevel=True, outline=True):
        sx, sy, sz = (s / 2 for s in size)
        v = [(x * sx, y * sy, z * sz) for z in (-1, 1) for y in (-1, 1) for x in (-1, 1)]
        # wound so that normals point outwards (needed for baking and backface culling)
        f = [(2, 3, 1, 0), (5, 7, 6, 4), (1, 5, 4, 0), (6, 7, 3, 2), (4, 6, 2, 0), (3, 7, 5, 1)]
        obj = self.mesh(name, v, f)
        obj.location = loc
        obj.rotation_euler = rot
        return self._finish(obj, mat, bevel=bevel, parent=parent, outline=outline)

    def cylinder(self, name, radius, height, loc, mat, segs=24, rot=(0, 0, 0), parent=None,
                 smooth=None, radius_top=None, bevel=True, outline=True):
        rt = radius if radius_top is None else radius_top
        v, f = [], []
        for i in range(segs):
            a = 2 * math.pi * i / segs + (math.pi / segs if segs <= 8 else 0)
            v.append((radius * math.cos(a), radius * math.sin(a), 0))
            v.append((rt * math.cos(a), rt * math.sin(a), height))
        for i in range(segs):
            j = (i + 1) % segs
            f.append((2 * i, 2 * j, 2 * j + 1, 2 * i + 1))
        f.append(tuple(2 * i for i in reversed(range(segs))))
        f.append(tuple(2 * i + 1 for i in range(segs)))
        obj = self.mesh(name, v, f)
        obj.location = loc
        obj.rotation_euler = rot
        if smooth is None:
            smooth = segs > 8
        return self._finish(obj, mat, smooth=smooth, bevel=bevel, parent=parent, outline=outline)

    def lathe(self, name, profile, mat, segs=28, loc=(0, 0, 0), rot=(0, 0, 0), parent=None,
              outline=True):
        """Revolve a (y, radius) profile around the local +Y axis. Used for barrels."""
        v, f = [], []
        rings = len(profile)
        for (y, r) in profile:
            for i in range(segs):
                a = 2 * math.pi * i / segs
                v.append((r * math.cos(a), y, r * math.sin(a)))
        for k in range(rings - 1):
            for i in range(segs):
                j = (i + 1) % segs
                a, b = k * segs + i, k * segs + j
                f.append((a, a + segs, b + segs, b))
        # caps
        v.append((0, profile[0][0], 0))
        c0 = len(v) - 1
        v.append((0, profile[-1][0], 0))
        c1 = len(v) - 1
        last = (rings - 1) * segs
        for i in range(segs):
            j = (i + 1) % segs
            f.append((c0, j, i))
            f.append((c1, last + i, last + j))
        obj = self.mesh(name, v, f)
        obj.location = loc
        obj.rotation_euler = rot
        return self._finish(obj, mat, smooth=True, bevel=False, parent=parent, outline=outline)

    def empty(self, name, loc=(0, 0, 0), parent=None):
        e = bpy.data.objects.new(name, None)
        e.location = loc
        self.collection.objects.link(e)
        if parent is not None:
            e.parent = parent
        return e

    def ring(self, name, radius, height, z, mat, segs=24, parent=None, thickness=0.03):
        """Thin band around a cylinder (iron/brass hoops)."""
        return self.cylinder(name, radius + thickness, height, (0, 0, z), mat, segs=segs,
                             parent=parent, bevel=False)

    def flag(self, name, width, height, loc, mat, parent=None, waves=2, amp=0.05):
        """Waving cloth strip, attached on its left edge (pennant)."""
        nx, nz = 10, 4
        v, f = [], []
        for iz in range(nz + 1):
            for ix in range(nx + 1):
                t = ix / nx
                taper = 1 - 0.55 * t  # pennant tapers toward the tip
                z = (iz / nz - 0.5) * height * taper
                y = amp * t * math.sin(t * math.pi * waves)
                v.append((t * width, y, z))
        for iz in range(nz):
            for ix in range(nx):
                a = iz * (nx + 1) + ix
                f.append((a, a + 1, a + nx + 2, a + nx + 1))
        obj = self.mesh(name, v, f)
        obj.location = loc
        m = obj.modifiers.new("Thick", "SOLIDIFY")
        m.thickness = 0.015
        return self._finish(obj, mat, smooth=True, bevel=False, parent=parent)


    # -- real-scale helpers (used by the photoreal models) -------------------
    def tube(self, name, p0, p1, radius, mat, radius_end=None, segs=20, parent=None, bevel=True):
        """Cylinder running from point p0 to point p1."""
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        return self.cylinder(name, radius, d.length, p0, mat, segs=segs,
                             rot=d.to_track_quat("Z", "Y").to_euler(), parent=parent,
                             radius_top=radius_end, bevel=bevel, outline=False)

    def beam(self, name, p0, p1, section, mat, section_end=None, parent=None, bevel=True):
        """Box-section beam from p0 to p1. section = (width, height); may taper."""
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        w0, h0 = section
        w1, h1 = section_end or section
        v = []
        for z, w, h in ((0, w0, h0), (d.length, w1, h1)):
            v += [(-w / 2, -h / 2, z), (w / 2, -h / 2, z), (w / 2, h / 2, z), (-w / 2, h / 2, z)]
        f = [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        obj = self.mesh(name, v, f)
        obj.location = p0
        obj.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
        return self._finish(obj, mat, bevel=bevel, parent=parent, outline=False)

    def plate(self, name, outline_yz, thickness, x, mat, parent=None, bevel=True):
        """Flat plate cut from a (y, z) outline (counter-clockwise), extruded along X."""
        n = len(outline_yz)
        v = [(x - thickness / 2, y, z) for y, z in outline_yz]
        v += [(x + thickness / 2, y, z) for y, z in outline_yz]
        f = [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
        for i in range(n):
            j = (i + 1) % n
            f.append((i, j, j + n, i + n))
        return self._finish(self.mesh(name, v, f), mat, bevel=bevel, parent=parent, outline=False)

    def prism(self, name, outline_xz, thickness, mat, y=0.0, parent=None, bevel=True):
        """Flat plate cut from an (x, z) outline (any winding, may be concave),
        thickness along Y. Used for shields and armour plates."""
        n = len(outline_xz)
        v = [(x, y - thickness / 2, z) for x, z in outline_xz]
        v += [(x, y + thickness / 2, z) for x, z in outline_xz]
        f = [tuple(range(n)), tuple(reversed(range(n, 2 * n)))]
        for i in range(n):
            j = (i + 1) % n
            f.append((i, j, j + n, i + n))
        obj = self.mesh(name, v, f)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(obj.data)
        bm.free()
        return self._finish(obj, mat, bevel=bevel, parent=parent, outline=False)

    def torus(self, name, radius, tube_radius, loc, mat, rot=(0, 0, 0), parent=None,
              segs=32, tube_segs=10):
        """Ring around the local Z axis."""
        v, f = [], []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            for j in range(tube_segs):
                b = 2 * math.pi * j / tube_segs
                r = radius + tube_radius * math.cos(b)
                v.append((r * math.cos(a), r * math.sin(a), tube_radius * math.sin(b)))
        for i in range(segs):
            for j in range(tube_segs):
                a, b = i * tube_segs + j, i * tube_segs + (j + 1) % tube_segs
                c, d = ((i + 1) % segs) * tube_segs + (j + 1) % tube_segs, ((i + 1) % segs) * tube_segs + j
                f.append((a, d, c, b))
        obj = self.mesh(name, v, f)
        obj.location = loc
        obj.rotation_euler = rot
        return self._finish(obj, mat, smooth=True, bevel=False, parent=parent, outline=False)

    def hose(self, name, points, radius, mat, parent=None):
        """Flexible hose / cable through the given points (smooth curve)."""
        cu = bpy.data.curves.new(name, "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = radius
        cu.bevel_resolution = 3
        sp = cu.splines.new("NURBS")
        sp.points.add(len(points) - 1)
        for pt, co in zip(sp.points, points):
            pt.co = (*co, 1.0)
        sp.use_endpoint_u = True
        sp.order_u = min(4, len(points))
        sp.resolution_u = 8
        obj = bpy.data.objects.new(name, cu)
        self.collection.objects.link(obj)
        cu.materials.append(self.material(mat))
        if parent is not None:
            obj.parent = parent
        return obj


def _smooth_by_angle(me, angle):
    """Shade smooth, but keep edges sharper than `angle` crisp (hard-surface look)."""
    bm = bmesh.new()
    bm.from_mesh(me)
    for face in bm.faces:
        face.smooth = True
    for e in bm.edges:
        e.smooth = len(e.link_faces) == 2 and e.calc_face_angle() < angle
    bm.to_mesh(me)
    bm.free()


def look_rot(direction):
    """Euler that turns local +Y toward `direction`."""
    return Vector(direction).to_track_quat("Y", "Z").to_euler()
