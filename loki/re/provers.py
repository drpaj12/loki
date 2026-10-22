"""Provers for claims (L1 spec 8): exact truth tables and Odin III ``cone_check``."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from loki.odin import error_reason, odin_module
from loki.re.claims import CONE_TEMPLATES, DONT_CARE, REFS, Claim, template_args
from loki.re.fngraph import FnGraph
from loki.re.sim import cone, simulate

EXHAUSTIVE_MAX = 16
SAMPLE_N = 4096


@dataclass(frozen=True)
class Verdict:
    """``verdict`` in equivalent differs unproven invalid error."""

    verdict: str
    engine: str
    detail: str
    cex: dict[str, int] = field(default_factory=dict)


def parse_cex(text: str) -> dict[str, int]:
    """``"A[0]=1,B[2]=0"`` to ``{"A[0]": 1, "B[2]": 0}``; empty text gives ``{}``."""
    out: dict[str, int] = {}
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        name, _, value = item.partition("=")
        out[name.strip()] = int(value)
    return out


def bit_name(port: str, bit: int, width: int) -> str:
    """The template port bit as ``cone_check`` names it (``PORT`` alone for a one-bit port)."""
    return port if width == 1 else f"{port}[{bit}]"


def _input_nets(claim: Claim) -> list[int]:
    seen: dict[int, None] = {}
    for _, nets in claim.inputs:
        for net in nets:
            seen.setdefault(net)
    return list(seen)


def _port_value(nets: tuple[int, ...], values: dict[int, int], k: int) -> int:
    return sum(((values.get(n, 0) >> k) & 1) << i for i, n in enumerate(nets))


def cex_ports(claim: Claim, cex: dict[str, int]) -> dict[str, int]:
    """Integer value per input port of a counterexample over port bits (missing bits are 0)."""
    out: dict[str, int] = {}
    for port, nets in claim.inputs:
        value = 0
        for i in range(len(nets)):
            value |= cex.get(bit_name(port, i, len(nets)), 0) << i
        out[port] = value
    return out


class TruthTableProver:
    """Enumerates (at most ``EXHAUSTIVE_MAX`` variables) or samples the claim's cone."""

    def prove(self, graph: FnGraph, claim: Claim, rng: random.Random) -> Verdict:
        ref = REFS[claim.op]
        dont_care = DONT_CARE.get(claim.op)
        params = dict(claim.params)
        outs = [n for _, nets in claim.outputs for n in nets]
        inputs = _input_nets(claim)
        cells, side = cone(graph, frozenset(inputs), outs, frozenset())
        variables = inputs + sorted(side)
        exact = len(variables) <= EXHAUSTIVE_MAX
        count = 1 << len(variables) if exact else SAMPLE_N
        values: dict[int, int] = {}
        for j, net in enumerate(variables):
            if exact:
                values[net] = _column(j, count)
            else:
                values[net] = rng.getrandbits(count)
        nets = simulate(graph, cells, values, count)
        for k in range(count):
            ins = {port: _port_value(ns, nets, k) for port, ns in claim.inputs}
            if dont_care is not None and dont_care(params, ins):
                continue
            want = ref(params, ins)
            for port, ns in claim.outputs:
                if _port_value(ns, nets, k) != want[port]:
                    return Verdict("differs", "truth_table", "exact" if exact else "sampled",
                                   _cex(claim, variables, nets, k))
        if exact:
            return Verdict("equivalent", "truth_table", "exact", {})
        return Verdict("unproven", "truth_table", "sampled", {})


def _column(j: int, count: int) -> int:
    """Bit ``k`` is bit ``j`` of ``k``, for ``k`` below ``count`` (a power of two)."""
    half = 1 << j
    unit = ((1 << half) - 1) << half
    period = half << 1
    return unit * (((1 << count) - 1) // ((1 << period) - 1))


def _cex(claim: Claim, variables: list[int], nets: dict[int, int], k: int) -> dict[str, int]:
    bound: dict[int, str] = {}
    for port, ns in claim.inputs:
        for i, net in enumerate(ns):
            bound.setdefault(net, bit_name(port, i, len(ns)))
    return {bound.get(net, f"n{net}"): (nets.get(net, 0) >> k) & 1 for net in variables}


class ConeCheckProver:
    """One scratch copy of level 0; claims are proved one at a time with ``cone_check``."""

    def __init__(self, level0: Any, graph: FnGraph, timeout: int) -> None:
        self.level0 = level0
        self.graph = graph
        self.timeout = timeout
        self.counter = 0
        self.work: Any = None
        self._open()

    def _open(self) -> None:
        self.work = self.level0.copy()
        self.nodes = {int(n.id): n for n in self.work.top().nodes()}

    def close(self) -> None:
        """Release the scratch copy."""
        if self.work is not None:
            self.work.close()
            self.work = None

    def next_key(self) -> str:
        """A fresh ``lk<k>`` attribute key."""
        self.counter += 1
        return f"lk{self.counter}"

    def _boundary(self, cells: tuple[int, ...]) -> set[int]:
        group = set(cells)
        pos = set(self.graph.pos)
        out: set[int] = set()
        for cid in cells:
            cell = self.graph.cells[cid]
            for net in cell.ins:
                if net and self.graph.driver.get(net) not in group:
                    out.add(net)
            for net in cell.outs:
                readers = self.graph.readers.get(net, ())
                if net and (net in pos or any(r not in group for r, _ in readers)):
                    out.add(net)
        return out

    def prove(self, claim: Claim, key: str) -> Verdict:
        """``cone_check`` the claim; ``invalid`` without a pass when it cannot bind the group."""
        if claim.op not in CONE_TEMPLATES:
            return Verdict("invalid", "cone_check", f"no template for {claim.op}")
        binding: dict[int, str] = {}
        for ports in (claim.inputs, claim.outputs):
            for port, nets in ports:
                for i, net in enumerate(nets):
                    if net in binding:
                        return Verdict("invalid", "cone_check", "net bound twice")
                    binding[net] = bit_name(port, i, len(nets))
        outs = [n for _, nets in claim.outputs for n in nets]
        cells, side = cone(self.graph, frozenset(_input_nets(claim)), outs, frozenset())
        if side:
            return Verdict("invalid", "cone_check", "side input")
        if not cells:
            return Verdict("invalid", "cone_check", "empty cone")
        if self._boundary(cells) != set(binding):
            return Verdict("invalid", "cone_check", "boundary nets differ from the claim")
        return self._run(claim, key, cells, binding)

    def _run(
        self, claim: Claim, key: str, cells: tuple[int, ...], binding: dict[int, str]
    ) -> Verdict:
        mod = odin_module()
        o = mod.default()
        module = self.work.top()
        try:
            for cid in cells:
                self.nodes[cid].set_attr(key, "1")
            for net, port in binding.items():
                module.net(self.graph.names[net]).set_attr("odin3:bind", port)
            args = f"-attr {key}=1 {template_args(claim)} -timeout {self.timeout}"
            with o.capture_log() as records:
                try:
                    self.work.run_pass("cone_check", args)
                except mod.Odin3Error as err:
                    reason = error_reason(err, records, o.lib)
                    self.close()
                    self._open()
                    return Verdict("error", "cone_check", reason)
            verdict = str(module.attr("odin3:cone_check"))
            cex = str(module.attr("odin3:cone_cex") or "") if verdict == "differs" else ""
        except mod.Odin3Error as err:
            self.close()
            self._open()
            return Verdict("error", "cone_check", str(err))
        if verdict == "unproven":
            return Verdict("unproven", "cone_check", "timeout")
        return Verdict(verdict, "cone_check", "", parse_cex(cex))


def prove(claim: Claim, graph: FnGraph, cc: ConeCheckProver | None, rng: random.Random) -> Verdict:
    """``cone_check`` first when the claim has a template; the truth table on ``invalid``."""
    if cc is not None and claim.op in CONE_TEMPLATES:
        verdict = cc.prove(claim, cc.next_key())
        if verdict.verdict != "invalid":
            return verdict
    return TruthTableProver().prove(graph, claim, rng)
