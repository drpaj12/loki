"""L2 Task 9: the global-signal classifier (L2 spec 8.1 and 8.2, spec 4.1)."""

from __future__ import annotations

import json
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from loki.analysis.graphio import Graph, load_graph, to_feature_graph
from loki.analysis.graphlets.signals import (
    CLASS_NAMES,
    SignalConfig,
    SignalInfo,
    classify_signals,
    is_forcing,
    is_hold,
    lut_bits,
    lut_restrict,
)
from loki.blifout import LUT_ROW_ORDER
from loki.features.graph import from_graph_json
from loki.features.roles import classify_nets
from loki.schemas import SCHEMA
from tests.analysis_fixtures import _EMPTY_LABELS, make_graph, make_sync_design, write_graph
from tests.helpers import skip_without

if TYPE_CHECKING:
    import numpy as np

SIGNAL = CLASS_NAMES.index("signal")


def _table(width: int, fn: Callable[[list[int]], int]) -> np.ndarray:
    """``lut_bits`` of the truth table of ``fn``; input ``i`` is bit ``i`` of the address."""
    value = sum(fn([(x >> i) & 1 for i in range(width)]) << x for x in range(1 << width))
    return lut_bits(format(value, "x"), width)


def _load(obj: dict[str, object]) -> Graph:
    """Load a hand-built ``graph.json`` object through the real loader."""
    with tempfile.TemporaryDirectory() as tmp:
        return load_graph(write_graph(Path(tmp), obj))


def _small(
    nodes: list[tuple[str, str, dict[str, int]]], edges: list[tuple[str, str, str]]
) -> Graph:
    """A loaded ``Graph`` from ``(id, kind, feature overrides)`` nodes and ``(src, dst, pin)``."""
    ids = [nid for nid, _kind, _extra in nodes]
    fan_in = dict.fromkeys(ids, 0)
    fan_out = dict.fromkeys(ids, 0)
    for src, dst, _pin in edges:
        fan_out[src] += 1
        fan_in[dst] += 1
    net_of = {nid: f"n{100 + row}" for row, nid in enumerate(ids)}
    entries: list[dict[str, object]] = []
    for nid, node_kind, extra in nodes:
        features: dict[str, object] = {
            "fan_in": fan_in[nid], "fan_out": fan_out[nid], "level": 0, "lut_width": 0,
            "lut_table": "", "is_seq": int(node_kind == "ff"),
            "is_const": int(node_kind == "const"), "hard_ports": 0,
        }
        features.update(extra)
        entries.append({"id": nid, "kind": node_kind, "features": features,
                        "labels": dict(_EMPTY_LABELS)})
    pairs = sorted(edges, key=lambda e: (int(e[0][1:]), int(e[1][1:]), e[2]))
    edge_objs = [{"src": src, "dst": dst, "net": net_of[src], "pin": pin}
                 for src, dst, pin in pairs]
    obj: dict[str, object] = {
        "schema": SCHEMA, "design": "small", "floor": "f2", "nodes": entries, "edges": edge_objs,
    }
    return _load(obj)


def _node(g: Graph, node_id: str) -> int:
    return g.node_ids.index(node_id)


def _out_net(g: Graph, node_id: str) -> str:
    """The net id a node drives (the net of its first out-edge)."""
    row = _node(g, node_id)
    return next(g.net[e] for e in range(g.n_edges) if int(g.src[e]) == row)


def _class(info: SignalInfo, edge: int) -> str:
    return CLASS_NAMES[int(info.edge_class[edge])]


def _net_class(g: Graph, info: SignalInfo, net: str) -> str:
    edges = [e for e in range(g.n_edges) if g.net[e] == net]
    assert edges, f"net {net} has no edges"
    classes = {_class(info, e) for e in edges}
    assert len(classes) == 1, f"net {net} carries several classes: {sorted(classes)}"
    return classes.pop()


@skip_without("numpy")
class SignalsTest(unittest.TestCase):
    def test_lut_convention(self) -> None:
        import numpy as np

        self.assertEqual(LUT_ROW_ORDER, "string_msb_first")
        bits = lut_bits("8", 2)
        self.assertEqual(bits.dtype, np.uint8)
        self.assertEqual(bits.tolist(), [0, 0, 0, 1])
        self.assertEqual(lut_restrict(bits, 2, 0, 0).tolist(), [0, 0])
        self.assertEqual(lut_restrict(bits, 2, 0, 1).tolist(), [0, 1])

    def test_is_forcing_and_hold(self) -> None:
        and2 = lut_bits("8", 2)
        self.assertTrue(is_forcing(and2, 2, 0))
        self.assertTrue(is_forcing(and2, 2, 1))
        mux = _table(3, lambda v: v[0] if v[1] else v[2])  # inputs d, en, q
        self.assertTrue(is_hold(mux, 3, 1, 2))
        self.assertFalse(is_forcing(mux, 3, 1))
        self.assertFalse(is_hold(mux, 3, 0, 2))

    def test_clock_nets_and_domains(self) -> None:
        import numpy as np

        g = _load(make_sync_design(clocks=2))
        info = classify_signals(g)
        self.assertEqual(info.classified["clock"], 2)
        self.assertEqual(info.clock_domains, 2)
        self.assertEqual(info.roles.shape, (g.n_nodes, 4))
        self.assertEqual(info.roles.dtype, np.int64)
        ffs = [row for row in range(g.n_nodes) if g.kind[row] == "ff"]
        self.assertEqual(len(ffs), 20)
        self.assertEqual([int(info.roles[row, 0]) for row in ffs], [1, 2] * 10)
        for row in range(g.n_nodes):
            if g.kind[row] != "ff":
                self.assertEqual(int(info.roles[row, 0]), 0)

    def test_latch_enable_is_not_clock(self) -> None:
        g = _small([("n0", "pi", {}), ("n1", "pi", {}), ("n2", "ff", {})],
                   [("n0", "n2", "EN"), ("n1", "n2", "D")])
        info = classify_signals(g)
        self.assertEqual(info.classified["clock"], 0)
        self.assertEqual(int(info.roles[_node(g, "n2"), 0]), 0)
        self.assertEqual(_net_class(g, info, _out_net(g, "n0")), "signal")

    def test_hard_clock_pin(self) -> None:
        g = _small(
            [("n0", "pi", {}), ("n1", "hard", {"hard_ports": 1}),
             ("n2", "pi", {}), ("n3", "hard", {"hard_ports": 1})],
            [("n0", "n1", "clk"), ("n2", "n3", "data[0]")],
        )
        info = classify_signals(g)
        self.assertEqual(_net_class(g, info, _out_net(g, "n0")), "clock")
        self.assertEqual(int(info.roles[_node(g, "n1"), 0]), 1)
        self.assertEqual(_net_class(g, info, _out_net(g, "n2")), "signal")
        self.assertEqual(int(info.roles[_node(g, "n3"), 0]), 0)

    def test_reset_found(self) -> None:
        g = _load(make_sync_design(reset=True))
        info = classify_signals(g)
        self.assertEqual(info.classified["reset"], 1)
        self.assertEqual(_net_class(g, info, _out_net(g, "n1")), "reset")  # PI rst
        for row, kind in enumerate(g.kind):
            if kind in ("lut", "ff"):
                self.assertEqual(int(info.roles[row, 1]), 1)
        self.assertEqual(int(info.roles[_node(g, "n1"), 1]), 0)

    def test_enable_found(self) -> None:
        g = _load(make_sync_design(enable=True))
        info = classify_signals(g)
        self.assertEqual(info.classified["enable"], 1)
        en_row = _node(g, "n1")  # clk0 is n0, so PI en is n1
        self.assertEqual(g.kind[en_row], "pi")
        self.assertEqual(_net_class(g, info, _out_net(g, "n1")), "enable")
        for row, kind in enumerate(g.kind):
            if kind in ("lut", "ff"):
                self.assertEqual(int(info.roles[row, 3]), 1)

    def test_below_min_fanout_is_signal(self) -> None:
        g = _load(make_sync_design(reset=True, n_ff=5))
        info = classify_signals(g)
        self.assertEqual(info.classified["reset"], 0)
        self.assertEqual(_net_class(g, info, _out_net(g, "n1")), "signal")
        small = classify_signals(g, SignalConfig(min_fanout=2))
        self.assertEqual(small.classified["reset"], 1)
        self.assertEqual(_net_class(g, small, _out_net(g, "n1")), "reset")

    def test_data_net_not_reset(self) -> None:
        g = _load(make_sync_design())
        info = classify_signals(g)
        self.assertEqual(info.classified["reset"], 0)
        for node_id in ("n1", "n2"):  # the two shared data PIs, fan-out 20 each
            self.assertEqual(int(g.num["fan_out"][_node(g, node_id)]), 20)
            self.assertEqual(_net_class(g, info, _out_net(g, node_id)), "signal")

    def test_hard_reset_pin(self) -> None:
        nodes: list[tuple[str, str, dict[str, int]]] = [("n0", "pi", {})]
        edges: list[tuple[str, str, str]] = []
        for i in range(1, 21):
            nodes.append((f"n{i}", "hard", {"hard_ports": 1}))
            edges.append(("n0", f"n{i}", "rst"))
        g = _small(nodes, edges)
        info = classify_signals(g)
        self.assertEqual(info.classified["reset"], 1)
        self.assertEqual(_net_class(g, info, _out_net(g, "n0")), "reset")
        self.assertEqual(int(info.roles[_node(g, "n1"), 1]), 1)

    def test_const_nets(self) -> None:
        g = _load(make_sync_design(n_ff=5, consts=True))
        info = classify_signals(g)
        self.assertEqual(info.classified["const"], 1)
        const_row = _node(g, "n1")  # clk0 is n0, so the const node is n1
        self.assertEqual(g.kind[const_row], "const")
        self.assertEqual(_net_class(g, info, _out_net(g, "n1")), "const")
        for row, kind in enumerate(g.kind):
            if kind == "lut":
                const_in = sum(1 for e in range(g.n_edges)
                               if int(g.dst[e]) == row and g.kind[int(g.src[e])] == "const")
                self.assertEqual(int(info.roles[row, 2]), const_in)
                self.assertGreaterEqual(const_in, 1)

    def test_edge_class_aligned(self) -> None:
        import numpy as np

        g = _load(make_sync_design(reset=True, enable=True, clocks=2))
        info = classify_signals(g)
        self.assertEqual(info.edge_class.shape, (g.n_edges,))
        self.assertEqual(info.edge_class.dtype, np.int8)
        classified = 0
        for net in set(g.net):
            classes = {int(info.edge_class[e]) for e in range(g.n_edges) if g.net[e] == net}
            self.assertEqual(len(classes), 1)
            classified += int(classes.pop() != SIGNAL)
        self.assertGreater(classified, 0)

    def test_no_edges(self) -> None:
        g = _small([("n0", "pi", {}), ("n1", "lut", {}), ("n2", "ff", {})], [])
        info = classify_signals(g)
        self.assertEqual(info.edge_class.shape, (0,))
        self.assertEqual(info.roles.shape, (3, 4))
        self.assertFalse(info.roles.any())
        self.assertEqual(info.clock_domains, 0)
        self.assertEqual(info.classified, dict.fromkeys(CLASS_NAMES, 0))

    def test_to_feature_graph_equals_from_graph_json(self) -> None:
        for obj in (make_sync_design(reset=True, clocks=2), make_graph()):
            with tempfile.TemporaryDirectory() as tmp:
                path = write_graph(Path(tmp), obj)
                g = load_graph(path)
                from_file = from_graph_json(json.loads(path.read_text(encoding="utf-8")))
            self.assertEqual(to_feature_graph(g), from_file)

    def test_classify_signals_delegates(self) -> None:
        g = _load(make_sync_design(reset=True, enable=True, clocks=2))
        info = classify_signals(g)
        fg = to_feature_graph(g)
        expected = classify_nets(fg)
        self.assertEqual(info.classified, expected.classified)
        self.assertEqual(info.clock_domains, expected.clock_domains)
        for e in range(g.n_edges):
            self.assertEqual(CLASS_NAMES[int(info.edge_class[e])],
                             expected.net_class[int(g.net[e][1:])])
        roles = [tuple(int(v) for v in info.roles[row]) for row in range(g.n_nodes)]
        self.assertEqual(roles, [(n.clock_domain, n.has_reset, n.const_inputs, n.enable)
                                 for n in expected.nodes])
