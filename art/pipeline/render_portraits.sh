#!/usr/bin/env bash
# Clean gun portraits for the Arsenal screen: the gun alone (no soil, no fortifications), 32 headings per
# level, then atlases in public/art/portraits. All 7 guns x 5 levels by default; on CI each level is its
# own job (render-queue.json "portraits").
set -euo pipefail
cd "$(dirname "$0")"
OUT="${OUT:-../out}"
MODELS="${MODELS:-howitzer zis3 ballista scorpion greekfire trebuchet railgun}"
LEVELS="${LEVELS:-1 2 3 4 5}"
for model in $MODELS; do
  python3 render_portraits.py --model "$model" --levels $LEVELS --dirs 32 --ppm 44 --samples 24 --resume --out "$OUT"
done
python3 pack_portraits.py --src "$OUT/portraits" --dst ../../public/art
