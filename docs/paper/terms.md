# Terms for the Loki III paper (Background and Methodology order)

Ordered so that every term depends only on terms above it. `defined at` is the position (file:line of the .tex files) where the paper explains the term now (`none`: the paper never defines it); `first used at` is where the term first occurs outside the abstract; `search` is the regular expression the checker uses.
Check with `python3 docs/paper/check_terms.py --tex docs/paper/loki.tex` (the abstract is exempt).
Generated 2026-10-28 against origin/main ae709e4.
| term | definition | defined at | first used at | depends on | search |
|---|---|---|---|---|---|
| netlist | A list of the gates (or LUTs) of a design and the wires between them. | none | loki.tex:84 | - | `\bnetlists?\b` |
| gate | A basic logic element (AND, OR, NOT) of the cmos6 gate library. | none | loki.tex:84 | netlist | `\bgates?\b` |
| LUT | Look-up table: a small memory that implements any logic function of K inputs (K = 6 here). | none | loki.tex:173 | netlist | `\bLUT6?s?\b` |
| RTL | Register-transfer level: the Verilog text that says what registers hold and how they change. | none | loki.tex:86 | - | `\bRTL\b` |
| HDL | Hardware description language: the Verilog source a designer writes. | none | loki.tex:117 | RTL | `\bHDL\b` |
| provenance | The link from each netlist object back to the HDL that produced it. | loki.tex:117 | loki.tex:94 | HDL; netlist | `provenance` |
| Odin III | The provenance-tracked synthesis front end under Loki; it keeps the link in one IR. | loki.tex:118 | loki.tex:118 | provenance | `Odin~?III` |
| answer key / ground truth | What the synthesis tool kept about which objects form which HDL construct; the target the recovery is scored against. | loki.tex:121 | loki.tex:94 | provenance | `answer key\|ground.truth` |
| L0 / L1 / L2 | Loki's three layers: L0 labelled datasets, L1 a Bayesian hypothesis flow, L2 graph analysis. | loki.tex:94 | loki.tex:94 | answer key / ground truth | `\bL0\b\|\bL1\b\|\bL2\b` |
| Gate-Breaker | The earlier study in which a language model rewrites gate netlists into RTL; Loki's method baseline. | loki.tex:84 | loki.tex:84 | netlist; RTL | `Gate-Breaker` |
| quartile (complexity) | One quarter of the benchmark designs ordered by Gate-Breaker's construct-count complexity score. | loki.tex:599 | loki.tex:88 | Gate-Breaker | `quartile` |
| AST / CFG similarity | How alike two Verilog texts are by subtree overlap (AST) and control-flow-graph kernel (CFG). | loki.tex:128 | loki.tex:128 | RTL | `\bAST\b\|\bCFG\b` |
| micro designs | The 68 small synthesizable designs (counters, registers, ALUs, muxes, FSMs) used as the first benchmark. | loki.tex:214 | loki.tex:214 | RTL | `micro (suite\|designs?)\|micro-` |
| VerilogEval references | The 156 reference designs of the VerilogEval spec-to-RTL set; the second benchmark. | loki.tex:216 | loki.tex:86 | RTL | `VerilogEval` |
| floor | The abstraction level and technology mapping at which a design is cut and written as the netlist to reconstruct (f1-k6, f1-earch, f2, f3). | loki.tex:158 | loki.tex:152 | netlist; LUT; gate | `\bfloors?\b\|\bf1-\|\bf2\b\|\bf3\b` |
| renamed-instance protocol | Rename every identifier through a shared permutation, run the pipeline, map back: proves the pipeline does not use names. | loki.tex:227 | loki.tex:104 | floor | `renamed` |
| hypothesis (structure claim) | A claim that a set of cells is a structure of some kind (register, adder, mux, FSM, ...). | loki.tex:246 | loki.tex:95 | netlist | `hypothes[ei]s` |
| detector | A plug-in that proposes hypotheses and reports bin-label features, never a likelihood. | loki.tex:252 | loki.tex:95 | hypothesis (structure claim) | `detectors?` |
| calibration | Fitting priors and likelihood ratios on a training split so that predicted probabilities match observed rates. | loki.tex:275 | loki.tex:106 | detector | `calibrat` |
| ECE | Expected calibration error: average gap between predicted probability and observed match rate over ten bins. | loki.tex:288 | loki.tex:288 | calibration | `\bECE\b` |
| prover | An engine (cone check, truth table, transfer) that proves a claim equal to the netlist; a proof makes the claim near certain. | loki.tex:300 | loki.tex:95 | hypothesis (structure claim) | `prover\|proof` |
| must/may bracket | Proved-and-committed cells (must) versus cells that candidates also cover (may). | loki.tex:1158 | round2-tables.tex:246 | prover | `must/may\|bracket` |
| count / match (scoring) | A hypothesis counts when committed or at p >= 0.5; it matches a ground-truth instance by overlap rule. | loki.tex:478 | loki.tex:277 | hypothesis (structure claim); answer key / ground truth | `\bcounts\b\|\bmatche[sd]` |
| precision / recall / F1 | Share of counted hypotheses that match; share of ground-truth instances matched; their harmonic mean. | none | loki.tex:106 | count / match (scoring) | `precision\|recall\|\bF1\b` |
| macro-F1 / micro-F1 | F1 averaged over kinds (macro) or pooled over all instances (micro). | none | loki.tex:411 | precision / recall / F1 | `macro-F1\|micro-F1` |
| Louvain / modularity / NMI | Community detection; a score of cluster density; a score of agreement with the known module hierarchy. | loki.tex:392 | loki.tex:392 | netlist; answer key / ground truth | `Louvain\|modularity\|\bNMI\b` |
| GNN and 1-WL baseline | A graph neural network, and the colour-refinement baseline that a message-passing GNN cannot beat in distinguishing power. | loki.tex:408 | loki.tex:107 | netlist | `\bGNN\|1-WL` |
| operator type-F1 | F1 of recovered word-level operator types (adder, mux, comparator...) against the ground-truth operators. | loki.tex:1070 | round2-tables.tex:170 | precision / recall / F1 | `operator (type-)?F1` |
| word | A group of cells that act as one multi-bit signal (a register, a datapath operator, a bus). | none | loki.tex:142 | netlist | `\bwords?\b` |
| fragment | A wrong-looking candidate that is in fact part of a real construct. | none | loki.tex:1182 | word; detector | `fragment` |
| word-first detector | A detector that first groups flip-flops into register words by shared clock, enable and reset, then builds the rest around them. | loki.tex:1524 | loki.tex:146 | word; detector | `word-first\|wordfirst` |
| pre-registration / Stage-0 rules | Decision rules committed to the repository before the numbers were computed; Stage 0 is the first committed text. | loki.tex:1193 | loki.tex:1193 | - | `pre-registered\|committed before\|committed first\|Stage.0` |
| McNemar / Wilcoxon test | Exact paired test on discordant pairs; paired rank test. | none | loki.tex:1103 | - | `McNemar\|Wilcoxon` |
| synthetic corpus | A seeded generator's 1200 labelled idiom designs (twelve families) with train, iid and ood splits. | loki.tex:1366 | round4-tables.tex:296 | floor | `synthetic corpus\|\bcorpus\b` |
| signature dictionary | A table from a cell's cone class and WL colour to the construct it usually is, mined from the corpus. | loki.tex:1386 | round4-tables.tex:322 | synthetic corpus | `dictionary` |
| D14 provenance map / unit | Odin III's name map (version 2): per object, the statement-level units it blends and the labelled join records. | loki.tex:2031 | loki.tex:1706 | provenance | `D14\|name map\|prov-map` |
| unit, separable, lost | A unit is the statement-level anchor of a construct; separable while some object has exactly that unit set; lost at the first later snapshot where none has. | loki.tex:2039 | round6-tables.tex:77 | D14 provenance map / unit | `separable\|unit set\|statement-level` |
| persistence null | A null that merges random objects of the previous snapshot until the real object count is reached. | loki.tex:2052 | round6-tables.tex:77 | unit, separable, lost | `persistence null\|Stage-0 null` |
| LLM pilot arms A, B, C | A: gate netlist; B: netlist plus Loki hints; C: interface line only (memorisation control). | loki.tex:1824 | loki.tex:1824 | Gate-Breaker | `\barms?~?[ABC]\b` |
