"""Render isometric sprites for a model.

Usage:
  python3 render_sprites.py --model cannon --style stylized --levels 1 2 3 --dirs 8 --out ../out

Output: <out>/<model>/<style>/L<level>/dir_<NN>.png (RGBA, shadow kept in alpha).
Direction NN aims the turret at yaw = NN * 360/dirs degrees, counter-clockwise
from world +Y. dir_00 points toward the upper-right of the screen.

Game sprites of the photoreal style (`--ground patch`) are rendered in layers:
  python3 render_sprites.py --model howitzer --style photoreal --levels 1 2 3 \
      --dirs 32 --ground patch --ppm 32 --samples 96 --out ../out
writes base.png (everything that never moves, with the gun hidden), aim_NN.png
(the complete tower aiming at game angle NN * 2*pi/dirs) and meta.json into
<out>/<model>/photoreal/L<level>/. pack_atlas.py turns these into game atlases.
Here the camera is the game's own orthographic 2:1 projection and frame NN aims
at the angle the game uses: atan2(dy, dx) in grid cells, 0 = +x (screen
lower-right), growing clockwise on screen.
"""
import argparse
import importlib
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from strelite_art import materials, scene as stage  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="cannon")
    ap.add_argument("--style", choices=stage.STYLES, default="stylized")
    ap.add_argument("--levels", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--dirs", type=int, default=8)
    ap.add_argument("--only-dir", type=int, nargs="*", help="render only these direction indices")
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--ground", choices=("catcher", "terrain", "patch"), default="catcher",
                    help="catcher: transparent sprite + shadow; terrain: real soil (photo "
                         "stills); patch: layered game sprites on their own soil patch")
    ap.add_argument("--ppm", type=float, default=32.0, help="patch mode: pixels per metre")
    ap.add_argument("--resume", action="store_true",
                    help="patch mode: skip frames that are already on disk")
    ap.add_argument("--frame", type=float, default=None,
                    help="patch mode: metres across the render (default: the model's SPRITE_FRAME_M)")
    ap.add_argument("--lens", type=float, default=stage.PHOTO_LENS_MM, help="photoreal lens, mm")
    ap.add_argument("--tag", default="", help="suffix for the output file name")
    ap.add_argument("--fire", type=int, nargs="*",
                    help="also render these firing-animation frames (all if no number) as fire_DD_FF.png "
                         "for the directions in --fire-dirs; the model must define FIRE_FRAMES")
    ap.add_argument("--fire-dirs", type=int, default=16, help="directions of the firing animation")
    ap.add_argument("--fire-samples", type=int, default=None,
                    help="samples for the firing frames (motion-blurred, so fewer are enough)")
    ap.add_argument("--enemy", action="store_true",
                    help="moving unit: the whole model turns; writes <out>/enemies/<model>/dir_NN.png")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "out"))
    a = ap.parse_args(argv)

    model = importlib.import_module(f"strelite_art.models.{a.model}")
    if a.enemy:
        render_enemy(model, a)
        return
    if a.style == "photoreal" and a.ground == "patch":
        for level in a.levels:
            render_tower_layers(model, a, level)
        return
    for level in a.levels:
        materials.clear_cache()
        frame_m = getattr(model, "FRAME_M", stage.ORTHO_SCALE)
        scene = stage.build_stage(a.style, a.size, a.samples, frame_m=frame_m,
                                  ground=a.ground if a.style == "photoreal" else "catcher",
                                  lens_mm=a.lens, target_z=getattr(model, "TARGET_Z", None))
        _, turret = model.build(a.style, level)
        if a.style == "photoreal":
            from strelite_art import materials_photoreal
            materials_photoreal.stamp(scene)
        if a.style == "photoreal" and a.ground == "terrain":
            from strelite_art.terrain import Terrain
            Terrain(frame_m * 3.1).build(scene)
        out_dir = os.path.join(a.out, a.model, a.style, f"L{level}")
        os.makedirs(out_dir, exist_ok=True)
        dirs = a.only_dir if a.only_dir is not None else range(a.dirs)
        for d in dirs:
            turret.rotation_euler = (0, 0, math.radians(d * 360 / a.dirs))
            scene.render.filepath = os.path.join(out_dir, f"dir_{d:02d}{a.tag}.png")
            t = time.time()
            bpy.ops.render.render(write_still=True)
            print(f"[render] {a.model} {a.style} L{level} dir {d}: {time.time() - t:.1f}s",
                  flush=True)


def render_tower_layers(model, a, level):
    """Layered game sprites: base.png + aim_NN.png + meta.json (see module docstring)."""
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector

    from strelite_art import materials_photoreal
    from strelite_art.terrain import Patch
    materials.clear_cache()
    wh = getattr(model, "SPRITE_WH_M", None)
    frame_m = a.frame or (wh[0] if wh else model.SPRITE_FRAME_M)
    size = int(round(frame_m * a.ppm / 2)) * 2
    patch = model.ground(level)
    scene = stage.build_stage("photoreal", size, a.samples, frame_m=frame_m * (1.6 if wh else 1.0),
                              ground="patch", target_z=0.0, projection="ortho",
                              catcher_hole=getattr(patch, "catcher_hole", patch.r_solid - Patch.CATCHER_INSET))
    size_y = size
    if wh:      # taller-than-wide frame: tower ground point ANCHOR_FROM_BOTTOM_M above the bottom
        size_y = int(round(wh[1] * a.ppm / 2)) * 2
        cam = scene.camera
        cam.data.sensor_fit = "HORIZONTAL"
        cam.data.ortho_scale = frame_m
        scene.render.resolution_y = size_y
        up = cam.rotation_euler.to_matrix().col[1].normalized()
        cam.location = cam.location + up * (wh[1] / 2 - model.ANCHOR_FROM_BOTTOM_M)
    scene.cycles.seed = 1                       # same noise in every frame: static pixels match
    scene.render.use_persistent_data = True
    _, turret = model.build("photoreal", level)
    materials_photoreal.stamp(scene)
    patch.build(scene)
    out_dir = os.path.join(a.out, a.model, "photoreal", f"L{level}")
    os.makedirs(out_dir, exist_ok=True)

    gun, stack = [], [turret]
    while stack:
        o = stack.pop()
        gun.append(o)
        stack.extend(o.children)
    muzzle = next((o for o in gun if o.get("marker") == "muzzle"), None)

    def shoot(name):
        scene.render.filepath = os.path.join(out_dir, name)
        if a.resume and os.path.exists(scene.render.filepath) and os.path.getsize(scene.render.filepath) > 0:
            return
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"[render] {a.model} L{level} {name}: {time.time() - t:.1f}s", flush=True)

    only = a.only_dir
    if only is None or -1 in only:
        for o in gun:
            o.hide_render = True
        shoot("base.png")
        for o in gun:
            o.hide_render = False
    bpy.context.view_layer.update()
    ndc0 = world_to_camera_view(scene, scene.camera, Vector((0, 0, 0)))
    anchor_px = [round(ndc0.x * size, 2), round((1 - ndc0.y) * size_y, 2)]
    aims = []
    for i in range(a.dirs):
        aim = 2 * math.pi * i / a.dirs                  # game angle: atan2(dy, dx) in grid cells
        turret.rotation_euler = (0, 0, -aim - math.pi / 2)
        if hasattr(model, "set_aim"):                   # parts that turn with the yaw (e.g. gears)
            model.set_aim(-aim - math.pi / 2)
        bpy.context.view_layer.update()
        entry = {"index": i, "aimRad": round(aim, 6)}
        if muzzle is not None:
            w = muzzle.matrix_world.translation
            ndc = world_to_camera_view(scene, scene.camera, w)
            entry["muzzlePx"] = [round(ndc.x * size, 2), round((1 - ndc.y) * size_y, 2)]
            entry["muzzleM"] = [round(w.x, 3), round(-w.y, 3), round(w.z, 3)]   # grid x, y, height
        aims.append(entry)
        if only is None or i in only:
            shoot(f"aim_{i:02d}.png")
    fire = None
    if a.fire is not None and hasattr(model, "set_fire_frame"):
        frames = a.fire or list(range(1, model.FIRE_FRAMES + 1))
        model.key_fire_animation(scene)
        if a.fire_samples:
            scene.cycles.samples = a.fire_samples
        scene.render.use_motion_blur = True
        scene.render.motion_blur_shutter = 0.5
        for owner in (scene.render, scene.cycles):          # shutter closes at the frame
            if hasattr(owner, "motion_blur_position"):
                owner.motion_blur_position = "END"
        for i in range(a.fire_dirs):
            if only is not None and i not in only:
                continue
            aim = 2 * math.pi * i / a.fire_dirs
            turret.rotation_euler = (0, 0, -aim - math.pi / 2)
            if hasattr(model, "set_aim"):
                model.set_aim(-aim - math.pi / 2)
            for f in frames:
                model.set_fire_frame(f, scene)
                shoot(f"fire_{i:02d}_{f:02d}.png")
        model.set_fire_frame(0, scene)
        scene.render.use_motion_blur = False
        fire = {"dirs": a.fire_dirs, "frames": model.FIRE_FRAMES, "fps": model.FIRE_FPS,
                "releaseFrame": model.RELEASE_FRAME, "reloadFrom": model.RELOAD_FROM,
                "loop": getattr(model, "LOOP", False)}
    meta = {
        "model": a.model, "level": level, "dirs": a.dirs, "pxPerMetre": a.ppm,
        "frame": [size, size_y], "anchorPx": anchor_px, "fire": fire,
        "footprintRadiusM": getattr(model, "FOOTPRINT_M", None),
        "sweepRadiusM": getattr(model, "SWEEP_M", None),
        "aims": aims,
    }
    with open(os.path.join(out_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)


def render_enemy(model, a):
    """A moving unit in `--dirs` headings: dir_NN.png faces game angle NN * 2*pi/dirs
    (atan2(dy, dx) in grid cells, 0 = screen lower-right), shadow kept in alpha."""
    from strelite_art import materials_photoreal
    materials.clear_cache()
    frame_m = a.frame or model.SPRITE_FRAME_M
    size = int(round(frame_m * a.ppm / 2)) * 2
    flying = getattr(model, "FLYING", False)        # no ground shadow: the game draws one
    scene = stage.build_stage("photoreal", size, a.samples, frame_m=frame_m,
                              ground="none" if flying else "patch",
                              target_z=0.0, projection="ortho", catcher_hole=0.0)
    scene.render.film_transparent = True
    scene.cycles.seed = 1
    scene.render.use_persistent_data = True
    root, _ = model.build("photoreal", 1)
    materials_photoreal.stamp(scene)
    out_dir = os.path.join(a.out, "enemies", a.model)
    os.makedirs(out_dir, exist_ok=True)
    # movement animation (SOP "Movement animation"): MOVE_FRAMES frames per heading,
    # dir_NN_FF.png; models without it render one still per heading, dir_NN.png
    move_frames = getattr(model, "MOVE_FRAMES", 0)
    for i in range(a.dirs):
        if a.only_dir is not None and i not in a.only_dir:
            continue
        heading = 2 * math.pi * i / a.dirs
        root.rotation_euler = (0, 0, -heading - math.pi / 2)
        for f in range(max(move_frames, 1)):
            if move_frames:
                model.set_move_frame(f, scene)
                name = f"dir_{i:02d}_{f:02d}.png"
            else:
                name = f"dir_{i:02d}.png"
            scene.render.filepath = os.path.join(out_dir, name)
            if a.resume and os.path.exists(scene.render.filepath) and os.path.getsize(scene.render.filepath) > 0:
                continue
            t = time.time()
            bpy.ops.render.render(write_still=True)
            print(f"[render] enemy {a.model} {name}: {time.time() - t:.1f}s", flush=True)
    meta = {"model": a.model, "dirs": a.dirs, "pxPerMetre": a.ppm, "frame": [size, size],
            "anchorPx": [size / 2, size / 2], "lengthM": model.LENGTH_M, "radiusM": model.RADIUS_M,
            "flying": flying, "flightHeightM": getattr(model, "FLIGHT_HEIGHT_M", None)}
    if move_frames:
        meta["move"] = {"frames": move_frames, "kind": model.MOVE_KIND,
                        "cycleM": getattr(model, "MOVE_CYCLE_M", None), "fps": getattr(model, "MOVE_FPS", None)}
    with open(os.path.join(out_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)


if __name__ == "__main__":
    main()
