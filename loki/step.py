"""The Wyrd step plugin that builds a design's dataset floors (spec 8.1)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from wyrd.model import Metric, RunSpec, StepSpec
from wyrd.settings import Settings
from wyrd.steps import arch_xml, finite_number, read_json_object

from loki.schemas import short_arch

_FLOORS = ("f1", "f2", "f3")


def expand_floor(floor: str, arch: str) -> str:
    """``f1`` becomes ``f1-<short arch>``; ``f2`` and ``f3`` are architecture independent."""
    return f"f1-{short_arch(arch)}" if floor == "f1" else floor


class DatasetStep:
    name = "loki-dataset"
    tools: tuple[str, ...] = ()
    is_vpr = False

    def __init__(self, spec: StepSpec) -> None:
        raw = spec.args.get("floors", ["f1", "f2"])
        if not isinstance(raw, list) or not all(isinstance(f, str) for f in raw):
            raise ValueError("step 'loki-dataset': floors must be a list of strings")
        bad = [f for f in raw if f not in _FLOORS]
        if bad or not raw:
            raise ValueError(f"step 'loki-dataset': floors must be among {_FLOORS}, got {raw}")
        self.floors: list[str] = list(raw)
        root = spec.args.get("odin3_root")
        if root is not None and not isinstance(root, str):
            raise ValueError("step 'loki-dataset': odin3_root must be a string")
        self.odin3_root = root

    def command(
        self, run: RunSpec, step_dir: Path, settings: Settings
    ) -> tuple[list[str], dict[str, str]]:
        root = self.odin3_root or os.environ.get("ODIN3_ROOT")
        if not root:
            raise ValueError("step 'loki-dataset': odin3_root is not set (step arg or $ODIN3_ROOT)")
        floors = ",".join(expand_floor(f, run.arch) for f in self.floors)
        argv = [
            sys.executable, "-m", "loki.build",
            "--design", run.design.name,
            "--files", *[str(f) for f in run.design.files],
            "--top", run.design.top or "",
            "--arch-xml", str(arch_xml(settings, run.arch)),
            "--floors", floors,
            "--out", str(step_dir / "dataset"),
        ]
        return argv, {"ODIN3_ROOT": root}

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
