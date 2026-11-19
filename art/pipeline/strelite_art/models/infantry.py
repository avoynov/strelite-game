"""Infantry squad of the Iron Concord (bg: „Пехота“): five riflemen advancing at a
combat jog in a loose wedge, about 2.4 m across. Built to the guns' standard
(SOP "Human figures"): real human bodies (MakeHuman CC0 base mesh, each man his own
build and ancestry) on Blender's Rigify Human meta-rig, uniforms grown from the body,
gloved hands closed on the rifle by IK, full field gear, and a running cycle with the
feet planted by IK.

Real sizes: men 1.71 to 1.84 m; rifle 1.15 m (a long bolt-action of the 1900s-1940s
kind, 4 kg); pack 0.30 x 0.13 x 0.31 m; helmet bowl about 0.25 m.

What makes them unmistakable at game zoom: five upright figures, slate tunics, a
crested steel helmet with an oxblood band and brass goggles, rifles held across the
body, oxblood scarves at the throat, rolled blankets on their packs, the NCO's pennant.

Faction kit: slate uniform (the Concord's grey), oxblood scarf and helmet band, brass
gorget, crest, buttons, goggles and rifle bands, faction emblem on the left sleeve and
on the NCO's pennant.

Movement: a 12-frame running cycle driven by distance (MOVE_CYCLE_M metres per loop:
the stance foot moves back exactly that far, so feet stay planted at any game speed).
Each man runs with his own phase, so the squad never moves in step. The squad faces
local +Y; render_sprites.py --enemy turns the whole group.
"""
import math

from mathutils import Vector

from .. import human as hu
from .. import materials_photoreal as mp
from .. import mhuman as mh
from ..geo import Kit
from . import faction

SPRITE_FRAME_M = 5.6
LENGTH_M = 2.4
RADIUS_M = 1.2
MOVE_FRAMES = 12
MOVE_KIND = "walk"
MOVE_CYCLE_M = 1.85           # metres per running cycle (two steps); the stance foot moves back this far

SQUAD = [  # x, y, yaw deg, height m, phase, skin, body shape, role
    (0.0, 0.85, 0, 1.80, 0.00, "skin", dict(ancestry={"caucasian": 0.85, "asian": 0.15}, muscle=0.5), "nco"),
    (-0.95, 0.15, 6, 1.74, 0.55, "skin_fair", dict(ancestry={"caucasian": 1.0}, muscle=0.5, weight=0.42), "rifle"),
    (0.9, 0.25, -5, 1.84, 0.27, "skin_olive",
     dict(ancestry={"caucasian": 0.55, "asian": 0.2, "african": 0.25}, muscle=0.55, weight=0.45), "rifle"),
    (-0.5, -0.85, 3, 1.77, 0.80, "skin_dark", dict(ancestry={"african": 0.9, "caucasian": 0.1}, muscle=0.52, weight=0.45), "rifle"),
    (0.55, -0.75, -8, 1.71, 0.40, "skin", dict(ancestry={"caucasian": 0.7, "asian": 0.3}, weight=0.56), "rifle"),
]
_MEN = []          # (runner, phase, grips) per man, set by build()


def build(style, level=1, only=None):
    k = Kit(style)
    root = k.empty("infantry")
    mp.set_reference(root)
    _MEN.clear()
    for i, (x, y, yaw, h, ph, skin, shape, role) in enumerate(SQUAD):
        if only is not None and i not in only:
            continue
        man = k.empty(f"soldier{i}", (x, y, 0) if only is None else (0, 0, 0), parent=root)
        man.rotation_euler = (0, 0, math.radians(yaw))
        shape = dict(shape, height=0.5 + (h - 1.78) * 2.0)
        p, grips = soldier(k, man, i, h, skin, shape, role)
        _MEN.append((mh.Runner(p, cycle_m=MOVE_CYCLE_M), ph, grips))
    set_move_frame(0)
    return root, root


def set_move_frame(f, scene=None):
    mh.pose_group([r for r, _, _ in _MEN], [(f / MOVE_FRAMES + ph) % 1.0 for _, ph, _ in _MEN],
                  [g for _, _, g in _MEN])


# ---------------------------------------------------------------------------
def soldier(k, man, i, height, skin, shape, role):
    p = mh.Person(k, man, f"man{i}", height, shape, skin)
    mh.field_uniform(p)
    if role == "nco":
        mh.moustache(p)
    s = p.s
    bvh = p.surface()
    tunic = p.surface(["tunic"])

    def front(x, z):
        return p.hit(tunic, (x, 1.0, z), (0, -1, 0))

    def back(x, z):
        return p.hit(tunic, (x, -1.0, z), (0, 1, 0))

    # --- rifle across the body: right hand on the wrist of the stock by the right hip,
    #     left hand under the fore-end, muzzle forward, left and a little up
    J = p.J
    zg = J("r-upper-leg").z + 0.17 * s
    fh, _ = front(0.12 * s, zg)
    grip = Vector((0.12 * s, fh.y + 0.075 * s, zg))
    u = Vector((-0.34, 1.0, 0.16)).normalized()
    v = (Vector((0, 0, 1)) - u * u.z).normalized()
    r = u.cross(v)
    rf = k.empty("rifle", grip, parent=p.g)
    rf.rotation_euler = u.to_track_quat("Y", "Z").to_euler()
    _rifle(k, rf)
    p.attach(rf, "DEF-spine.003")
    # hand targets (person space), then into the rig's space
    sh_l, el_l, wr_l = J("l-shoulder"), J("l-elbow"), J("l-hand")
    reach = ((el_l - sh_l).length + (wr_l - el_l).length) * 0.97
    hold = 0.31 * s
    while True:
        pl = grip + u * hold + v * 0.012 * s
        wrist = pl - r * 0.075 * s - v * 0.028 * s
        if (wrist - sh_l).length <= reach or hold < 0.16:
            break
        hold -= 0.01
    pr = grip + u * -0.012 + v * -0.03 * s
    grips = {
        "R": (p.to_arm(pr), p.to_arm((u - v * 0.9).normalized()), p.to_arm((u + v).normalized())),
        "L": (p.to_arm(pl), p.to_arm((r + u * 0.25).normalized()), p.to_arm(u)),
    }

    _helmet(k, p)
    _gear(k, p, role, front, back, bvh)
    return p, grips


def _head_box(p):
    """Centre, half width, half length and top of the skull (person space)."""
    V = p.body.verts
    ey = p.body.J("l-eye")
    m = V[:, 2] > ey.z
    xs, ys = -V[m, 0], -V[m, 1]
    c = Vector(((xs.max() + xs.min()) / 2, (ys.max() + ys.min()) / 2, V[m, 2].max()))
    return c, (xs.max() - xs.min()) / 2, (ys.max() - ys.min()) / 2


def _helmet(k, p):
    """Crested steel helmet of the Concord: deep bowl, brim, brass comb, oxblood band,
    brass goggles pushed up on the front, leather chin strap. Fitted to this head."""
    c, hw, hl = _head_box(p)
    sx, sy = (hw + 0.024) / 0.133, (hl + 0.024) / 0.133
    sz = 0.5 * (sx + sy)
    g = k.empty("helmet", (c.x, c.y - 0.012, c.z - 0.123 * sz + 0.026), parent=p.g)
    g.scale = (sx, sy, sz)
    g.rotation_euler = (-0.16, 0, 0)                 # worn tipped back: the brim clears the eyes
    bowl = [(0.0, 0.123), (0.035, 0.124), (0.07, 0.115), (0.1, 0.095), (0.125, 0.06), (0.138, 0.025),
            (0.141, 0.0)]
    k.lathe("helmet_bowl", bowl, "paint_enemy_worn", segs=32, rot=(math.pi / 2, 0, 0), parent=g)
    k.cylinder("helmet_brim", 0.158, 0.012, (0, 0, -0.004), "paint_enemy_worn", segs=36, radius_top=0.122,
               parent=g, bevel=0.003)
    k.torus("helm_band", 0.124, 0.011, (0, 0, 0.022), "paint_faction_red", parent=g, segs=32, tube_segs=6)
    crest = [(-0.11, 0.06), (-0.06, 0.125), (0.0, 0.152), (0.06, 0.13), (0.11, 0.07), (0.1, 0.05), (0.0, 0.135),
             (-0.1, 0.045)]
    k.plate("helm_crest", crest, 0.012, 0.0, "brass", parent=g, bevel=0.002)
    for sxx in (-1, 1):                               # goggles on the front of the bowl
        k.cylinder("goggle", 0.022, 0.018, (sxx * 0.032, 0.112, 0.055), "brass", segs=16,
                   rot=(-math.pi / 2 + 0.35, 0, 0), parent=g, bevel=0.002)
        k.cylinder("goggle_lens", 0.016, 0.004, (sxx * 0.032, 0.129, 0.061), "glass", segs=16,
                   rot=(-math.pi / 2 + 0.35, 0, 0), parent=g, bevel=False)
        k.box("chin_strap", (0.008, 0.016, 0.11), (sxx * 0.118, 0.025, -0.065), "leather", rot=(0.15, 0, 0),
              parent=g, bevel=False)
    k.torus("goggle_strap", 0.126, 0.006, (0, 0, 0.05), "leather", rot=(0.06, 0, 0), parent=g, segs=32,
            tube_segs=5)
    p.attach(g, "DEF-spine.006")


def _rifle(k, rf):
    """Bolt-action rifle, origin at the wrist of the stock, barrel along +Y, built at 1:1."""
    stock = [(-0.38, -0.112), (-0.30, -0.095), (-0.08, -0.042), (-0.025, -0.075), (0.02, -0.07), (0.04, -0.03),
             (0.44, -0.024), (0.465, -0.01), (0.465, 0.01), (0.04, 0.016), (-0.04, 0.008), (-0.12, 0.016),
             (-0.38, 0.03)]
    k.plate("stock", stock, 0.04, 0.0, "wood", parent=rf, bevel=0.006)
    k.box("butt_plate", (0.042, 0.008, 0.145), (0, -0.384, -0.041), "brass", rot=(-0.06, 0, 0), parent=rf,
          bevel=0.002)
    k.box("receiver", (0.03, 0.2, 0.034), (0, 0.13, 0.032), "gunmetal", parent=rf, bevel=0.003)
    k.box("magazine", (0.028, 0.075, 0.04), (0, 0.15, -0.04), "gunmetal", parent=rf, bevel=0.003)
    k.torus("trigger_guard", 0.022, 0.004, (0, 0.06, -0.04), "brass", rot=(0, math.pi / 2, 0), parent=rf,
            segs=16, tube_segs=5)
    k.tube("bolt", (0.0, 0.05, 0.046), (0.0, 0.2, 0.046), 0.008, "steel_worn", parent=rf, segs=10, bevel=False)
    k.tube("bolt_handle", (0.006, 0.06, 0.046), (0.05, 0.05, 0.025), 0.005, "steel_worn", parent=rf, segs=8,
           bevel=False)
    k.cylinder("bolt_knob", 0.011, 0.016, (0.05, 0.05, 0.017), "steel_worn", segs=12, parent=rf, bevel=False)
    k.tube("barrel", (0, 0.2, 0.03), (0, 0.775, 0.03), 0.0095, "gunmetal", radius_end=0.0085, parent=rf, segs=14,
           bevel=False)
    k.beam("handguard", (0, 0.22, 0.04), (0, 0.42, 0.04), (0.03, 0.02), "wood", parent=rf, bevel=0.004)
    for y in (0.24, 0.43):
        k.box("band", (0.044, 0.016, 0.07), (0, y, 0.0), "brass", parent=rf, bevel=0.004)
    k.box("front_sight", (0.006, 0.012, 0.022), (0, 0.76, 0.048), "gunmetal", parent=rf, bevel=False)
    k.box("rear_sight", (0.026, 0.05, 0.012), (0, 0.24, 0.06), "gunmetal", parent=rf, bevel=False)
    k.box("bayonet_lug", (0.012, 0.03, 0.014), (0, 0.75, 0.014), "gunmetal", parent=rf, bevel=False)
    k.hose("sling", [(0.024, 0.43, -0.01), (0.03, 0.2, -0.17), (0.03, -0.05, -0.2), (0.024, -0.28, -0.1)],
           0.006, "leather", parent=rf)


def _on(k, p, name, size, hit, mat, up=Vector((0, 0, 1)), out=0.0, bevel=0.005, spin=0.0, bone=None):
    """A box lying on the surface at `hit` (point, normal): thin side along the normal."""
    loc, n = hit
    n = Vector(n).normalized()
    q = n.to_track_quat("Y", "Z")
    o = k.box(name, size, loc + n * (size[1] / 2 + out), mat, rot=q.to_euler(), parent=p.g, bevel=bevel)
    if spin:
        o.rotation_euler.rotate_axis("Y", spin)
    p.attach(o, bone or p.bone_at(loc))
    return o


def _ribbon(k, p, name, pts, nrms, width, thick, mat):
    """Strap lying on the body through points with surface normals (person space), skinned."""
    verts, faces = [], []
    for i, (c, n) in enumerate(zip(pts, nrms)):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        sd = t.cross(n).normalized() * (width / 2)
        for a, b in ((-1, 0), (1, 0), (1, 1), (-1, 1)):
            verts.append(c + sd * a + n * (0.003 + b * thick))
    m = len(pts)
    for i in range(m - 1):
        for j in range(4):
            jj = (j + 1) % 4
            faces.append((i * 4 + j, i * 4 + jj, (i + 1) * 4 + jj, (i + 1) * 4 + j))
    faces += [(0, 3, 2, 1), ((m - 1) * 4, (m - 1) * 4 + 1, (m - 1) * 4 + 2, (m - 1) * 4 + 3)]
    obj = k.mesh(name, verts, faces)
    k._finish(obj, mat, bevel=False, parent=p.g)
    p.skin_near(obj)
    return obj


def _gear(k, p, role, front, back, bvh):
    s = p.s
    J = p.J
    waist = J("spine-3").z + 0.01 * s
    # --- belt round the waist, on the cloth
    yf, _ = front(0.0, waist)
    yb, _ = back(0.0, waist)
    cy = 0.5 * (yf.y + yb.y)
    ring = []
    for i in range(40):
        a = 2 * math.pi * i / 40
        d = Vector((math.sin(a), math.cos(a), 0))
        hit, n = p.hit(bvh, Vector((0, cy, waist)) + d * 0.5, -d)
        ring.append((hit, n))
    verts, faces = [], []
    for c, n in ring:
        n = Vector((n.x, n.y, 0)).normalized()
        for dz, o in ((-0.028, 0.002), (0.028, 0.002), (0.028, 0.009), (-0.028, 0.009)):
            verts.append(c + n * o + Vector((0, 0, dz * s)))
    for i in range(40):
        ii = (i + 1) % 40
        for j in range(4):
            jj = (j + 1) % 4
            faces.append((i * 4 + j, i * 4 + jj, ii * 4 + jj, ii * 4 + j))
    belt = k.mesh("belt", verts, faces)
    k._finish(belt, "leather", bevel=False, parent=p.g)
    p.skin_near(belt)
    _on(k, p, "buckle", (0.065 * s, 0.012, 0.05 * s), front(0.0, waist), "brass", out=0.008, bevel=0.003)
    # ammunition pouches on the front of the belt
    for sx in (-1, 1):
        for x in (0.07, 0.135):
            h = front(sx * x * s, waist)
            _on(k, p, "pouch", (0.062 * s, 0.035, 0.072 * s), h, "leather", out=0.008, bevel=0.007)
            hh = (h[0] + Vector((0, 0, 0.034 * s)), h[1])
            _on(k, p, "pouch_flap", (0.066 * s, 0.04, 0.024 * s), hh, "leather", out=0.009, bevel=0.005)
    # --- Y-straps: belt front, over the shoulders, down the back to the pack
    sh_top = {}
    for sx in (-1, 1):
        pts, ns = [], []
        for z in [waist + 0.04 * s + i * 0.06 * s for i in range(6)]:
            h, n = front(sx * (0.095 - 0.02 * (z - waist) / 0.4) * s, z)
            pts.append(h)
            ns.append(n)
        for yy in (0.06, 0.0, -0.06):
            h, n = p.hit(bvh, (sx * 0.12 * s, yy * s, 2.2), (0, 0, -1))
            pts.append(h)
            ns.append(n)
        sh_top[sx] = pts[-2]
        for z in [J("neck").z - 0.12 * s - i * 0.07 * s for i in range(3)]:
            h, n = back(sx * 0.1 * s, z)
            pts.append(h)
            ns.append(n)
        _ribbon(k, p, "y_strap", pts, ns, 0.038 * s, 0.005, "webbing_pale")
    # --- tunic front: brass buttons, breast pockets with flaps, hip pockets, gorget
    zc = J("neck").z
    for i in range(4):
        z = waist + 0.07 * s + i * 0.075 * s
        h = front(0.0, z)
        _on(k, p, "button", (0.016 * s, 0.006, 0.016 * s), h, "brass", out=0.0, bevel=0.003)
    for sx in (-1, 1):
        h = front(sx * 0.1 * s, zc - 0.21 * s)
        _on(k, p, "breast_pocket", (0.09 * s, 0.008, 0.105 * s), h, "tunic_slate", out=-0.005, bevel=0.003)
        h = front(sx * 0.1 * s, zc - 0.155 * s)
        _on(k, p, "pocket_flap", (0.094 * s, 0.008, 0.034 * s), h, "tunic_slate", out=-0.002, bevel=0.003)
        h = front(sx * 0.12 * s, waist - 0.09 * s)
        _on(k, p, "hip_pocket", (0.1 * s, 0.008, 0.1 * s), h, "tunic_slate", out=-0.005, bevel=0.003)
        # shoulder straps (brass for the NCO)
        h = p.hit(bvh, (sx * 0.16 * s, 0.0, 2.2), (0, 0, -1))
        _on(k, p, "shoulder_strap", (0.055 * s, 0.01, 0.13 * s), h, "brass" if role == "nco" else "tunic_slate",
            out=0.0, bevel=0.004, spin=math.pi / 2)
    _on(k, p, "gorget", (0.12 * s, 0.012, 0.06 * s), front(0.0, zc - 0.085 * s), "brass", out=0.004, bevel=0.004)
    # --- oxblood scarf at the throat over the collar line
    V = p.body.verts
    nz = zc - 0.03 * s
    m = (abs(V[:, 2] - nz) < 0.012) & (abs(V[:, 0]) < 0.11)
    rx, ry = abs(V[m, 0]).max(), 0.5 * (V[m, 1].max() - V[m, 1].min())
    cy0 = -0.5 * (V[m, 1].max() + V[m, 1].min())
    ax = Vector((0, 0.6, 1)).normalized()
    c0 = Vector((0, cy0, nz - 0.01 * s))
    c0 = c0 - Vector((0, 0, 0.012 * s))
    scarf = hu.loft(k, "scarf", [dict(c=c0 - ax * 0.012, rx=rx + 0.022, ry=ry + 0.024),
                                 dict(c=c0 + ax * 0.012, rx=rx + 0.015, ry=ry + 0.017),
                                 dict(c=c0 + ax * 0.03, rx=rx + 0.009, ry=ry + 0.011)],
                    "cloth_oxblood", p.g, segs=20, caps=(False, False), subsurf=1)
    p.skin_near(scarf)
    hk, nk = front(0.0, nz - 0.05 * s)
    knot = k.box("scarf_knot", (0.05 * s, 0.035, 0.055 * s), hk + nk * 0.02, "cloth_oxblood",
                 rot=(-0.3, 0, 0.2), parent=p.g, bevel=0.014)
    p.attach(knot, "DEF-spine.003")
    for sx, ang in ((-1, 0.25), (1, -0.18)):           # the two tails hang over the chest
        ht, nt = front(sx * 0.025 * s, nz - 0.12 * s)
        tail = k.box("scarf_tail", (0.045 * s, 0.012, 0.11 * s), ht + nt * 0.012, "cloth_oxblood",
                     rot=(nt.to_track_quat("Y", "Z").to_euler()), parent=p.g, bevel=0.006)
        tail.rotation_euler.rotate_axis("Y", ang)
        p.attach(tail, "DEF-spine.003")
    # --- pack with a blanket roll, mess tin and entrenching tool
    hb, _ = back(0.0, zc - 0.25 * s)
    pk = k.empty("pack", (0, hb.y - 0.07, zc - 0.25 * s), parent=p.g)
    k.box("pack_body", (0.3 * s, 0.13, 0.31 * s), (0, 0, 0), "canvas", parent=pk, bevel=0.035)
    k.box("pack_flap", (0.31 * s, 0.07, 0.13 * s), (0, -0.04, 0.1 * s), "canvas", rot=(0.12, 0, 0),
          parent=pk, bevel=0.025)
    for sx in (-1, 1):
        k.box("pack_strap", (0.03 * s, 0.14, 0.006), (sx * 0.08 * s, -0.005, 0.03 * s), "leather",
              rot=(math.pi / 2, 0, 0), parent=pk, bevel=False)
        k.box("pack_buckle", (0.03 * s, 0.006, 0.02 * s), (sx * 0.08 * s, -0.072, -0.03 * s), "brass",
              parent=pk, bevel=False)
    k.cylinder("blanket_roll", 0.055 * s, 0.4 * s, (0.0, 0.0, 0.2 * s), "canvas", segs=18,
               rot=(0, math.pi / 2, 0), parent=pk, bevel=0.02)
    for sx in (-1, 1):
        k.torus("roll_strap", 0.058 * s, 0.005, (sx * 0.1 * s, 0.0, 0.2 * s), "leather",
                rot=(0, math.pi / 2, 0), parent=pk, segs=18, tube_segs=4)
    k.cylinder("mess_tin", 0.065 * s, 0.04, (0.0, -0.085, -0.06 * s), "steel_worn", segs=20,
               rot=(math.pi / 2, 0, 0), parent=pk, bevel=0.004)
    k.tube("shovel_haft", (0.17 * s, 0.0, -0.14 * s), (0.17 * s, 0.0, 0.12 * s), 0.014, "wood", parent=pk, segs=8)
    k.box("shovel_blade", (0.012, 0.13, 0.17 * s), (0.17 * s, 0.0, -0.22 * s), "steel_worn", parent=pk,
          bevel=0.004)
    if role == "nco":                                # oxblood pennant on a brass mast from the pack
        faction.pennant(k, pk, (-0.12 * s, -0.04, 0.12 * s), h=0.75 * s, w=0.32 * s)
    p.attach(pk, "DEF-spine.003")
    # --- canteen and bayonet on the left hip (person's left is -X)
    hl, nl = p.hit(bvh, (-1.0, -0.02, waist - 0.12 * s), (1, 0, 0))
    cn = k.empty("canteen", hl + Vector((-0.045, -0.02, 0.0)), parent=p.g)
    k.lathe("canteen_body", [(-0.04, 0.0), (-0.04, 0.06), (-0.03, 0.075), (0.03, 0.075), (0.04, 0.06), (0.04, 0.0)],
            "canvas", segs=18, rot=(0, 0, math.pi / 2), parent=cn).scale = (s, s * 0.55, s * 1.3)
    k.cylinder("canteen_cap", 0.016 * s, 0.03, (0, 0, 0.095 * s), "brass", segs=10, parent=cn, bevel=False)
    p.attach(cn, "DEF-spine")
    hs, _ = p.hit(bvh, (-1.0, -0.09, waist - 0.05 * s), (1, 0, 0))
    sc = k.tube("scabbard", hs + Vector((-0.02, 0.0, 0.0)), hs + Vector((-0.04, -0.06, -0.3 * s)), 0.017,
                "leather", radius_end=0.01, parent=p.g, segs=10)
    p.attach(sc, "DEF-spine")
    # --- faction emblem on the outside of the left sleeve
    sh, el = J("l-shoulder"), J("l-elbow")
    mid = sh.lerp(el, 0.32)
    he, ne = p.hit(bvh, (mid.x - 0.4, mid.y, mid.z), (1, 0, 0))
    faction.emblem(k, p.g, he + ne * 0.003, ne, r=0.028 * s)
    for o in [c for c in p.g.children if c.name.startswith("emblem")]:
        p.attach(o, p.bone_at(he))
