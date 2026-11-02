"""Diagnostic for the ``ext`` designs (no model call): why is a design not equivalent?

For each ext (design, arm) the assembled design is rebuilt with every block whose reply failed
the block check (``mismatch``, ``compile``) replaced by the faithful stub of its own cells, and
the sequential equivalence is run again. ``equiv`` after the replacement means the failed blocks
are the whole cause; ``neq`` means something else also differs (assembly, check method).
Usage: ``python -B q10_extdiag.py [--run DIR]``; writes ``results/ext_diagnostic.csv``.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import q10_build as bd
import q10_check as ck
import q10_collect as co
import q10_env as env
import q10_equiv as equiv
import q10_pop as pop
import q10_render as rn


def main(argv: list[str]) -> int:
    run = Path(argv[0]) if argv else env.RUN
    idx = co.index_calls(run)
    res = list(csv.DictReader((run / "results.csv").open(encoding="utf-8")))
    blk = list(csv.DictReader((run / "blocks.csv").open(encoding="utf-8")))
    out: list[dict[str, object]] = []
    for r in res:
        if r["tier"] != "ext" or r["outcome"] == "not_run":
            continue
        p, arm, draw = r["problem"], r["arm"], int(r["draw"])
        nl = pop.read(p)
        blocks = bd.load_blocks(p)
        ports = rn.block_ports(nl, blocks)
        chk = {int(b["bid"]): b["check"] for b in blk if b["problem"] == p and b["arm"] == arm
               and int(b["draw"]) == draw}
        codes: dict[int, str] = {}
        bad = []
        for b, pt in zip(blocks, ports, strict=True):
            code, _found = co.code_of(run, idx[(p, b.bid, arm, draw)], b.bid)
            if chk[b.bid] != "ok":
                bad.append(b.bid)
                code = ck.stub_decode(nl, b, pt)
            codes[b.bid] = code
        work = run / "work" / p / f"diag-{arm}-{draw}"
        work.mkdir(parents=True, exist_ok=True)
        (work / "sample.sv").write_text(rn.assemble(nl, blocks, ports, codes), encoding="utf-8",
                                        newline="\n")
        eq = equiv.design_equiv(pop.netlist_path(p), nl.module, work / "sample.sv", work / "eq")
        out.append({"problem": p, "arm": arm, "original": r["outcome"],
                    "failed_blocks": " ".join(map(str, bad)), "n_failed": len(bad),
                    "after_replacing_failed_with_own_cells": eq})
    path = Path(__file__).resolve().parent / "results" / "ext_diagnostic.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, list(out[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(out)
        print(*[tuple(o.values()) for o in out], sep="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
