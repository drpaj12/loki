"""L2 Task 10: graphlet core and the orbit oracle (L2 spec 8.3 to 8.6).

The oracle self-tests fix the orbit numbering of spec 8.4 with hand-computed values (and one
line ORCA printed); the core tests drive the counting graph, the orbit files and ``run_graphlets``
through a ``FakeCounter`` registered in :data:`loki.analysis.graphlets.BACKENDS`, so they run
without ORCA (its own backend arrives in plan Task G-ext). numpy and networkx belong to the
``analysis`` extra, so the classes skip when one is absent.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loki.analysis.graphio import Graph, load_graph
from loki.analysis.graphlets import (
    BACKENDS,
    DEFAULT_BACKEND,
    N_ORBITS,
    BackendUnavailable,
    CountingGraph,
    counting_graph,
    get_backend,
    graphlet_features,
    load_orbits,
    read_orbit_file,
    run_graphlets,
    write_edge_file,
)
from loki.analysis.graphlets.signals import CLASS_NAMES, classify_signals
from loki.schemas import SCHEMA
from tests.analysis_fixtures import (
    _EMPTY_LABELS,
    _features,
    make_sync_design,
    star_graph,
    write_graph,
)
from tests.graphlet_oracle import brute_orbits
from tests.helpers import skip_without

if TYPE_CHECKING:
    import numpy.typing as npt

_JSON_KEYS = {
    "schema", "kind", "design", "floor", "backend", "tool", "size", "n_orbits", "removal",
    "hub_threshold", "signal_config", "classified", "removed_edges", "dropped_hubs",
    "clock_domains", "n_nodes", "n_edges", "graph_sha256", "seconds", "versions",
}


def _load(obj: dict[str, object]) -> Graph:
    """Load a hand-built ``graph.json`` object through the real loader."""
    with tempfile.TemporaryDirectory() as tmp:
        return load_graph(write_graph(Path(tmp), obj))


def _orbits(n: int, edges: list[tuple[int, int]]) -> npt.NDArray[Any]:
    """The oracle's orbit vectors for an edge list of a simple undirected graph."""
    import numpy as np

    src = np.asarray([u for u, _v in edges], dtype=np.int32)
    dst = np.asarray([v for _u, v in edges], dtype=np.int32)
    return brute_orbits(n, src, dst)


def _pairs(src: npt.NDArray[Any], dst: npt.NDArray[Any]) -> set[tuple[int, int]]:
    """Undirected node pairs of an edge array, endpoints as plain ints."""
    return {(int(u), int(v)) for u, v in zip(src.tolist(), dst.tolist(), strict=True)}


def _small_graph(n: int, edges: list[tuple[int, int, str]]) -> dict[str, object]:
    """A valid ``graph.json`` of ``n`` width-0 LUTs and ``(src, dst, pin)`` edges.

    Each driver owns one net (``n<100 + driver>``), so parallel edges of one driver share it; the
    shape is for projection tests only, no rule can classify these nets but ``signal``.
    """
    fan_in = [0] * n
    fan_out = [0] * n
    for src, dst, _pin in edges:
        fan_out[src] += 1
        fan_in[dst] += 1
    nodes = [
        {
            "id": f"n{row}",
            "kind": "lut",
            "features": _features(fan_in=fan_in[row], fan_out=fan_out[row], level=0),
            "labels": dict(_EMPTY_LABELS),
        }
        for row in range(n)
    ]
    rows = [
        {"src": f"n{src}", "dst": f"n{dst}", "net": f"n{100 + src}", "pin": pin}
        for src, dst, pin in edges
    ]
    return {"schema": SCHEMA, "design": "small", "floor": "f2", "nodes": nodes, "edges": rows}


class _FakeCounter:
    """The oracle as a registered backend (plan Task 10 step 1); no ORCA needed."""

    name = "fake"
    max_size = 5
    commit = "0" * 40
    sha256 = "1" * 64
    licence = "test only"

    def available(self) -> tuple[bool, str]:
        """Always installed: the oracle is Python."""
        return True, ""

    def count(
        self, n: int, src: npt.NDArray[Any], dst: npt.NDArray[Any], size: int = 4
    ) -> npt.NDArray[Any]:
        """The oracle's counts; size 5 is zero-filled because the oracle is 4-node only."""
        import numpy as np

        if size == 5:
            return np.zeros((n, N_ORBITS[5]), dtype=np.int64)
        return brute_orbits(n, src, dst)


class _UnavailableCounter(_FakeCounter):
    """A registered backend that reports itself missing, with a reason."""

    name = "missing"
    reason = "run: loki tools fetch-orca"

    def available(self) -> tuple[bool, str]:
        """Not installed."""
        return False, self.reason


class _BigCounter(_FakeCounter):
    """A counter whose counts exceed 2**31, pinning int64 storage."""

    name = "big"

    def count(
        self, n: int, src: npt.NDArray[Any], dst: npt.NDArray[Any], size: int = 4
    ) -> npt.NDArray[Any]:
        """Every orbit count is 2**40."""
        import numpy as np

        return np.full((n, N_ORBITS[size]), 2**40, dtype=np.int64)


class _Registers(unittest.TestCase):
    """Register the fake backends for one test and remove them again."""

    counters: tuple[type[_FakeCounter], ...] = (_FakeCounter, _UnavailableCounter, _BigCounter)

    def setUp(self) -> None:
        """Register one instance per fake backend, undone after the test."""
        for factory in self.counters:
            instance = factory()
            BACKENDS[instance.name] = instance
            self.addCleanup(BACKENDS.pop, instance.name, None)


@skip_without("numpy", "networkx")
class OracleTests(unittest.TestCase):
    """Orbit self-tests: hand-computed values from spec 8.4."""

    def test_oracle_path4(self) -> None:
        """P4: ends orbit 4, inner nodes orbit 5, P3 ends 1 and middles 2, orbit 0 = degree."""
        import numpy as np

        orbits = _orbits(4, [(0, 1), (1, 2), (2, 3)])
        self.assertEqual(orbits.dtype, np.int64)
        self.assertEqual(orbits.shape, (4, 15))
        self.assertEqual(int(orbits[0, 4]), 1)
        self.assertEqual(int(orbits[3, 4]), 1)
        self.assertEqual(int(orbits[1, 5]), 1)
        self.assertEqual(int(orbits[2, 5]), 1)
        self.assertEqual(int(orbits[0, 1]), 1)
        self.assertEqual(int(orbits[1, 2]), 1)
        self.assertEqual(orbits[:, 0].tolist(), [1, 2, 2, 1])

    def test_oracle_star4(self) -> None:
        """K1,3: the hub is orbit 7 once, per leaf orbit 6 once, hub orbit 2 = C(3, 2)."""
        orbits = _orbits(4, [(0, 1), (0, 2), (0, 3)])
        self.assertEqual(int(orbits[0, 7]), 1)
        self.assertEqual(orbits[[1, 2, 3], 6].tolist(), [1, 1, 1])
        self.assertEqual(int(orbits[0, 2]), 3)
        self.assertEqual(orbits[:, 5].tolist(), [0, 0, 0, 0])

    def test_oracle_triangle(self) -> None:
        """K3: degree 2 (orbit 0) and one triangle (orbit 3); no P3 is induced in it."""
        orbits = _orbits(3, [(0, 1), (1, 2), (0, 2)])
        expected = [2, 0, 0, 1] + [0] * 11
        self.assertEqual(orbits.tolist(), [expected] * 3)

    def test_oracle_c4_matches_orca(self) -> None:
        """C4: the line ORCA printed for every node (spec 8.4, checked 2026-10-21)."""
        orbits = _orbits(4, [(0, 1), (1, 2), (2, 3), (0, 3)])
        expected = [2, 2, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0]
        self.assertEqual(orbits.tolist(), [expected] * 4)

    def test_oracle_tailed_triangle(self) -> None:
        """Tailed triangle: pendant orbit 9, degree-2 triangle nodes 10, degree-3 node 11."""
        orbits = _orbits(4, [(0, 1), (1, 2), (0, 2), (2, 3)])
        self.assertEqual(int(orbits[3, 9]), 1)
        self.assertEqual(int(orbits[0, 10]), 1)
        self.assertEqual(int(orbits[1, 10]), 1)
        self.assertEqual(int(orbits[2, 11]), 1)
        self.assertEqual(orbits[:, 8].tolist(), [0, 0, 0, 0])

    def test_oracle_diamond(self) -> None:
        """Diamond: both degree-2 nodes are orbit 12, both degree-3 nodes orbit 13."""
        orbits = _orbits(4, [(0, 2), (0, 3), (1, 2), (1, 3), (2, 3)])
        self.assertEqual(int(orbits[0, 12]), 1)
        self.assertEqual(int(orbits[1, 12]), 1)
        self.assertEqual(int(orbits[2, 13]), 1)
        self.assertEqual(int(orbits[3, 13]), 1)

    def test_oracle_k4(self) -> None:
        """K4: one orbit-14 subgraph per node and the three triangles through it."""
        orbits = _orbits(4, [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)])
        self.assertEqual(orbits[:, 14].tolist(), [1, 1, 1, 1])
        self.assertEqual(orbits[:, 3].tolist(), [3, 3, 3, 3])

    def test_star_hub_exact(self) -> None:
        """A hub of 60 leaves: orbit 7 is C(60, 3) = 34220, orbit 2 is C(60, 2) = 1770."""
        import numpy as np

        leaves = 60
        src = np.zeros(leaves, dtype=np.int32)
        dst = np.arange(1, leaves + 1, dtype=np.int32)
        orbits = brute_orbits(leaves + 1, src, dst)
        self.assertEqual(int(orbits[0, 7]), 34220)
        self.assertEqual(int(orbits[0, 2]), 1770)
        self.assertEqual(orbits[:, 0].tolist(), [leaves] + [1] * leaves)

    def test_oracle_identities(self) -> None:
        """Orbit 3 is three times the triangles of networkx; orbit 0 is 2m."""
        import importlib

        import numpy as np

        nx: Any = importlib.import_module("networkx")
        graph = nx.gnp_random_graph(30, 0.2, seed=7)
        edges = [(min(u, v), max(u, v)) for u, v in graph.edges()]
        orbits = _orbits(30, edges)
        triangles = int(sum(nx.triangles(graph).values())) // 3
        self.assertEqual(int(orbits[:, 3].sum()), triangles * 3)
        self.assertEqual(int(orbits[:, 0].sum()), 2 * len(edges))
        self.assertGreater(triangles, 0)
        self.assertEqual(orbits.ndim, 2)
        self.assertEqual(orbits.shape, (30, 15))
        self.assertEqual(orbits.dtype, np.int64)


class CountingGraphTests(_Registers):
    """The counting graph of spec 8.3: class removal, the hub fallback and the projection."""

    def test_counting_graph_global_removes_non_signal(self) -> None:
        """No clock and no reset edge remains; removed edges are counted; all nodes stay."""
        from collections import Counter

        g = _load(make_sync_design(n_ff=20, reset=True, clocks=2))
        counting = counting_graph(g)
        self.assertIsInstance(counting, CountingGraph)
        self.assertEqual(counting.n, g.n_nodes)
        info = classify_signals(g)
        names = [CLASS_NAMES[int(cls)] for cls in info.edge_class]
        counts = Counter(names)
        self.assertEqual(counting.removed_edges["clock"], counts["clock"])
        self.assertEqual(counting.removed_edges["reset"], counts["reset"])
        self.assertEqual(counts["clock"], 20)
        self.assertEqual(counts["reset"], 20)
        self.assertEqual(counting.removed_edges["hub"], 0)
        self.assertEqual(counting.dropped_hubs, [])
        pairs = _pairs(counting.src, counting.dst)
        for edge, name in enumerate(names):
            if name in ("clock", "reset"):
                src, dst = int(g.src[edge]), int(g.dst[edge])
                self.assertNotIn((min(src, dst), max(src, dst)), pairs)
        self.assertEqual(counting.src.size, 40)
        self.assertTrue((counting.src < counting.dst).all())

    def test_hub_fallback_lists_nodes(self) -> None:
        """A hub above ``hub_threshold`` loses every edge and is listed with its degree."""
        g = _load(star_graph(10))
        counting = counting_graph(g, hub_threshold=5)
        self.assertEqual(counting.src.size, 0)
        self.assertEqual(counting.dst.size, 0)
        self.assertEqual(counting.dropped_hubs, [(g.node_ids[0], 10)])
        self.assertEqual(counting.removed_edges["hub"], 10)

    def test_removal_none_keeps_everything(self) -> None:
        """``none`` keeps the whole projection, removes nothing and still computes the roles."""
        g = _load(make_sync_design(n_ff=6, reset=True))
        counting = counting_graph(g, removal="none")
        expected = {
            (min(int(u), int(v)), max(int(u), int(v)))
            for u, v in zip(g.src, g.dst, strict=True)
        }
        self.assertEqual(_pairs(counting.src, counting.dst), expected)
        self.assertEqual(set(counting.removed_edges.values()), {0})
        self.assertEqual(counting.dropped_hubs, [])
        self.assertIsNotNone(counting.info)
        info = classify_signals(g)
        clock = [e for e, cls in enumerate(info.edge_class) if CLASS_NAMES[int(cls)] == "clock"]
        self.assertTrue(clock)
        first = clock[0]
        self.assertIn((min(int(g.src[first]), int(g.dst[first])),
                       max(int(g.src[first]), int(g.dst[first]))), expected)

    def test_simple_undirected(self) -> None:
        """Parallel edges merge, a self-loop goes, directions merge and ``src < dst`` holds."""
        g = _load(_small_graph(3, [(0, 1, "I0"), (0, 1, "I1"), (1, 0, "I0"), (0, 0, "I2")]))
        counting = counting_graph(g, removal="none")
        self.assertEqual(counting.src.tolist(), [0])
        self.assertEqual(counting.dst.tolist(), [1])
        self.assertTrue((counting.src < counting.dst).all())

    def test_edge_file_roundtrip(self) -> None:
        """``write_edge_file`` writes the protocol's input; ``read_orbit_file`` its output."""
        import numpy as np

        src = np.asarray([0, 1, 2], dtype=np.int32)
        dst = np.asarray([1, 2, 3], dtype=np.int32)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "edges.txt"
            write_edge_file(path, 4, src, dst)
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], "4 3")
            self.assertEqual(lines[1:], ["0 1", "1 2", "2 3"])
            empty = Path(tmp) / "empty.txt"
            write_edge_file(empty, 4, np.zeros(0, dtype=np.int32), np.zeros(0, dtype=np.int32))
            self.assertEqual(empty.read_text(encoding="utf-8"), "4 0\n")
            orbits = brute_orbits(4, src, dst)
            orbit_path = Path(tmp) / "orbits.txt"
            orbit_path.write_text(
                "".join(" ".join(str(int(v)) for v in row) + "\n" for row in orbits),
                encoding="utf-8",
            )
            read = read_orbit_file(orbit_path, 4, 15)
            self.assertEqual(read.dtype, np.int64)
            np.testing.assert_array_equal(read, orbits)
            with self.assertRaises(ValueError):
                read_orbit_file(orbit_path, 5, 15)
            with self.assertRaises(ValueError):
                read_orbit_file(orbit_path, 4, 14)

    def test_features_roles_appended(self) -> None:
        """Standardised log1p of the non-constant orbits, then the four role columns as is."""
        import numpy as np

        orbits = np.zeros((5, 15), dtype=np.int64)
        orbits[:, 0] = [0, 1, 2, 3, 4]
        orbits[:, 3] = [1, 1, 0, 2, 2]
        roles = np.arange(20, dtype=np.int64).reshape(5, 4)
        x = graphlet_features(orbits, roles)
        self.assertEqual(x.shape, (5, 2 + 4))
        values = np.log1p(orbits[:, [0, 3]].astype(np.float64))
        expected = (values - values.mean(axis=0)) / values.std(axis=0)
        np.testing.assert_allclose(x[:, :2], expected)
        np.testing.assert_array_equal(x[:, 2:], roles)


class RunnerTests(_Registers):
    """``run_graphlets``, ``load_orbits`` and backend selection with fake backends."""

    def test_run_graphlets_outputs(self) -> None:
        """The npz holds int64 orbits, roles and node ids; the JSON has exactly spec 8.6."""
        import numpy as np

        g = _load(make_sync_design(n_ff=4, reset=True))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "graphlets"
            path = run_graphlets(g, "fake", out)
            self.assertEqual(path, out / "graphlets-fake-global.json")
            npz_path = out / "orbits-fake-global.npz"
            self.assertTrue(npz_path.is_file())
            with np.load(npz_path) as data:
                orbits = np.asarray(data["orbits"])
                roles = np.asarray(data["roles"])
                node_ids = np.asarray(data["node_ids"])
            self.assertEqual(orbits.dtype, np.int64)
            self.assertEqual(orbits.shape, (g.n_nodes, 15))
            self.assertEqual(roles.dtype, np.int64)
            self.assertEqual(roles.shape, (g.n_nodes, 4))
            self.assertEqual([str(node_id) for node_id in node_ids], list(g.node_ids))
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(set(record), _JSON_KEYS)
            self.assertEqual(record["schema"], 1)
            self.assertEqual(record["kind"], "graphlets")
            self.assertEqual(record["design"], "sync")
            self.assertEqual(record["floor"], "f2")
            self.assertEqual(record["backend"], "fake")
            self.assertEqual(record["size"], 4)
            self.assertEqual(record["n_orbits"], 15)
            self.assertEqual(record["removal"], "global")
            self.assertEqual(record["hub_threshold"], 1000)
            self.assertEqual(record["signal_config"], {"min_fanout": 16, "dominance": 0.8})
            self.assertEqual(set(record["classified"]), {"clock", "reset", "enable", "const"})
            self.assertEqual(
                set(record["removed_edges"]), {"clock", "reset", "enable", "const", "hub"}
            )
            self.assertEqual(record["clock_domains"], 1)
            self.assertEqual(record["n_nodes"], g.n_nodes)
            self.assertEqual(record["graph_sha256"], g.sha256)
            self.assertEqual(
                record["tool"],
                {
                    "name": "fake",
                    "commit": _FakeCounter.commit,
                    "sha256": _FakeCounter.sha256,
                    "licence": _FakeCounter.licence,
                },
            )
            self.assertEqual(record["dropped_hubs"], [])
            loaded, loaded_roles = load_orbits(g, "fake", "global", out)
            np.testing.assert_array_equal(loaded, orbits)
            np.testing.assert_array_equal(loaded_roles, roles)

    def test_size5_none_refused_without_force(self) -> None:
        """5-node orbits without removal are refused with the spec's message, writing nothing."""
        g = _load(star_graph(3))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "graphlets"
            with self.assertRaises(BackendUnavailable) as caught:
                run_graphlets(g, "fake", out, size=5, removal="none")
            self.assertEqual(
                str(caught.exception),
                "5-node orbits on the full graph did not finish in 30 min; "
                "use --removal global or --force",
            )
            self.assertFalse(out.exists())

    def test_default_backend_is_ext(self) -> None:
        """The spike's decision: ORCA is the default backend (spec 8.5)."""
        self.assertEqual(DEFAULT_BACKEND, "ext")

    def test_unavailable_backend_message(self) -> None:
        """An unavailable backend names itself and carries its reason."""
        self.assertEqual(get_backend("fake").name, "fake")
        with self.assertRaises(BackendUnavailable) as caught:
            get_backend("missing")
        message = str(caught.exception)
        self.assertIn("missing", message)
        self.assertIn(_UnavailableCounter.reason, message)

    def test_zero_edge_graph(self) -> None:
        """A graph of one node and no edges: zero orbits, zero roles, valid files."""
        import numpy as np

        g = _load(star_graph(0))
        self.assertEqual(g.n_edges, 0)
        with tempfile.TemporaryDirectory() as tmp:
            path = run_graphlets(g, "fake", Path(tmp))
            with np.load(Path(tmp) / "orbits-fake-global.npz") as data:
                orbits = np.asarray(data["orbits"])
                roles = np.asarray(data["roles"])
            np.testing.assert_array_equal(orbits, np.zeros((1, 15), dtype=np.int64))
            np.testing.assert_array_equal(roles, np.zeros((1, 4), dtype=np.int64))
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(record["n_edges"], 0)
            self.assertEqual(graphlet_features(orbits, roles).shape, (1, 4))

    def test_int64_survives_npz(self) -> None:
        """Counts above 2**31 keep their int64 value through npz."""
        import numpy as np

        g = _load(star_graph(2))
        with tempfile.TemporaryDirectory() as tmp:
            run_graphlets(g, "big", Path(tmp))
            with np.load(Path(tmp) / "orbits-big-global.npz") as data:
                orbits = np.asarray(data["orbits"])
        self.assertEqual(orbits.dtype, np.int64)
        self.assertTrue(bool((orbits == 2**40).all()))


if __name__ == "__main__":
    unittest.main()
