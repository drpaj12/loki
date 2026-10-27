"""Stage 3: detector arms on the S7 (gates) and S8 (LUTs) netlists, recall per kind.

    python run_detect.py gt SET      # ground truth per design and snapshot (Odin III)
    python run_detect.py run SET     # B, W, WB with loki re (heavy-run); skips finished runs
    python run_detect.py score       # per-design counts -> l15_detect.csv (no Odin III)

``gt`` builds the round-5 word cells at S6 (take_snapshot), derives the instances with
``loki.score.gt.derive_instances`` and gives each word the cells of S7/S8 that drive a net whose
construct-leaf set contains the word's leaf set (the span-subset rule of L0, on construct keys)."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from r6lib import DATA, HERE, SETS, read_csv, write_csv

from loki.audit.units import construct_key, leaf_constructs
from loki.model import Port, Snapshot, WordCell
from loki.odin import odin_module
from loki.schemas import dump_json
from loki.words import _const_nets, _const_ports, _edges

ARMS = {
    "B": "",
    "W": "wordfirst",
    "WB": "wordfirst,hard,ff_pattern,mux,arith,seqfn,fsm,bus,unit,role,wordgroup",
}
SNAPS = (7, 8)
TIME_BUDGET = 900


def _snapshot(words: dict[str, Any]) -> Snapshot:
    cells = tuple(
        WordCell(int(w["id"]), str(w["type"]), str(w["name"]), dict(w["params"]), (),
                 tuple(Port(n, len(nets), tuple(nets)) for n, nets in w["in"]),
                 tuple(Port(n, len(nets), tuple(nets)) for n, nets in w["out"]), bool(w["fsm"]))
        for w in words["words"]
    )
    return Snapshot(cells, (), str(words["top"]))


def _leaf_keys(nm: Any, records: dict[int, Any], rec: int) -> frozenset[Any]:
    return frozenset(construct_key(nm, c) for c in leaf_constructs(nm, records, rec))


def word_leaves(snapdir: Path, words: dict[str, Any]) -> dict[int, frozenset[Any]]:
    """Leaf-construct key set of each S6 word (by node name in the S6 map)."""
    nm = odin_module().read_name_map(snapdir / "s6.json.names")
    records = {r.number: r for r in nm.records}
    by_name: dict[str, list[Any]] = defaultdict(list)
    for obj in nm.objects:
        if obj.kind == "node" and obj.records and obj.full:
            by_name[obj.full.rsplit("@", 1)[0].rsplit("/", 1)[-1]].append(obj)
    out: dict[int, frozenset[Any]] = {}
    for w in words["words"]:
        # the nodes are unnamed; the map's full name is ``<hier>/$c<node id>@file:line``
        hits = by_name.get(str(w["name"]) or f"$c{w['id']}", [])
        if len(hits) == 1:
            out[int(w["id"])] = _leaf_keys(nm, records, hits[0].records[0])
    return out


def net_cells(blif: Path) -> dict[str, str]:
    """BLIF net name to the label of the cell that drives it (the label ``loki re`` uses)."""
    from loki.re.fngraph import from_design
    from loki.re.normalise import load_level0

    graph = from_design(load_level0(blif, "f2", None, None))
    return {graph.names[net]: graph.label(cid) for net, cid in graph.driver.items()
            if net in graph.names}


def footprints(snapdir: Path, k: int, wl: dict[int, frozenset[Any]]) -> dict[int, list[str]]:
    nm = odin_module().read_name_map(snapdir / f"b{k}.blif.names")
    records = {r.number: r for r in nm.records}
    drv = net_cells(snapdir / f"b{k}.blif")
    nets = {o.name: _leaf_keys(nm, records, o.records[0])
            for o in nm.objects if o.records and o.name in drv}
    out: dict[int, list[str]] = {}
    for wid, leaves in wl.items():
        if leaves:
            out[wid] = sorted({drv[n] for n, ls in nets.items() if leaves <= ls})
    return out


def gt_design(snapdir: Path, out: Path) -> None:
    words = json.loads((snapdir / "manifest.json").read_text(encoding="utf-8"))["words"]
    snap = _snapshot(words)
    const = _const_nets(snap)
    edges = _edges(snap)
    wl = word_leaves(snapdir, words)
    for k in SNAPS:
        foot = footprints(snapdir, k, wl)
        obj = {"schema": 1, "edges": edges, "words": [
            {"id": w.id, "type": w.type, "params": {a: b for a, b in w.params.items()
                                                    if not isinstance(b, str)},
             "fsm": w.fsm, "const_ports": _const_ports(w, const),
             "footprint": foot.get(w.id, [])} for w in snap.words]}
        (out / f"gt{k}.json").write_text(dump_json(obj), encoding="utf-8")


def cmd_gt(name: str) -> None:
    for row in read_csv(DATA / "snap" / name / "status.csv"):
        if row["status"] != "ok":
            continue
        out = DATA / "detect" / name / row["design"]
        out.mkdir(parents=True, exist_ok=True)
        if (out / "gt8.json").is_file():
            continue
        try:
            gt_design(DATA / "snap" / name / row["design"], out)
        except Exception as err:
            (out / "gt_error.txt").write_text(repr(err), encoding="utf-8")


def _one(job: tuple[Path, str, str, int, Path]) -> str:
    netlist, arm, detectors, k, out = job
    if (out / "overlay.json").is_file():
        return "exists"
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "loki.cli", "re", str(netlist), "--floor", "f2", "--calib",
           "none", "--features", "none", "--time-budget", str(TIME_BUDGET), "--out", str(out)]
    if detectors:
        cmd += ["--detectors", detectors]
    t0 = time.monotonic()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=TIME_BUDGET + 120,
                           check=False)
    except subprocess.TimeoutExpired:
        (out.parent / f"timeout_{arm}{k}.txt").write_text("timeout", encoding="utf-8")
        return "timeout"
    if not (out / "overlay.json").is_file():
        (out.parent / f"stderr_{arm}{k}.txt").write_text(p.stderr[-2000:], encoding="utf-8")
        return f"error {p.returncode}"
    (out.parent / f"seconds_{arm}{k}.txt").write_text(f"{time.monotonic() - t0:.2f}")
    return "ok"


def cmd_run(name: str) -> None:
    jobs = []
    for row in read_csv(DATA / "snap" / name / "status.csv"):
        d = DATA / "detect" / name / row["design"]
        if row["status"] != "ok" or not (d / "gt8.json").is_file():
            continue
        for k in SNAPS:
            for arm, dets in ARMS.items():
                blif = DATA / "snap" / name / row["design"] / f"b{k}.blif"
                jobs.append((blif, arm, dets, k, d / f"{arm}{k}"))
    with ThreadPoolExecutor(3) as pool:
        res = list(pool.map(_one, jobs))
    print(name, len(res), {r: res.count(r) for r in set(res)})


def cmd_score() -> None:
    from loki.score.gt import SCORED_TYPES, derive_instances
    from loki.score.metrics import construct_scores, load_preds

    rows: list[list[Any]] = []
    for name in SETS:
        for dd in sorted((DATA / "detect" / name).glob("*")):
            for k in SNAPS:
                gtp = dd / f"gt{k}.json"
                if not gtp.is_file():
                    continue
                inst = derive_instances(json.loads(gtp.read_text(encoding="utf-8")))
                for arm in ARMS:
                    ov = dd / f"{arm}{k}" / "overlay.json"
                    if not ov.is_file():
                        continue
                    preds = load_preds(json.loads(ov.read_text(encoding="utf-8")))
                    sc = construct_scores(preds, inst, 0.5)
                    for kind in sorted(SCORED_TYPES):
                        r = sc.get(kind, {"counted": 0, "matched": 0})
                        gt = sum(1 for g in inst if g.type in SCORED_TYPES[kind])
                        rows.append([name, dd.name, f"S{k}", arm, kind, r["counted"],
                                     r["matched"], gt])
    write_csv(HERE / "l15_detect_design.csv",
              ["set", "design", "snapshot", "arm", "kind", "counted", "matched", "gt"], rows)


def main(argv: list[str]) -> int:
    if argv[0] == "gt":
        cmd_gt(argv[1])
    elif argv[0] == "run":
        cmd_run(argv[1])
    else:
        cmd_score()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
