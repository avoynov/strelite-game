#!/usr/bin/env bash
# Render and pack the enemy units, one at a time (resumable).
set -euo pipefail
cd "$(dirname "$0")"
OUT="${OUT:-../out}"; MODELS="${MODELS:-infantry truck tank}"
for model in $MODELS; do
  python3 render_sprites.py --model "$model" --style photoreal --enemy --dirs 16 --ppm 32 \
    --samples 32 --resume --out "$OUT"
  python3 pack_enemies.py --src "$OUT" --models "$model"
done
