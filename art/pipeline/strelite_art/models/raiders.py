"""The defenders' raiding party (bg: „Разузнавачи“): the player's own riders who dash out
of the base to provoke the enemy („Провокирай врага“), then race back with the attackers
in pursuit. The same three heavy motorcycles and seated riders as the Iron Concord's
raiders (models/bikers.py), repainted to the defenders' side so the two can never be
confused at game zoom: 4BO green machines with blue bands, olive tunics, blue scarves,
green helmets, the blue-and-gold tower shield in place of the cog-and-spear, a blue
pennant on the leader's machine. Same size, headings and wheel movement as the bikers.
"""
from . import bikers, defender

SPRITE_FRAME_M = bikers.SPRITE_FRAME_M
LENGTH_M = bikers.LENGTH_M
RADIUS_M = bikers.RADIUS_M
MOVE_FRAMES = bikers.MOVE_FRAMES
MOVE_KIND = bikers.MOVE_KIND
MOVE_CYCLE_M = bikers.MOVE_CYCLE_M

SWAP = {"paint_enemy": "paint_4bo", "paint_enemy_worn": "paint_4bo_worn", "paint_faction_red": "paint_blue",
        "tunic_slate": "tunic_olive", "cloth_oxblood": "cloth_blue"}


def set_move_frame(f, scene=None):
    bikers.set_move_frame(f, scene)


def build(style, level=1, only=None):
    import bpy
    from mathutils import Vector

    from .. import materials
    from ..geo import Kit
    root, _ = bikers.build(style, level, only)
    bpy.context.view_layer.update()
    k = Kit(style)
    for e in [o for o in list(bpy.data.objects) if o.type == "EMPTY" and o.name.startswith("emblem")
              and _under(o, root)]:
        mw = e.matrix_world.copy()
        normal = (mw.to_3x3() @ Vector((0, 0, 1))).normalized()
        size = max((c.dimensions.x for c in e.children if c.type == "MESH"), default=0.2)
        loc = e.location.copy()
        parent = e.parent
        n_local = (parent.matrix_world.to_3x3().inverted() @ normal).normalized() if parent else normal
        for c in list(e.children_recursive):
            bpy.data.objects.remove(c)
        bpy.data.objects.remove(e)
        defender.emblem(k, parent, loc, n_local, h=size * 1.1)
    for o in [o for o in bpy.data.objects if o.type in ("MESH", "CURVE") and _under(o, root)]:
        for i, m in enumerate(o.data.materials):
            if m is None:
                continue
            base = m.name.split("__")[0]
            if base in SWAP:
                o.data.materials[i] = materials.get(SWAP[base], style)
    return root, root


def _under(o, root):
    while o is not None:
        if o == root:
            return True
        o = o.parent
    return False
