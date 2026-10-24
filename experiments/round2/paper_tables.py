#!/usr/bin/env python3
"""Write docs/paper/round2-tables.tex from the committed round-2 CSVs.

The file holds the round-2 tables (tab:r2-*), the research-log table (tab:r2-log) and a macro
for every deciding number the prose cites (``\\rt...``), so no number in the paper's round-2
text is typed by hand. The status of each hypothesis is computed here with the decision rules of
EXPERIMENT.md (thresholds set by the implementer during the round). No timestamps and no
environment: a rerun reproduces the file byte for byte.

Usage: paper_tables.py [--out PATH]
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE.parents[1] / "docs" / "paper" / "round2-tables.tex"
MACROS: dict[str, str] = {}
# Decision thresholds of EXPERIMENT.md (set by the implementer during the round).
THR_L1_SUPPORT, THR_L1_REJECT = 0.8, 0.5
THR_L4_GAP, THR_L4_SHARE = 0.02, 0.8
THR_L5B_FRAC = 0.3


def rows(name: str) -> list[dict[str, str]]:
    with (HERE / name).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def num(x: str) -> float | None:
    return float(x) if x not in ("", "None") else None


def f3(x: float | None, digits: int = 3) -> str:
    return "--" if x is None else f"{x:.{digits}f}".replace("-", "$-$")


def fi(x: float | int | str) -> str:
    return f"{int(float(x)):,}".replace(",", "{,}")


def macro(name: str, value: str) -> None:
    MACROS[name] = value


def tex(text: str) -> str:
    return text.replace("_", r"\_")


def table(caption: str, label: str, head: list[str], body: list[list[str]], spec: str,
          star: bool = False) -> str:
    env = "table*" if star else "table"
    lines = [rf"\begin{{{env}}}[t]", rf"\caption{{{caption}}}", rf"\label{{{label}}}",
             r"\centering", r"\footnotesize", r"\resizebox{\columnwidth}{!}{%",
             rf"\begin{{tabular}}{{@{{}}{spec}@{{}}}}",
             r"\toprule", " & ".join(head) + r" \\", r"\midrule"]
    for r in body:
        lines.append(r"\midrule" if r == ["---"] else " & ".join(r) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}}", rf"\end{{{env}}}"]
    return "\n".join(lines)


def verdict(status: str) -> str:
    return {"S": "supported", "N": "not supported", "I": "inconclusive"}[status]


def verdict_l7(status: str) -> str:
    """RQ-L7 holds by the letter of its rule only; the evidence is weak (see EXPERIMENT.md)."""
    return "supported by the letter of the rule (weak evidence)" if status == "S" \
        else verdict(status)


# ------------------------------------------------------------------------------------------ L1
def l1_block() -> tuple[str, str]:
    s = {r["set"]: r for r in rows("l1_summary.csv")}

    def get(name: str, key: str) -> float | None:
        return num(s[name][key])

    ratios = {}
    for split in ("test", "all"):
        lut, nat = get(f"lut-calib-{split}", "micro_f1"), get(f"native-calib-{split}", "micro_f1")
        ratios[split] = None if not nat or lut is None else lut / nat
        macro(f"rtLone{split.capitalize()}Ratio", f3(ratios[split], 2))
        macro(f"rtLone{split.capitalize()}Lut", f3(lut))
        macro(f"rtLone{split.capitalize()}Native", f3(nat))
    macro("rtLoneThr", f"{THR_L1_SUPPORT:g}")
    macro("rtLoneDesigns", s["lut-calib-all"]["runs"])
    macro("rtLoneTestDesigns", s["lut-calib-test"]["runs"])
    macro("rtLoneGateMatched", fi(s["gate-calib-test"]["matched"]))
    macro("rtLoneGateGt", fi(s["gate-calib-test"]["gt"]))
    macro("rtLoneLutMatchedTest", fi(s["lut-calib-test"]["matched"]))
    macro("rtLoneNativeMatchedTest", fi(s["native-calib-test"]["matched"]))
    macro("rtLoneLutMatchedAll", fi(s["lut-calib-all"]["matched"]))
    macro("rtLoneNativeMatchedAll", fi(s["native-calib-all"]["matched"]))
    macro("rtLoneLutCountedAll", fi(s["lut-calib-all"]["counted"]))
    macro("rtLoneNativeCountedAll", fi(s["native-calib-all"]["counted"]))
    macro("rtLoneGtAll", fi(s["lut-calib-all"]["gt"]))
    cov = rows("l1_cover.csv")
    luts = sum(int(r["luts"]) for r in cov)
    nomatch = sum(int(r["no_net_match"]) for r in cov)
    macro("rtLoneLuts", fi(luts))
    macro("rtLoneNoMatch", fi(nomatch))
    macro("rtLoneNoMatchFrac", f3(nomatch / luts, 3))
    macro("rtLoneEmpty", fi(sum(int(r["empty_cover"]) for r in cov)))
    vals = [ratios["test"], ratios["all"]]
    if any(v is None for v in vals):
        st = "I"
    elif all(v >= THR_L1_SUPPORT for v in vals if v is not None):
        st = "S"
    elif all(v < THR_L1_REJECT for v in vals if v is not None):
        st = "N"
    else:
        st = "I"
    macro("rtLoneStatus", verdict(st))
    body = []
    for label, key in (("f3 gate netlist", "gate"), ("f3 re-mapped to LUT6", "lut"),
                       ("f2 floor (native LUT6)", "native")):
        for cond, cname in (("calib", "calibrated"), ("none", "uncalibrated")):
            for split in ("test", "all"):
                name = f"{key}-{cond}-{split}"
                if name not in s:
                    continue
                r = s[name]
                body.append([label if (cond, split) == ("calib", "test") else "", cname, split,
                             r["runs"], fi(r["counted"]), fi(r["matched"]), fi(r["gt"]),
                             f3(num(r["micro_f1"])), f3(num(r["macro_f1"]))])
        body.append(["---"])
    body.pop()
    tab = table(
        r"Round-2 L1 (RQ-L1): recovery from the f3 gate netlist re-mapped to LUT6 against the "
        r"native f2 floor, same 65 micro designs. \code{test} is the 15 held-out designs, "
        r"\code{all} the 65. Calibration: the micro-fit f2 table (gate rows: the f3 table). Hard "
        r"kinds excluded from counts and averages; macro-F1 averages the kinds with a counted "
        r"prediction.",
        "tab:r2-l1", ["Netlist", "Calib.", "Split", "Runs", "Counted", "Matched", "GT",
                      "micro-F1", "macro-F1"], body, "llrrrrrrr")
    return tab, st


# ------------------------------------------------------------------------------------------ L7
def l7_block() -> tuple[str, str]:
    sets = {r["set"]: r for r in rows("l7_sets.csv")}
    ties = {r["condition"]: r for r in rows("l7_ties.csv")}
    for key, name in (("Fonek", "rename-f1-k6-calib"), ("Ftwo", "rename-f2-calib"),
                      ("Fthree", "f3exp-f3-calib")):
        macro(f"rtLsevenType{key}", f3(num(sets[name]["type_f1"])))
    cal, unc, flat = (ties["L1 calibrated"], ties["L1 uncalibrated"],
                      ties["L1 uncalibrated, flattened"])
    d_ast = float(unc["ast_mean"]) - float(cal["ast_mean"])
    d_cfg = float(unc["cfg_mean"]) - float(cal["cfg_mean"])
    d_f1 = float(unc["type_f1"]) - float(cal["type_f1"])
    f_ast = float(flat["ast_mean"]) - float(unc["ast_mean"])
    f_cfg = float(flat["cfg_mean"]) - float(unc["cfg_mean"])
    f_f1 = float(flat["type_f1"]) - float(unc["type_f1"])
    macro("rtLsevenDAst", f3(d_ast, 4))
    macro("rtLsevenDCfg", f3(d_cfg, 4))
    macro("rtLsevenDF", f3(d_f1, 4))
    macro("rtLsevenFAst", f3(f_ast, 4))
    macro("rtLsevenFCfg", f3(f_cfg, 4))
    macro("rtLsevenFF", f3(f_f1, 4))
    tie = abs(d_ast) < 0.02 and abs(d_cfg) < 0.02 and abs(d_f1) >= 0.01
    flatok = f_ast >= 0.04 and f_cfg >= 0.04 and abs(f_f1) == 0
    st = "S" if tie and flatok else ("N" if not tie and not flatok else "I")
    macro("rtLsevenStatus", verdict_l7(st))
    order = [("rename-f1-k6-calib", "f1-k6, calibrated"), ("rename-f1-k6-nocalib", "f1-k6, none"),
             ("rename-f2-calib", "f2, calibrated"), ("rename-f2-nocalib", "f2, none"),
             ("f3exp-f3-calib", "f3 gates, calibrated"), ("f3exp-f3-nocalib", "f3 gates, none"),
             ("l1-lut-calib", "f3 as LUT6, calibrated"), ("l1-lut-none", "f3 as LUT6, none"),
             ("l2-f2-calib", "VerilogEval f2, calibrated"), ("l2-f2-none", "VerilogEval f2, none"),
             ("l2-f3-calib", "VerilogEval f3, calibrated"), ("l2-f3-none", "VerilogEval f3, none")]
    body = [[lab, sets[k]["designs"], fi(sets[k]["key_ops"]), fi(sets[k]["got_ops"]),
             f3(num(sets[k]["type_p"])), f3(num(sets[k]["type_r"])), f3(num(sets[k]["type_f1"])),
             f3(num(sets[k]["tw_f1"]))] for k, lab in order if k in sets]
    t1 = table(
        r"Operator-recovery F1 (RQ-L7) of the existing and new L1 runs: the multiset of "
        r"recovered operators (class and operand width) against the operators of the L0 key, "
        r"pooled over designs. \code{type} ignores the width, \code{tw} requires it.",
        "tab:r2-l7", ["Run set", "Designs", "Key ops", "Got ops", "P", "R", "type-F1", "tw-F1"],
        body, "lrrrrrrr")
    tbody = [[c, f3(num(ties[c]["ast_mean"]), 4), f3(num(ties[c]["cfg_mean"]), 4),
              fi(ties[c]["got_ops"]), f3(num(ties[c]["type_f1"]), 4)]
             for c in ("L0-stop gate netlist", "L1 calibrated", "L1 uncalibrated",
                       "L1 uncalibrated, flattened")]
    t2 = table(
        r"AST and CFG similarity against operator F1 on the 15 f3 test designs (the "
        r"f3-recovery runs). Calibrated and uncalibrated L1 tie on AST and CFG; the flatten "
        r"control moves both and leaves the recovery record unchanged.",
        "tab:r2-ties", ["Condition", "AST", "CFG", "Ops recovered", "type-F1"], tbody, "lrrrr")
    return t1 + "\n\n" + t2, st


# ------------------------------------------------------------------------------------------ L4
def l4_block() -> tuple[str, str]:
    a = {r["ablation"]: r for r in rows("l4_ablation.csv")}
    full, prior = float(a["full"]["micro_f1"]), float(a["priors-only"]["micro_f1"])
    drops = {k: full - float(a[f"drop-{k}"]["micro_f1"]) for k in ("npn", "wl", "struct")}
    top2 = sum(sorted(drops.values(), reverse=True)[:2])
    gap = full - prior
    ng = {r["ablation"]: r for r in rows("l4_nogshare.csv")}
    ng_full, ng_prior = float(ng["full"]["micro_f1"]), float(ng["priors-only"]["micro_f1"])
    macro("rtLfourNgFull", f3(ng_full, 4))
    macro("rtLfourNgPriors", f3(ng_prior, 4))
    macro("rtLfourNgNone", f3(num(ng["none"]["micro_f1"]), 4))
    macro("rtLfourNgGap", f3(ng_full - ng_prior, 4))
    macro("rtLfourNgGt", fi(ng["full"]["gt"]))
    macro("rtLfourFull", f3(full, 4))
    macro("rtLfourPriors", f3(prior, 4))
    macro("rtLfourNone", f3(num(a["none"]["micro_f1"]), 4))
    macro("rtLfourGap", f3(gap, 4))
    macro("rtLfourAucFull", f3(num(a["full"]["auc"])))
    macro("rtLfourAucNone", f3(num(a["none"]["auc"])))
    macro("rtLfourThr", f"{THR_L4_GAP:g}")
    macro("rtLfourHeld", a["full"]["runs"])
    macro("rtLfourGt", fi(a["full"]["gt"]))
    st = "I" if gap < THR_L4_GAP else ("S" if top2 >= THR_L4_SHARE * gap else "N")
    macro("rtLfourStatus", verdict(st))
    names = [("none", "defaults (no calibration)"), ("full", "full calibration"),
             ("drop-npn", "without npn"), ("drop-wl", "without wl"),
             ("drop-struct", "without struct"), ("priors-only", "priors only")]
    body = []
    for k, lab in names:
        r = a[k]
        body.append([lab, fi(r["counted"]), fi(r["matched"]), f3(num(r["micro_f1"]), 4),
                     f"{f3(num(r['micro_f1_lo']), 4)}--{f3(num(r['micro_f1_hi']), 4)}",
                     f3(num(ng[k]["micro_f1"]), 4), f3(num(r["macro_f1"])), f3(num(r["ece"])),
                     f3(num(r["auc"]))])
    tab = table(
        r"Evidence-family ablation (RQ-L4) on the 49 held-out f2 designs (16 micro, 33 "
        r"VerilogEval). Each row refits the calibration on the 169 train designs with the family "
        r"removed (its weight set to 0). The \code{l2} family has no feature in \code{loki re} and "
        r"is not applicable. The interval is a 95\% design bootstrap of micro-F1 "
        r"(hard kinds excluded); the next column is micro-F1 with the design "
        r"\code{ve\_Prob153\_gshare} (about 1{,}300 of the 1{,}558 instances) left out.",
        "tab:r2-l4", ["Calibration", "Counted", "Matched", "micro-F1", "95\\% interval",
                      "w/o gshare", "macro-F1", "ECE", "AUC"], body, "lrrrrrrrr")
    return tab, st


# ------------------------------------------------------------------------------------------ L5
def l5_block() -> tuple[str, str, str]:
    corr = {(r["set"], r["variable"]): r for r in rows("l5_corr.csv")}
    snd = {r["set"]: r for r in rows("l5_soundness.csv")}
    pre = rows("l5_prefilter.csv")
    prim = corr[("l2-f2-none", "width")]
    sec = corr.get(("l2-f2-calib-rp0.1", "width"))
    rho, p = num(prim["spearman"]), num(prim["p"])
    macro("rtLfiveRho", f3(rho, 3))
    macro("rtLfiveP", f3(p, 3))
    macro("rtLfiveN", prim["designs_with_gt"])
    sec_rho = num(sec["spearman"]) if sec else None
    macro("rtLfiveRhoCal", f3(sec_rho, 3))
    macro("rtLfiveRhoMust", f3(num(corr[("l2-f2-none", "must")]["spearman"]), 3))
    macro("rtLfiveMustPrec", f3(num(snd["l2-f2-none"]["must_precision"]), 3))
    macro("rtLfiveMayRec", f3(num(snd["l2-f2-none"]["may_recall"]), 3))
    macro("rtLfiveMustRec", f3(num(snd["l2-f2-none"]["must_recall"]), 3))
    if rho is None or p is None:
        sta = "I"
    elif rho <= -0.2 and p < 0.05 and (sec_rho is None or sec_rho < 0):
        sta = "S"
    elif rho >= -0.1:
        sta = "N"
    else:
        sta = "I"
    macro("rtLfiveaStatus", verdict(sta))
    cc = [r for r in pre if r["prover"] == "cone_check"]
    total = int(cc[0]["calls_total"])
    eq_total = int(cc[0]["equivalent_total"])
    zero = [r for r in cc if int(r["equivalent_lost"]) == 0]
    best = max(zero, key=lambda r: int(r["calls_pruned"]))
    frac = int(best["calls_pruned"]) / total
    macro("rtLfiveCalls", fi(total))
    macro("rtLfiveEquivCalls", fi(eq_total))
    macro("rtLfiveThr", f"{THR_L5B_FRAC:g}")
    macro("rtLfiveNonEquiv", fi(total - eq_total))
    macro("rtLfiveNonEquivFrac", f3((total - eq_total) / total, 2))
    macro("rtLfiveBestFrac", f3(frac, 3))
    macro("rtLfiveBestRule", tex(f"{best['kind']}/{best['feature']}={best['bin']}"))
    tt = [r for r in pre if r["prover"] == "truth_table"]
    macro("rtLfiveTruthCalls", fi(tt[0]["calls_total"]) if tt else "0")
    stb = "S" if frac >= THR_L5B_FRAC else "N"
    macro("rtLfivebStatus", verdict(stb))
    names = [("l2-f2-none", "VerilogEval f2, uncalibrated"),
             ("l2-f2-calib", "VerilogEval f2, calibrated"),
             ("l2-f2-calib-rp0.1", "VerilogEval f2, calibrated, rp 0.1"),
             ("l2-f3-none", "VerilogEval f3, uncalibrated"),
             ("l1-native-none", "micro f2, uncalibrated"),
             ("l1-native-calib", "micro f2, calibrated")]
    body = []
    for k, lab in names:
        if (k, "width") not in corr:
            continue
        w, m = corr[(k, "width")], corr[(k, "must")]
        s2 = snd.get(k, {})
        body.append([lab, w["designs_with_gt"], f3(num(w["spearman"])), f3(num(w["p"])),
                     f3(num(m["spearman"])), f3(num(s2.get("must_precision", ""))),
                     f3(num(s2.get("must_recall", ""))), f3(num(s2.get("may_recall", "")))])
    t1 = table(
        r"Graph sandwich (RQ-L5): Spearman correlation of the bracket width (candidate "
        r"fraction of the cells) and of the committed fraction with the per-design F1; "
        r"cell-level soundness against the union of the scored ground-truth footprints "
        r"(\code{must}: committed cells; \code{may}: committed plus candidate cells).",
        "tab:r2-l5", ["Run set", "Designs", "$\\rho$ width", "$p$", "$\\rho$ must",
                      "must prec.", "must rec.", "may rec."], body, "lrrrrrrr")
    pbody = [[tex(f"{r['kind']}/{r['feature']}={r['bin']}"), fi(r["calls_pruned"]),
              f3(num(r["fraction_pruned"])), fi(r["equivalent_lost"])]
             for r in sorted(cc, key=lambda r: (-int(r["calls_pruned"]), r["kind"], r["feature"]))
             if int(r["equivalent_lost"]) == 0][:5]
    pbody += [["\\emph{unrestricted best}"] + (lambda r: [fi(r["calls_pruned"]),
              f3(num(r["fraction_pruned"])), fi(r["equivalent_lost"])])(
                  max(cc, key=lambda r: int(r["calls_pruned"])))]
    t2 = table(
        r"Structural prefilter (RQ-L5b), measured offline on the " + fi(total) +
        r" \code{cone\_check} calls of all round-2 runs (" + fi(eq_total) +
        r" proved \code{equivalent}): the rules that prune calls without losing a proved "
        r"construct, and the largest rule overall.",
        "tab:r2-prefilter", ["Rule (kind/feature=bin)", "Calls pruned", "Fraction",
                             "Equivalent lost"], pbody, "lrrr")
    return t1 + "\n\n" + t2, sta, stb


# ------------------------------------------------------------------------------------------ L2
def l2_block() -> tuple[str, str]:
    h = {(r["variant"], r["quartile"], r["set"]): r for r in rows("l2_headtohead.csv")}
    eq = {r["set"]: r for r in rows("l2_equiv.csv")}
    ops = {(r["set"], r["quartile"]): r for r in rows("l2_ops.csv")}

    def v(variant: str, q: str, which: str, metric: str) -> float | None:
        r = h.get((variant, q, which))
        return num(r[f"{metric}_mean"]) if r else None

    cond_a = all((v("f3-calib", q, "common", m) or 0) < (v("llm", q, "common", m) or 0)
                 for q in ("Q1", "Q2") for m in ("ast", "cfg"))
    cond_b = all((v("f3-calib", "Q4", "all", m) or 0) >= (v("f3-calib", "Q1", "all", m) or 0) - 0.05
                 for m in ("ast", "cfg"))
    e = eq["f3-calib"]
    cond_c = int(e["final_equiv_equivalent"]) == int(e["runs"]) == 150
    macro("rtLtwoLlmAstQa", f3(v("llm", "Q1", "common", "ast")))
    macro("rtLtwoLlmAstQb", f3(v("llm", "Q2", "common", "ast")))
    macro("rtLtwoLlmCfgQa", f3(v("llm", "Q1", "common", "cfg")))
    macro("rtLtwoLlmCfgQb", f3(v("llm", "Q2", "common", "cfg")))
    for q, tag in (("Q1", "Qa"), ("Q2", "Qb")):
        macro(f"rtLtwoLokiAst{tag}", f3(v("f3-calib", q, "common", "ast")))
        macro(f"rtLtwoLokiCfg{tag}", f3(v("f3-calib", q, "common", "cfg")))
        macro(f"rtLtwoCommonN{tag}", h[("f3-calib", q, "common")]["n"])
    for q, tag in (("Q1", "Qa"), ("Q2", "Qb"), ("Q3", "Qc"), ("Q4", "Qd")):
        macro(f"rtLtwoTrendAst{tag}", f3(v("f3-calib", q, "all", "ast")))
        macro(f"rtLtwoTrendCfg{tag}", f3(v("f3-calib", q, "all", "cfg")))
        macro(f"rtLtwoTrendN{tag}", h[("f3-calib", q, "all")]["n"])
    ts = {(r["variant"], r["quartiles"], r["set"]): r for r in rows("l2_testsplit.csv")}
    for key, name in (("llm", "Llm"), ("f3-calib", "Loki")):
        r = ts[(key, "Q1+Q2", "common")]
        macro(f"rtLtwoTest{name}Ast", f3(num(r["ast_mean"])))
        macro(f"rtLtwoTest{name}Cfg", f3(num(r["cfg_mean"])))
    macro("rtLtwoTestN", ts[("f3-calib", "Q1+Q2", "common")]["n"])
    for r in rows("l2_refparse.csv"):
        tag = {"Q1": "Qa", "Q2": "Qb", "Q3": "Qc", "Q4": "Qd"}[r["quartile"]]
        macro(f"rtLtwoRefFail{tag}", r["ref_ast_parse_fail"])
    sp = {r["split"]: r["designs"] for r in rows("l2_split.csv")}
    macro("rtLtwoTrainDesigns", sp["train"])
    macro("rtLtwoTestDesigns", sp["test"])
    cov = {r["variant"]: r for r in rows("l2_coverage.csv")}
    macro("rtLtwoRefAstFail", cov["f3-calib"]["ref_ast_parse_fail"])
    macro("rtLtwoCfgSkip", cov["f3-calib"]["cfg_skipped_size"])
    macro("rtLtwoAstN", cov["f3-calib"]["ast_values"])
    macro("rtLtwoEquivRuns", e["runs"])
    macro("rtLtwoDesigns", e["runs"])
    macro("rtLtwoCommitDesigns", e["designs_with_commits"])
    macro("rtLtwoEquivOk", e["final_equiv_equivalent"])
    macro("rtLtwoSelfOk", e["input_netlist_selfcheck_ok"])
    macro("rtLtwoOpsLlm", f3(num(ops[("llm", "Q1+Q2")]["type_f1"])))
    macro("rtLtwoOpsLokiNone", f3(num(ops[("l2-f2-none", "Q1+Q2")]["type_f1"])))
    macro("rtLtwoOpsLokiCal", f3(num(ops[("l2-f2-calib", "Q1+Q2")]["type_f1"])))
    st = "S" if cond_a and cond_b and cond_c else ("N" if not cond_a else "I")
    macro("rtLtwoStatus", verdict(st))
    macro("rtLtwoCondA", "yes" if cond_a else "no")
    macro("rtLtwoCondB", "yes" if cond_b else "no")
    macro("rtLtwoCondC", "yes" if cond_c else "no")
    cols = [("llm", "LLM (round 1)"), ("f3-l0", "f3 netlist (L0)"), ("f3-calib", "f3 L1 cal."),
            ("f3-none", "f3 L1 none"), ("f2-calib", "f2 L1 cal."), ("f2-none", "f2 L1 none")]
    body = []
    for q in ("Q1", "Q2", "Q1+Q2"):
        for metric, lab in (("ast", "AST"), ("cfg", "CFG")):
            row = [f"{q} {lab}"]
            for var, _ in cols:
                if q == "Q1+Q2":
                    vals = [(num(h[(var, qq, "common")]["n"]), v(var, qq, "common", metric))
                            for qq in ("Q1", "Q2") if (var, qq, "common") in h]
                    tot = sum(n or 0 for n, x in vals if x is not None)
                    mean = None
                    if tot:
                        mean = sum((n or 0) * x for n, x in vals if x is not None) / tot
                    row.append(f3(mean))
                else:
                    row.append(f3(v(var, q, "common", metric)))
            body.append(row)
    t1 = table(
        r"Head-to-head on the VerilogEval designs the language model was scored on "
        r"(Q1 and Q2, functionally correct samples; AST depth 3 and CFG as in "
        r"Table~\ref{tab:veval}). Loki columns: the output Verilog of the flow at that floor "
        r"against the reference \code{.sv}; \code{L0} is the netlist before L1.",
        "tab:r2-l2", ["Metric"] + [c for _, c in cols], body, "l" + "r" * len(cols))
    body2 = []
    for q in ("Q1", "Q2", "Q3", "Q4"):
        n = h[("f3-calib", q, "all")]["n"]
        row2 = [q, n]
        for var in ("f3-l0", "f3-calib", "f2-calib"):
            row2 += [f3(v(var, q, "all", "ast")), f3(v(var, q, "all", "cfg"))]
        o = ops.get(("l2-f2-none", q))
        row2.append(f3(num(o["type_f1"])) if o else "--")
        body2.append(row2)
    t2 = table(
        r"Loki on all 150 VerilogEval designs by complexity quartile (mean AST and CFG of the "
        r"output Verilog against the reference; last column: operator type-F1 of the "
        r"uncalibrated f2 run). Calibrated f3 equals the f3 netlist wherever L1 commits "
        r"nothing.", "tab:r2-l2q",
        ["Quartile", "$n$", "f3 AST", "f3 CFG", "f3 cal. AST", "f3 cal. CFG", "f2 cal. AST",
         "f2 cal. CFG", "op F1"], body2, "lrrrrrrrr")
    return t1 + "\n\n" + t2, st


# ------------------------------------------------------------------------------------------ log
def log_table(status: dict[str, str]) -> str:
    m = MACROS
    body = [
        ["L1", "f3 failure is detector vocabulary", "2", status["L1"],
         f"micro-F1 LUT6/f2 = {m['rtLoneAllRatio']} (all, in-sample), "
         f"{m['rtLoneTestRatio']} (test)"],
        ["L2", "Loki below the LLM on AST/CFG, flat over Q1--Q4", "2", status["L2"],
         f"AST Q1/Q2 {m['rtLtwoLokiAstQa']}/{m['rtLtwoLokiAstQb']} vs "
         f"{m['rtLtwoLlmAstQa']}/{m['rtLtwoLlmAstQb']}"],
        ["L4", "one or two evidence families carry the posterior", "2", status["L4"],
         f"full minus priors-only micro-F1 {m['rtLfourGap']}"],
        ["L5a", "bracket width falls with per-design F1", "2", status["L5a"],
         f"Spearman {m['rtLfiveRho']} ($p={m['rtLfiveP']}$)"],
        ["L5b", "structural prefilter cuts prover calls, keeps recall", "2", status["L5b"],
         f"best zero-loss rule prunes {m['rtLfiveBestFrac']}"],
        ["L7", "operator F1 separates AST/CFG ties", "2", status["L7"],
         f"tie pair dF1 {m['rtLsevenDF']}; flatten dAST {m['rtLsevenFAst']}"],
        ["L3", "cross-suite GNN", "next", "not run", "--"],
        ["L6", "motif null model", "next", "not run", "--"],
        ["L8", "LLM with reverse provenance", "next", "deferred (Peter)", "--"],
    ]
    return table(
        r"Research log: the round-2 questions, their status and the deciding number "
        r"(all generated from \code{experiments/round2}).",
        "tab:r2-log", ["RQ", "Hypothesis", "Round", "Status", "Deciding number"], body,
        "lp{3.0cm}lp{2.6cm}p{3.2cm}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    parts: list[str] = []
    status: dict[str, str] = {}
    t, status["L1"] = l1_block()
    parts.append(t)
    t, st7 = l7_block()
    status["L7"] = st7
    parts.append(t)
    t, status["L2"] = l2_block()
    parts.append(t)
    t, status["L4"] = l4_block()
    parts.append(t)
    t, status["L5a"], status["L5b"] = l5_block()
    parts.append(t)
    status = {k: verdict(v) if v in ("S", "N", "I") else v for k, v in status.items()}
    status["L7"] = verdict_l7(st7)
    head = ["% Generated by experiments/round2/paper_tables.py; do not edit."]
    macros = [rf"\newcommand{{\{k}}}{{{v}}}" for k, v in sorted(MACROS.items())]
    args.out.write_text("\n".join(head + macros) + "\n\n" + "\n\n".join(parts) + "\n",
                        encoding="utf-8")
    log = args.out.with_name("round2-log.tex")
    log.write_text("\n".join(head) + "\n\n" + log_table(status) + "\n", encoding="utf-8")
    print(f"wrote {args.out} and {log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
