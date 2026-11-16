"""Procedural geometry kit. All models are built from these primitives so that
bevels, outlines and shading treatment stay uniform across every asset."""
import math

import bpy
from mathutils import Matrix, Vector

from . import materials

# Per-style treatment of edges.
BEVEL = {"stylized": (0.035, 3), "realistic": (0.008, 2)}
OUTLINE_THICKNESS = 0.022  # metres; only used by "stylized"


class Kit:
    def __init__(self, style, collection=None):
        self.style = style
        self.collection = collection or bpy.context.scene.collection

    # -- low level ---------------------------------------------------------
    def _finish(self, obj, mat_name, smooth=False, bevel=True, parent=None, outline=True):
        self.collection.objects.link(obj)
        obj.data.materials.append(materials.get(mat_name, self.style))
        if smooth:
            for p in obj.data.polygons:
                p.use_smooth = True
        if bevel:
            width, segs = BEVEL[self.style]
            m = obj.modifiers.new("Bevel", "BEVEL")
            m.width = width
            m.segments = segs
            m.limit_method = "ANGLE"
            m.angle_limit = math.radians(40)
            m.harden_normals = False
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
        f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
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


def look_rot(direction):
    """Euler that turns local +Y toward `direction`."""
    return Vector(direction).to_track_quat("Y", "Z").to_euler()
