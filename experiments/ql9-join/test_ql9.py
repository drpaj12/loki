"""Tests of the Q-L9 links, cuts, rules, scoring and tuning helpers (no Odin III needed).

Run from this directory: ``python -m unittest test_ql9``.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

import numpy as np
import q9_cfg as cfgs
import q9_env as env
import q9_eval as qe
import q9_net as nt
import q9_rules as rules
import q9_score as sc
import q9_tune as tune
from q9_rules import Config
from q9_units import Blk

qn = env.mod("q6_net")


def chain_blif(n: int) -> str:
    """n gates in a chain g0 -> g1 -> ... (one net each)."""
    out = [".model t", ".inputs a b", ".outputs z"]
    prev = "a"
    for i in range(n):
        out += [f".names {prev} b w{i}", "11 1"]
        prev = f"w{i}"
    out += [f".names {prev} z", "1 1", ".end"]
    return "\n".join(out) + "\n"


def two_chains_blif(n: int) -> str:
    """Two chains of n gates joined by one link: a dumbbell with an obvious cut."""
    out = [".model t", ".inputs a b c d", ".outputs z"]
    for tag, src in (("p", "a"), ("q", "c")):
        prev = src
        for i in range(n):
            out += [f".names {prev} {'b' if tag == 'p' else 'd'} {tag}{i}", "11 1"]
            prev = f"{tag}{i}"
    out += [f".names p{n - 1} q0 q{n - 1} z", "111 1", ".end"]
    return "\n".join(out) + "\n"


def graph(text: str) -> Any:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "n.blif"
        p.write_text(text, encoding="utf-8")
        return qn.Graph.read(p)


class StubEvid:
    """Evidence = number of cells (a union always beats its parts by the BF of 0)."""

    def __init__(self, f: Any) -> None:
        self.f = f

    def ev(self, _src: str, cells: frozenset[int]) -> float:
        return float(self.f(cells))


class NetTests(unittest.TestCase):
    def test_links_chain(self) -> None:
        g = graph(chain_blif(5))
        lk = nt.Links(g)
        self.assertEqual(len(lk.pairs), 5)  # 4 inner links plus the last gate to the output gate
        owner = {i: 0 if i < 3 else 1 for i in range(g.b.n)}
        self.assertEqual(lk.between(owner), {(0, 1): 1})
        self.assertEqual(lk.block_deg(frozenset({0})), 1)

    def test_fiedler_cuts_the_bridge(self) -> None:
        g = graph(two_chains_blif(8))
        lk = nt.Links(g)
        cells = frozenset(range(g.b.n))
        cut = nt.fiedler_cut(lk, cells, 4)
        self.assertIsNotNone(cut)
        assert cut is not None
        x, y = cut
        self.assertEqual(x | y, cells)
        self.assertFalse(x & y)
        tags = [g.b.outs[i][0][0] for i in range(g.b.n)]
        side = [{tags[i] for i in part} - {"z"} for part in (x, y)]
        self.assertEqual(sorted(map(sorted, side)), [["p"], ["q"]])

    def test_disconnected_block_cut_at_components(self) -> None:
        g = graph(two_chains_blif(6))
        lk = nt.Links(g)
        keep = frozenset(i for i in range(g.b.n) if g.b.outs[i][0] != "z")
        cut = nt.fiedler_cut(lk, keep, 4)
        self.assertIsNotNone(cut)
        assert cut is not None
        self.assertEqual(sorted(len(s) for s in cut), [6, 6])

    def test_sweep_min_side(self) -> None:
        adj = {i: {j: 1 for j in (i - 1, i + 1) if 0 <= j < 6} for i in range(6)}
        self.assertIsNone(nt.sweep(list(range(6)), adj, 4))
        cut = nt.sweep(list(range(6)), adj, 3)
        assert cut is not None
        self.assertEqual((len(cut[0]), len(cut[1])), (3, 3))


class RuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.g = graph(chain_blif(6))
        self.lk = nt.Links(self.g)

    def blocks(self) -> list[Blk]:
        return [Blk(frozenset({0, 1}), "fsm"), Blk(frozenset({2, 3}), "fsm"),
                Blk(frozenset({6}), "const")]

    def test_join_cond_merges_adjacent_only(self) -> None:
        cfg = Config("c", "JOIN", "cond", "E73", 0.3)
        out, nj, ns = rules.apply(cfg, self.blocks(), self.lk, StubEvid(len))
        cells = sorted(sorted(b.cells) for b in out)
        self.assertEqual((nj, ns), (1, 0))
        self.assertIn([0, 1, 2, 3], cells)
        self.assertIn([6], cells)

    def test_join_threshold_and_cap(self) -> None:
        cfg = Config("c", "JOIN", "cond", "E73", 0.99)
        out, nj, _ = rules.apply(cfg, self.blocks(), self.lk, StubEvid(len))
        self.assertEqual((nj, len(out)), (0, 3))

    def test_join_bf_uses_evidence(self) -> None:
        union_better = StubEvid(lambda c: 10.0 if len(c) == 4 else 1.0)
        cfg = Config("b", "JOIN", "bf", "E73", 0.0)
        _, nj, _ = rules.apply(cfg, self.blocks(), self.lk, union_better)
        self.assertEqual(nj, 1)  # 10 - 1 - 1 >= 0
        worse = StubEvid(lambda c: 1.0)
        _, nj2, _ = rules.apply(cfg, self.blocks(), self.lk, worse)
        self.assertEqual(nj2, 0)  # 1 - 1 - 1 < 0

    def test_split_skips_const_and_small(self) -> None:
        cfg = Config("s", "SPLIT", ssrc="E73", st=-100.0)
        out, _, ns = rules.apply(cfg, self.blocks(), self.lk, StubEvid(len))
        self.assertEqual((ns, len(out)), (0, 3))  # every block is below 8 cells or const

    def test_split_makes_two_blocks(self) -> None:
        g = graph(two_chains_blif(8))
        lk = nt.Links(g)
        whole = [Blk(frozenset(range(g.b.n)), "fsm")]
        cfg = Config("s", "SPLIT", ssrc="E73", st=0.0)
        ev = StubEvid(lambda c: 100.0 if len(c) < g.b.n else 0.0)
        out, _, ns = rules.apply(cfg, whole, lk, ev)
        self.assertEqual((ns, len(out)), (1, 2))
        self.assertEqual(frozenset().union(*(b.cells for b in out)), whole[0].cells)

    def test_fix_stops_at_fixed_point(self) -> None:
        cfg = Config("f", "FIX", "cond", "E73", 0.3, "E73", None)
        out, nj, ns = rules.apply(cfg, self.blocks(), self.lk, StubEvid(len))
        self.assertEqual(ns, 0)
        self.assertLessEqual(nj, env.MAX_MERGES)
        self.assertEqual(sum(len(b.cells) for b in out), 5)


class ScoreTests(unittest.TestCase):
    def test_is_right(self) -> None:
        t = frozenset(range(10))
        self.assertTrue(sc.is_right(frozenset(range(10)), t))
        self.assertTrue(sc.is_right(frozenset(range(8)) | {20, 21}, t))  # cov 0.8, jac 8/12
        self.assertFalse(sc.is_right(frozenset(range(8)) | set(range(20, 30)), t))  # jac < 0.5
        self.assertFalse(sc.is_right(frozenset(range(5)), t))

    def test_failure_classes(self) -> None:
        t = frozenset(range(10))
        cases = {
            "NOSEED": [Blk(frozenset({50, 51}), "x")],
            "UNDERREACH": [Blk(frozenset(range(3)), "x"), Blk(frozenset(range(5, 7)), "x")],
            "SPLIT": [Blk(frozenset(range(5)), "x"), Blk(frozenset(range(5, 10)), "x")],
            "BLOATED": [Blk(frozenset(range(10)) | set(range(20, 40)), "x")],
        }
        for want, blocks in cases.items():
            self.assertEqual(sc.failure_class(blocks, t), want)

    def test_construct_rows_and_tally(self) -> None:
        cons = [(0, "fsm", frozenset(range(8)))]
        blocks = [Blk(frozenset(range(8)), "fsm")]
        rows = sc.construct_rows(("single", "d", "O-lut"), blocks, cons)
        self.assertEqual((rows[0]["right"], rows[0]["cls"]), (1, ""))
        post = np.zeros(len(env.KINDS))
        post[env.KINDS.index("fsm")] = 1.0
        tal = sc.kind_tally(blocks, cons, [post])
        self.assertEqual((tal["claims"]["fsm"], tal["tp"]["fsm"], tal["got"]), (1, 1, [(0, "fsm")]))
        glue = np.zeros(len(env.KINDS))
        glue[env.GLUE] = 1.0
        self.assertEqual(sum(sc.kind_tally(blocks, cons, [glue])["claims"].values()), 0)


class ConfigTests(unittest.TestCase):
    def test_grids(self) -> None:
        self.assertEqual(len(cfgs.join_grid()), 8 + 8 + 5 + 4)
        self.assertEqual(len(cfgs.split_grid()), 10)
        self.assertEqual(len({c.name for c in cfgs.join_grid()}), 25)

    def test_sources(self) -> None:
        c = Config("x", "JS", "bf", "EM2", 0.0, "E73", 1.0)
        self.assertEqual(c.sources, ("E73", "EM2"))
        self.assertEqual(Config("y", "JOIN", "cond").sources, ())

    def test_best_prefers_strict_on_ties(self) -> None:
        rows = [{"net": 3, "t": 1}, {"net": 3, "t": 4}, {"net": 2, "t": 9}]
        self.assertEqual(tune.best(rows, lambda r: r["t"])["t"], 4)

    def test_nets(self) -> None:
        def u(b: int, a: int) -> dict[str, Any]:
            return {"cfg": {"BASE": {"rows": [{"right": b}], "joins": 0, "splits": 0},
                            "x": {"rows": [{"right": a}], "joins": 1, "splits": 2}}}
        r = tune.nets([u(0, 1), u(1, 0), u(1, 1)])["x"]
        self.assertEqual((r["gained"], r["lost"], r["net"], r["joins"], r["splits"]),
                         (1, 1, 0, 3, 6))


def erow(base: int, head: int, cls: str, c74: str, kind: str = "fsm") -> dict[str, Any]:
    r: dict[str, Any] = {"set": "comp", "design": "d", "cell": "O-lut", "part": 0, "kind": kind,
                         "n_true": 5, "base": base, "base_cls": cls, "c74": c74, "d70": 0,
                         "e73": 0}
    for n in qe.NAMES:
        r[n.lower()] = head
        r[n.lower() + "_cls"] = "" if head else "BLOATED"
    return r


class EvalTests(unittest.TestCase):
    def test_fixed_rows_count_by_class(self) -> None:
        rows = [erow(0, 1, "SPLIT", "SPLIT"), erow(0, 0, "SPLIT", "SPLIT"),
                erow(1, 1, "", "BLOATED"), erow(0, 0, "UNDERREACH", "")]
        out = {(r["classes"], r["class"]): r for r in qe.fixed_rows(rows)}
        self.assertEqual(out[("#77 class", "SPLIT")]["head_right"], 1)
        self.assertEqual(out[("#77 class", "SPLIT")]["constructs"], 2)
        self.assertEqual(out[("#76 class (E74)", "BLOATED")]["base_right"], 1)
        self.assertNotIn(("#76 class (E74)", ""), out)

    def test_gained_lost(self) -> None:
        rows = [erow(0, 1, "SPLIT", "SPLIT"), erow(1, 0, "", "")]
        h = qe.gained_lost(rows)[0]
        self.assertEqual((h["gained"], h["lost"], h["net"], h["lost_by_class"]),
                         (1, 1, 0, "BLOATED:1"))

    def test_verdict_labels(self) -> None:
        rows = [erow(0, 1, "SPLIT", "SPLIT")] * 4 + [erow(0, 0, "SPLIT", "SPLIT")] * 4
        cmp_rows = [{"scope": s, "config": "HEAD", "against": "BASE", "geomean": 1.2,
                     "ci90_lo": 1.1, "ci90_hi": 1.3, "W": 4, "L": 0, "T": 4, "units": 8,
                     "label": "BETTER"} for s in ("all", "set single")]
        v = {r["id"]: r for r in qe.verdicts(rows, cmp_rows, qe.gained_lost(rows))}
        self.assertEqual(v["QL9-a"]["label"], "SUPPORTED")
        self.assertEqual(v["QL9-b split"]["label"], "SUPPORTED")  # 4 of 8 >= a quarter
        self.assertEqual(v["QL9-b swallowed"]["label"], "CONTRADICTED")  # none of the class


if __name__ == "__main__":
    unittest.main()
