"""Phase 5: Idolmorphosis with our material, using Boxer's pipeline.
A square image is placed in the 142 x 142 mm box centred at (21.65, -783.00) of the inverse-trapezoid frame
and forward-transformed with D = 1824.45, d = 257.88 into the painting frame, where it occupies exactly Holbein's
skull footprint (915 mm lateral).  Outputs (per source image):
  figures/phase5_<name>_anamorph_print.png   the streak alone at 4 px/mm (915 mm -> 3660 px; 36 in paper width)
  figures/phase5_<name>_in_painting.jpg      composited into the painting
  figures/phase5_<name>_from_O.jpg           the composite seen from Boxer's O (anamorphic.m, R = 1806.1, alpha = 81.87)
Sources: SHARP's best-pose crop, the torn render from Boxer's O, the SHARP depth map of the skull region.
Usage: python phase5_idolmorphosis.py [run]"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "boxer_repro")); sys.path.insert(0, str(ROOT / "lib"))
import boxer as B
from camera import project as cam_project

run = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "runs/sharp_wiki_f30")
D, d = B.solve_trapezoid()
BOX_C, BOX = (21.65, -783.0), 142.0
painting = Image.open(ROOT / "data" / "Holbein-ambassadors.jpg").convert("RGB")


def forward_warp(square: Image.Image, res=0.25):
    """square image (any size) -> its anamorphic streak in painting mm, rendered at `res` mm/px.
    Returns (image, bounds in painting mm (xmin, xmax, ymin, ymax))."""
    half = BOX / 2
    src_corners_t = np.array([[BOX_C[0] - half, BOX_C[1] - half], [BOX_C[0] + half, BOX_C[1] - half], [BOX_C[0] + half, BOX_C[1] + half], [BOX_C[0] - half, BOX_C[1] + half]])
    px, py = B.forward_trapezoid(src_corners_t[:, 0], src_corners_t[:, 1], D, d)
    dst = np.stack([px, py], 1)
    xmin, xmax, ymin, ymax = dst[:, 0].min(), dst[:, 0].max(), dst[:, 1].min(), dst[:, 1].max()
    W, H = int(np.ceil((xmax - xmin) / res)), int(np.ceil((ymax - ymin) / res))
    # output px -> painting mm -> (inverse trapezoid) transformed mm -> source px
    H_out = np.array([[res, 0, xmin], [0, -res, ymax], [0, 0, 1.0]])
    H_t2src = np.array([[square.width / BOX, 0, 0], [0, -square.height / BOX, 0], [0, 0, 1.0]]) @ np.array([[1, 0, -(BOX_C[0] - half)], [0, 1, -(BOX_C[1] + half)], [0, 0, 1.0]])
    corners_p = np.array([[0, 0], [0, B.LY], [B.LX, B.LY], [B.LX, 0], [B.LX / 2, B.LY / 3]], float)
    u, v = B.inverse_trapezoid(corners_p[:, 0], corners_p[:, 1], D, d)
    H_p2t = B.homography(corners_p, np.stack([u, v], 1))
    Mm = H_t2src @ H_p2t @ H_out; Mm /= Mm[2, 2]
    coeffs = (Mm[0, 0], Mm[0, 1], Mm[0, 2], Mm[1, 0], Mm[1, 1], Mm[1, 2], Mm[2, 0], Mm[2, 1])
    out = square.convert("RGBA").transform((W, Hh := H), Image.PERSPECTIVE, coeffs, Image.BICUBIC, fillcolor=(0, 0, 0, 0))
    return out, (xmin, xmax, ymin, ymax)


def composite(streak_rgba, bounds):
    """Paste the streak into the painting image (painting px), returns RGB."""
    xmin, xmax, ymin, ymax = bounds
    W, H = painting.size
    # painting mm -> px
    px = lambda x: x / B.LX * (W - 1); py = lambda y: (H - 1) - y / B.LY * (H - 1)
    x0, x1, y1, y0 = px(xmin), px(xmax), py(ymin), py(ymax)   # y0 top
    target_w, target_h = int(round(x1 - x0)), int(round(y1 - y0))
    s = streak_rgba.resize((max(1, target_w), max(1, target_h)), Image.LANCZOS)
    out = painting.copy(); out.paste(s, (int(round(x0)), int(round(y0))), s)
    return out


def from_O(img):
    """The composite as seen from Boxer's O (exact perspective), cropped to the skull box with margin."""
    R, al = 1806.136, 81.874
    m = B.skull_metrics(B.perspective, R=R, alpha_deg=al)
    cx, cy = m["bbox_center"]; half = m["width"] * 0.9
    im, _ = B.warp(img, B.perspective, bounds=(cx - half, cx + half, cy - half, cy + half), res=0.25, R=R, alpha_deg=al)
    return im


def sources():
    out = {}
    # 1. SHARP best pose crop (by resemblance) from the orbit / fine orbit
    rows = []
    for f in ("orbit_metrics.json", "fine_metrics.json"):
        if (run / f).exists():
            rows += [r for r in json.load(open(run / f)) if "resemblance" in r]
    if rows:
        b = max(rows, key=lambda r: r["resemblance"])
        folder = "renders_fine" if b["name"].startswith("fine") else "renders_orbit"
        src = next((run / folder / f"{b['name']}{e}" for e in (".png", ".jpg") if (run / folder / f"{b['name']}{e}").exists()), None)
        im = Image.open(src).convert("RGB")
        if b.get("crop_box"):
            im = im.crop(b["crop_box"])
        out["sharp_best"] = (im, f"SHARP best pose {b['name']} ({b['dx']:.0f}, {b['dy']:.0f}, {b['dz']:.0f}) mm, resemblance {b['resemblance']:.2f}")
    # 2. the torn render from Boxer's O (skull-tracked crop)
    p = run / "renders_ref" / "ref_boxer_inversetrapezoid.png"
    if p.exists():
        im = Image.open(p).convert("RGB")
        cfg = json.load(open(run / "jobs_ref.json")); j = next(x for x in cfg["jobs"] if x["name"] == "ref_boxer_inversetrapezoid")
        # a generous crop of the lower-left where SHARP puts the skull
        out["torn_from_O"] = (im.crop((0, im.height // 3, im.width // 2, im.height)), "SHARP render from Boxer's O (torn floor, lower-left crop)")
    # 3. depth map of the skull region
    dm = np.load(run / "depth.npy")
    c0, c1, r0, r1 = [int(x / 1084 * 256) for x in (318, 791)] + [int(x / 1069 * 256) for x in (824, 1068)]
    reg = dm[r0:r1, c0:c1]; lo, hi = np.nanpercentile(reg, 2), np.nanpercentile(reg, 98)
    g = np.clip((reg - lo) / (hi - lo + 1e-9), 0, 1); g[np.isnan(reg)] = 1
    out["depth_skull"] = (Image.fromarray((255 * (1 - g)).astype(np.uint8)).convert("RGB").resize((512, 512), Image.BICUBIC), "SHARP depth map of the skull region (bright = near)")
    return out


results = {}
for name, (im, desc) in sources().items():
    sq = im.resize((512, 512), Image.LANCZOS)
    streak, bounds = forward_warp(sq)
    streak.save(ROOT / "figures" / f"phase5_{name}_anamorph_print.png")
    comp = composite(streak, bounds); comp.save(ROOT / "figures" / f"phase5_{name}_in_painting.jpg", quality=92)
    view = from_O(comp); view.save(ROOT / "figures" / f"phase5_{name}_from_O.jpg", quality=92)
    results[name] = {"source": desc, "streak_px": streak.size, "streak_mm": [bounds[1] - bounds[0], bounds[3] - bounds[2]], "print_scale_px_per_mm": 4,
                     "lateral_extent_mm_expected": 915, "files": [f"figures/phase5_{name}_{k}" for k in ("anamorph_print.png", "in_painting.jpg", "from_O.jpg")]}
    print(name, results[name])
# pair figure: streak + view from O for each source
tiles = []
for name in results:
    a = Image.open(ROOT / "figures" / f"phase5_{name}_in_painting.jpg").convert("RGB"); a.thumbnail((600, 600))
    b = Image.open(ROOT / "figures" / f"phase5_{name}_from_O.jpg").convert("RGB"); b.thumbnail((600, 600))
    t = Image.new("RGB", (a.width + b.width + 30, max(a.height, b.height) + 30), (15, 15, 15)); t.paste(a, (10, 25)); t.paste(b, (a.width + 20, 25))
    ImageDraw.Draw(t).text((10, 6), f"{name}: anamorphic in the painting  |  seen from Boxer's O", fill=(255, 255, 255)); tiles.append(t)
pair = Image.new("RGB", (max(t.width for t in tiles), sum(t.height for t in tiles)), (15, 15, 15)); y = 0
for t in tiles: pair.paste(t, (0, y)); y += t.height
pair.save(ROOT / "figures" / "phase5_pairs.jpg", quality=90)
json.dump(results, open(ROOT / "runs" / "phase5_results.json", "w"), indent=1)
