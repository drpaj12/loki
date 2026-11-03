"""Tests for loki/prov_steps.py on two runs written by Odin III v1.4: the silicon flow (comparator
through GDS and back) and the VTR flow (``odin3-flow --prov``). The fixtures are copies of
Odin III ``tests/silicon/comparator*/prov``."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from loki.prov_steps import ProvError, ProvRun, read_run, resolve

DATA = Path(__file__).resolve().parent / "data" / "prov_steps"
SILICON = DATA / "silicon"
VTR = DATA / "vtr"


class SiliconRunTest(unittest.TestCase):
    run_: ProvRun

    @classmethod
    def setUpClass(cls) -> None:
        cls.run_ = read_run(SILICON)

    def test_index_and_stages(self) -> None:
        r = self.run_
        self.assertEqual(r.index["flow"], "silicon-sky130")
        self.assertEqual([s.id for s in r.steps], ["read", "elab", "map", "equiv", "netlist",
                                                   "place", "route", "gds", "extract", "lvs",
                                                   "recover"])
        counts = {st: len(ids) for st, ids in r.by_stage.items()}
        self.assertEqual(counts["gates"], 17)
        self.assertEqual(counts["placed"], 20)
        self.assertEqual(counts["routed"], 46)
        self.assertEqual(counts["recovered"], 46)

    def test_checks_are_in_headers(self) -> None:
        self.assertEqual(self.run_.step("equiv").header["check"]["result"], "equivalent")
        self.assertEqual(self.run_.step("lvs").header["check"]["result"], "match")
        census = self.run_.step("place").header["census"]["steps"]
        self.assertEqual([c["step"] for c in census][:3],
                         ["s00_link", "s01_floorplan", "s02_tapcell"])

    def test_gate_resolves_to_ir_by_cone(self) -> None:
        gate = self.run_.stage_objects("gates")[0]
        res = resolve(self.run_, gate)
        self.assertTrue(res.reached_hdl)
        self.assertEqual(res.path[0].id, gate.id)
        self.assertEqual(res.path[-1].stage, "ir")
        self.assertEqual(res.weakest, "medium")
        self.assertTrue(res.sources)

    def test_recovered_cell_resolves_through_every_stage(self) -> None:
        joined = [o for o in self.run_.stage_objects("recovered") if o.attrs["join"] == "matched"
                  and o.origin == "hdl"]
        self.assertEqual(len(joined), 17)
        res = resolve(self.run_, joined[0])
        self.assertTrue(res.reached_hdl)
        stages = [o.stage for o in res.path]
        self.assertEqual(stages[0], "recovered")
        self.assertEqual(stages[-1], "ir")
        for stage in ("routed", "placed", "gates"):
            self.assertIn(stage, stages)
        self.assertEqual(res.weakest, "medium")

    def test_physical_cells_have_no_hdl_chain(self) -> None:
        fill = [o for o in self.run_.stage_objects("routed") if o.physical_step == "fill"]
        tap = [o for o in self.run_.stage_objects("placed") if o.physical_step == "tap"]
        self.assertEqual((len(fill), len(tap)), (26, 3))
        res = resolve(self.run_, fill[0])
        self.assertFalse(res.reached_hdl)
        self.assertEqual(res.origin, "physical:fill")
        self.assertEqual(res.sources, ())

    def test_resized_cell_keeps_its_name_link(self) -> None:
        resized = [o for o in self.run_.stage_objects("placed")
                   if any(lk.kind == "resize" for lk in o.links)]
        self.assertEqual(len(resized), 1)
        self.assertIn("resized_from", resized[0].attrs)
        self.assertNotEqual(resized[0].attrs["resized_from"], resized[0].attrs["master"])
        self.assertTrue(resolve(self.run_, resized[0]).reached_hdl)

    def test_by_string_id(self) -> None:
        obj = self.run_.stage_objects("routed")[0]
        self.assertEqual(resolve(self.run_, obj.id).path[0], obj)


class VtrRunTest(unittest.TestCase):
    def test_lut_resolves_to_hdl_constructs(self) -> None:
        run = read_run(VTR)
        self.assertEqual([s.stage for s in run.steps], ["hdl", "luts"])
        luts = [o for o in run.stage_objects("luts") if o.origin == "hdl"]
        self.assertTrue(luts)
        res = resolve(run, luts[0])
        self.assertTrue(res.reached_hdl)
        self.assertEqual(res.path[-1].stage, "hdl")
        self.assertEqual(res.weakest, "exact")
        self.assertTrue(luts[0].recs)


class CliTest(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, str]:
        import contextlib
        import io

        from loki.cli import main

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["prov", *args])
        return code, out.getvalue()

    def test_summary(self) -> None:
        code, text = self.run_cli(str(SILICON))
        self.assertEqual(code, 0)
        self.assertIn("flow silicon-sky130", text)
        self.assertIn("recover", text)
        self.assertIn("check netgen_lvs: match", text)

    def test_resolve(self) -> None:
        run = read_run(SILICON)
        target = next(o for o in run.stage_objects("recovered") if o.origin == "hdl")
        code, text = self.run_cli(str(SILICON), "--resolve", target.id)
        self.assertEqual(code, 0)
        self.assertIn("reached hdl: True", text)
        self.assertIn("bm_DL_4_bit_comparator.v:", text)

    def test_unknown_object_and_bad_run(self) -> None:
        self.assertEqual(self.run_cli(str(SILICON), "--resolve", "gates:nope")[0], 1)
        self.assertEqual(self.run_cli(str(DATA))[0], 2)


class ContractTest(unittest.TestCase):
    def copy(self) -> Path:
        tmp = Path(tempfile.mkdtemp())
        shutil.copytree(VTR, tmp / "prov")
        return tmp / "prov"

    def test_sha256_mismatch_is_refused(self) -> None:
        run = self.copy()
        objs = run / "02-map.objects.jsonl"
        objs.write_text(objs.read_text().replace('"exact"', '"high"', 1))
        with self.assertRaises(ProvError):
            read_run(run)
        self.assertTrue(read_run(run, verify=False).objects)

    def test_unknown_schema_is_refused(self) -> None:
        run = self.copy()
        data = json.loads((run / "index.json").read_text())
        data["schema"] = 2
        (run / "index.json").write_text(json.dumps(data))
        with self.assertRaises(ProvError):
            read_run(run)

    def test_missing_index_is_a_partial_run(self) -> None:
        run = self.copy()
        (run / "index.json").rename(run / "index.json.part")
        with self.assertRaises(ProvError):
            read_run(run)

    def test_dangling_link_is_refused(self) -> None:
        run = self.copy()
        data = json.loads((run / "index.json").read_text())
        objs = run / "02-map.objects.jsonl"
        lines = objs.read_text().splitlines()
        row = json.loads(lines[0])
        row["links"][0]["to"] = "hdl:nowhere"
        lines[0] = json.dumps(row)
        objs.write_text("\n".join(lines) + "\n")
        with self.assertRaises(ProvError):
            read_run(run, verify=False)
        self.assertEqual(data["schema"], 1)

    def test_unknown_fields_are_ignored(self) -> None:
        run = self.copy()
        objs = run / "01-read.objects.jsonl"
        lines = objs.read_text().splitlines()
        row = json.loads(lines[0])
        row["future_field"] = {"x": 1}
        lines[0] = json.dumps(row)
        objs.write_text("\n".join(lines) + "\n")
        self.assertTrue(read_run(run, verify=False).objects)


if __name__ == "__main__":
    unittest.main()
