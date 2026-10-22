# Loki III L1 Bayesian Hypothesis Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `loki re`: read an anonymous netlist of any L0 floor into Odin III, propose hypotheses with detector plugins, update their log-odds with L0-calibrated priors, features and proofs, commit confirmed pieces with `raise`/`submod` round by round to a fixed point, write hierarchical Verilog with confidence attributes plus a JSON/markdown report, and score it against L0's labels.

**Architecture:** A pure core (`FnGraph` view of level 0, function facts, bit-parallel simulation, claims, overlay, Bayesian scoring, detectors, scoring) works on Python values; five modules touch Odin III objects handed out by L0's `loki/odin.py` (`normalise.py`, `fngraph.from_design`, `provers.ConeCheckProver`, `commit.py`, `loop.py`). Detectors are plugins behind one `Detector` protocol; the loop is detect, score, prove, compete, commit, repeat. Structural features (`loki.features`: role flags, 1-WL colours, NPN classes; standard library only, shared with L2) are computed once on level 0 and feed detectors, proof transfer and calibration (spec 6.7, Tasks 5a and 5b).

**Tech Stack:** Python 3.11+, the `odin3` cffi binding (via `loki.odin` only), `unittest`, `ruff`, `mypy --strict`; Wyrd III as a dev dependency for the step plugin.

**Spec:** `docs/specs/2026-10-21-l1-hypotheses-design.md` (section numbers below refer to it). Read it and L0's spec `docs/specs/2026-10-21-l0-dataset-design.md` first. Every constant, rule and threshold in this plan comes from the spec; where the plan and spec differ, the spec wins and the difference is reported in the PR.

## Global Constraints

- L0's Global Constraints apply unchanged (Python 3.11+, `ruff check .` and `mypy --strict loki tests` clean, no suppressions, line length 100, `unittest` under `tests/`, `skipUnless(odin_available())` for Odin III tests, never commit to `main`, deterministic files, `schema` = 1, only `loki/odin.py` imports `odin3`, never edit the Odin III repo; a missing Odin III API is an open question, not a workaround).
- Branches `feat/l1-<task>`; PR per task; squash merge on green CI; commit and push after every green step.
- Prerequisite: L0 Tasks 1, 2 and 6 merged before L1 Task 2; L0 Task 7 before L1 Task 11; L0 Task 11 before L1 Tasks 13, 14, 16. Each task states its gate.
- No LLM, no network at run time, no new runtime dependency (stdlib only beyond `odin3`).
- Natural logs; constants exactly as spec 6.2 (`PROOF_LO = 9.21`, `SIM_LLR = 4.61`, `STRUCT_CAP = 6.91`, `CHILD_LLR = 1.10` capped at `3.30`, `CHILD_NEG = -2.30`, `COMMIT_P = 0.9`, `PROVE_P = 0.2`, `REJECT_P = 0.01`, `MAX_PROOFS = 200`), `SUPPORT_MAX = 40`, `EXHAUSTIVE_MAX = 16`, `SAMPLE_N = 4096`, `MAX_ROUNDS = 8`, `--time-budget` 3600, `--timeout` 30, `--seed` 1, match Jaccard 0.5, `--score-p` 0.5.
- Structural features (spec 6.7): `loki.features` imports neither `loki.re` nor `loki.analysis` and uses the standard library only; constants `WL_ROUNDS = 4`, `TRANSFER_ROUND = 2`, `CALIB_WL_DEPTH = 2`, `NODE_MIN_COUNT = 5`, `CALIB_FOLDS = 2`, `WEIGHT_GRID` 0.0 to 1.0 by 0.1, `NPN_ENUM_MAX = 100000`; `loki re --features` defaults to `all`, and `--features none` restores the behaviour without them (ablation, spec 12.5).
- Detectors return feature **bin labels**, never LLRs (spec 6.4); default LLRs live only in `loki/re/bayes.py` `DEFAULTS`, keyed `"<kind>/<feature>"` then bin, with the values listed in spec 7.2 to 7.10.
- Determinism (spec 10): sorted iteration, `rng(purpose) = random.Random(f"{seed}:{purpose}")`, JSON via L0's `loki.schemas.dump_json`, floats `round(x, 6)`, infinities as `"inf"`/`"-inf"`, timings only in `timing.json`.
- Verified Odin III names (v1.0.0, `odin3` commit `00203c56`, probed 2026-10-21): `default()`, `Odin3.load_abc`, `Odin3.passes`, `Odin3.version`, `Odin3.abi_version`, `Odin3.capture_log`, `Design()`, `Design.read_blif(path, techlibs=...)`, `Design.copy`, `Design.close`, `Design.run_pass`, `Design.run_script`, `Design.top`, `Design.modules`, `Design.module(name)`, `Module.name/nodes/nets/wires/ports/node(name)/net(name)/wire(name)/attr/set_attr`, `Node.id/type_name/granularity/name/params/ports/pins/sources/attr/set_attr`, `Port(port, name, direction, width, pins)`, `Pin.net/bit/node`, `Net.id/name/pins/driver/drivers/aliases/attr/set_attr`, `Wire.name/attr`, `Source(file, line, col, end_line, end_col)`, `Odin3Error`. Passes: `read_blif read_techlib read_verilog write_blif write_json write_verilog flatten lower fsm_detect submod cone_check raise`. Not yet on `main` (gated tasks verify with `Odin3.passes()` first): `unmap`, `write_blif --gates-as-names`.
- Cell and port names (probed): `$sop` params `WIDTH`, `COVER`, ports `A` (in), `Y` (out); `$_DFF_P_`/`$_DFF_N_` ports `C`, `D`, `Q`, param `INIT`; latches `E`, `D`, `Q`; binary cells params `A_SIGNED B_SIGNED A_WIDTH B_WIDTH Y_WIDTH`, ports `A`, `B`, `Y`; `$mux` param `WIDTH`, ports `A B S Y`. Attribute keys Loki writes are identifiers without `:` (`loki_hid loki_kind loki_conf loki_proof loki_role loki_fn loki_bus loki_sm lk<k>`), except `odin3:bind` which `cone_check` defines.

## Review Focus

- A LUT that ABC shared between two constructs, so a claimed adder's internal net is also read outside the group: `ConeCheckProver` returns `invalid` without running a pass, `TruthTableProver` decides, and commit falls back to `submod` only. Pinned in Task 4 (`test_internal_net_read_outside_is_invalid`) and Task 11 (`test_commit_falls_back_to_submod`).
- A combinational loop or a flip-flop feedback loop in level 0: `support`, `cone` and the role fixpoint terminate. Pinned in Task 3 (`test_support_with_loop`) and Task 10 (`test_role_loop_terminates`).
- A netlist with nothing to find (L0's constant-only `zero.v`, a pure wire): round 1 reaches the fixed point, every output file is valid, `final_equiv` is `equivalent`. Pinned in Task 11 (`test_constant_only_design`).
- Two hypotheses with equal footprints, both proved (a 1-bit `$eq` and a 1-bit `$mux` reading of the same XNOR LUT): one member in competition, the higher `KIND_RANK` commits, the other becomes `alternative`, the same way every run. Pinned in Task 5 (`test_equivalent_alternatives`).
- A failing `submod` or `raise` during commit: the working copy is discarded, the offender rejected, the commit retried once without it. Pinned in Task 11 (`test_commit_retry_without_offender`).
- Reconvergent fan-out: two cones with equal 1-WL colours but different functions (`g(x, x)` against `g(y, z)`) must never share a proof. Pinned in Task 5a (`test_reconvergence_same_colour`), Task 5b (`test_cone_match_rejects_reconvergence`) and Task 11 (`test_reconvergent_no_transfer`).
- NPN classes must be exact canonical forms (equal keys exactly for NPN-equivalent tables), or the calibration keys split one class. Pinned in Task 5a (`test_npn_4_input_222_classes`, `test_npn_invariance_random`, `test_npn_matches_brute_6`).

---

### Task 1: L0 amendment: `words.json` (spec 12.1)

**Gate:** L0 Tasks 7 and 10 merged. If L0 Task 7 has not started when L1 starts, the controller folds this task into L0's Task 7 and Task 10 briefs instead and skips it here.

**Files:**
- Modify: `loki/build.py`, `loki/schemas.py`, `loki/assemble.py` (`check_dataset`), `docs/specs/2026-10-21-l0-dataset-design.md` (section 3 layout and a new 6.10)
- Create: `loki/words.py`, `tests/test_words.py`

**Interfaces:**
- Consumes: L0 `Snapshot`, `WordCell`, `Port`, `build_labels` second return value (matched word ids per final cell), `Numbering`.
- Produces: `build_words(snap: Snapshot, matched: dict[int, tuple[int, ...]], num: Numbering, word_roles: dict[int, str]) -> dict[str, object]` (spec 12.1 object); `schemas.validate_words(obj: object) -> list[str]`; `words.json` written by `build_floor` next to `labels.csv`.

- [ ] **Step 1: Failing tests** (`tests/test_words.py`, hand-built values): `test_footprint_from_matches` (word 6 matched by final cells 17 and 18 gives `"footprint": ["n17", "n18"]` with names from `Numbering.cell`); `test_const_ports` (an `$add` whose `B` bits are all net 0 or constant nets lists `["B"]`); `test_edges_sorted_and_deduplicated` (two nets from word 6 `Y` to word 9 `D` give one edge); `test_no_original_names` (no `WordCell.name` text appears in the dump); `test_validate_words` (the spec example validates; an unknown key, a non-int id, or an edge to a missing word is an error).
- [ ] **Step 2: Run** `python -m unittest tests.test_words -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `build_words`; a constant bit is a net driven by `$_CONST0_`/`$_CONST1_` or unconnected (0). Call it in `build_floor`, write `words.json` with `dump_json`, validate in `check_dataset`. Add spec section 6.10 (copy spec 12.1 of L1).
- [ ] **Step 4: Run** the full suite, ruff, mypy; rebuild the comparator micro F2 and confirm `words.json` lists `$eq $gt $lt`. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l1-words`), PR, merge.

### Task 2: Normalisation, `FnGraph`, and the L1 Odin III facts

**Gate:** L0 Tasks 1, 2, 6 merged.

**Files:**
- Create: `loki/re/__init__.py`, `loki/re/normalise.py`, `loki/re/fngraph.py`, `tests/test_re_fngraph.py`, `tests/test_re_odin_facts.py`, `tests/data/re/add2.blif` (spec 3.1's 2-bit adder plus one `.latch`, with `.cname` on every cell), `tests/data/re/nocname.blif`

**Interfaces:**
- Consumes: `loki.odin.odin_module()`, `tests.helpers.odin_available()`.
- Produces in `fngraph.py`: `@dataclass(frozen=True) Cell(id: int, name: str, kind: str, type: str, ins: tuple[int, ...], outs: tuple[int, ...], table: int, width: int, clock: int, line: int, params: dict[str, int | str])` (`kind` in `("lut","ff","latch","const","hard")`, `clock` 0 when none); `@dataclass(frozen=True) FnGraph(cells: dict[int, Cell], driver: dict[int, int], readers: dict[int, tuple[tuple[int, int], ...]], names: dict[int, str], pis: tuple[int, ...], pos: tuple[int, ...], line_to_cell: dict[int, int], source_file: str)` with methods `sources() -> frozenset[int]` (spec 4) and `label(cell_id) -> str` (`name` or `c<id>`); `cover_to_table(cover: str, width: int) -> int`; `from_design(design: Any) -> FnGraph`.
- Produces in `normalise.py`: `FLOORS = ("f1-k6","f1-earch","f2","f3")`; `floor_from_path(path: Path) -> str` (raises `ValueError`); `class NormaliseError(Exception)` (message `odin3: <status>` plus the first `error:` log line); `load_level0(path: Path, floor: str, odin3_root: Path | None, techlib: Path | None) -> Any` (spec 3 table; `f1-*` runs `read_techlib "<root>/lib/vtr.o3lib"` first; `.v` input raises `NotImplementedError("f3 gate-level Verilog needs gate mapping")` until Task 18).

- [ ] **Step 1: Failing unit tests** (`tests/test_re_fngraph.py`, pure): `test_cover_on_set` (`"10 1\n01 1\n"`, width 2 gives `0b0110`); `test_cover_dash` (`"1- 1\n"` gives `0b1010`); `test_cover_off_set` (`"11 0\n"` gives `0b0111`); `test_const_covers` (width 0 `"1\n"` gives 1, empty gives 0); `test_floor_from_path` (`d/x/f1-k6/netlist.blif` gives `f1-k6`; `x.blif` raises); `test_label_fallback` (a cell with empty name labels as `c5`).
- [ ] **Step 2: Failing probe tests** (`tests/test_re_odin_facts.py`, skip without Odin III), one per spec 3.1 fact: `test_sop_params_and_ports` (fact 1), `test_cname_is_node_name` (fact 2), `test_sources_are_blif_lines` (fact 3: lines 4, 7, 9 for the three `$sop` of `add2.blif`), `test_raise_sources_union` (fact 4: cone_check + raise of the 2-bit adder as `re_round.py` does; driver of net `y0` is `$add` with lines {4, 7, 9}), `test_submod_names_and_nesting` (fact 5: instance `<V>_i`; nested submod; `Design.copy` after it; net `y0` still found by `Module.net("y0")` in top), `test_attrs_in_verilog` (fact 6: an instance attribute is printed as `(* loki_conf = "0.9" *)`; a raised cell's as a `//` comment; a net attribute appears on its declaration), `test_fsm_detect_marks_nothing_at_bit_level` (fact 8), `test_int_attr_unreadable` (fact 9), `test_passes_present` (fact 10 list).
- [ ] **Step 3: Run** both modules. Expected: FAIL (modules missing); probes SKIP without Odin III.
- [ ] **Step 4: Implement** `cover_to_table`, `normalise.py`, `from_design` (one walk of `top().nodes()`; `$sop` to `lut` or `const` (width 0), `$_DFF_*`/`$_FF_` to `ff`, `$_DLATCH_*` to `latch`, ports to `pis`/`pos` from `Module.ports()` order, any other type `hard`; `line` = `sources()[0].line`).
- [ ] **Step 5: Run** the tests. Expected: PASS. A failing probe means a spec 3.1 fact is wrong: stop, correct the spec with the observed fact, report it in the PR.
- [ ] **Step 6: Commit** (`feat/l1-fngraph`), PR, merge.

### Task 3: Function facts and simulation

**Files:**
- Create: `loki/re/fnfacts.py`, `loki/re/sim.py`, `tests/test_re_fnfacts.py`, `tests/test_re_sim.py`

**Interfaces:**
- Consumes: `FnGraph`, `Cell` (Task 2).
- Produces in `fnfacts.py`: `@dataclass(frozen=True) MuxFact(select: tuple[int, ...], leaves: tuple[int, ...])` (input positions; `leaves[v]` is the data input chosen when the select inputs read value `v`, select bit `j` = `select[j]`); `@dataclass(frozen=True) FnFacts(support: tuple[int, ...], ones: int, parity: int, and_like: bool, or_like: bool, mux: MuxFact | None, maj3: bool)`; `facts(table: int, width: int) -> FnFacts` (cached by `(table, width)`); `cofactor(table: int, width: int, var: int, value: int) -> int` (a table of the same width that ignores `var`); `npn_sig(table: int, width: int) -> tuple[int, ...]` (spec 4).
- Produces in `sim.py`: `simulate(graph: FnGraph, cells: Sequence[int], values: dict[int, int], n: int) -> dict[int, int]` (cells evaluated in topological order of the given set; missing input nets read 0); `class Support` with `__init__(graph: FnGraph, extra_sources: frozenset[int] = frozenset())`, `of(net: int) -> frozenset[int] | None` (`None` when larger than `SUPPORT_MAX = 40`), `loops_cut: int`; `cone(graph: FnGraph, inputs: frozenset[int], outputs: Sequence[int], stop: frozenset[int]) -> tuple[tuple[int, ...], frozenset[int]]` (cells sorted by id, side inputs); `topo_order(graph: FnGraph, cells: Iterable[int]) -> list[int]`.

- [ ] **Step 1: Failing tests:** `test_facts_xor_xnor` (`0b0110` width 2: parity +1; `0b1001`: -1); `test_facts_and_or`; `test_facts_mux2` (table of `s ? b : a` with inputs `(a, b, s)` gives `MuxFact((2,), (0, 1))`); `test_facts_mux4_lut6` (a 6-input 4:1 mux gives a 2-input select); `test_facts_maj3_negated` (majority with input 1 inverted is `maj3`); `test_support_drops_dummy_input`; `test_npn_sig_invariant` (permuting inputs and negating the output give equal signatures; AND2 and XOR2 differ); `test_cofactor`; `test_simulate_bit_parallel` (the `add2.blif` graph built by hand, all 16 vectors in one call equal integer addition); `test_support_with_loop` (two LUTs in a loop: terminates, `loops_cut == 1`); `test_support_cap` (a 41-source cone gives `None`); `test_cone_side_inputs` (a cone that reads a net outside `inputs` reports it as a side input).
- [ ] **Step 2: Run** `python -m unittest tests.test_re_fnfacts tests.test_re_sim -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** `simulate`: a LUT output is the OR over its on-minterms of the AND of its input vectors or their complements under the mask `(1 << n) - 1`; FFs, latches and hard cells are not evaluated (their outputs are inputs). `Support.of`: iterative post-order with an explicit stack; on a back edge cut at the lowest-ID cell, count it.
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l1-facts`), PR, merge.

### Task 4: Claims and provers

**Files:**
- Create: `loki/re/claims.py`, `loki/re/provers.py`, `tests/test_re_claims.py`, `tests/test_re_provers.py`

**Interfaces:**
- Consumes: Tasks 2, 3.
- Produces in `claims.py`: `@dataclass(frozen=True) Claim(op: str, params: tuple[tuple[str, int | str], ...], inputs: tuple[tuple[str, tuple[int, ...]], ...], outputs: tuple[tuple[str, tuple[int, ...]], ...])` with `param(name)`; `REFS: dict[str, Callable[[Mapping[str, int | str], Mapping[str, int]], dict[str, int]]]` for `add add_cin sub eq ne lt le gt ge eq_const mux2 muxn counter shift lfsr` (spec 8; `muxn` returns `None`-free outputs and declares don't-care select values via `DONT_CARE: dict[str, Callable[..., bool]]`); `CONE_TEMPLATES: dict[str, str]` (`add` `$add`, `sub` `$sub`, `eq` `$eq`, ..., `mux2` `$mux`, `counter_en` `$add`); `template_args(claim: Claim) -> str` (`-cell <TYPE> -param A_WIDTH=.. ...`, params sorted by name).
- Produces in `provers.py`: `@dataclass(frozen=True) Verdict(verdict: str, engine: str, detail: str, cex: dict[str, int])`; `parse_cex(text: str) -> dict[str, int]` (`"A[0]=1,B[2]=0"` to `{"A[0]": 1, "B[2]": 0}`); `class TruthTableProver` with `prove(graph: FnGraph, claim: Claim, rng: random.Random) -> Verdict`; `class ConeCheckProver` with `__init__(level0: Any, graph: FnGraph, timeout: int)`, `prove(claim: Claim, key: str) -> Verdict` (`key` is `lk<k>`), `close()`; `prove(claim, graph, cc: ConeCheckProver | None, rng) -> Verdict` (cone_check first when `claim.op in CONE_TEMPLATES`, truth table on `invalid` or when `cc is None`).

- [ ] **Step 1: Failing pure tests:** `test_refs_add_sub_compare` (spot values, widths wrap); `test_ref_counter_modulo` (`modulus=10`: 9 goes to 0, 3 to 4; enable 0 holds); `test_ref_muxn_dont_care` (N=3, select 3 is don't-care); `test_template_args_sorted`; `test_parse_cex`; `test_tt_exact_equivalent` (hand graph of a 2-bit adder vs `add`); `test_tt_exact_differs_with_cex` (same graph vs `sub`: a counterexample that `REFS["sub"]` disagrees with); `test_tt_side_inputs_enumerated` (a cone with a side input that does not matter is `equivalent`, one that matters is `differs`); `test_tt_sampled_unproven` (17 inputs: `detail == "sampled"`, deterministic for a fixed `rng`).
- [ ] **Step 2: Failing Odin III tests** (skip without it): `test_cc_add2_equivalent` (`add2.blif`); `test_cc_wrong_binding_differs` (bind `A[0]` and `B[1]` swapped across bits on a subtractor-shaped claim: `differs` with a parsed cex); `test_internal_net_read_outside_is_invalid` (a fixture where carry net `c0` is also a primary output: `invalid`, no pass run, then `prove` returns the truth-table verdict); `test_cc_error_recovers` (a claim whose template parameter is unknown: `error`, and the next valid claim on the same prover is `equivalent`).
- [ ] **Step 3: Run** the two modules. Expected: FAIL.
- [ ] **Step 4: Implement** per spec 8. `ConeCheckProver` keeps one `level0.copy()`; it computes the group with `sim.cone` and the boundary nets itself (driven inside and read outside, or read inside and driven outside); finds nodes by id in `top().nodes()` once (dict id to `Node`) and nets by name; sets attributes; runs `run_pass("cone_check", f"-attr {key}=1 {template_args(claim)} -timeout {timeout}")`; reads `top().attr("odin3:cone_check")` and `"odin3:cone_cex"`. On `Odin3Error`: `close()` and copy level 0 again.
- [ ] **Step 5: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 6: Commit** (`feat/l1-provers`), PR, merge.

### Task 5: Overlay and the Bayesian model

**Files:**
- Create: `loki/re/bayes.py`, `loki/re/overlay.py`, `tests/test_re_bayes.py`, `tests/test_re_overlay.py`

**Interfaces:**
- Consumes: `Claim` (Task 4), `dump_json` (L0).
- Produces in `bayes.py`: the spec 6.2 constants by those names; `logit(p: float) -> float`; `sigmoid(x: float) -> float` (handles `±inf`); `@dataclass(frozen=True) Calib(floor: str, priors: dict[str, float], llr: dict[str, dict[str, float]], source: str)`; `DEFAULTS: Calib` (priors empty meaning 0; `llr` = every default of spec 7.2 to 7.10 keyed `"<kind>/<feature>"`); `load_calib(path: Path | None) -> Calib` (`None` gives `DEFAULTS`; refuses `schema != 1`); `Calib.prior(detector: str, kind: str) -> float`; `Calib.feature_llr(kind: str, feature: str, bin: str) -> float` (0.0 when unseen).
- Produces in `overlay.py`: `Evidence`, `Hypothesis` exactly as spec 5 (mutable dataclasses); `@dataclass(frozen=True) KindSpec(level: int, exclusive: bool, commit: str, rank: int)` (`commit` in `("no","attrs","submod","raise+submod")`; level bit 0, bus 1, word 2, unit 3); `KINDS: dict[str, KindSpec]` (spec 6.1; `rank` from spec 6.5 `KIND_RANK`, non-ranked kinds 0); `register_kind(name: str, spec: KindSpec) -> None` (refuses a duplicate); `class Overlay` with `add(cand: Candidate, detector: str, round: int) -> Hypothesis` (merge key of spec 5; ids `h1, h2, ...`), `get(hid) -> Hypothesis`, `by_kind(kind) -> list[Hypothesis]`, `committed() -> list[Hypothesis]`, `link_nesting() -> None`, `rescore(calib: Calib, round: int) -> float` (returns the largest absolute log-odds change), `apply_verdict(hid: str, v: Verdict, round: int) -> None`, `compete(round: int) -> None` (sets `p_comp`, `conflicts`, rejections), `select_commits() -> list[Hypothesis]` (spec 9.2 step 6), `to_json(graph: FnGraph) -> dict[str, object]`. `Candidate` is imported from `loki.re.detectors` (defined in Task 6); until then this task defines it there with the spec 7.1 fields.

- [ ] **Step 1: Failing tests:** `test_merge_key_dedupes` (same kind, cells, params: one hypothesis, features updated, two evidence records); `test_logodds_sum_and_cap` (feature LLRs summing to 9 are capped at `STRUCT_CAP`); `test_proof_sets_confirmed` (`equivalent` gives `log_odds >= 9.21`, `confirmed`); `test_refute_is_final` (`differs` gives `-inf`, `refuted`; later positive features do not revive it); `test_conflict_rule` (intersecting exclusive footprints conflict; a strict subset nests and becomes a child; equal footprints conflict; a non-exclusive kind never conflicts); `test_p_comp_normalisation` (two conflicting hypotheses with log-odds 0 each: `p_comp = 1/3` each); `test_p_comp_inf_members` (one `+inf`: it gets 1, the other 0); `test_equivalent_alternatives` (equal footprints, both `confirmed`, kinds `mux` and `comparator`: one competition member, `select_commits` returns the `comparator` (higher rank), the `mux` becomes `alternative`; repeated runs identical); `test_child_raises_parent` (two confirmed children add `2 * 1.10`; four add at most `3.30`; a refuted child adds `-2.30`); `test_conflict_with_committed_rejected`; `test_select_commits_order` (greedy by `p_comp`, rank, size, id; a hypothesis whose exclusive child is not committed is skipped); `test_calib_default_and_file` (`load_calib(None)` gives `DEFAULTS`; a file with `schema: 2` raises); `test_overlay_json_deterministic` (dump twice equal; infinities as strings).
- [ ] **Step 2: Run** `python -m unittest tests.test_re_bayes tests.test_re_overlay -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** Conflict components by union-find over pairs found through a cell-to-hypotheses index (no all-pairs scan); `p_comp` with log-sum-exp per component.
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l1-overlay`), PR, merge.

### Task 5a: Structural features package `loki.features` (spec 6.7: role flags, A colour refinement, B NPN classes)

Approved by Peter, 2026-10-21. Runs before the detectors because Tasks 6 to 8, 11 and 14 consume it; L2 reuses it unchanged (L2 plan Tasks 9 and 10a).

**Files:**
- Create: `loki/features/__init__.py`, `loki/features/graph.py`, `loki/features/roles.py`, `loki/features/npn.py`, `loki/features/wl.py`, `tests/features_fixtures.py`, `tests/test_features_graph.py`, `tests/test_features_roles.py`, `tests/test_features_npn.py`, `tests/test_features_wl.py`, `tests/test_features_scale.py`

**Interfaces:**
- Consumes: nothing from `loki.re` or `loki.analysis`; standard library only (`hashlib`, `functools`, `itertools`; no numpy, spec 18.1).
- Produces in `__init__.py`: `WL_ROUNDS = 4`, `NPN_ENUM_MAX = 100000`, `FEATURES_VERSION = 1`.
- Produces in `graph.py`: `@dataclass(frozen=True) FeatureGraph(node_ids: tuple[str, ...], kind: tuple[str, ...], type: tuple[str, ...], width: tuple[int, ...], table: tuple[int, ...], src: tuple[int, ...], dst: tuple[int, ...], pin: tuple[str, ...], net: tuple[int, ...])` (edges driver to sink, sorted by `(dst, pin, src)`; `table` -1 when none; spec 6.7) with `n_nodes`, `n_edges`, `adjacency() -> tuple[tuple[tuple[int, ...], ...], tuple[tuple[int, ...], ...]]` (in-edge and out-edge indices per node, cached); `validate_feature_graph(fg: FeatureGraph) -> list[str]`; `from_graph_json(obj: Mapping[str, object]) -> FeatureGraph` (L0 spec 6.4: node ids and order kept, `lut_table` hex to `int(hex, 16)`, `""` to -1, pins as given, net `n<k>` to `k`).
- Produces in `roles.py` (L2 spec 8.1 and 8.2 exactly): `CLASS_NAMES = ("signal", "clock", "reset", "enable", "const")`; `@dataclass(frozen=True) SignalConfig(min_fanout: int = 16, dominance: float = 0.8)`; `@dataclass(frozen=True) NodeRole(clock_domain: int, has_reset: int, const_inputs: int, enable: int)`; `@dataclass(frozen=True) NetRoles(net_class: dict[int, str], edge_class: tuple[str, ...], nodes: tuple[NodeRole, ...], classified: dict[str, int], clock_domains: int)`; `restrict(table: int, width: int, k: int, value: int) -> int` (the table over the other inputs, order kept); `is_forcing(table: int, width: int, k: int) -> bool`; `is_hold(table: int, width: int, k: int, q: int) -> bool`; `classify_nets(fg: FeatureGraph, cfg: SignalConfig = SignalConfig()) -> NetRoles` (check order `const`, `clock`, `reset`, `enable`, else `signal`; clock domains by lowest driver node index; `has_reset` and `enable` propagate from a D-LUT to the FFs it feeds).
- Produces in `npn.py`: `@dataclass(frozen=True) NpnClass(width: int, table: int, exact: bool)` with property `key` (`"<width>:<hex>"`, lower-case hex); `shrink_support(table: int, width: int) -> tuple[int, int, tuple[int, ...]]` (table over the support, its width, the kept input positions); `apply_transform(table: int, width: int, perm: Sequence[int], neg_in: int, neg_out: bool) -> int`; `npn_class(table: int, width: int) -> NpnClass` (`functools.lru_cache(maxsize=None)`; `ValueError` for width > 6); `npn_brute(table: int, width: int) -> NpnClass` (all `k! 2^k 2` transforms, the test oracle); `NAMED: dict[str, NpnClass]` (`const buf and2 xor2 and3 xor3 maj3 mux2 and4 xor4 mux4`, spec 6.7 B); `class_name(c: NpnClass) -> str` (a `NAMED` key or `"other"`); `stats() -> dict[str, int]` (`distinct_tables`, `worst_enum`, `inexact`).
- Produces in `wl.py`: `@dataclass(frozen=True) WLConfig(start: str = "npn", direction: str = "both", rounds: int = WL_ROUNDS)` (`start` in `table npn`, `direction` in `in out both`; property `name` = `"<start>/<direction>"`); `start_label(fg: FeatureGraph, roles: NetRoles, v: int, cfg: WLConfig) -> str`; `@dataclass(frozen=True) WLResult(config: WLConfig, colours: tuple[tuple[str, ...], ...], stable_round: int | None)` (`colours[r][v]`, 16 hex digits, `r` from 0 to `rounds`); `refine(fg: FeatureGraph, roles: NetRoles, cfg: WLConfig) -> WLResult` (edges whose `roles.edge_class` is not `signal` removed); `classes(res: WLResult, r: int) -> dict[str, tuple[int, ...]]`; `@dataclass(frozen=True) Partition(class_of: tuple[int, ...], n_classes: int)`; `stable_partition(fg: FeatureGraph, roles: NetRoles, cfg: WLConfig) -> Partition`; `@dataclass(frozen=True) Quotient(size: tuple[int, ...], label: tuple[str, ...], edges: tuple[tuple[int, int, str, int], ...])` (`(C, D, pin label, count per node of D)`); `quotient(fg: FeatureGraph, roles: NetRoles, part: Partition, cfg: WLConfig) -> Quotient`.
- Produces in `tests/features_fixtures.py`: `ripple_adder_fg(bits: int, carry_nets: bool = True) -> FeatureGraph`; `reconvergent_pair_fg() -> FeatureGraph` (LUT2 `g` reading `(x, x)` and an equal LUT2 reading `(y, z)`, `x y z` PIs); `sync_fg(n_ff: int, reset: bool = False, enable: bool = False, clocks: int = 1) -> FeatureGraph` (the twin of L2's `make_sync_design`); `synthetic_netlist(n: int, seed: int) -> FeatureGraph` (netlist-like, deterministic: LUT2 to LUT6, 10 % FFs on one clock, a reset of fan-out 1000, about 3 edges per node).

- [ ] **Step 1: Failing tests.** `tests/test_features_graph.py`: `test_from_graph_json_example` (the L0 spec 6.4 example: table `0x9009`, pin `I0`, net 3); `test_validate_feature_graph` (an edge to a missing node, an unsorted edge list: errors). `tests/test_features_roles.py`: `test_restrict_and_forcing` (AND2 table `0b1000`: `restrict(8, 2, 0, 0) == 0`, forcing on both inputs); `test_is_hold_mux` (`en ? d : q`: hold on `en`, not forcing); `test_clock_domains` (`sync_fg(4, clocks=2)`: domains 1 and 2 by lowest driver index); `test_reset_and_enable_found` (`sync_fg(20, reset=True)` and `enable=True`); `test_below_min_fanout_is_signal` (`n_ff=5`); `test_latch_en_not_clock`; `test_const_nets_any_fanout`. `tests/test_features_npn.py`: `test_shrink_support` (a 6-input table using inputs 1 and 4: width 2, positions `(1, 4)`); `test_npn_3_input_14_classes` (all 256 tables: 14 keys, each equal to `npn_brute`); `test_npn_4_input_222_classes` (all 65,536 tables: 222 keys, the known count of 4-input NPN classes; if it runs over 30 s it moves under `LOKI_SCALE=1` and the PR says so); `test_npn_invariance_random` (2,000 random 5- and 6-input tables, each under 3 random NPN transforms from a seeded `random.Random`: equal keys); `test_npn_matches_brute_6` (5 random 6-input tables and every `NAMED` table: equal to `npn_brute`); `test_named_classes` (`a^b^c` and `~a^b^~c` are `xor3`; majority with one inverted input is `maj3`; `s ? b : a` and `s ? ~b : a` are `mux2`; AND2 and OR2 share a class); `test_npn_stats` (`worst_enum <= 92160`, `inexact == 0`). `tests/test_features_wl.py`: `test_colours_are_sha_strings` (16 lower-case hex digits; two runs equal); `test_cross_graph_comparable` (the ripple adder built twice with different node ids and order: equal colour per corresponding node); `test_stable_round` (a chain of 6 LUTs, `rounds=8`: `stable_round` is set and later rounds repeat the partition); `test_directions_differ` (two cells with equal fan-in and different readers: equal `in` colours, different `both` colours); `test_npn_variant_ignores_pin_order` (`a & ~b` and `~a & b` over the same inputs: equal round-0 `npn` colours, different `table` colours); `test_role_edges_removed` (`sync_fg(20, reset=True)`: FF colours do not depend on the reset driver's colour; `has_reset` is in the start label); `test_reconvergence_same_colour` (`reconvergent_pair_fg`: both `g` cells have equal `table/in` colours in every round, the 1-WL limit spec 8.1 relies on); `test_stable_partition_equals_refine` (50 seeded random graphs of 5 to 40 nodes, all three directions: `refine` run to stability and `stable_partition` give the same partition); `test_quotient_equitable` (every node of class D receives exactly the listed count from class C). `tests/test_features_scale.py` (only with `LOKI_SCALE=1`): `synthetic_netlist(100_000, 1)`, each step in a fresh subprocess: `refine` (`npn/both`, 4 rounds) under 2 x 30 s, `stable_partition` under 2 x 60 s, `npn_class` over every distinct table under 60 s, peak RSS (`resource.getrusage`) under 2 GB; the numbers are printed for the PR.
- [ ] **Step 2: Run** `python -m unittest tests.test_features_graph tests.test_features_roles tests.test_features_npn tests.test_features_wl -v`. Expected: FAIL.
- [ ] **Step 3: Implement** per spec 6.7. NPN: shrink to the support; output and input phases from the ones counts; tie groups of the cofactor sort; symmetric inputs (equal table under their transposition, checked on the phase-assigned table) kept in one order; permutations within tie groups by adjacent transpositions (Steinhaus-Johnson-Trotter) and phases in Gray-code order, so each step is one swap or one flip of the integer table with precomputed masks per width; keep the minimum; record the transform count in `stats()`. WL: per round, per node the tuple `(c_r(v), sorted in pairs, sorted out pairs)` encoded as UTF-8 and hashed with `hashlib.sha256`; stable when the number of distinct colours does not grow. `stable_partition`: a work queue of splitter classes; for each splitter count labelled neighbours per node, split every class by the count, and enqueue all parts but the largest (the smaller-half rule).
- [ ] **Step 4: Run** the tests, ruff, mypy, then `LOKI_SCALE=1 python -m unittest tests.test_features_scale -v` once and paste the numbers into the PR. Expected: PASS. If the NPN budget fails, add the k = 6 semi-canonical fallback of spec 6.7 B (`exact = False`), keep `test_npn_invariance_random` for widths up to 5, and report it; a WL budget miss is reported with its numbers for the controller (spec 18.1), not hidden.
- [ ] **Step 5: Commit** (`feat/l1-features`), PR, merge.

### Task 5b: Structural features in L1: adapter, `StructFeatures`, family weights, `cone_match`

**Files:**
- Create: `loki/re/structural.py`, `tests/test_re_structural.py`
- Modify: `loki/re/bayes.py`, `loki/re/overlay.py`, `tests/test_re_bayes.py`, `tests/test_re_overlay.py`

**Interfaces:**
- Consumes: Tasks 2 to 5 (`FnGraph`, `sim.cone`, `Claim`, `Calib`, `Overlay`), Task 5a.
- Produces in `structural.py`: `feature_graph(graph: FnGraph) -> FeatureGraph` (spec 6.7: level-0 cells by `graph.label`, plus `pi:<net name>` and `po:<net name>` nodes; pins `I<k>`, `D`, `CLK`, `EN`, `I`, hard formal names); `@dataclass(frozen=True) StructFeatures(fg: FeatureGraph, index: dict[int, int], roles: NetRoles, wl: dict[str, WLResult], npn: dict[int, NpnClass], seconds: float)` (`index` cell id to node index; `wl` keyed `"table/in"`, `"npn/in"`, `"npn/both"`) with `colour(cell: int, variant: str, r: int) -> str`, `npn_of(cell: int) -> NpnClass | None`, `cell_keys(cell: int) -> tuple[str, ...]` (`"2:<c>"`, `"1:<c>"`, `"0:<c>"` of `npn/both`, spec 6.7 item 1 backoff order), `class_depth(cells: Sequence[int], variant: str) -> int` (deepest round at which all share one colour), `report() -> dict[str, object]` (spec 11 `features` keys except the transfer counts); `build_features(graph: FnGraph, rounds: int = WL_ROUNDS) -> StructFeatures`; `cone_match(graph: FnGraph, c0: Claim, c: Claim) -> bool` (spec 8.1); `transfer_key(h: Hypothesis, sf: StructFeatures, graph: FnGraph) -> tuple[str, ...] | None` (spec 8.1 group key; `None` without a claim).
- Produces in `bayes.py`: `TRANSFER_ROUND = 2`, `CALIB_WL_DEPTH = 2`, `NODE_MIN_COUNT = 5`, `CALIB_FOLDS = 2`, `WEIGHT_GRID = tuple(i / 10 for i in range(11))`; `family_of(feature: str) -> str` (spec 6.4); `Calib` gains `node_llr: dict[str, dict[str, float]]` and `weights: dict[str, float]` (defaults empty: no node table, every weight 1.0), `Calib.weight(family: str) -> float`, `Calib.node_score(kind: str, keys: Sequence[str]) -> float | None` (the first key present in `node_llr[kind]`); `wl_npn_bin(mean_llr: float | None) -> str` (spec 6.7 item 1 bins). `load_calib` reads the new keys when present.
- Produces in `overlay.py`: `rescore` weights feature LLRs by family (spec 6.2); `Overlay.apply_transfer(hid: str, src: str, round: int) -> None`; `Overlay.revoke_transfers(src: str, round: int) -> list[str]` (spec 8.1).

- [ ] **Step 1: Failing tests** (`tests/test_re_structural.py`, pure unless stated): `test_feature_graph_from_fngraph` (a hand-built `FnGraph` of `add2.blif`: three LUT nodes, one FF, PI and PO nodes, LUT edges `I0..`, FF edges `D` and `CLK`); `test_feature_graph_matches_graph_json` (skip without Odin III: the L0 F2 floor of `bm_DL_four_bit_adder_continuous_assign` built with L0's `build_floor` into a temp dir; `feature_graph(from_design(...))` equals `from_graph_json(graph.json)` for every cell node, and for PI/PO nodes up to the naming `pi:<net>` against the `graph.json` node driving that net); `test_build_features_variants` (three variants, an `npn` class for every LUT cell); `test_cell_keys_backoff_order`; `test_class_depth`; `test_cone_match_isomorphic` (two 2-bit adders on disjoint inputs); `test_cone_match_rejects_reconvergence` (`g(x, x)` against `g(y, z)`: equal colours, `False`); `test_cone_match_rejects_different_table`; `test_cone_match_rejects_side_input`; `test_transfer_key_groups` (two 2-bit adders: equal keys; a 3-bit adder: a different key). In the bayes/overlay modules: `test_family_of` (`npn_sum` to `npn`, `wl_depth` and `wl_npn` to `wl`, `k` to `struct`); `test_weighted_rescore` (`weights = {"npn": 0.5}`: an `npn_sum` LLR of 2.30 adds 1.15; `STRUCT_CAP` applies to the weighted sum); `test_node_score_backoff`; `test_wl_npn_bins` (edges -2, -0.5, 0.5, 2; `None` gives `unseen`); `test_apply_transfer_confirms` (status `confirmed`, `log_odds >= PROOF_LO`, `proof["engine"] == "transfer"`, `proof["from"] == "h1"`); `test_revoke_transfers` (records valued `revoked`, status back to `open`, `log_odds` recomputed without them); `test_calib_new_fields_roundtrip`.
- [ ] **Step 2: Run** `python -m unittest tests.test_re_structural tests.test_re_bayes tests.test_re_overlay -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** `build_features`: `feature_graph`, `classify_nets`, the three `refine` runs, `npn_class` per LUT cell, wall time into `seconds` (written only to `timing.json`). `cone_match`: two `sim.cone` calls, then the lockstep walk of spec 8.1 with two dicts for the one-to-one map.
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l1-structural`), PR, merge.

### Task 6: Detector framework, view, `bus` and `ff_pattern`

**Files:**
- Create: `loki/re/detectors/__init__.py`, `loki/re/detectors/bus.py`, `loki/re/detectors/ff_pattern.py`, `loki/re/view.py`, `tests/re_fixtures.py` (hand-built `FnGraph` builders shared by detector tests), `tests/test_re_detectors_api.py`, `tests/test_re_bus.py`, `tests/test_re_ff_pattern.py`

**Interfaces:**
- Consumes: Tasks 2 to 5, 5b (`StructFeatures`).
- Produces in `detectors/__init__.py`: `Candidate`, `Detector` (Protocol), `RoundContext` exactly as spec 7.1 (`overlay` typed as `OverlayReader`, a Protocol with `get`, `by_kind`, `children_of`, `committed`; `features: StructFeatures | None = None`); `DETECTOR_ORDER` (spec 7.1); `load_detectors(names: Sequence[str] | None) -> list[Detector]` (built-ins in order, then entry points of group `loki.detectors` by name; an unknown name raises `ValueError`); `check_candidate(det: Detector, cand: Candidate) -> None` (kind in `det.kinds` and in `KINDS`, else `ValueError`); `bin_count(n: int, edges: Sequence[int], labels: Sequence[str]) -> str` (shared binning helper; the `k` bins of spec 7.4 are `bin_count(k, (2, 3, 5, 9), ("2", "3-4", "5-8", "9+"))` with values below 2 refused).
- Produces in `view.py`: `@dataclass(frozen=True) Piece(hid: str, kind: str, ins: tuple[int, ...], outs: tuple[int, ...], cells: frozenset[int])`; `@dataclass(frozen=True) View(free_cells: tuple[int, ...], pieces: tuple[Piece, ...], absorbed: frozenset[int], support: Support)`; `View.level0(graph: FnGraph) -> View` (round 1, no pieces); `View.build(working: Any, graph: FnGraph, overlay: Overlay) -> View` (spec 9.2 step 1; Odin III, tested in Task 11).
- Produces: `BusDetector` (`name = "bus"`, `kinds = ("bus",)`) and `FfPatternDetector` (`name = "ff_pattern"`, `kinds = ("ff_en", "ff_srst", "register")`), both with `propose(ctx)`.

- [ ] **Step 1: Failing tests:** `test_unknown_detector_name`, `test_candidate_kind_checked`, `test_plugin_entry_point_loaded` (a fake entry point via `importlib.metadata` monkeypatch); `test_bus_k_slices_shared_select` (four 3-input mux LUTs sharing net `s`, disjoint data: one `bus`, `k = "3-4"`, `ctrl_fanout_exact = "yes"`, slices ordered by lowest data net id, `order_source = "net_id"`); `test_bus_rejects_overlapping_data` (two members share a data net: none); `test_bus_ctrl_fanout_not_exact` (an extra non-member reads `s`: `"no"`); `test_bus_groups_by_colour_class` (with `features` from `build_features`: four mux LUTs whose tables are input permutations of one another: one `bus`; `wl_depth` bin present); `test_bus_wl_depth_bins` (bins `0`, `1`, `2-3`, `4` of spec 7.4); `test_bus_without_features_uses_npn_sig` (`features=None`: grouping by `(kind, npn_sig, len(ins))`, `wl_depth = "n/a"`); `test_ff_enable_detected` (D LUT = `en ? d : Q`: `ff_en` with `active = 1`, feature `en_fn_exact = "yes"`); `test_ff_srst_detected` (D LUT = `d & ~r`: `ff_srst`, `active = 1`, `value = 0`; `rst_fanout` bins `1`, `2-3` for one and three FFs); `test_ff_reset_over_enable` (D = `r ? 0 : (en ? d : Q)`: both hypotheses); `test_register_group` (four FFs sharing clock and `en`: one `register` with the four `ff_en` as children, `shared_ctrl = "en"`); `test_no_register_without_shared_control` (FFs sharing only the clock); `test_candidates_sorted` (output order is `(min(cells), kind, params JSON)`).
- [ ] **Step 2: Run** the three modules. Expected: FAIL.
- [ ] **Step 3: Implement** per spec 7.1, 7.3, 7.4 (bus slices grouped by `ctx.features.colour(cell, "npn/in", 0)` when `ctx.features` is set, one dict pass; `wl_depth` from `class_depth(slices, "npn/in")`). The D cone for `ff_pattern` uses `sim.cone` with stop at sources and the depth-3, 12-input limit of spec 7.3; cofactor tests use `fnfacts.cofactor` on the cone's composed table (built by `simulate` over all `2^m` patterns, `m <= 12`).
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l1-bus-ff`), PR, merge.

### Task 7: `arith` detector (carry chains, adders, subtractors, comparators)

**Files:**
- Create: `loki/re/detectors/arith.py`, `tests/test_re_arith.py`

**Interfaces:**
- Consumes: Tasks 3 to 6, 5a (`npn_class`, `NAMED`).
- Produces: `ArithDetector` (`name = "arith"`, `kinds = ("adder","subtractor","adder_cin","comparator","eq_const")`); `cut_class(graph: FnGraph, inputs: Sequence[int], out: int) -> NpnClass | None` (the function of `out` over the cut by `simulate` over all patterns; `None` when the cone has side inputs); `carry_nets(view: View, chain: tuple[int, ...]) -> dict[int, int]` (bit to carry net, spec 7.5); `find_chains(view: View, graph: FnGraph) -> list[tuple[tuple[int, ...], tuple[tuple[int, int], ...]]]` (output nets, new source pair per bit); `orient(graph: FnGraph, chain: tuple[int, ...], pairs: Sequence[tuple[int, int]]) -> str | None` (`"add"`, `"sub:<orientation bits>"`, `None` for mixed).

- [ ] **Step 1: Failing tests** with fixtures built by a helper that maps a small reference circuit to LUTs of at most 6 inputs (in `tests/re_fixtures.py`): `test_ripple_adder_4_chain` (4-bit ripple: one chain of 4 with pairs per bit; candidate `adder` with claim `add`, `Y_WIDTH = 5` when a carry-out net exists); `test_lut6_packed_adder_chain` (sum bit 2 computed directly from `a0..a2, b0..b2` with no carry net: still a chain); `test_subtractor_orientation` (4-bit `a - b`: `subtractor`, claim inputs `A` = the `a` nets); `test_mixed_orientation_no_candidate`; `test_carry_in_gives_adder_cin`; `test_comparator_from_buses` (a 4-bit `a < b` output with buses for `a`, `b` in the overlay: six ops times two pairings proposed, each with a claim); `test_eq_const` (an AND of literals over 5 sources: `eq_const` with `C` the minterm; an OR gives `ne`); `test_support_none_skipped` (cones over `SUPPORT_MAX` give nothing); `test_npn_sum_carry_ripple` (4-bit ripple with explicit carry LUTs: `npn_sum = "all"`, `npn_carry = "all"`); `test_npn_no_cut_packed` (the LUT6-packed chain: `no_cut`); `test_subtractor_npn_classes` (sum bits `xor3`, borrow nets `maj3`); `test_npn_low_chain_not_proved` (a 2-bit support chain that is not an adder, outputs not read by a register or primary output: `npn_sum = "low"`, `npn_carry = "low"`, and with `DEFAULTS` its `p_comp` is below `PROVE_P`, so the loop would spend no proof on it); `test_comparator_npn_xor2`; `test_features_none_no_npn` (`ctx.features = None`: no `npn_*` features).
- [ ] **Step 2: Run** `python -m unittest tests.test_re_arith -v`. Expected: FAIL.
- [ ] **Step 3: Implement** spec 7.5. `find_chains`: index nets by support size; for each net `y` with support size 2 or 3, extend greedily to every superset net with exactly two new sources (all extensions, deduplicated by output tuple). `orient` uses `simulate` with two vectors per bit.
- [ ] **Step 4: Run** tests, ruff, mypy, plus an Odin III test `test_arith_on_micro_adder` (skip without it): the L0 F2 BLIF of `bm_DL_four_bit_adder_continuous_assign` (built through L0's `build_floor` into a temp dir) gives at least one `adder` or `adder_cin` candidate of width 4. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l1-arith`), PR, merge.

### Task 8: `mux` detector (mux bits, trees, word muxes)

**Files:**
- Create: `loki/re/detectors/mux.py`, `tests/test_re_mux.py`

**Interfaces:**
- Consumes: Tasks 3 to 6 (`facts().mux`, `bus` hypotheses), 5a (`class_name`).
- Produces: `MuxDetector` (`name = "mux"`, `kinds = ("mux_bit","mux_tree","mux")`).

- [ ] **Step 1: Failing tests:** `test_mux_bit_from_lut3` (claim `muxn` with `N = 2`); `test_mux4_in_one_lut6` (`N = 4`, select order from `MuxFact.select`); `test_tree_composition` (two 2:1 mux LUTs feeding a third with a disjoint select: `mux_tree` `N = 4`, `S_WIDTH = 2`, children the three `mux_bit`); `test_tree_not_composed_when_shared` (the inner mux output is also read elsewhere); `test_word_mux_from_bus` (a `bus` of four `mux_bit` sharing `s` in the overlay: `mux` `WIDTH = 4`, claim `mux2` with `A`, `B`, `S`, `Y` bound per slice, children the slices); `test_word_muxn_from_bus_of_trees` (claim `muxn`); `test_mux_bit_npn_class` (a LUT3 mux: `npn_class = "mux2"`; a LUT6 4:1 mux: `"mux4"`; a mux merged with an AND in one LUT: `"other"`); `test_word_mux_copies_wl_depth` (the bus's `wl_depth` bin appears on the word `mux`).
- [ ] **Step 2: Run** `python -m unittest tests.test_re_mux -v`. Expected: FAIL.
- [ ] **Step 3: Implement** spec 7.6.
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l1-mux`), PR, merge.

### Task 9: `seqfn` and `fsm` detectors

**Files:**
- Create: `loki/re/detectors/seqfn.py`, `loki/re/detectors/fsm.py`, `loki/re/seqtable.py`, `tests/test_re_seqfn.py`, `tests/test_re_fsm.py`

**Interfaces:**
- Consumes: Tasks 3 to 6.
- Produces in `seqtable.py`: `@dataclass(frozen=True) SeqTable(q: tuple[int, ...], controls: tuple[int, ...], exact: bool, rows: dict[tuple[int, int], int])` (`(q value, control value) -> next q`); `transition_table(graph: FnGraph, q: Sequence[int], rng: random.Random) -> SeqTable` (D nets of the FFs whose Q nets are `q`; exact when `k + |C| <= 16`, else `SAMPLE_N` sampled rows); `classify(t: SeqTable) -> dict[int, str]` (per control value: `hold inc dec modulo-M load-const shift-l shift-r linear other`); `reachable(t: SeqTable, start: int) -> tuple[list[int], list[tuple[int, int, int]]]`.
- Produces: `SeqfnDetector` (`name = "seqfn"`, `kinds = ("counter","shift_reg","lfsr")`), `FsmDetector` (`name = "fsm"`, `kinds = ("fsm",)`, plus `fsm_detect_marks(working: Any) -> dict[frozenset[int], str]` called by the loop when the level holds `$dff`/`$adff`, results passed in `RoundContext` via a new optional field `fsm_marks: Mapping[frozenset[int], str]`, default empty).

- [ ] **Step 1: Failing tests** (fixtures from small reference sequential circuits mapped to LUTs + `ff` cells): `test_up_counter_with_enable` (claim `counter`, `dir = "up"`, `modulus = 0`, `en` set; also a `counter_en` cone_check claim); `test_modulo_10_counter` (`Prob035`-like count 1..10 or `Prob040` count 0..9: `modulus` recovered, terminal set as spec 7.7); `test_down_counter`; `test_shift_register_4` (`shift_reg` width 4, serial input net); `test_lfsr_taps` (a 5-bit Fibonacci LFSR: `lfsr` with its taps); `test_sampled_table_when_wide` (k = 20: `exact = False`, feature `table = "sampled"`); `test_fsm_three_states` (a 2-bit state register with one input, equality decoders on the state: `fsm` candidate, `decoder_readers = ">=0.5"`, `counter_like = "no"`, `reset_found` from a sync reset, `params["states"] == 3`, the transition rows); `test_fsm_counter_like_penalised` (a counter group also offered to `fsm` carries `counter_like = "yes"`); `test_fsm_detect_marks_feature` (a `fsm_marks` entry gives `fsm_detect = "marked"`).
- [ ] **Step 2: Run** the two modules. Expected: FAIL.
- [ ] **Step 3: Implement** spec 7.7 and 7.8. Group discovery in `seqfn`: Q-support chains, shift chains, SCCs (iterative Tarjan); `classify` tests each pattern on all rows of one control value; `linear` checks every pair of sampled rows up to 256 pairs.
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l1-seq`), PR, merge.

### Task 10: `role` and `unit` detectors

**Files:**
- Create: `loki/re/detectors/role.py`, `loki/re/detectors/unit.py`, `tests/test_re_role.py`, `tests/test_re_unit.py`

**Interfaces:**
- Consumes: Tasks 5, 6; the overlay kinds of Tasks 6 to 9.
- Produces: `RoleDetector` (`name = "role"`, `kinds = ("role",)`), `predict_role(h: Hypothesis) -> str` (spec 7.10: `mixed`, `control`, `datapath`); `UnitDetector` (`name = "unit"`, `kinds = ("datapath_unit","control_unit")`).

- [ ] **Step 1: Failing tests:** `test_select_driver_is_control` (a cell driving the `S` of a confirmed `mux`: `role_prop = "control"`); `test_adder_input_is_data`; `test_fsm_cells_control`; `test_mixed`; `test_role_loop_terminates` (an FF feedback loop through a `role`-seeded cell); `test_datapath_unit` (three committed pieces `adder`, `register`, `mux` connected by data nets: one `datapath_unit`, children the three, `internal_ratio` bin); `test_control_unit` (a committed `fsm` and the control cells it drives); `test_piece_in_one_unit_only`; `test_units_not_before_round_2`.
- [ ] **Step 2: Run** the two modules. Expected: FAIL.
- [ ] **Step 3: Implement** spec 7.9, 7.10; the role fixpoint follows L0 spec 7.5 (an explicit worklist, monotone sets) over level-0 readers, with control sinks taken from the hypotheses listed in spec 7.10.
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l1-role-unit`), PR, merge.

### Task 11: Commit and the round loop

**Gate:** L0 Task 7 merged (`loki.equiv.check_equiv`).

**Files:**
- Create: `loki/re/commit.py`, `loki/re/loop.py`, `tests/test_re_commit.py`, `tests/test_re_loop.py`, `tests/data/re/zero.blif`, `tests/data/re/add2x4.blif`, `tests/data/re/reconv.blif`

**Interfaces:**
- Consumes: Tasks 2 to 10 (and 5a, 5b: `build_features`, `transfer_key`, `cone_match`, `apply_transfer`, `revoke_transfers`), `loki.equiv.check_equiv(a: str, b: str, odin3_root: Path, match_unnamed: bool) -> EquivResult`.
- Produces in `commit.py`: `@dataclass(frozen=True) CommitResult(design: Any, forms: dict[str, str], failed: tuple[str, ...])`; `commit(working: Any, hyps: Sequence[Hypothesis], overlay: Overlay, graph: FnGraph, timeout: int) -> CommitResult` (spec 9.3, on `working.copy()`; the input design is not changed); `fn_text(h: Hypothesis) -> str` (the `loki_fn` texts of spec 9.3).
- Produces in `loop.py`: `@dataclass(frozen=True) ReOptions(netlist: Path, floor: str, odin3_root: Path | None, techlib: Path | None, calib: Path | None, seed: int, max_rounds: int, timeout: int, time_budget: int, detectors: tuple[str, ...] | None, commit: bool, keep_levels: Path | None, features: str = "all")` (`"all"` or `"none"`, spec 6.7 item 6); `@dataclass RunResult(level0: Any, final: Any, graph: FnGraph, overlay: Overlay, rounds: list[dict[str, object]], stop_reason: str, final_equiv: dict[str, object], timing: dict[str, object], notes: dict[str, str])`; `run_re(opts: ReOptions) -> RunResult`.

- [ ] **Step 1: Failing Odin III tests** (`tests/test_re_commit.py`, skip without it): `test_raise_and_submod_adder` (overlay with a confirmed `adder` on `add2.blif`: module `adder_h1` holds one `$add`; instance `adder_h1_i` has `loki_hid = "h1"`, `loki_conf`, `loki_proof = "equivalent"`, `loki_fn = "Y = A + B"`; level 0 unchanged); `test_submod_only_for_const_claim` (an `eq_const`: module holds the `$sop` cells, `forms["h1"] == "submod"`); `test_commit_falls_back_to_submod` (the group's internal net read outside: no raise, `submod`); `test_nested_commit` (a committed child instance inside a parent's module); `test_commit_retry_without_offender` (two hypotheses, one whose module name already exists in the design: the other commits, the offender is in `failed` and `rejected`); `test_bus_attrs_on_nets`; `test_view_build_footprints` (after the commit, `View.build` maps the instance to the hypothesis cells and the raised cell to lines {4, 7, 9}).
- [ ] **Step 2: Failing loop tests** (`tests/test_re_loop.py`, skip without Odin III): `test_adder_end_to_end` (`add2.blif`, F2: one `adder` committed in round 1, `stop_reason = "fixed_point"`, `final_equiv.status = "equivalent"`); `test_constant_only_design` (`zero.blif`: round 1 fixed point, no hypotheses committed, `final_equiv` equivalent); `test_no_commit_option` (stops after round 1, nothing committed); `test_max_rounds` (`max_rounds = 1`: `stop_reason = "max_rounds"` when round 1 committed); `test_deterministic_overlay` (two runs: equal `overlay.to_json`); `test_f1_without_unmap` (a BLIF with one `.subckt adder` and `vtr.o3lib`: hard cell opaque, `notes["unmap"] == "unavailable"`, `final_equiv` `skipped:hard`); `test_transfer_four_adders` (`tests/data/re/add2x4.blif`, four 2-bit adders on disjoint inputs: one `cone_check` proof, three transfers, one spot check, all four committed, round `engines == {"cone_check": 2, "transfer": 3, "truth_table": 0}`, `transfer_failures == 0`); `test_reconvergent_no_transfer` (`tests/data/re/reconv.blif`, an adder-shaped cone and a twin whose two inputs are one net: no transfer between them); `test_features_none_no_transfer` (`features="none"`: four `cone_check` proofs, `notes["features"] == "off"`); `test_spot_check_failure_revokes` (`cone_match` monkeypatched to accept a non-matching member: the spot check differs, transfers revoked, `transfer_failures == 1`).
- [ ] **Step 3: Run** both modules. Expected: FAIL.
- [ ] **Step 4: Implement** spec 9 (loop steps 1 to 8, stopping rule, `fsm_detect_marks` when `$dff`/`$adff` present, `--keep-levels` via `write_json --odin3`; `build_features` once after `from_design` unless `features == "none"`, passed in every `RoundContext`; the prove step groups by `transfer_key` and applies spec 8.1, transfers and the spot check included) and 9.4 (`flatten; lower; write_blif` on a copy, `check_equiv` against the input BLIF; `match_unnamed` False for F2/F3).
- [ ] **Step 5: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 6: Commit** (`feat/l1-loop`), PR, merge.

### Task 12: Report, outputs and `loki re`

**Files:**
- Create: `loki/re/report.py`, `loki/re/main.py`, `tests/test_re_report.py`, `tests/test_re_cli.py`
- Modify: `loki/cli.py` (subcommand `re` delegating to `loki.re.main.main`)

**Interfaces:**
- Consumes: `RunResult` (Task 11).
- Produces: `build_report(res: RunResult, opts: ReOptions) -> dict[str, object]` (spec 11, every listed key, including `features` and per-round `engines`); `validate_report(obj: object) -> list[str]`; `write_markdown(report: Mapping[str, object]) -> str`; `write_outputs(res: RunResult, opts: ReOptions, out: Path) -> None` (`design.v` via `run_pass("write_verilog", ...)` on `res.final`, `overlay.json`, `report.json`, `report.md`, `timing.json`); `main(argv: Sequence[str] | None = None) -> int` (CLI of spec 13; exits 0, 1, 2, 3 as spec 13; `--odin3-root` defaults to `$ODIN3_ROOT`).

- [ ] **Step 1: Failing tests:** `test_report_keys_and_validates` (a hand-built `RunResult` with no Odin III objects needed for the keys: `validate_report == []`); `test_markdown_from_json_only` (`write_markdown(json.loads(dump_json(r)))` equals `write_markdown(r)`; it contains the pieces table header `| module | kind | confidence | proof | function |`); `test_cli_usage_exit_2`; `test_cli_unreadable_exit_3` (a malformed BLIF: exit 3, message starts `odin3:`; skip without Odin III); `test_cli_end_to_end_byte_identical` (`add2.blif` twice into two dirs: `design.v`, `overlay.json`, `report.json`, `report.md` byte-equal; `timing.json` exists; skip without Odin III); `test_design_v_has_confidence` (`(* ` and `loki_conf = "` on the instance line); `test_report_features_keys` (`features.enabled`, `wl`, `npn`, `transfers`, `transfer_failures`; `--features none` gives `enabled: false`); `test_cli_features_option` (`--features none` and `--features all` accepted, anything else exit 2).
- [ ] **Step 2: Run** the modules. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l1-cli`), PR, merge.

### Task 13: Scoring (`loki score`, `loki score-all`)

**Gate:** Task 1 and L0 Task 11 merged.

**Files:**
- Create: `loki/score/__init__.py`, `loki/score/gt.py`, `loki/score/match.py`, `loki/score/metrics.py`, `tests/test_score_gt.py`, `tests/test_score_match.py`, `tests/test_score_metrics.py`
- Modify: `loki/cli.py` (`score`, `score-all`)

**Interfaces:**
- Consumes: L0 floor files (`labels.csv`, `graph.json`, `words.json`), L1 `overlay.json` and `report.json`.
- Produces in `gt.py`: `@dataclass(frozen=True) GtInstance(gid: str, type: str, footprint: frozenset[str])`; `load_gt(floor_dir: Path) -> tuple[list[GtInstance], list[GtBus], dict[str, str], dict[str, str]]` (instances incl. the derived `counter`, `mux_tree`, `fsm` of spec 12.2; label buses of 12.3; role per node; `module_path` per node); `SCORED_TYPES: dict[str, frozenset[str]]` (kind to L0 types, spec 6.1 last column).
- Produces in `match.py`: `jaccard(a: frozenset[str], b: frozenset[str]) -> float`; `match_greedy(preds: Sequence[tuple[str, frozenset[str]]], gts: Sequence[tuple[str, frozenset[str]]], threshold: float) -> list[tuple[str, str, float]]` (spec 12.2 order and tie rules).
- Produces in `metrics.py`: `construct_scores(...) -> dict[str, dict[str, float | str]]` (per kind: precision, recall, f1, ap or `"n/a"`); `bus_scores(...)` (precision, recall, `order_exact`, `order_up_to_reversal` per `order_source`); `role_scores(...)`; `hierarchy_scores(gt_paths: Mapping[str, str], l1_clusters: Sequence[frozenset[str]], gt_constructs: Sequence[frozenset[str]]) -> dict[str, float | str]` (`HS_gt`, `HS_l1`, `hier_f`, `nmi_leaf`, spec 12.4); `score_run(re_dir: Path, floor_dir: Path, score_p: float) -> dict[str, object]`; `aggregate(scores: Sequence[Mapping[str, object]]) -> tuple[dict[str, object], str]` (`scores.json` object and `scores.md` text, with the per-kind reliability curves and `ece` of spec 12.5); `reliability(points: Sequence[tuple[float, bool]], bins: int = 10) -> dict[str, object]` (`bins`: `lo`, `hi`, `mean_p`, `rate`, `n` per bin; `ece`); `compare(with_scores: Sequence[Mapping[str, object]], without_scores: Sequence[Mapping[str, object]]) -> tuple[dict[str, object], str]` (`ablation.json` object and `ablation.md` text, spec 12.5; CLI `loki score-all --compare DIR`).

- [ ] **Step 1: Failing tests:** `test_gt_counter_rule` (words: `$dff` R, `$add` A with `const_ports ["B"]`, edges `R.Q -> A.A`, `A.Y -> M.A`, `M.Y -> R.D` with M a `$mux`: one `counter` instance with the union footprint); `test_gt_mux_tree_components`; `test_gt_label_buses` (nodes with `bus_name` `x`, bits 0..3 in one module path give one bus; size-1 groups dropped); `test_match_greedy_one_to_one` (two predictions on one ground truth: the higher Jaccard wins; ties by ids); `test_precision_recall_per_kind`; `test_kind_without_gt_is_na`; `test_bus_order_reversal` (a predicted bus in reverse bit order: `order_exact = 0`, `order_up_to_reversal = 1`); `test_hierarchy_identical_trees` (`hier_f == 1.0`, `nmi_leaf == 1.0`); `test_hierarchy_flat_gt` (`HS_gt == "n/a"`); `test_hierarchy_worked_example` (L0 modules `top/u1` = {a, b, c}, `top/u2` = {d, e}; L1 pieces {a, b}, {d, e, f}: `HS_gt = (3 * 0.8 + 2 * 0.8) / 5 = 0.8`, computed exactly); `test_ap_thresholds` (nine thresholds 0.1..0.9); `test_aggregate_markdown_table` (a floor-by-kind table, rows sorted); `test_reliability_bins_and_ece` (points `(0.05, False)`, `(0.15, True)`, `(0.95, True)`: three non-empty bins, hand-computed `ece`); `test_ablation_table` (two sets of `score.json` for the same designs: per-kind deltas of precision, recall, F1, AP; proof calls summed by engine; `transfer_failures` summed).
- [ ] **Step 2: Run** the three modules. Expected: FAIL.
- [ ] **Step 3: Implement** spec 12.2 to 12.4. `score_run` maps L1 cell labels (`overlay.json` uses L0 names when `.cname`s exist) directly to L0 node ids; PI/PO port nets map by name.
- [ ] **Step 4: Run** tests, ruff, mypy; then score `loki re` on the comparator micro's L0 F2 floor and paste the `score.json` summary into the PR. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l1-score`), PR, merge.

### Task 14: Calibration (`loki calibrate`)

**Gate:** Task 13 merged.

**Files:**
- Create: `loki/score/calibrate.py`, `tests/test_calibrate.py`
- Modify: `loki/cli.py` (`calibrate`)

**Interfaces:**
- Consumes: `run_re`, `load_gt`, `match_greedy`, the L0 manifest's `split` per design; Task 5b (`StructFeatures.cell_keys`, `family_of`, `wl_npn_bin`, `WEIGHT_GRID`, `CALIB_FOLDS`, `NODE_MIN_COUNT`); `reliability` (Task 13).
- Produces: `calibrate(dataset: Path, floor: str, split: str, odin3_root: Path, seed: int) -> dict[str, object]` (spec 6.3 file object with `schema`, `floor`, `dataset` (manifest sha256), `split`, `designs`, `priors`, `llr`, and from spec 6.7 `node_llr`, `weights`, `reliability`); `fold_of(design: str) -> int` (first byte of `sha256(design)` mod `CALIB_FOLDS`); `node_tally(sf: StructFeatures, gt: Sequence[GtInstance], kinds: Sequence[str]) -> NodeCounts` (pure; per kind and key `pos`/`neg` over level-0 logic cells, spec 6.7 item 1); `node_table(counts: NodeCounts) -> dict[str, dict[str, float]]` (Laplace form, keys under `NODE_MIN_COUNT` dropped); `fit_weights(rows: Sequence[tuple[float, dict[str, float], float, bool]]) -> dict[str, float]` (rows of prior, family sums, child sum, label from the out-of-fold scores; coordinate ascent of spec 6.7 item 5); `tally(hyps: Sequence[Hypothesis], gt: Sequence[GtInstance]) -> Counts` (pure); `to_calib(counts: Counts) -> dict[str, object]` (Laplace formulas of spec 6.3, exactly).

- [ ] **Step 1: Failing tests:** `test_prior_laplace` (`n = 8`, `tp = 2`: `p = 0.3`, stored `logit(0.3)`); `test_llr_laplace` (`pos 3/10`, `neg 1/20`, two bins: `ln((4/12)/(2/22))`); `test_unseen_bin_absent` (`Calib.feature_llr` gives 0 for it); `test_only_train_designs` (a fake manifest with train and test designs: only train ones run, via a stubbed `run_re`); `test_calib_file_deterministic` (dump twice equal); `test_roundtrip_load_calib` (`load_calib` on the written file gives the same numbers, `node_llr` and `weights` included); `test_node_llr_laplace_and_min_count` (`pos 3`, `neg 1` dropped under `NODE_MIN_COUNT`; `pos 6`, `neg 2` kept with the spec 6.7 formula); `test_node_backoff_keys` (a round-2 key below the minimum falls back to round 1); `test_fold_of_deterministic`; `test_cross_fit_no_leak` (the node table applied to a design is learned from the other fold only, via a stubbed `run_re`); `test_fit_weights_grid` (a planted `wl` family that duplicates the `struct` family: the two weights sum to at most 1.3; with independent planted families both stay 1.0; ties go to the larger weight); `test_reliability_in_calib_file`.
- [ ] **Step 2: Run** `python -m unittest tests.test_calibrate -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** Run with `DEFAULTS`, label each hypothesis by spec 12.2 (true when matched), tally per `"<detector>/<kind>"` and per `"<kind>/<feature>"` bin. Then spec 6.7 items 1 and 5: node tallies per design; for each fold, the node table and bin tables from the other fold give the hypotheses their `wl_npn` bin and out-of-fold family sums; `fit_weights` on those rows; the reliability curve of the out-of-fold `p`; finally node and bin tables refitted on all train designs.
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l1-calib`), PR, merge.

### Task 15: Wyrd step `loki-re` and `loki re-project`

**Files:**
- Create: `loki/re_step.py`, `loki/re_project.py`, `tests/test_re_step.py`
- Modify: `pyproject.toml` (`[project.entry-points."wyrd.steps"] loki-re = "loki.re_step:ReStep"`), `loki/cli.py` (`re-project`), `loki/re/main.py` (`--score-dataset`, `--score-design` write `score.json` and `metrics.json` after the run)

**Interfaces:**
- Consumes: Wyrd `StepSpec`, `RunSpec`, `Metric`, `Settings` (as L0 Task 8); L0 manifest.
- Produces: `class ReStep` (`name = "loki-re"`, `tools = ()`, `is_vpr = False`, `__init__(spec: StepSpec)` reading args `calib`, `dataset`, `odin3_root`; `command(run, step_dir, settings) -> tuple[list[str], dict[str, str]]` per spec 13; `collect(step_dir) -> list[Metric]` from `metrics.json` keys of spec 13); `write_re_project(dataset: Path, floors: Sequence[str], split: str, calib: Path, out: Path) -> Path`.

- [ ] **Step 1: Failing tests** (skip the module when `wyrd` is not importable): `test_command_argv` (design `ve_Prob035_count1to10__f2`: argv starts `[sys.executable, "-m", "loki.re.main"]`, `--floor f2`, `--calib <calib>/f2.json`, `--out <step_dir>/re`, `--score-design ve_Prob035_count1to10`); `test_floor_from_design_name` (`x__f1-k6` gives `f1-k6`; a name without `__` raises `ValueError`); `test_collect_metrics`; `test_collect_missing_empty`; `test_project_toml` (two designs, floors `f2`, split `test` only: parses with `tomllib`, designs named `<id>__f2`, `files` point at the floor BLIFs, one recipe `re`); `test_entry_point_loads` (when installed).
- [ ] **Step 2: Run** `python -m unittest tests.test_re_step -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l1-step`), PR, merge.

### Task 16: Acceptance (L1 exit test) and the VerilogEval baseline

**Gate:** Tasks 1 to 15 merged; L0 dataset for micros and VerilogEval built (L0 Tasks 11, 13).

**Files:**
- Create: `tests/test_acceptance_l1.py`, `docs/runbook-l1.md`, `docs/results-l1.md`, `calib/f2.json` (committed, from the train split)
- Modify: `README.md`, `CLAUDE.md` (L1 commands)

- [ ] **Step 1: Write the test** (`skipUnless(odin_available() and odin3_root() is not None and LOKI_DATASET set)`): over L0's `SUBSET` at F2 with `--calib none`, assert spec 15 items 1 to 7 exactly (item 7: `transfer_failures == 0` in every report) (names as listed there; item 6 checks every FF of the L0 node set whose `construct_type` is `$sdff` has an `ff_srst` hypothesis with `p_comp >= 0.5`).
- [ ] **Step 2: Run** it. Expected: PASS. A failing construct pin is not relaxed: find the cause with a failing unit test in the owning detector's task module, fix, report the finding in the PR.
- [ ] **Step 3: Calibrate** `loki calibrate --dataset dataset --floor f2 --split train --out calib/f2.json`; commit the file.
- [ ] **Step 4: Run the baseline:** `loki re-project --dataset dataset --floors f2 --split test --calib calib --out datasets/l1`, `wyrd run datasets/l1`, then `loki score-all` over the run directories into `docs/results-l1.md` (smallest designs first; run only when no other lane holds the heavy lock). Add the Gate-Breaker failure designs of spec 15 with what L1 recovered for each (kind, parameters, `p_comp`, proof). Then the ablation: the same test designs with `--features none` into a second directory, `loki score-all <runs> --compare <runs-none>`, and the `ablation.md` table (precision and recall with and without features, proof calls by engine, transfers) plus the test-split reliability curves into `docs/results-l1.md`.
- [ ] **Step 5: Run** ruff, mypy, the full suite. Expected: clean.
- [ ] **Step 6: Commit** (`feat/l1-acceptance`), PR, merge. This is the L1 exit.

### Task 17: F1 with `unmap` and the `hard` detector (gated)

**Gate:** the Odin III PR implementing `docs/specs/2026-10-21-unmap-design.md` merged, and `"unmap" in Odin3.passes()`; L0 F1 floors built. A missing pass stops the task.

**Files:**
- Create: `loki/re/detectors/hard.py`, `tests/test_re_hard.py`, `tests/test_re_unmap_facts.py`
- Modify: `loki/re/loop.py` (run `unmap` on the working copy for `f1-*`, `notes["unmap"] = "ok"`), `docs/specs/2026-10-21-l1-hypotheses-design.md` (7.2 with the merged pass's exact behaviour)

**Interfaces:**
- Produces: `HardDetector` (`name = "hard"`, `kinds = ("hard_add","hard_mul","hard_mem","hard_group")`), proposing in round 1 only; `HardDetector.read_unmap(working: Any, graph: FnGraph) -> list[UnmapRecord]` (`UnmapRecord(node_type: str, rule: str, note: str, cand: str, cells: frozenset[int], ports: dict[str, tuple[int, ...]])`, read with `Node.attr("unmap")`, `attr("unmap_note")`, `attr("unmap_cand")` and source lines), called by the loop and passed to the detector through `RoundContext` field `unmap: tuple[UnmapRecord, ...]` (default empty).

- [ ] **Step 1: Failing fact tests** (`tests/test_re_unmap_facts.py`, skip without the pass): on the L0 `f1-k6` BLIF of a micro with an adder and a multiply, after `read_techlib lib/vtr.o3lib; read_blif; unmap`: recovered cells are `$add`/`$sub`/`$mul` with string attribute `unmap`; their `sources()` lines are the `.subckt` lines; on a RAM micro the `$mem` cells carry `unmap_cand` `ram:<N>`; a second `unmap` changes nothing.
- [ ] **Step 2: Failing detector tests** (`tests/test_re_hard.py`, hand-built `UnmapRecord`s): `test_recovered_cells_confirmed_inf` (`hard_add` with `log_odds == inf`, status `confirmed`, evidence `("hard", "unmap", "chain")`); `test_ram_candidates_group` (four `$mem` records with `unmap_cand = "ram:0"` sharing clk, addr, we nets: one `hard_group`, `shared_ctrl = "all"`, children the four `hard_mem`); `test_declined_chain_open` (`unmap_note = "adder:carry-in"`: `hard_add` open with `declined_chain = "yes"`).
- [ ] **Step 3: Run** both. Expected: FAIL.
- [ ] **Step 4: Implement**; update spec 7.2 to the merged pass's facts.
- [ ] **Step 5: Run** the acceptance subset at `f1-k6`: every design exit 0, `final_equiv` `skipped:hard`, every recovered hard cell a committed `hard_*` piece. Expected: PASS.
- [ ] **Step 6: Commit** (`feat/l1-unmap`), PR, merge.

### Task 18: F3 gate netlists (gated)

**Gate:** the Odin III gate-mapping PRs merged (`write_blif --gates-as-names` works) and L0 Task 12 merged (`f3` floors exist).

**Files:**
- Modify: `loki/re/normalise.py` (`.v` input path of spec 3), `tests/test_re_fngraph.py`, `tests/test_acceptance_l1.py` (F3 over the subset)

- [ ] **Step 1: Failing tests:** `test_f3_blif_reads_as_sop` (an L0 `f3` BLIF: every logic cell is `lut` kind with a 1- or 2-input table of BUF, INV, NAND2, NOR2); `test_f3_verilog_normalised` (`netlist.v` with `read_techlib lib/cmos6.o3lib`: same `FnGraph` tables as from the BLIF); `test_f3_subset_runs` (the acceptance subset at `f3`: exit 0, `final_equiv` equivalent).
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** the `.v` branch of `load_level0` (temp BLIF in a `tempfile.TemporaryDirectory`).
- [ ] **Step 4: Run** tests, ruff, mypy, and calibrate `calib/f3.json` on the train split. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l1-f3`), PR, merge.

---

## Self-review

- Spec coverage (features A and B, spec 6.7, 8.1, 12.5, 18): role flags, colour refinement, quotient, NPN classes (T5a); adapter, `StructFeatures`, family weights, `cone_match` (T5b); bus classes and `wl_depth` (T6); NPN evidence in arith (T7) and mux (T8); proof transfer and spot check in the loop (T11); report keys and `--features` (T12); reliability and ablation (T13); node likelihoods, cross-fitting, weights (T14); acceptance item 7 and the ablation baseline (T16). Spec 18 questions: 1 (T5a no numpy, scale test), 2 (T5b, T11 reconvergence tests), 3 (T5a `roles.py`; L2 Task 9 delegates), 4 and 5 (T14), 6 (T5a fallback rule), 7 (T13 ablation counts), 8 (T5b graph.json test at F2 only).
- Spec coverage: normalisation and facts (T2, T17, T18); `FnGraph`, facts, simulation (T2, T3); claims and provers (T4); overlay, priors, evidence, competition, children (T5, T14); detectors: ff_pattern and bus (T6), arith (T7), mux (T8), seqfn and fsm (T9), role and unit (T10), hard (T17); round loop, commit, stopping, final check (T11); determinism (T5, T11, T12); outputs and CLI (T12); scoring incl. hierarchy metric (T13); calibration (T14); Wyrd step (T15); acceptance and baseline (T16); `words.json` amendment (T1). Spec open questions 1 (T1 gate note), 2 (T17 gate and fact tests), 3 (T9 `fsm_detect_marks`, T11), 4 (T11 `test_submod_only_for_const_claim`), 5 (T11 `test_bus_attrs_on_nets`), 6 (T13 constants).
- Type consistency: `Cell`, `FnGraph` (T2); `FnFacts`, `MuxFact`, `Support` (T3); `Claim`, `Verdict`, `prove` (T4); `Evidence`, `Hypothesis`, `KindSpec`, `KINDS`, `Overlay`, `Calib` (T5); `FeatureGraph`, `SignalConfig`, `NetRoles`, `NpnClass`, `WLConfig`, `WLResult`, `Partition`, `Quotient` (T5a); `StructFeatures`, `cone_match`, `transfer_key`, `family_of`, `wl_npn_bin` (T5b); `Candidate`, `Detector`, `RoundContext`, `View`, `Piece` (T6; `RoundContext` carries `features` from T6 and gains `fsm_marks` in T9 and `unmap` in T17, all defaulted); `SeqTable` (T9); `CommitResult`, `ReOptions`, `RunResult`, `run_re` (T11); `GtInstance`, `match_greedy`, `score_run` (T13) are each defined once and used by those names later.
- Proportion: tasks give signatures, test names and assertions; algorithm text only where the spec leaves the method open (chain search, cofactor tests, conflict components).
