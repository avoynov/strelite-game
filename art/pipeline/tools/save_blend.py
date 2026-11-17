"""Save the procedural photoreal models as .blend files (one per model and level),
so they can be opened, inspected and reused in Blender without running the pipeline.

Each file holds the tower as built for the game sprites: camera, physical sky,
materials, node empties (`turret`, `elevating`, `recoil`) and the static kit.
`--ground` also adds the soil patch with its stones and grass (much bigger file).

Usage:
    python3 tools/save_blend.py --models howitzer zis3 --levels 1 2 3 --out ../blend
"""
import argparse
import importlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import bpy  # noqa: E402

from strelite_art import materials, materials_photoreal, scene as stage  # noqa: E402
from strelite_art.terrain import Patch  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["howitzer", "zis3"])
    ap.add_argument("--levels", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--ground", action="store_true")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "..", "blend"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for name in a.models:
        model = importlib.import_module(f"strelite_art.models.{name}")
        for level in a.levels:
            materials.clear_cache()
            frame_m = model.SPRITE_FRAME_M
            patch = model.ground(level)
            scene = stage.build_stage("photoreal", int(frame_m * 32), 32, frame_m=frame_m,
                                      ground="patch", target_z=0.0, projection="ortho",
                                      catcher_hole=patch.r_solid - Patch.CATCHER_INSET)
            model.build("photoreal", level)
            materials_photoreal.stamp(scene)
            if a.ground:
                patch.build(scene)
            bpy.ops.file.pack_all()                      # stencil images travel inside the file
            path = os.path.abspath(os.path.join(a.out, f"{name}_L{level}.blend"))
            bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
            print(f"[blend] {path}: {os.path.getsize(path) / 2**20:.1f} MB", flush=True)


if __name__ == "__main__":
    main()
