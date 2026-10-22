import dataclasses
import unittest

from loki.features.graph import (
    FeatureGraph,
    from_graph_json,
    make_feature_graph,
    validate_feature_graph,
)
from tests.features_fixtures import ripple_adder_fg


def example() -> dict[str, object]:
    def node(nid: str, kind: str, width: int, table: str) -> dict[str, object]:
        return {"id": nid, "kind": kind,
                "features": {"lut_width": width, "lut_table": table}, "labels": {}}

    return {
        "schema": 1,
        "nodes": [node("n17", "lut", 4, "9009"), node("n40", "po", 0, "")],
        "edges": [{"src": "n17", "dst": "n40", "net": "n3", "pin": "I0"}],
    }


class FeatureGraphTest(unittest.TestCase):
    def test_from_graph_json_example(self) -> None:
        fg = from_graph_json(example())
        self.assertEqual(fg.node_ids, ("n17", "n40"))
        self.assertEqual((fg.kind, fg.width, fg.table), (("lut", "po"), (4, 0), (0x9009, -1)))
        self.assertEqual((fg.src, fg.dst, fg.pin, fg.net), ((0,), (1,), ("I0",), (3,)))
        self.assertEqual(validate_feature_graph(fg), [])

    def test_edges_sorted_by_dst_pin_src(self) -> None:
        fg = make_feature_graph(
            [("a", "pi", "pi", 0, -1), ("b", "pi", "pi", 0, -1), ("c", "lut", "lut", 2, 8)],
            [(1, 2, "I1", 1), (0, 2, "I1", 0), (1, 2, "I0", 1)],
        )
        self.assertEqual(fg.pin, ("I0", "I1", "I1"))
        self.assertEqual(fg.src, (1, 0, 1))
        self.assertEqual(validate_feature_graph(fg), [])

    def test_adjacency_cached(self) -> None:
        fg = ripple_adder_fg(2)
        ins, outs = fg.adjacency()
        self.assertIs(fg.adjacency()[0], ins)
        self.assertEqual(sum(len(x) for x in ins), fg.n_edges)
        self.assertEqual(sum(len(x) for x in outs), fg.n_edges)
        self.assertEqual(fg, dataclasses.replace(fg))

    def test_validate_feature_graph(self) -> None:
        fg = from_graph_json(example())
        bad = FeatureGraph(fg.node_ids, fg.kind, fg.type, fg.width, fg.table,
                           (0,), (5,), ("I0",), (3,))
        self.assertTrue(any("dst 5" in e for e in validate_feature_graph(bad)))
        unsorted = FeatureGraph(fg.node_ids, fg.kind, fg.type, fg.width, fg.table,
                                (0, 0), (1, 0), ("I0", "I0"), (3, 3))
        self.assertTrue(any("not sorted" in e for e in validate_feature_graph(unsorted)))
        ragged = FeatureGraph(fg.node_ids, fg.kind[:1], fg.type, fg.width, fg.table,
                              (), (), (), ())
        self.assertTrue(validate_feature_graph(ragged))


if __name__ == "__main__":
    unittest.main()
