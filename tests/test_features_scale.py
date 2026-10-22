"""Budgets of L1 spec 6.7 on a 100k-node synthetic netlist (only with LOKI_SCALE=1)."""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
N = 100_000

_CHILD = """
import json, resource, sys, time
from tests.features_fixtures import synthetic_netlist
from loki.features.npn import npn_class, stats
from loki.features.roles import classify_nets
from loki.features.wl import WLConfig, refine, stable_partition

step = sys.argv[1]
fg = synthetic_netlist({n}, 1)
roles = classify_nets(fg)
cfg = WLConfig("npn", "both", 4)
t0 = time.monotonic()
extra = {{}}
if step == "refine":
    res = refine(fg, roles, cfg)
    extra["stable_round"] = res.stable_round
elif step == "stable_partition":
    extra["classes"] = stable_partition(fg, roles, cfg).n_classes
else:
    tables = sorted({{(fg.width[v], fg.table[v]) for v in range(fg.n_nodes) if fg.table[v] >= 0}})
    for w, t in tables:
        npn_class(t, w)
    extra["distinct_tables"] = len(tables)
    extra["stats"] = stats()
seconds = time.monotonic() - t0
rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
print(json.dumps({{"step": step, "seconds": seconds, "rss_mb": rss_mb, "n": fg.n_nodes,
                   "edges": fg.n_edges, **extra}}))
"""

# step: budget in seconds (2 x the spec 6.7 estimate; npn 60 s)
BUDGET = {"refine": 60.0, "stable_partition": 120.0, "npn": 60.0}


def measure(step: str) -> dict[str, object]:
    out = subprocess.run(
        [sys.executable, "-c", _CHILD.format(n=N), step], cwd=ROOT, check=True,
        capture_output=True, text=True,
    )
    result: dict[str, object] = json.loads(out.stdout.strip().splitlines()[-1])
    print(result)
    return result


@unittest.skipUnless(os.environ.get("LOKI_SCALE") == "1", "set LOKI_SCALE=1 for scale tests")
class ScaleTest(unittest.TestCase):
    def check(self, step: str) -> None:
        r = measure(step)
        seconds, rss = r["seconds"], r["rss_mb"]
        assert isinstance(seconds, float) and isinstance(rss, float)
        self.assertLess(seconds, BUDGET[step])
        self.assertLess(rss, 2048.0)

    def test_refine(self) -> None:
        self.check("refine")

    def test_stable_partition(self) -> None:
        self.check("stable_partition")

    def test_npn_distinct_tables(self) -> None:
        self.check("npn")


if __name__ == "__main__":
    unittest.main()
