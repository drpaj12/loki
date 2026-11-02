"""The anchor classes added by Q-L8b (EXPERIMENT.md "Anchor classes added"): bank, loop, const.

``extra_anchors(g, old, classes)`` returns the new anchors for the classes asked for; a new anchor
never holds a cell of an old anchor.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import q8b_env as env

qn = env.mod("q6_net")
CLASSES = ("bank", "loop", "const")
BANK_MIN = 8


def free_ffs(g: Any, taken: set[int]) -> list[int]:
    return [i for i in range(g.b.n) if g.b.latch[i] and i not in taken]


def bank_anchors(g: Any, ffs: list[int]) -> list[Any]:
    """Flip-flops grouped by the exact set of global nets in their next-state cone (>= 8 each)."""
    groups: dict[frozenset[str], list[int]] = defaultdict(list)
    for i in ffs:
        cut = frozenset(n for n in qn.ff_cone(g, i)[1] if g.is_cut(n))
        if cut:
            groups[cut].append(i)
    ordered = sorted(groups.values(), key=min)
    return [qn.Anchor("bank", frozenset(m)) for m in ordered if len(m) >= BANK_MIN]


def loop_anchors(g: Any, ffs: list[int]) -> list[Any]:
    """Strongly connected components of two or more flip-flops of the dependency graph."""
    fs = set(ffs)
    succ = {i: {d for d in qn.ff_cone(g, i)[0] if d != i and d in fs} for i in ffs}
    return [qn.Anchor("loop", frozenset(c)) for c in qn._sccs(ffs, succ) if len(c) >= 2]


def const_anchors(g: Any, taken: set[int]) -> list[Any]:
    cs = [i for i in range(g.b.n) if not g.b.ins[i] and not g.b.latch[i] and i not in g.hard
          and i not in taken]
    return [qn.Anchor("const", frozenset(cs))] if cs else []


def extra_anchors(g: Any, old: list[Any], classes: tuple[str, ...]) -> list[Any]:
    taken = {i for a in old for i in a.cells}
    out: list[Any] = []
    if "bank" in classes:
        out += bank_anchors(g, free_ffs(g, taken))
        taken |= {i for a in out for i in a.cells}
    if "loop" in classes:
        new = loop_anchors(g, free_ffs(g, taken))
        out += new
        taken |= {i for a in new for i in a.cells}
    if "const" in classes:
        out += const_anchors(g, taken)
    return out
