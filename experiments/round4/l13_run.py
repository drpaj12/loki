"""RQ-L13 stage 3a: build the big VTR designs one at a time, measuring peak RSS.

Usage: l13_run.py [DESIGN ...]   (default: the list of EXPERIMENT.md, smallest source first)
Each design runs as its own process under the heavy lock (``flock -x``), a hard address-space limit
of 14 GiB (``prlimit --as``; 60% of the 23 GB VM is 13.8 GB) and ``/usr/bin/time -v``. A design
that is already built (``metrics.json`` present) is skipped. Appends to ``l13_builds.csv``.
"""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import r4lib

DESIGNS = ("stereovision3", "sha", "mkPktMerge", "blob_merge", "stereovision2", "spree", "bgm",
           "boundtop", "raygentop", "stereovision1", "stereovision0", "or1200", "mkSMAdapter4B",
           "LU8PEEng", "LU32PEEng", "mkDelayWorker32B", "arm_core", "mcml", "LU64PEEng")
AS_LIMIT = 14 * 1024 ** 3
LOCK = os.environ.get("ODIN3_HEAVY_LOCK", "/tmp/claude-1000/odin3-heavy.lock")
BIG = r4lib.DATA / "big"
FIELDS = ["design", "source_bytes", "status", "seconds", "peak_rss_mb", "f1-k6", "f2", "f3",
          "nodes_f3", "note"]


def one(design: str) -> dict[str, object]:
    ddir = BIG / design
    ddir.mkdir(parents=True, exist_ok=True)
    tfile = ddir / "time.txt"
    log = ddir / "build.log"
    vtr = Path(os.environ["VTR_ROOT"])
    src = vtr / "vtr_flow" / "benchmarks" / "verilog" / f"{design}.v"
    cmd = ["flock", "-x", LOCK, "prlimit", f"--as={AS_LIMIT}", "/usr/bin/time", "-v", "-o",
           str(tfile), sys.executable, str(Path(__file__).with_name("l13_build.py")), design,
           str(ddir / "dataset")]
    start = time.monotonic()
    with log.open("w", encoding="utf-8") as fh:
        proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, check=False)
    secs = round(time.monotonic() - start, 1)
    rss = 0.0
    m = re.search(r"Maximum resident set size \(kbytes\): (\d+)", tfile.read_text("utf-8")) \
        if tfile.is_file() else None
    if m:
        rss = round(int(m.group(1)) / 1024, 1)
    floors = {"f1-k6": "", "f2": "", "f3": ""}
    for line in log.read_text(encoding="utf-8").splitlines():
        mm = re.match(rf"vtr_{design} (f1-k6|f2|f3): (\w+) ?(.*)", line)
        if mm:
            floors[mm.group(1)] = mm.group(2) + (":" + mm.group(3)[:60] if mm.group(3) else "")
    nodes = 0
    mj = ddir / "dataset" / f"vtr_{design}" / "f3" / "meta.json"
    if mj.is_file():
        nodes = int(json.loads(mj.read_text(encoding="utf-8"))["counts"]["nodes"])
    status = "ok" if proc.returncode == 0 else f"exit {proc.returncode}"
    return {"design": design, "source_bytes": src.stat().st_size, "status": status,
            "seconds": secs, "peak_rss_mb": rss, "f1-k6": floors["f1-k6"], "f2": floors["f2"],
            "f3": floors["f3"], "nodes_f3": nodes, "note": ""}


def main() -> int:
    designs = sys.argv[1:] or list(DESIGNS)
    BIG.mkdir(parents=True, exist_ok=True)
    out = BIG / "l13_builds.csv"
    new = not out.is_file()
    with out.open("a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, FIELDS, lineterminator="\n")
        if new:
            w.writeheader()
        for d in designs:
            if (BIG / d / "metrics.json").is_file():
                continue
            row = one(d)
            w.writerow(row)
            fh.flush()
            print(row, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
