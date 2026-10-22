import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from loki.assemble import DesignEntry, build_manifest, check_dataset
from loki.schemas import dump_json
from tests.helpers import write_fake_floor


def make_dataset(root: Path) -> Path:
    write_fake_floor(root, "micro_a", "f2")
    (root / "micro_a" / "design.json").write_text(
        dump_json({
            "schema": 1, "design": "micro_a", "benchmark": "micro", "top": None,
            "files": [{"path": "micro_a.v", "sha256": "00"}],
            "source": {"url": "u", "commit": "c", "license": "MIT"},
        }),
        encoding="utf-8",
    )
    entries = {"micro_a": DesignEntry("micro", {"f2": {"status": "ok", "nodes": 4}})}
    (root / "manifest.json").write_text(dump_json(build_manifest(entries, "1.0.0")), "utf-8")
    return root


def edit_json(path: Path, change: Any) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(dump_json(data), encoding="utf-8")


class CheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = make_dataset(Path(self._tmp.name))
        self.floor = self.root / "micro_a" / "f2"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def errors(self) -> str:
        return "\n".join(check_dataset(self.root))

    def test_clean_dataset(self) -> None:
        self.assertEqual(check_dataset(self.root), [])

    def test_renamed_node_id(self) -> None:
        edit_json(self.floor / "graph.json", lambda g: g["nodes"][0].update(id="n99"))
        self.assertIn("edge endpoint 'n3' is not a node", self.errors())

    def test_edge_to_missing_node(self) -> None:
        edit_json(self.floor / "graph.json", lambda g: g["edges"][0].update(dst="n77"))
        self.assertIn("n77", self.errors())

    def test_original_name_in_blif(self) -> None:
        blif = self.floor / "netlist.blif"
        blif.write_text(blif.read_text(encoding="utf-8").replace("n0", "A[0]"), "utf-8")
        self.assertIn("'A[0]' is not n<k>", self.errors())

    def test_key_missing_a_net(self) -> None:
        edit_json(self.floor / "key.json", lambda k: k["nets"].pop("n0"))
        self.assertIn("not in key.json", self.errors())

    def test_missing_labels_row(self) -> None:
        path = self.floor / "labels.csv"
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        path.write_text("".join(lines[:-1]), encoding="utf-8")
        self.assertIn("node ids of graph.json and labels.csv differ", self.errors())

    def test_design_dir_not_in_manifest(self) -> None:
        (self.root / "micro_extra").mkdir()
        self.assertIn("micro_extra: design directory is not in the manifest", self.errors())

    def test_wrong_split(self) -> None:
        def flip(m: Any) -> None:
            d = m["designs"][0]
            d["split"] = "test" if d["split"] == "train" else "train"

        edit_json(self.root / "manifest.json", flip)
        self.assertIn("differs from the split rule", self.errors())

    def test_missing_hdl_on_labelled_node(self) -> None:
        def strip(g: Any) -> None:
            labs = g["nodes"][0]["labels"]
            labs.update(construct_type="$eq", role="datapath", hdl_file="", hdl_line=-1)

        edit_json(self.floor / "graph.json", strip)
        path = self.floor / "labels.csv"
        self.assertIn("no hdl_file or hdl_line", self.errors())
        self.assertTrue(path.is_file())

    def test_unknown_key_in_graph(self) -> None:
        edit_json(self.floor / "graph.json", lambda g: g.update(extra=1))
        self.assertIn("unknown key 'extra'", self.errors())


if __name__ == "__main__":
    unittest.main()
