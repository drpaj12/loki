"""Check the `re` user messages are byte-equal to the `standard` ones (EXPERIMENT.md, decision 14).

Usage: ``python -I check_hash_equality.py``. Compares ``user_sha256`` per (arm, problem) between the
tracked ``prompt_sizes.csv`` (standard) and ``prompt_sizes_re.csv`` (re). Prints one summary line;
exit 0 only when both files hold the same 120 calls and every hash is equal.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(path: Path) -> dict[tuple[str, str], str]:
    with path.open(encoding="utf-8", newline="") as fh:
        return {(r["arm"], r["problem"]): r["user_sha256"] for r in csv.DictReader(fh)}


def compare(std: dict[tuple[str, str], str], re_: dict[tuple[str, str], str]) -> list[str]:
    """Differences: keys present in one run only, and keys whose hashes differ."""
    bad = [f"only in one run: {k}" for k in sorted(std.keys() ^ re_.keys())]
    bad += [f"hash differs: {k}" for k in sorted(std.keys() & re_.keys()) if std[k] != re_[k]]
    return bad


def main() -> int:
    std, re_ = load(HERE / "prompt_sizes.csv"), load(HERE / "prompt_sizes_re.csv")
    bad = compare(std, re_)
    for line in bad:
        print(line)
    print(f"standard {len(std)} calls, re {len(re_)} calls, differences {len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
