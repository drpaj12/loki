import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from loki.cli import main as loki_main
from loki.rp.doc import render, span
from loki.schemas import validate_reverse_provenance
from tests.helpers import can_run_f2
from tests.rp_fixtures import ADD2, fsm_run, run_re

DATA = Path(__file__).parent / "data" / "rp"


def element(n: int, status: str, kind: str = "adder", p: float = 0.99) -> dict[str, Any]:
    cells = [f"g{n * 10 + i}" for i in range(4)]
    return {
        "id": f"h{n}", "kind": kind, "stage": "L1", "status": status, "fn": "Y = A + B",
        "width": 4, "params": {}, "p_comp": p, "prior_log_odds": 0.0, "log_odds": 1.0,
        "proof": {"label": "equivalent" if status == "committed" else "none",
                  "engine": "cone_check", "verdict": "equivalent", "from": ""},
        "evidence": [], "cells": cells, "nets": {},
        "ports": {"inputs": {"A": [f"a{n}0", f"a{n}1"]}, "outputs": {"Y": [f"y{n}0"]}},
        "recovered": {"module": f"{kind}_h{n}", "instance": f"{kind}_h{n}_i", "form": "submod"}
        if status == "committed" else None,
        "parents": [], "children": [], "conflicts": [], "role": "datapath" if n % 2 else "",
        "reason": "proof differs (cone_check), counterexample A=1,B=2"
        if status == "rejected" else "",
    }


def big() -> dict[str, Any]:
    els = [element(1, "committed")]
    els += [element(n, "candidate", p=0.9 - n / 1000) for n in range(2, 42)]
    els += [element(n, "rejected") for n in range(42, 82)]
    cov = {"cells_total": 400, "committed": {"cells": 4, "fraction": 0.01},
           "candidate": {"cells": 100, "fraction": 0.25},
           "uncovered": {"cells": 296, "fraction": 0.74},
           "uncovered_cells": [f"u{i}" for i in range(296)], "uncovered_nets": ["q1", "q2"]}
    return {
        "schema": 1,
        "header": {"loki": "0", "odin3": "0", "input": {"path": "x.blif", "sha256": "0" * 64},
                   "floor": "f2", "calib": {"path": None, "sha256": None}, "seed": 1,
                   "commit_threshold": 0.9, "candidate_threshold": 0.5},
        "netlist": {"cells": [], "inputs": [], "outputs": []},
        "elements": els, "buses": [], "fsms": [],
        "hierarchy": [{"id": "h1", "module": "adder_h1", "instance": "adder_h1_i",
                       "children": []}],
        "coverage": cov,
    }


def write(rp: dict[str, Any], tmp: str) -> Path:
    assert validate_reverse_provenance(rp) == []
    path = Path(tmp) / "reverse-provenance.json"
    path.write_text(json.dumps(rp), encoding="utf-8")
    return path


class SpanTest(unittest.TestCase):
    def test_runs(self) -> None:
        self.assertEqual(span(["g40", "g41", "g42", "g43"]), "g40..g43")
        self.assertEqual(span(["g2", "g1", "x"]), "g1, g2, x")
        self.assertEqual(span(["n9", "n3", "n10"], ordered=True), "n9, n3, n10")
        self.assertEqual(span(["n3", "n4", "n5", "n7"], ordered=True), "n3..n5, n7")


class DocTest(unittest.TestCase):
    def test_golden(self) -> None:
        text = render(DATA / "add2.reverse-provenance.json")
        self.assertEqual(text, (DATA / "add2.doc.md").read_text(encoding="utf-8"))

    def test_deterministic_and_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write(big(), tmp)
            a, b = render(path), render(path)
        self.assertEqual(a, b)
        for head in ("## 1.", "## 2.", "## 3.", "## 4.", "## 5.", "## 6.", "## 7.", "## 9."):
            self.assertIn(head, a)
        self.assertNotIn("## 8.", a)
        self.assertIn("h1: cells g10..g13 (4 cells) form a 4-bit adder", a)
        self.assertIn("h3 (unconfirmed)", a)
        self.assertIn("Loki tested a 4-bit adder (`Y = A + B`) on cells g420..g423 (4 cells) "
                      "and the proof showed it differs (cone_check), counterexample A=1,B=2.", a)

    def test_candidates_ordered_lowest_confidence_last(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            text = render(write(big(), tmp))
        self.assertLess(text.index("h2 (unconfirmed)"), text.index("h41 (unconfirmed)"))

    def test_no_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            text = render(write(big(), tmp), candidates=False)
        self.assertNotIn("(unconfirmed)", text)
        self.assertNotIn("## 6.", text)
        self.assertNotIn("Omitted", text)

    def test_truncation_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write(big(), tmp)
            full = render(path, max_chars=10**6)
            no_rej = render(path, max_chars=len(full) - 10)
            no_cand = render(path, max_chars=len(no_rej) - 10)
            no_lists = render(path, max_chars=len(no_cand) - 10)
            cut = render(path, max_chars=1000)
        self.assertIn("rejected claims (40).", no_rej)
        self.assertNotIn("## 7.", no_rej)
        self.assertIn("(unconfirmed)", no_rej)
        self.assertIn("rejected claims (40), candidates (40).", no_cand)
        self.assertNotIn("## 6.", no_cand)
        self.assertIn("cells g10..g13", no_cand)
        self.assertIn("per-cell lists.", no_lists)
        self.assertNotIn("g10..g13", no_lists)
        self.assertNotIn("u0..u295", no_lists)
        self.assertIn("h1: 4 cells form", no_lists)
        self.assertLessEqual(len(no_lists), len(no_cand) - 10)
        self.assertLessEqual(len(cut), 1000)
        self.assertIn("Cut at 1000 characters", cut)

    def test_invalid_file_is_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reverse-provenance.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                render(path)

    def test_l2_section(self) -> None:
        rp = copy.deepcopy(big())
        rp["l2"] = {
            "method": "kmeans",
            "partition": {"key": "kmeans:ab12cd34", "n_clusters": 1, "port_nodes": 0},
            "clusters": {"0": {"size": 4, "cells": ["g10", "g11", "g12", "g13"],
                               "overlap": [{"id": "h1", "module": "adder_h1",
                                            "cells_in_common": 4, "fraction_of_cluster": 1.0,
                                            "fraction_of_module": 1.0}],
                               "cells_outside_committed": 0}},
            "cells_unclustered": 0,
        }
        with tempfile.TemporaryDirectory() as tmp:
            text = render(write(rp, tmp))
        self.assertIn("## 8. Groupings from graph analysis (L2)", text)
        self.assertIn("cluster 0: cells g10..g13 (4 cells); overlaps h1 adder_h1: 4 cells", text)


@unittest.skipUnless(can_run_f2(), "needs Odin III, ABC and an F2 architecture")
class RealDocTest(unittest.TestCase):
    def test_real_runs_render_and_cli(self) -> None:
        for out in (run_re(ADD2), fsm_run()):
            text = render(out)
            self.assertIn("## 4. Committed claims", text)
            self.assertEqual(text, render(out))
        self.assertIn("finite state machine", render(fsm_run()))
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "rp.md"
            with contextlib.redirect_stdout(io.StringIO()):
                code = loki_main(["rp", "doc", str(run_re(ADD2)), "-o", str(target),
                                  "--max-chars", "6000", "--no-candidates"])
            self.assertEqual(code, 0)
            self.assertEqual(target.read_text(encoding="utf-8"),
                             render(run_re(ADD2), 6000, candidates=False))

    def test_cli_missing_dir(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(loki_main(["rp", "doc", "/nonexistent-lrp"]), 3)


if __name__ == "__main__":
    unittest.main()
