"""Fit, calibrate and choose on FIT, CAL and VAL only: ``python -B q8_tune.py``.

Fits M1, M2, M3 on FIT, fits every temperature on the CAL grown blocks, scores all models on VAL and
chooses the model of highest VAL macro F1 (ties by lower negative log posterior). No TEST file is
read. Writes results/tuning.csv, results/chosen.json and $QL8C_OUT/models.pkl.
"""

from __future__ import annotations

import json
import pickle
import sys
from typing import Any

import numpy as np
import q8_env as env
import q8_feat as qf
import q8_model as qm
import q8_score as sc


def load(name: str) -> list[Any]:
    with (env.OUT8 / f"data_{name}.pkl").open("rb") as fh:
        data: list[Any] = pickle.load(fh)
    return data


def make_post(lik: qm.Likelihood, temperature: float, prior: dict[str, float]) -> sc.Post:
    post = qm.Posterior(prior, temperature)

    def fn(cell: str, x: np.ndarray, size: int) -> np.ndarray:
        return post.post(np.asarray(lik.loglik(cell, x, size)), not x[qf.H].any())

    return fn


def cal_blocks(recs: list[Any]) -> list[tuple[str, np.ndarray, int, list[str]]]:
    return [(r["cell"], b["x"], b["size"], sorted({k for _p, k in b["right"]}))
            for r in recs for b in r["blocks"]]


def grown_samples(recs: list[Any]) -> list[dict[str, Any]]:
    """Grown blocks as fit samples: one per right kind, glue when the block is right for none."""
    out = []
    for r in recs:
        for b in r["blocks"]:
            for k in sorted({k for _p, k in b["right"]}) or ["glue"]:
                out.append({"cell": r["cell"], "kind": k, "size": b["size"], "x": b["x"]})
    return out


def models_and_temps(cal_mode: str = "right"
                     ) -> tuple[dict[str, qm.Likelihood], dict[str, float], dict[str, float]]:
    prior = qm.qm.census_prior()
    fit = load("FIT")
    lik: dict[str, qm.Likelihood] = {"B73": qm.Baseline(), **qm.build_models(fit)}
    lik["B73-T"] = lik["B73"]
    lik["M4"] = qm.build_models(fit + grown_samples(load("FITG")))["M2"]
    blocks = cal_blocks(load("CAL"))
    if cal_mode == "right":  # deviation 1: calibrate on the right blocks only
        blocks = [b for b in blocks if b[3]]
    temps = {"B73": lik["B73"].T0}  # type: ignore[attr-defined]
    for name in ("B73-T", "M1", "M2", "M3", "M4"):
        temps[name] = qm.fit_temperature(lik[name], prior, blocks)
    return lik, temps, prior


def vector_sum(recs: list[Any], post: sc.Post) -> np.ndarray:
    return np.sum([sc.unit_vector(r, post) for r in recs], axis=0)


def main(argv: list[str]) -> int:
    cal_mode = argv[0] if argv else "right"
    lik, temps, prior = models_and_temps(cal_mode)
    val = load("VAL")
    rows = []
    for name in ("B73", "B73-T", "M1", "M2", "M3", "M4"):
        v = vector_sum(val, make_post(lik[name], temps[name], prior))
        rows.append({"model": name, "T": temps[name], "val_macro_f1": round(sc.macro_f1(v), 4),
                     "val_true_macro_f1": round(sc.macro_f1(v, True), 4),
                     "val_nll": round(v[sc.O_NLL] / v[sc.O_NLL + 1], 4),
                     "val_ece_grown": round(sc.ece(v, 0), 4), "val_ece_true": round(sc.ece(v, 2), 4),
                     "val_top3_right": round(sc.top3(v, False), 4),
                     "val_top3_true": round(sc.top3(v, True), 4)})
    new = [r for r in rows if r["model"].startswith("M")]
    best = max(new, key=lambda r: (r["val_macro_f1"], -r["val_nll"]))
    env.RES.mkdir(exist_ok=True)
    suffix = "" if cal_mode == "right" else "_first"
    env.l3dlib.write_csv(env.RES / f"tuning{suffix}.csv", list(rows[0]), rows)
    if suffix:
        return 0
    chosen = {"model": best["model"], "temperatures": temps, "n_scalars": len(qf.SCALARS), "cal_mode": cal_mode}
    (env.RES / "chosen.json").write_text(json.dumps(chosen, sort_keys=True, indent=1) + "\n",
                                         encoding="utf-8")
    with (env.OUT8 / "models.pkl").open("wb") as fh:
        pickle.dump({"lik": {k: v for k, v in lik.items()}, "temps": temps, "prior": prior}, fh)
    for r in rows:
        print(r)
    print("chosen", best["model"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
