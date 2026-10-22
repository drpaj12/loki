import random
import tempfile
import unittest
from pathlib import Path

from loki.re.claims import REFS, Claim
from loki.re.fngraph import Cell, FnGraph, from_design
from loki.re.normalise import load_level0
from loki.re.provers import ConeCheckProver, TruthTableProver, cex_ports, parse_cex, prove
from tests.helpers import DATA, can_run_f2, odin_available
from tests.test_re_sim import AND2, XOR2, XOR3, add2, graph_of, lut

ADD2 = DATA / "re" / "add2.blif"
MAJ3 = 0b11101000
ADD_P = (("A_WIDTH", 2), ("B_WIDTH", 2), ("Y_WIDTH", 2))


def add2_claim(op: str = "add") -> Claim:
    return Claim(op, ADD_P, (("A", (1, 2)), ("B", (3, 4))), (("Y", (5, 7)),))


def ripple(n: int) -> tuple[FnGraph, Claim]:
    cells: list[Cell] = []
    a = [1 + i for i in range(n)]
    b = [101 + i for i in range(n)]
    y = [201 + i for i in range(n)]
    c = [301 + i for i in range(n)]
    for i in range(n):
        if i == 0:
            cells.append(lut(1000, (a[0], b[0]), y[0], XOR2))
            cells.append(lut(1001, (a[0], b[0]), c[0], AND2))
        else:
            cells.append(lut(1000 + 2 * i, (a[i], b[i], c[i - 1]), y[i], XOR3))
            cells.append(lut(1001 + 2 * i, (a[i], b[i], c[i - 1]), c[i], MAJ3))
    graph = graph_of(cells, tuple(a + b), tuple(y))
    p = (("A_WIDTH", n), ("B_WIDTH", n), ("Y_WIDTH", n))
    return graph, Claim("add", p, (("A", tuple(a)), ("B", tuple(b))), (("Y", tuple(y)),))


def side_graph(table: int) -> tuple[FnGraph, Claim]:
    """y = a xor t, t = f(b, s) with s a side input (net 9)."""
    cells = [lut(20, (3, 9), 8, table), lut(21, (1, 8), 5, XOR2)]
    graph = graph_of(cells, (1, 3, 9), (5,))
    p = (("A_WIDTH", 1), ("B_WIDTH", 1), ("Y_WIDTH", 1))
    return graph, Claim("add", p, (("A", (1,)), ("B", (3,))), (("Y", (5,)),))


class TruthTableTest(unittest.TestCase):
    def test_parse_cex(self) -> None:
        self.assertEqual(parse_cex("A[0]=1,B[2]=0"), {"A[0]": 1, "B[2]": 0})
        self.assertEqual(parse_cex(""), {})

    def test_tt_exact_equivalent(self) -> None:
        v = TruthTableProver().prove(add2(), add2_claim(), random.Random(1))
        self.assertEqual((v.verdict, v.engine, v.detail), ("equivalent", "truth_table", "exact"))

    def test_tt_exact_differs_with_cex(self) -> None:
        claim = add2_claim("sub")
        v = TruthTableProver().prove(add2(), claim, random.Random(1))
        self.assertEqual(v.verdict, "differs")
        ports = cex_ports(claim, v.cex)
        got = (ports["A"] + ports["B"]) & 3
        want = REFS["sub"](dict(ADD_P), ports)["Y"]
        self.assertNotEqual(got, want)

    def test_tt_side_inputs_enumerated(self) -> None:
        graph, claim = side_graph(0b1010)
        v = TruthTableProver().prove(graph, claim, random.Random(1))
        self.assertEqual(v.verdict, "equivalent")
        graph, claim = side_graph(XOR2)
        v = TruthTableProver().prove(graph, claim, random.Random(1))
        self.assertEqual(v.verdict, "differs")
        self.assertIn("n9", v.cex)

    def test_tt_sampled_unproven(self) -> None:
        graph, claim = ripple(8)
        v = TruthTableProver().prove(graph, claim, random.Random(1))
        self.assertEqual((v.verdict, v.detail), ("equivalent", "exact"))
        graph, claim = ripple(9)
        v1 = TruthTableProver().prove(graph, claim, random.Random(1))
        v2 = TruthTableProver().prove(graph, claim, random.Random(1))
        self.assertEqual((v1.verdict, v1.detail), ("unproven", "sampled"))
        self.assertEqual(v1, v2)

    def test_tt_sampled_finds_difference(self) -> None:
        graph, claim = ripple(9)
        wrong = Claim("sub", claim.params, claim.inputs, claim.outputs)
        v = TruthTableProver().prove(graph, wrong, random.Random(1))
        self.assertEqual((v.verdict, v.detail), ("differs", "sampled"))

    def test_prove_without_cone_check(self) -> None:
        v = prove(add2_claim(), add2(), None, random.Random(1))
        self.assertEqual(v.engine, "truth_table")


def names_to_ids(graph: FnGraph) -> dict[str, int]:
    return {name: net for net, name in graph.names.items()}


def claim_of(graph: FnGraph, op: str, a: tuple[str, ...], b: tuple[str, ...],
             y: tuple[str, ...], params: tuple[tuple[str, int | str], ...] = ADD_P) -> Claim:
    ids = names_to_ids(graph)
    return Claim(op, params, (("A", tuple(ids[n] for n in a)), ("B", tuple(ids[n] for n in b))),
                 (("Y", tuple(ids[n] for n in y)),))


@unittest.skipUnless(odin_available() and can_run_f2(), "needs Odin III and ABC")
class ConeCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self.design = load_level0(ADD2, "f2", None, None)
        self.graph = from_design(self.design)
        self.cc = ConeCheckProver(self.design, self.graph, 30)
        self.addCleanup(self.design.close)
        self.addCleanup(self.cc.close)

    def test_cc_add2_equivalent(self) -> None:
        claim = claim_of(self.graph, "add", ("a0", "a1"), ("b0", "b1"), ("y0", "y1"))
        v = self.cc.prove(claim, "lk1")
        self.assertEqual((v.verdict, v.engine), ("equivalent", "cone_check"))

    def test_cc_wrong_binding_differs(self) -> None:
        claim = claim_of(self.graph, "add", ("a1", "a0"), ("b0", "b1"), ("y0", "y1"))
        v = self.cc.prove(claim, "lk1")
        self.assertEqual(v.verdict, "differs")
        self.assertTrue(v.cex)
        self.assertTrue(all(k[0] in "AB" for k in v.cex))
        sub = claim_of(self.graph, "sub", ("a0", "a1"), ("b0", "b1"), ("y0", "y1"))
        self.assertEqual(self.cc.prove(sub, "lk2").verdict, "differs")

    def test_internal_net_read_outside_is_invalid(self) -> None:
        text = ADD2.read_text(encoding="utf-8").replace(".outputs y0 y1 q", ".outputs y0 y1 q c0")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "add2c.blif"
            path.write_text(text, encoding="utf-8")
            design = load_level0(path, "f2", None, None)
        self.addCleanup(design.close)
        graph = from_design(design)
        cc = ConeCheckProver(design, graph, 30)
        self.addCleanup(cc.close)
        claim = claim_of(graph, "add", ("a0", "a1"), ("b0", "b1"), ("y0", "y1"))
        v = cc.prove(claim, "lk1")
        self.assertEqual(v.verdict, "invalid")
        self.assertIsNone(cc.work.top().attr("odin3:cone_check"))
        v2 = prove(claim, graph, cc, random.Random(1))
        self.assertEqual((v2.verdict, v2.engine), ("equivalent", "truth_table"))

    def test_cc_error_recovers(self) -> None:
        bad = claim_of(self.graph, "add", ("a0", "a1"), ("b0", "b1"), ("y0", "y1"),
                       ADD_P + (("BOGUS", 1),))
        self.assertEqual(self.cc.prove(bad, "lk1").verdict, "error")
        good = claim_of(self.graph, "add", ("a0", "a1"), ("b0", "b1"), ("y0", "y1"))
        self.assertEqual(self.cc.prove(good, "lk2").verdict, "equivalent")

    def test_prove_uses_cone_check_first(self) -> None:
        claim = claim_of(self.graph, "add", ("a0", "a1"), ("b0", "b1"), ("y0", "y1"))
        v = prove(claim, self.graph, self.cc, random.Random(1))
        self.assertEqual(v.engine, "cone_check")


if __name__ == "__main__":
    unittest.main()
