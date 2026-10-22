"""The ``loki`` command: bench init, assemble, check, re, score, score-all."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from loki.assemble import assemble, check_dataset, dataset_warnings
from loki.bench import SUITES, write_project
from loki.schemas import FLOORS, dump_json
from loki.score.metrics import aggregate, compare, score_run


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
    sc = sub.add_parser("score", help="score one loki re output against an L0 floor")
    sc.add_argument("re_dir")
    sc.add_argument("--dataset", required=True)
    sc.add_argument("--design", required=True)
    sc.add_argument("--floor", required=True, choices=FLOORS)
    sc.add_argument("--score-p", type=float, default=0.5)
    sa = sub.add_parser("score-all", help="aggregate score.json files of many runs")
    sa.add_argument("runs", help="directory searched for score.json files")
    sa.add_argument("--dataset", default="", help="score runs that lack a score.json")
    sa.add_argument("--out", required=True)
    sa.add_argument("--compare", default="", help="runs made with --features none")
    sa.add_argument("--score-p", type=float, default=0.5)
    sub.add_parser("re", help="reverse-engineer a netlist (loki re --help)", add_help=False)
    return ap


def _default_cache() -> Path:
    base = os.environ.get("XDG_CACHE_HOME")
    return (Path(base) if base else Path.home() / ".cache") / "loki" / "verilog-eval"


def _load_scores(runs: Path, dataset: str, score_p: float) -> list[dict[str, Any]]:
    """Every ``score.json`` under ``runs``; a run dir ``<design>__<floor>`` holding an
    ``overlay.json`` but no score is scored against ``dataset`` when one is given."""
    out: list[dict[str, Any]] = []
    for path in sorted(runs.rglob("score.json")):
        out.append(json.loads(path.read_text(encoding="utf-8")))
    if dataset:
        for ov in sorted(runs.rglob("overlay.json")):
            run = ov.parent
            if (run / "score.json").is_file():
                continue
            for name in (run.name, run.parent.name):
                design, sep, floor = name.rpartition("__")
                floor_dir = Path(dataset) / design / floor
                if sep and floor_dir.is_dir():
                    score = score_run(run, floor_dir, score_p)
                    (run / "score.json").write_text(dump_json(score), encoding="utf-8")
                    out.append(score)
                    break
    return out


def _score_all(args: argparse.Namespace) -> int:
    scores = _load_scores(Path(args.runs), args.dataset, args.score_p)
    if not scores:
        print(f"loki score-all: no score.json under {args.runs}", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    obj, md = aggregate(scores)
    (out / "scores.json").write_text(dump_json(obj), encoding="utf-8")
    (out / "scores.md").write_text(md, encoding="utf-8")
    print(f"scored {len(scores)} runs into {out}")
    if args.compare:
        base = _load_scores(Path(args.compare), args.dataset, args.score_p)
        if not base:
            print(f"loki score-all: no score.json under {args.compare}", file=sys.stderr)
            return 2
        abl, abl_md = compare(scores, base)
        (out / "ablation.json").write_text(dump_json(abl), encoding="utf-8")
        (out / "ablation.md").write_text(abl_md, encoding="utf-8")
    return 0


def _run(args: argparse.Namespace) -> int:
    if args.cmd == "score":
        floor_dir = Path(args.dataset) / args.design / args.floor
        if not floor_dir.is_dir():
            raise ValueError(f"{floor_dir}: no such floor directory")
        score = score_run(Path(args.re_dir), floor_dir, args.score_p)
        (Path(args.re_dir) / "score.json").write_text(dump_json(score), encoding="utf-8")
        print(f"wrote {Path(args.re_dir) / 'score.json'}")
        return 0
    if args.cmd == "score-all":
        return _score_all(args)
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
    """Exit 0 ok, 1 invariant errors, 2 usage. ``re`` is delegated to ``loki.re.main``."""
    words = list(sys.argv[1:] if argv is None else argv)
    if words[:1] == ["re"]:
        from loki.re.main import main as re_main

        return re_main(words[1:])
    try:
        args = _parser().parse_args(words)
    except SystemExit as exc:
        return 0 if exc.code in (0, None) else 2
    try:
        return _run(args)
    except (ValueError, RuntimeError, OSError) as err:
        print(f"loki: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
