# Loki III L1: the Bayesian hypothesis flow (design)

Status: decisions approved by Peter, 2026-10-21 (section 2, items 1 to 7, verbatim); everything
else is an agent default he may override. Open questions are section 17. This file is for his
review.

Amended 2026-10-21 (branch `docs/wl-npn`) with two features Peter approved that day: colour
refinement (1-WL, feature A) and functional node features (NPN classes, feature B), section 6.7,
used by the detectors (7.4 to 7.6), the provers (8.1), calibration (12.5) and scoring (12.5). Their
open questions are section 18.

## 1. Goal

L1 reverse-engineers one anonymous structural netlist (any L0 floor: F1 LUT + hard blocks, F2 LUT,
F3 gates) into hierarchical, word-level Verilog. Detectors propose **hypotheses** ("these 9 LUTs
are a 4-bit adder", "these 6 flip-flops are a modulo-10 counter"); each hypothesis carries
log-odds that priors (from L0 statistics), structural evidence and proofs (`cone_check`, or Loki III's
own exhaustive truth-table check) update. Confirmed pieces are committed with Odin III's `raise`
and `submod`, which moves the design up one level; the next round detects on the new level, until
a fixed point. There is no LLM step. L0's labels are the answer key for scoring.

Gate-Breaker (Faruque, Jamieson, Patooghy, Badawy, IPCCC 2025) is the baseline this work answers.
Its failure analysis (section V.C.3) names the hard cases: FSMs (`Prob089`, `Prob110_fsm2`,
`Prob119_fsm3`), counters and timers with self-feedback (`Prob035_count1to10`, `Prob037`,
`Prob040_count10`) and LFSRs (`Prob082_lfsr32`). Its future work (section VI) asks for bus naming
by clustering, datapath versus control classification, and partitioning. L1 targets exactly these:
the `seqfn` detector recovers counters (including modulo), shift registers and LFSRs from the exact
next-state table; the `fsm` detector recovers state registers and their transition tables; `bus`,
`role` and `unit` give buses, datapath/control and partitions.

**Done when** (acceptance, section 15): on the L0 micro subset at floor F2, `loki re` finishes
every design, the final design is formally equivalent to the input, two runs are byte-identical,
and the named constructs of section 15 are recovered; the VerilogEval test split at F2 has a
scored baseline.

## 2. Decisions (Peter, 2026-10-21, verbatim)

| # | Decision |
|---|---|
| 1 | Normalise any floor into the Odin III IR as functions (library gates by their fn, LUTs by truth table). |
| 2 | Unmap first where hard cells exist (probability 1); hard pieces regrouped (adder chain width, split multipliers, sliced RAMs) by unmap where exact, ambiguous groupings decided by L1 clustering; hard blocks are not equivalence-checked. |
| 3 | Detectors, each giving a likelihood: FF patterns (sync reset, enable as mux on D), buses (k isomorphic slices sharing a control), carry chains/adders, mux trees, comparators, counters (FF + incrementer feedback), FSMs (fsm_detect on the netlist), datapath vs control. |
| 4 | Priors from L0 statistics per floor; evidence multiplies odds (log-odds); cone_check proof drives a hypothesis to ~1 or kills it; hypotheses claiming the same cells compete (competition rule exact, section 6.5); a confirmed child raises its parent's prior (bits -> bus -> word op -> datapath unit). |
| 5 | Raise and submod move the design up; iterate to a fixed point; alternatives kept on the overlay (e-graphs later). |
| 6 | Output: hierarchical Verilog with a confidence attribute per piece + a report (JSON + markdown). |
| 7 | Scoring vs L0 labels: precision/recall per construct type and per floor, bus recovery, hierarchy similarity (metric defined in section 12.4). |
| - | No LLM step. Each detector is a plugin with a fixed interface (section 7.1). |

## 3. Inputs and normalisation (decision 1)

`loki re <netlist> --floor F` reads one netlist into a fresh Odin III design, **level 0**, which
is never edited afterwards (RE-ARCHITECTURE section 2).

| Input | Floor | Odin III script (`Design.run_script`) |
|---|---|---|
| `netlist.blif` (L0 output) | `f2` | `read_blif "<path>"` |
| `netlist.blif` | `f1-k6`, `f1-earch` | `read_techlib "<odin3>/lib/vtr.o3lib"; read_blif "<path>"` (the unmap spec's input situation S-2(b)); then `unmap` on the working level (section 9.1, gated) |
| `netlist.blif` | `f3` | `read_blif "<path>"` (L0 writes gates as `.names` covers of their fn, L0 Task 12) |
| `netlist.v` (gate-level) | `f3` | `read_techlib "<lib>"; read_verilog "<path>"; write_blif --gates-as-names "<tmp>"`, then `read_blif "<tmp>"` into a new design (gated on Odin III gate mapping) |

So every logic cell of level 0 is a `$sop` whose `COVER` is its function: a LUT by its truth
table, a library gate by its fn. Flip-flops are `$_DFF_P_`, `$_DFF_N_`, `$_FF_`; latches
`$_DLATCH_P_`, `$_DLATCH_N_`; hard cells keep their `lib/vtr.o3lib` type (`adder`, `multiply`,
`single_port_ram`, `dual_port_ram`). `<odin3>` is `$ODIN3_ROOT` (or `--odin3-root`). `--floor auto` takes the
floor from the path (`.../<floor>/netlist.blif`) and fails if it cannot.

### 3.1 Odin III facts L1 rests on

Probed on 2026-10-21 against the release build of `odin3` commit `00203c56` (v1.0.0, ABI 4); plan
Task 2 turns each into a test, and a changed fact stops the build.

1. `read_blif`: `.names` becomes `$sop`, granularity `bit`, params `WIDTH` (int) and `COVER` (text,
   one row `pattern value` per line); ports `A` (in, width `WIDTH`) and `Y` (out, 1). Pattern
   character `i` is input pin `A[i]` (as `plugins/python/re_round.py` reads it). `.latch ... re`
   gives `$_DFF_P_` with ports `C`, `D`, `Q` and param `INIT`.
2. `.cname n17` becomes `Node.name == "n17"`: the L0 node id of the cell.
3. `Node.sources()` of a level-0 cell is one `Source(file, line, ...)`: the BLIF path as given and
   the line of its `.names` / `.latch` / `.subckt`. Lines are unique per cell, so `line` maps any
   later object back to level-0 cells.
4. `raise`: the new cell's `sources()` is the union of the replaced cells' sources (probed: a
   2-bit adder of 3 `$sop` gave lines 4, 7, 9). It has no name; it drives the net bound to `Y[0]`,
   so `Module.net(name).driver().node()` finds it.
5. `submod -attr KEY`: one module per value `V`, instance named `V_i`; moved nodes get new IDs in
   the new module (RE-ARCHITECTURE gap 5); nested `submod` (a group holding an instance) works;
   `Design.copy` works after `submod`. Boundary nets stay in the parent module with their names.
6. `Node.set_attr` / `Module.set_attr` / `Net.set_attr` take strings; `write_verilog` writes them
   as `(* key = "value" *)` on instances, modules and net declarations, but **as a comment**
   (`// (* ... *)`) on a cell it prints as an `assign` (a raised `$add`). Hence every committed
   piece is wrapped in a submodule (section 9.3).
7. `cone_check` + `raise` work on a BLIF-read design after `Odin3.load_abc()`; the template may be
   any combinational word or bit cell type (`src/passes/cone_check/tmpl.c`: registers, tristates
   and processes refused). Binary cells take `A_WIDTH`, `B_WIDTH`, `Y_WIDTH` (and `A_SIGNED`,
   `B_SIGNED`); `$mux` takes `WIDTH`, ports `A`, `B`, `S`, `Y` (`Y = S ? B : A`). Odin III has no
   `$bmux`.
8. `fsm_detect` runs on a bit-level design without error and marks nothing: it only considers a
   `$dff`/`$adff` whose D is a `$mux`/`$pmux` tree (4.8 spec D-2, D-3).
9. INT attributes (such as `levelize`'s `odin3_level`) cannot be read through the binding
   (`odin3_attr_get_string` fails with `INVALID_ARG`): Loki computes levels itself.
10. Passes present (`Odin3.passes()`): `read_blif read_techlib read_arch read_verilog write_blif
    write_json write_verilog flatten lower fsm_detect levelize submod cone_check raise`. Not yet:
    `unmap` (Odin III project 3, spec `docs/specs/2026-10-21-unmap-design.md` on branch
    `feat/unmap-spec`, commit `bc9e5799`, not merged), `write_blif --gates-as-names` (gate mapping).

### 3.2 ABI gaps and how L1 lives with them (RE-ARCHITECTURE section 5)

| Gap | L1's answer |
|---|---|
| 1 no attribute remove | marks use a fresh key per hypothesis (`lk<k>`); proofs run on a scratch copy |
| 2 one `cone_check` result per module | proofs run one at a time; the result is read immediately |
| 3 `cone_check` is combinational only | sequential claims are checked as next-state functions (Q nets in, D nets out); FSMs get no proof |
| 4 one cffi call per field | the level-0 `FnGraph` is read once; VTR-size inputs later through `write_json` (section 16) |
| 5 IDs are module-local | footprints are level-0 cells (by BLIF line, fact 3); instances carry `loki_hid` |
| 7 no cell creation | a claim with a constant operand (`Q + 1`, `A == 13`) is committed by `submod` only, with `loki_fn` |
| 8 `cone_cex` is text | `loki.re.provers.parse_cex` parses `PORT[i]=v,...` into the evidence record |
| 9 one ABC engine per process | proofs are serial; `MAX_PROOFS` per round bounds the time |
| new: no net rename, scalar submod ports | buses appear as `loki_bus` net attributes and in the report, not as vector ports |

## 4. The level-0 view (`loki.re.fngraph`)

`FnGraph` is Loki's read-only Python view of level 0, built once by `from_design(design)`:

- `Cell(id, name, kind, type, ins, outs, table, width, clock, line, params)`: `id` the level-0
  node ID (the **cell id** used everywhere in L1), `name` the `.cname` (L0 node id, or `""`),
  `kind` in `lut ff latch const hard`, `ins` input net IDs in pin order (`$sop`: `A[0..]`; FF:
  `(D,)`), `outs` output net IDs, `table` (an `int`, bit `x` is the output for input pattern `x`,
  input `i` = bit `i` of `x`) for `lut` and `const`, `clock` the `C`/`E` net of FFs and latches,
  `line` the BLIF line.
- `cover_to_table(cover: str, width: int) -> int`: rows with output `1` are the on-set; rows with
  output `0` are the off-set (the table is the complement of their union); `-` is any value; an
  empty cover is constant 0; width 0 with row `1` is constant 1.
- Nets: `driver: dict[int, int]` (net to cell id), `readers: dict[int, tuple[(cell id, pin)]]`,
  `names: dict[int, str]`, `pis`, `pos` (net IDs in port order), `line_to_cell`.
- **Sources** of combinational logic: PI nets, FF and latch outputs, hard-cell outputs, constant
  outputs, and (in later rounds) the outputs of committed opaque pieces.
- `support(net) -> frozenset[int]`: the source nets in the transitive fan-in, computed iteratively
  with a cache; a combinational loop is cut at its lowest-ID cell (counted). Supports larger than
  `SUPPORT_MAX = 40` are stored as `None` (too wide for chain detection).

`loki.re.sim.simulate(graph, cells, values: dict[int, int], n) -> dict[int, int]` evaluates cells
bit-parallel: every net value is an `n`-bit Python int (one bit per input vector). `cone(graph,
inputs, outputs) -> (cells, side_inputs)` walks back from `outputs` and stops at `inputs` and at
sources; nets it stops at that are not in `inputs` are the side inputs.

`loki.re.fnfacts.facts(table, width) -> FnFacts`: `support` (inputs the function depends on),
`ones`, `parity` (`+1` XOR, `-1` XNOR, `0`), `and_like` (one on-minterm over the support),
`or_like`, `mux` (the smallest select set `T`, `|T| <= 3`, such that all `2^|T|` cofactors are
single positive literals of distinct non-`T` inputs; `None` otherwise), `maj3` (3-input majority
under any input/output negation). `npn_sig(table, width) -> tuple`: a signature invariant under
input permutation and output negation: `(len(support), min(ones, 2^w - ones), sorted per-input
(|f0|, |f1|) cofactor-ones pairs with each pair sorted)`. It is a hash for "isomorphic slices",
not a canonical form. The exact NPN class is `loki.features.npn` (6.7, feature B); with the
structural features on it replaces `npn_sig` where slices are grouped (7.4), and `npn_sig` stays
for `--features none`.

## 5. The overlay data model (`loki.re.overlay`)

```python
@dataclass
class Evidence:
    round: int
    source: str        # "prior", "feature", "child", "cone_check", "truth_table", "sim", "hard", "competition", "transfer"
    name: str          # feature or detector name
    value: str         # bin label, verdict, or child id
    llr: float         # natural-log likelihood ratio added; 0.0 for records that only document

@dataclass
class Hypothesis:
    id: str                          # "h<k>", k from 1 in creation order
    kind: str                        # a key of KINDS (section 6.1)
    detector: str
    round: int                       # round created
    cells: frozenset[int]            # footprint: level-0 cell ids
    nets: dict[str, tuple[int, ...]] # role -> level-0 net ids, LSB first ("A", "B", "Y", "S", "Q", "D", ...)
    params: dict[str, int | str]     # width, op, modulus, ...
    claim: Claim | None              # functional claim for provers (section 8)
    children: tuple[str, ...]
    parents: tuple[str, ...]
    features: dict[str, str]         # latest bin per feature
    prior_log_odds: float
    log_odds: float                  # prior + evidence; +inf / -inf allowed
    p_comp: float                    # probability after competition (6.5)
    evidence: list[Evidence]
    status: str                      # open confirmed refuted rejected committed alternative
    proof: dict[str, str] | None     # {"engine", "verdict", "template", "cex", "from"}; engine "transfer" (8.1) names its source in "from"
    conflicts: tuple[str, ...]
    commit: dict[str, str] | None    # {"round", "module", "instance", "form"}
```

The **merge key** of a hypothesis is `(kind, cells, canonical JSON of params)`. A detector
proposing an existing key updates that hypothesis (new feature bins replace old ones, an evidence
record is added) instead of creating one. Status transitions:

```
open -> confirmed     proof equivalent, or hard (unmap exact)
open -> refuted       proof or simulation differs          (log_odds = -inf, never revived)
open -> rejected      p_comp < REJECT_P, or conflicts a committed hypothesis (kept, may reopen only by new evidence)
open|confirmed -> committed      selected in a round's commit (section 9.3)
confirmed -> alternative         an equivalent competitor was committed (section 6.5)
```

`overlay.json` (schema 1) lists every hypothesis, every status, sorted by id; nothing is deleted
(decision 5: alternatives kept on the overlay). Cell ids are written as the L0 node names when
the input has `.cname`s, else `c<id>`; net ids as their BLIF names.

## 6. The Bayesian model (decision 4)

### 6.1 Kinds

| Kind | Level | Excl. | Commit | Detector | Claim op (prover) | Scored against L0 (12.2) |
|---|---|---|---|---|---|---|
| `ff_en` | bit | no | no | ff_pattern | none (fn fact) | ff node, construct in `$dffe $adffe $sdffe $sdffce` |
| `ff_srst` | bit | no | no | ff_pattern | none (fn fact) | ff node, construct in `$sdff $sdffe $sdffce` |
| `register` | word | yes | submod | ff_pattern | none | storage word, width >= 2 |
| `bus` | bus | no | attrs | bus | none | label buses (12.3) |
| `adder` | word | yes | raise+submod | arith | `add` (cone_check `$add`) | `$add` |
| `subtractor` | word | yes | raise+submod | arith | `sub` (cone_check `$sub`) | `$sub` |
| `adder_cin` | word | yes | submod | arith | `add_cin` (truth table) | `$add` |
| `comparator` | word | yes | raise+submod | arith | `eq ne lt le gt ge` (cone_check, same type) | same type |
| `eq_const` | word | yes | submod | arith | `eq_const` (truth table) | `$eq $ne` |
| `mux_bit` | bit | no | no | mux | `muxn` (truth table) | `$mux $pmux` |
| `mux` | word | yes | raise+submod (2:1), submod (N:1) | mux | `mux2` (cone_check `$mux`), `muxn` | `$mux $pmux` |
| `mux_tree` | word | yes | submod | mux | `muxn` (truth table) | mux-tree components |
| `counter` | word | yes | submod | seqfn | `counter` (truth table; cone_check `$add` B=en form) | counter rule (12.2) |
| `shift_reg` | word | yes | submod | seqfn | `shift` (truth table) | not scored |
| `lfsr` | word | yes | submod | seqfn | `lfsr` (truth table) | not scored |
| `fsm` | word | yes | submod | fsm | none | storage word with `fsm` flag |
| `hard_add` `hard_mul` `hard_mem` | word | yes | submod | hard | none (p = 1) | F1 hard nodes by type |
| `hard_group` | word | yes | submod | hard | none | not scored |
| `datapath_unit` `control_unit` | unit | yes | submod | unit | none | hierarchy metric only |
| `role` | bit | no | attrs | role | none | cell roles (12.3) |

"Excl." means the hypothesis claims its cells exclusively (section 6.5). "Commit" is how a
committed hypothesis is materialised (section 9.3); `no` kinds are evidence and report only;
`attrs` kinds become attributes. Levels order the lattice bit < bus < word < unit.

### 6.2 Log-odds

Natural logs throughout. `L(h) = prior_log_odds(h) + sum(evidence llr)`, `p(h) = 1 / (1 + e^-L)`.
Feature LLRs are weighted by family (6.4, 6.7 item 5): the feature part of the sum is
`sum_f w_f * (sum of the feature LLRs of family f)`, with `w_f` from the calibration file (1.0
without one); `STRUCT_CAP` applies to the weighted feature sum plus the child sum.
Constants (agent defaults, in `loki/re/bayes.py`):

| Name | Value | Meaning |
|---|---|---|
| `PROOF_LO` | 9.21 (`ln 9999`) | proof `equivalent`: `L := max(L, PROOF_LO)`, status `confirmed` |
| refute | `-inf` | proof or simulation `differs`: status `refuted` |
| `SIM_LLR` | 4.61 (`ln 100`) | sampled check (`SAMPLE_N = 4096` vectors) found no counterexample |
| `STRUCT_CAP` | 6.91 (`ln 1000`) | cap on the absolute sum of `feature` and `child` LLRs (naive-Bayes double counting) |
| `CHILD_LLR` | 1.10 (`ln 3`) per confirmed child, total capped at 3.30 | 6.6 |
| `CHILD_NEG` | -2.30 (`ln 0.1`) per refuted child | 6.6 |
| `COMMIT_P` | 0.9 | `p_comp` needed to commit |
| `PROVE_P` | 0.2 | `p_comp` needed to spend a proof |
| `REJECT_P` | 0.01 | below it, status `rejected` |
| `MAX_PROOFS` | 200 per round | proofs ordered by `p_comp` desc, then id |

### 6.3 Priors from L0 statistics per floor

`loki calibrate` (section 12.5) runs the flow on the L0 **train** split of one floor and writes
`calib/<floor>.json`:

- `priors["<detector>/<kind>"] = {"n", "tp", "log_odds"}`: `n` candidates proposed, `tp` of them
  matching an L0 construct (12.2); prior `p = (tp + 1) / (n + 2)`, stored as its logit.
- `llr["<kind>/<feature>"]["<bin>"] = {"pos", "neg", "llr"}`: `llr = ln(((pos + 1) / (POS + B)) /
  ((neg + 1) / (NEG + B)))`, `POS`/`NEG` the totals of true/false candidates of that kind, `B` the
  number of bins seen.
- `node_llr`, `weights` and `reliability` (6.7 items 1 and 5): the node-level table per kind, the
  weight per feature family, and the reliability curve of the out-of-fold predictions.

With no calibration file (`--calib none`), `loki/re/bayes.py` `DEFAULTS` applies: prior log-odds
0 for every kind and the feature table of section 7 (each detector lists its default LLRs).
Hypotheses whose kinds have no feature evidence then move only by proofs, simulation and children.
Without a calibration file there is no node table (every `wl_npn` bin is `unseen`, LLR 0) and every
family weight is 1.0.

### 6.4 Evidence

Detectors report **features as bin labels** (strings), never LLRs; the framework turns a feature
into an LLR through the calibration table (`llr` of that bin, 0 for an unseen bin). Proofs and
simulation add the fixed records of 6.2. All evidence is an `Evidence` record, so the report can
explain every number. Each feature belongs to one family (`family_of` in `loki/re/bayes.py`):
`npn_*` to `npn`, `wl_*` to `wl`, features read from L2 outputs (partitions, graphlet orbits) to
`l2`, every other feature to `struct`.

### 6.5 Competition (exact rule)

- Two hypotheses **conflict** when both kinds are exclusive, their `cells` intersect, and neither
  `cells` is a strict subset of the other. Equal footprints conflict. A strict subset is
  **nesting**: the framework links the smaller as a child of the larger (no conflict).
- The **conflict graph** has an edge per conflicting pair among hypotheses with status `open` or
  `confirmed`. For each connected component `C`, with `o_j = e^{L_j}`:
  `p_comp(h) = o_h / (1 + sum_{j in C} o_j)` (computed with log-sum-exp; `+inf` members share
  probability 1 equally among themselves and the rest get 0). The `1` is "none of these". A
  hypothesis without conflicts has `p_comp = p`.
- **Equivalent alternatives:** when two conflicting hypotheses with equal `cells` are both
  `confirmed`, they are two true forms of the same logic, not rivals: they count as one member of
  `C` (its `o` the larger), and at commit the one with the higher `KIND_RANK` wins, the other
  becomes `alternative` (`KIND_RANK`, highest first: `counter lfsr shift_reg fsm adder subtractor
  adder_cin comparator eq_const mux_tree mux register hard_group`).
- A hypothesis that conflicts a `committed` one is `rejected` with an `Evidence(source=
  "competition", value="<committed id>")`, unless the committed one nests in it.
- `rejected` hypotheses with `p < REJECT_P` stay rejected; others re-enter the next round's
  competition if new evidence raises `L`.

### 6.6 Children raise parents

Parent links come from detectors (a `mux` word lists its `mux_bit` slices; a `register` its
`ff_en`/`ff_srst`; a unit its pieces; a `bus` its slices) and from nesting (6.5). On every
re-score: each `confirmed` or `committed` child adds `CHILD_LLR` to the parent (total capped),
each `refuted` child adds `CHILD_NEG`. This is "a confirmed child raises its parent's prior" along
bits -> bus -> word op -> datapath unit.

### 6.7 Structural and functional features (A: colour refinement, B: NPN classes)

Approved by Peter, 2026-10-21. Package `loki.features` (plan Task 5a): standard library only
(`hashlib`; no numpy, so L1's no-new-runtime-dependency rule holds; open question 18.1), and
independent of `loki.re` and `loki.analysis`, so L2 runs the same code on `graph.json` (L2 spec
4.1). L1 computes the features once per run on level 0 (`loki.re.structural`, plan Task 5b) and
hands them to detectors as `RoundContext.features` (7.1); later rounds reuse the level-0 values for
level-0 cells, and committed pieces keep their existing keys.

**Feature graph.** `FeatureGraph` has one node per level-0 cell plus PI and PO pseudo-nodes (as in
L0's `graph.json`; ids are the cell labels of section 5 and `pi:<net>`, `po:<net>`), each with
`kind` (`pi po lut ff latch const hard gate`), `type`, `width` and `table` (the `Cell.table`
convention of section 4; -1 when none), and directed edges driver to sink carrying the sink pin
name of L0 spec 6.4 (`I<k>` for LUT input `k`, `D`, `CLK`, `EN`, `I` on a PO, hard formal names
with index) and the net id. L1 builds it from `FnGraph` (`structural.feature_graph`);
`loki.features.graph.from_graph_json` builds it from a `graph.json` object (standard library), and
L2's `graphio.to_feature_graph` gives the same from its `Graph`. On F1 and F2 the `FnGraph` and
`graph.json` routes give the same nodes, tables and edges, up to the PI/PO node names (a test pins
it on an L0 micro). F3 differs until L0 writes gate tables (open question 18.8).

**Role flags.** `loki.features.roles.classify_nets` implements L2 spec 8.1's rules once (per net:
`const`, `clock`, `reset`, `enable` or `signal`; `SignalConfig(min_fanout=16, dominance=0.8)`) and
the per-node flags of L2 spec 8.2 (`clock_domain`, `has_reset`, `const_inputs`, `enable`); L2's
`classify_signals` delegates to it (open question 18.3). Edges of non-`signal` nets are removed from
the refinement graph and kept in the start colours, as L2 removes them from the graphlet counting
graph.

**A. Colour refinement (1-WL), `loki.features.wl`.** Deterministic directed colour refinement:

- Start colour `c_0(v) = H(start_label(v))`. `start_label` joins: `kind`; `type`; for a LUT either
  its width and exact table (variant `table`) or the NPN class key of B (variant `npn`); the role
  flags `clocked` (`clock_domain > 0`), `has_reset`, `enable`; and the constant inputs (variant
  `table`: the sorted `<pin>=<value>` pairs; variant `npn`: their count, capped at 3).
- Round `r + 1`: `c_{r+1}(v) = H(c_r(v), sorted multiset of (pin label, c_r(u)) over in-edges
  u -> v, sorted multiset of (pin label, c_r(w)) over out-edges v -> w)`. Direction `in` drops the
  out part, `out` the in part, `both` keeps both. The pin label is the sink pin name where pins are
  ordered (LUT `I<k>` in variant `table`, `D`, `CLK`, `EN`, hard pins); LUT inputs in variant `npn`
  all get the label `I`, because the NPN class is invariant under input permutation and pin
  positions mean nothing there.
- `H` = SHA-256 of a canonical UTF-8 encoding (fields joined by `|`, multisets as sorted lists),
  first 16 hex digits. Colours are strings, identical across runs, machines and designs; the
  cross-design keys of item 1 need this, which per-graph renumbering would not give. No soundness
  argument rests on `H` being collision-free (proof transfer checks structure, 8.1).
- Rounds: up to `WL_ROUNDS = 4` (h), or until stable. Because `c_r` is hashed into `c_{r+1}`,
  colours only split, so a round that does not raise the number of colours leaves the partition
  unchanged: that round is `stable_round`. Output: per node its colour in every round, per round
  the colour classes (colour to sorted node indices), and `stable_round` (or `None`).
- Variants L1 computes: `table/in` (the proof-transfer filter, item 4), `npn/in` (bus slices, item
  3), `npn/both` (calibration keys, item 1). L2 exports `npn/both`, and `table/both` on request.
- **Quotient.** `stable_partition` computes the coarsest equitable partition that refines the start
  colours (pin-labelled edges, both directions) by partition refinement with the "process the
  smaller half" rule (Berkholz, Bonsma and Grohe, "Tight lower and upper bounds for the complexity
  of canonical colour refinement", ESA 2013 and Theory of Computing Systems 2017), O((n + m) log n)
  in total; classes are numbered by their lowest node index (canonical within one graph, not across
  graphs). `quotient` returns per class its size and start label, and per (class C, class D, pin
  label) the number of such edges each node of D receives from C (well defined because the
  partition is equitable). A test checks that `refine` run to stability and `stable_partition` give
  the same partition on random small graphs.
- **Cost.** `refine` is O((n + m) log n) per round (one sort of each node's multisets, one hash per
  node), memory O(n h + m). Budgets, pure Python, estimates to be measured (plan Task 5a on a
  100k-node, 300k-edge synthetic netlist; L2 plan Task 15 on the L2 scale fixture): one variant,
  4 rounds, at 100k nodes 30 s and 1 GB; `stable_partition` at 100k nodes 60 s and 1 GB; at 820k
  nodes eight times these. A miss is reported with its numbers, not hidden (open question 18.1).

**B. Functional node features, `loki.features.npn`.** The NPN class (input negation, input
permutation, output negation) of each LUT function, and of each gate, which level 0 holds as a
`$sop` table (decision 1):

- The table is first shrunk to its support (inputs it does not depend on are removed), so a LUT6
  used as an AND2 is in the AND2 class. The class key is `"<support size>:<canonical table hex>"`.
- **Method: an exact canonical form for every k <= 6.** The canonical form is the smallest table in
  `N ∩ orbit(f)`, where `orbit(f)` is the NPN orbit of `f` and `N` the set of *normalised* tables:
  at most `2^(k-1)` ones; for every input, the 1-cofactor has at least as many ones as the
  0-cofactor; inputs ordered by non-decreasing 1-cofactor ones count. `N` is defined by properties
  of the table alone, so `N ∩ orbit(f)` is the same set for every member of the orbit and its
  minimum is an exact canonical form. Enumeration: the allowed output phases (both only when the
  ones count is exactly `2^(k-1)`); for each, the allowed input phases (both only for a tied input);
  for each, every input order consistent with the sort, permuting only within tie groups. Inputs
  that are symmetric in the phase-assigned table (swapping two of them leaves it unchanged) are
  kept in one order, since their permutations give the same table. For k <= 4 the plain
  enumeration of all `k! 2^k 2` transforms (at most 768) is the test oracle.
- **Cost.** A table whose inputs have distinct cofactor counts needs 1 or 2 transforms. The worst
  case (k = 6, all inputs tied, no symmetry, both output phases) is `2 * 2^6 * 6! = 92,160`
  transforms, estimated at 0.1 to 0.5 s in CPython (each transform a few big-integer operations,
  stepped in Gray-code order). Results are cached by `(width, table)` and a netlist has few
  distinct tables, so a design pays once per distinct table. `NPN_ENUM_MAX = 100000` lies above the
  worst case, so every class is exact. If plan Task 5a's budget test fails, k = 6 falls back to a
  documented semi-canonical form (the first normalised table found instead of the smallest:
  deterministic, but two NPN-equivalent tables with ties may get different keys), the class is
  marked `exact = false` and the report says so (open question 18.6).
- Named classes `NAMED`, computed from their tables at import: `const`, `buf`, `and2`, `xor2`,
  `and3`, `xor3`, `maj3`, `mux2` (3 inputs), `and4`, `xor4`, `mux4` (6 inputs); every other class
  is `other` in feature bins.

**How the Bayesian flow uses A and B.**

1. **Learned likelihoods.** `loki calibrate` (12.5) learns, per kind `K`, a node-level table over
   keys `"<d>:<c_d(v)>"` (the `npn/both` colour at round `d`; its start label carries the NPN class
   of B): `pos` counts level-0 logic cells inside the footprint of an L0 instance of `K`'s scored
   types (12.2), `neg` the other logic cells; `node_llr[K][key] = ln(((pos + 1) / (POS + B_d)) /
   ((neg + 1) / (NEG + B_d)))`, the Laplace form of 6.3 with `B_d` the number of keys at round
   `d`, for example `ln(P(key | adder cell) / P(key | not adder cell))`. Keys with `pos + neg <
   NODE_MIN_COUNT = 5` are dropped. Lookup backs off from `d = CALIB_WL_DEPTH = 2` to 1 and 0; no
   key with enough counts gives `unseen`. A hypothesis of kind `K` gets the feature `wl_npn`, the
   bin of the mean node LLR over its logic cells: `--` (< -2), `-` (-2 to -0.5), `0` (-0.5 to
   0.5), `+` (0.5 to 2), `++` (> 2), `unseen`. The bin table of 6.3 then learns the
   hypothesis-level LLR of each bin. This extends the default LLR table (section 17 item 6): with
   `--calib none` every `wl_npn` bin is `unseen` and adds 0, so the defaults are unchanged.
2. **NPN evidence before proofs.** Cut functions in the classes `xor2`, `xor3`, `maj3`, `mux2`,
   `mux4` are cheap, strong evidence: `arith` reads the class of each sum bit over its cut and of
   each carry net (7.5: `npn_sum`, `npn_carry`; subtractor bits fall in the same classes because
   NPN absorbs the negations) and counts `xor2` cells under a comparator (`npn_xor2`); `mux` reads
   the class of each `mux_bit` cell (7.6: `npn_class`). Proofs are spent in `p_comp` order and
   only above `PROVE_P` (9.2 step 4), so chains whose bits are not adder-shaped drop below it
   without a SAT call. The ablation (12.5) reports the proof calls with and without.
3. **Bus and slice priors.** `k` slices in one colour class (`npn/in`, round 0) that share a
   control are the `bus` detector's isomorphic slices, found in one pass over the classes (7.4)
   instead of pairwise tests. The bus's log-odds rise with the class evidence through features:
   `k` (as before), `ctrl_fanout_exact` (shared control) and `wl_depth` (the deepest round at which
   all slices still share one colour). Calibration learns their LLRs, which in log-odds form is a
   prior that rises with class size and shared-control evidence. A word `mux` built on a bus
   copies its `wl_depth` bin.
4. **Proof transfer across a colour class.** One proof serves every member of a class whose cone
   matches the proved one; section 8.1 states the rule and exactly when it is sound.
5. **Correlated evidence.** WL colours, graphlet orbits (when L2 outputs are read) and NPN classes
   describe overlapping structure, while odds updates assume independent evidence. Calibration
   fits one weight `w_f` in `[0, 1]` per feature family (6.4: `struct`, `wl`, `npn`, `l2`) on the
   train split by 2-fold cross-fitting over designs (`CALIB_FOLDS = 2`, fold = first byte of
   `sha256(design id)` mod 2): the tables learned on one fold score the hypotheses of the other,
   then coordinate ascent over `WEIGHT_GRID` = 0.0, 0.1, ..., 1.0 (three sweeps, families in name
   order, ties to the larger weight) maximises the Bernoulli log-likelihood of the match labels
   under `sigmoid(prior + sum_f w_f s_f + child)`. The final tables are refitted on the whole train
   split. The calibration file stores `weights` and `reliability` (10 equal-width bins of the
   out-of-fold `p`: mean predicted, observed match rate, count; and the expected calibration error
   `ece`); `loki score-all` writes the same curves for the test split (12.5).
6. **Ablation.** `loki re --features none` turns A and B off (no structural features, no
   transfers, bus grouping by `npn_sig`); `loki score-all --compare` reports precision and recall
   with and without them (12.5).

Constants (agent defaults; `loki/features/__init__.py` for the first and last, `loki/re/bayes.py`
for the rest): `WL_ROUNDS = 4`, `TRANSFER_ROUND = 2`, `CALIB_WL_DEPTH = 2`, `NODE_MIN_COUNT = 5`,
`CALIB_FOLDS = 2`, `WEIGHT_GRID = (0.0, 0.1, ..., 1.0)`, `NPN_ENUM_MAX = 100000`.

## 7. Detectors

### 7.1 The plugin interface (`loki.re.detectors`)

```python
@dataclass(frozen=True)
class Candidate:
    kind: str
    cells: frozenset[int]
    nets: Mapping[str, tuple[int, ...]]
    params: Mapping[str, int | str]
    features: Mapping[str, str]          # feature name -> bin label
    claim: Claim | None = None
    children: tuple[str, ...] = ()       # existing hypothesis ids

class Detector(Protocol):
    name: str
    kinds: tuple[str, ...]
    def propose(self, ctx: RoundContext) -> Iterable[Candidate]: ...

@dataclass(frozen=True)
class RoundContext:
    round: int
    floor: str
    graph: FnGraph            # level 0, read only
    view: View                # the current level (section 9.2)
    overlay: OverlayReader    # read-only access: by_kind, get, children_of, committed
    rng: Callable[[str], random.Random]
    calib: Calib
    fsm_marks: Mapping[frozenset[int], str] = {}   # fsm_detect results of this level (7.8)
    unmap: tuple[UnmapRecord, ...] = ()           # unmap attributes read on F1 (7.2)
    features: StructFeatures | None = None         # level-0 structural features (6.7); None with --features none
```

Rules: `propose` is pure with respect to its inputs (no Odin III calls; proofs are the
framework's), yields candidates in a deterministic order (sorted by `min(cells)`, kind, then the
canonical params JSON), and every candidate kind is in its `kinds`. Built-in detectors run in
`DETECTOR_ORDER = ("hard", "ff_pattern", "mux", "arith", "seqfn", "fsm", "bus", "unit", "role")`;
plugins come from the entry-point group `loki.detectors` (value: a class with a no-argument
constructor), run after the built-ins in name order, and are selected with `--detectors`. A new
kind is registered by adding a `KindSpec(level, exclusive, commit, rank)` to `KINDS` through
`register_kind`, called at plugin import.

Default feature LLRs (used without calibration) are given below per detector; every other bin is 0.

### 7.2 `hard` (decision 2; gated on Odin III `unmap`, plan Task 17)

On F1 the working level is the output of `unmap` (unmap spec, `bc9e5799`; section 9.1). Its
contract as L1 uses it: hard cells of `lib/vtr.o3lib` become `$add`/`$sub` (carry chains, C-n),
`$mul` (M-n, split multipliers regrouped by their exact pattern) and `$mem` (R-n); each new cell
has one DERIVED provenance record whose parents are the replaced cells' IMPORTED records (P-1), so
`sources()` gives their BLIF lines; it carries the string attribute `unmap` = the rule (P-2).
Cells `unmap` declines carry `unmap_note` = `<kind>:<reason>` (P-3); ambiguous candidate sets
(RAM width or replica slices with different origin, R-6, R-7: always the case for a BLIF input,
whose `.subckt` lines are separate records) carry `unmap_cand` = `<kind>:<N>` on every member.

- Every node with an `unmap` attribute gives `hard_add` (`$add`, `$sub`), `hard_mul` or
  `hard_mem`, status `confirmed`, log-odds `+inf` (probability 1), evidence `("hard", "unmap",
  <rule>)`, cells = the hard cells it came from (by source lines). Hard blocks are not
  equivalence-checked.
- **Ambiguous groupings, decided by L1 clustering:** the nodes sharing one `unmap_cand` value
  give one `hard_group` candidate (params `kind`, `members`, the summed `WIDTH`, slices in node-ID
  order); feature `shared_ctrl` (`all`: every `clk`, `addr`, `we` net shared, +4.61; `addr_only`
  +1.10); the bus detector's `k` bins apply too. Its children are the members' `hard_mem`.
- A declined `adder` chain (`unmap_note` `adder:<reason>`, such as a real carry-in, unmap open
  question 2) is followed `cout` to `cin` and gives a `hard_add` candidate with status `open`
  and feature `declined_chain = yes` (+4.61), not probability 1.
- Before `unmap` exists on Odin III `main`, F1 runs with hard cells as opaque sources and no
  `hard` hypotheses; the report says `unmap: unavailable`. `unmap` is never run with
  `--no-regroup`.

### 7.3 `ff_pattern` (FF patterns: sync reset, enable as mux on D)

Per FF (`$_DFF_P_`, `$_DFF_N_`, `$_FF_`): the **D cone** is the driver cell of D, extended
backwards through cells whose only reader is this cone, to depth 3 and at most 12 cut inputs.
Exact tests over its function `f` (enumeration, at most 4096 patterns):

- **enable:** some cut input `e` and value `v` give `f|e=v == Q` (the FF's own output) while
  `f|e=!v` is not `Q`: hypothesis `ff_en`, params `{"en": <net>, "active": 1 - v}`, feature
  `en_fn_exact = yes` (+4.61).
- **sync reset:** some cut input `r` (not `Q`) and value `v` give `f|r=v` constant `c` while
  `f|r=!v` is not constant: `ff_srst`, params `{"rst", "active": v, "value": c}`; feature
  `rst_fanout` = number of FFs with an `ff_srst` on the same net and polarity, binned `1` (-1.10),
  `2-3` (+1.10), `4-7` (+2.20), `8+` (+3.00). A reset over an enable is found by testing reset first.
- **register:** FFs with the same clock net and the same `(en, active)` and `(rst, active)`
  (at least one present), or the same clock and all D cones reading one committed piece or one
  bus: one `register` per group of `>= 2`, slices ordered as their D-side bus (else ascending
  output net id, `order_source = "net_id"`). Children: its `ff_en`/`ff_srst`. Features
  `shared_ctrl` (`en`, `rst`, `both`: +1.39) and `d_from_piece` (`yes` +1.39), `width` (bins as
  `bus.k`).

### 7.4 `bus` (k isomorphic slices sharing a control)

Slices are level-0 cells not absorbed in a committed piece, or committed pieces (instances) in
later rounds. Group slices by key: for cells their colour class at round 0 of the `npn/in`
refinement (6.7 item 3: kind, NPN class with its support size, role flags), or `(kind, npn_sig,
len(ins))` with `--features none`; for pieces `(kind, canonical params)`. In each group, for each net `s` read by `>= 2` members, take the
members reading `s`; the **controls** are the nets read by all of them; the remaining (data)
inputs must be pairwise disjoint across members, else no bus. `k >= 2` gives a `bus` with
`nets["slice<i>"]` per slice and `nets["ctrl"]`. Bit order: the chain order when an `arith` or
`seqfn` hypothesis relates the slices (`order_source = "chain"`), else ascending lowest data-input
net id (`"net_id"`, a heuristic). Features: `k` bins `2` (0), `3-4` (+0.69), `5-8` (+1.39),
`9+` (+2.08); `ctrl_fanout_exact` (`yes`: every reader of the control is a member, +1.10; `no`
-0.69); `data_from_bus` (`none`, `some`, `all`: +1.10); `wl_depth` (the deepest round `r <=
WL_ROUNDS` at which all slices share one `npn/in` colour: `0` (0), `1` (+0.41), `2-3` (+0.69), `4`
(+1.10); `n/a` with features off, 0). Buses are non-exclusive and are not
committed as pieces; a bus with `p_comp >= COMMIT_P` writes `loki_bus = "h<k>[<bit>]"` on its
output nets (section 9.3).

### 7.5 `arith` (carry chains/adders, comparators)

**Chains.** A chain is a sequence of nets `y_0..y_{k-1}` (`k >= 2`) with supports
`S(y_0)` of size 2 (or 3: carry-in) and `S(y_i) = S(y_{i-1}) | {p_i, q_i}` with exactly two new
sources. Found by indexing nets with a non-`None` support by size and testing supersets. Every
ripple implementation (any LUT packing) has this property; it is a candidate only.

**Orientation** (exact, two simulations per bit): with every other source 0, evaluate `y_{i+1}`
for `(p_i, q_i) = (0, 1)` and `(1, 0)`. Both 0: symmetric bit (add). Exactly one 1: that
assignment is `(a_i, b_i) = (0, 1)` of a subtraction (borrow). All bits symmetric gives `adder`
(`A[i] = min(p_i, q_i)`, `B[i] = max`: addition is invariant under per-bit operand swaps); all
bits oriented gives `subtractor`; mixed gives no candidate. A size-3 `S(y_0)` gives `adder_cin`.
`Y` is the chain; a net whose support equals the last `S` and is not a chain member is offered as
`Y[k]` (carry-out; `Y_WIDTH = k + 1`).

**Comparators.** A net `z` whose support is exactly the union of two `bus` hypotheses `A`, `B` of
equal width `k` (or one bus and a chain's operands) gives one `comparator` candidate per op in
`eq ne lt le gt ge`, with both pairings (`B` in bus order and reversed); the prover keeps the ones
that hold. A net `z` whose support `S` has `2 <= |S| <= 16` and whose function over `S` is
`and_like` (or `or_like`) gives `eq_const` (`ne` for `or_like`) with `C` the on-minterm.
Features: `width` bins as `bus.k`; `out_reads` (`y` read by a register or primary output: `yes`
+0.69). Arithmetic and comparators are expected to be decided by proof.

**NPN evidence** (6.7 item 2; off with `--features none`). For bit `i >= 1` a *carry net* `c_i` is
a net that is not a chain member and whose support is `S(y_{i-1})` (bit 0 has none; for
`adder_cin` it is the carry-in). `npn_sum` is the share of bits whose function over the cut `(p_i,
q_i, c_i)` (bit 0: `(p_0, q_0)`) is in class `xor3` (bit 0: `xor2`), computed by simulating the cone
over the cut and counted only when that cone has no side inputs: `all` +2.30, `half` (>= 0.5)
+0.69, `low` -1.39, `no_cut` (no carry nets, a LUT-packed chain) 0. `npn_carry` is the share of
carry nets `c_{i+1}` whose function over `(p_i, q_i, c_i)` is in class `maj3` (bit 0: `and2`):
`all` +1.39, `half` +0.41, `low` -0.69, `no_cut` 0. Comparators: `npn_xor2` (`yes`: at least
`k / 2` cells of the cone are in class `xor2`, +0.69).

### 7.6 `mux` (mux trees)

Bit level: a cell with a `mux` fact (select set `T`, data leaves) gives `mux_bit` with claim
`muxn` (N = `2^|T|`). Trees: a `mux_bit` whose data leaf is the output of another `mux_bit` with
a disjoint select set, read only by it, is composed; a maximal composition of `>= 2` cells gives
`mux_tree` (params `N`, `S_WIDTH`; select order from the composition, leaves in select-value
order), claim `muxn`. Word level: a `bus` whose slices are `mux_bit`s (or `mux_tree`s) of one
select set gives `mux` of `WIDTH = k` (2:1: claim `mux2`, provable by `cone_check $mux`; N:1:
claim `muxn` per bit). Children: the slices. Features: `width` bins as `bus.k`; `sel_shared`
(`yes` +0.69); `npn_class` on `mux_bit` (the cell's class: `mux2` or `mux4` +0.69, `other` 0, a mux
merged with other logic in one LUT); a word `mux` copies its bus's `wl_depth` bin (7.4).

### 7.7 `seqfn` (counters: FF + incrementer feedback; shift registers, LFSRs)

**Groups.** (a) Q-support chains: FFs `q_0..q_{k-1}`, one clock, where the Q-nets in `S(D_i)`
are exactly `{q_0..q_i}` (`k >= 2`); (b) shift chains: `D_i`'s cone reads `q_{i-1}` and no other
FF of the group (`k >= 2`); (c) linear groups: SCCs of the FF dependency graph of size `>= 2`
whose next-state passes the linearity test below. The **controls** `C` are the other sources of
the D cones.

**Transition table.** When `k + |C| <= 16`, enumerate all `(q, c)` (exact); else sample
`SAMPLE_N` vectors (`rng("seqfn:<group>")`). For each `c`, `g_c(q)` is the next state. Classify:
`hold` (`g = q`), `inc` (`g = q + 1 mod 2^k`), `dec`, `modulo-M` (`g = q + 1` except on a terminal
set `E` where `g` is one constant `r`; `M` = `max(E) + 1` when `r = 0`), `load-const`, `shift-l`/
`shift-r` (`g = (q << 1 | x)` or `(q >> 1 | x << k-1)` with `x` a control), `linear`
(`g(a ^ b) = g(a) ^ g(b) ^ g(0)` on every tested pair). A group where some control value gives
`inc`/`dec`/`modulo` and the others give `hold` or `load-const` is a `counter` (params `dir`,
`width`, `modulus` or 0, `en`, `rst`, `rst_value`); `shift-*` gives `shift_reg`; `linear` with
feedback taps gives `lfsr` (params `taps`). The claim (op `counter`, `shift`, `lfsr`) is the
classified next-state function with the Q nets as inputs and the D nets as outputs; in the exact
case the prover confirms it, in the sampled case it adds `SIM_LLR` at best. A counter whose only
control is an enable is also offered to `cone_check` as `$add A_WIDTH=k B_WIDTH=1 Y_WIDTH=k` with
`B[0] = en`. Features: `table` (`exact` +0, `sampled` -0.69), `counter_terms` (number of control
modes, `1-2` +0.69).

### 7.8 `fsm` (FSMs: fsm_detect on the netlist)

Two sources of evidence:

1. **The `fsm_detect` pass** runs on the working level of each round when it holds `$dff` or
   `$adff` cells (a word-level input, or a future register raise). A wire it marks
   (`Wire.attr("fsm_encoding")` not `None`, `"none"` excluded) gives feature `fsm_detect = marked`
   (+4.61) on the hypothesis over those FFs. At level 0 of a BLIF it marks nothing (fact 8); the
   report says so.
2. **The bit-level analogue of fsm_detect's rules D-3 to D-5** on level 0. Candidates: SCCs of
   size `>= 2` of the FF dependency graph (one clock) and `seqfn` groups. Features:
   `ctrl_inputs` = `|C|` (`0` -1.10, `1-4` +0.69, `5+` -0.69); `decoder_readers` = share of the
   readers of the group's Q nets (support `<= 12`) that are equality-to-constant over the group
   bits for some fixed other inputs (`>= 0.5` +1.39); `counter_like` (`yes` when `seqfn` classified
   the group, -2.30); `self_reset` (D-5: forcing every equality reader to its non-matching value
   makes D constant, `yes` -0.69); `reset_found` (`yes`: all bits share an `ff_srst` net, +0.69).
   When `k + |C| <= 16`, the report gets the **transition table**: from the reset state (if
   `reset_found`) a breadth-first walk over all control values gives the reachable states and
   the transitions (at most 256 rows written); `params["states"]` is their count.

### 7.9 `unit` (datapath vs control: partition)

From round 2, on the view's committed pieces: a `datapath_unit` is a connected component (via
nets, not through control ports) of `>= 2` committed pieces whose kinds are arithmetic, mux,
register, counter or hard, plus the uncommitted cells between them whose role (7.10) is datapath;
a `control_unit` is a committed `fsm` with the control-role cells and pieces it drives. A piece
belongs to at most one unit per round. Children: its pieces. Feature `internal_ratio` (nets
internal / all nets touched: `>= 0.7` +1.10, `< 0.4` -1.10). A unit nests its children, so it
never conflicts them.

### 7.10 `role` (datapath vs control: per cell)

One `role` hypothesis per level-0 logic cell (log-odds of **control**). Seeds: cells of confirmed
or committed `fsm`; cells driving a `S` port of a `mux`/`mux_tree`/`mux_bit`, the `en`/`rst` of an
`ff_pattern` or `counter`: control sinks; cells inside committed arithmetic, `register` or a `bus`
with `k >= 4`: data. Propagation is L0's fixpoint (L0 spec 7.5) on the level-0 graph with these
sinks. Feature `role_prop` (`control` +2.30, `data` -2.30, `mixed` 0, `none` 0) and `in_bus4`
(`yes` -1.10). The predicted role is `mixed` when `role_prop = mixed`, else `control` when
`p >= 0.5`, else `datapath`. Role hypotheses do not compete and are not committed; committed
pieces get `loki_role` = the majority role of their cells.

## 8. Claims and provers (`loki.re.claims`, `loki.re.provers`)

`Claim(op, params, inputs, outputs)`: `inputs` and `outputs` are tuples of `(port, nets)` in
template port order, nets LSB first. `REFS[op](params, ins: dict[str, int]) -> dict[str, int]`
is the reference function over unsigned integers: `add`, `add_cin`, `sub`, `eq ne lt le gt ge`,
`eq_const` (`Y = A == C`), `mux2` (`Y = S ? B : A`), `muxn` (`Y = D[S]`; select values `>= N` are
don't-care), `counter`, `shift`, `lfsr`. Signed operations are not in L1.

Provers return `Verdict(verdict, engine, detail, cex)` with `verdict` in `equivalent differs
unproven invalid error`:

1. **`ConeCheckProver`** (ops `add sub eq ne lt le gt ge mux2` and the enable-counter form): on a
   scratch copy of level 0 made once per run. It computes the group (`cone(inputs, outputs)`) and
   its boundary nets itself; the claim must bind every boundary net (else `invalid`, no pass run,
   so stale `odin3:bind` texts never matter); a side input also makes it `invalid`. Then: set
   `lk<k>=1` on the group's nodes, `odin3:bind` = `PORT[i]` on every boundary net, run
   `cone_check -attr lk<k>=1 -cell <TYPE> -param ... -timeout <S>` and read `odin3:cone_check`
   (and `odin3:cone_cex`) immediately. An `Odin3Error` gives `error`, and the scratch copy is
   closed and made again.
2. **`TruthTableProver`** (every op): enumerates claim inputs plus side inputs when they total at
   most `EXHAUSTIVE_MAX = 16` (exact: `equivalent` or `differs` with a counterexample); else
   `SAMPLE_N = 4096` seeded random vectors (`differs` with a counterexample, or `unproven` with
   `detail = "sampled"`, which adds `SIM_LLR`).

The framework tries `ConeCheckProver` first when the op is one of its ops and the claim is
`cone_check`-shaped, then `TruthTableProver` on `invalid`. `equivalent` sets `L := max(L,
PROOF_LO)` and status `confirmed`; `differs` sets `-inf` and `refuted`; `unproven` from
`cone_check` (timeout) adds 0 and is counted in `report.timeouts`.

### 8.1 Proof transfer across a colour class (6.7 item 4)

**Groups.** Open hypotheses with a claim are grouped by `(kind, claim op, canonical params, tuple
over the claim's output nets of c_r(driver cell))`, `c_r` the `table/in` colour at round
`TRANSFER_ROUND = 2`. When a member `h0` gets `equivalent` from an exact prover (`cone_check`, or
`TruthTableProver` in its exhaustive mode; never a sampled `unproven`), every other member `h` of
its group, in id order, is tried with `cone_match`.

**`cone_match(graph, c0, c)`** walks both claims' level-0 cones in lockstep from the outputs and
keeps a map `M` from `c0`'s nets to `c`'s nets: claim output and input nets are paired by port and
bit; for every paired net that is not a claim input, both drivers must be cells of equal kind,
width and exact table, and their input nets are paired pin by pin; `M` must stay one-to-one in both
directions; neither cone may have a side input; both cones have the same number of cells. Cost
O(cone size).

**Effect.** A match makes `h` `confirmed`, `L := max(L, PROOF_LO)`, with `Evidence(source=
"transfer", name=h0.id, value="equivalent")` and `proof = {"engine": "transfer", "verdict":
"equivalent", "template": <h0's template>, "from": h0.id}`; a committed instance gets `loki_proof =
"derived"`. **Spot check:** in each group with at least one transfer, the transferred member with
the lowest id is also proved for real in the same round (it counts against `MAX_PROOFS`). If that
proof is not `equivalent`, every transfer from `h0` is revoked (the records get value `revoked`
and re-scoring skips them; the hypotheses return to `open`) and `report.features.transfer_failures`
counts it. Acceptance requires 0 (section 15).

**When transfer is sound.** A successful `cone_match` is an isomorphism of the two cones that keeps
pin order, cell functions and the claim's port binding, so `h`'s cone computes the same function
of its claim inputs as `h0`'s cone of its own, and `h0`'s exact proof of `REFS[op]` with the same
params proves `h`'s claim. Conditions: (a) the match; (b) an exact proof for `h0`; (c) the same op,
params and port widths; (d) cones at level 0 without side inputs.

**When it is not.** Equal colours alone never transfer a proof, even with exact tables in the
start colours and a refinement depth that covers the whole cone: 1-WL sees the unfolding tree,
not the cone, so reconvergent fan-out is invisible (a cell `g(x, x)` and a cell `g(y, z)` whose
inputs `x`, `y`, `z` share one colour get one colour, yet compute different functions of their
sources), and the 64-bit hash can collide. Colours of the `npn` variant never transfer (permuted or
negated inputs change the claim's binding). A sampled proof never transfers. The colour group is a
filter that makes the search near linear; `cone_match` is what makes the transfer sound. Raise at
commit still runs its own `cone_check` (9.3), so a transfer saves the prove step, not the commit
check.

## 9. The round loop (`loki.re.loop`)

### 9.1 Start

```
level0  = normalise(input, floor)           # never edited
graph   = FnGraph.from_design(level0)
working = level0.copy()
if hard cells and floor f1-*: run "unmap" on working (gated); hard hypotheses confirmed
```

### 9.2 One round `r` (1 to `MAX_ROUNDS = 8`)

1. **View.** `View.build(working, graph, overlay)` walks the top module: each node is a leaf cell
   (footprint by its source lines, fact 3), a raised cell (union of lines), or an instance of a
   committed piece (footprint = `overlay.get(node.attr("loki_hid")).cells`). Cells inside
   committed pieces are **absorbed**; their outputs that leave the piece become sources.
   `View.support(net)` is `FnGraph.support` with those outputs added as sources; detectors use
   the view's supports and cells, provers always use level 0.
2. **Propose.** Each detector in order; candidates merge into the overlay (5).
3. **Score.** Prior (calibration, `"<detector>/<kind>"`), feature LLRs, child effects, `STRUCT_CAP`.
4. **Prove.** Hypotheses with a claim, status `open`, never proved with this claim, and
   `p_comp >= PROVE_P`, ordered by `p_comp` desc then id, at most `MAX_PROOFS`. After a member of a
   transfer group (8.1) is proved `equivalent`, the other members get `cone_match` instead of a
   proof, plus the spot check.
5. **Re-score and compete** (6.5); mark `rejected`.
6. **Select commits.** Kinds with a commit form, status `open` or `confirmed`, `p_comp >=
   COMMIT_P`, every exclusive child already committed, no conflict with a committed hypothesis.
   Greedy over `(p_comp desc, KIND_RANK, |cells| desc, id)`, skipping any that conflicts an already
   selected one (losers: `rejected`, evidence `competition`).
7. **Commit** (9.3) on `working.copy()`; the old level is kept in `levels` (`--keep-levels`
   writes each with `write_json --odin3`).
8. **Stop** when the round committed nothing, created no hypothesis, and changed no log-odds by
   more than `1e-6` (`stop_reason = "fixed_point"`), or at `MAX_ROUNDS` (`"max_rounds"`), or when
   `--time-budget` seconds (default 3600) are spent at a round boundary (`"time_budget"`). Every
   round either commits (finitely many cells and pieces) or ends the loop, so it terminates.

### 9.3 Commit: raise and submod (decision 5)

For the selected hypotheses, in the selection order, on the new working copy:

1. **Raise** when the kind's form is `raise+submod`, the proof engine was `cone_check` (or
   `transfer` from a `cone_check` proof, 8.1), and every
   node of the group at this level is a leaf cell (no instance): set `lk<k>=1` on the group,
   `odin3:bind` on its boundary nets (found by name, `Module.net(name)`), run `cone_check` (the
   same session, immediately before, as `raise` requires), then `raise` with the same options.
   If the re-check is not `equivalent`, record `commit.form = "submod"` and continue without raise.
2. **Group.** Set `loki_sm = "<kind>_h<k>"` on every node of every selected hypothesis at this
   level (the raised cell, the leaf cells, and nested children's instance nodes).
3. **Submod.** One `submod -attr loki_sm`. Each piece becomes module `<kind>_h<k>` with instance
   `<kind>_h<k>_i`.
4. **Tag.** On the instance: `loki_hid`, `loki_kind`, `loki_conf` (`p_comp`, 4 decimals),
   `loki_proof` (`equivalent`, `derived`, `unproven`, `none`), `loki_role`, `loki_fn` (the recovered function
   as text, such as `Y = A + B`, `Q <= (Q == 9) ? 0 : Q + 1`, `fsm: 5 states`). On the module:
   `loki_kind`, `loki_fn`. On bus output nets: `loki_bus`.

A failed `submod` or `raise` (an `Odin3Error`) discards that working copy, marks the offending
hypothesis `rejected` with evidence `("commit", "error", <status>)`, and retries the commit
without it, once.

### 9.4 Final check

For F2 and F3: copy the final level, `flatten; lower; write_blif`, and run L0's
`loki.equiv.check_equiv` against the input BLIF; the result is `report.final_equiv`. F1 records
`skipped:hard` (decision 2). `differs` is a bug: the run exits 1.

## 10. Determinism

Same input, floor, seed, calibration file and options give byte-identical `design.v`,
`overlay.json`, `report.json`, `report.md`. Rules: every set is iterated sorted; hypothesis ids
come from the deterministic candidate order (7.1); randomness only through
`rng(purpose) = random.Random(f"{seed}:{purpose}")` (string seeding, deterministic across runs);
JSON through L0's `schemas.dump_json`, floats as `round(x, 6)`, infinities as the strings `"inf"`
and `"-inf"`; timings only in `timing.json`. The one exception is a `cone_check` timeout, which
depends on the machine: the report counts `timeouts`, and the determinism tests use designs whose
proofs finish far inside the limit. `--seed` defaults to 1. Structural features (6.7) are
deterministic too: colours are SHA-256 based and NPN classes exact (or the documented
semi-canonical form, itself deterministic).

## 11. Outputs (decision 6)

`loki re` writes into `--out DIR`:

- `design.v`: `write_verilog` of the final level: hierarchical, one module per committed piece,
  with the `loki_*` attributes of 9.3. Uncommitted logic stays as `$sop` assigns in its parent.
- `overlay.json` (5).
- `report.json`, schema 1: `input` (`path`, `sha256`, `floor`), `seed`, `calib` (`path`, `sha256`
  or `null`), `versions` (`loki`, `odin3`, `abi`), `rounds` (per round: `new`, `proved`
  `{equivalent, differs, unproven, invalid, error}`, `committed` ids, `rejected` count),
  `stop_reason`, `counts` (`cells`, `absorbed`, `committed`, `by_kind`), `pieces` (per committed
  hypothesis: `hid`, `kind`, `module`, `instance`, `p`, `proof`, `fn`, `cells`, `children`),
  `buses` (`hid`, `width`, `order_source`, `nets`), `roles` (`datapath`, `control`, `mixed` counts),
  `fsms` (`hid`, `states`, `reset_state`, `transitions`), `unmap` (`ok`, `unavailable`, `n/a`),
  `fsm_detect` (`applied`, `not-applicable`), `final_equiv`, `timeouts`, and `features`
  (`enabled`; `wl`: per variant `stable_round` and classes per round; `npn`: `distinct_tables`,
  `classes`, `exact`, `worst_enum`; `transfers`; `transfer_failures`). Each round also lists
  `engines` (`cone_check`, `truth_table`, `transfer` counts).
- `report.md`: generated from `report.json` only: a summary table, a pieces table (module,
  kind, confidence, proof, function), FSM transition tables, buses, and the round log.
- `timing.json`: seconds per round and per prover call, and of the feature build (6.7).

## 12. Scoring against L0 (decision 7)

### 12.1 L0 amendment: `words.json`

L0's per-floor files lack word-level connectivity, so L1 adds one file to each L0 floor directory
(plan Task 1), written from the L0 snapshot and the join, with no original names:

```json
{"schema": 1, "words": [
  {"id": 6, "type": "$add", "params": {"A_WIDTH": 4, "B_WIDTH": 4, "Y_WIDTH": 5},
   "fsm": false, "role": "datapath", "const_ports": ["B"], "footprint": ["n17", "n18"]}],
 "edges": [{"src": 6, "src_port": "Y", "dst": 9, "dst_port": "D"}]}
```

`footprint` = the final cells whose matched word ids contain `id`; `const_ports` = input ports
whose every bit is constant; `edges` = one per (driver word, port, reader word, port) pair over
nets, sorted. `loki check` validates it.

### 12.2 Construct precision and recall

Ground truth instances `g = (type, F_g)` from `words.json`, plus derived ones: **counter** = a
storage word `R` (width >= 2) and an `$add`/`$sub` word `A` with an edge `R.Q -> A.(A|B)`, the
other operand in `const_ports`, and a path `A.Y -> R.D` through `$mux`/`$pmux` words only
(`F_g` the union); **mux tree** = a connected component of `>= 2` `$mux`/`$pmux` words over
`Y -> A|B` edges; **fsm** = a storage word with `fsm = true` plus the mux words on its D side.
Words with an empty footprint are skipped.

An L1 hypothesis `h` counts when committed, or when `p_comp >= --score-p` (default 0.5). `h`
matches `g` when `g.type` is in the kind's scored set (6.1) and `Jaccard(F_h, F_g) >= 0.5`, with
`F_h` the L0 names of `h.cells`. Matching is one-to-one, greedy by Jaccard desc, then `h.id`, then
`g` id. Per kind and floor: precision = matched `h` / counted `h`; recall = matched `g` / all `g`
of the kind's types; also F1, and average precision over `p_comp` thresholds
`0.1, 0.2, ..., 0.9`. Kinds with no ground truth report `n/a`.

### 12.3 Bus recovery and roles

Ground-truth buses: L0 nodes grouped by equal non-empty `(module_path, bus_name)` with
`bit_index >= 0`, groups of size `>= 2` (PI and PO pseudo-nodes map to L1's port nets by name).
An L1 bus (`p_comp >= --score-p`) recovers a ground-truth bus when the Jaccard of their member
sets (output cells or port nets) is `>= 0.5`; one-to-one greedy as 12.2. Report bus precision,
recall, and for matched pairs **bit-order accuracy**: the share of shared members with equal bit
index (`order_exact`) and the same up to reversal (`order_up_to_reversal`), each split by
`order_source`.

Roles: over level-0 logic cells whose L0 role is `datapath` or `control`: precision, recall and
F1 of the predicted `control` and `datapath`; `mixed` reported separately as a confusion row.

### 12.4 Hierarchy similarity (the metric)

Both sides are trees over the same level-0 cells: L0 by `module_path` (each non-root prefix is a
cluster: the cells whose path starts with it), L1 by the committed pieces (each piece is a
cluster: its `cells`, nested pieces inside it). With `C_gt` and `C_l1` the non-root clusters:

- `F(g, h) = 2 |g & h| / (|g| + |h|)`;
- `HS_gt = sum_{g in C_gt} |g| max_h F(g, h) / sum |g|` (how well L1 recovers L0's modules);
- `HS_l1 = sum_{h in C_l1} |h| max_g F(g, h) / sum |h|` computed against `C_gt` plus the
  ground-truth construct footprints of 12.2 (how much L1 structure is real);
- `hier_f` = harmonic mean of the two (the hierarchical F-measure of Larsen and Aone, KDD 1999).

A design whose L0 hierarchy is flat (`C_gt` empty) reports `HS_gt = n/a` and only `HS_l1`. As a
secondary number, `nmi_leaf`: normalised mutual information (arithmetic-mean normalisation) of
the leaf partitions (each cell's deepest cluster), comparable to Narayanan et al.'s 0.73
(Gate-Breaker reference 12).

### 12.5 Calibration and aggregation

`loki calibrate --dataset D --floor F --split train --out calib/F.json` runs the flow with
`DEFAULTS` on every `ok` train design of floor `F`, labels each hypothesis true when it matches
(12.2), and writes 6.3's tables (deterministic). Evaluation uses the **test** split with that
calibration. `loki score` writes `score.json` per run; `loki score-all` writes a floor-by-kind
table (`scores.md`, `scores.json`) with micro-averaged precision, recall, F1, AP, bus, role and
hierarchy numbers, and the Gate-Breaker classes (VerilogEval `fsm`, `count`, `lfsr` problems)
listed per design.

With the structural features (6.7), `loki calibrate` also writes `node_llr` (item 1), `weights` and
the train `reliability` curve (item 5), using 2-fold cross-fitting over the train designs.
`loki score-all` adds per kind the reliability curve of `p_comp` on the test split (10 equal-width
bins: mean predicted, observed match rate, count) and `ece`. `loki score-all --compare DIR` takes a
second set of runs of the same designs made with `--features none` and writes `ablation.md` and
`ablation.json`: per floor and kind precision, recall, F1 and AP with and without the features and
their difference, plus proof calls by engine, transfers and `transfer_failures`.

## 13. CLI and the Wyrd III step

```
loki re <netlist> --floor {f1-k6,f1-earch,f2,f3,auto} [--odin3-root DIR] [--techlib L]
        [--calib FILE|none] [--out DIR] [--seed N] [--max-rounds R] [--timeout S]
        [--time-budget S] [--detectors a,b,...] [--keep-levels DIR] [--no-commit]
        [--features all|none]
        [--score-dataset D --score-design ID]   (also write score.json and metrics.json)
loki score <re_out_dir> --dataset D --design ID --floor F [--score-p P]
loki score-all <dir of runs> --dataset D --out DIR [--compare <dir of runs with --features none>]
loki calibrate --dataset D --floor F --split train --out FILE
loki re-project --dataset D --floors f2,... --split test --calib DIR --out datasets/l1
```

Exit codes of `loki re`: 0 done; 1 internal error or `final_equiv = differs`; 2 usage; 3 input
unreadable (an `Odin3Error` while normalising, message `odin3: <status>` and the first `error:`
log line). `--no-commit` stops after scoring round 1 (for detector debugging).

**Wyrd step** `loki-re` (entry point group `wyrd.steps`, `loki.re_step:ReStep`), following L0's
`DatasetStep` (L0 spec 8.1): `name = "loki-re"`, `tools = ()`, `is_vpr = False`. `loki re-project`
writes `datasets/l1/wyrd.toml` with one `[[design]]` per (design, floor) named `<id>__<floor>`
whose `files` is that floor's `netlist.blif`, `[recipe.re] steps = [{ use = "loki-re", calib =
"<dir>", dataset = "<D>" }]`, and `[sweep] recipe = ["re"] design = [all] arch =
["k6_frac_N10_frac_chain_mem32K_40nm"]`. `ReStep.command` returns `[sys.executable, "-m",
"loki.re.main", <file>, "--floor", <floor from the name>, "--calib", <calib>/<floor>.json,
"--out", <step_dir>/re, "--score-dataset", <D>, "--score-design", <id>]` (and `--odin3-root` from the step arg
`odin3_root`, else `$ODIN3_ROOT`, for `lib/vtr.o3lib` and `tools/equiv-check`); `collect` reads
`<step_dir>/metrics.json` (`rounds`, `committed`, `proved`, `refuted`, `timeouts`, `precision`,
`recall`, `bus_recall`, `hier_f`, `final_equiv_ok`).

## 14. Package layout (added to L0's)

```
loki/
  odin.py            (L0) still the only importer of odin3
  features/          (6.7; stdlib only; shared with L2)
    __init__.py      WL_ROUNDS, NPN_ENUM_MAX, FEATURES_VERSION
    graph.py         FeatureGraph, validate_feature_graph, from_graph_json
    roles.py         SignalConfig, NetRoles, classify_nets, restrict, is_forcing, is_hold
    npn.py           NpnClass, npn_class, shrink_support, NAMED, class_name
    wl.py            WLConfig, WLResult, refine, classes, stable_partition, Quotient, quotient
  re/
    __init__.py
    normalise.py     load_level0(path, floor, odin3_root, techlib) -> Design
    fngraph.py       Cell, FnGraph, from_design, cover_to_table
    fnfacts.py       FnFacts, facts, npn_sig, cofactor
    structural.py    feature_graph, StructFeatures, build_features, cone_match, transfer_key
    sim.py           simulate, support, cone
    claims.py        Claim, REFS
    provers.py       Verdict, ConeCheckProver, TruthTableProver, parse_cex, prove
    bayes.py         constants, Calib, load_calib, DEFAULTS, logit, sigmoid
    overlay.py       Evidence, Hypothesis, Overlay, KINDS, KindSpec, register_kind
    view.py          View, Piece
    detectors/       __init__ (Candidate, Detector, RoundContext, registry), hard.py,
                     ff_pattern.py, bus.py, arith.py, mux.py, seqfn.py, fsm.py, unit.py, role.py
    commit.py        commit(working, hyps, overlay, graph) -> Design
    seqtable.py      SeqTable, transition_table, classify, reachable
    loop.py          run_re(options) -> RunResult
    report.py        build_report, write_markdown
    main.py          python -m loki.re.main
  score/
    gt.py  match.py  metrics.py  calibrate.py
  words.py           build_words (L0 amendment, 12.1)
  re_step.py         ReStep
  re_project.py      write_re_project
```

Boundaries: everything except `normalise.py`, `fngraph.from_design`, `provers.ConeCheckProver`,
`commit.py` and `loop.py` is pure and unit-tested on hand-built `FnGraph` values; those five take
Odin III objects from `loki.odin` and are tested with `skipUnless(odin_available())`.

## 15. Acceptance (plan Task 16)

On L0's 12-micro subset (L0 plan Task 11 `SUBSET`), floor F2, default calibration:

1. every design: `loki re` exit 0, `final_equiv` `equivalent`, a second run byte-identical;
2. `bm_DL_four_bit_adder_continuous_assign`: an `adder` (or `adder_cin`) of width 4 committed with
   a proof and matching L0's `$add` (Jaccard >= 0.5);
3. `bm_DL_2_1_mux`: a `mux` committed and matching `$mux`;
4. `bm_DL_4_bit_comparator`: at least one `comparator` proved `equivalent`;
5. `bm_DL_4_bit_shift_register`: a `shift_reg` of width 4;
6. `bm_DL_Dff_w_synch_reset`: an `ff_srst` on every flip-flop of the register;
7. every run: `report.features.transfer_failures == 0`, and the structural features of a second
   run are identical (part of item 1's byte identity).

Then the VerilogEval test split at F2 with calibration from the train split: no run `fail`s; the
`scores.md` table is committed to `docs/results-l1.md` as the baseline, with the Gate-Breaker
failure designs (`Prob035_count1to10`, `Prob040_count10`, `Prob037_review2015_count1k`,
`Prob082_lfsr32`, `Prob110_fsm2`, `Prob119_fsm3`) listed with what L1 recovered. No precision
threshold gates the exit: the first numbers are the result. The test split is also run with
`--features none`, and the `score-all --compare` ablation table goes into `docs/results-l1.md`
next to the baseline.

## 16. Not in L1

LLM steps; e-graphs (alternatives stay on the overlay); signed arithmetic and comparators;
multipliers and dividers from soft logic; memories from soft logic (LUT RAM); bounded sequential
equivalence; proofs in parallel processes; the `write_json` bulk loader for VTR-size inputs (the
binding path is used; L2 or later); vector ports and net renaming in the output; GUI; any Odin III
core change (the gaps of 3.2 are open questions, not workarounds in the core); NPN classes of
cuts wider than 6 inputs; colours of committed pieces (later rounds reuse level-0 colours); typed
graphlets and the GNN (L2).

## 17. Decisions (Peter, 2026-10-21: "all good with the ideas")

All six recommendations below are decisions. In particular: (1) `words.json` is folded into L0: the
L0 build order is L0 Tasks 1-10, then L1 Task 1 (`words.json`), then L0 Task 11 onwards, so L0's
acceptance already covers it; (2) the unmap contract items (BLIF input with vtr.o3lib, provenance to BLIF
lines, the string attributes `unmap`, `unmap_note`, `unmap_cand`, and `unmap_cand` on converted `$mem`)
are kept by the unmap review; (3) no core change for bit-level FSMs; (4) and (5) the core options
`raise -const PORT=V` and vector ports for `submod` are later Odin III patch releases (after v1.0.4),
each with its own spec; (6) metrics and default likelihoods as stated until the first baseline.

The recommendations as written:

1. **L0 `words.json`.** L0 is planned but not built. Recommend folding 12.1 into L0 Task 7 and
   Task 10 briefs before L0 Task 7 starts; otherwise L1 Task 1 adds it as its own PR.
2. **The `unmap` contract** (7.2) is taken from the unmap spec on branch `feat/unmap-spec`
   (`bc9e5799`, under review). L1 needs four of its points to stay: the BLIF input situation
   S-2(b) with `lib/vtr.o3lib`, DERIVED provenance over the IMPORTED records (P-1), the string
   attributes `unmap`, `unmap_note`, `unmap_cand` (P-2, P-3), and `unmap_cand` on the converted
   `$mem` cells (the integer `unmap_origin` cannot be read from Python, fact 9). Recommend the
   unmap review keeps them; L1 Task 17 is gated on its merge and re-checks them as tests.
3. **`fsm_detect` at bit level.** The pass only sees word-level `$dff` + `$mux` trees, so on a
   LUT or gate netlist it never fires (fact 8). L1 runs it where applicable and reimplements its
   D-3 to D-5 rules on the bit-level graph in Python. Recommend no core change now.
4. **Constant operands.** `cone_check` cannot bind a constant and the ABI cannot create cells, so
   `Q + 1`, `A == 13` and modulo counters are committed as submodules with `loki_fn`, not as
   word cells. Recommend a later small core option (`cone_check`/`raise -const PORT=V`).
5. **Buses in the Verilog.** `submod` makes scalar ports and nets cannot be renamed, so buses are
   attributes and report entries. Recommend a later core `submod` option for vector ports by an
   attribute.
6. **Metric choices** (Jaccard 0.5 for matching, Larsen-Aone F for hierarchy, NMI secondary) and
   the default LLR table are agent defaults. Recommend keeping them until the first baseline.

## 18. Open questions on features A and B (2026-10-21, for Peter)

1. **numpy.** The request said "pure Python + numpy, no new dependency", but numpy is only in L2's
   optional `analysis` extra; L1's runtime is the standard library plus `odin3`. Recommend:
   `loki.features` uses the standard library only (`hashlib`), the L2 adapters turn its results
   into numpy arrays, and only if the measured budgets of 6.7 fail does an optional numpy path
   behind the `analysis` extra follow, with a test that it gives identical colours.
2. **Proof transfer by colour alone is unsound.** Equal 1-WL colours, even with exact tables in the
   start colours and a depth covering the cone, do not imply isomorphic cones (reconvergent
   fan-out, hash collisions). Recommend: transfer only after `cone_match` (8.1), with the colour
   group as a filter and one spot check per group; a failed spot check is a bug, counted, and fails
   acceptance.
3. **One signal classifier.** L1 needs the role flags before L2 exists. Recommend: the rules of L2
   spec 8.1 live once in `loki.features.roles` (L1 plan Task 5a) and L2's `classify_signals`
   delegates to it; if the pure-Python version misses L2's 60 s budget at 820k nodes, L2 keeps its
   numpy grouping of edges by net and shares only the per-net rule functions.
4. **Node-level likelihoods.** Recommend: the mean member LLR, binned (6.7 item 1), 2-fold
   cross-fitting within the train split, backoff from round 2 to 0, `NODE_MIN_COUNT = 5`; the test
   split is never used for calibration.
5. **Correlated evidence.** Recommend one weight per family on a 0.1 grid (6.7 item 5), keeping
   `STRUCT_CAP`; if the test `ece` exceeds 0.1 after the first baseline, replace the weights by a
   logistic-regression stack over the family sums, as its own change.
6. **NPN for k = 6.** Recommend the exact signature-pruned canonical form (6.7 B, worst case 92,160
   transforms per distinct table, cached); the semi-canonical fallback only if plan Task 5a's
   budget test fails, marked `exact = false` in the report. Calibration keys stay deterministic
   either way, and proof transfer never uses NPN classes.
7. **Raise after a transfer.** `raise` needs a `cone_check` right before it (9.3), so transfers
   save the prove step, not the commit check. Recommend keeping that rule and measuring the saved
   calls in the ablation (12.5) before any change.
8. **F3 consistency with L2.** L0's `graph.json` has no `lut_table` for `gate` nodes, while L1
   reads F3 gates as `$sop` tables, so L1 and L2 colours differ on F3. Recommend: L0 Task 12 also
   writes the gate's function table into `lut_table` of `gate` nodes; until then F3 colours are
   compared within L1 only.
