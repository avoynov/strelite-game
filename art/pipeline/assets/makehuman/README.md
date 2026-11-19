# MakeHuman hm08 base mesh and targets (CC0)

The soldiers' bodies (`strelite_art/mhuman.py`) start from the MakeHuman "hm08" base mesh,
shaped with a few MakeHuman targets (male, young, muscle, weight, height, ideal proportions,
three ancestry mixes), then rigged with Blender's Rigify Human meta-rig.

- Source: https://github.com/makehumancommunity/makehuman (branch master),
  `makehuman/data/3dobjs/base.obj` and `makehuman/data/targets/macrodetails/...`.
- Licence: the MakeHuman project released its assets (base mesh, proxies, targets,
  textures, clothes, poses) under **CC0 1.0 Universal** in September 2020 (see the
  project's LICENSE.md, section C, and the header of base.obj). No attribution is
  required; we keep this note for provenance.
- Converted with `tools/import_makehuman.py` into `hm08.npz` (vertices in MakeHuman
  units = decimetres, y up, z forward; faces of the `body`, `helper-skirt` and eye
  helper groups; vertex indices of every `joint-*` helper) and `targets/*.npz`
  (`idx`, `delta` in the same units).
