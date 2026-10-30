"""``fsm``: state machines from flip-flop groups (L1 spec 7.8).

Two sources of evidence: the ``fsm_detect`` pass (``fsm_detect_marks``, its result reaches the
detector through ``RoundContext.fsm_marks``, keyed by the net IDs of the marked wire's bits) and
the bit-level analogue of its rules D-3 to D-5 on level 0.

Deviation from the spec text (reported in the plan result): without a found reset the walk of the
reachable states starts from the state 0. A decoder reads at least two bits of the group.

Encoding kinds (FSM encoding experiment): the target may recode the state register (Odin III and
Yosys make a register of fewer than 32 states one-hot), so the detector speculates which encoding
it sees. ``fsm_onehot``: the states reached from the reset state (a control value that sets the
same next state from every state, else the ``ff_srst`` reset, else any single-bit state) all have
at most one bit set and at least three have exactly one; the bit-to-bit graph (state bit i turns
on state bit j under control values V) is kept. ``fsm_binary``: the reachable state count fits the
bit width tightly (``ceil(log2(states)) == width``). ``fsm``: neither. The walk of every kind
starts from the reset state, never from an all-zero code that is not reset.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from loki.re.detectors import Candidate, RoundContext, bin_count, sorted_candidates
from loki.re.detectors.seqfn import SeqfnDetector, find_groups
from loki.re.fngraph import Cell
from loki.re.overlay import Hypothesis
from loki.re.seqtable import SeqTable, d_nets, onehot_table, reachable, transition_table
from loki.re.sim import cone, simulate

CTRL_EDGES = (0, 1, 5)
CTRL_LABELS = ("0", "1-4", "5+")
ROWS_MAX = 256
SELF_RESET_MAX = 16
DECODER_SUPPORT_MAX = 12
ONEHOT_MIN_STATES = 3
DECODER_EDGES = (0, 1, 2)
DECODER_LABELS = ("0", "1", "2+")
FSM_KINDS = ("fsm", "fsm_onehot", "fsm_binary")


def fsm_detect_marks(working: Any) -> dict[frozenset[int], str]:
    """Wires of the top module of ``working`` that ``fsm_detect`` marked (``fsm_encoding`` set,
    not ``none``), as ``{net IDs of the wire's bits: encoding}``."""
    module = working.top()
    nets = list(module.nets())
    out: dict[frozenset[int], str] = {}
    for wire in module.wires():
        enc = wire.attr("fsm_encoding")
        if enc is None or enc == "none":
            continue
        name = str(wire.name)
        ids = frozenset(
            int(n.id) for n in nets if str(n.name) == name or str(n.name).startswith(name + "[")
        )
        if ids:
            out[ids] = str(enc)
    return out


@dataclass(frozen=True)
class _Decoder:
    cell: int
    net: int
    off: int  # the output value that means "not the matched state"


def _decoder_of(cell: Cell, group: frozenset[int]) -> _Decoder | None:
    """``cell`` as an equality (one on-minterm) or inequality (one off-minterm) of the group
    bits, for some value of its other inputs."""
    if cell.kind != "lut" or len(cell.outs) != 1 or len(set(cell.ins)) != len(cell.ins):
        return None
    if len(cell.ins) > DECODER_SUPPORT_MAX:
        return None
    pos = [i for i, n in enumerate(cell.ins) if n in group]
    rest = [i for i in range(len(cell.ins)) if i not in pos]
    if len(pos) < 2:
        return None
    rows = 1 << len(pos)
    for o in range(1 << len(rest)):
        base = sum(((o >> j) & 1) << i for j, i in enumerate(rest))
        ones = 0
        for y in range(rows):
            x = base | sum(((y >> j) & 1) << i for j, i in enumerate(pos))
            ones += (cell.table >> x) & 1
        if ones == 1:
            return _Decoder(cell.id, cell.outs[0], 0)
        if ones == rows - 1:
            return _Decoder(cell.id, cell.outs[0], 1)
    return None


def _decoders(ctx: RoundContext, q: tuple[int, ...]) -> tuple[list[_Decoder], int]:
    """The decoder readers of the group's Q nets and the number of reader cells."""
    g = ctx.graph
    free = set(ctx.view.free_cells)
    group = frozenset(q)
    readers = sorted({r for n in q for r, _ in g.readers.get(n, ()) if r in free})
    cells = [
        g.cells[r] for r in readers
        if g.cells[r].kind == "lut" and len(g.cells[r].ins) <= DECODER_SUPPORT_MAX
    ]
    decoders = [d for d in (_decoder_of(c, group) for c in cells) if d is not None]
    return decoders, len(cells)


def _self_reset(ctx: RoundContext, q: tuple[int, ...], decoders: list[_Decoder]) -> bool:
    """Rule D-5: with every decoder output forced to its non-matching value, every D net is
    constant."""
    if not decoders:
        return False
    g = ctx.graph
    forced = {d.net: d.off for d in decoders}
    ds = d_nets(g, q)
    cells, side = cone(g, frozenset(forced), ds, frozenset())
    consts = {
        n: g.cells[g.driver[n]].table & 1
        for n in side
        if n in g.driver and g.cells[g.driver[n]].kind == "const"
    }
    variables = sorted(n for n in side if n not in consts)
    if len(variables) > SELF_RESET_MAX:
        return False
    n = 1 << len(variables)
    full = (1 << n) - 1
    values: dict[int, int] = {}
    for i, net in enumerate(variables):
        block = ((1 << (1 << i)) - 1) << (1 << i)
        values[net] = sum(block << x for x in range(0, n, 1 << (i + 1)))
    values.update({net: full if v else 0 for net, v in consts.items()})
    values.update({net: full if off else 0 for net, off in forced.items()})
    nets = simulate(g, cells, values, n)
    return all(nets.get(d, 0) in (0, full) for d in ds)


def _reset(
    ctx: RoundContext, q: tuple[int, ...]
) -> tuple[tuple[int, int], int] | None:
    """``((reset net, active level), reset state)`` when every bit has an ``ff_srst`` hypothesis
    on one common reset net, else None."""
    per_bit: list[dict[tuple[int, int], int]] = []
    srst: list[Hypothesis] = [h for h in ctx.overlay.by_kind("ff_srst") if h.status != "rejected"]
    for net in q:
        found: dict[tuple[int, int], int] = {}
        for h in srst:
            if h.nets.get("q") == (net,) and h.nets.get("rst"):
                key = (h.nets["rst"][0], int(h.params["active"]))
                found.setdefault(key, int(h.params["value"]))
        per_bit.append(found)
    common = set(per_bit[0]).intersection(*per_bit[1:]) if per_bit else set()
    if not common:
        return None
    key = min(common)
    return key, sum(per_bit[i][key] << i for i in range(len(q)))


def _transition_params(t: SeqTable, start: int) -> dict[str, int | str]:
    states, edges = reachable(t, start)
    shown = [[q, c, n] for q, c, n in edges[:ROWS_MAX]]
    return {
        "states": len(states),
        "start": start,
        "rows_n": len(edges),
        "rows": json.dumps(shown, separators=(",", ":")),
    }


def _const_reset(t: SeqTable) -> int | None:
    """The next state shared by every state under one control value (a synchronous reset or
    load); the smallest such control value wins. ``None`` when there is none."""
    by_cv: dict[int, set[int]] = {}
    qs: set[int] = set()
    for (qv, cv), nxt in t.rows.items():
        by_cv.setdefault(cv, set()).add(nxt)
        qs.add(qv)
    if len(qs) < 2:
        return None
    for cv in sorted(by_cv):
        if len(by_cv[cv]) == 1:
            return next(iter(by_cv[cv]))
    return None


@dataclass(frozen=True)
class _OneHot:
    start: int
    states: int
    edges: tuple[tuple[int, int, tuple[int, ...]], ...]
    or_form: str  # "yes", "no" or "n/a"
    reset_const: bool
    table: SeqTable


def _is_single(v: int) -> bool:
    return v != 0 and v & (v - 1) == 0


def _bit_edges(
    t: SeqTable, states: list[int]
) -> tuple[tuple[int, int, tuple[int, ...]], ...]:
    """Bit-to-bit graph: ``(i, j, control values)`` where state bit i set turns state bit j on."""
    conds: dict[tuple[int, int], list[int]] = {}
    for (qv, cv), nxt in sorted(t.rows.items()):
        if _is_single(qv) and qv in states and _is_single(nxt):
            conds.setdefault((qv.bit_length() - 1, nxt.bit_length() - 1), []).append(cv)
    return tuple((i, j, tuple(v)) for (i, j), v in sorted(conds.items()))


def _or_form(t: SeqTable) -> str:
    """Whether the next state of every two-bit state is the OR of the next states of its bits."""
    pairs = [qv for (qv, _) in t.rows if qv.bit_count() == 2]
    if not pairs:
        return "n/a"
    for (qv, cv), nxt in t.rows.items():
        if qv.bit_count() != 2:
            continue
        lo = qv & -qv
        hi = qv ^ lo
        if nxt != (t.rows[(lo, cv)] | t.rows[(hi, cv)]):
            return "no"
    return "yes"


def _onehot(
    ctx: RoundContext, q: tuple[int, ...], reset: tuple[tuple[int, int], int] | None
) -> _OneHot | None:
    """One-hot analysis of the group, or None when its reachable states are not one-hot."""
    k = len(q)
    if k < ONEHOT_MIN_STATES:
        return None
    t = onehot_table(ctx.graph, q, pairs=True)
    if t is None:
        return None
    const = _const_reset(t)
    if const is not None and _is_single(const):
        start, via_const = const, True
    elif reset is not None and _is_single(reset[1]):
        start, via_const = reset[1], False
    else:
        start, via_const = None, False
        best = -1
        for i in range(k):
            n = len(reachable(t, 1 << i)[0])
            if n > best:
                start, best = 1 << i, n
    if start is None:
        return None
    seen, _ = reachable(t, start)
    if any(v.bit_count() > 1 for v in seen):
        return None
    singles = [v for v in seen if _is_single(v)]
    if len(singles) < ONEHOT_MIN_STATES:
        return None
    return _OneHot(start, len(seen), _bit_edges(t, seen), _or_form(t), via_const, t)


def _binary_dense(t: SeqTable, start: int) -> str | None:
    """``partial`` or ``full`` when the reachable state count needs exactly the register width."""
    states, _ = reachable(t, start)
    n, k = len(states), len(t.q)
    if n < ONEHOT_MIN_STATES or (n - 1).bit_length() != k:
        return None
    return "full" if n == 1 << k else "partial"


def _bitgraph_json(edges: tuple[tuple[int, int, tuple[int, ...]], ...]) -> str:
    return json.dumps([[i, j, list(v)] for i, j, v in edges[:ROWS_MAX]], separators=(",", ":"))


class FsmDetector:
    name = "fsm"
    kinds = FSM_KINDS

    def propose(self, ctx: RoundContext) -> list[Candidate]:
        classified = {frozenset(c.nets["Q"]) for c in SeqfnDetector().propose(ctx)}
        out: list[Candidate] = []
        for grp in find_groups(ctx):
            order = tuple(sorted(grp.ffs))
            q = tuple(ctx.graph.cells[c].outs[0] for c in order)
            if grp.scc or frozenset(q) in classified:
                out.append(self._one(ctx, order, q, frozenset(q) in classified))
        return sorted_candidates(out)

    @staticmethod
    def _one(
        ctx: RoundContext, order: tuple[int, ...], q: tuple[int, ...], counter_like: bool
    ) -> Candidate:
        g = ctx.graph
        t = transition_table(g, q, ctx.rng(f"fsm:{min(order)}"))
        ds = d_nets(g, q)
        stop = frozenset(n for p in ctx.view.pieces for n in p.outs)
        cone_cells, _ = cone(g, frozenset(), ds, stop)
        decoders, readers = _decoders(ctx, q)
        reset = _reset(ctx, q)
        feats = {
            "ctrl_inputs": bin_count(len(t.controls), CTRL_EDGES, CTRL_LABELS),
            "decoder_readers": ">=0.5" if readers and 2 * len(decoders) >= readers else "<0.5",
            "counter_like": "yes" if counter_like else "no",
            "self_reset": "yes" if _self_reset(ctx, q, decoders) else "no",
            "reset_found": "yes" if reset is not None else "no",
        }
        marks: Mapping[frozenset[int], str] = ctx.fsm_marks
        if frozenset(q) in marks:
            feats["fsm_detect"] = "marked"
        params: dict[str, int | str] = {"width": len(q)}
        nets: dict[str, tuple[int, ...]] = {"Q": q, "D": tuple(ds)}
        if t.controls:
            nets["C"] = t.controls
        if reset is not None:
            nets["RST"] = (reset[0][0],)
        cells = frozenset(cone_cells) | frozenset(order)
        oh = _onehot(ctx, q, reset)
        if oh is not None:
            return _onehot_candidate(oh, feats, params, nets, cells)
        kind = "fsm"
        if t.exact:
            const = _const_reset(t)
            start = reset[1] if reset is not None else (const if const is not None else 0)
            params.update(_transition_params(t, start))
            dense = _binary_dense(t, start)
            if dense is not None:
                kind = "fsm_binary"
                feats["dense_codes"] = dense
                feats["wide_decoders"] = bin_count(len(decoders), DECODER_EDGES, DECODER_LABELS)
        return Candidate(kind, cells, nets, params, feats)


def _onehot_candidate(
    oh: _OneHot, feats: dict[str, str],
    params: dict[str, int | str], nets: dict[str, tuple[int, ...]], cells: frozenset[int],
) -> Candidate:
    t = oh.table
    del feats["decoder_readers"]
    feats["onehot_closed"] = "yes"
    feats["reset_const"] = "yes" if oh.reset_const else "no"
    if oh.or_form != "n/a":
        feats["onehot_or_form"] = oh.or_form
    params.update(_transition_params(t, oh.start))
    params["bitgraph"] = _bitgraph_json(oh.edges)
    if t.controls:
        nets["C"] = t.controls
    return Candidate("fsm_onehot", cells, nets, params, feats)
