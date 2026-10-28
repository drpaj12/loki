#!/usr/bin/env python3
"""Per-quartile (Gate-Breaker Q1-Q4) tables from committed result files; no model calls.

Inputs (committed): experiments/llm-pilot/{selection.csv,results/re/results.csv,
results/re/status.csv}, experiments/veval-l0/{benchmark.csv,l0-ceiling-veval.csv,sizes.csv},
experiments/round2/l2_headtohead.csv, experiments/hal/results/scores-hal8.csv.

Outputs (deterministic, sorted rows, LF, UTF-8): CSVs in this directory and
docs/paper/quartile-tables.tex.

Tests: exact two-sided McNemar per quartile on paired binary pass/fail. Conditional on the
discordant pairs, the first-only count is Binomial(d, 1/2) under H0; the stratified exact test
sums the discordant counts over the quartiles (the conditional distribution of the sum of
independent Binomial(d_i, 1/2) is Binomial(sum d_i, 1/2)), so it is the exact McNemar test on
the pooled discordant pairs. ``min_discordant`` is the least d for which an all-one-sided split
reaches p < 0.05 (the power floor of the test at that size).
"""

from __future__ import annotations

import argparse
import csv
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
QS = ("Q1", "Q2", "Q3", "Q4")
ARMS = ("A", "B", "C")
PAIRS = (("B", "A"), ("B", "C"), ("A", "C"))
Row = dict[str, str]


def read(path: Path) -> list[Row]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def mcnemar_p(first_only: int, second_only: int) -> float:
    d = first_only + second_only
    if d == 0:
        return 1.0
    k = min(first_only, second_only)
    tail = sum(comb(d, i) for i in range(k + 1)) / 2**d
    return float(min(1.0, 2 * tail))


def min_discordant(alpha: float = 0.05) -> int:
    d = 1
    while mcnemar_p(d, 0) >= alpha:
        d += 1
    return d


def min_majority(d: int, alpha: float = 0.05) -> int | None:
    """Least first-only count (of d discordant pairs) with p < alpha, or None."""
    for k in range(d // 2 + 1, d + 1):
        if mcnemar_p(k, d - k) < alpha:
            return k
    return None


def pilot_outcomes() -> tuple[dict[str, str], dict[tuple[str, str], int]]:
    quart = {r["problem"]: r["quartile"] for r in read(EXP / "llm-pilot/selection.csv")}
    res = {(r["arm"], r["problem"]): int(r["pass"])
           for r in read(EXP / "llm-pilot/results/re/results.csv")}
    return quart, res


def pilot_rows() -> tuple[list[Row], list[Row]]:
    quart, res = pilot_outcomes()
    cells: list[Row] = []
    tests: list[Row] = []
    strat: dict[tuple[str, str, str], list[int]] = {}
    for q in (*QS, "All"):
        probs = sorted(p for p in quart if q == "All" or quart[p] == q)
        paired = [p for p in probs if all((a, p) in res for a in ARMS)]
        for view, ps in (("all_calls", probs), ("paired", paired)):
            row: Row = {"quartile": q, "view": view, "n": str(len(ps))}
            for a in ARMS:
                row[f"pass_{a}"] = str(sum(res.get((a, p), 0) for p in ps))
            cells.append(row)
            for x, y in PAIRS:
                b = sum(1 for p in ps if res.get((x, p), 0) and not res.get((y, p), 0))
                c = sum(1 for p in ps if res.get((y, p), 0) and not res.get((x, p), 0))
                tests.append({"quartile": q, "view": view, "comparison": f"{x} vs {y}",
                              "n": str(len(ps)), "first_only": str(b), "second_only": str(c),
                              "discordant": str(b + c), "p": f"{mcnemar_p(b, c):.4f}"})
                if q != "All":
                    s = strat.setdefault((view, x, y), [0, 0, 0])
                    s[0] += b
                    s[1] += c
                    s[2] += len(ps)
    for (view, x, y), (b, c, n) in sorted(strat.items()):
        tests.append({"quartile": "Stratified", "view": view, "comparison": f"{x} vs {y}",
                      "n": str(n), "first_only": str(b), "second_only": str(c),
                      "discordant": str(b + c), "p": f"{mcnemar_p(b, c):.4f}"})
    return cells, tests


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def loki_only_rows() -> list[Row]:
    bench = {r["design"]: r["quartile"] for r in read(EXP / "veval-l0/benchmark.csv")}
    out: list[Row] = []
    ceil = read(EXP / "veval-l0/l0-ceiling-veval.csv")
    for q in QS:
        rs = [r for r in ceil if bench[r["design"]] == q]
        for col in ("label_cov", "cell_type_cov", "hdl_cov", "module_cov", "signal_cov"):
            out.append({"source": "veval-l0 f3 ceiling", "metric": col, "quartile": q,
                        "n": str(len(rs)), "value": f"{mean([float(r[col]) for r in rs]):.3f}"})
    sizes = read(EXP / "veval-l0/sizes.csv")
    for fl in ("f1-k6", "f2", "f3"):
        for q in QS:
            rs = [r for r in sizes if r["floor"] == fl and r["quartile"] == q]
            out.append({"source": "veval-l0 sizes", "metric": f"built_{fl}", "quartile": q,
                        "n": str(len(rs)), "value": str(len(rs))})
    for r in read(EXP / "round2/l2_headtohead.csv"):
        if r["set"] == "all" and r["variant"] != "llm":
            for m in ("ast_mean", "cfg_mean"):
                out.append({"source": "round2 head-to-head", "metric": f"{r['variant']} {m}",
                            "quartile": r["quartile"], "n": r["n"],
                            "value": f"{float(r[m]):.3f}"})
    hal = [r for r in read(EXP / "hal/results/scores-hal8.csv")
           if r["set"] == "VT" and r["floor"] == "f2"]
    for tool in ("lokiW", "lokiWB", "hal8"):
        for q in QS:
            rs = [r for r in hal if r["tool"] == tool and bench[r["design"]] == q]
            nm, npred, ngt = (sum(int(r[k]) for r in rs) for k in ("matched", "n_pred", "n_gt"))
            out.append({"source": "hal VT f2", "metric": f"{tool} matched/n_pred/n_gt",
                        "quartile": q, "n": str(len(rs)), "value": f"{nm}/{npred}/{ngt}"})
    return out


def llm_round1() -> dict[tuple[str, str], tuple[str, str]]:
    return {(r["quartile"], r["set"]): (r["ast_mean"], r["cfg_mean"])
            for r in read(EXP / "round2/l2_headtohead.csv") if r["variant"] == "llm"}


def compare_rows(cells: list[Row], loki: list[Row]) -> list[Row]:
    ast = {(r["quartile"], r["metric"]): r for r in loki if r["source"] == "round2 head-to-head"}
    l1 = llm_round1()
    out: list[Row] = []
    for q in QS:
        a = ast[(q, "f3-calib ast_mean")]
        c = ast[(q, "f3-calib cfg_mean")]
        lm = l1.get((q, "common"), ("", ""))
        row: Row = {"quartile": q, "loki_n": a["n"], "loki_f3_ast": a["value"],
                    "loki_f3_cfg": c["value"],
                    "round1_llm_ast": f"{float(lm[0]):.3f}" if lm[0] else "",
                    "round1_llm_cfg": f"{float(lm[1]):.3f}" if lm[1] else ""}
        cell = next(r for r in cells if r["quartile"] == q and r["view"] == "all_calls")
        for arm in ARMS:
            row[f"pilot_pass_{arm}"] = f"{cell['pass_' + arm]}/{cell['n']}"
        out.append(row)
    return out


def write_csv(path: Path, rows: list[Row]) -> None:
    keys = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def frac(k: str, n: str) -> str:
    return f"{k}/{n}"


def tex_pilot(cells: list[Row]) -> str:
    lines = [r"\begin{table}[t]", r"\centering",
             r"\caption{LLM pilot (run \code{re}) pass rate per Gate-Breaker complexity "
             r"quartile, strict "
             r"scorer. All calls: refusal or missing reply file counts as a fail. Paired: problems "
             r"answered in all three arms. Arm A netlist, B netlist plus Loki hints, C interface "
             r"only; one draw per cell. AST and CFG similarity were not scored in the pilot.}",
             r"\label{tab:q-pilot}", r"\small", r"\begin{tabular}{@{}llrccc@{}}", r"\toprule",
             r"Quartile & View & $n$ & A & B & C \\", r"\midrule"]
    for q in (*QS, "All"):
        if q == "All":
            lines.append(r"\midrule")
        for view, label in (("all_calls", "all calls"), ("paired", "paired")):
            r = next(x for x in cells if x["quartile"] == q and x["view"] == view)
            lines.append(f"{q} & {label} & {r['n']} & "
                         + " & ".join(frac(r[f"pass_{a}"], r["n"]) for a in ARMS) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    return "\n".join(lines)


def tex_tests(tests: list[Row]) -> str:
    lines = [r"\begin{table}[t]", r"\centering",
             r"\caption{LLM pilot (run \code{re}): exact two-sided McNemar test per quartile and "
             r"the "
             r"stratified exact test (discordant pairs pooled over Q1--Q4), strict scorer. Cells "
             r"are first-only/second-only discordant pairs (all-calls view in the first group, "
             r"paired view in the second); $p$ in brackets. A single test at this $n$ needs at "
             r"least 6 discordant pairs, all on one side, to reach $p<0.05$.}",
             r"\label{tab:q-tests}", r"\footnotesize", r"\begin{tabular}{@{}llccc@{}}", r"\toprule",
             r"View & Stratum & B vs A & B vs C & A vs C \\", r"\midrule"]
    for view, label in (("all_calls", "all calls"), ("paired", "paired")):
        for q in (*QS, "Stratified"):
            cs = []
            for x, y in PAIRS:
                t = next(r for r in tests if r["quartile"] == q and r["view"] == view
                         and r["comparison"] == f"{x} vs {y}")
                cs.append(f"{t['first_only']}/{t['second_only']} ({float(t['p']):.3f})")
            name = "Pooled (stratified)" if q == "Stratified" else q
            lines.append(f"{label} & {name} & " + " & ".join(cs) + r" \\")
        lines.append(r"\midrule" if view == "all_calls" else "")
    lines = [ln for ln in lines if ln != ""]
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    return "\n".join(lines)


def tex_loki(loki: list[Row]) -> str:
    def get(src: str, metric: str, q: str) -> Row:
        return next(r for r in loki if r["source"] == src and r["metric"] == metric
                    and r["quartile"] == q)
    lines = [r"\begin{table*}[t]", r"\centering",
             r"\caption{Loki without a language model on the VerilogEval references, per "
             r"Gate-Breaker "
             r"quartile. Built: designs with the floor built (of 38, 39, 40, 39 references). "
             r"Coverage: mean per-design coverage on \code{f3} (label rows, \code{cell\_type}, HDL "
             r"span, module scopes, declared signals). AST and CFG: mean similarity of the "
             r"re-emitted Verilog to the reference (round~2); $n$ is the designs with an AST "
             r"value (references that pyverilog cannot parse are excluded, 21 in all, mostly "
             r"Q3 and Q4); the CFG mean is over the designs with a CFG value, so it can rest on "
             r"fewer designs.}",
             r"\label{tab:q-loki}", r"\footnotesize", r"\begin{tabular}{@{}lrrrr@{}}", r"\toprule",
             r"Measure & Q1 & Q2 & Q3 & Q4 \\", r"\midrule"]

    def line(label: str, src: str, metric: str) -> str:
        return label + " & " + " & ".join(get(src, metric, q)["value"] for q in QS) + r" \\"
    for fl in ("f1-k6", "f2", "f3"):
        lines.append(line(f"Built, \\code{{{fl}}}", "veval-l0 sizes", f"built_{fl}"))
    lines.append(r"\midrule")
    for col, label in (("label_cov", "Label coverage"),
                       ("cell_type_cov", "\\code{cell\\_type} coverage"),
                       ("hdl_cov", "HDL-span coverage"), ("module_cov", "Module coverage"),
                       ("signal_cov", "Signal coverage")):
        lines.append(line(label + ", \\code{f3}", "veval-l0 f3 ceiling", col))
    lines.append(r"\midrule")
    lines.append("AST/CFG $n$ (designs with an AST value) & " + " & ".join(
        get("round2 head-to-head", "f3-l0 ast_mean", q)["n"] for q in QS) + r" \\")
    for v, label in (("f3-l0", "L0-stop \\code{f3}"), ("f3-calib", "L1 calibrated \\code{f3}"),
                     ("f3-none", "L1 uncalibrated \\code{f3}"), ("f2-l0", "L0-stop \\code{f2}"),
                     ("f2-calib", "L1 calibrated \\code{f2}"),
                     ("f2-none", "L1 uncalibrated \\code{f2}")):
        for m, ml in (("ast_mean", "AST"), ("cfg_mean", "CFG")):
            lines.append(line(f"{label}, {ml}", "round2 head-to-head", f"{v} {m}"))
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table*}", ""]
    return "\n".join(lines)


def tex_hal(loki: list[Row]) -> str:
    lines = [r"\begin{table}[t]", r"\centering",
             r"\caption{Round~5b on the 33 VerilogEval test-split designs at \code{f2}, per "
             r"quartile: word matches at Jaccard 0.5 over predicted words and over ground-truth "
             r"words (matched/predicted/ground truth). Loki W: word-first detector; WB: with the "
             r"block rule; HAL: DANA. Quartiles hold 7 to 10 designs, and designs without a ground "
             r"truth word contribute zeros, so read these as counts, not rates.}",
             r"\label{tab:q-hal}", r"\footnotesize", r"\begin{tabular}{@{}lrccc@{}}", r"\toprule",
             r"Quartile & Designs & Loki W & Loki WB & HAL \\", r"\midrule"]
    for q in QS:
        rs = {t: next(r for r in loki if r["source"] == "hal VT f2" and r["quartile"] == q
                      and r["metric"] == f"{t} matched/n_pred/n_gt")
              for t in ("lokiW", "lokiWB", "hal8")}
        lines.append(f"{q} & {rs['lokiW']['n']} & " + " & ".join(
            rs[t]["value"] for t in ("lokiW", "lokiWB", "hal8")) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    return "\n".join(lines)


def tex_compare(comp: list[Row]) -> str:
    lines = [r"\begin{table*}[t]", r"\centering",
             r"\caption{Per quartile, the Loki-only flow and the language-model arms side by side. "
             r"Loki: calibrated \code{f3} L1 output against the reference, AST and CFG similarity "
             r"(round~2; $n$ designs with an AST value). Round-1 LLM: the Gate-Breaker harness "
             r"replication (Table~\ref{tab:veval}), same AST and CFG metric, on the designs both "
             r"are scored on; run for Q1 and Q2 only. Pilot arms: functional pass rate, all calls "
             r"(strict scorer), a different metric that is not comparable with AST or CFG. "
             r"Gate-Breaker's published numbers appear in the paper only as deltas "
             r"(Section~\ref{sec:gb-results}), so no absolute published column is shown.}",
             r"\label{tab:q-compare}", r"\footnotesize",
             r"\begin{tabular}{@{}lrcccccc@{}}", r"\toprule",
             r" & & \multicolumn{2}{c}{Loki-only (AST / CFG)} & Round-1 LLM & "
             r"\multicolumn{3}{c}{Pilot pass} \\",
             r"\cmidrule(lr){3-4}\cmidrule(lr){6-8}",
             r"Quartile & $n$ & AST & CFG & AST / CFG & A & B & C \\", r"\midrule"]
    for r in comp:
        llm = f"{r['round1_llm_ast']} / {r['round1_llm_cfg']}" if r["round1_llm_ast"] else "--"
        lines.append(f"{r['quartile']} & {r['loki_n']} & {r['loki_f3_ast']} & {r['loki_f3_cfg']} & "
                     f"{llm} & {r['pilot_pass_A']} & {r['pilot_pass_B']} & "
                     f"{r['pilot_pass_C']} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table*}", ""]
    return "\n".join(lines)


def build(outdir: Path, texout: Path) -> None:
    cells, tests = pilot_rows()
    loki = loki_only_rows()
    comp = compare_rows(cells, loki)
    write_csv(outdir / "pilot_cells.csv", cells)
    write_csv(outdir / "pilot_tests.csv", tests)
    write_csv(outdir / "loki_only.csv", loki)
    write_csv(outdir / "comparison.csv", comp)
    head = ("% Generated by experiments/quartiles/quartiles.py from committed result files; "
            "do not edit.\n"
            "% Sources: llm-pilot/selection.csv, llm-pilot/results/re/results.csv,\n"
            "% veval-l0/{benchmark,l0-ceiling-veval,sizes}.csv, round2/l2_headtohead.csv,\n"
            "% hal/results/scores-hal8.csv.\n\n")
    body = "\n".join([tex_pilot(cells), tex_tests(tests), tex_loki(loki), tex_hal(loki),
                      tex_compare(comp)])
    texout.write_text(head + body, encoding="utf-8", newline="\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--outdir", type=Path, default=HERE)
    ap.add_argument("--tex", type=Path, default=EXP.parent / "docs/paper/quartile-tables.tex")
    args = ap.parse_args()
    build(args.outdir, args.tex)


if __name__ == "__main__":
    main()
