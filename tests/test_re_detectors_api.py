import importlib.metadata
import unittest
from collections.abc import Iterable
from typing import Any
from unittest import mock

from loki.re.detectors import (
    DETECTOR_ORDER,
    Candidate,
    Detector,
    RoundContext,
    bin_count,
    check_candidate,
    k_bin,
    load_detectors,
)


class FakeDetector:
    name = "fake"
    kinds: tuple[str, ...] = ("bus",)

    def propose(self, ctx: RoundContext) -> Iterable[Candidate]:
        return []


class FakeEntryPoint:
    name = "fake"

    def load(self) -> Any:
        return FakeDetector


def cand(kind: str) -> Candidate:
    return Candidate(kind, frozenset({1}), {}, {}, {})


class ApiTest(unittest.TestCase):
    def test_unknown_detector_name(self) -> None:
        with self.assertRaises(ValueError):
            load_detectors(["no_such_detector"])

    def test_builtins_in_order(self) -> None:
        names = [d.name for d in load_detectors(None)]
        self.assertEqual(names, [n for n in DETECTOR_ORDER if n in names])
        self.assertIn("bus", names)
        self.assertIn("ff_pattern", names)

    def test_candidate_kind_checked(self) -> None:
        det: Detector = FakeDetector()
        check_candidate(det, cand("bus"))
        with self.assertRaises(ValueError):
            check_candidate(det, cand("adder"))
        det2 = FakeDetector()
        det2.kinds = ("nonsense",)
        with self.assertRaises(ValueError):
            check_candidate(det2, cand("nonsense"))

    def test_plugin_entry_point_loaded(self) -> None:
        def fake_eps(**kw: str) -> list[Any]:
            self.assertEqual(kw, {"group": "loki.detectors"})
            return [FakeEntryPoint()]

        with mock.patch.object(importlib.metadata, "entry_points", fake_eps):
            got = load_detectors(["bus", "fake"])
            self.assertEqual([d.name for d in got], ["bus", "fake"])
            self.assertEqual([d.name for d in load_detectors(None)][-1], "role")

    def test_bin_count(self) -> None:
        self.assertEqual([k_bin(n) for n in (2, 3, 4, 5, 8, 9, 40)],
                         ["2", "3-4", "3-4", "5-8", "5-8", "9+", "9+"])
        with self.assertRaises(ValueError):
            k_bin(1)
        with self.assertRaises(ValueError):
            bin_count(0, (1, 2), ("a",))


class ViewTest(unittest.TestCase):
    def test_level0_view(self) -> None:
        from loki.re.view import View
        from tests.re_fixtures import GB, MUX

        g = GB()
        g.pos.append(g.lut(MUX, (g.pi(), g.pi(), g.pi())))
        graph = g.build()
        v = View.level0(graph)
        self.assertEqual(v.free_cells, tuple(sorted(graph.cells)))
        self.assertEqual((v.pieces, v.absorbed), ((), frozenset()))
