"""L2 Task 1: optional extras, the analysis package skeleton and the shared fixtures."""

from __future__ import annotations

import importlib
import json
import re
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from loki.analysis import MissingExtra, require
from loki.schemas import split_of, validate_graph, validate_manifest
from tests.analysis_fixtures import make_dataset, make_graph

ROOT = Path(__file__).resolve().parent.parent


def _extra_names(extras: dict[str, list[str]], name: str, seen: tuple[str, ...] = ()) -> set[str]:
    """The requirement names of an extra, expanding ``loki[...]`` self references."""
    if name in seen:
        return set()
    names: set[str] = set()
    for dep in extras[name]:
        match = re.match(r"[A-Za-z0-9_.-]+", dep)
        if match is None:
            continue
        req = match.group(0).lower()
        if req != "loki":
            names.add(req)
            continue
        inner = re.search(r"\[([^\]]+)\]", dep)
        for part in inner.group(1).split(",") if inner else ():
            names |= _extra_names(extras, part.strip(), (*seen, name))
    return names


class AnalysisPkgTest(unittest.TestCase):
    def test_require_missing_extra_message(self) -> None:
        real = importlib.import_module

        def fake(name: str, package: str | None = None) -> object:
            if name == "sklearn":
                raise ImportError("sklearn is not installed")
            return real(name, package)

        with (
            mock.patch("importlib.import_module", side_effect=fake),
            self.assertRaises(MissingExtra) as ctx,
        ):
            require("analysis")
        self.assertIn("loki[analysis]", str(ctx.exception))

    def test_extras_declared(self) -> None:
        with (ROOT / "pyproject.toml").open("rb") as fh:
            extras = tomllib.load(fh)["project"]["optional-dependencies"]
        analysis = _extra_names(extras, "analysis")
        gnn = _extra_names(extras, "gnn")
        dev = _extra_names(extras, "dev")
        self.assertLessEqual({"numpy", "scipy", "scikit-learn", "networkx"}, analysis)
        self.assertLessEqual({"torch", "torch_geometric"} | analysis, gnn)
        self.assertLessEqual(analysis | gnn, dev)

    def test_fixture_graph_valid(self) -> None:
        self.assertEqual(validate_graph(make_graph()), [])
        self.assertEqual(validate_graph(make_graph(labels=False)), [])

    def test_fixture_dataset_manifest_split(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_dataset(Path(tmp), designs=6)
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_manifest(manifest), [])
        self.assertEqual(len(manifest["designs"]), 6)
        for entry in manifest["designs"]:
            self.assertEqual(entry["split"], split_of(entry["design"]))


if __name__ == "__main__":
    unittest.main()
