"""Merge the outputs of the parallel render jobs (render-art workflow) into public/art.

Each job uploads a fragment directory:
  job.json      {"kind": "tower"|"proj"|"enemy", "model": ..., "level": n}
  towers.json   the manifest as that job left it
  files/...     every file under public/art the job added or changed (not towers.json)

    python3 ci_merge.py <fragments dir> <public/art>
"""
import json
import os
import shutil
import sys


def merge_levels(known, new):
    by = {lv["level"]: lv for lv in known.get("levels", [])}
    by.update({lv["level"]: lv for lv in new.get("levels", [])})
    out = dict(known)
    out.update({k: v for k, v in new.items() if k != "levels"})
    out["levels"] = [by[k] for k in sorted(by)]
    return out


def main(frags, dst):
    path = os.path.join(dst, "towers.json")
    with open(path) as f:
        manifest = json.load(f)
    for name in sorted(os.listdir(frags)):
        d = os.path.join(frags, name)
        if not os.path.exists(os.path.join(d, "job.json")):
            continue
        with open(os.path.join(d, "job.json")) as f:
            job = json.load(f)
        with open(os.path.join(d, "towers.json")) as f:
            frag = json.load(f)
        files = os.path.join(d, "files")
        if os.path.isdir(files):
            shutil.copytree(files, dst, dirs_exist_ok=True)
        model = job["model"]
        for k, v in frag.items():                      # top-level notes and constants
            if k not in ("towers", "enemies", "projectiles"):
                manifest[k] = v
        if job["kind"] == "proj":
            manifest.setdefault("projectiles", {})[model] = frag["projectiles"][model]
        elif job["kind"] == "tower":
            new = frag["towers"][model]
            known = manifest.setdefault("towers", {}).get(model, {"levels": []})
            manifest["towers"][model] = merge_levels(known, new)
        else:
            manifest.setdefault("enemies", {})[model] = frag["enemies"][model]
        print(f"[merge] {job}")
    with open(path, "w") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
