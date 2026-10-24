"""Shared runs of ``loki re`` for the ReverseProvenance tests (one run per netlist and options)."""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
from pathlib import Path

from loki.re.main import main
from tests.helpers import DATA

ADD2 = DATA / "re" / "add2.blif"
FSM2 = DATA / "re" / "fsm2.blif"
CALIB = Path(__file__).resolve().parent.parent / "calib" / "f2.json"
_TMP = tempfile.TemporaryDirectory(prefix="lrp-test-")
_CACHE: dict[tuple[str, ...], Path] = {}


def run_re(netlist: Path, *extra: str, tag: str = "") -> Path:
    """The output directory of ``loki re`` on ``netlist`` (calibrated F2), made once per key."""
    key = (str(netlist), tag, *extra)
    if key not in _CACHE:
        out = Path(_TMP.name) / f"run{len(_CACHE)}"
        argv = [str(netlist), "--floor", "f2", "--calib", str(CALIB), "--out", str(out),
                "--odin3-root", os.environ.get("ODIN3_ROOT", ""), *extra]
        with contextlib.redirect_stderr(io.StringIO()):
            code = main(argv)
        if code != 0:
            raise RuntimeError(f"loki re exited {code}")
        _CACHE[key] = out
    return _CACHE[key]


def fsm_run() -> Path:
    """The FSM fixture with a low candidate threshold (its FSM hypotheses stay below 0.5)."""
    return run_re(FSM2, "--rp-min-p", "0.01")
