import unittest

from loki.score.match import jaccard, match_greedy, natural_key


def fs(*xs: str) -> frozenset[str]:
    return frozenset(xs)


class MatchTest(unittest.TestCase):
    def test_jaccard(self) -> None:
        self.assertEqual(jaccard(fs("a", "b"), fs("b", "c")), 1 / 3)
        self.assertEqual(jaccard(fs(), fs()), 0.0)

    def test_match_greedy_one_to_one(self) -> None:
        gts = [("g1", fs("a", "b", "c", "d"))]
        preds = [("h1", fs("a", "b", "c", "x")), ("h2", fs("a", "b", "c", "d"))]
        self.assertEqual(match_greedy(preds, gts, 0.5), [("h2", "g1", 1.0)])

    def test_ties_by_ids_natural_order(self) -> None:
        gts = [("g1", fs("a", "b"))]
        preds = [("h10", fs("a", "b")), ("h2", fs("a", "b"))]
        self.assertEqual(match_greedy(preds, gts, 0.5), [("h2", "g1", 1.0)])
        gts2 = [("g10", fs("a", "b")), ("g2", fs("a", "b"))]
        self.assertEqual(match_greedy([("h1", fs("a", "b"))], gts2, 0.5), [("h1", "g2", 1.0)])

    def test_threshold_and_disjoint(self) -> None:
        gts = [("g1", fs("a", "b", "c", "d"))]
        self.assertEqual(match_greedy([("h1", fs("a", "x", "y", "z"))], gts, 0.5), [])
        self.assertEqual(match_greedy([("h1", fs("p"))], gts, 0.5), [])

    def test_natural_key(self) -> None:
        self.assertLess(natural_key("h2"), natural_key("h10"))
