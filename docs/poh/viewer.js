// Gaussian-splat viewer for SHARP scenes (uses shaders/sort worker from splat-core.js).
// World frame follows SHARP / OpenCV: x right, y down, z forward; the photo's camera sits at the origin.

(function () {
  const vsub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  const vadd = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
  const vscale = (a, s) => [a[0] * s, a[1] * s, a[2] * s];
  const vlen = (a) => Math.hypot(a[0], a[1], a[2]);
  const vnorm = (a) => vscale(a, 1 / (vlen(a) || 1));
  const vcross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];

  function lookAt(pos, target) {
    const f = vnorm(vsub(target, pos));
    let r = vnorm(vcross([0, 1, 0], f));
    if (vlen(r) < 1e-6) r = [1, 0, 0];
    const d = vcross(f, r);
    return [r[0], r[1], r[2], 0, d[0], d[1], d[2], 0, f[0], f[1], f[2], 0, pos[0], pos[1], pos[2], 1];
  }
  function rotateVec(v, axis, rad) {
    const c = Math.cos(rad), s = Math.sin(rad);
    const dot = v[0] * axis[0] + v[1] * axis[1] + v[2] * axis[2];
    const cr = vcross(axis, v);
    return [
      v[0] * c + cr[0] * s + axis[0] * dot * (1 - c),
      v[1] * c + cr[1] * s + axis[1] * dot * (1 - c),
      v[2] * c + cr[2] * s + axis[2] * dot * (1 - c),
    ];
  }

  class SplatViewer {
    constructor(canvas, opts = {}) {
      this.canvas = canvas;
      this.onFps = opts.onFps || (() => {});
      this.onInteract = opts.onInteract || (() => {});
      this.onProgress = opts.onProgress || (() => {});
      const gl = (this.gl = canvas.getContext("webgl2", { antialias: false, preserveDrawingBuffer: true }));

      const compile = (type, src) => {
        const sh = gl.createShader(type);
        gl.shaderSource(sh, src);
        gl.compileShader(sh);
        if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) console.error(gl.getShaderInfoLog(sh));
        return sh;
      };
      const program = (this.program = gl.createProgram());
      gl.attachShader(program, compile(gl.VERTEX_SHADER, vertexShaderSource));
      gl.attachShader(program, compile(gl.FRAGMENT_SHADER, fragmentShaderSource));
      gl.linkProgram(program);
      gl.useProgram(program);
      gl.disable(gl.DEPTH_TEST);
      gl.enable(gl.BLEND);
      gl.blendFuncSeparate(gl.ONE_MINUS_DST_ALPHA, gl.ONE, gl.ONE_MINUS_DST_ALPHA, gl.ONE);
      gl.blendEquationSeparate(gl.FUNC_ADD, gl.FUNC_ADD);
      this.u = {
        projection: gl.getUniformLocation(program, "projection"),
        viewport: gl.getUniformLocation(program, "viewport"),
        focal: gl.getUniformLocation(program, "focal"),
        view: gl.getUniformLocation(program, "view"),
      };
      const vb = gl.createBuffer(); this._posBuf = vb;
      gl.bindBuffer(gl.ARRAY_BUFFER, vb);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-2, -2, 2, -2, 2, 2, -2, 2]), gl.STATIC_DRAW);
      const a_position = gl.getAttribLocation(program, "position");
      gl.enableVertexAttribArray(a_position);
      gl.vertexAttribPointer(a_position, 2, gl.FLOAT, false, 0, 0);
      this.texture = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, this.texture);
      gl.uniform1i(gl.getUniformLocation(program, "u_texture"), 0);
      this.indexBuffer = gl.createBuffer();
      const a_index = gl.getAttribLocation(program, "index");
      gl.enableVertexAttribArray(a_index);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.indexBuffer);
      gl.vertexAttribIPointer(a_index, 1, gl.INT, false, 0, 0);
      gl.vertexAttribDivisor(a_index, 1);

      this.worker = new Worker(URL.createObjectURL(new Blob(["(", createWorker.toString(), ")(self)"], { type: "application/javascript" })));
      this.vertexCount = 0;
      this.worker.onmessage = (e) => {
        if (e.data.buffer) {
          const buf = e.data.buffer;
          this.worker.postMessage({ buffer: buf, vertexCount: Math.floor(buf.byteLength / 32) });
        } else if (e.data.texdata) {
          const { texdata, texwidth, texheight } = e.data;
          gl.bindTexture(gl.TEXTURE_2D, this.texture);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
          gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA32UI, texwidth, texheight, 0, gl.RGBA_INTEGER, gl.UNSIGNED_INT, texdata);
          gl.activeTexture(gl.TEXTURE0);
          gl.bindTexture(gl.TEXTURE_2D, this.texture);
        } else if (e.data.depthIndex) {
          gl.bindBuffer(gl.ARRAY_BUFFER, this.indexBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, e.data.depthIndex, gl.DYNAMIC_DRAW);
          this.vertexCount = e.data.vertexCount;
          if (this._sortWaiter) { const w = this._sortWaiter; this._sortWaiter = null; w(); }
        }
      };

      // camera state
      this.scene = { fx: null, width: null, height: null };
      this.params = { wobble: true, amp: 0.15, speed: 0.5, focus: 3, zoom: 1 };
      this._paused = true;          // effective state: true = loop fully stopped (no rAF, no view posts, no draw)
      this._pausedByView = false;   // intent from the page router, kept separate from tab visibility
      this._raf = 0;                // pending requestAnimationFrame handle (0 = loop not scheduled)
      this.fRatioOverride = null;   // focal / canvas width, overrides the photo-fit FOV
      this.drawMode = "sharp";      // "sharp" | "flat" | "split"  (flat = textured panel quad = Boxer's flat-panel model)
      this.split = 0.5;             // split position (fraction of width) for "split"
      this.overlaysOn = true;
      this._initAux();
      this.pos = [0, 0, 0];
      this.target = [0, 0, 3];
      this.keys = new Set();
      this.loadToken = 0;
      this.t0 = performance.now();
      this.last = this.t0;
      this.avgFps = 0;

      this._bindInput();
      this.resize();
      new ResizeObserver(() => this.resize()).observe(canvas.parentElement || canvas);
      // A hidden tab gets no useful frames; releasing the loop there also releases the sort worker.
      document.addEventListener("visibilitychange", () => this._sync());
      this._sync();
    }

    // Pausing cancels the frame loop outright rather than letting it spin on an early return, so a
    // scene left on another page costs nothing until it is shown again. Router intent and tab
    // visibility are tracked separately: folding them into one flag latches the loop off for good.
    get paused() { return this._paused; }
    set paused(v) { this._pausedByView = !!v; this._sync(); }
    _sync() {
      const next = this._pausedByView || document.hidden;
      if (next === this._paused) return;
      this._paused = next;
      if (next) { if (this._raf) { cancelAnimationFrame(this._raf); this._raf = 0; } }
      else this._start();
    }
    _start() {
      if (this._raf || this._paused) return;
      this.last = performance.now();   // avoid a large dt on the first frame after a resume
      this._raf = requestAnimationFrame((t) => this._frame(t));
    }

    // ---- overlays (3D lines in the SHARP frame) and the flat textured panel
    _initAux() {
      const gl = this.gl;
      const mk = (vs, fs) => {
        const c = (t, src) => { const sh = gl.createShader(t); gl.shaderSource(sh, src); gl.compileShader(sh); if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) console.error(gl.getShaderInfoLog(sh)); return sh; };
        const p = gl.createProgram(); gl.attachShader(p, c(gl.VERTEX_SHADER, vs)); gl.attachShader(p, c(gl.FRAGMENT_SHADER, fs)); gl.linkProgram(p); return p;
      };
      this.lineProg = mk(`#version 300 es
        precision highp float; uniform mat4 projection, view; in vec3 pos; in vec4 col; out vec4 vcol;
        void main(){ vec4 c = view * vec4(pos,1.0); vec4 p = projection * c; gl_Position = p; vcol = col; }`,
        `#version 300 es
        precision highp float; in vec4 vcol; out vec4 o; void main(){ o = vcol; }`);
      this.texProg = mk(`#version 300 es
        precision highp float; uniform mat4 projection, view; in vec3 pos; in vec2 uv; out vec2 vuv;
        void main(){ gl_Position = projection * view * vec4(pos,1.0); vuv = uv; }`,
        `#version 300 es
        precision highp float; uniform sampler2D tex; uniform float alpha; in vec2 vuv; out vec4 o;
        void main(){ vec4 c = texture(tex, vuv); o = vec4(c.rgb, 1.0) * alpha; }`);
      this.lineBuf = gl.createBuffer(); this.lineCount = 0;
      this.quadBuf = gl.createBuffer(); this.quadTex = null; this.quadCount = 0;
      this.meshBuf = gl.createBuffer(); this.meshIdx = gl.createBuffer(); this.meshCount = 0;
      this.meshWireIdx = gl.createBuffer(); this.meshWireCount = 0;
      this.compareMode = "flat";   // what the right half of a split shows: flat | mesh | wire
    }
    /** Depth mesh from a (n+1)x(n+1) grid of depths (SHARP metres, image row-major, null = hole); textured with the panel image. */
    setDepthMesh(grid, f_px, W, H) {
      const gl = this.gl; const n = grid.length - 1;
      const verts = [], idx = [], wire = [];
      const id = (i, j) => j * (n + 1) + i;
      for (let j = 0; j <= n; j++) for (let i = 0; i <= n; i++) {
        const z = grid[j][i]; const ok = z != null;
        const zz = ok ? z : 1;
        verts.push(((i / n) * W - W / 2) / f_px * zz, ((j / n) * H - H / 2) / f_px * zz, zz, i / n, j / n);
      }
      const okv = (i, j) => grid[j][i] != null;
      for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) {
        if (okv(i, j) && okv(i + 1, j) && okv(i, j + 1) && okv(i + 1, j + 1)) {
          idx.push(id(i, j), id(i + 1, j), id(i, j + 1), id(i + 1, j), id(i + 1, j + 1), id(i, j + 1));
        }
        if (okv(i, j) && okv(i + 1, j)) wire.push(id(i, j), id(i + 1, j));
        if (okv(i, j) && okv(i, j + 1)) wire.push(id(i, j), id(i, j + 1));
      }
      gl.bindBuffer(gl.ARRAY_BUFFER, this.meshBuf); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(verts), gl.STATIC_DRAW);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.meshIdx); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint32Array(idx), gl.STATIC_DRAW);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.meshWireIdx); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint32Array(wire), gl.STATIC_DRAW);
      this.meshCount = idx.length; this.meshWireCount = wire.length;
    }
    /** lines: [{pts:[[x,y,z],...], color:[r,g,b,a], loop?:bool}] in SHARP metres. */
    setOverlayLines(lines) {
      const data = [];
      for (const l of lines) {
        const c = l.color || [1, 1, 1, 1];
        const n = l.pts.length;
        for (let i = 0; i < (l.loop ? n : n - 1); i++) {
          const a = l.pts[i], b = l.pts[(i + 1) % n];
          data.push(a[0], a[1], a[2], ...c, b[0], b[1], b[2], ...c);
        }
      }
      const gl = this.gl;
      gl.bindBuffer(gl.ARRAY_BUFFER, this.lineBuf);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(data), gl.DYNAMIC_DRAW);
      this.lineCount = data.length / 7;
    }
    /** Textured quad: corners in SHARP metres [lowerLeft, lowerRight, upperRight, upperLeft]; image is any <img>/URL. */
    setPanelQuad(corners, image) {
      const gl = this.gl;
      const [a, b, c, d] = corners;   // uv: image top-left is (0,0)
      const v = [...a, 0, 1, ...b, 1, 1, ...c, 1, 0, ...a, 0, 1, ...c, 1, 0, ...d, 0, 0];
      gl.bindBuffer(gl.ARRAY_BUFFER, this.quadBuf);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(v), gl.STATIC_DRAW);
      this.quadCount = 6;
      const apply = (img) => {
        this.quadTex = this.quadTex || gl.createTexture();
        gl.bindTexture(gl.TEXTURE_2D, this.quadTex);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.generateMipmap(gl.TEXTURE_2D);
        this.quadReady = true;
      };
      if (typeof image === "string") { const im = new Image(); im.crossOrigin = "anonymous"; im.onload = () => apply(im); im.src = image; }
      else apply(image);
    }
    _drawScene(view) {
      const gl = this.gl;
      const W = gl.canvas.width, H = gl.canvas.height;
      const drawSplats = () => {
        if (this.vertexCount <= 0) return;
        gl.useProgram(this.program);
        gl.enable(gl.BLEND); gl.blendFuncSeparate(gl.ONE_MINUS_DST_ALPHA, gl.ONE, gl.ONE_MINUS_DST_ALPHA, gl.ONE);
        gl.bindBuffer(gl.ARRAY_BUFFER, this.indexBuffer);
        const a_index = gl.getAttribLocation(this.program, "index"); gl.enableVertexAttribArray(a_index); gl.vertexAttribIPointer(a_index, 1, gl.INT, false, 0, 0); gl.vertexAttribDivisor(a_index, 1);
        gl.bindBuffer(gl.ARRAY_BUFFER, this._posBuf); const a_pos = gl.getAttribLocation(this.program, "position"); gl.enableVertexAttribArray(a_pos); gl.vertexAttribPointer(a_pos, 2, gl.FLOAT, false, 0, 0);
        gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, this.texture);
        gl.uniformMatrix4fv(this.u.view, false, view);
        gl.drawArraysInstanced(gl.TRIANGLE_FAN, 0, 4, this.vertexCount);
      };
      const drawFlat = () => {
        if (!this.quadReady) return;
        gl.useProgram(this.texProg);
        gl.disable(gl.BLEND);
        gl.uniformMatrix4fv(gl.getUniformLocation(this.texProg, "projection"), false, this.projection);
        gl.uniformMatrix4fv(gl.getUniformLocation(this.texProg, "view"), false, view);
        gl.uniform1f(gl.getUniformLocation(this.texProg, "alpha"), 1.0);
        gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, this.quadTex); gl.uniform1i(gl.getUniformLocation(this.texProg, "tex"), 1);
        gl.bindBuffer(gl.ARRAY_BUFFER, this.quadBuf);
        const ap = gl.getAttribLocation(this.texProg, "pos"), au = gl.getAttribLocation(this.texProg, "uv");
        gl.enableVertexAttribArray(ap); gl.vertexAttribPointer(ap, 3, gl.FLOAT, false, 20, 0); gl.vertexAttribDivisor(ap, 0);
        gl.enableVertexAttribArray(au); gl.vertexAttribPointer(au, 2, gl.FLOAT, false, 20, 12); gl.vertexAttribDivisor(au, 0);
        gl.drawArrays(gl.TRIANGLES, 0, this.quadCount);
        gl.disableVertexAttribArray(au);
      };
      const drawMesh = (wire) => {
        if (!this.quadReady || !this.meshCount) return;
        if (wire) {
          gl.useProgram(this.lineProg);
          gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
          gl.uniformMatrix4fv(gl.getUniformLocation(this.lineProg, "projection"), false, this.projection);
          gl.uniformMatrix4fv(gl.getUniformLocation(this.lineProg, "view"), false, view);
          gl.bindBuffer(gl.ARRAY_BUFFER, this.meshBuf);
          const ap = gl.getAttribLocation(this.lineProg, "pos"), ac = gl.getAttribLocation(this.lineProg, "col");
          gl.enableVertexAttribArray(ap); gl.vertexAttribPointer(ap, 3, gl.FLOAT, false, 20, 0); gl.vertexAttribDivisor(ap, 0);
          gl.disableVertexAttribArray(ac); gl.vertexAttrib4f(ac, 0.55, 0.9, 1.0, 0.75);
          gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.meshWireIdx);
          gl.drawElements(gl.LINES, this.meshWireCount, gl.UNSIGNED_INT, 0);
          return;
        }
        gl.useProgram(this.texProg);
        gl.disable(gl.BLEND); gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL);
        gl.uniformMatrix4fv(gl.getUniformLocation(this.texProg, "projection"), false, this.projection);
        gl.uniformMatrix4fv(gl.getUniformLocation(this.texProg, "view"), false, view);
        gl.uniform1f(gl.getUniformLocation(this.texProg, "alpha"), 1.0);
        gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, this.quadTex); gl.uniform1i(gl.getUniformLocation(this.texProg, "tex"), 1);
        gl.bindBuffer(gl.ARRAY_BUFFER, this.meshBuf);
        const ap = gl.getAttribLocation(this.texProg, "pos"), au = gl.getAttribLocation(this.texProg, "uv");
        gl.enableVertexAttribArray(ap); gl.vertexAttribPointer(ap, 3, gl.FLOAT, false, 20, 0); gl.vertexAttribDivisor(ap, 0);
        gl.enableVertexAttribArray(au); gl.vertexAttribPointer(au, 2, gl.FLOAT, false, 20, 12); gl.vertexAttribDivisor(au, 0);
        gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.meshIdx);
        gl.drawElements(gl.TRIANGLES, this.meshCount, gl.UNSIGNED_INT, 0);
        gl.disableVertexAttribArray(au); gl.disable(gl.DEPTH_TEST);
      };
      const drawBy = (mode) => { if (mode === "flat") drawFlat(); else if (mode === "mesh") drawMesh(false); else if (mode === "wire") drawMesh(true); else drawSplats(); };
      if (this.drawMode === "split") {
        gl.enable(gl.SCISSOR_TEST);
        const sx = Math.round(W * this.split);
        gl.scissor(0, 0, sx, H); drawSplats();
        gl.scissor(sx, 0, W - sx, H); drawBy(this.compareMode);
        gl.disable(gl.SCISSOR_TEST);
      } else drawBy(this.drawMode);
      if (this.overlaysOn && this.lineCount > 0) {
        gl.useProgram(this.lineProg);
        gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
        gl.uniformMatrix4fv(gl.getUniformLocation(this.lineProg, "projection"), false, this.projection);
        gl.uniformMatrix4fv(gl.getUniformLocation(this.lineProg, "view"), false, view);
        gl.bindBuffer(gl.ARRAY_BUFFER, this.lineBuf);
        const ap = gl.getAttribLocation(this.lineProg, "pos"), ac = gl.getAttribLocation(this.lineProg, "col");
        gl.enableVertexAttribArray(ap); gl.vertexAttribPointer(ap, 3, gl.FLOAT, false, 28, 0); gl.vertexAttribDivisor(ap, 0);
        gl.enableVertexAttribArray(ac); gl.vertexAttribPointer(ac, 4, gl.FLOAT, false, 28, 12); gl.vertexAttribDivisor(ac, 0);
        gl.drawArrays(gl.LINES, 0, this.lineCount);
        gl.disableVertexAttribArray(ac);
      }
      gl.useProgram(this.program);
    }
    /** Current camera-to-world and view matrices (for HUD / capture metadata). */
    currentView() { const c2w = lookAt(this.pos, this.target); return { c2w, view: invert4(c2w) }; }

    // ---- public API
    setScene({ fx, width, height }) { this.scene = { fx, width, height }; this.resize(); }
    set(param, value) { this.params[param] = value; if (param === "zoom") this.resize(); if (param === "focus") this._refocus(); }
    resetView() { this.pos = [0, 0, 0]; this.target = [0, 0, this.params.focus]; this.params.wobble = true; }
    setPose(pos, target) { this.pos = pos; this.target = target; this.params.wobble = false; }
    clear() { ++this.loadToken; this.vertexCount = 0; }
    get state() { return { pos: this.pos, target: this.target, vertexCount: this.vertexCount, ...this.params }; }

    async loadUrl(url) {
      const token = ++this.loadToken;
      this.vertexCount = 0;
      const req = await fetch(url);
      if (!req.ok) throw new Error(`${req.status} unable to load ${url}`);
      const total = +req.headers.get("content-length") || 0;
      const chunks = [];
      let read = 0, lastPost = 0;
      const reader = req.body.getReader();
      const data = total ? new Uint8Array(total) : null;
      while (true) {
        const { done, value } = await reader.read();
        if (done || token !== this.loadToken) break;
        if (data) data.set(value, read); else chunks.push(value);
        read += value.length;
        this.onProgress(total ? read / total : 0);
        if (data && read - lastPost > 6e6) {
          this.worker.postMessage({ buffer: data.buffer, vertexCount: Math.floor(read / 32) });
          lastPost = read;
        }
      }
      if (token !== this.loadToken) return false;
      let buf = data ? data.buffer : new Blob(chunks).arrayBuffer && (await new Blob(chunks).arrayBuffer());
      this.worker.postMessage({ buffer: buf, vertexCount: Math.floor(read / 32) });
      this.onProgress(1);
      return true;
    }

    loadFile(file) {
      return new Promise((resolve, reject) => {
        ++this.loadToken;
        this.vertexCount = 0;
        const fr = new FileReader();
        fr.onerror = reject;
        fr.onload = () => {
          const u8 = new Uint8Array(fr.result);
          const isPly = u8[0] == 112 && u8[1] == 108 && u8[2] == 121 && u8[3] == 10;
          let meta = { fx: null, width: null, height: null };
          if (isPly) {
            meta = parseSharpMeta(fr.result) || meta;
            this.worker.postMessage({ ply: fr.result, save: false });
          } else {
            this.worker.postMessage({ buffer: fr.result, vertexCount: Math.floor(u8.length / 32) });
          }
          this.setScene(meta);
          resolve(meta);
        };
        fr.readAsArrayBuffer(file);
      });
    }

    // ---- internals
    resize() {
      const gl = this.gl, c = this.canvas;
      const W = c.clientWidth || 1, H = c.clientHeight || 1;
      const s = this.scene;
      // Returning to the Lab re-runs this with identical inputs; reallocating the backing store
      // there costs a GPU stall for nothing, so bail when no input has moved.
      const sig = `${W}x${H}|${s.fx}|${s.width}|${s.height}|${this.params.zoom}|${this.fRatioOverride}`;
      if (sig === this._resizeSig) return;
      this._resizeSig = sig;
      const ratioW = s.fx && s.width ? s.fx / s.width : 30 / 36;
      const ratioH = s.fx && s.height ? s.fx / s.height : ratioW * (16 / 9);
      const f = (this.fRatioOverride ? W * this.fRatioOverride : Math.max(W * ratioW, H * ratioH)) * this.params.zoom;  // "cover": photo fills the canvas
      this.width = W; this.height = H;
      gl.useProgram(this.program);
      gl.uniform2fv(this.u.focal, new Float32Array([f, f]));
      this.projection = getProjectionMatrix(f, f, W, H);
      gl.uniform2fv(this.u.viewport, new Float32Array([W, H]));
      // cap the backing store: DPR up to 1.5 and at most ~3.2 MP, which keeps 1.18M splats interactive
      const dpr = Math.min(devicePixelRatio || 1, 1.5, Math.sqrt(3.2e6 / Math.max(1, W * H)));
      c.width = Math.round(W * dpr);
      c.height = Math.round(H * dpr);
      gl.viewport(0, 0, c.width, c.height);
      gl.uniformMatrix4fv(this.u.projection, false, this.projection);
    }

    _refocus() { this.target = vadd(this.pos, vscale(vnorm(vsub(this.target, this.pos)), this.params.focus)); }

    _bindInput() {
      const c = this.canvas;
      let drag = null;
      const interact = () => { if (this.params.wobble) { this.params.wobble = false; this.onInteract(); } };
      c.addEventListener("pointerdown", (e) => {
        drag = { x: e.clientX, y: e.clientY, button: e.button, shift: e.shiftKey };
        c.setPointerCapture(e.pointerId);
        interact();
      });
      c.addEventListener("contextmenu", (e) => e.preventDefault());
      c.addEventListener("pointermove", (e) => {
        if (!drag) return;
        const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
        drag.x = e.clientX; drag.y = e.clientY;
        const c2w = lookAt(this.pos, this.target);
        const right = [c2w[0], c2w[1], c2w[2]], down = [c2w[4], c2w[5], c2w[6]];
        if (drag.button === 2 || drag.shift) {
          const dist = vlen(vsub(this.target, this.pos));
          const mv = vadd(vscale(right, (-dx / this.height) * dist), vscale(down, (-dy / this.height) * dist));
          this.pos = vadd(this.pos, mv); this.target = vadd(this.target, mv);
        } else {
          let rel = vsub(this.pos, this.target);
          rel = rotateVec(rel, [0, 1, 0], (-dx / this.height) * 2.5);
          rel = rotateVec(rel, right, (dy / this.height) * 2.5);
          this.pos = vadd(this.target, rel);
        }
      });
      c.addEventListener("pointerup", () => { drag = null; });
      c.addEventListener("wheel", (e) => {
        e.preventDefault();
        interact();
        const rel = vsub(this.target, this.pos);
        this.pos = vsub(this.pos, vscale(vnorm(rel), Math.sign(e.deltaY) * 0.06 * vlen(rel)));
      }, { passive: false });
      window.addEventListener("keydown", (e) => {
        if (["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)) return;
        if (["KeyW", "KeyA", "KeyS", "KeyD", "KeyQ", "KeyE"].includes(e.code)) { this.keys.add(e.code); interact(); }
      });
      window.addEventListener("keyup", (e) => this.keys.delete(e.code));
      window.addEventListener("blur", () => this.keys.clear());
    }

    // Headless render of one pose: returns a PNG blob once the depth sort for that view has landed.
    async renderPose(pos, target, timeoutMs = 600) {
      this.paused = true;
      if (this.drawMode !== "sharp" && this.drawMode !== "split") timeoutMs = 0;
      this.pos = pos; this.target = target; this.params.wobble = false;
      const view = invert4(lookAt(pos, target));
      await new Promise((resolve) => {
        this._sortWaiter = resolve;
        this.worker.postMessage({ view: multiply4(this.projection, view), force: true });
        setTimeout(() => { if (this._sortWaiter === resolve) { this._sortWaiter = null; resolve(); } }, timeoutMs);
      });
      const gl = this.gl;
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      this._drawScene(view);
      gl.finish();
      return true;   // the caller reads the canvas (toDataURL); no Blob is created here
    }
    waitForSplats(timeoutMs = 60000) {
      return new Promise((resolve, reject) => {
        const t0 = performance.now();
        const tick = () => { if (this.vertexCount > 0) resolve(this.vertexCount); else if (performance.now() - t0 > timeoutMs) reject(new Error("timeout")); else setTimeout(tick, 100); };
        tick();
      });
    }

    _frame(now) {
      this._raf = 0;
      const dt = Math.min(0.1, (now - this.last) / 1000);
      this.last = now;
      if (this._paused) return;
      const p = this.params;
      let c2w;
      if (p.wobble) {
        const t = ((now - this.t0) / 1000) * p.speed * Math.PI * 0.5;
        const pos = [p.amp * Math.sin(t), 0.4 * p.amp * Math.sin(2 * t), 0.25 * p.amp * (Math.cos(t) - 1)];
        c2w = lookAt(pos, [0, 0, p.focus]);
      } else {
        if (this.keys.size) {
          const c = lookAt(this.pos, this.target);
          const right = [c[0], c[1], c[2]], down = [c[4], c[5], c[6]], fwd = [c[8], c[9], c[10]];
          const sp = 0.6 * Math.max(0.3, vlen(vsub(this.target, this.pos))) * dt;
          let mv = [0, 0, 0];
          if (this.keys.has("KeyW")) mv = vadd(mv, vscale(fwd, sp));
          if (this.keys.has("KeyS")) mv = vadd(mv, vscale(fwd, -sp));
          if (this.keys.has("KeyD")) mv = vadd(mv, vscale(right, sp));
          if (this.keys.has("KeyA")) mv = vadd(mv, vscale(right, -sp));
          if (this.keys.has("KeyE")) mv = vadd(mv, vscale(down, -sp));
          if (this.keys.has("KeyQ")) mv = vadd(mv, vscale(down, sp));
          this.pos = vadd(this.pos, mv); this.target = vadd(this.target, mv);
        }
        c2w = lookAt(this.pos, this.target);
      }
      const view = invert4(c2w);
      this.worker.postMessage({ view: multiply4(this.projection, view) });
      const gl = this.gl;
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      this._drawScene(view);
      this.avgFps = this.avgFps * 0.9 + (1 / dt || 0) * 0.1;
      this.onFps(this.avgFps, this.vertexCount);
      this._raf = requestAnimationFrame((t) => this._frame(t));
    }
  }

  // Parse the SHARP-specific metadata elements stored after the vertex block of a .ply.
  function parseSharpMeta(arrayBuffer) {
    const u8 = new Uint8Array(arrayBuffer);
    const header = new TextDecoder().decode(u8.slice(0, 10240));
    const endTag = "end_header\n";
    const end = header.indexOf(endTag);
    if (end < 0 || !/element intrinsic 9/.test(header)) return null;
    const vc = parseInt(/element vertex (\d+)/.exec(header)[1]);
    const block = /element vertex \d+\n([\s\S]*?)(?=\nelement |\nend_header)/.exec(header)[1];
    const props = (block.match(/property/g) || []).length;
    let off = end + endTag.length + vc * props * 4;
    const dv = new DataView(arrayBuffer);
    const meta = { fx: null, width: null, height: null };
    const order = header.slice(0, end).split("\n").filter((l) => l.startsWith("element ")).map((l) => l.split(" ")[1]);
    for (const el of order.slice(1)) {
      if (el === "extrinsic") off += 64;
      else if (el === "intrinsic") { meta.fx = dv.getFloat32(off, true); off += 36; }
      else if (el === "image_size") { meta.width = dv.getUint32(off, true); meta.height = dv.getUint32(off + 4, true); off += 8; }
      else if (el === "frame" || el === "disparity") off += 8;
      else if (el === "color_space") off += 1;
      else if (el === "version") off += 3;
    }
    return meta;
  }

  window.SplatViewer = SplatViewer;
})();
