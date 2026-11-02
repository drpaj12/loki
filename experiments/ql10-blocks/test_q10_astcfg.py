"""The numpy kernel of q10_astcfg equals the probe's pure-Python kernel (needs Odin III; skipped
without it): ``python -m unittest test_q10_astcfg`` from this directory."""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))


class FastKernelTest(unittest.TestCase):
    def test_equals_probe(self) -> None:
        try:
            ac: Any = importlib.import_module("q10_astcfg")
            _m, cfg = ac.load_tools()
            sc = ac.Scorer()
            names = sorted(ac.REFS.glob("Prob00*_ref.sv"))[:6]
            graphs = [sc.cfg_of(f, "RefModule") for f in names]
        except Exception as err:  # environment not set up: nothing to compare
            self.skipTest(str(err))
        self.assertTrue(graphs)
        for i, a in enumerate(graphs):
            for b in graphs[i:]:
                self.assertAlmostEqual(ac.fast_similarity(cfg, a, b), cfg.cfg_similarity(a, b),
                                       places=9)


if __name__ == "__main__":
    unittest.main()
