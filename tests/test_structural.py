"""L2 Task 10a: structural features (WL colours, NPN classes, GSN blocks; L2 spec 4.1)."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from loki.analysis.graphio import Graph, load_graph, to_feature_graph
from loki.analysis.graphlets import gsn_features
from loki.analysis.structural import (
    compute_structural,
    hash64,
    load_structural,
    run_structural,
)
from loki.features import WL_ROUNDS
from loki.features.graph import from_graph_json
from tests.analysis_fixtures import make_graph, write_graph
from tests.helpers import skip_without

_JSON_KEYS = {
    "schema", "kind", "design", "floor", "variant", "rounds", "stable_round",
    "classes_per_round", "npn", "npn_keys", "colours", "quotient", "graph_sha256", "seconds",
    "versions",
}
_NPN_KEYS = {"distinct_tables", "classes", "exact", "worst_enum"}


def _graph(root: Path, n_lut: int = 12, design: str = "d") -> Graph:
    """Load the fixture graph written under ``root``."""
    return load_graph(write_graph(root, make_graph(n_lut=n_lut, design=design)))


@skip_without("numpy")
class StructuralTest(unittest.TestCase):
    """The eight tests of plan Task 10a step 1."""

    def test_hash64(self) -> None:
        """The empty string is 0; anything else is the signed first 8 bytes of its SHA-256."""
        self.assertEqual(hash64(""), 0)
        expected = int.from_bytes(hashlib.sha256(b"4:6996").digest()[:8], "big", signed=True)
        self.assertEqual(hash64("4:6996"), expected)
        other = int.from_bytes(hashlib.sha256(b"npn/both").digest()[:8], "big", signed=True)
        self.assertEqual(hash64("npn/both"), other)

    def test_adapter_equals_from_graph_json(self) -> None:
        """L2's adapter and L1's reader build the same feature graph from one file."""
        with tempfile.TemporaryDirectory() as tmp:
            path = write_graph(Path(tmp), make_graph())
            graph = load_graph(path)
            obj = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(to_feature_graph(graph), from_graph_json(obj))

    def test_wl_ids_match_colours(self) -> None:
        """Every WL id is the hash64 of the colour string behind it (spec 4.1)."""
        import numpy as np

        with tempfile.TemporaryDirectory() as tmp:
            graph = _graph(Path(tmp))
        structural = compute_structural(graph)
        self.assertEqual(structural.variant, "npn/both")
        self.assertEqual(structural.wl.dtype, np.int64)
        self.assertEqual(structural.wl.shape, (graph.n_nodes, WL_ROUNDS + 1))
        self.assertEqual(len(structural.colours), WL_ROUNDS + 1)
        for round_index, colours in enumerate(structural.colours):
            self.assertEqual(len(colours), graph.n_nodes)
            for row, colour in enumerate(colours):
                self.assertEqual(
                    int(structural.wl[row, round_index]), hash64(colour),
                    f"round {round_index} node {row}",
                )
        self.assertEqual(structural.roles.shape, (graph.n_nodes, 4))

    def test_npn_keys_luts_only(self) -> None:
        """LUT nodes carry a class key and its id; nodes without a table carry ``""`` and 0."""
        import numpy as np

        with tempfile.TemporaryDirectory() as tmp:
            graph = _graph(Path(tmp))
        structural = compute_structural(graph)
        self.assertEqual(structural.npn.dtype, np.int64)
        self.assertEqual(structural.npn.shape, (graph.n_nodes,))
        self.assertEqual(len(structural.npn_keys), graph.n_nodes)
        for row, kind in enumerate(graph.kind):
            if kind == "lut":
                self.assertNotEqual(structural.npn_keys[row], "")
                self.assertEqual(int(structural.npn[row]), hash64(structural.npn_keys[row]))
            else:
                self.assertEqual(structural.npn_keys[row], "")
                self.assertEqual(int(structural.npn[row]), 0)
        luts = [row for row, kind in enumerate(graph.kind) if kind == "lut"]
        self.assertEqual(len({structural.npn_keys[row] for row in luts}), 2)

    def test_structural_files_deterministic(self) -> None:
        """Two runs give the same JSON except ``seconds`` and equal arrays; a rerun reuses."""
        import numpy as np

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            graph = _graph(root)
            first = run_structural(graph, root / "a")
            second = run_structural(graph, root / "b")
            self.assertEqual(first.name, "structural-npn-both.json")
            record = json.loads(first.read_text(encoding="utf-8"))
            self.assertEqual(set(record), _JSON_KEYS)
            self.assertEqual(record["schema"], 1)
            self.assertEqual(record["kind"], "structural")
            self.assertEqual(record["design"], "d")
            self.assertEqual(record["floor"], "f2")
            self.assertEqual(record["variant"], "npn/both")
            self.assertEqual(record["rounds"], WL_ROUNDS)
            self.assertEqual(record["graph_sha256"], graph.sha256)
            self.assertEqual(len(record["classes_per_round"]), WL_ROUNDS + 1)
            self.assertEqual(set(record["npn"]), _NPN_KEYS)
            self.assertEqual(len(record["npn_keys"]), graph.n_nodes)
            self.assertEqual(len(record["colours"]), WL_ROUNDS + 1)
            self.assertTrue(all(len(c) == graph.n_nodes for c in record["colours"]))
            other = json.loads(second.read_text(encoding="utf-8"))
            for key in _JSON_KEYS - {"seconds"}:
                self.assertEqual(record[key], other[key], key)
            with np.load(first.with_suffix(".npz")) as one, \
                    np.load(second.with_suffix(".npz")) as two:
                self.assertEqual(
                    sorted(one.files), ["node_ids", "npn", "roles", "wl"]
                )
                for name in one.files:
                    self.assertTrue(np.array_equal(one[name], two[name]), name)
                self.assertEqual(tuple(str(n) for n in one["node_ids"]), graph.node_ids)
            before = first.read_bytes()
            self.assertEqual(run_structural(graph, root / "a"), first)
            self.assertEqual(first.read_bytes(), before)
            variant = run_structural(graph, root / "a", variant="table/both")
            self.assertNotEqual(variant, first)
            self.assertEqual(
                json.loads(variant.read_text(encoding="utf-8"))["variant"], "table/both"
            )

    def test_quotient_optional(self) -> None:
        """``stable_class`` and the quotient exist only with ``with_quotient`` (spec 4.1)."""
        import numpy as np

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            graph = _graph(root)
            plain = compute_structural(graph)
            self.assertIsNone(plain.stable_class)
            self.assertIsNone(plain.quotient)
            coarse = compute_structural(graph, with_quotient=True)
            self.assertIsNotNone(coarse.stable_class)
            self.assertIsNotNone(coarse.quotient)
            stable_class = coarse.stable_class
            quotient = coarse.quotient
            if stable_class is None or quotient is None:
                self.fail("with_quotient must fill both fields")
            self.assertEqual(stable_class.dtype, np.int64)
            self.assertEqual(stable_class.shape, (graph.n_nodes,))
            self.assertEqual(len(quotient.label), len(quotient.size))
            self.assertEqual(sum(quotient.size), graph.n_nodes)
            path = run_structural(graph, root / "q", with_quotient=True)
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertIsNotNone(record["quotient"])
            self.assertEqual(set(record["quotient"]), {"n_classes", "edges"})
            with np.load(path.with_suffix(".npz")) as data:
                self.assertIn("stable_class", data.files)
                self.assertTrue(np.array_equal(data["stable_class"], stable_class))
                self.assertIn("wl", data.files)
            loaded = load_structural(graph, "npn/both", root / "q")
            self.assertEqual(loaded.variant, "npn/both")
            self.assertIsNotNone(loaded.stable_class)
            self.assertIsNotNone(loaded.quotient)
            self.assertEqual(loaded.npn_keys, coarse.npn_keys)
            self.assertEqual(loaded.colours, coarse.colours)
            self.assertEqual(len(loaded.colours), WL_ROUNDS + 1)
            if loaded.stable_class is not None and loaded.quotient is not None:
                self.assertTrue(np.array_equal(loaded.stable_class, stable_class))
                self.assertEqual(loaded.quotient.edges, quotient.edges)
                self.assertEqual(loaded.quotient.size, quotient.size)
            plain_path = run_structural(graph, root / "p")
            self.assertIsNone(
                json.loads(plain_path.read_text(encoding="utf-8"))["quotient"]
            )
            # The same out directory with a new option recomputes instead of reusing.
            rerun = run_structural(graph, root / "p", with_quotient=True)
            self.assertIsNotNone(
                json.loads(rerun.read_text(encoding="utf-8"))["quotient"]
            )

    def test_cross_design_ids(self) -> None:
        """A sub-circuit shared by two designs keeps equal WL and NPN ids at round 1."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            small = _graph(root / "small", n_lut=12, design="alpha")
            large = _graph(root / "large", n_lut=14, design="beta")
        first = compute_structural(small)
        second = compute_structural(large)
        self.assertNotEqual(small.n_nodes, large.n_nodes)
        shared = ("n2", "n3", "n4", "n5", "n6")
        small_rows, large_rows = small.index(), large.index()
        for node_id in shared:
            a, b = small_rows[node_id], large_rows[node_id]
            self.assertEqual(int(first.wl[a, 1]), int(second.wl[b, 1]), node_id)
            self.assertEqual(int(first.npn[a]), int(second.npn[b]), node_id)
            self.assertEqual(first.npn_keys[a], second.npn_keys[b], node_id)

    def test_gsn_features_blocks(self) -> None:
        """The numeric block and the int64 categorical block of spec 8.6."""
        import numpy as np

        with tempfile.TemporaryDirectory() as tmp:
            graph = _graph(Path(tmp))
        structural = compute_structural(graph)
        numeric, categorical = gsn_features(None, structural.roles, structural)
        self.assertEqual(categorical.dtype, np.int64)
        self.assertEqual(categorical.shape, (graph.n_nodes, 1 + WL_ROUNDS + 1))
        self.assertEqual(numeric.shape, (graph.n_nodes, 4))
        self.assertTrue(np.array_equal(numeric, structural.roles.astype(np.float64)))
        self.assertTrue(np.array_equal(categorical[:, 0], structural.npn))
        self.assertTrue(np.array_equal(categorical[:, 1:], structural.wl))
        orbits = np.arange(graph.n_nodes * 15, dtype=np.int64).reshape(graph.n_nodes, 15)
        numeric, with_orbits = gsn_features(orbits, structural.roles, structural)
        self.assertTrue(np.array_equal(with_orbits, categorical))
        self.assertEqual(numeric.shape, (graph.n_nodes, 15 + 4))
        expected = np.log1p(orbits.astype(np.float64))
        mean = expected.mean(axis=0)
        spread = expected.std(axis=0)
        self.assertTrue(np.allclose(numeric[:, :15], (expected - mean) / spread))
        self.assertTrue(np.array_equal(numeric[:, 15:], structural.roles.astype(np.float64)))


if __name__ == "__main__":
    unittest.main()
