"""Normalise an anonymous netlist into an Odin III design, level 0 (L1 spec 3)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from loki.odin import error_reason, odin_module
from loki.schemas import FLOORS
from loki.techlib import load_techlib

VTR_LIB = Path("lib") / "vtr.o3lib"
CMOS6_LIB = Path("lib") / "cmos6.o3lib"
# Gate-level Verilog: elaborate (`proc` reads the always blocks), split word cells, map gates.
VERILOG_FRONT = "proc; lower"


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


def _root(odin3_root: Path | None) -> Path | None:
    if odin3_root is not None:
        return odin3_root
    raw = os.environ.get("ODIN3_ROOT")
    return Path(raw) if raw else None


def _techlib(floor: str, odin3_root: Path | None, techlib: Path | None) -> Path | None:
    if techlib is not None:
        return techlib
    if not floor.startswith("f1-"):
        return None
    root = _root(odin3_root)
    if root is None:
        raise ValueError(f"floor {floor} needs the Odin III checkout (--odin3-root) for vtr.o3lib")
    return root / VTR_LIB


def gate_library(odin3_root: Path | None, techlib: Path | None) -> Path:
    """The gate library of a gate-level Verilog input (spec 3 ``.v`` row)."""
    if techlib is not None:
        return techlib
    root = _root(odin3_root)
    if root is None:
        raise ValueError(
            "gate-level Verilog needs the Odin III checkout (--odin3-root) for lib/cmos6.o3lib")
    return root / CMOS6_LIB


def level0_script(floor: str, path: Path, odin3_root: Path | None, techlib: Path | None) -> str:
    """The Odin III script of spec 3 for a BLIF input."""
    if floor not in FLOORS:
        raise ValueError(f"unknown floor {floor!r}")
    if path.suffix == ".v":
        raise ValueError(f"{path}: gate-level Verilog is normalised by load_level0 (spec 3)")
    lib = _techlib(floor, odin3_root, techlib)
    read = f"read_blif {_q(path)}"
    return f"read_techlib {_q(lib)}; {read}" if lib is not None else read


def _run(design: Any, script: str, o: Any, mod: Any) -> None:
    """Run ``script``; an Odin III refusal becomes ``NormaliseError`` and closes the design."""
    with o.capture_log() as records:
        try:
            design.run_script(script)
        except mod.Odin3Error as err:
            design.close()
            raise NormaliseError(error_reason(err, records, o.lib)) from err


def _verilog_script(path: Path, lib: Path, out: Path) -> str:
    """Read gate-level Verilog, map it to the gate library and write a gate BLIF (spec 3)."""
    name = load_techlib(lib).name
    return (f"read_techlib {_q(lib)}; read_verilog {_q(path)}; {VERILOG_FRONT}; "
            f"abc --gates {name}; dfflibmap {name}; write_blif --gates-as-names {_q(out)}")


def _load_verilog(path: Path, floor: str, odin3_root: Path | None, techlib: Path | None) -> Any:
    """Gate-level Verilog: map to gates, write a temporary BLIF and read that into a new design."""
    if floor != "f3":
        raise ValueError(f"{path}: gate-level Verilog needs floor f3, not {floor}")
    lib = gate_library(odin3_root, techlib)
    if not lib.is_file():
        raise ValueError(f"{path}: no technology library {lib}")
    mod = odin_module()
    o = mod.default()
    o.load_abc()
    with tempfile.TemporaryDirectory(prefix="loki-f3-") as tmpname:
        mapped = mod.Design(o)
        _run(mapped, _verilog_script(path, lib, Path(tmpname) / "gate.blif"), o, mod)
        mapped.close()
        level0 = mod.Design(o)
        _run(level0, f'read_blif {_q(Path(tmpname) / "gate.blif")}', o, mod)
    return level0


def load_level0(path: Path, floor: str, odin3_root: Path | None, techlib: Path | None) -> Any:
    """A fresh ``odin3.Design`` holding the netlist (never edited afterwards).

    Gate-level Verilog (``.v``, floor f3) is mapped and read back from a temporary BLIF so that
    every logic cell is a ``$sop`` cover, like the BLIF inputs.
    """
    if path.suffix == ".v":
        return _load_verilog(path, floor, odin3_root, techlib)
    mod = odin_module()
    o = mod.default()
    o.load_abc()
    design = mod.Design(o)
    _run(design, level0_script(floor, path, odin3_root, techlib), o, mod)
    return design
