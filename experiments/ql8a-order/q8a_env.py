"""Paths, orders and constants of Q-L8a (reuses experiments/ql6-grow and ql7-stop by import)."""

from __future__ import annotations

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
CELLS: tuple[str, ...] = q7env.CELLS
l3dlib = q7env.l3dlib
RES = HERE / "results"
OUT8 = Path(os.environ.get("QL8A_OUT", str(q6env.WS / "work" / "ql8-out" / "a")))
OUT7: Path = q7env.OUT7
OUT6: Path = q7env.OUT6
CAP = q7env.CAP
MAX_UNIT_CELLS = q7env.MAX_UNIT_CELLS
ORDERS = ("E74", "OA", "OB", "OC")
CANDIDATES = ("OA", "OB", "OC")
TARGETS = {"gate": ("O-gate", "Y-gate"), "k4": ("O-lut", "Y-lut"), "k6/hardmap": ("O-hard",)}


def paths_dir(order: str, split: str) -> Path:
    """Grown paths of an order. E74 reads #74's own paths (TEST: #73 blocks_nostop), read only."""
    if order == "E74":
        return Path(q7env.paths_dir(split))
    return Path(OUT8 / f"paths_{order}" / split)
