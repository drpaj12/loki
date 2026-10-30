"""Check a sequential claim against the original netlist, independently of Loki's own graph.

The claim is turned into a next-state function (counter, shift register, LFSR, mode table, state
machine), and the function is compared with the D wire of every state flip-flop of the *original*
gate netlist on random vectors in which each primary input and each flip-flop output is a free
512-bit signature (``netmap.orig_signatures`` of the pilot). This does not use Loki's re-mapped
graph or its classifier; it checks the sentence the claim makes: the stated width, direction,
modulus, wrap value, reset and enable, the bit order, the transitions. A vector whose present
state the claim does not cover (a state past the modulus, one the machine never reaches) or whose
asynchronous reset is active is skipped. A claim with no model, or whose nets are not wires of the
netlist, is ``unverified`` (``ok`` None) and gets no probability from the calibration.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from loki.re.seqtable import parse_count

N = 512
MIN_CHECKED = 64
Model = Callable[[int], int | None]


@dataclass(frozen=True)
class Verdict:
    ok: bool | None
    checked: int
    bad: int
    note: str = ""


class _Env:
    """Signatures of one netlist and the vector bits of its wires."""

    def __init__(self, sig: dict[str, int], dmap: dict[str, str]) -> None:
        self.sig, self.dmap = sig, dmap

    def has(self, name: str) -> bool:
        return name in self.sig or name in ("#0", "#1")

    def bit(self, name: str, v: int) -> int:
        if name == "#0":
            return 0
        if name == "#1":
            return 1
        return (self.sig[name] >> v) & 1

    def word(self, names: list[str], v: int) -> int:
        return sum(self.bit(n, v) << i for i, n in enumerate(names))


def _holds(cond: list[list[list[Any]]], env: _Env, v: int) -> bool:
    return any(all(env.bit(n, v) == pol for n, pol in prod) for prod in cond)


def _reset_hit(f: dict[str, Any], env: _Env, v: int) -> bool | None:
    """True when the reset is active at vector ``v``; None when the vector must be skipped (an
    asynchronous reset is active: the D wire does not describe that clock edge)."""
    r = f.get("rst")
    if r is None:
        return False
    active = env.bit(r["net"], v) == int(r["active"])
    return None if active and f.get("async") else active


def _count_next(direction: str, modulus: int, wrap: int, width: int, s: int) -> int | None:
    mask = (1 << width) - 1
    if modulus and s >= modulus:
        return None
    if direction == "down":
        return ((modulus - 1 if modulus else mask) if s == 0 else s - 1) & mask
    if modulus and s == modulus - 1:
        return wrap & mask
    return (s + 1) & mask


def _counter(f: dict[str, Any], env: _Env) -> Model:
    q, w = f["q"], int(f["width"])

    def model(v: int) -> int | None:
        s = env.word(q, v)
        hit = _reset_hit(f, env, v)
        if hit is None:
            return None
        if hit:
            return int(f["rst"]["value"])
        e = f.get("en")
        if e is not None and env.bit(e["net"], v) != int(e["active"]):
            return s
        mod = int(f["modulus"])
        return _count_next(f["dir"], 0 if mod == 1 << w else mod, int(f["wrap"]), w, s)

    return model


def _shift(f: dict[str, Any], env: _Env) -> Model:
    q, w = f["q"], int(f["width"])
    x = f.get("x")
    if x is None or not env.has(x):
        return lambda v: None

    def model(v: int) -> int | None:
        s = env.word(q, v)
        hit = _reset_hit(f, env, v)
        if hit is None:
            return None
        if hit:
            return int(f["rst"]["value"])
        e = f.get("en")
        if e is not None and env.bit(e["net"], v) != int(e["active"]):
            return s
        b = env.bit(x, v)
        mask = (1 << w) - 1
        return ((s << 1) | b) & mask if f["dir"] == "l" else (s >> 1) | (b << (w - 1))

    return model


def _lfsr(f: dict[str, Any], env: _Env) -> Model:
    q, w, taps = f["q"], int(f["width"]), int(f["taps"])

    def model(v: int) -> int | None:
        s = env.word(q, v)
        hit = _reset_hit(f, env, v)
        if hit is None:
            return None
        if hit:
            return int(f["rst"]["value"])
        e = f.get("en")
        if e is not None and env.bit(e["net"], v) != int(e["active"]):
            return s
        return ((s << 1) | (bin(s & taps).count("1") & 1)) & ((1 << w) - 1)

    return model


def _apply_mode(label: str, data: list[str], f: dict[str, Any], env: _Env, v: int) -> int | None:
    q, w = f["q"], int(f["width"])
    s = env.word(q, v)
    mask = (1 << w) - 1
    if label == "hold":
        return s
    if label == "load-const":
        return env.word(data, v) if len(data) == w else None
    if label in ("shift-l", "shift-r"):
        if len(data) != 1:
            return None
        b = env.bit(data[0], v)
        return ((s << 1) | b) & mask if label == "shift-l" else (s >> 1) | (b << (w - 1))
    count = parse_count(label)
    if count is None:
        return None
    return _count_next(count[0], count[1], count[2], w, s)


def _modes(f: dict[str, Any], env: _Env) -> Model:
    modes = f["modes"]

    def model(v: int) -> int | None:
        hit = _reset_hit(f, env, v)
        if hit is None:
            return None
        if hit:
            return int(f["rst"]["value"])
        live = [m for m in modes if _holds(m["cond"], env, v)]
        if len(live) != 1:
            return None
        return _apply_mode(live[0]["label"], live[0]["data"], f, env, v)

    return model


def _fsm(f: dict[str, Any], env: _Env) -> Model:
    q = f["q"]
    states = set(f["states"])
    moves: dict[int, list[tuple[list[list[list[Any]]], int]]] = {}
    for t in f["transitions"]:
        moves.setdefault(t["src"], []).append((t["cond"], t["dst"]))

    def model(v: int) -> int | None:
        s = env.word(q, v)
        hit = _reset_hit(f, env, v)
        if hit is None or (not hit and s not in states):
            return None
        if hit:
            return int(f["rst"]["value"])
        nxt = [dst for cond, dst in moves.get(s, []) if _holds(cond, env, v)]
        return nxt[0] if len(nxt) == 1 else -1

    return model


def _model(claim: dict[str, Any], env: _Env) -> Model | None:
    f = claim["facts"]
    kind = claim["kind"]
    if kind == "fsm":
        return _fsm(f, env)
    if "modes" in f:
        return _modes(f, env)
    if kind == "counter":
        return _counter(f, env)
    if kind == "shift_reg":
        return _shift(f, env)
    if kind == "lfsr" and "taps" in f:
        return _lfsr(f, env)
    return None


def _names_of(claim: dict[str, Any]) -> list[str]:
    f = claim["facts"]
    out = list(f.get("q", []))
    for key in ("en", "rst"):
        if key in f:
            out.append(f[key]["net"])
    out += f.get("controls", [])
    for m in f.get("modes", []):
        out += m["data"]
        out += [n for prod in m["cond"] for n, _ in prod]
    for t in f.get("transitions", []):
        out += [n for prod in t["cond"] for n, _ in prod]
    return out


def verify_claim(claim: dict[str, Any], sig: dict[str, int], dmap: dict[str, str]) -> Verdict:
    """Compare the claim's next-state function with the original D wires on ``N`` vectors."""
    env = _Env(sig, dmap)
    f = claim["facts"]
    if claim["source"] != "seq" or "q" not in f:
        return Verdict(None, 0, 0, "not a sequential claim")
    names = _names_of(claim)
    if any(not env.has(n) for n in names) or any(n not in dmap for n in f["q"]):
        return Verdict(None, 0, 0, "a net is not a wire of the netlist")
    if any(not env.has(dmap[n]) for n in f["q"]):
        return Verdict(None, 0, 0, "a D pin is not a wire")
    model = _model(claim, env)
    if model is None:
        return Verdict(None, 0, 0, "no model for this claim")
    checked = bad = 0
    ds = [dmap[n] for n in f["q"]]
    for v in range(N):
        want = model(v)
        if want is None:
            continue
        checked += 1
        bad += want != env.word(ds, v)
    if checked < MIN_CHECKED:
        return Verdict(None, checked, bad, "too few covered vectors")
    return Verdict(bad == 0, checked, bad)
