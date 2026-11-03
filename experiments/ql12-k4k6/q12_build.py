"""Build the blocks, prompts, calls and batches of Q-L12 (no model call).

Usage: ``python -B q12_build.py blocks [JOBS]`` (Loki blocks of every design at k4 and k6, cached
under ``$QL12_OUT/blocks/<endpoint>``), then ``python -B q12_build.py calls`` (prompts,
``calls.jsonl``, ``batches.json``, ``batches-D.json``, tables). Leak gate: no prompt may hold a
Loki-internal name (``build_prompts.leak_hits``).
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import q12_blocks as qb
import q12_env as env
import q12_nl as nlm
import q12_render as rn

q10_pop: Any = env.mod("q10_pop")
common: Any = env.mod("common")
bp: Any = env.mod("build_prompts")
Q10_RESULTS = env.EXP / "ql10-blocks" / "results" / "results.csv"
Q10_DESIGNS = env.EXP / "ql10-blocks" / "designs.json"
ARMS = ("D", "A")
GROUPS = (("core", ("vq", "vbig"), env.DRAWS), ("ext", ("ext",), (1,)))
BYTES_PER_TOKEN = bp.BYTES_PER_TOKEN
DELIM_SYS = "===== SYSTEM MESSAGE =====\n"
DELIM_USER = "\n===== USER MESSAGE =====\n"


def problems() -> list[dict[str, str]]:
    """The Q-L10 set: the designs with a D row that was run (43 vq, 4 vbig, 5 ext), in Q-L10
    design order."""
    with Q10_RESULTS.open(encoding="utf-8", newline="") as fh:
        ran = {r["problem"] for r in csv.DictReader(fh)
               if r["arm"] == "D" and r["outcome"] != "not_run"}
    designs = json.loads(Q10_DESIGNS.read_text(encoding="utf-8"))
    return [{"problem": d["problem"], "tier": d["tier"], "quartile": d["quartile"]}
            for d in designs if d["problem"] in ran]


def ceiling_zero() -> set[tuple[str, str]]:
    """(problem, endpoint) whose faithful decode does not pass the testbench (``q12_stubcheck``):
    the netlist is not the function of the reference, no reply can pass; left out of the calls."""
    path = env.RES / "stubcheck.csv"
    if not path.is_file():
        return set()
    with path.open(encoding="utf-8", newline="") as fh:
        return {(r["problem"], r["endpoint"]) for r in csv.DictReader(fh)
                if r["outcome"] != "pass"}


def blocks_file(endpoint: str, problem: str) -> Path:
    return env.RUN / "blocks" / endpoint / f"{problem}.json"


def available(endpoint: str, problem: str) -> bool:
    return nlm.blif_path(endpoint, problem).is_file() and (problem, endpoint) not in ceiling_zero()


def build_one(args: tuple[str, str]) -> tuple[str, str, int, int]:
    endpoint, problem = args
    nl = nlm.read(endpoint, problem)
    f = blocks_file(endpoint, problem)
    if f.is_file():
        return endpoint, problem, len(nl.cells), len(json.loads(f.read_text(encoding="utf-8")))
    blocks = qb.build(nl, nlm.blif_path(endpoint, problem), env.ENDPOINTS[endpoint][0])
    rec = [{"bid": b.bid, "kind": b.kind, "cells": b.cells} for b in blocks]
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(rec, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return endpoint, problem, len(nl.cells), len(blocks)


def load_blocks(endpoint: str, problem: str) -> list[Any]:
    rec = json.loads(blocks_file(endpoint, problem).read_text(encoding="utf-8"))
    return [qb.Block(r["bid"], r["kind"], r["cells"], "", []) for r in rec]


def cmd_blocks(jobs: int) -> int:
    work = [(ep, r["problem"]) for r in problems() for ep in env.ENDPOINTS
            if available(ep, r["problem"])]
    work.sort(key=lambda w: (nlm.blif_path(*w).stat().st_size, w))  # smallest first
    with ProcessPoolExecutor(min(jobs, 2)) as ex:
        for ep, p, n, nb in ex.map(build_one, work, chunksize=1):
            print(f"{ep} {p}: {n} cells, {nb} blocks", flush=True)
    return 0


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def dataset_prompt(problem: str) -> str:
    """The Gate-Breaker dataset prompt file of a problem ('' for a processor module)."""
    if nlm.is_ext(problem):
        return ""
    return (Path(common.dataset_dir()) / f"{problem}_prompt.txt").read_text(encoding="utf-8")


def a_body_bytes(nl: nlm.Netlist, prompt: str) -> int:
    """Bytes of the arm A prompt without the 2-shot prefix: the quantity the earlier runs capped
    at 40000 (their dataset prompt file)."""
    body = rn.template("a_prompt_lut.txt").replace("{INTRO}", prompt[:prompt.find(rn.GATE_WORD)])
    return len(body.replace("{NETLIST}", rn.whole_blif(nl)).encode("utf-8"))


def design_record(endpoint: str, r: dict[str, str], prefix: str) -> dict[str, Any]:
    p = r["problem"]
    nl = nlm.read(endpoint, p)
    blocks = load_blocks(endpoint, p)
    ports = rn.block_ports(nl, blocks)
    gate = q10_pop.read(p)
    items = []
    prompts: dict[str, str] = {}
    for b, pt in zip(blocks, ports, strict=True):
        u = rn.prompt_text(nl, b.bid, b.cells, pt)
        bad = bp.leak_hits(u)
        if bad:
            raise SystemExit(f"leak gate: D {endpoint} {p} block {b.bid}: {bad}")
        prompts[sha(u)] = u
        items.append({"bid": b.bid, "kind": b.kind, "n_cells": len(b.cells),
                      "n_in": len(pt.inputs), "n_out": len(pt.outputs), "sha": sha(u),
                      "bytes": len(u.encode("utf-8"))})
    a_text = ""
    dprompt = dataset_prompt(p) or _ext_prompt(gate)
    a_bytes = a_body_bytes(nl, dprompt)
    runs_a = a_bytes <= env.A_CAP_BYTES
    if runs_a:
        a_text = rn.a_prompt(nl, dprompt, prefix)
        bad = bp.leak_hits(a_text)
        if bad:
            raise SystemExit(f"leak gate: A {endpoint} {p}: {bad}")
        prompts[sha(a_text)] = a_text
    return {"problem": p, "endpoint": endpoint, "tier": r["tier"], "quartile": r["quartile"],
            "n_cells": len(nl.cells), "gate_cells": len(gate.cells), "n_blocks": len(blocks),
            "blocks": items, "a_bytes": a_bytes, "runs_a": runs_a,
            "a_sha": sha(a_text) if runs_a else "",
            "a_bytes_total": len(a_text.encode("utf-8")), "prompts": prompts}


def _ext_prompt(gate: Any) -> str:
    """The dataset prompt of a processor module (it has none): the Gate-Breaker wording with the
    module's interface line."""
    return ("\nI would like you to reverse engineer a gate-level netlist back to its original RTL "
            "description.\nThe netlist was synthesized from a Verilog RTL design.\n\n"
            "Please create an equivalent, clean, and readable RTL description that implements the "
            "same functionality.\nYour RTL should be written in standard Verilog or SystemVerilog "
            "using best practices.\n\nThe module should be named 'TopModule' with the following "
            f"interface:\n{', '.join(gate.header)}\n\n{rn.GATE_WORD}\n")


def out_tokens(gate_cells: int) -> int:
    """Estimated reply tokens of a whole-design reply: 113 + 0.36 per gate-level cell of the design
    (the least-squares fit of the 40 pilot arm A replies, reply bytes / 3.2 against gate cells)."""
    return round(113 + 0.36 * gate_cells)


def design_calls(d: dict[str, Any], sys_tok: int) -> list[dict[str, Any]]:
    """The calls of one design at one endpoint: arm A (when it runs), then every block of D."""
    out: list[dict[str, Any]] = []
    base = {"problem": d["problem"], "endpoint": d["endpoint"], "tier": d["tier"],
            "n_blocks": d["n_blocks"]}
    if d["runs_a"]:
        out.append({**base, "arm": "A", "bid": -1, "sha": d["a_sha"], "bytes": d["a_bytes_total"],
                    "cells": d["n_cells"],
                    "est_tokens_in": round(d["a_bytes_total"] / BYTES_PER_TOKEN) + sys_tok,
                    "est_tokens_out": out_tokens(d["gate_cells"])})
    total = max(1, d["n_cells"])
    for b in d["blocks"]:
        out.append({**base, "arm": "D", "bid": b["bid"], "sha": b["sha"], "bytes": b["bytes"],
                    "cells": b["n_cells"],
                    "est_tokens_in": round(b["bytes"] / BYTES_PER_TOKEN) + sys_tok,
                    "est_tokens_out": round(113 + 0.36 * d["gate_cells"] * b["n_cells"] / total)})
    return out


def order_calls(recs: list[dict[str, Any]], system: str) -> list[dict[str, Any]]:
    """One call per (design, endpoint, arm, block, draw). Group-major (core = vq and vbig with
    three draws, then ext with one), draw-major, designs by total D prompt bytes ascending (smallest
    first), inside a design arm A then the blocks of D in order."""
    sys_tok = round(len(system.encode("utf-8")) / BYTES_PER_TOKEN)
    ordered = sorted(recs, key=lambda d: (sum(b["bytes"] for b in d["blocks"]), d["endpoint"],
                                          d["problem"]))
    seq: list[dict[str, Any]] = []
    for group, tiers, draws in GROUPS:
        for draw in draws:
            for d in (x for x in ordered if x["tier"] in tiers):
                seq += [{**c, "group": group, "draw": draw} for c in design_calls(d, sys_tok)]
    return seq


def write_all(recs: list[dict[str, Any]], calls: list[dict[str, Any]], system: str) -> None:
    prompts: dict[str, str] = {}
    for d in recs:
        prompts.update(d.pop("prompts"))
    for n, c in enumerate(calls, start=1):
        text = DELIM_SYS + system + DELIM_USER + prompts[c["sha"]]
        if bp.leak_hits(text):
            raise SystemExit(f"leak gate: call file {n}")
        c.update({"call": n, "call_file": f"calls/call-{n:04d}.txt",
                  "outbox_file": f"outbox/resp-{n:04d}.txt"})
        bp.write(env.RUN / c["call_file"], text)
    bp.write(env.RUN / "calls.jsonl", "".join(json.dumps(c, sort_keys=True) + "\n" for c in calls))
    (env.HERE / "designs.json").write_text(json.dumps(recs, sort_keys=True, indent=1) + "\n",
                                           encoding="utf-8", newline="\n")
    write_tables(recs, calls)
    for name, sel in (("batches.json", calls), ("batches-D.json", [c for c in calls
                                                                    if c["arm"] == "D"])):
        (env.HERE / name).write_text(json.dumps(
            {"schema": 1, "batch_size": env.BATCH, "run_dir": "work/ql12-out",
             "batches": batches(sel)}, sort_keys=True, indent=1) + "\n",
            encoding="utf-8", newline="\n")


def batches(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for group, _tiers, draws in GROUPS:
        for d in draws:
            sub = [c for c in calls if c["draw"] == d and c["group"] == group]
            for i in range(0, len(sub), env.BATCH):
                chunk = sub[i:i + env.BATCH]
                out.append({"batch": len(out) + 1, "group": group, "draw": d,
                            "n_calls": len(chunk),
                            "est_tokens_in": sum(c["est_tokens_in"] for c in chunk),
                            "est_tokens_out": sum(c["est_tokens_out"] for c in chunk),
                            "calls": [{"call": c["call"], "call_file": c["call_file"],
                                       "outbox_file": c["outbox_file"]} for c in chunk]})
    return out


def write_tables(recs: list[dict[str, Any]], calls: list[dict[str, Any]]) -> None:
    with (env.HERE / "blocks_summary.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["problem", "endpoint", "tier", "cells", "gate_cells", "bid", "kind",
                    "block_cells", "inputs", "outputs", "bytes_D"])
        for d in recs:
            for b in d["blocks"]:
                w.writerow([d["problem"], d["endpoint"], d["tier"], d["n_cells"], d["gate_cells"],
                            b["bid"], b["kind"], b["n_cells"], b["n_in"], b["n_out"], b["bytes"]])
    with (env.HERE / "a_limit.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["problem", "endpoint", "tier", "cells", "n_blocks", "a_prompt_bytes",
                    "cap_bytes", "a_runs"])
        for d in recs:
            w.writerow([d["problem"], d["endpoint"], d["tier"], d["n_cells"], d["n_blocks"],
                        d["a_bytes"], env.A_CAP_BYTES, int(d["runs_a"])])
    with (env.HERE / "calls_table.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["call", "problem", "endpoint", "arm", "bid", "draw", "group", "bytes",
                    "est_tokens_in", "est_tokens_out", "prompt_sha256"])
        for c in calls:
            w.writerow([c["call"], c["problem"], c["endpoint"], c["arm"], c["bid"], c["draw"],
                        c["group"], c["bytes"], c["est_tokens_in"], c["est_tokens_out"], c["sha"]])
    write_counts(calls)


def write_counts(calls: list[dict[str, Any]]) -> None:
    """Call count and token estimate per endpoint, arm and group (and D on multi-block designs)."""
    rows = []
    for ep in env.ENDPOINTS:
        for label, sel in (("D", lambda c: c["arm"] == "D"),
                           ("D multi-block designs", lambda c: c["arm"] == "D"
                            and c["n_blocks"] >= 2),
                           ("D designs of at most 64 blocks", lambda c: c["arm"] == "D"
                            and c["n_blocks"] <= 64),
                           ("A", lambda c: c["arm"] == "A")):
            cs = [c for c in calls if c["endpoint"] == ep and sel(c)]
            rows.append({"endpoint": ep, "arm": label, "calls": len(cs),
                         "est_tokens_in": sum(c["est_tokens_in"] for c in cs),
                         "est_tokens_out": sum(c["est_tokens_out"] for c in cs)})
    with (env.HERE / "counts.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main_calls() -> int:
    system = common.system_msg()
    sys_leak = bp.leak_hits(system)
    if sys_leak:
        raise SystemExit(f"leak gate: system message: {sys_leak}")
    prefix = common.prefix_file().read_text(encoding="utf-8")
    bp.check_prefix(prefix)
    recs = [design_record(ep, r, prefix) for r in problems() for ep in env.ENDPOINTS
            if available(ep, r["problem"])]
    calls = order_calls(recs, system)
    write_all(recs, calls, system)
    print(len(calls), "calls", {a: sum(1 for c in calls if c["arm"] == a) for a in ARMS})
    return 0


def main(argv: list[str]) -> int:
    if argv and argv[0] == "blocks":
        return cmd_blocks(int(argv[1]) if len(argv) > 1 else 2)
    if argv and argv[0] == "calls":
        return main_calls()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
