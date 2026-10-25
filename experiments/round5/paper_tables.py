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


def build() -> str:
    parts = [status_macros(), tiling_table(), summary_table("f2", "tab:r5-f2"),
             summary_table("f3", "tab:r5-f3"), summary_table("f1-k6", "tab:r5-f1"),
             big_table(), time_table()]
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
    lines += [rf"{h} & {tex(s)} \\" for h, (s, _n) in sorted(st.items())]
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
