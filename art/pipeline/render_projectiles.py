"""Flying rounds of the siege engines, as small tumbling sprite loops.

For every level the model's round (model.build_round(kit, parent, level)) is rendered alone,
lit like the towers, through the game camera, turning about a tilted axis in --frames
steps. The game draws it along its flight path with its own ground shadow (a dark ellipse
under the round; the sprites carry no shadow). The anchor is the centre of the round.

Writes <dst>/projectiles/<model>@1x|@2x (.webp + .json, frames <model>_L<n>_round_FF,
animations <model>_L<n>_round) and a "projectiles" entry per model in towers.json.

Usage: python3 render_projectiles.py --model trebuchet
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from pack_atlas import bbox, load_premultiplied, pack, to_image  # noqa: E402
from strelite_art import materials, scene as stage  # noqa: E402


def render(model, a, out_dir):
    import importlib
    from strelite_art import materials_photoreal
    from strelite_art.geo import Kit
    mod = importlib.import_module(f"strelite_art.models.{model}")
    size = int(round(a.frame_m * a.ppm / 2)) * 2
    for level in mod.LEVELS:
        materials.clear_cache()
        scene = stage.build_stage("photoreal", size, a.samples, frame_m=a.frame_m, ground="none",
                                  target_z=0.0, projection="ortho")
        scene.render.film_transparent = True
        scene.cycles.seed = 1
        k = Kit("photoreal")
        spin = k.empty("spin")
        materials_photoreal.set_reference(spin)
        mod.build_round(k, spin, level)
        materials_photoreal.stamp(scene)
        for f in range(a.frames):
            spin.rotation_euler = (2 * math.pi * f / a.frames, 0.5, 0.3)
            path = os.path.join(out_dir, f"L{level}_{f:02d}.png")
            scene.render.filepath = path
            if not (a.resume and os.path.exists(path)):
                bpy.ops.render.render(write_still=True)
        print(f"[round] {model} L{level}: {a.frames} frames", flush=True)
    return mod


def pack_rounds(model, mod, a, out_dir):
    dst = os.path.join(a.dst, "projectiles")
    os.makedirs(dst, exist_ok=True)
    for tag, scale in (("@2x", 1.0), ("@1x", 0.5)):
        names, frames = [], []
        for level in mod.LEVELS:
            for f in range(a.frames):
                names.append(f"{model}_L{level}_round_{f:02d}")
                frames.append(load_premultiplied(os.path.join(out_dir, f"L{level}_{f:02d}.png"), scale))
        H, W = frames[0].shape[:2]
        boxes = [bbox(pm) for pm in frames]
        pos, AW, AH = pack([(b[2] - b[0], b[3] - b[1]) for b in boxes])
        atlas = Image.new("RGBA", (AW, AH), (0, 0, 0, 0))
        anims = {f"{model}_L{level}_round": [f"{model}_L{level}_round_{f:02d}" for f in range(a.frames)]
                 for level in mod.LEVELS}
        sheet = {"frames": {}, "animations": anims}
        for name, pm, b, (x, y) in zip(names, frames, boxes, pos):
            w, h = b[2] - b[0], b[3] - b[1]
            atlas.paste(to_image(pm[b[1]:b[3], b[0]:b[2]]), (x, y))
            sheet["frames"][name] = {
                "frame": {"x": x, "y": y, "w": w, "h": h}, "rotated": False, "trimmed": True,
                "spriteSourceSize": {"x": b[0], "y": b[1], "w": w, "h": h},
                "sourceSize": {"w": W, "h": H}, "anchor": {"x": 0.5, "y": 0.5}}
        img = f"{model}{tag}.webp"
        atlas.save(os.path.join(dst, img), quality=92, method=6, alpha_quality=100)
        sheet["meta"] = {"app": "strelite art pipeline", "image": img, "format": "RGBA8888",
                         "size": {"w": AW, "h": AH}, "scale": "2" if tag == "@2x" else "1"}
        with open(os.path.join(dst, f"{model}{tag}.json"), "w") as fh:
            json.dump(sheet, fh, separators=(",", ":"))
        print(f"[round] {model}{tag}: atlas {AW}x{AH}", flush=True)
    path = os.path.join(a.dst, "towers.json")
    with open(path) as fh:
        manifest = json.load(fh)
    manifest.setdefault("projectiles", {})[model] = {
        "sheet": f"projectiles/{model}", "levels": list(mod.LEVELS), "frames": a.frames, "fps": a.fps,
        "radiusM": getattr(mod, "PROJ_R", None),
        "animation": f"{model}_L<level>_round",
        "note": "tumbling round, no shadow: draw a dark ellipse on the ground below it",
    }
    with open(path, "w") as fh:
        json.dump(manifest, fh, indent=1, ensure_ascii=False)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="trebuchet")
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--fps", type=int, default=16)
    ap.add_argument("--frame-m", type=float, default=1.4)
    ap.add_argument("--ppm", type=float, default=32.0)
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--out", default=os.path.join(here, "..", "out"))
    ap.add_argument("--dst", default=os.path.join(here, "..", "..", "public", "art"))
    ap.add_argument("--no-pack", action="store_true")
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    out_dir = os.path.join(a.out, "projectiles", a.model)
    os.makedirs(out_dir, exist_ok=True)
    mod = render(a.model, a, out_dir)
    if not a.no_pack:
        pack_rounds(a.model, mod, a, out_dir)


if __name__ == "__main__":
    main()
