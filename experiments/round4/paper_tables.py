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
    return t.replace("_", r"\_").replace("#", r"\#")


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
    kr = [r for r in rows("l12b_kinds.csv") if r["floor"] == "f2"]
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


def big_block() -> str:
    try:
        big = rows("l13_big.csv")
    except FileNotFoundError:
        return ""
    bd = {r["design"]: r for r in r4lib.read_csv(r4lib.DATA / "big" / "l13_builds.csv")} \
        if (r4lib.DATA / "big" / "l13_builds.csv").is_file() else {}
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
             ("L13c", "repeated instances share the signature", "H13c", "-"),
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
            macro(f"rfs{key}Status", s)
            macro(f"rfs{key}Numbers", tex(n))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    st = status_of()
    parts = [corpus_block(), kinds_block(), curve_block(), big_block(), ident_block(),
             mdl_block()]
    macros_from_status(st)
    ov = rows("l12b_overlap.csv") if (r4lib.OUT / "l12b_overlap.csv").is_file() else []
    for r in ov:
        if r["kind"] == "register" and r["share"]:
            macro("rfsOverlap" + r["arm"].replace("-", "").replace("V", "v").title()
                  .replace("Dict", "Dict"), f3(r["share"]))
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
