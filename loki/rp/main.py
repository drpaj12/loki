"""``loki rp``: ``add-l2`` and ``doc`` on a ``loki re`` output directory. Exit 0 done, 2 usage or
a failed join, 3 input unreadable."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

DEFAULT_MAX_CHARS = 24000


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="loki rp", description="ReverseProvenance tools")
    sub = ap.add_subparsers(dest="rp_cmd", required=True)
    l2 = sub.add_parser("add-l2", help="merge an L2 partition into reverse-provenance.json")
    l2.add_argument("re_dir")
    l2.add_argument("partition")
    l2.add_argument("--allow-unjoined-ports", action="store_true",
                    help="accept partition nodes that join to nothing when their count equals "
                    "the ports not joined by name, even if the partition design differs from "
                    "the re input")
    doc = sub.add_parser("doc", help="write the LLM context document")
    doc.add_argument("re_dir")
    doc.add_argument("-o", "--out", default="", help="output file (default: stdout)")
    doc.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS,
                     help="size limit; section 9 (what Loki does not claim) is never cut, so a "
                     "value below the size of sections 1, 2 and 9 (about 1500 characters, more "
                     "for long netlist names) is raised to that size")
    doc.add_argument("--include-candidates", dest="candidates", action="store_true", default=True)
    doc.add_argument("--no-candidates", dest="candidates", action="store_false",
                     help="leave the candidate section out")
    return ap


def _doc(args: argparse.Namespace) -> int:
    from loki.rp.doc import render

    text = render(Path(args.re_dir), max_chars=args.max_chars, candidates=args.candidates)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(text)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code in (0, None) else 2
    try:
        if args.rp_cmd == "add-l2":
            from loki.rp.l2 import add_l2

            done = add_l2(Path(args.re_dir), Path(args.partition), args.allow_unjoined_ports)
            print(f"wrote {done}")
            return 0
        return _doc(args)
    except FileNotFoundError as err:
        print(f"loki rp: {err}", file=sys.stderr)
        return 3
    except (ValueError, KeyError, TypeError) as err:
        print(f"loki rp: {type(err).__name__}: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
