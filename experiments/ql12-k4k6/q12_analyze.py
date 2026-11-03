"""Tables of Q-L12 from ``results.csv`` and ``astcfg_rows.csv`` of a run (no model call).

Usage: ``python -B q12_analyze.py [--run DIR] [--out DIR]`` (default out: ``results/``). Reads the
Q-L10 rows at the gates endpoint (``ql10-blocks/results``: arm D results and AST/CFG rows, arm A
AST/CFG rows) and the full run's arm A results (``llm-full/results/results.csv``). Unit: the
design. Differences are means over the draws two arms share; interval: seeded problem-level
bootstrap (seed 20261103, 2000 resamples). Rules of EXPERIMENT.md: (a) D at an endpoint minus D
at gates, SUPPORTED when the lower bound is above -0.05, CONTRADICTED when the upper bound is
below 0; (b) D minus A at an endpoint, SUPPORTED (A lower) when the lower bound is above 0,
CONTRADICTED when the upper bound is below 0; else INCONCLUSIVE. Holm over the exact McNemar
tests on MAJ of pass. Headline first.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import q12_env as env

q10a: Any = env.mod("q10_analyze")
SEED = 20261103
MARGIN = 0.05
Vals = dict[tuple[str, str], dict[int, float]]  # (arm, problem) -> draw -> value
Row = dict[str, str]


def read(path: Path) -> list[Row]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def pass_vals(rows: list[Row], endpoint: str | None) -> Vals:
    v: Vals = defaultdict(dict)
    for r in rows:
        if r["outcome"] in ("not_run", "") or (endpoint and r.get("endpoint") != endpoint):
            continue
        v[(r["arm"], r["problem"])][int(r["draw"])] = float(r["pass"])
    return v


def score_vals(rows: list[Row], endpoint: str | None, metric: str, variant: str) -> Vals:
    v: Vals = defaultdict(dict)
    for r in rows:
        var = "raw" if r["variant"] == "asm" else r["variant"]
        if var != variant or r[metric] == "" or (endpoint and r.get("endpoint") != endpoint):
            continue
        v[(r["arm"], r["problem"])][int(r["draw"])] = float(r[metric])
    return v


def pairs(a: Vals, arm_a: str, b: Vals, arm_b: str, only: set[str] | None = None
          ) -> dict[str, tuple[dict[int, float], dict[int, float]]]:
    out = {}
    for (arm, prob), da in a.items():
        db = b.get((arm_b, prob))
        if arm != arm_a or not db or (only is not None and prob not in only):
            continue
        if set(da) & set(db):
            out[prob] = ({d: da[d] for d in sorted(set(da) & set(db))},
                         {d: db[d] for d in sorted(set(da) & set(db))})
    return out


def compare(pr: dict[str, tuple[dict[int, float], dict[int, float]]]) -> dict[str, Any]:
    diffs = [q10a.mean(list(x.values())) - q10a.mean(list(y.values())) for x, y in pr.values()]
    lo, hi = q10a.boot_ci(diffs, seed=SEED)
    dl = [x[d] - y[d] for x, y in pr.values() for d in x]
    mj = [(int(sum(x.values()) >= 2), int(sum(y.values()) >= 2)) for x, y in pr.values()]
    first = sum(a > b for a, b in mj)
    second = sum(a < b for a, b in mj)
    pd = [d for d in diffs]
    return {"n": len(pr), "diff": q10a.mean(diffs) if diffs else float("nan"), "lo": lo, "hi": hi,
            "draws_WLT": f"{sum(x > 1e-9 for x in dl)}/{sum(x < -1e-9 for x in dl)}/"
                         f"{sum(abs(x) <= 1e-9 for x in dl)}",
            "designs_WLT": f"{sum(x > 1e-9 for x in pd)}/{sum(x < -1e-9 for x in pd)}/"
                           f"{sum(abs(x) <= 1e-9 for x in pd)}",
            "maj_first": sum(a for a, _ in mj), "maj_second": sum(b for _, b in mj),
            "p_mcnemar": q10a.mcnemar(first, second)}


def label_a(c: dict[str, Any]) -> str:
    if c["n"] == 0:
        return "NO DATA"
    if c["lo"] > -MARGIN:
        return "SUPPORTED"
    return "CONTRADICTED" if c["hi"] < 0 else "INCONCLUSIVE"


def label_b(c: dict[str, Any]) -> str:
    if c["n"] == 0:
        return "NO DATA"
    if c["lo"] > 0:
        return "SUPPORTED"
    return "CONTRADICTED" if c["hi"] < 0 else "INCONCLUSIVE"


def fmt(c: dict[str, Any]) -> str:
    if c["n"] == 0:
        return "no data"
    return (f"{c['diff']:+.3f} ({c['lo']:+.3f}, {c['hi']:+.3f}) over {c['n']} designs; "
            f"draws W/L/T {c['draws_WLT']}, designs W/L/T {c['designs_WLT']}")


def tests(run: Path) -> tuple[list[str], list[dict[str, Any]]]:
    res = read(run / "results.csv")
    ast_path = run / "astcfg_rows.csv"
    new_ac = read(ast_path) if ast_path.is_file() else []
    old = env.EXP / "ql10-blocks" / "results"
    g_res = read(old / "results.csv")
    g_ac = read(old / "astcfg_rows.csv")
    full_a = read(env.EXP / "llm-full" / "results" / "results.csv")
    designs = {d["problem"]: d for d in json.loads(
        (env.EXP / "ql10-blocks" / "designs.json").read_text(encoding="utf-8"))}
    multi = {p for p, d in designs.items() if d["n_blocks"] >= 2}
    rows: list[dict[str, Any]] = []
    lines: list[str] = []
    gates = {"pass": pass_vals([r for r in g_res if r["arm"] == "D"], None),
             "A_pass": pass_vals([r for r in full_a if r["arm"] == "A"], None)}
    for ep in env.ENDPOINTS:
        new = {"pass": pass_vals(res, ep)}
        for m in ("ast", "cfg"):
            new[m] = score_vals(new_ac, ep, m, "flat")
            gates[m] = score_vals(g_ac, None, m, "flat")
        for m in ("pass", "ast", "cfg"):
            for stratum, only in (("all designs", None), ("multi-block at gates", multi)):
                c = compare(pairs(new[m], "D", gates[m], "D", only))
                rows.append({"hyp": "a", "endpoint": ep, "metric": m, "stratum": stratum,
                             **c, "label": label_a(c)})
                lines.append(f"- (a) {ep} {m} D minus D at gates, {stratum}: {fmt(c)}; "
                             f"{label_a(c)}")
            c = compare(pairs(new[m], "D", new[m], "A"))
            rows.append({"hyp": "b", "endpoint": ep, "metric": m, "stratum": "A runs", **c,
                         "label": label_b(c)})
            lines.append(f"- (b) {ep} {m} D minus A, designs where A runs: {fmt(c)}; "
                         f"{label_b(c)}; MAJ {c['maj_first']} vs {c['maj_second']}, "
                         f"McNemar p = {c['p_mcnemar']:.3f}")
        c = compare(pairs(new["pass"], "A", gates["A_pass"], "A"))
        rows.append({"hyp": "desc", "endpoint": ep, "metric": "pass",
                     "stratum": "A minus A at gates", **c, "label": ""})
        lines.append(f"- (descriptive) {ep} pass A minus A at gates: {fmt(c)}")
    return lines, rows


def holm_line(rows: list[dict[str, Any]]) -> str:
    fam = [r for r in rows if r["metric"] == "pass" and r["stratum"] in ("all designs", "A runs")
           and r["hyp"] in ("a", "b")]
    ps = [float(r["p_mcnemar"]) for r in fam]
    adj = q10a.holm(ps)
    return "Holm over the McNemar tests on MAJ: " + "; ".join(
        f"{r['hyp']} {r['endpoint']} p={p:.3f} adj={a:.3f}" for r, p, a in zip(fam, ps, adj,
                                                                                strict=True))


def provenance(run: Path) -> tuple[list[str], list[dict[str, Any]]]:
    agg: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    for r in read(run / "results.csv"):
        if r["arm"] != "D" or r["outcome"] in ("not_run", ""):
            continue
        a = agg[(r["endpoint"], r["draw"])]
        a[0] += 1
        a[1] += int(r["key_total"])
        a[2] += int(r["key_right"])
        a[3] += int(r["key_right_ok"])
    rows = [{"endpoint": ep, "draw": dr, "rows": a[0], "key_total": a[1], "key_right": a[2],
             "key_right_ok": a[3]} for (ep, dr), a in sorted(agg.items())]
    lines = [f"- {r['endpoint']} draw {r['draw']}: {r['key_right']} of {r['key_total']} key "
             f"constructs have a right block; {r['key_right_ok']} with a block that checks ok"
             for r in rows]
    return lines, rows


def ext_rows(run: Path) -> list[str]:
    out = []
    blocks = read(run / "blocks.csv") if (run / "blocks.csv").is_file() else []
    for r in read(run / "results.csv"):
        if r["tier"] != "ext":
            continue
        ok = sum(1 for b in blocks if b["problem"] == r["problem"]
                 and b["endpoint"] == r["endpoint"] and b["draw"] == r["draw"]
                 and b["check"] == "ok") if r["arm"] == "D" else ""
        out.append(f"- {r['problem']} {r['endpoint']} {r['arm']}: {r['outcome']}"
                   + (f"; blocks ok {ok} of {r['n_blocks']}" if r["arm"] == "D" else ""))
    return out


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    keys: list[str] = []
    for r in rows:
        keys += [k for k in r if k not in keys]
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, keys, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", type=Path, default=env.RUN)
    ap.add_argument("--out", type=Path, default=env.RES)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    tl, trows = tests(a.run)
    pl, prows = provenance(a.run)
    md = ["# Q-L12 results (generated by q12_analyze.py)", "", "## H-L12 tests", *tl, "",
          holm_line(trows), "", "## Provenance (arm D, structure and checked decode)", *pl, "",
          "## Processor modules (ext)", *ext_rows(a.run), ""]
    (a.out / "summary.md").write_text("\n".join(md), encoding="utf-8", newline="\n")
    write_csv(a.out / "tests.csv", trows)
    write_csv(a.out / "provenance.csv", prows)
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
