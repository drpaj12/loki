#!/usr/bin/env python3
"""Split the generated *-tables.tex files into one macros file and one file per table.

The generated files (experiments/*/paper_tables.py output) hold the \\newcommand macros that
carry every number and also all tables of a round. The paper prints only the tables that belong
to a kept hypothesis, so each table is written to gen/<label>.tex (label with ':' replaced by
'-') and everything outside the tables to gen/<name>-macros.tex. Standard library only.

Usage (from docs/paper): python3 split_tables.py
"""

from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = ["round2", "round3", "round4", "round5", "round6", "hal"]
BEGIN = re.compile(r"\\begin\{(table\*?)\}")
LABEL = re.compile(r"\\label\{(tab:[^}]+)\}")


def split(name: str) -> list[str]:
    """Write the split files of one generated file; return the table labels in order."""
    src = (HERE / f"{name}-tables.tex").read_text(encoding="utf-8").splitlines(keepends=True)
    macros: list[str] = []
    labels: list[str] = []
    block: list[str] = []
    env = ""
    for line in src:
        if not env:
            m = BEGIN.search(line)
            if m:
                env, block = m.group(1), [line]
            else:
                macros.append(line)
            continue
        block.append(line)
        if line.strip().startswith("\\end{" + env + "}"):
            text = "".join(block)
            lab = LABEL.search(text)
            if lab is None:
                raise SystemExit(f"{name}: table without label")
            labels.append(lab.group(1))
            out = HERE / "gen" / (lab.group(1).replace(":", "-") + ".tex")
            out.write_text(text, encoding="utf-8", newline="\n")
            env = ""
    if env:
        raise SystemExit(f"{name}: unterminated {env}")
    (HERE / "gen" / f"{name}-macros.tex").write_text(
        "".join(macros), encoding="utf-8", newline="\n"
    )
    return labels


def main() -> None:
    """Split every generated file."""
    (HERE / "gen").mkdir(exist_ok=True)
    for name in SOURCES:
        print(name, " ".join(split(name)))


if __name__ == "__main__":
    main()
