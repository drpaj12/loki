#!/usr/bin/env python3
"""Write docs/paper/veval-tables.tex from the committed veval-l0 CSVs and stats.json.

Inputs (all in this directory): benchmark.csv, complexity.csv, features.csv, sizes.csv,
stats.json. Output: ../../docs/paper/veval-tables.tex (or --out). No timestamps, no
environment: re-running reproduces the file byte for byte. The script cross-checks its own
counts and means against stats.json and stops on any mismatch.

Tables written:
  tab:veval-bench     complexity bins, counts of the 156 refs and of the 150 built designs
  tab:veval-sample    feature matrix of 12 designs (3 per quartile, fixed rank rule below)
  tab:veval-features  designs showing each feature, per quartile (count and percent)
  tab:veval-sizes     mean / median node counts per floor and per quartile

Sample rule (no hand picking): inside each quartile sort the built designs by
(f3 node count, design id) and take the 0-based ranks floor(n/6), floor(n/2), floor(5n/6).

Symbols: x (\\ding{55}) = count 0, check (\\ding{51}) = one, double check = two or more.
fsm and control are 0/1 flags (the experiment records no count). The bus column is
``buses_wide`` (distinct multi-bit buses), not ``buses``, which is at least 1 everywhere.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUARTILES = ("Q1", "Q2", "Q3", "Q4")
BINS = {"Q1": "3--23", "Q2": "24--111", "Q3": "112--1064", "Q4": "1065--1326"}
FEATURES = (
    ("arithmetic", "Arithmetic", False),
    ("select", "Select/mux", False),
    ("storage", "Storage", False),
    ("fsm", "FSM", True),
    ("control", "Control", True),
    ("buses_wide", "Wide buses", False),
)
FLOORS = ("f1-k6", "f2", "f3")
TOL = 1e-5


def read_csv(name: str) -> list[dict[str, str]]:
    with (HERE / name).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def tex(text: str) -> str:
    return text.replace("_", r"\_")


def sym(count: int, flag: bool) -> str:
    if count <= 0:
        return r"\ding{55}"
    if count == 1 or flag:
        return r"\ding{51}"
    return r"\ding{51}\ding{51}"


def pct(num: int, den: int) -> str:
    return f"{100.0 * num / den:.0f}"


def num1(x: float) -> str:
    return f"{x:.1f}"


def check_close(label: str, got: float, want: float) -> None:
    if abs(got - want) > TOL:
        raise SystemExit(f"stats.json mismatch for {label}: computed {got}, recorded {want}")


def sample_ids(bench: list[dict[str, str]]) -> list[str]:
    ids: list[str] = []
    for q in QUARTILES:
        rows = sorted(
            (r for r in bench if r["quartile"] == q),
            key=lambda r: (int(r["f3_nodes"]), r["design"]),
        )
        n = len(rows)
        for rank in (n // 6, n // 2, (5 * n) // 6):
            ids.append(rows[rank]["design"])
    return ids


def table_bench(cplx: list[dict[str, str]], built: set[str], stats: dict) -> list[str]:
    lines = [
        r"\begin{table}[t]",
        r"\caption{The VerilogEval spec-to-rtl references by Gate-Breaker complexity quartile "
        r"(absolute bins of Table~II; score range observed in the 156 refs; pyverilog AST "
        r"scores against regex-fallback scores; built = designs with all three floors).}",
        r"\label{tab:veval-bench}",
        r"\centering",
        r"\footnotesize",
        r"\begin{tabular}{@{}lrrrrrr@{}}",
        r"\toprule",
        r"Quartile & Bin & Observed & Refs & AST/regex & Built \\",
        r"\midrule",
    ]
    tot = [0, 0, 0, 0]
    for q in QUARTILES:
        rows = [r for r in cplx if r["quartile"] == q]
        scores = [int(r["score"]) for r in rows]
        ast = sum(1 for r in rows if r["method"] == "ast")
        rx = sum(1 for r in rows if r["method"] == "regex")
        nb = sum(1 for r in rows if r["design"] in built)
        check_close(f"built {q}", nb, stats["feature_coverage"]["by_quartile"][q])
        tot = [tot[0] + len(rows), tot[1] + ast, tot[2] + rx, tot[3] + nb]
        lines.append(
            f"{q} & {BINS[q]} & {min(scores)}--{max(scores)} & {len(rows)} & "
            f"{ast}/{rx} & {nb} \\\\"
        )
    lines += [
        r"\midrule",
        f"All & & & {tot[0]} & {tot[1]}/{tot[2]} & {tot[3]} \\\\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ]
    return lines


def table_sample(feats: dict[str, dict[str, str]], bench: list[dict[str, str]]) -> list[str]:
    nodes = {r["design"]: r["f3_nodes"] for r in bench}
    lines = [
        r"\begin{table}[t]",
        r"\caption{Benchmark feature matrix, a sample of 12 of the 150 designs (the designs at "
        r"ranks $\lfloor n/6\rfloor$, $\lfloor n/2\rfloor$ and $\lfloor 5n/6\rfloor$ by f3 node "
        r"count inside each quartile). \ding{55}: feature absent; \ding{51}: one; "
        r"\ding{51}\ding{51}: more than one; FSM and control are 0/1 flags. Features are read "
        r"from the f3 floor (Section~\ref{sec:veval-features}).}",
        r"\label{tab:veval-sample}",
        r"\centering",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{3pt}",
        r"\begin{tabular}{@{}llrcccccc@{}}",
        r"\toprule",
        r"Design & Q & f3 nodes & Arith & Sel & Stor & FSM & Ctl & Bus \\",
        r"\midrule",
    ]
    ids = sample_ids(bench)
    for i, design in enumerate(ids):
        f = feats[design]
        cells = [sym(int(f[col]), flag) for col, _, flag in FEATURES]
        name = design[3:] if design.startswith("ve_") else design
        lines.append(
            f"{tex(name)} & {f['quartile']} & {nodes[design]} & " + " & ".join(cells) + " \\\\"
        )
        if i % 3 == 2 and i != len(ids) - 1:
            lines.append(r"\midrule")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return lines


def table_features(feats: dict[str, dict[str, str]], stats: dict) -> list[str]:
    per_q = {q: [f for f in feats.values() if f["quartile"] == q] for q in QUARTILES}
    n_all = len(feats)
    lines = [
        r"\begin{table*}[t]",
        r"\caption{Designs showing each feature, per complexity quartile: count (percent of the "
        r"quartile). The last column counts designs with two or more instances of the feature "
        r"(always 0 for the 0/1 flags). Wide buses are distinct multi-bit buses; a design "
        r"with only single-bit ports has none.}",
        r"\label{tab:veval-features}",
        r"\centering",
        r"\footnotesize",
        r"\begin{tabular}{@{}lrrrrrr@{}}",
        r"\toprule",
        "Feature & "
        + " & ".join(f"{q} ($n{{=}}{len(per_q[q])}$)" for q in QUARTILES)
        + f" & All ($n{{=}}{n_all}$) & $\\geq 2$ \\\\",
        r"\midrule",
    ]
    for col, label, flag in FEATURES:
        cells = []
        total = 0
        for q in QUARTILES:
            c = sum(1 for f in per_q[q] if int(f[col]) >= 1)
            check_close(f"{col} {q}", c, stats["feature_coverage"][col][q])
            total += c
            cells.append(f"{c} ({pct(c, len(per_q[q]))}\\%)")
        ge2 = sum(1 for f in feats.values() if int(f[col]) >= 2)
        check_close(f"{col} ge1", total, stats["feature_coverage"][col]["ge1"])
        check_close(f"{col} ge2", ge2, stats["feature_coverage"][col]["ge2"])
        cells.append(f"{total} ({pct(total, n_all)}\\%)")
        cells.append(str(ge2))
        lines.append(f"{label} & " + " & ".join(cells) + " \\\\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table*}"]
    return lines


def size_stats(rows: list[dict[str, str]], col: str) -> tuple[float, float]:
    vals = [int(r[col]) for r in rows]
    return statistics.mean(vals), statistics.median(vals)


def table_sizes(sizes: list[dict[str, str]], stats: dict) -> list[str]:
    by = {(f, q): [r for r in sizes if r["floor"] == f and r["quartile"] == q]
          for f in FLOORS for q in QUARTILES}
    allrows = {f: [r for r in sizes if r["floor"] == f] for f in FLOORS}
    lines = [
        r"\begin{table}[t]",
        r"\caption{Benchmark size per technology-mapping floor, 150 designs: mean / median "
        r"node count (top), and per complexity quartile (bottom; nodes). Nodes are all graph "
        r"nodes of the floor netlist: primary inputs and outputs, constants, cells.}",
        r"\label{tab:veval-sizes}",
        r"\centering",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{3pt}",
        r"\begin{tabular}{@{}lrrr@{}}",
        r"\toprule",
        r"All 150 designs & f1-k6 & f2 & f3 \\",
        r"\midrule",
    ]
    for col, label in (("nodes", "Nodes"), ("cells", "Cells"), ("nets", "Nets")):
        cells = []
        for f in FLOORS:
            mean, med = size_stats(allrows[f], col)
            want = stats["sizes"][f][col]["all"]
            check_close(f"{f} {col} mean", mean, want["mean"])
            check_close(f"{f} {col} median", med, want["median"])
            cells.append(f"{num1(mean)} / {num1(med)}")
        lines.append(f"{label} & " + " & ".join(cells) + " \\\\")
    lines += [r"\midrule", r"Nodes by quartile & f1-k6 & f2 & f3 \\", r"\midrule"]
    for q in QUARTILES:
        cells = []
        for f in FLOORS:
            rows = by[(f, q)]
            mean, med = size_stats(rows, "nodes")
            want = stats["sizes"][f]["nodes"][q]
            check_close(f"{f} nodes {q} mean", mean, want["mean"])
            check_close(f"{f} nodes {q} median", med, want["median"])
            check_close(f"{f} nodes {q} n", len(rows), want["n"])
            cells.append(f"{num1(mean)} / {num1(med)}")
        n = len(by[("f3", q)])
        lines.append(f"{q} ($n{{=}}{n}$) & " + " & ".join(cells) + " \\\\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return lines


def build() -> str:
    bench = read_csv("benchmark.csv")
    cplx = read_csv("complexity.csv")
    feats = {r["design"]: r for r in read_csv("features.csv")}
    sizes = read_csv("sizes.csv")
    stats = json.loads((HERE / "stats.json").read_text(encoding="utf-8"))
    built = {r["design"] for r in bench}
    out = [
        "% Generated by experiments/veval-l0/paper_tables.py from benchmark.csv, complexity.csv,",
        "% features.csv, sizes.csv and stats.json. Do not edit; rerun the script.",
    ]
    for block in (
        table_bench(cplx, built, stats),
        table_sample(feats, bench),
        table_features(feats, stats),
        table_sizes(sizes, stats),
    ):
        out.append("")
        out.extend(block)
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=HERE.parent.parent / "docs/paper/veval-tables.tex")
    args = ap.parse_args()
    args.out.write_text(build(), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
