"""The only module that imports odin3: scripts per floor and the front-end driver (spec 4)."""

from __future__ import annotations

import importlib
import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from loki.model import InstanceSite
from loki.snapshot import take_instances

FRONT = "proc; fsm; opt; flatten; opt -full; wreduce"
_ERROR_LINE = re.compile(r"^(\S+?):(\d+:\d+): error: (.*)$")


class OdinSkip(Exception):
    """The design cannot be read or elaborated by Odin III; the floor is skipped."""


def odin_module() -> Any:
    """The odin3 Python module (imported lazily so the rest of Loki runs without it)."""
    return importlib.import_module("odin3")


def _q(path: Path | str) -> str:
    text = os.fspath(path)
    if '"' in text:
        raise ValueError(f"{text}: a pass argument cannot hold a double quote")
    return f'"{text}"'


def read_script(
    floor: str, files: Sequence[Path], arch_xml: Path | None, cmos6_lib: Path | None
) -> str:
    """Reader part of a floor's script: architecture or tech library, then the Verilog files."""
    if floor == "f3":
        raise NotImplementedError("f3 needs gate mapping")
    if floor not in ("f1-k6", "f1-earch", "f2"):
        raise ValueError(f"unknown floor {floor!r}")
    if arch_xml is None:
        raise ValueError(f"floor {floor} needs an architecture xml")
    paths = " ".join(_q(f) for f in files)
    return f"read_arch {_q(arch_xml)}; read_verilog --nolatches --vtr-compat {paths}"


def floor_script(
    floor: str, files: Sequence[Path], arch_xml: Path | None, cmos6_lib: Path | None
) -> tuple[str, str]:
    """(front script, map script) of a floor (spec 3)."""
    front = f"{read_script(floor, files, arch_xml, cmos6_lib)}; {FRONT}"
    mapping = "hardmap; lower; abc --lut 6" if floor.startswith("f1-") else "lower; abc --lut 6"
    return front, mapping


def _skip_reason(err: Exception, records: list[Any], lib: Any) -> str:
    first = next((r.message for r in records if r.level <= int(lib.ODIN3_LOG_ERROR)), "")
    first = first.splitlines()[0] if first else ""
    m = _ERROR_LINE.match(first)
    if m:
        first = f"{Path(m.group(1)).name}:{m.group(2)}: {m.group(3)}"
    status = str(err).split(": ", 1)[-1]
    return f"odin3: {status} {first}".strip()


def open_front(
    floor: str,
    files: Sequence[Path],
    top: str | None,
    arch_xml: Path | None,
    cmos6_lib: Path | None,
) -> tuple[Any, tuple[InstanceSite, ...]]:
    """Read the design and run the common front; returns (design, instances before flatten).

    Raises OdinSkip with the reason when Odin III rejects the design.
    """
    mod = odin_module()
    o = mod.default()
    o.load_abc()
    reader = read_script(floor, files, arch_xml, cmos6_lib)
    design = mod.Design(o)
    if top:
        o.lib.odin3_pass_set_top_name(top.encode())
    try:
        with o.capture_log() as records:
            try:
                design.run_script(reader)
                instances = take_instances(design)
                design.run_script(FRONT)
            except mod.Odin3Error as err:
                raise OdinSkip(_skip_reason(err, records, o.lib)) from err
    finally:
        if top:
            o.lib.odin3_pass_set_top_name(o.ffi.NULL)
    return design, instances
