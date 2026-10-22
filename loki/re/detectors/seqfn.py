"""``seqfn``: counters, shift registers and LFSRs from flip-flop groups (L1 spec 7.7).

Groups are Q-support chains, shift chains and strongly connected sets of the flip-flop
dependency graph (one clock, at most ``GROUP_MAX`` flip-flops). The bit order of a group is tried
in the order of its chain or shift path, then by toggle frequency (the least significant bit of a
counter toggles most often); the first order whose transition table classifies wins.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from loki.re.claims import Claim
from loki.re.detectors import Candidate, RoundContext, sorted_candidates
from loki.re.seqtable import (
    SeqTable,
    classify,
    parse_count,
    rows_by_control,
    transition_table,
)
from loki.re.sim import cone

GROUP_MAX = 64


@dataclass(frozen=True)
class Group:
    """Flip-flop cell ids of one group and the bit orders (LSB first) worth trying."""

    ffs: frozenset[int]
    orders: tuple[tuple[int, ...], ...]
    scc: bool = False


def _bit(value: int, j: int) -> int:
    return (value >> j) & 1


def _tarjan(nodes: Sequence[int], succ: dict[int, list[int]]) -> list[list[int]]:
    """Strongly connected sets of size >= 2 (iterative Tarjan)."""
    index: dict[int, int] = {}
    low: dict[int, int] = {}
    on: set[int] = set()
    stack: list[int] = []
    found: list[list[int]] = []
    for root in nodes:
        if root in index:
            continue
        work: list[tuple[int, int]] = [(root, 0)]
        while work:
            v, i = work.pop()
            if i == 0:
                index[v] = low[v] = len(index)
                stack.append(v)
                on.add(v)
            children = succ.get(v, [])
            descended = False
            while i < len(children):
                w = children[i]
                i += 1
                if w not in index:
                    work.append((v, i))
                    work.append((w, 0))
                    descended = True
                    break
                if w in on:
                    low[v] = min(low[v], index[w])
            if descended:
                continue
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop()
                    on.discard(w)
                    comp.append(w)
                    if w == v:
                        break
                if len(comp) > 1:
                    found.append(sorted(comp))
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[v])
    return found


def _chain_a(members: list[int], qset: dict[int, frozenset[int]]) -> list[tuple[int, ...]]:
    out: list[tuple[int, ...]] = []
    for start in members:
        if qset[start] != frozenset({start}):
            continue
        chain = [start]
        seen = {start}
        while True:
            nxt = [c for c in members if c not in seen and qset[c] == frozenset(seen) | {c}]
            if not nxt:
                break
            chain.append(nxt[0])
            seen.add(nxt[0])
        if len(chain) >= 2:
            out.append(tuple(chain))
    return out


def _links(members: Sequence[int], qset: dict[int, frozenset[int]]) -> dict[int, list[int]]:
    """``i -> [j]`` when flip-flop ``j`` reads exactly one other flip-flop of the group: ``i``."""
    group = set(members)
    succ: dict[int, list[int]] = {}
    for c in members:
        others = (qset[c] & group) - {c}
        if len(others) == 1:
            succ.setdefault(next(iter(others)), []).append(c)
    return succ


def _paths(members: Sequence[int], qset: dict[int, frozenset[int]]) -> list[tuple[int, ...]]:
    succ = _links(members, qset)
    has_pred = {j for js in succ.values() for j in js}
    out: list[tuple[int, ...]] = []
    for start in members:
        if start not in succ or start in has_pred:
            continue
        path = [start]
        while len(succ.get(path[-1], ())) == 1 and succ[path[-1]][0] not in path:
            path.append(succ[path[-1]][0])
        if len(path) >= 2:
            out.append(tuple(path))
    return out


def find_groups(ctx: RoundContext) -> list[Group]:
    """Flip-flop groups of the current view, sorted by their smallest cell id."""
    g = ctx.graph
    by_clock: dict[int, list[int]] = {}
    for cid in ctx.view.free_cells:
        cell = g.cells[cid]
        single = len(cell.ins) == 1 and len(cell.outs) == 1
        if cell.kind == "ff" and single and cell.ins[0] and cell.outs[0]:
            by_clock.setdefault(cell.clock, []).append(cid)
    found: dict[frozenset[int], list[tuple[int, ...]]] = {}
    sccs: set[frozenset[int]] = set()
    for clock in sorted(by_clock):
        ffs = sorted(by_clock[clock])
        cell_of_q = {g.cells[c].outs[0]: c for c in ffs}
        qset: dict[int, frozenset[int]] = {}
        for c in ffs:
            sup = ctx.view.support.of(g.cells[c].ins[0])
            if sup is not None:
                qset[c] = frozenset(cell_of_q[n] for n in sup if n in cell_of_q)
        members = sorted(qset)
        if len(members) < 2:
            continue
        for order in (*_chain_a(members, qset), *_paths(members, qset)):
            found.setdefault(frozenset(order), []).append(order)
        succ = {i: [j for j in members if j != i and i in qset[j]] for i in members}
        for comp in _tarjan(members, succ):
            if len(comp) <= GROUP_MAX:
                sccs.add(frozenset(comp))
                orders = _paths(comp, qset)
                found.setdefault(frozenset(comp), []).extend(
                    o for o in orders if len(o) == len(comp)
                )
    out = [
        Group(k, tuple(dict.fromkeys(v)), k in sccs)
        for k, v in found.items()
        if len(k) <= GROUP_MAX
    ]
    return sorted(out, key=lambda grp: sorted(grp.ffs))


def toggle_order(cells: Sequence[int], t: SeqTable) -> tuple[int, ...]:
    """The cells ordered by how often their bit toggles in ``t`` (most first, ties by id)."""
    counts = [0] * len(t.q)
    for (qv, _), nxt in t.rows.items():
        diff = qv ^ nxt
        for i in range(len(counts)):
            counts[i] += _bit(diff, i)
    return tuple(cells[i] for i in sorted(range(len(counts)), key=lambda i: (-counts[i], cells[i])))


def _gate(cvals: Sequence[int], on: set[int], nbits: int) -> tuple[int, int] | None:
    """A control bit ``(j, polarity)`` whose value is ``polarity`` exactly on ``on``."""
    for j in range(nbits):
        for pol in (1, 0):
            if {c for c in cvals if _bit(c, j) == pol} == on:
                return j, pol
    return None


@dataclass(frozen=True)
class _Modes:
    en: int | None
    en_active: int
    rst: int | None
    rst_active: int
    rst_value: int


def _counter_modes(t: SeqTable, labels: dict[int, str]) -> tuple[str, _Modes] | None:
    cvals = sorted(labels)
    counts = {c for c in cvals if parse_count(labels[c]) is not None}
    hold = {c for c in cvals if labels[c] == "hold"}
    load = {c for c in cvals if labels[c] == "load-const"}
    if not counts or len(counts) + len(hold) + len(load) != len(cvals):
        return None
    if len({labels[c] for c in counts}) != 1:
        return None
    nbits = len(t.controls)
    by = rows_by_control(t)
    rst: tuple[int, int] | None = None
    value = 0
    if load:
        rst = _gate(cvals, load, nbits)
        values = {next(iter(by[c].values())) for c in load}
        if rst is None or len(values) != 1:
            return None
        value = values.pop()
    rest = [c for c in cvals if c not in load]
    en: tuple[int, int] | None = None
    if hold:
        en = _gate(rest, counts, nbits)
        if en is None:
            return None
    return labels[min(counts)], _Modes(
        None if en is None else en[0], 1 if en is None else en[1],
        None if rst is None else rst[0], 1 if rst is None else rst[1], value,
    )


def _solve_taps(pairs: Sequence[tuple[int, int]]) -> int | None:
    """``taps`` with ``parity(q & taps) == fb`` for every ``(q, fb)``; free taps are 0."""
    basis: dict[int, tuple[int, int]] = {}
    for q, fb in pairs:
        v, r = q, fb
        while v:
            p = v.bit_length() - 1
            if p not in basis:
                basis[p] = (v, r)
                break
            bv, br = basis[p]
            v ^= bv
            r ^= br
        else:
            if r:
                return None
    taps = 0
    for p in sorted(basis):
        v, r = basis[p]
        rest = v & ~(1 << p) & taps
        taps |= (r ^ (rest.bit_count() & 1)) << p
    ok = all((q & taps).bit_count() & 1 == fb for q, fb in pairs)
    return taps if ok else None


def _maximal(cands: list[Candidate]) -> list[Candidate]:
    """Drop a candidate whose flip-flops are a proper subset of another one of the same kind
    (the low bits of a counter also look like a smaller counter)."""
    sets = [(c.kind, frozenset(c.nets["Q"])) for c in cands]
    return [
        c for c, (kind, q) in zip(cands, sets, strict=True)
        if not any(kind == k2 and q < q2 for k2, q2 in sets)
    ]


class SeqfnDetector:
    name = "seqfn"
    kinds = ("counter", "shift_reg", "lfsr")

    def propose(self, ctx: RoundContext) -> list[Candidate]:
        out: list[Candidate] = []
        for grp in find_groups(ctx):
            out.extend(self._group(ctx, grp))
        return sorted_candidates(_maximal(out))

    def _group(self, ctx: RoundContext, grp: Group) -> list[Candidate]:
        for order in grp.orders:
            cands = self._try(ctx, order)
            if cands:
                return cands
        base = tuple(sorted(grp.ffs))
        order = toggle_order(base, self._table(ctx, base))
        return [] if order in grp.orders else self._try(ctx, order)

    def _try(self, ctx: RoundContext, order: tuple[int, ...]) -> list[Candidate]:
        t = self._table(ctx, order)
        base = _Base(ctx, order, t, classify(t))
        for build in (base.counter, base.shift, base.lfsr):
            cands = build()
            if cands:
                return cands
        return []

    @staticmethod
    def _table(ctx: RoundContext, order: tuple[int, ...]) -> SeqTable:
        q = tuple(ctx.graph.cells[c].outs[0] for c in order)
        return transition_table(ctx.graph, q, ctx.rng(f"seqfn:{min(order)}"))


class _Base:
    """The shared parts of the three candidate builders of one group order."""

    def __init__(
        self, ctx: RoundContext, order: tuple[int, ...], t: SeqTable, labels: dict[int, str]
    ) -> None:
        self.ctx, self.order, self.t, self.labels = ctx, order, t, labels
        g = ctx.graph
        self.k = len(order)
        self.q = t.q
        self.d = tuple(g.cells[c].ins[0] for c in order)
        stop = frozenset(n for p in ctx.view.pieces for n in p.outs)
        cells, _ = cone(g, frozenset(), self.d, stop)
        self.cells = frozenset(cells) | frozenset(order)
        self.table = "exact" if t.exact else "sampled"

    def net(self, j: int | None) -> int:
        return 0 if j is None else self.t.controls[j]

    def counter(self) -> list[Candidate]:
        got = _counter_modes(self.t, self.labels)
        if got is None:
            return []
        label, m = got
        parsed = parse_count(label)
        assert parsed is not None
        direction, modulus, wrap = parsed
        en, rst = self.net(m.en), self.net(m.rst)
        params: dict[str, int | str] = {
            "width": self.k, "dir": direction, "modulus": modulus, "en": en, "rst": rst,
            "rst_value": m.rst_value, "wrap": wrap, "en_active": m.en_active,
            "rst_active": m.rst_active,
        }
        cparams = tuple(sorted((k, v) for k, v in params.items() if k not in ("en", "rst")))
        ins: list[tuple[str, tuple[int, ...]]] = [("Q", self.q)]
        nets: dict[str, tuple[int, ...]] = {"Q": self.q, "D": self.d}
        if en:
            ins.append(("EN", (en,)))
            nets["EN"] = (en,)
        if rst:
            ins.append(("RST", (rst,)))
            nets["RST"] = (rst,)
        modes = len(set(self.labels.values()))
        feats = {"table": self.table, "counter_terms": "1-2" if modes <= 2 else "3+"}
        claim = Claim("counter", cparams, tuple(ins), (("D", self.d),))
        out = [Candidate("counter", self.cells, nets, params, feats, claim)]
        if en and m.en_active == 1 and not rst and direction == "up" and modulus == 0:
            alt = Claim(
                "counter_en", (("A_WIDTH", self.k), ("B_WIDTH", 1), ("Y_WIDTH", self.k)),
                (("A", self.q), ("B", (en,))), (("Y", self.d),),
            )
            out.append(Candidate(
                "counter", self.cells, nets, {**params, "claim": "counter_en"}, feats, alt
            ))
        return out

    def _idle(self, active: set[int]) -> tuple[int, int] | None | bool:
        """``(j, pol)`` of the enable, ``None`` when every control value is active, ``False``
        when the other control values are not all ``hold``."""
        cvals = sorted(self.labels)
        rest = [c for c in cvals if c not in active]
        if not rest:
            return None
        if any(self.labels[c] != "hold" for c in rest):
            return False
        gate = _gate(cvals, active, len(self.t.controls))
        return gate if gate is not None else False

    def shift(self) -> list[Candidate]:
        cvals = sorted(self.labels)
        active = {c for c in cvals if self.labels[c] in ("shift-l", "shift-r")}
        kinds = {self.labels[c] for c in active}
        if not active or len(kinds) != 1:
            return []
        gate = self._idle(active)
        if gate is False:
            return []
        en = gate if isinstance(gate, tuple) else None
        by = rows_by_control(self.t)
        left = kinds == {"shift-l"}
        xs = {}
        for c in active:
            first = by[c][min(by[c])]
            xs[c] = first & 1 if left else _bit(first, self.k - 1)
        xj = None
        for j in range(len(self.t.controls)):
            if (en is None or j != en[0]) and all(_bit(c, j) == xs[c] for c in active):
                xj = j
                break
        if xj is None:
            return []
        x, e = self.net(xj), self.net(None if en is None else en[0])
        active_lvl = 1 if en is None else en[1]
        params: dict[str, int | str] = {
            "width": self.k, "dir": "l" if left else "r", "x": x, "en": e, "en_active": active_lvl,
        }
        ins: list[tuple[str, tuple[int, ...]]] = [("Q", self.q), ("X", (x,))]
        nets: dict[str, tuple[int, ...]] = {"Q": self.q, "D": self.d, "X": (x,)}
        if e:
            ins.append(("EN", (e,)))
            nets["EN"] = (e,)
        cparams = (("dir", params["dir"]), ("en_active", active_lvl), ("width", self.k))
        claim = Claim("shift", cparams, tuple(ins), (("D", self.d),))
        return [Candidate("shift_reg", self.cells, nets, params, {"table": self.table}, claim)]

    def lfsr(self) -> list[Candidate]:
        cvals = sorted(self.labels)
        active = {c for c in cvals if self.labels[c] == "linear"}
        if not active:
            return []
        gate = self._idle(active)
        if gate is False:
            return []
        en = gate if isinstance(gate, tuple) else None
        mask = (1 << self.k) - 1
        by = rows_by_control(self.t)
        pairs: list[tuple[int, int]] = []
        for c in active:
            for qv, nxt in by[c].items():
                if (nxt >> 1) != (qv & (mask >> 1)):
                    return []
                pairs.append((qv, nxt & 1))
        taps = _solve_taps(pairs)
        if not taps:
            return []
        e = self.net(None if en is None else en[0])
        active_lvl = 1 if en is None else en[1]
        params: dict[str, int | str] = {
            "width": self.k, "taps": taps, "en": e, "en_active": active_lvl,
        }
        ins: list[tuple[str, tuple[int, ...]]] = [("Q", self.q)]
        nets: dict[str, tuple[int, ...]] = {"Q": self.q, "D": self.d}
        if e:
            ins.append(("EN", (e,)))
            nets["EN"] = (e,)
        cparams = (("en_active", active_lvl), ("taps", taps), ("width", self.k))
        claim = Claim("lfsr", cparams, tuple(ins), (("D", self.d),))
        return [Candidate("lfsr", self.cells, nets, params, {"table": self.table}, claim)]
