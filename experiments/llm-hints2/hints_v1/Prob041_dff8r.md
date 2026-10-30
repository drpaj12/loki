Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 86500f6c05bd, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| bus | 2 | 0 | 0 |
| eq_const | 8 | 0 | 0 |
| ff_srst | 0 | 9 | 0 |
| register | 1 | 1 | 0 |

Input cells (in Loki's re-mapped netlist): 24.

Of the committed cells, 16 (in 2 claims) are marked only by attributes on existing cells (form attrs). Those claims are not modules, so the hierarchy below does not show them.

Recovered module hierarchy (a module contains its children):

- h2 register_h2 (register)
  - h3 eq_const_h3 (eq_const)
  - h4 eq_const_h4 (eq_const)
  - h5 eq_const_h5 (eq_const)
  - h6 eq_const_h6 (eq_const)
  - h7 eq_const_h7 (eq_const)
  - h8 eq_const_h8 (eq_const)
  - h9 eq_const_h9 (eq_const)
  - h10 eq_const_h10 (eq_const)

## 4. Committed claims

- h2: 24 cells form an 8-bit register, `register: 8 bits`. No proof recorded. Confidence 0.9977. Inputs: clk = nets clk; d = nets _04_, _05_, _06_, _07_, _00_, _01_, _02_, _03_; rst = nets reset. Outputs: q = nets q[0], q[1], q[2], q[3], q[4], q[5], q[6], q[7]. Recovered as module register_h2, instance register_h2_i. Role: datapath.
- h3: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets d[4], reset. Outputs: Y = nets _00_. Recovered as module eq_const_h3, instance eq_const_h3_i. Role: datapath.
- h4: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets d[5], reset. Outputs: Y = nets _01_. Recovered as module eq_const_h4, instance eq_const_h4_i. Role: datapath.
- h5: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proof derived from h3 (proof transfer). Confidence 0.9999. Inputs: A = nets d[6], reset. Outputs: Y = nets _02_. Recovered as module eq_const_h5, instance eq_const_h5_i. Role: datapath.
- h6: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proof derived from h3 (proof transfer). Confidence 0.9999. Inputs: A = nets d[7], reset. Outputs: Y = nets _03_. Recovered as module eq_const_h6, instance eq_const_h6_i. Role: datapath.
- h7: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proof derived from h3 (proof transfer). Confidence 0.9999. Inputs: A = nets d[0], reset. Outputs: Y = nets _04_. Recovered as module eq_const_h7, instance eq_const_h7_i. Role: datapath.
- h8: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proof derived from h3 (proof transfer). Confidence 0.9999. Inputs: A = nets d[1], reset. Outputs: Y = nets _05_. Recovered as module eq_const_h8, instance eq_const_h8_i. Role: datapath.
- h9: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proof derived from h3 (proof transfer). Confidence 0.9999. Inputs: A = nets d[2], reset. Outputs: Y = nets _06_. Recovered as module eq_const_h9, instance eq_const_h9_i. Role: datapath.
- h10: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proof derived from h3 (proof transfer). Confidence 0.9999. Inputs: A = nets d[3], reset. Outputs: Y = nets _07_. Recovered as module eq_const_h10, instance eq_const_h10_i. Role: datapath.
- h27: 8 cells form an 8-bit bus, `bus: 8 bits`. No proof recorded. Confidence 0.9731. Inputs: ctrl = nets reset; slice0 = nets _00_; slice1 = nets _01_; slice2 = nets _02_; slice3 = nets _03_; slice4 = nets _04_; slice5 = nets _05_; slice6 = nets _06_; slice7 = nets _07_. Role: datapath.
- h53: 16 cells form an 8-bit bus, `bus: 8 bits`. No proof recorded. Confidence 0.9234. Inputs: ctrl = nets reset; slice0 = nets _04_; slice1 = nets _05_; slice2 = nets _06_; slice3 = nets _07_; slice4 = nets _00_; slice5 = nets _01_; slice6 = nets _02_; slice7 = nets _03_. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h27: 8 bits, bit order from net_id: bit 0 = _00_; bit 1 = _01_; bit 2 = _02_; bit 3 = _03_; bit 4 = _04_; bit 5 = _05_; bit 6 = _06_; bit 7 = _07_.
- h53: 8 bits, bit order from net_id: bit 0 = _04_; bit 1 = _05_; bit 2 = _06_; bit 3 = _07_; bit 4 = _00_; bit 5 = _01_; bit 6 = _02_; bit 7 = _03_.

State machines: none.

Roles of committed claims: datapath: h2, h3, h4, h5, h6, h7, h8, h9, h10, h27, h53.

## 6. Candidates (not committed, unconfirmed)

- h12 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _04_; rst = nets reset. Outputs: q = nets q[0]. Role: datapath.
- h14 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _05_; rst = nets reset. Outputs: q = nets q[1]. Role: datapath.
- h16 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _06_; rst = nets reset. Outputs: q = nets q[2]. Role: datapath.
- h18 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _07_; rst = nets reset. Outputs: q = nets q[3]. Role: datapath.
- h20 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _00_; rst = nets reset. Outputs: q = nets q[4]. Role: datapath.
- h22 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _01_; rst = nets reset. Outputs: q = nets q[5]. Role: datapath.
- h24 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _02_; rst = nets reset. Outputs: q = nets q[6]. Role: datapath.
- h26 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _03_; rst = nets reset. Outputs: q = nets q[7]. Role: datapath.
- h52 (unconfirmed): 8 cells form an 8-bit register, `register: 8 bits`. No proof recorded. Confidence 0.8006. Inputs: clk = nets clk; d = nets _04_, _05_, _06_, _07_, _00_, _01_, _02_, _03_. Outputs: q = nets q[0], q[1], q[2], q[3], q[4], q[5], q[6], q[7]. Role: datapath.
- h1 (unconfirmed): 24 cells form a flip-flop with synchronous reset, `ff_srst: 8 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _04_, _05_, _06_, _07_, _00_, _01_, _02_, _03_; rst = nets reset. Outputs: q = nets q[0], q[1], q[2], q[3], q[4], q[5], q[6], q[7]. Role: datapath.

## 7. Rejected claims

(none)

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
