#!/usr/bin/env python3
"""Write glossary.tex and terms.md from one list of terms (single source for both).

Usage (from docs/paper): python3 make_glossary.py [--tex loki.tex]

glossary.tex is the Glossary subsection body of loki.tex (one \\item per line, in dependency
order). Terms marked ``intro`` are defined where the Introduction first uses them (a line tagged
``% def:<key>`` in loki.tex); the glossary repeats them untagged (``% ref:<key>``). terms.md is
rewritten with ``defined at`` read from the ``% def:<key>`` tags and ``first used at`` computed by
check_terms. Standard library only.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_terms as ct  # noqa: E402

JT = r"\cite{jamiesonthesis}"
LT = r"\cite{luuthesis}"

# key, name, definition (LaTeX), depends on (names), search regex, defined in the Introduction
TERMS: list[tuple[str, str, str, list[str], str, bool]] = [
    ("hdl", "HDL", f"Hardware description language: the language, such as Verilog, in which a designer writes a circuit~{JT}.", [], r"\bHDL\b|hardware description language", True),
    ("rtl", "RTL", f"Register-transfer level: the HDL text that says what the registers hold and how they change~{JT}.", ["HDL"], r"\bRTL\b|register-transfer", True),
    ("gate", "gate", f"A basic logic element (AND, OR, NOT); the elaborated design is first written with such primitive gates~{JT}.", [], r"\bgates?\b(?!-)", True),
    ("netlist", "netlist", f"The list of the basic blocks of a design and the nets (wires) that join them; every net is driven by exactly one block~{LT}.", ["gate"], r"\bnetlists?\b", True),
    ("ff", "flip-flop", "A one-bit storage element that keeps its value between clock edges.", [], r"flip-flops?|\bFFs?\b", False),
    ("lut", "LUT", f"Look-up table: a small memory that implements any logic function of $K$ inputs ($K=6$ here). In most FPGAs a LUT and a flip-flop form one basic logic element~{JT}~{LT}.", ["flip-flop"], r"\bLUT6?s?\b|look-up table", False),
    ("techmap", "technology mapping", f"The CAD step that covers the logic of a netlist with the cells the target offers: gates for a gate library, LUTs and flip-flops for an FPGA~{JT}.", ["netlist", "gate", "LUT", "flip-flop"], r"technology.map", False),
    ("prov", "provenance", "The link from each netlist object back to the HDL that produced it.", ["HDL", "netlist"], r"provenance", True),
    ("odin", "Odin III", "The provenance-tracked synthesis front end under Loki; it keeps that link in one intermediate representation.", ["provenance"], r"Odin~?III", True),
    ("key", "answer key / ground truth", "What the synthesis tool recorded about which netlist objects form which HDL construct; the target that recovery is scored against.", ["provenance"], r"answer.key|ground.truth", True),
    ("gb", "Gate-Breaker", "An earlier study in which a language model rewrites gate netlists into RTL; Loki's method baseline.", ["netlist", "RTL"], r"Gate-Breaker", True),
    ("hyp", "hypothesis", "A claim that an experiment can confirm or fail to confirm. In L1 a structure hypothesis is the claim that a set of netlist cells is a structure of some kind (register, adder, mux, ...).", ["netlist"], r"hypothes[ei]s", True),
    ("layers", "L0 / L1 / L2", "Loki's three layers: L0 labelled datasets, L1 a Bayesian flow over structure hypotheses, L2 graph analysis.", ["answer key / ground truth", "hypothesis"], r"\bL0\b|\bL1\b|\bL2\b", True),
    ("quart", "quartile", "One quarter of the benchmark designs ordered by Gate-Breaker's complexity score (Q1 simplest, Q4 most complex).", ["Gate-Breaker"], r"quartile", False),
    ("astcfg", "AST / CFG similarity", "How alike two RTL texts are by subtree overlap of the syntax trees (AST) and by a kernel on the control-flow graphs (CFG); Gate-Breaker's measures of a recovered text against its reference.", ["RTL", "Gate-Breaker"], r"\bAST\b|\bCFG\b", False),
    ("micro", "micro designs", "The 68 small synthesizable RTL designs (counters, registers, arithmetic, ALUs, muxes, comparators, small state machines) used as the first benchmark.", ["RTL"], r"micro (suite|designs?)|micro-", False),
    ("veval", "VerilogEval references", "The 156 reference RTL designs of the VerilogEval spec-to-RTL set; the second benchmark.", ["RTL"], r"VerilogEval", False),
    ("floor", "floor", "The abstraction level and technology mapping at which a design is cut and written as the netlist to reconstruct (f1-k6, f1-earch, f2, f3).", ["netlist", "technology mapping"], r"\bfloors?\b|\bf1-|\bf2\b|\bf3\b", False),
    ("renamed", "renamed-instance protocol", "Rename every identifier through one shared permutation, run the pipeline, map the tokens back: equal results show that the pipeline does not use names.", ["floor"], r"renamed", False),
    ("det", "detector", "A plug-in that proposes structure hypotheses for a netlist and reports features of them, never a likelihood.", ["hypothesis"], r"detectors?", False),
    ("cal", "calibration", "Fitting priors and likelihood ratios on a training split so that predicted probabilities match observed rates.", ["detector"], r"calibrat", False),
    ("ece", "ECE", "Expected calibration error: the average gap between predicted probability and observed match rate over ten bins.", ["calibration"], r"\bECE\b", False),
    ("prover", "prover", "An engine (cone check, truth table, transfer) that proves a structure hypothesis equal to the netlist; a proof makes it near certain.", ["hypothesis"], r"prover|proof", False),
    ("count", "count / match (scoring)", "A hypothesis is counted when it is committed or has probability at least 0.5; it matches an answer-key instance by an overlap rule (Section~\\ref{sec:eval}).", ["hypothesis", "answer key / ground truth"], r"\bcounted\b|\bmatched\b|\bmatches\b", False),
    ("prf", "precision / recall / F1", "Precision is the share of counted hypotheses that match; recall is the share of answer-key instances matched; F1 is their harmonic mean.", ["count / match (scoring)"], r"precision|recall|(?<![\w-])F1(?![\w-])", False),
    ("macro", "macro-F1 / micro-F1", "F1 averaged over the kinds of structure (macro) or pooled over all instances (micro).", ["precision / recall / F1"], r"macro-F1|micro-F1", False),
    ("louv", "Louvain / modularity / NMI", "Louvain is a community-detection method; modularity scores how dense the clusters are; NMI scores the agreement of a clustering with the known module hierarchy.", ["netlist", "answer key / ground truth"], r"Louvain|modularity|\bNMI\b", False),
    ("gnn", "GNN and 1-WL baseline", "A graph neural network (GNN) labels each netlist node from its neighbours; the 1-WL baseline is colour refinement, whose distinguishing power a message-passing GNN cannot exceed.", ["netlist"], r"\bGNN|1-WL", False),
    ("word", "word", "A group of cells that act as one multi-bit signal (a register, a datapath operator, a bus).", ["netlist"], r"\bwords?\b", False),
    ("opf1", "operator type-F1", "F1 of the recovered word-level operator types (adder, mux, comparator, ...) against the answer key's operators.", ["precision / recall / F1", "word"], r"operator (type-)?F1", False),
    ("frag", "fragment", "A wrong-looking candidate that is in fact part of a real construct.", ["word", "detector"], r"fragment", False),
    ("wf", "word-first detector", "A detector that first groups flip-flops into register words by shared clock, enable and reset, then builds the rest around them.", ["word", "detector", "flip-flop"], r"word-first|wordfirst", False),
    ("dana", "DANA (through HAL)", "A published method, run through the HAL framework, that groups flip-flops into register words from their shared control nets and the dataflow between them.", ["word", "flip-flop"], r"DANA|\bHAL\b", False),
    ("tests", "McNemar / Wilcoxon test", "An exact paired test on discordant pairs; a paired rank test.", [], r"McNemar|Wilcoxon", False),
    ("corpus", "synthetic corpus", "A seeded generator's 1200 labelled idiom designs (twelve families) with train, iid and ood splits.", ["floor"], r"synthetic corpus|\bcorpus\b", False),
    ("dict", "signature dictionary", "A table from a cell's cone class and WL colour to the construct it usually is, mined from the synthetic corpus.", ["synthetic corpus"], r"dictionary", False),
    ("d14", "D14 provenance map", "Odin III's version-2 name map: per object, the source-statement units it blends, and labelled join records.", ["provenance"], r"D14|name map|prov-map", False),
    ("unit", "unit, separable, lost", "A unit is the statement-level anchor of a construct; it is separable while some object has exactly that unit set, and lost at the first later snapshot where none has.", ["D14 provenance map"], r"separable|unit set|statement-level", False),
    ("nullm", "random-set null / persistence null", "The random-set null draws random unit sets of the real sizes at each pass; the persistence null starts from the objects of the previous snapshot and merges at random until the real object count is reached.", ["unit, separable, lost"], r"random-set null|persistence null|persistence-free", False),
    ("arms", "LLM pilot arms A, B, C", "Arm A: gate netlist; arm B: netlist plus Loki hints; arm C: interface line only (memorisation control).", ["Gate-Breaker"], r"\barms?[~ ]?[ABC]\b", False),
]


def write_glossary() -> None:
    """Write glossary.tex."""
    lines = ["% Generated by make_glossary.py from the term list; do not edit by hand.\n",
             "\\begingroup\\small\n"]
    for key, name, definition, _deps, _rx, intro in TERMS:
        tag = f"% ref:{key}" if intro else f"% def:{key}"
        lines.append(f"\\par\\noindent\\textbf{{{name}.}} {definition} {tag}\n")
    lines.append("\\endgroup\n")
    (HERE / "glossary.tex").write_text("".join(lines), encoding="utf-8", newline="\n")


def tag_lines(tex: Path) -> dict[str, str]:
    """Map each ``% def:<key>`` tag to ``file:line`` over loki.tex and the inputs."""
    found: dict[str, str] = {}
    base = tex.parent

    def walk(path: Path) -> None:
        rel = path.relative_to(base).as_posix()
        for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            m = re.search(r"%\s*def:(\w+)", raw)
            if m and m.group(1) not in found:
                found[m.group(1)] = f"{rel}:{number}"
            inp = re.search(r"\\input\{([^}]+)\}", raw)
            if inp and not raw.lstrip().startswith("%"):
                name = inp.group(1)
                target = base / (name if name.endswith(".tex") else name + ".tex")
                if target.is_file() and not name.startswith(("IMAGE/", "gen/")):
                    walk(target)

    walk(tex)
    return found


def write_terms(tex: Path) -> None:
    """Write terms.md."""
    tags = tag_lines(tex)
    lines = ct.flatten(tex)
    rows = []
    for key, name, definition, deps, rx, _intro in TERMS:
        term = ct.Term(name, definition, tags.get(key, "none"), "", deps, rx)
        used = ct.first_use(lines, term)
        first = f"{lines[used].file}:{lines[used].number}" if used is not None else "-"
        plain = re.sub(r"\\cite\{[^}]*\}|~", " ", definition).replace("\\ref{sec:eval}", "6.1")
        rows.append((name, plain.strip(), tags.get(key, "none"), first, "; ".join(deps) or "-", rx))
    head = [
        "# Terms for the Loki III paper (Background and Methodology order)\n",
        "\n",
        "Generated by `make_glossary.py` (the same list writes `glossary.tex`). Ordered so that every "
        "term depends only on terms above it. `defined at` is the line tagged `% def:<key>` in the "
        "paper; `first used at` is where the term first occurs outside the abstract; `search` is the "
        "regular expression the checker uses.\n",
        "Check with `python3 docs/paper/check_terms.py --tex docs/paper/loki.tex` "
        "(the abstract is exempt).\n",
        "| term | definition | defined at | first used at | depends on | search |\n",
        "|---|---|---|---|---|---|\n",
    ]
    body = [
        "| " + " | ".join(c.replace("|", "\\|") if i != 5 else f"`{c.replace('|', chr(92) + '|')}`"
                           for i, c in enumerate(r)) + " |\n"
        for r in rows
    ]
    (HERE / "terms.md").write_text("".join(head + body), encoding="utf-8", newline="\n")


def main() -> None:
    """Entry point."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--tex", type=Path, default=HERE / "loki.tex")
    args = ap.parse_args()
    write_glossary()
    write_terms(args.tex.resolve())


if __name__ == "__main__":
    main()
