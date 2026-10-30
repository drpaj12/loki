Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 13ba91030c6d, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| bus | 0 | 19 | 0 |
| eq_const | 1 | 0 | 0 |
| ff_srst | 0 | 5 | 0 |
| fsm | 0 | 1 | 0 |

Input cells (in Loki's re-mapped netlist): 34.

Recovered module hierarchy (a module contains its children):

- h12 eq_const_h12 (eq_const)

## 4. Committed claims

- h12: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[2], q[3]. Outputs: Y = nets _13_. Recovered as module eq_const_h12, instance eq_const_h12_i. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h6 (unconfirmed): 3 bits, bit order from wf: bit 0 = w1; bit 1 = _04_; bit 2 = _06_.
- h7 (unconfirmed): 4 bits, bit order from wf: bit 0 = w1; bit 1 = _06_; bit 2 = _05_; bit 3 = _04_.
- h8 (unconfirmed): 3 bits, bit order from wf: bit 0 = w2; bit 1 = _05_; bit 2 = _07_.
- h9 (unconfirmed): 3 bits, bit order from wf: bit 0 = w3; bit 1 = w6; bit 2 = _28_.
- h10 (unconfirmed): 3 bits, bit order from wf: bit 0 = _09_; bit 1 = _13_; bit 2 = _16_.
- h11 (unconfirmed): 4 bits, bit order from wf: bit 0 = _09_; bit 1 = _16_; bit 2 = _19_; bit 3 = _13_.
- h43 (unconfirmed): 4 bits, bit order from net_id: bit 0 = w4; bit 1 = _18_; bit 2 = _23_; bit 3 = w9.
- h44 (unconfirmed): 3 bits, bit order from net_id: bit 0 = w7; bit 1 = _16_; bit 2 = _14_.
- h45 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _13_; bit 1 = _28_.
- h46 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _14_; bit 1 = w8.
- h87 (unconfirmed): 2 bits, bit order from wf: bit 0 = w1; bit 1 = _06_.
- h88 (unconfirmed): 3 bits, bit order from wf: bit 0 = w1; bit 1 = _06_; bit 2 = _05_.
- h89 (unconfirmed): 2 bits, bit order from wf: bit 0 = w2; bit 1 = _06_.
- h90 (unconfirmed): 2 bits, bit order from wf: bit 0 = w2; bit 1 = _07_.
- h91 (unconfirmed): 2 bits, bit order from wf: bit 0 = w2; bit 1 = _05_.
- h92 (unconfirmed): 2 bits, bit order from wf: bit 0 = w3; bit 1 = w6.
- h93 (unconfirmed): 2 bits, bit order from wf: bit 0 = _09_; bit 1 = _16_.
- h94 (unconfirmed): 2 bits, bit order from wf: bit 0 = _09_; bit 1 = _19_.
- h95 (unconfirmed): 3 bits, bit order from wf: bit 0 = _09_; bit 1 = _16_; bit 2 = _19_.

State machines:
- h2 (unconfirmed): state registers , 0 states, reset state 0, encoding unknown. 0 transitions.

Roles of committed claims: datapath: h12.

## 6. Candidates (not committed, unconfirmed)

- h13 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9002. Inputs: d = nets _00_; rst = nets _07_. Outputs: q = nets q[0]. Role: datapath.
- h15 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9002. Inputs: d = nets _01_; rst = nets _07_. Outputs: q = nets q[1]. Role: datapath.
- h17 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9002. Inputs: d = nets _02_; rst = nets _07_. Outputs: q = nets q[2]. Role: datapath.
- h19 (unconfirmed): 7 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9002. Inputs: d = nets _03_; rst = nets _07_. Outputs: q = nets q[3]. Role: datapath.
- h43 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.8569. Inputs: ctrl = nets _07_; slice0 = nets w4; slice1 = nets _18_; slice2 = nets _23_; slice3 = nets w9. Role: datapath.
- h44 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.8569. Inputs: ctrl = nets _08_; slice0 = nets w7; slice1 = nets _16_; slice2 = nets _14_. Role: datapath.
- h2 (unconfirmed): 34 cells form a finite state machine, `fsm: 4 bits`. No proof recorded. Confidence 0.7748. Inputs: d = nets _00_, _01_, _02_, _03_. Outputs: q = nets q[0], q[1], q[2], q[3]. Role: datapath. Conflicts with 1 more not listed.
- h6 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets w1; slice1 = nets _04_; slice2 = nets _06_. Role: datapath.
- h7 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets w1; slice1 = nets _06_; slice2 = nets _05_; slice3 = nets _04_. Role: datapath.
- h8 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets w2; slice1 = nets _05_; slice2 = nets _07_. Role: datapath.
- h9 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets w3; slice1 = nets w6; slice2 = nets _28_. Role: datapath.
- h10 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _09_; slice1 = nets _13_; slice2 = nets _16_. Role: datapath.
- h11 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _09_; slice1 = nets _16_; slice2 = nets _19_; slice3 = nets _13_. Role: datapath.
- h45 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _04_; slice0 = nets _13_; slice1 = nets _28_. Role: datapath.
- h46 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _13_; slice0 = nets _14_; slice1 = nets w8. Role: datapath.
- h88 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets w1; slice1 = nets _06_; slice2 = nets _05_. Role: datapath.
- h95 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _09_; slice1 = nets _16_; slice2 = nets _19_. Role: datapath.
- h87 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w1; slice1 = nets _06_. Role: datapath.
- h89 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w2; slice1 = nets _06_. Role: datapath.
- h90 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w2; slice1 = nets _07_. Role: datapath.
- h91 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w2; slice1 = nets _05_. Role: datapath.
- h92 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w3; slice1 = nets w6. Role: datapath.
- h93 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _09_; slice1 = nets _16_. Role: datapath.
- h94 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _09_; slice1 = nets _19_. Role: datapath.
- h1 (unconfirmed): 20 cells form a flip-flop with synchronous reset, `ff_srst: 4 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _00_, _01_, _02_, _03_; rst = nets _07_. Outputs: q = nets q[0], q[1], q[2], q[3]. Role: datapath.

## 7. Rejected claims

(none)

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = NOT(q[0])
- w2 = NOT(slowena)
- w3 = OR(NOT(w2), NOT(w1))
- w4 = OR(NOT(_07_), NOT(w3))
- w5 = NOT(_16_)
- w6 = OR(NOT(_05_), NOT(w5))
- w7 = AND(NOT(_08_), NOT(q[1]))
- w8 = OR(NOT(_13_), NOT(w7))
- w9 = OR(NOT(_07_), NOT(w8))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
