"""The defenders' marks for the parallel world (2026-11-17): a white tower on a blue heater
shield with a gold rim. The field guns carry it on their shields; keep it small, an accent.
"""
from mathutils import Vector

BLUE, WHITE, GOLD = "paint_blue", "paint_white", "gold_trim"


def _frame(k, parent, loc, normal, name="defender_emblem"):
    """An empty at loc whose local +Y points along normal (out of the surface)."""
    e = k.empty(name, Vector(loc), parent=parent)
    e.rotation_euler = Vector(normal).normalized().to_track_quat("Y", "Z").to_euler()
    return e


def _shield(w, h):
    """Heater shield outline in (x, z), centred on the origin: flat top, pointed foot."""
    pts = [(-w, h * 0.5), (w, h * 0.5), (w, -h * 0.05)]
    n = 6
    for i in range(1, n + 1):                       # right flank curving to the point
        t = i / n
        pts.append((w * (1 - t) ** 1.4, -h * 0.05 - h * 0.45 * t ** 0.8))
    for i in range(n - 1, 0, -1):
        t = i / n
        pts.append((-w * (1 - t) ** 1.4, -h * 0.05 - h * 0.45 * t ** 0.8))
    pts.append((-w, -h * 0.05))
    return pts


def emblem(k, parent, loc, normal, h=0.3):
    """Gold-rimmed blue shield with a white crenellated tower, flat on a surface."""
    e = _frame(k, parent, loc, normal)
    w = h * 0.42
    th = 0.006
    k.prism("emblem_rim", _shield(w, h), th, GOLD, y=0.0, parent=e, bevel=False)
    k.prism("emblem_field", _shield(w * 0.86, h * 0.86), th, BLUE, y=th * 0.8, parent=e, bevel=False)
    u = h * 0.06
    tower = [(-2 * u, -2.6 * u), (2 * u, -2.6 * u), (1.6 * u, 1.6 * u), (2.2 * u, 1.6 * u), (2.2 * u, 3.0 * u),
             (1.3 * u, 3.0 * u), (1.3 * u, 2.4 * u), (0.45 * u, 2.4 * u), (0.45 * u, 3.0 * u), (-0.45 * u, 3.0 * u),
             (-0.45 * u, 2.4 * u), (-1.3 * u, 2.4 * u), (-1.3 * u, 3.0 * u), (-2.2 * u, 3.0 * u),
             (-2.2 * u, 1.6 * u), (-1.6 * u, 1.6 * u)]
    k.prism("emblem_tower", tower, th, WHITE, y=th * 1.6, parent=e, bevel=False)
    k.prism("emblem_gate", [(-0.6 * u, -2.6 * u), (0.6 * u, -2.6 * u), (0.6 * u, -1.2 * u), (0, -0.7 * u),
                            (-0.6 * u, -1.2 * u)], th, BLUE, y=th * 2.4, parent=e, bevel=False)
    return e
