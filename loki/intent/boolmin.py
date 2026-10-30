"""Small two-level minimiser (Quine-McCluskey with a greedy cover) for transition conditions.

A condition is a sum of products; a product is a tuple of ``(net, polarity)`` literals. Pure.
"""

from __future__ import annotations

from collections.abc import Sequence

Literal = tuple[int, int]
Product = tuple[Literal, ...]
Cube = tuple[int, int]  # (care mask, value)

MAX_VARS = 8


def _merge(a: Cube, b: Cube) -> Cube | None:
    """The cube covering ``a`` and ``b`` when they differ in exactly one cared bit."""
    if a[0] != b[0]:
        return None
    diff = a[1] ^ b[1]
    if diff == 0 or diff & (diff - 1):
        return None
    return a[0] & ~diff, a[1] & ~diff


def _primes(minterms: Sequence[int], nvars: int) -> list[Cube]:
    full = (1 << nvars) - 1
    level = {(full, m) for m in minterms}
    primes: set[Cube] = set()
    while level:
        used: set[Cube] = set()
        nxt: set[Cube] = set()
        ordered = sorted(level)
        for i, a in enumerate(ordered):
            for b in ordered[i + 1:]:
                m = _merge(a, b)
                if m is not None:
                    nxt.add(m)
                    used.update((a, b))
        primes |= level - used
        level = nxt
    return sorted(primes)


def _covers(cube: Cube, minterm: int) -> bool:
    return (minterm & cube[0]) == cube[1]


def minimise(minterms: Sequence[int], nvars: int) -> list[Cube]:
    """A small set of cubes covering exactly ``minterms`` over ``nvars`` variables."""
    if nvars > MAX_VARS:
        raise ValueError(f"{nvars} variables: more than {MAX_VARS}")
    todo = set(minterms)
    primes = _primes(sorted(todo), nvars)
    chosen: list[Cube] = []
    while todo:
        best = max(primes, key=lambda c: (sum(_covers(c, m) for m in todo),
                                         -bin(c[0]).count("1"), -c[1]))
        chosen.append(best)
        todo = {m for m in todo if not _covers(best, m)}
    return sorted(chosen, key=lambda c: (bin(c[0]).count("1"), c))


def products(minterms: Sequence[int], nets: Sequence[int]) -> tuple[Product, ...]:
    """The condition ``minterms`` (bit ``j`` is the value of ``nets[j]``) as products of literals.

    The empty product (a constant true) is the tuple ``((),)``; no minterm gives ``()``.
    """
    if not minterms:
        return ()
    cubes = minimise(minterms, len(nets))
    out: list[Product] = []
    for care, val in cubes:
        out.append(tuple((nets[j], (val >> j) & 1) for j in range(len(nets)) if (care >> j) & 1))
    return tuple(out)


def render(prods: Sequence[Product], name: dict[int, str]) -> str:
    """``a & ~b | c``; ``always`` for a constant true, ``never`` for none."""
    if not prods:
        return "never"
    if any(not p for p in prods):
        return "always"

    def lit(net: int, pol: int) -> str:
        return name[net] if pol else "~" + name[net]

    return " | ".join(" & ".join(lit(n, p) for n, p in prod) for prod in prods)
