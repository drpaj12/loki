"""Right blocks, failure classes and kind claims of a set of blocks against the answer key."""

from __future__ import annotations

from typing import Any

import numpy as np
import q9_env as env
from q9_units import Blk

MIN_CLAIM = 4
CLASSES = ("NOSEED", "UNDERREACH", "SPLIT", "BLOATED")


def is_right(cells: frozenset[int], true: frozenset[int]) -> bool:
    inter = len(cells & true)
    return bool(inter / len(true) >= 0.8 and inter / (len(cells) + len(true) - inter) >= 0.5)


def failure_class(blocks: list[Blk], true: frozenset[int]) -> str:
    """Why no block is right for the construct (EXPERIMENT.md "Failure classes")."""
    inter = [len(b.cells & true) for b in blocks]
    if not any(inter):
        return "NOSEED"
    if any(i / len(true) >= 0.8 for i in inter):
        return "BLOATED"
    return "SPLIT" if sum(inter) / len(true) >= 0.8 else "UNDERREACH"


def construct_rows(key: tuple[str, str, str], blocks: list[Blk],
                   cons: list[tuple[int, str, frozenset[int]]]) -> list[dict[str, Any]]:
    rows = []
    for part, kind, true in cons:
        right = any(is_right(b.cells, true) for b in blocks)
        rows.append({"set": key[0], "design": key[1], "cell": key[2], "part": part, "kind": kind,
                     "n_true": len(true), "right": int(right),
                     "cls": "" if right else failure_class(blocks, true)})
    return rows


def kind_tally(blocks: list[Blk], cons: list[tuple[int, str, frozenset[int]]],
               posts: list[np.ndarray]) -> dict[str, Any]:
    """Claims and true positives per kind and the recovered (part, kind) pairs (as #75)."""
    k5 = env.KINDS5
    claims = dict.fromkeys(k5, 0)
    tp = dict.fromkeys(k5, 0)
    got: set[tuple[int, str]] = set()
    for b, p in zip(blocks, posts, strict=True):
        arg = int(np.argmax(p))
        if arg == env.GLUE or len(b.cells) < MIN_CLAIM:
            continue
        kind = env.KINDS[arg]
        right = [(pt, k) for pt, k, t in cons if is_right(b.cells, t)]
        claims[kind] += 1
        tp[kind] += int(any(k == kind for _pt, k in right))
        got.update((pt, k) for pt, k in right if k == kind)
    return {"claims": claims, "tp": tp, "got": sorted(got),
            "cons": [(pt, k) for pt, k, _t in cons]}
