"""RQ-L7: operator-recovery F1 of every existing run set, and the AST/CFG tie analysis on f3.

Run sets: the rename-l2 experiment (f1-k6, f1-earch, f2; base; calibrated and uncalibrated), the
f3-recovery experiment (calibrated and uncalibrated), the RQ-L1 LUT6 runs and the RQ-L2
VerilogEval runs. Writes ``l7_runs.csv`` (one row per run), ``l7_sets.csv`` (pooled and
per-design mean per set) and ``l7_ties.csv`` (f3 AST/CFG against operator F1, per condition).

Usage: l7_rescore.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import opf1
import r2lib

W = Path("/home/jamiespa/odin3-ws/work")
RENAME = W / "loki-rename-exp"
F3EXP = W / "loki-f3-exp"
MICRO = r2lib.MICRO


def overlay_glob(root: Path, floor: str) -> list[tuple[str, Path]]:
    out = []
    for run in sorted(root.glob(f"*__{floor}")):
        found = sorted(run.glob("**/re/overlay.json"))
        if found:
            out.append((run.name.removesuffix(f"__{floor}"), found[0]))
    return out


def run_sets() -> dict[str, tuple[Path, str, list[tuple[str, Path]]]]:
    """label -> (dataset dir, floor, [(design, overlay path)])."""
    sets: dict[str, tuple[Path, str, list[tuple[str, Path]]]] = {}
    for floor in ("f1-k6", "f1-earch", "f2"):
        for cond in ("calib", "nocalib"):
            root = RENAME / "runs-rebuild" / f"base-{cond}" / "runs"
            sets[f"rename-{floor}-{cond}"] = (MICRO, floor, overlay_glob(root, floor))
    for cond, sub in (("calib", "runs"), ("nocalib", "runs-nocalib")):
        root = F3EXP / sub / "base"
        sets[f"f3exp-f3-{cond}"] = (MICRO, "f3", [
            (p.parent.parent.name.removesuffix("__f3"), p)
            for p in sorted(root.glob("*__f3/re/overlay.json"))])
    for s in ("lut", "native"):
        for cond in ("calib", "none"):
            root = r2lib.DATA / "l1" / "runs" / f"{s}-{cond}"
            floor = "f3" if s == "lut" else "f2"
            sets[f"l1-{s}-{cond}"] = (MICRO, floor, [
                (p.parent.parent.name.removesuffix("__f2"), p)
                for p in sorted(root.glob("*__f2/re/overlay.json"))])
    for floor in ("f2", "f3"):
        for cond in ("calib", "none"):
            root = r2lib.DATA / "l2" / "runs" / f"{floor}-{cond}"
            sets[f"l2-{floor}-{cond}"] = (r2lib.VEVAL, floor, [
                (p.parent.parent.name.removesuffix(f"__{floor}"), p)
                for p in sorted(root.glob(f"*__{floor}/re/overlay.json"))])
    return sets


def score_set(dataset: Path, floor: str, runs: list[tuple[str, Path]]) -> list[dict[str, Any]]:
    rows = []
    for design, path in runs:
        key = opf1.key_ops(opf1.load(dataset / design / floor / "words.json"))
        got = opf1.hyp_ops(opf1.load(path))
        rows.append({"design": design, **opf1.score(key, got)})
    return rows


def fmt(x: object) -> object:
    return round(x, 6) if isinstance(x, float) else ("" if x is None else x)


def mean(vals: list[float]) -> float | None:
    return sum(vals) / len(vals) if vals else None


def f3_ties(sets: dict[str, list[dict[str, Any]]]) -> list[list[object]]:
    """Per f3 test condition: mean AST, mean CFG and operator F1 (pooled)."""
    l0 = opf1.load(F3EXP / "astcfg-l0-l1.json")["designs"]
    nc = opf1.load(F3EXP / "astcfg-nocalib.json")["designs"]
    flat = opf1.load(F3EXP / "astcfg-flat.json")
    by = {r["design"]: r for r in sets["f3exp-f3-nocalib"]}
    byc = {r["design"]: r for r in sets["f3exp-f3-calib"]}

    def col(rows: list[dict[str, Any]], key: str, only: set[str]) -> float | None:
        return mean([float(r[key]) for r in rows if r["design"] in only and key in r])

    ds = {r["design"] for r in l0}
    cfg_ok = {r["design"] for r in l0 if "simcfg_l0" in r}
    out: list[list[object]] = []
    cases = [
        ("L0-stop gate netlist", l0, "simast_l0", "simcfg_l0", []),
        ("L1 calibrated", l0, "simast_l1", "simcfg_l1", list(byc.values())),
        ("L1 uncalibrated", nc, "simast_l1", "simcfg_l1", list(by.values())),
        ("L1 uncalibrated, flattened", flat, "simast_flat", "simcfg_flat", list(by.values())),
    ]
    for label, rows, a, c, ops in cases:
        sel = [r for r in ops if r["design"] in ds]
        pool = opf1.pooled(sel) if sel else {"type_f1": 0.0, "tw_f1": 0.0, "got_n": 0}
        out.append([label, len(ds), col(rows, a, ds), col(rows, c, cfg_ok), pool["got_n"],
                    pool["type_f1"], pool["tw_f1"]])
    return out


def main() -> int:
    sets = {}
    run_rows: list[list[object]] = []
    set_rows: list[list[object]] = []
    for label, (dataset, floor, runs) in run_sets().items():
        if not runs:
            continue
        rows = score_set(dataset, floor, runs)
        sets[label] = rows
        for r in rows:
            run_rows.append([label, r["design"], r["key_n"], r["got_n"], r["type_tp"],
                             fmt(r["type_f1"]), r["tw_tp"], fmt(r["tw_f1"])])
        pool = opf1.pooled(rows)
        mean_tw = mean([float(r["tw_f1"] or 0.0) for r in rows if r["key_n"]])
        set_rows.append([label, pool["designs"], pool["key_n"], pool["got_n"],
                         fmt(pool["type_p"]), fmt(pool["type_r"]), fmt(pool["type_f1"]),
                         fmt(pool["tw_p"]), fmt(pool["tw_r"]), fmt(pool["tw_f1"]), fmt(mean_tw)])
    r2lib.write_csv(r2lib.OUT / "l7_runs.csv",
                    ["set", "design", "key_ops", "got_ops", "type_tp", "type_f1", "tw_tp", "tw_f1"],
                    run_rows)
    r2lib.write_csv(r2lib.OUT / "l7_sets.csv",
                    ["set", "designs", "key_ops", "got_ops", "type_p", "type_r", "type_f1",
                     "tw_p", "tw_r", "tw_f1", "tw_f1_mean_design"], set_rows)
    if "f3exp-f3-calib" in sets and "f3exp-f3-nocalib" in sets:
        ties = f3_ties(sets)
        r2lib.write_csv(r2lib.OUT / "l7_ties.csv",
                        ["condition", "designs", "ast_mean", "cfg_mean", "got_ops", "type_f1",
                         "tw_f1"], [[c[0], c[1], fmt(c[2]), fmt(c[3]), c[4], fmt(c[5]), fmt(c[6])]
                                    for c in ties])
    for row in set_rows:
        print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
