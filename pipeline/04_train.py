"""Шаг 4. Обучение коннектомной нейросети на опубликованных экспериментах.

Функция потерь состоит из трёх частей:
  1. Поведение: предсказанная доля (например, самок, принявших самца) должна попасть в интервал из статьи.
  2. Физиология: группы нейронов должны отвечать так, как это измерено в опытах
     (например, vpoEN сильнее отвечают на песню 35 мс, чем на 48 мс).
  3. Регуляризация: усиления не должны уходить далеко от исходных —
     основную работу обязана делать настоящая проводка коннектома.

Запуск:  python pipeline/04_train.py --sex female --iters 600
         python pipeline/04_train.py --sex male --iters 600
Результат: models/<пол>_model.pt, models/<пол>_report.json
"""
import argparse
import json
import time

import numpy as np
import torch

from config import PROCESSED, LITERATURE, MODELS
from model import FlyCircuit, encode_scenario, load_circuit, SPECS


def masks_for(model: FlyCircuit, sc: dict):
    C = len(model.spec["channels"])
    sil = torch.zeros(model.N)
    act = torch.zeros(model.N)
    add = torch.zeros(C)
    for g in sc.get("silence", []):
        sil += model.group_mat[model.group_index(g)]
    for g in sc.get("activate", []):
        if g in model.spec["virtual"]:
            ch, val = model.spec["virtual"][g]
            add[ch] += val
        else:
            act += model.group_mat[model.group_index(g)]
    return sil.clamp(max=1), act.clamp(max=1), add


def run(model, scenarios, rng=None):
    u = torch.as_tensor(np.stack([encode_scenario(s, rng, model.sex) for s in scenarios]))
    m = [masks_for(model, s) for s in scenarios]
    sil = torch.stack([a for a, _, _ in m])
    act = torch.stack([b for _, b, _ in m])
    add = torch.stack([c for _, _, c in m])
    return model(u, sil, act, add)


def interval_loss(p, lo, hi):
    mid = (lo + hi) / 2
    return (torch.relu(lo - p) ** 2 + torch.relu(p - hi) ** 2) * 20 + 0.5 * (p - mid) ** 2


def targets_of(model, b):
    """{имя считывания: [мин, макс]} для записи датасета."""
    return {ro: b[key] for key, ro in model.spec["targets"].items() if key in b}


def evaluate(model, data):
    """Детерминированный прогон (как в браузере): предсказания для всех опытов и фактов."""
    model.noise = 0.0
    inv = {ro: key for key, ro in model.spec["targets"].items()}
    with torch.no_grad():
        beh = data["behavior"]
        out = run(model, [b["scenario"] for b in beh])
        rows = []
        for i, b in enumerate(beh):
            row = {"id": b["id"], "split": b["split"], "title_ru": b["title_ru"], "preds": {}, "ok": True}
            for ro, (lo, hi) in targets_of(model, b).items():
                p = float(out["p"][ro][i])
                ok = lo - 0.02 <= p <= hi + 0.02
                row["preds"][inv[ro]] = {"pred": round(p, 3), "target": [lo, hi], "ok": ok}
                row["ok"] = row["ok"] and ok
            main = model.spec["readouts"][0][0]
            row["pred"] = round(float(out["p"][main][i]), 3)
            row["target"] = b.get(inv[main])
            rows.append(row)
        phys = data["physiology"]
        oa = run(model, [f["a"] for f in phys])
        ob = run(model, [f["b"] for f in phys])
        prow = []
        for i, f in enumerate(phys):
            k = model.group_index(f["group"])
            a, b = float(oa["mean"][i, k]), float(ob["mean"][i, k])
            ok = (a - b >= f["margin"] * 0.8) if f["rel"] == ">" else (abs(a - b) <= f["margin"] * 1.25)
            prow.append({"id": f["id"], "group": f["group"], "text_ru": f["text_ru"], "a": round(a, 3),
                         "b": round(b, 3), "rel": f["rel"], "margin": f["margin"], "ok": bool(ok)})
    return rows, prow


def load_model(sex: str) -> FlyCircuit:
    model = FlyCircuit(load_circuit(PROCESSED / f"{sex}_circuit.npz"), sex)
    model.load_state_dict(torch.load(MODELS / f"{sex}_model.pt")["state"])
    return model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sex", default="female", choices=list(SPECS))
    ap.add_argument("--iters", type=int, default=600)
    ap.add_argument("--lr", type=float, default=0.03)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--resume", action="store_true", help="продолжить с models/<пол>_model.pt")
    args = ap.parse_args()
    torch.manual_seed(args.seed)
    torch.set_num_threads(4)
    rng = np.random.default_rng(args.seed)
    sex = args.sex

    circ = load_circuit(PROCESSED / f"{sex}_circuit.npz")
    data = json.loads((LITERATURE / f"{sex}_experiments.json").read_text())
    model = FlyCircuit(circ, sex)
    history, prev_seconds = [], 0
    if args.resume:
        model.load_state_dict(torch.load(MODELS / f"{sex}_model.pt")["state"])
        prev = json.loads((MODELS / f"{sex}_report.json").read_text())
        history, prev_seconds = prev.get("history", []), prev.get("train_seconds", 0)
        print("продолжаю обучение с шага", history[-1]["it"] if history else 0)
    it0 = history[-1]["it"] if history else 0

    train_beh = [b for b in data["behavior"] if b["split"] == "train"]
    phys = data["physiology"]
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.iters, eta_min=args.lr * 0.05)
    MODELS.mkdir(exist_ok=True)
    readouts = [name for name, _ in model.spec["readouts"]]

    t0 = time.time()
    for it in range(1, args.iters + 1):
        model.noise = 0.03
        beh = train_beh * args.reps
        scen = [b["scenario"] for b in beh] + [f["a"] for f in phys] + [f["b"] for f in phys]
        out = run(model, scen, rng)
        nb, nf = len(beh), len(phys)
        losses = {}
        for ro in readouts:
            idx = [i for i, b in enumerate(beh) if ro in targets_of(model, b)]
            if not idx:
                continue
            lo = torch.tensor([targets_of(model, beh[i])[ro][0] for i in idx])
            hi = torch.tensor([targets_of(model, beh[i])[ro][1] for i in idx])
            losses[ro] = interval_loss(out["p"][ro][idx], lo, hi).mean()
        main_ro = readouts[0]
        loss_beh = losses.get(main_ro, torch.tensor(0.0))
        loss_aux = sum((v for k, v in losses.items() if k != main_ro), torch.tensor(0.0))
        gi = torch.tensor([model.group_index(f["group"]) for f in phys])
        a = out["mean"][nb:nb + nf].gather(1, gi[:, None])[:, 0]
        b = out["mean"][nb + nf:].gather(1, gi[:, None])[:, 0]
        margin = torch.tensor([f["margin"] for f in phys])
        greater = torch.tensor([f["rel"] == ">" for f in phys])
        l_gt = torch.relu(margin - (a - b)) ** 2
        l_eq = torch.relu((a - b).abs() - margin) ** 2
        loss_phys = torch.where(greater, l_gt, l_eq).mean() * 20
        reg = 1e-3 * ((model.log_gpre - model.init_gpre).pow(2).mean() + (model.log_gpost - model.init_gpost).pow(2).mean()
                      + model.log_gpair.pow(2).mean())
        act_reg = 1e-3 * out["mean_neuron"].pow(2).mean()
        loss = loss_beh + 0.5 * loss_aux + loss_phys + reg + act_reg

        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()

        if it % 25 == 0 or it == 1:
            history.append({"it": it0 + it, "loss": loss.item(), "beh": loss_beh.item(), "phys": loss_phys.item()})
            print(f"[{it:5d}] loss {loss.item():.4f}  поведение {loss_beh.item():.4f}  "
                  f"доп. {loss_aux.item():.4f}  физиология {loss_phys.item():.4f}  ({time.time() - t0:.0f} c)", flush=True)
        if it % 250 == 0 or it == args.iters:
            rows, prow = evaluate(model, data)
            tr = [r for r in rows if r["split"] == "train"]; te = [r for r in rows if r["split"] == "test"]
            print(f"   обучение: {sum(r['ok'] for r in tr)}/{len(tr)}  тест: {sum(r['ok'] for r in te)}/{len(te)}  "
                  f"физиология: {sum(r['ok'] for r in prow)}/{len(prow)}", flush=True)
            torch.save({"state": model.state_dict(), "args": vars(args)}, MODELS / f"{sex}_model.pt")
            report = {"behavior": rows, "physiology": prow, "history": history,
                      "train_seconds": prev_seconds + round(time.time() - t0)}
            (MODELS / f"{sex}_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))

    rows, prow = evaluate(model, data)
    print("\nИтог по опытам:")
    for r in rows:
        mark = "✓" if r["ok"] else "✗"
        preds = "  ".join(f"{k}: {v['pred']:.2f} цель {v['target']}" for k, v in r["preds"].items())
        print(f"  {mark} [{r['split']:5s}] {r['title_ru'][:58]:58s} {preds}")
    print("Физиология:")
    for r in prow:
        mark = "✓" if r["ok"] else "✗"
        print(f"  {mark} {r['text_ru'][:70]:70s} A={r['a']:.2f} B={r['b']:.2f}")


if __name__ == "__main__":
    main()
