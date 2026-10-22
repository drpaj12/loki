import random
import tempfile
import unittest
from pathlib import Path

from loki.build import build_floor
from loki.features.npn import NAMED
from loki.re.bayes import DEFAULTS, PROVE_P
from loki.re.detectors import Candidate
from loki.re.detectors.arith import (
    ArithDetector,
    carry_nets,
    cut_class,
    find_chains,
    orient,
    support_index,
)
from loki.re.fngraph import from_design
from loki.re.normalise import load_level0
from loki.re.overlay import Overlay
from loki.re.sim import SUPPORT_MAX
from loki.re.view import View
from tests.helpers import can_run_f2, f2_arch, micro, odin3_root, odin_available
from tests.re_fixtures import GB, lut_fn, make_ctx, packed_adder, ripple, table_of


def by_kind(cands: list[Candidate], kind: str) -> list[Candidate]:
    return [c for c in cands if c.kind == kind]


def chains(cands: list[Candidate]) -> list[Candidate]:
    return [c for c in cands if c.kind in ("adder", "subtractor", "adder_cin")]


def words(g: GB, k: int) -> tuple[list[int], list[int]]:
    return g.pis_n(k, "a"), g.pis_n(k, "b")


class ChainTest(unittest.TestCase):
    def test_ripple_adder_4_chain(self) -> None:
        g = GB()
        a, b = words(g, 4)
        ys, cs = ripple(g, a, b)
        graph = g.build([*ys, cs[-1]])
        chains = find_chains(View.level0(graph), graph)
        self.assertEqual(chains, [(tuple(ys), tuple(zip(a, b, strict=True)))])
        (add,) = by_kind(ArithDetector().propose(make_ctx(graph)), "adder")
        assert add.claim is not None
        self.assertEqual(add.claim.op, "add")
        self.assertEqual(dict(add.claim.params)["Y_WIDTH"], 5)
        self.assertEqual(add.nets["Y"], (*ys, cs[-1]))
        self.assertEqual((add.nets["A"], add.nets["B"]), (tuple(a), tuple(b)))
        self.assertEqual(add.features["width"], "3-4")
        self.assertEqual(add.features["out_reads"], "yes")

    def test_lut6_packed_adder_chain(self) -> None:
        g = GB()
        a, b = words(g, 3)
        ys = packed_adder(g, a, b)
        graph = g.build(ys)
        view = View.level0(graph)
        self.assertEqual(find_chains(view, graph), [(tuple(ys), tuple(zip(a, b, strict=True)))])
        self.assertEqual(carry_nets(view, tuple(ys)), {})
        (add,) = chains(ArithDetector().propose(make_ctx(graph)))
        assert add.claim is not None
        self.assertEqual((add.kind, dict(add.claim.params)["Y_WIDTH"]), ("adder", 3))

    def _sub(self, swap_ids: bool) -> Candidate:
        g = GB()
        if swap_ids:
            b = g.pis_n(4, "b")
            a = g.pis_n(4, "a")
        else:
            a, b = words(g, 4)
        ys, cs = ripple(g, a, b, ops=["sub"] * 4)
        graph = g.build([*ys, cs[-1]])
        (sub,) = chains(ArithDetector().propose(make_ctx(graph)))
        self.assertEqual(sub.kind, "subtractor")
        assert sub.claim is not None
        self.assertEqual(dict(sub.claim.inputs)["A"], tuple(a))
        self.assertEqual(dict(sub.claim.inputs)["B"], tuple(b))
        return sub

    def test_subtractor_orientation(self) -> None:
        self.assertEqual(self._sub(False).params["orient"], "0000")
        self.assertEqual(self._sub(True).params["orient"], "1111")

    def test_mixed_orientation_no_candidate(self) -> None:
        g = GB()
        a, b = words(g, 4)
        ys, cs = ripple(g, a, b, ops=["add", "add", "sub", "sub"])
        graph = g.build([*ys, cs[-1]])
        chain = find_chains(View.level0(graph), graph)[0]
        self.assertIsNone(orient(graph, (*chain[0], cs[-1]), chain[1]))
        self.assertEqual(chains(ArithDetector().propose(make_ctx(graph))), [])

    def test_carry_in_gives_adder_cin(self) -> None:
        g = GB()
        a, b = words(g, 4)
        cin = g.pi("cin")
        ys, cs = ripple(g, a, b, cin=cin)
        graph = g.build([*ys, cs[-1]])
        (add,) = chains(ArithDetector().propose(make_ctx(graph)))
        assert add.claim is not None
        self.assertEqual((add.kind, add.claim.op), ("adder_cin", "add_cin"))
        self.assertEqual(dict(add.claim.inputs)["CI"], (cin,))
        self.assertEqual(add.nets["Y"], (*ys, cs[-1]))

    def test_support_none_skipped(self) -> None:
        g = GB()
        xor6 = table_of(6, lambda v: sum(v) & 1)
        layer = [g.lut(xor6, g.pis_n(6, "x")) for _ in range(8)]
        top = g.lut(xor6, layer[:6])
        top2 = g.lut(xor6, [top, *layer[6:], g.pi(), g.pi(), g.pi()])
        graph = g.build([top2])
        view = View.level0(graph)
        self.assertGreater(len(graph.pis), SUPPORT_MAX)
        self.assertIsNone(view.support.of(top2))
        self.assertEqual(ArithDetector().propose(make_ctx(graph)), [])


class RngTest(unittest.TestCase):
    def test_chain_sampling_uses_ctx_rng(self) -> None:
        """Spec 10: randomness only through ``rng(purpose)``; the sum-bit sampling of a chain
        (two nets share a support) must take its Random from the round context, so --seed
        reaches it."""
        g = GB()
        a, b = words(g, 4)
        ripple(g, a, b)
        graph = g.build()
        purposes: list[str] = []

        def rng(purpose: str) -> random.Random:
            purposes.append(purpose)
            return random.Random(purpose)

        got = ArithDetector().propose(make_ctx(graph, rng=rng))
        self.assertTrue([p for p in purposes if p.startswith("arith:")])
        self.assertTrue(by_kind(got, "adder"))


class NpnTest(unittest.TestCase):
    def test_npn_sum_carry_ripple(self) -> None:
        g = GB()
        a, b = words(g, 4)
        ys, cs = ripple(g, a, b)
        (add,) = chains(ArithDetector().propose(make_ctx(g.build([*ys, cs[-1]]))))
        self.assertEqual((add.features["npn_sum"], add.features["npn_carry"]), ("all", "all"))

    def test_npn_no_cut_packed(self) -> None:
        g = GB()
        a, b = words(g, 3)
        ys = packed_adder(g, a, b)
        (add,) = chains(ArithDetector().propose(make_ctx(g.build(ys))))
        self.assertEqual((add.features["npn_sum"], add.features["npn_carry"]),
                         ("no_cut", "no_cut"))

    def test_subtractor_npn_classes(self) -> None:
        g = GB()
        a, b = words(g, 4)
        ys, cs = ripple(g, a, b, ops=["sub"] * 4)
        graph = g.build([*ys, cs[-1]])
        self.assertEqual(cut_class(graph, [a[1], b[1], cs[0]], ys[1]), NAMED["xor3"])
        self.assertEqual(cut_class(graph, [a[1], b[1], cs[0]], cs[1]), NAMED["maj3"])
        self.assertIsNone(cut_class(graph, [a[1], b[1]], ys[1]))
        (sub,) = chains(ArithDetector().propose(make_ctx(graph)))
        self.assertEqual((sub.features["npn_sum"], sub.features["npn_carry"]), ("all", "all"))

    def test_npn_low_chain_not_proved(self) -> None:
        g = GB()
        a, b = words(g, 3)
        xor2 = table_of(2, lambda v: v[0] ^ v[1])
        and3 = table_of(3, lambda v: int(sum(v) == 3))
        or3 = table_of(3, lambda v: int(sum(v) > 0))
        y0 = g.lut(xor2, (a[0], b[0]))
        c1 = g.lut(xor2, (a[0], b[0]))
        y1 = g.lut(and3, (a[1], b[1], c1))
        c2 = g.lut(or3, (a[1], b[1], c1))
        y2 = g.lut(and3, (a[2], b[2], c2))
        (add,) = chains(ArithDetector().propose(make_ctx(g.build())))
        self.assertEqual(add.nets["Y"], (y0, y1, y2))
        self.assertEqual((add.features["npn_sum"], add.features["npn_carry"]), ("low", "low"))
        self.assertEqual(add.features["out_reads"], "no")
        ov = Overlay()
        h = ov.add(add, "arith", 1)
        ov.rescore(DEFAULTS, 1)
        ov.compete(1)
        self.assertLess(h.p_comp, PROVE_P)

    def test_features_none_no_npn(self) -> None:
        g = GB()
        a, b = words(g, 4)
        ys, cs = ripple(g, a, b)
        (add,) = chains(ArithDetector().propose(make_ctx(g.build([*ys, cs[-1]]), features=False)))
        self.assertFalse([f for f in add.features if f.startswith("npn_")])


class CompareTest(unittest.TestCase):
    def _lt(self, xor: bool = False) -> tuple[GB, list[int], list[int], int]:
        g = GB()
        a, b = words(g, 4)
        if xor:
            eqs = [lut_fn(g, lambda v: 1 - (v[0] ^ v[1]), (a[i], b[i])) for i in range(4)]
            z = lut_fn(g, lambda v: int(all(v)), eqs)
            return g, a, b, z
        low = lut_fn(g, lambda v: int(v[0] + 2 * v[1] < v[2] + 2 * v[3]), (a[0], a[1], b[0], b[1]))
        z = lut_fn(g, lambda v: int((v[0] + 2 * v[1] < v[2] + 2 * v[3])
                                    or (v[0] + 2 * v[1] == v[2] + 2 * v[3] and v[4])),
                   (a[2], a[3], b[2], b[3], low))
        return g, a, b, z

    @staticmethod
    def _buses(a: list[int], b: list[int]) -> Overlay:
        ov = Overlay()
        for n, word in ((9001, a), (9002, b)):
            ov.add(Candidate("bus", frozenset({n}), {f"slice{i}": (x,) for i, x in enumerate(word)},
                             {"k": len(word)}, {}), "bus", 1)
        return ov

    def test_comparator_from_buses(self) -> None:
        g, a, b, z = self._lt()
        graph = g.build([z])
        got = [c for c in by_kind(ArithDetector().propose(make_ctx(graph, self._buses(a, b))),
                                  "comparator") if c.nets["Y"] == (z,)]
        self.assertEqual(len(got), 12)
        self.assertEqual({str(c.params["op"]) for c in got}, {"eq", "ne", "lt", "le", "gt", "ge"})
        self.assertTrue(all(c.claim is not None for c in got))
        lt = [c for c in got if c.params == {"op": "lt", "pairing": "fwd", "width": 4}]
        assert lt[0].claim is not None
        self.assertEqual(dict(lt[0].claim.inputs), {"A": tuple(a), "B": tuple(b)})

    def test_comparator_npn_xor2(self) -> None:
        g, a, b, z = self._lt(xor=True)
        graph = g.build([z])
        got = by_kind(ArithDetector().propose(make_ctx(graph, self._buses(a, b))), "comparator")
        self.assertEqual({c.features["npn_xor2"] for c in got}, {"yes"})
        none = by_kind(ArithDetector().propose(
            make_ctx(graph, self._buses(a, b), features=False)), "comparator")
        self.assertTrue(all("npn_xor2" not in c.features for c in none))

    def test_comparator_without_buses(self) -> None:
        """L1 spec 15 pin 4: a LUT-packed comparator has no per-bit cells, so no ``bus``
        hypotheses; the operand words are read off the function of the output."""
        for xor in (False, True):
            g, a, b, z = self._lt(xor)
            got = [c for c in by_kind(ArithDetector().propose(make_ctx(g.build([z]))), "comparator")
                   if c.nets["Y"] == (z,)]
            self.assertTrue(got)
            self.assertTrue(all(c.params["pairing"] == "fwd" for c in got))
            ops = {str(c.params["op"]) for c in got}
            self.assertEqual(ops, {"eq"} if xor else {"gt"})
            for c in got:
                assert c.claim is not None
                ins = dict(c.claim.inputs)
                self.assertEqual(sorted((*ins["A"], *ins["B"])), sorted((*a, *b)))
                if not xor:
                    self.assertEqual({tuple(ins["A"]), tuple(ins["B"])}, {tuple(a), tuple(b)})

    def test_no_derived_comparator_for_and_or_parity(self) -> None:
        for fn in (lambda v: int(all(v)), lambda v: int(any(v)), lambda v: sum(v) & 1):
            g = GB()
            z = lut_fn(g, fn, g.pis_n(4, "x"))
            got = by_kind(ArithDetector().propose(make_ctx(g.build([z]))), "comparator")
            self.assertEqual(got, [])

    def test_eq_const(self) -> None:
        for c, op, kind_fn in (
            (13, "eq", lambda v: int(list(v) == [1, 0, 1, 1, 0])),
            (18, "ne", lambda v: int(list(v) != [0, 1, 0, 0, 1])),
        ):
            g = GB()
            srcs = g.pis_n(5, "x")
            z = lut_fn(g, kind_fn, srcs)
            got = by_kind(ArithDetector().propose(make_ctx(g.build([z]))), "eq_const")
            self.assertEqual(len(got), 1)
            self.assertEqual(dict(got[0].params), {"op": op, "C": c, "width": 5})
            assert got[0].claim is not None
            self.assertEqual(got[0].claim.op, "eq_const" if op == "eq" else "ne_const")
            self.assertEqual(dict(got[0].claim.inputs)["A"], tuple(srcs))


class MicroTest(unittest.TestCase):
    @unittest.skipUnless(odin_available() and can_run_f2(), "needs Odin III and ABC")
    def test_arith_on_micro_adder(self) -> None:
        root = odin3_root()
        assert root is not None
        name = "bm_DL_four_bit_adder_continuous_assign"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            res = build_floor("d", [micro(name)], None, "f2", f2_arch(), out, root)
            self.assertEqual(res.status, "ok")
            design = load_level0(out / "d" / "f2" / "netlist.blif", "f2", None, None)
            self.addCleanup(design.close)
            graph = from_design(design)
        got = ArithDetector().propose(make_ctx(graph))
        adders = [c for c in got if c.kind in ("adder", "adder_cin")]
        self.assertTrue(adders)
        self.assertTrue(any(dict(c.params)["width"] == 4 for c in adders))
        self.assertTrue(support_index(View.level0(graph)))


if __name__ == "__main__":
    unittest.main()
