"""Versioned graphlet pattern-signature database (Mimir ``records`` columns, one SQLite file).

Tables: ``records`` (Mimir spec 2026-10-27 section 2, same columns and identity), ``entries``
(Loki side: pattern, variant, width, depth, cell, provenance, hashes, tool versions) and
``meta``. One signature value = one ``records`` row: design ``glet/<name>``, metric
``graphlet_orbit_count``, bin = orbit id, arm = mode (undirected, directed, directed_typed),
arch = cell, level = gate or lut, source ``loki-graphlet-pre`` (precomputed) or
``loki-graphlet-live`` (made on demand, widths above 32). Needs from Mimir: see EXPERIMENT.md.
"""

from __future__ import annotations

import csv
import hashlib
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = "1"
LIBRARY_VERSION = "1"
METRIC = "graphlet_orbit_count"
MODES = ("undirected", "directed", "directed_typed")
LEVEL = {"O-gate": "gate", "Y-gate": "gate", "O-lut": "lut", "Y-lut": "lut", "O-hard": "lut"}
SOURCE = {"precomputed": "loki-graphlet-pre", "live": "loki-graphlet-live"}
RECORD_COLS = ("design", "source", "input_sha256", "tool_commit", "script_hash", "level", "arch",
               "seed", "arm", "family", "metric", "bin", "value", "unit", "measurer",
               "measurer_version", "origin")
IDENTITY = tuple(c for c in RECORD_COLS if c not in ("value", "unit", "measurer_version"))

DDL = f"""
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS records(
  design TEXT, source TEXT, input_sha256 TEXT, tool_commit TEXT, script_hash TEXT, level TEXT,
  arch TEXT, seed INTEGER, arm TEXT, family TEXT, metric TEXT, bin TEXT, value REAL, unit TEXT,
  measurer TEXT, measurer_version TEXT, origin TEXT,
  PRIMARY KEY({", ".join(IDENTITY)}));
CREATE TABLE IF NOT EXISTS entries(
  pattern TEXT, variant TEXT, width INTEGER, depth INTEGER, cell TEXT, provenance TEXT,
  rtl_sha256 TEXT, netlist_sha256 TEXT, build_status TEXT, odin3_commit TEXT, yosys_version TEXT,
  gen_hash TEXT, loki_version TEXT,
  PRIMARY KEY(pattern, variant, width, depth, cell, provenance));
"""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


@dataclass(frozen=True)
class Key:
    pattern: str
    variant: str
    width: int
    depth: int
    cell: str

    @property
    def design(self) -> str:
        d = f"_d{self.depth}" if self.depth else ""
        return f"glet/{self.pattern}_{self.variant}{d}_w{self.width:03d}"


def open_db(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.executescript(DDL)
    con.execute("INSERT OR IGNORE INTO meta VALUES('schema_version', ?)", (SCHEMA_VERSION,))
    con.execute("INSERT OR IGNORE INTO meta VALUES('library_version', ?)", (LIBRARY_VERSION,))
    con.commit()
    return con


def put_entry(con: sqlite3.Connection, k: Key, provenance: str, row: Mapping[str, str | int]
              ) -> None:
    con.execute("INSERT OR REPLACE INTO entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (k.pattern, k.variant, k.width, k.depth, k.cell, provenance,
                 row.get("rtl_sha256", ""), row.get("netlist_sha256", ""),
                 row.get("build_status", ""), row.get("odin3_commit", ""),
                 row.get("yosys_version", ""), row.get("gen_hash", ""),
                 row.get("loki_version", "")))
    con.commit()


def put_signature(con: sqlite3.Connection, k: Key, provenance: str, mode: str,
                  sig: Mapping[int, float], *, input_sha256: str, tool_commit: str,
                  script_hash: str, measurer_version: str, origin: str) -> None:
    """Store one signature (orbit id -> count); replaces an earlier one of the same identity."""
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}")
    rows = [(k.design, SOURCE[provenance], input_sha256, tool_commit, script_hash,
             LEVEL[k.cell], k.cell, -1, mode, "", METRIC, str(o), float(v), "count", "graphlet",
             measurer_version, origin) for o, v in sorted(sig.items())]
    con.executemany(f"INSERT OR REPLACE INTO records VALUES({','.join('?' * 17)})", rows)
    con.commit()


def get_signature(con: sqlite3.Connection, k: Key, mode: str) -> tuple[dict[int, float], str]:
    """(signature, provenance); empty dict when absent. Precomputed wins over live."""
    for prov in ("precomputed", "live"):
        cur = con.execute("SELECT bin, value FROM records WHERE design=? AND arch=? AND arm=? "
                          "AND metric=? AND source=?",
                          (k.design, k.cell, mode, METRIC, SOURCE[prov]))
        got = {int(b): float(v) for b, v in cur.fetchall()}
        if got:
            return got, prov
    return {}, ""


def export_csv(con: sqlite3.Connection, path: Path) -> int:
    """Sorted, byte-stable CSV of ``records`` (Mimir convention)."""
    rows = con.execute(f"SELECT {','.join(RECORD_COLS)} FROM records "
                       f"ORDER BY {','.join(IDENTITY)}").fetchall()
    rows.sort(key=lambda r: (r[:11], int(r[11]) if str(r[11]).isdigit() else -1))
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(RECORD_COLS)
        w.writerows(rows)
    return len(rows)
