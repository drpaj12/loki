"""L2 Task 7: k-means and affinity propagation (L2 spec sections 7.1 and 7.2)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from loki.analysis import cluster
from loki.analysis.cluster import (
    ClusterError,
    assign_nearest,
    cluster_affinity,
    cluster_kmeans,
    cluster_space,
    resolve_k,
)
from loki.analysis.graphio import Graph, load_graph
from loki.analysis.partition import write_partition
from tests.analysis_fixtures import make_graph, write_graph
from tests.helpers import skip_without

_LABELS: dict[str, object] = {
    "construct_type": "", "construct_types": "", "n_construct_cells": -1, "module_path": "",
    "bus_name": "", "bit_index": -1, "role": "unknown", "hdl_file": "", "hdl_line": -1,
    "hdl_col": -1, "hdl_end_line": -1, "hdl_end_col": -1, "n_spans": 0,
}


def _node(nid: str, kind: str, **features: int) -> dict[str, object]:
    """A valid node with the given kind; unset features are zero."""
    values: dict[str, object] = {
        "fan_in": 0, "fan_out": 0, "level": 0, "lut_width": 0, "lut_table": "",
        "is_seq": 0, "is_const": 0, "hard_ports": 0,
    }
    values.update(features)
    return {"id": nid, "kind": kind, "features": values, "labels": dict(_LABELS)}


def _flat_graph(n: int, kind: str) -> dict[str, object]:
    """``n`` nodes of one kind with identical features and no edges (constant-only designs)."""
    return {
        "schema": 1,
        "design": "flat",
        "floor": "f2",
        "nodes": [_node(f"n{i}", kind) for i in range(n)],
        "edges": [],
    }


def _load(obj: dict[str, object]) -> Graph:
    """Write ``obj`` as a ``graph.json`` and load it back (the temp file is not needed after)."""
    with tempfile.TemporaryDirectory() as tmp:
        return load_graph(write_graph(Path(tmp), obj))


def _fake_fit(outcomes: list[list[int]]) -> tuple[Any, list[Any]]:
    """A stand-in for ``AffinityPropagation.fit`` replaying ``outcomes`` (last one repeats)."""
    calls: list[Any] = []

    def fit(model: Any, x: Any, y: Any = None) -> Any:
        import numpy as np

        labels = np.asarray(outcomes[min(len(calls), len(outcomes) - 1)], dtype=np.int64)
        calls.append(np.asarray(x))
        model.labels_ = labels
        model.cluster_centers_ = np.asarray(x, dtype=np.float64)[:1]
        return model

    return fit, calls


@skip_without("numpy", "scipy", "sklearn", "networkx")
class ClusterFeaturesTest(unittest.TestCase):
    """Plan Task 7, steps 1: the ten pinned behaviours of the two feature-space methods."""

    def test_resolve_k(self) -> None:
        self.assertEqual(resolve_k("auto", 200), 10)
        self.assertEqual(resolve_k("auto", 4), 2)
        self.assertEqual(resolve_k(50, 10), 10)
        self.assertEqual(resolve_k("auto", 1), 1)
        with self.assertRaises(ValueError):
            resolve_k("bogus", 1)
        with self.assertRaises(ValueError):
            resolve_k(0, 1)

    def test_kmeans_separates_planted_blocks(self) -> None:
        import numpy as np

        g = _load(make_graph(40))
        partition = cluster_kmeans(g, k=2)
        widths = np.asarray(g.num["lut_width"])
        assignment = np.asarray(partition.assignment)
        self.assertEqual(partition.n_clusters, 2)
        self.assertTrue(all(size > 0 for size in partition.sizes()))
        for width in (2, 3):
            rows = np.flatnonzero(widths == width)
            self.assertEqual(len(set(assignment[rows].tolist())), 1, f"width {width} split")

    def test_kmeans_deterministic(self) -> None:
        g = _load(make_graph(40))
        first = cluster_kmeans(g, k=3, seed=7)
        second = cluster_kmeans(g, k=3, seed=7)
        self.assertEqual(first.assignment, second.assignment)
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            path_a = write_partition(first, Path(a))
            path_b = write_partition(second, Path(b))
            self.assertEqual(path_a.read_bytes(), path_b.read_bytes())

    def test_kmeans_uses_minibatch_over_20000(self) -> None:
        g = _load(make_graph(40))
        small = cluster_kmeans(g, k=2)
        self.assertEqual(small.params["algorithm"], "kmeans")
        with mock.patch.object(cluster, "KMEANS_FULL_MAX", 10):
            large = cluster_kmeans(g, k=2)
        self.assertEqual(large.params["algorithm"], "minibatch")

    def test_kmeans_records_convergence_warning(self) -> None:
        import importlib
        import warnings as warnings_module

        g = _load(make_graph(20))
        kmeans = importlib.import_module("sklearn.cluster").KMeans
        exceptions = importlib.import_module("sklearn.exceptions")
        real = kmeans.fit_predict

        def warned_fit(model: Any, x: Any, y: Any = None) -> Any:
            warnings_module.warn("planted", exceptions.ConvergenceWarning, stacklevel=2)
            return real(model, x, y)

        with mock.patch.object(kmeans, "fit_predict", new=warned_fit):
            warned = cluster_kmeans(g, k=2)
        self.assertIs(warned.params["convergence_warning"], True)

        def quiet_fit(model: Any, x: Any, y: Any = None) -> Any:
            import numpy as np

            return np.zeros(len(x), dtype=np.int64)

        with mock.patch.object(kmeans, "fit_predict", new=quiet_fit):
            clean = cluster_kmeans(g, k=2)
        self.assertIs(clean.params["convergence_warning"], False)

    def test_affinity_sampled_and_assigned(self) -> None:
        g = _load(make_graph(115))
        self.assertEqual(g.n_nodes, 120)
        partition = cluster_affinity(g, max_points=50)
        self.assertEqual(partition.sampled, {"points": 50})
        self.assertEqual(len(partition.assignment), 120)
        self.assertGreaterEqual(min(partition.assignment), 0)
        self.assertGreaterEqual(partition.n_clusters, 1)

    def test_assign_nearest_chunked_matches_unchunked(self) -> None:
        import numpy as np

        rng = np.random.default_rng(5)
        x = rng.normal(size=(23, 4))
        centers = rng.normal(size=(3, 4))
        chunked = assign_nearest(x, centers, chunk=7)
        whole = assign_nearest(x, centers, chunk=10000)
        self.assertEqual(chunked.tolist(), whole.tolist())

    def test_affinity_identical_rows(self) -> None:
        g = _load(_flat_graph(6, "lut"))
        partition = cluster_affinity(g, max_points=10)
        self.assertEqual(partition.n_clusters, 1)
        self.assertEqual(set(partition.assignment), {0})

    def test_affinity_nonconvergence_retry_then_error(self) -> None:
        import importlib

        g = _load(make_graph(20))
        node_count = g.n_nodes
        affinity = importlib.import_module("sklearn.cluster").AffinityPropagation
        failing = [-1] * node_count
        failing_fit = _fake_fit([failing, failing])[0]
        with (
            mock.patch.object(affinity, "fit", new=failing_fit),
            self.assertRaises(ClusterError) as caught,
        ):
            cluster_affinity(g)
        self.assertEqual(str(caught.exception), "affinity propagation did not converge")
        fit, calls = _fake_fit([failing, [0] * node_count])
        with mock.patch.object(affinity, "fit", new=fit):
            partition = cluster_affinity(g)
        self.assertEqual(len(calls), 2)
        self.assertIs(partition.params["retried"], True)
        self.assertEqual(partition.n_clusters, 1)

    def test_single_node_and_zero_edge(self) -> None:
        one = _load(_flat_graph(1, "lut"))
        partition = cluster_kmeans(one)
        self.assertEqual(partition.assignment, (0,))
        self.assertEqual(partition.n_clusters, 1)
        self.assertIs(partition.params["convergence_warning"], False)
        const = _load(_flat_graph(5, "const"))
        kmeans = cluster_kmeans(const, k="auto")
        self.assertEqual(len(kmeans.assignment), 5)
        self.assertGreaterEqual(kmeans.n_clusters, 1)
        affinity = cluster_affinity(const)
        self.assertEqual(affinity.assignment, (0,) * 5)

    def test_extra_columns_change_space(self) -> None:
        import numpy as np

        g = _load(make_graph(10))
        base = cluster_space(g)
        extra = np.arange(2 * g.n_nodes, dtype=np.float64).reshape(g.n_nodes, 2)
        wide = cluster_space(g, extra)
        self.assertEqual(wide.shape[0], base.shape[0])
        self.assertEqual(wide.shape[1], base.shape[1] + extra.shape[1])
        self.assertEqual(base.dtype, np.float64)
        self.assertEqual(wide.dtype, np.float64)
        features = cluster_kmeans(g, k=2, extra=extra).params["features"]
        self.assertEqual(
            features,
            [
                "fan_in", "fan_out", "level", "lut_width", "hard_ports", "lut_ones",
                "kind:pi", "kind:po", "kind:lut", "kind:ff", "kind:const", "kind:hard",
                "kind:gate", "extra:0", "extra:1",
            ],
        )


if __name__ == "__main__":
    unittest.main()
