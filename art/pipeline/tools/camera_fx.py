"""Whole-frame "camera" filter for the photoreal style (preview of the in-game
post-process). These effects belong to the FRAME, not to a sprite: in the game
they run once over the whole screen (PixiJS filter), so they are never baked
into sprites. This script applies the same chain to a still for review.

Chain, in the order light meets them in a real camera (Carlson et al. 2018):
  lens softness -> lateral chromatic aberration -> vignetting (cos^4 falloff)
  -> sensor noise (shot + read, stronger in the shadows) -> in-camera sharpening
  -> JPEG compression.

Usage: python3 tools/camera_fx.py in.png out.jpg [--strength 1.0]
"""
import argparse

import numpy as np
from PIL import Image, ImageFilter


def _to_linear(a):
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def _to_srgb(a):
    a = np.clip(a, 0.0, 1.0)
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * a ** (1 / 2.4) - 0.055)


def apply(img, strength=1.0, seed=3, ev=0.0):
    img = img.convert("RGB")
    w, h = img.size
    # 1. lens softness: no real lens resolves a perfectly crisp CG edge
    img = img.filter(ImageFilter.GaussianBlur(0.55 * strength * w / 1600))
    # 2. lateral chromatic aberration: red and blue are magnified slightly differently
    r, g, b = img.split()
    k = 0.0009 * strength

    def scaled(ch, f):
        nw, nh = round(w * f), round(h * f)
        big = ch.resize((nw, nh), Image.BICUBIC)
        left, top = (nw - w) // 2, (nh - h) // 2
        return big.crop((left, top, left + w, top + h))

    img = Image.merge("RGB", (scaled(r, 1 + k), g, scaled(b, 1 + 2 * k)))
    a = _to_linear(np.asarray(img, np.float32) / 255.0)
    # 3. vignetting: natural cos^4 falloff of a 200 mm lens is tiny, mechanical adds more
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    rr = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)) / np.sqrt(2)
    a *= (1.0 - 0.22 * strength * rr ** 2.2)[..., None]
    a *= 2.0 ** ev                      # exposure compensation dialled in on the camera
    # 4. sensor noise: photon shot noise ~ sqrt(signal), plus a read-noise floor
    rng = np.random.default_rng(seed)
    sigma = strength * (0.012 * np.sqrt(np.maximum(a, 0)) + 0.0015)
    noise = rng.standard_normal(a.shape).astype(np.float32)
    # demosaicing correlates noise between neighbours: blur it a touch
    noise = (noise + np.roll(noise, 1, 0) * 0.35 + np.roll(noise, 1, 1) * 0.35) / 1.2
    a = a + noise * sigma
    out = Image.fromarray((_to_srgb(a) * 255 + 0.5).astype(np.uint8))
    # 5. in-camera sharpening (leaves the faint halos every phone/DSLR JPEG has)
    out = out.filter(ImageFilter.UnsharpMask(radius=1.2 * w / 1600, percent=int(55 * strength),
                                             threshold=2))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--strength", type=float, default=1.0)
    ap.add_argument("--ev", type=float, default=0.0, help="exposure compensation, stops")
    ap.add_argument("--quality", type=int, default=90)
    a = ap.parse_args()
    res = apply(Image.open(a.src), a.strength, ev=a.ev)
    if a.dst.lower().endswith((".jpg", ".jpeg")):
        res.save(a.dst, quality=a.quality, subsampling=1)      # 6. JPEG, 4:2:2 chroma
    else:
        res.save(a.dst)
