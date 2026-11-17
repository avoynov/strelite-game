"""Render the game's ground as one seamless tile in the photoreal style.

The tile is a square of real ground (`--metres` on a side, aligned with the
screen, i.e. turned 45 deg to the grid) seen through the game's 2:1 camera, so
the picture is twice as wide as it is tall and repeats in both screen
directions. The render covers a little more than one tile; the overlap is
cross-faded along an irregular line, which hides the seam in soil and grass.

Usage:
    python3 render_ground.py                              # the field, 64 m
    python3 render_ground.py --kind road --metres 32      # packed earth for the road
Output: <dst>/ground/<name>@2x.webp, <name>@1x.webp and an entry in <dst>/towers.json
"""
import argparse
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402


def render(a, path):
    import bpy

    from strelite_art import scene as stage
    from strelite_art.terrain import Field, Road
    width_m = a.metres + a.overlap
    w = int(round(width_m * a.ppm))
    scene = stage.build_stage("photoreal", w, a.samples, frame_m=width_m, ground="none",
                              target_z=0.0, projection="ortho")
    scene.render.resolution_x, scene.render.resolution_y = w, w // 2
    scene.render.film_transparent = False
    t = time.time()
    size = width_m * math.sqrt(2) + 4.0
    if a.kind == "road":
        Road(size, seed=a.seed).build(scene)
    else:
        Field(size, seed=a.seed, grass=a.grass, patchiness=a.patchiness).build(scene)
    print(f"[ground] terrain built in {time.time() - t:.0f}s", flush=True)
    scene.render.filepath = path
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"[ground] rendered {w}x{w // 2} in {time.time() - t:.0f}s", flush=True)


def make_seamless(img, tile_w, tile_h, seed=5):
    """img is (tile_h + oy, tile_w + ox). Cross-fade the overlap so the result tiles."""
    a = np.asarray(img.convert("RGB"), np.float32)
    H, W = a.shape[:2]
    ox, oy = W - tile_w, H - tile_h
    rng = np.random.default_rng(seed)

    def wobble(rows, cols, shape):
        g = rng.standard_normal(shape).astype(np.float32)
        return np.asarray(Image.fromarray(g, "F").resize((cols, rows), Image.BICUBIC))

    # horizontal wrap: columns 0..ox blend from the picture beyond the right edge
    x = (np.arange(ox, dtype=np.float32)[None, :] + 0.5) / ox
    t = np.clip((x - 0.5) * 2.2 + 0.5 + wobble(H, ox, (max(4, H // 40), 3)) * 0.45, 0, 1)
    t = (t * t * (3 - 2 * t))[..., None]
    a[:, :ox] = a[:, :ox] * t + a[:, tile_w:tile_w + ox] * (1 - t)
    a = a[:, :tile_w]
    # vertical wrap
    y = (np.arange(oy, dtype=np.float32)[:, None] + 0.5) / oy
    t = np.clip((y - 0.5) * 2.2 + 0.5 + wobble(oy, tile_w, (3, max(4, tile_w // 40))) * 0.45, 0, 1)
    t = (t * t * (3 - 2 * t))[..., None]
    a[:oy] = a[:oy] * t + a[tile_h:tile_h + oy] * (1 - t)
    a = a[:tile_h]
    return Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8))


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--metres", type=float, default=64.0, help="side of the repeating square")
    ap.add_argument("--overlap", type=float, default=4.0, help="extra metres rendered for the cross-fade")
    ap.add_argument("--ppm", type=float, default=32.0)
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--seed", type=int, default=31)
    ap.add_argument("--kind", choices=["field", "road"], default="field")
    ap.add_argument("--grass", type=float, default=0.85, help="0 bare soil .. 1 meadow")
    ap.add_argument("--patchiness", type=float, default=0.4,
                    help="edge hardness between turf and bare soil; lower is calmer")
    ap.add_argument("--name", default=None, help="file and manifest name (default: --kind)")
    ap.add_argument("--raw", default=None)
    ap.add_argument("--dst", default=os.path.join(here, "..", "..", "public", "art"))
    ap.add_argument("--reuse", action="store_true", help="skip the render, reuse --raw")
    a = ap.parse_args()
    a.name = a.name or a.kind
    a.raw = a.raw or os.path.join(here, "..", "out", f"ground_{a.name}_raw.png")
    if not a.reuse:
        os.makedirs(os.path.dirname(a.raw), exist_ok=True)
        render(a, a.raw)
    tw = int(round(a.metres * a.ppm))
    tile = make_seamless(Image.open(a.raw), tw, tw // 2)
    out = os.path.join(a.dst, "ground")
    os.makedirs(out, exist_ok=True)
    tile.save(os.path.join(out, f"{a.name}@2x.webp"), quality=90, method=6)
    tile.resize((tw // 2, tw // 4), Image.LANCZOS).save(os.path.join(out, f"{a.name}@1x.webp"),
                                                         quality=90, method=6)
    path = os.path.join(a.dst, "towers.json")
    manifest = {}
    if os.path.exists(path):
        with open(path) as f:
            manifest = json.load(f)
    manifest.setdefault("ground", {})[a.name] = {
        "image": f"ground/{a.name}",
        "sizePx1x": [tw // 2, tw // 4],
        "metres": a.metres,
        "note": "seamless in both screen directions; draw as a tiling sprite at the same "
                "pxPerMetre as the towers",
    }
    with open(path, "w") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
    print(f"[ground] wrote {out}/{a.name}@2x.webp ({tw}x{tw // 2}) and @1x")


if __name__ == "__main__":
    main()
