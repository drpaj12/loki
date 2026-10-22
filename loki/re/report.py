"""``report.json``, ``report.md`` and the output directory of ``loki re`` (L1 spec 11)."""

from __future__ import annotations

import hashlib
import json
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import loki
from loki.odin import odin_module
from loki.re.commit import fn_text, proof_label, role_label
from loki.re.overlay import Hypothesis
from loki.schemas import dump_json

if TYPE_CHECKING:
    from loki.re.loop import ReOptions, RunResult

SCHEMA = 1
KEYS = (
    "schema", "input", "seed", "calib", "versions", "rounds", "stop_reason", "counts", "pieces",
    "buses", "roles", "fsms", "unmap", "fsm_detect", "final_equiv", "timeouts", "features",
)
ROUND_KEYS = ("round", "new", "proved", "committed", "rejected", "engines")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _versions() -> dict[str, object]:
    try:
        o = odin_module().default()
        return {"loki": loki.__version__, "odin3": str(o.version()), "abi": int(o.abi_version())}
    except Exception:
        return {"loki": loki.__version__, "odin3": "unknown", "abi": 0}


def _names(res: RunResult, nets: Sequence[int]) -> list[str]:
    return [res.graph.names.get(n, str(n)) for n in nets]


def _piece(res: RunResult, h: Hypothesis) -> dict[str, object]:
    commit = h.commit or {}
    return {
        "hid": h.id, "kind": h.kind, "module": commit.get("module", ""),
        "instance": commit.get("instance", ""), "p": round(h.p_comp, 6), "proof": proof_label(h),
        "fn": fn_text(h), "cells": [res.graph.label(c) for c in sorted(h.cells)],
        "children": list(h.children),
    }


def _bus(res: RunResult, h: Hypothesis) -> dict[str, object]:
    k = h.params.get("k", 0)
    return {
        "hid": h.id, "width": k, "order_source": h.params.get("order_source", ""),
        "nets": {role: _names(res, ns) for role, ns in sorted(h.nets.items())},
    }


def _fsm(h: Hypothesis) -> dict[str, object]:
    rows = json.loads(str(h.params.get("rows", "[]")))
    return {
        "hid": h.id, "states": h.params.get("states", 0), "reset_state": h.params.get("start", 0),
        "transitions": rows,
    }


def _counts(res: RunResult, done: list[Hypothesis]) -> dict[str, object]:
    pieces = [h for h in done if (h.commit or {}).get("form") != "attrs"]
    by_kind: dict[str, int] = {}
    for h in done:
        by_kind[h.kind] = by_kind.get(h.kind, 0) + 1
    absorbed: set[int] = set()
    for h in pieces:
        absorbed |= h.cells
    return {"cells": len(res.graph.cells), "absorbed": len(absorbed), "committed": len(done),
            "by_kind": dict(sorted(by_kind.items()))}


def _roles(res: RunResult) -> dict[str, int]:
    out = {"datapath": 0, "control": 0, "mixed": 0}
    for h in res.overlay.by_kind("role"):
        if h.status not in ("refuted", "rejected"):
            out[role_label(h)] += 1
    return out


def build_report(res: RunResult, opts: ReOptions) -> dict[str, object]:
    """The ``report.json`` object of spec 11, JSON-native (no tuples) and deterministic."""
    done = [h for h in res.overlay.committed() if h.kind != "role"]
    path = opts.netlist
    calib: dict[str, object] = {"path": None, "sha256": None}
    if opts.calib is not None:
        calib = {"path": str(opts.calib), "sha256": _sha256(opts.calib)}
    report: dict[str, object] = {
        "schema": SCHEMA,
        "input": {"path": str(path), "sha256": _sha256(path) if path.is_file() else "",
                  "floor": opts.floor},
        "seed": opts.seed,
        "calib": calib,
        "versions": _versions(),
        "rounds": json.loads(json.dumps(res.rounds)),
        "stop_reason": res.stop_reason,
        "counts": _counts(res, done),
        "pieces": [_piece(res, h) for h in done if (h.commit or {}).get("form") != "attrs"],
        "buses": [_bus(res, h) for h in done if h.kind == "bus"],
        "roles": _roles(res),
        "fsms": [_fsm(h) for h in done if h.kind == "fsm"],
        "unmap": res.notes.get("unmap", "n/a"),
        "fsm_detect": res.notes.get("fsm_detect", "not-applicable"),
        "final_equiv": dict(res.final_equiv),
        "timeouts": res.timeouts,
        "features": json.loads(json.dumps(res.features)),
    }
    return report


def validate_report(obj: object) -> list[str]:
    """Errors of a report object against spec 11 (an empty list: valid)."""
    if not isinstance(obj, dict):
        return ["report: not an object"]
    errs = [f"report: missing key {k!r}" for k in KEYS if k not in obj]
    errs += [f"report: unknown key {k!r}" for k in obj if k not in KEYS]
    if obj.get("schema") != SCHEMA:
        errs.append(f"report: schema must be {SCHEMA}")
    rounds = obj.get("rounds")
    if not isinstance(rounds, list):
        errs.append("report: rounds is not a list")
    else:
        for i, rnd in enumerate(rounds):
            if not isinstance(rnd, dict):
                errs.append(f"rounds[{i}]: not an object")
                continue
            errs += [f"rounds[{i}]: missing key {k!r}" for k in ROUND_KEYS if k not in rnd]
    for key in ("pieces", "buses", "fsms"):
        if key in obj and not isinstance(obj[key], list):
            errs.append(f"report: {key} is not a list")
    for key in ("input", "counts", "roles", "final_equiv", "features", "versions", "calib"):
        if key in obj and not isinstance(obj[key], dict):
            errs.append(f"report: {key} is not an object")
    feats = obj.get("features")
    if isinstance(feats, dict):
        errs += [f"features: missing key {k!r}" for k in
                 ("enabled", "wl", "npn", "transfers", "transfer_failures") if k not in feats]
    return errs


def _row(cells: Sequence[object]) -> str:
    return "| " + " | ".join(str(c) for c in cells) + " |"


def _table(head: Sequence[str], rows: Sequence[Sequence[object]]) -> list[str]:
    return [_row(head), _row(["---"] * len(head)), *(_row(r) for r in rows)]


def _dict(obj: object) -> Mapping[str, object]:
    return obj if isinstance(obj, dict) else {}


def _list(obj: object) -> list[object]:
    return obj if isinstance(obj, list) else []


def _summary(rep: Mapping[str, object]) -> list[str]:
    inp, counts = _dict(rep.get("input")), _dict(rep.get("counts"))
    feats, final = _dict(rep.get("features")), _dict(rep.get("final_equiv"))
    rows = [
        ("input", inp.get("path", "")), ("floor", inp.get("floor", "")),
        ("sha256", inp.get("sha256", "")), ("seed", rep.get("seed", "")),
        ("stop reason", rep.get("stop_reason", "")), ("cells", counts.get("cells", 0)),
        ("absorbed", counts.get("absorbed", 0)), ("committed", counts.get("committed", 0)),
        ("final equivalence", final.get("status", "")), ("timeouts", rep.get("timeouts", 0)),
        ("unmap", rep.get("unmap", "")), ("fsm_detect", rep.get("fsm_detect", "")),
        ("features", "on" if feats.get("enabled") else "off"),
        ("transfers", feats.get("transfers", 0)),
        ("transfer failures", feats.get("transfer_failures", 0)),
    ]
    return ["## Summary", "", *_table(["item", "value"], rows), ""]


def _pieces(rep: Mapping[str, object]) -> list[str]:
    rows = []
    for p in map(_dict, _list(rep.get("pieces"))):
        rows.append((p.get("module", ""), p.get("kind", ""), f"{float(str(p.get('p', 0))):.4f}",
                     p.get("proof", ""), p.get("fn", "")))
    head = ["module", "kind", "confidence", "proof", "function"]
    return ["## Pieces", "", *_table(head, rows), ""]


def _fsms(rep: Mapping[str, object]) -> list[str]:
    out: list[str] = []
    for f in map(_dict, _list(rep.get("fsms"))):
        out += [f"## FSM {f.get('hid', '')}", "",
                f"{f.get('states', 0)} states, reset state {f.get('reset_state', 0)}", ""]
        rows = [tuple(_list(t)) for t in _list(f.get("transitions"))]
        out += [*_table(["state", "control", "next"], rows), ""]
    return out


def _buses(rep: Mapping[str, object]) -> list[str]:
    buses = list(map(_dict, _list(rep.get("buses"))))
    if not buses:
        return []
    rows = [(b.get("hid", ""), b.get("width", ""), b.get("order_source", "")) for b in buses]
    return ["## Buses", "", *_table(["hid", "width", "order"], rows), ""]


def _rounds(rep: Mapping[str, object]) -> list[str]:
    rows = []
    for r in map(_dict, _list(rep.get("rounds"))):
        proved, eng = _dict(r.get("proved")), _dict(r.get("engines"))
        rows.append((
            r.get("round", ""), r.get("new", 0), ",".join(map(str, _list(r.get("committed")))),
            r.get("rejected", 0),
            "/".join(str(proved.get(k, 0)) for k in ("equivalent", "differs", "unproven")),
            "/".join(str(eng.get(k, 0)) for k in ("cone_check", "truth_table", "transfer")),
        ))
    head = ["round", "new", "committed", "rejected", "proved eq/diff/unproven",
            "engines cc/tt/transfer"]
    return ["## Rounds", "", *_table(head, rows), ""]


def write_markdown(report: Mapping[str, object]) -> str:
    """``report.md`` from the report object only (so from ``report.json`` alone)."""
    lines = ["# Loki re report", ""]
    for part in (_summary, _pieces, _fsms, _buses, _rounds):
        lines += part(report)
    return "\n".join(lines).rstrip("\n") + "\n"


def write_outputs(res: RunResult, opts: ReOptions, out: Path) -> None:
    """Write ``design.v``, ``overlay.json``, ``report.json``, ``report.md`` and ``timing.json``."""
    out.mkdir(parents=True, exist_ok=True)
    mod = odin_module()
    with tempfile.TemporaryDirectory(prefix="loki-re-") as tmp:
        target = Path(tmp) / "design.v"
        with mod.default().capture_log():
            res.final.run_pass("write_verilog", f'"{target}"')
        (out / "design.v").write_bytes(target.read_bytes())
    report = build_report(res, opts)
    (out / "overlay.json").write_text(dump_json(res.overlay.to_json(res.graph)), encoding="utf-8")
    (out / "report.json").write_text(dump_json(report), encoding="utf-8")
    (out / "report.md").write_text(write_markdown(report), encoding="utf-8")
    (out / "timing.json").write_text(dump_json(res.timing), encoding="utf-8")
