"""Score SHARP renders for one run: skull crops on the (dx, dz) grid with the Phase 1 metric, orbit
collapse metrics, contact sheets, and the SHARP basin figure.

Usage: python phase2_score.py runs/sharp_wiki_f30
"""

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
import boxer as B
from score import clip_scores, symmetry_score, clip_image_similarity
from camera import project as cam_project
from bridge import load_ply_xyz, skull_region_px, project as img_project

run = ROOT / sys.argv[1]
# SHARP's own skull: 3D bbox of opaque Gaussians that project into Boxer's skull box in the photo
_info = json.load(open(run / "run.json"))
_xyz, _op, _ = load_ply_xyz(run / "model.ply")
_c0, _c1, _r0, _r1 = skull_region_px(_info["width"], _info["height"])
_u, _v = img_project(_xyz, _info["f_px"], _info["width"], _info["height"])
_sel = (_u >= _c0) & (_u <= _c1) & (_v >= _r0) & (_v <= _r1) & (_op > 0.5)
_lo, _hi = np.percentile(_xyz[_sel], 2, axis=0), np.percentile(_xyz[_sel], 98, axis=0)
SKULL3D = np.array([[x, y, z] for x in (_lo[0], _hi[0]) for y in (_lo[1], _hi[1]) for z in (_lo[2], _hi[2])])
SKULL3D_CENTRE = _xyz[_sel].mean(0)
PANEL3D = None
# reference crop for the resemblance metric: the resolved skull of the flat model at Boxer's anamorphic.m point
_ref = Image.open(ROOT / "boxer_repro" / "restored_skull_perspective.png").convert("RGB")
_ref = _ref.crop((int(_ref.width * 0.18), int(_ref.height * 0.18), int(_ref.width * 0.82), int(_ref.height * 0.82))).resize((224, 224))


def tracked_crop(im, pos, target, fratio, size, margin=1.3):
    """Crop around SHARP's reconstructed skull as seen by this camera (projected 3D bbox), clamped to the frame."""
    uv, z = cam_project(pos, target, fratio, size, SKULL3D)
    ok = z > 0.05
    if ok.sum() < 2:
        return None, None
    u0, u1 = uv[ok, 0].min(), uv[ok, 0].max(); v0, v1 = uv[ok, 1].min(), uv[ok, 1].max()
    cx, cy, half = (u0 + u1) / 2, (v0 + v1) / 2, max(u1 - u0, v1 - v0) * margin / 2
    half = float(np.clip(half, 24, size / 2))
    box = (int(np.clip(cx - half, 0, size - 48)), int(np.clip(cy - half, 0, size - 48)), int(np.clip(cx + half, 48, size)), int(np.clip(cy + half, 48, size)))
    return im.crop(box).resize((224, 224), Image.BICUBIC), box
cfg = json.load(open(run / "jobs_grid.json"))
size, fratio = cfg["size"], cfg["fratio"]
f_render = fratio * size
DY = cfg["dy"]


def skull_box_px(dx, dz):
    """Where the flat-panel skull would appear in a 50 deg render from (dx, DY, dz): Phase 1 geometry."""
    R, al = B.R_alpha_from_eye(dx, dz)
    m = B.skull_metrics(B.perspective, R=R, alpha_deg=al, y0=DY)
    cx, cy = m["bbox_center"]; half = max(m["width"], m["height"]) * 1.35 / 2
    k = f_render / R                       # screen mm (zscreen = R) -> pixels
    return (size / 2 + (cx - half) * k, size / 2 - (cy + half) * k, size / 2 + (cx + half) * k, size / 2 - (cy - half) * k)


def crop_metrics(im: Image.Image):
    g = np.asarray(im.convert("L"), dtype=np.float32)
    hole = float((g < 6).mean())
    lap = float(np.var(np.diff(g, 2, axis=0)[:, :-2] + np.diff(g, 2, axis=1)[:-2, :]))
    return hole, lap


# ------------------------------------------------------------------ grid
DX, DZ = np.array(cfg["dx"], float), np.array(cfg["dz"], float)
crops, holes, laps, missing = [], [], [], 0
for j in cfg["jobs"]:
    p = render_path(run / "renders_grid", j["name"])
    if not p.exists():
        missing += 1; crops.append(Image.new("RGB", (224, 224))); holes.append(1.0); laps.append(0.0); continue
    im = Image.open(p).convert("RGB")
    c, box = tracked_crop(im, j["pos"], j["target"], fratio, size)
    if c is None:
        c = Image.new("RGB", (224, 224))
    h, l = crop_metrics(c)
    crops.append(c); holes.append(h); laps.append(l)
print("missing renders:", missing)
p, sim = clip_scores(crops)
res = clip_image_similarity(crops, _ref)
sym = np.array([symmetry_score(c) for c in crops])
shape = (len(DZ), len(DX))
P, SIM, SYM, HOLE, LAP, RES = [np.array(a).reshape(shape) for a in (p, sim, sym, holes, laps, res)]
np.savez(run / "grid_surfaces.npz", DX=DX, DZ=DZ, P=P, SIM=SIM, SYM=SYM, HOLE=HOLE, LAP=LAP, RES=RES)

cell = (DX[1] - DX[0]) * (DZ[1] - DZ[0])
def basin(S, fracs=(0.5, 0.7, 0.9, 0.95)):
    pk = float(S.max()); iz, ix = np.unravel_index(S.argmax(), S.shape)
    out = {"peak": {"value": pk, "dx": float(DX[ix]), "dz": float(DZ[iz])}}
    for f in fracs:
        mask = S >= f * pk; zz, xx = np.nonzero(mask)
        out[f"above_{int(f*100)}pct"] = {"area_mm2": float(mask.sum() * cell), "dx_range": [float(DX[xx].min()), float(DX[xx].max())], "dz_range": [float(DZ[zz].min()), float(DZ[zz].max())]}
    return out
def at(S, dx, dz):
    ix = int(np.argmin(np.abs(DX - dx))); iz = int(np.argmin(np.abs(DZ - dz))); return float(S[iz, ix])
stats = {"clip_skull": basin(P), "clip_sim": basin(SIM), "symmetry": basin(SYM), "resemblance": basin(RES), "crop": "tracked 3D bbox of SHARP's skull Gaussians",
         "hole_fraction_at_published": {n: at(HOLE, dx, dz) for n, (dx, dy, dz) in B.PUBLISHED.items()},
         "scores_at_published": {n: {"clip_skull": at(P, dx, dz), "clip_sim": at(SIM, dx, dz), "resemblance": at(RES, dx, dz)} for n, (dx, dy, dz) in B.PUBLISHED.items()},
         "grid_step": [float(DX[1] - DX[0]), float(DZ[1] - DZ[0])], "n_missing": missing}
# displacement of SHARP's peak from Boxer's point, in mm and in units of the expert disagreement (13, 138)
for key in ("clip_skull", "clip_sim", "resemblance"):
    pk = stats[key]["peak"]; ddx, ddz = pk["dx"] - 776.9, pk["dz"] - 257.9
    stats[key]["displacement_from_boxer_mm"] = {"dx": ddx, "dz": ddz, "euclid": float(np.hypot(ddx, ddz))}
    stats[key]["displacement_in_expert_disagreement_units"] = {"dx": ddx / 13.0, "dz": ddz / 138.0}
    stats[key]["inside_boxer_2sigma_ellipse"] = bool((ddx / 40) ** 2 + (ddz / 8) ** 2 <= 1)
json.dump(stats, open(run / "grid_stats.json", "w"), indent=1)

# contact sheet of crops along the same two lines as Phase 1
def nearest_job(dx, dz):
    return f"grid_dx{int(DX[np.argmin(np.abs(DX-dx))])}_dz{int(DZ[np.argmin(np.abs(DZ-dz))])}"
sheet = Image.new("RGB", (224 * 9, 224 * 2 + 30), (15, 15, 15)); d = ImageDraw.Draw(sheet)
for row, (label, pts) in enumerate([("dx=777", [(776.9, z) for z in np.linspace(60, 600, 9)]), ("dz=258", [(x, 257.9) for x in np.linspace(300, 1500, 9)])]):
    for i, (dx, dz) in enumerate(pts):
        idx = [j["name"] for j in cfg["jobs"]].index(nearest_job(dx, dz))
        sheet.paste(crops[idx], (i * 224, 15 + row * (224 + 15)))
        d.text((i * 224 + 4, 2 + row * (224 + 15)), f"dx={dx:.0f} dz={dz:.0f}  P={p[idx]:.2f} res={res[idx]:.2f}", fill=(255, 255, 255))
sheet.save(run / "grid_contact_sheet.jpg", quality=90)

# ------------------------------------------------------------------ orbit: collapse metrics + contact sheets
ocfg = json.load(open(run / "jobs_orbit.json"))
orbit_rows = []
frontal = None
for j in ocfg["jobs"]:
    pth = render_path(run / "renders_orbit", j["name"])
    if not pth.exists():
        continue
    im = Image.open(pth).convert("RGB")
    g = np.asarray(im.convert("L"), dtype=np.float32)
    hole = float((g < 6).mean())
    lap = float(np.var(np.diff(g, 2, axis=0)[:, :-2] + np.diff(g, 2, axis=1)[:-2, :]))
    # angular distance of this viewpoint from the photo camera's axis, measured at the skull
    cam0 = -np.asarray(ocfg["skull_centre_sharp"]); pv = np.asarray(j["pos"]) - np.asarray(ocfg["skull_centre_sharp"])
    ang = float(np.degrees(np.arccos(np.clip(cam0 @ pv / np.linalg.norm(cam0) / np.linalg.norm(pv), -1, 1))))
    orbit_rows.append({**{k: j[k] for k in ("name", "az", "el", "dist_mm", "dx", "dy", "dz")}, "hole": hole, "laplacian_var": lap, "angle_from_camera_axis_deg": ang})
# crop around SHARP's reconstructed skull (projected 3D bbox) for orbit renders
oc = []
_jobs = {j["name"]: j for j in ocfg["jobs"]}
for r in orbit_rows:
    j = _jobs[r["name"]]
    c, box = tracked_crop(Image.open(render_path(run / "renders_orbit", r["name"])).convert("RGB"), j["pos"], j["target"], fratio, size)
    if c is None: c = Image.new("RGB", (224, 224))
    r["crop_box"] = box; r["hole_crop"] = float((np.asarray(c.convert("L")) < 6).mean())
    oc.append(c)
if oc:
    op_, osim = clip_scores(oc)
    ores = clip_image_similarity(oc, _ref)
    for r, a, b, cc in zip(orbit_rows, op_, osim, ores):
        r["clip_skull"], r["clip_sim"], r["resemblance"] = float(a), float(b), float(cc)
    ref_lap = np.median([r["laplacian_var"] for r in orbit_rows if abs(r["az"]) <= 10 and abs(r["el"]) <= 15]) or 1.0
    for r in orbit_rows:
        r["lap_ratio_to_frontal"] = r["laplacian_var"] / ref_lap
        r["collapsed"] = bool(r["hole_crop"] > 0.15 or r["lap_ratio_to_frontal"] < 0.3)
if orbit_rows:
    json.dump(orbit_rows, open(run / "orbit_metrics.json", "w"), indent=1)
# collapse summary: smallest angle at which >= half of poses are collapsed, per distance
summary = {}
for dist in ocfg["dist_mm"]:
    rows = [r for r in orbit_rows if r["dist_mm"] == dist]
    bins = {}
    for r in rows:
        b = int(r["angle_from_camera_axis_deg"] // 15) * 15
        bins.setdefault(b, []).append(r["collapsed"])
    summary[str(dist)] = {str(k): float(np.mean(v)) for k, v in sorted(bins.items())}
if orbit_rows:
    json.dump(summary, open(run / "orbit_collapse_by_angle.json", "w"), indent=1)

for dist in (ocfg["dist_mm"] if orbit_rows else []):   # no sheets for runs without orbit renders
    AZ, EL = ocfg["az"], ocfg["el"]; th = 128
    sheet = Image.new("RGB", (th * len(AZ) + 60, th * len(EL) + 30), (15, 15, 15)); d = ImageDraw.Draw(sheet)
    for ei, el in enumerate(EL):
        d.text((4, 30 + ei * th + th // 2), f"el {el:+d}", fill=(255, 255, 255))
        for ai, az in enumerate(AZ):
            pth = render_path(run / "renders_orbit", f"orbit_d{dist}_el{int(el):+d}_az{int(az):+d}")
            if pth.exists():
                sheet.paste(Image.open(pth).convert("RGB").resize((th, th)), (60 + ai * th, 30 + ei * th))
            if ei == 0: d.text((60 + ai * th + 4, 8), f"az {az:+d}", fill=(255, 255, 255))
    sheet.save(run / f"orbit_contact_sheet_d{dist}.jpg", quality=88)

# ------------------------------------------------------------------ figure
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse
fig, axes = plt.subplots(2, 2, figsize=(14, 10.5), constrained_layout=True); axes = axes.ravel()
for ax, S, title, cmap in [(axes[0], P, "SHARP render: CLIP P(skull), crop tracks SHARP's skull", "magma"), (axes[1], RES, "SHARP render: resemblance to the resolved skull", "magma"),
                           (axes[2], SIM, "SHARP render: CLIP similarity to skull prompts", "magma"), (axes[3], HOLE, "hole fraction in the tracked crop (1 = empty)", "viridis")]:
    im = ax.imshow(S, origin="lower", extent=[DX[0], DX[-1], DZ[0], DZ[-1]], aspect="auto", cmap=cmap)
    fig.colorbar(im, ax=ax, shrink=0.8)
    markers = {"National Gallery 1997": ("s", "white"), "Boxer inverseTrapezoid.m": ("o", "cyan"), "Boxer anamorphic.m": ("^", "lime"), "Boxer 8x8 grid hypothesis": ("x", "yellow")}
    for name, (dx, dy, dz) in B.PUBLISHED.items():
        mk, col = markers[name]; ax.plot(dx, dz, mk, color=col, ms=8, mec="black", label=name)
    ax.add_patch(Ellipse((776.9, 257.9), 80, 16, fill=False, ec="cyan", lw=1.5))
    pk = stats["resemblance"]["peak"]; ax.plot(pk["dx"], pk["dz"], "*", color="red", ms=14, mec="black", label="SHARP peak (resemblance)")
    ax.set_xlabel("Δx mm right of the right edge"); ax.set_ylabel("Δz mm from the wall"); ax.set_title(title, fontsize=10)
axes[0].legend(loc="upper right", fontsize=7)
fig.suptitle(f"SHARP station-point surface, {run.name}, f35 = {cfg['f35_mm']} mm, panel = {cfg['panel']}, Δy = {DY} mm, 50° renders", fontsize=11)
fig.savefig(run / "sharp_basin.png", dpi=130)
print(json.dumps({k: stats[k] for k in ("clip_skull", "clip_sim", "resemblance")}, indent=1))
print("collapse by angle:", json.dumps(summary))
