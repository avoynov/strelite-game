"""Review sheets for the photoreal towers, built from the very files the game
loads (public/art): atlases, manifest and ground tile. PIL only.

  levels_<tower>.jpg   the three levels side by side on the ground
  turntable_<tower>_L<n>.jpg  all 32 aim frames of one level
  phone.png            every tower level at the size it has on a phone, 1:1 device
                       pixels, plus a 3x enlargement to judge readability
  compare_abv.jpg      styles A, Б (from the earlier cannon sheet) and В

Usage: python3 tools/review_sheets.py --art ../../public/art --dst ../previews/style-v
"""
import argparse
import json
import math
import os

from PIL import Image, ImageDraw, ImageFont

BG = (24, 28, 36)
LABEL = (235, 235, 240)


def font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


class Art:
    def __init__(self, root):
        self.root = root
        with open(os.path.join(root, "towers.json")) as f:
            self.manifest = json.load(f)
        self.sheets = {}
        g = next(iter(self.manifest.get("ground", {}).values()), None)
        self.ground = Image.open(os.path.join(root, g["image"] + "@2x.webp")).convert("RGB") if g else None
        self.ppm = self.manifest["pxPerMetre"]["@2x"]

    def level(self, tower, level):
        return next(lv for lv in self.manifest["towers"][tower]["levels"] if lv["level"] == level)

    def _sheet(self, lv):
        if lv["sheet"] not in self.sheets:
            with open(os.path.join(self.root, lv["sheet"] + "@2x.json")) as f:
                data = json.load(f)
            img = Image.open(os.path.join(self.root, "towers", data["meta"]["image"])).convert("RGBA")
            self.sheets[lv["sheet"]] = (data, img)
        return self.sheets[lv["sheet"]]

    def paste(self, canvas, lv, name, x, y):
        """Draw frame `name` with the tower's ground point at (x, y), like the game does."""
        data, img = self._sheet(lv)
        f = data["frames"][name]
        fr, sss, src = f["frame"], f["spriteSourceSize"], f["sourceSize"]
        tile = img.crop((fr["x"], fr["y"], fr["x"] + fr["w"], fr["y"] + fr["h"]))
        canvas.alpha_composite(tile, (int(round(x - src["w"] / 2 + sss["x"])),
                                      int(round(y - src["h"] / 2 + sss["y"]))))

    def ground_canvas(self, w, h, ox=0, oy=0):
        canvas = Image.new("RGBA", (w, h), (107, 106, 69, 255))
        if self.ground is not None:
            gw, gh = self.ground.size
            for y in range(-((oy % gh) or gh), h, gh):
                for x in range(-((ox % gw) or gw), w, gw):
                    canvas.paste(self.ground, (x, y))
        return canvas

    def tower(self, tower, level, aim, w, h, cy=0.56, ox=0, oy=0):
        lv = self.level(tower, level)
        canvas = self.ground_canvas(w, h, ox, oy)
        self.paste(canvas, lv, lv["base"], w / 2, h * cy)
        self.paste(canvas, lv, f"{lv['aim']}_{aim:02d}", w / 2, h * cy)
        return canvas


def levels_sheet(art, dst, tower, aim=6):
    lvs = art.manifest["towers"][tower]["levels"]
    r = max(lv["footprintRadiusM"] for lv in lvs) + 1.4
    w, h = int(2 * r * art.ppm), int(1.25 * r * art.ppm)
    pad, head = 12, 44
    sheet = Image.new("RGBA", (pad + len(lvs) * (w + pad), head + h + pad), BG + (255,))
    d = ImageDraw.Draw(sheet)
    for i, lv in enumerate(lvs):
        x = pad + i * (w + pad)
        d.text((x + w // 2, head // 2), f"Ниво {lv['level']}", fill=LABEL, font=font(22), anchor="mm")
        sheet.alpha_composite(art.tower(tower, lv["level"], aim, w, h, ox=i * 310, oy=i * 170), (x, head))
    sheet.convert("RGB").save(os.path.join(dst, f"levels_{tower}.jpg"), quality=92)


def turntable_sheet(art, dst, tower, level, cols=8):
    lv = art.level(tower, level)
    n = art.manifest["directions"]
    r = lv["footprintRadiusM"] + 0.9
    w, h = int(2 * r * art.ppm / 2), int(1.3 * r * art.ppm / 2)
    rows = math.ceil(n / cols)
    sheet = Image.new("RGBA", (cols * w, rows * h), BG + (255,))
    for i in range(n):
        big = art.tower(tower, level, i, w * 2, h * 2)
        sheet.alpha_composite(big.resize((w, h), Image.LANCZOS), ((i % cols) * w, (i // cols) * h))
    sheet.convert("RGB").save(os.path.join(dst, f"turntable_{tower}_L{level}.jpg"), quality=90)


def phone_sheet(art, dst, tile_px_css=48, dpr=3, zoom=3):
    """A 12 m tile is a 48 pt wide diamond at the game's default zoom; a 3x phone
    shows it 144 device pixels wide."""
    T = art.manifest["suggestedMetresPerTile"]
    ppm_dev = tile_px_css * dpr / (T * math.sqrt(2))
    k = ppm_dev / art.ppm
    cell = int(tile_px_css * dpr * 1.25)
    towers = list(art.manifest["towers"].items())
    pad, head, side = 14, 64, 250
    cols = 3
    W = side + cols * (cell + cell * zoom // 2 + 2 * pad) + pad
    H = head + len(towers) * (cell * zoom // 2 + pad) + pad
    sheet = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(sheet)
    d.text((16, 14), f"Телефон: плочка 12 м = {tile_px_css} pt. Вляво 1:1 пиксели на екран 3x, "
                     f"вдясно увеличено.", fill=LABEL, font=font(18))
    for ti, (tid, tw) in enumerate(towers):
        y = head + ti * (cell * zoom // 2 + pad)
        d.multiline_text((16, y + cell * zoom // 4), tw["name"]["bg"].replace(" ", "\n"), fill=LABEL,
                         font=font(20), anchor="lm")
        for li, lv in enumerate(tw["levels"]):
            src = int(cell / k)
            big = art.tower(tid, lv["level"], 6 + 9 * li, src, src, cy=0.55, ox=li * 300, oy=ti * 200)
            small = big.resize((cell, cell), Image.LANCZOS)
            x = side + li * (cell + cell * zoom // 2 + 2 * pad)
            sheet.alpha_composite(small, (x, y + (cell * zoom // 2 - cell) // 2))
            crop = small.crop((cell // 4, cell // 4, cell * 3 // 4, cell * 3 // 4))
            sheet.alpha_composite(crop.resize((cell * zoom // 2, cell * zoom // 2), Image.NEAREST),
                                  (x + cell + pad, y))
    sheet.convert("RGB").save(os.path.join(dst, "phone.png"))


def compare_sheet(art, dst, old_compare, tower="howitzer", aim=6):
    """A and Б rows come from the earlier cannon comparison; В is added below."""
    if not os.path.exists(old_compare):
        return
    old = Image.open(old_compare).convert("RGBA")
    lvs = art.manifest["towers"][tower]["levels"]
    side, pad = 230, 16
    cell = (old.width - side - pad) // len(lvs) - pad
    sheet = Image.new("RGBA", (old.width, old.height + cell + pad), BG + (255,))
    sheet.alpha_composite(old, (0, 0))
    d = ImageDraw.Draw(sheet)
    y = old.height
    d.multiline_text((16, y + cell // 2), "В · Фотореален\n(избран)", fill=LABEL, font=font(18), anchor="lm")
    r = max(lv["footprintRadiusM"] for lv in lvs) + 0.8
    src = int(2 * r * art.ppm)
    for i, lv in enumerate(lvs):
        big = art.tower(tower, lv["level"], aim, src, src, cy=0.55, ox=i * 310, oy=i * 170)
        sheet.alpha_composite(big.resize((cell, cell), Image.LANCZOS), (side + i * (cell + pad), y))
    sheet.convert("RGB").save(os.path.join(dst, "compare_abv.jpg"), quality=92)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--art", default=os.path.join(here, "..", "..", "..", "public", "art"))
    ap.add_argument("--dst", default=os.path.join(here, "..", "..", "previews", "style-v"))
    ap.add_argument("--old-compare", default="/mnt/project-files/art-previews/compare_cannon.png")
    a = ap.parse_args()
    os.makedirs(a.dst, exist_ok=True)
    art = Art(a.art)
    for tid, tw in art.manifest["towers"].items():
        levels_sheet(art, a.dst, tid)
        turntable_sheet(art, a.dst, tid, tw["levels"][-1]["level"])
    phone_sheet(art, a.dst)
    compare_sheet(art, a.dst, a.old_compare)
    print(f"[sheets] written to {a.dst}")


if __name__ == "__main__":
    main()
