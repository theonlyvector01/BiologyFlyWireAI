/* Симулятор коннектомной нейросети в браузере.
 * Точная копия pipeline/model.py: encode_female/encode_male и FlyCircuit.forward() при noise = 0.
 * Работает и в браузере (window.FlySim), и в Node.js (module.exports) — для проверки совпадения с PyTorch.
 */
(function (root) {
  "use strict";

  const sigmoid = (x) => 1 / (1 + Math.exp(-x));

  // ------------------------------- самка -------------------------------------------
  const SPECIES_IPI = { mel: 35.0, sim: 48.0 };
  const BOUT_MS = 600.0, PULSE_PART_MS = 400.0;
  const FEMALE_DEFAULT = {
    age_h: 96, mated: false, days_since_mating: 1, sp_null_male: false,
    deaf: false, or67d_mutant: false, lk_mutant: false,
    male_species: "mel", male_wings: true, male_cva: 1.0, song_amount: 1.0, custom_ipi: null,
    playback_ipi: null, silence: [], activate: [],
  };

  function immaturity(age_h, lk_mutant) {
    const other = sigmoid((22.0 - age_h) / 3.0);
    const lk = lk_mutant ? 0.0 : sigmoid((age_h - 10.0) / 4.0) * sigmoid((54.0 - age_h) / 6.0);
    return other + lk;
  }
  function sagDrive(sc) {
    if (!sc.mated) return 1.0;
    if (sc.sp_null_male) return 0.95;
    return 1.0 - 0.95 * Math.exp(-sc.days_since_mating / 4.0);
  }
  function songIpi(sc) {
    if (sc.playback_ipi) return +sc.playback_ipi;
    return +(sc.custom_ipi || SPECIES_IPI[sc.male_species] || 35.0);
  }

  function encodeFemale(scIn, cfg) {
    const sc = Object.assign({}, FEMALE_DEFAULT, scIn);
    const T = cfg.T_STEPS, DT = cfg.DT_MS, ON = cfg.STIM_ON, C = 6;
    const u = new Float32Array(T * C);
    const phase = 0.0;
    const malePresent = sc.male_species !== "none";
    const naturalSong = malePresent && sc.male_wings && sc.song_amount > 0;
    let ipi = 0, amp = 0, bouts = false;
    if (sc.playback_ipi) { ipi = +sc.playback_ipi; amp = 1.0; bouts = false; }
    else if (naturalSong) { ipi = songIpi(sc); amp = +sc.song_amount; bouts = true; }
    if (sc.deaf) amp = 0.0;
    if (amp > 0) {
      let t = ON * DT;
      const end = T * DT;
      while (t < end) {
        const inPulse = !bouts || ((t + phase) % BOUT_MS) < PULSE_PART_MS;
        if (inPulse) { const k = Math.floor(t / DT); if (k < T) u[k * C] += amp; }
        t += Math.max(ipi, 5.0);
      }
      if (bouts) for (let k = ON; k < T; k++) if (((k * DT + phase) % BOUT_MS) >= PULSE_PART_MS) u[k * C + 1] = amp;
    }
    const cva = malePresent ? +sc.male_cva : 0.0;
    const sag = sagDrive(sc), imm = immaturity(+sc.age_h, !!sc.lk_mutant);
    for (let k = 0; k < T; k++) {
      if (k >= ON) { u[k * C + 2] = sc.or67d_mutant ? 0.0 : cva; u[k * C + 3] = cva; }
      u[k * C + 4] = sag;
      u[k * C + 5] = imm;
    }
    return u;
  }

  // ------------------------------- самец -------------------------------------------
  const VIS_PERIOD_MS = 400.0;
  const TARGETS = {
    virgin: { hd: 1.0, t7: 0.1, cva: 0.0, motion: 1.0 },
    mated: { hd: 1.0, t7: 0.6, cva: 1.0, motion: 1.0 },
    sim: { hd: 0.0, t7: 0.8, cva: 0.0, motion: 1.0 },
    male: { hd: 0.0, t7: 1.0, cva: 1.0, motion: 1.0 },
    none: { hd: 0.0, t7: 0.0, cva: 0.0, motion: 0.0 },
  };
  const MALE_DEFAULT = {
    target: "virgin", hd: null, t7: null, cva: null, motion: null, dark: false,
    or67d_mutant: false, ppk23_mutant: false, gr32a_mutant: false, satiety: 0.0, silence: [], activate: [],
  };
  function targetCues(scIn) {
    const sc = Object.assign({}, MALE_DEFAULT, scIn);
    const c = Object.assign({}, TARGETS[sc.target]);
    for (const k of ["hd", "t7", "cva", "motion"]) if (sc[k] !== null && sc[k] !== undefined) c[k] = +sc[k];
    return c;
  }
  function encodeMale(scIn, cfg) {
    const sc = Object.assign({}, MALE_DEFAULT, scIn);
    const T = cfg.T_STEPS, DT = cfg.DT_MS, ON = cfg.STIM_ON, C = 5;
    const u = new Float32Array(T * C);
    const c = targetCues(sc);
    const fem = c.hd * (sc.ppk23_mutant ? 0 : 1);
    const mal = c.t7 * (sc.ppk23_mutant ? 0 : 1) * (sc.gr32a_mutant ? 0.4 : 1);
    const cva = c.cva * (sc.or67d_mutant ? 0 : 1);
    const mot = c.motion * (sc.dark ? 0 : 1);
    for (let k = 0; k < T; k++) {
      if (k >= ON) {
        u[k * C] = fem; u[k * C + 1] = mal; u[k * C + 2] = cva;
        u[k * C + 3] = mot * (0.7 + 0.3 * Math.sin(2 * Math.PI * (k * DT) / VIS_PERIOD_MS));
      }
      u[k * C + 4] = +sc.satiety;
    }
    return u;
  }

  const DEFAULTS = { female: FEMALE_DEFAULT, male: MALE_DEFAULT };
  function encodeScenario(model, sc) {
    return model.sex === "male" ? encodeMale(sc, model.config) : encodeFemale(sc, model.config);
  }

  function softplus(z) { return z > 20 ? z : Math.log1p(Math.exp(z)); }
  function act(x) { return Math.tanh(softplus(5.0 * x) / 5.0); }

  /**
   * Прогон сети. model — объект из data/<пол>_model.js.
   * Возвращает {p{имя}, groupMean{}, neuronMean, trace (T*N) | null, u, C}
   */
  function simulate(model, scIn, opts) {
    opts = opts || {};
    const sc = Object.assign({}, DEFAULTS[model.sex], scIn);
    const cfg = model.config, spec = model.spec;
    const N = model.N, T = cfg.T_STEPS, R0 = cfg.READOUT_FROM, C = spec.channels.length;
    const u = encodeScenario(model, sc);
    const keep = new Float32Array(N).fill(1);
    const actv = new Float32Array(N);
    const add = new Float32Array(C);
    for (const g of sc.silence || []) for (const i of model.groupMembers[g] || []) keep[i] = 0;
    for (const g of sc.activate || []) {
      if (spec.virtual[g]) add[spec.virtual[g][0]] += spec.virtual[g][1];
      else for (const i of model.groupMembers[g] || []) actv[i] = 1;
    }
    const { bias, alpha, win, ePre, ePost, eW } = model;
    if (!model._inList) {   // ненулевые входные веса: (нейрон, канал, вес)
      const li = [], lc = [], lw = [];
      for (let i = 0; i < N; i++) for (let c = 0; c < C; c++) { const w = win[i * C + c]; if (w !== 0) { li.push(i); lc.push(c); lw.push(w); } }
      model._inList = { i: Int32Array.from(li), c: Int32Array.from(lc), w: Float32Array.from(lw) };
    }
    const IL = model._inList, nIn = IL.i.length;
    const base = new Float32Array(N);
    for (let i = 0; i < N; i++) base[i] = bias[i] + actv[i] * 2.0;
    const x = new Float32Array(N), r = new Float32Array(N), drive = new Float32Array(N);
    const acc = new Float64Array(N);
    const trace = opts.record ? new Float32Array(T * N) : null;
    const E = ePre.length;
    for (let t = 0; t < T; t++) {
      const ub = t * C;
      drive.set(base);
      for (let k = 0; k < nIn; k++) { const c = IL.c[k]; drive[IL.i[k]] += IL.w[k] * (u[ub + c] + add[c]); }
      for (let e = 0; e < E; e++) drive[ePost[e]] += eW[e] * r[ePre[e]];   // реальные связи коннектома
      for (let i = 0; i < N; i++) {
        x[i] += alpha[i] * (drive[i] - x[i]);
        r[i] = keep[i] ? act(x[i]) : 0;
        if (t >= R0) acc[i] += r[i];
      }
      if (trace) trace.set(r, t * N);
    }
    const neuronMean = new Float32Array(N);
    for (let i = 0; i < N; i++) neuronMean[i] = acc[i] / (T - R0);
    const groupMean = {};
    for (const g of model.groupNames) {
      const m = model.groupMembers[g] || [];
      let s = 0;
      for (const i of m) s += neuronMean[i];
      groupMean[g] = m.length ? s / m.length : 0;
    }
    const ro = model.readout, p = {};
    for (const [name, grp] of spec.readouts) {
      let z = ro[name + "_k"] * (groupMean[grp] - ro[name + "_th"]);
      if (name === "oe") z += ro.oe_mated * (2 * (u[4] < 0.9 ? 1 : 0) - 1);   // самка: SAG подавлены => спаривалась
      p[name] = sigmoid(z);
    }
    return { p, groupMean, neuronMean, trace, u, C, sc };
  }

  const api = { simulate, encodeScenario, targetCues, immaturity, sagDrive, songIpi, DEFAULTS, TARGETS, SPECIES_IPI };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.FlySim = api;
})(typeof window !== "undefined" ? window : globalThis);
