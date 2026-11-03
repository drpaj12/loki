"""Reader for the Odin III provenance step files (Odin III v1.4, ``<out>/prov``).

A run directory holds ``index.json``, one header per flow step and one objects file per step that
creates objects (JSON Lines). Objects of each stage link to objects of the previous stage, so an
object of any stage (a placed cell, an extracted cell, a LUT) resolves back to the HDL.

    run = read_run(Path("out/prov"))
    cell = run.objects["recovered:o3__c8"]
    res = resolve(run, cell)       # res.path, res.weakest, res.sources, res.reached_hdl

Contract (Odin III ``docs/user/provenance-files.md``): ``schema`` 1 only; unknown fields are
ignored; the sha256 of every file is checked against the index unless ``verify`` is False.
Standard library only; no Odin III import.
"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA = 1
RANK = {"ambiguous": 0, "low": 1, "medium": 2, "high": 3, "exact": 4}
TERMINAL_STAGES = ("hdl", "ir")


class ProvError(ValueError):
    """A run directory that breaks the contract (schema, sha256, a dangling link)."""


@dataclass(frozen=True)
class Link:
    to: str
    kind: str
    confidence: str


@dataclass(frozen=True)
class Source:
    file: str
    span: str


@dataclass(frozen=True)
class ProvObject:
    id: str
    stage: str
    kind: str
    name: str
    origin: str
    type: str = ""
    links: tuple[Link, ...] = ()
    src: tuple[Source, ...] = ()
    recs: tuple[str, ...] = ()
    attrs: Mapping[str, Any] = field(default_factory=dict)

    @property
    def has_hdl_chain(self) -> bool:
        return self.origin == "hdl"

    @property
    def physical_step(self) -> str | None:
        """The kind of the inserting step for ``physical:KIND``, else None."""
        return self.origin.split(":", 1)[1] if self.origin.startswith("physical:") else None


@dataclass(frozen=True)
class Step:
    id: str
    stage: str
    file: str
    objects_file: str | None
    count: int
    needs: tuple[str, ...]
    tool: Mapping[str, str]
    header: Mapping[str, Any]


@dataclass
class ProvRun:
    root: Path
    index: Mapping[str, Any]
    steps: list[Step]
    objects: dict[str, ProvObject]
    by_stage: dict[str, list[str]]

    def step(self, step_id: str) -> Step:
        for s in self.steps:
            if s.id == step_id:
                return s
        raise KeyError(step_id)

    def stage_objects(self, stage: str) -> list[ProvObject]:
        return [self.objects[i] for i in self.by_stage.get(stage, [])]


@dataclass(frozen=True)
class Resolution:
    """Where an object comes from. ``path`` runs from the object to the first object of a terminal
    stage (``hdl`` or ``ir``) by the strongest links; ``weakest`` is the lowest confidence on it;
    ``sources`` are the spans of every terminal object reachable; ``reached_hdl`` is False for an
    object with a physical origin or no link."""

    path: tuple[ProvObject, ...]
    weakest: str
    sources: tuple[Source, ...]
    reached_hdl: bool
    origin: str


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _object(row: Mapping[str, Any]) -> ProvObject:
    return ProvObject(
        id=row["id"], stage=row["stage"], kind=row["kind"], name=row.get("name", ""),
        origin=row["origin"], type=row.get("type", ""),
        links=tuple(Link(x["to"], x["kind"], x["confidence"]) for x in row.get("links", [])),
        src=tuple(Source(x["file"], x["span"]) for x in row.get("src", [])),
        recs=tuple(row.get("recs", [])), attrs=dict(row.get("attrs", {})))


def read_run(path: Path, verify: bool = True) -> ProvRun:
    """Read ``path`` (the ``prov`` directory). ProvError for schema, sha256 or dangling links."""
    index_path = path / "index.json"
    if not index_path.is_file():
        raise ProvError(f"{index_path}: no index.json (partial run?)")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if index.get("schema") != SCHEMA or index.get("kind") != "odin3-prov-index":
        raise ProvError(f"{index_path}: schema {index.get('schema')!r} is not supported "
                        f"(this reader reads {SCHEMA})")
    steps: list[Step] = []
    objects: dict[str, ProvObject] = {}
    by_stage: dict[str, list[str]] = {}
    for entry in index["steps"]:
        head_path = path / entry["file"]
        if verify and _sha(head_path) != entry["sha256"]:
            raise ProvError(f"{head_path}: sha256 differs from the index")
        header = json.loads(head_path.read_text(encoding="utf-8"))
        if header.get("schema") != SCHEMA:
            raise ProvError(f"{head_path}: schema {header.get('schema')!r} is not supported")
        steps.append(Step(entry["id"], entry["stage"], entry["file"], entry.get("objects"),
                          entry["count"], tuple(entry.get("needs", [])), entry["tool"], header))
        if entry.get("objects"):
            obj_path = path / entry["objects"]
            if verify and _sha(obj_path) != entry["objects_sha256"]:
                raise ProvError(f"{obj_path}: sha256 differs from the index")
            for line in obj_path.read_text(encoding="utf-8").splitlines():
                obj = _object(json.loads(line))
                objects[obj.id] = obj
                by_stage.setdefault(obj.stage, []).append(obj.id)
    for obj in objects.values():
        for link in obj.links:
            if link.to not in objects:
                raise ProvError(f"{obj.id}: link target {link.to} is not an object")
    return ProvRun(path, index, steps, objects, by_stage)


def _best_first(links: tuple[Link, ...]) -> list[Link]:
    return sorted(links, key=lambda x: -RANK.get(x.confidence, 0))


def resolve(run: ProvRun, target: ProvObject | str) -> Resolution:
    """Walk ``links`` back to stage ``hdl`` or ``ir``. The path is the shortest by number of
    links, ties broken by the stronger link; ``sources`` collects the spans of every terminal
    object reached on any path."""
    start = run.objects[target] if isinstance(target, str) else target
    prev: dict[str, tuple[str, Link] | None] = {start.id: None}
    queue: deque[ProvObject] = deque([start])
    terminal: ProvObject | None = None
    sources: list[Source] = []
    while queue:
        cur = queue.popleft()
        if cur.stage in TERMINAL_STAGES and cur.origin == "hdl":
            terminal = terminal or cur
            sources.extend(s for s in cur.src if s not in sources)
            continue
        for link in _best_first(cur.links):
            if link.to not in prev:
                prev[link.to] = (cur.id, link)
                queue.append(run.objects[link.to])
    if terminal is None:
        return Resolution((start,), "exact", (), False, start.origin)
    path = [terminal]
    weakest = "exact"
    cur_id = terminal.id
    while prev[cur_id] is not None:
        step = prev[cur_id]
        assert step is not None
        parent, link = step
        weakest = link.confidence if RANK[link.confidence] < RANK[weakest] else weakest
        path.append(run.objects[parent])
        cur_id = parent
    path.reverse()
    return Resolution(tuple(path), weakest, tuple(sources), True, start.origin)


def summary(run: ProvRun) -> list[str]:
    """One line per step (stage, objects, share with an HDL chain) for ``loki prov``."""
    lines = [f"flow {run.index['flow']}  design {run.index['design']}  top {run.index['top']}"]
    for step in run.steps:
        ids = run.by_stage.get(step.stage, []) if step.objects_file else []
        mine = [o for o in (run.objects[i] for i in ids) if _of_step(run, o, step)]
        hdl = sum(1 for o in mine if o.origin == "hdl")
        check = step.header.get("check")
        tail = f"  check {check['name']}: {check['result']}" if check else ""
        lines.append(f"  {step.id:<10} {step.stage:<10} objects {step.count:>6}"
                     f"  hdl chain {hdl:>6}{tail}")
    return lines


def _of_step(run: ProvRun, obj: ProvObject, step: Step) -> bool:
    """Whether obj was written by step (objects of one stage may come from several steps)."""
    owners = [s for s in run.steps if s.stage == obj.stage and s.objects_file]
    return len(owners) == 1 or any(s.id == step.id for s in owners)


def main(argv: list[str]) -> int:
    """``loki prov RUN_DIR [--resolve OBJECT_ID]``: print a run's steps, or one object's chain.
    Exit 0 ok, 1 unknown object, 2 the run breaks the contract."""
    import argparse

    ap = argparse.ArgumentParser(prog="loki prov", description=(__doc__ or "").split("\n")[0])
    ap.add_argument("run", type=Path, help="the prov directory of an Odin III run")
    ap.add_argument("--resolve", metavar="ID", help="print the chain of one object to the HDL")
    ap.add_argument("--no-verify", action="store_true", help="skip the sha256 checks")
    ns = ap.parse_args(argv)
    try:
        run = read_run(ns.run, verify=not ns.no_verify)
    except ProvError as err:
        print(f"loki prov: {err}")
        return 2
    if ns.resolve is None:
        print("\n".join(summary(run)))
        return 0
    if ns.resolve not in run.objects:
        print(f"loki prov: no object {ns.resolve}")
        return 1
    res = resolve(run, ns.resolve)
    for obj in res.path:
        print(f"{obj.id}  [{obj.stage}/{obj.kind}]  {obj.origin}")
    print(f"reached hdl: {res.reached_hdl}  weakest link: {res.weakest}")
    for src in res.sources:
        print(f"  source {src.file}:{src.span}")
    return 0
