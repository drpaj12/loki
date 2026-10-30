"""Build prompts, call files, ``calls.jsonl`` and ``batches.json`` of the hints-v2 run (no model).

Usage: ``python -I build_hints2.py``. Needs ``run/hints2`` (``make_hints_v2.py --table
calib/intent-f3.json``) and the tracked ``hints_v1/``. Arms (64 problems x 3 draws = 768 calls):
A2 (netlist, new prompt), B1p (hints v1, new prompt), B2 (hints v2, claims linked as comments in
the netlist), W (hints v2 moved to wrong wires). Checks: the system message is the llm-full
``re`` message (md5), the v1 hint blocks rebuild the llm-full arm B user messages (sha256 of the
user message built the llm-full way), the leak gate (0 hits) on the system message, every user
message and every call file. Writes under ``run/``: ``prompts/<arm>/<problem>/{system,user}.txt``,
``calls/call-NNNN.txt``, ``calls.jsonl``; beside this file: ``batches.json``,
``prompt_sizes_hints2.csv``, ``claim_kinds.json``.

Call order: draw-major; inside a draw by the A2 user-message size ascending; per problem the four
arms rotated by the parity of the problem hash. A batch is 6 problems x 4 arms = 24 calls, never
spanning two draws.
"""

from __future__ import annotations

import csv
import hashlib
import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
hintscfg: Any = importlib.import_module("hintscfg")
promptv2: Any = importlib.import_module("promptv2")
bp: Any = importlib.import_module("build_prompts")
common = hintscfg.common

ARMS = ("A2", "B1p", "B2", "W")
HINT_ARMS = ("B1p", "B2", "W")
BATCH = 24
DELIM_SYS = "===== SYSTEM MESSAGE =====\n"
DELIM_USER = "\n===== USER MESSAGE =====\n"
V1_DIR = HERE / "hints_v1"
FULL_SIZES = hintscfg.FULL / "prompt_sizes_full.csv"
PILOT_REPLY_ARM = {"A2": "A", "B1p": "B", "B2": "B", "W": "B"}


KEYWORDS = frozenset([
    "module", "endmodule", "input", "output", "inout", "wire", "reg", "logic", "integer",
    "parameter", "localparam", "assign", "always", "always_ff", "always_comb",
    "always_latch", "initial", "begin", "end", "if", "else", "case", "casex", "casez",
    "endcase", "default", "for", "while", "posedge", "negedge", "or", "and", "not", "xor",
    "nand", "nor", "xnor", "function", "endfunction", "task", "endtask", "signed",
    "unsigned", "genvar", "generate", "endgenerate", "typedef", "enum", "struct", "int",
    "bit", "byte"
])
WORD = re.compile(r"[A-Za-z_]\w*")


def template_words() -> set[str]:
    """Words of the fixed English templates (hint renderer and prompt pieces): a reference name that
    is also an ordinary word of our own text ("bits") is not a leak."""
    root = HERE.parents[1]
    return set(WORD.findall((root / "loki" / "intent" / "text.py").read_text(encoding="utf-8"))) | \
        set(WORD.findall((HERE / "promptv2.py").read_text(encoding="utf-8"))) | \
        set(WORD.findall(common.system_msg()))


def ref_names(problem: str) -> set[str]:
    """Identifiers of the reference RTL that are not ports, keywords or already present in the
    original netlist or the dataset prompt (what the model is allowed to see): reaching a prompt,
    they would be a leak from the reference. Names shorter than 3 characters are not checked."""
    d = common.dataset_dir()
    ref = (d / f"{problem}_ref.sv").read_text(encoding="utf-8")
    ref = re.sub(r"//[^\n]*|/\*.*?\*/", " ", ref, flags=re.S)
    ref = re.sub(r"\d*'[sS]?[bBoOdDhH][0-9a-fA-F_xXzZ]+", " ", ref)
    head = ref.split(");", 1)[0]
    seen = set(WORD.findall((d / f"{problem}_netlist.v").read_text(encoding="utf-8"))) | set(
        WORD.findall((d / f"{problem}_prompt.txt").read_text(encoding="utf-8")))
    ids = set(WORD.findall(ref)) - set(WORD.findall(head)) - KEYWORDS - seen - template_words()
    return {i for i in ids if len(i) >= 3}


def ref_hits(problem: str, text: str) -> list[str]:
    return sorted(ref_names(problem) & set(WORD.findall(text)))


def call_file_text(system: str, user: str) -> str:
    return DELIM_SYS + system + DELIM_USER + user


def v1_block(problem: str) -> str:
    return (V1_DIR / f"{problem}.md").read_text(encoding="utf-8")


def v2_block(problem: str, wrong: bool) -> str:
    name = "hints_w.md" if wrong else "hints.md"
    doc = (hintscfg.RUN / "hints2" / problem / name).read_text(encoding="utf-8")
    return str(promptv2.HINTS_PREFACE + doc.strip("\n") + "\n" + common.HINTS_POSTFACE)


def with_netlist(prompt: str, problem: str, linked: str) -> str:
    """The dataset prompt with the netlist text replaced by the linked netlist."""
    base = (common.dataset_dir() / f"{problem}_netlist.v").read_text(encoding="utf-8")
    if prompt.count(base) != 1:
        raise SystemExit(f"{problem}: the netlist is not exactly once in the prompt")
    return prompt.replace(base, linked)


def user_message(prefix: str, prompt: str, hints: str, hint_arm: bool) -> str:
    question = prompt.strip()
    if hints:
        question += "\n\n" + hints.strip("\n")
    full = prefix + "\nQuestion:\n" + question + "\n"
    full = full.rstrip() + "\n" + str(promptv2.suffix(hint_arm))
    return full + "\nAnswer:\n"


def hint_part(arm: str, problem: str) -> str:
    if arm == "B1p":
        return str(promptv2.EXPLAIN_V1) + "\n\n" + v1_block(problem)
    wrong = arm == "W"
    return str(promptv2.EXPLAIN_V2) + "\n\n" + v2_block(problem, wrong)


def build_one(prefix: str, problem: str, arm: str) -> str:
    prompt = (common.dataset_dir() / f"{problem}_prompt.txt").read_text(encoding="utf-8")
    if arm in ("B2", "W"):
        name = "netlist_w.v" if arm == "W" else "netlist_linked.v"
        linked = (hintscfg.RUN / "hints2" / problem / name).read_text(encoding="utf-8")
        prompt = with_netlist(prompt, problem, linked)
    hints = hint_part(arm, problem) if arm in HINT_ARMS else ""
    return user_message(prefix, prompt, hints, arm in HINT_ARMS)


def v1_fidelity(prefix: str, rows: list[dict[str, str]]) -> int:
    """Number of problems whose frozen v1 block rebuilds the llm-full arm B user message."""
    with FULL_SIZES.open(encoding="utf-8", newline="") as fh:
        want = {r["problem"]: r["user_sha256"] for r in csv.DictReader(fh) if r["arm"] == "B"}
    ok = 0
    for r in rows:
        p = r["problem"]
        prompt = (common.dataset_dir() / f"{p}_prompt.txt").read_text(encoding="utf-8")
        user = bp.user_message(prefix, prompt, "B", v1_block(p))
        ok += common.sha256_text(user) == want[p]
    return ok


def reply_tokens() -> dict[str, float]:
    """Mean pilot reply size per arm in tokens (reply bytes / 3.2), from the tracked pilot replies
    (the llm-full estimate; ``build_full.py`` is not imported because it re-points the pilot
    modules at its own directory)."""
    arm_of: dict[int, str] = {}
    with (hintscfg.PILOT / "prompt_sizes_re.csv").open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            arm_of[int(r["order"])] = r["arm"]
    sums: dict[str, list[int]] = {"A": [], "B": [], "C": []}
    for f in sorted((hintscfg.PILOT / "results" / "re" / "raw").glob("resp-*.txt")):
        sums[arm_of[int(f.stem.split("-")[1])]].append(f.stat().st_size)
    return {a: sum(v) / len(v) / bp.BYTES_PER_TOKEN for a, v in sums.items()}


def order_calls(rows: list[dict[str, str]], users: dict[tuple[str, str], str]
                ) -> list[dict[str, Any]]:
    probs = sorted(rows, key=lambda r: (len(users[("A2", r["problem"])].encode()), r["problem"]))
    seq: list[dict[str, Any]] = []
    for draw in hintscfg.DRAWS:
        for r in probs:
            k = int(common.rank_key(r["problem"])[-1], 16) % len(ARMS)
            for arm in (*ARMS[k:], *ARMS[:k]):
                seq.append({"problem": r["problem"], "quartile": r["quartile"], "arm": arm,
                            "draw": draw})
    return seq


def make_batches(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for d in hintscfg.DRAWS:
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


def claim_kinds(problems: list[str]) -> dict[str, dict[str, dict[str, str]]]:
    """Claim id to kind per arm and problem, for the per-kind analysis."""
    out: dict[str, dict[str, dict[str, str]]] = {a: {} for a in HINT_ARMS}
    for p in problems:
        v1 = json.loads((hintscfg.RUN / "hints" / p / "out" / "reverse-provenance.json")
                        .read_text(encoding="utf-8"))
        out["B1p"][p] = {e["id"]: e["kind"] for e in v1["elements"]}
        used = set(re.findall(r"\bh\d+\b", v1_block(p)))
        if not used <= set(out["B1p"][p]):
            raise SystemExit(f"{p}: ids {sorted(used - set(out['B1p'][p]))} of hints_v1 have no "
                             "kind in reverse-provenance.json")
        v2 = json.loads((hintscfg.RUN / "hints2" / p / "intent.json").read_text(encoding="utf-8"))
        kinds = {c["id"]: c["kind"] for c in v2["claims"]}
        out["B2"][p], out["W"][p] = kinds, dict(kinds)
    return out


def write_sizes(calls: list[dict[str, Any]]) -> None:
    cols = ["call", "problem", "quartile", "arm", "draw", "user_bytes", "est_tokens_in",
            "user_sha256"]
    with (HERE / "prompt_sizes_hints2.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(cols)
        w.writerows([c[k] for k in cols] for c in calls)


def main() -> int:
    prefix = common.prefix_file().read_text(encoding="utf-8")
    bp.check_prefix(prefix)
    bp.check_pin(prefix)
    system = common.system_msg()
    if hashlib.md5(system.encode(), usedforsecurity=False).hexdigest() != common.RE_SYSTEM_MD5:
        raise SystemExit("re system prompt md5 mismatch")
    if bp.leak_hits(system):
        raise SystemExit(f"leak gate: system message: {bp.leak_hits(system)}")
    with (HERE / "selection.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    fidelity = v1_fidelity(prefix, rows)
    if fidelity != len(rows):
        raise SystemExit(f"v1 fidelity: {fidelity} of {len(rows)} blocks rebuild llm-full arm B")
    users: dict[tuple[str, str], str] = {}
    for r in rows:
        for arm in ARMS:
            user = build_one(prefix, r["problem"], arm)
            if bp.leak_hits(user):
                raise SystemExit(f"leak gate: {arm} {r['problem']}: {bp.leak_hits(user)}")
            if ref_hits(r["problem"], user):
                raise SystemExit(f"ref-name gate: {arm} {r['problem']}: "
                                 f"{ref_hits(r['problem'], user)}")
            users[(arm, r["problem"])] = user
    run = hintscfg.RUN
    for (arm, p), user in sorted(users.items()):
        base = run / "prompts" / arm / p
        bp.write(base / "system.txt", system)
        bp.write(base / "user.txt", user)
    reply_tok = reply_tokens()
    calls: list[dict[str, Any]] = []
    for n, c in enumerate(order_calls(rows, users), start=1):
        arm, p, d = c["arm"], c["problem"], c["draw"]
        user = users[(arm, p)]
        text = call_file_text(system, user)
        if bp.leak_hits(text):
            raise SystemExit(f"leak gate: call file {n}: {bp.leak_hits(text)}")
        if ref_hits(p, text):
            raise SystemExit(f"ref-name gate: call file {n}: {ref_hits(p, text)}")
        nbytes = len(user.encode("utf-8"))
        base = Path("prompts") / arm / p
        calls.append({
            "call": n, "problem": p, "quartile": c["quartile"], "arm": arm, "draw": d,
            "system_file": str(base / "system.txt"), "user_file": str(base / "user.txt"),
            "system_sha256": common.sha256_text(system), "user_sha256": common.sha256_text(user),
            "user_bytes": nbytes, "est_tokens_in": round(nbytes / bp.BYTES_PER_TOKEN),
            "est_tokens_out": round(reply_tok[PILOT_REPLY_ARM[arm]]),
            "call_file": f"calls/call-{n:04d}.txt", "call_sha256": common.sha256_text(text),
            "outbox_file": f"outbox/resp-{n:04d}.txt",
            "reply_path": f"responses/{arm}/{d}/{p}.txt"})
        bp.write(run / "calls" / f"call-{n:04d}.txt", text)
    bp.write(run / "calls.jsonl", "".join(json.dumps(c, sort_keys=True) + "\n" for c in calls))
    batches = make_batches(calls)
    (HERE / "batches.json").write_text(
        json.dumps({"schema": 1, "batch_size": BATCH, "run_dir": "experiments/llm-hints2/run",
                    "batches": batches}, sort_keys=True, indent=1) + "\n", encoding="utf-8",
        newline="\n")
    (HERE / "claim_kinds.json").write_text(
        json.dumps(claim_kinds([r["problem"] for r in rows]), sort_keys=True, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    write_sizes(calls)
    sizes = [c["user_bytes"] for c in calls]
    tin = sum(c["est_tokens_in"] for c in calls)
    tout = sum(c["est_tokens_out"] for c in calls)
    print(f"ref-name gate: 0 hits ({sum(len(ref_names(r['problem'])) for r in rows)} names over "
          f"{len(rows)} problems, {len(calls)} call files)")
    print(f"{len(rows)} problems, {len(calls)} calls, {len(batches)} batches; v1 fidelity "
          f"{fidelity}/{len(rows)}; max user message {max(sizes)} bytes; est tokens in {tin}, "
          f"out {tout}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
