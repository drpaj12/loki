"""Build a renamed L2 dataset from the assembled L0 graph files.

The L2 analyses read ``graph.json`` (L0 labels included) and never the BLIF.  L2's numeric code
(``graphio.undirected_adjacency`` and the graphlet signal classifier) parses ``int(id[1:])``, so
an L2 node id must keep the ``n<k>`` shape; the naming decoupling here is a seeded permutation of
the numbering, not the HMAC text tokens of the L1 netlists.  The permutation keeps the graph
isomorphic and every cross-reference consistent, removes the original numbering order, and is what
a name- or order-dependent analysis would notice.  Labels stay the answer key: ``cell_type`` is a
library name the netlist carries, construct, role and numeric fields are kept, and the text label
columns (``module_path``, ``bus_name``, ``hdl_file``) are identical on both sides.
Floor directories keep their names: L2 input is L0's graph layout, not a netlist path (the floor
alias is an L1-input property).
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
from pathlib import Path

SEED = 20261022


def token(design: str, floor: str, value: str) -> str:
    msg = f"{design}\0l2node\0{floor}\0{value}".encode()
    return hmac.new(str(SEED).encode(), msg, hashlib.sha256).hexdigest()


def rename_graph(graph: dict, design: str, floor: str) -> dict:
    """Relabel one graph's identifiers with a seeded numeric permutation."""
    out = json.loads(json.dumps(graph))
    ids = {str(node["id"]) for node in out["nodes"]}
    ids |= {str(edge[key]) for edge in out["edges"] for key in ("src", "dst", "net")}
    order = sorted(ids, key=lambda value: token(design, floor, value))
    remap = {old: f"n{rank}" for rank, old in enumerate(order)}
    for node in out["nodes"]:
        node["id"] = remap[str(node["id"])]
    for edge in out["edges"]:
        for key in ("src", "dst", "net"):
            edge[key] = remap[str(edge[key])]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--floors", default="f1-k6,f1-earch,f2,f3")
    args = ap.parse_args()
    floors = [f.strip() for f in args.floors.split(",") if f.strip()]
    manifest = json.loads((args.dataset / "manifest.json").read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    written = 0
    designs: list[dict] = []
    for entry in sorted(manifest["designs"], key=lambda e: e["design"]):
        design = entry["design"]
        floors_out: dict[str, dict] = {}
        for floor in floors:
            info = entry["floors"].get(floor)
            if info is None or info.get("status") != "ok":
                continue
            src = args.dataset / design / floor / "graph.json"
            if not src.is_file():
                continue
            graph = json.loads(src.read_text(encoding="utf-8"))
            out = rename_graph(graph, design, floor)
            dest = args.out / design / floor
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "graph.json").write_text(
                json.dumps(out, sort_keys=True) + "\n", encoding="utf-8")
            floors_out[floor] = {"status": "ok"}
            written += 1
        designs.append({"design": design, "split": entry.get("split"),
                        "benchmark": entry.get("benchmark"), "floors": floors_out})
    out_manifest = {
        "schema": 1,
        "name": args.dataset.name + "-renamed-l2",
        "designs": [d for d in designs if d["floors"]],
        "odin3_version": manifest.get("odin3_version"),
        "created_by": manifest.get("created_by"),
        "split_rule": manifest.get("split_rule"),
        "split_seed": manifest.get("split_seed"),
    }
    (args.out / "manifest.json").write_text(
        json.dumps(out_manifest, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {written} renamed graph.json files into {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
