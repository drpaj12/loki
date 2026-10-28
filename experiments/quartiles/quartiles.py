#!/usr/bin/env python3
"""Per-quartile (Gate-Breaker Q1-Q4) tables from committed result files; no model calls.

Primary partition: the Gate-Breaker quartile files
(gb-quartiles/{low,mid-low,mid-high,high}_quartile.txt, verbatim copies of
Gate-Breaker-verilog-eval/quartiles at commit
d60f0b10458746e2fefc2a98fa2455b77a32e8be, MIT; 144 problems, 41/36/36/31), the same files the
LLM pilot's selection.csv `quartile` column uses. Every per-quartile table uses it. The paper's
absolute-bin quartiles (veval-l0/benchmark.csv `quartile`) are kept only as the secondary table
tab:q-bins; 12 built designs are in no quartile file and are left out of the primary tables.

Inputs (committed): experiments/llm-pilot/{selection.csv,results/re/results.csv},
experiments/veval-l0/{benchmark.csv,l0-ceiling-veval.csv,sizes.csv}, gb-quartiles/*.txt,
round2_per_design.csv (per-design AST/CFG of round 2 and the round-1 LLM replication, extracted
once by ``--extract-round2`` from loki-exp2-data/l2/astcfg.json and
gatebreaker-exp2/data/results.json, the sources of round2/l2_headtohead.csv),
experiments/hal/results/scores-hal8.csv.

Outputs (deterministic, sorted rows, LF, UTF-8): CSVs in this directory and
docs/paper/quartile-tables.tex.

Tests: exact two-sided McNemar per quartile on paired binary pass/fail. Conditional on the
discordant pairs, the first-only count is Binomial(d, 1/2) under H0; the stratified exact test
sums the discordant counts over the quartiles; the sum of independent Binomial(d_i, 1/2) is
Binomial(sum d_i, 1/2), so the stratified test equals the overall exact McNemar test and is the
``All`` row (no separate Stratified rows). ``min_discordant`` is the least d for which an
all-one-sided split reaches p < 0.05 (independent of n).
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
QS = ("Q1", "Q2", "Q3", "Q4")
ARMS = ("A", "B", "C")
PAIRS = (("B", "A"), ("B", "C"), ("A", "C"))
GB_FILES = {"Q1": "low", "Q2": "mid-low", "Q3": "mid-high", "Q4": "high"}
VARIANTS = ("f3-l0", "f3-calib", "f3-none", "f2-l0", "f2-calib", "f2-none")
PER_DESIGN = HERE / "round2_per_design.csv"
# Reasons a reference is not built (experiments/veval-l0/EXPERIMENT.md "Result in one paragraph"
# and "Caveats"): Prob151 and Prob156 are skipped by Odin III's SystemVerilog reader (explicit
# 4-bit cast); Prob031, Prob046, Prob078, Prob145 fail Loki's own equivalence gate.
NOT_BUILT = {"Prob151_review2015_fsm": "odin3 reader", "Prob156_review2015_fancytimer":
             "odin3 reader", "Prob031_dff": "equivalence gate", "Prob046_dff8p":
             "equivalence gate", "Prob078_dualedge": "equivalence gate",
             "Prob145_circuit8": "equivalence gate"}
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


# ---- partitions -------------------------------------------------------------------------


def gb_problems() -> dict[str, str]:
    """Problem -> Gate-Breaker quartile, from the committed copies of the quartile files."""
    out: dict[str, str] = {}
    for q, name in GB_FILES.items():
        path = HERE / "gb-quartiles" / f"{name}_quartile.txt"
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out[line.strip()] = q
    return out


def design_problem() -> dict[str, str]:
    return {r["design"]: r["problem"] for r in read(EXP / "veval-l0/benchmark.csv")}


def gb_part() -> dict[str, str]:
    """Design -> Gate-Breaker quartile (built designs that are in a quartile file)."""
    gb = gb_problems()
    return {d: gb[p] for d, p in design_problem().items() if p in gb}


def bench_part() -> dict[str, str]:
    """Design -> the paper's absolute-bin quartile (veval-l0/benchmark.csv), secondary only."""
    return {r["design"]: r["quartile"] for r in read(EXP / "veval-l0/benchmark.csv")}


def crosstab() -> list[Row]:
    gb, bench = gb_part(), bench_part()
    out: list[Row] = []
    for b in QS:
        for g in (*QS, "none"):
            n = sum(1 for d in bench if bench[d] == b and gb.get(d, "none") == g)
            out.append({"bin_quartile": b, "gb_quartile": g, "designs": str(n)})
    return out


def not_built() -> list[Row]:
    gb = gb_problems()
    built = set(design_problem().values())
    return [{"problem": p, "gb_quartile": gb[p], "reason": NOT_BUILT.get(p, "UNEXPLAINED")}
            for p in sorted(gb) if p not in built]


# ---- pilot ------------------------------------------------------------------------------


def pilot_outcomes() -> tuple[dict[str, str], dict[tuple[str, str], int]]:
    quart = {r["problem"]: r["quartile"] for r in read(EXP / "llm-pilot/selection.csv")}
    res = {(r["arm"], r["problem"]): int(r["pass"])
           for r in read(EXP / "llm-pilot/results/re/results.csv")}
    return quart, res


def pilot_rows() -> tuple[list[Row], list[Row]]:
    quart, res = pilot_outcomes()
    cells: list[Row] = []
    tests: list[Row] = []
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
    return cells, tests


# ---- Loki-only --------------------------------------------------------------------------


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def extract_round2(astcfg: Path, results: Path) -> None:
    """Write round2_per_design.csv from the round-2 AST/CFG scores and the round-1 LLM results
    (the two inputs of round2/l2_report.py headtohead); run once, the CSV is committed."""
    loki = json.loads(astcfg.read_text(encoding="utf-8"))
    llm = {f"ve_{str(d['design']).removesuffix('_ref')}": d
           for d in json.loads(results.read_text(encoding="utf-8"))["designs"]}
    dp = design_problem()
    rows: list[Row] = []
    for r in sorted(loki, key=lambda x: str(x["design"])):
        d = str(r["design"])
        row: Row = {"design": d, "problem": dp[d]}
        for m in ("ast", "cfg"):
            v = llm.get(d, {}).get(m)
            row[f"llm_{m}"] = "" if v is None else repr(float(v))
        for v_ in VARIANTS:
            for m in ("ast", "cfg"):
                x = r.get(f"{v_}:{m}")
                row[f"{v_}_{m}"] = "" if x is None else repr(float(x))
        rows.append(row)
    write_csv(PER_DESIGN, rows)


def loki_only_rows(part: dict[str, str]) -> list[Row]:
    """Loki-only measures per quartile of ``part`` (design -> quartile)."""
    out: list[Row] = []
    ceil = read(EXP / "veval-l0/l0-ceiling-veval.csv")
    for q in QS:
        rs = [r for r in ceil if part.get(r["design"]) == q]
        for col in ("label_cov", "cell_type_cov", "hdl_cov", "module_cov", "signal_cov"):
            vals = [float(r[col]) for r in rs]
            for stat, v in (("mean", mean(vals)), ("median", statistics.median(vals))):
                out.append({"source": "veval-l0 f3 ceiling", "metric": f"{col} {stat}",
                            "quartile": q, "n": str(len(rs)), "value": f"{v:.3f}"})
    sizes = read(EXP / "veval-l0/sizes.csv")
    for fl in ("f1-k6", "f2", "f3"):
        for q in QS:
            n = sum(1 for r in sizes if r["floor"] == fl and part.get(r["design"]) == q)
            out.append({"source": "veval-l0 sizes", "metric": f"built_{fl}", "quartile": q,
                        "n": str(n), "value": str(n)})
    pd = read(PER_DESIGN)
    for q in QS:
        in_q = [r for r in pd if part.get(r["design"]) == q]
        for sel in ("all", "common"):
            rs = [r for r in in_q if sel == "all" or r["llm_ast"] != ""]
            for name in ("llm", *VARIANTS):
                if name == "llm" and sel == "all":
                    continue
                for m in ("ast", "cfg"):
                    vals = [float(r[f"{name}_{m}"]) for r in rs if r[f"{name}_{m}"] != ""]
                    out.append({"source": "round2 per design", "metric": f"{sel} {name} {m}_mean",
                                "quartile": q, "n": str(len(vals)),
                                "value": f"{mean(vals):.3f}" if vals else ""})
    hal = [r for r in read(EXP / "hal/results/scores-hal8.csv")
           if r["set"] == "VT" and r["floor"] == "f2"]
    for tool in ("lokiW", "lokiWB", "hal8"):
        for q in QS:
            rs = [r for r in hal if r["tool"] == tool and part.get(r["design"]) == q]
            nm, npred, ngt = (sum(int(r[k]) for r in rs) for k in ("matched", "n_pred", "n_gt"))
            out.append({"source": "hal VT f2", "metric": f"{tool} matched/n_pred/n_gt",
                        "quartile": q, "n": str(len(rs)), "value": f"{nm}/{npred}/{ngt}"})
    return out


def get(rows: list[Row], src: str, metric: str, q: str) -> Row:
    return next(r for r in rows if r["source"] == src and r["metric"] == metric
                and r["quartile"] == q)


def compare_rows(cells: list[Row], loki: list[Row]) -> list[Row]:
    """Common set (designs scored by both the round-1 LLM and Loki), Gate-Breaker quartiles."""
    out: list[Row] = []
    for q in QS:
        def g(metric: str, q: str = q) -> Row:
            return get(loki, "round2 per design", metric, q)
        la, lc = g("common f3-calib ast_mean"), g("common f3-calib cfg_mean")
        ma, mc = g("common llm ast_mean"), g("common llm cfg_mean")
        row: Row = {"quartile": q, "loki_n_ast": la["n"], "llm_n_ast": ma["n"],
                    "loki_n_cfg": lc["n"], "llm_n_cfg": mc["n"], "loki_f3_ast": la["value"],
                    "loki_f3_cfg": lc["value"], "round1_llm_ast": ma["value"],
                    "round1_llm_cfg": mc["value"]}
        cell = next(r for r in cells if r["quartile"] == q and r["view"] == "all_calls")
        row["pilot_n"] = cell["n"]
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


# ---- LaTeX ------------------------------------------------------------------------------


def frac(k: str, n: str) -> str:
    return f"{k}/{n}"


def tex_pilot(cells: list[Row]) -> str:
    lines = [r"\begin{table}[t]", r"\centering",
             r"\caption{LLM pilot (run \code{re}) pass rate per Gate-Breaker complexity "
             r"quartile (the quartile files), strict "
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
             r"\caption{LLM pilot (run \code{re}): exact two-sided McNemar test per quartile, "
             r"strict scorer. Cells "
             r"are first-only/second-only discordant pairs (all-calls view in the first group, "
             r"paired view in the second); $p$ in brackets. The All row pools the discordant pairs "
             r"of Q1--Q4; it is also the stratified exact test, because the sum of independent "
             r"Binomial($d_i$, 1/2) counts is Binomial($\sum d_i$, 1/2). A two-sided exact test "
             r"needs at least 6 discordant pairs, all in one direction, for $p<0.05$.}",
             r"\label{tab:q-tests}", r"\footnotesize", r"\begin{tabular}{@{}llccc@{}}", r"\toprule",
             r"View & Stratum & B vs A & B vs C & A vs C \\", r"\midrule"]
    for view, label in (("all_calls", "all calls"), ("paired", "paired")):
        for q in (*QS, "All"):
            cs = []
            for x, y in PAIRS:
                t = next(r for r in tests if r["quartile"] == q and r["view"] == view
                         and r["comparison"] == f"{x} vs {y}")
                cs.append(f"{t['first_only']}/{t['second_only']} ({float(t['p']):.3f})")
            name = r"All (strat.)" if q == "All" else q
            lines.append(f"{label} & {name} & " + " & ".join(cs) + r" \\")
        lines.append(r"\midrule" if view == "all_calls" else "")
    lines = [ln for ln in lines if ln != ""]
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    return "\n".join(lines)


def tex_loki(loki: list[Row], refs: dict[str, int], nb: list[Row]) -> str:
    cnt = {q: sum(1 for r in nb if r["gb_quartile"] == q) for q in QS}
    detail = ", ".join(f"{cnt[q]} in {q}" for q in QS if cnt[q])
    reasons = sorted({r["reason"] for r in nb})
    n_reader = sum(1 for r in nb if r["reason"] == "odin3 reader")
    n_gate = sum(1 for r in nb if r["reason"] == "equivalence gate")
    lines = [r"\begin{table*}[t]", r"\centering",
             r"\caption{Loki without a language model on the VerilogEval references, per "
             r"Gate-Breaker quartile (the quartile files; 12 built designs that are in no quartile "
             r"file are left out). References: problems in the quartile file ("
             + ", ".join(str(refs[q]) for q in QS) + r"). Built: designs with the floor built; "
             f"the {len(nb)} references that are not built ({detail}) are "
             f"{n_reader} that Odin III's SystemVerilog reader skips (an explicit cast) and "
             f"{n_gate} that fail Loki's own equivalence gate, see the veval-l0 record. "
             r"Coverage: per-design coverage on \code{f3} (label rows, \code{cell\_type}, HDL "
             r"span, module scopes, declared signals), mean (median). Signal coverage "
             r"exceeds 1 for \code{ve\_Prob080\_timer} (5 recovered against 4 declared; "
             r"flattened array elements add names). AST and CFG: mean similarity of the "
             r"re-emitted Verilog to the reference (round~2); $n$ is the designs with a value "
             r"(references that pyverilog cannot parse have no AST value), so the CFG mean can "
             r"rest on fewer designs.}",
             r"\label{tab:q-loki}", r"\footnotesize", r"\begin{tabular}{@{}lrrrr@{}}", r"\toprule",
             r"Measure & Q1 & Q2 & Q3 & Q4 \\", r"\midrule"]
    assert reasons
    lines.append("References in the quartile file & " + " & ".join(str(refs[q]) for q in QS)
                 + r" \\")
    for fl in ("f1-k6", "f2", "f3"):
        lines.append(f"Built, \\code{{{fl}}} & " + " & ".join(
            get(loki, "veval-l0 sizes", f"built_{fl}", q)["value"] for q in QS) + r" \\")
    lines.append(r"\midrule")
    for col, label in (("label_cov", "Label coverage"),
                       ("cell_type_cov", "\\code{cell\\_type} coverage"),
                       ("hdl_cov", "HDL-span coverage"), ("module_cov", "Module coverage"),
                       ("signal_cov", "Signal coverage")):
        cells = [f"{get(loki, 'veval-l0 f3 ceiling', col + ' mean', q)['value']} "
                 f"({get(loki, 'veval-l0 f3 ceiling', col + ' median', q)['value']})"
                 for q in QS]
        lines.append(label + ", \\code{f3} & " + " & ".join(cells) + r" \\")
    lines.append(r"\midrule")
    for m, ml in (("ast", "AST"), ("cfg", "CFG")):
        art = "an" if ml == "AST" else "a"
        lines.append(f"$n$ (designs with {art} {ml} value) & " + " & ".join(
            get(loki, "round2 per design", f"all f3-calib {m}_mean", q)["n"] for q in QS)
            + r" \\")
    for v, label in (("f3-l0", "L0-stop \\code{f3}"), ("f3-calib", "L1 calibrated \\code{f3}"),
                     ("f3-none", "L1 uncalibrated \\code{f3}"), ("f2-l0", "L0-stop \\code{f2}"),
                     ("f2-calib", "L1 calibrated \\code{f2}"),
                     ("f2-none", "L1 uncalibrated \\code{f2}")):
        for m, ml in (("ast", "AST"), ("cfg", "CFG")):
            lines.append(f"{label}, {ml} & " + " & ".join(
                get(loki, "round2 per design", f"all {v} {m}_mean", q)["value"]
                for q in QS) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table*}", ""]
    return "\n".join(lines)


def hal_ns(loki: list[Row]) -> list[int]:
    return [int(get(loki, "hal VT f2", "lokiW matched/n_pred/n_gt", q)["n"]) for q in QS]


def tex_hal(loki: list[Row]) -> str:
    ns = hal_ns(loki)
    lines = [r"\begin{table}[t]", r"\centering",
             r"\caption{Round~5b on the VerilogEval test-split designs at \code{f2} that are in a "
             f"Gate-Breaker quartile file ({sum(ns)} of the 33), per quartile: word matches at "
             r"Jaccard 0.5 over predicted words and over ground-truth "
             r"words (matched/predicted/ground truth). Loki W: word-first detector; WB: with the "
             f"block rule; HAL: DANA. Quartiles hold {min(ns)} to {max(ns)} designs, and designs "
             r"without a ground truth word contribute zeros, so read these as counts, not "
             r"rates.}",
             r"\label{tab:q-hal}", r"\footnotesize", r"\begin{tabular}{@{}lrccc@{}}", r"\toprule",
             r"Quartile & Designs & Loki W & Loki WB & HAL \\", r"\midrule"]
    for q in QS:
        rs = {t: get(loki, "hal VT f2", f"{t} matched/n_pred/n_gt", q)
              for t in ("lokiW", "lokiWB", "hal8")}
        lines.append(f"{q} & {rs['lokiW']['n']} & " + " & ".join(
            rs[t]["value"] for t in ("lokiW", "lokiWB", "hal8")) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    return "\n".join(lines)


def tex_compare(comp: list[Row]) -> str:
    lines = [r"\begin{table*}[t]", r"\centering",
             r"\caption{Per Gate-Breaker quartile, the Loki-only flow and the language-model arms "
             r"side by side. Loki and Round-1 LLM are both taken on the common set, the designs "
             r"scored by the round-1 Gate-Breaker harness replication (Table~\ref{tab:veval}) and "
             r"by Loki, with the same AST and CFG metric; Loki is the calibrated \code{f3} L1 "
             r"output (round~2). $n$ is the common designs with an AST value; $n_{\mathrm{CFG}}$ "
             r"is the designs with a CFG value for Loki / the round-1 model. A dash is a quartile "
             r"with no common design. Pilot arms: functional pass rate, all calls (strict "
             r"scorer), $n$ problems, a different metric that is not comparable with AST or CFG. "
             r"Gate-Breaker's published numbers appear in the paper only as deltas "
             r"(Section~\ref{sec:gb-results}), so no absolute published column is shown.}",
             r"\label{tab:q-compare}", r"\footnotesize",
             r"\begin{tabular}{@{}lccccccrccc@{}}", r"\toprule",
             r" & \multicolumn{4}{c}{Common set, Loki} & \multicolumn{2}{c}{Round-1 LLM} & "
             r"\multicolumn{4}{c}{Pilot pass} \\",
             r"\cmidrule(lr){2-5}\cmidrule(lr){6-7}\cmidrule(lr){8-11}",
             r"Quartile & $n_{\mathrm{AST}}$ & $n_{\mathrm{CFG}}$ & AST & CFG & AST & CFG & "
             r"$n$ & A & B & C \\",
             r"\midrule"]
    for r in comp:
        lines.append(f"{r['quartile']} & {r['loki_n_ast']} / {r['llm_n_ast']} & "
                     f"{r['loki_n_cfg']} / {r['llm_n_cfg']} & "
                     f"{r['loki_f3_ast']} & {r['loki_f3_cfg']} & {r['round1_llm_ast']} & "
                     f"{r['round1_llm_cfg']} & {r['pilot_n']} & {r['pilot_pass_A']} & "
                     f"{r['pilot_pass_B']} & {r['pilot_pass_C']} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table*}", ""]
    return "\n".join(lines)


def tex_bins(loki_b: list[Row], xt: list[Row]) -> str:
    def cell(b: str, g: str) -> int:
        return int(next(r for r in xt if r["bin_quartile"] == b
                        and r["gb_quartile"] == g)["designs"])
    total = sum(cell(b, g) for b in QS for g in (*QS, "none"))
    agree = sum(cell(b, b) for b in QS)
    none = sum(cell(b, "none") for b in QS)
    differ = total - none - agree
    lines = [r"\begin{table*}[t]", r"\centering",
             r"\caption{Secondary view: the same Loki-only measures per quartile of the paper's "
             r"absolute complexity bins (Table~\ref{tab:veval}), not of the Gate-Breaker quartile "
             f"files. Of the {total} built designs, {none} are in no quartile file and {differ} of "
             f"the other {total - none} sit in a different quartile in the two partitions "
             r"(cross-tabulation in \code{partition\_crosstab.csv}). Cells as in "
             r"Table~\ref{tab:q-loki}; HAL cells are Loki W matched/predicted/ground truth. "
             r"The Q4 signal-coverage mean includes \code{ve\_Prob153\_gshare}: 140 recovered "
             r"signals against 15 declared (reference method: regex), a ratio of 9.33. The regex "
             r"extractor does not undercount the source declarations (15 names: 11 ports, 3 "
             r"internal nets, the array \code{pht}, counted once); the recovered count is "
             r"consistent with the 128-entry array \code{pht} (\code{2**n}, $n=7$) flattened "
             r"into elements plus 12 other names, but the recovered signal list itself was not "
             r"inspected.}",
             r"\label{tab:q-bins}", r"\footnotesize", r"\begin{tabular}{@{}lrrrr@{}}", r"\toprule",
             r"Measure & Q1 & Q2 & Q3 & Q4 \\", r"\midrule",
             "Built designs, \\code{f3} & " + " & ".join(
                 get(loki_b, "veval-l0 sizes", "built_f3", q)["value"] for q in QS) + r" \\",
             "Signal coverage, \\code{f3} & " + " & ".join(
                 f"{get(loki_b, 'veval-l0 f3 ceiling', 'signal_cov mean', q)['value']} "
                 f"({get(loki_b, 'veval-l0 f3 ceiling', 'signal_cov median', q)['value']})"
                 for q in QS) + r" \\"]
    for m, ml in (("ast", "AST"), ("cfg", "CFG")):
        lines.append(f"{ml} $n$, L1 calibrated \\code{{f3}} & " + " & ".join(
            get(loki_b, "round2 per design", f"all f3-calib {m}_mean", q)["n"]
            for q in QS) + r" \\")
        lines.append(f"{ml}, L1 calibrated \\code{{f3}} & " + " & ".join(
            get(loki_b, "round2 per design", f"all f3-calib {m}_mean", q)["value"]
            for q in QS) + r" \\")
    lines.append("HAL designs & " + " & ".join(
        get(loki_b, "hal VT f2", "lokiW matched/n_pred/n_gt", q)["n"] for q in QS) + r" \\")
    lines.append("Loki W, matched/pred/GT & " + " & ".join(
        get(loki_b, "hal VT f2", "lokiW matched/n_pred/n_gt", q)["value"] for q in QS) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table*}", ""]
    return "\n".join(lines)


def build(outdir: Path, texout: Path) -> None:
    cells, tests = pilot_rows()
    loki = loki_only_rows(gb_part())
    loki_b = loki_only_rows(bench_part())
    comp = compare_rows(cells, loki)
    xt = crosstab()
    nb = not_built()
    gb = gb_problems()
    refs = {q: sum(1 for v in gb.values() if v == q) for q in QS}
    write_csv(outdir / "pilot_cells.csv", cells)
    write_csv(outdir / "pilot_tests.csv", tests)
    write_csv(outdir / "loki_only.csv", loki)
    write_csv(outdir / "loki_only_bins.csv", loki_b)
    write_csv(outdir / "comparison.csv", comp)
    write_csv(outdir / "partition_crosstab.csv", xt)
    write_csv(outdir / "not_built.csv", nb)
    head = ("% Generated by experiments/quartiles/quartiles.py from committed result files; "
            "do not edit.\n"
            "% Sources: gb-quartiles/*.txt, llm-pilot/selection.csv, "
            "llm-pilot/results/re/results.csv,\n"
            "% veval-l0/{benchmark,l0-ceiling-veval,sizes}.csv, "
            "quartiles/round2_per_design.csv,\n"
            "% hal/results/scores-hal8.csv.\n\n")
    body = "\n".join([tex_pilot(cells), tex_tests(tests), tex_loki(loki, refs, nb),
                      tex_hal(loki), tex_compare(comp), tex_bins(loki_b, xt)])
    texout.write_text(head + body, encoding="utf-8", newline="\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--outdir", type=Path, default=HERE)
    ap.add_argument("--tex", type=Path, default=EXP.parent / "docs/paper/quartile-tables.tex")
    ap.add_argument("--extract-round2", nargs=2, type=Path, metavar=("ASTCFG_JSON", "RESULTS_JSON"),
                    help="write round2_per_design.csv from loki-exp2-data/l2/astcfg.json and "
                    "gatebreaker-exp2/data/results.json, then exit")
    args = ap.parse_args()
    if args.extract_round2:
        extract_round2(*args.extract_round2)
        return
    build(args.outdir, args.tex)


if __name__ == "__main__":
    main()
