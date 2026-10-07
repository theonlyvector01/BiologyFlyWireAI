"""Шаг 5б. 3D-скелеты нейронов цепи самца из MaleCNS (формат neuroglancer precomputed, по файлу на нейрон).

Скачиваются только нейроны цепи (~1400 файлов), упрощаются как у самки.
Облако — сомы всех нейронов MaleCNS: видны и мозг, и брюшная нервная цепочка.
Результат: data/processed/male_skeletons.npz (+ уточнённые координаты нейронов без сомы).
"""
import concurrent.futures as cf
import struct
import urllib.request

import numpy as np
import pandas as pd

from config import RAW_MALE, PROCESSED, MALECNS_SKELETONS
from skeleton_utils import simplify_tree, tree_from_edges

BRAIN_CLOUD_POINTS = 26000


def fetch(body_id: int):
    url = f"{MALECNS_SKELETONS}/{body_id}"
    for attempt in range(4):
        try:
            data = urllib.request.urlopen(url, timeout=60).read()
            nv, ne = struct.unpack_from("<II", data, 0)
            v = np.frombuffer(data, "<f4", nv * 3, 8).reshape(nv, 3).astype(np.float64)
            e = np.frombuffer(data, "<u4", ne * 2, 8 + nv * 12).reshape(ne, 2).astype(np.int64)
            return body_id, v, e
        except Exception as ex:  # noqa: BLE001 — повторяем при сетевых сбоях
            err = ex
    print("не удалось скачать", body_id, err)
    return body_id, None, None


def main() -> None:
    circ = np.load(PROCESSED / "male_circuit.npz", allow_pickle=True)
    ids = [int(x) for x in circ["root_id"]]
    pos = circ["pos"].copy()
    xyz_all, par_all, nidx_all = [], [], []
    offset = 0
    with cf.ThreadPoolExecutor(16) as ex:
        results = list(ex.map(fetch, ids))
    for k, (bid, v, e) in enumerate(results):
        if v is None or len(v) == 0:
            continue
        v_um = v / 1000.0                                    # нм -> мкм
        root = 0
        if np.isfinite(pos[k]).all():
            root = int(np.argmin(np.linalg.norm(v_um - pos[k], axis=1)))
        else:
            pos[k] = v_um.mean(0)                            # нет сомы (сенсорный нейрон): центр скелета
        par = tree_from_edges(len(v_um), e, root)
        sx, sp = simplify_tree(v_um, par, min_step=9.0, min_twig=45.0)   # нейроны самца крупнее
        xyz_all.append(sx); par_all.append(np.where(sp >= 0, sp + offset, -1)); nidx_all.append(np.full(len(sx), k, np.int32))
        offset += len(sx)
    xyz = np.concatenate(xyz_all); par = np.concatenate(par_all); nidx = np.concatenate(nidx_all)
    print("скелетов:", len(xyz_all), "узлов после упрощения:", len(xyz))

    ann = pd.read_feather(RAW_MALE / "body-annotations-male-cns-v1.0-minconf-0.5.feather", columns=["somaLocation", "status"])
    locs = np.array([l for l in ann.somaLocation.values if l is not None and len(l) == 3], np.float64) * 8 / 1000
    rng = np.random.default_rng(0)
    cloud = locs[rng.choice(len(locs), min(BRAIN_CLOUD_POINTS, len(locs)), replace=False)].astype(np.float32)
    np.savez_compressed(PROCESSED / "male_skeletons.npz", xyz=xyz, parent=par, neuron=nidx, cloud=cloud, pos=pos.astype(np.float32))
    print("сохранено", PROCESSED / "male_skeletons.npz")


if __name__ == "__main__":
    main()
