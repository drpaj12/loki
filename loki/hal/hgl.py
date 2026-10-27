"""The two HAL gate libraries (``.hgl``, JSON version 4) written for the L0 floors.

``lut6``: f2, the LUT6 floor (LUT1..LUT6 with an ``INIT`` generic, FF, GND, VCC).
``cmos6``: f3, the cmos6 floor of ``lib/cmos6.o3lib`` (BUF INV NAND2 NOR2 DFF DFFSR, GND, VCC).
The structure follows ``example_library.hgl`` of HAL v4.5.0 (MIT); no HAL file is copied.
The committed files are ``experiments/hal/hgl/<name>.hgl``; ``python -m loki.hal.hgl <name>``
prints the same text.
"""

from __future__ import annotations

import json
import sys
from typing import Any

Json = dict[str, Any]

LUT_PINS = ("I0", "I1", "I2", "I3", "I4", "I5")


def _pin(name: str, direction: str, ptype: str, function: str = "") -> Json:
    pin: Json = {"name": name, "direction": direction, "type": ptype}
    if function:
        pin["function"] = function
    return pin


def _group(name: str, direction: str, ptype: str, function: str = "") -> Json:
    return {
        "name": name, "direction": direction, "type": ptype, "ascending": False,
        "start_index": 0, "ordered": False, "pins": [_pin(name, direction, ptype, function)],
    }


def _comb(name: str, kind: str, ins: list[str], out: str, function: str) -> Json:
    groups = [_group(i, "input", "none") for i in ins]
    groups.append(_group(out, "output", "none", function))
    return {"name": name, "types": ["combinational", kind], "pin_groups": groups}


def _lut(k: int) -> Json:
    # HAL (gate.cpp, get_boolean_function_from_lut): "ascending" bit-reverses INIT over 2^k bits;
    # INIT bit i then selects input assignment i with the first input pin as the least
    # significant bit. The converter writes INIT bit i = assignment with I0 as LSB, so the
    # no-reversal order ("descending") is the matching one.
    groups = [_group(p, "input", "none") for p in LUT_PINS[:k]]
    groups.append(_group("O", "output", "lut"))
    return {
        "name": f"LUT{k}", "types": ["combinational", "c_lut"],
        "lut_config": {
            "bit_order": "descending", "data_category": "generic", "data_identifier": "INIT",
        },
        "pin_groups": groups,
    }


def _const(name: str, kind: str, value: str) -> Json:
    return {
        "name": name, "types": ["combinational", kind],
        "pin_groups": [_group("O", "output", kind, value)],
    }


def _ff(name: str, extra_cfg: Json, ctrl: list[tuple[str, str]]) -> Json:
    cfg: Json = {
        "state": "IQ", "neg_state": "IQN", "data_category": "generic", "data_identifier": "INIT",
        "next_state": "D", "clocked_on": "C",
    }
    cfg.update(extra_cfg)
    groups = [_group("C", "input", "clock"), _group("D", "input", "data")]
    groups += [_group(p, "input", t) for p, t in ctrl]
    groups.append(_group("Q", "output", "state", "IQ"))
    return {"name": name, "types": ["sequential", "ff"], "ff_config": cfg, "pin_groups": groups}


def lut6() -> Json:
    """Library for the f2 floor; the FF has a clock and a data pin, no enable or reset."""
    cells = [_lut(k) for k in range(1, 7)]
    cells.append(_ff("FF", {}, []))
    cells += [_const("GND", "ground", "0b0"), _const("VCC", "power", "0b1")]
    return {"version": 4, "library": "LOKI_LUT6", "cells": cells}


def cmos6() -> Json:
    """Library for the f3 floor; DFFSR has asynchronous set and reset, set wins (cmos_cells.v)."""
    cells = [
        _comb("BUF", "c_buffer", ["A"], "Y", "A"),
        _comb("INV", "c_inverter", ["A"], "Y", "(! A)"),
        _comb("NAND2", "c_nand", ["A", "B"], "Y", "(! (A & B))"),
        _comb("NOR2", "c_nor", ["A", "B"], "Y", "(! (A | B))"),
        _ff("DFF", {}, []),
        _ff("DFFSR", {"clear_on": "R", "preset_on": "S", "state_clear_preset": "H",
                      "neg_state_clear_preset": "L"}, [("S", "set"), ("R", "reset")]),
        _const("GND", "ground", "0b0"),
        _const("VCC", "power", "0b1"),
    ]
    return {"version": 4, "library": "LOKI_CMOS6", "cells": cells}


LIBRARIES = {"lut6": lut6, "cmos6": cmos6}


def render(name: str) -> str:
    """The text of the committed ``<name>.hgl`` (4-space indent, trailing newline)."""
    return json.dumps(LIBRARIES[name](), indent=4) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in LIBRARIES:
        sys.stderr.write("usage: python -m loki.hal.hgl lut6|cmos6\n")
        return 2
    sys.stdout.write(render(argv[0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
