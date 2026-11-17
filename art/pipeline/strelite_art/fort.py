"""Field fortifications and position kit for the photoreal towers: sandbag walls,
HESCO-type barriers, concrete slab, log revetment, camouflage net, ammunition
crates, pennant, fire-control post. Real sizes in metres.

Layout helper: positions are given in polar form around the tower centre, see
`pol()`. On screen -45 deg is toward the camera (bottom), 45 right, 135 the far
side (top), 225 left. The sun stands at about -104 deg.
"""
import math
import os
import random
import tempfile

import bpy
from mathutils import Vector
from PIL import Image, ImageDraw, ImageFont

from . import materials
from . import materials_photoreal as mp


def pol(r, deg, z=0.0):
    a = math.radians(deg)
    return Vector((r * math.cos(a), r * math.sin(a), z))


def arc_steps(r, deg0, deg1, pitch):
    """Angles (deg) that divide the arc deg0..deg1 at radius r into equal steps of about `pitch` m."""
    span = math.radians(deg1 - deg0) * r
    n = max(1, int(round(span / pitch)))
    step = (deg1 - deg0) / n
    return [deg0 + step * (i + 0.5) for i in range(n)], step


# -- stencilled markings --------------------------------------------------------
_decal_dir = tempfile.mkdtemp(prefix="strelite_decals_")


def decal(k, name, text, parent, centre, u, v, height):
    """White stencilled text on a flat face. u = reading direction, v = up."""
    path = os.path.join(_decal_dir, name + ".png")
    if not os.path.exists(path):
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 120)
        w = int(font.getlength(text)) + 40
        img = Image.new("L", (w, 170), 0)
        d = ImageDraw.Draw(img)
        d.text((20, 10), text, font=font, fill=255)
        for x in range(20 + 36, w, 72):                     # stencil bridges
            d.line([(x, 0), (x, 170)], fill=0, width=7)
        img.convert("RGB").save(path)
    if name not in mp._decals:
        mp.register_decal(name, path)
    with Image.open(path) as im:
        aspect = im.width / im.height
    u, v, c = Vector(u).normalized(), Vector(v).normalized(), Vector(centre)
    hw, hh = height * aspect / 2, height / 2
    verts = [c - u * hw - v * hh, c + u * hw - v * hh, c + u * hw + v * hh, c - u * hw + v * hh]
    me = bpy.data.meshes.new("decal")
    me.from_pydata([tuple(p) for p in verts], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name="UVMap")
    for i, co in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[i].uv = co
    obj = bpy.data.objects.new("decal", me)
    k.collection.objects.link(obj)
    obj.data.materials.append(materials.get(name, k.style))
    obj.parent = parent
    obj.visible_shadow = False
    return obj


def crate(k, root, name, loc, yaw, size=(0.42, 0.98, 0.3), text="155 ОФ  2 БР.",
          mat="paint_crate", batten="wood", decal_name="decal_crate"):
    """Ammunition crate with battens, rope handles and a stencil. Long side = local Y."""
    e = k.empty(name, loc, parent=root)
    e.rotation_euler = (0, 0, yaw)
    sx, sy, sz = size
    k.box("crate", size, (0, 0, sz / 2), mat, parent=e, bevel=0.006)
    for y in (-sy * 0.33, sy * 0.33):
        k.box("batten", (sx + 0.03, 0.07, sz + 0.02), (0, y, sz / 2), batten, parent=e)
    for s in (-1, 1):
        k.hose("handle", [(-0.09, s * (sy / 2 + 0.002), sz * 0.62),
                          (-0.05, s * (sy / 2 + 0.06), sz * 0.45),
                          (0.05, s * (sy / 2 + 0.06), sz * 0.45),
                          (0.09, s * (sy / 2 + 0.002), sz * 0.62)], 0.011, "rope", parent=e)
    if text:
        h = min(0.075, sz * 0.3)
        decal(k, decal_name, text, e, centre=(sx / 2 + 0.0015, 0, sz * 0.5),
              u=(0, 1, 0), v=(0, 0, 1), height=h)
        decal(k, decal_name, text, e, centre=(0, 0, sz + 0.0015),
              u=(0, 1, 0), v=(-1, 0, 0), height=h)
    return e


# -- sandbags ------------------------------------------------------------------------
def sandbag(k, parent, loc, yaw, rnd, size=(0.62, 0.30, 0.17), mat="burlap"):
    """One filled sandbag: a slumped pillow. Long side = local X, resting on z = loc.z."""
    a, b, c = size[0] / 2, size[1] / 2, size[2] / 2
    n_lon, n_lat = 14, 6
    eh, ev = 0.5, 0.78
    sgn = lambda t: (t > 0) - (t < 0)
    ph = [rnd.uniform(0, 6.28) for _ in range(4)]
    verts = []
    for kk in range(n_lat):
        th = -math.pi / 2 + math.pi * (kk + 1) / (n_lat + 1)
        r = abs(math.cos(th)) ** ev
        z = sgn(math.sin(th)) * abs(math.sin(th)) ** ev
        for i in range(n_lon):
            f = 2 * math.pi * i / n_lon
            x = a * r * sgn(math.cos(f)) * abs(math.cos(f)) ** eh
            y = b * r * sgn(math.sin(f)) * abs(math.sin(f)) ** eh
            zz = c * z * (0.82 if z < 0 else 1.0)
            # lumpy fill + ends that droop a little
            lump = 0.012 * math.sin(7 * x + ph[0]) * math.cos(9 * y + ph[1]) \
                + 0.008 * math.sin(15 * x + ph[2] + 11 * y)
            zz += lump * (1.0 if z > 0 else 0.3) - 0.02 * (abs(x) / a) ** 3
            verts.append((x * (1 + 0.04 * math.sin(11 * y + ph[3])), y, zz + c * 0.82))
    c0 = len(verts)
    verts.append((0, 0, 0.0))
    verts.append((0, 0, c * 1.82 + 0.004))
    faces = []
    for kk in range(n_lat - 1):
        for i in range(n_lon):
            j = (i + 1) % n_lon
            faces.append((kk * n_lon + i, kk * n_lon + j, (kk + 1) * n_lon + j, (kk + 1) * n_lon + i))
    last = (n_lat - 1) * n_lon
    for i in range(n_lon):
        j = (i + 1) % n_lon
        faces.append((c0, j, i))
        faces.append((c0 + 1, last + i, last + j))
    obj = k.mesh("sandbag", verts, faces)
    obj.location = loc
    obj.rotation_euler = (rnd.uniform(-0.04, 0.04), rnd.uniform(-0.04, 0.04), yaw)
    s = rnd.uniform(0.94, 1.06)
    obj.scale = (s, rnd.uniform(0.95, 1.05), rnd.uniform(0.92, 1.05))
    return k._finish(obj, mat, bevel=False, parent=parent, outline=False)


def sandbag_wall(k, parent, r_in, arcs, courses=5, seed=3, double_until=3, bag=(0.62, 0.30, 0.17)):
    """Curved sandbag wall. arcs = [(deg0, deg1), ...]. The lower `double_until`
    courses are two bags thick, the rest one bag, laid in running bond.
    Returns (outer radius, height)."""
    rnd = random.Random(seed)
    L, W, H = bag
    rise = H * 0.86                                          # bags flatten under load
    for deg0, deg1 in arcs:
        for cz in range(courses):
            rows = [r_in + W / 2, r_in + W * 1.5] if cz < double_until else [r_in + W]
            for ri, r in enumerate(rows):
                angs, step = arc_steps(r, deg0, deg1, L * 0.97)
                shift = step / 2 if (cz + ri) % 2 else 0.0
                for i, deg in enumerate(angs):
                    d = deg + shift
                    if d + step / 2 > deg1 + 0.01:              # running bond: half bag at the end
                        continue
                    p = pol(r + rnd.uniform(-0.015, 0.015), d, cz * rise)
                    sandbag(k, parent, p, math.radians(d + 90) + rnd.uniform(-0.07, 0.07), rnd, bag)
    return r_in + 2 * W, courses * rise


# -- HESCO-type barrier ---------------------------------------------------------------
def hesco(k, parent, loc, yaw, rnd, size=1.06, height=1.25):
    """One barrier unit: wire-mesh cage with a felt liner, filled with soil."""
    e = k.empty("hesco", loc, parent=parent)
    e.rotation_euler = (0, 0, yaw)
    h = size / 2 - 0.04
    nu, nz = 5, 6
    cols = []
    for side in range(4):
        for i in range(nu):
            u = i / nu
            t = -h + 2 * h * u
            nx, ny = [(1, 0), (0, 1), (-1, 0), (0, -1)][side]
            px, py = [(h, t), (-t, h), (-h, -t), (t, -h)][side]
            cols.append((px, py, nx, ny, u))
    ph = [rnd.uniform(0, 6.28) for _ in range(3)]
    verts, faces = [], []
    for j in range(nz + 1):
        z = height * j / nz
        for (px, py, nx, ny, u) in cols:
            bulge = 0.04 * math.sin(math.pi * u) * math.sin(math.pi * min(z / height, 1.0)) ** 0.7
            bulge += 0.008 * math.sin(5 * z + ph[0] + 3 * px) * math.sin(math.pi * u)
            verts.append((px + nx * bulge, py + ny * bulge, z))
    nc = len(cols)
    for j in range(nz):
        for i in range(nc):
            i2 = (i + 1) % nc
            faces.append((j * nc + i, j * nc + i2, (j + 1) * nc + i2, (j + 1) * nc + i))
    k._finish(k.mesh("hesco_liner", verts, faces), "geotextile", bevel=False, parent=e, outline=False)
    # soil fill, heaped a little
    m = 6
    fv, ff = [], []
    for j in range(m + 1):
        for i in range(m + 1):
            x, y = -h + 2 * h * i / m, -h + 2 * h * j / m
            edge = min(h - abs(x), h - abs(y)) / h
            z = height - 0.07 + 0.09 * math.sin(math.pi / 2 * min(edge * 1.6, 1.0)) \
                + 0.02 * math.sin(6 * x + ph[1]) * math.cos(7 * y + ph[2])
            fv.append((x, y, z))
    for j in range(m):
        for i in range(m):
            a = j * (m + 1) + i
            ff.append((a, a + 1, a + m + 2, a + m + 1))
    k._finish(k.mesh("hesco_fill", fv, ff), "dirt_fill", bevel=False, parent=e, outline=False)
    # top wire of the cage
    for (x0, y0, x1, y1) in ((-h, -h, h, -h), (h, -h, h, h), (h, h, -h, h), (-h, h, -h, -h)):
        k.tube("hesco_wire", (x0, y0, height), (x1, y1, height), 0.006, "steel_worn", parent=e,
               segs=6, bevel=False)
    return e


def hesco_wall(k, parent, r_in, arcs, seed=5, size=1.06, height=1.25):
    """Ring of barrier units whose inner faces stand at r_in. Returns (outer radius, height)."""
    rnd = random.Random(seed)
    r = r_in + size / 2
    for deg0, deg1 in arcs:
        angs, _ = arc_steps(r - size * 0.42, deg0, deg1, size + 0.02)
        for deg in angs:
            hesco(k, parent, pol(r + rnd.uniform(-0.02, 0.02), deg),
                  math.radians(deg) + rnd.uniform(-0.03, 0.03), rnd, size,
                  height * rnd.uniform(0.985, 1.01))
    return r_in + size, height


# -- slabs, logs -------------------------------------------------------------------------
def concrete_pad(k, parent, radius, top=0.06, segs=64):
    return k.cylinder("pad", radius, top + 0.1, (0, 0, -0.1), "concrete", segs=segs, parent=parent,
                      bevel=0.012)


def log_wall(k, parent, radius, arcs, z0, z1, seed=9, dia=0.16):
    """Revetment of round timber standing on end along a circle (logs touch each other)."""
    rnd = random.Random(seed)
    for deg0, deg1 in arcs:
        angs, _ = arc_steps(radius, deg0, deg1, dia * 0.97)
        for deg in angs:
            d = dia * rnd.uniform(0.82, 1.12)
            top = z1 + rnd.uniform(-0.05, 0.06)
            p = pol(radius + rnd.uniform(-0.012, 0.012), deg, z0)
            o = k.cylinder("log", d / 2, top - z0, p, "log", segs=10, parent=parent, bevel=False,
                           radius_top=d / 2 * rnd.uniform(0.9, 1.0), smooth=True)
            o.rotation_euler = (rnd.uniform(-0.03, 0.03), rnd.uniform(-0.03, 0.03), rnd.uniform(0, 6.28))


# -- camouflage net ------------------------------------------------------------------------
def net(k, parent, corners, sag=0.18, nu=28, nv=16, seed=1):
    """Net stretched between four corner points (order: around the outline). The edges
    hang in shallow curves between the corners, the middle sags."""
    rnd = random.Random(seed)
    p00, p10, p11, p01 = (Vector(c) for c in corners)
    ph = [rnd.uniform(0, 6.28) for _ in range(3)]
    verts, faces = [], []
    for j in range(nv + 1):
        v = j / nv
        for i in range(nu + 1):
            u = i / nu
            p = (p00 * (1 - u) + p10 * u) * (1 - v) + (p01 * (1 - u) + p11 * u) * v
            # catenary-like sag: edges a little, the middle more
            s = sag * (0.35 * (math.sin(math.pi * u) * (1 - math.sin(math.pi * v)) ** 2
                               + math.sin(math.pi * v) * (1 - math.sin(math.pi * u)) ** 2)
                       + math.sin(math.pi * u) * math.sin(math.pi * v))
            s += 0.02 * math.sin(9 * u + ph[0]) * math.sin(7 * v + ph[1])
            # edges pull inward between the fixing points
            pull = 0.12 * math.sin(math.pi * u) * (abs(2 * v - 1) ** 3) * (1 if v > 0.5 else -1)
            pull_u = 0.1 * math.sin(math.pi * v) * (abs(2 * u - 1) ** 3) * (1 if u > 0.5 else -1)
            edge_v = (p01 - p00).normalized()
            edge_u = (p10 - p00).normalized()
            p = p - edge_v * pull - edge_u * pull_u
            verts.append((p.x, p.y, max(p.z - s, 0.03)))
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            faces.append((a, a + 1, a + nu + 2, a + nu + 1))
    obj = k.mesh("camo_net", verts, faces)
    k._finish(obj, "camo_net", bevel=False, parent=parent, outline=False)
    return obj


def pole(k, parent, base, height, mat="wood", radius=0.028, lean=(0, 0)):
    top = Vector(base) + Vector((lean[0], lean[1], height))
    k.tube("pole", base, top, radius, mat, parent=parent, segs=10, bevel=False)
    return top


def guy(k, parent, a, b, radius=0.006):
    k.tube("guy", a, b, radius, "rope", parent=parent, segs=6, bevel=False)
    k.tube("peg", Vector(b) + Vector((0, 0, 0.12)), Vector(b) - Vector((0, 0, 0.02)), 0.014,
           "steel_worn", parent=parent, segs=6, bevel=False)


def lean_to_net(k, parent, r_top, r_foot, deg0, deg1, top_z, seed=1):
    """Net strung from poles standing at r_top down to pegs at r_foot: cover for the
    ammunition point. Returns nothing; adds net, poles, pegs and guy lines."""
    tops = []
    mid = (deg0 + deg1) / 2
    for deg in (deg0, mid, deg1):
        tops.append(pole(k, parent, pol(r_top, deg), top_z + (0.12 if deg == mid else 0.0)))
    guy(k, parent, tops[0], pol(r_top + 0.3, deg0 - 9))
    guy(k, parent, tops[2], pol(r_top + 0.3, deg1 + 9))
    foot0, foot1 = pol(r_foot, deg0 - 2, 0.1), pol(r_foot, deg1 + 2, 0.1)
    net(k, parent, [tops[0] + Vector((0, 0, -0.02)), tops[2] + Vector((0, 0, -0.02)), foot1, foot0],
        sag=0.16, seed=seed)
    for f in (foot0, foot1, pol(r_foot, (deg0 + deg1) / 2, 0.1)):
        k.tube("peg", f + Vector((0, 0, 0.06)), f - Vector((0, 0, 0.1)), 0.014, "steel_worn",
               parent=parent, segs=6, bevel=False)


# -- small kit ------------------------------------------------------------------------------
def pennant(k, parent, base, height=2.4, yaw=0.6):
    """Crimson unit pennant on a pole."""
    top = pole(k, parent, base, height, mat="paint_white", radius=0.018)
    f = k.flag("pennant", 0.75, 0.42, (top.x, top.y, top.z - 0.26), "flag", parent=parent, amp=0.07)
    f.rotation_euler = (0, 0, yaw)
    k.cylinder("finial", 0.03, 0.05, (top.x, top.y, top.z), "brass", segs=10, parent=parent)


def fire_control(k, parent, base, yaw):
    """Fire-control post: rugged computer on a tripod, whip aerial, cable reel."""
    e = k.empty("fire_control", base, parent=parent)
    e.rotation_euler = (0, 0, yaw)
    head = Vector((0, 0, 0.95))
    for i in range(3):
        a = 2 * math.pi * i / 3 + 0.5
        k.tube("tripod", (0.42 * math.cos(a), 0.42 * math.sin(a), 0.0), head, 0.016, "gunmetal",
               parent=e, segs=8, bevel=False)
    k.box("fc_shelf", (0.5, 0.4, 0.03), (0, 0, 0.96), "paint_olive_worn", parent=e)
    k.box("fc_case", (0.44, 0.32, 0.07), (0, 0, 1.01), "paint_olive", parent=e, bevel=0.012)
    lid = k.box("fc_lid", (0.44, 0.03, 0.3), (0, 0.17, 1.2), "paint_olive", parent=e, bevel=0.01)
    lid.rotation_euler = (math.radians(-12), 0, 0)
    scr = k.box("fc_screen", (0.36, 0.004, 0.22), (0, 0.15, 1.2), "screen", parent=e, bevel=False)
    scr.rotation_euler = (math.radians(-12), 0, 0)
    # radio with whip aerial
    k.box("radio", (0.3, 0.12, 0.36), (0.55, 0.1, 0.18), "paint_olive_worn", parent=e, bevel=0.015)
    k.tube("aerial", (0.66, 0.1, 0.36), (0.72, 0.1, 2.9), 0.006, "gunmetal", parent=e, segs=6,
           bevel=False)
    k.cylinder("aerial_base", 0.02, 0.1, (0.66, 0.1, 0.36), "rubber", segs=10, parent=e)
    # cable reel lying on the ground
    k.cylinder("reel", 0.16, 0.2, (-0.5, -0.1, 0.0), "hose", segs=20, parent=e)
    for z in (0.0, 0.2):
        k.cylinder("reel_flange", 0.22, 0.012, (-0.5, -0.1, z), "steel_worn", segs=24, parent=e)
    k.hose("fc_cable", [(-0.5, 0.06, 0.1), (-0.3, 0.3, 0.03), (-0.05, 0.2, 0.03), (0.1, 0.1, 0.5),
                        (0.1, 0.05, 0.98)], 0.008, "hose", parent=e)
    return e
