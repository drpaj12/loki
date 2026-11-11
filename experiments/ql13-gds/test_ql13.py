"""Unit tests of Q-L13: chain completeness on the stored comparator run, and the extracted-cell
netlist converter on a small hand-written hierarchical SPICE (no Odin III, no external tool)."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ql13_chain as ch  # noqa: E402
import ql13_env as env  # noqa: E402
import ql13_gdsnet as gn  # noqa: E402

from loki.prov_steps import read_run  # noqa: E402

FIXTURE = env.REPO / "tests" / "data" / "prov_steps" / "silicon"
LIB_TEXT = """library t

cell sky130_fd_sc_hd__nand2_1 gate area 1
  in A 1 ; in B 1 ; out Y 1
  fn Y = ( ~ A ) | ( ~ B )
end
cell sky130_fd_sc_hd__dfxtp_1 gate area 1
  in CLK 1 clock ; in D 1 ; out Q 1
  seq Q <= D @ posedge CLK init x
end
"""
SPICE = """* test
.subckt sky130_fd_sc_hd__nand2_1 B Y A VGND VPWR VPB VNB
.ends

.subckt sky130_fd_sc_hd__dfxtp_1 Q CLK D VPWR VGND VPB VNB
.ends

.subckt sky130_fd_sc_hd__fill_4 VGND VPWR VPB VNB
.ends

.subckt top a b clk q VDD VSS
Xsky130_fd_sc_hd__nand2_1_0 b nand/Y a VSS VDD VDD VSS sky130_fd_sc_hd__nand2_1
Xsky130_fd_sc_hd__dfxtp_1_0 q clk
+ nand/Y VDD VSS VDD VSS sky130_fd_sc_hd__dfxtp_1
Xsky130_fd_sc_hd__fill_4_0 VSS VDD VDD VSS sky130_fd_sc_hd__fill_4
.ends
"""


class ChainTest(unittest.TestCase):
    def test_comparator_share_one(self) -> None:
        row, cat, weak = ch.analyse(read_run(FIXTURE))
        self.assertEqual(row["n_logic"], 17)
        self.assertEqual(row["a_share"], "1.0000")
        self.assertEqual(row["b_share"], "1.0000")
        self.assertEqual(cat, [])
        self.assertEqual(sum(weak.values()), 17)
        self.assertGreater(row["n_tap"] + row["n_fill"], 0)

    def test_chain_reaches_hdl_through_every_stage(self) -> None:
        run = read_run(FIXTURE)
        obj = next(o for o in run.stage_objects("extracted") if ch.cell_class(run, o) == "logic")
        c = ch.full_chain(run, obj, "logic")
        self.assertTrue(c.complete)
        self.assertEqual(c.stages[0], "extracted")
        self.assertEqual(c.stages[-1], "hdl")
        for stage in ch.STAGE_ORDER:
            self.assertIn(stage, c.stages)
        self.assertTrue(c.spans)

    def test_unjoined_is_a_break(self) -> None:
        run = read_run(FIXTURE)
        obj = next(o for o in run.stage_objects("extracted") if ch.cell_class(run, o) == "logic")
        c = ch.full_chain(run, obj, "unjoined")
        self.assertFalse(c.complete)
        self.assertEqual(c.broken_at, "extracted")


class BreakTest(unittest.TestCase):
    """A run with a cut link must land in the failure catalogue (the measure can say no)."""

    def _copy(self, tmp: Path) -> Path:
        dst = tmp / "prov"
        shutil.copytree(FIXTURE, dst)
        return dst

    def test_cut_join_and_cut_cone(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            prov = self._copy(Path(t))
            ext = prov / "09-extract.objects.jsonl"
            rows = [json.loads(x) for x in ext.read_text(encoding="utf-8").splitlines()]
            logic = [r for r in rows if "tap" not in r["type"] and "fill" not in r["type"]]
            logic[0]["links"] = []  # no location_match: unjoined
            ext.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
            gates = prov / "03-map.objects.jsonl"
            grows = [json.loads(x) for x in gates.read_text(encoding="utf-8").splitlines()]
            grows[0]["links"] = []  # a mapped gate with no cone link to the ir
            gates.write_text("\n".join(json.dumps(r) for r in grows) + "\n", encoding="utf-8")
            row, cat, _w = ch.analyse(read_run(prov, verify=False))
        self.assertEqual(row["n_unjoined"], 1)
        self.assertLess(float(row["a_share"]), 1.0)
        self.assertLess(float(row["b_share"]), 1.0)
        causes = {c["cause"] for c in cat}
        self.assertIn("no location_match link", causes)
        self.assertTrue(len(cat) >= 2, cat)


class NetTest(unittest.TestCase):
    def test_cover(self) -> None:
        self.assertEqual(gn.cover("( ~ A ) | ( ~ B )", ["A", "B"]), ["0- 1", "-0 1"])
        self.assertEqual(gn.cover("( A & B )", ["A", "B"]), ["11 1"])
        with self.assertRaises(gn.Unsupported):
            gn.cover("( C )", ["A", "B"])

    def test_convert(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "h.spice"
            sp.write_text(SPICE, encoding="utf-8")
            lib_file = Path(tmp) / "t.o3lib"
            lib_file.write_text(LIB_TEXT, encoding="utf-8")
            text, ports, kinds = gn.convert(sp, gn.read_lib(lib_file))
        self.assertEqual(kinds, {"sky130_fd_sc_hd__nand2_1_0": "lut",
                                 "sky130_fd_sc_hd__dfxtp_1_0": "ff"})
        self.assertIn(".latch", text)
        self.assertIn("0- 1\n-0 1", text)
        self.assertEqual(sorted(p["orig"] for p in ports if p["dir"] == "out"), ["q"])
        self.assertEqual(sorted(p["orig"] for p in ports if p["dir"] == "in"), ["a", "b", "clk"])

    def test_constants_get_unique_cnames(self) -> None:
        spice = (".subckt sky130_fd_sc_hd__conb_1 HI LO VPWR VGND VPB VNB\n.ends\n"
                 ".subckt top y z VDD VSS\n"
                 "Xsky130_fd_sc_hd__conb_1_0 y z VDD VSS VDD VSS sky130_fd_sc_hd__conb_1\n.ends\n")
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "h.spice"
            sp.write_text(spice, encoding="utf-8")
            text, _ports, _kinds = gn.convert(sp, {})
        names = [x for x in text.splitlines() if x.startswith(".cname")]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(names), 2)

    def test_resized_master_and_buffer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lib_file = Path(tmp) / "t.o3lib"
            lib_file.write_text(LIB_TEXT, encoding="utf-8")
            lib = gn.read_lib(lib_file)
        kind, lc = gn.lib_cell(lib, "sky130_fd_sc_hd__nand2_4",
                               ["A", "B", "Y", "VGND", "VPWR", "VPB", "VNB"])
        self.assertEqual((kind, lc.outs), ("lut", ["Y"]))
        kind, lc = gn.lib_cell(lib, "sky130_fd_sc_hd__clkbuf_16",
                               ["X", "A", "VGND", "VPWR", "VPB", "VNB"])
        self.assertEqual((kind, lc.fn), ("lut", {"X": "A"}))
        kind, lc = gn.lib_cell(lib, "sky130_fd_sc_hd__clkinvlp_4",
                               ["A", "Y", "VGND", "VPWR", "VPB", "VNB"])
        self.assertEqual(lc.fn, {"Y": "~ A"})
        with self.assertRaises(gn.Unsupported):
            gn.lib_cell(lib, "sky130_fd_sc_hd__nosuch_2", ["A", "X"])
        self.assertEqual(gn.lib_cell(lib, "sky130_fd_sc_hd__dfxtp_1", [])[0], "ff")


if __name__ == "__main__":
    unittest.main()


class EnvTest(unittest.TestCase):
    def test_results_dir_default_and_override(self) -> None:
        import importlib
        import os
        old = os.environ.pop("QL13_RES", None)
        try:
            self.assertEqual(importlib.reload(env).RES.name, "results")
            os.environ["QL13_RES"] = "/x/results-v161"
            self.assertEqual(importlib.reload(env).RES, Path("/x/results-v161"))
        finally:
            os.environ.pop("QL13_RES", None)
            if old is not None:
                os.environ["QL13_RES"] = old
            importlib.reload(env)


class FlowTest(unittest.TestCase):
    def test_limit_inside_heavy_run(self) -> None:
        import ql13_flow as fl
        d = {"name": "x", "top": "t", "src": "s", "clock": "clk"}
        cmd = fl.build_cmd(d, Path("/a/s.v"), Path("/r"))
        self.assertTrue(cmd[0].endswith("heavy-run"))
        self.assertEqual(cmd[1:5], ["timeout", "-s", "KILL", str(fl.FLOW_LIMIT)])
        self.assertGreater(fl.BACKSTOP, fl.SLOT_WAIT + fl.FLOW_LIMIT)
        self.assertGreaterEqual(fl.FLOW_LIMIT, 14400)

    def test_timeout_kills_whole_group(self) -> None:
        import os
        import time

        import ql13_flow as fl
        marker = Path(tempfile.mkdtemp()) / "pid"
        sh = f"sleep 300 & echo $! > {marker}; wait"
        out, code = fl.run_group(["bash", "-c", sh], 1.0)
        self.assertEqual(code, 124)
        pid = int(marker.read_text())
        time.sleep(0.3)
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)
