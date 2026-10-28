# Main-paper outline: Loki III (as written, fix round of 2026-10-28)

This file describes `loki.tex` as it stands. The paper has no pre-registration record: a hypothesis is stated, the experiment confirms it or not, and the verdict is one of USEFUL, POSSIBLY GOOD, INCONCLUSIVE, DISMISSED (a MEASUREMENT row has no hypothesis and no verdict). The register is `hypotheses.md`; the appendix table `register.tex` is generated from it by `make_register.py`.

Counts (51 register rows): 8 USEFUL (L0a, L0b, L1h, L1c, H12a, H13a, H13c, H14a), 6 POSSIBLY GOOD (L2b, R2-L7, H9a, H13b, L15a, L15d), 12 DISMISSED, 16 INCONCLUSIVE, 6 MEASUREMENT (L11, L15b, L2m, GB1, GB2, Q2), 3 untested (L3, L6, L8). Round-2 hypothesis IDs carry the prefix R2- so that they do not collide with the layer names L1 and L2.

## Structure of the paper

0. Abstract (about 195 words, four short paragraphs): the problem, the verdict counts, the confirmed results, the candidate innovations and the negative answers.
1. Introduction: the problem in plain English (HDL, RTL, gate, netlist, provenance, answer key); the hypothesis and verdict words; the three confirmed innovations with the hypotheses that confirmed them (1. L0a, L0b; 2. L1h, L1c; 3. H14a, H12a, H13a, H13c); a paragraph of candidate innovations that have only POSSIBLY GOOD support (graph network L2b, operator F1 R2-L7, loss audit L15a/L15d), each with the experiment that would confirm it; the negative and undecided answers; the area, speed and power note (not measured; Mimir would store the answer key); the suite tree (full-page figure).
2. Background: Glossary (from `terms.md`, dependency order, Jamieson 2007 and Luu 2014 theses), the provenance problem and Odin III, Gate-Breaker as the method baseline, HAL and DANA as a second baseline.
3. The innovations (plain English in the Introduction, technical here): floors, L0, L1 (confirmed); L2, operator type-F1 and the loss audit (candidates).
4. Methodology: evaluation protocol, one design through the pipeline, metrics and statistics, the VerilogEval benchmark (complexity score, quartiles, feature matrix, sizes).
5. Experiments, one subsection per kept hypothesis (Hypothesis / Experiment / Result / Verdict):
   - Naming neutrality and the answer key (L0a, L0b, USEFUL).
   - L1 (L1h, L1c USEFUL; L1s INCONCLUSIVE; F3 DISMISSED with the f3 similarity probe, detail in Appendix B; R2-L1 INCONCLUSIVE).
   - L2 (L2a DISMISSED: NMI against the module path ranks the centroid methods above the community methods; L2m modularity MEASUREMENT; L2b POSSIBLY GOOD).
   - An instrument that sees recovery, and the language model (R2-L7 POSSIBLY GOOD, R2-L2 INCONCLUSIVE).
   - Why the detectors miss (H9a POSSIBLY GOOD, H9b DISMISSED).
   - The word-first detector and DANA (H16 rows, RQ-H1 INCONCLUSIVE).
   - The loss audit (L15a POSSIBLY GOOD, L15c INCONCLUSIVE, L15d POSSIBLY GOOD).
   - What is recoverable in principle (H14a USEFUL); the idiom corpus (H12a USEFUL); repetition in big designs (H13a, H13c USEFUL, H13b POSSIBLY GOOD).
   - The Gate-Breaker replication (GB1, GB2 MEASUREMENT: the baseline the model rows compare against).
   - The language-model pilot (LLM1, LLM2 INCONCLUSIVE) and the per-quartile results (Q1 INCONCLUSIVE, Q2 MEASUREMENT).
6. Discussion and limits: four observations, the candidate innovations with the experiment each needs, five limits.
7. Future work: the untested hypotheses L3, L6, L8 (idea and the experiment it needs).
8. Conclusion.
Appendix A: research log (every hypothesis, one row each, with the committed source of the numbers named by round) and the dated order of the work. Appendix B: the f3 experiment in detail (per-kind table and the per-quartile AST/CFG table).

## Where the step-1 content went

| step-1 content | place now |
|---|---|
| Round 0 and 1 results | Experiments: naming neutrality, L1, L2 |
| Round 2 (R2-L1, R2-L2, R2-L7) | Experiments; R2-L4, R2-L5a, R2-L5b are log rows |
| Round 3 (H9a, H9b, L11) | Experiments (fragments and words); H10a, H10b log rows |
| Round 4 | Experiments: H14a, H12a, H13a to H13c each have a subsection; H12b, H12b2, H12c, H14b to H14d log rows |
| Round 5 and 5b | Experiments: word-first detector and DANA |
| Round 6 | Experiments: loss audit |
| Gate-Breaker replication | Experiments (GB1, GB2), no longer in Methodology |
| LLM pilot, quartiles | Experiments |
| generated tables | `gen/tab-*.tex` (one per table, from `split_tables.py`), `veval-tables.tex`, `quartile-tables.tex` |

## Provenance as the enabler

Loki's recovery questions are posed against the Odin III provenance answer key: every L0 label, cell type, HDL span, module scope and signal name comes from the link that Odin III keeps through elaboration, optimisation, mapping and ABC. Without it there is no ground truth for precision, recall, the renamed-instance proof, the loss audit (version 2 name map) or the clusters-against-hierarchy score. Mimir is not used by Loki today; a Mimir run would let the same keys be queried across designs.
