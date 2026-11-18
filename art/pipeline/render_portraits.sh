#!/usr/bin/env bash
# Clean gun portraits for the Arsenal screen: 32 headings per level, then atlases in public/art/portraits.
set -euo pipefail
cd "$(dirname "$0")"
OUT="${OUT:-../out}"
MODELS="${MODELS:-zis3 howitzer}"
for model in $MODELS; do
  python3 render_portraits.py --model "$model" --levels 1 2 3 --dirs 32 --ppm 44 --samples 24 --resume --out "$OUT"
done
python3 pack_portraits.py --src "$OUT/portraits" --dst ../../public/art
