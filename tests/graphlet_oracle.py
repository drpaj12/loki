"""The graphlet oracle of L2 Task 10 (L2 spec 8.4): brute-force orbit counts for small graphs.

``brute_orbits`` enumerates every connected induced subgraph of 2, 3 and 4 nodes and classifies
it by edge count and degree sequence; it is the reference the ORCA backend is compared against
(plan Task G-ext, ``test_real_orca_matches_oracle``). The cost grows with the number of connected
4-sets, so it is meant for graphs of up to a few hundred sparse nodes. numpy is imported inside
the function so a test module can import this helper without the ``analysis`` extra installed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy.typing as npt

_MAX_SIZE = 4


def _classify(degrees: tuple[int, ...]) -> tuple[int, ...] | None:
    """The orbit of each member of one induced subgraph, or ``None`` when it is not a graphlet.

    The degree sequence decides the shape (spec 8.4): an edge, P3, a triangle, P4, K1,3, C4, a
    tailed triangle, a diamond or K4. Disconnected sets (a zero degree, or a triangle plus an
    isolated node) match no row of the table and are skipped.
    """
    sequence = sorted(degrees)
    if sequence == [1, 1]:
        return (0, 0)
    if sequence == [1, 1, 2]:
        return tuple(1 if degree == 1 else 2 for degree in degrees)
    if sequence == [2, 2, 2]:
        return (3, 3, 3)
    if sequence == [1, 1, 2, 2]:
        return tuple(4 if degree == 1 else 5 for degree in degrees)
    if sequence == [1, 1, 1, 3]:
        return tuple(6 if degree == 1 else 7 for degree in degrees)
    if sequence == [2, 2, 2, 2]:
        return (8, 8, 8, 8)
    if sequence == [1, 2, 2, 3]:
        return tuple(9 if degree == 1 else 10 if degree == 2 else 11 for degree in degrees)
    if sequence == [2, 2, 3, 3]:
        return tuple(12 if degree == 2 else 13 for degree in degrees)
    if sequence == [3, 3, 3, 3]:
        return (14, 14, 14, 14)
    return None


def _add(members: list[int], adjacency: list[set[int]], orbits: npt.NDArray[Any]) -> None:
    """Classify the induced subgraph on ``members`` and count every member's orbit."""
    degrees = tuple(
        sum(1 for other in members if other != member and other in adjacency[member])
        for member in members
    )
    roles = _classify(degrees)
    if roles is None:
        return
    for member, orbit in zip(members, roles, strict=True):
        orbits[member, orbit] += 1


def _grow(
    root: int,
    members: list[int],
    adjacency: list[set[int]],
    orbits: npt.NDArray[Any],
    seen: set[frozenset[int]],
) -> None:
    """Extend one connected set whose lowest node is ``root`` by a neighbouring node.

    ``seen`` holds every set already visited, so a set reachable through several addition
    orders is classified once; the ``root`` bound keeps the lowest node of a set its origin.
    """
    key = frozenset(members)
    if key in seen:
        return
    seen.add(key)
    if len(members) > 1:
        _add(members, adjacency, orbits)
    if len(members) == _MAX_SIZE:
        return
    candidates: set[int] = set()
    for member in members:
        candidates |= adjacency[member]
    for candidate in sorted(candidates - key):
        if candidate > root:
            _grow(root, [*members, candidate], adjacency, orbits, seen)


def brute_orbits(n: int, src: npt.NDArray[Any], dst: npt.NDArray[Any]) -> npt.NDArray[Any]:
    """Orbit counts int64 ``(n, 15)`` of the simple undirected graph (spec 8.4).

    ``src``/``dst`` are 0-based endpoints, one entry per edge, in any direction; parallel edges
    and self-loops are ignored. Every connected induced subgraph of 2, 3 and 4 nodes adds 1 to
    the orbit of each of its members, so a node's orbit vector is its graphlet degree vector.
    """
    import numpy as np

    adjacency: list[set[int]] = [set() for _ in range(n)]
    for u, v in zip(src.tolist(), dst.tolist(), strict=True):
        start, end = int(u), int(v)
        if start == end or not (0 <= start < n and 0 <= end < n):
            continue
        adjacency[start].add(end)
        adjacency[end].add(start)
    orbits = np.zeros((n, 15), dtype=np.int64)
    seen: set[frozenset[int]] = set()
    for root in range(n):
        _grow(root, [root], adjacency, orbits, seen)
    return orbits
