"""Turn layered tower renders into game-ready sprite atlases (PIL + numpy only).

Input  (from `render_sprites.py --ground patch`), per model and level:
    <src>/<model>/photoreal/L<level>/base.png      everything that never moves
    <src>/<model>/photoreal/L<level>/aim_NN.png    the complete tower aiming at direction NN
    <src>/<model>/photoreal/L<level>/meta.json
Output, per model and level, at two resolutions (@2x as rendered, @1x half size):
    <dst>/towers/<model>_L<level>@2x.webp + .json   PixiJS / TexturePacker spritesheet
    <dst>/towers/<model>_L<level>@1x.webp + .json
and one manifest for the game:
    <dst>/towers.json

How the layers work. The game draws two sprites at the tower's ground point:
`<model>_L<n>_base`, then `<model>_L<n>_aim_NN` on top with normal alpha blending.
An aim frame is not "the gun cut out". It is the exact difference between the
complete render and the base: wherever the gun, its shadow or its bounce light
changes a pixel, the frame holds the pixel that reproduces the complete render
when laid over the base. So shadows on sandbags, walls hiding the trails and
contact shadows are all correct, while the 32 frames stay small (only the part
of the picture that the gun changes is stored).

Usage:
    python3 pack_atlas.py --src ../out --dst ../../public/art --models howitzer zis3
"""
import argparse
import json
import math
import os

import numpy as np
from PIL import Image, ImageFilter

PAD = 2                       # transparent pixels around each packed frame
SHADOW_TINT = (0.0, 8 / 255, 17 / 255)   # catcher shadows are slightly blue, like the sky-lit
#                                          shadows on the soil patch (measured on the renders)
TAU_LO, TAU_HI = 3.0 / 255, 12.0 / 255   # "changed" thresholds (premultiplied RGBA difference)

NAMES = {
    "howitzer": {"bg": "Гаубица", "en": "Howitzer"},
    "zis3": {"bg": "Дивизионно оръдие", "en": "Field gun"},
}


def load_premultiplied(path, scale=1.0):
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im, np.float32) / 255.0
    a[..., :3] *= a[..., 3:4]
    # Shadow-catcher pixels come out as black + alpha; give them the tint of real shadow.
    rgb, al = a[..., :3], a[..., 3]
    pure = (rgb.max(axis=2) < 0.03 * al + 1e-6) & (al > 0)
    a[pure, :3] = np.asarray(SHADOW_TINT, np.float32) * al[pure, None]
    if scale != 1.0:
        h, w = a.shape[:2]
        size = (int(round(w * scale)), int(round(h * scale)))
        chans = [Image.fromarray(a[..., c], "F").resize(size, Image.LANCZOS) for c in range(4)]
        a = np.clip(np.stack([np.asarray(c) for c in chans], axis=-1), 0.0, 1.0)
        a[..., :3] = np.minimum(a[..., :3], a[..., 3:4])
    return a


def _morph(mask, op, size=3, times=1):
    im = Image.fromarray((mask * 255).astype(np.uint8))
    f = ImageFilter.MaxFilter(size) if op == "dilate" else ImageFilter.MinFilter(size)
    for _ in range(times):
        im = im.filter(f)
    return np.asarray(im) > 127


def _flood(seeds, allowed):
    """Grow `seeds` through 8-connected `allowed` pixels."""
    m = seeds & allowed
    while True:
        grown = _morph(m, "dilate") & allowed
        if grown.sum() == m.sum():
            return m
        m = grown


def aim_layer(base, full):
    """Premultiplied RGBA layer L with  L over base == full  wherever the gun changes
    the picture (itself, its shadow, its bounce light). Unchanged pixels stay empty,
    and so does render noise that is not connected to the gun."""
    d = np.abs(full - base).max(axis=2)
    changed = d > TAU_LO
    core = _morph(_morph(d > TAU_HI, "erode"), "dilate")            # solid changed areas
    mask = _flood(core, changed) | (changed & _morph(core, "dilate", 5, 3))
    mask = _morph(_morph(mask, "dilate"), "erode")                  # close pinholes
    w = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))
    w = np.asarray(w.filter(ImageFilter.GaussianBlur(0.8)), np.float32) / 255.0
    w = np.maximum(w, mask.astype(np.float32))                      # 1 inside, soft rim outside
    ba, fa = base[..., 3], full[..., 3]
    brgb, frgb = base[..., :3], full[..., :3]
    # Opacity p of the layer. Three lower bounds: reach the alpha of the full render,
    # keep every colour channel non-negative (darkening), and not above p (brightening).
    with np.errstate(divide="ignore", invalid="ignore"):
        p_alpha = np.where(ba >= 0.999, 1.0, (fa - ba) / np.maximum(1.0 - ba, 1e-6))
        eps = 1.5 / 255                                             # ignore 8-bit rounding noise
        p_dark = 1.0 - ((frgb + eps) / (brgb + eps)).min(axis=2)
        p_bright = ((frgb - brgb - eps) / np.maximum(1.0 - brgb, eps)).max(axis=2)
    p_alpha = np.clip(p_alpha, 0.0, 1.0)
    p_colour = np.clip(np.maximum(np.maximum(p_alpha, p_dark), p_bright), 0.0, 1.0)
    # Raising p above p_alpha makes the result too opaque by (p - p_alpha) * (1 - ba): harmless
    # on solid ground, wrong on the see-through edge of the patch. So blend by the base alpha.
    p = p_alpha * (1.0 - ba) + p_colour * ba
    rgb = np.clip(frgb - (1.0 - p[..., None]) * brgb, 0.0, p[..., None])
    layer = np.concatenate([rgb, p[..., None]], axis=-1) * w[..., None]
    return layer.astype(np.float32)


def over(top, bottom):
    return top + (1.0 - top[..., 3:4]) * bottom


def to_image(pm):
    """Premultiplied float RGBA -> straight 8-bit RGBA image."""
    a = pm[..., 3:4]
    rgb = np.where(a > 1e-6, pm[..., :3] / np.maximum(a, 1e-6), 0.0)
    out = np.concatenate([rgb, a], axis=-1)
    return Image.fromarray((np.clip(out, 0, 1) * 255.0 + 0.5).astype(np.uint8), "RGBA")


def bbox(pm):
    ys, xs = np.where(pm[..., 3] > 0.5 / 255)
    if len(xs) == 0:
        return 0, 0, 1, 1
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _maxrects(sizes, W, H):
    """MaxRects, best-short-side-fit. Returns positions or None if they do not fit."""
    free = [(0, 0, W, H)]
    pos = [None] * len(sizes)
    for i in sorted(range(len(sizes)), key=lambda i: -max(sizes[i])):
        w, h = sizes[i][0] + 2 * PAD, sizes[i][1] + 2 * PAD
        best = None
        for (fx, fy, fw, fh) in free:
            if w <= fw and h <= fh:
                score = (min(fw - w, fh - h), max(fw - w, fh - h))
                if best is None or score < best[0]:
                    best = (score, fx, fy)
        if best is None:
            return None
        _, x, y = best
        pos[i] = (x + PAD, y + PAD)
        out = []
        for (fx, fy, fw, fh) in free:                       # split every free rect the new one cuts
            if x >= fx + fw or x + w <= fx or y >= fy + fh or y + h <= fy:
                out.append((fx, fy, fw, fh))
                continue
            if x > fx:
                out.append((fx, fy, x - fx, fh))
            if x + w < fx + fw:
                out.append((x + w, fy, fx + fw - x - w, fh))
            if y > fy:
                out.append((fx, fy, fw, y - fy))
            if y + h < fy + fh:
                out.append((fx, y + h, fw, fy + fh - y - h))
        free = [r for r in out if not any(
            o is not r and o[0] <= r[0] and o[1] <= r[1] and o[0] + o[2] >= r[0] + r[2]
            and o[1] + o[3] >= r[1] + r[3] for o in out)]
    return pos


def pack(sizes, max_side=2048):
    """sizes: [(w, h)] -> (positions, W, H) with the smallest area found."""
    area = sum((w + 2 * PAD) * (h + 2 * PAD) for w, h in sizes)
    widest = max(w for w, _ in sizes) + 2 * PAD
    best = None
    lo = max(256, (widest + 63) // 64 * 64, int(math.sqrt(area) * 0.75) // 64 * 64)
    hi = max(lo, min(max_side * 2, int(math.sqrt(area) * 1.7) // 64 * 64))
    for W in range(lo, hi + 1, 64):
        H = max(64, int(math.ceil(area / W / 16)) * 16)
        while H <= max_side * 2:
            if best is not None and W * H >= best[1] * best[2]:
                break
            pos = _maxrects(sizes, W, H)
            if pos is not None:
                # tighten to the rows actually used
                used = max(p[1] + sizes[i][1] + PAD for i, p in enumerate(pos))
                best = (pos, W, (used + 3) // 4 * 4)
                break
            H += 16
    return best


def pack_level(src, dst, model, level, check=True):
    d = os.path.join(src, model, "photoreal", f"L{level}")
    with open(os.path.join(d, "meta.json")) as f:
        meta = json.load(f)
    n = meta["dirs"]
    prefix = f"{model}_L{level}"
    report = {}
    for tag, scale in (("@2x", 1.0), ("@1x", 0.5)):
        base = load_premultiplied(os.path.join(d, "base.png"), scale)
        H, W = base.shape[:2]
        frames = [(f"{prefix}_base", base)]
        worst = 0.0
        for i in range(n):
            full = load_premultiplied(os.path.join(d, f"aim_{i:02d}.png"), scale)
            layer = aim_layer(base, full)
            if check:           # what the game will show vs. the complete render, in 8-bit
                q = np.asarray(to_image(layer), np.float32) / 255.0      # steps, where the layer is
                q[..., :3] *= q[..., 3:4]
                inside = layer[..., 3] > 0.5
                if inside.any():
                    err = np.abs(over(q, base) - full).max(axis=2)[inside]
                    worst = max(worst, float(np.percentile(err, 99.9)) * 255)
            frames.append((f"{prefix}_aim_{i:02d}", layer))
        boxes = [bbox(pm) for _, pm in frames]
        pos, AW, AH = pack([(b[2] - b[0], b[3] - b[1]) for b in boxes])
        atlas = Image.new("RGBA", (AW, AH), (0, 0, 0, 0))
        sheet = {"frames": {}, "animations": {f"{prefix}_aim": [f"{prefix}_aim_{i:02d}" for i in range(n)]}}
        for (name, pm), b, (x, y) in zip(frames, boxes, pos):
            w, h = b[2] - b[0], b[3] - b[1]
            atlas.paste(to_image(pm[b[1]:b[3], b[0]:b[2]]), (x, y))
            sheet["frames"][name] = {
                "frame": {"x": x, "y": y, "w": w, "h": h},
                "rotated": False, "trimmed": True,
                "spriteSourceSize": {"x": b[0], "y": b[1], "w": w, "h": h},
                "sourceSize": {"w": W, "h": H},
                "anchor": {"x": 0.5, "y": 0.5},
            }
        os.makedirs(os.path.join(dst, "towers"), exist_ok=True)
        image_name = f"{prefix}{tag}.webp"
        atlas.save(os.path.join(dst, "towers", image_name), quality=92, method=6, alpha_quality=100,
                   exact=False)
        sheet["meta"] = {"app": "strelite art pipeline", "image": image_name, "format": "RGBA8888",
                         "size": {"w": AW, "h": AH}, "scale": "2" if tag == "@2x" else "1"}
        with open(os.path.join(dst, "towers", f"{prefix}{tag}.json"), "w") as f:
            json.dump(sheet, f, separators=(",", ":"))
        kb = os.path.getsize(os.path.join(dst, "towers", image_name)) / 1024
        report[tag] = (AW, AH, kb, worst)
        print(f"[pack] {prefix}{tag}: atlas {AW}x{AH}, {kb:.0f} kB, "
              f"{AW * AH * 4 / 2**20:.1f} MB in GPU memory, layer error p99.9 {worst:.1f}/255", flush=True)
    ppm1 = meta["pxPerMetre"] / 2
    cx, cy = meta["anchorPx"]
    return {
        "level": level,
        "sheet": f"towers/{prefix}",
        "base": f"{prefix}_base",
        "aim": f"{prefix}_aim",
        "footprintRadiusM": meta["footprintRadiusM"],
        "sweepRadiusM": meta["sweepRadiusM"],
        # muzzle per direction: offset from the tower's ground point in @1x pixels (x right,
        # y down), and the same point in metres (grid x, grid y, height above ground)
        "muzzlePx": [[round((a["muzzlePx"][0] - cx) / 2, 1), round((a["muzzlePx"][1] - cy) / 2, 1)]
                     for a in meta["aims"]],
        "muzzleM": [a["muzzleM"] for a in meta["aims"]],
        "pxPerMetre1x": ppm1,
    }


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(here, "..", "out"))
    ap.add_argument("--dst", default=os.path.join(here, "..", "..", "public", "art"))
    ap.add_argument("--models", nargs="+", default=["howitzer", "zis3"])
    ap.add_argument("--levels", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--no-check", action="store_true")
    a = ap.parse_args()
    towers, ppm1, dirs = {}, None, None
    for model in a.models:
        levels = []
        for level in a.levels:
            if not os.path.exists(os.path.join(a.src, model, "photoreal", f"L{level}", "meta.json")):
                continue
            info = pack_level(a.src, a.dst, model, level, check=not a.no_check)
            ppm1 = info.pop("pxPerMetre1x")
            dirs = len(info["muzzlePx"])
            levels.append(info)
        if levels:
            towers[model] = {"name": NAMES.get(model, {"bg": model, "en": model}),
                             "placeholder": True, "levels": levels}
    if not towers:
        raise SystemExit("nothing to pack: no meta.json under " + a.src)
    path = os.path.join(a.dst, "towers.json")
    manifest = {}
    if os.path.exists(path):                    # keep towers packed in an earlier run
        with open(path) as f:
            manifest = json.load(f)
    manifest.update({
        "version": 1,
        "style": "photoreal",
        "projection": "2:1 dimetric, orthographic, camera elevation 30 deg: one ground metre is "
                      "pxPerMetre wide along screen x and half of that along screen y",
        "pxPerMetre": {"@1x": ppm1, "@2x": ppm1 * 2},
        "suggestedMetresPerTile": 12,
        "directions": dirs,
        "aimZero": "frame 0 aims along grid +x (screen lower-right); frames advance with "
                   "atan2(dy, dx) in grid cells, i.e. clockwise on screen",
        "frameForAim": "Math.round(aim / (2 * Math.PI / directions)) mod directions",
        "sheets": "towers/<model>_L<level>@1x.json or @2x.json (PixiJS spritesheet); draw "
                  "<base> first, then <aim>_NN on top, both at the tower's ground point",
    })
    for model, entry in towers.items():         # merge by level, so levels can be packed one by one
        known = manifest.setdefault("towers", {}).setdefault(model, {"levels": []})
        merged = {lv["level"]: lv for lv in known.get("levels", [])}
        merged.update({lv["level"]: lv for lv in entry["levels"]})
        entry["levels"] = [merged[k] for k in sorted(merged)]
        manifest["towers"][model] = entry
    with open(path, "w") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
    print(f"[pack] manifest: {path}")


if __name__ == "__main__":
    main()
