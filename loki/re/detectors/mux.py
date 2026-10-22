"""``mux``: mux bits, mux trees and word muxes (L1 spec 7.6).

Deviation from the spec text (reported in the plan result): a word mux over trees (``N > 2``)
carries the claim of its first slice, since a candidate holds one claim; the slices are its
children and are proved individually.
"""

from __future__ import annotations

from dataclasses import dataclass

from loki.features.npn import class_name, npn_class
from loki.re.claims import Claim
from loki.re.detectors import Candidate, RoundContext, k_bin, sorted_candidates
from loki.re.fnfacts import facts
from loki.re.overlay import Hypothesis

_MAX_DEPTH = 8
LONE_FROM_ROUND = 2


@dataclass(frozen=True)
class _Mux:
    cell: int
    sel: tuple[int, ...]
    leaves: tuple[int, ...]
    out: int


@dataclass(frozen=True)
class _Tree:
    root: int
    sel: tuple[int, ...]
    leaves: tuple[int, ...]
    out: int
    cells: frozenset[int]


def mux_class(table: int, width: int) -> str:
    """The NPN class name of a LUT (``other`` when it has no name or too many inputs)."""
    try:
        return class_name(npn_class(table, width))
    except ValueError:
        return "other"


def _mux_cells(ctx: RoundContext) -> dict[int, _Mux]:
    g = ctx.graph
    out: dict[int, _Mux] = {}
    for cid in ctx.view.free_cells:
        c = g.cells[cid]
        if c.kind != "lut" or len(c.outs) != 1 or not c.outs[0]:
            continue
        fact = facts(c.table, c.width).mux
        if fact is None:
            continue
        sel = tuple(c.ins[i] for i in fact.select)
        leaves = tuple(c.ins[i] for i in fact.leaves)
        out[cid] = _Mux(cid, sel, leaves, c.outs[0])
    return out


def _tree_of(
    ctx: RoundContext,
    muxes: dict[int, _Mux],
    cid: int,
    memo: dict[int, _Tree],
    active: frozenset[int],
    pos: frozenset[int],
) -> _Tree:
    if cid in memo:
        return memo[cid]
    m = muxes[cid]
    plain = _Tree(cid, m.sel, m.leaves, m.out, frozenset({cid}))
    subs: list[_Tree] = []
    if len(active) < _MAX_DEPTH:
        for net in m.leaves:
            d = ctx.graph.driver.get(net)
            readers = ctx.graph.readers.get(net, ())
            if (
                d is None
                or d not in muxes
                or d in active
                or d == cid
                or net in pos
                or len(readers) != 1
            ):
                break
            subs.append(_tree_of(ctx, muxes, d, memo, active | {cid}, pos))
        else:
            first = subs[0].sel
            if (
                all(s.sel == first for s in subs)
                and not set(first) & set(m.sel)
                and len({s.root for s in subs}) == len(subs)
            ):
                leaves = tuple(n for s in subs for n in s.leaves)
                cells = frozenset().union(*(s.cells for s in subs)) | {cid}
                plain = _Tree(cid, (*first, *m.sel), leaves, m.out, cells)
    memo[cid] = plain
    return plain


def _trees(ctx: RoundContext, muxes: dict[int, _Mux]) -> list[_Tree]:
    memo: dict[int, _Tree] = {}
    pos = frozenset(ctx.graph.pos)
    found = [_tree_of(ctx, muxes, cid, memo, frozenset(), pos) for cid in sorted(muxes)]
    composed = [t for t in found if len(t.cells) >= 2]
    inner = {c for t in composed for c in t.cells if c != t.root}
    return [t for t in composed if t.root not in inner]


def _live(ctx: RoundContext, kind: str) -> list[Hypothesis]:
    return [h for h in ctx.overlay.by_kind(kind) if h.status != "rejected"]


def _muxn_claim(sel: tuple[int, ...], leaves: tuple[int, ...], out: int) -> Claim:
    return Claim(
        "muxn",
        (("N", len(leaves)), ("S_WIDTH", len(sel))),
        (("D", leaves), ("S", sel)),
        (("Y", (out,)),),
    )


def _bits(ctx: RoundContext, muxes: dict[int, _Mux]) -> list[Candidate]:
    out: list[Candidate] = []
    for cid in sorted(muxes):
        m = muxes[cid]
        feats: dict[str, str] = {}
        if ctx.features is not None:
            cls = ctx.features.npn_of(cid)
            feats["npn_class"] = "other" if cls is None else class_name(cls)
        out.append(
            Candidate(
                "mux_bit",
                frozenset({cid}),
                {"S": m.sel, "D": m.leaves, "Y": (m.out,)},
                {"N": len(m.leaves)},
                feats,
                _muxn_claim(m.sel, m.leaves, m.out),
            )
        )
    return out


def _tree_cands(ctx: RoundContext, muxes: dict[int, _Mux]) -> list[Candidate]:
    bit_ids = {h.cells: h.id for h in _live(ctx, "mux_bit")}
    out: list[Candidate] = []
    for t in _trees(ctx, muxes):
        children = tuple(
            sorted(bit_ids[frozenset({c})] for c in t.cells if frozenset({c}) in bit_ids)
        )
        out.append(
            Candidate(
                "mux_tree",
                t.cells,
                {"S": t.sel, "D": t.leaves, "Y": (t.out,)},
                {"N": len(t.leaves), "S_WIDTH": len(t.sel)},
                {},
                _muxn_claim(t.sel, t.leaves, t.out),
                children,
            )
        )
    return out


def _words(ctx: RoundContext) -> list[Candidate]:
    by_out: dict[int, Hypothesis] = {}
    for kind in ("mux_tree", "mux_bit"):
        for h in _live(ctx, kind):
            y = h.nets.get("Y", ())
            if len(y) == 1:
                by_out.setdefault(y[0], h)
    out: list[Candidate] = []
    for bus in _live(ctx, "bus"):
        slices = sorted(
            (int(n[5:]), ns)
            for n, ns in bus.nets.items()
            if n.startswith("slice") and n[5:].isdigit()
        )
        members = [by_out.get(ns[0]) if len(ns) == 1 else None for _, ns in slices]
        if len(members) < 2 or any(m is None for m in members):
            continue
        hyps = [m for m in members if m is not None]
        sel = hyps[0].nets["S"]
        n = len(hyps[0].nets["D"])
        if any(h.nets["S"] != sel or len(h.nets["D"]) != n for h in hyps):
            continue
        cand = _word(bus, hyps, sel, n)
        if cand is not None:
            out.append(cand)
    if ctx.round >= LONE_FROM_ROUND:
        out.extend(_lone_words(ctx))
    return out


def _lone_words(ctx: RoundContext) -> list[Candidate]:
    """WIDTH 1 words for 2:1 ``mux_bit`` cells that no bus slice and no tree covers."""
    taken: set[int] = set()
    for tree in _live(ctx, "mux_tree"):
        taken |= tree.cells
    for bus in _live(ctx, "bus"):
        for name, nets in bus.nets.items():
            if name.startswith("slice"):
                taken |= {ctx.graph.driver[n] for n in nets if n in ctx.graph.driver}
    out: list[Candidate] = []
    for h in _live(ctx, "mux_bit"):
        if len(h.nets.get("D", ())) != 2 or h.cells & taken:
            continue
        a, b = h.nets["D"]
        sel, y = h.nets["S"], h.nets["Y"]
        claim = Claim("mux2", (("WIDTH", 1),), (("A", (a,)), ("B", (b,)), ("S", sel)), (("Y", y),))
        feats = {"width": "1", "sel_shared": "no", "wl_depth": "n/a"}
        out.append(Candidate(
            "mux", h.cells, {"A": (a,), "B": (b,), "S": sel, "Y": y}, {"WIDTH": 1, "N": 2},
            feats, claim, (h.id,),
        ))
    return out


def _word(
    bus: Hypothesis, hyps: list[Hypothesis], sel: tuple[int, ...], n: int
) -> Candidate | None:
    k = len(hyps)
    ys = tuple(h.nets["Y"][0] for h in hyps)
    feats = {
        "width": k_bin(k),
        "sel_shared": "yes",
        "wl_depth": bus.features.get("wl_depth", "n/a"),
    }
    cells = frozenset().union(*(h.cells for h in hyps))
    children = tuple(h.id for h in hyps)
    params: dict[str, int | str] = {"WIDTH": k, "N": n}
    claim: Claim | None
    if n == 2:
        a = tuple(h.nets["D"][0] for h in hyps)
        b = tuple(h.nets["D"][1] for h in hyps)
        claim = Claim("mux2", (("WIDTH", k),), (("A", a), ("B", b), ("S", sel)), (("Y", ys),))
        nets = {"A": a, "B": b, "S": sel, "Y": ys}
    else:
        claim = hyps[0].claim
        if claim is None:
            return None
        nets = {f"D{v}": tuple(h.nets["D"][v] for h in hyps) for v in range(n)}
        nets.update({"S": sel, "Y": ys})
    return Candidate("mux", cells, nets, params, feats, claim, children)


class MuxDetector:
    name = "mux"
    kinds = ("mux_bit", "mux_tree", "mux")

    def propose(self, ctx: RoundContext) -> list[Candidate]:
        muxes = _mux_cells(ctx)
        out = _bits(ctx, muxes)
        out.extend(_tree_cands(ctx, muxes))
        out.extend(_words(ctx))
        return sorted_candidates(out)
