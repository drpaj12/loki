"""Unit tests of Q-L12 lut4 (frozen prompts, K=4 floor script, subset rule, k4k6 untouched)."""

from __future__ import annotations

import hashlib
import importlib
import sys
import unittest
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

l4: Any = importlib.import_module("l4_env")
cen: Any = importlib.import_module("l4_census")
calls: Any = importlib.import_module("l4_calls")


class TestLut4(unittest.TestCase):
    def test_endpoint_set(self) -> None:
        self.assertEqual(l4.env.ENDPOINTS, {"lut4": ("O-lut", "f2")})
        self.assertEqual(l4.env.HERE, HERE)

    def test_frozen_prompts_hold(self) -> None:
        for name, want in l4.FROZEN.items():
            self.assertEqual(hashlib.sha256((l4.K46 / name).read_bytes()).hexdigest(), want)
        self.assertFalse((HERE / "block_prompt_lut.txt").exists())  # read from ql12-k4k6, no copy

    def test_templates_read_from_k4k6(self) -> None:
        rn: Any = importlib.import_module("q12_render")
        self.assertEqual(rn.template("a_prompt_lut.txt"),
                         (l4.K46 / "a_prompt_lut.txt").read_text(encoding="utf-8"))

    def test_floor_script_k4(self) -> None:
        front, mapping = cen.floor_script_k4("f2", [Path("x.v")], Path("a.xml"), None)
        self.assertTrue(mapping.endswith("abc --lut 4"))
        self.assertIn("read_arch", front)
        with self.assertRaises(ValueError):
            cen.floor_script_k4("f1-k6", [Path("x.v")], Path("a.xml"), None)

    def test_subset_rule(self) -> None:
        cs = [{"arm": "A", "n_blocks": 300}, {"arm": "D", "n_blocks": 64},
              {"arm": "D", "n_blocks": 65}]
        self.assertEqual(calls.subset(cs), cs[:2])


if __name__ == "__main__":
    unittest.main()
