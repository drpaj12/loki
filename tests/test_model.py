import dataclasses
import unittest

from loki.model import Span


class ModelTest(unittest.TestCase):
    def test_frozen_and_hashable(self) -> None:
        s = Span("a.v", 1, 2, 1, 5)
        self.assertEqual(hash(s), hash(Span("a.v", 1, 2, 1, 5)))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            s.__setattr__("line", 3)


if __name__ == "__main__":
    unittest.main()
