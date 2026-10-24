"""RQ-L2: head-to-head tables, Loki against the Gate-Breaker LLM replication, on VerilogEval.

Inputs: ``<data>/l2/astcfg.json`` (l2_astcfg.py), the round-1 LLM results
(``gatebreaker-exp2/data/results.json``), ``<data>/l2/llm_ops.json`` (l2_llm_ops.py), the Loki
run directories (final_equiv) and the dataset ``benchmark.csv`` quartiles.

Writes ``l2_headtohead.csv`` (mean AST and CFG per quartile and variant, all designs and the
common LLM set), ``l2_paired.csv`` (Loki minus LLM on the common designs, Wilcoxon signed-rank)
and ``l2_equiv.csv`` (final_equiv status counts, and the round-1 self-check of the input netlists).
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

import r2lib
from scipy.stats import wilcoxon

GB = Path("/home/jamiespa/odin3-ws/work/gatebreaker-exp2/data")
VARIANTS = ("f3-l0", "f2-l0", "f3-calib", "f3-none", "f2-calib", "f2-none")
QS = ("Q1", "Q2", "Q3", "Q4")


def mean(vals: list[float]) -> float | None:
    return round(sum(vals) / len(vals), 6) if vals else None


def quartile_map() -> dict[str, str]:
    path = Path(__file__).resolve().parents[1] / "veval-l0" / "benchmark.csv"
    with path.open(encoding="utf-8", newline="") as fh:
        return {r["design"]: r["quartile"] for r in csv.DictReader(fh)}


def llm_rows() -> dict[str, dict[str, Any]]:
    res = json.loads((GB / "results.json").read_text(encoding="utf-8"))
    return {f"ve_{str(d['design']).removesuffix('_ref')}": d for d in res["designs"]}


def headtohead() -> list[list[Any]]:
    quart = quartile_map()
    loki = {r["design"]: r for r in json.loads(
        (r2lib.DATA / "l2" / "astcfg.json").read_text(encoding="utf-8"))}
    llm = llm_rows()
    rows: list[list[Any]] = []
    for q in QS:
        designs = sorted(d for d in loki if quart.get(d) == q)
        common = [d for d in designs if d in llm and llm[d]["ast"] is not None]
        rows.append(["llm", q, len(common), mean([float(llm[d]["ast"]) for d in common]),
                     mean([float(llm[d]["cfg"]) for d in common if llm[d]["cfg"] is not None]),
                     "common"])
        for v in VARIANTS:
            for label, sel in (("all", designs), ("common", common)):
                a = [float(loki[d][f"{v}:ast"]) for d in sel if f"{v}:ast" in loki[d]]
                c = [float(loki[d][f"{v}:cfg"]) for d in sel if f"{v}:cfg" in loki[d]]
                rows.append([v, q, len(a), mean(a), mean(c), label])
    return rows


def paired() -> list[list[Any]]:
    quart = quartile_map()
    loki = {r["design"]: r for r in json.loads(
        (r2lib.DATA / "l2" / "astcfg.json").read_text(encoding="utf-8"))}
    llm = llm_rows()
    rows: list[list[Any]] = []
    for v in VARIANTS:
        for metric, key in (("ast", "ast"), ("cfg", "cfg")):
            for q in ("Q1", "Q2", "Q1+Q2"):
                sel = [d for d in sorted(loki) if d in llm and llm[d][key] is not None
                       and f"{v}:{metric}" in loki[d]
                       and (quart.get(d) in q.split("+"))]
                diffs = [float(loki[d][f"{v}:{metric}"]) - float(llm[d][key]) for d in sel]
                p = None
                if len(diffs) >= 5 and any(x != 0 for x in diffs):
                    p = round(float(wilcoxon(diffs).pvalue), 6)
                rows.append([v, metric, q, len(diffs), mean(diffs), p])
    return rows


def equiv_rows() -> list[list[Any]]:
    out: list[list[Any]] = []
    sc = {f"ve_{r['design'].removesuffix('_ref')}": r.get("selfcheck")
          for r in json.loads((GB / "netlist_results.json").read_text(encoding="utf-8"))}
    for floor in ("f2", "f3"):
        for cond in ("calib", "none"):
            root = r2lib.DATA / "l2" / "runs" / f"{floor}-{cond}"
            status: Counter[str] = Counter()
            committed = designs_changed = 0
            ok_input = 0
            for rep in sorted(root.glob(f"*__{floor}/re/report.json")):
                data = json.loads(rep.read_text(encoding="utf-8"))
                status[str(data["final_equiv"]["status"])] += 1
                n = int(data["counts"]["committed"])
                committed += n
                designs_changed += 1 if n else 0
                design = rep.parent.parent.name.rsplit("__", 1)[0]
                ok_input += 1 if sc.get(design) == "ok" else 0
            out.append([f"{floor}-{cond}", sum(status.values()), status.get("equivalent", 0),
                        json.dumps(dict(sorted(status.items()))), committed, designs_changed,
                        ok_input])
    return out


def _f(prec: float | None, rec: float | None) -> float | None:
    if rec is None:
        return None
    return 0.0 if rec == 0 or prec is None else 2 * prec * rec / (prec + rec)


def _pool(per_design: list[dict[str, Any]]) -> list[Any]:
    """Pooled (key, got, type P/R/F1, tw P/R/F1) of per-design expected counts."""
    key = sum(d["key_n"] for d in per_design)
    got = sum(d["got_n"] for d in per_design)
    out: list[Any] = [len(per_design), round(key, 4), round(got, 4)]
    for name in ("type", "tw"):
        tp = sum(d[f"{name}_tp"] for d in per_design)
        prec = tp / got if got else None
        rec = tp / key if key else None
        f = _f(prec, rec)
        out += ["" if x is None else round(x, 6) for x in (prec, rec, f)]
    return out


def ops_rows() -> list[list[Any]]:
    """Operator F1 per quartile on the common LLM designs: the LLM samples (mean over the
    correct samples of a design) and the Loki runs of l7_runs.csv."""
    path = r2lib.DATA / "l2" / "llm_ops.json"
    if not path.is_file():
        return []
    quart = quartile_map()
    llm: dict[str, list[dict[str, Any]]] = {}
    for r in json.loads(path.read_text(encoding="utf-8")):
        if "error" not in r:
            llm.setdefault(r["design"], []).append(r)
    common = set(llm)
    out: list[list[Any]] = []
    sets: dict[str, list[dict[str, Any]]] = {}
    for d, samples in llm.items():
        n = len(samples)
        sets.setdefault("llm", [])
        sets["llm"].append({"design": d, **{k: sum(float(s[k]) for s in samples) / n for k in (
            "key_n", "got_n", "type_tp", "tw_tp")}})
    with (r2lib.OUT / "l7_runs.csv").open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["set"].startswith("l2-") and r["design"] in common:
                sets.setdefault(r["set"], []).append({
                    "design": r["design"], "key_n": float(r["key_ops"]),
                    "got_n": float(r["got_ops"]), "type_tp": float(r["type_tp"]),
                    "tw_tp": float(r["tw_tp"])})
    for label, per in sorted(sets.items()):
        for q in (*QS, "Q1+Q2"):
            sel = [d for d in per if quart.get(str(d["design"])) in q.split("+")]
            if sel:
                out.append([label, q, *_pool(sel)])
    return out


def main() -> int:
    r2lib.write_csv(r2lib.OUT / "l2_headtohead.csv",
                    ["variant", "quartile", "n", "ast_mean", "cfg_mean", "set"], headtohead())
    r2lib.write_csv(r2lib.OUT / "l2_paired.csv",
                    ["variant", "metric", "quartile", "n", "mean_diff_loki_minus_llm",
                     "wilcoxon_p"], paired())
    r2lib.write_csv(r2lib.OUT / "l2_equiv.csv",
                    ["set", "runs", "final_equiv_equivalent", "status_counts", "committed",
                     "designs_with_commits", "input_netlist_selfcheck_ok"], equiv_rows())
    ops = ops_rows()
    if ops:
        r2lib.write_csv(r2lib.OUT / "l2_ops.csv",
                        ["set", "quartile", "designs", "key_ops", "got_ops", "type_p",
                         "type_r", "type_f1", "tw_p", "tw_r", "tw_f1"], ops)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
