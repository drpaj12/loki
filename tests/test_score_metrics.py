import tempfile
import unittest
from pathlib import Path

from loki.score.gt import GtBus, GtInstance
from loki.score.metrics import (
    AP_THRESHOLDS,
    Pred,
    PredBus,
    aggregate,
    ap_from_curve,
    bus_scores,
    compare,
    construct_scores,
    gate_breaker_class,
    hierarchy_scores,
    label_preds,
    reliability,
    role_scores,
    score_run,
    wyrd_metrics,
)
from tests.score_fixtures import write_floor_and_run


def fs(*xs: str) -> frozenset[str]:
    return frozenset(xs)


def pred(i: str, kind: str, cells: frozenset[str], p: float = 0.95, status: str = "open",
         op: str = "") -> Pred:
    return Pred(i, kind, cells, p, status, op=op)


GT = [GtInstance("w1", "$add", fs("a", "b", "c", "d")), GtInstance("w2", "$add", fs("e", "f")),
      GtInstance("w3", "$sub", fs("g", "h"))]


class ConstructTest(unittest.TestCase):
    def test_precision_recall_per_kind(self) -> None:
        preds = [pred("h1", "adder", fs("a", "b", "c", "d")), pred("h2", "adder", fs("x", "y")),
                 pred("h3", "adder", fs("e", "f"), p=0.3)]
        s = construct_scores(preds, GT, 0.5)["adder"]
        self.assertEqual((s["counted"], s["matched"], s["gt"]), (2, 1, 2))
        self.assertEqual((s["precision"], s["recall"]), (0.5, 0.5))
        self.assertEqual(s["f1"], 0.5)

    def test_committed_counts_below_score_p(self) -> None:
        preds = [pred("h1", "adder", fs("e", "f"), p=0.1, status="committed")]
        self.assertEqual(construct_scores(preds, GT, 0.5)["adder"]["matched"], 1)

    def test_rejected_never_counts(self) -> None:
        preds = [pred("h1", "adder", fs("e", "f"), p=0.99, status="rejected")]
        self.assertEqual(construct_scores(preds, GT, 0.5)["adder"]["counted"], 0)

    def test_kind_without_gt_is_na(self) -> None:
        s = construct_scores([pred("h1", "eq_const", fs("a", "b"))], GT, 0.5)["eq_const"]
        self.assertEqual((s["precision"], s["recall"], s["f1"], s["ap"]), ("n/a",) * 4)
        self.assertEqual(s["counted"], 1)

    def test_comparator_scored_by_its_own_op(self) -> None:
        gts = [GtInstance("w1", "$lt", fs("a", "b"))]
        ok = construct_scores([pred("h1", "comparator", fs("a", "b"), op="lt")], gts, 0.5)
        bad = construct_scores([pred("h1", "comparator", fs("a", "b"), op="eq")], gts, 0.5)
        self.assertEqual(ok["comparator"]["matched"], 1)
        self.assertEqual(bad["comparator"]["matched"], 0)

    def test_label_preds_not_one_to_one(self) -> None:
        preds = [pred("h1", "adder", fs("e", "f")), pred("h2", "adder", fs("e", "f")),
                 pred("h3", "adder", fs("q", "r"))]
        self.assertEqual(label_preds(preds, GT), {"h1": True, "h2": True, "h3": False})

    def test_ap_thresholds(self) -> None:
        self.assertEqual(AP_THRESHOLDS, (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9))
        # one true prediction at p = 0.65 against two ground truths, one false at p = 0.35
        preds = [pred("h1", "adder", fs("a", "b", "c", "d"), p=0.65),
                 pred("h2", "adder", fs("x", "y"), p=0.35)]
        s = construct_scores(preds, GT, 0.5)["adder"]
        # thresholds 0.1..0.3 count both (P 1/2, R 1/2), 0.4..0.6 count h1 (P 1, R 1/2)
        # from the top: R 0.5 at P 1.0 adds 0.5; lower thresholds add no recall
        self.assertEqual(s["ap"], 0.5)

    def test_ap_from_curve_na_without_gt(self) -> None:
        self.assertEqual(ap_from_curve([[0.5, 1.0, 1.0]], 0), "n/a")


class BusTest(unittest.TestCase):
    def gt(self) -> list[GtBus]:
        names = ["n1", "n2", "n3", "n4"]
        return [GtBus("b0", "x", frozenset(names), tuple((n, i) for i, n in enumerate(names)))]

    def test_bus_order_reversal(self) -> None:
        rev = PredBus("h1", 0.9, "open", "chain", ("n4", "n3", "n2", "n1"))
        s = bus_scores([rev], self.gt(), 0.5)
        self.assertEqual(s["order_exact"], {"chain": 0.0})
        self.assertEqual(s["order_up_to_reversal"], {"chain": 1.0})
        self.assertEqual((s["precision"], s["recall"]), (1.0, 1.0))

    def test_bus_exact_order_and_sources(self) -> None:
        a = PredBus("h1", 0.9, "open", "chain", ("n1", "n2", "n3", "n4"))
        s = bus_scores([a], self.gt(), 0.5)
        self.assertEqual(s["order_exact"], {"chain": 1.0})

    def test_bus_alt_view_used_for_port_buses(self) -> None:
        p = PredBus("h1", 0.9, "open", "net_id", ("l1", "l2", "l3", "l4"),
                    ("n1", "n2", "n3", "n4"))
        s = bus_scores([p], self.gt(), 0.5)
        self.assertEqual(s["matched"], 1)

    def test_bus_no_gt(self) -> None:
        s = bus_scores([PredBus("h1", 0.9, "open", "chain", ("n1", "n2"))], [], 0.5)
        self.assertEqual((s["precision"], s["recall"]), ("n/a", "n/a"))


class RoleTest(unittest.TestCase):
    def test_role_scores(self) -> None:
        gt = {"a": "control", "b": "control", "c": "datapath", "d": "datapath", "e": "io"}
        pr = {"a": "control", "b": "datapath", "c": "datapath", "d": "mixed", "e": "control"}
        s = role_scores(pr, gt, {"a", "b", "c", "d", "e"})
        control = s["control"]
        assert isinstance(control, dict)
        self.assertEqual((control["precision"], control["recall"]), (1.0, 0.5))
        self.assertEqual(s["mixed"], {"control": 0, "datapath": 1})


class HierarchyTest(unittest.TestCase):
    def test_hierarchy_identical_trees(self) -> None:
        paths = {"a": "top/u1", "b": "top/u1", "c": "top/u2", "d": "top/u2"}
        s = hierarchy_scores(paths, [fs("a", "b"), fs("c", "d")], [])
        self.assertEqual(s["hier_f"], 1.0)
        self.assertEqual(s["nmi_leaf"], 1.0)

    def test_hierarchy_flat_gt(self) -> None:
        s = hierarchy_scores({"a": "top", "b": "top"}, [fs("a", "b")], [fs("a", "b")])
        self.assertEqual(s["HS_gt"], "n/a")
        self.assertEqual(s["HS_l1"], 1.0)
        self.assertEqual(s["hier_f"], "n/a")

    def test_hierarchy_worked_example(self) -> None:
        paths = {"a": "top/u1", "b": "top/u1", "c": "top/u1", "d": "top/u2", "e": "top/u2",
                 "f": "top"}
        s = hierarchy_scores(paths, [fs("a", "b"), fs("d", "e", "f")], [])
        self.assertEqual(s["HS_gt"], 0.8)
        self.assertEqual(s["HS_l1"], 0.8)

    def test_no_pieces_over_hierarchy(self) -> None:
        s = hierarchy_scores({"a": "top/u1", "b": "top/u2"}, [], [])
        self.assertEqual((s["HS_gt"], s["HS_l1"], s["hier_f"]), (0.0, "n/a", 0.0))


class ReliabilityTest(unittest.TestCase):
    def test_reliability_bins_and_ece(self) -> None:
        r = reliability([(0.05, False), (0.15, True), (0.95, True)])
        bins = r["bins"]
        assert isinstance(bins, list)
        self.assertEqual(len(bins), 3)
        self.assertEqual(bins[0], {"lo": 0.0, "hi": 0.1, "mean_p": 0.05, "rate": 0.0, "n": 1})
        self.assertEqual(r["ece"], round((0.05 + 0.85 + 0.05) / 3, 6))

    def test_reliability_p_one_in_last_bin(self) -> None:
        r = reliability([(1.0, True)])
        bins = r["bins"]
        assert isinstance(bins, list)
        self.assertEqual(bins[0]["hi"], 1.0)
        self.assertEqual(r["ece"], 0.0)


def score_obj(design: str, floor: str, matched: int, counted: int, eng: int) -> dict[str, object]:
    curve = [[t, float(counted), float(matched)] for t in AP_THRESHOLDS]
    return {
        "design": design, "floor": floor,
        "constructs": {"adder": {"counted": counted, "matched": matched, "gt": 2,
                                 "curve": curve}},
        "bus": {"counted": 0, "matched": 0, "gt": 0, "order_n": {}, "order_exact_n": {},
                "order_reversal_n": {}},
        "roles": {r: {"tp": 0, "pred": 0, "gt": 0} for r in ("control", "datapath")},
        "hierarchy": {k: "n/a" for k in ("HS_gt", "HS_l1", "hier_f", "nmi_leaf")},
        "points": {"adder": [[0.9, 1.0], [0.8, 0.0]]},
        "engines": {"cone_check": eng, "transfer": 0, "truth_table": 1},
        "transfers": 1, "transfer_failures": 0,
    }


class AggregateTest(unittest.TestCase):
    def test_aggregate_markdown_table(self) -> None:
        scores = [score_obj("ve_Prob1_fsm", "f2", 1, 2, 3), score_obj("micro_a", "f1-k6", 2, 2, 1),
                  score_obj("micro_b", "f2", 1, 1, 1)]
        obj, md = aggregate(scores)
        floors = obj["floors"]
        assert isinstance(floors, dict)
        self.assertEqual(sorted(floors), ["f1-k6", "f2"])
        self.assertEqual(floors["f2"]["constructs"]["adder"]["precision"], round(2 / 3, 6))
        self.assertEqual(floors["f2"]["constructs"]["adder"]["recall"], 0.5)
        lines = [ln for ln in md.splitlines() if ln.startswith(("| f1-", "| f2"))]
        self.assertTrue(lines[0].startswith("| f1-k6 | adder"))
        self.assertEqual(obj["gate_breaker"], {"ve_Prob1_fsm": "fsm"})
        self.assertIn("| floor | kind |", md)

    def test_gate_breaker_class(self) -> None:
        self.assertEqual(gate_breaker_class("ve_Prob035_count1to10"), "count")
        self.assertEqual(gate_breaker_class("micro_count"), "")

    def test_ablation_table(self) -> None:
        w = [score_obj("d1", "f2", 2, 2, 5), score_obj("d2", "f2", 2, 2, 5)]
        wo = [score_obj("d1", "f2", 1, 2, 9), score_obj("d2", "f2", 1, 2, 9)]
        wo[0]["transfer_failures"] = 2
        obj, md = compare(w, wo)
        floors = obj["floors"]
        assert isinstance(floors, dict)
        adder = floors["f2"]["constructs"]["adder"]
        self.assertEqual(adder["recall"], {"with": 1.0, "without": 0.5, "delta": 0.5})
        self.assertEqual(floors["f2"]["with"]["engines"]["cone_check"], 10)
        self.assertEqual(floors["f2"]["without"]["engines"]["cone_check"], 18)
        self.assertEqual(floors["f2"]["without"]["transfer_failures"], 2)
        self.assertIn("transfer_failures", md)


class ScoreRunTest(unittest.TestCase):
    def test_score_run_end_to_end_on_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            floor, run, report = write_floor_and_run(Path(tmp))
            sc = score_run(run, floor, 0.5)
        cons = sc["constructs"]
        assert isinstance(cons, dict)
        self.assertEqual((cons["adder"]["precision"], cons["adder"]["recall"]), (1.0, 1.0))
        self.assertEqual(sc["design"], "d")
        self.assertEqual(sc["floor"], "f2")
        hier = sc["hierarchy"]
        assert isinstance(hier, dict)
        self.assertEqual(hier["hier_f"], 1.0)
        roles = sc["roles"]
        assert isinstance(roles, dict)
        self.assertEqual(roles["control"]["recall"], 1.0)
        m = wyrd_metrics(report, sc)
        self.assertEqual((m["rounds"], m["committed"], m["proved"]), (1, 1, 1))
        self.assertEqual((m["precision"], m["recall"], m["final_equiv_ok"]), (1.0, 1.0, 1))
