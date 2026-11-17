"""Clean gun portraits for menus (the Arsenal screen): the gun alone, no soil patch and
no fortifications, on a transparent background with only its own shadow.

Same camera, light and materials as the game sprites (orthographic 2:1, frame NN aims
at game angle NN * 2*pi/dirs), so the pictures match the board.

  python3 render_portraits.py --model howitzer --levels 1 2 3 --dirs 32 --ppm 48 --out ../out
writes <out>/portraits/<model>/L<level>/aim_NN.png; pack_portraits.py turns them into atlases.
"""
import argparse
import importlib
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from strelite_art import materials, materials_photoreal, scene as stage  # noqa: E402

# Metres across the square render: room for the barrel in every heading plus its shadow.
FRAME_M = {"howitzer": 15.0, "zis3": 11.0}


def render(model_name, level, a):
    model = importlib.import_module(f"strelite_art.models.{model_name}")
    materials.clear_cache()
    frame_m = a.frame or FRAME_M.get(model_name, model.SPRITE_FRAME_M)
    size = int(round(frame_m * a.ppm / 2)) * 2
    scene = stage.build_stage("photoreal", size, a.samples, frame_m=frame_m, ground="patch",
                              target_z=0.0, projection="ortho", catcher_hole=0.0)
    scene.cycles.seed = 1
    scene.render.use_persistent_data = True
    _, turret = model.build("photoreal", level)
    materials_photoreal.stamp(scene)

    gun, stack = set(), [turret]
    while stack:
        o = stack.pop()
        gun.add(o)
        stack.extend(o.children)
    # Hide the static kit (sandbags, slab, crates, nets): only the gun stays.
    for o in scene.objects:
        if o.type in {"MESH", "CURVE"} and o not in gun and not o.is_shadow_catcher:
            o.hide_render = True

    out_dir = os.path.join(a.out, "portraits", model_name, f"L{level}")
    os.makedirs(out_dir, exist_ok=True)
    for i in range(a.dirs):
        if a.only_dir is not None and i not in a.only_dir:
            continue
        path = os.path.join(out_dir, f"aim_{i:02d}.png")
        if a.resume and os.path.exists(path) and os.path.getsize(path) > 0:
            continue
        aim = 2 * math.pi * i / a.dirs
        turret.rotation_euler = (0, 0, -aim - math.pi / 2)
        bpy.context.view_layer.update()
        scene.render.filepath = path
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"[portrait] {model_name} L{level} {i:02d}: {time.time() - t:.1f}s", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--levels", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--dirs", type=int, default=32)
    ap.add_argument("--only-dir", type=int, nargs="*")
    ap.add_argument("--ppm", type=float, default=48.0)
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--frame", type=float, default=None)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "out"))
    a = ap.parse_args(argv)
    for level in a.levels:
        render(a.model, level, a)


if __name__ == "__main__":
    main()
