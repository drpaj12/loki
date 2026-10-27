"""Aggregate scored records into tables (pass rates, paired A/B, outcomes, label agreement).

Usage: ``python -I summarize.py --records DIR [--hints DIR] [--status FILE] [--out FILE]``.
Reads each
``<arm>/<problem>/result.json`` under DIR; quartiles and ground truth come from selection.csv and
experiments/veval-l0/features.csv. Rates are shown with counts; n is small. Label agreement is
defined on arm B only and is not a recovery measure.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
common = importlib.import_module("common")
score = importlib.import_module("score")

_ASSIGN = re.compile(r"\b([A-Za-z_]\w*)(?:\[[^\]]*\])?\s*<=")
_CLOCKED = re.compile(
    r"always(?:_ff)?\s*@\s*\(\s*(?:pos|neg)edge[^)]*\)(.*?)(?=\balways|\bendmodule)", re.S)


def read_csv(path: Path, key: str) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return {r[key]: r for r in csv.DictReader(fh)}


def load_results(records: Path) -> dict[tuple[str, str], dict[str, Any]]:
    out = {}
    for f in sorted(records.glob("*/*/result.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        out[(r["arm"], r["problem"])] = r
    return out


def rate(passed: int, total: int) -> str:
    return f"{passed}/{total}" + (f" ({passed / total:.2f})" if total else "")


def pass_table(res: dict[tuple[str, str], dict[str, Any]], quart: dict[str, str],
               arms: list[str], key: str = "pass") -> list[str]:
    lines = ["| quartile | " + " | ".join(f"arm {a}" for a in arms) + " |",
             "| --- | " + " | ".join("---" for _ in arms) + " |"]
    for q in [*common.QUARTILES, "all"]:
        cells = []
        for a in arms:
            rows = [r for (arm, p), r in res.items() if arm == a and q in ("all", quart[p])]
            cells.append(rate(sum(bool(r.get(key)) for r in rows), len(rows)))
        lines.append(f"| {q} | " + " | ".join(cells) + " |")
    return lines


def paired(res: dict[tuple[str, str], dict[str, Any]]) -> list[str]:
    both = sorted({p for (a, p) in res if a == "A"} & {p for (a, p) in res if a == "B"})
    ab = sum(res[("A", p)]["pass"] and res[("B", p)]["pass"] for p in both)
    ao = sum(res[("A", p)]["pass"] and not res[("B", p)]["pass"] for p in both)
    bo = sum(not res[("A", p)]["pass"] and res[("B", p)]["pass"] for p in both)
    no = len(both) - ab - ao - bo
    return ["| both pass | A only | B only | neither | problems |",
            "| --- | --- | --- | --- | --- |",
            f"| {ab} | {ao} | {bo} | {no} | {len(both)} |",
            f"B minus A = {bo - ao} problems (discordant pairs {ao + bo})."]


def outcome_table(res: dict[tuple[str, str], dict[str, Any]], arms: list[str]) -> list[str]:
    lines = ["| outcome | " + " | ".join(f"arm {a}" for a in arms) + " |",
             "| --- | " + " | ".join("---" for _ in arms) + " |"]
    for o in score.OUTCOMES:
        counts = [sum(1 for (a, _), r in res.items() if a == arm and r["outcome"] == o)
                  for arm in arms]
        lines.append(f"| {o} | " + " | ".join(str(c) for c in counts) + " |")
    return lines


def clocked_regs(rtl: str) -> set[str]:
    return {n for body in _CLOCKED.findall(rtl) for n in _ASSIGN.findall(body)}


def fsm_uptake(rtl: str) -> bool:
    """Exploratory: a clocked register that also steers a case, comparison or ?: in the RTL."""
    for name in clocked_regs(rtl):
        n = re.escape(name)
        if re.search(rf"\bcase[xz]?\s*\(\s*{n}\b|\b{n}\s*(?:==|!=)|\b{n}\s*\?", rtl):
            return True
    return False


def bus_uptake(rtl: str, width: int) -> bool:
    return any(int(m) == width - 1 for m in re.findall(r"\[\s*(\d+)\s*:\s*0\s*\]", rtl))


def hint_facts(translated: dict[str, Any]) -> dict[str, Any]:
    els = translated["elements"]
    roles = [e["role"] for e in els if e["role"]]
    return {"fsm": bool(translated["fsms"]),
            "bus_width": max((b["width"] for b in translated["buses"]), default=0),
            "claims": len(els), "datapath": sum(r == "datapath" for r in roles),
            "roles": len(roles)}


def label_section(res: dict[tuple[str, str], dict[str, Any]], records: Path, hints: Path,
                  gt: dict[str, dict[str, str]], sel: dict[str, dict[str, str]]) -> list[str]:
    rows = []
    for (arm, p), r in sorted(res.items()):
        t = hints / p / "out" / "translated.json"
        if arm != "B" or not t.exists():
            continue
        h = hint_facts(json.loads(t.read_text(encoding="utf-8")))
        feat = gt.get(f"ve_{p}")
        fsm_gt = None if feat is None else feat["fsm"] == "1"
        bus_gt = None if feat is None else feat["buses_wide"] == "1"
        rtl = (records / "B" / p / "sample.sv").read_text(encoding="utf-8")
        rows.append({"p": p, "pass": r["pass"], "h": h, "fsm_ok": None if fsm_gt is None
                     else h["fsm"] == fsm_gt, "bus_ok": None if bus_gt is None
                     else (h["bus_width"] > 0) == bus_gt,
                     "fsm_up": fsm_uptake(rtl) if h["fsm"] else None,
                     "bus_up": bus_uptake(rtl, h["bus_width"]) if h["bus_width"] else None})
    if not rows:
        return ["(no arm B records)"]
    def count(f: Any) -> int:
        return sum(1 for x in rows if f(x))
    wrong = [x for x in rows if x["fsm_ok"] is False or x["bus_ok"] is False]
    right = [x for x in rows if x["fsm_ok"] is not False and x["bus_ok"] is not False]
    claims = sum(x["h"]["claims"] for x in rows)
    return [
        f"- arm B problems with hints read: {len(rows)}",
        f"- FSM candidate present: {count(lambda x: x['h']['fsm'])}; of those the L0 ground truth "
        f"says FSM: {count(lambda x: x['h']['fsm'] and x['fsm_ok'])}; FSM hint wrong or absent "
        f"against ground truth: {count(lambda x: x['fsm_ok'] is False)}",
        f"- bus candidate present: {count(lambda x: x['h']['bus_width'] > 0)}; hint agrees with "
        f"`buses_wide`: {count(lambda x: x['bus_ok'])} of "
        f"{count(lambda x: x['bus_ok'] is not None)}",
        f"- claims labelled datapath: {sum(x['h']['datapath'] for x in rows)} of "
        f"{sum(x['h']['roles'] for x in rows)} role-labelled ({claims} kept claims)",
        f"- uptake (exploratory regex): FSM hint with state register steering logic in the RTL "
        f"{count(lambda x: x['fsm_up'])} of {count(lambda x: x['fsm_up'] is not None)}; bus hint "
        f"with a vector of the hinted width {count(lambda x: x['bus_up'])} of "
        f"{count(lambda x: x['bus_up'] is not None)}",
        f"- right for the wrong reason: B passes with a wrong FSM or bus hint "
        f"{sum(1 for x in wrong if x['pass'])}; B failures with right hints "
        f"{sum(1 for x in right if not x['pass'])}",
    ]


def status_section(status: Path, res: dict[tuple[str, str], dict[str, Any]]) -> list[str]:
    """Refusal-aware pass rates from ``status.csv`` (ok / refused / not_run per call).

    View 1: refused counts as a fail (denominator = ok + refused, calls actually made).
    View 2: the paired set, problems answered (ok) in all three arms.
    """
    with status.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    st = {(r["arm"], r["problem"]): r for r in rows}
    arms = [a for a in common.ARMS if any(r["arm"] == a for r in rows)]
    probs = sorted({r["problem"] for r in rows})
    def ok(a: str, p: str) -> bool:
        return st[(a, p)]["status"] == "ok"
    paired_set = [p for p in probs if all(ok(a, p) for a in arms)]
    out = ["| arm | ok | refused | not run | pass | refused = fail | answered only | "
           "paired set |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for a in arms:
        n = {k: sum(1 for r in rows if r["arm"] == a and r["status"] == k)
             for k in ("ok", "refused", "not_run")}
        passed = sum(bool(res[(a, p)]["pass"]) for p in probs if ok(a, p) and (a, p) in res)
        pp = sum(bool(res[(a, p)]["pass"]) for p in paired_set)
        out.append(f"| {a} | {n['ok']} | {n['refused']} | {n['not_run']} | {passed} | "
                   f"{rate(passed, n['ok'] + n['refused'])} | {rate(passed, n['ok'])} | "
                   f"{rate(pp, len(paired_set))} |")
    multi = [f"{r['order']} {r['arm']} {r['problem']} ({r['tool_calls']} tool calls)"
             for r in rows if r["status"] == "ok" and r["tool_calls"] not in ("", "2")]
    out += ["", f"Paired set: {len(paired_set)} problems answered in all of {''.join(arms)}.",
            "Ok calls with tool-call count other than 2: " + ("; ".join(multi) or "none") + "."]
    return out


def summarize(records: Path, hints: Path, status: Path | None = None) -> str:
    res = load_results(records)
    sel = read_csv(common.HERE / "selection.csv", "problem")
    quart = {p: r["quartile"] for p, r in sel.items()}
    gt = read_csv(common.REPO / "experiments" / "veval-l0" / "features.csv", "design")
    arms = [a for a in common.ARMS if any(k[0] == a for k in res)]
    out = ["# Pilot tables", "", "## Pass rate by quartile and arm", "",
           *pass_table(res, quart, arms),
           "", "## Pass rate, Gate-Breaker-equivalent scorer", "",
           *pass_table(res, quart, arms, "gb_pass")]
    if "A" in arms and "B" in arms:
        out += ["", "## Paired A/B", "", *paired(res)]
    out += ["", "## Outcome codes", "", *outcome_table(res, arms)]
    if status is not None and status.exists():
        out += ["", "## Pass rate with refusals and paired set", "", *status_section(status, res)]
    out += ["", "## Loki-label agreement (arm B, counts)", "",
            *label_section(res, records, hints, gt, sel)]
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--records", type=Path, required=True)
    ap.add_argument("--hints", type=Path, default=common.hints_root() / "hints")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--status", type=Path, help="status.csv from archive_run.py")
    a = ap.parse_args(argv)
    text = summarize(a.records, a.hints, a.status)
    if a.out:
        a.out.write_text(text, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
