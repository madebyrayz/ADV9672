"""Python port of Alexander Boxer's anamorphic.m and inverseTrapezoid.m
("Anamorphic Ambassadors", Idols of the Cave, May 2012).

Coordinate conventions (stated once here, used everywhere):

* Painting frame: x in mm from the LEFT edge, y in mm from the BOTTOM edge, z = 0 on the wall.
  Lx = 2095, Ly = 2070 (Wyld 1998).
* Viewing point O in the report convention (dx, dy, dz):
      dx = mm to the right of the painting's RIGHT edge,
      dy = viewing height, mm above the bottom edge,
      dz = mm out from the wall.
  Boxer's own tables write O = (O_x, O_y) with O_x = dx and O_y = dz (height fixed at Ly/2).
* Transformed frame: mm on the projection screen, origin at the image of the target point (x0, y0).

Both of Boxer's transforms are planar homographies, so instead of his scattered
interpolation we build the 3x3 matrix and inverse-warp the image (exact, fast).
"""

from __future__ import annotations

import numpy as np
from PIL import Image

LX, LY = 2095.0, 2070.0

# Boxer's five marked skull points, painting frame (mm), copied from inverseTrapezoid.m
SKULL_PTS = np.array(
    [
        [661.0, 0.0],      # s1 chin, lower-left corner
        [615.0, 58.0],     # s2 left eye-socket, left extremum
        [1083.2, 337.0],   # s3 top mid-point
        [1530.0, 472.0],   # s4 right extremum
        [1210.0, 257.0],   # s5 corner of jawbone
    ]
)

# Published viewing points, (dx, dy, dz) in mm
PUBLISHED = {
    "National Gallery 1997": (790.0, 1040.0, 120.0),
    "Boxer inverseTrapezoid.m": (776.9, 1035.0, 257.9),
    "Boxer anamorphic.m": (740.5, 1035.0, 255.3),
    "Boxer 8x8 grid hypothesis": (3 * LX / 8, LY / 2, LY / 8),
}
BOXER_SIGMA = (20.0, 4.0)  # 1-sigma in (dx, dz), mm
BOXER_D, BOXER_d = 1824.45, 257.88


# ----------------------------------------------------------------------------- transforms
def inverse_trapezoid(x, y, D, d, x0=LX / 2, y0=LY / 2):
    """Painting mm -> transformed mm (Boxer's inverse trapezoid, red diagram)."""
    xr, yr = np.asarray(x) - x0, np.asarray(y) - y0
    return d * xr / (D - xr), D * yr / (D - xr)


def forward_trapezoid(xp, yp, D, d, x0=LX / 2, y0=LY / 2):
    """Transformed mm -> painting mm (Kircher's forward trapezoid)."""
    xp, yp = np.asarray(xp), np.asarray(yp)
    return D * xp / (d + xp) + x0, d * yp / (d + xp) + y0


def perspective(x, y, R, alpha_deg, x0=LX / 2, y0=LY / 2, beta_deg=0.0, zscreen=None):
    """Painting mm -> screen mm, exactly as anamorphic.m: P = Rx(beta) Tz Ry(alpha) Txy P1,
    then x2 = zscreen * X/Z, y2 = zscreen * Y/Z.  alpha is measured from the wall NORMAL.
    Eye at the origin; target (x0, y0) at (0, 0, -R).  Default zscreen = -R."""
    if zscreen is None:
        zscreen = -R
    a, b = np.radians(alpha_deg), np.radians(beta_deg)
    xr, yr = np.asarray(x, float) - x0, np.asarray(y, float) - y0
    X = np.cos(a) * xr            # Ry: [cos,0,-sin; 0,1,0; sin,0,cos] applied to (xr, yr, 0)
    Z = np.sin(a) * xr - R        # then Tz
    Y = np.cos(b) * yr - np.sin(b) * Z   # Rx(beta)
    Z = np.sin(b) * yr + np.cos(b) * Z
    return zscreen * X / Z, zscreen * Y / Z


def eye_from_R_alpha(R, alpha_deg, x0=LX / 2, y0=LY / 2):
    """Physical eye position (dx, dy, dz) for anamorphic.m parameters."""
    a = np.radians(alpha_deg)
    return (x0 + R * np.sin(a) - LX, y0, R * np.cos(a))


def R_alpha_from_eye(dx, dz, x0=LX / 2):
    """Inverse of eye_from_R_alpha (dy is not involved when beta = 0)."""
    ex = LX + dx - x0
    return float(np.hypot(ex, dz)), float(np.degrees(np.arctan2(ex, dz)))


def trapezoid_eye(D, d, x0=LX / 2, y0=LY / 2):
    """Boxer's reported O for the trapezoid: S is D along the wall from x0, O is d off the wall."""
    return (D + x0 - LX, y0, d)


# ----------------------------------------------------------------------------- homographies
def homography(src, dst):
    """3x3 H with dst ~ H src (DLT on 4+ correspondences)."""
    src, dst = np.asarray(src, float), np.asarray(dst, float)
    A = []
    for (x, y), (u, v) in zip(src, dst):
        A.append([-x, -y, -1, 0, 0, 0, u * x, u * y, u])
        A.append([0, 0, 0, -x, -y, -1, v * x, v * y, v])
    _, _, vt = np.linalg.svd(np.asarray(A))
    H = vt[-1].reshape(3, 3)
    return H / H[2, 2]


def apply_h(H, x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    w = H[2, 0] * x + H[2, 1] * y + H[2, 2]
    return (H[0, 0] * x + H[0, 1] * y + H[0, 2]) / w, (H[1, 0] * x + H[1, 1] * y + H[1, 2]) / w


def painting_to_pixel_h(img_w, img_h):
    """Painting mm -> input pixel (col, row), Boxer's linspace(0, L, n) convention."""
    return np.array([[(img_w - 1) / LX, 0, 0], [0, -(img_h - 1) / LY, img_h - 1], [0, 0, 1.0]])


def transform_h(fn, **kw):
    """3x3 homography for one of the analytic transforms (painting mm -> transformed mm)."""
    corners = np.array([[0, 0], [0, LY], [LX, LY], [LX, 0], [LX / 2, LY / 3]], float)
    u, v = fn(corners[:, 0], corners[:, 1], **kw)
    return homography(corners, np.stack([u, v], 1))


def warp(img: Image.Image, fn, bounds=None, res=1.0, **kw):
    """Render the transformed painting.  bounds = (xmin, xmax, ymin, ymax) in transformed mm
    (default: bounding box of the transformed corners); res = mm per output pixel.
    Returns (PIL image, bounds actually used).  Output pixel (X, Y) <-> mm (xmin + X*res, ymax - Y*res)."""
    H = transform_h(fn, **kw)
    if bounds is None:
        c = np.array([[0, 0], [0, LY], [LX, LY], [LX, 0]], float)
        u, v = apply_h(H, c[:, 0], c[:, 1])
        bounds = (np.floor(u.min()), np.ceil(u.max()), np.floor(v.min()), np.ceil(v.max()))
    xmin, xmax, ymin, ymax = bounds
    W, Hh = int(round((xmax - xmin) / res)), int(round((ymax - ymin) / res))
    out_px_to_mm = np.array([[res, 0, xmin], [0, -res, ymax], [0, 0, 1.0]])
    M = painting_to_pixel_h(*img.size) @ np.linalg.inv(H) @ out_px_to_mm   # out px -> in px
    M = M / M[2, 2]
    coeffs = (M[0, 0], M[0, 1], M[0, 2], M[1, 0], M[1, 1], M[1, 2], M[2, 0], M[2, 1])
    out = img.transform((W, Hh), Image.PERSPECTIVE, coeffs, Image.BICUBIC, fillcolor=(0, 0, 0))
    return out, bounds


# ----------------------------------------------------------------------------- skull metrics
def skull_metrics(fn, **kw):
    """Boxer's diagnostics on the five marked points: width, height, aspect, jaw angle (deg), bbox."""
    u, v = fn(SKULL_PTS[:, 0], SKULL_PTS[:, 1], **kw)
    width, height = u.max() - u.min(), v.max() - v.min()
    jaw = np.degrees(np.arctan2(v[4] - v[0], u[4] - u[0]))
    return {
        "width": float(width), "height": float(height), "aspect": float(width / height),
        "jaw_angle_deg": float(jaw),
        "bbox_center": (float((u.max() + u.min()) / 2), float((v.max() + v.min()) / 2)),
        "bbox": (float(u.min()), float(u.max()), float(v.min()), float(v.max())),
    }


def solve_trapezoid(x0=LX / 2, y0=LY / 2, pts=SKULL_PTS):
    """Boxer's two conditions under the inverse trapezoid, in closed form.
    (i) jaw horizontal  -> the jaw line must pass through S = (x0 + D, y0)  -> fixes D.
    (ii) aspect ratio 1 -> x' scales linearly with d                       -> fixes d."""
    s1, s5 = pts[0], pts[4]
    jaw_tan = (s5[1] - s1[1]) / (s5[0] - s1[0])
    D = s1[0] + (y0 - s1[1]) / jaw_tan - x0
    m = skull_metrics(inverse_trapezoid, D=D, d=1.0, x0=x0, y0=y0)
    d = m["height"] / m["width"]
    return D, d


def solve_perspective(x0=LX / 2, y0=LY / 2, guess=(1800.0, 82.0)):
    """Boxer's two conditions under the exact perspective transform (numerical)."""
    from scipy.optimize import fsolve

    def f(p):
        R, al = p
        m = skull_metrics(perspective, R=R, alpha_deg=al, x0=x0, y0=y0)
        u, v = perspective(SKULL_PTS[:, 0], SKULL_PTS[:, 1], R, al, x0, y0)
        return [v[4] - v[0], m["width"] - m["height"]]

    R, al = fsolve(f, guess, xtol=1e-12)
    return float(R), float(al)
