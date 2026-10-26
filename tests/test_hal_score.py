"""DANA groups.txt reader and the shared word scorer, on hand-written fixtures."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from loki.hal.dana import DanaError, hal_words, parse_groups_txt
from loki.hal.wordscore import (
    GtWord,
    WordScore,
    dana_words,
    gt_words,
    loki_words,
    round5_register,
    score_words,
)
from loki.score.gt import derive_instances
from loki.score.metrics import Pred, construct_scores

DATA = Path(__file__).resolve().parent / "data" / "hal"
WORK = Path(__file__).resolve().parents[2]
R5 = Path(os.environ.get("LOKI_R5_DATA", str(WORK / "loki-exp5-data")))
MICRO = Path(os.environ.get("LOKI_MICRO", str(WORK / "loki-rename-exp" / "dataset-rebuild")))
VEVAL = Path(os.environ.get("LOKI_VEVAL", str(WORK / "loki-veval-exp" / "dataset")))
REAL = (("W-MI-f2", MICRO, "f2"), ("W-MI-f3", MICRO, "f3"),
        ("W-VT-f2", VEVAL, "f2"), ("W-VT-f3", VEVAL, "f3"))


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

    def test_dedup_switch(self) -> None:
        gt = [GtWord("w1", frozenset({"a", "b"}))]
        pred = [{"a", "b"}, {"a", "b"}]
        self.assertEqual(score_words(pred, gt).n_pred, 1)
        s = score_words(pred, gt, dedup=False)
        self.assertEqual((s.n_pred, s.matched, s.exact_pred), (2, 1, 2))

    def test_width_one_word_is_label_only(self) -> None:
        d = floor_dir()
        words = json.loads((d / "words.json").read_text(encoding="utf-8"))
        words["words"][2]["footprint"] = ["n7", "n8"]  # width 1 but two FFs
        (d / "words.json").write_text(json.dumps(words), encoding="utf-8")
        gt, _ = gt_words(d)
        self.assertEqual({w.wid for w in gt if w.scored}, {"w1", "w2"})
        self.assertEqual(score_words([{"n7", "n8"}], gt).n_gt, 2)
        self.assertEqual(score_words([{"n7", "n8"}], gt).matched, 0)
        r5, _ = gt_words(d, round5=True)
        self.assertEqual({w.wid for w in r5}, {"r1", "r2"})

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


def real_deltas(arm: str, dataset: Path, floor: str) -> dict[str, int]:
    """Sum over the designs of one round-5 W run: the round-5 counts, the comparison scorer's
    counts, and the effect of each deviation alone. Asserts that the scorer in round-5 mode
    (``round5=True``, no dedup, no FF cut) reproduces ``construct_scores`` per design."""
    tot: dict[str, int] = {}

    def add(**kw: int) -> None:
        for k, v in kw.items():
            tot[k] = tot.get(k, 0) + v

    for run in sorted((R5 / "runs" / arm).iterdir()):
        re_dir, fd = run / "re", dataset / run.name.rsplit("__", 1)[0] / floor
        if not (re_dir / "overlay.json").is_file():
            continue
        ref = round5_register(re_dir, fd)
        g5, ffs = gt_words(fd, round5=True)
        mine5 = score_words(loki_words(re_dir, ffs, cut=False), g5, dedup=False)
        assert (mine5.matched, mine5.n_pred, mine5.n_gt) == (
            ref["matched"], ref["counted"], ref["gt"]), run.name
        gt, _ = gt_words(fd)
        cmp_ = score_words(loki_words(re_dir, ffs), gt)
        dedup_only = score_words(loki_words(re_dir, ffs, cut=False), g5)
        cut_only = score_words(loki_words(re_dir, ffs), g5, dedup=False)
        add(designs=1, r5_pred=ref["counted"], r5_matched=ref["matched"], r5_gt=ref["gt"],
            cmp_pred=cmp_.n_pred, cmp_matched=cmp_.matched, cmp_gt=cmp_.n_gt,
            dedup_pred=dedup_only.n_pred, dedup_matched=dedup_only.matched,
            cut_pred=cut_only.n_pred, cut_matched=cut_only.matched)
    return tot


class RealDataTest(unittest.TestCase):
    """The comparison scorer against the round-5 scorer on the round-5 W runs (skips if absent)."""

    def test_round5_mode_and_deltas(self) -> None:
        ran = 0
        for arm, dataset, floor in REAL:
            if not (R5 / "runs" / arm).is_dir() or not dataset.is_dir():
                continue
            tot = real_deltas(arm, dataset, floor)
            ran += 1
            sys.stderr.write(f"\n[deltas] {arm}: {json.dumps(tot, sort_keys=True)}\n")
            self.assertGreater(tot["designs"], 10, arm)
            self.assertLessEqual(tot["dedup_pred"], tot["r5_pred"], arm)
        if ran == 0:
            self.skipTest("round-5 W runs or datasets not present")


if __name__ == "__main__":
    unittest.main()
