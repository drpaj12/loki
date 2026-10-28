# Hypothesis register: Loki III paper (loki.tex, rounds 0 to 6, HAL comparison, LLM pilot)

Step 1 of the restructure (brief `papers-hypothesis-register.md`, 2026-10-28). Register only: the .tex is untouched, no new experiment, every number is copied from a committed file named in the row. Written against origin/main ae709e4 (loki #56).

Verdict words (step 2, after Peter's decisions of 2026-10-28): USEFUL = supported under the round's own decision rule; POSSIBLY GOOD = supported but narrow or fragile (stated with the fragility in the main text, never proof of an innovation alone; decision 1; these were the FRAGILE rows of step 1 and L2b, whose evidence is one run on one split); DISMISSED = not supported (failed); INCONCLUSIVE = neither (power or rule limit stated; no threshold invented, decision 3). The framing column (PRE-REGISTERED, RECONSTRUCTED) is kept here for the record only; the paper does not argue it (decision 7).
Framing: PRE-REGISTERED = the rule text was committed before the round's numbers existed (commit cited with its time); RECONSTRUCTED = built from the round's stated aim (cited). Round 2 is NOT pre-registered (experiments/round2/EXPERIMENT.md:15-20: thresholds set by the implementer during the round; the file first appears in commit 38b6f66, 2026-10-24 19:00, after the scripts and CSVs).
Measures: Loki's purpose chain states the recovery questions are "understanding of what is recoverable, not area, speed or power" (docs/plan/hal-compare-prereg.md:11-13; experiments/round6 header); the metrics are precision, recall, F1 (micro/macro), calibration error (ECE), AST/CFG similarity, operator type-F1, modularity/NMI, functional pass rate. No area, speed or power is measured in any Loki round.

Source keys: `R2` = experiments/round2/EXPERIMENT.md, `R3` = experiments/round3/EXPERIMENT.md (commit `5f8de24`, 2026-10-24 21:26), `R4` = experiments/round4/EXPERIMENT.md (`c6c66bf`, 2026-10-25 03:12), `R5` = experiments/round5/EXPERIMENT.md (`ce02fa4`, 2026-10-25 15:54), `R6` = experiments/round6/EXPERIMENT.md (`6d0e5b5`, 2026-10-27 08:20), `HAL` = docs/plan/hal-compare-prereg.md (`363187f`, 2026-10-26 17:27) and docs/results-hal.md, `LLM` = experiments/llm-pilot/EXPERIMENT.md. Paper line refs are loki.tex; the generated `round*-log.tex` tables hold the same statuses.

## Rounds 0 and 1: build and first results (RECONSTRUCTED)

Framing for all rows in this block: RECONSTRUCTED from the question "how much structure does Loki recover without a language model?" (loki.tex:2269-2279, dated research log "Round 0", "Round 1") and each experiment's stated question; none of these experiments carries a decision rule, margin or test. Sources: experiments/rename-l2/EXPERIMENT.md:11-31, experiments/f3-recovery/EXPERIMENT.md:11-31, experiments/veval-l0/EXPERIMENT.md:11-24.

| H-ID | round / section | innovation tested | hypothesis (plain English) | framing | experiment | metrics | result | test, p / CI | verdict | main paper? |
|---|---|---|---|---|---|---|---|---|---|---|
| L0a | R1, loki.tex:227-232, 57-58 | Renamed-instance protocol (naming neutrality) | The pipeline uses no names: renaming every identifier changes nothing. | RECONSTRUCTED (rename-l2/EXPERIMENT.md:11) | 269 netlists, 105,646 identifiers, 476 L1 runs per variant pair, L2 | byte-identity of scores | all pairs byte-identical for L1 (204 + 204 + 68 sets); L2 clusters identical on 271 of 272 partitions (one spectral nondeterminism, also present on base) | digest equality | USEFUL | yes: the method export |
| L0b | R1, loki.tex:706-790 | L0 provenance answer key on VerilogEval | The provenance answer key reconstructs the reference at every floor with no recovery step. | RECONSTRUCTED (veval-l0/EXPERIMENT.md:11-24) | 156 references, 150 build on all floors | label, cell-type, HDL-span, module and signal coverage | 54,306 gate nodes all labelled; module coverage 1.000; signal coverage geomean 0.986; 6 of 156 not built | coverage ratios | USEFUL | yes |
| L1h | R1, loki.tex:788-800 | L1 hard-block detector | Structures the synthesis flow already reverse-engineered (hard adders and multipliers) are recovered almost perfectly. | RECONSTRUCTED (loki.tex:2274-2279) | micro suite f1, calibrated | precision, recall | hard adders 67/67 (P 0.985), hard multipliers 30/30 | none | USEFUL | yes |
| L1s | R1, loki.tex:788-806 | L1 soft-structure recovery | The Bayesian flow recovers the structures the flow erased. | RECONSTRUCTED (loki.tex:2274-2279) | f1 and f2, calibrated vs uncalibrated | macro-F1 | f1 0.354 (271 counted, 107 matched, 688 GT); f2 0.108 (91/19/686); uncalibrated f1 0.202, f2 0.075 | none | INCONCLUSIVE (weak, but no threshold or baseline was set) | yes (the honest limit) |
| L1c | R1, loki.tex:790-799 | Calibration | Calibration makes the predicted probabilities honest. | RECONSTRUCTED | f2 | ECE | calibrated 0.217 vs uncalibrated 0.650 | none | USEFUL | yes |
| F3 | R1, loki.tex:833-945 | Recovery from the cmos6 gate netlist (f3) | L1 recovers structure from Gate-Breaker's own gate input. | RECONSTRUCTED (f3-recovery/EXPERIMENT.md:11-16) | 15 f3 test designs, 144 GT instances | macro-F1 | 0 of 144 counted, 0 committed; buses proposed 2,569, none match | none | DISMISSED | yes (the f3 failure drives round 2 L1) |
| L2a | R1, loki.tex:946-960 | L2 clustering | Community methods find the designer's hierarchy; centroid methods do not. | RECONSTRUCTED | 68 designs, four clusterings | modularity, NMI | Louvain modularity 0.4220, NMI 0.1360; k-means and affinity propagation negative | none | USEFUL (clear gap, no test) | yes |
| L2b | R1, loki.tex:957-980 | L2 GNN with combined features | A GNN with node, graphlet, WL and NPN features beats the 1-WL baseline. | RECONSTRUCTED | 13 test designs, 3,932 test nodes | macro-F1, accuracy | 0.4241 vs 0.2717; accuracy 0.8863 vs 0.8492; node-only GNN loses (0.2413 vs 0.2711) | none | POSSIBLY GOOD (narrow: one run, one split of 13 test designs, no interval) | yes |

## Round 2 (NOT pre-registered)

Framing: the thresholds were set by the implementer during the round and the rule table first appears in commit 38b6f66 after the scripts and CSVs (R2:15-18); the paper says so (loki.tex:2263-2266). Labelled RECONSTRUCTED in effect. Results: R2:31-49, loki.tex:1033-1181, round2-log.tex:11-18.

| H-ID | round / section | innovation tested | hypothesis | framing | experiment | metrics | result | test, p / CI | verdict | main paper? |
|---|---|---|---|---|---|---|---|---|---|---|
| L1 | R2:22, loki.tex:1045-1068 | LUT6 re-map of the f3 netlist | The f3 failure is detector vocabulary, not missing information. | RECONSTRUCTED (rules not registered) | 65 designs in-sample, 15 held-out | micro-F1 ratio LUT6/f2 | 0.87 in-sample (14 vs 16 constructs of 580), 0.51 held-out (2 vs 4) | rule thresholds 0.8 / 0.5 | INCONCLUSIVE (too few matches on the held-out 15) | yes: the honest answer on f3 |
| L2 | R2:23, loki.tex:1092-1136 | Head-to-head with the language model | Loki's AST/CFG is below the LLM's on Q1/Q2 and does not fall Q1 to Q4, with output equal to input. | RECONSTRUCTED | 150 VerilogEval designs | AST, CFG, final equivalence | Loki AST 0.763/0.460 vs LLM 0.894/0.761 (Q1/Q2); AST falls Q1 to Q4 (0.754 ... 0.505); equivalence 150/150 | paired Wilcoxon, all differences significant | INCONCLUSIVE (below the LLM, but AST falls with complexity) | yes: positioning |
| L4 | R2:24, loki.tex:1137-1157 | Evidence families in the posterior | One or two evidence families carry the calibrated performance. | RECONSTRUCTED | 49 held-out designs | held-out micro-F1 | full 0.0038 vs priors-only 0.0051 (difference -0.0013; the gap is below the 0.02 floor) | rule | INCONCLUSIVE | no (log row) |
| L5a | R2:25, loki.tex:1158-1175 | Must/may bracket as uncertainty | Bracket width falls with per-design F1. | RECONSTRUCTED | uncalibrated VerilogEval f2 | Spearman | rho 0.087, p 0.417 (exploratory calibrated: -0.346, p 0.0008) | Spearman | DISMISSED | log row only |
| L5b | R2:26, loki.tex:1175-1181 | Structural prefilter before the prover | A cheap structural rule prunes >= 30% of prover calls with no lost proof. | RECONSTRUCTED | 210 cone_check calls | pruned share | best zero-loss rule prunes 0.067 | rule | DISMISSED | log row only |
| L7 | R2:27, loki.tex:1069-1091 | Operator type-F1 | Word-level operator F1 separates runs that AST and CFG tie on. | RECONSTRUCTED | tie pairs plus a flatten control | operator F1 vs AST/CFG | tie pair dF1 0.0173; flatten control moves AST by 0.0422, operator F1 unchanged | rule | POSSIBLY GOOD (fragile: small margins on few pairs; the calibrated flow recovers no operator) | yes: the one new instrument |

## Round 3 (why the detectors miss; pre-registered)

Framing: PRE-REGISTERED, `5f8de24` 2026-10-24 21:26, "before any round-3 number was computed" (R3:3-5, loki.tex:1193). Not blind to round-2 counts (loki.tex:1195-1197). Results: R3:169-197, round3-log.tex.

| H-ID | round / section | innovation tested | hypothesis | framing | experiment | metrics | result | test, p / CI | verdict | main paper? |
|---|---|---|---|---|---|---|---|---|---|---|
| H9a | R3:169, loki.tex:1200-1260 | Grouping of fragments | Most false candidates are fragments of a word of a related kind. | PRE-REGISTERED (5f8de24) | set P, four kinds, 2,615 false candidates | share of fragment_related | pooled 0.583 (1,525 of 2,615); without the largest design 0.415, without `ff_en` 0.304 (exploratory); noise class unreachable by construction | rule thresholds | POSSIBLY GOOD (fragile: fails leave-one-design-out and without the near-tautological ff_en slices) | yes, with the caveat |
| H9b | R3:176 | Word-first grouping | A word's fragments cover most of it, so grouping recovers it. | PRE-REGISTERED | 4 kinds, instances with >= 2 cells | share with coverage >= 0.8 | 0.065 (touched words only 0.069) | rule | DISMISSED | yes (it motivates word-first and shows grouping alone is not enough) |
| H10a | R3:186 | I/O-port propagation | Datapath words are reached from the I/O words within two hops. | PRE-REGISTERED | f2 both datasets, relaxed tau 0.75 | share reached at h <= 2 | 0.095 (per-design mean 0.326 exploratory) | rule | DISMISSED | log row only |
| H10b | R3:186 | same | Control words are not reached. | PRE-REGISTERED | as H10a | share | 0.605 (needs <= D - 0.20) | rule | DISMISSED (uninformative by construction once H10a fails) | log row only |
| L11 | R3:196 | FSM chain | (measurement, no hypothesis) 0.214 of muxes with a select are chain sinks; complete chains 5 of 89 on VerilogEval | measurement | | | | | MEASUREMENT (not counted) | yes (scope for the detector) |

## Round 4 (patterns from our data; pre-registered)

Framing: PRE-REGISTERED, `c6c66bf` 2026-10-25 03:12 (loki.tex:1349-1360); dictionary variants V1, V2 added after Stage 0 and before any dictionary result (entry 2026-10-25-a); exploratory checks of entry 2026-10-25-c do not change statuses. Results: R4 lines cited, round4-log.tex:11-20, loki.tex:1346-1513.

| H-ID | round / section | innovation tested | hypothesis | framing | experiment | metrics | result | test, p / CI | verdict | main paper? |
|---|---|---|---|---|---|---|---|---|---|---|
| H12a | R4:103 | Synthetic idiom corpus | The corpus builds on all floors (P_ok >= 0.95). | PRE-REGISTERED (c6c66bf) | 1,200 designs, 12 families | build success | P_ok 1.0000 (1200/1200), min family 100 | thresholds | USEFUL (a validity check) | yes (data method) |
| H12b | R4:158 | Signature dictionary | The dictionary beats the round-2 detectors on real designs. | PRE-REGISTERED (V1, V2 after Stage 0) | 7 eligible kinds, micros + 33 VerilogEval test designs, f2 | pooled F1, one-sided Wilcoxon | won on 0 of 7 kinds (V0, V1, V2) | Wilcoxon, margin 0.05 | DISMISSED | log row only |
| H12b2 | R4:158-196 | Dictionary generalisation | The dictionary generalises over unseen regions. | PRE-REGISTERED | corpus iid vs ood | ratio R | R 0.3288 (iid 0.1866, ood 0.0614) | rule | INCONCLUSIVE (iid below 0.20: ratio uninformative) | no |
| H12c | R4:197 | GNN scaling | GNN transfer to real designs improves with corpus size. | PRE-REGISTERED | 6 sizes, 33 VerilogEval designs | slope per doubling | -0.0026, CI [-0.0097, 0.0094], 29 designs | bootstrap CI | DISMISSED | yes (transfer failure) |
| H13a | R4:235 | Repetition in big designs | Big designs are mostly repeated structure. | PRE-REGISTERED | 6 big VTR designs | share repeated | 0.9283 (6,653 of 7,167) | threshold 0.50 | USEFUL | no (log row) |
| H13b | R4:239 | same | Big designs repeat more than small. | PRE-REGISTERED | big vs small | difference | 0.2404 (0.9283 vs 0.6879); flips with the small baseline (entry 2026-10-25-c) | threshold 0.15 | POSSIBLY GOOD (fragile: flips with the small baseline) | no |
| H13c | R4:242 | same | Repeated instances share the dictionary signature. | PRE-REGISTERED | 911 repeat groups | share identical | 0.8606 | threshold 0.70 | USEFUL | no |
| H14a | R4:270 | Identifiability | The flow destroys style information. | PRE-REGISTERED | twin sets | ceiling(f3) | 0.5000 (f2 0.4823, f1 0.4697) | <= 0.60 | USEFUL | yes (limit on what any recovery can do) |
| H14b | R4:274 | same | The coarser floor destroys more. | PRE-REGISTERED | f3 minus f2 ceiling | difference | 0.0177 | >= 0.05 / <= 0.00 | INCONCLUSIVE | no |
| H14c | R4:298 | MDL readability | The MDL score ranks references above recovered RTL. | PRE-REGISTERED | variants | share | l0-f2 0.860 ... f3-none 0.940 (rule not met) | rule | INCONCLUSIVE | no |
| H14d | R4:304 | same | The MDL score tracks round-2 similarity. | PRE-REGISTERED | 516 pairs | Spearman | rho -0.5110, partial 0.3029 | rule | INCONCLUSIVE | no |

## Round 5 (the word-first detector; pre-registered)

Framing: PRE-REGISTERED, `ce02fa4` 2026-10-25 15:54 (R5:157-217; loki.tex:1514-1600). Entries a to c disclose deviations (the relaxed FSM rule; null seeding) and label H16f degenerate; no status changed. Results: R5 `r5_status.csv`, round5-log.tex.

| H-ID | round / section | innovation tested | hypothesis | framing | experiment | metrics | result | test, p / CI | verdict | main paper? |
|---|---|---|---|---|---|---|---|---|---|---|
| H16a | R5:165 | Word-first detector, tiling | Word tiling beats the detectors on held-out real designs. | PRE-REGISTERED | VT set at f2 | tiling q | q_WB 0.023 vs baseline 0.022, null 0.203 | Wilcoxon p 1.0 | DISMISSED | yes (the detector does not tile) |
| H16b | R5:174 | Word grouping of enabled registers | Grouping recovers the enabled words (R +0.20, F1 +0.10). | PRE-REGISTERED | ff_en on E_all f2, 113 designs | recall, F1 | recall 0.008 to 0.146, F1 0.002 to 0.026, precision 0.014 | Wilcoxon p<0.001 | INCONCLUSIVE (recall +0.138, F1 +0.025: below the margins) | yes |
| H16c | R5:183 | Word-level eq_const | Word-level eq_const beats per-bit. | PRE-REGISTERED | 25 designs | F1 | dF1 -0.000 | p 1.0 | DISMISSED | log row |
| H16d | R5:190 | FSM chain | The chain is complete more often. | PRE-REGISTERED | 22 GT chains | chains complete | WB 3 vs R2N 1 | sign test p 0.25 | INCONCLUSIVE | log row |
| H16e | R5:199 | Growth from register words | Words grown from registers reach the datapath beyond a null. | PRE-REGISTERED | E_real f2 | seeded share D | D 0.829, null 0.715, gap 0.114 | rule | INCONCLUSIVE | no |
| H16f | R5:207 | Repetition as evidence on big designs | Repetition evidence raises F1 on big designs. | PRE-REGISTERED | 3+ big designs | dF1 | -0.0033; degenerate (margin unreachable, F1 bound 0.0165) | rule | DISMISSED (degenerate) | log row |

## Round 5b: the word-first detector against HAL's DANA (pre-registered)

| H-ID | round / section | innovation tested | hypothesis | framing | experiment | metrics | result | test, p / CI | verdict | main paper? |
|---|---|---|---|---|---|---|---|---|---|---|
| RQ-H1 | HAL:95-112, loki.tex:1721-1808 | Word-first detector vs an outside baseline | Loki's word-first detector recovers register words better than, equal to or worse than DANA. | PRE-REGISTERED (363187f, 2026-10-26 17:27; scorer fixed after Loki's round-5 counts were seen, before any DANA score, docs/results-hal.md:5-17) | E_real f2: 100 designs in both arms, 41 with a GT word, 24 non-zero pairs | pooled F1_J | Loki 0.169 vs HAL 0.261, D = -0.092, 95% CI [-0.317, 0.043] | Wilcoxon p(Loki greater) 0.8284 | INCONCLUSIVE (no difference shown) | yes |

## LLM pilot and quartiles

| H-ID | round / section | innovation tested | hypothesis | framing | experiment | metrics | result | test, p / CI | verdict | main paper? |
|---|---|---|---|---|---|---|---|---|---|---|
| LLM1 | LLM:1-56, loki.tex:1809-1932 | Loki hints for a model | A model given Loki's hints recovers RTL better than without. | PRE-REGISTERED by header (protocol "written 2026-10-26 before any standard or re call"; batch-1 calls preceded decisions 12-14; the history keeps the file only from squash commit 995fbe1, so the order is not verifiable from git) | 40 designs, 10 per quartile, K=1, claude-sonnet-5-5 | functional pass rate (strict scorer) | A 35/40, B 35/40; paired 38: A 33, B 35 (B vs A discordant 2/0) | exact McNemar p=0.5000 | INCONCLUSIVE (pilot; one draw; about 5 problems is noise) | yes (honest answer to the opening question) |
| LLM2 | same | Netlist vs memorisation control | The netlist helps beyond what the model knows from the interface line. | as LLM1 | arm C interface only | pass rate | C 30/40; paired A 33 vs C 29 | McNemar A vs C p=0.2188, B vs C p=0.0703 | INCONCLUSIVE | yes |
| Q1 | loki.tex:1933-2019 | Hints per complexity quartile | The hints help in some quartiles. | RECONSTRUCTED (purpose-page question L Q1.2 per quartile) | pilot cells 8 to 10 problems | pass rate | B ahead by one in Q2 and Q3, level in Q1, behind by two in Q4 | stratified exact McNemar = overall (p=0.5) | INCONCLUSIVE (power floor: min discordant) | no |
| Q2 | same | Loki alone by complexity | (measurement) what Loki alone recovers per quartile | measurement | 138 designs binned | ceiling, recall | see quartile tables | | MEASUREMENT (not counted) | yes |

## Round 6 (the L15 loss audit; pre-registered)

Framing: PRE-REGISTERED, `6d0e5b5` 2026-10-27 08:20 (R6:186-206; loki.tex:2020-2172); five dated entries and three post-data amendments (persistence null, inherited blend by descent, reporting) described at loki.tex:2323-2330; the persistence-null statuses are exploratory, post-data. Results: R6 `r6_status.csv`, loki.tex:2060-2172.

| H-ID | round / section | innovation tested | hypothesis | framing | experiment | metrics | result | test, p / CI | verdict | main paper? |
|---|---|---|---|---|---|---|---|---|---|---|
| L15a | R6:186-195 (rules 1, 2) | Loss audit with the D14 provenance map | Each construct kind is first lost at one dominant Odin III pass. | PRE-REGISTERED (6d0e5b5) | 1,436 units, 580 first losses (419 without 161 subsumed); passes proc..abc | share at the dominant pass | register, compare, mux, arithmetic `dominant` under the random-set null (opt 320, abc 166, flatten 68, second opt 26); under the persistence null (exploratory) `dominant-null` for all four (null shares 0.80, 0.84, 0.79, 0.46); only flatten of logic stays dominant | null counts | POSSIBLY GOOD (fragile: the persistence null says chance merging gives the same placement; the paper keeps only the descriptive statement) | yes with the caveat |
| L15c | R6:197-200 | Explained share | The D14 labels explain the merged losses. | PRE-REGISTERED | merged losses | explained share | 0.606 pooled "partly explained"; MI 0.978, CI 0.462, VT 0.459; opt 0.425, abc 0.821 | thresholds 0.50/0.90 | INCONCLUSIVE (partly explained is the middle class) | yes |
| L15d | R6:200-203 | Detector recall across a pass | A pass fools a detector. | PRE-REGISTERED | arms B, W, WB, S7 vs S8, kinds with GT >= 10 | recall change | mux word fooled by abc in all arms (WB 0.55 to 0.07, 174 instances); others at a floor | rule 4 | USEFUL for the mux word only (small n for FSM 24, counter 18) | yes |
| L15b | R6:20 | Partners and reason classes | (descriptive) which constructs are joined with which, why | measurement | | | | | MEASUREMENT (not counted) | yes |

## Untested hypotheses (decision 10: idea and the experiment it needs only)

| H-ID | idea | experiment it needs |
|---|---|---|
| L3 | A GNN trained on one suite transfers to the other suite. | Train on the micro designs, test on the VerilogEval designs and the reverse, with an interval over designs. |
| L6 | The graphlet counts differ from a motif null model. | Compare the ORCA graphlet counts of each netlist with degree-preserving random rewirings of the same graph. |
| L8 | A language model given Loki's ReverseProvenance record recovers RTL better than the model alone. | The Gate-Breaker task with a record arm and a no-record arm on the full quartile files, three draws per arm (deferred by Peter; the pilot of the LLM rows is the small first step). |

## Counts

45 register rows (grouped H-IDs count once; H12b covers V0, V1, V2), plus 3 untested hypotheses listed above.

| USEFUL | POSSIBLY GOOD | DISMISSED | INCONCLUSIVE | measurement, not a hypothesis | untested |
|---|---|---|---|---|---|
| 10 | 5 (L2b, L7, H9a, H13b, L15a) | 11 | 16 | 3 (L11, Q2, L15b) | 3 (L3, L6, L8) |

Rows that bear on a result for the paper's question: L0a, L0b, L1h, L1c, L2a (USEFUL), L2b (POSSIBLY GOOD); H12c, H16a, H9b, F3 (failures that drive later rounds); RQ-H1, LLM1, LLM2, L1, L2 (INCONCLUSIVE answers).
