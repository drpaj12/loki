# Loki III L1: the Bayesian hypothesis flow (design)

Status: decisions approved by Peter, 2026-10-21 (section 2, items 1 to 7, verbatim); everything
else is an agent default he may override. Open questions are section 17. This file is for his
review.

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
not a canonical form.

## 5. The overlay data model (`loki.re.overlay`)

```python
@dataclass
class Evidence:
    round: int
    source: str        # "prior", "feature", "child", "cone_check", "truth_table", "sim", "hard", "competition"
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
    proof: dict[str, str] | None     # {"engine", "verdict", "template", "cex"}
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

With no calibration file (`--calib none`), `loki/re/bayes.py` `DEFAULTS` applies: prior log-odds
0 for every kind and the feature table of section 7 (each detector lists its default LLRs).
Hypotheses whose kinds have no feature evidence then move only by proofs, simulation and children.

### 6.4 Evidence

Detectors report **features as bin labels** (strings), never LLRs; the framework turns a feature
into an LLR through the calibration table (`llr` of that bin, 0 for an unseen bin). Proofs and
simulation add the fixed records of 6.2. All evidence is an `Evidence` record, so the report can
explain every number.

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
later rounds. Group slices by key: for cells `(kind, npn_sig, len(ins))`, for pieces
`(kind, canonical params)`. In each group, for each net `s` read by `>= 2` members, take the
members reading `s`; the **controls** are the nets read by all of them; the remaining (data)
inputs must be pairwise disjoint across members, else no bus. `k >= 2` gives a `bus` with
`nets["slice<i>"]` per slice and `nets["ctrl"]`. Bit order: the chain order when an `arith` or
`seqfn` hypothesis relates the slices (`order_source = "chain"`), else ascending lowest data-input
net id (`"net_id"`, a heuristic). Features: `k` bins `2` (0), `3-4` (+0.69), `5-8` (+1.39),
`9+` (+2.08); `ctrl_fanout_exact` (`yes`: every reader of the control is a member, +1.10; `no`
-0.69); `data_from_bus` (`none`, `some`, `all`: +1.10). Buses are non-exclusive and are not
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

### 7.6 `mux` (mux trees)

Bit level: a cell with a `mux` fact (select set `T`, data leaves) gives `mux_bit` with claim
`muxn` (N = `2^|T|`). Trees: a `mux_bit` whose data leaf is the output of another `mux_bit` with
a disjoint select set, read only by it, is composed; a maximal composition of `>= 2` cells gives
`mux_tree` (params `N`, `S_WIDTH`; select order from the composition, leaves in select-value
order), claim `muxn`. Word level: a `bus` whose slices are `mux_bit`s (or `mux_tree`s) of one
select set gives `mux` of `WIDTH = k` (2:1: claim `mux2`, provable by `cone_check $mux`; N:1:
claim `muxn` per bit). Children: the slices. Features: `width` bins as `bus.k`; `sel_shared`
(`yes` +0.69).

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
   `p_comp >= PROVE_P`, ordered by `p_comp` desc then id, at most `MAX_PROOFS`.
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

1. **Raise** when the kind's form is `raise+submod`, the proof engine was `cone_check`, and every
   node of the group at this level is a leaf cell (no instance): set `lk<k>=1` on the group,
   `odin3:bind` on its boundary nets (found by name, `Module.net(name)`), run `cone_check` (the
   same session, immediately before, as `raise` requires), then `raise` with the same options.
   If the re-check is not `equivalent`, record `commit.form = "submod"` and continue without raise.
2. **Group.** Set `loki_sm = "<kind>_h<k>"` on every node of every selected hypothesis at this
   level (the raised cell, the leaf cells, and nested children's instance nodes).
3. **Submod.** One `submod -attr loki_sm`. Each piece becomes module `<kind>_h<k>` with instance
   `<kind>_h<k>_i`.
4. **Tag.** On the instance: `loki_hid`, `loki_kind`, `loki_conf` (`p_comp`, 4 decimals),
   `loki_proof` (`equivalent`, `unproven`, `none`), `loki_role`, `loki_fn` (the recovered function
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
proofs finish far inside the limit. `--seed` defaults to 1.

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
  `fsm_detect` (`applied`, `not-applicable`), `final_equiv`, `timeouts`.
- `report.md`: generated from `report.json` only: a summary table, a pieces table (module,
  kind, confidence, proof, function), FSM transition tables, buses, and the round log.
- `timing.json`: seconds per round and per prover call.

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

## 13. CLI and the Wyrd III step

```
loki re <netlist> --floor {f1-k6,f1-earch,f2,f3,auto} [--odin3-root DIR] [--techlib L]
        [--calib FILE|none] [--out DIR] [--seed N] [--max-rounds R] [--timeout S]
        [--time-budget S] [--detectors a,b,...] [--keep-levels DIR] [--no-commit]
        [--score-dataset D --score-design ID]   (also write score.json and metrics.json)
loki score <re_out_dir> --dataset D --design ID --floor F [--score-p P]
loki score-all <dir of runs> --dataset D --out DIR
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
  re/
    __init__.py
    normalise.py     load_level0(path, floor, odin3_root, techlib) -> Design
    fngraph.py       Cell, FnGraph, from_design, cover_to_table
    fnfacts.py       FnFacts, facts, npn_sig, cofactor
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
6. `bm_DL_Dff_w_synch_reset`: an `ff_srst` on every flip-flop of the register.

Then the VerilogEval test split at F2 with calibration from the train split: no run `fail`s; the
`scores.md` table is committed to `docs/results-l1.md` as the baseline, with the Gate-Breaker
failure designs (`Prob035_count1to10`, `Prob040_count10`, `Prob037_review2015_count1k`,
`Prob082_lfsr32`, `Prob110_fsm2`, `Prob119_fsm3`) listed with what L1 recovered. No precision
threshold gates the exit: the first numbers are the result.

## 16. Not in L1

LLM steps; e-graphs (alternatives stay on the overlay); signed arithmetic and comparators;
multipliers and dividers from soft logic; memories from soft logic (LUT RAM); bounded sequential
equivalence; proofs in parallel processes; the `write_json` bulk loader for VTR-size inputs (the
binding path is used; L2 or later); vector ports and net renaming in the output; GUI; any Odin III
core change (the gaps of 3.2 are open questions, not workarounds in the core).

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
