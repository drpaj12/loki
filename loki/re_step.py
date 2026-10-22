"""The Wyrd step that runs ``loki re`` on one dataset floor design and scores it (L1 spec 13)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from wyrd.model import Metric, RunSpec, StepSpec
from wyrd.settings import Settings
from wyrd.steps import finite_number, read_json_object

from loki.re_project import SEP
from loki.schemas import FLOORS


def split_name(name: str) -> tuple[str, str]:
    """``<design id>__<floor>`` to ``(design id, floor)``; ``ValueError`` without a known floor."""
    design, sep, floor = name.rpartition(SEP)
    if not sep or not design or floor not in FLOORS:
        raise ValueError(f"design name {name!r} is not <id>{SEP}<floor> with floor in {FLOORS}")
    return design, floor


def _text(spec: StepSpec, key: str, required: bool) -> str | None:
    value = spec.args.get(key)
    if value is None:
        if required:
            raise ValueError(f"step 'loki-re': {key} is required")
        return None
    if not isinstance(value, str):
        raise ValueError(f"step 'loki-re': {key} must be a string")
    return value


class ReStep:
    name = "loki-re"
    tools: tuple[str, ...] = ()
    is_vpr = False

    def __init__(self, spec: StepSpec) -> None:
        self.calib = _text(spec, "calib", False)
        self.dataset = _text(spec, "dataset", True) or ""
        self.odin3_root = _text(spec, "odin3_root", False)

    def command(
        self, run: RunSpec, step_dir: Path, settings: Settings
    ) -> tuple[list[str], dict[str, str]]:
        design, floor = split_name(run.design.name)
        root = self.odin3_root or os.environ.get("ODIN3_ROOT")
        calib = "none" if self.calib is None else str(Path(self.calib) / f"{floor}.json")
        argv = [
            sys.executable, "-m", "loki.re.main", str(run.design.files[0]),
            "--floor", floor, "--calib", calib, "--out", str(step_dir / "re"),
            "--score-dataset", self.dataset, "--score-design", design,
        ]
        if root:
            argv += ["--odin3-root", root]
        return argv, ({"ODIN3_ROOT": root} if root else {})

    def collect(self, step_dir: Path) -> list[Metric]:
        data = read_json_object(step_dir / "metrics.json")
        if data is None:
            return []
        out: list[Metric] = []
        for key, value in data.items():
            number = finite_number(value)
            if number is not None:
                out.append(Metric(str(key), number))
        return out
