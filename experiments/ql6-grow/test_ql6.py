"""Tests of the Q-L6 anchors, model, statistics helpers and (with Odin III) signature caching."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import q6_eval as ev  # noqa: E402
import q6_model as qm  # noqa: E402
import q6_net as qn  # noqa: E402
from q6_env import KINDS  # noqa: E402

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

SHIFT = """.model t
.inputs a clk r
.outputs q3
.names a r d0
11 1
.names q0 r d1
11 1
.names q1 r d2
11 1
.names q2 r d3
11 1
.latch d0 q0 re clk 0
.latch d1 q1 re clk 0
.latch d2 q2 re clk 0
.latch d3 q3 re clk 0
.end
"""

COUNTER = """.model t
.inputs en clk
.outputs q2
.names q0 en d0
10 1
01 1
.names q1 q0 en d1
010 1
100 1
111 1
.names q2 q1 q0 en d2
0100 1
1010 1
1001 1
1111 1
.latch d0 q0 re clk 0
.latch d1 q1 re clk 0
.latch d2 q2 re clk 0
.end
"""


def graph(text: str) -> qn.Graph:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "n.blif"
        p.write_text(text, encoding="utf-8")
        return qn.Graph.read(p)


class AnchorTests(unittest.TestCase):
    def kinds(self, text: str) -> list[tuple[str, int]]:
        return sorted((a.kind, len(a.cells)) for a in qn.anchors(graph(text)))

    def test_ring_is_fsm(self) -> None:
        self.assertEqual(self.kinds(RING), [("fsm", 3)])

    def test_shift_chain(self) -> None:
        self.assertEqual(self.kinds(SHIFT), [("shift", 4)])

    def test_counter_triangular(self) -> None:
        self.assertEqual(self.kinds(COUNTER), [("counter", 3)])

    def test_cut_net(self) -> None:
        lines = [".model t", ".inputs g"] + [f".names g x{i} y{i}\n11 1" for i in range(16)]
        g = graph("\n".join(lines) + "\n.end\n")
        self.assertTrue(g.is_cut("g"))
        self.assertEqual(g.neighbours(0), [])


class ModelTests(unittest.TestCase):
    def samples(self) -> list[tuple[str, str, int, np.ndarray]]:
        rng = np.random.default_rng(1)
        out = []
        for k, kind in enumerate(KINDS):
            for _ in range(40):
                x = np.abs(rng.normal(0.0, 0.05, 129))
                x[k] += 0.8
                out.append(("O-gate", kind, int(rng.integers(2, 60)), x))
        return out

    def test_posterior_and_temperature(self) -> None:
        m = qm.fit_all(self.samples(), qm.census_prior())
        m.T = 0.05
        x = self.samples()[3][3]
        p = m.posterior("O-gate", x, 10)
        self.assertAlmostEqual(float(p.sum()), 1.0)
        self.assertEqual(int(np.argmax(p)), 0)
        t = qm.fit_temperature(m, self.samples())
        self.assertGreater(t, 0)

    def test_empty_signature_is_prior(self) -> None:
        m = qm.fit_all(self.samples(), qm.census_prior())
        z = np.zeros(129)
        self.assertAlmostEqual(float(m.posterior("O-gate", z, 3)[KINDS.index("glue")]),
                               m.prior["glue"] / sum(m.prior.values()))
        self.assertLess(m.evidence("O-gate", z, 3, np.ones(6) / 6), -1e5)

    def test_entropy(self) -> None:
        self.assertAlmostEqual(qm.entropy_bits(np.array([0.5, 0.5, 0.0])), 1.0)
        self.assertEqual(qm.entropy_bits(np.array([1.0, 0.0])), 0.0)

    def test_prior_sums_to_one(self) -> None:
        self.assertAlmostEqual(sum(qm.census_prior().values()), 1.0)

    def test_roundtrip(self) -> None:
        m = qm.fit_all(self.samples(), qm.census_prior())
        with tempfile.TemporaryDirectory() as d:
            qm.save(m, Path(d) / "m.json")
            m2 = qm.load(Path(d) / "m.json")
        x = self.samples()[0][3]
        self.assertTrue(np.allclose(m.posterior("O-gate", x, 8), m2.posterior("O-gate", x, 8),
                                    atol=1e-4))


class StatTests(unittest.TestCase):
    def test_spearman(self) -> None:
        self.assertAlmostEqual(ev.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)
        self.assertAlmostEqual(ev.spearman([1, 2, 3, 4], [1, 5, 6, 9]), 1.0)

    def test_right_block(self) -> None:
        self.assertTrue(ev.right({1, 2, 3, 4}, frozenset({1, 2, 3, 4, 5}))[0])
        self.assertFalse(ev.right({1, 2}, frozenset({1, 2, 3, 4, 5}))[0])
        self.assertFalse(ev.right(set(range(20)), frozenset({1, 2}))[0])

    def test_bins(self) -> None:
        self.assertEqual([ev.bin_of(s) for s in (1, 3, 4, 7, 8, 31, 32, 600)],
                         [0, 0, 1, 1, 2, 3, 4, 4])


def odin_ready() -> bool:
    lib = os.environ.get("ODIN3_LIB", "")
    return bool(lib) and Path(lib).is_file()


@unittest.skipUnless(odin_ready(), "Odin III not available")
class SigTests(unittest.TestCase):
    def test_cache_equals_fresh_count(self) -> None:
        import q6_sig as qs

        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "n.blif"
            p.write_text(COUNTER, encoding="utf-8")
            g = qn.Graph.read(p)
            sc = qs.SigCounter(p, g.b)
            for n in range(1, g.b.n + 1):
                blk = frozenset(range(n))
                first = sc.orbits(blk).copy()
                sc.cache.clear()
                self.assertTrue(np.array_equal(first, sc.orbits(blk)))
            sc.close()


if __name__ == "__main__":
    unittest.main()
