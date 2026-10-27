#!/usr/bin/env python3
"""Write docs/paper/round6-tables.tex and round6-log.tex from the round-6 CSVs.

Every number the round-6 prose cites is a macro (``\\rsx...``) generated here; statuses come from
``r6_status.csv`` (``decide.py``: Stage-0 rules under the Stage-0 null; the persistence null of
Amendment A is exploratory and always labelled so). No timestamps: a rerun reproduces the files
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
PASS_HEAD = {"S2_fsm": "fsm", "S3_opt": "opt", "S4_flatten": "flatten", "S5_opt_full": "opt -full",
             "S6_wreduce": "wreduce", "S7_lower": "lower", "S8_abc": "abc"}
STAGE0 = "Stage-0 null (persistence-free; see amendment)"
ARMS = ("B", "W", "WB")
KDICT = ("ff_en", "ff_srst", "register", "adder", "subtractor", "comparator", "eq_const", "mux",
         "mux_tree", "counter", "fsm")


def tex(t: str) -> str:
    return t.replace("_", r"\_").replace("#", r"\#").replace("<", "$<$").replace(">", "$>$")


def macro(name: str, value: str) -> None:
    MACROS["rsx" + name] = value


def table(caption: str, label: str, head: list[str], body: list[list[str]], spec: str) -> str:
    for row in body:
        if len(row) != len(head):
            raise ValueError(f"table {label}: {len(row)} cells under {len(head)} headers: {row}")
    lines = [r"\begin{table}[t]", rf"\caption{{{caption}}}", rf"\label{{{label}}}",
             r"\centering", r"\footnotesize", r"\resizebox{\columnwidth}{!}{%",
             rf"\begin{{tabular}}{{@{{}}{spec}@{{}}}}", r"\toprule",
             " & ".join(head) + r" \\", r"\midrule"]
    lines += [" & ".join(r) + r" \\" for r in body]
    lines += [r"\bottomrule", r"\end{tabular}}", r"\end{table}"]
    return "\n".join(lines)


def kind_pass() -> str:
    acc: dict[tuple[str, str], tuple[int, int, float, float]] = {}
    for r in read_csv(HERE / "l15_kind_pass.csv"):
        if (r["set"], r["level"], r["axis"]) == ("ALL", "stmt", "hw"):
            acc[(r["kind"], r["pass"])] = (int(r["at_risk"]), int(r["first_losses"]),
                                           float(r["null_expected"]), float(r["pnull_mean"]))
    body = []
    for k in HW:
        cells = []
        for p in ALLP:
            a = acc.get((k, p))
            cells.append(f"{a[1]}/{a[2]:.0f}/{a[3]:.0f}" if a and a[0] else "--")
        n0 = acc.get((k, "S3_opt"))
        body.append([k, str(n0[0]) if n0 else "0", *cells])
    return table("Round 6: first losses of a unit per hardware kind and pass, as real/Stage-0 "
                 "null/persistence null (expected counts, stmt level, MI+VT+CI). The first column "
                 "is the units at risk at \\code{opt}. The Stage-0 null is persistence-free and "
                 "overstates chance losses; the persistence null (mean of 50 draws, exploratory, "
                 "post-data) starts from the real objects of the previous snapshot. Both nulls and "
                 "the real count use the same units at risk (separable at the previous snapshot, "
                 "not lost earlier). The \\code{logic} loss at \\code{flatten} is the 68 "
                 "\\code{INSTANCE} units (\\code{removed}), not dead logic. The loss measure "
                 "cannot see FSM re-encoding (hardware kind \\code{fsm} is read at S1, before the "
                 "\\code{fsm} pass), so the \\code{fsm} row is empty and FSM units are counted "
                 "under register, mux or logic.", "tab:r6-kindpass",
                 ["Kind", "n", *(PASS_HEAD[p] for p in ALLP)], body, "lr" + "r" * len(ALLP))


def pnull_table() -> str:
    """Real count against the persistence null with its 95% interval (exploratory)."""
    acc: dict[tuple[str, str], list[str]] = {}
    for r in read_csv(HERE / "l15_kind_pass.csv"):
        if (r["set"], r["level"], r["axis"]) == ("ALL", "stmt", "hw") and r["pass"] in PASSES:
            acc[(r["kind"], r["pass"])] = [r["first_losses"], r["null_expected"], r["pnull_mean"],
                                           r["pnull_lo"], r["pnull_hi"]]
    body = []
    for k in HW:
        cells = []
        for p in PASSES:
            a = acc.get((k, p))
            cells.append(f"{a[0]} / {float(a[1]):.0f} / {float(a[2]):.0f} [{a[3]}--{a[4]}]"
                         if a and any(float(x) for x in a) else "--")
        body.append([k, *cells])
    return table("Round 6 (exploratory, post-data): real first losses / Stage-0 null / "
                 "persistence-null mean [2.5th--97.5th percentile of the 50 per-draw totals], "
                 "stmt level, MI+VT+CI. The interval covers the draws within the fixed designs, "
                 "not variation across designs. A pass that removes objects lowers the object "
                 "count and the persistence null reads every removal as a merge, so at "
                 "\\code{opt} it is an upper bound of chance merging.", "tab:r6-pnull",
                 ["Kind", *(PASS_HEAD[p] for p in PASSES)], body, "l" + "r" * len(PASSES))


def reasons() -> str:
    acc: dict[tuple[str, str], int] = defaultdict(int)
    names: list[str] = []
    for r in read_csv(HERE / "l15_reason.csv"):
        if (r["set"], r["level"]) == ("ALL", "stmt"):
            acc[(r["reason"], r["pass"])] += int(r["losses"])
            if r["reason"] not in names:
                names.append(r["reason"])
    body = [[tex(n), *(str(acc[(n, p)]) for p in ALLP)] for n in names]
    return table("Round 6: first losses per reason class and pass (stmt level, MI+VT+CI). "
                 "Classes with no loss are kept.", "tab:r6-reason",
                 ["Reason", *(PASS_HEAD[p] for p in ALLP)], body, "l" + "r" * len(ALLP))


def headline() -> str:
    """First losses with and without the subsumed ones (Amendment C)."""
    body = []
    tot = [0, 0, 0, 0]
    for r in read_csv(HERE / "l15_subsumed.csv"):
        if (r["set"], r["level"]) == ("ALL", "stmt") and int(r["first_losses"]):
            n, sub, rem, mer = (int(r[c]) for c in ("first_losses", "subsumed", "removed",
                                                    "merged"))
            body.append([tex(r["pass"]), str(n), str(sub), f"{sub / n:.2f}", str(mer + rem)])
            tot = [t + v for t, v in zip(tot, (n, sub, rem, mer), strict=True)]
    body.append(["all", str(tot[0]), str(tot[1]), f"{tot[1] / tot[0]:.2f}", str(tot[2] + tot[3])])
    macro("LostAll", str(tot[0]))
    macro("SubsumedAll", str(tot[1]))
    macro("LostNoSub", str(tot[2] + tot[3]))
    macro("SubsumedShare", f"{tot[1] / tot[0]:.2f}")
    return table("Round 6: first losses (the Stage-0 total) and, apart from them, the "
                 "\\code{subsumed} ones (the unit survives only as the enclosing statement of a "
                 "finer unit that is still alive) and the remaining merged-plus-removed losses "
                 "(stmt level, MI+VT+CI).", "tab:r6-headline",
                 ["Pass", "First losses", "Subsumed", "Share", "Merged + removed"], body, "lrrrr")


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
    inh: dict[str, tuple[int, int, int]] = {}
    for r in read_csv(HERE / "l15_explained.csv"):
        if (r["set"], r["level"]) == ("ALL", "stmt"):
            exp[r["pass"]] = (int(r["merged"]), int(r["explained"]))
    for r in read_csv(HERE / "l15_x_inherited.csv"):
        if (r["set"], r["level"]) == ("ALL", "stmt"):
            inh[r["pass"]] = (int(r["unlabelled"]), int(r["inherited"]),
                              int(r["inherited_subset"]))
    body = []
    for p in ALLP:
        m, e = exp[p]
        u, i, sub = inh[p]
        if m:
            body.append([tex(p), str(m), str(e), f"{e / m:.3f}", str(u), str(i), str(sub)])
    tm = sum(v[0] for v in exp.values())
    te = sum(v[1] for v in exp.values())
    tu = sum(v[0] for v in inh.values())
    ti = sum(v[1] for v in inh.values())
    ts = sum(v[2] for v in inh.values())
    macro("MergedAll", str(tm))
    macro("ExplainedAll", str(te))
    macro("ExplainedShare", f"{te / tm:.3f}")
    macro("UnlabelledAll", str(tu))
    macro("InheritedAll", str(ti))
    macro("InheritedSubsetAll", str(ts))
    body.append(["all", str(tm), str(te), f"{te / tm:.3f}", str(tu), str(ti), str(ts)])
    for pm in ("opt", "abc"):
        key = "S3_opt" if pm == "opt" else "S8_abc"
        macro("ExplShare" + pm.title(), f"{exp[key][1] / exp[key][0]:.3f}")
        macro("ExplMerged" + pm.title(), str(exp[key][0]))
        macro("ExplExplained" + pm.title(), str(exp[key][1]))
    sets: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in read_csv(HERE / "l15_explained.csv"):
        if r["level"] == "stmt" and r["set"] != "ALL":
            sets[r["set"]][0] += int(r["merged"])
            sets[r["set"]][1] += int(r["explained"])
    for name, (m, e) in sets.items():
        macro("ExplShare" + name, f"{e / m:.3f}")
        macro("ExplMerged" + name, str(m))
        macro("ExplExplained" + name, str(e))
    return table("Round 6: merged first losses, those a labelled same-pass join record names "
                 "(explained), the unlabelled rest and how many of those are inherited blends "
                 "(exploratory; by descent through the parent records, then by the earlier subset "
                 "check). stmt level, MI+VT+CI.", "tab:r6-explained",
                 ["Pass", "Merged", "Explained", "Share", "Unlabelled", "Inherited (descent)",
                  "Inherited (subset)"], body, "lrrrrrr")


def rules() -> str:
    body = []
    rows = [r for r in read_csv(HERE / "r6_status.csv")
            if (r["rule"], r["set"], r["level"], r["axis"]) == ("R1", "ALL", "stmt", "hw")]
    for kind in sorted({r["kind"] for r in rows}):
        by = {r["null"]: r for r in rows if r["kind"] == kind}
        s0, pp = by["stage0"], by["persist"]
        body.append([tex(kind), tex(s0["pass"]), s0["n"], s0["aux"], tex(s0["outcome"]),
                     pp["aux"], tex(pp["outcome"])])
        macro("Rone" + kind.title(), tex(s0["outcome"]))
        macro("RonePersist" + kind.title(), tex(pp["outcome"]))
    return table("Round 6, rule 1: the pass that loses most of each hardware kind, its share, and "
                 "the outcome under the pre-registered Stage-0 null (persistence-free; see "
                 "amendment) and, beside it and exploratory (post-data), under the persistence "
                 "null with the same thresholds (stmt, MI+VT+CI). Where they differ, neither is "
                 "confirmatory.", "tab:r6-rule1",
                 ["Kind", "Pass", "Losses", "Share/Stage-0 null", "Stage-0", "Share/persist.",
                  "Persist. (expl.)"], body, "llrcl" + "cl")


def detect() -> str:
    path = HERE / "l15_detect_design.csv"
    if not path.is_file():
        return ""
    per: dict[tuple[str, str, str, str], dict[str, tuple[int, int, int]]] = defaultdict(dict)
    for r in read_csv(path):
        per[(r["set"], r["arm"], r["kind"], r["snapshot"])][r["design"]] = (
            int(r["counted"]), int(r["matched"]), int(r["gt"]))
    # paired set (as decide.detect_pooled): designs with rows at both S7 and S8
    acc: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0, 0])
    for (name, arm, kind, snap), rows in per.items():
        other = per.get((name, arm, kind, "S8" if snap == "S7" else "S7"), {})
        for d, v in rows.items():
            if d in other:
                a = acc[(arm, kind, snap)]
                a[0] += v[0]
                a[1] += v[1]
                a[2] += v[2]
    kinds = [k for k in KDICT if any(k == kk for _, kk, _ in acc)]
    body = []
    for k in kinds:
        g7 = acc.get(("WB", k, "S7"), [0, 0, 0])[2]
        g8 = acc.get(("WB", k, "S8"), [0, 0, 0])[2]
        if not g7:
            continue
        row = [tex(k), f"{g7}/{g8}"]
        for arm in ARMS:
            for snap in ("S7", "S8"):
                c, m, g = acc.get((arm, k, snap), [0, 0, 0])
                row.append(f"{m / g:.2f}" if g else "--")
        body.append(row)
    return table("Round 6: recall per kind of the three arms on the gate netlist (S7) and the "
                 "LUT netlist (S8), MI+VT+CI, on the paired designs (those with a run at both "
                 "snapshots). GT is the WB ground-truth count at S7/S8; the two differ because "
                 "the footprints are rebuilt from each snapshot's map (the S7 and S8 ground "
                 "truths are not the same instances), and the gate and LUT footprints are not like "
                 "for like.", "tab:r6-detect",
                 ["Kind", "GT S7/S8", "B S7", "B S8", "W S7", "W S8", "WB S7", "WB S8"], body,
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
    parts = [status_table(), headline(), kind_pass(), pnull_table(), reasons(), explained(),
             rules(), detect(), lost_list()]
    body = "\n\n".join(p for p in parts if p)
    mac = "\n".join(rf"\newcommand{{\{k}}}{{{v}}}" for k, v in sorted(MACROS.items()))
    (OUT / "round6-tables.tex").write_text(
        "% generated by experiments/round6/paper_tables.py\n" + mac + "\n\n" + body + "\n",
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
