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


def design_matches(rp: dict[str, Any], design: str) -> bool:
    """The partition design is the stem or a directory name of the re input path."""
    path = Path(str(rp["header"]["input"]["path"]))
    stem = path.name.split(".")[0]
    return design in {stem, *(d for d in path.parent.parts)}


def _split(rp: dict[str, Any], part: Partition,
           allow: bool) -> tuple[dict[int, set[str]], int, int]:
    """Cells per cluster, port nodes joined by name and nodes not joined (ports of other id).

    Cells join by name only. The graph of the dataset names its PI/PO nodes with ids of the shared
    counter, which differ from the net names of the netlist, so port nodes may not join. Nodes
    that join to nothing are accepted only when every cell of the netlist is in the partition and
    their number is the number of port nets not joined by name: then they can only be ports.
    That count is a coincidence check, so it also needs the partition design to match the re input
    (``design_matches``), unless ``allow`` (``--allow-unjoined-ports``) is passed.
    Anything else is a ``JoinError``."""
    net = rp["netlist"]
    cells, ports = set(net["cells"]), set(net["inputs"]) | set(net["outputs"])
    unknown = [n for n in part.node_ids if n not in cells and n not in ports]
    named = {n for n in part.node_ids if n in ports}
    out: dict[int, set[str]] = {}
    for node, number in zip(part.node_ids, part.assignment, strict=True):
        if node in cells:
            out.setdefault(number, set()).add(node)
    joined = set().union(*out.values()) if out else set()
    if not joined:
        raise JoinError("no partition node is a cell of the re input")
    if unknown and not (joined == cells and len(unknown) == len(ports - named)):
        raise JoinError(
            f"{len(unknown)} of {len(part.node_ids)} partition nodes are not cells or ports of "
            f"the re input (first: {', '.join(unknown[:5])}); not joining by guess")
    if unknown and not allow and not design_matches(rp, part.design):
        raise JoinError(
            f"{len(unknown)} partition nodes are not joined by name and the partition design "
            f"{part.design!r} does not match the re input {rp['header']['input']['name']!r}; "
            "pass --allow-unjoined-ports to accept them by count")
    return out, len(named), len(unknown)


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


def build_l2(rp: dict[str, Any], part: Partition, source: str,
             allow_unjoined_ports: bool = False) -> dict[str, object]:
    """The ``l2`` block for ``rp`` from the partition ``part`` (read from file ``source``)."""
    clusters, n_ports, n_unjoined = _split(rp, part, allow_unjoined_ports)
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
                      "n_clusters": part.n_clusters, "port_nodes": n_ports,
                      "unjoined_nodes": n_unjoined,
                      "allow_unjoined_ports": allow_unjoined_ports},
        "clusters": block,
        "cells_unclustered": len(set(net["cells"]) - clustered),
    }


def add_l2(re_dir: Path, partition: Path, allow_unjoined_ports: bool = False) -> Path:
    """Add (or replace) the ``l2`` block of ``re_dir/reverse-provenance.json``; returns the path."""
    path = re_dir / FILE
    rp = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(rp, dict):
        rp.pop("l2", None)
    if validate_reverse_provenance(rp):
        raise ValueError(f"{path}: not a schema-1 reverse-provenance file")
    part = load_partition(partition)
    rp["l2"] = build_l2(rp, part, str(partition), allow_unjoined_ports)
    errs = validate_reverse_provenance(rp)
    if errs:
        raise ValueError(f"{path}: merged file invalid: {errs[0]}")
    path.write_text(dump_json(rp), encoding="utf-8")
    return path
