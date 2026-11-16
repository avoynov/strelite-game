"""Real ground for the "photoreal" style: displaced soil, stones and grass tufts.

Built at real scale (metres). The height field is generated with numpy so the
relief is true geometry (it catches the sun and casts micro-shadows), not a
flat plane with a picture on it. Art-directable masks (wheel ruts, trampled
soil, grass cover) are stored per vertex in the colour attribute "masks" and
read by the "dirt" material.
"""
import math
import random

import bmesh
import bpy
import numpy as np
from PIL import Image

from . import materials

STYLE = "photoreal"


def _fbm(n, rng, octaves):
    """Sum of smooth random layers. octaves = [(cells_across, amplitude), ...]."""
    h = np.zeros((n, n), np.float32)
    for cells, amp in octaves:
        g = rng.standard_normal((cells + 3, cells + 3)).astype(np.float32)
        img = Image.fromarray(g, "F").resize((n, n), Image.BICUBIC)
        h += np.asarray(img) * amp
    return h


class Terrain:
    def __init__(self, size_m, cell=0.04, seed=7, clear_radius=2.2):
        self.size, self.seed = size_m, seed
        self.n = n = int(size_m / cell) + 1
        rng = np.random.default_rng(seed)
        s = size_m
        h = _fbm(n, rng, [(int(s / 7), 0.045), (int(s / 1.6), 0.02), (int(s / 0.45), 0.012),
                          (int(s / 0.13), 0.006)])
        ax = np.linspace(-s / 2, s / 2, n, dtype=np.float32)
        X, Y = np.meshgrid(ax, ax)          # h[iy, ix]
        r = np.sqrt(X * X + Y * Y)

        # Trampled, flatter ground around the gun (crew walks here all day).
        tramp = np.clip(1.0 - (r - clear_radius) / 3.0, 0.0, 1.0)
        tramp = tramp * tramp * (3 - 2 * tramp)
        tramp_n = _fbm(n, rng, [(int(s / 2.5), 0.5), (int(s / 0.8), 0.3)])
        tramp = np.clip(tramp * (0.75 + tramp_n), 0.0, 1.0)
        h *= 1.0 - 0.6 * tramp

        # Wheel ruts left by the towing truck: two tracks crossing the position.
        ang = math.radians(118)
        u = X * math.cos(ang) + Y * math.sin(ang)           # along the track
        v = -X * math.sin(ang) + Y * math.cos(ang) + 3.6    # across, offset from the gun
        wander = 0.3 * np.sin(u * 0.3) + 0.1 * np.sin(u * 1.1 + 1.0)
        rut_mask = np.zeros_like(h)
        for off in (-1.0, 1.0):
            d = (v + wander - off) / 0.17
            rut = np.exp(-d * d)
            tread = 0.5 + 0.5 * np.sin(u * 40.0 + off * 2.0 * np.sin(d * 3))   # tyre lugs
            h -= rut * (0.05 + 0.014 * tread)
            for side in (-1.9, 1.9):                        # squeezed-out shoulders
                dd = (v + wander - off) / 0.17 - side
                h += np.exp(-dd * dd) * 0.018
            rut_mask = np.maximum(rut_mask, rut)

        # Grass cover: patchy, kept away from the trampled zone and the ruts.
        cover = _fbm(n, rng, [(int(s / 5), 1.0), (int(s / 1.5), 0.55), (int(s / 0.4), 0.3)])
        cover = 0.5 + 0.5 * np.tanh(cover * 1.3 - 0.15)
        cover = np.clip(cover * (1.0 - tramp * 1.3) * (1.0 - rut_mask * 1.5), 0.0, 1.0)
        h += cover * 0.012                                   # turf sits slightly proud

        self.h, self.ax = h, ax
        self.rut, self.tramp, self.cover = rut_mask, tramp, cover
        self.rng = random.Random(seed)

    def _ij(self, x, y):
        k = (self.n - 1) / self.size
        i = min(max(int(round((x + self.size / 2) * k)), 0), self.n - 1)
        j = min(max(int(round((y + self.size / 2) * k)), 0), self.n - 1)
        return j, i

    def height(self, x, y):
        return float(self.h[self._ij(x, y)])

    def build(self, scene):
        n = self.n
        X, Y = np.meshgrid(self.ax, self.ax)
        co = np.stack([X, Y, self.h], axis=-1).reshape(-1, 3)
        idx = np.arange(n * n, dtype=np.int32).reshape(n, n)
        quads = np.stack([idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]], axis=-1).reshape(-1)
        nq = (n - 1) * (n - 1)
        me = bpy.data.meshes.new("terrain")
        me.vertices.add(n * n)
        me.vertices.foreach_set("co", co.reshape(-1))
        me.loops.add(nq * 4)
        me.loops.foreach_set("vertex_index", quads)
        me.polygons.add(nq)
        me.polygons.foreach_set("loop_start", np.arange(0, nq * 4, 4, dtype=np.int32))
        me.polygons.foreach_set("loop_total", np.full(nq, 4, dtype=np.int32))
        me.polygons.foreach_set("use_smooth", np.ones(nq, dtype=bool))
        me.update(calc_edges=True)
        masks = me.color_attributes.new("masks", "FLOAT_COLOR", "POINT")
        rgba = np.stack([self.rut, self.tramp, self.cover, np.ones_like(self.rut)], axis=-1)
        masks.data.foreach_set("color", rgba.reshape(-1).astype(np.float32))
        obj = bpy.data.objects.new("terrain", me)
        obj["terrain"] = True
        obj.data.materials.append(materials.get("dirt", STYLE))
        scene.collection.objects.link(obj)
        self._stones(scene)
        self._grass(scene)
        return obj

    # -- scatter -----------------------------------------------------------
    def _stones(self, scene, count=2600):
        rnd = self.rng
        variants = []
        for i in range(8):
            me = bpy.data.meshes.new(f"stone{i}")
            bm = bmesh.new()
            bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
            sx, sy, sz = rnd.uniform(0.7, 1.3), rnd.uniform(0.6, 1.1), rnd.uniform(0.4, 0.8)
            for v in bm.verts:
                k = 1.0 + rnd.uniform(-0.25, 0.25)
                v.co.x *= sx * k
                v.co.y *= sy * k
                v.co.z *= sz * k
            for f in bm.faces:
                f.smooth = rnd.random() < 0.6
            bm.to_mesh(me)
            bm.free()
            me.materials.append(materials.get("stone", STYLE))
            variants.append(me)
        half = self.size / 2 - 0.2
        for i in range(count):
            x, y = rnd.uniform(-half, half), rnd.uniform(-half, half)
            # mostly gravel, a few fist-sized stones
            r = rnd.choice([0.008, 0.01, 0.012, 0.012, 0.016, 0.02, 0.026, 0.035, 0.06]) \
                * rnd.uniform(0.7, 1.4)
            j, ii = self._ij(x, y)
            if self.tramp[j, ii] > 0.5 and r > 0.022:
                continue
            o = bpy.data.objects.new("stone", rnd.choice(variants))
            o["terrain"] = True
            o.location = (x, y, self.h[j, ii] - r * 0.12)        # half sunk in the soil
            o.scale = (r, r, r)
            o.rotation_euler = (rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), rnd.uniform(0, 6.28))
            scene.collection.objects.link(o)

    def _grass(self, scene, count=14000):
        rnd = self.rng
        variants = []
        for i in range(10):
            verts, faces = [], []
            for _ in range(rnd.randint(10, 22)):
                a = rnd.uniform(0, 6.28)
                lean = rnd.uniform(0.15, 1.0)
                ht = rnd.uniform(0.45, 1.0)
                w = rnd.uniform(0.014, 0.026)
                bx, by = rnd.uniform(-0.25, 0.25), rnd.uniform(-0.25, 0.25)
                px, py = -math.sin(a) * w, math.cos(a) * w
                base = len(verts)
                segs = 4
                for sgi in range(segs + 1):
                    t = sgi / segs
                    out = lean * t * t * ht
                    cx, cy, cz = bx + math.cos(a) * out, by + math.sin(a) * out, ht * t * (1 - 0.3 * lean * t)
                    k = 1 - t * 0.9
                    verts += [(cx - px * k, cy - py * k, cz), (cx + px * k, cy + py * k, cz)]
                for sgi in range(segs):
                    b = base + sgi * 2
                    faces.append((b, b + 1, b + 3, b + 2))
            me = bpy.data.meshes.new(f"tuft{i}")
            me.from_pydata(verts, [], faces)
            for p in me.polygons:
                p.use_smooth = True
            me.materials.append(materials.get("grass", STYLE))
            variants.append(me)
        half = self.size / 2 - 0.2
        placed = tries = 0
        while placed < count and tries < count * 10:
            tries += 1
            x, y = rnd.uniform(-half, half), rnd.uniform(-half, half)
            j, ii = self._ij(x, y)
            c = float(self.cover[j, ii])
            if rnd.random() > c * c * 1.2 + 0.006:
                continue
            o = bpy.data.objects.new("tuft", rnd.choice(variants))
            o["terrain"] = True
            s = rnd.uniform(0.10, 0.22) * (0.6 + 0.8 * c)
            o.location = (x, y, self.h[j, ii] - 0.005)
            o.scale = (s * rnd.uniform(0.8, 1.3), s * rnd.uniform(0.8, 1.3), s)
            o.rotation_euler = (0, 0, rnd.uniform(0, 6.28))
            scene.collection.objects.link(o)
            placed += 1
