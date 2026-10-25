"""Verilog templates of the round-4 corpus: one function per family.

Each ``gen_<family>(p, rnd)`` returns the text of one module ``top`` (Verilog-2005, no latches, no
``initial``). ``p`` is the parameter dict of ``regions.REGIONS[family]``; ``rnd`` supplies the
design's own randomness (transition tables, constants, operation choices). Output is a pure
function of ``(p, seed)``.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

Params = dict[str, Any]


def clog2(n: int) -> int:
    """Smallest ``k >= 1`` with ``2**k >= n``."""
    k = 1
    while (1 << k) < n:
        k += 1
    return k


def rng(w: int) -> str:
    return f"[{w - 1}:0]"


def seq(reset: str, body: str, rst_body: str, clk: str = "clk") -> str:
    """A clocked block; ``reset`` is none, sync or async (active high ``rst``)."""
    if reset == "none":
        return f"  always @(posedge {clk}) begin\n{body}\n  end\n"
    sens = f"posedge {clk} or posedge rst" if reset == "async" else f"posedge {clk}"
    return (f"  always @({sens}) begin\n    if (rst) begin\n{rst_body}\n    end else begin\n"
            f"{body}\n    end\n  end\n")


def gen_register(p: Params, rnd: random.Random) -> str:
    w, en, rs, src, st = p["width"], p["en"], p["reset"], p["src"], p["style"]
    ports = ["input clk", "input rst", f"input {rng(w)} d", f"input {rng(w)} d2", "input sel",
             "input en", f"output reg {rng(w)} q"]
    nxt = "(sel ? d2 : d)" if src == "mux2" else "d"
    rv = f"{w}'d0" if p["rv"] == 0 else f"{{{w}{{1'b1}}}}"
    out = f"module top({', '.join(ports)});\n"
    if st == "nextstate":
        out += f"  reg {rng(w)} nq;\n  always @* begin\n    nq = q;\n"
        out += f"    if (en) nq = {nxt};\n" if en else f"    nq = {nxt};\n"
        out += "  end\n"
        out += seq(rs, "      q <= nq;", f"      q <= {rv};")
    elif st == "ternary":
        rhs = f"en ? {nxt} : q" if en else nxt
        out += seq(rs, f"      q <= {rhs};", f"      q <= {rv};")
    else:
        body = f"      if (en) q <= {nxt};" if en else f"      q <= {nxt};"
        out += seq(rs, body, f"      q <= {rv};")
    return out + "endmodule\n"


def gen_counter(p: Params, rnd: random.Random) -> str:
    w, d, ld, en, rs, st = (p["width"], p["dir"], p["load"], p["en"], p["reset"], p["style"])
    ports = ["input clk", "input rst", f"input {rng(w)} d", "input load", "input en", "input up",
             f"output reg {rng(w)} cnt"]
    step = {"up": "cnt + 1'b1", "down": "cnt - 1'b1", "updown": "(up ? cnt + 1'b1 : cnt - 1'b1)"}[d]
    out = f"module top({', '.join(ports)});\n"
    if st == "nextstate":
        out += f"  reg {rng(w)} nc;\n  always @* begin\n    nc = cnt;\n"
        out += "    if (load) nc = d;\n    else " if ld else "    "
        out += (f"if (en) nc = {step};\n" if en else f"nc = {step};\n") + "  end\n"
        out += seq(rs, "      cnt <= nc;", f"      cnt <= {w}'d0;")
    elif st == "ternary":
        rhs = f"{step}" if not en else f"en ? {step} : cnt"
        if ld:
            rhs = f"load ? d : ({rhs})"
        out += seq(rs, f"      cnt <= {rhs};", f"      cnt <= {w}'d0;")
    else:
        lines = []
        if ld:
            lines.append("      if (load) cnt <= d;")
        if en:
            lines.append(("      else " if ld else "      ") + f"if (en) cnt <= {step};")
        else:
            lines.append(("      else " if ld else "      ") + f"cnt <= {step};")
        out += seq(rs, "\n".join(lines), f"      cnt <= {w}'d0;")
    return out + "endmodule\n"


def _ripple_add(w: int, a: str, b: str, cin: str, s: str, co: str) -> str:
    """Explicit full-adder chain, one statement per bit (the test-only adder style)."""
    lines = []
    for i in range(w):
        c_in = cin if i == 0 else f"c{i}"
        x = f"{a}[{i}] ^ {b}[{i}]"
        lines.append(f"  wire c{i + 1};\n  assign {s}[{i}] = {x} ^ {c_in};\n"
                     f"  assign c{i + 1} = ({a}[{i}] & {b}[{i}]) | ({c_in} & ({x}));")
    lines.append(f"  assign {co} = c{w};")
    return "\n".join(lines) + "\n"


def _arith_top(p: Params, op: str) -> str:
    w, st, reg = p["width"], p["style"], p["reg"]
    cin = p["cin"] if op == "add" else p["bin"]
    cout = p["cout"] if op == "add" else p["bout"]
    ports = ["input clk", f"input {rng(w)} a", f"input {rng(w)} b", "input ci",
             f"output {'reg ' if reg else ''}{rng(w)} s", "output co"]
    out = f"module top({', '.join(ports)});\n"
    out += f"  wire {rng(w)} sw;\n  wire cw;\n"
    sign = "+" if op == "add" else "-"
    c = "ci" if cin else "1'b0"
    if st == "ripple":
        out += _ripple_add(w, "a", "b", c, "sw", "cw")
    elif st == "twos":
        cn = "~ci" if cin else "1'b1"
        out += f"  wire cx;\n  assign {{cx, sw}} = a + ~b + {cn};\n  assign cw = ~cx;\n"
    elif st == "always":
        out += f"  reg {rng(w + 1)} t;\n  always @* t = a {sign} b {sign} {c};\n"
        out += f"  assign sw = t[{w - 1}:0];\n  assign cw = t[{w}];\n"
    else:
        out += f"  assign {{cw, sw}} = a {sign} b {sign} {c};\n"
    if reg:
        out += "  always @(posedge clk) s <= sw;\n"
    else:
        out += "  assign s = sw;\n"
    out += "  assign co = cw;\n" if cout else "  assign co = 1'b0;\n"
    return out + "endmodule\n"


def gen_adder(p: Params, rnd: random.Random) -> str:
    return _arith_top(p, "add")


def gen_subtractor(p: Params, rnd: random.Random) -> str:
    return _arith_top(p, "sub")


_OPS = {"eq": "==", "ne": "!=", "lt": "<", "le": "<=", "gt": ">", "ge": ">="}


def gen_comparator(p: Params, rnd: random.Random) -> str:
    w, op, opd, sg, st = p["width"], _OPS[p["op"]], p["operand"], p["signed"], p["style"]
    sgn = "signed " if sg else ""
    ports = ["input clk", f"input {sgn}{rng(w)} a"]
    if opd == "var":
        ports.append(f"input {sgn}{rng(w)} b")
        rhs = "b"
    else:
        k = rnd.randrange(1, 1 << w)
        rhs = f"{w}'d{k}"
    ports.append("output y")
    out = f"module top({', '.join(ports)});\n"
    if st == "always":
        out += f"  reg r;\n  always @* begin\n    if (a {op} {rhs}) r = 1'b1;\n    else r = 1'b0;\n"
        out += "  end\n  assign y = r;\n"
    elif st == "ternary":
        out += f"  assign y = (a {op} {rhs}) ? 1'b1 : 1'b0;\n"
    else:
        out += f"  assign y = (a {op} {rhs});\n"
    return out + "endmodule\n"


def gen_shifter(p: Params, rnd: random.Random) -> str:
    w, d, amt, reg, st = p["width"], p["dir"], p["amount"], p["reg"], p["style"]
    sh = clog2(w)
    barrel = amt == "barrel"
    ports = ["input clk", f"input {'signed ' if d == 'asr' else ''}{rng(w)} a"]
    if barrel:
        ports.append(f"input {rng(sh)} sh")
    ports.append(f"output {'reg ' if reg else ''}{rng(w)} y")
    out = f"module top({', '.join(ports)});\n  wire {rng(w)} yw;\n"
    opr = {"left": "<<", "right": ">>", "asr": ">>>"}[d]
    if barrel and st == "stages":
        prev = "a"
        for i in range(sh):
            k = 1 << i
            if d == "left":
                sft = f"{{{prev}[{w - 1 - k}:0], {k}'b0}}" if k < w else f"{w}'d0"
            elif d == "right":
                sft = f"{{{k}'b0, {prev}[{w - 1}:{k}]}}" if k < w else f"{w}'d0"
            else:
                sft = (f"{{{{{k}{{{prev}[{w - 1}]}}}}, {prev}[{w - 1}:{k}]}}" if k < w
                       else f"{{{w}{{{prev}[{w - 1}]}}}}")
            out += f"  wire {rng(w)} st{i} = sh[{i}] ? {sft} : {prev};\n"
            prev = f"st{i}"
        out += f"  assign yw = {prev};\n"
    elif barrel:
        out += f"  assign yw = a {opr} sh;\n"
    else:
        k = {"c1": 1, "c2": 2, "c3": 3, "c5": 5}[amt]
        k = min(k, w - 1)
        out += f"  assign yw = a {opr} {k};\n"
    out += "  always @(posedge clk) y <= yw;\n" if reg else "  assign y = yw;\n"
    return out + "endmodule\n"


def gen_mux(p: Params, rnd: random.Random) -> str:
    n, w, kind, st = p["ways"], p["width"], p["kind"], p["style"]
    sb = clog2(n)
    ports = [f"input {rng(w)} d{i}" for i in range(n)]
    out_decl = f"output reg {rng(w)} y" if st != "ternary" and st != "index" else \
        f"output {rng(w)} y"
    if kind == "sel":
        ports.append(f"input {rng(sb)} s")
    else:
        ports += [f"input r{i}" for i in range(n - 1)]
    out = f"module top({', '.join(ports + [out_decl])});\n"
    if kind == "sel":
        if st == "ternary":
            expr = f"d{n - 1}"
            for i in range(n - 2, -1, -1):
                expr = f"(s == {sb}'d{i}) ? d{i} : {expr}"
            out += f"  assign y = {expr};\n"
        elif st == "index":
            cat = ", ".join(f"d{i}" for i in range(n - 1, -1, -1))
            pad = (1 << sb) - n
            if pad:
                cat = f"{{{pad}{{{w}'d0}}}}, " + cat if pad > 1 else f"{w}'d0, " + cat
            out += f"  wire [{(1 << sb) * w - 1}:0] bus = {{{cat}}};\n"
            out += f"  assign y = bus[s * {w} +: {w}];\n"
        elif st == "case":
            out += "  always @* begin\n    case (s)\n"
            for i in range(n - 1):
                out += f"      {sb}'d{i}: y = d{i};\n"
            out += f"      default: y = d{n - 1};\n    endcase\n  end\n"
        else:
            out += "  always @* begin\n"
            for i in range(n - 1):
                out += f"    {'else ' if i else ''}if (s == {sb}'d{i}) y = d{i};\n"
            out += f"    else y = d{n - 1};\n  end\n"
    else:
        if st == "ternary":
            expr = f"d{n - 1}"
            for i in range(n - 2, -1, -1):
                expr = f"r{i} ? d{i} : {expr}"
            out += f"  assign y = {expr};\n"
        elif st == "casez":
            out += "  always @* begin\n    casez ({" + ", ".join(
                f"r{i}" for i in range(n - 2, -1, -1)) + "})\n"
            for i in range(n - 1):
                pat = "".join(
                    "1" if j == i else ("?" if j > i else "0") for j in range(n - 2, -1, -1))
                out += f"      {n - 1}'b{pat}: y = d{i};\n"
            out += f"      default: y = d{n - 1};\n    endcase\n  end\n"
        elif st == "case":
            out += f"  always @* begin\n    y = d{n - 1};\n"
            for i in range(n - 2, -1, -1):
                out += f"    if (r{i}) y = d{i};\n"
            out += "  end\n"
        else:
            out += "  always @* begin\n"
            for i in range(n - 1):
                out += f"    {'else ' if i else ''}if (r{i}) y = d{i};\n"
            out += f"    else y = d{n - 1};\n  end\n"
    return out + "endmodule\n"


def _code(enc: str, i: int, n: int) -> tuple[int, str]:
    if enc == "onehot":
        return n, f"{n}'b{1 << i:0{n}b}"
    b = clog2(n)
    v = i ^ (i >> 1) if enc == "gray" else i
    return b, f"{b}'d{v}"


def gen_fsm(p: Params, rnd: random.Random) -> str:
    n, enc, ty, nin, st = p["states"], p["enc"], p["type"], p["nin"], p["style"]
    sw = _code(enc, 0, n)[0]
    nout = 2 if n <= 6 else 3
    ports = ["input clk", "input rst", f"input {rng(nin)} x", f"output reg {rng(nout)} y"]
    out = f"module top({', '.join(ports)});\n  reg {rng(sw)} state, nxt;\n"
    for i in range(n):
        out += f"  localparam S{i} = {_code(enc, i, n)[1]};\n"
    trans: list[list[tuple[int, int]]] = []
    for _ in range(n):
        k = rnd.choice([1, 1, 2])
        conds = rnd.sample(range(1 << nin), min(k, 1 << nin))
        trans.append([(c, rnd.randrange(n)) for c in conds])
    default = [(i + 1) % n if rnd.random() < 0.7 else rnd.randrange(n) for i in range(n)]
    for i in range(n):  # a branch that leads where the default leads is no branch
        trans[i] = [(c, t if t != default[i] else (t + 1) % n) for c, t in trans[i]]
    out += "  always @* begin\n    nxt = state;\n"
    if st == "ifelse":
        for i in range(n):
            out += f"    {'else ' if i else ''}if (state == S{i}) begin\n"
            for j, (c, t) in enumerate(trans[i]):
                out += f"      {'else ' if j else ''}if (x == {nin}'d{c}) nxt = S{t};\n"
            out += f"      else nxt = S{default[i]};\n    end\n"
        out += "    else nxt = S0;\n"
    else:
        out += "    case (state)\n"
        for i in range(n):
            out += f"      S{i}: begin\n"
            for j, (c, t) in enumerate(trans[i]):
                out += f"        {'else ' if j else ''}if (x == {nin}'d{c}) nxt = S{t};\n"
            out += f"        else nxt = S{default[i]};\n      end\n"
        out += "      default: nxt = S0;\n    endcase\n"
    out += "  end\n"
    out += seq("sync", "      state <= nxt;", "      state <= S0;")
    table = [rnd.randrange(1 << nout) for _ in range(n)]
    out += "  always @* begin\n    case (state)\n"
    for i in range(n):
        if ty == "mealy":
            out += (f"      S{i}: y = x[0] ? {nout}'d{table[i]} : "
                    f"{nout}'d{(table[i] + 1) % (1 << nout)};\n")
        else:
            out += f"      S{i}: y = {nout}'d{table[i]};\n"
    out += f"      default: y = {nout}'d0;\n    endcase\n  end\n"
    return out + "endmodule\n"


def gen_regfile(p: Params, rnd: random.Random) -> str:
    d, w, nr, wen, rs, rdreg, st = (p["depth"], p["width"], p["nread"], p["wen"], p["rst"],
                                    p["rdreg"], p["style"])
    ab = clog2(d)
    ports = ["input clk", "input rst", "input we", f"input {rng(ab)} wa", f"input {rng(w)} wd"]
    ports += [f"input {rng(ab)} ra{k}" for k in range(nr)]
    ports += [f"output {'reg ' if rdreg else ''}{rng(w)} rd{k}" for k in range(nr)]
    out = f"module top({', '.join(ports)});\n"
    out += "".join(f"  reg {rng(w)} r{i};\n" for i in range(d))
    cond = "we" if wen else "1'b1"
    rst_body = "\n".join(f"      r{i} <= {w}'d0;" for i in range(d))
    if st == "ifelse":
        body = "\n".join(
            f"      {'else ' if i else ''}if (({cond}) && wa == {ab}'d{i}) r{i} <= wd;"
            for i in range(d))
    else:
        body = (f"      if ({cond}) begin\n        case (wa)\n"
                + "\n".join(f"          {ab}'d{i}: r{i} <= wd;" for i in range(d))
                + "\n          default: ;\n        endcase\n      end")
    out += seq(rs, body, rst_body)
    for k in range(nr):
        out += f"  reg {rng(w)} q{k};\n  always @* begin\n    case (ra{k})\n"
        out += "".join(f"      {ab}'d{i}: q{k} = r{i};\n" for i in range(d))
        out += f"      default: q{k} = {w}'d0;\n    endcase\n  end\n"
        out += (f"  always @(posedge clk) rd{k} <= q{k};\n" if rdreg
                else f"  assign rd{k} = q{k};\n")
    return out + "endmodule\n"


def _stage_op(kind: str, src: str, w: int, k: int) -> str:
    return {
        "inc": f"{src} + {w}'d{k}", "xor": f"{src} ^ b", "and": f"{src} & b", "or": f"{src} | b",
        "add": f"{src} + b", "pass": src, "not": f"~{src}",
    }[kind]


def gen_pipeline(p: Params, rnd: random.Random) -> str:
    n, w, en, rs, st = p["stages"], p["width"], p["en"], p["reset"], p["style"]
    ops = [rnd.choice(["inc", "xor", "and", "or", "add", "pass", "not"]) for _ in range(n)]
    ks = [rnd.randrange(1, 1 << min(w, 4)) for _ in range(n)]
    ports = ["input clk", "input rst", "input en", f"input {rng(w)} din", f"input {rng(w)} b",
             f"output {rng(w)} dout"]
    out = f"module top({', '.join(ports)});\n"
    srcs = ["din"] + [f"r{i}" for i in range(n - 1)]
    guard = "if (en) " if en else ""
    if st == "vector":
        out += f"  reg [{n * w - 1}:0] v;\n"
        parts = [_stage_op(ops[i], srcs[i].replace(f"r{i - 1}", f"v[{i * w - 1}:{(i - 1) * w}]")
                           if i else "din", w, ks[i]) for i in range(n)]
        out += seq(rs, f"      {guard}v <= {{{', '.join(reversed(parts))}}};",
                   f"      v <= {n * w}'d0;")
        out += f"  assign dout = v[{n * w - 1}:{(n - 1) * w}];\n"
        return out + "endmodule\n"
    out += "".join(f"  reg {rng(w)} r{i};\n" for i in range(n))
    stmts = [f"      {guard}r{i} <= {_stage_op(ops[i], srcs[i], w, ks[i])};" for i in range(n)]
    rsts = [f"      r{i} <= {w}'d0;" for i in range(n)]
    if st == "one":
        out += seq(rs, "\n".join(stmts), "\n".join(rsts))
    else:
        for s_, r_ in zip(stmts, rsts, strict=True):
            out += seq(rs, s_, r_)
    return out + f"  assign dout = r{n - 1};\nendmodule\n"


def gen_dpfsm(p: Params, rnd: random.Random) -> str:
    w, n, op, st = p["width"], p["states"], p["op"], p["style"]
    sb = clog2(n)
    ports = ["input clk", "input rst", "input start", f"input {rng(w)} x", "output done",
             f"output reg {rng(w)} acc"]
    out = f"module top({', '.join(ports)});\n  reg {rng(sb)} state, nxt;\n"
    hold = [rnd.choice(["start", "x[0]", "~x[0]"]) for _ in range(n)]
    out += "  always @* begin\n    nxt = state;\n"
    if st == "ifelse":
        for i in range(n):
            nxt = 0 if i == n - 1 else i + 1
            out += (f"    {'else ' if i else ''}if (state == {sb}'d{i}) begin\n"
                    f"      if ({hold[i] if i == 0 else 'start | ' + hold[i]}) nxt = {sb}'d{nxt};\n"
                    "    end\n")
    else:
        out += "    case (state)\n"
        for i in range(n):
            nxt = 0 if i == n - 1 else i + 1
            out += (f"      {sb}'d{i}: if ({hold[i] if i == 0 else 'start | ' + hold[i]}) "
                    f"nxt = {sb}'d{nxt};\n")
        out += "      default: nxt = 0;\n    endcase\n"
    out += "  end\n"
    out += seq("sync", "      state <= nxt;", f"      state <= {sb}'d0;")
    sym = {"add": "+", "sub": "-", "xor": "^"}[op]
    out += seq("sync",
               f"      if (state == {sb}'d1) acc <= x;\n"
               f"      else if (state == {sb}'d{min(2, n - 1)}) acc <= acc {sym} x;",
               f"      acc <= {w}'d0;")
    out += f"  assign done = (state == {sb}'d{n - 1});\nendmodule\n"
    return out


def gen_alu(p: Params, rnd: random.Random) -> str:
    n, w, reg, st = p["ops"], p["width"], p["reg"], p["style"]
    pool = ["a + b", "a - b", "a & b", "a | b", "a ^ b", "a << 1", "~a", "a + 1"]
    ops = rnd.sample(pool, n)
    ob = clog2(n)
    ports = ["input clk", f"input {rng(w)} a", f"input {rng(w)} b", f"input {rng(ob)} op",
             f"output {'reg ' if reg else ''}{rng(w)} y"]
    out = f"module top({', '.join(ports)});\n  reg {rng(w)} r;\n  always @* begin\n"
    if st == "case":
        out += "    case (op)\n"
        out += "".join(f"      {ob}'d{i}: r = {o};\n" for i, o in enumerate(ops[:-1]))
        out += f"      default: r = {ops[-1]};\n    endcase\n"
    elif st == "ifelse":
        for i, o in enumerate(ops[:-1]):
            out += f"    {'else ' if i else ''}if (op == {ob}'d{i}) r = {o};\n"
        out += f"    else r = {ops[-1]};\n"
    else:
        expr = ops[-1]
        for i in range(n - 2, -1, -1):
            expr = f"(op == {ob}'d{i}) ? ({ops[i]}) : ({expr})"
        out += f"    r = {expr};\n"
    out += "  end\n"
    out += "  always @(posedge clk) y <= r;\n" if reg else "  assign y = r;\n"
    return out + "endmodule\n"


GENERATORS: dict[str, Callable[[Params, random.Random], str]] = {
    "mux": gen_mux, "counter": gen_counter, "adder": gen_adder, "subtractor": gen_subtractor,
    "comparator": gen_comparator, "shifter": gen_shifter, "fsm": gen_fsm,
    "regfile": gen_regfile, "pipeline": gen_pipeline, "register": gen_register,
    "dpfsm": gen_dpfsm, "alu": gen_alu,
}
