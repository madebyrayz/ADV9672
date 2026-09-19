---
date: 2026-09-10
tags:
  - design-research
  - measurements
---

# The Post-Original Holbein — data

> [!warning] Generated file — don't write here
> Rebuilt from the experiment's run data whenever you ask for a refresh. Anything typed into this file is lost on the next rebuild. Write in [[The Post-Original Holbein]] instead.

_Numbers behind the essay. The full figure set — per-lens basins, orbit contact sheets — stays in the project repo and on the Report tab._

## 1 — Ground truth and reproduction

Boxer's published parameters and the port of his two scripts. Numbers from boxer_repro/reproduction.json.

### Published viewing points (Δx, Δy, Δz mm)

| source | Δx | Δy | Δz |
| --- | --- | --- | --- |
| National Gallery 1997 | 790 | 1040 | 120 |
| Boxer inverseTrapezoid.m | 776.9 | 1035 | 257.9 |
| Boxer anamorphic.m | 740.5 | 1035 | 255.3 |
| Boxer 8x8 grid hypothesis | 785.625 | 1035 | 258.75 |

_1σ = 20 mm (Δx), 4 mm (Δz). Expert disagreement Boxer vs National Gallery: 13 mm, 138 mm._

### Boxer's construction (reproduced)

| Parameter              | Value                      |
| ---------------------- | -------------------------- |
| D (jaw through S)      | 1824.453 mm                |
| d (aspect = 1)         | 257.882 mm                 |
| S                      | (2872.0, 1035)             |
| O                      | (2872.0, 1035, 257.9)      |
| Exact-perspective R, α | 1806.136 mm, 81.874°       |
| Restored skull box     | 142 mm at (21.65, -783)    |
| Identity               | D = R / sin α, d = R cot α |

### Restored skull: port beside Boxer's

![](../00_Attachment/ADV9672_R1_restored-skull-comparison.jpg)

_Inverse trapezoid, exact perspective, and Boxer's OptimalSkull.jpg._

## 2 — Perceptual basin of the flat model (Phase 1)

Exact perspective of the painting over a 13 700-point (Δx, Δz) grid at Δy = 1035, four scores on the skull crop.

### Basins against Boxer's 2σ ellipse (1005 mm²)

| metric | peak Δx, Δz | value | area ≥95 % mm² | × ellipse |
| --- | --- | --- | --- | --- |
| clip_skull | 1090, 235 | 1.000 | 607,650 | 604 |
| clip_sim | 820, 115 | 0.360 | 34,200 | 34 |
| resemblance | 740, 255 | 0.997 | 23,900 | 24 |
| symmetry | 1490, 40 | 0.672 | 15,600 | 16 |

### Scores at the published points (flat model)

| point                     | resemblance | P(skull) | aspect | jaw ° |
| ------------------------- | ----------- | -------- | ------ | ----- |
| National Gallery 1997     | 0.909       | 1.000    | 0.45   | 4.6   |
| Boxer inverseTrapezoid.m  | 0.972       | 0.999    | 0.97   | 4.1   |
| Boxer anamorphic.m        | 0.997       | 0.999    | 1.00   | -0.1  |
| Boxer 8x8 grid hypothesis | 0.967       | 0.999    | 0.96   | 5.1   |

### Basin surfaces

![](../00_Attachment/ADV9672_03_perceptual-basin.png)

_P(skull), resemblance, symmetry and Boxer's own geometric conditions, with the four published points and the 2σ ellipse._

## 3 — Reference reconstructions (Phases 2–3)

Thirteen assumed lenses, each rendered on the Phase 1 grid and scored with a crop that tracks the skull Gaussians.

### Assumed lens → reconstruction → station point

| lens mm | f_px | depth median m | relief mm | mm/unit | photo cam Δz | peak Δx | peak Δz | resemblance | offset from O mm | Δx/13 | Δz/138 | in 2σ | resemblance at O | empty at O |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | 176 | 0.33 | 104 | 1095 | 340 | 850 | 560 | 0.57 | 311 | 5.6 | 2.19 | no | 0.25 | 100% |
| 8 | 281 | 0.53 | 166 | 1097 | 544 | 850 | 520 | 0.57 | 272 | 5.6 | 1.90 | no | 0.25 | 100% |
| 10 | 352 | 0.67 | 208 | 1095 | 680 | 850 | 600 | 0.58 | 350 | 5.6 | 2.48 | no | 0.25 | 100% |
| 14 | 493 | 0.93 | 291 | 1095 | 952 | 900 | 600 | 0.57 | 364 | 9.5 | 2.48 | no | 0.25 | 100% |
| 18 | 633 | 1.20 | 374 | 1095 | 1224 | 1000 | 560 | 0.58 | 376 | 17.2 | 2.19 | no | 0.53 | 96% |
| 24 | 844 | 1.60 | 499 | 1095 | 1632 | 650 | 120 | 0.58 | 187 | -9.8 | -1.00 | no | 0.50 | 88% |
| 30 | 1056 | 2.00 | 623 | 1095 | 2040 | 675 | 160 | 0.61 | 141 | -7.8 | -0.71 | no | 0.54 | 87% |
| 35 | 1232 | 2.33 | 727 | 1096 | 2380 | 650 | 160 | 0.60 | 160 | -9.8 | -0.71 | no | 0.53 | 89% |
| 50 | 1759 | 3.33 | 1039 | 1098 | 3400 | 900 | 600 | 0.58 | 364 | 9.5 | 2.48 | no | 0.53 | 92% |
| 70 | 2463 | 4.66 | 1454 | 1095 | 4760 | 1350 | 280 | 0.55 | 574 | 44.1 | 0.16 | no | 0.46 | 100% |
| 100 | 3519 | 6.66 | 2077 | 1095 | 6801 | 1300 | 80 | 0.51 | 553 | 40.2 | -1.29 | no | 0.25 | 100% |
| 135 | 4750 | 8.99 | 2804 | 1098 | 9181 | 1500 | 40 | 0.53 | 755 | 55.6 | -1.58 | no | 0.25 | 100% |
| 200 | 7037 | 13.25 | 4124 | 1075 | 13601 | 1100 | 480 | 0.51 | 392 | 24.9 | 1.61 | no | 0.45 | 2% |

_Offset = distance of SHARP's best resemblance position from Boxer's O (776.9, 257.9). The flat model scores 0.997 at Boxer's point._

### SHARP station point per lens on Boxer's plane

_Chart generated live in the app; see the Report tab._

### Collapse by angle from the photo axis (30 mm orbit)

| distance | 0° | 15° | 30° | 45° | 60° | 75° | 90° | 105° |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 700 mm | 100% | 100% | 88% | 64% | 29% | 78% | 83% | 100% |
| 1400 mm | 0% | 0% | 0% | 20% | 42% | 57% | 17% | 0% |
| 2000 mm | 0% | 0% | 6% | 44% | 48% | 52% | 58% | 100% |
| 2800 mm | 0% | 11% | 35% | 48% | 58% | 52% | 67% | 100% |

_Share of poses collapsed (>15 % empty in the tracked crop or Laplacian variance <30 % of frontal)._

### SHARP 30 mm: score surfaces on the grid

![](../00_Attachment/ADV9672_R2_sharp-basin-30mm.png)

## 4 — The assumed lens (Phase 4)

Depth scales with the assumed focal length; the lateral scale does not. No lens brings SHARP's station point into the ellipse.

### Metric depth against assumed focal length

_Chart generated live in the app; see the Report tab._

### Sweep summary

![](../00_Attachment/ADV9672_R3_focal-sweep.png)

_Depth, bridge parameters and the station point per lens._

### Depth maps per lens

![](../00_Attachment/ADV9672_07_depth-strip.png)

_Bright = near. The picture is the same; only the depth scale changes._

## 5 — Orbits around SHARP's skull (30 mm)

532 coarse poses and a 440-pose fine orbit in the az 50°–90° sector. Nothing resolves; the best poses are grazing views down the floor.

### Fine orbit surface

![](../00_Attachment/ADV9672_R4_fine-orbit-surface.png)

## 6 — Idolmorphosis (Phase 5)

Model output forward-transformed into the 142 mm skull box with D = 1824.45 and d = 257.88, composited, and seen from the exact-perspective point.

### Three sources: best pose, the torn render from O, the depth map

![](../00_Attachment/ADV9672_08_idolmorphosis.jpg)

_Left: the streak in the painting. Right: seen from Boxer's O, where it resolves back into its square. Print files at 4 px/mm in figures/._

## 7 — Test reconstructions

SHARP run on views rendered in the Lab (oblique photographs of the panel), bridged geometrically from the render camera.

### Runs

| id | status | source | from (Δx, Δy, Δz) | fov | f_px | depth median m | relief mm | mm/unit | k | tag |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20260910-002333__from-boxer-O-flat | ready | flat | 777, 1035, 258 | 50 | 3294 | 1.82 | 5650 | 1202 | 0.91 | from-boxer-O-flat |

## 8 — Captures and recordings

20 log entries. Files in anamorph/captures/.

### Where captures were taken (plan)

_Chart generated live in the app; see the Report tab._

### Counts

| Parameter | Value |
| --- | --- |
| capture | 19 |
| user_run | 1 |
| sharp_wiki_f30 | 16 |
| sharp_wiki_f5 | 2 |
| sharp_wiki_f200 | 2 |
