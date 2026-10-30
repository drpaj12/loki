Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 a26cd6d0585f, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| bus | 0 | 2 | 0 |
| eq_const | 3 | 0 | 0 |
| ff_srst | 0 | 6 | 0 |
| fsm | 1 | 0 | 0 |
| register | 1 | 0 | 0 |

Input cells (in Loki's re-mapped netlist): 16.

Recovered module hierarchy (a module contains its children):

- h18 fsm_h18 (fsm)
  - h4 register_h4 (register)
    - h14 eq_const_h14 (eq_const)
    - h17 eq_const_h17 (eq_const)
  - h15 eq_const_h15 (eq_const)

## 4. Committed claims

- h18: 16 cells form a finite state machine, `fsm: 5 states`. No proof recorded. Confidence 0.9818. Inputs: C = nets in[3], reset; D = nets _03_, _00_, _01_, _02_; Q = nets state[0], state[1], state[2], done. Recovered as module fsm_h18, instance fsm_h18_i. Role: mixed.
- h4: 6 cells form a 2-bit register, `register: 2 bits`. No proof recorded. Confidence 0.9731. Inputs: clk = nets clk; d = nets _02_, _00_; rst = nets reset. Outputs: q = nets done, state[1]. Recovered as module register_h4, instance register_h4_i. Role: mixed.
- h14: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, state[2]. Outputs: Y = nets _00_. Recovered as module eq_const_h14, instance eq_const_h14_i. Role: mixed.
- h17: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, state[1]. Outputs: Y = nets _02_. Recovered as module eq_const_h17, instance eq_const_h17_i. Role: mixed.
- h15: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets done, state[0]. Outputs: Y = nets w1. Recovered as module eq_const_h15, instance eq_const_h15_i. Role: mixed.

## 5. Buses, state machines and roles

Buses:
- h19 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _00_; bit 1 = _02_.
- h20 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _09_; bit 1 = _03_.

State machines:
- h18: state registers state[0], state[1], state[2], done, 5 states, reset state 0, encoding unknown, control inputs in[3], reset. 20 transitions (state, control value, next state; integers; first 12): (0,0,0), (0,1,0), (0,2,1), (0,3,1), (1,0,1), (1,1,4), (1,2,1), (1,3,1), (2,0,8), (2,1,8), (2,2,1), (2,3,1).

Roles of committed claims: mixed: h4, h14, h15, h17, h18.

## 6. Candidates (not committed, unconfirmed)

- h6 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _03_; rst = nets _04_. Outputs: q = nets state[0]. Role: mixed.
- h8 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _00_; rst = nets reset. Outputs: q = nets state[1]. Role: mixed.
- h9 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _01_; rst = nets _04_. Outputs: q = nets state[2]. Role: mixed.
- h13 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _02_; rst = nets reset. Outputs: q = nets done. Role: mixed.
- h20 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _04_; slice0 = nets _09_; slice1 = nets _03_. Role: mixed.
- h1 (unconfirmed): 8 cells form a flip-flop with synchronous reset, `ff_srst: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _03_, _01_; rst = nets _04_. Outputs: q = nets state[0], state[2]. Role: mixed.
- h3 (unconfirmed): 6 cells form a flip-flop with synchronous reset, `ff_srst: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _02_, _00_; rst = nets reset. Outputs: q = nets done, state[1]. Role: mixed.
- h19 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: ctrl = nets reset; slice0 = nets _00_; slice1 = nets _02_. Role: mixed.

## 7. Rejected claims

(none)

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = AND(NOT(done), NOT(state[0]))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
