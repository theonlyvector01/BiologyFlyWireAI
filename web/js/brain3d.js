/* 3D-«микроскоп»: WebGL-визуализация нейронов FlyWire без внешних библиотек.
 * Скелеты нейронов рисуются линиями, сомы — светящимися точками, силуэт мозга — облаком сом всех нейронов.
 * Цвет и яркость нейрона = его активность в модели (шкала как у кальциевой визуализации).
 */
(function (root) {
  "use strict";

  // Палитра активности как у мультиплексной флуоресцентной микроскопии: синий -> фиолетовый -> пурпур -> жёлтый
  const STOPS = [[0.00, [44, 62, 150]], [0.3, [96, 78, 210]], [0.55, [184, 96, 222]], [0.8, [238, 228, 92]], [1.0, [255, 253, 214]]];
  function cmap(a) {
    a = Math.max(0, Math.min(1, a));
    for (let i = 1; i < STOPS.length; i++) {
      if (a <= STOPS[i][0]) {
        const [p0, c0] = STOPS[i - 1], [p1, c1] = STOPS[i];
        const t = (a - p0) / (p1 - p0);
        return [c0[0] + (c1[0] - c0[0]) * t, c0[1] + (c1[1] - c0[1]) * t, c0[2] + (c1[2] - c0[2]) * t];
      }
    }
    return STOPS[STOPS.length - 1][1];
  }
  const cmapCss = "linear-gradient(90deg," + STOPS.map(([p, c]) => `rgb(${c.join(",")}) ${p * 100}%`).join(",") + ")";

  function b64(str, Type) {
    const bin = atob(str);
    const buf = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
    return new Type(buf.buffer);
  }

  // --- матрицы 4x4 (column-major) ---
  function persp(fov, asp, n, f) {
    const t = 1 / Math.tan(fov / 2), nf = 1 / (n - f);
    return [t / asp, 0, 0, 0, 0, t, 0, 0, 0, 0, (f + n) * nf, -1, 0, 0, 2 * f * n * nf, 0];
  }
  function mul(a, b) {
    const o = new Array(16);
    for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) {
      let s = 0;
      for (let k = 0; k < 4; k++) s += a[k * 4 + r] * b[c * 4 + k];
      o[c * 4 + r] = s;
    }
    return o;
  }
  const rotX = (a) => [1, 0, 0, 0, 0, Math.cos(a), Math.sin(a), 0, 0, -Math.sin(a), Math.cos(a), 0, 0, 0, 0, 1];
  const rotY = (a) => [Math.cos(a), 0, -Math.sin(a), 0, 0, 1, 0, 0, Math.sin(a), 0, Math.cos(a), 0, 0, 0, 0, 1];
  const trans = (x, y, z) => [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1];

  const VS_LINE = `attribute vec3 p; attribute vec4 c; uniform mat4 M; varying vec4 vc;
    void main(){ gl_Position = M * vec4(p,1.0); vc = c; }`;
  const FS_LINE = `precision mediump float; varying vec4 vc; void main(){ gl_FragColor = vc; }`;
  const VS_PT = `attribute vec3 p; attribute vec4 c; attribute float s; uniform mat4 M; uniform float dpr; varying vec4 vc;
    void main(){ gl_Position = M * vec4(p,1.0); gl_PointSize = s * dpr; vc = c; }`;
  const FS_PT = `precision mediump float; varying vec4 vc; uniform float sq;
    void main(){ vec2 d = gl_PointCoord - 0.5; float r = length(d);
      if (sq > 0.5) { gl_FragColor = vc; return; }
      if (r > 0.5) discard;
      float g = smoothstep(0.5, 0.0, r); gl_FragColor = vec4(vc.rgb, vc.a * g); }`;

  function compile(gl, vs, fs) {
    const mk = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); return s; };
    const p = gl.createProgram();
    gl.attachShader(p, mk(gl.VERTEX_SHADER, vs));
    gl.attachShader(p, mk(gl.FRAGMENT_SHADER, fs));
    gl.linkProgram(p);
    return p;
  }

  function create(canvas, opts) {
    const model = opts.model, sk = opts.skeleton;
    const N = model.N;
    const gl = canvas.getContext("webgl", { antialias: true, alpha: true, premultipliedAlpha: true, preserveDrawingBuffer: true });
    if (!gl) throw new Error("WebGL недоступен в этом браузере");

    // --- геометрия -------------------------------------------------------------
    const cloud = sk ? b64(sk.cloud, Int16Array) : null;
    let cx = 0, cy = 0, cz = 0, ext = 1;
    {
      const P = model.neurons.pos;
      const src = cloud || Int16Array.from(P, (v) => v * 10);
      const n = src.length / 3;
      let mn = [1e9, 1e9, 1e9], mx = [-1e9, -1e9, -1e9];
      for (let i = 0; i < n; i++) for (let k = 0; k < 3; k++) {
        const v = src[i * 3 + k] * 0.1; if (v < mn[k]) mn[k] = v; if (v > mx[k]) mx[k] = v;
      }
      cx = (mn[0] + mx[0]) / 2; cy = (mn[1] + mx[1]) / 2; cz = (mn[2] + mx[2]) / 2;
      ext = Math.max(mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2]) / 2;
    }
    // мировые координаты: X вправо, Y вверх (спинная сторона), Z к зрителю (передняя сторона)
    const W = (x, y, z) => [(x - cx) / ext, -(y - cy) / ext, -(z - cz) / ext];

    let linePos = null, lineNeuron = null, nLineV = 0;
    if (sk) {
      const xyz = b64(sk.xyz, Int16Array), par = b64(sk.parent, Int32Array), nid = b64(sk.neuron, Uint16Array);
      let nseg = 0;
      for (let i = 0; i < par.length; i++) if (par[i] >= 0) nseg++;
      nLineV = nseg * 2;
      linePos = new Float32Array(nLineV * 3);
      lineNeuron = new Uint16Array(nLineV);
      let k = 0;
      for (let i = 0; i < par.length; i++) {
        const j = par[i];
        if (j < 0) continue;
        for (const v of [i, j]) {
          const w = W(xyz[v * 3] * 0.1, xyz[v * 3 + 1] * 0.1, xyz[v * 3 + 2] * 0.1);
          linePos.set(w, k * 3); lineNeuron[k] = nid[i]; k++;
        }
      }
    }
    const somaPos = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) somaPos.set(W(model.neurons.pos[i * 3], model.neurons.pos[i * 3 + 1], model.neurons.pos[i * 3 + 2]), i * 3);
    let cloudPos = null, nCloud = 0;
    if (cloud) {
      nCloud = cloud.length / 3;
      cloudPos = new Float32Array(nCloud * 3);
      for (let i = 0; i < nCloud; i++) cloudPos.set(W(cloud[i * 3] * 0.1, cloud[i * 3 + 1] * 0.1, cloud[i * 3 + 2] * 0.1), i * 3);
    }

    // --- буферы -----------------------------------------------------------------
    const progL = compile(gl, VS_LINE, FS_LINE), progP = compile(gl, VS_PT, FS_PT);
    const buf = (data, usage) => { const b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.bufferData(gl.ARRAY_BUFFER, data, usage || gl.STATIC_DRAW); return b; };
    const bLinePos = linePos ? buf(linePos) : null;
    const lineCol = new Uint8Array(nLineV * 4);
    const bLineCol = linePos ? buf(lineCol, gl.DYNAMIC_DRAW) : null;
    const bSomaPos = buf(somaPos);
    const somaCol = new Uint8Array(N * 4), somaSize = new Float32Array(N);
    const bSomaCol = buf(somaCol, gl.DYNAMIC_DRAW), bSomaSize = buf(somaSize, gl.DYNAMIC_DRAW);
    let bCloudPos = null, bCloudCol = null, bCloudSize = null;
    if (cloudPos) {
      bCloudPos = buf(cloudPos);
      const cc = new Uint8Array(nCloud * 4);
      for (let i = 0; i < nCloud; i++) cc.set([170, 170, 170, 60], i * 4);   // «ASCII»-точки силуэта
      bCloudCol = buf(cc);
      bCloudSize = buf(new Float32Array(nCloud).fill(1.6));
    }

    // --- состояние ---------------------------------------------------------------
    let yaw = 0, pitch = 0.0, dist = 2.15, M = null;
    let activity = new Float32Array(N), highlight = null, pathSet = null, dirty = true;
    const neuronRGBA = new Uint8Array(N * 4);

    function recolor() {
      for (let i = 0; i < N; i++) {
        const a = activity[i];
        const c = cmap(a);
        // линии (скелеты) складываются, поэтому их яркость невысокая; сомы ярче
        let alpha = 0.035 + 0.32 * Math.pow(a, 1.2);
        let somaA = 0.25 + 0.75 * a;
        if (highlight && !highlight.has(i)) { alpha *= 0.15; somaA *= 0.2; }
        if (highlight && highlight.has(i)) { alpha = Math.min(1, alpha * 2.2 + 0.08); }
        if (pathSet && pathSet.has(i)) { alpha = Math.min(1, alpha + 0.3); somaA = 1; }
        neuronRGBA[i * 4] = c[0]; neuronRGBA[i * 4 + 1] = c[1]; neuronRGBA[i * 4 + 2] = c[2];
        neuronRGBA[i * 4 + 3] = Math.round(alpha * 255);
        somaCol.set(neuronRGBA.subarray(i * 4, i * 4 + 4), i * 4);
        somaCol[i * 4 + 3] = Math.min(255, Math.round(somaA * 255));
        let s = 3 + 9 * a;
        if (pathSet && pathSet.has(i)) s += 5;
        if (highlight && !highlight.has(i)) s *= 0.6;
        somaSize[i] = s;
      }
      for (let v = 0; v < nLineV; v++) lineCol.set(neuronRGBA.subarray(lineNeuron[v] * 4, lineNeuron[v] * 4 + 4), v * 4);
      if (bLineCol) { gl.bindBuffer(gl.ARRAY_BUFFER, bLineCol); gl.bufferSubData(gl.ARRAY_BUFFER, 0, lineCol); }
      gl.bindBuffer(gl.ARRAY_BUFFER, bSomaCol); gl.bufferSubData(gl.ARRAY_BUFFER, 0, somaCol);
      gl.bindBuffer(gl.ARRAY_BUFFER, bSomaSize); gl.bufferSubData(gl.ARRAY_BUFFER, 0, somaSize);
    }

    function bindAttr(prog, name, b, size, type, norm) {
      const loc = gl.getAttribLocation(prog, name);
      if (loc < 0) return;
      gl.bindBuffer(gl.ARRAY_BUFFER, b);
      gl.enableVertexAttribArray(loc);
      gl.vertexAttribPointer(loc, size, type, !!norm, 0, 0);
    }

    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = Math.max(1, Math.round(canvas.clientWidth * dpr)), h = Math.max(1, Math.round(canvas.clientHeight * dpr));
      if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; dirty = true; }
      return dpr;
    }

    function draw() {
      const dpr = resize();
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.clearColor(0, 0, 0, 0);                       // прозрачный фон: видна сетка рамки
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.disable(gl.DEPTH_TEST);
      gl.enable(gl.BLEND);
      gl.blendFuncSeparate(gl.SRC_ALPHA, gl.ONE, gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
      const P = persp(0.7, canvas.width / canvas.height, 0.1, 20);
      // сдвиг изображения в кадре: на широком экране мозг правее (слева текст), на узком — ниже
      const wide = canvas.width > canvas.height * 1.1;
      const off = opts.offset ? opts.offset(wide) : [0, 0];
      M = mul(trans(off[0], off[1], 0), mul(P, mul(trans(0, 0, -dist), mul(rotX(pitch), rotY(yaw)))));
      if (bCloudPos) {
        gl.useProgram(progP);
        gl.uniformMatrix4fv(gl.getUniformLocation(progP, "M"), false, M);
        gl.uniform1f(gl.getUniformLocation(progP, "dpr"), dpr);
        gl.uniform1f(gl.getUniformLocation(progP, "sq"), 1);
        bindAttr(progP, "p", bCloudPos, 3, gl.FLOAT);
        bindAttr(progP, "c", bCloudCol, 4, gl.UNSIGNED_BYTE, true);
        bindAttr(progP, "s", bCloudSize, 1, gl.FLOAT);
        gl.drawArrays(gl.POINTS, 0, nCloud);
      }
      if (bLinePos) {
        gl.useProgram(progL);
        gl.uniformMatrix4fv(gl.getUniformLocation(progL, "M"), false, M);
        bindAttr(progL, "p", bLinePos, 3, gl.FLOAT);
        bindAttr(progL, "c", bLineCol, 4, gl.UNSIGNED_BYTE, true);
        gl.drawArrays(gl.LINES, 0, nLineV);
      }
      gl.useProgram(progP);
      gl.uniformMatrix4fv(gl.getUniformLocation(progP, "M"), false, M);
      gl.uniform1f(gl.getUniformLocation(progP, "dpr"), dpr);
      gl.uniform1f(gl.getUniformLocation(progP, "sq"), 0);
      bindAttr(progP, "p", bSomaPos, 3, gl.FLOAT);
      bindAttr(progP, "c", bSomaCol, 4, gl.UNSIGNED_BYTE, true);
      bindAttr(progP, "s", bSomaSize, 1, gl.FLOAT);
      gl.drawArrays(gl.POINTS, 0, N);
      dirty = false;
      if (opts.onDraw) opts.onDraw(project);
    }

    // проекция точки нейрона (индексы) в пиксели холста — для подписей-«булавок»
    function project(indices) {
      if (!M || !indices.length) return null;
      let x = 0, y = 0, z = 0;
      for (const i of indices) { x += somaPos[i * 3]; y += somaPos[i * 3 + 1]; z += somaPos[i * 3 + 2]; }
      x /= indices.length; y /= indices.length; z /= indices.length;
      const cxp = M[0] * x + M[4] * y + M[8] * z + M[12], cyp = M[1] * x + M[5] * y + M[9] * z + M[13], cw = M[3] * x + M[7] * y + M[11] * z + M[15];
      if (cw <= 0) return null;
      return { x: (cxp / cw * 0.5 + 0.5) * canvas.clientWidth, y: (1 - (cyp / cw * 0.5 + 0.5)) * canvas.clientHeight };
    }

    let alive = true;
    function loop() {
      if (!alive) return;
      if (dirty) draw();
      requestAnimationFrame(loop);
    }

    // --- управление камерой ------------------------------------------------------
    const pointers = new Map();
    let pinch0 = 0, dist0 = dist;
    canvas.addEventListener("pointerdown", (e) => { canvas.setPointerCapture(e.pointerId); pointers.set(e.pointerId, [e.clientX, e.clientY]); if (pointers.size === 2) { const [a, b] = [...pointers.values()]; pinch0 = Math.hypot(a[0] - b[0], a[1] - b[1]); dist0 = dist; } });
    canvas.addEventListener("pointerup", (e) => pointers.delete(e.pointerId));
    canvas.addEventListener("pointercancel", (e) => pointers.delete(e.pointerId));
    canvas.addEventListener("pointermove", (e) => {
      if (pointers.has(e.pointerId)) {
        const prev = pointers.get(e.pointerId);
        if (pointers.size === 1) {
          yaw += (e.clientX - prev[0]) * 0.008;
          pitch = Math.max(-1.57, Math.min(1.57, pitch + (e.clientY - prev[1]) * 0.008));
        }
        pointers.set(e.pointerId, [e.clientX, e.clientY]);
        if (pointers.size === 2) {
          const [a, b] = [...pointers.values()];
          const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
          if (pinch0 > 0) dist = Math.max(1.2, Math.min(7, dist0 * pinch0 / d));
        }
        dirty = true;
        if (opts.onHover) opts.onHover(null);
        return;
      }
      if (opts.onHover) opts.onHover(pick(e));
    });
    canvas.addEventListener("pointerleave", () => opts.onHover && opts.onHover(null));
    canvas.addEventListener("wheel", (e) => { e.preventDefault(); dist = Math.max(1.2, Math.min(7, dist * Math.exp(e.deltaY * 0.001))); dirty = true; }, { passive: false });

    function pick(e) {
      if (!M) return null;
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left, my = e.clientY - rect.top;
      let best = -1, bd = 14 * 14;
      for (let i = 0; i < N; i++) {
        if (highlight && !highlight.has(i)) continue;
        const x = somaPos[i * 3], y = somaPos[i * 3 + 1], z = somaPos[i * 3 + 2];
        const cxp = M[0] * x + M[4] * y + M[8] * z + M[12], cyp = M[1] * x + M[5] * y + M[9] * z + M[13], cw = M[3] * x + M[7] * y + M[11] * z + M[15];
        if (cw <= 0) continue;
        const sx = (cxp / cw * 0.5 + 0.5) * rect.width, sy = (1 - (cyp / cw * 0.5 + 0.5)) * rect.height;
        const d = (sx - mx) ** 2 + (sy - my) ** 2;
        if (d < bd) { bd = d; best = i; }
      }
      return best < 0 ? null : { index: best, x: mx, y: my };
    }

    window.addEventListener("resize", () => { dirty = true; });
    recolor();
    requestAnimationFrame(loop);

    const api = {
      hasSkeletons: !!sk,
      nSegments: nLineV / 2,
      setActivity(a) { activity = a; recolor(); dirty = true; },
      setHighlight(set) { highlight = set && set.size ? set : null; recolor(); dirty = true; },
      setPath(set) { pathSet = set && set.size ? set : null; recolor(); dirty = true; },
      setView(v) {
        if (v === "front") { yaw = 0; pitch = 0; }
        if (v === "top") { yaw = 0; pitch = 1.45; }
        if (v === "side") { yaw = -1.45; pitch = 0.05; }
        if (v === "three") { yaw = 0.85; pitch = 0.25; }
        dirty = true;
      },
      destroy() { alive = false; },
      redraw() { dirty = true; },
    };
    if (opts.view) api.setView(opts.view);
    if (opts.dist) dist = opts.dist;
    return api;
  }

  root.FlyBrain3D = { create, cmap, cmapCss };
})(window);
