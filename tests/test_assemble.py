import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any

from loki.assemble import DesignEntry, assemble, build_manifest, check_dataset
from loki.schemas import dump_json, split_of, validate_manifest
from tests.helpers import write_fake_floor

K6 = "k6_frac_N10_frac_chain_mem32K_40nm"
SCHEMA = (
    "CREATE TABLE runs (key TEXT PRIMARY KEY, design TEXT, arch TEXT, recipe TEXT, params TEXT, "
    "status TEXT, started TEXT, ended TEXT, run_dir TEXT)"
)


def designs_of(manifest: dict[str, object]) -> list[Any]:
    designs = manifest["designs"]
    assert isinstance(designs, list)
    return designs


class Project:
    """A fake finished Wyrd project under a temporary directory."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.rows: list[tuple[str, str, str, str, str]] = []

    def add_run(self, design: str, arch: str, status: str, floors: list[str]) -> Path:
        key = f"{design}-{arch}-{status}"
        run_dir = self.root / "runs" / design / arch / key
        dataset = run_dir / "0-loki-dataset" / "dataset"
        for floor in floors:
            write_fake_floor(dataset, design, floor)
        (dataset / design).mkdir(parents=True, exist_ok=True)
        spec = self.root / "designs" / design
        spec.mkdir(parents=True, exist_ok=True)
        (spec / "design.json").write_text(
            dump_json({
                "schema": 1, "design": design, "benchmark": "micro", "top": None,
                "files": [{"path": f"{design}.v", "sha256": "00"}],
                "source": {"url": "u", "commit": "c", "license": "MIT"},
            }),
            encoding="utf-8",
        )
        self.rows.append((key, design, arch, status, str(run_dir)))
        return dataset / design

    def save(self) -> Path:
        con = sqlite3.connect(self.root / "wyrd.db")
        con.execute(SCHEMA)
        con.executemany(
            "INSERT INTO runs (key, design, arch, status, run_dir) VALUES (?,?,?,?,?)", self.rows
        )
        con.commit()
        con.close()
        return self.root


class AssembleTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.proj = Project(self.tmp / "proj")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_assemble_copies_ok_runs_only(self) -> None:
        self.proj.add_run("micro_a", K6, "ok", ["f1-k6", "f2"])
        self.proj.add_run("micro_b", K6, "fail", ["f2"])
        out = self.tmp / "dataset"
        manifest = assemble(self.proj.save(), out)
        self.assertTrue((out / "micro_a" / "f2" / "graph.json").is_file())
        self.assertFalse((out / "micro_b").exists())
        names = {d["design"]: d for d in designs_of(manifest)}
        self.assertEqual(names["micro_b"]["floors"]["f2"]["status"], "fail")
        self.assertEqual(check_dataset(out), [])

    def test_f2_from_first_arch(self) -> None:
        earch = self.proj.add_run("micro_a", "EArch", "ok", ["f1-earch", "f2"])
        (earch / "f2" / "from.txt").write_text("EArch", encoding="utf-8")
        self.proj.add_run("micro_a", K6, "ok", ["f1-k6", "f2"])
        out = self.tmp / "dataset"
        manifest = assemble(self.proj.save(), out)
        self.assertEqual((out / "micro_a" / "f2" / "from.txt").read_text(), "EArch")
        floors = designs_of(manifest)[0]["floors"]
        self.assertEqual(sorted(floors), ["f1-earch", "f1-k6", "f2"])
        self.assertEqual(check_dataset(out), [])

    def test_f2_mismatch_reported(self) -> None:
        self.proj.add_run("micro_a", "EArch", "ok", ["f2"])
        other = self.proj.add_run("micro_a", K6, "ok", ["f2"])
        graph = other / "f2" / "graph.json"
        graph.write_text(graph.read_text(encoding="utf-8").replace('"n3"', '"n3 "'), "utf-8")
        with self.assertRaisesRegex(ValueError, "f2 differs between architectures"):
            assemble(self.proj.save(), self.tmp / "dataset")

    def test_manifest_sorted_and_split(self) -> None:
        for name in ("micro_z", "micro_a", "micro_m"):
            self.proj.add_run(name, K6, "ok", ["f2", "f1-k6"])
        manifest = assemble(self.proj.save(), self.tmp / "dataset")
        designs = designs_of(manifest)
        self.assertEqual([d["design"] for d in designs], ["micro_a", "micro_m", "micro_z"])
        for d in designs:
            self.assertEqual(d["split"], split_of(d["design"]))
            self.assertEqual(list(d["floors"]), ["f1-k6", "f2"])
        self.assertEqual(validate_manifest(manifest), [])

    def test_skipped_floor_listed(self) -> None:
        design = self.proj.add_run("micro_a", K6, "ok", ["f1-k6"])
        (design / "skipped.json").write_text(
            json.dumps({"schema": 1, "floors": {"f2": "odin3: ODIN3_ERR_PARSE x"}}), "utf-8"
        )
        manifest = assemble(self.proj.save(), self.tmp / "dataset")
        floors = designs_of(manifest)[0]["floors"]
        self.assertEqual(floors["f2"], {"status": "skipped", "reason": "odin3: ODIN3_ERR_PARSE x"})
        self.assertEqual(floors["f1-k6"]["status"], "ok")
        self.assertEqual(check_dataset(self.tmp / "dataset"), [])

    def test_build_manifest_direct(self) -> None:
        entries = {"ve_b": DesignEntry("verilog-eval", {"f2": {"status": "ok", "nodes": 1}}),
                   "micro_a": DesignEntry("micro")}
        manifest = build_manifest(entries, "1.0.0")
        self.assertIn("sources", manifest)
        self.assertEqual([d["design"] for d in designs_of(manifest)], ["micro_a", "ve_b"])


if __name__ == "__main__":
    unittest.main()
