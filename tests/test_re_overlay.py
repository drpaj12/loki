import math
import unittest

from loki.re.bayes import STRUCT_CAP, Calib
from loki.re.claims import Claim
from loki.re.detectors import Candidate
from loki.re.overlay import KINDS, Evidence, KindSpec, Overlay, register_kind
from loki.re.provers import Verdict
from loki.schemas import dump_json
from tests.test_re_sim import add2

EQUIV = Verdict("equivalent", "cone_check", "", {})
CALIB = Calib("", {}, {}, "t")


def cand(kind: str, cells: set[int], params: dict[str, int | str] | None = None,
         features: dict[str, str] | None = None, children: tuple[str, ...] = ()) -> Candidate:
    return Candidate(kind, frozenset(cells), {"Y": (1,)}, params or {}, features or {},
                     None, children)


class OverlayTest(unittest.TestCase):
    def test_merge_key_dedupes(self) -> None:
        ov = Overlay()
        a = ov.add(cand("adder", {1, 2}, {"w": 2}, {"k": "2"}), "arith", 1)
        b = ov.add(cand("adder", {1, 2}, {"w": 2}, {"k": "3-4", "x": "y"}), "arith", 2)
        self.assertIs(a, b)
        self.assertEqual(a.id, "h1")
        self.assertEqual(a.features, {"k": "3-4", "x": "y"})
        self.assertEqual(len(a.evidence), 2)
        c = ov.add(cand("adder", {1, 2}, {"w": 3}), "arith", 2)
        self.assertEqual(c.id, "h2")
        self.assertEqual([h.id for h in ov.by_kind("adder")], ["h1", "h2"])

    def test_logodds_sum_and_cap(self) -> None:
        ov = Overlay()
        h = ov.add(cand("adder", {1}, features={"f1": "x", "f2": "x", "npn_f": "x"}), "arith", 1)
        calib = Calib("", {"arith/adder": 1.0},
                      {"adder/f1": {"x": 4.0}, "adder/f2": {"x": 5.0},
                       "adder/npn_f": {"x": 3.0}}, "t", {"npn": 0.5})
        change = ov.rescore(calib, 1)
        self.assertEqual(h.log_odds, 1.0 + STRUCT_CAP)
        self.assertEqual(change, 1.0 + STRUCT_CAP)
        self.assertEqual(ov.rescore(calib, 2), 0.0)
        weighted = [e.llr for e in h.evidence if e.name == "npn_f"]
        self.assertEqual(weighted, [1.5])
        self.assertEqual(sum(1 for e in h.evidence if e.source == "prior"), 1)

    def test_weighted_rescore(self) -> None:
        ov = Overlay()
        h = ov.add(cand("adder", {1}, features={"npn_sum": "all"}), "arith", 1)
        calib = Calib("", {}, {"adder/npn_sum": {"all": 2.30}}, "t", {"npn": 0.5})
        ov.rescore(calib, 1)
        self.assertAlmostEqual(h.log_odds, 1.15)
        rec = next(e for e in h.evidence if e.name == "npn_sum")
        self.assertAlmostEqual(rec.llr, 1.15)
        big = Calib("", {}, {"adder/npn_sum": {"all": 20.0}}, "t", {"npn": 0.5})
        ov.rescore(big, 2)
        self.assertEqual(h.log_odds, STRUCT_CAP)
        none = Calib("", {}, {"adder/npn_sum": {"all": 2.30}}, "t", {"npn": 0.0})
        ov.rescore(none, 3)
        self.assertEqual(h.log_odds, 0.0)

    def test_apply_transfer_confirms(self) -> None:
        ov = Overlay()
        src = ov.add(cand("adder", {1}, {"w": 1}), "arith", 1)
        h = ov.add(cand("adder", {2}, {"w": 2}), "arith", 1)
        ov.apply_verdict(src.id, EQUIV, 1)
        ov.apply_transfer(h.id, src.id, 2)
        self.assertEqual(h.status, "confirmed")
        self.assertGreaterEqual(h.log_odds, 9.21)
        assert h.proof is not None
        self.assertEqual(h.proof["engine"], "transfer")
        self.assertEqual(h.proof["from"], src.id)
        self.assertEqual(h.proof["verdict"], "equivalent")
        self.assertEqual([(e.source, e.name, e.value) for e in h.evidence
                          if e.source == "transfer"], [("transfer", "h1", "equivalent")])
        ov.rescore(CALIB, 3)
        self.assertGreaterEqual(h.log_odds, 9.21)
        self.assertEqual(h.status, "confirmed")

    def test_revoke_transfers(self) -> None:
        ov = Overlay()
        calib = Calib("", {"arith/adder": 1.0}, {"adder/f": {"x": 2.0}}, "t")
        src = ov.add(cand("adder", {1}, {"w": 1}, {"f": "x"}), "arith", 1)
        a = ov.add(cand("adder", {2}, {"w": 2}, {"f": "x"}), "arith", 1)
        b = ov.add(cand("adder", {3}, {"w": 3}, {"f": "x"}), "arith", 1)
        other = ov.add(cand("adder", {4}, {"w": 4}, {"f": "x"}), "arith", 1)
        ov.rescore(calib, 1)
        for h in (src, other):
            ov.apply_verdict(h.id, EQUIV, 1)
        for h in (a, b):
            ov.apply_transfer(h.id, src.id, 2)
        self.assertEqual(ov.revoke_transfers(src.id, 3), [a.id, b.id])
        for h in (a, b):
            self.assertEqual(h.status, "open")
            self.assertIsNone(h.proof)
            self.assertAlmostEqual(h.log_odds, 3.0)
            self.assertEqual([e.value for e in h.evidence if e.source == "transfer"], ["revoked"])
        ov.rescore(calib, 4)
        self.assertAlmostEqual(a.log_odds, 3.0)
        self.assertEqual((src.status, other.status), ("confirmed", "confirmed"))
        self.assertGreaterEqual(src.log_odds, 9.21)
        self.assertEqual(ov.revoke_transfers(src.id, 5), [])

    def test_proof_sets_confirmed(self) -> None:
        ov = Overlay()
        h = ov.add(cand("adder", {1}), "arith", 1)
        ov.apply_verdict(h.id, EQUIV, 1)
        self.assertEqual(h.status, "confirmed")
        self.assertGreaterEqual(h.log_odds, 9.21)
        ov.rescore(CALIB, 2)
        self.assertGreaterEqual(h.log_odds, 9.21)
        assert h.proof is not None
        self.assertEqual(h.proof["engine"], "cone_check")

    def test_refute_is_final(self) -> None:
        ov = Overlay()
        h = ov.add(cand("adder", {1}, features={"f": "x"}), "arith", 1)
        ov.apply_verdict(h.id, Verdict("differs", "truth_table", "exact", {"A[0]": 1}), 1)
        self.assertEqual((h.status, h.log_odds, h.p_comp), ("refuted", -math.inf, 0.0))
        ov.add(cand("adder", {1}, features={"f": "y"}), "arith", 2)
        ov.rescore(Calib("", {}, {"adder/f": {"y": 8.0}}, "t"), 2)
        ov.compete(2)
        self.assertEqual((h.status, h.log_odds), ("refuted", -math.inf))
        assert h.proof is not None
        self.assertEqual(h.proof["cex"], "A[0]=1")

    def test_sampled_unproven_adds_sim_llr(self) -> None:
        ov = Overlay()
        h = ov.add(cand("counter", {1}), "seqfn", 1)
        ov.apply_verdict(h.id, Verdict("unproven", "truth_table", "sampled", {}), 1)
        self.assertAlmostEqual(h.log_odds, 4.61)
        ov.rescore(CALIB, 1)
        self.assertAlmostEqual(h.log_odds, 4.61)
        self.assertEqual(h.status, "open")

    def test_conflict_rule(self) -> None:
        ov = Overlay()
        a = ov.add(cand("adder", {1, 2}), "arith", 1)
        b = ov.add(cand("comparator", {2, 3}), "arith", 1)
        c = ov.add(cand("register", {1}), "ff_pattern", 1)
        d = ov.add(cand("mux", {1, 2}), "mux", 1)
        e = ov.add(cand("bus", {1, 2, 3}), "bus", 1)
        ov.link_nesting()
        ov.rescore(CALIB, 1)
        ov.compete(1)
        self.assertEqual(a.conflicts, ("h2", "h4"))
        self.assertEqual(b.conflicts, ("h1", "h4"))
        self.assertEqual(c.conflicts, ())
        self.assertEqual(c.parents, ("h1", "h4"))
        self.assertEqual(a.children, ("h3",))
        self.assertEqual(d.conflicts, ("h1", "h2"))
        self.assertEqual(e.conflicts, ())
        self.assertAlmostEqual(c.p_comp, 0.5)

    def test_p_comp_normalisation(self) -> None:
        ov = Overlay()
        a = ov.add(cand("adder", {1, 2}), "arith", 1)
        b = ov.add(cand("comparator", {2, 3}), "arith", 1)
        ov.rescore(CALIB, 1)
        ov.compete(1)
        self.assertAlmostEqual(a.p_comp, 1 / 3)
        self.assertAlmostEqual(b.p_comp, 1 / 3)

    def test_p_comp_inf_members(self) -> None:
        ov = Overlay()
        a = ov.add(cand("hard_add", {1, 2}), "hard", 1)
        b = ov.add(cand("adder", {2, 3}), "arith", 1)
        a.evidence.append(Evidence(1, "hard", "unmap", "x", math.inf))
        ov.rescore(CALIB, 1)
        self.assertEqual(a.log_odds, math.inf)
        ov.compete(1)
        self.assertEqual((a.p_comp, b.p_comp), (1.0, 0.0))
        self.assertEqual(b.status, "rejected")

    def test_equivalent_alternatives(self) -> None:
        def run() -> tuple[list[str], str, str, float, float]:
            ov = Overlay()
            m = ov.add(cand("mux", {1, 2, 3}, {"w": 1}), "mux", 1)
            c = ov.add(cand("comparator", {1, 2, 3}, {"op": "eq"}), "arith", 1)
            ov.apply_verdict(m.id, EQUIV, 1)
            ov.apply_verdict(c.id, EQUIV, 1)
            ov.rescore(CALIB, 1)
            ov.compete(1)
            chosen = [h.id for h in ov.select_commits(1)]
            return chosen, m.status, c.status, m.p_comp, c.p_comp

        chosen, mux, comp, pm, pc = run()
        self.assertEqual(chosen, ["h2"])
        self.assertEqual((mux, comp), ("alternative", "confirmed"))
        self.assertEqual(pm, pc)
        self.assertGreater(pm, 0.9)
        self.assertEqual(run(), (chosen, mux, comp, pm, pc))

    def test_child_raises_parent(self) -> None:
        ov = Overlay()
        kids = [ov.add(cand("ff_en", {10 + i}), "ff_pattern", 1) for i in range(4)]
        parent = ov.add(cand("register", {1, 2}, children=tuple(k.id for k in kids[:2])),
                        "ff_pattern", 1)
        for k in kids[:2]:
            ov.apply_verdict(k.id, EQUIV, 1)
        ov.rescore(CALIB, 1)
        self.assertAlmostEqual(parent.log_odds, 2.20)
        for k in kids[2:]:
            ov.apply_verdict(k.id, EQUIV, 1)
            ov.add(cand("register", {1, 2}, children=(k.id,)), "ff_pattern", 1)
        ov.rescore(CALIB, 2)
        self.assertAlmostEqual(parent.log_odds, 3.30)
        ov.apply_verdict(kids[0].id, Verdict("differs", "truth_table", "exact", {}), 2)
        ov.rescore(CALIB, 3)
        self.assertAlmostEqual(parent.log_odds, 3.30 - 2.30)

    def test_conflict_with_committed_rejected(self) -> None:
        ov = Overlay()
        a = ov.add(cand("adder", {1, 2}), "arith", 1)
        b = ov.add(cand("comparator", {2, 3}), "arith", 1)
        n = ov.add(cand("register", {1}), "ff_pattern", 1)
        a.status = "committed"
        ov.rescore(CALIB, 2)
        ov.compete(2)
        self.assertEqual(b.status, "rejected")
        self.assertEqual(n.status, "open")
        self.assertEqual([(e.source, e.value) for e in b.evidence if e.source == "competition"],
                         [("competition", "h1")])
        self.assertEqual(ov.committed(), [a])

    def test_low_p_rejected_and_reopened(self) -> None:
        ov = Overlay()
        h = ov.add(cand("bus", {1}, features={"f": "x"}), "bus", 1)
        ov.rescore(Calib("", {"bus/bus": -6.0}, {}, "t"), 1)
        ov.compete(1)
        self.assertEqual(h.status, "rejected")
        ov.rescore(Calib("", {"bus/bus": -6.0}, {}, "t"), 2)
        ov.compete(2)
        self.assertEqual(h.status, "rejected")
        ov.rescore(Calib("", {"bus/bus": 0.0}, {}, "t"), 3)
        ov.compete(3)
        self.assertEqual(h.status, "open")

    def test_select_commits_order(self) -> None:
        ov = Overlay()
        parent = ov.add(cand("adder", {1, 2, 3}), "arith", 1)
        child = ov.add(cand("register", {1}), "ff_pattern", 1)
        rival = ov.add(cand("comparator", {3, 4}), "arith", 1)
        free = ov.add(cand("counter", {9}), "seqfn", 1)
        ov.link_nesting()
        self.assertEqual(parent.children, (child.id,))
        for h, p in ((parent, 0.99), (child, 0.95), (rival, 0.95), (free, 0.91)):
            h.p_comp = p
        got = [h.id for h in ov.select_commits(1)]
        self.assertEqual(got, ["h3", "h2", "h4"])
        self.assertNotIn(parent.id, got)
        self.assertEqual(rival.status, "open")
        child.status = "committed"
        parent.p_comp = 0.99
        rival.p_comp = 0.95
        got2 = [h.id for h in ov.select_commits(2)]
        self.assertEqual(got2, ["h1", "h4"])
        self.assertEqual(rival.status, "rejected")

    def test_register_kind(self) -> None:
        with self.assertRaises(ValueError):
            register_kind("adder", KindSpec(2, True, "submod", 0))
        register_kind("zz_test_kind", KindSpec(2, True, "no", 0))
        self.assertIn("zz_test_kind", KINDS)
        del KINDS["zz_test_kind"]
        self.assertEqual(KINDS["adder"].commit, "raise+submod")
        self.assertGreater(KINDS["counter"].rank, KINDS["mux"].rank)

    def test_overlay_json_deterministic(self) -> None:
        graph = add2()

        def build() -> str:
            ov = Overlay()
            claim = Claim("add", (("A_WIDTH", 1),), (("A", (1,)),), (("Y", (5,)),))
            a = ov.add(Candidate("adder", frozenset({9, 10}), {"Y": (5, 7)}, {"w": 2},
                                 {"k": "2"}, claim), "arith", 1)
            b = ov.add(cand("comparator", {10, 11}), "arith", 1)
            a.evidence.append(Evidence(1, "hard", "unmap", "x", math.inf))
            ov.apply_verdict(b.id, Verdict("differs", "truth_table", "exact", {"A[0]": 1}), 1)
            ov.rescore(CALIB, 1)
            ov.compete(1)
            return dump_json(ov.to_json(graph))

        text = build()
        self.assertEqual(text, build())
        self.assertIn('"inf"', text)
        self.assertIn('"-inf"', text)
        self.assertNotIn("Infinity", text)
        self.assertIn('"schema": 1', text)


if __name__ == "__main__":
    unittest.main()
