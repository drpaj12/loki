# Loki round 6: the L15 loss audit

Protocol written 2026-10-27, before the audit was run on any evaluation design. This file is
committed and pushed first (Stage 0); its commit SHA is the rule-provenance SHA quoted in the
paper. A later change to a rule is a dated entry in "Rule additions" at the end that keeps the old
rule; the paper reports the result under both rules. Post-data analyses are dated, labelled
exploratory entries and never change a status.

Purpose chain (hub `docs/purpose.md`): Loki L3 (where reverse engineering loses information),
question **L Q3.1**: for each HDL construct, at which Odin III step is it first lost as a separable
unit, joined with what, and why? L Q3.2 (what a detector could recover from the provenance) is
exploratory notes only. Measure: understanding of where structure is lost (counts of constructs lost
per kind and pass, the share the D14 provenance explains, detector recall before and after a pass),
not area, speed or power directly. RQ prefix of this round: L15 (reserved since round 4).

## Questions

- RQ-L15a: per construct kind and Odin III pass of the round-5 flow, how many constructs are first
  lost at that pass, and is that more than a random grouping of the same size would lose (null)?
- RQ-L15b: which constructs do they join with, and what is the reason class?
- RQ-L15c: what share of the losses does the D14 provenance explain (a labelled join record that
  names the construct, written by the pass that lost it)?
- RQ-L15d: per detector arm and snapshot, which kinds does a pass fool (recall found before, missed
  after)?

## What was known before this file

Round 5 (loki main ce12a3c, `experiments/round5/EXPERIMENT.md`): register and enable words are
findable; FSM decoders, compare and mux boundaries are absorbed into LUTs at f2. D14 is merged in
Odin III main c82609e6 (v2 maps `--prov-map`, `names --lookup/--chain`, `odin3.read_name_map`,
the `join` label of V1.2.0 3.3). No loss-audit number of any kind existed before this file.
Development used only hand-written Verilog fixtures (unit tests) and the corpus **train** split
(`r4_adder_000`, `r4_fsm_000` and similar) to learn the shape of the maps: the map holds nodes
only after `proc` (a design with processes cannot be written before `proc`), a snapshot is
written with `write_json --name-style hash --prov-map refs` inside one Python session, the pass
runs are named in the `T` lines, the `R` records carry the `join` flag, and construct ids `c<n>`
are renumbered per file.

## Environment

Odin III c82609e6 (release build of the detached worktree `work/odin3-c826`, built with
`tools/build-locked --preset release`; the pip-style install is `PYTHONPATH=<worktree>/plugins/python`
plus `ODIN3_LIB=<worktree>/build/release/libodin3.so`, as in round 5, no wheel), Loki
`exp/round6` (main ce12a3c plus this branch), the Wyrd venv of `work/loki-f3-exp`, 12 cores, 23 GB
VM. Odin batches run through `tools/heavy-run` (heavy lock, 6 GB slice), one batch per call, so
memory stays far under 60% of the VM. Architecture for `read_arch`:
`k6_frac_N10_frac_chain_mem32K_40nm` (f2, as in round 5). Data under `work/loki-exp6-data/`
(not in git). No LLM call, no VPR run.

## Design sets (fixed here, smallest first)

| set | designs | notes |
|---|---|---|
| MI | the 68 micro designs with an ok f2 floor in `work/loki-rename-exp/dataset-rebuild` | sources `tests/micro/verilog/micro/<name>.v` of the c826 worktree |
| VT | the 33 VerilogEval designs of the manifest split `test` (ok f2) of `work/loki-veval-exp/dataset` | `.sv` sources through the slang adapter, read flags as `loki.odin.read_flags` |
| CI | the 120 corpus iid designs (ok f2) of `work/loki-exp4-data/corpus` | sources `corpus-project/designs/<d>/<d>.v` |

These are the round-5 sets MI, VT, CI at f2 with the same n. CO (240 ood) is not run: the iid
set already covers the same generators and the audit has no train/test effect to separate. BIG is
**not** in the confirmatory sets. If time remains after the tables, the three smallest BIG
designs may be run last, one at a time, as an exploratory entry (peak RSS recorded; the run is
dropped if the slice cap is hit). A design that Odin III rejects, or whose snapshot run fails, is
recorded with the reason and left out of every table (n is reported per table). The corpus train
split and hand fixtures are development data and never enter a table.

## Snapshot points

The flow is the round-5 f2 script, run pass by pass in one Python session (`Design.run_script`
runs one pass at a time; verified):

    read_arch A; read_verilog --nolatches --vtr-compat --prov-ast refs F   (no --vtr-compat for .sv)
    proc; fsm; opt; flatten; opt -full; wreduce; lower; abc --lut 6

Snapshot S_k is written after pass k, k = 1..8: S1 proc, S2 fsm, S3 opt, S4 flatten, S5 opt -full,
S6 wreduce, S7 lower, S8 abc. Each writes `write_json <file> --name-style hash --prov-map refs`
(netlist plus v2 map). S0 (after the read) is written only when the design has no processes and is
otherwise recorded as unwritable (`write_json` refuses a module with processes); the audit starts
at S1, so a construct that is already not separable at S1 is classed `born-joined` (first
snapshot) and has no loss pass. S7 and S8 also write `write_blif --vtr --name-style hash
--prov-map refs` for the detectors. At S6 the word cells are read with `loki.snapshot.take_snapshot`
(the round-5 ground truth source). The BLIF/JSON writers do not change the design; a check
(final BLIF of S8 byte-identical to the same flow without the prov options) runs on MI and is
reported.

## Definitions

**Object.** A live logic object of a snapshot: an `O` or `N` line of kind `node` with a type
other than `$const`/`$port_*` (JSON snapshots S1..S8). Wires and ports (kind `wire`, `net`) are
not objects: they keep their declaration chain at every snapshot and cannot be lost.

**Leaf set of an object.** Walk the object's naming record backward through `R` parents, each
record once, skipping the last `n` parents of a record whose flags have `ctx=n` (flatten's instance
record, V1.2.0 3.3). A `S` record with a construct `c<n>` is a construct leaf; leaves without a
construct (`chain=span`, imported) are ignored. The file-stable key of a construct is
`(file path, kind, span, name)`; ids are not compared across snapshots.

**Unit of the audit, level `stmt` (the main level).** The anchor of V1.2.0 3.3: a leaf construct
of level `stmt` or coarser is its own anchor, otherwise its nearest ancestor of that level. The
reduced set U(o) of an object is its anchors with every ancestor of another member removed. The
units are the anchors that occur in U(o) of some object at some snapshot. Two bits of one
statement, or a statement and its own condition, are one unit.

**Unit, level `branch`.** As `stmt`, except that a leaf (or its anchor) that lies under a branch
row (`CASE_ITEM`, `IF_THEN`, `IF_ELSE`) is mapped to its nearest branch ancestor-or-self; then the
reduced set is formed. The `branch` level tells apart the arms of one `if`/`case` that `stmt`
folds into one statement; it is reported next to `stmt`, never instead of it. Level `word` (the
declarator of the signal a cell drives) is **not observable** in the map: a cell's chain reaches
the expressions and statements that made it, not the declaration of the net it drives, and the
declaration chain sits on wires, which are not objects. The `word` level is reported as not
observable, with no number.

**Separable at S_k.** A unit u is separable at S_k when some object o at S_k has U(o) = {u}.
(A set of objects with a chain to u and to no other unit exists exactly when one such object
exists: every member's U is contained in {u}.) **Lost at S_k** (k >= 2): u separable at S_{k-1}
and not separable at S_k. u is **permanently lost at S_k** when it is not separable at any later
snapshot, **transiently lost** when it is separable again later. The headline uses the first loss
(transient or not); the transient count is a separate column. A unit separable at S1 and never
lost is `kept`. A unit not separable at S1 is `born-joined` (not part of the loss counts).

**Join partner.** At S_k, Q(u) is the union of U(o) \ {u} over the objects o at S_k with u in
U(o), sorted by (file, start line, start column, kind), reported with the first five and the total.
If no object at S_k reaches u, u is `removed` and has no partner.

**Hardware kind of a unit** (for the kind axis and the detector link). From the Odin III types of
the objects that are pure for u at the first snapshot where it is separable: `fsm` if any is
`$fsm` or carries the FSM marker, else `register` if any type is storage (`loki.score.gt.STORAGE`),
else `arith` (`$add`, `$sub`, `$mul`, `$alu`), else `mux` (`$mux`, `$pmux`), else `compare`
(`$eq`, `$ne`, `$lt`, `$le`, `$gt`, `$ge`), else `logic`. The AST kind of the unit (`NET_ASSIGN`,
`NONBLOCKING_ASSIGN`, `IF`, `IF_THEN`, ...) is the other axis. Tables are given per both axes.

**Explained loss.** A loss of u at S_k (merged, not removed) is explained when some object o at S_k
with u in U(o) has, in its provenance, a record r that is derived (`D`), carries the flag `join`
(or `join=instance`), whose pass run (`T` row, matched by pass name and argument string to the
pass of S_k) is the pass of S_k, and whose `cons` contains u's key (a `lossy=cap` record whose
visible `cons` lacks u is **not** explained; it is counted as `capped`). Reported separately:
unexplained merged losses, `removed` losses (no join record is expected for a removal). Explained
share = explained / merged losses.

**Reason classes.** First matching rule, evaluated for each loss; the class names the observable
evidence only.

| class | evidence in the map | plan class it stands for |
|---|---|---|
| `removed` | no object at S_k reaches u | dead or constant-folded logic removed (constant fold) |
| `fsm-recode` | pass S_k is `fsm` and u is merged or removed | FSM re-encode |
| `instance-join` | explained by a `join=instance` record | style/hierarchy collapse by flatten |
| `opt-merge` | explained, pass `opt` (either run) | constant fold/share |
| `width-reduce` | explained, pass `wreduce` | constant fold/share (width) |
| `lower-share` | explained, pass `lower` | restructure mux to AND-OR, adder to gates (read with the hardware kind) |
| `lut-cone` | explained, pass `abc` | LUT-cone merge, adder to LUT/carry (read with the hardware kind) |
| `unlabelled-merge` | merged at S_k, not explained | joins the D14 map does not label |

"Restructure mux to AND-OR" and "adder to LUT/carry" have no class of their own: they are
`lower-share` / `lut-cone` read with the hardware kind `mux` / `arith`. "Style collapse" has no
direct evidence in the map (a style change leaves no record); it is reported as not observable,
with the count of losses at `proc` whose partner has another AST kind as an exploratory column.
A class with no losses is reported with zero, never dropped.

**Null baseline (random object set).** For every design and every k >= 2, draw 5 times (seed =
sha256 of design name, k and draw index): one random unit set per real object of S_k, with the
size |U(o)| of that object, the units drawn uniformly without replacement from the pool of units
that are separable at S_{k-1} or reached by some object at S_k (if the pool is smaller than the
size, all of it). A unit u is null-separable at S_k when some null object has U = {u}. Null loss at S_k =
units separable at S_{k-1} (real) and not null-separable at S_k. The null keeps the object
count and the size distribution of each pass, so removal and chain growth are matched; only the
who-merges-with-whom structure is random. Reported: null mean per kind and pass next to the real
count. (A pass-order permutation null is not used: the snapshots are cumulative, so permuting
them is not defined.)

## Detectors and recall

Arms (uncalibrated, `--features none`, `--calib none`, `--floor f2`, timeout 900 s): **B** the
default detector list of `loki re`, **W** `--detectors wordfirst`, **WB** `--detectors
wordfirst,hard,ff_pattern,mux,arith,seqfn,fsm,bus,unit,role,wordgroup` (round-5 lists). They run
on the BLIF of **S7** (gate netlist after `lower`) and **S8** (LUT netlist after `abc`); the
word-level snapshots S1..S6 are not netlists a Loki detector reads (`.names`/`.latch` only), so
detector recall at S1..S6 is reported as not defined, not as zero. Ground truth: the round-5
`derive_instances` on a words dict built from the S6 word cells (`take_snapshot`; edges by shared
nets, `const_ports`, `fsm`), with the footprint of word w at S_k = the cells (S7 gates, S8 LUTs) that
drive an S_k net whose leaf-construct set (expr level, by key) contains the leaf-construct set of
w (the span-subset rule of L0, on construct keys). Counted candidates and recall are the
round-5 scorer's: `construct_scores` with `score_p` 0.5, instances of at least one cell, micro sums
per kind over designs. Recall of kind K at S_k is matched/GT over the set's designs that have both
snapshots (paired). All three arms are reported; no baseline choice is made.

## Numeric rules (every outcome reachable)

Pooled over a set (and over MI+VT+CI as "all"); a kind-axis cell with fewer than 10 first losses
pooled is `too few` and gets no claim.

1. **Where a kind is lost.** For kind K with L_K >= 10 first losses, p_K = the pass with the most
   losses and s = its share of L_K; the null share s0 = null losses at that pass over null
   losses of K (null kind = the hardware kind of the unit). Outcomes: `dominant` if s >= 0.5 and
   s - s0 >= 0.2; `dominant-null` if s >= 0.5 and s - s0 < 0.2 (a growth artefact); `spread` if
   s < 0.5.
2. **Pass above chance.** A pass P loses kind K `above chance` if real losses >= 5 and real >=
   2 x null mean; `at chance` if real >= 5 and 0.5 x null mean < real < 2 x null mean; `below chance`
   if real >= 5 and real <= 0.5 x null mean; `few` if real < 5.
3. **Explained share** (merged losses, all sets pooled, and per pass): >= 0.90 `D14 explains`,
   0.50 to < 0.90 `partly explained`, < 0.50 `mostly unexplained`. Needs >= 20 merged losses, else
   `few`.
4. **Detector fooled.** Per arm, kind K with GT >= 10 at S7 and S8 (paired designs): delta =
   recall(S8) - recall(S7). `fooled by abc` if delta <= -0.20, `not fooled` if |delta| < 0.20,
   `helped` if delta >= 0.20, `too few` if GT < 10.
5. **Transient losses.** Reported as a share of first losses; no claim rule.

## Stages

1. Audit tool (`loki/audit/`, `loki audit`), unit tests on hand-built maps and two micros with a
   loss pass known by construction. Gates: ruff, mypy --strict, unittest.
2. Snapshot runs on MI, VT, CI (one `heavy-run` batch per set), then the audit tables.
3. Detector runs on S7 and S8, recall tables.
4. Tables, paper section (round 6), result.

## Reproduce

Environment as above (`ODIN3_ROOT`, `ODIN3_LIB`, `PYTHONPATH=<c826>/plugins/python:<checkout>`,
`ODIN3_WS`). From `experiments/round6`:

    python run_snap.py MI|VT|CI        # one batch: snapshots + maps into work/loki-exp6-data/snap/
    python run_audit.py                # per-design audit JSON and the tables (CSV)
    python run_detect.py               # B, W, WB on S7 and S8, recall
    python decide.py                   # r6_status.csv by the numeric rules
    python paper_tables.py             # docs/paper/round6-tables.tex

The module and script names are fixed by the code in this branch; a rename is a dated entry
below.

## Rule additions

(none yet)

### 2026-10-27 (before any evaluation run): `removed` split into `removed` and `subsumed`

Found on development designs (corpus train `r4_fsm_000`): the reduced set drops a unit that is
an ancestor of another member, so a register whose leaves are `{ALWAYS, IF}` becomes `{IF}` and the
`ALWAYS` block reads as "reached by no object" although a chain to it remains. The Stage-0 rule
is kept as written (a unit no reduced set contains is lost; the class `removed` of the table
above counts it). The audit now also writes `subsumed` = no reduced set contains u, but some
object has u among its unreduced anchors (u is only the enclosing statement of a finer unit). The
tables report `removed` (no chain at all) and `subsumed` as two columns, and "Stage-0 removed" =
their sum. `subsumed` is not a merge, so it is outside the explained-share denominator under
the new rule; under the Stage-0 rule it is outside too (removed losses are not merged).

### 2026-10-27 (before any evaluation run): units first separable after S1

The Definitions section says "lost at S_k = separable at S_{k-1} and not at S_k" and also "a unit
not separable at S1 is `born-joined`". They conflict for a unit that is joined at S1 and becomes
separable later (for example when `lower` splits a word cell into gates). Rule used: `born-joined`
= never separable at any snapshot; a unit first separable at S_j, j > 1, has status `late`, and
its first loss after S_j counts as a loss with the column `late = 1`. Tables give the totals and the
totals without late units; the numeric rules use the totals.
