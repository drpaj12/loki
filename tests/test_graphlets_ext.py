"""L2 Task G-ext: the ORCA backend, ``loki tools fetch-orca`` and the real-oracle cross-check.

The counter tests drive :class:`loki.analysis.graphlets.ext.OrcaCounter` through
``tests/data/fake_orca.py``, which implements the ORCA file protocol of spec 8.5 with the 4-node
oracle, so they need neither network access nor a C++ compiler. ``test_fetch_verifies_sha``
injects its downloader and compiler, and ``test_real_orca_matches_oracle`` runs only when
:func:`~loki.analysis.graphlets.ext.find_orca` finds a built binary.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest import mock

from loki.analysis.graphio import Graph, load_graph
from loki.analysis.graphlets import (
    BACKENDS,
    N_ORBITS,
    BackendUnavailable,
    get_backend,
    run_graphlets,
)
from loki.analysis.graphlets.ext import (
    ORCA_CITATION,
    ORCA_COMMIT,
    ORCA_LICENCE,
    ORCA_SHA256,
    ORCA_URL,
    OrcaCounter,
    cache_dir,
    find_orca,
)
from loki.tools import fetch_orca
from tests.analysis_fixtures import make_sync_design, write_graph
from tests.graphlet_oracle import brute_orbits
from tests.helpers import skip_without

if TYPE_CHECKING:
    import numpy.typing as npt

_FAKE = Path(__file__).resolve().parent / "data" / "fake_orca.py"
_FAKE_ARGV = [sys.executable, str(_FAKE)]


def _random_graph(seed: int, hi: int = 60) -> tuple[int, npt.NDArray[Any], npt.NDArray[Any]]:
    """A seeded simple undirected graph: ``n`` in 5..``hi``, int32 ``src < dst`` arrays."""
    import numpy as np

    rng = np.random.default_rng(seed)
    n = int(rng.integers(5, hi + 1))
    density = float(rng.uniform(0.05, 0.15))
    upper = np.triu(rng.random((n, n)) < density, k=1)
    src, dst = np.nonzero(upper)
    return n, src.astype(np.int32), dst.astype(np.int32)


def _load(obj: dict[str, object]) -> Graph:
    """Load a hand-built ``graph.json`` object through the real loader."""
    with tempfile.TemporaryDirectory() as tmp:
        return load_graph(write_graph(Path(tmp), obj))


class PinnedTests(unittest.TestCase):
    """The pinned tool constants, tool lookup, the fetch and the CLI usage (no ORCA needed)."""

    def test_constants_pinned(self) -> None:
        """The commit, the SHA-256, the URL, the licence and the citations of spec 8.5."""
        self.assertEqual(ORCA_COMMIT, "e146a8b1a99a90f5e3096b7bcc2ab0ea246c3ca7")
        self.assertEqual(
            ORCA_SHA256, "01c580febfd3653a632a04d6b466f7c6f2bf2f9baf3a75a2e553be30ac7ee778"
        )
        self.assertEqual(len(ORCA_COMMIT), 40)
        self.assertEqual(len(ORCA_SHA256), 64)
        for value in (ORCA_COMMIT, ORCA_SHA256):
            int(value, 16)
        self.assertIn(ORCA_COMMIT, ORCA_URL)
        self.assertTrue(ORCA_URL.startswith("https://raw.githubusercontent.com/thocevar/orca/"))
        self.assertTrue(ORCA_URL.endswith("/orca.cpp"))
        self.assertIn("GPL-3.0", ORCA_LICENCE)
        self.assertIn("separate program", ORCA_LICENCE)
        self.assertIn("btt717", ORCA_CITATION)
        self.assertIn("btl301", ORCA_CITATION)

    def test_find_tool_order(self) -> None:
        """Argument first, then ``$LOKI_GRAPHLET_TOOL``, then the cache; a miss falls through."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            argument = root / "arg-orca"
            argument.write_text("", encoding="utf-8")
            env_tool = root / "env-orca"
            env_tool.write_text("", encoding="utf-8")
            cache = root / "cache"
            env = {"XDG_CACHE_HOME": str(cache), "LOKI_GRAPHLET_TOOL": str(env_tool)}
            with mock.patch.dict(os.environ, env):
                self.assertEqual(
                    cache_dir(), cache / "loki" / "tools" / f"orca-{ORCA_COMMIT[:7]}"
                )
                self.assertEqual(find_orca(argument), argument)
                self.assertEqual(find_orca(Path(root / "absent")), env_tool)
                self.assertEqual(find_orca(), env_tool)
                del os.environ["LOKI_GRAPHLET_TOOL"]
                self.assertIsNone(find_orca())
                cached = cache_dir() / "orca"
                cached.parent.mkdir(parents=True)
                cached.write_text("", encoding="utf-8")
                self.assertEqual(find_orca(), cached)
                self.assertEqual(find_orca(argument), argument)
            with mock.patch.dict(
                os.environ, {"XDG_CACHE_HOME": str(cache), "LOKI_GRAPHLET_TOOL": ""}
            ):
                self.assertEqual(find_orca(), cached)

    def test_available_false_with_reason(self) -> None:
        """With no binary the backend is unavailable and names the fetch command."""
        with tempfile.TemporaryDirectory() as tmp:
            env = {"XDG_CACHE_HOME": tmp, "LOKI_GRAPHLET_TOOL": ""}
            with mock.patch.dict(os.environ, env):
                ok, reason = OrcaCounter().available()
                self.assertFalse(ok)
                self.assertIn("run: loki tools fetch-orca", reason)
                with self.assertRaises(BackendUnavailable) as caught:
                    get_backend("ext")
                self.assertIn("run: loki tools fetch-orca", str(caught.exception))
                cached = cache_dir() / "orca"
                cached.parent.mkdir(parents=True)
                cached.write_text("", encoding="utf-8")
                self.assertEqual(OrcaCounter().available(), (True, ""))
                self.assertEqual(get_backend("ext").name, "ext")

    def test_fetch_verifies_sha(self) -> None:
        """Wrong bytes are refused; matching bytes are written and compiled with the pinned argv."""
        payload = b"// pinned orca.cpp\nint main() { return 0; }\n"
        digest = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "tools"
            with self.assertRaises(ValueError) as caught:
                fetch_orca(dest, downloader=lambda _url: b"tampered\n")
            self.assertEqual(str(caught.exception), "orca.cpp sha256 mismatch")
            self.assertFalse(dest.exists())
            urls: list[str] = []

            def download(url: str) -> bytes:
                urls.append(url)
                return payload

            def no_download(_url: str) -> bytes:
                raise AssertionError("an existing binary must not download again")

            calls: list[tuple[list[str], dict[str, Any]]] = []

            def compile_argv(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
                calls.append((argv, kwargs))
                Path(kwargs["cwd"], "orca").write_text("", encoding="utf-8")
                return subprocess.CompletedProcess(argv, 0, "", "")

            with mock.patch("loki.tools.ORCA_SHA256", digest), mock.patch(
                "loki.tools.subprocess.run", side_effect=compile_argv
            ):
                binary = fetch_orca(dest, downloader=download)
                again = fetch_orca(dest, downloader=no_download)
            self.assertEqual(binary, dest / "orca")
            self.assertEqual(again, binary)
            self.assertEqual(urls, [ORCA_URL])
            self.assertEqual((dest / "orca.cpp").read_bytes(), payload)
            self.assertEqual(calls[0][0], ["g++", "-O2", "-std=c++11", "-o", "orca", "orca.cpp"])
            self.assertEqual(calls[0][1]["cwd"], dest)

            with mock.patch("loki.tools.ORCA_SHA256", digest):
                with self.assertRaises(RuntimeError) as caught_compile:
                    fetch_orca(
                        dest / "no-compiler", downloader=download, compiler="no-such-compiler"
                    )
                self.assertIn("cannot run the compiler", str(caught_compile.exception))
                self.assertFalse((dest / "no-compiler" / "orca").exists())
                failed = subprocess.CompletedProcess(["g++"], 1, "", "orca.cpp: error: boom\n")
                with (
                    mock.patch("loki.tools.subprocess.run", return_value=failed),
                    self.assertRaises(RuntimeError) as caught_build,
                ):
                    fetch_orca(dest / "bad-build", downloader=download)
                self.assertIn("failed (exit 1)", str(caught_build.exception))
                self.assertIn("orca.cpp: error: boom", str(caught_build.exception))
                self.assertFalse((dest / "bad-build" / "orca").exists())

    def test_cli_tools_fetch_orca_usage(self) -> None:
        """``loki tools`` without a subcommand is a usage error (exit 2)."""
        from loki.cli import main

        stderr = io.StringIO()
        with redirect_stderr(stderr):
            self.assertEqual(main(["tools"]), 2)
        self.assertIn("fetch-orca", stderr.getvalue())
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(["tools", "bogus"]), 2)


@skip_without("numpy")
class CounterTests(unittest.TestCase):
    """``OrcaCounter`` through the fake tool, plus the real-binary cross-check."""

    def test_count_with_fake_tool(self) -> None:
        """The fake implements the file protocol; five random graphs match the 4-node oracle."""
        import numpy as np

        counter = OrcaCounter(argv_prefix=_FAKE_ARGV)
        self.assertEqual(counter.available(), (True, ""))
        for seed in range(5):
            n, src, dst = _random_graph(seed, hi=30)
            orbits = counter.count(n, src, dst)
            self.assertEqual(orbits.dtype, np.int64)
            np.testing.assert_array_equal(orbits, brute_orbits(n, src, dst))

    def test_argv_is_list_no_shell(self) -> None:
        """``subprocess.run`` gets a str argv list ending ``node 4 <in> <out>``; never a shell."""
        n, src, dst = _random_graph(1, hi=15)
        calls: list[tuple[list[str], dict[str, Any]]] = []

        def fake_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            calls.append((argv, kwargs))
            self.assertTrue(Path(argv[-2]).is_file())
            rows = "".join(" ".join(["0"] * 15) + "\n" for _ in range(n))
            Path(argv[-1]).write_text(rows, encoding="utf-8")
            return subprocess.CompletedProcess(argv, 0, "", "")

        counter = OrcaCounter(argv_prefix=_FAKE_ARGV)
        with mock.patch("loki.analysis.graphlets.ext.subprocess.run", side_effect=fake_run):
            orbits = counter.count(n, src, dst)
        argv, kwargs = calls[0]
        self.assertIsInstance(argv, list)
        self.assertTrue(all(isinstance(part, str) for part in argv))
        self.assertFalse(kwargs.get("shell", False))
        self.assertEqual(argv[:-4], _FAKE_ARGV)
        self.assertEqual(argv[-4:-2], ["node", "4"])
        self.assertTrue(kwargs["capture_output"])
        self.assertTrue(kwargs["text"])
        self.assertFalse(kwargs["check"])
        self.assertEqual(kwargs["timeout"], 7200.0)
        self.assertEqual(orbits.shape, (n, N_ORBITS[4]))

    def test_tool_failure_message(self) -> None:
        """A non-zero exit raises ``RuntimeError`` carrying the tool's stderr text."""
        import numpy as np

        code = "import sys; sys.stderr.write('orca exploded\\n'); sys.exit(1)"
        counter = OrcaCounter(argv_prefix=[sys.executable, "-c", code])
        src = np.asarray([0], dtype=np.int32)
        dst = np.asarray([1], dtype=np.int32)
        with self.assertRaises(RuntimeError) as caught:
            counter.count(2, src, dst)
        self.assertIn("orca exploded", str(caught.exception))

    def test_timeout(self) -> None:
        """A tool that overruns the timeout raises ``RuntimeError`` instead of hanging."""
        import numpy as np

        slow = [sys.executable, "-c", "import time; time.sleep(10)"]
        counter = OrcaCounter(argv_prefix=slow, timeout=0.2)
        src = np.asarray([0], dtype=np.int32)
        dst = np.asarray([1], dtype=np.int32)
        with self.assertRaises(RuntimeError) as caught:
            counter.count(2, src, dst)
        self.assertIn("did not finish", str(caught.exception))

    def test_size5_width_73(self) -> None:
        """Size 5 returns the 73 orbit columns of spec 8.4; the first 15 are the 4-node orbits."""
        import numpy as np

        counter = OrcaCounter(argv_prefix=_FAKE_ARGV)
        n, src, dst = _random_graph(3, hi=20)
        orbits = counter.count(n, src, dst, size=5)
        self.assertEqual(orbits.shape, (n, N_ORBITS[5]))
        self.assertEqual(orbits.dtype, np.int64)
        np.testing.assert_array_equal(orbits[:, :15], brute_orbits(n, src, dst))

    @unittest.skipUnless(
        find_orca() is not None, "ORCA is not installed: run loki tools fetch-orca"
    )
    def test_real_orca_matches_oracle(self) -> None:
        """Ten random graphs match the oracle at 4 and the first 15 of 5; a 3000-leaf star
        keeps the hub's orbit 7 int64-exact at C(3000, 3) = 4495501000."""
        import numpy as np

        counter = OrcaCounter()
        for seed in range(10):
            n, src, dst = _random_graph(100 + seed)
            expected = brute_orbits(n, src, dst)
            np.testing.assert_array_equal(counter.count(n, src, dst), expected)
            wide = counter.count(n, src, dst, size=5)
            self.assertEqual(wide.shape, (n, N_ORBITS[5]))
            np.testing.assert_array_equal(wide[:, :15], expected)
        degree = 3000
        src = np.zeros(degree, dtype=np.int32)
        dst = np.arange(1, degree + 1, dtype=np.int32)
        hub = counter.count(degree + 1, src, dst)
        self.assertEqual(hub.dtype, np.int64)
        self.assertEqual(int(hub[0][7]), degree * (degree - 1) * (degree - 2) // 6)

    def test_run_graphlets_with_fake_orca_end_to_end(self) -> None:
        """``run_graphlets(backend="ext")`` through the fake writes both files and pins the tool."""
        g = _load(make_sync_design(n_ff=4, reset=True))
        previous = BACKENDS["ext"]
        BACKENDS["ext"] = OrcaCounter(argv_prefix=_FAKE_ARGV)
        self.addCleanup(BACKENDS.__setitem__, "ext", previous)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "graphlets"
            path = run_graphlets(g, "ext", out)
            self.assertEqual(path, out / "graphlets-ext-global.json")
            self.assertTrue((out / "orbits-ext-global.npz").is_file())
            record = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(record["backend"], "ext")
        self.assertEqual(record["tool"]["name"], "ext")
        self.assertEqual(record["tool"]["commit"], ORCA_COMMIT)
        self.assertEqual(record["tool"]["sha256"], ORCA_SHA256)
        self.assertEqual(record["tool"]["licence"], ORCA_LICENCE)
        self.assertEqual(record["size"], 4)
        self.assertEqual(record["n_orbits"], N_ORBITS[4])


if __name__ == "__main__":
    unittest.main()
