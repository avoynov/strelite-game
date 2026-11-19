"""Pack the clean gun portraits (render_portraits.py) into one WebP atlas per gun level
plus public/art/portraits.json.

Every frame of a level is cropped to the same box (the union of all headings, faint
shadow-catcher noise dropped), so the ground point sits at the same `anchor` in every
cell and the gun turns in place. Cells are laid out left to right, `cols` per row.
"""
import argparse
import json
import os
import re

from PIL import Image

from pack_atlas import GAME_ID   # model file name -> the game's tower id (ballista -> crossbow)

ALPHA_MIN = 10   # below this the catcher's noise, not the gun or its shadow


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="<out>/portraits")
    ap.add_argument("--dst", required=True, help="public/art")
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--quality", type=int, default=84)
    ap.add_argument("--ppm", type=float, default=44.0)
    a = ap.parse_args()
    os.makedirs(os.path.join(a.dst, "portraits"), exist_ok=True)
    guns, dirs = {}, None
    for model in sorted(os.listdir(a.src)):
        gid = GAME_ID.get(model, model)
        levels = []
        for lv_dir in sorted(os.listdir(os.path.join(a.src, model))):
            m = re.fullmatch(r"L(\d+)", lv_dir)
            if not m:
                continue
            folder = os.path.join(a.src, model, lv_dir)
            files = sorted(f for f in os.listdir(folder) if re.fullmatch(r"aim_\d\d\.png", f))
            if not files:
                continue
            if dirs is None:
                dirs = len(files)
            assert len(files) == dirs, f"{folder}: {len(files)} frames, expected {dirs}"
            frames = []
            for f in files:
                im = Image.open(os.path.join(folder, f)).convert("RGBA")
                alpha = im.getchannel("A").point(lambda v: 255 if v >= ALPHA_MIN else 0)
                r, g, b, al = im.split()
                im = Image.merge("RGBA", (r, g, b, Image.composite(al, alpha, alpha)))
                frames.append(im)
            box = None
            for im in frames:
                bb = im.getchannel("A").getbbox()
                if bb:
                    box = bb if box is None else (min(box[0], bb[0]), min(box[1], bb[1]), max(box[2], bb[2]), max(box[3], bb[3]))
            x0, y0, x1, y1 = box
            pad = 2
            x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
            x1, y1 = min(frames[0].width, x1 + pad), min(frames[0].height, y1 + pad)
            cw, ch = x1 - x0, y1 - y0
            rows = -(-dirs // a.cols)
            sheet = Image.new("RGBA", (cw * a.cols, ch * rows), (0, 0, 0, 0))
            for i, im in enumerate(frames):
                sheet.paste(im.crop((x0, y0, x1, y1)), ((i % a.cols) * cw, (i // a.cols) * ch))
            name = f"portraits/{gid}_{lv_dir}.webp"
            sheet.save(os.path.join(a.dst, name), "WEBP", quality=a.quality, method=6)
            levels.append({"level": int(m.group(1)), "image": name, "cell": [cw, ch], "cols": a.cols,
                           "size": list(sheet.size),
                           "anchor": [frames[0].width / 2 - x0, frames[0].height / 2 - y0]})
            print(f"[pack] {name}: cell {cw}x{ch}, {os.path.getsize(os.path.join(a.dst, name)) // 1024} KB")
        if levels:
            guns[gid] = {"levels": levels}
    # keep what is already packed (other guns, other levels); new levels replace old ones
    path = os.path.join(a.dst, "portraits.json")
    if os.path.exists(path):
        with open(path) as f:
            old = json.load(f)
        if old.get("directions") == dirs and old.get("pxPerMetre") == a.ppm:
            for gid, g in old.get("guns", {}).items():
                by = {lv["level"]: lv for lv in g["levels"]}
                by.update({lv["level"]: lv for lv in guns.get(gid, {}).get("levels", [])})
                guns[gid] = {"levels": [by[k] for k in sorted(by)]}
    manifest = {
        "version": 1,
        "about": "Clean gun portraits for menus: gun only, transparent, no ground and no cast shadow. Cell i aims at game angle i * 2*pi/directions (same convention as towers.json). Made by art/pipeline/render_portraits.sh.",
        "directions": dirs, "pxPerMetre": a.ppm, "guns": guns,
    }
    with open(path, "w") as f:
        json.dump(manifest, f, indent=1)


if __name__ == "__main__":
    main()
