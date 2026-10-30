Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 24427d8ac2db, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| bus | 2 | 35 | 0 |
| eq_const | 24 | 7 | 0 |
| ff_srst | 0 | 2 | 0 |

Input cells (in Loki's re-mapped netlist): 77.

Of the committed cells, 21 (in 2 claims) are marked only by attributes on existing cells (form attrs). Those claims are not modules, so the hierarchy below does not show them.

Recovered module hierarchy (a module contains its children):

- h8 eq_const_h8 (eq_const)
- h9 eq_const_h9 (eq_const)
- h16 eq_const_h16 (eq_const)
- h17 eq_const_h17 (eq_const)
- h18 eq_const_h18 (eq_const)
- h19 eq_const_h19 (eq_const)
- h20 eq_const_h20 (eq_const)
- h21 eq_const_h21 (eq_const)
- h22 eq_const_h22 (eq_const)
- h23 eq_const_h23 (eq_const)
- h34 eq_const_h34 (eq_const)
  - h27 eq_const_h27 (eq_const)
    - h26 eq_const_h26 (eq_const)
      - h25 eq_const_h25 (eq_const)
      - h32 eq_const_h32 (eq_const)
      - h338 eq_const_h338 (eq_const)
    - h33 eq_const_h33 (eq_const)
    - h376 eq_const_h376 (eq_const)
- h40 eq_const_h40 (eq_const)
- h77 eq_const_h77 (eq_const)
- h352 eq_const_h352 (eq_const)
- h353 eq_const_h353 (eq_const)
- h388 eq_const_h388 (eq_const)
- h389 eq_const_h389 (eq_const)

## 4. Committed claims

- h8: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets load, data[0]. Outputs: Y = nets _042_. Recovered as module eq_const_h8, instance eq_const_h8_i. Role: datapath.
- h9: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets load, data[1]. Outputs: Y = nets _046_. Recovered as module eq_const_h9, instance eq_const_h9_i. Role: datapath.
- h16: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h8 (proof transfer). Confidence 0.9999. Inputs: A = nets load, data[2]. Outputs: Y = nets _050_. Recovered as module eq_const_h16, instance eq_const_h16_i. Role: datapath.
- h17: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h8 (proof transfer). Confidence 0.9999. Inputs: A = nets load, data[3]. Outputs: Y = nets _054_. Recovered as module eq_const_h17, instance eq_const_h17_i. Role: datapath.
- h18: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h8 (proof transfer). Confidence 0.9999. Inputs: A = nets load, data[4]. Outputs: Y = nets _058_. Recovered as module eq_const_h18, instance eq_const_h18_i. Role: datapath.
- h19: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h8 (proof transfer). Confidence 0.9999. Inputs: A = nets load, data[5]. Outputs: Y = nets _062_. Recovered as module eq_const_h19, instance eq_const_h19_i. Role: datapath.
- h20: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h8 (proof transfer). Confidence 0.9999. Inputs: A = nets load, data[6]. Outputs: Y = nets _066_. Recovered as module eq_const_h20, instance eq_const_h20_i. Role: datapath.
- h21: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h8 (proof transfer). Confidence 0.9999. Inputs: A = nets load, data[7]. Outputs: Y = nets _070_. Recovered as module eq_const_h21, instance eq_const_h21_i. Role: datapath.
- h22: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h8 (proof transfer). Confidence 0.9999. Inputs: A = nets load, data[8]. Outputs: Y = nets _011_. Recovered as module eq_const_h22, instance eq_const_h22_i. Role: datapath.
- h23: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h8 (proof transfer). Confidence 0.9999. Inputs: A = nets load, data[9]. Outputs: Y = nets _012_. Recovered as module eq_const_h23, instance eq_const_h23_i. Role: datapath.
- h34: 6 cells form a comparison against a constant, `Y = (A != 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets count_value[0], count_value[1], count_value[2], count_value[3]. Outputs: Y = nets _030_. Recovered as module eq_const_h34, instance eq_const_h34_i. Role: datapath.
- h27: 5 cells form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets count_value[0], count_value[1], count_value[2], count_value[3]. Outputs: Y = nets _029_. Recovered as module eq_const_h27, instance eq_const_h27_i. Role: datapath.
- h26: 3 cells form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets count_value[0], count_value[1], count_value[2]. Outputs: Y = nets _028_. Recovered as module eq_const_h26, instance eq_const_h26_i. Role: datapath.
- h25: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets count_value[0], count_value[1]. Outputs: Y = nets _025_. Recovered as module eq_const_h25, instance eq_const_h25_i. Role: datapath.
- h32: 2 cells form a comparison against a constant, `Y = (A != 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets count_value[0], count_value[1]. Outputs: Y = nets _026_. Recovered as module eq_const_h32, instance eq_const_h32_i. Role: datapath.
- h338: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets count_value[2], _026_. Outputs: Y = nets _028_. Recovered as module eq_const_h338, instance eq_const_h338_i. Role: datapath.
- h33: 4 cells form a comparison against a constant, `Y = (A != 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets count_value[0], count_value[1], count_value[2]. Outputs: Y = nets _027_. Recovered as module eq_const_h33, instance eq_const_h33_i. Role: datapath.
- h376: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets count_value[3], _027_. Outputs: Y = nets _029_. Recovered as module eq_const_h376, instance eq_const_h376_i. Role: datapath.
- h40: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets count_value[0], count_value[1]. Outputs: Y = nets _043_. Recovered as module eq_const_h40, instance eq_const_h40_i. Role: datapath.
- h77: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets load, count_value[9]. Outputs: Y = nets _013_. Recovered as module eq_const_h77, instance eq_const_h77_i. Role: datapath.
- h352: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _026_, _043_. Outputs: Y = nets _044_. Recovered as module eq_const_h352, instance eq_const_h352_i. Role: datapath.
- h353: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets count_value[2], _026_. Outputs: Y = nets _047_. Recovered as module eq_const_h353, instance eq_const_h353_i. Role: datapath.
- h388: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _027_, _047_. Outputs: Y = nets _048_. Recovered as module eq_const_h388, instance eq_const_h388_i. Role: datapath.
- h389: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets count_value[3], _027_. Outputs: Y = nets _051_. Recovered as module eq_const_h389, instance eq_const_h389_i. Role: datapath.
- h80: 12 cells form a 12-bit bus, `bus: 12 bits`. No proof recorded. Confidence 0.9601. Inputs: ctrl = nets load; slice0 = nets _042_; slice1 = nets _046_; slice10 = nets _040_; slice11 = nets _013_; slice2 = nets _050_; slice3 = nets _054_; slice4 = nets _058_; slice5 = nets _062_; slice6 = nets _066_; slice7 = nets _070_; slice8 = nets _011_; slice9 = nets _012_. Role: datapath.
- h81: 9 cells form a 9-bit bus, `bus: 9 bits`. No proof recorded. Confidence 0.9601. Inputs: ctrl = nets _040_; slice0 = nets _041_; slice1 = nets _045_; slice2 = nets _049_; slice3 = nets _053_; slice4 = nets _057_; slice5 = nets _061_; slice6 = nets _065_; slice7 = nets _069_; slice8 = nets _010_. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h4 (unconfirmed): 5 bits, bit order from wf: bit 0 = _025_; bit 1 = _029_; bit 2 = _033_; bit 3 = _036_; bit 4 = tc.
- h5 (unconfirmed): 7 bits, bit order from wf: bit 0 = _025_; bit 1 = _028_; bit 2 = _029_; bit 3 = _032_; bit 4 = _033_; bit 5 = _036_; bit 6 = _036_.
- h6 (unconfirmed): 4 bits, bit order from wf: bit 0 = _026_; bit 1 = _030_; bit 2 = _034_; bit 3 = _035_.
- h7 (unconfirmed): 7 bits, bit order from wf: bit 0 = _026_; bit 1 = _027_; bit 2 = _030_; bit 3 = _031_; bit 4 = _034_; bit 5 = _035_; bit 6 = _035_.
- h10 (unconfirmed): 5 bits, bit order from wf: bit 0 = _043_; bit 1 = _047_; bit 2 = _055_; bit 3 = _063_; bit 4 = _071_.
- h11 (unconfirmed): 5 bits, bit order from wf: bit 0 = _043_; bit 1 = _051_; bit 2 = _059_; bit 3 = _022_; bit 4 = _012_.
- h12 (unconfirmed): 7 bits, bit order from wf: bit 0 = _043_; bit 1 = _047_; bit 2 = _051_; bit 3 = _055_; bit 4 = _059_; bit 5 = _063_; bit 6 = _022_.
- h13 (unconfirmed): 5 bits, bit order from wf: bit 0 = _044_; bit 1 = _048_; bit 2 = _056_; bit 3 = _064_; bit 4 = _072_.
- h14 (unconfirmed): 5 bits, bit order from wf: bit 0 = _044_; bit 1 = _052_; bit 2 = _060_; bit 3 = _068_; bit 4 = _009_.
- h15 (unconfirmed): 7 bits, bit order from wf: bit 0 = _044_; bit 1 = _048_; bit 2 = _052_; bit 3 = _056_; bit 4 = _060_; bit 5 = _064_; bit 6 = _068_.
- h79 (unconfirmed): 3 bits, bit order from net_id: bit 0 = tc; bit 1 = _072_; bit 2 = _014_.
- h80: 12 bits, bit order from net_id: bit 0 = _042_; bit 1 = _046_; bit 2 = _050_; bit 3 = _054_; bit 4 = _058_; bit 5 = _062_; bit 6 = _066_; bit 7 = _070_; bit 8 = _011_; bit 9 = _012_; bit 10 = _040_; bit 11 = _013_.
- h81: 9 bits, bit order from net_id: bit 0 = _041_; bit 1 = _045_; bit 2 = _049_; bit 3 = _053_; bit 4 = _057_; bit 5 = _061_; bit 6 = _065_; bit 7 = _069_; bit 8 = _010_.
- h82 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _071_; bit 1 = _068_.
- h163 (unconfirmed): 4 bits, bit order from wf: bit 0 = _028_; bit 1 = _032_; bit 2 = _036_; bit 3 = _040_.
- h164 (unconfirmed): 6 bits, bit order from wf: bit 0 = _028_; bit 1 = _029_; bit 2 = _032_; bit 3 = _033_; bit 4 = _036_; bit 5 = _036_.
- h165 (unconfirmed): 3 bits, bit order from wf: bit 0 = _027_; bit 1 = _031_; bit 2 = _035_.
- h166 (unconfirmed): 6 bits, bit order from wf: bit 0 = _027_; bit 1 = _030_; bit 2 = _031_; bit 3 = _034_; bit 4 = _035_; bit 5 = _035_.
- h167 (unconfirmed): 4 bits, bit order from wf: bit 0 = _029_; bit 1 = _033_; bit 2 = _036_; bit 3 = tc.
- h168 (unconfirmed): 3 bits, bit order from wf: bit 0 = _030_; bit 1 = _034_; bit 2 = _035_.
- h169 (unconfirmed): 4 bits, bit order from wf: bit 0 = _051_; bit 1 = _059_; bit 2 = _022_; bit 3 = _044_.
- h170 (unconfirmed): 4 bits, bit order from wf: bit 0 = _052_; bit 1 = _060_; bit 2 = _068_; bit 3 = _045_.
- h171 (unconfirmed): 4 bits, bit order from wf: bit 0 = _047_; bit 1 = _055_; bit 2 = _063_; bit 3 = _071_.
- h172 (unconfirmed): 6 bits, bit order from wf: bit 0 = _047_; bit 1 = _051_; bit 2 = _055_; bit 3 = _059_; bit 4 = _063_; bit 5 = _022_.
- h173 (unconfirmed): 4 bits, bit order from wf: bit 0 = _048_; bit 1 = _056_; bit 2 = _064_; bit 3 = _072_.
- h174 (unconfirmed): 6 bits, bit order from wf: bit 0 = _048_; bit 1 = _052_; bit 2 = _056_; bit 3 = _060_; bit 4 = _064_; bit 5 = _068_.
- h334 (unconfirmed): 10 bits, bit order from net_id: bit 0 = _042_; bit 1 = _046_; bit 2 = _050_; bit 3 = _054_; bit 4 = _058_; bit 5 = _062_; bit 6 = _066_; bit 7 = _070_; bit 8 = _011_; bit 9 = _012_.
- h396 (unconfirmed): 3 bits, bit order from wf: bit 0 = _032_; bit 1 = _036_; bit 2 = _040_.
- h397 (unconfirmed): 3 bits, bit order from wf: bit 0 = _033_; bit 1 = _036_; bit 2 = tc.
- h398 (unconfirmed): 3 bits, bit order from wf: bit 0 = _059_; bit 1 = _022_; bit 2 = _045_.
- h399 (unconfirmed): 3 bits, bit order from wf: bit 0 = _060_; bit 1 = _068_; bit 2 = _001_.
- h400 (unconfirmed): 3 bits, bit order from wf: bit 0 = _059_; bit 1 = _022_; bit 2 = _049_.
- h401 (unconfirmed): 3 bits, bit order from wf: bit 0 = _060_; bit 1 = _068_; bit 2 = _002_.
- h402 (unconfirmed): 3 bits, bit order from wf: bit 0 = _059_; bit 1 = _022_; bit 2 = _052_.
- h403 (unconfirmed): 3 bits, bit order from wf: bit 0 = _060_; bit 1 = _068_; bit 2 = _053_.
- h404 (unconfirmed): 3 bits, bit order from wf: bit 0 = _055_; bit 1 = _063_; bit 2 = _071_.
- h405 (unconfirmed): 3 bits, bit order from wf: bit 0 = _056_; bit 1 = _064_; bit 2 = _072_.

State machines: none.

Roles of committed claims: datapath: h8, h9, h16, h17, h18, h19, h20, h21, h22, h23, h25, h26, h27, h32, h33, h34, h40, h77, h80, h81, h338, h352, h353, h376, h388, h389.

## 6. Candidates (not committed, unconfirmed)

- h28 (unconfirmed): 7 cells form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets count_value[0], count_value[1], count_value[2], count_value[3], count_value[4]. Outputs: Y = nets _032_. Role: datapath.
- h29 (unconfirmed): 9 cells form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets count_value[0], count_value[1], count_value[2], count_value[3], count_value[4], count_value[5]. Outputs: Y = nets _033_. Role: datapath.
- h30 (unconfirmed): 11 cells form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets count_value[0], count_value[1], count_value[2], count_value[3], count_value[4], count_value[5], count_value[6]. Outputs: Y = nets _036_. Role: datapath.
- h31 (unconfirmed): 13 cells form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets count_value[0], count_value[1], count_value[2], count_value[3], count_value[4], count_value[5], count_value[6], count_value[7]. Outputs: Y = nets _036_. Role: datapath.
- h35 (unconfirmed): 8 cells form a comparison against a constant, `Y = (A != 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets count_value[0], count_value[1], count_value[2], count_value[3], count_value[4]. Outputs: Y = nets _031_. Role: datapath.
- h36 (unconfirmed): 10 cells form a comparison against a constant, `Y = (A != 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets count_value[0], count_value[1], count_value[2], count_value[3], count_value[4], count_value[5]. Outputs: Y = nets _034_. Role: datapath.
- h37 (unconfirmed): 12 cells form a comparison against a constant, `Y = (A != 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets count_value[0], count_value[1], count_value[2], count_value[3], count_value[4], count_value[5], count_value[6]. Outputs: Y = nets _035_. Role: datapath.
- h4 (unconfirmed): 5 cells form a 5-bit bus, `bus: 5 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _025_; slice1 = nets _029_; slice2 = nets _033_; slice3 = nets _036_; slice4 = nets tc. Role: datapath.
- h5 (unconfirmed): 7 cells form a 7-bit bus, `bus: 7 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _025_; slice1 = nets _028_; slice2 = nets _029_; slice3 = nets _032_; slice4 = nets _033_; slice5 = nets _036_; slice6 = nets _036_. Role: datapath.
- h7 (unconfirmed): 7 cells form a 7-bit bus, `bus: 7 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _026_; slice1 = nets _027_; slice2 = nets _030_; slice3 = nets _031_; slice4 = nets _034_; slice5 = nets _035_; slice6 = nets _035_. Role: datapath.
- h10 (unconfirmed): 5 cells form a 5-bit bus, `bus: 5 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _043_; slice1 = nets _047_; slice2 = nets _055_; slice3 = nets _063_; slice4 = nets _071_. Role: datapath.
- h11 (unconfirmed): 5 cells form a 5-bit bus, `bus: 5 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _043_; slice1 = nets _051_; slice2 = nets _059_; slice3 = nets _022_; slice4 = nets _012_. Role: datapath.
- h12 (unconfirmed): 7 cells form a 7-bit bus, `bus: 7 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _043_; slice1 = nets _047_; slice2 = nets _051_; slice3 = nets _055_; slice4 = nets _059_; slice5 = nets _063_; slice6 = nets _022_. Role: datapath.
- h13 (unconfirmed): 5 cells form a 5-bit bus, `bus: 5 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _044_; slice1 = nets _048_; slice2 = nets _056_; slice3 = nets _064_; slice4 = nets _072_. Role: datapath.
- h14 (unconfirmed): 5 cells form a 5-bit bus, `bus: 5 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _044_; slice1 = nets _052_; slice2 = nets _060_; slice3 = nets _068_; slice4 = nets _009_. Role: datapath.
- h15 (unconfirmed): 7 cells form a 7-bit bus, `bus: 7 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _044_; slice1 = nets _048_; slice2 = nets _052_; slice3 = nets _056_; slice4 = nets _060_; slice5 = nets _064_; slice6 = nets _068_. Role: datapath.
- h164 (unconfirmed): 6 cells form a 6-bit bus, `bus: 6 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _028_; slice1 = nets _029_; slice2 = nets _032_; slice3 = nets _033_; slice4 = nets _036_; slice5 = nets _036_. Role: datapath.
- h166 (unconfirmed): 6 cells form a 6-bit bus, `bus: 6 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _027_; slice1 = nets _030_; slice2 = nets _031_; slice3 = nets _034_; slice4 = nets _035_; slice5 = nets _035_. Role: datapath.
- h172 (unconfirmed): 6 cells form a 6-bit bus, `bus: 6 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _047_; slice1 = nets _051_; slice2 = nets _055_; slice3 = nets _059_; slice4 = nets _063_; slice5 = nets _022_. Role: datapath.
- h174 (unconfirmed): 6 cells form a 6-bit bus, `bus: 6 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _048_; slice1 = nets _052_; slice2 = nets _056_; slice3 = nets _060_; slice4 = nets _064_; slice5 = nets _068_. Role: datapath.
- h79 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.8569. Inputs: ctrl = nets _039_; slice0 = nets tc; slice1 = nets _072_; slice2 = nets _014_. Role: datapath.
- h334 (unconfirmed): 10 cells form a 10-bit bus, `bus: 10 bits`. No proof recorded. Confidence 0.8006. Inputs: ctrl = nets load; slice0 = nets _042_; slice1 = nets _046_; slice2 = nets _050_; slice3 = nets _054_; slice4 = nets _058_; slice5 = nets _062_; slice6 = nets _066_; slice7 = nets _070_; slice8 = nets _011_; slice9 = nets _012_. Role: datapath.
- h6 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _026_; slice1 = nets _030_; slice2 = nets _034_; slice3 = nets _035_. Role: datapath.
- h82 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _035_; slice0 = nets _071_; slice1 = nets _068_. Role: datapath.
- h163 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _028_; slice1 = nets _032_; slice2 = nets _036_; slice3 = nets _040_. Role: datapath.
- h165 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _027_; slice1 = nets _031_; slice2 = nets _035_. Role: datapath.
- h167 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _029_; slice1 = nets _033_; slice2 = nets _036_; slice3 = nets tc. Role: datapath.
- h168 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _030_; slice1 = nets _034_; slice2 = nets _035_. Role: datapath.
- h169 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _051_; slice1 = nets _059_; slice2 = nets _022_; slice3 = nets _044_. Role: datapath.
- h170 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _052_; slice1 = nets _060_; slice2 = nets _068_; slice3 = nets _045_. Role: datapath.
- h171 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _047_; slice1 = nets _055_; slice2 = nets _063_; slice3 = nets _071_. Role: datapath.
- h173 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _048_; slice1 = nets _056_; slice2 = nets _064_; slice3 = nets _072_. Role: datapath.
- h396 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _032_; slice1 = nets _036_; slice2 = nets _040_. Role: datapath.
- h397 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _033_; slice1 = nets _036_; slice2 = nets tc. Role: datapath.
- h398 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _059_; slice1 = nets _022_; slice2 = nets _045_. Role: datapath.
- h399 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _060_; slice1 = nets _068_; slice2 = nets _001_. Role: datapath.
- h400 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _059_; slice1 = nets _022_; slice2 = nets _049_. Role: datapath.
- h401 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _060_; slice1 = nets _068_; slice2 = nets _002_. Role: datapath.
- h402 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _059_; slice1 = nets _022_; slice2 = nets _052_. Role: datapath.
- h403 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _060_; slice1 = nets _068_; slice2 = nets _053_. Role: datapath.
- h404 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _055_; slice1 = nets _063_; slice2 = nets _071_. Role: datapath.
- h405 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _056_; slice1 = nets _064_; slice2 = nets _072_. Role: datapath.
- h374 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.5000. Inputs: rst = nets _046_. Role: datapath.
- h494 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.5000. Inputs: rst = nets _050_. Role: datapath.

## 7. Rejected claims

(none)

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
