"""Re-score the replies of llm-full (A, B, C) and llm-hints2 (A2, B1p, B2, W) with the Q-L10 scorer.

No model call. The scorer is ``q10_astcfg.Scorer`` (chosen in ``results/scorer_compare.csv``). Per
(arm, problem, draw) with a compiled reply (outcome ``pass`` or ``runtime``) two variants: ``raw``
(the code between [BEGIN] and [DONE], as written) and ``flat`` (the same code through Odin III
``hierarchy; proc; flatten; write_verilog``, the writer D-flat goes through). Resumable; sharded.
Usage: python -B q11_rescore.py SHARD NSHARDS   -> $QL11_OUT/rescore/shard<SHARD>.csv
"""

from __future__ import annotations

import csv
import importlib
import os
import sys
from pathlib import Path
from typing import Any

import q11_env as env

q10: Any = importlib.import_module("q10_astcfg")

FIELDS = ["exp", "arm", "problem", "quartile", "draw", "variant", "ast", "cfg", "ast_err",
          "cfg_err"]
SOURCES = (("llm-full", env.EXP / "llm-full" / "results" / "results.csv", env.FULL),
           ("llm-hints2", env.EXP / "llm-hints2" / "results" / "results.csv", env.H2))


def items() -> list[tuple[str, str, str, str, int, Path]]:
    out = []
    for exp, csvp, root in SOURCES:
        for r in csv.DictReader(csvp.open(encoding="utf-8")):
            if r["outcome"] in ("pass", "runtime"):
                f = root / r["arm"] / r["draw"] / f"{r['problem']}.txt"
                out.append((exp, r["arm"], r["problem"], r["quartile"], int(r["draw"]), f))
    out.sort(key=lambda x: (x[5].stat().st_size if x[5].is_file() else 0, x[0], x[1], x[2], x[4]))
    return out


def code_of(f: Path) -> str | None:
    if not f.is_file():
        return None
    code, ok = env.mod_collect().extract_rtl(f.read_text(encoding="utf-8", errors="replace"))
    return code if ok else None


def main() -> int:
    shard, nsh = int(sys.argv[1]), int(sys.argv[2])
    scratch = env.OUT11 / "scratch" / f"s{shard}"
    scratch.mkdir(parents=True, exist_ok=True)
    q10.SCRATCH = scratch
    os.chdir(scratch)
    outp = env.OUT11 / "rescore" / f"shard{shard}.csv"
    outp.parent.mkdir(parents=True, exist_ok=True)
    done: list[dict[str, str]] = []
    if outp.is_file():
        done = list(csv.DictReader(outp.open(encoding="utf-8")))
    have = {(r["exp"], r["arm"], r["problem"], r["draw"], r["variant"]) for r in done}
    sc = q10.Scorer()
    for i, (exp, arm, p, quart, draw, f) in enumerate(items()):
        if i % nsh != shard:
            continue
        code = code_of(f)
        src = None
        if code is not None:
            src = scratch / f"c_{exp}_{arm}_{p}_{draw}.sv"
            src.write_text(code, encoding="utf-8", newline="\n")
        for var in ("raw", "flat"):
            if (exp, arm, p, str(draw), var) in have:
                continue
            row: dict[str, Any] = {"exp": exp, "arm": arm, "problem": p, "quartile": quart,
                                   "draw": draw, "variant": var, "ast": "", "cfg": "",
                                   "ast_err": "", "cfg_err": ""}
            use: Path | None = src
            if src is None:
                row["ast_err"] = row["cfg_err"] = "no code"
            elif var == "flat":
                use = scratch / f"f_{exp}_{arm}_{p}_{draw}.v"
                try:
                    q10.flatten(src, use, "TopModule")
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
        print(i, exp, arm, p, draw, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
