"""Re-run `loki re` on the five netlists that raised KeyError before the groups.py fix."""

from __future__ import annotations

import l3dlib as lib
import run_re

JOBS = [("O-gate", "ve_Prob153_gshare"), ("O-lut", "ve_Prob153_gshare"),
        ("O-hard", "ve_Prob153_gshare"), ("Y-gate", "vtr_ch_intrinsics_nolatches"),
        ("Y-lut", "vtr_ch_intrinsics_nolatches")]


def main() -> int:
    for cell, design in JOBS:
        net = run_re.lib.netlist(cell, design)
        out = lib.CENSUS / "re" / cell / design
        if net.is_file() and not (out / "intent.json").is_file():
            code = run_re.one((net.stat().st_size, cell, net, out))
            print(cell, design, "exit", code, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
