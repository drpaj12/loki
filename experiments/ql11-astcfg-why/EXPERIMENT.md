# Q-L11: AST/CFG for every LLM arm, and why higher-level structure is not recovered (plan, 2026-11-03)

Branch exp/ql11-astcfg on loki main fa542d6 (after #82, Q-L10). Plan written before any scoring or analysis run of this
lane; no model call is made at any point. A later change is a dated entry under "Amendments"; the old text stays.

## Peter's words (2026-11-03)

"have AST/CFG all the way so we can say that Loki approach with LLM agent is better than Gatebreaker alone, but for the
deeper part of the question have some understanding of or hypothesis, why we can't recover higher level structures - Note
too that these experiements are from 3 end points (k=6, k=4, and gates) three points instead of 1 for gatebreaker (so the k
ones are bigger reverse engineerings)".

Purpose: Loki reverse engineering of structural netlists. RQ: L, Q-L10 continued, Q-L4 (why structure is missed).
Measures: functional pass@1 and Gate-Breaker's two similarity measures (AST, CFG), per endpoint; right-block share per
structure kind and endpoint.

## Part A: AST and CFG for every LLM arm

1. Inventory of every experiment with model replies (arms, endpoints, problems, draws), from the committed results and
   the archived run data. Read only.
2. One scorer. The three AST/CFG wrappers (`ql10-blocks/q10_astcfg.py`, `f3-recovery/tools/astcfg.py`,
   `round2/l2_astcfg.py` with `metrics_ext.py`) are run on one shared sample and compared value by value. One is chosen and
   every arm is re-scored with it; the reasons are written in the results.
3. Paired comparison per endpoint and per arm pair against arm A (Gate-Breaker whole-netlist prompting): pass@1, AST, CFG,
   each with W/L/T and a seeded bootstrap 95 percent CI over problems (seed 20261103, 2000 resamples). Both writers: "as
   written" (raw) and flattened through the same Odin III writer on both sides (the headline, as in Q-L10).
   Labels per the CAD reporting convention: headline geomean-style gain first, then the strict label; a CI touching zero is
   INCONCLUSIVE, not DISMISSED.
4. Endpoint framing: Gate-Breaker reports one endpoint (gates); Loki runs three (gates, k4, k6). Size per endpoint (cells,
   nets, mean LUT input count, provenance constructs per cell) from the structural benchmark of Q-L4 to Q-L10.

Limit stated in advance: every LLM experiment (llm-pilot, llm-full, llm-hints2, ql10-blocks) was run on the Gate-Breaker
gate netlists only. If the replies for k4 and k6 do not exist, the paired comparison at k4 and k6 cannot be made without
new model calls; this lane makes none and gives the call count and token estimate for the controller.

## Part B: why higher-level structure is not recovered

1. Gather the existing misses (Q-L4 census, Q-L5 distances, Q-L6 to Q-L9 right-block data, Q-L10 block checks): per
   structure kind and endpoint, recovered, partly (a block touches it, none is right), missed (no block touches it).
2. Locate the loss: (i) provenance mixing (one cell carries logic of more than one HDL construct), (ii) partition cut
   wrongly (SPLIT, BLOATED, UNDERREACH, NOSEED of Q-L9), (iii) wrong kind label, (iv) wrong LLM decode of a right block,
   (v) assembly.
3. 3 to 5 ranked plain-English hypotheses, each with its measure. One question at a time: the strongest is tested with
   existing data only, with a CI.

## Amendments
