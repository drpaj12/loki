import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from loki.analysis.partition import load_partition
from loki.cli import main as loki_main
from loki.rp.l2 import JoinError, add_l2, build_l2
from loki.schemas import validate_reverse_provenance
from tests.helpers import can_run_f2
from tests.rp_fixtures import ADD2, run_re

FILE = "reverse-provenance.json"


def partition(node_ids: list[str], assignment: list[int]) -> dict[str, object]:
    return {
        "schema": 1, "kind": "partition", "design": "add2", "floor": "f2", "method": "kmeans",
        "params": {"k": 2}, "seed": 0, "graph_sha256": "ab" * 32, "n_nodes": len(node_ids),
        "n_clusters": max(assignment) + 1, "node_ids": node_ids, "assignment": assignment,
        "quality": {}, "versions": {"numpy": "1"}, "sampled": None, "components": None,
    }


def write(path: Path, obj: dict[str, object]) -> Path:
    path.write_text(json.dumps(obj), encoding="utf-8")
    return path


@unittest.skipUnless(can_run_f2(), "needs Odin III, ABC and an F2 architecture")
class AddL2Test(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name) / "re"
        shutil.copytree(run_re(ADD2), self.dir)

    def test_merge(self) -> None:
        # add2 cells n10 n11 n12 (adder) and n13 (ff); ports a0 y0 are not cells
        part = write(Path(self.tmp.name) / "p.json",
                     partition(["n10", "n11", "n12", "n13", "a0", "y0"], [0, 0, 1, 1, 0, 1]))
        add_l2(self.dir, part)
        rp = json.loads((self.dir / FILE).read_text(encoding="utf-8"))
        self.assertEqual(validate_reverse_provenance(rp), [])
        l2 = rp["l2"]
        self.assertEqual(l2["method"], "kmeans")
        self.assertEqual(l2["partition"]["port_nodes"], 2)
        c0, c1 = l2["clusters"]["0"], l2["clusters"]["1"]
        self.assertEqual(c0["cells"], ["n10", "n11"])
        self.assertEqual(c0["overlap"][0]["module"], "adder_h1")
        self.assertEqual(c0["overlap"][0]["cells_in_common"], 2)
        self.assertEqual(c0["overlap"][0]["fraction_of_module"], 0.666667)
        self.assertEqual(c1["cells_outside_committed"], 1)
        self.assertEqual(l2["cells_unclustered"], 0)

    def test_merge_twice_replaces(self) -> None:
        part = write(Path(self.tmp.name) / "p.json", partition(["n10", "n13"], [0, 1]))
        add_l2(self.dir, part)
        first = (self.dir / FILE).read_bytes()
        add_l2(self.dir, part)
        self.assertEqual((self.dir / FILE).read_bytes(), first)

    def test_join_failure(self) -> None:
        part = write(Path(self.tmp.name) / "p.json", partition(["n10", "x99", "x98"], [0, 0, 1]))
        before = (self.dir / FILE).read_bytes()
        rp = json.loads(before)
        with self.assertRaises(JoinError) as ctx:
            build_l2(rp, load_partition(part), "p.json")
        self.assertIn("x99", str(ctx.exception))
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = loki_main(["rp", "add-l2", str(self.dir), str(part)])
        self.assertEqual(code, 2)
        self.assertIn("not joining by guess", err.getvalue())
        self.assertEqual((self.dir / FILE).read_bytes(), before)

    def test_unjoined_port_ids_accepted_when_cells_complete(self) -> None:
        ids = ["n10", "n11", "n12", "n13", *[f"p{i}" for i in range(8)]]
        part = write(Path(self.tmp.name) / "p.json", partition(ids, [0, 0, 1, 1, *[0] * 8]))
        add_l2(self.dir, part)
        rp = json.loads((self.dir / FILE).read_text(encoding="utf-8"))
        self.assertEqual(rp["l2"]["partition"]["unjoined_nodes"], 8)
        self.assertEqual(rp["l2"]["partition"]["port_nodes"], 0)

    def test_unjoined_ids_refused_when_count_differs_or_cells_missing(self) -> None:
        few = ["n10", "n11", "n12", "n13", "p0", "p1"]
        part = write(Path(self.tmp.name) / "p.json", partition(few, [0, 0, 1, 1, 0, 0]))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(loki_main(["rp", "add-l2", str(self.dir), str(part)]), 2)
        short = ["n10", "n11", *[f"p{i}" for i in range(8)]]
        part = write(Path(self.tmp.name) / "q.json", partition(short, [0, 1, *[0] * 8]))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(loki_main(["rp", "add-l2", str(self.dir), str(part)]), 2)

    def test_ports_only_fails(self) -> None:
        part = write(Path(self.tmp.name) / "p.json", partition(["a0", "y0"], [0, 1]))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(loki_main(["rp", "add-l2", str(self.dir), str(part)]), 2)

    def test_missing_input_exit_3(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            code = loki_main(["rp", "add-l2", str(self.dir / "nope"), str(self.dir / "p.json")])
        self.assertEqual(code, 3)


if __name__ == "__main__":
    unittest.main()
