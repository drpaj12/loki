import tomllib
import unittest
from pathlib import Path

import loki


class PackagingTest(unittest.TestCase):
    def test_version_and_entry_point(self) -> None:
        self.assertEqual(loki.__version__, "0.1.0")
        path = Path(__file__).resolve().parent.parent / "pyproject.toml"
        with path.open("rb") as fh:
            data = tomllib.load(fh)
        self.assertEqual(data["project"]["requires-python"], ">=3.11")
        self.assertEqual(data["project"]["scripts"]["loki"], "loki.cli:main")


if __name__ == "__main__":
    unittest.main()
