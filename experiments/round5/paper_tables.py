#!/usr/bin/env python3
"""Write docs/paper/round5-tables.tex and round5-log.tex from the round-5 CSVs.

Every number the round-5 prose cites is a macro (``\\rfv...``) generated here; statuses come from
``r5_status.csv`` (``decide.py``, Stage-0 rules). No timestamps: a rerun reproduces the files
byte for byte.

Usage: paper_tables.py [--out PATH]
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import r5lib

DEFAULT_OUT = r5lib.HERE.parents[1] / "docs" / "paper" / "round5-tables.tex"
MACROS: dict[str, str] = {}
KINDS = ("ff_en", "ff_srst", "register", "adder", "subtractor", "comparator", "eq_const", "mux",
         "mux_tree", "counter", "fsm")
ARM_NAME = {"R2N": "R2N", "R2C": "R2C", "W": "W", "WB": "WB"}
WORDS = {"0": "Zero", "1": "One", "2": "Two", "3": "Three", "4": "Four", "5": "Five",
         "6": "Six", "7": "Seven", "8": "Eight", "9": "Nine"}


def rows(name: str) -> list[dict[str, str]]:
    return r5lib.read_csv(r5lib.OUT / name)


def f3(x: float | str, d: int = 3) -> str:
    return f"{float(x):.{d}f}".replace("-", "$-$")


def fi(x: float | int | str) -> str:
    return f"{int(float(x)):,}".replace(",", "{,}")


def tex(t: str) -> str:
    return t.replace("_", r"\_").replace("#", r"\#").replace("<", "$<$")


def mname(*parts: str) -> str:
    out = ""
    for p in parts:
        for ch in p:
            out += WORDS[ch] if ch.isdigit() else ch
    return "".join(c for c in out.title() if c.isalpha())


def macro(name: str, value: str) -> None:
    MACROS["rfv" + name] = value


def table(caption: str, label: str, head: list[str], body: list[list[str]], spec: str) -> str:
    lines = [r"\begin{table}[t]", rf"\caption{{{caption}}}", rf"\label{{{label}}}",
             r"\centering", r"\footnotesize", r"\resizebox{\columnwidth}{!}{%",
             rf"\begin{{tabular}}{{@{{}}{spec}@{{}}}}", r"\toprule",
             " & ".join(head) + r" \\", r"\midrule"]
    lines += [" & ".join(r) + r" \\" for r in body]
    lines += [r"\bottomrule", r"\end{tabular}}", r"\end{table}"]
    return "\n".join(lines)


def numbers() -> dict[tuple[str, str], str]:
    return {(r["hypothesis"], r["key"]): r["value"] for r in rows("r5_numbers.csv")}


def statuses() -> dict[str, tuple[str, str]]:
    return {r["hypothesis"]: (r["status"], r["numbers"]) for r in rows("r5_status.csv")}


def status_macros() -> str:
    st, nums = statuses(), numbers()
    for h, (s, note) in sorted(st.items()):
        macro(h.replace("H16", "H") + "Status", s)
        macro(h.replace("H16", "H") + "Note", tex(note))
    for (h, k), v in sorted(nums.items()):
        key = mname(h.replace("H16", "H"), *k.split("_"))
        try:
            fv = float(v)
            macro(key, fi(fv) if fv == int(fv) and abs(fv) >= 1000 else
                  (str(int(fv)) if fv == int(fv) else f3(fv)))
        except ValueError:
            macro(key, tex(v))
    body = [[f"H16{c}", tex(st[f"H16{c}"][0]), tex(st[f"H16{c}"][1])] for c in "abcdef"
            if f"H16{c}" in st]
    return table("Round 5: the six hypotheses, their status under the Stage-0 rules and the "
                 "numbers the rules use.", "tab:r5-status", ["Hypothesis", "Status", "Numbers"],
                 body, "lll")


def summary_table(floor: str, label: str) -> str:
    acc: dict[tuple[str, str], dict[str, tuple[int, int, int]]] = defaultdict(dict)
    for r in rows("l16_summary.csv"):
        if r["floor"] == floor and r["kind"] in KINDS:
            acc[(r["set"], r["kind"])][r["arm"]] = (int(r["counted"]), int(r["matched"]),
                                                    int(r["gt"]))
    body = []
    for (s, k), arms in sorted(acc.items()):
        cells = []
        for a in ("R2N", "R2C", "W", "WB"):
            if a in arms:
                c, m, g = arms[a]
                p = m / c if c else 0.0
                rec = m / g if g else 0.0
                f = 2 * m / (c + g) if c + g else 0.0
                cells.append(f"{f3(p, 2)}/{f3(rec, 2)}/{f3(f, 2)}")
            else:
                cells.append("--")
        gt = next(iter(arms.values()))[2]
        body.append([s, tex(k), str(gt), *cells])
    return table(f"Round 5, floor {floor}: precision/recall/F1 per kind and set for the "
                 "round-2 detectors (R2N, R2C) and the word-first arms (W, WB). Pooled over "
                 "the designs each arm has; GT is the first arm's count.", label,
                 ["Set", "Kind", "GT", "R2N", "R2C", "W", "WB"], body, "llrcccc")


def tiling_table() -> str:
    acc: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0])
    for r in rows("l16_tiling.csv"):
        a = acc[(r["set"], r["arm"])]
        a[0] += float(r["instances"])
        a[1] += float(r["covered"])
    body = []
    for s in ("MI", "VT", "CI", "CO"):
        body.append([s, *(f3(acc[(s, a)][1] / acc[(s, a)][0]) if acc[(s, a)][0] else "--"
                          for a in ("R2N", "R2C", "W", "WB", "null-W", "null-WB"))])
    return table("Round 5: word tiling q (share of GT words whose fragments cover 0.8) at f2.",
                 "tab:r5-tiling", ["Set", "R2N", "R2C", "W", "WB", "null W", "null WB"], body,
                 "lrrrrrr")


def time_table() -> str:
    acc: dict[str, list[float]] = defaultdict(list)
    for r in rows("l16_designs.csv"):
        if r["seconds"]:
            acc[f'{r["arm"]} {r["set"]} {r["floor"]}'].append(float(r["seconds"]))
    body = []
    for k, v in sorted(acc.items()):
        v.sort()
        body.append([tex(k), str(len(v)), f3(sum(v) / len(v), 2), f3(v[len(v) // 2], 2),
                     f3(v[-1], 2)])
    return table("Round 5: wall time per run in seconds (up to eight runs in parallel).",
                 "tab:r5-time", ["Arm set floor", "Runs", "Mean", "Median", "Max"], body, "lrrrr")


def big_table() -> str:
    t = {r["design"]: r for r in rows("l16_big_time.csv")}
    agg: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0, 0])
    for r in rows("l16_big.csv"):
        a = agg[r["design"]]
        for i, k in enumerate(("counted", "matched", "gt", "counted_F", "matched_F")):
            a[i] += int(r[k])
    body = []
    for d, r in t.items():
        a = agg.get(d)
        body.append([tex(d), tex(r["status"]), r["seconds"] or "--",
                     *([str(x) for x in a] if a else ["--"] * 5)])
    return table("Round 5, BIG set (arm W, f2): counted, matched, GT and the same after the "
                 "repetition filter F.", "tab:r5-big",
                 ["Design", "Status", "s", "Counted", "Matched", "GT", "Counted F", "Matched F"],
                 body, "llrrrrrr")


# -- exploratory entries (review fixes, 2026-10-25-c): macros ``\rfvX...`` and three tables -------
FSM_GROUPS = ("fsm", "counter", "register", "none")
ARM_CAP = {"R2N": "RtwoN", "R2C": "RtwoC", "W": "W", "WB": "Wb", "W1": "WOne", "WB1": "WbOne"}
XSETS = ("MI", "VT", "CI", "CO")


def xrows(name: str) -> list[dict[str, str]]:
    path = r5lib.OUT / name
    return r5lib.read_csv(path) if path.is_file() else []


def f1_of(c: int, m: int, g: int) -> float:
    return 2 * m / (c + g) if c + g else 0.0


def fsm_macros() -> dict[str, dict[str, int]]:
    """FSM candidates by ground-truth kind per arm; macros ``XFsmCand<Arm><Group>`` (all
    hypotheses), ``XFsmCnt<Arm><Group>`` (counted), ``XFsmDec<Arm>`` (with a decoder)."""
    rows = xrows("l16_x_fsmcand.csv")
    out: dict[str, dict[str, int]] = {}
    for arm in ("W", "WB", "W1", "WB1"):
        mine = [r for r in rows if r["arm"] == arm]
        cnt = {"all": len(mine), "counted": sum(int(r["counted"]) for r in mine),
               "dec": sum(1 for r in mine if int(r["decoders"]) > 0)}
        macro(f"XFsmCand{ARM_CAP[arm]}Total", str(len(mine)))
        macro(f"XFsmCnt{ARM_CAP[arm]}Total", str(cnt["counted"]))
        macro(f"XFsmDec{ARM_CAP[arm]}", str(cnt["dec"]))
        for g in FSM_GROUPS:
            a = sum(1 for r in mine if r["gt_group"] == g)
            b = sum(1 for r in mine if r["gt_group"] == g and r["counted"] == "1")
            macro(f"XFsmCand{ARM_CAP[arm]}{g.capitalize()}", str(a))
            macro(f"XFsmCnt{ARM_CAP[arm]}{g.capitalize()}", str(b))
            cnt[g] = a
        out[arm] = cnt
    comp = xrows("l16_x_fsmcomp.csv")
    for arm in ("W", "WB"):
        mine = [r for r in comp if r["arm"] == arm]
        macro(f"XFsmCompTotal{ARM_CAP[arm]}", str(len(mine)))
        macro(f"XFsmCompCounted{ARM_CAP[arm]}", str(sum(int(r["counted"]) for r in mine)))
        macro(f"XFsmCompReg{ARM_CAP[arm]}",
              str(sum(1 for r in mine if "register" in r["conflicts_with"].split("+"))))
    return out


def fsm_rule_table(counts: dict[str, dict[str, int]]) -> str:
    kind: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for r in xrows("l16_x_fsmkind.csv"):
        a = kind[r["arm"]]
        a[0] += int(r["counted"])
        a[1] += int(r["matched"])
        a[2] += int(r["gt"])
    chain: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    for r in rows("l16_chain.csv") + xrows("l16_x_chain.csv"):
        a = chain[r["arm"]]
        if r["item"].startswith("fsm_"):
            a[2] += int(r["complete"])
            a[3] += 1
        else:
            a[0] += int(r["complete"])
            a[1] += 1
    body = []
    for arm, rule in (("R2N", "per-bit"), ("R2C", "per-bit"), ("W", "round 5"), ("WB", "round 5"),
                      ("W1", "Stage 0"), ("WB1", "Stage 0")):
        c, m, g = kind[arm]
        ch = chain[arm]
        cand = counts.get(arm)
        macro(f"XFsmKind{ARM_CAP[arm]}Counted", str(c))
        macro(f"XFsmKind{ARM_CAP[arm]}Matched", str(m))
        macro(f"XFsmKind{ARM_CAP[arm]}Gt", str(g))
        macro(f"XFsmKind{ARM_CAP[arm]}F", f3(f1_of(c, m, g)))
        macro(f"XChain{ARM_CAP[arm]}Complete", str(ch[0]))
        macro(f"XChain{ARM_CAP[arm]}Fsm", str(ch[2]))
        body.append([ARM_NAME.get(arm, arm), rule, f"{c}/{m}/{g}", f3(f1_of(c, m, g), 2),
                     f"{ch[0]}/{ch[1]}", f"{ch[2]}/{ch[3]}",
                     *([str(cand[x]) for x in ("all", *FSM_GROUPS)] if cand else ["--"] * 5)])
    return table("Round 5, exploratory (2026-10-25-c): the FSM rule. W and WB use the evaluated "
                 "rule (feedback coupling, no decoder), W1 and WB1 the Stage-0 rule (feedback "
                 "plus at least two word-level decoders). Kind-level counted/matched/GT of "
                 "\\code{fsm} and F1 pooled over MI, VT, CI and CO at f2; chains complete "
                 "and FSM instances hit on MI and VT; the last columns classify every "
                 "\\code{fsm} hypothesis by the ground-truth kind of its flip-flops (FSM, "
                 "counter, register that is neither, none).", "tab:r5x-fsm",
                 ["Arm", "Rule", "fsm c/m/GT", "F1", "Chains", "FSM hit", "Hyp.", "FSM",
                  "Counter", "Register", "None"], body, "llccccccccc")


def nullmix_table() -> str:
    body = []
    for r in xrows("l16_x_nullmix.csv"):
        if r["set"] != "VT":
            continue
        inst = float(r["instances"])
        key = f"XNullVt{ARM_CAP[r['arm']]}{r['subset'].capitalize().replace('_', '')}"
        macro(key + "Cands", fi(r["candidates"]))
        macro(key + "Max", fi(r["max_cells"]))
        macro(key + "Big", fi(r["cells_ge10"]))
        macro(key + "Q", f3(float(r["covered_real"]) / inst))
        macro(key + "Null", f3(float(r["covered_null"]) / inst))
        body.append([ARM_NAME[r["arm"]], tex(r["subset"]), r["candidates"], r["cells_ge10"],
                     r["max_cells"], f3(float(r["covered_real"]) / inst),
                     f3(float(r["covered_null"]) / inst)])
    return table("Round 5, exploratory (2026-10-25-c): tiling on VT and its random null by "
                 "candidate subset. Candidates of at least ten cells and the largest candidate "
                 "drive the null; the same \\code{ff\\_en} candidates give a null of a few "
                 "percent for R2N and 0.19 for WB.", "tab:r5x-null",
                 ["Arm", "Subset", "Candidates", "$\\ge$10 cells", "Max cells", "q", "q null"],
                 body, "llrrrrr")


def eqconst_macros() -> None:
    by_set: dict[str, list[int]] = defaultdict(lambda: [0] * 7)
    for r in xrows("l16_x_eqconst.csv"):
        a = by_set[r["set"]]
        for i, k in enumerate(("r2n", "w", "wb", "w_not_in_r2n", "wb_equals_r2n", "w_ne",
                               "w_ne_refuted")):
            a[i] += int(r[k])
    n_designs = sum(1 for _ in xrows("l16_x_eqconst.csv"))
    tot = [sum(v[i] for v in by_set.values()) for i in range(7)]
    for s in ("MI", "VT"):
        v = by_set[s]
        macro(f"XEq{s.capitalize()}RtwoN", fi(v[0]))
        macro(f"XEq{s.capitalize()}W", fi(v[1]))
        macro(f"XEq{s.capitalize()}Wb", fi(v[2]))
    macro("XEqDesigns", str(n_designs))
    macro("XEqWNotInRtwoN", str(tot[3]))
    macro("XEqWbSame", str(tot[4]))
    macro("XEqNe", str(tot[5]))
    macro("XEqNeRefuted", str(tot[6]))


def time_macros() -> None:
    t = [r for r in rows("l16_big_time.csv") if r["status"] == "ok" and r["seconds"]]
    t.sort(key=lambda r: float(r["seconds"]))
    if t:
        macro("XTimeBigMin", f3(t[0]["seconds"], 1))
        macro("XTimeBigMinName", tex(t[0]["design"]))
        macro("XTimeBigMax", f3(t[-1]["seconds"], 0))
        macro("XTimeBigMaxName", tex(t[-1]["design"]))
    med: dict[str, list[float]] = defaultdict(list)
    for r in rows("l16_designs.csv"):
        if r["seconds"] and r["floor"] == "f2" and r["arm"] in ("W", "WB"):
            med[f'{r["arm"]} {r["set"]}'].append(float(r["seconds"]))
    for arm in ("W", "WB"):
        ms = sorted(sorted(v)[len(v) // 2] for k, v in med.items() if k.startswith(arm + " "))
        macro(f"XTime{ARM_CAP[arm]}MedLo", f3(ms[0], 2))
        macro(f"XTime{ARM_CAP[arm]}MedHi", f3(ms[-1], 2))


def f3_macros() -> None:
    """f3: counted ``eq_const`` candidates per arm (MI + VT) with their matches, and the number of
    runs WB lacks against W (the 900 s limit)."""
    acc: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in rows("l16_summary.csv"):
        if r["floor"] == "f3" and r["kind"] == "eq_const":
            acc[r["arm"]][0] += int(r["counted"])
            acc[r["arm"]][1] += int(r["matched"])
    for arm in ("R2N", "W", "WB"):
        macro(f"XFthreeEq{ARM_CAP[arm]}Counted", fi(acc[arm][0]))
        macro(f"XFthreeEq{ARM_CAP[arm]}Matched", str(acc[arm][1]))
    runs: dict[tuple[str, str], int] = defaultdict(int)
    for r in rows("l16_designs.csv"):
        if r["floor"] == "f3":
            runs[(r["arm"], r["set"])] += 1
    macro("XFthreeWbMissing",
          str(sum(runs[("W", s)] - runs[("WB", s)] for s in ("MI", "VT"))))


def bigwb_table() -> str:
    st = {r["design"]: r for r in xrows("l16_x_bigwb_time.csv")}
    agg: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0] * 5)
    for r in xrows("l16_x_bigwb.csv"):
        a = agg[(r["arm"], r["design"])]
        for i, k in enumerate(("counted", "matched", "gt", "counted_F", "matched_F")):
            a[i] += int(r[k])
    order = [r["design"] for r in rows("l16_big_time.csv")]
    body = []
    done = 0
    tot = {"W": [0] * 5, "WB": [0] * 5}
    for d in order:
        r = st.get(d, {"status": "not run", "seconds": ""})
        w, wb = agg.get(("W", d)), agg.get(("WB", d))
        if wb:
            done += 1
            for arm, a in (("W", w), ("WB", wb)):
                if a:
                    tot[arm] = [x + y for x, y in zip(tot[arm], a, strict=True)]
        body.append([tex(d), tex(r["status"]), r["seconds"] or "--",
                     f"{w[0]}/{w[1]}" if w else "--", f"{wb[0]}/{wb[1]}" if wb else "--",
                     str(wb[2]) if wb else "--"])
    timeouts = sum(1 for r in st.values() if r["status"] == "timeout")
    errors = sum(1 for r in st.values() if r["status"] == "error")
    macro("XBigWbDone", str(done))
    macro("XBigWbTimeout", str(timeouts))
    macro("XBigWbError", str(errors))
    macro("XBigWbTotal", str(len(order)))
    for arm in ("W", "WB"):
        c, m, _g, cf, mf = tot[arm]
        gt = tot[arm][2]
        macro(f"XBigWbCounted{ARM_CAP[arm]}", fi(c))
        macro(f"XBigWbMatched{ARM_CAP[arm]}", fi(m))
        macro(f"XBigWbGt{ARM_CAP[arm]}", fi(gt))
        macro(f"XBigWbFAll{ARM_CAP[arm]}", f3(f1_of(c, m, gt)) if done else "n/a")
        macro(f"XBigWbFFilt{ARM_CAP[arm]}", f3(f1_of(cf, mf, gt)) if done else "n/a")
    return table("Round 5, exploratory (2026-10-25-c): arm WB on BIG with the Stage-0 cap of "
                 "1800 s per design (smallest first). Counted/matched for W and WB on the "
                 "designs where WB finished; GT words of the design.", "tab:r5x-bigwb",
                 ["Design", "WB status", "s", "W c/m", "WB c/m", "GT"], body, "llrccr")


def build() -> str:
    parts = [status_macros(), tiling_table(), summary_table("f2", "tab:r5-f2"),
             summary_table("f3", "tab:r5-f3"), summary_table("f1-k6", "tab:r5-f1"),
             big_table(), time_table()]
    counts = fsm_macros()
    eqconst_macros()
    time_macros()
    f3_macros()
    parts += [fsm_rule_table(counts), nullmix_table(), bigwb_table()]
    head = "% Generated by experiments/round5/paper_tables.py; do not edit.\n"
    macros = "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in sorted(MACROS.items()))
    return head + macros + "\n\n".join(parts) + "\n"


def log_text() -> str:
    st = statuses()
    lines = ["% Generated by experiments/round5/paper_tables.py; do not edit.",
             r"\begin{table}[t]",
             r"\caption{Round 5 (2026-10-25): the hypotheses and their status.}",
             r"\label{tab:r5-log}", r"\centering", r"\footnotesize",
             r"\begin{tabular}{@{}ll@{}}", r"\toprule", r"Hypothesis & Status \\", r"\midrule"]
    lines += [rf"{h} & {tex(s)}{' (degenerate)' if 'degenerate' in n else ''} \\"
              for h, (s, n) in sorted(st.items())]
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    out = Path(ap.parse_args().out)
    out.write_text(build(), encoding="utf-8")
    out.with_name("round5-log.tex").write_text(log_text(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
