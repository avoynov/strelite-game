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

## Style В: `photoreal` (preview)
Guns that look photographed. Same pipeline, different physics:
- **Camera**: full-frame, 200 mm telephoto, same 30°/45° view. Models are built at real
  size (metres) and declare `FRAME_M`, the real width the sprite frame covers.
- **Light**: Blender's physical sky with its own 0.545° sun at 45°, white balance and
  exposure calibrated on an 18 % grey card (`tools/calibrate_exposure.py`), AgX.
- **Materials** (`materials_photoreal.py`): layered ageing driven by geometry (edges,
  cavities, up-facing, height): primer, paint, chips, rust and wash streaks, grime, dust, mud.
- **Ground** (`terrain.py`): displaced soil, ruts, stones, grass. `--ground terrain` renders
  the photo, `--ground catcher` the transparent game sprite.
- **Camera effects** (`tools/camera_fx.py`) are a whole-frame filter, never baked in sprites.

```
python3 render_sprites.py --model howitzer --style photoreal --levels 1 --dirs 16 \
  --only-dir 12 --size 1600 --samples 96 --ground terrain
python3 tools/camera_fx.py in.png out.jpg --ev 0.35
```
Scanned CC0 textures (Poly Haven, ambientCG) are not used yet: their download hosts
were unreachable from the build container, so everything is procedural for now.

## Output
`art/out/<model>/<style>/L<level>/dir_NN.png`, 512×512 RGBA. `dir_NN` aims the turret at
`NN * 360/dirs` degrees CCW from world +Y (`dir_00` = screen upper-right).

## Next steps
- Render base and turret as separate layers (static base + rotating turret, fewer frames).
- 16 directions, auto-crop + pack into a texture atlas for PixiJS.
- More models: crossbow, mortar, enemies, ground tiles, using the same kit.
