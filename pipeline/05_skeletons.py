"""Шаг 5. 3D-форма нейронов цепи для визуализации в браузере.

Из скелетов FlyWire (Schlegel et al. 2024, Zenodo 10877326, ~5.4 ГБ) берём только нейроны нашей цепи
и упрощаем каждый (skeleton_utils.simplify_tree): отрезаем мелкие веточки и прореживаем узлы.
Плюс «облако» сом всех ~139 000 нейронов мозга — оно рисует силуэт мозга.

Результат (маленький, хранится в репозитории): data/processed/female_skeletons.npz
"""
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from config import RAW, PROCESSED
from skeleton_utils import simplify_tree

BRAIN_CLOUD_POINTS = 24000


def simplify(df: pd.DataFrame, soma_node) -> tuple[np.ndarray, np.ndarray]:
    nid = df.node_id.values
    xyz = np.stack([df.x.values, df.y.values, df.z.values], 1).astype(np.float64) / 1000.0  # нм -> мкм
    pos = {n: i for i, n in enumerate(nid)}
    par = np.array([pos.get(p, -1) for p in df.parent_id.values])
    return simplify_tree(xyz, par)


def main() -> None:
    circ = np.load(PROCESSED / "female_circuit.npz", allow_pickle=True)
    ids = set(int(x) for x in circ["root_id"])
    pf = pq.ParquetFile(RAW / "sk_lod1_783_healed_ds2.parquet")
    meta = pf.schema_arrow.metadata or {}
    parts = []
    for batch in pf.iter_batches(batch_size=4_000_000, columns=["node_id", "parent_id", "x", "y", "z", "neuron"]):
        df = batch.to_pandas()
        df = df[df.neuron.isin(ids)]
        if len(df):
            parts.append(df)
    sk = pd.concat(parts)
    print("узлов в скелетах цепи:", len(sk), "нейронов:", sk.neuron.nunique())

    order = {int(r): i for i, r in enumerate(circ["root_id"])}
    xyz_all, par_all, nidx_all = [], [], []
    offset = 0
    for rid, df in sk.groupby("neuron"):
        soma = meta.get(f"{rid}:soma".encode())
        xyz, par = simplify(df, soma)
        xyz_all.append(xyz)
        par_all.append(np.where(par >= 0, par + offset, -1))
        nidx_all.append(np.full(len(xyz), order[int(rid)], np.int32))
        offset += len(xyz)
    xyz = np.concatenate(xyz_all); par = np.concatenate(par_all); nidx = np.concatenate(nidx_all)
    print("после упрощения узлов:", len(xyz))

    ann = pd.read_csv(RAW / "neuron_annotations.tsv", sep="\t", low_memory=False,
                      usecols=["soma_x", "soma_y", "soma_z", "pos_x", "pos_y", "pos_z"])
    cx = ann.soma_x.fillna(ann.pos_x).values * 4 / 1000
    cy = ann.soma_y.fillna(ann.pos_y).values * 4 / 1000
    cz = ann.soma_z.fillna(ann.pos_z).values * 40 / 1000
    cloud = np.stack([cx, cy, cz], 1)
    rng = np.random.default_rng(0)
    cloud = cloud[rng.choice(len(cloud), BRAIN_CLOUD_POINTS, replace=False)].astype(np.float32)

    np.savez_compressed(PROCESSED / "female_skeletons.npz", xyz=xyz, parent=par, neuron=nidx, cloud=cloud)
    print("сохранено", PROCESSED / "female_skeletons.npz")


if __name__ == "__main__":
    main()
