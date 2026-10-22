"""Detector plugin interface (L1 spec 7.1): candidates, the round context, loading."""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import random
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from loki.re.claims import Claim

if TYPE_CHECKING:
    from loki.re.bayes import Calib
    from loki.re.fngraph import FnGraph
    from loki.re.overlay import Hypothesis
    from loki.re.structural import StructFeatures
    from loki.re.view import View

DETECTOR_ORDER = ("hard", "ff_pattern", "mux", "arith", "seqfn", "fsm", "bus", "unit", "role")
ENTRY_GROUP = "loki.detectors"
# Built-in detectors that exist so far: name -> (module, class). Later tasks add their line.
_BUILTINS: dict[str, tuple[str, str]] = {
    "ff_pattern": ("loki.re.detectors.ff_pattern", "FfPatternDetector"),
    "bus": ("loki.re.detectors.bus", "BusDetector"),
}

K_EDGES = (2, 3, 5, 9)
K_LABELS = ("2", "3-4", "5-8", "9+")


@dataclass(frozen=True)
class Candidate:
    """A detector's proposal; ``features`` are bin labels, never LLRs (spec 6.4)."""

    kind: str
    cells: frozenset[int]
    nets: Mapping[str, tuple[int, ...]]
    params: Mapping[str, int | str]
    features: Mapping[str, str]
    claim: Claim | None = None
    children: tuple[str, ...] = ()


class OverlayReader(Protocol):
    """The read-only side of the overlay that detectors may use."""

    def get(self, hid: str) -> Hypothesis: ...

    def by_kind(self, kind: str) -> list[Hypothesis]: ...

    def children_of(self, hid: str) -> list[Hypothesis]: ...

    def committed(self) -> list[Hypothesis]: ...


@dataclass(frozen=True)
class RoundContext:
    round: int
    floor: str
    graph: FnGraph
    view: View
    overlay: OverlayReader
    rng: Callable[[str], random.Random]
    calib: Calib
    fsm_marks: Mapping[frozenset[int], str] = field(default_factory=dict)
    unmap: tuple[Any, ...] = ()
    features: StructFeatures | None = None


class Detector(Protocol):
    name: str
    kinds: tuple[str, ...]

    def propose(self, ctx: RoundContext) -> Iterable[Candidate]: ...


def bin_count(n: int, edges: Sequence[int], labels: Sequence[str]) -> str:
    """The label of the last edge that ``n`` reaches; below the first edge is refused."""
    if len(edges) != len(labels) or not edges:
        raise ValueError("bin_count: edges and labels must have the same non-zero length")
    if n < edges[0]:
        raise ValueError(f"bin_count: {n} is below the first edge {edges[0]}")
    out = labels[0]
    for edge, label in zip(edges, labels, strict=True):
        if n >= edge:
            out = label
    return out


def k_bin(n: int) -> str:
    """The ``k`` / ``width`` bins of spec 7.4 (``2``, ``3-4``, ``5-8``, ``9+``)."""
    return bin_count(n, K_EDGES, K_LABELS)


def params_json(params: Mapping[str, int | str]) -> str:
    return json.dumps(dict(params), sort_keys=True, separators=(",", ":"))


def sorted_candidates(cands: Iterable[Candidate]) -> list[Candidate]:
    """Deterministic order of spec 7.1: ``(min(cells), kind, canonical params JSON)``."""
    return sorted(cands, key=lambda c: (min(c.cells, default=0), c.kind, params_json(c.params)))


def check_candidate(det: Detector, cand: Candidate) -> None:
    """Raise ``ValueError`` unless the kind is one of the detector's and a registered kind."""
    from loki.re.overlay import KINDS  # deferred: overlay imports this module

    if cand.kind not in det.kinds:
        raise ValueError(f"detector {det.name!r} proposed kind {cand.kind!r} outside {det.kinds}")
    if cand.kind not in KINDS:
        raise ValueError(f"unknown kind {cand.kind!r}")


def load_detectors(names: Sequence[str] | None) -> list[Detector]:
    """Built-ins in ``DETECTOR_ORDER`` then plugins by name; ``None`` means every built-in.

    A name that is neither a built-in nor an entry point of group ``loki.detectors`` raises
    ``ValueError``."""
    plugins = {ep.name: ep for ep in importlib.metadata.entry_points(group=ENTRY_GROUP)}
    if names is None:
        builtin = [n for n in DETECTOR_ORDER if n in _BUILTINS]
        extra: list[str] = []
    else:
        for n in names:
            if n not in _BUILTINS and n not in plugins:
                raise ValueError(f"unknown detector {n!r}")
        builtin = [n for n in DETECTOR_ORDER if n in _BUILTINS and n in names]
        extra = sorted(n for n in set(names) if n not in _BUILTINS)
    out: list[Detector] = []
    for n in builtin:
        module, cls = _BUILTINS[n]
        out.append(getattr(importlib.import_module(module), cls)())
    for n in extra:
        out.append(plugins[n].load()())
    return out
