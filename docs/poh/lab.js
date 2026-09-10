// The Post-Original Holbein — interactive station-point study of Holbein's Ambassadors with Apple SHARP.
// Frames: Boxer panel frame (mm; dx right of the panel's right edge, dy above the bottom edge, dz off the wall)
//         <-> SHARP frame (metres; x right, y down, z forward, photo camera at the origin) via the scene's panel bridge.

const $ = (id) => document.getElementById(id);
const LX = 2095, LY = 2070;
const SKULL_C = [1072.5, 236.0];
const SKULL_BBOX = [615, 1530, 0, 472];
const COLORS = { "National Gallery 1997": "#ffffff", "Boxer inverseTrapezoid.m": "#22d3ee", "Boxer anamorphic.m": "#4ade80", "Boxer 8x8 grid hypothesis": "#facc15", "SHARP best (orbit)": "#f87171", "Photo camera": "#a78bfa" };
const MODE_LABEL = { sharp: "splat", mesh: "mesh", wire: "wire", flat: "flat", split: "split" };

let M = null, scene = null, viewer = null;
const state = { mode: "sharp", compare: "flat", targetMode: "centre", fov: 50, photoFit: true,
                overlays: { grid: true, skull: true, points: true, construction: false, sight: false, wire: false },
                traj: null, trajT: 0, playing: false, view: "lab", captures: [], loadedSplat: null, sliderDrag: false,
                savedViewpoints: [], savedTrajs: [], keyframes: [], userRuns: [], pollTimer: null };

// ---------------------------------------------------------------- helpers
function toast(title, desc, kind = "") {
  const el = document.createElement("div"); el.className = `toast ${kind}`;
  el.innerHTML = `<div class="title"></div>${desc ? '<div class="desc"></div>' : ""}`;
  el.querySelector(".title").textContent = title; if (desc) el.querySelector(".desc").textContent = desc;
  $("toaster").appendChild(el); setTimeout(() => { el.style.opacity = "0"; el.style.transition = "opacity .3s"; setTimeout(() => el.remove(), 300); }, 4000);
}
// A published build serves the API as plain files, which caches happily and would
// otherwise hand a returning visitor last week's data. The build stamp busts it once
// per deploy while still allowing caching in between.
const BUILD_ID = document.querySelector('meta[name="build-id"]')?.content || "";
const api = (path, body) => {
  const url = !body && BUILD_ID ? `${path}${path.includes("?") ? "&" : "?"}v=${BUILD_ID}` : path;
  return fetch(url, body ? { method: "POST", body: JSON.stringify(body) } : {}).then((r) => r.json());
};
const v3 = { add: (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]], sub: (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]], mul: (a, s) => [a[0] * s, a[1] * s, a[2] * s], dot: (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2], len: (a) => Math.hypot(a[0], a[1], a[2]) };
function toSharp(p, dx, dy, dz) { const s = p.scale_mm_per_unit; return v3.add(v3.add(v3.add(p.origin, v3.mul(p.u, (dx + LX) / s)), v3.mul(p.v, dy / s)), v3.mul(p.n, dz / s)); }
function toMM(p, P) { const d = v3.sub(P, p.origin), s = p.scale_mm_per_unit; return { dx: v3.dot(d, p.u) * s - LX, dy: v3.dot(d, p.v) * s, dz: v3.dot(d, p.n) * s }; }
function wall(x, y) { return toSharp(scene.panel, x - LX, y, 0); }
const skullC = () => wall(SKULL_C[0], SKULL_C[1]);
const panelC = (dy) => wall(LX / 2, dy);
const lerp = (a, b, t) => a + (b - a) * t, ease = (t) => t * t * (3 - 2 * t);

// ---------------------------------------------------------------- pose
function currentPoseMM() { return toMM(scene.panel, viewer.pos); }
function eyeGeometry(mm) {
  const ex = mm.dx + LX / 2, R = Math.hypot(ex, mm.dz), alpha = Math.atan2(ex, mm.dz) * 180 / Math.PI;
  const sx = mm.dx + LX - SKULL_C[0], sy = mm.dy - SKULL_C[1], sz = mm.dz;
  return { R, alpha, az: Math.atan2(sx, sz) * 180 / Math.PI, el: Math.atan2(sy, Math.hypot(sx, sz)) * 180 / Math.PI, dist: Math.hypot(sx, sy, sz) };
}
function setPoseMM(dx, dy, dz, opts = {}) {
  const P = toSharp(scene.panel, dx, dy, dz);
  const tm = opts.target || state.targetMode; let T;
  if (tm === "centre") T = panelC(dy); else if (tm === "skull") T = skullC();
  else { const dir = v3.sub(viewer.target, viewer.pos); T = v3.add(P, v3.len(dir) > 1e-6 ? dir : [0, 0, 1]); }
  viewer.setPose(P, T);
  if (opts.fov !== undefined) setFov(opts.fov);
}
function setFov(fov) { state.fov = fov; state.photoFit = false; viewer.fRatioOverride = 0.5 / Math.tan((fov * Math.PI) / 360); viewer.resize(); $("c-fov").value = fov; $("v-fov").textContent = fov.toFixed(0); }
function photoView() { state.photoFit = true; viewer.fRatioOverride = null; viewer.resize(); viewer.setPose([0, 0, 0], [0, 0, 1]); state.targetMode = "centre"; syncSeg("target-tabs", "target", "centre"); }
function effectiveFovDeg() { const f = viewer.fRatioOverride || (scene ? Math.max(scene.f_px / scene.width, scene.f_px / scene.height * (viewer.height / viewer.width)) : 1); return (2 * Math.atan(0.5 / f) * 180) / Math.PI; }
function effectivePhotoFov() { return 2 * Math.atan(0.5 / Math.max(scene.f_px / scene.width, scene.f_px / scene.height * (viewer.height / viewer.width))) * 180 / Math.PI; }
function syncSeg(id, attr, value) { for (const b of $(id).children) b.setAttribute("aria-selected", b.dataset[attr] === value ? "true" : "false"); }

// ---------------------------------------------------------------- overlays
function cross3(P, r, col) { return [{ pts: [[P[0] - r, P[1], P[2]], [P[0] + r, P[1], P[2]]], color: col }, { pts: [[P[0], P[1] - r, P[2]], [P[0], P[1] + r, P[2]]], color: col }, { pts: [[P[0], P[1], P[2] - r], [P[0], P[1], P[2] + r]], color: col }]; }
const hex = (h, a = 1) => [parseInt(h.slice(1, 3), 16) / 255, parseInt(h.slice(3, 5), 16) / 255, parseInt(h.slice(5, 7), 16) / 255, a];
function buildOverlays() {
  if (!scene) return;
  const L = [];
  if (state.overlays.grid) {
    L.push({ pts: [wall(0, 0), wall(LX, 0), wall(LX, LY), wall(0, LY)], color: [1, 1, 1, 0.9], loop: true });
    for (let i = 1; i < 8; i++) { L.push({ pts: [wall(i * LX / 8, 0), wall(i * LX / 8, LY)], color: [1, 1, 1, 0.28] }); L.push({ pts: [wall(0, i * LY / 8), wall(LX, i * LY / 8)], color: [1, 1, 1, 0.28] }); }
  }
  if (state.overlays.skull) {
    const [x0, x1, y0, y1] = SKULL_BBOX;
    L.push({ pts: [wall(x0, y0), wall(x1, y0), wall(x1, y1), wall(x0, y1)], color: hex("#facc15", 0.95), loop: true });
    for (const [x, y] of M.boxer.skull_points_mm) L.push(...cross3(wall(x, y), 0.02, hex("#facc15", 1)));
  }
  if (state.overlays.points) for (const p of viewpointList()) L.push(...cross3(toSharp(scene.panel, p.dx, p.dy, p.dz), 0.05, hex(p.color, 1)));
  if (state.overlays.construction) {
    const b = M.boxer; const S = wall(b.S_mm[0], b.S_mm[1]); const O = toSharp(scene.panel, b.O_mm[0] - LX, b.O_mm[1], b.O_mm[2]);
    L.push({ pts: [wall(b.x0, b.y0), S], color: hex("#22d3ee", 0.9) }, { pts: [S, O], color: hex("#22d3ee", 0.9) }, { pts: [wall(b.x0, 0), wall(b.x0, LY)], color: hex("#22d3ee", 0.5) }, { pts: [wall(0, b.y0), S], color: hex("#22d3ee", 0.5) });
    const [x0, x1, y0, y1] = SKULL_BBOX;
    for (const [x, y] of [[x0, y0], [x0, y1], [x1, y0], [x1, y1]]) L.push({ pts: [S, wall(x, y)], color: hex("#22d3ee", 0.35) });
    L.push({ pts: [wall(661, 0), S], color: hex("#fb923c", 0.9) }, ...cross3(S, 0.04, hex("#22d3ee", 1)), ...cross3(O, 0.04, hex("#22d3ee", 1)));
  }
  if (state.overlays.sight) for (const p of viewpointList()) { const E = toSharp(scene.panel, p.dx, p.dy, p.dz); L.push({ pts: [E, panelC(p.dy)], color: hex(p.color, 0.45) }, { pts: [E, skullC()], color: hex(p.color, 0.25) }); }
  if (state.overlays.wire && scene.depth_grid) {
    const g = scene.depth_grid, n = g.length - 1, f = scene.f_px, W = scene.width, H = scene.height, step = Math.max(1, Math.round(n / 32));
    const P = (i, j) => { const z = g[j][i]; return z == null ? null : [((i / n) * W - W / 2) / f * z, ((j / n) * H - H / 2) / f * z, z]; };
    for (let j = 0; j <= n; j += step) for (let i = 0; i <= n; i += step) {
      const a = P(i, j); if (!a) continue; const r = i + step <= n ? P(i + step, j) : null, d = j + step <= n ? P(i, j + step) : null;
      if (r) L.push({ pts: [a, r], color: [0.5, 0.9, 1, 0.55] }); if (d) L.push({ pts: [a, d], color: [0.5, 0.9, 1, 0.55] });
    }
  }
  viewer.setOverlayLines(L);
}
function viewpointList() {
  const pts = M.published_points.map((p) => ({ ...p, color: COLORS[p.name] || "#fff", key: 1 + M.published_points.indexOf(p) }));
  if (scene && scene.best_orbit_pose) pts.push({ name: "SHARP best (orbit)", dx: scene.best_orbit_pose.dx, dy: scene.best_orbit_pose.dy, dz: scene.best_orbit_pose.dz, color: COLORS["SHARP best (orbit)"], target: "skull", key: 5 });
  return pts;
}

// ---------------------------------------------------------------- minimap (plan view)
const mm = { x0: -300, x1: 3350, z0: -120, z1: 2650 };
function mapXY(x_mm, z_mm) { const c = $("minimap"); return [((x_mm - mm.x0) / (mm.x1 - mm.x0)) * c.width, c.height - ((z_mm - mm.z0) / (mm.z1 - mm.z0)) * c.height]; }
function drawMinimap() {
  const c = $("minimap"); if (c.offsetParent === null) return;
  const ctx = c.getContext("2d"); ctx.clearRect(0, 0, c.width, c.height);
  const cs = getComputedStyle(document.documentElement); const fg = `hsl(${cs.getPropertyValue("--foreground")})`, mu = `hsl(${cs.getPropertyValue("--muted-foreground")})`;
  ctx.font = "10px Inter, sans-serif"; ctx.fillStyle = mu; ctx.fillText("plan · Δx →  Δz ↑ (mm)", 6, 12);
  ctx.strokeStyle = fg; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(...mapXY(0, 0)); ctx.lineTo(...mapXY(LX, 0)); ctx.stroke();
  ctx.lineWidth = 1; ctx.strokeStyle = mu; for (let i = 0; i <= 8; i++) { const [x, y] = mapXY(i * LX / 8, 0); ctx.beginPath(); ctx.moveTo(x, y - 3); ctx.lineTo(x, y + 3); ctx.stroke(); }
  ctx.setLineDash([3, 3]); ctx.beginPath(); ctx.moveTo(...mapXY(LX, 0)); ctx.lineTo(...mapXY(mm.x1, 0)); ctx.stroke(); ctx.setLineDash([]);
  const b = M.boxer; const S = mapXY(b.S_mm[0], 0), O = mapXY(b.O_mm[0], b.O_mm[2]);
  ctx.strokeStyle = "#22d3ee"; ctx.beginPath(); ctx.moveTo(...mapXY(b.x0, 0)); ctx.lineTo(...S); ctx.lineTo(...O); ctx.stroke();
  ctx.beginPath(); ctx.ellipse(O[0], O[1], (80 / (mm.x1 - mm.x0)) * c.width, (16 / (mm.z1 - mm.z0)) * c.height, 0, 0, Math.PI * 2); ctx.stroke();
  if (state.traj) { ctx.strokeStyle = "#a78bfa"; ctx.beginPath(); for (let i = 0; i <= 60; i++) { const p = state.traj.fn(i / 60); const [x, y] = mapXY(p.dx + LX, p.dz); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); } ctx.stroke(); }
  for (const p of [...viewpointList(), ...state.savedViewpoints]) { const [x, y] = mapXY(p.dx + LX, p.dz); ctx.fillStyle = p.color || "#f472b6"; ctx.beginPath(); ctx.arc(x, y, 3.5, 0, Math.PI * 2); ctx.fill(); }
  if (scene) {
    const cur = currentPoseMM(); const tmm = toMM(scene.panel, viewer.target);
    const [x, y] = mapXY(cur.dx + LX, cur.dz), [tx, ty] = mapXY(tmm.dx + LX, tmm.dz);
    ctx.strokeStyle = "#f87171"; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(tx, ty); ctx.stroke();
    ctx.fillStyle = "#f87171"; ctx.beginPath(); ctx.arc(x, y, 5, 0, Math.PI * 2); ctx.fill(); ctx.strokeStyle = "#000"; ctx.stroke();
  }
}
$("minimap").addEventListener("pointerdown", (e) => {
  const c = $("minimap"), r = c.getBoundingClientRect();
  const x = mm.x0 + ((e.clientX - r.left) / r.width) * (mm.x1 - mm.x0), z = mm.z1 - ((e.clientY - r.top) / r.height) * (mm.z1 - mm.z0);
  const cur = currentPoseMM(); stopTraj(); setPoseMM(x - LX, cur.dy, Math.max(20, z)); if (state.photoFit) setFov(50);
});
$("minimap-toggle").onclick = () => { const w = $("minimap-toggle").parentElement; w.classList.toggle("collapsed"); $("minimap-toggle").textContent = w.classList.contains("collapsed") ? "▸ plan view" : "▾ plan view"; };

// ---------------------------------------------------------------- HUD + sliders
function updateHUD() {
  if (!scene) return;
  const cur = currentPoseMM(), g = eyeGeometry(cur);
  $("h-dx").textContent = cur.dx.toFixed(0); $("h-dy").textContent = cur.dy.toFixed(0); $("h-dz").textContent = cur.dz.toFixed(0);
  $("h-az").textContent = g.az.toFixed(1) + "°"; $("h-el").textContent = g.el.toFixed(1) + "°"; $("h-dist").textContent = g.dist.toFixed(0);
  $("h-R").textContent = g.R.toFixed(0); $("h-alpha").textContent = g.alpha.toFixed(1) + "°"; $("h-fov").textContent = effectiveFovDeg().toFixed(0) + "°";
  if (!state.sliderDrag) { $("c-dx").value = cur.dx; $("c-dy").value = cur.dy; $("c-dz").value = cur.dz; $("v-dx").textContent = cur.dx.toFixed(0); $("v-dy").textContent = cur.dy.toFixed(0); $("v-dz").textContent = cur.dz.toFixed(0); }
  drawMinimap();
}
for (const k of ["dx", "dy", "dz"]) {
  const el = $("c-" + k);
  el.addEventListener("pointerdown", () => (state.sliderDrag = true)); el.addEventListener("pointerup", () => (state.sliderDrag = false));
  el.addEventListener("input", () => { stopTraj(); const cur = currentPoseMM(); cur[k] = parseFloat(el.value); setPoseMM(cur.dx, cur.dy, cur.dz); if (state.photoFit) setFov(50); $("v-" + k).textContent = el.value; });
}
$("c-fov").addEventListener("input", () => setFov(parseFloat($("c-fov").value)));
$("target-tabs").addEventListener("click", (e) => { const b = e.target.closest("[data-target]"); if (!b) return; state.targetMode = b.dataset.target; syncSeg("target-tabs", "target", state.targetMode); const cur = currentPoseMM(); setPoseMM(cur.dx, cur.dy, cur.dz); });
$("btn-fit-skull").onclick = () => { const cur = currentPoseMM(); state.targetMode = "skull"; syncSeg("target-tabs", "target", "skull"); setPoseMM(cur.dx, cur.dy, cur.dz); setFov(Math.min(110, Math.max(10, 2 * Math.atan(0.55 * 915 / eyeGeometry(cur).dist) * 180 / Math.PI * 1.4))); };
$("btn-fit-panel").onclick = () => { const cur = currentPoseMM(); state.targetMode = "centre"; syncSeg("target-tabs", "target", "centre"); setPoseMM(cur.dx, cur.dy, cur.dz); setFov(Math.min(110, 2 * Math.atan(0.6 * Math.hypot(LX, LY) / eyeGeometry(cur).R) * 180 / Math.PI)); };
$("btn-reset").onclick = () => { stopTraj(); photoView(); };

// ---------------------------------------------------------------- view modes
function setMode(m) {
  state.mode = m; viewer.drawMode = m; syncSeg("mode-seg", "mode", m);
  $("split-handle").hidden = m !== "split"; $("split-handle").dataset.label = `splat ⟷ ${state.compare}`;
  $("h-mode").textContent = m === "split" ? `split · ${state.compare}` : MODE_LABEL[m];
}
$("mode-seg").addEventListener("click", (e) => { const b = e.target.closest("[data-mode]"); if (b) setMode(b.dataset.mode); });
$("compare-select").addEventListener("change", () => { state.compare = $("compare-select").value; viewer.compareMode = state.compare; setMode(state.mode); });
(() => { const body = $("stage-body"); let dragging = false;
  body.addEventListener("pointerdown", (e) => { if (state.mode === "split" && e.altKey) { dragging = true; move(e); e.stopPropagation(); } }, true);
  window.addEventListener("pointerup", () => (dragging = false)); window.addEventListener("pointermove", (e) => { if (dragging) move(e); });
  function move(e) { const r = body.getBoundingClientRect(); const pct = Math.min(0.98, Math.max(0.02, (e.clientX - r.left) / r.width)); viewer.split = pct; body.style.setProperty("--split", pct * 100 + "%"); }
})();
$("overlay-toggles").addEventListener("change", (e) => { const i = e.target.closest("[data-ov]"); if (!i) return; state.overlays[i.dataset.ov] = i.checked; buildOverlays(); });

// ---------------------------------------------------------------- layout: collapsible panels, clean view
const labEl = () => $("view-lab");
const togglePanel = (side) => { labEl().classList.toggle("no-" + side); viewer.resize(); };
$("sidebar-toggle").onclick = () => togglePanel("left");
$("inspector-toggle").onclick = () => togglePanel("right");
$("reveal-left").onclick = () => togglePanel("left");
$("reveal-right").onclick = () => togglePanel("right");
$("btn-clean").onclick = () => { document.body.classList.toggle("clean"); $("btn-clean").setAttribute("aria-pressed", document.body.classList.contains("clean")); viewer.resize(); };

// ---------------------------------------------------------------- scenes
function sceneOptions() {
  const groups = {};
  for (const s of M.scenes) (groups[s.group || "Reference"] = groups[s.group || "Reference"] || []).push(s);
  $("scene-select").innerHTML = Object.entries(groups).map(([g, list]) => `<optgroup label="${g}">${list.map((s) => `<option value="${s.id}">${s.label}</option>`).join("")}</optgroup>`).join("");
}
async function loadScene(id) {
  // keep the eye at the same physical position (mm) across scenes; frames differ per run
  const prevPose = scene && viewer ? { mm: currentPoseMM(), target: state.targetMode, fov: state.photoFit ? null : state.fov } : null;
  scene = M.scenes.find((s) => s.id === id) || M.scenes[0];
  $("scene-select").value = scene.id; $("h-scene").textContent = scene.label; $("scene-badge").textContent = scene.group === "Tests" ? "test" : `${scene.f35_mm} mm`;
  $("btn-delete-run").hidden = scene.group !== "Tests";
  $("scene-info").textContent = `f_px ${scene.f_px.toFixed(0)} · depth median ${scene.depth_m.median.toFixed(2)} m · relief ${(scene.relief_mm || 0).toFixed(0)} mm` + (scene.source_pose_mm ? ` · from (${scene.source_pose_mm.dx.toFixed(0)}, ${scene.source_pose_mm.dy.toFixed(0)}, ${scene.source_pose_mm.dz.toFixed(0)})` : "");
  const cam0 = toMM(scene.panel, [0, 0, 0]);
  const rows = [["Set", scene.group], ["Assumed lens", `${scene.f35_mm} mm eq`], ["f_px", scene.f_px.toFixed(1)], ["Camera (Δx, Δy, Δz)", `${cam0.dx.toFixed(0)}, ${cam0.dy.toFixed(0)}, ${cam0.dz.toFixed(0)} mm`],
                ["Depth p05 · med · p95", `${scene.depth_m.p05.toFixed(2)} · ${scene.depth_m.median.toFixed(2)} · ${scene.depth_m.p95.toFixed(2)} m`], ["Relief p95−p05", `${(scene.relief_mm || 0).toFixed(0)} mm`], ["mm per SHARP unit", scene.panel.scale_mm_per_unit.toFixed(1)]];
  if (scene.grid_stats && scene.grid_stats.resemblance) { const pk = scene.grid_stats.resemblance.peak, dd = scene.grid_stats.resemblance.displacement_from_boxer_mm; rows.push(["Grid peak (Δx, Δz)", `${pk.dx}, ${pk.dz} mm · ${pk.value.toFixed(2)}`], ["Offset from Boxer O", `${dd.euclid.toFixed(0)} mm`]); }
  if (scene.best_orbit_pose) { const b = scene.best_orbit_pose; rows.push(["Best orbit pose", `az ${b.az}° el ${b.el}° d ${b.dist_mm}`]); }
  if (scene.derived_from) rows.push(["Derived from", scene.derived_from], ["Source", scene.source_image_is_view ? "rendered view" : "photograph"]);
  $("scene-kv").innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");
  viewer.setScene({ fx: scene.f_px, width: scene.width, height: scene.height });
  viewer.setPanelQuad([wall(0, 0), wall(LX, 0), wall(LX, LY), wall(0, LY)], M.painting.image);
  if (scene.depth_grid) viewer.setDepthMesh(scene.depth_grid, scene.f_px, scene.width, scene.height);
  buildOverlays(); renderViewpoints(); renderTrajectories();
  if (prevPose) { if (prevPose.fov == null) photoView(); else setPoseMM(prevPose.mm.dx, prevPose.mm.dy, prevPose.mm.dz, { target: prevPose.target === "free" ? "centre" : prevPose.target, fov: prevPose.fov }); }
  if (STATIC_BUILD && !bridged) {
    $("stage-loading").hidden = false;
    $("stage-loading").innerHTML = `<div class="stage-note"><b>The Lab needs a local server.</b>
      <span>Reconstructions run to about a gigabyte each, so they are not published. Method, Log and Report are complete here.
      Start <code>sharp-studio/server.py</code> on this machine and reload: the page will find it on
      <code>localhost:8765</code> and the Lab will work from this URL.</span></div>`;
  } else if (state.loadedSplat !== scene.splat) {
    state.loadedSplat = scene.splat; $("stage-loading").hidden = false; $("stage-loading-text").textContent = "loading " + scene.label;
    try { await viewer.loadUrl(scene.splat); $("stage-loading-text").textContent = "sorting…"; } catch (e) { toast("Could not load scene", e.message, "error"); $("stage-loading").hidden = true; }
  }
  if (state.view === "lab") writeUrl("lab", false);
}
$("scene-select").addEventListener("change", () => loadScene($("scene-select").value));
$("btn-scene-details").onclick = () => { labEl().classList.remove("no-right"); $("details-section").open = true; $("details-section").scrollIntoView({ behavior: "smooth" }); viewer.resize(); };
$("btn-delete-run").onclick = async () => { if (scene.group !== "Tests" || !confirm(`Delete ${scene.id}? Removes its files from runs_user/.`)) return; await fetch(`api/lab/user_runs/${scene.id}`, { method: "DELETE" }); toast("Run deleted", scene.id); await refreshManifest(); loadScene(M.scenes[0].id); };

// ---------------------------------------------------------------- viewpoints (published + saved)
function vpRow({ color, name, sub, key, onclick, onremove, active }) {
  const b = document.createElement("button"); b.className = "vp" + (active ? " active" : "");
  b.innerHTML = `<span class="sw"></span><span class="name"></span><span class="sub"></span>`;
  b.querySelector(".sw").style.background = color; b.querySelector(".name").textContent = name; b.querySelector(".sub").innerHTML = (key != null ? `<span class="key">${key}</span> ` : "") + sub;
  if (onremove) { const x = document.createElement("span"); x.className = "x"; x.textContent = "✕"; x.title = "remove"; x.onclick = (e) => { e.stopPropagation(); onremove(); }; b.querySelector(".sub").appendChild(x); }
  b.onclick = onclick; b.title = name; return b;
}
function renderViewpoints() {
  const el = $("viewpoints"); el.innerHTML = "";
  const cam0 = toMM(scene.panel, [0, 0, 0]);
  el.appendChild(vpRow({ color: COLORS["Photo camera"], name: "Photo camera", sub: `${cam0.dx.toFixed(0)}, ${cam0.dy.toFixed(0)}, ${cam0.dz.toFixed(0)}`, key: 0, onclick: () => { stopTraj(); photoView(); } }));
  for (const p of viewpointList()) el.appendChild(vpRow({ color: p.color, name: p.name, sub: `${p.dx.toFixed(0)}, ${p.dy.toFixed(0)}, ${p.dz.toFixed(0)}`, key: p.key, onclick: () => goToViewpoint(p) }));
  if (state.savedViewpoints.length) { const h = document.createElement("div"); h.className = "row-between text-xs text-muted"; h.style.margin = "6px 0 2px"; h.innerHTML = `<span>Saved</span>`; el.appendChild(h); }
  for (const p of state.savedViewpoints) el.appendChild(vpRow({ color: p.color || "#f472b6", name: p.name, sub: `${p.dx.toFixed(0)}, ${p.dy.toFixed(0)}, ${p.dz.toFixed(0)}`, onclick: () => goToViewpoint(p), onremove: async () => { state.savedViewpoints = state.savedViewpoints.filter((q) => q !== p); await api("api/lab/viewpoints", { viewpoints: state.savedViewpoints }); renderViewpoints(); buildOverlays(); } }));
  const add = document.createElement("button"); add.className = "btn btn-outline btn-xs"; add.textContent = "+ save current view"; add.style.marginTop = "4px";
  add.onclick = async () => { const name = prompt("Name for this viewpoint"); if (!name) return; const cur = currentPoseMM();
    state.savedViewpoints.push({ id: "vp-" + Date.now(), name, dx: +cur.dx.toFixed(1), dy: +cur.dy.toFixed(1), dz: +cur.dz.toFixed(1), target: state.targetMode, fov: +effectiveFovDeg().toFixed(1), mode: state.mode, scene: scene.id, saved: new Date().toISOString().slice(0, 10), color: "#f472b6" });
    await api("api/lab/viewpoints", { viewpoints: state.savedViewpoints }); renderViewpoints(); buildOverlays(); toast("Viewpoint saved", name); };
  el.appendChild(add);
}
function goToViewpoint(p) {
  stopTraj();
  if (p.mode) setMode(p.mode);
  state.targetMode = p.target || "centre"; syncSeg("target-tabs", "target", state.targetMode);
  setPoseMM(p.dx, p.dy, p.dz, { fov: p.fov || (state.photoFit ? 50 : state.fov) });

}

// ---------------------------------------------------------------- trajectories (built-in + saved keyframe paths)
function trajectories() {
  const O = M.published_points.find((p) => p.name.includes("inverseTrapezoid"));   // 776.9, 1035, 257.9
  const BEST = { dx: 740.5, dy: 1035, dz: 255.3 };   // Boxer exact-perspective solution
  const PEAK = { dx: 675, dy: 1035, dz: 160 };       // the reconstruction's own grid maximum
  const cam0 = () => toMM(scene.panel, [0, 0, 0]);   // where the model places the photograph's camera
  const K = (o) => ({ target: "centre", mode: "sharp", fov: 50, dy: 1035, ...o });

  // Composite paths: camera and view mode are keyframed together, so a transition between
  // representations happens inside a single move rather than as a separate manual step.
  const c = cam0(), pf = effectivePhotoFov();
  const composite = [
    { id: "control-resolve", name: "Flat panel → (740.5, 1035, 255.3)",
      desc: "Control condition. The panel is treated as a plane and the camera runs from the photograph's own camera to Boxer's exact-perspective solution. Resemblance 0.997 at the endpoint.",
      kfs: [K({ dx: c.dx, dy: c.dy, dz: c.dz, fov: pf, mode: "flat" }),
            K({ ...BEST, fov: 22, target: "skull", mode: "flat" })] },

    { id: "model-same-coordinate", name: "Reconstruction → same coordinate",
      desc: "Identical camera path with the SHARP reconstruction substituted for the panel. Resemblance 0.54 at the endpoint; the tracked skull box is 87 % empty at Boxer's O.",
      kfs: [K({ dx: c.dx, dy: c.dy, dz: c.dz, fov: pf, mode: "sharp" }),
            K({ ...BEST, fov: 22, target: "skull", mode: "sharp" })] },

    { id: "wipe-at-O", name: "Wipe at O · reconstruction vs panel",
      desc: "Camera fixed at Boxer's published solution (776.9, 1035, 257.9). The reconstruction is wiped across the full frame against the flat panel, holding pose, field of view and eye height constant.",
      kfs: [K({ dx: O.dx, dz: O.dz, fov: 40, target: "skull", mode: "sharp" }),
            K({ dx: O.dx, dz: O.dz, fov: 40, target: "skull", mode: "flat" })] },

    { id: "relief-disclosure", name: "Relief disclosure · wire → splat",
      desc: "Oblique traverse at eye 1600 mm. The depth wireframe carries 623 mm of relief across a surface that is physically flat; the second half shows the same geometry textured.",
      kfs: [K({ dx: -2400, dy: 1600, dz: 2000, fov: 55, mode: "wire" }),
            K({ dx: -400, dy: 1600, dz: 2400, fov: 55, mode: "wire" }),
            K({ dx: 900, dy: 1600, dz: 2400, fov: 55, mode: "sharp" }),
            K({ dx: 2200, dy: 1600, dz: 2000, fov: 55, mode: "sharp" })] },

    { id: "residual-141", name: "Grid maximum → O · 141 mm residual",
      desc: "From the reconstruction's best-scoring grid position (675, 1035, 160) to Boxer's O. Euclidean residual 141 mm, or 7.8 units of the 13 mm along-wall disagreement between the two published human estimates.",
      kfs: [K({ ...PEAK, fov: 35, target: "skull", mode: "sharp" }),
            K({ dx: O.dx, dz: O.dz, fov: 35, target: "skull", mode: "sharp" })] },

    { id: "grazing-floor", name: "Grazing descent · az 84°, el −6°",
      desc: "The geometry the reconstruction scores highest on: a near-tangential view down the invented floor from 0.4 m off the wall. Mesh pass first, then the same pose as splats.",
      kfs: [K({ dx: 1400, dy: 1500, dz: 900, fov: 45, target: "skull", mode: "mesh" }),
            K({ dx: 500, dy: 500, dz: 400, fov: 45, target: "skull", mode: "mesh" }),
            K({ dx: -500, dy: 260, dz: 400, fov: 45, target: "skull", mode: "sharp" })] },
  ].map((t) => ({ ...t, fn: keyframeFn(t.kfs), group: "Composite" }));

  // Single-axis sweeps: one parameter moves, everything else is held.
  const axes = [
    { id: "approach", name: "Photo camera → O", desc: "Arc from the photograph's camera to Boxer's viewing point, eye height held at the panel midline.", fn: (t) => { const cc = cam0(), e = ease(t); const a0 = Math.atan2(cc.dx + LX / 2, cc.dz), a1 = Math.atan2(O.dx + LX / 2, O.dz); const R0 = Math.hypot(cc.dx + LX / 2, cc.dz), R1 = Math.hypot(O.dx + LX / 2, O.dz); const a = lerp(a0, a1, e), R = lerp(R0, R1, e); return { dx: R * Math.sin(a) - LX / 2, dy: 1035, dz: R * Math.cos(a), target: "centre", fov: lerp(effectivePhotoFov(), 50, e), mode: state.mode }; } },
    { id: "dz", name: "Δz sweep at Boxer's Δx", desc: "600 → 40 mm off the wall, Δx and eye height fixed.", fn: (t) => ({ dx: O.dx, dy: 1035, dz: lerp(600, 40, t), target: "centre", fov: 50, mode: state.mode }) },
    { id: "dx", name: "Δx sweep at Boxer's Δz", desc: "300 → 1500 mm along the wall, Δz and eye height fixed.", fn: (t) => ({ dx: lerp(300, 1500, t), dy: 1035, dz: O.dz, target: "centre", fov: 50, mode: state.mode }) },
    { id: "descend", name: "Eye height sweep at O", desc: "2000 → 200 mm at Boxer's (Δx, Δz).", fn: (t) => ({ dx: O.dx, dy: lerp(2000, 200, t), dz: O.dz, target: "centre", fov: 50, mode: state.mode }) },
    { id: "orbit", name: "Orbit the skull", desc: "Azimuth −90° → +90° at elevation 20°, 2 m from the skull centre.", fn: (t) => { const az = lerp(-90, 90, t) * Math.PI / 180, el = 20 * Math.PI / 180, d = 2000; return { dx: SKULL_C[0] + d * Math.sin(az) * Math.cos(el) - LX, dy: SKULL_C[1] + d * Math.sin(el), dz: d * Math.cos(az) * Math.cos(el), target: "skull", fov: 40, mode: state.mode }; } },
  ].map((t) => ({ ...t, group: "Single axis" }));

  const saved = state.savedTrajs.map((tr) => ({ id: tr.id, name: tr.name, desc: `${tr.keyframes.length} keyframes`, saved: true, group: "Saved", fn: keyframeFn(tr.keyframes) }));
  return [...composite, ...axes, ...saved];
}
// View modes are discrete. Where one side of a transition is the splat render, the split
// renderer can show both at once, so the change plays as a wipe across the frame; any other
// pair has no simultaneous representation and cuts at the midpoint instead.
function modeAt(ma, mb, u) {
  if (ma === mb) return { mode: ma };
  if (ma === "sharp") return { mode: "split", compare: mb, split: 1 - u };
  if (mb === "sharp") return { mode: "split", compare: ma, split: u };
  return { mode: u < 0.5 ? ma : mb };
}
function keyframeFn(kfs) {
  return (t) => {
    if (kfs.length === 1) return { ...kfs[0], ...modeAt(kfs[0].mode || "sharp", kfs[0].mode || "sharp", 0) };
    const n = kfs.length - 1, x = Math.min(n - 1e-9, Math.max(0, t * n)), i = Math.floor(x), u = ease(x - i);
    const a = kfs[i], b = kfs[i + 1];
    return { dx: lerp(a.dx, b.dx, u), dy: lerp(a.dy, b.dy, u), dz: lerp(a.dz, b.dz, u), fov: lerp(a.fov, b.fov, u),
             target: u < 0.5 ? a.target : b.target, ...modeAt(a.mode || "sharp", b.mode || "sharp", u) };
  };
}
function renderTrajectories() {
  const el = $("trajectories"); el.innerHTML = "";
  let group = null;
  for (const tr of trajectories()) {
    if (tr.group !== group) { group = tr.group; const h = document.createElement("p"); h.className = "group-label"; h.textContent = group; el.appendChild(h); }
    const row = vpRow({ color: tr.saved ? "#f472b6" : tr.group === "Composite" ? "#38bdf8" : "#a78bfa",
      name: tr.name, sub: "", active: state.traj && state.traj.id === tr.id, onclick: () => selectTraj(tr),
      onremove: tr.saved ? async () => { state.savedTrajs = state.savedTrajs.filter((q) => q.id !== tr.id); await api("api/lab/trajectories", { trajectories: state.savedTrajs }); if (state.traj && state.traj.id === tr.id) state.traj = null; renderTrajectories(); } : null });
    row.title = tr.desc;
    el.appendChild(row);
  }
  const d = $("traj-desc"); if (d) d.textContent = state.traj ? state.traj.desc || "" : "";
  renderKeyframes();
}
function renderKeyframes() {
  const el = $("kf-list"); el.innerHTML = "";
  state.keyframes.forEach((k, i) => { const d = document.createElement("div"); d.className = "kf"; d.innerHTML = `<span>${i + 1} · ${k.dx.toFixed(0)}, ${k.dy.toFixed(0)}, ${k.dz.toFixed(0)} · ${k.fov.toFixed(0)}° · <b>${MODE_LABEL[k.mode || "sharp"]}</b></span><span class="x" style="cursor:pointer">✕</span>`; d.querySelector(".x").onclick = () => { state.keyframes.splice(i, 1); renderKeyframes(); }; el.appendChild(d); });
  $("kf-save").disabled = state.keyframes.length < 2;
}
$("kf-add").onclick = () => { const c = currentPoseMM(); state.keyframes.push({ dx: +c.dx.toFixed(1), dy: +c.dy.toFixed(1), dz: +c.dz.toFixed(1), fov: +effectiveFovDeg().toFixed(1), target: state.targetMode === "free" ? "centre" : state.targetMode, mode: state.mode === "split" ? "sharp" : state.mode }); renderKeyframes(); if (state.keyframes.length >= 2) { state.traj = { id: "draft", name: "draft path", fn: keyframeFn(state.keyframes) }; $("traj-play").disabled = $("traj-record").disabled = $("traj-scrub").disabled = false; } };
$("kf-save").onclick = async () => { const name = $("kf-name").value.trim() || `path ${state.savedTrajs.length + 1}`; state.savedTrajs.push({ id: "traj-" + Date.now(), name, keyframes: state.keyframes.slice(), scene: scene.id, saved: new Date().toISOString() }); await api("api/lab/trajectories", { trajectories: state.savedTrajs }); state.keyframes = []; $("kf-name").value = ""; renderTrajectories(); toast("Path saved", name); };
function selectTraj(tr) { state.traj = tr; state.trajT = 0; renderTrajectories(); $("traj-play").disabled = $("traj-record").disabled = $("traj-scrub").disabled = false; applyTraj(0); playTraj(true); }
function applyTraj(t) {
  const p = state.traj.fn(t);
  state.trajT = t; $("traj-scrub").value = t; $("traj-t").textContent = t.toFixed(2);
  state.targetMode = p.target; syncSeg("target-tabs", "target", p.target);
  if (p.compare && p.compare !== state.compare) { state.compare = p.compare; viewer.compareMode = p.compare; $("compare-select").value = p.compare; }
  if (p.split !== undefined) { viewer.split = p.split; $("stage-body").style.setProperty("--split", p.split * 100 + "%"); }
  if (p.mode && p.mode !== state.mode) setMode(p.mode);
  setPoseMM(p.dx, p.dy, p.dz, { target: p.target, fov: p.fov });
}
let trajRaf = null, trajStart = 0;
function playTraj(on) {
  state.playing = on; $("traj-play").textContent = on ? "Pause" : "Play";
  if (!on) { cancelAnimationFrame(trajRaf); return; }
  const dur = parseFloat($("traj-dur").value) * 1000; trajStart = performance.now() - state.trajT * dur;
  const tick = (now) => { if (!state.playing) return; let t = (now - trajStart) / dur; if (t >= 1) { applyTraj(1); playTraj(false); return; } applyTraj(t); trajRaf = requestAnimationFrame(tick); };
  trajRaf = requestAnimationFrame(tick);
}
function stopTraj() { if (state.playing) playTraj(false); }
$("traj-play").onclick = () => { if (!state.traj) return; if (!state.playing && state.trajT >= 1) state.trajT = 0; playTraj(!state.playing); };
$("traj-scrub").addEventListener("input", () => { stopTraj(); applyTraj(parseFloat($("traj-scrub").value)); });
$("traj-dur").addEventListener("input", () => ($("v-dur").textContent = $("traj-dur").value));
$("traj-record").onclick = () => recordTraj();

// ---------------------------------------------------------------- capture + recording
function captureMeta(extra = {}) {
  const cur = currentPoseMM(), g = eyeGeometry(cur), tmm = toMM(scene.panel, viewer.target);
  return { scene: scene.id, scene_label: scene.label, scene_group: scene.group, f35_mm: scene.f35_mm, f_px: scene.f_px, splat: scene.splat, mode: state.mode, compare: state.compare, split: viewer.split,
           pose_mm: { dx: +cur.dx.toFixed(2), dy: +cur.dy.toFixed(2), dz: +cur.dz.toFixed(2) }, target_mm: { dx: +tmm.dx.toFixed(2), dy: +tmm.dy.toFixed(2), dz: +tmm.dz.toFixed(2) }, target_mode: state.targetMode,
           pose_sharp: { pos: viewer.pos.map((v) => +v.toFixed(5)), target: viewer.target.map((v) => +v.toFixed(5)) }, eye: { R_mm: +g.R.toFixed(1), alpha_deg: +g.alpha.toFixed(2), skull_az_deg: +g.az.toFixed(2), skull_el_deg: +g.el.toFixed(2), skull_dist_mm: +g.dist.toFixed(1) },
           fov_deg: +effectiveFovDeg().toFixed(2), fratio: viewer.fRatioOverride, photo_fit: state.photoFit, canvas_px: [viewer.gl.canvas.width, viewer.gl.canvas.height], overlays: { ...state.overlays }, overlays_drawn: viewer.overlaysOn,
           panel: scene.panel, trajectory: state.traj ? { id: state.traj.id, t: state.trajT } : null, url: location.href, ...extra };
}
// Captures travel as JPEG (q 0.93): PNGs of splat renders compress badly (10 MB+) and large uploads fail.
const blobToDataURL = (blob) => new Promise((r) => { const fr = new FileReader(); fr.onload = () => r(fr.result); fr.readAsDataURL(blob); });
const nextFrames = (n) => new Promise((r) => { const step = () => (--n <= 0 ? r() : requestAnimationFrame(step)); requestAnimationFrame(step); });
async function settleAndRead(quality = 0.93, frames = 3) {
  // The live loop draws every frame into a preserved buffer (and posts the view to the sorter), so after a
  // few frames the canvas holds a fully sorted render of the current pose: read it directly.
  viewer.paused = false;
  await nextFrames(frames); await new Promise((r) => setTimeout(r, 120)); await nextFrames(2);
  if (viewer.canvas.width < 16 || viewer.canvas.height < 16) throw new Error("canvas has no size (is the Lab view visible?)");
  // toDataURL is synchronous and needs no Blob storage (Chrome's blob quota can be exhausted by long render batches)
  const url = viewer.canvas.toDataURL("image/jpeg", quality);
  if (!url || url.length < 100) throw new Error("toDataURL returned nothing");
  return url;
}
async function grabImage(quality = 0.93) {
  if (state.view !== "lab") { showView("lab"); await new Promise((r) => setTimeout(r, 120)); }
  viewer.resize();
  return settleAndRead(quality);
}
async function capture(tag, note, folder) {
  if (!scene) return;
  let png;
  try { png = await grabImage(); } catch (e) { toast("Capture failed", e.message, "error"); return; }
  const meta = captureMeta({ tag: tag || $("cap-tag").value.trim(), note: note !== undefined ? note : $("cap-note").value.trim() });
  const res = await api("api/lab/capture", { png, meta, folder });
  if (res.error) { toast("Capture failed", res.error, "error"); return; }
  toast("Captured", res.entry.file.split("/").pop(), "success"); state.captures.push(res.entry); renderRecent(); reportsDirty = logDirty = true;
  return res.entry;
}
async function captureSet() { const m = state.mode; for (const mode of ["sharp", "mesh", "flat", "split"]) { setMode(mode); await capture(($("cap-tag").value.trim() || "set") + "-" + mode, undefined); } setMode(m); }
// Captures are written at full render size (~800 KB each) but are only ever shown as thumbnails here,
// in the Log grid and in the report strip. The server keeps a 480 px copy in _thumbs/ beside each file;
// entries written before that existed have no `thumb` field, so derive the path and fall back on error.
const thumbSrc = (c) => "anamorph/" + (c.thumb ? c.thumb
  : c.kind === "capture" ? c.file.replace(/([^/]+)\.[^.]+$/, "_thumbs/$1.jpg") : c.file);
const useThumb = (img, c) => { img.src = thumbSrc(c); img.loading = "lazy"; img.decoding = "async"; img.onerror = () => { img.onerror = null; img.src = "anamorph/" + c.file; }; };

function renderRecent() { const el = $("cap-recent"); el.innerHTML = ""; for (const c of state.captures.filter((c) => c.kind === "capture").slice(-6).reverse()) { const im = document.createElement("img"); useThumb(im, c); im.title = c.file; im.onclick = () => openLightbox(c); el.appendChild(im); } }
async function recordTraj() {
  if (!state.traj) return;
  stopTraj();
  const fps = 24, dur = parseFloat($("traj-dur").value), n = Math.round(fps * dur);
  const start = await api("api/lab/record", { action: "start", name: state.traj.id, scene: scene.id, meta: { ...captureMeta(), pose_mm_start: state.traj.fn(0), trajectory_desc: state.traj.desc, duration_s: dur, fps, n_frames: n } });
  toast("Recording", `${n} frames → ${start.rec}`); $("traj-record").disabled = true;
  for (let i = 0; i < n; i++) {
    applyTraj(i / (n - 1));
    const png = await settleAndRead(0.9, 2);
    await api("api/lab/record", { action: "frame", rec: start.rec, i, png, meta: { t: i / (n - 1), pose_mm: currentPoseMM(), fov_deg: effectiveFovDeg(), mode: state.mode } });
    if (i % 12 === 0) $("traj-t").textContent = `rec ${i}/${n}`;
  }
  viewer.paused = false;
  const fin = await api("api/lab/record", { action: "finish", rec: start.rec, fps });
  $("traj-record").disabled = false; toast("Recording saved", fin.entry ? fin.entry.file || fin.entry.id : "done", "success"); if (fin.entry) state.captures.push(fin.entry); reportsDirty = logDirty = true;
}
$("btn-capture").onclick = () => capture(); $("btn-capture-2").onclick = () => capture(); $("btn-capture-set").onclick = captureSet;

// ---------------------------------------------------------------- Run SHARP from the current camera
async function runSharpFromHere() {
  if (!scene) return;
  if (state.view !== "lab") { showView("lab"); await new Promise((r) => setTimeout(r, 120)); }
  const source = $("run-source").value, size = parseInt($("run-size").value), tag = $("run-tag").value.trim();
  const cur = currentPoseMM();
  // render the source image at the requested size with the current intrinsics, overlays off
  const canvas = viewer.canvas, wrap = canvas.parentElement; const prevW = wrap.style.width, prevH = wrap.style.height, prevMode = viewer.drawMode, prevOv = viewer.overlaysOn;
  const box = wrap.getBoundingClientRect(); const fr = viewer.fRatioOverride || (0.5 / Math.tan((effectiveFovDeg() * Math.PI) / 360));
  let png, meta;
  try {
    viewer.overlaysOn = false; viewer.drawMode = source === "flat" ? "flat" : (state.mode === "split" ? "sharp" : state.mode);
    // render off the live layout: a fixed-size canvas box, same intrinsics (fratio = focal / width)
    canvas.style.position = "absolute"; canvas.style.inset = "auto"; canvas.style.left = "0"; canvas.style.top = "0"; canvas.style.width = size + "px"; canvas.style.height = size + "px";
    viewer.fRatioOverride = fr; viewer.resize();
    if (viewer.canvas.width < 16) throw new Error("render canvas has no size");
    meta = captureMeta({ tag, source, size, fratio: fr, ref_panel: scene.panel, note: `SHARP run from (${cur.dx.toFixed(0)}, ${cur.dy.toFixed(0)}, ${cur.dz.toFixed(0)}) mm, ${effectiveFovDeg().toFixed(0)}°, source ${source}` });
    meta.render_px = [viewer.canvas.width, viewer.canvas.height];
    png = await settleAndRead(0.96, 4);
  } catch (e) { toast("Render for SHARP failed", e.message, "error"); }
  finally { canvas.style.cssText = ""; viewer.overlaysOn = prevOv; viewer.drawMode = prevMode; viewer.fRatioOverride = state.photoFit ? null : (0.5 / Math.tan((state.fov * Math.PI) / 360)); viewer.resize(); viewer.paused = false; }
  if (!png) return;
  $("run-status").textContent = `uploading ${(png.length / 1e6).toFixed(1)} MB…`;
  let res;
  try { res = await api("api/lab/run_sharp", { png, meta }); } catch (e) { toast("Upload failed", e.message, "error"); $("run-status").textContent = "upload failed"; return; }
  if (res.error) { toast("Run failed", res.error, "error"); return; }
  toast("Reconstruction queued", res.id); $("run-status").textContent = `queued ${res.id}`;
  pollUserRuns();
}
$("btn-run-sharp").onclick = runSharpFromHere; $("btn-run-sharp-top").onclick = runSharpFromHere;
async function pollUserRuns() {
  clearTimeout(state.pollTimer);
  const { runs } = await api("api/lab/user_runs");
  const prev = state.userRuns; state.userRuns = runs; renderUserRuns();
  const active = runs.some((r) => r.status === "queued" || r.status === "running");
  for (const r of runs) { const p = prev.find((q) => q.id === r.id); if (p && p.status !== "ready" && r.status === "ready") { toast("Reconstruction ready", r.id, "success"); await refreshManifest(); reportsDirty = logDirty = true; loadScene(r.id); } if (p && p.status !== "error" && r.status === "error") toast("Reconstruction failed", r.error, "error"); }
  if (active) { $("engine-pill").dataset.state = "busy"; $("engine-text").textContent = "reconstructing"; state.pollTimer = setTimeout(pollUserRuns, 800); }
  else { $("engine-pill").dataset.state = "ready"; $("engine-text").textContent = `${M.scenes.length} scenes`; }
}
function renderUserRuns() {
  const el = $("user-runs"); el.innerHTML = "";
  for (const r of state.userRuns.slice().reverse().slice(0, 8)) {
    const sub = r.status === "ready" ? `${r.fov_deg ? r.fov_deg.toFixed(0) + "°" : ""} · ${r.depth_m ? r.depth_m.median.toFixed(2) + " m" : ""}` : r.status === "running" ? r.stage : r.status;
    el.appendChild(vpRow({ color: r.status === "ready" ? "#4ade80" : r.status === "error" ? "#f87171" : "#facc15", name: (r.tag || r.id) + (r.source ? ` · ${r.source}` : ""), sub, onclick: () => { if (r.status === "ready") loadScene(r.id); } }));
  }
  $("run-status").textContent = state.userRuns.length ? `${state.userRuns.filter((r) => r.status === "ready").length} ready of ${state.userRuns.length}` : "";
}
async function refreshManifest() { M = await api("api/lab/scenes"); sceneOptions(); if (scene) $("scene-select").value = scene.id; }

// ---------------------------------------------------------------- tooltips
// A CSS ::after tooltip is laid out inside its trigger, so any scrolling ancestor —
// the stage, a side panel, the log grid — clips it. One fixed-position node appended
// to <body> escapes every container, and flipping/clamping keeps it on screen.
const tip = Object.assign(document.createElement("div"), { className: "tip" });
tip.hidden = true; document.body.appendChild(tip);
let tipFor = null;
function showTip(el) {
  const text = el.getAttribute("data-tip"); if (!text) return;
  tipFor = el; tip.textContent = text; tip.hidden = false;
  const r = el.getBoundingClientRect(), t = tip.getBoundingClientRect(), gap = 8;
  const below = r.top < t.height + gap * 2;                       // not enough room above
  let top = below ? r.bottom + gap : r.top - t.height - gap;
  let left = r.left + r.width / 2 - t.width / 2;
  left = Math.max(8, Math.min(left, innerWidth - t.width - 8));   // never past the viewport
  tip.style.top = `${Math.round(top)}px`; tip.style.left = `${Math.round(left)}px`;
}
function hideTip() { tip.hidden = true; tipFor = null; }
document.addEventListener("pointerover", (e) => {
  const el = e.target.closest("[data-tip]");
  if (el === tipFor) return;
  el ? showTip(el) : hideTip();
});
document.addEventListener("pointerdown", hideTip);
addEventListener("scroll", () => tipFor && hideTip(), true);
addEventListener("blur", hideTip);

// Footnotes jump both ways. The essay scrolls inside .page rather than the document, so the
// container is driven directly and the target flashed, otherwise the jump is invisible.
document.getElementById("method").addEventListener("click", (e) => {
  const a = e.target.closest('a[href^="#fn"]');
  if (!a) return;
  e.preventDefault();
  const t = document.getElementById(decodeURIComponent(a.getAttribute("href").slice(1)));
  if (!t) return;
  t.scrollIntoView({ behavior: "smooth", block: "center" });
  t.classList.remove("fn-flash"); void t.offsetWidth; t.classList.add("fn-flash");
});

// The four floating HUD corners are toggled from the Overlays panel alongside the 3D overlays.
for (const cb of document.querySelectorAll("[data-hud]")) {
  cb.addEventListener("change", () => {
    const el = document.querySelector(".float-" + cb.dataset.hud);
    if (el) el.hidden = !cb.checked;
  });
}

// Essay figures open in the viewer; the reading column caps their width.
function wireFigures() {
  for (const fig of document.querySelectorAll("#method .mfig")) {
    const img = fig.querySelector("img"); if (!img) continue;
    const open = () => showLightbox({ src: fig.dataset.full || img.src, title: fig.dataset.title || "", caption: fig.dataset.cap || "" });
    img.addEventListener("click", open);
    img.setAttribute("role", "button"); img.setAttribute("tabindex", "0");
    img.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } });
  }
}

// ---------------------------------------------------------------- lightbox
let lightboxReturn = null;
function showLightbox({ src, title = "", caption = "", meta = "" }) {
  lightboxReturn = document.activeElement;
  const img = $("lightbox-img");
  img.src = src; img.alt = caption || title;
  $("lightbox-title").textContent = title;
  $("lightbox-cap").textContent = caption; $("lightbox-cap").hidden = !caption;
  $("lightbox-open").href = src;
  const m = $("lightbox-meta"); m.textContent = meta; m.hidden = !meta;
  $("lightbox").hidden = false;
  $("lightbox-close").focus();          // the close control takes focus, so Enter and Esc both dismiss
}
function closeLightbox() {
  const box = $("lightbox");
  if (box.hidden) return;
  box.hidden = true; $("lightbox-img").src = "";   // drop the decoded bitmap
  if (lightboxReturn && lightboxReturn.focus) lightboxReturn.focus();
  lightboxReturn = null;
}
function openLightbox(entry) {
  const src = "anamorph/" + (entry.kind === "recording" ? entry.thumb : entry.file);
  showLightbox({ src, title: entry.file.split("/").pop(), caption: entry.note || "", meta: JSON.stringify(entry, null, 1) });
  if (entry.meta) fetch("anamorph/" + entry.meta).then((r) => r.json())
    .then((m) => { if (!$("lightbox").hidden) $("lightbox-meta").textContent = JSON.stringify(m, null, 1); }).catch(() => {});
}
// Anywhere outside the picture dismisses, as does the labelled button and Esc.
$("lightbox").addEventListener("click", (e) => { if (e.target.id === "lightbox" || e.target.classList.contains("lightbox-body")) closeLightbox(); });
$("lightbox").addEventListener("keydown", (e) => { if (e.key === "Tab") e.preventDefault(); });  // trap focus in the dialog
$("lightbox-close").onclick = closeLightbox;

// ---------------------------------------------------------------- log view
async function renderLog() {
  const data = await api("api/lab/captures"); const all = data.captures.slice().reverse();
  const sel = $("log-filter-scene"); const scenesSeen = [...new Set(all.map((c) => c.scene).filter(Boolean))];
  const cur = sel.value; sel.innerHTML = `<option value="">all scenes</option>` + scenesSeen.map((s) => `<option value="${s}">${s}</option>`).join(""); sel.value = cur;
  const q = $("log-search").value.toLowerCase(), fs = sel.value, fk = $("log-filter-kind").value;
  const items = all.filter((c) => (!fs || c.scene === fs) && (!fk || c.kind === fk) && (!q || `${c.tag} ${c.note} ${c.file}`.toLowerCase().includes(q)));
  const grid = $("log-grid"); grid.innerHTML = "";
  if (!items.length) grid.innerHTML = `<div class="empty">Nothing here yet. Press <span class="kbd">S</span> in the Lab.</div>`;
  for (const c of items) {
    const card = document.createElement("div"); card.className = "card log-card";
    const pose = c.pose_mm ? `Δx ${Math.round(c.pose_mm.dx)} · Δy ${Math.round(c.pose_mm.dy)} · Δz ${Math.round(c.pose_mm.dz)}` : "";
    const kindBadge = c.kind === "recording" ? `recording · ${c.frames} fr` : c.kind === "user_run" ? `reconstruction · ${c.mode}` : c.mode;
    card.innerHTML = `${c.kind === "recording" ? `<video src="anamorph/${c.file}" poster="anamorph/${c.thumb || ""}" controls muted loop></video>` : `<img alt="" />`}
      <div class="body"><div class="row-between"><span class="badge badge-outline">${c.scene || ""}</span><span class="badge badge-muted">${kindBadge}</span></div>
      <div>${pose}${c.fov_deg ? ` · fov ${Math.round(c.fov_deg)}°` : ""}</div><div class="text-muted">${c.tag || ""} · ${c.time}</div><div class="name">${c.file}</div>
      ${c.kind === "user_run" ? `<button class="btn btn-outline btn-xs open-run">Open</button>` : ""}
      <input class="input input-sm note" placeholder="note…" value="${(c.note || "").replace(/"/g, "&quot;")}" /></div>`;
    const img = card.querySelector("img"); if (img) { useThumb(img, c); img.onclick = () => openLightbox(c); }
    const ob = card.querySelector(".open-run"); if (ob) ob.onclick = () => { showView("lab"); loadScene(c.folder); };
    card.querySelector(".note").addEventListener("change", (e) => api("api/lab/note", { id: c.id, note: e.target.value }));
    grid.appendChild(card);
  }
  $("log-export-json").href = URL.createObjectURL(new Blob([JSON.stringify(all, null, 1)], { type: "application/json" }));
  const cols = ["id", "kind", "time", "scene", "mode", "tag", "note", "fov_deg", "file"];
  const csv = [cols.concat(["dx", "dy", "dz"]).join(",")].concat(all.map((c) => cols.map((k) => JSON.stringify(c[k] ?? "")).concat(c.pose_mm ? [c.pose_mm.dx, c.pose_mm.dy, c.pose_mm.dz] : ["", "", ""]).join(","))).join("\n");
  $("log-export-csv").href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
}
$("log-filter-scene").addEventListener("change", renderLog); $("log-filter-kind").addEventListener("change", renderLog); $("log-search").addEventListener("input", renderLog);
$("log-snapshot").onclick = async () => { const r = await api("api/lab/log_snapshot", {}); toast("Log snapshot saved", r.file, "success"); };

// ---------------------------------------------------------------- reports view
function svgChart(w, h, draw) { const ns = "http://www.w3.org/2000/svg"; const s = document.createElementNS(ns, "svg"); s.setAttribute("viewBox", `0 0 ${w} ${h}`); s.setAttribute("xmlns", ns); const add = (tag, attrs, text) => { const e = document.createElementNS(ns, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (text != null) e.textContent = text; s.appendChild(e); return e; }; draw(add); return s; }
let reportData = null;
async function renderReports() {
  const { runs } = await api("api/lab/runs"); const caps = (await api("api/lab/captures")).captures; const { versions } = await api("api/lab/report_versions");
  const p1 = M.phase1 && M.phase1.stats;
  reportData = { runs, captures: caps, scenes: M.scenes.map((s) => s.id), user_runs: state.userRuns, phase1: p1 };
  $("report-versions").innerHTML = versions.length ? versions.map((v) => `<a class="badge badge-outline" href="${v.html}" target="_blank">${v.id}${v.note ? " · " + v.note : ""}</a>`).join("") : `<span class="text-xs text-muted">no saved versions yet</span>`;
  const R = $("reports"); R.innerHTML = "";
  const fg = "#e5e5e5", mu = "#8a8a8a";
  const section = (num, title, lead) => { const s = document.createElement("section"); s.className = "rsec"; s.innerHTML = `<div class="rsec-head"><span class="rsec-num">${num}</span><div><h2></h2><p class="text-muted text-sm"></p></div></div><div class="rgrid"></div>`; s.querySelector("h2").textContent = title; s.querySelector("p").textContent = lead; R.appendChild(s); return s.querySelector(".rgrid"); };
  const card = (grid, title, cls = "") => { const c = document.createElement("div"); c.className = "card rcard " + cls; c.innerHTML = `<h3></h3>`; c.querySelector("h3").textContent = title; grid.appendChild(c); return c; };
  const fig = (grid, title, src, cls = "", caption = "") => {
    const c = card(grid, title, cls);
    const im = document.createElement("img");
    im.src = src; im.alt = title; im.loading = "lazy"; im.decoding = "async"; im.className = "zoomable";
    im.setAttribute("role", "button"); im.tabIndex = 0;
    const open = () => showLightbox({ src, title, caption });
    im.onclick = open;
    im.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } };
    c.appendChild(im);
    if (caption) { const p = document.createElement("p"); p.className = "text-xs text-muted"; p.style.marginTop = "6px"; p.textContent = caption; c.appendChild(p); }
    return c;
  };
  const kvTable = (rows) => `<table>${rows.map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join("")}</table>`;
  const sorted = runs.filter((r) => r.run).sort((a, b) => a.run.f35_mm - b.run.f35_mm);
  const f30 = sorted.find((r) => r.run.f35_mm === 30) || sorted[0];

  // ---- 1 ground truth
  let g = section("1", "Ground truth and reproduction", "Establishes the reference answer. Boxer derived the viewing position from the panel by geometry; a Python port of his two MATLAB scripts reproduces every published figure to within 0.2 mm, which is what licenses the rest of the study to treat his coordinate as ground truth. Read the offsets between the four published points as the width of expert disagreement, not as error.");
  const b = M.boxer;
  card(g, "Published viewing points (Δx, Δy, Δz mm)").innerHTML += `<table><tr><th>source</th><th>Δx</th><th>Δy</th><th>Δz</th></tr>${M.published_points.map((p) => `<tr><td>${p.name}</td><td>${p.dx}</td><td>${p.dy}</td><td>${p.dz}</td></tr>`).join("")}</table><p class="text-xs text-muted" style="margin-top:6px">1σ = 20 mm (Δx), 4 mm (Δz). Expert disagreement Boxer vs National Gallery: 13 mm, 138 mm.</p>`;
  card(g, "Boxer's construction (reproduced)").innerHTML += kvTable([["D (jaw through S)", `${b.D.toFixed(3)} mm`], ["d (aspect = 1)", `${b.d.toFixed(3)} mm`], ["S", `(${b.S_mm[0].toFixed(1)}, ${b.S_mm[1].toFixed(0)})`], ["O", `(${b.O_mm[0].toFixed(1)}, ${b.O_mm[1].toFixed(0)}, ${b.O_mm[2].toFixed(1)})`], ["Exact-perspective R, α", `${b.R_perspective} mm, ${b.alpha_perspective_deg}°`], ["Restored skull box", `${b.restored_box.size_mm} mm at (${b.restored_box.centre.join(", ")})`], ["Identity", "D = R / sin α, d = R cot α"]]);
  fig(g, "Restored skull: port beside Boxer's", "anamorph/boxer_repro/comparison_restored_skull.jpg", "", "Inverse trapezoid, exact perspective, and Boxer's OptimalSkull.jpg.");

  // ---- 2 flat model basin
  g = section("2", "Perceptual basin of the flat model (Phase 1)", "Establishes how much positional error looking can absorb. The flat painting is projected from 13 700 eye positions and each skull crop scored four ways. The ratio column is the decisive one: it gives the area scoring within 5 % of the best, in multiples of Boxer's 2σ ellipse. Large ratios mean perception cannot localise the viewer even where geometry can.");
  if (p1) { const rows = ["clip_skull", "clip_sim", "resemblance", "symmetry"].map((k) => [k, `${p1[k].peak.dx}, ${p1[k].peak.dz}`, p1[k].peak.value.toFixed(3), p1[k].above_95pct.area_mm2.toLocaleString(), Math.round(p1[k].above_95pct.area_mm2 / p1.ellipse_area_mm2)]);
    card(g, "Basins against Boxer's 2σ ellipse (1005 mm²)").innerHTML += `<table><tr><th>metric</th><th>peak Δx, Δz</th><th>value</th><th>area ≥95 % mm²</th><th>× ellipse</th></tr>${rows.map((r) => `<tr>${r.map((v) => `<td>${v}</td>`).join("")}</tr>`).join("")}</table>`;
    card(g, "Scores at the published points (flat model)").innerHTML += `<table><tr><th>point</th><th>resemblance</th><th>P(skull)</th><th>aspect</th><th>jaw °</th></tr>${Object.entries(p1.scores_at_published).map(([n, v]) => `<tr><td>${n}</td><td>${v.resemblance.toFixed(3)}</td><td>${v.clip_skull.toFixed(3)}</td><td>${v.aspect.toFixed(2)}</td><td>${v.jaw_deg.toFixed(1)}</td></tr>`).join("")}</table>`; }
  if (p1) { const rP = Math.round(p1.clip_skull.above_95pct.area_mm2 / p1.ellipse_area_mm2), rR = Math.round(p1.resemblance.above_95pct.area_mm2 / p1.ellipse_area_mm2);
    card(g, "What the ratios mean").innerHTML += kvTable([
      ["Boxer 2σ ellipse", `${Math.round(p1.ellipse_area_mm2).toLocaleString()} mm²`],
      ["Within 5 % on P(skull)", `${rP}× the ellipse`],
      ["Within 5 % on resemblance", `${rR}× the ellipse`],
      ["Grid samples", p1.grid && p1.grid.n ? p1.grid.n.toLocaleString() : "13 700"],
    ]) + `<p class="text-xs text-muted" style="margin-top:6px">Geometry localises the eye to a few millimetres; the looser of the two perceptual scores accepts a region ${rP} times larger. The two answers are different in kind, so the study reports them separately rather than averaging.</p>`; }
  fig(g, "Basin surfaces", M.phase1.figure, "span3", "P(skull), resemblance, symmetry and Boxer's own geometric conditions, with the four published points and the 2σ ellipse.");
  fig(g, "Skull crops along Δz (top) and Δx (bottom)", M.phase1.contact_sheet, "span3");

  // ---- 3 SHARP reference runs
  g = section("3", "Reference reconstructions (Phases 2–3)", "Tests whether the model recovers the same coordinate. SHARP reconstructs the photograph at thirteen assumed focal lengths; each reconstruction is then rendered across the Phase 1 grid and scored with a crop that follows the skull Gaussians rather than the panel position, since the model does not place the skull on the wall. \u0022Offset from O\u0022 is the residual against ground truth; \u0022empty at O\u0022 is the fraction of the tracked crop containing no geometry at Boxer's point.");
  const t = card(g, "Assumed lens → reconstruction → station point", "span3");
  let html = `<div class="scroll"><table><tr><th>lens mm</th><th>f_px</th><th>depth median m</th><th>relief mm</th><th>mm/unit</th><th>photo cam Δz</th><th>peak Δx</th><th>peak Δz</th><th>resemblance</th><th>offset from O mm</th><th>Δx/13</th><th>Δz/138</th><th>in 2σ</th><th>resemblance at O</th><th>empty at O</th></tr>`;
  for (const r of sorted) { const j = r.run, gs = r.grid_stats; const pv = j.panel_variants ? j.panel_variants.skull_frontoparallel : null; const rs = gs && gs.resemblance; const pk = rs ? rs.peak : null, dd = rs ? rs.displacement_from_boxer_mm : null, du = rs ? rs.displacement_in_expert_disagreement_units : null; const atO = gs && gs.scores_at_published["Boxer inverseTrapezoid.m"];
    html += `<tr><td>${j.f35_mm}</td><td>${j.f_px.toFixed(0)}</td><td>${j.depth_m.median.toFixed(2)}</td><td>${j.panel.relief_p95_minus_p05_mm.toFixed(0)}</td><td>${pv ? pv.scale_mm_per_unit.toFixed(0) : ""}</td><td>${pv ? pv.camera0_mm[2].toFixed(0) : ""}</td><td>${pk ? pk.dx : "—"}</td><td>${pk ? pk.dz : "—"}</td><td>${pk ? pk.value.toFixed(2) : ""}</td><td>${dd ? dd.euclid.toFixed(0) : "—"}</td><td>${du ? du.dx.toFixed(1) : ""}</td><td>${du ? du.dz.toFixed(2) : ""}</td><td>${rs ? (rs.inside_boxer_2sigma_ellipse ? "yes" : "no") : ""}</td><td>${atO ? atO.resemblance.toFixed(2) : ""}</td><td>${gs ? (gs.hole_fraction_at_published["Boxer inverseTrapezoid.m"] * 100).toFixed(0) + "%" : ""}</td></tr>`; }
  t.innerHTML += html + `</table></div><p class='text-xs text-muted' style='margin-top:6px'>Offset = distance of SHARP's best resemblance position from Boxer's O (776.9, 257.9). The flat model scores 0.997 at Boxer's point.</p>`;
  const c3 = card(g, "SHARP station point per lens on Boxer's plane", "span2");
  c3.appendChild(svgChart(560, 340, (add) => { const X = (dx) => 40 + (dx - 200) * 500 / 1400, Y = (dz) => 300 - dz * 270 / 650;
    add("rect", { x: 40, y: 30, width: 500, height: 270, fill: "none", stroke: mu });
    for (const dx of [400, 800, 1200]) add("text", { x: X(dx), y: 318, fill: mu, "font-size": 11, "text-anchor": "middle" }, "Δx " + dx);
    for (const dz of [100, 300, 500]) add("text", { x: 34, y: Y(dz) + 4, fill: mu, "font-size": 11, "text-anchor": "end" }, dz);
    for (const p of M.published_points) add("circle", { cx: X(p.dx), cy: Y(p.dz), r: 5, fill: COLORS[p.name], stroke: "#000" });
    add("ellipse", { cx: X(776.9), cy: Y(257.9), rx: 40 * 500 / 1400, ry: 8 * 270 / 650, fill: "none", stroke: "#22d3ee" });
    for (const r of sorted) { const gs = r.grid_stats; if (!gs || !gs.resemblance) continue; const pk = gs.resemblance.peak; add("circle", { cx: X(pk.dx), cy: Y(pk.dz), r: 6, fill: "#f87171", stroke: "#000" }); add("text", { x: X(pk.dx) + 8, y: Y(pk.dz) + 4, fill: fg, "font-size": 11 }, r.run.f35_mm + ""); }
    add("text", { x: 48, y: 48, fill: fg, "font-size": 12 }, "red: SHARP resemblance peak per lens (mm) · cyan: Boxer 2σ · dots: published"); }));
  if (f30 && f30.orbit_collapse_by_angle) { const cc = card(g, "Collapse by angle from the photo axis (30 mm orbit)"); cc.innerHTML += `<table><tr><th>distance</th>${Object.keys(f30.orbit_collapse_by_angle[Object.keys(f30.orbit_collapse_by_angle)[0]]).map((a) => `<th>${a}°</th>`).join("")}</tr>${Object.entries(f30.orbit_collapse_by_angle).map(([d, bins]) => `<tr><td>${d} mm</td>${Object.values(bins).map((v) => `<td>${Math.round(v * 100)}%</td>`).join("")}</tr>`).join("")}</table><p class="text-xs text-muted" style="margin-top:6px">Share of poses collapsed (&gt;15 % empty in the tracked crop or Laplacian variance &lt;30 % of frontal).</p>`; }
  const f30s = M.scenes.find((s) => s.id === "sharp_wiki_f30");
  if (f30s && f30s.figures["sharp_basin.png"]) fig(g, "SHARP 30 mm: score surfaces on the grid", f30s.figures["sharp_basin.png"], "span3");
  if (f30s && f30s.figures["grid_contact_sheet.jpg"]) fig(g, "SHARP 30 mm: tracked skull crops along Δz and Δx", f30s.figures["grid_contact_sheet.jpg"], "span3", "Same lines as the Phase 1 sheet. From every published point the skull is a sliver.");
  const det = document.createElement("details"); det.className = "rdetails span3"; det.innerHTML = `<summary>Score surfaces for the other twelve lenses</summary><div class="rgrid"></div>`; g.appendChild(det);
  for (const s of M.scenes) if (s.id !== "sharp_wiki_f30" && s.figures && s.figures["sharp_basin.png"]) fig(det.querySelector(".rgrid"), `${s.f35_mm} mm`, s.figures["sharp_basin.png"]);

  // ---- 4 lens sweep
  g = section("4", "The assumed lens (Phase 4)", "Isolates the one free parameter. With no EXIF the model assumes a 30 mm lens, so every metric depth it reports descends from that default. Sweeping the default from 5 to 200 mm shows depth is exactly linear in focal length while lateral scale is invariant — the metric output is a depth guess only. No setting moves the station point inside Boxer's ellipse.");
  const c2 = card(g, "Metric depth against assumed focal length");
  const pts = sorted.map((r) => ({ f: r.run.f35_mm, med: r.run.depth_m.median, p05: r.run.depth_m.p05, p95: r.run.depth_m.p95, relief: r.run.panel.relief_p95_minus_p05_mm / 1000 }));
  c2.appendChild(svgChart(560, 300, (add) => { const X = (f) => 60 + (Math.log10(f) - 0.6) * 460 / 1.75, Y = (v) => 260 - (Math.log10(v) + 0.6) * 220 / 1.9;
    add("line", { x1: 60, y1: 260, x2: 540, y2: 260, stroke: mu }); add("line", { x1: 60, y1: 20, x2: 60, y2: 260, stroke: mu });
    for (const f of [5, 10, 24, 50, 100, 200]) add("text", { x: X(f), y: 278, fill: mu, "font-size": 11, "text-anchor": "middle" }, f + " mm");
    for (const v of [0.3, 1, 3, 10]) { add("text", { x: 52, y: Y(v) + 4, fill: mu, "font-size": 11, "text-anchor": "end" }, v + " m"); add("line", { x1: 60, y1: Y(v), x2: 540, y2: Y(v), stroke: mu, "stroke-opacity": .25 }); }
    add("polyline", { points: pts.map((p) => `${X(p.f)},${Y(p.med)}`).join(" "), fill: "none", stroke: "#22d3ee", "stroke-width": 2 });
    add("polyline", { points: pts.map((p) => `${X(p.f)},${Y(p.p05)}`).join(" "), fill: "none", stroke: "#22d3ee", "stroke-dasharray": "3 3" });
    add("polyline", { points: pts.map((p) => `${X(p.f)},${Y(p.p95)}`).join(" "), fill: "none", stroke: "#22d3ee", "stroke-dasharray": "3 3" });
    add("polyline", { points: pts.map((p) => `${X(p.f)},${Y(Math.max(0.26, p.relief))}`).join(" "), fill: "none", stroke: "#f87171", "stroke-width": 2 });
    add("text", { x: 70, y: 30, fill: "#22d3ee", "font-size": 12 }, "median depth (dashed: p05 / p95)"); add("text", { x: 70, y: 46, fill: "#f87171", "font-size": 12 }, "relief p95−p05, true panel units"); }));
  fig(g, "Sweep summary", "anamorph/figures/focal_sweep.png", "span2", "Depth, bridge parameters and the station point per lens.");
  fig(g, "Depth maps per lens", "anamorph/figures/depth_strip.png", "span3", "Bright = near. The picture is the same; only the depth scale changes.");

  // ---- 5 orbits
  g = section("5", "Orbits around SHARP's skull (30 mm)", "Checks whether any viewpoint at all resolves the reconstruction, not just those on Boxer's plane. 532 coarse poses plus a 440-pose refinement in the azimuth 50°–90° sector, scored on the same tracked crop. Collapse fraction counts poses where the crop is more than 15 % empty or its Laplacian variance falls below 30 % of the frontal view.");
  if (f30s) { for (const k of ["orbit_contact_sheet_d700.jpg", "orbit_contact_sheet_d1400.jpg", "orbit_contact_sheet_d2000.jpg", "orbit_contact_sheet_d2800.jpg"]) if (f30s.figures[k]) fig(g, `Orbit contact sheet, ${k.match(/d(\d+)/)[1]} mm from the skull`, f30s.figures[k], "span3"); }
  fig(g, "Top 12 orbit poses by resemblance", "anamorph/runs/sharp_wiki_f30/orbit_top12.jpg", "span3", "Red box: the tracked skull crop.");
  fig(g, "Fine orbit surface", "anamorph/runs/sharp_wiki_f30/fine_surface.png", "span2");
  fig(g, "Fine orbit, top 12", "anamorph/runs/sharp_wiki_f30/fine_top12.jpg", "span3");

  // ---- 6 idolmorphosis
  g = section("6", "Idolmorphosis (Phase 5)", "Runs the construction backwards as a control on the port. Model output is forward-transformed into the restored painting's 142 mm skull box using the same D = 1824.45 and d = 257.88, then composited into the panel. If the port is correct the streak lands exactly on Holbein's footprint and resolves only from the exact-perspective point — which is what the right-hand column shows.");
  fig(g, "Three sources: best pose, the torn render from O, the depth map", "anamorph/figures/phase5_pairs.jpg", "span3", "Left: the streak in the painting. Right: seen from Boxer's O, where it resolves back into its square. Print files at 4 px/mm in figures/.");

  // ---- 7 test reconstructions
  g = section("7", "Test reconstructions", "Removes the lens assumption. Each run feeds SHARP an image rendered inside the Lab, whose focal length is therefore known exactly rather than defaulted, and bridges the result from the render camera instead of an assumed plane. Column k is the scale ratio between the test bridge and the reference bridge.");
  if (state.userRuns.length) { const u = card(g, "Runs", "span3"); u.innerHTML += `<div class="scroll"><table><tr><th>id</th><th>status</th><th>source</th><th>from (Δx, Δy, Δz)</th><th>fov</th><th>f_px</th><th>depth median m</th><th>relief mm</th><th>mm/unit</th><th>k</th><th>tag</th></tr>` +
    state.userRuns.map((r) => `<tr><td>${r.id}</td><td>${r.status}</td><td>${r.source}</td><td>${r.source_pose_mm ? `${r.source_pose_mm.dx.toFixed(0)}, ${r.source_pose_mm.dy.toFixed(0)}, ${r.source_pose_mm.dz.toFixed(0)}` : ""}</td><td>${r.fov_deg ? r.fov_deg.toFixed(0) : ""}</td><td>${r.f_px ? r.f_px.toFixed(0) : ""}</td><td>${r.depth_m ? r.depth_m.median.toFixed(2) : ""}</td><td>${r.relief_mm ? r.relief_mm.toFixed(0) : ""}</td><td>${r.panel ? r.panel.scale_mm_per_unit.toFixed(0) : ""}</td><td>${r.bridge ? r.bridge.k_sharp_per_ref.toFixed(2) : ""}</td><td>${r.tag || ""}</td></tr>`).join("") + "</table></div>"; }
  else card(g, "Runs").innerHTML += `<p class="text-xs text-muted">None yet.</p>`;

  // ---- 8 captures
  g = section("8", "Captures and recordings", `Provenance for every frame reproduced in the essay. ${caps.length} entries, each a JPEG beside a JSON sidecar recording pose in both coordinate frames, field of view, view mode, active overlays and bridge parameters. The plan below shows where each was taken relative to the panel and the published points.`);
  const c4 = card(g, "Where captures were taken", "span2");
  c4.appendChild(svgChart(760, 430, (add) => {
    // plan of the room: Δx along the wall, Δz out from it. Axes are drawn because the
    // question this answers is "from where", and that is unreadable without a scale.
    const X0 = 62, Y0 = 372, W = 660, H = 320;
    const xmin = -400, xmax = 3200, zmin = 0, zmax = 2600;
    const X = (x) => X0 + (x - xmin) * W / (xmax - xmin);
    const Y = (z) => Y0 - (z - zmin) * H / (zmax - zmin);
    const txt = (x, y, t, o = {}) => add("text", { x, y, fill: o.fill || mu, "font-size": o.size || 10,
      "text-anchor": o.anchor || "start", "font-family": "var(--font-mono)" }, t);

    for (let z = 0; z <= zmax; z += 500) {                              // grid + Δz ticks
      add("line", { x1: X0, y1: Y(z), x2: X0 + W, y2: Y(z), stroke: mu, "stroke-opacity": z ? .12 : .35 });
      txt(X0 - 8, Y(z) + 3, String(z), { anchor: "end" });
    }
    for (let x = 0; x <= 3000; x += 500) {                              // Δx ticks
      add("line", { x1: X(x), y1: Y0, x2: X(x), y2: Y0 + 4, stroke: mu, "stroke-opacity": .4 });
      txt(X(x), Y0 + 16, String(x - LX), { anchor: "middle" });
    }
    txt(X0 + W / 2, Y0 + 32, "Δx  mm right of the panel's right edge", { anchor: "middle", size: 10.5 });
    add("text", { x: 16, y: Y0 - H / 2, fill: mu, "font-size": 10.5, "text-anchor": "middle",
      "font-family": "var(--font-mono)", transform: `rotate(-90 16 ${Y0 - H / 2})` }, "Δz  mm from the wall");

    add("line", { x1: X(0), y1: Y(0), x2: X(LX), y2: Y(0), stroke: fg, "stroke-width": 4, "stroke-linecap": "butt" });
    txt(X(LX / 2), Y(0) - 9, "panel, 2095 mm", { anchor: "middle", fill: fg });

    const seen = {};
    for (const c of caps) {                                            // captures, jittered so stacks stay countable
      if (!c.pose_mm) continue;
      const k = `${Math.round(c.pose_mm.dx / 25)}|${Math.round(c.pose_mm.dz / 25)}`;
      const n = (seen[k] = (seen[k] || 0) + 1) - 1;
      const col = c.kind === "recording" ? "#a78bfa" : c.kind === "user_run" ? "#4ade80" : "#f87171";
      add("circle", { cx: X(c.pose_mm.dx + LX) + (n % 3) * 3.5, cy: Y(c.pose_mm.dz) - Math.floor(n / 3) * 3.5,
        r: 4, fill: col, "fill-opacity": .55, stroke: col, "stroke-width": .8 });
    }
    for (const p of M.published_points) {                              // ground truth on top
      add("circle", { cx: X(p.dx + LX), cy: Y(p.dz), r: 5.5, fill: "none", stroke: COLORS[p.name], "stroke-width": 2 });
      add("circle", { cx: X(p.dx + LX), cy: Y(p.dz), r: 1.6, fill: COLORS[p.name] });
    }
    const legend = [["#f87171", "capture"], ["#a78bfa", "recording"], ["#4ade80", "reconstruction"],
                    [null, "published station point"]];
    legend.forEach(([col, name], i) => {
      const ly = 34 + i * 17;
      if (col) add("circle", { cx: X0 + 12, cy: ly - 3.5, r: 4, fill: col, "fill-opacity": .55, stroke: col, "stroke-width": .8 });
      else { add("circle", { cx: X0 + 12, cy: ly - 3.5, r: 5.5, fill: "none", stroke: fg, "stroke-width": 2 });
             add("circle", { cx: X0 + 12, cy: ly - 3.5, r: 1.6, fill: fg }); }
      txt(X0 + 26, ly, name, { fill: fg, size: 11 });
    });
  }));
  c4.innerHTML += `<p class="text-xs text-muted" style="margin-top:6px">Eye positions in plan. Overlapping captures are offset slightly so a stack of frames taken from one point stays countable.</p>`;
  const byKind = {}; for (const c of caps) byKind[c.kind] = (byKind[c.kind] || 0) + 1;
  const byScene = {}; for (const c of caps) if (c.scene) byScene[c.scene] = (byScene[c.scene] || 0) + 1;
  card(g, "Counts").innerHTML += kvTable([...Object.entries(byKind), ...Object.entries(byScene).slice(0, 12)]);
  const recent = card(g, "Latest captures"); const strip = caps.filter((c) => c.kind === "capture").slice(-6).reverse();
  recent.innerHTML += `<div class="cap-recent">${strip.map(() => `<img alt="" class="zoomable" />`).join("")}</div>`;
  recent.querySelectorAll(".cap-recent img").forEach((im, i) => { useThumb(im, strip[i]); im.onclick = () => openLightbox(strip[i]); });
}
$("report-save").onclick = async () => { if (!reportData) await renderReports(); const r = await api("api/lab/report_version", { html: $("reports").innerHTML, data: reportData, note: $("report-note").value.trim() }); toast("Report version saved", r.id, "success"); $("report-note").value = ""; renderReports(); };

// ---------------------------------------------------------------- views + keys + boot
let reportsDirty = true, logDirty = true, methodRendered = false;
const VIEW_SLUG = { lab: "lab", log: "log", reports: "report", method: "method" };
const SLUG_VIEW = Object.fromEntries(Object.entries(VIEW_SLUG).map(([k, v]) => [v, k]));
function writeUrl(v, push) {
  const u = new URL(location.href);
  u.searchParams.set("view", VIEW_SLUG[v] || v);
  if (v !== "lab") u.searchParams.delete("scene");
  else if (scene) u.searchParams.set("scene", scene.id);
  u.hash = "";
  history[push ? "pushState" : "replaceState"]({ view: v }, "", u);
}
function showView(v, opts = {}) {
  if (state.view === v) { if (!opts.silent) writeUrl(v, false); return; }
  state.view = v; for (const id of ["lab", "log", "reports", "method"]) $("view-" + id).hidden = id !== v;
  for (const a of document.querySelectorAll("[data-view]")) a.setAttribute("aria-current", a.dataset.view === v ? "page" : "false");
  viewer.paused = v !== "lab";                       // stops the frame loop outright, not just the drawing
  $("lab-actions").hidden = v !== "lab";             // capture / reconstruct / clean view belong to the Lab only
  // Page builds are deferred a frame so the tab switch itself paints immediately.
  if (v === "log" && logDirty) requestAnimationFrame(() => renderLog().then(() => (logDirty = false)));
  if (v === "reports" && reportsDirty) requestAnimationFrame(() => renderReports().then(() => (reportsDirty = false)));
  if (v === "method" && !methodRendered) { renderMethod(); wireFigures(); methodRendered = true; }
  if (v === "lab") viewer.resize();                  // cheap now: no-ops unless the stage actually changed size
  if (!opts.silent) writeUrl(v, opts.push !== false);
}
addEventListener("popstate", () => {
  const slug = new URLSearchParams(location.search).get("view");
  showView(SLUG_VIEW[slug] || "lab", { silent: true });
});
document.querySelectorAll("[data-view]").forEach((a) => (a.onclick = (e) => { e.preventDefault(); showView(a.dataset.view); }));
const applyTheme = (t) => { document.documentElement.dataset.theme = t; try { localStorage.setItem("theme", t); } catch {} };
try { if (localStorage.getItem("theme")) applyTheme(localStorage.getItem("theme")); } catch {}
$("btn-theme").onclick = () => applyTheme(document.documentElement.dataset.theme === "light" ? "dark" : "light");
window.addEventListener("keydown", (e) => {
  if (["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)) { if (e.key === "Escape") closeLightbox(); return; }
  if (e.key === "Escape") { if (!$("lightbox").hidden) { closeLightbox(); return; } if (document.body.classList.contains("clean")) $("btn-clean").click(); return; }
  if (state.view !== "lab") return;
  if (e.code === "KeyS") capture(); else if (e.code === "KeyR") { stopTraj(); photoView(); } else if (e.code === "KeyH") $("btn-clean").click();
  else if (e.code === "KeyF") { const b = $("stage-body"); document.fullscreenElement ? document.exitFullscreen() : b.requestFullscreen(); }
  else if (e.code === "KeyC") setMode({ sharp: "mesh", mesh: "wire", wire: "flat", flat: "split", split: "sharp" }[state.mode]);
  else if (e.code === "BracketLeft") $("sidebar-toggle").click(); else if (e.code === "BracketRight") $("inspector-toggle").click();
  else if (e.code === "Space") { e.preventDefault(); if (state.traj) $("traj-play").click(); }
  else if (/^Digit[0-9]$/.test(e.code)) { const i = +e.code.slice(5); const rows = [...$("viewpoints").querySelectorAll(".vp")]; if (rows[i]) rows[i].click(); }
});

async function runDocSet(items, folder = "docs") {
  const out = [];
  for (const it of items) {
    if (it.scene && (!scene || scene.id !== it.scene)) { await loadScene(it.scene); await viewer.waitForSplats(); await new Promise((r) => setTimeout(r, 400)); }
    if (it.overlays) { for (const k in state.overlays) { const on = !!it.overlays[k]; state.overlays[k] = on; const cb = document.querySelector(`[data-ov=${k}]`); if (cb) cb.checked = on; } buildOverlays(); }
    if (it.compare) { state.compare = it.compare; viewer.compareMode = it.compare; $("compare-select").value = it.compare; }
    if (it.mode) setMode(it.mode);
    if (it.split !== undefined) { viewer.split = it.split; $("stage-body").style.setProperty("--split", it.split * 100 + "%"); }
    if (it.photo) photoView(); else if (it.pose) { state.targetMode = it.target || "centre"; syncSeg("target-tabs", "target", state.targetMode); setPoseMM(it.pose[0], it.pose[1], it.pose[2], { target: it.target || "centre", fov: it.fov || 50 }); }
    await new Promise((r) => setTimeout(r, 250));
    out.push(await capture(it.tag, it.note || "", folder));
  }
  return out;
}

// A published copy has no server behind it, so the Lab's Gaussian files and every
// write route are absent. Say so plainly rather than leaving the stage spinning.
const STATIC_BUILD = document.querySelector('meta[name="build"]')?.content === "static";
// A published copy can borrow a local server when one happens to be running on the same
// machine, which is the only way the Lab has reconstructions to draw. Everything else on
// the page keeps coming from the published files.
const LOCAL_ORIGIN = "http://localhost:8765";
let bridged = false;
async function findLocalServer() {
  if (!STATIC_BUILD) return false;
  try {
    const stop = new AbortController();
    const timer = setTimeout(() => stop.abort(), 1500);
    const r = await fetch(`${LOCAL_ORIGIN}/api/lab/scenes`, { signal: stop.signal, mode: "cors" });
    clearTimeout(timer);
    return r.ok;
  } catch { return false; }
}
// The local server returns absolute paths; from a published page those would resolve
// against the published host, so they are re-pointed at the machine that served them.
// The test is for a leading slash rather than a named prefix: the static build rewrites
// absolute asset prefixes to relative ones, and a literal here would be rewritten too.
const rebase = (v) => typeof v === "string" ? (v.startsWith("/") ? LOCAL_ORIGIN + v : v)
  : Array.isArray(v) ? v.map(rebase)
  : v && typeof v === "object" ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, rebase(x)]))
  : v;
if (STATIC_BUILD) {
  document.body.classList.add("static-build");
  for (const id of ["btn-capture", "btn-run-sharp-top", "btn-capture-2", "btn-capture-set", "btn-run-sharp", "traj-record"]) {
    const el = $(id); if (el) { el.disabled = true; el.dataset.tip = "Needs the local server"; }
  }
}

(async () => {
  bridged = await findLocalServer();
  M = bridged ? rebase(await (await fetch(`${LOCAL_ORIGIN}/api/lab/scenes`)).json()) : await api("api/lab/scenes");
  if (bridged) {
    document.body.classList.remove("static-build");
    for (const id of ["btn-capture", "btn-run-sharp-top", "btn-capture-2", "btn-capture-set", "btn-run-sharp", "traj-record"]) {
      const el = $(id); if (el) { el.disabled = false; delete el.dataset.tip; }
    }
  }
  let hudTick = 0;
  viewer = new SplatViewer($("canvas"), { onFps: (fps, n) => { if (n > 0 && !$("stage-loading").hidden) $("stage-loading").hidden = true; const t = performance.now(); if (t - hudTick > 100) { hudTick = t; $("fps").textContent = `${Math.round(fps)} fps · ${(n / 1e6).toFixed(2)}M`; updateHUD(); } }, onInteract: () => { stopTraj(); state.targetMode = "free"; syncSeg("target-tabs", "target", "free"); } });
  viewer.set("wobble", false);
  state.savedViewpoints = (await api("api/lab/viewpoints")).viewpoints || []; state.savedTrajs = (await api("api/lab/trajectories")).trajectories || []; state.userRuns = M.user_runs || [];
  sceneOptions(); renderUserRuns();
  $("engine-pill").dataset.state = "ready"; $("engine-text").textContent = `${M.scenes.length} scenes`;
  // read the requested view before loadScene, which rewrites the query string itself
  const wanted = SLUG_VIEW[new URLSearchParams(location.search).get("view")];
  await loadScene(new URLSearchParams(location.search).get("scene") || "sharp_wiki_f30");
  photoView(); setMode("sharp");
  if (wanted && wanted !== "lab") showView(wanted, { push: false }); else writeUrl("lab", false);
  state.captures = (await api("api/lab/captures")).captures; renderRecent();
  if (state.userRuns.some((r) => r.status === "queued" || r.status === "running")) pollUserRuns();
  window.lab = { state, viewer, setPoseMM, capture, loadScene, trajectories, applyTraj, selectTraj, currentPoseMM, setMode, setFov, runDocSet, recordTraj, photoView, runSharpFromHere, goToViewpoint, refreshManifest };
})();
