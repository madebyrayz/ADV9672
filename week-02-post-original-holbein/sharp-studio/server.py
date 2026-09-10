#!/usr/bin/env python
"""SHARP Studio server.

Serves the web UI, keeps the SHARP model resident in memory, and exposes a small JSON API
to upload / import photos, run inference, and fetch the resulting 3D Gaussian splats.

Run with the ml-sharp venv:  ../ml-sharp/.venv/bin/python server.py [--port 8765]
"""

from __future__ import annotations

import argparse
import json
import logging
import mimetypes
import re
import shutil
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
DATA = ROOT / "data"
UPLOADS = DATA / "uploads"
SCENES = DATA / "scenes"
THUMBS = DATA / "thumbs"
REGISTRY = DATA / "scenes.json"
def _up(name: str, start: Path = None, depth: int = 5) -> Path:
    """Nearest ancestor containing `name`. Keeps the app working wherever the week folder sits
    in the course repo, rather than hard-coding how deep it is."""
    here = (start or ROOT)
    for _ in range(depth):
        if (here / name).exists():
            return here / name
        here = here.parent
    return ROOT.parent / name


UI_DIR = _up("shared") / "ui" if (_up("shared") / "ui").exists() else _up("ui")   # shared shell
ANAMORPH_DIR = ROOT.parent / "anamorph"   # research runs: served read-only at /anamorph/, renders saved via PUT /anamorph/save
SHARP_DIR = _up("ml-sharp")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".tif", ".tiff"}

for d in (UPLOADS, SCENES, THUMBS):
    d.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(SHARP_DIR))  # for ply2splat
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
LOG = logging.getLogger("studio")


# --------------------------------------------------------------------------- registry
class Registry:
    """Thread-safe list of scenes persisted to scenes.json."""

    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.RLock()
        self.items: list[dict] = []
        if path.exists():
            try:
                self.items = json.load(open(path))
            except Exception:
                LOG.exception("could not read registry")

    def save(self):
        with self.lock:
            tmp = self.path.with_suffix(".tmp")
            json.dump(self.items, open(tmp, "w"), indent=1)
            tmp.replace(self.path)

    def get(self, name: str) -> dict | None:
        with self.lock:
            return next((s for s in self.items if s["name"] == name), None)

    def unique_name(self, stem: str) -> str:
        base = re.sub(r"[^a-zA-Z0-9_-]+", "-", stem).strip("-").lower() or "photo"
        with self.lock:
            names = {s["name"] for s in self.items}
            name, i = base, 2
            while name in names:
                name, i = f"{base}-{i}", i + 1
            return name

    def add(self, item: dict):
        with self.lock:
            self.items.append(item)
            self.save()

    def update(self, name: str, **fields):
        with self.lock:
            s = self.get(name)
            if s is not None:
                s.update(fields)
                self.save()

    def remove(self, name: str):
        with self.lock:
            self.items = [s for s in self.items if s["name"] != name]
            self.save()

    def snapshot(self) -> list[dict]:
        with self.lock:
            return [dict(s) for s in self.items]


registry = Registry(REGISTRY)


# --------------------------------------------------------------------------- engine
class Engine:
    """Holds the SHARP predictor in memory and processes a queue of scenes."""

    def __init__(self):
        self.predictor = None
        self.device = None
        self.model_loading = False
        self.queue: list[str] = []
        self.current: str | None = None
        self.cv = threading.Condition()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    # ---- public
    def enqueue(self, name: str):
        with self.cv:
            if name not in self.queue and name != self.current:
                self.queue.append(name)
                registry.update(name, status="queued", stage="queued", progress=0, error=None)
                self.cv.notify()

    def status(self) -> dict:
        return {
            "device": self.device,
            "model_loaded": self.predictor is not None,
            "model_loading": self.model_loading,
            "queue": list(self.queue),
            "current": self.current,
        }

    # ---- internals
    def _load_model(self):
        import torch
        from sharp.cli.predict import DEFAULT_MODEL_URL
        from sharp.models import PredictorParams, create_predictor

        self.model_loading = True
        t0 = time.time()
        if torch.cuda.is_available():
            self.device = "cuda"
        elif torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"
        LOG.info("loading SHARP checkpoint on %s ...", self.device)
        state_dict = torch.hub.load_state_dict_from_url(DEFAULT_MODEL_URL, progress=True)
        predictor = create_predictor(PredictorParams())
        predictor.load_state_dict(state_dict)
        predictor.eval()
        predictor.to(self.device)
        self.predictor = predictor
        self.model_loading = False
        LOG.info("model ready in %.1fs", time.time() - t0)

    def _loop(self):
        while True:
            with self.cv:
                while not self.queue:
                    self.cv.wait()
                name = self.queue.pop(0)
                self.current = name
            try:
                self._process(name)
            except Exception as e:  # noqa: BLE001
                LOG.error("scene %s failed: %s\n%s", name, e, traceback.format_exc())
                registry.update(name, status="error", stage="error", error=str(e), progress=0)
            finally:
                with self.cv:
                    self.current = None

    def _process(self, name: str):
        import torch
        from sharp.cli.predict import predict_image
        from sharp.utils import io as sharp_io
        from sharp.utils.gaussians import save_ply

        from ply2splat import convert

        scene = registry.get(name)
        if scene is None:
            return
        src = DATA / scene["source"]
        t0 = time.time()

        def stage(s, p):
            registry.update(name, status="running", stage=s, progress=p, error=None)

        if self.predictor is None:
            stage("loading model", 5)
            self._load_model()

        stage("reading photo", 20)
        image, _, f_px = sharp_io.load_rgb(src)
        height, width = image.shape[:2]

        stage("inference", 35)
        t_inf = time.time()
        gaussians = predict_image(self.predictor, image, f_px, torch.device(self.device))
        inference_s = time.time() - t_inf

        stage("saving .ply", 75)
        ply_path = SCENES / f"{name}.ply"
        save_ply(gaussians, f_px, (height, width), ply_path)

        stage("converting to .splat", 88)
        meta = convert(str(ply_path), str(SCENES / f"{name}.splat"))

        stage("thumbnail", 96)
        make_thumb(src, THUMBS / f"{name}.jpg")

        registry.update(
            name,
            status="ready",
            stage="ready",
            progress=100,
            ply=f"scenes/{name}.ply",
            splat=f"scenes/{name}.splat",
            thumb=f"thumbs/{name}.jpg",
            width=meta["width"],
            height=meta["height"],
            fx=meta["fx"],
            count=meta["count"],
            depth_near=meta["depth_near"],
            depth_far=meta["depth_far"],
            depth_median=meta["depth_median"],
            focal_from_exif=bool(scene.get("focal_from_exif")),
            inference_s=round(inference_s, 2),
            total_s=round(time.time() - t0, 2),
            processed_at=time.time(),
        )
        LOG.info("scene %s ready (%.1fs total, %.1fs inference)", name, time.time() - t0, inference_s)


def make_thumb(src: Path, dst: Path, size: int = 480):
    from PIL import Image, ImageOps

    try:
        if src.suffix.lower() == ".heic":
            import pillow_heif

            img = pillow_heif.open_heif(src, convert_hdr_to_8bit=True).to_pillow()
        else:
            img = Image.open(src)
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((size, size))
        img.save(dst, "JPEG", quality=85)
    except Exception:
        LOG.exception("thumbnail failed for %s", src)


def capture_thumb_path(img: Path) -> Path:
    """Thumbnails live in a _thumbs/ folder beside the capture, so they travel with it and never
    collide with the capture's own name."""
    return img.parent / "_thumbs" / f"{img.stem}.jpg"


def build_capture_thumbs() -> int:
    """Captures are written at full render size but are only ever shown small in the Log grid and the
    report strips. Derive a 480 px copy for each one. Idempotent, and it never reads or rewrites a
    capture, its sidecar, or the index."""
    n = 0
    for img in CAPTURES.rglob("*.jpg"):
        if img.parent.name == "_thumbs" or not img.with_suffix(".json").exists():
            continue          # recording frames have no sidecar; skip them and the thumbs themselves
        dst = capture_thumb_path(img)
        if dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        make_thumb(img, dst)
        n += dst.exists()
    if n:
        LOG.info("built %d capture thumbnails", n)
    return n


def photo_info(path: Path) -> dict:
    """Image size + whether EXIF carries a focal length (SHARP falls back to 30 mm otherwise)."""
    from PIL import Image, ImageOps

    info = {"width": None, "height": None, "focal_from_exif": False}
    try:
        img = Image.open(path)
        img = ImageOps.exif_transpose(img)
        info["width"], info["height"] = img.size
        exif = Image.open(path).getexif().get_ifd(0x8769)
        info["focal_from_exif"] = any(k in exif for k in (0x920A, 0xA405))  # FocalLength / FocalLengthIn35mmFilm
    except Exception:
        pass
    return info


engine = Engine()


def register_photo(src_path: Path, original_name: str, run: bool) -> dict:
    """Add an uploaded/imported photo to the registry; returns the new scene item."""
    name = registry.unique_name(Path(original_name).stem)
    ext = Path(original_name).suffix.lower() or ".jpg"
    dst = UPLOADS / f"{name}{ext}"
    if src_path != dst:
        shutil.copy2(src_path, dst)
    info = photo_info(dst)
    make_thumb(dst, THUMBS / f"{name}.jpg")
    item = {
        "name": name,
        "title": name,  # unique slug; keeps duplicates like photo-2 distinguishable in the UI
        "source": f"uploads/{dst.name}",
        "thumb": f"thumbs/{name}.jpg",
        "status": "pending",
        "stage": "pending",
        "progress": 0,
        "created_at": time.time(),
        **info,
    }
    registry.add(item)
    if run:
        engine.enqueue(name)
    return item


# --------------------------------------------------------------------------- http
class Handler(BaseHTTPRequestHandler):
    server_version = "SharpStudio/0.1"

    def log_message(self, fmt, *args):  # quieter logs
        if "/api/state" not in str(args[0] if args else ""):
            LOG.debug(fmt, *args)

    # ---- helpers
    # The published copy on github.io has no reconstructions behind it. When this server is
    # running on the same machine the page can borrow it, which needs CORS. The allowance is
    # limited to the published origin and to localhost: a wildcard would let any site the
    # browser visits read this machine's research data for as long as the server is up.
    PUBLISHED_ORIGIN = "https://madebyrayz.github.io"

    @staticmethod
    def _origin_allowed(origin):
        if not origin:
            return False
        if origin == Handler.PUBLISHED_ORIGIN:
            return True
        host = urlparse(origin)
        return host.scheme == "http" and host.hostname in ("localhost", "127.0.0.1")

    def _cors(self):
        origin = self.headers.get("Origin")
        if self._origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Private-Network", "true")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def _json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def _file(self, path: Path, root: Path):
        try:
            path = path.resolve()
            path.relative_to(root.resolve())
        except ValueError:
            return self._json({"error": "forbidden"}, 403)
        if path.is_dir():
            path = path / "index.html"
        if not path.is_file():
            return self._json({"error": "not found"}, 404)
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        size = path.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-cache")
        self._cors()
        if path.suffix in (".splat", ".ply"):
            self.send_header("Content-Disposition", f'inline; filename="{path.name}"')
        self.end_headers()
        with open(path, "rb") as f:
            shutil.copyfileobj(f, self.wfile)

    # ---- routes
    def do_GET(self):
        u = urlparse(self.path)
        p = unquote(u.path)
        if p == "/api/lab/scenes":
            m = json.load(open(ANAMORPH_DIR / "lab" / "scenes.json"))
            for sc in m["scenes"]:
                sc["group"] = "Reference"
            m["scenes"] += user_run_scenes()
            m["user_runs"] = user_runs_status()
            return self._json(m)
        if p == "/api/lab/user_runs":
            return self._json({"runs": user_runs_status()})
        if p == "/api/lab/viewpoints":
            f = ANAMORPH_DIR / "lab" / "viewpoints.json"
            return self._json({"viewpoints": json.load(open(f)) if f.exists() else []})
        if p == "/api/lab/trajectories":
            f = ANAMORPH_DIR / "lab" / "trajectories.json"
            return self._json({"trajectories": json.load(open(f)) if f.exists() else []})
        if p == "/api/lab/report_versions":
            out = []
            for d in sorted((ANAMORPH_DIR / "reports").glob("v*")) if (ANAMORPH_DIR / "reports").exists() else []:
                meta = d / "meta.json"
                out.append({"id": d.name, "html": f"/anamorph/reports/{d.name}/report.html", **(json.load(open(meta)) if meta.exists() else {})})
            return self._json({"versions": out})
        if p == "/api/lab/captures":
            return self._json({"captures": lab_index()})
        if p == "/api/lab/runs":
            out = []
            for run in sorted(ANAMORPH_DIR.glob("runs/sharp_*")):
                item = {"run": run.name}
                for f in ("run.json", "grid_stats.json", "orbit_collapse_by_angle.json"):
                    if (run / f).exists():
                        item[f.split(".")[0]] = json.load(open(run / f))
                out.append(item)
            return self._json({"runs": out})
        if p == "/api/state":
            return self._json({"scenes": registry.snapshot(), "engine": engine.status()})
        if p.startswith("/data/"):
            return self._file(DATA / p[len("/data/"):], DATA)
        if p.startswith("/ui/"):
            return self._file(UI_DIR / p[len("/ui/"):], UI_DIR)
        if p.startswith("/anamorph/"):
            return self._file(ANAMORPH_DIR / p[len("/anamorph/"):], ANAMORPH_DIR)
        return self._file(STATIC / p.lstrip("/"), STATIC)

    def do_PUT(self):
        u = urlparse(self.path)
        if u.path == "/anamorph/save":
            rel = parse_qs(u.query).get("path", [""])[0]
            dst = (ANAMORPH_DIR / rel).resolve()
            if not rel or not str(dst).startswith(str(ANAMORPH_DIR.resolve())) or dst.suffix not in (".png", ".jpg", ".json", ".txt"):
                return self._json({"error": "bad path"}, 400)
            dst.parent.mkdir(parents=True, exist_ok=True)
            n = int(self.headers.get("Content-Length") or 0)
            with open(dst, "wb") as f:
                f.write(self.rfile.read(n))
            return self._json({"ok": True, "bytes": n})
        if u.path == "/api/upload":
            q = parse_qs(u.query)
            filename = Path(q.get("name", ["photo.jpg"])[0]).name
            run = q.get("run", ["1"])[0] != "0"
            if Path(filename).suffix.lower() not in IMAGE_EXTS:
                return self._json({"error": f"unsupported file type: {filename}"}, 400)
            n = int(self.headers.get("Content-Length") or 0)
            tmp = UPLOADS / f".upload-{time.time_ns()}{Path(filename).suffix.lower()}"
            with open(tmp, "wb") as f:
                remaining = n
                while remaining > 0:
                    chunk = self.rfile.read(min(1 << 20, remaining))
                    if not chunk:
                        break
                    f.write(chunk)
                    remaining -= len(chunk)
            item = register_photo(tmp, filename, run)
            tmp.unlink(missing_ok=True)
            return self._json({"scene": item})
        return self._json({"error": "not found"}, 404)

    def do_POST(self):
        u = urlparse(self.path)
        try:
            body = self._read_json()
        except Exception:
            return self._json({"error": "bad json"}, 400)

        if u.path == "/api/lab/capture":
            return self._json(lab_capture(body))
        if u.path == "/api/lab/run_sharp":
            return self._json(lab_run_sharp(body))
        if u.path == "/api/lab/viewpoints":
            f = ANAMORPH_DIR / "lab" / "viewpoints.json"
            json.dump(body.get("viewpoints", []), open(f, "w"), indent=1)
            return self._json({"ok": True})
        if u.path == "/api/lab/trajectories":
            f = ANAMORPH_DIR / "lab" / "trajectories.json"
            json.dump(body.get("trajectories", []), open(f, "w"), indent=1)
            return self._json({"ok": True})
        if u.path == "/api/lab/report_version":
            return self._json(lab_report_version(body))
        if u.path == "/api/lab/log_snapshot":
            snaps = CAPTURES / "snapshots"; snaps.mkdir(exist_ok=True)
            n = len(list(snaps.glob("log_*.jsonl"))) + 1
            dst = snaps / f"log_{n:03d}_{_dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.jsonl"
            shutil.copy2(LAB_INDEX, dst) if LAB_INDEX.exists() else dst.write_text("")
            return self._json({"ok": True, "file": str(dst.relative_to(ANAMORPH_DIR))})
        if u.path == "/api/lab/record":
            return self._json(lab_record(body))
        if u.path == "/api/lab/note":
            idx = lab_index()
            for e in idx:
                if e["id"] == body.get("id"):
                    e["note"] = str(body.get("note", ""))
                    meta_path = ANAMORPH_DIR / e["meta"]
                    if meta_path.exists():
                        m = json.load(open(meta_path)); m["note"] = e["note"]; json.dump(m, open(meta_path, "w"), indent=1)
            lab_index_write(idx)
            return self._json({"ok": True})
        if u.path == "/api/import":
            raw = str(body.get("path", "")).strip()
            path = Path(raw).expanduser()
            if not path.exists():
                return self._json({"error": f"path not found: {raw}"}, 400)
            files = [path] if path.is_file() else sorted(
                f for f in path.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS
            )
            files = [f for f in files if f.suffix.lower() in IMAGE_EXTS]
            if not files:
                return self._json({"error": "no images found"}, 400)
            items = [register_photo(f, f.name, bool(body.get("run", True))) for f in files[:200]]
            return self._json({"scenes": items})

        if u.path == "/api/run":
            names = body.get("names") or [s["name"] for s in registry.snapshot() if s["status"] in ("pending", "error")]
            for n in names:
                if registry.get(n):
                    engine.enqueue(n)
            return self._json({"queued": names})

        if u.path == "/api/rename":
            name, title = body.get("name"), str(body.get("title", "")).strip()
            if registry.get(name) and title:
                registry.update(name, title=title)
            return self._json({"ok": True})

        return self._json({"error": "not found"}, 404)

    def do_DELETE(self):
        u = urlparse(self.path)
        m2 = re.fullmatch(r"/api/lab/user_runs/([A-Za-z0-9_.+-]+)", u.path)
        if m2:
            d = (USER_RUNS / m2.group(1)).resolve()
            if str(d).startswith(str(USER_RUNS.resolve())) and d.exists():
                shutil.rmtree(d)
                return self._json({"ok": True})
            return self._json({"error": "unknown run"}, 404)
        m = re.fullmatch(r"/api/scenes/([a-z0-9_-]+)", u.path)
        if not m:
            return self._json({"error": "not found"}, 404)
        name = m.group(1)
        scene = registry.get(name)
        if not scene:
            return self._json({"error": "unknown scene"}, 404)
        registry.remove(name)
        for key in ("source", "ply", "splat", "thumb"):
            if scene.get(key):
                (DATA / scene[key]).unlink(missing_ok=True)
        return self._json({"ok": True})


# --------------------------------------------------------------------------- captures & recordings
import base64
import datetime as _dt

CAPTURES = ANAMORPH_DIR / "captures"
CAPTURES.mkdir(exist_ok=True)
LAB_INDEX = CAPTURES / "index.jsonl"
_lab_lock = threading.Lock()


def lab_index():
    if not LAB_INDEX.exists():
        return []
    return [json.loads(l) for l in open(LAB_INDEX) if l.strip()]


def lab_index_write(items):
    with _lab_lock:
        with open(LAB_INDEX, "w") as f:
            for it in items:
                f.write(json.dumps(it) + "\n")


def _slug(x):
    return re.sub(r"[^a-zA-Z0-9_.+-]+", "-", str(x)).strip("-")


def _fmt_mm(v):
    return f"{int(round(v)):+d}" if v is not None else "na"


def lab_capture(body):
    """Save one screenshot + full metadata sidecar.  Name encodes scene, mode, pose (Boxer mm), fov, seq."""
    meta = body.get("meta", {})
    head, b64 = body["png"].split(",", 1)
    ext = ".jpg" if "jpeg" in head or "jpg" in head else ".png"
    png = base64.b64decode(b64)
    now = _dt.datetime.now()
    day = now.strftime("%Y%m%d")
    folder = CAPTURES / day / (str(body.get("folder")) if body.get("folder") else "captures")
    folder.mkdir(parents=True, exist_ok=True)
    with _lab_lock:
        seq = len(list(folder.glob("*.json"))) + 1
    pose = meta.get("pose_mm", {})
    name = "__".join([f"{seq:04d}", _slug(meta.get("scene", "scene")), _slug(meta.get("mode", "3d")),
                      f"dx{_fmt_mm(pose.get('dx'))}_dy{_fmt_mm(pose.get('dy'))}_dz{_fmt_mm(pose.get('dz'))}",
                      f"fov{int(round(meta.get('fov_deg', 0)))}", _slug(meta.get("tag", "")) or "shot"])
    png_path = folder / f"{name}{ext}"; meta_path = folder / f"{name}.json"
    png_path.write_bytes(png)
    thumb = capture_thumb_path(png_path)
    thumb.parent.mkdir(parents=True, exist_ok=True)
    make_thumb(png_path, thumb)
    entry = {"id": f"{day}/{folder.name}/{name}", "file": str(png_path.relative_to(ANAMORPH_DIR)), "meta": str(meta_path.relative_to(ANAMORPH_DIR)),
             "time": now.isoformat(timespec="seconds"), "scene": meta.get("scene"), "mode": meta.get("mode"), "tag": meta.get("tag", ""),
             "pose_mm": pose, "fov_deg": meta.get("fov_deg"), "note": meta.get("note", ""), "kind": "capture", "folder": folder.name,
             "thumb": str(thumb.relative_to(ANAMORPH_DIR)) if thumb.exists() else None}
    full = {**entry, **meta, "app": "The Post-Original Holbein", "conventions": "pose_mm = (dx right of the panel's right edge, dy above the bottom edge, dz off the wall); pose_sharp = SHARP camera frame metres (x right, y down, z forward)"}
    json.dump(full, open(meta_path, "w"), indent=1)
    with _lab_lock:
        with open(LAB_INDEX, "a") as f:
            f.write(json.dumps(entry) + "\n")
    return {"ok": True, "entry": entry}


def lab_record(body):
    """Recording protocol: action=start -> folder; action=frame -> save frame i; action=finish -> mp4 + meta."""
    action = body.get("action")
    now = _dt.datetime.now(); day = now.strftime("%Y%m%d")
    if action == "start":
        with _lab_lock:
            n = len([p for p in (CAPTURES / day).glob("rec_*")]) + 1 if (CAPTURES / day).exists() else 1
        folder = CAPTURES / day / f"rec_{n:03d}__{_slug(body.get('name', 'trajectory'))}__{_slug(body.get('scene', ''))}"
        folder.mkdir(parents=True, exist_ok=True)
        json.dump({**body.get("meta", {}), "started": now.isoformat(timespec="seconds"), "name": body.get("name"), "scene": body.get("scene")},
                  open(folder / "recording.json", "w"), indent=1)
        return {"ok": True, "rec": str(folder.relative_to(ANAMORPH_DIR))}
    folder = (ANAMORPH_DIR / body["rec"]).resolve()
    if not str(folder).startswith(str(CAPTURES.resolve())):
        return {"error": "bad rec"}
    if action == "frame":
        i = int(body["i"])
        head, b64 = body["png"].split(",", 1)
        (folder / f"frame_{i:04d}{'.jpg' if 'jpeg' in head else '.png'}").write_bytes(base64.b64decode(b64))
        frames_meta = folder / "frames.jsonl"
        with open(frames_meta, "a") as f:
            f.write(json.dumps({"i": i, **body.get("meta", {})}) + "\n")
        return {"ok": True}
    if action == "finish":
        fps = int(body.get("fps", 24))
        frames = sorted(list(folder.glob("frame_*.png")) + list(folder.glob("frame_*.jpg")))
        mp4 = folder / "recording.mp4"
        try:
            import imageio.v2 as iio
            w = iio.get_writer(mp4, fps=fps, codec="libx264", quality=8, pixelformat="yuv420p", macro_block_size=8)
            for fr in frames:
                w.append_data(iio.imread(fr))
            w.close()
        except Exception as e:  # noqa: BLE001
            LOG.exception("mp4 failed")
            mp4 = None
        rec = json.load(open(folder / "recording.json"))
        rec.update({"finished": now.isoformat(timespec="seconds"), "frames": len(frames), "fps": fps, "mp4": str(mp4.relative_to(ANAMORPH_DIR)) if mp4 else None})
        json.dump(rec, open(folder / "recording.json", "w"), indent=1)
        entry = {"id": str(folder.relative_to(CAPTURES)), "kind": "recording", "file": rec["mp4"], "meta": str((folder / "recording.json").relative_to(ANAMORPH_DIR)),
                 "time": rec["finished"], "scene": rec.get("scene"), "mode": rec.get("mode"), "tag": rec.get("name"), "frames": len(frames),
                 "thumb": str(frames[len(frames) // 2].relative_to(ANAMORPH_DIR)) if frames else None, "note": "", "folder": folder.name, "pose_mm": rec.get("pose_mm_start"), "fov_deg": rec.get("fov_deg")}
        with _lab_lock:
            with open(LAB_INDEX, "a") as f:
                f.write(json.dumps(entry) + "\n")
        return {"ok": True, "entry": entry}
    return {"error": "unknown action"}


# --------------------------------------------------------------------------- test reconstructions
USER_RUNS = ANAMORPH_DIR / "runs_user"
USER_RUNS.mkdir(exist_ok=True)
sys.path.insert(0, str(ANAMORPH_DIR / "lib"))
_user_jobs: dict[str, dict] = {}


def user_runs_status():
    out = []
    for d in sorted(USER_RUNS.iterdir()):
        if not d.is_dir():
            continue
        rj = d / "run.json"
        item = json.load(open(rj)) if rj.exists() else {"id": d.name, "status": "unknown"}
        item.update(_user_jobs.get(d.name, {}))
        out.append(item)
    return out


def user_run_scenes():
    scenes = []
    for it in user_runs_status():
        if it.get("status") != "ready":
            continue
        d = USER_RUNS / it["id"]
        scenes.append({
            "id": it["id"], "label": f"Test · {it.get('tag') or it['id']} ({it['source']}, {it['fov_deg']:.0f}°)", "kind": "sharp", "group": "Tests",
            "splat": f"/anamorph/runs_user/{it['id']}/model.splat", "ply": f"/anamorph/runs_user/{it['id']}/model.ply",
            "depth_png": f"/anamorph/runs_user/{it['id']}/depth.png", "f35_mm": it["f35_mm"], "f_px": it["f_px"], "width": it["width"], "height": it["height"],
            "image": f"/anamorph/runs_user/{it['id']}/{it.get('source_file', 'source.png')}", "source_image_is_view": True, "depth_m": it["depth_m"], "relief_mm": it.get("relief_mm", 0),
            "panel": it["panel"], "panel_variants": None, "grid_stats": None, "best_orbit_pose": None, "figures": {}, "depth_grid": it.get("depth_grid"),
            "source_pose_mm": it.get("source_pose_mm"), "derived_from": it.get("derived_from"), "created": it.get("created"),
        })
    return scenes


def lab_run_sharp(body):
    """Run SHARP on a view rendered in the lab.  The lab sends the PNG, the render intrinsics (fratio, size) and the
    camera pose in the reference scene's SHARP frame plus that scene's panel bridge, so the panel can be placed
    geometrically in the new run's camera frame."""
    meta = body.get("meta", {})
    now = _dt.datetime.now()
    rid = now.strftime("%Y%m%d-%H%M%S") + "__" + (_slug(meta.get("tag")) or "run")
    d = USER_RUNS / rid; d.mkdir(parents=True, exist_ok=True)
    head, b64 = body["png"].split(",", 1)
    src_name = "source.jpg" if "jpeg" in head else "source.png"
    (d / src_name).write_bytes(base64.b64decode(b64))
    run = {"id": rid, "status": "queued", "stage": "queued", "created": now.isoformat(timespec="seconds"), "tag": meta.get("tag", ""),
           "source": meta.get("source", "flat"), "derived_from": meta.get("scene"), "fov_deg": meta.get("fov_deg"), "fratio": meta.get("fratio"),
           "size": meta.get("size"), "source_file": src_name, "source_pose_mm": meta.get("pose_mm"), "source_target_mm": meta.get("target_mm"), "source_pose_sharp": meta.get("pose_sharp"),
           "ref_panel": meta.get("ref_panel"), "note": meta.get("note", ""),
           "conventions": "SHARP frame of THIS run = the lab camera that rendered source.png (x right, y down, z forward); panel placed geometrically from that camera; depth scale from the central-region median"}
    json.dump(run, open(d / "run.json", "w"), indent=1)
    _user_jobs[rid] = {"status": "queued", "stage": "queued", "progress": 0}
    threading.Thread(target=_user_run_worker, args=(rid,), daemon=True).start()
    return {"ok": True, "id": rid}


def _user_run_worker(rid):
    import numpy as np
    import torch
    from PIL import Image
    from sharp.cli.predict import predict_image
    from sharp.utils.gaussians import save_ply
    from bridge import Panel, depth_map, load_ply_xyz, project as img_project
    from ply2splat import convert

    d = USER_RUNS / rid
    run = json.load(open(d / "run.json"))
    def stage(s, p):
        _user_jobs[rid] = {"status": "running", "stage": s, "progress": p}
    try:
        if engine.predictor is None:
            stage("loading model", 5); engine._load_model()
        stage("reading view", 15)
        img = np.asarray(Image.open(d / run.get("source_file", "source.png")).convert("RGB"))
        H, W = img.shape[:2]
        f_px = float(run["fratio"]) * W                       # exact intrinsics of the rendered view
        f35 = f_px * 43.27 / float(np.hypot(W, H))            # SHARP's diagonal convention, for the record
        stage("inference", 30)
        t0 = time.time()
        g = predict_image(engine.predictor, img, f_px, torch.device(engine.device))
        inf = time.time() - t0
        stage("saving", 70)
        save_ply(g, f_px, (H, W), d / "model.ply")
        meta = convert(str(d / "model.ply"), str(d / "model.splat"))
        xyz, op, _ = load_ply_xyz(d / "model.ply")
        dm = depth_map(xyz, op, f_px, W, H, res=256)
        np.save(d / "depth.npy", dm)
        dd = dm.copy(); lo, hi = np.nanpercentile(dd, 1), np.nanpercentile(dd, 99)
        dd = np.clip((dd - lo) / (hi - lo + 1e-9), 0, 1); dd[np.isnan(dm)] = 0
        Image.fromarray((255 * (1 - dd)).astype(np.uint8)).save(d / "depth.png")
        # ---- geometric panel bridge: transform the reference panel into this camera's frame
        stage("bridging units", 90)
        rp = run["ref_panel"]; ps = run["source_pose_sharp"]
        pos, tgt = np.asarray(ps["pos"], float), np.asarray(ps["target"], float)
        f = tgt - pos; f /= np.linalg.norm(f); r = np.cross([0, 1, 0], f); r /= (np.linalg.norm(r) or 1); dn = np.cross(f, r)
        Rm = np.stack([r, dn, f], 0)                            # world -> camera rotation (rows = camera axes)
        to_cam = lambda P: Rm @ (np.asarray(P, float) - pos)
        origin_ref = np.asarray(rp["origin"]); u_ref, v_ref, n_ref = (np.asarray(rp[k]) for k in ("u", "v", "n"))
        # geometric depth of the panel centre in reference units vs SHARP's depth for the central region
        centre_ref = origin_ref + u_ref * rp["width_units"] / 2 + v_ref * rp["height_units"] / 2
        z_geom = float(to_cam(centre_ref)[2])
        uu, vv = img_project(xyz, f_px, W, H)
        cen = (uu > 0.4 * W) & (uu < 0.6 * W) & (vv > 0.4 * H) & (vv < 0.6 * H) & (op > 0.5)
        z_sharp = float(np.median(xyz[cen, 2])) if cen.sum() > 50 else float(np.median(xyz[op > 0.5, 2]))
        k = z_sharp / z_geom if z_geom > 0 else 1.0             # SHARP units per reference unit
        panel = Panel(origin=(to_cam(origin_ref) * k).tolist(), u=(Rm @ u_ref).tolist(), v=(Rm @ v_ref).tolist(), n=(Rm @ n_ref).tolist(),
                      scale_mm_per_unit=float(rp["scale_mm_per_unit"] / k), scale_y_mm_per_unit=float(rp["scale_mm_per_unit"] / k),
                      width_units=float(rp["width_units"] * k), height_units=float(rp["height_units"] * k), plane_rms_border=0.0, plane_rms_all=0.0, n_border=0,
                      f_px=f_px, image_size=[W, H], border_frac=0.0, camera0_mm=[0, 0, 0],
                      depth_stats={"z_geom_centre_ref_units": z_geom, "z_sharp_centre": z_sharp, "k_sharp_per_ref": k, "label": "geometric-from-source-camera"})
        panel.camera0_mm = list(panel.to_mm([0, 0, 0]))
        panel.save(d / "panel_geometric.json")
        # coarse depth grid for the mesh view
        n = 64; res = dm.shape[0]; grid = []
        for j in range(n + 1):
            row = []
            for i in range(n + 1):
                r0, r1 = int(max(0, (j - 0.5) * res / n)), int(min(res, (j + 0.5) * res / n) + 1)
                c0, c1 = int(max(0, (i - 0.5) * res / n)), int(min(res, (i + 0.5) * res / n) + 1)
                blk = dm[r0:r1, c0:c1]; blk = blk[np.isfinite(blk)]
                row.append(float(np.median(blk)) if blk.size else None)
            grid.append(row)
        z = xyz[op > 0.5, 2]
        run.update({"status": "ready", "stage": "ready", "width": W, "height": H, "f_px": f_px, "f35_mm": round(f35, 2), "inference_s": round(inf, 2), "n_gaussians": int(len(xyz)),
                    "depth_m": {"min": float(z.min()), "p05": float(np.percentile(z, 5)), "median": float(np.median(z)), "p95": float(np.percentile(z, 95)), "max": float(z.max())},
                    "relief_mm": float((np.percentile(z, 95) - np.percentile(z, 5)) * panel.scale_mm_per_unit),
                    "panel": {k2: getattr(panel, k2) for k2 in ("origin", "u", "v", "n", "scale_mm_per_unit", "width_units", "height_units")}, "camera0_mm": panel.camera0_mm,
                    "bridge": panel.depth_stats, "depth_grid": grid, "finished": _dt.datetime.now().isoformat(timespec="seconds")})
        json.dump(run, open(d / "run.json", "w"), indent=1)
        _user_jobs[rid] = {"status": "ready", "stage": "ready", "progress": 100}
        with _lab_lock:
            with open(LAB_INDEX, "a") as fh:
                fh.write(json.dumps({"id": f"user_run/{rid}", "kind": "user_run", "file": f"runs_user/{rid}/{run.get('source_file', 'source.png')}", "meta": f"runs_user/{rid}/run.json", "time": run["finished"],
                                     "scene": run.get("derived_from"), "mode": run["source"], "tag": run.get("tag", ""), "pose_mm": run.get("source_pose_mm"), "fov_deg": run.get("fov_deg"), "note": run.get("note", ""), "folder": rid}) + "\n")
        LOG.info("user run %s ready (%.1fs)", rid, inf)
    except Exception as e:  # noqa: BLE001
        LOG.exception("user run failed")
        run.update({"status": "error", "error": str(e)}); json.dump(run, open(d / "run.json", "w"), indent=1)
        _user_jobs[rid] = {"status": "error", "stage": "error", "error": str(e), "progress": 0}


def lab_report_version(body):
    reports = ANAMORPH_DIR / "reports"; reports.mkdir(exist_ok=True)
    n = len(list(reports.glob("v*"))) + 1
    now = _dt.datetime.now()
    d = reports / f"v{n:03d}_{now.strftime('%Y%m%d-%H%M%S')}"; d.mkdir()
    html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'><title>{d.name} · report</title>
<link rel='stylesheet' href='/ui/components.css'><link rel='stylesheet' href='/lab.css'><style>body{{padding:24px 32px}}</style></head>
<body><h1 class='text-lg'>Report · {d.name}</h1><p class='text-muted text-sm'>{body.get('note','')} · saved {now.isoformat(timespec='seconds')}</p>
<div class='reports'>{body.get('html','')}</div></body></html>"""
    (d / "report.html").write_text(html)
    json.dump(body.get("data", {}), open(d / "data.json", "w"), indent=1)
    meta = {"time": now.isoformat(timespec="seconds"), "note": body.get("note", ""), "n_runs": len(body.get("data", {}).get("runs", [])), "n_captures": len(body.get("data", {}).get("captures", []))}
    json.dump(meta, open(d / "meta.json", "w"), indent=1)
    if LAB_INDEX.exists():
        shutil.copy2(LAB_INDEX, d / "log_index.jsonl")
    return {"ok": True, "id": d.name, "html": f"/anamorph/reports/{d.name}/report.html"}


def bootstrap_existing():
    """Register scenes that were produced before the studio existed (splat + ply + upload present)."""
    for splat in sorted(SCENES.glob("*.splat")):
        name = splat.stem
        if registry.get(name):
            continue
        src = next((p for p in UPLOADS.glob(f"{name}.*") if p.suffix.lower() in IMAGE_EXTS), None)
        ply = SCENES / f"{name}.ply"
        if not src:
            continue
        from ply2splat import convert

        meta = convert(str(ply), str(splat)) if ply.exists() else {"width": None, "height": None, "fx": None,
                                                                    "count": splat.stat().st_size // 32,
                                                                    "depth_near": None, "depth_far": None,
                                                                    "depth_median": None}
        make_thumb(src, THUMBS / f"{name}.jpg")
        registry.add({
            "name": name, "title": name, "source": f"uploads/{src.name}", "thumb": f"thumbs/{name}.jpg",
            "status": "ready", "stage": "ready", "progress": 100,
            "ply": f"scenes/{name}.ply" if ply.exists() else None, "splat": f"scenes/{name}.splat",
            "created_at": src.stat().st_mtime, "processed_at": splat.stat().st_mtime,
            **{k: meta[k] for k in ("width", "height", "fx", "count", "depth_near", "depth_far", "depth_median")},
            **{"focal_from_exif": photo_info(src)["focal_from_exif"]},
        })
        LOG.info("registered existing scene %s", name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--preload", action="store_true", help="load the model at startup")
    args = ap.parse_args()
    bootstrap_existing()
    threading.Thread(target=build_capture_thumbs, daemon=True).start()
    if args.preload:
        threading.Thread(target=engine._load_model, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    LOG.info("SHARP Studio on http://localhost:%d  (data in %s)", args.port, DATA)
    srv.serve_forever()


if __name__ == "__main__":
    main()
