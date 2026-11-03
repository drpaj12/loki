"""AST and CFG similarity of the Q-L12 rows to the VerilogEval reference (the Q-L11 scorer).

No model call. The scorer is ``ql10-blocks/q10_astcfg.py`` imported unchanged (Gate-Breaker
``metrics.py`` AST depth 3, the Odin III CFG probe with the numpy kernel, the Odin III
``flatten; write_verilog`` writer); only its scratch directory is moved to this lane's run root.
Candidates per (problem, endpoint, arm, draw): D = the assembled ``sample.sv`` (``TopModule`` and
``Block_<k>``), A = the reply code; variants ``raw`` (as written; for D the top module only) and
``flat`` (through the same Odin III flatten step on both arms; the headline). Rows with the outcome
``pass`` or ``runtime`` only, as Q-L10; no value for the processor modules (no reference RTL).
Usage: ``python -B q12_astcfg.py [--run DIR]``; writes ``<run>/astcfg_rows.csv`` (resumable).
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Any

import q12_env as env

q10a: Any = env.mod("q10_astcfg")
FIELDS = ["problem", "endpoint", "tier", "arm", "draw", "variant", "ast", "cfg", "ast_err",
          "cfg_err"]


def work_items(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [r for r in rows if r["outcome"] in ("pass", "runtime") and r["tier"] != "ext"]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", type=Path, default=env.RUN)
    run = ap.parse_args(argv).run
    scratch = run / "astcfg-scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    q10a.SCRATCH = scratch  # the scorer's module global: keep the Q-L10 run root untouched
    os.chdir(scratch)  # pyverilog writes parser tables to the working directory
    with (run / "results.csv").open(encoding="utf-8", newline="") as fh:
        rows = work_items(list(csv.DictReader(fh)))
    outp = run / "astcfg_rows.csv"
    done: list[dict[str, str]] = []
    if outp.is_file():
        with outp.open(encoding="utf-8", newline="") as fh:
            done = list(csv.DictReader(fh))
    have = {(r["problem"], r["endpoint"], r["arm"], r["draw"], r["variant"]) for r in done}
    sc = q10a.Scorer()
    for r in rows:
        p, ep, arm, draw = r["problem"], r["endpoint"], r["arm"], r["draw"]
        src = run / "work" / ep / p / f"top-{arm}-{draw}" / "sample.sv"
        for var in ("raw", "flat"):
            if (p, ep, arm, draw, var) in have:
                continue
            row: dict[str, Any] = {"problem": p, "endpoint": ep, "tier": r["tier"], "arm": arm,
                                   "draw": draw, "variant": var, "ast": "", "cfg": "",
                                   "ast_err": "", "cfg_err": ""}
            use: Path | None = src
            if not src.is_file():
                use = None
                row["ast_err"] = row["cfg_err"] = "no code"
            elif var == "flat":
                use = scratch / f"flat_{ep}_{arm}_{p}_{draw}.v"
                try:
                    q10a.flatten(src, use, "TopModule")
                except Exception as err:
                    use = None
                    row["ast_err"] = row["cfg_err"] = f"flatten {type(err).__name__}"
            if use is not None:
                row.update(sc.score(p, use, "TopModule"))
            done.append({k: str(row[k]) for k in FIELDS})
            with outp.open("w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, FIELDS, lineterminator="\n")
                w.writeheader()
                w.writerows(done)
        print(p, ep, arm, draw, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
