"""Paths and imports of Q-L11 (reuses ql10-blocks, llm-pilot and llm-full by import; no model call).

Environment as ql10-out/env.sh: ODIN3_ROOT, ODIN3_LIB (rel-main2 build), PYTHONPATH with the odin3
Python plugin. QL10_OUT is the Q-L10 run root (read only); QL11_OUT holds this lane's scratch and
the extracted hints2 replies.
"""

from __future__ import annotations

import os
import sys
from typing import Any
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
RES = HERE / "results"
for _sub in ("ql10-blocks", "ql9-join", "ql8b-anchors", "ql8c-kind", "ql6-grow", "ql4-misses",
             "graphlets", "l3-detector", "llm-pilot", "llm-full", "llm-hints2", "f3-recovery/tools",
             "round2"):
    sys.path.insert(0, str(EXP / _sub))
WS = Path(os.environ.get("ODIN3_WS", str(Path(__file__).resolve().parents[4])))
OUT10 = Path(os.environ.get("QL10_OUT", str(WS / "work" / "ql10-out")))
OUT11 = Path(os.environ.get("QL11_OUT", str(WS / "work" / "ql11-out")))
H2 = OUT11 / "h2" / "run" / "responses"
FULL = OUT10 / "llmfull" / "run" / "responses"
REFS = WS / "external" / "verilog-eval" / "dataset_spec-to-rtl"
SEED = 20261103
BOOT = 2000


def mod_collect() -> Any:
    import importlib
    return importlib.import_module("collect")
