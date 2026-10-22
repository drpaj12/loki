"""The ``loki`` command: bench init, assemble, check."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from loki.assemble import assemble, check_dataset, dataset_warnings
from loki.bench import SUITES, write_project


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="loki")
    sub = ap.add_subparsers(dest="cmd", required=True)
    bench = sub.add_parser("bench", help="benchmark projects")
    bsub = bench.add_subparsers(dest="bench_cmd", required=True)
    init = bsub.add_parser("init", help="write a Wyrd project for a benchmark suite")
    init.add_argument("--suite", choices=SUITES, required=True)
    init.add_argument("--odin3-root", required=True)
    init.add_argument("--out", required=True)
    init.add_argument("--cache", default="")
    asm = sub.add_parser("assemble", help="merge finished Wyrd runs into a dataset")
    asm.add_argument("--project", required=True)
    asm.add_argument("--out", required=True)
    chk = sub.add_parser("check", help="validate a dataset directory")
    chk.add_argument("dataset")
    return ap


def _default_cache() -> Path:
    base = os.environ.get("XDG_CACHE_HOME")
    return (Path(base) if base else Path.home() / ".cache") / "loki" / "verilog-eval"


def _run(args: argparse.Namespace) -> int:
    if args.cmd == "bench":
        cache = Path(args.cache) if args.cache else _default_cache()
        toml = write_project(args.suite, Path(args.odin3_root), cache, Path(args.out))
        print(f"wrote {toml}")
        return 0
    if args.cmd == "assemble":
        manifest = assemble(Path(args.project), Path(args.out))
        designs = manifest["designs"]
        count = len(designs) if isinstance(designs, list) else 0
        print(f"assembled {count} designs into {args.out}")
        return 0
    errors = check_dataset(Path(args.dataset))
    warnings = dataset_warnings(Path(args.dataset))
    for line in warnings[:50]:
        print(f"warning: {line}")
    if len(warnings) > 50:
        print(f"... and {len(warnings) - 50} more warnings")
    for line in errors[:50]:
        print(line)
    if len(errors) > 50:
        print(f"... and {len(errors) - 50} more")
    suffix = f", {len(warnings)} warning(s)" if warnings else ""
    print(f"loki check: {len(errors)} error(s){suffix}")
    return 1 if errors else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Exit 0 ok, 1 invariant errors, 2 usage."""
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code in (0, None) else 2
    try:
        return _run(args)
    except (ValueError, RuntimeError, OSError) as err:
        print(f"loki: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
