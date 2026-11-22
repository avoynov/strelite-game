# Strelite Art Generation SOP (style В)

As of 2026-11-18. The living copy is the Claude Doc https://claude.ai/artifact/1napqXYweBF9qdJYeGTkpm; this file is synced from it (keep both in step when you change one).

## 1. Purpose and how to use this SOP

Any new art object for Strelite (gun, enemy, projectile, effect, wall, building, prop, ground) is built with the same headless Blender pipeline, the same camera, light, material library and level rules as the 7 guns, 7 enemies and 3 walls already in the game. Follow this SOP step by step and the new object will sit beside them with no visible seam in look, scale or quality.

The source of truth is the code in `art/pipeline/` of `avoynov/strelite-game` (main). When this SOP and the code disagree, the code wins: read the nearest existing model first and copy its patterns.

**Workflow for a new thread (do these in order):**

1. Read this SOP, then `art/pipeline/README.md` and the closest existing model file (section 12 names which one per asset type).
2. Restate the ask to the user in two or three lines: what the object is, its role in the game, its size in tiles, how many levels. Ask only what you cannot decide (section 8 lists what is the user's call).
3. Write the model as `art/pipeline/strelite_art/models/<model>.py` with the Kit API and the photoreal material library (sections 5 and 6). Real metres, real proportions.
4. Render a **review sheet** first: all levels side by side from the game angle, plus one close-up at @2x (section 8). Post it to the user and wait for their go. Never start a long render before the user approves the test.
5. Apply the user's notes, re-render only the changed levels, post again.
6. After approval, render for the game: short jobs locally, long jobs on GitHub Actions via `render-queue.json` (section 9).
7. Pack atlases and write the manifest entry in `public/art/towers.json` (section 10), run the repo tests, open or update a PR.
8. Tell the gameplay thread exactly which ids, frames and manifest keys are new (section 11).

**Who does what:** the art thread owns `art/pipeline/` and `public/art/`. The gameplay thread owns `src/` and the game ids in `src/sim/content.ts`. Never change the other side's files without telling them.

**Language:** talk to the user in Bulgarian, short and direct. Code, file names and comments in English. Display names in the manifest carry `bg` and `en`.

## 2. Style bible (what "looks like ours" means)

Style В is **ultra-realistic military hardware that looks photographed**, in a **parallel world with light steampunk accents**. The user chose it on 2026-11-16 ("Искам такава да е играта") and confirmed the world on 2026-11-17. Every new object must pass one test: placed next to the howitzer, the trebuchet and the tank in a screenshot, nobody can tell it was made later.

**The world**

- Familiar military and siege forms (towed guns, torsion engines, trucks, tanks), but with unfamiliar lines and details: brass, rivets, gauges, pipes, lamps, steam. Accents only, never the bulk of the object.
- The world justifies ancient siege engines next to field guns and one far-future railgun. A new object can come from any era if it is built as a real, working machine.
- Two sides with their own heraldry:
  - **Defenders (the player):** a gold-rimmed blue heater shield with a white crenellated tower. Helper `defender.emblem(k, parent, loc, normal, h=0.3)`. Put it on guns where a real army would paint a marking (shield, cheeks of the saddle), front and back.
  - **Attackers, the Iron Concord (Железният съюз):** slate paint (`paint_enemy`, `paint_enemy_worn`), oxblood bands (`paint_faction_red`), brass fittings, and the emblem: a red disc in a black cog with a brass spear. Helpers in `models/faction.py`: `emblem`, `band`, `rivets`, `lamp`, `gauge`, `stack`, `pennant`. Every enemy carries the emblem and a few of these accents.

**The look**

- Real size, real proportions, real construction. Every part must be explainable: what it does, how it is fixed, what holds it up. Bolts at joints, bands on timber, rivets on plates, cables that go somewhere.
- Built a little larger than history only where a part would vanish at game zoom (the ballista and scorpion are about 20 % oversize). Say so in the model docstring.
- Weathering is physical, not painted on: primer under paint, chipped edges, rust streaks on vertical faces, dust on up-facing surfaces and near the ground. The material library does this from geometry (section 6); do not fake it with extra geometry.
- Silhouette first. The game camera is zoomed out (a 2×2-tile gun is about 85 px wide on a phone at @1x). Each object needs one or two big, readable shapes (a long barrel, a tall arm, a cross of four arms, a big envelope) before any detail.
- Each gun must never be mistaken for another one. Write in the docstring what makes it unique (for example the scorpion: four arms in a cross, two strings, four legs, no hopper, big handwheels).
- Colour: muted, natural, military. Saturation comes only from materials that are really saturated (brass, copper, gold, red paint, blue enamel, ember glow). No pure black, no pure white surfaces.
- Light: one sun from the screen's upper left (shadows fall to the lower right), physical sky fill. It is set by the pipeline; never add lamps to a scene.

**What to avoid** (each of these was tried and rejected)

- Generic grey placeholders: enemies need faction colour, emblem and accents.
- Upgrades that only make the same part bigger, or that add props around the gun (sandbags, HESCO, nets) instead of changing the gun itself.
- The same upgrade on every gun (for example a shield on everything). The ballista never gets a shield.
- Muzzle flash on torsion and counterweight weapons (ballista, scorpion, trebuchet): they shoot by tension, not powder.
- Square, blocky structures where the user expects something thin and elegant (walls had to be thin, 0.5 to 0.65 m).
- Effects baked into sprites (camera filters, glare, flashes): effects are separate sprites, camera effects are only for stills.

## 3. Units, camera, scale and framing

Everything is modelled in **real metres** and rendered through **one camera**: the game's own 2:1 dimetric orthographic projection (elevation 30°, azimuth 45°), so one metre of ground is `pxPerMetre` wide along screen x and half of that along screen y. Never set up a camera, a light or render settings in a model or a render script; call `scene.build_stage("photoreal", size, samples, frame_m=..., ground=..., target_z=0.0, projection="ortho")`.

| Rule | Value | Where it lives |
| --- | --- | --- |
| Metres per game tile | 4 m | `METRES_PER_TILE` in `src/sim/content.ts` |
| Game pixels per metre | 16 at @1x, 32 at @2x, for **every** sheet (towers, enemies, projectiles, walls, ground) | `towers.json` → `pxPerMetre` |
| Render pixels per metre | towers and enemies `--ppm 32`; a smaller object may render at 64 and the packer scales it down | `render_sprites.py`, `render_fences.py` |
| Tower static art radius | `FOOTPRINT_M` ≤ size × 4 / 2 (1 tile 2 m, 2×2 4 m, 3×3 6 m) | checked by `tests/towerArt.test.ts` |
| Turning radius | `SWEEP_M`: nothing static may stand inside it | model constant |
| Enemy radius | `RADIUS_M` within 0.6 m of the game's `radius × 4` | checked by the same test |
| Tower directions | 32 aim frames; frame i aims at i × 2π/32 = `atan2(dy, dx)` in grid cells, 0 = grid +x (screen lower right), clockwise on screen | `render_sprites.py` |
| Fire animation | 32 directions, same angles | `--fire --fire-dirs 32` |
| Enemy headings | 16 | `--enemy --dirs 16` |
| Projectile headings | 32 for bolts (`ROUND_DIRS`), tumbling rounds use frames instead | `render_projectiles.py` |
| Grid to world | grid +x = world +X, grid +y = world −Y | `render_fences.py`, enemies |
| Model front | local +Y is the front of every gun and every vehicle | all models |
| Sun | upper left of the screen, 45° high, 0.545° disc; shadows fall lower right | `scene.sun_vector` |
| Exposure | −5.18 EV, AgX Medium High Contrast, white balance (0.907, 1, 1.118) | `scene.py` (calibrated on a grey card; never change) |

**Current game sizes** (in tiles, from `src/sim/content.ts`): guns — crossbow (самострел) 2, scorpion 2, zis3 2, greekfire 2, howitzer 3, trebuchet 3, railgun 3. Enemy radius — infantry 0.3, moto 0.35, truck 0.7, tank 0.8, apc 0.95, drone (airship) 1.0, fortress 1.85. A new object's size in tiles is decided with the user and the gameplay thread before modelling.

**Framing constants every model declares**

- `SPRITE_FRAME_M`: metres across the game render. Leave room for the longest part at every angle and for its shadow (howitzer 20 m, trebuchet uses `SPRITE_WH_M = (18, 18)` with `ANCHOR_FROM_BOTTOM_M = 5` because the arm is tall).
- `FRAME_M` and `TARGET_Z`: the photo-style preview frame and its centre height (review stills only).
- The anchor of every sprite is the object's **ground point** (the tile or unit centre at z = 0), at the frame centre unless `SPRITE_WH_M` moves it. The packer pads `sourceSize` so the anchor stays 0.5, 0.5.
- Shadows stay in the sprite's alpha (shadow catcher). Flying things (`FLYING = True`) render without a ground shadow; the game draws a dark ellipse at `flightHeightM`.

## 4. Repo map

All art code is in `art/pipeline/`; the game loads only `public/art/`. Renders go to `art/out/` (git-ignored); review images go to `/mnt/project-files/art-previews/<topic>/`.

| Path | What it is |
| --- | --- |
| `strelite_art/scene.py` | The one camera, physical sky, exposure, shadow catcher, `build_stage()`. Never edit per asset. |
| `strelite_art/geo.py` | `Kit`: every primitive a model may use (section 5). |
| `strelite_art/materials_photoreal.py` | The style В material library (`SPEC`), `stamp()`, `set_reference()`. Add new materials here only. |
| `strelite_art/terrain.py` | `Patch` (a tower's own soil that fades out), `Field`, `Terrain` (stills). |
| `strelite_art/fort.py` | Fortification kit (sandbags, HESCO, slab, logs, nets, crates). Rarely used now: props around guns were rejected. |
| `strelite_art/models/<model>.py` | One file per object. Guns: `ballista` (самострел), `scorpion`, `zis3`, `howitzer`, `greekfire`, `trebuchet`, `railgun`. Enemies: `infantry`, `bikers`, `truck`, `apc`, `tank`, `airship`, `fortress`. Structures: `fences`. Shared: `faction.py` (attackers), `defender.py` (player), `vehicle.py` (wheels, tracks). |
| `render_sprites.py` | Renders towers (`--ground patch`: base + 32 aims + fire frames + meta) and enemies (`--enemy`). |
| `render_projectiles.py` | Flying rounds per level (`build_round` in the model). |
| `render_effects.py` | Procedural 2D effects (muzzle flash, smoke, bursts, fire stream, rail beam). |
| `render_fences.py` | Wall pieces, `--pack`, `--review`. Pattern for any tile-assembled structure. |
| `render_ground.py` | Seamless ground tiles (`field`, `road`). |
| `render_portraits.py`, `pack_portraits.py` | Gun-only portraits for the Arsenal screen (add new guns to `FRAME_M` and to `render_portraits.sh`). |
| `pack_atlas.py` | Towers: base/aim decomposition, MaxRects packing, @2x + @1x sheets, `towers.json`; tables `NAMES`, `GAME_ID`, `SHOT_FX`. |
| `pack_enemies.py` | Enemies: sheets + manifest; tables `NAMES`, `GAME_ID`. |
| `ci_merge.py`, `render-queue.json`, `.github/workflows/render-art.yml` | Long renders on GitHub Actions (section 9). |
| `tools/level_sheet.py` | Side-by-side level review sheet on the field ground (section 8). |
| `tools/review_sheets.py`, `tools/camera_fx.py` | Older review sheets; whole-frame camera filter for stills only. |
| `export_gltf.py`, `tools/save_blend.py` | Kept for a later move to real-time 3D. Keep new models exportable: Kit primitives only, node empties named. |
| `public/art/towers.json` | The single manifest: towers, enemies, projectiles, effects, ground, fences. |
| `tests/towerArt.test.ts` | Repo test that checks the art against the game (ids, sizes, frames, scale). |

Read `art/README.md` for what the game does with the files, but trust this SOP for numbers: the README still mentions an old 12 m tile.

## 5. Model building strategy

A model is a Python module that builds the object from `Kit` primitives at real size, names its moving parts, and declares its framing constants. No imported meshes, no hand-made `.blend` files, no textures: the whole look comes from geometry plus the material library, which is what keeps every asset consistent.

**Build method, in this order**

1. **Research the real thing.** Find public dimensions (length, width, barrel, wheel size, line of fire) and write them in the docstring. The ZIS-3 and howitzer were built from published sizes; siege engines from historical proportions.
2. **Write the docstring first**: what it is (bg name in „“), real size, front = local +Y, the per-level ladder (section 7), what makes it unmistakable, what is static and what turns, the firing animation.
3. **Block out the silhouette** with boxes, tubes and beams at the right size. Render one test frame at game zoom and check it reads (section 8).
4. **Add structure**: every joint gets its fixing (bolts, bands, pins, lashings), every load has a support, every cable or hose runs from somewhere to somewhere.
5. **Add mechanism per level** as separate helper functions (`_hydraulics`, `_rammer`, `_windlass`, `_steam_crane`) gated by `if level >= n`.
6. **Add the traverse base and the ammo pile** (section 7).
7. **Add heraldry and accents** last: defender emblem on guns, faction kit on enemies.
8. **People** (crews, infantry, riders) come from `mhuman` (section 5a); **movement** for every enemy (section 5b).

**The `Kit` API** (`strelite_art/geo.py`; every call takes `name`, a material name and `parent=`)

| Call | Use it for |
| --- | --- |
| `k.empty(name, loc, parent)` | Nodes, pivots, groups you rotate (turret, slide, arm, wheel). |
| `k.box(name, (sx, sy, sz), loc, mat, rot, bevel=)` | Plates, planks, blocks, crates. Size is full size, `loc` is the centre. |
| `k.cylinder(name, r, h, loc, mat, segs, rot, radius_top=)` | Posts, drums, wheels, rivets, bolts; `loc` is the bottom centre. `radius_top` makes a cone. |
| `k.tube(name, p0, p1, r, mat, radius_end=)` | Any round bar between two points: barrels, pipes, stakes, slugs. |
| `k.beam(name, p0, p1, (w, h), mat, section_end=)` | Square timber or steel members between two points (frames, braces, trails). |
| `k.lathe(name, [(y, r), ...], mat, segs)` | Turned shapes around +Y: barrels with steps, muzzle swells, bottles, shells. |
| `k.plate(name, outline_yz, t, x, mat)` / `k.prism(name, outline_xz, t, mat, y=)` | Flat cut shapes: shields, gun shields, armour, cheeks. |
| `k.torus(name, R, r, loc, mat, rot)` | Hoops, bands, rings, ball races. |
| `k.ring(name, r, h, z, mat)` | A thin band around a cylinder. |
| `k.hose(name, points, r, mat)` | Cables, ropes, hoses through points (smooth curve). |
| `k.flag(name, w, h, loc, mat)` | Pennants. |
| `k.mesh(name, verts, faces)` | Last resort for a shape nothing else makes. |

Edges get a real 6 mm bevel automatically (`bevel=0.02` overrides in metres, `bevel=False` for tiny parts like rivets). Smoothing is by angle (35°), so hard-surface parts stay crisp. Reuse helpers from other models instead of copying: `ballista._beam`, `ballista._keep_world`, `trebuchet._ball`, `trebuchet.ground_spot`, `zis3._traverse_ground`, `faction.*`, `defender.emblem`.

**Tower contract** (what `render_sprites.py`, `pack_atlas.py` and the game expect)

```python
LEVELS = (1, 2, 3, 4, 5)
FRAME_M, TARGET_Z = 9.0, 1.2          # preview still
SPRITE_FRAME_M = 11.0                  # game render, metres across
SWEEP_M = 3.6                          # the turning parts stay inside
FOOTPRINT_M = 3.0                      # all static art stays inside; <= tiles * 4 / 2
STYLE = {1: dict(body="timber_raw", fit="iron_forged"), ...}   # materials per level
FIRE = [-0.55, -0.4, -0.26, -0.15, -0.07, -0.02]  # one value per frame (recoil m, angle...)
FIRE_FRAMES, RELEASE_FRAME, RELOAD_FROM, FIRE_FPS, LOOP = len(FIRE), 1, 2, 16, False
_RIG = {}                              # the nodes set_fire_frame moves

def build(style, level=1):
    k = Kit(style); s = STYLE[level]
    root = k.empty("<model>")
    _base(k, root, level, s); _ammo(k, root, level, s)      # static
    turret = k.empty("turret", (0, 0, 0), parent=root); turret["node"] = "turret"
    mp.set_reference(turret)          # wear patterns ride with the gun
    ...                               # the gun, built facing +Y
    m = k.empty("muzzle", tip, parent=turret); m["marker"] = "muzzle"
    set_fire_frame(0)                 # cocked / at rest before stamp()
    return root, turret

def ground(level):                    # the soil patch the sprite brings
    from ..terrain import Patch
    return Patch(r_solid=FOOTPRINT_M, r_out=FOOTPRINT_M + 0.6, r_bare=2.6, seed=97, ragged=0.5)

def key_fire_animation(scene): ...    # keyframe FIRE on _RIG nodes (linear), frame 0 = rest
def set_fire_frame(f, scene=None): ...
def build_round(k, parent, level): ...  # only if it throws a visible round (bolt, stone)
```

- Everything under `turret` turns; everything else is the static base. Nothing static may enter `SWEEP_M`.
- Name nodes `turret`, `elevating`, `recoil` where they exist, so the glTF exporter can find them later.
- Fire animation: 6 to 16 frames. `RELEASE_FRAME` is when the round leaves (muzzle point), `RELOAD_FROM` is where the reload part starts, `LOOP = True` for continuous weapons (самострел 6 frames at 24 fps, greek fire pump). Motion blur is added by the renderer.
- `materials_photoreal.stamp(scene)` runs after `build()`, with the gun at yaw 0 and at rest. Never build after stamping.

**Enemy contract**: `SPRITE_FRAME_M`, `LENGTH_M`, `RADIUS_M` (match the game's radius × 4 within 0.6 m), optional `FLYING = True` and `FLIGHT_HEIGHT_M`; `build(style, level=1)` returns `(root, root)`, the unit facing +Y. Groups (infantry squad, bikers) are one sprite with members placed by a table (`SQUAD`, `GROUP`). Every enemy also declares its movement (`MOVE_FRAMES`, `MOVE_KIND`, `MOVE_CYCLE_M` or `MOVE_FPS`, `set_move_frame`, section 5b); people are built with `mhuman` (section 5a).

**Structure contract** (walls and any tile-assembled piece, see `fences.py`): `build(material, piece)`, pieces anchored at the tile centre on the ground, patterns that repeat with a period dividing 2 m so neighbours join without a seam.

## 5a. Human figures

Every person in the game (infantry, riders, drivers, commanders in hatches, crews) is built with `strelite_art/mhuman.py`: a real human body on Blender's Rigify Human meta-rig. Never loose tubes and eggs, and no longer the procedural lofts of `human.py` (rejected twice: "toy soldiers", then "can be better"). This is the standard game pipeline (AAA and indie alike): a proper base mesh, a standard rig, automatic skin weights, clothes and gear on top, posed by controls, rendered to sprites.

**Body**: the MakeHuman hm08 base mesh (CC0, committed in `art/pipeline/assets/makehuman`, see its README), about 13 000 quads with a real face, hands and feet. `mh.Body(height, ancestry={...}, muscle, weight, height)` morphs it with MakeHuman's own targets (ancestry mix, muscle, weight, height, ideal proportions), then scales it to the exact height. Vary build and ancestry inside a group; muscle stays near average (0.5), or the uniform reads as a wetsuit.

**Skeleton**: `mh.build_rig(body)` creates the Rigify Human meta-rig (face and breast bones removed), fits every bone to the MakeHuman joint centres of that very body (rolls: Z toward the inside of the bend for arms and legs, palm-ward for fingers, as the meta-rig), and generates the Rigify control rig (IK and FK limbs, spine, fingers). About 0.3 s per man.

**Skin**: Blender's automatic weights (`ARMATURE_AUTO`, bone heat) bind the body to the DEF bones. About 3 s per man.

**Clothes**: shells grown out of the body itself (`Person.shell`): the same vertices pushed out along the normals, Taubin-smoothed so cloth hides anatomy, cut clean along planes at hems, cuffs, collar and boot tops (no quad-step edges). They carry the body's weights, so they never cut through it; the skin they cover is removed. `mh.field_uniform`: tunic with a short skirt below the belt, breeches, boot shafts, gauntlet gloves, cropped hair, eyebrows. Boot feet are a boot-last loft (rounded toe box, high instep, sole and heel), never the body's foot (toes show through).

**Value hierarchy** (readability at 2 to 4 px faces): lighter tunic (`tunic_slate`) over darker breeches (`breeches_dark`) and black boots; one saturated accent at chest level (the oxblood neckerchief and its tails); pale webbing so the straps read.

**Gear**: Kit parts built in the person's space (`Person.g`: front +Y, right +X), placed on the clothed surface with rays (`Person.surface`, `Person.hit`), so they sit on this body. Rigid parts ride on one DEF bone (`attach`, `bone_at` picks the bone under the part). Parts lying on the body (belt, Y-straps, scarf, boot feet) take blended weights from the nearest body vertices (`skin_near`) and bend with the cloth. Helmet fitted to the measured skull and worn tipped back so the face shows.

**Hands on things**: `hand_ik` targets on grip frames carried by the chest bone (finger direction and thumb direction per hand); fingers closed with the Rigify finger controls. Check the reach (IK stretch is off).

**Seated people** (riders, drivers, crews): `mh.Rider(person, seat, pegs, bars, lean, chest).pose()` puts the pelvis on the saddle (the torso control is moved after the lean so the hip joints land exactly on the seat point), the boots on the pegs (foot IK) and the hands on fixed grips (`mh.close_hands(person, grips, carry=None)`; a rifle uses `carry="DEF-spine.003"`). All points in the person's space, which is the machine's space when the person is parented to it. Kit and gear are the infantry's (`infantry._helmet`, `infantry._gear(pack=False)`); a slung carbine lies low and flat across the back.

**Faces**: eyes from the MakeHuman helpers (white, dark iris), eyebrows and moustache are thin hair shells, skin materials have subsurface scattering (`sss`).

**Review gate for people**: one man close up (300 px per metre, two members side by side on the field ground), a GIF of one man running, a GIF of the whole group at 2x, and old vs new at the game's real size. Then the full render.

## 5b. Movement animation

Every enemy moves visibly: people walk or run, wheels roll, tracks run, propellers turn. One format for all of them.

**Model contract** (beside the enemy contract):
```python
MOVE_FRAMES = 12          # frames per loop (people 12, wheels 4, tracks 4, propellers 4)
MOVE_KIND = "walk"        # walk | wheels | tracks | props
MOVE_CYCLE_M = 2.6        # metres travelled per loop (distance-driven), or
MOVE_FPS = None           # frames per second (time-driven, e.g. propellers)
def set_move_frame(f, scene=None): ...   # pose frame f of the loop
```
- People: `mh.Runner(person, cycle_m)` poses the Rigify controls per frame: feet on IK along a planted path (the stance foot moves back exactly `cycle_m` per cycle, so it never slides at any game speed), heel-off and toe roll, swing with heel kick and knee drive; hips bob (heights solved from what the legs can reach), lean, turn with the legs, sway over the stance foot; the chest counter-turns; the head keeps the eyes on the way ahead. `mh.pose_group` poses a whole squad with two scene updates per frame. Infantry: `MOVE_CYCLE_M = 1.85`, stance 37.5% of the cycle.
- Vehicles: one `vehicle.Motion(frames, cycle_m)` per model. Register wheels (`lug_wheel`, `motion.wheel(node, r)`), tracks (`track_links`, links that run along the belt path) and propellers (`motion.prop`). Pick the cycle so the last frame wraps exactly onto the first: a wheel turns by a whole number of its pattern repeats (8 rim holes: `cycle = 2*pi*r/8`), a track moves a whole number of links, a propeller turns one blade spacing.
- Tracked vehicles: `vehicle.TrackPlan(road_y, idler_yz, sprocket_yz, n_road, n_idler, n_sprocket, pitch)` lays a belt of separate links (shoe, grouser outside, guide horn inside, pin) round the idler, the road wheels and the sprocket (`vehicle.belt`: tangents and arcs; the top run rests on the road wheels when they stand higher than the sprocket and idler). It solves the link step so the belt closes on a whole number of links, and sizes every wheel from that step (radius = bolts or teeth × step / 2π), so one cycle of one link turns each wheel by exactly one pattern repeat. `PLAN.build(k, root, motion, x, width, ...)` makes wheels, links and suspension arms for one track; `MOVE_CYCLE_M = PLAN.step`. Used by `tank.py` (0.58 m tracks) and `fortress.py` (four 1.0 m tracks).
- Wire wheels (`vehicle.spoke_wheel`): 36 crossed spokes and 24 knobs repeat every 1/6 turn; `cycle = 2*pi*r/6`. Rings with an open middle (tyres, rims, bands) use `vehicle.ring_lathe` (no end caps).
- Propellers (`motion.prop(node, axis=1, symmetry=4)`) are time-driven: `MOVE_CYCLE_M = None`, `MOVE_FPS = 20`.
- Faceted armour (`vehicle.hull(k, name, sections, mat, parent)`): flat plates lofted through half cross-sections from the belly centre round to the roof centre; the same number of points in every section. Turrets and casemates too; a painted band round a faceted turret is another `hull` slab 2 cm proud.
- Parts laid on a sloped side are rotated about Y by `-sx * tilt` (sx = +1 on the right): the plate's up axis then leans inward with the side.
- No motion blur for movement frames (the frames are short steps; blur is only for firing).

**Render**: `render_sprites.py --enemy` renders `dir_NN_FF.png` (16 headings × MOVE_FRAMES) when the model has `MOVE_FRAMES`, else `dir_NN.png`. Quick looks: `tools/figure_test.py --model M --frames 0 1 2 ... --dir D`.

**Pack and manifest**: `pack_enemies.py` writes frames `<model>_NN_FF`, keeps `<model>_NN` (= frame 00) so the still still works, adds animations `<model>_NN_move`, and writes `enemies.<id>.move = {frames, kind, cycleM, fps, names: "<model>_DD_FF", animation: "<model>_DD_move"}`.

**How the game reads it**: distance-driven (`cycleM` set): `frame = floor((distanceTravelled / cycleM + phase) * frames) mod frames`; time-driven (`fps` set): `frame = floor(t * fps + phase * frames) mod frames`. `phase` is a random 0..1 per unit so units never move in step. A standing unit shows frame 00. Atlas size: keep each enemy sheet at or under 4096 px at @2x; fewer frames for big vehicles.

## 6. Material library

Models ask for materials **by name** from `materials_photoreal.SPEC`; they never create shaders. Every material ages from geometry (edges, cavities, up-facing, height) through the `pcoord`, `ocoord` and `rnd` attributes that `stamp()` writes, so it needs no UVs and survives joining and baking. Values follow measured references (albedo, F0 0.04, metals as metallic 1).

| Family | Names | Typical use |
| --- | --- | --- |
| Military paint | `paint_olive`, `paint_olive_worn`, `paint_barrel`, `paint_soot`, `paint_4bo`, `paint_4bo_worn`, `paint_4bo_barrel`, `paint_4bo_soot`, `paint_camo`, `paint_steel`, `paint_crate`, `paint_shell` | Defender guns (olive, 4BO green, camouflage, grey steel); `_soot` near muzzles. |
| Attackers' paint | `paint_enemy`, `paint_enemy_worn`, `paint_faction_red` | Slate body, oxblood bands of the Iron Concord. |
| Other paint and enamel | `paint_red`, `paint_white`, `paint_yellow`, `paint_blue`, `enamel_white` | Markings, emblems, gauge faces, level 5 of the railgun. |
| Iron and steel | `iron_forged`, `iron_black`, `steel_worn`, `gunmetal`, `track_steel`, `steel_cable`, `chrome` | Bands, plates, fittings, rails, tracks. |
| Precious and coloured metal | `bronze_old`, `brass`, `copper`, `silver`, `silver_satin`, `gold_trim` | Steampunk accents, level 4 and 5 trims. |
| Timber | `timber_raw`, `timber_tarred`, `timber_red`, `timber_honey`, `timber_oak`, `wood`, `log` | Siege engines, decks, crates, palisades. |
| Stone and ground | `stone`, `concrete`, `clay`, `dirt`, `dirt_fill`, `grass` | Platforms, flagstones, walls, jars, ground. |
| Cloth, rope, leather | `rope`, `hemp`, `burlap`, `canvas`, `flag`, `uniform`, `webbing`, `leather`, `geotextile`, `camo_net` | Lashings, skeins, sandbags, tilts, airship envelope, crews. |
| Rubber, glass, porcelain | `rubber`, `hose`, `glass`, `porcelain`, `screen` | Tyres, hoses, lenses, insulators. |
| Light emitters | `ember` (warm glow), `arc_glow` (electric) | Lamps, braziers, coils. Use sparingly. |
| People | `skin`, `boot` | Infantry, riders. |

**Rules**

- Use existing names first. A new material goes into `SPEC` with an existing builder (`painted`, `metal`, `plain`, `timber`, `wood`, `stone`, `cloth`, `concrete`, ...) and measured values, with a comment on what it is for.
- `painted` takes `wear` (chips), `dust`, `soot`, `primer` and `bare`; raise `wear` and `dust` for old or front-line things, lower them for polished level 5.
- The colour constants `OLIVE`, `GREEN_4BO`, `ENEMY_GREY`, `DUST`, `PRIMER`, `RUST` are the palette anchors. A new paint sits near them in tone.
- Camouflage must be visible at game zoom: large blotches, strong contrast (it was invisible at first and had to be enlarged).
- Ground and walls need dark joints to read against dirt (flagstones needed a dark mortar bed and 5 cm joints).
- Call `mp.set_reference(turret)` in every tower so wear patterns turn with the gun instead of swimming.

## 7. Upgrade levels

Every gun has **5 levels**, and each level must be told apart at a glance at game zoom. The user's rules (2026-11-17 and 2026-11-18):

1. **The weapon itself changes material** every level: rough and worn at 1, precious and polished at 5. Do not change the surroundings instead.
2. **Each level adds one new kind of mechanism** that explains the stronger shot and fits that weapon (a ratchet, then a reduction gear, then a crossbeam...). Never the same part made bigger.
3. **The traverse base under the gun changes every level** (pivot, then ring, then rollers on a track, then a toothed ring and pinion, then a turntable on a ball race).
4. **A small ammo pile on the ground** beside the gun changes every level (the rounds and their box get better).
5. **The silhouette stays** so the player still recognises the gun.
6. **Upgrades differ per gun.** Do not give every gun the same upgrade (no shield on the самострел).
7. **Big visible steps early.** The user rejected levels 1 to 3 of the howitzer as too similar; the fix was to hold features back: no tubes around the barrel at level 1, tubes at 2, muzzle brake from 3.

**Material ladders in use** (pick the one that fits the era of the new object)

| Era | L1 | L2 | L3 | L4 | L5 |
| --- | --- | --- | --- | --- | --- |
| Siege engines (самострел, scorpion, trebuchet) | pale raw timber, rope | tarred or red-painted timber, forged iron bands | dark or honey oak, black iron plates | blackened steel or iron plate, bronze | silver with gold |
| Powder guns (ZIS-3, howitzer) | worn green or olive | fresh paint | camouflage | grey steel | black steel and brass |
| Greek fire | clay jars, wood, leather | copper | bronze | armoured iron | silver and gold |
| Railgun | timber cradle, bare copper | iron housing | black iron armour | iron and bronze | white enamel, chrome, gold |

**Mechanism and base ladders as built** (copy the pattern, not the parts)

| Gun | New mechanism per level (1 → 5) | Traverse base per level (1 → 5) |
| --- | --- | --- |
| Самострел (`ballista`) | plain cranks; ratchet and pawl; reduction gear; crossbeam with extra ropes; steel leaf springs | pivot; tiller bar; toothed ring and crank; rollers under the yoke; gunner's ring walkway |
| Scorpion | handwheels on the axle; ratchet; reduction gear; worm screws on the skeins; block and tackle | pivot; index ring with pin; trail wheel on a rail; worm-driven gear ring; ball race |
| ZIS-3 | open sights; brass panoramic sight and quadrant; hydraulic accumulator with gauge; three-baffle brake, bigger shield; pneumatic rammer | spades in soil; plank deck; rollers on a timber track; toothed ring and pinion; steel turntable on ball race |
| Howitzer | plain telescope; recoil tubes, brass dial sight and aiming circle; hydraulics and muzzle brake; longer barrel, three baffles; steam crane | pads in soil; stone platform; ring rail and flanged shoes; toothed ring and drive shaft; turntable on ball race |
| Greek fire | hand pump; cauldron over a brazier; double-acting pump on a rocking beam; bellows, gauge, safety valve; bank of pressure flasks | swivel post; iron ring with push bars; wheels on a plank track; toothed ring and crank (4 and 5) |
| Trebuchet | rope lashings; iron bands; heavy iron straps; iron plate sheathing and chain sling; cast silver counterweight | turntable changes with the frame material |
| Railgun | Leyden jars and hand dynamo; capacitor cabinet and flywheel; water jacket and fins; booster coils; crown of discharge spheres | timber crib; iron pedestal; wheels on a ring rail; geared ring; ball race under a gilded ring |

**Ammo piles**: a plank box of stones → iron-bound stones → cast balls → spiked balls → silver orbs (trebuchet); slugs in a box, brighter metal each level (railgun); crates per level, a ready rack from 3, a growing heap of spent cases (ZIS-3). Place them with `trebuchet.ground_spot(r, deg)` inside `FOOTPRINT_M`, toward the camera side so they read.

**Rounds** that fly visibly get a matching look per level (`build_round`), for example field stone, iron-bound stone, cast ball, spiked ball, silver orb banded in gold.

**Non-gun objects** follow the same idea where levels exist: walls are one material per level (wood palisade, stone wall, steel wall). Enemies have one look (no levels) unless the user asks.

## 8. Review loop and approval gates

**No long render starts before the user has seen and approved a test render** (user, 2026-11-18: „Нека направи пробни първо преди пълния рендър“). A test costs minutes; a full render costs hours of Actions time.

**Standard test for a gun** (about 1 to 3 min per level on 4 CPUs):

```bash
cd art/pipeline
python3 render_sprites.py --model <m> --style photoreal --levels 1 2 3 4 5 --dirs 32 \
    --only-dir -1 22 --ground patch --ppm 64 --samples 16 --out /tmp/rev
python3 tools/level_sheet.py /tmp/rev/<m>/photoreal 22 /mnt/project-files/art-previews/<topic>/levels_<m>.jpg --scale 2
```

`-1` is the base layer, `22` one aim direction with the barrel toward the lower left and the sunlit side to the camera. The sheet shows all five levels side by side on the game's field ground. Look at it yourself first (Read the image), then post it.

**Other tests**

- Close-up of fine detail: same command with `--levels <n> --ppm 96` and a crop, for mechanisms the user should judge (the howitzer close-up of levels 1 to 4).
- Firing animation: `--levels 1 --only-dir -1 10 --fire --fire-dirs 32 --samples 16`, then assemble the `fire_10_FF.png` frames into a GIF.
- Enemy: `render_sprites.py --model <m> --style photoreal --enemy --dirs 16 --only-dir 2 10 --ppm 64 --samples 16`, shown next to an existing enemy for scale and faction look.
- Walls and structures: `render_fences.py --samples 16 --review out.jpg` assembles a straight run, a corner and a T on the field.
- All guns together: one aim of every gun side by side, to check the new one sits in the family.

**Self-check before posting** (answer each with the image open)

- [ ] Reads at game zoom: shrink the sheet to @1x size (half) and the object is still recognisable and distinct from every other object.
- [ ] Each level is clearly different from the one before, by material and by one new mechanism.
- [ ] Nothing floats, nothing intersects visibly, every part is held by something.
- [ ] Static art stays inside `FOOTPRINT_M`, nothing static inside `SWEEP_M`, the shadow is not cut by the frame.
- [ ] Colours sit in the palette: no new saturated colour except real metal or paint.
- [ ] Heraldry is in place (defender emblem on guns, Iron Concord accents on enemies).
- [ ] No muzzle flash planned for weapons that do not burn powder.

**Posting**: put previews in `/mnt/project-files/art-previews/<topic>/` with a version suffix (`levels_samostrel_v4.jpg`), attach them, and say in two or three Bulgarian lines what each level adds. Ask one clear question if there is a choice to make.

**What is the user's call** (ask, do not decide): a new object's role and size in tiles, its look direction when the ask is vague, anything that changes the world or the faction look, and the go for every long render. **What is yours**: construction details, materials within the ladders, framing constants, mechanism choices that fit the rules (state them in the review message).

## 9. Rendering

Run anything under about 20 minutes **in the session**; run every full tower or enemy render **on GitHub Actions**. The cloud container is reclaimed when the session is idle (30 to 90 min), which kills background Blender jobs; self-scheduled keep-alive check-ins did not save them.

**Setup in the session**: `pip install bpy==5.3.0 numpy pillow` (Blender as a Python module, Cycles on CPU). blender.org downloads are blocked; pip works.

**Full render settings** (keep identical for every asset of a kind)

| Asset | Command (from `art/pipeline`) | Time per job on Actions |
| --- | --- | --- |
| Tower level | `render_sprites.py --model M --style photoreal --levels L --dirs 32 --fire --fire-dirs 32 --fire-samples 20 --ground patch --ppm 32 --samples 32`, then `pack_atlas.py --models M --levels L` | 25 to 35 min (самострел), about 1 h (scorpion, ZIS-3), about 2.5 h (trebuchet, 16 fire frames) |
| Enemy | `render_sprites.py --model M --style photoreal --enemy --dirs 16 --ppm 32 --samples 32`, then `pack_enemies.py --models M` | under 1 h |
| Projectiles | `render_projectiles.py --model M` (all levels) | minutes |
| Walls | `render_fences.py --samples 32 --pack` | about 2 min in the session |
| Effects | `render_effects.py` | seconds in the session |
| Ground | `render_ground.py --kind field\|road` | minutes in the session |

**GitHub Actions workflow** (`.github/workflows/render-art.yml`, approved by the user 2026-11-18)

1. On your own `claude/**` branch, edit `art/pipeline/render-queue.json`: set `"branch"` to that branch name exactly, and list the work: `"towers": {"<model>": [1, 2, 3, 4, 5]}`, `"projectiles": ["<model>"]`, `"enemies": ["<model>"]`. Use the art model names (`ballista`, `bikers`, `airship`), not the game ids.
2. Commit and push. The `plan` job builds one job per tower level, projectile set and enemy; each renders and packs on its own runner (350 min limit) and uploads its files.
3. The `merge` job runs `ci_merge.py`, which merges every fragment into `public/art` and `towers.json` (tower levels merged by level, game ids applied), then `github-actions[bot]` commits „art: rendered sprite atlases (render-art workflow)“ to your branch. `git pull` before your next commit.
4. When the run is done, empty the lists again (keep `"branch"`), so the next edit queues only new work.

Rules: pushing the queue again cancels the run in progress on that branch. The queue renders only on the branch it names, so a merge that carries it elsewhere does nothing (a full re-render once started on another thread's branch that way; fixed 2026-11-18). Follow a run with the GitHub Actions API or `gh api repos/avoynov/strelite-game/actions/runs/<id>/jobs`; read a failed job's log, fix, and re-queue only what failed.

**Local runs**: pass `--resume` to continue after an interruption; it skips frames already on disk.

## 10. Packing and manifest formats

Every sheet is a PixiJS spritesheet (`.json` + lossless-alpha `.webp`, quality 92) at two densities: **@2x = 32 px per metre, @1x = 16 px per metre**. Frames are trimmed and packed with MaxRects; `sourceSize` keeps the full frame so the anchor (0.5, 0.5) stays on the ground point. `pack_atlas.py` and `pack_enemies.py` treat the render as @2x, so towers, enemies and projectiles **must render at `--ppm 32`**; a script that renders at another ppm must scale to 32 and 16 itself (`render_fences.py` does).

| Asset | Files | Frame names | Manifest key in `towers.json` |
| --- | --- | --- | --- |
| Tower level | `towers/<id>_L<n>@1x\|@2x` | `<id>_L<n>_base`, `<id>_L<n>_aim_00..31` | `towers.<id>.levels[]`: `level`, `sheet`, `base`, `aim`, `footprintRadiusM`, `sweepRadiusM`, `muzzlePx[32]`, `muzzleM[32]`, `fire` |
| Fire animation | `towers/<id>_L<n>_fire_DD@1x\|@2x` (one sheet per direction, loaded on demand) | `<id>_L<n>_fire_DD_FF`, FF from 01 | `levels[].fire`: `sheet`, `animation`, `dirs`, `frames`, `fps`, `releaseFrame`, `reloadFrom`, `loop`, `use` |
| Tower meta |  |  | `towers.<id>`: `name {bg, en}`, `shotEffects`, `placeholder` |
| Enemy | `enemies/<model>@1x\|@2x` | `<model>_00..15` | `enemies.<id>`: `name`, `sheet`, `frames`, `directions`, `lengthM`, `radiusM`, and `flying`, `flightHeightM`, `shadow` for flyers |
| Projectile | `projectiles/<model>@1x\|@2x` | `<model>_L<n>_round_FF` | `projectiles.<id>`: `sheet`, `levels`, `frames`, `fps`, `radiusM`, `animation`, `headings`, `note` |
| Effect | `effects/<name>@1x\|@2x` | `<name>_FF` | `effects.<name>`: `sheet`, `frames`, `count`, `fps`, `anchor`, `blend`, `loop`, `lengthM` |
| Wall | `fences/<material>@1x\|@2x` | `<material>_post\|px\|nx\|py\|ny` | `fences.<material>`: `name`, `sheet`, piece frame names, `heightM`, `thicknessM`, `frameM`; plus `fencesNote` |
| Ground | `ground/<kind>@1x\|@2x.webp` | (image) | `ground.<kind>`: `image`, `sizePx1x`, `metres`, `note` |

**How tower layers work**: the game draws `base`, then `aim_NN` on top. The aim frame is not the gun cut out: it is the exact difference between the complete render and the base, so it carries the gun's shadow on the ground and is missing where static parts hide the gun. The packer prints the reconstruction error per atlas; it must stay small.

**Tables to update for a new object** (all in `art/pipeline/`)

- `pack_atlas.NAMES` / `pack_enemies.NAMES`: the `bg` and `en` display names.
- `pack_atlas.GAME_ID` / `pack_enemies.GAME_ID`: the model name → the game id where they differ (`ballista` → `crossbow`, `bikers` → `moto`, `airship` → `drone`). Keep `enemies.drone` pointing at the airship: the gameplay thread depends on it.
- `pack_atlas.SHOT_FX`: effects played on a shot. Default is `muzzle_flash` + `muzzle_smoke`; torsion and counterweight weapons get `[]`, greek fire `fire_stream`, railgun `rail_charge` + `rail_beam`.
- `render_portraits.FRAME_M` and `render_portraits.sh` `MODELS`: the Arsenal portrait of a new gun.

Never hand-edit `towers.json`; it is written only by the packers and `ci_merge.py`, which keep the other entries.

## 11. Handoff to gameplay, ids and tests

Art is finished only when the game can load it and the repo tests pass. The gameplay thread is „Build 7 guns and 7 enemies“; message it there, not the older Fable gameplay thread.

1. **Agree ids and sizes first.** Before modelling, ask the gameplay thread (or read `src/sim/content.ts`) for the game id, size in tiles (towers) or radius in tiles (enemies). If the art needs a different size, say why and let the user decide (the самострел went from 1 tile to 2×2 that way).
2. **Run the repo checks** before every PR: `npx vitest run`, `npx tsc --noEmit`, `npx eslint .`. `tests/towerArt.test.ts` fails when a tower id is not in `TOWERS`, when `footprintRadiusM` exceeds size × 4 / 2, when an enemy id is not in `ENEMIES` or its `radiusM` is more than 0.6 m from radius × 4, when frames are missing at either density, or when wall frames are not at the towers' pixels per metre.
3. **PR**: from your `claude/**` branch to `main`, titled by what the player gets. List the new ids, frames and manifest keys, the previews, and what the gameplay side must do. If a test fails only because the game's numbers are behind the art, say so in one PR comment and ask the gameplay thread to change them.
4. **Handoff message to the gameplay thread**: new ids (art model → game id), files and frame names, anchors and draw order, `shotEffects`, flying height and shadow rules, anything loaded on demand (fire sheets per direction), and which existing keys must not be renamed.
5. Never edit the gameplay thread's files without telling it. A one-line type addition in `src/render/towers/towerArt.ts` for a new manifest field is fine if you tell them.

Preview and source locations other threads can rely on: `/mnt/project-files/art-previews/` (siege, style-v, fences), `.blend` sources in `/mnt/project-files/art-sources/style-v/`, this SOP in `art/SOP.md` and `/mnt/project-files/art-briefs/art-generation-sop.md`.

## 12. Checklists per asset type

Start every new object by copying the closest existing model and keeping its structure.

**New gun (tower)** — copy `railgun.py` (shortest, clean) or the gun closest in kind (siege engine: `ballista.py` or `scorpion.py`; powder gun: `zis3.py`; heavy: `howitzer.py` or `trebuchet.py`).

- [ ] Size in tiles and game id agreed; `FOOTPRINT_M` ≤ tiles × 2 m.
- [ ] Docstring: real size, front +Y, 5-level ladder (material + mechanism + base + ammo), what makes it unique, firing animation.
- [ ] `STYLE` per level from a material ladder (section 7).
- [ ] Static base with a different traverse per level; ammo pile per level.
- [ ] `turret` node, `muzzle` marker, `mp.set_reference(turret)`, `_RIG`, `FIRE`, `set_fire_frame`, `key_fire_animation`.
- [ ] `ground(level)` patch; `SPRITE_FRAME_M`, `SWEEP_M`.
- [ ] `build_round` if the round is visible in flight.
- [ ] Defender emblem where a marking belongs.
- [ ] Level review sheet approved by the user; firing GIF approved.
- [ ] `NAMES`, `GAME_ID`, `SHOT_FX` updated; portrait added to `render_portraits`.
- [ ] Queued on Actions (towers 1–5, projectiles), bot commit pulled, tests green, PR, handoff.

**New enemy** — copy `apc.py` (wheeled), `tank.py` (tracked), `infantry.py` or `bikers.py` (groups), `airship.py` (flying), `fortress.py` (boss).

- [ ] Game id and radius agreed; `RADIUS_M` within 0.6 m of radius × 4.
- [ ] Faction look: `paint_enemy` / `paint_enemy_worn`, oxblood bands, brass, emblem on visible faces, one or two of lamp, gauge, stack, pennant.
- [ ] `SPRITE_FRAME_M` fits the longest axis plus shadow at every heading (edge check, section 13); `FLYING` and `FLIGHT_HEIGHT_M` for flyers.
- [ ] People on `mhuman` (section 5a), never loose primitives; riders with `mh.Rider`.
- [ ] Movement (section 5b): frames that wrap exactly; GIF of the movement approved.
- [ ] Atlas at or under 4096 px at @2x: frames × trimmed frame area × 1.15 ≤ 16.7 Mpx (the boss uses 3 movement frames).
- [ ] Test at two headings next to an existing enemy, approved.
- [ ] `pack_enemies.NAMES`, `GAME_ID`; queued; tests; handoff.

**New projectile or effect** — projectiles come from the gun's `build_round` (`render_projectiles.py`, `ROUND_DIRS = 32` for bolts that fly nose first, tumbling frames for stones). Effects are procedural 2D in `render_effects.py`: add a function, a manifest entry with `anchor`, `blend` (`add` for light, `normal` for smoke and debris), `fps`, `count`; check both densities.

**New wall, building or tile-assembled structure** — copy `fences.py` + `render_fences.py`.

- [ ] Thin and elegant, not blocky; height and thickness in real metres.
- [ ] Pieces anchored at the tile centre; patterns repeat with a period dividing 2 m.
- [ ] `--review` sheet with a run, a corner and a T, approved.
- [ ] Packed at 32 / 16 px per metre with `frameM` in the manifest; draw-order note for the game.

**New building (base)** — `models/building.py` is the construction kit (masonry block by block with openings cut, log and plank walls, gable roofs of real shingles on a boarded deck, windows, doors, flag mast, crates, barrels). `render_buildings.py` renders one static frame per level (`SPRITE_WH_M`, `ANCHOR_FROM_BOTTOM_M`, own soil patch), `--review` makes the level sheet, `--pack` writes `buildings/<id>@1x|@2x`, frames `<id>_L<n>`, manifest key `buildings`. Doors and emblems face -Y and +X (the faces the camera sees). Each level: new material and one new machine; the silhouette stays.

Built so far: `hq`, `lab`, `muster` (Военно свикване; its mark is a military horn on a post or tower at the +X side, from an ox horn to a crown of gilded fanfares), `arsenal` (two crossed barrels over the gate, a lifting rig in the yard), `treasury` (a big open trough heaped with gold coins, the mound growing with the level; the mound is a displaced grid plus hundreds of loose coins in `gold_coins`, a dust-free gold). Give every new building one mark of this kind that reads at game zoom and grows with the level, so the player knows what it is for without a label.

**Damage states (buildings and guns)** — `strelite_art/damage.py`, applied after `build()` and before `stamp()`; never model a damaged version by hand, and never lay debris in a heap by formula (it reads as Lego).

- The destroyed region is a lumpy blob (`damaged`: the upper front-right corner, the roof above it falls in so light reaches the room; `wreck`: a blast on one side of a gun) or a noisy height field (`rubble`: ragged stumps, one corner left higher). Pieces under 1.5 m (blocks, planks, shingles, panels, gun parts) come out whole when their centre is inside, so masonry breaks along its joints; bigger pieces are cut by the same shape with a boolean. Hidden layers (mortar, decks) are cut a little wider so they never show.
- The pieces taken out are the debris: stone blocks split two or three times along random planes, planks and beams snap with slanted ends, plus gravel and broken rafters. Only part of it stays (about half for `damaged`, 40% for `rubble`, 60% for `wreck`): a ruin has lost material that was carried off, burnt or blown away, so never keep 100%. Everything falls under Bullet rigid bodies (`_simulate`, with a short outward blast for `damaged` and `wreck`) onto a ragged dust bed, the floor and the remaining walls. The inner `core` is removed so the room shows through the breach.
- A wrecked gun never stays standing or balanced: the gun and its timber or metal stand (masonry stays) are split into 3 to 5 chunks (k-means on part centres, then split again where nothing touches). One chunk and 40% of the small pieces are gone. Each chunk is set down on its most stable face (`_stable_rest`: the convex hull face that puts the real centre of mass lowest), thrown a little away from the blast and clear of the pedestal, then settles with the debris.
- Soot fades out from the hit (`stone_soot`, `timber_charred`, `paint_soot`). `occupied` = `damage.occupy()` then `damaged`.
- A model with contents that must not be cut defines `damage_hook(scene, state, info, phase)`; the treasury rebuilds its gold and returns the coins, which fall with the debris.
- Loose small things (coins) are always dropped with physics and settle on a low solid body, never laid on a surface or made as one flowing mesh.
- Render: `render_buildings.py --states normal damaged rubble occupied`, `render_wrecks.py`; about 2.5 hours locally for everything (the treasury coins are the slow part).

**Own units (allies)** — the player's units reuse an enemy model with the defenders' paint swapped in (`models/raiders.py`: 4BO green, `tunic_olive`, `cloth_blue`, defender emblem, blue pennant). Pack with `pack_enemies.py`; models in its `ALLIES` set go to the manifest key `allies`, not `enemies` (the art test checks every enemy id against the game).

**New ground** — `render_ground.py --kind ... --name ...`: seamless in both screen directions, same pixels per metre, calm enough that units read on top of it.

## 13. Gotchas and lessons learned

| Symptom | Cause | Fix |
| --- | --- | --- |
| Asset twice as big as the guns in the game | Packed at a different px per metre than 32/16 | Render towers and enemies at `--ppm 32`; other scripts scale to 32/16; the wall test checks `frameM` |
| Full re-render on another thread's branch | `render-queue.json` carried there by a merge | Queue names its `"branch"`; workflow renders nothing elsewhere |
| Long local render vanished | Container reclaimed while the session was idle | Long renders go to Actions; local runs use `--resume` |
| CI collect step failed on a job that changed no files | `grep -v` exits 1 on no input under `set -o pipefail` | `{ grep -v ... \|\| true; }` |
| Camouflage invisible at game zoom | Blotches too small and too similar | Larger noise, lower thresholds, stronger colours |
| Flagstones invisible against soil | Joints too thin, mortar too light | Dark mortar bed (`iron_black`), 5 cm joints, stone not concrete |
| Levels look the same | Features present from level 1 | Hold features back to later levels; one new mechanism per level |
| `NameError` after a search-and-replace in a model | A replace changed a string constant (`paint_soot`) | Re-run the test render after any bulk edit |
| `request_decision` refused | An option's consequence over 200 bytes (Cyrillic is 2 bytes a letter) | Keep Bulgarian consequences under about 90 letters |
| `ModuleNotFoundError: mathutils` in a pack step | A model module imported without `bpy` | `import bpy` before importing models |
| Wear patterns swim when the gun turns | `set_reference` missing | `mp.set_reference(turret)` before `stamp()` |
| Noise differs between frames | Seed not fixed | `scene.cycles.seed = 1` (render scripts already do it) |
| PIL float frames turn to noise | `Image.fromarray(..., "F")` with float64 | Convert to float32 first |
| Test fails on a size that the game sets | Game numbers behind the art | One PR comment, ask the gameplay thread to change the number; the user decides real conflicts |
| Pushing a workflow file blocked | Auto mode needs explicit user approval for CI changes | Ask the user to approve the exact action and branch in the thread |
| Soldiers read as toys ("can be better") | Bodies from tubes and lofts | MakeHuman body on the Rigify Human meta-rig, clothes grown from the body (section 5a) |
| A belt or strap stretches toward the hand when an arm moves | Its weights came from hand vertices hanging beside it in the rest pose | `skin_near` skips arm-dominated body vertices (default) |
| Wire wheels look like solid discs | `k.lathe` caps both ends of the profile | `vehicle.ring_lathe` for tyres, rims and bands |
| A door or band on a sloped side sticks out at the top | Rotated about Y by `+sx * tilt` | `-sx * tilt`: the plate's up axis must lean in with the side |
| Enemy frames do not trim, atlas far too big | The shadow catcher leaves a faint, noisy alpha haze over the whole frame | `pack_enemies.trim_haze`: drops alpha under 12/255 (`HAZE`) and everything outside the box of alpha 32/255 and over (`SOLID`) grown by 8 px |
| Shadow cut off straight at the frame edge | `SPRITE_FRAME_M` too small for the long low-sun shadow (barrels, masts, tarp bodies) | Render all 16 headings at 2 samples and check that no alpha 32/255 or over touches the outer 2 px; frames are trimmed, so a larger frame costs only render time (fortress 30 m, truck and APC 13 m) |
| Track links jump at the loop | Belt length not a whole number of links, or wheels not sized from the step | `vehicle.TrackPlan` solves the step and sizes the wheels |
| Slung rifle points forward over a leaning rider | Rifle slung muzzle up while the torso leans 0.5 rad | Sling it low and flat across the back |

**Working habits that kept quality high**

- Look at every render yourself before posting it; describe what you see, not what you intended.
- One review image per question; version the file names; keep old versions for comparison.
- Commit the model before a long render, so the bot commit lands on top of known code.
- Keep the user's decisions in project memory the turn you learn them (sizes, looks, rejections), with the date.
