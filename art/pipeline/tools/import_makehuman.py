"""Convert the MakeHuman hm08 base mesh and the few targets the soldiers use into
compact numpy files under art/pipeline/assets/makehuman (run once; the result is
committed so renders never need the network).

Source: github.com/makehumancommunity/makehuman (master), files
  makehuman/data/3dobjs/base.obj and makehuman/data/targets/macrodetails/*.target
Licence of these assets: CC0 1.0 (see assets/makehuman/README.md).

  python3 tools/import_makehuman.py <folder with base.obj and *.target>

The files are parsed as plain text here; nothing in them is executed.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "assets", "makehuman")
KEEP_GROUPS = ("body", "helper-skirt", "helper-l-eye", "helper-r-eye")


def read_obj(path):
    verts, faces, group = [], {}, None
    joints = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("v "):
                verts.append([float(x) for x in line.split()[1:4]])
            elif line.startswith("g "):
                group = line.split()[1]
            elif line.startswith("f "):
                idx = [int(p.split("/")[0]) - 1 for p in line.split()[1:]]
                if group.startswith("joint-"):
                    joints.setdefault(group, set()).update(idx)
                elif group in KEEP_GROUPS:
                    if len(idx) == 3:
                        idx.append(idx[2])          # store triangles as degenerate quads
                    faces.setdefault(group, []).append(idx)
    return np.array(verts, np.float32), {g: np.array(v, np.int32) for g, v in faces.items()}, \
        {g: np.array(sorted(v), np.int32) for g, v in joints.items()}


def read_target(path):
    idx, d = [], []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            p = line.split()
            idx.append(int(p[0]))
            d.append([float(p[1]), float(p[2]), float(p[3])])
    return np.array(idx, np.int32), np.array(d, np.float32).reshape(-1, 3)


def main(src):
    os.makedirs(os.path.join(OUT, "targets"), exist_ok=True)
    verts, faces, joints = read_obj(os.path.join(src, "base.obj"))
    arrays = {"verts": verts}
    for g, f in faces.items():
        arrays["faces:" + g] = f
    for g, v in joints.items():
        arrays["joint:" + g[6:]] = v
    np.savez_compressed(os.path.join(OUT, "hm08.npz"), **arrays)
    print("base", verts.shape, {g: f.shape for g, f in faces.items()}, len(joints), "joints")
    for fn in sorted(os.listdir(os.path.join(src, "t"))):
        if fn.endswith(".target"):
            i, d = read_target(os.path.join(src, "t", fn))
            np.savez_compressed(os.path.join(OUT, "targets", fn[:-7] + ".npz"), idx=i, delta=d)
            print("target", fn, len(i))


if __name__ == "__main__":
    main(sys.argv[1])
