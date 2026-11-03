"""Compare the three AST/CFG wrappers on one shared sample (no model call).

Wrappers: q10 (ql10-blocks/q10_astcfg.py), f3 (f3-recovery/tools/astcfg.py ast_pair/cfg_pair) and
l2 (round2/metrics_ext.py as l2_astcfg.py calls it). All three call the same Gate-Breaker
``metrics.py`` (AST, Algorithm 2) and the same ``odin3_cfg.py`` probe (CFG, Algorithm 3); the
comparison finds what the wrappers add. Sample: arm A draw 1 reply, N problems spread evenly over the
reply size ranking. Output: results/scorer_compare.csv.
Usage: python -B q11_scorecmp.py [N]
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path
from typing import Any

import q11_env as env

import q10_astcfg as q10  # noqa: E402  (path set by q11_env)


def l2_score(ref: Path, cand: Path, binding: Any) -> tuple[str, str]:
    import metrics_ext as mx
    try:
        a = f"{mx.ast_similarity(mx.parse_clean(ref), cand):.6f}"
    except Exception as err:
        a = f"ERR {type(err).__name__}"
    try:
        c = f"{mx.cfg_similarity(mx.cfg_of(binding, ref), mx.cfg_of(binding, cand)):.6f}"
    except Exception as err:
        c = f"ERR {type(err).__name__}"
    return a, c


def f3_score(ref: Path, cand: Path, binding: Any) -> tuple[str, str]:
    import astcfg as f3
    try:
        a = f"{f3.ast_pair(ref, cand, cand, '')[0]:.6f}"
    except Exception as err:
        a = f"ERR {type(err).__name__}"
    try:
        c = f"{f3.cfg_pair(binding, ref, cand, cand)[0]:.6f}"
    except Exception as err:
        c = f"ERR {type(err).__name__}"
    return a, c


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    q10.SCRATCH.mkdir(parents=True, exist_ok=True)
    os.chdir(q10.SCRATCH)
    files = sorted((env.FULL / "A" / "1").glob("*.txt"), key=lambda f: f.stat().st_size)
    files = files[:: max(1, len(files) // n)][:n]
    sc = q10.Scorer()
    rows = []
    for f in files:
        p = f.stem
        code = q10.a_code(p, 1)
        if code is None:
            continue
        cand = q10.SCRATCH / f"cmp_{p}.sv"
        cand.write_text(code, encoding="utf-8", newline="\n")
        ref = env.REFS / f"{p}_ref.sv"
        s = sc.score(p, cand, "TopModule")
        a2, c2 = l2_score(ref, cand, sc.binding)
        a3, c3 = f3_score(ref, cand, sc.binding)
        rows.append({"problem": p, "q10_ast": s["ast"] or s["ast_err"], "l2_ast": a2, "f3_ast": a3,
                     "q10_cfg": s["cfg"] or s["cfg_err"], "l2_cfg": c2, "f3_cfg": c3})
        print(rows[-1], flush=True)
    out = env.RES / "scorer_compare.csv"
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
