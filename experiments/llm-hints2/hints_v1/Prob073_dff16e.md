Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 5f53a01244fd, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| bus | 3 | 6 | 0 |
| eq_const | 16 | 0 | 0 |
| ff_en | 0 | 18 | 0 |
| ff_srst | 0 | 35 | 0 |

Input cells (in Loki's re-mapped netlist): 96.

Of the committed cells, 48 (in 3 claims) are marked only by attributes on existing cells (form attrs). Those claims are not modules, so the hierarchy below does not show them.

Recovered module hierarchy (a module contains its children):

- h73 eq_const_h73 (eq_const)
- h74 eq_const_h74 (eq_const)
- h75 eq_const_h75 (eq_const)
- h76 eq_const_h76 (eq_const)
- h77 eq_const_h77 (eq_const)
- h78 eq_const_h78 (eq_const)
- h79 eq_const_h79 (eq_const)
- h80 eq_const_h80 (eq_const)
- h81 eq_const_h81 (eq_const)
- h82 eq_const_h82 (eq_const)
- h83 eq_const_h83 (eq_const)
- h84 eq_const_h84 (eq_const)
- h85 eq_const_h85 (eq_const)
- h86 eq_const_h86 (eq_const)
- h87 eq_const_h87 (eq_const)
- h88 eq_const_h88 (eq_const)

## 4. Committed claims

- h73: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets byteena[1], q[14]. Outputs: Y = nets _056_. Recovered as module eq_const_h73, instance eq_const_h73_i. Role: datapath.
- h74: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets byteena[1], q[15]. Outputs: Y = nets _059_. Recovered as module eq_const_h74, instance eq_const_h74_i. Role: datapath.
- h75: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets byteena[0], q[0]. Outputs: Y = nets _062_. Recovered as module eq_const_h75, instance eq_const_h75_i. Role: datapath.
- h76: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets byteena[0], q[1]. Outputs: Y = nets _065_. Recovered as module eq_const_h76, instance eq_const_h76_i. Role: datapath.
- h77: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets byteena[0], q[2]. Outputs: Y = nets _068_. Recovered as module eq_const_h77, instance eq_const_h77_i. Role: datapath.
- h78: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets byteena[0], q[3]. Outputs: Y = nets _071_. Recovered as module eq_const_h78, instance eq_const_h78_i. Role: datapath.
- h79: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets byteena[0], q[4]. Outputs: Y = nets _074_. Recovered as module eq_const_h79, instance eq_const_h79_i. Role: datapath.
- h80: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets byteena[0], q[5]. Outputs: Y = nets _077_. Recovered as module eq_const_h80, instance eq_const_h80_i. Role: datapath.
- h81: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets byteena[0], q[6]. Outputs: Y = nets _016_. Recovered as module eq_const_h81, instance eq_const_h81_i. Role: datapath.
- h82: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets byteena[0], q[7]. Outputs: Y = nets _019_. Recovered as module eq_const_h82, instance eq_const_h82_i. Role: datapath.
- h83: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets byteena[1], q[8]. Outputs: Y = nets _022_. Recovered as module eq_const_h83, instance eq_const_h83_i. Role: datapath.
- h84: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets byteena[1], q[9]. Outputs: Y = nets _025_. Recovered as module eq_const_h84, instance eq_const_h84_i. Role: datapath.
- h85: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets byteena[1], q[10]. Outputs: Y = nets _028_. Recovered as module eq_const_h85, instance eq_const_h85_i. Role: datapath.
- h86: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets byteena[1], q[11]. Outputs: Y = nets _031_. Recovered as module eq_const_h86, instance eq_const_h86_i. Role: datapath.
- h87: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets byteena[1], q[12]. Outputs: Y = nets _034_. Recovered as module eq_const_h87, instance eq_const_h87_i. Role: datapath.
- h88: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets byteena[1], q[13]. Outputs: Y = nets _037_. Recovered as module eq_const_h88, instance eq_const_h88_i. Role: datapath.
- h89: 16 cells form a 16-bit bus, `bus: 16 bits`. No proof recorded. Confidence 0.9601. Inputs: ctrl = nets byteena[1]; slice0 = nets _022_; slice1 = nets _025_; slice10 = nets _023_; slice11 = nets _026_; slice12 = nets _029_; slice13 = nets _032_; slice14 = nets _035_; slice15 = nets _038_; slice2 = nets _028_; slice3 = nets _031_; slice4 = nets _034_; slice5 = nets _037_; slice6 = nets _056_; slice7 = nets _059_; slice8 = nets _057_; slice9 = nets _060_. Role: datapath.
- h90: 16 cells form a 16-bit bus, `bus: 16 bits`. No proof recorded. Confidence 0.9863. Inputs: ctrl = nets resetn; slice0 = nets _058_; slice1 = nets _061_; slice10 = nets _024_; slice11 = nets _027_; slice12 = nets _030_; slice13 = nets _033_; slice14 = nets _036_; slice15 = nets _039_; slice2 = nets _064_; slice3 = nets _067_; slice4 = nets _070_; slice5 = nets _073_; slice6 = nets _076_; slice7 = nets _079_; slice8 = nets _018_; slice9 = nets _021_. Role: datapath.
- h91: 16 cells form a 16-bit bus, `bus: 16 bits`. No proof recorded. Confidence 0.9601. Inputs: ctrl = nets byteena[0]; slice0 = nets _062_; slice1 = nets _065_; slice10 = nets _069_; slice11 = nets _072_; slice12 = nets _075_; slice13 = nets _078_; slice14 = nets _017_; slice15 = nets _020_; slice2 = nets _068_; slice3 = nets _071_; slice4 = nets _074_; slice5 = nets _077_; slice6 = nets _016_; slice7 = nets _019_; slice8 = nets _063_; slice9 = nets _066_. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h9 (unconfirmed): 8 bits, bit order from wf: bit 0 = _022_; bit 1 = _025_; bit 2 = _028_; bit 3 = _031_; bit 4 = _034_; bit 5 = _037_; bit 6 = _056_; bit 7 = _059_.
- h14 (unconfirmed): 8 bits, bit order from wf: bit 0 = _062_; bit 1 = _065_; bit 2 = _068_; bit 3 = _071_; bit 4 = _074_; bit 5 = _077_; bit 6 = _016_; bit 7 = _019_.
- h89: 16 bits, bit order from net_id: bit 0 = _022_; bit 1 = _025_; bit 2 = _028_; bit 3 = _031_; bit 4 = _034_; bit 5 = _037_; bit 6 = _056_; bit 7 = _059_; bit 8 = _057_; bit 9 = _060_; bit 10 = _023_; bit 11 = _026_; bit 12 = _029_; bit 13 = _032_; bit 14 = _035_; bit 15 = _038_.
- h90: 16 bits, bit order from net_id: bit 0 = _058_; bit 1 = _061_; bit 2 = _064_; bit 3 = _067_; bit 4 = _070_; bit 5 = _073_; bit 6 = _076_; bit 7 = _079_; bit 8 = _018_; bit 9 = _021_; bit 10 = _024_; bit 11 = _027_; bit 12 = _030_; bit 13 = _033_; bit 14 = _036_; bit 15 = _039_.
- h91: 16 bits, bit order from net_id: bit 0 = _062_; bit 1 = _065_; bit 2 = _068_; bit 3 = _071_; bit 4 = _074_; bit 5 = _077_; bit 6 = _016_; bit 7 = _019_; bit 8 = _063_; bit 9 = _066_; bit 10 = _069_; bit 11 = _072_; bit 12 = _075_; bit 13 = _078_; bit 14 = _017_; bit 15 = _020_.
- h238 (unconfirmed): 8 bits, bit order from net_id: bit 0 = _057_; bit 1 = _060_; bit 2 = _023_; bit 3 = _026_; bit 4 = _029_; bit 5 = _032_; bit 6 = _035_; bit 7 = _038_.
- h239 (unconfirmed): 8 bits, bit order from net_id: bit 0 = _022_; bit 1 = _025_; bit 2 = _028_; bit 3 = _031_; bit 4 = _034_; bit 5 = _037_; bit 6 = _056_; bit 7 = _059_.
- h240 (unconfirmed): 8 bits, bit order from net_id: bit 0 = _063_; bit 1 = _066_; bit 2 = _069_; bit 3 = _072_; bit 4 = _075_; bit 5 = _078_; bit 6 = _017_; bit 7 = _020_.
- h241 (unconfirmed): 8 bits, bit order from net_id: bit 0 = _062_; bit 1 = _065_; bit 2 = _068_; bit 3 = _071_; bit 4 = _074_; bit 5 = _077_; bit 6 = _016_; bit 7 = _019_.

State machines: none.

Roles of committed claims: datapath: h73, h74, h75, h76, h77, h78, h79, h80, h81, h82, h83, h84, h85, h86, h87, h88, h89, h90, h91.

## 6. Candidates (not committed, unconfirmed)

- h1 (unconfirmed): 40 cells form a flip-flop with enable, `ff_en: 8 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _010_, _011_, _012_, _013_, _014_, _015_, _000_, _001_; en = nets byteena[1]. Outputs: q = nets q[8], q[9], q[10], q[11], q[12], q[13], q[14], q[15]. Role: datapath.
- h4 (unconfirmed): 40 cells form a flip-flop with enable, `ff_en: 8 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _002_, _003_, _004_, _005_, _006_, _007_, _008_, _009_; en = nets byteena[0]. Outputs: q = nets q[0], q[1], q[2], q[3], q[4], q[5], q[6], q[7]. Role: datapath.
- h41 (unconfirmed): 5 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _000_; en = nets byteena[1]. Outputs: q = nets q[14]. Role: datapath.
- h43 (unconfirmed): 5 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _001_; en = nets byteena[1]. Outputs: q = nets q[15]. Role: datapath.
- h45 (unconfirmed): 5 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _002_; en = nets byteena[0]. Outputs: q = nets q[0]. Role: datapath.
- h47 (unconfirmed): 5 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _003_; en = nets byteena[0]. Outputs: q = nets q[1]. Role: datapath.
- h49 (unconfirmed): 5 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _004_; en = nets byteena[0]. Outputs: q = nets q[2]. Role: datapath.
- h51 (unconfirmed): 5 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _005_; en = nets byteena[0]. Outputs: q = nets q[3]. Role: datapath.
- h53 (unconfirmed): 5 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _006_; en = nets byteena[0]. Outputs: q = nets q[4]. Role: datapath.
- h55 (unconfirmed): 5 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _007_; en = nets byteena[0]. Outputs: q = nets q[5]. Role: datapath.
- h57 (unconfirmed): 5 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _008_; en = nets byteena[0]. Outputs: q = nets q[6]. Role: datapath.
- h59 (unconfirmed): 5 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _009_; en = nets byteena[0]. Outputs: q = nets q[7]. Role: datapath.
- h61 (unconfirmed): 5 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _010_; en = nets byteena[1]. Outputs: q = nets q[8]. Role: datapath.
- h63 (unconfirmed): 5 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _011_; en = nets byteena[1]. Outputs: q = nets q[9]. Role: datapath.
- h65 (unconfirmed): 5 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _012_; en = nets byteena[1]. Outputs: q = nets q[10]. Role: datapath.
- h67 (unconfirmed): 5 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _013_; en = nets byteena[1]. Outputs: q = nets q[11]. Role: datapath.
- h69 (unconfirmed): 5 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _014_; en = nets byteena[1]. Outputs: q = nets q[12]. Role: datapath.
- h71 (unconfirmed): 5 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _015_; en = nets byteena[1]. Outputs: q = nets q[13]. Role: datapath.
- h42 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _000_; rst = nets resetn. Outputs: q = nets q[14]. Role: datapath.
- h44 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _001_; rst = nets resetn. Outputs: q = nets q[15]. Role: datapath.
- h46 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _002_; rst = nets resetn. Outputs: q = nets q[0]. Role: datapath.
- h48 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _003_; rst = nets resetn. Outputs: q = nets q[1]. Role: datapath.
- h50 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _004_; rst = nets resetn. Outputs: q = nets q[2]. Role: datapath.
- h52 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _005_; rst = nets resetn. Outputs: q = nets q[3]. Role: datapath.
- h54 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _006_; rst = nets resetn. Outputs: q = nets q[4]. Role: datapath.
- h56 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _007_; rst = nets resetn. Outputs: q = nets q[5]. Role: datapath.
- h58 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _008_; rst = nets resetn. Outputs: q = nets q[6]. Role: datapath.
- h60 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _009_; rst = nets resetn. Outputs: q = nets q[7]. Role: datapath.
- h62 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _010_; rst = nets resetn. Outputs: q = nets q[8]. Role: datapath.
- h64 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _011_; rst = nets resetn. Outputs: q = nets q[9]. Role: datapath.
- h66 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _012_; rst = nets resetn. Outputs: q = nets q[10]. Role: datapath.
- h68 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _013_; rst = nets resetn. Outputs: q = nets q[11]. Role: datapath.
- h70 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _014_; rst = nets resetn. Outputs: q = nets q[12]. Role: datapath.
- h72 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _015_; rst = nets resetn. Outputs: q = nets q[13]. Role: datapath.
- h206 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _000_; rst = nets resetn. Outputs: q = nets q[14]. Role: datapath.
- h208 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _001_; rst = nets resetn. Outputs: q = nets q[15]. Role: datapath.
- h210 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _002_; rst = nets resetn. Outputs: q = nets q[0]. Role: datapath.
- h212 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _003_; rst = nets resetn. Outputs: q = nets q[1]. Role: datapath.
- h214 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _004_; rst = nets resetn. Outputs: q = nets q[2]. Role: datapath.
- h216 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _005_; rst = nets resetn. Outputs: q = nets q[3]. Role: datapath.
- h218 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _006_; rst = nets resetn. Outputs: q = nets q[4]. Role: datapath.
- h220 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _007_; rst = nets resetn. Outputs: q = nets q[5]. Role: datapath.
- h222 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _008_; rst = nets resetn. Outputs: q = nets q[6]. Role: datapath.
- h224 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _009_; rst = nets resetn. Outputs: q = nets q[7]. Role: datapath.
- h226 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _010_; rst = nets resetn. Outputs: q = nets q[8]. Role: datapath.
- h228 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _011_; rst = nets resetn. Outputs: q = nets q[9]. Role: datapath.
- h230 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _012_; rst = nets resetn. Outputs: q = nets q[10]. Role: datapath.
- h232 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _013_; rst = nets resetn. Outputs: q = nets q[11]. Role: datapath.
- h234 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _014_; rst = nets resetn. Outputs: q = nets q[12]. Role: datapath.
- h236 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _015_; rst = nets resetn. Outputs: q = nets q[13]. Role: datapath.
- h9 (unconfirmed): 8 cells form an 8-bit bus, `bus: 8 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _022_; slice1 = nets _025_; slice2 = nets _028_; slice3 = nets _031_; slice4 = nets _034_; slice5 = nets _037_; slice6 = nets _056_; slice7 = nets _059_. Role: datapath.
- h14 (unconfirmed): 8 cells form an 8-bit bus, `bus: 8 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _062_; slice1 = nets _065_; slice2 = nets _068_; slice3 = nets _071_; slice4 = nets _074_; slice5 = nets _077_; slice6 = nets _016_; slice7 = nets _019_. Role: datapath.
- h238 (unconfirmed): 8 cells form an 8-bit bus, `bus: 8 bits`. No proof recorded. Confidence 0.8581. Inputs: ctrl = nets byteena[1]; slice0 = nets _057_; slice1 = nets _060_; slice2 = nets _023_; slice3 = nets _026_; slice4 = nets _029_; slice5 = nets _032_; slice6 = nets _035_; slice7 = nets _038_. Role: datapath.
- h240 (unconfirmed): 8 cells form an 8-bit bus, `bus: 8 bits`. No proof recorded. Confidence 0.8581. Inputs: ctrl = nets byteena[0]; slice0 = nets _063_; slice1 = nets _066_; slice2 = nets _069_; slice3 = nets _072_; slice4 = nets _075_; slice5 = nets _078_; slice6 = nets _017_; slice7 = nets _020_. Role: datapath.
- h239 (unconfirmed): 8 cells form an 8-bit bus, `bus: 8 bits`. No proof recorded. Confidence 0.6682. Inputs: ctrl = nets byteena[1]; slice0 = nets _022_; slice1 = nets _025_; slice2 = nets _028_; slice3 = nets _031_; slice4 = nets _034_; slice5 = nets _037_; slice6 = nets _056_; slice7 = nets _059_. Role: datapath.
- h241 (unconfirmed): 8 cells form an 8-bit bus, `bus: 8 bits`. No proof recorded. Confidence 0.6682. Inputs: ctrl = nets byteena[0]; slice0 = nets _062_; slice1 = nets _065_; slice2 = nets _068_; slice3 = nets _071_; slice4 = nets _074_; slice5 = nets _077_; slice6 = nets _016_; slice7 = nets _019_. Role: datapath.
- h2 (unconfirmed): 40 cells form a flip-flop with synchronous reset, `ff_srst: 8 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _010_, _011_, _012_, _013_, _014_, _015_, _000_, _001_; rst = nets resetn. Outputs: q = nets q[8], q[9], q[10], q[11], q[12], q[13], q[14], q[15]. Role: datapath.
- h5 (unconfirmed): 40 cells form a flip-flop with synchronous reset, `ff_srst: 8 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _002_, _003_, _004_, _005_, _006_, _007_, _008_, _009_; rst = nets resetn. Outputs: q = nets q[0], q[1], q[2], q[3], q[4], q[5], q[6], q[7]. Role: datapath.
- h188 (unconfirmed): 64 cells form a flip-flop with synchronous reset, `ff_srst: 16 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _002_, _003_, _004_, _005_, _006_, _007_, _008_, _009_, _010_, _011_, _012_, _013_, _014_, _015_, _000_, _001_; rst = nets resetn. Outputs: q = nets q[0], q[1], q[2], q[3], q[4], q[5], q[6], q[7], q[8], q[9], q[10], q[11], q[12], q[13], q[14], q[15]. Role: datapath.

## 7. Rejected claims

(none)

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
