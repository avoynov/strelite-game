"""Shared scene setup: one camera, one lighting rig, one set of render settings.

Every sprite in the game must be rendered through this module so that the
camera angle, pixel density and light direction never drift between assets.
"""
import math

import bpy
from mathutils import Vector, Euler

# --- Camera contract -------------------------------------------------------
# 2:1 dimetric ("isometric" in game-art terms): elevation 30 deg, azimuth 45 deg.
# A 1x1 m ground tile projects to a diamond exactly twice as wide as it is tall.
CAM_ELEVATION_DEG = 30.0
CAM_AZIMUTH_DEG = 45.0
# World metres covered by the frame width. Fixed for ALL assets so pixel
# density (px per metre) is identical across towers, enemies and props.
ORTHO_SCALE = 3.2
# Height (m) of the point the camera is centred on.
CAM_TARGET_Z = 0.7

STYLES = ("stylized", "realistic")


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    return scene


def camera_vectors():
    rot = Euler((math.radians(90 - CAM_ELEVATION_DEG), 0, math.radians(CAM_AZIMUTH_DEG)), "XYZ")
    back = rot.to_matrix() @ Vector((0, 0, 1))
    right = rot.to_matrix() @ Vector((1, 0, 0))
    return rot, back, right


def add_camera(scene):
    rot, back, _ = camera_vectors()
    cam_data = bpy.data.cameras.new("IsoCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = ORTHO_SCALE
    cam_data.clip_start = 0.1
    cam_data.clip_end = 100
    cam = bpy.data.objects.new("IsoCam", cam_data)
    cam.rotation_euler = rot
    cam.location = Vector((0, 0, CAM_TARGET_Z)) + back * 30
    scene.collection.objects.link(cam)
    scene.camera = cam
    return cam


def add_lights(scene, style):
    """Key sun from screen upper-left (shadows fall to the lower-right), sky fill, rim."""
    _, back, right = camera_vectors()
    right_h = Vector((right.x, right.y, 0)).normalized()
    back_h = Vector((back.x, back.y, 0)).normalized()
    to_sun = (-0.75 * right_h + 0.45 * back_h + Vector((0, 0, 1.25))).normalized()

    sun_data = bpy.data.lights.new("Key", "SUN")
    if style == "stylized":
        sun_data.energy = 3.2
        sun_data.angle = math.radians(12)  # soft, friendly shadows
        sun_data.color = (1.0, 0.95, 0.86)
    else:
        sun_data.energy = 4.0
        sun_data.angle = math.radians(2.5)  # crisp daylight
        sun_data.color = (1.0, 0.93, 0.82)
    sun = bpy.data.objects.new("Key", sun_data)
    sun.rotation_euler = (-to_sun).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(sun)

    # Rim light from behind the object to separate it from the ground.
    rim_data = bpy.data.lights.new("Rim", "SUN")
    rim_data.energy = 1.2 if style == "stylized" else 0.6
    rim_data.color = (0.75, 0.85, 1.0)
    rim_data.angle = math.radians(20)
    rim = bpy.data.objects.new("Rim", rim_data)
    to_rim = (-back_h * 1.0 + Vector((0, 0, 0.6))).normalized()
    rim.rotation_euler = (-to_rim).to_track_quat("-Z", "Y").to_euler()
    rim.visible_shadow = False
    scene.collection.objects.link(rim)

    # Sky fill via world colour.
    world = bpy.data.worlds.new("Sky")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    if style == "stylized":
        bg.inputs["Color"].default_value = (0.55, 0.68, 0.9, 1)
        bg.inputs["Strength"].default_value = 0.9
    else:
        bg.inputs["Color"].default_value = (0.5, 0.6, 0.78, 1)
        bg.inputs["Strength"].default_value = 0.6
    scene.world = world


def add_shadow_catcher(scene):
    """Invisible ground that keeps cast shadows in the sprite's alpha."""
    mesh = bpy.data.meshes.new("Ground")
    s = 3.0
    mesh.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    ground = bpy.data.objects.new("Ground", mesh)
    ground.is_shadow_catcher = True
    scene.collection.objects.link(ground)
    return ground


def configure_render(scene, style, size=512, samples=48):
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 6 if style == "realistic" else 4
    scene.render.film_transparent = True
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Punchy" if style == "stylized" else "AgX - Base Contrast"
    except TypeError:
        pass
    scene.view_settings.exposure = 0.3 if style == "stylized" else -0.1


def build_stage(style, size=512, samples=48):
    scene = reset_scene()
    add_camera(scene)
    add_lights(scene, style)
    add_shadow_catcher(scene)
    configure_render(scene, style, size, samples)
    return scene
