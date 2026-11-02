"""Score the chosen prefixes of a rule against the answer key (EXPERIMENT.md "Evaluation").

``score(units, picks)``: picks[i][b] is the chosen prefix of block b of unit i. Returns one row per
construct (right, claimed with its kind, size of the best-Jaccard block, failure class) and one
row per block (claims for recall and precision).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import q7_env as env
import q7_feat as ft

CLASSES = ("NOSEED", "ORDER", "TOOSMALL", "TOOBIG", "MERGED", "BETWEEN")


def failure_class(u: ft.UnitData, j: int, picks: list[int]) -> str:
    if not any(bp.inter[j, -1] for bp in u.blocks):
        return "NOSEED"
    best: tuple[float, int] | None = None
    for b, bp in enumerate(u.blocks):
        ok = bp.right[j]
        if ok.any():
            jm = float(bp.jaccard[j][ok].max())
            if best is None or jm > best[0]:
                best = (jm, b)
    if best is None:
        return "ORDER"
    bp = u.blocks[best[1]]
    k = picks[best[1]]
    sizes = bp.size[bp.right[j]]
    if bp.size[k] < sizes.min():
        return "TOOSMALL"
    if bp.size[k] > sizes.max():
        others = [i for i in range(len(u.cons)) if i != j]
        merged = any(bp.inter[i, k] / bp.ntrue[i] >= 0.5 for i in others)
        return "MERGED" if merged else "TOOBIG"
    return "BETWEEN"


def construct_row(u: ft.UnitData, j: int, picks: list[int]) -> dict[str, Any]:
    part, kind, n_true = u.cons[j]
    right = claimed = False
    best = (-1.0, -1)  # (jaccard, block)
    for b, bp in enumerate(u.blocks):
        k = picks[b]
        if bp.right[j, k]:
            right = True
            argmax = env.KINDS[int(np.argmax(bp.post[k]))]
            claimed = claimed or (bp.size[k] >= 4 and argmax == kind)
        jac = float(bp.jaccard[j, k])
        if jac > best[0] or (jac == best[0] and best[1] >= 0 and
                             bp.size[k] < u.blocks[best[1]].size[picks[best[1]]]):
            best = (jac, b)
    bsize = int(u.blocks[best[1]].size[picks[best[1]]]) if best[1] >= 0 else 0
    oracle = any(bp.right[j].any() for bp in u.blocks)
    return {"set": u.set, "design": u.design, "cell": u.cell, "part": part, "kind": kind,
            "n_true": n_true, "right": int(right), "claimed": int(claimed),
            "oracle": int(oracle), "best_jaccard": round(max(best[0], 0.0), 4),
            "best_size": bsize, "ratio": round(bsize / n_true, 4),
            "cls": "" if right else failure_class(u, j, picks)}


def block_rows(u: ft.UnitData, picks: list[int]) -> list[dict[str, Any]]:
    out = []
    for b, bp in enumerate(u.blocks):
        k = picks[b]
        argmax = env.KINDS[int(np.argmax(bp.post[k]))]
        right_kinds = {u.cons[j][1] for j in range(len(u.cons)) if bp.right[j, k]}
        out.append({"set": u.set, "design": u.design, "cell": u.cell, "bid": bp.bid,
                    "size": int(bp.size[k]), "argmax": argmax, "claim": int(
                        bp.size[k] >= 4 and argmax != "glue"),
                    "tp": int(argmax in right_kinds), "path_len": int(bp.size[-1])})
    return out


def score(units: list[ft.UnitData], picks: list[list[int]]
          ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cons: list[dict[str, Any]] = []
    blocks: list[dict[str, Any]] = []
    for u, pk in zip(units, picks, strict=True):
        cons.extend(construct_row(u, j, pk) for j in range(len(u.cons)))
        blocks.extend(block_rows(u, pk))
    return cons, blocks


def share(rows: list[dict[str, Any]]) -> float:
    return sum(r["right"] for r in rows) / len(rows) if rows else float("nan")
