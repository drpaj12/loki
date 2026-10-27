"""Build the prompts for arms A, B, C and the call manifest ``run/calls.jsonl``.

Usage: ``python -I build_prompts.py``. Run ``make_hints.py`` first (arm B needs ``run/hints``).
Prompt assembly mirrors ``scripts/sv-generate`` (task netlist-to-rtl, 2-shot, no rules, no
explain); see EXPERIMENT.md. ``LLM_PILOT_VARIANT=re`` builds variant ``re`` (decision 14) into
``run-re/``. Writes ``run/prompts/<arm>/<problem>/{system.txt,user.txt}``,
``run/calls.jsonl`` and ``prompt_sizes.csv`` (``prompt_sizes_re.csv`` for variant ``re``). The
leak gate runs on the system message and on every user message.
"""

from __future__ import annotations

import csv
import hashlib
import importlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
common = importlib.import_module("common")

BYTES_PER_TOKEN = 3.2
NETLIST_HEAD = "Gate-level netlist:"
PIN_PROBLEM = "Prob024_hadd"
PIN_LEN = 4154
PIN_MD5 = "3cf721c28b377e4bfe1719d424ec4c01"
PREFIX_MD5 = "e5c9110aadcb958b52750e40a8acb9b5"  # standard 2-shot prefix, 3030 bytes
OLD_COT_PIN = ("ebc2f2899a6e55a4d8689c1ae3fac87e", 7986)  # superseded pin, variant cot


LEAK = re.compile(r"\$n\d|\bc\d+\b|loki_|Prob\d|\bL0\b|provenance|key\.json|level0",
                  re.I)


def leak_hits(text: str) -> list[str]:
    """Loki-internal names and L0/provenance strings that must not reach a prompt."""
    return sorted({m.group(0) for m in LEAK.finditer(text)})


def question_text(prompt: str, arm: str, hints: str = "") -> str:
    """The Question body for an arm (``prompt`` is the dataset prompt file text)."""
    body = prompt.strip()
    if arm == "B":
        return body + "\n\n" + hints.strip("\n")
    if arm == "C":
        cut = body.find(NETLIST_HEAD)
        if cut < 0:
            raise ValueError("no netlist section in prompt")
        return body[:cut].rstrip("\n") + "\n\n" + common.C_NOTE
    return body


def user_message(prefix: str, prompt: str, arm: str, hints: str = "") -> str:
    full = prefix + "\nQuestion:\n" + question_text(prompt, arm, hints) + "\n"
    full = full.rstrip() + "\n" + common.SUFFIX
    return full + "\nAnswer:\n"


def read_selection() -> list[dict[str, str]]:
    with (common.HERE / "selection.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def call_order(rows: list[dict[str, str]]) -> list[tuple[dict[str, str], str]]:
    """(row, arm) in call order: problems by netlist size; the A/B order by hash parity; C last."""
    ordered = sorted(rows, key=lambda r: (int(r["netlist_lines"]), r["problem"]))
    out: list[tuple[dict[str, str], str]] = []
    for r in ordered:
        pair = ("A", "B") if common.a_first(r["problem"]) else ("B", "A")
        out += [(r, pair[0]), (r, pair[1]), (r, "C")]
    return out


def sizes_file() -> Path:
    """Tracked size/hash table of the selected variant (the `standard` file is never overwritten
    by a `re` build)."""
    suffix = "" if common.VARIANT == "standard" else f"_{common.VARIANT}"
    return common.HERE / f"prompt_sizes{suffix}.csv"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def check_prefix(prefix: str) -> str:
    md5 = hashlib.md5(prefix.encode("utf-8"), usedforsecurity=False).hexdigest()
    if md5 != PREFIX_MD5:
        raise SystemExit(f"prefix md5 mismatch: {md5}")
    return md5


def check_pin(prefix: str) -> str:
    prompt = (common.dataset_dir() / f"{PIN_PROBLEM}_prompt.txt").read_text(encoding="utf-8")
    msg = user_message(prefix, prompt, "A")
    md5 = hashlib.md5(msg.encode("utf-8"), usedforsecurity=False).hexdigest()
    if len(msg) != PIN_LEN or md5 != PIN_MD5:
        raise SystemExit(f"regression pin failed: {len(msg)} chars, md5 {md5}")
    return md5


def main() -> int:
    prefix = common.prefix_file().read_text(encoding="utf-8")
    check_prefix(prefix)
    check_pin(prefix)
    root = common.run_dir()
    system = common.system_msg()
    bad_sys = leak_hits(system)
    if bad_sys:
        raise SystemExit(f"leak gate: system message: {bad_sys}")
    if common.VARIANT == "re":
        md5 = hashlib.md5(system.encode("utf-8"), usedforsecurity=False).hexdigest()
        if md5 != common.RE_SYSTEM_MD5:
            raise SystemExit(f"re system prompt md5 mismatch: {md5}")
    calls = []
    sizes = []
    for order, (r, arm) in enumerate(call_order(read_selection()), start=1):
        p = r["problem"]
        prompt = (common.dataset_dir() / f"{p}_prompt.txt").read_text(encoding="utf-8")
        hints = ""
        if arm == "B":
            hints = (common.hints_root() / "hints" / p / "hints.md").read_text(encoding="utf-8")
        user = user_message(prefix, prompt, arm, hints)
        bad = leak_hits(user)
        if bad:
            raise SystemExit(f"leak gate: {arm} {p}: {bad}")
        base = Path("prompts") / arm / p
        write(root / base / "system.txt", system)
        write(root / base / "user.txt", user)
        nbytes = len(user.encode("utf-8"))
        calls.append({
            "order": order, "problem": p, "quartile": r["quartile"], "arm": arm,
            "system_file": str(base / "system.txt"), "user_file": str(base / "user.txt"),
            "system_sha256": common.sha256_text(system),
            "user_sha256": common.sha256_text(user), "user_bytes": nbytes,
            "est_tokens": round(nbytes / BYTES_PER_TOKEN)})
        sizes.append((arm, p, nbytes))
    write(root / "calls.jsonl", "".join(json.dumps(c, sort_keys=True) + "\n" for c in calls))
    with sizes_file().open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["order", "problem", "quartile", "arm", "user_bytes", "est_tokens",
                    "user_sha256"])
        for c in calls:
            w.writerow([c[k] for k in ("order", "problem", "quartile", "arm", "user_bytes",
                                       "est_tokens", "user_sha256")])
    print(f"{len(calls)} calls; pin ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
