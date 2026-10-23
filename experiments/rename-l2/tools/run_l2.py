"""Run the L2 analyses over one dataset floor: cluster on every design, a region export on a
sample, and the dataset-level GNN baseline.

Each analysis is the ``loki analyze`` CLI in its own process, so an analysis failure is one exit
code, not a broken runner.  ``status.json`` records every command's exit and seconds.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def loki_exe() -> str:
    return str(Path(sys.executable).parent / "loki")


def run(argv: list[str], cwd: Path, logdir: Path, tag: str, records: list[dict]) -> int:
    log = logdir / f"{tag}.log"
    t0 = time.time()
    with log.open("w", encoding="utf-8") as fh:
        code = subprocess.run(argv, stdout=fh, stderr=subprocess.STDOUT, cwd=cwd,
                              check=False).returncode
    records.append({"tag": tag, "exit": code, "seconds": round(time.time() - t0, 2)})
    return code


def labelled_subset(source: Path, root: Path, floor: str) -> tuple[Path, list[str]]:
    """A GNN-only copy of ``source``: designs with no train-kind node carrying a construct type
    are left out (the GNN refuses them, spec 9 ``UNLABELLED_MESSAGE``; the L2 acceptance test
    does the same with ``labelled_subset``).  Only manifest and graph files are written.
    """
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    dataset = root / "dataset"
    if dataset.exists():
        import shutil
        shutil.rmtree(dataset)
    dataset.mkdir(parents=True)
    kept: list[dict] = []
    refused: list[str] = []
    for entry in manifest.get("designs", []):
        if entry.get("floors", {}).get(floor, {}).get("status") != "ok":
            continue
        name = str(entry["design"])
        graph_path = source / name / floor / "graph.json"
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        labelled = any(
            node["kind"] in ("lut", "ff", "hard", "gate")
            and str(node["labels"]["construct_type"])
            for node in graph["nodes"]
        )
        if not labelled:
            refused.append(name)
            continue
        kept.append(entry)
        (dataset / name / floor).mkdir(parents=True)
        (dataset / name / floor / "graph.json").write_bytes(graph_path.read_bytes())
    (dataset / "manifest.json").write_text(
        json.dumps({**manifest, "designs": kept}, sort_keys=True, indent=1) + "\n",
        encoding="utf-8")
    return dataset, refused


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, type=Path)
    ap.add_argument("--floor", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--gnn-subset", type=Path,
                    help="write a GNN-only copy of the dataset here, dropping unlabelled designs")
    ap.add_argument("--region-designs", type=int, default=5)
    ap.add_argument("--skip-cluster", action="store_true")
    ap.add_argument("--skip-gnn", action="store_true")
    ap.add_argument("--features", default="node,graphlet,wl,npn")
    args = ap.parse_args()
    exe = loki_exe()
    args.out.mkdir(parents=True, exist_ok=True)
    logdir = Path("/tmp/claude-1000/rn2-l2-logs") / args.out.name
    logdir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((args.dataset / "manifest.json").read_text(encoding="utf-8"))
    designs = [d["design"] for d in sorted(manifest["designs"], key=lambda e: e["design"])
               if d["floors"].get(args.floor, {}).get("status") == "ok"]
    records: list[dict] = []
    if not args.skip_cluster:
        for design in designs:
            argv = [exe, "analyze", "cluster", "--dataset", str(args.dataset), "--design", design,
                    "--floor", args.floor, "--method", "all", "--out", str(args.out)]
            if run(argv, args.out, logdir, f"cluster-{design}", records) != 0:
                break
    if args.region_designs:
        for design in designs[: args.region_designs]:
            graph = json.loads((args.dataset / design / args.floor / "graph.json")
                               .read_text(encoding="utf-8"))
            node = next((n["id"] for n in graph["nodes"] if n["kind"] == "lut"), None)
            if node is None:
                continue
            argv = [exe, "analyze", "export", "--dataset", str(args.dataset), "--design", design,
                    "--floor", args.floor, "--region", f"cone:{node}:in:2",
                    "--format", "edgelist", "--out", str(args.out)]
            run(argv, args.out, logdir, f"export-{design}", records)
    if not args.skip_gnn:
        gnn_dataset = args.dataset
        if args.gnn_subset:
            gnn_dataset, refused = labelled_subset(args.dataset, args.gnn_subset, args.floor)
            records.append({"tag": "gnn-subset", "exit": 0, "seconds": 0.0, "refused": refused})
            print(f"gnn subset: refused {len(refused)} unlabelled design(s): {refused}")
        argv = [exe, "analyze", "gnn", "--dataset", str(gnn_dataset), "--floor", args.floor,
                "--features", args.features, "--out", str(args.out)]
        run(argv, args.out, logdir, "gnn", records)
    (args.out / "l2-status.json").write_text(
        json.dumps(records, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    bad = [r for r in records if r["exit"] != 0]
    print(f"{args.out.name}: {len(records)} analyses, {len(bad)} failed, "
          f"{round(sum(r['seconds'] for r in records), 1)} s")
    for r in bad[:5]:
        print("  ", r)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
