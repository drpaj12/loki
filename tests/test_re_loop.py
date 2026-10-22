import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from loki.re import provers
from loki.re.claims import Claim
from loki.re.detectors import Candidate
from loki.re.fngraph import FnGraph
from loki.re.loop import ReOptions, RunResult, round_rejections, run_re
from loki.re.overlay import Evidence, Overlay
from loki.re.provers import Verdict
from loki.schemas import dump_json
from tests.helpers import DATA, can_run_f2, odin3_root, odin_available

RE = DATA / "re"
HARD = (
    ".model h\n.inputs a b cin\n.outputs s cout\n"
    ".subckt adder a=a b=b cin=cin cout=cout sumout=s\n.end\n"
)


def opts(path: Path, **kw: Any) -> ReOptions:
    base: dict[str, Any] = dict(
        netlist=path, floor="f2", odin3_root=odin3_root(), techlib=None, calib=None, seed=1,
        max_rounds=8, timeout=30, time_budget=3600, detectors=None, commit=True,
        keep_levels=None, features="all",
    )
    base.update(kw)
    return ReOptions(**base)


def of_kind(res: RunResult, kind: str) -> list[Any]:
    return [h for h in res.overlay.all() if h.kind == kind]


def engines(res: RunResult) -> dict[str, int]:
    total = {"cone_check": 0, "transfer": 0, "truth_table": 0}
    for rnd in res.rounds:
        eng = rnd["engines"]
        assert isinstance(eng, dict)
        for k in total:
            total[k] += int(eng[k])
    return total


def transfers_of(res: RunResult, kind: str) -> int:
    return sum(1 for h in of_kind(res, kind) for e in h.evidence if e.source == "transfer"
               and e.value == "equivalent")


class RoundRejectionsTest(unittest.TestCase):
    def test_counts_only_the_round(self) -> None:
        """Spec 11 rounds.rejected is the round's new rejections, not the cumulative count."""
        ov = Overlay()
        a = ov.add(Candidate("adder", frozenset({1, 2}), {}, {}, {}), "arith", 1)
        b = ov.add(Candidate("adder", frozenset({3, 4}), {}, {}, {}), "arith", 1)
        c = ov.add(Candidate("adder", frozenset({5, 6}), {}, {}, {}), "arith", 1)
        a.status, b.status, c.status = "rejected", "rejected", "rejected"
        a.evidence.append(Evidence(1, "competition", "p_comp", "low", 0.0))
        b.evidence.append(Evidence(2, "commit", "error", "footprint", 0.0))
        c.evidence.append(Evidence(1, "competition", "p_comp", "low", 0.0))
        c.status = "open"  # reopened: not rejected now
        self.assertEqual(round_rejections(ov, 1), 1)
        self.assertEqual(round_rejections(ov, 2), 1)
        self.assertEqual(round_rejections(ov, 3), 0)


@unittest.skipUnless(can_run_f2(), "needs Odin III, ABC and an F2 architecture")
class LoopTest(unittest.TestCase):
    def test_adder_end_to_end(self) -> None:
        res = run_re(opts(RE / "add2.blif"))
        adders = of_kind(res, "adder")
        self.assertEqual([h.status for h in adders], ["committed"])
        self.assertEqual(adders[0].commit, {"round": "2", "module": "adder_h1",
                                            "instance": "adder_h1_i", "form": "submod"})
        self.assertEqual(res.stop_reason, "fixed_point")
        self.assertEqual(res.final_equiv["status"], "equivalent")
        self.assertEqual(res.notes["unmap"], "n/a")

    def test_lone_mux_committed_and_equivalent(self) -> None:
        """L1 spec 15 pin 3: a lone 2:1 mux is committed as a WIDTH 1 ``mux``; the final BLIF
        keeps its ``$_MUX_`` gate as ``.names`` so equiv-check can read it."""
        res = run_re(opts(RE / "mux1.blif"))
        self.assertEqual([h.status for h in of_kind(res, "mux")], ["committed"])
        self.assertEqual(res.final_equiv["status"], "equivalent")

    def test_constant_only_design(self) -> None:
        res = run_re(opts(RE / "zero.blif"))
        self.assertEqual(len(res.rounds), 1)
        self.assertEqual(res.stop_reason, "fixed_point")
        self.assertEqual(res.overlay.committed(), [])
        self.assertEqual(res.final_equiv["status"], "equivalent")

    def test_no_commit_option(self) -> None:
        res = run_re(opts(RE / "add2.blif", commit=False))
        self.assertEqual(len(res.rounds), 1)
        self.assertEqual(res.stop_reason, "no_commit")
        self.assertEqual(res.overlay.committed(), [])

    def test_max_rounds(self) -> None:
        res = run_re(opts(RE / "add2.blif", max_rounds=1))
        self.assertEqual(len(res.rounds), 1)
        self.assertTrue(res.rounds[0]["committed"])
        self.assertEqual(res.stop_reason, "max_rounds")

    def test_deterministic_overlay(self) -> None:
        a = run_re(opts(RE / "add2x4.blif"))
        b = run_re(opts(RE / "add2x4.blif"))
        ja, jb = a.overlay.to_json(a.graph), b.overlay.to_json(b.graph)
        self.assertEqual(dump_json(ja), dump_json(jb))
        self.assertEqual(a.rounds, b.rounds)

    def test_keep_levels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = run_re(opts(RE / "add2.blif", keep_levels=Path(tmp)))
            names = sorted(p.name for p in Path(tmp).iterdir())
        self.assertEqual(names, ["level0.json", "level1.json", "level2.json"])
        self.assertTrue(res.overlay.committed())

    def test_transfer_four_adders(self) -> None:
        res = run_re(opts(RE / "add2x4.blif"))
        adders = of_kind(res, "adder")
        self.assertEqual([h.status for h in adders], ["committed"] * 4)
        self.assertEqual(transfers_of(res, "adder"), 3)
        self.assertEqual(sum(1 for h in adders if h.proof and h.proof["engine"] == "cone_check"), 2)
        self.assertEqual(engines(res)["cone_check"], 2)
        self.assertEqual(res.features["transfer_failures"], 0)
        self.assertEqual(res.features["transfers"], engines(res)["transfer"])
        self.assertEqual(res.final_equiv["status"], "equivalent")

    def test_reconvergent_no_transfer(self) -> None:
        res = run_re(opts(RE / "reconv.blif"))
        self.assertEqual(transfers_of(res, "adder"), 0)
        self.assertEqual(res.features["transfer_failures"], 0)
        self.assertEqual(res.final_equiv["status"], "equivalent")

    def test_features_none_no_transfer(self) -> None:
        res = run_re(opts(RE / "add2x4.blif", features="none"))
        self.assertEqual(res.notes["features"], "off")
        self.assertEqual(res.features["enabled"], False)
        self.assertEqual(engines(res)["transfer"], 0)
        self.assertEqual(engines(res)["cone_check"], 4)

    def test_no_transfer_without_spot_budget(self) -> None:
        """Spec 8.1: a transfer stands only when the spot check runs in the same round. With the
        MAX_PROOFS budget spent, no group is transferred (an unverified proof must not stand)."""
        with mock.patch("loki.re.loop.bayes.MAX_PROOFS", 1):
            res = run_re(opts(RE / "add2x4.blif", max_rounds=1))
        self.assertEqual(engines(res)["cone_check"], 1)
        self.assertEqual(engines(res)["transfer"], 0)
        self.assertEqual(res.features["transfers"], 0)
        self.assertEqual(res.features["transfer_failures"], 0)

    def test_spot_check_failure_revokes(self) -> None:
        real = provers.prove
        calls: list[str] = []

        def fake(claim: Claim, graph: FnGraph, cc: Any, rng: Any) -> Verdict:
            if claim.op == "add":
                calls.append("add")
                if len(calls) == 2:
                    return Verdict("differs", "cone_check", "", {})
            return real(claim, graph, cc, rng)

        with (mock.patch("loki.re.loop.cone_match", lambda g, a, b: True),
              mock.patch("loki.re.loop.prove", fake)):
            res = run_re(opts(RE / "add2x4.blif"))
        self.assertEqual(res.features["transfer_failures"], 1)
        refuted = [h for h in of_kind(res, "adder") if h.status == "refuted"]
        self.assertEqual(len(refuted), 1)
        first = res.rounds[0]
        self.assertEqual(first["transfer_failures"], 1)

    def test_f1_without_unmap(self) -> None:
        root = odin3_root()
        assert root is not None
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "h.blif"
            path.write_text(HARD, encoding="utf-8")
            res = run_re(opts(path, floor="f1-k6", techlib=root / "lib" / "vtr.o3lib"))
        self.assertEqual(res.notes["unmap"], "unavailable")
        self.assertEqual(res.final_equiv["status"], "skipped:hard")
        self.assertEqual(res.overlay.committed(), [])


@unittest.skipUnless(odin_available(), "needs Odin III")
class NoToolTest(unittest.TestCase):
    def test_missing_root_skips_equiv(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "ODIN3_ROOT"}
        with mock.patch.dict("os.environ", env, clear=True):
            res = run_re(opts(RE / "zero.blif", odin3_root=None))
        self.assertEqual(res.final_equiv["status"], "skipped:no-odin3-root")


if __name__ == "__main__":
    unittest.main()
