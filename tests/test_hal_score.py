"""DANA groups.txt reader and the shared word scorer, on hand-written fixtures."""

import json
import tempfile
import unittest
from pathlib import Path

from loki.hal.dana import DanaError, hal_words, parse_groups_txt
from loki.hal.wordscore import GtWord, WordScore, dana_words, gt_words, loki_words, score_words
from loki.score.gt import derive_instances
from loki.score.metrics import Pred, construct_scores

DATA = Path(__file__).resolve().parent / "data" / "hal"


def floor_dir() -> Path:
    """FFs n1..n8; storage words A = n1..n4 ($dff, width 4), B = n5 n6 ($dffe, width 2),
    C = n7 (width 1); n8 is a flip-flop in no word; n20 is a LUT inside A's footprint."""
    d = Path(tempfile.mkdtemp(prefix="lhl-"))
    nodes = [{"id": f"n{i}", "kind": "ff"} for i in range(1, 9)] + [{"id": "n20", "kind": "lut"}]
    (d / "graph.json").write_text(json.dumps({"nodes": nodes, "edges": []}), encoding="utf-8")
    words = [
        {"id": 1, "type": "$dff", "params": {"WIDTH": 4},
         "footprint": ["n1", "n2", "n3", "n4", "n20"]},
        {"id": 2, "type": "$dffe", "params": {"WIDTH": 2}, "footprint": ["n5", "n6"]},
        {"id": 3, "type": "$dff", "params": {"WIDTH": 1}, "footprint": ["n7"]},
        {"id": 4, "type": "$add", "params": {"WIDTH": 4}, "footprint": ["n20"]},
    ]
    (d / "words.json").write_text(json.dumps({"words": words, "edges": []}), encoding="utf-8")
    return d


class DanaParseTest(unittest.TestCase):
    def test_fixture(self) -> None:
        groups = parse_groups_txt((DATA / "groups_fixture.txt").read_text(encoding="utf-8"))
        self.assertEqual([g.gid for g in groups], [1, 2, 3])
        g = groups[0]
        self.assertEqual(g.gates, ("n1", "n2", "n3", "n4"))
        self.assertEqual((g.clk, g.en, g.reset, g.set), ((7,), (12,), (), ()))
        self.assertEqual((g.successors, g.predecessors), ((2,), ()))
        self.assertEqual(groups[1].reset, (9,))
        self.assertEqual(groups[1].predecessors, (1,))
        self.assertEqual(groups[2].gate_types, ("FF",))

    def test_size_mismatch(self) -> None:
        bad = ("ID:1, Size:2, CLK: {}, EN: {}, R: {}, S: {}\n  Successors:   {}\n"
               "n1, type: FF, id: 1, RS: \n")
        with self.assertRaises(DanaError):
            parse_groups_txt(bad)

    def test_multi_net_lists_and_padding(self) -> None:
        text = ("State:\n\nID:4, Size:1, CLK: {1, 2}, EN: {}, R: {3, 4}, S: {}\n"
                "n9,       type: FF  , id: 12, RS: \n")
        g = parse_groups_txt(text)[0]
        self.assertEqual((g.clk, g.reset, g.gates), ((1, 2), (3, 4), ("n9",)))

    def test_hal_words_cut_to_ffs(self) -> None:
        groups = parse_groups_txt((DATA / "groups_fixture.txt").read_text(encoding="utf-8"))
        words = hal_words(groups, frozenset({"n1", "n2", "n3", "n4", "n5", "n6"}))
        self.assertEqual(words[1], frozenset({"n5", "n6"}))


class ScoreTest(unittest.TestCase):
    def test_gt_words(self) -> None:
        gt, ffs = gt_words(floor_dir())
        self.assertEqual(len(ffs), 8)
        self.assertEqual({w.wid: len(w.ffs) for w in gt}, {"w1": 4, "w2": 2, "w3": 1})

    def test_dana_fixture_scores(self) -> None:
        d = floor_dir()
        gt, ffs = gt_words(d)
        txt = DATA / "groups_fixture.txt"
        s = score_words(dana_words(txt, ffs), gt)
        self.assertEqual((s.n_pred, s.n_gt), (2, 2))
        self.assertEqual((s.exact_pred, s.exact_gt, s.matched), (1, 1, 2))
        self.assertEqual((s.pur_num, s.pur_den), (4 + 2, 4 + 3))
        self.assertEqual((s.comp_num, s.comp_den, s.cov_num, s.cov_den), (6, 6, 6, 6))
        r = s.ratios()
        self.assertEqual(r["precision_exact"], 0.5)
        self.assertEqual(r["recall_j"], 1.0)
        self.assertEqual(r["f1_j"], 1.0)
        self.assertAlmostEqual(r["purity"] or 0.0, 6 / 7, places=5)

    def test_split_word_and_noise(self) -> None:
        gt = [GtWord("w1", frozenset({"a", "b", "c", "d"}))]
        s = score_words([{"a", "b"}, {"c"}, {"x", "y"}], gt)
        self.assertEqual(s.n_pred, 2)  # the singleton is dropped
        self.assertEqual(s.matched, 1)  # J(ab, abcd) = 0.5 is a match
        self.assertEqual(s.pur_num, 2)
        self.assertEqual(s.pur_den, 4)
        self.assertEqual((s.comp_num, s.comp_den), (2, 4))
        self.assertEqual((s.cov_num, s.cov_den), (2, 4))

    def test_empty_prediction(self) -> None:
        gt = [GtWord("w1", frozenset({"a", "b"}))]
        s = score_words([], gt)
        self.assertEqual(s.ratios()["precision_j"], None)
        self.assertEqual(s.ratios()["recall_j"], 0.0)

    def test_sum_of_designs(self) -> None:
        a = WordScore(n_pred=2, n_gt=2, matched=1)
        b = WordScore(n_pred=1, n_gt=3, matched=1)
        self.assertEqual((a + b).matched, 2)
        self.assertEqual((a + b).ratios()["f1_j"], round(4 / 8, 6))

    def test_agrees_with_round5_register_scorer(self) -> None:
        """Same matched count as ``construct_scores`` for kind register when the answer-key
        footprints hold only flip-flops (the round-5 scorer matches whole footprints)."""
        d = floor_dir()
        words = json.loads((d / "words.json").read_text(encoding="utf-8"))
        words["words"][0]["footprint"] = ["n1", "n2", "n3", "n4"]
        gt, ffs = gt_words(d)
        pred = [frozenset({"n1", "n2", "n3", "n4"}), frozenset({"n5", "n6", "n7"}),
                frozenset({"n1", "n8"})]
        mine = score_words(pred, gt)
        preds = [Pred(f"h{i}", "register", p, 1.0, "committed") for i, p in enumerate(pred)]
        inst = [i for i in derive_instances(words) if i.type == "register"]
        ref = construct_scores(preds, inst, 0.5)["register"]
        self.assertEqual(mine.matched, ref["matched"])
        self.assertEqual(mine.n_gt, ref["gt"])
        self.assertEqual(len(ffs), 8)

    def test_loki_words_from_overlay(self) -> None:
        d = Path(tempfile.mkdtemp(prefix="lhl-"))
        hyps = [
            {"id": "h1", "kind": "register", "cells": ["n1", "n2", "n20"], "p_comp": 0.9,
             "status": "open", "detector": "wordfirst", "features": {}},
            {"id": "h2", "kind": "register", "cells": ["n5", "n6"], "p_comp": 0.2,
             "status": "open", "detector": "wordfirst", "features": {}},
            {"id": "h3", "kind": "adder", "cells": ["n3", "n4"], "p_comp": 1.0,
             "status": "committed", "detector": "arith", "features": {}},
        ]
        (d / "overlay.json").write_text(json.dumps({"hypotheses": hyps}), encoding="utf-8")
        _, ffs = gt_words(floor_dir())
        self.assertEqual(loki_words(d, ffs), [frozenset({"n1", "n2"})])


if __name__ == "__main__":
    unittest.main()
