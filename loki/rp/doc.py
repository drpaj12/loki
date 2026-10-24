"""``loki rp doc``: a plain-English document for an LLM from ``reverse-provenance.json``.

Every sentence is built from fields of the JSON; nothing is added that the file does not say.
When the text exceeds ``max_chars`` the lowest-priority material goes first: rejected claims,
then candidates, then per-cell lists. The document names what it dropped.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from loki.rp.build import natural_key
from loki.schemas import validate_reverse_provenance

FILE = "reverse-provenance.json"
MAX_CHARS = 24000
_SPLIT = re.compile(r"^(.*?)(\d+)$")
_AN_NUMBER = re.compile(r"8|(11|18)(?!\d)")
_NOUN = {
    "adder": "adder", "subtractor": "subtractor", "adder_cin": "adder with carry-in",
    "comparator": "comparator", "eq_const": "comparison against a constant",
    "mux": "multiplexer", "mux_tree": "multiplexer tree", "mux_bit": "one-bit multiplexer",
    "register": "register", "counter": "counter", "shift_reg": "shift register",
    "lfsr": "linear-feedback shift register", "fsm": "finite state machine", "bus": "bus",
    "ff_en": "flip-flop with enable", "ff_srst": "flip-flop with synchronous reset",
    "hard_add": "hard adder block", "hard_mul": "hard multiplier block",
    "hard_mem": "hard memory block", "hard_group": "group of hard blocks",
    "datapath_unit": "datapath unit", "control_unit": "control unit",
}
_WORD_LEVEL = frozenset({
    "adder", "subtractor", "adder_cin", "comparator", "mux", "mux_tree", "register", "counter",
    "shift_reg", "lfsr", "bus"})
_ENGINES = {"cone_check": "cone check", "truth_table": "truth table", "sim": "simulation",
            "transfer": "proof transfer"}


def span(names: list[str], ordered: bool = False) -> str:
    """Names as runs (``n3..n10``); sorted naturally unless ``ordered`` keeps the given order."""
    items = list(names) if ordered else sorted(set(names), key=lambda n: (natural_key(n), n))
    runs: list[list[str]] = []
    last: tuple[str, int] | None = None
    for name in items:
        m = _SPLIT.match(name)
        key = (m.group(1), int(m.group(2))) if m else None
        if key and last and key[0] == last[0] and key[1] == last[1] + 1 and runs:
            runs[-1].append(name)
        else:
            runs.append([name])
        last = key
    return ", ".join(r[0] if len(r) == 1 else f"{r[0]}..{r[-1]}" if len(r) > 2
                     else f"{r[0]}, {r[1]}" for r in runs)


def _cells(names: list[str], lists: bool) -> str:
    count = f"{len(names)} cell" + ("" if len(names) == 1 else "s")
    return f"cells {span(names)} ({count})" if lists else f"{count}"


def _noun(el: dict[str, Any]) -> str:
    noun = str(_NOUN.get(el["kind"], el["kind"]))
    if el["kind"] in _WORD_LEVEL and el["width"] > 0:
        return f"{el['width']}-bit {noun}"
    return noun


def _article(text: str) -> str:
    """``an`` before a vowel and before a number said with a vowel (8, 80..89, 11, 18)."""
    vowel = bool(text) and text[0] in "aeiou"
    return ("an " if vowel or _AN_NUMBER.match(text) else "a ") + text


def _proof(el: dict[str, Any]) -> str:
    p = el["proof"]
    engine = _ENGINES.get(p["engine"], p["engine"])
    if p["label"] == "equivalent":
        return f"Proved equivalent by {engine}."
    if p["label"] == "derived":
        return f"Proof derived from {p['from']} (proof transfer)."
    if p["label"] == "unproven":
        return f"Not proven ({engine})."
    if p["verdict"] == "differs":
        return f"The proof showed it differs ({engine})."
    return "No proof recorded."


def _ports(el: dict[str, Any]) -> str:
    parts = []
    for label, group in (("Inputs", el["ports"]["inputs"]), ("Outputs", el["ports"]["outputs"])):
        if group:
            items = "; ".join(f"{p} = nets {span(ns, True)}" for p, ns in sorted(group.items()))
            parts.append(f"{label}: {items}.")
    return " ".join(parts)


def _statement(el: dict[str, Any], lists: bool, confirmed: bool) -> str:
    head = el["id"] if confirmed else f"{el['id']} (unconfirmed)"
    text = (f"{head}: {_cells(el['cells'], lists)} form {_article(_noun(el))}, "
            f"`{el['fn']}`. {_proof(el)} Confidence {el['p_comp']:.4f}.")
    ports = _ports(el)
    if ports:
        text += " " + ports
    rec = el["recovered"]
    if rec and rec["module"]:
        text += f" Recovered as module {rec['module']}, instance {rec['instance']}."
    if el["role"]:
        text += f" Role: {el['role']}."
    more = el["links_outside"]["conflicts"]
    if el["conflicts"] or more:
        text += " Conflicts with " + ", ".join(el["conflicts"])
        if more:
            text += (" and " if el["conflicts"] else "") + f"{more} more not listed"
        text += "."
    return text


def _rejected(el: dict[str, Any], lists: bool) -> str:
    what = f"{_article(_noun(el))} (`{el['fn']}`) on {_cells(el['cells'], lists)}"
    reason = el["reason"]
    if not reason:
        return f"- {el['id']}: Loki proposed {what}; it was rejected."
    if reason.startswith("proof differs"):
        return (f"- {el['id']}: Loki tested {what} and the proof showed it differs"
                f"{reason[len('proof differs'):]}.")
    return f"- {el['id']}: Loki proposed {what}; rejected: {reason}."


def _tree(nodes: list[dict[str, Any]], kinds: dict[str, str], depth: int = 0) -> list[str]:
    out: list[str] = []
    for n in nodes:
        mod = n["module"] or "(no module)"
        out.append(f"{'  ' * depth}- {n['id']} {mod} ({kinds.get(n['id'], '')})")
        out += _tree(n["children"], kinds, depth + 1)
    return out


def _tree_order(nodes: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for n in nodes:
        out.append(n["id"])
        out += _tree_order(n["children"])
    return out


def _intro(rp: dict[str, Any]) -> list[str]:
    h = rp["header"]
    return [
        "# Loki analysis of a gate netlist", "",
        "## 1. What this is", "",
        f"Loki III analysed the gate-level netlist `{h['input']['name']}` "
        f"(sha256 {h['input']['sha256'][:12]}, floor {h['floor']}).",
        "The list below holds Loki's claims about its higher-level structure.",
        "Each claim has a confidence (a probability) and a proof status.",
        "Trust order: proved or derived claims, then unproven claims with high confidence, "
        "then candidates.",
        f"Committed claims have confidence of at least {h['commit_threshold']}; candidates "
        f"are listed from {h['candidate_threshold']} and are unconfirmed.", "",
    ]


def _howto() -> list[str]:
    return [
        "## 2. How to read the netlist with it", "",
        "The recovered Verilog (`design.v`) carries Loki attributes on the pieces it committed:",
        "- `loki_hid`: the claim id (`h12`), the same id as in this document.",
        "- `loki_kind`, `loki_fn`: what the piece is and its function; `loki_conf`: confidence.",
        "- `loki_proof`: `equivalent`, `derived`, `unproven` or `none`; `loki_role`: control, "
        "datapath or mixed.",
        "- `loki_bus = \"<hid>[bit]\"` on a net: the net is that bit of bus `<hid>`.",
        "Cell and net names are those of the input netlist.", "",
    ]


def _summary(rp: dict[str, Any], kinds: dict[str, str]) -> list[str]:
    counts: dict[str, dict[str, int]] = {}
    for el in rp["elements"]:
        row = counts.setdefault(el["kind"], {})
        row[el["status"]] = row.get(el["status"], 0) + 1
    out = ["## 3. Summary", "", "| kind | committed | candidate | rejected |",
           "| --- | --- | --- | --- |"]
    for kind in sorted(counts):
        c = counts[kind]
        out.append(f"| {kind} | {c.get('committed', 0)} | {c.get('candidate', 0)} | "
                   f"{c.get('rejected', 0)} |")
    cov = rp["coverage"]
    out += ["", f"Input cells: {cov['cells_total']}. Covered by committed claims: "
            f"{cov['committed']['cells']} ({cov['committed']['fraction']:.1%}); by candidates "
            f"only: {cov['candidate']['cells']} ({cov['candidate']['fraction']:.1%}); by nothing: "
            f"{cov['uncovered']['cells']} ({cov['uncovered']['fraction']:.1%}).", ""]
    attrs = cov["attrs"]
    if attrs["elements"]:
        out += [f"Of the committed cells, {attrs['cells']} (in {attrs['elements']} claims) are "
                "marked only by attributes on existing cells (form attrs). Those claims are not "
                "modules, so the hierarchy below does not show them.", ""]
    out += ["Recovered module hierarchy (a module contains its children):", ""]
    out += _tree(rp["hierarchy"], kinds) or ["(no committed modules)"]
    return [*out, ""]


def _committed(rp: dict[str, Any], lists: bool) -> list[str]:
    done = {e["id"]: e for e in rp["elements"] if e["status"] == "committed"}
    order = [i for i in _tree_order(rp["hierarchy"]) if i in done]
    order += [i for i in sorted(done, key=lambda i: int(i[1:])) if i not in order]
    out = ["## 4. Committed claims", ""]
    out += [f"- {_statement(done[i], lists, True)}" for i in order] or ["(none)"]
    return [*out, ""]


def _head(row: dict[str, Any]) -> str:
    return row["id"] if row["status"] == "committed" else f"{row['id']} (unconfirmed)"


def _bus_line(b: dict[str, Any]) -> str:
    bits = "; ".join(f"bit {i} = {span(ns, True)}" for i, ns in enumerate(b["bits"]))
    src = b["order_source"] or "not recorded"
    return f"- {_head(b)}: {b['width']} bits, bit order from {src}: {bits}."


def _fsm_line(f: dict[str, Any]) -> str:
    rows = f["transitions"][:12]
    text = (f"- {_head(f)}: state registers {span(f['state_nets'], True)}, {f['states']} states, "
            f"reset state {f['reset_state']}, encoding {f['encoding']}")
    if f["control_nets"]:
        text += f", control inputs {span(f['control_nets'], True)}"
    text += f". {f['transitions_total']} transitions"
    if rows:
        text += " (state, control value, next state; integers; first " + str(len(rows)) + "): "
        text += ", ".join(f"({a},{b},{c})" for a, b, c in rows)
    return text + "."


def _structure(rp: dict[str, Any], cands: bool) -> list[str]:
    """Section 5; candidate buses and state machines are marked and drop with the candidates."""
    def keep(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [r for r in rows if cands or r["status"] == "committed"]

    none = "none." if cands else "none committed."
    buses, fsms = keep(rp["buses"]), keep(rp["fsms"])
    out = ["## 5. Buses, state machines and roles", ""]
    out += ["Buses:", *(_bus_line(b) for b in buses)] if buses else [f"Buses: {none}"]
    out += ["", *(["State machines:", *(_fsm_line(f) for f in fsms)]
                  if fsms else [f"State machines: {none}"]), ""]
    roles: dict[str, list[str]] = {}
    for el in rp["elements"]:
        if el["status"] == "committed" and el["role"]:
            roles.setdefault(el["role"], []).append(el["id"])
    if roles:
        out.append("Roles of committed claims: " + "; ".join(
            f"{r}: {', '.join(ids)}" for r, ids in sorted(roles.items())) + ".")
    else:
        out.append("Roles of committed claims: not known.")
    return [*out, ""]


def _candidates(rp: dict[str, Any], lists: bool) -> list[str]:
    cands = [e for e in rp["elements"] if e["status"] == "candidate"]
    cands.sort(key=lambda e: (-e["p_comp"], int(e["id"][1:])))
    out = ["## 6. Candidates (not committed, unconfirmed)", ""]
    out += [f"- {_statement(e, lists, False)}" for e in cands] or ["(none)"]
    return [*out, ""]


def _rejects(rp: dict[str, Any], lists: bool) -> list[str]:
    rej = [e for e in rp["elements"] if e["status"] == "rejected"]
    out = ["## 7. Rejected claims", ""]
    out += [_rejected(e, lists) for e in rej] or ["(none)"]
    return [*out, ""]


def _l2(rp: dict[str, Any], lists: bool) -> list[str]:
    l2 = rp.get("l2")
    if not l2:
        return []
    p = l2["partition"]
    out = ["## 8. Groupings from graph analysis (L2)", "",
           f"Method {l2['method']} (partition {p['key']}, {p['n_clusters']} clusters). These "
           "groups come from graph structure, not from Loki's claims above."]
    if len(l2["clusters"]) < p["n_clusters"]:
        out.append("Clusters that hold no cell (only ports) are not listed.")
    out.append("")
    for number in sorted(l2["clusters"], key=int):
        c = l2["clusters"][number]
        text = f"- cluster {number}: {_cells(c['cells'], lists)}"
        parts = [f"{o['id']} {o['module']}: {o['cells_in_common']} cells "
                 f"({o['fraction_of_cluster']:.0%} of the cluster, "
                 f"{o['fraction_of_module']:.0%} of the module)" for o in c["overlap"]]
        text += "; overlaps " + ", ".join(parts) if parts else "; overlaps no committed module"
        out.append(text + f"; {c['cells_outside_committed']} cells in no committed module.")
    return [*out, ""]


def _not_claimed(rp: dict[str, Any], lists: bool) -> list[str]:
    cov = rp["coverage"]
    out = ["## 9. What Loki does NOT claim", "",
           f"- Cells covered by no claim at all: {cov['uncovered']['cells']} of "
           f"{cov['cells_total']}"
           + (f": {span(cov['uncovered_cells'])}." if lists and cov["uncovered_cells"] else "."),
           f"- Nets driven by those cells: {len(cov['uncovered_nets'])}"
           + (f": {span(cov['uncovered_nets'])}." if lists and cov["uncovered_nets"] else "."),
           "- Candidates and rejected claims are not statements of fact.",
           "- Module names such as `adder_h1` are Loki's labels built from the kind and the id; "
           "they are not the original HDL names, which Loki does not know.", ""]
    return out


def _kinds(rp: dict[str, Any]) -> dict[str, str]:
    return {e["id"]: e["kind"] for e in rp["elements"]}


def _parts(rp: dict[str, Any], rejected: bool, cands: bool,
           lists: bool) -> tuple[list[str], list[str]]:
    """The text before section 9 and section 9, which is never cut."""
    out = _intro(rp) + _howto() + _summary(rp, _kinds(rp)) + _committed(rp, lists)
    out += _structure(rp, cands)
    if cands:
        out += _candidates(rp, lists)
    if rejected:
        out += _rejects(rp, lists)
    return out + _l2(rp, lists), _not_claimed(rp, lists)


def _note(rp: dict[str, Any], steps: tuple[bool, bool, bool], asked: bool, limit: int) -> str:
    rejected, cands, lists = steps
    els = rp["elements"]
    dropped = []
    if not rejected:
        dropped.append(f"rejected claims ({sum(e['status'] == 'rejected' for e in els)})")
    if asked and not cands:
        dropped.append(f"candidates ({sum(e['status'] == 'candidate' for e in els)})")
        rows = sum(r["status"] == "candidate" for r in rp["buses"] + rp["fsms"])
        if rows:
            dropped.append(f"candidate buses and state machines ({rows})")
    if not lists:
        dropped.append("per-cell lists")
    if not dropped:
        return ""
    return f"> Omitted to fit {limit} characters: {', '.join(dropped)}.\n"


def _variants(candidates: bool) -> list[tuple[bool, bool, bool]]:
    steps = [(True, candidates, True), (False, candidates, True)]
    if candidates:
        steps.append((False, False, True))
    steps.append((False, False, False))
    return steps


def _join(lines: list[str]) -> str:
    return "\n".join(lines).rstrip("\n") + "\n"


def _text(rp: dict[str, Any], steps: tuple[bool, bool, bool], candidates: bool,
          limit: int) -> tuple[list[str], list[str]]:
    head, tail = _parts(rp, *steps)
    note = _note(rp, steps, candidates, limit)
    return ([*head[:2], note, *head[2:]] if note else head), tail


def min_chars(rp: dict[str, Any], candidates: bool = True) -> int:
    """The size below which ``max_chars`` is raised: sections 1, 2 and 9 and the notices."""
    last = _variants(candidates)[-1]
    head, tail = _text(rp, last, candidates, 10**6)
    fixed = _join(head[: head.index("## 3. Summary")]) + _join(tail)
    return len(fixed) + len(_cut_notice(10**6, 10**6)) + 4


def _cut_notice(limit: int, asked: int) -> str:
    raised = f" (--max-chars {asked} raised to fit sections 1, 2 and 9)" if asked != limit else ""
    return f"> Cut at {limit} characters{raised}; later text of sections 3 to 8 is missing.\n"


def _cut(head: list[str], tail: list[str], limit: int, asked: int) -> str:
    notice = _cut_notice(limit, asked)
    tail_text = _join(tail)
    cut = _join(head)[: max(limit - len(tail_text) - len(notice) - 1, 0)]
    return cut[: cut.rfind("\n") + 1] + notice + "\n" + tail_text


def render(path: Path, max_chars: int = MAX_CHARS, candidates: bool = True) -> str:
    """The document for ``path`` (a ``loki re`` output directory or the JSON file).

    Over ``max_chars`` the lowest-priority material goes first. Section 9 is never cut:
    ``max_chars`` below ``min_chars`` is raised to it."""
    file = path / FILE if path.is_dir() else path
    rp = json.loads(file.read_text(encoding="utf-8"))
    errs = validate_reverse_provenance(rp)
    if errs:
        raise ValueError(f"{file}: not a valid reverse-provenance file: {errs[0]}")
    limit = max(max_chars, min_chars(rp, candidates))
    for steps in _variants(candidates):
        head, tail = _text(rp, steps, candidates, limit)
        text = _join([*head, *tail])
        if len(text) <= limit:
            return text
    return _cut(head, tail, limit, max_chars)
