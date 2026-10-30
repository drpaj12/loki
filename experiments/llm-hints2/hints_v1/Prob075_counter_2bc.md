Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 9edf501299c8, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| adder | 0 | 0 | 1 |
| adder_cin | 0 | 0 | 2 |
| bus | 0 | 8 | 0 |
| eq_const | 1 | 0 | 4 |
| subtractor | 0 | 0 | 1 |

Input cells (in Loki's re-mapped netlist): 16.

Recovered module hierarchy (a module contains its children):

- h7 eq_const_h7 (eq_const)

## 4. Committed claims

- h7: 2 cells form a comparison against a constant, `Y = (A != 1)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets train_valid, train_taken. Outputs: Y = nets _08_. Recovered as module eq_const_h7, instance eq_const_h7_i. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h3 (unconfirmed): 2 bits, bit order from wf: bit 0 = _11_; bit 1 = _10_.
- h4 (unconfirmed): 2 bits, bit order from wf: bit 0 = w2; bit 1 = _08_.
- h5 (unconfirmed): 2 bits, bit order from wf: bit 0 = w3; bit 1 = w6.
- h6 (unconfirmed): 2 bits, bit order from wf: bit 0 = _08_; bit 1 = w5.
- h11 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w5; bit 1 = w1.
- h12 (unconfirmed): 3 bits, bit order from net_id: bit 0 = w5; bit 1 = w7; bit 2 = w3.
- h13 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w7; bit 1 = w4.
- h77 (unconfirmed): 2 bits, bit order from wf: bit 0 = w2; bit 1 = w6.

State machines: none.

Roles of committed claims: datapath: h7.

## 6. Candidates (not committed, unconfirmed)

- h11 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _10_; slice0 = nets w5; slice1 = nets w1. Role: datapath.
- h12 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets state[0]; slice0 = nets w5; slice1 = nets w7; slice2 = nets w3. Role: datapath.
- h13 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets w1; slice0 = nets w7; slice1 = nets w4. Role: datapath.
- h3 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _11_; slice1 = nets _10_. Role: datapath.
- h4 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w2; slice1 = nets _08_. Role: datapath.
- h5 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w3; slice1 = nets w6. Role: datapath.
- h6 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _08_; slice1 = nets w5. Role: datapath.
- h77 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w2; slice1 = nets w6. Role: datapath.

## 7. Rejected claims

- h1: Loki tested a 2-bit adder (`Y = A + B`) on 13 cells and the proof showed it differs (truth_table), counterexample A[0]=0,A[1]=0,B[0]=0,B[1]=0.
- h2: Loki tested a 2-bit subtractor (`Y = A - B`) on 13 cells and the proof showed it differs (truth_table), counterexample A[0]=0,A[1]=0,B[0]=0,B[1]=0.
- h8: Loki proposed a comparison against a constant (`Y = (A == 0)`) on 1 cell; rejected: commit failed: ODIN3_ERR_INVALID_ARG.
- h9: Loki proposed a comparison against a constant (`Y = (A != 2)`) on 2 cells; rejected: commit failed: ODIN3_ERR_INVALID_ARG.
- h10: Loki proposed a comparison against a constant (`Y = (A != 3)`) on 1 cell; rejected: commit failed: ODIN3_ERR_INVALID_ARG.
- h75: Loki tested a 2-bit adder with carry-in (`Y = A + B + CI`) on 6 cells and the proof showed it differs (truth_table), counterexample A[0]=1,A[1]=0,B[0]=0,B[1]=0,CI=0.
- h76: Loki tested a 2-bit adder with carry-in (`Y = A + B + CI`) on 8 cells and the proof showed it differs (truth_table), counterexample A[0]=0,A[1]=0,B[0]=0,B[1]=0,CI=0.
- h78: Loki proposed a comparison against a constant (`Y = (A != 3)`) on 1 cell; rejected: commit failed: ODIN3_ERR_INVALID_ARG.

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = AND(NOT(_11_), NOT(_10_))
- w2 = OR(NOT(train_taken), NOT(state[1]))
- w3 = OR(NOT(state[0]), NOT(w2))
- w4 = OR(NOT(w3), NOT(w1))
- w5 = OR(NOT(_10_), NOT(state[0]))
- w6 = OR(NOT(state[1]), NOT(_08_))
- w7 = OR(NOT(state[0]), NOT(w1))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
