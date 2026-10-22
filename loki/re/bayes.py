"""The Bayesian model: constants, calibration tables and default feature LLRs (L1 spec 6.2-6.4)."""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

PROOF_LO = 9.21
SIM_LLR = 4.61
STRUCT_CAP = 6.91
CHILD_LLR = 1.10
CHILD_CAP = 3.30
CHILD_NEG = -2.30
COMMIT_P = 0.9
PROVE_P = 0.2
REJECT_P = 0.01
MAX_PROOFS = 200
MAX_ROUNDS = 8
TRANSFER_ROUND = 2
CALIB_WL_DEPTH = 2
NODE_MIN_COUNT = 5
CALIB_FOLDS = 2
WEIGHT_GRID = tuple(i / 10 for i in range(11))
SCHEMA = 1


def logit(p: float) -> float:
    """Natural-log odds; ``0`` and ``1`` give ``-inf`` and ``inf``."""
    if p <= 0.0:
        return -math.inf
    if p >= 1.0:
        return math.inf
    return math.log(p / (1.0 - p))


def sigmoid(x: float) -> float:
    """``1 / (1 + e^-x)``, exact at ``+-inf`` and stable for large ``|x|``."""
    if x == math.inf:
        return 1.0
    if x == -math.inf:
        return 0.0
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


@dataclass(frozen=True)
class Calib:
    """Calibration: prior log-odds per ``<detector>/<kind>``, LLR per ``<kind>/<feature>`` and bin,
    and the weight of each feature family (1.0 when absent)."""

    floor: str
    priors: dict[str, float]
    llr: dict[str, dict[str, float]]
    source: str
    weights: dict[str, float] = field(default_factory=dict)
    node_llr: dict[str, dict[str, float]] = field(default_factory=dict)

    def prior(self, detector: str, kind: str) -> float:
        """Prior log-odds of ``kind`` proposed by ``detector`` (0.0 when unseen)."""
        return self.priors.get(f"{detector}/{kind}", 0.0)

    def feature_llr(self, kind: str, feature: str, bin: str) -> float:
        """The LLR of a feature bin (0.0 when unseen)."""
        return self.llr.get(f"{kind}/{feature}", {}).get(bin, 0.0)

    def weight(self, family: str) -> float:
        """Weight of a feature family (1.0 without calibration)."""
        return self.weights.get(family, 1.0)

    def node_score(self, kind: str, keys: Sequence[str]) -> float | None:
        """The node LLR of the first key present in ``node_llr[kind]`` (None when none is)."""
        table = self.node_llr.get(kind, {})
        for key in keys:
            if key in table:
                return table[key]
        return None


def family_of(feature: str) -> str:
    """The feature family: ``npn``, ``wl``, ``l2`` or ``struct`` (spec 6.4)."""
    for prefix in ("npn_", "wl_", "l2_"):
        if feature.startswith(prefix):
            return prefix[:-1]
    return "struct"


def wl_npn_bin(mean_llr: float | None) -> str:
    """Bin of the mean node LLR of a hypothesis (spec 6.7 item 1); ``None`` is ``unseen``."""
    if mean_llr is None:
        return "unseen"
    if mean_llr < -2.0:
        return "--"
    if mean_llr < -0.5:
        return "-"
    if mean_llr <= 0.5:
        return "0"
    if mean_llr <= 2.0:
        return "+"
    return "++"


_K_BINS = {"2": 0.0, "3-4": 0.69, "5-8": 1.39, "9+": 2.08}
_WL_DEPTH = {"0": 0.0, "1": 0.41, "2-3": 0.69, "4": 1.10, "n/a": 0.0}
_ARITH = ("adder", "subtractor", "adder_cin", "comparator", "eq_const")
_CHAIN = ("adder", "subtractor", "adder_cin")
_SEQ = ("counter", "shift_reg", "lfsr")
_YES = {"yes": 0.69}


def _defaults() -> dict[str, dict[str, float]]:
    t: dict[str, dict[str, float]] = {
        "hard_group/shared_ctrl": {"all": 4.61, "addr_only": 1.10},
        "hard_add/declined_chain": {"yes": 4.61},
        "ff_en/en_fn_exact": {"yes": 4.61},
        "ff_srst/rst_fanout": {"1": -1.10, "2-3": 1.10, "4-7": 2.20, "8+": 3.00},
        "register/shared_ctrl": {"en": 1.39, "rst": 1.39, "both": 1.39},
        "register/d_from_piece": {"yes": 1.39},
        "register/width": dict(_K_BINS),
        "bus/k": dict(_K_BINS),
        "bus/ctrl_fanout_exact": {"yes": 1.10, "no": -0.69},
        "bus/data_from_bus": {"all": 1.10},
        "bus/wl_depth": dict(_WL_DEPTH),
        "comparator/npn_xor2": {"yes": 0.69},
        "mux_bit/npn_class": {"mux2": 0.69, "mux4": 0.69, "other": 0.0},
        "mux/width": dict(_K_BINS),
        "mux/sel_shared": dict(_YES),
        "mux/wl_depth": dict(_WL_DEPTH),
        "fsm/ctrl_inputs": {"0": -1.10, "1-4": 0.69, "5+": -0.69},
        "fsm/decoder_readers": {">=0.5": 1.39},
        "fsm/fsm_detect": {"marked": 4.61},
        "fsm/counter_like": {"yes": -2.30},
        "fsm/self_reset": {"yes": -0.69},
        "fsm/reset_found": {"yes": 0.69},
        "role/role_prop": {"control": 2.30, "data": -2.30, "mixed": 0.0, "none": 0.0},
        "role/in_bus4": {"yes": -1.10},
    }
    for kind in _ARITH:
        t[f"{kind}/width"] = dict(_K_BINS)
        t[f"{kind}/out_reads"] = dict(_YES)
    for kind in _CHAIN:
        t[f"{kind}/npn_sum"] = {"all": 2.30, "half": 0.69, "low": -1.39, "no_cut": 0.0}
        t[f"{kind}/npn_carry"] = {"all": 1.39, "half": 0.41, "low": -0.69, "no_cut": 0.0}
    for kind in _SEQ:
        t[f"{kind}/table"] = {"exact": 0.0, "sampled": -0.69}
    t["counter/counter_terms"] = {"1-2": 0.69}
    for kind in ("datapath_unit", "control_unit"):
        t[f"{kind}/internal_ratio"] = {">=0.7": 1.10, "<0.4": -1.10}
    return t


DEFAULTS = Calib(floor="", priors={}, llr=_defaults(), source="defaults")


def _num(value: object, key: str, where: str) -> float:
    if isinstance(value, dict):
        value = value[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{where}: not a number")
    return float(value)


def load_calib(path: Path | None) -> Calib:
    """``DEFAULTS`` for ``None``; else a calibration file of schema 1 (spec 6.3)."""
    if path is None:
        return DEFAULTS
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or obj.get("schema") != SCHEMA:
        raise ValueError(f"{path}: schema must be {SCHEMA}")
    priors = {
        str(k): _num(v, "log_odds", f"{path}: priors {k}") for k, v in obj.get("priors", {}).items()
    }
    llr = {
        str(k): {str(b): _num(v, "llr", f"{path}: llr {k}/{b}") for b, v in bins.items()}
        for k, bins in obj.get("llr", {}).items()
    }
    weights = {str(k): float(v) for k, v in obj.get("weights", {}).items()}
    node_llr = {
        str(k): {str(b): _num(v, "llr", f"{path}: node_llr {k}/{b}") for b, v in keys.items()}
        for k, keys in obj.get("node_llr", {}).items()
    }
    return Calib(str(obj.get("floor", "")), priors, llr, str(path), weights, node_llr)
