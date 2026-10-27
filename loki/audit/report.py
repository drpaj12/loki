"""Per-design audit result (JSON-ready) from the snapshot maps of one design."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loki.audit.loss import (
    PARTNER_SHOWN,
    PERSIST_DRAWS,
    UnitRow,
    audit,
    null_losses,
    persistence_losses,
)
from loki.audit.snap import PASSES
from loki.audit.units import ObjView, UnitKey, view_map
from loki.odin import odin_module


def cell_types(json_path: Path) -> dict[str, str]:
    """Hash name to Odin III cell type of a ``write_json`` file."""
    obj = json.loads(json_path.read_text(encoding="utf-8"))
    types: dict[str, str] = {}
    for mod in obj.get("modules", {}).values():
        for name, cell in mod.get("cells", {}).items():
            types[str(name)] = str(cell["type"])
    return types


def load_snaps(d: Path, level: str) -> list[tuple[str, list[ObjView]]]:
    mod = odin_module()
    snaps: list[tuple[str, list[ObjView]]] = []
    for k, (name, args) in enumerate(PASSES, start=1):
        nm = mod.read_name_map(d / f"s{k}.json.names")
        snaps.append((name, view_map(nm, cell_types(d / f"s{k}.json"), level, name, args)))
    return snaps


def _unit_json(row: UnitRow, null: list[dict[UnitKey, float]],
               pnull: list[dict[UnitKey, int]]) -> dict[str, Any]:
    key = row.key
    out: dict[str, Any] = {"file": Path(key[0]).name, "kind": key[1], "span": key[2],
                           "name": key[3], "hw": row.hw, "status": row.status,
                           "first": row.first + 1 if row.pure_at else 0}
    last = row.loss.index if row.loss is not None else len(null) - 1
    risk = {str(k + 1): round(null[k].get(key, 0.0), 6)
            for k in range(row.first + 1, last + 1) if row.pure_at and k - 1 in row.pure_at}
    out["null"] = risk
    # persistence null (Amendment A): bit mask over the draws, same first-loss support as ``risk``
    out["pnull"] = {k: format(pnull[int(k) - 1].get(key, 0), "x") for k in risk}
    if row.loss is not None:
        loss = row.loss
        out["loss"] = {
            "at": loss.index + 1, "pass": loss.pass_name, "reason": loss.reason,
            "explained": loss.explained, "capped": loss.capped, "transient": loss.transient,
            "inherited": loss.inherited, "inherited_subset": loss.inherited_subset,
            "n_partners": len(loss.partners),
            "partners": [[Path(p[0]).name, p[1], p[2]] for p in loss.partners[:PARTNER_SHOWN]],
        }
    return out


def audit_design(d: Path, design: str, level: str) -> dict[str, Any]:
    """Audit result of the snapshot directory ``d`` at one level."""
    snaps = load_snaps(d, level)
    rows = audit(snaps)
    null = null_losses(snaps, design)
    pnull, mad = persistence_losses(snaps, design, PERSIST_DRAWS)
    units = [_unit_json(r, null, pnull) for _, r in sorted(rows.items(), key=lambda x: x[0])]
    # null loss counts per snapshot index on the first-loss support (the support of the tables)
    null_counts = [0.0] * len(null)
    pnull_counts = [0.0] * len(null)
    for unit in units:
        for k, frac in unit["null"].items():
            null_counts[int(k) - 1] += frac
            pnull_counts[int(k) - 1] += bin(int(unit["pnull"][k], 16)).count("1") / PERSIST_DRAWS
    return {"schema": 2, "design": design, "level": level, "units": units,
            "null_lost": [round(x, 6) for x in null_counts],
            "pnull_lost": [round(x, 6) for x in pnull_counts],
            "pnull_draws": PERSIST_DRAWS, "pnull_size_mad": [round(x, 6) for x in mad],
            "objects": [len(o) for _, o in snaps],
            "passes": [[n, a] for n, a in PASSES]}
