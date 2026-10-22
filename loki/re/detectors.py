"""Detector plugin interface (L1 spec 7.1). Task 6 adds the protocol and the context."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from loki.re.claims import Claim


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
