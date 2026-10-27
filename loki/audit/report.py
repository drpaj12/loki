"""Per-design audit result (JSON-ready) from the snapshot maps of one design."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loki.audit.loss import PARTNER_SHOWN, UnitRow, audit, null_losses
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


def _unit_json(row: UnitRow, null: list[dict[UnitKey, float]]) -> dict[str, Any]:
    key = row.key
    out: dict[str, Any] = {"file": Path(key[0]).name, "kind": key[1], "span": key[2],
                           "name": key[3], "hw": row.hw, "status": row.status,
                           "first": row.first + 1 if row.pure_at else 0}
    if row.loss is not None:
        loss = row.loss
        out["loss"] = {
            "at": loss.index + 1, "pass": loss.pass_name, "reason": loss.reason,
            "explained": loss.explained, "capped": loss.capped, "transient": loss.transient,
            "n_partners": len(loss.partners),
            "partners": [[Path(p[0]).name, p[1], p[2]] for p in loss.partners[:PARTNER_SHOWN]],
            "null": round(null[loss.index].get(key, 0.0), 6),
        }
    return out


def audit_design(d: Path, design: str, level: str) -> dict[str, Any]:
    """Audit result of the snapshot directory ``d`` at one level."""
    snaps = load_snaps(d, level)
    rows = audit(snaps)
    null = null_losses(snaps, design)
    units = [_unit_json(r, null) for _, r in sorted(rows.items(), key=lambda x: x[0])]
    # null loss counts per snapshot index: expected number of real-separable units lost
    null_counts = [round(sum(n.values()), 6) for n in null]
    return {"schema": 1, "design": design, "level": level, "units": units,
            "null_lost": null_counts, "objects": [len(o) for _, o in snaps],
            "passes": [[n, a] for n, a in PASSES]}
