import tempfile
import unittest
from pathlib import Path

from loki.score.gt import (
    SCORED_TYPES,
    GtInstance,
    derive_instances,
    label_buses,
    load_gt,
    load_netmap,
)
from tests.helpers import write_fake_floor


def word(i: int, typ: str, foot: list[str], **kw: object) -> dict[str, object]:
    return {"id": i, "type": typ, "params": kw.get("params", {}), "fsm": kw.get("fsm", False),
            "role": "unknown", "const_ports": kw.get("const_ports", []), "footprint": foot}


def edge(s: int, sp: str, d: int, dp: str) -> dict[str, object]:
    return {"src": s, "src_port": sp, "dst": d, "dst_port": dp}


def by_type(insts: list[GtInstance], typ: str) -> list[GtInstance]:
    return [i for i in insts if i.type == typ]


class DeriveTest(unittest.TestCase):
    def test_gt_counter_rule(self) -> None:
        words = {"words": [
            word(1, "$dff", ["n1", "n2"], params={"WIDTH": 2}),
            word(2, "$add", ["n3"], const_ports=["B"]),
            word(3, "$mux", ["n4"]),
        ], "edges": [edge(1, "Q", 2, "A"), edge(2, "Y", 3, "A"), edge(3, "Y", 1, "D")]}
        insts = derive_instances(words)
        counters = by_type(insts, "counter")
        self.assertEqual(len(counters), 1)
        self.assertEqual(counters[0].footprint, frozenset({"n1", "n2", "n3", "n4"}))
        self.assertEqual(len(by_type(insts, "register")), 1)

    def test_counter_needs_const_operand(self) -> None:
        words = {"words": [
            word(1, "$dff", ["n1", "n2"], params={"WIDTH": 2}),
            word(2, "$add", ["n3"], const_ports=[]),
        ], "edges": [edge(1, "Q", 2, "A"), edge(2, "Y", 1, "D")]}
        self.assertEqual(by_type(derive_instances(words), "counter"), [])

    def test_gt_mux_tree_components(self) -> None:
        words = {"words": [
            word(1, "$mux", ["n1"]), word(2, "$mux", ["n2"]), word(3, "$pmux", ["n3"]),
            word(4, "$mux", ["n4"]), word(5, "$mux", ["n5"]),
        ], "edges": [edge(1, "Y", 2, "A"), edge(2, "Y", 3, "B"), edge(4, "Y", 5, "S")]}
        trees = by_type(derive_instances(words), "mux_tree")
        self.assertEqual([t.footprint for t in trees], [frozenset({"n1", "n2", "n3"})])

    def test_fsm_collects_d_side_muxes(self) -> None:
        words = {"words": [
            word(1, "$dff", ["n1"], params={"WIDTH": 2}, fsm=True),
            word(2, "$mux", ["n2"]), word(3, "$mux", ["n3"]),
        ], "edges": [edge(2, "Y", 1, "D"), edge(3, "Y", 2, "A")]}
        fsms = by_type(derive_instances(words), "fsm")
        self.assertEqual([f.footprint for f in fsms], [frozenset({"n1", "n2", "n3"})])

    def test_empty_footprint_skipped(self) -> None:
        words = {"words": [word(1, "$add", [])], "edges": []}
        self.assertEqual(derive_instances(words), [])

    def test_scored_types_kinds(self) -> None:
        self.assertEqual(SCORED_TYPES["adder"], frozenset({"$add"}))
        self.assertNotIn("shift_reg", SCORED_TYPES)


class BusTest(unittest.TestCase):
    def rows(self) -> list[dict[str, str]]:
        def row(n: str, path: str, bus: str, bit: int) -> dict[str, str]:
            return {"node_id": n, "module_path": path, "bus_name": bus, "bit_index": str(bit)}

        return [row("n1", "top", "x", 0), row("n2", "top", "x", 1), row("n3", "top", "x", 2),
                row("n4", "top", "x", 3), row("n5", "top", "y", 0), row("n6", "top/u", "x", 0),
                row("n7", "top", "", -1), row("n8", "top", "z", -1)]

    def test_gt_label_buses(self) -> None:
        buses = label_buses(self.rows())
        self.assertEqual(len(buses), 1)
        self.assertEqual(buses[0].members, frozenset({"n1", "n2", "n3", "n4"}))
        self.assertEqual(buses[0].bits[2], ("n3", 2))


class LoadTest(unittest.TestCase):
    def test_load_fake_floor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            floor = write_fake_floor(Path(tmp), "d", "f2")
            insts, buses, roles, paths = load_gt(floor)
            nm = load_netmap(floor)
        self.assertEqual(insts, [])
        self.assertEqual([b.name for b in buses], ["A"])
        self.assertEqual(roles["n3"], "unknown")
        self.assertEqual(paths["n4"], "top")
        self.assertEqual(nm.kinds["n4"], "pi")
        self.assertEqual(nm.driver["n2"], "n3")
        self.assertEqual(nm.readers["n2"], ("n6",))
