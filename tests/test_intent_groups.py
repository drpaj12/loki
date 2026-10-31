"""Regression: a flip-flop with no usable support (not a key of ``deps``) must not crash the
feeder search (``loki re`` KeyError on Prob153_gshare, 2026-10-30)."""

from __future__ import annotations

import unittest

from loki.intent.groups import _feeders


class FeedersTest(unittest.TestCase):
    def test_upstream_without_deps_entry(self) -> None:
        deps = {1: frozenset({1, 38}), 2: frozenset({1, 2})}
        self.assertEqual(_feeders(frozenset({1}), deps), frozenset())

    def test_feeder_added(self) -> None:
        deps = {1: frozenset({1, 2}), 2: frozenset({2})}
        self.assertEqual(_feeders(frozenset({1}), deps), frozenset({2}))


if __name__ == "__main__":
    unittest.main()
