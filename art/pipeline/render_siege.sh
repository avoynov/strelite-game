#!/usr/bin/env bash
# Render the siege engines as layered game sprites: base + 32 aim directions per level, the
# firing animation in FIRE_DIRS directions, the flying rounds, and pack it all into
# public/art/. Resumable: finished frames are kept, each level is packed when complete.
# About 1.5 h per trebuchet level on 4 CPU cores.
set -euo pipefail
cd "$(dirname "$0")"
OUT="${OUT:-../out}"
MODELS="${MODELS:-trebuchet ballista}"
LEVELS="${LEVELS:-1 2 3 4 5}"
FIRE_DIRS="${FIRE_DIRS:-32}"
for model in $MODELS; do
  for level in $LEVELS; do
    python3 render_sprites.py --model "$model" --style photoreal --levels "$level" --dirs 32 \
      --fire --fire-dirs "$FIRE_DIRS" --fire-samples 20 --ground patch --ppm 32 --samples 32 --resume --out "$OUT"
    python3 pack_atlas.py --src "$OUT" --dst ../../public/art --models "$model" --levels "$level"
  done
  if grep -q "^def build_round" "strelite_art/models/$model.py"; then
    python3 render_projectiles.py --model "$model" --resume --out "$OUT"
  fi
done
