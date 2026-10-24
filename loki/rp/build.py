"""``reverse-provenance.json`` (schema 1): the stable, documented view of an L1 run.

Odin III's forward provenance says where a netlist element came from in the HDL. This record is
the inverse claim of Loki: for each recovered piece, which input cells and nets it covers, what
Loki says it is, how sure Loki is and why. Keys are hypothesis ids, the same ids as the inline
``loki_hid`` attributes of ``design.v``. It is derived from the overlay and never changes it.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

import loki
from loki.re import bayes
from loki.re.commit import fn_text, proof_label, role_label
from loki.re.overlay import Evidence, Hypothesis, Overlay
from loki.re.report import _sha256, _versions

if TYPE_CHECKING:
    from loki.re.loop import ReOptions, RunResult

SCHEMA = 1
STAGE = "L1"
DEFAULT_MIN_P = 0.5
MAX_EVIDENCE = 5
_LIVE = ("open", "confirmed", "alternative")
_DEAD = ("refuted", "rejected")
_PROOF_SOURCES = ("cone_check", "truth_table", "sim", "transfer")
_DOC_PREFIX = "detector:"
_NATURAL = re.compile(r"(\d+)")


def natural_key(name: str) -> tuple[tuple[int, int, str], ...]:
    """Sort key ordering ``g2`` before ``g10``; deterministic for any text."""
    parts = _NATURAL.split(name)
    return tuple((0, int(p), "") if i % 2 else (1, 0, p) for i, p in enumerate(parts) if p != "")


def sorted_names(names: Iterable[str]) -> list[str]:
    return sorted(set(names), key=lambda n: (natural_key(n), n))


def num(x: float) -> float | str:
    """A float at the fixed precision of the file (6 decimals); infinities as text."""
    if math.isinf(x):
        return "inf" if x > 0 else "-inf"
    return round(x, 6)


def _id_num(hid: str) -> int:
    return int(hid[1:])


def _names(res: RunResult, nets: Iterable[int]) -> list[str]:
    return [res.graph.names.get(n, str(n)) for n in nets]


def _role_map(overlay: Overlay) -> dict[str, list[Hypothesis]]:
    """Live ``role`` hypotheses by each cell they cover (one list per cell)."""
    out: dict[str, list[Hypothesis]] = {}
    for rh in overlay.by_kind("role"):
        if rh.status not in _DEAD:
            for cell in rh.cells:
                out.setdefault(str(cell), []).append(rh)
    return out


def _role(h: Hypothesis, roles: dict[str, list[Hypothesis]]) -> str:
    """Majority role of the cells of ``h`` (the rule of ``loki.re.commit.role_of``)."""
    seen: dict[str, Hypothesis] = {}
    for cell in h.cells:
        for rh in roles.get(str(cell), ()):
            if rh.cells <= h.cells:
                seen[rh.id] = rh
    counts: dict[str, int] = {}
    for rh in seen.values():
        label = role_label(rh)
        counts[label] = counts.get(label, 0) + 1
    if not counts:
        return ""
    return sorted(counts, key=lambda r: (-counts[r], r))[0]


def _evidence(h: Hypothesis) -> list[dict[str, object]]:
    keep: list[Evidence] = []
    for e in h.evidence:
        if e.source == "feature" and e.name.startswith(_DOC_PREFIX):
            continue
        if e.llr != 0.0 or e.source in _PROOF_SOURCES or e.source == "prior":
            keep.append(e)
    keep.sort(key=lambda e: (-abs(e.llr), e.source, e.name, e.value))
    return [{"name": e.name, "source": e.source, "value": e.value, "llr": num(e.llr)}
            for e in keep[:MAX_EVIDENCE]]


def _commit_error(h: Hypothesis) -> str | None:
    for e in h.evidence:
        if e.source == "commit" and e.name == "error":
            return e.value
    return None


def _rejection(h: Hypothesis) -> str:
    if h.proof is not None and h.proof.get("verdict") == "differs":
        cex = h.proof.get("cex", "")
        engine = h.proof.get("engine", "")
        return f"proof differs ({engine})" + (f", counterexample {cex}" if cex else "")
    err = _commit_error(h)
    if err is not None:
        return f"commit failed: {err}"
    for e in h.evidence:
        if e.source == "competition":
            lost = e.name in ("selected", "committed")
            return f"lost to {e.value}" if lost else "low probability"
    return "rejected"


def status_of(h: Hypothesis, min_p: float) -> str:
    """``committed``, ``candidate``, ``rejected`` (after a proof or a failed commit) or ``""``."""
    if h.kind == "role":
        return ""
    if h.status == "committed":
        return "committed"
    if h.status in _DEAD:
        return "rejected" if h.proof is not None or _commit_error(h) is not None else ""
    if h.status in _LIVE and h.p_comp >= min_p:
        return "candidate"
    return ""


def _width(h: Hypothesis) -> int:
    for key in ("width", "k"):
        value = h.params.get(key)
        if isinstance(value, int):
            return value
    return max((len(ns) for ns in h.nets.values()), default=0)


def _fn(h: Hypothesis) -> str:
    """``fn_text``, except for a bus: its text counts the width of one slice, not the bits."""
    if h.kind == "bus":
        return f"bus: {_width(h)} bits"
    return fn_text(h)


def _ports(res: RunResult, h: Hypothesis) -> dict[str, dict[str, list[str]]]:
    if h.claim is None:
        return {"inputs": {}, "outputs": {}}
    return {
        "inputs": {p: _names(res, ns) for p, ns in h.claim.inputs},
        "outputs": {p: _names(res, ns) for p, ns in h.claim.outputs},
    }


def _proof(h: Hypothesis) -> dict[str, object]:
    p = h.proof or {}
    return {"label": proof_label(h), "engine": p.get("engine", ""), "verdict": p.get("verdict", ""),
            "from": p.get("from", "")}


def _element(res: RunResult, h: Hypothesis, status: str,
             roles: dict[str, list[Hypothesis]]) -> dict[str, object]:
    commit = h.commit or {}
    recovered: dict[str, str] | None = None
    if status == "committed":
        recovered = {"module": commit.get("module", ""), "instance": commit.get("instance", ""),
                     "form": commit.get("form", "")}
    el: dict[str, object] = {
        "id": h.id, "kind": h.kind, "stage": STAGE, "status": status, "fn": _fn(h),
        "width": _width(h),
        "params": {k: v for k, v in sorted(h.params.items()) if k != "rows"},
        "proof": _proof(h), "p_comp": num(h.p_comp),
        "prior_log_odds": num(h.prior_log_odds), "log_odds": num(h.log_odds),
        "evidence": _evidence(h),
        "cells": sorted_names(res.graph.label(c) for c in h.cells),
        "nets": {role: _names(res, ns) for role, ns in sorted(h.nets.items())},
        "ports": _ports(res, h),
        "recovered": recovered,
        "parents": list(h.parents), "children": list(h.children), "conflicts": list(h.conflicts),
        "role": _role(h, roles),
        "reason": _rejection(h) if status == "rejected" else "",
    }
    return el


def _bus(res: RunResult, h: Hypothesis) -> dict[str, object]:
    slices = sorted((k for k in h.nets if k.startswith("slice")), key=lambda k: int(k[5:]))
    return {"id": h.id, "width": len(slices),
            "order_source": str(h.params.get("order_source", "")),
            "bits": [_names(res, h.nets[k]) for k in slices]}


def _fsm(res: RunResult, h: Hypothesis) -> dict[str, object]:
    rows = json.loads(str(h.params.get("rows", "[]")))
    feats = h.features
    return {
        "id": h.id, "state_nets": _names(res, h.nets.get("Q", ())),
        "control_nets": _names(res, h.nets.get("C", ())),
        "reset_net": _names(res, h.nets.get("RST", ())),
        "states": h.params.get("states", 0), "reset_state": h.params.get("start", 0),
        "encoding": "marked by fsm_detect" if feats.get("fsm_detect") == "marked" else "unknown",
        "transitions": rows, "transitions_total": h.params.get("rows_n", len(rows)),
    }


def _tree(committed: dict[str, Hypothesis]) -> list[dict[str, object]]:
    """The committed module tree: a node per committed piece, children from ``h.children``."""
    parent_of: dict[str, str] = {}
    for hid in sorted(committed, key=_id_num):
        for cid in committed[hid].children:
            if cid in committed:
                parent_of.setdefault(cid, hid)

    def node(hid: str) -> dict[str, object]:
        h = committed[hid]
        kids = [c for c in sorted(committed, key=_id_num) if parent_of.get(c) == hid]
        return {"id": hid, "module": (h.commit or {}).get("module", ""),
                "instance": (h.commit or {}).get("instance", ""),
                "children": [node(c) for c in kids]}

    roots = [h for h in sorted(committed, key=_id_num) if h not in parent_of]
    return [node(h) for h in roots]


def _keep_known(elements: list[dict[str, object]]) -> None:
    """Drop links to hypotheses that are not elements, so every id in the file resolves."""
    known = {str(el["id"]) for el in elements}
    for el in elements:
        for key in ("parents", "children", "conflicts"):
            ids = el[key]
            assert isinstance(ids, list)
            el[key] = [i for i in ids if i in known]


def _frac(part: int, whole: int) -> float:
    return round(part / whole, 6) if whole else 0.0


def _coverage(res: RunResult, elements: Sequence[Hypothesis],
              status: dict[str, str]) -> dict[str, object]:
    g = res.graph
    committed: set[int] = set()
    cand: set[int] = set()
    for h in elements:
        if status[h.id] == "committed":
            committed |= h.cells
        elif status[h.id] == "candidate":
            cand |= h.cells
    cand -= committed
    rest = set(g.cells) - committed - cand
    total = len(g.cells)
    nets = sorted({n for c in rest for n in g.cells[c].outs})
    return {
        "cells_total": total,
        "committed": {"cells": len(committed), "fraction": _frac(len(committed), total)},
        "candidate": {"cells": len(cand), "fraction": _frac(len(cand), total)},
        "uncovered": {"cells": len(rest), "fraction": _frac(len(rest), total)},
        "uncovered_cells": sorted_names(g.label(c) for c in rest),
        "uncovered_nets": sorted_names(_names(res, nets)),
    }


def _inventory(res: RunResult) -> dict[str, list[str]]:
    g = res.graph
    return {"cells": sorted_names(g.label(c) for c in g.cells),
            "inputs": sorted_names(_names(res, g.pis)),
            "outputs": sorted_names(_names(res, g.pos))}


def _header(opts: ReOptions, min_p: float) -> dict[str, object]:
    calib: dict[str, object] = {"path": None, "sha256": None}
    if opts.calib is not None:
        calib = {"path": str(opts.calib), "sha256": _sha256(opts.calib)}
    v = _versions()
    return {
        "loki": loki.__version__, "odin3": v["odin3"],
        "input": {"path": str(opts.netlist),
                  "sha256": _sha256(opts.netlist) if opts.netlist.is_file() else ""},
        "floor": opts.floor, "calib": calib, "seed": opts.seed,
        "commit_threshold": bayes.COMMIT_P, "candidate_threshold": min_p,
    }


def build_rp(res: RunResult, opts: ReOptions) -> dict[str, object]:
    """The ``reverse-provenance.json`` object, JSON-native and deterministic."""
    min_p = opts.rp_min_p
    ov = res.overlay
    roles = _role_map(ov)
    status = {h.id: status_of(h, min_p) for h in ov.all()}
    chosen = [h for h in ov.all() if status[h.id]]
    committed = {h.id: h for h in chosen
                 if status[h.id] == "committed" and (h.commit or {}).get("form") != "attrs"}
    shown = chosen
    live = [h for h in shown if status[h.id] != "rejected"]
    elements = [_element(res, h, status[h.id], roles) for h in shown]
    _keep_known(elements)
    return {
        "schema": SCHEMA, "header": _header(opts, min_p),
        "netlist": _inventory(res),
        "elements": elements,
        "buses": [_bus(res, h) for h in live if h.kind == "bus"],
        "fsms": [_fsm(res, h) for h in live if h.kind == "fsm"],
        "hierarchy": _tree(committed),
        "coverage": _coverage(res, shown, status),
    }
