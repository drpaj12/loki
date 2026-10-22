import unittest
from dataclasses import replace

from loki.re.detectors import Candidate, RoundContext
from loki.re.detectors.unit import UnitDetector, _ratio_bin
from loki.re.fngraph import FnGraph
from loki.re.overlay import Overlay
from loki.re.sim import Support
from loki.re.view import Piece, View
from tests.re_fixtures import AND2, GB, MUX, XOR2, make_ctx


class Fix:
    """A graph plus the pieces and hypotheses built on it."""

    def __init__(self) -> None:
        self.g = GB()
        self.ov = Overlay()
        self.pieces: list[Piece] = []

    def piece(
        self, kind: str, cells: list[int], ins: tuple[int, ...], outs: tuple[int, ...],
        nets: dict[str, tuple[int, ...]] | None = None,
    ) -> str:
        h = self.ov.add(Candidate(kind, frozenset(cells), nets or {}, {}, {}), "test", 1)
        h.status = "committed"
        self.pieces.append(Piece(h.id, kind, ins, outs, frozenset(cells)))
        return h.id

    def role(self, cell: int, log_odds: float) -> None:
        h = self.ov.add(Candidate("role", frozenset({cell}), {}, {}, {}), "role", 1)
        h.log_odds = log_odds

    def ctx(self, graph: FnGraph, rnd: int = 2) -> RoundContext:
        absorbed = frozenset(c for p in self.pieces for c in p.cells)
        free = tuple(c for c in sorted(graph.cells) if c not in absorbed)
        view = View(free, tuple(self.pieces), absorbed, Support(graph))
        return replace(make_ctx(graph, self.ov, view=view), round=rnd)


def datapath(f: Fix) -> tuple[list[str], int]:
    """adder -> mux -> register; returns the piece ids and the mux select net."""
    g = f.g
    a, b, b2, s, clk = g.pi("a"), g.pi("b"), g.pi("b2"), g.pi("s"), g.pi("clk")
    y = g.lut(XOR2, (a, b))
    m = g.lut(MUX, (y, b2, s))
    q = g.ff(m, clk)
    ids = [
        f.piece("adder", [g.cell_of(y)], (a, b), (y,), {"A": (a,), "B": (b,), "Y": (y,)}),
        f.piece("mux", [g.cell_of(m)], (y, b2, s), (m,), {"S": (s,), "Y": (m,)}),
        f.piece("register", [g.cell_of(q)], (m, clk), (q,), {"q": (q,), "d": (m,)}),
    ]
    return ids, s


class UnitTest(unittest.TestCase):
    def test_datapath_unit(self) -> None:
        f = Fix()
        ids, _ = datapath(f)
        got = UnitDetector().propose(f.ctx(f.g.build()))
        self.assertEqual([c.kind for c in got], ["datapath_unit"])
        self.assertEqual(got[0].children, tuple(sorted(ids)))
        self.assertEqual(got[0].features["internal_ratio"], "<0.4")
        self.assertEqual(got[0].params["pieces"], 3)

    def test_ratio_bins(self) -> None:
        self.assertEqual(_ratio_bin(7, 10), ">=0.7")
        self.assertEqual(_ratio_bin(5, 10), "0.4-0.7")
        self.assertEqual(_ratio_bin(3, 10), "<0.4")
        self.assertEqual(_ratio_bin(0, 0), "<0.4")

    def test_control_port_does_not_join(self) -> None:
        f = Fix()
        g = f.g
        a, b, c, d = g.pi(), g.pi(), g.pi(), g.pi()
        y = g.lut(XOR2, (a, b))
        out = g.lut(MUX, (c, d, y))  # y only drives the select of the mux
        f.piece("adder", [g.cell_of(y)], (a, b), (y,), {"A": (a,), "B": (b,), "Y": (y,)})
        f.piece("mux", [g.cell_of(out)], (c, d, y), (out,), {"S": (y,), "Y": (out,)})
        self.assertEqual(UnitDetector().propose(f.ctx(g.build())), [])

    def test_free_datapath_cell_between_pieces(self) -> None:
        f = Fix()
        g = f.g
        a, b, c = g.pi(), g.pi(), g.pi()
        y1 = g.lut(XOR2, (a, b))
        mid = g.lut(0b10, (y1,))
        y2 = g.lut(XOR2, (mid, c))
        f.piece("adder", [g.cell_of(y1)], (a, b), (y1,), {"Y": (y1,)})
        f.piece("adder", [g.cell_of(y2)], (mid, c), (y2,), {"Y": (y2,)})
        f.role(g.cell_of(mid), -2.0)
        got = UnitDetector().propose(f.ctx(g.build()))
        self.assertEqual(len(got), 1)
        self.assertIn(g.cell_of(mid), got[0].cells)
        # without a datapath role the cell does not join the pieces
        f.ov.get(f.ov.by_kind("role")[0].id).log_odds = 2.0
        self.assertEqual(UnitDetector().propose(f.ctx(g.build())), [])

    def test_control_unit(self) -> None:
        f = Fix()
        g = f.g
        clk, x, a, b = g.pi("clk"), g.pi(), g.pi(), g.pi()
        q = g.net()
        d = g.lut(XOR2, (q, x))
        g.ff(d, clk, q)
        dec = g.lut(AND2, (q, x))
        out = g.lut(MUX, (a, b, dec))
        fsm = f.piece("fsm", [g.cell_of(q), g.cell_of(d)], (x, clk), (q,), {"Q": (q,)})
        mux = f.piece("mux", [g.cell_of(out)], (a, b, dec), (out,), {"S": (dec,), "Y": (out,)})
        f.role(g.cell_of(dec), 2.0)
        got = UnitDetector().propose(f.ctx(g.build()))
        self.assertEqual([c.kind for c in got], ["control_unit"])
        self.assertEqual(got[0].children, tuple(sorted((fsm, mux))))
        self.assertIn(g.cell_of(dec), got[0].cells)

    def test_piece_in_one_unit_only(self) -> None:
        f = Fix()
        ids, s = datapath(f)
        g = f.g
        clk, x = g.pi("clk2"), g.pi()
        q = g.net()
        d = g.lut(XOR2, (q, x))
        g.ff(d, clk, q)
        sel = g.lut(AND2, (q, x))
        # the register's enable port (a control port) is driven by the fsm's decode too
        f.pieces[2] = Piece(f.pieces[2].hid, "register", f.pieces[2].ins + (sel,), f.pieces[2].outs,
                            f.pieces[2].cells)
        f.ov.get(ids[2]).nets["en"] = (sel,)
        f.ov.get(ids[1]).nets["S"] = (sel,)
        fsm = f.piece("fsm", [g.cell_of(q), g.cell_of(d)], (x, clk), (q,), {"Q": (q,)})
        f.role(g.cell_of(sel), 2.0)
        got = UnitDetector().propose(f.ctx(g.build()))
        kinds = sorted(c.kind for c in got)
        self.assertEqual(kinds, ["control_unit", "datapath_unit"])
        seen: list[str] = []
        for c in got:
            seen.extend(c.children)
        self.assertEqual(len(seen), len(set(seen)))
        control = next(c for c in got if c.kind == "control_unit")
        self.assertEqual(control.children, (fsm,))

    def test_units_not_before_round_2(self) -> None:
        f = Fix()
        datapath(f)
        graph = f.g.build()
        self.assertEqual(UnitDetector().propose(f.ctx(graph, rnd=1)), [])
        self.assertEqual(len(UnitDetector().propose(f.ctx(graph, rnd=2))), 1)


if __name__ == "__main__":
    unittest.main()
