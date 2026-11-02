"""Q-L10 analysis: tables, paired tests, verdict rules of EXPERIMENT.md. No model call.

Usage: ``python -B q10_analyze.py [--res results]``. Reads from the results directory the copies
``results.csv``, ``blocks.csv``, ``status.csv``, ``tool-deviations.csv``, the committed
``calls_table.csv`` and ``designs.json``, and arm A of the full run
(``../llm-full/results/results.csv``). Writes ``summary.md`` and csv tables into the results
directory. Deterministic: the bootstrap is seeded (20261102), 2000 resamples. Standard library only.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from math import comb
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SEED = 20261102
RESAMPLES = 2000
MARGIN = 0.05
Row = dict[str, str]
Draws = dict[int, int]
Pairs = dict[str, tuple[Draws, Draws]]


def read_csv(path: Path) -> list[Row]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def p1(d: Draws) -> float:
    return float(mean([float(v) for v in d.values()]))


def p3(d: Draws) -> int:
    return int(any(d.values()))


def maj(d: Draws) -> int:
    return int(sum(d.values()) >= 2)


def boot_ci(diffs: list[float], seed: int = SEED, n: int = RESAMPLES) -> tuple[float, float]:
    """Percentile 95% interval of the mean over problems (resampled with replacement)."""
    if not diffs:
        return float("nan"), float("nan")
    rng = random.Random(seed)
    k = len(diffs)
    ms = sorted(mean([diffs[rng.randrange(k)] for _ in range(k)]) for _ in range(n))
    return ms[int(0.025 * n)], ms[int(0.975 * n) - 1]


def mcnemar(b: int, c: int) -> float:
    """Exact two-sided McNemar p from the discordant counts."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(comb(n, i) for i in range(min(b, c) + 1)) / 2**n
    return float(min(1.0, 2 * tail))


def holm(ps: list[float]) -> list[float]:
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    out = [0.0] * len(ps)
    run = 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        out[i] = run
    return out


def wlt(pairs: Pairs) -> tuple[int, int, int]:
    """Win/loss/tie of first over second on the (problem, draw) pairs both have."""
    w = lo = t = 0
    for a, b in pairs.values():
        for dr in sorted(set(a) & set(b)):
            w += a[dr] > b[dr]
            lo += a[dr] < b[dr]
            t += a[dr] == b[dr]
    return w, lo, t


def wlt_problem(pairs: Pairs) -> tuple[int, int, int]:
    """Win/loss/tie on the per-problem pass@1."""
    d = [p1(a) - p1(b) for a, b in pairs.values()]
    return sum(x > 1e-12 for x in d), sum(x < -1e-12 for x in d), sum(abs(x) <= 1e-12 for x in d)


def compare(pairs: Pairs) -> dict[str, Any]:
    """Headline numbers of a paired comparison, first minus second."""
    diffs = [p1(a) - p1(b) for a, b in pairs.values()]
    lo, hi = boot_ci(diffs)
    ma = [maj(a) for a, _ in pairs.values()]
    mb = [maj(b) for _, b in pairs.values()]
    fo = sum(x > y for x, y in zip(ma, mb, strict=True))
    so = sum(x < y for x, y in zip(ma, mb, strict=True))
    return {"n": len(pairs), "p1_first": mean([p1(a) for a, _ in pairs.values()]),
            "p1_second": mean([p1(b) for _, b in pairs.values()]), "diff": mean(diffs),
            "lo": lo, "hi": hi, "wlt_draw": wlt(pairs), "wlt_problem": wlt_problem(pairs),
            "p3_first": sum(p3(a) for a, _ in pairs.values()),
            "p3_second": sum(p3(b) for _, b in pairs.values()),
            "maj_first": sum(ma), "maj_second": sum(mb), "disc_first": fo, "disc_second": so,
            "p": mcnemar(fo, so)}


def verdict_a(c: dict[str, Any]) -> str:
    """Plan rule (a): non-inferior within 0.05."""
    if c["lo"] > -MARGIN:
        return "SUPPORTED"
    return "CONTRADICTED" if c["hi"] < 0 else "INCONCLUSIVE"


def verdict_c(c: dict[str, Any], p_adj: float) -> str:
    """Plan rule (c): the hint does not help (first = D+h, second = D)."""
    if c["diff"] > 0 and p_adj < 0.05:
        return "USEFUL"
    if c["lo"] >= -MARGIN and c["hi"] <= MARGIN and not (c["diff"] > 0 and p_adj < 0.05):
        return "DISMISSED"
    return "INCONCLUSIVE"


class Data:
    """All inputs, indexed."""

    def __init__(self, res: Path) -> None:
        self.designs = {d["problem"]: d for d in
                        json.loads((HERE / "designs.json").read_text(encoding="utf-8"))}
        self.results = [r for r in read_csv(res / "results.csv")]
        self.blocks = read_csv(res / "blocks.csv")
        self.calls = {int(r["call"]): r for r in read_csv(HERE / "calls_table.csv")}
        self.status = {int(r["call"]): r["status"] for r in read_csv(res / "status.csv")}
        self.dev = {int(r["call"]): r["deviation"] for r in read_csv(res / "tool-deviations.csv")}
        full = HERE.parent / "llm-full" / "results" / "results.csv"
        self.arm_a: dict[str, Draws] = defaultdict(dict)
        for r in read_csv(full):
            if r["arm"] == "A":
                self.arm_a[r["problem"]][int(r["draw"])] = int(r["pass"] in ("1", "True"))
        self.dev_rows = self.deviation_rows()

    def ran(self) -> list[Row]:
        return [r for r in self.results if r["outcome"] != "not_run"]

    def deviation_rows(self) -> set[tuple[str, str, int]]:
        """(problem, arm, draw) result rows that hold a reply of a call with a tool deviation."""
        out: set[tuple[str, str, int]] = set()
        have = {(r["problem"], r["arm"], int(r["draw"])) for r in self.ran()}
        for c in self.dev:
            row = self.calls[c]
            for arm in row["arms"].split("+"):
                key = (row["problem"], arm, int(row["draw"]))
                if key in have:
                    out.add(key)
        return out

    def arm_draws(self, arm: str, problems: list[str], skip: set[tuple[str, str, int]]
                  ) -> dict[str, Draws]:
        out: dict[str, Draws] = {}
        for r in self.ran():
            p, d = r["problem"], int(r["draw"])
            if r["arm"] == arm and p in problems and (p, arm, d) not in skip:
                out.setdefault(p, {})[d] = int(r["pass"])
        return out

    def strata(self) -> dict[str, list[str]]:
        vq = [p for p, d in self.designs.items() if d["tier"] == "vq"]
        ran_vq = {r["problem"] for r in self.ran() if r["tier"] == "vq"}
        gate_free = [p for p in vq if self.designs[p]["n_blocks"] == 0]
        multi = [p for p in vq if self.designs[p]["n_blocks"] >= 2]
        single_run = [p for p in vq if self.designs[p]["n_blocks"] == 1 and p in ran_vq]
        return {"gate-free": gate_free, "multi-block": multi, "single-block (pilot)": single_run,
                "vbig": [p for p, d in self.designs.items() if d["tier"] == "vbig"],
                "ext": [p for p, d in self.designs.items() if d["tier"] == "ext"]}

    def hinted(self, problem: str) -> list[int]:
        return [b["bid"] for b in self.designs[problem]["blocks"]
                if b["sha"]["D"] != b["sha"]["Dh"]]


def pairs_a(data: Data, problems: list[str], skip: set[tuple[str, str, int]]) -> Pairs:
    """Per problem (D draws, A draws) on the draws both have and that are not skipped."""
    d = data.arm_draws("D", problems, skip)
    out: Pairs = {}
    for p in problems:
        if p not in d:
            continue
        keep = {k: v for k, v in d[p].items() if k in data.arm_a.get(p, {})}
        if keep:
            out[p] = (keep, {k: data.arm_a[p][k] for k in keep})
    return out


def pairs_c(data: Data, problems: list[str], skip: set[tuple[str, str, int]]) -> Pairs:
    """Per problem (D+h draws, D draws); a draw dropped when either row is skipped."""
    h = data.arm_draws("Dh", problems, skip)
    d = data.arm_draws("D", problems, skip)
    out: Pairs = {}
    for p in problems:
        if p in h and p in d:
            keep = sorted(set(h[p]) & set(d[p]))
            if keep:
                out[p] = ({k: h[p][k] for k in keep}, {k: d[p][k] for k in keep})
    return out


def fmt(c: dict[str, Any]) -> str:
    w, lo, t = c["wlt_draw"]
    wp, lp, tp = c["wlt_problem"]
    return (f"{c['diff']:+.3f} [{c['lo']:+.3f}, {c['hi']:+.3f}] ; draws W/L/T {w}/{lo}/{t} ; "
            f"problems W/L/T {wp}/{lp}/{tp}")


def part_a(data: Data, skip: set[tuple[str, str, int]]) -> tuple[list[str], list[dict[str, Any]]]:
    st = data.strata()
    sets = {"gate-free": st["gate-free"], "multi-block": st["multi-block"],
            "ran set (gate-free + multi-block)": st["gate-free"] + st["multi-block"],
            "ran set + pilot single-block": st["gate-free"] + st["multi-block"]
            + st["single-block (pilot)"]}
    lines = ["| stratum | designs | A pass@1 | D pass@1 | D minus A [95% CI] / W/L/T | "
             "pass@3 A/D | MAJ A/D | discordant (A only, D only) | p | plan rule (a) |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    rows: list[dict[str, Any]] = []
    for name, probs in sets.items():
        c = compare(pairs_a(data, probs, skip))
        c["name"] = name
        rows.append(c)
    ps = holm([rows[i]["p"] for i in (0, 1, 2)])
    for i, c in enumerate(rows):
        adj = f"{ps[i]:.4f}" if i < 3 else "n/a"
        lines.append(f"| {c['name']} | {c['n']} | {c['p1_second']:.3f} | {c['p1_first']:.3f} | "
                     f"{fmt(c)} | {c['p3_second']}/{c['p3_first']} | {c['maj_second']}/"
                     f"{c['maj_first']} | {c['disc_second']}, {c['disc_first']} | "
                     f"{c['p']:.4f} (Holm {adj}) | {verdict_a(c)} |")
        c["p_holm"] = ps[i] if i < 3 else float("nan")
    return lines, rows


def part_b(data: Data) -> tuple[list[str], list[dict[str, Any]]]:
    st = data.strata()
    lines = ["| design | tier | cells | blocks | D pass (draws) | D+h pass (draws) | "
             "blocks ok / replied (D) | blocks ok / replied (D+h) |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    rows: list[dict[str, Any]] = []
    ok_tot, rep_tot = 0, 0
    any_pass = False
    for tier in ("vbig", "ext"):
        for p in st[tier]:
            cells: dict[str, tuple[int, int, int, int, int]] = {}
            for arm in ("D", "Dh"):
                rs = [r for r in data.ran() if r["problem"] == p and r["arm"] == arm]
                passes = sum(int(r["pass"]) for r in rs)
                bl = [b for b in data.blocks if b["problem"] == p and b["arm"] == arm
                      and b["status"] != "not_run"]
                ok = sum(b["check"] == "ok" for b in bl)
                cells[arm] = (passes, len(rs), ok, len(bl), 0)
                if arm == "D":
                    ok_tot += ok
                    rep_tot += len(bl)
                    any_pass = any_pass or passes > 0
            d, h = cells["D"], cells["Dh"]
            lines.append(f"| {p} | {tier} | {data.designs[p]['n_cells']} | "
                         f"{data.designs[p]['n_blocks']} | {d[0]}/{d[1]} | {h[0]}/{h[1]} | "
                         f"{d[2]}/{d[3]} | {h[2]}/{h[3]} |")
            rows.append({"problem": p, "tier": tier, "cells": data.designs[p]["n_cells"],
                         "blocks": data.designs[p]["n_blocks"], "D_pass": d[0], "D_draws": d[1],
                         "Dh_pass": h[0], "Dh_draws": h[1], "D_blocks_ok": d[2],
                         "D_blocks_replied": d[3], "Dh_blocks_ok": h[2],
                         "Dh_blocks_replied": h[3]})
    share = ok_tot / rep_tot if rep_tot else float("nan")
    if not any_pass or share < 0.5:
        v = "CONTRADICTED"
    elif share >= 0.8:
        v = "SUPPORTED"
    else:
        v = "INCONCLUSIVE"
    lines.append("")
    lines.append(f"Arm D block check: {ok_tot} of {rep_tot} block replies `ok` "
                 f"(share {share:.3f}); at least one design "
                 f"passes in at least one draw: {any_pass}. Plan rule (b): {v}.")
    rows.append({"problem": "TOTAL", "tier": "vbig+ext", "D_blocks_ok": ok_tot,
                 "D_blocks_replied": rep_tot, "verdict": v})
    return lines, rows


def part_c(data: Data, skip: set[tuple[str, str, int]]) -> tuple[list[str], list[dict[str, Any]]]:
    st = data.strata()
    with_hint = {n: [p for p in st[n] if data.hinted(p)] for n in
                 ("multi-block", "single-block (pilot)", "vbig", "ext")}
    lines = ["| set | designs | D pass@1 | D+h pass@1 | D+h minus D [95% CI] / W/L/T | "
             "pass@3 D/D+h | MAJ D/D+h | discordant (D+h only, D only) | p | plan rule (c) |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    rows: list[dict[str, Any]] = []
    three = with_hint["multi-block"] + with_hint["vbig"]
    sets = {"multi-block + vbig, designs with a hint": three,
            "multi-block, designs with a hint": with_hint["multi-block"],
            "vbig, designs with a hint": with_hint["vbig"],
            "ext, designs with a hint (1 draw)": with_hint["ext"],
            "all multi-block + vbig + ext designs (hint or not)":
                st["multi-block"] + st["vbig"] + st["ext"]}
    for name, probs in sets.items():
        c = compare(pairs_c(data, probs, skip))
        c["name"] = name
        rows.append(c)
    p_adj = rows[0]["p"]  # family of one confirmatory test
    for i, c in enumerate(rows):
        v = verdict_c(c, p_adj if i == 0 else c["p"]) if i == 0 else "descriptive"
        lines.append(f"| {c['name']} | {c['n']} | {c['p1_second']:.3f} | {c['p1_first']:.3f} | "
                     f"{fmt(c)} | {c['p3_second']}/{c['p3_first']} | {c['maj_second']}/"
                     f"{c['maj_first']} | {c['disc_first']}, {c['disc_second']} | "
                     f"{c['p']:.4f} | {v} |")
        c["verdict"] = v
    return lines, rows


def hint_blocks(data: Data) -> tuple[list[str], list[dict[str, Any]]]:
    """Block level: check ok on the blocks that carry a hint in D+h, D+h against D."""
    cnt: dict[str, list[int]] = {"D": [0, 0], "Dh": [0, 0]}
    per: dict[tuple[str, int, int], dict[str, str]] = {}
    for b in data.blocks:
        if b["status"] == "not_run":
            continue
        p = b["problem"]
        if int(b["bid"]) in data.hinted(p):
            per.setdefault((p, int(b["bid"]), int(b["draw"])), {})[b["arm"]] = b["check"]
    better = worse = 0
    for v in per.values():
        if "D" in v and "Dh" in v:
            for arm in ("D", "Dh"):
                cnt[arm][0] += v[arm] == "ok"
                cnt[arm][1] += 1
            better += v["Dh"] == "ok" and v["D"] != "ok"
            worse += v["D"] == "ok" and v["Dh"] != "ok"
    lines = [f"Hinted blocks with both replies (block, draw): {cnt['D'][1]}. Check `ok`: D "
             f"{cnt['D'][0]} ({cnt['D'][0] / max(1, cnt['D'][1]):.3f}), D+h {cnt['Dh'][0]} "
             f"({cnt['Dh'][0] / max(1, cnt['Dh'][1]):.3f}); D+h ok and D not: {better}, D ok and "
             f"D+h not: {worse}."]
    return lines, [{"arm": a, "ok": v[0], "n": v[1]} for a, v in cnt.items()]


def key_table(data: Data) -> tuple[list[str], list[dict[str, Any]]]:
    st = data.strata()
    lines = ["| tier | arm | rows | designs with a key | key constructs (summed over rows) | "
             "right block (structure) | right block and decoded `ok` |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    rows: list[dict[str, Any]] = []
    sets = {"multi-block": st["multi-block"], "single-block (pilot)": st["single-block (pilot)"],
            "vbig": st["vbig"], "ext": st["ext"]}
    for name, probs in sets.items():
        for arm in ("D", "Dh"):
            rs = [r for r in data.ran() if r["problem"] in probs and r["arm"] == arm]
            kt = sum(int(r["key_total"]) for r in rs)
            kr = sum(int(r["key_right"]) for r in rs)
            ko = sum(int(r["key_right_ok"]) for r in rs)
            nd = len({r["problem"] for r in rs if int(r["key_total"])})
            lines.append(f"| {name} | {arm} | {len(rs)} | {nd} | {kt} | {kr} | {ko} |")
            rows.append({"tier": name, "arm": arm, "rows": len(rs), "designs_with_key": nd,
                         "key_total": kt, "key_right": kr, "key_right_ok": ko})
    return lines, rows


def tokens(data: Data) -> tuple[list[str], list[dict[str, Any]]]:
    """Estimated tokens (calls_table.csv) of the calls that were run, per arm."""
    done = {c for c, s in data.status.items() if s == "ok"}
    acc: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    rows: list[dict[str, Any]] = []
    for c in sorted(done):
        r = data.calls[c]
        for arm in r["arms"].split("+"):
            a = acc[r["problem"] + "|" + arm]
            a["calls"] += 1
            a["tin"] += int(r["est_tokens_in"])
            a["tout"] += int(r["est_tokens_out"])
    tier_arm: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
    for k, a in sorted(acc.items()):
        p, arm = k.split("|")
        t = data.designs[p]["tier"] + ("-multi" if data.designs[p]["n_blocks"] > 1 else "")
        rows.append({"problem": p, "arm": arm, "calls": int(a["calls"]),
                     "est_tokens_in": int(a["tin"]), "est_tokens_out": int(a["tout"])})
        x = tier_arm[(t, arm)]
        x[0] += 1
        x[1] += a["calls"]
        x[2] += a["tin"]
        x[3] += a["tout"]
    lines = ["| tier | arm | designs | calls (summed over draws) | est. tokens in+out per design "
             "(all draws) | est. tokens in+out per call |", "| --- | --- | --- | --- | --- | --- |"]
    for (t, arm), x in sorted(tier_arm.items()):
        lines.append(f"| {t} | {arm} | {int(x[0])} | {int(x[1])} | {(x[2] + x[3]) / x[0]:,.0f} | "
                     f"{(x[2] + x[3]) / x[1]:,.0f} |")
    uni_in = sum(int(data.calls[c]["est_tokens_in"]) for c in done)
    uni_out = sum(int(data.calls[c]["est_tokens_out"]) for c in done)
    lines.append("")
    lines.append(f"Unique calls run: {len(done)}; estimated tokens in {uni_in:,}, out "
                 f"{uni_out:,}, total {uni_in + uni_out:,} (a call shared by D and D+h is counted "
                 f"once here and once in each arm above; harness overhead of each subagent is not "
                 f"included).")
    return lines, rows


EPS = 1e-9
Vals = dict[tuple[str, str, str, str], dict[int, float]]


def load_astcfg(res: Path) -> tuple[Vals, list[Row]]:
    """(problem, arm, variant, metric) -> {draw: value}; absent values are left out."""
    path = res / "astcfg_rows.csv"
    rows = read_csv(path) if path.is_file() else []
    vals: Vals = defaultdict(dict)
    for r in rows:
        for m in ("ast", "cfg"):
            if r[m] != "":
                vals[(r["problem"], r["arm"], r["variant"], m)][int(r["draw"])] = float(r[m])
    return vals, rows


def cell_pairs(vals: Vals, first: tuple[str, str], second: tuple[str, str], metric: str,
               problems: list[str]) -> dict[str, tuple[dict[int, float], dict[int, float]]]:
    out: dict[str, tuple[dict[int, float], dict[int, float]]] = {}
    for p in problems:
        a = vals.get((p, first[0], first[1], metric), {})
        b = vals.get((p, second[0], second[1], metric), {})
        keep = sorted(set(a) & set(b))
        if keep:
            out[p] = ({k: a[k] for k in keep}, {k: b[k] for k in keep})
    return out


def compare_cont(pairs: dict[str, tuple[dict[int, float], dict[int, float]]]) -> dict[str, Any]:
    diffs = [mean(list(a.values())) - mean(list(b.values())) for a, b in pairs.values()]
    lo, hi = boot_ci(diffs)
    w = lz = t = 0
    for a, b in pairs.values():
        for k in a:
            d = a[k] - b[k]
            w += d > EPS
            lz += d < -EPS
            t += abs(d) <= EPS
    wp = sum(x > EPS for x in diffs)
    lp = sum(x < -EPS for x in diffs)
    return {"n": len(pairs), "first": mean([mean(list(a.values())) for a, _ in pairs.values()]),
            "second": mean([mean(list(b.values())) for _, b in pairs.values()]),
            "diff": mean(diffs), "lo": lo, "hi": hi, "wlt_draw": (w, lz, t),
            "wlt_problem": (wp, lp, len(diffs) - wp - lp)}


def mean_ci(vals: Vals, cell: tuple[str, str], metric: str, problems: list[str]
            ) -> tuple[int, int, float, float, float]:
    """(problems with a value, scored draws, mean over problems, CI low, CI high)."""
    per = [mean(list(vals[(p, cell[0], cell[1], metric)].values())) for p in problems
           if (p, cell[0], cell[1], metric) in vals]
    nd = sum(len(vals[(p, cell[0], cell[1], metric)]) for p in problems
             if (p, cell[0], cell[1], metric) in vals)
    lo, hi = boot_ci(per)
    return len(per), nd, mean(per), lo, hi


def astcfg_section(data: Data, res: Path) -> tuple[list[str], list[dict[str, Any]]]:
    vals, rows = load_astcfg(res)
    if not rows:
        return ["(no astcfg_rows.csv)"], []
    st = data.strata()
    multi, gf = st["multi-block"], st["gate-free"]
    cells = [("A", "raw"), ("A", "flat"), ("D", "asm"), ("D", "flat"), ("Dh", "asm"),
             ("Dh", "flat")]
    out: list[dict[str, Any]] = []
    lines = ["Mean similarity to the VerilogEval reference, per problem then over problems "
             "(bootstrap 95% CI over problems); n = problems with a value, draws = scored draws.",
             "", "| set | cell | AST n / draws | AST mean [CI] | CFG n / draws | CFG mean [CI] |",
             "| --- | --- | --- | --- | --- | --- |"]
    sets = {"multi-block": multi, "gate-free": gf, "vbig": st["vbig"]}
    for sn, probs in sets.items():
        for cell in cells:
            a = mean_ci(vals, cell, "ast", probs)
            k = mean_ci(vals, cell, "cfg", probs)
            if a[0] == 0 and k[0] == 0:
                continue
            lines.append(f"| {sn} | {cell[0]}-{cell[1]} | {a[0]} / {a[1]} | {a[2]:.3f} "
                         f"[{a[3]:.3f}, {a[4]:.3f}] | {k[0]} / {k[1]} | {k[2]:.3f} "
                         f"[{k[3]:.3f}, {k[4]:.3f}] |")
            out.append({"set": sn, "cell": f"{cell[0]}-{cell[1]}", "ast_n": a[0],
                        "ast_draws": a[1], "ast_mean": a[2], "ast_lo": a[3], "ast_hi": a[4],
                        "cfg_n": k[0], "cfg_draws": k[1], "cfg_mean": k[2], "cfg_lo": k[3],
                        "cfg_hi": k[4]})
    comps = [("D-flat minus A-raw (headline)", ("D", "flat"), ("A", "raw")),
             ("D-asm minus A-raw", ("D", "asm"), ("A", "raw")),
             ("D-flat minus A-flat (same writer)", ("D", "flat"), ("A", "flat")),
             ("D+h-flat minus D-flat", ("Dh", "flat"), ("D", "flat"))]
    lines += ["", "Paired differences (same problem and draw; first minus second):", "",
              "| comparison | set | metric | problems | diff [95% CI] | draws W/L/T | "
              "problems W/L/T |", "| --- | --- | --- | --- | --- | --- | --- |"]
    qsets = {"multi-block": multi, "ran set (gate-free + multi-block)": gf + multi}
    for name, f, s in comps:
        for sn, probs in qsets.items():
            for m in ("ast", "cfg"):
                c = compare_cont(cell_pairs(vals, f, s, m, probs))
                if not c["n"]:
                    continue
                lines.append(f"| {name} | {sn} | {m.upper()} | {c['n']} | {c['diff']:+.3f} "
                             f"[{c['lo']:+.3f}, {c['hi']:+.3f}] | "
                             f"{'/'.join(map(str, c['wlt_draw']))} | "
                             f"{'/'.join(map(str, c['wlt_problem']))} |")
                out.append({"comparison": name, "set": sn, "metric": m, **c})
    lines += ["", "Per quartile, D-flat minus A-raw (multi-block + gate-free):", "",
              "| quartile | metric | problems | A mean | D-flat mean | diff [95% CI] |",
              "| --- | --- | --- | --- | --- | --- |"]
    for q in ("Q1", "Q2", "Q3", "Q4"):
        probs = [p for p in gf + multi if data.designs[p]["quartile"] == q]
        for m in ("ast", "cfg"):
            c = compare_cont(cell_pairs(vals, ("D", "flat"), ("A", "raw"), m, probs))
            if c["n"]:
                lines.append(f"| {q} | {m.upper()} | {c['n']} | {c['second']:.3f} | "
                             f"{c['first']:.3f} | {c['diff']:+.3f} [{c['lo']:+.3f}, "
                             f"{c['hi']:+.3f}] |")
                out.append({"comparison": "quartile " + q, "metric": m, **c})
    errs: dict[str, int] = defaultdict(int)
    for r in rows:
        for fld in ("ast_err", "cfg_err"):
            if r[fld]:
                errs[f"{r['arm']}-{r['variant']} {fld[:3]}: {r[fld][:48]}"] += 1
    lines += ["", "Rows without a value (reason, count):", ""]
    lines += [f"- {k}: {v}" for k, v in sorted(errs.items())]
    return lines, out


def coverage(data: Data) -> list[str]:
    st = data.strata()
    ran = data.ran()
    lines = ["| stratum | designs | D rows run | D+h rows run |", "| --- | --- | --- | --- |"]
    for name, probs in st.items():
        d = sum(1 for r in ran if r["problem"] in probs and r["arm"] == "D")
        h = sum(1 for r in ran if r["problem"] in probs and r["arm"] == "Dh")
        lines.append(f"| {name} | {len(probs)} | {d} | {h} |")
    out: dict[str, int] = defaultdict(int)
    for r in data.results:
        out[r["outcome"]] += 1
    lines.append("")
    lines.append(f"Result rows {len(data.results)}: " + ", ".join(
        f"{k} {v}" for k, v in sorted(out.items())) + ".")
    lines.append(f"Calls with a reply: {sum(1 for s in data.status.values() if s == 'ok')}; "
                 f"tool deviations: {len(data.dev)} calls touching {len(data.dev_rows)} "
                 f"result rows "
                 f"(D {sum(1 for k in data.dev_rows if k[1] == 'D')}, D+h "
                 f"{sum(1 for k in data.dev_rows if k[1] == 'Dh')}) of "
                 f"{len({k[0] for k in data.dev_rows})} problems.")
    return lines


def per_design(data: Data) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    st = data.strata()
    tier_of = {p: n for n, ps in st.items() for p in ps}
    for p in sorted(tier_of):
        for arm in ("A", "D", "Dh"):
            d = data.arm_a.get(p, {}) if arm == "A" else data.arm_draws(arm, [p], set()).get(p, {})
            if arm == "A" and tier_of[p] in ("vbig", "ext"):
                continue
            if d:
                out.append({"problem": p, "stratum": tier_of[p], "arm": arm,
                            "draws": len(d), "passes": sum(d.values())})
    return out


def run(res: Path) -> str:
    data = Data(res)
    skip = data.dev_rows
    parts: list[str] = ["# Q-L10 results (generated by q10_analyze.py; no model call)", "",
                        "Seeded bootstrap (seed 20261102, 2000 resamples, problems resampled). "
                        "First named arm minus second. Strict pass of the pilot scorer; `ext` is "
                        "sequential equivalence (`dsec`).", "", "## Coverage", ""]
    parts += coverage(data)
    la, ra = part_a(data, set())
    lb, rb = part_b(data)
    lc, rc = part_c(data, set())
    parts += ["", "## (a) D against A (arm A: full run, same problems and draws)", ""] + la
    la2, ra2 = part_a(data, skip)
    parts += ["", "Sensitivity, the result rows with a tool deviation removed (both arms of a "
              "paired draw dropped):", ""] + la2
    parts += ["", "## (b) D where arm A cannot run (vbig, ext)", ""] + lb
    parts += ["", "## (c) D+h against D", ""] + lc
    lc2, rc2 = part_c(data, skip)
    parts += ["", "Sensitivity, deviation rows removed:", ""] + lc2
    lh, rh = hint_blocks(data)
    parts += ["", "Block level:", ""] + lh
    lk, rk = key_table(data)
    parts += ["", "## Provenance answer key (measurement, no verdict)", "",
              "A key construct is counted once per result row (design x draw), so a design with "
              "3 draws counts its constructs 3 times; the share is unaffected.", ""] + lk
    lx, rx = astcfg_section(data, res)
    parts += ["", "## AST and CFG similarity (Gate-Breaker's second measure)", ""] + lx
    lt, rt = tokens(data)
    parts += ["", "## Tokens (estimates from calls_table.csv, not measured)", ""] + lt
    flat = []
    for tag, rows in (("a", ra), ("a_sens", ra2), ("c", rc), ("c_sens", rc2)):
        for r in rows:
            flat.append({"part": tag, "name": r.get("name", ""), "n": r.get("n", ""),
                         "first": r.get("p1_first", ""), "second": r.get("p1_second", ""),
                         "diff": r.get("diff", ""), "lo": r.get("lo", ""), "hi": r.get("hi", ""),
                         "wlt_draw": "/".join(map(str, r.get("wlt_draw", ()))),
                         "wlt_problem": "/".join(map(str, r.get("wlt_problem", ()))),
                         "p": r.get("p", "")})
    write_csv(res / "tests.csv", ["part", "name", "n", "first", "second", "diff", "lo", "hi",
                                  "wlt_draw", "wlt_problem", "p"], flat)
    write_csv(res / "part_b.csv", list(rb[0].keys()) + ["verdict"], [
        {**{k: "" for k in rb[0]}, **r} for r in rb])
    if rx:
        keys = sorted({k for r in rx for k in r})
        write_csv(res / "astcfg_summary.csv", keys, [{k: r.get(k, "") for k in keys} for r in rx])
    write_csv(res / "key_recovery.csv", list(rk[0].keys()), rk)
    write_csv(res / "tokens_estimate.csv", list(rt[0].keys()), rt)
    write_csv(res / "per_design.csv", ["problem", "stratum", "arm", "draws", "passes"],
              per_design(data))
    text = "\n".join(parts) + "\n"
    (res / "summary.md").write_text(text, encoding="utf-8", newline="\n")
    return text


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--res", type=Path, default=HERE / "results")
    a = ap.parse_args(argv)
    sys.stdout.write(run(a.res))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
