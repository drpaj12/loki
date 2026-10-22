"""Benchmark discovery, fetching and Wyrd project generation (spec 8.2, plan Task 9)."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from loki.schemas import SCHEMA, dump_json

VERILOG_EVAL = {
    "url": "https://github.com/NMSU-PEARL/verilog-eval",
    "commit": "d60f0b10458746e2fefc2a98fa2455b77a32e8be",
    "license": "MIT",
}
ODIN3_SOURCE = {"url": "https://github.com/drpaj12/odin3", "license": "MIT"}
VE_COUNT = 156
ARCHS = ("k6_frac_N10_frac_chain_mem32K_40nm", "EArch")
SUITES = ("micro", "verilog-eval", "all")
_VE_DIR = "dataset_spec-to-rtl"


def discover_micros(odin3_root: Path) -> list[Path]:
    """The micro benchmarks of an Odin III checkout, sorted by name."""
    return sorted((odin3_root / "tests" / "micro" / "verilog" / "micro").glob("*.v"))


def _git(args: list[str], cwd: Path | None = None) -> str:
    proc = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *args],
        cwd=cwd, capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()[-300:]}")
    return proc.stdout.strip()


def _ve_files(cache: Path) -> list[Path]:
    return sorted((cache / _VE_DIR).glob("*_ref.sv"))


def fetch_verilog_eval(cache: Path) -> list[Path]:
    """Clone the pinned VerilogEval commit into ``cache`` (a new directory) and list its refs.

    The download is data: nothing in it is executed. A reused cache must be clean. Raises
    RuntimeError on local changes, symbolic links, or unless it holds 156 reference designs.
    """
    if (cache / ".git").is_dir():
        if _git(["rev-parse", "HEAD"], cache) != VERILOG_EVAL["commit"]:
            raise RuntimeError(f"{cache} holds another commit than {VERILOG_EVAL['commit']}")
        if _git(["status", "--porcelain"], cache):
            raise RuntimeError(f"{cache} has local changes; remove it to fetch again")
    else:
        if cache.exists() and any(cache.iterdir()):
            raise RuntimeError(f"{cache} is not empty and not a clone")
        cache.parent.mkdir(parents=True, exist_ok=True)
        _git(["clone", "--filter=blob:none", "--no-checkout", VERILOG_EVAL["url"], str(cache)])
        _git(["checkout", "--quiet", VERILOG_EVAL["commit"]], cache)
    files = _ve_files(cache)
    links = [f.name for f in files if f.is_symlink()]
    if links:
        raise RuntimeError(f"{cache} holds symbolic links: {', '.join(links[:3])}")
    if len(files) != VE_COUNT:
        raise RuntimeError(f"expected {VE_COUNT} VerilogEval designs, found {len(files)}")
    return files


def design_id(path: Path, suite: str) -> str:
    """``micro_<stem>`` or ``ve_<Prob...>`` (``_ref`` stripped); ``vtr_<stem>`` for VTR."""
    stem = path.stem
    if suite == "micro":
        return f"micro_{stem}"
    if suite == "verilog-eval":
        return "ve_" + stem.removesuffix("_ref")
    if suite == "vtr":
        return f"vtr_{stem}"
    raise ValueError(f"unknown suite {suite!r}")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _odin3_commit(odin3_root: Path) -> str:
    try:
        return _git(["rev-parse", "HEAD"], odin3_root)
    except (RuntimeError, OSError):
        return "unknown"


def _design_json(did: str, suite: str, src: Path, dest: Path, source: dict[str, str]) -> str:
    return dump_json(
        {
            "schema": SCHEMA,
            "design": did,
            "benchmark": suite,
            "top": "RefModule" if suite == "verilog-eval" else None,
            "files": [{"path": dest.name, "sha256": _sha256(src)}],
            "source": source,
        }
    )


def _copy_design(src: Path, suite: str, out: Path, source: dict[str, str]) -> str:
    did = design_id(src, suite)
    ddir = out / "designs" / did
    ddir.mkdir(parents=True, exist_ok=True)
    dest = ddir / f"{did}{src.suffix}"
    shutil.copyfile(src, dest)
    (ddir / "design.json").write_text(_design_json(did, suite, src, dest, source), encoding="utf-8")
    return did


def _q(text: str) -> str:
    return json.dumps(text)


def _toml(ids: list[str], files: dict[str, str], tops: dict[str, str]) -> str:
    lines = ['[project]', 'name = "loki-l0"', ""]
    for did in ids:
        lines += ["[[design]]", f"name = {_q(did)}", f"files = [{_q(files[did])}]"]
        if did in tops:
            lines.append(f"top = {_q(tops[did])}")
        lines.append("")
    lines += [
        "[recipe.l0]",
        'steps = [{ use = "loki-dataset", floors = ["f1", "f2"] }]',
        "",
        "[sweep]",
        'recipe = ["l0"]',
        "design = [" + ", ".join(_q(i) for i in ids) + "]",
        "arch = [" + ", ".join(_q(a) for a in ARCHS) + "]",
        "",
    ]
    return "\n".join(lines)


def write_project(suite: str, odin3_root: Path, cache: Path, out: Path) -> Path:
    """Write ``out/wyrd.toml`` and ``out/designs/<id>/`` for a suite; returns the toml path."""
    if suite not in SUITES:
        raise ValueError(f"unknown suite {suite!r}")
    ids: list[str] = []
    files: dict[str, str] = {}
    tops: dict[str, str] = {}
    if suite in ("micro", "all"):
        src = {**ODIN3_SOURCE, "commit": _odin3_commit(odin3_root)}
        for path in discover_micros(odin3_root):
            ids.append(_copy_design(path, "micro", out, src))
    if suite in ("verilog-eval", "all"):
        for path in fetch_verilog_eval(cache):
            did = _copy_design(path, "verilog-eval", out, dict(VERILOG_EVAL))
            ids.append(did)
            tops[did] = "RefModule"
    ids.sort()
    for did in ids:
        suffix = ".sv" if did.startswith("ve_") else ".v"
        files[did] = f"designs/{did}/{did}{suffix}"
    toml = out / "wyrd.toml"
    toml.write_text(_toml(ids, files, tops), encoding="utf-8")
    return toml
