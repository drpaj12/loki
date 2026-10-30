Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 4078c9fbf95c, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| bus | 1 | 2 | 0 |
| eq_const | 5 | 0 | 0 |
| ff_srst | 0 | 10 | 0 |

Input cells (in Loki's re-mapped netlist): 33.

Of the committed cells, 3 (in 1 claims) are marked only by attributes on existing cells (form attrs). Those claims are not modules, so the hierarchy below does not show them.

Recovered module hierarchy (a module contains its children):

- h4 eq_const_h4 (eq_const)
- h5 eq_const_h5 (eq_const)
- h6 eq_const_h6 (eq_const)
- h7 eq_const_h7 (eq_const)
- h8 eq_const_h8 (eq_const)

## 4. Committed claims

- h4: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets d[3], reset. Outputs: Y = nets _09_. Recovered as module eq_const_h4, instance eq_const_h4_i. Role: datapath.
- h5: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets d[6], reset. Outputs: Y = nets _12_. Recovered as module eq_const_h5, instance eq_const_h5_i. Role: datapath.
- h6: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proof derived from h4 (proof transfer). Confidence 0.9999. Inputs: A = nets d[7], reset. Outputs: Y = nets _13_. Recovered as module eq_const_h6, instance eq_const_h6_i. Role: datapath.
- h7: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proof derived from h4 (proof transfer). Confidence 0.9999. Inputs: A = nets d[0], reset. Outputs: Y = nets _14_. Recovered as module eq_const_h7, instance eq_const_h7_i. Role: datapath.
- h8: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proof derived from h4 (proof transfer). Confidence 0.9999. Inputs: A = nets d[1], reset. Outputs: Y = nets _15_. Recovered as module eq_const_h8, instance eq_const_h8_i. Role: datapath.
- h25: 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w1; slice0 = nets _08_; slice1 = nets _10_; slice2 = nets _11_. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h25: 3 bits, bit order from net_id: bit 0 = _08_; bit 1 = _10_; bit 2 = _11_.
- h26 (unconfirmed): 5 bits, bit order from net_id: bit 0 = _09_; bit 1 = _12_; bit 2 = _13_; bit 3 = _14_; bit 4 = _15_.
- h62 (unconfirmed): 5 bits, bit order from net_id: bit 0 = _14_; bit 1 = _15_; bit 2 = _09_; bit 3 = _12_; bit 4 = _13_.

State machines: none.

Roles of committed claims: datapath: h4, h5, h6, h7, h8, h25.

## 6. Candidates (not committed, unconfirmed)

- h10 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9002. Inputs: d = nets _14_; rst = nets reset. Outputs: q = nets q[0]. Role: datapath.
- h12 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9002. Inputs: d = nets _15_; rst = nets reset. Outputs: q = nets q[1]. Role: datapath.
- h16 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9002. Inputs: d = nets _09_; rst = nets reset. Outputs: q = nets q[3]. Role: datapath.
- h22 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9002. Inputs: d = nets _12_; rst = nets reset. Outputs: q = nets q[6]. Role: datapath.
- h24 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9002. Inputs: d = nets _13_; rst = nets reset. Outputs: q = nets q[7]. Role: datapath.
- h26 (unconfirmed): 5 cells form a 5-bit bus, `bus: 5 bits`. No proof recorded. Confidence 0.8581. Inputs: ctrl = nets reset; slice0 = nets _09_; slice1 = nets _12_; slice2 = nets _13_; slice3 = nets _14_; slice4 = nets _15_. Role: datapath.
- h13 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _08_; rst = nets w1. Outputs: q = nets q[2]. Role: datapath.
- h17 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _10_; rst = nets w1. Outputs: q = nets q[4]. Role: datapath.
- h19 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _11_; rst = nets w1. Outputs: q = nets q[5]. Role: datapath.
- h62 (unconfirmed): 10 cells form a 5-bit bus, `bus: 5 bits`. No proof recorded. Confidence 0.6682. Inputs: ctrl = nets reset; slice0 = nets _14_; slice1 = nets _15_; slice2 = nets _09_; slice3 = nets _12_; slice4 = nets _13_. Role: datapath.
- h60 (unconfirmed): 15 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.5000. Inputs: rst = nets reset. Role: datapath.
- h61 (unconfirmed): 9 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.5000. Inputs: rst = nets w1. Role: datapath.

## 7. Rejected claims

(none)

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = NOT(reset)
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
