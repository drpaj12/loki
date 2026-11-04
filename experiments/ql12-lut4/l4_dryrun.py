"""Dry run (lut4 endpoint) with no model: stub replies go through outbox, assembly, scoring.

Usage: ``python -B l4_dryrun.py`` (a copy of q12_dryrun.py for lut4; after ``l4_run.py blocks`` and
``l4_calls.py``). Works in
``$QL12_OUT/dry`` (blocks, calls and the processor census are linked from the real run). Per design,
endpoint and draw a fixed pattern writes, for every call of arms D and A: the faithful stub RTL
(``pass``; draw 1 is always this), the same with every output of the first block tied low
(``wrong``), a syntax error, a reply without markers, or a module with another name
(``assembly``). Checks: every row with the ``pass`` pattern scores ``pass`` (VerilogEval
testbench, or equivalence for tier ext), every other pattern does not pass with the expected
outcome, 0 timeouts, the block check agrees (ok for stubs, mismatch for wrong), the equivalence
check says ``neq`` on a mutated processor module, and the AST/CFG scorer returns values on two
rows. Writes ``dryrun_result.json``; exit 1 on any mismatch.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REAL = Path(os.environ.get("QL12_OUT", str(HERE.parents[2] / "work" / "ql12l4-out"))).resolve()
DRY = REAL / "dry"
os.environ["QL12_CENSUS"] = str(REAL / "census-ve")
os.environ["QL12_OUT"] = str(DRY)
sys.path.insert(0, str(HERE))

importlib.import_module("l4_env")  # first: sets q12_env for the lut4 endpoint

ck: Any = importlib.import_module("q12_check")  # after the environment is set
co: Any = importlib.import_module("q12_collect")
env: Any = importlib.import_module("q12_env")
nlm: Any = importlib.import_module("q12_nl")
rn: Any = importlib.import_module("q12_render")
ac: Any = importlib.import_module("q12_astcfg")
q10_pop: Any = importlib.import_module("q10_pop")

PATTERNS = ("pass", "wrong", "syntax", "nomark", "assembly")
EXPECT = {"pass": "pass", "wrong": "runtime", "syntax": "compile", "nomark": "not_run",
          "assembly": "assembly"}
# a constants-and-buffers design, a one-block combinational design, two multi-block register
# designs, an FSM, a mux tree, a one-block FSM, a shift register, a processor module
DESIGNS = ("Prob001_zero", "Prob055_conditional", "Prob034_dff8", "Prob045_edgedetect2",
           "Prob121_2014_q3bfsm", "Prob154_fsm_ps2data", "Prob097_mux9to1v",
           "Prob115_shift18", "tinyriscv_clint")


def reply(kind: str, text: str, name: str) -> str:
    if kind == "pass":
        return f"[BEGIN]\n{text}[DONE]\n"
    if kind == "wrong":
        outs = [ln.split()[1].rstrip(";") for ln in text.splitlines()
                if ln.strip().startswith("output")]
        head = text.split(");", 1)[0] + ");\n"
        decl = "".join(ln + "\n" for ln in text.splitlines()
                       if ln.strip().startswith(("input", "output")))
        tied = "\n".join(f"  assign {o} = 1'b0;" for o in outs)
        return f"[BEGIN]\n{head}{decl}{tied}\nendmodule\n[DONE]\n"
    if kind == "syntax":
        return f"[BEGIN]\nmodule {name}(input a; output y)\nassign y = ;\nendmodule\n[DONE]\n"
    if kind == "assembly":
        return "[BEGIN]\n" + text.replace(f"module {name}", "module Other_module") + "[DONE]\n"
    return "I think this is a design.\n"


def write_out(call: dict[str, Any], text: str) -> None:
    out = DRY / call["outbox_file"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")


def a_reply(kind: str, nl: Any, gate: Any) -> str:
    """Arm A reply: the faithful design as one TopModule (a stub block under it)."""
    one = type("One", (), {"bid": 0, "cells": nl.logic()})()
    pt = rn.block_ports(nl, [one])[0]
    stub = rn.stub_module(nl, 0, one.cells, pt)
    if kind == "wrong":
        stub = reply("wrong", stub, "Block_0")[len("[BEGIN]\n"):-len("[DONE]\n")]
    text = str(rn.assemble(nl, gate, [one], [pt], {0: stub}))
    if kind == "assembly":
        return "[BEGIN]\n" + text.replace("module TopModule", "module Other_module") + "[DONE]\n"
    return reply(kind, text, "TopModule")


def mutation_check() -> str:
    """Equivalence of the assembled clint with every LUT row of one cell inverted: ``neq``."""
    ep = "lut4"
    nl = nlm.read(ep, "tinyriscv_clint")
    gate = q10_pop.read("tinyriscv_clint")
    work = DRY / "work" / ep / "tinyriscv_clint"
    sample = (work / "top-D-1" / "sample.sv").read_text(encoding="utf-8")
    bad = work / "mutated"
    bad.mkdir(exist_ok=True)
    (bad / "sample.sv").write_text(sample.replace(" = (", " = ~(", 1), encoding="utf-8",
                                   newline="\n")
    return str(ck.design_equiv(nl, gate, bad / "sample.sv", bad / "eq"))


def main() -> int:
    DRY.mkdir(exist_ok=True)
    for n in ("blocks", "calls", "census"):
        link = DRY / n
        if not link.exists() and (REAL / n).exists():
            link.symlink_to(REAL / n)
    (DRY / "calls.jsonl").write_text((REAL / "calls.jsonl").read_text(encoding="utf-8"),
                                     encoding="utf-8", newline="\n")
    designs = [d for d in json.loads((env.HERE / "designs.json").read_text(encoding="utf-8"))
               if d["problem"] in DESIGNS]
    idx = co.index_calls(DRY)
    expect: dict[tuple[str, str, str, int], str] = {}
    n_written = 0
    for i, d in enumerate(designs):
        p, ep = d["problem"], d["endpoint"]
        nl, gate = nlm.read(ep, p), q10_pop.read(p)
        blocks = co.bd.load_blocks(ep, p)
        ports = rn.block_ports(nl, blocks)
        for draw in (1,) if d["tier"] == "ext" else env.DRAWS:
            kind = "pass" if draw == 1 else PATTERNS[(i + draw) % len(PATTERNS)]
            call = idx.get((p, ep, "A", -1, draw))
            if call is not None:
                expect[(p, ep, "A", draw)] = kind
                write_out(call, a_reply(kind, nl, gate))
                n_written += 1
            if not d["n_blocks"]:
                expect[(p, ep, "D", draw)] = "pass"
                continue
            expect[(p, ep, "D", draw)] = kind
            for k, (b, pt) in enumerate(zip(blocks, ports, strict=True)):
                dcall = idx.get((p, ep, "D", b.bid, draw))
                bad = kind != "pass" and k == 0
                text = rn.stub_module(nl, b.bid, b.cells, pt)
                write_out(dcall, reply(kind if bad else "pass", text, rn.module_name(b.bid)))
                n_written += 1
    rows, brows = co.run_all(DRY, {}, set(DESIGNS))
    co.write_csv(DRY / "results.csv", co.RES_FIELDS, rows)
    co.write_csv(DRY / "blocks.csv", co.BLK_FIELDS, brows)
    wrong = []
    for r in rows:
        kind = expect[(r["problem"], r["endpoint"], r["arm"], r["draw"])]
        if kind == "pass" and r["outcome"] != "pass":
            wrong.append((r["problem"], r["endpoint"], r["arm"], r["draw"], kind, r["outcome"]))
        if kind == "wrong" and r["tier"] == "ext" and r["outcome"] != "neq":
            wrong.append((r["problem"], r["endpoint"], r["arm"], r["draw"], kind, r["outcome"]))
        if kind in ("syntax", "assembly", "nomark") and r["pass"]:
            wrong.append((r["problem"], r["endpoint"], r["arm"], r["draw"], kind, r["outcome"]))
        if kind in ("syntax", "assembly", "nomark") and r["outcome"] not in (
                EXPECT[kind], "compile", "syntax", "assembly", "not_run", "error"):
            wrong.append((r["problem"], r["endpoint"], r["arm"], r["draw"], kind, r["outcome"]))
    mutated = mutation_check()
    if mutated != "neq":
        wrong.append(("tinyriscv_clint", "lut4", "mutation", 0, "neq", mutated))
    timeouts = sum(1 for r in rows if r["outcome"] in ("timeout", "compile-timeout"))
    ok = [b for b in brows if b["check"] == "ok"]
    scored = _astcfg_probe()
    report = {"designs": sorted(DESIGNS), "replies": n_written, "rows": len(rows),
              "pass": sum(r["pass"] for r in rows), "unexpected": wrong, "timeouts": timeouts,
              "blocks_checked_ok": len(ok), "blocks_total": len(brows),
              "astcfg_rows_scored": scored,
              "outcomes": {o: sum(1 for r in rows if r["outcome"] == o)
                           for o in sorted({r["outcome"] for r in rows})}}
    (HERE / "dryrun_result.json").write_text(json.dumps(report, sort_keys=True, indent=1) + "\n",
                                             encoding="utf-8", newline="\n")
    print(json.dumps(report, sort_keys=True))
    return 0 if not wrong and timeouts == 0 and scored >= 2 else 1


def _astcfg_probe() -> int:
    """Run the AST/CFG scorer on the pass rows of two designs; the number of rows with a value."""
    keep = {"Prob055_conditional", "Prob034_dff8"}
    src = DRY / "results.csv"
    full = src.read_text(encoding="utf-8").splitlines()
    sub = [full[0]] + [ln for ln in full[1:] if ln.split(",")[0] in keep and ",1," not in ln[:0]]
    probe = DRY / "probe"
    probe.mkdir(exist_ok=True)
    (probe / "results.csv").write_text("\n".join(sub) + "\n", encoding="utf-8", newline="\n")
    for n in ("work",):
        link = probe / n
        if not link.exists():
            link.symlink_to(DRY / n)
    ac.main(["--run", str(probe)])
    import csv
    with (probe / "astcfg_rows.csv").open(encoding="utf-8", newline="") as fh:
        got = list(csv.DictReader(fh))
    return sum(1 for r in got if r["ast"] != "" and r["cfg"] != "")


if __name__ == "__main__":
    sys.exit(main())
