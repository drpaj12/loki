import unittest
from typing import Any

from loki.anon import number
from loki.graph import build_graph, levels, lut_table_hex
from loki.labels import build_labels
from loki.model import FinalCell, Net, Netlist, Port, PortBit, Snapshot
from loki.schemas import validate_graph
from tests.helpers import lut_cell


def chain() -> Netlist:
    nets = {i: Net(i, ()) for i in (1, 2, 3)}
    cells = (lut_cell(10, [1], 2, "01"), lut_cell(11, [2], 3, "10"))
    return Netlist("top", nets, cells, (PortBit("A", "in", 1), PortBit("X", "out", 3)))


def graph_of(nl: Netlist) -> dict[str, Any]:
    num = number(nl)
    labels, _ = build_labels(nl, Snapshot((), (), "top"), num, {}, "/p")
    g, _ = build_graph(nl, labels, num, "d", "f2")
    return dict(g)


class GraphTest(unittest.TestCase):
    def test_level_chain(self) -> None:
        lv, loops = levels(chain())
        self.assertEqual((lv, loops), ({10: 1, 11: 2}, 0))
        g = graph_of(chain())
        by = {n["id"]: n["features"]["level"] for n in g["nodes"]}
        self.assertEqual(by, {"n3": 1, "n4": 2, "n5": 0, "n6": 3})

    def test_level_with_loop(self) -> None:
        nets = {i: Net(i, ()) for i in (1, 2, 3)}
        cells = (lut_cell(10, [1, 3], 2, "0110"), lut_cell(11, [2], 3, "01"))
        nl = Netlist("t", nets, cells, (PortBit("A", "in", 1),))
        lv, loops = levels(nl)
        self.assertGreaterEqual(loops, 1)
        self.assertEqual(set(lv), {10, 11})

    def test_ff_breaks_levels(self) -> None:
        nets = {i: Net(i, ()) for i in (1, 2, 3, 4)}
        ff = FinalCell(12, "ff", "$_DFF_P_", "", {}, (), (Port("C", 1, (1,)), Port("D", 1, (3,))),
                       (Port("Q", 1, (2,)),))
        cells = (lut_cell(10, [2], 3, "01"), ff, lut_cell(11, [2, 3], 4, "0110"))
        nl = Netlist("t", nets, cells, (PortBit("C", "in", 1),))
        lv, loops = levels(nl)
        self.assertEqual((lv[12], lv[10], lv[11], loops), (0, 1, 2, 0))

    def test_graph_edges_and_features(self) -> None:
        nets = {i: Net(i, ()) for i in (1, 2, 3, 4)}
        cells = (lut_cell(10, [1, 2], 3, "0001"), lut_cell(11, [3, 1], 4, "0110"))
        pbs = (PortBit("A", "in", 1), PortBit("B", "in", 2), PortBit("X", "out", 4))
        g = graph_of(Netlist("top", nets, cells, pbs))
        nodes = {n["id"]: n for n in g["nodes"]}
        f = nodes["n4"]["features"]
        got = (f["fan_in"], f["fan_out"], f["lut_width"], f["lut_table"])
        self.assertEqual(got, (2, 1, 2, "1"))
        self.assertEqual(nodes["n5"]["features"]["lut_table"], "6")
        self.assertEqual(nodes["n6"]["features"]["fan_out"], 2)  # PI A reads: both LUTs
        edges = {(e["src"], e["dst"], e["pin"]) for e in g["edges"]}
        self.assertIn(("n4", "n5", "I0"), edges)
        self.assertIn(("n6", "n5", "I1"), edges)
        self.assertIn(("n5", "n8", "I"), edges)
        self.assertEqual(len(edges), 5)

    def test_lut_table_hex(self) -> None:
        self.assertEqual(lut_table_hex("1001000000001001"), "9009")
        self.assertEqual(lut_table_hex("1"), "1")
        self.assertEqual(lut_table_hex("0010"), "2")

    def test_graph_validates(self) -> None:
        self.assertEqual(validate_graph(graph_of(chain())), [])

    def test_label_mismatch_raises(self) -> None:
        nl = chain()
        with self.assertRaises(ValueError):
            build_graph(nl, [], number(nl), "d", "f2")


if __name__ == "__main__":
    unittest.main()
