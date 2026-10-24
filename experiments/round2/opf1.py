"""RQ-L7: word-level operator-recovery F1.

The L0 key lists the word cells of the elaborated reference (``words.json``). A run recovers an
operator when it names one by type (and width). The score is location-free: it compares multisets
of ``(operator, width)``, so it does not depend on which cells carry the operator, only on whether
the right operators were recovered. Two variants: ``type`` (operator class only) and ``tw``
(operator class and operand width).

Operator classes: ``add``, ``sub``, ``mul``, ``neg``, ``eq``, ``ne``, ``lt``, ``le``, ``gt``,
``ge``, ``mux`` ($mux and $pmux), ``reg`` (every flip-flop word). Bitwise logic, reductions,
constants and shifts are not operators the L1 detectors can name and are left out of the key.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

OpKey = tuple[str, int]

_ARITH = {"$add": "add", "$sub": "sub", "$mul": "mul", "$neg": "neg"}
_COMPARE = {"$eq": "eq", "$ne": "ne", "$lt": "lt", "$le": "le", "$gt": "gt", "$ge": "ge"}
_MUX = ("$mux", "$pmux")
_REG_PREFIXES = ("$dff", "$adff", "$sdff", "$aldff", "$dlatch", "$adlatch")
LIVE = ("open", "confirmed", "committed")


def word_op(wtype: str, params: Mapping[str, Any]) -> OpKey | None:
    """The ``(class, width)`` of a word cell, or None when it is not an operator."""
    if wtype in _ARITH or wtype in _COMPARE:
        cls = _ARITH.get(wtype) or _COMPARE[wtype]
        width = max(int(params.get("A_WIDTH", 1)), int(params.get("B_WIDTH", 0)))
        return cls, width
    if wtype in _MUX:
        return "mux", int(params.get("WIDTH", 1))
    if wtype.startswith(_REG_PREFIXES):
        return "reg", int(params.get("WIDTH", 1))
    return None


def key_ops(words: Mapping[str, Any]) -> Counter[OpKey]:
    """Operator multiset of a ``words.json`` object."""
    out: Counter[OpKey] = Counter()
    for w in words["words"]:
        op = word_op(str(w["type"]), w["params"])
        if op is not None:
            out[op] += 1
    return out


def counted(h: Mapping[str, Any], p_min: float) -> bool:
    return bool(h["status"] == "committed" or (h["status"] in LIVE and h["p_comp"] >= p_min))


def _hyp_op(h: Mapping[str, Any]) -> OpKey | None:
    kind = str(h["kind"])
    par = h.get("params", {})
    width = int(par.get("width", 1))
    if kind in ("adder", "adder_cin", "hard_add"):
        return "add", width
    if kind == "subtractor":
        return "sub", width
    if kind == "hard_mul":
        return "mul", width
    if kind == "comparator":
        return str(par.get("op", "")), width
    if kind == "eq_const":
        return str(par.get("op", "eq")), width
    if kind == "mux":
        return "mux", width
    return None


def hyp_ops(overlay: Mapping[str, Any], p_min: float = 0.5) -> Counter[OpKey]:
    """Operator multiset of the counted hypotheses of an ``overlay.json`` object.

    Bit-level ``mux_bit``, ``ff_en`` and ``ff_srst`` hypotheses count as width-1 operators only
    when their cells lie in no counted ``mux`` or ``register`` hypothesis."""
    hyps = [h for h in overlay["hypotheses"] if counted(h, p_min)]
    out: Counter[OpKey] = Counter()
    word_cells: dict[str, set[str]] = {"mux": set(), "reg": set()}
    for h in hyps:
        op = _hyp_op(h)
        if op is not None:
            out[op] += 1
            if op[0] == "mux":
                word_cells["mux"].update(h["cells"])
        elif h["kind"] == "register":
            out["reg", len(h["nets"].get("q", ())) or 1] += 1
            word_cells["reg"].update(h["cells"])
    for h in hyps:
        if h["kind"] == "mux_bit" and not set(h["cells"]) & word_cells["mux"]:
            out["mux", 1] += 1
        elif h["kind"] in ("ff_en", "ff_srst") and not set(h["cells"]) & word_cells["reg"]:
            out["reg", 1] += 1
    return out


def _by_class(ops: Counter[OpKey]) -> Counter[OpKey]:
    out: Counter[OpKey] = Counter()
    for (cls, _w), n in ops.items():
        out[cls, 0] += n
    return out


def _f1(prec: float | None, rec: float | None) -> float | None:
    """F1; 0 when recall is 0 (even without a prediction); None when there is no key."""
    if rec is None:
        return None
    if rec == 0 or prec is None:
        return 0.0
    return 2 * prec * rec / (prec + rec)


def score(key: Counter[OpKey], got: Counter[OpKey]) -> dict[str, float | int | None]:
    """Multiset precision, recall and F1 of ``got`` against ``key``, for ``type`` and ``tw``."""
    out: dict[str, float | int | None] = {"key_n": sum(key.values()), "got_n": sum(got.values())}
    for name, (k, g) in {"type": (_by_class(key), _by_class(got)), "tw": (key, got)}.items():
        tp = sum((k & g).values())
        prec = tp / sum(g.values()) if g else None
        rec = tp / sum(k.values()) if k else None
        f = _f1(prec, rec)
        out.update({f"{name}_tp": tp, f"{name}_p": prec, f"{name}_r": rec, f"{name}_f1": f})
    return out


def pooled(rows: Iterable[Mapping[str, Any]]) -> dict[str, float | int | None]:
    """Micro-pooled precision, recall and F1 over per-design score rows."""
    rows = list(rows)
    key_n = sum(int(r["key_n"]) for r in rows)
    got_n = sum(int(r["got_n"]) for r in rows)
    out: dict[str, float | int | None] = {"designs": len(rows), "key_n": key_n, "got_n": got_n}
    for name in ("type", "tw"):
        tp = sum(int(r[f"{name}_tp"]) for r in rows)
        prec = tp / got_n if got_n else None
        rec = tp / key_n if key_n else None
        f = _f1(prec, rec)
        out.update({f"{name}_p": prec, f"{name}_r": rec, f"{name}_f1": f})
    return out


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
