import stat
import tempfile
import unittest
from pathlib import Path

from loki.equiv import check_equiv


def fake_root(tmp: Path, exit_code: int, message: str = "") -> Path:
    tool = tmp / "tools" / "equiv-check" / "equiv-check"
    tool.parent.mkdir(parents=True)
    tool.write_text(f"#!/bin/sh\necho '{message}'\nexit {exit_code}\n", encoding="utf-8")
    tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
    return tmp


class EquivTest(unittest.TestCase):
    def status(self, code: int, message: str = "") -> str:
        with tempfile.TemporaryDirectory() as tmp:
            root = fake_root(Path(tmp), code, message)
            return check_equiv(".model a\n", ".model b\n", root, False).status

    def test_status_mapping(self) -> None:
        self.assertEqual(self.status(0), "equivalent")
        self.assertEqual(self.status(1), "differs")
        self.assertEqual(self.status(4), "unproven")
        self.assertEqual(self.status(2), "error")
        self.assertEqual(self.status(5), "error")
        self.assertEqual(self.status(2, "cannot name black box x"), "skipped:blackbox-names")

    def test_detail_and_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = check_equiv("a", "b", fake_root(Path(tmp), 1, "NOT equivalent"), True)
        self.assertEqual((res.tool_exit, res.detail), (1, "NOT equivalent"))


if __name__ == "__main__":
    unittest.main()
