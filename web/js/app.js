/* Интерфейс «Коннектом выбора»: управление опытом, симуляция, объяснение решения, графики.
 * Два режима: самка выбирает самца (FlyWire) и самец решает, ухаживать ли (MaleCNS). */
(function () {
  "use strict";
  const $ = (s, r) => (r || document).querySelector(s);
  const el = (tag, attrs, ...kids) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === "class") e.className = v;
      else if (k === "html") e.innerHTML = v;
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
      else if (v !== null && v !== undefined && v !== false) e.setAttribute(k, v === true ? "" : v);
    }
    for (const k of kids.flat()) if (k !== null && k !== undefined && k !== false) e.append(k.nodeType ? k : document.createTextNode(k));
    return e;
  };
  const SVGNS = "http://www.w3.org/2000/svg";
  const svg = (tag, attrs) => { const e = document.createElementNS(SVGNS, tag); for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v); return e; };
  const nf = (x, d = 2) => Number(x).toLocaleString("ru-RU", { minimumFractionDigits: d, maximumFractionDigits: d });
  const pct = (p) => Math.round(p * 100) + "%";
  const pp = (d) => { const v = Math.round(d * 100); return v > 0 ? "+" + v : v < 0 ? "−" + Math.abs(v) : "0"; };
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const clone = (o) => JSON.parse(JSON.stringify(o));

  const MODELS = window.FLY_MODELS || {};
  const SKELS = window.FLY_SKELETONS || {};
  if (!MODELS.female && !MODELS.male) {
    $("#tab-sim").innerHTML = '<div class="err">Не найдены данные модели (web/data/*_model.js). Запустите pipeline/06_export_web.py.</div>';
    return;
  }

  function prep(m) {
    if (m._ready) return m;
    m.bias = Float32Array.from(m.bias); m.alpha = Float32Array.from(m.alpha); m.win = Float32Array.from(m.win);
    m.ePre = Int32Array.from(m.ePre); m.ePost = Int32Array.from(m.ePost); m.eW = Float32Array.from(m.eW);
    m.outEdges = Array.from({ length: m.N }, () => []);
    for (let e = 0; e < m.ePre.length; e++) m.outEdges[m.ePre[e]].push(e);
    m._ready = true;
    return m;
  }
  const ageFmt = (h) => (h < 48 ? `${Math.round(h)} ч` : `${nf(h / 24, h % 24 ? 1 : 0)} сут`);
  const optoNames = (cfg, list) => list.map((k) => (cfg.opto.find((o) => o[0] === k) || [k, k])[1]).join(", ");
  function optoText(cfg, sc) {
    const parts = [];
    if ((sc.silence || []).length) parts.push("выключены " + optoNames(cfg, sc.silence));
    if ((sc.activate || []).length) parts.push("включены " + optoNames(cfg, sc.activate));
    return `Оптогенетика: ${parts.join("; ")}.`;
  }

  // =====================================================================================
  // Самка
  // =====================================================================================
  const FEMALE = {
    key: "female",
    subtitle: "Нейросеть на настоящей проводке мозга дрозофилы решает, примет ли самка самца",
    tag: "самка · FlyWire 783",
    view: "front",
    statement: "Это мозг самки дрозофилы, которая выбирает партнёра.",
    lede: "Каждая светящаяся линия — настоящий нейрон из коннектома FlyWire. Нейросеть, построенная на связях этих нейронов, решает, принять ли самца.",
    pins: [["JO", "Слух", "--mint", "l"], ["vpoEN", "vpoEN", "--sky", "r"], ["pC1", "pC1", "--lemon", "l"], ["SAG", "SAG", "--mint", "r"], ["vpoDN", "vpoDN · да", "--lime", "l"], ["DNp13", "DNp13 · нет", "--pink", "r"], ["ORN_cVA", "Обоняние", "--sky", "l"]],
    presetDefault: "wt_mel",
    groupsShown: [
      ["JO", "Слух (JO)"], ["ORN_cVA", "Обоняние cVA"], ["SAG", "SAG «девственница»"], ["vpoEN", "vpoEN"], ["pC2l", "pC2l"],
      ["pCd", "pCd"], ["pC1", "pC1a–c"], ["vpoIN", "AVLP008 (торм.)"], ["vpoDN", "vpoDN → принять"], ["DNp13", "DNp13 → отказ"],
    ],
    trace: [["vpoEN", "vpoEN", "--s1"], ["pC1", "pC1a–c", "--s2"], ["vpoDN", "vpoDN", "--s3"], ["DNp13", "DNp13", "--s4"]],
    opto: [["vpoEN", "vpoEN"], ["pC2l", "pC2l"], ["pC1", "pC1a–c"], ["pC1de", "pC1d/e"], ["pCd", "pCd"], ["SAG", "SAG"],
      ["vpoIN", "AVLP008"], ["aSP", "aSP-f/g"], ["vpoDN", "vpoDN"], ["DNp13", "DNp13"], ["LK", "Лейкокинин"]],
    optoOnlyOn: ["LK"],
    alias: { DNp37: "vpoDN", AN_SMP_2: "SAG", AVLP008: "AVLP008 (торм.)" },
    defaults: { age_h: 96, mated: false, days_since_mating: 1, sp_null_male: false, deaf: false, or67d_mutant: false, lk_mutant: false,
      male_species: "mel", custom_ipi: 35, male_wings: true, song_amount: 1, male_cva: 1, playback_on: false, playback_ipi: 35, opto: {} },
    sections() {
      return [
        { title: "Самка", small: "выбирает партнёра", fields: [
          { type: "range", id: "age_h", label: "Возраст после выхода из куколки", min: 6, max: 240, step: 6, fmt: ageFmt },
          { type: "seg", id: "mated", label: "Статус", options: [[false, "Девственница"], [true, "Спаривалась"]] },
          { type: "range", id: "days_since_mating", label: "Прошло после спаривания", min: 0.5, max: 10, step: 0.5, fmt: (d) => `${nf(d, d % 1 ? 1 : 0)} сут`, show: (u) => u.mated },
          { type: "check", id: "sp_null_male", label: "Прошлый самец был без полового пептида (SP0)", show: (u) => u.mated },
          { type: "check", id: "deaf", label: "Глухая: удалены аристы антенн" },
          { type: "check", id: "or67d_mutant", label: "Мутант Or67d: не чувствует феромон cVA" },
          { type: "check", id: "lk_mutant", label: "Мутант по лейкокинину (LK)" },
        ] },
        { title: "Самец", small: "кандидат", fields: [
          { type: "seg", id: "male_species", label: "Вид самца", options: [["mel", "D. melanogaster"], ["sim", "D. simulans"], ["custom", "Свой ритм"]] },
          { type: "range", id: "custom_ipi", label: "Интервал между импульсами песни", min: 15, max: 90, step: 1, fmt: (v) => `${v} мс`, show: (u) => u.male_species === "custom" },
          { type: "check", id: "male_wings", label: "Есть крылья: может петь" },
          { type: "range", id: "song_amount", label: "Громкость песни", min: 0, max: 1.5, step: 0.05, fmt: (v) => nf(v, 2) },
          { type: "range", id: "male_cva", label: "Феромон cVA на самце", min: 0, max: 1.5, step: 0.05, fmt: (v) => nf(v, 2) },
          { type: "check", id: "playback_on", label: "Песня из динамика (опыт с немым самцом)" },
          { type: "range", id: "playback_ipi", label: "Интервал песни в динамике", min: 15, max: 90, step: 1, fmt: (v) => `${v} мс`, show: (u) => u.playback_on },
        ] },
      ];
    },
    toScenario(ui) {
      const sc = {
        age_h: ui.age_h, mated: ui.mated, days_since_mating: ui.days_since_mating, sp_null_male: ui.sp_null_male,
        deaf: ui.deaf, or67d_mutant: ui.or67d_mutant, lk_mutant: ui.lk_mutant,
        male_species: ui.male_species === "custom" ? "mel" : ui.male_species,
        custom_ipi: ui.male_species === "custom" ? ui.custom_ipi : null,
        male_wings: ui.male_wings, song_amount: ui.song_amount, male_cva: ui.male_cva,
        playback_ipi: ui.playback_on ? ui.playback_ipi : null, silence: [], activate: [],
      };
      for (const [g, v] of Object.entries(ui.opto)) { if (v === "off") sc.silence.push(g); if (v === "on") sc.activate.push(g); }
      return sc;
    },
    fromScenario(sc) {
      const ui = clone(this.defaults);
      for (const k of Object.keys(ui)) if (k in sc && sc[k] !== null && sc[k] !== undefined) ui[k] = sc[k];
      if (sc.custom_ipi) { ui.male_species = "custom"; ui.custom_ipi = sc.custom_ipi; }
      ui.playback_on = !!sc.playback_ipi;
      if (sc.playback_ipi) ui.playback_ipi = sc.playback_ipi;
      ui.opto = {};
      for (const g of sc.silence || []) ui.opto[g] = "off";
      for (const g of sc.activate || []) ui.opto[g] = "on";
      return ui;
    },
    verdict(r) {
      const p = r.p.acc;
      const cls = p >= 0.6 ? "yes" : p <= 0.35 ? "no" : "mid";
      return { p, cls, word: { yes: "Примет самца", no: "Отвергнет самца", mid: "Сомневается" }[cls],
        sub: `вероятность спаривания за 30–60 мин (по активности vpoDN: ${nf(r.groupMean.vpoDN)})`,
        second: [`Отказ через DNp13: ${r.p.oe >= 0.5 ? "выдвигает яйцеклад — активный отказ" : "активного отказа нет"}`, r.p.oe] };
    },
    explain(sc, base, sim) {
      const items = [], g = base.groupMean, P = (r) => r.p.acc;
      const add = (dp, text) => items.push({ dp, text });
      const songOn = !!sc.playback_ipi || (sc.male_species !== "none" && sc.male_wings && sc.song_amount > 0);
      const ipi = FlySim.songIpi(sc);
      if (sc.deaf) {
        add(P(base) - P(sim({ ...sc, deaf: false })), `Самка глухая: нейроны Джонстонова органа не слышат песню, детекторы vpoEN молчат (${nf(g.vpoEN)}).`);
      } else if (songOn) {
        const near = Math.abs(ipi - 35) <= 5, src = sc.playback_ipi ? "Песня из динамика" : "Песня самца";
        add(P(base) - P(sim({ ...sc, male_wings: false, playback_ipi: null })), near
          ? `${src} с интервалом ${ipi} мс совпадает с ритмом D. melanogaster: детекторы vpoEN активны (${nf(g.vpoEN)}) и возбуждают vpoDN.`
          : `${src} с интервалом ${ipi} мс не похожа на песню своего вида (≈35 мс): vpoEN отвечают слабо (${nf(g.vpoEN)}).`);
      } else {
        add(P(base) - P(sim({ ...sc, male_wings: true, playback_ipi: null, song_amount: 1 })), `Самец не поёт: без песни vpoEN не возбуждаются (${nf(g.vpoEN)}), и сильного сигнала «свой» нет.`);
      }
      if (sc.male_species !== "none" && sc.male_cva > 0) {
        add(P(base) - P(sim({ ...sc, male_cva: 0 })), sc.or67d_mutant
          ? "Феромон cVA есть, но у самки нет рецептора Or67d: остаётся только слабый путь через Or65a (DL3)."
          : `Феромон самца cVA → обонятельные нейроны Or67d (клубочек DA1) → pCd (${nf(g.pCd)}) и pC1.`);
      }
      if (sc.mated) {
        add(P(base) - P(sim({ ...sc, mated: false })), sc.sp_null_male
          ? `Самка спаривалась, но без полового пептида: нейроны SAG остались активны (${nf(g.SAG)}).`
          : `Самка спаривалась ${nf(sc.days_since_mating, sc.days_since_mating % 1 ? 1 : 0)} сут назад: половой пептид подавил нейроны SAG (${nf(g.SAG)}), поэтому pC1 слабее (${nf(g.pC1)}), а vpoDN хуже открывают путь.`);
      } else {
        add(P(base) - P(sim({ ...sc, mated: true, days_since_mating: 1 })), `Самка — девственница: нейроны SAG активны (${nf(g.SAG)}) и поддерживают pC1 (${nf(g.pC1)}), центр «желания».`);
      }
      if (sc.age_h < 72 || sc.lk_mutant) {
        add(P(base) - P(sim({ ...sc, age_h: 96, lk_mutant: false })), sc.age_h < 72
          ? `Возраст ${ageFmt(sc.age_h)}: самка ещё созревает; гормоны (экдизон → лейкокинин) тормозят pC1.${sc.lk_mutant ? " Без лейкокинина торможение слабее." : ""}`
          : "Мутация по лейкокинину не важна для зрелой самки.");
      }
      if ((sc.silence || []).length || (sc.activate || []).length) add(P(base) - P(sim({ ...sc, silence: [], activate: [] })), optoText(this, sc));
      return items;
    },
    pathEnds(sc, r) {
      const songOn = !sc.deaf && (!!sc.playback_ipi || (sc.male_wings && sc.song_amount > 0));
      return [songOn ? "JO" : sc.male_cva > 0 && !sc.or67d_mutant ? "ORN_cVA" : "SAG", r.p.acc >= 0.5 || r.p.oe < 0.5 ? "vpoDN" : "DNp13"];
    },
    readoutName: { accept: "принятие", oe: "яйцеклад" },
  };

  // =====================================================================================
  // Самец
  // =====================================================================================
  const TARGET_NAMES = [["virgin", "Девственница"], ["mated", "Спарившаяся самка"], ["sim", "Самка D. simulans"], ["male", "Самец"], ["none", "Никого"]];
  const MALE = {
    key: "male",
    subtitle: "Нейросеть на настоящей проводке нервной системы самца дрозофилы решает, ухаживать ли ему",
    tag: "самец · MaleCNS v1.0",
    view: "three",
    statement: "Это нервная система самца, который решает, ухаживать ли.",
    lede: "Мозг и брюшная нервная цепочка из коннектома MaleCNS: от вкусовых клеток на лапках до нейронов, задающих ритм песни крыльями.",
    pins: [["GRN_F", "Лапки · вкус", "--mint", "l"], ["LC10a", "Зрение", "--sky", "r"], ["mAL", "mAL", "--pink", "l"], ["P1", "P1", "--lemon", "r"], ["pIP10", "pIP10 · песня", "--lime", "l"], ["song", "Ритм песни", "--lime", "r"], ["ORN_cVA", "Обоняние", "--sky", "l"]],
    presetDefault: "m_virgin",
    groupsShown: [
      ["GRN_F", "Вкус: феромон самки"], ["GRN_M", "Вкус: феромон самца"], ["ORN_cVA", "Обоняние cVA"], ["LC10a", "Зрение LC10a"],
      ["vAB3", "vAB3"], ["PPN1", "PPN1"], ["mAL", "mAL (торм.)"], ["aSP", "aSP-f/g"], ["P1", "P1 → ухаживать"], ["pIP10", "pIP10 → петь"], ["song", "Генератор песни"],
    ],
    trace: [["P1", "P1", "--s1"], ["mAL", "mAL", "--s2"], ["pIP10", "pIP10", "--s3"], ["song", "генератор песни", "--s4"]],
    opto: [["P1", "P1"], ["pIP10", "pIP10"], ["song", "Генератор песни"], ["vAB3", "vAB3"], ["PPN1", "PPN1"], ["mAL", "mAL"], ["aSP", "aSP-f/g"], ["LC10a", "LC10a"]],
    optoOnlyOn: [],
    alias: { AN05B102a: "PPN1", AN09B017e: "vAB3", AN09B017f: "vAB3", AN09B017g: "vAB3" },
    defaults: { target: "virgin", hd: null, t7: null, cva: null, motion: null, dark: false, or67d_mutant: false, ppk23_mutant: false,
      gr32a_mutant: false, satiety: 0, opto: {} },
    cue(ui, k) { return ui[k] !== null && ui[k] !== undefined ? ui[k] : FlySim.TARGETS[ui.target][k]; },
    sections() {
      const cue = (k) => (u) => this.cue(u, k);
      return [
        { title: "Цель", small: "кого встретил самец", fields: [
          { type: "seg", id: "target", label: "Кто рядом", options: TARGET_NAMES, onSet: (u) => { u.hd = u.t7 = u.cva = u.motion = null; } },
          { type: "range", id: "hd", label: "Феромон самки 7,11-HD", min: 0, max: 1.5, step: 0.05, fmt: (v) => nf(v, 2), get: cue("hd") },
          { type: "range", id: "t7", label: "7-трикозен (запах самцов)", min: 0, max: 1.5, step: 0.05, fmt: (v) => nf(v, 2), get: cue("t7") },
          { type: "range", id: "cva", label: "cVA (метка другого самца)", min: 0, max: 1.5, step: 0.05, fmt: (v) => nf(v, 2), get: cue("cva") },
          { type: "range", id: "motion", label: "Движение цели", min: 0, max: 1.5, step: 0.05, fmt: (v) => nf(v, 2), get: cue("motion") },
          { type: "check", id: "dark", label: "Темнота: зрение не работает" },
        ] },
        { title: "Самец", small: "решает, ухаживать ли", fields: [
          { type: "range", id: "satiety", label: "Пресыщение после спариваний", min: 0, max: 1, step: 0.05, fmt: (v) => nf(v, 2) },
          { type: "check", id: "or67d_mutant", label: "Мутант Or67d: не чует cVA" },
          { type: "check", id: "ppk23_mutant", label: "Мутант ppk23: лапки не чувствуют феромоны" },
          { type: "check", id: "gr32a_mutant", label: "Мутант Gr32a: хуже чувствует 7-трикозен" },
        ] },
      ];
    },
    toScenario(ui) {
      const sc = { target: ui.target, hd: ui.hd, t7: ui.t7, cva: ui.cva, motion: ui.motion, dark: ui.dark,
        or67d_mutant: ui.or67d_mutant, ppk23_mutant: ui.ppk23_mutant, gr32a_mutant: ui.gr32a_mutant, satiety: ui.satiety, silence: [], activate: [] };
      for (const [g, v] of Object.entries(ui.opto)) { if (v === "off") sc.silence.push(g); if (v === "on") sc.activate.push(g); }
      return sc;
    },
    fromScenario(sc) {
      const ui = clone(this.defaults);
      for (const k of Object.keys(ui)) if (k in sc && sc[k] !== undefined) ui[k] = sc[k];
      ui.opto = {};
      for (const g of sc.silence || []) ui.opto[g] = "off";
      for (const g of sc.activate || []) ui.opto[g] = "on";
      return ui;
    },
    verdict(r) {
      const p = r.p.court;
      const cls = p >= 0.5 ? "yes" : p <= 0.25 ? "no" : "mid";
      return { p, cls, word: { yes: "Будет ухаживать", no: "Не станет ухаживать", mid: "Колеблется" }[cls],
        sub: `индекс ухаживания — доля времени, которую самец тратит на ухаживание (по активности P1: ${nf(r.groupMean.P1)})`,
        second: [`Песня крыльями: ${r.p.song >= 0.5 ? "поёт" : "молчит"}`, r.p.song] };
    },
    explain(sc, base, sim) {
      const items = [], g = base.groupMean, P = (r) => r.p.court;
      const add = (dp, text) => items.push({ dp, text });
      const c = FlySim.targetCues(sc);
      if (c.hd > 0) add(P(base) - P(sim({ ...sc, hd: 0 })), sc.ppk23_mutant
        ? "Феромон самки есть, но без канала ppk23 вкусовые клетки лапок его не чувствуют."
        : `Вкус феромона самки 7,11-HD на лапках → F-клетки → vAB3 (${nf(g.vAB3)}) и PPN1 (${nf(g.PPN1)}) → P1 (${nf(g.P1)}).`);
      if (c.t7 > 0) add(P(base) - P(sim({ ...sc, t7: 0 })), sc.ppk23_mutant
        ? "7-трикозен на цели не ощущается: у мутанта ppk23 молчат и M-клетки."
        : `7-трикозен (запах самцов) → M-клетки ног → тормозные нейроны mAL (${nf(g.mAL)}) гасят P1.${sc.gr32a_mutant ? " Без Gr32a этот сигнал слабее." : ""}`);
      if (c.cva > 0) add(P(base) - P(sim({ ...sc, cva: 0 })), sc.or67d_mutant
        ? "На цели есть cVA, но у самца нет рецептора Or67d — метку соперника он не чует."
        : `Запах cVA — метка другого самца → Or67d → нейроны aSP (${nf(g.aSP)}): «здесь уже был самец».`);
      if (c.motion > 0) add(P(base) - P(sim({ ...sc, dark: !sc.dark })), sc.dark
        ? `Темно: зрительные нейроны LC10a молчат (${nf(g.LC10a)}), самцу труднее преследовать цель.`
        : `Движущаяся цель → зрительные нейроны LC10a (${nf(g.LC10a)}) помогают преследовать и запускать ухаживание.`);
      if (sc.satiety > 0) add(P(base) - P(sim({ ...sc, satiety: 0 })), "Самец недавно спаривался: дофаминовый сигнал мотивации на P1 (рецептор DopR2) ослаблен.");
      if (c.hd + c.t7 + c.cva + c.motion === 0 && !(sc.activate || []).length) add(0, "Рядом нет другой мухи: P1 не получают ни вкусового, ни зрительного сигнала.");
      if ((sc.silence || []).length || (sc.activate || []).length) add(P(base) - P(sim({ ...sc, silence: [], activate: [] })), optoText(this, sc));
      return items;
    },
    pathEnds(sc, r) {
      const c = FlySim.targetCues(sc);
      const src = c.hd > 0 && !sc.ppk23_mutant ? "GRN_F" : c.motion > 0 && !sc.dark ? "LC10a" : c.t7 > 0 && !sc.ppk23_mutant ? "GRN_M" : "ORN_cVA";
      return [src, r.p.song >= 0.5 ? "song" : "P1"];
    },
    readoutName: { court: "ухаживание", song: "песня" },
  };
  const CFGS = { female: FEMALE, male: MALE };

  // =====================================================================================
  // Состояние
  // =====================================================================================
  const S = { sex: MODELS.female ? "female" : "male", cfg: null, model: null, ui: null, preset: "", res: null, items: [], path: [],
    frame: 0, playing: !window.matchMedia("(prefers-reduced-motion: reduce)").matches, highlight: null };
  const sim = (sc, rec) => FlySim.simulate(S.model, sc, { record: rec });

  // ---------- поля управления ----------
  const fields = [];
  function makeField(f) {
    const ui = S.ui;
    if (f.type === "range") {
      const out = el("output", { for: f.id });
      const inp = el("input", { type: "range", id: f.id, min: f.min, max: f.max, step: f.step });
      const val = () => (f.get ? f.get(S.ui) : S.ui[f.id]);
      const sync = () => { const v = val(); out.textContent = f.fmt(v); inp.value = v; };
      inp.addEventListener("input", () => { S.ui[f.id] = +inp.value; S.preset = ""; sync(); changed(); });
      sync();
      const w = el("div", { class: "field" }, el("label", { for: f.id }, f.label, out), inp);
      w._sync = sync; w._show = f.show;
      return w;
    }
    if (f.type === "check") {
      const inp = el("input", { type: "checkbox", id: f.id });
      inp.checked = !!ui[f.id];
      inp.addEventListener("change", () => { S.ui[f.id] = inp.checked; S.preset = ""; changed(); });
      const w = el("label", { class: "check" }, inp, el("span", {}, f.label));
      w._sync = () => { inp.checked = !!S.ui[f.id]; }; w._show = f.show;
      return w;
    }
    const seg = el("div", { class: "seg", role: "group", "aria-label": f.label });
    const btns = f.options.map(([v, t]) => {
      const b = el("button", { type: "button" }, t);
      b.addEventListener("click", () => { S.ui[f.id] = v; if (f.onSet) f.onSet(S.ui); S.preset = ""; fields.forEach((x) => x._sync && x._sync()); changed(); });
      seg.append(b);
      return [v, b];
    });
    const sync = () => btns.forEach(([v, b]) => b.setAttribute("aria-pressed", String(S.ui[f.id] === v)));
    sync();
    const w = el("div", { class: "field" }, el("span", { class: "lbl" }, f.label), seg);
    w._sync = sync; w._show = f.show;
    return w;
  }

  function buildControls() {
    const box = $("#controls");
    box.innerHTML = "";
    const model = S.model, cfg = S.cfg;
    const sel = el("select", { id: "preset", "aria-label": "Опыт из статьи" });
    sel.append(el("option", { value: "" }, "Свои условия"));
    for (const b of model.dataset.behavior) sel.append(el("option", { value: b.id }, (b.split === "test" ? "[тест] " : "") + b.title_ru));
    sel.addEventListener("change", () => {
      const b = model.dataset.behavior.find((x) => x.id === sel.value);
      S.preset = sel.value;
      if (b) S.ui = cfg.fromScenario(b.scenario);
      fields.forEach((f) => f._sync && f._sync());
      changed();
    });
    box.append(el("section", { class: "block" }, el("h2", {}, "Опыт из статьи →", el("small", {}, `${model.dataset.behavior.length} опытов`)),
      sel, el("div", { class: "preset-note", id: "preset-note" })));
    fields.length = 0;
    for (const sec of cfg.sections()) {
      const card = el("section", { class: "block" }, el("h2", {}, sec.title, el("small", {}, sec.small)));
      for (const f of sec.fields) { const w = makeField(f); fields.push(w); card.append(w); }
      box.append(card);
    }
    const opto = el("div", { class: "opto" });
    for (const [g, name] of cfg.opto) {
      const seg = el("div", { class: "seg", role: "group", "aria-label": name });
      const btns = [["off", "выкл"], ["", "норма"], ["on", "вкл"]].map(([v, t]) => {
        const b = el("button", { type: "button", "data-v": v || "norm", disabled: cfg.optoOnlyOn.includes(g) && v === "off" }, t);
        b.addEventListener("click", () => { if (v) S.ui.opto[g] = v; else delete S.ui.opto[g]; S.preset = ""; sync(); changed(); });
        seg.append(b);
        return [v, b];
      });
      const sync = () => btns.forEach(([v, b]) => b.setAttribute("aria-pressed", String((S.ui.opto[g] || "") === v)));
      sync();
      const row = el("div", { class: "opto-row" }, el("span", { class: "nm", title: (model.groupInfo[g] || {}).role_ru || "" }, name), seg);
      row._sync = sync;
      fields.push(row);
      opto.append(row);
    }
    box.append(el("section", { class: "block" }, el("h2", {}, "Оптогенетика", el("small", {}, "выкл / вкл группы")), opto));
    syncVisibility();
  }
  function syncVisibility() {
    for (const f of fields) if (f._show) f.hidden = !f._show(S.ui);
    const sel = $("#preset");
    if (sel) sel.value = S.preset;
    const b = S.model.dataset.behavior.find((x) => x.id === S.preset);
    const note = $("#preset-note");
    if (!note) return;
    if (b) {
      const tg = Object.keys(S.model.spec.targets).filter((k) => b[k]).map((k) => `${S.cfg.readoutName[k]}: ${pct(b[k][0])}–${pct(b[k][1])}`);
      note.textContent = `${b.evidence_ru} Цель из статьи — ${tg.join(", ")}.`;
    } else note.textContent = "Меняйте условия ниже — модель пересчитает решение.";
  }
  let timer = 0;
  function changed() { syncVisibility(); clearTimeout(timer); timer = setTimeout(run, 60); }

  // ---------- путь сигнала ----------
  function strongestPath(srcGroup, dstGroup, act) {
    const m = S.model, N = m.N;
    const cost = new Float64Array(N).fill(Infinity), prev = new Int32Array(N).fill(-1), done = new Uint8Array(N);
    const src = m.groupMembers[srcGroup] || [], dst = new Set(m.groupMembers[dstGroup] || []);
    for (const i of src) cost[i] = -Math.log(Math.max(1e-4, act[i]));
    for (let it = 0; it < N; it++) {
      let u = -1, best = Infinity;
      for (let i = 0; i < N; i++) if (!done[i] && cost[i] < best) { best = cost[i]; u = i; }
      if (u < 0) break;
      done[u] = 1;
      if (dst.has(u)) { const path = []; for (let v = u; v >= 0; v = prev[v]) path.unshift(v); return path; }
      for (const e of m.outEdges[u]) {
        const w = m.eW[e];
        if (w <= 0) continue;
        const v = m.ePost[e];
        const c = cost[u] - Math.log(Math.max(1e-6, w * act[u])) + 0.3;
        if (c < cost[v]) { cost[v] = c; prev[v] = u; }
      }
    }
    return [];
  }

  function run() {
    const sc = S.cfg.toScenario(S.ui);
    const res = sim(sc, true);
    S.res = res;
    S.items = S.cfg.explain(sc, res, (x) => sim(x, false)).sort((a, b) => Math.abs(b.dp) - Math.abs(a.dp));
    const [srcG, dstG] = S.cfg.pathEnds(sc, res);
    S.path = strongestPath(srcG, dstG, res.neuronMean);
    viewer && viewer.setPath(new Set(S.path));
    renderResult();
    if (!S.playing) showFrame(S.frame);
  }

  // ---------- вывод решения ----------
  function renderResult() {
    const r = S.res, m = S.model, cfg = S.cfg;
    const v = cfg.verdict(r);
    const icon = { yes: "✓", no: "✕", mid: "≈" }[v.cls];
    const box = $("#verdict");
    box.className = "verdict " + v.cls;
    box.innerHTML = `<div class="pct">${pct(v.p)}</div><div class="word"><span class="sq" aria-hidden="true"></span><span>${icon} ${v.word}</span></div><div class="sub">${v.sub}</div>`;
    $("#meter").style.width = pct(v.p);
    $("#meter").style.background = css(v.cls === "yes" ? "--lime" : v.cls === "no" ? "--pink" : "--lemon");
    $("#oe").innerHTML = `<span>${v.second[0]}</span><b>${pct(v.second[1])}</b>`;
    $("#model-tag").textContent = cfg.tag;

    const why = $("#why");
    why.innerHTML = "";
    for (const it of S.items) {
      const c = Math.abs(it.dp) < 0.03 ? "neu" : it.dp > 0 ? "pos" : "neg";
      why.append(el("li", {}, el("span", { class: "d " + c, title: "изменение вероятности, процентные пункты" }, pp(it.dp)), el("span", {}, it.text)));
    }
    const path = $("#path");
    path.innerHTML = "";
    if (S.path.length) {
      const names = [];
      for (const i of S.path) { const t = cfg.alias[m.neurons.type[i]] || m.neurons.type[i]; if (names[names.length - 1] !== t) names.push(t); }
      path.append(el("span", { class: "lab" }, "Путь сигнала:"));
      names.forEach((t, k) => { if (k) path.append(el("span", { class: "a" }, "→")); path.append(el("span", { class: "n" }, t)); });
    }
    const bars = $("#bars");
    bars.innerHTML = "";
    for (const [g, name] of cfg.groupsShown) {
      const a = r.groupMean[g] || 0;
      bars.append(el("div", { class: "bar", title: (m.groupInfo[g] || {}).role_ru || "" },
        el("span", { class: "nm" }, name), el("span", { class: "tr" }, el("i", { style: `width:${Math.min(100, a * 100)}%` })), el("span", { class: "v" }, nf(a))));
    }
    renderLegend();
    renderTrace();
    renderBand();
  }
  function renderBand() {
    const m = S.model, rep = m.report;
    const tr = rep.behavior.filter((b) => b.split === "train"), te = rep.behavior.filter((b) => b.split === "test");
    const st = (num, label) => el("div", { class: "st" }, el("b", {}, num), el("span", {}, label));
    const box = $("#band");
    box.innerHTML = "";
    box.append(
      st(m.stats.neurons.toLocaleString("ru-RU"), "настоящих нейронов в сети"),
      st(m.stats.edges.toLocaleString("ru-RU"), "синаптических связей"),
      st(m.stats.synapses.toLocaleString("ru-RU"), "синапсов из электронной микроскопии"),
      st(`${tr.filter((b) => b.ok).length}/${tr.length}`, "опытов обучения совпали со статьями"),
      st(`${te.filter((b) => b.ok).length}/${te.length}`, "скрытых опытов предсказано верно"));
  }

  // ---------- 3D ----------
  let viewer = null;
  const tip = $("#tip");
  function onHover(h) {
    if (!h) { tip.hidden = true; return; }
    const m = S.model, i = h.index, g = m.neurons.group[i];
    const a = S.res ? (S.playing ? S.res.trace[S.frame * m.N + i] : S.res.neuronMean[i]) : 0;
    tip.innerHTML = `<b>${esc(m.neurons.type[i])}</b> · ${esc((m.groupInfo[g] || {}).name_ru || g)}<br>медиатор: ${esc(m.neurons.nt[i])} · активность <span class="mono">${nf(a)}</span><br><span style="opacity:.7">ID ${m.neurons.rootId[i]}</span>`;
    tip.style.left = h.x + "px"; tip.style.top = h.y + "px"; tip.hidden = false;
  }
  function buildViewer() {
    if (viewer) { viewer.destroy(); viewer = null; }
    const old = $("#brain");
    const cv = old.cloneNode(false);
    old.replaceWith(cv);
    try {
      viewer = FlyBrain3D.create(cv, { model: S.model, skeleton: SKELS[S.sex] || null, onHover, view: S.cfg.view, onDraw: (pr) => placePins(pr),
        offset: (wide) => (S.sex === "male" ? (wide ? [0.04, -0.12] : [0, -0.2]) : (wide ? [0.22, -0.06] : [0, -0.22])),
        dist: S.sex === "male" ? 2.95 : 2.15 });
    } catch (e) {
      $("#hud").textContent = "3D недоступно: " + e.message;
      return;
    }
    $("#hud").innerHTML = `<b>${esc(S.model.source.split(" (")[0])}</b>` + (!viewer.hasSkeletons ? "<br>скелеты не загружены — показаны сомы" : "");
    $("#statement").textContent = S.cfg.statement;
    $("#lede").textContent = S.cfg.lede;
    buildPins();
  }

  // подписи-«булавки» групп нейронов поверх 3D (как метки на карте)
  let pinEls = [];
  function buildPins() {
    const layer = $("#pins");
    layer.innerHTML = "";
    const side = S.model.neurons.side;
    pinEls = S.cfg.pins.filter(([g]) => (S.model.groupMembers[g] || []).length).map(([g, text, col, sd]) => {
      const e = el("div", { class: "pin" }, el("i", { style: `background:${css(col)}` }, "+"), el("span", { style: `background:${css(col)}` }, text));
      layer.append(e);
      const all = S.model.groupMembers[g];
      const one = all.filter((i) => (side[i] || "").toLowerCase().startsWith(sd));   // одна сторона мозга
      return { g, e, idx: one.length ? one : all, w: 22 + text.length * 7 };
    });
  }
  function placePins(project) {
    const placed = [];
    for (const p of pinEls) {
      const xy = project(p.idx);
      if (!xy) { p.e.hidden = true; continue; }
      let y = xy.y;
      for (let k = 0; k < 8; k++) {      // раздвигаем подписи, чтобы не налезали друг на друга
        const hit = placed.find((q) => Math.abs(q.y - y) < 17 && xy.x < q.x + q.w && xy.x + p.w > q.x);
        if (!hit) break;
        y = hit.y + 18;
      }
      placed.push({ x: xy.x, y, w: p.w });
      p.e.hidden = false;
      p.e.style.left = xy.x + "px"; p.e.style.top = y + "px";
    }
  }
  function pinActivity(act) {
    const m = S.model;
    for (const p of pinEls) {
      const mem = m.groupMembers[p.g];
      let a = 0; for (const i of mem) a += act[i];
      p.e.style.opacity = (0.72 + 0.28 * Math.min(1, (a / mem.length) * 1.6)).toFixed(2);
    }
  }
  $("#cmap-swatch").style.background = FlyBrain3D.cmapCss;
  document.querySelectorAll("[data-view]").forEach((b) => b.addEventListener("click", () => viewer && viewer.setView(b.dataset.view)));

  function renderLegend() {
    const box = $("#legend");
    box.innerHTML = "";
    for (const [g, name] of S.cfg.groupsShown) {
      const a = S.res.groupMean[g] || 0;
      const c = FlyBrain3D.cmap(Math.min(1, a * 1.2));
      const b = el("button", { type: "button", "aria-pressed": String(S.highlight === g), title: (S.model.groupInfo[g] || {}).role_ru || "" },
        el("span", { class: "dot", style: `background:rgb(${c.map(Math.round).join(",")})` }), name);
      b.addEventListener("click", () => {
        S.highlight = S.highlight === g ? null : g;
        viewer && viewer.setHighlight(S.highlight ? new Set(S.model.groupMembers[g]) : null);
        renderLegend();
      });
      box.append(b);
    }
  }

  // ---------- анимация ----------
  const T = (MODELS.female || MODELS.male).config.T_STEPS, DT = (MODELS.female || MODELS.male).config.DT_MS;
  const scrub = $("#scrub");
  scrub.max = T - 1;
  function showFrame(f) {
    S.frame = f;
    const r = S.res;
    if (!r) return;
    const N = S.model.N;
    const act = S.playing || f > 0 ? r.trace.subarray(f * N, (f + 1) * N) : r.neuronMean;
    viewer && viewer.setActivity(act);
    pinActivity(act);
    scrub.value = f;
    $("#tlabel").textContent = nf((f * DT) / 1000, 2) + " с";
    const ph = $("#playhead");
    if (ph) ph.setAttribute("transform", `translate(${traceX(f)},0)`);
  }
  let last = 0;
  function tick(ts) {
    if (S.playing && S.res && !$("#tab-sim").hidden && ts - last > 1000 / 30) { last = ts; showFrame((S.frame + 1) % T); }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
  const playBtn = $("#play");
  function setPlaying(p) { S.playing = p; playBtn.textContent = p ? "❚❚" : "▶"; playBtn.setAttribute("aria-label", p ? "Пауза" : "Воспроизвести"); }
  playBtn.addEventListener("click", () => setPlaying(!S.playing));
  scrub.addEventListener("input", () => { setPlaying(false); showFrame(+scrub.value); });
  setPlaying(S.playing);

  // ---------- график динамики ----------
  let TW = 360;
  const TH = 180, PL = 30, PR = 8, PT = 22, PB = 22;
  const traceX = (f) => PL + (f / (T - 1)) * (TW - PL - PR);
  function renderTrace() {
    const r = S.res, m = S.model, N = m.N, C = r.C;
    const box = $("#trace");
    TW = Math.max(300, Math.round(box.clientWidth || 360));
    box.innerHTML = "";
    const s = svg("svg", { viewBox: `0 0 ${TW} ${TH}`, role: "img", "aria-label": "Активность групп нейронов во времени" });
    const y = (v) => PT + (1 - v) * (TH - PT - PB);
    const R0 = m.config.READOUT_FROM;
    s.append(svg("rect", { x: traceX(R0), y: PT, width: traceX(T - 1) - traceX(R0), height: TH - PT - PB, fill: css("--grid"), opacity: 0.6 }));
    const lab = svg("text", { x: traceX(R0) + 4, y: PT + 10 }); lab.textContent = "окно решения"; s.append(lab);
    for (const v of [0, 0.5, 1]) {
      s.append(svg("line", { x1: PL, x2: TW - PR, y1: y(v), y2: y(v), stroke: css("--grid"), "stroke-width": 1 }));
      const t = svg("text", { x: PL - 5, y: y(v) + 3, "text-anchor": "end" }); t.textContent = nf(v, v % 1 ? 1 : 0); s.append(t);
    }
    for (const sec of [0, 0.5, 1, 1.5]) {
      const f = Math.min(T - 1, Math.round(sec * 1000 / DT));
      const t = svg("text", { x: traceX(f), y: TH - 6, "text-anchor": sec === 0 ? "start" : sec === 1.5 ? "end" : "middle" });
      t.textContent = nf(sec, sec % 1 ? 1 : 0) + " с"; s.append(t);
    }
    const keys = $("#trace-keys");
    keys.innerHTML = "";
    if (S.sex === "female") {   // импульсы и синусоида песни самца
      for (let k = 0; k < T; k++) {
        if (r.u[k * C] > 0) s.append(svg("line", { x1: traceX(k), x2: traceX(k), y1: 6, y2: 14, stroke: css("--ink-2"), "stroke-width": 1 }));
        else if (r.u[k * C + 1] > 0) s.append(svg("line", { x1: traceX(k), x2: traceX(k + 1), y1: 10, y2: 10, stroke: css("--ink-3"), "stroke-width": 1 }));
      }
      keys.append(el("span", {}, el("i", { style: `background:${css("--ink-2")};height:8px;width:2px` }), "песня: импульсы | синус"));
    } else {                    // момент появления цели
      const t0 = svg("text", { x: traceX(m.config.STIM_ON) + 4, y: 12 }); t0.textContent = "цель рядом →"; s.append(t0);
      s.append(svg("line", { x1: traceX(m.config.STIM_ON), x2: traceX(m.config.STIM_ON), y1: 4, y2: TH - PB, stroke: css("--ink-3"), "stroke-width": 1 }));
    }
    const series = S.cfg.trace.map(([g, name, col]) => {
      const mem = m.groupMembers[g];
      const vals = new Float32Array(T);
      for (let f = 0; f < T; f++) { let a = 0; for (const i of mem) a += r.trace[f * N + i]; vals[f] = a / mem.length; }
      let d = "";
      for (let f = 0; f < T; f++) d += (f ? "L" : "M") + traceX(f).toFixed(1) + " " + y(vals[f]).toFixed(1);
      s.append(svg("path", { d, fill: "none", stroke: css(col), "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));
      keys.append(el("span", {}, el("i", { style: `background:${css(col)}` }), name));
      return { name, vals };
    });
    const ph = svg("g", { id: "playhead", transform: `translate(${traceX(S.frame)},0)` });
    ph.append(svg("line", { x1: 0, x2: 0, y1: PT, y2: TH - PB, stroke: css("--ink"), "stroke-width": 1 }));
    s.append(ph);
    const hit = svg("rect", { x: PL, y: PT, width: TW - PL - PR, height: TH - PT - PB, fill: "transparent" });
    const vt = $("#vtip");
    hit.addEventListener("pointermove", (e) => {
      const b = s.getBoundingClientRect();
      const fx = ((e.clientX - b.left) / b.width) * TW;
      const f = Math.max(0, Math.min(T - 1, Math.round(((fx - PL) / (TW - PL - PR)) * (T - 1))));
      vt.innerHTML = `<b>${nf((f * DT) / 1000, 2)} с</b><br>` + series.map((q) => `${q.name}: ${nf(q.vals[f])}`).join("<br>");
      vt.style.left = e.clientX + 14 + "px"; vt.style.top = e.clientY - 10 + "px"; vt.hidden = false;
      if (!S.playing) showFrame(f);
    });
    hit.addEventListener("pointerleave", () => { vt.hidden = true; });
    s.append(hit);
    box.append(s);
  }
  let rz = 0;
  window.addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(() => S.res && renderTrace(), 150); });

  // ---------- проверка совпадения с PyTorch ----------
  function parity(model) {
    let worst = 0;
    for (const tv of model.testVectors) {
      const r = FlySim.simulate(model, tv.scenario, {});
      for (const [k, v] of Object.entries(tv.p)) worst = Math.max(worst, Math.abs(r.p[k] - v));
      for (const [g, v] of Object.entries(tv.groupMean)) worst = Math.max(worst, Math.abs(r.groupMean[g] - v));
    }
    return worst;
  }

  // ---------- страница «Литература» ----------
  const ruDate = (iso) => iso.split("-").reverse().join(".");
  function renderRefs() {
    const R = window.FLY_REFS;
    const page = $("#refs-page");
    page.innerHTML = "";
    if (!R) { page.append(el("p", { class: "err" }, "Нет файла web/data/references.js. Запустите pipeline/08_check_references.py.")); return; }
    page.append(el("div", { class: "prose" },
      el("h2", {}, "Литература"),
      el("p", {}, `Статьи и данные, на которых построены и обучены модели. Каждая ссылка проверена ${ruDate(R.checked)}: ${R.method_ru}`)));
    const link = (url, text) => el("a", { href: url, target: "_blank", rel: "noopener" }, text);
    const checked = (c) => el("span", { class: "chk" }, `✓ проверено ${ruDate(c.date)}`);
    const sections = [["connectome", "Коннектомы"], ["female", "Выбор самки"], ["both", "Обе модели"], ["male", "Ухаживание самца"]];
    let n = 0;
    for (const [sec, name] of sections) {
      const items = R.papers.filter((p) => p.section === sec);
      if (!items.length) continue;
      const ol = el("ol", { class: "reflist", start: n + 1 });
      for (const p of items) {
        n++;
        const authors = p.authors.join(", ") + (p.n_authors > 3 ? " и др." : "");
        const where = `${p.journal}${p.volume ? ", " + p.volume : ""}${p.pages ? ": " + p.pages.replace("-", "–") : ""}`;
        ol.append(el("li", {},
          el("div", { class: "cite" }, `${authors} (${p.year}). `, link(p.url, p.title), `. ${where}.`),
          el("div", { class: "meta" }, `DOI ${p.doi}`, el("span", {}, " · "), `для модели: ${p.used_for}`, el("span", {}, " · "), checked(p.check))));
      }
      page.append(el("section", { class: "refsec" }, el("h3", {}, name), ol));
    }
    const ul = el("ul", { class: "reflist data" });
    for (const d of R.data) ul.append(el("li", {}, el("div", { class: "cite" }, link(d.url, d.name)),
      el("div", { class: "meta" }, d.url.replace(/^https:\/\//, ""), el("span", {}, " · "), checked(d.check))));
    page.append(el("section", { class: "refsec" }, el("h3", {}, "Данные"), ul));
  }

  // ---------- вкладки и переключение пола ----------
  const tabs = [["t-sim", "tab-sim"], ["t-refs", "tab-refs"]];
  let curTab = "t-sim";
  function openTab(id) {
    if (!tabs.some(([t]) => t === id)) id = "t-sim";     // старые вкладки «Обучение» и «О проекте» удалены
    curTab = id;
    for (const [t, p] of tabs) { const on = t === id; $("#" + t).setAttribute("aria-selected", String(on)); $("#" + p).hidden = !on; }
    if (id === "t-refs") renderRefs();
    try { localStorage.setItem("fly-tab", id); } catch (e) { /* хранилище недоступно */ }
  }
  tabs.forEach(([t]) => $("#" + t).addEventListener("click", () => openTab(t)));

  function setSex(sex) {
    if (!MODELS[sex]) return;
    S.sex = sex; S.cfg = CFGS[sex]; S.model = prep(MODELS[sex]); S.highlight = null; S.frame = 0;
    S.preset = S.cfg.presetDefault;
    const b = S.model.dataset.behavior.find((x) => x.id === S.preset);
    S.ui = b ? S.cfg.fromScenario(b.scenario) : clone(S.cfg.defaults);
    document.querySelectorAll("[data-sex]").forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.sex === sex)));
    document.querySelector('meta[name="description"]')?.setAttribute("content", S.cfg.subtitle);
    buildViewer();
    buildControls();
    run();
    try { localStorage.setItem("fly-sex", sex); } catch (e) { /* хранилище недоступно */ }
  }
  document.querySelectorAll("[data-sex]").forEach((b) => {
    if (MODELS[b.dataset.sex]) { b.disabled = false; b.removeAttribute("title"); }
    b.addEventListener("click", () => setSex(b.dataset.sex));
  });

  // ---------- запуск ----------
  let saved = {};
  try { saved = { tab: localStorage.getItem("fly-tab"), sex: localStorage.getItem("fly-sex") }; } catch (e) { /* хранилище недоступно */ }
  const hash = location.hash.replace("#", "");
  const startSex = hash === "male" && MODELS.male ? "male" : saved.sex && MODELS[saved.sex] ? saved.sex : S.sex;
  setSex(startSex);
  openTab(hash === "refs" ? "t-refs" : saved.tab || "t-sim");
  window.__fly = { S, sim, parity };
})();
