"""Shared construction kit for the base's buildings (headquarters, laboratory): real
masonry, log and plank walls, roofs of real shingles, slates or plates, windows,
doors and masts. Walls are built block by block so joints, courses and corners
read at game zoom the way the walls (fences.py) do.

The camera sees the +X and -Y faces of a building (screen lower right and lower
left), so doors, signs and the defender emblem go there.
"""
import math
import random

from mathutils import Vector

FRONT = Vector((0, -1, 0))      # the face toward screen lower left
SIDE = Vector((1, 0, 0))        # the face toward screen lower right


def _dir(p0, p1):
    d = Vector((p1[0] - p0[0], p1[1] - p0[1], 0))
    return d.length, d.normalized()


def masonry(k, parent, p0, p1, z0, h, t, rnd, mat="stone", course=0.32, unit=(0.45, 0.95), mortar="slate",
            rough=0.02, skip=(), name="block"):
    """Wall of stone blocks from p0 to p1 (ground plan), bottom z0, height h, thickness t.
    Courses of `course` m, blocks `unit` m long, running bond, dark mortar bed behind.
    skip: (s0, s1, za, zb) openings along the wall (s in metres from p0)."""
    L, d = _dir(p0, p1)
    n = Vector((-d.y, d.x, 0))
    yaw = math.atan2(d.y, d.x)
    c = Vector((p0[0], p0[1], 0)) + d * (L / 2)
    k.box("mortar", (L - 0.02, t * 0.8, h - 0.02), c + Vector((0, 0, z0 + h / 2)), mortar, rot=(0, 0, yaw),
          parent=parent, bevel=False)
    rows = max(1, round(h / course))
    ch = h / rows
    for r in range(rows):
        z = z0 + r * ch
        s = -rnd.uniform(0, unit[1]) if r % 2 else 0.0
        while s < L:
            ln = rnd.uniform(*unit)
            a, b = max(s, 0.0), min(s + ln, L)
            s += ln
            pieces = [(a, b)]
            for s0, s1, za, zb in skip:                      # cut the block round an opening
                if z + ch > za + 0.01 and z < zb - 0.01:
                    pieces = [q for x0, x1 in pieces for q in ((x0, min(x1, s0)), (max(x0, s1), x1)) if q[1] - q[0] > 0]
            for a, b in pieces:
                if b - a < 0.1:
                    continue
                m = (a + b) / 2
                j = 0.012 + rnd.uniform(0, rough)
                pos = Vector((p0[0], p0[1], 0)) + d * m + n * rnd.uniform(-rough, rough) * 0.6
                k.box(name, (b - a - j, t + rnd.uniform(0, rough), ch - j), pos + Vector((0, 0, z + ch / 2)), mat,
                      rot=(0, 0, yaw + rnd.uniform(-0.01, 0.01)), parent=parent, bevel=0.02 + rough * 0.6)


def logs(k, parent, p0, p1, z0, h, r, rnd, mat="log", over=0.25, skip=(), phase=0):
    """Horizontal log wall with notched corners: logs run past the ends by `over`."""
    L, d = _dir(p0, p1)
    n = int(h / (2 * r * 0.92))
    for i in range(n):
        if (i + phase) % 2:
            continue
        z = z0 + r + i * 2 * r * 0.92
        a, b = -over, L + over
        segs = [(a, b)]
        for s0, s1, za, zb in skip:
            if za < z < zb:
                segs = [(x0, min(x1, s0)) for x0, x1 in segs if x0 < s0] + \
                       [(max(x0, s1), x1) for x0, x1 in segs if x1 > s1]
        for x0, x1 in segs:
            if x1 - x0 < 0.2:
                continue
            q0 = Vector((p0[0], p0[1], z)) + d * x0
            q1 = Vector((p0[0], p0[1], z)) + d * x1
            rr = r * rnd.uniform(0.9, 1.08)
            k.tube("log", q0, q1, rr, mat, radius_end=rr * rnd.uniform(0.88, 1.0), parent=parent, segs=12)
    return n


def planks(k, parent, p0, p1, z0, h, t, rnd, mat="timber_tarred", w=0.22, vertical=True, skip=()):
    L, d = _dir(p0, p1)
    yaw = math.atan2(d.y, d.x)
    n = int(L / w)
    for i in range(n):
        s = (i + 0.5) * L / n
        if any(s0 < s < s1 for s0, s1, za, zb in skip):
            for s0, s1, za, zb in skip:
                if s0 < s < s1:
                    for lo, hi in ((z0, za), (zb, z0 + h)):
                        if hi - lo > 0.05:
                            pos = Vector((p0[0], p0[1], (lo + hi) / 2)) + d * s
                            k.box("plank", (L / n - 0.012, t, hi - lo), pos, mat, rot=(0, 0, yaw), parent=parent,
                                  bevel=0.008)
            continue
        hh = h + rnd.uniform(-0.01, 0.01)
        pos = Vector((p0[0], p0[1], z0 + hh / 2)) + d * s
        k.box("plank", (L / n - 0.012, t, hh), pos, mat, rot=(0, 0, yaw + rnd.uniform(-0.004, 0.004)), parent=parent,
              bevel=0.008)


def gable_roof(k, parent, x0, x1, y0, y1, z, rise, rnd, mat, unit=(0.32, 0.22), over=0.3, thick=0.03,
               ridge_mat=None, along="x", jitter=0.02):
    """Gable roof of overlapping shingles or slates (`unit` = exposed width, course).
    Ridge runs along X (along="x") or Y. Eaves overhang by `over`."""
    if along == "y":
        x0, x1, y0, y1 = y0, y1, x0, x1
    half = (y1 - y0) / 2 + over
    yc = (y0 + y1) / 2
    slope = math.atan2(rise, (y1 - y0) / 2)
    length = half / math.cos(slope)
    rows = max(2, int(length / unit[1]))
    span = (x1 - x0) + 2 * over
    for side in (-1, 1):
        for r in range(rows):
            u = (r + 0.5) / rows * length               # from the eave upward
            hy = half - u * math.cos(slope)
            zz = z + (half - hy) * math.tan(slope) - over * math.tan(slope)
            off = rnd.uniform(0, unit[0]) if r % 2 else 0.0
            sx = -span / 2 - off
            while sx < span / 2:
                w = unit[0] * rnd.uniform(0.85, 1.15)
                a, b = max(sx, -span / 2), min(sx + w, span / 2)
                sx += w
                if b - a < 0.06:
                    continue
                cx = (x0 + x1) / 2 + (a + b) / 2
                cy = yc + side * hy
                rot = (-side * slope + rnd.uniform(-jitter, jitter), rnd.uniform(-jitter, jitter) * 0.5, 0)
                loc, size = (cx, cy, zz + 0.02), (b - a - 0.012, length / rows * 1.45, thick)
                if along == "y":
                    loc, size = (cy, cx, zz + 0.02), (length / rows * 1.45, b - a - 0.012, thick)
                    rot = (rnd.uniform(-jitter, jitter) * 0.5, side * slope + rnd.uniform(-jitter, jitter), 0)
                k.box("shingle", size, loc, mat, rot=rot, parent=parent, bevel=0.006)
    rz = z + ((y1 - y0) / 2) * math.tan(slope)
    for side in (-1, 1):                                     # boarded deck under the covering
        cy = yc + side * half / 2
        cz = rz - (half / 2) * math.tan(slope) - 0.03
        loc, size, rot = ((x0 + x1) / 2, cy, cz), (span, length, 0.03), (-side * slope, 0, 0)
        if along == "y":
            loc, size, rot = (cy, (x0 + x1) / 2, cz), (length, span, 0.03), (0, side * slope, 0)
        k.box("roof_deck", size, loc, "timber_tarred", rot=rot, parent=parent, bevel=False)
    rm = ridge_mat or mat
    if along == "y":
        k.beam("ridge", ((x0 + x1) / 2 * 0 + yc, x0 - over, rz + 0.04), (yc, x1 + over, rz + 0.04), (0.16, 0.1), rm,
               parent=parent)
    else:
        k.beam("ridge", (x0 - over, yc, rz + 0.04), (x1 + over, yc, rz + 0.04), (0.16, 0.1), rm, parent=parent)
    return rz


def gable_ends(k, parent, x0, x1, y0, y1, z, rz, mat, t=0.2, along="x"):
    """Triangular gable walls closing the roof ends."""
    if along == "x":
        yc = (y0 + y1) / 2
        for x in (x0, x1):
            k.plate("gable", [(y0, z), (y1, z), (yc, rz)], t, x, mat, parent=parent)
    else:
        xc = (x0 + x1) / 2
        for y in (y0, y1):
            k.prism("gable", [(x0, z), (x1, z), (xc, rz)], t, mat, y=y, parent=parent)


def window(k, parent, centre, normal, w, h, frame="timber_tarred", glass="glass", panes=(2, 2), sill="stone",
           shutters=None):
    """Window set into a wall face: frame, sill, mullions, glass. normal points out."""
    n = Vector(normal).normalized()
    yaw = math.atan2(n.y, n.x) + math.pi / 2
    c = Vector(centre)
    tx = Vector((math.cos(yaw), math.sin(yaw), 0))
    k.box("glass", (w, 0.02, h), c - n * 0.04, glass, rot=(0, 0, yaw), parent=parent, bevel=False)
    k.box("frame_top", (w + 0.12, 0.1, 0.07), c + n * 0.02 + Vector((0, 0, h / 2 + 0.03)), frame, rot=(0, 0, yaw),
          parent=parent, bevel=0.01)
    k.box("sill", (w + 0.2, 0.18, 0.06), c + n * 0.06 - Vector((0, 0, h / 2 + 0.03)), sill, rot=(0, 0, yaw),
          parent=parent, bevel=0.01)
    for sx in (-1, 1):
        k.box("jamb", (0.06, 0.1, h), c + n * 0.02 + tx * sx * (w / 2 + 0.03), frame, rot=(0, 0, yaw), parent=parent,
              bevel=0.008)
    for i in range(1, panes[0]):
        k.box("mullion", (0.035, 0.05, h), c + tx * (-w / 2 + w * i / panes[0]), frame, rot=(0, 0, yaw),
              parent=parent, bevel=False)
    for i in range(1, panes[1]):
        k.box("transom", (w, 0.05, 0.035), c + Vector((0, 0, -h / 2 + h * i / panes[1])), frame, rot=(0, 0, yaw),
              parent=parent, bevel=False)
    if shutters:
        for sx in (-1, 1):
            k.box("shutter", (w / 2, 0.035, h + 0.05), c + n * 0.08 + tx * sx * (w * 0.75 + 0.08), shutters,
                  rot=(0, 0, yaw), parent=parent, bevel=0.008)


def door(k, parent, centre_bottom, normal, w, h, mat="timber_oak", strap="iron_black", arch=False):
    n = Vector(normal).normalized()
    yaw = math.atan2(n.y, n.x) + math.pi / 2
    c = Vector(centre_bottom)
    tx = Vector((math.cos(yaw), math.sin(yaw), 0))
    k.box("door_recess", (w + 0.04, 0.05, h), c - n * 0.06 + Vector((0, 0, h / 2)), "iron_black", rot=(0, 0, yaw),
          parent=parent, bevel=False)
    nb = 4
    for i in range(nb):
        k.box("door_board", (w / nb - 0.01, 0.05, h - 0.02), c - n * 0.02 + tx * (-w / 2 + (i + 0.5) * w / nb)
              + Vector((0, 0, h / 2)), mat, rot=(0, 0, yaw), parent=parent, bevel=0.006)
    for z in (0.25, h - 0.3):
        k.box("door_strap", (w * 0.85, 0.02, 0.06), c + n * 0.015 + tx * (-w * 0.06) + Vector((0, 0, z)), strap,
              rot=(0, 0, yaw), parent=parent, bevel=False)
    k.torus("door_ring", 0.05, 0.008, c + n * 0.03 + tx * (w * 0.3) + Vector((0, 0, h * 0.5)), "iron_black",
            rot=(math.pi / 2, 0, yaw), parent=parent, segs=12, tube_segs=4)
    k.box("door_step", (w + 0.3, 0.35, 0.12), c + n * 0.18 + Vector((0, 0, 0.06)), "stone", rot=(0, 0, yaw),
          parent=parent, bevel=0.02)


def flag_mast(k, parent, base, h, mat="timber_honey", flag="paint_blue", w=1.1, finial="brass"):
    """Mast with halyard, a blue defender flag and a finial."""
    base = Vector(base)
    k.tube("mast", base, base + Vector((0, 0, h)), 0.06, mat, radius_end=0.04, parent=parent, segs=12)
    k.cylinder("finial", 0.07, 0.12, base + Vector((0, 0, h)), finial, segs=14, radius_top=0.0, parent=parent,
               bevel=False)
    k.flag("flag", w, w * 0.62, base + Vector((0.05, 0, h - w * 0.36)), flag, parent=parent, waves=2, amp=0.06)
    k.tube("halyard", base + Vector((0.07, 0, 1.2)), base + Vector((0.07, 0, h - 0.1)), 0.006, "rope",
           parent=parent, segs=4, bevel=False)


def crate(k, parent, loc, size, yaw=0.0, mat="paint_crate"):
    k.box("crate", size, loc, mat, rot=(0, 0, yaw), parent=parent, bevel=0.015)
    sx, sy, sz = size
    for z in (-sz / 2 + 0.05, sz / 2 - 0.05):
        k.box("crate_band", (sx + 0.01, sy + 0.01, 0.025), Vector(loc) + Vector((0, 0, z)), "iron_forged",
              rot=(0, 0, yaw), parent=parent, bevel=False)


def barrel(k, parent, loc, r=0.28, h=0.85, mat="timber_oak", hoop="iron_forged"):
    loc = Vector(loc)
    prof = [(0.0, r * 0.86), (h * 0.5, r), (h, r * 0.86)]
    k.lathe("barrel", [(0, 0)] + prof + [(h, 0)], mat, segs=20, loc=loc, rot=(math.pi / 2, 0, 0), parent=parent)
    for z in (0.08, 0.3, h - 0.3, h - 0.08):
        rr = r * (0.86 + 0.14 * math.sin(math.pi * z / h)) + 0.006
        k.torus("hoop", rr, 0.012, loc + Vector((0, 0, z)), hoop, parent=parent, segs=24, tube_segs=4)


def rnd_for(seed):
    return random.Random(seed)
