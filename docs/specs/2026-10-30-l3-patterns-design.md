# Loki III L3: design patterns (design)

Status: draft for Peter's review, 2026-10-30. Everything not marked as Peter's words is an agent
default he may override (section 14 lists them as one numbered list). Doc only: no L3 code exists
yet. The first measurement is the census, `experiments/l3-census/EXPERIMENT.md`.

Peter, 2026-10-30: "I like this pattern catalogue (or composite idioms), I think it needs to go
bigger and can be reflected as design pattern and goes down with provenance (the trick being
different synthesis tools might make different provenance paths) so this is a bigger idea" ...
"why can't we make this L3 in Loki as I think it should be." And: "Also note how the design patterns
change with target technology!"

## 1. Goal and place in the levels

Loki's levels so far: L0 = datasets (netlists with Odin III provenance as the answer key), L1 =
claims (`loki re`, `loki re --intent`: Bayesian hypotheses with proofs), L2 = analysis (`loki
analyze`: structure, clusters, graphlets, GNN baseline). **L3 = design patterns**: composite idioms
built from L1 claims. A pattern is not one construct (a counter, an FSM); it is a known way of wiring
several constructs together (a timer is a sequence-detector FSM, a shift register that loads, a
prescaler, a down counter and a done/ack handshake). L3 holds three things:

1. a **catalogue** of patterns, each with its HDL forms, its composition, its footprint per synthesis
   tool and per target technology, and the provenance path that produces the footprint;
2. **composite claims**: a claim that says "these L1 claims, wired this way, are an instance of
   pattern P", with a posterior and a proof (section 6);
3. a **closed loop** (section 9): inspect, hypothesise, rebuild RTL from the claims, test against the
   netlist, refine.

Purpose chain (hub `docs/purpose.md`): Loki L1 and L2 purposes (recover behavioural, hierarchical
HDL; say why a construct is not recovered); hub L Q2.2 (which netlist patterns identify which RTL
idioms), L Q3.1 and L Q3.3 (where a construct is lost; how a target-specific transformation changes
its footprint), and Odin III O Q2.4 (target-aware optimisation: the same pattern is an exception for
one target and the default for another). Measures are structure-recovery measures: composite recall
and precision against RTL-side labels, footprint stability across tools and targets, and the fraction
of patterns that stay connected as the catalogue says. Area, speed and power are not touched here;
the Norns use (packer hints) is noted in section 11 and not built.

Why L3 and not "more L1 kinds": the Gate-Breaker failures (Prob151_review2015_fsm,
Prob156_review2015_fancytimer, hints-v2 run) are not misses of one construct. In `fancytimer` the
counters and the FSM are each claimed correctly by L1 v2 yet the model still fails, because nothing
says that the shift register is loaded in states B0..B3, that the 1000-cycle prescaler and the down
counter are one timer, and that `done` waits for `ack`. What is missing is the composition.

## 2. Decisions

Peter's words are in the quotation at the top. Agent defaults:

| # | Default |
|---|---|
| 1 | L3 consumes L1 claims (`intent.json` kinds: fsm, counter, shift_reg, lfsr, register, eq_const, bus, ...) and the netlist graph. It never edits L1 results and never reads a label. |
| 2 | A catalogue entry is data (JSON, versioned), not code. A detector is a small signature interpreter over L1 claims plus a connectedness test, so adding a pattern needs no core change. |
| 3 | Footprint and provenance path are first-class fields per (tool, target) pair, not one flat footprint. The catalogue says what each tool does to the pattern, not only what the pattern is. |
| 4 | Target technology is an axis of its own, next to the tool axis (section 3). |
| 5 | "No pattern: keep as gates" (glue logic) is an explicit entry, so that unexplained logic is a stated outcome and not a silent failure. |
| 6 | Proof first: a composite claim is proved by the rebuild-and-test loop (section 9) or by exhaustive/sampled equivalence of the composite cone; unproved composites stay candidates with a posterior. |
| 7 | No LLM step in L3 detection, rebuild or test. The model-in-the-loop use (hints into Gate-Breaker-style prompts) is an experiment on top, as hints v1/v2. |
| 8 | The catalogue is seeded by hand from the failures and families already measured (section 8), then grown by the census (section 12). |

## 3. Target technology as an axis

A pattern's netlist footprint depends on two things the RTL does not say: the **tool** (Odin III,
Yosys, ...) and the **target** (the cell library and hard resources the netlist is mapped to). The
catalogue records both. Targets used here, with the tools that produce them in this repository:

| target id | description | produced by | hard resources |
|---|---|---|---|
| `gate` (ASIC-like) | small gate library; cmos6 for Odin III (floor f3), `cmos_cells.lib` for Yosys as Gate-Breaker uses it | Odin III `lower; abc; dfflibmap`, Yosys `techmap; dfflibmap; abc -liberty` | none: every adder, multiplier and memory is gates and flip-flops |
| `lut` (FPGA soft logic) | K-input LUT (K = 6) plus flip-flops, no hard blocks (floor f2) | Odin III `lower; abc --lut 6`, Yosys `abc -lut 6` | none: a carry chain is LUT logic, a memory is a flip-flop array |
| `lut+hard` (FPGA with hard resources) | LUT6 plus carry chains (`adder` cells), hard multipliers (DSP) and block RAM, bound onto the VTR architecture (`k6_frac_N10_frac_chain_mem32K_40nm`) by `partial_map` / `hardmap` (floor f1-k6) | Odin III `hardmap` on the architecture record | adder chains, `multiply` WIDTH 36, `single_port_ram` / `dual_port_ram` slices |

Expected transformation per target (which pattern change is claimed, to be measured, not assumed):

| construct | `gate` | `lut` | `lut+hard` |
|---|---|---|---|
| FSM state register | the `fsm` pass recodes below 32 states to one-hot (Odin III `auto`; same rule as Yosys fsm_recode); the HDL encoding often survives in Yosys flows without `fsm_recode` | same; one-hot is cheap in FFs, packing into LUT+FF pairs | same as `lut` |
| counter, adder | ripple of gates (xor/and per bit); no carry structure to find | per-bit LUT logic; the carry is LUT-to-LUT wiring | `adder` cells in a chain: the counter increment becomes a hard carry chain, the L1 `counter` footprint changes from gates to a chain plus flip-flops |
| comparator | gates / LUT tree | LUT tree | adder-chain based when mapped onto a chain (a subtract) or LUT tree |
| multiplier | gate array | LUT array | `multiply` hard block (split above the block width) |
| memory (register file) | flip-flop array plus read mux trees of gates | flip-flop array plus LUT mux trees | RAM slices (depth split by address bits, one slice per data bit) when the port pattern fits; else the flip-flop array |
| shift register | chain of flip-flops (no logic) | chain of flip-flops (LUT-free; may become SRL-style on other archs) | chain of flip-flops |

This ties to hub O Q2.4 (target-aware optimisation: Odin III chooses the encoding and the hard-block
binding by target) and to L Q3.3 (does Loki recover more when it knows which transformation was
applied). The FSM-encoding experiment (`experiments/fsm-encoding`) is the first single-pattern
instance of this axis; L3 generalises it to composites. A consequence for detection: a pattern's
**signature** is stated per target (section 7), because the same RTL idiom has a different claim set
per target (an up counter is a `counter` claim on `gate` and `lut`, and a counter whose increment sits
in an `adder` chain on `lut+hard`).

## 4. The catalogue entry (schema)

One entry is a JSON object (`catalogue/<id>.json`, schema 1, sorted keys). Fields:

| field | meaning |
|---|---|
| `id`, `name`, `version` | stable id (`timer`, `fsm_counter`, `glue`), human name, entry version |
| `purpose` | the RQ id and measure the entry serves (L Q2.2 and so on) |
| `hdl_forms` | list of RTL idioms with a short Verilog example each (e.g. counter as `cnt <= cnt - 1`, as a case on `state`, as a generate loop); the forms drive the RTL-side labeller |
| `composition` | `parts`: list of `{role, l1_kind, params}`; `wires`: list of `{from, to, via}` where `via` is one of `direct` (a net from a part's output to the other's input), `comb` (through combinational glue of at most `max_depth` gates), `clock/reset` (shared control only); `optional_parts` |
| `footprint` | per (tool, target): `claims` (the L1 claim kinds and counts expected), `encoding` (e.g. one-hot / binary for an FSM), `cells` (cell counts or ratios), `connectedness` (which wires of `composition` survive as stated), `notes`. Entries are filled from the census, not guessed |
| `provenance` | per (tool, target): the pass sequence that produced the footprint, as a list of `{pass, effect}` (section 5) |
| `detector` | the signature (section 7): required claims, wires, and the negative conditions |
| `proof` | the method (section 6.3) and its cost class |
| `frequency` | per corpus: designs with the pattern, instances, from the census |
| `exceptions` | known confusions with other entries, the "exception HDL pattern" notes, and whether the entry also serves as a packer hint (section 11) |

Glue logic (`glue`) is an entry with an empty `composition` and the rule "keep as gates": a cone of
combinational logic with no sequential claim attached, reported as unexplained, not as a failure.

## 5. Footprint and provenance path per tool

Different synthesis tools make different provenance paths: the same RTL idiom goes through different
passes, and what survives for L3 to use differs.

- **Odin III.** Per-pass provenance: every node, net and wire carries a provenance ID in an
  append-only lineage DAG (kind source / imported / derived, pass run, operation, source locations,
  AST node, hierarchical path, parents; `docs/IR.md` 6; granularity DAG with op classes and the
  construct table, ADR D14 / IR-12a). The L0 dataset exports it as `construct_types`, a chain such as
  `$sdff|$sub|$mux` per cell and the HDL line span. So for an Odin III netlist the **provenance path
  of a pattern instance is observable**: the chain of statement, block and module a cell came from,
  and, with per-pass records, which pass created or merged it (`fsm` recode, `opt`, `lower`, `abc`,
  `dfflibmap`, `hardmap`).
- **Yosys.** The `src` attribute marks cells with the source location they came from; passes keep or
  drop it (`abc` re-synthesises logic and loses most; flip-flops mapped by `dfflibmap` keep the
  position of the `$dff` they replace). There is no pass lineage DAG and no construct table. The
  provenance path of a pattern instance is therefore **inferred** (from the pass script and the
  `src` positions that remain), not observed. The Gate-Breaker flow drops attributes at
  `write_verilog -noattr`.
- Consequence: the catalogue stores a `provenance` field per (tool, target) as the *pass sequence that
  transforms the pattern*, and the census compares footprints (claims, encoding, connectedness) across
  tools; the L0 construct chain is used as the RTL-side check for Odin III netlists only.

## 6. Composite claims

### 6.1 Form

A composite claim is `{id, kind: "pattern", pattern, version, parts, wires, p, status, evidence,
proof, tool, target}` where:

- `parts` maps each composition role to the **L1 claim ids** that fill it (`{"counter": "h7",
  "fsm": "h2"}`); an L1 claim keeps its own `p`, `status` and proof, and is never copied;
- `wires` lists the nets that connect the parts as the entry says: `{from_role, to_role, nets, depth}`
  (depth = number of combinational cells between);
- `status` is `proved`, `candidate` or `rejected` as in L1; `p` is a posterior (6.2);
- `tool` and `target` are the footprint the signature matched (when known; `unknown` otherwise).

### 6.2 Posterior

Log-odds, as L1 (L1 spec 6): prior from the catalogue `frequency` of the pattern per corpus
(Laplace-smoothed); plus the log-odds of each part claim given it is proved or a candidate (a rejected
part kills the composite); plus evidence terms for the wires (a direct wire +, a comb wire at depth d
decays with d, a missing required wire -); competition between composites that claim the same
flip-flops follows the L1 rule (6.5 of the L1 spec). The terms are hand-set first, then fitted on
the census; fitting on the measured designs is declared circular as in the FSM-encoding experiment
and avoided.

### 6.3 Proof methods

In order of cost: (a) **structural**: all parts proved and all required wires present: the composite
is "as claimed", not proved correct; (b) **composite cone equivalence**: the cone of the part
flip-flops is extracted and compared with the entry's reference cone (exhaustive for at most 20
inputs, sampled beyond, as the v2 intent verify); (c) **rebuild and test** (section 9): the RTL
rebuilt from the composite is checked against the netlist by equivalence (`loki.equiv`) or
simulation; only (c) can mark a composite `proved` for sequential behaviour.

## 7. Detector

A detector for entry E is: a set of required L1 claims (kind, params constraints), the required
wires (direct or comb within `max_depth` gates, found with a bounded forward/backward walk through
combinational cells that stops at flip-flops), and negative conditions (a claim that must not be
present). The signature is stated **per target**: `gate`/`lut` use the sequential claims directly;
`lut+hard` first treats an `adder` chain feeding a flip-flop group as the increment of a counter (the
L1 `hard` detector unmaps the chain, spec 7.2). The matching is over the claim graph (nodes = L1
claims, edges = wires), so it is a subgraph match on a small graph, not on the netlist.
Where several signatures match, the composite with the most parts wins (L1 competition rule).

## 8. Seed entries

Seeded from the hints-v2 failures, the round 4 families and the v2 kinds (FSM, counter, shift
register, LFSR, register). Columns: HDL form, composition, expected footprint note (to be replaced
by census numbers).

| id | HDL forms | composition | notes |
|---|---|---|---|
| `fsm` | `case (state)` with `next` block; if/else chain; enum states | state register + next-state logic + output logic | encoding changes by tool and target (section 3) |
| `counter` | `cnt <= cnt + 1` / `- 1`; modulo with compare-and-clear; enable | register + incrementer feedback | up/down, modulus, enable; ripple on `gate`, chain on `lut+hard` |
| `shift` | `{q[n-2:0], d}`, `q >> 1`, generate loop | chain of flip-flops with optional load mux | no logic when pure shift |
| `lfsr` | shift with xor of taps (`q_next[k] ^= q[0]`) | shift + xor taps | Prob082_lfsr32 |
| `prescaler` | counter that wraps at N-1 and pulses `tick` | counter + compare-to-const + reload | 999 in `fancytimer` |
| `down_timer` | load, decrement, flag at zero | counter + compare + load mux | `scount`, `fcount` |
| `seq_detector_fsm` | FSM that follows a bit pattern (S, S1, S11, S110) | FSM + input decode | Prob151/156 first states |
| `handshake` | state waits for `ack` then returns, `done` output | FSM state + input dependency + output | Wait state in `fancytimer` |
| `timer` | detector FSM + shift (load) + prescaler + down counter + done/ack | `seq_detector_fsm` + `shift` + `prescaler` + `down_timer` + `handshake` wired as in Prob156 | the motivating composite |
| `fsm_counter` | FSM whose state enables or is advanced by a counter | `fsm` + `counter`, wire counter flag to next-state or state to enable | round 4 `dpfsm` family |
| `fsm_shift` | FSM that loads or shifts a register | `fsm` + `shift` | Prob095_review2015_fsmshift |
| `regfile` | `reg [w:0] mem [0:d]` array with write enable and read mux | flip-flop array + decode + read mux | RAM slices on `lut+hard` |
| `register` | plain `always @(posedge clk) q <= d` | flip-flops | carries enable and reset forms |
| `adder_chain` | `a + b`, `a - b` | adders | `adder` cells on `lut+hard` |
| `glue` | combinational logic around flip-flops (Prob074_ece241_2014_q4: gates feeding three flip-flops) | none | "no pattern: keep as gates" |

## 9. Closed loop (REA-like)

Side note from Peter: the REA software reverse-engineering system runs a closed loop of inventory and
parsing, evidence linked to the exact file and line, explanation and proof, and reconstruction and
testing. L3's loop mirrors it for netlists (described here only from Peter's note):

1. **Inspect** (inventory and parsing): L1 `loki re --intent` gives claims with their evidence; L2
   gives structure and regions; the netlist graph gives connectedness.
2. **Hypothesise**: the detector (section 7) matches catalogue signatures over the claims and emits
   composite claims with posteriors. Evidence is linked to cells (their `wires`) and, for Odin III
   netlists, to HDL lines through the L0 construct chain.
3. **Rebuild** (reconstruction): each composite claim, plus the L1 claims it covers, is rendered as
   RTL by the entry's `hdl_forms` template (parameters from the claim facts: widths, modulus,
   transitions, reset). Uncovered cones stay as gates ("keep as gates").
4. **Test**: the rebuilt design is synthesised by the same flow and checked against the original
   netlist with `loki.equiv` (formal where it scales) or by random simulation (sampled, as the v2
   verify). An equivalent rebuild proves the composite; a mismatch localises the cones that differ.
5. **Refine**: claims whose cone fails are re-scored (log-odds lowered, status `rejected` if the
   cone is fully refuted), and the next iteration re-detects with those claims removed or replaced.

One iteration is steps 2 to 5. **Stop rule**: stop when the rebuilt design is equivalent, or when an
iteration changes no claim status and no posterior by more than 0.01, or after 8 iterations (the
L1 round bound). The report records, per iteration, the claims added, the cones tested and the
mismatch count; an unfinished loop reports which cones are still unexplained and why (the "say why a
construct is not recovered" purpose).

## 10. Outputs

`loki patterns <netlist-or-re-dir> --catalogue <dir> --out <dir>` (not built) writes `patterns.json`
(composite claims, schema 1, sorted keys), `rebuild.v` (when the loop ran), `loop.json` (iterations)
and a markdown report. Node and net names follow the L1 convention (anonymised `n<k>` in outputs).

## 11. Where the catalogue lives

- **A Mimir table** (`pattern_instance`): columns pattern, instance, design, tool, target, footprint
  (claims, encoding, cell counts), provenance path, frequency source. The census writes its rows here
  (`experiments/l3-census/results/*.csv` first; the table is a join of these).
- **A versioned file in loki**: `catalogue/` (one JSON per entry, schema 1), the source of truth for
  the detector; entries are versioned (`version`) and each footprint cites the census run that
  filled it.
- **Norns use (noted, not built).** The nornsIII exception-HDL-pattern catalogue
  (`docs/plan/heap-picking.md`, 11 rows: patterns with a detector that works before packing and the
  hint it would give the packer) and this catalogue are the same object seen from two sides: L3 entries
  detect the pattern in a netlist (what is it?), the Norns rows say what the packer should do with it
  (what to do?). The merge is a shared `id` and a `packer_hint` field on the entry, filled only when a
  Norns experiment measured an effect (data first, Peter 10-26).

## 12. First measurement: the census

`experiments/l3-census/EXPERIMENT.md`: which seed patterns occur in the VerilogEval references, round
4 and VTR Verilog (RTL-side labels from Odin III's word-level IR plus named idioms), and, per pattern x
tool x target, which L1 claims appear on the netlist, the FSM encoding, and whether the pieces stay
connected. Targets: `gate` and `lut` with both tools, `lut+hard` with Odin III only (a hard-block
Yosys target is the next step). The results fill the `footprint` and `frequency` fields.

## 13. Not in L3 (yet)

- Detectors, the rebuild templates, `loki patterns` and the Mimir table: designed here, not built.
- A learned detector (GNN on the claim graph); the L2 GNN baseline is the starting point.
- Instance-level matching of RTL labels to netlist claims for Yosys netlists (names do not survive);
  the census matches at design level.
- Yosys with a hard-block target and an Odin III vs Yosys comparison on hard resources.
- Hierarchy of patterns (a pattern inside a pattern beyond the seed `timer`).

## 14. Open questions (agent defaults; Peter may override)

1. Catalogue as JSON files in loki (default) vs rows in Mimir only.
2. Composition `max_depth` for `comb` wires: 6 gates (default, from the census) vs per-entry.
3. Posterior terms hand-set (default) vs fitted after the census on a held-out corpus.
4. `lut+hard` signature through the L1 `hard` detector unmap (default) vs a separate hard-aware claim.
5. Whether `loki patterns` ships as a subcommand (default) or a Wyrd step.
6. Whether the merge with the Norns catalogue shares ids now (default: noted only).
