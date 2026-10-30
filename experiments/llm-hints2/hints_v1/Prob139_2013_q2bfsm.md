Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 8de53c8406e4, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| adder | 0 | 0 | 2 |
| adder_cin | 0 | 0 | 1 |
| bus | 1 | 13 | 0 |
| eq_const | 16 | 0 | 0 |
| ff_en | 0 | 1 | 0 |
| ff_srst | 0 | 7 | 0 |

Input cells (in Loki's re-mapped netlist): 34.

Of the committed cells, 2 (in 1 claims) are marked only by attributes on existing cells (form attrs). Those claims are not modules, so the hierarchy below does not show them.

Recovered module hierarchy (a module contains its children):

- h15 eq_const_h15 (eq_const)
- h31 eq_const_h31 (eq_const)
  - h30 eq_const_h30 (eq_const)
    - h7 eq_const_h7 (eq_const)
      - h29 eq_const_h29 (eq_const)
    - h108 eq_const_h108 (eq_const)
- h36 eq_const_h36 (eq_const)
  - h35 eq_const_h35 (eq_const)
  - h99 eq_const_h99 (eq_const)
- h39 eq_const_h39 (eq_const)
- h40 eq_const_h40 (eq_const)
- h41 eq_const_h41 (eq_const)
- h101 eq_const_h101 (eq_const)
- h115 eq_const_h115 (eq_const)
  - h116 eq_const_h116 (eq_const)
  - h119 eq_const_h119 (eq_const)

## 4. Committed claims

- h15: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets resetn, x. Outputs: Y = nets _23_. Recovered as module eq_const_h15, instance eq_const_h15_i. Role: datapath.
- h31: 4 cells form a comparison against a constant, `Y = (A != 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets state[1], state[4], state[6]. Outputs: Y = nets g. Recovered as module eq_const_h31, instance eq_const_h31_i. Role: datapath.
- h30: 3 cells form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets state[1], state[4], state[6]. Outputs: Y = nets _13_. Recovered as module eq_const_h30, instance eq_const_h30_i. Role: datapath.
- h7: 2 cells form a comparison against a constant, `Y = (A != 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets state[1], state[4]. Outputs: Y = nets w2. Recovered as module eq_const_h7, instance eq_const_h7_i. Role: datapath.
- h29: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets state[1], state[4]. Outputs: Y = nets w1. Recovered as module eq_const_h29, instance eq_const_h29_i. Role: datapath.
- h108: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets state[6], w2. Outputs: Y = nets _13_. Recovered as module eq_const_h108, instance eq_const_h108_i. Role: datapath.
- h36: 2 cells form a comparison against a constant, `Y = (A == 5)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets resetn, y, state[6]. Outputs: Y = nets _01_. Recovered as module eq_const_h36, instance eq_const_h36_i. Role: datapath.
- h35: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets resetn, state[6]. Outputs: Y = nets _25_. Recovered as module eq_const_h35, instance eq_const_h35_i. Role: datapath.
- h99: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets y, _25_. Outputs: Y = nets _01_. Recovered as module eq_const_h99, instance eq_const_h99_i. Role: datapath.
- h39: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets state[3], state[7]. Outputs: Y = nets _26_. Recovered as module eq_const_h39, instance eq_const_h39_i. Role: datapath.
- h40: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets y, state[1]. Outputs: Y = nets _14_. Recovered as module eq_const_h40, instance eq_const_h40_i. Role: datapath.
- h41: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets resetn, f. Outputs: Y = nets w5. Recovered as module eq_const_h41, instance eq_const_h41_i. Role: datapath.
- h101: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _23_, _26_. Outputs: Y = nets _04_. Recovered as module eq_const_h101, instance eq_const_h101_i. Role: datapath.
- h115: 2 cells form a comparison against a constant, `Y = (A == 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets resetn, g, _14_. Outputs: Y = nets _06_. Recovered as module eq_const_h115, instance eq_const_h115_i. Role: datapath.
- h116: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets resetn, g. Outputs: Y = nets w3. Recovered as module eq_const_h116, instance eq_const_h116_i. Role: datapath.
- h119: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets w3, _14_. Outputs: Y = nets _06_. Recovered as module eq_const_h119, instance eq_const_h119_i. Role: datapath.
- h50: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9002. Inputs: ctrl = nets _10_; slice0 = nets _03_; slice1 = nets _19_. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h8 (unconfirmed): 2 bits, bit order from wf: bit 0 = _13_; bit 1 = _26_.
- h11 (unconfirmed): 2 bits, bit order from wf: bit 0 = _05_; bit 1 = w4.
- h13 (unconfirmed): 2 bits, bit order from wf: bit 0 = _20_; bit 1 = _26_.
- h43 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _14_; bit 1 = w1.
- h44 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _25_; bit 1 = _13_.
- h45 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _23_; bit 1 = _20_.
- h47 (unconfirmed): 4 bits, bit order from net_id: bit 0 = _23_; bit 1 = w5; bit 2 = w3; bit 3 = _25_.
- h48 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _14_; bit 1 = _01_.
- h49 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _03_; bit 1 = _04_.
- h50: 2 bits, bit order from net_id: bit 0 = _03_; bit 1 = _19_.
- h102 (unconfirmed): 3 bits, bit order from net_id: bit 0 = _23_; bit 1 = w5; bit 2 = _25_.
- h106 (unconfirmed): 2 bits, bit order from wf: bit 0 = _13_; bit 1 = _06_.
- h107 (unconfirmed): 2 bits, bit order from wf: bit 0 = w4; bit 1 = _09_.
- h120 (unconfirmed): 3 bits, bit order from net_id: bit 0 = _23_; bit 1 = w5; bit 2 = w3.

State machines: none.

Roles of committed claims: datapath: h7, h15, h29, h30, h31, h35, h36, h39, h40, h41, h50, h99, h101, h108, h115, h116, h119.

## 6. Candidates (not committed, unconfirmed)

- h27 (unconfirmed): 3 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _04_; en = nets state[3]. Outputs: q = nets state[7]. Role: datapath.
- h16 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _06_; rst = nets resetn. Outputs: q = nets state[1]. Role: datapath.
- h21 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _01_; rst = nets resetn. Outputs: q = nets state[4]. Role: datapath.
- h28 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _04_; rst = nets _23_. Outputs: q = nets state[7]. Role: datapath.
- h43 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets state[1]; slice0 = nets _14_; slice1 = nets w1. Role: datapath.
- h44 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets state[6]; slice0 = nets _25_; slice1 = nets _13_. Role: datapath.
- h45 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets x; slice0 = nets _23_; slice1 = nets _20_. Role: datapath.
- h48 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets y; slice0 = nets _14_; slice1 = nets _01_. Role: datapath.
- h49 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _23_; slice0 = nets _03_; slice1 = nets _04_. Role: datapath.
- h95 (unconfirmed): 2 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _04_; rst = nets _23_. Outputs: q = nets state[7]. Role: datapath.
- h8 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _13_; slice1 = nets _26_. Role: datapath.
- h11 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _05_; slice1 = nets w4. Role: datapath.
- h13 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _20_; slice1 = nets _26_. Role: datapath.
- h106 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _13_; slice1 = nets _06_. Role: datapath.
- h107 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w4; slice1 = nets _09_. Role: datapath.
- h1 (unconfirmed): 7 cells form a flip-flop with synchronous reset, `ff_srst: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _06_, _01_; rst = nets resetn. Outputs: q = nets state[1], state[4]. Role: datapath.
- h3 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _03_, _04_; rst = nets _23_. Outputs: q = nets state[6], state[7]. Role: datapath.
- h47 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.5000. Inputs: ctrl = nets resetn; slice0 = nets _23_; slice1 = nets w5; slice2 = nets w3; slice3 = nets _25_. Role: datapath.
- h85 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _03_, _04_; rst = nets _23_. Outputs: q = nets state[6], state[7]. Role: datapath.
- h102 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.5000. Inputs: ctrl = nets resetn; slice0 = nets _23_; slice1 = nets w5; slice2 = nets _25_. Role: datapath.
- h120 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.5000. Inputs: ctrl = nets resetn; slice0 = nets _23_; slice1 = nets w5; slice2 = nets w3. Role: datapath.

## 7. Rejected claims

- h6: Loki tested a 2-bit adder with carry-in (`Y = A + B + CI`) on 9 cells and the proof showed it differs (truth_table), counterexample A[0]=1,A[1]=0,B[0]=0,B[1]=0,CI=0.
- h9: Loki tested a 2-bit adder (`Y = A + B`) on 5 cells and the proof showed it differs (truth_table), counterexample A[0]=0,A[1]=1,B[0]=0,B[1]=0.
- h14: Loki tested a 2-bit adder (`Y = A + B`) on 3 cells and the proof showed it differs (truth_table), counterexample A[0]=0,A[1]=0,B[0]=0,B[1]=0.

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = AND(NOT(state[4]), NOT(state[1]))
- w2 = NOT(w1)
- w3 = OR(NOT(resetn), NOT(g))
- w4 = NOT(state[3])
- w5 = OR(NOT(resetn), NOT(f))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
