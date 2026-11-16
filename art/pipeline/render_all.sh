#!/usr/bin/env bash
# Render every style/level/direction for the cannon prototype, then build review sheets.
set -euo pipefail
cd "$(dirname "$0")"
OUT="${OUT:-../out}"
for style in stylized realistic; do
  python3 render_sprites.py --model cannon --style "$style" --levels 1 2 3 --dirs 8 \
    --size 512 --samples 48 --out "$OUT"
done
python3 make_sheets.py --model cannon --src "$OUT" --dst ../previews
