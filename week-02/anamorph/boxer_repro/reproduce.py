"""Phase 0: reproduce Boxer's numbers and restored skull from his image and parameters."""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
import boxer as B

HERE = Path(__file__).parent
IMG = HERE.parent / "data" / "Holbein-ambassadors.jpg"
img = Image.open(IMG).convert("RGB")
assert img.size == (1084, 1069), img.size

rows = []
def row(name, ours, his, unit="mm"):
    diff = None if his is None else ours - his
    rows.append((name, ours, his, diff, unit))

# ---------------------------------------------------------------- inverse trapezoid, closed form
D, d = B.solve_trapezoid()
m_t = B.skull_metrics(B.inverse_trapezoid, D=D, d=d)
dx_t, dy_t, dz_t = B.trapezoid_eye(D, d)
row("D (jaw through S)", D, B.BOXER_D)
row("d (aspect = 1)", d, B.BOXER_d)
row("jaw angle in painting", np.degrees(np.arctan2(257, 1210 - 661)), 25.1, "deg")
row("trapezoid dx", dx_t, 776.9)
row("trapezoid dy", dy_t, 1035.0)
row("trapezoid dz", dz_t, 257.9)
row("restored skull width", m_t["width"], 142.0)
row("restored skull height", m_t["height"], 142.0)
row("restored box centre x", m_t["bbox_center"][0], 21.65)
row("restored box centre y", m_t["bbox_center"][1], -783.00)
row("restored jaw angle", m_t["jaw_angle_deg"], 0.0, "deg")

# ---------------------------------------------------------------- perspective, numerical
R, al = B.solve_perspective()
dx_p, dy_p, dz_p = B.eye_from_R_alpha(R, al)
m_p = B.skull_metrics(B.perspective, R=R, alpha_deg=al)
row("perspective R", R, None)
row("perspective alpha (from normal)", al, None, "deg")
row("perspective dx", dx_p, 740.5)
row("perspective dz", dz_p, 255.3)
row("perspective jaw angle", m_p["jaw_angle_deg"], 0.0, "deg")
row("perspective aspect", m_p["aspect"], 1.0, "")

# ---------------------------------------------------------------- the relation between the two parameter sets
# Brief's derivation: D = R sin(a), d = R cos(a)  ->  R = hypot(D, d), a = atan(D/d)
R_brief, a_brief = float(np.hypot(D, d)), float(np.degrees(np.arctan2(D, d)))
# Algebraic identity: perspective(x; R, a) == inverse_trapezoid(x; D = R/sin a, d = R cot a)
R_alg, a_alg = D * np.sin(np.arccos(d / D)), float(np.degrees(np.arccos(d / D)))
row("R implied by brief (hypot)", R_brief, None)
row("alpha implied by brief", a_brief, None, "deg")
row("R from algebraic identity", R_alg, R)
row("alpha from algebraic identity", a_alg, al, "deg")
# numeric check of the identity on a grid of points
xs, ys = np.meshgrid(np.linspace(0, B.LX, 40), np.linspace(0, B.LY, 40))
u1, v1 = B.inverse_trapezoid(xs, ys, D, d)
u2, v2 = B.perspective(xs, ys, R_alg, a_alg)
identity_err = float(np.max(np.hypot(u1 - u2, v1 - v2)))
row("max |trapezoid - perspective| under identity", identity_err, 0.0)
u3, v3 = B.perspective(xs, ys, R_brief, a_brief)
row("max |trapezoid - perspective| under brief relation", float(np.max(np.hypot(u1 - u3, v1 - v3))), None)

# ---------------------------------------------------------------- images
res = 1.0
full_t, bounds_t = B.warp(img, B.inverse_trapezoid, res=2.0, D=D, d=d)
full_t.save(HERE / "restored_painting_inverse_trapezoid.jpg", quality=92)

def crop_box(fn, bbox_center, size, res, margin=1.6, **kw):
    cx, cy = bbox_center
    half = size * margin / 2
    im, b = B.warp(img, fn, bounds=(cx - half, cx + half, cy - half, cy + half), res=res, **kw)
    return im, b

skull_t, bt = crop_box(B.inverse_trapezoid, m_t["bbox_center"], m_t["width"], 0.25, D=D, d=d)
skull_p, bp = crop_box(B.perspective, m_p["bbox_center"], m_p["width"], 0.25, R=R, alpha_deg=al)
for im, b, name, mm in [(skull_t, bt, "restored_skull_inverse_trapezoid.png", m_t), (skull_p, bp, "restored_skull_perspective.png", m_p)]:
    dr = ImageDraw.Draw(im)
    x0, x1, y0, y1 = mm["bbox"]
    px = lambda x, y: ((x - b[0]) / 0.25, (b[3] - y) / 0.25)
    dr.rectangle([px(x0, y1), px(x1, y0)], outline=(0, 255, 255), width=2)
    im.save(HERE / name)

# side by side with Boxer's published OptimalSkull.jpg
bx = Image.open(HERE.parent / "data" / "boxer_figs" / "OptimalSkull.jpg").convert("RGB")
h = 600
panel = Image.new("RGB", (3 * h + 40, h + 40), (20, 20, 20))
for i, (im, label) in enumerate([(skull_t, "ours: inverse trapezoid"), (skull_p, "ours: perspective"), (bx, "Boxer: OptimalSkull.jpg")]):
    im2 = im.copy(); im2.thumbnail((h, h))
    panel.paste(im2, (10 + i * (h + 10), 30))
    ImageDraw.Draw(panel).text((10 + i * (h + 10), 10), label, fill=(230, 230, 230))
panel.save(HERE / "comparison_restored_skull.jpg", quality=90)

# ---------------------------------------------------------------- report
out = ["# Phase 0: reproduction of Boxer (2012)", "",
       "Input: Wikimedia `Holbein-ambassadors.jpg`, 1084 x 1069 px, sha1 0543318124d91bf44070b07ae991faf1a98c4134.",
       "Panel 2095 x 2070 mm. Convention: dx right of the right edge, dy above the bottom edge, dz off the wall.", "",
       "| quantity | ours | Boxer | diff | unit |", "|---|---|---|---|---|"]
for name, ours, his, diff, unit in rows:
    out.append(f"| {name} | {ours:.3f} | {'' if his is None else f'{his:.3f}'} | {'' if diff is None else f'{diff:+.3f}'} | {unit} |")
out += ["", "Images: `restored_painting_inverse_trapezoid.jpg`, `restored_skull_inverse_trapezoid.png`, "
        "`restored_skull_perspective.png`, `comparison_restored_skull.jpg` (ours beside Boxer's OptimalSkull.jpg)."]
(HERE / "reproduction_table.md").write_text("\n".join(out))
json.dump({"D": D, "d": d, "trapezoid_eye": (dx_t, dy_t, dz_t), "R": R, "alpha_deg": al,
           "perspective_eye": (dx_p, dy_p, dz_p), "skull_metrics_trapezoid": m_t, "skull_metrics_perspective": m_p,
           "identity": {"R": R_alg, "alpha_deg": a_alg, "max_err_mm": identity_err},
           "brief_relation": {"R": R_brief, "alpha_deg": a_brief}},
          open(HERE / "reproduction.json", "w"), indent=1)
print("\n".join(out))
