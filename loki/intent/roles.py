"""A4: control or datapath, per net and per claim, with a confidence.

Sinks: a net is *control* when it steers a claimed piece: the select of a mux, the enable, reset
or load of a counter, shift register or register, the inputs that decide a state machine's next
state, and the state bits of the machine itself. A net is *data* when it reaches a primary output
or is the serial input or parallel word of a shift register or register. Roles flow backwards
through logic and flip-flops (a net takes the roles of everything that reads it), as in the L0
role fixpoint (L0 spec 7.5); a net with both is ``mixed``, one with neither ``unknown``.

The confidence of a control net is the largest probability of a claim whose sink it is. A data
net's role is a fact about the netlist (it reaches an output), so it carries no probability.
Pure on an ``FnGraph`` and claim dicts.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from loki.re.fngraph import FnGraph

CONTROL, DATA = "control", "data"
SINK_ROLES = frozenset({"en", "rst", "load", "S", "sel", "rst_net"})


def _data_nets(claim: dict[str, Any]) -> set[str]:
    facts = claim.get("facts", {})
    out = {n for m in facts.get("modes", []) for n in m.get("data", [])}
    out.update(claim["nets"].get("x", []))
    return out


def sinks(claims: list[dict[str, Any]]) -> dict[str, float | None]:
    """Control sink nets of the claims, each with the largest ``p`` of a claim that has it (None
    when no such claim has a probability)."""
    out: dict[str, float | None] = {}

    def add(net: str, p: float | None) -> None:
        old = out.get(net)
        out[net] = p if old is None else (old if p is None else max(old, p))

    for c in claims:
        p = c.get("p")
        data = _data_nets(c)
        for role, nets in c["nets"].items():
            if role in SINK_ROLES or (role == "c" and c["kind"] in ("fsm", "register", "counter",
                                                                     "shift_reg", "lfsr")):
                for n in nets:
                    if n not in data:
                        add(n, p)
        if c["kind"] == "fsm":
            for n in c["nets"].get("q", []):
                add(n, p)
    return out


def owners(claims: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Per control sink net, the wires of the claims that own it: the reads of a sink inside its
    own claim carry nothing back to it (an enable does not become data because the counter it
    enables reaches an output)."""
    out: dict[str, set[str]] = {}
    for c in claims:
        for name in sinks([c]):
            out.setdefault(name, set()).update(c.get("wires", []))
    return out


def _fixpoint(
    graph: FnGraph, seeds: dict[int, set[str]], own: dict[str, set[str]]
) -> dict[int, set[str]]:
    kinds: dict[int, set[str]] = {n: set(s) for n, s in seeds.items()}
    work = deque(sorted(kinds))
    while work:
        net = work.popleft()
        drv = graph.driver.get(net)
        if drv is None:
            continue
        here = graph.names.get(net, f"net{net}")
        for src in graph.cells[drv].ins:
            if src and here in own.get(graph.names.get(src, f"net{src}"), ()):
                continue
            if src and not kinds.get(src, set()) >= kinds[net]:
                kinds.setdefault(src, set()).update(kinds[net])
                work.append(src)
    return kinds


def assign_roles(graph: FnGraph, claims: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """``{net name: {"role", "p"}}`` for every net with a role, and ``role`` / ``role_p`` set on
    each claim: a state machine is control; others take the role of their state nets (``unknown``
    without state nets)."""
    by_name = {name: net for net, name in graph.names.items()}
    ctrl = sinks(claims)
    seeds: dict[int, set[str]] = {}
    for name in ctrl:
        if name in by_name:
            seeds.setdefault(by_name[name], set()).add(CONTROL)
    for net in graph.pos:
        seeds.setdefault(net, set()).add(DATA)
    for c in claims:
        for name in _data_nets(c):
            if name in by_name:
                seeds.setdefault(by_name[name], set()).add(DATA)
    kinds = _fixpoint(graph, seeds, owners(claims))
    roles: dict[str, dict[str, Any]] = {}
    for net, ks in sorted(kinds.items()):
        label = graph.names.get(net)
        if label is None:
            continue
        role = "mixed" if ks == {CONTROL, DATA} else ("control" if CONTROL in ks else "datapath")
        p = ctrl.get(label)
        roles[label] = {"role": role, "p": None if p is None else round(p, 6)}
    _claim_roles(claims, roles)
    return roles


def _claim_roles(claims: list[dict[str, Any]], roles: dict[str, dict[str, Any]]) -> None:
    for c in claims:
        if c["kind"] == "fsm":
            c["role"], c["role_p"] = "control", c.get("p")
            continue
        got = [roles[n] for n in c["nets"].get("q", []) if n in roles]
        if not got:
            c["role"], c["role_p"] = "unknown", None
            continue
        kinds = {str(g["role"]) for g in got}
        c["role"] = kinds.pop() if len(kinds) == 1 else "mixed"
        ps = [g["p"] for g in got if g["p"] is not None]
        c["role_p"] = min(ps) if ps and c["role"] == "control" else None
