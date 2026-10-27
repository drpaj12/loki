"""Driver of the Loki vs HAL/DANA comparison (pre-registration + Amendment 1).

    run_hal.py plan
    run_hal.py loadcheck OUT [--floors f2,f3] [--sample 30]            # step 2, corpus train
    run_hal.py lutcheck OUT                                            # lut6.hgl bit_order
    run_hal.py summary OUT --sets BIG --floors f2                      # descriptive table
    run_hal.py roundtrip OUT [--sets MI,VT,BIG] [--floors f2,f3]     # Amendment A8
    run_hal.py run OUT --setting 8|2 [--sets ..] [--floors ..] [--permute SEED] [--fresh]
    run_hal.py repeat OUT [--fresh]                                 # Amendment A7
    run_hal.py f2f3 OUT                                            # DANA f2 vs f3, DFFSR search
    run_hal.py permute OUT [--fresh]                                # Amendment A6
    run_hal.py score OUT [--setting 8] [--permute SEED]            # tables + decision

``OUT`` is a data directory outside the repo (a fresh ``mktemp -d``); nothing is deleted. Run with
``PYTHONPATH=<repo>:<repo>/experiments/round5`` (the round-5 helpers and ``loki``). The HAL
binary is ``$HAL_BIN`` (default ``hal`` on PATH).
Designs are always taken smallest first (node count of the floor in the L0 manifest). All paths
come from ``r5lib`` (environment variables, workspace-relative defaults).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import r5lib

from loki.hal import blif2hal
from loki.hal.blif import Blif, Gate, read_blif
from loki.hal.dana import parse_groups_txt
from loki.hal.wordscore import (
    WordScore,
    dana_words,
    group_shape,
    gt_words,
    loki_words,
    round5_register,
    score_words,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

HGL = {"f2": REPO / "experiments" / "hal" / "hgl" / "lut6.hgl",
       "f3": REPO / "experiments" / "hal" / "hgl" / "cmos6.hgl"}
TIMEOUT = {"MI": 900, "VT": 900, "BIG": 1800, "CT": 900}
SETTINGS = (8, 2)
SCORE_FIELDS = ("n_pred", "n_gt", "exact_pred", "exact_gt", "matched", "pur_num", "pur_den",
                "comp_num", "comp_den", "cov_num", "cov_den")


@dataclass(frozen=True)
class Item:
    set: str
    floor: str
    design: str
    blif: Path
    floor_dir: Path
    nodes: int

    @property
    def key(self) -> str:
        return f"{self.set}-{self.floor}/{self.design}"

    def loki_re(self, arm: str) -> Path:
        return r5lib.run_dir(arm, self.set, self.floor, self.design)


def _nodes(dataset: Path, design: str, floor: str) -> int:
    for e in r5lib.manifest(dataset)["designs"]:
        if e["design"] == design:
            return int(e["floors"][floor].get("nodes", 0))
    return 0


def items(sets: list[str], floors: list[str]) -> list[Item]:
    out: list[Item] = []
    for fl in floors:
        if "MI" in sets:
            for d in r5lib.ok_designs(r5lib.MICRO, fl):
                out.append(_item("MI", fl, r5lib.MICRO, d, d))
        if "VT" in sets:
            for d in r5lib.ok_designs(r5lib.VEVAL, fl, "test"):
                out.append(_item("VT", fl, r5lib.VEVAL, d, d))
        if "CT" in sets:  # corpus train split: load checks only, never scored
            split = r5lib.corpus_split()
            for d in r5lib.ok_designs(r5lib.CORPUS, fl):
                if split[d][1] == "train":
                    out.append(_item("CT", fl, r5lib.CORPUS, d, d))
        if "BIG" in sets and fl == "f2":
            for d in sorted(p.name for p in r5lib.BIGDIR.iterdir() if (p / "dataset").is_dir()):
                ds = r5lib.BIGDIR / d / "dataset"
                sub = next(ds.iterdir()).name
                if (ds / sub / "f2" / "netlist.blif").is_file():
                    out.append(Item("BIG", fl, d, ds / sub / "f2" / "netlist.blif",
                                    ds / sub / "f2", _graph_nodes(ds / sub / "f2")))
    return out


def _graph_nodes(floor_dir: Path) -> int:
    return len(json.loads((floor_dir / "graph.json").read_text(encoding="utf-8"))["nodes"])


def _item(set_name: str, floor: str, dataset: Path, design: str, _d: str) -> Item:
    fd = dataset / design / floor
    return Item(set_name, floor, design, fd / "netlist.blif", fd, _nodes(dataset, design, floor))


def order(its: list[Item]) -> list[Item]:
    """Smallest first within MI+VT (E_real) and then BIG, as in the pre-registration."""
    return sorted(its, key=lambda i: (i.set == "BIG", i.nodes, i.design))


def hal_cmd() -> list[str]:
    """HAL v4.5.0 with the DANA script (its ``--dataflow`` command line route does not run, see
    ``dana_run.py``); the netlist, library, output directory and group size travel in the
    environment."""
    return [os.environ.get("HAL_BIN", "hal"), "--volatile-mode", "--no-log", "--python-script",
            str(HERE / "dana_run.py")]


def hal_env(verilog: Path, floor: str, out: Path, setting: int) -> dict[str, str]:
    return {**os.environ, "HAL_V": str(verilog), "HAL_L": str(HGL[floor]), "HAL_OUT": str(out),
            "HAL_MIN": str(setting)}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def permuted(b: Blif, seed: int) -> tuple[Blif, dict[str, str]]:
    """Cells renamed by a seeded permutation (``q<k>``) and the cell order shuffled (A6)."""
    rng = random.Random(seed)
    named = [c.cname for c in b.cells if c.cname]
    idx = list(range(len(named)))
    rng.shuffle(idx)
    mapping = {old: f"q{idx[i]}" for i, old in enumerate(named)}
    cells = [replace(c, cname=mapping.get(c.cname, c.cname)) for c in b.cells]
    rng.shuffle(cells)
    return replace(b, cells=tuple(cells)), mapping


def run_hal(it: Item, setting: int, base: Path, permute: int | None,
            tag: str = "", fresh: bool = False) -> dict[str, Any]:
    """Convert and run DANA for one item; the row says ok / not convertible / error / timeout.
    A ``status.json`` from an earlier run is reused unless ``fresh`` (``--fresh``) is set."""
    work = base / f"hal{setting}{tag}" / it.key
    row: dict[str, Any] = {"key": it.key, "setting": setting, "status": "ok", "seconds": 0.0,
                           "detail": ""}
    if not fresh and (work / "status.json").is_file():
        return dict(json.loads((work / "status.json").read_text(encoding="utf-8")))
    try:
        b = read_blif(it.blif)
        if permute is not None:
            b, mapping = permuted(b, permute)
            _write(work / "mapping.json", json.dumps(mapping, sort_keys=True))
        text = blif2hal.convert(b, it.floor)
    except (blif2hal.ConvertError, ValueError) as exc:
        row.update(status="not_convertible", detail=str(exc)[:200])
        _write(work / "status.json", json.dumps(row, sort_keys=True))
        return row
    _write(work / "design.v", text)
    out = work / "out"
    out.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    try:
        proc = subprocess.run(hal_cmd(), env=hal_env(work / "design.v", it.floor, out, setting),
                              capture_output=True, text=True, timeout=TIMEOUT[it.set])
        _write(work / "stdout.txt", proc.stdout[-20000:])
        _write(work / "stderr.txt", proc.stderr[-20000:])
        if proc.returncode != 0 or not (out / "done.txt").is_file():
            row.update(status="error", detail=(proc.stderr + proc.stdout)[-300:])
    except subprocess.TimeoutExpired:
        row.update(status="timeout", detail=str(TIMEOUT[it.set]))
    row["seconds"] = round(time.monotonic() - start, 2)
    _write(work / "status.json", json.dumps(row, sort_keys=True))
    return row


def cmd_plan(_a: argparse.Namespace) -> int:
    for it in order(items(["MI", "VT", "BIG"], ["f2", "f3"])):
        print(f"{it.key}\t{it.nodes}")
    return 0


def _parse_list(s: str) -> list[str]:
    return [x for x in s.split(",") if x]


def cmd_roundtrip(a: argparse.Namespace) -> int:
    from loki.hal.sim import compare_traces
    out = Path(a.out)
    rows = []
    for it in order(items(_parse_list(a.sets), _parse_list(a.floors))):
        b = read_blif(it.blif)
        try:
            text = blif2hal.convert(b, it.floor)
        except blif2hal.ConvertError as exc:
            rows.append((it.key, "not_convertible", str(exc)[:120]))
            print(rows[-1], flush=True)
            continue
        wd = Path(tempfile.mkdtemp(prefix="rt-", dir=out))
        # BIG is checked at the primary outputs only (probe "out"). This was a choice made when
        # the BLIF simulator was still slow (before the gate-table cache of 9228d8c); no timing
        # was recorded for the larger probe, and BIG is not scored (Amendment 2 B4), so the
        # weaker check on BIG is a limit of the round trip, not part of a result.
        probe = "out" if it.set == "BIG" else "ffq"
        msg = compare_traces(b, it.floor, text, wd, 256, probe=probe)
        rows.append((it.key, "ok" if not msg else "FAIL", msg[:120]))
        print(rows[-1], flush=True)
    _write_csv(out / "roundtrip.csv", ("key", "status", "detail"), rows)
    return 0


def _write_csv(path: Path, header: tuple[str, ...], rows: list[Any]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def cmd_loadcheck(a: argparse.Namespace) -> int:
    """Step 2: DANA on an evenly spaced sample of corpus-train designs per floor (loading and
    parsing checks, no scoring): HAL loads the Verilog and the library, the groups.txt parses,
    every gate name is a flip-flop node of the design."""
    base = Path(a.out)
    rows = []
    for fl in _parse_list(a.floors):
        pool = order(items(["CT"], [fl]))
        step = max(1, len(pool) // a.sample)
        for it in pool[::step][:a.sample]:
            r = run_hal(it, 8, base / "loadcheck", None)
            note = ""
            if r["status"] == "ok":
                _gt, ffs = gt_words(it.floor_dir)
                groups = parse_groups_txt(
                    (base / "loadcheck" / "hal8" / it.key / "out" / "groups.txt").read_text(
                        encoding="utf-8"))
                names = {g for grp in groups for g in grp.gates}
                note = f"groups={len(groups)} ffs={len(ffs)} all_names_ff={names <= ffs} " \
                       f"covered={len(names & ffs)}"
            rows.append((it.key, r["status"], r["seconds"], r["detail"] or note))
            print(rows[-1], flush=True)
    _write_csv(base / "loadcheck.csv", ("key", "status", "seconds", "note"), rows)
    return 0


def _read_tt(path: Path) -> dict[str, int]:
    """``lut_tt.txt`` of one HAL run: gate name to truth table."""
    got: dict[str, int] = {}
    for ln in (path.read_text(encoding="utf-8").split("\n") if path.is_file() else []):
        if ln:
            name, _k, val = ln.split()
            got[name] = int(val)
    return got


def _lut_row(key: str, b: Blif, got: dict[str, int]) -> tuple[Any, ...]:
    """Compare HAL's LUTs with the BLIF covers: named gates by name, unnamed gates (HAL names
    them ``_c<index>``) as a multiset of truth tables, and the LUT counts."""
    gates = [g for g in b.cells if isinstance(g, Gate) and g.inputs]
    named = {g.cname: g.table() for g in gates if g.cname}
    unnamed = sorted(g.table() for g in gates if not g.cname)
    rest = sorted(v for n, v in got.items() if n not in named)
    bad = sum(got.get(n) != t for n, t in named.items()) + (unnamed != rest)
    return (key, len(named), len(unnamed), len(got), bad, int(len(gates) != len(got)))


def cmd_lutcheck(a: argparse.Namespace) -> int:
    """HAL's own truth table of every LUT gate (``lut_tt.py``) against the BLIF cover: checks the
    ``bit_order`` of ``lut6.hgl`` in a real HAL load, for every convertible MI and VT f2 design,
    and compares the number of LUTs on both sides (a mismatch is listed in the last column)."""
    base = Path(a.out) / "lutcheck"
    rows = []
    for it in order(items(["MI", "VT"], ["f2"])):
        b = read_blif(it.blif)
        try:
            text = blif2hal.convert(b, "f2")
        except blif2hal.ConvertError:
            continue
        wd = base / it.key
        _write(wd / "design.v", text)
        cmd = [os.environ.get("HAL_BIN", "hal"), "--volatile-mode", "--no-log", "--python-script",
               str(HERE / "lut_tt.py")]
        subprocess.run(cmd, env=hal_env(wd / "design.v", "f2", wd, 8), capture_output=True,
                       text=True, timeout=300, check=False)
        rows.append(_lut_row(it.key, b, _read_tt(wd / "lut_tt.txt")))
    _write_csv(Path(a.out) / "lutcheck.csv", ("key", "luts_blif_named", "luts_blif_unnamed",
                                              "luts_hal", "mismatches", "count_mismatch"), rows)
    bad, cnt = sum(r[4] for r in rows), sum(r[5] for r in rows)
    print(f"designs {len(rows)}, LUTs {sum(r[3] for r in rows)}, table mismatches {bad}, "
          f"designs with a LUT count mismatch {cnt}")
    return 0 if bad == 0 and cnt == 0 else 1


def cmd_summary(a: argparse.Namespace) -> int:
    """Descriptive table of a HAL run without the answer key (BIG, Amendment 2 B4): flip-flops,
    DANA groups, groups of at least 2 flip-flops, largest group, seconds."""
    base = Path(a.out)
    rows = []
    for it in order(items(_parse_list(a.sets), _parse_list(a.floors))):
        wd = base / f"hal{a.setting}" / it.key
        st = json.loads((wd / "status.json").read_text(encoding="utf-8")) if (
            wd / "status.json").is_file() else {"status": "not_run", "seconds": 0, "detail": ""}
        ffs = len([n for n in json.loads((it.floor_dir / "graph.json").read_text(
            encoding="utf-8"))["nodes"] if n["kind"] == "ff"])
        sizes = []
        if st["status"] == "ok":
            sizes = [g.size for g in parse_groups_txt(
                (wd / "out" / "groups.txt").read_text(encoding="utf-8"))]
        rows.append((it.design, st["status"], ffs, len(sizes), sum(s >= 2 for s in sizes),
                     max(sizes, default=0), st["seconds"], st["detail"]))
    _write_csv(base / f"summary-hal{a.setting}.csv", ("design", "status", "ffs", "groups",
                                                      "groups_ge2", "largest", "seconds",
                                                      "detail"), rows)
    return 0


def cmd_run(a: argparse.Namespace) -> int:
    base = Path(a.out)
    rows = []
    for it in order(items(_parse_list(a.sets), _parse_list(a.floors))):
        r = run_hal(it, a.setting, base, a.permute, "" if a.permute is None else f"-p{a.permute}",
                    a.fresh)
        rows.append((r["key"], r["setting"], r["status"], r["seconds"], r["detail"]))
        print(rows[-1], flush=True)
    tag = "" if a.permute is None else f"-p{a.permute}"
    _write_csv(base / f"run-hal{a.setting}{tag}.csv",
               ("key", "setting", "status", "seconds", "detail"), rows)
    return 0


def partition(groups_txt: Path) -> list[tuple[str, ...]]:
    return sorted(tuple(sorted(g.gates)) for g in parse_groups_txt(
        groups_txt.read_text(encoding="utf-8")))


def cmd_repeat(a: argparse.Namespace) -> int:
    """A7: smallest 5 designs of E_real at f2 (with a GT word), DANA twice, diff partitions.
    With ``--fresh`` both runs bypass the ``status.json`` cache (use an empty OUT directory)."""
    base = Path(a.out)
    its = [i for i in order(items(["MI", "VT"], ["f2"])) if _has_gt(i)][:5]
    res = []
    for it in its:
        r1 = run_hal(it, 8, base, None, fresh=a.fresh)
        r2 = run_hal(it, 8, base, None, tag="-rep", fresh=a.fresh)
        same = (r1["status"] == r2["status"] == "ok" and
                partition(base / "hal8" / it.key / "out" / "groups.txt") ==
                partition(base / "hal8-rep" / it.key / "out" / "groups.txt"))
        res.append((it.key, r1["status"], r2["status"], "identical" if same else "DIFFERENT"))
        print(res[-1], flush=True)
    _write_csv(base / "determinism.csv", ("key", "run1", "run2", "partitions"), res)
    return 0


def _has_gt(it: Item) -> bool:
    gt, _ = gt_words(it.floor_dir)
    return any(w.scored for w in gt)


def cmd_permute(a: argparse.Namespace) -> int:
    """A6: 6 designs (smallest 5 of E_real f2 with a GT word + the median-size one)."""
    base = Path(a.out)
    pool = [i for i in order(items(["MI", "VT"], ["f2"])) if _has_gt(i)]
    chosen = pool[:5] + [pool[len(pool) // 2]]
    res = []
    for it in chosen:
        r0 = run_hal(it, 8, base, None, fresh=a.fresh)
        rp = run_hal(it, 8, base, 7, tag="-p7", fresh=a.fresh)
        if r0["status"] != "ok" or rp["status"] != "ok":
            res.append((it.key, r0["status"], rp["status"], "n/a"))
            continue
        mp = json.loads((base / "hal8-p7" / it.key / "mapping.json").read_text(encoding="utf-8"))
        back = {v: k for k, v in mp.items()}
        pg = sorted(tuple(sorted(back.get(g, g) for g in grp)) for grp in partition(
            base / "hal8-p7" / it.key / "out" / "groups.txt"))
        same = pg == partition(base / "hal8" / it.key / "out" / "groups.txt")
        res.append((it.key, r0["status"], rp["status"], "identical" if same else "DIFFERENT"))
        print(res[-1], flush=True)
    _write_csv(base / "permutation.csv", ("key", "plain", "permuted", "partitions"), res)
    return 0


def _row(tool: str, it: Item, s: WordScore, extra: tuple[int, int, int] = (0, 0, 0)) -> list[Any]:
    return [tool, it.set, it.floor, it.design] + [getattr(s, f) for f in SCORE_FIELDS] + list(extra)


def _shape_row(tool: str, it: Item, pred: list[frozenset[str]], gt: list[Any]) -> list[Any]:
    sizes, merging = group_shape(pred, gt)
    return [tool, it.set, it.floor, it.design, len(sizes), merging, " ".join(map(str, sizes))]


def _score_item(it: Item, wd: Path, rows: list[list[Any]], shapes: list[list[Any]],
                drops: list[list[Any]], setting: int) -> None:
    """Score one design: the HAL row, then each Loki arm; a missing Loki run is logged."""
    gt, ffs = gt_words(it.floor_dir)
    hal_pred = dana_words(wd / "out" / "groups.txt", ffs)
    rows.append(_row(f"hal{setting}", it, score_words(hal_pred, gt)))
    shapes.append(_shape_row(f"hal{setting}", it, hal_pred, gt))
    for arm in ("W", "WB"):
        d = it.loki_re(arm)
        if not (d / "overlay.json").is_file():
            drops.append([it.key, f"loki{arm}", f"no_{arm}_run",
                          "overlay.json missing in the round-5 run directory; the design is "
                          f"left out of the Loki {arm} rows only"])
            continue
        pred = loki_words(d, ffs)
        r5 = round5_register(d, it.floor_dir)
        rows.append(_row(f"loki{arm}", it, score_words(pred, gt),
                         (r5["counted"], r5["matched"], r5["gt"])))
        shapes.append(_shape_row(f"loki{arm}", it, pred, gt))


def cmd_score(a: argparse.Namespace) -> int:
    """Per-design counts of both tools into ``scores-*.csv`` and the shape of the predicted groups
    into ``groups-*.csv`` (the statistics are in ``loki.hal.compare``). A design without a Loki W
    run is dropped from both arms; a design without a WB run is dropped from the WB rows only and
    logged in ``dropped-*.csv``."""
    base = Path(a.out)
    tag = "" if a.permute is None else f"-p{a.permute}"
    rows: list[list[Any]] = []
    shapes: list[list[Any]] = []
    drops: list[list[Any]] = []
    for it in order(items(_parse_list(a.sets), _parse_list(a.floors))):
        wd = base / f"hal{a.setting}{tag}" / it.key
        st = json.loads((wd / "status.json").read_text(encoding="utf-8")) if (
            wd / "status.json").is_file() else {"status": "not_run"}
        if st["status"] != "ok":
            drops.append([it.key, "hal", st["status"], st.get("detail", "")])
        elif not (it.loki_re("W") / "overlay.json").is_file():
            drops.append([it.key, "loki", "no_W_run", ""])
        else:
            _score_item(it, wd, rows, shapes, drops, a.setting)
    _write_csv(base / f"scores-hal{a.setting}{tag}.csv",
               ("tool", "set", "floor", "design", *SCORE_FIELDS, "r5_counted", "r5_matched",
                "r5_gt"), rows)
    _write_csv(base / f"groups-hal{a.setting}{tag}.csv",
               ("tool", "set", "floor", "design", "groups", "merging", "sizes"), shapes)
    _write_csv(base / f"dropped-hal{a.setting}{tag}.csv", ("key", "arm", "status", "detail"), drops)
    print(f"scored {len(rows)} rows, dropped {len(drops)}")
    return 0


def _count_dffsr(blif: Path) -> int:
    return sum(1 for ln in blif.read_text(encoding="utf-8").splitlines()
               if ln.startswith(".subckt") and ln.split()[1] == "DFFSR")


def _named_partition(groups_txt: Path, floor_dir: Path) -> list[tuple[str, ...]]:
    """DANA groups with the node ids replaced by the original flip-flop names of ``key.json``
    (node ids differ between the floors of one design; an unnamed node keeps its id)."""
    cells = json.loads((floor_dir / "key.json").read_text(encoding="utf-8"))["cells"]
    return sorted(tuple(sorted(cells.get(g, {}).get("name") or g for g in grp))
                  for grp in partition(groups_txt))


def cmd_f2f3(a: argparse.Namespace) -> int:
    """For every MI and VT design that HAL ran at both floors: are DANA's f2 and f3 partitions
    equal (``f2f3.csv``)? Also the number of ``DFFSR`` cells in every f2 and f3 netlist
    (``dffsr.csv``). DANA reads the FF graph and the control pins of the FF cells, so equal
    partitions and no DFFSR are the evidence behind the statement that DANA's f2 and f3 rows are
    equal by construction."""
    base = Path(a.out)
    f2f3, dffsr = [], []
    by = {(it.set, it.floor, it.design): it for it in items(["MI", "VT"], ["f2", "f3"])}
    for (s, fl, d), it in sorted(by.items()):
        dffsr.append((it.key, _count_dffsr(it.blif)))
        other = by.get((s, "f3", d))
        if fl != "f2" or other is None:
            continue
        p2, p3 = (base / "hal8" / f"{s}-{f}" / d / "out" / "groups.txt" for f in ("f2", "f3"))
        if not (p2.is_file() and p3.is_file()):
            f2f3.append((f"{s}/{d}", "not_both_run"))
            continue
        same = _named_partition(p2, it.floor_dir) == _named_partition(p3, other.floor_dir)
        f2f3.append((f"{s}/{d}", "equal" if same else "DIFFERENT"))
    _write_csv(base / "f2f3.csv", ("key", "partitions"), f2f3)
    _write_csv(base / "dffsr.csv", ("key", "dffsr_cells"), dffsr)
    eq = sum(r[1] == "equal" for r in f2f3)
    print(f"designs {len(f2f3)}, equal {eq}, different {sum(r[1] == 'DIFFERENT' for r in f2f3)}, "
          f"not run at both floors {sum(r[1] == 'not_both_run' for r in f2f3)}; DFFSR cells in "
          f"{sum(r[1] > 0 for r in dffsr)} of {len(dffsr)} netlists")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="run_hal.py", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan").set_defaults(fn=cmd_plan)
    cmds = {"summary": cmd_summary, "lutcheck": cmd_lutcheck, "loadcheck": cmd_loadcheck,
            "roundtrip": cmd_roundtrip, "run": cmd_run, "score": cmd_score,
            "repeat": cmd_repeat, "permute": cmd_permute, "f2f3": cmd_f2f3}
    for name, fn in cmds.items():
        p = sub.add_parser(name)
        p.add_argument("out")
        p.add_argument("--sets", default="MI,VT,BIG")
        p.add_argument("--floors", default="f2,f3")
        p.add_argument("--setting", type=int, default=8, choices=SETTINGS)
        p.add_argument("--permute", type=int, default=None)
        p.add_argument("--sample", type=int, default=30)
        p.add_argument("--fresh", action="store_true",
                       help="ignore the status.json cache of an earlier run")
        p.set_defaults(fn=fn)
    args = ap.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
