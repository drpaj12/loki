"""Tests for loki/runrecord.py and loki/re/record.py: the Mimir run record of ``loki re``."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from loki import runrecord as rr
from loki.re.main import main as re_main
from tests.helpers import odin_available

DATA = Path(__file__).resolve().parent / "data" / "re"
CALIB = Path(__file__).resolve().parents[1] / "calib" / "f2.json"


class TmpCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)


class Placeholders(TmpCase):
    def rec(self, top: str = "") -> rr.RunRecorder:
        return rr.RunRecorder("s", "d", "a", 0, "arch", {"out": self.tmp}, top=top)

    def test_paths(self) -> None:
        rec = self.rec()
        self.assertEqual(rec.ph(f"{self.tmp}/x/report.json"), "<out>/x/report.json")
        self.assertEqual(rec.ph("/elsewhere/x.v"), "<abs>/x.v")
        self.assertEqual(rec.ph("calib/f2.json"), "calib/f2.json")

    def test_idempotent(self) -> None:
        rec = self.rec()
        once = rec.ph(f"x {self.tmp}/run")
        self.assertEqual(rec.ph(once), once)


class HostAlias(TmpCase):
    def test_no_map_is_unknown(self) -> None:
        self.assertEqual(rr.host_alias("some-host", self.tmp / "none.toml"), "unknown")

    def test_map_numbers_a_new_name(self) -> None:
        path = self.tmp / "hosts.toml"
        path.write_text('[hosts]\n"alpha" = "host-1"\n', encoding="utf-8")
        self.assertEqual(rr.host_alias("ALPHA", path), "host-1")
        self.assertEqual(rr.host_alias("beta", path), "host-2")


class Privacy(unittest.TestCase):
    def test_rule_and_key_not_value(self) -> None:
        hits = rr.privacy_hits({"a": "/home" + "/someone/x", "b": ["k=/abs/p"], "c": "a/b.py:3"})
        self.assertEqual(hits, ["home-path at record.a", "absolute-path at record.b[0]"])

    def test_user_name(self) -> None:
        with mock.patch("getpass.getuser", return_value="zzuser"):
            self.assertEqual(rr.privacy_hits({"k": "by ZZUSER"}), ["user-name at record.k"])


@unittest.skipUnless(odin_available(), "needs Odin III")
class LokiReRecord(TmpCase):
    def run_re(self, *extra: str) -> dict[str, object]:
        out = self.tmp / "out"
        env = {**os.environ, "MIMIR_HOST_MAP": str(self.tmp / "missing.toml")}
        with mock.patch.dict(os.environ, env, clear=True):
            code = re_main([str(DATA / "add2.blif"), "--floor", "f2", "--calib", str(CALIB),
                            "--out", str(out), *extra])
        self.assertEqual(code, 0)
        data: dict[str, object] = json.loads((out / "mimir-run.json").read_text(encoding="utf-8"))
        return data

    def test_record(self) -> None:
        rec = self.run_re()
        self.assertEqual(rec["kind"], "loki-run")
        self.assertEqual(rec["source"], "loki")
        self.assertEqual(rec["host"], "unknown")
        self.assertEqual(rec["arm"], "re-f2")
        self.assertEqual(rr.privacy_hits(rec), [])
        steps = rec["steps"]
        assert isinstance(steps, list)
        self.assertEqual(steps[0]["argv"][:3], ["loki", "re", "<netlist>"])
        self.assertIn("<out>", steps[0]["argv"])

    def test_params_given_and_default(self) -> None:
        params = self.run_re("--seed", "7")["params"]
        assert isinstance(params, dict)
        self.assertEqual(params["run.seed"]["conf"], "given")
        self.assertEqual(params["re.floor"]["conf"], "given")
        self.assertEqual(params["re.max-rounds"]["conf"], "default")
        self.assertRegex(params["re.max-rounds"]["source"], r"loki/re/main\.py:\d+$")
        self.assertEqual(len(params["re.calib_sha256"]["value"]), 64)
