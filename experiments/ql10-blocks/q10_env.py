"""Paths and imports of Q-L10 (reuses ql9-join, ql8b-anchors, ql6-grow and llm-pilot by import).

Environment: ODIN3_ROOT / ODIN3_LIB / PYTHONPATH as in ql9-out/env.sh; QL10_OUT is the run root
(default <workspace>/work/ql10-out); QL6_OUT and QL8C_OUT point at the #73 model and the #75 M2
models (read only).
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
for _sub in ("ql9-join", "ql8b-anchors", "ql8c-kind", "llm-pilot", "llm-full"):
    sys.path.insert(0, str(EXP / _sub))


def mod(name: str) -> Any:
    return importlib.import_module(name)


q9env = mod("q9_env")
q6env = q9env.q6env
WS: Path = q6env.WS
RUN = Path(os.environ.get("QL10_OUT", str(WS / "work" / "ql10-out")))
RES = HERE / "results"
CELL = "O-gate"  # the cell class (target) of the models: gate-level netlists
FULL_RUN = Path(os.environ.get("QL10_FULL_RUN", str(WS / "work" / "ql10-out" / "full-run")))
JOIN_T = 0.2  # the #78 headline join: JCOND at 0.2
MAX_BLOCK_CELLS = 300  # q9_env.CAP
MIN_CLAIM = 4  # a kind guess is made only for a block of 4 cells or more (as #74, #75, #78)
SEED = "yggdrasil-ql10-20261102"
