Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 224f2218c3a7, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| eq_const | 5 | 0 | 0 |
| ff_en | 0 | 1 | 0 |
| ff_srst | 0 | 2 | 0 |

Input cells (in Loki's re-mapped netlist): 5.

Recovered module hierarchy (a module contains its children):

- h3 eq_const_h3 (eq_const)
- h4 eq_const_h4 (eq_const)
- h14 eq_const_h14 (eq_const)
  - h13 eq_const_h13 (eq_const)
  - h19 eq_const_h19 (eq_const)

## 4. Committed claims

- h3: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets in, out. Outputs: Y = nets w1. Recovered as module eq_const_h3, instance eq_const_h3_i. Role: datapath.
- h4: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets in, out. Outputs: Y = nets w3. Recovered as module eq_const_h4, instance eq_const_h4_i. Role: datapath.
- h14: 2 cells form a comparison against a constant, `Y = (A != 4)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, w1, w3. Outputs: Y = nets _0_. Recovered as module eq_const_h14, instance eq_const_h14_i. Role: datapath.
- h13: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, w1. Outputs: Y = nets w2. Recovered as module eq_const_h13, instance eq_const_h13_i. Role: datapath.
- h19: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets w2, w3. Outputs: Y = nets _0_. Recovered as module eq_const_h19, instance eq_const_h19_i. Role: datapath.

## 5. Buses, state machines and roles

Buses: none.

State machines: none.

Roles of committed claims: datapath: h3, h4, h13, h14, h19.

## 6. Candidates (not committed, unconfirmed)

- h1 (unconfirmed): 5 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _0_; en = nets in. Outputs: q = nets out. Role: datapath.
- h16 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.5000. Inputs: rst = nets reset. Role: datapath.
- h21 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.5000. Inputs: rst = nets w3. Role: datapath.

## 7. Rejected claims

(none)

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = AND(NOT(out), NOT(in))
- w2 = AND(NOT(w1), NOT(reset))
- w3 = OR(NOT(in), NOT(out))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
