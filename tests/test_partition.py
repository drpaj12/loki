"""L2 Task 6: partition record, storage, quality and evidence loading (L2 spec section 6)."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any

from loki.analysis.graphio import Graph, load_graph
from loki.analysis.partition import (
    compute_quality,
    load_partition,
    make_partition,
    partition_hash,
    write_partition,
)
from loki.analysis.region import parse_region
from loki.schemas import dump_json
from tests.analysis_fixtures import make_graph, write_graph
from tests.helpers import skip_without

_LABELS = {
    "construct_type": "", "construct_types": "", "n_construct_cells": -1, "module_path": "",
    "bus_name": "", "bit_index": -1, "role": "unknown", "hdl_file": "", "hdl_line": -1,
    "hdl_col": -1, "hdl_end_line": -1, "hdl_end_col": -1, "n_spans": 0,
}
_QUALITY_KINDS = ("lut", "ff", "hard", "gate")


def _node(nid: str, kind: str) -> dict[str, object]:
    return {
        "id": nid,
        "kind": kind,
        "features": {
            "fan_in": 0, "fan_out": 0, "level": 0, "lut_width": 0, "lut_table": "",
            "is_seq": 0, "is_const": 0, "hard_ports": 0,
        },
        "labels": dict(_LABELS),
    }


def _single_node_obj() -> dict[str, object]:
    """A valid ``graph.json`` with one LUT and no edges."""
    return {"schema": 1, "design": "one", "floor": "f2", "nodes": [_node("n0", "lut")],
            "edges": []}


def _planted(g: Graph) -> Any:
    """Assignment by ``module_path`` over lut/ff/hard/gate nodes; other kinds join cluster 0."""
    import numpy as np

    labels = g.labels
    assert labels is not None
    paths = labels["module_path"]
    numbers: dict[str, int] = {}
    rows: list[int] = []
    for row, kind in enumerate(g.kind):
        path = str(paths[row])
        if kind in _QUALITY_KINDS and path:
            rows.append(numbers.setdefault(path, len(numbers)))
        else:
            rows.append(0)
    return np.asarray(rows, dtype=np.int64)


def _assert_rounded(case: unittest.TestCase, value: object) -> None:
    """Every float of a parsed JSON value equals its own 6-decimal rounding."""
    if isinstance(value, float):
        case.assertEqual(value, round(value, 6))
    elif isinstance(value, dict):
        for item in value.values():
            _assert_rounded(case, item)
    elif isinstance(value, list):
        for item in value:
            _assert_rounded(case, item)


@skip_without("numpy", "scipy", "sklearn", "networkx")
class PartitionTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.graph = load_graph(write_graph(self.dir / "graph", make_graph()))
        self.small = load_graph(write_graph(self.dir / "small", make_graph(n_lut=2)))

    def test_roundtrip_and_key(self) -> None:
        p = make_partition(
            self.graph, "louvain", {"resolution": 1.0}, 0, _planted(self.graph),
            sampled={"points": 3}, components=1,
        )
        path = write_partition(p, self.dir / "partitions")
        self.assertEqual(path, self.dir / "partitions" / f"louvain-{p.key[8:]}.json")
        loaded = load_partition(path)
        self.assertEqual(loaded, p)
        self.assertEqual(loaded.node_ids, self.graph.node_ids)
        self.assertEqual(loaded.quality, p.quality)
        self.assertEqual(loaded.sampled, {"points": 3})
        self.assertEqual(loaded.components, 1)
        self.assertEqual(
            p.key, "louvain:" + partition_hash("louvain", {"resolution": 1.0}, 0,
                                               self.graph.sha256)
        )
        self.assertEqual(len(p.key), len("louvain:") + 8)
        self.assertEqual(set(p.versions), {"numpy", "networkx", "scikit-learn"})
        self.assertTrue(p.versions["numpy"])

    def test_hash_depends_on_params_and_seed(self) -> None:
        base = partition_hash("louvain", {"resolution": 1.0}, 0, "abc")
        self.assertEqual(base, partition_hash("louvain", {"resolution": 1.0}, 0, "abc"))
        self.assertEqual(len(base), 8)
        self.assertTrue(set(base) <= set("0123456789abcdef"))
        self.assertNotEqual(base, partition_hash("louvain", {"resolution": 2.0}, 0, "abc"))
        self.assertNotEqual(base, partition_hash("louvain", {"resolution": 1.0}, 1, "abc"))
        self.assertNotEqual(base, partition_hash("louvain", {"resolution": 1.0}, 0, "abd"))
        self.assertNotEqual(base, partition_hash("kmeans", {"resolution": 1.0}, 0, "abc"))

    def test_quality_planted_blocks(self) -> None:
        import numpy as np

        quality = compute_quality(self.graph, _planted(self.graph))
        self.assertEqual(quality["nmi_module_path"], 1.0)
        self.assertEqual(quality["ari_module_path"], 1.0)
        self.assertEqual(quality["size_min"], 7)
        self.assertEqual(quality["size_median"], 8.5)
        self.assertEqual(quality["size_max"], 10)
        modularity = quality["modularity"]
        construct = quality["nmi_construct_type"]
        assert isinstance(modularity, float)
        assert isinstance(construct, float)
        self.assertGreater(modularity, 0.0)
        self.assertGreaterEqual(construct, 0.0)
        self.assertLessEqual(construct, 1.0)
        one = compute_quality(self.graph, np.zeros(self.graph.n_nodes, dtype=np.int64))
        one_modularity = one["modularity"]
        assert isinstance(one_modularity, float)
        self.assertAlmostEqual(one_modularity, 0.0, places=9)
        self.assertEqual(one["size_min"], self.graph.n_nodes)

    def test_quality_unlabelled_is_null(self) -> None:
        import numpy as np

        g = load_graph(write_graph(self.dir / "unlabelled", make_graph(labels=False)))
        quality = compute_quality(g, np.zeros(g.n_nodes, dtype=np.int64))
        self.assertIsNone(quality["nmi_module_path"])
        self.assertIsNone(quality["ari_module_path"])
        self.assertIsNone(quality["nmi_construct_type"])
        modularity = quality["modularity"]
        assert isinstance(modularity, float)
        self.assertAlmostEqual(modularity, 0.0, places=9)
        obj: Any = make_graph()
        for node in obj["nodes"]:
            if node["kind"] in ("lut", "ff"):
                node["labels"]["module_path"] = ""
                node["labels"]["construct_type"] = ""
        blank = load_graph(write_graph(self.dir / "blank", obj))
        partial = compute_quality(blank, np.zeros(blank.n_nodes, dtype=np.int64))
        self.assertIsNone(partial["nmi_module_path"])
        self.assertIsNone(partial["ari_module_path"])
        self.assertIsNone(partial["nmi_construct_type"])

    def test_members_and_cluster_of(self) -> None:
        import numpy as np

        self.assertEqual(self.small.node_ids, ("n0", "n1", "n2", "n3", "n4", "n5", "n6"))
        p = make_partition(self.small, "louvain", {}, 0,
                           np.asarray([0, 0, 0, 1, 0, 1, 1], dtype=np.int64))
        self.assertEqual(p.n_clusters, 2)
        self.assertEqual(p.sizes(), [4, 3])
        self.assertEqual(p.members(0), ("n0", "n1", "n2", "n4"))
        self.assertEqual(p.members(1), ("n3", "n5", "n6"))
        self.assertEqual(p.members(2), ())
        self.assertEqual(p.cluster_of("n3"), 1)
        self.assertEqual(p.cluster_of("n0"), 0)
        with self.assertRaises(ValueError):
            p.cluster_of("n99")

    def test_load_rejects_gaps_and_length(self) -> None:
        import numpy as np

        p = make_partition(self.small, "louvain", {}, 0,
                           np.asarray([0, 0, 0, 1, 0, 1, 1], dtype=np.int64))
        data: dict[str, Any] = json.loads(
            write_partition(p, self.dir / "p").read_text(encoding="utf-8")
        )
        cases = {
            "short": dict(data, assignment=data["assignment"][:-1]),
            "gap": dict(data, assignment=[0, 0, 0, 2, 0, 2, 2]),
            "negative": dict(data, assignment=[0, 0, 0, -1, 0, -1, -1]),
            "nodes": dict(data, node_ids=data["node_ids"][:-1]),
            "clusters": dict(data, n_clusters=5),
            "kind": dict(data, kind="graph"),
            "duplicate": dict(data, node_ids=[data["node_ids"][0]] * len(data["node_ids"])),
            "schema_true": dict(data, schema=True),
        }
        for name, broken in cases.items():
            path = self.dir / f"{name}.json"
            path.write_text(dump_json(broken), encoding="utf-8")
            with self.subTest(name=name), self.assertRaises(ValueError):
                load_partition(path)
        missing = dict(data)
        del missing["assignment"]
        path = self.dir / "missing.json"
        path.write_text(dump_json(missing), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_partition(path)

    def test_parse_region_cluster(self) -> None:
        import numpy as np

        p = make_partition(self.small, "louvain", {}, 0,
                           np.asarray([0, 0, 0, 1, 0, 1, 1], dtype=np.int64))
        path = write_partition(p, self.dir / "p")
        region = parse_region(self.small, f"cluster:{path}:1")
        self.assertEqual(region.node_ids, ("n3", "n5", "n6"))
        self.assertEqual(region.spec, f"cluster:{p.key}:1")
        self.assertEqual(parse_region(self.small, f"cluster:{path}:0").node_ids,
                         ("n0", "n1", "n2", "n4"))

    def test_quality_rejects_gap(self) -> None:
        import numpy as np

        with self.assertRaises(ValueError):
            compute_quality(self.small, np.asarray([0, 0, 2, 0, 2, 2, 2], dtype=np.int64))
        with self.assertRaises(ValueError):
            compute_quality(self.small, np.asarray([0, 0, -1, 0, 1, 1, 1], dtype=np.int64))

    def test_write_deterministic(self) -> None:
        p = make_partition(self.graph, "louvain", {"resolution": 1.0}, 0, _planted(self.graph))
        first = write_partition(p, self.dir / "a")
        second = write_partition(p, self.dir / "b")
        self.assertEqual(first.name, second.name)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        _assert_rounded(self, json.loads(first.read_text(encoding="utf-8")))
        noisy = replace(p, quality={
            "modularity": 0.1234567890123, "size_min": 1, "size_median": 2.5, "size_max": 3,
            "nmi_module_path": None, "ari_module_path": None, "nmi_construct_type": None,
        })
        text = write_partition(noisy, self.dir / "c").read_text(encoding="utf-8")
        self.assertIn("0.123457", text)
        self.assertNotIn("0.1234567", text)

    def test_hand_built_params_hash_stored_form(self) -> None:
        import numpy as np

        p = make_partition(self.small, "louvain", {}, 0,
                           np.asarray([0, 0, 0, 1, 0, 1, 1], dtype=np.int64))
        noisy = replace(p, params={"resolution": 0.1234567890123})
        path = write_partition(noisy, self.dir / "hand")
        loaded = load_partition(path)
        self.assertEqual(loaded.params, {"resolution": 0.123457})
        self.assertEqual(path.name, f"louvain-{loaded.key[8:]}.json")
        self.assertEqual(loaded.key, noisy.key)

    def test_single_node_graph(self) -> None:
        import numpy as np

        g = load_graph(write_graph(self.dir / "one", _single_node_obj()))
        self.assertEqual(g.n_nodes, 1)
        quality = compute_quality(g, np.zeros(1, dtype=np.int64))
        self.assertEqual(quality["modularity"], 0.0)
        self.assertEqual(quality["size_min"], 1)
        self.assertEqual(quality["size_median"], 1.0)
        self.assertEqual(quality["size_max"], 1)
        self.assertIsNone(quality["nmi_module_path"])
        p = make_partition(g, "louvain", {}, 0, np.zeros(1, dtype=np.int64))
        self.assertEqual(p.n_clusters, 1)
        self.assertEqual(load_partition(write_partition(p, self.dir / "p")), p)
