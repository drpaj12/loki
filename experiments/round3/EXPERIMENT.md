# Loki round 3: why the detectors miss (overlap rescoring), I/O-port words, the FSM chain

Protocol written 2026-10-24, before any round-3 number was computed. This file is committed and
pushed first (Stage 0); its commit SHA is the rule-provenance SHA quoted in the paper. A later
change to a rule is a dated entry in "Rule additions" at the end that keeps the old rule; the
paper reports the result under both rules.

Compute-only: no LLM call, no new detector code in `loki/`. The only new `loki re` runs are the
micro f3 and micro f1-k6 sets of the table below (existing detectors, existing command). The
scripts of this round live in `experiments/round3/`.

## Question

Peter (2026-10-24): from a reverse-engineering view, why is it hard to rebuild HDL from a
netlist? The structures are words (muxes, registers, comparators), control is mux selects and FSMs
(state feedback, decode, select), and the input and output words give hints where the datapath
words are. Round 2 showed that uncalibrated, the detectors propose many candidates that almost
never match the ground truth (ff_en 732 candidates / 1 correct, eq_const 279 / 1, mux_bit
160 / 0, register 77 / 16, fsm 5 / 2 on the 49 held-out designs), and that calibrated they commit
almost nothing. Are the wrong candidates fragments of real word constructs (a grouping problem:
fix by word-first detection) or unrelated (a detector problem)?

## Data

Ground truth (GT): the L0 floor directories (`words.json`, `labels.csv`, `graph.json`) of the
micro dataset (`work/loki-rename-exp/dataset-rebuild`, 68 designs at f2, 65 at f3, 68 at f1-k6) and
the VerilogEval dataset (`work/loki-veval-exp/dataset`, 150 designs, f2 and f3). GT constructs are
`loki.score.gt.derive_instances` (primitive words, plus derived register, counter, mux_tree,
fsm). Candidates and committed constructs: the `loki re` runs below.

| set | dataset | floor | calibration | runs | source |
|---|---|---|---|---|---|
| M2N | micro | f2 | none | 65 | round 2 `l1/runs/native-none` |
| M2C | micro | f2 | `calib/f2.json` of round 2 | 65 | round 2 `l1/runs/native-calib` |
| V2N | VerilogEval | f2 | none | 150 | round 2 `l2/runs/f2-none` |
| V2C | VerilogEval | f2 | VerilogEval train | 150 | round 2 `l2/runs/f2-calib` |
| V3N | VerilogEval | f3 | none | 150 | round 2 `l2/runs/f3-none` |
| V3C | VerilogEval | f3 | VerilogEval train | 150 | round 2 `l2/runs/f3-calib` |
| M3N | micro | f3 | none | 65 | new, `loki re --calib none` |
| M3C | micro | f3 | repo `calib/f3.json` | 65 | new |
| M1N | micro | f1-k6 | none | 68 | new, `loki re --calib none` |

New runs use the round-2 command (`r2lib.run_re`: `python -m loki.cli re <netlist.blif> --floor F
--calib <file|none> --out <dir>`), a 900 s timeout per run, and are scored with `score_run`
(`score_p` 0.5) as in round 2. A run that times out is missing from its set and the set size is
reported. No micro f1-k6 calibration exists, so M1N is the only f1 set. The primary set for the
decisions is P = M2N + V2N (f2, uncalibrated, 215 runs): it is where the many wrong candidates
arise. Every other set is reported, none decides.

Candidates of a run: the hypotheses of `overlay.json` that are counted at p >= 0.5 (committed, or
live with `p_comp` >= 0.5; `Pred.counted(0.5)`), restricted to the construct kinds of
`loki.score.gt.SCORED_TYPES` without the hard kinds (`hard_add`, `hard_mul`, `hard_mem`). These are
the candidates ("may") of `reverse-provenance.json` (`candidate_threshold` 0.5) and the
committed ones its "must" set; the script asserts that per run the counted total equals the
`counted` sum of `score.json` without hard kinds.

## Definitions

Cells are L0 node ids; a footprint is the cell set of a GT instance, a candidate is its `cells`.

Families (used for "matching or related kind"): storage = {$dff, $dffe, $adff, $adffe, $sdff,
$sdffe, $sdffce, $dffsr, $dffsre, $aldff, $aldffe, $dlatch, $adlatch, $dlatchsr, register,
counter, fsm}; mux = {$mux, $pmux, mux_tree}; compare = {$eq, $ne, $lt, $le, $gt, $ge}; arith =
{$add, $sub, $mul, counter}. Candidate kind to family: ff_en, ff_srst, register, counter, fsm to
storage; mux_bit, mux, mux_tree to mux; eq_const, comparator to compare; adder, subtractor,
adder_cin to arith. GT instance type to family by the same sets (a type may be in two families).

For a candidate c and a GT instance g: Jaccard J = |c & g| / |c | g|; containment of c in g =
|c & g| / |c|; coverage of g by a set of candidates = |g & (union of them)| / |g|.

### RQ-L9 measures (per set, per GT type group)

GT side. For every GT construct g whose type is in a scored type set (any type of
`SCORED_TYPES`, hard types excluded) over all runs of a set: best Jaccard of any counted candidate
of any kind; best containment (candidate inside g); fragmentation = number of counted candidates
with a non-empty intersection with g; union coverage of g by those candidates; whether g is
matched by the scorer (one-to-one greedy at J >= 0.5, same-type, as `construct_matches`).

Confusion. Each counted candidate is assigned the GT instance (any type, derived ones included)
with the highest J > 0 (ties: lowest natural id); the table counts (candidate kind, GT type); no
overlap is "none".

False candidate. A counted candidate of kind K in {ff_en, mux_bit, eq_const, register} that the
scorer does not match one-to-one (greedy, J >= 0.5, same scored type) in its run. The other kinds
are tabulated the same way but are not decisive. Each false candidate c gets exactly one class,
first rule that applies:

1. same_extent: J >= 0.5 with some GT instance of the family of K (it lost the one-to-one
   choice, or the type differs inside the family);
2. fragment_related: containment >= 0.8 in one GT instance of the family of K, and that instance
   is larger than c;
3. fragment_other: containment >= 0.8 in one GT instance of any other type (including plain
   gates such as $and, $or, $not);
4. straddle: not 1 to 3, and the union of the GT instances intersecting c covers >= 0.8 of c with
   at least 2 instances;
5. partial: not 1 to 4, and the union of all GT instances covers >= 0.5 of c;
6. noise: otherwise (less than half of c is inside any GT instance).

Fragments of a GT word g (for H9b): the counted candidates c of any kind of the family of g's
type with containment of c in g >= 0.8. Cov_frag(g) is their union coverage of g. Cov_any(g) is
the union coverage by every candidate with a non-empty intersection (upper bound, any kind). Only
GT instances with |g| >= 2 cells enter H9b.

### RQ-L10 definitions

Graph: `graph.json` of the floor (nodes with `kind`, `labels.cell_type`, `features.lut_table`,
`features.lut_width`; edges src, dst, net, pin). A cell signature is (kind, cell_type,
lut_table, lut_width).

Port words (level 0): label buses (`loki.score.gt.label_buses`) all of whose members are `pi`
nodes, or all `po` nodes, with at least 2 members, ordered by `bit_index`.

Forward step from an ordered word X = (x_0, ..., x_{k-1}): for bit i let E_i be the set of
(reader cell r, input pin p) over the edges with src x_i. The step signature of (r, p) is
(signature of r, p). A bit i is in class sigma if E_i holds exactly one pair of step signature
sigma. The class gives the group Y_sigma = (r_i for the bits in the class) when its cells are
pairwise distinct, are not `pi`, `po` or `const` nodes, and it has at least max(2, ceil(tau * k))
bits. Backward step: the same with the drivers: E_i = set of (driver cell d, pin p of x_i it
enters), step signature (signature of d, p). All bits of a group keep their bit index, so groups
are ordered.

tau = 0.75 is the primary (relaxed) rule; tau = 1.0 (strict: every bit) is also reported.

Hop h: level-1 groups are the steps from the port words; level-(h+1) groups are the forward and
backward steps from the level-h groups (deduplicated by cell set; a group is kept at the lowest
level it appears). The search stops at level 4 or when no new group appears.

Seeding: a group Y seeds a GT construct g when |Y & g| >= 2 and |Y & g| / |Y| >= 0.5. A GT
construct is reached at hop h if a group of level <= h seeds it (level 1 = adjacent to a port
word, "a port word" for the construct's inputs or outputs); never reached otherwise. The stricter
"full" seeding J(Y, g) >= 0.5 is also reported.

GT constructs counted: those with width >= 2 and |g| >= 2 cells, where width = max of the
WIDTH, Y_WIDTH, A_WIDTH, B_WIDTH params of the words.json word (derived register: the storage
word's WIDTH; counter, mux_tree, fsm: only |g| >= 2 is required). Kinds: register (derived),
mux ($mux, $pmux), mux_tree, adder ($add), subtractor ($sub), comparator ($eq, $ne, $lt, $le,
$gt, $ge with no constant port), counter: datapath. eq_const ($eq, $ne with a constant port) and
fsm: control. Primitive storage words are not counted separately (they are in register).

### RQ-L11 definitions (GT only, then detectors)

Word graph of `words.json` (nodes = word ids, edges as given with ports).

- Feedback register R: a storage word with a directed path from its Q to its own D through at
  most 6 non-storage words.
- Decoder d: an $eq or $ne word with a constant port and a direct edge from the Q of a feedback
  register.
- Sink x: a $mux or $pmux word with an S edge, or a storage word with an EN or SRST edge, whose
  source is a decoder directly, or a decoder through at most 2 intermediate non-storage words of
  type $not, $and, $or, $xor, $xnor, $logic_not, $logic_and, $logic_or, $reduce_and, $reduce_or,
  $reduce_bool.
- Chain: a triple (R, d, x).

GT measures per set (GT does not depend on the calibration): number of feedback registers (and
of those flagged `fsm` in words.json), decoders, sinks, chains; share of GT muxes with an S edge
whose select comes from a decoder on a feedback register (the chain share), the same for
any $eq/$ne-with-constant decoder (not necessarily on a feedback register), and for enables.
Detector side, per run set: each chain element (R as the derived register instance when width
>= 2, else its word; d and x as their words) is "proposed" if some counted candidate of any kind
has J >= 0.5 with its footprint, "kind-correct" if that candidate's scored type set contains the
element's type, "committed" if it is committed. A chain is "complete" if all three elements are
proposed. Also the number of GT fsm instances matched by a counted fsm candidate.

## Hypotheses and numeric decision rules

All decisive numbers use the primary set P (RQ-L9) or the f2 floor of both datasets pooled
(RQ-L10); shares are micro (pooled counts), not per-design means.

H9a (most false candidates are fragments of a word of a matching or related kind). Let s_K be
the share of class fragment_related among the false candidates of kind K in P, and s the pooled
share over the four kinds. Supported: s_K >= 0.50 for at least 3 of the 4 kinds and s >= 0.50.
Not supported: s < 0.25, or the pooled share of class noise >= 0.50. Otherwise inconclusive.
Reported alongside: the shares of every class, so the reader can see same_extent and
fragment_other (detector confusion rather than grouping).

H9b (a GT word's fragments cover most of it, so grouping would recover it). Let q_K be the share
of the GT instances of the types of K (SCORED_TYPES[K], |g| >= 2 cells) in P with Cov_frag(g) >=
0.8. Supported: q_K >= 0.50 for at least 3 of 4 kinds. Not supported: the pooled share < 0.20.
Otherwise inconclusive. If H9a is supported and H9b is not, the paper says grouping alone does
not recover the words.

Reading of RQ-L9 for the next detector: word-first grouping is the fix only if H9a is supported;
if H9a is not supported and noise or fragment_other dominates, the detectors themselves are the
problem.

H10 (datapath words are reached from the I/O words within a few hops; control is not). D = share
of GT datapath constructs of the f2 floor (both datasets pooled, relaxed tau 0.75) reached at hop
h <= 2; C = the same for control constructs. H10a: supported when D >= 0.50, not supported when D
< 0.25, otherwise inconclusive. H10b: supported when C <= D - 0.20, not supported when C > D -
0.10, otherwise inconclusive. Per-kind shares for h = 1, 2, 3, 4, the strict rule, the f3 and
f1-k6 floors and per dataset are reported, not decisive. The chain share of RQ-L11 (muxes whose
select is decoded from a feedback register) is quoted next to C as the report the brief asks for.

RQ-L11 has no hypothesis and no status: measurement only. It scopes the chain-aware detector.

## Outputs

`l9_gt.csv`, `l9_false.csv`, `l9_confusion.csv`, `l9_h9b.csv`, `l10_reach.csv`,
`l10_ports.csv`, `l11_gt.csv`, `l11_detect.csv`, `r3_status.csv` (the decisions) written by
`l9_overlap.py`, `l10_propagate.py`, `l11_chain.py`, `decide.py` through `r3lib.py`;
`paper_tables.py` turns them into `docs/paper/round3-tables.tex` and `round3-log.tex`
(`\rtt...` macros). CSVs and the generated .tex regenerate byte for byte from the data (sorted
iteration, no randomness, no timestamps).

## Rule additions

No rule was changed. Implementation notes, 2026-10-24, added after the data (they alter no
threshold or definition above):

- `l10_design.csv` and the per-design macro-average of the h <= 2 shares are an extra,
  report-only output (the decision rule uses the pooled counts); it was added after the pooled
  numbers were seen, because one VerilogEval design holds 1,793 of the 2,124 datapath
  constructs.
- M3N has 64 scored runs of 65: `micro_bm_arithmetic_unused_bits` (15,225 nodes) hit the 900 s
  timeout. Candidates and `loki re` options were as in round 2; the micro runs were made under
  the heavy lock.
- Environment of the new runs: venv of `work/loki-f3-exp`, Odin III checkout 1.1.0 (ABI 6).
