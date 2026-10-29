"""Pre-flight: every selected reference, as TopModule, passes its own testbench.

Usage: ``python -I preflight_full.py``. Same check as ``score.py preflight`` over this
``selection.csv``; output under ``run/preflight``.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
fullcfg: Any = importlib.import_module("fullcfg")
score: Any = importlib.import_module("score")

if __name__ == "__main__":
    sys.exit(score.main(["preflight"]))
