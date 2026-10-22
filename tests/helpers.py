"""Shared test helpers: Odin III availability and location."""

from __future__ import annotations

import importlib
import os
from pathlib import Path

from loki.model import FinalCell, Net, Netlist, Port, PortBit, Span


def odin_available() -> bool:
    """True when the odin3 module imports and the shared library loads."""
    try:
        mod = importlib.import_module("odin3")
        mod.Odin3()
    except Exception:
        return False
    return True


def odin3_root() -> Path | None:
    """The Odin III checkout from $ODIN3_ROOT, or None when it lacks equiv-check."""
    raw = os.environ.get("ODIN3_ROOT")
    if not raw:
        return None
    root = Path(raw)
    if not (root / "tools" / "equiv-check" / "equiv-check").is_file():
        return None
    return root


def lut_cell(
    cid: int, ins: list[int], out: int, table: str, spans: tuple[Span, ...] = ()
) -> FinalCell:
    """A hand-built $lut cell."""
    return FinalCell(
        id=cid, kind="lut", type="$lut", name="", params={"WIDTH": len(ins), "LUT": table},
        spans=spans, inputs=(Port("A", len(ins), tuple(ins)),), outputs=(Port("Y", 1, (out,)),),
    )


def and_netlist() -> Netlist:
    """PIs A[0], A[1]; one AND LUT; PO X."""
    nets = {i: Net(i, ()) for i in (1, 2, 3)}
    pbs = (PortBit("A[0]", "in", 1), PortBit("A[1]", "in", 2), PortBit("X", "out", 3))
    return Netlist("t", nets, (lut_cell(10, [1, 2], 3, "0001"),), pbs)
