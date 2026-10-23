"""The round loop: detect, score, prove, compete, commit, repeat (L1 spec 9)."""

from __future__ import annotations

import os
import random
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loki.equiv import check_equiv
from loki.odin import odin_module
from loki.re import bayes
from loki.re.bayes import Calib, load_calib, wl_npn_bin
from loki.re.claims import Claim
from loki.re.commit import commit, module_name, reject_failed
from loki.re.detectors import Detector, RoundContext, check_candidate, load_detectors
from loki.re.detectors.fsm import fsm_detect_marks
from loki.re.detectors.hard import HardDetector, UnmapRecord
from loki.re.fngraph import FnGraph, from_design
from loki.re.normalise import floor_from_path, load_level0
from loki.re.overlay import Hypothesis, Overlay
from loki.re.provers import ConeCheckProver, Verdict, prove
from loki.re.structural import StructFeatures, build_features, cone_match, transfer_key
from loki.re.view import View

CHANGE_EPS = 1e-6
VERDICTS = ("equivalent", "differs", "unproven", "invalid", "error")


@dataclass(frozen=True)
class ReOptions:
    netlist: Path
    floor: str
    odin3_root: Path | None
    techlib: Path | None
    calib: Path | None
    seed: int
    max_rounds: int
    timeout: int
    time_budget: int
    detectors: tuple[str, ...] | None
    commit: bool
    keep_levels: Path | None
    features: str = "all"


@dataclass
class RunResult:
    level0: Any
    final: Any
    graph: FnGraph
    overlay: Overlay
    rounds: list[dict[str, object]]
    stop_reason: str
    final_equiv: dict[str, object]
    timing: dict[str, object]
    notes: dict[str, str]
    timeouts: int = 0
    features: dict[str, object] = field(default_factory=dict)


def _num(hid: str) -> int:
    return int(hid[1:])


def round_rejections(overlay: Overlay, r: int) -> int:
    """Hypotheses rejected in round ``r``: a competition or commit record of that round on a
    hypothesis rejected now. Not the cumulative count (spec 11 ``rounds.rejected``)."""
    return sum(
        1
        for h in overlay.all()
        if h.status == "rejected"
        and any(e.round == r and e.source in ("competition", "commit") for e in h.evidence)
    )


class _Run:
    """State of one ``run_re``: the levels, the overlay and the per-run counters."""

    def __init__(self, opts: ReOptions, floor: str, root: Path | None) -> None:
        self.opts, self.floor, self.root = opts, floor, root
        self.level0 = load_level0(opts.netlist, floor, root, opts.techlib)
        self.graph = from_design(self.level0)
        self.calib: Calib = load_calib(opts.calib)
        bayes.require_floor(self.calib, floor)
        self.sf: StructFeatures | None = (
            None if opts.features == "none" else build_features(self.graph)
        )
        self.working = self.level0.copy()
        self.overlay = Overlay()
        self.detectors: list[Detector] = load_detectors(opts.detectors)
        self.proved: dict[str, Claim] = {}
        self.cc: ConeCheckProver | None = None
        self.notes: dict[str, str] = {}
        self.unmap: tuple[UnmapRecord, ...] = ()
        self.timeouts = 0
        self.transfers = 0
        self.transfer_failures = 0
        self.prove_seconds: list[float] = []
        self.round_seconds: list[float] = []
        self.start_unmap()

    def start_unmap(self) -> None:
        """Spec 9.1: on F1 with hard cells, run ``unmap`` on the working copy (gated) and read its
        facts; without the pass the cells stay opaque and the report says ``unavailable``. A failed
        pass discards the working copy (the binding contract: it may have mutated the design)."""
        hard = any(c.kind == "hard" for c in self.graph.cells.values())
        if not (self.floor.startswith("f1-") and hard):
            self.notes["unmap"] = "n/a"
            return
        try:
            with odin_module().default().capture_log():
                self.working.run_pass("unmap")
        except odin_module().Odin3Error:
            self.working.close()
            self.working = self.level0.copy()
            self.notes["unmap"] = "unavailable"
            return
        self.notes["unmap"] = "ok"
        self.unmap = tuple(HardDetector.read_unmap(self.working, self.graph))

    # -- helpers ------------------------------------------------------------------------------
    def rng(self, purpose: str) -> random.Random:
        return random.Random(f"{self.opts.seed}:{purpose}")

    def prover(self) -> ConeCheckProver:
        if self.cc is None:
            self.cc = ConeCheckProver(self.level0, self.graph, self.opts.timeout)
        return self.cc

    def fsm_marks(self) -> dict[frozenset[int], str]:
        """Run ``fsm_detect`` when the level holds ``$dff`` or ``$adff`` (spec 7.8)."""
        mod = odin_module()
        top = self.working.top()
        if not any(str(n.type_name) in ("$dff", "$adff") for n in top.nodes()):
            self.notes.setdefault("fsm_detect", "not-applicable")
            return {}
        try:
            with mod.default().capture_log():
                self.working.run_pass("fsm_detect")
        except mod.Odin3Error:
            self.notes.setdefault("fsm_detect", "not-applicable")
            return {}
        self.notes["fsm_detect"] = "applied"
        return fsm_detect_marks(self.working)

    def context(self, r: int) -> RoundContext:
        view = View.level0(self.graph) if r == 1 else View.build(
            self.working, self.graph, self.overlay)
        return RoundContext(
            round=r, floor=self.floor, graph=self.graph, view=view, overlay=self.overlay,
            rng=self.rng, calib=self.calib, fsm_marks=self.fsm_marks(), unmap=self.unmap,
            features=self.sf,
        )

    # -- steps ----------------------------------------------------------------------------------
    def propose(self, ctx: RoundContext, r: int) -> int:
        before = len(self.overlay.hyps)
        for det in self.detectors:
            for cand in det.propose(ctx):
                check_candidate(det, cand)
                self.overlay.add(cand, det.name, r)
            if isinstance(det, HardDetector):
                det.confirm(self.overlay, r)
        return len(self.overlay.hyps) - before

    def node_features(self) -> None:
        """The ``wl_npn`` bin of each hypothesis from the calibrated node table (6.7 item 1)."""
        sf = self.sf
        if sf is None or not self.calib.node_llr:
            return
        for h in self.overlay.all():
            if h.kind not in self.calib.node_llr:
                continue
            scores = [
                self.calib.node_score(h.kind, sf.cell_keys(c))
                for c in sorted(h.cells) if self.graph.cells[c].kind == "lut"
            ]
            known = [s for s in scores if s is not None]
            mean = sum(known) / len(known) if known else None
            h.features["wl_npn"] = wl_npn_bin(mean)

    def score(self, r: int) -> float:
        self.overlay.link_nesting()
        self.node_features()
        return self.overlay.rescore(self.calib, r)

    def prove_one(self, h: Hypothesis, counts: dict[str, Any]) -> Verdict:
        """Prove ``h.claim`` for real (the verdict is not recorded on ``h``)."""
        assert h.claim is not None
        start = time.monotonic()
        v = prove(h.claim, self.graph, self.prover(), self.rng(f"prove:{h.id}"))
        self.prove_seconds.append(time.monotonic() - start)
        counts["proved"][v.verdict] += 1
        if v.engine in counts["engines"]:
            counts["engines"][v.engine] += 1
        if v.verdict == "unproven" and v.engine == "cone_check":
            self.timeouts += 1
        self.proved[h.id] = h.claim
        return v

    def groups(self, open_hyps: list[Hypothesis]) -> dict[tuple[str, ...], list[str]]:
        out: dict[tuple[str, ...], list[str]] = {}
        if self.sf is None:
            return out
        for h in open_hyps:
            key = transfer_key(h, self.sf, self.graph)
            if key is not None:
                out.setdefault(key, []).append(h.id)
        return out

    def transfer(self, h0: Hypothesis, members: list[str], r: int,
                 counts: dict[str, Any], budget: list[int]) -> set[str]:
        """Spec 8.1: ``cone_match`` the other members of ``h0``'s group, then the spot check.

        The spot check costs one ``MAX_PROOFS`` slot and must run in the same round as the
        transfers: with no free slot no transfer is made (a transfer never stands unproved)."""
        assert h0.claim is not None
        if budget[0] <= 0:
            return set()
        moved: list[str] = []
        for mid in sorted(members, key=_num):
            m = self.overlay.get(mid)
            if mid == h0.id or m.status != "open" or m.claim is None or mid in self.proved:
                continue
            if cone_match(self.graph, h0.claim, m.claim):
                self.overlay.apply_transfer(mid, h0.id, r)
                self.proved[mid] = m.claim
                counts["engines"]["transfer"] += 1
                self.transfers += 1
                moved.append(mid)
        if moved:
            budget[0] -= 1
            spot = self.overlay.get(moved[0])
            v = self.prove_one(spot, counts)
            if v.verdict != "equivalent":
                for rid in self.overlay.revoke_transfers(h0.id, r):
                    self.proved.pop(rid, None)
                self.transfer_failures += 1
                counts["transfer_failures"] += 1
                if spot.claim is not None:
                    self.proved[spot.id] = spot.claim
                moved = []
            self.overlay.apply_verdict(spot.id, v, r)
        return set(moved)

    def prove_step(self, r: int, counts: dict[str, Any]) -> None:
        open_hyps = [
            h for h in self.overlay.all()
            if h.claim is not None and h.status == "open" and self.proved.get(h.id) != h.claim
        ]
        groups = self.groups(open_hyps)
        key_of = {hid: key for key, ids in groups.items() for hid in ids}
        order = sorted(
            (h for h in open_hyps if h.p_comp >= bayes.PROVE_P),
            key=lambda h: (-h.p_comp, _num(h.id)),
        )
        budget = [bayes.MAX_PROOFS]
        for h in order:
            if budget[0] <= 0:
                break
            if h.status != "open" or h.id in self.proved:
                continue
            budget[0] -= 1
            v = self.prove_one(h, counts)
            self.overlay.apply_verdict(h.id, v, r)
            if v.verdict == "equivalent" and h.id in key_of:
                self.transfer(h, groups[key_of[h.id]], r, counts, budget)

    def select_and_commit(self, r: int) -> list[str]:
        chosen = [h for h in self.overlay.select_commits(r) if h.kind != "role"]
        if not chosen:
            return []
        res = commit(self.working, chosen, self.overlay, self.graph, self.opts.timeout)
        reject_failed(self.overlay, res, r)
        done = [h for h in chosen if h.id in res.forms]
        for h in done:
            form = res.forms[h.id]
            attrs = form == "attrs"
            h.status = "committed"
            h.commit = {
                "round": str(r), "module": "" if attrs else module_name(h),
                "instance": "" if attrs else f"{module_name(h)}_i", "form": form,
            }
        if done:
            self.working.close()
            self.working = res.design
            self.keep_level(r)
        else:
            res.design.close()
        return [h.id for h in done]

    def keep_level(self, r: int) -> None:
        keep = self.opts.keep_levels
        if keep is None:
            return
        keep.mkdir(parents=True, exist_ok=True)
        design = self.level0 if r == 0 else self.working
        with odin_module().default().capture_log():
            design.run_pass("write_json", f'--odin3 "{keep / f"level{r}.json"}"')

    # -- the loop -----------------------------------------------------------------------------
    def one_round(self, r: int) -> tuple[dict[str, object], bool]:
        counts: dict[str, Any] = {
            "proved": dict.fromkeys(VERDICTS, 0),
            "engines": {"cone_check": 0, "transfer": 0, "truth_table": 0},
            "transfer_failures": 0,
        }
        ctx = self.context(r)
        new = self.propose(ctx, r)
        change = self.score(r)
        self.overlay.compete(r)
        self.prove_step(r, counts)
        change = max(change, self.score(r))
        self.overlay.compete(r)
        committed = self.select_and_commit(r) if self.opts.commit else []
        rejected = round_rejections(self.overlay, r)
        record: dict[str, object] = {
            "round": r, "new": new, "proved": counts["proved"], "committed": committed,
            "rejected": rejected, "engines": counts["engines"],
            "transfer_failures": counts["transfer_failures"],
        }
        fixed = not committed and new == 0 and change <= CHANGE_EPS
        return record, fixed

    def loop(self) -> tuple[list[dict[str, object]], str]:
        rounds: list[dict[str, object]] = []
        start = time.monotonic()
        self.keep_level(0)
        for r in range(1, self.opts.max_rounds + 1):
            if r > 1 and time.monotonic() - start >= self.opts.time_budget:
                return rounds, "time_budget"
            t0 = time.monotonic()
            record, fixed = self.one_round(r)
            self.round_seconds.append(time.monotonic() - t0)
            rounds.append(record)
            if not self.opts.commit:
                return rounds, "no_commit"
            if fixed:
                return rounds, "fixed_point"
        return rounds, "max_rounds"

    def final_check(self) -> dict[str, object]:
        """Spec 9.4: flatten, lower, write the BLIF and compare it with the input."""
        if self.floor.startswith("f1-"):
            return {"status": "skipped:hard", "tool_exit": -1}
        if self.root is None:
            return {"status": "skipped:no-odin3-root", "tool_exit": -1}
        mod = odin_module()
        copy = self.working.copy()
        with tempfile.TemporaryDirectory(prefix="loki-re-") as tmp:
            out = Path(tmp) / "final.blif"
            with mod.default().capture_log():
                copy.run_script(f'flatten; lower; write_blif --gates-as-names "{out}"')
            text = out.read_text(encoding="utf-8")
        copy.close()
        src = self.opts.netlist.read_text(encoding="utf-8")
        res = check_equiv(src, text, self.root, False)
        return {"status": res.status, "tool_exit": res.tool_exit}

    def features_block(self) -> dict[str, object]:
        block: dict[str, object] = (
            self.sf.report() if self.sf is not None
            else {"enabled": False, "wl": {}, "npn": {}}
        )
        block["transfers"] = self.transfers
        block["transfer_failures"] = self.transfer_failures
        return block


def run_re(opts: ReOptions) -> RunResult:
    """Run the flow of spec 9 on one netlist. ``NormaliseError`` when Odin III refuses it."""
    floor = floor_from_path(opts.netlist.resolve()) if opts.floor == "auto" else opts.floor
    root = opts.odin3_root
    if root is None and os.environ.get("ODIN3_ROOT"):
        root = Path(os.environ["ODIN3_ROOT"])
    start = time.monotonic()
    run = _Run(opts, floor, root)
    run.notes["features"] = "off" if run.sf is None else "on"
    try:
        rounds, stop = run.loop()
        final_equiv = run.final_check()
    finally:
        if run.cc is not None:
            run.cc.close()
    run.notes.setdefault("fsm_detect", "not-applicable")
    timing: dict[str, object] = {
        "rounds": [round(s, 3) for s in run.round_seconds],
        "prove": [round(s, 3) for s in run.prove_seconds],
        "features": round(run.sf.seconds, 3) if run.sf is not None else 0.0,
        "total": round(time.monotonic() - start, 3),
    }
    return RunResult(run.level0, run.working, run.graph, run.overlay, rounds, stop, final_equiv,
                     timing, run.notes, run.timeouts, run.features_block())
