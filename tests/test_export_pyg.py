"""L2 Task 5: PyTorch Geometric export (L2 spec section 5)."""

from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from loki.analysis.export import (
    FORMATS,
    build_vocab_for_graph,
    export_graph,
    load_pyg,
    pyg_dict,
    write_pyg,
)
from loki.analysis.graphio import featurize, load_graph
from loki.analysis.region import cone, region_hash
from tests.analysis_fixtures import make_graph, write_graph
from tests.helpers import skip_without


def _partially_labelled() -> dict[str, Any]:
    """The fixture graph with the first LUT's construct type emptied, the rest labelled."""
    obj: dict[str, Any] = make_graph()
    labels = obj["nodes"][2]["labels"]
    labels["construct_type"] = ""
    labels["construct_types"] = ""
    labels["module_path"] = ""
    return obj


@skip_without("torch", "torch_geometric")
class PygExportTest(unittest.TestCase):
    def test_pyg_dict_shapes(self) -> None:
        torch: Any = importlib.import_module("torch")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_graph(root, make_graph())
            first: Any = json.loads(path.read_text(encoding="utf-8"))["edges"][0]
            g = load_graph(path)
            matrix = featurize(g)
            payload = pyg_dict(g)
            x: Any = payload["x"]
            edge_index: Any = payload["edge_index"]
            self.assertEqual(tuple(x.shape), (g.n_nodes, len(matrix.names)))
            self.assertEqual(x.dtype, torch.float32)
            self.assertTrue(torch.equal(x, torch.from_numpy(matrix.x)))
            self.assertEqual(tuple(edge_index.shape), (2, g.n_edges))
            self.assertEqual(edge_index.dtype, torch.int64)
            self.assertEqual(edge_index[0].tolist(), [int(row) for row in g.src])
            self.assertEqual(edge_index[1].tolist(), [int(row) for row in g.dst])
            self.assertEqual(g.node_ids[int(edge_index[0][0])], first["src"])
            self.assertEqual(payload["node_ids"], list(g.node_ids))
            self.assertEqual(payload["feature_names"], list(matrix.names))
            self.assertEqual(payload["hard_types"], list(matrix.hard_types))
            self.assertEqual(payload["design"], "d")
            self.assertEqual(payload["floor"], "f2")
            self.assertNotIn("split", payload)

    def test_pyg_label_vocab_and_minus_one(self) -> None:
        torch: Any = importlib.import_module("torch")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_graph(root, _partially_labelled())
            g = load_graph(path)
            labels = g.labels
            if labels is None:
                self.fail("fixture must stay labelled")
            vocab = build_vocab_for_graph(g)
            self.assertEqual(sorted(vocab), ["construct_type", "role"])
            self.assertEqual(
                vocab["construct_type"], ["$add", "$dff", "$eq", "$port_in", "$port_out"]
            )
            self.assertEqual(vocab["role"], ["control", "datapath", "io"])
            payload = pyg_dict(g)
            self.assertEqual(payload["vocab"], vocab)
            construct: Any = payload["y_construct_type"]
            role: Any = payload["y_role"]
            self.assertEqual(construct.dtype, torch.int64)
            self.assertEqual(role.dtype, torch.int64)
            self.assertEqual(tuple(construct.shape), (g.n_nodes,))
            names = vocab["construct_type"]
            rows = {node_id: row for row, node_id in enumerate(g.node_ids)}
            encoded = construct.tolist()
            self.assertEqual(encoded[rows["n2"]], -1)
            self.assertEqual(encoded[rows["n0"]], names.index("$port_in"))
            self.assertEqual(encoded[rows["n1"]], names.index("$port_in"))
            po = g.node_ids[-1]
            self.assertEqual(g.kind[rows[po]], "po")
            self.assertEqual(encoded[rows[po]], names.index("$port_out"))
            for row, value in enumerate(labels["construct_type"].tolist()):
                self.assertEqual(encoded[row], -1 if not value else names.index(value))
            encoded_role = role.tolist()
            for row, value in enumerate(labels["role"].tolist()):
                self.assertEqual(encoded_role[row], vocab["role"].index(value))

    def test_pyg_split_passed_through(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_graph(root, make_graph())
            g = load_graph(root / "graph.json")
            self.assertEqual(pyg_dict(g, split="train")["split"], "train")
            write_pyg(g, root / "export" / "whole.pt", split="train")
            loaded: Any = load_pyg(root / "export" / "whole.pt")
            self.assertEqual(loaded.split, "train")

    def test_pyg_unlabelled_has_no_y(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_graph(root, make_graph(labels=False))
            g = load_graph(path)
            self.assertIsNone(g.labels)
            self.assertEqual(
                build_vocab_for_graph(g), {"construct_type": [], "role": []}
            )
            payload = pyg_dict(g)
            self.assertEqual(payload["vocab"], {"construct_type": [], "role": []})
            self.assertNotIn("y_construct_type", payload)
            self.assertNotIn("y_role", payload)
            self.assertIn("x", payload)
            self.assertIn("edge_index", payload)

    def test_load_pyg_weights_only(self) -> None:
        torch: Any = importlib.import_module("torch")
        data_module: Any = importlib.import_module("torch_geometric.data")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_graph(root, make_graph())
            g = load_graph(root / "graph.json")
            payload = pyg_dict(g)
            path = write_pyg(g, root / "export" / "whole.pt")
            self.assertEqual(path, root / "export" / "whole.pt")
            raw: Any = torch.load(path, weights_only=True)
            self.assertIsInstance(raw, dict)
            loaded: Any = load_pyg(path)
            self.assertIsInstance(loaded, data_module.Data)
            for name in ("x", "edge_index", "y_construct_type", "y_role"):
                self.assertTrue(torch.equal(getattr(loaded, name), payload[name]), name)
            self.assertEqual(loaded.node_ids, payload["node_ids"])
            self.assertEqual(loaded.feature_names, payload["feature_names"])
            self.assertEqual(loaded.hard_types, payload["hard_types"])
            self.assertEqual(loaded.vocab, payload["vocab"])
            self.assertEqual(loaded.design, "d")
            self.assertEqual(loaded.floor, "f2")

    def test_pyg_region(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_graph(root, make_graph())
            data: Any = json.loads(path.read_text(encoding="utf-8"))
            g = load_graph(path)
            region = cone(g, [data["nodes"][-1]["id"]], "in", 1)
            paths = export_graph(g, region, ["pyg"], root / "export")
            stem = f"region-{region_hash(region.spec)}"
            self.assertEqual([p.name for p in paths], [f"{stem}.pt"])
            loaded: Any = load_pyg(root / "export" / f"{stem}.pt")
            self.assertEqual(loaded.node_ids, list(region.node_ids))
            self.assertEqual(loaded.num_nodes, len(region.node_ids))
            self.assertEqual(
                tuple(loaded.x.shape), (len(region.node_ids), len(featurize(g).names))
            )
            edge_index: Any = loaded.edge_index
            inside = set(region.node_ids)
            expected = [
                edge for edge in data["edges"]
                if edge["src"] in inside and edge["dst"] in inside
            ]
            self.assertEqual(tuple(edge_index.shape), (2, len(expected)))
            for row in edge_index.tolist():
                for index in row:
                    self.assertTrue(0 <= index < len(region.node_ids))
            self.assertEqual(
                edge_index[0].tolist(),
                [region.node_ids.index(edge["src"]) for edge in expected],
            )

    def test_export_graph_pyg_format_listed(self) -> None:
        torch: Any = importlib.import_module("torch")
        self.assertIn("pyg", FORMATS)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_graph(root, make_graph())
            g = load_graph(root / "graph.json")
            paths = export_graph(g, None, ["edgelist", "pyg"], root / "export")
            self.assertEqual(
                sorted(p.name for p in paths),
                ["whole.edges.tsv", "whole.nodes.tsv", "whole.pt"],
            )
            only = export_graph(g, None, ["pyg"], root / "only-pyg")
            self.assertEqual([p.name for p in only], ["whole.pt"])
            loaded: Any = load_pyg(root / "export" / "whole.pt")
            payload = pyg_dict(g)
            self.assertEqual(loaded.num_nodes, g.n_nodes)
            self.assertTrue(torch.equal(loaded.x, payload["x"]))
            self.assertTrue(torch.equal(loaded.edge_index, payload["edge_index"]))


if __name__ == "__main__":
    unittest.main()
