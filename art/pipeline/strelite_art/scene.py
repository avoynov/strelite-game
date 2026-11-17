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

STYLES = ("stylized", "realistic", "photoreal")

# --- "photoreal" camera: a full-frame camera with a telephoto lens -------------
# Same elevation/azimuth as the ortho contract, but true perspective. The camera
# is placed so that `frame_m` metres fill the frame width at the target point,
# i.e. sprites keep the same footprint as in the ortho styles.
PHOTO_LENS_MM = 200.0
PHOTO_SENSOR_MM = 36.0
PHOTO_SUN_ELEVATION_DEG = 45.0
# Film exposure (stops) that puts an 18 % grey card in full sun at middle grey
# under the sky below ("sunny 16"). Measured with tools/calibrate_exposure.py.
PHOTO_EXPOSURE_EV = -5.18
PHOTO_WHITE_BALANCE = (0.907, 1.0, 1.118)


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


def add_camera(scene, style="stylized", frame_m=ORTHO_SCALE, lens_mm=PHOTO_LENS_MM,
               target_z=None, projection="persp"):
    """projection: photoreal stills use the telephoto lens ("persp"); photoreal game
    sprites use "ortho", the game's own 2:1 projection, so every sprite sits on the
    tile grid exactly and world metres map to pixels linearly."""
    rot, back, _ = camera_vectors()
    cam_data = bpy.data.cameras.new("IsoCam")
    target = Vector((0, 0, CAM_TARGET_Z if target_z is None else target_z))
    if style == "photoreal" and projection == "ortho":
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = frame_m
        cam_data.clip_start = 0.5
        cam_data.clip_end = 400
        distance = 120
    elif style == "photoreal":
        cam_data.type = "PERSP"
        cam_data.sensor_fit = "HORIZONTAL"
        cam_data.sensor_width = PHOTO_SENSOR_MM
        cam_data.lens = lens_mm
        distance = frame_m * lens_mm / PHOTO_SENSOR_MM
        cam_data.clip_start = 0.5
        cam_data.clip_end = distance * 4
    else:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = ORTHO_SCALE
        cam_data.clip_start = 0.1
        cam_data.clip_end = 100
        distance = 30
    cam = bpy.data.objects.new("IsoCam", cam_data)
    cam.rotation_euler = rot
    cam.location = target + back * distance
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


def sun_vector(elevation_deg=PHOTO_SUN_ELEVATION_DEG):
    """Unit vector toward the sun: screen upper-left, like the key light of A/B."""
    _, back, right = camera_vectors()
    right_h = Vector((right.x, right.y, 0)).normalized()
    back_h = Vector((back.x, back.y, 0)).normalized()
    h = (-0.75 * right_h + 0.45 * back_h).normalized()
    el = math.radians(elevation_deg)
    return h * math.cos(el) + Vector((0, 0, math.sin(el)))


def add_physical_sky(scene, elevation_deg=PHOTO_SUN_ELEVATION_DEG):
    """Physically based daylight: atmospheric sky model with its own sun disc
    (0.545 deg, so shadow sharpness is real). The sky is not visible in frame but
    gives the blue fill in shadows and the reflections in paint and metal."""
    world = bpy.data.worlds.new("PhysicalSky")
    world.use_nodes = True
    nt = world.node_tree
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_disc = True
    sky.sun_size = math.radians(0.545)
    sky.sun_elevation = math.radians(elevation_deg)
    to_sun = sun_vector(elevation_deg)
    # Sky model convention: rotation 0 puts the sun toward +Y, positive turns toward +X.
    sky.sun_rotation = math.atan2(to_sun.x, to_sun.y)
    sky.altitude = 300
    sky.air_density = 1.0
    sky.aerosol_density = 0.5   # clear day
    sky.ozone_density = 1.0
    bg = nt.nodes["Background"]
    bg.inputs["Strength"].default_value = 1.0
    # Camera white balance ("daylight" preset): a grey card in the sun comes out neutral.
    wb = nt.nodes.new("ShaderNodeMix")
    wb.data_type = "RGBA"
    wb.blend_type = "MULTIPLY"
    wb.inputs["Factor"].default_value = 1.0
    wb.inputs["B"].default_value = (*PHOTO_WHITE_BALANCE, 1.0)
    nt.links.new(sky.outputs["Color"], wb.inputs["A"])
    nt.links.new(wb.outputs["Result"], bg.inputs["Color"])
    scene.world = world
    return sky


def add_shadow_catcher(scene, hole_radius=0.0, half=3.0, z=0.0):
    """Invisible ground that keeps cast shadows in the sprite's alpha.
    hole_radius > 0 leaves the middle open (a sprite's own soil patch lies there)."""
    mesh = bpy.data.meshes.new("Ground")
    s = half
    if hole_radius > 0:
        n = 96
        inner = [(hole_radius * math.cos(2 * math.pi * i / n), hole_radius * math.sin(2 * math.pi * i / n), z)
                 for i in range(n)]
        outer = []
        for i in range(n):
            a = 2 * math.pi * i / n
            k = s / max(abs(math.cos(a)), abs(math.sin(a)))
            outer.append((k * math.cos(a), k * math.sin(a), z))
        faces = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        mesh.from_pydata(inner + outer, [], faces)
    else:
        mesh.from_pydata([(-s, -s, z), (s, -s, z), (s, s, z), (-s, s, z)], [], [(0, 1, 2, 3)])
    ground = bpy.data.objects.new("Ground", mesh)
    ground.is_shadow_catcher = True
    scene.collection.objects.link(ground)
    return ground


def configure_render(scene, style, size=512, samples=48):
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = {"stylized": 4, "realistic": 6, "photoreal": 8}[style]
    scene.render.film_transparent = True
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = {"stylized": "AgX - Punchy", "realistic": "AgX - Base Contrast",
                                    "photoreal": "AgX - Medium High Contrast"}[style]
    except TypeError:
        pass
    scene.view_settings.exposure = {"stylized": 0.3, "realistic": -0.1,
                                    "photoreal": PHOTO_EXPOSURE_EV}[style]
    if style == "photoreal":
        scene.cycles.sample_clamp_indirect = 10.0
        scene.cycles.use_adaptive_sampling = True
        scene.cycles.adaptive_threshold = 0.02


def build_stage(style, size=512, samples=48, frame_m=ORTHO_SCALE, ground="catcher",
                lens_mm=PHOTO_LENS_MM, target_z=None, projection="persp", catcher_hole=0.0):
    """ground: "catcher" = transparent sprite with shadow, "patch" = the same plus a
    hole in the middle for the sprite's own soil patch, "terrain"/"none" = caller
    adds opaque ground."""
    scene = reset_scene()
    if style == "photoreal":
        add_camera(scene, style, frame_m, lens_mm, target_z, projection)
        add_physical_sky(scene)
    else:
        add_camera(scene)
        add_lights(scene, style)
    if ground == "catcher":
        g = add_shadow_catcher(scene)
        g.scale = (frame_m / ORTHO_SCALE,) * 3
    elif ground == "patch":
        add_shadow_catcher(scene, hole_radius=catcher_hole, half=frame_m, z=-0.004)
    configure_render(scene, style, size, samples)
    scene.render.film_transparent = ground in ("catcher", "patch")
    return scene
