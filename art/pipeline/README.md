# Art pipeline (prototype)

All game art is generated procedurally in headless Blender, so every asset shares
**one camera, one light rig and one material library** and looks like one set.

```
pip install bpy pillow        # Blender as a Python module (5.x)
./render_all.sh               # renders to art/out/, review sheets to art/previews/
```

## Contracts (do not change per asset)
- **Camera** (`strelite_art/scene.py`): Clash-of-Clans-style 2:1 dimetric, orthographic,
  30° elevation, 45° azimuth. A 1×1 m tile is a diamond twice as wide as tall.
  `ORTHO_SCALE` is fixed so every sprite has the same pixels per metre.
- **Light**: key sun from screen upper-left (shadows fall lower-right), sky fill, rim.
  Shadows are kept in the sprite's alpha via a shadow catcher.
- **Materials** (`strelite_art/materials.py`): one palette, two treatments:
  `stylized` (saturated, AO, dark outline) and `realistic` (PBR grain, wear, bump).
  Models ask for materials by name, never create their own.
- **Models** (`strelite_art/models/`): built only from the `Kit` primitives in `geo.py`.
  Upgrade levels add parts and better materials; the silhouette stays the same.

## Style В: `photoreal` (the game's art style)
Military hardware that looks photographed. Same pipeline, different physics:
- **Models** are built at real size (metres) from the `Kit` primitives plus the
  fortification kit in `strelite_art/fort.py` (sandbags, HESCO-type barriers, slab,
  log revetment, camouflage net, crates). Node empties `turret`, `elevating`,
  `recoil` and a `muzzle` marker describe how the gun moves.
- **Light**: Blender's physical sky with its own 0.545° sun at 45°, white balance and
  exposure calibrated on an 18 % grey card (`tools/calibrate_exposure.py`), AgX.
- **Materials** (`materials_photoreal.py`): layered ageing driven by geometry (edges,
  cavities, up-facing, height): primer, paint, chips, rust and wash streaks, grime, dust, mud.
  They read per-vertex attributes written by `stamp()`, so they survive joining and baking.
- **Ground** (`terrain.py`): `Patch` is the soil a tower sprite brings with it (fades out
  at the edge, can be dug into a pit or levelled for a slab), `Field` the open ground of
  the map, `Terrain` the big ground for photo-style stills.

### Game sprites
```
./render_towers.sh            # render_sprites.py --ground patch, then pack_atlas.py
python3 render_ground.py      # seamless ground tile
```
- Camera: the board's own orthographic 2:1 projection at **32 px per metre**, so sprites
  sit on the tile grid exactly and metres map to pixels linearly.
- `render_sprites.py --ground patch` writes `base.png` (gun hidden), `aim_00..31.png`
  (complete tower per direction, same noise seed) and `meta.json` per level.
- `pack_atlas.py` turns each aim frame into a layer that reproduces the complete render
  when drawn over the base (exact "over" decomposition, render noise away from the gun
  is dropped), trims, packs with MaxRects and writes PixiJS spritesheets at @2x and @1x
  plus `towers.json`. It prints the reconstruction error per atlas.
- Frame `NN` aims at `NN * 2π/32` in the game's own angle (`atan2(dy, dx)` in grid cells).
- What the game does with the files: `art/README.md`.

### Menu portraits (Arsenal screen)
```
./render_portraits.sh         # render_portraits.py (gun only, 32 headings, 44 px/m), then pack_portraits.py
```
- Same camera, light and materials as the game sprites, but the soil patch and every static
  part (sandbags, slab, crates, nets) are hidden: only the gun and its shadow, transparent.
- `pack_portraits.py` crops all headings of a level to one box and writes
  `public/art/portraits/<model>_L<n>.webp` plus `public/art/portraits.json`.
- A new gun: add its frame size to `FRAME_M` in `render_portraits.py` and add it to `MODELS`.

### Photo-style stills (hero shots, blind tests)
```
python3 render_sprites.py --model howitzer --style photoreal --levels 1 --dirs 16 \
  --only-dir 12 --size 1600 --samples 96 --ground terrain      # 200 mm telephoto, real terrain
python3 tools/camera_fx.py in.png out.jpg --ev 0.35             # whole-frame camera filter
```
Camera effects (`tools/camera_fx.py`) are a whole-frame filter and are never baked into sprites.

### Kept for a later move to real 3D
- `export_gltf.py`: bakes base colour, ORM and normal maps and exports a GLB with
  `static` / `turret` / `elevating` / `recoil` nodes (1 unit = 1 m, +Y up).
- `tools/save_blend.py`: writes each model and level as a `.blend` file.

Scanned CC0 textures (Poly Haven, ambientCG) are not used: everything is procedural.

## Output
Styles A/Б: `art/out/<model>/<style>/L<level>/dir_NN.png`, 512×512 RGBA. `dir_NN` aims the
turret at `NN * 360/dirs` degrees CCW from world +Y (`dir_00` = screen upper-right).
Style В: game-ready atlases in `public/art/` (see above).

## Next steps
- The final gun roster replaces the two placeholder guns (same format).
- Enemies, projectiles, muzzle flash and smoke, road and other map tiles in style В.
- Recoil frames, if firing needs more than a flash.
