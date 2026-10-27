"""Unit tests for the LLM pilot scripts. Run: ``python -I -m unittest discover -s
experiments/llm-pilot -p 'test_*.py'`` (tests that need the VE clone skip without it)."""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))
common = importlib.import_module("common")
build = importlib.import_module("build_prompts")
collect = importlib.import_module("collect")
hints = importlib.import_module("make_hints")
netmap = importlib.import_module("netmap")
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


class RenameRp(unittest.TestCase):
    def rp(self) -> dict[str, object]:
        a = element("h1", {"A": ["a[0]", "a[1]"]}, {"Y": ["q"]})
        b = element("h2", {"A": ["a[0]"]}, {"Y": ["$n5"]})
        c = element("h3", {}, {}, {"d": ["_1_"], "q": ["q"]})
        a["conflicts"] = ["h2"]
        bus = {"id": "h4", "bits": [["a[0]"], ["$n9"]], "width": 2, "status": "candidate"}
        d = element("h4", {}, {})
        d["kind"] = "bus"
        fsm = {"id": "h5", "state_nets": ["c7"], "control_nets": ["$n5"], "reset_net": []}
        return {"elements": [a, b, c, d], "buses": [bus], "fsms": [fsm], "hierarchy": []}

    def test_every_net_list_renamed_nothing_dropped(self) -> None:
        new = hints.rename_rp(self.rp(), {"$n5": "w1", "$n9": "_7_", "c7": "w2"})
        self.assertEqual([e["id"] for e in new["elements"]], ["h1", "h2", "h3", "h4"])
        self.assertEqual(new["elements"][1]["ports"]["outputs"], {"Y": ["w1"]})
        self.assertEqual(new["buses"][0]["bits"], [["a[0]"], ["_7_"]])
        self.assertEqual(new["fsms"][0]["state_nets"], ["w2"])
        self.assertEqual(new["fsms"][0]["control_nets"], ["w1"])
        left = {n for n in hints.all_names(new) if n.startswith("$n") or n == "c7"}
        self.assertEqual(left, set())

    def test_nets_shown_as_ports(self) -> None:
        new = hints.rename_rp(self.rp(), {})
        h3 = new["elements"][2]
        self.assertEqual(h3["ports"]["outputs"], {"q": ["q"]})
        self.assertEqual(h3["ports"]["inputs"], {"d": ["_1_"]})

    def test_input_not_mutated(self) -> None:
        rp = self.rp()
        hints.rename_rp(rp, {"$n5": "w1"})
        self.assertEqual(rp["elements"][1]["ports"]["outputs"], {"Y": ["$n5"]})


class NetMap(unittest.TestCase):
    def test_expr(self) -> None:
        self.assertEqual(netmap.expr(0b01, ["x"]), "NOT(x)")
        self.assertEqual(netmap.expr(0b10, ["x"]), "x")
        self.assertEqual(netmap.expr(0b1000, ["a", "b"]), "AND(a, b)")
        self.assertEqual(netmap.expr(0b0001, ["a", "b"]), "AND(NOT(a), NOT(b))")
        self.assertEqual(netmap.expr(0b1110, ["a", "b"]), "OR(a, b)")
        self.assertEqual(netmap.expr(0, ["a"]), "0")
        self.assertEqual(netmap.expr(0b11, ["a"]), "1")

    def test_order_key(self) -> None:
        names = ["c9", "$n10", "$n2", "c10"]
        self.assertEqual(sorted(names, key=netmap.order_key), ["$n2", "$n10", "c10", "c9"])

    def test_signatures_follow_logic(self) -> None:
        sig = netmap.orig_signatures(NETLIST)
        self.assertEqual(sig["_0_"], ~sig["a[0]"] & netmap.MASK)
        self.assertEqual(sig["_1_"], ~(sig["_0_"] & sig["a[1]"]) & netmap.MASK)
        self.assertEqual(sig["q"], netmap.vec("q"))

    def test_bits_of(self) -> None:
        self.assertEqual(netmap.bits_of("{a[1:0], 2'h1}"), ["a[1]", "a[0]", "#0", "#1"])


class LeakGate(unittest.TestCase):
    def test_hits(self) -> None:
        for bad in ("net $n12", "cell c9 here", "loki_x", "Prob024_hadd", "from L0", "provenance"):
            self.assertTrue(build.leak_hits(bad), bad)
        self.assertEqual(build.leak_hits("Y = AND(w1, _03_) and clk, a[0]"), [])


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
        self.assertEqual(score.classify_sim("garbage")[0], "no-result")

    def test_sim_requires_exactly_one_anchored_line(self) -> None:
        faked = 'Mismatches: 0 in 20 samples\nMismatches: 3 in 20 samples\n'
        self.assertEqual(score.classify_sim(faked)[0], "no-result")
        indented = 'x $display("Mismatches: 0 in 20 samples");\n'
        self.assertEqual(score.classify_sim(indented)[0], "no-result")
        self.assertEqual(score.classify_sim("noise\nMismatches: 0 in 20 samples\n")[0], "pass")

    def test_compile_classes(self) -> None:
        self.assertEqual(score.classify_compile(0, ""), "")
        self.assertEqual(score.classify_compile(1, "x.sv:1: syntax error"), "syntax")
        self.assertEqual(score.classify_compile(1, "x.sv:1: error: unknown module"), "compile")


def run_dir_tmp(name: str) -> Path:
    path = common.run_dir() / "testtmp" / name
    path.mkdir(parents=True, exist_ok=True)
    return path


GOOD_AND = "module TopModule(input a, input b, output out);\n assign out = a & b;\nendmodule\n"


class ScorerFixes(unittest.TestCase):
    def test_cheat_detection(self) -> None:
        self.assertTrue(score.is_cheat("module TopModule(input a, output y);\n"
                                       "RefModule r(.a(a), .y(y));\nendmodule"))
        self.assertTrue(score.is_cheat("module stimulus_gen(); endmodule"))
        self.assertTrue(score.is_cheat("module tb(); endmodule"))
        self.assertFalse(score.is_cheat("// RefModule is only named in a comment\n" + GOOD_AND))
        self.assertFalse(score.is_cheat(GOOD_AND))

    def test_gb_equivalent_strings(self) -> None:
        ok = "Mismatches: 0 in 20 samples\n"
        self.assertEqual(score.gb_classify(ok), ".")
        self.assertEqual(score.gb_classify("x.sv:3: syntax error\n" + ok), "S")
        self.assertEqual(score.gb_classify("x.sv:3: error: boom\n" + ok), "C")
        self.assertEqual(score.gb_classify(
            "x.sv:2: warning: always_comb process has no sensitivities\n" + ok), "n")
        self.assertEqual(score.gb_classify(
            "x.sv:2: warning: @* found no sensitivities so it will never trigger.\n" + ok), "n")
        self.assertEqual(score.gb_classify("TIMEOUT\n" + ok), "T")
        self.assertEqual(score.gb_classify("Unknown module type: foo\n" + ok), "m")
        self.assertEqual(score.gb_classify("Mismatches: 4 in 20 samples\n"), "?")

    @unittest.skipUnless(have_ve(), "VE clone not available")
    def test_run_sample_happy_path(self) -> None:
        work = run_dir_tmp("happy")
        sample = work / "sample.sv"
        sample.write_text(GOOD_AND, encoding="utf-8")
        res = score.run_sample(sample, "Prob014_andgate", work)
        self.assertEqual(res["outcome"], "pass")
        self.assertTrue(res["gb_pass"])
        self.assertEqual(res["mismatches"], 0)

    @unittest.skipUnless(have_ve(), "VE clone not available")
    def test_run_sample_wrong_fails(self) -> None:
        work = run_dir_tmp("wrong")
        sample = work / "sample.sv"
        sample.write_text(GOOD_AND.replace("a & b", "a | b"), encoding="utf-8")
        res = score.run_sample(sample, "Prob014_andgate", work)
        self.assertEqual(res["outcome"], "runtime")
        self.assertFalse(res["gb_pass"])

    @unittest.skipUnless(have_ve(), "VE clone not available")
    def test_refmodule_wrapper_is_cheat(self) -> None:
        work = run_dir_tmp("cheat")
        sample = work / "sample.sv"
        sample.write_text("module TopModule(input a, input b, output out);\n"
                          " RefModule r(.a(a), .b(b), .out(out));\nendmodule\n", encoding="utf-8")
        res = score.run_sample(sample, "Prob014_andgate", work)
        self.assertEqual(res["outcome"], "cheat")
        self.assertFalse(res["gb_pass"])

    @unittest.skipUnless(have_ve(), "VE clone not available")
    def test_faked_display_is_not_a_pass(self) -> None:
        work = run_dir_tmp("faked")
        sample = work / "sample.sv"
        sample.write_text(
            GOOD_AND.replace("a & b", "a | b").replace(
                "endmodule", ' initial $display("Mismatches: 0 in 100 samples");\nendmodule'),
            encoding="utf-8")
        res = score.run_sample(sample, "Prob014_andgate", work)
        self.assertNotEqual(res["outcome"], "pass")  # Gate-Breaker gb_pass is True here: its hole
        self.assertEqual(res["outcome"], "cheat")  # raw `Mismatches` text (fix 3, M1)

    def test_forbidden_raw_tokens(self) -> None:
        for tok in ("$finish", "$fatal", "Mismatches"):
            self.assertTrue(score.is_cheat(GOOD_AND + f"// {tok}\n"), tok)
        self.assertFalse(score.is_cheat(GOOD_AND))

    @unittest.skipUnless(have_ve(), "VE clone not available")
    def test_finish_at_time_zero_is_cheat(self) -> None:
        work = run_dir_tmp("finish0")
        sample = work / "sample.sv"
        sample.write_text(GOOD_AND.replace("a & b", "a | b").replace(
            "endmodule", " initial $finish;\nendmodule"), encoding="utf-8")
        res = score.run_sample(sample, "Prob014_andgate", work)
        self.assertEqual(res["outcome"], "cheat")
        self.assertFalse(res["gb_pass"])

    @unittest.skipUnless(have_ve(), "VE clone not available")
    def test_compile_timeout(self) -> None:
        import subprocess
        from unittest import mock
        work = run_dir_tmp("ctimeout")
        sample = work / "sample.sv"
        sample.write_text(GOOD_AND, encoding="utf-8")
        boom = subprocess.TimeoutExpired(cmd="iverilog", timeout=1)
        with mock.patch.object(score.subprocess, "run", side_effect=boom):
            res = score.run_sample(sample, "Prob014_andgate", work)
        self.assertEqual(res["outcome"], "compile-timeout")


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
        self.assertEqual(len(prefix.encode("utf-8")), 3030)
        build.check_prefix(prefix)
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


class VariantRe(unittest.TestCase):
    def test_re_system_prompt_pinned(self) -> None:
        text = (HERE / "prompts_variants" / "re" / "system.txt").read_text(encoding="utf-8")
        self.assertEqual(hashlib.md5(text.encode("utf-8"), usedforsecurity=False).hexdigest(),
                         common.RE_SYSTEM_MD5)
        self.assertEqual(len(text.encode("utf-8")), 495)
        self.assertTrue(text.startswith("You are a hardware engineer"))
        self.assertTrue(text.endswith("between [BEGIN] and [DONE]."))

    def test_variant_default_and_dirs(self) -> None:
        self.assertIn(common.VARIANT, common.VARIANTS)
        expect = "run" if common.VARIANT == "standard" else "run-re"
        self.assertEqual(common.run_dir().name, expect)
        self.assertEqual(common.hints_root().name, "run")

    def test_sizes_file_per_variant_and_system_leak_gate(self) -> None:
        want = "prompt_sizes.csv" if common.VARIANT == "standard" else "prompt_sizes_re.csv"
        self.assertEqual(build.sizes_file().name, want)
        self.assertEqual(build.leak_hits(common.system_msg()), [])
        self.assertEqual(build.leak_hits("see $n3 and key.json"), ["$n3", "key.json"])

    def test_hash_equality_compare(self) -> None:
        import check_hash_equality as che
        a = {("A", "P1"): "x", ("B", "P1"): "y"}
        self.assertEqual(che.compare(a, dict(a)), [])
        self.assertEqual(len(che.compare(a, {("A", "P1"): "x", ("B", "P1"): "z"})), 1)
        self.assertEqual(len(che.compare(a, {("A", "P1"): "x"})), 1)

    def test_status_section(self) -> None:
        rows = ["order,arm,problem,status,tool_calls,note"]
        for arm, st in (("A", "ok"), ("B", "ok"), ("C", "api_refused")):
            rows.append(f"001,{arm},P1,{st},2,")
        for arm in "ABC":
            rows.append(f"002,{arm},P2,ok,3,")
        res = {(a, p): {"pass": a != "C" or p == "P2"} for a in "ABC" for p in ("P1", "P2")}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.csv"
            path.write_text("\n".join(rows) + "\n", encoding="utf-8")
            out = "\n".join(summ.status_section(path, res))
        self.assertIn("| C | 1 | 1 | 0 | 0 | 1 | 1/2 (0.50) | 1/1 (1.00) | 1/1 (1.00) |", out)
        self.assertIn("api_refused | no_file", out)
        self.assertIn("Paired set: 1 problems", out)

    def test_archive_no_file(self) -> None:
        import archive_run
        with tempfile.TemporaryDirectory() as d:
            src, run = Path(d) / "src", Path(d) / "run"
            src.mkdir()
            run.mkdir()
            calls = [{"order": i, "arm": "A", "problem": f"P{i}"} for i in (1, 2)]
            (run / "calls.jsonl").write_text(
                "\n".join(json.dumps(c) for c in calls) + "\n", encoding="utf-8")
            (src / "dispatch-log.tsv").write_text("1\tok\t2\t9\t\n2\terror\t1\t9\tx\n",
                                                  encoding="utf-8")
            (src / "resp-001.txt").write_text("x", encoding="utf-8")
            counts = archive_run.archive(src, run, "m", 120, set(), frozenset({2}))
            self.assertEqual((counts["ok"], counts["no_file"]), (1, 1))
            self.assertIn("002,A,P2,no_file,1,x", (run / "status.csv").read_text("utf-8"))

    def test_archive_empty_response_and_conflict(self) -> None:
        import archive_run
        with tempfile.TemporaryDirectory() as d:
            src, run = Path(d) / "src", Path(d) / "run"
            src.mkdir()
            run.mkdir()
            calls = [{"order": i, "arm": "A", "problem": f"P{i}"} for i in (1, 2)]
            (run / "calls.jsonl").write_text(
                "\n".join(json.dumps(c) for c in calls) + "\n", encoding="utf-8")
            (src / "dispatch-log.tsv").write_text("1\tok\t2\t9\t\n2\tok\t2\t0\t\n",
                                                  encoding="utf-8")
            (src / "resp-001.txt").write_text("x", encoding="utf-8")
            (src / "resp-002.txt").write_text("", encoding="utf-8")
            counts = archive_run.archive(src, run, "m", 120, set())
            self.assertEqual((counts["ok"], counts["no-output"]), (1, 1))
            self.assertIn("002,A,P2,no-output,", (run / "status.csv").read_text("utf-8"))
            with self.assertRaises(SystemExit):
                archive_run.archive(src, run, "m", 120, {1}, frozenset({1}))

    def test_mcnemar_exact(self) -> None:
        import pilot_stats
        self.assertEqual(pilot_stats.mcnemar(2, 0), 0.5)
        self.assertAlmostEqual(pilot_stats.mcnemar(7, 1), 0.0703125)
        self.assertEqual(pilot_stats.mcnemar(0, 0), 1.0)


if __name__ == "__main__":
    unittest.main()
