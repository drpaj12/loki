"""Gate-level netlists of the designs over arm A's size limit (tier ``ext``): processor modules
from the suite's external checkouts, synthesized with the Gate-Breaker script's Yosys recipe
(``scripts/synth-to-netlist``: proc, fsm, opt, memory, techmap, dfflibmap, abc with
``cmos_cells.lib``) plus ``flatten``. Yosys is the VTR checkout's build (0.55; the dataset used
0.51). Usage: ``python -B q10_synth_ext.py``; writes ``$QL10_OUT/ext/<name>.netlist.v``.
Sources are read in place, never changed. Not the private processor set.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import q10_env as env

EXT = env.WS / "external"
LIB = EXT / "yosys" / "examples" / "cmos" / "cmos_cells.lib"
YOSYS = EXT / "vtr-verilog-to-routing" / "build" / "bin" / "yosys"
TINY = EXT / "tinyriscv" / "rtl" / "core"
PICO = EXT / "picorv32" / "picorv32.v"
# name -> (top module, source files)
DESIGNS: dict[str, tuple[str, list[Path]]] = {
    "picorv32_pcpi_div": ("picorv32_pcpi_div", [PICO]),
    "picorv32_pcpi_mul": ("picorv32_pcpi_mul", [PICO]),
    "tinyriscv_div": ("div", [TINY / "div.v"]),
    "tinyriscv_csr": ("csr_reg", [TINY / "csr_reg.v"]),
    "tinyriscv_clint": ("clint", [TINY / "clint.v"]),
}


def ys_text(top: str, files: list[Path], out: Path) -> str:
    reads = "\n".join(f"read_verilog -sv -I{TINY} {f}" for f in files)
    return (f"{reads}\nhierarchy -top {top}\nflatten\nproc; fsm; opt; memory; opt\n"
            f"techmap; opt\ndfflibmap -liberty {LIB}\nabc -liberty {LIB}\nclean\n"
            f"write_verilog -noattr {out}\n")


def main() -> int:
    out_dir = env.RUN / "ext"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, (top, files) in DESIGNS.items():
        out = out_dir / f"{name}.netlist.v"
        ys = out_dir / f"{name}.ys"
        ys.write_text(ys_text(top, files, out), encoding="utf-8", newline="\n")
        done = subprocess.run([str(YOSYS), "-q", str(ys)], capture_output=True, text=True,
                              check=False, timeout=900)
        print(name, "rc", done.returncode, flush=True)
        if done.returncode != 0:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
