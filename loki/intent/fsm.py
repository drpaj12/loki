"""A1: state-machine claims with states, reset state, encoding and transitions.

An FSM claim is made only when its transition relation can be read: the reachable states are
explored by bit-parallel simulation of the next-state cone (all values of the control nets at
once) and every transition carries its condition over netlist nets. A group whose controls are too
many or whose reachable set is too large is not claimed. Pure given an ``FnGraph``.
"""

from __future__ import annotations

import random
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass

from loki.intent.boolmin import MAX_VARS, Product, products
from loki.re.fngraph import FnGraph
from loki.re.seqtable import d_nets
from loki.re.sim import cone, simulate

CONTROLS_MAX = 14
STATES_MAX = 40
SAMPLE_STATES = 24


@dataclass(frozen=True)
class Transition:
    src: int
    dst: int
    cond: tuple[Product, ...]


@dataclass(frozen=True)
class Fsm:
    """State bit ``i`` is net ``q[i]``; ``reset`` is ``(net, active level, state)`` or None."""

    q: tuple[int, ...]
    controls: tuple[int, ...]
    reset: tuple[int, int, int] | None
    start: int
    states: tuple[int, ...]
    encoding: str
    transitions: tuple[Transition, ...]


def _column(i: int, m: int) -> int:
    block = ((1 << (1 << i)) - 1) << (1 << i)
    out = 0
    for x in range(0, 1 << m, 1 << (i + 1)):
        out |= block << x
    return out


class _Cone:
    """The next-state cone of a state group, simulated for many (state, control) vectors."""

    def __init__(self, graph: FnGraph, q: Sequence[int]) -> None:
        self.graph, self.q = graph, tuple(q)
        self.ds = d_nets(graph, q)
        self.cells, side = cone(graph, frozenset(), self.ds, frozenset())
        self.consts = {
            n: graph.cells[graph.driver[n]].table & 1
            for n in side
            if n in graph.driver and graph.cells[graph.driver[n]].kind == "const"
        }
        qset = set(q)
        self.controls = tuple(sorted(n for n in side if n not in qset and n not in self.consts))

    def step(self, states: Sequence[int], forced: dict[int, int]) -> list[list[int]]:
        """``out[s][cv]``: next state of ``states[s]`` for the control value ``cv`` over the free
        controls (forced controls are removed from the vector; ``forced`` maps net to 0/1)."""
        free = [n for n in self.controls if n not in forced]
        m = len(free)
        width = 1 << m
        total = width * len(states)
        values: dict[int, int] = {}
        ones = (1 << total) - 1
        for j, net in enumerate(free):
            col = _column(j, m)
            values[net] = sum(col << (s * width) for s in range(len(states)))
        for net, v in forced.items():
            values[net] = ones if v else 0
        for net, v in self.consts.items():
            values[net] = ones if v else 0
        blk = (1 << width) - 1
        for i, net in enumerate(self.q):
            values[net] = sum(blk << (s * width) for s, sv in enumerate(states) if (sv >> i) & 1)
        nets = simulate(self.graph, self.cells, values, total)
        out: list[list[int]] = []
        for s in range(len(states)):
            row = [0] * width
            for i, d in enumerate(self.ds):
                bits = (nets.get(d, 0) >> (s * width)) & blk
                for cv in range(width):
                    row[cv] |= ((bits >> cv) & 1) << i
            out.append(row)
        return out


def _sample_states(k: int, rng: random.Random) -> list[int]:
    pool = {0, (1 << k) - 1} | {1 << i for i in range(min(k, 12))}
    while len(pool) < min(SAMPLE_STATES, 1 << k):
        pool.add(rng.getrandbits(k))
    return sorted(pool)[:SAMPLE_STATES]


def find_reset(cn: _Cone, rng: random.Random) -> tuple[int, int, int] | None:
    """A control ``(net, active level, state)`` that forces one state whatever the state and the
    other controls are. The lowest net wins."""
    budget = max(2, min(SAMPLE_STATES, (1 << 20) >> len(cn.controls)))
    states = _sample_states(len(cn.q), rng)[:budget]
    for net in cn.controls:
        for level in (1, 0):
            rows = cn.step(states, {net: level})
            nexts = {v for row in rows for v in row}
            if len(nexts) == 1:
                return net, level, next(iter(nexts))
    return None


def encoding_of(states: Sequence[int], k: int) -> str:
    """``binary`` (the states are 0..n-1), ``one-hot`` (every state but 0 has one bit set and at
    least ``k - 1`` of them) or ``coded`` (anything else)."""
    if sorted(states) == list(range(len(states))):
        return "binary"
    live = [s for s in states if s]
    if len(states) >= 3 and live and all(s & (s - 1) == 0 for s in live) and len(live) >= k - 1:
        return "one-hot"
    return "coded"


def _relevant(rows: dict[int, list[int]], m: int) -> list[int]:
    """Indices of the control bits that change some next state of some explored state."""
    keep = []
    for j in range(m):
        if any(row[cv] != row[cv ^ (1 << j)] for row in rows.values() for cv in range(len(row))):
            keep.append(j)
    return keep


def _explore(
    cn: _Cone, start: int, forced: dict[int, int]
) -> tuple[dict[int, list[int]], list[int]] | None:
    """The next-state rows of every state reachable from ``start``, or None past the cap."""
    rows: dict[int, list[int]] = {}
    todo = deque([start])
    seen = {start}
    free = [n for n in cn.controls if n not in forced]
    while todo:
        batch: list[int] = []
        while todo and len(batch) < 8:
            batch.append(todo.popleft())
        for s, row in zip(batch, cn.step(batch, forced), strict=True):
            rows[s] = row
            for nxt in row:
                if nxt not in seen:
                    seen.add(nxt)
                    todo.append(nxt)
        if len(seen) > STATES_MAX:
            return None
    return rows, [n for n in free]


def _transitions(
    rows: dict[int, list[int]], free: list[int]
) -> tuple[list[int], list[Transition]] | None:
    keep = _relevant(rows, len(free))
    if len(keep) > MAX_VARS:
        return None
    nets = [free[j] for j in keep]
    out: list[Transition] = []
    for src in sorted(rows):
        by_dst: dict[int, list[int]] = {}
        for cv, dst in enumerate(rows[src]):
            small = sum(((cv >> j) & 1) << b for b, j in enumerate(keep))
            by_dst.setdefault(dst, []).append(small)
        for dst in sorted(by_dst):
            minterms = sorted(set(by_dst[dst]))
            out.append(Transition(src, dst, products(minterms, nets)))
    return nets, out


def cone_of(graph: FnGraph, q: Sequence[int]) -> _Cone | None:
    """The next-state cone of ``q``, or None when it has too many control nets to be explored."""
    cn = _Cone(graph, q)
    return None if len(cn.controls) > CONTROLS_MAX or len(q) > 64 else cn


def read_fsm(graph: FnGraph, q: Sequence[int], seed: str = "fsm") -> Fsm | None:
    """The state machine of the flip-flops driving ``q`` (LSB first), or None when it cannot be
    read: too many control nets (more than ``CONTROLS_MAX``, or more than ``MAX_VARS`` that matter
    for a transition), more than ``STATES_MAX`` reachable states, or one state."""
    cn = cone_of(graph, q)
    if cn is None:
        return None
    rng = random.Random(f"intent:{seed}:{min(q)}")
    reset = find_reset(cn, rng)
    forced = {} if reset is None else {reset[0]: 1 - reset[1]}
    start = 0 if reset is None else reset[2]
    got = _explore(cn, start, forced)
    if got is None:
        return None
    rows, free = got
    if len(rows) < 2:
        return None
    got_t = _transitions(rows, free)
    if got_t is None:
        return None
    nets, trans = got_t
    states = tuple(sorted(rows))
    return Fsm(tuple(q), tuple(nets), reset, start, states, encoding_of(states, len(q)),
               tuple(t for t in trans))
