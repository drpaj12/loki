"""Place replies, assemble each (design, arm, draw), score, and write the result tables.

Usage: ``python -B q10_collect.py [--status status.csv] [--run DIR]``. No model call. Per call the
outbox file ``outbox/resp-NNNN.txt`` holds the reply; the code between [BEGIN] and [DONE] must
contain ``module Block_<bid>``. A (design, arm, draw) is assembled when every block has a reply
with that module; else its outcome is ``not_run`` (a missing reply) or ``assembly`` (a reply
without the module). The assembled ``TopModule`` is scored by the pilot's ``score.run_sample``
(VerilogEval testbench; strict ``pass``). Per block: ``q10_check.block_check`` against the block's
own cells. Outputs ``results.csv`` (design level), ``blocks.csv`` (block level), ``key.csv``
(answer-key constructs recovered).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

import q10_build as bd
import q10_check as ck
import q10_env as env
import q10_equiv as equiv
import q10_key as key
import q10_pop as pop
import q10_render as rn

collect: Any = env.mod("collect")
score: Any = env.mod("score")
RES_FIELDS = ["problem", "quartile", "tier", "arm", "draw", "status", "outcome", "pass",
              "mismatches", "samples", "n_blocks", "blocks_replied", "blocks_ok", "key_total",
              "key_right", "key_right_ok"]
BLK_FIELDS = ["problem", "bid", "arm", "draw", "status", "module_found", "check"]


def read_status(path: Path | None) -> dict[int, str]:
    if path is None:
        return {}
    with path.open(encoding="utf-8", newline="") as fh:
        return {int(r["call"]): r["status"] for r in csv.DictReader(fh)}


def code_of(run: Path, call: dict[str, Any], bid: int) -> tuple[str, bool]:
    """(code, found): the extracted code of a call's reply, found = it defines Block_<bid>."""
    f = run / call["outbox_file"]
    if not f.is_file():
        return "", False
    code, ok = collect.extract_rtl(f.read_text(encoding="utf-8", errors="replace"))
    found = ok and re.search(rf"\bmodule\s+Block_{bid}\b",
                             code) is not None
    return code, bool(found)


def index_calls(run: Path) -> dict[tuple[str, int, str, int], dict[str, Any]]:
    idx: dict[tuple[str, int, str, int], dict[str, Any]] = {}
    for ln in (run / "calls.jsonl").read_text(encoding="utf-8").splitlines():
        c = json.loads(ln)
        for a in c["arms"]:
            idx[(c["problem"], c["bid"], a, c["draw"])] = c
    return idx


def score_design(run: Path, d: dict[str, Any], arm: str, draw: int,
                 idx: dict[tuple[str, int, str, int], dict[str, Any]],
                 status: dict[int, str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    p = d["problem"]
    nl = pop.read(p)
    blocks = bd.load_blocks(p)
    ports = rn.block_ports(nl, blocks)
    codes: dict[int, str] = {}
    brows: list[dict[str, Any]] = []
    states = []
    for b, pt in zip(blocks, ports, strict=True):
        call = idx.get((p, b.bid, arm, draw))
        code, found = ("", False)
        has, st = False, "not_run"
        if call is not None:
            code, found = code_of(run, call, b.bid)
            has = (run / call["outbox_file"]).is_file()
            st = status.get(call["call"], "ok") if has else "not_run"
        states.append("ok" if (has and found) else ("not_run" if not has else "assembly"))
        chk = ""
        if has and found:
            codes[b.bid] = code
            chk = ck.block_check(nl, b, pt, code, run / "work" / p / f"chk-{arm}-{draw}-{b.bid}")
        brows.append({"problem": p, "bid": b.bid, "arm": arm, "draw": draw, "status": st,
                      "module_found": int(found), "check": chk})
    row: dict[str, Any] = {"problem": p, "quartile": d["quartile"], "tier": d["tier"],
                           "arm": arm, "draw": draw, "n_blocks": len(blocks),
                           "blocks_replied": len(codes),
                           "blocks_ok": sum(1 for r in brows if r["check"] == "ok"),
                           "status": "ok", "outcome": "", "pass": 0, "mismatches": -1,
                           "samples": 0}
    if len(codes) == len(blocks):
        work = run / "work" / p / f"top-{arm}-{draw}"
        work.mkdir(parents=True, exist_ok=True)
        (work / "sample.sv").write_text(rn.assemble(nl, blocks, ports, codes), encoding="utf-8",
                                        newline="\n")
        if d["tier"] == "ext":
            eq = equiv.design_equiv(pop.netlist_path(p), nl.module, work / "sample.sv",
                                    work / "equiv")
            row.update({"outcome": "pass" if eq == "equiv" else eq, "pass": int(eq == "equiv")})
        else:
            res = score.run_sample(work / "sample.sv", p, work)
            row.update({"outcome": res["outcome"], "pass": int(res["outcome"] == "pass"),
                        "mismatches": res["mismatches"], "samples": res["samples"]})
    else:
        row["status"] = "not_run" if "not_run" in states else "assembly"
        row["outcome"] = row["status"]
    cons = key.key_constructs(nl, p)
    rb = key.right_blocks(nl, blocks, cons)
    okb = {r["bid"] for r in brows if r["check"] == "ok"}
    row.update({"key_total": len(cons), "key_right": sum(1 for x in rb if x),
                "key_right_ok": sum(1 for x in rb if any(b in okb for b in x))})
    return row, brows


def run_all(run: Path, status: dict[int, str], only: set[str] | None = None
            ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    designs = json.loads((env.HERE / "designs.json").read_text(encoding="utf-8"))
    idx = index_calls(run)
    rows: list[dict[str, Any]] = []
    brows: list[dict[str, Any]] = []
    for d in designs:
        if only is not None and d["problem"] not in only:
            continue
        for arm in bd.ARMS:
            for draw in bd.DRAWS:
                if d["n_blocks"] and not any(
                        (d["problem"], b["bid"], arm, draw) in idx for b in d["blocks"]):
                    continue
                if not d["n_blocks"] and arm != "D":
                    continue  # a design without gates has no call: one row per draw, arm D
                r, b = score_design(run, d, arm, draw, idx, status)
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
