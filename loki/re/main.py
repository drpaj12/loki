"""``loki re``: reverse-engineer one netlist (L1 spec 13). Exit 0 done, 1 internal error or
``final_equiv = differs``, 2 usage, 3 input unreadable."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from loki.re import bayes
from loki.re.loop import ReOptions, run_re
from loki.re.normalise import NormaliseError
from loki.re.report import write_outputs

FLOORS = ("f1-k6", "f1-earch", "f2", "f3", "auto")


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="loki re", description="reverse-engineer a netlist")
    ap.add_argument("netlist")
    ap.add_argument("--floor", choices=FLOORS, default="auto")
    ap.add_argument("--odin3-root", default="")
    ap.add_argument("--techlib", default="")
    ap.add_argument("--calib", default="none", help="calibration file or 'none'")
    ap.add_argument("--out", default="re_out")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max-rounds", type=int, default=bayes.MAX_ROUNDS)
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--time-budget", type=int, default=3600)
    ap.add_argument("--detectors", default="", help="comma-separated detector names")
    ap.add_argument("--keep-levels", default="")
    ap.add_argument("--no-commit", action="store_true")
    ap.add_argument("--features", choices=("all", "none"), default="all")
    return ap


def _options(args: argparse.Namespace) -> ReOptions:
    root = args.odin3_root or os.environ.get("ODIN3_ROOT", "")
    return ReOptions(
        netlist=Path(args.netlist),
        floor=args.floor,
        odin3_root=Path(root) if root else None,
        techlib=Path(args.techlib) if args.techlib else None,
        calib=None if args.calib == "none" else Path(args.calib),
        seed=args.seed,
        max_rounds=args.max_rounds,
        timeout=args.timeout,
        time_budget=args.time_budget,
        detectors=tuple(d for d in args.detectors.split(",") if d) or None,
        commit=not args.no_commit,
        keep_levels=Path(args.keep_levels) if args.keep_levels else None,
        features=args.features,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the flow and write ``--out``; the exit codes are those of spec 13."""
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code in (0, None) else 2
    opts = _options(args)
    if not opts.netlist.is_file():
        print(f"loki re: {opts.netlist}: cannot read the netlist", file=sys.stderr)
        return 3
    try:
        res = run_re(opts)
        write_outputs(res, opts, Path(args.out))
    except NormaliseError as err:
        print(str(err), file=sys.stderr)
        return 3
    except ValueError as err:
        print(f"loki re: {err}", file=sys.stderr)
        return 2
    except Exception as err:
        print(f"loki re: internal error: {err!r}", file=sys.stderr)
        return 1
    return 1 if res.final_equiv.get("status") == "differs" else 0


if __name__ == "__main__":
    sys.exit(main())
