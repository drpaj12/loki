"""Build the blocks, prompts, calls and batches of Q-L10 (no model call).

Usage: ``python -B q10_build.py blocks [JOBS]`` (Loki blocks of every design, cached under
``$QL10_OUT/blocks``), then ``python -B q10_build.py calls`` (prompts, ``calls.jsonl``,
``batches.json``, ``batches-pilot.json``, tables). Leak gate: no prompt may hold a Loki-internal
name (``build_prompts.leak_hits``).
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import q10_blocks as qb
import q10_env as env
import q10_pop as pop
import q10_render as rn

common: Any = env.mod("common")
bp: Any = env.mod("build_prompts")
BATCH = 24
PILOT_N = 10
DRAWS = (1, 2, 3)
GROUPS = (("core", ("vq", "vbig"), DRAWS), ("ext", ("ext",), (1,)))  # ext: one draw
DELIM_SYS = "===== SYSTEM MESSAGE =====\n"
DELIM_USER = "\n===== USER MESSAGE =====\n"
ARMS = ("D", "Dh")


def blocks_file(problem: str) -> Path:
    return env.RUN / "blocks" / f"{problem}.json"


def build_one(problem: str) -> tuple[str, int, int]:
    f = blocks_file(problem)
    nl = pop.read(problem)
    if f.is_file():
        return problem, len(nl.cells), len(json.loads(f.read_text(encoding="utf-8")))
    blocks = qb.build(nl, env.RUN / "work" / problem)
    rec = [{"bid": b.bid, "kind": b.kind, "cells": b.cells, "guess": b.guess,
            "post": [round(x, 6) for x in b.post]} for b in blocks]
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(rec, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return problem, len(nl.cells), len(blocks)


def load_blocks(problem: str) -> list[qb.Block]:
    rec = json.loads(blocks_file(problem).read_text(encoding="utf-8"))
    return [qb.Block(r["bid"], r["kind"], r["cells"], r["guess"], r["post"]) for r in rec]


def cmd_blocks(jobs: int) -> int:
    probs = [r["problem"] for r in pop.rows()]
    sizes = {p: pop.netlist_path(p).stat().st_size for p in probs}
    probs.sort(key=lambda p: (sizes[p], p))  # smallest first
    with ProcessPoolExecutor(min(jobs, 2)) as ex:
        for p, n, nb in ex.map(build_one, probs, chunksize=1):
            print(f"{p}: {n} cells, {nb} blocks", flush=True)
    return 0


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def pilot_set(designs: list[dict[str, Any]]) -> list[str]:
    """The pilot designs (tier vq only: arm A has draws there): every design with 2 or more
    blocks of which one has Loki structure (not residual), plus the single-block design with a
    kind guess of lowest hash rank (so the hint arm differs from D in the pilot), 10 in all."""
    vq = [d for d in designs if d["tier"] == "vq"]
    multi = [d["problem"] for d in vq if d["n_blocks"] >= 2
             and any(b["kind"] != "residual" for b in d["blocks"])]
    single = sorted((d["problem"] for d in vq if d["n_blocks"] == 1
                     and d["blocks"][0]["guess"]), key=lambda p: sha(f"{env.SEED}:{p}"))
    return sorted(multi + single[:max(0, PILOT_N - len(multi))])


def main_calls() -> int:
    prefix_sys = common.system_msg()
    sys_leak = bp.leak_hits(prefix_sys)
    if sys_leak:
        raise SystemExit(f"leak gate: system message: {sys_leak}")
    designs: list[dict[str, Any]] = []
    prompts: dict[str, str] = {}  # sha -> user message
    for r in pop.rows():
        p = r["problem"]
        nl = pop.read(p)
        blocks = load_blocks(p)
        ports = rn.block_ports(nl, blocks)
        items = []
        for b, pt in zip(blocks, ports, strict=True):
            users = {a: rn.prompt_text(nl, b, pt, a == "Dh") for a in ARMS}
            for a, u in users.items():
                bad = bp.leak_hits(u)
                if bad:
                    raise SystemExit(f"leak gate: {a} {p} block {b.bid}: {bad}")
                prompts[sha(u)] = u
            items.append({"bid": b.bid, "kind": b.kind, "n_cells": len(b.cells), "guess": b.guess,
                          "n_in": len(pt.inputs), "n_out": len(pt.outputs),
                          "sha": {a: sha(u) for a, u in users.items()},
                          "bytes": {a: len(u.encode("utf-8")) for a, u in users.items()}})
        designs.append({"problem": p, "quartile": r["quartile"], "tier": r["tier"],
                        "n_cells": len(nl.cells), "n_blocks": len(blocks), "blocks": items})
    pilot = set(pilot_set(designs))
    calls = order_calls(designs, pilot)
    write_all(designs, prompts, calls, prefix_sys, pilot)
    return 0


def order_calls(designs: list[dict[str, Any]], pilot: set[str]) -> list[dict[str, Any]]:
    """One call per unique prompt and draw. Group-major (core = vq and vbig, then ext), then
    draw-major, designs by total D prompt bytes ascending, blocks in order, D before Dh. A block
    whose D and Dh prompts are byte-equal is one call that serves both arms."""
    seq: list[dict[str, Any]] = []
    ordered = sorted(designs, key=lambda d: (sum(b["bytes"]["D"] for b in d["blocks"]),
                                             d["problem"]))
    for group, tiers, draws in GROUPS:
        for draw in draws:
            for d in (x for x in ordered if x["tier"] in tiers):
                seq += design_calls(d, draw, group, pilot)
    return seq


def design_calls(d: dict[str, Any], draw: int, group: str, pilot: set[str]
                 ) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for b in d["blocks"]:
        same = b["sha"]["D"] == b["sha"]["Dh"]
        for arms in ((("D", "Dh"),) if same else (("D",), ("Dh",))):
            out.append({"problem": d["problem"], "quartile": d["quartile"], "tier": d["tier"],
                        "group": group, "bid": b["bid"], "arms": list(arms), "draw": draw,
                        "sha": b["sha"][arms[0]], "bytes": b["bytes"][arms[0]],
                        "pilot": d["problem"] in pilot and draw == 1})
    return out


def out_tokens(n_cells: int) -> int:
    """Estimated reply tokens of a block call: 113 + 0.36 per cell, the least-squares fit of the 40
    arm A replies of the pilot (reply bytes / 3.2 against netlist cells); an extrapolation above
    the pilot's cell counts (EXPERIMENT.md)."""
    return round(113 + 0.36 * n_cells)


def write_all(designs: list[dict[str, Any]], prompts: dict[str, str], calls: list[dict[str, Any]],
              system: str, pilot: set[str]) -> None:
    run = env.RUN
    cells = {(d["problem"], b["bid"]): b["n_cells"] for d in designs for b in d["blocks"]}
    for n, c in enumerate(calls, start=1):
        text = DELIM_SYS + system + DELIM_USER + prompts[c["sha"]]
        if bp.leak_hits(text):
            raise SystemExit(f"leak gate: call file {n}")
        c.update({"call": n, "call_file": f"calls/call-{n:04d}.txt",
                  "outbox_file": f"outbox/resp-{n:04d}.txt",
                  "est_tokens_in": round(c["bytes"] / bp.BYTES_PER_TOKEN)
                  + round(len(system.encode("utf-8")) / bp.BYTES_PER_TOKEN),
                  "est_tokens_out": out_tokens(cells[(c["problem"], c["bid"])])})
        bp.write(run / c["call_file"], text)
    bp.write(run / "calls.jsonl", "".join(json.dumps(c, sort_keys=True) + "\n" for c in calls))
    (env.HERE / "designs.json").write_text(json.dumps(designs, sort_keys=True, indent=1) + "\n",
                                           encoding="utf-8", newline="\n")
    write_tables(designs, calls)
    full = batches([c for c in calls if not c["pilot"]])
    pil = batches([c for c in calls if c["pilot"]])
    for name, bs in (("batches.json", full), ("batches-pilot.json", pil)):
        (env.HERE / name).write_text(json.dumps(
            {"schema": 1, "batch_size": BATCH, "run_dir": "work/ql10-out", "batches": bs},
            sort_keys=True, indent=1) + "\n", encoding="utf-8", newline="\n")
    report(calls, full, pil, pilot)


def batches(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for group, _tiers, draws in GROUPS:
        for d in draws:
            sub = [c for c in calls if c["draw"] == d and c["group"] == group]
            for i in range(0, len(sub), BATCH):
                chunk = sub[i:i + BATCH]
                out.append({"batch": len(out) + 1, "group": group, "draw": d,
                            "n_calls": len(chunk),
                            "est_tokens_in": sum(c["est_tokens_in"] for c in chunk),
                            "est_tokens_out": sum(c["est_tokens_out"] for c in chunk),
                            "calls": [{"call": c["call"], "call_file": c["call_file"],
                                       "outbox_file": c["outbox_file"]} for c in chunk]})
    return out


def write_tables(designs: list[dict[str, Any]], calls: list[dict[str, Any]]) -> None:
    with (env.HERE / "blocks_summary.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["problem", "quartile", "tier", "bid", "kind", "cells", "guess", "inputs",
                    "outputs", "bytes_D", "bytes_Dh", "same_prompt"])
        for d in designs:
            for b in d["blocks"]:
                w.writerow([d["problem"], d["quartile"], d["tier"], b["bid"], b["kind"],
                            b["n_cells"], b["guess"], b["n_in"], b["n_out"], b["bytes"]["D"],
                            b["bytes"]["Dh"], int(b["sha"]["D"] == b["sha"]["Dh"])])
    with (env.HERE / "calls_table.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["call", "problem", "bid", "arms", "draw", "pilot", "bytes", "est_tokens_in",
                    "est_tokens_out", "prompt_sha256"])
        for c in calls:
            w.writerow([c["call"], c["problem"], c["bid"], "+".join(c["arms"]), c["draw"],
                        int(c["pilot"]), c["bytes"], c["est_tokens_in"], c["est_tokens_out"],
                        c["sha"]])


def report(calls: list[dict[str, Any]], full: list[dict[str, Any]], pil: list[dict[str, Any]],
           pilot: set[str]) -> None:
    def tot(cs: list[dict[str, Any]]) -> tuple[int, int]:
        return sum(c["est_tokens_in"] for c in cs), sum(c["est_tokens_out"] for c in cs)

    p = [c for c in calls if c["pilot"]]
    f = [c for c in calls if not c["pilot"]]
    print(f"{len(calls)} calls: pilot {len(p)} ({len(pil)} batches), full {len(f)} "
          f"({len(full)} batches); pilot designs {sorted(pilot)}")
    for name, cs in (("pilot", p), ("full", f), ("all", calls)):
        i, o = tot(cs)
        print(f"{name}: est tokens in {i}, out {o}, sum {i + o}")


def main(argv: list[str]) -> int:
    if argv and argv[0] == "blocks":
        return cmd_blocks(int(argv[1]) if len(argv) > 1 else 2)
    if argv and argv[0] == "calls":
        return main_calls()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
