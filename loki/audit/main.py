"""``loki audit``: ``snap`` writes the pass-by-pass snapshots of one design, ``report`` audits them.

Exit 0 done, 2 usage or Odin III refusal."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from loki.audit.report import audit_design
from loki.audit.snap import run_snapshots
from loki.odin import OdinSkip
from loki.schemas import dump_json


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="loki audit", description="L15 loss audit (round 6)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sn = sub.add_parser("snap", help="run the f2 flow pass by pass; write maps into --out")
    sn.add_argument("files", nargs="+")
    sn.add_argument("--arch-xml", required=True)
    sn.add_argument("--out", required=True)
    sn.add_argument("--top", default="")
    sn.add_argument("--no-detect", action="store_true", help="skip the S7/S8 BLIF files")
    rp = sub.add_parser("report", help="audit the snapshots of one design")
    rp.add_argument("snapdir")
    rp.add_argument("--design", required=True)
    rp.add_argument("--level", choices=("stmt", "branch"), default="stmt")
    rp.add_argument("--out", required=True)
    return ap


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(list(sys.argv[1:] if argv is None else argv))
    except SystemExit as exc:
        return 0 if exc.code in (0, None) else 2
    try:
        if args.cmd == "snap":
            run_snapshots([Path(f) for f in args.files], Path(args.arch_xml), Path(args.out),
                          args.top or None, not args.no_detect)
        else:
            res = audit_design(Path(args.snapdir), args.design, args.level)
            Path(args.out).write_text(dump_json(res), encoding="utf-8")
    except (OdinSkip, ValueError, OSError) as err:
        print(f"loki audit: {err}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
