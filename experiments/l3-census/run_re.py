"""``loki re --intent`` on every built netlist: ``python -B run_re.py [JOBS] [CELL...]``.

Reads OUT/build/<cell>/..., writes OUT/re/<cell>/<design>/. Smallest netlist first; resumes
(an existing intent.json is kept); each run is capped at 6 GB address space and 300 s.
"""

from __future__ import annotations

import importlib
import os
import resource
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
lib: Any = importlib.import_module("l3lib")


def limit() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (6 << 30, 6 << 30))


def jobs_list(cells: list[str]) -> list[tuple[int, str, Path, Path]]:
    todo = []
    for cell in cells:
        for r in lib.manifest():
            net = lib.netlist(cell, r["design"])
            out = lib.OUT / "re" / cell / r["design"]
            if net.is_file() and not (out / "intent.json").is_file():
                todo.append((net.stat().st_size, cell, net, out))
    return sorted(todo)


def one(job: tuple[int, str, Path, Path]) -> int:
    _, cell, net, out = job
    out.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-B", "-m", "loki.re.main", str(net), "--floor", lib.FLOOR_OF[cell],
           "--calib", "none", "--detectors", lib.DETECTORS, "--seed", "1", "--features", "none",
           "--intent", "--time-budget", "300", "--out", str(out)]
    try:
        done = subprocess.run(cmd, env=dict(os.environ), capture_output=True, text=True,
                              check=False, cwd=str(lib.OUT), timeout=330, preexec_fn=limit)
        (out / "stderr.txt").write_text(done.stderr[-2000:], encoding="utf-8")
        return done.returncode
    except subprocess.TimeoutExpired:
        (out / "stderr.txt").write_text("timeout 330 s", encoding="utf-8")
        return 124


def main(argv: list[str]) -> int:
    jobs = int(argv[0]) if argv else 3
    cells = argv[1:] or list(lib.CELLS)
    todo = jobs_list(cells)
    with ThreadPoolExecutor(jobs) as pool:
        codes = list(pool.map(one, todo))
    print(f"{len(todo)} runs, nonzero exit {sum(1 for c in codes if c)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
