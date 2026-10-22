"""Function facts of a truth table (L1 spec 4): support, parity, AND/OR, mux, majority, NPN hash.

A table is an int: bit ``x`` is the output for input pattern ``x`` (input ``i`` is bit ``i`` of
``x``), ``width`` inputs. Counts such as ``ones`` are taken over the function projected onto its
support, so a dummy input never changes a fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from itertools import combinations

MUX_SELECT_MAX = 3


@dataclass(frozen=True)
class MuxFact:
    """``leaves[v]`` is the data input chosen when select input ``j`` reads bit ``j`` of ``v``."""

    select: tuple[int, ...]
    leaves: tuple[int, ...]


@dataclass(frozen=True)
class FnFacts:
    support: tuple[int, ...]
    ones: int
    parity: int
    and_like: bool
    or_like: bool
    mux: MuxFact | None
    maj3: bool


def cofactor(table: int, width: int, var: int, value: int) -> int:
    """The table with input ``var`` fixed to ``value``; same width, ignores ``var``."""
    out = 0
    for x in range(1 << width):
        y = (x | (1 << var)) if value else (x & ~(1 << var))
        out |= ((table >> y) & 1) << x
    return out


def _support(table: int, width: int) -> tuple[int, ...]:
    return tuple(
        v for v in range(width) if cofactor(table, width, v, 0) != cofactor(table, width, v, 1)
    )


def _project(table: int, width: int, support: tuple[int, ...]) -> int:
    """The function over its support inputs only (support input ``j`` is bit ``j``)."""
    out = 0
    for y in range(1 << len(support)):
        x = 0
        for j, v in enumerate(support):
            x |= ((y >> j) & 1) << v
        out |= ((table >> x) & 1) << y
    return out


def _xor_table(k: int) -> int:
    return sum(1 << y for y in range(1 << k) if bin(y).count("1") & 1)


def _parity(small: int, k: int) -> int:
    if k < 2:
        return 0
    odd = _xor_table(k)
    full = (1 << (1 << k)) - 1
    return 1 if small == odd else -1 if small == odd ^ full else 0


def _literal(table: int, width: int, exclude: frozenset[int]) -> int | None:
    """The input ``u`` (not in ``exclude``) whose positive literal ``table`` is, else None."""
    for u in range(width):
        if u not in exclude and table == _literal_table(u, width):
            return u
    return None


@cache
def _literal_table(var: int, width: int) -> int:
    return sum(1 << x for x in range(1 << width) if (x >> var) & 1)


def _mux(table: int, width: int, support: tuple[int, ...]) -> MuxFact | None:
    for size in range(1, MUX_SELECT_MAX + 1):
        for sel in combinations(support, size):
            leaves = _mux_leaves(table, width, sel)
            if leaves is not None:
                return MuxFact(sel, leaves)
    return None


def _mux_leaves(table: int, width: int, sel: tuple[int, ...]) -> tuple[int, ...] | None:
    leaves: list[int] = []
    for v in range(1 << len(sel)):
        cof = table
        for j, s in enumerate(sel):
            cof = cofactor(cof, width, s, (v >> j) & 1)
        leaf = _literal(cof, width, frozenset(sel))
        if leaf is None or leaf in leaves:
            return None
        leaves.append(leaf)
    return tuple(leaves)


@cache
def _maj3_tables() -> frozenset[int]:
    out: set[int] = set()
    for mask in range(8):
        base = sum(
            1 << y for y in range(8) if bin((y ^ mask) & 7).count("1") >= 2
        )
        out.update((base, base ^ 0xFF))
    return frozenset(out)


@cache
def facts(table: int, width: int) -> FnFacts:
    """The facts of one function (cached by ``(table, width)``)."""
    support = _support(table, width)
    k = len(support)
    small = _project(table, width, support)
    ones = small.bit_count()
    rows = 1 << k
    return FnFacts(
        support=support,
        ones=ones,
        parity=_parity(small, k),
        and_like=k >= 2 and ones == 1,
        or_like=k >= 2 and ones == rows - 1,
        mux=_mux(table, width, support),
        maj3=k == 3 and small in _maj3_tables(),
    )


def _raw_sig(small: int, k: int) -> tuple[int, ...]:
    pairs = []
    for v in range(k):
        c0 = cofactor(small, k, v, 0)
        c1 = cofactor(small, k, v, 1)
        n0 = (c0 & _half_mask(k, v, 0)).bit_count()
        n1 = (c1 & _half_mask(k, v, 1)).bit_count()
        pairs.append(tuple(sorted((n0, n1))))
    flat = [n for pair in sorted(pairs) for n in pair]
    return (k, small.bit_count(), *flat)


@cache
def _half_mask(k: int, var: int, value: int) -> int:
    return sum(1 << x for x in range(1 << k) if ((x >> var) & 1) == value)


def npn_sig(table: int, width: int) -> tuple[int, ...]:
    """A signature invariant under input permutation, input negation and output negation.

    ``(support size, min(ones, rows - ones), sorted per-input cofactor-ones pairs, each pair
    sorted)``, flattened. It is a hash for "isomorphic slices", not a canonical form.
    """
    support = _support(table, width)
    k = len(support)
    small = _project(table, width, support)
    full = (1 << (1 << k)) - 1
    return min(_raw_sig(small, k), _raw_sig(small ^ full, k))
