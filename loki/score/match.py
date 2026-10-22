"""One-to-one greedy matching by Jaccard similarity (L1 spec 12.2)."""

from __future__ import annotations

import re
from collections.abc import Sequence

_DIGITS = re.compile(r"(\d+)")


def natural_key(text: str) -> tuple[tuple[int, int, str], ...]:
    """Sort key that orders ``h2`` before ``h10`` (digit runs compare as numbers)."""
    return tuple(
        (1, int(part), "") if part.isdigit() else (0, 0, part)
        for part in _DIGITS.split(text) if part
    )


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """``|a & b| / |a | b|``; 0.0 when both are empty."""
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def pairs_above(
    preds: Sequence[tuple[str, frozenset[str]]],
    gts: Sequence[tuple[str, frozenset[str]]],
    threshold: float,
) -> list[tuple[str, str, float]]:
    """Every (prediction, ground truth, Jaccard) with Jaccard >= ``threshold``, unordered.

    Only pairs that share a member are tried, so the cost follows the overlaps, not P x G."""
    by_member: dict[str, list[int]] = {}
    for gi, (_, cells) in enumerate(gts):
        for c in cells:
            by_member.setdefault(c, []).append(gi)
    out: list[tuple[str, str, float]] = []
    for pid, cells in preds:
        near = {gi for c in cells for gi in by_member.get(c, ())}
        for gi in sorted(near):
            j = jaccard(cells, gts[gi][1])
            if j >= threshold:
                out.append((pid, gts[gi][0], j))
    return out


def greedy_from_pairs(
    pairs: Sequence[tuple[str, str, float]],
) -> list[tuple[str, str, float]]:
    """Greedy one-to-one choice from candidate pairs: Jaccard descending, then prediction id, then
    ground-truth id (natural order); each side is used once. The result is in that order."""
    ordered = sorted(pairs, key=lambda t: (-t[2], natural_key(t[0]), natural_key(t[1])))
    used_p: set[str] = set()
    used_g: set[str] = set()
    out: list[tuple[str, str, float]] = []
    for pid, gid, j in ordered:
        if pid in used_p or gid in used_g:
            continue
        used_p.add(pid)
        used_g.add(gid)
        out.append((pid, gid, j))
    return out


def match_greedy(
    preds: Sequence[tuple[str, frozenset[str]]],
    gts: Sequence[tuple[str, frozenset[str]]],
    threshold: float,
) -> list[tuple[str, str, float]]:
    """One-to-one matches of spec 12.2 (see ``greedy_from_pairs`` for the order)."""
    return greedy_from_pairs(pairs_above(preds, gts, threshold))
