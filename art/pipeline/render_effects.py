"""Fire effects for style В as short sprite sequences (numpy + PIL, no Blender):

  muzzle_flash  4 frames, flame cone along +x (rotate the sprite to the barrel's screen
                direction), anchor at the muzzle; draw with additive blending
  muzzle_smoke  12 frames, a puff that grows and drifts up while it fades; normal blending
  shell_burst   16 frames, flash, fireball, dark smoke and a dust ring with flying earth;
                anchor at the impact point on the ground; normal blending

Sizes are real metres at the game's pixels per metre (32 at @2x, 16 at @1x), seen through
the game camera (the ground squashed to half height). Light comes from the lower left like
the towers. Writes <dst>/effects/<name>@1x|@2x.json+.webp and an "effects" manifest entry.

Usage: python3 render_effects.py
"""
import argparse
import json
import math
import os

import numpy as np
from PIL import Image

from pack_atlas import bbox, pack, to_image

PPM = 32.0
FPS = 24


def fbm(shape, rng, octaves=5, base=4):
    """Tileable-enough value noise in [-1, 1]."""
    h, w = shape
    out = np.zeros(shape, np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        n = base * 2 ** o
        g = rng.standard_normal((n + 1, n + 1)).astype(np.float32)
        img = Image.fromarray(g, "F").resize((w, h), Image.BICUBIC)
        out += amp * np.asarray(img)
        tot += amp
        amp *= 0.55
    return out / tot


def grid(size, cx, cy):
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    return (x - cx) / PPM, (y - cy) / PPM            # metres on screen


def premul(rgb, a):
    a = np.clip(a, 0, 1)[..., None]
    return np.concatenate([np.clip(rgb, 0, 1) * a, a], axis=-1)


def over(top, bottom):
    return top + bottom * (1 - top[..., 3:4])


def flash_frames(rng, n=4, size=96):
    frames = []
    for i in range(n):
        X, Y = grid(size, size * 0.25, size / 2)
        noise = fbm((size, size), rng, 4, 3)
        L = 2.2 * (1 - i / n * 0.5)                 # flame length, m
        r = np.hypot(X / L, Y / (0.35 + 0.35 * np.clip(X, 0, None) / L))
        cone = np.clip(1 - r + noise * 0.35, 0, 1) * (X > -0.15)
        core = np.exp(-(X ** 2 + Y ** 2) / 0.06)
        star = np.zeros_like(X)
        for a in (0.9, -0.9, 0.45, -0.45):          # side jets of the muzzle brake
            d = np.abs(np.sin(np.arctan2(Y, X + 1e-6) - a)) * np.hypot(X, Y)
            star += np.exp(-d ** 2 / 0.004) * np.exp(-np.hypot(X, Y) / 0.35)
        inten = np.clip(cone ** 1.5 + core + star * 0.6, 0, 1.5) * (1 - i / (n + 1))
        hot = np.clip(inten, 0, 1)
        rgb = np.stack([np.ones_like(hot), 0.55 + 0.42 * hot, 0.15 + 0.7 * hot ** 2], -1)
        frames.append(premul(rgb, hot))
    return frames


def smoke_frames(rng, n=12, size=160):
    frames = []
    base = fbm((size, size), rng, 5, 3)
    for i in range(n):
        t = i / (n - 1)
        X, Y = grid(size, size / 2, size * 0.62 - t * 0.9 * PPM)
        R = 0.45 + 1.5 * t ** 0.6
        drift = np.roll(base, int(t * 9), axis=0)
        d = np.hypot(X, Y * 1.15) / R + drift * 0.45
        dens = np.clip((1 - d) * 1.8, 0, 1) * (1 - t) ** 1.2 * 0.9
        lit = np.clip(0.5 - (X - Y) * 0.25 / R + drift * 0.2, 0, 1)     # lit from the lower left
        g = 0.36 + 0.3 * lit
        rgb = np.stack([g * 1.02, g, g * 0.94], -1)
        frames.append(premul(rgb, dens))
    return frames


def burst_frames(rng, n=16, size=352):
    frames = []
    cx, cy = size / 2, size * 0.76
    n1, n2 = fbm((size, size), rng, 5, 3), fbm((size, size), rng, 5, 4)
    debris = [(rng.uniform(-1, 1) * 2.4, rng.uniform(1.5, 5.0), rng.uniform(0.04, 0.09)) for _ in range(26)]
    for i in range(n):
        t = i / (n - 1)
        X, Y = grid(size, cx, cy)
        img = np.zeros((size, size, 4), np.float32)
        # dust ring along the ground (an ellipse: the ground is squashed by the camera)
        Rg = 0.6 + 2.6 * t ** 0.5
        dg = np.hypot(X, Y * 2.0) / Rg + n2 * 0.35
        dust = np.clip((1 - dg) * 2.0, 0, 1) * np.clip(1.3 - t * 1.25, 0, 1) * 0.9
        img = over(premul(np.stack([0.62 + 0 * X, 0.54 + 0 * X, 0.42 + 0 * X], -1), dust), img)
        # rising column of smoke and earth
        H = 0.6 + 3.2 * t ** 0.55
        Rc = 0.7 + 1.5 * t ** 0.6
        Yc = Y + H * 0.55
        dc = np.hypot(X / Rc, Yc / (H * 0.6)) + n1 * 0.4
        col = np.clip((1 - dc) * 2.2, 0, 1) * np.clip(1.25 - t, 0, 1) ** 0.8
        lit = np.clip(0.45 - (X - Yc) * 0.2 / Rc + n1 * 0.25, 0, 1)
        g = 0.16 + 0.32 * lit
        img = over(premul(np.stack([g * 1.08, g, g * 0.88], -1), col), img)
        # flying clods
        for (vx, vy, r) in debris:
            px, py = vx * t * 1.6, -(vy * t - 4.9 * t * t) * 1.0
            if py > 0.05:
                continue
            m = np.exp(-((X - px) ** 2 + (Y - py) ** 2) / (r * r)) * np.clip(1.2 - t, 0, 1)
            img = over(premul(np.stack([0.2 + 0 * X, 0.16 + 0 * X, 0.12 + 0 * X], -1), m), img)
        # fireball, only in the first frames
        if t < 0.35:
            k = 1 - t / 0.35
            Rf = 0.7 + 1.4 * t / 0.35
            df = np.hypot(X, (Y + 0.7 * Rf) * 1.1) / Rf + n2 * 0.3
            fire = np.clip((1 - df) * 2.0, 0, 1) * k
            hot = np.clip(fire * 1.4, 0, 1)
            rgb = np.stack([np.ones_like(hot), 0.45 + 0.5 * hot, 0.1 + 0.6 * hot ** 2], -1)
            img = over(premul(rgb, fire), img)
        frames.append(np.nan_to_num(img))
    return frames


def write(dst, name, frames, anchor, blend):
    os.makedirs(os.path.join(dst, "effects"), exist_ok=True)
    for tag, scale in (("@2x", 1.0), ("@1x", 0.5)):
        fr = []
        for pm in frames:
            if scale != 1.0:
                h, w = pm.shape[:2]
                size = (int(w * scale), int(h * scale))
                chans = [np.asarray(Image.fromarray(pm[..., c], "F").resize(size, Image.LANCZOS)) for c in range(4)]
                pm = np.clip(np.nan_to_num(np.stack(chans, -1)), 0, 1)
                pm[..., :3] = np.minimum(pm[..., :3], pm[..., 3:4])
            fr.append(pm)
        H, W = fr[0].shape[:2]
        boxes = [bbox(pm) for pm in fr]
        sizes = [(b[2] - b[0], b[3] - b[1]) for b in boxes]
        pos, AW, AH = pack(sizes)
        atlas = Image.new("RGBA", (AW, AH), (0, 0, 0, 0))
        sheet = {"frames": {}, "animations": {name: [f"{name}_{i:02d}" for i in range(len(fr))]}}
        for i, (pm, b, (x, y)) in enumerate(zip(fr, boxes, pos)):
            w, h = b[2] - b[0], b[3] - b[1]
            atlas.paste(to_image(pm[b[1]:b[3], b[0]:b[2]]), (x, y))
            sheet["frames"][f"{name}_{i:02d}"] = {
                "frame": {"x": x, "y": y, "w": w, "h": h}, "rotated": False, "trimmed": True,
                "spriteSourceSize": {"x": b[0], "y": b[1], "w": w, "h": h},
                "sourceSize": {"w": W, "h": H}, "anchor": {"x": anchor[0], "y": anchor[1]},
            }
        img = f"{name}{tag}.webp"
        atlas.save(os.path.join(dst, "effects", img), quality=90, method=6, alpha_quality=100)
        sheet["meta"] = {"app": "strelite art pipeline", "image": img, "format": "RGBA8888",
                         "size": {"w": AW, "h": AH}, "scale": "2" if tag == "@2x" else "1"}
        with open(os.path.join(dst, "effects", f"{name}{tag}.json"), "w") as f:
            json.dump(sheet, f, separators=(",", ":"))
        print(f"[fx] {name}{tag}: {len(fr)} frames, atlas {AW}x{AH}, "
              f"{os.path.getsize(os.path.join(dst, 'effects', img)) / 1024:.0f} kB")
    return {"sheet": f"effects/{name}", "frames": name, "count": len(frames), "fps": FPS,
            "anchor": list(anchor), "blend": blend}


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--dst", default=os.path.join(here, "..", "..", "public", "art"))
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    fx = {
        "muzzle_flash": write(a.dst, "muzzle_flash", flash_frames(rng), (0.25, 0.5), "add"),
        "muzzle_smoke": write(a.dst, "muzzle_smoke", smoke_frames(rng), (0.5, 0.62), "normal"),
        "shell_burst": write(a.dst, "shell_burst", burst_frames(rng), (0.5, 0.76), "normal"),
    }
    fx["muzzle_flash"]["note"] = "flame points along +x: rotate the sprite to the barrel's screen angle"
    path = os.path.join(a.dst, "towers.json")
    with open(path) as f:
        manifest = json.load(f)
    manifest["effects"] = fx
    with open(path, "w") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
    print(f"[fx] manifest: {path}")


if __name__ == "__main__":
    main()
