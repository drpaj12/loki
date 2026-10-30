"""Prompt text of hints v2 (B2): the pieces of the user message that differ from llm-full.

The system message is the llm-full ``re`` message, byte for byte (md5 checked by the build). What
changes sits in the user message, after the question: for every arm a ``Notes:`` allowance of at
most 10 lines before ``[BEGIN]``; for the hint arms an explanation of the claims and a required
last line ``CLAIMS-USED: ...`` after ``[DONE]``. The scorer reads only between the markers.
"""

from __future__ import annotations

NOTES = (
    "Reply in this format: an optional section starting with the line \"Notes:\" (at most 10 "
    "lines: your reading of the circuit, what its registers and buses are and what its control "
    "signals do), then the module enclosed in [BEGIN] and [DONE]."
)
USED = (
    "After [DONE], write one last line \"CLAIMS-USED:\" followed by the ids of the Loki claims "
    "you relied on, separated by commas (for example \"CLAIMS-USED: h7,h2\"), or "
    "\"CLAIMS-USED: none\"."
)
EXPLAIN_V1 = (
    "How to read the Loki claims. Each claim has an id (such as h7), a confidence (a number from "
    "0 to 1) and a status: committed claims have confidence of at least 0.9; candidates are "
    "unconfirmed guesses that can be wrong. A claim says what a group of signals is (a counter, "
    "a state machine, a bus), not what the designer called it. Use the claims where they help "
    "you and check them against the netlist."
)
EXPLAIN_V2 = (
    "How to read the Loki claims. Each claim has an id (such as h7), a probability p and a "
    "status. p is Loki's calibrated probability that the claim is true of this netlist. "
    "\"proved\" means Loki checked the claim against the netlist logic (a truth table or an "
    "exhaustive simulation of the next-state logic); \"candidate\" means a structural guess that "
    "can be wrong, so check it against the netlist before you rely on it. A claim says what a "
    "group of signals is (a counter, a state machine, a bus), not what the designer called it. "
    "The netlist above carries comments of the form \"// loki h7 ...\" on the gates and ports a "
    "claim covers, so you can see which gates belong to which claim. Use the claims where they "
    "help you."
)
HINTS_PREFACE = (
    "Loki claims for the netlist above. Loki is a netlist analysis program (no language model).\n"
    "Its output follows between the markers. The worked examples above did not carry claims.\n"
    "Net names in the claims are wires and ports of the netlist above.\n"
    "[LOKI-HINTS-BEGIN]\n"
)


def suffix(hints: bool) -> str:
    """The format instruction that replaces the llm-full suffix."""
    return "\n" + NOTES + (" " + USED if hints else "") + " Write nothing else.\n"
