Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 711689eb18b1, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| eq_const | 0 | 0 | 2 |

Input cells (in Loki's re-mapped netlist): 7.

Recovered module hierarchy (a module contains its children):

(no committed modules)

## 4. Committed claims

(none)

## 5. Buses, state machines and roles

Buses: none.

State machines: none.

Roles of committed claims: not known.

## 6. Candidates (not committed, unconfirmed)

(none)

## 7. Rejected claims

- h1: Loki proposed a comparison against a constant (`Y = (A == 0)`) on 1 cell; rejected: commit failed: ODIN3_ERR_INVALID_ARG.
- h2: Loki proposed a comparison against a constant (`Y = (A == 3)`) on 3 cells; rejected: commit failed: ODIN3_ERR_INVALID_ARG.

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = AND(NOT(out), NOT(j))
- w2 = NOT(out)
- w3 = NOT(k)
- w4 = AND(NOT(w2), NOT(w3))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
