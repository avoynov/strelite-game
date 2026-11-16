"""Build review sheets from rendered sprites (PIL only, no Blender needed).

- compare_<model>.png : both styles x all levels, hero direction, on a grass tile grid
- turntable_<model>_<style>.png : all directions of one level
- mobile_<model>.png  : sprites at the sizes they will appear on a phone

Usage: python3 make_sheets.py --model cannon --src ../out --dst ../previews
"""
import argparse
import glob
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from strelite_art.scene import CAM_ELEVATION_DEG, CAM_TARGET_Z, ORTHO_SCALE  # noqa: E402

BG = (24, 28, 36)
GRASS = [(110, 160, 72), (100, 150, 66)]
GRASS_REAL = [(92, 120, 64), (86, 113, 60)]
LABEL = (235, 235, 240)


def font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def project(size, x, y, z=0.0):
    """World metres -> pixel coords, same maths as the Blender camera."""
    ppm = size / ORTHO_SCALE
    el, az = math.radians(CAM_ELEVATION_DEG), math.radians(45)
    # camera right and up vectors
    rx, ry = math.cos(az), math.sin(az)
    ux, uy, uz = -math.sin(az) * math.sin(el), math.cos(az) * math.sin(el), math.cos(el)
    sx = (x * rx + y * ry) * ppm
    sy = (x * ux + y * uy + (z - CAM_TARGET_Z) * uz) * ppm
    return size / 2 + sx, size / 2 - sy


def ground(size, style, tiles=5):
    """Iso grass tiles (1 m each) under the sprite, matched to the camera projection.
    The tower's 2x2 footprint is the 4 tiles around the origin."""
    img = Image.new("RGBA", (size, size), BG + (255,))
    d = ImageDraw.Draw(img)
    cols = GRASS if style == "stylized" else GRASS_REAL
    for i in range(-tiles, tiles):
        for j in range(-tiles, tiles):
            pts = [project(size, i, j), project(size, i + 1, j), project(size, i + 1, j + 1),
                   project(size, i, j + 1)]
            d.polygon(pts, fill=cols[(i + j) % 2])
    return img


def hero_dir(paths):
    n = len(paths)
    return paths[n // 2] if n > 1 else paths[0]


def load_level(src, model, style, level):
    paths = sorted(glob.glob(os.path.join(src, model, style, f"L{level}", "dir_*.png")))
    return paths


def compose(sprite_path, style, size):
    spr = Image.open(sprite_path).convert("RGBA")
    if spr.size[0] != size:
        spr = spr.resize((size, size), Image.LANCZOS)
    g = ground(size, style)
    g.alpha_composite(spr)
    return g


def compare_sheet(src, dst, model, styles, levels, cell=384):
    pad, head, side = 16, 56, 230
    W = side + len(levels) * (cell + pad) + pad
    H = head + len(styles) * (cell + pad) + pad
    sheet = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(sheet)
    names = {"stylized": "A · Стилизиран\n(Clash-подобен)", "realistic": "Б · Реалистичен"}
    for li, lv in enumerate(levels):
        d.text((side + li * (cell + pad) + cell // 2, head // 2), f"Ниво {lv}", fill=LABEL,
               font=font(26), anchor="mm")
    for si, st in enumerate(styles):
        y = head + si * (cell + pad)
        d.multiline_text((16, y + cell // 2), names.get(st, st), fill=LABEL, font=font(18),
                         anchor="lm")
        for li, lv in enumerate(levels):
            paths = load_level(src, model, st, lv)
            if not paths:
                continue
            sheet.alpha_composite(compose(hero_dir(paths), st, cell),
                                  (side + li * (cell + pad), y))
    sheet.convert("RGB").save(os.path.join(dst, f"compare_{model}.png"))


def turntable_sheet(src, dst, model, style, level, cell=200):
    paths = load_level(src, model, style, level)
    if not paths:
        return
    W = len(paths) * cell
    sheet = Image.new("RGBA", (W, cell), BG + (255,))
    for i, p in enumerate(paths):
        sheet.alpha_composite(compose(p, style, cell), (i * cell, 0))
    sheet.convert("RGB").save(os.path.join(dst, f"turntable_{model}_{style}_L{level}.png"))


def mobile_sheet(src, dst, model, styles, levels):
    """Phone check: a 2x2-tile tower is roughly 70-110 px wide on a 3x phone
    (~25-35 pt per tile). Shown at 1:1 pixels, upscaled x2 with nearest
    neighbour on the right so the blur/mush is visible."""
    sizes = [96, 64]
    pad = 12
    row_h = max(sizes) * 2 + pad
    W = 150 + len(levels) * (sum(sizes) + max(sizes) * 2 + 4 * pad)
    H = 50 + len(styles) * (row_h + pad)
    sheet = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(sheet)
    d.text((16, 16), "Телефон: 96px и 64px (1:1), плюс 64px увеличено x2", fill=LABEL, font=font(18))
    for si, st in enumerate(styles):
        y = 50 + si * (row_h + pad)
        d.text((16, y + row_h // 2), "A" if st == "stylized" else "Б", fill=LABEL, font=font(28),
               anchor="lm")
        x = 150
        for lv in levels:
            paths = load_level(src, model, st, lv)
            if not paths:
                continue
            full = compose(hero_dir(paths), st, 512)
            for s in sizes:
                small = full.resize((s, s), Image.LANCZOS)
                sheet.alpha_composite(small, (x, y + (row_h - s) // 2))
                x += s + pad
            zoom = full.resize((64, 64), Image.LANCZOS).resize((128, 128), Image.NEAREST)
            sheet.alpha_composite(zoom, (x, y + (row_h - 128) // 2))
            x += 128 + 3 * pad
    sheet.convert("RGB").save(os.path.join(dst, f"mobile_{model}.png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="cannon")
    ap.add_argument("--src", default=os.path.join(os.path.dirname(__file__), "..", "out"))
    ap.add_argument("--dst", default=os.path.join(os.path.dirname(__file__), "..", "previews"))
    ap.add_argument("--styles", nargs="+", default=["stylized", "realistic"])
    ap.add_argument("--levels", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--turntable-level", type=int, default=3)
    a = ap.parse_args()
    os.makedirs(a.dst, exist_ok=True)
    compare_sheet(a.src, a.dst, a.model, a.styles, a.levels)
    mobile_sheet(a.src, a.dst, a.model, a.styles, a.levels)
    for st in a.styles:
        turntable_sheet(a.src, a.dst, a.model, st, a.turntable_level)


if __name__ == "__main__":
    main()
