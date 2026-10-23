"""L2 Task 3: regions (cones, node sets, parsing and hashing; L2 spec section 4)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from loki.analysis.graphio import load_graph
from loki.analysis.region import RegionError, cone, from_nodes, parse_region, region_hash
from tests.analysis_fixtures import make_graph, write_graph
from tests.helpers import skip_without

_LABELS = {
    "construct_type": "", "construct_types": "", "n_construct_cells": -1, "module_path": "",
    "bus_name": "", "bit_index": -1, "role": "unknown", "hdl_file": "", "hdl_line": -1,
    "hdl_col": -1, "hdl_end_line": -1, "hdl_end_col": -1, "n_spans": 0,
}


def _node(nid: str, kind: str, fan_in: int, fan_out: int, is_seq: int = 0) -> dict[str, object]:
    return {
        "id": nid,
        "kind": kind,
        "features": {
            "fan_in": fan_in, "fan_out": fan_out, "level": 0, "lut_width": 0, "lut_table": "",
            "is_seq": is_seq, "is_const": 0, "hard_ports": 0,
        },
        "labels": dict(_LABELS),
    }


def _chain_obj() -> dict[str, object]:
    """A valid ``graph.json``: the chain ``a -> b -> c -> d`` with ``b`` a flip-flop."""
    nodes = [
        _node("a", "pi", 0, 1),
        _node("b", "ff", 1, 1, is_seq=1),
        _node("c", "lut", 1, 1),
        _node("d", "po", 1, 0),
    ]
    edges = [
        {"src": "a", "dst": "b", "net": "n4", "pin": "D"},
        {"src": "b", "dst": "c", "net": "n5", "pin": "I0"},
        {"src": "c", "dst": "d", "net": "n6", "pin": "I0"},
    ]
    return {"schema": 1, "design": "chain", "floor": "f2", "nodes": nodes, "edges": edges}


@skip_without("numpy", "scipy")
class RegionTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.chain = load_graph(write_graph(self.dir / "chain", _chain_obj()))
        self.fixture = load_graph(write_graph(self.dir / "fixture", make_graph()))

    def test_cone_in_depth(self) -> None:
        region = cone(self.chain, ["d"], "in", 1)
        self.assertEqual(region.node_ids, ("c", "d"))
        self.assertEqual(region.spec, "cone:d:in:1")
        self.assertEqual(cone(self.chain, ["d"], "in", 2).node_ids, ("b", "c", "d"))
        # From a non-sink node, ``in`` differs from ``both`` (which also reaches ``d``).
        self.assertEqual(cone(self.chain, ["c"], "in", 1).node_ids, ("b", "c"))

    def test_cone_out_all(self) -> None:
        self.assertEqual(cone(self.chain, ["a"], "out", None).node_ids, ("a", "b", "c", "d"))
        self.assertEqual(cone(self.chain, ["b"], "out", None).node_ids, ("b", "c", "d"))
        self.assertEqual(cone(self.chain, ["d"], "out", None).node_ids, ("d",))

    def test_cone_both(self) -> None:
        self.assertEqual(cone(self.chain, ["b"], "both", None).node_ids, ("a", "b", "c", "d"))
        self.assertEqual(cone(self.chain, ["c"], "both", 1).node_ids, ("b", "c", "d"))

    def test_cone_crosses_flipflop(self) -> None:
        self.assertEqual(self.chain.kind[self.chain.index()["b"]], "ff")
        self.assertEqual(cone(self.chain, ["d"], "in", None).node_ids, ("a", "b", "c", "d"))
        self.assertEqual(cone(self.chain, ["a"], "out", None).node_ids, ("a", "b", "c", "d"))

    def test_unknown_root_raises(self) -> None:
        with self.assertRaises(RegionError) as ctx:
            cone(self.chain, ["zz"], "in", None)
        self.assertIn("zz", str(ctx.exception))
        with self.assertRaises(RegionError) as ctx:
            from_nodes(self.chain, ["a", "nope"])
        self.assertIn("nope", str(ctx.exception))

    def test_empty_region_raises(self) -> None:
        with self.assertRaises(RegionError):
            from_nodes(self.chain, [])
        with self.assertRaises(RegionError):
            cone(self.chain, [], "both", None)
        empty = self.dir / "empty.txt"
        empty.write_text("", encoding="utf-8")
        with self.assertRaises(RegionError):
            parse_region(self.chain, f"nodes:{empty}")

    def test_parse_cone_and_nodes_file(self) -> None:
        self.assertEqual(parse_region(self.chain, "cone:d:in:1").node_ids, ("c", "d"))
        self.assertEqual(
            parse_region(self.chain, "cone:a:out:all").node_ids, ("a", "b", "c", "d")
        )
        self.assertEqual(parse_region(self.chain, "cone:a,b:both:0").node_ids, ("a", "b"))
        reversed_order = parse_region(self.chain, "cone:b,a:both:0")
        self.assertEqual(reversed_order.node_ids, ("a", "b"))
        self.assertEqual(reversed_order.spec, "cone:a,b:both:0")
        nodes = self.dir / "ids.txt"
        nodes.write_text("n5\n\nn0\n\nn5\n", encoding="utf-8")
        region = parse_region(self.fixture, f"nodes:{nodes}")
        self.assertEqual(region.node_ids, ("n0", "n5"))
        self.assertEqual(region.spec, "nodes:n0,n5")

    def test_parse_bad_spec(self) -> None:
        bad = (
            "bogus:x",
            "noprefix",
            "cone:a:up:1",
            "cone:a:in:soon",
            "cone:a:in:1:2",
            "cone::in:1",
            "cluster:only.json",
            "cluster:only.json:x",
        )
        for spec in bad:
            with self.subTest(spec=spec), self.assertRaises(RegionError):
                parse_region(self.chain, spec)

    def test_region_hash_stable(self) -> None:
        first = region_hash("cone:a:in:1")
        # sha256("cone:a:in:1") first 8 hex: pins the algorithm, not only stability.
        self.assertEqual(first, "5ffca7ba")
        self.assertEqual(first, region_hash("cone:a:in:1"))
        self.assertRegex(first, r"^[0-9a-f]{8}$")
        self.assertNotEqual(first, region_hash("cone:a:in:2"))
        self.assertEqual(len(region_hash("nodes:a,b")), 8)


if __name__ == "__main__":
    unittest.main()
