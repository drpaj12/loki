import unittest
from typing import Any

from loki.intent.claims import from_seq, namer
from loki.intent.roles import assign_roles, sinks
from loki.intent.seq import sequential_claims
from tests.re_fixtures import GB, table_of
from tests.seq_fixtures import up_counter
from tests.test_re_fsm import three_state


def fsm_and_counter() -> tuple[GB, list[dict[str, Any]]]:
    """A 3-state machine whose input ``go`` is also the enable of a 2-bit counter whose bits go
    to primary outputs."""
    g = GB()
    q0, q1, _rst, go = three_state(g)
    clk = g.pis[0]
    cq = up_counter(g, clk, 2, en=go)
    g.pos.extend(cq)
    graph = g.build()
    name = namer(graph)
    claims = [from_seq(graph, c, f"h{i + 1}", name) for i, c in enumerate(sequential_claims(graph))]
    for c in claims:
        c["p"] = 0.9
    assert q0 and q1
    return g, claims


class RolesTest(unittest.TestCase):
    def test_sinks_are_enables_resets_and_fsm_state(self) -> None:
        _g, claims = fsm_and_counter()
        s = sinks(claims)
        self.assertIn("s0", s)
        self.assertIn("s1", s)
        self.assertIn("go", s)
        self.assertEqual(s["go"], 0.9)
        self.assertNotIn("q0", s)

    def test_fsm_is_control_counter_is_datapath(self) -> None:
        g, claims = fsm_and_counter()
        roles = assign_roles(g.build(), claims)
        kinds = {c["kind"]: c for c in claims}
        self.assertEqual(kinds["fsm"]["role"], "control")
        self.assertEqual(kinds["fsm"]["role_p"], 0.9)
        self.assertEqual(kinds["counter"]["role"], "datapath")
        self.assertIsNone(kinds["counter"]["role_p"])
        self.assertEqual(roles["go"]["role"], "control")
        self.assertEqual(roles["q0"]["role"], "datapath")

    def test_a_net_that_steers_and_reaches_an_output_is_mixed(self) -> None:
        g = GB()
        clk, rst, en = g.pi("clk"), g.pi("rst"), g.pi("en")
        q = up_counter(g, clk, 2, en=en, rst=rst)
        g.pos.extend([q[0], en])
        graph = g.build()
        name = namer(graph)
        claims = [from_seq(graph, c, "h1", name) for c in sequential_claims(graph)]
        claims[0]["p"] = 0.8
        roles = assign_roles(graph, claims)
        self.assertEqual(roles["en"]["role"], "mixed")
        self.assertEqual(roles["rst"]["role"], "control")
        self.assertEqual(roles["rst"]["p"], 0.8)

    def test_no_state_nets_means_unknown(self) -> None:
        g = GB()
        g.lut(table_of(1, lambda v: v[0]), (g.pi("a"),))
        claims = [{"id": "h1", "kind": "bus", "nets": {"s0": ["a"]}, "p": 0.6}]
        assign_roles(g.build(), claims)
        self.assertEqual(claims[0]["role"], "unknown")


if __name__ == "__main__":
    unittest.main()
