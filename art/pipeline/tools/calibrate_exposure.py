"""Check the photoreal sky: (1) the sun really comes from `scene.sun_vector()`,
(2) which film exposure puts an 18 % grey card in full sun at middle grey.

Usage: python3 tools/calibrate_exposure.py
"""
import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import bpy  # noqa: E402
import numpy as np  # noqa: E402

from strelite_art import scene as stage  # noqa: E402

sc = stage.reset_scene()
stage.add_physical_sky(sc)
# top-down ortho camera, +Y up in the image
cam_d = bpy.data.cameras.new("c"); cam_d.type = "ORTHO"; cam_d.ortho_scale = 6
cam = bpy.data.objects.new("c", cam_d); cam.location = (0, 0, 20); sc.collection.objects.link(cam)
sc.camera = cam
mat = bpy.data.materials.new("grey"); mat.use_nodes = True
mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.18, 0.18, 0.18, 1)
mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 1.0
bpy.ops.mesh.primitive_plane_add(size=6); bpy.context.object.data.materials.append(mat)
bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=1.0, location=(0, 0, 0.5))
bpy.context.object.data.materials.append(mat)
sc.render.engine = "CYCLES"; sc.cycles.samples = 64; sc.cycles.use_denoising = False
sc.render.resolution_x = sc.render.resolution_y = 96
sc.render.image_settings.file_format = "OPEN_EXR"
path = os.path.join(tempfile.mkdtemp(), "cal.exr")
sc.render.filepath = path
bpy.ops.render.render(write_still=True)
img = bpy.data.images.load(path)
px = np.array(img.pixels[:]).reshape(96, 96, 4)[:, :, :3]   # row 0 = bottom (-Y)
lum = px.mean(axis=2)
lit = np.median(lum)
ys, xs = np.nonzero(lum < lit * 0.5)
# shadow centroid relative to the pole (image centre) points AWAY from the sun
sx, sy = xs.mean() - 47.5, ys.mean() - 47.5
want = stage.sun_vector()
print(f"shadow dir (x,y) = ({sx:.1f},{sy:.1f}); expected opposite of sun ({want.x:.2f},{want.y:.2f})")
print(f"shadow length px = {math.hypot(sx, sy) * 2:.1f} (pole 1 m = 16 px, 45 deg => ~16)")
print(f"sunlit 18% card radiance = {lit:.4f}  => PHOTO_EXPOSURE_EV = {math.log2(0.18 / lit):.2f}")
print("sun/sky colour of lit card:", px[lum > lit * 0.9].mean(axis=0))
print("shadow colour:", px[lum < lit * 0.5].mean(axis=0), "ratio", lit / lum[lum < lit * 0.5].mean())
