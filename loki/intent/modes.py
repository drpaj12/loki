"""Mode tables of a flip-flop group: what the group does for each value of its control nets.

``classify`` of ``loki.re.seqtable`` labels every control value (hold, inc, dec, modulo, load a
constant, shift, linear). Here the control values of one label are written as a condition over the
control nets, and a loaded constant or a shifted-in bit is traced to the control net that carries
it (parallel data, serial input). A group whose labels are all hold, load, shift or count gets a
kind from them; this covers a shift register with both a load and an enable, which the closed
templates of ``seqfn`` do not. Pure given an ``FnGraph``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from loki.intent.boolmin import MAX_VARS, Product, products
from loki.re.fngraph import FnGraph
from loki.re.seqtable import SeqTable, classify, parse_count, rows_by_control, transition_table

_SHIFT = ("shift-l", "shift-r")


@dataclass(frozen=True)
class Mode:
    """``label`` is a seqtable label; ``cond`` the control values that give it; ``data`` the control
    net that carries bit ``i`` of a loaded word (``load``) or ``(net,)`` the serial input
    (``shift``), when one net does."""

    label: str
    cond: tuple[Product, ...]
    data: tuple[int, ...] = ()


@dataclass(frozen=True)
class ModeTable:
    kind: str
    controls: tuple[int, ...]
    modes: tuple[Mode, ...]
    exact: bool


def _bit(v: int, j: int) -> int:
    return (v >> j) & 1


def _load_data(t: SeqTable, cvs: list[int]) -> tuple[int, ...]:
    """Per state bit, the one control net equal to the loaded bit on every ``cvs`` (or none)."""
    by = rows_by_control(t)
    const = {c: by[c][min(by[c])] for c in cvs}
    out: list[int] = []
    for i in range(len(t.q)):
        hit = [j for j in range(len(t.controls))
               if all(_bit(c, j) == _bit(const[c], i) for c in cvs)]
        if len(hit) != 1:
            return ()
        out.append(t.controls[hit[0]])
    return tuple(out)


def _serial(t: SeqTable, cvs: list[int], left: bool) -> tuple[int, ...]:
    by = rows_by_control(t)
    xs = {c: (by[c][min(by[c])] & 1) if left else _bit(by[c][min(by[c])], len(t.q) - 1)
          for c in cvs}
    hit = [j for j in range(len(t.controls)) if all(_bit(c, j) == xs[c] for c in cvs)]
    return (t.controls[hit[0]],) if len(hit) == 1 else ()


def _kind(labels: set[str]) -> str | None:
    """``shift_reg``, ``counter``, ``lfsr`` or (several behaviours) ``register``; None when a label
    is not one of hold, load, shift, count or linear, or the group only loads (a pipeline)."""
    shifts = labels & set(_SHIFT)
    counts = {x for x in labels if parse_count(x) is not None}
    linear = labels & {"linear"}
    if labels - shifts - counts - linear - {"hold", "load-const"}:
        return None
    families = [bool(shifts), bool(counts), bool(linear)]
    if sum(families) > 1 or len(shifts) > 1 or len(counts) > 1:
        return "register"
    if shifts:
        return "shift_reg"
    if counts:
        return "counter"
    return "lfsr" if linear else None


def _shifty(t: SeqTable) -> bool:
    """A linear group is an LFSR when it has at least four bits and, in the linear map, all but at
    most two bits just move one place (in either direction)."""
    k = len(t.q)
    if k < 4:
        return False
    plain = {"l": 0, "r": 0}
    for (qv, _), nxt in t.rows.items():
        for i in range(k - 1):
            plain["l"] += _bit(nxt, i + 1) == _bit(qv, i)
            plain["r"] += _bit(nxt, i) == _bit(qv, i + 1)
    total = len(t.rows) * (k - 1)
    return max(plain.values()) >= total * (k - 3) / (k - 1)


def mode_table(graph: FnGraph, q: tuple[int, ...], seed: str = "modes") -> ModeTable | None:
    """The mode table of ``q`` when the table is exact and every label is recognised."""
    t = transition_table(graph, q, random.Random(f"intent:{seed}"))
    if not t.exact or len(t.controls) > MAX_VARS:
        return None
    labels = classify(t)
    kind = _kind(set(labels.values()))
    if kind is None or (kind == "lfsr" and not _shifty(t)):
        return None
    modes: list[Mode] = []
    for label in sorted(set(labels.values())):
        cvs = sorted(c for c, v in labels.items() if v == label)
        data: tuple[int, ...] = ()
        if label == "load-const":
            data = _load_data(t, cvs)
        elif label in _SHIFT:
            data = _serial(t, cvs, label == "shift-l")
        modes.append(Mode(label, products(cvs, t.controls), data))
    return ModeTable(kind, t.controls, tuple(modes), True)
