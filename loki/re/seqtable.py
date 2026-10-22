"""Transition tables of flip-flop groups and their classification (L1 spec 7.7). Pure.

Deviation from the spec text (reported in the plan result): when the table is sampled, the state
values are the span of random basis vectors (closed under XOR, so the ``linear`` test has pairs)
and the control values are a pool of at most 16 vectors (so every control value has many rows),
instead of ``SAMPLE_N`` independent random rows. A modulo counter needs exactly one terminal
state ``E = {e}`` (``M = e + 1``, any wrap value ``r``); a larger terminal set is ``other``.
"""

from __future__ import annotations

import random
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass

from loki.re.fngraph import FnGraph
from loki.re.provers import EXHAUSTIVE_MAX, SAMPLE_N
from loki.re.sim import cone, simulate

POOL_MAX = 16
LINEAR_PAIRS = 256
ROWS_MAX = 256


@dataclass(frozen=True)
class SeqTable:
    """``rows[(q value, control value)]`` is the next ``q`` value; bit ``i`` of ``q`` is net
    ``q[i]``, bit ``j`` of a control value is net ``controls[j]``."""

    q: tuple[int, ...]
    controls: tuple[int, ...]
    exact: bool
    rows: dict[tuple[int, int], int]


def _column(i: int, m: int) -> int:
    block = ((1 << (1 << i)) - 1) << (1 << i)
    out = 0
    for x in range(0, 1 << m, 1 << (i + 1)):
        out |= block << x
    return out


def d_nets(graph: FnGraph, q: Sequence[int]) -> list[int]:
    """The D net of the flip-flop driving each net of ``q``."""
    return [graph.cells[graph.driver[n]].ins[0] for n in q]


def _constants(graph: FnGraph, nets: frozenset[int], n: int) -> dict[int, int]:
    out: dict[int, int] = {}
    for net in nets:
        drv = graph.driver.get(net)
        if drv is not None and graph.cells[drv].kind == "const":
            out[net] = ((1 << n) - 1) if graph.cells[drv].table & 1 else 0
    return out


def _span(rng: random.Random, k: int, count: int) -> list[int]:
    basis = [rng.getrandbits(k) for _ in range(count)]
    out = [0]
    for b in basis:
        out += [v ^ b for v in out]
    return out


def _pool(rng: random.Random, c: int) -> list[int]:
    if c == 0:
        return [0]
    if (1 << c) <= POOL_MAX:
        return list(range(1 << c))
    return sorted({rng.getrandbits(c) for _ in range(POOL_MAX)} | {0})


def transition_table(graph: FnGraph, q: Sequence[int], rng: random.Random) -> SeqTable:
    """D nets of the flip-flops whose Q nets are ``q``; exact when ``k + |C| <= 16``, else a
    sample of at most ``SAMPLE_N`` rows (``rng`` is only used then)."""
    k = len(q)
    ds = d_nets(graph, q)
    cells, side = cone(graph, frozenset(), ds, frozenset())
    consts = _constants(graph, side, 1)
    controls = tuple(sorted(n for n in side if n not in set(q) and n not in consts))
    c = len(controls)
    exact = k + c <= EXHAUSTIVE_MAX
    if exact:
        qs, cs = list(range(1 << k)), list(range(1 << c))
    else:
        cs = _pool(rng, c)
        bits = (SAMPLE_N // len(cs)).bit_length() - 1
        qs = list(range(1 << k)) if k <= bits else _span(rng, k, bits)
    pairs = [(qv, cv) for cv in cs for qv in qs]
    n = len(pairs)
    if exact:
        values = {net: _column(i, k + c) for i, net in enumerate((*q, *controls))}
    else:
        values = {}
        for i, net in enumerate(q):
            values[net] = sum(((qv >> i) & 1) << x for x, (qv, _) in enumerate(pairs))
        for j, net in enumerate(controls):
            values[net] = sum(((cv >> j) & 1) << x for x, (_, cv) in enumerate(pairs))
    values.update(_constants(graph, side, n))
    nets = simulate(graph, cells, values, n)
    rows: dict[tuple[int, int], int] = {}
    for x, key in enumerate(pairs):
        rows[key] = sum(((nets.get(d, 0) >> x) & 1) << i for i, d in enumerate(ds))
    return SeqTable(tuple(q), controls, exact, rows)


def rows_by_control(t: SeqTable) -> dict[int, dict[int, int]]:
    """``{control value: {q: next q}}``."""
    out: dict[int, dict[int, int]] = {}
    for (qv, cv), nxt in t.rows.items():
        out.setdefault(cv, {})[qv] = nxt
    return out


def _modulo(items: list[tuple[int, int]], mask: int) -> str | None:
    up = [(q, g) for q, g in items if g != (q + 1) & mask]
    if len(up) == 1 and up[0][0] < mask:
        return f"modulo-{up[0][0] + 1}" + (f"@{up[0][1]}" if up[0][1] else "")
    down = [(q, g) for q, g in items if g != (q - 1) & mask]
    if len(down) == 1 and down[0][0] == 0 and down[0][1] != mask:
        return f"down-{down[0][1] + 1}"
    return None


def _linear(rows: dict[int, int]) -> bool:
    g0 = rows.get(0)
    if g0 is None:
        return False
    qs = sorted(rows)
    n = len(qs)
    tested = 0
    for i in range(min(n, LINEAR_PAIRS)):
        a, b = qs[i], qs[(i * 5 + 3) % n]
        if a == b or (a ^ b) not in rows:
            continue
        tested += 1
        if rows[a ^ b] != rows[a] ^ rows[b] ^ g0:
            return False
    return tested > 0


def _label(k: int, rows: dict[int, int]) -> str:
    mask = (1 << k) - 1
    items = sorted(rows.items())
    if all(g == q for q, g in items):
        return "hold"
    if all(g == (q + 1) & mask for q, g in items):
        return "inc"
    if all(g == (q - 1) & mask for q, g in items):
        return "dec"
    mod = _modulo(items, mask)
    if mod is not None:
        return mod
    if len({g for _, g in items}) == 1:
        return "load-const"
    x = items[0][1] & 1
    if all(g == ((q << 1) | x) & mask for q, g in items):
        return "shift-l"
    x = (items[0][1] >> (k - 1)) & 1
    if all(g == (q >> 1) | (x << (k - 1)) for q, g in items):
        return "shift-r"
    return "linear" if _linear(rows) else "other"


def classify(t: SeqTable) -> dict[int, str]:
    """Per control value: ``hold inc dec modulo-M[@r] down-M load-const shift-l shift-r linear
    other`` (``modulo-M@r`` wraps to ``r``, ``down-M`` counts ``M - 1`` down to 0 and wraps to
    ``M - 1``)."""
    k = len(t.q)
    return {cv: _label(k, rows) for cv, rows in sorted(rows_by_control(t).items())}


def parse_count(label: str) -> tuple[str, int, int] | None:
    """``(direction, modulus, wrap)`` of a counting label (modulus 0: ``2**k``), else None."""
    if label == "inc":
        return ("up", 0, 0)
    if label == "dec":
        return ("down", 0, 0)
    if label.startswith("modulo-"):
        mod, _, wrap = label[7:].partition("@")
        return ("up", int(mod), int(wrap) if wrap else 0)
    if label.startswith("down-"):
        return ("down", int(label[5:]), 0)
    return None


def reachable(t: SeqTable, start: int) -> tuple[list[int], list[tuple[int, int, int]]]:
    """States reachable from ``start`` over every control value, and the transitions
    ``(q, control value, next q)`` among them, both sorted."""
    by_q: dict[int, list[tuple[int, int]]] = {}
    for (qv, cv), nxt in t.rows.items():
        by_q.setdefault(qv, []).append((cv, nxt))
    seen = {start}
    todo = deque([start])
    edges: list[tuple[int, int, int]] = []
    while todo:
        qv = todo.popleft()
        for cv, nxt in sorted(by_q.get(qv, ())):
            edges.append((qv, cv, nxt))
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    return sorted(seen), sorted(edges)
