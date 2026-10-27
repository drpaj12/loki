"""Stage 2: snapshot batch of one set. ``python run_snap.py MI|VT|CI``; one design per process.

One heavy-run batch per set: ``ODIN3_HEAVY_OK=1 $ODIN3_ROOT/tools/heavy-run python run_snap.py MI``.
Restartable: a design with ``manifest.json`` in its directory is skipped. Writes
``<DATA>/snap/<set>/status.csv`` (design, status, seconds, reason)."""

from __future__ import annotations

import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from r6lib import ARCH, DATA, design_set, write_csv

TIMEOUT = 900
JOBS = 3


def one(item: tuple[str, list[Path], str], out_root: Path) -> tuple[str, str, float, str]:
    design, files, top = item
    out = out_root / design
    if (out / "manifest.json").is_file():
        return design, "ok", 0.0, "cached"
    cmd = [sys.executable, "-m", "loki.audit.main", "snap", *map(str, files),
           "--arch-xml", str(ARCH), "--out", str(out)]
    if top:
        cmd += ["--top", top]
    t0 = time.monotonic()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT, check=False)
    except subprocess.TimeoutExpired:
        return design, "timeout", time.monotonic() - t0, f"over {TIMEOUT} s"
    secs = time.monotonic() - t0
    if p.returncode == 0:
        return design, "ok", secs, ""
    lines = [x for x in p.stderr.splitlines() if "error" in x.lower() and "write_json" not in x]
    return design, "fail", secs, (lines[0] if lines else f"exit {p.returncode}")[:200]


def main(name: str) -> int:
    out_root = DATA / "snap" / name
    out_root.mkdir(parents=True, exist_ok=True)
    items = design_set(name)
    with ThreadPoolExecutor(JOBS) as pool:
        rows = list(pool.map(lambda it: one(it, out_root), items))
    write_csv(out_root / "status.csv", ["design", "status", "seconds", "reason"],
              [(d, s, f"{t:.2f}", r) for d, s, t, r in rows])
    print(name, len(rows), sum(1 for r in rows if r[1] == "ok"), "ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
