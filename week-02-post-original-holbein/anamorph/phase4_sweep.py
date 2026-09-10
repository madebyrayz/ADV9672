"""Phase 4: aggregate the assumed-lens sweep. Reads runs/sharp_wiki_f*/run.json + grid_stats.json.
Writes figures/focal_sweep.png (depth vs lens; station point vs lens on Boxer's plane), figures/depth_strip.png,
and runs/phase4_sweep.json (table)."""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "boxer_repro")); import boxer as B

runs = sorted(ROOT.glob("runs/sharp_wiki_f*"), key=lambda p: int(p.name.split("_f")[-1]))
rows = []
for run in runs:
    info = json.load(open(run / "run.json"))
    g = json.load(open(run / "grid_stats.json")) if (run / "grid_stats.json").exists() else None
    pv = info["panel_variants"]["skull_frontoparallel"]
    row = {"run": run.name, "f35_mm": info["f35_mm"], "f_px": info["f_px"], "depth_median_m": info["depth_m"]["median"], "depth_p05_m": info["depth_m"]["p05"], "depth_p95_m": info["depth_m"]["p95"],
           "relief_mm": info["panel"]["relief_p95_minus_p05_mm"], "scale_mm_per_unit": pv["scale_mm_per_unit"], "camera0_dz_mm": pv["camera0_mm"][2],
           "border_tilt_deg": info["panel_variants"]["border_plane"]["tilt_deg"], "grid_step": g["grid_step"] if g else None}
    if g:
        for key in ("resemblance", "clip_sim", "clip_skull"):
            if key in g:
                pk = g[key]["peak"]; dd = g[key]["displacement_from_boxer_mm"]
                row[f"{key}_peak"] = {"dx": pk["dx"], "dz": pk["dz"], "value": pk["value"]}; row[f"{key}_offset_mm"] = dd["euclid"]
                row[f"{key}_inside_2sigma"] = g[key]["inside_boxer_2sigma_ellipse"]
        row["at_boxer_O"] = g["scores_at_published"]["Boxer inverseTrapezoid.m"]
        row["hole_at_boxer_O"] = g["hole_fraction_at_published"]["Boxer inverseTrapezoid.m"]
    rows.append(row)
json.dump(rows, open(ROOT / "runs" / "phase4_sweep.json", "w"), indent=1)

import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse
f = np.array([r["f35_mm"] for r in rows])
fig, axes = plt.subplots(1, 3, figsize=(19, 5.6), constrained_layout=True)
ax = axes[0]
ax.plot(f, [r["depth_median_m"] for r in rows], "o-", label="median depth (m)")
ax.fill_between(f, [r["depth_p05_m"] for r in rows], [r["depth_p95_m"] for r in rows], alpha=.2, label="p05–p95")
ax.plot(f, [r["relief_mm"] / 1000 for r in rows], "s-", color="tab:red", label="relief p95−p05 (m, true panel units)")
ax.plot(f, [r["camera0_dz_mm"] / 1000 for r in rows], "^-", color="tab:green", label="photo camera Δz (m)")
ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlabel("assumed lens, 35 mm-equivalent focal (mm)"); ax.set_ylabel("metres"); ax.legend(fontsize=8); ax.grid(alpha=.3, which="both")
ax.set_title("Metric depth is linear in the assumed lens; lateral scale is not", fontsize=10)
ax = axes[1]
ax.plot(f, [r["scale_mm_per_unit"] for r in rows], "o-", label="mm per SHARP unit (skull-anchored)")
ax.plot(f, [r["border_tilt_deg"] * 10 for r in rows], "s-", color="tab:orange", label="border-plane tilt × 10 (deg)")
ax.set_xscale("log"); ax.set_xlabel("assumed lens (mm)"); ax.legend(fontsize=8); ax.grid(alpha=.3, which="both"); ax.set_title("Bridge parameters", fontsize=10)
ax = axes[2]
for name, (dx, dy, dz) in B.PUBLISHED.items():
    ax.plot(dx, dz, "o", ms=7, mec="black", label=name)
ax.add_patch(Ellipse((776.9, 257.9), 80, 16, fill=False, ec="cyan", lw=1.5, label="Boxer 2σ"))
cm = plt.cm.viridis
for i, r in enumerate(rows):
    if "resemblance_peak" in r:
        pk = r["resemblance_peak"]; ax.plot(pk["dx"], pk["dz"], "*", ms=13, color=cm(i / max(1, len(rows) - 1)), mec="black"); ax.annotate(f"{r['f35_mm']:.0f}", (pk["dx"], pk["dz"]), textcoords="offset points", xytext=(6, 4), fontsize=8)
ax.set_xlim(250, 1550); ax.set_ylim(0, 650); ax.set_xlabel("Δx mm right of the right edge"); ax.set_ylabel("Δz mm from the wall"); ax.legend(fontsize=7, loc="upper right")
ax.set_title("SHARP station point (resemblance peak) per assumed lens", fontsize=10)
fig.savefig(ROOT / "figures" / "focal_sweep.png", dpi=130)

# depth-map strip
tiles = []
for r in rows:
    p = ROOT / "runs" / r["run"] / "depth.png"
    if p.exists():
        im = Image.open(p).convert("RGB").resize((220, 220)); d = ImageDraw.Draw(im); d.text((6, 4), f"{r['f35_mm']:.0f} mm  relief {r['relief_mm']:.0f} mm", fill=(255, 80, 80)); tiles.append(im)
strip = Image.new("RGB", (220 * len(tiles), 220)); [strip.paste(t, (i * 220, 0)) for i, t in enumerate(tiles)]
strip.save(ROOT / "figures" / "depth_strip.png")
print(json.dumps([{k: r[k] for k in r if k in ("f35_mm", "depth_median_m", "relief_mm", "resemblance_offset_mm", "resemblance_inside_2sigma", "hole_at_boxer_O")} for r in rows], indent=1))
