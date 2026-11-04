"""Tables of Q-L12 lut4 from ``results.csv`` and ``astcfg_rows.csv`` of a run (no model call).

Usage: ``python -B l4_analyze.py [--run DIR] [--out DIR]`` (default out: ``results/``). Same tests,
bootstrap (seed 20261103, 2000 resamples), labels and Holm rule as ``ql12-k4k6/q12_analyze.py``
(imported), with lut4 as the endpoint. Reads the Q-L10 rows at gates (arm D results, AST/CFG rows),
the full run's arm A pass rows, and the Q-L12 rows at k6 (``ql12-k4k6/results``). Tests: (a) D at
lut4 minus D at gates; (b) D minus A at lut4; descriptive: A at lut4 minus A at gates, and lut4
minus k6 for D and for A. Also ``side_by_side.csv``: mean per arm, measure and endpoint, over
all designs with data and over the designs all three endpoints share. Holm family: the two pass@1
tests (a) all designs and (b). Unit: the design. Headline first.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import l4_env as l4

env = l4.env
qa: Any = env.mod("q12_analyze")
q10a: Any = env.mod("q10_analyze")
K6_RES = l4.K46 / "results"
OLD = env.EXP / "ql10-blocks" / "results"
METRICS = ("pass", "ast", "cfg")
Vals = dict[tuple[str, str], dict[int, float]]


def load(run: Path) -> dict[str, dict[str, Vals]]:
    """Per endpoint (gates, lut4, k6) and measure, the values (arm, problem) -> draw -> value."""
    out: dict[str, dict[str, Vals]] = {}
    new_res = qa.read(run / "results.csv")
    ap = run / "astcfg_rows.csv"
    new_ac = qa.read(ap) if ap.is_file() else []
    k6_res, k6_ac = qa.read(K6_RES / "results.csv"), qa.read(K6_RES / "astcfg_rows.csv")
    g_res = qa.read(OLD / "results.csv")
    g_ac = qa.read(OLD / "astcfg_rows.csv")
    full_a = qa.read(env.EXP / "llm-full" / "results" / "results.csv")
    g_pass = qa.pass_vals([r for r in g_res if r["arm"] == "D"], None)
    g_pass.update(qa.pass_vals([r for r in full_a if r["arm"] == "A"], None))
    out["gates"] = {"pass": g_pass}
    out["lut4"] = {"pass": qa.pass_vals(new_res, "lut4")}
    out["k6"] = {"pass": qa.pass_vals(k6_res, "k6")}
    for m in ("ast", "cfg"):
        out["gates"][m] = qa.score_vals(g_ac, None, m, "flat")
        out["lut4"][m] = qa.score_vals(new_ac, "lut4", m, "flat")
        out["k6"][m] = qa.score_vals(k6_ac, "k6", m, "flat")
    return out


def tests(data: dict[str, dict[str, Vals]]) -> tuple[list[str], list[dict[str, Any]]]:
    designs = json.loads((env.EXP / "ql10-blocks" / "designs.json").read_text(encoding="utf-8"))
    multi = {d["problem"] for d in designs if d["n_blocks"] >= 2}
    rows: list[dict[str, Any]] = []
    lines: list[str] = []

    def add(hyp: str, m: str, stratum: str, c: dict[str, Any], label: str, what: str) -> None:
        rows.append({"hyp": hyp, "endpoint": "lut4", "metric": m, "stratum": stratum, **c,
                     "label": label})
        extra = (f"; MAJ {c['maj_first']} vs {c['maj_second']}, McNemar p = {c['p_mcnemar']:.3f}"
                 if m == "pass" else "")
        lines.append(f"- ({hyp}) lut4 {m} {what}, {stratum}: {qa.fmt(c)}"
                     f"{'; ' + label if label else ''}{extra}")

    for m in METRICS:
        new, gat, k6 = data["lut4"][m], data["gates"][m], data["k6"][m]
        for stratum, only in (("all designs", None), ("multi-block at gates", multi)):
            c = qa.compare(qa.pairs(new, "D", gat, "D", only))
            add("a", m, stratum, c, qa.label_a(c), "D minus D at gates")
        c = qa.compare(qa.pairs(new, "D", new, "A"))
        add("b", m, "A runs", c, qa.label_b(c), "D minus A, designs where A runs")
        c = qa.compare(qa.pairs(new, "A", gat, "A"))
        add("desc", m, "A minus A at gates", c, "", "A minus A at gates")
        for arm in ("D", "A"):
            c = qa.compare(qa.pairs(new, arm, k6, arm))
            add("desc", m, f"{arm} lut4 minus k6", c, "", f"{arm} lut4 minus k6")
    return lines, rows


def side_by_side(data: dict[str, dict[str, Vals]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for arm in ("D", "A"):
        for m in METRICS:
            probs = {ep: {p for (a, p), v in data[ep][m].items() if a == arm and v}
                     for ep in data}
            common = probs["gates"] & probs["lut4"] & probs["k6"]
            row: dict[str, Any] = {"arm": arm, "metric": m, "common_n": len(common)}
            for ep in ("gates", "lut4", "k6"):
                vals = data[ep][m]
                own = [q10a.mean(list(vals[(arm, p)].values())) for p in sorted(probs[ep])]
                com = [q10a.mean(list(vals[(arm, p)].values())) for p in sorted(common)]
                row[f"{ep}_n"] = len(own)
                row[f"{ep}_mean"] = round(q10a.mean(own), 4) if own else ""
                row[f"{ep}_common_mean"] = round(q10a.mean(com), 4) if com else ""
            out.append(row)
    return out


def holm_line(rows: list[dict[str, Any]]) -> str:
    fam = [r for r in rows if r["metric"] == "pass"
           and ((r["hyp"] == "a" and r["stratum"] == "all designs") or r["hyp"] == "b")]
    ps = [float(r["p_mcnemar"]) for r in fam]
    adj = q10a.holm(ps)
    return "Holm over the McNemar tests on MAJ: " + "; ".join(
        f"{r['hyp']} p={p:.3f} adj={a:.3f}" for r, p, a in zip(fam, ps, adj, strict=True))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", type=Path, default=env.RUN)
    ap.add_argument("--out", type=Path, default=env.RES)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    data = load(a.run)
    tl, trows = tests(data)
    sbs = side_by_side(data)
    pl, prows = qa.provenance(a.run)
    side = [f"- {r['arm']} {r['metric']}: gates {r['gates_mean']} (n {r['gates_n']}), lut4 "
            f"{r['lut4_mean']} (n {r['lut4_n']}), k6 {r['k6_mean']} (n {r['k6_n']}); on the "
            f"{r['common_n']} common designs: {r['gates_common_mean']} / {r['lut4_common_mean']} / "
            f"{r['k6_common_mean']}" for r in sbs]
    md = ["# Q-L12 lut4 results (generated by l4_analyze.py)", "",
          "## Side by side: gates, lut4, k6 (mean over designs of the per-design mean over draws)",
          *side, "", "## H-L12 tests at lut4", *tl, "", holm_line(trows), "",
          "## Provenance (arm D, structure and checked decode)", *pl, "",
          "## Processor modules (ext)", *qa.ext_rows(a.run), ""]
    (a.out / "summary.md").write_text("\n".join(md), encoding="utf-8", newline="\n")
    qa.write_csv(a.out / "tests.csv", trows)
    qa.write_csv(a.out / "side_by_side.csv", sbs)
    qa.write_csv(a.out / "provenance.csv", prows)
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
