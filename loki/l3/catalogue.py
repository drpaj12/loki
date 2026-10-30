"""The L3 catalogue: JSON entries (schema 1), one signature list per target."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CATALOGUE_DIR = Path(__file__).resolve().parent / "catalogue"
TARGETS = ("gate", "lut", "lut+hard")
ORDER = ("fsm", "counter", "lfsr", "shift", "timer", "regfile", "register", "glue")


@dataclass(frozen=True)
class Entry:
    id: str
    version: int
    raw: dict[str, Any]

    def signatures(self, target: str) -> list[dict[str, Any]]:
        det: dict[str, Any] = self.raw["detector"]
        return list(det.get(target) or det.get("lut") or [])


def load(directory: Path = CATALOGUE_DIR) -> dict[str, Entry]:
    """Entries by id, in detection order (``forbid`` refers to earlier entries)."""
    found: dict[str, Entry] = {}
    for path in sorted(directory.glob("*.json")):
        if path.name == "tuning.json":
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("schema") != 1:
            raise ValueError(f"{path.name}: schema must be 1")
        found[raw["id"]] = Entry(raw["id"], int(raw["version"]), raw)
    return {k: found[k] for k in ORDER if k in found} | {
        k: v for k, v in found.items() if k not in ORDER}


def load_tuning(directory: Path = CATALOGUE_DIR) -> dict[str, Any]:
    path = directory / "tuning.json"
    if not path.is_file():
        return {"max_depth": 6, "min_p": 0.0, "regfile_k": 4, "regfile_k2": 16}
    out: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return out
