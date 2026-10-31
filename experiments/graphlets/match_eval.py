"""Calibrate on TUNE, evaluate on TEST: ``python -B match_eval.py`` (after match_run.py).

Writes results/match_*.csv and results/calibration_<mode>_<tag>.json (pass format). Decision:
posterior (naive Bayes of GDD agreement and cosine-log, Laplace-smoothed binned likelihoods, spec
section 14 of the Odin III graphlets design) per library pattern from the best entry of that
pattern; predicted = highest posterior if >= threshold fit on TUNE, else none.
"""

from __future__ import annotations

import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "l3-detector"))
import l3dlib  # noqa: E402
import live  # noqa: E402

EDGES = [0, 500, 700, 800, 850, 900, 930, 960, 980, 1000]
ENT = l3dlib.ENTRIES
RES = HERE / "results"
MODEMAP = {"undirected": "undirected-5", "directed": "directed-4"}


def binof(v: float) -> int:
    pm = int(round(v * 1000))
    for i in range(len(EDGES) - 1):
        if pm < EDGES[i + 1]:
            return i
    return len(EDGES) - 2


class Calib:
    def __init__(self) -> None:
        nb = len(EDGES) - 1
        self.cnt = {m: {"same": [0] * nb, "different": [0] * nb} for m in ("gdd", "cos")}
        self.prior = {"same": 0, "different": 0}

    def add(self, g: float, c: float, same: bool) -> None:
        k = "same" if same else "different"
        self.cnt["gdd"][k][binof(g)] += 1
        self.cnt["cos"][k][binof(c)] += 1
        self.prior[k] += 1

    def lik(self, m: str, k: str, b: int) -> float:
        arr = self.cnt[m][k]
        return (arr[b] + 1) / (sum(arr) + len(arr))

    def post(self, g: float, c: float) -> float:
        ps = self.prior["same"] / (self.prior["same"] + self.prior["different"])
        ls = ps * self.lik("gdd", "same", binof(g)) * self.lik("cos", "same", binof(c))
        ld = (1 - ps) * self.lik("gdd", "different", binof(g)) * self.lik("cos", "different",
                                                                       binof(c))
        return ls / (ls + ld)

    def file(self, mode: str) -> dict[str, Any]:
        return {"schema": "odin3-graphlet-calibration", "version": 1,
                "source": "loki graphlets experiment, L3 v0 TUNE single designs x library patterns",
                "modes": {MODEMAP[mode]: {
                    "prior": dict(self.prior),
                    "metrics": {("gdd_agreement" if m == "gdd" else "cosine_log"):
                                {"edges": EDGES, "same": self.cnt[m]["same"],
                                 "different": self.cnt[m]["different"]} for m in self.cnt}}}}


def truth_family() -> dict[str, str]:
    lab = {r["design"]: r for r in l3dlib.read_csv(l3dlib.CENSUS_RES / "labels_rtl.csv")
           if r["status"] in ("ok", "manual")}
    return {d: [e for e in ENT if r[e] not in ("", "0")][0] for d, r in lab.items()
            if len([e for e in ENT if r[e] not in ("", "0")]) == 1}


def posts(calib: Calib, row: dict[str, Any], tag: str) -> dict[str, float]:
    best = row[tag]
    return {p: (calib.post(best[p][0], best[p][1]) if p in best else 0.0) for p in ENT}


def predict(ps: dict[str, float], thr: float) -> str:
    p = max(ENT, key=lambda e: ps[e])
    return p if ps[p] >= thr else "none"


def prf(counts: list[tuple[int, int, int]]) -> tuple[float, float]:
    tp, fp, fn = (sum(x[i] for x in counts) for i in range(3))
    return (tp / (tp + fp) if tp + fp else 1.0), (tp / (tp + fn) if tp + fn else 1.0)


def main() -> int:
    rows = [json.loads(x) for x in (live.OUT / "match" / "scores.jsonl").read_text(
        encoding="utf-8").splitlines()]
    fam = truth_family()
    split = {r["design"]: r["split"] for r in l3dlib.read_csv(l3dlib.RES / "split_single.csv")}
    rule: dict[tuple[str, str], dict[str, int]] = {}
    for r in l3dlib.read_csv(l3dlib.RES / "partA_design.csv"):
        rule[(r["design"], r["cell"])] = {e: int(r[f"found_{e}"]) for e in ENT}
    out: list[dict[str, Any]] = []
    pred_tab: dict[tuple[str, str, str, str], str] = {}
    reliab: list[dict[str, Any]] = []
    for mode in ("undirected", "directed"):
        for tag in ("all", "ff"):
            sel = [r for r in rows if r["set"] == "l3" and r["mode"] == mode]
            tune = [r for r in sel if split[r["design"]] == "TUNE"]
            cal = Calib()
            for r in tune:
                for p in ENT:
                    if p in r[tag]:
                        cal.add(r[tag][p][0], r[tag][p][1], p == fam[r["design"]])
            (RES / f"calibration_{mode}_{tag}.json").write_text(
                json.dumps(cal.file(mode), sort_keys=True), encoding="utf-8")
            grid = [x / 100 for x in range(5, 100, 5)]
            def acc(thr: float, tune: list[dict[str, Any]] = tune, cal: Calib = cal,
                    tag: str = tag) -> float:
                return sum(predict(posts(cal, r, tag), thr) == fam[r["design"]]
                           for r in tune) / max(1, len(tune))
            thr = max(grid, key=lambda t: (round(acc(t), 6), -t))
            rel: dict[int, list[int]] = defaultdict(lambda: [0, 0])
            for r in sel:
                if split[r["design"]] == "TEST":
                    for p, pv in posts(cal, r, tag).items():
                        if p in r[tag]:
                            b = min(9, int(pv * 10))
                            rel[b][0] += 1
                            rel[b][1] += int(p == fam[r["design"]])
            for b, (n_, k_) in sorted(rel.items()):
                reliab.append({"mode": mode, "restrict": tag,
                               "posterior_bin": f"{b / 10:.1f}-{(b + 1) / 10:.1f}",
                               "pairs": n_, "observed_same": round(k_ / n_, 3)})
            for r in sel:
                pred_tab[(mode, tag, r["design"], r["cell"])] = predict(posts(cal, r, tag), thr)
            out.append({"mode": mode, "tag": tag, "threshold": thr,
                        "tune_accuracy": round(acc(thr), 3), "tune_n": len(tune)})
    RES.mkdir(exist_ok=True)
    l3dlib.write_csv(RES / "match_reliability.csv", list(reliab[0]), reliab)
    with (RES / "match_threshold.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, list(out[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    # TEST table per pattern x cell x variant (sig modes, rule, hybrid)
    tab: list[dict[str, Any]] = []
    per: dict[tuple[str, str, str], dict[str, tuple[int, int, int]]] = defaultdict(dict)
    test = sorted({(r["design"], r["cell"]) for r in rows
                   if r["set"] == "l3" and split[r["design"]] == "TEST"
                   and all((m, t, r["design"], r["cell"]) in pred_tab
                           for m in ("undirected", "directed") for t in ("all", "ff"))})
    for variant in ("rule", "undirected/all", "undirected/ff", "directed/all", "directed/ff",
                    "hybrid-undirected/ff", "hybrid-directed/ff"):
        for p in ENT:
            for cell in live.CELLS:
                for d, c in test:
                    if c != cell or (d, c) not in rule:
                        continue
                    t = int(fam[d] == p)
                    if variant == "rule":
                        f = rule[(d, c)][p]
                    elif variant.startswith("hybrid"):
                        m = variant.split("-")[1].split("/")
                        f = int(rule[(d, c)][p] or pred_tab[(m[0], m[1], d, c)] == p)
                    else:
                        m = variant.split("/")
                        f = int(pred_tab[(m[0], m[1], d, c)] == p)
                    per[(variant, p, cell)][d] = (t & f, (1 - t) & f, t & (1 - f))
    for (variant, p, cell), dd in sorted(per.items()):
        cnt = list(dd.values())
        tp, fp, fn = (sum(x[i] for x in cnt) for i in range(3))
        pr, rc = prf(cnt)
        lp, lr = l3dlib.bootstrap(cnt)
        tab.append({"variant": variant, "pattern": p, "cell": cell, "designs": len(cnt),
                    "TP": tp, "FP": fp, "FN": fn, "precision": round(pr, 3),
                    "precision_lo": round(lp, 3), "recall": round(rc, 3),
                    "recall_lo": round(lr, 3), "label": l3dlib.label(pr, rc, lp, lr, tp + fn)})
    l3dlib.write_csv(RES / "match_table.csv", list(tab[0]), tab)
    # directed vs undirected: paired bootstrap of precision difference, Holm
    tests = []
    rng = random.Random(7)
    for p in ENT:
        for cell in live.CELLS:
            a = per.get(("undirected/ff", p, cell))
            b = per.get(("directed/ff", p, cell))
            if not a or not b:
                continue
            ds = sorted(a)
            npos = sum(a[d][0] + a[d][2] for d in ds)
            if npos < 5:
                continue
            diffs = []
            for _ in range(2000):
                s = [ds[rng.randrange(len(ds))] for _ in ds]
                pa_, ra_ = prf([a[d] for d in s])
                pb_, rb_ = prf([b[d] for d in s])
                diffs.append((pb_ - pa_) if rb_ >= ra_ else -1.0)
            pv = sum(x <= 0 for x in diffs) / len(diffs)
            pa0, ra0 = prf([a[d] for d in ds])
            pb0, rb0 = prf([b[d] for d in ds])
            tests.append({"pattern": p, "cell": cell, "n_pos": npos, "prec_und": round(pa0, 3),
                          "prec_dir": round(pb0, 3), "rec_und": round(ra0, 3),
                          "rec_dir": round(rb0, 3), "p": pv})
    tests.sort(key=lambda t: t["p"])
    m = len(tests)
    run = 0.0
    for i, t in enumerate(tests):
        run = max(run, min(1.0, t["p"] * (m - i)))
        t["p_holm"] = round(run, 4)
        t["directed_more_precise"] = int(t["p_holm"] < 0.05 and t["prec_dir"] > t["prec_und"])
    if tests:
        l3dlib.write_csv(RES / "match_directed_vs_undirected.csv", list(tests[0]), tests)
    # held-out widths
    hold: dict[tuple[str, str, str, str], list[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["set"] != "hold":
            continue
        truth = r["design"].split("_")[0]
        for tag in ("all", "ff"):
            best = r[tag] or r["all"]  # no entry with this flip-flop count: nearest size (all)
            if not best:
                ok = 0
            else:
                ok = int(max(best, key=lambda q: best[q][0] + best[q][1]) == truth)
            h = hold[(r["mode"], tag, truth, r["cell"])]
            h[0] += 1
            h[1] += ok
    hrows = [{"mode": k[0], "restrict": k[1], "pattern": k[2], "cell": k[3], "n": v[0],
              "correct": v[1], "rate": round(v[1] / v[0], 3)} for k, v in sorted(hold.items())]
    l3dlib.write_csv(RES / "match_heldout_widths.csv", list(hrows[0]), hrows)
    print(len(tab), "table rows,", len(tests), "directed tests,", len(hrows), "hold rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
