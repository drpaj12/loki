import csv
import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from typing import Any

from loki.build import FloorResult, build_floor, floor_failures, main
from loki.equiv import EquivResult
from loki.schemas import validate_graph, validate_key, validate_labels_csv, validate_meta
from tests.helpers import DATA, can_run_f2, can_run_flow, f2_arch, micro, odin3_root, vtr_arch

FILES = ("netlist.blif", "netlist.v", "graph.json", "labels.csv", "key.json", "meta.json")
KEYWORDS = {"module", "endmodule", "input", "output", "wire", "assign", "reg", "always",
            "posedge", "negedge", "begin", "end", "if", "else"}


def build(path: Path, out: Path, floor: str = "f2", design: str = "d") -> FloorResult:
    root = odin3_root()
    assert root is not None
    arch = vtr_arch() if floor.startswith("f1") else f2_arch()
    return build_floor(design, [path], None, floor, arch, out, root)


def load(out: Path, name: str, design: str = "d", floor: str = "f2") -> Any:
    return json.loads((out / design / floor / name).read_text(encoding="utf-8"))


class FloorFailureTest(unittest.TestCase):
    def test_differs_and_error_fail_the_floor(self) -> None:
        r = {
            "a": EquivResult("equivalent", 0, ""),
            "b": EquivResult("error", 2, "x"),
            "c": EquivResult("differs", 1, ""),
            "d": EquivResult("unproven", 4, ""),
        }
        self.assertEqual(floor_failures(r), ["b=error", "c=differs"])


@unittest.skipUnless(can_run_f2(), "needs Odin III")
class BuildTest(unittest.TestCase):
    def test_f2_comparator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            res = build(micro("bm_DL_4_bit_comparator"), out)
            self.assertEqual((res.status, res.reason), ("ok", ""))
            fdir = out / "d" / "f2"
            self.assertEqual(sorted(p.name for p in fdir.iterdir()), sorted(FILES))
            graph, meta = load(out, "graph.json"), load(out, "meta.json")
            self.assertEqual(validate_graph(graph), [])
            self.assertEqual(validate_key(load(out, "key.json")), [])
            self.assertEqual(validate_meta(meta), [])
            text = (fdir / "labels.csv").read_text(encoding="utf-8")
            self.assertEqual(validate_labels_csv(text), [])
            self.assertEqual(len(list(csv.reader(io.StringIO(text)))) - 1, len(graph["nodes"]))
            self.assertEqual(meta["equiv"]["writer"]["status"], "equivalent")
            self.assertEqual(meta["equiv"]["anon"]["status"], "equivalent")
            kinds = [n["kind"] for n in graph["nodes"]]
            self.assertEqual((kinds.count("pi"), kinds.count("po"), kinds.count("lut")), (8, 3, 5))
            self.assertEqual(meta["unmatched"], 0)

    @unittest.skipUnless(can_run_flow(), "needs a VTR architecture")
    def test_f1_hard_cells_and_declared_ports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            res = build(micro("bm_base_multiply"), out, "f1-k6")
            self.assertEqual(res.status, "ok", res.reason)
            self.assertGreater(res.counts["hard"], 0)
            meta = load(out, "meta.json", floor="f1-k6")
            self.assertEqual(meta["equiv"]["anon"]["mode"], "soft-only")
            self.assertNotIn(res.equiv["writer"].status, ("differs", "error"))
            res = build(micro("bm_DL_BCD_7_segment_without_x"), out)  # output [7:1] leds
            self.assertEqual((res.status, res.equiv["writer"].status), ("ok", "equivalent"))
            text = (out / "d" / "f2" / "labels.csv").read_text(encoding="utf-8")
            self.assertIn("leds,7", text)
            self.assertNotIn("leds,0,", text)

    def test_no_original_names_outside_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            for micro_name in ("bm_DL_4_bit_comparator", "bm_DL_74381_ALU"):
                build(micro(micro_name), out, design=micro_name)
                fdir = out / micro_name / "f2"
                key = load(out, "key.json", micro_name)
                names = {n for net in key["nets"].values() for n in net["names"]}
                names |= {c["name"] for c in key["cells"].values()}
                names |= {p["orig"] for p in key["ports"]}
                names = {n for n in names if re.search(r"[A-Za-z]", n)}
                self.assertTrue(names, micro_name)
                graph = load(out, "graph.json", micro_name)
                for node in graph["nodes"]:  # answer-key label fields may carry names
                    for field in ("bus_name", "module_path"):
                        node["labels"].pop(field)
                text_csv = (fdir / "labels.csv").read_text(encoding="utf-8")
                rows = list(csv.reader(io.StringIO(text_csv)))
                skip = [rows[0].index("bus_name"), rows[0].index("module_path")]
                for row in rows[1:]:
                    for i in skip:
                        row[i] = ""
                visible = {f.name: f.read_text(encoding="utf-8") for f in fdir.iterdir()}
                visible.pop("key.json")
                visible["graph.json"] = json.dumps(graph)
                visible["labels.csv"] = "\n".join(",".join(r) for r in rows)
                for fname, text in visible.items():
                    for name in sorted(names):
                        self.assertNotIn(name, text, f"{micro_name}/{fname}")

    def test_verilog_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            build(micro("bm_DL_4_bit_comparator"), out)
            text = (out / "d" / "f2" / "netlist.v").read_text(encoding="utf-8")
        idents = set(re.findall(r"[A-Za-z_][A-Za-z0-9_$]*", re.sub(r"\d+'[bdh]\w+", "", text)))
        extra = {i for i in idents - KEYWORDS - {"top"} if not re.fullmatch(r"n\d+", i)}
        self.assertEqual(extra, set())

    def test_constant_only_design(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            res = build(DATA / "zero.v", out)
            self.assertEqual(res.status, "ok", res.reason)
            graph = load(out, "graph.json")
            self.assertEqual(validate_graph(graph), [])
            kinds = sorted(n["kind"] for n in graph["nodes"])
            self.assertEqual(kinds, ["const", "po"])
            self.assertEqual(res.equiv["anon"].status, "equivalent")
            rows = (out / "d" / "f2" / "labels.csv").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(rows) - 1, 2)

    def test_parse_failure_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            res = build(DATA / "sv_always_comb.v", out)
            self.assertEqual(res.status, "skipped")
            self.assertTrue(res.reason.startswith("odin3:"), res.reason)
            self.assertFalse((out / "d" / "f2").exists())
            skipped = load(out, "skipped.json", floor="")
            self.assertEqual(skipped["floors"], {"f2": res.reason})
            self.assertNotIn(str(DATA), res.reason)

    def test_floor_result_change_clears_the_other_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            self.assertEqual(build(micro("bm_DL_4_bit_comparator"), out).status, "ok")
            self.assertEqual(build(DATA / "sv_always_comb.v", out).status, "skipped")
            self.assertFalse((out / "d" / "f2").exists())
            self.assertIn("f2", load(out, "skipped.json", floor="")["floors"])
            self.assertEqual(build(micro("bm_DL_4_bit_comparator"), out).status, "ok")
            self.assertFalse((out / "d" / "skipped.json").exists())
            self.assertTrue((out / "d" / "f2" / "graph.json").is_file())

    def test_main_exit_codes_and_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dataset"
            arch = str(f2_arch())
            argv = ["--design", "d", "--files", str(DATA / "sv_always_comb.v"), "--top", "",
                    "--arch-xml", arch, "--floors", "f2", "--out", str(out)]
            self.assertEqual(main(argv), 0)
            metrics = json.loads((Path(tmp) / "metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(metrics["skipped_floors"], 1)
            argv[3] = str(micro("bm_DL_4_bit_comparator"))
            self.assertEqual(main(argv), 0)
            metrics = json.loads((Path(tmp) / "metrics.json").read_text(encoding="utf-8"))
            self.assertEqual((metrics["luts"], metrics["equiv_bad"]), (5, 0))

    def test_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
            for tmp in (t1, t2):
                self.assertEqual(build(micro("bm_DL_4_bit_comparator"), Path(tmp)).status, "ok")
            for name in FILES:
                a = (Path(t1) / "d" / "f2" / name).read_bytes()
                b = (Path(t2) / "d" / "f2" / name).read_bytes()
                self.assertEqual(a, b, name)

    def test_unmatched_counted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            res = build(micro("bm_DL_4_bit_comparator"), out)
            rows = list(csv.DictReader((out / "d" / "f2" / "labels.csv").open(newline="")))
            empty = [r for r in rows if r["kind"] not in ("pi", "po") and r["construct_type"] == ""]
            self.assertEqual(len(empty), res.unmatched)


if __name__ == "__main__":
    unittest.main()
