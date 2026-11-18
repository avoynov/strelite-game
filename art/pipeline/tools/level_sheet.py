"""Review sheet of a tower's levels, side by side, on the game's field ground.

The standard test before any long render (see art/SOP.md, "Review loop"):

  python3 render_sprites.py --model <m> --style photoreal --levels 1 2 3 4 5 --dirs 32 \
      --only-dir -1 22 --ground patch --ppm 64 --samples 16 --out /tmp/rev
  python3 tools/level_sheet.py /tmp/rev/<m>/photoreal 22 levels_<m>.jpg --scale 2

-1 renders the base layer, 22 one aim direction (barrel toward the screen's lower left,
the sunlit side to the camera). --scale is the render's pixels per metre over the
ground tile's (64 / 32 = 2), so the grass has the right size behind the gun.
"""
import argparse
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FIELD = os.path.join(HERE, "..", "..", "..", "public", "art", "ground", "field@2x.webp")


def composite(src, level, aim, ground):
    b = Image.open(os.path.join(src, f"L{level}", "base.png")).convert("RGBA")
    b.alpha_composite(Image.open(os.path.join(src, f"L{level}", f"aim_{aim:02d}.png")).convert("RGBA"))
    bg = Image.new("RGBA", b.size)
    for y in range(0, b.height, ground.height):
        for x in range(0, b.width, ground.width):
            bg.paste(ground, (x, y))
    bg.alpha_composite(b)
    return bg.convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="<out>/<model>/photoreal")
    ap.add_argument("aim", type=int, help="aim direction rendered with --only-dir")
    ap.add_argument("out", help="output .jpg")
    ap.add_argument("--scale", type=int, default=2, help="render ppm / 32")
    ap.add_argument("--levels", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    ap.add_argument("--crop", type=float, nargs=4, default=(0.18, 0.18, 0.64, 0.62),
                    help="x, y, width, height of the kept part, as fractions of the frame")
    a = ap.parse_args()
    g = Image.open(FIELD).convert("RGBA")
    if a.scale != 1:
        g = g.resize((g.width * a.scale, g.height * a.scale), Image.LANCZOS)
    ims = [composite(a.src, lv, a.aim, g) for lv in a.levels]
    W, H = ims[0].size
    x0, y0, cw, ch = int(W * a.crop[0]), int(H * a.crop[1]), int(W * a.crop[2]), int(H * a.crop[3])
    sheet = Image.new("RGB", (cw * len(ims), ch))
    for i, im in enumerate(ims):
        sheet.paste(im.crop((x0, y0, x0 + cw, y0 + ch)), (i * cw, 0))
    sheet.save(a.out, quality=90)
    print(f"[sheet] {a.out}: {sheet.width}x{sheet.height}")


if __name__ == "__main__":
    main()
