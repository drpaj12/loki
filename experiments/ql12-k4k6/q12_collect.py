"""Place replies, assemble each (design, endpoint, arm, draw), score, and write the result tables.

Usage: ``python -B q12_collect.py [--status status.csv] [--run DIR]``. No model call. Per call the
outbox file ``outbox/resp-NNNN.txt`` holds the reply; the code between [BEGIN] and [DONE]. Arm D: it
must contain ``module Block_<bid>``; a (design, draw) is assembled when every block has a reply with
that module, else its outcome is ``not_run`` (a missing reply) or ``assembly`` (a reply without
the module). Arm A: the reply is the design (``TopModule``). The sample is scored by the pilot's
``score.run_sample`` (VerilogEval testbench; strict ``pass``) or, for a processor module, by
sequential equivalence with the netlist. Per block: ``q12_check.block_check``. Outputs
``results.csv`` (design level) and ``blocks.csv`` (block level).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

import q12_build as bd
import q12_check as ck
import q12_env as env
import q12_key as key
import q12_nl as nlm
import q12_render as rn

collect: Any = env.mod("collect")
score: Any = env.mod("score")
q10_pop: Any = env.mod("q10_pop")
RES_FIELDS = ["problem", "endpoint", "tier", "arm", "draw", "status", "outcome", "pass",
              "mismatches", "samples", "n_blocks", "blocks_replied", "blocks_ok", "key_total",
              "key_right", "key_right_ok"]
BLK_FIELDS = ["problem", "endpoint", "bid", "draw", "status", "module_found", "check"]
Idx = dict[tuple[str, str, str, int, int], dict[str, Any]]


def read_status(path: Path | None) -> dict[int, str]:
    if path is None:
        return {}
    with path.open(encoding="utf-8", newline="") as fh:
        return {int(r["call"]): r["status"] for r in csv.DictReader(fh)}


def reply_code(run: Path, call: dict[str, Any]) -> tuple[str, bool, bool]:
    """(code, extracted, has_file) of the reply of a call."""
    f = run / call["outbox_file"]
    if not f.is_file():
        return "", False, False
    code, ok = collect.extract_rtl(f.read_text(encoding="utf-8", errors="replace"))
    return code, bool(ok), True


def index_calls(run: Path) -> Idx:
    idx: Idx = {}
    for ln in (run / "calls.jsonl").read_text(encoding="utf-8").splitlines():
        c = json.loads(ln)
        idx[(c["problem"], c["endpoint"], c["arm"], c["bid"], c["draw"])] = c
    return idx


def score_sample(d: dict[str, Any], nl: nlm.Netlist, gate: Any, sample: Path, work: Path
                 ) -> dict[str, Any]:
    if d["tier"] == "ext":
        eq = ck.design_equiv(nl, gate, sample, work / "equiv")
        return {"outcome": "pass" if eq == "equiv" else eq, "pass": int(eq == "equiv"),
                "mismatches": -1, "samples": 0}
    res = score.run_sample(sample, d["problem"], work)
    return {"outcome": res["outcome"], "pass": int(res["outcome"] == "pass"),
            "mismatches": res["mismatches"], "samples": res["samples"]}


def score_a(run: Path, d: dict[str, Any], draw: int, idx: Idx, status: dict[int, str]
            ) -> dict[str, Any]:
    p, ep = d["problem"], d["endpoint"]
    row: dict[str, Any] = {"problem": p, "endpoint": ep, "tier": d["tier"], "arm": "A",
                           "draw": draw, "n_blocks": d["n_blocks"], "blocks_replied": 0,
                           "blocks_ok": 0, "status": "ok", "outcome": "", "pass": 0,
                           "mismatches": -1, "samples": 0, "key_total": 0, "key_right": 0,
                           "key_right_ok": 0}
    call = idx[(p, ep, "A", -1, draw)]
    code, found, has = reply_code(run, call)
    if not has:
        row.update({"status": "not_run", "outcome": "not_run"})
        return row
    row["status"] = status.get(call["call"], "ok")
    work = run / "work" / ep / p / f"top-A-{draw}"
    work.mkdir(parents=True, exist_ok=True)
    if not found or not re.search(r"\bmodule\s+TopModule\b", code):
        row["outcome"] = "assembly"
        return row
    (work / "sample.sv").write_text(code, encoding="utf-8", newline="\n")
    row.update(score_sample(d, nlm.read(ep, p), q10_pop.read(p), work / "sample.sv", work))
    return row


def score_d(run: Path, d: dict[str, Any], draw: int, idx: Idx, status: dict[int, str]
            ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    p, ep = d["problem"], d["endpoint"]
    nl = nlm.read(ep, p)
    gate = q10_pop.read(p)
    blocks = bd.load_blocks(ep, p)
    ports = rn.block_ports(nl, blocks)
    codes: dict[int, str] = {}
    brows: list[dict[str, Any]] = []
    states = []
    for b, pt in zip(blocks, ports, strict=True):
        call = idx.get((p, ep, "D", b.bid, draw))
        code, found, has = ("", False, False)
        st = "not_run"
        if call is not None:
            code, ok, has = reply_code(run, call)
            found = ok and re.search(rf"\bmodule\s+Block_{b.bid}\b", code) is not None
            st = status.get(call["call"], "ok") if has else "not_run"
        states.append("ok" if (has and found) else ("not_run" if not has else "assembly"))
        chk = ""
        if has and found:
            codes[b.bid] = code
            chk = ck.block_check(nl, b.bid, b.cells, pt, code,
                                 run / "work" / ep / p / f"chk-D-{draw}-{b.bid}")
        brows.append({"problem": p, "endpoint": ep, "bid": b.bid, "draw": draw, "status": st,
                      "module_found": int(found), "check": chk})
    row: dict[str, Any] = {"problem": p, "endpoint": ep, "tier": d["tier"], "arm": "D",
                           "draw": draw, "n_blocks": len(blocks), "blocks_replied": len(codes),
                           "blocks_ok": sum(1 for r in brows if r["check"] == "ok"),
                           "status": "ok", "outcome": "", "pass": 0, "mismatches": -1,
                           "samples": 0}
    if len(codes) == len(blocks):
        work = run / "work" / ep / p / f"top-D-{draw}"
        work.mkdir(parents=True, exist_ok=True)
        (work / "sample.sv").write_text(rn.assemble(nl, gate, blocks, ports, codes),
                                        encoding="utf-8", newline="\n")
        row.update(score_sample(d, nl, gate, work / "sample.sv", work))
    else:
        row["status"] = "not_run" if "not_run" in states else "assembly"
        row["outcome"] = row["status"]
    cons = key.key_constructs(nl, ep, p)
    rb = key.right_blocks(nl, blocks, cons)
    okb = {r["bid"] for r in brows if r["check"] == "ok"}
    row.update({"key_total": len(cons), "key_right": sum(1 for x in rb if x),
                "key_right_ok": sum(1 for x in rb if any(b in okb for b in x))})
    return row, brows


def has_reply(idx: Idx, d: dict[str, Any], arm: str, draw: int) -> bool:
    if arm == "A":
        return (d["problem"], d["endpoint"], "A", -1, draw) in idx
    if not d["n_blocks"]:
        return True  # no call: one fixed-assembly row per draw
    return any((d["problem"], d["endpoint"], "D", b["bid"], draw) in idx for b in d["blocks"])


def run_all(run: Path, status: dict[int, str], only: set[str] | None = None
            ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    designs = json.loads((env.HERE / "designs.json").read_text(encoding="utf-8"))
    idx = index_calls(run)
    rows: list[dict[str, Any]] = []
    brows: list[dict[str, Any]] = []
    for d in designs:
        if only is not None and d["problem"] not in only:
            continue
        draws = (1,) if d["tier"] == "ext" else env.DRAWS
        for draw in draws:
            if d["runs_a"] and has_reply(idx, d, "A", draw):
                rows.append(score_a(run, d, draw, idx, status))
            if has_reply(idx, d, "D", draw):
                r, b = score_d(run, d, draw, idx, status)
                rows.append(r)
                brows += b
    return rows, brows


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fields, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--status", type=Path, default=None)
    ap.add_argument("--run", type=Path, default=env.RUN)
    a = ap.parse_args(argv)
    rows, brows = run_all(a.run, read_status(a.status))
    write_csv(a.run / "results.csv", RES_FIELDS, rows)
    write_csv(a.run / "blocks.csv", BLK_FIELDS, brows)
    outcomes: dict[str, int] = {}
    for r in rows:
        outcomes[r["outcome"]] = outcomes.get(r["outcome"], 0) + 1
    bad = outcomes.get("timeout", 0) + outcomes.get("compile-timeout", 0)
    print(json.dumps({"rows": len(rows), "outcomes": outcomes, "timeouts": bad}, sort_keys=True))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
