Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 0dac543d6997, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| adder | 0 | 0 | 1 |
| adder_cin | 0 | 0 | 1 |
| bus | 0 | 1 | 0 |
| eq_const | 9 | 0 | 0 |

Input cells (in Loki's re-mapped netlist): 13.

Recovered module hierarchy (a module contains its children):

- h2 eq_const_h2 (eq_const)
  - h1 eq_const_h1 (eq_const)
- h4 eq_const_h4 (eq_const)
  - h3 eq_const_h3 (eq_const)
  - h21 eq_const_h21 (eq_const)
- h24 eq_const_h24 (eq_const)
- h27 eq_const_h27 (eq_const)
- h30 eq_const_h30 (eq_const)
- h32 eq_const_h32 (eq_const)

## 4. Committed claims

- h2: 3 cells form a comparison against a constant, `Y = (A != 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets a, b, state. Outputs: Y = nets w7. Recovered as module eq_const_h2, instance eq_const_h2_i. Role: datapath.
- h1: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets b, state. Outputs: Y = nets w1. Recovered as module eq_const_h1, instance eq_const_h1_i. Role: datapath.
- h4: 4 cells form a comparison against a constant, `Y = (A != 7)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets a, b, state. Outputs: Y = nets w9. Recovered as module eq_const_h4, instance eq_const_h4_i. Role: datapath.
- h3: 3 cells form a comparison against a constant, `Y = (A == 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets b, state. Outputs: Y = nets w5. Recovered as module eq_const_h3, instance eq_const_h3_i. Role: datapath.
- h21: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets a, w5. Outputs: Y = nets w9. Recovered as module eq_const_h21, instance eq_const_h21_i. Role: datapath.
- h24: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets w1, _07_. Outputs: Y = nets w2. Recovered as module eq_const_h24, instance eq_const_h24_i. Role: datapath.
- h27: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets w2, w5. Outputs: Y = nets w6. Recovered as module eq_const_h27, instance eq_const_h27_i. Role: datapath.
- h30: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets w6, w7. Outputs: Y = nets w8. Recovered as module eq_const_h30, instance eq_const_h30_i. Role: datapath.
- h32: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets w8, w9. Outputs: Y = nets q. Recovered as module eq_const_h32, instance eq_const_h32_i. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h5 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w9; bit 1 = w6.

State machines: none.

Roles of committed claims: datapath: h1, h2, h3, h4, h21, h24, h27, h30, h32.

## 6. Candidates (not committed, unconfirmed)

- h5 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets w5; slice0 = nets w9; slice1 = nets w6. Role: datapath.

## 7. Rejected claims

- h23: Loki tested a 2-bit adder with carry-in (`Y = A + B + CI`) on 5 cells and the proof showed it differs (truth_table), counterexample A[0]=0,A[1]=0,B[0]=0,B[1]=0,CI=0.
- h26: Loki tested a 2-bit adder (`Y = A + B`) on 4 cells and the proof showed it differs (cone_check), counterexample A[0]=0,A[1]=0,B[0]=0,B[1]=0.

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = AND(NOT(state), NOT(b))
- w2 = AND(NOT(w1), NOT(_07_))
- w3 = NOT(state)
- w4 = NOT(b)
- w5 = AND(NOT(w3), NOT(w4))
- w6 = AND(NOT(w2), NOT(w5))
- w7 = OR(NOT(_07_), NOT(w1))
- w8 = OR(NOT(w7), NOT(w6))
- w9 = OR(NOT(a), NOT(w5))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
