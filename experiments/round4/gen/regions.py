"""Parameter regions of the round-4 corpus: train values and test-only values per family.

A design is *train-region* when every parameter takes a train value; it is *ood* when at least one
parameter takes a test-only value (an unseen width, an unseen coding style, an unseen reset style
and so on). The tables are the corpus specification of ``EXPERIMENT.md``; change them only through
a dated entry there.
"""

from __future__ import annotations

from typing import Any

# family -> parameter -> (train values, test-only values)
Region = dict[str, tuple[list[Any], list[Any]]]

W_TRAIN: list[Any] = [4, 6, 8, 12, 16]
W_TEST: list[Any] = [5, 7, 10, 24]

REGIONS: dict[str, Region] = {
    "mux": {
        "ways": ([2, 3, 4, 6, 8], [5, 7, 16]),
        "width": ([1, 4, 8], [3, 6, 16]),
        "kind": (["sel", "prio"], []),
        "style": (["ternary", "ifelse", "case"], ["index", "casez"]),
    },
    "counter": {
        "width": ([4, 6, 8, 12], [5, 7, 10, 16]),
        "dir": (["up", "down"], ["updown"]),
        "load": ([0, 1], []),
        "en": ([0, 1], []),
        "reset": (["none", "sync"], ["async"]),
        "style": (["ifelse", "ternary"], ["nextstate"]),
    },
    "adder": {
        "width": (W_TRAIN, W_TEST),
        "cin": ([0, 1], []),
        "cout": ([0, 1], []),
        "reg": ([0, 1], []),
        "style": (["assign", "always"], ["ripple"]),
    },
    "subtractor": {
        "width": (W_TRAIN, W_TEST),
        "bin": ([0, 1], []),
        "bout": ([0, 1], []),
        "reg": ([0, 1], []),
        "style": (["assign", "always"], ["twos"]),
    },
    "comparator": {
        "width": (W_TRAIN, W_TEST),
        "op": (["eq", "lt", "gt"], ["ne", "le", "ge"]),
        "operand": (["var", "const"], []),
        "signed": ([0], [1]),
        "style": (["assign", "always"], ["ternary"]),
    },
    "shifter": {
        "width": (W_TRAIN, [7, 10, 24, 32]),
        "dir": (["left", "right"], ["asr"]),
        "amount": (["c1", "c2", "c3", "barrel"], ["c5"]),
        "reg": ([0, 1], []),
        "style": (["op"], ["stages"]),
    },
    "fsm": {
        "states": ([3, 4, 5, 6, 8], [7, 10, 12, 16]),
        "enc": (["binary", "onehot"], ["gray"]),
        "type": (["moore", "mealy"], []),
        "nin": ([1, 2], [3]),
        "style": (["case"], ["ifelse"]),
    },
    "regfile": {
        "depth": ([2, 4, 8], [3, 5, 16]),
        "width": ([4, 8], [6, 12]),
        "nread": ([1, 2], []),
        "wen": ([0, 1], []),
        "rst": (["none", "sync"], ["async"]),
        "rdreg": ([0, 1], []),
        "style": (["case"], ["ifelse"]),
    },
    "pipeline": {
        "stages": ([2, 3, 4], [5]),
        "width": ([4, 8, 12], [6, 10, 16]),
        "en": ([0, 1], []),
        "reset": (["none", "sync"], ["async"]),
        "style": (["one", "sep"], ["vector"]),
    },
    "register": {
        "width": (W_TRAIN, W_TEST),
        "en": ([0, 1], []),
        "reset": (["none", "sync"], ["async"]),
        "src": (["plain", "mux2"], []),
        "rv": ([0, 1], []),
        "style": (["ifelse", "ternary"], ["nextstate"]),
    },
    "dpfsm": {
        "width": ([4, 8, 12], [6, 10, 16]),
        "states": ([3, 4], [5, 6]),
        "op": (["add", "sub"], ["xor"]),
        "style": (["case"], ["ifelse"]),
    },
    "alu": {
        "ops": ([2, 3, 4], [5, 6]),
        "width": ([4, 8, 12], [6, 10, 16]),
        "reg": ([0, 1], []),
        "style": (["case", "ternary"], ["ifelse"]),
    },
}

FAMILIES: tuple[str, ...] = tuple(REGIONS)
#: Designs per family and split: indices 0-69 train, 70-79 iid test, 80-99 ood test.
N_TRAIN, N_IID, N_OOD = 70, 10, 20
