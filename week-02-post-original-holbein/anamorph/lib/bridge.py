"""Units bridge: SHARP camera frame (metres, assumed focal) <-> Boxer panel frame (mm).

SHARP frame (OpenCV): origin at the photo's camera, x right, y DOWN, z forward (into the scene).
The painting fills the input image, so the panel's edges are the image edges.

Panel frame (Boxer): origin at the panel's lower-left corner, x right along the wall, y UP,
z OUT of the wall toward the viewer.  Report convention (dx, dy, dz): dx = x - 2095, dy = y, dz = z.

Procedure (every assumption is explicit and logged into the Panel object):
 1. Project every Gaussian back into the original image with the run's f_px (pinhole, principal
    point at the image centre, the convention of sharp.cli.predict).
 2. The "panel plane" is fitted (PCA / total least squares) to opaque Gaussians whose projection
    lies in the outer border band of the image (default 4 % of width/height).  Reason: the border
    of a painting is the frame/wall region and is where a physical panel would be, whereas the
    depicted subjects may be reconstructed at depicted (fictive) depth.  A global fit is logged too.
 3. In-plane axes: u = image-right projected into the plane, v = image-up projected into the plane,
    n = plane normal oriented toward the camera.
 4. Panel edges: left/right = 2nd/98th percentile of u over Gaussians in the left/right border band,
    bottom/top likewise with v.  The metric scale is s = 2095 mm / (right - left); the y scale
    2070 / (top - bottom) is logged separately as a consistency check (they should agree to ~1 %).
 5. A point P (SHARP metres) maps to mm: x = ((P - O) . u) s, y = ((P - O) . v) s, z = ((P - O) . n) s.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict

import numpy as np

LX, LY = 2095.0, 2070.0


def load_ply_xyz(path):
    from plyfile import PlyData
    v = PlyData.read(str(path))["vertex"]
    xyz = np.stack([v["x"], v["y"], v["z"]], 1).astype(np.float64)
    op = 1 / (1 + np.exp(-np.asarray(v["opacity"], dtype=np.float64)))
    sc = np.exp(np.stack([v["scale_0"], v["scale_1"], v["scale_2"]], 1).astype(np.float64))
    return xyz, op, sc


def project(xyz, f_px, W, H):
    u = f_px * xyz[:, 0] / xyz[:, 2] + W / 2
    v = f_px * xyz[:, 1] / xyz[:, 2] + H / 2
    return u, v


def fit_plane(pts):
    c = pts.mean(0)
    _, sv, vt = np.linalg.svd(pts - c, full_matrices=False)
    n = vt[2]
    rms = float(np.sqrt(np.mean(((pts - c) @ n) ** 2)))
    return c, n, rms


@dataclass
class Panel:
    origin: list          # SHARP-frame position of the panel's lower-left corner (m)
    u: list               # in-plane right axis (unit, SHARP frame)
    v: list               # in-plane up axis
    n: list               # normal toward the viewer
    scale_mm_per_unit: float
    scale_y_mm_per_unit: float
    width_units: float
    height_units: float
    plane_rms_border: float      # SHARP units (m)
    plane_rms_all: float
    n_border: int
    f_px: float
    image_size: list
    border_frac: float
    camera0_mm: list             # the photo's own camera expressed as (dx, dy, dz)
    depth_stats: dict

    # ---- conversions
    def to_mm(self, P):
        P = np.asarray(P, float) - np.asarray(self.origin)
        s = self.scale_mm_per_unit
        x, y, z = P @ np.asarray(self.u), P @ np.asarray(self.v), P @ np.asarray(self.n)
        return (float(x * s - LX), float(y * s), float(z * s))

    def to_sharp(self, dx, dy, dz):
        s = self.scale_mm_per_unit
        return (np.asarray(self.origin) + ((dx + LX) / s) * np.asarray(self.u) + (dy / s) * np.asarray(self.v)
                + (dz / s) * np.asarray(self.n)).tolist()

    def wall_point(self, x_mm, y_mm):
        """A point ON the panel (painting frame mm) in SHARP coordinates."""
        return self.to_sharp(x_mm - LX, y_mm, 0.0)

    def save(self, path):
        json.dump(asdict(self), open(path, "w"), indent=1)

    @staticmethod
    def load(path):
        return Panel(**json.load(open(path)))


def fit_panel(xyz, opacity, f_px, W, H, border_frac=0.04, min_opacity=0.5) -> Panel:
    u_px, v_px = project(xyz, f_px, W, H)
    inside = (u_px >= 0) & (u_px < W) & (v_px >= 0) & (v_px < H) & (opacity > min_opacity)
    bw, bh = border_frac * W, border_frac * H
    left = inside & (u_px < bw); right = inside & (u_px > W - bw)
    bottom = inside & (v_px > H - bh); top = inside & (v_px < bh)     # image v is DOWN
    border = left | right | bottom | top
    c, n, rms_b = fit_plane(xyz[border])
    _, _, rms_all = fit_plane(xyz[inside])
    if n[2] > 0:
        n = -n                                   # toward the camera (camera looks +z)
    ex, ey_up = np.array([1.0, 0, 0]), np.array([0, -1.0, 0])
    uax = ex - (ex @ n) * n; uax /= np.linalg.norm(uax)
    vax = ey_up - (ey_up @ n) * n - (ey_up @ uax) * uax; vax /= np.linalg.norm(vax)
    a = (xyz - c) @ uax; b = (xyz - c) @ vax
    L, Rr = np.percentile(a[left], 2), np.percentile(a[right], 98)
    Bo, T = np.percentile(b[bottom], 2), np.percentile(b[top], 98)
    origin = c + L * uax + Bo * vax
    width, height = Rr - L, T - Bo
    z = xyz[inside, 2]
    panel = Panel(origin=origin.tolist(), u=uax.tolist(), v=vax.tolist(), n=n.tolist(),
                  scale_mm_per_unit=float(LX / width), scale_y_mm_per_unit=float(LY / height),
                  width_units=float(width), height_units=float(height),
                  plane_rms_border=rms_b, plane_rms_all=rms_all, n_border=int(border.sum()),
                  f_px=float(f_px), image_size=[int(W), int(H)], border_frac=border_frac, camera0_mm=[0, 0, 0],
                  depth_stats={"z_min": float(z.min()), "z_p05": float(np.percentile(z, 5)), "z_median": float(np.median(z)),
                               "z_p95": float(np.percentile(z, 95)), "z_max": float(z.max()),
                               "relief_p95_minus_p05": float(np.percentile(z, 95) - np.percentile(z, 5)),
                               "panel_plane_depth_at_centre": float(c[2])})
    panel.camera0_mm = list(panel.to_mm([0.0, 0.0, 0.0]))
    return panel


def depth_map(xyz, opacity, f_px, W, H, res=256):
    """Median depth per pixel bin of the Gaussians projected into the original camera."""
    u_px, v_px = project(xyz, f_px, W, H)
    ok = (u_px >= 0) & (u_px < W) & (v_px >= 0) & (v_px < H) & (opacity > 0.3)
    ix = (u_px[ok] / W * res).astype(int); iy = (v_px[ok] / H * res).astype(int)
    z = xyz[ok, 2]
    out = np.full((res, res), np.nan)
    order = np.lexsort((z, iy * res + ix)); key = (iy * res + ix)[order]; zs = z[order]
    starts = np.r_[0, np.nonzero(np.diff(key))[0] + 1]; ends = np.r_[starts[1:], len(key)]
    for s0, e0 in zip(starts, ends):
        out[key[s0] // res, key[s0] % res] = np.median(zs[s0:e0])
    return out


# ------------------------------------------------------------------------------ self test
def _selftest():
    """Synthetic panel: a plane at z0 with known extent, plus a camera at a known mm position."""
    W, H, f = 1084, 1069, 900.0
    z0 = 3.0
    # dense samples of the plane covering the full image, slight noise
    rng = np.random.default_rng(0)
    u = rng.uniform(0, W, 200000); v = rng.uniform(0, H, 200000)
    x = (u - W / 2) / f * z0; y = (v - H / 2) / f * z0
    xyz = np.stack([x, y, np.full_like(x, z0) + rng.normal(0, 1e-4, len(x))], 1)
    panel = fit_panel(xyz, np.ones(len(xyz)), f, W, H)
    width_true = W / f * z0
    s_true = LX / width_true
    assert abs(panel.scale_mm_per_unit - s_true) / s_true < 0.01, (panel.scale_mm_per_unit, s_true)
    assert abs(panel.scale_y_mm_per_unit / panel.scale_mm_per_unit - 1) < 0.02
    cam = panel.to_mm([0, 0, 0])
    assert abs(cam[0] + LX / 2) < 15 and abs(cam[1] - LY / 2) < 15 and abs(cam[2] - z0 * s_true) < 15, cam
    # a camera placed at Boxer's O and back again
    P = panel.to_sharp(776.9, 1035, 257.9)
    back = panel.to_mm(P)
    assert np.allclose(back, (776.9, 1035, 257.9), atol=1e-6), back
    # it should sit 257.9 mm in front of the wall: distance to the plane
    assert abs(P[2] - z0 + 257.9 / s_true) < 1e-3, P
    # tilted panel (rotate the plane 6 deg about the vertical axis): camera must map consistently
    th = np.radians(6.0); Rm = np.array([[np.cos(th), 0, np.sin(th)], [0, 1, 0], [-np.sin(th), 0, np.cos(th)]])
    xyz_t = (xyz - [0, 0, z0]) @ Rm.T + [0, 0, z0]
    panel_t = fit_panel(xyz_t, np.ones(len(xyz)), f, W, H)
    n = np.asarray(panel_t.n)
    assert abs(np.degrees(np.arccos(-n[2])) - 6.0) < 0.5, n
    print("bridge self-test OK", {"scale": panel.scale_mm_per_unit, "expected": s_true, "camera0_mm": cam})


if __name__ == "__main__":
    _selftest()


# ------------------------------------------------------------------------------ fronto-parallel variants
def fit_panel_frontoparallel(xyz, opacity, f_px, W, H, region_px=None, min_opacity=0.5, label="fp"):
    """Panel = plane perpendicular to the camera axis at the reference depth z_ref, where z_ref is the
    median depth of opaque Gaussians projecting into region_px = (c0, c1, r0, r1) (default: whole image).
    Extents come from the camera frustum at z_ref (the painting fills the image), so the mm scale is
    s = 2095 / (W * z_ref / f_px).  The photo camera then maps EXACTLY to (-Lx/2, Ly/2, z_ref*s) by construction."""
    u_px, v_px = project(xyz, f_px, W, H)
    ok = (u_px >= 0) & (u_px < W) & (v_px >= 0) & (v_px < H) & (opacity > min_opacity)
    if region_px is not None:
        c0, c1, r0, r1 = region_px
        ok &= (u_px >= c0) & (u_px <= c1) & (v_px >= r0) & (v_px <= r1)
    z_ref = float(np.median(xyz[ok, 2]))
    width = W * z_ref / f_px; height = H * z_ref / f_px
    origin = np.array([-width / 2, height / 2, z_ref])       # lower-left corner (image y is down => +y is bottom)
    _, _, rms_region = fit_plane(xyz[ok])
    zz = xyz[ok, 2]
    panel = Panel(origin=origin.tolist(), u=[1, 0, 0], v=[0, -1, 0], n=[0, 0, -1],
                  scale_mm_per_unit=float(LX / width), scale_y_mm_per_unit=float(LY / height),
                  width_units=float(width), height_units=float(height), plane_rms_border=rms_region, plane_rms_all=rms_region,
                  n_border=int(ok.sum()), f_px=float(f_px), image_size=[int(W), int(H)], border_frac=0.0, camera0_mm=[0, 0, 0],
                  depth_stats={"z_ref": z_ref, "z_p05": float(np.percentile(zz, 5)), "z_median": z_ref, "z_p95": float(np.percentile(zz, 95)),
                               "relief_p95_minus_p05": float(np.percentile(zz, 95) - np.percentile(zz, 5)), "label": label,
                               "region_px": None if region_px is None else [float(x) for x in region_px]})
    panel.camera0_mm = list(panel.to_mm([0.0, 0.0, 0.0]))
    return panel


def skull_region_px(W, H):
    """Boxer's marked skull points' bounding box, painting mm -> image pixels (c0, c1, r0, r1)."""
    xs = np.array([661, 615, 1083.2, 1530, 1210.0]); ys = np.array([0, 58, 337, 472, 257.0])
    c = xs / LX * (W - 1); r = (H - 1) - ys / LY * (H - 1)
    return (float(c.min()), float(c.max()), float(r.min()), float(r.max()))


def panel_variants(xyz, opacity, f_px, W, H):
    """All panel definitions we carry: primary = skull-anchored fronto-parallel."""
    return {
        "skull_frontoparallel": fit_panel_frontoparallel(xyz, opacity, f_px, W, H, skull_region_px(W, H), label="skull"),
        "median_frontoparallel": fit_panel_frontoparallel(xyz, opacity, f_px, W, H, None, label="median"),
        "border_plane": fit_panel(xyz, opacity, f_px, W, H),
    }


def skull_lateral_extent_units(xyz, opacity, f_px, W, H):
    """Reconstructed lateral extent of the skull (SHARP units) for a skull-anchored scale check:
    Boxer says the anamorphic skull spans 915 mm laterally in the painting."""
    c0, c1, r0, r1 = skull_region_px(W, H)
    u_px, v_px = project(xyz, f_px, W, H)
    ok = (u_px >= c0) & (u_px <= c1) & (v_px >= r0) & (v_px <= r1) & (opacity > 0.5)
    x = xyz[ok, 0]
    return float(np.percentile(x, 99) - np.percentile(x, 1))
