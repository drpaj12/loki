"""Claim dicts (JSON-native) of the intent layer, built from sequential claims and the overlay.

A claim is ``{id, kind, source, status, p, evidence, nets, wires, params, facts, merged}``. Nets
are names (``graph.names`` or ``net<id>``); ``wires`` are the output nets of every cell the claim
covers, so a reader can put a mark on each gate. ``p`` is filled by ``loki.intent.calib``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from loki.intent.boolmin import Product
from loki.intent.modes import Mode
from loki.intent.seq import SeqClaim
from loki.re.commit import fn_text
from loki.re.fngraph import FnGraph
from loki.re.overlay import Hypothesis

Namer = Callable[[int], str]


def namer(graph: FnGraph) -> Namer:
    return lambda n: graph.names.get(n, f"net{n}")


def cond_json(cond: Sequence[Product], name: Namer) -> list[list[list[Any]]]:
    return [[[name(n), pol] for n, pol in prod] for prod in cond]


def wires_of(graph: FnGraph, cells: Sequence[int] | frozenset[int], name: Namer) -> list[str]:
    nets = sorted({n for c in cells for n in graph.cells[c].outs if n})
    return sorted({name(n) for n in nets})


def _modes_json(modes: Sequence[Mode], name: Namer) -> list[dict[str, Any]]:
    return [
        {"label": m.label, "cond": cond_json(m.cond, name),
         "data": [n if isinstance(n, str) else name(n) for n in m.data]}
        for m in modes
    ]


def _counter_facts(sc: SeqClaim, name: Namer) -> dict[str, Any]:
    p = sc.params
    width = int(p["width"])
    modulus = int(p.get("modulus", 0)) or (1 << width)
    out: dict[str, Any] = {"width": width, "dir": str(p.get("dir", "up")), "modulus": modulus,
                           "wrap": int(p.get("wrap", 0))}
    if "rst_value" in p:
        out["start"] = int(p["rst_value"])
    if "en" in sc.nets:
        out["en"] = {"net": name(sc.nets["en"][0]), "active": int(p.get("en_active", 1))}
    return out


def _facts(sc: SeqClaim, name: Namer) -> dict[str, Any]:
    p = sc.params
    out: dict[str, Any] = {"width": len(sc.q), "q": [name(n) for n in sc.q]}
    if sc.kind == "counter" and not sc.modes:
        out.update(_counter_facts(sc, name))
    if sc.kind == "shift_reg" and not sc.modes:
        out["dir"] = str(p["dir"])
        if "x" in sc.nets:
            out["x"] = name(sc.nets["x"][0])
        if "en" in sc.nets:
            out["en"] = {"net": name(sc.nets["en"][0]), "active": int(p.get("en_active", 1))}
    if sc.kind == "lfsr" and "taps" in p:
        out["taps"] = int(p["taps"])
    if sc.modes:
        out["modes"] = _modes_json(sc.modes, name)
    if "rst" in sc.nets:
        out["rst"] = {"net": name(sc.nets["rst"][0]), "active": int(p.get("rst_active", 1)),
                      "value": int(p.get("rst_value", p.get("rst_state", 0)))}
    if sc.fsm is not None:
        out.update(_fsm_facts(sc, name))
    out["async"] = sc.asynchronous
    return out


def _fsm_facts(sc: SeqClaim, name: Namer) -> dict[str, Any]:
    f = sc.fsm
    assert f is not None
    return {
        "states": list(f.states), "encoding": f.encoding, "start": f.start,
        "controls": [name(n) for n in f.controls],
        "transitions": [{"src": t.src, "dst": t.dst, "cond": cond_json(t.cond, name)}
                        for t in f.transitions],
    }


def from_seq(graph: FnGraph, sc: SeqClaim, hid: str, name: Namer) -> dict[str, Any]:
    """The claim dict of a sequential claim; ``p`` is None until calibrated."""
    nets: dict[str, list[str]] = {"q": [name(n) for n in sc.q], "d": [name(n) for n in sc.d]}
    for role, ns in sorted(sc.nets.items()):
        nets[role] = [name(n) for n in ns]
    return {
        "id": hid, "kind": sc.kind, "source": "seq", "status": "proved" if sc.exact else "sampled",
        "p": None, "evidence": "exhaustive" if sc.exact else "sampled",
        "nets": nets, "wires": wires_of(graph, sc.cells, name), "params": dict(sc.params),
        "facts": _facts(sc, name), "merged": [],
    }


def from_overlay(graph: FnGraph, h: Hypothesis, status: str, name: Namer) -> dict[str, Any]:
    """The claim dict of an overlay hypothesis (``p`` is its ``p_comp`` under the run's
    calibration)."""
    proof = h.proof or {}
    proved = proof.get("verdict") == "equivalent"
    return {
        "id": h.id, "kind": h.kind, "source": "overlay",
        "status": "proved" if proved else status, "p": round(h.p_comp, 6),
        "evidence": f"proof:{proof.get('engine', '')}" if proved else "structural",
        "nets": {role: [name(n) for n in ns] for role, ns in sorted(h.nets.items())},
        "wires": wires_of(graph, sorted(h.cells), name),
        "params": {k: v for k, v in sorted(h.params.items()) if k != "rows"},
        "facts": {"fn": fn_text(h)}, "merged": [],
    }
