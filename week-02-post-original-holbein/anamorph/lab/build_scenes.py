"""Build anamorph/lab/scenes.json: everything the app UI needs (scenes, panel bridges,
published points, Boxer's construction, figure paths).  Re-run after adding runs."""

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "boxer_repro")); sys.path.insert(0, str(ROOT / "lib"))
import boxer as B

scenes = []
for run in sorted(ROOT.glob("runs/sharp_*_f*"), key=lambda p: (p.name.split("_")[1], int(p.name.split("_f")[-1]))):
    info = json.load(open(run / "run.json"))
    panel = json.load(open(run / "panel_skull_frontoparallel.json"))
    stats = json.load(open(run / "grid_stats.json")) if (run / "grid_stats.json").exists() else None
    best = None
    if (run / "orbit_metrics.json").exists():
        rows = json.load(open(run / "orbit_metrics.json"))
        rows = [r for r in rows if "clip_sim" in r]
        if rows:
            key = "resemblance" if "resemblance" in rows[0] else "clip_sim"
            b = max(rows, key=lambda r: r[key]); best = {k: b.get(k) for k in ("name", "az", "el", "dist_mm", "dx", "dy", "dz", "clip_sim", "clip_skull", "resemblance", "hole", "hole_crop")}
    # coarse depth grid (33 x 33 medians, metres) for the in-app depth wireframe
    dm = np.load(run / "depth.npy") if (run / "depth.npy").exists() else None
    grid = None
    if dm is not None:
        n = 64; res = dm.shape[0]; grid = []
        for j in range(n + 1):
            row = []
            for i in range(n + 1):
                r0, r1 = int(max(0, (j - 0.5) * res / n)), int(min(res, (j + 0.5) * res / n) + 1)
                c0, c1 = int(max(0, (i - 0.5) * res / n)), int(min(res, (i + 0.5) * res / n) + 1)
                blk = dm[r0:r1, c0:c1]; blk = blk[np.isfinite(blk)]
                row.append(float(np.median(blk)) if blk.size else None)
            grid.append(row)
    scenes.append({
        "depth_grid": grid,
        "id": run.name, "label": f"SHARP {info['f35_mm']:.0f} mm eq ({'Wikimedia 1084px' if 'wiki' in run.name else 'Google Art 3840px'})",
        "kind": "sharp", "splat": f"/anamorph/runs/{run.name}/model.splat", "ply": f"/anamorph/runs/{run.name}/model.ply",
        "depth_png": f"/anamorph/runs/{run.name}/depth.png", "f35_mm": info["f35_mm"], "f_px": info["f_px"],
        "width": info["width"], "height": info["height"], "image": f"/anamorph/{info['image']}",
        "depth_m": info["depth_m"], "relief_mm": info["panel"]["relief_p95_minus_p05_mm"],
        "panel": {k: panel[k] for k in ("origin", "u", "v", "n", "scale_mm_per_unit", "width_units", "height_units")},
        "panel_variants": info.get("panel_variants"), "grid_stats": stats, "best_orbit_pose": best,
        "figures": {k: f"/anamorph/runs/{run.name}/{k}" for k in ("sharp_basin.png", "grid_contact_sheet.jpg", "orbit_contact_sheet_d700.jpg", "orbit_contact_sheet_d1400.jpg", "orbit_contact_sheet_d2000.jpg", "orbit_contact_sheet_d2800.jpg") if (run / k).exists()},
    })

D, d = B.solve_trapezoid()
manifest = {
    "painting": {"image": "/anamorph/data/Holbein-ambassadors.jpg", "width_mm": B.LX, "height_mm": B.LY, "px": [1084, 1069],
                 "source": "Wikimedia Holbein-ambassadors.jpg (Boxer's input); panel size Wyld 1998"},
    "published_points": [{"name": n, "dx": v[0], "dy": v[1], "dz": v[2]} for n, v in B.PUBLISHED.items()],
    "boxer": {"D": D, "d": d, "x0": B.LX / 2, "y0": B.LY / 2, "sigma_dx": 20, "sigma_dz": 4,
              "S_mm": [B.LX / 2 + D, B.LY / 2, 0], "O_mm": [B.LX / 2 + D, B.LY / 2, d],
              "skull_points_mm": B.SKULL_PTS.tolist(), "skull_bbox_mm": [615, 1530, 0, 472],
              "restored_box": {"size_mm": 142, "centre": [21.65, -783.0]}, "R_perspective": 1806.136, "alpha_perspective_deg": 81.874},
    "phase1": {"figure": "/anamorph/figures/perceptual_basin.png", "contact_sheet": "/anamorph/runs/phase1/contact_sheet.jpg",
               "stats": json.load(open(ROOT / "runs/phase1/basin_stats.json")) if (ROOT / "runs/phase1/basin_stats.json").exists() else None},
    "scenes": scenes,
}
(ROOT / "lab").mkdir(exist_ok=True)
json.dump(manifest, open(ROOT / "lab" / "scenes.json", "w"), indent=1)
print("scenes:", [s["id"] for s in scenes])
