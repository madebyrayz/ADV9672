"""Build render job lists for one SHARP run (consumed by sharp-studio/static/render.html).

  jobs_grid.json  : viewer positions on the same (dx, dz) grid as Phase 1 at dy = 1035, camera looking
                    horizontally at the panel centre column (beta = 0, like anamorphic.m), 50 deg FOV.
  jobs_orbit.json : az/el/distance orbit around the skull centre (camera looks at the skull).
  jobs_ref.json   : the photo's own camera (frontal) and the four published viewing points.

Usage: python phase2_jobs.py runs/sharp_wiki_f30 [--panel skull_frontoparallel] [--coarse]
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "lib")); sys.path.insert(0, str(ROOT / "boxer_repro"))
from bridge import LX, LY, Panel
import boxer as B

ap = argparse.ArgumentParser()
ap.add_argument("run")
ap.add_argument("--panel", default="skull_frontoparallel")
ap.add_argument("--coarse", action="store_true")
ap.add_argument("--size", type=int, default=768)
args = ap.parse_args()
run = ROOT / args.run
info = json.load(open(run / "run.json"))
panel = Panel.load(run / f"panel_{args.panel}.json")
FOV = 50.0
fratio = 0.5 / np.tan(np.radians(FOV / 2))     # focal / canvas width
DY = 1035.0
splat_url = f"/anamorph/{run.relative_to(ROOT)}/model.splat"
common = {"splat": splat_url, "fx": info["f_px"], "width": info["width"], "height": info["height"], "size": args.size,
          "fratio": float(fratio), "fov_deg": FOV, "panel": args.panel, "panel_scale_mm_per_unit": panel.scale_mm_per_unit,
          "f35_mm": info["f35_mm"], "f_px": info["f_px"]}

def wall(x_mm, y_mm):
    return panel.wall_point(x_mm, y_mm)

# ------------------------------------------------------------------ grid (same frame as Phase 1)
step_x, step_z = (50, 40) if args.coarse else (25, 20)
DX = np.arange(300, 1501, step_x); DZ = np.arange(40, 601, step_z)
jobs = []
for dz in DZ:
    for dx in DX:
        pos = panel.to_sharp(float(dx), DY, float(dz))
        jobs.append({"name": f"grid_dx{int(dx)}_dz{int(dz)}", "pos": pos, "target": wall(LX / 2, DY), "dx": float(dx), "dy": DY, "dz": float(dz)})
json.dump({**common, "out": f"{run.relative_to(ROOT)}/renders_grid", "kind": "grid", "dx": DX.tolist(), "dz": DZ.tolist(), "dy": DY, "jobs": jobs},
          open(run / "jobs_grid.json", "w"))
print("grid jobs", len(jobs))

# ------------------------------------------------------------------ orbit around the skull
skull_c = wall(1072.5, 236.0)      # centre of Boxer's skull bbox, on the panel plane
u, v, n = map(np.asarray, (panel.u, panel.v, panel.n))
AZ = np.arange(-90, 91, 10); EL = np.arange(-45, 46, 15); DIST = [700, 1400, 2000, 2800]
jobs = []
for dist in DIST:
    for el in EL:
        for az in AZ:
            a, e = np.radians(az), np.radians(el)
            d = (np.sin(a) * np.cos(e)) * u + np.sin(e) * v + (np.cos(a) * np.cos(e)) * n
            pos = (np.asarray(skull_c) + d * dist / panel.scale_mm_per_unit).tolist()
            dx, dy, dz = panel.to_mm(pos)
            jobs.append({"name": f"orbit_d{dist}_el{int(el):+d}_az{int(az):+d}", "pos": pos, "target": skull_c,
                         "az": float(az), "el": float(el), "dist_mm": dist, "dx": dx, "dy": dy, "dz": dz})
json.dump({**common, "out": f"{run.relative_to(ROOT)}/renders_orbit", "kind": "orbit", "az": AZ.tolist(), "el": EL.tolist(), "dist_mm": DIST,
           "skull_centre_sharp": skull_c, "jobs": jobs}, open(run / "jobs_orbit.json", "w"))
print("orbit jobs", len(jobs))

# ------------------------------------------------------------------ references
jobs = [{"name": "ref_camera0_photofit", "pos": [0, 0, 0], "target": [0, 0, 1.0], "fratio": info["f_px"] / info["height"]},
        {"name": "ref_camera0_fov50", "pos": [0, 0, 0], "target": [0, 0, 1.0]}]
for name, (dx, dy, dz) in B.PUBLISHED.items():
    key = name.split()[0].lower() + ("_" + name.split()[1].split(".")[0].lower() if "Boxer" in name and "grid" not in name else ("_grid" if "grid" in name else ""))
    jobs.append({"name": f"ref_{key}", "pos": panel.to_sharp(dx, dy, dz), "target": wall(LX / 2, dy), "dx": dx, "dy": dy, "dz": dz, "published": name})
    jobs.append({"name": f"ref_{key}_lookskull", "pos": panel.to_sharp(dx, dy, dz), "target": skull_c, "dx": dx, "dy": dy, "dz": dz, "published": name})
json.dump({**common, "out": f"{run.relative_to(ROOT)}/renders_ref", "kind": "ref", "jobs": jobs}, open(run / "jobs_ref.json", "w"))
print("ref jobs", len(jobs), [j["name"] for j in jobs])
