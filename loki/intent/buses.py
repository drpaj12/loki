"""A5: buses with a bit order and a purpose link.

A bus is a list of nets that carry one word. Three sources, in this order: nets named
``base[i]`` with consecutive indices (bit order: index, bit 0 first, ``order_source`` ``index``);
the state, next-state and parallel-load nets of a claim (bit order of the claim, LSB first,
``claim``); the slices of an overlay bus claim (``slices``). Each bus lists what it is *for*:
the state of FSM h2, the value of counter h7, the operand of adder h9. Buses that name the same
nets in the same order are one. Pure on claim dicts and names.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

_INDEXED = re.compile(r"^(.*)\[(\d+)\]$")
_STATE = {"fsm": "state of the state machine", "counter": "value of the counter",
          "shift_reg": "contents of the shift register", "lfsr": "state of the LFSR",
          "register": "contents of the register"}
_OPERAND = {"A": "operand A", "B": "operand B", "Y": "result"}
_ARITH = frozenset({"adder", "subtractor", "adder_cin", "comparator"})


def index_groups(names: Iterable[str]) -> dict[str, list[str]]:
    """``{base: [base[i0], base[i1], ...]}`` ascending, for bases with two or more consecutive
    indices."""
    found: dict[str, dict[int, str]] = {}
    for name in sorted(set(names)):
        m = _INDEXED.match(name)
        if m is not None:
            found.setdefault(m.group(1), {})[int(m.group(2))] = name
    out: dict[str, list[str]] = {}
    for base, by in sorted(found.items()):
        idx = sorted(by)
        run: list[int] = []
        for i in idx:
            run = [*run, i] if run and i == run[-1] + 1 else [i]
            if len(run) >= 2:
                out[base] = [by[j] for j in run]
    return out


def _links(bits: list[str], claims: list[dict[str, Any]]) -> list[dict[str, str]]:
    want = set(bits)
    out: list[dict[str, str]] = []
    for c in claims:
        nets = c["nets"]
        if c["kind"] in _STATE and want <= set(nets.get("q", [])):
            out.append({"claim": c["id"], "text": f"{_STATE[c['kind']]} {c['id']}"})
        if c["kind"] in _STATE and want & set(nets.get("d", [])) and len(want) > 1:
            out.append({"claim": c["id"], "text": f"next-state input of {c['id']}"})
        for m in c.get("facts", {}).get("modes", []):
            if m["label"] == "load-const" and want <= set(m.get("data", [])):
                out.append({"claim": c["id"], "text": f"parallel load word of {c['id']}"})
        if c["kind"] in _ARITH:
            for port, label in _OPERAND.items():
                if want <= set(nets.get(port.lower(), nets.get(port, []))):
                    out.append({"claim": c["id"], "text": f"{label} of {c['kind']} {c['id']}"})
    return out


def _p_of(links: list[dict[str, str]], claims: list[dict[str, Any]]) -> float | None:
    by = {c["id"]: c.get("p") for c in claims}
    ps: list[float] = [float(p) for x in links if (p := by.get(x["claim"])) is not None]
    return max(ps) if ps else None


def _claim_lists(claims: list[dict[str, Any]]) -> Iterable[tuple[list[str], str]]:
    for c in claims:
        if c["source"] == "seq":
            for role in ("q", "d"):
                if len(c["nets"].get(role, [])) >= 2:
                    yield c["nets"][role], "claim"
            for m in c.get("facts", {}).get("modes", []):
                if len(m.get("data", [])) >= 2:
                    yield m["data"], "claim"
        if c["kind"] == "bus":
            slices = sorted((k for k in c["nets"] if k.startswith("slice")),
                            key=lambda k: int(k[5:]))
            bits = [n for k in slices for n in c["nets"][k][:1]]
            if len(bits) >= 2:
                yield bits, "slices"


def find_buses(claims: list[dict[str, Any]], port_names: Iterable[str]) -> list[dict[str, Any]]:
    """The buses of a run, each ``{id, bits, width, order_source, base, links, p, evidence}``."""
    names = {n for c in claims for ns in c["nets"].values() for n in ns} | set(port_names)
    names |= {n for c in claims for m in c.get("facts", {}).get("modes", []) for n in m["data"]}
    seen: set[tuple[str, ...]] = set()
    out: list[dict[str, Any]] = []

    def add(bits: list[str], source: str, base: str) -> None:
        key = tuple(bits)
        if key in seen or len(set(bits)) != len(bits):
            return
        seen.add(key)
        links = _links(bits, claims)
        out.append({"id": f"b{len(out) + 1}", "bits": bits, "width": len(bits),
                    "order_source": source, "base": base, "links": links,
                    "p": _p_of(links, claims),
                    "evidence": "declared" if source == "index" else "derived"})

    for base, bits in index_groups(names).items():
        add(bits, "index", base)
    for bits, source in _claim_lists(claims):
        add(list(bits), source, "")
    return out
