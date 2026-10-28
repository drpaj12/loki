# Innovations of the Loki III paper

Plain English first, then the technical paragraph, then the H-IDs (hypotheses.md) whose USEFUL verdict proves the value, then what is still unproven. Round-1 claims (L0a, L0b, L1h, L1c, L2a, L2b) carry no registered rule; they are USEFUL by their numbers only.

## 1. Provenance-labelled, anonymised netlist datasets with a renamed-instance protocol

Plain English. To test a reverse-engineering tool we need netlists where we know the right answer and where the tool cannot cheat by reading names. We build the netlists from Verilog with a front end that remembers which source text made each gate, hide every name, and show the tool gives the same answer on renamed copies.
Technical. L0: Odin III writes floors f1-k6, f1-earch, f2, f3 with an answer key (label, cell type, HDL span, module and signal names); the renamed-instance protocol permutes every identifier (105,646 across 269 netlists), reruns L1 and L2 and inverse-maps the tokens (loki.tex:211-233).
Proves its value: L0a (naming neutral: 476 byte-identical L1 run pairs; the protocol also exposed a rename-script defect and a spectral nondeterminism), L0b (answer key covers 54,306 gate nodes, module coverage 1.000).
Still unproven: nothing about recovery quality; this is a method contribution.

## 2. L1: a Bayesian hypothesis flow with calibration and proofs

Plain English. The tool proposes "this group of gates is an adder / a register with enable / a mux", gives each a probability learned from training designs, and uses an equivalence proof to settle the ones it can.
Technical. Nine detector plugins propose hypotheses; priors and log-likelihood ratios fitted on the training split; provers (cone check, truth table, transfer) set odds to near certainty; commit at p_comp >= 0.9 (loki.tex:234-370).
Proves its value: L1h (already-reverse-engineered hard blocks: adders 67/67, multipliers 30/30), L1c (ECE 0.217 calibrated vs 0.650).
Still unproven: recovery of erased structure (L1s INCONCLUSIVE: macro-F1 0.354 at f1, 0.108 at f2; F3 DISMISSED: nothing on the gate netlist; L4 evidence families add nothing; L5a, L5b DISMISSED).

## 3. L2: graph analysis (clusters and a GNN)

Plain English. Treat the netlist as a graph: find communities that match the designer's modules, and train a small graph network to label each gate's role.
Technical. Louvain, spectral, k-means and affinity propagation scored by modularity and NMI against the known hierarchy; GraphSAGE with node, graphlet (ORCA), WL and NPN features against a 1-WL colour-refinement baseline (loki.tex:371-416).
Proves its value: L2a (Louvain modularity 0.4220, NMI 0.1360; centroid methods negative), L2b (macro-F1 0.4241 against 0.2717 for 1-WL, 3,932 test nodes).
Still unproven: any interval or second split (single run); transfer from synthetic to real designs (H12c DISMISSED).

## 4. Operator-recovery F1 (a metric that sees recovery)

Plain English. Comparing recovered Verilog to a reference by text similarity cannot tell whether the tool found the right adders. This metric counts the right operator types recovered.
Technical. Word-level operator type-F1 against the L0 key's word cells, reported beside AST and CFG similarity (loki.tex:1066-1092).
Proves its value: L7 (USEFUL by the letter of the rule, weak evidence: tie pair dF1 0.0173, flatten control moves AST by 0.0422, operator F1 unchanged).
Still unproven: robustness (few pairs).

## 5. Word-first detection

Plain English. Registers and buses are the clues: find the multi-bit signals first, then work out what the logic around them does.
Technical. `wordfirst` and `wordgroup` detectors group flip-flops by shared clock, enable and reset, and join plain flip-flops through D-driver and Q-reader words (loki.tex:1514-1600).
Proves its value: none. H9a (fragments exist; fragile) and H9b (fragments do not tile words, 0.065) motivated it; H16a DISMISSED (q 0.023 vs 0.022), H16c DISMISSED, H16b INCONCLUSIVE (recall 0.008 to 0.146), RQ-H1 INCONCLUSIVE against DANA (D -0.092, CI [-0.317, 0.043]).
Still unproven: a detector that tiles words; chain completion (H16d).

## 6. Loss audit (L15): where Odin III stops holding a construct as a unit

Plain English. When synthesis merges the logic of two source statements, the construct is no longer separable. We record which pass merged what, using the provenance map the front end already keeps.
Technical. Version 2 name map (`--prov-map`) read after each of the pass snapshots proc, fsm, opt, flatten, opt -full, wreduce, lower, abc; unit separable/lost; Stage-0 and persistence nulls (loki.tex:2020-2172).
Proves its value: L15d (the mux word is the one kind that abc fools: recall 0.55 to 0.07 on 174 instances), L15a (descriptive: a compare is no longer separable after the first opt, 18 of 19; FRAGILE as a "dominant pass" claim).
Still unproven: whether opt is special (chance merging gives the same placement), FSM re-encoding (not observable), big designs.

## 7. Synthetic idiom corpus and signature dictionary

Plain English. Generate many small labelled designs of known idioms to learn patterns from, then check the patterns on real designs.
Technical. 1,200 designs from twelve families with train, iid and ood splits; a dictionary keyed by cone class and WL colour (loki.tex:1346-1420).
Proves its value: H12a (the corpus builds: 1200/1200). H12b (0 of 7 kinds), H12c (slope -0.0026 per doubling) show the patterns did not transfer.
Still unproven: any transfer.

## 8. Identifiability and repetition (what is recoverable in principle)

Plain English. How much of the designer's coding style survives synthesis at all, and do big designs repeat enough to give free evidence?
Technical. Twin sets (different RTL, same netlist) give a style-recovery ceiling; MDL readability; repeat groups in big VTR designs.
Proves its value: H14a (ceiling at f3 0.5000, so at least 40% of style variants are indistinguishable), H13a, H13c (repetition 0.9283; identical signatures 0.8606).
Still unproven: H13b is fragile; H14b-d INCONCLUSIVE.

## 9. LLM hints pilot (Loki plus a model)

Plain English. Does giving a language model Loki's structural findings help it write the RTL?
Technical. 40 VerilogEval problems, three arms (netlist, netlist + hints, interface only), one draw each, strict scorer on Icarus Verilog (loki.tex:1809-1932).
Proves its value: none (LLM1 p=0.5000, LLM2 B vs C p=0.0703).
Still unproven: any effect of the hints; the pilot cannot support one.
