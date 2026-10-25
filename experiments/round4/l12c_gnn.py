"""RQ-L12c: GNN learning curve on corpus subsets and transfer to real designs.

Usage: l12c_gnn.py run [--floor f2|f3] [--workers N] | summarize
``run`` trains ``loki.analysis.gnn.train_eval`` (round-2 L2 settings) on corpus train subsets of
3, 6, 12, 24, 48, 70 designs per family (seeds 0, 1, 2) and on the VerilogEval train split
(reference), each scored on the corpus iid / ood test, the micros and the VerilogEval test split.
Every run is its own process (restartable: a finished run has ``conf.json``). ``summarize`` writes
``l12c_curve.csv`` and the per-design confusion table ``<data>/gnn/conf.json``.
"""

from __future__ import annotations

import csv
import json
import random
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import r4lib

PER_FAMILY = (3, 6, 12, 24, 48, 70)
SEEDS = (0, 1, 2)
SETNAMES = ("iid", "ood", "micro", "vetest")
GNN = r4lib.DATA / "gnn"


def make_view(name: str, floor: str, train: list[tuple[Path, str]],
              test: list[tuple[Path, str]]) -> Path:
    """A dataset directory of symlinks with a manifest whose train / test split is given."""
    view = GNN / "views" / name
    if (view / "manifest.json").is_file():
        return view
    view.mkdir(parents=True, exist_ok=True)
    entries = []
    for split, items in (("train", train), ("test", test)):
        for dataset, des in items:
            link = view / des
            if not link.exists():
                link.symlink_to(dataset / des)
            entries.append({"design": des, "benchmark": "micro", "split": split,
                            "floors": {floor: {"status": "ok", "nodes": 0}}})
    entries.sort(key=lambda e: str(e["design"]))
    (view / "manifest.json").write_text(
        json.dumps({"schema": 1, "designs": entries}, sort_keys=True), encoding="utf-8")
    return view


def test_items(floor: str) -> tuple[list[tuple[Path, str]], dict[str, str]]:
    sets = r4lib.eval_sets(floor)
    items: list[tuple[Path, str]] = []
    which: dict[str, str] = {}
    for s in SETNAMES:
        for dataset, des in sets[s]:
            if not has_logic(dataset, des, floor):
                continue
            items.append((dataset, des))
            which[des] = s
    return items, which


def has_logic(dataset: Path, design: str, floor: str) -> bool:
    """True when some logic node carries a construct type (the GNN needs one per train design)."""
    with (dataset / design / floor / "labels.csv").open(encoding="utf-8", newline="") as fh:
        return any(r["kind"] in ("lut", "ff", "gate", "hard") and r["construct_type"]
                   for r in csv.DictReader(fh))


def subset(floor: str, m: int, seed: int) -> list[tuple[Path, str]]:
    cs = r4lib.corpus_split()
    rnd = random.Random(seed)
    out: list[tuple[Path, str]] = []
    ok = r4lib.ok_designs(r4lib.CORPUS, floor)
    for fam in sorted({f for f, _ in cs.values()}):
        pool = [d for d in ok if cs[d] == (fam, "train") and has_logic(r4lib.CORPUS, d, floor)]
        rnd.shuffle(pool)
        out += [(r4lib.CORPUS, d) for d in sorted(pool[:m])]
    return out


def job_list(floor: str) -> list[tuple[str, str, int, int]]:
    jobs = [(floor, f"c{m}", m, s) for m in PER_FAMILY for s in SEEDS]
    jobs += [(floor, "ve", 0, s) for s in SEEDS]
    return jobs


def conf_of(out: Path, which: dict[str, str]) -> dict[str, dict[str, int]]:
    """Per test design: ``"true|pred" -> count`` from the predictions CSVs."""
    conf: dict[str, dict[str, int]] = {}
    for p in sorted(out.glob("predictions-*.csv")):
        des = p.stem.removeprefix("predictions-")
        cnt: Counter[str] = Counter()
        for line in p.read_text(encoding="utf-8").splitlines()[1:]:
            _, t, q = line.split(",")
            cnt[f"{t}|{q}"] += 1
        conf[des] = dict(sorted(cnt.items()))
    del which
    return conf


def run_one(job: tuple[str, str, int, int]) -> str:
    floor, tag, m, seed = job
    out = GNN / "runs" / floor / f"{tag}-s{seed}"
    if (out / "conf.json").is_file():
        return f"exists {out.name}"
    import torch

    torch.set_num_threads(2)
    from loki.analysis.gnn import train_eval

    items, which = test_items(floor)
    if tag == "ve":
        ve = [d for d in r4lib.ok_designs(r4lib.VEVAL, floor, "train")
              if has_logic(r4lib.VEVAL, d, floor)]
        train = [(r4lib.VEVAL, d) for d in ve]
    else:
        train = subset(floor, m, seed)
    view = make_view(f"{floor}-{tag}-s{seed}", floor, train, items)
    res = train_eval(view, floor, out, seed=seed)
    (out / "conf.json").write_text(
        json.dumps({"which": which, "conf": conf_of(out, which), "n_train": len(train),
                    "test": res["test"]}, sort_keys=True), encoding="utf-8")
    for p in out.glob("predictions-*.csv"):
        p.unlink()
    (out / "model.pt").unlink(missing_ok=True)
    return f"done {out.name} train={len(train)} test={res['test']}"


def run(floors: list[str], workers: int) -> int:
    jobs = [j for f in floors for j in job_list(f)]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for line in pool.map(run_one, jobs):
            print(line, flush=True)
    return 0


def macro_f1(conf: dict[str, int]) -> float:
    """Macro-F1 over the classes that occur in truth or prediction (as sklearn's default)."""
    tp: Counter[str] = Counter()
    fp: Counter[str] = Counter()
    fn: Counter[str] = Counter()
    labels: set[str] = set()
    for key, n in conf.items():
        t, q = key.split("|")
        labels.update((t, q))
        if t == q:
            tp[t] += n
        else:
            fn[t] += n
            fp[q] += n
    f = [2 * tp[c] / (2 * tp[c] + fp[c] + fn[c]) if 2 * tp[c] + fp[c] + fn[c] else 0.0
         for c in sorted(labels)]
    return sum(f) / len(f) if f else 0.0


def pooled(conf: dict[str, dict[str, int]], designs: list[str]) -> dict[str, int]:
    tot: Counter[str] = Counter()
    for d in designs:
        tot.update(conf.get(d, {}))
    return dict(tot)


def summarize() -> int:
    rows: list[list[Any]] = []
    table: dict[str, Any] = {}
    for floor in r4lib.FLOORS:
        for floor_, tag, m, seed in job_list(floor):
            p = GNN / "runs" / floor_ / f"{tag}-s{seed}" / "conf.json"
            if not p.is_file():
                continue
            obj = json.loads(p.read_text(encoding="utf-8"))
            table[f"{floor_}/{tag}-s{seed}"] = obj
            for s in SETNAMES:
                des = sorted(d for d, w in obj["which"].items() if w == s)
                c = pooled(obj["conf"], des)
                n = sum(c.values())
                acc = sum(v for k, v in c.items() if k.split("|")[0] == k.split("|")[1])
                rows.append([floor_, tag, m * 12 if tag != "ve" else obj["n_train"], seed, s,
                             len(des), n, round(acc / n, 6) if n else 0.0,
                             round(macro_f1(c), 6)])
    r4lib.write_csv(r4lib.OUT / "l12c_curve.csv",
                    ["floor", "arm", "n_train", "seed", "set", "n_designs", "n_nodes",
                     "accuracy", "macro_f1"], rows)
    (GNN / "conf.json").write_text(json.dumps(table, sort_keys=True), encoding="utf-8")
    print(len(rows), "rows")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if args[:1] == ["summarize"]:
        return summarize()
    if args[:1] == ["run"]:
        floors = list(r4lib.FLOORS)
        workers = 3
        if "--floor" in args:
            floors = [args[args.index("--floor") + 1]]
        if "--workers" in args:
            workers = int(args[args.index("--workers") + 1])
        return run(floors, workers)
    raise SystemExit(__doc__)


if __name__ == "__main__":
    raise SystemExit(main())
