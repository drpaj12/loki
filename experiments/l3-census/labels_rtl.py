"""RTL-side pattern labels for the L3 census (never from a netlist).

Input per design: the L0 ``words.json`` of an Odin III build (the word-level IR of the HDL after
``proc; fsm; opt; flatten``; word types, the ``fsm`` flag of Odin III fsm detection, word edges)
and the Verilog source text (named idioms). ``label_design`` returns pattern counts.
Rules (spec section 9): fsm, counter, shift, lfsr, timer, fsm_counter, fsm_shift, regfile,
register, glue.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

REGS = ("$dff", "$dffe", "$sdff", "$sdffe", "$adff", "$adffe")
ARITH = ("$add", "$sub")
COMPARE = ("$eq", "$ne", "$gt", "$lt", "$ge", "$le", "$logic_not", "$reduce_or", "$reduce_bool")
PATTERNS = ("fsm", "counter", "shift", "lfsr", "timer", "fsm_counter", "fsm_shift", "regfile",
            "register", "glue")

_COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
_SHIFT = (
    re.compile(r"\b(\w+)\s*(?:<=|=)\s*\{[^;]*?\b\1\s*\[[^\]]*:[^\]]*\]"),
    re.compile(r"\b(\w+)\s*(?:<=|=)\s*\(?\s*\1\s*(?:>>>|>>|<<)"),
    re.compile(r"\b(\w+)_next\s*=\s*\1\s*\[\s*\w+\s*:\s*\w+\s*\]"),
    re.compile(r"\b(\w+)\s*\[[^\]]+\]\s*(?:<=|=)\s*\1\s*\[[^\]]*[-+]\s*1\s*\]"),
)
_ARRAY = re.compile(r"\b(?:reg|logic)\b[^;=]*?\b\w+\s*\[[^\]]+:[^\]]+\]\s*(?:,|;)")


def strip_comments(text: str) -> str:
    return _COMMENT.sub("", text)


def _graph(words: dict[str, Any]) -> tuple[dict[int, str], dict[int, set[int]], dict[int, Any]]:
    kind = {w["id"]: w["type"] for w in words["words"]}
    byid = {w["id"]: w for w in words["words"]}
    succ: dict[int, set[int]] = defaultdict(set)
    for e in words["edges"]:
        succ[e["src"]].add(e["dst"])
    return kind, succ, byid


def _reach(start: int, succ: dict[int, set[int]], kind: dict[int, str]) -> dict[int, set[str]]:
    """Words reachable from ``start`` without crossing a register; value = types seen on the way
    (including the end word). A register reached is recorded but not expanded."""
    seen: dict[int, set[str]] = {}
    stack: list[tuple[int, frozenset[str]]] = [(start, frozenset())]
    while stack:
        node, types = stack.pop()
        for nxt in succ.get(node, ()):
            t = types | {kind[nxt]}
            if nxt in seen and t <= seen[nxt]:
                continue
            seen.setdefault(nxt, set()).update(t)
            if kind[nxt] not in REGS:
                stack.append((nxt, frozenset(seen[nxt])))
    return seen


def source_shift(text: str) -> bool:
    return any(p.search(text) for p in _SHIFT)


def label_design(words: dict[str, Any], src_text: str) -> dict[str, int]:
    """Pattern -> instance count (0 = absent). Instances are register words, not designs."""
    text = strip_comments(src_text)
    kind, succ, byid = _graph(words)
    regs = [i for i, t in kind.items() if t in REGS]
    fsm = {i for i in regs if byid[i].get("fsm")}
    loops: dict[int, set[str]] = {}
    for r in regs:
        types = _reach(r, succ, kind).get(r)
        if types is not None:
            loops[r] = types
    counters = {r for r, t in loops.items() if r not in fsm and any(x in ARITH for x in t)}
    shift = source_shift(text)
    lfsr = shift and ("^" in text or any(kind[i] in ("$xor", "$xnor") for i in kind))
    timers = {r for r in counters if _timer(r, succ, kind)}
    out = {p: 0 for p in PATTERNS}
    out["fsm"] = len(fsm)
    out["counter"] = len(counters)
    out["shift"] = int(shift)
    out["lfsr"] = int(lfsr)
    out["timer"] = len(timers)
    out["fsm_counter"] = int(bool(fsm and counters and _linked(fsm, counters, succ, kind)))
    out["fsm_shift"] = int(bool(fsm and shift and len(regs) > len(fsm)))
    out["regfile"] = int(bool(_ARRAY.search(text)) or any(t == "$mem" for t in kind.values()))
    plain = [r for r in regs if r not in fsm and r not in counters]
    out["register"] = int(bool(regs) and not (fsm or counters or shift or out["regfile"])
                          and bool(plain))
    out["glue"] = int(not regs)
    return out


def _timer(reg: int, succ: dict[int, set[int]], kind: dict[int, str]) -> bool:
    """A counter whose value is compared and whose compare result reaches the counter again
    (terminal count reload/stop) without crossing a register."""
    for w, types in _reach(reg, succ, kind).items():
        if kind[w] in COMPARE and reg in _reach(w, succ, kind):
            return True
    return False


def _linked(a: set[int], b: set[int], succ: dict[int, set[int]], kind: dict[int, str]) -> bool:
    for x in a:
        if b & set(_reach(x, succ, kind)):
            return True
    for y in b:
        if a & set(_reach(y, succ, kind)):
            return True
    return False
