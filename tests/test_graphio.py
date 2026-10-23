"""L2 Task 2: graph loading, features, undirected projections and dataset iteration."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any

from loki.analysis.graphio import (
    LABEL_COLUMNS_FORBIDDEN,
    NUMERIC_FEATURES,
    canonical_numbers,
    featurize,
    iter_dataset,
    load_graph,
    undirected_adjacency,
    undirected_edges,
)
from loki.schemas import dump_json, split_of
from tests.analysis_fixtures import make_dataset, make_graph, write_graph
from tests.helpers import skip_without


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@skip_without("numpy", "scipy")
class GraphioTest(unittest.TestCase):
    def test_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            obj = make_graph()
            path = write_graph(Path(tmp), obj)
            data = _read(path)
            raw = path.read_bytes()
            g = load_graph(path)
        self.assertEqual(g.design, "d")
        self.assertEqual(g.floor, "f2")
        self.assertEqual(g.n_nodes, len(data["nodes"]))
        self.assertEqual(g.n_edges, len(data["edges"]))
        self.assertEqual(g.sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(list(g.node_ids), [node["id"] for node in data["nodes"]])
        self.assertEqual(g.index(), {node["id"]: i for i, node in enumerate(data["nodes"])})
        first = data["edges"][0]
        self.assertEqual(
            (g.node_ids[int(g.src[0])], g.node_ids[int(g.dst[0])]), (first["src"], first["dst"])
        )
        self.assertEqual((g.pin[0], g.net[0]), (first["pin"], first["net"]))

    def test_load_invalid_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            obj: Any = make_graph()
            obj["nodes"][0]["kind"] = "bogus"
            path = write_graph(Path(tmp), obj)
            with self.assertRaises(ValueError) as ctx:
                load_graph(path)
        self.assertIn("unknown kind 'bogus'", str(ctx.exception))

    def test_features_columns_exact(self) -> None:
        import numpy as np

        with tempfile.TemporaryDirectory() as tmp:
            obj: Any = make_graph()
            luts = [i for i, node in enumerate(obj["nodes"]) if node["kind"] == "lut"]
            obj["nodes"][luts[0]]["features"]["lut_table"] = "9009"
            path = write_graph(Path(tmp), obj)
            data = _read(path)
            matrix = featurize(load_graph(path))
        self.assertEqual(
            NUMERIC_FEATURES,
            ("fan_in", "fan_out", "level", "lut_width", "is_seq", "is_const", "hard_ports",
             "lut_ones"),
        )
        expected = (
            *NUMERIC_FEATURES,
            "kind:pi", "kind:po", "kind:lut", "kind:ff", "kind:const", "kind:hard", "kind:gate",
            "floor:f1-k6", "floor:f1-earch", "floor:f2", "floor:f3",
            "hard:<unk>",
        )
        self.assertEqual(matrix.names, expected)
        self.assertEqual(matrix.x.shape, (len(data["nodes"]), len(expected)))
        self.assertEqual(matrix.x.dtype, np.float32)
        levels = [float(node["features"]["level"]) for node in data["nodes"]]
        self.assertEqual(matrix.x[:, expected.index("level")].tolist(), levels)
        self.assertEqual(float(matrix.x[luts[0], expected.index("lut_ones")]), 4.0)
        self.assertEqual(float(matrix.x[luts[0], expected.index("kind:lut")]), 1.0)
        self.assertEqual(matrix.x[:, expected.index("floor:f2")].tolist(), [1.0] * len(levels))
        self.assertEqual(matrix.hard_types, ())

    def test_features_hard_types_one_hot(self) -> None:
        import numpy as np

        with tempfile.TemporaryDirectory() as tmp:
            loaded = load_graph(write_graph(Path(tmp), make_graph()))
        hard = {"n2": "adder", "n3": "multiplier", "n4": ""}
        kind = tuple(
            "hard" if node_id in hard else node_kind
            for node_id, node_kind in zip(loaded.node_ids, loaded.kind, strict=True)
        )
        assert loaded.labels is not None
        labels = dict(loaded.labels)
        labels["cell_type"] = np.asarray([hard.get(node_id, "") for node_id in loaded.node_ids])
        g = replace(loaded, kind=kind, labels=labels)
        matrix = featurize(g)
        expected = (
            *NUMERIC_FEATURES,
            "kind:pi", "kind:po", "kind:lut", "kind:ff", "kind:const", "kind:hard", "kind:gate",
            "floor:f1-k6", "floor:f1-earch", "floor:f2", "floor:f3",
            "hard:adder", "hard:multiplier", "hard:<unk>",
        )
        self.assertEqual(matrix.names, expected)
        self.assertEqual(matrix.hard_types, ("adder", "multiplier"))
        block = matrix.x[:, [expected.index(name) for name in (
            "hard:adder", "hard:multiplier", "hard:<unk>")]]
        rows = {node_id: block[row].tolist() for row, node_id in enumerate(g.node_ids)}
        self.assertEqual(rows["n2"], [1.0, 0.0, 0.0])
        self.assertEqual(rows["n3"], [0.0, 1.0, 0.0])
        self.assertEqual(rows["n4"], [0.0, 0.0, 1.0])
        for node_id in ("n0", "n1", "n5"):
            self.assertEqual(rows[node_id], [0.0, 0.0, 0.0])
        explicit = featurize(g, hard_types=("multiplier",))
        self.assertEqual(explicit.hard_types, ("multiplier",))
        self.assertEqual(explicit.names[-2:], ("hard:multiplier", "hard:<unk>"))
        explicit_rows = {
            node_id: explicit.x[row, len(explicit.names) - 2:].tolist()
            for row, node_id in enumerate(g.node_ids)
        }
        self.assertEqual(explicit_rows["n3"], [1.0, 0.0])
        self.assertEqual(explicit_rows["n2"], [0.0, 1.0])
        self.assertEqual(explicit_rows["n4"], [0.0, 1.0])
        bare = replace(loaded, kind=kind, labels=None)
        no_labels = featurize(bare)
        self.assertEqual(no_labels.hard_types, ())
        self.assertEqual(no_labels.names[-1], "hard:<unk>")
        unknown = no_labels.x[:, len(no_labels.names) - 1]
        self.assertEqual(unknown[g.index()["n2"]], 1.0)
        self.assertEqual(unknown[g.index()["n4"]], 1.0)
        self.assertEqual(unknown[g.index()["n5"]], 0.0)
        bare_explicit = featurize(bare, hard_types=("adder",))
        self.assertEqual(bare_explicit.hard_types, ("adder",))
        self.assertEqual(bare_explicit.names[-2:], ("hard:adder", "hard:<unk>"))
        last = len(bare_explicit.names) - 1
        self.assertEqual(bare_explicit.x[g.index()["n2"], last], 1.0)
        self.assertEqual(bare_explicit.x[g.index()["n5"], last], 0.0)

    def test_cell_type_hard_block_from_file(self) -> None:
        import numpy as np

        with tempfile.TemporaryDirectory() as tmp:
            obj: Any = make_graph()
            by_id = {node["id"]: node for node in obj["nodes"]}
            hard = {"n2": "adder", "n3": "multiplier", "n4": ""}
            for node_id, cell_type in hard.items():
                by_id[node_id]["kind"] = "hard"
                by_id[node_id]["labels"]["cell_type"] = cell_type
            g = load_graph(write_graph(Path(tmp), obj))
        self.assertIsNotNone(g.labels)
        assert g.labels is not None
        self.assertEqual(
            list(g.labels["cell_type"]),
            [by_id[node_id]["labels"]["cell_type"] for node_id in g.node_ids],
        )
        matrix = featurize(g)
        self.assertEqual(matrix.hard_types, ("adder", "multiplier"))
        columns = [matrix.names.index(name) for name in (
            "hard:adder", "hard:multiplier", "hard:<unk>")]
        rows = {node_id: matrix.x[row, columns].tolist()
                for row, node_id in enumerate(g.node_ids)}
        self.assertEqual(rows["n2"], [1.0, 0.0, 0.0])
        self.assertEqual(rows["n3"], [0.0, 1.0, 0.0])
        self.assertEqual(rows["n4"], [0.0, 0.0, 1.0])
        self.assertEqual(int(np.count_nonzero(matrix.x[:, columns].sum(axis=1))), 3)

    def test_features_exclude_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            obj: Any = make_graph()
            path = write_graph(Path(tmp), obj)
            matrix = featurize(load_graph(path))
        values = {node["labels"]["construct_type"] for node in obj["nodes"]} - {""}
        self.assertTrue(values)
        for name in matrix.names:
            self.assertNotIn(name, LABEL_COLUMNS_FORBIDDEN)
            self.assertNotIn(name, values)
        self.assertNotIn("cell_type", LABEL_COLUMNS_FORBIDDEN)
        self.assertLessEqual(
            {"construct_type", "construct_types", "n_construct_cells", "module_path",
             "bus_name", "bit_index", "role", "n_spans"},
            LABEL_COLUMNS_FORBIDDEN,
        )
        self.assertLessEqual(
            {"hdl_file", "hdl_line", "hdl_col", "hdl_end_line", "hdl_end_col"},
            LABEL_COLUMNS_FORBIDDEN,
        )

    def test_unlabelled_graph(self) -> None:
        import numpy as np

        with tempfile.TemporaryDirectory() as tmp:
            path = write_graph(Path(tmp), make_graph(labels=False))
            g = load_graph(path)
            matrix = featurize(g)
        self.assertIsNone(g.labels)
        self.assertEqual(matrix.x.shape[0], g.n_nodes)
        self.assertEqual(matrix.hard_types, ())
        hard = [j for j, name in enumerate(matrix.names) if name.startswith("hard:")]
        self.assertEqual([matrix.names[j] for j in hard], ["hard:<unk>"])
        for column in hard:
            self.assertEqual(int(np.count_nonzero(matrix.x[:, column])), 0)

    def test_undirected_adjacency_merges_parallel(self) -> None:
        import numpy as np

        with tempfile.TemporaryDirectory() as tmp:
            obj: Any = make_graph(n_lut=2)
            obj["edges"] = [
                {"src": "n2", "dst": "n3", "net": "n7", "pin": "I0"},
                {"src": "n2", "dst": "n3", "net": "n7", "pin": "I1"},
                {"src": "n2", "dst": "n2", "net": "n8", "pin": "I2"},
            ]
            path = write_graph(Path(tmp), obj)
            g = load_graph(path)
            adj = undirected_adjacency(g)
        self.assertEqual(adj.shape, (g.n_nodes, g.n_nodes))
        self.assertEqual(adj.nnz, 2)
        self.assertEqual(int(np.count_nonzero(adj.diagonal())), 0)
        self.assertEqual(adj.dtype, np.float32)
        self.assertEqual(int((adj != adj.T).nnz), 0)
        self.assertEqual(adj.data.tolist(), [1.0, 1.0])

    def test_induced_keeps_features(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_graph(Path(tmp), make_graph(n_lut=4))
            g = load_graph(path)
            keep = ("n0", "n1", "n2", "n3")
            sub = g.induced(keep)
        self.assertEqual(sub.node_ids, keep)
        self.assertEqual(sub.n_nodes, 4)
        self.assertEqual(sub.kind, g.kind[:4])
        inside = {g.index()[nid] for nid in keep}
        expected_edges = sum(
            1 for src, dst in zip(g.src.tolist(), g.dst.tolist(), strict=True)
            if src in inside and dst in inside
        )
        self.assertEqual(sub.n_edges, expected_edges)
        full_fan_in = {g.node_ids[i]: int(g.num["fan_in"][i]) for i in range(g.n_nodes)}
        for row, nid in enumerate(sub.node_ids):
            self.assertEqual(int(sub.num["fan_in"][row]), full_fan_in[nid])
        assert sub.labels is not None and g.labels is not None
        self.assertEqual(
            sub.labels["construct_type"].tolist(), g.labels["construct_type"][:4].tolist()
        )
        self.assertEqual(g.induced(("n3", "n0")).node_ids, ("n0", "n3"))

    def test_iter_dataset_skips_non_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_dataset(Path(tmp), designs=4)
            manifest_path = root / "manifest.json"
            manifest: Any = _read(manifest_path)
            manifest["designs"][0]["floors"]["f2"]["status"] = "skipped"
            manifest_path.write_text(dump_json(manifest), encoding="utf-8")
            entries = list(iter_dataset(root, "f2"))
            self.assertEqual(list(iter_dataset(root, "f1-earch")), [])
            for entry in entries:
                self.assertEqual(entry.floor, "f2")
                self.assertEqual(entry.split, split_of(entry.design))
                self.assertEqual(entry.graph_path, root / entry.design / "f2" / "graph.json")
                self.assertTrue(entry.graph_path.is_file())
        self.assertEqual([entry.design for entry in entries], ["micro_a1", "micro_a2", "micro_a3"])

    def test_zero_edge_graph(self) -> None:
        import numpy as np

        with tempfile.TemporaryDirectory() as tmp:
            obj: Any = make_graph()
            obj["edges"] = []
            path = write_graph(Path(tmp), obj)
            g = load_graph(path)
            adj = undirected_adjacency(g)
            src, dst = undirected_edges(g)
        self.assertEqual(g.n_edges, 0)
        self.assertEqual(g.n_nodes, 17)
        self.assertEqual(adj.shape, (17, 17))
        self.assertEqual(adj.nnz, 0)
        self.assertEqual(src.size, 0)
        self.assertEqual(dst.size, 0)
        self.assertEqual(src.dtype, np.int32)
        self.assertEqual(dst.dtype, np.int32)

    def test_canonical_numbers(self) -> None:
        import numpy as np

        out = canonical_numbers(np.asarray([5, 5, 2, 9, 2]))
        self.assertEqual(out.tolist(), [0, 0, 1, 2, 1])
        self.assertEqual(canonical_numbers(np.asarray([0, 1, 2])).tolist(), [0, 1, 2])
        self.assertEqual(canonical_numbers(np.zeros(0, dtype=np.int64)).tolist(), [])


if __name__ == "__main__":
    unittest.main()
