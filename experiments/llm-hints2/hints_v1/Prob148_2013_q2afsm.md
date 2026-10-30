Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 58de63bb291a, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| adder | 1 | 0 | 2 |
| bus | 0 | 19 | 0 |
| datapath_unit | 1 | 0 | 0 |
| eq_const | 8 | 0 | 0 |
| ff_srst | 0 | 5 | 0 |
| fsm | 0 | 1 | 0 |

Input cells (in Loki's re-mapped netlist): 31.

Recovered module hierarchy (a module contains its children):

- h129 datapath_unit_h129 (datapath_unit)
  - h4 adder_h4 (adder)
    - h8 eq_const_h8 (eq_const)
    - h10 eq_const_h10 (eq_const)
  - h41 eq_const_h41 (eq_const)
  - h95 eq_const_h95 (eq_const)
  - h108 eq_const_h108 (eq_const)
  - h109 eq_const_h109 (eq_const)
  - h114 eq_const_h114 (eq_const)
  - h116 eq_const_h116 (eq_const)

## 4. Committed claims

- h129: 31 cells form a datapath unit, `datapath_unit: 4 bits`. No proof recorded. Confidence 0.9879. Inputs: in = nets resetn, r[0], r[1], r[2]; out = nets g[0], g[1], g[2]. Recovered as module datapath_unit_h129, instance datapath_unit_h129_i. Role: datapath.
- h4: 3 cells form a 2-bit adder, `Y = A + B`. No proof recorded. Confidence 0.9474. Inputs: A = nets g[0], resetn; B = nets state[0], r[0]. Outputs: Y = nets w1, _00_. Recovered as module adder_h4, instance adder_h4_i. Role: datapath.
- h8: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets resetn, r[0]. Outputs: Y = nets _25_. Recovered as module eq_const_h8, instance eq_const_h8_i. Role: datapath.
- h10: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets g[0], state[0]. Outputs: Y = nets w1. Recovered as module eq_const_h10, instance eq_const_h10_i. Role: datapath.
- h41: 3 cells form a comparison against a constant, `Y = (A != 5)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets resetn, r[0], state[0]. Outputs: Y = nets _08_. Recovered as module eq_const_h41, instance eq_const_h41_i. Role: datapath.
- h95: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proved equivalent by truth table. Confidence 0.9975. Inputs: A = nets g[1], _06_. Outputs: Y = nets w10. Recovered as module eq_const_h95, instance eq_const_h95_i. Role: datapath. Conflicts with 12 more not listed.
- h108: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets r[1], _08_. Outputs: Y = nets _22_. Recovered as module eq_const_h108, instance eq_const_h108_i. Role: datapath.
- h109: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets g[2], _06_. Outputs: Y = nets w13. Recovered as module eq_const_h109, instance eq_const_h109_i. Role: datapath.
- h114: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets r[1], w4. Outputs: Y = nets w5. Recovered as module eq_const_h114, instance eq_const_h114_i. Role: datapath.
- h116: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _22_, w13. Outputs: Y = nets w14. Recovered as module eq_const_h116, instance eq_const_h116_i. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h6 (unconfirmed): 2 bits, bit order from wf: bit 0 = _25_; bit 1 = _08_.
- h7 (unconfirmed): 3 bits, bit order from wf: bit 0 = _25_; bit 1 = _08_; bit 2 = w2.
- h9 (unconfirmed): 2 bits, bit order from wf: bit 0 = _07_; bit 1 = w1.
- h11 (unconfirmed): 2 bits, bit order from wf: bit 0 = _00_; bit 1 = _22_.
- h12 (unconfirmed): 3 bits, bit order from wf: bit 0 = _06_; bit 1 = _04_; bit 2 = _05_.
- h15 (unconfirmed): 2 bits, bit order from wf: bit 0 = _06_; bit 1 = _04_.
- h16 (unconfirmed): 2 bits, bit order from wf: bit 0 = _06_; bit 1 = w7.
- h45 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _25_; bit 1 = _07_.
- h46 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w1; bit 1 = _08_.
- h47 (unconfirmed): 3 bits, bit order from net_id: bit 0 = w2; bit 1 = w6; bit 2 = _03_.
- h48 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w5; bit 1 = _22_.
- h49 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w5; bit 1 = w10.
- h50 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w6; bit 1 = _02_.
- h51 (unconfirmed): 3 bits, bit order from net_id: bit 0 = _07_; bit 1 = w10; bit 2 = w13.
- h52 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _08_; bit 1 = w9.
- h93 (unconfirmed): 2 bits, bit order from wf: bit 0 = w4; bit 1 = w11.
- h94 (unconfirmed): 2 bits, bit order from wf: bit 0 = w4; bit 1 = _04_.
- h110 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w10; bit 1 = w13.
- h122 (unconfirmed): 2 bits, bit order from wf: bit 0 = w3; bit 1 = _01_.

State machines:
- h2 (unconfirmed): state registers , 0 states, reset state 0, encoding unknown. 0 transitions.

Roles of committed claims: datapath: h4, h8, h10, h41, h95, h108, h109, h114, h116, h129.

## 6. Candidates (not committed, unconfirmed)

- h47 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.8569. Inputs: ctrl = nets _05_; slice0 = nets w2; slice1 = nets w6; slice2 = nets _03_. Role: datapath.
- h51 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.8569. Inputs: ctrl = nets _06_; slice0 = nets _07_; slice1 = nets w10; slice2 = nets w13. Role: datapath.
- h7 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _25_; slice1 = nets _08_; slice2 = nets w2. Role: datapath.
- h12 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _06_; slice1 = nets _04_; slice2 = nets _05_. Role: datapath.
- h21 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _00_; rst = nets resetn. Outputs: q = nets g[0]. Role: datapath.
- h45 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets r[0]; slice0 = nets _25_; slice1 = nets _07_. Role: datapath.
- h46 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets state[0]; slice0 = nets w1; slice1 = nets _08_. Role: datapath.
- h49 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets w4; slice0 = nets w5; slice1 = nets w10. Role: datapath.
- h50 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _04_; slice0 = nets w6; slice1 = nets _02_. Role: datapath.
- h52 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _07_; slice0 = nets _08_; slice1 = nets w9. Role: datapath.
- h6 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _25_; slice1 = nets _08_. Role: datapath.
- h9 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _07_; slice1 = nets w1. Role: datapath.
- h11 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _00_; slice1 = nets _22_. Role: datapath.
- h15 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _06_; slice1 = nets _04_. Role: datapath.
- h16 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _06_; slice1 = nets w7. Role: datapath.
- h48 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: ctrl = nets r[1]; slice0 = nets w5; slice1 = nets _22_. Role: datapath.
- h93 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w4; slice1 = nets w11. Role: datapath.
- h94 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w4; slice1 = nets _04_. Role: datapath.
- h110 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: ctrl = nets _06_; slice0 = nets w10; slice1 = nets w13. Role: datapath.
- h122 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w3; slice1 = nets _01_. Role: datapath.
- h2 (unconfirmed): 14 cells form a finite state machine, `fsm: 2 bits`. No proof recorded. Confidence 0.5525. Inputs: d = nets _00_, _01_. Outputs: q = nets g[0], state[0]. Role: datapath. Conflicts with 1 more not listed.
- h1 (unconfirmed): 11 cells form a flip-flop with synchronous reset, `ff_srst: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _00_, _01_; rst = nets resetn. Outputs: q = nets g[0], state[0]. Role: datapath.
- h119 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.5000. Inputs: rst = nets _04_. Role: datapath.
- h120 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.5000. Inputs: rst = nets _05_. Role: datapath.
- h130 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.5000. Inputs: rst = nets _05_. Role: datapath.

## 7. Rejected claims

- h5: Loki tested a 3-bit adder (`Y = A + B`) on 10 cells and the proof showed it differs (truth_table), counterexample A[0]=0,A[1]=0,A[2]=0,B[0]=0,B[1]=0,B[2]=0.
- h84: Loki tested a 3-bit adder (`Y = A + B`) on 9 cells and the proof showed it differs (truth_table), counterexample A[0]=0,A[1]=1,A[2]=0,B[0]=0,B[1]=0,B[2]=0.

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = AND(NOT(g[0]), NOT(state[0]))
- w2 = OR(NOT(_05_), NOT(g[2]))
- w3 = OR(NOT(resetn), NOT(w2))
- w4 = NOT(g[1])
- w5 = AND(NOT(w4), NOT(r[1]))
- w6 = OR(NOT(_04_), NOT(_05_))
- w7 = NOT(g[0])
- w8 = OR(NOT(w7), NOT(w6))
- w9 = OR(NOT(_07_), NOT(w8))
- w10 = AND(NOT(w4), NOT(_06_))
- w11 = NOT(_08_)
- w12 = NOT(g[2])
- w13 = AND(NOT(w12), NOT(_06_))
- w14 = AND(NOT(_22_), NOT(w13))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
