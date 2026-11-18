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

from PIL import Image

from pack_atlas import bbox, load_premultiplied, pack, to_image

NAMES = {
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


def pack_model(src, dst, model):
    d = os.path.join(src, "enemies", model)
    with open(os.path.join(d, "meta.json")) as f:
        meta = json.load(f)
    n = meta["dirs"]
    os.makedirs(os.path.join(dst, "enemies"), exist_ok=True)
    for tag, scale in (("@2x", 1.0), ("@1x", 0.5)):
        frames = [load_premultiplied(os.path.join(d, f"dir_{i:02d}.png"), scale) for i in range(n)]
        H, W = frames[0].shape[:2]
        boxes = [bbox(pm) for pm in frames]
        sizes = [(b[2] - b[0], b[3] - b[1]) for b in boxes]
        pos, AW, AH = pack(sizes)
        atlas = Image.new("RGBA", (AW, AH), (0, 0, 0, 0))
        sheet = {"frames": {}, "animations": {model: [f"{model}_{i:02d}" for i in range(n)]}}
        for i, (pm, b, (x, y)) in enumerate(zip(frames, boxes, pos)):
            w, h = b[2] - b[0], b[3] - b[1]
            atlas.paste(to_image(pm[b[1]:b[3], b[0]:b[2]]), (x, y))
            sheet["frames"][f"{model}_{i:02d}"] = {
                "frame": {"x": x, "y": y, "w": w, "h": h}, "rotated": False, "trimmed": True,
                "spriteSourceSize": {"x": b[0], "y": b[1], "w": w, "h": h},
                "sourceSize": {"w": W, "h": H}, "anchor": {"x": 0.5, "y": 0.5},
            }
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
        "placeholder": True,
        "sheet": f"enemies/{model}",
        "frames": model,
        "directions": n,
        "lengthM": meta["lengthM"],
        "radiusM": meta["radiusM"],
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
        enemies[GAME_ID.get(model, model)] = pack_model(a.src, a.dst, model)
    manifest["enemiesNote"] = ("enemies/<model>@1x|@2x.json: frame <model>_NN faces game angle "
                               "NN * 2*pi/directions (atan2(dy, dx) in grid cells, 0 = screen "
                               "lower-right); anchor = the unit's ground centre; shadow included")
    with open(path, "w") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
    print(f"[pack] manifest: {path}")


if __name__ == "__main__":
    main()
