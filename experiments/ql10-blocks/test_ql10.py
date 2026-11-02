"""Tests of the Q-L10 helpers (no model, no Odin III graphlets): ``python -m unittest``."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib

bd: Any = importlib.import_module("q10_build")
blocks: Any = importlib.import_module("q10_blocks")
ck: Any = importlib.import_module("q10_check")
key: Any = importlib.import_module("q10_key")
nlm: Any = importlib.import_module("q10_nl")
rn: Any = importlib.import_module("q10_render")

NETLIST = """
/* c */
module RefModule(clk, a, b, y, z);
  input a;
  wire a;
  input b;
  wire b;
  input clk;
  wire clk;
  output [1:0] y;
  wire [1:0] y;
  output z;
  wire z;
  wire _0_;
  wire _1_;
  NAND _2_ (
    .A(a),
    .B(b),
    .Y(_0_)
  );
  NOT _3_ (
    .A(_0_),
    .Y(_1_)
  );
  DFF _4_ (
    .C(clk),
    .D(_1_),
    .Q(y[0])
  );
  DFFSR _5_ (
    .C(clk),
    .D(y[0]),
    .Q(y[1]),
    .R(b),
    .S(1'h0)
  );
  assign z = y[1];
endmodule
"""


def two_blocks(nl: Any) -> list[Any]:
    return [blocks.Block(0, "register", [0, 1, 2]), blocks.Block(1, "register", [3])]


class Parse(unittest.TestCase):
    def test_cells_and_assigns(self) -> None:
        nl = nlm.parse(NETLIST)
        self.assertEqual([c.typ for c in nl.cells], ["NAND", "NOT", "DFF", "DFFSR"])
        self.assertEqual(nl.cells[3].pins["S"], "#0")
        self.assertEqual(nl.assigns, [("z", "y[1]")])
        self.assertEqual(nl.header, ["clk", "a", "b", "y", "z"])
        self.assertEqual(nl.san["y[1]"], "y_1_")

    def test_unsupported(self) -> None:
        with self.assertRaises(nlm.Unsupported):
            nlm.parse("module m(a);\n  input a;\n  reg q;\nendmodule\n")

    def test_x_constant_and_vector_assign(self) -> None:
        nl = nlm.parse("module m(a, o);\n  input [1:0] a;\n  output [2:0] o;\n"
                       "  assign o = { a, 1'hx };\nendmodule\n")
        self.assertEqual(nl.assigns, [("o[2]", "a[1]"), ("o[1]", "a[0]"), ("o[0]", "#x")])


class Blif(unittest.TestCase):
    def test_blif_cells(self) -> None:
        nl = nlm.parse(NETLIST)
        bl = blocks.to_blif(nl)
        self.assertEqual(bl.halves[3], [len(bl.owner) - 2, len(bl.owner) - 1])
        self.assertIn(".latch", bl.text)
        self.assertEqual(bl.owner.count(-1), 2)  # the gnd cell and the assign z = y[1]
        self.assertIn(".names gnd", bl.text)


class Render(unittest.TestCase):
    def test_ports(self) -> None:
        nl = nlm.parse(NETLIST)
        bs = two_blocks(nl)
        ports = rn.block_ports(nl, bs)
        self.assertEqual(ports[0].inputs, ["a", "b", "clk"])
        self.assertEqual(ports[0].outputs, ["y[0]"])
        self.assertEqual(ports[0].internal, ["_0_", "_1_"])
        self.assertEqual(ports[1].inputs, ["b", "clk", "y[0]"])
        self.assertEqual(ports[1].outputs, ["y[1]"])

    def test_prompt_hint_and_leak(self) -> None:
        nl = nlm.parse(NETLIST)
        bs = two_blocks(nl)
        bs[0].guess = "fsm"
        ports = rn.block_ports(nl, bs)
        plain = rn.prompt_text(nl, bs[0], ports[0], False)
        hinted = rn.prompt_text(nl, bs[0], ports[0], True)
        self.assertNotIn("Loki", plain)
        self.assertIn("a finite state machine", hinted)
        self.assertEqual(rn.prompt_text(nl, bs[1], ports[1], True),
                         rn.prompt_text(nl, bs[1], ports[1], False))
        self.assertEqual(bd.bp.leak_hits(plain + hinted), [])

    @unittest.skipUnless(shutil.which("iverilog"), "iverilog needed")
    def test_assemble_stub_and_block_check(self) -> None:
        nl = nlm.parse(NETLIST)
        bs = two_blocks(nl)
        ports = rn.block_ports(nl, bs)
        codes = {b.bid: ck.stub_decode(nl, b, p) for b, p in zip(bs, ports, strict=True)}
        top = rn.assemble(nl, bs, ports, codes)
        self.assertIn("module TopModule(clk, a, b, y, z);", top)
        self.assertIn("Block_1 u_1(", top)
        with tempfile.TemporaryDirectory() as tmp:
            for b, p in zip(bs, ports, strict=True):
                self.assertEqual(ck.block_check(nl, b, p, codes[b.bid], Path(tmp) / str(b.bid)),
                                 "ok")
            wrong = codes[0].replace("~(a & b)", "(a & b)")
            self.assertEqual(ck.block_check(nl, bs[0], ports[0], wrong, Path(tmp) / "w"),
                             "mismatch")
            self.assertEqual(ck.block_check(nl, bs[0], ports[0], "module Block_0(;", Path(tmp)
                                            / "s"), "compile")


class Key(unittest.TestCase):
    def test_right_rule(self) -> None:
        true = frozenset({1, 2, 3, 4, 5})
        self.assertTrue(key.is_right(frozenset({1, 2, 3, 4}), true))
        self.assertFalse(key.is_right(frozenset({1, 2, 3}), true))  # coverage 0.6
        self.assertFalse(key.is_right(frozenset(range(1, 15)), true))  # Jaccard 5/14


class Calls(unittest.TestCase):
    def test_batches_do_not_span_draws(self) -> None:
        calls = [{"call": i, "draw": 1 + i // 30, "group": "core", "call_file": "x",
                  "outbox_file": "y",
                  "est_tokens_in": 1, "est_tokens_out": 1} for i in range(90)]
        out = bd.batches(calls)
        self.assertTrue(all(len({calls[c["call"]]["draw"] for c in b["calls"]}) == 1
                            for b in out))
        self.assertEqual(sum(b["n_calls"] for b in out), 90)
        self.assertEqual(bd.out_tokens(0), 113)


if __name__ == "__main__":
    unittest.main()
