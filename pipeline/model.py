"""Коннектомная нейросеть (connectome-constrained RNN) мозга дрозофилы — общая для самки и самца.

Каждый узел сети — реальный нейрон коннектома (FlyWire для самки, MaleCNS для самца),
каждая связь — реальная синаптическая связь. Знак связи задаётся медиатором (ацетилхолин +,
ГАМК/глутамат −), сила — числом синапсов. Обучаются только «физиологические» параметры:
  * усиление выхода (gpre) и входа (gpost) клеточного типа и класса связи (тип -> тип),
  * порог (bias) и постоянная времени (tau) типа,
  * чувствительность сенсорных нейронов к стимулам и считывание решения.
Сеть не может «выдумать» новые связи — она обязана решать задачу проводкой настоящего мозга.

Динамика (метод Эйлера, шаг DT_MS):
  tau_i * dx_i/dt = -x_i + sum_j W_ij r_j + b_i + I_i(t),     r_i = tanh(softplus(5 x_i) / 5)
"""
from __future__ import annotations

import math

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from config import DT_MS, T_STEPS, STIM_ON, READOUT_FROM

# =======================================================================================
# Сценарий -> входные сигналы. ЭТОТ КОД ПОВТОРЁН 1:1 В web/js/sim.js.
# =======================================================================================


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


# ----------------------------- самка ---------------------------------------------------
SPECIES_IPI = {"mel": 35.0, "sim": 48.0}   # мс; Bennet-Clark & Ewing 1969; Wang et al. 2021
FEMALE_CHANNELS = ["pulse", "sine", "cva_da1", "cva_dl3", "sag", "immature"]
BOUT_MS = 600.0      # цикл песни: 400 мс импульсной песни + 200 мс синусоидальной
PULSE_PART_MS = 400.0
FEMALE_DEFAULT = dict(
    age_h=96.0, mated=False, days_since_mating=1.0, sp_null_male=False,
    deaf=False, or67d_mutant=False, lk_mutant=False,
    male_species="mel", male_wings=True, male_cva=1.0, song_amount=1.0, custom_ipi=None,
    playback_ipi=None, silence=(), activate=(),
)
DEFAULT_SCENARIO = FEMALE_DEFAULT   # совместимость


def immaturity(age_h: float, lk_mutant: bool) -> float:
    """Гормональный сигнал незрелости самки (модельное допущение по Chen et al., PNAS 2025):
    до ~20 ч самка не спаривается вовсе (общая незрелость), а примерно в 20–60 ч рецептивность
    дополнительно подавляет нейропептид лейкокинин (LK) через рецептор LKR в нейронах pC1."""
    other = sigmoid((22.0 - age_h) / 3.0)
    lk = 0.0 if lk_mutant else sigmoid((age_h - 10.0) / 4.0) * sigmoid((54.0 - age_h) / 6.0)
    return other + lk


def sag_drive(sc: dict) -> float:
    """Активность восходящих нейронов SAG. У девственницы высокая. Половой пептид (SP) самца
    после спаривания выключает SPSN->SAG (Feng et al. 2014); эффект SP постепенно слабеет
    за ~неделю (Peng et al. 2005). Если у самца не было SP (SP0), SAG почти не подавлены."""
    if not sc["mated"]:
        return 1.0
    if sc["sp_null_male"]:
        return 0.95
    return 1.0 - 0.95 * math.exp(-sc["days_since_mating"] / 4.0)


def encode_female(sc: dict, rng: np.random.Generator | None = None) -> np.ndarray:
    sc = {**FEMALE_DEFAULT, **sc}
    T = T_STEPS
    u = np.zeros((T, len(FEMALE_CHANNELS)), np.float32)
    jit = (lambda s: rng.normal(0, s)) if rng is not None else (lambda s: 0.0)
    scale = (lambda lo, hi: rng.uniform(lo, hi)) if rng is not None else (lambda lo, hi: 1.0)
    phase = rng.uniform(0, BOUT_MS) if rng is not None else 0.0

    male_present = sc["male_species"] != "none"
    natural_song = male_present and sc["male_wings"] and sc["song_amount"] > 0
    if sc["playback_ipi"]:
        ipi, amp, bouts = float(sc["playback_ipi"]), 1.0, False      # динамик: только импульсы
    elif natural_song:
        ipi = float(sc["custom_ipi"] or SPECIES_IPI.get(sc["male_species"], 35.0))
        amp, bouts = float(sc["song_amount"]) * scale(0.85, 1.15), True
    else:
        ipi, amp, bouts = 0.0, 0.0, False
    if sc["deaf"]:
        amp = 0.0

    if amp > 0:
        t_ms = STIM_ON * DT_MS + (rng.uniform(0, ipi) if rng is not None else 0.0)
        end_ms = T * DT_MS
        while t_ms < end_ms:
            in_pulse_part = (not bouts) or (((t_ms + phase) % BOUT_MS) < PULSE_PART_MS)
            if in_pulse_part:
                k = int(t_ms // DT_MS)
                if k < T:
                    u[k, 0] += amp
            t_ms += max(ipi + jit(1.5), 5.0)
        if bouts:  # синусоидальная песня в оставшейся части цикла
            for k in range(STIM_ON, T):
                if ((k * DT_MS + phase) % BOUT_MS) >= PULSE_PART_MS:
                    u[k, 1] = amp

    cva = float(sc["male_cva"]) * scale(0.8, 1.2) if male_present else 0.0
    u[STIM_ON:, 2] = 0.0 if sc["or67d_mutant"] else cva
    u[STIM_ON:, 3] = cva
    u[:, 4] = sag_drive(sc)
    u[:, 5] = immaturity(float(sc["age_h"]), bool(sc["lk_mutant"]))
    return u


# ----------------------------- самец ---------------------------------------------------
MALE_CHANNELS = ["fem_pher", "male_pher", "cva", "visual", "satiety"]
VIS_PERIOD_MS = 400.0
# Феромоны цели (относительные уровни): 7,11-HD — феромон самки D. melanogaster;
# 7-T — углеводород самцов (и самок D. simulans); cVA — феромон самца, переносится на самку при спаривании.
TARGETS = {
    "virgin": dict(hd=1.0, t7=0.1, cva=0.0, motion=1.0),
    "mated": dict(hd=1.0, t7=0.6, cva=1.0, motion=1.0),
    "sim": dict(hd=0.0, t7=0.8, cva=0.0, motion=1.0),
    "male": dict(hd=0.0, t7=1.0, cva=1.0, motion=1.0),
    "none": dict(hd=0.0, t7=0.0, cva=0.0, motion=0.0),
}
MALE_DEFAULT = dict(
    target="virgin", hd=None, t7=None, cva=None, motion=None, dark=False,
    or67d_mutant=False, ppk23_mutant=False, gr32a_mutant=False, satiety=0.0, silence=(), activate=(),
)


def target_cues(sc: dict) -> dict:
    sc = {**MALE_DEFAULT, **sc}
    cues = dict(TARGETS[sc["target"]])
    for k in ("hd", "t7", "cva", "motion"):
        if sc[k] is not None:
            cues[k] = float(sc[k])
    return cues


def encode_male(sc: dict, rng: np.random.Generator | None = None) -> np.ndarray:
    sc = {**MALE_DEFAULT, **sc}
    T = T_STEPS
    u = np.zeros((T, len(MALE_CHANNELS)), np.float32)
    scale = (lambda: rng.uniform(0.85, 1.15)) if rng is not None else (lambda: 1.0)
    phase = rng.uniform(0, VIS_PERIOD_MS) if rng is not None else 0.0
    c = target_cues(sc)
    fem = c["hd"] * (0.0 if sc["ppk23_mutant"] else 1.0) * scale()
    mal = c["t7"] * (0.0 if sc["ppk23_mutant"] else 1.0) * (0.4 if sc["gr32a_mutant"] else 1.0) * scale()
    cva = c["cva"] * (0.0 if sc["or67d_mutant"] else 1.0) * scale()
    mot = c["motion"] * (0.0 if sc["dark"] else 1.0) * scale()
    for k in range(STIM_ON, T):
        u[k, 0] = fem
        u[k, 1] = mal
        u[k, 2] = cva
        u[k, 3] = mot * (0.7 + 0.3 * math.sin(2 * math.pi * (k * DT_MS + phase) / VIS_PERIOD_MS))
    u[:, 4] = float(sc["satiety"])
    return u


# ----------------------------- описание полов ------------------------------------------
SPECS = {
    "female": dict(
        channels=FEMALE_CHANNELS, encode=encode_female,
        input_sign=[1, 1, 1, 1, 1, -1],                       # незрелость тормозит pC1
        readouts=[("acc", "vpoDN"), ("oe", "DNp13")],         # принятие / выдвижение яйцеклада
        targets={"accept": "acc", "oe": "oe"},
        virtual={"LK": (5, 1.5)},                              # «включить LK» = +1.5 к каналу незрелости
        sensory=["JO", "ORN_cVA", "SAG"],
    ),
    "male": dict(
        channels=MALE_CHANNELS, encode=encode_male,
        input_sign=[1, 1, 1, 1, -1],                          # пресыщение (дофамин -> DopR2 в P1) тормозит
        readouts=[("court", "P1"), ("song", "pIP10")],
        targets={"court": "court", "song": "song"},
        virtual={},
        sensory=["GRN_F", "GRN_M", "ORN_cVA", "LC10a"],
    ),
}


def encode_scenario(sc: dict, rng: np.random.Generator | None = None, sex: str = "female") -> np.ndarray:
    """Массив (T_STEPS, число каналов). rng=None -> детерминированный стимул (как в браузере)."""
    return SPECS[sex]["encode"](sc, rng)


def input_init(sex: str, circ: dict):
    """Какие нейроны получают какой канал (маска) и начальная чувствительность."""
    g = np.asarray(circ["group"])
    ct = np.asarray(circ["cell_type"])
    N = len(g)
    C = len(SPECS[sex]["channels"])
    mask = np.zeros((N, C), np.float32)
    w0 = np.zeros((N, C), np.float32)
    if sex == "female":
        jo_a = np.array([c.startswith("JO-A") for c in ct])
        jo_b = np.array([c.startswith("JO-B") for c in ct])
        mask[jo_a | jo_b, 0] = 1
        mask[jo_a | jo_b, 1] = 1
        mask[ct == "ORN_DA1", 2] = 1
        mask[ct == "ORN_DL3", 3] = 1
        mask[g == "SAG", 4] = 1
        mask[g == "pC1", 5] = 1                               # LKR в pC1 (Chen et al. 2025)
        # JO-A сильнее отвечают на импульсы, JO-B — на низкочастотную синусоиду
        w0[jo_a, 0], w0[jo_a, 1] = 4.0, 0.5
        w0[jo_b, 0], w0[jo_b, 1] = 2.0, 1.5
        w0[:, 2:6] = 1.0
    else:
        mask[g == "GRN_F", 0] = 1
        mask[g == "GRN_M", 1] = 1
        mask[g == "ORN_cVA", 2] = 1
        mask[g == "LC10a", 3] = 1
        mask[g == "P1", 4] = 1                                # дофамин -> DopR2 в P1 (Zhang et al. 2016)
        w0[:] = 1.5
    return mask, w0


# =======================================================================================
class FlyCircuit(nn.Module):
    def __init__(self, circ: dict, sex: str = "female"):
        super().__init__()
        self.sex = sex
        spec = SPECS[sex]
        self.spec = spec
        self.N = N = len(circ["group"])
        self.groups = list(circ["group"])
        tidx = np.asarray(circ["type_idx"])
        self.type_idx = torch.as_tensor(tidx, dtype=torch.long)
        n_types = int(tidx.max()) + 1
        g = np.asarray(circ["group"])
        nt = np.asarray(circ["nt"])

        # --- синапсы коннектома (фиксированы: кто с кем связан и знак связи) -------------
        epost = np.asarray(circ["edge_post"], np.int64)
        epre = np.asarray(circ["edge_pre"], np.int64)
        w0 = np.asarray(circ["edge_w"], np.float32)
        self.register_buffer("e_post", torch.as_tensor(epost))
        self.register_buffer("e_pre", torch.as_tensor(epre))
        self.register_buffer("e_w0", torch.as_tensor(w0))
        # класс связи = (тип пресинаптического, тип постсинаптического нейрона)
        pair_key = tidx[epre].astype(np.int64) * n_types + tidx[epost]
        pairs, pair_idx = np.unique(pair_key, return_inverse=True)
        self.register_buffer("e_pair", torch.as_tensor(pair_idx, dtype=torch.long))
        self.n_pairs = len(pairs)

        # --- обучаемые параметры (на клеточный тип и на класс связи) ----------------------
        absw = np.zeros(N, np.float32)
        np.add.at(absw, epost, np.abs(w0))
        tmean = np.array([max(absw[tidx == t].mean(), 0.05) for t in range(n_types)], np.float32)
        inhibitory_t = np.array([np.isin(nt[tidx == t], ["gaba", "glutamate"]).mean() > 0.5 for t in range(n_types)])
        sensory = np.isin(g, spec["sensory"])
        sensory_t = np.array([sensory[tidx == t].any() for t in range(n_types)])
        self.log_gpost = nn.Parameter(torch.as_tensor(np.log(2.0 / tmean)))
        self.log_gpre = nn.Parameter(torch.as_tensor(np.where(inhibitory_t, np.log(0.5), 0.0), dtype=torch.float32))
        self.log_gpair = nn.Parameter(torch.zeros(self.n_pairs))
        self.bias = nn.Parameter(torch.as_tensor(np.where(sensory_t, -0.3, 0.0), dtype=torch.float32))
        tau0 = np.where(sensory_t, 8.0, 25.0)
        self.tau_raw = nn.Parameter(torch.as_tensor(np.log(np.expm1(tau0 - 4.0)), dtype=torch.float32))
        self.register_buffer("init_gpost", self.log_gpost.detach().clone())
        self.register_buffer("init_gpre", self.log_gpre.detach().clone())

        # --- входы ----------------------------------------------------------------------
        mask, win0 = input_init(sex, circ)
        self.register_buffer("in_mask", torch.as_tensor(mask))
        self.in_raw = nn.Parameter(torch.as_tensor(np.log(np.expm1(np.maximum(win0, 0.05)))))
        self.register_buffer("in_sign", torch.tensor(spec["input_sign"], dtype=torch.float32))

        # --- группы для считывания и манипуляций --------------------------------------
        self.group_names = sorted(set(g)) + list(spec["virtual"].keys())
        gm = np.zeros((len(self.group_names), N), np.float32)
        for k, name in enumerate(self.group_names):
            gm[k] = (g == name)
        self.register_buffer("group_mat", torch.as_tensor(gm))

        ro = {}
        for name, _ in spec["readouts"]:
            ro[f"{name}_k"] = nn.Parameter(torch.tensor(8.0))
            ro[f"{name}_th"] = nn.Parameter(torch.tensor(0.3 if name != "oe" else 0.4))
        if sex == "female":
            ro["oe_mated"] = nn.Parameter(torch.tensor(2.0))
        self.readout = nn.ParameterDict(ro)
        self.noise = 0.0

    # ------------------------------------------------------------------------------
    def tau(self):
        return 4.0 + F.softplus(self.tau_raw)

    def edge_weights(self) -> torch.Tensor:
        """Эффективный вес каждой синаптической связи: знак и число синапсов из коннектома,
        умноженные на обученные усиления типов и класса связи."""
        t = self.type_idx
        log_g = self.log_gpost[t[self.e_post]] + self.log_gpre[t[self.e_pre]] + self.log_gpair[self.e_pair]
        return self.e_w0 * torch.exp(log_g)

    def dense_W(self) -> torch.Tensor:
        W = torch.zeros(self.N, self.N)
        return W.index_put((self.e_post, self.e_pre), self.edge_weights(), accumulate=True)

    def neuron_params(self):
        t = self.type_idx
        return self.bias[t], self.tau()[t], F.softplus(self.in_raw) * self.in_mask * self.in_sign

    def group_index(self, name: str) -> int:
        return self.group_names.index(name)

    def forward(self, u: torch.Tensor, silence: torch.Tensor, activate: torch.Tensor, chan_add: torch.Tensor,
                record: bool = False):
        """u: (B, T, C) входы; silence/activate: (B, N) маски; chan_add: (B, C) добавка к каналам
        (виртуальные группы, например «включить LK»). Возвращает dict: mean (B, G), p{имя: (B,)}."""
        B, T, C = u.shape
        bias, tau, win = self.neuron_params()
        W = self.dense_W()                                              # (N, N), при ~1000 нейронах быстрее разреженной
        alpha = (DT_MS / tau)[:, None]                                  # (N, 1)
        u = u + chan_add[:, None, :]
        ext = (torch.einsum("btc,nc->tnb", u, win) + (bias[:, None] + activate.T * 2.0)[None]).unbind(0)  # T x (N, B)
        keep = (1.0 - silence).T                                        # (N, B)
        x = torch.zeros(self.N, B)
        r = torch.zeros(self.N, B)
        acc = torch.zeros(self.N, B)
        trace = []
        for t in range(T):
            drive = W @ r + ext[t]                                      # синаптический + внешний вход
            if self.noise > 0:
                drive = drive + self.noise * torch.randn_like(drive)
            x = x + alpha * (drive - x)
            r = act_fn(x) * keep
            if t >= READOUT_FROM:
                acc = acc + r
            if record:
                trace.append(r.T)
        mean_n = (acc / (T - READOUT_FROM)).T                          # (B, N)
        gsum = self.group_mat.sum(1).clamp(min=1)
        mean_g = (mean_n @ self.group_mat.T) / gsum                    # (B, G)
        ro = self.readout
        p = {}
        for name, grp in self.spec["readouts"]:
            z = ro[f"{name}_k"] * (mean_g[:, self.group_index(grp)] - ro[f"{name}_th"])
            if name == "oe":   # выдвижение яйцеклада отпугивает только у спарившейся самки (SAG подавлены)
                mated_gate = (u[:, 0, 4] < 0.9).float()
                z = z + ro["oe_mated"] * (2 * mated_gate - 1)
            p[name] = torch.sigmoid(z)
        out = {"mean": mean_g, "mean_neuron": mean_n, "p": p}
        if record:
            out["trace"] = torch.stack(trace, 1)
        return out


def act_fn(x: torch.Tensor) -> torch.Tensor:
    """Частота разрядов 0..1: почти ноль при отрицательном входе, насыщение при сильном."""
    return torch.tanh(F.softplus(5.0 * x) / 5.0)


def load_circuit(path) -> dict:
    d = np.load(path, allow_pickle=True)
    return {k: d[k] for k in d.files}
