# Game art (style В, photoreal)

**Making new art?** Follow [`SOP.md`](SOP.md): style, scale, model building, review, render, pack and handoff rules for every new object.

The game's art style is **В: photoreal military hardware that looks photographed**.
Everything is rendered from procedural Blender models in `art/pipeline/`; the game
only loads the finished files in `public/art/`.

The two guns shipped here (a 155 mm towed howitzer and a 76 mm field gun) are
**placeholders** for the final roster. The format will not change when the real
guns replace them.

## What the game loads

```
public/art/
  towers.json                     manifest: every tower, level, scale, muzzle points
  towers/<tower>_L<n>@1x.json     PixiJS spritesheet, 16 px per metre
  towers/<tower>_L<n>@1x.webp
  towers/<tower>_L<n>@2x.json     the same frames at 32 px per metre (4x the memory)
  towers/<tower>_L<n>@2x.webp
  ground/field@1x.webp            seamless ground tile, same scale as the towers
  ground/field@2x.webp
```

Each tower level is **two layers** drawn at the tower's ground point (frame anchor
0.5, 0.5 is that point):

1. `<tower>_L<n>_base`: everything that never moves: the tower's own patch of
   soil (it fades out at the edge and sits on any ground), fortifications,
   crates, their shadows.
2. `<tower>_L<n>_aim_00 … _31`: the gun in 32 directions, drawn on top with normal
   alpha blending.

An aim frame is not just the gun cut out. It is the exact difference between the
complete render and the base, so it also carries the gun's shadow on the ground
and on the sandbags, and it is missing where a wall hides the gun. Base + aim
reproduces the path-traced render of the whole tower.

### Conventions

| | |
|---|---|
| Projection | the board's own: 2:1 dimetric, orthographic. One metre of ground is `pxPerMetre` wide along screen x and half of that along screen y. |
| Aim | frame `i` aims at `i * 2π/32`, measured like `Tower.aim` in the simulation: `atan2(dy, dx)` in grid cells. Frame 0 points along grid +x (screen lower-right). `frameForAim()` does the rounding. |
| Scale | `pxPerMetre` in the manifest (16 at @1x, 32 at @2x). `spriteScale(cellPx, metresPerTile, 16)` gives the sprite scale for the board. |
| Tile size | **4 m per tile** (`METRES_PER_TILE` in `src/sim/content.ts`). A tower's static art stays inside `footprintRadiusM` ≤ size in tiles × 2 m. |
| Depth | sort the tower's node by its ground point like any other object. Base and aim always go together (base first). |
| Light | sun from the screen's lower-left, shadows fall to the upper-right. Enemies and props must be rendered with the same pipeline to match. |
| Muzzle | `muzzlePx[i]` (offset from the ground point, @1x pixels) and `muzzleM[i]` (grid x, grid y, height in metres) per aim frame: spawn projectiles, flashes and smoke there. |
| Ground | `ground/field` repeats in both screen directions (it is a 64 m square of ground). Draw it as a tiling sprite at the same pixels-per-metre as the towers. |
| Memory | about 2 MB of GPU memory per tower level at @1x, 8 MB at @2x. Load @1x on phones by default, @2x when the player zooms in or on large screens. |

## Using it (PixiJS)

`src/render/towers/` has the loader and a ready view:

```ts
import { TowerArt, SpriteTowerView } from './render/towers/spriteTowerView';

const art = await TowerArt.load(`${import.meta.env.BASE_URL}art`, 1);   // 1 = @1x, 2 = @2x
const view = new SpriteTowerView(art, 'howitzer', 1, (gx, gy) => board.project(gx, gy), board.cell);
objectsLayer.addChild(view.node);
view.place(tower.cx + 0.5, tower.cy + 0.5);
view.setAim(tower.aim);        // every frame; only swaps a texture when the frame changes
view.setLevel(2);              // on upgrade
const m = view.muzzle();       // where the shot leaves the barrel
```

`board.project` is the board's grid-to-screen function (`ix`/`iy` in
`boardRenderer.ts`) and `board.cell` the tile width in pixels.

The service worker does not precache `public/art` by default; add
`art/**/*.{webp,json}` to the PWA's `globPatterns` when the atlases go live.

## Moving to real 3D later

The decision to stay with sprites is deliberate (phones). To keep a later move
to real-time 3D cheap, the game talks to a tower's picture only through
`TowerView` (`src/render/towers/towerView.ts`): `place`, `setAim`, `setLevel`,
`muzzle`, in grid cells, radians and metres. Keep new gameplay code on that
interface and never reach into the sprites directly.

What is already prepared for 3D:

- The models are real-scale 3D (metres) with the node structure a game needs:
  `turret` (yaw), `elevating` (pitch about the trunnions), `recoil` (barrel slide).
- `art/pipeline/export_gltf.py` bakes base colour, roughness/metallic/AO and
  normal maps and exports a GLB with those nodes (verified on howitzer level 1:
  30 k triangles, 2.6 MB with 1024² textures).
- `art/pipeline/tools/save_blend.py --ground` writes each model and level as a
  `.blend` file (camera, sky, materials, soil patch; 4 to 6 MB each). They are not
  kept in git because the script rebuilds them in a minute; a saved set lives in the
  project files under `art-sources/style-v/`.
- All numbers in the manifest are in metres, so a 3D view can use them unchanged.

A 3D view would be one new class implementing `TowerView` with three.js (or
PixiJS 3D), an orthographic camera at 30° elevation / 45° azimuth and a sun at
45° elevation from the lower-left. The simulation, the HUD and the board code
stay as they are.

## Re-rendering

```
cd art/pipeline
pip install bpy pillow numpy          # Blender 5.x as a Python module
./render_towers.sh                    # all towers: ~1.5 h on 4 CPU cores, writes public/art
python3 render_ground.py              # the ground tile
python3 tools/review_sheets.py        # review sheets in art/previews/style-v
```

See `art/pipeline/README.md` for how the pipeline is built.
