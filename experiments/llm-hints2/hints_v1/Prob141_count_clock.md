Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 7581db96cb58, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| bus | 9 | 33 | 0 |
| eq_const | 12 | 0 | 0 |
| ff_en | 0 | 2 | 0 |
| ff_srst | 0 | 31 | 0 |
| fsm | 0 | 2 | 0 |
| register | 0 | 2 | 0 |

Input cells (in Loki's re-mapped netlist): 219.

Of the committed cells, 49 (in 9 claims) are marked only by attributes on existing cells (form attrs). Those claims are not modules, so the hierarchy below does not show them.

Recovered module hierarchy (a module contains its children):

- h117 eq_const_h117 (eq_const)
  - h26 eq_const_h26 (eq_const)
  - h118 eq_const_h118 (eq_const)
  - h395 eq_const_h395 (eq_const)
- h119 eq_const_h119 (eq_const)
- h126 eq_const_h126 (eq_const)
  - h28 eq_const_h28 (eq_const)
  - h125 eq_const_h125 (eq_const)
  - h401 eq_const_h401 (eq_const)
- h510 eq_const_h510 (eq_const)
  - h509 eq_const_h509 (eq_const)
- h512 eq_const_h512 (eq_const)

## 4. Committed claims

- h117: 5 cells form a comparison against a constant, `Y = (A != 9)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets hh[0], hh[1], hh[2], hh[3]. Outputs: Y = nets _033_. Recovered as module eq_const_h117, instance eq_const_h117_i. Role: datapath.
- h26: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets hh[1], hh[2]. Outputs: Y = nets _030_. Recovered as module eq_const_h26, instance eq_const_h26_i. Role: datapath.
- h118: 3 cells form a comparison against a constant, `Y = (A == 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets hh[0], hh[3]. Outputs: Y = nets _029_. Recovered as module eq_const_h118, instance eq_const_h118_i. Role: datapath.
- h395: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _030_, _029_. Outputs: Y = nets _033_. Recovered as module eq_const_h395, instance eq_const_h395_i. Role: datapath.
- h119: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets mm[4], mm[6]. Outputs: Y = nets _060_. Recovered as module eq_const_h119, instance eq_const_h119_i. Role: datapath.
- h126: 3 cells form a comparison against a constant, `Y = (A != 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets hh[2], hh[3], hh[6], hh[7]. Outputs: Y = nets _037_. Recovered as module eq_const_h126, instance eq_const_h126_i. Role: datapath.
- h28: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets hh[6], hh[7]. Outputs: Y = nets _036_. Recovered as module eq_const_h28, instance eq_const_h28_i. Role: datapath.
- h125: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets hh[2], hh[3]. Outputs: Y = nets _035_. Recovered as module eq_const_h125, instance eq_const_h125_i. Role: datapath.
- h401: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _035_, _036_. Outputs: Y = nets _037_. Recovered as module eq_const_h401, instance eq_const_h401_i. Role: datapath.
- h510: 7 cells form a comparison against a constant, `Y = (A != 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets mm[5], mm[7], _033_, _060_. Outputs: Y = nets w11. Recovered as module eq_const_h510, instance eq_const_h510_i. Role: datapath.
- h509: 6 cells form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets mm[5], mm[7], _033_, _060_. Outputs: Y = nets w10. Recovered as module eq_const_h509, instance eq_const_h509_i. Role: datapath.
- h512: 7 cells form a comparison against a constant, `Y = (A != 6)`. Proved equivalent by truth table. Confidence 0.9979. Inputs: A = nets hh[0], hh[1], hh[4], hh[5], _037_. Outputs: Y = nets _047_. Recovered as module eq_const_h512, instance eq_const_h512_i. Role: datapath. Conflicts with 3 more not listed.
- h20: 12 cells form a 12-bit bus, `bus: 12 bits`. No proof recorded. Confidence 0.9234. Inputs: slice0 = nets _175_; slice1 = nets _120_; slice10 = nets w1; slice11 = nets w4; slice2 = nets _125_; slice3 = nets _072_; slice4 = nets _085_; slice5 = nets _093_; slice6 = nets _138_; slice7 = nets _147_; slice8 = nets _098_; slice9 = nets _176_. Role: datapath.
- h21: 11 cells form an 11-bit bus, `bus: 11 bits`. No proof recorded. Confidence 0.9234. Inputs: slice0 = nets hh[0]; slice1 = nets _113_; slice10 = nets w5; slice2 = nets hh[2]; slice3 = nets hh[4]; slice4 = nets hh[6]; slice5 = nets hh[7]; slice6 = nets mm[0]; slice7 = nets mm[2]; slice8 = nets mm[4]; slice9 = nets w17. Role: datapath.
- h139: 14 cells form a 14-bit bus, `bus: 14 bits`. No proof recorded. Confidence 0.9731. Inputs: ctrl = nets _090_; slice0 = nets w6; slice1 = nets _004_; slice10 = nets _140_; slice11 = nets _149_; slice12 = nets w18; slice13 = nets _163_; slice2 = nets w13; slice3 = nets w14; slice4 = nets w15; slice5 = nets _109_; slice6 = nets reset; slice7 = nets _119_; slice8 = nets _014_; slice9 = nets w16. Role: datapath.
- h143: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9644. Inputs: ctrl = nets _090_; slice0 = nets _206_; slice1 = nets _211_. Role: datapath.
- h148: 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.9227. Inputs: ctrl = nets _033_; slice0 = nets w10; slice1 = nets _066_; slice2 = nets _088_. Role: datapath.
- h154: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9002. Inputs: ctrl = nets _042_; slice0 = nets _113_; slice1 = nets _047_. Role: datapath.
- h155: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9315. Inputs: ctrl = nets _066_; slice0 = nets _067_; slice1 = nets _067_. Role: datapath.
- h164: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9002. Inputs: ctrl = nets _067_; slice0 = nets _066_; slice1 = nets _066_. Role: datapath.
- h167: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9315. Inputs: ctrl = nets _157_; slice0 = nets _160_; slice1 = nets _166_. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h19 (unconfirmed): 2 bits, bit order from wf: bit 0 = _169_; bit 1 = _167_.
- h20: 12 bits, bit order from wf: bit 0 = _175_; bit 1 = _120_; bit 2 = _125_; bit 3 = _072_; bit 4 = _085_; bit 5 = _093_; bit 6 = _138_; bit 7 = _147_; bit 8 = _098_; bit 9 = _176_; bit 10 = w1; bit 11 = w4.
- h21: 11 bits, bit order from wf: bit 0 = hh[0]; bit 1 = _113_; bit 2 = hh[2]; bit 3 = hh[4]; bit 4 = hh[6]; bit 5 = hh[7]; bit 6 = mm[0]; bit 7 = mm[2]; bit 8 = mm[4]; bit 9 = w17; bit 10 = w5.
- h22 (unconfirmed): 2 bits, bit order from wf: bit 0 = _181_; bit 1 = w7.
- h23 (unconfirmed): 2 bits, bit order from wf: bit 0 = _205_; bit 1 = _210_.
- h24 (unconfirmed): 3 bits, bit order from wf: bit 0 = _035_; bit 1 = w12; bit 2 = w8.
- h25 (unconfirmed): 3 bits, bit order from wf: bit 0 = _130_; bit 1 = _081_; bit 2 = _180_.
- h29 (unconfirmed): 2 bits, bit order from wf: bit 0 = _159_; bit 1 = _165_.
- h138 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w9; bit 1 = _189_.
- h139: 14 bits, bit order from net_id: bit 0 = w6; bit 1 = _004_; bit 2 = w13; bit 3 = w14; bit 4 = w15; bit 5 = _109_; bit 6 = reset; bit 7 = _119_; bit 8 = _014_; bit 9 = w16; bit 10 = _140_; bit 11 = _149_; bit 12 = w18; bit 13 = _163_.
- h141 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _066_; bit 1 = _056_.
- h142 (unconfirmed): 7 bits, bit order from net_id: bit 0 = _157_; bit 1 = _090_; bit 2 = _003_; bit 3 = _090_; bit 4 = _090_; bit 5 = _090_; bit 6 = _005_.
- h143: 2 bits, bit order from net_id: bit 0 = _206_; bit 1 = _211_.
- h147 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w10; bit 1 = _066_.
- h148: 3 bits, bit order from net_id: bit 0 = w10; bit 1 = _066_; bit 2 = _088_.
- h149 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _066_; bit 1 = _066_.
- h150 (unconfirmed): 3 bits, bit order from net_id: bit 0 = _044_; bit 1 = _113_; bit 2 = _066_.
- h152 (unconfirmed): 3 bits, bit order from net_id: bit 0 = w12; bit 1 = hh[4]; bit 2 = _083_.
- h153 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _042_; bit 1 = _066_.
- h154: 2 bits, bit order from net_id: bit 0 = _113_; bit 1 = _047_.
- h155: 2 bits, bit order from net_id: bit 0 = _067_; bit 1 = _067_.
- h156 (unconfirmed): 3 bits, bit order from net_id: bit 0 = _090_; bit 1 = _067_; bit 2 = _067_.
- h158 (unconfirmed): 2 bits, bit order from net_id: bit 0 = hh[4]; bit 1 = _066_.
- h159 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _083_; bit 1 = hh[5].
- h160 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _087_; bit 1 = _067_.
- h161 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _088_; bit 1 = _067_.
- h162 (unconfirmed): 2 bits, bit order from net_id: bit 0 = hh[7]; bit 1 = _066_.
- h163 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _104_; bit 1 = reset.
- h164: 2 bits, bit order from net_id: bit 0 = _066_; bit 1 = _066_.
- h166 (unconfirmed): 2 bits, bit order from net_id: bit 0 = reset; bit 1 = _152_.
- h167: 2 bits, bit order from net_id: bit 0 = _160_; bit 1 = _166_.
- h388 (unconfirmed): 11 bits, bit order from wf: bit 0 = _120_; bit 1 = _125_; bit 2 = _072_; bit 3 = _085_; bit 4 = _093_; bit 5 = _138_; bit 6 = _147_; bit 7 = _098_; bit 8 = _176_; bit 9 = w1; bit 10 = w4.
- h389 (unconfirmed): 10 bits, bit order from wf: bit 0 = _113_; bit 1 = hh[2]; bit 2 = hh[4]; bit 3 = hh[6]; bit 4 = hh[7]; bit 5 = mm[0]; bit 6 = mm[2]; bit 7 = mm[4]; bit 8 = w17; bit 9 = w5.
- h501 (unconfirmed): 2 bits, bit order from wf: bit 0 = w9; bit 1 = _120_.
- h502 (unconfirmed): 2 bits, bit order from wf: bit 0 = _072_; bit 1 = _120_.
- h505 (unconfirmed): 2 bits, bit order from wf: bit 0 = _072_; bit 1 = _085_.
- h506 (unconfirmed): 2 bits, bit order from wf: bit 0 = w12; bit 1 = _042_.
- h507 (unconfirmed): 2 bits, bit order from wf: bit 0 = hh[4]; bit 1 = hh[6].
- h508 (unconfirmed): 2 bits, bit order from wf: bit 0 = hh[4]; bit 1 = _113_.
- h554 (unconfirmed): 2 bits, bit order from wf: bit 0 = _081_; bit 1 = _085_.
- h574 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _066_; bit 1 = _088_.
- h575 (unconfirmed): 2 bits, bit order from net_id: bit 0 = hh[4]; bit 1 = _083_.

State machines:
- h5 (unconfirmed): state registers , 0 states, reset state 0, encoding unknown. 0 transitions.
- h11 (unconfirmed): state registers , 0 states, reset state 0, encoding unknown. 0 transitions.

Roles of committed claims: datapath: h20, h21, h26, h28, h117, h118, h119, h125, h126, h139, h143, h148, h154, h155, h164, h167, h395, h401, h509, h510, h512.

## 6. Candidates (not committed, unconfirmed)

- h50 (unconfirmed): 6 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _012_; en = nets _113_. Outputs: q = nets pm. Role: datapath.
- h51 (unconfirmed): 6 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _012_; en = nets _067_. Outputs: q = nets pm. Role: datapath.
- h30 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _000_; rst = nets _090_. Outputs: q = nets ss[4]. Role: datapath.
- h38 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _004_; rst = nets _090_. Outputs: q = nets hh[4]. Role: datapath.
- h40 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _006_; rst = nets _090_. Outputs: q = nets hh[6]. Role: datapath.
- h42 (unconfirmed): 7 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _007_; rst = nets _090_. Outputs: q = nets hh[7]. Role: datapath.
- h43 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _008_; rst = nets _090_. Outputs: q = nets mm[4]. Role: datapath.
- h49 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _011_; rst = nets _090_. Outputs: q = nets mm[7]. Role: datapath.
- h52 (unconfirmed): 6 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _012_; rst = nets _090_. Outputs: q = nets pm. Role: datapath.
- h53 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _013_; rst = nets _090_. Outputs: q = nets hh[0]. Role: datapath.
- h55 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _014_; rst = nets _090_. Outputs: q = nets hh[1]. Role: datapath.
- h56 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _015_; rst = nets _090_. Outputs: q = nets hh[2]. Role: datapath.
- h60 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _017_; rst = nets _090_. Outputs: q = nets mm[0]. Role: datapath.
- h64 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _019_; rst = nets _090_. Outputs: q = nets mm[2]. Role: datapath.
- h67 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _021_; rst = nets _090_. Outputs: q = nets ss[0]. Role: datapath.
- h72 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _023_; rst = nets _090_. Outputs: q = nets ss[2]. Role: datapath.
- h388 (unconfirmed): 11 cells form an 11-bit bus, `bus: 11 bits`. No proof recorded. Confidence 0.9234. Inputs: slice0 = nets _120_; slice1 = nets _125_; slice10 = nets w4; slice2 = nets _072_; slice3 = nets _085_; slice4 = nets _093_; slice5 = nets _138_; slice6 = nets _147_; slice7 = nets _098_; slice8 = nets _176_; slice9 = nets w1. Role: datapath.
- h389 (unconfirmed): 10 cells form a 10-bit bus, `bus: 10 bits`. No proof recorded. Confidence 0.9234. Inputs: slice0 = nets _113_; slice1 = nets hh[2]; slice2 = nets hh[4]; slice3 = nets hh[6]; slice4 = nets hh[7]; slice5 = nets mm[0]; slice6 = nets mm[2]; slice7 = nets mm[4]; slice8 = nets w17; slice9 = nets w5. Role: datapath.
- h150 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.8569. Inputs: ctrl = nets _120_; slice0 = nets _044_; slice1 = nets _113_; slice2 = nets _066_. Role: datapath.
- h152 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.8569. Inputs: ctrl = nets _072_; slice0 = nets w12; slice1 = nets hh[4]; slice2 = nets _083_. Role: datapath.
- h156 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.8569. Inputs: ctrl = nets _066_; slice0 = nets _090_; slice1 = nets _067_; slice2 = nets _067_. Role: datapath.
- h161 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.8191. Inputs: ctrl = nets _086_; slice0 = nets _088_; slice1 = nets _067_. Role: datapath.
- h163 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.8191. Inputs: ctrl = nets _090_; slice0 = nets _104_; slice1 = nets reset. Role: datapath.
- h166 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.8191. Inputs: ctrl = nets _090_; slice0 = nets reset; slice1 = nets _152_. Role: datapath.
- h6 (unconfirmed): 8 cells form a 2-bit register, `register: 2 bits`. No proof recorded. Confidence 0.8006. Inputs: clk = nets clk; d = nets _001_, _002_; rst = nets _090_. Outputs: q = nets ss[5], ss[6]. Role: datapath.
- h12 (unconfirmed): 8 cells form a 2-bit register, `register: 2 bits`. No proof recorded. Confidence 0.8006. Inputs: clk = nets clk; d = nets _009_, _010_; rst = nets _090_. Outputs: q = nets mm[5], mm[6]. Role: datapath.
- h142 (unconfirmed): 7 cells form a 7-bit bus, `bus: 7 bits`. No proof recorded. Confidence 0.7521. Inputs: ctrl = nets reset; slice0 = nets _157_; slice1 = nets _090_; slice2 = nets _003_; slice3 = nets _090_; slice4 = nets _090_; slice5 = nets _090_; slice6 = nets _005_. Role: datapath.
- h24 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _035_; slice1 = nets w12; slice2 = nets w8. Role: datapath.
- h25 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _130_; slice1 = nets _081_; slice2 = nets _180_. Role: datapath.
- h33 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _001_; rst = nets _090_. Outputs: q = nets ss[5]. Role: datapath.
- h35 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _002_; rst = nets _090_. Outputs: q = nets ss[6]. Role: datapath.
- h37 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _003_; rst = nets reset. Outputs: q = nets ss[7]. Role: datapath.
- h39 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _005_; rst = nets reset. Outputs: q = nets hh[5]. Role: datapath.
- h45 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _009_; rst = nets _090_. Outputs: q = nets mm[5]. Role: datapath.
- h47 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _010_; rst = nets _090_. Outputs: q = nets mm[6]. Role: datapath.
- h59 (unconfirmed): 7 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _016_; rst = nets reset. Outputs: q = nets hh[3]. Role: datapath.
- h63 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _018_; rst = nets _090_. Outputs: q = nets mm[1]. Role: datapath.
- h66 (unconfirmed): 6 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _020_; rst = nets _090_. Outputs: q = nets mm[3]. Role: datapath.
- h69 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _022_; rst = nets _157_. Outputs: q = nets ss[1]. Role: datapath.
- h73 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _024_; rst = nets _157_. Outputs: q = nets ss[3]. Role: datapath.
- h138 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _188_; slice0 = nets w9; slice1 = nets _189_. Role: datapath.
- h141 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _201_; slice0 = nets _066_; slice1 = nets _056_. Role: datapath.
- h147 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _063_; slice0 = nets w10; slice1 = nets _066_. Role: datapath.
- h149 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets w11; slice0 = nets _066_; slice1 = nets _066_. Role: datapath.
- h153 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _034_; slice0 = nets _042_; slice1 = nets _066_. Role: datapath.
- h159 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _081_; slice0 = nets _083_; slice1 = nets hh[5]. Role: datapath.
- h160 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _083_; slice0 = nets _087_; slice1 = nets _067_. Role: datapath.
- h162 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _093_; slice0 = nets hh[7]; slice1 = nets _066_. Role: datapath.
- h5 (unconfirmed): 9 cells form a finite state machine, `fsm: 2 bits`. No proof recorded. Confidence 0.6660. Inputs: d = nets _001_, _002_. Outputs: q = nets ss[5], ss[6]. Role: datapath.
- h11 (unconfirmed): 9 cells form a finite state machine, `fsm: 2 bits`. No proof recorded. Confidence 0.6660. Inputs: d = nets _009_, _010_. Outputs: q = nets mm[5], mm[6]. Role: datapath.
- h19 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _169_; slice1 = nets _167_. Role: datapath.
- h22 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _181_; slice1 = nets w7. Role: datapath.
- h23 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _205_; slice1 = nets _210_. Role: datapath.
- h29 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _159_; slice1 = nets _165_. Role: datapath.
- h158 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: ctrl = nets _067_; slice0 = nets hh[4]; slice1 = nets _066_. Role: datapath.
- h501 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w9; slice1 = nets _120_. Role: datapath.
- h502 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _072_; slice1 = nets _120_. Role: datapath.
- h505 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _072_; slice1 = nets _085_. Role: datapath.
- h506 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w12; slice1 = nets _042_. Role: datapath.
- h507 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets hh[4]; slice1 = nets hh[6]. Role: datapath.
- h508 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets hh[4]; slice1 = nets _113_. Role: datapath.
- h554 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _081_; slice1 = nets _085_. Role: datapath.
- h575 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: ctrl = nets _072_; slice0 = nets hh[4]; slice1 = nets _083_. Role: datapath.
- h1 (unconfirmed): 63 cells form a flip-flop with synchronous reset, `ff_srst: 14 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _012_, _013_, _014_, _015_, _004_, _006_, _007_, _017_, _019_, _008_, _011_, _021_, _023_, _000_; rst = nets _090_. Outputs: q = nets pm, hh[0], hh[1], hh[2], hh[4], hh[6], hh[7], mm[0], mm[2], mm[4], mm[7], ss[0], ss[2], ss[4]. Role: datapath.
- h4 (unconfirmed): 8 cells form a flip-flop with synchronous reset, `ff_srst: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _001_, _002_; rst = nets _090_. Outputs: q = nets ss[5], ss[6]. Role: datapath.
- h7 (unconfirmed): 17 cells form a flip-flop with synchronous reset, `ff_srst: 3 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _016_, _005_, _003_; rst = nets reset. Outputs: q = nets hh[3], hh[5], ss[7]. Role: datapath.
- h10 (unconfirmed): 8 cells form a flip-flop with synchronous reset, `ff_srst: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _009_, _010_; rst = nets _090_. Outputs: q = nets mm[5], mm[6]. Role: datapath.
- h13 (unconfirmed): 10 cells form a flip-flop with synchronous reset, `ff_srst: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _018_, _020_; rst = nets _090_. Outputs: q = nets mm[1], mm[3]. Role: datapath.
- h16 (unconfirmed): 9 cells form a flip-flop with synchronous reset, `ff_srst: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _022_, _024_; rst = nets _157_. Outputs: q = nets ss[1], ss[3]. Role: datapath.
- h574 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: ctrl = nets _033_; slice0 = nets _066_; slice1 = nets _088_. Role: datapath.

## 7. Rejected claims

(none)

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = NOT(ss[0])
- w2 = NOT(ena)
- w3 = NOT(_189_)
- w4 = NOT(ss[4])
- w5 = OR(NOT(w4), NOT(w3))
- w6 = OR(NOT(_090_), NOT(w5))
- w7 = NOT(ss[6])
- w8 = AND(NOT(ss[7]), NOT(w7))
- w9 = AND(NOT(_188_), NOT(hh[4]))
- w10 = AND(NOT(_033_), NOT(_063_))
- w11 = NOT(w10)
- w12 = AND(NOT(hh[5]), NOT(_072_))
- w13 = OR(NOT(_090_), NOT(hh[6]))
- w14 = OR(NOT(_090_), NOT(hh[7]))
- w15 = OR(NOT(_090_), NOT(mm[4]))
- w16 = OR(NOT(_090_), NOT(hh[2]))
- w17 = OR(NOT(w2), NOT(w1))
- w18 = OR(NOT(_090_), NOT(w17))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
