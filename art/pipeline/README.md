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

## Output
`art/out/<model>/<style>/L<level>/dir_NN.png`, 512×512 RGBA. `dir_NN` aims the turret at
`NN * 360/dirs` degrees CCW from world +Y (`dir_00` = screen upper-right).

## Next steps
- Render base and turret as separate layers (static base + rotating turret, fewer frames).
- 16 directions, auto-crop + pack into a texture atlas for PixiJS.
- More models: crossbow, mortar, enemies, ground tiles, using the same kit.
