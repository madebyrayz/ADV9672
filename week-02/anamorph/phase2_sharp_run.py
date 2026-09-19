"""Run SHARP on the painting at a list of assumed 35 mm-equivalent focal lengths.
One directory per run under runs/sharp_<image>_f<mm>/ with model.ply, model.splat, depth.png,
panel.json (units bridge) and run.json (every parameter and depth metric).

Usage: python phase2_sharp_run.py [--image wiki|gap] [--focals 14,18,...]
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image

ROOT = Path(__file__).parent
def _up(name, start, depth=5):
    for _ in range(depth):
        if (start / name).exists():
            return start / name
        start = start.parent
    return ROOT.parent / name


sys.path.insert(0, str(ROOT / "lib")); sys.path.insert(0, str(_up("ml-sharp", ROOT)))
from bridge import depth_map, fit_panel, load_ply_xyz
from ply2splat import convert
from sharp.cli.predict import DEFAULT_MODEL_URL, predict_image
from sharp.models import PredictorParams, create_predictor
from sharp.utils import io as sharp_io
from sharp.utils.gaussians import save_ply

IMAGES = {"wiki": ROOT / "data" / "Holbein-ambassadors.jpg", "gap": ROOT / "data" / "gigapixel" / "ambassadors_gap_3840.jpg"}

ap = argparse.ArgumentParser()
ap.add_argument("--image", default="wiki")
ap.add_argument("--focals", default="14,18,24,30,35,50,70,100,135,200")
args = ap.parse_args()
focals = [float(f) for f in args.focals.split(",")]

device = "mps" if torch.backends.mps.is_available() else "cpu"
t0 = time.time()
state = torch.hub.load_state_dict_from_url(DEFAULT_MODEL_URL, progress=False)
predictor = create_predictor(PredictorParams()); predictor.load_state_dict(state); predictor.eval().to(device)
print(f"model on {device} in {time.time()-t0:.1f}s")

image, _, _ = sharp_io.load_rgb(IMAGES[args.image])
H, W = image.shape[:2]
for f_mm in focals:
    f_px = float(sharp_io.convert_focallength(W, H, f_mm))     # SHARP: f_mm * diag_px / diag_35mm(43.27)
    run = ROOT / "runs" / f"sharp_{args.image}_f{int(f_mm)}"
    run.mkdir(parents=True, exist_ok=True)
    t1 = time.time()
    g = predict_image(predictor, image, f_px, torch.device(device))
    t_inf = time.time() - t1
    save_ply(g, f_px, (H, W), run / "model.ply")
    meta = convert(str(run / "model.ply"), str(run / "model.splat"))
    xyz, op, sc = load_ply_xyz(run / "model.ply")
    panel = fit_panel(xyz, op, f_px, W, H)
    panel.save(run / "panel.json")
    dm = depth_map(xyz, op, f_px, W, H, res=256)
    np.save(run / "depth.npy", dm)
    d = dm.copy(); lo, hi = np.nanpercentile(d, 1), np.nanpercentile(d, 99)
    d = np.clip((d - lo) / (hi - lo + 1e-9), 0, 1); d[np.isnan(dm)] = 0
    Image.fromarray((255 * (1 - d)).astype(np.uint8)).save(run / "depth.png")   # bright = near
    z = xyz[op > 0.5, 2]
    info = {
        "image": str(IMAGES[args.image].relative_to(ROOT)), "width": W, "height": H, "f35_mm": f_mm, "f_px": f_px,
        "device": device, "inference_s": round(t_inf, 2), "n_gaussians": int(len(xyz)),
        "sharp_internal_shape": [1536, 1536],
        "depth_m": {"min": float(z.min()), "p05": float(np.percentile(z, 5)), "median": float(np.median(z)),
                    "p95": float(np.percentile(z, 95)), "max": float(z.max()), "mean": float(z.mean())},
        "scale_size_p50_m": float(np.median(sc.max(1))),
        "panel": {"scale_mm_per_m": panel.scale_mm_per_unit, "scale_y_mm_per_m": panel.scale_y_mm_per_unit,
                  "plane_rms_border_m": panel.plane_rms_border, "plane_rms_all_m": panel.plane_rms_all,
                  "plane_rms_border_mm": panel.plane_rms_border * panel.scale_mm_per_unit,
                  "plane_rms_all_mm": panel.plane_rms_all * panel.scale_mm_per_unit,
                  "relief_p95_minus_p05_mm": panel.depth_stats["relief_p95_minus_p05"] * panel.scale_mm_per_unit,
                  "normal": panel.n, "tilt_from_camera_axis_deg": float(np.degrees(np.arccos(-np.asarray(panel.n)[2]))),
                  "camera0_mm": panel.camera0_mm},
        "convention": "SHARP frame x right, y down, z forward, metres; panel frame per lib/bridge.py; (dx,dy,dz) = right of right edge, above bottom edge, off the wall, mm",
    }
    json.dump(info, open(run / "run.json", "w"), indent=1)
    print(f"f={f_mm:>5.0f}mm f_px={f_px:7.1f}  depth median {info['depth_m']['median']:.2f} m  p05-p95 {info['depth_m']['p05']:.2f}-{info['depth_m']['p95']:.2f}"
          f"  scale {panel.scale_mm_per_unit:.0f} mm/m  relief {info['panel']['relief_p95_minus_p05_mm']:.0f} mm  border rms {info['panel']['plane_rms_border_mm']:.1f} mm  cam0 {np.round(panel.camera0_mm,0)}  ({t_inf:.1f}s)")
print("total", time.time() - t0)
