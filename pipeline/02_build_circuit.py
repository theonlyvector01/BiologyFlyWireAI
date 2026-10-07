"""Шаг 2. Выделяем из полного коннектома FlyWire (≈139 000 нейронов) цепь выбора партнёра самкой.

Алгоритм («поток сигнала»):
  1. Матрица A[post, pre] = доля входных синапсов нейрона post, приходящих от pre (связи >= 5 синапсов).
  2. Прямой поток f: насколько сильно сенсорные входы (слух JO, обоняние cVA, SAG) влияют на нейрон
     за 1..5 синаптических шагов.
  3. Обратный поток b: насколько нейрон влияет на выходные нейроны решения (vpoDN, DNp13).
  4. Оценка s = f * b. Берём лучшие нейроны + все нейроны ключевых типов из литературы.

Результат: data/processed/female_circuit.npz и female_circuit_summary.json
"""
import json

import numpy as np
import pandas as pd
import scipy.sparse as sp

from config import RAW, PROCESSED, MIN_SYN, FEMALE_GROUPS, SENSORY_GROUPS

TOP_K_CENTRAL = 450   # сколько «промежуточных» нейронов добавить по оценке потока
DECAY = 0.7           # затухание влияния на каждом синаптическом шаге
HOPS = 5


def load_edges() -> pd.DataFrame:
    path = PROCESSED / "edges_all.parquet"
    if not path.exists():
        print("Агрегирую связи по парам нейронов (один раз)...")
        c = pd.read_feather(RAW / "proofread_connections_783.feather",
                            columns=["pre_pt_root_id", "post_pt_root_id", "syn_count"])
        e = c.groupby(["pre_pt_root_id", "post_pt_root_id"], sort=False)["syn_count"].sum().reset_index()
        e.columns = ["pre", "post", "syn"]
        PROCESSED.mkdir(parents=True, exist_ok=True)
        e.to_parquet(path)
    return pd.read_parquet(path)


def group_of(cell_type: str) -> str:
    for key, cond, *_ in FEMALE_GROUPS:
        if cond(cell_type):
            return key
    return "other"


def main() -> None:
    ann = pd.read_csv(RAW / "neuron_annotations.tsv", sep="\t", low_memory=False)
    ann["cell_type"] = ann["cell_type"].fillna("")
    ann["group"] = ann["cell_type"].map(group_of)
    ids = ann["root_id"].values
    index = {r: i for i, r in enumerate(ids)}
    n_all = len(ids)

    e = load_edges()
    e = e[(e.syn >= MIN_SYN) & e.pre.isin(index) & e.post.isin(index)]
    pre = e.pre.map(index).values
    post = e.post.map(index).values
    syn = e.syn.values.astype(np.float64)
    tot_in = np.bincount(post, weights=syn, minlength=n_all)
    A = sp.csr_matrix((syn / np.maximum(tot_in[post], 1), (post, pre)), shape=(n_all, n_all))

    group = ann["group"].values
    sources = np.isin(group, list(SENSORY_GROUPS)).astype(float)
    outputs = np.isin(group, ["vpoDN", "DNp13"]).astype(float)

    f = np.zeros(n_all); x = sources.copy()
    b = np.zeros(n_all); y = outputs.copy()
    for t in range(HOPS):
        x = A @ x; f += x * DECAY ** t
        y = A.T @ y; b += y * DECAY ** t
    score = f * b

    key = group != "other"
    sensory = np.isin(group, list(SENSORY_GROUPS))
    # сенсорные нейроны берём, только если они реально влияют на выходы
    keep = (key & ~sensory) | (sensory & (b > 0))
    central = np.where(~key)[0]
    top = central[np.argsort(-score[central])[:TOP_K_CENTRAL]]
    keep[top] = True
    sel = np.where(keep)[0]

    # связи внутри цепи
    in_sel = np.zeros(n_all, bool); in_sel[sel] = True
    m = in_sel[pre] & in_sel[post]
    local = -np.ones(n_all, int); local[sel] = np.arange(len(sel))
    epre, epost, esyn = local[pre[m]], local[post[m]], syn[m]

    # убираем изолированные нейроны (кроме ключевых)
    deg = np.bincount(epre, minlength=len(sel)) + np.bincount(epost, minlength=len(sel))
    ok = (deg > 0) | key[sel]
    sel = sel[ok]
    local = -np.ones(n_all, int); local[sel] = np.arange(len(sel))
    in_sel = np.zeros(n_all, bool); in_sel[sel] = True
    m = in_sel[pre] & in_sel[post]
    epre, epost, esyn = local[pre[m]], local[post[m]], syn[m]

    sub = ann.iloc[sel].reset_index(drop=True)
    # медиатор -> знак синапса. Сенсорные нейроны холинергические (предсказание NT для них ненадёжно).
    nt = sub["top_nt"].fillna("acetylcholine").values.copy()
    grp = sub["group"].values
    nt[np.isin(grp, list(SENSORY_GROUPS))] = "acetylcholine"
    sign = np.where(np.isin(nt, ["gaba", "glutamate"]), -1.0, 1.0)
    modulatory = np.isin(nt, ["dopamine", "serotonin", "octopamine"])

    # веса: знак * (синапсы / все входные синапсы постсинаптического нейрона во всём мозге)
    weight = sign[epre] * esyn / np.maximum(tot_in[sel][epost], 1)

    # типы нейронов (для общих параметров обучения)
    tname = sub["cell_type"].where(sub["cell_type"] != "", sub["hemibrain_type"].fillna("")).values
    tname = np.array([t if t else f"untyped_{g}" for t, g in zip(tname, grp)])
    types, type_idx = np.unique(tname, return_inverse=True)

    # координаты: сома (если есть), иначе опорная точка; FlyWire voxel 4x4x40 нм -> мкм
    sx = sub["soma_x"].fillna(sub["pos_x"]).values * 4 / 1000
    sy = sub["soma_y"].fillna(sub["pos_y"]).values * 4 / 1000
    sz = sub["soma_z"].fillna(sub["pos_z"]).values * 40 / 1000
    pos = np.stack([sx, sy, sz], 1).astype(np.float32)

    np.savez_compressed(
        PROCESSED / "female_circuit.npz",
        root_id=sub["root_id"].values.astype(np.int64), group=grp.astype(str), cell_type=tname,
        types=types, type_idx=type_idx.astype(np.int32), nt=nt.astype(str), sign=sign.astype(np.float32),
        modulatory=modulatory, side=sub["side"].fillna("").values.astype(str), pos=pos,
        edge_pre=epre.astype(np.int32), edge_post=epost.astype(np.int32),
        edge_syn=esyn.astype(np.int32), edge_w=weight.astype(np.float32),
        score=score[sel].astype(np.float32),
    )

    # краткий отчёт
    summary = {
        "neurons": int(len(sel)), "edges": int(len(epre)), "synapses": int(esyn.sum()),
        "types": int(len(types)),
        "groups": {g: int((grp == g).sum()) for g in sorted(set(grp))},
        "nt": {k: int(v) for k, v in pd.Series(nt).value_counts().items()},
    }
    df = pd.DataFrame({"pre": tname[epre], "post": tname[epost], "syn": esyn, "w": weight})
    for target in ["DNp37", "DNp13", "vpoEN", "pC1a"]:
        top_in = (df[df.post == target].groupby("pre").agg(syn=("syn", "sum"), w=("w", "sum"))
                  .sort_values("syn", ascending=False).head(8))
        summary[f"top_inputs_{target}"] = {k: {"syn": int(r.syn), "sign": "+" if r.w > 0 else "-"}
                                           for k, r in top_in.iterrows()}
    (PROCESSED / "female_circuit_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
