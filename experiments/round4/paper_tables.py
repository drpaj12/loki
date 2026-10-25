#!/usr/bin/env python3
"""Write docs/paper/round4-tables.tex and round4-log.tex from the round-4 CSVs.

Every number the round-4 prose cites is a macro (``\\rfs...``) generated here; statuses come from
``r4_status.csv`` (written by ``decide.py`` under the Stage-0 rules). No timestamps: a rerun
reproduces the files byte for byte.

Usage: paper_tables.py [--out PATH]
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import r4lib

DEFAULT_OUT = r4lib.HERE.parents[1] / "docs" / "paper" / "round4-tables.tex"
MACROS: dict[str, str] = {}


def rows(name: str) -> list[dict[str, str]]:
    return r4lib.read_csv(r4lib.OUT / name)


def f3(x: float | str, d: int = 3) -> str:
    return f"{float(x):.{d}f}".replace("-", "$-$")


def fi(x: float | int | str) -> str:
    return f"{int(float(x)):,}".replace(",", "{,}")


def tex(t: str) -> str:
    return t.replace("_", r"\_").replace("#", r"\#").replace("<", "$<$")


def macro(name: str, value: str) -> None:
    MACROS[name] = value


def table(caption: str, label: str, head: list[str], body: list[list[str]], spec: str) -> str:
    lines = [r"\begin{table}[t]", rf"\caption{{{caption}}}", rf"\label{{{label}}}",
             r"\centering", r"\footnotesize", r"\resizebox{\columnwidth}{!}{%",
             rf"\begin{{tabular}}{{@{{}}{spec}@{{}}}}", r"\toprule",
             " & ".join(head) + r" \\", r"\midrule"]
    lines += [" & ".join(r) + r" \\" for r in body]
    lines += [r"\bottomrule", r"\end{tabular}}", r"\end{table}"]
    return "\n".join(lines)


def status_of() -> dict[tuple[str, str], tuple[str, str]]:
    return {(r["id"], r["variant"]): (r["status"], r["numbers"]) for r in rows("r4_status.csv")}


def corpus_block() -> str:
    rep = rows("corpus_report.csv")
    fam: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rep:
        fam[r["family"]][r["split"]] += int(r["generated"])
        fam[r["family"]]["ok"] += int(r["all_floors_ok"])
    body = [[tex(k), fi(v["train"]), fi(v["iid"]), fi(v["ood"]), fi(v["ok"])]
            for k, v in sorted(fam.items())]
    tot = sum(int(r["generated"]) for r in rep)
    ok = sum(int(r["all_floors_ok"]) for r in rep)
    macro("rfsCorpusTotal", fi(tot))
    macro("rfsCorpusOk", fi(ok))
    macro("rfsFamilies", str(len(fam)))
    return table("The round-4 corpus: designs per family and split, and designs that build on "
                 "f1-k6, f2 and f3 with every equivalence check passing.", "tab:r4-corpus",
                 ["family", "train", "iid test", "ood test", "ok on all floors"], body, "lrrrr")


def kinds_block() -> str:
    kr = [r for r in rows("l12b_kinds.csv")
          if r["floor"] == "f2" and r["sets"] == "micro,vetest"]
    body = []
    for k in ("adder", "subtractor", "comparator", "eq_const", "mux", "register", "ff_srst"):
        line = [tex(k)]
        for v in ("V0", "V1", "V2"):
            r = next(x for x in kr if x["variant"] == v and x["kind"] == k)
            line.append(f"{f3(r['f1_dict'])}")
        r0 = next(x for x in kr if x["variant"] == "V0" and x["kind"] == k)
        line += [f3(r0["f1_det"]), r0["designs_with_gt"], r0["gt"]]
        body.append(line)
    return table("H12b on real designs (micros and the 33 VerilogEval test designs, f2): pooled "
                 "F1 of the dictionary (V0 as written; V1 and V2 added after Stage 0) and of the "
                 "better detector arm, and the number of designs and ground-truth constructs.",
                 "tab:r4-kinds",
                 ["kind", "dict V0", "dict V1", "dict V2", "best detector", "designs", "GT"],
                 body, "lcccccc")


def curve_block() -> str:
    cv = rows("l12c_curve.csv")
    sizes = sorted({int(r["n_train"]) for r in cv if r["arm"] != "ve"})
    body = []
    for fl in ("f2",):
        for s in ("iid", "ood", "micro", "vetest"):
            line = [s]
            for n in sizes:
                v = [float(r["macro_f1"]) for r in cv if r["floor"] == fl and r["set"] == s
                     and r["arm"] != "ve" and int(r["n_train"]) == n]
                line.append(f3(sum(v) / len(v)) if v else "--")
            ve = [float(r["macro_f1"]) for r in cv if r["floor"] == fl and r["set"] == s
                  and r["arm"] == "ve"]
            line.append(f3(sum(ve) / len(ve)) if ve else "--")
            body.append(line)
    sl = {(r["floor"], r["set"]): r for r in rows("l12c_slope.csv")}
    sv = sl[("f2", "vetest")]
    macro("rfsGnnSlope", f3(sv["slope_per_doubling"], 4))
    macro("rfsGnnCiLo", f3(sv["ci_lo"], 4))
    macro("rfsGnnCiHi", f3(sv["ci_hi"], 4))
    macro("rfsGnnVeDesigns", sv["n_designs"])
    t1 = table("GNN macro-F1 (f2, mean of 3 seeds) by corpus train size, on four test sets; last "
               "column: trained on the VerilogEval train split.", "tab:r4-curve",
               ["test set", *[str(n) for n in sizes], "VE train"], body,
               "l" + "c" * (len(sizes) + 1))
    body2 = [[r["floor"], r["set"], r["n_designs"], f3(r["slope_per_doubling"], 4),
              f"[{f3(r['ci_lo'], 4)}, {f3(r['ci_hi'], 4)}]"] for r in rows("l12c_slope.csv")]
    t2 = table("Slope of macro-F1 per doubling of the corpus train size, with 95\\% bootstrap "
               "interval over test designs.", "tab:r4-slope",
               ["floor", "test set", "designs", "slope", "95\\% CI"], body2, "llrcc")
    return t1 + "\n\n" + t2


def big_skips() -> None:
    path = r4lib.OUT / "l13_builds.csv"
    if not path.is_file():
        return
    f3: list[str] = []
    mem: list[str] = []
    built = 0
    for r in r4lib.read_csv(path):
        if "MemoryError" in (r["f1-k6"] + r["f2"] + r["f3"]):
            mem.append(tex(r["design"]))
        elif r["f3"].startswith("skipped"):
            f3.append(tex(r["design"]))
        if r["status"] == "ok":
            built += 1
    macro("rfsBigFThreeSkipped", ", ".join(f3) if f3 else "none")
    macro("rfsBigMemSkipped", ", ".join(mem) if mem else "none")
    macro("rfsBigBuilt", str(built))


def big_block() -> str:
    big_skips()
    try:
        big = rows("l13_big.csv")
    except FileNotFoundError:
        return ""
    bd = {r["design"]: r for r in rows("l13_builds.csv")}
    body = []
    for r in big:
        if r["floor"] != "f3":
            continue
        name = r["design"].removeprefix("vtr_")
        b = bd.get(name, {})
        e = int(r["eligible_words"])
        body.append([tex(name), fi(r["cells"]), b.get("peak_rss_mb", "--"), fi(e),
                     f3(int(r["repeated_words"]) / e) if e else "--", r["memories"],
                     r["wide_buses"], r["high_fanout_nets"], r["fsm_words"]])
    sm = [r for r in rows("l13_small.csv") if r["floor"] == "f3"]
    e = sum(int(r["eligible_words"]) for r in sm)
    macro("rfsSmallShare", f3(sum(int(r["repeated_words"]) for r in sm) / e) if e else "--")
    macro("rfsSmallDesigns", fi(len(sm)))
    return table("Big VTR designs at f3: cells, Odin III peak RSS (MB, all three floors), words "
                 "with at least two cells and width $\\geq 2$, share of them in a repeat group, "
                 "memories, buses of at least 8 bits, nets with at least 8 readers, FSM words.",
                 "tab:r4-big",
                 ["design", "cells", "RSS", "words", "repeated", "mem", "buses", "hi-fanout",
                  "fsm"], body, "lrrrrrrrr")


def ident_block() -> str:
    try:
        idr = rows("l14_ident.csv")
    except FileNotFoundError:
        return ""
    fams = sorted({r["family"] for r in idr})
    body = []
    for fam in fams:
        line = [tex(fam) if fam != "*" else "all"]
        for fl in ("f1-k6", "f2", "f3"):
            r = next((x for x in idr if x["family"] == fam and x["floor"] == fl), None)
            line.append(f3(r["ceiling_wl"]) if r else "--")
        body.append(line)
    for fl, nm in (("f1-k6", "One"), ("f2", "Two"), ("f3", "Three")):
        r = next((x for x in idr if x["family"] == "*" and x["floor"] == fl), None)
        if r:
            macro(f"rfsCeil{nm}", f3(r["ceiling_wl"]))
    return table("Style-recovery ceiling (classes of equivalent netlists over coding styles) on "
                 "the twin set, per family and floor.", "tab:r4-ident",
                 ["family", "f1-k6", "f2", "f3"], body, "lccc")


def mdl_block() -> str:
    m = rows("l14_mdl.csv")
    body = []
    for v in ("ref", "llm", "l0-f2", "l0-f3", "f2-none", "f3-none", "f2-calib", "f3-calib"):
        rr = [float(r["ratio"]) for r in m if r["variant"] == v]
        rr.sort()
        body.append([tex(v), str(len(rr)), f3(rr[len(rr) // 2], 2),
                     f3(sum(1 for x in rr if x > 1.0) / len(rr))])
    return table("MDL readability: description length of a candidate relative to the "
                 "VerilogEval reference (median ratio) and the share of designs where the "
                 "reference is strictly shorter.", "tab:r4-mdl",
                 ["variant", "designs", "median ratio", "ref shorter"], body, "lrrr")


KIND_FAMILY = {"adder": "adder", "subtractor": "subtractor", "comparator": "comparator",
               "eq_const": "comparator", "mux": "mux", "mux_tree": "mux", "register": "register",
               "ff_en": "register", "ff_srst": "register", "counter": "counter", "fsm": "fsm"}


def overlap_block() -> str:
    """Word-level overlap q_K (Stage 0, report only): share of GT instances with at least two
    cells whose fragment coverage is at least 0.8."""
    ov = rows("l12b_overlap.csv")
    arms = ["det-N", "det-C", "dict-V0", "dict-V1", "dict-V2"]
    kinds = sorted({r["kind"] for r in ov})
    body = []
    for k in kinds:
        line = [tex(k)]
        inst = ""
        for a in arms:
            r = next((x for x in ov if x["arm"] == a and x["kind"] == k), None)
            line.append(f3(r["share"]) if r and r["share"] != "" else "--")
            inst = r["instances"] if r else inst
        body.append([line[0], inst, *line[1:]])
    return table("Word-level overlap $q_K$ (report only): share of ground-truth instances of kind "
                 "$K$ with at least two cells that a fragment of the arm covers to at least 0.8, "
                 "detectors (N uncalibrated, C calibrated) and dictionary variants.",
                 "tab:r4-overlap", ["kind", "instances", "det N", "det C", "dict V0", "dict V1",
                                    "dict V2"], body, "lrccccc")


def ceiling_block() -> str:
    """Ceiling statement (Stage 0): per kind and floor, the Bayes ceiling of the signature
    classifier (cell recall of the kind, in-sample, kmax 6) and the style-recovery ceiling of the
    family that produces the kind, and their minimum."""
    bay = rows("l14_bayes.csv")
    idr = {(r["family"], r["floor"]): float(r["ceiling_wl"]) for r in rows("l14_ident.csv")}
    body = []
    for k, fam in sorted(KIND_FAMILY.items()):
        line = [tex(k), tex(fam)]
        for fl in ("f2", "f3"):
            b = {int(r["radius"]): r[f"recall_{k}"] for r in bay
                 if r["floor"] == fl and r["kmax"] == "6"}
            st = idr[(fam, fl)]
            b0, b3 = float(b[0]), float(b[3])
            line += [f3(b0, 2), f3(b3, 2), f3(st, 2), f3(min(b3, st), 2)]
        body.append(line)
    return table("Ceiling statement (report only): per kind, the Bayes ceiling of a signature "
                 "classifier (share of the kind's cells in signatures where the kind has share "
                 "at least 0.5; in-sample, 6 leaves; radius 0 and 3), the style-recovery "
                 "ceiling of the family that makes the kind, and the minimum of radius 3 and "
                 "style.", "tab:r4-ceiling",
                 ["kind", "family", "B0 f2", "B3 f2", "style f2", "min f2", "B0 f3", "B3 f3",
                  "style f3", "min f3"], body, "ll" + "c" * 8)


def mset(prefix: str, row: dict[str, str], cols: dict[str, str], d: int = 3) -> None:
    for col, name in cols.items():
        if row.get(col, "") != "":
            macro(f"rfsX{name}{prefix}", f3(row[col], d))


def explore_macros() -> None:
    """Macros of the exploratory entry 2026-10-25-c (labelled exploratory in the paper)."""
    import decide
    import l13_run

    macro("rfsAsLimitGiB", str(l13_run.AS_LIMIT // 1024 ** 3))
    cur = rows("l12c_curve.csv")
    sizes = sorted({int(r["n_train"]) for r in cur if r["arm"] != "ve"})
    macro("rfsTrainMin", str(sizes[0]))
    macro("rfsTrainMax", str(sizes[-1]))
    flt = {(r["floor"], r["set"]): r for r in rows("x12_filter.csv")}
    nolog = sum(int(flt[("f2", s)]["designs"]) - int(flt[("f2", s)]["with_logic"])
                for s in ("corpus_train", "iid", "ood"))
    macro("rfsNoLogic", str(nolog))
    for s, nm in (("iid", "Iid"), ("ood", "Ood"), ("micro", "Micro"), ("vetest", "VeTest"),
                  ("ve_train", "VeTrain"), ("corpus_train", "CorpusTrain")):
        macro(f"rfsN{nm}", flt[("f2", s)]["with_logic"])
        macro(f"rfsNAll{nm}", flt[("f2", s)]["designs"])
    nt = {(r["floor"], r["set"]): r["mean_n_train_by_per_family"] for r in rows("x12_ntrain.csv")}
    macro("rfsTrainActual", ", ".join(v.split(":")[1] for v in nt[("f2", "iid")].split("|")))
    macro("rfsTrainActualMax", nt[("f2", "iid")].split("|")[-1].split(":")[1])
    builds = {r["design"]: r for r in rows("l13_builds.csv")}
    if "arm_core" in builds:
        macro("rfsArmHours", f3(float(builds["arm_core"]["seconds"]) / 3600, 1))
    # H13 exploratory
    sm = {r["set"]: r for r in rows("x13_summary.csv")}
    cols = {"share_k0": "RepZero", "null_k0": "NullZero", "k0_minus_null": "ExcZero",
            "share_k1": "RepOne", "null_k1": "NullOne", "k1_minus_null": "ExcOne",
            "share_edges": "Edges", "null_share_edges": "NullEdges",
            "share_k0_among_edges": "RepEdges", "cross_module_k0": "Cross"}
    names = {"big": "Big", "small": "Small", "small_real": "Real", "small_ve": "Ve",
             "small_micro": "Micro", "small_corpus": "Corpus"}
    for k, nm in names.items():
        mset(nm, sm[k], cols)
        macro(f"rfsXEligible{nm}", fi(sm[k]["eligible"]))
        macro(f"rfsXDesigns{nm}", fi(sm[k]["designs"]))
    sb = float(sm["big"]["share_k0"])
    for k in ("small", "small_real", "small_ve"):
        diff = sb - float(sm[k]["share_k0"])
        macro(f"rfsXThirteenB{names[k]}", f"{'+' if diff >= 0 else '$-$'}{abs(diff):.3f}")
        macro(f"rfsXThirteenB{names[k]}Status", decide.status(diff >= 0.15, diff <= 0.05))
    grp = rows("x13_h13c.csv")
    for var, nm in (("V0", "Vzero"), ("V1", "Vone"), ("V2", "Vtwo")):
        gv = [g for g in grp if g["variant"] == var]
        if gv:
            n = len(gv)
            macro(f"rfsXThirteenC{nm}Null",
                  f3(sum(int(g["null_same_sum"]) for g in gv) / sum(int(g["draws"]) for g in gv)))
            edge = [g for g in gv if g["has_edges"] == "1"]
            macro(f"rfsXThirteenC{nm}Edge",
                  f3(sum(int(g["same_signature"]) for g in edge) / len(edge)) if edge else "--")
            macro(f"rfsXThirteenC{nm}EdgeN", fi(len(edge)))
            macro(f"rfsXThirteenC{nm}N", fi(n))
    # H12 exploratory
    dup = {(r["what"], r["floor"], r["set_or_variant"], r["key"]): r
           for r in rows("x12_dup_summary.csv")}
    for fl, nm in (("f2", "Two"), ("f3", "Three")):
        for sp, sn in (("iid", "Iid"), ("ood", "Ood")):
            r = dup[("dup_rate", fl, sp, "multiset")]
            macro(f"rfsDup{nm}{sn}", r["a"])
            macro(f"rfsDup{nm}{sn}N", r["n"])
            macro(f"rfsDup{nm}{sn}Wl", dup[("dup_rate", fl, sp, "wl")]["a"])
            macro(f"rfsDup{nm}{sn}Share", f3(int(r["a"]) / int(r["n"])))
    for var, nm in (("V0", "Vzero"), ("V1", "Vone"), ("V2", "Vtwo")):
        a = dup[("h12b2_all", "f2", var, "multiset")]
        b = dup[("h12b2_restricted", "f2", var, "multiset")]
        macro(f"rfsDupRestr{nm}Iid", f3(b["a"]))
        macro(f"rfsDupRestr{nm}Ood", f3(b["b"]))
        macro(f"rfsDupRestr{nm}R", f3(float(b["b"]) / float(b["a"])))
        macro(f"rfsDupAll{nm}R", f3(float(a["b"]) / float(a["a"])))
    macro("rfsDupRestrIidN", dup[("h12b2_restricted", "f2", "V0", "multiset")]["n"].split("/")[0])
    macro("rfsDupRestrOodN", dup[("h12b2_restricted", "f2", "V0", "multiset")]["n"].split("/")[1])
    for fl, nm in (("f2", "Two"), ("f3", "Three")):
        for sp, sn in (("iid", "Iid"), ("ood", "Ood")):
            for tag, tn in (("all", "All"), ("restricted", "Restr")):
                macro(f"rfsDupGnn{nm}{sn}{tn}Slope",
                      f3(dup[(f"gnn_{tag}", fl, sp, "multiset")]["b"], 4))
    gn = {(r["x_axis"], r["B"]): r for r in rows("x12_gnn.csv")}
    for ax, an in (("nominal", "Nom"), ("actual", "Act")):
        for nb, bn in (("2000", "Small"), ("20000", "Large")):
            gr = gn[(ax, nb)]
            macro(f"rfsGnn{an}{bn}Slope", f3(gr["slope"], 4))
            macro(f"rfsGnn{an}{bn}CiLo", f3(gr["ci_lo"], 4))
            macro(f"rfsGnn{an}{bn}CiHi", f3(gr["ci_hi"], 4))
    macro("rfsGnnMargin", f3(0.010 - float(gn[("nominal", "2000")]["ci_hi"]), 4))
    macro("rfsGnnMarginLarge", f3(0.010 - float(gn[("actual", "20000")]["ci_hi"]), 4))
    # H14 exploratory
    xi = {(r["variant"], r["family"], r["floor"]): r for r in rows("x14_ident.csv")}
    for v, nm in (("reg", "Reg"), ("cap720", "Cap"), ("pins", "Pins"), ("cap720+pins", "CapPins"),
                  ("reg+dedupe", "Dedupe"), ("cap720+pins+dedupe", "AllDedupe")):
        for fl, fn in (("f1-k6", "One"), ("f2", "Two"), ("f3", "Three")):
            macro(f"rfsIdent{nm}{fn}", f3(xi[(v, "*", fl)]["ceiling_wl"]))
        macro(f"rfsIdent{nm}Diff", f3(float(xi[(v, "*", "f3")]["ceiling_wl"])
                                    - float(xi[(v, "*", "f2")]["ceiling_wl"]), 4))
        macro(f"rfsIdent{nm}N", xi[(v, "*", "f3")]["n_designs"])
    tw = rows("l14_twins.csv")
    for fl, fn in (("f1-k6", "One"), ("f2", "Two"), ("f3", "Three")):
        macro(f"rfsExact{fn}", str(sum(1 for r in tw if r["floor"] == fl
                                       and r["classes_exact"] != "")))
        macro(f"rfsExact{fn}Of", str(sum(1 for r in tw if r["floor"] == fl)))
    # twin designs covered by the exact check, and disagreements with WL
    ex = [r for r in tw if r["classes_exact"] != ""]
    macro("rfsExactBases", str(len(ex)))
    macro("rfsExactDisagree", str(sum(1 for r in ex if r["classes_exact"] != r["classes_wl"])))
    md = {(r["measure"], r["variant"]): r for r in rows("x14_mdl.csv")}
    for m, mn in (("ast", "Ast"), ("cfg", "Cfg")):
        for v, vn in (("pooled", "Pooled"), ("f2-none", "FTwoNone"), ("f3-none", "FThreeNone"),
                      ("f2-calib", "FTwoCalib"), ("f3-calib", "FThreeCalib")):
            r = md[(m, v)]
            macro(f"rfsMdl{mn}{vn}Rho", f3(r["rho"]))
            macro(f"rfsMdl{mn}{vn}Part", f3(r["partial_rho"]))
            macro(f"rfsMdl{mn}{vn}N", r["n"])
        macro(f"rfsMdl{mn}Ci", tex(md[(m, "pooled")]["rho_ci_design_clustered"]))
        macro(f"rfsMdl{mn}PartCi", tex(md[(m, "pooled")]["partial_ci_design_clustered"]))
        macro(f"rfsMdl{mn}Designs", md[(m, "pooled")]["designs"])
    stat = status_of()
    macro("rfsXFourteenCfgStatus", stat[("H14d-cfg(report)", "-")][0])
    macro("rfsXFourteenCfgNumbers", tex(stat[("H14d-cfg(report)", "-")][1]))
    for key, nm in (("H12b-corpus-ood(report)", "Ood"), ("H12b-f3(report)", "FThree")):
        for v, vn in (("V0", "Vzero"), ("V1", "Vone"), ("V2", "Vtwo")):
            macro(f"rfsXTwelveB{nm}{vn}", tex(stat[(key, v)][1].split(" floor")[0]))


def log_table(st: dict[tuple[str, str], tuple[str, str]]) -> str:
    def g(i: str, v: str = "-") -> tuple[str, str]:
        return st.get((i, v), ("not run", ""))

    body = []
    rows_ = [("L12a", "corpus is usable", "H12a", "-"),
             ("L12b", "dictionary beats detectors (V0 as written)", "H12b", "V0"),
             ("L12b", "same, V1 (added after Stage 0)", "H12b", "V1"),
             ("L12b", "same, V2 (added after Stage 0)", "H12b", "V2"),
             ("L12b2", "dictionary generalises over unseen regions (V0)", "H12b2", "V0"),
             ("L12c", "GNN transfer improves with corpus size", "H12c", "-"),
             ("L13a", "big designs mostly repeated structure", "H13a", "-"),
             ("L13b", "big designs repeat more than small", "H13b", "-"),
             ("L13c", "repeated instances share the signature (V0)", "H13c", "V0"),
             ("L14a", "flow destroys style information", "H14a", "f3"),
             ("L14b", "coarser floor destroys more", "H14b", "-"),
             ("L14c", "MDL ranks references above recovered RTL", "H14c", "-"),
             ("L14d", "MDL tracks round-2 similarity", "H14d", "-")]
    for rq, hyp, i, v in rows_:
        s, n = g(i, v)
        body.append([rq, hyp, "4", tex(s), tex(n)])
    return table(r"Research log: the round-4 questions, their status under the Stage-0 rules "
                 r"and the deciding number (generated from \code{experiments/round4}).",
                 "tab:r4-log", ["RQ", "Hypothesis", "Round", "Status", "Deciding number"],
                 body, "lp{3.0cm}lp{2.2cm}p{3.8cm}")


def macros_from_status(st: dict[tuple[str, str], tuple[str, str]]) -> None:
    names = {"H12a": "TwelveA", "H12b": "TwelveB", "H12b2": "TwelveBTwo", "H12c": "TwelveC",
             "H13a": "ThirteenA", "H13b": "ThirteenB", "H13c": "ThirteenC",
             "H14a": "FourteenA", "H14b": "FourteenB", "H14c": "FourteenC",
             "H14d": "FourteenD"}
    var = {"V0": "Vzero", "V1": "Vone", "V2": "Vtwo"}
    for (i, v), (s, n) in st.items():
        if i in names and not i.endswith("f3(report)"):
            key = names[i] + (var.get(v, "") if i in ("H12b", "H12b2") else "")
            if i == "H13c" and v != "V0":
                key += var[v]
            macro(f"rfs{key}Status", s)
            macro(f"rfs{key}Numbers", tex(n))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    st = status_of()
    parts = [corpus_block(), kinds_block(), curve_block(), big_block(), ident_block(),
             mdl_block(), overlap_block(), ceiling_block()]
    explore_macros()
    macros_from_status(st)
    head = ["% Generated by experiments/round4/paper_tables.py; do not edit."]
    macros = [rf"\newcommand{{\{k}}}{{{v}}}" for k, v in sorted(MACROS.items())]
    args.out.write_text("\n".join(head + macros) + "\n\n"
                        + "\n\n".join(p for p in parts if p) + "\n", encoding="utf-8")
    log = args.out.with_name("round4-log.tex")
    log.write_text("\n".join(head) + "\n\n" + log_table(st) + "\n", encoding="utf-8")
    print(f"wrote {args.out} and {log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
