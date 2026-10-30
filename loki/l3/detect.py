"""L3 v0 single-pattern detector: a signature interpreter over L1 claims (never reads a label)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loki.l3.catalogue import Entry
from loki.l3.netlist import Netlist

Claim = dict[str, Any]
CONTROL_KEYS = frozenset({"q", "clk", "rst", "rst_n", "srst", "arst"})
ANY_SEQ = ("fsm", "counter", "shift_reg", "lfsr", "register", "ff_en", "ff_srst")


@dataclass
class Instance:
    entry: str
    claims: list[str]
    q: frozenset[str]
    inputs: frozenset[str]
    p: float
    nets: frozenset[str] = field(default_factory=frozenset)


@dataclass
class Detection:
    target: str
    instances: dict[str, list[Instance]]
    reason: dict[str, str]  # entry -> "ok" | "l1_absent" | "l3_composition"

    def found(self, entry: str) -> bool:
        return bool(self.instances.get(entry))


def q_nets(claim: Claim) -> frozenset[str]:
    nets = claim.get("nets", {})
    out: list[str] = []
    for key in ("q", "Q"):
        out += nets.get(key, [])
    return frozenset(out or claim.get("facts", {}).get("q", []))


def input_nets(claim: Claim) -> frozenset[str]:
    """Every claim net except state, clock and reset nets."""
    nets = claim.get("nets", {})
    return frozenset(n for k, v in nets.items() if k.lower() not in CONTROL_KEYS
                     for n in v if isinstance(n, str))


def prob(claim: Claim) -> float:
    p = claim.get("p")
    return 1.0 if p is None else float(p)


def usable(claims: list[Claim], min_p: float) -> list[Claim]:
    return [c for c in claims if c.get("status") != "rejected" and prob(c) >= min_p]


def dedupe(items: list[Claim]) -> list[Claim]:
    """Merge claims that share a state net: the highest posterior stays."""
    kept: list[Claim] = []
    for c in sorted(items, key=lambda c: (-prob(c), c["id"])):
        qs = q_nets(c)
        if qs and any(qs & q_nets(k) for k in kept):
            continue
        kept.append(c)
    return sorted(kept, key=lambda c: c["id"])


def _count(spec: Any, tuning: dict[str, Any]) -> int:
    return int(tuning[spec] if isinstance(spec, str) else spec)


def _compare_ok(claims: list[Claim], q: frozenset[str], kinds: list[str],
                back: frozenset[str] | None, net: Netlist | None, cap: int) -> bool:
    """A compare claim reads the state nets; with ``back`` (and a netlist) its result must also
    reach the role's own input nets within ``cap`` cells (terminal count reload or stop)."""
    for c in claims:
        if c["kind"] in kinds:
            ins = {n for k, v in c.get("nets", {}).items() if k != "Y" for n in v}
            if not q & ins:
                continue
            if back is None or net is None:
                return True
            if set(net.forward(c.get("nets", {}).get("Y", []), cap)) & back:
                return True
    return False


def _feedback(claim: Claim, net: Netlist | None, tuning: dict[str, Any],
              narrow_operand: bool) -> frozenset[str] | None:
    if net is None:
        return None
    nets = claim.get("nets", {})
    a, b = set(nets.get("A", [])), set(nets.get("B", []))
    narrow = [x for x in (a, b) if len(x) <= 1 or x <= net.consts]
    if narrow_operand and not narrow:
        return None  # an accumulator: both operands are wide and not constant
    qs = net.feedback_q(nets.get("Y", []), a | b, int(tuning["max_depth"]))
    return frozenset(qs) or None


class Detector:
    def __init__(self, entries: dict[str, Entry], tuning: dict[str, Any]) -> None:
        self.entries = entries
        self.tuning = tuning

    def run(self, claims: list[Claim], target: str, net: Netlist | None = None) -> Detection:
        pool = usable(claims, float(self.tuning.get("min_p", 0.0)))
        by_kind: dict[str, list[Claim]] = {}
        for c in pool:
            by_kind.setdefault(c["kind"], []).append(c)
        det = Detection(target, {}, {})
        for eid, entry in self.entries.items():
            found, reason = self._entry(entry, by_kind, pool, net, det)
            det.reason[eid] = "ok" if found else reason
            if found:
                det.instances[eid] = found
        return det

    def _entry(self, entry: Entry, by_kind: dict[str, list[Claim]], pool: list[Claim],
               net: Netlist | None, det: Detection) -> tuple[list[Instance], str]:
        out: list[Instance] = []
        reason = "l1_absent"
        for sig in entry.signatures(det.target):
            if any(det.found(f) for f in sig.get("forbid", ())):
                reason = "l3_composition" if reason == "l1_absent" else reason
                continue
            got, state = self._signature(entry.id, sig, by_kind, pool, net)
            out += got
            if state == "l3_composition":
                reason = state
        return out, reason

    def _signature(self, eid: str, sig: dict[str, Any], by_kind: dict[str, list[Claim]],
                   pool: list[Claim], net: Netlist | None) -> tuple[list[Instance], str]:
        absent = sig.get("absent")
        if absent is not None:
            ok = not any(by_kind.get(k) for k in absent)
            if sig.get("no_latches") and net is not None:
                ok = ok and not net.latches
            return ([Instance(eid, [], frozenset(), frozenset(), 1.0)] if ok else []), \
                "l3_composition"
        if sig.get("latches"):
            has = net is not None and bool(net.latches)
            return ([Instance(eid, [], frozenset(), frozenset(), 1.0)] if has else []), \
                "l1_absent"
        parts = sig["parts"]
        pri = parts[0]
        cands = dedupe([c for k in pri["kinds"] for c in by_kind.get(k, [])])
        if not cands:
            return [], "l1_absent"
        others = [[c for k in p["kinds"] for c in by_kind.get(k, [])] for p in parts[1:]]
        need = [_count(p.get("min", 1), self.tuning) for p in parts[1:]]
        if any(len(o) < n for n, o in zip(need, others, strict=True)):
            return [], "l1_absent"
        if pri.get("group"):
            if len(cands) < _count(pri.get("min", 1), self.tuning):
                return [], "l3_composition"
            ids = [c["id"] for c in cands] + [c["id"] for o in others for c in o]
            return [Instance(eid, ids, frozenset().union(*(q_nets(c) for c in cands)),
                             frozenset(), min(prob(c) for c in cands))], "ok"
        return self._per_claim(eid, sig, cands, pool, net), "l3_composition"

    def _per_claim(self, eid: str, sig: dict[str, Any], cands: list[Claim], pool: list[Claim],
                   net: Netlist | None) -> list[Instance]:
        out: list[Instance] = []
        for c in cands:
            q = q_nets(c)
            ids = [c["id"]]
            c_in = input_nets(c)
            ok = True
            for con in sig.get("constraints", ()):
                if con["type"] == "compare_on":
                    back = c_in if con.get("reaches_back") else None
                    ok = ok and _compare_ok(pool, q, con["kinds"], back, net,
                                            int(self.tuning["max_depth"]))
                elif con["type"] == "feedback":
                    fq = _feedback(c, net, self.tuning, bool(con.get("narrow_operand")))
                    ok = ok and fq is not None
                    q = fq or q
            if ok:
                out.append(Instance(eid, ids, q, input_nets(c), prob(c)))
        return out
