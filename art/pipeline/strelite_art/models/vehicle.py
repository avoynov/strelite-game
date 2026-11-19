"""Shared running gear for the enemy vehicles: wheels and tracks. Axles run along X,
vehicles face +Y."""
import math

from mathutils import Vector

AXLE_X = (0, 0, -math.pi / 2)        # lathe axis (local Y) turned onto world X


def road_wheel(k, parent, loc, r, width, mat, sprocket=False, tyre="rubber"):
    """Wheel with a rubber rim and a painted disc; a sprocket gets teeth instead of rubber."""
    w = k.empty("wheel", loc, parent=parent)
    h = width / 2
    if sprocket:
        k.lathe("sprocket", [(-h, 0.0), (-h, r * 0.8), (h, r * 0.8), (h, 0.0)], mat, segs=28,
                rot=AXLE_X, parent=w)
        n = 13
        for i in range(n):
            a = 2 * math.pi * i / n
            k.box("tooth", (width * 0.7, 0.07, r * 0.32), (0, r * 0.9 * math.cos(a), r * 0.9 * math.sin(a)),
                  "track_steel", rot=(a - math.pi / 2, 0, 0), parent=w, bevel=False)
    else:
        k.lathe(tyre, [(-h, 0.0), (-h, r * 0.9), (-h + 0.03, r), (h - 0.03, r), (h, r * 0.9), (h, 0.0)],
                tyre, segs=32, rot=AXLE_X, parent=w)
    for s in (-1, 1):
        k.lathe("disc", [(0.0, 0.0), (0.0, r * 0.84), (s * 0.03, r * 0.8), (s * 0.05, r * 0.3),
                         (s * 0.09, r * 0.22), (s * 0.09, 0.0)], mat, segs=28,
                loc=(s * h, 0, 0), rot=AXLE_X, parent=w)
    return w


def track(k, parent, x, y0, y1, z, r, width, mat, pitch=0.15, thick=0.06):
    """Track run around a stadium in the Y-Z plane: centres (y0, z) and (y1, z), inner radius r."""
    straight = y1 - y0
    arc = math.pi * (r + thick / 2)
    total = 2 * straight + 2 * arc
    n = int(total / pitch)
    step = total / n
    rc = r + thick / 2
    for i in range(n):
        s = i * step
        if s < straight:                                    # bottom run, front to back
            p, phi = Vector((x, y1 - s, z - rc)), math.pi
        elif s < straight + arc:                            # around the rear wheel
            a = (s - straight) / rc                         # 0 .. pi
            ang = -math.pi / 2 - a
            p, phi = Vector((x, y0 + rc * math.cos(ang), z + rc * math.sin(ang))), ang - math.pi / 2
        elif s < 2 * straight + arc:                        # top run, back to front
            p, phi = Vector((x, y0 + (s - straight - arc), z + rc)), 0.0
        else:                                               # around the front wheel
            a = (s - 2 * straight - arc) / rc
            ang = math.pi / 2 - a
            p, phi = Vector((x, y1 + rc * math.cos(ang), z + rc * math.sin(ang))), ang - math.pi / 2
        k.box("link", (width, step * 0.92, thick), p, mat, rot=(phi, 0, 0), parent=parent, bevel=False)
        if i % 2 == 0:                                      # guide horn in the middle of every other link
            n_in = Vector((0, -math.cos(phi + math.pi / 2), -math.sin(phi + math.pi / 2)))
            k.box("horn", (0.04, 0.08, 0.07), p - n_in * 0.0 + (Vector((0, 0, 0))), mat, rot=(phi, 0, 0),
                  parent=parent, bevel=False)


def tyre_wheel(k, parent, loc, r, width, hub_mat, tread=True):
    """Truck wheel: tyre with tread blocks and a steel disc."""
    w = k.empty("wheel", loc, parent=parent)
    h = width / 2
    k.lathe("tyre", [(-h, 0.0), (-h, r * 0.62), (-h - 0.01, r * 0.85), (-h + 0.03, r), (h - 0.03, r),
                     (h + 0.01, r * 0.85), (h, r * 0.62), (h, 0.0)], "rubber", segs=36, rot=AXLE_X, parent=w)
    for s in (-1, 1):
        k.lathe("rim", [(0.0, 0.0), (0.0, r * 0.62), (s * 0.02, r * 0.6), (s * 0.04, r * 0.25),
                        (s * 0.09, r * 0.18), (s * 0.09, 0.0)], hub_mat, segs=28,
                loc=(s * (h - 0.03), 0, 0), rot=AXLE_X, parent=w)
    if tread:
        n = 30
        for i in range(n):
            a = 2 * math.pi * i / n
            k.box("tread", (width * 0.9, 0.05, 0.03), (0, r * math.cos(a), r * math.sin(a)), "rubber",
                  rot=(a - math.pi / 2, 0.0, 0.25 if i % 2 else -0.25), parent=w, bevel=False)
    return w


# ---------------------------------------------------------------------------
# movement animation (SOP "Movement animation"): wheels roll, tracks run, propellers
# turn. A model keeps one Motion, registers its moving parts while building, and
# calls motion.set(f) from set_move_frame(f). The cycle is chosen so frame F wraps
# exactly onto frame 0: every wheel turns by a whole number of its pattern's
# repeats per cycle, every track moves a whole number of links.
class Motion:
    def __init__(self, frames, cycle_m=None, turns=None):
        self.frames, self.cycle_m, self.turns = frames, cycle_m, turns
        self.wheels, self.links, self.props = [], [], []

    def wheel(self, node, r):
        self.wheels.append((node, r, node.rotation_euler.x))

    def prop(self, node, axis=1, symmetry=3):
        """Propeller: per cycle it turns by one blade spacing (2*pi/symmetry)."""
        self.props.append((node, axis, symmetry, tuple(node.rotation_euler)))

    def set(self, f):
        s = self.cycle_m * f / self.frames if self.cycle_m else 0.0
        for node, r, x0 in self.wheels:
            node.rotation_euler.x = x0 - s / r
        for path, objs in self.links:
            for o, s0 in objs:
                p, phi = path(s0 + s)
                o.location = p
                o.rotation_euler = (phi, 0, 0)
        for node, axis, sym, r0 in self.props:
            r = list(r0)
            r[axis] = r0[axis] + 2 * math.pi / sym * f / self.frames
            node.rotation_euler = r


def stadium(x, y0, y1, z, rc, z_low=None):
    """Closed path of a track belt in the Y-Z plane (front y1, rear y0, centres at z,
    belt radius rc), as s -> (point, pitch angle). Bottom run moves backward."""
    straight = y1 - y0
    arc = math.pi * rc
    total = 2 * straight + 2 * arc

    def at(s):
        s %= total
        if s < straight:
            return Vector((x, y1 - s, z - rc)), math.pi
        if s < straight + arc:
            a = (s - straight) / rc
            ang = -math.pi / 2 - a
            return Vector((x, y0 + rc * math.cos(ang), z + rc * math.sin(ang))), ang - math.pi / 2
        if s < 2 * straight + arc:
            return Vector((x, y0 + (s - straight - arc), z + rc)), 0.0
        a = (s - 2 * straight - arc) / rc
        ang = math.pi / 2 - a
        return Vector((x, y1 + rc * math.cos(ang), z + rc * math.sin(ang))), ang - math.pi / 2
    return at, total


def track_links(k, parent, motion, x, y0, y1, z, r, width, mat, pitch, thick=0.06):
    """Track of separate links on a stadium path; `pitch` must divide the path length
    to a whole number of links (the caller picks the pitch, see Motion)."""
    rc = r + thick / 2
    path, total = stadium(x, y0, y1, z, rc)
    n = max(1, round(total / pitch))
    step = total / n
    objs = []
    for i in range(n):
        p, phi = path(i * step)
        e = k.empty("link", p, parent=parent)
        e.rotation_euler = (phi, 0, 0)
        k.box("shoe", (width, step * 0.88, thick), (0, 0, 0), mat, parent=e, bevel=0.006)
        k.box("grouser", (width * 0.96, 0.035, 0.03), (0, 0, -thick / 2 - 0.012), mat, parent=e, bevel=False)
        k.cylinder("pin", 0.016, width + 0.04, (-width / 2 - 0.02, step / 2, 0), "steel_worn", segs=8,
                   rot=(0, math.pi / 2, 0), parent=e, bevel=False)
        k.box("guide_horn", (0.05, step * 0.5, 0.08), (0, 0, thick / 2 + 0.04), mat, parent=e, bevel=0.005)
        objs.append((e, i * step))
    motion.links.append((path, objs))
    return step


def lug_wheel(k, parent, motion, loc, r, width, hub_mat, holes=8, lugs=24, tyre="tyre"):
    """Military tyre with chevron lugs on a pressed steel disc with `holes` holes and
    lug nuts: the pattern repeats every 2*pi/holes (lugs a multiple of holes)."""
    w = k.empty("wheel", loc, parent=parent)
    h = width / 2
    k.lathe("tyre", [(-h, r * 0.6), (-h - 0.012, r * 0.84), (-h + 0.04, r * 0.97), (h - 0.04, r * 0.97),
                     (h + 0.012, r * 0.84), (h, r * 0.6)], tyre, segs=48, rot=AXLE_X, parent=w)
    for i in range(lugs):
        a = 2 * math.pi * i / lugs
        for sx in (-1, 1):
            k.box("lug", (h * 0.85, 0.05, 0.022), (sx * h * 0.48, r * 0.968 * math.cos(a), r * 0.968 * math.sin(a)),
                  tyre, rot=(a - math.pi / 2, 0, sx * 0.45), parent=w, bevel=0.008)
    for sx in (-1, 1):
        k.lathe("rim", [(0.0, 0.0), (0.0, r * 0.62), (sx * 0.03, r * 0.6), (sx * 0.05, r * 0.32),
                        (sx * 0.1, r * 0.24), (sx * 0.1, 0.0)], hub_mat, segs=40,
                loc=(sx * (h - 0.04), 0, 0), rot=AXLE_X, parent=w)
        for i in range(holes):
            a = 2 * math.pi * (i + 0.5) / holes
            k.cylinder("rim_hole", r * 0.075, 0.02, (sx * (h - 0.03), r * 0.47 * math.cos(a), r * 0.47 * math.sin(a)),
                       "iron_black", segs=10, rot=(0, math.pi / 2, 0), parent=w, bevel=False)
            b = a - math.pi / holes
            k.cylinder("lug_nut", 0.018, 0.03, (sx * (h + 0.06), r * 0.21 * math.cos(b), r * 0.21 * math.sin(b)),
                       "steel_worn", segs=6, rot=(0, math.pi / 2, 0), parent=w, bevel=False)
        k.cylinder("hub_cap", r * 0.13, 0.05, (sx * (h + 0.08), 0, 0), "gunmetal", segs=16, rot=(0, math.pi / 2, 0),
                   parent=w, bevel=0.006)
        k.cylinder("hub_nut", r * 0.055, 0.02, (sx * (h + 0.115), 0, 0), "brass", segs=12, rot=(0, math.pi / 2, 0),
                   parent=w, bevel=False)
    motion.wheel(w, r)
    return w


def sheet(k, name, path_yz, x, width, mat, parent, lip=0.06, thick=0.012, segs=10, outward=1):
    """Pressed sheet-metal wing (mudguard): a strip of `width` across X centred at x,
    following a (y, z) path; the outer edge (side `outward`) turns down by `lip`."""
    import bpy
    pts = [Vector((0.0, y, z)) for y, z in path_yz]
    verts, faces = [], []
    n = len(pts)
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        up = Vector((1, 0, 0)).cross(t).normalized()          # surface normal (outward of the curve)
        if up.z < 0 and abs(t.z) < 0.9:
            up = -up
        for j in range(segs + 1):
            u = j / segs                                       # 0 inner edge .. 1 outer edge
            xx = x + outward * (u - 0.5) * width
            drop = lip * max(0.0, (u - 0.8) / 0.2) ** 2
            verts.append(p + Vector((xx, 0, 0)) - up * drop)
    for i in range(n - 1):
        for j in range(segs):
            a = i * (segs + 1) + j
            faces.append((a, a + 1, a + segs + 2, a + segs + 1))
    obj = k.mesh(name, [tuple(v) for v in verts], faces)
    k._finish(obj, mat, bevel=False, parent=parent)
    m = obj.modifiers.new("Solidify", "SOLIDIFY")
    m.thickness = thick
    m.offset = -1.0
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def arc_yz(cy, cz, r, a0, a1, n):
    """Points of an arc in the Y-Z plane, angles in degrees from +Y toward +Z."""
    return [(cy + r * math.cos(math.radians(a0 + (a1 - a0) * i / (n - 1))),
             cz + r * math.sin(math.radians(a0 + (a1 - a0) * i / (n - 1)))) for i in range(n)]


def hull(k, name, sections, mat, parent, bevel=0.012):
    """Faceted armour hull lofted through cross-sections. `sections`: list of
    (y, half_profile) from rear to front; half_profile is [(x, z), ...] from the bottom
    centre (x = 0) round the right side to the roof centre (x = 0), the same number of
    points in every section. Flat plates, closed ends."""
    rings = []
    for y, half in sections:
        right = [(x, z) for x, z in half]
        left = [(-x, z) for x, z in reversed(half[1:-1])]
        rings.append([(x, y, z) for x, z in right + left])
    n = len(rings[0])
    verts = [v for r in rings for v in r]
    faces = []
    for i in range(len(rings) - 1):
        for j in range(n):
            jj = (j + 1) % n
            faces.append((i * n + j, i * n + jj, (i + 1) * n + jj, (i + 1) * n + j))
    faces.append(tuple(reversed(range(n))))
    last = (len(rings) - 1) * n
    faces.append(tuple(range(last, last + n)))
    obj = k.mesh(name, verts, faces)
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    return k._finish(obj, mat, bevel=bevel, parent=parent)


# ---------------------------------------------------------------------------
# tracks of real tanks: a belt round sprocket, road wheels and idler
def belt(circles):
    """Closed belt (link centreline) round circles [(y, z, r), ...] listed clockwise as
    seen from +X with +Y to the right: front idler, the road wheels' bottoms front to
    rear, the sprocket, then any wheels the top run rests on, rear to front. Circles the
    belt does not touch (inside the hull of the others) are dropped. Returns
    (path, total): path(s) -> (Vector point, pitch angle); s grows along the travel, so
    the bottom run moves backward (-Y) as s grows."""
    cs = [(Vector((y, z)), r) for y, z, r in circles]
    while True:
        m = len(cs)
        seg = []
        for i in range(m):
            (p1, r1), (p2, r2) = cs[i], cs[(i + 1) % m]
            d = p2 - p1
            ln = d.length
            dh = d / ln
            nl = Vector((-dh.y, dh.x))
            a = (r1 - r2) / ln
            n = dh * a + nl * math.sqrt(max(0.0, 1 - a * a))
            seg.append((p1 + n * r1, p2 + n * r2, n))
        arcs, drop = [], None
        for i in range(m):
            a_in = math.atan2(seg[i - 1][2].y, seg[i - 1][2].x)
            a_out = math.atan2(seg[i][2].y, seg[i][2].x)
            sweep = (a_in - a_out) % (2 * math.pi)
            if sweep > 1.5 * math.pi:
                drop = i
                break
            arcs.append((a_in, sweep))
        if drop is None:
            break
        cs.pop(drop)
    parts, total = [], 0.0
    for i in range(len(cs)):
        (c, r), (a_in, sweep) = cs[i], arcs[i]
        parts.append(("arc", total, r * sweep, c, r, a_in))
        total += r * sweep
        t1, t2, _ = seg[i]
        parts.append(("line", total, (t2 - t1).length, t1, t2, None))
        total += (t2 - t1).length

    def at(s):
        s %= total
        for kind, s0, ln, a, b, c in parts:
            if s < s0 + ln or (kind, s0, ln) == parts[-1][:3]:
                u = s - s0
                if kind == "arc":
                    ang = c - u / b
                    q = a + Vector((math.cos(ang), math.sin(ang))) * b
                    return Vector((0.0, q.x, q.y)), ang - math.pi / 2
                d = (b - a)
                q = a + d * (u / ln if ln else 0.0)
                return Vector((0.0, q.x, q.y)), math.atan2(d.y, d.x)
    return at, total


def belt_links(k, parent, motion, x, path, total, n, width, mat, thick=0.06, horn=True):
    """n track links spaced evenly on a belt path at x; each link is a shoe with an
    outside grouser, an inside guide horn and the pin. Moves with motion.set."""
    step = total / n

    def placed(s):
        q, phi = path(s)
        return Vector((x, q.y, q.z)), phi
    objs = []
    for i in range(n):
        p, phi = placed(i * step)
        e = k.empty("link", p, parent=parent)
        e.rotation_euler = (phi, 0, 0)
        k.box("shoe", (width, step * 0.86, thick), (0, 0, 0), mat, parent=e, bevel=0.008)
        k.box("grouser", (width * 0.94, 0.04, 0.028), (0, -step * 0.15, thick / 2 + 0.012), mat, parent=e,
              bevel=0.006)
        if horn:
            k.box("guide_horn", (0.06, step * 0.5, 0.1), (0, 0, -thick / 2 - 0.045), mat, parent=e, bevel=0.01)
        k.cylinder("pin", 0.02, width + 0.05, (-width / 2 - 0.025, step / 2, 0), "steel_worn", segs=8,
                   rot=(0, math.pi / 2, 0), parent=e, bevel=False)
        objs.append((e, i * step))
    motion.links.append((placed, objs))
    return step


def ring_lathe(k, name, profile, mat, segs=28, loc=(0, 0, 0), rot=(0, 0, 0), parent=None):
    """A lathe whose profile is a closed loop (a tyre, a rim, a hoop): no end caps, the
    last ring joined back to the first, so the middle stays open."""
    import bmesh
    obj = k.lathe(name, profile, mat, segs=segs, loc=loc, rot=rot, parent=parent)
    n = len(profile) * segs
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[n], bm.verts[n + 1]], context="VERTS")
    bm.verts.ensure_lookup_table()
    last = n - segs
    for i in range(segs):
        j = (i + 1) % segs
        bm.faces.new((bm.verts[last + i], bm.verts[last + j], bm.verts[j], bm.verts[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def spoke_wheel(k, parent, motion, loc, r, width, rim_mat, spokes=36, knobs=24, tyre="tyre"):
    """Motorcycle wheel: knobbly tyre on a painted rim, crossed wire spokes laced to a
    drum-brake hub. Pattern repeats every 2*pi/(spokes/2) and 2*pi/(knobs/2)."""
    w = k.empty("wheel", loc, parent=parent)
    h = width / 2
    ring_lathe(k, "tyre", [(-h * 0.8, r * 0.76), (-h - 0.006, r * 0.86), (-h * 0.7, r * 0.97), (h * 0.7, r * 0.97),
                           (h + 0.006, r * 0.86), (h * 0.8, r * 0.76)], tyre, segs=48, rot=AXLE_X, parent=w)
    for i in range(knobs):
        a = 2 * math.pi * i / knobs
        off = (h * 0.32) * (1 if i % 2 else -1)
        k.box("knob", (h * 0.9, 0.04, 0.02), (off, r * 0.965 * math.cos(a), r * 0.965 * math.sin(a)), tyre,
              rot=(a - math.pi / 2, 0, 0), parent=w, bevel=0.006)
    ring_lathe(k, "rim", [(-0.022, r * 0.72), (-0.024, r * 0.78), (0.024, r * 0.78), (0.022, r * 0.72)], rim_mat,
               segs=48, rot=AXLE_X, parent=w)
    k.cylinder("hub", 0.075, 0.13, (-0.065, 0, 0), "gunmetal", segs=20, rot=(0, math.pi / 2, 0), parent=w,
               bevel=0.01)
    for sd in (-1, 1):
        k.cylinder("hub_flange", 0.085, 0.012, (sd * 0.05 - 0.006, 0, 0), "steel_worn", segs=20,
                   rot=(0, math.pi / 2, 0), parent=w, bevel=False)
    for i in range(spokes):
        a = 2 * math.pi * i / spokes
        sd = 1 if i % 2 else -1
        a0 = a + sd * 0.45
        k.tube("spoke", (sd * 0.05, 0.08 * math.cos(a0), 0.08 * math.sin(a0)),
               (sd * 0.01, r * 0.72 * math.cos(a), r * 0.72 * math.sin(a)), 0.0035, "steel_worn", parent=w, segs=4,
               bevel=False)
    motion.wheel(w, r)
    return w


# ---------------------------------------------------------------------------
# tracked running gear sized so everything wraps (tank, fortress)
class TrackPlan:
    """Belt round an idler (front), road wheels and a sprocket (rear). The link step is
    chosen so the belt closes on a whole number of links, and every wheel is sized from
    that step so it turns by exactly one repeat of its bolt or tooth pattern while the
    belt moves one link: a cycle of one link wraps for links and wheels alike."""

    def __init__(self, road_y, idler_yz, sprocket_yz, n_road=16, n_idler=14, n_sprocket=13, pitch=0.16,
                 thick=0.06, grouser=0.026):
        self.road_y, self.idler_yz, self.sprocket_yz = road_y, idler_yz, sprocket_yz
        self.n_road, self.n_idler, self.n_sprocket = n_road, n_idler, n_sprocket
        self.pitch, self.thick, self.grouser = pitch, thick, grouser
        n = max(1, round(belt_length(self.circles(pitch)) / pitch))
        # solve belt_length(step) = n * step (the wheels grow with the step): secant
        s0, s1 = pitch * 0.98, pitch * 1.02
        g0 = belt_length(self.circles(s0)) - n * s0
        for _ in range(40):
            g1 = belt_length(self.circles(s1)) - n * s1
            if abs(g1) < 1e-10 or g1 == g0:
                break
            s0, s1, g0 = s1, s1 - g1 * (s1 - s0) / (g1 - g0), g1
        step = s1
        self.step, self.n = step, n
        self.r_road, self.r_idler, self.r_sprocket = self.radii(step)
        self.z_road = grouser + thick + self.r_road

    def radii(self, step):
        f = step / (2 * math.pi)
        return self.n_road * f, self.n_idler * f, self.n_sprocket * f

    def circles(self, step=None):
        step = step or self.step
        rr, ri, rs = self.radii(step)
        t = self.thick
        zr = self.grouser + t + rr            # road wheels stand on the inner face of the bottom run
        road = [(y, zr, rr + t / 2) for y in self.road_y]
        return ([(self.idler_yz[0], self.idler_yz[1], ri + t / 2)] + road +
                [(self.sprocket_yz[0], self.sprocket_yz[1], rs)] + list(reversed(road)))

    def build(self, k, root, motion, x, width, paint, worn, link_mat, horn=True, arms=True):
        """Wheels, belt of links and suspension arms for one track centred at x."""
        sx = 1 if x > 0 else -1
        f = width / 0.58
        path, total = belt(self.circles())
        assert abs(total / self.n - self.step) < 1e-6, (total, self.n, self.step)
        for y in self.road_y:
            road_wheel_pair(k, root, motion, (x, y, self.z_road), self.r_road, sx, f, self.n_road, paint)
        idler(k, root, motion, (x, self.idler_yz[0], self.idler_yz[1]), self.r_idler, sx, f, self.n_idler, paint,
              worn)
        sprocket(k, root, motion, (x, self.sprocket_yz[0], self.sprocket_yz[1]), self.r_sprocket, sx, f,
                 self.n_sprocket, paint, worn, link_mat)
        belt_links(k, root, motion, x, path, total, self.n, width, link_mat, thick=self.thick, horn=horn)
        if arms:
            xi = x - sx * width / 2
            for y in self.road_y:
                k.beam("road_arm", (xi - sx * 0.09 * f, y + 0.32 * f, self.z_road + 0.12 * f),
                       (xi + sx * 0.03 * f, y, self.z_road), (0.08 * f, 0.1 * f), worn, parent=root, bevel=0.01)


def belt_length(circles):
    """Length of belt(circles) in pure Python (usable at import time)."""
    cs = [((y, z), r) for y, z, r in circles]
    while True:
        m = len(cs)
        seg = []
        for i in range(m):
            (p1, r1), (p2, r2) = cs[i], cs[(i + 1) % m]
            dy, dz = p2[0] - p1[0], p2[1] - p1[1]
            ln = math.hypot(dy, dz)
            hy, hz = dy / ln, dz / ln
            a = (r1 - r2) / ln
            b = math.sqrt(max(0.0, 1 - a * a))
            ny, nz = hy * a - hz * b, hz * a + hy * b
            t1 = (p1[0] + ny * r1, p1[1] + nz * r1)
            t2 = (p2[0] + ny * r2, p2[1] + nz * r2)
            seg.append((t1, t2, (ny, nz)))
        total, drop = 0.0, None
        for i in range(m):
            a_in = math.atan2(seg[i - 1][2][1], seg[i - 1][2][0])
            a_out = math.atan2(seg[i][2][1], seg[i][2][0])
            sweep = (a_in - a_out) % (2 * math.pi)
            if sweep > 1.5 * math.pi:
                drop = i
                break
            total += cs[i][1] * sweep + math.hypot(seg[i][1][0] - seg[i][0][0], seg[i][1][1] - seg[i][0][1])
        if drop is None:
            return total
        cs.pop(drop)



def road_wheel_pair(k, root, motion, loc, r, sx, f, n_bolts, paint):
    """Double road wheel with rubber tyres on dished discs; f scales the widths (1 = a
    0.58 m track), sx is the side (+1 right) whose face shows the bolts and hub."""
    w = k.empty("road_wheel", loc, parent=root)
    hw, cx0 = 0.085 * f, 0.16 * f
    for s in (-1, 1):
        cx = s * cx0
        k.lathe("tyre", [(-hw, r * 0.78), (-hw, r * 0.95), (-hw + 0.015, r), (hw - 0.015, r), (hw, r * 0.95),
                         (hw, r * 0.78)], "rubber", segs=40, loc=(cx, 0, 0), rot=AXLE_X, parent=w)
        face = cx + s * hw
        k.lathe("wheel_disc", [(0.0, 0.0), (0.0, r * 0.8), (s * 0.02, r * 0.76), (s * 0.04, r * 0.4),
                               (s * 0.07, r * 0.3), (s * 0.07, 0.0)], paint, segs=40,
                loc=(face - s * 0.02, 0, 0), rot=AXLE_X, parent=w)
    face = cx0 + hw
    for i in range(n_bolts):
        a = 2 * math.pi * i / n_bolts
        k.cylinder("wheel_bolt", 0.016 * f ** 0.5, 0.03, (sx * (face + 0.009), r * 0.6 * math.cos(a),
                                                           r * 0.6 * math.sin(a)),
                   "steel_worn", segs=6, rot=(0, sx * math.pi / 2, 0), parent=w, bevel=False)
    k.cylinder("hub_cap", r * 0.24, 0.07, (sx * (face + 0.05), 0, 0), "gunmetal", segs=20,
               rot=(0, sx * math.pi / 2, 0), parent=w, radius_top=r * 0.2, bevel=0.008)
    k.cylinder("hub_nut", r * 0.07, 0.03, (sx * (face + 0.12), 0, 0), "brass", segs=12,
               rot=(0, sx * math.pi / 2, 0), parent=w, bevel=False)
    motion.wheel(w, r)
    return w


def idler(k, root, motion, loc, r, sx, f, n_bolts, paint, worn):
    """Front idler: two steel rims on dished discs, with the track adjuster crank."""
    w = k.empty("idler", loc, parent=root)
    hw, cx0 = 0.07 * f, 0.16 * f
    for s in (-1, 1):
        k.lathe("idler_rim", [(-hw, r * 0.8), (-hw, r), (hw, r), (hw, r * 0.8)], "steel_worn", segs=40,
                loc=(s * cx0, 0, 0), rot=AXLE_X, parent=w)
        k.lathe("idler_disc", [(0.0, 0.0), (0.0, r * 0.82), (s * 0.03, r * 0.7), (s * 0.06, r * 0.3),
                               (s * 0.06, 0.0)], paint, segs=40, loc=(s * (cx0 + 0.04 * f), 0, 0), rot=AXLE_X,
                parent=w)
    face = cx0 + 0.04 * f + 0.044
    for i in range(n_bolts):
        a = 2 * math.pi * i / n_bolts
        k.cylinder("idler_bolt", 0.015 * f ** 0.5, 0.03, (sx * face, r * 0.52 * math.cos(a), r * 0.52 * math.sin(a)),
                   "steel_worn", segs=6, rot=(0, sx * math.pi / 2, 0), parent=w, bevel=False)
    k.cylinder("idler_hub", r * 0.26, 0.08, (sx * (face + 0.016), 0, 0), "gunmetal", segs=18,
               rot=(0, sx * math.pi / 2, 0), parent=w, radius_top=r * 0.2, bevel=0.008)
    x = loc[0]
    k.beam("idler_crank", (x - sx * 0.36 * f, loc[1] - 0.35 * f, loc[2] + 0.1 * f), (x - sx * 0.23 * f, loc[1], loc[2]),
           (0.1 * f, 0.12 * f), worn, parent=root, bevel=0.01)
    motion.wheel(w, r)
    return w


def sprocket(k, root, motion, loc, r, sx, f, n_teeth, paint, worn, tooth_mat):
    """Rear drive sprocket: two toothed rings (pitch radius r), dished cover, final drive."""
    w = k.empty("sprocket", loc, parent=root)
    cx0 = 0.13 * f
    for s in (-1, 1):
        k.lathe("sprocket_ring", [(-0.035 * f, r * 0.6), (-0.035 * f, r * 0.86), (0.035 * f, r * 0.86),
                                  (0.035 * f, r * 0.6)], worn, segs=40, loc=(s * cx0, 0, 0), rot=AXLE_X, parent=w)
        for i in range(n_teeth):
            a = 2 * math.pi * (i + 0.5) / n_teeth
            k.box("sprocket_tooth", (0.07 * f, 0.075 * r / 0.33, r * 0.3),
                  (s * cx0, r * 0.94 * math.cos(a), r * 0.94 * math.sin(a)),
                  tooth_mat, rot=(a - math.pi / 2, 0, 0), parent=w, bevel=0.01)
    k.lathe("sprocket_disc", [(0.0, 0.0), (0.0, r * 0.66), (sx * 0.05, r * 0.6), (sx * 0.1, r * 0.3),
                              (sx * 0.12, 0.0)], paint, segs=40, loc=(sx * (cx0 + 0.04 * f), 0, 0), rot=AXLE_X,
            parent=w)
    face = cx0 + 0.04 * f + 0.083
    for i in range(n_teeth):
        a = 2 * math.pi * i / n_teeth
        k.cylinder("sprocket_bolt", 0.016 * f ** 0.5, 0.03, (sx * face, r * 0.4 * math.cos(a), r * 0.4 * math.sin(a)),
                   "steel_worn", segs=6, rot=(0, sx * math.pi / 2, 0), parent=w, bevel=False)
    k.cylinder("sprocket_hub", r * 0.24, 0.06, (sx * (face + 0.037), 0, 0), "brass", segs=18,
               rot=(0, sx * math.pi / 2, 0), parent=w, radius_top=r * 0.18, bevel=0.008)
    x = loc[0]
    x0 = min(x - sx * 0.48 * f, x - sx * 0.18 * f)
    k.cylinder("final_drive", 0.3 * f ** 0.7, 0.3 * f, (x0, loc[1], loc[2]), worn, segs=24,
               rot=(0, math.pi / 2, 0), parent=root, bevel=0.02)
    motion.wheel(w, r)
    return w
