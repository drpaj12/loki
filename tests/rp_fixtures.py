"""Shared runs of ``loki re`` for the ReverseProvenance tests (one run per netlist and options)."""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
from pathlib import Path
from typing import Any

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


def normalised(rp: dict[str, Any]) -> dict[str, Any]:
    """``rp`` with the machine- and version-specific header fields fixed (for stored copies)."""
    out: dict[str, Any] = json.loads(json.dumps(rp))
    head = out["header"]
    head["loki"] = head["odin3"] = "test"
    head["input"]["path"] = head["input"]["name"]
    if head["calib"]["name"] is not None:
        head["calib"]["path"] = head["calib"]["name"]
    return out


def golden() -> dict[str, Any]:
    """The stored ``reverse-provenance.json`` of ``ADD2`` (see ``normalised``)."""
    path = Path(__file__).parent / "data" / "rp" / "add2.reverse-provenance.json"
    obj: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return obj
