"""Run Odin III's equiv-check on two BLIF texts (spec 9)."""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

TIMEOUT_SECONDS = 300
_STATUS = {0: "equivalent", 1: "differs", 4: "unproven", 2: "error", 5: "error"}


@dataclass(frozen=True)
class EquivResult:
    status: str
    tool_exit: int
    detail: str


def _classify(code: int, output: str) -> str:
    if code == 2 and "cannot name black box" in output:
        return "skipped:blackbox-names"
    return _STATUS.get(code, "error")


def check_equiv(a: str, b: str, odin3_root: Path, match_unnamed: bool) -> EquivResult:
    """Compare two BLIF texts; the tool is ``<odin3_root>/tools/equiv-check/equiv-check``."""
    tool = odin3_root / "tools" / "equiv-check" / "equiv-check"
    with tempfile.TemporaryDirectory(prefix="loki-equiv-") as tmp:
        pa, pb = Path(tmp) / "a.blif", Path(tmp) / "b.blif"
        pa.write_text(a, encoding="utf-8")
        pb.write_text(b, encoding="utf-8")
        argv = [str(tool), str(pa), str(pb)]
        if match_unnamed:
            argv.append("--match-unnamed")
        try:
            proc = subprocess.run(
                argv, capture_output=True, text=True, timeout=TIMEOUT_SECONDS, check=False
            )
        except subprocess.TimeoutExpired:
            return EquivResult("unproven", -1, f"timeout after {TIMEOUT_SECONDS} s")
    out = (proc.stdout + proc.stderr).strip()
    return EquivResult(_classify(proc.returncode, out), proc.returncode, out[-400:])
