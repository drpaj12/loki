"""Functional claims and their reference functions (L1 spec 8). Pure."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Claim:
    """``op`` over ``inputs`` and ``outputs``: ``(port, nets)`` pairs, nets LSB first."""

    op: str
    params: tuple[tuple[str, int | str], ...]
    inputs: tuple[tuple[str, tuple[int, ...]], ...]
    outputs: tuple[tuple[str, tuple[int, ...]], ...]

    def param(self, name: str) -> int | str:
        """The value of parameter ``name`` (KeyError when absent)."""
        for key, value in self.params:
            if key == name:
                return value
        raise KeyError(name)


Params = Mapping[str, int | str]
Ins = Mapping[str, int]
Ref = Callable[[Params, Ins], dict[str, int]]


def _mask(width: int) -> int:
    return (1 << width) - 1


def _w(params: Params, name: str) -> int:
    value = params[name]
    if not isinstance(value, int):
        raise ValueError(f"parameter {name} is not an integer")
    return value


def _add(p: Params, i: Ins) -> dict[str, int]:
    return {"Y": (i["A"] + i["B"]) & _mask(_w(p, "Y_WIDTH"))}


def _add_cin(p: Params, i: Ins) -> dict[str, int]:
    return {"Y": (i["A"] + i["B"] + i["CI"]) & _mask(_w(p, "Y_WIDTH"))}


def _sub(p: Params, i: Ins) -> dict[str, int]:
    return {"Y": (i["A"] - i["B"]) & _mask(_w(p, "Y_WIDTH"))}


def _cmp(fn: Callable[[int, int], bool]) -> Ref:
    def ref(_p: Params, i: Ins) -> dict[str, int]:
        return {"Y": int(fn(i["A"], i["B"]))}

    return ref


def _eq_const(p: Params, i: Ins) -> dict[str, int]:
    return {"Y": int(i["A"] == _w(p, "C"))}


def _mux2(_p: Params, i: Ins) -> dict[str, int]:
    return {"Y": i["B"] if i["S"] else i["A"]}


def _muxn(p: Params, i: Ins) -> dict[str, int]:
    """``Y = D[S]`` with ``D`` an ``N``-bit vector; a select ``>= N`` gives 0 (don't-care)."""
    if i["S"] >= _w(p, "N"):
        return {"Y": 0}
    return {"Y": (i["D"] >> i["S"]) & 1}


def _muxn_dont_care(p: Params, i: Ins) -> bool:
    return i["S"] >= _w(p, "N")


def _counter(p: Params, i: Ins) -> dict[str, int]:
    """Next state of a counter. Optional inputs ``EN`` (default 1) and ``RST`` (default 0).

    Parameters: ``width``, ``dir`` (``up`` or ``down``), ``modulus`` (0 for ``2**width``),
    ``rst_value``. Reset wins over enable.
    """
    width = _w(p, "width")
    q = i["Q"]
    if i.get("RST", 0):
        return {"D": _w(p, "rst_value") & _mask(width)}
    if not i.get("EN", 1):
        return {"D": q}
    mod = _w(p, "modulus")
    if p["dir"] == "down":
        nxt = (mod - 1 if mod else _mask(width)) if q == 0 else q - 1
    else:
        nxt = 0 if mod and q == mod - 1 else (q + 1) & _mask(width)
    return {"D": nxt & _mask(width)}


def _shift(p: Params, i: Ins) -> dict[str, int]:
    """Next state of a shift register with serial input ``X`` (and optional ``EN``)."""
    width = _w(p, "width")
    q = i["Q"]
    if not i.get("EN", 1):
        return {"D": q}
    x = i["X"] & 1
    if p["dir"] == "l":
        return {"D": ((q << 1) | x) & _mask(width)}
    return {"D": (q >> 1) | (x << (width - 1))}


def _lfsr(p: Params, i: Ins) -> dict[str, int]:
    """Fibonacci LFSR: shift left, the new bit 0 is the parity of ``Q & taps``."""
    width = _w(p, "width")
    q = i["Q"]
    fb = bin(q & _w(p, "taps")).count("1") & 1
    return {"D": ((q << 1) | fb) & _mask(width)}


REFS: dict[str, Ref] = {
    "add": _add,
    "add_cin": _add_cin,
    "sub": _sub,
    "eq": _cmp(lambda a, b: a == b),
    "ne": _cmp(lambda a, b: a != b),
    "lt": _cmp(lambda a, b: a < b),
    "le": _cmp(lambda a, b: a <= b),
    "gt": _cmp(lambda a, b: a > b),
    "ge": _cmp(lambda a, b: a >= b),
    "eq_const": _eq_const,
    "mux2": _mux2,
    "muxn": _muxn,
    "counter": _counter,
    "counter_en": _add,
    "shift": _shift,
    "lfsr": _lfsr,
}

DONT_CARE: dict[str, Callable[[Params, Ins], bool]] = {"muxn": _muxn_dont_care}

CONE_TEMPLATES: dict[str, str] = {
    "add": "$add",
    "sub": "$sub",
    "eq": "$eq",
    "ne": "$ne",
    "lt": "$lt",
    "le": "$le",
    "gt": "$gt",
    "ge": "$ge",
    "mux2": "$mux",
    "counter_en": "$add",
}


def template_args(claim: Claim) -> str:
    """``-cell <TYPE> -param NAME=VALUE ...`` for ``cone_check``, params sorted by name."""
    parts = [f"-cell {CONE_TEMPLATES[claim.op]}"]
    parts.extend(f"-param {k}={v}" for k, v in sorted(claim.params))
    return " ".join(parts)
