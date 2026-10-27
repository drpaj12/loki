#!/usr/bin/env python3
"""Write docs/paper/round6-tables.tex and round6-log.tex from the round-6 CSVs.

Every number the round-6 prose cites is a macro (``\\rsx...``) generated here; statuses come from
``r6_status.csv`` (``decide.py``, Stage-0 rules). No timestamps: a rerun reproduces the files
byte for byte.

Usage: paper_tables.py
"""

from __future__ import annotations

import sys
from collections import defaultdict

from r6lib import HERE, read_csv

OUT = HERE.parents[1] / "docs" / "paper"
MACROS: dict[str, str] = {}
HW = ("fsm", "register", "arith", "mux", "compare", "logic")
PASSES = ("S3_opt", "S4_flatten", "S5_opt_full", "S8_abc")
ALLP = ("S2_fsm", "S3_opt", "S4_flatten", "S5_opt_full", "S6_wreduce", "S7_lower", "S8_abc")
ARMS = ("B", "W", "WB")
KDICT = ("ff_en", "ff_srst", "register", "adder", "subtractor", "comparator", "eq_const", "mux",
         "mux_tree", "counter", "fsm")


def tex(t: str) -> str:
    return t.replace("_", r"\_").replace("#", r"\#").replace("<", "$<$").replace(">", "$>$")


def macro(name: str, value: str) -> None:
    MACROS["rsx" + name] = value


def table(caption: str, label: str, head: list[str], body: list[list[str]], spec: str) -> str:
    lines = [r"\begin{table}[t]", rf"\caption{{{caption}}}", rf"\label{{{label}}}",
             r"\centering", r"\footnotesize", r"\resizebox{\columnwidth}{!}{%",
             rf"\begin{{tabular}}{{@{{}}{spec}@{{}}}}", r"\toprule",
             " & ".join(head) + r" \\", r"\midrule"]
    lines += [" & ".join(r) + r" \\" for r in body]
    lines += [r"\bottomrule", r"\end{tabular}}", r"\end{table}"]
    return "\n".join(lines)


def kind_pass() -> str:
    acc: dict[tuple[str, str], tuple[int, int, float]] = {}
    for r in read_csv(HERE / "l15_kind_pass.csv"):
        if (r["set"], r["level"], r["axis"]) == ("ALL", "stmt", "hw"):
            acc[(r["kind"], r["pass"])] = (int(r["at_risk"]), int(r["first_losses"]),
                                           float(r["null_expected"]))
    body = []
    for k in HW:
        cells = []
        for p in ALLP[1:]:
            a = acc.get((k, p))
            cells.append(f"{a[1]}/{a[2]:.0f}" if a and a[0] else "--")
        n0 = acc.get((k, "S3_opt"))
        body.append([k, str(n0[0]) if n0 else "0", *cells])
    return table("Round 6: first losses of a unit per hardware kind and pass, real/null (stmt "
                 "level, MI+VT+CI). The first column is the units at risk at \\code{opt}; the "
                 "null is the expected loss of the random-set null.", "tab:r6-kindpass",
                 ["Kind", "n", "fsm", "opt", "flatten", "opt -full", "wreduce", "lower", "abc"],
                 body, "lrrrrrrrr")


def reasons() -> str:
    acc: dict[tuple[str, str], int] = defaultdict(int)
    names: list[str] = []
    for r in read_csv(HERE / "l15_reason.csv"):
        if (r["set"], r["level"]) == ("ALL", "stmt"):
            acc[(r["reason"], r["pass"])] += int(r["losses"])
            if r["reason"] not in names:
                names.append(r["reason"])
    body = [[tex(n), *(str(acc[(n, p)]) for p in ALLP[1:])] for n in names]
    return table("Round 6: first losses per reason class and pass (stmt level, MI+VT+CI). "
                 "Classes with no loss are kept.", "tab:r6-reason",
                 ["Reason", "fsm", "opt", "flatten", "opt -full", "wreduce", "lower", "abc"],
                 body, "lrrrrrrr")


def status_table() -> str:
    body = []
    for r in read_csv(HERE / "l15_status.csv"):
        if r["level"] == "stmt":
            body.append([r["set"], r["designs"], r["units"], r["kept"], r["lost"],
                         r["born_joined"], r["capped"]])
    macro("UnitsAll", next(b[2] for b in body if b[0] == "ALL"))
    return table("Round 6: units per set at the stmt level and what became of them.",
                 "tab:r6-status", ["Set", "Designs", "Units", "Kept", "Lost", "Born joined",
                                   "Capped"], body, "lrrrrrr")


def explained() -> str:
    exp: dict[str, tuple[int, int]] = {}
    inh: dict[str, tuple[int, int]] = {}
    for r in read_csv(HERE / "l15_explained.csv"):
        if (r["set"], r["level"]) == ("ALL", "stmt"):
            exp[r["pass"]] = (int(r["merged"]), int(r["explained"]))
    for r in read_csv(HERE / "l15_x_inherited.csv"):
        if (r["set"], r["level"]) == ("ALL", "stmt"):
            inh[r["pass"]] = (int(r["unlabelled"]), int(r["inherited"]))
    body = []
    for p in ALLP[1:]:
        m, e = exp[p]
        u, i = inh[p]
        if m:
            body.append([tex(p), str(m), str(e), f"{e / m:.3f}", str(u), str(i)])
    tm = sum(v[0] for v in exp.values())
    te = sum(v[1] for v in exp.values())
    tu = sum(v[0] for v in inh.values())
    ti = sum(v[1] for v in inh.values())
    macro("MergedAll", str(tm))
    macro("ExplainedAll", str(te))
    macro("ExplainedShare", f"{te / tm:.3f}")
    macro("UnlabelledAll", str(tu))
    macro("InheritedAll", str(ti))
    body.append(["all", str(tm), str(te), f"{te / tm:.3f}", str(tu), str(ti)])
    return table("Round 6: merged first losses, those a labelled same-pass join record names "
                 "(explained), the unlabelled rest and how many of those are inherited blends "
                 "(exploratory). stmt level, MI+VT+CI.", "tab:r6-explained",
                 ["Pass", "Merged", "Explained", "Share", "Unlabelled", "Inherited"], body,
                 "lrrrrr")


def rules() -> str:
    body = []
    for r in read_csv(HERE / "r6_status.csv"):
        if (r["rule"], r["set"], r["level"], r["axis"]) == ("R1", "ALL", "stmt", "hw"):
            body.append([tex(r["kind"]), tex(r["pass"]), r["n"], r["aux"], tex(r["outcome"])])
            macro("Rone" + r["kind"].title(), tex(r["outcome"]))
    return table("Round 6, rule 1: the pass that loses most of each hardware kind, its share and "
                 "the null share (stmt, MI+VT+CI).", "tab:r6-rule1",
                 ["Kind", "Pass", "Losses", "Share/null", "Outcome"], body, "llrcl")


def detect() -> str:
    path = HERE / "l15_detect_design.csv"
    if not path.is_file():
        return ""
    acc: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0, 0])
    for r in read_csv(path):
        a = acc[(r["arm"], r["kind"], r["snapshot"])]
        a[0] += int(r["counted"])
        a[1] += int(r["matched"])
        a[2] += int(r["gt"])
    kinds = [k for k in KDICT if any(k == kk for _, kk, _ in acc)]
    body = []
    for k in kinds:
        row = [tex(k)]
        for arm in ARMS:
            for s in ("S7", "S8"):
                c, m, g = acc.get((arm, k, s), [0, 0, 0])
                row.append(f"{m / g:.2f}" if g else "--")
        g7 = acc.get(("WB", k, "S7"), [0, 0, 0])[2]
        if g7:
            body.append([row[0], str(g7), *row[1:]])
    return table("Round 6: recall per kind of the three arms on the gate netlist (S7) and the "
                 "LUT netlist (S8), MI+VT+CI pooled; GT is the S7 count.", "tab:r6-detect",
                 ["Kind", "GT", "B S7", "B S8", "W S7", "W S8", "WB S7", "WB S8"], body,
                 "lrrrrrrr")


def lost_list() -> str:
    body = []
    for r in read_csv(HERE / "l15_lost_list.csv"):
        if r["set"] == "MI" and r["explained"] == "1" and r["n_partners"] == "1":
            body.append([tex(r["design"].removeprefix("micro_")), f'{tex(r["file"])}:{r["span"]}',
                         tex(r["kind"]), tex(r["pass"]), tex(r["partners"].replace("@", " "))])
        if len(body) == 8:
            break
    return table("Round 6: eight lost micro constructs, 'construct at file:line lost at pass P "
                 "because merged with Q' (first rows of \\code{l15\\_lost\\_list.csv} with one "
                 "labelled partner).", "tab:r6-list",
                 ["Design", "Construct", "Kind", "Pass", "Joined with"], body, "lllll")


def main() -> int:
    parts = [status_table(), kind_pass(), reasons(), explained(), rules(), detect(), lost_list()]
    body = "\n\n".join(p for p in parts if p)
    mac = "\n".join(rf"\newcommand{{\{k}}}{{{v}}}" for k, v in sorted(MACROS.items()))
    (OUT / "round6-tables.tex").write_text(
        "% generated by experiments/round6/paper_tables.py\n" + mac + "\n\n" + body + "\n",
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
