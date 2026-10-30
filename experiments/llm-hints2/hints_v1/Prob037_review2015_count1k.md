Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 897d40f2715a, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| adder | 0 | 0 | 1 |
| bus | 2 | 41 | 0 |
| eq_const | 18 | 3 | 0 |
| ff_srst | 0 | 26 | 0 |

Input cells (in Loki's re-mapped netlist): 72.

Of the committed cells, 7 (in 2 claims) are marked only by attributes on existing cells (form attrs). Those claims are not modules, so the hierarchy below does not show them.

Recovered module hierarchy (a module contains its children):

- h41 eq_const_h41 (eq_const)
- h58 eq_const_h58 (eq_const)
  - h18 eq_const_h18 (eq_const)
  - h56 eq_const_h56 (eq_const)
    - h49 eq_const_h49 (eq_const)
- h59 eq_const_h59 (eq_const)
- h246 eq_const_h246 (eq_const)
- h288 eq_const_h288 (eq_const)
  - h284 eq_const_h284 (eq_const)
    - h283 eq_const_h283 (eq_const)
    - h287 eq_const_h287 (eq_const)
    - h387 eq_const_h387 (eq_const)
- h345 eq_const_h345 (eq_const)
- h346 eq_const_h346 (eq_const)
- h347 eq_const_h347 (eq_const)
- h384 eq_const_h384 (eq_const)
- h385 eq_const_h385 (eq_const)
- h386 eq_const_h386 (eq_const)

## 4. Committed claims

- h41: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, q[0]. Outputs: Y = nets _000_. Recovered as module eq_const_h41, instance eq_const_h41_i. Role: datapath.
- h58: 14 cells form a comparison against a constant, `Y = (A != 999)`. Proved equivalent by truth table. Confidence 0.9967. Inputs: A = nets q[0], q[1], q[2], q[3], q[4], q[5], q[6], q[7], q[8], q[9]. Outputs: Y = nets w11. Recovered as module eq_const_h58, instance eq_const_h58_i. Role: datapath. Conflicts with 7 more not listed.
- h18: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[3], q[4]. Outputs: Y = nets w4. Recovered as module eq_const_h18, instance eq_const_h18_i. Role: datapath.
- h56: 3 cells form a comparison against a constant, `Y = (A == 7)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[0], q[1], q[2]. Outputs: Y = nets _021_. Recovered as module eq_const_h56, instance eq_const_h56_i. Role: datapath.
- h49: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[0], q[1]. Outputs: Y = nets _020_. Recovered as module eq_const_h49, instance eq_const_h49_i. Role: datapath.
- h59: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[0], q[1]. Outputs: Y = nets _031_. Recovered as module eq_const_h59, instance eq_const_h59_i. Role: datapath.
- h246: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _020_, _012_. Outputs: Y = nets _033_. Recovered as module eq_const_h246, instance eq_const_h246_i. Role: datapath.
- h288: 11 cells form a comparison against a constant, `Y = (A != 7)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[3], q[4], _021_, _014_, _013_. Outputs: Y = nets w15. Recovered as module eq_const_h288, instance eq_const_h288_i. Role: datapath.
- h284: 10 cells form a comparison against a constant, `Y = (A == 7)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[3], q[4], _021_, _014_, _013_. Outputs: Y = nets _047_. Recovered as module eq_const_h284, instance eq_const_h284_i. Role: datapath.
- h283: 8 cells form a comparison against a constant, `Y = (A == 7)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[3], q[4], _021_, _013_. Outputs: Y = nets _043_. Recovered as module eq_const_h283, instance eq_const_h283_i. Role: datapath.
- h287: 9 cells form a comparison against a constant, `Y = (A != 7)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[3], q[4], _021_, _013_. Outputs: Y = nets _044_. Recovered as module eq_const_h287, instance eq_const_h287_i. Role: datapath.
- h387: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _014_, _044_. Outputs: Y = nets _047_. Recovered as module eq_const_h387, instance eq_const_h387_i. Role: datapath.
- h345: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _022_, _016_. Outputs: Y = nets w1. Recovered as module eq_const_h345, instance eq_const_h345_i. Role: datapath.
- h346: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _037_, _017_. Outputs: Y = nets w13. Recovered as module eq_const_h346, instance eq_const_h346_i. Role: datapath.
- h347: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _013_, _041_. Outputs: Y = nets _045_. Recovered as module eq_const_h347, instance eq_const_h347_i. Role: datapath.
- h384: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _037_, w1. Outputs: Y = nets w2. Recovered as module eq_const_h384, instance eq_const_h384_i. Role: datapath.
- h385: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _041_, w13. Outputs: Y = nets w14. Recovered as module eq_const_h385, instance eq_const_h385_i. Role: datapath.
- h386: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _014_, _044_. Outputs: Y = nets _049_. Recovered as module eq_const_h386, instance eq_const_h386_i. Role: datapath.
- h66: 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.9002. Inputs: ctrl = nets _018_; slice0 = nets _032_; slice1 = nets _034_; slice2 = nets w12. Role: datapath.
- h70: 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.9818. Inputs: ctrl = nets _030_; slice0 = nets _046_; slice1 = nets _050_; slice2 = nets _054_; slice3 = nets _059_. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h11 (unconfirmed): 4 bits, bit order from wf: bit 0 = _016_; bit 1 = _013_; bit 2 = w7; bit 3 = _018_.
- h12 (unconfirmed): 3 bits, bit order from wf: bit 0 = _016_; bit 1 = _017_; bit 2 = _010_.
- h13 (unconfirmed): 3 bits, bit order from wf: bit 0 = w1; bit 1 = w13; bit 2 = _061_.
- h14 (unconfirmed): 3 bits, bit order from wf: bit 0 = w1; bit 1 = _045_; bit 2 = _052_.
- h15 (unconfirmed): 4 bits, bit order from wf: bit 0 = _013_; bit 1 = _014_; bit 2 = w7; bit 3 = w6.
- h16 (unconfirmed): 4 bits, bit order from wf: bit 0 = _017_; bit 1 = _014_; bit 2 = w6; bit 3 = _010_.
- h20 (unconfirmed): 4 bits, bit order from wf: bit 0 = w13; bit 1 = _049_; bit 2 = _058_; bit 3 = _061_.
- h21 (unconfirmed): 4 bits, bit order from wf: bit 0 = _045_; bit 1 = _049_; bit 2 = _052_; bit 3 = _058_.
- h66: 3 bits, bit order from net_id: bit 0 = _032_; bit 1 = _034_; bit 2 = w12.
- h68 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w9; bit 1 = w17.
- h69 (unconfirmed): 3 bits, bit order from net_id: bit 0 = _003_; bit 1 = _004_; bit 2 = _009_.
- h70: 4 bits, bit order from net_id: bit 0 = _046_; bit 1 = _050_; bit 2 = _054_; bit 3 = _059_.
- h148 (unconfirmed): 5 bits, bit order from wf: bit 0 = _012_; bit 1 = _017_; bit 2 = _014_; bit 3 = w6; bit 4 = _018_.
- h150 (unconfirmed): 4 bits, bit order from wf: bit 0 = _012_; bit 1 = _016_; bit 2 = _013_; bit 3 = w7.
- h151 (unconfirmed): 4 bits, bit order from wf: bit 0 = _033_; bit 1 = w1; bit 2 = _045_; bit 3 = _052_.
- h152 (unconfirmed): 4 bits, bit order from wf: bit 0 = _033_; bit 1 = w13; bit 2 = _049_; bit 3 = _058_.
- h153 (unconfirmed): 4 bits, bit order from wf: bit 0 = _034_; bit 1 = _050_; bit 2 = _059_; bit 3 = w17.
- h154 (unconfirmed): 3 bits, bit order from wf: bit 0 = _002_; bit 1 = _006_; bit 2 = _008_.
- h155 (unconfirmed): 4 bits, bit order from wf: bit 0 = _016_; bit 1 = _013_; bit 2 = w7; bit 3 = _010_.
- h156 (unconfirmed): 4 bits, bit order from wf: bit 0 = w1; bit 1 = _045_; bit 2 = _052_; bit 3 = _061_.
- h157 (unconfirmed): 3 bits, bit order from wf: bit 0 = _017_; bit 1 = _014_; bit 2 = w6.
- h158 (unconfirmed): 3 bits, bit order from wf: bit 0 = w13; bit 1 = _049_; bit 2 = _058_.
- h238 (unconfirmed): 5 bits, bit order from wf: bit 0 = _016_; bit 1 = _017_; bit 2 = _014_; bit 3 = w6; bit 4 = _018_.
- h239 (unconfirmed): 2 bits, bit order from wf: bit 0 = _033_; bit 1 = w11.
- h240 (unconfirmed): 2 bits, bit order from wf: bit 0 = _034_; bit 1 = w12.
- h242 (unconfirmed): 4 bits, bit order from wf: bit 0 = _022_; bit 1 = _013_; bit 2 = w7; bit 3 = _010_.
- h243 (unconfirmed): 3 bits, bit order from wf: bit 0 = _016_; bit 1 = _013_; bit 2 = w7.
- h244 (unconfirmed): 4 bits, bit order from wf: bit 0 = w1; bit 1 = w13; bit 2 = _049_; bit 3 = _058_.
- h245 (unconfirmed): 3 bits, bit order from wf: bit 0 = _050_; bit 1 = _059_; bit 2 = w17.
- h263 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _032_; bit 1 = _033_.
- h269 (unconfirmed): 4 bits, bit order from wf: bit 0 = _016_; bit 1 = _017_; bit 2 = _018_; bit 3 = _010_.
- h270 (unconfirmed): 4 bits, bit order from wf: bit 0 = _002_; bit 1 = _043_; bit 2 = _053_; bit 3 = _056_.
- h271 (unconfirmed): 4 bits, bit order from wf: bit 0 = _045_; bit 1 = w12; bit 2 = _052_; bit 3 = _058_.
- h272 (unconfirmed): 3 bits, bit order from wf: bit 0 = _046_; bit 1 = _054_; bit 2 = _059_.
- h273 (unconfirmed): 3 bits, bit order from wf: bit 0 = _005_; bit 1 = _007_; bit 2 = _008_.
- h274 (unconfirmed): 3 bits, bit order from wf: bit 0 = _044_; bit 1 = w16; bit 2 = _055_.
- h342 (unconfirmed): 2 bits, bit order from wf: bit 0 = w1; bit 1 = w12.
- h343 (unconfirmed): 2 bits, bit order from wf: bit 0 = w13; bit 1 = w12.
- h344 (unconfirmed): 3 bits, bit order from wf: bit 0 = _052_; bit 1 = w12; bit 2 = _058_.
- h356 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w2; bit 1 = w13.
- h357 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _045_; bit 1 = w14.
- h367 (unconfirmed): 2 bits, bit order from wf: bit 0 = w2; bit 1 = w12.
- h368 (unconfirmed): 2 bits, bit order from wf: bit 0 = w12; bit 1 = w14.

State machines: none.

Roles of committed claims: datapath: h18, h41, h49, h56, h58, h59, h66, h70, h246, h283, h284, h287, h288, h345, h346, h347, h384, h385, h386, h387.

## 6. Candidates (not committed, unconfirmed)

- h285 (unconfirmed): 12 cells form a comparison against a constant, `Y = (A == 7)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[3], q[4], _021_, _014_, _013_, w7. Outputs: Y = nets _053_. Role: datapath.
- h286 (unconfirmed): 14 cells form a comparison against a constant, `Y = (A == 7)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[3], q[4], _021_, _014_, _013_, w6, w7. Outputs: Y = nets _056_. Role: datapath.
- h289 (unconfirmed): 13 cells form a comparison against a constant, `Y = (A != 7)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[3], q[4], _021_, _014_, _013_, w7. Outputs: Y = nets w16. Role: datapath.
- h32 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9002. Inputs: d = nets _005_; rst = nets _030_. Outputs: q = nets q[5]. Role: datapath.
- h34 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9002. Inputs: d = nets _006_; rst = nets _030_. Outputs: q = nets q[6]. Role: datapath.
- h36 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9002. Inputs: d = nets _007_; rst = nets _030_. Outputs: q = nets q[7]. Role: datapath.
- h38 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9002. Inputs: d = nets _008_; rst = nets _030_. Outputs: q = nets q[8]. Role: datapath.
- h377 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9002. Inputs: d = nets _005_; rst = nets _030_. Outputs: q = nets q[5]. Role: datapath.
- h406 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9002. Inputs: d = nets _006_; rst = nets _030_. Outputs: q = nets q[6]. Role: datapath.
- h148 (unconfirmed): 5 cells form a 5-bit bus, `bus: 5 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _012_; slice1 = nets _017_; slice2 = nets _014_; slice3 = nets w6; slice4 = nets _018_. Role: datapath.
- h238 (unconfirmed): 5 cells form a 5-bit bus, `bus: 5 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _016_; slice1 = nets _017_; slice2 = nets _014_; slice3 = nets w6; slice4 = nets _018_. Role: datapath.
- h11 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _016_; slice1 = nets _013_; slice2 = nets w7; slice3 = nets _018_. Role: datapath.
- h12 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _016_; slice1 = nets _017_; slice2 = nets _010_. Role: datapath.
- h13 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets w1; slice1 = nets w13; slice2 = nets _061_. Role: datapath.
- h14 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets w1; slice1 = nets _045_; slice2 = nets _052_. Role: datapath.
- h15 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _013_; slice1 = nets _014_; slice2 = nets w7; slice3 = nets w6. Role: datapath.
- h16 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _017_; slice1 = nets _014_; slice2 = nets w6; slice3 = nets _010_. Role: datapath.
- h20 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets w13; slice1 = nets _049_; slice2 = nets _058_; slice3 = nets _061_. Role: datapath.
- h21 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _045_; slice1 = nets _049_; slice2 = nets _052_; slice3 = nets _058_. Role: datapath.
- h24 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _001_; rst = nets _018_. Outputs: q = nets q[1]. Role: datapath.
- h25 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _002_; rst = nets _018_. Outputs: q = nets q[2]. Role: datapath.
- h28 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _003_; rst = nets w12. Outputs: q = nets q[3]. Role: datapath.
- h30 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _004_; rst = nets w12. Outputs: q = nets q[4]. Role: datapath.
- h40 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _009_; rst = nets w12. Outputs: q = nets q[9]. Role: datapath.
- h150 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _012_; slice1 = nets _016_; slice2 = nets _013_; slice3 = nets w7. Role: datapath.
- h151 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _033_; slice1 = nets w1; slice2 = nets _045_; slice3 = nets _052_. Role: datapath.
- h152 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _033_; slice1 = nets w13; slice2 = nets _049_; slice3 = nets _058_. Role: datapath.
- h153 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _034_; slice1 = nets _050_; slice2 = nets _059_; slice3 = nets w17. Role: datapath.
- h154 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _002_; slice1 = nets _006_; slice2 = nets _008_. Role: datapath.
- h155 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _016_; slice1 = nets _013_; slice2 = nets w7; slice3 = nets _010_. Role: datapath.
- h156 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets w1; slice1 = nets _045_; slice2 = nets _052_; slice3 = nets _061_. Role: datapath.
- h157 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _017_; slice1 = nets _014_; slice2 = nets w6. Role: datapath.
- h158 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets w13; slice1 = nets _049_; slice2 = nets _058_. Role: datapath.
- h160 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _001_; rst = nets _018_. Outputs: q = nets q[1]. Role: datapath.
- h242 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _022_; slice1 = nets _013_; slice2 = nets w7; slice3 = nets _010_. Role: datapath.
- h243 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _016_; slice1 = nets _013_; slice2 = nets w7. Role: datapath.
- h244 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets w1; slice1 = nets w13; slice2 = nets _049_; slice3 = nets _058_. Role: datapath.
- h245 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _050_; slice1 = nets _059_; slice2 = nets w17. Role: datapath.
- h269 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _016_; slice1 = nets _017_; slice2 = nets _018_; slice3 = nets _010_. Role: datapath.
- h270 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _002_; slice1 = nets _043_; slice2 = nets _053_; slice3 = nets _056_. Role: datapath.
- h271 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _045_; slice1 = nets w12; slice2 = nets _052_; slice3 = nets _058_. Role: datapath.
- h272 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _046_; slice1 = nets _054_; slice2 = nets _059_. Role: datapath.
- h273 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _005_; slice1 = nets _007_; slice2 = nets _008_. Role: datapath.
- h274 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _044_; slice1 = nets w16; slice2 = nets _055_. Role: datapath.
- h275 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _002_; rst = nets _018_. Outputs: q = nets q[2]. Role: datapath.
- h344 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _052_; slice1 = nets w12; slice2 = nets _058_. Role: datapath.
- h371 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _003_; rst = nets w12. Outputs: q = nets q[3]. Role: datapath.
- h374 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _004_; rst = nets w12. Outputs: q = nets q[4]. Role: datapath.
- h402 (unconfirmed): 2 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _003_; rst = nets w12. Outputs: q = nets q[3]. Role: datapath.
- h403 (unconfirmed): 2 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _004_; rst = nets w12. Outputs: q = nets q[4]. Role: datapath.
- h263 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6942. Inputs: ctrl = nets _020_; slice0 = nets _032_; slice1 = nets _033_. Role: datapath.
- h69 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.6011. Inputs: ctrl = nets w12; slice0 = nets _003_; slice1 = nets _004_; slice2 = nets _009_. Role: datapath.
- h239 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _033_; slice1 = nets w11. Role: datapath.
- h240 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _034_; slice1 = nets w12. Role: datapath.
- h342 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w1; slice1 = nets w12. Role: datapath.
- h343 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w13; slice1 = nets w12. Role: datapath.
- h356 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: ctrl = nets _037_; slice0 = nets w2; slice1 = nets w13. Role: datapath.
- h357 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: ctrl = nets _041_; slice0 = nets _045_; slice1 = nets w14. Role: datapath.
- h367 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w2; slice1 = nets w12. Role: datapath.
- h368 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w12; slice1 = nets w14. Role: datapath.
- h1 (unconfirmed): 8 cells form a flip-flop with synchronous reset, `ff_srst: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _001_, _002_; rst = nets _018_. Outputs: q = nets q[1], q[2]. Role: datapath.
- h4 (unconfirmed): 13 cells form a flip-flop with synchronous reset, `ff_srst: 3 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _003_, _004_, _009_; rst = nets w12. Outputs: q = nets q[3], q[4], q[9]. Role: datapath.
- h7 (unconfirmed): 16 cells form a flip-flop with synchronous reset, `ff_srst: 4 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _005_, _006_, _007_, _008_; rst = nets _030_. Outputs: q = nets q[5], q[6], q[7], q[8]. Role: datapath.
- h68 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: ctrl = nets q[9]; slice0 = nets w9; slice1 = nets w17. Role: datapath.
- h144 (unconfirmed): 7 cells form a flip-flop with synchronous reset, `ff_srst: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _001_, _002_; rst = nets _018_. Outputs: q = nets q[1], q[2]. Role: datapath.
- h264 (unconfirmed): 6 cells form a flip-flop with synchronous reset, `ff_srst: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _001_, _002_; rst = nets _018_. Outputs: q = nets q[1], q[2]. Role: datapath.
- h359 (unconfirmed): 11 cells form a flip-flop with synchronous reset, `ff_srst: 3 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _003_, _004_, _009_; rst = nets w12. Outputs: q = nets q[3], q[4], q[9]. Role: datapath.
- h361 (unconfirmed): 15 cells form a flip-flop with synchronous reset, `ff_srst: 4 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _005_, _006_, _007_, _008_; rst = nets _030_. Outputs: q = nets q[5], q[6], q[7], q[8]. Role: datapath.
- h395 (unconfirmed): 9 cells form a flip-flop with synchronous reset, `ff_srst: 3 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _003_, _004_, _009_; rst = nets w12. Outputs: q = nets q[3], q[4], q[9]. Role: datapath.
- h397 (unconfirmed): 14 cells form a flip-flop with synchronous reset, `ff_srst: 4 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _005_, _006_, _007_, _008_; rst = nets _030_. Outputs: q = nets q[5], q[6], q[7], q[8]. Role: datapath.

## 7. Rejected claims

- h266: Loki tested a 5-bit adder (`Y = A + B`) on 31 cells and the proof showed it differs (truth_table), counterexample A[0]=0,A[1]=0,A[2]=0,A[3]=0,A[4]=0,B[0]=0,B[1]=0,B[2]=0,B[3]=0,B[4]=0.

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = OR(NOT(_016_), NOT(_022_))
- w2 = OR(NOT(w1), NOT(_037_))
- w3 = AND(NOT(_014_), NOT(_013_))
- w4 = AND(NOT(q[4]), NOT(q[3]))
- w5 = OR(NOT(w4), NOT(w3))
- w6 = NOT(q[8])
- w7 = NOT(q[7])
- w8 = AND(NOT(w6), NOT(w7))
- w9 = OR(NOT(q[9]), NOT(w8))
- w10 = AND(NOT(w5), NOT(w9))
- w11 = OR(NOT(_021_), NOT(w10))
- w12 = OR(NOT(_018_), NOT(w11))
- w13 = OR(NOT(_017_), NOT(_037_))
- w14 = OR(NOT(w13), NOT(_041_))
- w15 = NOT(_047_)
- w16 = NOT(_053_)
- w17 = OR(NOT(q[9]), NOT(_056_))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
