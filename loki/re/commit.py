"""Commit selected hypotheses to a new level: raise and submod (L1 spec 9.3)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from loki.odin import odin_module
from loki.re.claims import CONE_TEMPLATES, template_args
from loki.re.overlay import KINDS, Evidence, Hypothesis, Overlay
from loki.re.provers import bit_name, boundary_nets
from loki.re.sim import cone

if TYPE_CHECKING:
    from loki.re.fngraph import FnGraph

SM = "loki_sm"
_CMP = {"eq": "==", "ne": "!=", "lt": "<", "le": "<=", "gt": ">", "ge": ">="}


@dataclass(frozen=True)
class CommitResult:
    """``design`` is the new level, ``forms`` the form each committed id took (``raise+submod``,
    ``submod``, ``attrs``), ``failed`` the rejected offenders (``reasons`` holds their status)."""

    design: Any
    forms: dict[str, str]
    failed: tuple[str, ...]
    reasons: dict[str, str] = field(default_factory=dict)


class CommitError(Exception):
    """A pass failed for the hypothesis ``hid``; ``status`` is the Odin III status text."""

    def __init__(self, hid: str, status: str) -> None:
        super().__init__(f"{hid}: {status}")
        self.hid = hid
        self.status = status


def _int(h: Hypothesis, name: str, default: int = 0) -> int:
    value = h.params.get(name, default)
    return value if isinstance(value, int) else default


def _counter_text(h: Hypothesis) -> str:
    mod, wrap = _int(h, "modulus"), _int(h, "wrap")
    if h.params.get("dir") == "down":
        core = f"(Q == 0) ? {mod - 1} : Q - 1" if mod else "Q - 1"
    else:
        core = f"(Q == {mod - 1}) ? {wrap} : Q + 1" if mod else "Q + 1"
    if _int(h, "en"):
        en = "EN" if _int(h, "en_active", 1) else "!EN"
        core = f"{en} ? ({core}) : Q"
    if _int(h, "rst"):
        rst = "RST" if _int(h, "rst_active", 1) else "!RST"
        core = f"{rst} ? {_int(h, 'rst_value')} : ({core})"
    return f"Q <= {core}"


def _shift_text(h: Hypothesis) -> str:
    w = _int(h, "width")
    core = f"{{Q[{w - 2}:0], X}}" if h.params.get("dir") == "l" else f"{{X, Q[{w - 1}:1]}}"
    if _int(h, "en"):
        en = "EN" if _int(h, "en_active", 1) else "!EN"
        core = f"{en} ? {core} : Q"
    return f"Q <= {core}"


def _lfsr_text(h: Hypothesis) -> str:
    w, taps = _int(h, "width"), _int(h, "taps")
    core = f"{{Q[{w - 2}:0], ^(Q & {w}'h{taps:x})}}"
    if _int(h, "en"):
        en = "EN" if _int(h, "en_active", 1) else "!EN"
        core = f"{en} ? {core} : Q"
    return f"Q <= {core}"


def fn_text(h: Hypothesis) -> str:
    """The recovered function as text (spec 9.3), such as ``Y = A + B``."""
    if h.kind == "counter":
        return _counter_text(h)
    if h.kind == "shift_reg":
        return _shift_text(h)
    if h.kind == "lfsr":
        return _lfsr_text(h)
    if h.kind == "fsm":
        states = h.params.get("states")
        return f"fsm: {states} states" if states is not None else f"fsm: {_int(h, 'width')} bits"
    op = h.claim.op if h.claim is not None else ""
    if op == "add":
        return "Y = A + B"
    if op == "add_cin":
        return "Y = A + B + CI"
    if op == "sub":
        return "Y = A - B"
    if op in _CMP:
        return f"Y = (A {_CMP[op]} B)"
    if op in ("eq_const", "ne_const") and h.claim is not None:
        sign = "==" if op == "eq_const" else "!="
        return f"Y = (A {sign} {h.claim.param('C')})"
    if op == "mux2":
        return "Y = S ? B : A"
    if op == "muxn":
        return "Y = D[S]"
    width = max((len(ns) for ns in h.nets.values()), default=0)
    return f"{h.kind}: {width} bits" if width else h.kind


def proof_label(h: Hypothesis) -> str:
    """The ``loki_proof`` value: equivalent, derived (a transfer), unproven or none."""
    p = h.proof
    if p is None:
        return "none"
    if p.get("engine") == "transfer" and p.get("verdict") == "equivalent":
        return "derived"
    if p.get("verdict") in ("equivalent", "unproven"):
        return str(p["verdict"])
    return "none"


def role_of(h: Hypothesis, overlay: Overlay) -> str:
    """Majority role (``control``, ``datapath``, ``mixed``) of the cells of ``h`` from the
    ``role`` hypotheses (spec 7.10); empty when none covers a cell."""
    counts: dict[str, int] = {}
    for rh in overlay.by_kind("role"):
        if not rh.cells <= h.cells or rh.status in ("refuted", "rejected"):
            continue
        if rh.features.get("role_prop") == "mixed":
            role = "mixed"
        else:
            role = "control" if rh.log_odds >= 0 else "datapath"
        counts[role] = counts.get(role, 0) + 1
    if not counts:
        return ""
    return sorted(counts, key=lambda r: (-counts[r], r))[0]


def module_name(h: Hypothesis) -> str:
    return f"{h.kind}_{h.id}"


def _footprint(node: Any, graph: FnGraph, overlay: Overlay) -> frozenset[int]:
    hid = node.attr("loki_hid")
    if hid is not None:
        return overlay.get(hid).cells
    return frozenset(
        graph.line_to_cell[int(s.line)] for s in node.sources() if int(s.line) in graph.line_to_cell
    )


def _raise_binding(h: Hypothesis, graph: FnGraph, overlay: Overlay) -> dict[int, str] | None:
    """The port bit of every boundary net when ``h`` may be raised, else None (spec 9.3 item 1)."""
    claim = h.claim
    if KINDS[h.kind].commit != "raise+submod" or claim is None or claim.op not in CONE_TEMPLATES:
        return None
    proof = h.proof
    if proof is None or proof.get("verdict") != "equivalent":
        return None
    engine = proof.get("engine")
    if engine == "transfer":
        src = overlay.get(proof["from"]).proof
        engine = src.get("engine") if src is not None else None
    if engine != "cone_check":
        return None
    binding: dict[int, str] = {}
    for ports in (claim.inputs, claim.outputs):
        for port, nets in ports:
            for i, net in enumerate(nets):
                if net in binding:
                    return None
                binding[net] = bit_name(port, i, len(nets))
    ins = frozenset(n for _, ns in claim.inputs for n in ns)
    outs = [n for _, ns in claim.outputs for n in ns]
    cells, side = cone(graph, ins, outs, frozenset())
    if side or frozenset(cells) != h.cells:
        return None
    if boundary_nets(graph, cells) != set(binding):
        return None
    return binding


class _Attempt:
    """One commit attempt on one fresh copy of the working level."""

    def __init__(self, working: Any, hyps: Sequence[Hypothesis], overlay: Overlay,
                 graph: FnGraph, timeout: int) -> None:
        self.work = working.copy()
        self.hyps, self.overlay, self.graph, self.timeout = hyps, overlay, graph, timeout
        self.forms: dict[str, str] = {}
        self.groups: dict[str, list[Any]] = {}

    def run(self) -> dict[str, str]:
        mod = odin_module()
        try:
            with mod.default().capture_log():
                self._run()
        except mod.Odin3Error as err:
            raise CommitError("", str(err).split(": ", 1)[-1]) from err
        return self.forms

    def _group(self) -> None:
        top = self.work.top()
        nodes = [
            (n, _footprint(n, self.graph, self.overlay))
            for n in top.nodes() if not str(n.type_name).startswith("$port_")
        ]
        used: set[int] = set()
        for h in self.hyps:
            if KINDS[h.kind].commit in ("no", "attrs"):
                continue
            if self.work.module(module_name(h)) is not None:
                raise CommitError(h.id, f"module {module_name(h)} exists")
            group = [(n, fp) for n, fp in nodes if fp and fp <= h.cells]
            covered: set[int] = set()
            for _, fp in group:
                covered |= fp
            if covered != h.cells or any(int(n.id) in used for n, _ in group):
                raise CommitError(h.id, "footprint not found at this level")
            used.update(int(n.id) for n, _ in group)
            self.groups[h.id] = [n for n, _ in group]

    def _raise(self, h: Hypothesis, serial: int) -> None:
        binding = _raise_binding(h, self.graph, self.overlay)
        group = self.groups[h.id]
        self.forms[h.id] = "submod"
        if binding is None or h.claim is None:
            return
        if any(n.attr("loki_hid") is not None for n in group):
            return
        top = self.work.top()
        key = f"lkc{serial}"
        for node in group:
            node.set_attr(key, "1")
        for net, port in binding.items():
            top.net(self.graph.names[net]).set_attr("odin3:bind", port)
        args = f"-attr {key}=1 {template_args(h.claim)}"
        self.work.run_pass("cone_check", f"{args} -timeout {self.timeout}")
        if top.attr("odin3:cone_check") != "equivalent":
            return
        self.work.run_pass("raise", args)
        y0 = h.claim.outputs[0][1][0]
        driver = top.net(self.graph.names[y0]).driver()
        if driver is None:
            raise CommitError(h.id, "raised cell not found")
        self.groups[h.id] = [driver.node()]
        self.forms[h.id] = "raise+submod"

    def _run(self) -> None:
        self._group()
        serial = 0
        for h in self.hyps:
            if h.id in self.groups:
                serial += 1
                try:
                    self._raise(h, serial)
                except odin_module().Odin3Error as err:
                    raise CommitError(h.id, str(err).split(": ", 1)[-1]) from err
        for h in self.hyps:
            for node in self.groups.get(h.id, ()):
                node.set_attr(SM, module_name(h))
        if self.groups:
            self.work.run_pass("submod", f"-attr {SM}")
        for h in self.hyps:
            if h.id in self.groups:
                self._tag(h)
            elif KINDS[h.kind].commit == "attrs":
                self._attrs(h)

    def _tag(self, h: Hypothesis) -> None:
        name = module_name(h)
        inst = self.work.top().node(f"{name}_i")
        module = self.work.module(name)
        if inst is None or module is None:
            raise CommitError(h.id, "instance not found after submod")
        text = fn_text(h)
        role = role_of(h, self.overlay)
        tags = {"loki_hid": h.id, "loki_kind": h.kind, "loki_conf": f"{h.p_comp:.4f}",
                "loki_proof": proof_label(h), "loki_fn": text}
        if role:
            tags["loki_role"] = role
        for key, value in tags.items():
            inst.set_attr(key, value)
        module.set_attr("loki_kind", h.kind)
        module.set_attr("loki_fn", text)

    def _attrs(self, h: Hypothesis) -> None:
        self.forms[h.id] = "attrs"
        if h.kind != "bus":
            return
        top = self.work.top()
        slices = sorted((k for k in h.nets if k.startswith("slice")), key=lambda k: int(k[5:]))
        for bit, key in enumerate(slices):
            for net in h.nets[key]:
                found = top.net(self.graph.names.get(net, ""))
                if found is not None:
                    old = found.attr("loki_bus")
                    tag = f"{h.id}[{bit}]"
                    found.set_attr("loki_bus", tag if old is None else f"{old},{tag}")


def _blame(working: Any, hyps: Sequence[Hypothesis], overlay: Overlay, graph: FnGraph,
           timeout: int) -> str:
    """The first hypothesis that fails alone (else the last): a submod failure names no one."""
    for h in hyps:
        probe = _Attempt(working, [h], overlay, graph, timeout)
        try:
            probe.run()
        except CommitError:
            return h.id
        finally:
            probe.work.close()
    return hyps[-1].id


def commit(working: Any, hyps: Sequence[Hypothesis], overlay: Overlay, graph: FnGraph,
           timeout: int) -> CommitResult:
    """Commit ``hyps`` on ``working.copy()`` (``working`` is not changed). A failing hypothesis
    is dropped and the commit retried once without it (spec 9.3)."""
    failed: list[str] = []
    reasons: dict[str, str] = {}
    todo = list(hyps)
    for _ in range(2):
        attempt = _Attempt(working, todo, overlay, graph, timeout)
        try:
            forms = attempt.run()
        except CommitError as err:
            attempt.work.close()
            hid = err.hid or _blame(working, todo, overlay, graph, timeout)
            failed.append(hid)
            reasons[hid] = err.status
            todo = [h for h in todo if h.id != hid]
            if not todo:
                break
            continue
        return CommitResult(attempt.work, forms, tuple(failed), reasons)
    return CommitResult(working.copy(), {}, tuple(failed), reasons)


def reject_failed(overlay: Overlay, result: CommitResult, round: int) -> None:
    """Mark the offenders of a commit rejected with the record ``("commit", "error", status)``."""
    for hid in result.failed:
        h = overlay.get(hid)
        h.status = "rejected"
        h.p_comp = 0.0
        h.evidence.append(Evidence(round, "commit", "error", result.reasons.get(hid, ""), 0.0))
