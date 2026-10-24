"""L1 runs on the f3 floor: base and renamed netlists, test split, then score both sides.

Runs ``loki re`` per design (smallest f3 netlist first), then scores each run against the
original-named L0 floor. A renamed run's overlay/report is translated through the inverse
rename map first, exactly as experiments/rename-l2/tools/score_runs.py does, so both variants
are scored by ``loki.score.metrics.score_run`` against the same answer key. Both variants'
``score.json`` are written with ``loki.schemas.dump_json`` so the neutrality digest compares
bytes, not formatting.

Usage:
  run_l1.py run    --variant base|renamed --dataset DS --out RUNS --calib CALIB
                   [--renamed DS_RENAMED] [--split test] [--max-designs N]
  run_l1.py score  --variant base|renamed --dataset DS --out RUNS [--rename-map MAP]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from loki.schemas import dump_json
from loki.score.metrics import score_run

TRANSLATED = Path("/tmp/claude-1000/f3-translated")


def f3_designs(dataset: Path, split: str) -> list[tuple[str, int]]:
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    out = []
    for entry in manifest["designs"]:
        info = entry["floors"].get("f3")
        if entry["split"] == split and info is not None and info.get("status") == "ok":
            out.append((str(entry["design"]), int(info["nodes"])))
    return sorted(out, key=lambda x: (x[1], x[0]))


def renamed_floor(dataset: Path, design: str) -> Path:
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["designs"]:
        if entry["design"] == design:
            return dataset / design / entry["floors"]["f3"]["dir"]
    raise KeyError(design)


def run_one(netlist: Path, calib: Path | None, out: Path, timeout: int) -> dict[str, object]:
    if (out / "report.json").is_file():
        return {"status": "exists"}
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "loki.cli", "re", str(netlist), "--floor", "f3",
           "--calib", "none" if calib is None else str(calib), "--out", str(out)]
    start = time.monotonic()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    seconds = round(time.monotonic() - start, 1)
    status = "ok" if proc.returncode in (0, 1) else f"error {proc.returncode}"
    if proc.returncode not in (0, 1):
        (out / "stderr.txt").write_text(proc.stderr[-4000:], encoding="utf-8")
    return {"status": status, "seconds": seconds,
            "equiv": (json.loads((out / "report.json").read_text())["final_equiv"]["status"]
                      if (out / "report.json").is_file() else "missing")}


def inverse_map(rename_map: Path) -> dict[str, dict[str, str]]:
    raw = json.loads(rename_map.read_text(encoding="utf-8"))["designs"]
    return {design: {new: old for kind in ("cells", "nets", "modules")
                     for old, new in entry[kind].items()}
            for design, entry in raw.items()}


def translate(obj: object, inv: dict[str, str]) -> object:
    if isinstance(obj, dict):
        return {inv.get(k, k) if isinstance(k, str) else k: translate(v, inv)
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [translate(v, inv) for v in obj]
    if isinstance(obj, str):
        return inv.get(obj, obj)
    return obj


def score_variant(variant: str, dataset: Path, runs: Path, rename_map: Path | None) -> int:
    invs = inverse_map(rename_map) if rename_map else {}
    scored = 0
    for score_path in sorted(runs.rglob("score.json")):
        score_path.unlink()
    for run in sorted(runs.glob("*__f3")):
        design = run.name.removesuffix("__f3")
        run_dir = run / "re"
        floor_dir = dataset / design / "f3"
        if not (run_dir / "overlay.json").is_file():
            print(f"skip {design}: no run", file=sys.stderr)
            continue
        target = run_dir
        if variant == "renamed":
            tdir = TRANSLATED / variant / run.name
            tdir.mkdir(parents=True, exist_ok=True)
            for item in ("overlay.json", "report.json"):
                obj = json.loads((run_dir / item).read_text(encoding="utf-8"))
                (tdir / item).write_text(json.dumps(translate(obj, invs[design]), sort_keys=True)
                                         + "\n", encoding="utf-8")
            target = tdir
        score = score_run(target, floor_dir, 0.5)
        (run_dir / "score.json").write_text(dump_json(score), encoding="utf-8")
        scored += 1
    print(f"scored {scored} runs ({variant})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("run", "score"))
    ap.add_argument("--variant", required=True, choices=("base", "renamed"))
    ap.add_argument("--dataset", required=True, type=Path)
    ap.add_argument("--renamed", type=Path)
    ap.add_argument("--rename-map", type=Path)
    ap.add_argument("--calib", type=Path)
    ap.add_argument("--no-calib", action="store_true", help="run with the default tables")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--split", default="test")
    ap.add_argument("--max-designs", type=int, default=0)
    ap.add_argument("--timeout", type=int, default=7200)
    args = ap.parse_args()
    if args.stage == "score":
        return score_variant(args.variant, args.dataset, args.out, args.rename_map)
    assert args.calib is not None or args.no_calib
    calib = None if args.no_calib else args.calib
    source = args.renamed if args.variant == "renamed" else args.dataset
    designs = f3_designs(args.dataset, args.split)
    if args.max_designs:
        designs = designs[: args.max_designs]
    for design, nodes in designs:
        floor = (renamed_floor(source, design) if args.variant == "renamed"
                 else source / design / "f3")
        result = run_one(floor / "netlist.blif", calib, args.out / f"{design}__f3" / "re",
                         args.timeout)
        print(design, nodes, json.dumps(result), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
