"""Run the Odin III v1.4 silicon flow on the Q-L13 designs, one at a time, smallest first.

Each run is ``tools/heavy-run python3 silicon_flow.py`` (ODIN3_HEAVY_OK=1 must be set) in
``$QL13_OUT/<name>/``: the source is copied to ``src/``, the flow writes ``out/`` (with ``out/prov``
step files), the stdout goes to ``flow.log``, the result to ``status.json`` (step results, exit
code, wall seconds). Resumable: a design with a ``status.json`` is skipped. Odin III is read only.
Usage: ``python3 -B ql13_flow.py [--redo] [NAME_FILTER ...]`` (``--redo`` runs again over a
status.json); ``--list`` prints the designs.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import ql13_env as env

# Time limit of the flow itself, INSIDE heavy-run (``heavy-run timeout -s KILL N ...``), so the wait
# for a heavy slot (up to ODIN3_HEAVY_WAIT, 14400 s) is not counted. The Python timeout is only a
# backstop: slot wait + flow limit + margin; it kills the whole process group (no orphan keeps a
# slot).
FLOW_LIMIT = 28800
SLOT_WAIT = 14400
BACKSTOP = SLOT_WAIT + FLOW_LIMIT + 600


def stage_source(d: dict[str, str], dst: Path) -> None:
    """Copy the design source to ``dst``. The flow reads one file and has no include path, and
    ``read_verilog`` needs one top module in it, so two things are staged (the code is unchanged):
    the ``defines.v`` that a tinyriscv module includes goes beside the copy, and for
    ``picorv32_pcpi_div`` (a module of the multi-module ``picorv32.v``) the copy holds that module
    only, verbatim from ``module`` to ``endmodule``."""
    src = Path(d["src"])
    if d["name"] == "picorv32_pcpi_div":
        text = src.read_text(encoding="utf-8")
        start = text.index(f"module {d['top']}")
        end = text.index("endmodule", start) + len("endmodule")
        dst.write_text(text[start:end] + "\n", encoding="utf-8")
        return
    shutil.copyfile(src, dst)
    if (src.parent / "defines.v").is_file():
        shutil.copyfile(src.parent / "defines.v", dst.parent / "defines.v")


def build_cmd(d: dict[str, str], src: Path, root: Path) -> list[str]:
    """heavy-run first, the flow time limit inside it (slot wait not counted)."""
    cmd = [str(env.ODIN / "tools" / "heavy-run"), "timeout", "-s", "KILL", str(FLOW_LIMIT),
           "python3", "-B", str(env.ODIN / "tools" / "silicon" / "silicon_flow.py"), str(src),
           "--top", d["top"], "--out", str(root / "out"), "--tools", str(env.TOOLS),
           "--odin3", str(env.ODIN_BIN)]
    if d["clock"]:
        cmd += ["--clock", d["clock"]]
    return cmd


def run_group(cmd: list[str], limit: float) -> tuple[str, int]:
    """Run ``cmd`` in its own session; on timeout kill the whole group (flock children too)."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            stdin=subprocess.DEVNULL, start_new_session=True,
                            env=dict(os.environ, ODIN3_HEAVY_OK="1"))
    try:
        out, _ = proc.communicate(timeout=limit)
        return out, proc.returncode
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, _ = proc.communicate()
        return f"timeout after {limit}s (process group killed)\n{out or ''}", 124


def run_one(d: dict[str, str], redo: bool = False) -> dict[str, object]:
    root = env.RUN / d["name"]
    status = root / "status.json"
    if status.is_file() and not redo:
        return json.loads(status.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    (root / "src").mkdir(parents=True, exist_ok=True)
    src = root / "src" / Path(d["src"]).name
    stage_source(d, src)
    cmd = build_cmd(d, src, root)
    t0 = time.monotonic()
    out, code = run_group(cmd, BACKSTOP)
    secs = time.monotonic() - t0
    (root / "flow.log").write_text(out, encoding="utf-8")
    steps: dict[str, str] = {}
    for line in out.splitlines():
        name, sep, rest = line.partition(": ")
        if sep and name.isalpha():
            steps[name] = rest.strip()
    res: dict[str, object] = {"name": d["name"], "top": d["top"], "clock": d["clock"],
                              "exit": code, "seconds": round(secs, 1), "steps": steps}
    if redo:
        (root / "flow.log").write_text(out, encoding="utf-8")
    status.write_text(json.dumps(res, sort_keys=True), encoding="utf-8")
    return res


def main(argv: list[str]) -> int:
    rows = env.designs()
    if argv == ["--list"]:
        for r in rows:
            print(r["name"], r["bytes"], r["clock"] or "-")
        return 0
    redo = "--redo" in argv
    argv = [a for a in argv if a != "--redo"]
    rows = [r for r in rows if not argv or any(a in r["name"] for a in argv)]
    for d in rows:
        res = run_one(d, redo)
        steps = res["steps"]
        assert isinstance(steps, dict)
        last = list(steps.items())[-1] if steps else ("", "")
        print(f"{d['name']:<32} exit {res['exit']} {res['seconds']:>7}s  last {last[0]}: "
              f"{str(last[1])[:80]}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
