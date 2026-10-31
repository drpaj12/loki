"""L3 v0: netlist reach, catalogue signatures, single-pattern detector."""

from __future__ import annotations

import unittest
from typing import Any

from loki.l3 import catalogue
from loki.l3.detect import Detector
from loki.l3.netlist import Netlist

TUNING: dict[str, Any] = {"max_depth": 4, "min_p": 0.0, "regfile_k": 2, "regfile_k2": 4}
# a 2-bit up counter through a hard adder: sum bits y0 y1 -> latches q0 q1 -> adder input a0 a1;
# b is a single enable net
BLIF = """.model m
.inputs en clk
.names z
1
.subckt adder a[0]=q0 a[1]=q1 b[0]=en sumout[0]=y0 sumout[1]=y1
.latch y0 q0 re clk 3
.latch y1 q1 re clk 3
.names q0 q1 t
11 1
.names t u
1 1
.end
"""


def claim(cid: str, kind: str, p: float | None = 0.99, **nets: list[str]) -> dict[str, Any]:
    return {"id": cid, "kind": kind, "p": p, "status": "proved", "nets": nets, "facts": {}}


def detector() -> Detector:
    return Detector(catalogue.load(), TUNING)


class NetlistTest(unittest.TestCase):
    def test_forward_stops_at_flip_flops(self) -> None:
        net = Netlist(BLIF)
        reach = net.forward(["q0"], 3)
        self.assertEqual(reach["t"], 1)
        self.assertEqual(reach["u"], 2)
        self.assertNotIn("q1", reach)

    def test_feedback_q(self) -> None:
        net = Netlist(BLIF)
        self.assertEqual(net.feedback_q(["y0", "y1"], {"q0", "q1", "en"}, 2), ["q0", "q1"])
        self.assertEqual(net.feedback_q(["y0"], {"zzz"}, 2), [])
        self.assertIn("z", net.consts)


class CatalogueTest(unittest.TestCase):
    def test_all_entries_load_in_order(self) -> None:
        entries = catalogue.load()
        self.assertEqual(list(entries)[:3], ["fsm", "counter", "lfsr"])
        self.assertEqual(set(entries), set(catalogue.ORDER))


class DetectTest(unittest.TestCase):
    def test_fsm_and_forbidden_register(self) -> None:
        cl = [claim("h1", "fsm", None, q=["a", "b"]), claim("h2", "ff_en", q=["c"])]
        det = detector().run(cl, "gate")
        self.assertTrue(det.found("fsm"))
        self.assertFalse(det.found("register"))
        self.assertFalse(det.found("glue"))

    def test_dedupe_shared_q(self) -> None:
        cl = [claim("h1", "fsm", 0.9, q=["a"]), claim("h2", "fsm", 0.8, q=["a", "b"])]
        self.assertEqual(len(detector().run(cl, "lut").instances["fsm"]), 1)

    def test_timer_needs_compare_on_counter(self) -> None:
        cnt = claim("c1", "counter", Q=["q0", "q1"], D=["d0"])
        cmp_ = claim("c2", "eq_const", A=["q0", "q1"], Y=["y"])
        self.assertTrue(detector().run([cnt, cmp_], "gate").found("timer"))
        self.assertFalse(detector().run([cnt], "gate").found("timer"))
        other = claim("c3", "eq_const", A=["zz"], Y=["y"])
        det = detector().run([cnt, other], "gate")
        self.assertFalse(det.found("timer"))
        self.assertEqual(det.reason["timer"], "l3_composition")

    def test_hard_counter_needs_feedback(self) -> None:
        add = claim("a1", "hard_add", A=["q0", "q1"], B=["en"], Y=["y0", "y1"])
        net = Netlist(BLIF)
        det = detector().run([add], "lut+hard", net)
        self.assertTrue(det.found("counter"))
        self.assertEqual(det.instances["counter"][0].q, frozenset({"q0", "q1"}))
        self.assertFalse(detector().run([add], "lut+hard", None).found("counter"))
        wide = claim("a2", "hard_add", A=["q0", "q1"], B=["u", "t"], Y=["y0", "y1"])
        self.assertFalse(detector().run([wide], "lut+hard", net).found("counter"))

    def test_regfile_group_and_glue(self) -> None:
        regs = [claim(f"r{i}", "ff_en", q=[f"q{i}"]) for i in range(3)]
        sel = claim("m1", "mux_tree", Y=["o"])
        self.assertTrue(detector().run([*regs, sel], "gate").found("regfile"))
        self.assertFalse(detector().run(regs[:1] + [sel], "gate").found("regfile"))
        comb = detector().run([claim("e1", "eq_const", A=["x"], Y=["y"])], "gate")
        self.assertTrue(comb.found("glue"))
        self.assertFalse(detector().run([claim("e1", "eq_const")], "gate", Netlist(BLIF)).found(
            "glue"))

    def test_rejected_claim_ignored(self) -> None:
        c = claim("h1", "fsm", None, q=["a"])
        c["status"] = "rejected"
        self.assertFalse(detector().run([c], "gate").found("fsm"))


if __name__ == "__main__":
    unittest.main()
