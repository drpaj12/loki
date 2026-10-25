"""H16f: repetition evidence on the BIG set (arm W). Writes ``l16_big.csv`` (per design and kind),
``l16_big_null.csv`` (pooled F1 of the shuffled-flag draws, one ``random.Random`` per design seeded
by the sha256 of the design name, as Stage 0 says), ``l16_big_null_stream.csv`` (the same with one
``random.Random(16)`` stream over the designs: the seeding of the first Stage-2 run, a deviation
from Stage 0 kept for comparison) and ``l16_big_time.csv``.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

import dictlib
import l13_measure
import l16_eval
import r5lib

from loki.score.gt import SCORED_TYPES, derive_instances
from loki.score.metrics import Pred, construct_matches

DRAWS = 1000


def design_rows(name: str, ds: Path, sub: str,
                arm: str = "W") -> tuple[list[list[Any]], list[list[Any]]]:
    rd = r5lib.run_dir(arm, "BIG", "f2", name)
    fd = ds / sub / "f2"
    gts = derive_instances(json.loads((fd / "words.json").read_text(encoding="utf-8")))
    preds = l16_eval.counted(rd)
    fg = dictlib.load_fg(fd / "graph.json")
    keyed: dict[tuple[Any, ...], list[Pred]] = defaultdict(list)
    for p in preds:
        keyed[(p.kind, len(p.cells), l13_measure.induced_hash(fg, p.cells))].append(p)
    flag = {p.id: int(len(v) >= 2) for v in keyed.values() for p in v}
    rows: list[list[Any]] = []
    flags: list[list[Any]] = []
    for kind, types in sorted(SCORED_TYPES.items()):
        kp = [p for p in preds if p.kind == kind]
        kg = [g for g in gts if g.type in types]
        if not kp and not kg:
            continue
        hit = {m[0] for m in construct_matches(kp, kg)}
        rows.append([name, kind, len(kp), len(hit), len(kg),
                     sum(flag[p.id] for p in kp), sum(flag[p.id] for p in kp if p.id in hit)])
        flags.append([name, kind, [(flag[p.id], int(p.id in hit)) for p in kp]])
    return rows, flags


def f1(matched: int, counted: int, gt: int) -> float:
    return 2 * matched / (counted + gt) if counted + gt else 0.0


def main() -> int:
    order = json.loads((r5lib.DATA / "big_order.json").read_text(encoding="utf-8"))
    rows: list[list[Any]] = []
    allflags: list[list[Any]] = []
    times: list[list[Any]] = []
    for name in order:
        ds = r5lib.BIGDIR / name / "dataset"
        sub = next(ds.iterdir()).name
        rd = r5lib.run_dir("W", "BIG", "f2", name)
        sp = rd.parent / "seconds.txt"
        status = "ok" if (rd / "score.json").is_file() else (
            "timeout" if (rd.parent / "timeout.txt").is_file() else "missing")
        times.append([name, status, sp.read_text(encoding="utf-8").strip() if sp.is_file() else ""])
        if status != "ok":
            continue
        r, f = design_rows(name, ds, sub)
        rows += r
        allflags += f
    r5lib.write_csv(r5lib.OUT / "l16_big.csv",
                    ["design", "kind", "counted", "matched", "gt", "counted_F", "matched_F"], rows)
    r5lib.write_csv(r5lib.OUT / "l16_big_time.csv", ["design", "status", "seconds"], times)
    gt_total = sum(int(r[4]) for r in rows)
    stream = random.Random(16)
    per_design = {d: r5lib.seed_rng(d) for d, _k, _f in allflags}
    nulls: list[list[Any]] = []
    nulls_stream: list[list[Any]] = []
    for draw in range(DRAWS):
        kept = matched = kept_s = matched_s = 0
        for d, _k, fl in allflags:
            n_keep = sum(a for a, _ in fl)
            pick = per_design[d].sample(range(len(fl)), n_keep) if fl else []
            pick_s = stream.sample(range(len(fl)), n_keep) if fl else []
            kept += n_keep
            matched += sum(fl[i][1] for i in pick)
            kept_s += n_keep
            matched_s += sum(fl[i][1] for i in pick_s)
        nulls.append([draw, kept, matched, round(f1(matched, kept, gt_total), 6)])
        nulls_stream.append([draw, kept_s, matched_s, round(f1(matched_s, kept_s, gt_total), 6)])
    r5lib.write_csv(r5lib.OUT / "l16_big_null.csv", ["draw", "kept", "matched", "f1"], nulls)
    r5lib.write_csv(r5lib.OUT / "l16_big_null_stream.csv", ["draw", "kept", "matched", "f1"],
                    nulls_stream)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
