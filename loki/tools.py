"""Fetch and build external tools used by Loki analyses (L2 spec 8.5).

ORCA is the default graphlet counter. It is GPL-3.0, so Loki downloads its pinned single-file
source into the cache, verifies the SHA-256, builds it with the system C++ compiler and runs it as
a separate process; it is never linked, included or vendored. Standard library only.
"""

from __future__ import annotations

import hashlib
import subprocess
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

from loki.analysis.graphlets.ext import ORCA_SHA256, ORCA_URL, cache_dir

if TYPE_CHECKING:
    from collections.abc import Callable

_STDERR_LINES = 5
_HTTP_TIMEOUT = 60
_COMPILE_ARGV = ["-O2", "-std=c++11", "-o", "orca", "orca.cpp"]


def _http_get(url: str) -> bytes:
    """Read ``url`` once; :func:`fetch_orca` requests only the pinned URL."""
    with urllib.request.urlopen(url, timeout=_HTTP_TIMEOUT) as response:
        return bytes(response.read())


def fetch_orca(
    dest: Path | None = None,
    *,
    downloader: Callable[[str], bytes] = _http_get,
    compiler: str = "g++",
) -> Path:
    """Download, verify and build ORCA into ``dest`` (default :func:`cache_dir`) and return it.

    An existing ``orca`` binary returns at once without downloading. The download must hash to
    :data:`ORCA_SHA256`, else ``ValueError("orca.cpp sha256 mismatch")`` and nothing is written.
    The build runs the argv list ``[compiler, "-O2", "-std=c++11", "-o", "orca", "orca.cpp"]``
    in ``dest``; a non-zero exit or a missing compiler raises ``RuntimeError``, so nothing
    unverified is ever executed.
    """
    root = Path(dest) if dest is not None else cache_dir()
    binary = root / "orca"
    if binary.is_file():
        return binary
    payload = downloader(ORCA_URL)
    if hashlib.sha256(payload).hexdigest() != ORCA_SHA256:
        raise ValueError("orca.cpp sha256 mismatch")
    root.mkdir(parents=True, exist_ok=True)
    (root / "orca.cpp").write_bytes(payload)
    argv = [compiler, *_COMPILE_ARGV]
    try:
        done = subprocess.run(argv, cwd=root, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise RuntimeError(f"{compiler}: cannot run the compiler: {exc}") from exc
    if done.returncode != 0:
        tail = done.stderr.splitlines()[-_STDERR_LINES:]
        raise RuntimeError(f"{compiler} failed (exit {done.returncode}): " + "\n".join(tail))
    if not binary.is_file():
        raise RuntimeError(f"{compiler} exited 0 but wrote no {binary}")
    return binary
