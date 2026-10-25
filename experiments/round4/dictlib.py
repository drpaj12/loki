"""Signature dictionary of round 4: cone classes, WL contexts, mining, matcher (RQ-L12b).

See ``EXPERIMENT.md`` (Stage 2). A *floor graph* (:class:`FG`) is read from ``graph.json``; a
signature of a cell is ``(cone class, WL_r)``. The cone class is the canonical class of the Boolean
function of the largest cut of at most ``kmax`` leaves below the cell (exact NPN for up to four
leaves, a cofactor-sorted semi-canonical form for five and six).
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loki.score.gt import SCORED_TYPES, derive_instances
from loki.score.metrics import Pred
from loki.techlib import TechLib, load_techlib

KDICT: tuple[str, ...] = ("ff_en", "ff_srst", "register", "adder", "subtractor", "comparator",
                          "eq_const", "mux", "mux_tree", "counter", "fsm")
ODIN3_ROOT = Path(os.environ.get("ODIN3_ROOT", "odin3"))
MAX_CUTS = 12
COMB = ("lut", "gate")


def h64(obj: object) -> int:
    """Stable 64-bit hash of a repr-able object (independent of PYTHONHASHSEED)."""
    return int.from_bytes(hashlib.blake2b(repr(obj).encode(), digest_size=8).digest(), "big")


_LIB: TechLib | None = None


def techlib() -> TechLib:
    global _LIB
    if _LIB is None:
        _LIB = load_techlib(ODIN3_ROOT / "lib" / "cmos6.o3lib")
    return _LIB


# -- truth tables ------------------------------------------------------------------------------
_PERM_CACHE: dict[int, list[list[int]]] = {}
_NPN_CACHE: dict[tuple[int, int], tuple[int, int]] = {}


def _maps(k: int) -> list[list[int]]:
    """Index maps of every input permutation and input negation (k <= 4)."""
    if k not in _PERM_CACHE:
        out: list[list[int]] = []
        for perm in itertools.permutations(range(k)):
            for neg in range(1 << k):
                m = []
                for i in range(1 << k):
                    j = 0
                    for new_pos, old_pos in enumerate(perm):
                        bit = ((i >> new_pos) & 1) ^ ((neg >> new_pos) & 1)
                        j |= bit << old_pos
                    m.append(j)
                out.append(m)
        _PERM_CACHE[k] = out
    return _PERM_CACHE[k]


def npn_exact(tt: int, k: int) -> int:
    """Smallest truth table over input permutations, input and output negations (k <= 4)."""
    full = (1 << (1 << k)) - 1
    best = full + 1
    for m in _maps(k):
        v = 0
        for i, j in enumerate(m):
            if (tt >> j) & 1:
                v |= 1 << i
        best = min(best, v, v ^ full)
    return best


def _cof(tt: int, k: int, var: int, val: int) -> int:
    return sum(1 for i in range(1 << k) if ((i >> var) & 1) == val and (tt >> i) & 1)


def semi_canonical(tt: int, k: int) -> int:
    """Cofactor-sorted form for k = 5, 6: negate an input when its one-cofactor has more ones,
    order inputs by their sorted cofactor counts, negate the output when more than half ones."""
    keys = []
    neg = 0
    for v in range(k):
        c0, c1 = _cof(tt, k, v, 0), _cof(tt, k, v, 1)
        if c1 > c0:
            neg |= 1 << v
            c0, c1 = c1, c0
        keys.append((c0, c1, v))
    order = [v for _, _, v in sorted(keys)]
    out = 0
    for i in range(1 << k):
        j = 0
        for new_pos, old_pos in enumerate(order):
            bit = ((i >> new_pos) & 1) ^ ((neg >> old_pos) & 1)
            j |= bit << old_pos
        if (tt >> j) & 1:
            out |= 1 << i
    full = (1 << (1 << k)) - 1
    return out ^ full if bin(out).count("1") > (1 << (k - 1)) else out


def reduce_support(tt: int, k: int) -> tuple[int, int]:
    """Drop the inputs the function does not depend on; returns (table, remaining inputs)."""
    deps = []
    for v in range(k):
        dep = any(((tt >> i) & 1) != ((tt >> (i ^ (1 << v))) & 1) for i in range(1 << k))
        if dep:
            deps.append(v)
    if len(deps) == k:
        return tt, k
    out = 0
    for i in range(1 << len(deps)):
        j = 0
        for pos, v in enumerate(deps):
            j |= ((i >> pos) & 1) << v
        if (tt >> j) & 1:
            out |= 1 << i
    return out, len(deps)


def canonical(tt: int, k: int) -> tuple[int, int]:
    """(class table, support size) of a function: exact NPN up to 4 inputs."""
    tt, k = reduce_support(tt, k)
    key = (tt, k)
    if key not in _NPN_CACHE:
        _NPN_CACHE[key] = ((npn_exact(tt, k) if k <= 4 else semi_canonical(tt, k)), k)
    return _NPN_CACHE[key]


# -- floor graph -------------------------------------------------------------------------------
@dataclass
class FG:
    """One floor graph: kinds, cell types, tables, fan-in (pin, src) and fan-out (pin, dst)."""

    kind: dict[str, str] = field(default_factory=dict)
    ctype: dict[str, str] = field(default_factory=dict)
    table: dict[str, tuple[int, int]] = field(default_factory=dict)
    fin: dict[str, list[tuple[str, str, str]]] = field(default_factory=dict)  # (pin, src, net)
    fout: dict[str, list[tuple[str, str, str]]] = field(default_factory=dict)  # (pin, dst, net)
    cells: list[str] = field(default_factory=list)

    def pin_of(self, node: str, pin: str) -> str:
        return "I" if self.kind[node] == "lut" else pin


def load_fg(path: Path) -> FG:
    obj = json.loads(path.read_text(encoding="utf-8"))
    g = FG()
    for n in obj["nodes"]:
        i = str(n["id"])
        g.kind[i] = str(n["kind"])
        g.ctype[i] = str(n["labels"]["cell_type"])
        f = n["features"]
        if n["kind"] == "lut":
            g.table[i] = (int(str(f["lut_table"]), 16) if f["lut_table"] else 0,
                          int(f["lut_width"]))
        g.fin[i] = []
        g.fout[i] = []
        if n["kind"] in ("lut", "gate", "ff", "hard"):
            g.cells.append(i)
    for e in obj["edges"]:
        s, d, p, net = str(e["src"]), str(e["dst"]), str(e["pin"]), str(e["net"])
        g.fin[d].append((p, s, net))
        g.fout[s].append((p, d, net))
    for i in g.fin:
        g.fin[i].sort()
        g.fout[i].sort()
    return g


def _gate_tt(ctype: str, pins: dict[str, int]) -> int | None:
    lib = techlib()
    c = lib.cells.get(ctype)
    if c is None or not c.functions:
        return None
    from loki.techlib import _eval  # the library expression evaluator

    return _eval(c.functions[c.outputs[0]], pins)


class ConeEngine:
    """Cuts and cone classes of a floor graph for a leaf limit ``kmax`` (4 or 6)."""

    def __init__(self, g: FG, kmax: int) -> None:
        self.g, self.kmax = g, kmax
        self.cuts: dict[str, list[frozenset[str]]] = {}
        self._order_cuts()
        self._cls: dict[str, int] = {}

    def _inputs(self, n: str) -> list[str]:
        """Fan-in sources of a combinational node in pin order (lut: I0.., gate: A, B)."""
        g = self.g
        if g.kind[n] == "lut":
            w = g.table[n][1]
            by = {p: s for p, s, _ in g.fin[n]}
            return [by.get(f"I{i}", "") for i in range(w)]
        return [s for p, s, _ in sorted(g.fin[n])]

    def _order_cuts(self) -> None:
        g = self.g
        comb = [c for c in g.cells if g.kind[c] in COMB]
        indeg = {c: 0 for c in comb}
        succ: dict[str, list[str]] = {c: [] for c in comb}
        for c in comb:
            for s in self._inputs(c):
                if s in indeg:
                    indeg[c] += 1
                    succ[s].append(c)
        ready = sorted(c for c in comb if indeg[c] == 0)
        while ready:
            n = ready.pop()
            self.cuts[n] = self._cuts_of(n)
            for d in succ[n]:
                indeg[d] -= 1
                if indeg[d] == 0:
                    ready.append(d)

    def _leaf_cuts(self, s: str) -> list[frozenset[str]]:
        return self.cuts.get(s, [frozenset({s})]) if s else [frozenset()]

    def _cuts_of(self, n: str) -> list[frozenset[str]]:
        acc: set[frozenset[str]] = {frozenset()}
        for s in self._inputs(n):
            nxt: set[frozenset[str]] = set()
            child = self._leaf_cuts(s)
            for a in acc:
                for b in child:
                    u = a | b
                    if len(u) <= self.kmax:
                        nxt.add(u)
            acc = nxt
            if not acc:
                break
        out = sorted(acc, key=lambda c: (-len(c), sorted(c)))[:MAX_CUTS]
        return [*out, frozenset({n})]

    def _eval_cone(self, root: str, leaves: list[str]) -> int:
        """Truth table over the sorted ``leaves`` of the cone of ``root``."""
        k = len(leaves)
        full = (1 << (1 << k)) - 1
        val: dict[str, int] = {}
        for pos, lf in enumerate(leaves):
            t = 0
            for i in range(1 << k):
                if (i >> pos) & 1:
                    t |= 1 << i
            val[lf] = t

        def ev(n: str) -> int:
            if n in val:
                return val[n]
            ins = [ev(s) if s else 0 for s in self._inputs(n)]
            if self.g.kind[n] == "lut":
                tab, w = self.g.table[n]
                out = 0
                for m in range(1 << w):
                    if (tab >> m) & 1:
                        term = full
                        for b in range(w):
                            term &= ins[b] if (m >> b) & 1 else ~ins[b] & full
                        out |= term
            else:
                names = techlib().cells[self.g.ctype[n]].inputs
                out = 0
                for m in range(1 << len(names)):
                    bits = {nm: (m >> b) & 1 for b, nm in enumerate(names)}
                    if _gate_tt(self.g.ctype[n], bits):
                        term = full
                        for b in range(len(names)):
                            term &= ins[b] if (m >> b) & 1 else ~ins[b] & full
                        out |= term
            val[n] = out
            return out

        return ev(root)

    def cone_class(self, cell: str) -> int:
        """Class id of the largest cut below ``cell`` (ff: of its data input)."""
        if cell in self._cls:
            return self._cls[cell]
        g = self.g
        root = cell
        feedback = 0
        if g.kind[cell] == "ff":
            d = [s for p, s, _ in g.fin[cell] if p == "D"]
            root = d[0] if d else ""
        if not root or root not in self.cuts:
            res = h64(("leaf", g.kind[cell], g.ctype[cell]))
            self._cls[cell] = res
            return res
        cands = [c for c in self.cuts[root] if c != frozenset({root})]
        if not cands:
            res = h64(("wide", g.kind[cell]))
            self._cls[cell] = res
            return res
        top = max(len(c) for c in cands)
        best: tuple[int, int] | None = None
        for cut in cands:
            if len(cut) != top:
                continue
            leaves = sorted(cut)
            cls = canonical(self._eval_cone(root, leaves), len(leaves))
            if best is None or cls < best:
                best = cls
                feedback = 1 if cell in cut else 0
        res = h64(("cone", g.kind[cell], best, feedback))
        self._cls[cell] = res
        return res


def wl_colors(g: FG, rounds: int) -> list[dict[str, int]]:
    """``rounds + 1`` colourings: WL_0 = (kind, cell type, lut width), then fan-in and fan-out
    multisets keyed by pin class."""
    cur = {i: h64((g.kind[i], g.ctype[i], g.table[i][1] if i in g.table else 0)) for i in g.kind}
    out = [cur]
    for _ in range(rounds):
        nxt = {}
        for i in g.kind:
            fi = sorted((g.pin_of(i, p), cur[s]) for p, s, _ in g.fin[i])
            fo = sorted((g.pin_of(d, p), cur[d]) for p, d, _ in g.fout[i])
            nxt[i] = h64((cur[i], fi, fo))
        cur = nxt
        out.append(cur)
    return out


@dataclass
class Sigs:
    """Signatures of the cells of one floor graph: ``cone[c]`` and ``wl[r][c]``."""

    g: FG
    cone: dict[str, int]
    wl: list[dict[str, int]]

    def key(self, cell: str, r: int) -> tuple[int, int]:
        return (self.cone[cell], self.wl[r][cell])


def signatures(g: FG, kmax: int, rmax: int = 3) -> Sigs:
    eng = ConeEngine(g, kmax)
    cone = {c: eng.cone_class(c) for c in g.cells}
    return Sigs(g, cone, wl_colors(g, rmax))


# -- ground truth ------------------------------------------------------------------------------
def kinds_of_cells(words: dict[str, Any]) -> dict[str, set[str]]:
    """``K(c)``: dictionary kinds with a GT instance containing the cell."""
    out: dict[str, set[str]] = {}
    for inst in derive_instances(words):
        for k in KDICT:
            if inst.type in SCORED_TYPES[k]:
                for c in inst.footprint:
                    out.setdefault(c, set()).add(k)
    return out


# -- dictionary --------------------------------------------------------------------------------
@dataclass
class Dictionary:
    """Per radius r: signature key -> (n cells, Counter of kinds)."""

    kmax: int
    rmax: int = 3
    tab: list[dict[tuple[int, int], tuple[int, Counter[str]]]] = field(default_factory=list)
    cone_tab: dict[int, tuple[int, Counter[str]]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.tab:
            self.tab = [{} for _ in range(self.rmax + 1)]

    def add(self, sg: Sigs, kinds: dict[str, set[str]]) -> None:
        for c in sg.g.cells:
            ks = kinds.get(c, set())
            for r in range(self.rmax + 1):
                n, cnt = self.tab[r].setdefault(sg.key(c, r), (0, Counter()))
                self.tab[r][sg.key(c, r)] = (n + 1, cnt + Counter(ks))
            n2, cnt2 = self.cone_tab.setdefault(sg.cone[c], (0, Counter()))
            self.cone_tab[sg.cone[c]] = (n2 + 1, cnt2 + Counter(ks))

    def fires(self, key: tuple[int, int], r: int, n_min: int = 3,
              theta: float = 0.6) -> set[str]:
        ent = self.tab[r].get(key)
        if ent is None or ent[0] < n_min:
            return set()
        return {k for k, v in ent[1].items() if v / ent[0] >= theta}

    def cone_fires(self, cone: int, n_min: int = 3, theta: float = 0.6) -> set[str]:
        ent = self.cone_tab.get(cone)
        if ent is None or ent[0] < n_min:
            return set()
        return {k for k, v in ent[1].items() if v / ent[0] >= theta}


class _UF:
    def __init__(self) -> None:
        self.p: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


STORAGE_KINDS = frozenset({"ff_en", "ff_srst", "register", "counter", "fsm"})


def match(sg: Sigs, d: Dictionary, r: int, clock_union: bool = False) -> list[Pred]:
    """Candidates of the dictionary on one floor graph: connected components per kind.

    ``clock_union`` (grouping G2): for storage kinds a shared clock net also joins equal-signature
    cells; with it off (G1, the Stage-0 rule) clock pins never join cells."""
    g = sg.g
    label: dict[str, set[str]] = {c: d.fires(sg.key(c, r), r) for c in g.cells}
    preds: list[Pred] = []
    for k in KDICT:
        cells = sorted(c for c in g.cells if k in label[c])
        if not cells:
            continue
        sel = set(cells)
        uf = _UF()
        for c in cells:
            uf.find(c)
        by_net: dict[str, list[str]] = {}
        for c in cells:
            for p, s, net in g.fin[c]:
                if s in sel:
                    uf.union(c, s)
                elif p != "CLK" or (clock_union and k in STORAGE_KINDS):
                    by_net.setdefault(net, []).append(c)
        for readers in by_net.values():
            first: dict[tuple[int, int], str] = {}
            for c in readers:
                key = sg.key(c, r)
                if key in first:
                    uf.union(c, first[key])
                else:
                    first[key] = c
        groups: dict[str, list[str]] = {}
        for c in cells:
            groups.setdefault(uf.find(c), []).append(c)
        for j, root in enumerate(sorted(groups)):
            preds.append(Pred(id=f"d_{k}_{j}", kind=k, cells=frozenset(groups[root]), p=1.0,
                              status="committed", detector="dict"))
    return preds
