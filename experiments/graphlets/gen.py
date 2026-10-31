"""RTL generators of the graphlet pattern library: widths 1..32 (any width for live runs).

``instances(widths)`` yields ``Inst`` records; ``verilog(inst)`` gives module ``top``.
Patterns: counter, shift, lfsr, register, timer, regfile, fsm, glue (see EXPERIMENT.md).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

TOP = "top"
WIDTHS = tuple(range(1, 33))
DEPTHS = (2, 4, 8, 16)
ENCODINGS = ("binary", "onehot", "gray")

# Fibonacci LFSR taps, Xilinx XAPP052 table (stage numbers, 1 = first stage).
TAPS: dict[int, tuple[int, ...]] = {
    2: (2, 1), 3: (3, 2), 4: (4, 3), 5: (5, 3), 6: (6, 5), 7: (7, 6), 8: (8, 6, 5, 4),
    9: (9, 5), 10: (10, 7), 11: (11, 9), 12: (12, 6, 4, 1), 13: (13, 4, 3, 1),
    14: (14, 5, 3, 1), 15: (15, 14), 16: (16, 15, 13, 4), 17: (17, 14), 18: (18, 11),
    19: (19, 6, 2, 1), 20: (20, 17), 21: (21, 19), 22: (22, 21), 23: (23, 18),
    24: (24, 23, 22, 17), 25: (25, 22), 26: (26, 6, 2, 1), 27: (27, 5, 2, 1), 28: (28, 25),
    29: (29, 27), 30: (30, 6, 4, 1), 31: (31, 28), 32: (32, 22, 2, 1),
}

# Live-run taps above 32 (XAPP052 table, period not simulated: 2**33 steps is too long to check).
TAPS_LIVE: dict[int, tuple[int, ...]] = {33: (33, 20), 48: (48, 47, 21, 20), 64: (64, 63, 61, 60)}

VARIANTS: dict[str, tuple[str, ...]] = {
    "counter": ("up", "down", "updown", "upload"),
    "shift": ("serial", "parload"),
    "lfsr": ("fib",),
    "register": ("plain", "enable", "enrst"),
    "timer": ("plain", "enable"),
    "regfile": ("1w1r",),
    "fsm": tuple(ENCODINGS),
    "glue": ("mux2", "bitops", "eq"),
}


@dataclass(frozen=True)
class Inst:
    pattern: str
    variant: str
    width: int  # bits; for fsm the state count
    depth: int = 0  # regfile words, else 0

    @property
    def name(self) -> str:
        d = f"_d{self.depth}" if self.depth else ""
        return f"{self.pattern}_{self.variant}{d}_w{self.width:03d}"


def instances(widths: tuple[int, ...] = WIDTHS, patterns: tuple[str, ...] | None = None
              ) -> Iterator[Inst]:
    for pat, variants in VARIANTS.items():
        if patterns and pat not in patterns:
            continue
        for v in variants:
            for w in widths:
                if pat == "lfsr" and w not in TAPS and w <= 32:
                    continue
                if pat == "fsm" and w < 2:
                    continue
                if pat == "lfsr" and w > 32:
                    continue
                for d in (DEPTHS if pat == "regfile" else (0,)):
                    yield Inst(pat, v, w, d)


def taps_of(w: int) -> tuple[int, ...]:
    if w in TAPS:
        return TAPS[w]
    if w in TAPS_LIVE:
        return TAPS_LIVE[w]
    raise ValueError(f"no LFSR tap entry for width {w} (live runs need a tap source)")


def _rng(w: int) -> str:
    return f"[{w - 1}:0]" if w > 1 else ""


def _counter(i: Inst) -> str:
    w, r = i.width, _rng(i.width)
    ins = {"up": "", "down": "", "updown": "input up,", "upload": "input load, input "
           + f"{r} d,"}[i.variant]
    body = {"up": "q <= q + 1'b1;", "down": "q <= q - 1'b1;",
            "updown": "if (up) q <= q + 1'b1; else q <= q - 1'b1;",
            "upload": "if (load) q <= d; else q <= q + 1'b1;"}[i.variant]
    return (f"module {TOP}(input clk, input rst, {ins} output reg {r} q);\n"
            f"  always @(posedge clk) begin\n    if (rst) q <= {w}'d0; else begin {body} end\n"
            "  end\nendmodule\n")


def _shift(i: Inst) -> str:
    w, r = i.width, _rng(i.width)
    if i.variant == "serial":
        nxt = "sin" if w == 1 else f"{{q[{w - 2}:0], sin}}"
        return (f"module {TOP}(input clk, input rst, input sin, output reg {r} q);\n"
                f"  always @(posedge clk) begin\n    if (rst) q <= {w}'d0; else q <= {nxt};\n"
                "  end\nendmodule\n")
    nxt = "sin" if w == 1 else f"{{q[{w - 2}:0], sin}}"
    return (f"module {TOP}(input clk, input rst, input load, input sin, input {r} d, "
            f"output reg {r} q);\n  always @(posedge clk) begin\n"
            f"    if (rst) q <= {w}'d0; else if (load) q <= d; else q <= {nxt};\n"
            "  end\nendmodule\n")


def _lfsr(i: Inst) -> str:
    w, r = i.width, _rng(i.width)
    fb = " ^ ".join(f"q[{t - 1}]" for t in taps_of(w))
    nxt = "fb" if w == 1 else f"{{q[{w - 2}:0], fb}}"
    return (f"module {TOP}(input clk, input rst, output reg {r} q);\n  wire fb = {fb};\n"
            f"  always @(posedge clk) begin\n    if (rst) q <= {w}'d1; else q <= {nxt};\n"
            "  end\nendmodule\n")


def _register(i: Inst) -> str:
    w, r = i.width, _rng(i.width)
    if i.variant == "plain":
        return (f"module {TOP}(input clk, input {r} d, output reg {r} q);\n"
                "  always @(posedge clk) q <= d;\nendmodule\n")
    if i.variant == "enable":
        return (f"module {TOP}(input clk, input en, input {r} d, output reg {r} q);\n"
                "  always @(posedge clk) if (en) q <= d;\nendmodule\n")
    return (f"module {TOP}(input clk, input rst, input en, input {r} d, output reg {r} q);\n"
            f"  always @(posedge clk) begin\n    if (rst) q <= {w}'d0; else if (en) q <= d;\n"
            "  end\nendmodule\n")


def _timer(i: Inst) -> str:
    w, r = i.width, _rng(i.width)
    en = "input en, " if i.variant == "enable" else ""
    cond = "en && " if i.variant == "enable" else ""
    return (f"module {TOP}(input clk, input rst, {en}input load, input {r} d, output done);\n"
            f"  reg {r} q;\n  assign done = (q == {w}'d0);\n"
            f"  always @(posedge clk) begin\n    if (rst) q <= {w}'d0;\n"
            f"    else if (load) q <= d;\n"
            f"    else if ({cond}q != {w}'d0) q <= q - 1'b1;\n  end\nendmodule\n")


def _regfile(i: Inst) -> str:
    d, r = i.depth, _rng(i.width)
    a = max(1, (d - 1).bit_length())
    return (f"module {TOP}(input clk, input we, input [{a - 1}:0] wa, input [{a - 1}:0] ra, "
            f"input {r} wd, output {r} rd);\n  reg {r} mem [0:{d - 1}];\n"
            f"  always @(posedge clk) if (we) mem[wa] <= wd;\n  assign rd = mem[ra];\nendmodule\n")


def _code(enc: str, k: int, n: int) -> tuple[int, int]:
    """(value, bits) of state k of n in the encoding."""
    if enc == "onehot":
        return 1 << k, n
    bits = max(1, (n - 1).bit_length())
    return (k ^ (k >> 1) if enc == "gray" else k), bits


def _fsm(i: Inst) -> str:
    n, enc = i.width, i.variant
    _, bits = _code(enc, 0, n)
    r = _rng(bits)
    params = "".join(f"  localparam S{k} = {bits}'d{_code(enc, k, n)[0]};\n" for k in range(n))
    cases = "".join(
        f"      S{k}: if (a) st <= S{(k + 1) % n}; else if (b) st <= S0; else st <= S{k};\n"
        for k in range(n))
    return (f"module {TOP}(input clk, input rst, input a, input b, output z);\n{params}"
            f"  reg {r} st;\n  assign z = (st == S{n - 1});\n"
            f"  always @(posedge clk) begin\n    if (rst) st <= S0; else case (st)\n{cases}"
            f"      default: st <= S0;\n    endcase\n  end\nendmodule\n")


def _glue(i: Inst) -> str:
    r = _rng(i.width)
    if i.variant == "mux2":
        return (f"module {TOP}(input s, input {r} a, input {r} b, output {r} y);\n"
                "  assign y = s ? a : b;\nendmodule\n")
    if i.variant == "bitops":
        return (f"module {TOP}(input {r} a, input {r} b, input {r} c, output {r} y);\n"
                "  assign y = (a & b) | (b ^ c);\nendmodule\n")
    return (f"module {TOP}(input {r} a, input {r} b, output y);\n  assign y = (a == b);\n"
            "endmodule\n")


_GEN = {"counter": _counter, "shift": _shift, "lfsr": _lfsr, "register": _register,
        "timer": _timer, "regfile": _regfile, "fsm": _fsm, "glue": _glue}


def verilog(i: Inst) -> str:
    if i.variant not in VARIANTS[i.pattern]:
        raise ValueError(f"unknown variant {i.variant} of {i.pattern}")
    if i.pattern == "lfsr":
        taps_of(i.width)
    return _GEN[i.pattern](i)


def lfsr_period(w: int) -> int:
    """Simulated period of the generated LFSR from state 1 (full period is 2**w - 1)."""
    mask = (1 << w) - 1
    taps = TAPS[w]
    s, n = 1, 0
    while True:
        fb = 0
        for t in taps:
            fb ^= (s >> (t - 1)) & 1
        s = ((s << 1) | fb) & mask
        n += 1
        if s == 1:
            return n
