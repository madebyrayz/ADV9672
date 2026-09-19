# Findings: anamorphic station point study (Holbein, Boxer, SHARP)

Ray Zhang, ADV9672, 9 September 2026. Everything below was measured with the scripts in this folder; the numbers are
read from `boxer_repro/reproduction.json`, `runs/phase1/basin_stats.json`, `runs/sharp_wiki_f*/grid_stats.json`,
`runs/sharp_wiki_f30/orbit_metrics.json`, `runs/phase4_sweep.json` and `runs/phase5_results.json`.

Conventions. Δx is millimetres to the right of the panel's right edge, Δy millimetres above the bottom edge, Δz
millimetres out from the wall. Panel 2095 × 2070 mm (Wyld 1998). The input image is Boxer's, Wikimedia
`Holbein-ambassadors.jpg`, 1084 × 1069 px, sha1 0543318124d91bf44070b07ae991faf1a98c4134.

## Phase 0. Boxer reproduces, to a fraction of a millimetre

The Python port of `inverseTrapezoid.m` and `anamorphic.m` (`boxer_repro/boxer.py`) recovers his numbers from his
five marked skull points and his two conditions:

| quantity | ours | Boxer |
|---|---|---|
| D (jaw line through S) | 1824.453 | 1824.45 |
| d (aspect ratio 1) | 257.882 | 257.88 |
| trapezoid O (Δx, Δy, Δz) | 776.95, 1035, 257.88 | 776.9, 1035, 257.9 |
| perspective O (anamorphic.m, x0 = Lx/2) | 740.50, 1035, 255.29 | 740.5, 1035, 255.3 |
| restored skull box | 142.14 mm square at (21.65, −783.00) | 142 mm at (21.65, −783.00) |
| jaw angle in the painting | 25.085° | 25.1° |

Both conditions turn out to be closed form under the trapezoid: the horizontal-jaw condition means the jaw line
must pass through S, which fixes D directly, and x' scales linearly with d, so d is the ratio of the restored
height to the restored width at d = 1. The restored painting and skull are visually identical to his
`InverseTrapezoidFinal.png` and `OptimalSkull.jpg` (`boxer_repro/comparison_restored_skull.jpg`).

One correction to the brief. Boxer's two transforms are not an approximation of each other but the same
function under a different parameterisation: perspective(R, α) equals inverse trapezoid(D, d) exactly when
D = R / sin α and d = R cot α (maximum difference over the panel 6 × 10⁻¹³ mm). The brief's relation
D = R sin α, d = R cos α, which is what Boxer writes as his intended geometry, gives R = 1842.6 mm and α = 81.96°, and
under it the two transforms differ by up to 64 mm across the panel. The exact identity gives R = 1806.1 mm,
α = 81.87°, and this reproduces his anamorphic.m point (740.5, 255.3) to 0.01 mm. So the 36 mm gap between his two
published points is not a small-angle error; it is the difference between reporting the eye of a trapezoid
construction (O at d off the wall above S) and the eye of a pinhole whose screen is perpendicular to the line of
sight. Both see the same image. Boxer's own weak points stand as he states them: the 1 % non-squareness of the
panel and the fact that the jaw line is a judgement.

## Phase 1. The perceptual basin of the flat model is 24 to 600 times larger than Boxer's ellipse

Sweep: Δx 300 to 1500 mm step 10, Δz 40 to 600 mm step 5, Δy = 1035, 13 700 viewpoints, exact perspective of
`anamorphic.m` with β = 0 and x0 = Lx/2, skull crop from the five marked points with a 1.35 margin, CLIP ViT-B-32.
Boxer's 2σ ellipse (radii 40 × 8 mm) has an area of 1005 mm².

| metric | peak (Δx, Δz) | area ≥ 95 % of peak | area ≥ 90 % | ratio 95 % area / ellipse |
|---|---|---|---|---|
| CLIP P(skull) vs negatives | 1090, 235 (0.99998) | 607 650 mm² | 629 300 mm² | 604 |
| CLIP cosine to skull prompts | 820, 115 (0.360) | 34 200 mm² | 238 600 mm² | 34 |
| CLIP resemblance to the resolved skull | 740, 255 (0.997) | 23 900 mm² | 143 100 mm² | 24 |
| bilateral symmetry | 1490, 40 (0.672) | 15 600 mm² | 44 200 mm² | 16 |

P(skull) saturates above 0.99 over essentially the whole grid: a skull stretched to twice its length is still a
skull to CLIP, so "skull-likeness" carries almost no information about location. This is the quantitative form of
Boxer's complaint about dragging corners in a graphics program until the skull looks acceptable. The resemblance
metric (image-to-image cosine against the crop at his anamorphic.m point, so it peaks there by construction) is the
most discriminating perceptual surface, and even its 95 % basin is 24 times the geometric ellipse; the two
surfaces disagree in shape (P(skull) is flat, resemblance is a broad diagonal ridge), and they are reported
separately. Symmetry peaks in the wrong place, as expected for a profile skull; it is reported because the brief
asked for it. Boxer's own two conditions carve a narrow diagonal valley (|aspect − 1| + |jaw|/10 in
`figures/perceptual_basin.png`, bottom right) about 60 mm wide in Δx and 300 mm long in Δz, which is the honest
shape of the geometric constraint before his second condition is applied.

Scores of the four published points on the flat model: National Gallery resemblance 0.909 (its aspect ratio is
0.45), trapezoid O 0.972, anamorphic.m O 0.997, grid hypothesis 0.967.

## Phase 2. SHARP does not reconstruct a panel

SHARP at its default 30 mm equivalent lens (f_px = 1055.6) reconstructs the depicted room, not a painted board:
median depth 2.00 m, 5th to 95th percentile 1.72 to 2.43 m, which in true panel units is 623 mm of relief across
a 2095 mm panel. The floor of the painting comes forward and the curtain recedes; a plane fitted to the outer
4 % border of the image is tilted 19.7° from the camera axis, and that tilt is the depicted floor, not a panel.

Units bridge (`lib/bridge.py`, self-tested on a synthetic plane). Because there is no panel in the
reconstruction, "the panel plane" is a choice. Three definitions are carried:

| definition | mm per SHARP unit | photo camera as (Δx, Δy, Δz) |
|---|---|---|
| skull-anchored fronto-parallel (primary) | 1095.3 | −1034, 1035, 2040 |
| global-median fronto-parallel | 1022.2 | −1034, 1035, 2040 |
| tilted border-band plane | 876.0 | −1034, 200, 1651 |

A fourth check, the skull's known 915 mm lateral extent against its reconstructed extent, gives 1035.8 mm per
unit, 6 % from the primary. The primary definition is used because the question is about the skull; the others
bracket the ambiguity. Every render job stores which bridge produced its pose.

Renders were made in the lab's own WebGL splat renderer (`static/render.html`, 768 px, 50° FOV, forced depth
sort per frame): 1421 frames on the same (Δx, Δz) grid as Phase 1 at 25 × 20 mm, camera looking horizontally at
the panel centre column as in anamorphic.m; a 532-frame orbit around the skull (azimuth −90° to 90° step 10,
elevation −45° to 45° step 15, 0.7, 1.4, 2.0 and 2.8 m); and reference renders from the four published points.

From every one of the four published points the floor tears forward and the skull is a sliver. The scoring crop
tracks the projected 3D bounding box of the Gaussians that belong to the skull in the photo (crops placed where a
flat panel would put the skull were empty, which is itself the finding that SHARP's skull is not on the wall).
Inside that crop 87 % of the pixels are empty at Boxer's O and 94 % at the National Gallery point.

| SHARP 30 mm, grid | peak (Δx, Δz) | value | offset from Boxer's O | in Δx / 13, Δz / 138 units | inside 2σ |
|---|---|---|---|---|---|
| resemblance | 675, 160 | 0.606 | 141 mm | −7.8, −0.7 | no |
| CLIP cosine | 650, 380 | 0.283 | 176 mm | −9.8, +0.9 | no |
| P(skull) | 975, 60 | 0.979 | 280 mm | +15.2, −1.4 | no |

At Boxer's O the SHARP render scores resemblance 0.538, P(skull) 0.02. The flat model scores 0.972 and 0.999 at
the same point. The whole SHARP resemblance surface lies between 0.30 and 0.61, below the flat model's value at
the National Gallery point (0.909), so the "peak" is the maximum of a low, noisy surface rather than a resolved
skull; its 95 % region is 21 000 mm² and it is not repeatable across metrics (the three metrics peak 280 mm
apart). The orbit says the same thing from a different direction: the best of 532 poses reaches resemblance 0.59
with the skull still a bone-coloured smear lying on the reconstructed floor (`runs/sharp_wiki_f30/orbit_top12.jpg`).

Collapse. Collapse is defined per pose as more than 15 % empty pixels inside the tracked skull crop or a
Laplacian variance below 30 % of the near-frontal median. At 1.4 m the first collapsed poses appear beyond 45°
from the photo camera's axis (20 % of poses), rising to 57 % at 60° to 75°; at 2.0 and 2.8 m about half the
poses have collapsed by 45° to 60° and all of them beyond 105°; at 0.7 m every pose is collapsed because the
camera is inside the floor relief. Boxer's O sits 82° from the axis. Apple's "nearby views" means, for this
scene, about ±30° and not less than a metre.

## Phase 3. Comparison in units of human disagreement

Boxer's 1σ envelope is 20 × 4 mm. The Boxer to National Gallery disagreement is 13 mm in Δx and 138 mm in Δz.

SHARP's best-scoring position at the default lens is 141 mm from Boxer's O by the resemblance metric (−102 mm in
Δx, −98 mm in Δz), which is 7.8 expert-disagreement units in Δx and 0.7 in Δz, and 5 to 25 σ outside his ellipse
depending on the axis. That is the refinement-versus-different-category question the brief asked, and the answer
is in between: it is not off by metres, but the number is not a location, because nothing resolves there. The
prediction in the brief was that SHARP flattens the panel into shallow relief near the picture plane and no pose
produces a resolved skull. The second half is confirmed: no pose on the grid or the orbit produces a resolved
skull, and SHARP's best pose scores 0.39 below Boxer's peak on the flat model (0.606 against 0.997). The first
half is wrong in an instructive way: SHARP does not flatten the panel, it inflates it. It reconstructs 0.6 m of
depicted depth at 30 mm and 4.1 m at 200 mm. The skull streak ends up lying on a floor that recedes at about 20°,
and orbiting a camera around a streak on a receding floor cannot undo a projective distortion that Holbein
painted for a vertical wall.

## Phase 4. The assumed lens rescales depth and nothing else, and no lens brings SHARP into the ellipse

Thirteen assumed lenses from 5 to 200 mm equivalent (`figures/focal_sweep.png`, `figures/depth_strip.png`,
`runs/phase4_sweep.json`). Metric depth is exactly linear in the assumed focal length (median 0.33 m at 5 mm, 2.00 m
at 30 mm, 13.2 m at 200 mm) while the lateral scale of the reconstruction does not change at all (1095 mm per SHARP
unit at every lens, to within 2 %). SHARP's metric guess is a depth guess only; the panel it draws is always 2.39 m
wide in its own units. Consequently the relief, in true panel millimetres, is also linear in the lens: 104 mm at
5 mm, 623 mm at 30 mm, 4124 mm at 200 mm. A short assumed lens is the only way to make SHARP's scene approach a
flat panel.

SHARP's station point on Boxer's plane, per lens (resemblance peak on the 50 × 40 mm grid, distance from Boxer's O):

| lens mm | relief mm | peak (Δx, Δz) | offset from O mm | peak value | resemblance at O | empty pixels in the skull crop at O |
|---|---|---|---|---|---|---|
| 5 | 104 | 850, 560 | 311 | 0.57 | 0.25 | 100 % |
| 8 | 166 | 850, 520 | 272 | 0.57 | 0.25 | 100 % |
| 10 | 208 | 850, 600 | 350 | 0.58 | 0.25 | 100 % |
| 14 | 291 | 900, 600 | 364 | 0.57 | 0.25 | 100 % |
| 18 | 374 | 1000, 560 | 376 | 0.58 | 0.53 | 96 % |
| 24 | 499 | 650, 120 | 187 | 0.58 | 0.50 | 88 % |
| 30 | 623 | 675, 160 | 141 | 0.61 | 0.54 | 87 % |
| 35 | 727 | 650, 160 | 160 | 0.60 | 0.53 | 89 % |
| 50 | 1039 | 900, 600 | 364 | 0.58 | 0.53 | 92 % |
| 70 | 1454 | 1350, 280 | 574 | 0.55 | 0.46 | 100 % |
| 100 | 2077 | 1300, 80 | 553 | 0.51 | 0.25 | 100 % |
| 135 | 2804 | 1500, 40 | 755 | 0.53 | 0.25 | 100 % |
| 200 | 4124 | 1100, 480 | 392 | 0.51 | 0.45 | 2 % |

No lens puts the peak inside Boxer's 2σ ellipse; the closest approach is 141 mm at the default 30 mm, and every
peak value sits between 0.51 and 0.61, far below the flat model's 0.997. The answer to the brief's question is
therefore no: matching a statistical lens guess to the geometric reconstruction does not recover Holbein's station
point. The 100 % empty crops at short lenses are a units effect worth stating: at 5 mm the whole scene is 0.3 m
deep, so a viewer placed 258 mm off the wall by the bridge stands inside or beyond the Gaussians and sees nothing in
the tracked box. The interactive lab tells the complementary story that the numbers cannot: at an assumed 5 mm lens
the reconstruction is nearly flat, and from Boxer's anamorphic.m point with a 22° field of view the skull begins to
read as a skull (`captures/20260910/docs/0014…14-boxer-anamorphic-sharp-5mm-skull.jpg`), although the tracked crop
is placed on the far-wall depth and misses it. That capture, not the grid, is the strongest evidence that the lens
prior is what stands between SHARP and the panel.

A finer orbit around SHARP's skull at 30 mm (azimuth 50° to 90° in 4° steps, elevation −30° to 15°, 0.8 to 2.6 m,
440 poses, `runs/sharp_wiki_f30/fine_surface.png`) peaks at resemblance 0.60 at az 58°, el 10°, 0.8 m, which is
(Δx −354, Δy 375, Δz 417): in front of the panel's right half, 0.4 m off the wall, looking down at the floor. It is
not a station point in Boxer's sense; it is the angle from which a streak painted on a receding floor looks least
elongated.

## Phase 5. Idolmorphosis

Boxer's forward pipeline was run on three pieces of our material (`figures/phase5_pairs.jpg`,
`runs/phase5_results.json`): SHARP's best-pose crop, the torn render from Boxer's O, and SHARP's depth map of the
skull region. Each 512 px square was placed in the 142 × 142 mm box centred at (21.65, −783.00) and forward
trapezoid transformed with D = 1824.45 and d = 257.88. The resulting streaks measure 914.0 × 532.3 mm in the
painting frame, matching the 915 mm lateral extent Boxer reports for Holbein's skull, and are saved at 4 px/mm
(3656 × 2130 px) for a 36 inch print, composited into the painting, and re-projected from the exact-perspective
point (R = 1806.1, α = 81.87°) where each resolves back into its square. The one that reads best from O is the
depth map: a machine's belief about where the skull is, stretched across the floor exactly where Holbein stretched
the skull itself.

## Interactive lab and my own runs

The app (`sharp-studio/`) exposes all of this: splat, textured depth mesh, wireframe, flat-panel and split
views from any eye position in Boxer's frame, the published and saved viewpoints (`★ Best match` is the resolved
skull at 740.5, 1035, 255.3), trajectories, and a "Run SHARP from here" button that renders the painting from the
current camera and runs the model on that oblique photograph with the render's exact focal length. The first such
run, from Boxer's O (`runs_user/20260910-002333__from-boxer-O-flat`), bridges back to the source camera at exactly
(777, 1035, 258) and reconstructs the oblique panel as a 5.6 m deep scene at k = 0.91 SHARP units per reference
unit: SHARP given a grazing photograph of a flat painting again reads the depicted room, not the board. Every
capture in the lab writes a JSON sidecar with the pose in both frames, and `captures/index.jsonl` is the log.

## Drawings

`method_figures.py` writes the analytical plates used in the lab's Method tab: `figures/method/tiepoints_plate.png`
(Boxer's five points, reference lines, 8 × 8 grid), `two_eyes.png` (trapezoid and perspective eyes), `section_plate.png`
(eye level, skull box and SHARP's relief in section), `resection_plate.png` (published points, construction and SHARP's
floor in plan under the picture plane), `orbit_fan.png` (532 SHARP camera cones shaded by resemblance).

## What failed, what surprised

* The first grid scoring used the flat model's skull position for the crop and returned all-black crops. That
  was a bug in the measurement and a result at the same time: SHARP's skull is not on the wall.
* The reference antimatter15 viewer mis-rendered SHARP scenes under camera motion (its default camera and
  projection conventions do not match SHARP's); the lab's own viewer was written to fix that and is what all
  renders use.
* The perceptual metric that the brief specifies, CLIP against "a human skull", is nearly useless for location:
  it saturates. The image-to-image resemblance metric was added; it is anchored on the answer and therefore
  peaks there by construction, which is why the basin area, not the peak, is the reported quantity.
* The panel-plane ambiguity is real and large: the border-fit bridge puts the photo camera at eye height 200 mm
  instead of 1035 mm because it is fitting the floor. Stating it beats hiding it.
* Boxer's two published points differ by 36 mm because of a screen-orientation convention, not an approximation
  error; the brief's stated relation between (D, d) and (R, α) is the small-angle version of the exact one.
* Long batch renders exhausted Chrome's blob storage and silently broke every later canvas read; the render and
  capture paths were moved to JPEG data URLs. Server restarts mid-sweep lost frames twice; the sweep was re-rendered
  from per-lens missing-frame job lists, and only complete grids were scored.
