import unittest
from typing import Any

from loki.intent.text import bus_name, claim_line, cond_text, pfmt, render_claims, state_label

COUNTER = {
    "id": "h7", "kind": "counter", "source": "seq", "status": "proved", "p": 0.9712,
    "evidence": "exhaustive", "merged": ["h3"],
    "nets": {"q": ["q[0]", "q[1]", "q[2]", "q[3]"], "rst": ["reset"]},
    "wires": [], "params": {},
    "facts": {"q": ["q[0]", "q[1]", "q[2]", "q[3]"], "width": 4, "dir": "up", "modulus": 10,
              "wrap": 0, "start": 0, "async": False,
              "rst": {"net": "reset", "active": 1, "value": 0}},
}
FSM = {
    "id": "h2", "kind": "fsm", "source": "seq", "status": "proved", "p": 0.95,
    "evidence": "exhaustive", "merged": [], "nets": {"q": ["s[0]", "s[1]", "s[2]"]}, "wires": [],
    "params": {},
    "facts": {"q": ["s[0]", "s[1]", "s[2]"], "width": 3, "states": [1, 2, 4], "encoding": "one-hot",
              "start": 1, "controls": ["go"], "async": True,
              "rst": {"net": "areset", "active": 1, "value": 1},
              "transitions": [{"src": 1, "dst": 2, "cond": [[["go", 1]]]},
                              {"src": 1, "dst": 1, "cond": [[["go", 0]]]}]},
}


class TextTest(unittest.TestCase):
    def test_probability_is_truncated_not_rounded_up(self) -> None:
        self.assertEqual(pfmt(0.9999), "p=0.99")
        self.assertEqual(pfmt(0.971), "p=0.97")
        self.assertEqual(pfmt(None), "no calibrated p")

    def test_bus_name(self) -> None:
        self.assertEqual(bus_name(["q[0]", "q[1]", "q[2]"]), "q[2:0]")
        self.assertEqual(bus_name(["q[2]", "q[1]"]), "q[2:1]")
        self.assertEqual(bus_name(["a", "b"]), "a, b")
        self.assertEqual(bus_name(["q[0]", "q[2]"]), "q[0], q[2]")

    def test_condition(self) -> None:
        self.assertEqual(cond_text([[["a", 1], ["b", 0]], [["c", 1]]]), "a & ~b | c")
        self.assertEqual(cond_text([[]]), "always")
        self.assertEqual(cond_text([]), "never")

    def test_counter_line_is_the_brief_example(self) -> None:
        line = claim_line(COUNTER)
        self.assertTrue(line.startswith("h7 (p=0.97, proved by exhaustive simulation"))
        self.assertIn("q[3:0] is a 4-bit up counter", line)
        self.assertIn("counts up by 1 from 0 to 9, then returns to 0", line)
        self.assertIn("synchronous reset to 0 when reset is high", line)
        self.assertIn("Also reported as h3", line)

    def test_one_hot_states_are_named_by_their_bit(self) -> None:
        f = FSM["facts"]
        assert isinstance(f, dict)
        self.assertEqual(state_label(f, 4), "s[2]")
        self.assertEqual(state_label(f, 0), "idle(all zero)")
        doc = render_claims({"claims": [FSM], "buses": [], "net_roles": {}})
        self.assertIn("s[0] -> s[1] when go", doc)
        self.assertIn("asynchronous reset when areset is high enters state s[0]", doc)

    def test_document_sections_and_empty_case(self) -> None:
        intent: dict[str, Any] = {
            "claims": [COUNTER], "net_roles": {"reset": {"role": "control", "p": 0.97},
                                               "q[0]": {"role": "datapath", "p": None}},
            "buses": [{"id": "b1", "bits": ["q[0]", "q[1]"], "p": 0.97,
                       "links": [{"claim": "h7", "text": "value of the counter h7"}]},
                      {"id": "b2", "bits": ["x[0]", "x[1]"], "p": None,
                       "links": [{"claim": "h7", "text": "next-state input of h7"}]}]}
        doc = render_claims(intent)
        self.assertIn("## Buses", doc)
        self.assertIn("b1 (p=0.97): q[1:0] is the value of the counter h7", doc)
        self.assertNotIn("b2", doc)
        self.assertIn("- control: reset (p=0.97)", doc)
        empty = render_claims({"claims": [], "buses": [], "net_roles": {}})
        self.assertIn("no claim about this netlist", empty)


if __name__ == "__main__":
    unittest.main()
