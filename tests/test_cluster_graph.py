"""L2 Task 8: spectral and Louvain clustering, ``run_cluster`` (L2 spec sections 7.3 and 7.4)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from loki.analysis.cluster import (
    METHODS,
    cluster_louvain,
    cluster_spectral,
    run_cluster,
)
from loki.analysis.graphio import Graph, load_graph
from loki.analysis.partition import Partition, load_partition, write_partition
from tests.analysis_fixtures import write_graph
from tests.helpers import skip_without

_LABELS: dict[str, object] = {
    "construct_type": "$eq", "construct_types": "$eq", "n_construct_cells": 1,
    "module_path": "", "bus_name": "", "bit_index": -1, "role": "datapath", "hdl_file": "d.v",
    "hdl_line": -1, "hdl_col": -1, "hdl_end_line": -1, "hdl_end_col": -1, "n_spans": 1,
}


def _build(
    design: str, modules: list[str], pairs: list[tuple[int, int]]
) -> dict[str, object]:
    """A valid ``graph.json`` object: one LUT per entry of ``modules``, edges from ``pairs``.

    Every edge is written once (driver to sink); the undirected projection is what the graph
    methods see. Labels carry ``module_path`` from ``modules`` so the partition quality reports
    NMI against the planted blocks.
    """
    order = [f"n{index}" for index in range(len(modules))]
    fan_in = dict.fromkeys(range(len(modules)), 0)
    fan_out = dict.fromkeys(range(len(modules)), 0)
    for src, dst in pairs:
        fan_out[src] += 1
        fan_in[dst] += 1
    nodes: list[dict[str, object]] = []
    for row, module in enumerate(modules):
        labels = dict(_LABELS)
        labels["module_path"] = module
        nodes.append(
            {
                "id": order[row],
                "kind": "lut",
                "features": {
                    "fan_in": fan_in[row], "fan_out": fan_out[row], "level": 0,
                    "lut_width": 2, "lut_table": "8", "is_seq": 0, "is_const": 0,
                    "hard_ports": 0,
                },
                "labels": labels,
            }
        )
    edges = [
        {"src": order[src], "dst": order[dst], "net": f"n{100 + index}", "pin": "I0"}
        for index, (src, dst) in enumerate(pairs)
    ]
    return {"schema": 1, "design": design, "floor": "f2", "nodes": nodes, "edges": edges}


def _blocks() -> dict[str, object]:
    """Two dense 10-node cliques joined by one edge, each clique its own ``module_path``."""
    groups = [list(range(10)), list(range(10, 20))]
    pairs = [
        (left, right)
        for group in groups
        for position, left in enumerate(group)
        for right in group[position + 1:]
    ]
    pairs.append((9, 10))
    pairs.sort()
    return _build("blocks", ["top/u0"] * 10 + ["top/u1"] * 10, pairs)


def _many_components() -> dict[str, object]:
    """50 isolated two-node components plus one connected block of 30 nodes."""
    pairs = [(2 * index, 2 * index + 1) for index in range(50)]
    pairs.extend((100 + index, 101 + index) for index in range(29))
    return _build("many", ["top/p"] * 100 + ["top/u0"] * 30, pairs)


def _small(design: str, modules: list[str], pairs: list[tuple[int, int]]) -> dict[str, object]:
    """A tiny graph object with the given nodes and edges."""
    return _build(design, modules, pairs)


def _load(obj: dict[str, object]) -> Graph:
    """Write ``obj`` as a ``graph.json`` and load it back (the temp file is not needed after)."""
    with tempfile.TemporaryDirectory() as tmp:
        return load_graph(write_graph(Path(tmp), obj))


def _nmi(partition: Partition) -> float:
    """``nmi_module_path`` of a partition, which these graphs always label."""
    value = partition.quality["nmi_module_path"]
    if not isinstance(value, float):
        raise AssertionError(f"nmi_module_path is {value!r}, not a float")
    return value


@skip_without("numpy", "scipy", "sklearn", "networkx")
class ClusterGraphTest(unittest.TestCase):
    """Plan Task 8, step 1: the nine pinned behaviours of the graph-structure methods."""

    def test_louvain_recovers_planted_blocks(self) -> None:
        partition = cluster_louvain(_load(_blocks()))
        self.assertEqual(partition.n_clusters, 2)
        self.assertGreater(_nmi(partition), 0.9)

    def test_louvain_deterministic_with_seed(self) -> None:
        g = _load(_blocks())
        first = cluster_louvain(g, seed=5)
        second = cluster_louvain(g, seed=5)
        self.assertEqual(first.assignment, second.assignment)
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            path_a = write_partition(first, Path(a))
            path_b = write_partition(second, Path(b))
            self.assertEqual(path_a.read_bytes(), path_b.read_bytes())

    def test_spectral_recovers_blocks(self) -> None:
        partition = cluster_spectral(_load(_blocks()), k=2)
        self.assertEqual(partition.n_clusters, 2)
        self.assertGreater(_nmi(partition), 0.9)

    def test_spectral_many_components(self) -> None:
        g = _load(_many_components())
        partition = cluster_spectral(g, k=2)
        self.assertEqual(partition.components, 51)
        self.assertEqual(len(partition.assignment), g.n_nodes)
        self.assertEqual(set(partition.assignment), set(range(partition.n_clusters)))
        assignment = partition.assignment
        for index in range(50):
            self.assertEqual(assignment[2 * index], assignment[2 * index + 1])
        pair_clusters = {assignment[2 * index] for index in range(50)}
        self.assertEqual(len(pair_clusters), 50)
        sizes = partition.sizes()
        self.assertTrue(all(sizes[number] == 2 for number in pair_clusters))

    def test_spectral_tiny(self) -> None:
        pair = cluster_spectral(_load(_small("tiny2", ["top/u0", "top/u0"], [(0, 1)])))
        self.assertEqual(len(pair.assignment), 2)
        self.assertEqual(pair.components, 1)
        self.assertEqual(pair.n_clusters, 1)
        self.assertEqual(set(pair.assignment), set(range(pair.n_clusters)))
        one = cluster_spectral(_load(_small("tiny1", ["top/u0"], [])))
        self.assertEqual(one.assignment, (0,))
        self.assertEqual(one.n_clusters, 1)
        self.assertEqual(one.components, 1)

    def test_spectral_zero_edges(self) -> None:
        partition = cluster_spectral(_load(_small("flat", ["top/u0"] * 5, [])))
        self.assertEqual(partition.components, 5)
        self.assertEqual(partition.n_clusters, 5)
        self.assertEqual(set(partition.assignment), set(range(5)))

    def test_run_cluster_all_writes_four_files(self) -> None:
        self.assertEqual(METHODS, ("kmeans", "affinity", "spectral", "louvain"))
        g = _load(_blocks())
        with tempfile.TemporaryDirectory() as tmp:
            paths = run_cluster(g, METHODS, Path(tmp))
            self.assertEqual([path.name.split("-")[0] for path in paths], list(METHODS))
            self.assertEqual(len(list(Path(tmp).iterdir())), 4)
            for path, method in zip(paths, METHODS, strict=True):
                self.assertRegex(path.name, rf"^{method}-[0-9a-f]{{8}}\.json$")
                partition = load_partition(path)
                self.assertEqual(partition.method, method)
                self.assertEqual(len(partition.assignment), g.n_nodes)

    def test_run_cluster_byte_identical_twice(self) -> None:
        g = _load(_blocks())
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            first = run_cluster(g, METHODS, Path(a))
            second = run_cluster(g, METHODS, Path(b))
            self.assertEqual([path.name for path in first], [path.name for path in second])
            for left, right in zip(first, second, strict=True):
                self.assertEqual(left.read_bytes(), right.read_bytes())

    def test_unknown_method(self) -> None:
        g = _load(_blocks())
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            run_cluster(g, ["bogus"], Path(tmp))


if __name__ == "__main__":
    unittest.main()
