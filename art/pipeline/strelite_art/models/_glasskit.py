"""Shared parts for Дяволско стъкло (models/glass.py):
lens and crystal optics, branches, rough rocks. The firing glow uses _glassbase._RIG."""
import math
import random

from mathutils import Vector

from ._glassbase import _lens, _crystal, _horn, _glyph, _glyph_band, _glyph_ring, _RIG, ROT_TY, ROT_Y  # noqa: F401
from .trebuchet import _ball  # noqa: F401


def start():
    _RIG.clear()
    _RIG["glow"] = []


def lens_optic(k, parent, R, mat, rim_mat, rim_t=0.05, tc=0.16, y=0.0):
    """A round burning lens facing +Y in a rim; returns the y of its front."""
    _lens(k, parent, R, tc, 0.05, mat, y=y)
    k.torus("rim", R + 0.02, rim_t, (0, y, 0), rim_mat, rot=ROT_TY, parent=parent, segs=40, tube_segs=10)
    g = k.cylinder("lens_glow", R * 0.55, 0.01, (0, y - 0.005, 0), "lamp_glow", segs=28, rot=ROT_Y, parent=parent,
                   bevel=False)
    _RIG["glow"].append((g, tuple(g.scale), 0.0))
    return y + tc / 2 + 0.05


def crystal_optic(k, parent, L, r, mat, c=(0, 0, 0), axis=(0, 1, 0), back=0.42):
    """A crystal with a glowing heart; returns its point."""
    tip = _crystal(k, parent, c, axis, L, r, mat, back=back)
    before = set(parent.children)
    _crystal(k, parent, Vector(c) + Vector(axis).normalized() * 0.05, axis, L * 0.55, r * 0.38, "crystal_core",
             back=0.45)
    for o in set(parent.children) - before:
        _RIG["glow"].append((o, tuple(o.scale), 1.0))
    return tip


def limb(k, parent, pts, r0, r1, mat, segs=10):
    """A bent branch, root or trunk through the points, tapering r0 -> r1."""
    pts = [Vector(p) for p in pts]
    n = len(pts) - 1
    for i in range(n):
        ra = r0 + (r1 - r0) * i / n
        rb = r0 + (r1 - r0) * (i + 1) / n
        k.tube("limb", pts[i], pts[i + 1], ra, mat, radius_end=rb, parent=parent, segs=segs, bevel=False)
        if i + 1 < n:
            _ball(k, parent, pts[i + 1], rb * 1.03, mat, subdiv=2)


def rock(k, parent, c, size, mat, rnd, rough=0.14, rot=None):
    """A rough boulder: a jittered, faceted sphere scaled to size (x, y, z)."""
    b = _ball(k, parent, c, 1.0, mat, subdiv=1)
    for v in b.data.vertices:
        v.co *= 1 + rnd.uniform(-rough, rough)
    b.scale = size
    b.rotation_euler = rot or (rnd.uniform(-0.08, 0.08), rnd.uniform(-0.08, 0.08), rnd.uniform(0, 2 * math.pi))
    return b


def stele(k, parent, base, w, d, h, mat, rnd, rough=0.14, taper=0.7, yaw=0.0):
    """A rough standing stone: a six-sided block narrowing up, its corners knocked about."""
    o = k.cylinder("stele", 1.0, 1.0, base, mat, segs=6, radius_top=taper, parent=parent, bevel=0.03)
    for v in o.data.vertices:
        v.co.x *= 1 + rnd.uniform(-rough, rough)
        v.co.y *= 1 + rnd.uniform(-rough, rough)
        if v.co.z > 0.5:
            v.co.z += rnd.uniform(-0.12, 0.05)
    o.scale = (w, d, h)
    o.rotation_euler = (rnd.uniform(-0.04, 0.04), rnd.uniform(-0.04, 0.04), yaw)
    return o


def slab(k, parent, c, size, mat, rnd, yaw=0.0, rough=0.1):
    """An uneven flat stone (a capstone)."""
    o = k.cylinder("slab", 1.0, 1.0, (c[0], c[1], c[2] - size[2] / 2), mat, segs=7, radius_top=0.92, parent=parent,
                   bevel=0.03)
    for v in o.data.vertices:
        v.co.x *= 1 + rnd.uniform(-rough, rough)
        v.co.y *= 1 + rnd.uniform(-rough, rough)
        v.co.z += rnd.uniform(-0.15, 0.15)
    o.scale = size
    o.rotation_euler = (0, 0, yaw)
    return o


def rnd_for(seed):
    return random.Random(seed)
