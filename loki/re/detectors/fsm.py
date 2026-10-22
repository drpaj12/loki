"""``fsm``: state machines from flip-flop groups (L1 spec 7.8).

Two sources of evidence: the ``fsm_detect`` pass (``fsm_detect_marks``, its result reaches the
detector through ``RoundContext.fsm_marks``, keyed by the net IDs of the marked wire's bits) and
the bit-level analogue of its rules D-3 to D-5 on level 0.

Deviation from the spec text (reported in the plan result): without a found reset the walk of the
reachable states starts from the state 0. A decoder reads at least two bits of the group.
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
from loki.re.seqtable import SeqTable, d_nets, reachable, transition_table
from loki.re.sim import cone, simulate

CTRL_EDGES = (0, 1, 5)
CTRL_LABELS = ("0", "1-4", "5+")
ROWS_MAX = 256
SELF_RESET_MAX = 16
DECODER_SUPPORT_MAX = 12


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


class FsmDetector:
    name = "fsm"
    kinds = ("fsm",)

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
        if t.exact:
            params.update(_transition_params(t, 0 if reset is None else reset[1]))
        nets: dict[str, tuple[int, ...]] = {"Q": q, "D": tuple(ds)}
        if t.controls:
            nets["C"] = t.controls
        if reset is not None:
            nets["RST"] = (reset[0][0],)
        return Candidate("fsm", frozenset(cone_cells) | frozenset(order), nets, params, feats)
