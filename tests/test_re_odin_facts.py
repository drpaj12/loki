"""Probes of the Odin III facts L1 rests on (L1 spec 3.1). A failing probe means a fact changed:
edit spec 3.1 with the observed fact before going on."""

import tempfile
import unittest
from pathlib import Path
from typing import Any

from loki.odin import odin_module
from loki.re.fngraph import from_design
from loki.re.normalise import NormaliseError, load_level0
from tests.helpers import DATA, can_run_f2, odin_available

ADD2 = DATA / "re" / "add2.blif"
NOCNAME = DATA / "re" / "nocname.blif"
# .names lines of add2.blif (each is followed by its .cname line)
LINES = (4, 8, 11)


def read(path: Path = ADD2) -> Any:
    mod = odin_module()
    design = mod.Design(mod.default())
    design.run_script(f'read_blif "{path}"')
    return design


def nodes(design: Any, typ: str) -> list[Any]:
    return [n for n in design.top().nodes() if str(n.type_name) == typ]


def sources(node: Any) -> set[int]:
    return {int(s.line) for s in node.sources()}


def raised() -> Any:
    """Level 1 of the 2-bit adder as re_round.py does it: mark, cone_check, raise."""
    mod = odin_module()
    mod.default().load_abc()
    design = read()
    module = design.top()
    for node in nodes(design, "$sop"):
        node.set_attr("grp", "add")
    for name, port in (("a0", "A[0]"), ("b0", "B[0]"), ("y0", "Y[0]"), ("a1", "A[1]"),
                       ("b1", "B[1]"), ("y1", "Y[1]")):
        module.net(name).set_attr("odin3:bind", port)
    args = "-attr grp=add -cell $add -param A_WIDTH=2 -param B_WIDTH=2 -param Y_WIDTH=2"
    design.run_pass("cone_check", f"{args} -timeout 30")
    design.run_pass("raise", args)
    return design


@unittest.skipUnless(odin_available(), "needs Odin III")
class OdinFactsTest(unittest.TestCase):
    def test_sop_params_and_ports(self) -> None:  # fact 1
        sops = nodes(read(), "$sop")
        self.assertEqual(len(sops), 3)
        node = next(n for n in sops if n.name == "n10")
        self.assertEqual(node.granularity, "bit")
        self.assertEqual(node.params(), {"WIDTH": 2, "COVER": "01 1\n10 1\n"})
        ports = {p.name: (p.direction, p.width) for p in node.ports()}
        self.assertEqual(ports, {"A": ("in", 2), "Y": ("out", 1)})
        a = next(p for p in node.ports() if p.name == "A")
        self.assertEqual([p.net().name for p in a.pins], ["a0", "b0"])
        ff = nodes(read(), "$_DFF_P_")[0]
        self.assertEqual([p.name for p in ff.ports()], ["C", "D", "Q"])
        self.assertEqual(ff.params(), {"INIT": 0})

    def test_cname_is_node_name(self) -> None:  # fact 2
        self.assertEqual(sorted(n.name for n in nodes(read(), "$sop")), ["n10", "n11", "n12"])
        self.assertEqual([n.name for n in nodes(read(NOCNAME), "$sop")], [""])

    def test_sources_are_blif_lines(self) -> None:  # fact 3
        found = sorted(sources(n) for n in nodes(read(), "$sop"))
        self.assertEqual(found, [{4}, {8}, {11}])
        for node in nodes(read(), "$sop"):
            self.assertEqual(len(node.sources()), 1)
            self.assertEqual(node.sources()[0].file, str(ADD2))
        self.assertEqual(sources(nodes(read(), "$_DFF_P_")[0]), {17})
        graph = from_design(read())
        self.assertEqual(sorted(graph.line_to_cell), [4, 8, 11, 17])

    @unittest.skipUnless(can_run_f2(), "needs ABC")
    def test_raise_sources_union(self) -> None:  # fact 4
        design = raised()
        driver = design.top().net("y0").driver()
        self.assertIsNotNone(driver)
        node = driver.node()
        self.assertEqual(node.type_name, "$add")
        self.assertEqual(node.name, "")
        self.assertEqual(sources(node), set(LINES))

    def test_submod_names_and_nesting(self) -> None:  # fact 5
        design = read()
        for node in nodes(design, "$sop"):
            node.set_attr("grp", "G1")
        design.run_pass("submod", "-attr grp")
        self.assertEqual(sorted(m.name for m in design.modules()), ["G1", "add2"])
        inst = next(n for n in design.top().nodes() if n.name == "G1_i")
        self.assertEqual(inst.type_name, "G1")
        for node in design.top().nodes():
            if str(node.type_name).startswith("$_DFF"):
                node.set_attr("outer", "O")
        inst.set_attr("outer", "O")
        design.run_pass("submod", "-attr outer")
        self.assertEqual(sorted(m.name for m in design.modules()), ["G1", "O", "add2"])
        inner = design.module("O")
        self.assertIn("G1_i", [n.name for n in inner.nodes()])
        copy = design.copy()
        self.assertEqual(sorted(m.name for m in copy.modules()), ["G1", "O", "add2"])
        self.assertIsNotNone(copy.top().net("y0"))
        self.assertIsNotNone(design.top().net("y0"))

    def test_attrs_in_verilog(self) -> None:  # fact 6
        design = read()
        for node in nodes(design, "$sop"):
            node.set_attr("grp", "G1")
            if node.name == "n12":
                node.set_attr("loki_conf", "0.2")
        design.top().net("c0").set_attr("loki_net", "cx")
        design.run_pass("submod", "-attr grp")
        next(n for n in design.top().nodes() if n.name == "G1_i").set_attr("loki_conf", "0.9")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "o.v"
            design.run_pass("write_verilog", f'"{out}"')
            text = out.read_text(encoding="utf-8")
        self.assertIn('(* loki_conf = "0.9" *)\n  G1 G1_i (', text)
        self.assertIn('(* loki_net = "cx" *) wire c0;', text)
        self.assertIn('// (* loki_conf = "0.2" *)', text)

    def test_fsm_detect_marks_nothing_at_bit_level(self) -> None:  # fact 8
        design = read()
        design.run_pass("fsm_detect")
        marked = [n for n in design.top().nodes() if n.attr("odin3_fsm_encoding") is not None]
        self.assertEqual(marked, [])

    def test_int_attr_unreadable(self) -> None:  # fact 9
        mod = odin_module()
        design = read()
        design.run_pass("levelize")
        node = nodes(design, "$sop")[0]
        with mod.default().capture_log(), self.assertRaises(mod.Odin3Error):
            node.attr("odin3_level")

    def test_passes_present(self) -> None:  # fact 10
        have = set(odin_module().default().passes())
        want = {"read_blif", "read_techlib", "read_arch", "read_verilog", "write_blif",
                "write_json", "write_verilog", "flatten", "lower", "fsm_detect", "levelize",
                "submod", "cone_check", "raise"}
        self.assertEqual(want - have, set())


@unittest.skipUnless(odin_available(), "needs Odin III")
class FromDesignTest(unittest.TestCase):
    def test_from_design_add2(self) -> None:
        graph = from_design(read())
        by_name = {c.name: c for c in graph.cells.values()}
        self.assertEqual(sorted(by_name), ["n10", "n11", "n12", "n13"])
        self.assertEqual((by_name["n10"].kind, by_name["n10"].table), ("lut", 0b0110))
        self.assertEqual((by_name["n11"].kind, by_name["n11"].table), ("lut", 0b1000))
        self.assertEqual(by_name["n12"].table, 0b10010110)
        ff = by_name["n13"]
        self.assertEqual((ff.kind, ff.type, len(ff.ins), len(ff.outs)), ("ff", "$_DFF_P_", 1, 1))
        self.assertEqual(graph.names[ff.clock], "clk")
        self.assertEqual([graph.names[n] for n in graph.pis], ["a0", "a1", "b0", "b1", "clk"])
        self.assertEqual([graph.names[n] for n in graph.pos], ["y0", "y1", "q"])
        self.assertEqual(by_name["n10"].line, 4)
        y1 = by_name["n12"].outs[0]
        self.assertEqual(graph.driver[y1], by_name["n12"].id)
        self.assertEqual(sorted(c for c, _ in graph.readers[y1]), [ff.id])
        self.assertEqual(graph.source_file, str(ADD2))
        self.assertIn(ff.outs[0], graph.sources())

    def test_load_level0_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.blif"
            bad.write_text(".model x\n.names\n.bogus\n.end\n", encoding="utf-8")
            with self.assertRaises(NormaliseError) as ctx:
                load_level0(bad, "f2", None, None)
        self.assertTrue(str(ctx.exception).startswith("odin3: "))

    def test_load_level0_ok(self) -> None:
        graph = from_design(load_level0(ADD2, "f2", None, None))
        self.assertEqual(len(graph.cells), 4)


if __name__ == "__main__":
    unittest.main()
