"""Tests of the Q-L8c split, features, models, scoring and bootstrap.

Run from this directory: ``python -m unittest test_ql8c``.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

import numpy as np
import q8_env as env
import q8_feat as qf
import q8_model as qm
import q8_score as sc

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


def graph(text: str) -> Any:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "n.blif"
        p.write_text(text, encoding="utf-8")
        return qn.Graph.read(p)


def sample(cell: str, kind: str, size: int, rng: np.random.Generator, shift: float
           ) -> dict[str, Any]:
    x = np.abs(rng.normal(size=qf.N_FEAT)) + 0.1
    x[qf.S] += shift
    return {"cell": cell, "kind": kind, "size": size, "x": x}


class SplitTests(unittest.TestCase):
    def test_design_set_partitions_tune(self) -> None:
        names = [f"design_{i}" for i in range(400)]
        parts = {n: env.design_set(n) for n in names}
        self.assertEqual(set(parts.values()), {"FIT", "CAL", "VAL"})
        q7 = env.q7env
        for n in names:  # CAL and VAL are the #74 TRAIN and VALIDATION halves, FIT the even half
            want = {"": "FIT", "TRAIN": "CAL", "VALIDATION": "VAL"}[q7.stop_split(n)]
            self.assertEqual(parts[n], want)


class FeatureTests(unittest.TestCase):
    def test_feedback_depth_and_scalars(self) -> None:
        g = graph(RING)
        cells = set(range(g.b.n))
        succ = qf.internal_edges(g, cells)
        n_scc, inside, big, ffs, rank = qf.feedback(g, cells, succ)
        self.assertEqual((n_scc, inside, big, ffs, rank), (1, 6, 6, 3, 1))  # one 6-cell ring
        self.assertEqual(qf.comb_depth(g, cells, succ), 1)  # flip-flops cut the chains
        self.assertEqual(qf.feedback(g, {0}, qf.internal_edges(g, {0}))[0], 0)  # one cell, no loop

    def test_hard_kind(self) -> None:
        self.assertEqual([qf.hard_kind(m) for m in ("adder", "multiply", "dual_port_ram", "x")],
                         ["adder", "mult", "mem", "other"])


class ModelTests(unittest.TestCase):
    def data(self) -> list[dict[str, Any]]:
        rng = np.random.default_rng(0)
        out = []
        for kind, shift in zip(env.KINDS, (0.0, 3.0, -3.0, 6.0, -6.0, 9.0), strict=True):
            for i in range(120):
                out.append(sample("O-gate" if i % 2 else "O-lut", kind, 4 + i % 30, rng, shift))
        return out

    def test_models_separate_shifted_kinds(self) -> None:
        samples = self.data()
        for name, m in qm.build_models(samples).items():
            hits = 0
            for s in samples[::10]:
                ll = m.loglik(s["cell"], s["x"], s["size"])
                hits += env.KINDS[int(np.argmax(ll))] == s["kind"]
            self.assertGreaterEqual(hits, 60, name)  # 72 probes, six well separated kinds

    def test_posterior_normalised_and_empty_gets_prior(self) -> None:
        post = qm.Posterior({k: 1.0 for k in env.KINDS}, 0.1)
        p = post.post(np.arange(6.0), False)
        self.assertAlmostEqual(float(p.sum()), 1.0)
        self.assertEqual(int(np.argmax(p)), 5)
        np.testing.assert_allclose(post.post(np.arange(6.0), True), np.full(6, 1 / 6))

    def test_label_set(self) -> None:
        self.assertEqual(qm.label_set([]), [env.GLUE])
        self.assertEqual(qm.label_set(["fsm", "shift"]), [0, 2])


class ScoreTests(unittest.TestCase):
    def rec(self) -> dict[str, Any]:
        x = np.ones(qf.N_FEAT)
        return {"set": "comp", "design": "d", "cell": "O-gate", "n_cells": 20,
                "cons": [(0, "fsm", 8), (1, "counter", 6)],
                "blocks": [{"bid": 0, "size": 8, "x": x, "right": [(0, "fsm")]},
                           {"bid": 1, "size": 5, "x": x, "right": []},
                           {"bid": 2, "size": 3, "x": x, "right": [(1, "counter")]}],
                "true": [{"part": 0, "kind": "fsm", "size": 8, "x": x},
                         {"part": 1, "kind": "counter", "size": 6, "x": x}]}

    def test_counts(self) -> None:
        def post(_c: str, _x: np.ndarray, size: int) -> np.ndarray:
            p = np.full(6, 0.02)
            p[0 if size == 8 else 5 if size == 5 else 1] = 0.9
            return p

        v = sc.unit_vector(self.rec(), post)
        # claims: block 0 fsm (TP); block 1 glue (no claim); block 2 counter, too small to claim
        self.assertEqual(v[sc.O_CLAIMS:sc.O_CLAIMS + sc.K].tolist(), [1, 0, 0, 0, 0])
        self.assertEqual(v[sc.O_TP], 1)
        self.assertEqual(v[sc.O_REC:sc.O_REC + sc.K].tolist(), [1, 0, 0, 0, 0])
        self.assertEqual(v[sc.O_CONS:sc.O_CONS + sc.K].tolist(), [1, 1, 0, 0, 0])
        self.assertEqual(v[sc.O_TTP:sc.O_TTP + sc.K].tolist(), [1, 1, 0, 0, 0])
        self.assertEqual(v[sc.O_TOP3], 2)  # two right blocks
        self.assertAlmostEqual(sc.ece(v, 0), 0.1)  # one bin, all correct

    def test_f1_and_ece_edges(self) -> None:
        z = np.zeros(sc.K)
        self.assertEqual(float(sc.f1s(z, z, z, z).sum()), 0.0)
        self.assertTrue(np.isnan(sc.ece(np.zeros(sc.LEN), 0)))
        tp, cl, cons = np.full(sc.K, 2.0), np.full(sc.K, 4.0), np.full(sc.K, 4.0)
        np.testing.assert_allclose(sc.f1s(tp, cl, cons, tp), np.full(sc.K, 0.5))

    def test_bootstrap_is_paired_and_deterministic(self) -> None:
        a = {f"d{i}": np.full(2, float(i)) for i in range(6)}
        r1 = sc.boot(a, lambda s: float(s[0] - s[1]))
        self.assertEqual(r1, sc.boot(a, lambda s: float(s[0] - s[1])))
        self.assertEqual(r1[0], 0.0)
        self.assertEqual(r1[1:], (0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
