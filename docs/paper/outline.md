# Main-paper outline: Loki III (step 2 applied 2026-10-28)

Order requested in the brief; step 2 follows it: Introduction (plain English, innovations with their confirming hypotheses), Background (Glossary in dependency order from terms.md, with the Jamieson 2007 and Luu 2014 theses), The innovations, Methodology (floors, benchmarks, metrics with the area/speed/power note, statistics), Experiments (Hypothesis / Experiment / Result / Verdict), Discussion and limits, Future work (untested L3, L6, L8), Conclusion, Appendix (research log, 48 rows from hypotheses.md). The pre-registration framing is not argued in the paper (decision 7). Loki's measures are recovery measures (precision, recall, F1, ECE, similarity, pass rate); none is area, speed or power (the purpose chain says so, hypotheses.md header). Paper text is not edited in this step.

## New structure

0. Abstract: plain-English problem, the innovations with their USEFUL hypotheses only, one sentence on what was dismissed.
1. Introduction: how much of a design can be recovered from its netlist without a language model (plain English); innovations 1 to 4 and 6 in plain English; contributions = innovations with USEFUL H-IDs (L0a, L0b, L1h, L1c, L2a, L2b, L7, L15d) and the INCONCLUSIVE answers that the paper's question needs (L1s, RQ-H1, LLM1).
2. Background (terms in dependency order, terms.md): netlist, gate, LUT, RTL, HDL, provenance, Odin III, answer key, Gate-Breaker, quartile, AST/CFG similarity.
3. The innovation (plain English, then technical): the L0 datasets and renamed-instance protocol; L1; L2; operator F1; the loss audit.
4. Methodology: floors; benchmarks (68 micro designs, 156 VerilogEval references, 150 on three floors); metrics (precision, recall, micro/macro F1, ECE, modularity, NMI, AST/CFG, operator F1, pass rate); statistics (Wilcoxon, exact McNemar, bootstrap, null models); the pre-registration record (round 3 to 6, HAL, LLM pilot by header) versus reconstructed (rounds 0 to 2); the data: the L0 datasets with the answer key (Mimir not used by Loki today).
5. Experiments, one subsection per USEFUL or INCONCLUSIVE hypothesis kept:
   - 5.1 Is the pipeline naming neutral (L0a), what the answer key covers (L0b).
   - 5.2 What the flow already reverse-engineered (L1h, L1c) and what it erased (L1s INCONCLUSIVE, F3 DISMISSED, L1 round 2 INCONCLUSIVE).
   - 5.3 Graph analysis (L2a, L2b).
   - 5.4 A metric that sees recovery (L7) and where the model is better (L2 INCONCLUSIVE).
   - 5.5 Why the detectors miss (H9a fragile, H9b DISMISSED as the motive for word-first); word-first (H16 rows INCONCLUSIVE/DISMISSED, RQ-H1 INCONCLUSIVE).
   - 5.6 Where synthesis loses constructs (L15a fragile, L15c, L15d).
   - 5.7 Language model plus hints (LLM1, LLM2, Q1 INCONCLUSIVE).
6. Discussion and limits: no language model step; structural not functional recovery; the two determinism defects (rename script, spectral); round 2 not pre-registered; fragile statuses (H9a, H13b, L15a); the LLM pilot is a pilot.
7. Conclusion.
Appendix A: research log, every hypothesis including DISMISSED, one row each (hypotheses.md); the dated thought-pattern entries (loki.tex:2258-2396) stay here.

## Mapping of the current paper

| current location | content | new place | action |
|---|---|---|---|
| loki.tex:46-76 abstract | Gate-Breaker context, round summaries | Abstract | rewrite |
| loki.tex:81-108 Introduction | question and three contributions | Introduction | rewrite around innovations |
| loki.tex:110-150 Background | provenance, Gate-Breaker, DANA/HAL | Background | keep, add terms in dependency order; HAL to 5.5 |
| loki.tex:152-210 floors | floor table | Methodology | keep |
| loki.tex:211-233 L0 | datasets, renamed instances | 3 and 4 | keep |
| loki.tex:234-370 L1 | Bayesian flow | 3 | keep; shorten constants |
| loki.tex:371-416 L2 | graph analysis | 3 | keep |
| loki.tex:417-578 evaluation protocol, one design through the pipeline | metrics | 4 | keep |
| loki.tex:579-702 VerilogEval and its structure | benchmark | 4 | keep, shrink feature matrix |
| loki.tex:703-980 Results rounds 0-1 | L0, L1, f3, L2 | 5.1 to 5.3 | keep (F3 and L1s as limits) |
| loki.tex:982-1032 Gate-Breaker metrics | replication | 5.4 | shrink |
| loki.tex:1033-1181 round 2 | L1 LUT6, L2 head-to-head, L4, L5, L7 | 5.2, 5.4 and Appendix A | L7 and L2 kept; L4, L5a, L5b to log rows |
| loki.tex:1182-1345 round 3 | H9, H10, L11 | 5.5 and Appendix A | H9b kept as motive, H9a with FRAGILE flag; H10a/b to log rows |
| loki.tex:1346-1513 round 4 | corpus, dictionary, GNN scaling, big designs, identifiability | 5.5 and Appendix A | H12a, H14a kept as limits; H12b, H12b2, H12c, H13, H14b-d to log rows |
| loki.tex:1514-1720 round 5 | word-first | 5.5 | keep as the main negative; H16c-f log rows |
| loki.tex:1721-1808 round 5b HAL | DANA comparison | 5.5 | keep |
| loki.tex:1809-1932 LLM pilot, 1933-2019 quartiles | pilot | 5.7 | shrink to one subsection |
| loki.tex:2020-2172 round 6 | loss audit | 5.6 | keep descriptive statements; Stage-0 null table to appendix |
| loki.tex:2173-2257 Discussion/Conclusion | | 6, 7 | rewrite |
| loki.tex:2258-2396 Research log | | Appendix A | keep verbatim |
| round*-tables.tex, hal-tables.tex, veval-tables.tex, quartile-tables.tex | generated tables | with the matching subsection | keep |

## Provenance as the enabler

Loki's recovery questions are posed against the Odin III provenance answer key: every L0 label, cell type, HDL span, module scope and signal name comes from the link that Odin III keeps through elaboration, optimisation, mapping and ABC. Without it there is no ground truth for precision, recall, the renamed-instance proof, the loss audit (version 2 name map) or the clusters-against-hierarchy score. Mímir is not used by Loki today; a Mímir run would let the same keys be queried across designs.
