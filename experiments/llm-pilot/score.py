"""Score collected records with Icarus Verilog as ``VE/Makefile.in`` does.

Usage: ``python -I score.py run --records DIR [--arm A ...]`` or ``python -I score.py preflight``.
Compile: ``iverilog -Wall -Winfloop -Wno-timescale -g2012 -s tb -o <bin> sample.sv test.sv ref.sv``;
run: ``vvp <bin>`` under a 30 s timeout. The test and reference files are read from VE in place
(read-only); the binary and logs are written in the record directory.
Outcomes: no-output, syntax, compile, runtime, timeout, pass.
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
common = importlib.import_module("common")

TIMEOUT_S = 30
_MISMATCH = re.compile(r"Mismatches:\s*(\d+)\s+in\s+(\d+)\s+samples")
OUTCOMES = ("no-output", "syntax", "compile", "runtime", "timeout", "pass")


def classify_compile(returncode: int, log: str) -> str:
    if returncode == 0:
        return ""
    return "syntax" if "syntax error" in log else "compile"


def classify_sim(log: str) -> tuple[str, int, int]:
    """(outcome, mismatches, samples) from a simulation log."""
    m = _MISMATCH.search(log)
    if not m:
        return "runtime", -1, 0
    miss, total = int(m.group(1)), int(m.group(2))
    return ("pass" if miss == 0 and total > 0 else "runtime"), miss, total


def run_sample(sample: Path, problem: str, workdir: Path) -> dict[str, Any]:
    """Compile and simulate ``sample`` against the problem's testbench and reference."""
    iverilog = shutil.which("iverilog")
    vvp = shutil.which("vvp")
    if not iverilog or not vvp:
        raise FileNotFoundError("iverilog and vvp are required")
    ds = common.dataset_dir()
    binary = workdir / "sim.bin"
    cmd = [iverilog, "-Wall", "-Winfloop", "-Wno-timescale", "-g2012", "-s", "tb", "-o",
           str(binary), str(sample), str(ds / f"{problem}_test.sv"), str(ds / f"{problem}_ref.sv")]
    t0 = time.monotonic()
    comp = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=str(workdir))
    clog = comp.stdout + comp.stderr
    (workdir / "compile.log").write_text(clog, encoding="utf-8", newline="\n")
    res: dict[str, Any] = {"compile_seconds": round(time.monotonic() - t0, 2),
                           "mismatches": -1, "samples": 0, "sim_seconds": 0.0}
    bad = classify_compile(comp.returncode, clog)
    if bad:
        return {**res, "outcome": bad}
    t1 = time.monotonic()
    try:
        sim = subprocess.run([vvp, str(binary)], capture_output=True, text=True, check=False,
                             cwd=str(workdir), timeout=TIMEOUT_S)
        slog = sim.stdout + sim.stderr
        outcome, miss, total = classify_sim(slog)
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout if isinstance(exc.stdout, str) else ""
        slog, outcome, miss, total = out + "\nTIMEOUT\n", "timeout", -1, 0
    (workdir / "sim.log").write_text(slog, encoding="utf-8", newline="\n")
    return {**res, "outcome": outcome, "mismatches": miss, "samples": total,
            "sim_seconds": round(time.monotonic() - t1, 2)}


def score_record(rec: Path) -> dict[str, Any]:
    info = json.loads((rec / "extract.json").read_text(encoding="utf-8"))
    problem = info["problem"]
    if not info["found_begin_done"]:
        res: dict[str, Any] = {"outcome": "no-output", "mismatches": -1, "samples": 0}
        if info["fallback_lines"]:
            fb = run_sample(rec / "fallback.sv", problem, rec)
            res["fallback_outcome"] = fb["outcome"]
    else:
        res = run_sample(rec / "sample.sv", problem, rec)
    res.update({"arm": info["arm"], "problem": problem, "pass": res["outcome"] == "pass"})
    (rec / "result.json").write_text(json.dumps(res, sort_keys=True, indent=1) + "\n",
                                     encoding="utf-8", newline="\n")
    return res


def score_all(records: Path, arms: list[str]) -> list[dict[str, Any]]:
    out = []
    for ex in sorted(records.glob("*/*/extract.json")):
        if not arms or ex.parent.parent.name in arms:
            out.append(score_record(ex.parent))
    return out


def preflight(names: list[str], root: Path) -> list[tuple[str, str]]:
    """Each reference, renamed to TopModule, must pass its own testbench."""
    rows = []
    for p in names:
        rec = root / p
        rec.mkdir(parents=True, exist_ok=True)
        ref = (common.dataset_dir() / f"{p}_ref.sv").read_text(encoding="utf-8")
        (rec / "sample.sv").write_text(re.sub(r"\bRefModule\b", "TopModule", ref),
                                       encoding="utf-8", newline="\n")
        rows.append((p, run_sample(rec / "sample.sv", p, rec)["outcome"]))
    return rows


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--records", type=Path, required=True)
    r.add_argument("--arm", action="append", default=[])
    sub.add_parser("preflight")
    a = ap.parse_args(argv)
    if a.cmd == "preflight":
        picked = importlib.import_module("make_hints").selected()
        rows = preflight(picked, common.run_dir() / "preflight")
        bad = [p for p, o in rows if o != "pass"]
        print(f"preflight: {len(rows) - len(bad)}/{len(rows)} pass; failing: {bad}")
        return 1 if bad else 0
    res = score_all(a.records, a.arm)
    counts: dict[str, int] = {}
    for x in res:
        counts[x["outcome"]] = counts.get(x["outcome"], 0) + 1
    print(json.dumps({"scored": len(res), "outcomes": counts}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
