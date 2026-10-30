"""The overlay: hypotheses, evidence, competition and commit selection (L1 spec 5, 6)."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from loki.re import bayes
from loki.re.bayes import Calib, family_of
from loki.re.claims import CONE_TEMPLATES, Claim
from loki.re.detectors import Candidate

if TYPE_CHECKING:
    from loki.re.fngraph import FnGraph
    from loki.re.provers import Verdict

SCHEMA = 1
_DOC = "detector:"
_OWNED = ("prior", "child")
_LIVE = ("open", "confirmed")


@dataclass
class Evidence:
    round: int
    source: str
    name: str
    value: str
    llr: float


@dataclass
class Hypothesis:
    id: str
    kind: str
    detector: str
    round: int
    cells: frozenset[int]
    nets: dict[str, tuple[int, ...]]
    params: dict[str, int | str]
    claim: Claim | None
    children: tuple[str, ...] = ()
    parents: tuple[str, ...] = ()
    features: dict[str, str] = field(default_factory=dict)
    prior_log_odds: float = 0.0
    log_odds: float = 0.0
    p_comp: float = 0.5
    evidence: list[Evidence] = field(default_factory=list)
    status: str = "open"
    proof: dict[str, str] | None = None
    proved_claim: Claim | None = None
    conflicts: tuple[str, ...] = ()
    commit: dict[str, str] | None = None


@dataclass(frozen=True)
class KindSpec:
    """``level`` bit 0, bus 1, word 2, unit 3; ``commit`` in no attrs submod raise+submod."""

    level: int
    exclusive: bool
    commit: str
    rank: int


def _kinds() -> dict[str, KindSpec]:
    rank = [
        "counter", "lfsr", "shift_reg", "fsm", "fsm_onehot", "fsm_binary", "adder", "subtractor",
        "adder_cin", "comparator", "eq_const", "mux_tree", "mux", "register", "hard_group",
    ]
    r = {name: len(rank) - i for i, name in enumerate(rank)}

    def k(level: int, excl: bool, commit: str, name: str) -> KindSpec:
        return KindSpec(level, excl, commit, r.get(name, 0))

    table: dict[str, KindSpec] = {}
    for name in ("ff_en", "ff_srst", "mux_bit"):
        table[name] = k(0, False, "no", name)
    table["register"] = k(2, True, "submod", "register")
    table["bus"] = k(1, False, "attrs", "bus")
    for name in ("adder", "subtractor", "comparator", "mux"):
        table[name] = k(2, True, "raise+submod", name)
    for name in ("adder_cin", "eq_const", "mux_tree", "counter", "shift_reg", "lfsr", "fsm",
                 "fsm_onehot", "fsm_binary", "hard_add", "hard_mul", "hard_mem", "hard_group"):
        table[name] = k(2, True, "submod", name)
    for name in ("datapath_unit", "control_unit"):
        table[name] = k(3, True, "submod", name)
    table["role"] = k(0, False, "attrs", "role")
    return table


KINDS: dict[str, KindSpec] = _kinds()


def register_kind(name: str, spec: KindSpec) -> None:
    """Add a kind (plugins, at import); a duplicate name is refused."""
    if name in KINDS:
        raise ValueError(f"kind {name!r} already registered")
    KINDS[name] = spec


def _owned(e: Evidence) -> bool:
    """Records that ``rescore`` rebuilds: prior, child and per-feature LLRs."""
    return e.source in _OWNED or (e.source == "feature" and not e.name.startswith(_DOC))


def _num(hid: str) -> int:
    return int(hid[1:])


def _canon(params: dict[str, int | str]) -> str:
    return json.dumps(params, sort_keys=True, separators=(",", ":"))


def _fmt(x: float) -> float | str:
    if math.isinf(x):
        return "inf" if x > 0 else "-inf"
    return round(x, 6)


def _cex_text(cex: dict[str, int]) -> str:
    return ",".join(f"{k}={v}" for k, v in sorted(cex.items()))


class Overlay:
    """All hypotheses of a run, nothing ever deleted (decision 5)."""

    def __init__(self) -> None:
        self.hyps: dict[str, Hypothesis] = {}
        self.by_key: dict[tuple[str, frozenset[int], str], str] = {}
        self.by_cell: dict[int, set[str]] = {}
        self._low_at: dict[str, float] = {}

    # -- access ---------------------------------------------------------------------------
    def get(self, hid: str) -> Hypothesis:
        return self.hyps[hid]

    def all(self) -> list[Hypothesis]:
        return [self.hyps[h] for h in sorted(self.hyps, key=_num)]

    def by_kind(self, kind: str) -> list[Hypothesis]:
        return [h for h in self.all() if h.kind == kind]

    def committed(self) -> list[Hypothesis]:
        return [h for h in self.all() if h.status == "committed"]

    def children_of(self, hid: str) -> list[Hypothesis]:
        return [self.hyps[c] for c in self.hyps[hid].children]

    # -- proposals ------------------------------------------------------------------------
    def add(self, cand: Candidate, detector: str, round: int) -> Hypothesis:
        """Merge a candidate by ``(kind, cells, params)``: update it or create ``h<k>``."""
        if cand.kind not in KINDS:
            raise ValueError(f"unknown kind {cand.kind!r}")
        params = dict(sorted(cand.params.items()))
        key = (cand.kind, cand.cells, _canon(params))
        hid = self.by_key.get(key)
        if hid is None:
            hid = f"h{len(self.hyps) + 1}"
            h = Hypothesis(hid, cand.kind, detector, round, cand.cells, {}, params, None)
            self.hyps[hid] = h
            self.by_key[key] = hid
            for cell in cand.cells:
                self.by_cell.setdefault(cell, set()).add(hid)
        h = self.hyps[hid]
        h.nets.update({k: tuple(v) for k, v in cand.nets.items()})
        h.features.update(cand.features)
        if cand.claim is not None and cand.claim != h.claim:
            self._set_claim(h, cand.claim)
        for child in cand.children:
            self._link(hid, child)
        text = ",".join(f"{k}={v}" for k, v in sorted(cand.features.items()))
        h.evidence.append(Evidence(round, "feature", _DOC + detector, text, 0.0))
        return h

    @staticmethod
    def _set_claim(h: Hypothesis, claim: Claim) -> None:
        """A proof holds for the claim that was proved: a different claim clears it (``add`` may
        replace ``h.claim`` because the merge key has no nets)."""
        if h.proof is not None or h.proved_claim is not None:
            h.proof = None
            h.proved_claim = None
            if h.status == "confirmed":
                h.status = "open"
        h.claim = claim

    def _link(self, parent: str, child: str) -> None:
        p, c = self.hyps[parent], self.hyps[child]
        if child not in p.children:
            p.children = tuple(sorted((*p.children, child), key=_num))
        if parent not in c.parents:
            c.parents = tuple(sorted((*c.parents, parent), key=_num))

    # -- conflicts and nesting --------------------------------------------------------------
    @staticmethod
    def _relation(a: Hypothesis, b: Hypothesis) -> str:
        """``conflict``, ``nest`` (strict subset either way) or ``none`` (spec 6.5)."""
        if not (KINDS[a.kind].exclusive and KINDS[b.kind].exclusive):
            return "none"
        if not a.cells & b.cells:
            return "none"
        if a.cells < b.cells or b.cells < a.cells:
            return "nest"
        return "conflict"

    def _neighbours(self, h: Hypothesis) -> list[Hypothesis]:
        """Hypotheses sharing a cell with ``h``, found through the cell index."""
        ids: set[str] = set()
        for cell in h.cells:
            ids |= self.by_cell.get(cell, set())
        ids.discard(h.id)
        return [self.hyps[i] for i in sorted(ids, key=_num)]

    def link_nesting(self) -> None:
        """Make the smaller of two nested exclusive hypotheses a child of the larger.

        Hypotheses that are refuted or rejected are not linked."""
        dead = ("refuted", "rejected")
        for h in self.all():
            if KINDS[h.kind].exclusive and h.status not in dead:
                for o in self._neighbours(h):
                    if (o.status not in dead and self._relation(h, o) == "nest"
                            and o.cells < h.cells):
                        self._link(h.id, o.id)

    # -- scoring ----------------------------------------------------------------------------
    def rescore(self, calib: Calib, round: int) -> float:
        """Recompute every log-odds from prior, features, children and fixed records.

        Records of source ``prior``, ``child`` and per-feature ``feature`` are rebuilt; proofs,
        simulation, competition and detector records are kept. Returns the largest absolute
        change of a log-odds."""
        change = 0.0
        for h in self.all():
            old = h.log_odds
            self._score(h, calib, round)
            if h.log_odds != old:
                change = max(change, abs(h.log_odds - old))
        return change

    def _score(self, h: Hypothesis, calib: Calib, round: int) -> None:
        if h.status == "refuted":
            h.log_odds = -math.inf
            return
        kept = [e for e in h.evidence if not _owned(e)]
        derived: list[Evidence] = []
        h.prior_log_odds = calib.prior(h.detector, h.kind)
        derived.append(Evidence(round, "prior", f"{h.detector}/{h.kind}", "", h.prior_log_odds))
        for name, bin_ in sorted(h.features.items()):
            raw = calib.feature_llr(h.kind, name, bin_)
            w = calib.weight(family_of(name))
            derived.append(Evidence(round, "feature", name, bin_, w * raw))
        for cid in h.children:
            child = self.hyps[cid]
            if child.status in ("confirmed", "committed"):
                derived.append(Evidence(round, "child", cid, child.status, bayes.CHILD_LLR))
            elif child.status == "refuted":
                derived.append(Evidence(round, "child", cid, "refuted", bayes.CHILD_NEG))
        h.evidence = kept + derived
        h.log_odds = self._total(h)

    @staticmethod
    def _total(h: Hypothesis) -> float:
        """Log-odds from the records of ``h``: prior, the capped feature and child sum, the
        fixed records, and the proof floor (spec 6.2)."""
        feat = pos = neg = extra = 0.0
        for e in h.evidence:
            if e.source == "feature" and not e.name.startswith(_DOC):
                feat += e.llr
            elif e.source == "child":
                if e.llr > 0:
                    pos += e.llr
                else:
                    neg += e.llr
            elif e.source != "prior":
                extra += e.llr
        struct = feat + min(pos, bayes.CHILD_CAP) + neg
        struct = max(-bayes.STRUCT_CAP, min(bayes.STRUCT_CAP, struct))
        log_odds = h.prior_log_odds + struct + extra
        if h.proof is not None and h.proof.get("verdict") == "equivalent":
            log_odds = max(log_odds, bayes.PROOF_LO)
        return log_odds

    def apply_verdict(self, hid: str, v: Verdict, round: int) -> None:
        """Record a prover verdict (spec 6.2): equivalent confirms, differs refutes for good."""
        h = self.hyps[hid]
        source = v.engine if v.engine in ("cone_check", "truth_table") else "sim"
        llr = 0.0
        if v.verdict == "unproven" and v.detail == "sampled":
            llr = bayes.SIM_LLR
        h.evidence.append(Evidence(round, source, v.engine, v.verdict, llr))
        template = CONE_TEMPLATES.get(h.claim.op, "") if h.claim is not None else ""
        if v.verdict in ("equivalent", "differs", "unproven"):
            h.proof = {"engine": v.engine, "verdict": v.verdict, "template": template,
                       "cex": _cex_text(v.cex), "from": ""}
            h.proved_claim = h.claim
        if v.verdict == "equivalent":
            h.log_odds = max(h.log_odds, bayes.PROOF_LO)
            if h.status in ("open", "rejected"):
                h.status = "confirmed"
        elif v.verdict == "differs":
            h.log_odds = -math.inf
            h.p_comp = 0.0
            h.status = "refuted"
        elif llr:
            h.log_odds += llr

    # -- proof transfer (spec 8.1) -----------------------------------------------------------
    def apply_transfer(self, hid: str, src: str, round: int) -> None:
        """``hid`` is proved by the exact proof of ``src`` through a matching cone."""
        h = self.hyps[hid]
        proof = self.hyps[src].proof
        template = proof["template"] if proof is not None else ""
        h.evidence.append(Evidence(round, "transfer", src, "equivalent", 0.0))
        h.proof = {"engine": "transfer", "verdict": "equivalent", "template": template,
                   "cex": "", "from": src}
        h.proved_claim = h.claim
        h.log_odds = max(h.log_odds, bayes.PROOF_LO)
        if h.status in ("open", "rejected"):
            h.status = "confirmed"

    def revoke_transfers(self, src: str, round: int) -> list[str]:
        """Withdraw every transfer from ``src`` (a failed spot check): the records get the value
        ``revoked``, confirmed hypotheses return to ``open`` and their log-odds are recomputed
        without the proof. Returns the revoked ids in id order."""
        revoked: list[str] = []
        for h in self.all():
            if h.proof is None or h.proof.get("engine") != "transfer" or h.proof["from"] != src:
                continue
            for e in h.evidence:
                if e.source == "transfer" and e.name == src and e.value == "equivalent":
                    e.value = "revoked"
            h.proof = None
            h.proved_claim = None
            if h.status == "confirmed":
                h.status = "open"
            h.log_odds = self._total(h)
            revoked.append(h.id)
        return revoked

    # -- competition ------------------------------------------------------------------------
    def compete(self, round: int) -> None:
        """Set ``p_comp``, ``conflicts`` and rejections (spec 6.5)."""
        self._reject_against_committed(round)
        self._reopen()
        live = [h for h in self.all() if h.status in _LIVE]
        group_of = self._equal_groups(live)
        parent = {h.id: h.id for h in live}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        edges: dict[str, list[str]] = {h.id: [] for h in live}
        liveset = {h.id for h in live}
        for h in live:
            if not KINDS[h.kind].exclusive:
                continue
            for o in self._neighbours(h):
                if o.id in liveset and self._relation(h, o) == "conflict":
                    edges[h.id].append(o.id)
                    parent[find(h.id)] = find(o.id)
        comps: dict[str, list[Hypothesis]] = {}
        for h in live:
            comps.setdefault(find(h.id), []).append(h)
        for members in comps.values():
            self._component_p(members, group_of)
        for h in live:
            h.conflicts = tuple(sorted(edges[h.id], key=_num))
        for h in self.all():
            if h.status == "refuted":
                h.p_comp = 0.0
            elif h.status == "open" and h.p_comp < bayes.REJECT_P:
                h.status = "rejected"
                self._low_at[h.id] = h.log_odds
                h.evidence.append(Evidence(round, "competition", "p_comp", "low", 0.0))

    def _reject_against_committed(self, round: int) -> None:
        for c in self.committed():
            for h in self._neighbours(c):
                if h.status in _LIVE and self._relation(h, c) == "conflict":
                    h.status = "rejected"
                    h.p_comp = 0.0
                    h.evidence.append(Evidence(round, "competition", "committed", c.id, 0.0))

    def _reopen(self) -> None:
        for hid, low in list(self._low_at.items()):
            h = self.hyps[hid]
            if h.status == "rejected" and h.log_odds > low:
                h.status = "open"
            if h.status != "rejected":
                del self._low_at[hid]

    @staticmethod
    def _equal_groups(live: list[Hypothesis]) -> dict[str, str]:
        """Confirmed exclusive hypotheses with equal cells form one competition member."""
        first: dict[frozenset[int], str] = {}
        out: dict[str, str] = {}
        for h in live:
            if h.status == "confirmed" and KINDS[h.kind].exclusive:
                out[h.id] = first.setdefault(h.cells, h.id)
            else:
                out[h.id] = h.id
        return out

    @staticmethod
    def _component_p(members: list[Hypothesis], group_of: dict[str, str]) -> None:
        groups: dict[str, list[Hypothesis]] = {}
        for h in members:
            groups.setdefault(group_of[h.id], []).append(h)
        score = {g: max(h.log_odds for h in hs) for g, hs in groups.items()}
        inf_groups = [g for g, s in score.items() if s == math.inf]
        for g, hs in groups.items():
            if inf_groups:
                p = 1.0 / len(inf_groups) if g in inf_groups else 0.0
            else:
                top = max(score.values())
                denom = math.exp(-top) + sum(math.exp(s - top) for s in score.values())
                p = math.exp(score[g] - top) / denom
            for h in hs:
                h.p_comp = p

    # -- commit selection ---------------------------------------------------------------------
    def select_commits(self, round: int = 0) -> list[Hypothesis]:
        """Greedy commit selection (spec 9.2 step 6); losers become rejected or alternative.
        A cell absorbed by a committed piece cannot be committed again, so a live hypothesis
        wholly inside a committed piece is skipped: the piece took its cells."""
        committed = self.committed()
        cands = [
            h for h in self.all()
            if KINDS[h.kind].commit != "no" and h.status in _LIVE and h.p_comp >= bayes.COMMIT_P
            and self._children_ready(h)
            and not any(self._relation(h, c) == "conflict" for c in committed)
            and not any(h.cells < c.cells for c in committed)
        ]
        cands.sort(key=lambda h: (-h.p_comp, -KINDS[h.kind].rank, -len(h.cells), _num(h.id)))
        chosen: list[Hypothesis] = []
        for h in cands:
            win = next((w for w in chosen if self._relation(h, w) == "conflict"), None)
            if win is None:
                chosen.append(h)
                continue
            equal = h.cells == win.cells and h.status == "confirmed" and win.status == "confirmed"
            h.status = "alternative" if equal else "rejected"
            h.evidence.append(Evidence(round, "competition", "selected", win.id, 0.0))
        return chosen

    def _children_ready(self, h: Hypothesis) -> bool:
        """Every exclusive child that could commit (``p_comp >= COMMIT_P``) is already committed.
        A weaker child cannot be committed first, so waiting for it would hold the parent back
        for ever (deviation from spec 9.2, found by the Task 16 baseline)."""
        for cid in h.children:
            child = self.hyps[cid]
            if (
                KINDS[child.kind].exclusive
                and child.status in _LIVE
                and child.p_comp >= bayes.COMMIT_P
            ):
                return False
        return True

    # -- output -----------------------------------------------------------------------------
    def to_json(self, graph: FnGraph) -> dict[str, object]:
        """The ``overlay.json`` object (schema 1): ids, cells and nets as in the input."""

        def nets(ns: tuple[int, ...]) -> list[str]:
            return [graph.names.get(n, str(n)) for n in ns]

        def claim(c: Claim | None) -> object:
            if c is None:
                return None
            return {
                "op": c.op,
                "params": {k: v for k, v in c.params},
                "inputs": {p: nets(ns) for p, ns in c.inputs},
                "outputs": {p: nets(ns) for p, ns in c.outputs},
            }

        out = []
        for h in self.all():
            out.append({
                "id": h.id, "kind": h.kind, "detector": h.detector, "round": h.round,
                "cells": [graph.label(c) for c in sorted(h.cells)],
                "nets": {role: nets(ns) for role, ns in sorted(h.nets.items())},
                "params": dict(sorted(h.params.items())),
                "claim": claim(h.claim),
                "children": list(h.children), "parents": list(h.parents),
                "features": dict(sorted(h.features.items())),
                "prior_log_odds": _fmt(h.prior_log_odds), "log_odds": _fmt(h.log_odds),
                "p_comp": _fmt(h.p_comp),
                "evidence": [
                    {"round": e.round, "source": e.source, "name": e.name, "value": e.value,
                     "llr": _fmt(e.llr)} for e in h.evidence
                ],
                "status": h.status, "proof": h.proof, "conflicts": list(h.conflicts),
                "commit": h.commit,
            })
        return {"schema": SCHEMA, "hypotheses": out}

