Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 05c2441a6c43, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| eq_const | 3 | 0 | 0 |

Input cells (in Loki's re-mapped netlist): 6.

Recovered module hierarchy (a module contains its children):

- h1 eq_const_h1 (eq_const)
- h2 eq_const_h2 (eq_const)
- h9 eq_const_h9 (eq_const)

## 4. Committed claims

- h1: 2 cells form a comparison against a constant, `Y = (A != 2)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets clk, qn. Outputs: Y = nets _2_. Recovered as module eq_const_h1, instance eq_const_h1_i. Role: datapath.
- h2: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets clk, qp. Outputs: Y = nets _1_. Recovered as module eq_const_h2, instance eq_const_h2_i. Role: datapath.
- h9: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _2_, _1_. Outputs: Y = nets q. Recovered as module eq_const_h9, instance eq_const_h9_i. Role: datapath.

## 5. Buses, state machines and roles

Buses: none.

State machines: none.

Roles of committed claims: datapath: h1, h2, h9.

## 6. Candidates (not committed, unconfirmed)

(none)

## 7. Rejected claims

(none)

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
