"""``loki rp add-l2``: merge an L2 partition into ``reverse-provenance.json``.

The partition lists graph nodes by id. The ids join to the input netlist only when they are the
same names the ``loki re`` input uses (cell ``.cname`` values, port net names). Any other node id
stops the merge: names are never guessed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loki.analysis.partition import Partition, load_partition
from loki.rp.build import sorted_names
from loki.schemas import dump_json, validate_reverse_provenance

FILE = "reverse-provenance.json"


class JoinError(ValueError):
    """The partition node ids cannot be joined to the input netlist names."""


def _frac(part: int, whole: int) -> float:
    return round(part / whole, 6) if whole else 0.0


def _split(rp: dict[str, Any], part: Partition) -> tuple[dict[int, set[str]], int]:
    """Cells per cluster, and the number of port nodes; ``JoinError`` on any unknown id."""
    net = rp["netlist"]
    cells, ports = set(net["cells"]), set(net["inputs"]) | set(net["outputs"])
    unknown = [n for n in part.node_ids if n not in cells and n not in ports]
    if unknown:
        raise JoinError(
            f"{len(unknown)} of {len(part.node_ids)} partition nodes are not cells or ports of "
            f"the re input (first: {', '.join(unknown[:5])}); not joining by guess")
    out: dict[int, set[str]] = {}
    n_ports = 0
    for node, number in zip(part.node_ids, part.assignment, strict=True):
        if node in cells:
            out.setdefault(number, set()).add(node)
        else:
            n_ports += 1
    if not any(out.values()):
        raise JoinError("no partition node is a cell of the re input")
    return out, n_ports


def _modules(rp: dict[str, Any]) -> list[dict[str, Any]]:
    els: list[dict[str, Any]] = rp["elements"]
    return [e for e in els if e["status"] == "committed" and e["recovered"]["form"] != "attrs"]


def _overlap(members: set[str], mods: list[dict[str, Any]]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for m in mods:
        cells: list[str] = m["cells"]
        common = members & set(cells)
        if common:
            out.append({
                "id": m["id"], "module": m["recovered"]["module"],
                "cells_in_common": len(common),
                "fraction_of_cluster": _frac(len(common), len(members)),
                "fraction_of_module": _frac(len(common), len(cells)),
            })
    return out


def build_l2(rp: dict[str, Any], part: Partition, source: str) -> dict[str, object]:
    """The ``l2`` block for ``rp`` from the partition ``part`` (read from file ``source``)."""
    clusters, n_ports = _split(rp, part)
    mods = _modules(rp)
    in_module: set[str] = set()
    for m in mods:
        in_module |= set(m["cells"])
    block: dict[str, dict[str, Any]] = {}
    for number in sorted(clusters):
        members = clusters[number]
        block[str(number)] = {
            "size": len(members), "cells": sorted_names(members),
            "overlap": _overlap(members, mods),
            "cells_outside_committed": len(members - in_module),
        }
    net = rp["netlist"]
    clustered = set().union(*clusters.values())
    return {
        "method": part.method,
        "partition": {"key": part.key, "file": Path(source).name, "seed": part.seed,
                      "params": part.params, "graph_sha256": part.graph_sha256,
                      "design": part.design, "floor": part.floor,
                      "n_clusters": part.n_clusters, "port_nodes": n_ports},
        "clusters": block,
        "cells_unclustered": len(set(net["cells"]) - clustered),
    }


def add_l2(re_dir: Path, partition: Path) -> Path:
    """Add (or replace) the ``l2`` block of ``re_dir/reverse-provenance.json``; returns the path."""
    path = re_dir / FILE
    rp = json.loads(path.read_text(encoding="utf-8"))
    part = load_partition(partition)
    rp["l2"] = build_l2(rp, part, str(partition))
    errs = validate_reverse_provenance(rp)
    if errs:
        raise ValueError(f"{path}: merged file invalid: {errs[0]}")
    path.write_text(dump_json(rp), encoding="utf-8")
    return path
