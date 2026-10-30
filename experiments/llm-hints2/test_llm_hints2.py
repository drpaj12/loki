"""Tests for the llm-hints2 helpers (no model, no Odin III): run with ``python -m unittest``."""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
analyze: Any = importlib.import_module("analyze_hints2")
build: Any = importlib.import_module("build_hints2")
collect: Any = importlib.import_module("collect_hints2")
netlink: Any = importlib.import_module("netlink")
promptv2: Any = importlib.import_module("promptv2")

NETLIST = """module RefModule(clk, reset, q);
  wire _00_;
  input clk;
  input reset;
  output [1:0] q;
  NOT _23_ (
    .A(q[0]),
    .Y(_00_)
  );
  DFF _46_ (
    .C(clk),
    .D(_00_),
    .Q(q[0])
  );
  DFF _47_ (
    .C(clk),
    .D(q[0]),
    .Q(q[1])
  );
endmodule
"""
CLAIM: dict[str, Any] = {"id": "h7", "kind": "counter", "source": "seq", "p": 0.97,
         "status": "proved", "evidence": "exhaustive", "merged": [], "params": {},
         "nets": {"q": ["q[0]", "q[1]"], "d": ["_00_", "q[0]"], "rst": ["reset"]},
         "wires": ["_00_", "q[0]", "q[1]"],
         "facts": {"q": ["q[0]", "q[1]"], "rst": {"net": "reset", "active": 1, "value": 0}}}
INTENT: dict[str, Any] = {"claims": [CLAIM], "buses": [], "net_roles": {}}


class Annotate(unittest.TestCase):
    def test_comment_lands_on_the_driving_gate_and_port(self) -> None:
        out = netlink.annotate(NETLIST, INTENT)
        lines = out.split("\n")
        self.assertTrue(any("NOT _23_ (  // loki h7 next-state of counter bit 0, p=0.97" in x
                            for x in lines))
        self.assertTrue(any("DFF _46_ (  // loki h7 counter bit 0, p=0.97" in x for x in lines))
        self.assertTrue(any("DFF _47_ (  // loki h7 counter bit 1" in x for x in lines))
        self.assertTrue(any("input reset;  // loki h7 reset of counter" in x for x in lines))
        stripped = "\n".join(x.split("  // loki")[0] for x in lines)
        self.assertEqual(stripped, NETLIST)

    def test_wrong_content_moves_every_name_inside_its_class(self) -> None:
        wrong = netlink.wrong_content(NETLIST, INTENT, "seed")
        again = netlink.wrong_content(NETLIST, INTENT, "seed")
        self.assertEqual(wrong, again)
        c = wrong["claims"][0]
        self.assertEqual((c["id"], c["kind"], c["p"]), ("h7", "counter", 0.97))
        self.assertNotEqual(c["nets"]["q"], CLAIM["nets"]["q"])
        self.assertEqual(sorted(c["nets"]["q"]), sorted(CLAIM["nets"]["q"]))
        self.assertEqual(INTENT["claims"][0]["nets"]["q"], ["q[0]", "q[1]"])

    def test_clock_is_never_a_target(self) -> None:
        mapping = netlink.permutation(NETLIST, INTENT, "x")
        self.assertNotIn("clk", mapping)
        self.assertNotIn("clk", mapping.values())


class Prompt(unittest.TestCase):
    def test_suffix_asks_for_notes_and_only_hint_arms_for_claims_used(self) -> None:
        self.assertIn("Notes:", promptv2.suffix(False))
        self.assertNotIn("CLAIMS-USED", promptv2.suffix(False))
        self.assertIn("CLAIMS-USED", promptv2.suffix(True))

    def test_user_message_places_hints_after_the_question(self) -> None:
        msg = build.user_message("PREFIX\n", "PROMPT\n", "HINTS\n", True)
        self.assertTrue(msg.startswith("PREFIX\n\nQuestion:\nPROMPT\n\nHINTS\n"))
        self.assertTrue(msg.endswith("\nAnswer:\n"))
        self.assertNotIn("HINTS", build.user_message("PREFIX\n", "PROMPT\n", "", False))

    def test_call_file_text(self) -> None:
        text = build.call_file_text("sys", "usr\n")
        self.assertTrue(text.startswith(build.DELIM_SYS + "sys"))
        self.assertTrue(text.endswith(build.DELIM_USER + "usr\n"))


class Collect(unittest.TestCase):
    def test_claims_used_line(self) -> None:
        f = collect.claims_used
        self.assertEqual(f("[BEGIN]\nx\n[DONE]\nCLAIMS-USED: h7,h2\n"), ["h2", "h7"])
        self.assertEqual(f("[DONE]\nCLAIMS-USED: none\n"), [])
        self.assertIsNone(f("[BEGIN]\nx\n[DONE]\n"))
        self.assertEqual(f("Notes: h9\n[BEGIN]\nm\n[DONE]\nclaims-used: h1"), ["h1"])
        self.assertEqual(f("[DONE]\nCLAIMS-USED: h3, h3, h12\n"), ["h3", "h12"])


class Analysis(unittest.TestCase):
    def counts(self, a2: int, b2: int, w: int,
               n: int = 16) -> tuple[dict[Any, int], dict[str, str]]:
        counts: dict[Any, int] = {}
        quart: dict[str, str] = {}
        for i in range(n):
            p = f"P{i}"
            quart[p] = "Q3" if i < n // 2 else "Q4"
            counts[("A2", p)] = 3 if i < a2 else 0
            counts[("B2", p)] = 3 if i < b2 else 0
            counts[("B1p", p)] = counts[("A2", p)]
            counts[("W", p)] = 3 if i < w else 0
        return counts, quart

    def test_holm_and_family_size(self) -> None:
        self.assertEqual(analyze.holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])
        counts, quart = self.counts(8, 8, 8)
        self.assertEqual(len(analyze.tests(counts, quart, "MAJ")), 9)

    def test_verdict_rule(self) -> None:
        v = analyze.verdict
        self.assertEqual(v(0.01, 0.20, 0.10, 0.30), "USEFUL")
        self.assertEqual(v(0.01, 0.08, 0.01, 0.15), "POSSIBLY GOOD")
        self.assertEqual(v(0.50, 0.01, -0.03, 0.04), "DISMISSED")
        self.assertEqual(v(0.50, 0.04, -0.10, 0.12), "INCONCLUSIVE")

    def test_llm6_needs_a_drop_and_use(self) -> None:
        row = analyze.TestRow("W vs A2", "all", 16, 0, 8, 0.01, 0.04)
        self.assertTrue(analyze.llm6(row, -0.3, 0.8))
        self.assertFalse(analyze.llm6(row, -0.3, 0.4))
        self.assertFalse(analyze.llm6(row, 0.1, 0.8))

    def test_pooled_equals_mcnemar(self) -> None:
        counts, quart = self.counts(2, 10, 2)
        rows = analyze.tests(counts, quart, "MAJ")
        pooled = next(r for r in rows if r.cmp == "B2 vs A2" and r.stratum.startswith("all"))
        self.assertEqual((pooled.x_only, pooled.y_only), (8, 0))
        self.assertAlmostEqual(pooled.p, 2 * 0.5**8)

    def test_use_rates_and_kind_table(self) -> None:
        rows = [
            {"arm": "B2", "problem": "P0", "used": "1", "claims_used": "h1", "pass": "1"},
            {"arm": "B2", "problem": "P0", "used": "0", "claims_used": "", "pass": "0"},
            {"arm": "B2", "problem": "P0", "used": "", "claims_used": "", "pass": "0"},
            {"arm": "A2", "problem": "P0", "used": "", "claims_used": "", "pass": "1"}]
        self.assertEqual(analyze.use_rates(rows)["B2"], (1, 2, 3))
        kinds = {"B2": {"P0": {"h1": "fsm", "h2": "counter"}}}
        table = "\n".join(analyze.kind_table(rows, kinds, "B2"))
        self.assertIn("| fsm | 1 | 1 | 1 | 0 |", table)
        self.assertIn("| counter | 0 | 0 | 2 | 1 |", table)


if __name__ == "__main__":
    unittest.main()
