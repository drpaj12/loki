"""Summarise the L2 analyses of one or two variants: cluster quality per method and the GNN
numbers against the 1-WL baseline.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def cluster_summary(out: Path) -> dict[str, dict[str, float | int]]:
    by_method: dict[str, list[dict]] = defaultdict(list)
    for path in sorted(out.glob("*/*/partition/*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        by_method[str(record["method"])].append(record)
    summary: dict[str, dict[str, float | int]] = {}
    for method, records in sorted(by_method.items()):
        modularity = [float(r["quality"]["modularity"]) for r in records
                      if isinstance(r["quality"].get("modularity"), (int, float))]
        nmi = [float(r["quality"]["nmi_module_path"]) for r in records
               if isinstance(r["quality"].get("nmi_module_path"), (int, float))]
        clusters = [int(r["n_clusters"]) for r in records]
        summary[method] = {
            "designs": len(records),
            "mean_modularity": round(sum(modularity) / len(modularity), 6) if modularity else None,
            "mean_nmi_module_path": round(sum(nmi) / len(nmi), 6) if nmi else None,
            "mean_n_clusters": round(sum(clusters) / len(clusters), 6) if clusters else None,
        }
    return summary


def status_summary(out: Path) -> dict[str, object]:
    path = out / "l2-status.json"
    if not path.is_file():
        return {"analyses": 0, "failed": 0}
    records = json.loads(path.read_text(encoding="utf-8"))
    return {"analyses": len(records),
            "failed": sum(1 for r in records if r["exit"] != 0),
            "seconds": round(sum(float(r["seconds"]) for r in records), 1)}


def gnn_summary(out: Path) -> dict[str, object]:
    path = out / "gnn" / "metrics.json"
    if not path.is_file():
        return {}
    metrics = json.loads(path.read_text(encoding="utf-8"))
    return {
        "model": metrics.get("model"),
        "target": metrics.get("target"),
        "features": metrics.get("features"),
        "train": metrics.get("train"),
        "test": metrics.get("test"),
        "baselines": metrics.get("baselines"),
        "beats_wl": metrics.get("beats_wl"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", action="append", required=True, metavar="LABEL=DIR")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    summary: dict[str, object] = {}
    for item in args.variant:
        label, _, directory = item.partition("=")
        out = Path(directory)
        summary[label] = {"status": status_summary(out), "cluster": cluster_summary(out),
                          "gnn": gnn_summary(out)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    for label, data in summary.items():
        print(f"== {label}: {data['status']}")
        for method, row in data["cluster"].items():
            print(f"  cluster {method:9s} designs {row['designs']} "
                  f"modularity {row['mean_modularity']} "
                  f"nmi_module_path {row['mean_nmi_module_path']} "
                  f"k {row['mean_n_clusters']}")
        gnn = data["gnn"]
        if gnn:
            test = gnn["test"]
            wl = gnn["baselines"]["wl"]
            print(f"  gnn test macro_f1 {test['macro_f1']} accuracy {test['accuracy']} "
                  f"nodes {test['n_nodes']} | 1-WL macro_f1 {wl['macro_f1']} "
                  f"acc {wl['accuracy']} | beats_wl {gnn['beats_wl']} | "
                  f"features {gnn['features']} target {gnn['target']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
