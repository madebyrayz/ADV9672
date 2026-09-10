"""Phase 1: map the perceptual basin of the anamorphic skull over viewing position (dx, dz) at dy = 1035,
using the exact perspective transform of anamorphic.m (beta = 0, x0 = Lx/2, screen perpendicular to the
horizontal line of sight to the panel centre).  Scores the skull crop with CLIP, symmetry, and Boxer's own
geometric conditions.  Writes runs/phase1/ and figures/perceptual_basin.png."""

import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "boxer_repro")); sys.path.insert(0, str(ROOT / "lib"))
import boxer as B
from score import clip_scores, symmetry_score, clip_image_similarity

OUT = ROOT / "runs" / "phase1"; OUT.mkdir(parents=True, exist_ok=True)
img = Image.open(ROOT / "data" / "Holbein-ambassadors.jpg").convert("RGB")
DY = 1035.0
DX = np.arange(300, 1501, 10.0)
DZ = np.arange(40, 601, 5.0)
CROP_RES = 1.0   # mm per pixel in the screen frame (zscreen = -R, so screen mm are comparable across poses)
MARGIN = 1.35


def skull_crop(dx, dz):
    R, al = B.R_alpha_from_eye(dx, dz)
    m = B.skull_metrics(B.perspective, R=R, alpha_deg=al, y0=DY)
    cx, cy = m["bbox_center"]; half = max(m["width"], m["height"]) * MARGIN / 2
    crop, _ = B.warp(img, B.perspective, bounds=(cx - half, cx + half, cy - half, cy + half), res=CROP_RES,
                     R=R, alpha_deg=al, y0=DY)
    return crop.resize((224, 224), Image.BICUBIC), m


t0 = time.time()
crops, geo = [], []
for dz in DZ:
    for dx in DX:
        c, m = skull_crop(dx, dz)
        crops.append(c); geo.append((m["aspect"], m["jaw_angle_deg"]))
print(f"rendered {len(crops)} crops in {time.time()-t0:.1f}s")
p, sim = clip_scores(crops)
sym = np.array([symmetry_score(c) for c in crops])
# resemblance to the restored skull: reference = our own crop at Boxer's anamorphic.m point (the exact-perspective solution)
ref_crop, _ = skull_crop(740.5, 255.3)
res = clip_image_similarity(crops, ref_crop)
print(f"scored in {time.time()-t0:.1f}s")

shape = (len(DZ), len(DX))
P, SIM, SYM, RES = p.reshape(shape), sim.reshape(shape), sym.reshape(shape), res.reshape(shape)
ASP = np.array([g[0] for g in geo]).reshape(shape); JAW = np.array([g[1] for g in geo]).reshape(shape)
np.savez(OUT / "surfaces.npz", DX=DX, DZ=DZ, P=P, SIM=SIM, SYM=SYM, RES=RES, ASP=ASP, JAW=JAW)

# basin statistics
cell = (DX[1] - DX[0]) * (DZ[1] - DZ[0])  # mm^2
def basin(S, fracs=(0.5, 0.7, 0.9, 0.95)):
    out = {}
    pk = float(S.max()); iz, ix = np.unravel_index(S.argmax(), S.shape)
    out["peak"] = {"value": pk, "dx": float(DX[ix]), "dz": float(DZ[iz])}
    for f in fracs:
        mask = S >= f * pk
        zz, xx = np.nonzero(mask)
        out[f"above_{int(f*100)}pct"] = {"area_mm2": float(mask.sum() * cell), "n_cells": int(mask.sum()),
                                         "dx_range": [float(DX[xx].min()), float(DX[xx].max())],
                                         "dz_range": [float(DZ[zz].min()), float(DZ[zz].max())]}
    return out
stats = {"clip_skull": basin(P), "clip_sim": basin(SIM), "symmetry": basin(SYM), "resemblance": basin(RES),
         "ellipse_area_mm2": float(np.pi * 2 * 20 * 2 * 4), "grid": {"dx": [300, 1500, 10], "dz": [40, 600, 5], "dy": DY},
         "scores_at_published": {}}
for name, (dx, dy, dz) in B.PUBLISHED.items():
    ix, iz = int(round((dx - DX[0]) / 10)), int(round((dz - DZ[0]) / 5))
    ix, iz = np.clip(ix, 0, len(DX) - 1), np.clip(iz, 0, len(DZ) - 1)
    stats["scores_at_published"][name] = {"clip_skull": float(P[iz, ix]), "clip_sim": float(SIM[iz, ix]), "resemblance": float(RES[iz, ix]),
                                          "symmetry": float(SYM[iz, ix]), "aspect": float(ASP[iz, ix]), "jaw_deg": float(JAW[iz, ix])}
json.dump(stats, open(OUT / "basin_stats.json", "w"), indent=1)
print(json.dumps(stats, indent=1))

# contact sheet of crops along dz at Boxer's dx and along dx at Boxer's dz
sheet = Image.new("RGB", (224 * 9, 224 * 2 + 30), (15, 15, 15))
from PIL import ImageDraw
d = ImageDraw.Draw(sheet)
for i, dz in enumerate(np.linspace(60, 600, 9)):
    c, _ = skull_crop(776.9, dz); sheet.paste(c, (i * 224, 15)); d.text((i * 224 + 4, 2), f"dx=777 dz={dz:.0f}", fill=(255, 255, 255))
for i, dx in enumerate(np.linspace(300, 1500, 9)):
    c, _ = skull_crop(dx, 257.9); sheet.paste(c, (i * 224, 224 + 30)); d.text((i * 224 + 4, 224 + 17), f"dx={dx:.0f} dz=258", fill=(255, 255, 255))
sheet.save(OUT / "contact_sheet.jpg", quality=90)

# figure
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse
fig, axes = plt.subplots(2, 2, figsize=(14, 10.5), constrained_layout=True); axes = axes.ravel()
for ax, S, title in [(axes[0], P, "CLIP  P(skull)  (saturates: skull-likeness is not location)"), (axes[1], RES, "CLIP resemblance to the resolved skull (image-image cosine)"),
                     (axes[2], SYM, "bilateral symmetry (not expected to peak: skull is a profile)"),
                     (axes[3], np.abs(ASP - 1) + np.abs(JAW) / 10, "Boxer geometry  |aspect-1| + |jaw deg|/10  (lower = better)")]:
    im = ax.imshow(S, origin="lower", extent=[DX[0], DX[-1], DZ[0], DZ[-1]], aspect="auto", cmap="magma" if ax is not axes[3] else "magma_r",
                   vmax=None if ax is not axes[3] else 0.6)
    fig.colorbar(im, ax=ax, shrink=0.8)
    if ax is not axes[3]:
        pk = S.max()
        ax.contour(DX, DZ, S, levels=[0.5 * pk, 0.7 * pk, 0.9 * pk], colors=["white", "cyan", "lime"], linewidths=0.8)
    markers = {"National Gallery 1997": ("s", "white"), "Boxer inverseTrapezoid.m": ("o", "cyan"),
               "Boxer anamorphic.m": ("^", "lime"), "Boxer 8x8 grid hypothesis": ("x", "yellow")}
    for name, (dx, dy, dz) in B.PUBLISHED.items():
        mk, col = markers[name]
        ax.plot(dx, dz, mk, color=col, ms=8, mec="black", label=name)
    ax.add_patch(Ellipse((776.9, 257.9), 2 * 40, 2 * 8, fill=False, ec="cyan", lw=1.5, label="Boxer 2σ ellipse (40 × 8 mm radii)"))
    ax.set_xlabel("Δx  mm right of the right edge"); ax.set_ylabel("Δz  mm from the wall"); ax.set_title(title, fontsize=10)
axes[0].legend(loc="upper right", fontsize=8)
fig.suptitle("Perceptual basin of the anamorphic skull, viewing height Δy = 1035 mm, exact perspective (anamorphic.m), Wikimedia 1084 px image", fontsize=11)
fig.savefig(ROOT / "figures" / "perceptual_basin.png", dpi=130)
print("done", time.time() - t0)
