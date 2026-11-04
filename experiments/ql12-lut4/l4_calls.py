"""Prompts, call files and batches of the lut4 run (reduced subset, no model call).

Usage: ``python -B l4_calls.py`` (after ``l4_run.py blocks``). Builds the prompts exactly as
``q12_build.main_calls`` (frozen templates of ql12-k4k6; leak gate; sha256 of the two templates
checked), then keeps the reduced-run subset (Q-L12 amendment 9): every arm A call, and the arm D
calls of designs of at most 64 blocks. Calls are numbered from 1 in the new run root. Writes
``<run>/calls/``, ``<run>/calls.jsonl``, ``batches.json``, ``batches-D.json``, the compact
``run-batches.json`` (``[[batch, [call, ...]], ...]``), ``calls_table.csv`` (sha256 of the text after
the user-message delimiter), ``counts.csv``, ``designs.json``, ``blocks_summary.csv``, ``a_limit.csv``.
It also re-hashes every call file and fails on a mismatch with ``calls_table.csv``.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from typing import Any

import l4_env as l4

env = l4.env
bd: Any = env.mod("q12_build")
common: Any = env.mod("common")
bp: Any = env.mod("build_prompts")
MAX_D_BLOCKS = 64


def check_templates() -> None:
    for name, want in l4.FROZEN.items():
        got = hashlib.sha256((l4.K46 / name).read_bytes()).hexdigest()
        if got != want:
            raise SystemExit(f"frozen prompt {name} changed: {got}")


def subset(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in calls if c["arm"] == "A" or c["n_blocks"] <= MAX_D_BLOCKS]


def write_counts_full(recs: list[dict[str, Any]], full: list[dict[str, Any]]) -> None:
    """Counts of the full lut4 call set (before the subset), for the record."""
    with (env.HERE / "counts_full.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["set", "calls_A", "calls_D", "est_tokens_in", "est_tokens_out"])
        for label, sel in (("all designs, all blocks", full), ("reduced run", subset(full))):
            w.writerow([label, sum(c["arm"] == "A" for c in sel),
                        sum(c["arm"] == "D" for c in sel),
                        sum(c["est_tokens_in"] for c in sel),
                        sum(c["est_tokens_out"] for c in sel)])


def compact(path_in: str, path_out: str) -> None:
    data = json.loads((env.HERE / path_in).read_text(encoding="utf-8"))
    out = [[b["batch"], [c["call"] for c in b["calls"]]] for b in data["batches"]]
    (env.HERE / path_out).write_text(json.dumps(out, separators=(",", ":")) + "\n",
                                     encoding="utf-8", newline="\n")


def set_run_dir() -> None:
    for name in ("batches.json", "batches-D.json"):
        p = env.HERE / name
        d = json.loads(p.read_text(encoding="utf-8"))
        d["run_dir"] = "work/ql12l4-out"
        p.write_text(json.dumps(d, sort_keys=True, indent=1) + "\n", encoding="utf-8",
                     newline="\n")


def verify_files() -> int:
    n = bad = 0
    with (env.HERE / "calls_table.csv").open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            text = (env.RUN / "calls" / f"call-{int(r['call']):04d}.txt").read_text(
                encoding="utf-8")
            user = text.split(bd.DELIM_USER, 1)[1]
            n += 1
            bad += hashlib.sha256(user.encode("utf-8")).hexdigest() != r["prompt_sha256"]
    print(f"call files hashed {n}, mismatches {bad}")
    return bad


def main() -> int:
    check_templates()
    system = common.system_msg()
    if bp.leak_hits(system):
        raise SystemExit("leak gate: system message")
    prefix = common.prefix_file().read_text(encoding="utf-8")
    bp.check_prefix(prefix)
    recs = [bd.design_record(ep, r, prefix) for r in bd.problems() for ep in env.ENDPOINTS
            if bd.available(ep, r["problem"])]
    full = bd.order_calls(recs, system)
    write_counts_full(recs, full)
    calls = subset(full)
    bd.write_all(recs, calls, system)
    set_run_dir()
    compact("batches.json", "run-batches.json")
    print(len(calls), "calls", {a: sum(1 for c in calls if c["arm"] == a) for a in bd.ARMS},
          "full set", len(full))
    return 1 if verify_files() else 0


if __name__ == "__main__":
    sys.exit(main())
