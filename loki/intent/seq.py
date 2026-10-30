"""A1 and A2: counters, shift registers, LFSRs and state machines from sequential groups.

Counters, shift registers and LFSRs reuse the classifier of ``loki.re.detectors.seqfn`` on a
context where every cell is free; state machines use ``loki.intent.fsm``. A reset that forces one
state is found first and tied off, so the classifier sees the running behaviour; the claim names
the reset net, its active level and the state it forces. Each claim says whether the
classification came from an exhaustive transition table (``exact``) or from sampled rows.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from loki.intent.fsm import Fsm, cone_of, find_reset, read_fsm
from loki.intent.groups import Group, sequential_groups
from loki.intent.lower import tie_net
from loki.intent.modes import Mode, mode_table
from loki.re.bayes import load_calib
from loki.re.detectors import RoundContext
from loki.re.detectors.seqfn import Group as SeqGroup
from loki.re.detectors.seqfn import SeqfnDetector
from loki.re.fngraph import FnGraph
from loki.re.overlay import Overlay
from loki.re.view import View

_INDEXED = re.compile(r"^(.*)\[(\d+)\]$")


@dataclass(frozen=True)
class SeqClaim:
    """One sequential claim. ``q`` and ``d`` are LSB first; ``nets`` maps a role (``en``, ``rst``,
    ``x``, ``load``, ``p``, ``c``) to net ids; ``fsm`` is set for ``kind == 'fsm'``."""

    kind: str
    q: tuple[int, ...]
    d: tuple[int, ...]
    cells: frozenset[int]
    params: dict[str, int | str]
    nets: dict[str, tuple[int, ...]]
    exact: bool
    fsm: Fsm | None = None
    asynchronous: bool = False
    tags: dict[str, str] = field(default_factory=dict)
    modes: tuple[Mode, ...] = ()


def fresh_context(graph: FnGraph, overlay: Overlay | None = None, seed: int = 1) -> RoundContext:
    """A round-1 context over ``graph`` with every cell free and the defaults calibration."""
    return RoundContext(
        round=1, floor="f3", graph=graph, view=View.level0(graph),
        overlay=overlay or Overlay(), rng=lambda p: random.Random(f"{seed}:{p}"),
        calib=load_calib(None),
    )


def name_order(graph: FnGraph, ffs: frozenset[int]) -> tuple[int, ...]:
    """The flip-flops by the index of their Q net name (``q[3]``) when all share one base name and
    the indices are distinct; else by cell id."""
    keyed: list[tuple[int, int]] = []
    bases: set[str] = set()
    for c in ffs:
        m = _INDEXED.match(graph.names.get(graph.cells[c].outs[0], ""))
        if m is None:
            return tuple(sorted(ffs))
        bases.add(m.group(1))
        keyed.append((int(m.group(2)), c))
    if len(bases) != 1 or len({k for k, _ in keyed}) != len(keyed):
        return tuple(sorted(ffs))
    return tuple(c for _, c in sorted(keyed))


def _reset_of(graph: FnGraph, q: tuple[int, ...]) -> tuple[int, int, int] | None:
    cn = cone_of(graph, q)
    if cn is None:
        return None
    return find_reset(cn, random.Random(f"intent:reset:{min(q)}"))


def _classify(graph: FnGraph, order: tuple[int, ...], asyn: set[int]) -> SeqClaim | None:
    """A counter, shift register or LFSR on ``order`` (reset tied off first)."""
    q = tuple(graph.cells[c].outs[0] for c in order)
    reset = _reset_of(graph, q)
    work = graph if reset is None else tie_net(graph, reset[0], 1 - reset[1])
    ctx = fresh_context(work)
    cands = SeqfnDetector()._group(ctx, SeqGroup(frozenset(order), (order,), True))
    if not cands:
        return _mode_claim(work, order, q, reset, asyn)
    cand = cands[0]
    nets = {k.lower(): v for k, v in cand.nets.items() if k not in ("Q", "D")}
    params = {k: v for k, v in cand.params.items() if k not in ("en", "rst", "x", "load", "taps")}
    if "taps" in cand.params:
        params["taps"] = cand.params["taps"]
    nets.pop("rst", None)
    params.pop("rst_active", None)
    params.pop("rst_value", None)
    if reset is not None:
        nets["rst"] = (reset[0],)
        params["rst_active"] = reset[1]
        params["rst_value"] = reset[2]
    exact = cand.features.get("table") == "exact"
    return SeqClaim(cand.kind, q, tuple(cand.nets["D"]), cand.cells, params, nets, exact, None,
                    bool(set(q) & asyn))


def _mode_claim(graph: FnGraph, order: tuple[int, ...], q: tuple[int, ...],
                reset: tuple[int, int, int] | None, asyn: set[int]) -> SeqClaim | None:
    """A shift register, counter or register whose modes the closed templates do not cover."""
    mt = mode_table(graph, q, f"{min(order)}")
    if mt is None or (mt.kind == "register" and not _contiguous(graph, q)):
        return None
    params: dict[str, int | str] = {"width": len(q), "via": "modes"}
    nets: dict[str, tuple[int, ...]] = {"c": mt.controls}
    if reset is not None:
        nets["rst"] = (reset[0],)
        params["rst_active"] = reset[1]
        params["rst_value"] = reset[2]
    d = tuple(graph.cells[c].ins[0] for c in order)
    return SeqClaim(mt.kind, q, d, frozenset(order), params, nets, True, None, bool(set(q) & asyn),
                    modes=mt.modes)


def _contiguous(graph: FnGraph, q: tuple[int, ...]) -> bool:
    """Whether the Q nets are the bits ``name[i]``, ``i`` consecutive, of one name."""
    found = [_INDEXED.match(graph.names.get(n, "")) for n in q]
    if any(m is None for m in found):
        return False
    pairs = [(m.group(1), int(m.group(2))) for m in found if m is not None]
    return len({b for b, _ in pairs}) == 1 and [i for _, i in pairs] == list(
        range(pairs[0][1], pairs[0][1] + len(pairs)))


def _single_ok(graph: FnGraph, fsm: Fsm) -> bool:
    """A one-flip-flop machine is claimed only when it has a reset, every control is a primary
    input and the flip-flop is not a hold-or-load register (a flip-flop with enable)."""
    pis = set(graph.pis)
    if not fsm.controls or any(n not in pis for n in fsm.controls):
        return False
    return not _register_like(fsm)


def _register_like(fsm: Fsm) -> bool:
    """True when one control ``e`` exists with: ``e`` at one level holds the state and ``e`` at
    the other makes the next state independent of the state (a flip-flop with enable)."""
    by: dict[tuple[int, int], int] = {}
    for t in fsm.transitions:
        for cv in range(1 << len(fsm.controls)):
            if _holds(t.cond, fsm.controls, cv):
                by[(t.src, cv)] = t.dst
    for j in range(len(fsm.controls)):
        for level in (0, 1):
            hold = all(by[(s, cv)] == s for (s, cv) in by if ((cv >> j) & 1) == level)
            free = all(by[(0, cv)] == by[(1, cv)] for cv in range(1 << len(fsm.controls))
                       if ((cv >> j) & 1) != level and (0, cv) in by and (1, cv) in by)
            if hold and free:
                return True
    return False


def _holds(cond: tuple[tuple[tuple[int, int], ...], ...], nets: tuple[int, ...], cv: int) -> bool:
    value = {n: (cv >> i) & 1 for i, n in enumerate(nets)}
    return any(all(value[n] == pol for n, pol in prod) for prod in cond)


def _fsm_claim(graph: FnGraph, order: tuple[int, ...], asyn: set[int]) -> SeqClaim | None:
    q = tuple(graph.cells[c].outs[0] for c in order)
    fsm = read_fsm(graph, q, f"{min(order)}")
    if fsm is None or (len(q) == 1 and (fsm.reset is None or not _single_ok(graph, fsm))):
        return None
    d = tuple(graph.cells[c].ins[0] for c in order)
    params: dict[str, int | str] = {"width": len(q), "states": len(fsm.states),
                                    "encoding": fsm.encoding}
    nets = {"c": fsm.controls}
    if fsm.reset is not None:
        nets["rst"] = (fsm.reset[0],)
        params["rst_active"] = fsm.reset[1]
        params["rst_state"] = fsm.reset[2]
    return SeqClaim("fsm", q, d, frozenset(order), params, nets, True, fsm, bool(set(q) & asyn))


def _claim_group(graph: FnGraph, group: Group, asyn: set[int]) -> SeqClaim | None:
    order = name_order(graph, group.ffs)
    claim = _classify(graph, order, asyn) if len(order) > 1 else None
    if claim is None and group.is_loop:
        claim = _fsm_claim(graph, order, asyn)
    return claim


def controls_ok(graph: FnGraph, claim: SeqClaim, claimed: set[int]) -> bool:
    """Whether every control net of ``claim`` is something other than the state bit of an
    unclaimed flip-flop. A group that is steered by flip-flops no claim explains is a fragment of
    a larger machine (a few bits of a BCD counter), and a claim about it would mislead."""
    for role, nets in claim.nets.items():
        if role == "rst":
            continue
        for n in nets:
            drv = graph.driver.get(n)
            if drv is not None and graph.cells[drv].kind == "ff" and n not in claimed:
                return False
    return True


def sequential_claims(graph: FnGraph, asyn: set[int] | None = None) -> list[SeqClaim]:
    """The counter / shift register / LFSR / FSM claims of ``graph`` (already lowered). Groups are
    tried largest first and a flip-flop belongs to at most one claim; a group steered by the state
    bits of another group is retried until the claims stop growing."""
    out: list[SeqClaim] = []
    used: set[int] = set()
    claimed: set[int] = set()
    grew = True
    while grew:
        grew = False
        for group in sequential_groups(graph, frozenset(used)):
            if group.ffs & used:
                continue
            claim = _claim_group(graph, group, asyn or set())
            if claim is not None and controls_ok(graph, claim, claimed):
                out.append(claim)
                used |= group.ffs
                claimed |= set(claim.q)
                grew = True
    return sorted(out, key=lambda c: min(c.cells))
