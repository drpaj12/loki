"""Structural features in L1: the feature graph of level 0, colours and NPN classes per cell,
and proof transfer across a colour class (L1 spec 6.7 and 8.1)."""

from __future__ import annotations

import contextlib
import json
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loki.features import WL_ROUNDS
from loki.features.graph import FeatureGraph, make_feature_graph
from loki.features.npn import NpnClass, npn_class, transforms
from loki.features.roles import NetRoles, classify_nets
from loki.features.wl import WLConfig, WLResult, refine
from loki.re.bayes import CALIB_WL_DEPTH, TRANSFER_ROUND
from loki.re.claims import Claim
from loki.re.fngraph import Cell, FnGraph
from loki.re.sim import cone

if TYPE_CHECKING:
    from loki.re.overlay import Hypothesis

VARIANTS = (WLConfig("table", "in"), WLConfig("npn", "in"), WLConfig("npn", "both"))


def _pins(cell: Cell) -> list[tuple[str, int]]:
    """``(sink pin name, net)`` for every connected input of a cell, as in L0 spec 6.4."""
    if cell.kind == "lut":
        pins = [(f"I{k}", net) for k, net in enumerate(cell.ins)]
    elif cell.kind in ("ff", "latch"):
        pins = [("D" if k == 0 else f"I{k}", net) for k, net in enumerate(cell.ins)]
        pins.append(("CLK" if cell.kind == "ff" else "EN", cell.clock))
    elif cell.kind == "hard":
        named = len(cell.in_pins) == len(cell.ins)
        pins = [(cell.in_pins[k] if named else f"I{k}", net) for k, net in enumerate(cell.ins)]
    else:
        pins = []
    return [(pin, net) for pin, net in pins if net]


def feature_graph(graph: FnGraph) -> FeatureGraph:
    """Level 0 as a feature graph: one node per cell (id ``graph.label``), then one ``pi:<net>``
    node per input net and one ``po:<net>`` node per output net; edges driver to sink pin.

    ``type`` is the cell kind, except for hard cells (their Odin III type), and only LUTs have a
    table (a constant's value is not kept): L0's ``graph.json`` keeps no constant values."""
    nodes: list[tuple[str, str, str, int, int]] = []
    index: dict[int, int] = {}
    for cid in sorted(graph.cells):
        c = graph.cells[cid]
        index[cid] = len(nodes)
        nodes.append((graph.label(cid), c.kind, c.type if c.kind == "hard" else c.kind,
                      c.width if c.kind == "lut" else 0, c.table if c.kind == "lut" else -1))

    def name(net: int) -> str:
        return graph.names.get(net, f"n{net}")

    pi_node: dict[int, int] = {}
    for net in graph.pis:
        if net not in pi_node:
            pi_node[net] = len(nodes)
            nodes.append((f"pi:{name(net)}", "pi", "pi", 0, -1))
    po_node: dict[int, int] = {}
    for net in graph.pos:
        if net not in po_node:
            po_node[net] = len(nodes)
            nodes.append((f"po:{name(net)}", "po", "po", 0, -1))

    def driver(net: int) -> int | None:
        d = graph.driver.get(net)
        return index[d] if d is not None else pi_node.get(net)

    edges: list[tuple[int, int, str, int]] = []
    for cid in sorted(graph.cells):
        for pin, net in _pins(graph.cells[cid]):
            src = driver(net)
            if src is not None:
                edges.append((src, index[cid], pin, net))
    for net, node in po_node.items():
        src = driver(net)
        if src is not None:
            edges.append((src, node, "I", net))
    return make_feature_graph(nodes, edges)


@dataclass(frozen=True)
class StructFeatures:
    """Features of level 0, computed once per run (spec 6.7)."""

    fg: FeatureGraph
    index: dict[int, int]
    roles: NetRoles
    wl: dict[str, WLResult]
    npn: dict[int, NpnClass]
    seconds: float

    def colour(self, cell: int, variant: str, r: int) -> str:
        """Colour of ``cell`` in round ``r`` of ``variant`` (``table/in``, ``npn/in``,
        ``npn/both``)."""
        return self.wl[variant].colours[r][self.index[cell]]

    def npn_of(self, cell: int) -> NpnClass | None:
        """NPN class of a LUT cell (None for other cells and for supports above 6 inputs)."""
        return self.npn.get(cell)

    def cell_keys(self, cell: int) -> tuple[str, ...]:
        """Calibration keys ``"<d>:<colour>"`` of ``npn/both``, deepest first (spec 6.7 item 1)."""
        if cell not in self.index:
            return ()
        return tuple(f"{d}:{self.colour(cell, 'npn/both', d)}"
                     for d in range(CALIB_WL_DEPTH, -1, -1))

    def class_depth(self, cells: Sequence[int], variant: str) -> int:
        """The deepest round at which all ``cells`` share one colour (-1: not even at round 0)."""
        depth = -1
        for r in range(len(self.wl[variant].colours)):
            if len({self.colour(c, variant, r) for c in cells}) != 1:
                break
            depth = r
        return depth

    def report(self) -> dict[str, object]:
        """The ``features`` block of ``report.json`` without the transfer counts (spec 11)."""
        wl: dict[str, object] = {
            name: {"stable_round": res.stable_round,
                   "classes": [len(set(colours)) for colours in res.colours]}
            for name, res in sorted(self.wl.items())
        }
        tables = {(self.fg.width[self.index[c]], self.fg.table[self.index[c]]) for c in self.npn}
        npn: dict[str, object] = {
            "distinct_tables": len(tables),
            "classes": len({k.key for k in self.npn.values()}),
            "exact": all(k.exact for k in self.npn.values()),
            "worst_enum": max((transforms(t, w) for w, t in tables), default=0),
        }
        return {"enabled": True, "wl": wl, "npn": npn}


def build_features(graph: FnGraph, rounds: int = WL_ROUNDS) -> StructFeatures:
    """``feature_graph``, role flags, the three colour variants and the NPN class of every LUT."""
    start = time.monotonic()
    fg = feature_graph(graph)
    roles = classify_nets(fg)
    wl = {}
    for cfg in VARIANTS:
        run = WLConfig(cfg.start, cfg.direction, rounds)
        wl[run.name] = refine(fg, roles, run)
    index = {cid: i for i, cid in enumerate(sorted(graph.cells))}
    npn: dict[int, NpnClass] = {}
    for cid, c in graph.cells.items():
        if c.kind == "lut":
            with contextlib.suppress(ValueError):
                npn[cid] = npn_class(c.table, c.width)
    return StructFeatures(fg, index, roles, wl, npn, time.monotonic() - start)


def cone_match(graph: FnGraph, c0: Claim, c: Claim) -> bool:
    """True when the level-0 cones of ``c0`` and ``c`` are isomorphic, keeping pin order, cell
    kind, width and exact table, with the claims' ports bound alike (spec 8.1)."""
    if c0.op != c.op or c0.params != c.params:
        return False
    if [(p, len(ns)) for p, ns in c0.inputs] != [(p, len(ns)) for p, ns in c.inputs]:
        return False
    if [(p, len(ns)) for p, ns in c0.outputs] != [(p, len(ns)) for p, ns in c.outputs]:
        return False
    fwd: dict[int, int] = {}
    back: dict[int, int] = {}
    todo: list[int] = []

    def pair(a: int, b: int) -> bool:
        if (a == 0) != (b == 0):
            return False
        if a == 0:
            return True
        if a in fwd or b in back:
            return fwd.get(a) == b and back.get(b) == a
        fwd[a], back[b] = b, a
        todo.append(a)
        return True

    ins0 = frozenset(n for _, ns in c0.inputs for n in ns)
    ins1 = frozenset(n for _, ns in c.inputs for n in ns)
    cells0, side0 = cone(graph, ins0, [n for _, ns in c0.outputs for n in ns], frozenset())
    cells1, side1 = cone(graph, ins1, [n for _, ns in c.outputs for n in ns], frozenset())
    if side0 or side1 or len(cells0) != len(cells1):
        return False
    for (_, ns0), (_, ns1) in zip((*c0.inputs, *c0.outputs), (*c.inputs, *c.outputs), strict=True):
        if not all(pair(a, b) for a, b in zip(ns0, ns1, strict=True)):
            return False
    matched = 0
    while todo:
        a = todo.pop()
        b = fwd[a]
        if (a in ins0) != (b in ins1):
            return False
        if a in ins0:
            continue
        da, db = graph.driver.get(a), graph.driver.get(b)
        if da is None or db is None:
            return False
        ca, cb = graph.cells[da], graph.cells[db]
        if (ca.kind, ca.width, ca.table, len(ca.ins)) != (cb.kind, cb.width, cb.table,
                                                          len(cb.ins)):
            return False
        matched += 1
        if not all(pair(x, y) for x, y in zip(ca.ins, cb.ins, strict=True)):
            return False
    return matched == len(cells0)


def transfer_key(h: Hypothesis, sf: StructFeatures, graph: FnGraph) -> tuple[str, ...] | None:
    """The group key of spec 8.1: kind, claim op, canonical claim params, and the ``table/in``
    colour at round ``TRANSFER_ROUND`` of the driver of every claim output net (None without a
    claim)."""
    claim = h.claim
    if claim is None:
        return None
    r = min(TRANSFER_ROUND, len(sf.wl["table/in"].colours) - 1)
    colours = []
    for _, nets in claim.outputs:
        for net in nets:
            d = graph.driver.get(net)
            colours.append(sf.colour(d, "table/in", r) if d is not None and d in sf.index else "-")
    params = json.dumps(dict(sorted(claim.params)), separators=(",", ":"))
    return (h.kind, claim.op, params, *colours)
