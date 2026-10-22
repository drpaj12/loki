import csv
import io
import unittest

from loki.anon import number
from loki.labels import (
    Label,
    build_labels,
    bus_bit,
    labels_to_csv,
    match_words,
    module_path,
)
from loki.model import FinalCell, InstanceSite, Net, Netlist, PortBit, Snapshot, Span, WordCell
from loki.schemas import LABEL_COLUMNS, validate_labels_csv
from tests.helpers import lut_cell

DEF = Span("/p/a.v", 2, 1, 2, 9)
I1 = Span("/p/a.v", 6, 3, 6, 20)
I2 = Span("/p/a.v", 7, 3, 7, 20)
EQ = Span("/p/a.v", 12, 6, 12, 12)
M1 = Span("/p/a.v", 14, 1, 14, 5)
M2 = Span("/p/a.v", 15, 1, 15, 5)


def word(wid: int, typ: str, spans: tuple[Span, ...]) -> WordCell:
    return WordCell(wid, typ, "", {}, spans, (), (), False)


SITES = (InstanceSite(I1, "u1", "sub", "top"), InstanceSite(I2, "u2", "sub", "top"))


class LabelsTest(unittest.TestCase):
    def test_two_instances_not_confused(self) -> None:
        w1, w2 = word(1, "$add", (DEF, I1)), word(2, "$add", (DEF, I2))
        cell = lut_cell(10, [1], 2, "01", (DEF, I2))
        self.assertEqual([w.id for w in match_words(cell, [w1, w2])], [2])
        self.assertEqual(module_path((DEF, I2), SITES, "top"), "top/u2")
        self.assertEqual(module_path((DEF,), SITES, "top"), "top")

    def test_nested_chain(self) -> None:
        mid = Span("/p/a.v", 20, 1, 20, 9)
        leaf = Span("/p/a.v", 30, 1, 30, 9)
        sites = (
            InstanceSite(leaf, "l1", "leaf", "mid"),
            InstanceSite(mid, "m1", "mid", "top"),
        )
        self.assertEqual(module_path((DEF, leaf, mid), sites, "top"), "top/m1/l1")
        # Odin III lists only the innermost instantiation span: climb to the one parent.
        self.assertEqual(module_path((DEF, leaf), sites, "top"), "top/m1/l1")

    def test_ambiguous_parent_is_star(self) -> None:
        mid1, mid2 = Span("/p/a.v", 20, 1, 20, 9), Span("/p/a.v", 21, 1, 21, 9)
        leaf = Span("/p/a.v", 30, 1, 30, 9)
        sites = (
            InstanceSite(leaf, "l1", "leaf", "mid"),
            InstanceSite(mid1, "m1", "mid", "top"),
            InstanceSite(mid2, "m2", "mid", "top"),
            InstanceSite(leaf, "dead", "leaf", "unused"),
        )
        self.assertEqual(module_path((DEF, leaf), sites, "top"), "top/*/l1")

    def test_lut_merged_across_instances_is_ambiguous(self) -> None:
        w1, w2 = word(1, "$add", (DEF, I1)), word(2, "$add", (DEF, I2))
        cell = lut_cell(10, [1], 2, "01", (DEF, I1, I2))
        nl = Netlist("top", {1: Net(1, ()), 2: Net(2, ())}, (cell,), ())
        snap = Snapshot((w1, w2), SITES, "top")
        (lab,), _ = build_labels(nl, snap, number(nl), {1: "datapath", 2: "datapath"}, "/p")
        self.assertEqual(lab.module_path, "top/*")
        self.assertEqual(module_path((DEF, I1, I2), SITES, "top"), "top/*")

    def test_identical_span_words_are_ambiguous(self) -> None:
        # nested2: m1.l1 and m2.l1 give two $sub words with identical spans
        leaf = Span("/p/a.v", 30, 1, 30, 9)
        w1, w2 = word(1, "$sub", (DEF, leaf)), word(2, "$sub", (DEF, leaf))
        cell = lut_cell(10, [1], 2, "01", (DEF, leaf))
        nl = Netlist("top", {1: Net(1, ()), 2: Net(2, ())}, (cell,), ())
        snap = Snapshot((w1, w2), (), "top")
        (lab,), ids = build_labels(nl, snap, number(nl), {1: "datapath", 2: "datapath"}, "/p")
        self.assertEqual((lab.n_construct_cells, lab.role, lab.ambiguous), (1, "unknown", True))
        self.assertEqual(lab.construct_types, "$sub")
        self.assertEqual(ids[10], (1, 2))
        # a distinct second construct keeps its own role
        eq = word(3, "$eq", (EQ,))
        cell2 = lut_cell(11, [1], 2, "01", (DEF, leaf, EQ))
        nl2 = Netlist("top", {1: Net(1, ()), 2: Net(2, ())}, (cell2,), ())
        snap2 = Snapshot((w1, w2, eq), (), "top")
        roles = {1: "datapath", 2: "datapath", 3: "control"}
        (lab2,), _ = build_labels(nl2, snap2, number(nl2), roles, "/p")
        self.assertEqual((lab2.n_construct_cells, lab2.role), (2, "control"))

    def test_match_order_and_primary(self) -> None:
        eq = word(1, "$eq", (EQ,))
        mux = word(2, "$mux", (M1, M2))
        cell = lut_cell(10, [1], 2, "01", (EQ, M1, M2))
        self.assertEqual([w.type for w in match_words(cell, [eq, mux])], ["$mux", "$eq"])
        nl = Netlist("top", {1: Net(1, ()), 2: Net(2, ())}, (cell,), ())
        snap = Snapshot((eq, mux), (), "top")
        (lab,), ids = build_labels(nl, snap, number(nl), {1: "control", 2: "datapath"}, "/p")
        self.assertEqual(lab.construct_types, "$mux|$eq")
        self.assertEqual(lab.construct_type, "$eq")
        self.assertEqual((lab.n_construct_cells, lab.role), (2, "mixed"))
        self.assertEqual(ids, {10: (2, 1)})
        self.assertEqual((lab.hdl_file, lab.hdl_line, lab.n_spans), ("a.v", 12, 3))

    def test_no_match_is_unknown(self) -> None:
        cell = lut_cell(10, [1], 2, "01", (EQ,))
        nl = Netlist("top", {1: Net(1, ()), 2: Net(2, ())}, (cell,), ())
        (lab,), ids = build_labels(nl, Snapshot((), (), "top"), number(nl), {}, "/p")
        self.assertEqual((lab.construct_type, lab.role, lab.n_construct_cells), ("", "unknown", 0))
        self.assertEqual(ids[10], ())

    def test_bus_bit_from_alias(self) -> None:
        def nl_with(names: tuple[str, ...]) -> tuple[FinalCell, Netlist]:
            c = lut_cell(10, [1], 2, "01")
            return c, Netlist("t", {1: Net(1, ()), 2: Net(2, names)}, (c,), ())

        self.assertEqual(bus_bit(*nl_with(("", "AeqB[0]"))), ("AeqB", 0))
        self.assertEqual(bus_bit(*nl_with(("x",))), ("x", -1))
        self.assertEqual(bus_bit(*nl_with(())), ("", -1))
        self.assertEqual(bus_bit(*nl_with(("x", "bus[3]"))), ("bus", 3))

    def test_hdl_file_relative_and_ports(self) -> None:
        port = PortBit("A[1]", "in", 1, (Span("/p/sub/a.v", 4, 2, 4, 16),))
        nl = Netlist("top", {1: Net(1, ())}, (), (port,))
        (lab,), _ = build_labels(nl, Snapshot((), (), "top"), number(nl), {}, "/p")
        self.assertEqual((lab.hdl_file, lab.role, lab.kind), ("sub/a.v", "io", "pi"))
        self.assertEqual((lab.bus_name, lab.bit_index), ("A", 1))

    def test_labels_cover_every_node(self) -> None:
        cell = lut_cell(10, [1], 2, "01", (EQ,))
        pbs = (PortBit("A", "in", 1), PortBit("X", "out", 2))
        nl = Netlist("top", {1: Net(1, ()), 2: Net(2, ())}, (cell,), pbs)
        labels, _ = build_labels(nl, Snapshot((), (), "top"), number(nl), {}, "/p")
        self.assertEqual([x.kind for x in labels], ["lut", "pi", "po"])
        self.assertEqual([x.node_id for x in labels], ["n2", "n3", "n4"])

    def test_csv_roundtrip_with_commas(self) -> None:
        lab = Label("n1", "lut", "$lut", "$eq", "$eq", 1, 'top/u 1,"x"', "b", 0, "datapath",
                    "d,ir/a b.v", 1, 2, 3, 4, 1)
        text = labels_to_csv([lab])
        self.assertEqual(validate_labels_csv(text), [])
        rows = list(csv.reader(io.StringIO(text)))
        self.assertEqual(tuple(rows[0]), LABEL_COLUMNS)
        self.assertEqual(rows[1][6], 'top/u 1,"x"')
        self.assertEqual(rows[1][10], "d,ir/a b.v")


if __name__ == "__main__":
    unittest.main()
