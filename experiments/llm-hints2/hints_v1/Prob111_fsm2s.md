Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 738e5f3dff64, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| bus | 0 | 1 | 0 |
| eq_const | 4 | 0 | 0 |
| ff_srst | 0 | 2 | 0 |
| subtractor | 0 | 0 | 1 |

Input cells (in Loki's re-mapped netlist): 7.

Recovered module hierarchy (a module contains its children):

- h4 eq_const_h4 (eq_const)
- h5 eq_const_h5 (eq_const)
- h14 eq_const_h14 (eq_const)
- h19 eq_const_h19 (eq_const)

## 4. Committed claims

- h4: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets k, out. Outputs: Y = nets w2. Recovered as module eq_const_h4, instance eq_const_h4_i. Role: datapath.
- h5: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets j, out. Outputs: Y = nets w4. Recovered as module eq_const_h5, instance eq_const_h5_i. Role: datapath.
- h14: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets w2, w4. Outputs: Y = nets w5. Recovered as module eq_const_h14, instance eq_const_h14_i. Role: datapath.
- h19: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, w5. Outputs: Y = nets _00_. Recovered as module eq_const_h19, instance eq_const_h19_i. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h2 (unconfirmed): 2 bits, bit order from wf: bit 0 = w4; bit 1 = _00_.

State machines: none.

Roles of committed claims: datapath: h4, h5, h14, h19.

## 6. Candidates (not committed, unconfirmed)

- h2 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w4; slice1 = nets _00_. Role: datapath.
- h16 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.5000. Inputs: rst = nets reset. Role: datapath.
- h21 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.5000. Inputs: rst = nets reset. Role: datapath.

## 7. Rejected claims

- h1: Loki tested a 2-bit subtractor (`Y = A - B`) on 6 cells and the proof showed it differs (truth_table), counterexample A[0]=1,A[1]=0,B[0]=0,B[1]=0.

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = NOT(out)
- w2 = AND(NOT(w1), NOT(k))
- w3 = NOT(j)
- w4 = AND(NOT(out), NOT(w3))
- w5 = AND(NOT(w2), NOT(w4))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
