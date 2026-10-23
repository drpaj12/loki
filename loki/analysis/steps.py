"""The four Wyrd step plugins that run L2 analyses on one dataset floor design (spec 10).

Same shape as L0's ``DatasetStep``: a class per step with ``name``, ``tools``, ``is_vpr``,
``command(run, step_dir, settings) -> (argv, env)`` and ``collect(step_dir) -> list[Metric]``.
Each step validates its project-file arguments in ``__init__`` and builds a
``python -m loki.analysis.run <kind> ...`` command, writing under ``<step_dir>/analysis``.
The runner's ``metrics.json`` (``<step_dir>/analysis/metrics.json``) becomes the step's
metrics; a plain ``<step_dir>/metrics.json`` is read first for older step layouts.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from wyrd.model import Metric, RunSpec, StepSpec
from wyrd.settings import Settings
from wyrd.steps import finite_number, read_json_object

from loki.schemas import FLOORS

_COMMON = ("dataset", "floor", "seed")
_BACKENDS = ("ext", "own", "default")


class _AnalysisStep:
    """One analysis kind as a Wyrd step: shared validation, argv building and metrics."""

    name = ""
    kind = ""
    # Kind options of spec 10, in the order they appear in the argv.
    options: tuple[str, ...] = ()
    choices: dict[str, tuple[str, ...]] = {}
    flags: tuple[str, ...] = ()
    has_design = True

    def __init__(self, spec: StepSpec) -> None:
        unknown = sorted(set(spec.args) - set(_COMMON) - set(self.options))
        if unknown:
            raise ValueError(f"step {self.name!r}: unknown argument {unknown[0]!r}")
        dataset = spec.args.get("dataset")
        if dataset is None:
            raise ValueError(f"step {self.name!r}: dataset is required")
        if not isinstance(dataset, str):
            raise ValueError(f"step {self.name!r}: dataset must be a string")
        self.dataset = dataset
        floor = spec.args.get("floor", "f2")
        if not isinstance(floor, str) or floor not in FLOORS:
            raise ValueError(f"step {self.name!r}: floor must be one of {FLOORS}, got {floor!r}")
        self.floor = floor
        seed = spec.args.get("seed", 0)
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError(f"step {self.name!r}: seed must be an integer")
        self.seed = seed
        self.option_values: dict[str, object] = {}
        for key in self.options:
            if key in spec.args:
                self.option_values[key] = self._check_option(key, spec.args[key])

    def _check_option(self, key: str, value: object) -> object:
        """Reject a wrong option type or a value outside the spec-10 choices."""
        allowed = self.choices.get(key)
        if key in self.flags:
            if not isinstance(value, bool):
                raise ValueError(f"step {self.name!r}: {key} must be a boolean")
            return value
        if isinstance(value, list):
            if not all(isinstance(item, str) for item in value):
                raise ValueError(
                    f"step {self.name!r}: {key} must be a string or a list of strings"
                )
            bad = [item for item in value if allowed is not None and item not in allowed]
            if bad:
                raise ValueError(
                    f"step {self.name!r}: {key} must be among {allowed}, got {bad!r}"
                )
            return list(value)
        if not isinstance(value, str):
            return value
        if allowed is not None and value not in allowed:
            raise ValueError(
                f"step {self.name!r}: {key} must be among {allowed}, got {value!r}"
            )
        return value

    def command(
        self, run: RunSpec, step_dir: Path, settings: Settings
    ) -> tuple[list[str], dict[str, str]]:
        argv = [sys.executable, "-m", "loki.analysis.run", self.kind, "--dataset", self.dataset]
        if self.has_design:
            argv += ["--design", run.design.name]
        argv += ["--floor", self.floor, "--out", str(step_dir / "analysis"),
                 "--seed", str(self.seed)]
        for key in self.options:
            if key in self.option_values:
                argv += self._option_argv(key, self.option_values[key])
        tool = os.environ.get("LOKI_GRAPHLET_TOOL")
        return argv, ({"LOKI_GRAPHLET_TOOL": tool} if tool else {})

    def _option_argv(self, key: str, value: object) -> list[str]:
        """One option as ``--flag value``; a true flag alone; a list comma-joined."""
        flag = "--" + key.replace("_", "-")
        if isinstance(value, bool):
            return [flag] if value else []
        if isinstance(value, list):
            return [flag, ",".join(str(item) for item in value)]
        return [flag, str(value)]

    def collect(self, step_dir: Path) -> list[Metric]:
        data = read_json_object(self._metrics_path(step_dir))
        if data is None:
            return []
        out: list[Metric] = []
        for key, value in data.items():
            number = finite_number(value)
            if number is not None:
                out.append(Metric(str(key), number))
        return out

    @staticmethod
    def _metrics_path(step_dir: Path) -> Path:
        """``<step_dir>/metrics.json``, else the runner's ``<step_dir>/analysis/metrics.json``."""
        direct = step_dir / "metrics.json"
        return direct if direct.is_file() else step_dir / "analysis" / "metrics.json"


class ExportStep(_AnalysisStep):
    name = "loki-export"
    kind = "export"
    options = ("format", "region", "no_structural")
    flags = ("no_structural",)


class ClusterStep(_AnalysisStep):
    name = "loki-cluster"
    kind = "cluster"
    options = ("method", "k", "resolution", "max_points", "features", "backend")
    choices = {
        "method": ("kmeans", "affinity", "spectral", "louvain", "all"),
        "backend": _BACKENDS,
    }


class GraphletStep(_AnalysisStep):
    name = "loki-graphlets"
    kind = "graphlets"
    options = ("backend", "size", "removal", "hub_threshold", "min_fanout", "force",
               "graphlet_tool", "licence")
    choices = {"backend": _BACKENDS, "removal": ("global", "none")}
    flags = ("force", "licence")


class GnnStep(_AnalysisStep):
    name = "loki-gnn"
    kind = "gnn"
    options = ("model", "target", "epochs", "hidden", "min_count", "features")
    choices = {"model": ("sage", "gcn"), "target": ("construct_type", "role")}
    has_design = False
