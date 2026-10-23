"""``hard``: unmap facts to hard hypotheses (L1 spec 7.2, plan Task 17).

Hand-built ``UnmapRecord``s keep the detector tests independent of Odin III; the pass's real
attributes are covered by ``tests/test_re_unmap_facts.py``.
"""

import math
import unittest
from dataclasses import replace

from loki.re.bayes import DEFAULTS
from loki.re.detectors import RoundContext
from loki.re.detectors.hard import HardDetector, UnmapRecord, shared_ctrl
from loki.re.fngraph import FnGraph
from loki.re.overlay import Overlay
from tests.re_fixtures import GB, make_ctx


def ctx_of(records: tuple[UnmapRecord, ...], rnd: int = 1) -> RoundContext:
    graph: FnGraph = GB().build()
    return replace(make_ctx(graph, features=False), round=rnd, unmap=records)


def mem(cell: int, out: int, data: int) -> UnmapRecord:
    """A ``$mem`` recovered by ``ram``; the four records of one test share clk, addr and we."""
    return UnmapRecord(
        node_type="$mem", rule="ram", note="", cand="ram:0", cells=frozenset({cell}),
        ports={
            "RD_CLK": (1,), "RD_EN": (9,), "RD_ADDR": (3, 4), "RD_DATA": (out,),
            "WR_CLK": (1,), "WR_EN": (2,), "WR_ADDR": (3, 4), "WR_DATA": (data,),
        },
    )


def apply(det: HardDetector, records: tuple[UnmapRecord, ...], rnd: int = 1) -> Overlay:
    ov = Overlay()
    for cand in det.propose(ctx_of(records, rnd)):
        ov.add(cand, det.name, rnd)
    det.confirm(ov, rnd)
    ov.link_nesting()
    ov.rescore(DEFAULTS, rnd)
    return ov


class HardDetectorTest(unittest.TestCase):
    def test_recovered_cells_confirmed_inf(self) -> None:
        rec = UnmapRecord(
            node_type="$add", rule="chain", note="", cand="", cells=frozenset({3, 4}),
            ports={"A": (1,), "B": (2,), "Y": (5, 6)},
        )
        det = HardDetector()
        ov = apply(det, (rec,))
        got = ov.by_kind("hard_add")
        self.assertEqual(len(got), 1)
        h = got[0]
        self.assertEqual(h.status, "confirmed")
        self.assertEqual(h.log_odds, math.inf)
        self.assertIn(("hard", "unmap", "chain"),
                      [(e.source, e.name, e.value) for e in h.evidence])
        self.assertEqual(h.cells, frozenset({3, 4}))

    def test_sub_is_hard_add(self) -> None:
        rec = UnmapRecord(
            node_type="$sub", rule="chain", note="", cand="", cells=frozenset({5}),
            ports={"A": (1,), "B": (2,), "Y": (3, 4)},
        )
        ov = apply(HardDetector(), (rec,))
        self.assertEqual([h.kind for h in ov.all()], ["hard_add"])
        self.assertEqual(ov.all()[0].status, "confirmed")

    def test_ram_candidates_group(self) -> None:
        records = (mem(10, 20, 30), mem(11, 21, 31), mem(12, 22, 32), mem(13, 23, 33))
        ov = apply(HardDetector(), records)
        mems = ov.by_kind("hard_mem")
        groups = ov.by_kind("hard_group")
        self.assertEqual(len(mems), 4)
        self.assertEqual(len(groups), 1)
        group = groups[0]
        self.assertEqual(group.features["shared_ctrl"], "all")
        self.assertEqual(group.features["k"], "3-4")
        self.assertEqual(group.params, {"kind": "ram", "members": 4, "width": 4})
        self.assertEqual(group.cells, frozenset({10, 11, 12, 13}))
        self.assertEqual(sorted(group.children), sorted(h.id for h in mems))
        self.assertTrue(all(h.status == "confirmed" for h in mems))

    def test_declined_chain_open(self) -> None:
        rec = UnmapRecord(
            node_type="adder", rule="", note="adder:carry-in", cand="", cells=frozenset({7}),
            ports={"a": (1,), "b": (2,), "cin": (3,), "cout": (4,), "sumout": (5,)},
        )
        ov = apply(HardDetector(), (rec,))
        got = ov.by_kind("hard_add")
        self.assertEqual(len(got), 1)
        h = got[0]
        self.assertEqual(h.status, "open")
        self.assertEqual(h.features.get("declined_chain"), "yes")
        self.assertAlmostEqual(h.log_odds, 4.61)
        self.assertFalse([e for e in h.evidence if e.source == "hard"])

    def test_shared_ctrl_requires_control_nets(self) -> None:
        """Spec 7.2: an empty control set is ``none``, not vacuously ``all``."""
        bare = UnmapRecord(
            node_type="$add", rule="chain", note="", cand="", cells=frozenset({4}),
            ports={"A": (1,), "B": (2,), "Y": (3,)},
        )
        self.assertEqual(shared_ctrl([bare, replace(bare, cells=frozenset({5}))]), "none")
        addr: dict[str, tuple[int, ...]] = {"RD_ADDR": (3, 4)}
        self.assertEqual(
            shared_ctrl([replace(bare, ports=addr), replace(bare, ports=addr)]), "addr_only"
        )

    def test_group_without_control_nets_is_none(self) -> None:
        """A ``hard_group`` whose members carry no CLK/ADDR/WE nets gets no control credit."""
        rec = UnmapRecord(
            node_type="$add", rule="chain", note="", cand="add:0", cells=frozenset({4}),
            ports={"A": (1,), "B": (2,), "Y": (3,)},
        )
        other = replace(rec, cells=frozenset({5}), ports={"A": (6,), "B": (7,), "Y": (8,)})
        ov = apply(HardDetector(), (rec, other))
        groups = ov.by_kind("hard_group")
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].features["shared_ctrl"], "none")

    def test_later_rounds_propose_nothing(self) -> None:
        rec = UnmapRecord(
            node_type="$add", rule="chain", note="", cand="", cells=frozenset({3}),
            ports={"A": (1,), "B": (2,), "Y": (3,)},
        )
        self.assertEqual(list(HardDetector().propose(ctx_of((rec,), rnd=2))), [])


if __name__ == "__main__":
    unittest.main()
