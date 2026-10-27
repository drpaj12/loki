# Loki word-first detector vs HAL/DANA: pre-registration

Written 2026-10-26, before HAL is built and before any HAL run on any evaluation design. This file
is committed and pushed first; its commit SHA is the pre-registration SHA quoted in the paper. A
later change is a dated entry in "Rule additions" at the end that keeps the old rule; the paper
reports both. Feasibility and sources: `docs/plan/hal-feasibility.md`. Round-5 protocol this extends:
`experiments/round5/EXPERIMENT.md`.

Purpose chain (hub `docs/purpose.md`): Loki **L Q2.4** (can words, control nets and FSMs be found
first) and L Q1.1. Measure: word recovery (precision, recall, purity) against the L0 provenance
ground truth, same designs, same metric code for both tools. This is understanding of what is
recoverable, not area, speed or power.

Tools credited: HAL (Embedded Security Group, MIT licence, tag v4.5.0, commit e7fea566b51e) and
its dataflow plugin, which implements DANA (Albartus, Hoffmann, Temme, Azriel, Paar, TCHES 2020(4),
309-336, doi 10.46586/tches.v2020.i4.309-336). Bib entries: feasibility doc section 5. Nothing of
HAL is vendored; the repo carries our gate-library files, converter and scorer only.

## Question

RQ-H1: on the netlists Loki's word-first detector was evaluated on, does DANA (grouping
flip-flops by shared control nets and by common predecessors and successors, designed for
gate-level cell libraries) recover the L0 register words better than, equal to, or worse than
Loki's word-first detector (which groups by shared clock, enable and reset and joins plain
flip-flops through D-driver and Q-reader words)?

## Inputs

| set | designs | floors | notes |
|---|---|---|---|
| MI | the micro dataset (68 designs at f2, 65 at f3) | f2 (headline), f3 | as round 5 |
| VT | the 33 VerilogEval held-out designs (manifest split test) | f2 (headline), f3 | as round 5 |
| BIG | the 13 round-4 big designs with an ok f2 floor | f2 only | smallest first; 1800 s per run |

E_real = MI + VT, the headline set, as in round 5. The corpus sets CI and CO (synthetic) are not
part of this comparison. Netlist floors: f2 = LUT6 floor, converted to `lut6.hgl` instances; f3 =
cmos6 gate floor (BUF INV NAND2 NOR2 DFF DFFSR), converted to `cmos6.hgl` instances. Floor names
follow the L0 spec (f2 LUT, f3 cmos6). Both tools read the same `netlist.blif` of the floor; HAL
through `loki.hal.blif2hal`. Designs that the converter rejects (for example `.subckt` hard
blocks such as `micro_multiply_hard_block` at f2) or that HAL fails to load are dropped from both
arms and counted per set and floor.

Development data for the converter and the gate libraries: hand-written fixtures and the round-4
corpus train split (loading and function checks only, no scoring). The micro, VerilogEval and BIG
designs are used before the HAL run only for the converter's function round trip (BLIF versus
iverilog, no HAL, no word scoring). No HAL group is scored on any E_real or BIG design before this
file is pushed.

## Ground truth

Same L0 answer key as round 5 (`words.json`, `graph.json`). FF = node of kind `ff` in `graph.json`.
GT word = an L0 storage word (`loki.score.gt.STORAGE`: `$dff`, `$dffe`, `$adff`, `$adffe`, `$sdff`,
`$sdffe`, `$sdffce`, `$dffsr`, `$dffsre`, `$aldff`, `$aldffe`, `$dlatch`, `$adlatch`, `$dlatchsr`)
with a footprint that holds at least 2 FFs; its bit set is footprint intersected with FFs. A
design with no such word contributes nothing to the recall side and its predicted groups count
only on the precision side (they are then wrong by definition). FFs of GT words of width 1 count
as label carriers for purity (a group that joins them is impure), but those words are not scored for
recall.

## Predictions

- **HAL**: `dataflow.analyze` groups (Python route) or `groups.txt` rows (CLI route); each group is
  the set of gate (instance) names, which the converter keeps equal to the L0 node ids. Groups of
  at least 2 FFs are words. Two DANA settings, fixed here: **A** = the tool default of
  `min_group_size` as built (the value is read from the built plugin and recorded, not chosen by
  us); **B** = `min_group_size` 2. No `--sizes`, no `bad_group_size`, other options default, no
  hint derived from the answer key. Headline HAL arm = the setting with the higher pooled F1_J on
  E_real at f2 (conservative for the comparison: the choice favours HAL); both are reported.
- **Loki**: the round-5 `W` arm (`--detectors wordfirst`, existing runs under
  `work/loki-exp5-data/runs/W-<set>-<floor>`, not rerun): counted candidates (`Pred.counted(0.5)`)
  of kind `register`, cells intersected with FFs, at least 2 FFs. The round-5 `WB` arm is reported
  as a second row. No Loki rerun and no change to the detector.

## Metrics (one code path: `loki.hal.wordscore`, used for both tools)

Per design, then summed (micro-pooled) over a set; per-design values for the paired test. P =
predicted words, G = GT words.

- **Exact precision / recall**: the share of P whose FF set equals a GT word's FF set; the share of
  G exactly equalled by some P.
- **Matched precision / recall / F1_J** (headline): one-to-one greedy matching by Jaccard >= 0.5
  (`loki.score.match.match_greedy`, the matching of round-5 `construct_scores` for the kind
  `register`); precision = matched / |P|, recall = matched / |G|, F1 = 2 matched / (|P| + |G|).
  A cross-check asserts that Loki's matched count equals `construct_scores` for kind `register`
  whenever the GT instances are the derived `register` instances (test, not a result).
- **Purity**: sum over P of the largest overlap of a group with one GT word (any width, label =
  GT word id), over the sum of |group|. Unlabelled FFs count as impure.
- **Completeness** (inverse purity): sum over G of the largest overlap with one P group, over the
  sum of |word|.
- **FF coverage**: the share of FFs in GT words (>= 2 bits) that lie in some P group.
- **Descriptive only**: number of groups, HAL clock/enable/reset/set net counts per group, run
  time. Control-net recovery is not scored here: `words.json` carries no control-net answer key.
  FSMs are not found by DANA and are not scored in this comparison.

## Decision rule

Statistic: one-sided paired Wilcoxon signed-rank (`scipy.stats.wilcoxon`, zero differences
dropped, alpha 0.05) on per-design F1_i = 2 matched_i / (|P_i| + |G_i|) over the designs of E_real
at f2 with at least one GT word and one converted/loaded netlist in both arms; fewer than 8
non-zero paired differences makes the outcome `inconclusive`. Let D = pooled F1_J(Loki W) minus
pooled F1_J(HAL headline arm) on E_real at f2.

- **Loki ahead**: D >= 0.05 and Wilcoxon (Loki greater) p < 0.05.
- **HAL ahead**: D <= -0.05 and Wilcoxon (HAL greater) p < 0.05.
- **Comparable**: |D| < 0.05.
- Otherwise **inconclusive**.

Purity and completeness are reported with the same two arms and are not part of the rule. f3 (HAL on
cmos6 gates versus Loki f3), BIG (per design, smallest first, no test) and the per-set split MI /
VT are reported, not decided. Reachability: E_real holds on the order of 100 GT words of at least
2 FFs in MI and several hundred in VT, so 0.05 is a handful of words in MI and tens in VT; all four
outcomes are reachable.

## Stop rules

- A converted netlist that HAL rejects: the parser error is recorded; the design is dropped from
  both arms. If more than 20 percent of the designs of a set at a floor are dropped, stop, report
  the cause and do not score that set/floor.
- HAL run time limit 900 s per design (BIG 1800 s). A timeout drops the design from both arms and
  is listed.
- HAL needs a source change, or the library description cannot express a floor cell: stop and
  report; do not patch HAL.
- Any change of the converter or the `.hgl` files after the first HAL run on an E_real design is a
  dated "Rule additions" entry; results are then reported under both versions.
- No tuning of DANA options on E_real or BIG. The two settings above are the only ones.

## What is NOT done

No LLM call, no Loki rerun, no heavy lock for the prep (the HAL build and the sweeps take the lock
later), no change to Odin III, VTR or Loki detector code, no use of `hal-benchmarks`.

## Rule additions

(none)

## Amendment 1 (2026-10-26, before any run)

Written before any HAL run and before any word score of any HAL group; the original text above is
unchanged and where an item here conflicts with it, this amendment rules. Review of commit
ca4cbace; findings are numbered as in `loki-hal-fix1`. The pre-registration SHA above stays the
anchor; this amendment has its own SHA, quoted in the paper beside it.

**A1. The shared scorer is not the round-5 scorer; each difference is now stated.** (finding 1)
`loki.hal.wordscore` (comparison scorer) and the round-5 scorer (`construct_scores`, kind
register, `loki.score.metrics`) differ in four places:

| # | comparison scorer | round-5 scorer | reason for the comparison scorer |
|---|---|---|---|
| 1 | predicted sets deduplicated (a repeated set counts once) | a repeated set is a further false positive | DANA groups are a partition and cannot repeat; Loki repeats come from overlapping hypotheses. Dedup flatters Loki, so see the rule below |
| 2 | Loki cells cut to flip-flops; GT footprint cut to flip-flops | cells and footprints are full node sets | HAL/DANA groups can only hold the gates it was given as flip-flops; both tools on FF sets is the common ground |
| 3 | GT word = storage word with WIDTH >= 2 and >= 2 FFs after the cut | WIDTH >= 2 only | see correction below |
| 4 | prediction ids `p<i>` over lexicographically sorted sets | hypothesis ids, natural order | HAL groups have no Loki ids; ties in Jaccard are the only place it matters |

Correction to the original "Ground truth" paragraph: it said a GT word is a storage word "with a
footprint that holds at least two FFs". Read literally that counts WIDTH-1 words, because two
WIDTH-1 `$dff` can share one footprint (`micro_bm_DL_2_cascaded_flip_flops`: two WIDTH-1 words,
both with footprint {n4, n5}): MI f2 would hold 159 GT words instead of 94. A scored GT word is
a storage word with WIDTH >= 2 whose footprint cut to FFs still holds >= 2 FFs; WIDTH-1 words
stay purity labels only, as the original paragraph's second half already said. Code:
`wordscore.gt_words` (the `scored` flag).

Measured effect of each difference on Loki's own counts, round-5 W runs, kind register, sum over
designs (`tests/test_hal_score.py::RealDataTest`, run with `LOKI_MICRO`, `LOKI_VEVAL`,
`LOKI_R5_DATA` set; the test also asserts that the scorer in round-5 mode, `round5=True`, no
dedup, no cut, reproduces `construct_scores` on every design). P = predicted words, M = matched,
G = GT words.

| run | round 5 (P / M / G) | comparison (P / M / G) | dedup only (P / M) | FF cut only (P / M) |
|---|---|---|---|---|
| W-MI-f2 (68) | 136 / 25 / 94 | 120 / 30 / 94 | 136 / 25 | 136 / 26 |
| W-MI-f3 (65) | 48 / 4 / 94 | 42 / 20 / 94 | 48 / 4 | 48 / 4 |
| W-VT-f2 (33) | 150 / 9 / 146 | 148 / 13 / 146 | 150 / 9 | 150 / 6 |
| W-VT-f3 (33) | 19 / 6 / 146 | 19 / 14 / 146 | 19 / 6 | 19 / 0 |

("dedup only" and "FF cut only" change that one thing against round 5, GT as round 5; the FF cut
of the GT footprint is what moves f3, where footprints hold the gates of the word's logic.)

Rules for reporting: Loki's round-5-scorer numbers (`wordscore.round5_register`, CLI
`--round5`) are printed beside the comparison numbers in every table. The "Loki ahead" outcome
below must also hold with Loki's round-5-scorer counts in place of its comparison counts (HAL
counts unchanged); if it holds only under the comparison scorer the outcome is `inconclusive`.
"HAL ahead" and "comparable" need no such condition (the round-5 counts can only lower Loki).

**A2. Decision statistic (finding 2).** Per-design F1_i has heavy ties (many 0 and 1) and the MI
designs are template families, so a paired test over designs is not enough alone. Added: a
design-level bootstrap CI of D = pooled F1_J(Loki W) - pooled F1_J(HAL headline arm) on E_real
at f2: resample clusters with replacement, 10000 resamples, `random.Random(20261026)`, a cluster
is one VT design or one MI family (MI family = the first two `_` tokens of the design name after
`micro_`, digits removed, lower case), recompute the pooled counts and D per resample, percentile
interval. The Wilcoxon call is pinned: `scipy.stats.wilcoxon(x, y, zero_method="wilcox",
alternative=..., method="approx", correction=False)` (approx because ties rule out the exact
distribution); scipy is not in the base install and is added to the driver environment.
**Loki ahead** = D >= 0.05 and the 95 percent bootstrap CI lies entirely above +0.05 and the
Wilcoxon (Loki greater) p < 0.05 and the A1 round-5 condition. **HAL ahead** = mirror image
(CI entirely below -0.05, Wilcoxon HAL greater).

**A3. "Comparable" needs evidence (finding 3).** |D| < 0.05 alone no longer gives
**comparable**. Comparable = the 90 percent bootstrap CI of D lies inside (-0.05, 0.05) (an
equivalence test at alpha 0.05, TOST in effect). |D| < 0.05 with a wider CI is `inconclusive`,
reported as "no difference shown".

**A4. DANA arms (finding 4).** The best-of-two choice on E_real is dropped: it selected the
analysis setting on the test data. The headline HAL arm is the **library default**
`min_group_size` 8 (`dataflow_analysis/api/configuration.h:77`), fixed now. Setting B
(`min_group_size` 2) is a sensitivity run reported beside it, never the headline. What the
parameter does (read in the HAL clone, v4.5.0): `--bad_group_size` sets `min_group_size`; in
`evaluation.cpp` (lines 109-216) groups smaller than it are "bad": they rank below larger groups
when overlapping candidate groups are chosen and are replaced by a larger group that contains a
gate when one exists (a penalty), and `pre_processing.cpp:96` uses it only to skip user-supplied
known net groups (none are given). It is not a filter that removes small groups, so setting 2 is
not "report small groups too"; it removes the penalty. `plugin_dataflow.cpp:98` parses it.

**A5. Threat to validity: f2 flip-flop pins (finding 5).** The f2 `FF` of `lut6.hgl` has a
clock and a data pin only: the L0 f2 netlist carries enable and reset in the LUT feeding D, so
DANA loses the EN/R/S control-net evidence it uses at gate level. This is kept as pre-registered
(f2 stays the headline floor, as in round 5) and is a threat to validity: a HAL result on f2 is
a result for a LUT-mapped netlist without control pins, not for HAL on a netlist with enable
and reset flip-flops. To make the effect visible, **f3 (cmos6, DFFSR with set and reset pins) is
reported beside f2 in the headline table** (same columns, same two tools), still without a rule.
The paper says that f2 is the more favourable floor for Loki and f3 for DANA.

**A6. Ordering leakage (finding 7).** L0 node ids (`n<k>`) come from one counter, so instance
names and instance order in the converted Verilog carry the L0 construction order, which DANA
could exploit through HAL's id order. Plan step before the E_real HAL run: on 6 designs (the
smallest 5 of E_real with a GT word and the median-size one) convert twice more with instance
names replaced by a seeded random permutation of the names and the instance lines shuffled
(`random.Random(7)`, mapping kept for scoring), run DANA, map names back, and compare the group
partitions. Any difference is reported and the permuted version is then also run on all of E_real
and reported beside the headline.

**A7. DANA determinism (finding 8).** `dataflow.cpp:48` sets `num_threads` to
`hardware_concurrency()`, so the grouping may depend on thread timing. Plan step before the
E_real run: run the smallest 5 designs of E_real at f2 twice and diff the sorted group
partitions. A difference is reported and then every design is run twice, the partitions are
compared, and the first run is the scored one. No thread option is assumed to exist.

**A8. Round trip scope (finding 9).** The original "Development data" paragraph uses MI/VT/BIG
designs for the function round trip; only the micros were run so far. Added driver step before
the first HAL run on a set: `python -m loki.hal.sim --floor <f> --probe ffq <netlist.blif>
--workdir <empty dir>` for every VT and BIG design (BIG at `--probe out` if the BLIF simulator
is too slow), 256 cycles; a design that fails is dropped from both arms and listed. The micro test
reads the micro dataset from `$LOKI_MICRO` and skips when it is unset.

**A9. Converter checks (findings 6, 11, 12, 13).** `tests/test_hal_convert.py` now compares every
FF Q net and every gate output per cycle (`probe="all"`), 256 cycles, seeds 1, 2, 3, with a
4-cycle init phase (inputs all 0, then all 1); the simulation library is hand-written, so the
round trip checks the converter and that the `.hgl` files agree with it, not the libraries or
HAL. A model of HAL's LUT `bit_order` rule (gate.cpp) shows `lut6.hgl` had `ascending`, which
bit-reverses INIT and disagrees with the converter; it is now `descending` (the HAL parser
`hgl_parser.cpp:588` maps the string to `init_ascending`). Unverified until a HAL build loads
the files; DANA itself does not read LUT functions. `.latch` init 2 and 3 emit no INIT (the
README note); instance names must differ from net and port names; a flip-flop without `.cname`
makes `convert` raise, and the design is dropped from both arms.

Changes in this amendment alter the converter and `lut6.hgl` before any HAL run on any design, so
they are not "Rule additions" in the sense of the Stop rules.

## Amendment 2 (2026-10-26, after the HAL build and the load checks, before any E_real HAL run)

Written after HAL v4.5.0 (commit e7fea566b51e, fresh shallow clone of the tag) was built and run on
hand-written fixtures and on 60 corpus-train designs (30 at f2, 30 at f3; loading and parsing
checks only, no word scoring), and before any HAL run on an MI, VT or BIG design. The earlier text
stays; where an item conflicts with it, this amendment rules. No pre-registered rule (metrics,
decision, DANA settings 8 and 2, stop rules) is changed.

**B1. DANA is driven through HAL's Python API, not its `--dataflow` command line.** At the tag,
`CliExtensionDataflow::handle_cli_call` (`plugins/dataflow_analysis/src/plugin_dataflow.cpp`,
lines 60-110) builds a `Configuration` without gate types or control pin types and never writes a
result; running `hal -i x.v -gl lib.hgl --dataflow --path out/` on a fixture ends with
`dataflow analysis failed: no gate types specified` (`src/api/dataflow.cpp:21`). The feasibility
note and A4 had read the later `master` clone, whose handler sets
`with_gate_types({GateTypeProperty::ff})` and the four control pin types. The comparison therefore
uses the route the pre-registration already allows ("Python route"): `hal --python-script
experiments/hal/dana_run.py` with `dataflow.Configuration(nl).with_flip_flops()
.with_min_group_size(N)`, `dataflow.analyze`, `Result.write_txt` (`groups.txt`, the format that
`loki.hal.dana` reads). `with_flip_flops()` is the documented default configuration (all
flip-flop gate types; clock, enable, set, reset as control pins) and equals what the `master`
command line sets. Stage identification and type consistency stay at their defaults (off,
`configuration.h:107,112`). Nothing else is set; HAL is not patched. A4's source line numbers
refer to the `master` clone; at the tag the same statements are at `configuration.h:77`
(`min_group_size = 8`), `evaluation.cpp:47,109-216`, `pre_processing.cpp:96`,
`plugin_dataflow.cpp:95`, and `dataflow.cpp:35` (`num_threads = hardware_concurrency()`, A7).

**B2. `lut6.hgl` bit order verified in a real HAL load.** A9 left the `descending` setting
unverified. `experiments/hal/lut_tt.py` (run inside HAL) evaluates every LUT gate's Boolean
function as HAL parsed it and `run_hal.py lutcheck` compares it with the BLIF cover: all MI and VT
f2 designs that convert (100 designs), 9,915 LUTs with a name, 0 mismatches. DANA does not read
LUT functions; the check shows the library file means what the converter intends.

**B3. Load checks passed; the f3 flip-flop with set and reset is not in the evaluation sets.**
The 60 corpus-train designs load with both libraries, `groups.txt` parses with `loki.hal.dana`
(`tests/test_hal_score.py`, real files in `tests/data/hal/`), and every gate name in a group is a
flip-flop node of the design. No MI or VT f3 netlist contains a `DFFSR` (searched; BIG has no f3 floor), so
the f3 control pins used are the clock only; a two-flip-flop `DFFSR` fixture loads and DANA reports
the set and reset nets, so the library is correct where it is not exercised. This weakens the
A5 argument that f3 gives DANA its enable/reset evidence: f3 gates carry enable and reset in
the logic, as f2 does. The paper says so.

**B4. BIG: the 20 percent stop rule applies.** The A8 round trip (BLIF versus iverilog, 256 cycles)
passes for all 33 VT designs at both floors and for the 6 BIG designs whose f2 netlist converts.
Seven of the 13 BIG designs contain a `.subckt single_port_ram` or `dual_port_ram` hard block, which
neither `.hgl` library can express (a stop rule: the library cannot express a cell of the floor):
mkPktMerge, spree, boundtop, mkSMAdapter4B, mkDelayWorker32B, raygentop, or1200. That is 54 percent
dropped, above the 20 percent limit, so BIG f2 is **not scored**. HAL is still run on the 6
convertible BIG designs for run time and group counts only (descriptive, no precision, recall or
F1), and the table says so.

**B5. Project metadata.** Run with `--volatile-mode --no-log`; the netlist is loaded in the script
with `NetlistFactory.load_netlist`, so HAL creates no project directory.
