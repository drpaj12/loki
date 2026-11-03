"""Paths and imports of Q-L12 (reuses ql10-blocks, ql9-join, ql6-grow and llm-pilot by import).

Environment: as ql10-blocks (ODIN3_ROOT, ODIN3_LIB, PYTHONPATH, QL6_OUT, QL9_OUT ...); QL12_OUT is
the run root (default <workspace>/work/ql12-out); QL12_CENSUS is the l3-census build tree with the
Odin III netlists of the VerilogEval references (default <workspace>/work/l3-out/build; read only).
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "ql10-blocks"))

q10_env: Any = importlib.import_module("q10_env")  # puts the ql9, ql8, ql6, llm dirs on sys.path
WS: Path = q10_env.WS
RUN = Path(os.environ.get("QL12_OUT", str(WS / "work" / "ql12-out")))
CENSUS = Path(os.environ.get("QL12_CENSUS", str(WS / "work" / "l3-out" / "build")))
RES = HERE / "results"
# endpoint -> (census cell class, floor directory)
ENDPOINTS: dict[str, tuple[str, str]] = {"k4": ("O-lut", "f2"), "k6": ("O-hard", "f1-k6")}
MAX_BLOCK_CELLS = q10_env.MAX_BLOCK_CELLS
JOIN_T = q10_env.JOIN_T
SEED = "yggdrasil-ql12-20261103"
DRAWS = (1, 2, 3)
BATCH = 24
A_CAP_BYTES = 40000  # the pilot and full run cap on a dataset prompt (cost cap, not a window)


def mod(name: str) -> Any:
    return importlib.import_module(name)
