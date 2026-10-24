#!/usr/bin/env python3
"""Write docs/paper/round2-tables.tex from the committed round-2 CSVs.

The file holds the round-2 tables (tab:r2-*), the research-log table (tab:r2-log) and a macro
for every deciding number the prose cites (``\\rt...``), so no number in the paper's round-2
text is typed by hand. The status of each hypothesis is computed here with the decision rules of
EXPERIMENT.md (fixed before the runs). No timestamps and no environment: a rerun reproduces the
file byte for byte.

Usage: paper_tables.py [--out PATH]
"""

from __future__ import annotations

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE.parents[1] / "docs" / "paper" / "round2-tables.tex"
MACROS: dict[str, str] = {}


def rows(name: str) -> list[dict[str, str]]:
    with (HERE / name).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def num(x: str) -> float | None:
    return float(x) if x not in ("", "None") else None


def f3(x: float | None, digits: int = 3) -> str:
    return "--" if x is None else f"{x:.{digits}f}".replace("-", "$-$")


def fi(x: float | int | str) -> str:
    return f"{int(float(x)):,}".replace(",", "{,}")


def macro(name: str, value: str) -> None:
    MACROS[name] = value


def tex(text: str) -> str:
    return text.replace("_", r"\_")


def table(caption: str, label: str, head: list[str], body: list[list[str]], spec: str,
          star: bool = False) -> str:
    env = "table*" if star else "table"
    lines = [rf"\begin{{{env}}}[t]", rf"\caption{{{caption}}}", rf"\label{{{label}}}",
             r"\centering", r"\footnotesize", rf"\begin{{tabular}}{{@{{}}{spec}@{{}}}}",
             r"\toprule", " & ".join(head) + r" \\", r"\midrule"]
    for r in body:
        lines.append(r"\midrule" if r == ["---"] else " & ".join(r) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}", rf"\end{{{env}}}"]
    return "\n".join(lines)


def verdict(status: str) -> str:
    return {"S": "supported", "N": "not supported", "I": "inconclusive"}[status]
