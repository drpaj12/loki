"""Unit tests for the LLM pilot scripts. Run: ``python -I -m unittest discover -s
experiments/llm-pilot -p 'test_*.py'`` (tests that need the VE clone skip without it)."""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))
common = importlib.import_module("common")
build = importlib.import_module("build_prompts")
collect = importlib.import_module("collect")
hints = importlib.import_module("make_hints")
pick = importlib.import_module("pick_designs")
score = importlib.import_module("score")
summ = importlib.import_module("summarize")


def have_ve() -> bool:
    try:
        return common.dataset_dir().is_dir()
    except FileNotFoundError:
        return False


NETLIST = """module RefModule(clk, a, q);
  wire _0_;
  wire _1_;
  input clk;
  wire clk;
  input [1:0] a;
  wire [1:0] a;
  output q;
  wire q;
  NOT _2_ (
    .A(a[0]),
    .Y(_0_)
  );
  NAND _3_ (
    .A(_0_),
    .B(a[1]),
    .Y(_1_)
  );
  NOR _4_ (
    .A(_1_),
    .B(a[1]),
    .Y(_5_)
  );
  DFF _6_ (
    .C(clk),
    .D(_1_),
    .Q(q)
  );
endmodule
"""


class RenameAndNets(unittest.TestCase):
    def test_rename(self) -> None:
        out = hints.rename_cells(NETLIST)
        self.assertIn("  INV _2_ (", out)
        self.assertIn("  NAND2 _3_ (", out)
        self.assertIn("  NOR2 _4_ (", out)
        self.assertIn("  DFF _6_ (", out)

    def test_rename_rejects_odd_cell_line(self) -> None:
        with self.assertRaises(ValueError):
            hints.rename_cells("  NOT  weird_name (\n")

    def test_mappable(self) -> None:
        got = hints.mappable_nets(NETLIST)
        self.assertEqual(got, {"clk", "a[0]", "a[1]", "q", "_1_"})


def element(hid: str, ports: dict[str, list[str]], outs: dict[str, list[str]],
            nets: dict[str, list[str]] | None = None) -> dict[str, object]:
    return {"id": hid, "kind": "eq_const", "status": "committed", "conflicts": [],
            "children": [], "parents": [], "links_outside": {"conflicts": 0, "children": 0,
                                                             "parents": 0},
            "ports": {"inputs": ports, "outputs": outs}, "nets": nets or {}, "role": "datapath"}


class Translate(unittest.TestCase):
    def rp(self) -> dict[str, object]:
        a = element("h1", {"A": ["a[0]", "a[1]"]}, {"Y": ["q"]})
        b = element("h2", {"A": ["a[0]"]}, {"Y": ["$n5"]})
        c = element("h3", {}, {}, {"d": ["_1_"], "q": ["q"]})
        a["conflicts"] = ["h2"]
        bus = {"id": "h4", "bits": [["a[0]"], ["$n9"]], "width": 2, "status": "candidate"}
        d = element("h4", {}, {})
        d["kind"] = "bus"
        return {"elements": [a, b, c, d], "buses": [bus], "fsms": [],
                "hierarchy": [{"id": "h2", "module": "m2", "instance": "i2", "children": [
                    {"id": "h1", "module": "m1", "instance": "i1", "children": []}]}]}

    def test_drops_and_counts(self) -> None:
        new, stats = hints.translate(self.rp(), {"a[0]", "a[1]", "q", "_1_"})
        self.assertEqual([e["id"] for e in new["elements"]], ["h1", "h3"])
        self.assertEqual(stats, {"claims": 4, "claims_kept": 2, "buses": 1, "buses_kept": 0,
                                 "fsms": 0, "fsms_kept": 0})
        self.assertEqual(new["buses"], [])

    def test_hierarchy_promotes_children(self) -> None:
        new, _ = hints.translate(self.rp(), {"a[0]", "a[1]", "q", "_1_"})
        self.assertEqual([n["id"] for n in new["hierarchy"]], ["h1"])

    def test_conflicts_become_counted(self) -> None:
        new, _ = hints.translate(self.rp(), {"a[0]", "a[1]", "q", "_1_"})
        h1 = new["elements"][0]
        self.assertEqual(h1["conflicts"], [])
        self.assertEqual(h1["links_outside"]["conflicts"], 1)

    def test_nets_shown_as_ports(self) -> None:
        new, _ = hints.translate(self.rp(), {"a[0]", "a[1]", "q", "_1_"})
        h3 = new["elements"][1]
        self.assertEqual(h3["ports"]["outputs"], {"q": ["q"]})
        self.assertEqual(h3["ports"]["inputs"], {"d": ["_1_"]})

    def test_input_not_mutated(self) -> None:
        rp = self.rp()
        hints.translate(rp, set())
        self.assertEqual(len(rp["elements"]), 4)


class Extract(unittest.TestCase):
    def test_plain(self) -> None:
        code, found = collect.extract_rtl("[BEGIN]\nmodule TopModule;\nendmodule\n[DONE]\n")
        self.assertTrue(found)
        self.assertEqual(code, "module TopModule;\nendmodule\n")

    def test_fence_inside_markers_removed(self) -> None:
        text = "x\n[BEGIN]\n```verilog\nmodule T;\nendmodule\n```\n[DONE]"
        code, found = collect.extract_rtl(text)
        self.assertTrue(found)
        self.assertEqual(code, "module T;\nendmodule\n")

    def test_inline_markers(self) -> None:
        code, found = collect.extract_rtl("[BEGIN] module T;\nendmodule [DONE]")
        self.assertTrue(found)
        self.assertIn("module T;", code)

    def test_missing_done_is_not_found(self) -> None:
        self.assertEqual(collect.extract_rtl("[BEGIN]\nmodule T;\n"), ("", False))

    def test_no_markers(self) -> None:
        self.assertEqual(collect.extract_rtl("module T;\nendmodule"), ("", False))

    def test_fallback_fence(self) -> None:
        self.assertEqual(collect.fallback_rtl("hi\n```verilog\nmodule T;\n```\nbye"), "module T;\n")
        self.assertEqual(collect.fallback_rtl("no fence"), "")

    def test_steps(self) -> None:
        got = collect.steps_present("// Step 1: x\n//Step 3\n// step 4")
        self.assertEqual(got, {1: True, 2: False, 3: True, 4: True})


class Scoring(unittest.TestCase):
    def test_sim_classes(self) -> None:
        self.assertEqual(score.classify_sim("Mismatches: 0 in 20 samples")[0], "pass")
        self.assertEqual(score.classify_sim("Mismatches: 3 in 20 samples")[0], "runtime")
        self.assertEqual(score.classify_sim("Mismatches: 0 in 0 samples")[0], "runtime")
        self.assertEqual(score.classify_sim("garbage")[0], "runtime")

    def test_compile_classes(self) -> None:
        self.assertEqual(score.classify_compile(0, ""), "")
        self.assertEqual(score.classify_compile(1, "x.sv:1: syntax error"), "syntax")
        self.assertEqual(score.classify_compile(1, "x.sv:1: error: unknown module"), "compile")


class Summaries(unittest.TestCase):
    def test_fsm_uptake(self) -> None:
        rtl = ("module T(input clk, output y);\nreg [1:0] state;\nalways @(posedge clk) begin\n"
               "state <= 1;\nend\nalways @(*) case (state)\n0: ;\nendcase\nendmodule\n")
        self.assertTrue(summ.fsm_uptake(rtl))
        self.assertFalse(summ.fsm_uptake("module T(input a, output y); assign y = a; endmodule"))

    def test_bus_uptake(self) -> None:
        self.assertTrue(summ.bus_uptake("input [3:0] a;", 4))
        self.assertFalse(summ.bus_uptake("input [3:0] a;", 5))

    def test_rate(self) -> None:
        self.assertEqual(summ.rate(3, 4), "3/4 (0.75)")
        self.assertEqual(summ.rate(0, 0), "0/0")


class Prompts(unittest.TestCase):
    def test_a_first_is_deterministic(self) -> None:
        self.assertEqual(common.a_first("Prob024_hadd"), common.a_first("Prob024_hadd"))
        flags = {common.a_first(f"Prob{n:03d}") for n in range(40)}
        self.assertEqual(flags, {True, False})

    def test_arm_c_cuts_netlist(self) -> None:
        text = "intro\nthe interface:\na, b\n\nGate-level netlist:\n```verilog\nmodule X;\n```\n"
        c = build.question_text(text, "C")
        self.assertNotIn("module X", c)
        self.assertTrue(c.endswith(common.C_NOTE))

    def test_arm_b_appends_hints(self) -> None:
        b = build.question_text("p\n", "B", "HINTS\n")
        self.assertEqual(b, "p\n\nHINTS")

    def test_user_message_shape(self) -> None:
        msg = build.user_message("PREFIX", "Q\n", "A")
        self.assertEqual(msg, "PREFIX\nQuestion:\nQ\n" + common.SUFFIX + "\nAnswer:\n")

    @unittest.skipUnless(have_ve(), "VE clone not available")
    def test_regression_pin(self) -> None:
        prefix = common.prefix_file().read_text(encoding="utf-8")
        self.assertEqual(len(prefix.encode("utf-8")), 6862)
        build.check_pin(prefix)

    @unittest.skipUnless(have_ve(), "VE clone not available")
    def test_call_order(self) -> None:
        order = build.call_order(build.read_selection())
        self.assertEqual(len(order), 120)
        self.assertEqual([a for _, a in order[2::3]], ["C"] * 40)
        sizes = [int(r["netlist_lines"]) for r, _ in order[::3]]
        self.assertEqual(sizes, sorted(sizes))


class Selection(unittest.TestCase):
    @unittest.skipUnless(have_ve(), "VE clone not available")
    def test_selection_matches_csv(self) -> None:
        import csv
        with (HERE / "selection.csv").open(encoding="utf-8", newline="") as fh:
            want = [(r["quartile"], r["problem"]) for r in csv.DictReader(fh)]
        self.assertEqual(pick.select(), want)
        self.assertEqual(len(want), 40)


if __name__ == "__main__":
    unittest.main()
