"""Render and pack the siege-mode wall pieces (strelite_art/models/fences.py).

Each piece is rendered alone, same camera for all, ground point of the tile centre at the
frame centre, shadow kept in alpha:
  <out>/fences/<material>/<piece>.png  (+ meta.json with the screen step of one tile)
then packed into <dst>/fences/<material>@1x|@2x (.webp + PixiJS .json, frames
<material>_<piece>) and a "fences" entry in <dst>/towers.json.

  python3 render_fences.py --materials wood stone steel --samples 32
  python3 render_fences.py --review out.jpg      # assemble a sample wall for review
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FRAME_M = 7.5
HERE = os.path.dirname(os.path.abspath(__file__))


def render(a):
    import bpy
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector

    from strelite_art import materials, materials_photoreal, scene as stage
    from strelite_art.models import fences

    size = int(round(FRAME_M * a.ppm / 2)) * 2
    for mat in a.materials:
        out_dir = os.path.join(a.out, "fences", mat)
        os.makedirs(out_dir, exist_ok=True)
        for piece in fences.PIECES:
            path = os.path.join(out_dir, f"{piece}.png")
            if a.resume and os.path.exists(path):
                continue
            materials.clear_cache()
            scene = stage.build_stage("photoreal", size, a.samples, frame_m=FRAME_M, ground="patch",
                                      target_z=0.0, projection="ortho", catcher_hole=0.0)
            scene.render.film_transparent = True
            scene.cycles.seed = 1
            fences.build(mat, piece)
            materials_photoreal.stamp(scene)
            scene.render.filepath = path
            t = time.time()
            bpy.ops.render.render(write_still=True)
            print(f"[render] fence {mat} {piece}: {time.time() - t:.1f}s", flush=True)

            def px(p):
                v = world_to_camera_view(scene, scene.camera, Vector(p))
                return [(v.x - 0.5) * size, (0.5 - v.y) * size]
            meta = {"material": mat, "pxPerMetre": a.ppm, "frame": [size, size], "anchorPx": [size / 2, size / 2],
                    "gridXStepPx": px((4, 0, 0)), "gridYStepPx": px((0, -4, 0)),
                    "heightM": fences.HEIGHT[mat], "thicknessM": fences.THICK[mat]}
        with open(os.path.join(out_dir, "meta.json"), "w") as f:
            json.dump(meta, f, indent=1)


def pack(a):
    from PIL import Image

    from pack_atlas import bbox, load_premultiplied, pack as pack_rects, to_image
    from strelite_art.models.fences import NAMES, PIECES

    os.makedirs(os.path.join(a.dst, "fences"), exist_ok=True)
    entry = {}
    for mat in a.materials:
        d = os.path.join(a.out, "fences", mat)
        with open(os.path.join(d, "meta.json")) as f:
            meta = json.load(f)
        for tag, scale in (("@2x", 1.0), ("@1x", 0.5)):
            frames = [load_premultiplied(os.path.join(d, f"{p}.png"), scale) for p in PIECES]
            H, W = frames[0].shape[:2]
            boxes = [bbox(pm) for pm in frames]
            pos, AW, AH = pack_rects([(b[2] - b[0], b[3] - b[1]) for b in boxes])
            atlas = Image.new("RGBA", (AW, AH), (0, 0, 0, 0))
            sheet = {"frames": {}}
            for p, pm, b, (x, y) in zip(PIECES, frames, boxes, pos):
                w, h = b[2] - b[0], b[3] - b[1]
                atlas.paste(to_image(pm[b[1]:b[3], b[0]:b[2]]), (x, y))
                sheet["frames"][f"{mat}_{p}"] = {
                    "frame": {"x": x, "y": y, "w": w, "h": h}, "rotated": False, "trimmed": True,
                    "spriteSourceSize": {"x": b[0], "y": b[1], "w": w, "h": h},
                    "sourceSize": {"w": W, "h": H}, "anchor": {"x": 0.5, "y": 0.5}}
            img = f"{mat}{tag}.webp"
            atlas.save(os.path.join(a.dst, "fences", img), quality=92, method=6, alpha_quality=100)
            sheet["meta"] = {"app": "strelite art pipeline", "image": img, "format": "RGBA8888",
                             "size": {"w": AW, "h": AH}, "scale": "2" if tag == "@2x" else "1"}
            with open(os.path.join(a.dst, "fences", f"{mat}{tag}.json"), "w") as f:
                json.dump(sheet, f, separators=(",", ":"))
            print(f"[pack] fences {mat}{tag}: {AW}x{AH}", flush=True)
        entry[mat] = {"name": NAMES[mat], "sheet": f"fences/{mat}",
                      **{p: f"{mat}_{p}" for p in PIECES},
                      "heightM": meta["heightM"], "thicknessM": meta["thicknessM"]}
    path = os.path.join(a.dst, "towers.json")
    with open(path) as f:
        manifest = json.load(f)
    manifest.setdefault("fences", {}).update(entry)
    manifest["fencesNote"] = (
        "fences/<material>@1x|@2x.json, frames <material>_<piece>, anchor = ground point of the tile "
        "centre. Per tile draw <material>_post, then the half-segments toward each fenced neighbour: "
        "px (+x), nx (-x), py (+y), ny (-y) in grid cells. Draw order: segments behind the post "
        "(ny, nx) first, then post, then py, px; sort tiles back to front as usual.")
    with open(path, "w") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)


def review(a):
    """Assemble each material into a small wall (a straight run, a corner and a T) on the
    field ground, using the screen step from meta.json."""
    from PIL import Image
    g = Image.open(os.path.join(HERE, "..", "..", "public", "art", "ground", "field@2x.webp")).convert("RGBA")
    layout = {(0, 0): "px", (1, 0): "nx px", (2, 0): "nx py", (2, 1): "ny py nx", (2, 2): "ny",
              (1, 1): "px"}
    tiles = []
    for mat in a.materials:
        d = os.path.join(a.out, "fences", mat)
        with open(os.path.join(d, "meta.json")) as f:
            meta = json.load(f)
        sx, sy = meta["gridXStepPx"], meta["gridYStepPx"]
        W = H = 1400
        canvas = Image.new("RGBA", (W, H))
        for y in range(0, H, g.height):
            for x in range(0, W, g.width):
                canvas.paste(g, (x, y))
        im = {p: Image.open(os.path.join(d, f"{p}.png")).convert("RGBA") for p in ("post", "px", "nx", "py", "ny")}
        fw = im["post"].width
        order = sorted(layout, key=lambda t: t[0] + t[1])
        for gx, gy in order:
            cx = W / 2 - 300 + gx * sx[0] + gy * sy[0]
            cy = H / 2 - 250 + gx * sx[1] + gy * sy[1]
            parts = layout[(gx, gy)].split()
            seq = [p for p in ("ny", "nx") if p in parts] + ["post"] + [p for p in ("py", "px") if p in parts]
            for p in seq:
                canvas.alpha_composite(im[p], (int(cx - fw / 2), int(cy - fw / 2)))
        tiles.append(canvas.crop((150, 150, W - 150, H - 250)))
    w, h = tiles[0].size
    sheet = Image.new("RGB", (w * len(tiles), h))
    for i, t in enumerate(tiles):
        sheet.paste(t.convert("RGB"), (i * w, 0))
    sheet.save(a.review, quality=88)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--materials", nargs="+", default=["wood", "stone", "steel"])
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--ppm", type=float, default=64.0, help="pixels per metre of the @2x sprites")
    ap.add_argument("--out", default=os.path.join(HERE, "..", "out"))
    ap.add_argument("--dst", default=os.path.join(HERE, "..", "..", "public", "art"))
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--pack", action="store_true")
    ap.add_argument("--review", default=None)
    args = ap.parse_args()
    if not args.no_render:
        render(args)
    if args.pack:
        pack(args)
    if args.review:
        review(args)
