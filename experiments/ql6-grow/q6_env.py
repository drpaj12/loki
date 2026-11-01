"""Paths and imports shared by the Q-L6 scripts (reuses the #68 to #72 experiment code)."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
RES = HERE / "results"
for _sub in (HERE, EXP / "ql4-misses", EXP / "graphlets", EXP / "l3-detector"):
    sys.path.insert(0, str(_sub))


def mod(name: str) -> Any:
    return importlib.import_module(name)


bl = mod("blocks")
l3dlib = mod("l3dlib")
sigs = mod("sigs")
WS = l3dlib.WS
OUT = Path(os.environ.get("QL6_OUT", str(WS / "work" / "ql6-out")))
CELLS = l3dlib.CELLS
KINDS = ("fsm", "counter", "shift", "regfile", "register", "glue")
# composite parts merge timer into counter and lfsr into shift, as in #69 to #72
MERGE = {"timer": "counter", "lfsr": "shift"}
