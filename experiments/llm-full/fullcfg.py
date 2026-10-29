"""Point the pilot modules at the llm-full directory (no copies of pilot code).

Import this module first (it sets ``LLM_PILOT_VARIANT=re`` before ``common`` is read, then patches
``common.HERE``, ``common.run_dir``, ``common.hints_root`` and ``common.system_msg``). The pilot
scripts (``make_hints``, ``build_prompts``, ``collect``, ``score``, ``pick_designs``) then read
``selection.csv`` from here and write under ``llm-full/run``. The ``re`` system message is still
read from the pilot's ``prompts_variants/re/system.txt``; ``build_full.py`` checks its md5.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any

os.environ["LLM_PILOT_VARIANT"] = "re"
FULL = Path(__file__).resolve().parent
PILOT = FULL.parent / "llm-pilot"
sys.path.insert(0, str(PILOT))
common: Any = importlib.import_module("common")

RUN = Path(os.environ.get("LLM_FULL_RUN", str(FULL / "run")))
DRAWS = (1, 2, 3)
common.HERE = FULL


def _system_msg() -> str:
    return (PILOT / "prompts_variants" / "re" / "system.txt").read_text(encoding="utf-8")


common.run_dir = lambda: RUN
common.hints_root = lambda: RUN
common.system_msg = _system_msg
