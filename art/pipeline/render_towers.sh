#!/usr/bin/env bash
# Render every photoreal tower as layered game sprites (base + 32 aim directions per
# level) and pack them into atlases in public/art/. About 1.5 h on 4 CPU cores.
# Safe to re-run after an interruption: finished frames are kept, each level is packed
# as soon as its frames are complete.
set -euo pipefail
cd "$(dirname "$0")"
OUT="${OUT:-../out}"
MODELS="${MODELS:-howitzer zis3}"
LEVELS="${LEVELS:-1 2 3}"
for model in $MODELS; do
  for level in $LEVELS; do
    python3 render_sprites.py --model "$model" --style photoreal --levels "$level" --dirs 32 \
      --ground patch --ppm 32 --samples 32 --resume --out "$OUT"
    python3 pack_atlas.py --src "$OUT" --dst ../../public/art --models "$model" --levels "$level"
  done
done
