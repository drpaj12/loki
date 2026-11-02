"""Paths and constants of Q-L9 (reuses ql6-grow, ql7-stop, ql8b-anchors and ql8c-kind by import)."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "ql8b-anchors"))  # q8b_env also puts ql7-stop and ql6-grow
sys.path.insert(0, str(HERE.parent / "ql8c-kind"))


def mod(name: str) -> Any:
    return importlib.import_module(name)


q8benv = mod("q8b_env")
q7env = q8benv.q7env
q6env = q8benv.q6env
q8env = mod("q8_env")
KINDS: tuple[str, ...] = q6env.KINDS
KINDS5: tuple[str, ...] = q8benv.KINDS5
GLUE = KINDS.index("glue")
CELLS: tuple[str, ...] = q8benv.CELLS
TARGETS: dict[str, tuple[str, ...]] = q8benv.TARGETS
l3dlib = q6env.l3dlib
RES = HERE / "results"
OUT9 = Path(os.environ.get("QL9_OUT", str(q6env.WS / "work" / "ql9-out")))
OUT8B: Path = q8benv.OUT8  # where the #77 paths of TRAIN and VALIDATION are regrown here
PREV8B = q6env.WS / "work" / "ql8-out" / "b"  # #77's own TEST paths, read only
OUT6: Path = q6env.OUT
CAP = q7env.CAP
VARIANT = "bank+loop+const"
MAX_MERGES = 50
FIX_ROUNDS = 3
MIN_SIDE = 4
MIN_SPLIT = 8
