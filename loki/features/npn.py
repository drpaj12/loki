"""NPN classes of small truth tables: an exact canonical form for every support size <= 6.

A table is an integer whose bit ``x`` is the output for the input pattern ``x`` (input ``i`` is
bit ``i`` of ``x``). The canonical form is the smallest table in ``N`` intersected with the NPN
orbit, where ``N`` holds the normalised tables (at most half ones; per input the 1-cofactor has
at least as many ones as the 0-cofactor; inputs ordered by non-decreasing 1-cofactor ones).
``N`` is defined by properties of the table alone, so the minimum is the same for every member of
the orbit (L1 spec 6.7 B). The enumeration walks transforms one swap or flip at a time.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cache

from loki.features import NPN_ENUM_MAX as NPN_ENUM_MAX

MAX_WIDTH = 6


@dataclass(frozen=True)
class NpnClass:
    width: int
    table: int
    exact: bool

    @property
    def key(self) -> str:
        return f"{self.width}:{self.table:x}"


_STATS = {"distinct_tables": 0, "worst_enum": 0, "inexact": 0}
_COUNTS: dict[tuple[int, int], int] = {}


def stats() -> dict[str, int]:
    """Counters since import: distinct ``(table, width)`` classified, most transforms one table
    needed, classes that were not exact."""
    return dict(_STATS)


@cache
def _masks(k: int) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    """Per input ``j``: positions with bit ``j`` = 0, and (for ``j < k - 1``) the positions with
    ``x_j = 1, x_{j+1} = 0`` and ``x_j = 0, x_{j+1} = 1``."""
    size = 1 << k
    zero = tuple(sum(1 << x for x in range(size) if not (x >> j) & 1) for j in range(k))
    a = tuple(sum(1 << x for x in range(size) if (x >> j) & 1 and not (x >> (j + 1)) & 1)
              for j in range(k - 1))
    b = tuple(sum(1 << x for x in range(size) if not (x >> j) & 1 and (x >> (j + 1)) & 1)
              for j in range(k - 1))
    return zero, a, b


def _flip(t: int, k: int, j: int) -> int:
    """Negate input ``j``."""
    m = _masks(k)[0][j]
    sh = 1 << j
    return ((t & m) << sh) | ((t >> sh) & m)


def _swap(t: int, k: int, j: int) -> int:
    """Exchange inputs ``j`` and ``j + 1``."""
    _, a, b = _masks(k)
    sh = 1 << j
    return (t & ~(a[j] | b[j])) | ((t & a[j]) << sh) | ((t & b[j]) >> sh)


def _remove_input(table: int, width: int, i: int) -> int:
    """The table without input ``i`` (its 0-cofactor; used when ``i`` is not in the support)."""
    low = (1 << i) - 1
    out = 0
    for y in range(1 << (width - 1)):
        x = ((y & ~low) << 1) | (y & low)
        out |= ((table >> x) & 1) << y
    return out


def shrink_support(table: int, width: int) -> tuple[int, int, tuple[int, ...]]:
    """``(table over the support, its width, kept input positions)``."""
    positions = list(range(width))
    t, w = table, width
    i = 0
    while i < w:
        sh = 1 << i
        m = sum(1 << x for x in range(1 << w) if not (x >> i) & 1)
        if (t & m) == ((t >> sh) & m):
            t = _remove_input(t, w, i)
            w -= 1
            del positions[i]
        else:
            i += 1
    return t, w, tuple(positions)


def apply_transform(
    table: int, width: int, perm: Sequence[int], neg_in: int, neg_out: bool
) -> int:
    """``g(y) = f(z) xor neg_out`` with ``z_j = y_perm[j] xor bit j of neg_in``."""
    out = 0
    for y in range(1 << width):
        z = 0
        for j in range(width):
            z |= (((y >> perm[j]) & 1) ^ ((neg_in >> j) & 1)) << j
        out |= (((table >> z) & 1) ^ int(neg_out)) << y
    return out


def _sjt(n: int) -> list[int]:
    """Adjacent swaps (position ``j`` with ``j + 1``) visiting all ``n!`` permutations."""
    if n <= 1:
        return []
    inner = _sjt(n - 1)
    out: list[int] = []
    down = list(range(n - 2, -1, -1))
    up = list(range(n - 1))
    for idx in range(len(inner) + 1):
        out += down if idx % 2 == 0 else up
        if idx < len(inner):
            out.append(inner[idx] + (1 if idx % 2 == 0 else 0))
    return out


def _combine(seqs: list[list[int]]) -> list[int]:
    """Reflected product of op sequences: one op per step through all combinations."""
    if not seqs:
        return []
    inner = _combine(seqs[1:])
    first = seqs[0]
    out: list[int] = []
    reverse = False
    for step in range(len(first) + 1):
        out += inner[::-1] if reverse else inner
        reverse = not reverse
        if step < len(first):
            out.append(first[step])
    return out


def _gray_bits(t: int) -> list[int]:
    """Bit to flip at each step of the reflected Gray code over ``t`` bits."""
    return [((i & -i).bit_length() - 1) for i in range(1, 1 << t)]


def _enumerate_phase(s: int, k: int) -> tuple[int, int]:
    """Smallest table over the allowed input phases and orders of ``s`` (output phase fixed),
    and the number of tables examined."""
    ones = s.bit_count()
    zero_mask = _masks(k)[0]
    c1 = [ones - (s & zero_mask[i]).bit_count() for i in range(k)]
    tied = [2 * c1[i] == ones for i in range(k)]
    for i in range(k):
        if 2 * c1[i] < ones:
            s = _flip(s, k, i)
            c1[i] = ones - c1[i]
    order = sorted(range(k), key=lambda i: (c1[i], i))
    cur = list(range(k))
    for target in range(k):
        j = cur.index(order[target])
        while j > target:
            s = _swap(s, k, j - 1)
            cur[j - 1], cur[j] = cur[j], cur[j - 1]
            j -= 1
    key = [c1[i] for i in order]
    is_tied = [tied[i] for i in order]
    groups: list[tuple[int, int]] = []
    a = 0
    while a < k:
        b = a
        while b + 1 < k and key[b + 1] == key[a]:
            b += 1
        if b > a:
            groups.append((a, b + 1))
        a = b + 1
    seqs: list[list[int]] = []
    for lo, hi in groups:
        untied_symmetric = not any(is_tied[lo:hi]) and all(
            _swap(s, k, j) == s for j in range(lo, hi - 1)
        )
        if not untied_symmetric:
            seqs.append([lo + op for op in _sjt(hi - lo)])
    swaps = _combine(seqs)
    tied_ids = [p for p in range(k) if is_tied[p]]
    gray = _gray_bits(len(tied_ids))
    total = (len(swaps) + 1) * (len(gray) + 1)
    if total > NPN_ENUM_MAX:
        raise ValueError(f"NPN enumeration of {total} transforms exceeds {NPN_ENUM_MAX}")
    posof = list(range(k))
    arr = list(range(k))
    zero = zero_mask
    best = s
    rev = False
    for step in range(len(swaps) + 1):
        for b in (gray[::-1] if rev else gray):
            p = posof[tied_ids[b]]
            sh = 1 << p
            m = zero[p]
            s = ((s & m) << sh) | ((s >> sh) & m)
            if s < best:
                best = s
        rev = not rev
        if step < len(swaps):
            j = swaps[step]
            s = _swap(s, k, j)
            arr[j], arr[j + 1] = arr[j + 1], arr[j]
            posof[arr[j]] = j
            posof[arr[j + 1]] = j + 1
            if s < best:
                best = s
    return best, total


def _canonical(table: int, k: int) -> tuple[int, int]:
    """Canonical table and transform count for a table whose support is all ``k`` inputs."""
    if k == 0:
        return 0, 1
    size = 1 << k
    ones = table.bit_count()
    half = size // 2
    phases = [False, True] if ones == half else [ones > half]
    full = (1 << size) - 1
    best = -1
    count = 0
    for out_neg in phases:
        cand, n = _enumerate_phase(table ^ full if out_neg else table, k)
        count += n
        if best < 0 or cand < best:
            best = cand
    return best, count


@cache
def npn_class(table: int, width: int) -> NpnClass:
    """The exact NPN class of a table; ``ValueError`` when its support exceeds 6 inputs."""
    t, k, _ = shrink_support(table, width)
    if k > MAX_WIDTH:
        raise ValueError(f"support of {k} inputs exceeds {MAX_WIDTH}")
    canon, count = _canonical(t, k)
    _COUNTS[(table, width)] = count
    _STATS["distinct_tables"] += 1
    _STATS["worst_enum"] = max(_STATS["worst_enum"], count)
    return NpnClass(k, canon, True)


def transforms(table: int, width: int) -> int:
    """How many transforms ``npn_class(table, width)`` examined (the same on every run)."""
    npn_class(table, width)
    return _COUNTS[(table, width)]


def _normalised(t: int, k: int) -> bool:
    """Membership in ``N``: at most half ones, per input the 1-cofactor has at least as many
    ones as the 0-cofactor, and the 1-cofactor counts do not decrease with the input position."""
    ones = t.bit_count()
    if 2 * ones > (1 << k):
        return False
    zero = _masks(k)[0] if k else ()
    prev = -1
    for i in range(k):
        c1 = ones - (t & zero[i]).bit_count()
        if 2 * c1 < ones or c1 < prev:
            return False
        prev = c1
    return True


def npn_brute(table: int, width: int) -> NpnClass:
    """The smallest normalised table over all ``k! 2^k 2`` transforms (the test oracle)."""
    t, k, _ = shrink_support(table, width)
    if k > MAX_WIDTH:
        raise ValueError(f"support of {k} inputs exceeds {MAX_WIDTH}")
    if k == 0:
        return NpnClass(0, 0, True)
    full = (1 << (1 << k)) - 1
    best = -1

    def offer(x: int) -> None:
        nonlocal best
        for y in (x, x ^ full):
            if (best < 0 or y < best) and _normalised(y, k):
                best = y

    if k <= 4:
        for perm in itertools.permutations(range(k)):
            for neg_in in range(1 << k):
                for neg_out in (False, True):
                    offer(apply_transform(t, k, perm, neg_in, neg_out))
        return NpnClass(k, best, True)
    swaps = _combine([_sjt(k)])
    flips = _gray_bits(k)
    s = t
    offer(s)
    rev = False
    for step in range(len(swaps) + 1):
        for b in flips[::-1] if rev else flips:
            s = _flip(s, k, b)
            offer(s)
        rev = not rev
        if step < len(swaps):
            s = _swap(s, k, swaps[step])
            offer(s)
    return NpnClass(k, best, True)


def _table_of(width: int, fn: Callable[[int], int]) -> int:
    return sum(fn(x) << x for x in range(1 << width))


def _named() -> dict[str, NpnClass]:
    def bit(x: int, i: int) -> int:
        return (x >> i) & 1

    tables: dict[str, tuple[int, int]] = {
        "const": (0, 0),
        "buf": (1, _table_of(1, lambda x: x)),
        "and2": (2, _table_of(2, lambda x: int(x == 3))),
        "xor2": (2, _table_of(2, lambda x: bit(x, 0) ^ bit(x, 1))),
        "and3": (3, _table_of(3, lambda x: int(x == 7))),
        "xor3": (3, _table_of(3, lambda x: bit(x, 0) ^ bit(x, 1) ^ bit(x, 2))),
        "maj3": (3, _table_of(3, lambda x: int(x.bit_count() >= 2))),
        "mux2": (3, _table_of(3, lambda x: bit(x, 1) if bit(x, 2) else bit(x, 0))),
        "and4": (4, _table_of(4, lambda x: int(x == 15))),
        "xor4": (4, _table_of(4, lambda x: x.bit_count() & 1)),
        "mux4": (6, _table_of(6, lambda x: bit(x, 2 + (x & 3)))),
    }
    return {name: npn_class(t, w) for name, (w, t) in tables.items()}


NAMED: dict[str, NpnClass] = _named()
_BY_CLASS = {(c.width, c.table): name for name, c in NAMED.items()}


def class_name(c: NpnClass) -> str:
    """The ``NAMED`` key of a class, or ``"other"``."""
    return _BY_CLASS.get((c.width, c.table), "other")
