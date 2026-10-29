"""Build prompts, call files, ``calls.jsonl`` and ``batches.json`` of the full run (no model call).

Usage: ``python -I build_full.py``. Needs ``run/hints`` (``make_hints_full.py``). Reuses the
pilot's ``build_prompts`` (user_message, leak_hits, prefix and pin checks, byte-exact ``re`` system
message).
Writes under ``run/``: ``prompts/<arm>/<problem>/{system,user}.txt`` (one per problem and arm,
shared by the 3 draws), ``calls/call-NNNN.txt`` (one per call: system message, then user message),
``calls.jsonl`` (1 row per call), and ``batches.json``, ``prompt_sizes_full.csv`` beside this file.

Call order: draw-major (draw 1 for every problem, then draw 2, then draw 3); inside a draw by the
arm A user-message size ascending (ties by name); per problem the arms in the pilot's A/B parity
order, C last. A batch is 24 consecutive calls (8 problems x 3 arms), never spanning two draws.
"""

from __future__ import annotations

import csv
import hashlib
import importlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
fullcfg: Any = importlib.import_module("fullcfg")
common = fullcfg.common
bp: Any = importlib.import_module("build_prompts")

BATCH = 24
PILOT_RAW = fullcfg.PILOT / "results" / "re" / "raw"
PILOT_SIZES = fullcfg.PILOT / "prompt_sizes_re.csv"
DELIM_SYS = "===== SYSTEM MESSAGE =====\n"
DELIM_USER = "\n===== USER MESSAGE =====\n"


def pilot_reply_tokens() -> dict[str, float]:
    """Mean pilot reply size per arm in tokens (reply bytes / 3.2), from the tracked raw replies.

    ``results/re/raw/resp-NNN.txt`` is the reply of call NNN (the pilot call order of
    ``prompt_sizes_re.csv``); calls with no file (no_file) are skipped.
    """
    arm_of: dict[int, str] = {}
    with PILOT_SIZES.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            arm_of[int(r["order"])] = r["arm"]
    sums: dict[str, list[int]] = {"A": [], "B": [], "C": []}
    for f in sorted(PILOT_RAW.glob("resp-*.txt")):
        sums[arm_of[int(f.stem.split("-")[1])]].append(f.stat().st_size)
    return {a: sum(v) / len(v) / bp.BYTES_PER_TOKEN for a, v in sums.items()}


def call_file_text(system: str, user: str) -> str:
    return DELIM_SYS + system + DELIM_USER + user


def build_texts(prefix: str, rows: list[dict[str, str]]) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for r in rows:
        p = r["problem"]
        prompt = (common.dataset_dir() / f"{p}_prompt.txt").read_text(encoding="utf-8")
        hints = (fullcfg.RUN / "hints" / p / "hints.md").read_text(encoding="utf-8")
        for arm in common.ARMS:
            user = bp.user_message(prefix, prompt, arm, hints if arm == "B" else "")
            bad = bp.leak_hits(user)
            if bad:
                raise SystemExit(f"leak gate: {arm} {p}: {bad}")
            out[(arm, p)] = user
    return out


def order_calls(rows: list[dict[str, str]],
                users: dict[tuple[str, str], str]) -> list[dict[str, Any]]:
    probs = sorted(rows, key=lambda r: (len(users[("A", r["problem"])].encode()), r["problem"]))
    seq: list[dict[str, Any]] = []
    for draw in fullcfg.DRAWS:
        for r in probs:
            pair = ("A", "B") if common.a_first(r["problem"]) else ("B", "A")
            for arm in (*pair, "C"):
                seq.append({"problem": r["problem"], "quartile": r["quartile"], "arm": arm,
                            "draw": draw})
    return seq


def main() -> int:
    prefix = common.prefix_file().read_text(encoding="utf-8")
    bp.check_prefix(prefix)
    bp.check_pin(prefix)
    system = common.system_msg()
    if hashlib.md5(system.encode(), usedforsecurity=False).hexdigest() != common.RE_SYSTEM_MD5:
        raise SystemExit("re system prompt md5 mismatch")
    bad_sys = bp.leak_hits(system)
    if bad_sys:
        raise SystemExit(f"leak gate: system message: {bad_sys}")
    with (common.HERE / "selection.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    users = build_texts(prefix, rows)
    run = fullcfg.RUN
    for (arm, p), user in sorted(users.items()):
        base = run / "prompts" / arm / p
        bp.write(base / "system.txt", system)
        bp.write(base / "user.txt", user)
    reply_tok = pilot_reply_tokens()
    seq = order_calls(rows, users)
    calls: list[dict[str, Any]] = []
    for n, c in enumerate(seq, start=1):
        arm, p, d = c["arm"], c["problem"], c["draw"]
        user = users[(arm, p)]
        text = call_file_text(system, user)
        if bp.leak_hits(text):
            raise SystemExit(f"leak gate: call file {n}: {bp.leak_hits(text)}")
        nbytes = len(user.encode("utf-8"))
        base = Path("prompts") / arm / p
        calls.append({
            "call": n, "problem": p, "quartile": c["quartile"], "arm": arm, "draw": d,
            "system_file": str(base / "system.txt"), "user_file": str(base / "user.txt"),
            "system_sha256": common.sha256_text(system), "user_sha256": common.sha256_text(user),
            "user_bytes": nbytes, "est_tokens_in": round(nbytes / bp.BYTES_PER_TOKEN),
            "est_tokens_out": round(reply_tok[arm]),
            "call_file": f"calls/call-{n:04d}.txt", "call_sha256": common.sha256_text(text),
            "outbox_file": f"outbox/resp-{n:04d}.txt",
            "reply_path": f"responses/{arm}/{d}/{p}.txt"})
        bp.write(run / "calls" / f"call-{n:04d}.txt", text)
    bp.write(run / "calls.jsonl", "".join(json.dumps(c, sort_keys=True) + "\n" for c in calls))
    batches = make_batches(calls)
    (fullcfg.FULL / "batches.json").write_text(
        json.dumps({"schema": 1, "batch_size": BATCH, "run_dir": "experiments/llm-full/run",
                    "batches": batches}, sort_keys=True, indent=1) + "\n", encoding="utf-8",
        newline="\n")
    write_sizes(calls)
    tot_in = sum(c["est_tokens_in"] for c in calls)
    tot_out = sum(c["est_tokens_out"] for c in calls)
    print(f"{len(rows)} problems, {len(calls)} calls, {len(batches)} batches; est tokens "
          f"in {tot_in}, out {tot_out}, sum {tot_in + tot_out} (excludes harness overhead)")
    return 0


def make_batches(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for d in fullcfg.DRAWS:
        sub = [c for c in calls if c["draw"] == d]
        for i in range(0, len(sub), BATCH):
            chunk = sub[i:i + BATCH]
            out.append({
                "batch": len(out) + 1, "draw": d, "n_calls": len(chunk),
                "est_tokens_in": sum(c["est_tokens_in"] for c in chunk),
                "est_tokens_out": sum(c["est_tokens_out"] for c in chunk),
                "calls": [{"call": c["call"], "call_file": c["call_file"],
                           "outbox_file": c["outbox_file"]} for c in chunk]})
    return out


def write_sizes(calls: list[dict[str, Any]]) -> None:
    cols = ["call", "problem", "quartile", "arm", "draw", "user_bytes", "est_tokens_in",
            "user_sha256"]
    with (fullcfg.FULL / "prompt_sizes_full.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(cols)
        w.writerows([c[k] for k in cols] for c in calls)


if __name__ == "__main__":
    sys.exit(main())
