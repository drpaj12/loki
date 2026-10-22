"""L0 exit test: the micros through floors F2 (and F1) into a checked dataset (spec 11)."""

import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from loki.assemble import assemble, check_dataset
from loki.bench import ODIN3_SOURCE
from loki.build import FloorResult, build_floor
from loki.schemas import dump_json
from tests.helpers import DATA, can_run_flow, have_f3, micro, odin3_root, vtr_arch

K6 = "k6_frac_N10_frac_chain_mem32K_40nm"
SUBSET = (
    "bm_DL_2_1_mux", "bm_DL_4_bit_comparator", "bm_DL_four_bit_adder_continuous_assign",
    "bm_DL_4_bit_shift_register", "bm_DL_Dff_w_synch_reset", "bm_DL_D_flipflop", "bm_my_D_latch1",
    "bm_base_multiply", "bm_DL_74381_ALU", "bm_DL_BCD_adder", "bm_dag1_mod",
)
# No micro holds an FSM that the fsm pass detects (probed): the FSM case is a fixture.
FSM_FIXTURE = DATA / "fsm2.v"
THRESHOLD = 0.95
# The modules Odin III resolves later than the gate-mapping main of d7defba (all unresolved_module).
F3_SKIPS = {"adder_hard_block", "hard_adder_cin_propagation", "multiply_hard_block"}


def sources(names: tuple[str, ...]) -> dict[str, Path]:
    found = {f"micro_{n}": micro(n) for n in names}
    found["micro_fsm2"] = FSM_FIXTURE
    return found


def build_all(
    designs: dict[str, Path], floor: str, root: Path
) -> dict[str, FloorResult]:
    odin = odin3_root()
    assert odin is not None
    return {
        did: build_floor(did, [path], None, floor, vtr_arch(), root, odin)
        for did, path in designs.items()
    }


def assemble_built(designs: dict[str, Path], built: Path, project: Path) -> Path:
    """Wrap build_floor outputs as a finished Wyrd project and assemble it."""
    project.mkdir(parents=True)
    con = sqlite3.connect(project / "wyrd.db")
    con.execute("CREATE TABLE runs (key TEXT, design TEXT, arch TEXT, status TEXT, run_dir TEXT)")
    for did in designs:
        run_dir = project / "runs" / did
        (run_dir / "0-loki-dataset").mkdir(parents=True)
        (run_dir / "0-loki-dataset" / "dataset").symlink_to(built, target_is_directory=True)
        spec = project / "designs" / did
        spec.mkdir(parents=True)
        (spec / "design.json").write_text(
            dump_json({
                "schema": 1, "design": did, "benchmark": "micro", "top": None,
                "files": [{"path": f"{did}.v", "sha256": "00"}],
                "source": {**ODIN3_SOURCE, "commit": "c"},
            }),
            encoding="utf-8",
        )
        con.execute("INSERT INTO runs VALUES (?,?,?,?,?)", (did, did, "k6", "ok", str(run_dir)))
    con.commit()
    con.close()
    out = project / "dataset"
    assemble(project, out)
    return out


def label_ratio(
    built: Path, ids: list[str], floor: str, kinds: tuple[str, ...] = ("lut", "ff")
) -> tuple[int, int]:
    have = total = 0
    for did in ids:
        path = built / did / floor / "labels.csv"
        if not path.is_file():
            continue
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row["kind"] in kinds:
                    total += 1
                    have += row["construct_type"] != ""
    return have, total


def equiv_problems(results: dict[str, FloorResult]) -> list[str]:
    bad = []
    for did, res in results.items():
        for name, eq in res.equiv.items():
            if eq.status != "equivalent":
                bad.append(f"{did}:{name}:{eq.status}")
    return bad


@unittest.skipUnless(can_run_flow() and odin3_root() is not None, "needs Odin III and VTR")
class AcceptanceTest(unittest.TestCase):
    def test_micro_subset_f2(self) -> None:
        designs = sources(SUBSET)
        with tempfile.TemporaryDirectory() as tmp:
            built = Path(tmp) / "built"
            results = build_all(designs, "f2", built)
            for did, res in results.items():
                self.assertEqual((res.status, res.reason), ("ok", ""), did)
            self.assertEqual(equiv_problems(results), [])
            out = assemble_built(designs, built, Path(tmp) / "proj")
            self.assertEqual(check_dataset(out), [])

    def test_all_micros_f2(self) -> None:
        odin = odin3_root()
        assert odin is not None
        names = tuple(p.stem for p in sorted((odin / "tests/micro/verilog/micro").glob("*.v")))
        self.assertEqual(len(names), 68)
        designs = {f"micro_{n}": micro(n) for n in names}
        with tempfile.TemporaryDirectory() as tmp:
            built = Path(tmp) / "built"
            results = build_all(designs, "f2", built)
            failed = {d: r.reason for d, r in results.items() if r.status == "fail"}
            self.assertEqual(failed, {})
            ok = {d: r for d, r in results.items() if r.status == "ok"}
            problems = equiv_problems(ok)
            self.assertEqual(problems, [])
            for did in ok:
                graph_rows = (built / did / "f2" / "labels.csv").read_text().count("\n") - 1
                self.assertEqual(graph_rows, ok[did].counts["nodes"], did)
            have, total = label_ratio(built, list(ok), "f2")
            ratio = have / total if total else 1.0
            print(f"label coverage over lut and ff nodes: {have}/{total} = {ratio:.4f}")
            self.assertGreaterEqual(ratio, THRESHOLD, f"{have}/{total}")
            out = assemble_built(designs, built, Path(tmp) / "proj")
            self.assertEqual(check_dataset(out), [])
            again = Path(tmp) / "again"
            three = {d: designs[d] for d in list(ok)[:3]}
            build_all(three, "f2", again)
            for did in three:
                for f in (built / did / "f2").iterdir():
                    self.assertEqual(f.read_bytes(), (again / did / "f2" / f.name).read_bytes())

    def test_micros_f1_no_differs(self) -> None:
        designs = sources(SUBSET)
        with tempfile.TemporaryDirectory() as tmp:
            results = build_all(designs, f"f1-{K6.split('_')[0]}", Path(tmp))
            allowed = ("equivalent", "unproven", "skipped:blackbox-names")
            for did, res in results.items():
                self.assertIn(res.status, ("ok", "skipped"), (did, res.reason))
                for name, eq in res.equiv.items():
                    self.assertIn(eq.status, allowed, (did, name))


@unittest.skipUnless(have_f3(), "needs Odin III gate mapping")
class AcceptanceF3Test(unittest.TestCase):
    def test_all_micros_f3(self) -> None:
        odin = odin3_root()
        assert odin is not None
        names = tuple(p.stem for p in sorted((odin / "tests/micro/verilog/micro").glob("*.v")))
        self.assertEqual(len(names), 68)
        designs = {f"micro_{n}": micro(n) for n in names}
        with tempfile.TemporaryDirectory() as tmp:
            built = Path(tmp) / "built"
            results = build_all(designs, "f3", built)
            failed = {d: r.reason for d, r in results.items() if r.status == "fail"}
            self.assertEqual(failed, {})
            ok = {d: r for d, r in results.items() if r.status == "ok"}
            skipped = {d: r.reason for d, r in results.items() if r.status == "skipped"}
            print(f"f3: {len(ok)} ok, {len(skipped)} skipped {sorted(set(skipped.values()))}")
            self.assertEqual(equiv_problems(ok), [])
            for did, res in ok.items():
                self.assertEqual(res.counts["lut"], 0, did)
                self.assertEqual(res.counts["hard"], 0, did)
                rows = (built / did / "f3" / "labels.csv").read_text().count("\n") - 1
                self.assertEqual(rows, res.counts["nodes"], did)
            have, total = label_ratio(built, list(ok), "f3", ("gate", "ff"))
            ratio = have / total if total else 1.0
            print(f"f3 label coverage over gate and ff nodes: {have}/{total} = {ratio:.4f}")
            self.assertGreaterEqual(ratio, THRESHOLD, f"{have}/{total}")
            unmatched = 0
            for did in ok:
                meta = json.loads(
                    (built / did / "f3" / "meta.json").read_text(encoding="utf-8")
                )
                unmatched += int(meta["unmatched"])
            self.assertEqual(unmatched, 0)
            reasons = sorted(set(skipped.values()))
            names_skipped = {d.removeprefix("micro_") for d in skipped}
            self.assertTrue(
                names_skipped == F3_SKIPS or len(ok) >= 65, (sorted(names_skipped), reasons)
            )
            if names_skipped == F3_SKIPS:
                for reason in reasons:
                    self.assertIn("unresolved_module", reason)
            out = assemble_built(designs, built, Path(tmp) / "proj")
            self.assertEqual(check_dataset(out), [])
            again = Path(tmp) / "again"
            three = {d: designs[d] for d in list(ok)[:3]}
            build_all(three, "f3", again)
            for did in three:
                for f in (built / did / "f3").iterdir():
                    self.assertEqual(
                        f.read_bytes(), (again / did / "f3" / f.name).read_bytes(), f.name
                    )

    def test_subset_f3_checked_dataset(self) -> None:
        designs = sources(SUBSET)
        with tempfile.TemporaryDirectory() as tmp:
            built = Path(tmp) / "built"
            results = build_all(designs, "f3", built)
            for did, res in results.items():
                self.assertEqual((res.status, res.reason), ("ok", ""), did)
            self.assertEqual(equiv_problems(results), [])
            out = assemble_built(designs, built, Path(tmp) / "proj")
            self.assertEqual(check_dataset(out), [])


if __name__ == "__main__":
    unittest.main()
