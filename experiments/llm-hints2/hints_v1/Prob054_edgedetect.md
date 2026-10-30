Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 973c6344efe5, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| bus | 0 | 1 | 0 |
| eq_const | 8 | 0 | 0 |
| register | 1 | 2 | 0 |

Input cells (in Loki's re-mapped netlist): 32.

Recovered module hierarchy (a module contains its children):

- h1 register_h1 (register)
  - h20 eq_const_h20 (eq_const)
  - h21 eq_const_h21 (eq_const)
  - h22 eq_const_h22 (eq_const)
  - h23 eq_const_h23 (eq_const)
  - h24 eq_const_h24 (eq_const)
  - h25 eq_const_h25 (eq_const)
  - h26 eq_const_h26 (eq_const)
  - h27 eq_const_h27 (eq_const)

## 4. Committed claims

- h1: 24 cells form an 8-bit register, `register: 8 bits`. No proof recorded. Confidence 0.9909. Inputs: clk = nets clk; d = nets _00_[0], _00_[1], _00_[2], _00_[3], _00_[4], _00_[5], _00_[6], _00_[7]. Outputs: q = nets pedge[0], pedge[1], pedge[2], pedge[3], pedge[4], pedge[5], pedge[6], pedge[7]. Recovered as module register_h1, instance register_h1_i. Role: datapath.
- h20: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets in[0], d_last[0]. Outputs: Y = nets _00_[0]. Recovered as module eq_const_h20, instance eq_const_h20_i. Role: datapath.
- h21: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets in[1], d_last[1]. Outputs: Y = nets _00_[1]. Recovered as module eq_const_h21, instance eq_const_h21_i. Role: datapath.
- h22: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proof derived from h20 (proof transfer). Confidence 0.9999. Inputs: A = nets in[2], d_last[2]. Outputs: Y = nets _00_[2]. Recovered as module eq_const_h22, instance eq_const_h22_i. Role: datapath.
- h23: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proof derived from h20 (proof transfer). Confidence 0.9999. Inputs: A = nets in[3], d_last[3]. Outputs: Y = nets _00_[3]. Recovered as module eq_const_h23, instance eq_const_h23_i. Role: datapath.
- h24: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proof derived from h20 (proof transfer). Confidence 0.9999. Inputs: A = nets in[4], d_last[4]. Outputs: Y = nets _00_[4]. Recovered as module eq_const_h24, instance eq_const_h24_i. Role: datapath.
- h25: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proof derived from h20 (proof transfer). Confidence 0.9999. Inputs: A = nets in[5], d_last[5]. Outputs: Y = nets _00_[5]. Recovered as module eq_const_h25, instance eq_const_h25_i. Role: datapath.
- h26: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proof derived from h20 (proof transfer). Confidence 0.9999. Inputs: A = nets in[6], d_last[6]. Outputs: Y = nets _00_[6]. Recovered as module eq_const_h26, instance eq_const_h26_i. Role: datapath.
- h27: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proof derived from h20 (proof transfer). Confidence 0.9999. Inputs: A = nets in[7], d_last[7]. Outputs: Y = nets _00_[7]. Recovered as module eq_const_h27, instance eq_const_h27_i. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h3 (unconfirmed): 8 bits, bit order from wf: bit 0 = _01_; bit 1 = _02_; bit 2 = _03_; bit 3 = _04_; bit 4 = _05_; bit 5 = _06_; bit 6 = _07_; bit 7 = _08_.

State machines: none.

Roles of committed claims: datapath: h1, h20, h21, h22, h23, h24, h25, h26, h27.

## 6. Candidates (not committed, unconfirmed)

- h3 (unconfirmed): 8 cells form an 8-bit bus, `bus: 8 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _01_; slice1 = nets _02_; slice2 = nets _03_; slice3 = nets _04_; slice4 = nets _05_; slice5 = nets _06_; slice6 = nets _07_; slice7 = nets _08_. Role: datapath.
- h2 (unconfirmed): 8 cells form an 8-bit register, `register: 8 bits`. No proof recorded. Confidence 0.8006. Inputs: clk = nets clk; d = nets in[0], in[1], in[2], in[3], in[4], in[5], in[6], in[7]. Outputs: q = nets d_last[0], d_last[1], d_last[2], d_last[3], d_last[4], d_last[5], d_last[6], d_last[7]. Role: datapath.
- h60 (unconfirmed): 8 cells form an 8-bit register, `register: 8 bits`. No proof recorded. Confidence 0.8006. Inputs: clk = nets clk; d = nets _00_[0], _00_[1], _00_[2], _00_[3], _00_[4], _00_[5], _00_[6], _00_[7]. Outputs: q = nets pedge[0], pedge[1], pedge[2], pedge[3], pedge[4], pedge[5], pedge[6], pedge[7]. Role: datapath.

## 7. Rejected claims

(none)

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
