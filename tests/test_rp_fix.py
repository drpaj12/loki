"""Fix-round tests of ReverseProvenance (review 2026-10-24); each fails on the code before it."""

import contextlib
import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest import mock

from loki.analysis.partition import load_partition
from loki.cli import main as loki_main
from loki.re.overlay import Evidence, Hypothesis
from loki.rp import build
from loki.rp.doc import _article, min_chars, render
from loki.rp.l2 import JoinError, add_l2, build_l2
from loki.schemas import dump_json, validate_reverse_provenance
from tests.helpers import can_run_f2
from tests.rp_fixtures import ADD2, CALIB, FSM2, golden, normalised, run_re
from tests.test_rp_doc import big, write
from tests.test_rp_l2 import partition
from tests.test_rp_l2 import write as write_obj

FILE = "reverse-provenance.json"
DIGEST = {
    "design.v": "a5786b9f739939a7a796823dc06a59d55f7cb02faf0256aa733595e62495cb3b",
    "overlay.json": "801861472087421b1f322c4a64c32a0a5036b24fc3e748381631050dad9d8a65",
    "report.json": "4944547d163d8b12253020579f16ff7bd8d4a3e02108e04e70e4b7900172fcc3",
    "report.md": "7c20c9bebf6e5f0db6c9ba24756752994a459d452f7bd2e1585e3aa8d8a3e740",
}


def hyp(hid: str, kind: str = "bus", **kw: Any) -> Hypothesis:
    fields: dict[str, Any] = {
        "id": hid, "kind": kind, "detector": "t", "round": 0, "cells": frozenset(),
        "nets": {}, "params": {}, "claim": None}
    fields.update(kw)
    return Hypothesis(**fields)


class Graph:
    def __init__(self, cells: dict[int, str]) -> None:
        self.cells = {c: SimpleNamespace(name=n, outs=(c + 100,)) for c, n in cells.items()}
        self.names: dict[int, str] = {}

    def label(self, cell_id: int) -> str:
        return self.cells[cell_id].name or f"c{cell_id}"


def res_of(cells: dict[int, str]) -> Any:
    return cast(Any, SimpleNamespace(graph=Graph(cells)))


class BuildUnitTest(unittest.TestCase):
    def test_bus_and_fsm_rows_carry_status(self) -> None:  # H1
        res = res_of({})
        bus = hyp("h2", nets={"slice0": (1,), "slice1": (2,)})
        fsm = hyp("h3", "fsm", params={"rows": "[[0, 1, 2]]", "states": 2, "start": 0})
        self.assertEqual(build._bus(res, bus, "candidate")["status"], "candidate")
        self.assertEqual(build._fsm(res, fsm, "committed")["status"], "committed")

    def test_unnamed_net_is_not_a_bare_number(self) -> None:  # M7
        self.assertEqual(build._names(res_of({}), [7]), ["net7"])

    def test_same_name_cells_are_counted_by_id(self) -> None:  # L3
        res = res_of({1: "x", 2: "x", 3: "y"})
        cov: Any = build._coverage(res, [hyp("h1", cells=frozenset({1}))], {"h1": "committed"})
        self.assertEqual(cov["uncovered"]["cells"], 2)
        self.assertEqual(cov["uncovered_cells"], ["x", "y"])
        both: Any = build._coverage(res, [], {})
        self.assertEqual(both["uncovered_cells"], ["x", "x", "y"])

    def test_no_reason_is_empty_not_the_word_rejected(self) -> None:  # L4
        h = hyp("h1", "adder", status="rejected", proof={"verdict": "equivalent", "engine": "e"})
        self.assertEqual(build._rejection(h), "")
        h2 = hyp("h2", "adder", status="rejected", proof={"verdict": "differs", "engine": "e"})
        self.assertTrue(build._rejection(h2).startswith("proof differs"))
        ev = Evidence(source="commit", name="error", value="boom", llr=0.0, round=0)
        h3 = hyp("h3", "adder", status="rejected", evidence=[ev])
        self.assertEqual(build._rejection(h3), "commit failed: boom")

    def test_links_to_non_elements_are_counted(self) -> None:  # L5
        els: list[dict[str, object]] = [
            {"id": "h1", "parents": [], "children": ["h2", "h9"], "conflicts": ["h2", "h8", "h9"]},
            {"id": "h2", "parents": ["h1"], "children": [], "conflicts": []}]
        build._keep_known(els)
        self.assertEqual(els[0]["conflicts"], ["h2"])
        self.assertEqual(els[0]["links_outside"], {"parents": 0, "children": 1, "conflicts": 2})

    def test_attrs_claims_are_counted_in_coverage(self) -> None:  # M6
        res = res_of({1: "a", 2: "b", 3: "c"})
        mod = hyp("h1", "adder", cells=frozenset({1}), commit={"form": "submod"})
        att = hyp("h2", "ff_en", cells=frozenset({2, 3}), commit={"form": "attrs"})
        status = {"h1": "committed", "h2": "committed"}
        cov: Any = build._coverage(res, [mod, att], status)
        self.assertEqual(cov["attrs"], {"elements": 1, "cells": 2})
        self.assertEqual(cov["committed"]["cells"], 3)


class ValidatorTest(unittest.TestCase):
    def mutants(self) -> list[tuple[str, dict[str, Any]]]:
        base = golden()
        base["l2"] = {"method": "kmeans", "partition": {"key": "k", "n_clusters": 1},
                      "clusters": {}, "cells_unclustered": 0}
        out: list[tuple[str, dict[str, Any]]] = []

        def add(name: str, edit: Any) -> None:
            obj = copy.deepcopy(base)
            edit(obj)
            out.append((name, obj))

        add("l2 partition", lambda o: o["l2"].update(partition={"x": 1}))
        add("l2 cluster", lambda o: o["l2"].update(clusters={"0": {"size": 1}}))
        add("l2 cluster key", lambda o: o["l2"].update(clusters={"x": {
            "size": 0, "cells": [], "overlap": [], "cells_outside_committed": 0}}))
        add("bus row", lambda o: o.update(buses=[{"id": "h1"}]))
        add("fsm row", lambda o: o.update(fsms=[{"id": "h1", "status": "candidate"}]))
        add("coverage sub", lambda o: o["coverage"].update(committed={"cells": 1}))
        add("coverage attrs", lambda o: o["coverage"].pop("attrs"))
        add("header input", lambda o: o["header"].update(input="x"))
        add("header input name", lambda o: o["header"]["input"].pop("name"))
        add("element width", lambda o: o["elements"][0].update(width="2"))
        add("element ports", lambda o: o["elements"][0].update(ports={"inputs": {"A": 3}}))
        add("element cells", lambda o: o["elements"][0].update(cells=[1, 2]))
        add("element p_comp", lambda o: o["elements"][0].update(p_comp="high"))
        add("element evidence", lambda o: o["elements"][0].update(evidence=[{"name": "x"}]))
        add("element recovered", lambda o: o["elements"][0].update(recovered={"module": 1}))
        add("element links", lambda o: o["elements"][0].pop("links_outside"))
        add("netlist", lambda o: o["netlist"].update(cells="n10"))
        add("hierarchy", lambda o: o.update(hierarchy=[{"id": "h1", "children": []}]))
        return out

    def test_golden_is_valid(self) -> None:
        self.assertEqual(validate_reverse_provenance(golden()), [])

    def test_every_mutant_is_rejected_and_render_raises_value_error(self) -> None:  # H2
        for name, obj in self.mutants():
            with self.subTest(name):
                self.assertTrue(validate_reverse_provenance(obj))
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / FILE
                    path.write_text(json.dumps(obj), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        render(path)

    def test_bool_is_not_an_int(self) -> None:
        obj = golden()
        obj["elements"][0]["width"] = True
        self.assertTrue(validate_reverse_provenance(obj))

    def test_inf_log_odds_are_valid(self) -> None:
        obj = golden()
        obj["elements"][0]["log_odds"] = "inf"
        self.assertEqual(validate_reverse_provenance(obj), [])

    def test_cli_turns_key_and_type_errors_into_exit_2(self) -> None:  # H2
        for exc in (KeyError("key"), TypeError("bad")):
            with tempfile.TemporaryDirectory() as tmp:
                write(big(), tmp)
                err = io.StringIO()
                patched = mock.patch("loki.rp.doc.render", side_effect=exc)
                with patched, contextlib.redirect_stderr(err):
                    code = loki_main(["rp", "doc", tmp])
            self.assertEqual(code, 2)
            self.assertIn("loki rp:", err.getvalue())


def with_rows() -> dict[str, Any]:
    rp = big()
    rp["buses"] = [
        {"id": "h1", "status": "committed", "width": 2, "order_source": "carry",
         "bits": [["a"], ["b"]]},
        {"id": "h2", "status": "candidate", "width": 2, "order_source": "net_id",
         "bits": [["c"], ["d"]]}]
    rp["fsms"] = [
        {"id": "h3", "status": "candidate", "state_nets": ["q0"], "control_nets": [],
         "reset_net": [], "states": 3, "reset_state": 0, "encoding": "unknown",
         "transitions": [], "transitions_total": 0}]
    return rp


class DocFixTest(unittest.TestCase):
    def render(self, rp: dict[str, Any], **kw: Any) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            return render(write(rp, tmp), **kw)

    def test_candidate_bus_and_fsm_are_marked(self) -> None:  # H1
        text = self.render(with_rows())
        self.assertIn("- h2 (unconfirmed): 2 bits", text)
        self.assertIn("- h3 (unconfirmed): state registers", text)
        self.assertIn("- h1: 2 bits", text)

    def test_candidate_bus_and_fsm_drop_without_candidates(self) -> None:  # H1
        text = self.render(with_rows(), candidates=False)
        self.assertNotIn("h2", text.split("## 6")[0].split("## 5")[1])
        self.assertIn("- h1: 2 bits", text)
        self.assertIn("State machines: none committed.", text)
        self.assertNotIn("state registers", text)

    def test_candidate_bus_and_fsm_drop_when_truncation_drops_candidates(self) -> None:  # H1
        rp = with_rows()
        full = self.render(rp, max_chars=10**6)
        text = self.render(rp, max_chars=len(full) - 10)
        while "## 6." in text:
            text = self.render(rp, max_chars=len(text) - 10)
        self.assertNotIn("(unconfirmed)", text)
        self.assertIn("candidate buses and state machines (2)", text)

    def test_no_bit_order_claim(self) -> None:  # M3
        self.assertNotIn("least-significant", self.render(big()))

    def test_derived_proof_text(self) -> None:  # M4
        rp = big()
        rp["elements"][0]["proof"] = {"label": "derived", "engine": "transfer",
                                      "verdict": "equivalent", "from": "h7"}
        text = self.render(rp)
        self.assertIn("Proof derived from h7 (proof transfer).", text)
        self.assertNotIn("matching cone", text)

    def test_section_9_survives_any_limit(self) -> None:  # M5
        with tempfile.TemporaryDirectory() as tmp:
            path = write(big(), tmp)
            floor = min_chars(json.loads(path.read_text(encoding="utf-8")))
            for limit in (1, 500, floor, floor + 300, 3000, 6000):
                with self.subTest(limit=limit):
                    text = render(path, max_chars=limit)
                    self.assertIn("## 9. What Loki does NOT claim", text)
                    self.assertIn("they are not the original HDL names", text)
                    self.assertIn("## 2. How to read the netlist", text)
                    self.assertLessEqual(len(text), max(limit, floor))
            tiny = render(path, max_chars=1)
            self.assertIn("raised to fit sections 1, 2 and 9", tiny)
            self.assertIn("Cut at", tiny)

    def test_help_names_the_minimum(self) -> None:  # M5
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            loki_main(["rp", "doc", "--help"])
        self.assertIn("never cut", " ".join(out.getvalue().split()))

    def test_attrs_line(self) -> None:  # M6
        rp = big()
        rp["coverage"]["attrs"] = {"elements": 2, "cells": 5}
        text = self.render(rp)
        self.assertIn("Of the committed cells, 5 (in 2 claims) are marked only by attributes", text)
        self.assertNotIn("marked only by attributes", self.render(big()))

    def test_article(self) -> None:  # L2
        for width in ("8", "11", "18", "80", "85", "800"):
            self.assertEqual(_article(f"{width}-bit adder"), f"an {width}-bit adder")
        for width in ("1", "2", "16", "110", "118", "180"):
            self.assertEqual(_article(f"{width}-bit adder"), f"a {width}-bit adder")
        self.assertEqual(_article("adder"), "an adder")
        self.assertEqual(_article("counter"), "a counter")

    def test_rejected_without_reason(self) -> None:  # L4
        rp = big()
        rp["elements"][-1]["reason"] = ""
        text = self.render(rp)
        self.assertIn("; it was rejected.", text)
        self.assertNotIn("rejected: .", text)
        self.assertNotIn("rejected: rejected", text)

    def test_conflicts_not_listed(self) -> None:  # L5
        rp = big()
        rp["elements"][0]["conflicts"] = ["h2"]
        rp["elements"][0]["links_outside"]["conflicts"] = 3
        self.assertIn("Conflicts with h2 and 3 more not listed.", self.render(rp))
        rp["elements"][0]["conflicts"] = []
        self.assertIn("Conflicts with 3 more not listed.", self.render(rp))

    def test_doc_names_input_by_basename(self) -> None:  # L1
        rp = big()
        rp["header"]["input"]["path"] = "/home/someone/secret/x.blif"
        self.assertNotIn("/home/someone", self.render(rp))


class GoldenL2Test(unittest.TestCase):
    """add-l2 on the stored add2 file: no Odin III needed."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        (self.dir / FILE).write_text(dump_json(golden()), encoding="utf-8")

    def part(self, design: str, ports: int = 8) -> Path:
        ids = ["n10", "n11", "n12", "n13", *[f"p{i}" for i in range(ports)]]
        obj = partition(ids, [0, 0, 1, 1, *[0] * ports])
        obj["design"] = design
        return write_obj(self.dir / "p.json", obj)

    def test_invalid_file_is_refused_before_indexing(self) -> None:  # M1
        for text in ("{}", "[]", '{"schema": 1}'):
            (self.dir / FILE).write_text(text, encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                add_l2(self.dir, self.part("add2"))
            self.assertIn("not a schema-1 reverse-provenance file", str(ctx.exception))
        (self.dir / FILE).write_text("{}", encoding="utf-8")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = loki_main(["rp", "add-l2", str(self.dir), str(self.dir / "p.json")])
        self.assertEqual(code, 2)
        self.assertIn("not a schema-1", err.getvalue())

    def test_design_match_accepts_unjoined_ports(self) -> None:  # M2
        add_l2(self.dir, self.part("add2"))
        l2 = json.loads((self.dir / FILE).read_text(encoding="utf-8"))["l2"]
        self.assertEqual(l2["partition"]["unjoined_nodes"], 8)
        self.assertIs(l2["partition"]["allow_unjoined_ports"], False)

    def test_other_design_is_refused(self) -> None:  # M2
        before = (self.dir / FILE).read_bytes()
        with self.assertRaises(JoinError) as ctx:
            add_l2(self.dir, self.part("mult8"))
        self.assertIn("--allow-unjoined-ports", str(ctx.exception))
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = loki_main(["rp", "add-l2", str(self.dir), str(self.dir / "p.json")])
        self.assertEqual(code, 2)
        self.assertEqual((self.dir / FILE).read_bytes(), before)

    def test_other_design_with_flag_is_recorded(self) -> None:  # M2
        part = self.part("mult8")
        with contextlib.redirect_stdout(io.StringIO()):
            code = loki_main(["rp", "add-l2", str(self.dir), str(part), "--allow-unjoined-ports"])
        self.assertEqual(code, 0)
        rp = json.loads((self.dir / FILE).read_text(encoding="utf-8"))
        self.assertEqual(validate_reverse_provenance(rp), [])
        self.assertIs(rp["l2"]["partition"]["allow_unjoined_ports"], True)

    def test_fully_named_ports_need_no_design_match(self) -> None:  # M2
        obj = partition(["n10", "n11", "n12", "n13"], [0, 0, 1, 1])
        obj["design"] = "mult8"
        block = build_l2(golden(), load_partition(write_obj(self.dir / "q.json", obj)), "q.json")
        partition_block = cast(dict[str, Any], block["partition"])
        self.assertEqual(partition_block["unjoined_nodes"], 0)


@unittest.skipUnless(can_run_f2(), "needs Odin III, ABC and an F2 architecture")
class RealFixTest(unittest.TestCase):
    def test_header_paths(self) -> None:  # L1
        head = json.loads((run_re(ADD2) / FILE).read_text(encoding="utf-8"))["header"]
        self.assertEqual(head["input"]["path"], str(ADD2))
        self.assertEqual(head["input"]["name"], "add2.blif")
        self.assertEqual(head["calib"]["name"], "f2.json")

    def test_candidate_fsm_rows_have_status(self) -> None:  # H1
        out = run_re(FSM2, "--rp-min-p", "0.01")
        fsms = json.loads((out / FILE).read_text(encoding="utf-8"))["fsms"]
        self.assertTrue(fsms)
        self.assertEqual({f["status"] for f in fsms}, {"candidate"})

    def test_stored_golden_input_is_a_real_run(self) -> None:  # M8b
        rp = json.loads((run_re(ADD2) / FILE).read_text(encoding="utf-8"))
        self.assertEqual(normalised(rp), golden())

    def test_existing_outputs_do_not_depend_on_rp_min_p(self) -> None:  # M8a
        runs = [run_re(ADD2, tag="d"), run_re(ADD2, "--rp-min-p", "0.01"),
                run_re(ADD2, "--rp-min-p", "0.99")]
        for name in DIGEST:
            blobs = {self.normal(name, r / name) for r in runs}
            self.assertEqual(len(blobs), 1, name)

    def test_existing_outputs_match_main(self) -> None:  # M8a
        out = run_re(ADD2)
        for name, digest in DIGEST.items():
            data = self.normal(name, out / name)
            self.assertEqual(hashlib.sha256(data).hexdigest(), digest, name)

    @staticmethod
    def normal(name: str, path: Path) -> bytes:
        """The file with the machine-specific paths replaced (and the versions of report.json)."""
        data = path.read_bytes()
        if name not in ("report.json", "report.md"):
            return data
        text = data.decode("utf-8").replace(str(ADD2), "ADD2").replace(str(CALIB), "CALIB")
        if name == "report.md":
            return text.encode("utf-8")
        obj = json.loads(text)
        obj.pop("versions")
        return json.dumps(obj, sort_keys=True).encode("utf-8")


if __name__ == "__main__":
    unittest.main()
