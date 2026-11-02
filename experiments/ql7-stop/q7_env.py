"""Paths, the split and the constants of Q-L7 (reuses experiments/ql6-grow by import)."""

from __future__ import annotations

import hashlib
import importlib
import os
import sys
from pathlib import Path
from typing import Any

os.environ["QL6_NOSTOP"] = "1"  # the grower of q6_grow is the no-stop variant for every import here
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "ql6-grow"))


def mod(name: str) -> Any:
    return importlib.import_module(name)


q6env = mod("q6_env")
KINDS: tuple[str, ...] = q6env.KINDS
CELLS: tuple[str, ...] = tuple(q6env.CELLS)
l3dlib = q6env.l3dlib
RES = HERE / "results"
OUT7 = Path(os.environ.get("QL7_OUT", str(q6env.WS / "work" / "ql7-out")))
OUT6: Path = q6env.OUT
CAP = 300
MAX_UNIT_CELLS = 400
SPLITS = ("TRAIN", "VALIDATION", "TEST")


def stop_split(design: str) -> str:
    """TRAIN or VALIDATION for a design of the odd (calibration) half of TUNE, else ''."""
    h = int(hashlib.md5(design.encode()).hexdigest(), 16)
    if h % 2 == 0:
        return ""  # even half: trained the #73 likelihood, not used here
    return "TRAIN" if (h // 2) % 2 == 0 else "VALIDATION"


def paths_dir(split: str) -> Path:
    """Directory of the grown paths: TEST reads #73's variant output (read only)."""
    return OUT6 / "blocks_nostop" if split == "TEST" else OUT7 / "paths"
