"""Score the fine orbit (renders_fine) of a run with the tracked skull crop + resemblance metric.
Writes fine_metrics.json, fine_top12.jpg and a fine surface figure (az x el per distance)."""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def render_path(folder, name):
    """Renders may be .png (early batches) or .jpg (later batches)."""
    for ext in (".png", ".jpg"):
        p = folder / f"{name}{ext}"
        if p.exists():
            return p
    return folder / f"{name}.png"

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "lib")); sys.path.insert(0, str(ROOT / "boxer_repro"))
from score import clip_scores, clip_image_similarity
from camera import project as cam_project
from bridge import load_ply_xyz, skull_region_px, project as img_project

run = ROOT / sys.argv[1]
cfg = json.load(open(run / "jobs_fine.json"))
size, fratio = cfg["size"], cfg["fratio"]
info = json.load(open(run / "run.json"))
xyz, op, _ = load_ply_xyz(run / "model.ply")
c0, c1, r0, r1 = skull_region_px(info["width"], info["height"])
u, v = img_project(xyz, info["f_px"], info["width"], info["height"])
sel = (u >= c0) & (u <= c1) & (v >= r0) & (v <= r1) & (op > 0.5)
lo, hi = np.percentile(xyz[sel], 2, axis=0), np.percentile(xyz[sel], 98, axis=0)
SKULL3D = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
ref = Image.open(ROOT / "boxer_repro" / "restored_skull_perspective.png").convert("RGB")
ref = ref.crop((int(ref.width * 0.18), int(ref.height * 0.18), int(ref.width * 0.82), int(ref.height * 0.82))).resize((224, 224))


def tracked_crop(im, pos, target, margin=1.3):
    uv, z = cam_project(pos, target, fratio, size, SKULL3D)
    ok = z > 0.05
    if ok.sum() < 2:
        return None, None
    u0, u1 = uv[ok, 0].min(), uv[ok, 0].max(); v0, v1 = uv[ok, 1].min(), uv[ok, 1].max()
    cx, cy, half = (u0 + u1) / 2, (v0 + v1) / 2, float(np.clip(max(u1 - u0, v1 - v0) * margin / 2, 24, size / 2))
    box = (int(np.clip(cx - half, 0, size - 48)), int(np.clip(cy - half, 0, size - 48)), int(np.clip(cx + half, 48, size)), int(np.clip(cy + half, 48, size)))
    return im.crop(box).resize((224, 224), Image.BICUBIC), box


rows, crops = [], []
for j in cfg["jobs"]:
    p = render_path(run / "renders_fine", j["name"])
    if not p.exists():
        continue
    im = Image.open(p).convert("RGB")
    c, box = tracked_crop(im, j["pos"], j["target"])
    if c is None:
        c = Image.new("RGB", (224, 224)); box = None
    rows.append({**{k: j[k] for k in ("name", "az", "el", "dist_mm", "dx", "dy", "dz")}, "crop_box": box, "hole_crop": float((np.asarray(c.convert("L")) < 6).mean())})
    crops.append(c)
p_, sim = clip_scores(crops); res = clip_image_similarity(crops, ref)
for r, a, b, c in zip(rows, p_, sim, res):
    r["clip_skull"], r["clip_sim"], r["resemblance"] = float(a), float(b), float(c)
json.dump(rows, open(run / "fine_metrics.json", "w"), indent=1)
rows.sort(key=lambda r: -r["resemblance"])
print("fine orbit: n =", len(rows), "best:", {k: rows[0][k] for k in ("name", "resemblance", "clip_skull", "hole_crop", "dx", "dy", "dz")})

th = 300; sheet = Image.new("RGB", (th * 6, th * 2 + 40), (15, 15, 15)); d = ImageDraw.Draw(sheet)
for i, r in enumerate(rows[:12]):
    im = Image.open(render_path(run / "renders_fine", r["name"])).convert("RGB"); dr = ImageDraw.Draw(im)
    if r["crop_box"]: dr.rectangle(r["crop_box"], outline=(255, 80, 80), width=4)
    im = im.resize((th, th)); x, y = (i % 6) * th, (i // 6) * (th + 20) + 20; sheet.paste(im, (x, y)); d.text((x + 4, y - 16), f"{r['name']} res {r['resemblance']:.2f} P {r['clip_skull']:.2f}", fill=(255, 255, 255))
sheet.save(run / "fine_top12.jpg", quality=88)

import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
dists = sorted({r["dist_mm"] for r in rows}); AZ = sorted({r["az"] for r in rows}); EL = sorted({r["el"] for r in rows})
fig, axes = plt.subplots(1, len(dists), figsize=(4.5 * len(dists), 4), constrained_layout=True)
for ax, dist in zip(np.atleast_1d(axes), dists):
    S = np.full((len(EL), len(AZ)), np.nan)
    for r in rows:
        if r["dist_mm"] == dist: S[EL.index(r["el"]), AZ.index(r["az"])] = r["resemblance"]
    im = ax.imshow(S, origin="lower", extent=[AZ[0], AZ[-1], EL[0], EL[-1]], aspect="auto", cmap="magma", vmin=0.3, vmax=1.0)
    ax.set_title(f"resemblance, {dist} mm from the skull"); ax.set_xlabel("azimuth from the wall normal (deg)"); ax.set_ylabel("elevation (deg)")
    ax.plot(81.8, 23.7, "o", color="cyan", mec="black", label="Boxer O direction")
fig.colorbar(im, ax=axes, shrink=0.8); np.atleast_1d(axes)[0].legend(fontsize=8)
fig.suptitle(f"{run.name}: fine orbit around SHARP's skull (flat-model resemblance at Boxer's point = 0.997)", fontsize=10)
fig.savefig(run / "fine_surface.png", dpi=120)
