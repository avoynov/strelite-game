"""Reconnaissance-strike drone (bg: „Дрон“): a large fixed-wing unmanned aircraft, generic
type, 6 m long with an 8.5 m wing, slender fuselage with a bulged nose, sensor ball under
the chin, inverted V tail and a pusher propeller. The flying enemy; dark grey.

FLYING: rendered alone without a ground shadow; the game draws it at its flight height
over the road and puts a dark ellipse on the ground below it.
The aircraft faces local +Y; render_sprites.py --enemy turns it. Returns (root, root).
"""
import math

from mathutils import Vector

from .. import materials_photoreal as mp
from ..geo import Kit

SPRITE_FRAME_M = 10.0
LENGTH_M = 6.0
RADIUS_M = 3.0
FLYING = True
FLIGHT_HEIGHT_M = 9.0     # suggested height above the road
G, WORN = "paint_enemy", "paint_enemy_worn"


def build(style, level=1):
    k = Kit(style)
    root = k.empty("drone")
    mp.set_reference(root)
    body = k.empty("body", (0, 0, 0), parent=root)
    body.rotation_euler = (math.radians(2), math.radians(4), 0)        # slight bank, nose up
    prof = [(-3.0, 0.0), (-2.9, 0.12), (-2.2, 0.2), (-0.5, 0.33), (1.2, 0.36), (2.2, 0.44), (2.75, 0.36),
            (3.0, 0.16), (3.05, 0.0)]
    f = k.lathe("fuselage", prof, G, segs=32, parent=body)
    f.scale = (1.0, 1.0, 0.92)
    k.lathe("sensor_ball", [(-0.2, 0.0), (-0.16, 0.13), (0.0, 0.2), (0.16, 0.13), (0.2, 0.0)], "gunmetal", segs=20,
            loc=(0, 2.25, -0.48), parent=body)
    k.cylinder("sensor_glass", 0.08, 0.02, (0, 2.42, -0.5), "glass", segs=16, rot=(-math.pi / 2, 0, 0), parent=body,
               bevel=False)
    # main wing, slightly tapered, with dihedral
    for sx in (-1, 1):
        root_le, tip_le = Vector((sx * 0.25, 0.75, 0.15)), Vector((sx * 4.25, 0.35, 0.42))
        k.beam("wing", root_le + Vector((0, -0.45, 0)), tip_le + Vector((0, -0.25, 0)), (0.9, 0.09), G,
               section_end=(0.5, 0.05), parent=body, bevel=0.012)
        k.box("aileron", (0.08, 1.4, 0.04), tip_le + Vector((-sx * 1.0, -0.62, -0.05)), WORN, parent=body,
              rot=(0, 0, math.pi / 2), bevel=False)
        k.box("hardpoint", (0.1, 0.4, 0.12), (sx * 1.6, 0.42, 0.07), G, parent=body, bevel=0.01)
        k.lathe("missile", [(-0.7, 0.0), (-0.68, 0.07), (0.55, 0.07), (0.7, 0.0)], WORN, segs=14,
                loc=(sx * 1.6, 0.45, -0.07), parent=body)
        # inverted V tail
        k.beam("tail", (sx * 0.1, -2.55, -0.05), (sx * 1.05, -2.85, -0.75), (0.55, 0.05), G, section_end=(0.3, 0.04),
               parent=body, bevel=0.01)
    # pusher propeller
    k.cylinder("spinner", 0.12, 0.25, (0, -3.0, 0), "gunmetal", segs=16, rot=(math.pi / 2, 0, 0), parent=body,
               radius_top=0.03)
    for a in (0.4, 0.4 + math.pi):
        d = Vector((math.cos(a), 0, math.sin(a)))
        k.beam("blade", Vector((0, -3.1, 0)) + d * 0.1, Vector((0, -3.1, 0)) + d * 0.92, (0.12, 0.02), "gunmetal",
               section_end=(0.06, 0.015), parent=body, bevel=False)
    k.tube("antenna", (0, 1.0, 0.3), (0, 0.8, 0.62), 0.012, "gunmetal", parent=body, segs=6, bevel=False)
    k.box("satcom_bulge", (0.5, 1.0, 0.2), (0, 1.6, 0.33), G, parent=body, bevel=0.08)
    return root, root
