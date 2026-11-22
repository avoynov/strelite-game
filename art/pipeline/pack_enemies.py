"""Pack enemy renders (render_sprites.py --enemy) into game atlases.

Input:  <src>/enemies/<model>/dir_NN.png + meta.json
Output: <dst>/enemies/<model>@2x.webp + .json and @1x (PixiJS spritesheets), and an
        "enemies" entry per model in <dst>/towers.json.
Frame names: <model>_NN; the animation <model> lists them in heading order.

Usage: python3 pack_enemies.py --models tank truck infantry
"""
import argparse
import json
import os

import numpy as np
from PIL import Image

from pack_atlas import bbox, load_premultiplied, pack, to_image

NAMES = {
    "raiders": {"bg": "Разузнавачи", "en": "Raiders"},
    "infantry": {"bg": "Пехота", "en": "Infantry"},
    "truck": {"bg": "Камион", "en": "Truck"},
    "tank": {"bg": "Танк", "en": "Tank"},
    "bikers": {"bg": "Мотоциклисти", "en": "Motorcycle raiders"},
    "drone": {"bg": "Дрон", "en": "Drone"},
    "airship": {"bg": "Дирижабъл", "en": "Armoured airship"},
    "apc": {"bg": "БТР", "en": "Armoured personnel carrier"},
    "fortress": {"bg": "Крепост", "en": "Land fortress"},
}


# Model name -> the game's enemy id (src/sim/content.ts): the bikers are "moto", and the
# armoured airship is the game's air unit "drone" (it replaced the drone model).
GAME_ID = {"bikers": "moto", "airship": "drone"}
ALLIES = {"raiders"}        # the player's own units: manifest "allies", not "enemies"
HAZE = 12 / 255   # alpha under this is shadow-catcher haze: dropped
SOLID = 32 / 255  # the trim box is set by alpha at or over this ...
MARGIN = 8        # ... grown by this many pixels at @2x for the soft shadow edge


def trim_haze(pm, margin):
    """Drop the haze, and everything outside the unit and its shadow (the box of alpha at or
    over SOLID, grown by margin), so frames trim tight even where noise in the haze passes HAZE."""
    a = pm[..., 3]
    ys, xs = np.where(a >= SOLID)
    keep = np.zeros(a.shape, bool)
    if len(xs):
        keep[max(0, ys.min() - margin):ys.max() + 1 + margin, max(0, xs.min() - margin):xs.max() + 1 + margin] = True
    pm[~keep | (a < HAZE)] = 0


def pack_model(src, dst, model):
    d = os.path.join(src, "enemies", model)
    with open(os.path.join(d, "meta.json")) as f:
        meta = json.load(f)
    n = meta["dirs"]
    mv = meta.get("move")
    nf = mv["frames"] if mv else 0
    # (frame name, file) in heading order; with movement, NN_FF for every frame
    items = ([(f"{model}_{i:02d}_{f:02d}", f"dir_{i:02d}_{f:02d}.png") for i in range(n) for f in range(nf)] if mv
             else [(f"{model}_{i:02d}", f"dir_{i:02d}.png") for i in range(n)])
    os.makedirs(os.path.join(dst, "enemies"), exist_ok=True)
    for tag, scale in (("@2x", 1.0), ("@1x", 0.5)):
        frames = [load_premultiplied(os.path.join(d, fn), scale) for _, fn in items]
        for pm in frames:  # the shadow catcher leaves a faint, noisy haze over the whole frame
            trim_haze(pm, max(1, round(MARGIN * scale)))
        H, W = frames[0].shape[:2]
        boxes = [bbox(pm) for pm in frames]
        sizes = [(b[2] - b[0], b[3] - b[1]) for b in boxes]
        pos, AW, AH = pack(sizes)
        atlas = Image.new("RGBA", (AW, AH), (0, 0, 0, 0))
        sheet = {"frames": {}, "animations": {model: [f"{model}_{i:02d}" for i in range(n)]}}
        for (name, _), pm, b, (x, y) in zip(items, frames, boxes, pos):
            w, h = b[2] - b[0], b[3] - b[1]
            atlas.paste(to_image(pm[b[1]:b[3], b[0]:b[2]]), (x, y))
            entry = {
                "frame": {"x": x, "y": y, "w": w, "h": h}, "rotated": False, "trimmed": True,
                "spriteSourceSize": {"x": b[0], "y": b[1], "w": w, "h": h},
                "sourceSize": {"w": W, "h": H}, "anchor": {"x": 0.5, "y": 0.5},
            }
            sheet["frames"][name] = entry
            if mv and name.endswith("_00"):              # the still per heading stays: <model>_NN
                sheet["frames"][name[:-3]] = dict(entry)
        if mv:
            for i in range(n):
                sheet["animations"][f"{model}_{i:02d}_move"] = [f"{model}_{i:02d}_{f:02d}" for f in range(nf)]
        image_name = f"{model}{tag}.webp"
        atlas.save(os.path.join(dst, "enemies", image_name), quality=92, method=6, alpha_quality=100)
        sheet["meta"] = {"app": "strelite art pipeline", "image": image_name, "format": "RGBA8888",
                         "size": {"w": AW, "h": AH}, "scale": "2" if tag == "@2x" else "1"}
        with open(os.path.join(dst, "enemies", f"{model}{tag}.json"), "w") as f:
            json.dump(sheet, f, separators=(",", ":"))
        kb = os.path.getsize(os.path.join(dst, "enemies", image_name)) / 1024
        print(f"[pack] {model}{tag}: atlas {AW}x{AH}, {kb:.0f} kB, {AW * AH * 4 / 2**20:.1f} MB GPU", flush=True)
    return {
        "name": NAMES.get(model, {"bg": model, "en": model}),
        "placeholder": False,
        "sheet": f"enemies/{model}",
        "frames": model,
        "directions": n,
        "lengthM": meta["lengthM"],
        "radiusM": meta["radiusM"],
        **({"move": {"frames": nf, "kind": mv["kind"], "cycleM": mv.get("cycleM"), "fps": mv.get("fps"),
                     "names": f"{model}_DD_FF", "animation": f"{model}_DD_move"}} if mv else {}),
        **({"flying": True, "flightHeightM": meta.get("flightHeightM"),
            "shadow": "no shadow in the sprite: draw a dark ellipse on the ground below it"}
           if meta.get("flying") else {}),
    }


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(here, "..", "out"))
    ap.add_argument("--dst", default=os.path.join(here, "..", "..", "public", "art"))
    ap.add_argument("--models", nargs="+", default=["infantry", "truck", "tank"])
    a = ap.parse_args()
    path = os.path.join(a.dst, "towers.json")
    with open(path) as f:
        manifest = json.load(f)
    enemies = manifest.setdefault("enemies", {})
    for model in a.models:
        if model in ALLIES:
            manifest.setdefault("allies", {})[model] = pack_model(a.src, a.dst, model)
            manifest["alliesNote"] = ("allies/<id>: the player's own units (raiders = the party that rides out "
                                      "to provoke the enemy). Same sheet layout, headings and movement as enemies.")
            continue
        enemies[GAME_ID.get(model, model)] = pack_model(a.src, a.dst, model)
    manifest["enemiesNote"] = ("enemies/<model>@1x|@2x.json: frame <model>_NN faces game angle "
                               "NN * 2*pi/directions (atan2(dy, dx) in grid cells, 0 = screen "
                               "lower-right); anchor = the unit's ground centre; shadow included. "
                               "With a 'move' entry, <model>_NN_FF are its movement frames (animation "
                               "<model>_NN_move); <model>_NN stays the still (= frame 00). Distance-driven "
                               "(cycleM set): frame = floor((distance / cycleM + phase) * frames) mod frames, "
                               "phase a random 0..1 per unit; time-driven (fps set): frame = floor(t * fps + "
                               "phase * frames) mod frames.")
    with open(path, "w") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
    print(f"[pack] manifest: {path}")


if __name__ == "__main__":
    main()
