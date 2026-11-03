"""LUT-level netlists (k4 = f2, k6 = f1-k6) of the five processor modules of Q-L10 (tier ext).

Same Odin III builds as the l3-census (``loki.build.build_floor``, ``read_arch`` of the VTR k6
architecture), on the same sources as ``ql10-blocks/q10_synth_ext.py``. Writes
``$QL12_OUT/census/<cell>/<name>/<floor>/`` (netlist.blif, key.json, labels.csv ...), the layout
of the census. Usage: ``python -B q12_synth_ext.py [NAME_FILTER]``. Sources are read in place.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import q12_env as env

bd: Any = env.mod("loki.build")
ARCH = (env.WS / "external" / "vtr-verilog-to-routing" / "vtr_flow" / "arch" / "timing"
        / "k6_frac_N10_frac_chain_mem32K_40nm.xml")
ODIN = Path(os.environ.get("ODIN3_ROOT", str(env.WS / "odin3")))
EXT = env.WS / "external"
TINY = EXT / "tinyriscv" / "rtl" / "core"
DESIGNS: dict[str, tuple[str, Path]] = {  # name -> (top module, source file)
    "tinyriscv_clint": ("clint", TINY / "clint.v"),
    "picorv32_pcpi_div": ("picorv32_pcpi_div", EXT / "picorv32" / "picorv32.v"),
    "picorv32_pcpi_mul": ("picorv32_pcpi_mul", EXT / "picorv32" / "picorv32.v"),
    "tinyriscv_div": ("div", TINY / "div.v"),
    "tinyriscv_csr": ("csr_reg", TINY / "csr_reg.v"),
}


def main(only: str) -> int:
    root = env.RUN / "census"
    for endpoint, (cell, floor) in env.ENDPOINTS.items():
        base = root / cell
        for name, (top, src) in DESIGNS.items():
            if only and only not in name:
                continue
            status = base / name / "status.json"
            if status.is_file():
                continue
            res = bd.build_floor(name, [src], top, floor, ARCH, base, ODIN)
            status.parent.mkdir(parents=True, exist_ok=True)
            status.write_text(json.dumps({"status": res.status, "reason": res.reason},
                                         sort_keys=True), encoding="utf-8")
            print(endpoint, name, res.status, res.reason[:100], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
