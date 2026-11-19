"""Quick look at a moving enemy: render chosen movement frames at one heading.

  python3 tools/figure_test.py --model infantry --only 0 --frames 0 3 6 9 --dir 10 \
      --frame-m 2.4 --target-z 0.9 --ppm 300 --out /tmp/fig

Writes <out>/f_FF.png. --only picks members of a group by index (close-ups)."""
import argparse
import importlib
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bpy  # noqa: E402

from strelite_art import materials, materials_photoreal, scene as stage  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--model", default="infantry")
ap.add_argument("--only", type=int, nargs="*")
ap.add_argument("--frames", type=int, nargs="+", default=[0])
ap.add_argument("--dir", type=float, default=10, help="heading index of 16")
ap.add_argument("--frame-m", type=float, default=None)
ap.add_argument("--target-z", type=float, default=0.0)
ap.add_argument("--ppm", type=float, default=64)
ap.add_argument("--samples", type=int, default=16)
ap.add_argument("--out", default="/tmp/fig")
a = ap.parse_args()

model = importlib.import_module(f"strelite_art.models.{a.model}")
materials.clear_cache()
frame_m = a.frame_m or model.SPRITE_FRAME_M
size = int(round(frame_m * a.ppm / 2)) * 2
scene = stage.build_stage("photoreal", size, a.samples, frame_m=frame_m,
                          ground="none" if getattr(model, "FLYING", False) else "patch",
                          target_z=a.target_z, projection="ortho", catcher_hole=0.0)
scene.render.film_transparent = True
scene.cycles.seed = 1
kw = {"only": a.only} if a.only is not None else {}
root, _ = model.build("photoreal", 1, **kw)
materials_photoreal.stamp(scene)
heading = 2 * math.pi * a.dir / 16
root.rotation_euler = (0, 0, -heading - math.pi / 2)
os.makedirs(a.out, exist_ok=True)
for f in a.frames:
    if hasattr(model, "set_move_frame"):
        model.set_move_frame(f)
    scene.render.filepath = os.path.join(a.out, f"f_{f:02d}.png")
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"frame {f}: {time.time() - t:.1f}s", flush=True)
