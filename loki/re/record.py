"""The Mimir run record of one ``loki re`` run (``mimir-run.json`` in ``--out``).

Built from the run itself: the command line, the argparse options with the source of every value
(the command line, the environment, or the default cited ``file:line`` at the Loki commit), the
Loki and Odin III trees and the library binary used, time and peak RSS, and the sha256 of the
inputs and outputs. Format and rules: ``loki/runrecord.py`` (Mimir's
docs/specs/2026-10-28-mimir-run-record.md). Mimir is not imported.
"""

from __future__ import annotations

import argparse
import os
import resource
import sys
from collections.abc import Sequence
from pathlib import Path

import loki
from loki import runrecord as rr
from loki.re.loop import ReOptions
from loki.re.normalise import floor_from_path

SOURCE = "loki"
MAIN_FILE = "loki/re/main.py"
OUTPUTS = ("design.v", "overlay.json", "report.json", "report.md", "timing.json",
           "reverse-provenance.json", "score.json")
# options that name where files are, not how the run is configured
SKIP_DESTS = frozenset(("help", "netlist", "out", "score_dataset", "score_design", "seed"))
PATH_DESTS = frozenset(("odin3_root", "techlib", "calib", "keep_levels"))


def peak_rss_mib() -> float:
    """Peak resident set of this process and of the children it waited for, in MiB."""
    own = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    kids = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return max(own, kids) / 1024.0  # KiB on Linux


def _given(argv: Sequence[str], flag: str) -> bool:
    return any(a == flag or a.startswith(flag + "=") for a in argv)


def _flag_line(lines: list[str] | None, flag: str) -> int:
    """1-based line of the ``add_argument`` that declares ``flag``; 0 when not found."""
    return rr.line_of(lines, f'add_argument("{flag}"')


def add_option_params(rec: rr.RunRecorder, parser: argparse.ArgumentParser,
                      args: argparse.Namespace, argv: Sequence[str], tree: Path | None,
                      commit: str) -> None:
    """One parameter per option: ``given`` when it is on the command line, else ``default`` cited
    at the ``add_argument`` line of the Loki tree as committed."""
    lines = rr.git_show(tree, commit, MAIN_FILE)
    for action in parser._actions:  # argparse has no public list of the declared options
        if action.dest in SKIP_DESTS or not action.option_strings:
            continue
        flag = action.option_strings[-1]
        value = getattr(args, action.dest)
        text = "(empty)" if value in ("", None) else str(value)
        if action.dest in PATH_DESTS and value:
            text = rec.ph(str(Path(str(value)).resolve()))
        key = f"re.{flag.lstrip('-')}"
        if _given(argv, flag):
            rec.param(key, text, "given", "command line")
            continue
        n = _flag_line(lines, flag)
        if n:
            rec.param(key, text, "default", f"loki-tree {commit[:8]} {MAIN_FILE}:{n}")
        else:
            rec.param(key, text, "default-unrecorded", "Loki source tree or commit not available")


def _odin_facts() -> tuple[Path | None, str]:
    """(library path, version text) of the Odin III library the run loaded."""
    try:
        from loki.odin import odin_module

        inst = odin_module().default()
        lib = getattr(inst, "_library", None)
        return (Path(str(lib)) if lib else None), str(inst.version())
    except Exception:
        return None, ""


def _roles(argv: Sequence[str], args: argparse.Namespace) -> list[str]:
    """The command line with the netlist, the output directory and the design id as placeholders,
    so the command text of one setup does not change from design to design."""
    named = {"--out": "<out>", "--score-design": "<design>"}
    out: list[str] = []
    prev = ""
    for a in argv:
        out.append("<netlist>" if a == args.netlist else named.get(prev, a))
        prev = a
    return out


def build_record(parser: argparse.ArgumentParser, args: argparse.Namespace, argv: Sequence[str],
                 opts: ReOptions, out: Path, rc: int, seconds: float) -> rr.RunRecorder:
    netlist = opts.netlist.resolve()
    floor = floor_from_path(netlist) if opts.floor == "auto" else opts.floor
    design = args.score_design or netlist.stem
    arm = f"re-{floor}" + ("" if opts.features == "all" else f"-{opts.features}features")
    top = Path(loki.__file__).resolve().parents[1]
    loki_tree = top if (top / ".git").exists() else None
    roots = {"out": out, "netlist": netlist.parent}
    odin_root = opts.odin3_root.resolve() if opts.odin3_root else None
    if odin_root is not None:
        roots["odin3"] = odin_root
    if loki_tree is not None:
        roots["loki"] = loki_tree
    rec = rr.RunRecorder(SOURCE, design, arm, opts.seed, floor, roots)
    shown = ["loki", "re", *_roles(argv, args)]
    rec.add_step("loki-re", shown, rc, seconds, peak_rss_mib())
    lcommit = rr.git(loki_tree, "rev-parse", "HEAD") if loki_tree else ""
    rec.add_tool("loki", rr.tool_entry(loki_tree, None, loki.__version__, is_script=True))
    lib, version = _odin_facts()
    otree = odin_root if odin_root is not None and (odin_root / ".git").exists() else None
    rec.add_tool("odin3", rr.tool_entry(otree, lib, version))
    add_seed(rec, opts.seed, argv, loki_tree, lcommit)
    add_option_params(rec, parser, args, argv, loki_tree, lcommit)
    add_environment(rec, args, lib)
    rec.param("re.floor_resolved", floor, "given", "--floor, or read from the netlist path")
    if opts.calib is not None and opts.calib.is_file():
        rec.param("re.calib_sha256", rr.file_sha256(opts.calib), "given",
                  "sha256 of the calibration file")
    rec.add_input("netlist", netlist)
    for name in OUTPUTS:
        if (out / name).is_file():
            rec.add_artifact(name.split(".")[0], out / name)
    return rec


def add_environment(rec: rr.RunRecorder, args: argparse.Namespace, lib: Path | None) -> None:
    """The Odin III root and library that came from the environment, not the command line."""
    root = os.environ.get("ODIN3_ROOT", "")
    if not args.odin3_root and root:
        rec.param("re.odin3-root", rec.ph(str(Path(root).resolve())), "given",
                  "environment ODIN3_ROOT")
    if lib is not None:
        rec.param("env.odin3_lib", rec.ph(str(lib.resolve())), "given",
                  "the library the Odin III binding loaded")


def add_seed(rec: rr.RunRecorder, seed: int, argv: Sequence[str], tree: Path | None,
             commit: str) -> None:
    if _given(argv, "--seed"):
        rec.param("run.seed", str(seed), "given", "command line")
        return
    n = _flag_line(rr.git_show(tree, commit, MAIN_FILE), "--seed")
    if n:
        rec.param("run.seed", str(seed), "default", f"loki-tree {commit[:8]} {MAIN_FILE}:{n}")
    else:
        rec.param("run.seed", str(seed), "default-unrecorded",
                  "Loki source tree or commit not available")


def write_record(parser: argparse.ArgumentParser, args: argparse.Namespace, argv: Sequence[str],
                 opts: ReOptions, out: Path, rc: int, seconds: float) -> Path | None:
    """Write ``<out>/mimir-run.json``. A privacy hit or an unreadable input is reported on stderr
    (rule and key path, never a value) and no record is written; the exit code is unchanged."""
    path = out / rr.FILE_NAME
    try:
        build_record(parser, args, argv, opts, out, rc, seconds).write(path)
    except (rr.RecordRefused, OSError, ValueError) as exc:
        print(f"loki re: no run record written: {exc}", file=sys.stderr)
        return None
    return path

