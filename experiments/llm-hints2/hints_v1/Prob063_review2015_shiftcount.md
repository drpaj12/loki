Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 3c0e08a43176, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| adder | 0 | 0 | 1 |
| bus | 3 | 23 | 0 |
| eq_const | 3 | 0 | 0 |
| ff_srst | 0 | 1 | 0 |
| subtractor | 0 | 0 | 1 |

Input cells (in Loki's re-mapped netlist): 40.

Of the committed cells, 8 (in 3 claims) are marked only by attributes on existing cells (form attrs). Those claims are not modules, so the hierarchy below does not show them.

Recovered module hierarchy (a module contains its children):

- h14 eq_const_h14 (eq_const)
  - h28 eq_const_h28 (eq_const)
- h16 eq_const_h16 (eq_const)

## 4. Committed claims

- h14: 2 cells form a comparison against a constant, `Y = (A != 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets shift_ena, count_ena. Outputs: Y = nets w7. Recovered as module eq_const_h14, instance eq_const_h14_i. Role: datapath.
- h28: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets shift_ena, count_ena. Outputs: Y = nets _23_. Recovered as module eq_const_h28, instance eq_const_h28_i. Role: datapath.
- h16: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets shift_ena, data. Outputs: Y = nets _28_. Recovered as module eq_const_h16, instance eq_const_h16_i. Role: datapath.
- h66: 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w1; slice0 = nets w3; slice1 = nets w12; slice2 = nets _35_. Role: datapath.
- h68: 5 cells form a 5-bit bus, `bus: 5 bits`. No proof recorded. Confidence 0.9234. Inputs: ctrl = nets _06_; slice0 = nets _17_; slice1 = nets _08_; slice2 = nets w12; slice3 = nets w6; slice4 = nets w5. Role: datapath.
- h72: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9002. Inputs: ctrl = nets _31_; slice0 = nets _35_; slice1 = nets _32_. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h3 (unconfirmed): 3 bits, bit order from wf: bit 0 = w2; bit 1 = w1; bit 2 = _04_.
- h6 (unconfirmed): 2 bits, bit order from wf: bit 0 = _07_; bit 1 = w2.
- h8 (unconfirmed): 2 bits, bit order from wf: bit 0 = _06_; bit 1 = _07_.
- h9 (unconfirmed): 2 bits, bit order from wf: bit 0 = w4; bit 1 = _30_.
- h11 (unconfirmed): 3 bits, bit order from wf: bit 0 = _31_; bit 1 = _08_; bit 2 = w8.
- h12 (unconfirmed): 3 bits, bit order from wf: bit 0 = _32_; bit 1 = _00_; bit 2 = w9.
- h13 (unconfirmed): 2 bits, bit order from wf: bit 0 = _23_; bit 1 = _31_.
- h15 (unconfirmed): 2 bits, bit order from wf: bit 0 = _28_; bit 1 = _17_.
- h66: 3 bits, bit order from net_id: bit 0 = w3; bit 1 = w12; bit 2 = _35_.
- h67 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w8; bit 1 = w4.
- h68: 5 bits, bit order from net_id: bit 0 = _17_; bit 1 = _08_; bit 2 = w12; bit 3 = w6; bit 4 = w5.
- h69 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _23_; bit 1 = _28_.
- h71 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _31_; bit 1 = w10.
- h72: 2 bits, bit order from net_id: bit 0 = _35_; bit 1 = _32_.
- h114 (unconfirmed): 2 bits, bit order from wf: bit 0 = w1; bit 1 = _06_.
- h115 (unconfirmed): 2 bits, bit order from wf: bit 0 = w1; bit 1 = w2.
- h118 (unconfirmed): 2 bits, bit order from wf: bit 0 = w2; bit 1 = w7.
- h119 (unconfirmed): 2 bits, bit order from wf: bit 0 = w2; bit 1 = _06_.
- h122 (unconfirmed): 2 bits, bit order from wf: bit 0 = w7; bit 1 = _07_.
- h123 (unconfirmed): 2 bits, bit order from wf: bit 0 = w7; bit 1 = _04_.
- h125 (unconfirmed): 2 bits, bit order from wf: bit 0 = w11; bit 1 = _12_.
- h126 (unconfirmed): 2 bits, bit order from wf: bit 0 = _06_; bit 1 = w7.
- h127 (unconfirmed): 2 bits, bit order from wf: bit 0 = _05_; bit 1 = _06_.
- h128 (unconfirmed): 2 bits, bit order from wf: bit 0 = _08_; bit 1 = _31_.
- h129 (unconfirmed): 2 bits, bit order from wf: bit 0 = _00_; bit 1 = _32_.
- h190 (unconfirmed): 2 bits, bit order from wf: bit 0 = w11; bit 1 = _17_.

State machines: none.

Roles of committed claims: datapath: h14, h16, h28, h66, h68, h72.

## 6. Candidates (not committed, unconfirmed)

- h3 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets w2; slice1 = nets w1; slice2 = nets _04_. Role: datapath.
- h11 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _31_; slice1 = nets _08_; slice2 = nets w8. Role: datapath.
- h12 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _32_; slice1 = nets _00_; slice2 = nets w9. Role: datapath.
- h67 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets w3; slice0 = nets w8; slice1 = nets w4. Role: datapath.
- h71 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _17_; slice0 = nets _31_; slice1 = nets w10. Role: datapath.
- h6 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _07_; slice1 = nets w2. Role: datapath.
- h8 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _06_; slice1 = nets _07_. Role: datapath.
- h9 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w4; slice1 = nets _30_. Role: datapath.
- h13 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _23_; slice1 = nets _31_. Role: datapath.
- h15 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _28_; slice1 = nets _17_. Role: datapath.
- h69 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: ctrl = nets shift_ena; slice0 = nets _23_; slice1 = nets _28_. Role: datapath.
- h114 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w1; slice1 = nets _06_. Role: datapath.
- h115 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w1; slice1 = nets w2. Role: datapath.
- h118 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w2; slice1 = nets w7. Role: datapath.
- h119 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w2; slice1 = nets _06_. Role: datapath.
- h122 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w7; slice1 = nets _07_. Role: datapath.
- h123 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w7; slice1 = nets _04_. Role: datapath.
- h125 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w11; slice1 = nets _12_. Role: datapath.
- h126 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _06_; slice1 = nets w7. Role: datapath.
- h127 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _05_; slice1 = nets _06_. Role: datapath.
- h128 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _08_; slice1 = nets _31_. Role: datapath.
- h129 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _00_; slice1 = nets _32_. Role: datapath.
- h190 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w11; slice1 = nets _17_. Role: datapath.
- h184 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.5000. Inputs: rst = nets _31_. Role: datapath.

## 7. Rejected claims

- h5: Loki tested a 2-bit adder (`Y = A + B`) on 10 cells and the proof showed it differs (truth_table), counterexample A[0]=0,A[1]=0,B[0]=0,B[1]=0.
- h7: Loki tested a 2-bit subtractor (`Y = A - B`) on 10 cells and the proof showed it differs (truth_table), counterexample A[0]=0,A[1]=0,B[0]=0,B[1]=0.

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = NOT(q[1])
- w2 = NOT(q[0])
- w3 = OR(NOT(w2), NOT(w1))
- w4 = AND(NOT(w3), NOT(_07_))
- w5 = OR(NOT(_06_), NOT(_12_))
- w6 = AND(NOT(_04_), NOT(_06_))
- w7 = NOT(_23_)
- w8 = AND(NOT(w3), NOT(q[2]))
- w9 = AND(NOT(w8), NOT(q[3]))
- w10 = AND(NOT(w9), NOT(_17_))
- w11 = OR(NOT(w2), NOT(w7))
- w12 = OR(NOT(_06_), NOT(w1))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
