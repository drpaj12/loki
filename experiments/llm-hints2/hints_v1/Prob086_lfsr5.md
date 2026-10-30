Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 963b974d67e5, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| bus | 0 | 5 | 0 |
| eq_const | 9 | 0 | 0 |
| ff_srst | 0 | 7 | 0 |
| register | 1 | 0 | 0 |

Input cells (in Loki's re-mapped netlist): 18.

Recovered module hierarchy (a module contains its children):

- h4 register_h4 (register)
  - h16 eq_const_h16 (eq_const)
  - h18 eq_const_h18 (eq_const)
  - h21 eq_const_h21 (eq_const)
- h17 eq_const_h17 (eq_const)
- h19 eq_const_h19 (eq_const)
- h20 eq_const_h20 (eq_const)
- h47 eq_const_h47 (eq_const)
  - h48 eq_const_h48 (eq_const)
  - h53 eq_const_h53 (eq_const)

## 4. Committed claims

- h4: 9 cells form a 3-bit register, `register: 3 bits`. No proof recorded. Confidence 0.9195. Inputs: clk = nets clk; d = nets _02_, _04_, _00_; rst = nets reset. Outputs: q = nets q[1], q[3], q[4]. Recovered as module register_h4, instance register_h4_i. Role: datapath. Conflicts with 1 more not listed.
- h16: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, q[0]. Outputs: Y = nets _00_. Recovered as module eq_const_h16, instance eq_const_h16_i. Role: datapath.
- h18: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, q[2]. Outputs: Y = nets _02_. Recovered as module eq_const_h18, instance eq_const_h18_i. Role: datapath.
- h21: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h16 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[4]. Outputs: Y = nets _04_. Recovered as module eq_const_h21, instance eq_const_h21_i. Role: datapath.
- h17: 3 cells form a comparison against a constant, `Y = (A != 0)`. Proved equivalent by truth table. Confidence 0.9963. Inputs: A = nets reset, q[1]. Outputs: Y = nets _01_. Recovered as module eq_const_h17, instance eq_const_h17_i. Role: datapath. Conflicts with 1 more not listed.
- h19: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[0], q[3]. Outputs: Y = nets _10_. Recovered as module eq_const_h19, instance eq_const_h19_i. Role: datapath.
- h20: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[0], q[3]. Outputs: Y = nets _11_. Recovered as module eq_const_h20, instance eq_const_h20_i. Role: datapath.
- h47: 2 cells form a comparison against a constant, `Y = (A == 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _05_, _10_, _11_. Outputs: Y = nets _03_. Recovered as module eq_const_h47, instance eq_const_h47_i. Role: datapath.
- h48: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _05_, _10_. Outputs: Y = nets _12_. Recovered as module eq_const_h48, instance eq_const_h48_i. Role: datapath.
- h53: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _12_, _11_. Outputs: Y = nets _03_. Recovered as module eq_const_h53, instance eq_const_h53_i. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h5 (unconfirmed): 2 bits, bit order from wf: bit 0 = _08_; bit 1 = _06_.
- h6 (unconfirmed): 2 bits, bit order from wf: bit 0 = _00_; bit 1 = _02_.
- h23 (unconfirmed): 3 bits, bit order from net_id: bit 0 = _00_; bit 1 = _02_; bit 2 = _04_.
- h24 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _01_; bit 1 = _12_.
- h49 (unconfirmed): 3 bits, bit order from net_id: bit 0 = _00_; bit 1 = _02_; bit 2 = _04_.

State machines: none.

Roles of committed claims: datapath: h4, h16, h17, h18, h19, h20, h21, h47, h48, h53.

## 6. Candidates (not committed, unconfirmed)

- h7 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _01_; rst = nets _05_. Outputs: q = nets q[0]. Role: datapath.
- h10 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _02_; rst = nets reset. Outputs: q = nets q[1]. Role: datapath.
- h11 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _03_; rst = nets _05_. Outputs: q = nets q[2]. Role: datapath.
- h13 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _04_; rst = nets reset. Outputs: q = nets q[3]. Role: datapath.
- h15 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _00_; rst = nets reset. Outputs: q = nets q[4]. Role: datapath.
- h24 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _05_; slice0 = nets _01_; slice1 = nets _12_. Role: datapath.
- h23 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.6660. Inputs: ctrl = nets reset; slice0 = nets _00_; slice1 = nets _02_; slice2 = nets _04_. Role: datapath.
- h5 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _08_; slice1 = nets _06_. Role: datapath.
- h6 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _00_; slice1 = nets _02_. Role: datapath.
- h1 (unconfirmed): 8 cells form a flip-flop with synchronous reset, `ff_srst: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _01_, _03_; rst = nets _05_. Outputs: q = nets q[0], q[2]. Role: datapath.
- h3 (unconfirmed): 9 cells form a flip-flop with synchronous reset, `ff_srst: 3 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _02_, _04_, _00_; rst = nets reset. Outputs: q = nets q[1], q[3], q[4]. Role: datapath.
- h49 (unconfirmed): 6 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.5000. Inputs: ctrl = nets reset; slice0 = nets _00_; slice1 = nets _02_; slice2 = nets _04_. Role: datapath.

## 7. Rejected claims

(none)

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
