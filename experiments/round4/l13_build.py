"""Build one big VTR design into an L0 dataset directory with the equivalence check disabled.

Usage: l13_build.py DESIGN OUT_DIR   (``ODIN3_ROOT``, ``ODIN3_LIB``, ``VTR_ROOT`` set)
Floors f1-k6, f2, f3 as the veval-L0 pipeline. The equivalence checks of ``loki.build`` are replaced
by a result with status ``skipped:big`` (agent default of EXPERIMENT.md: big designs are not
equivalence-checked, as in Odin III); everything else is ``python -m loki.build`` unchanged.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any

from loki.equiv import EquivResult


def _skip(a: str, b: str, odin3_root: Path, match_unnamed: bool) -> EquivResult:
    return EquivResult("skipped:big", 0, "")


def main() -> int:
    design, out = sys.argv[1], sys.argv[2]
    vtr = Path(os.environ["VTR_ROOT"])
    src = vtr / "vtr_flow" / "benchmarks" / "verilog" / f"{design}.v"
    arch = vtr / "vtr_flow" / "arch" / "timing" / "k6_frac_N10_frac_chain_mem32K_40nm.xml"
    lb: Any = importlib.import_module("loki.build")
    lb.check_equiv = _skip
    lb._EQUIV_OK = (*lb._EQUIV_OK, "skipped:big")
    rc: int = lb.main(["--design", f"vtr_{design}", "--files", str(src), "--arch-xml", str(arch),
                    "--floors", "f1-k6,f2,f3", "--out", out])
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
