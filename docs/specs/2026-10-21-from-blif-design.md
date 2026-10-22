# Loki III: `loki graph from-blif` (design)

Status: for Peter's review. A follow-up to Loki III L0 (`docs/specs/2026-10-21-l0-dataset-design.md`,
cited as L0 x.y). Source: L2 spec (`docs/specs/2026-10-21-l2-analysis-design.md`) section 14,
open question 2, which Peter accepted on 2026-10-21: "Real reverse engineering of an unlabelled
netlist needs a BLIF-to-`graph.json` path ... a small `loki graph from-blif` command in a later L0
follow-up (it needs L0's numbering and level computation); until then such a netlist goes through
L0's `build` with the Odin III binding." Agent defaults are FB-1 to FB-10 (section 9).

## 1. Goal

Turn a BLIF netlist that L0 did not make (no Verilog source, no provenance, any names) into the
files of one L0 floor directory, so that L2 (`load_graph`, clustering, graphlets) and L1
(`loki re <dir>/netlist.blif --floor auto`) can analyse it exactly as they analyse L0's output.

**Done when:** `loki graph from-blif X.blif --out D` writes `D/<design>/<floor>/` with
`netlist.blif`, `netlist.v`, `graph.json`, `labels.csv`, `key.json` and `meta.json`; every file
passes L0's validators and the floor invariants of L0 10 (items 1 to 6); both L0 equivalence checks
(section 3 step 7) give `equivalent`; and on an L0-built `netlist.blif` without output buffers (L0 6.2; the comparator micro's
`f2`) fed back in, the graph
has the same multiset of `(kind, fan_in, fan_out, level, lut_width, lut_table, is_seq, is_const,
hard_ports)` as L0's own `graph.json`.

## 2. Read through Odin III, or parse BLIF in Python? (recommendation: Odin III)

| | Odin III binding (`Design.read_blif`), as L0 | Pure Python BLIF reader in Loki III |
|---|---|---|
| BLIF coverage | Odin III's reader: `.model`/`.inputs`/`.outputs`/`.names` (on-set and off-set covers)/`.latch` (`re fe ah al`, none)/`.subckt`/`.blackbox`/`.cname`/`.attr`/`.param`, several models; its round trip is identical on the VTR goldens | a second reader to write and keep in step |
| Hierarchy | `flatten` (one pass) | own flattening |
| Hard cells (`adder`, `multiply`, RAMs) | pin directions from `lib/vtr.o3lib` via `read_techlib` | needs an `.o3lib` parser for directions |
| Reuse of L0 | `extract_netlist`, `number`, `build_labels`, `build_graph`/`levels`, `write_blif`, `deanonymise`, `check_equiv`, `netlist.v` writing: all unchanged or with a small addition (section 6) | numbering, graph and writer reused; extraction rewritten |
| Agreement with L1 | L1 reads the same file with the same reader (L1 3), so its level 0 and this graph see one netlist | two readers may disagree on corner cases |
| Dependency | `odin3` is already Loki III's runtime dependency (L0 8, `dependencies = ["odin3"]`) | none for this command |

**Recommendation: read through the Odin III binding** (FB-1). The L2 text's "without Odin III" is
read as "without the Odin III Verilog flow and its provenance"; L0's `build` cannot take a BLIF,
this command can. The pure-Python path would only pay off for a user who has L2's extras but not
the `odin3` wheel, which Loki III already requires.

## 3. Pipeline of one input

1. **Read** (`loki.odin.open_blif`): `odin3.default().load_abc()` once; a fresh `Design`;
   `run_script` of `read_techlib "<odin3_root>/lib/vtr.o3lib"` (FB-3) and of each `--techlib`,
   then `read_blif "<path>"` and `flatten`. The first model is the top (Odin III `read_blif`). An
   `Odin3Error` is exit 3 with `odin3: <status>` and the first `error:` log line (as L1's `loki
   re`).
2. **Extract** with L0's `extract_netlist(design, top)` (L0 Task 6) plus the kinds BLIF reading
   makes (section 6.1). Refusals (`Unsupported`, exit 3): a surviving instance of a user model
   (cannot happen after `flatten` unless a model is recursive), an implicit black box (a
   `.subckt` of a model that is neither in the file nor registered: Odin III gives its pins
   direction INOUT, so edges cannot be oriented; declare it with `.model X .blackbox` and
   `.inputs`/`.outputs`, or read a `--techlib` that has it), a `.names` with more than
   `SOP_MAX_INPUTS = 16` inputs (FB-5).
3. **Normalise** (`loki.fromblif.normalise`, pure): each `$sop` becomes a `$lut` `FinalCell` with
   `WIDTH` and the `LUT` string in L0's `LUT_ROW_ORDER` (L0 Task 4 Step 6), computed from the
   cover as Odin III's `$sop` simulates it (ON rows set 1; OFF rows: 1 except where a row
   matches; no rows: constant 0; a mix follows the ON rows); a zero-input `$sop` becomes a
   `$_CONST0_`/`$_CONST1_` cell (kind `const`). Then L0's own writer and graph code apply
   unchanged (FB-4).
4. **Spans cleared.** Every `FinalCell.spans` is set to `()` before labelling: a BLIF-read cell's
   `sources()` is the BLIF file and line (L1 3.1 fact 3), not an HDL location, so it must not
   fill `hdl_*` (FB-6).
5. **Number, label, graph** with L0's `number` (L0 6.1), `build_labels(nl, Snapshot((), (),
   top), num, {}, root)` and `build_graph` (levels, `loops_cut`). With an empty snapshot every
   logic cell is unmatched: section 5 lists the resulting label values.
6. **Write** the six files as L0 4 steps 6 and 7 (`netlist.v` from `read_blif netlist.blif` with
   the same techlib script, then `write_verilog`).
7. **Verify** as L0 9: `writer` (Odin III `write_blif --vtr` of the read and flattened design
   against Loki III's BLIF with the identity naming) and `anon` (Loki III's identity-named BLIF
   against `deanonymise(netlist.blif, key.json)`), `--match-unnamed` when hard cells are present.
   The `writer` reference is Odin III's BLIF of the flattened design, not the input file, so a
   hierarchical input compares flat against flat (FB-7). `differs` is exit 1.

## 4. CLI

```
loki graph from-blif <netlist.blif> --out DIR [--design ID] [--floor {f1-k6,f1-earch,f2,f3,auto}]
                     [--techlib FILE.o3lib ...] [--odin3-root DIR]
```

- `--design` default `blif_<stem>`, every character outside `[A-Za-z0-9_]` replaced by `_`
  (FB-8). The output directory is `DIR/<design>/<floor>/`; an existing directory is replaced.
- `--floor auto` (the default, FB-2): a path component that is a floor name (`.../f2/...`) wins;
  else `f2` when the netlist has no hard or black-box cell and no `.names` wider than 6 inputs;
  else exit 2 with `cannot tell the floor: give --floor`.
- `--odin3-root` default `$ODIN3_ROOT` (for `lib/vtr.o3lib` and `tools/equiv-check`).
- Exit: 0 written and `equivalent` (or `unproven`, recorded); 1 `differs` or an internal error;
  2 usage; 3 input unreadable or unsupported. One summary line on stdout:
  `from-blif: <design>/<floor>: N nodes, E edges, equiv <status>`.

## 5. Label values without provenance

`labels.csv` and the `labels` of `graph.json` keep L0's columns (L0 6.5) so every reader works
unchanged; the values follow from L0's own rules with an empty snapshot and no spans:

| Node | `construct_type` | `role` | `module_path` | `bus_name`, `bit_index` | `hdl_*`, `n_spans` |
|---|---|---|---|---|---|
| `pi`, `po` | `$port_in`, `$port_out` | `io` | as L0 for no spans | from the port bit name (L0 5.4) | `""`/`-1`, 0 |
| `const` | `""` | `const` | as L0 | from the net names (L0 5.4) | `""`/`-1`, 0 |
| `lut`, `ff`, `hard` | `""` (`construct_types` `""`, `n_construct_cells` 0) | `unknown` | as L0 | from the net names (L0 5.4) | `""`/`-1`, 0 |

`cell_type` is the final cell's type (`$lut`, `$_DFF_P_`, `adder`, ...), as in L0. `meta.json`
`unmatched` counts the `lut`, `ff` and `hard` nodes (all unmatched). `words.json` (L1 12.1) is not
written: there are no word cells. L0 invariant 6 already allows empty `hdl_*` when the construct
is empty and the role `unknown`.

## 6. Changes to L0's code (in the from-blif tasks, after L0 is built)

1. `extract.py`: kind `lut` for `$sop` (WIDTH >= 1), `const` for a zero-input `$sop`, `ff` for
   `$_FF_` (BLIF `.latch` without a control, Odin III's reader type), and `Unsupported` for a cell
   with an INOUT pin of a black-box type (section 3 step 2).
2. `blifout.py`: `.latch` keeps the cell's `INIT` when it is 0 or 1 (else `3`, as now), and
   `$_FF_` is written `.latch <d> <q> <init>` (FB-9). This amends L0 6.2, which writes `3` always:
   an input with `.latch ... 1` must stay equivalent after anonymisation.
3. `build.py`: the part of `build_floor` after extraction (number, labels, graph, write, verify,
   `netlist.v`) moves into `write_floor(nl, snap, *, design, floor, out_dir, script, odin3_root,
   root) -> FloorResult`, called by `build_floor` and by `from_blif`; L0's tests stay green.
4. `assemble.py`: `check_floor(path) -> list[str]` (invariants 1 to 6 for one floor directory;
   `words.json` checked when present) is split out of `check_dataset`, which calls it;
   `loki check` takes a floor directory as well as a dataset.
5. `cli.py`: the `graph from-blif` subcommand.

## 7. Where it slots into L0's order

It needs L0 Tasks 4 (writer, `LUT_ROW_ORDER`), 5 (labels, graph, levels), 6 (`odin.py`,
`extract.py`), 7 (`build.py`, `equiv.py`) and 10 (`cli.py`, `check_dataset`). It runs **after L0
Task 11** (the L0 exit test), as Tasks FB-1 to FB-3 of `docs/plans/2026-10-21-from-blif-plan.md`,
in parallel with L0 Tasks 12 and 13 (they touch `odin.py`'s F3 script and `bench.py`, not these
paths; `extract.py` kind mapping is the one shared file, merged with `git merge origin/main`). It
does not delay L0's exit and is not part of L0's acceptance.

## 8. Tests

- Pure: `sop_to_lut` on an ON-set cover, an OFF-set cover, a cover with `-`, no rows, a mixed
  cover, a width-1 buffer and inverter, a width-17 refusal; `normalise` turns zero-input `$sop`s
  into constants; `.latch` init 0/1/3 and `$_FF_` written by `blifout`.
- With Odin III (`skipUnless(odin_available())`): a named 4-bit ripple adder BLIF (fixture), an
  anonymous one (every signal `x<k>`), a two-model hierarchical BLIF, a `.latch ... 1` design, a
  design with a `vtr.o3lib` `adder` `.subckt` (F1-like, `--floor f1-k6`), an implicit black box
  (exit 3), a 17-input `.names` (exit 3); each `ok` case validates, is `equivalent`, and two runs
  are byte-identical. The L0 round trip of section 1 on the comparator micro's L0 floor.
- CLI: exit codes 0, 2 (`--floor auto` cannot tell), 3; `loki check <floor dir>` returns 0 on the
  output.

## 9. Agent defaults (Peter may override)

1. **FB-1** Read through the Odin III binding (section 2).
2. **FB-2** `--floor auto` from the path, else `f2` only for a pure LUT netlist of width <= 6,
   else ask for `--floor`. The floor is a model feature in L2 (one-hot), so it is never guessed
   beyond that.
3. **FB-3** `lib/vtr.o3lib` is always read first, so VTR hard cells (`adder`, `multiply`,
   `single_port_ram`, `dual_port_ram`) get pin directions; `--techlib` adds others.
4. **FB-4** `$sop` is converted to L0's `$lut` form, so `graph.json` (`lut_table`), the writer and
   L2's features see one LUT representation whatever made the netlist.
5. **FB-5** `.names` wider than 16 inputs are refused (a 2^16-row truth table is the most L0's
   minterm writer and `lut_table` hex should hold); real LUT and gate netlists stay far below.
6. **FB-6** No spans: BLIF lines are not HDL locations; L1 reads BLIF lines itself.
7. **FB-7** The `writer` check compares with Odin III's BLIF of the flattened design, as in L0,
   not with the input file.
8. **FB-8** Design id `blif_<stem>`, like L0's `micro_`/`ve_`/`vtr_` prefixes.
9. **FB-9** `.latch` keeps init 0/1 in Loki III's writer (an L0 amendment; L0 builds are
   unaffected unless a flip-flop has an init).
10. **FB-10** No `words.json`, no `design.json`, no manifest: the output is one floor directory, not a
    dataset.

## 10. Not in scope

`.gate`/`.mlatch`/`.conn` (Odin III's reader refuses them as unknown directives); gate-level
Verilog input (L1 3 already reads it through `write_blif --gates-as-names`); guessing hidden
structure (that is L1 and L2); a pure-Python BLIF reader.

## 11. Open questions (with recommendations)

1. **"Without Odin III" in L2 14.2.** This design uses the Odin III binding as a BLIF reader
   only. Recommend accepting that reading (FB-1); a pure-Python reader can be added later behind
   the same CLI if a user without the `odin3` wheel appears.
2. **`.gate` netlists (SIS/ABC genlib output).** Not readable by Odin III 1.0. Recommend: when
   needed, a text rewrite `.gate` to `.subckt` plus `--techlib <library>.o3lib` (after Odin III
   gate mapping, whose libraries are `.o3lib`), with the library cells as kind `gate` (L0 Task 12
   mapping). Not now.
3. **Wide `.names`** (FB-5). Recommend refusing above 16 inputs until a real input needs more;
   then write the cover verbatim and leave `lut_table` empty.
