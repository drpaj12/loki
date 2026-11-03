"""Unit tests of Q-L12 (LUT netlist reader, glue, renderer, key rule, call building)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib

bd: Any = importlib.import_module("q12_build")
key: Any = importlib.import_module("q12_key")
nlm: Any = importlib.import_module("q12_nl")
rn: Any = importlib.import_module("q12_render")


BLIF = """.model top
.inputs n0 n1 n2
.outputs n6 n7
.names n1 n2 n3
11 1
.cname n10
.names n3 n1 n4
01 1
10 1
.cname n11
.latch n4 n5 re n0 3
.cname n12
.names n5 n6
1 1
.cname n13
.names n8
.cname n14
.names n8 n7
1 1
.cname n15
.end
"""
PORTS = [{"anon": "n20", "dir": "in", "net": "n0", "orig": "clk"},
         {"anon": "n21", "dir": "in", "net": "n1", "orig": "d[0]"},
         {"anon": "n22", "dir": "in", "net": "n2", "orig": "d[1]"},
         {"anon": "n23", "dir": "out", "net": "n6", "orig": "q"},
         {"anon": "n24", "dir": "out", "net": "n7", "orig": "z"}]


def netlist() -> Any:
    return nlm.parse(BLIF, PORTS)


class Blk:
    def __init__(self, bid: int, cells: list[int]) -> None:
        self.bid, self.cells = bid, cells


class TestNetlist(unittest.TestCase):
    def test_cells_and_idents(self) -> None:
        nl = netlist()
        self.assertEqual([c.kind for c in nl.cells], ["lut", "lut", "ff", "lut", "lut", "lut"])
        self.assertEqual(nl.ident["n1"], "d_0_")
        self.assertEqual(nl.ident["n3"], "w3")
        self.assertEqual(nl.orig["n6"], "q")

    def test_glue_is_buffer_and_constant(self) -> None:
        nl = netlist()
        self.assertEqual([c.idx for c in nl.cells if c.glue], [3, 4, 5])
        self.assertEqual(nl.logic(), [0, 1, 2])

    def test_output_matched_through_buffer(self) -> None:
        ports = [dict(p) for p in PORTS]
        ports[3]["net"] = "n5"  # the output port is the net before the buffer
        self.assertEqual(nlm.parse(BLIF, ports).orig["n6"], "q")
        ports[3]["net"] = "n9"
        with self.assertRaises(nlm.Unsupported):
            nlm.parse(BLIF, ports)

    def test_offset_cover_rejected(self) -> None:
        with self.assertRaises(nlm.Unsupported):
            nlm.parse(".model top\n.inputs n0\n.outputs n1\n.names n0 n1\n1 0\n.end\n", [])


class TestRender(unittest.TestCase):
    def test_xor_tree_is_exact(self) -> None:
        c = nlm.Cell(0, "lut", ["a", "b"], ["y"], cover=["01 1", "10 1"])
        nl = nlm.Netlist([c], ["a", "b"], ["y"], {"a": "a", "b": "b", "y": "y"}, {})
        self.assertEqual(rn.lut_expr(nl, c), "(a ? (b ? 1'b0 : 1'b1) : (b ? 1'b1 : 1'b0))")

    def test_ports_and_block_text(self) -> None:
        nl = netlist()
        blocks = [Blk(0, [0, 1]), Blk(1, [2])]
        ports = rn.block_ports(nl, blocks)
        self.assertEqual([nl.ident[n] for n in ports[0].inputs], ["d_0_", "d_1_"])
        self.assertEqual([nl.ident[n] for n in ports[0].outputs], ["w4"])
        self.assertEqual([nl.ident[n] for n in ports[1].inputs], ["clk", "w4"])
        text = rn.fragment(nl, 1, [2], ports[1])
        self.assertIn(".latch w4 w5 re clk 3", text)
        self.assertNotIn("n10", text)

    def test_prompt_has_no_leak_and_names_module(self) -> None:
        nl = netlist()
        blocks = [Blk(0, [0, 1]), Blk(1, [2])]
        ports = rn.block_ports(nl, blocks)
        prompt = rn.prompt_text(nl, 0, [0, 1], ports[0])
        self.assertIn("'Block_0'", prompt)
        self.assertEqual(rn.bp.leak_hits(prompt), [])
        self.assertTrue(prompt.endswith("Answer:\n"))

    def test_assemble_connects_original_bits_and_glue(self) -> None:
        nl = netlist()
        gate = type("G", (), {"header": ["clk", "d", "q", "z"],
                              "decl": {"clk": ("input", None, None), "d": ("input", 1, 0),
                                       "q": ("output", None, None),
                                       "z": ("output", None, None)}})()
        blocks = [Blk(0, [0, 1, 2])]
        ports = rn.block_ports(nl, blocks)
        codes: dict[int, Any] = {0: rn.stub_module(nl, 0, [0, 1, 2], ports[0])}
        text = rn.assemble(nl, gate, blocks, ports, codes)
        self.assertIn("module TopModule(clk, d, q, z);", text)
        self.assertIn(".d_0_(d[0])", text)
        self.assertIn("assign q = t_w5;", text)  # a buffer to an output is glue
        self.assertIn("assign t_w8 = 1'b0;", text)  # a constant is glue


class TestKey(unittest.TestCase):
    def test_right_rule(self) -> None:
        self.assertTrue(key.is_right(frozenset({1, 2, 3, 4, 5}), frozenset({1, 2, 3, 4, 5})))
        self.assertFalse(key.is_right(frozenset({1}), frozenset({1, 2})))
        self.assertFalse(key.is_right(frozenset(range(10)), frozenset({1, 2})))


class TestBuild(unittest.TestCase):
    def test_problem_set_is_the_ql10_set(self) -> None:
        rows = bd.problems()
        tiers = [r["tier"] for r in rows]
        self.assertEqual((tiers.count("vq"), tiers.count("vbig"), tiers.count("ext")), (43, 4, 5))

    def test_out_tokens(self) -> None:
        self.assertEqual(bd.out_tokens(100), 149)


if __name__ == "__main__":
    unittest.main()
