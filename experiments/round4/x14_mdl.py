"""Exploratory entry 2026-10-25-c, item 17 of the round-4 fix brief (H14d).

The registered H14d correlation pools four variants of the same designs (n = 516), so its p value
treats the rows as independent. This script writes ``x14_mdl.csv``: the correlation and partial
correlation per variant (own n) and, for the pooled rows, a design-clustered percentile bootstrap
interval (resample designs, keep all their variant rows; B = 2000, ``random.Random(4)``). Not part
of the registered analysis; no status changes.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Any

import decide
import r4lib

VARS = ("f2-none", "f3-none", "f2-calib", "f3-calib")
B = 2000


def triple(rr: list[dict[str, str]], col: str) -> tuple[list[float], list[float], list[float]]:
    return ([math.log(float(r["ratio"])) for r in rr], [float(r[col]) for r in rr],
            [math.log(max(1, int(r["tokens"]))) for r in rr])


def main() -> int:
    rows = [r for r in r4lib.read_csv(r4lib.OUT / "l14_mdl.csv") if r["variant"] in VARS]
    out: list[list[Any]] = []
    for col in ("ast", "cfg"):
        sel = [r for r in rows if r[col] != ""]
        for v in (*VARS, "pooled"):
            rr = [r for r in sel if v in ("pooled", r["variant"])]
            rho, p, pr, pp = decide.spearman_partial(*triple(rr, col))
            out.append([col, v, len(rr), round(rho, 6), f"{p:.3g}", round(pr, 6), f"{pp:.3g}",
                        "", "", "", ""])
        by: dict[str, list[dict[str, str]]] = defaultdict(list)
        for r in sel:
            by[r["design"]].append(r)
        designs = sorted(by)
        rnd = random.Random(4)
        rhos, parts = [], []
        for _ in range(B):
            pick = [r for d in (rnd.choice(designs) for _ in designs) for r in by[d]]
            rho, _p, pr, _pp = decide.spearman_partial(*triple(pick, col))
            rhos.append(rho)
            parts.append(pr)
        rhos.sort()
        parts.sort()
        lo, hi = math.ceil(0.025 * B) - 1, math.ceil(0.975 * B) - 1
        out[-1][7:] = [len(designs), f"[{rhos[lo]:.4f}, {rhos[hi]:.4f}]",
                       f"[{parts[lo]:.4f}, {parts[hi]:.4f}]", B]
    r4lib.write_csv(r4lib.OUT / "x14_mdl.csv",
                    ["measure", "variant", "n", "rho", "p", "partial_rho", "partial_p",
                     "designs", "rho_ci_design_clustered", "partial_ci_design_clustered", "B"],
                    out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
