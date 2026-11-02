"""Population of Q-L10: the llm-full problems (137) plus the four problems it left out for size.

Tiers: ``vq`` = the 137 problems of experiments/llm-full/selection.csv (arm A has 3 draws in the
full run); ``vbig`` = the four VerilogEval problems the full run excluded because the dataset prompt
is over the pilot's 40000 B cap (Prob018, Prob052, Prob105, Prob115; arm A is not run on them);
``ext`` = processor modules over the size limit (``ext_designs.csv``; netlists from
``q10_synth_ext.py`` under ``$QL10_OUT/ext``; no testbench, scored by equivalence). Designs the
block reader cannot read (behavioural latches) are listed in the plan with the reason.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import q10_env as env
import q10_nl

common: Any = env.mod("common")
BIG = ("Prob018_mux256to1", "Prob052_gates100", "Prob105_rotate100", "Prob115_shift18")


def rows() -> list[dict[str, str]]:
    """problem, quartile, tier for every design, tier then problem order."""
    full = env.EXP / "llm-full"
    out: list[dict[str, str]] = []
    with (full / "selection.csv").open(encoding="utf-8", newline="") as fh:
        out += [{"problem": r["problem"], "quartile": r["quartile"], "tier": "vq"}
                for r in csv.DictReader(fh)]
    with (full / "excluded.csv").open(encoding="utf-8", newline="") as fh:
        out += [{"problem": r["problem"], "quartile": r["quartile"], "tier": "vbig"}
                for r in csv.DictReader(fh) if r["problem"] in BIG]
    ext = env.HERE / "ext_designs.csv"
    if ext.is_file():
        with ext.open(encoding="utf-8", newline="") as fh:
            out += [{"problem": r["name"], "quartile": "-", "tier": "ext"}
                    for r in csv.DictReader(fh)]
    return out


def is_ext(problem: str) -> bool:
    return (env.RUN / "ext" / f"{problem}.netlist.v").is_file()


def netlist_path(problem: str) -> Path:
    if is_ext(problem):
        return env.RUN / "ext" / f"{problem}.netlist.v"
    return Path(common.dataset_dir()) / f"{problem}_netlist.v"


def read(problem: str) -> q10_nl.Netlist:
    return q10_nl.read(netlist_path(problem))
