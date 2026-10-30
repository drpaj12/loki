Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 bd08673a6709, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| bus | 1 | 3 | 0 |
| datapath_unit | 1 | 0 | 0 |
| eq_const | 3 | 0 | 0 |
| ff_srst | 0 | 6 | 0 |
| fsm | 0 | 1 | 0 |

Input cells (in Loki's re-mapped netlist): 26.

Of the committed cells, 2 (in 1 claims) are marked only by attributes on existing cells (form attrs). Those claims are not modules, so the hierarchy below does not show them.

Recovered module hierarchy (a module contains its children):

- h66 datapath_unit_h66 (datapath_unit)
  - h4 eq_const_h4 (eq_const)
  - h12 eq_const_h12 (eq_const)
  - h20 eq_const_h20 (eq_const)

## 4. Committed claims

- h66: 26 cells form a datapath unit, `datapath_unit: 4 bits`. No proof recorded. Confidence 0.9879. Inputs: in = nets reset; out = nets q[0], q[1], q[2], q[3]. Recovered as module datapath_unit_h66, instance datapath_unit_h66_i. Role: datapath.
- h4: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[1], q[2]. Outputs: Y = nets w4. Recovered as module eq_const_h4, instance eq_const_h4_i. Role: datapath.
- h12: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, q[0]. Outputs: Y = nets _00_. Recovered as module eq_const_h12, instance eq_const_h12_i. Role: datapath.
- h20: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[0], q[1]. Outputs: Y = nets _11_. Recovered as module eq_const_h20, instance eq_const_h20_i. Role: datapath.
- h25: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9002. Inputs: ctrl = nets _04_; slice0 = nets _12_; slice1 = nets w3. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h23 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _00_; bit 1 = _10_.
- h25: 2 bits, bit order from net_id: bit 0 = _12_; bit 1 = w3.
- h27 (unconfirmed): 3 bits, bit order from net_id: bit 0 = w5; bit 1 = _19_; bit 2 = w8.
- h58 (unconfirmed): 2 bits, bit order from wf: bit 0 = w2; bit 1 = _05_.

State machines:
- h2 (unconfirmed): state registers , 0 states, reset state 0, encoding unknown. 0 transitions.

Roles of committed claims: datapath: h4, h12, h20, h25, h66.

## 6. Candidates (not committed, unconfirmed)

- h27 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.8569. Inputs: ctrl = nets _10_; slice0 = nets w5; slice1 = nets _19_; slice2 = nets w8. Role: datapath.
- h6 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _01_; rst = nets _10_. Outputs: q = nets q[1]. Role: datapath.
- h8 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _02_; rst = nets _10_. Outputs: q = nets q[2]. Role: datapath.
- h11 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _03_; rst = nets _10_. Outputs: q = nets q[3]. Role: datapath.
- h23 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets reset; slice0 = nets _00_; slice1 = nets _10_. Role: datapath.
- h59 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _01_; rst = nets _10_. Outputs: q = nets q[1]. Role: datapath.
- h2 (unconfirmed): 24 cells form a finite state machine, `fsm: 3 bits`. No proof recorded. Confidence 0.6956. Inputs: d = nets _01_, _02_, _03_. Outputs: q = nets q[1], q[2], q[3]. Role: datapath. Conflicts with 3 more not listed.
- h58 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w2; slice1 = nets _05_. Role: datapath.
- h1 (unconfirmed): 14 cells form a flip-flop with synchronous reset, `ff_srst: 3 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _01_, _02_, _03_; rst = nets _10_. Outputs: q = nets q[1], q[2], q[3]. Role: datapath.
- h54 (unconfirmed): 13 cells form a flip-flop with synchronous reset, `ff_srst: 3 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _01_, _02_, _03_; rst = nets _10_. Outputs: q = nets q[1], q[2], q[3]. Role: datapath.

## 7. Rejected claims

(none)

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = NOT(_12_)
- w2 = NOT(q[3])
- w3 = AND(NOT(w2), NOT(_04_))
- w4 = AND(NOT(q[2]), NOT(q[1]))
- w5 = OR(NOT(_10_), NOT(w1))
- w6 = OR(NOT(q[2]), NOT(_12_))
- w7 = OR(NOT(w2), NOT(w6))
- w8 = OR(NOT(_10_), NOT(w7))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
