"""Archive a controller dispatch dir into ``<run>/responses`` and write ``<run>/status.csv``.

Usage: ``python -I archive_run.py --src DIR --run RUN --model ID [--last-order N]
[--refused 009 027 ...]``. ``DIR/resp-NNN.txt`` is the reply of call order NNN;
``DIR/dispatch-log.tsv`` (order, status, tool calls, bytes, note) is copied to
``<run>/dispatch-log.tsv``. Orders are mapped to (arm, problem) through ``<run>/calls.jsonl``.
Status: ``ok`` (response present), ``refused`` (listed, no response file), ``no-file`` (listed with
``--no-file``: the reply never reached a file; counts as fail, outside the paired set), ``not_run`` (order above
``--last-order``). Refused calls are never retried. Nothing is deleted.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path


def archive(src: Path, run: Path, model: str, last_order: int, refused: set[int],
            no_file: frozenset[int] = frozenset()) -> dict[str, int]:
    calls = [json.loads(ln) for ln in (run / "calls.jsonl").read_text("utf-8").splitlines()]
    log: dict[int, list[str]] = {}
    log_path = src / "dispatch-log.tsv"
    for ln in log_path.read_text("utf-8").splitlines():
        cells = ln.split("\t")
        log[int(cells[0])] = cells
    shutil.copyfile(log_path, run / "dispatch-log.tsv")
    rows, counts = [], {"ok": 0, "refused": 0, "not_run": 0}
    for c in calls:
        o = c["order"]
        resp = src / f"resp-{o:03d}.txt"
        if o > last_order:
            status = "not_run"
        elif o in refused:
            status = "refused"
            if resp.exists():
                raise SystemExit(f"order {o:03d} is listed refused but has a response file")
        elif o in no_file:
            status = "no-file"
            if resp.exists():
                raise SystemExit(f"order {o:03d} is listed no-file but has a response file")
        elif resp.exists():
            status = "ok"
            dest = run / "responses" / c["arm"] / f"{c['problem']}.txt"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(resp, dest)
            meta = {"model": model, "order": o, "tool_calls": (log.get(o) or ["", "", ""])[2]}
            (dest.with_suffix(".meta.json")).write_text(
                json.dumps(meta, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        else:
            raise SystemExit(f"order {o:03d} is neither refused nor has a response file")
        counts[status] += 1
        cells = log.get(o, [])
        rows.append([f"{o:03d}", c["arm"], c["problem"], status,
                     cells[2] if len(cells) > 2 else "", cells[4] if len(cells) > 4 else ""])
    with (run / "status.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["order", "arm", "problem", "status", "tool_calls", "note"])
        w.writerows(rows)
    return counts


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--last-order", type=int, default=120)
    ap.add_argument("--refused", nargs="*", default=[])
    ap.add_argument("--no-file", nargs="*", default=[], dest="no_file",
                    help="orders whose reply never reached a file (status no-file)")
    a = ap.parse_args(argv)
    print(json.dumps(archive(a.src, a.run, a.model, a.last_order,
                             {int(x) for x in a.refused},
                             frozenset(int(x) for x in a.no_file)), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
