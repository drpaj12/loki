"""A stand-in for the ORCA binary (L2 plan Task G-ext): ``node <4|5> <in> <out>``.

It implements the file protocol of L2 spec 8.5 with :func:`tests.graphlet_oracle.brute_orbits`,
so the counter tests run without network access or a C++ compiler. Size 4 writes the 15 orbit
columns of spec 8.4; size 5 writes the 73 columns of the same numbering, where the first 15 are
the 4-node orbits and the remaining 58 stand in as zeros (the real ORCA fills them).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


def main(argv: list[str]) -> int:
    """Run the protocol once; returns the process exit code."""
    if len(argv) != 4 or argv[0] != "node" or argv[1] not in ("4", "5"):
        print("usage: fake_orca.py node <4|5> <in> <out>", file=sys.stderr)
        return 2
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tests.graphlet_oracle import brute_orbits

    size = int(argv[1])
    tokens = Path(argv[2]).read_text(encoding="utf-8").split()
    if len(tokens) < 2:
        print("bad input: missing the N M header", file=sys.stderr)
        return 2
    n, m = int(tokens[0]), int(tokens[1])
    ends = [int(token) for token in tokens[2:]]
    if len(ends) != 2 * m:
        print(f"bad input: {len(ends)} endpoints for {m} edges", file=sys.stderr)
        return 2
    src = np.asarray(ends[0::2], dtype=np.int32)
    dst = np.asarray(ends[1::2], dtype=np.int32)
    orbits = brute_orbits(n, src, dst)
    if size == 5:
        wide = np.zeros((n, 73), dtype=np.int64)
        wide[:, :15] = orbits
        orbits = wide
    text = "".join(" ".join(str(value) for value in row) + "\n" for row in orbits.tolist())
    Path(argv[3]).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
