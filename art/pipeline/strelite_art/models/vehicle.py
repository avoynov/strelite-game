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
