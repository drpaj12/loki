"""Synthesise and analyse the composites: ``python -B run_all.py STAGE [ARG...]``.

Stages: odin CELL, yosys CELL, re JOBS. Sets the census manifest to the composites; outputs go
to $L3_OUT (work/l3d-out). Reuses the census build_odin / build_yosys / run_re scripts.
"""

from __future__ import annotations

import os
import subprocess
import sys

import l3dlib as lib

os.environ.setdefault("L3_OUT", str(lib.OUT))



def manifest() -> list[dict[str, str]]:
    rows = []
    for r in lib.read_csv(lib.RES / "composites.csv"):
        src = lib.OUT / "composites" / r["name"] / f"{r['name']}.sv"
        rows.append({"corpus": "q", "design": r["name"], "src": str(src), "top": r["name"]})
    return rows


def disk_ok() -> bool:
    free = subprocess.run(["df", "--output=avail", "-BG", "/mnt/c"], capture_output=True,
                          text=True, check=True).stdout.split()[-1]
    return int(free.rstrip("G")) >= 15


def main(argv: list[str]) -> int:
    import importlib

    l3lib = importlib.import_module("l3lib")
    l3lib.manifest = manifest
    if not disk_ok():
        print("DISK below 15G: stop")
        return 2
    stage = argv[0]
    if stage == "odin":
        return int(importlib.import_module("build_odin").main(argv[1], ""))
    if stage == "yosys":
        by = importlib.import_module("build_yosys")
        by.FRONT = "flatten\n" + by.FRONT  # composites are hierarchical
        return int(by.main(argv[1]))
    return int(importlib.import_module("run_re").main(argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
