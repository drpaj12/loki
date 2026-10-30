Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 fe4ec57b423a, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| bus | 0 | 4 | 0 |
| eq_const | 24 | 0 | 0 |
| register | 0 | 1 | 0 |

Input cells (in Loki's re-mapped netlist): 56.

Recovered module hierarchy (a module contains its children):

- h7 eq_const_h7 (eq_const)
- h8 eq_const_h8 (eq_const)
- h9 eq_const_h9 (eq_const)
- h10 eq_const_h10 (eq_const)
- h11 eq_const_h11 (eq_const)
- h12 eq_const_h12 (eq_const)
- h13 eq_const_h13 (eq_const)
- h14 eq_const_h14 (eq_const)
- h15 eq_const_h15 (eq_const)
- h16 eq_const_h16 (eq_const)
- h17 eq_const_h17 (eq_const)
- h18 eq_const_h18 (eq_const)
- h19 eq_const_h19 (eq_const)
- h20 eq_const_h20 (eq_const)
- h21 eq_const_h21 (eq_const)
- h22 eq_const_h22 (eq_const)
- h96 eq_const_h96 (eq_const)
- h97 eq_const_h97 (eq_const)
- h98 eq_const_h98 (eq_const)
- h99 eq_const_h99 (eq_const)
- h100 eq_const_h100 (eq_const)
- h101 eq_const_h101 (eq_const)
- h102 eq_const_h102 (eq_const)
- h103 eq_const_h103 (eq_const)

## 4. Committed claims

- h7: 3 cells form a comparison against a constant, `Y = (A == 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets in[0], d_last[0]. Outputs: Y = nets _03_. Recovered as module eq_const_h7, instance eq_const_h7_i. Role: datapath.
- h8: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets in[0], d_last[0]. Outputs: Y = nets _01_. Recovered as module eq_const_h8, instance eq_const_h8_i. Role: datapath.
- h9: 3 cells form a comparison against a constant, `Y = (A == 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets in[1], d_last[1]. Outputs: Y = nets _06_. Recovered as module eq_const_h9, instance eq_const_h9_i. Role: datapath.
- h10: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets in[1], d_last[1]. Outputs: Y = nets _04_. Recovered as module eq_const_h10, instance eq_const_h10_i. Role: datapath.
- h11: 3 cells form a comparison against a constant, `Y = (A == 3)`. Proof derived from h7 (proof transfer). Confidence 0.9999. Inputs: A = nets in[2], d_last[2]. Outputs: Y = nets _09_. Recovered as module eq_const_h11, instance eq_const_h11_i. Role: datapath.
- h12: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h8 (proof transfer). Confidence 0.9999. Inputs: A = nets in[2], d_last[2]. Outputs: Y = nets _07_. Recovered as module eq_const_h12, instance eq_const_h12_i. Role: datapath.
- h13: 3 cells form a comparison against a constant, `Y = (A == 3)`. Proof derived from h7 (proof transfer). Confidence 0.9999. Inputs: A = nets in[3], d_last[3]. Outputs: Y = nets _12_. Recovered as module eq_const_h13, instance eq_const_h13_i. Role: datapath.
- h14: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h8 (proof transfer). Confidence 0.9999. Inputs: A = nets in[3], d_last[3]. Outputs: Y = nets _10_. Recovered as module eq_const_h14, instance eq_const_h14_i. Role: datapath.
- h15: 3 cells form a comparison against a constant, `Y = (A == 3)`. Proof derived from h7 (proof transfer). Confidence 0.9999. Inputs: A = nets in[4], d_last[4]. Outputs: Y = nets _15_. Recovered as module eq_const_h15, instance eq_const_h15_i. Role: datapath.
- h16: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h8 (proof transfer). Confidence 0.9999. Inputs: A = nets in[4], d_last[4]. Outputs: Y = nets _13_. Recovered as module eq_const_h16, instance eq_const_h16_i. Role: datapath.
- h17: 3 cells form a comparison against a constant, `Y = (A == 3)`. Proof derived from h7 (proof transfer). Confidence 0.9999. Inputs: A = nets in[5], d_last[5]. Outputs: Y = nets _18_. Recovered as module eq_const_h17, instance eq_const_h17_i. Role: datapath.
- h18: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h8 (proof transfer). Confidence 0.9999. Inputs: A = nets in[5], d_last[5]. Outputs: Y = nets _16_. Recovered as module eq_const_h18, instance eq_const_h18_i. Role: datapath.
- h19: 3 cells form a comparison against a constant, `Y = (A == 3)`. Proof derived from h7 (proof transfer). Confidence 0.9999. Inputs: A = nets in[6], d_last[6]. Outputs: Y = nets _21_. Recovered as module eq_const_h19, instance eq_const_h19_i. Role: datapath.
- h20: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h8 (proof transfer). Confidence 0.9999. Inputs: A = nets in[6], d_last[6]. Outputs: Y = nets _19_. Recovered as module eq_const_h20, instance eq_const_h20_i. Role: datapath.
- h21: 3 cells form a comparison against a constant, `Y = (A == 3)`. Proof derived from h7 (proof transfer). Confidence 0.9999. Inputs: A = nets in[7], d_last[7]. Outputs: Y = nets _24_. Recovered as module eq_const_h21, instance eq_const_h21_i. Role: datapath.
- h22: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h8 (proof transfer). Confidence 0.9999. Inputs: A = nets in[7], d_last[7]. Outputs: Y = nets _22_. Recovered as module eq_const_h22, instance eq_const_h22_i. Role: datapath.
- h96: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _03_, _01_. Outputs: Y = nets _00_[0]. Recovered as module eq_const_h96, instance eq_const_h96_i. Role: datapath.
- h97: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _06_, _04_. Outputs: Y = nets _00_[1]. Recovered as module eq_const_h97, instance eq_const_h97_i. Role: datapath.
- h98: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h96 (proof transfer). Confidence 0.9999. Inputs: A = nets _09_, _07_. Outputs: Y = nets _00_[2]. Recovered as module eq_const_h98, instance eq_const_h98_i. Role: datapath.
- h99: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h96 (proof transfer). Confidence 0.9999. Inputs: A = nets _12_, _10_. Outputs: Y = nets _00_[3]. Recovered as module eq_const_h99, instance eq_const_h99_i. Role: datapath.
- h100: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h96 (proof transfer). Confidence 0.9999. Inputs: A = nets _15_, _13_. Outputs: Y = nets _00_[4]. Recovered as module eq_const_h100, instance eq_const_h100_i. Role: datapath.
- h101: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h96 (proof transfer). Confidence 0.9999. Inputs: A = nets _18_, _16_. Outputs: Y = nets _00_[5]. Recovered as module eq_const_h101, instance eq_const_h101_i. Role: datapath.
- h102: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h96 (proof transfer). Confidence 0.9999. Inputs: A = nets _21_, _19_. Outputs: Y = nets _00_[6]. Recovered as module eq_const_h102, instance eq_const_h102_i. Role: datapath.
- h103: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h96 (proof transfer). Confidence 0.9999. Inputs: A = nets _24_, _22_. Outputs: Y = nets _00_[7]. Recovered as module eq_const_h103, instance eq_const_h103_i. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h3 (unconfirmed): 8 bits, bit order from wf: bit 0 = w5; bit 1 = w7; bit 2 = w9; bit 3 = w11; bit 4 = w13; bit 5 = w15; bit 6 = w1; bit 7 = w3.
- h4 (unconfirmed): 8 bits, bit order from wf: bit 0 = w6; bit 1 = w8; bit 2 = w10; bit 3 = w12; bit 4 = w14; bit 5 = w16; bit 6 = w2; bit 7 = w4.
- h5 (unconfirmed): 8 bits, bit order from wf: bit 0 = _09_; bit 1 = _12_; bit 2 = _15_; bit 3 = _18_; bit 4 = _21_; bit 5 = _24_; bit 6 = _03_; bit 7 = _06_.
- h6 (unconfirmed): 8 bits, bit order from wf: bit 0 = _07_; bit 1 = _10_; bit 2 = _13_; bit 3 = _16_; bit 4 = _19_; bit 5 = _22_; bit 6 = _01_; bit 7 = _04_.

State machines: none.

Roles of committed claims: datapath: h7, h8, h9, h10, h11, h12, h13, h14, h15, h16, h17, h18, h19, h20, h21, h22, h96, h97, h98, h99, h100, h101, h102, h103.

## 6. Candidates (not committed, unconfirmed)

- h3 (unconfirmed): 8 cells form an 8-bit bus, `bus: 8 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets w5; slice1 = nets w7; slice2 = nets w9; slice3 = nets w11; slice4 = nets w13; slice5 = nets w15; slice6 = nets w1; slice7 = nets w3. Role: datapath.
- h4 (unconfirmed): 8 cells form an 8-bit bus, `bus: 8 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets w6; slice1 = nets w8; slice2 = nets w10; slice3 = nets w12; slice4 = nets w14; slice5 = nets w16; slice6 = nets w2; slice7 = nets w4. Role: datapath.
- h5 (unconfirmed): 8 cells form an 8-bit bus, `bus: 8 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _09_; slice1 = nets _12_; slice2 = nets _15_; slice3 = nets _18_; slice4 = nets _21_; slice5 = nets _24_; slice6 = nets _03_; slice7 = nets _06_. Role: datapath.
- h6 (unconfirmed): 8 cells form an 8-bit bus, `bus: 8 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _07_; slice1 = nets _10_; slice2 = nets _13_; slice3 = nets _16_; slice4 = nets _19_; slice5 = nets _22_; slice6 = nets _01_; slice7 = nets _04_. Role: datapath.
- h112 (unconfirmed): 8 cells form an 8-bit register, `register: 8 bits`. No proof recorded. Confidence 0.8006. Inputs: clk = nets clk; d = nets _00_[0], _00_[1], _00_[2], _00_[3], _00_[4], _00_[5], _00_[6], _00_[7]. Outputs: q = nets anyedge[0], anyedge[1], anyedge[2], anyedge[3], anyedge[4], anyedge[5], anyedge[6], anyedge[7]. Role: datapath.

## 7. Rejected claims

(none)

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = NOT(d_last[0])
- w2 = NOT(in[0])
- w3 = NOT(d_last[1])
- w4 = NOT(in[1])
- w5 = NOT(d_last[2])
- w6 = NOT(in[2])
- w7 = NOT(d_last[3])
- w8 = NOT(in[3])
- w9 = NOT(d_last[4])
- w10 = NOT(in[4])
- w11 = NOT(d_last[5])
- w12 = NOT(in[5])
- w13 = NOT(d_last[6])
- w14 = NOT(in[6])
- w15 = NOT(d_last[7])
- w16 = NOT(in[7])
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
