Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 6738315c1c2a, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| bus | 2 | 17 | 0 |
| eq_const | 1 | 0 | 0 |
| ff_srst | 0 | 3 | 0 |
| fsm | 0 | 1 | 0 |

Input cells (in Loki's re-mapped netlist): 20.

Of the committed cells, 4 (in 2 claims) are marked only by attributes on existing cells (form attrs). Those claims are not modules, so the hierarchy below does not show them.

Recovered module hierarchy (a module contains its children):

- h32 eq_const_h32 (eq_const)

## 4. Committed claims

- h32: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets out, state[2]. Outputs: Y = nets w1. Recovered as module eq_const_h32, instance eq_const_h32_i. Role: datapath.
- h71: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9315. Inputs: ctrl = nets _05_; slice0 = nets _14_; slice1 = nets w5. Role: datapath.
- h73: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9002. Inputs: ctrl = nets _07_; slice0 = nets _01_; slice1 = nets _02_. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h5 (unconfirmed): 2 bits, bit order from wf: bit 0 = _05_; bit 1 = _06_.
- h6 (unconfirmed): 2 bits, bit order from wf: bit 0 = w4; bit 1 = _05_.
- h10 (unconfirmed): 2 bits, bit order from wf: bit 0 = _04_; bit 1 = w4.
- h12 (unconfirmed): 2 bits, bit order from wf: bit 0 = _14_; bit 1 = w5.
- h13 (unconfirmed): 2 bits, bit order from wf: bit 0 = _08_; bit 1 = w1.
- h15 (unconfirmed): 2 bits, bit order from wf: bit 0 = _07_; bit 1 = w2.
- h16 (unconfirmed): 2 bits, bit order from wf: bit 0 = w3; bit 1 = _10_.
- h17 (unconfirmed): 2 bits, bit order from wf: bit 0 = w3; bit 1 = _08_.
- h18 (unconfirmed): 2 bits, bit order from wf: bit 0 = _08_; bit 1 = _10_.
- h19 (unconfirmed): 2 bits, bit order from wf: bit 0 = _01_; bit 1 = _03_.
- h20 (unconfirmed): 2 bits, bit order from wf: bit 0 = w4; bit 1 = _06_.
- h71: 2 bits, bit order from net_id: bit 0 = _14_; bit 1 = w5.
- h72 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _08_; bit 1 = _14_.
- h73: 2 bits, bit order from net_id: bit 0 = _01_; bit 1 = _02_.
- h96 (unconfirmed): 2 bits, bit order from wf: bit 0 = _05_; bit 1 = w2.
- h97 (unconfirmed): 2 bits, bit order from wf: bit 0 = _05_; bit 1 = _04_.
- h99 (unconfirmed): 2 bits, bit order from wf: bit 0 = _08_; bit 1 = _00_.
- h100 (unconfirmed): 2 bits, bit order from wf: bit 0 = w3; bit 1 = _00_.
- h101 (unconfirmed): 2 bits, bit order from wf: bit 0 = w4; bit 1 = w2.

State machines:
- h70 (unconfirmed): state registers state[0], state[1], state[2], out, 5 states, reset state 0, encoding unknown, control inputs in, reset. 20 transitions (state, control value, next state; integers; first 12): (0,0,0), (0,1,0), (0,2,1), (0,3,1), (1,0,1), (1,1,4), (1,2,1), (1,3,1), (2,0,1), (2,1,8), (2,2,1), (2,3,1).

Roles of committed claims: datapath: h32, h71, h73.

## 6. Candidates (not committed, unconfirmed)

- h70 (unconfirmed): 20 cells form a finite state machine, `fsm: 5 states`. No proof recorded. Confidence 0.8569. Inputs: C = nets in, reset; D = nets _03_, _00_, _01_, _02_; Q = nets state[0], state[1], state[2], out. Role: datapath.
- h25 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _01_; rst = nets _07_. Outputs: q = nets state[2]. Role: datapath.
- h27 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _02_; rst = nets _07_. Outputs: q = nets out. Role: datapath.
- h72 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _04_; slice0 = nets _08_; slice1 = nets _14_. Role: datapath.
- h5 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _05_; slice1 = nets _06_. Role: datapath.
- h6 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w4; slice1 = nets _05_. Role: datapath.
- h10 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _04_; slice1 = nets w4. Role: datapath.
- h12 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _14_; slice1 = nets w5. Role: datapath.
- h13 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _08_; slice1 = nets w1. Role: datapath.
- h15 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _07_; slice1 = nets w2. Role: datapath.
- h16 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w3; slice1 = nets _10_. Role: datapath.
- h17 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w3; slice1 = nets _08_. Role: datapath.
- h18 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _08_; slice1 = nets _10_. Role: datapath.
- h19 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _01_; slice1 = nets _03_. Role: datapath.
- h20 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w4; slice1 = nets _06_. Role: datapath.
- h96 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _05_; slice1 = nets w2. Role: datapath.
- h97 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _05_; slice1 = nets _04_. Role: datapath.
- h99 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _08_; slice1 = nets _00_. Role: datapath.
- h100 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w3; slice1 = nets _00_. Role: datapath.
- h101 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w4; slice1 = nets w2. Role: datapath.
- h2 (unconfirmed): 7 cells form a flip-flop with synchronous reset, `ff_srst: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _02_, _01_; rst = nets _07_. Outputs: q = nets out, state[2]. Role: datapath.

## 7. Rejected claims

(none)

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = AND(NOT(out), NOT(state[2]))
- w2 = NOT(w1)
- w3 = AND(NOT(w2), NOT(state[0]))
- w4 = NOT(state[0])
- w5 = OR(NOT(_05_), NOT(w4))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
