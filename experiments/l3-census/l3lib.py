"""Shared pieces of the L3 census: paths, corpora manifest, cells (tool x target)."""

from __future__ import annotations

import csv
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
WS = Path(os.environ.get("L3_WS", str(REPO.parent.parent)))
OUT = Path(os.environ.get("L3_OUT", str(WS / "work" / "l3-out")))
ODIN = Path(os.environ.get("ODIN3_ROOT", str(WS / "odin3")))
YOSYS = WS / "external" / "yosys" / "build" / "yosys"
LIB = WS / "external" / "yosys" / "examples" / "cmos" / "cmos_cells.lib"
VEVAL = WS / "external" / "verilog-eval" / "dataset_spec-to-rtl"
VTRV = WS / "external" / "vtr-verilog-to-routing" / "vtr_flow" / "benchmarks" / "verilog"
ARCH = WS / "work/norns-vtr/vtr_flow/arch/timing/k6_frac_N10_frac_chain_mem32K_40nm.xml"
R4 = OUT / "r4corpus"
R4_PER_FAMILY = 30
VTR_SMALL = ("single_ff", "diffeq1", "diffeq2", "ch_intrinsics_nolatches")
ODIN_CELLS = {"O-gate": "f3", "O-lut": "f2", "O-hard": "f1-k6"}
YOSYS_CELLS = ("Y-gate", "Y-lut")
CELLS = (*ODIN_CELLS, *YOSYS_CELLS)
FLOOR_OF = {"O-gate": "f3", "O-lut": "f2", "O-hard": "f1-k6", "Y-gate": "f3", "Y-lut": "f2"}
DETECTORS = "wordfirst,hard,ff_pattern,mux,arith,seqfn,fsm,bus,unit,role,wordgroup"


# Odin III's read_slang refuses the 4-bit enum cast States'(...) of these two references; the
# Odin III builds use a copy with the cast removed and the state variables plain logic
# (OUT/patched/, same logic); Yosys reads the
# originals.
PATCHED = ("Prob151_review2015_fsm", "Prob156_review2015_fancytimer")


def manifest() -> list[dict[str, str]]:
    """Every design of the three corpora: corpus, design, source path, top ('' = auto)."""
    rows: list[dict[str, str]] = []
    for ref in sorted(VEVAL.glob("*_ref.sv")):
        name = ref.name[: -len("_ref.sv")]
        row = {"corpus": "veval", "design": "ve_" + name, "src": str(ref), "top": "RefModule"}
        if name in PATCHED:
            row["osrc"] = str(OUT / "patched" / ref.name)
        rows.append(row)
    with (R4 / "corpus.csv").open(encoding="utf-8", newline="") as fh:
        per: dict[str, int] = {}
        for r in csv.DictReader(fh):
            n = per.get(r["family"], 0)
            if n >= R4_PER_FAMILY:
                continue
            per[r["family"]] = n + 1
            d = r["design"]
            rows.append({"corpus": "r4", "design": d,
                         "src": str(R4 / "designs" / d / f"{d}.v"), "top": ""})
    for name in VTR_SMALL:
        rows.append({"corpus": "vtr", "design": "vtr_" + name,
                     "src": str(VTRV / f"{name}.v"), "top": ""})
    return rows


def netlist(cell: str, design: str) -> Path:
    if cell in ODIN_CELLS:
        return OUT / "build" / cell / design / ODIN_CELLS[cell] / "netlist.blif"
    return OUT / "build" / cell / design / "netlist.blif"
