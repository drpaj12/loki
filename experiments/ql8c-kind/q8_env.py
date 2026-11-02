"""Paths, sets and constants of Q-L8c (reuses experiments/ql6-grow and ql7-stop by import)."""

from __future__ import annotations

import hashlib
import importlib
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "ql7-stop"))  # q7_env sets QL6_NOSTOP and the ql6 path


def mod(name: str) -> Any:
    return importlib.import_module(name)


q7env = mod("q7_env")
q6env = q7env.q6env
KINDS: tuple[str, ...] = q6env.KINDS
KINDS5 = tuple(k for k in KINDS if k != "glue")
GLUE = KINDS.index("glue")
CELLS: tuple[str, ...] = q7env.CELLS
l3dlib = q7env.l3dlib
RES = HERE / "results"
OUT8 = Path(os.environ.get("QL8C_OUT", str(q6env.WS / "work" / "ql8-out" / "c")))
OUT7: Path = q7env.OUT7
OUT6: Path = q7env.OUT6
SETS = ("FIT", "CAL", "VAL", "TEST")
TARGETS = {"gate": ("O-gate", "Y-gate"), "k4": ("O-lut", "Y-lut"), "k6/hardmap": ("O-hard",)}


def design_set(design: str, tune: bool = True) -> str:
    """FIT (even MD5 half of TUNE), CAL (#74 TRAIN) or VAL (#74 VALIDATION) for a TUNE design."""
    h = int(hashlib.md5(design.encode()).hexdigest(), 16)
    if h % 2 == 0:
        return "FIT"
    return "CAL" if (h // 2) % 2 == 0 else "VAL"
