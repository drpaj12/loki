"""Link claims into the netlist text (B1) and build the wrong-content variant (B3, arm W).

Pure helpers on the original gate netlist text and the translated ``intent.json`` object.

``annotate`` appends a comment ``// loki h7 counter bit 2, p=0.97`` to the line of every gate,
flip-flop or port declaration whose output wire a claim covers. ``wrong_content`` moves every
claim to other wires of the same netlist: a seeded permutation inside each class of wire (primary
input, flip-flop output, other wire) is applied to every name of every claim, so kinds, shapes and
probabilities stay and only the place is wrong.
"""

from __future__ import annotations

import copy
import random
import re
from typing import Any

_INST = re.compile(r"^(\s*)(\w+)\s+(\S+)\s*\(\s*$")
_PIN = re.compile(r"\.(\w+)\(\s*([^()]*?)\s*\)")
_DECL = re.compile(r"^\s*(input|output|wire)\s*(?:\[(\d+):(\d+)\])?\s*([A-Za-z_]\w*)\s*;")
OUT_PINS = ("Y", "Q")
MAX_TAGS = 3


def _bits(name: str, msb: str, lsb: str) -> list[str]:
    if not msb:
        return [name]
    lo, hi = sorted((int(msb), int(lsb)))
    return [f"{name}[{i}]" for i in range(lo, hi + 1)]


def declarations(text: str) -> dict[str, str]:
    """Wire bit name to ``input`` / ``output`` / ``wire`` (a port wins over its ``wire``)."""
    out: dict[str, str] = {}
    for line in text.split("\n"):
        m = _DECL.match(line)
        if m:
            for b in _bits(m.group(4), m.group(2) or "", m.group(3) or ""):
                out[b] = out[b] if out.get(b) in ("input", "output") else m.group(1)
    return out


def driver_lines(text: str) -> dict[str, int]:
    """Output wire to the index of the first line of the gate or flip-flop that drives it, and
    input port bit to its declaration line."""
    lines = text.split("\n")
    out: dict[str, int] = {}
    i = 0
    while i < len(lines):
        m = _INST.match(lines[i])
        if m and m.group(2) not in ("module", "input", "output", "wire"):
            j = i
            body = []
            while j < len(lines) and not lines[j].strip().startswith(");"):
                body.append(lines[j])
                j += 1
            for pin, wire in _PIN.findall("\n".join(body)):
                if pin in OUT_PINS:
                    out.setdefault(wire, i)
            i = j
        i += 1
    for i, line in enumerate(lines):
        m = _DECL.match(line)
        if m and m.group(1) == "input":
            for b in _bits(m.group(4), m.group(2) or "", m.group(3) or ""):
                out.setdefault(b, i)
    return out


def _tag(c: dict[str, Any], wire: str) -> str:
    from loki.intent.text import pfmt

    f = c["facts"]
    p = "" if c["p"] is None else f", {pfmt(c['p'])}"
    q = f.get("q", [])
    if wire in q:
        return f"{c['id']} {c['kind']} bit {q.index(wire)}{p}"
    d = c["nets"].get("d", [])
    if wire in d:
        return f"{c['id']} next-state of {c['kind']} bit {d.index(wire)}{p}"
    for key in ("rst", "en"):
        if key in f and f[key]["net"] == wire:
            word = "reset" if key == "rst" else "enable"
            return f"{c['id']} {word} of {c['kind']}{p}"
    if wire in f.get("controls", []):
        return f"{c['id']} input of {c['kind']}{p}"
    return f"{c['id']} {c['kind']} logic{p}"


def marks(intent: dict[str, Any], lines: dict[str, int]) -> dict[int, list[str]]:
    """Line index to the tags of the claims that cover a wire driven there."""
    out: dict[int, list[str]] = {}
    for c in sorted(intent["claims"], key=lambda c: int(c["id"][1:])):
        wires = set(c["wires"]) | set(c["facts"].get("q", [])) | {
            c["facts"][k]["net"] for k in ("rst", "en") if k in c["facts"]} | set(
            c["facts"].get("controls", []))
        for w in sorted(wires):
            if w in lines:
                out.setdefault(lines[w], []).append(_tag(c, w))
    return out


def annotate(text: str, intent: dict[str, Any]) -> str:
    """``text`` with a ``// loki ...`` comment on the line of each covered gate or port."""
    lines = text.split("\n")
    for idx, tags in marks(intent, driver_lines(text)).items():
        extra = [f"+{len(tags) - MAX_TAGS} more"] if len(tags) > MAX_TAGS else []
        shown = tags[:MAX_TAGS] + extra
        lines[idx] = lines[idx].rstrip() + "  // loki " + "; ".join(shown)
    return "\n".join(lines)


def _classes(text: str, intent: dict[str, Any]) -> dict[str, list[str]]:
    decl = declarations(text)
    ff_q = {w for c in intent["claims"] for w in c["facts"].get("q", [])}
    pins = {w for _, w in _PIN.findall(text)}
    clocks = {w for p, w in _PIN.findall(text) if p == "C"}
    cls: dict[str, list[str]] = {"input": [], "state": [], "wire": []}
    for w, kind in sorted(decl.items()):
        if w in clocks:
            continue
        if kind == "input":
            cls["input"].append(w)
        elif w in ff_q or (w in pins and kind == "output"):
            cls["state"].append(w)
        else:
            cls["wire"].append(w)
    return cls


def permutation(text: str, intent: dict[str, Any], seed: str) -> dict[str, str]:
    """A seeded map wire -> other wire of the same class; no wire maps to itself unless its class
    has a single member."""
    rng = random.Random(seed)
    out: dict[str, str] = {}
    for members in _classes(text, intent).values():
        if len(members) < 2:
            continue
        shuffled = list(members)
        for _ in range(20):
            rng.shuffle(shuffled)
            if all(a != b for a, b in zip(members, shuffled, strict=True)):
                break
        else:
            shuffled = members[1:] + members[:1]
        out.update(zip(members, shuffled, strict=True))
    return out


def _walk(obj: Any, mapping: dict[str, str]) -> Any:
    if isinstance(obj, str):
        return mapping.get(obj, obj)
    if isinstance(obj, list):
        return [_walk(x, mapping) for x in obj]
    if isinstance(obj, dict):
        return {k: _walk(v, mapping) for k, v in obj.items()}
    return obj


def wrong_content(text: str, intent: dict[str, Any], seed: str) -> dict[str, Any]:
    """The intent with every wire name moved by ``permutation`` (claim ids, kinds, p kept)."""
    mapping = permutation(text, intent, seed)
    out = copy.deepcopy(intent)
    for key in ("claims", "buses"):
        out[key] = _walk(out[key], mapping)
    out["net_roles"] = {mapping.get(n, n): r for n, r in out["net_roles"].items()}
    return out
