"""Odin III four-input LUT netlists (floor f2 with ``abc --lut 4``) for the Q-L12 lut4 set.

How K is set: the Loki floor script (``loki.odin.floor_script``) ends the f2 mapping with
``lower; abc --lut 6``; ``abc --lut <K>`` is the Odin III pass option that gives ABC its K
(odin3 docs/PHASE3.md, script language: ``{K}`` = the LUT size, from ``abc --lut <K>``). This
script replaces ``--lut 6`` by ``--lut 4`` in that script for this process only (the Loki source
is not changed) and calls ``loki.build.build_floor`` as the l3-census does, so everything else
(front end, ``--nolatches --vtr-compat``, no hardmap, equivalence checks) is the census f2 build.
``read_arch`` still needs an architecture file: the VTR ``k4_N4_90nm.xml`` of the checkout
(four-input LUTs, no hard blocks); it does not change the soft-logic mapping.

Writes ``$QL12_OUT/census-ve/O-lut/ve_<problem>/f2/`` (VerilogEval problems of the Q-L10 set,
sources and tops as the l3-census manifest) and ``$QL12_OUT/census/O-lut/<name>/f2/``
(processor modules, sources as ``q12_synth_ext``). Resumable. Usage: ``python -B l4_census.py
[NAME_FILTER]``; run through ``odin3/tools/heavy-run`` (ODIN3_HEAVY_OK=1).
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import l4_env as l4

env = l4.env
bd: Any = env.mod("loki.build")
odin: Any = env.mod("loki.odin")
ARCH = (env.WS / "external" / "vtr-verilog-to-routing" / "vtr_flow" / "arch" / "timing"
        / "k4_N4_90nm.xml")
FLOOR = "f2"
CELL = "O-lut"


def floor_script_k4(floor: str, files: Any, arch: Any, lib: Any) -> tuple[str, str]:
    front, mapping = odin.floor_script(floor, files, arch, lib)
    if floor != FLOOR or "abc --lut 6" not in mapping:
        raise ValueError(f"unexpected floor script {floor}: {mapping}")
    return front, mapping.replace("abc --lut 6", "abc --lut 4")


def problems() -> list[str]:
    bk: Any = importlib.import_module("q12_build")
    return [r["problem"] for r in bk.problems() if r["tier"] != "ext"]


PATCHED = ("Prob151_review2015_fsm", "Prob156_review2015_fancytimer")  # as the l3-census
VEVAL = env.WS / "external" / "verilog-eval" / "dataset_spec-to-rtl"
PATCH_DIR = env.WS / "work" / "l3-out" / "patched"  # the census's patched copies, read only


def source(problem: str) -> Path:
    """Source of a VerilogEval problem as the l3-census builds it (top ``RefModule``)."""
    name = f"{problem}_ref.sv"
    return (PATCH_DIR if problem in PATCHED else VEVAL) / name


def build(name: str, src: Path, top: str, base: Path) -> None:
    done = base / name / "status.json"
    if done.is_file():
        return
    odin_root = Path(os.environ.get("ODIN3_ROOT", str(env.WS / "odin3")))
    res = bd.build_floor(name, [src], top or None, FLOOR, ARCH, base, odin_root)
    done.parent.mkdir(parents=True, exist_ok=True)
    done.write_text(json.dumps({"status": res.status, "reason": res.reason}, sort_keys=True),
                    encoding="utf-8")
    print(name, res.status, res.reason[:100], flush=True)


def main(only: str) -> int:
    bd.floor_script = floor_script_k4  # this process only
    base = env.CENSUS / CELL
    for p in sorted(problems(), key=lambda q: (source(q).stat().st_size, q)):
        if not only or only in p:
            build(f"ve_{p}", source(p), "RefModule", base)
    synth: Any = importlib.import_module("q12_synth_ext")
    for name, (top, src) in synth.DESIGNS.items():
        if not only or only in name:
            build(name, src, top, env.RUN / "census" / CELL)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
