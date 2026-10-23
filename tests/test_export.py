"""L2 Task 4: edge-list and GraphML exports (L2 spec section 5)."""

from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from loki.analysis.export import export_graph
from loki.analysis.graphio import featurize, load_graph
from loki.analysis.region import cone, region_hash
from tests.analysis_fixtures import make_graph, write_graph
from tests.helpers import skip_without

_LABELS = {
    "construct_type": "", "construct_types": "", "n_construct_cells": -1, "module_path": "",
    "bus_name": "", "bit_index": -1, "role": "unknown", "hdl_file": "", "hdl_line": -1,
    "hdl_col": -1, "hdl_end_line": -1, "hdl_end_col": -1, "n_spans": 0,
}


def _zero_edge_obj() -> dict[str, object]:
    """A valid ``graph.json`` with one PI node and no edges."""
    features = {
        "fan_in": 0, "fan_out": 0, "level": 0, "lut_width": 0, "lut_table": "",
        "is_seq": 0, "is_const": 0, "hard_ports": 0,
    }
    node = {"id": "n0", "kind": "pi", "features": features, "labels": dict(_LABELS)}
    return {"schema": 1, "design": "empty", "floor": "f2", "nodes": [node], "edges": []}


@skip_without("numpy", "scipy")
class ExportTest(unittest.TestCase):
    def test_edgelist_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_graph(root, make_graph())
            data: Any = json.loads(path.read_text(encoding="utf-8"))
            g = load_graph(path)
            out = root / "export"
            paths = export_graph(g, None, ["edgelist"], out)
            self.assertEqual(
                sorted(p.name for p in paths), ["whole.edges.tsv", "whole.nodes.tsv"]
            )
            edges = (out / "whole.edges.tsv").read_text(encoding="utf-8").splitlines()
            self.assertEqual(
                edges, [f"{edge['src']}\t{edge['dst']}" for edge in data["edges"]]
            )
            rows = (out / "whole.nodes.tsv").read_text(encoding="utf-8").splitlines()
            matrix = featurize(g)
            header = rows[0].split("\t")
            self.assertEqual(header[:2], ["id", "kind"])
            self.assertEqual(header[2:2 + len(matrix.names)], list(matrix.names))
            self.assertEqual(header[2], "fan_in")
            self.assertIn("lut_ones", header)
            labels = list(g.labels or {})
            self.assertEqual(header[2 + len(matrix.names):], labels)
            self.assertEqual(len(rows), 1 + g.n_nodes)
            construct = 2 + len(matrix.names) + labels.index("construct_type")
            for row, node in enumerate(data["nodes"]):
                cells = rows[row + 1].split("\t")
                self.assertEqual(cells[:2], [node["id"], node["kind"]])
                self.assertEqual(cells[2], str(node["features"]["fan_in"]))
                self.assertEqual(cells[construct], node["labels"]["construct_type"])
            plain = root / "plain"
            write_graph(plain, make_graph(labels=False))
            g_plain = load_graph(plain / "graph.json")
            export_graph(g_plain, None, ["edgelist"], plain / "export")
            plain_rows = (plain / "export" / "whole.nodes.tsv").read_text(
                encoding="utf-8"
            ).splitlines()
            self.assertEqual(len(plain_rows), 1 + g_plain.n_nodes)
            plain_header = plain_rows[0].split("\t")
            self.assertNotIn("construct_type", plain_header)
            self.assertEqual(len(plain_header), 2 + len(featurize(g_plain).names))

    @skip_without("networkx")
    def test_graphml_roundtrip(self) -> None:
        nx: Any = importlib.import_module("networkx")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_graph(root, make_graph())
            data: Any = json.loads(path.read_text(encoding="utf-8"))
            g = load_graph(path)
            paths = export_graph(g, None, ["graphml"], root / "export")
            self.assertEqual([p.name for p in paths], ["whole.graphml"])
            graph: Any = nx.read_graphml(root / "export" / "whole.graphml")
            self.assertEqual(graph.number_of_nodes(), len(data["nodes"]))
            self.assertEqual(graph.number_of_edges(), len(data["edges"]))
            self.assertEqual(graph.graph["design"], "d")
            self.assertEqual(graph.graph["floor"], "f2")
            for node in data["nodes"]:
                attrs = graph.nodes[node["id"]]
                self.assertEqual(attrs["fan_in"], node["features"]["fan_in"])
                self.assertEqual(attrs["construct_type"], node["labels"]["construct_type"])
            for edge in data["edges"]:
                attrs = graph.edges[edge["src"], edge["dst"]]
                self.assertEqual(attrs["pin"], edge["pin"])
                self.assertEqual(attrs["net"], edge["net"])

    def test_region_export_is_induced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_graph(root, make_graph())
            data: Any = json.loads(path.read_text(encoding="utf-8"))
            g = load_graph(path)
            region = cone(g, [data["nodes"][-1]["id"]], "in", 1)
            paths = export_graph(g, region, ["edgelist"], root / "export")
            stem = f"region-{region_hash(region.spec)}"
            self.assertEqual(
                sorted(p.name for p in paths), [f"{stem}.edges.tsv", f"{stem}.nodes.tsv"]
            )
            inside = set(region.node_ids)
            self.assertLess(len(inside), g.n_nodes)
            lines = (root / "export" / f"{stem}.edges.tsv").read_text(
                encoding="utf-8"
            ).splitlines()
            expected = [
                f"{edge['src']}\t{edge['dst']}" for edge in data["edges"]
                if edge["src"] in inside and edge["dst"] in inside
            ]
            self.assertEqual(lines, expected)
            rows = (root / "export" / f"{stem}.nodes.tsv").read_text(
                encoding="utf-8"
            ).splitlines()
            self.assertEqual(len(rows), 1 + len(region.node_ids))
            measured = {node["id"]: node["features"] for node in data["nodes"]}
            for row, node_id in zip(rows[1:], region.node_ids, strict=True):
                cells = row.split("\t")
                self.assertEqual(cells[0], node_id)
                self.assertEqual(int(cells[2]), measured[node_id]["fan_in"])

    def test_export_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_graph(root, make_graph())
            g = load_graph(root / "graph.json")
            first = export_graph(g, None, ["graphml", "edgelist"], root / "a")
            second = export_graph(g, None, ["graphml", "edgelist"], root / "b")
            self.assertEqual([p.name for p in first], [p.name for p in second])
            for left, right in zip(first, second, strict=True):
                self.assertEqual(left.read_bytes(), right.read_bytes())

    def test_unknown_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_graph(root, make_graph())
            g = load_graph(root / "graph.json")
            out = root / "export"
            with self.assertRaises(ValueError) as ctx:
                export_graph(g, None, ["edgelist", "parquet"], out)
            self.assertIn("parquet", str(ctx.exception))
            self.assertFalse(out.exists())

    @skip_without("networkx")
    def test_zero_edge_graph_exports(self) -> None:
        nx: Any = importlib.import_module("networkx")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_graph(root, _zero_edge_obj())
            g = load_graph(root / "graph.json")
            self.assertEqual(g.n_edges, 0)
            export_graph(g, None, ["edgelist", "graphml"], root / "export")
            edges = (root / "export" / "whole.edges.tsv").read_text(encoding="utf-8")
            self.assertEqual(edges, "")
            rows = (root / "export" / "whole.nodes.tsv").read_text(
                encoding="utf-8"
            ).splitlines()
            self.assertEqual(len(rows), 1 + g.n_nodes)
            graph: Any = nx.read_graphml(root / "export" / "whole.graphml")
            self.assertEqual(graph.number_of_nodes(), 1)
            self.assertEqual(graph.number_of_edges(), 0)
            self.assertEqual(graph.graph["floor"], "f2")


if __name__ == "__main__":
    unittest.main()
