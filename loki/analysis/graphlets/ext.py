"""The external graphlet backend: ORCA run as a separate process (L2 spec 8.5).

ORCA is a single-file C++11 program by Hocevar and Demsar (2014) under GPL-3.0. Loki never
links, includes or vendors it: :class:`OrcaCounter` runs ``orca node <size> <in> <out>`` on the
shared file protocol of spec 8.5, captures and discards its progress output, and reads the orbit
file back. :func:`loki.tools.fetch_orca` downloads the pinned source, verifies its SHA-256 and
builds the binary; the tests use ``tests/data/fake_orca.py`` instead.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

    import numpy.typing as npt

#: The pinned ORCA source (master, 2016-11-15); the SHA-256 was checked on 2026-10-21 (spec 8.5).
ORCA_COMMIT = "e146a8b1a99a90f5e3096b7bcc2ab0ea246c3ca7"
ORCA_SHA256 = "01c580febfd3653a632a04d6b466f7c6f2bf2f9baf3a75a2e553be30ac7ee778"
ORCA_URL = "https://raw.githubusercontent.com/thocevar/orca/" + ORCA_COMMIT + "/orca.cpp"
ORCA_LICENCE = (
    "GPL-3.0 (https://github.com/thocevar/orca/blob/master/LICENSE); "
    "run as a separate program, never linked or vendored"
)
ORCA_CITATION = (
    "Hocevar and Demsar, Bioinformatics 30(4):559-565, 2014, "
    "doi:10.1093/bioinformatics/btt717; Przulj, Bioinformatics 23(2):e177-e183, 2007, "
    "doi:10.1093/bioinformatics/btl301"
)
_FETCH_HINT = "run: loki tools fetch-orca"
_STDERR_LINES = 5


def cache_dir() -> Path:
    """The tool cache of spec 8.5: ``~/.cache/loki/tools/orca-<commit>`` (``$XDG_CACHE_HOME``)."""
    base = os.environ.get("XDG_CACHE_HOME")
    root = Path(base) if base else Path.home() / ".cache"
    return root / "loki" / "tools" / f"orca-{ORCA_COMMIT[:7]}"


def find_orca(explicit: Path | None = None) -> Path | None:
    """The ORCA binary of spec 8.5, or ``None``.

    Candidates in order: ``explicit`` (``--graphlet-tool``), ``$LOKI_GRAPHLET_TOOL``, then
    :func:`cache_dir` ``/orca``. A candidate that is not a file falls through to the next.
    """
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(Path(explicit))
    env = os.environ.get("LOKI_GRAPHLET_TOOL")
    if env:
        candidates.append(Path(env))
    candidates.append(cache_dir() / "orca")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


class OrcaCounter:
    """The ORCA backend (spec 8.5): 4- and 5-node orbit counts from a separate process.

    The ``tool`` argument or ``$LOKI_GRAPHLET_TOOL`` or the cache supplies the binary;
    ``argv_prefix`` replaces the whole command (the tests pass ``[python, fake_orca.py]``), and
    ``timeout`` bounds one run. The class attributes feed the ``tool`` object of spec 8.6.
    """

    name = "ext"
    max_size = 5
    commit = ORCA_COMMIT
    sha256 = ORCA_SHA256
    licence = ORCA_LICENCE

    def __init__(
        self,
        tool: Path | None = None,
        argv_prefix: Sequence[str] | None = None,
        timeout: float = 7200.0,
    ) -> None:
        self.tool = Path(tool) if tool is not None else None
        self.argv_prefix = tuple(argv_prefix) if argv_prefix is not None else None
        self.timeout = float(timeout)

    def _command(self) -> list[str] | None:
        """The argv prefix to run ORCA with, or ``None`` when no binary is found."""
        if self.argv_prefix is not None:
            return list(self.argv_prefix)
        tool = find_orca(self.tool)
        return [str(tool)] if tool is not None else None

    def available(self) -> tuple[bool, str]:
        """``(True, "")`` when an ORCA binary is found, else ``(False, reason)``."""
        if self._command() is None:
            return False, f"ORCA is not installed: {_FETCH_HINT}"
        return True, ""

    def count(
        self, n: int, src: npt.NDArray[Any], dst: npt.NDArray[Any], size: int = 4
    ) -> npt.NDArray[Any]:
        """Orbit counts int64 ``(n, N_ORBITS[size])`` of the simple undirected graph.

        The run writes the input file, runs ``orca node <size> <in> <out>`` in a temporary
        directory with an argv list (never a shell), discards stdout on success, and raises
        ``RuntimeError`` with the last stderr lines on a non-zero exit or a timeout.
        """
        from loki.analysis.graphlets import (
            N_ORBITS,
            BackendUnavailable,
            read_orbit_file,
            write_edge_file,
        )

        if size not in N_ORBITS:
            raise ValueError(f"unknown graphlet size {size}: ORCA counts 4- and 5-node graphlets")
        command = self._command()
        if command is None:
            raise BackendUnavailable(f"ORCA is not installed: {_FETCH_HINT}")
        with tempfile.TemporaryDirectory(prefix="loki-orca-") as tmp:
            in_path = Path(tmp) / "in.txt"
            out_path = Path(tmp) / "out.txt"
            write_edge_file(in_path, n, src, dst)
            argv = [*command, "node", str(int(size)), str(in_path), str(out_path)]
            try:
                done = subprocess.run(
                    argv, capture_output=True, text=True, timeout=self.timeout, check=False
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(
                    f"ORCA did not finish within {self.timeout:g} s: {exc}"
                ) from exc
            if done.returncode != 0:
                tail = done.stderr.splitlines()[-_STDERR_LINES:]
                raise RuntimeError(
                    f"ORCA failed (exit {done.returncode}): " + "\n".join(tail)
                )
            return read_orbit_file(out_path, n, N_ORBITS[size])
