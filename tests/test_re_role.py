import unittest

from loki.re.detectors import Candidate
from loki.re.detectors.role import RoleDetector, predict_role
from loki.re.overlay import Hypothesis, Overlay
from tests.re_fixtures import AND2, GB, MUX, XOR2, make_ctx


def hyp(
    ov: Overlay, kind: str, cells: list[int], nets: dict[str, tuple[int, ...]],
    status: str, params: dict[str, int | str] | None = None,
) -> Hypothesis:
    h = ov.add(Candidate(kind, frozenset(cells), nets, params or {}, {}), "test", 1)
    h.status = status
    return h


def roles(g: GB, ov: Overlay) -> dict[int, str]:
    got = RoleDetector().propose(make_ctx(g.build(), ov))
    return {min(c.cells): c.features["role_prop"] for c in got}


class RoleTest(unittest.TestCase):
    def test_select_driver_is_control(self) -> None:
        g = GB()
        a, b, x, y = g.pi(), g.pi(), g.pi(), g.pi()
        s = g.lut(AND2, (x, y))
        out = g.lut(MUX, (a, b, s))
        g.pos.append(out)
        ov = Overlay()
        hyp(ov, "mux_bit", [g.cell_of(out)], {"S": (s,), "D": (a, b), "Y": (out,)}, "confirmed")
        r = roles(g, ov)
        self.assertEqual(r[g.cell_of(s)], "control")
        self.assertEqual(r[g.cell_of(out)], "data")

    def test_unconfirmed_sink_is_ignored(self) -> None:
        g = GB()
        a, b, x = g.pi(), g.pi(), g.pi()
        s = g.lut(0b01, (x,))
        out = g.lut(MUX, (a, b, s))
        ov = Overlay()
        hyp(ov, "mux_bit", [g.cell_of(out)], {"S": (s,)}, "open")
        self.assertEqual(roles(g, ov)[g.cell_of(s)], "none")

    def test_adder_input_is_data(self) -> None:
        g = GB()
        x, b = g.pi(), g.pi()
        feeder = g.lut(0b10, (x,))
        y = g.lut(XOR2, (feeder, b))
        ov = Overlay()
        hyp(ov, "adder", [g.cell_of(y)], {"A": (feeder,), "B": (b,), "Y": (y,)}, "committed")
        self.assertEqual(roles(g, ov)[g.cell_of(feeder)], "data")

    def test_fsm_cells_control(self) -> None:
        g = GB()
        clk, x, y = g.pi("clk"), g.pi(), g.pi()
        feeder = g.lut(AND2, (x, y))
        q = g.net()
        d = g.lut(XOR2, (q, feeder))
        g.ff(d, clk, q)
        ff = g.cell_of(q)
        ov = Overlay()
        hyp(ov, "fsm", [ff, g.cell_of(d)], {"Q": (q,), "D": (d,)}, "confirmed")
        r = roles(g, ov)
        self.assertEqual({r[ff], r[g.cell_of(d)], r[g.cell_of(feeder)]}, {"control"})

    def test_mixed(self) -> None:
        g = GB()
        a, b, x, b2 = g.pi(), g.pi(), g.pi(), g.pi()
        c = g.lut(0b01, (x,))
        out = g.lut(MUX, (a, b, c))
        total = g.lut(XOR2, (c, b2))
        ov = Overlay()
        hyp(ov, "mux_bit", [g.cell_of(out)], {"S": (c,)}, "confirmed")
        hyp(ov, "adder", [g.cell_of(total)], {"A": (c,), "B": (b2,), "Y": (total,)}, "committed")
        self.assertEqual(roles(g, ov)[g.cell_of(c)], "mixed")

    def test_role_loop_terminates(self) -> None:
        g = GB()
        clk, x = g.pi("clk"), g.pi()
        q = g.net()
        d = g.lut(XOR2, (q, x))
        g.ff(d, clk, q)
        ov = Overlay()
        hyp(ov, "fsm", [g.cell_of(d)], {}, "confirmed")
        r = roles(g, ov)
        self.assertEqual((r[g.cell_of(d)], r[g.cell_of(q)]), ("control", "control"))

    def test_no_seeds_gives_none(self) -> None:
        g = GB()
        g.lut(AND2, (g.pi(), g.pi()))
        self.assertEqual(set(roles(g, Overlay()).values()), {"none"})

    def test_in_bus4_and_predict(self) -> None:
        g = GB()
        outs = [g.lut(AND2, (g.pi(), g.pi())) for _ in range(4)]
        ov = Overlay()
        hyp(ov, "bus", [g.cell_of(o) for o in outs], {}, "open", {"k": 4})
        got = RoleDetector().propose(make_ctx(g.build(), ov))
        self.assertEqual({c.features["in_bus4"] for c in got}, {"yes"})
        h = ov.add(got[0], "role", 1)
        h.log_odds = -1.0
        self.assertEqual(predict_role(h), "datapath")
        h.log_odds = 0.5
        self.assertEqual(predict_role(h), "control")
        h.features["role_prop"] = "mixed"
        self.assertEqual(predict_role(h), "mixed")

    def test_one_role_per_logic_cell(self) -> None:
        g = GB()
        clk = g.pi("clk")
        g.ff(g.lut(0b01, (g.pi(),)), clk)
        g.const(1)
        got = RoleDetector().propose(make_ctx(g.build()))
        self.assertEqual(len(got), 2)
        self.assertTrue(all(c.kind == "role" for c in got))


if __name__ == "__main__":
    unittest.main()
