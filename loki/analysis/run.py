"""The L2 runner: ``python -m loki.analysis.run <kind> ...`` (L2 spec sections 10 and 11).

The CLI behind ``loki analyze``. Every kind reads one ``graph.json`` (``--graph``) or one design
of an L0 dataset (``--dataset/--design/--floor``, which must be ``ok`` in the manifest) and
writes the output tree of spec 11 under ``--out``, plus ``<out>/metrics.json`` with numbers for
the Wyrd step. Analyses never write inside the dataset directory.

Exit codes (spec 10): 0 ok; 1 analysis failure (``ClusterError``, ``RegionError``, backend
failure, invalid input); 2 usage; 3 missing extra or backend unavailable.

Heavy libraries belong to the extras: every handler calls :func:`loki.analysis.require`; the
analysis modules themselves import numpy and friends inside their functions, so importing this
module needs the standard library only.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from loki.analysis import KINDS, MissingExtra, require
from loki.analysis.cluster import METHODS, ClusterError, run_cluster
from loki.analysis.export import export_graph
from loki.analysis.gnn import FEATURES, GraphletInput, train_eval
from loki.analysis.graphio import Graph, iter_dataset, load_graph
from loki.analysis.graphlets import (
    BACKENDS,
    DEFAULT_BACKEND,
    BackendUnavailable,
    graphlet_features,
    load_orbits,
    run_graphlets,
)
from loki.analysis.graphlets.signals import SignalConfig
from loki.analysis.partition import load_partition
from loki.analysis.region import RegionError, parse_region
from loki.analysis.structural import run_structural
from loki.features import WL_ROUNDS
from loki.schemas import FLOORS, dump_json

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    import numpy.typing as npt

#: Default graphlet removal and size of the feature blocks that cluster and gnn compute.
_FEATURE_REMOVAL = "global"
_FEATURE_SIZE = 4


class UsageError(ValueError):
    """A command-line combination the kind handlers refuse (exit code 2)."""


def parse_features(s: str) -> list[str]:
    """The comma-separated ``--features`` names of spec 10 in their given order."""
    names = [part.strip() for part in s.split(",") if part.strip()]
    if not names:
        raise UsageError(f"--features needs one of {', '.join(FEATURES)}")
    unknown = [name for name in names if name not in FEATURES]
    if unknown:
        raise UsageError(
            f"unknown feature {unknown[0]!r}: use one of {', '.join(FEATURES)}"
        )
    return names


def write_metrics(out: Path, metrics: dict[str, float]) -> None:
    """Write ``<out>/metrics.json`` with numbers only and sorted keys (spec 11)."""
    for name, value in metrics.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"metric {name!r} is not a number: {value!r}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(dump_json(metrics), encoding="utf-8")


def resolve_input(args: argparse.Namespace) -> tuple[Graph, str]:
    """The input graph and its manifest split from ``--graph`` or the dataset options (spec 10).

    In dataset mode the design must be ``ok`` in ``manifest.json``; a missing design or a floor
    with another status raises ``ValueError`` carrying that one-line reason. The split is the
    manifest's, or ``""`` for a bare ``graph.json``.
    """
    graph_arg = getattr(args, "graph", None)
    dataset = getattr(args, "dataset", None)
    if graph_arg:
        return load_graph(Path(str(graph_arg))), ""
    if not dataset:
        raise UsageError("give --graph or --dataset/--design/--floor")
    design = getattr(args, "design", None)
    floor = getattr(args, "floor", None)
    if not design or not floor:
        raise UsageError("--dataset needs --design and --floor")
    root = Path(str(dataset))
    split = _manifest_split(root, str(design), str(floor))
    graph_path = root / str(design) / str(floor) / "graph.json"
    return load_graph(graph_path), split


def _manifest_split(root: Path, design: str, floor: str) -> str:
    """The split of an ``ok`` design/floor of ``manifest.json``, else a one-line ``ValueError``."""
    path = root / "manifest.json"
    manifest: Any = json.loads(path.read_text(encoding="utf-8"))
    for entry in manifest.get("designs", []):
        if str(entry.get("design")) != design:
            continue
        info = entry.get("floors", {}).get(floor)
        status = "" if not isinstance(info, dict) else str(info.get("status", ""))
        if status != "ok":
            raise ValueError(
                f"{design}/{floor}: floor status {status or 'missing'!r} is not ok"
            )
        return str(entry.get("split", ""))
    raise ValueError(f"design {design!r} is not in {path}")


def _out(args: argparse.Namespace) -> Path:
    """``--out`` or a usage error (the ``graphlets --licence`` path needs none)."""
    raw = str(getattr(args, "out", ""))
    if not raw:
        raise UsageError("--out is required")
    return Path(raw)


def _design_dir(out: Path, g: Graph, name: str) -> Path:
    """``<out>/<design>/<floor>/<name>`` of spec 11."""
    return out / g.design / g.floor / name


def _load_or_count_orbits(
    g: Graph, out: Path, backend: str, *, removal: str = _FEATURE_REMOVAL
) -> tuple[npt.NDArray[Any], npt.NDArray[Any]]:
    """The graph's orbits and roles, counted first with :func:`run_graphlets` when missing."""
    orbit_dir = _design_dir(out, g, "graphlets")
    try:
        return load_orbits(g, backend, removal, orbit_dir)
    except FileNotFoundError:
        run_graphlets(
            g, backend, orbit_dir, size=_FEATURE_SIZE, removal=removal,
            cfg=SignalConfig(), hub_threshold=1000,
        )
        return load_orbits(g, backend, removal, orbit_dir)


@contextlib.contextmanager
def _tool_override(backend: str, tool: str) -> Iterator[None]:
    """Register an ORCA counter built from ``--graphlet-tool`` for the duration of the call."""
    from loki.analysis.graphlets.ext import OrcaCounter

    key = DEFAULT_BACKEND if backend == "default" else backend
    if not tool or key != OrcaCounter.name:
        yield
        return
    previous = BACKENDS.get(key)
    BACKENDS[key] = OrcaCounter(Path(tool))
    try:
        yield
    finally:
        if previous is None:
            BACKENDS.pop(key, None)
        else:
            BACKENDS[key] = previous


def _parse_k(raw: str) -> int | str:
    """``--k``: a positive integer or ``auto`` (spec 7)."""
    if raw == "auto":
        return "auto"
    try:
        return int(raw)
    except ValueError as exc:
        raise UsageError(f"--k must be an integer or 'auto', got {raw!r}") from exc


def _run_export(args: argparse.Namespace) -> int:
    require("analysis")
    formats = [part.strip() for part in str(args.format).split(",") if part.strip()]
    if not formats:
        raise UsageError("--format needs at least one of edgelist, graphml, pyg")
    g, _split = resolve_input(args)
    out = _out(args)
    region = None
    if args.region:
        region = parse_region(g, str(args.region))
    paths = export_graph(
        g, region, formats, _design_dir(out, g, "export"),
        include_structural=not bool(args.no_structural),
    )
    write_metrics(out, {"files": len(paths)})
    print(f"exported {len(paths)} file(s) into {_design_dir(out, g, 'export')}")
    return 0


def _run_structural(args: argparse.Namespace) -> int:
    require("analysis")
    g, _split = resolve_input(args)
    out = _out(args)
    path = run_structural(
        g, _design_dir(out, g, "structural"), variant=str(args.wl_variant),
        rounds=int(args.rounds), with_quotient=bool(args.quotient),
    )
    record: Any = json.loads(path.read_text(encoding="utf-8"))
    classes = record["classes_per_round"]
    stable = record["stable_round"]
    write_metrics(out, {
        "stable_round": -1 if stable is None else float(stable),
        "classes_last_round": float(classes[-1]) if classes else 0.0,
        "npn_classes": float(record["npn"]["classes"]),
        "seconds": float(record["seconds"]),
    })
    print(f"wrote {path}")
    return 0


def _run_cluster(args: argparse.Namespace) -> int:
    require("analysis")
    names = parse_features(str(args.features))
    if "wl" in names or "npn" in names:
        raise UsageError("wl and npn are categorical ids; only gnn uses them")
    g, _split = resolve_input(args)
    out = _out(args)
    extra: npt.NDArray[Any] | None = None
    if "graphlet" in names:
        orbits, roles = _load_or_count_orbits(g, out, str(args.backend))
        extra = graphlet_features(orbits, roles)
    methods = list(METHODS) if args.method == "all" else [str(args.method)]
    paths = run_cluster(
        g, methods, _design_dir(out, g, "partition"), k=_parse_k(str(args.k)),
        seed=int(args.seed), resolution=float(args.resolution),
        max_points=int(args.max_points), extra=extra,
    )
    metrics: dict[str, float] = {}
    for path in paths:
        partition = load_partition(path)
        metrics[f"n_clusters_{partition.method}"] = float(partition.n_clusters)
        for name in ("modularity", "nmi_module_path"):
            value = partition.quality.get(name)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                metrics[f"{name}_{partition.method}"] = float(value)
    write_metrics(out, metrics)
    print(f"wrote {len(paths)} partition(s)")
    return 0


def _run_graphlets(args: argparse.Namespace) -> int:
    require("analysis")
    g, _split = resolve_input(args)
    out = _out(args)
    cfg = SignalConfig(min_fanout=int(args.min_fanout))
    with _tool_override(str(args.backend), str(args.graphlet_tool)):
        path = run_graphlets(
            g, str(args.backend), _design_dir(out, g, "graphlets"),
            size=int(args.size), removal=str(args.removal), cfg=cfg,
            hub_threshold=int(args.hub_threshold), force=bool(args.force),
        )
    record: Any = json.loads(path.read_text(encoding="utf-8"))
    removed = record["removed_edges"]
    write_metrics(out, {
        "removed_edges_total": float(sum(int(value) for value in removed.values())),
        "dropped_hubs": float(len(record["dropped_hubs"])),
        "clock_domains": float(record["clock_domains"]),
        "nodes": float(record["n_nodes"]),
        "edges": float(record["n_edges"]),
        "seconds": float(record["seconds"]),
    })
    print(f"wrote {path}")
    return 0


def _run_gnn(args: argparse.Namespace) -> int:
    require("gnn")
    dataset = Path(str(args.dataset))
    floor = str(args.floor)
    out = _out(args)
    features = parse_features(str(args.features))
    extra: dict[str, GraphletInput] | None = None
    if "graphlet" in features:
        extra = {}
        for entry in iter_dataset(dataset, floor):
            g = load_graph(entry.graph_path)
            orbits, roles = _load_or_count_orbits(g, out, "default")
            extra[g.design] = GraphletInput(orbits, roles)
    result = train_eval(
        dataset, floor, out / "gnn", model=str(args.model), target=str(args.target),
        epochs=int(args.epochs), hidden=int(args.hidden), min_count=int(args.min_count),
        seed=int(args.seed), features=features, extra=extra,
    )
    test = cast(dict[str, Any], result["test"])
    baselines = cast(dict[str, Any], result["baselines"])
    majority = cast(dict[str, Any], baselines["majority"])
    write_metrics(out, {
        "test_accuracy": float(test["accuracy"]),
        "test_macro_f1": float(test["macro_f1"]),
        "baseline_majority_accuracy": float(majority["accuracy"]),
    })
    print(f"wrote {out / 'gnn'}")
    return 0


_HANDLERS: dict[str, Callable[[argparse.Namespace], int]] = {
    "export": _run_export,
    "structural": _run_structural,
    "cluster": _run_cluster,
    "graphlets": _run_graphlets,
    "gnn": _run_gnn,
}


def _parser() -> argparse.ArgumentParser:
    """The spec-10 CLI: one sub-subparser per analysis kind."""
    ap = argparse.ArgumentParser(prog="loki analyze")
    sub = ap.add_subparsers(dest="kind", required=True)
    for kind in KINDS:
        parser = sub.add_parser(kind)
        parser.add_argument("--out", default="")
        parser.add_argument("--seed", type=int, default=0)
        if kind == "gnn":
            parser.add_argument("--dataset", required=True)
            parser.add_argument("--floor", required=True, choices=FLOORS)
            parser.add_argument("--model", choices=("sage", "gcn"), default="sage")
            parser.add_argument("--target", choices=("construct_type", "role"),
                                default="construct_type")
            parser.add_argument("--epochs", type=int, default=100)
            parser.add_argument("--hidden", type=int, default=64)
            parser.add_argument("--min-count", type=int, default=5)
            parser.add_argument("--features", default="node")
            continue
        inputs = parser.add_mutually_exclusive_group()
        inputs.add_argument("--graph")
        inputs.add_argument("--dataset")
        parser.add_argument("--design")
        parser.add_argument("--floor", choices=FLOORS)
        if kind == "export":
            parser.add_argument("--format", default="edgelist")
            parser.add_argument("--region", default="")
            parser.add_argument("--no-structural", action="store_true")
        elif kind == "structural":
            parser.add_argument("--wl-variant", choices=("npn/both", "table/both"),
                                default="npn/both")
            parser.add_argument("--rounds", type=int, default=WL_ROUNDS)
            parser.add_argument("--quotient", action="store_true")
        elif kind == "cluster":
            parser.add_argument("--method", choices=(*METHODS, "all"), default="all")
            parser.add_argument("--k", default="auto")
            parser.add_argument("--resolution", type=float, default=1.0)
            parser.add_argument("--max-points", type=int, default=3000)
            parser.add_argument("--features", default="node")
            parser.add_argument("--backend", default="default")
        else:
            parser.add_argument("--backend", choices=("ext", "own", "default"),
                                default="default")
            parser.add_argument("--size", type=int, choices=(4, 5), default=4)
            parser.add_argument("--removal", choices=("global", "none"), default="global")
            parser.add_argument("--hub-threshold", type=int, default=1000)
            parser.add_argument("--min-fanout", type=int, default=SignalConfig().min_fanout)
            parser.add_argument("--force", action="store_true")
            parser.add_argument("--graphlet-tool", default="")
            parser.add_argument("--licence", action="store_true")
    return ap


def main(argv: Sequence[str] | None = None) -> int:
    """Run one ``loki analyze`` command; the spec-10 exit codes are in the module docstring."""
    words = list(sys.argv[1:] if argv is None else argv)
    try:
        args = _parser().parse_args(words)
    except SystemExit as exc:
        return 0 if exc.code in (0, None) else 2
    try:
        if args.kind == "graphlets" and bool(getattr(args, "licence", False)):
            from loki.analysis.graphlets.ext import ORCA_CITATION, ORCA_LICENCE

            print(ORCA_LICENCE)
            print(ORCA_CITATION)
            return 0
        return _HANDLERS[str(args.kind)](args)
    except (MissingExtra, BackendUnavailable) as err:
        print(f"loki analyze: {err}", file=sys.stderr)
        return 3
    except UsageError as err:
        print(f"loki analyze: {err}", file=sys.stderr)
        return 2
    except (ClusterError, RegionError, ValueError, OSError) as err:
        print(f"loki analyze: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
