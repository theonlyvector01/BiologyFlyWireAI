"""Шаг 6. Экспорт обученных моделей, цепей, 3D-скелетов и обучающих данных для веб-приложения.

Результат (для каждого пола, если модель обучена):
  web/data/<пол>_model.js      — window.FLY_MODELS.<пол> = {...}  (веса, нейроны, отчёт, датасет)
  web/data/<пол>_skeletons.js  — window.FLY_SKELETONS.<пол> = {...} (3D-форма нейронов, base64)
В модели сохраняются «контрольные векторы» — ответы PyTorch для нескольких сценариев, по которым
веб-приложение проверяет, что браузерная симуляция совпадает с обученной сетью.

Запуск: python pipeline/06_export_web.py [--sex female|male]
"""
import argparse
import base64
import importlib
import json

import numpy as np
import torch

from config import (PROCESSED, LITERATURE, MODELS, WEB, DT_MS, T_STEPS, STIM_ON, READOUT_FROM,
                    FEMALE_GROUPS, MALE_GROUPS)
from model import SPECS

train_mod = importlib.import_module("04_train")

GROUPS = {"female": FEMALE_GROUPS, "male": MALE_GROUPS}
SOURCE_NAME = {
    "female": "FlyWire 783 · мозг самки (Dorkenwald et al. 2024; Schlegel et al. 2024)",
    "male": "MaleCNS v1.0 · мозг и нервная цепочка самца (Berg et al., Cell 2026)",
}


def b64(arr: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(arr).tobytes()).decode()


def r(x, nd=4):
    return [round(float(v), nd) for v in np.asarray(x).ravel()]


def export(sex: str) -> None:
    model = train_mod.load_model(sex)
    model.eval()
    circ = np.load(PROCESSED / f"{sex}_circuit.npz", allow_pickle=True)
    data = json.loads((LITERATURE / f"{sex}_experiments.json").read_text())
    old = json.loads((MODELS / f"{sex}_report.json").read_text())
    rows, prow = train_mod.evaluate(model, data)                  # отчёт в едином формате
    report = {"behavior": rows, "physiology": prow, "history": old.get("history", []),
              "train_seconds": old.get("train_seconds", 0)}
    (MODELS / f"{sex}_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))

    with torch.no_grad():
        bias, tau, win = model.neuron_params()
        ew = model.edge_weights().numpy()
    N = model.N
    groups = [str(x) for x in circ["group"]]
    members = {g: [i for i, x in enumerate(groups) if x == g] for g in model.group_names}

    tests = [b["scenario"] for b in data["behavior"][:8]]
    with torch.no_grad():
        out = train_mod.run(model, tests)
    test_vectors = [{"scenario": s, "p": {k: float(v[i]) for k, v in out["p"].items()},
                     "groupMean": {g: float(out["mean"][i, k]) for k, g in enumerate(model.group_names)}}
                    for i, s in enumerate(tests)]

    info = {k: {"name_ru": name, "role_ru": role} for k, _, name, role in GROUPS[sex]}
    info["other"] = {"name_ru": "Промежуточные нейроны",
                     "role_ru": "Интернейроны, найденные алгоритмом потока сигнала между органами чувств и нейронами решения."}
    if sex == "female":
        info["LK"] = {"name_ru": "Лейкокинин (гормон незрелости)",
                      "role_ru": "Нейропептидный сигнал, тормозящий pC1 у молодых самок (Chen et al., 2025)."}

    pos = circ["pos"]
    sk_path = PROCESSED / f"{sex}_skeletons.npz"
    sk = np.load(sk_path) if sk_path.exists() else None
    if sk is not None and "pos" in sk.files:
        pos = sk["pos"]
    pos = np.nan_to_num(pos, nan=float(np.nanmean(pos)))

    summary = json.loads((PROCESSED / f"{sex}_circuit_summary.json").read_text())
    spec = SPECS[sex]
    obj = {
        "sex": sex,
        "source": SOURCE_NAME[sex],
        "config": {"DT_MS": DT_MS, "T_STEPS": T_STEPS, "STIM_ON": STIM_ON, "READOUT_FROM": READOUT_FROM},
        "spec": {"channels": spec["channels"], "readouts": [list(x) for x in spec["readouts"]],
                 "targets": spec["targets"], "virtual": {k: list(v) for k, v in spec["virtual"].items()}},
        "N": N,
        "nParams": int(sum(p.numel() for p in model.parameters())),
        "groupNames": model.group_names,
        "groupMembers": members,
        "groupInfo": info,
        "neurons": {
            "rootId": [str(x) for x in circ["root_id"]],
            "type": [str(x) for x in circ["cell_type"]],
            "group": groups,
            "nt": [str(x) for x in circ["nt"]],
            "side": [str(x) for x in circ["side"]],
            "pos": r(pos, 1),
        },
        "bias": r(bias), "alpha": r(DT_MS / tau.numpy(), 5), "win": r(win.numpy()),
        "ePre": circ["edge_pre"].tolist(), "ePost": circ["edge_post"].tolist(),
        "eW": r(ew, 5), "eSyn": circ["edge_syn"].tolist(),
        "readout": {k: float(v.detach()) for k, v in model.readout.items()},
        "stats": summary,
        "report": report,
        "dataset": data,
        "testVectors": test_vectors,
    }
    out_dir = WEB / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    js = f"window.FLY_MODELS = window.FLY_MODELS || {{}};\nwindow.FLY_MODELS.{sex} = " + \
         json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + ";\n"
    (out_dir / f"{sex}_model.js").write_text(js)
    print(f"{sex}: модель {len(js) / 1e6:.2f} МБ; обучение {sum(x['ok'] for x in rows if x['split'] == 'train')}/"
          f"{sum(x['split'] == 'train' for x in rows)}, тест {sum(x['ok'] for x in rows if x['split'] == 'test')}/"
          f"{sum(x['split'] == 'test' for x in rows)}, физиология {sum(x['ok'] for x in prow)}/{len(prow)}")

    if sk is not None:
        q = np.round(sk["xyz"] * 10).astype(np.int16)              # 0.1 мкм
        cloud = np.round(sk["cloud"] * 10).astype(np.int16)
        skel = {"scale": 0.1, "nVert": int(len(q)), "xyz": b64(q), "parent": b64(sk["parent"].astype(np.int32)),
                "neuron": b64(sk["neuron"].astype(np.uint16)), "nCloud": int(len(cloud)), "cloud": b64(cloud)}
        js = f"window.FLY_SKELETONS = window.FLY_SKELETONS || {{}};\nwindow.FLY_SKELETONS.{sex} = " + \
             json.dumps(skel, separators=(",", ":")) + ";\n"
        (out_dir / f"{sex}_skeletons.js").write_text(js)
        print(f"{sex}: скелеты {len(js) / 1e6:.2f} МБ")
    else:
        print("Нет", sk_path, "— запустите 05_skeletons.py / 05b_skeletons_male.py")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sex", choices=list(SPECS), help="по умолчанию — все обученные модели")
    args = ap.parse_args()
    for sex in ([args.sex] if args.sex else list(SPECS)):
        if (MODELS / f"{sex}_model.pt").exists():
            export(sex)


if __name__ == "__main__":
    main()
