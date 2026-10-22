"""Constants, hand-written validators and the deterministic JSON writer (spec section 6)."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re

SCHEMA = 1
KINDS = ("pi", "po", "lut", "ff", "const", "hard", "gate")
ROLES = ("datapath", "control", "mixed", "io", "const", "unknown")
FLOORS = ("f1-k6", "f1-earch", "f2", "f3")
SPLIT_SEED = "loki-l0-2026"
STATUSES = ("ok", "skipped", "fail")
BENCHMARKS = ("verilog-eval", "micro", "vtr")

LABEL_COLUMNS: tuple[str, ...] = (
    "node_id", "kind", "cell_type", "construct_type", "construct_types", "n_construct_cells",
    "module_path", "bus_name", "bit_index", "role", "hdl_file", "hdl_line", "hdl_col",
    "hdl_end_line", "hdl_end_col", "n_spans",
)
_TEXT_COLUMNS = frozenset(
    {"node_id", "kind", "cell_type", "construct_type", "construct_types", "module_path",
     "bus_name", "role", "hdl_file"}
)
_FEATURES = ("fan_in", "fan_out", "level", "lut_width", "lut_table", "is_seq", "is_const",
             "hard_ports")
_LABEL_KEYS = LABEL_COLUMNS[3:]
_NAME_RE = re.compile(r"^n[0-9]+$")


def dump_json(obj: object) -> str:
    """Deterministic JSON: sorted keys, indent 1, trailing newline."""
    return json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False) + "\n"


def split_of(design: str) -> str:
    """Design-level split (spec 6.9): first 8 bytes of sha256, big-endian, mod 100 < 80."""
    digest = hashlib.sha256(f"{SPLIT_SEED}:{design}".encode()).digest()
    return "train" if int.from_bytes(digest[:8], "big") % 100 < 80 else "test"


def _is_int(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _closed(obj: object, where: str, required: tuple[str, ...], optional: tuple[str, ...],
            errs: list[str]) -> dict[str, object] | None:
    """Check obj is a dict with exactly the allowed keys; return it when it is a dict."""
    if not isinstance(obj, dict):
        errs.append(f"{where}: not an object")
        return None
    for k in required:
        if k not in obj:
            errs.append(f"{where}: missing key {k!r}")
    for k in obj:
        if k not in required and k not in optional:
            errs.append(f"{where}: unknown key {k!r}")
    return obj


def _typed(d: dict[str, object], key: str, kind: type, where: str, errs: list[str]) -> None:
    if key not in d:
        return
    v = d[key]
    ok = _is_int(v) if kind is int else isinstance(v, kind) and not isinstance(v, bool)
    if not ok:
        errs.append(f"{where}: key {key!r} must be {kind.__name__}")


def _schema_ok(d: dict[str, object], where: str, errs: list[str]) -> None:
    if "schema" in d and d["schema"] != SCHEMA:
        errs.append(f"{where}: schema must be {SCHEMA}")


def _node_errors(node: object, idx: int, errs: list[str]) -> str | None:
    where = f"nodes[{idx}]"
    d = _closed(node, where, ("id", "kind", "features", "labels"), (), errs)
    if d is None:
        return None
    nid = d.get("id")
    if not isinstance(nid, str):
        errs.append(f"{where}: id must be a string")
        nid = None
    if "kind" in d and d["kind"] not in KINDS:
        errs.append(f"{where}: unknown kind {d['kind']!r}")
    feats = _closed(d.get("features", {}), f"{where}.features", _FEATURES, (), errs)
    if feats is not None:
        for k in _FEATURES:
            _typed(feats, k, str if k == "lut_table" else int, f"{where}.features", errs)
    labs = _closed(d.get("labels", {}), f"{where}.labels", _LABEL_KEYS, (), errs)
    if labs is not None:
        _label_errors(labs, f"{where}.labels", errs)
    return nid


def _label_errors(labs: dict[str, object], where: str, errs: list[str]) -> None:
    for k in _LABEL_KEYS:
        _typed(labs, k, str if k in _TEXT_COLUMNS else int, where, errs)
    if "role" in labs and labs["role"] not in ROLES:
        errs.append(f"{where}: unknown role {labs['role']!r}")


def validate_graph(obj: object) -> list[str]:
    """Errors of a graph.json object (spec 6.4); empty when valid."""
    errs: list[str] = []
    d = _closed(obj, "graph", ("schema", "design", "floor", "nodes", "edges"), (), errs)
    if d is None:
        return errs
    _schema_ok(d, "graph", errs)
    _typed(d, "design", str, "graph", errs)
    if "floor" in d and d["floor"] not in FLOORS:
        errs.append(f"graph: unknown floor {d['floor']!r}")
    nodes = d.get("nodes", [])
    ids: set[str] = set()
    if not isinstance(nodes, list):
        errs.append("graph: nodes must be a list")
        nodes = []
    for i, node in enumerate(nodes):
        nid = _node_errors(node, i, errs)
        if nid is None:
            continue
        if nid in ids:
            errs.append(f"nodes[{i}]: duplicate node id {nid!r}")
        ids.add(nid)
    _edge_errors(d.get("edges", []), ids, errs)
    return errs


def validate_words(obj: object) -> list[str]:
    """Errors of a words.json object (L1 spec 12.1, L0 spec 6.10)."""
    errs: list[str] = []
    d = _closed(obj, "words", ("schema", "words", "edges"), (), errs)
    if d is None:
        return errs
    _schema_ok(d, "words", errs)
    ids = _word_errors(d.get("words", []), errs)
    _word_edge_errors(d.get("edges", []), ids, errs)
    return errs


def _word_errors(words: object, errs: list[str]) -> set[int]:
    ids: set[int] = set()
    if not isinstance(words, list):
        errs.append("words: words must be a list")
        return ids
    keys = ("id", "type", "params", "fsm", "role", "const_ports", "footprint")
    for i, w in enumerate(words):
        where = f"words[{i}]"
        wd = _closed(w, where, keys, (), errs)
        if wd is None:
            continue
        _typed(wd, "id", int, where, errs)
        _typed(wd, "type", str, where, errs)
        _typed(wd, "params", dict, where, errs)
        if not isinstance(wd.get("fsm"), bool):
            errs.append(f"{where}: key 'fsm' must be bool")
        if wd.get("role") not in ROLES:
            errs.append(f"{where}: unknown role {wd.get('role')!r}")
        for k in ("const_ports", "footprint"):
            _typed(wd, k, list, where, errs)
        fp = wd.get("footprint")
        if isinstance(fp, list) and not all(isinstance(x, str) and _NAME_RE.match(x) for x in fp):
            errs.append(f"{where}: footprint entries must be n<k> names")
        wid = wd.get("id")
        if isinstance(wid, int) and not isinstance(wid, bool):
            if wid in ids:
                errs.append(f"{where}: duplicate word id {wid}")
            ids.add(wid)
    return ids


def _word_edge_errors(edges: object, ids: set[int], errs: list[str]) -> None:
    if not isinstance(edges, list):
        errs.append("words: edges must be a list")
        return
    for i, edge in enumerate(edges):
        where = f"edges[{i}]"
        e = _closed(edge, where, ("src", "src_port", "dst", "dst_port"), (), errs)
        if e is None:
            continue
        for k in ("src", "dst"):
            _typed(e, k, int, where, errs)
            if _is_int(e.get(k)) and e[k] not in ids:
                errs.append(f"{where}: edge endpoint {e[k]!r} is not a word")
        for k in ("src_port", "dst_port"):
            _typed(e, k, str, where, errs)


def _edge_errors(edges: object, ids: set[str], errs: list[str]) -> None:
    if not isinstance(edges, list):
        errs.append("graph: edges must be a list")
        return
    for i, edge in enumerate(edges):
        where = f"edges[{i}]"
        e = _closed(edge, where, ("src", "dst", "net", "pin"), (), errs)
        if e is None:
            continue
        for k in ("src", "dst", "net", "pin"):
            _typed(e, k, str, where, errs)
        for k in ("src", "dst"):
            if isinstance(e.get(k), str) and e[k] not in ids:
                errs.append(f"{where}: edge endpoint {e[k]!r} is not a node")


def validate_key(obj: object) -> list[str]:
    """Errors of a key.json object (spec 6.6)."""
    errs: list[str] = []
    d = _closed(obj, "key", ("schema", "design", "floor", "top", "nets", "cells", "ports"),
                (), errs)
    if d is None:
        return errs
    _schema_ok(d, "key", errs)
    for k in ("design", "top"):
        _typed(d, k, str, "key", errs)
    if "floor" in d and d["floor"] not in FLOORS:
        errs.append(f"key: unknown floor {d['floor']!r}")
    _map_errors(d.get("nets"), "nets", ("odin_id", "names"), errs)
    _map_errors(d.get("cells"), "cells", ("odin_id", "type", "name", "word_ids"), errs)
    ports = d.get("ports", [])
    if not isinstance(ports, list):
        errs.append("key: ports must be a list")
        return errs
    for i, p in enumerate(ports):
        pd = _closed(p, f"ports[{i}]", ("anon", "orig", "dir", "net"), (), errs)
        if pd is not None and "dir" in pd and pd["dir"] not in ("in", "out"):
            errs.append(f"ports[{i}]: dir must be in or out")
    return errs


def _map_errors(m: object, where: str, keys: tuple[str, ...], errs: list[str]) -> None:
    if not isinstance(m, dict):
        errs.append(f"key: {where} must be an object")
        return
    for name, entry in m.items():
        if not _NAME_RE.match(str(name)):
            errs.append(f"key.{where}: name {name!r} is not n<k>")
        _closed(entry, f"key.{where}[{name}]", keys, (), errs)


_COUNTS = ("nodes", "pi", "po", "lut", "ff", "const", "hard", "edges")


def validate_meta(obj: object) -> list[str]:
    """Errors of a meta.json object (spec 6.7)."""
    errs: list[str] = []
    req = ("schema", "design", "floor", "odin3_version", "abi_version", "script", "loki_version",
           "counts", "unmatched", "loops_cut", "equiv")
    d = _closed(obj, "meta", req, (), errs)
    if d is None:
        return errs
    _schema_ok(d, "meta", errs)
    if "floor" in d and d["floor"] not in FLOORS:
        errs.append(f"meta: unknown floor {d['floor']!r}")
    for k in ("design", "odin3_version", "loki_version"):
        _typed(d, k, str, "meta", errs)
    for k in ("abi_version", "unmatched", "loops_cut"):
        _typed(d, k, int, "meta", errs)
    if "script" in d and not isinstance(d["script"], list):
        errs.append("meta: script must be a list")
    counts = _closed(d.get("counts"), "meta.counts", _COUNTS, ("gate",), errs)
    if counts is not None:
        for k in counts:
            _typed(counts, k, int, "meta.counts", errs)
    _equiv_errors(d.get("equiv"), errs)
    return errs


def short_arch(arch: str) -> str:
    """The architecture's lower-case prefix before the first ``_`` (spec 3)."""
    return arch.split("_")[0].lower()


EQUIV_WARN_STATUSES = ("unproven", "skipped:blackbox-names")


def equiv_warnings(meta: object) -> list[str]:
    """Warnings for the equiv entries of a meta.json that are neither equivalent nor errors."""
    equiv = meta.get("equiv") if isinstance(meta, dict) else None
    if not isinstance(equiv, dict):
        return []
    return [
        f"equiv {name}: {res['status']}"
        for name, res in equiv.items()
        if isinstance(res, dict) and res.get("status") in EQUIV_WARN_STATUSES
    ]


def _equiv_errors(equiv: object, errs: list[str]) -> None:
    if not isinstance(equiv, dict):
        errs.append("meta: equiv must be an object")
        return
    for name, res in equiv.items():
        r = _closed(res, f"meta.equiv.{name}", ("status", "tool_exit"), ("detail", "mode"), errs)
        if r is not None:
            _typed(r, "status", str, f"meta.equiv.{name}", errs)
            _typed(r, "tool_exit", int, f"meta.equiv.{name}", errs)
            status = r.get("status")
            if isinstance(status, str) and status != "equivalent" and (
                status not in EQUIV_WARN_STATUSES
            ):
                errs.append(f"meta.equiv.{name}: status {status!r} is not equivalent")


def validate_design(obj: object) -> list[str]:
    """Errors of a design.json object (spec 6.8)."""
    errs: list[str] = []
    d = _closed(obj, "design", ("schema", "design", "benchmark", "top", "files", "source"),
                (), errs)
    if d is None:
        return errs
    _schema_ok(d, "design", errs)
    _typed(d, "design", str, "design", errs)
    if "benchmark" in d and d["benchmark"] not in BENCHMARKS:
        errs.append(f"design: unknown benchmark {d['benchmark']!r}")
    if d.get("top") is not None and not isinstance(d.get("top"), str):
        errs.append("design: top must be a string or null")
    files = d.get("files", [])
    if not isinstance(files, list):
        errs.append("design: files must be a list")
        files = []
    for i, f in enumerate(files):
        fd = _closed(f, f"files[{i}]", ("path", "sha256"), (), errs)
        if fd is not None:
            _typed(fd, "path", str, f"files[{i}]", errs)
            _typed(fd, "sha256", str, f"files[{i}]", errs)
    src = _closed(d.get("source"), "design.source", ("url", "commit", "license"), (), errs)
    if src is not None:
        for k in src:
            _typed(src, k, str, "design.source", errs)
    return errs


def validate_manifest(obj: object) -> list[str]:
    """Errors of a manifest.json object (spec 6.9)."""
    errs: list[str] = []
    req = ("schema", "created_by", "odin3_version", "split_seed", "split_rule", "designs")
    d = _closed(obj, "manifest", req, ("sources",), errs)
    if d is None:
        return errs
    _schema_ok(d, "manifest", errs)
    for k in ("created_by", "odin3_version", "split_seed", "split_rule"):
        _typed(d, k, str, "manifest", errs)
    designs = d.get("designs", [])
    if not isinstance(designs, list):
        errs.append("manifest: designs must be a list")
        return errs
    seen: set[str] = set()
    for i, entry in enumerate(designs):
        _manifest_entry_errors(entry, i, seen, errs)
    return errs


def _manifest_entry_errors(entry: object, idx: int, seen: set[str], errs: list[str]) -> None:
    where = f"designs[{idx}]"
    e = _closed(entry, where, ("design", "benchmark", "split", "floors"), (), errs)
    if e is None:
        return
    name = e.get("design")
    if isinstance(name, str):
        if name in seen:
            errs.append(f"{where}: duplicate design {name!r}")
        seen.add(name)
    if "benchmark" in e and e["benchmark"] not in BENCHMARKS:
        errs.append(f"{where}: unknown benchmark {e['benchmark']!r}")
    if "split" in e and e["split"] not in ("train", "test"):
        errs.append(f"{where}: split must be train or test")
    floors = e.get("floors")
    if not isinstance(floors, dict):
        errs.append(f"{where}: floors must be an object")
        return
    for fl, info in floors.items():
        if fl not in FLOORS:
            errs.append(f"{where}: unknown floor {fl!r}")
        i = _closed(info, f"{where}.floors.{fl}", ("status",), ("nodes", "reason", "message"), errs)
        if i is not None and i.get("status") not in STATUSES:
            errs.append(f"{where}.floors.{fl}: unknown status {i.get('status')!r}")


def validate_labels_csv(text: str) -> list[str]:
    """Errors of a labels.csv text (spec 6.5)."""
    errs: list[str] = []
    rows = list(csv.reader(io.StringIO(text, newline="")))
    if not rows or tuple(rows[0]) != LABEL_COLUMNS:
        return ["labels.csv: header differs from the spec"]
    for n, row in enumerate(rows[1:], start=2):
        if len(row) != len(LABEL_COLUMNS):
            errs.append(f"labels.csv line {n}: {len(row)} columns")
            continue
        errs.extend(_row_errors(dict(zip(LABEL_COLUMNS, row, strict=True)), n))
    return errs


def _row_errors(row: dict[str, str], n: int) -> list[str]:
    errs: list[str] = []
    if row["kind"] not in KINDS:
        errs.append(f"labels.csv line {n}: unknown kind {row['kind']!r}")
    if row["role"] not in ROLES:
        errs.append(f"labels.csv line {n}: unknown role {row['role']!r}")
    for col in LABEL_COLUMNS:
        if col in _TEXT_COLUMNS:
            continue
        try:
            int(row[col])
        except ValueError:
            errs.append(f"labels.csv line {n}: column {col} is not an integer")
    return errs
