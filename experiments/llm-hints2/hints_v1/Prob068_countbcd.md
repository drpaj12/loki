Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 7c10b084411f, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| adder | 0 | 0 | 3 |
| bus | 4 | 42 | 0 |
| eq_const | 34 | 1 | 0 |
| ff_en | 0 | 3 | 0 |
| ff_srst | 0 | 23 | 0 |
| fsm | 0 | 1 | 0 |
| subtractor | 0 | 0 | 2 |

Input cells (in Loki's re-mapped netlist): 109.

Of the committed cells, 11 (in 4 claims) are marked only by attributes on existing cells (form attrs). Those claims are not modules, so the hierarchy below does not show them.

Recovered module hierarchy (a module contains its children):

- h64 eq_const_h64 (eq_const)
  - h19 eq_const_h19 (eq_const)
    - h106 eq_const_h106 (eq_const)
    - h251 eq_const_h251 (eq_const)
  - h21 eq_const_h21 (eq_const)
    - h107 eq_const_h107 (eq_const)
    - h252 eq_const_h252 (eq_const)
  - h305 eq_const_h305 (eq_const)
  - h310 eq_const_h310 (eq_const)
  - h324 eq_const_h324 (eq_const)
  - h383 eq_const_h383 (eq_const)
- h108 eq_const_h108 (eq_const)
- h110 eq_const_h110 (eq_const)
  - h109 eq_const_h109 (eq_const)
  - h265 eq_const_h265 (eq_const)
- h111 eq_const_h111 (eq_const)
- h334 eq_const_h334 (eq_const)
  - h335 eq_const_h335 (eq_const)
  - h419 eq_const_h419 (eq_const)
- h336 eq_const_h336 (eq_const)
- h339 eq_const_h339 (eq_const)
- h340 eq_const_h340 (eq_const)
- h345 eq_const_h345 (eq_const)
- h417 eq_const_h417 (eq_const)
- h418 eq_const_h418 (eq_const)
- h420 eq_const_h420 (eq_const)
- h424 eq_const_h424 (eq_const)
- h426 eq_const_h426 (eq_const)
- h471 eq_const_h471 (eq_const)
- h472 eq_const_h472 (eq_const)
  - h473 eq_const_h473 (eq_const)
- h480 eq_const_h480 (eq_const)
- h494 eq_const_h494 (eq_const)
- h496 eq_const_h496 (eq_const)

## 4. Committed claims

- h64: 14 cells form a comparison against a constant, `Y = (A == 2457)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[0], q[1], q[2], q[3], q[4], q[5], q[6], q[7], q[8], q[9], q[10], q[11]. Outputs: Y = nets ena[3]. Recovered as module eq_const_h64, instance eq_const_h64_i. Role: datapath.
- h19: 2 cells form a comparison against a constant, `Y = (A != 4)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[5], q[6], q[7]. Outputs: Y = nets _071_. Recovered as module eq_const_h19, instance eq_const_h19_i. Role: datapath.
- h106: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[5], q[6]. Outputs: Y = nets _070_. Recovered as module eq_const_h106, instance eq_const_h106_i. Role: datapath.
- h251: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[7], _070_. Outputs: Y = nets _071_. Recovered as module eq_const_h251, instance eq_const_h251_i. Role: datapath.
- h21: 2 cells form a comparison against a constant, `Y = (A != 4)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[9], q[10], q[11]. Outputs: Y = nets _078_. Recovered as module eq_const_h21, instance eq_const_h21_i. Role: datapath.
- h107: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[9], q[10]. Outputs: Y = nets _077_. Recovered as module eq_const_h107, instance eq_const_h107_i. Role: datapath.
- h252: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[11], _077_. Outputs: Y = nets _078_. Recovered as module eq_const_h252, instance eq_const_h252_i. Role: datapath.
- h305: 8 cells form a comparison against a constant, `Y = (A == 25)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[0], q[1], q[2], q[3], q[4], _071_. Outputs: Y = nets ena[2]. Recovered as module eq_const_h305, instance eq_const_h305_i. Role: datapath.
- h310: 9 cells form a comparison against a constant, `Y = (A != 57)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[0], q[1], q[2], q[3], q[4], q[8], _071_. Outputs: Y = nets _025_. Recovered as module eq_const_h310, instance eq_const_h310_i. Role: datapath.
- h324: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets ena[2], q[8]. Outputs: Y = nets _025_. Recovered as module eq_const_h324, instance eq_const_h324_i. Role: datapath.
- h383: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _078_, _025_. Outputs: Y = nets ena[3]. Recovered as module eq_const_h383, instance eq_const_h383_i. Role: datapath.
- h108: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, q[0]. Outputs: Y = nets _000_. Recovered as module eq_const_h108, instance eq_const_h108_i. Role: datapath.
- h110: 2 cells form a comparison against a constant, `Y = (A != 4)`. Proof derived from h19 (proof transfer). Confidence 0.9999. Inputs: A = nets q[13], q[14], q[15]. Outputs: Y = nets _030_. Recovered as module eq_const_h110, instance eq_const_h110_i. Role: datapath.
- h109: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h106 (proof transfer). Confidence 0.9999. Inputs: A = nets q[13], q[14]. Outputs: Y = nets _029_. Recovered as module eq_const_h109, instance eq_const_h109_i. Role: datapath.
- h265: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h251 (proof transfer). Confidence 0.9999. Inputs: A = nets q[15], _029_. Outputs: Y = nets _030_. Recovered as module eq_const_h265, instance eq_const_h265_i. Role: datapath.
- h111: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, q[15]. Outputs: Y = nets w13. Recovered as module eq_const_h111, instance eq_const_h111_i. Role: datapath.
- h334: 4 cells form a comparison against a constant, `Y = (A == 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[1], q[2], w1, w3. Outputs: Y = nets w8. Recovered as module eq_const_h334, instance eq_const_h334_i. Role: datapath.
- h335: 3 cells form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[1], q[2], w3. Outputs: Y = nets w6. Recovered as module eq_const_h335, instance eq_const_h335_i. Role: datapath.
- h419: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets w1, w6. Outputs: Y = nets w8. Recovered as module eq_const_h419, instance eq_const_h419_i. Role: datapath.
- h336: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, ena[1]. Outputs: Y = nets _055_. Recovered as module eq_const_h336, instance eq_const_h336_i. Role: datapath.
- h339: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets ena[2], q[8]. Outputs: Y = nets _074_. Recovered as module eq_const_h339, instance eq_const_h339_i. Role: datapath.
- h340: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets ena[1], q[4]. Outputs: Y = nets _090_. Recovered as module eq_const_h340, instance eq_const_h340_i. Role: datapath.
- h345: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, ena[2]. Outputs: Y = nets _032_. Recovered as module eq_const_h345, instance eq_const_h345_i. Role: datapath.
- h417: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets w3, _049_. Outputs: Y = nets _058_. Recovered as module eq_const_h417, instance eq_const_h417_i. Role: datapath.
- h418: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets w1, w6. Outputs: Y = nets _066_. Recovered as module eq_const_h418, instance eq_const_h418_i. Role: datapath.
- h420: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, ena[3]. Outputs: Y = nets _032_. Recovered as module eq_const_h420, instance eq_const_h420_i. Role: datapath.
- h424: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets ena[3], q[12]. Outputs: Y = nets _025_. Recovered as module eq_const_h424, instance eq_const_h424_i. Role: datapath.
- h426: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets ena[3], q[12]. Outputs: Y = nets _027_. Recovered as module eq_const_h426, instance eq_const_h426_i. Role: datapath.
- h471: 4 cells form a comparison against a constant, `Y = (A == 6)`. Proved equivalent by truth table. Confidence 0.9993. Inputs: A = nets w5, _058_, _055_. Outputs: Y = nets _001_. Recovered as module eq_const_h471, instance eq_const_h471_i. Role: datapath. Conflicts with 2 more not listed.
- h472: 2 cells form a comparison against a constant, `Y = (A == 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _055_, _066_, w8. Outputs: Y = nets _003_. Recovered as module eq_const_h472, instance eq_const_h472_i. Role: datapath.
- h473: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _055_, _066_. Outputs: Y = nets w7. Recovered as module eq_const_h473, instance eq_const_h473_i. Role: datapath.
- h480: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _025_, _030_. Outputs: Y = nets ena[2]. Recovered as module eq_const_h480, instance eq_const_h480_i. Role: datapath.
- h494: 2 cells form a comparison against a constant, `Y = (A != 2)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[2], _059_. Outputs: Y = nets _062_. Recovered as module eq_const_h494, instance eq_const_h494_i. Role: datapath.
- h496: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, ena[2]. Outputs: Y = nets _032_. Recovered as module eq_const_h496, instance eq_const_h496_i. Role: datapath.
- h119: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9002. Inputs: ctrl = nets _059_; slice0 = nets _060_; slice1 = nets _062_. Role: datapath.
- h121: 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.9644. Inputs: ctrl = nets _032_; slice0 = nets _091_; slice1 = nets reset; slice2 = nets reset. Role: datapath.
- h122: 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.9002. Inputs: ctrl = nets _032_; slice0 = nets w9; slice1 = nets reset; slice2 = nets _089_. Role: datapath.
- h123: 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.9002. Inputs: ctrl = nets _032_; slice0 = nets w12; slice1 = nets _021_; slice2 = nets _024_. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h17 (unconfirmed): 2 bits, bit order from wf: bit 0 = w4; bit 1 = w2.
- h18 (unconfirmed): 2 bits, bit order from wf: bit 0 = w3; bit 1 = _033_.
- h20 (unconfirmed): 3 bits, bit order from wf: bit 0 = _068_; bit 1 = _025_; bit 2 = _025_.
- h22 (unconfirmed): 2 bits, bit order from wf: bit 0 = _000_; bit 1 = _029_.
- h23 (unconfirmed): 2 bits, bit order from wf: bit 0 = _049_; bit 1 = _050_.
- h24 (unconfirmed): 2 bits, bit order from wf: bit 0 = _058_; bit 1 = _062_.
- h25 (unconfirmed): 2 bits, bit order from wf: bit 0 = _058_; bit 1 = q[13].
- h26 (unconfirmed): 3 bits, bit order from wf: bit 0 = _090_; bit 1 = _074_; bit 2 = _027_.
- h27 (unconfirmed): 2 bits, bit order from wf: bit 0 = _025_; bit 1 = _030_.
- h118 (unconfirmed): 6 bits, bit order from net_id: bit 0 = _055_; bit 1 = _032_; bit 2 = _032_; bit 3 = _000_; bit 4 = w13; bit 5 = _032_.
- h119: 2 bits, bit order from net_id: bit 0 = _060_; bit 1 = _062_.
- h120 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _001_; bit 1 = _002_.
- h121: 3 bits, bit order from net_id: bit 0 = _091_; bit 1 = reset; bit 2 = reset.
- h122: 3 bits, bit order from net_id: bit 0 = w9; bit 1 = reset; bit 2 = _089_.
- h123: 3 bits, bit order from net_id: bit 0 = w12; bit 1 = _021_; bit 2 = _024_.
- h124 (unconfirmed): 3 bits, bit order from net_id: bit 0 = w13; bit 1 = _030_; bit 2 = _043_.
- h125 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _043_; bit 1 = _032_.
- h239 (unconfirmed): 2 bits, bit order from wf: bit 0 = _037_; bit 1 = _043_.
- h282 (unconfirmed): 4 bits, bit order from net_id: bit 0 = _055_; bit 1 = _032_; bit 2 = _032_; bit 3 = _032_.
- h291 (unconfirmed): 6 bits, bit order from wf: bit 0 = w2; bit 1 = ena[2]; bit 2 = ena[3]; bit 3 = _012_; bit 4 = _013_; bit 5 = reset.
- h292 (unconfirmed): 6 bits, bit order from wf: bit 0 = w2; bit 1 = ena[2]; bit 2 = _004_; bit 3 = _012_; bit 4 = _013_; bit 5 = reset.
- h293 (unconfirmed): 6 bits, bit order from wf: bit 0 = w2; bit 1 = _008_; bit 2 = _004_; bit 3 = _012_; bit 4 = _013_; bit 5 = reset.
- h294 (unconfirmed): 6 bits, bit order from wf: bit 0 = w4; bit 1 = ena[2]; bit 2 = ena[3]; bit 3 = _027_; bit 4 = ena[2]; bit 5 = reset.
- h295 (unconfirmed): 6 bits, bit order from wf: bit 0 = w4; bit 1 = ena[2]; bit 2 = _074_; bit 3 = ena[3]; bit 4 = ena[2]; bit 5 = reset.
- h296 (unconfirmed): 6 bits, bit order from wf: bit 0 = w4; bit 1 = _090_; bit 2 = ena[2]; bit 3 = ena[3]; bit 4 = ena[2]; bit 5 = reset.
- h297 (unconfirmed): 6 bits, bit order from wf: bit 0 = _060_; bit 1 = ena[2]; bit 2 = ena[3]; bit 3 = _012_; bit 4 = _013_; bit 5 = reset.
- h298 (unconfirmed): 6 bits, bit order from wf: bit 0 = _060_; bit 1 = ena[2]; bit 2 = _004_; bit 3 = _012_; bit 4 = _013_; bit 5 = reset.
- h299 (unconfirmed): 6 bits, bit order from wf: bit 0 = _060_; bit 1 = _008_; bit 2 = _004_; bit 3 = _012_; bit 4 = _013_; bit 5 = reset.
- h314 (unconfirmed): 3 bits, bit order from wf: bit 0 = ena[3]; bit 1 = ena[2]; bit 2 = reset.
- h318 (unconfirmed): 4 bits, bit order from wf: bit 0 = _074_; bit 1 = _027_; bit 2 = ena[2]; bit 3 = reset.
- h319 (unconfirmed): 4 bits, bit order from wf: bit 0 = _004_; bit 1 = _012_; bit 2 = _032_; bit 3 = _015_.
- h320 (unconfirmed): 2 bits, bit order from wf: bit 0 = _016_; bit 1 = _090_.
- h365 (unconfirmed): 2 bits, bit order from wf: bit 0 = ena[3]; bit 1 = _084_.
- h368 (unconfirmed): 2 bits, bit order from wf: bit 0 = w5; bit 1 = w8.
- h369 (unconfirmed): 2 bits, bit order from wf: bit 0 = _058_; bit 1 = w7.
- h370 (unconfirmed): 2 bits, bit order from wf: bit 0 = _058_; bit 1 = _066_.
- h371 (unconfirmed): 2 bits, bit order from wf: bit 0 = _060_; bit 1 = w7.
- h372 (unconfirmed): 2 bits, bit order from wf: bit 0 = _032_; bit 1 = _048_.
- h375 (unconfirmed): 3 bits, bit order from wf: bit 0 = _027_; bit 1 = ena[2]; bit 2 = reset.
- h376 (unconfirmed): 3 bits, bit order from wf: bit 0 = _012_; bit 1 = _032_; bit 2 = _015_.
- h408 (unconfirmed): 4 bits, bit order from net_id: bit 0 = _055_; bit 1 = _032_; bit 2 = _000_; bit 3 = w13.
- h410 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _032_; bit 1 = _032_.
- h413 (unconfirmed): 2 bits, bit order from wf: bit 0 = _059_; bit 1 = _056_.
- h481 (unconfirmed): 5 bits, bit order from net_id: bit 0 = _055_; bit 1 = _032_; bit 2 = _032_; bit 3 = _000_; bit 4 = w13.
- h490 (unconfirmed): 3 bits, bit order from wf: bit 0 = ena[2]; bit 1 = _032_; bit 2 = reset.
- h491 (unconfirmed): 3 bits, bit order from wf: bit 0 = ena[2]; bit 1 = _032_; bit 2 = _037_.

State machines:
- h237 (unconfirmed): state registers , 0 states, reset state 0, encoding unknown. 0 transitions.

Roles of committed claims: datapath: h19, h21, h64, h106, h107, h108, h109, h110, h111, h119, h121, h122, h123, h251, h252, h265, h305, h310, h324, h334, h335, h336, h339, h340, h345, h383, h417, h418, h419, h420, h424, h426, h471, h472, h473, h480, h494, h496.

## 6. Candidates (not committed, unconfirmed)

- h497 (unconfirmed): 2 cells form a comparison against a constant, `Y = (A != 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, ena[2]. Outputs: Y = nets reset. Role: datapath.
- h41 (unconfirmed): 6 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _007_; en = nets _025_. Outputs: q = nets q[11]. Role: datapath.
- h50 (unconfirmed): 6 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _011_; en = nets _020_. Outputs: q = nets q[7]. Role: datapath.
- h56 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _014_; en = nets ena[2]. Outputs: q = nets q[14]. Role: datapath.
- h291 (unconfirmed): 6 cells form a 6-bit bus, `bus: 6 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets w2; slice1 = nets ena[2]; slice2 = nets ena[3]; slice3 = nets _012_; slice4 = nets _013_; slice5 = nets reset. Role: datapath.
- h292 (unconfirmed): 6 cells form a 6-bit bus, `bus: 6 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets w2; slice1 = nets ena[2]; slice2 = nets _004_; slice3 = nets _012_; slice4 = nets _013_; slice5 = nets reset. Role: datapath.
- h293 (unconfirmed): 6 cells form a 6-bit bus, `bus: 6 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets w2; slice1 = nets _008_; slice2 = nets _004_; slice3 = nets _012_; slice4 = nets _013_; slice5 = nets reset. Role: datapath.
- h294 (unconfirmed): 6 cells form a 6-bit bus, `bus: 6 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets w4; slice1 = nets ena[2]; slice2 = nets ena[3]; slice3 = nets _027_; slice4 = nets ena[2]; slice5 = nets reset. Role: datapath.
- h295 (unconfirmed): 6 cells form a 6-bit bus, `bus: 6 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets w4; slice1 = nets ena[2]; slice2 = nets _074_; slice3 = nets ena[3]; slice4 = nets ena[2]; slice5 = nets reset. Role: datapath.
- h296 (unconfirmed): 6 cells form a 6-bit bus, `bus: 6 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets w4; slice1 = nets _090_; slice2 = nets ena[2]; slice3 = nets ena[3]; slice4 = nets ena[2]; slice5 = nets reset. Role: datapath.
- h297 (unconfirmed): 6 cells form a 6-bit bus, `bus: 6 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _060_; slice1 = nets ena[2]; slice2 = nets ena[3]; slice3 = nets _012_; slice4 = nets _013_; slice5 = nets reset. Role: datapath.
- h298 (unconfirmed): 6 cells form a 6-bit bus, `bus: 6 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _060_; slice1 = nets ena[2]; slice2 = nets _004_; slice3 = nets _012_; slice4 = nets _013_; slice5 = nets reset. Role: datapath.
- h299 (unconfirmed): 6 cells form a 6-bit bus, `bus: 6 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _060_; slice1 = nets _008_; slice2 = nets _004_; slice3 = nets _012_; slice4 = nets _013_; slice5 = nets reset. Role: datapath.
- h237 (unconfirmed): 18 cells form a finite state machine, `fsm: 3 bits`. No proof recorded. Confidence 0.8569. Inputs: d = nets _009_, _010_, _011_. Outputs: q = nets q[5], q[6], q[7]. Role: datapath.
- h120 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.8191. Inputs: ctrl = nets _056_; slice0 = nets _001_; slice1 = nets _002_. Role: datapath.
- h410 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.8191. Inputs: ctrl = nets reset; slice0 = nets _032_; slice1 = nets _032_. Role: datapath.
- h20 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _068_; slice1 = nets _025_; slice2 = nets _025_. Role: datapath.
- h26 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _090_; slice1 = nets _074_; slice2 = nets _027_. Role: datapath.
- h30 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _001_; rst = nets _056_. Outputs: q = nets q[1]. Role: datapath.
- h35 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _004_; rst = nets _032_. Outputs: q = nets q[8]. Role: datapath.
- h36 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _005_; rst = nets _032_. Outputs: q = nets q[9]. Role: datapath.
- h39 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _006_; rst = nets _032_. Outputs: q = nets q[10]. Role: datapath.
- h42 (unconfirmed): 6 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _007_; rst = nets _032_. Outputs: q = nets q[11]. Role: datapath.
- h44 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _008_; rst = nets _032_. Outputs: q = nets q[4]. Role: datapath.
- h45 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _009_; rst = nets _032_. Outputs: q = nets q[5]. Role: datapath.
- h48 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _010_; rst = nets _032_. Outputs: q = nets q[6]. Role: datapath.
- h51 (unconfirmed): 6 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _011_; rst = nets _032_. Outputs: q = nets q[7]. Role: datapath.
- h52 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _012_; rst = nets _032_. Outputs: q = nets q[12]. Role: datapath.
- h125 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets ena[2]; slice0 = nets _043_; slice1 = nets _032_. Role: datapath.
- h314 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets ena[3]; slice1 = nets ena[2]; slice2 = nets reset. Role: datapath.
- h318 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _074_; slice1 = nets _027_; slice2 = nets ena[2]; slice3 = nets reset. Role: datapath.
- h319 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _004_; slice1 = nets _012_; slice2 = nets _032_; slice3 = nets _015_. Role: datapath.
- h375 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _027_; slice1 = nets ena[2]; slice2 = nets reset. Role: datapath.
- h376 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _012_; slice1 = nets _032_; slice2 = nets _015_. Role: datapath.
- h378 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _004_; rst = nets _032_. Outputs: q = nets q[8]. Role: datapath.
- h381 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _008_; rst = nets _032_. Outputs: q = nets q[4]. Role: datapath.
- h463 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _001_; rst = nets _056_. Outputs: q = nets q[1]. Role: datapath.
- h467 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _012_; rst = nets _032_. Outputs: q = nets q[12]. Role: datapath.
- h490 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets ena[2]; slice1 = nets _032_; slice2 = nets reset. Role: datapath.
- h491 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets ena[2]; slice1 = nets _032_; slice2 = nets _037_. Role: datapath.
- h118 (unconfirmed): 6 cells form a 6-bit bus, `bus: 6 bits`. No proof recorded. Confidence 0.6682. Inputs: ctrl = nets reset; slice0 = nets _055_; slice1 = nets _032_; slice2 = nets _032_; slice3 = nets _000_; slice4 = nets w13; slice5 = nets _032_. Role: datapath.
- h481 (unconfirmed): 5 cells form a 5-bit bus, `bus: 5 bits`. No proof recorded. Confidence 0.6682. Inputs: ctrl = nets reset; slice0 = nets _055_; slice1 = nets _032_; slice2 = nets _032_; slice3 = nets _000_; slice4 = nets w13. Role: datapath.
- h17 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w4; slice1 = nets w2. Role: datapath.
- h18 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w3; slice1 = nets _033_. Role: datapath.
- h22 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _000_; slice1 = nets _029_. Role: datapath.
- h23 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _049_; slice1 = nets _050_. Role: datapath.
- h24 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _058_; slice1 = nets _062_. Role: datapath.
- h25 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _058_; slice1 = nets q[13]. Role: datapath.
- h27 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _025_; slice1 = nets _030_. Role: datapath.
- h239 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _037_; slice1 = nets _043_. Role: datapath.
- h320 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _016_; slice1 = nets _090_. Role: datapath.
- h365 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets ena[3]; slice1 = nets _084_. Role: datapath.
- h368 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w5; slice1 = nets w8. Role: datapath.
- h369 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _058_; slice1 = nets w7. Role: datapath.
- h370 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _058_; slice1 = nets _066_. Role: datapath.
- h371 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _060_; slice1 = nets w7. Role: datapath.
- h372 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _032_; slice1 = nets _048_. Role: datapath.
- h413 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _059_; slice1 = nets _056_. Role: datapath.
- h3 (unconfirmed): 8 cells form a flip-flop with synchronous reset, `ff_srst: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _001_, _002_; rst = nets _056_. Outputs: q = nets q[1], q[2]. Role: datapath.
- h6 (unconfirmed): 12 cells form a flip-flop with synchronous reset, `ff_srst: 3 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _008_, _004_, _012_; rst = nets _032_. Outputs: q = nets q[4], q[8], q[12]. Role: datapath.
- h9 (unconfirmed): 14 cells form a flip-flop with synchronous reset, `ff_srst: 3 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _005_, _006_, _007_; rst = nets _032_. Outputs: q = nets q[9], q[10], q[11]. Role: datapath.
- h12 (unconfirmed): 14 cells form a flip-flop with synchronous reset, `ff_srst: 3 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _009_, _010_, _011_; rst = nets _032_. Outputs: q = nets q[5], q[6], q[7]. Role: datapath.
- h124 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.5000. Inputs: ctrl = nets q[15]; slice0 = nets w13; slice1 = nets _030_; slice2 = nets _043_. Role: datapath.
- h282 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.5000. Inputs: ctrl = nets reset; slice0 = nets _055_; slice1 = nets _032_; slice2 = nets _032_; slice3 = nets _032_. Role: datapath.
- h360 (unconfirmed): 10 cells form a flip-flop with synchronous reset, `ff_srst: 3 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _008_, _004_, _012_; rst = nets _032_. Outputs: q = nets q[4], q[8], q[12]. Role: datapath.
- h408 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.5000. Inputs: ctrl = nets reset; slice0 = nets _055_; slice1 = nets _032_; slice2 = nets _000_; slice3 = nets w13. Role: datapath.
- h452 (unconfirmed): 7 cells form a flip-flop with synchronous reset, `ff_srst: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _001_, _002_; rst = nets _056_. Outputs: q = nets q[1], q[2]. Role: datapath.
- h454 (unconfirmed): 9 cells form a flip-flop with synchronous reset, `ff_srst: 3 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _008_, _004_, _012_; rst = nets _032_. Outputs: q = nets q[4], q[8], q[12]. Role: datapath.
- h484 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.5000. Inputs: rst = nets _055_. Role: datapath.
- h499 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.5000. Inputs: rst = nets w8. Role: datapath.

## 7. Rejected claims

- h412: Loki tested a 2-bit adder (`Y = A + B`) on 5 cells and the proof showed it differs (truth_table), counterexample A[0]=0,A[1]=0,B[0]=0,B[1]=0.
- h414: Loki tested a 2-bit subtractor (`Y = A - B`) on 6 cells and the proof showed it differs (truth_table), counterexample A[0]=0,A[1]=1,B[0]=0,B[1]=0.
- h457: Loki tested a 2-bit adder (`Y = A + B`) on 7 cells and the proof showed it differs (truth_table), counterexample A[0]=0,A[1]=0,B[0]=0,B[1]=0.
- h458: Loki tested a 2-bit adder (`Y = A + B`) on 7 cells and the proof showed it differs (truth_table), counterexample A[0]=0,A[1]=0,B[0]=0,B[1]=0.
- h486: Loki tested a 2-bit subtractor (`Y = A - B`) on 4 cells and the proof showed it differs (truth_table), counterexample A[0]=0,A[1]=0,B[0]=0,B[1]=0.

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = NOT(q[3])
- w2 = AND(NOT(w1), NOT(q[2]))
- w3 = NOT(q[0])
- w4 = AND(NOT(q[1]), NOT(w3))
- w5 = AND(NOT(_049_), NOT(w3))
- w6 = OR(NOT(q[2]), NOT(w5))
- w7 = OR(NOT(_055_), NOT(_066_))
- w8 = AND(NOT(w6), NOT(w1))
- w9 = OR(NOT(_032_), NOT(q[9]))
- w10 = NOT(q[5])
- w11 = OR(NOT(w10), NOT(_068_))
- w12 = OR(NOT(_032_), NOT(w11))
- w13 = AND(NOT(q[15]), NOT(reset))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
