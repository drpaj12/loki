"""Shared pieces of the FSM encoding experiment: paths, arms, population, truth."""

from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
WS = Path(os.environ.get("FSMENC_WS", str(REPO.parent.parent)))
OUT = Path(os.environ.get("FSMENC_OUT", str(WS / "work" / "fsmenc-out")))
CORPUS = OUT / "corpus"
ODIN = Path(os.environ.get("ODIN3_ROOT", str(WS / "odin3")))
ARCH = Path(os.environ.get(
    "FSMENC_ARCH",
    str(WS / "work/norns-vtr/vtr_flow/arch/timing/k6_frac_N10_frac_chain_mem32K_40nm.xml")))
TAIL = "opt; flatten; opt -full; wreduce"
ARMS = {
    "onehot": f"proc; fsm -encoding one-hot; {TAIL}",
    "binary": f"proc; fsm -encoding binary; {TAIL}",
    "none": f"proc; {TAIL}",
}
FLOORS = ("f3", "f2")
NEG_FAMILIES = ("counter", "shifter", "register", "pipeline", "regfile")
DETECTORS = "wordfirst,hard,ff_pattern,mux,arith,seqfn,fsm,bus,unit,role,wordgroup"
SCORE_P = 0.5
ENC_NAMES = {"onehot": "one-hot", "binary": "binary", "gray": "other"}


def population() -> list[dict[str, str]]:
    """Positives (all fsm designs) and negatives (indices 70 to 89 of five families)."""
    with (CORPUS / "corpus.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    out = []
    for r in rows:
        idx = int(r["design"].rsplit("_", 1)[1])
        if r["family"] == "fsm":
            out.append(dict(r, role="pos"))
        elif r["family"] in NEG_FAMILIES and 70 <= idx < 90:
            out.append(dict(r, role="neg"))
    return out


def src_path(design: str) -> Path:
    return CORPUS / "designs" / design / f"{design}.v"


_SBLOCK = re.compile(r"^\s*(?:else )?(?:S(\d+): begin|if \(state == S(\d+)\) begin)")
_COND = re.compile(r"if \(x == \d+'d(\d+)\) nxt = S(\d+);")
_ELSE = re.compile(r"^\s*else nxt = S(\d+);")
_NIN = re.compile(r"input \[(\d+):0\] x")


def hdl_graph(text: str) -> dict[int, set[int]]:
    """Exact transition graph of the generated FSM (first matching ``x == c`` branch, else the
    default branch, for every input value), from the next-state block of the Verilog text."""
    nin = int(_NIN.search(text).group(1)) + 1  # type: ignore[union-attr]
    start = text.index("always @* begin\n    nxt = state;")
    end = text.index("always @(posedge clk)")
    cur = -1
    conds: dict[int, list[tuple[int, int]]] = {}
    default: dict[int, int] = {}
    for line in text[start:end].splitlines():
        m = _SBLOCK.match(line)
        if m:
            cur = int(m.group(1) or m.group(2))
            conds[cur] = []
            continue
        m = _COND.search(line)
        if m and cur >= 0:
            conds[cur].append((int(m.group(1)), int(m.group(2))))
            continue
        m = _ELSE.match(line)
        if m and cur >= 0 and cur not in default:
            default[cur] = int(m.group(1))
    graph: dict[int, set[int]] = {}
    for s, cs in conds.items():
        graph[s] = set()
        for v in range(1 << nin):
            hit = next((t for c, t in cs if c == v), None)
            graph[s].add(default[s] if hit is None else hit)
    return graph


def hdl_truth(text: str) -> tuple[int, int]:
    """(reachable states from S0, distinct transitions among them)."""
    g = hdl_graph(text)
    seen, work = {0}, [0]
    while work:
        s = work.pop()
        for t in g.get(s, ()):
            if t not in seen:
                seen.add(t)
                work.append(t)
    return len(seen), sum(len(g.get(s, ())) for s in seen)


_REC = re.compile(r"fsm: recoding '[^']*' with (one-hot|binary) encoding \((\d+) states, (\d+) bits")
_MAP = re.compile(r"fsm: '[^']*': mapping auto encoding to '(one-hot|binary)'")
_EXT = re.compile(r"fsm: extracting '[^']*': (\d+) states")


def log_facts(lines: list[str]) -> dict[str, Any]:
    """Facts of the Odin III ``fsm`` log. ``log_enc``: the encoding the register ends in (the
    ``mapping auto encoding to`` line; also set when the code was already packed binary and no
    recode ran). ``log_states``: reachable states, from the recode line when there is one (the
    ``extracting`` line counts unreachable states too)."""
    out: dict[str, Any] = {"extracted": False}
    for ln in lines:
        m = _EXT.search(ln)
        if m:
            out["extracted"] = True
            out["log_states_raw"] = int(m.group(1))
        m = _MAP.search(ln)
        if m:
            out["log_enc"] = m.group(1)
        m = _REC.search(ln)
        if m:
            out["log_states"] = int(m.group(2))
            out["log_bits"] = int(m.group(3))
    return out


def truth(design: dict[str, str], arm: str, bdir: Path) -> dict[str, Any]:
    """Truth record of one positive design in one arm."""
    params = json.loads(design["params"])
    states, trans = hdl_truth(src_path(design["design"]).read_text(encoding="utf-8"))
    facts: dict[str, Any] = {}
    flog = bdir / "fsm.log"
    if flog.is_file():
        facts = log_facts(flog.read_text(encoding="utf-8").splitlines())
    enc = facts.get("log_enc") or ENC_NAMES[params["enc"]]
    mismatch = "log_states" in facts and facts["log_states"] != states
    odin_states = facts.get("log_states", "")
    return {"design": design["design"], "arm": arm, "states": states, "transitions": trans,
            "encoding": enc, "hdl_enc": params["enc"], "extracted": facts.get("extracted", False),
            "log_mismatch": mismatch, "odin_states": odin_states}
