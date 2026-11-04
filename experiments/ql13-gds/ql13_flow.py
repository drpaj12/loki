"""Run the Odin III v1.4 silicon flow on the Q-L13 designs, one at a time, smallest first.

Each run is ``tools/heavy-run python3 silicon_flow.py`` (ODIN3_HEAVY_OK=1 must be set) in
``$QL13_OUT/<name>/``: the source is copied to ``src/``, the flow writes ``out/`` (with ``out/prov``
step files), the stdout goes to ``flow.log``, the result to ``status.json`` (step results, exit
code, wall seconds). Resumable: a design with a ``status.json`` is skipped. Odin III is read only.
Usage: ``python3 -B ql13_flow.py [NAME_FILTER ...]``; ``--list`` prints the designs.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import ql13_env as env

TIMEOUT = 3600


def run_one(d: dict[str, str]) -> dict[str, object]:
    root = env.RUN / d["name"]
    status = root / "status.json"
    if status.is_file():
        return json.loads(status.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    (root / "src").mkdir(parents=True, exist_ok=True)
    src = root / "src" / Path(d["src"]).name
    shutil.copyfile(d["src"], src)
    cmd = [str(env.ODIN / "tools" / "heavy-run"), "python3", "-B",
           str(env.ODIN / "tools" / "silicon" / "silicon_flow.py"), str(src), "--top", d["top"],
           "--out", str(root / "out"), "--tools", str(env.TOOLS), "--odin3", str(env.ODIN_BIN)]
    if d["clock"]:
        cmd += ["--clock", d["clock"]]
    t0 = time.monotonic()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT, check=False,
                           stdin=subprocess.DEVNULL, env=dict(os.environ, ODIN3_HEAVY_OK="1"))
        out, code = p.stdout + p.stderr, p.returncode
    except subprocess.TimeoutExpired as err:
        out, code = f"timeout after {TIMEOUT}s\n{err.stdout or ''}", 124
    secs = time.monotonic() - t0
    (root / "flow.log").write_text(out, encoding="utf-8")
    steps: dict[str, str] = {}
    for line in out.splitlines():
        name, sep, rest = line.partition(": ")
        if sep and name.isalpha():
            steps[name] = rest.strip()
    res: dict[str, object] = {"name": d["name"], "top": d["top"], "clock": d["clock"],
                              "exit": code, "seconds": round(secs, 1), "steps": steps}
    status.write_text(json.dumps(res, sort_keys=True), encoding="utf-8")
    return res


def main(argv: list[str]) -> int:
    rows = env.designs()
    if argv == ["--list"]:
        for r in rows:
            print(r["name"], r["bytes"], r["clock"] or "-")
        return 0
    rows = [r for r in rows if not argv or any(a in r["name"] for a in argv)]
    for d in rows:
        res = run_one(d)
        steps = res["steps"]
        assert isinstance(steps, dict)
        last = list(steps.items())[-1] if steps else ("", "")
        print(f"{d['name']:<32} exit {res['exit']} {res['seconds']:>7}s  last {last[0]}: "
              f"{str(last[1])[:80]}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
