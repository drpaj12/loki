"""Normalise an anonymous netlist into an Odin III design, level 0 (L1 spec 3)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from loki.odin import error_reason, odin_module
from loki.schemas import FLOORS

VTR_LIB = Path("lib") / "vtr.o3lib"


class NormaliseError(Exception):
    """Odin III refused the netlist; the message is ``odin3: <status>`` plus the first error."""


def floor_from_path(path: Path) -> str:
    """The floor named by the nearest directory of ``path`` (``.../<floor>/netlist.blif``)."""
    for part in reversed(path.parts[:-1]):
        if part in FLOORS:
            return part
    raise ValueError(f"{path}: no floor directory ({', '.join(FLOORS)}) in the path")


def _q(path: Path) -> str:
    text = os.fspath(path)
    if '"' in text:
        raise ValueError(f"{text}: a pass argument cannot hold a double quote")
    return f'"{text}"'


def _techlib(floor: str, odin3_root: Path | None, techlib: Path | None) -> Path | None:
    if techlib is not None:
        return techlib
    if not floor.startswith("f1-"):
        return None
    root = odin3_root
    if root is None and os.environ.get("ODIN3_ROOT"):
        root = Path(os.environ["ODIN3_ROOT"])
    if root is None:
        raise ValueError(f"floor {floor} needs the Odin III checkout (--odin3-root) for vtr.o3lib")
    return root / VTR_LIB


def level0_script(floor: str, path: Path, odin3_root: Path | None, techlib: Path | None) -> str:
    """The Odin III script of spec 3 for a BLIF input."""
    if floor not in FLOORS:
        raise ValueError(f"unknown floor {floor!r}")
    if path.suffix == ".v":
        raise NotImplementedError("f3 gate-level Verilog needs gate mapping")
    lib = _techlib(floor, odin3_root, techlib)
    read = f"read_blif {_q(path)}"
    return f"read_techlib {_q(lib)}; {read}" if lib is not None else read


def load_level0(path: Path, floor: str, odin3_root: Path | None, techlib: Path | None) -> Any:
    """A fresh ``odin3.Design`` holding the netlist (never edited afterwards)."""
    script = level0_script(floor, path, odin3_root, techlib)
    mod = odin_module()
    o = mod.default()
    o.load_abc()
    design = mod.Design(o)
    with o.capture_log() as records:
        try:
            design.run_script(script)
        except mod.Odin3Error as err:
            design.close()
            raise NormaliseError(error_reason(err, records, o.lib)) from err
    return design
