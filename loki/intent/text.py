"""Plain-English text of the v2 claims: one line per claim, the probability first, then evidence.

Pure on the ``intent.json`` object (names already those of the netlist the reader sees).
Probabilities are printed as the calibrated value truncated to two decimals (0.9999 is ``0.99``);
a claim without a calibrated probability says so.
"""

from __future__ import annotations

import math
import re
from typing import Any

_IDX = re.compile(r"^(.*)\[(\d+)\]$")
MAX_TRANSITIONS = 24
MAX_LIST = 12
_NOUN = {"eq_const": "comparison against a constant", "adder": "adder", "subtractor": "subtractor",
         "adder_cin": "adder with carry-in", "comparator": "comparator", "mux": "multiplexer",
         "mux_tree": "multiplexer tree", "mux_bit": "one-bit multiplexer", "bus": "bus",
         "register": "register", "ff_en": "flip-flop with enable",
         "ff_srst": "flip-flop with synchronous reset"}


def pfmt(p: float | None) -> str:
    """``p=0.97``; the value is truncated to two decimals so 0.9999 never reads as certain."""
    return "no calibrated p" if p is None else f"p={math.floor(p * 100) / 100:.2f}"


def bus_name(names: list[str]) -> str:
    """``q[3:0]`` for ``q[0..3]`` in either order, else the names joined."""
    found = [_IDX.match(n) for n in names]
    if len(names) >= 2 and all(found):
        base = {m.group(1) for m in found if m}
        idx = [int(m.group(2)) for m in found if m]
        if len(base) == 1 and (idx == list(range(idx[0], idx[0] + len(idx)))
                               or idx == list(range(idx[0], idx[0] - len(idx), -1))):
            hi, lo = max(idx), min(idx)
            return f"{base.pop()}[{hi}:{lo}]"
    return ", ".join(names)


def cond_text(cond: list[list[list[Any]]]) -> str:
    """``go & ~rst | x``; ``always`` for a constant-true condition, ``never`` for none."""
    if not cond:
        return "never"
    if any(not prod for prod in cond):
        return "always"
    return " | ".join(" & ".join(n if pol else f"~{n}" for n, pol in prod) for prod in cond)


def _level(net: str, active: int) -> str:
    return f"{net} is {'high' if active else 'low'}"


def _reset_text(f: dict[str, Any]) -> str:
    r = f.get("rst")
    if r is None:
        return ""
    kind = "asynchronous" if f.get("async") else "synchronous"
    return f"; {kind} reset to {r['value']} when {_level(r['net'], r['active'])}"


def _enable_text(f: dict[str, Any]) -> str:
    e = f.get("en")
    return "" if e is None else f"; counts only when {_level(e['net'], e['active'])}"


def _serial_text(data: list[str]) -> str:
    if not data:
        return ""
    return f" (shifting in {data[0][1:]})" if data[0].startswith("#") else (
        f" (serial input {data[0]})")


def _modes_text(f: dict[str, Any], q: str) -> str:
    out = []
    for m in f["modes"]:
        label = m["label"]
        where = cond_text(m["cond"])
        if label == "load-const":
            what = f"loads {bus_name(m['data'])}" if m["data"] else "loads a value"
        elif label.startswith("shift"):
            way = "left" if label.endswith("l") else "right"
            what = f"shifts {way}" + _serial_text(m["data"])
        elif label == "hold":
            what = "holds"
        else:
            what = f"{label.replace('-', ' ')}"
        out.append(f"{what} when {where}")
    return f"{q}: " + "; ".join(out)


def _counter(f: dict[str, Any], q: str) -> str:
    w, mod, wrap = f["width"], f["modulus"], f["wrap"]
    if f["dir"] == "down":
        span = f"counts down by 1 and goes from 0 to {mod - 1}"
    elif mod == 1 << w:
        span = f"counts through all {mod} values and wraps to {wrap}"
    else:
        span = f"counts up by 1 from {f.get('start', 0)} to {mod - 1}, then returns to {wrap}"
    return f"{q} is a {w}-bit {f['dir']} counter; {span}" + _enable_text(f) + _reset_text(f)


def _shift(f: dict[str, Any], q: str) -> str:
    way = "left (new bit enters q[0] side)" if f["dir"] == "l" else "right"
    text = f"{q} is a {f['width']}-bit shift register shifting {way}"
    if f.get("x"):
        text += f"; serial input {f['x']}"
    if f.get("en"):
        text += f"; shifts only when {_level(f['en']['net'], f['en']['active'])}"
    return text + _reset_text(f)


def state_label(f: dict[str, Any], s: int) -> str:
    """A state of a one-hot machine is named by its set bit (``state[2]``), any other by its value
    as an unsigned number with bit 0 first."""
    if f["encoding"] == "one-hot":
        if s == 0:
            return "idle(all zero)"
        return str(f["q"][s.bit_length() - 1])
    return str(s)


def _fsm(f: dict[str, Any], q: str) -> str:
    states = f["states"]
    listed = ", ".join(state_label(f, s) for s in states)
    how = ("one-hot: a state is the flip-flop that is high" if f["encoding"] == "one-hot"
           else f"{f['encoding']} encoding: a state is the value of {q} as an unsigned number")
    text = f"{q} holds a {len(states)}-state machine ({how}); states {listed}"
    r = f.get("rst")
    if r is not None:
        kind = "asynchronous" if f.get("async") else "synchronous"
        text += (f"; {kind} reset when {_level(r['net'], r['active'])} enters state "
                 f"{state_label(f, int(r['value']))}")
    else:
        text += f"; no reset found, states reached from {state_label(f, int(f['start']))}"
    if f["controls"]:
        text += f"; inputs {', '.join(f['controls'])}"
    return text


def _transitions(f: dict[str, Any]) -> list[str]:
    rows = [f"{state_label(f, t['src'])} -> {state_label(f, t['dst'])} when "
            f"{cond_text(t['cond'])}" for t in f["transitions"]]
    if len(rows) > MAX_TRANSITIONS:
        rows = [*rows[:MAX_TRANSITIONS], f"... ({len(rows) - MAX_TRANSITIONS} more)"]
    return rows


def _sentence(c: dict[str, Any]) -> str:
    f = c["facts"]
    kind = c["kind"]
    if "q" in f:
        q = bus_name(f["q"])
        if kind == "fsm":
            return _fsm(f, q)
        if "modes" in f:
            noun = {"counter": "counter", "shift_reg": "shift register", "lfsr": "LFSR",
                    "register": "register"}[kind]
            return f"{q} is a {f['width']}-bit {noun} with modes - " + _modes_text(f, "") \
                .lstrip(": ") + _reset_text(f)
        if kind == "counter":
            return _counter(f, q)
        if kind == "shift_reg":
            return _shift(f, q)
        if kind == "lfsr":
            return f"{q} is a {f['width']}-bit LFSR with feedback taps mask {f['taps']}" \
                + _reset_text(f)
    ports = "; ".join(f"{k} = {bus_name(v)}" for k, v in c["nets"].items() if v)
    fn = f.get("fn", "")
    noun = _NOUN.get(kind, kind)
    return f"{noun} `{fn}` ({ports})" if fn else f"{noun} ({ports})"


def _evidence(c: dict[str, Any]) -> str:
    ev = c["evidence"]
    if ev == "exhaustive":
        return "proved by exhaustive simulation of the next-state logic"
    if ev == "sampled":
        return "candidate, checked on sampled inputs only"
    if ev.startswith("proof:"):
        return f"proved by {ev[6:].replace('_', ' ')}"
    return "candidate, structural match, unproven"


def claim_line(c: dict[str, Any]) -> str:
    """``h7 (p=0.97, proved by exhaustive simulation ...): q[3:0] is a 4-bit up counter; ...``"""
    head = f"{c['id']} ({pfmt(c['p'])}, {_evidence(c)})"
    line = f"{head}: {_sentence(c)}."
    if c.get("merged"):
        line += f" Also reported as {', '.join(c['merged'])}."
    return line


def claim_block(c: dict[str, Any]) -> list[str]:
    out = [claim_line(c)]
    if c["kind"] == "fsm":
        out += [f"    {row}" for row in _transitions(c["facts"])]
    return out


def role_lines(intent: dict[str, Any]) -> list[str]:
    """Control and data nets of the claims, leaf nets only (no internal wire)."""
    groups: dict[str, list[str]] = {"control": [], "datapath": [], "mixed": []}
    claim_nets = {n for c in intent["claims"] for k, ns in c["nets"].items() if k != "d"
                  for n in ns}
    for net, r in sorted(intent["net_roles"].items()):
        if net in claim_nets and r["role"] in groups:
            groups[r["role"]].append(net if r["p"] is None else f"{net} ({pfmt(r['p'])})")
    out = []
    for role in ("control", "datapath", "mixed"):
        items = groups[role]
        if items:
            more = f", ... (+{len(items) - MAX_LIST})" if len(items) > MAX_LIST else ""
            out.append(f"- {role}: {', '.join(items[:MAX_LIST])}{more}")
    return out


def bus_lines(intent: dict[str, Any]) -> list[str]:
    out = []
    for b in intent["buses"]:
        links = [x for x in b["links"] if not x["text"].startswith("next-state")]
        if not links:
            continue
        why = "; ".join(x["text"] for x in links)
        p = f" ({pfmt(b['p'])})" if b["p"] is not None else ""
        out.append(f"- {b['id']}{p}: {bus_name(b['bits'])} is the {why}; bit 0 = {b['bits'][0]}")
    return out


def render_claims(intent: dict[str, Any]) -> str:
    """The claim sections of the hint block (intent level first)."""
    claims = sorted(intent["claims"], key=lambda c: (c["source"] != "seq", int(c["id"][1:])))
    out = ["## Claims", ""]
    for c in claims:
        out += claim_block(c)
    if not claims:
        out.append("Loki has no claim about this netlist.")
    buses = bus_lines(intent)
    if buses:
        out += ["", "## Buses", "", *buses]
    roles = role_lines(intent)
    if roles:
        out += ["", "## Control and data nets", "", *roles]
    return "\n".join(out) + "\n"
