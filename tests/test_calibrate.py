import json
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from loki.re.bayes import NODE_MIN_COUNT, load_calib, logit
from loki.re.detectors import Candidate
from loki.re.loop import ReOptions
from loki.re.overlay import Overlay
from loki.schemas import dump_json
from loki.score.calibrate import (
    Counts,
    DesignData,
    NodeCounts,
    calibrate,
    fit,
    fit_weights,
    fold_of,
    node_calib,
    node_table,
    to_calib,
    write_calib,
)
from loki.score.gt import GtInstance
from loki.score.metrics import Pred
from tests.helpers import write_fake_floor
from tests.re_fixtures import AND2, GB, XOR2

ADD = GtInstance("w1", "$add", frozenset({"c1", "c2"}))


class TableTest(unittest.TestCase):
    def test_prior_laplace(self) -> None:
        c = Counts(priors={"arith/adder": [8, 2]}, totals={"adder": [2, 6]})
        p = to_calib(c)["priors"]
        assert isinstance(p, dict)
        self.assertAlmostEqual(p["arith/adder"]["log_odds"], logit(0.3), places=6)
        self.assertEqual((p["arith/adder"]["n"], p["arith/adder"]["tp"]), (8, 2))

    def test_llr_laplace(self) -> None:
        c = Counts(bins={"adder/width": {"a": [3, 1], "b": [7, 19]}}, totals={"adder": [10, 20]})
        t = to_calib(c)["llr"]
        assert isinstance(t, dict)
        self.assertAlmostEqual(t["adder/width"]["a"]["llr"], math.log((4 / 12) / (2 / 22)), 5)
        self.assertEqual((t["adder/width"]["a"]["pos"], t["adder/width"]["a"]["neg"]), (3, 1))

    def test_unseen_bin_absent(self) -> None:
        c = Counts(bins={"adder/width": {"a": [3, 1]}}, totals={"adder": [10, 20]})
        obj = {"schema": 1, "floor": "f2", **to_calib(c)}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.json"
            path.write_text(json.dumps(obj), encoding="utf-8")
            calib = load_calib(path)
        self.assertNotEqual(calib.feature_llr("adder", "width", "a"), 0.0)
        self.assertEqual(calib.feature_llr("adder", "width", "zzz"), 0.0)

    def test_node_llr_laplace_and_min_count(self) -> None:
        self.assertEqual(NODE_MIN_COUNT, 5)
        counts = NodeCounts(
            keys={"adder": {"2:a": [6, 2], "2:b": [3, 1]}}, totals={"adder": [9, 3]})
        t = node_table(counts)
        self.assertNotIn("2:b", t["adder"])
        self.assertAlmostEqual(t["adder"]["2:a"], math.log((7 / 11) / (3 / 5)))

    def test_node_backoff_keys(self) -> None:
        counts = NodeCounts(
            keys={"adder": {"2:x": [2, 1], "1:y": [8, 1], "0:z": [5, 5]}},
            totals={"adder": [20, 20]})
        calib = node_calib(node_table(counts))
        self.assertEqual(calib.node_score("adder", ("2:x", "1:y", "0:z")),
                         node_table(counts)["adder"]["1:y"])
        self.assertIsNone(calib.node_score("adder", ("2:q",)))

    def test_fold_of_deterministic(self) -> None:
        self.assertEqual(fold_of("micro_a"), fold_of("micro_a"))
        self.assertEqual({fold_of(f"d{i}") for i in range(40)}, {0, 1})


def pred(i: str, cells: set[str], det: str = "arith", feats: dict[str, str] | None = None,
         ) -> Pred:
    return Pred(i, "adder", frozenset(cells), 0.5, "open", det, "", feats or {})


def design(name: str, hits: int, misses: int, feats: tuple[dict[str, str], dict[str, str]]
           = ({"width": "2"}, {"width": "2"})) -> DesignData:
    preds = [pred(f"h{i}", {"c1", "c2"}, feats=feats[0]) for i in range(hits)]
    preds += [pred(f"h{hits + i}", {f"x{i}"}, feats=feats[1]) for i in range(misses)]
    return DesignData(name, preds, [ADD], NodeCounts(), {}, {})


def names_by_fold() -> tuple[str, str]:
    found: dict[int, str] = {}
    for i in range(100):
        found.setdefault(fold_of(f"d{i}"), f"d{i}")
    return found[0], found[1]


class FitTest(unittest.TestCase):
    def test_calib_file_deterministic(self) -> None:
        a, b = names_by_fold()
        ds = [design(a, 3, 5), design(b, 2, 4)]
        x = dump_json(fit(ds, "f2", "sha", "train"))
        y = dump_json(fit(list(reversed(ds)), "f2", "sha", "train"))
        self.assertEqual(x, y)

    def test_roundtrip_load_calib(self) -> None:
        a, b = names_by_fold()
        counts = NodeCounts({"adder": {"0:k": [10, 0], "0:j": [0, 10]}}, {"adder": [10, 10]})
        ds = [design(a, 3, 5), design(b, 2, 4)]
        for d in ds:
            d.nodes = counts
        obj = fit(ds, "f2", "sha", "train")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "f2.json"
            write_calib(obj, path)
            calib = load_calib(path)
        self.assertEqual(calib.floor, "f2")
        self.assertAlmostEqual(calib.prior("arith", "adder"), logit(6 / 16), places=5)
        self.assertIn("adder", calib.node_llr)
        self.assertEqual(calib.weights, obj["weights"])
        llr = obj["llr"]
        assert isinstance(llr, dict)
        self.assertEqual(calib.feature_llr("adder", "width", "2"), llr["adder/width"]["2"]["llr"])

    def test_defaults_kept_for_uncalibrated_kinds(self) -> None:
        a, _ = names_by_fold()
        obj = fit([design(a, 1, 1)], "f2", "sha", "train")
        llr = obj["llr"]
        assert isinstance(llr, dict)
        self.assertIn("bus/k", llr)
        self.assertEqual(llr["bus/k"]["2"]["llr"], 0.0)

    def test_cross_fit_no_leak(self) -> None:
        a, b = names_by_fold()
        key_k = ("0:k",)
        da, db = design(a, 1, 0), design(b, 1, 0)
        # design a: k is positive, j negative; design b the other way round
        da.nodes = NodeCounts({"adder": {"0:k": [10, 0], "0:j": [0, 10]}}, {"adder": [10, 10]})
        db.nodes = NodeCounts({"adder": {"0:k": [0, 10], "0:j": [10, 0]}}, {"adder": [10, 10]})
        da.keys, db.keys = {"c1": key_k, "c2": key_k}, {"c1": key_k, "c2": key_k}
        obj = fit([da, db], "f2", "sha", "train")
        llr = obj["llr"]
        assert isinstance(llr, dict)
        bins = llr["adder/wl_npn"]
        # a's hypothesis is binned by b's table (k is negative there), never by its own counts
        self.assertEqual(sorted(bins), ["++", "--"])
        self.assertEqual(bins["--"]["pos"], 1)
        self.assertEqual(bins["++"]["pos"], 1)

    def test_reliability_in_calib_file(self) -> None:
        a, b = names_by_fold()
        obj = fit([design(a, 3, 5), design(b, 2, 4)], "f2", "sha", "train")
        rel = obj["reliability"]
        assert isinstance(rel, dict)
        self.assertTrue(rel["bins"])
        self.assertIsInstance(rel["ece"], float)


class WeightTest(unittest.TestCase):
    def test_fit_weights_grid(self) -> None:
        up, down = math.log(3), -math.log(3)
        rows = [(0.0, {"struct": up, "wl": up}, 0.0, k < 3) for k in range(4)]
        rows += [(0.0, {"struct": down, "wl": down}, 0.0, k == 0) for k in range(4)]
        w = fit_weights(rows)
        self.assertLessEqual(w["struct"] + w["wl"], 1.3)

    def test_independent_families_keep_weight_one(self) -> None:
        up, down = math.log(3), -math.log(3)
        rows = [(0.0, {"struct": up, "wl": up}, 0.0, k < 9) for k in range(10)]
        for x1, x2 in ((up, down), (down, up)):
            rows += [(0.0, {"struct": x1, "wl": x2}, 0.0, k < 5) for k in range(10)]
        rows += [(0.0, {"struct": down, "wl": down}, 0.0, k < 1) for k in range(10)]
        self.assertEqual(fit_weights(rows), {"struct": 1.0, "wl": 1.0})

    def test_ties_go_to_the_larger_weight(self) -> None:
        rows = [(0.0, {"npn": 0.0}, 0.0, True), (0.0, {"npn": 0.0}, 0.0, False)]
        self.assertEqual(fit_weights(rows), {"npn": 1.0})


def fake_run(opts: ReOptions) -> SimpleNamespace:
    g = GB()
    a, b = g.pi("a"), g.pi("b")
    o1 = g.lut(XOR2, [a, b])
    o2 = g.lut(AND2, [a, b])
    graph = g.build(pos=[o1, o2])
    ov = Overlay()
    ov.add(Candidate("adder", frozenset({1001, 1002}), {}, {}, {"width": "2"}), "arith", 1)
    return SimpleNamespace(overlay=ov, graph=graph)


class RunTest(unittest.TestCase):
    def dataset(self, root: Path) -> None:
        for name in ("d1", "d2", "d3"):
            floor = write_fake_floor(root, name, "f2")
            words = {"words": [{"id": 1, "type": "$add", "params": {}, "fsm": False,
                                "role": "datapath", "const_ports": [],
                                "footprint": ["c1001", "c1002"]}], "edges": []}
            (floor / "words.json").write_text(json.dumps(words), encoding="utf-8")
        entries = [
            {"design": "d1", "benchmark": "micro", "split": "train",
             "floors": {"f2": {"status": "ok"}}},
            {"design": "d2", "benchmark": "micro", "split": "test",
             "floors": {"f2": {"status": "ok"}}},
            {"design": "d3", "benchmark": "micro", "split": "train",
             "floors": {"f2": {"status": "skipped"}}},
        ]
        (root / "manifest.json").write_text(json.dumps({"designs": entries}), encoding="utf-8")

    def test_only_train_designs(self) -> None:
        seen: list[str] = []

        def run(opts: ReOptions) -> SimpleNamespace:
            seen.append(opts.netlist.parent.parent.name)
            return fake_run(opts)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.dataset(root)
            with mock.patch("loki.score.calibrate.run_re", side_effect=run):
                obj = calibrate(root, "f2", "train", None, 1)
        self.assertEqual(seen, ["d1"])
        self.assertEqual(obj["designs"], ["d1"])
        priors = obj["priors"]
        assert isinstance(priors, dict)
        self.assertEqual((priors["arith/adder"]["n"], priors["arith/adder"]["tp"]), (1, 1))
