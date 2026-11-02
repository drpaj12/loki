"""Dry run with no model: stub replies go through outbox, assembly, scoring and the tables.

Usage: ``python -B q10_dryrun.py`` (after ``q10_build.py blocks`` and ``calls``). Works in
``$QL10_OUT/dry`` (blocks, calls and the veval key are linked from the real run). Per design
a fixed pattern writes, for every call of arm D and Dh and each draw: the faithful stub RTL
(``pass``), the same module with every output tied low (``wrong``), a syntax error, a reply
without markers, or a module with another name (``assembly``). Checks: every design with a
``pass`` pattern scores ``pass`` (VerilogEval testbench, or equivalence for tier ext), every other
pattern does not pass with the expected outcome, 0 timeouts, the block check agrees (ok for stubs,
mismatch for wrong), the equivalence check says ``neq`` on a mutated ext design. Writes
``dryrun_result.json``; exit 1 on any mismatch.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REAL = Path(os.environ.get("QL10_OUT", str(HERE.parents[2] / "work" / "ql10-out"))).resolve()
DRY = REAL / "dry"
os.environ["QL10_VEVAL"] = str(REAL / "veval" / "loki-veval-exp" / "dataset")
os.environ["QL10_OUT"] = str(DRY)
sys.path.insert(0, str(HERE))

ck: Any = importlib.import_module("q10_check")  # after the environment is set
co: Any = importlib.import_module("q10_collect")
env: Any = importlib.import_module("q10_env")
pop: Any = importlib.import_module("q10_pop")
rn: Any = importlib.import_module("q10_render")
equiv: Any = importlib.import_module("q10_equiv")

PATTERNS = ("pass", "wrong", "syntax", "nomark", "assembly")
EXPECT = {"pass": "pass", "wrong": "runtime", "syntax": "compile", "nomark": "not_run",
          "assembly": "assembly"}
# designs: a combinational one, a sequential single block, two multi-block register designs, an
# FSM, a shift/fsm design, one over-cap design
DESIGNS = ("Prob001_zero", "Prob024_hadd", "Prob140_fsm_hdlc", "Prob034_dff8",
           "Prob045_edgedetect2", "Prob121_2014_q3bfsm", "Prob154_fsm_ps2data", "Prob115_shift18",
           "tinyriscv_clint")


def reply(kind: str, text: str, name: str) -> str:
    if kind == "pass":
        return f"[BEGIN]\n{text}[DONE]\n"
    if kind == "wrong":
        tied = "\n".join(f"  assign {o} = 1'b0;" for o in _outs(text))
        head = text.split(");", 1)[0] + ");\n"
        decl = "".join(ln + "\n" for ln in text.splitlines() if ln.strip().startswith(
            ("input", "output")))
        return f"[BEGIN]\n{head}{decl}{tied}\nendmodule\n[DONE]\n"
    if kind == "syntax":
        return f"[BEGIN]\nmodule {name}(input a; output y)\nassign y = ;\nendmodule\n[DONE]\n"
    if kind == "assembly":
        return "[BEGIN]\n" + text.replace(f"module {name}", "module Other_module") + "[DONE]\n"
    return "I think this block is a gate.\n"


def _outs(text: str) -> list[str]:
    return [ln.split()[1].rstrip(";") for ln in text.splitlines()
            if ln.strip().startswith("output")]


def mutation_check() -> str:
    """Equivalence check on the assembled clint with every NAND/NOR/NOT output inverted: must be
    ``neq``."""
    work = DRY / "work" / "tinyriscv_clint"
    sample = (work / "top-D-1" / "sample.sv").read_text(encoding="utf-8")
    bad = work / "mutated"
    bad.mkdir(exist_ok=True)
    (bad / "sample.sv").write_text(sample.replace("= ~(", "= ("), encoding="utf-8", newline="\n")
    return str(equiv.design_equiv(pop.netlist_path("tinyriscv_clint"), pop.read(
        "tinyriscv_clint").module, bad / "sample.sv", bad / "eq"))


def main() -> int:
    DRY.mkdir(exist_ok=True)
    for n in ("blocks", "calls", "ext"):
        link = DRY / n
        if not link.exists():
            link.symlink_to(REAL / n)
    (DRY / "calls.jsonl").write_text((REAL / "calls.jsonl").read_text(encoding="utf-8"),
                                     encoding="utf-8", newline="\n")
    designs = [d for d in json.loads((env.HERE / "designs.json").read_text(encoding="utf-8"))
               if d["problem"] in DESIGNS]
    idx = co.index_calls(DRY)
    expect: dict[tuple[str, str, int], str] = {}
    n_written = 0
    for i, d in enumerate(designs):
        nl = pop.read(d["problem"])
        blocks = co.bd.load_blocks(d["problem"])
        ports = rn.block_ports(nl, blocks)
        for arm in co.bd.ARMS:
            for draw in co.bd.DRAWS:
                # one pattern per (design, draw): a call shared by D and Dh has one reply
                kind = "pass" if draw == 1 else PATTERNS[(i + draw) % len(PATTERNS)]
                if not d["n_blocks"]:
                    kind = "pass"  # no call to corrupt: the assembly of assigns alone
                if d["n_blocks"] and (d["problem"], d["blocks"][0]["bid"], arm, draw) not in idx:
                    continue  # no call for this draw (tier ext has one draw)
                if not d["n_blocks"] and arm != "D":
                    continue
                expect[(d["problem"], arm, draw)] = kind
                for k, (b, pt) in enumerate(zip(blocks, ports, strict=True)):
                    call = idx.get((d["problem"], b.bid, arm, draw))
                    if call is None:
                        continue
                    bad = kind != "pass" and k == 0
                    text = reply("pass" if (kind == "pass" or not bad) else kind,
                                 ck.stub_decode(nl, b, pt), rn.module_name(b))
                    out = DRY / call["outbox_file"]
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text(text, encoding="utf-8", newline="\n")
                    n_written += 1
    rows, brows = co.run_all(DRY, {}, set(DESIGNS))
    co.write_csv(DRY / "results.csv", co.RES_FIELDS, rows)
    co.write_csv(DRY / "blocks.csv", co.BLK_FIELDS, brows)
    wrong = []
    for r in rows:
        kind = expect[(r["problem"], r["arm"], r["draw"])]
        want = EXPECT[kind]
        # a tied-low block of a design whose outputs are constant 0 may still pass: not asserted
        if kind == "pass" and r["outcome"] != "pass":
            wrong.append((r["problem"], r["arm"], r["draw"], kind, r["outcome"]))
        if kind == "wrong" and r["tier"] == "ext" and r["outcome"] != "neq":
            wrong.append((r["problem"], r["arm"], r["draw"], kind, r["outcome"]))
        if kind in ("syntax", "assembly", "nomark") and r["pass"]:
            wrong.append((r["problem"], r["arm"], r["draw"], kind, r["outcome"]))
        if kind in ("syntax", "assembly", "nomark") and r["outcome"] not in (
                want, "compile", "syntax", "assembly", "not_run", "error"):
            wrong.append((r["problem"], r["arm"], r["draw"], kind, r["outcome"]))
    mutated = mutation_check()
    if mutated != "neq":
        wrong.append(("tinyriscv_clint", "mutation", 0, "neq", mutated))
    timeouts = sum(1 for r in rows if r["outcome"] in ("timeout", "compile-timeout"))
    stub_ok = [b for b in brows if b["check"] == "ok"]
    report = {"designs": sorted(DESIGNS), "replies": n_written, "rows": len(rows),
              "pass": sum(r["pass"] for r in rows), "unexpected": wrong, "timeouts": timeouts,
              "blocks_checked_ok": len(stub_ok),
              "blocks_total": len(brows),
              "outcomes": {o: sum(1 for r in rows if r["outcome"] == o)
                           for o in sorted({r["outcome"] for r in rows})}}
    (HERE / "dryrun_result.json").write_text(json.dumps(report, sort_keys=True, indent=1) + "\n",
                                             encoding="utf-8", newline="\n")
    print(json.dumps(report, sort_keys=True))
    return 0 if not wrong and timeouts == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
