"""Q-L12 lut4: the ql12-k4k6 machinery pointed at a four-input LUT endpoint (no model call).

Import this module FIRST. It imports ``q12_env`` of ``../ql12-k4k6`` (unchanged) and, before any
other ``q12_*`` module is used, sets in that module: ``ENDPOINTS`` to the one endpoint ``lut4``
(cell class ``O-lut``, floor ``f2``, the cell class the grow model of Q-L12 knows for soft-logic
LUT netlists), ``HERE`` and ``RES`` to this directory (outputs, ``designs.json``) and ``CENSUS``
to the netlist tree built by ``l4_census.py``. The prompt templates are still read from
``ql12-k4k6`` (``q12_render.template``), so the frozen prompts are those files, not copies.
Run root: ``$QL12_OUT`` (default ``<workspace>/work/ql12l4-out``).
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
K46 = HERE.parent / "ql12-k4k6"
sys.path.insert(0, str(K46))
os.environ.setdefault("QL12_OUT", str(HERE.parents[2] / "work" / "ql12l4-out"))
os.environ.setdefault("QL12_CENSUS", str(Path(os.environ["QL12_OUT"]) / "census-ve"))

env: Any = importlib.import_module("q12_env")
env.ENDPOINTS = {"lut4": ("O-lut", "f2")}
env.HERE = HERE
env.RES = HERE / "results"
EP = "lut4"
FROZEN = {
    "block_prompt_lut.txt": "cbacc5394283bbc8147f7cfd80c8e6393028dcf1a40e338012d459b7783de93e",
    "a_prompt_lut.txt": "7639439931d2f2aea16f007746bb244ac7530b1d3690850d89f93e95376d61cb"}


def _frozen_template(name: str) -> str:
    return (K46 / name).read_text(encoding="utf-8")


rn: Any = importlib.import_module("q12_render")
rn.template = _frozen_template
