"""Write the library RTL and synthesise it.

``python -B build_all.py rtl|odin CELL|yosys CELL|re [JOBS [CELL...]]``.

Reuses the l3-census build scripts through a manifest swap (as l3-detector/run_all.py). Outputs go
to $GLET_OUT (default <ws>/work/glet-out): rtl/<name>.v, build/<cell>/<name>/... Optional
GLET_ONLY=substring limits the designs (smoke tests). Stops when /mnt/c has under 15G free.
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = Path(os.environ.get("L3_WS", str(HERE.parent.parent.parent.parent)))
OUT = Path(os.environ.get("GLET_OUT", str(WS / "work" / "glet-out")))
os.environ["L3_OUT"] = str(OUT)
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "l3-census"))

import gen  # noqa: E402


def disk_ok() -> bool:
    free = subprocess.run(["df", "--output=avail", "-BG", "/mnt/c"], capture_output=True,
                          text=True, check=True).stdout.split()[-1]
    return int(free.rstrip("G")) >= 15


def write_rtl() -> list[gen.Inst]:
    (OUT / "rtl").mkdir(parents=True, exist_ok=True)
    only = os.environ.get("GLET_ONLY", "")
    insts = [i for i in gen.instances() if only in i.name]
    for i in insts:
        (OUT / "rtl" / f"{i.name}.v").write_text(gen.verilog(i), encoding="utf-8")
    return insts


def manifest() -> list[dict[str, str]]:
    return [{"corpus": "glet", "design": i.name, "src": str(OUT / "rtl" / f"{i.name}.v"),
             "top": gen.TOP} for i in write_rtl()]


def main(argv: list[str]) -> int:
    if not disk_ok():
        print("DISK below 15G: stop")
        return 2
    if argv[0] == "rtl":
        print(len(write_rtl()), "RTL files")
        return 0
    l3lib = importlib.import_module("l3lib")
    l3lib.manifest = manifest
    if argv[0] == "odin":
        return int(importlib.import_module("build_odin").main(argv[1], ""))
    if argv[0] == "re":
        return int(importlib.import_module("run_re").main(argv[1:]))
    return int(importlib.import_module("build_yosys").main(argv[1]))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
