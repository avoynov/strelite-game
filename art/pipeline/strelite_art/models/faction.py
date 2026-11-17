"""The attackers' faction look for the parallel world (user, 2026-11-17): ultra-realistic
military machines, but of another world, with light steampunk accents.

The Iron Concord (Железният съюз): slate paint, oxblood bands, brass fittings, and its
emblem, a red disc inside a black cog with a brass spear standing through it. These
helpers place those details on any enemy model; keep them as accents, never the bulk.
"""
import math

from mathutils import Vector

RED = "paint_faction_red"
BRASS = "brass"


def _frame(k, parent, loc, normal, name="emblem"):
    """An empty at loc whose local +Z points along normal (out of the surface)."""
    e = k.empty(name, Vector(loc), parent=parent)
    n = Vector(normal).normalized()
    e.rotation_euler = n.to_track_quat("Z", "Y").to_euler()
    return e


def emblem(k, parent, loc, normal, r=0.35):
    """The faction emblem, flat on a surface: red disc, black cog, brass spear."""
    e = _frame(k, parent, loc, normal)
    k.cylinder("emblem_cog", r, 0.012, (0, 0, 0), "iron_black", segs=40, parent=e, bevel=False)
    n = 12
    for i in range(n):
        a = 2 * math.pi * i / n
        k.box("emblem_tooth", (r * 0.22, r * 0.2, 0.012), (r * 1.05 * math.cos(a), r * 1.05 * math.sin(a), 0.006),
              "iron_black", rot=(0, 0, a), parent=e, bevel=False)
    k.cylinder("emblem_disc", r * 0.72, 0.016, (0, 0, 0.004), RED, segs=36, parent=e, bevel=False)
    k.box("emblem_spear", (r * 0.12, r * 1.9, 0.01), (0, 0, 0.02), BRASS, parent=e, bevel=False)
    k.box("emblem_head", (r * 0.28, r * 0.28, 0.01), (0, r * 0.95, 0.02), BRASS, rot=(0, 0, math.pi / 4), parent=e,
          bevel=False)
    k.box("emblem_guard", (r * 0.7, r * 0.1, 0.01), (0, -r * 0.35, 0.022), BRASS, parent=e, bevel=False)
    return e


def band(k, parent, p0, p1, section, name="faction_band"):
    """A painted oxblood band: a thin beam laid over a member."""
    return k.beam(name, p0, p1, section, RED, parent=parent, bevel=False)


def rivets(k, parent, p0, p1, n, normal, r=0.03):
    """A row of n domed rivets from p0 to p1, standing out along normal."""
    p0, p1 = Vector(p0), Vector(p1)
    rot = Vector(normal).normalized().to_track_quat("Z", "Y").to_euler()
    for i in range(n):
        k.cylinder("rivet", r, r * 0.6, p0.lerp(p1, i / max(n - 1, 1)), "paint_enemy_worn", segs=8, rot=rot,
                   parent=parent, bevel=False)


def lamp(k, parent, loc, normal, r=0.1):
    """A brass-rimmed lamp."""
    e = _frame(k, parent, loc, normal, "lamp")
    k.cylinder("lamp_body", r, r * 1.1, (0, 0, -r), BRASS, segs=18, parent=e, radius_top=r * 1.1)
    k.cylinder("lamp_lens", r * 0.95, 0.015, (0, 0, r * 0.1), "glass", segs=18, parent=e, bevel=False)
    return e


def gauge(k, parent, loc, normal, r=0.07):
    """A brass pressure gauge with a white face."""
    e = _frame(k, parent, loc, normal, "gauge")
    k.cylinder("gauge_case", r, 0.04, (0, 0, 0), BRASS, segs=18, parent=e)
    k.cylinder("gauge_face", r * 0.8, 0.01, (0, 0, 0.04), "paint_white", segs=18, parent=e, bevel=False)
    k.box("gauge_needle", (0.008, r * 0.7, 0.004), (r * 0.15, r * 0.2, 0.052), "iron_black", rot=(0, 0, -0.6),
          parent=e, bevel=False)
    return e


def stack(k, parent, base, h, r=0.08):
    """An exhaust stack with a brass band and a flared cap."""
    base = Vector(base)
    k.tube("stack", base, base + Vector((0, 0, h)), r, "steel_worn", parent=parent, segs=14)
    k.cylinder("stack_band", r + 0.012, 0.06, base + Vector((0, 0, h * 0.4)), BRASS, segs=14, parent=parent,
               bevel=False)
    k.cylinder("stack_cap", r * 1.5, 0.08, base + Vector((0, 0, h)), "iron_black", segs=14, parent=parent,
               radius_top=r * 1.1)


def pennant(k, parent, top, h=1.2, w=0.5):
    """A short mast with an oxblood pennant."""
    top = Vector(top)
    k.tube("mast", top, top + Vector((0, 0, h)), 0.012, BRASS, parent=parent, segs=6, bevel=False)
    k.flag("pennant", w, w * 0.45, top + Vector((0, 0, h - w * 0.5)), RED, parent=parent, waves=2, amp=0.03)
