"""Point the pilot modules at the llm-hints2 directory (no copies of pilot code).

Same mechanism as ``llm-full/fullcfg.py``: import this module first. It sets
``LLM_PILOT_VARIANT=re``, then patches ``common.HERE`` (so ``selection.csv`` is the 64-problem
Q3+Q4 file here), ``common.run_dir``, ``common.hints_root`` and ``common.system_msg``.
``RUN`` can be moved with ``LLM_HINTS2_RUN`` (keep it outside a worktree you may remove).
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any

os.environ["LLM_PILOT_VARIANT"] = "re"
H2 = Path(__file__).resolve().parent
PILOT = H2.parent / "llm-pilot"
FULL = H2.parent / "llm-full"
sys.path.insert(0, str(PILOT))
common: Any = importlib.import_module("common")

RUN = Path(os.environ.get("LLM_HINTS2_RUN", str(H2 / "run")))
DRAWS = (1, 2, 3)
common.HERE = H2


def _system_msg() -> str:
    return (PILOT / "prompts_variants" / "re" / "system.txt").read_text(encoding="utf-8")


common.run_dir = lambda: RUN
common.hints_root = lambda: RUN
common.system_msg = _system_msg
