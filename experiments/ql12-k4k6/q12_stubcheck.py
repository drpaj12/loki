"""Can the netlist pass the testbench at all? A faithful decode of the whole netlist per design.

For every VerilogEval problem of the set and endpoint, the faithful Verilog of the whole LUT
netlist (``q12_render.stub_module`` of all non-glue cells, assembled into a ``TopModule`` of the
interface of the design) is scored with the VerilogEval testbench. A design whose faithful decode
does not pass has a netlist that is not the function of the reference: the BLIF latch has no
asynchronous reset (Prob088, 089, 118), the Odin III build of Prob151 and Prob156 reads a patched
copy of the reference while the testbench runs the original, Odin III reads the ``casez`` of Prob071
as a constant, Prob139 is unexplained. No reply can pass such a design, so it is left out of the
calls at that endpoint. Writes ``results/stubcheck.csv`` (``problem, endpoint, outcome``).
Usage: ``python -B q12_stubcheck.py``. No model call.
"""

from __future__ import annotations

import csv
import sys
from typing import Any

import q12_build as bd
import q12_env as env
import q12_nl as nlm
import q12_render as rn

score: Any = env.mod("score")
q10_pop: Any = env.mod("q10_pop")
OUT = env.RES / "stubcheck.csv"


def faithful(endpoint: str, problem: str) -> str:
    nl, gate = nlm.read(endpoint, problem), q10_pop.read(problem)
    one = type("One", (), {"bid": 0, "cells": nl.logic()})()
    blocks = [one] if one.cells else []
    ports = rn.block_ports(nl, blocks)
    codes = {0: rn.stub_module(nl, 0, one.cells, ports[0])} if blocks else {}
    return str(rn.assemble(nl, gate, blocks, ports, codes))


def main() -> int:
    env.RES.mkdir(parents=True, exist_ok=True)
    rows = []
    for r in bd.problems():
        if r["tier"] == "ext":
            continue
        for ep in env.ENDPOINTS:
            work = env.RUN / "stubcheck" / ep / r["problem"]
            work.mkdir(parents=True, exist_ok=True)
            sample = work / "sample.sv"
            sample.write_text(faithful(ep, r["problem"]), encoding="utf-8", newline="\n")
            res = score.run_sample(sample, r["problem"], work)
            rows.append({"problem": r["problem"], "endpoint": ep, "outcome": res["outcome"]})
            print(rows[-1], flush=True)
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, ["problem", "endpoint", "outcome"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
