"""Match single-pattern L3 designs and held-out library widths against the library.

``python -B match_run.py [JOBS]`` writes $GLET_OUT/match/scores.jsonl: one line per (set, design,
cell, mode) with, per library pattern, the best GDD agreement and cosine over (a) all library
entries and (b) entries whose measured flip-flop count equals the design's (width known). Sets:
``l3`` (TUNE and TEST single-family designs of the L3 v0 benchmark, library = all widths 1..32) and
``hold`` (library instances of the held-out widths HOLD against the library without them).
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "l3-detector"))
import gen  # noqa: E402
import l3dlib  # noqa: E402
import live  # noqa: E402
import sigs  # noqa: E402
import simil  # noqa: E402
import width_infer as wi  # noqa: E402

OUT = live.OUT
HOLD = (5, 11, 19, 27)
ENTRIES = l3dlib.ENTRIES
CELLS = live.CELLS
MODES = tuple(sigs.MODES)


def prep(g: dict[str, Any]) -> dict[str, Any]:
    """Precompute the normalised GDD per orbit and the log vector of one signature."""
    return {"n": [simil._norm(x) for x in g["gdd"]],
            "z": [simil.math.log1p(v) for v in g["orbit_totals"]]}


def sim(a: dict[str, Any], b: dict[str, Any]) -> tuple[float, float]:
    tot = 0.0
    for na, nb in zip(a["n"], b["n"], strict=True):
        if not na and not nb:
            tot += 1.0
        elif na and nb:
            d = simil.math.sqrt(sum((na.get(k, 0.0) - nb.get(k, 0.0)) ** 2
                                    for k in na.keys() | nb.keys()))
            tot += 1.0 - d / simil.math.sqrt(2.0)
    nx = simil.math.sqrt(sum(v * v for v in a["z"]))
    ny = simil.math.sqrt(sum(v * v for v in b["z"]))
    cos = (1.0 if nx == ny == 0 else 0.0 if nx == 0 or ny == 0 else
           sum(p * q for p, q in zip(a["z"], b["z"], strict=True)) / (nx * ny))
    return tot / len(a["n"]), cos


_LIB: dict[tuple[str, str], list[tuple[gen.Inst, int, dict[str, Any]]]] = {}


def ffcount(intent: Path) -> int:
    return int(wi.infer(json.loads(intent.read_text(encoding="utf-8")))["M3"])


def load_lib() -> None:
    for cell in CELLS:
        for mode in MODES:
            rows = []
            for inst in gen.instances():
                p = sigs.sig_path(mode, cell, inst.name)
                ij = OUT / "re" / cell / inst.name / "intent.json"
                ff = ffcount(ij) if ij.is_file() else -1
                rows.append((inst, ff, prep(json.loads(p.read_text(encoding="utf-8")))))
            _LIB[(cell, mode)] = rows


def score(job: tuple[str, str, str, str, str, int, tuple[int, ...]]) -> dict[str, Any]:
    kind, name, cell, mode, sigfile, ff, hold = job
    if not _LIB:
        load_lib()
    q = prep(json.loads(Path(sigfile).read_text(encoding="utf-8")))
    res: dict[str, Any] = {"set": kind, "design": name, "cell": cell, "mode": mode, "ff": ff}
    for tag in ("all", "ff"):
        best: dict[str, list[Any]] = {}
        for inst, eff, s in _LIB[(cell, mode)]:
            if kind == "hold" and inst.width in hold:
                continue
            if tag == "ff" and eff != ff:
                continue
            g, c = sim(q, s)
            cur = best.get(inst.pattern)
            if cur is None or g + c > cur[0] + cur[1]:
                best[inst.pattern] = [g, c, inst.name]
        res[tag] = best
    return res


FAILED: list[str] = []
MAX_WORK = 3e8  # fail fast: a design above this is recorded as a failure, not waited for


def make_sig(job: tuple[Path, str, Path]) -> str:
    net, mode, p = job
    if p.is_file():
        return ""
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        p.write_text(json.dumps(sigs.signature(net, mode, MAX_WORK), sort_keys=True),
                     encoding="utf-8")
    except Exception as exc:  # work cap or read failure: counted, not hidden
        return f"{p.stem} {p.parent.name} {mode}: {str(exc)[:60]}"
    return ""


def l3_jobs() -> list[tuple[str, str, str, str, str, int, tuple[int, ...]]]:
    sys.path.insert(0, str(HERE.parent / "l3-census"))
    lab = {r["design"]: r for r in l3dlib.read_csv(l3dlib.CENSUS_RES / "labels_rtl.csv")
           if r["status"] in ("ok", "manual")}
    skip = {(r["design"], r["cell"]) for r in
            l3dlib.read_csv(l3dlib.CENSUS_RES / "excluded_ffsub.csv")}
    jobs = []
    todo = []
    for r in l3dlib.read_csv(l3dlib.RES / "split_single.csv"):
        d = r["design"]
        fam = [e for e in ENTRIES if d in lab and lab[d][e] not in ("", "0")]
        if len(fam) != 1:
            continue
        for cell in CELLS:
            net = l3dlib.netlist_path(l3dlib.CENSUS, cell, d)
            ij = l3dlib.intent_path(l3dlib.CENSUS, cell, d)
            if (d, cell) in skip or not net.is_file() or not ij.is_file():
                continue
            for mode in MODES:
                p = OUT / "sig_l3" / mode / cell / f"{d}.json"
                todo.append((net, mode, p))
                jobs.append(("l3", d, cell, mode, str(p), ffcount(ij), ()))
    with ProcessPoolExecutor(10) as pool:
        errs = list(pool.map(make_sig, todo, chunksize=8))
    FAILED.extend(e for e in errs if e)
    return [j for j in jobs if Path(j[4]).is_file()]


def hold_jobs() -> list[tuple[str, str, str, str, str, int, tuple[int, ...]]]:
    jobs = []
    for inst in gen.instances():
        if inst.width not in HOLD:
            continue
        for cell in CELLS:
            ij = OUT / "re" / cell / inst.name / "intent.json"
            for mode in MODES:
                jobs.append(("hold", inst.name, cell, mode,
                             str(sigs.sig_path(mode, cell, inst.name)),
                             ffcount(ij) if ij.is_file() else -1, HOLD))
    return jobs


def main(argv: list[str]) -> int:
    n = int(argv[0]) if argv else 8
    jobs = l3_jobs() + hold_jobs()
    out = OUT / "match"
    out.mkdir(exist_ok=True)
    with ProcessPoolExecutor(n) as pool:
        rows = list(pool.map(score, jobs, chunksize=4))
    with (out / "scores.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    (out / "failures.txt").write_text("\n".join(FAILED) + "\n", encoding="utf-8")
    print(len(rows), "rows;", len(FAILED), "signature failures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
