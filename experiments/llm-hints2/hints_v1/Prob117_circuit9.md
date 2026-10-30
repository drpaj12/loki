Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 15e0f683a23f, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| bus | 4 | 7 | 0 |
| counter | 2 | 0 | 0 |
| eq_const | 1 | 0 | 0 |
| ff_srst | 0 | 3 | 0 |

Input cells (in Loki's re-mapped netlist): 19.

Of the committed cells, 5 (in 4 claims) are marked only by attributes on existing cells (form attrs). Those claims are not modules, so the hierarchy below does not show them.

Recovered module hierarchy (a module contains its children):

- h14 counter_h14 (counter)
  - h6 eq_const_h6 (eq_const)
  - h123 counter_h123 (counter)

## 4. Committed claims

- h14: 19 cells form a 3-bit counter, `Q <= RST ? 4 : ((Q == 6) ? 0 : Q + 1)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: Q = nets q[0], q[1], q[2]; RST = nets a. Outputs: D = nets _00_, _01_, _02_. Recovered as module counter_h14, instance counter_h14_i. Role: datapath.
- h6: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[0], q[1]. Outputs: Y = nets w2. Recovered as module eq_const_h6, instance eq_const_h6_i. Role: datapath.
- h123: 18 cells form a 3-bit counter, `Q <= RST ? 4 : ((Q == 6) ? 0 : Q + 1)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: Q = nets q[0], q[1], q[2]; RST = nets a. Outputs: D = nets _00_, _01_, _02_. Recovered as module counter_h123, instance counter_h123_i. Role: datapath. Conflicts with 1 more not listed.
- h16: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9002. Inputs: ctrl = nets _03_; slice0 = nets w1; slice1 = nets w4. Role: datapath.
- h17: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets _15_; slice0 = nets w1; slice1 = nets w3. Role: datapath.
- h18: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9002. Inputs: ctrl = nets _04_; slice0 = nets w3; slice1 = nets _06_. Role: datapath.
- h22: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9002. Inputs: ctrl = nets w2; slice0 = nets w4; slice1 = nets _09_. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h4 (unconfirmed): 2 bits, bit order from wf: bit 0 = _04_; bit 1 = _15_.
- h16: 2 bits, bit order from net_id: bit 0 = w1; bit 1 = w4.
- h17: 2 bits, bit order from net_id: bit 0 = w1; bit 1 = w3.
- h18: 2 bits, bit order from net_id: bit 0 = w3; bit 1 = _06_.
- h19 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _07_; bit 1 = _02_.
- h21 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _00_; bit 1 = _01_.
- h22: 2 bits, bit order from net_id: bit 0 = w4; bit 1 = _09_.
- h43 (unconfirmed): 2 bits, bit order from wf: bit 0 = _04_; bit 1 = _03_.
- h44 (unconfirmed): 2 bits, bit order from wf: bit 0 = _03_; bit 1 = _15_.
- h48 (unconfirmed): 2 bits, bit order from wf: bit 0 = _15_; bit 1 = _14_.
- h49 (unconfirmed): 2 bits, bit order from wf: bit 0 = w4; bit 1 = w3.

State machines: none.

Roles of committed claims: datapath: h6, h14, h16, h17, h18, h22, h123.

## 6. Candidates (not committed, unconfirmed)

- h19 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.8569. Inputs: ctrl = nets _14_; slice0 = nets _07_; slice1 = nets _02_. Role: datapath.
- h7 (unconfirmed): 2 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _00_; rst = nets _07_. Outputs: q = nets q[0]. Role: datapath.
- h9 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _01_; rst = nets _07_. Outputs: q = nets q[1]. Role: datapath.
- h21 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _07_; slice0 = nets _00_; slice1 = nets _01_. Role: datapath.
- h4 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _04_; slice1 = nets _15_. Role: datapath.
- h43 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _04_; slice1 = nets _03_. Role: datapath.
- h44 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _03_; slice1 = nets _15_. Role: datapath.
- h48 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _15_; slice1 = nets _14_. Role: datapath.
- h49 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w4; slice1 = nets w3. Role: datapath.
- h1 (unconfirmed): 6 cells form a flip-flop with synchronous reset, `ff_srst: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _00_, _01_; rst = nets _07_. Outputs: q = nets q[0], q[1]. Role: datapath.

## 7. Rejected claims

(none)

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = AND(NOT(_03_), NOT(_15_))
- w2 = OR(NOT(q[0]), NOT(q[1]))
- w3 = OR(NOT(_04_), NOT(_15_))
- w4 = OR(NOT(_03_), NOT(w2))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
