"""Render and pack the wreck of every gun level (damage.py "wreck" state): one static
frame per level, the tower's own framing and anchor, the turret knocked askew and the
gun cut down to a ragged stump with its parts lying around it, on its soil patch.
The game draws the wreck alone (no base, no aim frame) where a gun was destroyed.

  python3 render_wrecks.py --models ballista zis3 --levels 1 2 3 4 5 --samples 32
  python3 render_wrecks.py --models ballista zis3 --pack       # towers/<id>_wreck@1x|@2x + towers.json
  python3 render_wrecks.py --models zis3 --review out.jpg

Writes <out>/wrecks/<model>/L<n>.png + meta.json.
"""
import argparse
import importlib
import json
import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
GUNS = ["ballista", "scorpion", "zis3", "howitzer", "greekfire", "trebuchet", "railgun"]


def render(a):
    import bpy  # noqa: F401

    from strelite_art import damage, materials, materials_photoreal, scene as stage
    from strelite_art.terrain import Patch

    for name in a.models:
        model = importlib.import_module(f"strelite_art.models.{name}")
        out_dir = os.path.join(a.out, "wrecks", name)
        os.makedirs(out_dir, exist_ok=True)
        wh = getattr(model, "SPRITE_WH_M", None)
        frame_m = wh[0] if wh else model.SPRITE_FRAME_M
        size = int(round(frame_m * a.ppm / 2)) * 2
        size_y = int(round(wh[1] * a.ppm / 2)) * 2 if wh else size
        anchor_from_bottom = model.ANCHOR_FROM_BOTTOM_M if wh else frame_m / 2
        for level in a.levels:
            path = os.path.join(out_dir, f"L{level}.png")
            if a.resume and os.path.exists(path):
                continue
            materials.clear_cache()
            patch = model.ground(level)
            scene = stage.build_stage("photoreal", size, a.samples, frame_m=frame_m * (1.6 if wh else 1.0),
                                      ground="patch", target_z=0.0, projection="ortho",
                                      catcher_hole=patch.r_solid - Patch.CATCHER_INSET)
            if wh:
                cam = scene.camera
                cam.data.sensor_fit = "HORIZONTAL"
                cam.data.ortho_scale = frame_m
                scene.render.resolution_y = size_y
                up = cam.rotation_euler.to_matrix().col[1].normalized()
                cam.location = cam.location + up * (wh[1] / 2 - model.ANCHOR_FROM_BOTTOM_M)
            scene.render.film_transparent = True
            scene.cycles.seed = 1
            seed = 2000 + 17 * level + sum(map(ord, name))
            rnd = random.Random(seed)
            _, turret = model.build("photoreal", level)
            yaw = math.radians(rnd.choice([200, 230, 250, 290, 320]))
            damage.apply(scene, "wreck", seed=seed, footprint=model.FOOTPRINT_M,
                         tilt=(turret, (rnd.uniform(-0.22, -0.12), rnd.uniform(-0.15, 0.15), yaw)),
                         heap_scale=0.6)
            materials_photoreal.stamp(scene)
            patch.build(scene)
            scene.render.filepath = path
            t = time.time()
            bpy.ops.render.render(write_still=True)
            print(f"[render] wreck {name} L{level}: {time.time() - t:.1f}s", flush=True)
        meta = {"model": name, "pxPerMetre": a.ppm, "frame": [size, size_y],
                "anchorPx": [size / 2, size_y - anchor_from_bottom * a.ppm], "levels": sorted(a.levels)}
        with open(os.path.join(out_dir, "meta.json"), "w") as f:
            json.dump(meta, f, indent=1)


def pack(a):
    from PIL import Image

    from pack_atlas import GAME_ID, bbox, load_premultiplied, pack as pack_rects, to_image

    os.makedirs(os.path.join(a.dst, "towers"), exist_ok=True)
    path = os.path.join(a.dst, "towers.json")
    with open(path) as f:
        manifest = json.load(f)
    for name in a.models:
        gid = GAME_ID.get(name, name)
        d = os.path.join(a.out, "wrecks", name)
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
                sheet["frames"][f"{gid}_L{lv}_wreck"] = {
                    "frame": {"x": x, "y": y, "w": w, "h": h}, "rotated": False, "trimmed": True,
                    "spriteSourceSize": {"x": b[0], "y": b[1], "w": w, "h": h},
                    "sourceSize": {"w": W, "h": H}, "anchor": {"x": 0.5, "y": round(ay, 5)}}
            img = f"{gid}_wreck{tag}.webp"
            atlas.save(os.path.join(a.dst, "towers", img), quality=92, method=6, alpha_quality=100)
            sheet["meta"] = {"app": "strelite art pipeline", "image": img, "format": "RGBA8888",
                             "size": {"w": AW, "h": AH}, "scale": "2" if tag == "@2x" else "1"}
            with open(os.path.join(a.dst, "towers", f"{gid}_wreck{tag}.json"), "w") as f:
                json.dump(sheet, f, separators=(",", ":"))
            print(f"[pack] wreck {gid}{tag}: {AW}x{AH}", flush=True)
        tower = manifest.get("towers", {}).get(gid)
        if tower is None:
            print(f"[pack] towers.{gid} missing in the manifest; skipped", flush=True)
            continue
        for entry in tower.get("levels", []):
            if entry.get("level") in levels:
                entry.setdefault("states", {})["wreck"] = {"sheet": f"towers/{gid}_wreck",
                                                           "frame": f"{gid}_L{entry['level']}_wreck"}
    manifest["wreckNote"] = (
        "towers.<id>.levels[].states.wreck = {sheet, frame}: the destroyed gun, one static frame per level, "
        "drawn alone instead of base + aim, same anchor as the base frame. Damaged guns (below half health) "
        "keep their normal frames with the looping effects fire_small and smoke_plume on top.")
    with open(path, "w") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
        f.write("\n")


def review(a):
    from PIL import Image, ImageDraw
    field = Image.open(os.path.join(HERE, "..", "..", "public", "art", "ground", "field@2x.webp")).convert("RGBA")
    tiles = []
    for name in a.models:
        d = os.path.join(a.out, "wrecks", name)
        with open(os.path.join(d, "meta.json")) as f:
            meta = json.load(f)
        for lv in meta["levels"]:
            tiles.append((f"{name} L{lv}", Image.open(os.path.join(d, f"L{lv}.png")).convert("RGBA"),
                          meta["pxPerMetre"]))
    cell = max(max(im.size) for _, im, _ in tiles)
    cols = min(5, len(tiles))
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGBA", (cell * cols, cell * rows))
    s = tiles[0][2] / 32.0
    g = field.resize((int(field.width * s), int(field.height * s)))
    for y in range(0, sheet.height, g.height):
        for x in range(0, sheet.width, g.width):
            sheet.paste(g, (x, y))
    dr = ImageDraw.Draw(sheet)
    for i, (label, im, _) in enumerate(tiles):
        x, y = (i % cols) * cell, (i // cols) * cell
        sheet.alpha_composite(im, (x + (cell - im.width) // 2, y + (cell - im.height) // 2))
        dr.text((x + 8, y + 8), label, fill=(255, 255, 255, 255))
    sheet.convert("RGB").save(a.review, quality=88)
    print("[review]", a.review)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=GUNS)
    ap.add_argument("--levels", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--ppm", type=float, default=32.0)
    ap.add_argument("--resume", action="store_true")
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
