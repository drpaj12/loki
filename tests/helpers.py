"""Shared test helpers: Odin III availability and location."""

from __future__ import annotations

import importlib
import os
from pathlib import Path


def odin_available() -> bool:
    """True when the odin3 module imports and the shared library loads."""
    try:
        mod = importlib.import_module("odin3")
        mod.Odin3()
    except Exception:
        return False
    return True


def odin3_root() -> Path | None:
    """The Odin III checkout from $ODIN3_ROOT, or None when it lacks equiv-check."""
    raw = os.environ.get("ODIN3_ROOT")
    if not raw:
        return None
    root = Path(raw)
    if not (root / "tools" / "equiv-check" / "equiv-check").is_file():
        return None
    return root
