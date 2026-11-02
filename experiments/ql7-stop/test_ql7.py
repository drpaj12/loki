"""Tests of the Q-L7 split, geometry, rules, scoring and (with Odin III) path determinism.

Run from this directory: ``python -m unittest test_ql7``.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
import q7_env as env
import q7_feat as ft
import q7_rules as rules
import q7_score as sc

qn = env.mod("q6_net")

RING = """.model t
.inputs a clk
.outputs q0
.names q2 a n0
11 1
.names q0 n1
1 1
.names q1 n2
1 1
.latch n0 q0 re clk 0
.latch n1 q1 re clk 0
.latch n2 q2 re clk 0
.end
"""


def graph(text: str) -> qn.Graph:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "n.blif"
        p.write_text(text, encoding="utf-8")
        return qn.Graph.read(p)


def path(post_ng: list[float], phi: list[float], inter: list[list[int]], ntrue: list[int],
         ev: list[float] | None = None) -> ft.BlockPath:
    """A block path of K prefixes of sizes 1..K; kind 0 carries the non-glue posterior."""
    k = len(post_ng)
    post = np.zeros((k, len(env.KINDS)))
    post[:, 0] = post_ng
    post[:, -1] = 1.0 - np.array(post_ng)  # glue
    return ft.BlockPath(0, "fsm", np.arange(1, k + 1), post,
                        np.array(ev if ev is not None else [1.0] * k), np.array(phi),
                        np.zeros(k), np.zeros(k), np.full(k, 0.5), np.array(inter, dtype=np.int32),
                        np.array(ntrue, dtype=float), "frontier")


class SplitTests(unittest.TestCase):
    def test_split_partitions_the_odd_half(self) -> None:
        names = [f"design_{i}" for i in range(400)]
        parts = {n: env.stop_split(n) for n in names}
        self.assertEqual(set(parts.values()), {"", "TRAIN", "VALIDATION"})
        self.assertEqual(parts, {n: env.stop_split(n) for n in names})  # deterministic
        even = [n for n in names if parts[n] == ""]
        self.assertTrue(120 < len(even) < 280)  # about half are the even (likelihood) half


class GeometryTests(unittest.TestCase):
    def test_conductance_and_fans(self) -> None:
        g = graph(RING)
        geo = ft.Geometry(g)
        geo.add(0)  # .names q2 a n0: nets q2, a, n0; q2 and n0 cross
        self.assertEqual((geo.cut, geo.vol), (2, 3))
        self.assertEqual(len(geo.pin), 1)  # q2 is driven by the outside latch
        geo.add(3)  # latch n0 -> q0 closes n0, opens q0
        self.assertEqual((geo.cut, geo.vol), (2, 5))
        for c in (1, 2, 4, 5):
            geo.add(c)
        self.assertEqual(geo.cut, 0)  # the whole ring: nothing crosses
        self.assertAlmostEqual(geo.phi(), 0.0)
        self.assertEqual((len(geo.pin), len(geo.pout)), (0, 0))
        self.assertEqual(geo.n_ff, 3)


class RuleTests(unittest.TestCase):
    def test_right_and_jaccard(self) -> None:
        bp = path([0.5] * 4, [0.5] * 4, [[1, 2, 3, 4]], [4])
        self.assertEqual(bp.right[0].tolist(), [False, False, False, True])  # cov >= 0.8, J >= 0.5
        self.assertAlmostEqual(float(bp.jaccard[0, 1]), 2 / 4)

    def test_rule_a_lambda(self) -> None:
        bp = path([0.6, 0.7, 0.95, 0.96], [0.5] * 4, [[0, 0, 0, 0]], [9])
        self.assertEqual(rules.rule_a(bp, 0.0), 3)
        self.assertEqual(rules.rule_a(bp, 4.0), 0)  # a strong size penalty keeps it small

    def test_rule_b_skips_noise_minimum(self) -> None:
        phi = [0.9, 0.5, 0.6, 0.7, 0.1, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3]
        bp = path([0.5] * len(phi), phi, [[0] * len(phi)], [9])
        self.assertEqual(rules.rule_b(bp, 2), 1)  # minimum at 1 survives a window of 2
        self.assertEqual(rules.rule_b(bp, 4), 4)  # the larger window sees the deeper minimum

    def test_rule_b_fallback_and_empty_signature(self) -> None:
        bp = path([0.5] * 3, [0.1, 0.2, 0.3], [[0, 0, 0]], [9], ev=[-1e6, 1.0, 1.0])
        self.assertEqual(rules.rule_b(bp, 2), 1)  # prefix 0 has no signature, never chosen
        bp2 = path([0.5] * 3, [0.3, 0.2, 0.1], [[0, 0, 0]], [9], ev=[-1e6] * 3)
        self.assertEqual(rules.mask(bp2).tolist(), [True, True, True])

    def test_combine(self) -> None:
        bp = path([0.5] * 20, [0.5] * 20, [[0] * 20], [9])
        self.assertEqual(rules.combine("smaller", 3, 15, bp), 3)
        self.assertEqual(rules.combine("larger", 3, 15, bp), 15)
        self.assertEqual(rules.combine("middle", 3, 12, bp), 6)  # sizes 4 and 13, sqrt 7.2: size 7

    def test_classifier_learns_a_size_signal(self) -> None:
        blocks = []
        for i in range(12):
            inter = [[min(j + 1, 6) if j < 6 else 6 for j in range(10)]]
            blocks.append(path([0.5 + 0.01 * i] * 10, [0.5] * 10, inter, [6]))
        clf = rules.fit_classifier(blocks, [1] * len(blocks))
        self.assertIn(rules.rule_c(blocks[0], clf), range(4, 10))  # a right prefix (sizes 5 to 10)


class ScoreTests(unittest.TestCase):
    def unit(self) -> ft.UnitData:
        # one construct of 4 cells; block 0 reaches it at prefix 3 (size 4), block 1 is elsewhere
        b0 = path([0.6, 0.6, 0.6, 0.6, 0.6], [0.5] * 5, [[1, 2, 3, 4, 4]], [4])
        b1 = path([0.6] * 3, [0.5] * 3, [[0, 0, 0]], [4])
        return ft.UnitData("single", "d", "O-gate", 40, [(0, "fsm", 4)], [b0, b1])

    def test_right_claimed_and_classes(self) -> None:
        u = self.unit()
        rows, blocks = sc.score([u], [[3, 0]])
        self.assertEqual((rows[0]["right"], rows[0]["claimed"], rows[0]["cls"]), (1, 1, ""))
        self.assertEqual(blocks[0]["size"], 4)
        small, _ = sc.score([u], [[0, 0]])
        self.assertEqual(small[0]["cls"], "TOOSMALL")

    def test_toobig_and_merged(self) -> None:
        sizes_inter = [[1, 2, 3, 4, 4, 4, 4, 4, 4], [0, 0, 0, 0, 1, 2, 3, 4, 4]]
        b = path([0.6] * 9, [0.5] * 9, sizes_inter, [4, 4])
        u = ft.UnitData("comp", "d", "O-gate", 40, [(0, "fsm", 4), (1, "counter", 4)], [b])
        self.assertEqual(sc.failure_class(u, 0, [8]), "MERGED")  # also covers the second part
        b2 = path([0.6] * 9, [0.5] * 9, [sizes_inter[0]], [4])
        u2 = ft.UnitData("single", "d", "O-gate", 40, [(0, "fsm", 4)], [b2])
        self.assertEqual(sc.failure_class(u2, 0, [8]), "TOOBIG")
        self.assertEqual(sc.failure_class(u2, 0, [0]), "TOOSMALL")
        far = ft.UnitData("single", "d", "O-gate", 40, [(0, "fsm", 4)],
                          [path([0.6] * 3, [0.5] * 3, [[0, 0, 0]], [4])])
        self.assertEqual(sc.failure_class(far, 0, [0]), "NOSEED")
        order = ft.UnitData("single", "d", "O-gate", 40, [(0, "fsm", 4)],
                            [path([0.6] * 3, [0.5] * 3, [[0, 1, 1]], [4])])
        self.assertEqual(sc.failure_class(order, 0, [0]), "ORDER")


def odin_ready() -> bool:
    lib = os.environ.get("ODIN3_LIB", "")
    return bool(lib) and Path(lib).is_file()


@unittest.skipUnless(odin_ready() and (env.OUT6 / "blocks_nostop").is_dir(),
                     "Odin III or the #73 paths are absent")
class DeterminismTests(unittest.TestCase):
    def test_regrown_test_units_equal_the_73_paths(self) -> None:
        import q7_paths as pa

        qt = env.mod("q6_truth")
        qm = env.mod("q6_model")
        model = qm.load(env.OUT6 / "model.json")
        old_dir = env.OUT6 / "blocks_nostop"
        us = sorted((u for u in qt.units("TEST") if qt.has_labels(u) and
                     (old_dir / f"{u.set}__{u.design}__{u.cell}.json").is_file()),
                    key=lambda u: u.net.stat().st_size)[:3]
        self.assertEqual(len(us), 3)
        for u in us:
            new = pa.grow_unit(u, model)
            old = json.loads((old_dir / f"{u.set}__{u.design}__{u.cell}.json").read_text(
                encoding="utf-8"))
            for field in ("order", "anchor"):
                self.assertEqual([b[field] for b in new["blocks"]],
                                 [b[field] for b in old["blocks"]])


if __name__ == "__main__":
    unittest.main()
