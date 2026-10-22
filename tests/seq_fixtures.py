"""Small sequential circuits (flip-flops plus LUT logic) for the seqfn and fsm tests."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from tests.re_fixtures import GB, table_of

BitFn = Callable[[int, Sequence[int]], int]


def _bound(fn: BitFn, i: int) -> Callable[[Sequence[int]], int]:
    def bit(v: Sequence[int]) -> int:
        return fn(i, v)

    return bit


def register_bank(
    g: GB, clk: int, k: int, ins_of: Callable[[int, Sequence[int]], list[int]], fn: BitFn
) -> list[int]:
    """``k`` flip-flops; bit ``i`` is a LUT of ``ins_of(i, q)`` computing ``fn(i, inputs)``.
    Returns the Q nets (created before the logic so that feedback works)."""
    qs = [g.net(f"q{i}") for i in range(k)]
    for i in range(k):
        ins = ins_of(i, qs)
        d = g.lut(table_of(len(ins), _bound(fn, i)), ins)
        g.ff(d, clk, qs[i])
    return qs


def value(bits: Sequence[int]) -> int:
    return sum(b << i for i, b in enumerate(bits))


def up_counter(g: GB, clk: int, k: int, en: int | None = None, rst: int | None = None) -> list[int]:
    """Binary counter; ``en`` and ``rst`` (both active high, reset wins) are optional."""
    extra = [n for n in (en, rst) if n is not None]

    def ins_of(i: int, q: Sequence[int]) -> list[int]:
        return [*q[: i + 1], *extra]

    def fn(i: int, v: Sequence[int]) -> int:
        e = 1 if en is None else v[i + 1]
        r = 0 if rst is None else v[-1]
        carry = int(all(v[:i]))
        return 0 if r else v[i] ^ (carry & e)

    return register_bank(g, clk, k, ins_of, fn)


def modulo_counter(g: GB, clk: int, k: int, last: int, wrap: int) -> list[int]:
    """Counts up, goes from ``last`` to ``wrap``."""

    def fn(i: int, v: Sequence[int]) -> int:
        x = value(v)
        nxt = wrap if x == last else (x + 1) & ((1 << k) - 1)
        return (nxt >> i) & 1

    return register_bank(g, clk, k, lambda i, q: list(q), fn)


def down_counter(g: GB, clk: int, k: int) -> list[int]:
    def fn(i: int, v: Sequence[int]) -> int:
        return v[i] ^ int(not any(v[:i]))

    return register_bank(g, clk, k, lambda i, q: list(q[: i + 1]), fn)


def shift_register(g: GB, clk: int, k: int, x: int) -> list[int]:
    qs = [g.net(f"q{i}") for i in range(k)]
    for i in range(k):
        g.ff(x if i == 0 else qs[i - 1], clk, qs[i])
    return qs


def lfsr(g: GB, clk: int, k: int, taps: Sequence[int]) -> list[int]:
    """Fibonacci LFSR: bit 0 takes the XOR of the tap bits, bit ``i`` takes bit ``i - 1``."""
    qs = [g.net(f"q{i}") for i in range(k)]
    fb = qs[taps[0]]
    for t in taps[1:]:
        fb = g.lut(0b0110, (fb, qs[t]))
    for i in range(k):
        g.ff(fb if i == 0 else qs[i - 1], clk, qs[i])
    return qs
