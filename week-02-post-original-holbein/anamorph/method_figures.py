"""Analytical drawings for the Method tab (figures/method/*.png).
Drawing convention borrowed from retroactive photogrammetry plates: white ground, thin black construction lines,
dashed projectors, red annotation in a monospaced face, the photograph itself placed in the drawing as the
picture plane.  All geometry is in Boxer's panel frame (mm)."""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Ellipse, Polygon
from PIL import Image

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "boxer_repro")); sys.path.insert(0, str(ROOT / "lib"))
import boxer as B
from bridge import Panel, load_ply_xyz, project as img_project

OUT = ROOT / "figures" / "method"; OUT.mkdir(parents=True, exist_ok=True)
RED, INK, GREY, LIGHT = "#c8102e", "#111111", "#7a7a7a", "#c9c9c9"
MONO = {"family": "monospace", "size": 8, "color": RED}
plt.rcParams.update({"font.family": "monospace", "font.size": 8, "axes.linewidth": 0.5})
LX, LY = B.LX, B.LY
D, d = B.solve_trapezoid()
S = (LX / 2 + D, LY / 2); O = (LX / 2 + D, d)
painting = Image.open(ROOT / "data" / "Holbein-ambassadors.jpg").convert("L")
run30 = ROOT / "runs" / "sharp_wiki_f30"
info = json.load(open(run30 / "run.json")); panel = Panel.load(run30 / "panel_skull_frontoparallel.json")
xyz, op, _ = load_ply_xyz(run30 / "model.ply")


DPI = 200          # plates are read at full width and opened in the viewer, so they carry real resolution
HAIR, FINE, FIRM = 0.35, 0.55, 0.9      # one line-weight vocabulary for every plate


def clean(ax):
    ax.set_aspect("equal"); ax.axis("off")


def leader(ax, xy, xytext, text, color=RED, size=6.5, ha="left", va="center", rot=0):
    """Hairline leader from the thing to its name, set in clear space. No frame, no arrowhead:
    the line simply touches what it labels, the way a survey annotation does."""
    ax.annotate(text, xy=xy, xytext=xytext, textcoords="data", rotation=rot,
                color=color, family="monospace", fontsize=size, ha=ha, va=va, zorder=8,
                arrowprops=dict(arrowstyle="-", color=color, lw=HAIR, shrinkA=0, shrinkB=2.5))


def along(ax, p0, p1, text, frac=0.5, off=16, color=RED, size=6.5, ha="center"):
    """Label laid along a line and rotated to follow it, so the drawing reads without a key."""
    (x0, y0), (x1, y1) = p0, p1
    ang = np.degrees(np.arctan2(y1 - y0, x1 - x0))
    if ang > 90: ang -= 180
    if ang < -90: ang += 180
    nx, ny = -(y1 - y0), (x1 - x0)
    n = np.hypot(nx, ny) or 1.0
    ax.text(x0 + frac * (x1 - x0) + off * nx / n, y0 + frac * (y1 - y0) + off * ny / n, text,
            rotation=ang, rotation_mode="anchor", ha=ha, va="bottom",
            color=color, family="monospace", fontsize=size, zorder=8)


def scalebar(ax, x, y, length=500, color=INK, size=6.5):
    """Bar scale, drawn at the same weight as the construction so it sits inside the drawing."""
    ax.plot([x, x + length], [y, y], color=color, lw=FINE, solid_capstyle="butt", zorder=6)
    for xx in (x, x + length):
        ax.plot([xx, xx], [y - 14, y + 14], color=color, lw=FINE, zorder=6)
    ax.text(x + length / 2, y + 22, f"{length:.0f} mm", ha="center", va="bottom",
            color=color, family="monospace", fontsize=size, zorder=6)


def dim(ax, p0, p1, text, color=RED, size=6.5, off=20, rot_follow=True):
    """Measured span: hairline arrows at both ends, value set along the span, never boxed."""
    (x0, y0), (x1, y1) = p0, p1
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0), zorder=6,
                arrowprops=dict(arrowstyle="<|-|>", color=color, lw=HAIR, mutation_scale=5,
                                shrinkA=0, shrinkB=0))
    if rot_follow:
        along(ax, p0, p1, text, off=off, color=color, size=size)
    else:
        ax.text((x0 + x1) / 2, (y0 + y1) / 2 + off, text, ha="center", va="bottom",
                color=color, family="monospace", fontsize=size, zorder=8)


def label(ax, x, y, text, rot=0, ha="left", va="bottom", color=RED, size=6.5):
    """Plain text set directly in the drawing, no frame."""
    ax.text(x, y, text, rotation=rot, ha=ha, va=va, color=color, family="monospace", fontsize=size, zorder=8)


def sharp_floor_profile(row_frac=0.90, band=0.03, ncol=48):
    """Robust depth profile of SHARP's reconstruction along an image row, in panel mm.
    Median of the central 60 % of depths per column bin (trims floaters)."""
    u, v = img_project(xyz, info["f_px"], info["width"], info["height"])
    row = (v > (row_frac - band) * info["height"]) & (v < (row_frac + band) * info["height"]) & (op > 0.6)
    xs, zs = [], []
    for c in np.linspace(0.02, 0.98, ncol) * info["width"]:
        sel = row & (np.abs(u - c) < info["width"] / (2 * ncol))
        if sel.sum() < 40:
            continue
        z = xyz[sel, 2]; lo, hi = np.percentile(z, [20, 80]); keep = sel.copy(); keep[sel] = (z >= lo) & (z <= hi)
        P = np.median(xyz[keep], axis=0)
        mm = panel.to_mm(P); xs.append(mm[0] + LX); zs.append(mm[2])
    return np.array(xs), np.array(zs)


LEGEND_MARK = {"National Gallery 1997": "s", "Boxer inverseTrapezoid.m": "o", "Boxer anamorphic.m": "^", "Boxer 8x8 grid hypothesis": "x"}


def published_legend(ax, x, y, zsc=1.0, size=7, step=34):
    """Marker legend for the four published points, drawn as text rows starting at (x, y) going down."""
    for i, (name, (dx, dy, dz)) in enumerate(B.PUBLISHED.items()):
        yy = y - i * step
        ax.plot([x], [yy], LEGEND_MARK[name], color=INK, ms=6, mfc="white" if LEGEND_MARK[name] != "x" else INK, mew=0.8)
        label(ax, x + 28, yy, f"{name}  ({dx:.0f}, {dy:.0f}, {dz:.0f})", va="center", color=INK, size=size)


# ------------------------------------------------------------------------- 1. resection plate
def fig_resection():
    fig = plt.figure(figsize=(15, 13))
    ax = fig.add_axes([0.03, 0.03, 0.94, 0.94]); clean(ax)
    ax.imshow(painting, cmap="gray", extent=[0, LX, 0, LY], zorder=1)
    ax.plot([0, LX], [0, 0], color=INK, lw=FIRM, zorder=4)                     # picture plane, seen edge-on
    for i in range(9):
        ax.plot([i * LX / 8, i * LX / 8], [0, -46], color=INK, lw=HAIR)
        if i < 8:
            label(ax, (i + 0.5) * LX / 8, -68, str(i + 1), color=GREY, size=6, ha="center", va="top")
    zsc = -1.0                                                                # plan below, z downwards = out from the wall

    # --- Boxer's construction
    ax.plot([LX / 2, S[0]], [0, 0], color=RED, lw=FINE, ls="--", zorder=4)
    ax.plot([S[0], O[0]], [0, zsc * O[1]], color=RED, lw=FINE, zorder=4)
    ax.plot([S[0]], [0], "o", ms=4, color=RED, zorder=5); ax.plot([O[0]], [zsc * O[1]], "o", ms=4, color=RED, zorder=5)
    label(ax, S[0] + 22, 10, "S = (x0 + D, y0),  D = %.2f mm" % D)
    label(ax, LX / 2 + 26, -140, "I = (x0, y0), panel centre")
    ax.plot([661, S[0]], [0, 0], color="#f08c00", lw=HAIR, ls="--", zorder=4)

    # --- the anamorphic extent and the rays that define it
    for x in (615, 1530):
        ax.plot([O[0], x], [zsc * O[1], 0], color=INK, lw=HAIR, ls=":", zorder=4)
    for x, y in B.SKULL_PTS:
        ax.plot([x], [0], "+", color=RED, ms=7, mew=1.0, zorder=5)
    ax.plot([615, 1530], [-16, -16], color=RED, lw=FINE, zorder=5)
    dim(ax, (615, -104), (1530, -104), "anamorphic skull, 915 mm lateral extent", off=14)

    # --- SHARP's reconstructed surface along three image rows
    for rf, lw in ((0.80, 0.6), (0.90, 1.4), (0.97, 0.6)):
        xs, zs = sharp_floor_profile(rf)
        ax.plot(xs, zsc * zs, color=GREY, lw=lw, zorder=3)
        if rf == 0.90:
            ax.fill_between(xs, 0, zsc * zs, color=LIGHT, alpha=0.45, zorder=2)
        label(ax, xs[-1] + 16, zsc * zs[-1], f"image row {int(rf*100)} %", color=GREY, va="center", size=7)

    # --- published station points, uncertainty, and the model's own maxima
    for name, (dx, dy, dz) in B.PUBLISHED.items():
        ax.plot([LX + dx], [zsc * dz], LEGEND_MARK[name], color=INK, ms=7,
                mfc="white" if LEGEND_MARK[name] != "x" else INK, mew=0.9, zorder=6)
    ax.add_patch(Ellipse((LX + 776.9, zsc * 257.9), 80, 16, fill=False, ec=RED, lw=FINE, zorder=6))
    label(ax, LX + 776.9 + 56, zsc * 257.9 + 34, "2σ = 40 × 8 mm")

    g = json.load(open(run30 / "grid_stats.json"))["resemblance"]["peak"]
    ax.plot([LX + g["dx"]], [zsc * g["dz"]], "*", color=RED, ms=13, mec=INK, mew=0.6, zorder=7)
    # the headline disagreement, drawn as a measured span
    resid = float(np.hypot(g["dx"] - 776.9, g["dz"] - 257.9))
    ax.annotate("", xy=(LX + 776.9, zsc * 257.9), xytext=(LX + g["dx"], zsc * g["dz"]),
                arrowprops=dict(arrowstyle="<|-|>", color=RED, lw=FINE, mutation_scale=7, shrinkA=0, shrinkB=0), zorder=6)

    fine = sorted(json.load(open(run30 / "fine_metrics.json")), key=lambda r: -r["resemblance"])[0] if (run30 / "fine_metrics.json").exists() else None
    if fine:
        ax.plot([LX + fine["dx"]], [zsc * fine["dz"]], "*", color="white", ms=13, mec=RED, mew=1.0, zorder=7)
        leader(ax, (LX + fine["dx"], zsc * fine["dz"]), (LX + 430, zsc * 1360),
               "SHARP resemblance maximum, orbit  eye %.0f mm" % fine["dy"], color=RED, size=6.5, ha="left")

    # The photograph's camera lies 2040 mm out. Drawing it on-sheet would compress the station
    # points — which sit between 120 and 259 mm — into an unreadable band, so it is referenced
    # off-sheet and its sight lines are shown only where they cross the plotted region.
    cam = panel.camera0_mm
    for x_t in (615, 1530):
        ax.plot([LX + cam[0], x_t], [zsc * cam[2], 0], color=INK, lw=HAIR, ls=":", zorder=3)
    ax.annotate("photo camera as SHARP places it,\nΔz = %.0f mm (off sheet, assumed 30 mm lens)" % cam[2],
                xy=(LX + cam[0] * 0.42, zsc * 860), xytext=(LX - 1050, zsc * 1180),
                color=INK, family="monospace", fontsize=7.5, va="center", zorder=8,
                arrowprops=dict(arrowstyle="-|>", color=INK, lw=HAIR, mutation_scale=9))

    # The four published points fall inside a 140 mm band. Rather than a framed detail box, each
    # is drawn out on a hairline leader, which keeps the plan intact and the cluster readable.
    fanned = [("National Gallery 1997", 790, 120, 430),
              ("Boxer inverseTrapezoid.m", 776.9, 257.9, 610),
              ("Boxer anamorphic.m", 740.5, 255.3, 790),
              ("Boxer 8\u00d78 grid hypothesis", 785.625, 258.75, 970)]
    for name, dx, dz, drop in fanned:
        leader(ax, (LX + dx, zsc * dz), (LX + 430, zsc * drop),
               f"{name}  ({dx:.1f}, {dz:.1f})", color=INK, size=6.5, ha="left")
    leader(ax, (LX + g["dx"], zsc * g["dz"]), (LX + 430, zsc * 1180),
           "SHARP resemblance maximum, grid  (%.0f, %.0f) at %.2f" % (g["dx"], g["dz"], g["value"]),
           color=RED, size=6.5, ha="left")

    # The picture plane and the plan necessarily share one scale, which leaves the station points —
    # all of them between 120 and 259 mm off the wall — inside a 140 mm band. A detail box at larger
    # scale carries that band without distorting the angles in the main plan.

    scalebar(ax, -180, zsc * 1400, 500)
    ax.set_xlim(-340, LX + 1500); ax.set_ylim(zsc * 1520, LY + 120)
    fig.savefig(OUT / "resection_plate.png", dpi=DPI, facecolor="white"); plt.close(fig)


# ------------------------------------------------------------------------- 1b. resolution ladder
def fig_resolution():
    """What the study actually measures on. The Wikimedia file beside the Google Art Project scan
    at the same crop, and the detail the smaller file cannot carry."""
    gap_path = ROOT / "data" / "gigapixel" / "ambassadors_gap_3840.jpg"
    if not gap_path.exists():
        print("skip fig_resolution: no gigapixel scan"); return
    wiki = Image.open(ROOT / "data" / "Holbein-ambassadors.jpg").convert("L")
    gap = Image.open(gap_path).convert("L")
    # same normalised crop on the skull in both files
    box = (0.26, 0.72, 0.76, 0.95)
    def crop(im):
        w, h = im.size
        return im.crop((int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)))
    cw, cg = crop(wiki), crop(gap)
    target = cg.size
    up = cw.resize(target, Image.NEAREST)                       # the small file blown up, no invention
    diff = np.abs(np.asarray(up, float) - np.asarray(cg, float))

    fig, axes = plt.subplots(1, 3, figsize=(15, 3.6))
    for ax in axes: clean(ax)
    axes[0].imshow(up, cmap="gray"); axes[1].imshow(cg, cmap="gray")
    axes[2].imshow(diff, cmap="magma", vmin=0, vmax=np.percentile(diff, 99))
    for ax, t in zip(axes, [f"Wikimedia {wiki.size[0]} \u00d7 {wiki.size[1]} px\nthe file every measurement uses",
                            f"Google Art Project {gap.size[0]} px\nsame crop, {gap.size[0] / wiki.size[0]:.1f}\u00d7 the linear sampling",
                            "absolute difference\nbright = detail the smaller file cannot carry"]):
        ax.set_title(t, fontsize=7.5, family="monospace", color=INK, pad=6, loc="left")
    fig.subplots_adjust(wspace=0.04)
    fig.savefig(OUT / "resolution_ladder.png", dpi=DPI, facecolor="white", bbox_inches="tight"); plt.close(fig)


# ------------------------------------------------------------------------- 2. tie points plate
def fig_tiepoints():
    fig, ax = plt.subplots(figsize=(11, 11)); clean(ax)
    ax.imshow(painting, cmap="gray", extent=[0, LX, 0, LY])
    names = ["chin", "eye socket", "top of cranium", "right extremum", "jaw corner"]
    for i, ((x, y), n) in enumerate(zip(B.SKULL_PTS, names), 1):
        ax.plot(x, y, "+", color="#ff7a00", ms=15, mew=1.6, zorder=6)
        ax.text(x + 16, y + 14, f"P{i}", color="#ff7a00", family="monospace", fontsize=11,
                fontweight="bold", zorder=7)
    ax.plot([661, LX], [0, (LX - 661) * 257 / 549], color="#ff7a00", lw=HAIR, ls="--")
    along(ax, (661, 0), (LX, (LX - 661) * 257 / 549), "jaw line, 25.1\u00b0, extended to eye level at S",
          frac=0.72, off=20, color="#ff7a00", size=7.5)
    ax.plot([LX / 2, LX / 2], [0, LY], color="cyan", lw=HAIR, ls=":"); ax.plot([0, LX], [LY / 2, LY / 2], color="cyan", lw=HAIR, ls=":")
    label(ax, LX / 2 + 10, LY - 40, "central axis x0 = Lx/2", color="cyan", size=9); label(ax, 20, LY / 2 + 12, "eye level y0 = Ly/2 = 1035 mm", color="cyan", size=9)
    ax.add_patch(plt.Rectangle((615, 0), 915, 472, fill=False, ec="#ffd400", lw=HAIR))
    leader(ax, (1072, 472), (LX + 90, 250), "skull box, 615\u20131530 \u00d7 0\u2013472 mm", color="#c79a00", size=7.5, ha="left")
    for i in range(1, 8):
        ax.plot([i * LX / 8] * 2, [0, LY], color="white", lw=HAIR, alpha=0.5); ax.plot([0, LX], [i * LY / 8] * 2, color="white", lw=HAIR, alpha=0.5)
    ax.plot([LX / 2 + 3 * LX / 8], [LY / 2], "o", color="cyan", ms=5, clip_on=False)
    ax.set_xlim(-40, LX + 1250); ax.set_ylim(-70, LY + 70)
    ax.plot([LX, LX + 3 * LX / 8], [LY / 2, LY / 2], color="cyan", lw=FINE); label(ax, LX + 3 * LX / 8 + 15, LY / 2, "S = 3 grid units right of the edge", color="cyan", size=9, va="center")
    # every point names itself where it sits; the fan keeps the cluster legible
    # named off the picture, on clear ground, so orange type never sits on dark paint
    for i, ((x, y), n) in enumerate(zip(B.SKULL_PTS, names), 1):
        leader(ax, (x, y), (LX + 90, 860 - i * 105), f"P{i}  {n}  ({x:.0f}, {y:.0f})",
               color="#ff7a00", size=7.5, ha="left")
    scalebar(ax, LX + 90, -40, 500)
    fig.savefig(OUT / "tiepoints_plate.png", dpi=DPI, facecolor="white", bbox_inches="tight"); plt.close(fig)


# ------------------------------------------------------------------------- 3. section through the eye
def _seg_hit(p0, p1, q0, q1):
    """Intersection of segments p0-p1 and q0-q1, or None. Used to locate where a sight line from
    Boxer's O first meets SHARP's reconstructed surface."""
    (x1, y1), (x2, y2), (x3, y3), (x4, y4) = p0, p1, q0, q1
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-9:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
    u = ((x1 - x3) * (y1 - y2) - (y1 - y3) * (x1 - x2)) / den
    if 0 <= t <= 1 and 0 <= u <= 1:
        return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
    return None


def fig_section():
    fig, ax = plt.subplots(figsize=(15, 7.5)); clean(ax)
    # section: horizontal axis = Δz (mm off the wall, right = toward the viewer), vertical = height
    ax.plot([0, 0], [0, LY], color=INK, lw=FIRM, zorder=4)
    label(ax, 14, LY + 26, "panel, seen in section", color=INK, size=7)
    ax.plot([-60, 2250], [0, 0], color=INK, lw=HAIR)
    ax.plot([0, 2250], [1035, 1035], color=RED, lw=HAIR, ls="--")
    along(ax, (0, 1035), (2250, 1035), "eye level, 1035 mm above the bottom edge", frac=0.55, off=9, color=RED, size=6.5)
    ax.plot([0, 0], [0, 472], color="#ffd400", lw=4.0, alpha=0.9, solid_capstyle="butt", zorder=5)
    leader(ax, (0, 236), (-360, 470), "skull box on the panel\n0\u2013472 mm", color="#b89000", size=6.5, ha="right")

    # SHARP relief in section along the column through the skull (x = 1072 mm), robust per row
    u, v = img_project(xyz, info["f_px"], info["width"], info["height"])
    ys, zs = [], []
    for r in np.linspace(0.02, 0.98, 45) * info["height"]:
        sel = (np.abs(v - r) < info["height"] / 60) & (np.abs(u - info["width"] * 0.51) < info["width"] / 12) & (op > 0.6)
        if sel.sum() < 40: continue
        z = xyz[sel, 2]; lo, hi = np.percentile(z, [20, 80]); keep = sel.copy(); keep[sel] = (z >= lo) & (z <= hi)
        mm = panel.to_mm(np.median(xyz[keep], axis=0)); ys.append(mm[1]); zs.append(mm[2])
    ax.plot(zs, ys, color=GREY, lw=FINE, zorder=3)
    ax.fill_betweenx(ys, 0, zs, color=LIGHT, alpha=0.45, zorder=2)
    leader(ax, (zs[len(zs) // 2], ys[len(ys) // 2]), (940, 640),
           "SHARP 30 mm, reconstructed surface\nat the skull's column: the floor stands\nforward of the panel, the curtain behind it",
           color=GREY, size=6.5)

    # sight lines from Boxer's O to the top and bottom of the skull box, and where they meet the relief
    relief = list(zip(zs, ys))
    for y_t in (0, 472):
        ax.plot([257.9, 0], [1035, y_t], color=INK, lw=HAIR, ls=":", zorder=4)
        for i in range(len(relief) - 1):
            hit = _seg_hit((257.9, 1035), (0, y_t), relief[i], relief[i + 1])
            if hit:
                ax.plot([hit[0]], [hit[1]], "o", ms=5, mfc="none", mec=RED, mew=0.7, zorder=7)
                leader(ax, hit, (620, hit[1] - 250), "sight line from O meets the\nreconstruction at \u0394z = %.0f mm" % hit[0],
                       color=RED, size=6.5)
                break
    leader(ax, (150, 700), (-560, 900), "rays from O to the top and\nbottom of the skull box", color=INK, size=6.5, ha="right")

    zmax = max(zs)
    dim(ax, (0, 1560), (zmax, 1560), "reconstructed relief at this column, %.0f mm" % zmax, off=9)
    dim(ax, (0, 1330), (257.9, 1330), "Boxer O, 257.9 mm off the wall", off=9)

    for name, (dx, dy, dz) in B.PUBLISHED.items():
        ax.plot(dz, dy, LEGEND_MARK[name], color=INK, ms=5, mfc="white" if LEGEND_MARK[name] != "x" else INK, mew=0.7, zorder=6)
    leader(ax, (120, 1035), (560, 1910), "National Gallery 1997 (790, 1040, 120)", color=INK, size=6.5)
    leader(ax, (257.9, 1035), (760, 1560),
           "Boxer inverseTrapezoid.m (776.9, 1035, 257.9)\nBoxer anamorphic.m (740.5, 1035, 255.3)\n8\u00d78 grid hypothesis (785.6, 1035, 258.8)", color=INK, size=6.5)

    cam = panel.camera0_mm
    ax.plot(cam[2], cam[1], "D", color=INK, ms=5, mfc="white", zorder=6)
    leader(ax, (cam[2], cam[1]), (cam[2] - 120, cam[1] + 330),
           "photo camera as SHARP places it\n\u0394z = %.0f mm, assumed 30 mm lens" % cam[2], color=INK, size=6.5, ha="right")

    scalebar(ax, 1700, 180, 500)
    ax.set_xlim(-780, 2320); ax.set_ylim(-140, LY + 150)
    fig.savefig(OUT / "section_plate.png", dpi=DPI, facecolor="white", bbox_inches="tight"); plt.close(fig)


# ------------------------------------------------------------------------- 4. the two eyes (screen orientation)
def fig_two_eyes():
    fig, ax = plt.subplots(figsize=(11, 6)); clean(ax)
    zsc = -1.0
    ax.plot([0, LX], [0, 0], color=INK, lw=FINE); label(ax, 0, 10, "panel, 2095 mm", color=INK)
    ax.plot([LX / 2, S[0]], [0, 0], color=RED, lw=HAIR, ls="--"); ax.plot([S[0], O[0]], [0, zsc * O[1]], color=RED, lw=FINE)
    ax.plot(S[0], 0, "o", ms=3, color=RED); ax.plot(O[0], zsc * O[1], "o", ms=4, color=RED); label(ax, O[0] + 15, zsc * O[1] - 6, "trapezoid eye O_t (776.9, 257.9)", va="top")
    # screen of the trapezoid: perpendicular to the wall through the central axis
    ax.plot([LX / 2, LX / 2], [0, zsc * 900], color=RED, lw=HAIR, ls=":"); label(ax, LX / 2 - 15, zsc * 880, "trapezoid screen: ⟂ wall, through x0", ha="right", rot=90, va="bottom")
    # perspective eye and its screen perpendicular to the line of sight
    R, al = 1806.136, 81.874; Ep = (LX / 2 + R * np.sin(np.radians(al)), R * np.cos(np.radians(al)))
    ax.plot(Ep[0], zsc * Ep[1], "^", ms=6, color="#0a7d5a"); label(ax, Ep[0] - 15, zsc * Ep[1] - 20, "perspective eye O_p (740.5, 255.3)\nR = 1806.1 mm, α = 81.87° from the normal", color="#0a7d5a", ha="right", va="top")
    ax.plot([Ep[0], LX / 2], [zsc * Ep[1], 0], color="#0a7d5a", lw=HAIR)
    # screen perpendicular to the line of sight at the centre
    dirv = np.array([LX / 2 - Ep[0], 0 - zsc * Ep[1]]); dirv /= np.linalg.norm(dirv); perp = np.array([-dirv[1], dirv[0]])
    ax.plot([LX / 2 + perp[0] * 600, LX / 2 - perp[0] * 600], [perp[1] * 600, -perp[1] * 600], color="#0a7d5a", lw=HAIR, ls=":"); label(ax, LX / 2 - perp[0] * 640, -perp[1] * 640, "perspective screen: ⟂ line of sight", color="#0a7d5a", size=7, ha="left", va="top")
    ax.annotate("", xy=(O[0], zsc * O[1]), xytext=(Ep[0], zsc * Ep[1]), arrowprops=dict(arrowstyle="<->", color=INK, lw=HAIR))
    leader(ax, ((O[0] + Ep[0]) / 2, zsc * (O[1] + Ep[1]) / 2), (LX + 520, zsc * 90), "36.4 mm apart", color=INK, size=6.5)
    ax.text(180, zsc * 560, "inverseTrapezoid(D, d)  \u2261  perspective(R, \u03b1)\n"
            "D = R / sin \u03b1          d = R cot \u03b1\n"
            "the 36.4 mm between the two published points is the\n"
            "orientation of the screen, not an approximation",
            ha="left", va="top", color=INK, family="monospace", fontsize=7.5, linespacing=1.7, zorder=8)
    scalebar(ax, 180, zsc * 960, 500)
    ax.set_xlim(-80, LX + 1180); ax.set_ylim(zsc * 1080, 140)
    fig.savefig(OUT / "two_eyes.png", dpi=DPI, facecolor="white", bbox_inches="tight"); plt.close(fig)


# ------------------------------------------------------------------------- 5. fan of SHARP cameras
def fig_fan():
    fig, ax = plt.subplots(figsize=(12, 10)); clean(ax)
    zsc = -1.0
    ax.imshow(painting, cmap="gray", extent=[0, LX, 0, LY], alpha=0.55)
    ax.plot([0, LX], [0, 0], color=INK, lw=FINE)
    rows = [r for r in json.load(open(run30 / "orbit_metrics.json")) if "resemblance" in r]
    rmax, rmin = max(r["resemblance"] for r in rows), min(r["resemblance"] for r in rows)
    sk = (1072.5, 0)
    for r in sorted(rows, key=lambda r: r["resemblance"]):
        x, z = LX + r["dx"], zsc * r["dz"]
        t = (r["resemblance"] - rmin) / (rmax - rmin + 1e-9)
        col = (0.78 - 0.5 * t, 0.06 + 0.2 * (1 - t), 0.18 * (1 - t) + 0.05, 0.10 + 0.55 * t)
        # view cone toward the skull centre (drawn as a thin triangle)
        v = np.array([sk[0] - x, sk[1] - z]); n = np.linalg.norm(v); v /= n; p = np.array([-v[1], v[0]])
        half = 0.09 * n
        ax.add_patch(Polygon([[x, z], [sk[0] + p[0] * half, sk[1] + p[1] * half], [sk[0] - p[0] * half, sk[1] - p[1] * half]], closed=True, fc=col, ec="none"))
        ax.plot(x, z, ".", color=RED if t > 0.9 else GREY, ms=2 + 6 * t)
    for name, (dx, dy, dz), m in zip(B.PUBLISHED, B.PUBLISHED.values(), "so^x"):
        ax.plot(LX + dx, zsc * dz, m, color="white", ms=7, mec=INK, mew=0.8)
    ax.add_patch(Ellipse((LX + 776.9, zsc * 257.9), 80, 16, fill=False, ec="white", lw=FINE))
    ax.set_xlim(-2600, LX + 2700); ax.set_ylim(zsc * 3000, LY + 40)
    label(ax, -2580, zsc * 2950, "Orbit overlay: 532 SHARP camera positions around the skull (plan), each drawn as its view cone; darker red = higher resemblance to the resolved skull (max 0.59).\nWhite markers: the published station points. Cameras above or below eye level are projected onto the plan.", color=INK, va="bottom")
    fig.savefig(OUT / "orbit_fan.png", dpi=DPI, facecolor="white", bbox_inches="tight"); plt.close(fig)


for f in (fig_resection, fig_resolution, fig_tiepoints, fig_section, fig_two_eyes, fig_fan):
    try:
        f(); print("ok", f.__name__)
    except Exception as e:  # noqa: BLE001
        import traceback; traceback.print_exc(); print("FAILED", f.__name__, e)
