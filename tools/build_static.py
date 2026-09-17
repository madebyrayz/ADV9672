#!/usr/bin/env python3
"""Build a static copy of the week-02 app into docs/ for GitHub Pages.

The app normally talks to server.py. Pages serves files and nothing else, so this
snapshots every read-only API response to a file at the same path and rewrites the
app's absolute URLs to relative ones, since a project site is served from a
subdirectory rather than the domain root.

The Lab's Gaussian files, about 36 MB a scene, are copied in under splats/ so the
published Lab can draw every scene. They match this repo's *.splat ignore rule, so they
never enter its history; tools/deploy_site.sh copies docs/ whole, ignored files
included, into the public site repo. The write routes have no static equivalent, and
the build marks itself so the app runs read-only.

Pages does not read docs/ from this repo, which is private; commit the build and run
tools/deploy_site.sh to publish it.
"""
import json
import re
import shutil
import sys
from pathlib import Path
pathlib_Path = Path

ROOT = Path(__file__).resolve().parent.parent
WEEK = ROOT / "week-02-post-original-holbein"
APP = WEEK / "sharp-studio"
ANAMORPH = WEEK / "anamorph"
SITE = "docs"          # published root, one folder per artifact beneath it
SLUG = "poh"           # this artifact: Post-Original Holbein
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


def write_index(site: pathlib_Path) -> None:
    """Course index. One row per artifact, so the published root stays a directory
    rather than becoming whichever week happened to be built last."""
    site.mkdir(parents=True, exist_ok=True)
    (site / "index.html").write_text("""<!doctype html>
<html lang="en"><head><meta charset="utf-8" />
<title>ADV9672</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
  :root { color-scheme: light dark; --ink:#111; --dim:#6b6b6b; --line:#e2e0dc; --bg:#f4f2ed; }
  @media (prefers-color-scheme: dark) { :root { --ink:#f2f2f2; --dim:#8d8d8d; --line:#262626; --bg:#0a0a0a; } }
  body { margin:0; background:var(--bg); color:var(--ink);
         font-family:"TWK Lausanne", ui-sans-serif, system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif; }
  main { max-width:720px; margin:0 auto; padding:96px 24px 96px; }
  h1 { font-size:15px; font-weight:600; letter-spacing:-0.01em; margin:0 0 40px; }
  ul { list-style:none; padding:0; margin:0; }
  li { border-top:1px solid var(--line); }
  li:last-child { border-bottom:1px solid var(--line); }
  a { display:grid; grid-template-columns:44px 1fr; gap:20px; padding:22px 2px;
      text-decoration:none; color:inherit; }
  a:hover { background:color-mix(in srgb, var(--ink) 4%, transparent); }
  .n { color:var(--dim); font-size:13px; padding-top:2px; }
  .t { font-size:19px; font-weight:500; letter-spacing:-0.015em; margin-bottom:6px; }
  .d { color:var(--dim); font-size:14px; line-height:1.5; }
  @media (max-width: 600px) { main { padding:48px 20px 64px; } a { grid-template-columns:36px 1fr; gap:14px; } }
</style></head><body><main>
<h1>ADV9672</h1>
<ul>
  <li><a href="poh/"><span class="n">02</span><span>
    <span class="t">The Post-Original Holbein</span>
    <span class="d">Where must you stand for the skull in Holbein's <i>The Ambassadors</i> to resolve,
    and does a monocular reconstruction model put its best viewpoint anywhere near the geometric answer?</span>
  </span></a></li>
</ul>
</main></body></html>
""")


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
    html = html.replace('<link rel="stylesheet" href="/ui/', '<link rel="stylesheet" href="ui/')
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
    write_index(ROOT / SITE)
    size = sum(f.stat().st_size for f in DOCS.rglob("*") if f.is_file())
    print(f"docs/ built: {total} assets, {(size - splat_bytes) / 1e6:.0f} MB, plus {len(manifest['scenes'])} splats, {splat_bytes / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
