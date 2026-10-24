"""Loader for the read-only Gate-Breaker metric code (AST Algorithm 2, CFG Algorithm 3).

``work/gatebreaker-exp2/scripts/metrics.py`` (pyverilog AST similarity) and the odin3 CFG probe
(``work/odin3-cfg/tools/cfg-probe/odin3_cfg.py``) are imported from their worktrees without
copying them. The CFG side builds Odin III designs, so callers run it under the heavy lock.
"""

from __future__ import annotations

import importlib
import os
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

SCRIPTS = Path("/home/jamiespa/odin3-ws/work/gatebreaker-exp2/scripts")
PROBE = Path("/home/jamiespa/odin3-ws/work/odin3-cfg/tools/cfg-probe")
CLEAN_DIR = Path("/tmp/claude-1000/le2-ast-clean")
CFG_NODE_LIMIT = 12000


def _load(name: str, path: Path) -> ModuleType:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    return importlib.import_module(name)


def metrics() -> ModuleType:
    return _load("metrics", SCRIPTS)


def cfg_probe() -> ModuleType:
    os.environ.setdefault("ODIN3_LIB", "/home/jamiespa/odin3-ws/odin3/build/release/libodin3.so")
    os.environ.setdefault(
        "ODIN3_SLANG_LIB", "/home/jamiespa/odin3-ws/odin3/build/release/libodin3_slang.so")
    return _load("odin3_cfg", PROBE)


def parse_clean(path: Path, top: str = "") -> Any:
    """pyverilog module of ``path`` after stripping ``(* ... *)`` attributes (metadata)."""
    m = metrics()
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    clean = CLEAN_DIR / f"{path.parent.name}__{path.name}"
    clean.write_text(re.sub(r"\(\*.*?\*\)", "", path.read_text(encoding="utf-8"), flags=re.S),
                     encoding="utf-8")
    return m.parse_module(str(clean), top) if top else m.parse_module(str(clean))


def ast_similarity(ref_mod: Any, cand: Path) -> float:
    return float(metrics().ast_similarity(ref_mod, parse_clean(cand), depth=3))


def cfg_of(binding: Any, path: Path) -> Any:
    probe = cfg_probe()
    design = probe.read_design(binding, path)
    try:
        return probe.design_cfg(design)
    finally:
        design.close()


def cfg_similarity(a: Any, b: Any) -> float:
    n = max(len(a), len(b))
    if n > CFG_NODE_LIMIT:
        raise ValueError(f"skipped: CFG {n} nodes > {CFG_NODE_LIMIT} (Algorithm 3 is O(n^2))")
    return float(cfg_probe().cfg_similarity(a, b))
