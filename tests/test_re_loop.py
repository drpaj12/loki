import importlib
import json
import math
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
from tests.helpers import DATA, can_run_f2, have_f3, micro, odin3_root, odin_available

RE = DATA / "re"
HARD = (
    ".model h\n.inputs a b cin\n.outputs s cout\n"
    ".subckt adder a=a b=b cin=cin cout=cout sumout=s\n.end\n"
)
# An adder with a constant carry-in and a multiply: ``unmap`` recovers a ``$add`` and a ``$mul``.
MIX = (
    ".model mix\n.inputs a b d\n.outputs s co p\n.names k\n"
    ".subckt adder a=a b=b cin=k cout=co sumout=s\n"
    ".subckt multiply a[0]=d b[0]=d out[0]=p\n.end\n"
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

    def test_time_budget_stop(self) -> None:
        """Spec 9.1: the loop stops before a round when the time budget is spent."""
        res = run_re(opts(RE / "add2.blif", time_budget=0))
        self.assertEqual(len(res.rounds), 1)
        self.assertEqual(res.stop_reason, "time_budget")

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

    def test_calib_floor_mismatch_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calib.json"
            path.write_text(json.dumps({"schema": 1, "floor": "f3"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                run_re(opts(RE / "mux1.blif", calib=path))

    def test_keep_levels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = run_re(opts(RE / "add2.blif", keep_levels=Path(tmp)))
            names = sorted(p.name for p in Path(tmp).iterdir())
        self.assertEqual(names, ["level0.json", "level1.json", "level2.json"])
        self.assertTrue(res.overlay.committed())

    def test_max_proofs_cap(self) -> None:
        """MAX_PROOFS bounds the real proofs of a round, spot checks included; with two slots
        the first adder is proved and the three transfers are checked by one spot proof."""
        with mock.patch("loki.re.loop.bayes.MAX_PROOFS", 2):
            res = run_re(opts(RE / "add2x4.blif", max_rounds=1))
        self.assertEqual(engines(res)["cone_check"], 2)
        self.assertEqual(engines(res)["transfer"], 3)
        self.assertEqual(res.rounds[0]["engines"],
                         {"cone_check": 2, "transfer": 3, "truth_table": 0})

    def test_seed_reaches_prover(self) -> None:
        """Spec 10: the prover's sampling rng is rng("prove:<hid>"), so --seed reaches it."""
        draws: list[float] = []

        def fake(claim: Claim, graph: FnGraph, cc: Any, rng: Any) -> Verdict:
            draws.append(rng.random())
            return Verdict("unproven", "truth_table", "sampled", {})

        runs: list[list[float]] = []
        for seed in (7, 7, 8):
            draws.clear()
            with mock.patch("loki.re.loop.prove", fake):
                run_re(opts(RE / "add2.blif", seed=seed, max_rounds=1))
            runs.append(list(draws))
        self.assertTrue(runs[0])
        self.assertEqual(runs[0], runs[1])
        self.assertNotEqual(runs[0], runs[2])

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

    def test_f1_declined_adder(self) -> None:
        """A real carry-in is not recovered: ``unmap`` runs, the hard cell stays and its
        ``hard_add`` is open with the ``declined_chain`` evidence (spec 7.2)."""
        root = odin3_root()
        assert root is not None
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "h.blif"
            path.write_text(HARD, encoding="utf-8")
            res = run_re(opts(path, floor="f1-k6", techlib=root / "lib" / "vtr.o3lib"))
        self.assertEqual(res.notes["unmap"], "ok")
        self.assertEqual(res.final_equiv["status"], "skipped:hard")
        got = of_kind(res, "hard_add")
        self.assertEqual([h.features.get("declined_chain") for h in got], ["yes"])
        self.assertEqual([h.status for h in got], ["committed"])

    def test_f1_unmap_failure_falls_back_and_discards(self) -> None:
        """Spec 7.2/9.1: a *failed* ``unmap`` is not the pass-absent case, so the working copy is
        discarded (the binding contract: a failed pass may have mutated it) and the run starts
        again from level 0; the cells stay opaque and the report says ``unmap: unavailable``."""
        root = odin3_root()
        assert root is not None
        mod = importlib.import_module("odin3")
        real = mod.Design.run_pass
        failed: list[Any] = []

        def fake(design: Any, name: str, args: str = "") -> None:
            if name == "unmap":
                failed.append(design)
                raise mod.Odin3Error("odin3_design_run_pass", 1, "unmap")
            real(design, name, args)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mix.blif"
            path.write_text(MIX, encoding="utf-8")
            with mock.patch.object(mod.Design, "run_pass", fake):
                res = run_re(opts(path, floor="f1-k6", techlib=root / "lib" / "vtr.o3lib"))
        self.assertEqual(res.notes["unmap"], "unavailable")
        self.assertEqual([h for h in res.overlay.all() if h.kind.startswith("hard_")], [])
        self.assertEqual(res.final_equiv["status"], "skipped:hard")
        self.assertEqual(len(failed), 1)
        self.assertIsNone(failed[0].ptr)
        self.assertIsNot(res.final, failed[0])

    def test_f1_recovered_hard_cells_commit(self) -> None:
        """An adder with a constant carry-in and a multiply are recovered: both are confirmed
        at probability 1 and committed as ``hard_*`` pieces (plan Task 17)."""
        root = odin3_root()
        assert root is not None
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mix.blif"
            path.write_text(MIX, encoding="utf-8")
            res = run_re(opts(path, floor="f1-k6", techlib=root / "lib" / "vtr.o3lib"))
        self.assertEqual(res.notes["unmap"], "ok")
        got = [h for h in res.overlay.all() if h.kind.startswith("hard_")]
        self.assertEqual(sorted(h.kind for h in got), ["hard_add", "hard_mul"])
        self.assertEqual([h.status for h in got], ["committed", "committed"])
        self.assertTrue(all(h.log_odds == math.inf for h in got))
        self.assertEqual(sum(len(h.cells) for h in got), 2)


@unittest.skipUnless(have_f3(), "needs Odin III with gate mapping")
class VerilogInputFinalCheckTest(unittest.TestCase):
    def test_verilog_input_checked_as_blif(self) -> None:
        """Loki issue #14: ``equiv-check`` reads BLIF only, so a gate-level ``.v`` input is
        compared as the BLIF level 0 writes out (the mapped netlist), not as raw Verilog text;
        the status is honest instead of always ``error`` with ``tool_exit`` 2."""
        res = run_re(opts(micro("bm_DL_4_bit_comparator"), floor="f3"))
        self.assertEqual(res.final_equiv["status"], "equivalent")
        self.assertEqual(res.final_equiv["tool_exit"], 0)


@unittest.skipUnless(odin_available(), "needs Odin III")
class NoToolTest(unittest.TestCase):
    def test_missing_root_skips_equiv(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "ODIN3_ROOT"}
        with mock.patch.dict("os.environ", env, clear=True):
            res = run_re(opts(RE / "zero.blif", odin3_root=None))
        self.assertEqual(res.final_equiv["status"], "skipped:no-odin3-root")


if __name__ == "__main__":
    unittest.main()
