"""A3: one claim per piece. Identical or nested claims of one kind collapse into the larger one.

Two claims of one kind are the same piece when every net list of the smaller is contained in the
same-named list of the larger and their parameters agree (width and bit-order source aside). The
survivor keeps the highest probability of the group and lists the merged ids (``merged``), so a
reader sees both that the claim was made several times and where. Pure on claim dicts.
"""

from __future__ import annotations

from typing import Any

IGNORED_PARAMS = frozenset({"width", "k", "order_source", "decoders", "states", "rows_n", "claim"})


def _size(c: dict[str, Any]) -> int:
    return sum(len(v) for v in c["nets"].values())


def _num(hid: str) -> int:
    return int(hid[1:])


def _same_params(a: dict[str, Any], b: dict[str, Any]) -> bool:
    pa, pb = a.get("params", {}), b.get("params", {})
    return all(pa[k] == pb[k] for k in pa.keys() & pb.keys() if k not in IGNORED_PARAMS)


def covers(big: dict[str, Any], small: dict[str, Any]) -> bool:
    """Whether ``big`` says everything ``small`` says (same kind, nets contained, same params)."""
    if big["kind"] != small["kind"] or not small["nets"]:
        return False
    for role, nets in small["nets"].items():
        if not set(nets) <= set(big["nets"].get(role, ())):
            return False
    return _same_params(big, small)


def _absorb(keep: dict[str, Any], gone: dict[str, Any]) -> None:
    pk, pg = keep.get("p"), gone.get("p")
    if pk is None or (pg is not None and pg > pk):
        keep["p"] = pg
    keep["merged"] = sorted({*keep.get("merged", []), gone["id"], *gone.get("merged", [])},
                            key=_num)
    keep["wires"] = sorted({*keep.get("wires", []), *gone.get("wires", [])})


def merge_duplicates(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The claims with identical and nested same-kind claims merged (input unchanged)."""
    order = sorted((dict(c) for c in claims),
                   key=lambda c: (-_size(c), _num(c["id"])))
    kept: list[dict[str, Any]] = []
    for c in order:
        for k in kept:
            if covers(k, c):
                _absorb(k, c)
                break
        else:
            c.setdefault("merged", [])
            kept.append(c)
    return sorted(kept, key=lambda c: _num(c["id"]))
