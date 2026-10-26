"""Turn the controller's response files into per-call records.

Usage: ``python -I collect.py --calls run/calls.jsonl --responses DIR --out DIR [--require-all]``.
``DIR/<arm>/<problem>.txt`` holds the raw reply; ``<problem>.meta.json`` (optional) holds the model
id and token counts. Per call it writes ``<out>/<arm>/<problem>/{system.txt,user.txt,response.txt,
sample.sv,fallback.sv,extract.json,meta.json}`` and ``<out>/steps.csv``. Extraction mirrors
``sv-generate`` (netlist-to-rtl): lines between ``[BEGIN]`` and ``[DONE]``; a reply without them is
``no-output`` and its fenced block, if any, is kept as ``fallback.sv`` for information only.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
common = importlib.import_module("common")

_STEP = re.compile(r"//\s*Step\s*([1-4])\b", re.I)


def extract_rtl(response: str) -> tuple[str, bool]:
    """(code, found): the lines between [BEGIN] and [DONE] as sv-generate keeps them."""
    lines: list[str] = []
    start = end = False
    for line in response.splitlines():
        if not start:
            if line.strip() == "[BEGIN]":
                start = True
            elif line.lstrip().startswith("[BEGIN]"):
                lines.append(line.lstrip().replace("[BEGIN]", ""))
                start = True
        elif not end:
            if line.strip() == "[DONE]":
                end = True
            elif line.rstrip().endswith("[DONE]"):
                lines.append(line.rstrip().replace("[DONE]", ""))
                end = True
            else:
                lines.append(line)
    if not (start and end):
        return "", False
    kept = []
    for i, line in enumerate(lines):
        if (i == 0 and line.strip() == "```verilog") or line.strip() == "```":
            continue
        kept.append(line)
    return "\n".join(kept) + "\n", True


def fallback_rtl(response: str) -> str:
    """The first fenced block of a reply, or the empty string."""
    inside = False
    lines: list[str] = []
    for line in response.splitlines():
        if line.startswith("```"):
            if inside:
                return "\n".join(lines) + "\n"
            inside = True
        elif inside:
            lines.append(line)
    return ""


def steps_present(response: str) -> dict[int, bool]:
    found = {int(m) for m in _STEP.findall(response)}
    return {n: n in found for n in (1, 2, 3, 4)}


def load_calls(path: Path) -> list[dict[str, Any]]:
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def collect_one(call: dict[str, Any], base: Path, response: str, meta: str,
                out: Path) -> dict[str, Any]:
    """Write one record; the prompt files must still match the manifest hashes."""
    system = (base / call["system_file"]).read_text(encoding="utf-8")
    user = (base / call["user_file"]).read_text(encoding="utf-8")
    if common.sha256_text(system) != call["system_sha256"] \
            or common.sha256_text(user) != call["user_sha256"]:
        raise ValueError(f"{call['arm']}/{call['problem']}: prompt file changed since the manifest")
    code, found = extract_rtl(response)
    steps = steps_present(response)
    rec = out / call["arm"] / call["problem"]
    write(rec / "system.txt", system)
    write(rec / "user.txt", user)
    write(rec / "response.txt", response)
    write(rec / "sample.sv", code)
    fb = "" if found else fallback_rtl(response)
    write(rec / "fallback.sv", fb)
    info = {"arm": call["arm"], "problem": call["problem"], "found_begin_done": found,
            "code_lines": code.count("\n"), "fallback_lines": fb.count("\n"),
            "steps": {str(k): v for k, v in steps.items()}, "response_chars": len(response)}
    write(rec / "extract.json", json.dumps(info, sort_keys=True, indent=1) + "\n")
    write(rec / "meta.json", meta or "{}\n")
    return info


def collect(calls_path: Path, responses: Path, out: Path,
            require_all: bool = False) -> dict[str, Any]:
    calls = load_calls(calls_path)
    base = calls_path.parent
    expected = {(c["arm"], c["problem"]) for c in calls}
    present = {(p.parent.name, p.stem) for p in responses.glob("*/*.txt")}
    extra = sorted(present - expected)
    if extra:
        raise ValueError(f"responses with no call: {extra[:5]}")
    done, missing, empty = [], [], []
    for call in calls:
        key = (call["arm"], call["problem"])
        if key not in present:
            missing.append(key)
            continue
        text = (responses / key[0] / f"{key[1]}.txt").read_text(encoding="utf-8")
        if not text.strip():
            empty.append(key)
        meta_path = responses / key[0] / f"{key[1]}.meta.json"
        meta = meta_path.read_text(encoding="utf-8") if meta_path.exists() else ""
        done.append(collect_one(call, base, text, meta, out))
    if require_all and missing:
        raise ValueError(f"{len(missing)} responses missing, first {missing[:3]}")
    with (out / "steps.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["arm", "problem", "begin_done", "step1", "step2", "step3", "step4"])
        for d in done:
            w.writerow([d["arm"], d["problem"], int(d["found_begin_done"]),
                        *(int(d["steps"][str(n)]) for n in (1, 2, 3, 4))])
    return {"collected": len(done), "missing": len(missing), "empty": len(empty)}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--calls", type=Path, required=True)
    ap.add_argument("--responses", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--require-all", action="store_true")
    a = ap.parse_args(argv)
    print(json.dumps(collect(a.calls, a.responses, a.out, a.require_all), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
