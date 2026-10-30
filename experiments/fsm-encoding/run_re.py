"""Run ``loki re`` on every built netlist of the population: ``run_re.py TAG [JOBS]``.

Reads ``OUT/build/<arm>/<design>/<floor>/netlist.blif``, writes ``OUT/re/TAG/<arm>/<floor>/
<design>/``. Smallest netlists first; resumes (an existing overlay.json is kept).
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
lib: Any = importlib.import_module("fsmlib")


def jobs_list(tag: str) -> list[tuple[int, Path, Path]]:
    todo = []
    for arm in lib.ARMS:
        for floor in lib.FLOORS:
            for d in lib.population():
                did = d["design"]
                net = lib.OUT / "build" / arm / did / floor / "netlist.blif"
                out = lib.OUT / "re" / tag / arm / floor / did
                if net.is_file() and not (out / "overlay.json").is_file():
                    todo.append((net.stat().st_size, net, out))
    return sorted(todo)


def one(job: tuple[int, Path, Path]) -> int:
    _, net, out = job
    floor = net.parent.name
    out.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-B", "-m", "loki.re.main", str(net), "--floor", floor,
           "--calib", "none", "--detectors", lib.DETECTORS, "--seed", "1", "--out", str(out)]
    done = subprocess.run(cmd, env=dict(os.environ), capture_output=True, text=True, check=False,
                          cwd=str(lib.OUT))
    (out / "stderr.txt").write_text(done.stderr[-2000:], encoding="utf-8")
    return done.returncode


def main(argv: list[str]) -> int:
    tag = argv[0]
    jobs = int(argv[1]) if len(argv) > 1 else 3
    todo = jobs_list(tag)
    with ThreadPoolExecutor(jobs) as pool:
        codes = list(pool.map(one, todo))
    print(f"{tag}: {len(todo)} runs, nonzero exit {sum(1 for c in codes if c)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
