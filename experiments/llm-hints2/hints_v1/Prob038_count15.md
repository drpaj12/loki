Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 d94baedf3518, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| bus | 1 | 2 | 0 |
| counter | 1 | 0 | 0 |
| eq_const | 1 | 0 | 0 |
| ff_en | 0 | 1 | 0 |
| ff_srst | 0 | 4 | 0 |

Input cells (in Loki's re-mapped netlist): 22.

Of the committed cells, 3 (in 1 claims) are marked only by attributes on existing cells (form attrs). Those claims are not modules, so the hierarchy below does not show them.

Recovered module hierarchy (a module contains its children):

- h21 counter_h21 (counter)
  - h15 eq_const_h15 (eq_const)

## 4. Committed claims

- h21: 22 cells form a 4-bit counter, `Q <= RST ? 0 : (Q + 1)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: Q = nets q[0], q[1], q[2], q[3]; RST = nets reset. Outputs: D = nets _00_, _01_, _02_, _03_. Recovered as module counter_h21, instance counter_h21_i. Role: datapath.
- h15: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, q[0]. Outputs: Y = nets _00_. Recovered as module eq_const_h15, instance eq_const_h15_i. Role: datapath.
- h23: 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.9002. Inputs: ctrl = nets _04_; slice0 = nets w4; slice1 = nets _12_; slice2 = nets w6. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h4 (unconfirmed): 2 bits, bit order from wf: bit 0 = _00_; bit 1 = _14_.
- h6 (unconfirmed): 2 bits, bit order from wf: bit 0 = _04_; bit 1 = _05_.
- h23: 3 bits, bit order from net_id: bit 0 = w4; bit 1 = _12_; bit 2 = w6.

State machines: none.

Roles of committed claims: datapath: h15, h21, h23.

## 6. Candidates (not committed, unconfirmed)

- h13 (unconfirmed): 5 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _03_; en = nets _10_. Outputs: q = nets q[3]. Role: datapath.
- h8 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _01_; rst = nets _04_. Outputs: q = nets q[1]. Role: datapath.
- h11 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _02_; rst = nets _04_. Outputs: q = nets q[2]. Role: datapath.
- h14 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _03_; rst = nets _04_. Outputs: q = nets q[3]. Role: datapath.
- h4 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _00_; slice1 = nets _14_. Role: datapath.
- h6 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _04_; slice1 = nets _05_. Role: datapath.
- h1 (unconfirmed): 13 cells form a flip-flop with synchronous reset, `ff_srst: 3 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _01_, _02_, _03_; rst = nets _04_. Outputs: q = nets q[1], q[2], q[3]. Role: datapath.

## 7. Rejected claims

(none)

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = NOT(q[1])
- w2 = NOT(q[0])
- w3 = OR(NOT(w2), NOT(w1))
- w4 = OR(NOT(_04_), NOT(w3))
- w5 = OR(NOT(q[3]), NOT(_10_))
- w6 = OR(NOT(_04_), NOT(w5))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
