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
        k.cylinder("hub_cap", r * 0.13, 0.05, (sx * (h + 0.08), 0, 0), "brass", segs=16, rot=(0, math.pi / 2, 0),
                   parent=w, bevel=0.006)
    motion.wheel(w, r)
    return w
