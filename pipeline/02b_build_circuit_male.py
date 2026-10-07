"""Шаг 2б. Цепь ухаживания самца из коннектома MaleCNS (мозг + брюшная нервная цепочка, ~166 000 нейронов).

Тот же алгоритм «потока сигнала», что и для самки (02_build_circuit.py):
  входы  — вкусовые клетки ног (феромоны самки и самца), обоняние cVA (Or67d), зрение LC10a;
  выходы — P1 (решение ухаживать) и pIP10 (команда песни).
Скачивание: python pipeline/01_download.py --male
Результат: data/processed/male_circuit.npz и male_circuit_summary.json
"""
import json

import numpy as np
import pandas as pd
import scipy.sparse as sp

from config import RAW_MALE, PROCESSED, MIN_SYN, MALE_GROUPS, MALE_SENSORY_GROUPS

TOP_K_CENTRAL = 450
DECAY = 0.7
HOPS = 5
MAX_PER_SENSORY_TYPE = 120   # чтобы сенсорные нейроны не заняли всю сеть


def group_of(cell_type: str) -> str:
    for key, cond, *_ in MALE_GROUPS:
        if cond(cell_type):
            return key
    return "other"


def main() -> None:
    ann = pd.read_feather(RAW_MALE / "body-annotations-male-cns-v1.0-minconf-0.5.feather",
                          columns=["bodyId", "type", "status", "superclass", "somaLocation", "somaSide", "rootSide", "fruDsx"])
    ann = ann[ann.status == "Traced"].reset_index(drop=True)
    ann["type"] = ann["type"].fillna("")
    ann["group"] = ann["type"].map(group_of)
    nt = pd.read_feather(RAW_MALE / "body-neurotransmitters-male-cns-v1.0.feather", columns=["body", "consensus_nt", "predicted_nt"])
    nt = nt.set_index("body")
    ann["nt"] = ann.bodyId.map(nt.consensus_nt).fillna(ann.bodyId.map(nt.predicted_nt)).fillna("acetylcholine")

    ids = ann.bodyId.values
    index = pd.Series(np.arange(len(ids)), index=ids)
    n_all = len(ids)

    w = pd.read_feather(RAW_MALE / "connectome-weights-male-cns-v1.0-minconf-0.5-traced-only.feather",
                        columns=["body_pre", "body_post", "weight"])
    w = w[w.weight >= MIN_SYN]
    w = w[w.body_pre.isin(index.index) & w.body_post.isin(index.index)]
    pre = index[w.body_pre.values].values
    post = index[w.body_post.values].values
    syn = w.weight.values.astype(np.float64)
    print("связей (>= 5 синапсов):", len(syn))
    tot_in = np.bincount(post, weights=syn, minlength=n_all)
    A = sp.csr_matrix((syn / np.maximum(tot_in[post], 1), (post, pre)), shape=(n_all, n_all))

    group = ann.group.values
    sources = np.isin(group, list(MALE_SENSORY_GROUPS)).astype(float)
    outputs = np.isin(group, ["P1", "pIP10"]).astype(float)
    f = np.zeros(n_all); x = sources.copy()
    b = np.zeros(n_all); y = outputs.copy()
    for t in range(HOPS):
        x = A @ x; f += x * DECAY ** t
        y = A.T @ y; b += y * DECAY ** t
    score = f * b

    key = group != "other"
    sensory = np.isin(group, list(MALE_SENSORY_GROUPS))
    keep = key & ~sensory
    # сенсорные: только влияющие на выходы, не больше MAX_PER_SENSORY_TYPE лучших каждого типа
    types = ann["type"].values
    for t in np.unique(types[sensory]):
        m = np.where((types == t) & (b > 0))[0]
        keep[m[np.argsort(-b[m])[:MAX_PER_SENSORY_TYPE]]] = True
    central = np.where(~key)[0]
    keep[central[np.argsort(-score[central])[:TOP_K_CENTRAL]]] = True

    sel = np.where(keep)[0]
    local = -np.ones(n_all, int); local[sel] = np.arange(len(sel))
    m = (local[pre] >= 0) & (local[post] >= 0)
    deg = np.bincount(local[pre[m]], minlength=len(sel)) + np.bincount(local[post[m]], minlength=len(sel))
    sel = sel[(deg > 0) | key[sel]]
    local = -np.ones(n_all, int); local[sel] = np.arange(len(sel))
    m = (local[pre] >= 0) & (local[post] >= 0)
    epre, epost, esyn = local[pre[m]], local[post[m]], syn[m]

    sub = ann.iloc[sel].reset_index(drop=True)
    ntv = sub.nt.values.copy()
    grp = sub.group.values
    ntv[np.isin(grp, list(MALE_SENSORY_GROUPS))] = "acetylcholine"   # сенсорные нейроны холинергические
    sign = np.where(np.isin(ntv, ["gaba", "glutamate"]), -1.0, 1.0)
    weight = sign[epre] * esyn / np.maximum(tot_in[sel][epost], 1)

    tname = np.array([t if t else f"untyped_{g}" for t, g in zip(sub["type"].values, grp)])
    tlist, type_idx = np.unique(tname, return_inverse=True)
    pos = np.full((len(sel), 3), np.nan, np.float32)
    for i, loc in enumerate(sub.somaLocation.values):
        if loc is not None and len(loc) == 3:
            pos[i] = np.asarray(loc, np.float32) * 8 / 1000          # воксель 8 нм -> мкм
    side = sub.somaSide.fillna(sub.rootSide).fillna("").astype(str).values

    np.savez_compressed(
        PROCESSED / "male_circuit.npz",
        root_id=sub.bodyId.values.astype(np.int64), group=grp.astype(str), cell_type=tname,
        types=tlist, type_idx=type_idx.astype(np.int32), nt=ntv.astype(str), sign=sign.astype(np.float32),
        modulatory=np.isin(ntv, ["dopamine", "serotonin", "octopamine"]), side=side, pos=pos,
        edge_pre=epre.astype(np.int32), edge_post=epost.astype(np.int32),
        edge_syn=esyn.astype(np.int32), edge_w=weight.astype(np.float32), score=score[sel].astype(np.float32),
    )
    summary = {
        "neurons": int(len(sel)), "edges": int(len(epre)), "synapses": int(esyn.sum()), "types": int(len(tlist)),
        "groups": {g: int((grp == g).sum()) for g in sorted(set(grp))},
        "nt": {k: int(v) for k, v in pd.Series(ntv).value_counts().items()},
    }
    df = pd.DataFrame({"pre": tname[epre], "post": tname[epost], "syn": esyn, "w": weight, "gpost": grp[epost]})
    for target in ["P1", "pIP10", "vAB3", "mAL"]:
        top_in = (df[df.gpost == target].groupby("pre").agg(syn=("syn", "sum"), w=("w", "sum"))
                  .sort_values("syn", ascending=False).head(8))
        summary[f"top_inputs_{target}"] = {k: {"syn": int(r.syn), "sign": "+" if r.w > 0 else "-"} for k, r in top_in.iterrows()}
    (PROCESSED / "male_circuit_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
