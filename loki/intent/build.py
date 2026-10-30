"""``intent.json``: the claims v2 of one ``loki re`` run, assembled.

Steps: lower asynchronous flip-flops, read the sequential claims, keep the overlay claims that
reach the candidate threshold under the run's calibration (those whose state nets a sequential
claim already explains are listed as subsumed by it), set the probability of sequential claims
from the intent calibration, merge duplicates (A3), assign roles (A4) and find buses with their
purpose (A5).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import loki
from loki.intent import calib as intent_calib
from loki.intent.buses import find_buses
from loki.intent.claims import from_overlay, from_seq, namer
from loki.intent.dedupe import merge_duplicates
from loki.intent.lower import lower_async_ff
from loki.intent.roles import assign_roles
from loki.intent.seq import sequential_claims
from loki.re.report import _sha256

if TYPE_CHECKING:
    from loki.re.loop import ReOptions, RunResult

SCHEMA = 1
SEQ_KINDS = frozenset({"counter", "shift_reg", "lfsr", "fsm", "register", "ff_srst", "ff_en"})
SKIP_KINDS = frozenset({"role", "datapath_unit", "control_unit"})
INTENT_MIN_P = 0.9


def _next_id(res: RunResult) -> int:
    return max((int(h.id[1:]) for h in res.overlay.all()), default=0) + 1


def _trivial(h: Any) -> bool:
    """A comparison of one or two gates: true, and no help to a reader."""
    return h.kind in ("eq_const", "comparator") and len(h.cells) <= 2


def _overlay_claims(res: RunResult, opts: ReOptions, name: Any) -> list[dict[str, Any]]:
    from loki.rp.build import status_of

    out: list[dict[str, Any]] = []
    for h in res.overlay.all():
        if h.kind in SKIP_KINDS or _trivial(h):
            continue
        status = status_of(h, INTENT_MIN_P)
        if status in ("committed", "candidate"):
            out.append(from_overlay(res.graph, h, status, name))
    return out


def _subsumed(overlay: list[dict[str, Any]], seq: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Overlay claims of a sequential kind whose q nets lie in a sequential claim are dropped and
    recorded in that claim's ``merged`` list; the others are kept."""
    keep: list[dict[str, Any]] = []
    for c in overlay:
        q = set(c["nets"].get("q", []))
        home = next((s for s in seq if c["kind"] in SEQ_KINDS and q
                     and q <= set(s["nets"]["q"])), None)
        if home is None:
            keep.append(c)
        else:
            home["merged"] = sorted({*home["merged"], c["id"]}, key=lambda i: int(i[1:]))
    return keep


def _seq_claims(res: RunResult, table: intent_calib.IntentCalib | None
                ) -> tuple[list[dict[str, Any]], Any]:
    graph, asyn = lower_async_ff(res.graph)
    name = namer(graph)
    nid = _next_id(res)
    claims: list[dict[str, Any]] = []
    for sc in sequential_claims(graph, set(asyn)):
        c = from_seq(graph, sc, f"h{nid}", name)
        nid += 1
        c["p"] = None if table is None else table.p_for(sc.kind)
        claims.append(c)
    return claims, graph


def _header(opts: ReOptions, table: intent_calib.IntentCalib | None, table_path: Path | None
            ) -> dict[str, Any]:
    run_calib: dict[str, Any] = {"path": None, "sha256": None}
    if opts.calib is not None:
        run_calib = {"path": opts.calib.name, "sha256": _sha256(opts.calib)}
    return {
        "loki": loki.__version__, "floor": opts.floor, "overlay_calib": run_calib,
        "intent_calib": None if table is None or table_path is None else {
            "path": table_path.name, "sha256": _sha256(table_path), "source": table.source},
        "overlay_min_p": INTENT_MIN_P,
    }


def _used(roles: dict[str, dict[str, Any]], claims: list[dict[str, Any]]) -> dict[str, Any]:
    """Roles of the nets a claim names (state, controls, data, covered wires)."""
    used = {n for c in claims for ns in c["nets"].values() for n in ns} | {
        w for c in claims for w in c["wires"]}
    return {n: r for n, r in roles.items() if n in used}


def build_intent(res: RunResult, opts: ReOptions, table_path: Path | None = None
                 ) -> dict[str, Any]:
    """The ``intent.json`` object of a run."""
    table = intent_calib.load(table_path) if table_path is not None else None
    seq, graph = _seq_claims(res, table)
    claims = [*seq, *_subsumed(_overlay_claims(res, opts, namer(graph)), seq)]
    claims = merge_duplicates(claims)
    roles = _used(assign_roles(graph, claims), claims)
    ports = [graph.names[n] for n in (*graph.pis, *graph.pos) if n in graph.names]
    return {
        "schema": SCHEMA, "header": _header(opts, table, table_path),
        "claims": claims, "buses": find_buses(claims, ports), "net_roles": roles,
    }
