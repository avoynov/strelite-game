"""Render isometric sprites for a model.

Usage:
  python3 render_sprites.py --model cannon --style stylized --levels 1 2 3 --dirs 8 --out ../out

Output: <out>/<model>/<style>/L<level>/dir_<NN>.png (RGBA, shadow kept in alpha).
Direction NN aims the turret at yaw = NN * 360/dirs degrees, counter-clockwise
from world +Y. dir_00 points toward the upper-right of the screen.
"""
import argparse
import importlib
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from strelite_art import materials, scene as stage  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="cannon")
    ap.add_argument("--style", choices=stage.STYLES, default="stylized")
    ap.add_argument("--levels", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--dirs", type=int, default=8)
    ap.add_argument("--only-dir", type=int, nargs="*", help="render only these direction indices")
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "out"))
    a = ap.parse_args(argv)

    model = importlib.import_module(f"strelite_art.models.{a.model}")
    for level in a.levels:
        materials.clear_cache()
        scene = stage.build_stage(a.style, a.size, a.samples)
        _, turret = model.build(a.style, level)
        out_dir = os.path.join(a.out, a.model, a.style, f"L{level}")
        os.makedirs(out_dir, exist_ok=True)
        dirs = a.only_dir if a.only_dir else range(a.dirs)
        for d in dirs:
            turret.rotation_euler = (0, 0, math.radians(d * 360 / a.dirs))
            scene.render.filepath = os.path.join(out_dir, f"dir_{d:02d}.png")
            t = time.time()
            bpy.ops.render.render(write_still=True)
            print(f"[render] {a.model} {a.style} L{level} dir {d}: {time.time() - t:.1f}s",
                  flush=True)


if __name__ == "__main__":
    main()
