"""Paths of Q-L13 (reads the Odin III v1.4 lane and the tools install; writes only under QL13_OUT).

QL13_OUT is the run root (default <workspace>/work/ql13-out). QL13_ODIN is the Odin III v1.4
checkout (default <workspace>/work/odin3-v14, read only); its build/debug/odin3 is the binary.
QL13_RES is the results directory (default ``results/``; the v1.6.1 rerun uses ``results-v161/``).
QL13_TOOLS is the user-space tools directory of the silicon flow manual
(default <workspace>/work/tools).
"""

from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parent
WS = Path(os.environ.get("QL13_WS", str(REPO.parent.parent)))
RUN = Path(os.environ.get("QL13_OUT", str(WS / "work" / "ql13-out")))
ODIN = Path(os.environ.get("QL13_ODIN", str(WS / "work" / "odin3-v14")))
TOOLS = Path(os.environ.get("QL13_TOOLS", str(WS / "work" / "tools")))
ODIN_BIN = Path(os.environ.get("QL13_ODIN_BIN", str(ODIN / "build" / "debug" / "odin3")))
RES = Path(os.environ.get("QL13_RES", str(HERE / "results")))
VEVAL = WS / "external" / "verilog-eval" / "dataset_spec-to-rtl"
EXT = WS / "external"
TINY = EXT / "tinyriscv" / "rtl" / "core"
# name -> (top module, source file): the Q-L10 / Q-L12 processor modules (pcpi_mul is unreadable)
EXT_DESIGNS: dict[str, tuple[str, Path]] = {
    "tinyriscv_clint": ("clint", TINY / "clint.v"),
    "picorv32_pcpi_div": ("picorv32_pcpi_div", EXT / "picorv32" / "picorv32.v"),
    "tinyriscv_div": ("div", TINY / "div.v"),
    "tinyriscv_csr": ("csr_reg", TINY / "csr_reg.v"),
}
Q12 = EXP / "ql12-k4k6"
CLOCK_RE = re.compile(r"\binput\s+(?:wire\s+|logic\s+|reg\s+)?clk\b")


def designs() -> list[dict[str, str]]:
    """The Q-L12 test set (40 VerilogEval problems + 4 processor modules), smallest source first.
    Rows: name, top, src, clock ('' = none)."""
    d = json.loads((Q12 / "designs.json").read_text(encoding="utf-8"))
    names = sorted({x["problem"] for x in d if x["endpoint"] == "k4"})
    rows: list[dict[str, str]] = []
    for n in names:
        if n in EXT_DESIGNS:
            top, src = EXT_DESIGNS[n]
        else:
            top, src = "RefModule", VEVAL / f"{n}_ref.sv"
        text = src.read_text(encoding="utf-8", errors="replace")
        rows.append({"name": n, "top": top, "src": str(src), "bytes": str(src.stat().st_size),
                     "clock": "clk" if CLOCK_RE.search(_top_text(text, top)) else ""})
    rows.sort(key=lambda r: (int(r["bytes"]), r["name"]))
    return rows


def _top_text(text: str, top: str) -> str:
    """The text of module ``top`` (to its endmodule), else the whole file."""
    m = re.search(rf"\bmodule\s+{re.escape(top)}\b.*?\bendmodule\b", text, re.S)
    return m.group(0) if m else text


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
