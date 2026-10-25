"""Token description length of a Verilog text (RQ-L14, EXPERIMENT.md "MDL readability")."""

from __future__ import annotations

import math
import re
from collections import Counter

KEYWORDS = frozenset("""module endmodule input output inout wire reg assign always begin end if else
case casez casex endcase default for while integer parameter localparam posedge negedge or and not
xor nand nor xnor buf signed unsigned function endfunction task endtask generate endgenerate
genvar initial""".split())
_COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
_TOKEN = re.compile(
    r"\d*'[sS]?[bBoOdDhH][0-9a-fA-F_xXzZ?]+|\d+|[A-Za-z_][A-Za-z0-9_$]*|<<<|>>>|===|!==|"
    r"<=|>=|==|!=|&&|\|\||<<|>>|~&|~\||~\^|\^~|\*\*|\+:|-:|\S")
_VAL = re.compile(r"(\d*)'[sS]?([bBoOdDhH])([0-9a-fA-F_]+)$")


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(_COMMENT.sub(" ", text))


def kind_of(tok: str) -> str:
    if tok[0].isdigit() or tok[0] == "'":
        return "num"
    if tok[0].isalpha() or tok[0] in "_":
        return "kw" if tok in KEYWORDS else "id"
    return "op"


def num_value(tok: str) -> int:
    m = _VAL.match(tok)
    if not m:
        return int(tok) if tok.isdigit() else 0
    base = {"b": 2, "o": 8, "d": 10, "h": 16}[m.group(2).lower()]
    try:
        return int(m.group(3).replace("_", ""), base)
    except ValueError:
        return 0


class Model:
    """Unigram counts of keyword and operator tokens over training texts."""

    def __init__(self) -> None:
        self.cnt: Counter[str] = Counter()
        self.total = 0

    def add(self, text: str) -> Counter[str]:
        c = Counter(t for t in tokens(text) if kind_of(t) in ("kw", "op"))
        self.cnt.update(c)
        self.total += sum(c.values())
        return c

    def dl(self, text: str, leave_out: Counter[str] | None = None) -> float:
        cnt = self.cnt - leave_out if leave_out is not None else self.cnt
        total = sum(cnt.values())
        vocab = len(cnt) + 1
        bits = 0.0
        seen: set[str] = set()
        for t in tokens(text):
            k = kind_of(t)
            if k in ("kw", "op"):
                bits += -math.log2((cnt[t] + 1) / (total + vocab + 1))
            elif k == "num":
                bits += 2 + math.log2(1 + num_value(t))
            elif t in seen:
                bits += math.log2(max(1, len(seen)))
            else:
                bits += 8.0
                seen.add(t)
        return bits
