# The Post-Original Holbein

Where must you stand for the skull in Holbein's *The Ambassadors* (1533) to resolve,
and does Apple's SHARP — a network that turns one photograph into a metric 3D scene —
put its best viewpoint anywhere near the geometric answer Alexander Boxer published in 2012?

**Result.** It does not, and the way it misses is the finding. Given a photograph with
no lens, the model fills in a room; once there is a room, the floor carries the smear
away from the wall the construction lives on. Its best-scoring position sits 141 mm from
Boxer's, and at Boxer's own point the tracked skull box is 87 % empty.

## Layout

```
week-02/
├── writing/            the essay and its measurements, in Markdown
├── anamorph/           the study
│   ├── boxer_repro/    Python port of Boxer's anamorphic.m + inverseTrapezoid.m
│   ├── lib/            bridge.py (SHARP metres <-> panel mm), score.py, camera.py
│   ├── phase*.py       the measurement passes, in order
│   ├── method_figures.py   every plate in the essay
│   ├── runs/           one directory per reconstruction (metadata only, see below)
│   ├── figures/        generated plates
│   ├── captures/       every frame reproduced in the essay, with JSON sidecars
│   └── findings.md     what was measured, what failed, what surprised
└── sharp-studio/       the prototype: server.py + static/
```

## Running the prototype

The reader needs the app for the Lab tab only. **Method, Log and Report work with no
model installed** — they read committed metadata and figures. The Lab needs the SHARP
checkpoint because it renders live Gaussians.

Without SHARP, from the repository root:

```bash
python3 week-02/sharp-studio/server.py --port 8765
```

Open <http://localhost:8765>. Method, Log and Report are fully usable. The Lab will
load the interface but not the reconstruction.

With SHARP, clone it beside this folder and use its environment:

```bash
git clone https://github.com/apple/ml-sharp
ml-sharp/.venv/bin/python week-02/sharp-studio/server.py --port 8765
```

The `.splat` files the Lab loads are excluded from the repository — one run is about a
gigabyte. Regenerate them with the reproduction steps below.

## Reproducing the measurements

```bash
cd week-02/anamorph
PY=../../ml-sharp/.venv/bin/python
$PY boxer_repro/reproduce.py                    # ground truth: ports Boxer's two scripts
$PY phase1_basin.py                             # how wide "it looks like a skull" is
$PY phase2_sharp_run.py --image wiki            # SHARP at thirteen assumed lenses
$PY phase2_jobs.py runs/sharp_wiki_f30          # render job lists
$PY phase2_score.py runs/sharp_wiki_f30         # score the renders
$PY phase4_sweep.py                             # assumed-lens sweep
$PY phase5_idolmorphosis.py runs/sharp_wiki_f30 # forward-transform back into the panel
$PY lab/build_scenes.py                         # refresh the app manifest
$PY method_figures.py                           # redraw every plate
```

## Third-party source material

Boxer's essay, his two MATLAB listings and his figures are his work, so they are
not republished here. `boxer_repro/reproduce.py` compares the port against his
`OptimalSkull.jpg`; save it to `anamorph/data/boxer_figs/` from the essay linked
above before running that step.

## Conventions

Δx = mm right of the panel's right edge · Δy = mm above its bottom edge · Δz = mm out
from the wall. Panel 2095 × 2070 mm after the 1996 restoration. Source image:
Wikimedia `Holbein-ambassadors.jpg`, 1084 × 1069 px, the file Boxer worked from.

Every capture is written as `captures/<date>/<folder>/NNNN__<scene>__<mode>__dx…_dy…_dz…__fov…__<tag>.jpg`
with a JSON sidecar carrying the pose in both coordinate frames, field of view, view
mode, active overlays and the bridge parameters.

## Sources

Third-party code is cloned, not vendored: [apple/ml-sharp](https://github.com/apple/ml-sharp)
for the reconstruction model, [antimatter15/splat](https://github.com/antimatter15/splat)
for the WebGL splat renderer the viewer is built on. Both keep their own licences.
