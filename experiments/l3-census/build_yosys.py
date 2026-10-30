"""Yosys builds of the census designs: ``python -B build_yosys.py CELL`` (Y-gate or Y-lut).

Y-gate: the Gate-Breaker script (proc; fsm; opt; memory; opt; techmap; opt; dfflibmap; abc with
cmos_cells.lib; clean), then read back through ``read_liberty`` and written as BLIF.
Y-lut: same front, then ``dfflegalize -cell $_DFF_P_ 01 ...; abc -lut 6`` (enable and reset
become LUT logic; v1 kept $_SDFFE_ cells and is not used).
Writes OUT/build/CELL/<design>/{netlist.blif,stat.txt}.
"""

from __future__ import annotations

import importlib
import json
import resource
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
lib: Any = importlib.import_module("l3lib")

FRONT = "proc; fsm; opt; memory; opt\ntechmap; opt\n"


def script(cell: str, r: dict[str, str], out: Path) -> str:
    top = f"hierarchy -top {r['top']}" if r["top"] else "hierarchy -auto-top"
    head = f"read_verilog -sv {r['src']}\n{top}\n{FRONT}"
    if cell == "Y-gate":
        return (head + f"dfflibmap -liberty {lib.LIB}\nabc -liberty {lib.LIB}\nclean\n"
                f"write_verilog -noattr {out}/gates.v\ntee -o {out}/stat.txt stat\n"
                f"design -reset\nread_liberty {lib.LIB}\nread_verilog {out}/gates.v\n"
                f"hierarchy -auto-top\nflatten\nopt_clean\nwrite_blif {out}/netlist.blif\n")
    legal = "-cell $_DFF_P_ 01 -cell $_DFF_PP0_ 01 -cell $_DFF_PP1_ 01 -cell $_DLATCH_P_ x"
    return (head + f"dfflegalize {legal}\n"
            f"abc -lut 6\nclean\ntee -o {out}/stat.txt stat\n"
            f"write_blif {out}/netlist.blif\n")


def limit() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (6 << 30, 6 << 30))


def main(cell: str) -> int:
    base = lib.OUT / "build" / cell
    rows = sorted(lib.manifest(), key=lambda r: (Path(r["src"]).stat().st_size, r["design"]))
    for r in rows:
        out = base / r["design"]
        if (out / "status.json").is_file():
            continue
        out.mkdir(parents=True, exist_ok=True)
        (out / "run.ys").write_text(script(cell, r, out), encoding="utf-8")
        try:
            p = subprocess.run([str(lib.YOSYS), "-q", "-s", str(out / "run.ys")],
                               capture_output=True, text=True, timeout=300, check=False,
                               preexec_fn=limit)
            status = "ok" if p.returncode == 0 and (out / "netlist.blif").is_file() else "fail"
            reason = p.stderr.strip().splitlines()[-1] if status == "fail" and p.stderr else ""
        except subprocess.TimeoutExpired:
            status, reason = "fail", "timeout 300 s"
        (out / "status.json").write_text(json.dumps({"status": status, "reason": reason[:300]},
                                                    sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
