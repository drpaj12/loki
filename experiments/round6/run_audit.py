"""Stage 2: audit every snapshot directory and write the L15 tables (CSV).

``python run_audit.py [--force]`` reads ``<DATA>/snap/<set>/<design>`` (ok rows of
``status.csv``), writes ``<AUDIT>/<set>/<design>.<level>.json`` (``$LOKI_R6_AUDIT``, default
``<DATA>/audit``) and, here in the checkout, ``l15_*.csv``."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from typing import Any

from r6lib import AUDIT, DATA, HERE, SETS, read_csv, write_csv

from loki.audit.loss import PERSIST_DRAWS, REASONS
from loki.audit.report import audit_design
from loki.audit.snap import PASSES
from loki.schemas import dump_json

LEVELS = ("stmt", "branch")
HW = ("fsm", "register", "arith", "mux", "compare", "logic")
PASS_LABEL = [f"S{k}_{n}{'_full' if a == '-full' else ''}" for k, (n, a) in enumerate(PASSES, 1)]


def source_hash() -> str:
    """Hash of the audit sources: a cached per-design JSON is valid only for this hash."""
    h = hashlib.sha256()
    for f in sorted((HERE.parents[1] / "loki" / "audit").glob("*.py")):
        h.update(f.name.encode() + b"\0" + f.read_bytes())
    return h.hexdigest()[:16]


def audit_all(force: bool = False) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """(set, level) to the audit objects of the designs whose snapshots are ok. A cached JSON is
    reused only when it carries the current ``source_hash``; ``force`` recomputes all."""
    stamp = source_hash()
    out: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for name in SETS:
        root = DATA / "snap" / name
        status = read_csv(root / "status.csv")
        (AUDIT / name).mkdir(parents=True, exist_ok=True)
        for level in LEVELS:
            res: list[dict[str, Any]] = []
            for row in status:
                if row["status"] != "ok":
                    continue
                path = AUDIT / name / f"{row['design']}.{level}.json"
                cached = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
                if force or cached.get("source_hash") != stamp:
                    cached = audit_design(root / row["design"], row["design"], level)
                    cached["source_hash"] = stamp
                    path.write_text(dump_json(cached), encoding="utf-8")
                res.append(cached)
            out[(name, level)] = res
    return out


def pooled(results: dict[tuple[str, str], list[dict[str, Any]]]
           ) -> dict[tuple[str, str], list[dict[str, Any]]]:
    allr = {}
    for level in LEVELS:
        allr[("ALL", level)] = [d for s in SETS for d in results[(s, level)]]
    return {**results, **allr}


def _units(designs: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    return [(d["design"], u) for d in designs for u in d["units"]]


def _pct(vals: list[int], q: float) -> float:
    """Nearest-rank percentile of a list of per-draw totals."""
    xs = sorted(vals)
    return float(xs[min(len(xs) - 1, max(0, round(q * len(xs) + 0.5) - 1))])


def table_kind_pass(results: dict[tuple[str, str], list[dict[str, Any]]]) -> list[list[Any]]:
    """set, level, axis, kind, pass, at-risk units, real first losses, Stage-0 null expected, and
    the persistence null (Amendment A): mean and 2.5 / 97.5 percentile of the per-draw totals."""
    rows: list[list[Any]] = []
    for (name, level), designs in sorted(results.items()):
        real: Counter[tuple[str, str, int]] = Counter()
        risk: Counter[tuple[str, str, int]] = Counter()
        null: defaultdict[tuple[str, str, int], float] = defaultdict(float)
        draws: defaultdict[tuple[str, str, int], list[int]] = defaultdict(
            lambda: [0] * PERSIST_DRAWS)
        for _, u in _units(designs):
            hw2 = "hier" if u["kind"] == "INSTANCE" else u["hw"]  # post-data, exploratory axis
            for axis, kind in (("hw", u["hw"]), ("ast", u["kind"]), ("hw2", hw2)):
                for k, frac in u["null"].items():
                    risk[(axis, kind, int(k))] += 1
                    null[(axis, kind, int(k))] += frac
                    mask = int(u["pnull"][k], 16)
                    acc = draws[(axis, kind, int(k))]
                    for d in range(PERSIST_DRAWS):
                        acc[d] += (mask >> d) & 1
                if "loss" in u:
                    real[(axis, kind, u["loss"]["at"])] += 1
        for key in sorted(set(risk) | set(real)):
            axis, kind, k = key
            dr = draws[key] if key in draws else [0] * PERSIST_DRAWS
            rows.append([name, level, axis, kind, PASS_LABEL[k - 1], risk[key], real[key],
                         f"{null[key]:.3f}", f"{sum(dr) / len(dr):.3f}",
                         f"{_pct(dr, 0.025):.0f}", f"{_pct(dr, 0.975):.0f}"])
    return rows


def table_reason(results: dict[tuple[str, str], list[dict[str, Any]]]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for (name, level), designs in sorted(results.items()):
        cnt: Counter[tuple[str, int]] = Counter()
        for _, u in _units(designs):
            if "loss" in u:
                cnt[(u["loss"]["reason"], u["loss"]["at"])] += 1
        for reason in REASONS:
            for k in range(2, len(PASSES) + 1):
                rows.append([name, level, reason, PASS_LABEL[k - 1], cnt[(reason, k)]])
    return rows


def table_status(results: dict[tuple[str, str], list[dict[str, Any]]]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for (name, level), designs in sorted(results.items()):
        st: Counter[str] = Counter()
        late = trans = capped = 0
        for _, u in _units(designs):
            st[u["status"]] += 1
            late += int(u["first"] > 1 and "loss" in u)
            if "loss" in u:
                trans += int(u["loss"]["transient"])
                capped += int(u["loss"]["capped"])
        rows.append([name, level, len(designs), sum(st.values()), st["kept"], st["lost"],
                     st["born-joined"], late, trans, capped])
    return rows


def table_explained(results: dict[tuple[str, str], list[dict[str, Any]]]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for (name, level), designs in sorted(results.items()):
        for k in range(2, len(PASSES) + 1):
            merged = expl = 0
            for _, u in _units(designs):
                loss = u.get("loss")
                if loss and loss["at"] == k and loss["reason"] not in ("removed", "subsumed"):
                    merged += 1
                    expl += int(loss["explained"])
            rows.append([name, level, PASS_LABEL[k - 1], merged, expl])
    return rows


def table_inherited(results: dict[tuple[str, str], list[dict[str, Any]]]) -> list[list[Any]]:
    """Post-data, exploratory: unlabelled merges whose merged objects are sub-blends of an object
    that was already impure at the previous snapshot (the blend is inherited, V1.2.0 3.3)."""
    rows: list[list[Any]] = []
    for (name, level), designs in sorted(results.items()):
        for k in range(2, len(PASSES) + 1):
            n = inh = sub = 0
            for _, u in _units(designs):
                loss = u.get("loss")
                if loss and loss["at"] == k and loss["reason"] == "unlabelled-merge":
                    n += 1
                    inh += int(loss["inherited"])
                    sub += int(loss["inherited_subset"])
            rows.append([name, level, PASS_LABEL[k - 1], n, inh, sub])
    return rows


def table_list(results: dict[tuple[str, str], list[dict[str, Any]]]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for (name, level), designs in sorted(results.items()):
        if name == "ALL" or level != "stmt":
            continue
        for design, u in _units(designs):
            loss = u.get("loss")
            if not loss:
                continue
            partners = ";".join(f"{p[1]}@{p[2]}" for p in loss["partners"])
            rows.append([name, design, u["file"], u["span"], u["kind"], u["hw"], loss["pass"],
                         loss["reason"], int(loss["explained"]), loss["n_partners"], partners])
    return rows


def table_subsumed(results: dict[tuple[str, str], list[dict[str, Any]]]) -> list[list[Any]]:
    """Per set, level and pass: first losses, of which subsumed, removed, merged."""
    rows: list[list[Any]] = []
    for (name, level), designs in sorted(results.items()):
        for k in range(2, len(PASSES) + 1):
            cnt: Counter[str] = Counter()
            for _, u in _units(designs):
                loss = u.get("loss")
                if loss and loss["at"] == k:
                    cnt["all"] += 1
                    cnt["sub" if loss["reason"] == "subsumed" else
                        "rem" if loss["reason"] == "removed" else "mer"] += 1
            rows.append([name, level, PASS_LABEL[k - 1], cnt["all"], cnt["sub"], cnt["rem"],
                         cnt["mer"]])
    return rows


def table_size_mad(results: dict[tuple[str, str], list[dict[str, Any]]]) -> list[list[Any]]:
    """Mean absolute size deviation of the persistence null from the real S_k, per pass, over
    the designs that drew at least one merge (the deviation is 0.0 for the others)."""
    rows: list[list[Any]] = []
    for (name, level), designs in sorted(results.items()):
        for k in range(2, len(PASSES) + 1):
            vals = [d["pnull_size_mad"][k - 1] for d in designs if d["pnull_size_mad"][k - 1] > 0]
            rows.append([name, level, PASS_LABEL[k - 1], len(vals),
                         f"{sum(vals) / len(vals):.3f}" if vals else "0.000"])
    return rows


def main() -> int:
    results = pooled(audit_all("--force" in sys.argv[1:]))
    write_csv(HERE / "l15_subsumed.csv",
              ["set", "level", "pass", "first_losses", "subsumed", "removed", "merged"],
              table_subsumed(results))
    write_csv(HERE / "l15_null_size_mad.csv", ["set", "level", "pass", "designs_with_merges",
                                              "mean_abs_size_dev"], table_size_mad(results))
    write_csv(HERE / "l15_kind_pass.csv",
              ["set", "level", "axis", "kind", "pass", "at_risk", "first_losses", "null_expected",
               "pnull_mean", "pnull_lo", "pnull_hi"],
              table_kind_pass(results))
    write_csv(HERE / "l15_reason.csv", ["set", "level", "reason", "pass", "losses"],
              table_reason(results))
    write_csv(HERE / "l15_status.csv",
              ["set", "level", "designs", "units", "kept", "lost", "born_joined", "late",
               "transient", "capped"], table_status(results))
    write_csv(HERE / "l15_explained.csv", ["set", "level", "pass", "merged", "explained"],
              table_explained(results))
    write_csv(HERE / "l15_x_inherited.csv",
              ["set", "level", "pass", "unlabelled", "inherited", "inherited_subset"],
              table_inherited(results))
    write_csv(HERE / "l15_lost_list.csv",
              ["set", "design", "file", "span", "kind", "hw", "pass", "reason", "explained",
               "n_partners", "partners"], table_list(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
