"""Decision statistics of the Loki vs HAL comparison, on synthetic pairs."""

import unittest

from loki.hal.compare import (
    Pair,
    bootstrap,
    cluster_of,
    decide,
    f1,
    interval,
    pooled_d,
)
from tests.helpers import skip_without


def pair(i: int, h: tuple[int, int], k: tuple[int, int], g: int, cluster: str = "") -> Pair:
    return Pair(cluster or f"c{i}", f"d{i}", h, k, k, g, g)


class ClusterTest(unittest.TestCase):
    def test_families(self) -> None:
        self.assertEqual(cluster_of("MI", "micro_bm_DL_2_1_mux"), "MI:bm_dl")
        self.assertEqual(cluster_of("MI", "micro_adder_hard_block"), "MI:adder_hard")
        self.assertEqual(cluster_of("MI", "micro_mux2"), "MI:mux")
        self.assertEqual(cluster_of("VT", "ve_Prob001"), "VT:ve_Prob001")


class NumbersTest(unittest.TestCase):
    def test_f1_and_pooled(self) -> None:
        self.assertEqual(f1(2, 3, 5), 0.5)
        self.assertEqual(f1(0, 0, 0), 0.0)
        ps = [pair(0, (1, 2), (2, 2), 2), pair(1, (0, 1), (1, 3), 2)]
        fk, fh, d, d5 = pooled_d(ps)
        self.assertAlmostEqual(fk, 2 * 3 / (5 + 4))
        self.assertAlmostEqual(fh, 2 * 1 / (3 + 4))
        self.assertAlmostEqual(d, fk - fh)
        self.assertAlmostEqual(d5, d)

    def test_interval_percentiles(self) -> None:
        vals = [float(i) for i in range(1000)]
        self.assertEqual(interval(vals, 0.95), (25.0, 974.0))
        self.assertEqual(interval(vals, 0.90), (50.0, 949.0))

    def test_bootstrap_is_seeded(self) -> None:
        ps = [pair(i, (i % 2, 2), (1, 2), 2) for i in range(6)]
        a = bootstrap(ps, 5, 200)
        self.assertEqual(a, bootstrap(ps, 5, 200))
        self.assertEqual(len(a[0]), 200)
        self.assertEqual(a[0], sorted(a[0]))


@skip_without("scipy")
class DecideTest(unittest.TestCase):
    def test_loki_ahead(self) -> None:
        ps = [pair(i, (0, 3), (2 + i % 2, 3), 4) for i in range(20)]
        dec = decide(ps)
        self.assertEqual(dec["outcome"], "Loki ahead")

    def test_hal_ahead(self) -> None:
        ps = [pair(i, (2 + i % 2, 3), (0, 3), 4) for i in range(20)]
        self.assertEqual(decide(ps)["outcome"], "HAL ahead")

    def test_equal_arms_are_inconclusive(self) -> None:
        ps = [pair(i, (1, 2), (1, 2), 2) for i in range(30)]
        self.assertEqual(decide(ps)["outcome"], "inconclusive")  # fewer than 8 non-zero pairs

    def test_comparable(self) -> None:
        ps = [pair(i, (1, 2), (1, 2), 2) for i in range(400)]
        for i in range(10):
            ps[i] = pair(i, (1, 2), (2 if i % 2 else 0, 2), 2)
        dec = decide(ps)
        self.assertEqual(dec["outcome"], "comparable")

    def test_round5_condition(self) -> None:
        ps = [Pair(f"c{i}", f"d{i}", (0, 3), (2 + i % 2, 3), (0, 6), 4, 4) for i in range(20)]
        dec = decide(ps)
        self.assertEqual(dec["outcome"], "inconclusive")
        self.assertIn("round-5", str(dec["note"]))


if __name__ == "__main__":
    unittest.main()
