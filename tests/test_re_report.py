import json
import unittest
from pathlib import Path

from loki.re.claims import Claim
from loki.re.detectors import Candidate
from loki.re.loop import ReOptions, RunResult
from loki.re.overlay import Overlay
from loki.re.report import build_report, validate_report, write_markdown
from loki.schemas import dump_json
from tests.re_fixtures import GB, XOR2


def opts() -> ReOptions:
    return ReOptions(Path("/nonexistent/x.blif"), "f2", None, None, None, 1, 8, 30, 3600, None,
                     True, None)


def result() -> RunResult:
    g = GB()
    a, b = g.pi("a"), g.pi("b")
    y = g.lut(XOR2, [a, b])
    g.names[y] = "y"
    graph = g.build(pos=[y])
    cell = g.cell_of(y)
    ov = Overlay()
    claim = Claim("add", (("Y_WIDTH", 1),), (("A", (a,)), ("B", (b,))), (("Y", (y,)),))
    cand = Candidate("adder", frozenset({cell}), {"A": (a,), "B": (b,), "Y": (y,)},
                     {"width": 1}, {}, claim)
    h = ov.add(cand, "arith", 1)
    h.status = "committed"
    h.p_comp = 0.987654321
    h.proof = {"engine": "cone_check", "verdict": "equivalent", "template": "$add", "cex": "",
               "from": ""}
    h.commit = {"round": "1", "module": "adder_h1", "instance": "adder_h1_i", "form": "submod"}
    rounds: list[dict[str, object]] = [{
        "round": 1, "new": 1, "committed": ["h1"], "rejected": 0,
        "proved": {"equivalent": 1, "differs": 0, "unproven": 0, "invalid": 0, "error": 0},
        "engines": {"cone_check": 1, "transfer": 0, "truth_table": 0}, "transfer_failures": 0,
    }]
    feats: dict[str, object] = {"enabled": True, "wl": {}, "npn": {}, "transfers": 0,
                                "transfer_failures": 0}
    return RunResult(None, None, graph, ov, rounds, "fixed_point",
                     {"status": "equivalent", "tool_exit": 0}, {"total": 0.1}, {"unmap": "n/a"},
                     0, feats)


class ReportTest(unittest.TestCase):
    def test_report_keys_and_validates(self) -> None:
        rep = build_report(result(), opts())
        self.assertEqual(validate_report(rep), [])
        self.assertEqual(rep["counts"], {"cells": 1, "absorbed": 1, "committed": 1,
                                         "by_kind": {"adder": 1}})
        pieces = rep["pieces"]
        assert isinstance(pieces, list)
        self.assertEqual(pieces[0]["fn"], "Y = A + B")
        self.assertEqual(pieces[0]["p"], 0.987654)
        self.assertEqual(rep["fsm_detect"], "not-applicable")

    def test_validate_reports_problems(self) -> None:
        rep = build_report(result(), opts())
        del rep["rounds"]
        self.assertIn("report: missing key 'rounds'", validate_report(rep))
        self.assertEqual(validate_report([]), ["report: not an object"])

    def test_markdown_from_json_only(self) -> None:
        rep = build_report(result(), opts())
        text = write_markdown(json.loads(dump_json(rep)))
        self.assertEqual(text, write_markdown(rep))
        self.assertIn("| module | kind | confidence | proof | function |", text)
        self.assertIn("| adder_h1 | adder | 0.9877 | equivalent | Y = A + B |", text)

    def test_report_features_keys(self) -> None:
        feats = build_report(result(), opts())["features"]
        assert isinstance(feats, dict)
        for key in ("enabled", "wl", "npn", "transfers", "transfer_failures"):
            self.assertIn(key, feats)


if __name__ == "__main__":
    unittest.main()
