"""``arith``: carry chains, adders, subtractors, comparators, constant compares (L1 spec 7.5).

Deviation from the spec text (reported in the plan result): a chain stage can hold several nets
with one support (a sum and a carry net of a ripple adder). Taking every combination is
exponential, so one chain is returned per support sequence: at each stage the first net, by id,
that flips whenever either new source flips (a sum bit), else the first net by id.
"""

from __future__ import annotations

import random
from collections.abc import Sequence

from loki.features.npn import NAMED, NpnClass, npn_class
from loki.re.claims import Claim
from loki.re.detectors import Candidate, RoundContext, k_bin, sorted_candidates
from loki.re.fngraph import FnGraph
from loki.re.sim import cone, simulate
from loki.re.view import View

CONST_SUPPORT_MAX = 16
SENSE_VECTORS = 64
COMPARE_OPS = ("eq", "ne", "lt", "le", "gt", "ge")
Chain = tuple[tuple[int, ...], tuple[tuple[int, int], ...]]
Index = dict[frozenset[int], list[int]]


def _column(i: int, m: int) -> int:
    """Vector over the ``2^m`` patterns whose bit ``x`` is bit ``i`` of ``x``."""
    block = ((1 << (1 << i)) - 1) << (1 << i)
    out = 0
    for x in range(0, 1 << m, 1 << (i + 1)):
        out |= block << x
    return out


def _stop(view: View) -> frozenset[int]:
    return frozenset(n for p in view.pieces for n in p.outs)


def support_index(view: View) -> Index:
    """Nets driven by a free LUT, grouped by (non-None) support of size 2 or more."""
    graph = view.support.graph
    free = set(view.free_cells)
    index: Index = {}
    for net in sorted(graph.driver):
        cid = graph.driver[net]
        if cid not in free or graph.cells[cid].kind != "lut":
            continue
        s = view.support.of(net)
        if s is not None and len(s) >= 2:
            index.setdefault(s, []).append(net)
    return index


def cut_class(graph: FnGraph, inputs: Sequence[int], out: int) -> NpnClass | None:
    """NPN class of ``out`` as a function of ``inputs`` (all patterns); ``None`` when the cone
    has side inputs, repeats an input or has more than six inputs."""
    m = len(inputs)
    if m == 0 or m > 6 or len(set(inputs)) != m:
        return None
    cells, side = cone(graph, frozenset(inputs), [out], frozenset())
    if side:
        return None
    n = 1 << m
    values = {net: _column(i, m) for i, net in enumerate(inputs)}
    table = simulate(graph, cells, values, n).get(out, 0)
    return npn_class(table, m)


def _sensitive(graph: FnGraph, view: View, net: int, pair: tuple[int, int]) -> bool:
    """True when flipping either source of ``pair`` flips ``net`` on every sampled vector."""
    support = view.support.of(net)
    if support is None:
        return False
    cells, _ = cone(graph, frozenset(), [net], _stop(view))
    rng = random.Random(f"arith:{net}")
    mask = (1 << SENSE_VECTORS) - 1
    base = {s: rng.getrandbits(SENSE_VECTORS) for s in sorted(support)}
    ref = simulate(graph, cells, base, SENSE_VECTORS)[net]
    for src in pair:
        flipped = dict(base)
        flipped[src] = ~base[src] & mask
        if (simulate(graph, cells, flipped, SENSE_VECTORS)[net] ^ ref) != mask:
            return False
    return True


def find_chains(view: View, graph: FnGraph, index: Index | None = None) -> list[Chain]:
    """Chains of spec 7.5: output nets and the new source pair of each bit (sorted), one chain
    per support sequence. The pair of bit 0 of a chain whose first support has three sources
    holds the two lowest net ids; the third is the carry-in."""
    idx = support_index(view) if index is None else index
    by_size: dict[int, list[frozenset[int]]] = {}
    for s in sorted(idx, key=sorted):
        by_size.setdefault(len(s), []).append(s)
    paths: list[list[frozenset[int]]] = []

    def extend(path: list[frozenset[int]]) -> None:
        last = path[-1]
        nxt = [t for t in by_size.get(len(last) + 2, ()) if last < t]
        if not nxt:
            if len(path) >= 2:
                paths.append(path)
            return
        for t in nxt:
            extend([*path, t])

    for size in (2, 3):
        for s in by_size.get(size, ()):
            extend([s])
    out: dict[tuple[int, ...], Chain] = {}
    for path in paths:
        pairs: list[tuple[int, int]] = []
        for i, s in enumerate(path):
            new = sorted(s if i == 0 else s - path[i - 1])
            pairs.append((new[0], new[1]))
        ys: list[int] = []
        for s, pair in zip(path, pairs, strict=True):
            nets = idx[s]
            pick = nets[0]
            if len(nets) > 1:
                pick = next((n for n in nets if _sensitive(graph, view, n, pair)), nets[0])
            ys.append(pick)
        out.setdefault(tuple(ys), (tuple(ys), tuple(pairs)))
    return [out[k] for k in sorted(out)]


def carry_nets(view: View, chain: tuple[int, ...], index: Index | None = None) -> dict[int, int]:
    """Bit ``i >= 1`` to a net that is not a chain member and whose support is that of
    ``chain[i - 1]`` (the lowest id when there are several)."""
    idx = support_index(view) if index is None else index
    out: dict[int, int] = {}
    for i in range(1, len(chain)):
        s = view.support.of(chain[i - 1])
        if s is None:
            continue
        found = [n for n in idx.get(s, ()) if n not in chain]
        if found:
            out[i] = found[0]
    return out


def orient(graph: FnGraph, chain: tuple[int, ...], pairs: Sequence[tuple[int, int]]) -> str | None:
    """``"add"``, ``"sub:<bits>"`` (bit ``i`` is ``1`` when ``a_i`` is the larger id of pair
    ``i``) or ``None`` for a mixed or ambiguous chain. Bit ``i`` is read on ``chain[i + 1]``
    with every other source 0; a bit with no following net is free (``0``)."""
    seen: list[str] = []
    for i in range(len(pairs)):
        if i + 1 >= len(chain):
            seen.append("?")
            continue
        p, q = pairs[i]
        cells, _ = cone(graph, frozenset(), [chain[i + 1]], frozenset())
        out = simulate(graph, cells, {p: 0b10, q: 0b01}, 2)[chain[i + 1]]
        first, second = out & 1, (out >> 1) & 1
        if first and second:
            return None
        seen.append("s" if not first and not second else "0" if first else "1")
    known = {c for c in seen if c != "?"}
    if known == {"s"} or not known:
        return "add"
    if "s" in known:
        return None
    return "sub:" + "".join("0" if c == "?" else c for c in seen)


def _share_bin(matched: int, counted: int, hi: str, mid: str, lo: str) -> str:
    if counted == 0:
        return "no_cut"
    if matched == counted:
        return hi
    return mid if 2 * matched >= counted else lo


def _npn_features(
    ctx: RoundContext, chain: Chain, cin: int | None, cout: int | None, index: Index
) -> dict[str, str]:
    ys, pairs = chain
    g = ctx.graph
    carries = carry_nets(ctx.view, ys, index)
    if not carries:
        return {"npn_sum": "no_cut", "npn_carry": "no_cut"}
    k = len(ys)

    def carry_in(bit: int) -> list[int] | None:
        if bit == 0:
            return [] if cin is None else [cin]
        return [carries[bit]] if bit in carries else None

    sum_hit = sum_n = 0
    for i in range(k):
        extra = carry_in(i)
        if extra is None:
            continue
        cut = [*pairs[i], *extra]
        cls = cut_class(g, cut, ys[i])
        if cls is not None:
            sum_n += 1
            sum_hit += cls == NAMED["xor3" if len(cut) == 3 else "xor2"]
    car_hit = car_n = 0
    for j in range(1, k + 1):
        net = carries.get(j) if j < k else cout
        extra = carry_in(j - 1)
        if net is None or extra is None:
            continue
        cut = [*pairs[j - 1], *extra]
        cls = cut_class(g, cut, net)
        if cls is not None:
            car_n += 1
            car_hit += cls == NAMED["maj3" if len(cut) == 3 else "and2"]
    return {
        "npn_sum": _share_bin(sum_hit, sum_n, "all", "half", "low"),
        "npn_carry": _share_bin(car_hit, car_n, "all", "half", "low"),
    }


def _out_reads(graph: FnGraph, nets: Sequence[int]) -> str:
    pos = set(graph.pos)
    for net in nets:
        if net in pos or any(
            graph.cells[c].kind in ("ff", "latch") for c, _ in graph.readers.get(net, ())
        ):
            return "yes"
    return "no"


def _chain_candidate(ctx: RoundContext, chain: Chain, index: Index) -> Candidate | None:
    ys, pairs = chain
    view, g = ctx.view, ctx.graph
    k = len(ys)
    s0 = view.support.of(ys[0])
    s_last = view.support.of(ys[-1])
    if s0 is None or s_last is None:
        return None
    cin = max(s0) if len(s0) == 3 else None
    spare = [n for n in index.get(s_last, ()) if n not in ys]
    cout = spare[0] if spare else None
    outs = (*ys, cout) if cout is not None else ys
    mode = orient(g, outs, pairs)
    if mode is None:
        return None
    params: dict[str, int | str] = {"width": k, "cout": int(cout is not None)}
    nets: dict[str, tuple[int, ...]] = {}
    if mode == "add":
        a = tuple(min(p) for p in pairs)
        b = tuple(max(p) for p in pairs)
        kind = "adder" if cin is None else "adder_cin"
    else:
        if cin is not None:
            return None
        bits = mode[4:]
        a = tuple(p[int(bits[i])] for i, p in enumerate(pairs))
        b = tuple(p[1 - int(bits[i])] for i, p in enumerate(pairs))
        kind = "subtractor"
        params["orient"] = bits
    nets.update({"A": a, "B": b, "Y": outs})
    sized = (("A_WIDTH", k), ("B_WIDTH", k), ("Y_WIDTH", len(outs)))
    inputs = [("A", a), ("B", b)]
    if cin is not None:
        nets["CI"] = (cin,)
        inputs.append(("CI", (cin,)))
    op = "sub" if kind == "subtractor" else "add" if cin is None else "add_cin"
    claim = Claim(op, sized, tuple(inputs), (("Y", outs),))
    cells, _ = cone(g, frozenset(), outs, _stop(view))
    feats = {"width": k_bin(k), "out_reads": _out_reads(g, ys)}
    if ctx.features is not None:
        feats.update(_npn_features(ctx, chain, cin, cout, index))
    return Candidate(kind, frozenset(cells), nets, params, feats, claim)


def _bus_words(ctx: RoundContext) -> list[tuple[int, ...]]:
    words: set[tuple[int, ...]] = set()
    for h in ctx.overlay.by_kind("bus"):
        if h.status == "rejected":
            continue
        slices = sorted((int(n[5:]), ns) for n, ns in h.nets.items()
                        if n.startswith("slice") and n[5:].isdigit() and ns)
        word = tuple(ns[0] for _, ns in slices)
        if len(word) >= 2 and len(set(word)) == len(word):
            words.add(word)
    return sorted(words)


def _comparators(ctx: RoundContext, index: Index) -> list[Candidate]:
    view = ctx.view
    words = _bus_words(ctx)
    out: list[Candidate] = []
    for i, a in enumerate(words):
        for b in words[i + 1:]:
            if len(a) != len(b) or set(a) & set(b):
                continue
            parts = [view.support.of(n) for n in (*a, *b)]
            if any(p is None for p in parts):
                continue
            support = frozenset().union(*(p for p in parts if p is not None))
            for z in index.get(support, ()):
                if z in a or z in b:
                    continue
                out.extend(_compare_cands(ctx, a, b, z))
    return out


def _compare_cands(
    ctx: RoundContext, a: tuple[int, ...], b: tuple[int, ...], z: int
) -> list[Candidate]:
    g = ctx.graph
    cut = frozenset((*a, *b))
    cells, side = cone(g, cut, [z], _stop(ctx.view))
    if side or not cells:
        return []
    k = len(a)
    xor2 = ""
    if ctx.features is not None:
        hits = sum(1 for c in cells if ctx.features.npn_of(c) == NAMED["xor2"])
        xor2 = "yes" if 2 * hits >= k else "no"
    out: list[Candidate] = []
    for pairing, word_b in (("fwd", b), ("rev", b[::-1])):
        for op in COMPARE_OPS:
            claim = Claim(
                op, (("A_WIDTH", k), ("B_WIDTH", k), ("Y_WIDTH", 1)),
                (("A", a), ("B", word_b)), (("Y", (z,)),),
            )
            feats = {"width": k_bin(k), "out_reads": _out_reads(g, (z,))}
            if xor2:
                feats["npn_xor2"] = xor2
            out.append(Candidate(
                "comparator", frozenset(cells), {"A": a, "B": word_b, "Y": (z,)},
                {"op": op, "pairing": pairing, "width": k}, feats, claim,
            ))
    return out


def _eq_consts(ctx: RoundContext, index: Index) -> list[Candidate]:
    g, view = ctx.graph, ctx.view
    out: list[Candidate] = []
    for support, nets in index.items():
        m = len(support)
        if m > CONST_SUPPORT_MAX:
            continue
        srcs = sorted(support)
        for z in nets:
            cells, side = cone(g, frozenset(srcs), [z], _stop(view))
            if side:
                continue
            n = 1 << m
            table = simulate(g, cells, {s: _column(i, m) for i, s in enumerate(srcs)}, n)[z]
            ones = table.bit_count()
            if ones == 1:
                op, c = "eq", table.bit_length() - 1
            elif ones == n - 1:
                op, c = "ne", (~table & ((1 << n) - 1)).bit_length() - 1
            else:
                continue
            claim = Claim(
                "eq_const" if op == "eq" else "ne_const", (("A_WIDTH", m), ("C", c)),
                (("A", tuple(srcs)),), (("Y", (z,)),),
            )
            out.append(Candidate(
                "eq_const", frozenset(cells), {"A": tuple(srcs), "Y": (z,)},
                {"op": op, "C": c, "width": m},
                {"width": k_bin(m), "out_reads": _out_reads(g, (z,))}, claim,
            ))
    return out


class ArithDetector:
    name = "arith"
    kinds = ("adder", "subtractor", "adder_cin", "comparator", "eq_const")

    def propose(self, ctx: RoundContext) -> list[Candidate]:
        index = support_index(ctx.view)
        out: list[Candidate] = []
        for chain in find_chains(ctx.view, ctx.graph, index):
            cand = _chain_candidate(ctx, chain, index)
            if cand is not None:
                out.append(cand)
        out.extend(_comparators(ctx, index))
        out.extend(_eq_consts(ctx, index))
        return sorted_candidates(out)
