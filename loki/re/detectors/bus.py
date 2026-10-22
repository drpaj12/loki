"""``bus``: k isomorphic slices sharing a control (L1 spec 7.4)."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass

from loki.re.detectors import (
    Candidate,
    RoundContext,
    bin_count,
    k_bin,
    params_json,
    sorted_candidates,
)
from loki.re.fnfacts import npn_sig

WL_EDGES = (0, 1, 2, 4)
WL_LABELS = ("0", "1", "2-3", "4")
_CHAIN_KINDS = ("adder", "subtractor", "adder_cin", "counter", "shift_reg", "lfsr")
_CHAIN_NETS = ("Y", "Q")


@dataclass(frozen=True)
class _Slice:
    key: Hashable
    cells: frozenset[int]
    ins: frozenset[int]
    outs: tuple[int, ...]
    cell: int  # the level-0 cell of a leaf slice, 0 for a piece


def _slices(ctx: RoundContext) -> list[_Slice]:
    g = ctx.graph
    out: list[_Slice] = []
    for cid in ctx.view.free_cells:
        c = g.cells[cid]
        ins = frozenset(n for n in c.ins if n)
        if c.kind != "lut" or not ins:
            continue
        if ctx.features is not None:
            key: Hashable = ("lut", ctx.features.colour(cid, "npn/in", 0))
        else:
            key = ("lut", npn_sig(c.table, c.width), len(c.ins))
        out.append(_Slice(key, frozenset({cid}), ins, c.outs, cid))
    for p in ctx.view.pieces:
        ins = frozenset(n for n in p.ins if n)
        if ins:
            key = ("piece", p.kind, params_json(ctx.overlay.get(p.hid).params))
            out.append(_Slice(key, p.cells, ins, p.outs, 0))
    return out


def _chain_position(ctx: RoundContext, members: list[_Slice]) -> dict[int, int] | None:
    """Slice index by chain order when one arith or seqfn hypothesis lists every slice output."""
    firsts = [s.outs[0] for s in members if s.outs]
    if len(firsts) != len(members):
        return None
    for kind in _CHAIN_KINDS:
        for h in ctx.overlay.by_kind(kind):
            if h.status == "rejected":
                continue
            for key in _CHAIN_NETS:
                order = h.nets.get(key, ())
                pos = {n: i for i, n in enumerate(order)}
                if all(n in pos for n in firsts):
                    return {i: pos[n] for i, n in enumerate(firsts)}
    return None


def _bus_nets(ctx: RoundContext) -> set[int]:
    nets: set[int] = set()
    for h in ctx.overlay.by_kind("bus"):
        if h.status != "rejected":
            for name, ns in h.nets.items():
                if name.startswith("slice"):
                    nets.update(ns)
    return nets


def _fanout_exact(ctx: RoundContext, controls: frozenset[int], members: list[_Slice]) -> str:
    cells = frozenset().union(*(m.cells for m in members))
    pos = set(ctx.graph.pos)
    for net in controls:
        if net in pos or any(r not in cells for r, _ in ctx.graph.readers.get(net, ())):
            return "no"
    return "yes"


def _wl_depth(ctx: RoundContext, members: list[_Slice]) -> str:
    if ctx.features is None or any(m.cell == 0 for m in members):
        return "n/a"
    depth = ctx.features.class_depth([m.cell for m in members], "npn/in")
    return bin_count(max(depth, 0), WL_EDGES, WL_LABELS)


class BusDetector:
    name = "bus"
    kinds = ("bus",)

    def propose(self, ctx: RoundContext) -> list[Candidate]:
        groups: dict[Hashable, list[_Slice]] = {}
        for s in _slices(ctx):
            groups.setdefault(s.key, []).append(s)
        known = _bus_nets(ctx)
        seen: set[frozenset[int]] = set()
        out: list[Candidate] = []
        for key in sorted(groups, key=repr):
            group = groups[key]
            readers: dict[int, list[int]] = {}
            for i, s in enumerate(group):
                for n in s.ins:
                    readers.setdefault(n, []).append(i)
            for net in sorted(readers):
                idx = frozenset(readers[net])
                if len(idx) < 2 or idx in seen:
                    continue
                seen.add(idx)
                cand = self._bus(ctx, [group[i] for i in sorted(idx)], known)
                if cand is not None:
                    out.append(cand)
        return sorted_candidates(out)

    @staticmethod
    def _bus(ctx: RoundContext, members: list[_Slice], known: set[int]) -> Candidate | None:
        controls = frozenset.intersection(*(m.ins for m in members))
        data = [m.ins - controls for m in members]
        if any(not d for d in data) or sum(len(d) for d in data) != len(frozenset().union(*data)):
            return None
        chain = _chain_position(ctx, members)
        if chain is not None:
            order = sorted(range(len(members)), key=lambda i: chain[i])
            source = "chain"
        else:
            order = sorted(range(len(members)), key=lambda i: (min(data[i]), i))
            source = "net_id"
        ordered = [members[i] for i in order]
        flat = frozenset().union(*data)
        hit = len(flat & known)
        nets: dict[str, tuple[int, ...]] = {f"slice{i}": s.outs for i, s in enumerate(ordered)}
        nets["ctrl"] = tuple(sorted(controls))
        feats = {
            "k": k_bin(len(members)),
            "ctrl_fanout_exact": _fanout_exact(ctx, controls, members),
            "data_from_bus": "none" if hit == 0 else ("all" if hit == len(flat) else "some"),
            "wl_depth": _wl_depth(ctx, members),
        }
        return Candidate(
            "bus", frozenset().union(*(m.cells for m in members)), nets,
            {"k": len(members), "order_source": source}, feats,
        )
