"""Link claims into the netlist text (B1) and build the wrong-content variant (B3, arm W).

Pure helpers on the original gate netlist text and the translated ``intent.json`` object.

``annotate`` appends a comment ``// loki h7 counter bit 2, p=0.97`` to the line of every gate,
flip-flop or port declaration whose output wire a claim covers. ``wrong_content`` moves every
claim to wires no claim names, on cells carrying no true tag (a seeded injective map over
every net a claim names, across classes), so ids, kinds, shapes and
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


def _cond(cond: Any, f: Any) -> Any:
    """A condition ``[[[net, value], ...], ...]`` with ``f`` applied to the nets."""
    return [[[f(n), v] for n, v in term] for term in cond]


def _fact(key: str, val: Any, f: Any) -> Any:
    """One ``facts`` entry with ``f`` applied to the net names it holds (all else kept)."""
    if key in ("q", "controls"):
        return [f(n) for n in val]
    if key in ("rst", "en"):
        return {**val, "net": f(val["net"])}
    if key == "x":
        return f(val)
    if key == "transitions":
        return [{**t, "cond": _cond(t["cond"], f)} for t in val]
    if key == "modes":
        return [{**m, "cond": _cond(m["cond"], f),
                 "data": [d if d.startswith("#") else f(d) for d in m["data"]]} for m in val]
    return val


def translate(intent: dict[str, Any], f: Any) -> dict[str, Any]:
    """Copy of ``intent`` with ``f`` applied to every net name: ``wires``, ``nets``, the net
    fields of ``facts``, bus bits and ``net_roles`` keys. Ids, kinds, p and text stay."""
    out = copy.deepcopy(intent)
    for c in out["claims"]:
        c["wires"] = [f(n) for n in c["wires"]]
        c["nets"] = {k: [f(n) for n in v] for k, v in c["nets"].items()}
        c["facts"] = {k: _fact(k, v, f) for k, v in c["facts"].items()}
    for b in out["buses"]:
        b["bits"] = [f(n) for n in b["bits"]]
        b["base"] = ""
    out["net_roles"] = {f(n): r for n, r in out["net_roles"].items()}
    return out


def _users(intent: dict[str, Any]) -> dict[str, set[str]]:
    """Net name to the ids of the claims that name it."""
    out: dict[str, set[str]] = {}
    for c in intent["claims"]:
        one = {"claims": [c], "buses": [], "net_roles": {}}
        seen: set[str] = set()

        def note(n: str, seen: set[str] = seen) -> str:
            seen.add(n)
            return n

        translate(one, note)
        for n in seen:
            out.setdefault(n, set()).add(c["id"])
    for b in intent["buses"]:
        for n in b["bits"]:
            out.setdefault(n, set())
    for n in intent["net_roles"]:
        out.setdefault(n, set())
    return out


def _shown(intent: dict[str, Any], users: dict[str, set[str]]) -> set[str]:
    """Nets whose name (or, for ``base[i]``, base name) occurs in the rendered hint text."""
    from loki.intent.text import render_claims

    doc = render_claims(intent)
    word = re.compile(r"[\w\[\]]+")
    toks = set(word.findall(doc))
    return {n for n in users if n in toks or n.split("[")[0] in toks
            or re.search(r"(?<![\w])" + re.escape(n.split("[")[0]) + r"\[", doc)}


def permutation(text: str, intent: dict[str, Any], seed: str) -> dict[str, str]:
    """A seeded map from each net a claim names to another wire. First choice: a wire no claim
    names whose driving line carries no true ``// loki`` tag (the wrong tags land on unrelated
    cells, in any class); a net with a driving line gets a target with one, so the number of tagged
    lines stays near the linked one. When those pools run dry (claims cover most of a small
    netlist): a net the hint text never prints gets a reused untagged wire (fewer tags on W);
    any other net gets a distinct wire on a tagged line whose true tags exclude every claim that
    names the net, if there is one. The clock maps to itself."""
    rng = random.Random(seed)
    lines = driver_lines(text)
    true_tags: dict[int, set[str]] = {}
    for c in intent["claims"]:
        for idx in marks({"claims": [c]}, lines):
            true_tags.setdefault(idx, set()).add(c["id"])
    decl = declarations(text)
    clocks = {w for p, w in _PIN.findall(text) if p == "C"}
    users = _users(intent)
    shown = _shown(intent, users)
    base = [w for w in sorted(decl) if w not in clocks and w not in users]
    fresh = [w for w in base if w in lines and lines[w] not in true_tags]
    plain = [w for w in base if w not in lines]
    rest = [w for w in base if w in lines and lines[w] in true_tags]
    named = [w for w in sorted(users) if w not in clocks and w in decl]
    rng.shuffle(named)
    for pool in (fresh, plain, rest):
        rng.shuffle(pool)
    spare = sorted(w for w in base if w in lines and lines[w] not in true_tags)
    out: dict[str, str] = {}
    for n in sorted(users):
        if n in clocks:
            continue
        order = (fresh, plain) if n in lines else (plain, fresh)
        pick = next((pool.pop() for pool in order if pool), None)
        if pick is None and n not in shown and spare:
            pick = spare[len(out) % len(spare)]
        for pool in (rest, named):
            if pick is None and pool:
                tags = [true_tags.get(lines.get(w, -1), set()) & users[n] for w in pool]
                ok = [i for i, w in enumerate(pool) if w != n and not tags[i]]
                other = [i for i, w in enumerate(pool) if w != n]
                if ok or other:
                    pick = pool.pop((ok or other)[0])
        if pick is not None and pick in named:
            named.remove(pick)
        if pick is not None:
            out[n] = pick
    return out


_TAG_ID = re.compile(r"(?:// loki |; )(h\d+) ")


def _tag_pairs(text: str) -> tuple[set[int], set[tuple[int, str]]]:
    lines: set[int] = set()
    pairs: set[tuple[int, str]] = set()
    for i, x in enumerate(text.split("\n")):
        if "// loki" in x:
            lines.add(i)
            pairs |= {(i, h) for h in _TAG_ID.findall(x)}
    return lines, pairs


def overlap(linked: str, wrong: str) -> dict[str, float | int]:
    """Overlap of two annotated netlists: tagged lines, and (line, claim id) tags, with the share
    of each side that the other has."""
    la, pa = _tag_pairs(linked)
    lb, pb = _tag_pairs(wrong)
    ln, pn = len(la & lb), len(pa & pb)
    return {"linked_lines": len(la), "wrong_lines": len(lb), "both_lines": ln,
            "line_of_linked": ln / len(la) if la else 0.0,
            "line_of_wrong": ln / len(lb) if lb else 0.0,
            "linked_tags": len(pa), "wrong_tags": len(pb), "both_tags": pn,
            "tag_of_linked": pn / len(pa) if pa else 0.0,
            "tag_of_wrong": pn / len(pb) if pb else 0.0}


def _mover(mapping: dict[str, str]) -> Any:
    return lambda n: mapping.get(n, n)


def wrong_content(text: str, intent: dict[str, Any], seed: str, tries: int = 40) -> dict[str, Any]:
    """The intent with every net name moved by ``permutation`` (claim ids, kinds, p kept). Of the
    ``tries`` permutations ``seed:0`` ... ``seed:tries-1`` the one whose annotated netlist shares
    the fewest (line, claim id) tags with the true one (worst of the two shares; lowest k on a
    tie) is used, so the choice is a function of ``seed`` alone."""
    linked = annotate(text, intent)
    best: tuple[float, int, dict[str, Any]] | None = None
    for k in range(tries):
        mapping = permutation(text, intent, f"{seed}:{k}")
        cand = translate(intent, _mover(mapping))
        o = overlap(linked, annotate(text, cand))
        score = max(o["tag_of_linked"], o["tag_of_wrong"])
        if best is None or score < best[0]:
            best = (score, k, cand)
    assert best is not None
    return best[2]
