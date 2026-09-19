#!/usr/bin/env python3
"""Build a static copy of the week-02 app into docs/week-02/ for GitHub Pages.

The app normally talks to server.py. Pages serves files and nothing else, so this
snapshots every read-only API response to a file at the same path and rewrites the
app's absolute URLs to relative ones, since a project site is served from a
subdirectory rather than the domain root.

The Lab's Gaussian files, about 36 MB a scene, are copied in under splats/ so the
published Lab can draw every scene. Splats elsewhere in the repo are ignored; the ones
under docs/ are committed, because Pages serves docs/ straight from this repo. The
write routes have no static equivalent, and the build marks itself so the app runs
read-only.

docs/index.html is written by hand and is not touched here.
"""
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEEK = ROOT / "week-02"
APP = WEEK / "sharp-studio"
ANAMORPH = WEEK / "anamorph"
SITE = "docs"          # published root, one folder per artifact beneath it
SLUG = "week-02"       # published folder for this week
DOCS = ROOT / SITE / SLUG

sys.path.insert(0, str(APP))
import server  # noqa: E402  — reused so the snapshot cannot drift from the live routes


def write(rel: str, payload) -> None:
    """Snapshot one API response. A project site is served from a subdirectory, so an
    absolute asset path inside the payload would resolve against the domain root."""
    p = DOCS / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload)
    for prefix in ("anamorph", "ui", "api"):
        text = text.replace(f'"/{prefix}/', f'"{prefix}/')
    p.write_text(text)


def copy_tree(src: Path, dst: Path, suffixes=None) -> int:
    n = 0
    for f in src.rglob("*"):
        if not f.is_file() or f.name == ".DS_Store":
            continue
        if suffixes and f.suffix.lower() not in suffixes:
            continue
        out = dst / f.relative_to(src)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, out)
        n += 1
    return n


def main() -> None:
    if DOCS.exists():
        shutil.rmtree(DOCS)
    DOCS.mkdir(parents=True)

    # --- the app itself
    copy_tree(APP / "static", DOCS)
    copy_tree(ROOT / "shared" / "ui", DOCS / "ui")

    # --- read-only API responses, at the paths the client already asks for
    manifest = json.load(open(ANAMORPH / "lab" / "scenes.json"))
    for sc in manifest["scenes"]:
        sc["group"] = "Reference"
    manifest["scenes"] += server.user_run_scenes()
    manifest["user_runs"] = server.user_runs_status()
    # The server names each scene's Gaussians by where the run left them; the site keeps
    # one flat folder named by scene id. The .ply beside each is not read by the client.
    splat_bytes = 0
    (DOCS / "splats").mkdir(parents=True)
    for sc in manifest["scenes"]:
        src = ANAMORPH / sc["splat"].removeprefix("/anamorph/")
        if not src.exists():
            print(f"  no splat for {sc['id']}: {src}", file=sys.stderr)
            sc["splat"] = None
            continue
        dst = DOCS / "splats" / f"{sc['id']}.splat"
        shutil.copy2(src, dst)
        splat_bytes += dst.stat().st_size
        sc["splat"] = f"splats/{dst.name}"
        sc["ply"] = None
    write("api/lab/scenes", manifest)
    write("api/lab/captures", {"captures": server.lab_index()})
    write("api/lab/user_runs", {"runs": server.user_runs_status()})
    runs = []
    for run in sorted(ANAMORPH.glob("runs/sharp_*")):
        item = {"run": run.name}
        for f in ("run.json", "grid_stats.json", "orbit_collapse_by_angle.json"):
            if (run / f).exists():
                item[f.split(".")[0]] = json.load(open(run / f))
        runs.append(item)
    write("api/lab/runs", {"runs": runs})
    for name in ("viewpoints", "trajectories"):
        f = ANAMORPH / "lab" / f"{name}.json"
        write(f"api/lab/{name}", {name: json.load(open(f)) if f.exists() else []})
    versions = []
    for d in sorted((ANAMORPH / "reports").glob("v*")):
        meta = d / "meta.json"
        versions.append({"id": d.name, "html": f"anamorph/reports/{d.name}/report.html",
                         **(json.load(open(meta)) if meta.exists() else {})})
    write("api/lab/report_versions", {"versions": versions})

    # --- assets the essay, log and report read
    media = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".json"}
    total = 0
    for sub in ("figures", "captures", "lab", "boxer_repro", "reports"):
        if (ANAMORPH / sub).exists():
            total += copy_tree(ANAMORPH / sub, DOCS / "anamorph" / sub, media)
    (DOCS / "anamorph" / "data").mkdir(parents=True, exist_ok=True)
    # Boxer's own figures stay out of the published copy; they are his images, and the
    # study cites his essay rather than reproducing it.
    for f in (ANAMORPH / "data").glob("*"):
        if f.is_file() and f.suffix.lower() in {".jpg", ".png"}:
            shutil.copy2(f, DOCS / "anamorph" / "data" / f.name)
            total += 1
    (DOCS / "anamorph" / "data").mkdir(parents=True, exist_ok=True)
    total += copy_tree(ANAMORPH / "data" / "gigapixel", DOCS / "anamorph" / "data" / "gigapixel", {".jpg", ".png"})
    for runs in ("runs", "runs_user"):
        if (ANAMORPH / runs).exists():
            for f in (ANAMORPH / runs).rglob("*"):
                if f.is_file() and f.suffix.lower() in media and "renders_" not in str(f):
                    out = DOCS / "anamorph" / runs / f.relative_to(ANAMORPH / runs)
                    out.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, out)
                    total += 1

    # --- absolute URLs become relative, and the build marks itself
    index = DOCS / "index.html"
    html = index.read_text()
    html = re.sub(r'(<link[^>]*href=")/ui/', r'\1ui/', html)
    stamp = __import__("datetime").datetime.now().strftime("%Y%m%d%H%M%S")
    html = html.replace("<head>", f'<head>\n<meta name="build" content="static" />\n<meta name="build-id" content="{stamp}" />')
    # Version the app's own scripts and styles. Without this the browser keeps the previous
    # lab.js, which is the code that does the cache-busting, so a deploy could not take
    # effect until the old copy expired on its own.
    html = re.sub(r'(src|href)="((?:ui/)?[a-z0-9._-]+\.(?:js|css))"', rf'\1="\2?v={stamp}"', html)
    index.write_text(html)
    for js in DOCS.glob("*.js"):
        t = js.read_text()
        for a, b in (('"/api/', '"api/'), ("`/api/", "`api/"),
                     ('"/anamorph/', '"anamorph/'), ("`/anamorph/", "`anamorph/"),
                     ('"/ui/', '"ui/')):
            t = t.replace(a, b)
        js.write_text(t)

    (ROOT / SITE / ".nojekyll").touch()   # otherwise Pages hides paths beginning with an underscore
    size = sum(f.stat().st_size for f in DOCS.rglob("*") if f.is_file())
    print(f"docs/ built: {total} assets, {(size - splat_bytes) / 1e6:.0f} MB, plus {len(manifest['scenes'])} splats, {splat_bytes / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
