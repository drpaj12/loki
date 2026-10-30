Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 46128fcea76c, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| adder | 0 | 0 | 1 |
| bus | 10 | 67 | 0 |
| eq_const | 19 | 0 | 0 |
| subtractor | 1 | 0 | 0 |

Input cells (in Loki's re-mapped netlist): 231.

Of the committed cells, 32 (in 10 claims) are marked only by attributes on existing cells (form attrs). Those claims are not modules, so the hierarchy below does not show them.

Recovered module hierarchy (a module contains its children):

- h2 eq_const_h2 (eq_const)
- h6 eq_const_h6 (eq_const)
- h9 eq_const_h9 (eq_const)
- h10 eq_const_h10 (eq_const)
- h13 subtractor_h13 (subtractor)
  - h12 eq_const_h12 (eq_const)
  - h16 eq_const_h16 (eq_const)
  - h19 eq_const_h19 (eq_const)
  - h20 eq_const_h20 (eq_const)
- h22 eq_const_h22 (eq_const)
- h25 eq_const_h25 (eq_const)
- h27 eq_const_h27 (eq_const)
- h28 eq_const_h28 (eq_const)
- h33 eq_const_h33 (eq_const)
- h43 eq_const_h43 (eq_const)
- h45 eq_const_h45 (eq_const)
- h699 eq_const_h699 (eq_const)
  - h698 eq_const_h698 (eq_const)
  - h700 eq_const_h700 (eq_const)
  - h1165 eq_const_h1165 (eq_const)

## 4. Committed claims

- h2: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets a[0], b[0]. Outputs: Y = nets _034_. Recovered as module eq_const_h2, instance eq_const_h2_i. Role: datapath.
- h6: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets a[1], b[1]. Outputs: Y = nets _006_. Recovered as module eq_const_h6, instance eq_const_h6_i. Role: datapath.
- h9: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets a[1], b[1]. Outputs: Y = nets w2. Recovered as module eq_const_h9, instance eq_const_h9_i. Role: datapath.
- h10: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets a[0], b[0]. Outputs: Y = nets _009_. Recovered as module eq_const_h10, instance eq_const_h10_i. Role: datapath.
- h13: 10 cells form a 2-bit subtractor, `Y = A - B`. No proof recorded. Confidence 0.9105. Inputs: A = nets b[2], a[3]; B = nets a[2], b[3]. Outputs: Y = nets _002_, w5, w6. Recovered as module subtractor_h13, instance subtractor_h13_i. Role: datapath.
- h12: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h9 (proof transfer). Confidence 0.9999. Inputs: A = nets a[3], b[3]. Outputs: Y = nets _321_. Recovered as module eq_const_h12, instance eq_const_h12_i. Role: datapath.
- h16: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h9 (proof transfer). Confidence 0.9999. Inputs: A = nets a[2], b[2]. Outputs: Y = nets _002_. Recovered as module eq_const_h16, instance eq_const_h16_i. Role: datapath.
- h19: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proof derived from h2 (proof transfer). Confidence 0.9999. Inputs: A = nets a[3], b[3]. Outputs: Y = nets _323_. Recovered as module eq_const_h19, instance eq_const_h19_i. Role: datapath.
- h20: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proof derived from h2 (proof transfer). Confidence 0.9999. Inputs: A = nets a[2], b[2]. Outputs: Y = nets _000_. Recovered as module eq_const_h20, instance eq_const_h20_i. Role: datapath.
- h22: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h9 (proof transfer). Confidence 0.9999. Inputs: A = nets a[4], b[4]. Outputs: Y = nets _317_. Recovered as module eq_const_h22, instance eq_const_h22_i. Role: datapath.
- h25: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h9 (proof transfer). Confidence 0.9999. Inputs: A = nets a[5], b[5]. Outputs: Y = nets _310_. Recovered as module eq_const_h25, instance eq_const_h25_i. Role: datapath.
- h27: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h9 (proof transfer). Confidence 0.9999. Inputs: A = nets a[6], b[6]. Outputs: Y = nets _309_. Recovered as module eq_const_h27, instance eq_const_h27_i. Role: datapath.
- h28: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proof derived from h2 (proof transfer). Confidence 0.9999. Inputs: A = nets a[6], b[6]. Outputs: Y = nets w8. Recovered as module eq_const_h28, instance eq_const_h28_i. Role: datapath.
- h33: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets a[7], b[7]. Outputs: Y = nets _306_. Recovered as module eq_const_h33, instance eq_const_h33_i. Role: datapath.
- h43: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proof derived from h2 (proof transfer). Confidence 0.9999. Inputs: A = nets a[5], b[5]. Outputs: Y = nets w16. Recovered as module eq_const_h43, instance eq_const_h43_i. Role: datapath.
- h45: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proof derived from h2 (proof transfer). Confidence 0.9999. Inputs: A = nets a[4], b[4]. Outputs: Y = nets w18. Recovered as module eq_const_h45, instance eq_const_h45_i. Role: datapath.
- h699: 3 cells form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _310_, _309_, w8. Outputs: Y = nets w11. Recovered as module eq_const_h699, instance eq_const_h699_i. Role: datapath.
- h698: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _309_, w8. Outputs: Y = nets w9. Recovered as module eq_const_h698, instance eq_const_h698_i. Role: datapath.
- h700: 2 cells form a comparison against a constant, `Y = (A != 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _309_, w8. Outputs: Y = nets w10. Recovered as module eq_const_h700, instance eq_const_h700_i. Role: datapath.
- h1165: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _310_, w10. Outputs: Y = nets w11. Recovered as module eq_const_h1165, instance eq_const_h1165_i. Role: datapath.
- h299: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9315. Inputs: ctrl = nets _006_; slice0 = nets w1; slice1 = nets _014_. Role: datapath.
- h302: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9315. Inputs: ctrl = nets w3; slice0 = nets _014_; slice1 = nets w4. Role: datapath.
- h305: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9315. Inputs: ctrl = nets _321_; slice0 = nets w5; slice1 = nets _021_. Role: datapath.
- h308: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9315. Inputs: ctrl = nets w6; slice0 = nets _021_; slice1 = nets _004_. Role: datapath.
- h309: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets _004_; slice0 = nets w7; slice1 = nets _016_. Role: datapath.
- h318: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9315. Inputs: ctrl = nets w12; slice0 = nets w20; slice1 = nets w13. Role: datapath.
- h322: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9315. Inputs: ctrl = nets w19; slice0 = nets w21; slice1 = nets _319_. Role: datapath.
- h325: 7 cells form a 7-bit bus, `bus: 7 bits`. No proof recorded. Confidence 0.9731. Inputs: ctrl = nets _041_; slice0 = nets _081_; slice1 = nets w29; slice2 = nets _062_; slice3 = nets _070_; slice4 = nets w26; slice5 = nets w32; slice6 = nets _043_. Role: datapath.
- h343: 6 cells form a 6-bit bus, `bus: 6 bits`. No proof recorded. Confidence 0.9731. Inputs: ctrl = nets _137_; slice0 = nets _209_; slice1 = nets _175_; slice2 = nets _183_; slice3 = nets w38; slice4 = nets _138_; slice5 = nets w36. Role: datapath.
- h355: 7 cells form a 7-bit bus, `bus: 7 bits`. No proof recorded. Confidence 0.9601. Inputs: ctrl = nets _252_; slice0 = nets _262_; slice1 = nets _256_; slice2 = nets _258_; slice3 = nets _266_; slice4 = nets _254_; slice5 = nets _260_; slice6 = nets _264_. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h1 (unconfirmed): 2 bits, bit order from wf: bit 0 = _284_; bit 1 = _285_.
- h4 (unconfirmed): 2 bits, bit order from wf: bit 0 = _034_; bit 1 = w2.
- h5 (unconfirmed): 2 bits, bit order from wf: bit 0 = _283_; bit 1 = _286_.
- h7 (unconfirmed): 2 bits, bit order from wf: bit 0 = _009_; bit 1 = _006_.
- h8 (unconfirmed): 2 bits, bit order from wf: bit 0 = w1; bit 1 = w3.
- h11 (unconfirmed): 2 bits, bit order from wf: bit 0 = _289_; bit 1 = _288_.
- h14 (unconfirmed): 2 bits, bit order from wf: bit 0 = _321_; bit 1 = _000_.
- h15 (unconfirmed): 2 bits, bit order from wf: bit 0 = _290_; bit 1 = _287_.
- h17 (unconfirmed): 2 bits, bit order from wf: bit 0 = _323_; bit 1 = _002_.
- h18 (unconfirmed): 2 bits, bit order from wf: bit 0 = w5; bit 1 = w6.
- h21 (unconfirmed): 2 bits, bit order from wf: bit 0 = _291_; bit 1 = _292_.
- h24 (unconfirmed): 2 bits, bit order from wf: bit 0 = _317_; bit 1 = _310_.
- h29 (unconfirmed): 2 bits, bit order from wf: bit 0 = w11; bit 1 = w21.
- h30 (unconfirmed): 2 bits, bit order from wf: bit 0 = w14; bit 1 = w11.
- h32 (unconfirmed): 2 bits, bit order from wf: bit 0 = _306_; bit 1 = _299_.
- h34 (unconfirmed): 2 bits, bit order from wf: bit 0 = _295_; bit 1 = _274_.
- h38 (unconfirmed): 2 bits, bit order from wf: bit 0 = _296_; bit 1 = _282_.
- h40 (unconfirmed): 2 bits, bit order from wf: bit 0 = _307_; bit 1 = w24.
- h41 (unconfirmed): 2 bits, bit order from wf: bit 0 = w14; bit 1 = w21.
- h42 (unconfirmed): 2 bits, bit order from wf: bit 0 = w17; bit 1 = w15.
- h44 (unconfirmed): 2 bits, bit order from wf: bit 0 = w18; bit 1 = w16.
- h297 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _034_; bit 1 = w28.
- h298 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _006_; bit 1 = _083_.
- h299: 2 bits, bit order from net_id: bit 0 = w1; bit 1 = _014_.
- h300 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w2; bit 1 = _081_.
- h301 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _009_; bit 1 = w29.
- h302: 2 bits, bit order from net_id: bit 0 = _014_; bit 1 = w4.
- h303 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _321_; bit 1 = _062_.
- h304 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _002_; bit 1 = _070_.
- h305: 2 bits, bit order from net_id: bit 0 = w5; bit 1 = _021_.
- h306 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _323_; bit 1 = _064_.
- h307 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _000_; bit 1 = _072_.
- h308: 2 bits, bit order from net_id: bit 0 = _021_; bit 1 = _004_.
- h309: 2 bits, bit order from net_id: bit 0 = w7; bit 1 = _016_.
- h310 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _317_; bit 1 = w26.
- h311 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _310_; bit 1 = w32.
- h312 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _309_; bit 1 = _043_.
- h313 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w8; bit 1 = _044_.
- h314 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w9; bit 1 = w20.
- h316 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _027_; bit 1 = _297_.
- h317 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _307_; bit 1 = w34.
- h318: 2 bits, bit order from net_id: bit 0 = w20; bit 1 = w13.
- h319 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w14; bit 1 = w21.
- h320 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w16; bit 1 = w31.
- h321 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w18; bit 1 = w25.
- h322: 2 bits, bit order from net_id: bit 0 = w21; bit 1 = _319_.
- h323 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _038_; bit 1 = _024_.
- h324 (unconfirmed): 7 bits, bit order from net_id: bit 0 = w28; bit 1 = _083_; bit 2 = _064_; bit 3 = _072_; bit 4 = _044_; bit 5 = w31; bit 6 = w25.
- h325: 7 bits, bit order from net_id: bit 0 = _081_; bit 1 = w29; bit 2 = _062_; bit 3 = _070_; bit 4 = w26; bit 5 = w32; bit 6 = _043_.
- h327 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _299_; bit 1 = _301_.
- h332 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w30; bit 1 = _202_.
- h333 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w30; bit 1 = _203_.
- h334 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _090_; bit 1 = _209_.
- h335 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _076_; bit 1 = _175_.
- h336 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _068_; bit 1 = _183_.
- h337 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _061_; bit 1 = w38.
- h339 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _114_; bit 1 = _138_.
- h340 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _113_; bit 1 = w36.
- h341 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w34; bit 1 = _301_.
- h342 (unconfirmed): 8 bits, bit order from net_id: bit 0 = _202_; bit 1 = _140_; bit 2 = _185_; bit 3 = w37; bit 4 = _211_; bit 5 = _177_; bit 6 = _203_; bit 7 = w35.
- h343: 6 bits, bit order from net_id: bit 0 = _209_; bit 1 = _175_; bit 2 = _183_; bit 3 = w38; bit 4 = _138_; bit 5 = w36.
- h344 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _144_; bit 1 = _265_.
- h345 (unconfirmed): 2 bits, bit order from chain: bit 0 = min[7]; bit 1 = _146_.
- h346 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w40; bit 1 = _261_.
- h347 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _165_; bit 1 = _262_.
- h348 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _193_; bit 1 = _257_.
- h349 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _220_; bit 1 = _255_.
- h350 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w43; bit 1 = _253_.
- h351 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _215_; bit 1 = _256_.
- h352 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _181_; bit 1 = _258_.
- h353 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _150_; bit 1 = _266_.
- h354 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _163_; bit 1 = min[7].
- h355: 7 bits, bit order from net_id: bit 0 = _262_; bit 1 = _256_; bit 2 = _258_; bit 3 = _266_; bit 4 = _254_; bit 5 = _260_; bit 6 = _264_.
- h356 (unconfirmed): 7 bits, bit order from net_id: bit 0 = _253_; bit 1 = _255_; bit 2 = _257_; bit 3 = _259_; bit 4 = _261_; bit 5 = _263_; bit 6 = _265_.
- h590 (unconfirmed): 2 bits, bit order from wf: bit 0 = _014_; bit 1 = w7.
- h592 (unconfirmed): 2 bits, bit order from wf: bit 0 = _027_; bit 1 = _146_.
- h593 (unconfirmed): 2 bits, bit order from wf: bit 0 = _031_; bit 1 = _148_.

State machines: none.

Roles of committed claims: datapath: h2, h6, h9, h10, h12, h13, h16, h19, h20, h22, h25, h27, h28, h33, h43, h45, h299, h302, h305, h308, h309, h318, h322, h325, h343, h355, h698, h699, h700, h1165.

## 6. Candidates (not committed, unconfirmed)

- h324 (unconfirmed): 7 cells form a 7-bit bus, `bus: 7 bits`. No proof recorded. Confidence 0.8581. Inputs: ctrl = nets _040_; slice0 = nets w28; slice1 = nets _083_; slice2 = nets _064_; slice3 = nets _072_; slice4 = nets _044_; slice5 = nets w31; slice6 = nets w25. Role: datapath.
- h356 (unconfirmed): 7 cells form a 7-bit bus, `bus: 7 bits`. No proof recorded. Confidence 0.8581. Inputs: ctrl = nets _251_; slice0 = nets _253_; slice1 = nets _255_; slice2 = nets _257_; slice3 = nets _259_; slice4 = nets _261_; slice5 = nets _263_; slice6 = nets _265_. Role: datapath.
- h332 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.8569. Inputs: ctrl = nets c[0]; slice0 = nets w30; slice1 = nets _202_. Role: datapath.
- h334 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.8569. Inputs: ctrl = nets _276_; slice0 = nets _090_; slice1 = nets _209_. Role: datapath.
- h335 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.8569. Inputs: ctrl = nets _277_; slice0 = nets _076_; slice1 = nets _175_. Role: datapath.
- h336 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.8569. Inputs: ctrl = nets _278_; slice0 = nets _068_; slice1 = nets _183_. Role: datapath.
- h337 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.8569. Inputs: ctrl = nets _279_; slice0 = nets _061_; slice1 = nets w38. Role: datapath.
- h339 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.8569. Inputs: ctrl = nets _281_; slice0 = nets _114_; slice1 = nets _138_. Role: datapath.
- h340 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.8569. Inputs: ctrl = nets _280_; slice0 = nets _113_; slice1 = nets w36. Role: datapath.
- h319 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.8191. Inputs: ctrl = nets w13; slice0 = nets w14; slice1 = nets w21. Role: datapath.
- h347 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.8191. Inputs: ctrl = nets _154_; slice0 = nets _165_; slice1 = nets _262_. Role: datapath.
- h350 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.8191. Inputs: ctrl = nets d[0]; slice0 = nets w43; slice1 = nets _253_. Role: datapath.
- h351 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.8191. Inputs: ctrl = nets _214_; slice0 = nets _215_; slice1 = nets _256_. Role: datapath.
- h352 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.8191. Inputs: ctrl = nets _180_; slice0 = nets _181_; slice1 = nets _258_. Role: datapath.
- h353 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.8191. Inputs: ctrl = nets _143_; slice0 = nets _150_; slice1 = nets _266_. Role: datapath.
- h297 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _284_; slice0 = nets _034_; slice1 = nets w28. Role: datapath.
- h298 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _286_; slice0 = nets _006_; slice1 = nets _083_. Role: datapath.
- h300 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _285_; slice0 = nets w2; slice1 = nets _081_. Role: datapath.
- h301 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _283_; slice0 = nets _009_; slice1 = nets w29. Role: datapath.
- h303 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _289_; slice0 = nets _321_; slice1 = nets _062_. Role: datapath.
- h304 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _287_; slice0 = nets _002_; slice1 = nets _070_. Role: datapath.
- h306 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _290_; slice0 = nets _323_; slice1 = nets _064_. Role: datapath.
- h307 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _288_; slice0 = nets _000_; slice1 = nets _072_. Role: datapath.
- h310 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _291_; slice0 = nets _317_; slice1 = nets w26. Role: datapath.
- h311 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _292_; slice0 = nets _310_; slice1 = nets w32. Role: datapath.
- h312 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _293_; slice0 = nets _309_; slice1 = nets _043_. Role: datapath.
- h313 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _294_; slice0 = nets w8; slice1 = nets _044_. Role: datapath.
- h314 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets w8; slice0 = nets w9; slice1 = nets w20. Role: datapath.
- h316 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _296_; slice0 = nets _027_; slice1 = nets _297_. Role: datapath.
- h320 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets w15; slice0 = nets w16; slice1 = nets w31. Role: datapath.
- h321 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets w17; slice0 = nets w18; slice1 = nets w25. Role: datapath.
- h323 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _319_; slice0 = nets _038_; slice1 = nets _024_. Role: datapath.
- h327 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _298_; slice0 = nets _299_; slice1 = nets _301_. Role: datapath.
- h333 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _094_; slice0 = nets w30; slice1 = nets _203_. Role: datapath.
- h341 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _282_; slice0 = nets w34; slice1 = nets _301_. Role: datapath.
- h345 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _302_; slice0 = nets min[7]; slice1 = nets _146_. Role: datapath.
- h354 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _274_; slice0 = nets _163_; slice1 = nets min[7]. Role: datapath.
- h342 (unconfirmed): 8 cells form an 8-bit bus, `bus: 8 bits`. No proof recorded. Confidence 0.6682. Inputs: ctrl = nets _136_; slice0 = nets _202_; slice1 = nets _140_; slice2 = nets _185_; slice3 = nets w37; slice4 = nets _211_; slice5 = nets _177_; slice6 = nets _203_; slice7 = nets w35. Role: datapath.
- h1 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _284_; slice1 = nets _285_. Role: datapath.
- h4 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _034_; slice1 = nets w2. Role: datapath.
- h5 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _283_; slice1 = nets _286_. Role: datapath.
- h7 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _009_; slice1 = nets _006_. Role: datapath.
- h8 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w1; slice1 = nets w3. Role: datapath.
- h11 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _289_; slice1 = nets _288_. Role: datapath.
- h14 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _321_; slice1 = nets _000_. Role: datapath.
- h15 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _290_; slice1 = nets _287_. Role: datapath.
- h17 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _323_; slice1 = nets _002_. Role: datapath.
- h18 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w5; slice1 = nets w6. Role: datapath.
- h21 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _291_; slice1 = nets _292_. Role: datapath.
- h24 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _317_; slice1 = nets _310_. Role: datapath.
- h29 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w11; slice1 = nets w21. Role: datapath.
- h30 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w14; slice1 = nets w11. Role: datapath.
- h32 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _306_; slice1 = nets _299_. Role: datapath.
- h34 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _295_; slice1 = nets _274_. Role: datapath.
- h38 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _296_; slice1 = nets _282_. Role: datapath.
- h40 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _307_; slice1 = nets w24. Role: datapath.
- h41 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w14; slice1 = nets w21. Role: datapath.
- h42 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w17; slice1 = nets w15. Role: datapath.
- h44 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w18; slice1 = nets w16. Role: datapath.
- h317 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: ctrl = nets _297_; slice0 = nets _307_; slice1 = nets w34. Role: datapath.
- h590 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _014_; slice1 = nets w7. Role: datapath.
- h592 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _027_; slice1 = nets _146_. Role: datapath.
- h593 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _031_; slice1 = nets _148_. Role: datapath.
- h344 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: ctrl = nets d[6]; slice0 = nets _144_; slice1 = nets _265_. Role: datapath.
- h346 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: ctrl = nets d[4]; slice0 = nets w40; slice1 = nets _261_. Role: datapath.
- h348 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: ctrl = nets d[2]; slice0 = nets _193_; slice1 = nets _257_. Role: datapath.
- h349 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: ctrl = nets d[1]; slice0 = nets _220_; slice1 = nets _255_. Role: datapath.

## 7. Rejected claims

- h31: Loki tested a 2-bit adder (`Y = A + B`) on 12 cells and the proof showed it differs (truth_table), counterexample A[0]=0,A[1]=1,B[0]=0,B[1]=0.

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = AND(NOT(_034_), NOT(_006_))
- w2 = AND(NOT(_285_), NOT(a[1]))
- w3 = AND(NOT(w2), NOT(_009_))
- w4 = OR(NOT(w3), NOT(w1))
- w5 = AND(NOT(_321_), NOT(_002_))
- w6 = AND(NOT(_323_), NOT(_000_))
- w7 = AND(NOT(w4), NOT(_004_))
- w8 = AND(NOT(b[6]), NOT(_294_))
- w9 = AND(NOT(_309_), NOT(w8))
- w10 = NOT(w9)
- w11 = AND(NOT(_310_), NOT(w10))
- w12 = NOT(_307_)
- w13 = OR(NOT(w12), NOT(w11))
- w14 = AND(NOT(_317_), NOT(w13))
- w15 = NOT(a[5])
- w16 = AND(NOT(b[5]), NOT(w15))
- w17 = NOT(a[4])
- w18 = AND(NOT(b[4]), NOT(w17))
- w19 = AND(NOT(w16), NOT(w18))
- w20 = OR(NOT(w12), NOT(w8))
- w21 = AND(NOT(w19), NOT(w13))
- w22 = AND(NOT(_044_), NOT(_043_))
- w23 = AND(NOT(w22), NOT(c[6]))
- w24 = AND(NOT(w23), NOT(_299_))
- w25 = AND(NOT(_040_), NOT(w17))
- w26 = AND(NOT(_041_), NOT(_291_))
- w27 = AND(NOT(w25), NOT(w26))
- w28 = AND(NOT(_040_), NOT(_284_))
- w29 = AND(NOT(_041_), NOT(_283_))
- w30 = AND(NOT(_094_), NOT(c[0]))
- w31 = AND(NOT(_040_), NOT(w15))
- w32 = AND(NOT(_041_), NOT(_292_))
- w33 = AND(NOT(w31), NOT(w32))
- w34 = AND(NOT(_297_), NOT(_282_))
- w35 = AND(NOT(_136_), NOT(w33))
- w36 = AND(NOT(_137_), NOT(_280_))
- w37 = AND(NOT(_136_), NOT(w27))
- w38 = AND(NOT(_137_), NOT(_279_))
- w39 = AND(NOT(w37), NOT(w38))
- w40 = AND(NOT(w39), NOT(d[4]))
- w41 = NOT(_202_)
- w42 = AND(NOT(_203_), NOT(w41))
- w43 = AND(NOT(w42), NOT(d[0]))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
