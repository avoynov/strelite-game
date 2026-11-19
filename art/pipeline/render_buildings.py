"""Render and pack the base's buildings (models/hq.py, models/lab.py): one static frame
per level, the game's camera, ground point of the building's centre at the anchor,
on its own soil patch, shadow kept in alpha.

  python3 render_buildings.py --models hq lab --levels 1 2 3 4 5 --samples 32
  python3 render_buildings.py --models hq --pack          # atlases + towers.json "buildings"
  python3 render_buildings.py --models hq --review out.jpg  # level sheet on the field ground

Writes <out>/buildings/<model>/L<n>.png + meta.json, then
<dst>/buildings/<model>@1x|@2x (.webp + PixiJS .json, frames <model>_L<n>).
"""
import argparse
import importlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))


def render(a):
    import bpy

    from strelite_art import materials, materials_photoreal, scene as stage
    from strelite_art.terrain import Patch

    for name in a.models:
        model = importlib.import_module(f"strelite_art.models.{name}")
        out_dir = os.path.join(a.out, "buildings", name)
        os.makedirs(out_dir, exist_ok=True)
        w_m, h_m = model.SPRITE_WH_M
        size_x = int(round(w_m * a.ppm / 2)) * 2
        size_y = int(round(h_m * a.ppm / 2)) * 2
        for level, state in [(lv, st) for st in a.states for lv in a.levels]:
            if state == "occupied" and name != "hq":
                continue
            path = os.path.join(out_dir, f"L{level}.png" if state == "normal" else f"L{level}_{state}.png")
            if a.resume and os.path.exists(path):
                continue
            materials.clear_cache()
            patch = model.ground(level)
            scene = stage.build_stage("photoreal", size_x, a.samples, frame_m=w_m * 1.6, ground="patch",
                                      target_z=0.0, projection="ortho",
                                      catcher_hole=patch.r_solid - Patch.CATCHER_INSET)
            cam = scene.camera
            cam.data.sensor_fit = "HORIZONTAL"
            cam.data.ortho_scale = w_m
            scene.render.resolution_y = size_y
            up = cam.rotation_euler.to_matrix().col[1].normalized()
            cam.location = cam.location + up * (h_m / 2 - model.ANCHOR_FROM_BOTTOM_M)
            scene.render.film_transparent = True
            scene.cycles.seed = 1
            model.build("photoreal", level)
            if state != "normal":
                from strelite_art import damage
                seed = 1000 * level + sum(map(ord, name))
                if state == "occupied":
                    damage.occupy(scene, seed=seed)
                damage.apply(scene, "damaged" if state == "occupied" else state, seed=seed,
                             footprint=model.FOOTPRINT_M)
            materials_photoreal.stamp(scene)
            patch.build(scene)
            scene.render.filepath = path
            t = time.time()
            bpy.ops.render.render(write_still=True)
            print(f"[render] building {name} L{level} {state}: {time.time() - t:.1f}s", flush=True)
        anchor_y = size_y - model.ANCHOR_FROM_BOTTOM_M * a.ppm
        meta = {"model": name, "pxPerMetre": a.ppm, "frame": [size_x, size_y], "anchorPx": [size_x / 2, anchor_y],
                "tiles": model.TILES, "footprintM": model.FOOTPRINT_M, "levels": sorted(a.levels),
                "name": model.NAMES,
                "states": sorted({st for st in a.states if st != "normal"} - ({"occupied"} if name != "hq" else set()))}
        with open(os.path.join(out_dir, "meta.json"), "w") as f:
            json.dump(meta, f, indent=1)


def pack(a):
    from PIL import Image

    from pack_atlas import bbox, load_premultiplied, pack as pack_rects, to_image

    os.makedirs(os.path.join(a.dst, "buildings"), exist_ok=True)
    entry = {}
    for name in a.models:
        d = os.path.join(a.out, "buildings", name)
        with open(os.path.join(d, "meta.json")) as f:
            meta = json.load(f)
        levels = meta["levels"]
        for tag, ppm_out in (("@2x", 32.0), ("@1x", 16.0)):
            scale = ppm_out / meta["pxPerMetre"]
            frames = [load_premultiplied(os.path.join(d, f"L{lv}.png"), scale) for lv in levels]
            H, W = frames[0].shape[:2]
            boxes = [bbox(pm) for pm in frames]
            pos, AW, AH = pack_rects([(b[2] - b[0], b[3] - b[1]) for b in boxes])
            atlas = Image.new("RGBA", (AW, AH), (0, 0, 0, 0))
            ay = meta["anchorPx"][1] / meta["frame"][1]
            sheet = {"frames": {}}
            for lv, pm, b, (x, y) in zip(levels, frames, boxes, pos):
                w, h = b[2] - b[0], b[3] - b[1]
                atlas.paste(to_image(pm[b[1]:b[3], b[0]:b[2]]), (x, y))
                sheet["frames"][f"{name}_L{lv}"] = {
                    "frame": {"x": x, "y": y, "w": w, "h": h}, "rotated": False, "trimmed": True,
                    "spriteSourceSize": {"x": b[0], "y": b[1], "w": w, "h": h},
                    "sourceSize": {"w": W, "h": H}, "anchor": {"x": 0.5, "y": round(ay, 5)}}
            img = f"{name}{tag}.webp"
            atlas.save(os.path.join(a.dst, "buildings", img), quality=92, method=6, alpha_quality=100)
            sheet["meta"] = {"app": "strelite art pipeline", "image": img, "format": "RGBA8888",
                             "size": {"w": AW, "h": AH}, "scale": "2" if tag == "@2x" else "1"}
            with open(os.path.join(a.dst, "buildings", f"{name}{tag}.json"), "w") as f:
                json.dump(sheet, f, separators=(",", ":"))
            print(f"[pack] buildings {name}{tag}: {AW}x{AH}", flush=True)
        entry[name] = {"name": meta["name"], "sheet": f"buildings/{name}",
                       "levels": [f"{name}_L{lv}" for lv in levels], "tiles": meta["tiles"],
                       "footprintM": meta["footprintM"],
                       "frameM": [round(meta["frame"][0] / meta["pxPerMetre"], 3),
                                  round(meta["frame"][1] / meta["pxPerMetre"], 3)]}
    path = os.path.join(a.dst, "towers.json")
    with open(path) as f:
        manifest = json.load(f)
    manifest.setdefault("buildings", {}).update(entry)
    manifest["buildingsNote"] = (
        "buildings/<id>@1x|@2x.json, frame <id>_L<n> for level n (1-based; the game's level index 0 = L1). "
        "Anchor = ground point of the building's centre (the middle of its 2x2 tiles); the frame is taller "
        "than wide, so anchor.y is below the middle. One static frame per level; draw in the normal depth "
        "sort with the guns.")
    with open(path, "w") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
        f.write("\n")


def review(a):
    from PIL import Image, ImageDraw
    field = Image.open(os.path.join(HERE, "..", "..", "public", "art", "ground", "field@2x.webp")).convert("RGBA")
    for name in a.models:
        d = os.path.join(a.out, "buildings", name)
        with open(os.path.join(d, "meta.json")) as f:
            meta = json.load(f)
        s = meta["pxPerMetre"] / 32.0
        g = field.resize((int(field.width * s), int(field.height * s)))
        imgs = [Image.open(os.path.join(d, f"L{lv}.png")).convert("RGBA") for lv in meta["levels"]]
        W, H = imgs[0].size
        sheet = Image.new("RGBA", (W * len(imgs), H))
        for y in range(0, H, g.height):
            for x in range(0, sheet.width, g.width):
                sheet.paste(g, (x, y))
        dr = ImageDraw.Draw(sheet)
        for i, (lv, im) in enumerate(zip(meta["levels"], imgs)):
            sheet.alpha_composite(im, (i * W, 0))
            dr.text((i * W + 12, 10), f"L{lv}", fill=(255, 255, 255, 255))
        out = a.review if len(a.models) == 1 else a.review.replace(".jpg", f"_{name}.jpg")
        sheet.convert("RGB").save(out, quality=88)
        print("[review]", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["hq", "lab"])
    ap.add_argument("--levels", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--ppm", type=float, default=32.0)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--states", nargs="+", default=["normal"], help="normal damaged rubble occupied (hq only)")
    ap.add_argument("--out", default=os.path.join(HERE, "..", "out"))
    ap.add_argument("--dst", default=os.path.join(HERE, "..", "..", "public", "art"))
    ap.add_argument("--pack", action="store_true")
    ap.add_argument("--review")
    a = ap.parse_args()
    if a.review:
        review(a)
    elif a.pack:
        pack(a)
    else:
        render(a)
