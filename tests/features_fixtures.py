"""Hand-built and synthetic feature graphs for the ``loki.features`` tests."""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence

from loki.features.graph import FeatureGraph, make_feature_graph

XOR2, AND2, XOR3, MAJ3 = 0b0110, 0b1000, 0b10010110, 0b11101000


def table_of(width: int, fn: Callable[[Sequence[int]], int]) -> int:
    """Truth table of ``fn`` over ``width`` inputs (input ``i`` is bit ``i`` of the pattern)."""
    return sum(fn([(x >> i) & 1 for i in range(width)]) << x for x in range(1 << width))


class Builder:
    """Collects nodes and edges; every node drives one net numbered like its index."""

    def __init__(self) -> None:
        self.nodes: list[tuple[str, str, str, int, int]] = []
        self.edges: list[tuple[int, int, str, int]] = []

    def node(self, nid: str, kind: str, width: int = 0, table: int = -1, type_: str = "") -> int:
        self.nodes.append((nid, kind, type_ or kind, width, table))
        return len(self.nodes) - 1

    def lut(self, nid: str, table: int, ins: Sequence[int]) -> int:
        v = self.node(nid, "lut", len(ins), table)
        for k, u in enumerate(ins):
            self.edges.append((u, v, f"I{k}", u))
        return v

    def edge(self, src: int, dst: int, pin: str) -> None:
        self.edges.append((src, dst, pin, src))

    def build(self) -> FeatureGraph:
        return make_feature_graph(self.nodes, self.edges)


def ripple_adder_fg(bits: int, carry_nets: bool = True, prefix: str = "") -> FeatureGraph:
    """``bits`` full adders; with ``carry_nets`` False each carry-in is its own input."""
    b = Builder()
    carry = b.node(f"{prefix}cin", "pi")
    for i in range(bits):
        a = b.node(f"{prefix}a{i}", "pi")
        c = b.node(f"{prefix}b{i}", "pi")
        s = b.lut(f"{prefix}s{i}", XOR3, [a, c, carry])
        nxt = b.lut(f"{prefix}c{i}", MAJ3, [a, c, carry])
        po = b.node(f"{prefix}po_s{i}", "po")
        b.edge(s, po, "I")
        carry = nxt if carry_nets else b.node(f"{prefix}cin{i + 1}", "pi")
    po = b.node(f"{prefix}po_cout", "po")
    b.edge(carry, po, "I")
    return b.build()


def relabelled(fg: FeatureGraph, seed: int) -> tuple[FeatureGraph, list[int]]:
    """``fg`` with its nodes shuffled and renamed; also the new index of each old node."""
    order = list(range(fg.n_nodes))
    random.Random(f"relabel:{seed}").shuffle(order)
    new_of = [0] * fg.n_nodes
    for new, old in enumerate(order):
        new_of[old] = new
    nodes = [(f"z{new}", fg.kind[old], fg.type[old], fg.width[old], fg.table[old])
             for new, old in enumerate(order)]
    edges = [(new_of[fg.src[e]], new_of[fg.dst[e]], fg.pin[e], fg.net[e] + 1000)
             for e in range(fg.n_edges)]
    return make_feature_graph(nodes, edges), new_of


def random_fg(n: int, seed: int) -> FeatureGraph:
    """A small random graph (cycles, parallel edges and constants allowed) for equivalence tests."""
    rng = random.Random(f"random:{seed}")
    b = Builder()
    for i in range(n):
        kind = rng.choice(["pi", "lut", "lut", "lut", "ff", "po", "const"])
        if kind == "lut":
            w = rng.randint(1, 2)
            b.node(f"v{i}", "lut", w, rng.choice([0b10, 0b0110]) if w == 1 else AND2)
        elif kind == "const":
            b.node(f"v{i}", "const", 0, rng.randint(0, 1))
        else:
            b.node(f"v{i}", kind)
    for _ in range(rng.randint(n // 2, 2 * n)):
        s, d = rng.randrange(n), rng.randrange(n)
        pin = {"lut": f"I{rng.randint(0, 1)}", "ff": rng.choice(["D", "CLK"]), "po": "I"}.get(
            b.nodes[d][1], "I0")
        b.edge(s, d, pin)
    return b.build()


def reconvergent_pair_fg() -> FeatureGraph:
    """LUT2 ``g`` reading ``(x, x)`` and an equal LUT2 reading ``(y, z)``; ``x y z`` are PIs."""
    b = Builder()
    x, y, z = (b.node(n, "pi") for n in ("x", "y", "z"))
    g1 = b.lut("g1", XOR2, [x, x])
    g2 = b.lut("g2", XOR2, [y, z])
    for name, g in (("po1", g1), ("po2", g2)):
        b.edge(g, b.node(name, "po"), "I")
    return b.build()


def sync_fg(
    n_ff: int, reset: bool = False, enable: bool = False, clocks: int = 1,
    rst_from_lut: bool = False,
) -> FeatureGraph:
    """``n_ff`` flip-flops, each fed by one D-LUT; PIs ``clk<i>``, ``rst``, ``en`` and ``d<i>``.

    Plain: the D-LUT is a buffer. Reset: ``d & ~rst``. Enable: ``en ? d : q``. Both: one LUT4
    ``rst ? 0 : (en ? d : q)`` (the enable is then not a hold path, L2 spec 8.1). With
    ``rst_from_lut`` the reset is an XOR of two inputs instead of an input."""
    b = Builder()
    clks = [b.node(f"clk{i}", "pi") for i in range(clocks)]
    if reset and rst_from_lut:
        rst = b.lut("rst", XOR2, [b.node("r0", "pi"), b.node("r1", "pi")])
    else:
        rst = b.node("rst", "pi") if reset else -1
    en = b.node("en", "pi") if enable else -1
    for i in range(n_ff):
        d = b.node(f"d{i}", "pi")
        ff = b.node(f"ff{i}", "ff", type_="$_DFF_P_")
        ins = [d]
        if enable:
            ins.append(en)
            ins.append(ff)
        if reset:
            ins.append(rst)
        if enable and reset:
            tab = table_of(4, lambda v: 0 if v[3] else (v[0] if v[1] else v[2]))
        elif enable:
            tab = table_of(3, lambda v: v[0] if v[1] else v[2])
        elif reset:
            tab = table_of(2, lambda v: v[0] & (1 - v[1]))
        else:
            tab = table_of(1, lambda v: v[0])
        lut = b.lut(f"dl{i}", tab, ins)
        b.edge(lut, ff, "D")
        b.edge(clks[i % clocks], ff, "CLK")
        b.edge(ff, b.node(f"q{i}", "po"), "I")
    return b.build()


def synthetic_netlist(n: int, seed: int) -> FeatureGraph:
    """A netlist-like graph of about ``n`` nodes: LUT2 to LUT6, 10 % flip-flops on one clock,
    a reset of fan-out up to 1000, about 3 edges per node."""
    rng = random.Random(f"features:{seed}")
    b = Builder()
    clk = b.node("clk", "pi")
    rst = b.node("rst", "pi")
    pis = [b.node(f"i{k}", "pi") for k in range(max(8, n // 50))]
    pool = list(pis)
    common = {
        w: [table_of(w, f) for f in (
            lambda v: int(all(v)), lambda v: int(any(v)), lambda v: sum(v) & 1,
            lambda v: int(not all(v)), lambda v: int(sum(v) * 2 > len(v)))]
        for w in range(2, 7)
    }
    widths = [2, 3, 4, 5, 6]
    weights = [35, 30, 20, 10, 5]
    reset_left = 1000
    count = 0
    while len(b.nodes) < n:
        window = pool[-2000:]
        if rng.random() < 0.10:
            with_reset = reset_left > 0
            ins = [rng.choice(window)] + ([rst] if with_reset else [])
            reset_left -= int(with_reset)
            tab = table_of(2, lambda v: v[0] & (1 - v[1])) if with_reset else 0b10
            d = b.lut(f"l{count}", tab, ins)
            ff = b.node(f"f{count}", "ff", type_="$_DFF_P_")
            b.edge(d, ff, "D")
            b.edge(clk, ff, "CLK")
            pool.append(ff)
        else:
            w = rng.choices(widths, weights)[0]
            tab = rng.choice(common[w]) if rng.random() < 0.7 else rng.getrandbits(1 << w)
            pool.append(b.lut(f"l{count}", tab, [rng.choice(window) for _ in range(w)]))
        count += 1
    for k, v in enumerate(pool[-20:]):
        b.edge(v, b.node(f"o{k}", "po"), "I")
    return b.build()
