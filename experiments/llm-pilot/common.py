"""Shared paths and constants for the Loki LLM pilot (Gate-Breaker replica).

No absolute home paths live here: the workspace root comes from ``YGG_WS`` or is found by walking up
from this file to the directory that holds ``external/Gate-Breaker-verilog-eval``.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SEED = "yggdrasil-llm-pilot-20261026"
QUARTILES = {"Q1": "low", "Q2": "mid-low", "Q3": "mid-high", "Q4": "high"}
PER_QUARTILE = 10
MAX_PROMPT_BYTES = 40000  # selection filter on dataset prompts only; arm B may exceed it
VE_NAME = "Gate-Breaker-verilog-eval"
VARIANT = "standard"  # decision 12; the single place the variant is set
ARMS = ("A", "B", "C")

SYSTEM_MSG = (
    "You are a skilled Verilog RTL designer who specializes in converting gate-level netlists "
    "back into clean, readable RTL code. You excel at recognizing common circuit patterns and "
    "implementing them in an idiomatic way."
)
SUFFIX = (
    "\nEnclose your code with [BEGIN] and [DONE]. Only output the code snippet\n"
    "and do NOT output anything else.\n"
)
HINTS_PREFACE = (
    "Loki structural hints for the netlist above. Loki is a netlist analysis program (no language "
    "model).\n"
    "Its output follows between the markers. The worked examples above did not carry hints.\n"
    "Net names in the hints are wires and ports of the netlist above, except the names w1, w2, "
    "...:\n"
    "those are helper nets that have no wire of their own; each is defined in the list of helper "
    "nets\n"
    "at the end of the hints, in terms of netlist wires or other helper nets.\n"
    "[LOKI-HINTS-BEGIN]\n"
)
HINTS_POSTFACE = (
    "[LOKI-HINTS-END]\n"
    "Designer prior: designers write RTL from familiar patterns. If a signal looks like a "
    "condition, it\n"
    "probably is one; if a register group looks like an FSM, it probably is one."
)
C_NOTE = (
    "No netlist is given for this problem. Use the interface above and your knowledge of "
    "common designs."
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def workspace() -> Path:
    env = os.environ.get("YGG_WS")
    if env:
        return Path(env)
    for parent in HERE.parents:
        if (parent / "external" / VE_NAME).is_dir():
            return parent
    raise FileNotFoundError("set YGG_WS to the workspace holding external/" + VE_NAME)


def ve_root() -> Path:
    return workspace() / "external" / VE_NAME


def dataset_dir() -> Path:
    return ve_root() / "dataset_netlist-to-rtl"


def prefix_file() -> Path:
    return (ve_root() / "scripts" / "prompt_variants" / VARIANT
            / "verilog-example-prefix_netlist-to-rtl_2-shot.txt")


def run_dir() -> Path:
    """Generated per-call files (prompts, responses, logs); ignored by git."""
    return HERE / "run"


def rank_key(problem: str) -> str:
    return sha256_text(f"{SEED}:{problem}")


def a_first(problem: str) -> bool:
    """Arm order within a problem: A then B when the digest's last hex digit is even."""
    return int(rank_key(problem)[-1], 16) % 2 == 0
