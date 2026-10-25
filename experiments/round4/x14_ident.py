"""Exploratory entry 2026-10-25-c, items 7, 8, 12 of the round-4 fix brief (RQ-L14).

Reruns the identifiability stage of ``l14_ident.py`` under variants of its canonical form and
writes ``x14_ident.csv`` (pooled ceilings per variant, family and floor). Not part of the
registered analysis; no status changes.

Variants: ``reg`` (the registered form, a check that this driver reproduces ``l14_ident.csv``),
``cap720`` (all tied LUT input orders enumerated, 720 = 6!), ``pins`` (isomorphism-invariant pin
labels: a LUT input is labelled by the cofactor counts of its variable, a gate input by its
symmetry class, so swapping symmetric gate pins no longer splits a class and a LUT with
distinguishable inputs no longer merges with its input-swapped sibling), ``cap720+pins``, and each
of these on the deduplicated twin set (one design per byte-identical Verilog text within a base
position, design name masked).
"""

from __future__ import annotations

import sys
from typing import Any

import dictlib
import l14_ident
import r4lib

_COF: dict[tuple[int, int], list[tuple[int, int]]] = {}
_SYM: dict[str, dict[str, str]] = {}


def lut_label(tab: int, w: int, i: int) -> str:
    key = (tab, w)
    if key not in _COF:
        _COF[key] = [(sum(1 for m in range(1 << w) if ((m >> v) & 1) == 0 and (tab >> m) & 1),
                      sum(1 for m in range(1 << w) if ((m >> v) & 1) == 1 and (tab >> m) & 1))
                     for v in range(w)]
    c0, c1 = _COF[key][i] if i < w else (0, 0)
    return f"C{c0}_{c1}"


def gate_classes(ctype: str) -> dict[str, str]:
    """Pin -> name of the lowest pin in its symmetry class (pins whose swap keeps the function)."""
    if ctype in _SYM:
        return _SYM[ctype]
    names = dictlib.techlib().cells[ctype].inputs
    n = len(names)
    tt = {}
    for m in range(1 << n):
        tt[m] = dictlib._gate_tt(ctype, {nm: (m >> b) & 1 for b, nm in enumerate(names)})
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            x = parent[x]
        return x

    for a in range(n):
        for b in range(a + 1, n):
            same = True
            for m in range(1 << n):
                ba, bb = (m >> a) & 1, (m >> b) & 1
                m2 = (m & ~(1 << a) & ~(1 << b)) | (bb << a) | (ba << b)
                if tt[m] != tt[m2]:
                    same = False
                    break
            if same:
                parent[max(find(a), find(b))] = min(find(a), find(b))
    out = {nm: names[find(i)] for i, nm in enumerate(names)}
    _SYM[ctype] = out
    return out


def pin_invariant(g: dictlib.FG, n: str, p: str) -> str:
    k = g.kind[n]
    if k == "lut" and p.startswith("I") and p[1:].isdigit():
        tab, w = g.table[n]
        return lut_label(tab, w, int(p[1:]))
    if k == "gate":
        return gate_classes(g.ctype[n]).get(p, p)
    return p


VARIANTS: dict[str, tuple[int, l14_ident.PinFn, bool]] = {
    "reg": (24, l14_ident.pin_registered, False),
    "cap720": (720, l14_ident.pin_registered, False),
    "pins": (24, pin_invariant, False),
    "cap720+pins": (720, pin_invariant, False),
    "reg+dedupe": (24, l14_ident.pin_registered, True),
    "cap720+pins+dedupe": (720, pin_invariant, True),
}


def run_variant(name: str) -> list[list[Any]]:
    cap, pin, dedupe = VARIANTS[name]
    l14_ident.TIE_CAP = cap
    l14_ident.PIN = pin
    rows = l14_ident.pooled(l14_ident.twins(dedupe))
    return [[name, *r] for r in rows]


def main() -> int:
    names = sys.argv[1:] or list(VARIANTS)
    out: list[list[Any]] = []
    for nm in names:
        out += run_variant(nm)
        print(nm, flush=True)
    r4lib.write_csv(r4lib.OUT / "x14_ident.csv",
                    ["variant", "family", "floor", "n_designs", "ceiling_wl", "collapse_wl",
                     "ceiling_exact"], out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
