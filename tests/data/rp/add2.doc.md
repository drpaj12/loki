# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `tests/data/re/add2.blif` (sha256 f3a46fe71efc, floor f2).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 2. How to read the netlist with it

The recovered Verilog (`design.v`) carries Loki attributes on the pieces it committed:
- `loki_hid`: the claim id (`h12`), the same id as in this document.
- `loki_kind`, `loki_fn`: what the piece is and its function; `loki_conf`: confidence.
- `loki_proof`: `equivalent`, `derived`, `unproven` or `none`; `loki_role`: control, datapath or mixed.
- `loki_bus = "<hid>[bit]"` on a net: the net is that bit of bus `<hid>`.
Port nets are listed least-significant bit first. Cell and net names are those of the input netlist.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| adder | 1 | 0 | 0 |

Input cells: 4. Covered by committed claims: 3 (75.0%); by candidates only: 0 (0.0%); by nothing: 1 (25.0%).

Recovered module hierarchy (a module contains its children):

- h1 adder_h1 (adder)

## 4. Committed claims

- h1: cells n10..n12 (3 cells) form a 2-bit adder, `Y = A + B`. Proved equivalent by cone check. Confidence 0.9999. Inputs: A = nets a0, a1; B = nets b0, b1. Outputs: Y = nets y0, y1. Recovered as module adder_h1, instance adder_h1_i. Role: datapath.

## 5. Buses, state machines and roles

Buses: none.

State machines: none.

Roles of committed claims: datapath: h1.

## 6. Candidates (not committed, unconfirmed)

(none)

## 7. Rejected claims

(none)

## 9. What Loki does NOT claim

- Cells covered by no claim at all: 1 of 4: n13.
- Nets driven by those cells: 1: q.
- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.
