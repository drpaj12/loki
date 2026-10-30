Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 1e1699f817b3, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| bus | 2 | 4 | 0 |
| datapath_unit | 1 | 0 | 0 |
| eq_const | 2 | 0 | 0 |
| ff_srst | 0 | 4 | 0 |
| fsm | 1 | 0 | 0 |

Input cells (in Loki's re-mapped netlist): 28.

Of the committed cells, 5 (in 2 claims) are marked only by attributes on existing cells (form attrs). Those claims are not modules, so the hierarchy below does not show them.

Recovered module hierarchy (a module contains its children):

- h61 datapath_unit_h61 (datapath_unit)
  - h2 fsm_h2 (fsm)
    - h22 eq_const_h22 (eq_const)
  - h14 eq_const_h14 (eq_const)

## 4. Committed claims

- h61: 28 cells form a datapath unit, `datapath_unit: 4 bits`. No proof recorded. Confidence 0.9879. Inputs: in = nets reset; out = nets q[0], q[1], q[2], q[3]. Recovered as module datapath_unit_h61, instance datapath_unit_h61_i. Role: mixed.
- h2: 25 cells form a finite state machine, `fsm: 3 bits`. No proof recorded. Confidence 0.9601. Inputs: d = nets _01_, _02_, _03_. Outputs: q = nets q[1], q[2], q[3]. Recovered as module fsm_h2, instance fsm_h2_i. Role: mixed.
- h22: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[0], q[2]. Outputs: Y = nets _07_. Recovered as module eq_const_h22, instance eq_const_h22_i. Role: mixed.
- h14: 2 cells form a comparison against a constant, `Y = (A != 2)`. Proved equivalent by truth table. Confidence 0.9987. Inputs: A = nets reset, q[0]. Outputs: Y = nets _00_. Recovered as module eq_const_h14, instance eq_const_h14_i. Role: mixed. Conflicts with 1 more not listed.
- h27: 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.9002. Inputs: ctrl = nets w9; slice0 = nets _01_; slice1 = nets _02_; slice2 = nets _03_. Role: mixed.
- h28: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9002. Inputs: ctrl = nets _17_; slice0 = nets w12; slice1 = nets w11. Role: mixed.

## 5. Buses, state machines and roles

Buses:
- h4 (unconfirmed): 3 bits, bit order from wf: bit 0 = _04_; bit 1 = _06_; bit 2 = w6.
- h6 (unconfirmed): 3 bits, bit order from wf: bit 0 = w5; bit 1 = w10; bit 2 = w12.
- h25 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _00_; bit 1 = w9.
- h26 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w7; bit 1 = w12.
- h27: 3 bits, bit order from net_id: bit 0 = _01_; bit 1 = _02_; bit 2 = _03_.
- h28: 2 bits, bit order from net_id: bit 0 = w12; bit 1 = w11.

State machines:
- h2: state registers , 0 states, reset state 0, encoding unknown. 0 transitions.

Roles of committed claims: mixed: h2, h14, h22, h27, h28, h61.

## 6. Candidates (not committed, unconfirmed)

- h26 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.8191. Inputs: ctrl = nets w6; slice0 = nets w7; slice1 = nets w12. Role: mixed.
- h4 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _04_; slice1 = nets _06_; slice2 = nets w6. Role: mixed.
- h6 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets w5; slice1 = nets w10; slice2 = nets w12. Role: mixed.
- h9 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _01_; rst = nets w9. Outputs: q = nets q[1]. Role: mixed.
- h11 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _02_; rst = nets w9. Outputs: q = nets q[2]. Role: mixed.
- h13 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _03_; rst = nets w9. Outputs: q = nets q[3]. Role: mixed.
- h25 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets w1; slice0 = nets _00_; slice1 = nets w9. Role: mixed.
- h1 (unconfirmed): 13 cells form a flip-flop with synchronous reset, `ff_srst: 3 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _01_, _02_, _03_; rst = nets w9. Outputs: q = nets q[1], q[2], q[3]. Role: mixed.

## 7. Rejected claims

(none)

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = NOT(reset)
- w2 = NOT(q[0])
- w3 = AND(NOT(_04_), NOT(w2))
- w4 = NOT(w3)
- w5 = OR(NOT(w2), NOT(_04_))
- w6 = NOT(q[3])
- w7 = AND(NOT(w6), NOT(_04_))
- w8 = OR(NOT(_07_), NOT(w7))
- w9 = OR(NOT(w1), NOT(w8))
- w10 = OR(NOT(_06_), NOT(w4))
- w11 = OR(NOT(w10), NOT(_17_))
- w12 = OR(NOT(w6), NOT(_17_))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
