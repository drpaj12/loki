# Loki III L0: the ground-truth dataset builder (design)

Status: decisions approved by Peter, 2026-10-21 (items 1 to 7 of section 2, and the floors of
section 3); the rest are agent defaults he may override. This file is for his review.

## 1. Goal

Loki III reverse-engineers structural netlists (BLIF or gate-level Verilog): it guesses data flow
versus control, then adders, multiplexers, register files, counters and FSMs, and rebuilds the
hierarchy. The method is Bayesian hypotheses that climb a hierarchy (L1, later) over graph and
clustering analysis (L2, later). There is no LLM step. L0 is step 0: a **labelled dataset in
which Odin III's provenance is the answer key**. Gate-Breaker (Faruque, Jamieson, Patooghy,
Badawy, IPCCC 2025) asks an LLM to recover RTL from a Yosys + ABC netlist in a six-cell CMOS
library, scored on VerilogEval's 156 problems; it has no per-gate answer key. L0 gives one:
every LUT, flip-flop, hard block and gate carries the HDL file:line it came from, the HDL
construct (`$add`, `$mux`, `$dff`, FSM state register) it implements, its module path, the bus
and bit it drives, and a datapath or control role.

**Done when** (acceptance, section 11): the 68 Odin III micros produce, for floor F2, a dataset
whose labels cover every node, whose anonymised netlist is equivalent to the original, and which
passes `loki check`.

## 2. Decisions

| # | Decision |
|---|---|
| 1 | Benchmarks: VerilogEval's 156 designs (from github.com/NMSU-PEARL/Gate-Breaker, BSD-3, `verilog-eval` submodule) plus Odin III's `tests/micro`; the VTR set after. |
| 2 | Netlist forms: k6 LUT netlists now (`odin3 abc --lut 6`); gate netlists in a Gate-Breaker-style six-cell library (`lib/cmos6.o3lib`) once gate mapping lands (a later task, gated on it). |
| 3 | Labels per gate or LUT: from provenance, the module path, the HDL construct cell type (`$add`, `$mux`, `$dff`, FSM state register, ...) and file:line; from net names before anonymising, the bus name and bit index; datapath or control by a rule table over construct type and what the gate drives (FSM, enable, select). The rule table is section 7. |
| 4 | Anonymise: flatten, rename every net and cell `n0`, `n1`, ..., strip attributes; keep the mapping in a separate key file. |
| 5 | Format: one directory per design: anonymised BLIF (and Verilog), `graph.json` (nodes with features and labels, edges), `labels.csv`, key file; a manifest lists every design. Schemas are section 6. |
| 6 | Runs as a Wyrd III project; the dataset builder is a Loki III step plugin (entry point group `wyrd.steps`); Loki reads provenance through Odin III's Python binding (Loki may import `odin3`; Wyrd may not). |
| 7 | Train and test split by design, fixed seed. |

Licences found while writing this spec (2026-10-21, GitHub API): Gate-Breaker is BSD-3-Clause;
`NMSU-PEARL/verilog-eval` (the fork Gate-Breaker pins at commit
`d60f0b10458746e2fefc2a98fa2455b77a32e8be`) has a `LICENSE` that reads MIT, Copyright NVIDIA
Research Projects 2023-2024 (the upstream `NVlabs/verilog-eval` is MIT too; GitHub reports
NOASSERTION for both because the file has a custom header). Both permit use and
redistribution with the notice. Loki does not vendor the designs: `loki bench fetch` clones the
pinned commit into a cache, and the dataset's `manifest.json` records the commit and licence.
Odin III's micros are MIT (Odin III repo).

## 3. Floors

Reverse engineering starts from different "floors": the same design, built to different netlist
forms, each with its own labels (Peter, 2026-10-21). L0 emits one netlist per design per floor.

| Floor | Directory | Netlist | Flow (after `read_verilog` and the common front, section 4) | Status |
|---|---|---|---|---|
| F1 | `f1-k6`, `f1-earch` | LUT6 + hard blocks | `read_arch` of `k6_frac_N10_frac_chain_mem32K_40nm` or `EArch`; `hardmap; lower; abc --lut 6`. Adders, multipliers and RAMs stay hard cells and are labelled too | now |
| F2 | `f2` | LUT6 only | no `hardmap` (soft arithmetic): `lower; abc --lut 6` | now |
| F3 | `f3` | six-cell gates | `read_techlib lib/cmos6.o3lib; read_verilog ...;` common front; `lower; abc --gates cmos6; dfflibmap cmos6` (library name read from the `.o3lib`; gatemap spec `odin3` `docs/specs/2026-10-21-gatemap-design.md`) | now |

Common front, all floors: `proc; fsm; opt; flatten; opt -full; wreduce` (the `vtr` flow of
`docs/user/flow.md` up to `hardmap`). `read_verilog --nolatches --vtr-compat` as that flow.
F2 reads the architecture only for its cell types (`read_arch` of the k6 file); its output does
not depend on the architecture. F3 reads no architecture: `read_techlib` of `lib/cmos6.o3lib` of the
Odin III checkout. Directory names are fixed by this rule: `f1-` plus
the architecture's lower-case prefix before the first `_` (`k6`, `EArch` becomes `earch`).

Layout, per design directory, the same files per floor:

```
dataset/
  manifest.json
  <design>/
    design.json
    <floor>/
      netlist.blif   netlist.v   graph.json   labels.csv   key.json   meta.json
```

## 4. Pipeline of one (design, floor)

1. **Read and front.** A fresh `odin3.Design`; `odin3.default().load_abc()` once per process;
   `run_script` of `read_arch <xml>` (F1, F2) or `read_techlib <cmos6.o3lib>` (F3), then
   `read_verilog --nolatches --vtr-compat <files>`, then the common front. A script error
   (`Odin3Error`) marks the (design, floor) `skipped` with reason `odin3: <status text>` and the
   first `error:` line of the captured log (`Odin3.capture_log`). Known cause: SystemVerilog
   (VerilogEval's `always_comb`) fails with `ODIN3_ERR_PARSE`, see open question 1.
2. **Snapshot** (`loki.snapshot`). Before `hardmap` and `lower`, record every live word-level
   node of the top module as a `WordCell` (id, type, parameters, ordered source spans, per-port
   net IDs, `fsm` flag) and every instance node of the pre-flatten design as an `InstanceSite`
   (section 5.2). The snapshot is read-only; the design continues.
3. **Map.** F1: `hardmap; lower; abc --lut 6`. F2: `lower; abc --lut 6`. F3 per section 3.
4. **Extract** (`loki.extract`). Read the final top module into a `Netlist` (section 5.1). A
   module with surviving instances of a user module, tristates or inout ports is `skipped`
   (`unsupported: <what>`).
5. **Label** (`loki.labels`): join `Netlist` cells to `WordCell`s by source spans (section 5.3),
   compute roles (section 7), bus and bit from net names (section 5.4).
6. **Anonymise and write** (`loki.anon`, `loki.blifout`, `loki.graph`): number everything, write
   `netlist.blif`, `graph.json`, `labels.csv`, `key.json`.
7. **Verilog.** In the same session: `read_blif netlist.blif` into a new design (with the same
   `read_arch` or `read_techlib` first), then `write_verilog netlist.v`. Names stay `n<k>`.
8. **Verify** (`loki.equiv`, section 9). Result into `meta.json`.

## 5. Provenance facts the labels rest on

Established by probing the v1.0.0 binding on 2026-10-21 (`odin3` commit `00203c56`); plan Task 6
re-checks each as a test, and a changed fact stops the build.

### 5.1 What the binding gives

- `Design.top()`, `Module.nodes()` (live, ID order), `Node.type_name`, `Node.name`,
  `Node.params()`, `Node.ports()` (each `Port(port, name, direction, width, pins)`),
  `Pin.net()`, `Pin.bit`, `Net.name`, `Net.aliases()`, `Net.pins()`, `Net.driver()`,
  `Module.ports()` (`ModulePort(node, wire)`), `Wire.name`.
- `Node.sources()` returns `odin3.Source(file, line, col, end_line, end_col)` items: the HDL
  spans the object comes from, the naming location first (`odin3_prov_visit_sources`). **It is
  the only provenance the ABI exposes**: there is no call for the derivation chain, a record's
  `hier` string or the ancestor cell types (`include/odin3/odin3.h` has `odin3_prov_visit_sources`
  and `odin3_prov_visit_objects` only). `write_json --odin3` prints `hier`, but a cell's key is
  blank-name dependent, so L0 does not use it.
- Attributes set on nodes or nets before `lower` do not survive `lower` or `abc`
  (probed): the label join cannot rely on tags.
- `lower` keeps each word cell's exact span on every gate it makes; `abc --lut 6` gives each
  `$lut` the union of its cone's spans, each once (probed on `bm_DL_4_bit_comparator.v`: the
  `$eq` at `12:6-12:12` gives gates and LUTs with that span; a LUT of the three comparators lists
  all three spans). Spans are line, column, end line, end column.
- After `flatten`, a cell from an instantiated module lists the module-definition span first and
  the **instantiation span** after it (probed: `sub u1` at line 6, `sub u2` at line 7 gave
  `[2:14-2:19, 6:7-6:31]` and `[2:14-2:19, 7:7-7:31]`). Two instances of one module are
  therefore told apart by their full span list, not by the first span.
- **Nested instances list only the innermost instantiation span** (probed by plan Task 6,
  `tests/data/nested.v` and `nested2.v`: `top -> mid m1 -> leaf l1` gave `[leaf def, l1]`, not
  `[leaf def, l1, m1]`; with `m1` and `m2` both instances of `mid`, the cells of `m1.l1` and
  `m2.l1` have identical span lists). The outer instance path is not in the sources. Net aliases
  carry `m1.l1.y[0]` before `lower`, but the final cells do not; no Odin III call gives the chain
  (open question for the controller: record the full instance chain in provenance).
- `lower` names its gates `<output wire>.<gate><n>` (`y1.xor0`), not by the word cell's id.
- `flatten` leaves unused modules (the instantiated module `sub`) in the design: Loki reads only
  the top.
- Net names are mostly empty after `lower` and `abc`; a primary output bit's net keeps an alias
  such as `AeqB[0]`.

### 5.2 Module path

An `InstanceSite(span, name, parent_path)` is recorded for each instance node of each module
before `flatten`, from the module hierarchy under the top (`Node.type_name` is a module name,
`Node.name` the instance name, `Node.sources()[0]` the instantiation span). A cell's module path
is `top/<i1>/<i2>` where `i1`, `i2` are the instance names whose spans appear in the cell's span
list, ordered outermost first, found by walking from the top: an instance site belongs to the
chain when its span is in the list and its parent is the previous element. A cell with no
instance span has path `<top>`. Because nested flattening keeps only the innermost instantiation
span (section 5.1), the path is completed by climbing from the outermost listed site: while the
current module is not the top, the sites that instantiate it (from modules reachable from the top)
are taken; exactly one gives its name, otherwise the unknown prefix is the single element `*`
(`top/*/l1`: no instance is guessed). The algorithm sorts by the chain, not by list position.
The span list used is the cell's own spans plus the spans of all its matches (section 5.3). If the
instance sites found there (from modules reachable from the top) do not form one parent-to-child
chain (a LUT merged across `u1` and `u2`), the path is `top/*`: the instance is not guessed.

### 5.3 The join: final cell to construct cells

`Σ(c)` is the set of spans of a final cell `c` (LUT, flip-flop, gate, hard cell, constant). A
word cell `W` **matches** `c` when `set(W.spans)` is a subset of `Σ(c)` and `W.spans` is not
empty. Matches are ordered by `(len(W.spans) descending, W.id ascending)`. Then:

- `construct_types` = the distinct `W.type` of the matches, in match order, joined with `|`.
- `construct_type` (primary) = the type of the first match whose first span equals `c`'s first
  span, else the first match, else the empty string.
- Matches with identical spans and type (two instances of one module after flatten, or bit-slices
  of one line) cannot be told apart. They count once in `n_construct_cells` and `construct_types`,
  contribute role `unknown` to the cell's role (never a guess), and the cell is flagged
  `ambiguous` (the `Label.ambiguous` field); `matched_ids` still lists all their ids.
- `n_construct_cells` = number of distinct matches (see above); `matched_ids` (in `graph.json` only) lists the
  `W.id`.
- `module_path` per section 5.2 from `c`'s spans and all matches' spans.
- A cell with no match keeps its spans, gets an empty construct and role `unknown`, and is counted
  in `meta.json` `unmatched`. A hard cell (F1) matches the same way; its own `type_name`
  (`adder`, `multiply`, `single_port_ram`, ...) goes in the `kind` and `cell_type` columns.

Limits, stated so no model overreads the answer key: a LUT that merges logic of several
constructs lists all of them (`n_construct_cells > 1`); a LUT is not split. ABC may duplicate or
merge logic, so one word cell may match many LUTs and conversely.

### 5.4 Bus name and bit index

Taken from the top port wire names and from net names and aliases before anonymising: a primary
input bit is `<wire>[<bit>]` from `Module.ports()` and `Pin.bit`; for any other cell the output
net's `name` then `aliases()` are searched in order for the pattern `^(.+)\[(\d+)\]$` (a plain
name `x` gives bus `x`, bit `-1`). No match: bus `""`, bit `-1`. Bus and bit are labels of the
cell's first output pin.

## 6. Schemas

All files are UTF-8, `\n` line ends, written deterministically (sorted keys, fixed float
formatting) so two builds of one input are byte-identical. `schema` is the integer 1 in every
JSON file; a reader refuses another value.

### 6.1 Numbering and names (loki.anon)

One counter `k` from 0 shared by all kinds; the assigned name is `n<k>`:
1. every live net of the top module that is connected to at least one pin, in net ID order;
2. every cell that is not a port node, in node ID order (LUT, flip-flop, constant, gate, hard
   cell);
3. every port bit pseudo-cell (`pi`, `po` nodes of the graph), in module port order, then bit
   order (LSB first), inputs and outputs interleaved as declared.

So one name never appears twice. Net names are the signal names in the BLIF; cell names appear
as `.cname` on `.subckt`, `.latch` and `.names` lines. Port signals of the BLIF are net names
(`n<k>` of the net), not the original `A[0]`. The model is named `top`.

### 6.2 `netlist.blif`

Berkeley/VPR BLIF: `.model top`, `.inputs` (PI nets in port order), `.outputs`, then per cell:
- `$lut`: `.names <inputs LSB first> <out>` with a cover that has one row per 1-entry of the
  LUT table (minterms, `1`/`0`/`-` free), a zero-input `.names <out>` plus a `1` row for a
  constant 1, none for a constant 0; then `.cname <name>`.
- constants `$_CONST0_`, `$_CONST1_`: the zero-input `.names` forms.
- flip-flops (`$_DFF_P_`, `$_DFF_N_`, latches `$_DLATCH_P_`, `$_DLATCH_N_`): `.latch <d> <q>
  <re|fe|ah|al> <clock or enable net> 3` then `.cname`.
- hard cells: `.subckt <cell type> <port>[<bit>]=<net> ...` (a width-1
  port without an index), `.param NAME VALUE` lines for parameters that the cell type needs,
  then `.cname`.
- F3 library gates (`BUF INV NAND2 NOR2`, kind `gate`): `.names <inputs in library port order> <out>`
  with the on-set rows of the cell function (read from the `.o3lib` `fn` line by `loki.techlib`; the
  binding exposes no cell function), so `equiv-check` runs in full mode; the `DFF` is kind `ff` and a
  `.latch <d> <q> re <clock> 3`. The Odin III side of the writer check is
  `write_blif --gates-as-names` (plain dialect; `--vtr` refuses library gates), and port names come
  from the same plain header.
- an output bit whose net is also an input or another output bit's net: a buffer
  `.names <net> <po pseudo name>` with row `1 1`, and that name is listed in `.outputs`.

LUT table order (decided in plan Task 4 step 6 against Odin III's own `write_blif`, three micros
equivalent): the `LUT` string reads like a binary number, `A[0]` the least significant input; its last
character is the output for all inputs 0, so character position `p` is the output for table index
`2**W - 1 - p`. The plan's two candidate orders (`index_lsb_first`, `index_msb_first` by string
position) both disagreed with Odin III.

### 6.3 `netlist.v`

Odin III `write_verilog` of the design read back from `netlist.blif`: structural Verilog-2005,
all names `n<k>`; no `// file:line` comments (an imported netlist has none).

### 6.4 `graph.json`

```json
{
  "schema": 1, "design": "micro_bm_DL_4_bit_comparator", "floor": "f2",
  "nodes": [
    {"id": "n17", "kind": "lut",
     "features": {"fan_in": 4, "fan_out": 2, "level": 1, "lut_width": 4,
                  "lut_table": "9009", "is_seq": 0, "is_const": 0, "hard_ports": 0},
     "labels": {"construct_type": "$eq", "construct_types": "$eq|$gt", "n_construct_cells": 2,
                "module_path": "top", "bus_name": "AeqB", "bit_index": 0,
                "role": "datapath", "hdl_file": "bm_DL_4_bit_comparator.v", "hdl_line": 12,
                "hdl_col": 6, "hdl_end_line": 12, "hdl_end_col": 12, "n_spans": 1}}
  ],
  "edges": [{"src": "n17", "dst": "n40", "net": "n3", "pin": "I0"}]
}
```

- `kind` one of `pi`, `po`, `lut`, `ff`, `const`, `hard` (F3 adds `gate`).
- Node order: by name's numeric part ascending. Edge order: by `(src, dst, pin)` numeric then
  text. One edge per (driver cell, sink pin) pair; `net` is the carrying net's `n<k>`.
- `pin` names: LUT `I0`..`I5` (input position in the cover's order), flip-flop `D`, `CLK`
  (`EN` for latches), PO `I`, hard cell the formal name with index, `a[3]`.
- `labels` hold the `labels.csv` columns except `node_id`, `kind` and `cell_type` (as in the
  example above; `cell_type` is only in the CSV).
- `features` (numbers only): `fan_in` (input pins connected to a driven net), `fan_out` (sink pins on its output
  nets), `level` (longest combinational path from a PI, flip-flop output or constant; flip-flops,
  PIs and constants are 0), `lut_width` (0 if not a LUT), `lut_table` (hex of the table, MSB
  first, `""` if not a LUT), `is_seq`, `is_const`, `hard_ports` (pin count of a hard cell, else 0).
  The `level` computation cuts each combinational loop at the node with the lowest ID inside a
  strongly connected component that no other unlevelled component feeds, and counts the cuts
  in `meta.json` `loops_cut`.
- `labels` are the `labels.csv` columns (6.5) except `node_id`, `kind`.
- PI nodes: `construct_type` `$port_in`, role `io`, bus and bit from the port. PO nodes likewise
  with `$port_out`. Constants: construct from the match if any, role `const`.

### 6.5 `labels.csv`

Header, exactly: `node_id,kind,cell_type,construct_type,construct_types,n_construct_cells,module_path,bus_name,bit_index,role,hdl_file,hdl_line,hdl_col,hdl_end_line,hdl_end_col,n_spans`

- One row per graph node, same order. `cell_type`: the final cell's Odin III type (`$lut`,
  `$_DFF_P_`, `adder`, `$port_in`, ...). Empty strings for missing text, `-1` for missing
  integers. `hdl_*` are the first span; `hdl_file` is the path relative to the design root (the
  common parent of the design's files), `/` separated. `role` in `datapath, control, mixed, io,
  const, unknown`. CSV quoting by Python `csv` module defaults (`QUOTE_MINIMAL`).

### 6.6 `key.json`

```json
{"schema": 1, "design": "...", "floor": "f2", "top": "bm_DL_4_bit_comparator",
 "nets": {"n0": {"odin_id": 12, "names": ["AeqB[0]"]}},
 "cells": {"n9": {"odin_id": 7, "type": "$lut", "name": "", "word_ids": [6]}},
 "ports": [{"anon": "n20", "orig": "A[0]", "dir": "in", "net": "n0"}]}
```
`names` lists the net's `name` then aliases (may be empty). `word_ids` are the matched snapshot
IDs. The key is the only file that holds original names; a dataset consumer that trains a model
must not read it.

### 6.7 `meta.json`

`{"schema":1, "design", "floor", "odin3_version", "abi_version", "script": [..the run_script text..],
"loki_version", "counts": {"nodes", "pi", "po", "lut", "ff", "const", "hard", "gate",
"edges"}, "unmatched": n, "loops_cut": n, "equiv": {"writer": {"status": "...", "tool_exit": n,
"mode": "full|soft-only"}, "anon": {...}}}`. `script` shows the commands with file names reduced
to base names and the architecture reduced to its stem (`f1-*`) or `<arch>` (`f2`), and omitted for
`f3` (it reads no architecture), so f2 files are byte-equal across architectures and f3 files do not
change with one. There is no timing field (it would break byte-identical rebuilds);
`metrics.json` of the step run holds seconds.

### 6.8 `design.json`

`{"schema":1, "design": "<id>", "benchmark": "verilog-eval|micro|vtr", "top": "...|null",
"files": [{"path": "relative", "sha256": "..."}], "source": {"url": "...", "commit": "...",
"license": "MIT"}}`. Design ids: `micro_<file stem>`, `ve_<ProbNNN_name>`, `vtr_<name>`.

### 6.9 `manifest.json`

```json
{"schema": 1, "created_by": "loki <version>", "odin3_version": "...", "split_seed": "loki-l0-2026",
 "split_rule": "sha256(seed + ':' + design) first 8 bytes, big-endian, mod 100 < 80 is train",
 "designs": [{"design": "micro_x", "benchmark": "micro", "split": "train",
              "floors": {"f1-k6": {"status": "ok", "nodes": 123},
                         "f2": {"status": "skipped", "reason": "odin3: ERR_PARSE ..."}}}]}
```
Designs sorted by id; floors sorted by name. Statuses: `ok`, `skipped` (with reason), `fail`
(internal error, with message). Only `ok` floors have a directory.

## 7. The role rule table

Roles are decided on the word-level snapshot (where "what the cell drives" is visible), then
inherited by final cells through the join. Notation: a **sink** is a reader pin `(cell r, port
p)` on a word cell's output net.

**7.1 Control ports** (a sink on one makes the driver control):

| Reader type | Control ports |
|---|---|
| `$mux`, `$pmux`, `$bmux`, `$demux` | `S` |
| `$dffe`, `$adffe`, `$sdffe`, `$sdffce`, `$dlatch` and the other enabled storage cells | `EN` |
| `$adff`, `$adffe`, `$adlatch`, `$dffsr`, `$aldff` | `ARST`, `SET`, `CLR`, `ALOAD` |
| `$sdff`, `$sdffe`, `$sdffce` | `SRST` |
| every storage cell | `CLK` |
| `$mem` and memory port cells | `RD_EN`, `WR_EN`, `RD_CLK`, `WR_CLK` |

Port names are Odin III's; plan Task 3 asserts them against the registry (a test reads each
listed type's `ports()` from a real design and fails on a missing name).

**7.2 Data-forced readers** (every input is data, whatever the reader's own role): `$add $sub
$mul $div $mod $neg $pos $pow $alu $macc $shl $shr $sshl $sshr $shift $shiftx`, the memory data
ports (`WR_DATA`, `RD_DATA`, `RD_ADDR`, `WR_ADDR`), and hard cells.

**7.3 Neutral types** (role is inherited from what they drive): comparators `$eq $ne $eqx $nex
$lt $le $gt $ge`, bitwise `$and $or $xor $xnor $not`, reductions `$reduce_and $reduce_or
$reduce_xor $reduce_xnor $reduce_bool`, `$logic_not $logic_and $logic_or`, muxes `$mux $pmux
$bmux $demux` (their data ports), storage `$dff` family and latches (data port `D`),
constants (`$_CONST0_`, `$_CONST1_`, `$_CONSTX_`). A type found in a snapshot and in no list stops the build for that design with
`fail: unlisted word type <type>`; the list is closed on purpose.

**7.4 Seeds.** A word cell is `control` by seed when it is an **FSM state register**: a storage
cell with `fsm = true` (section 7.6). A sink that is a primary output (`$port_out`) counts as a
data sink.

**7.5 Algorithm** (`loki.rules.assign_roles`): `sinks(W)` = the reader pins on `W`'s output nets.
`kinds(W)` is a set over `{control, data}`, empty at start. Repeat until no set changes: for
each `W`, for each sink `(r, p)`: add `control` if `p` is a control port of `r.type`; else add
`data` if `r` is data-forced or a primary output; else (`r` neutral) add every kind in
`kinds(r)`. FSM seeds hold `control` from the start and never lose it. After the fixpoint:
`kinds = {control}` gives `control`; `{data}` gives `datapath`; both gives `mixed`; empty gives
`unknown` (dead logic or a loop with no exit). The loop is monotone over a finite lattice, so it
ends.

A final cell's role combines its matches: all matched roles equal gives that role; `control`
and `datapath` together, or any `mixed`, gives `mixed`; `unknown` matches are ignored unless all
are unknown; no match gives `unknown`. PI and PO nodes get `io`, constants without a match
`const`.

**7.6 FSM flag.** `fsm` is true when the snapshot cell carries the string attribute `odin3_fsm_encoding` (value
e.g. `one-hot`) that Odin III's `fsm` pass leaves on the state register's node and wire (probed in
plan Task 6, `tests/data/fsm2.v`; the older name `fsm_encoding` is only the input attribute).
`snapshot.FSM_CARRIER` records it. `$dlatch` does not occur: the flow reads with `--nolatches`.

## 8. Components and package layout

Python 3.11+, MIT. Runtime dependencies: the `odin3` wheel (imported only inside `loki.odin`,
through `importlib.import_module`, so `mypy --strict` needs no stubs and the rest of the package
runs without it); `numpy` only if a feature needs it (none planned). Tools: `ruff`, `mypy
--strict`, `unittest`.

```
loki/
  pyproject.toml  CLAUDE.md  README.md  LICENSE  .gitignore
  .github/workflows/ci.yml
  loki/
    __init__.py        version
    model.py           Span, WordCell, InstanceSite, Net, FinalCell, Netlist (frozen dataclasses)
    schemas.py         constants (columns, kinds, roles, floors) and validate_* for each file
    rules.py           rule tables and assign_roles (section 7)
    labels.py          match, module_path, bus_bit, build_labels
    anon.py            number(netlist) -> Numbering, build_key
    blifout.py         write_blif(netlist, naming) -> str; deanonymise
    graph.py           build_graph(netlist, labels, numbering) -> dict; features
    odin.py            only importer of odin3: open_design, FLOOR_SCRIPTS, run_floor
    snapshot.py        take_snapshot(design) -> Snapshot
    extract.py         extract_netlist(design) -> Netlist
    equiv.py           check_equiv(a_blif, b_blif, tool) -> EquivResult
    build.py           build_floor(...), entry point python -m loki.build
    step.py            DatasetStep (Wyrd plugin)
    bench.py           micro and VerilogEval discovery, fetch, project generation
    assemble.py        assemble, manifest, split
    cli.py             loki bench | assemble | check
  tests/               unittest; tests/data/ small fixtures
  datasets/l0/         generated Wyrd project (gitignored except wyrd.toml.in)
```

Boundaries: everything except `odin.py`, `snapshot.py`, `extract.py` and `build.py` is pure and
unit-tested with hand-built `Netlist` values; these four are covered by tests that skip
(`unittest.skipUnless(odin_available())`) when `odin3` or `libodin3.so` is missing.

### 8.1 The Wyrd step

Wyrd's `Step` protocol (`wyrd/steps/__init__.py`): attributes `name: str`, `tools: tuple[str,
...]`, `is_vpr: bool`; `command(run, step_dir, settings) -> (argv, env)`; `collect(step_dir) ->
list[Metric]`. `get_step` loads an unknown `use` from the entry-point group `wyrd.steps` and
calls the class with the `StepSpec`. Loki registers
`[project.entry-points."wyrd.steps"] loki-dataset = "loki.step:DatasetStep"`.

`DatasetStep(spec)` reads `spec.args`: `floors` (list of `f1`, `f2`, `f3`; default `["f1","f2"]`),
`odin3_root` (optional path, becomes `ODIN3_ROOT` for `lib/` and `tools/`; default the
`$ODIN3_ROOT` of the environment). `name = "loki-dataset"`, `tools = ()`, `is_vpr = False`.
`command` returns `[sys.executable, "-m", "loki.build", "--design", <name>, "--files",
<files...>, "--top", <top or "">, "--arch-xml", <arch_xml(settings, run.arch)>, "--floors",
<csv>, "--out", <step_dir>/dataset]` and env `{"ODIN3_ROOT": ...}` (`ODIN3_LIB` and
`ODIN3_ABC_LIB` pass through from the environment). `collect` reads `<step_dir>/metrics.json`
(numbers `nodes`, `luts`, `ffs`, `hard`, `unmatched`, `skipped_floors`, `equiv_bad`) like Wyrd's
command steps. The process exit code is 0 if every requested floor is `ok` or `skipped` (a
skipped floor is data, not a failure; Wyrd shows it in `metrics.skipped_floors`) and 1 on an
internal `fail`.

A run of F1 uses the run's architecture. F2 and F3 do not depend on it, so each architecture's
run writes the same files; the assembler takes `f2` and `f3` from the run with the
lexicographically first architecture and `loki check` verifies that the others are byte-equal
(a determinism test).

### 8.2 The Wyrd project

`loki bench init --suite micro|verilog-eval|all --odin3-root DIR --out datasets/l0` writes
`datasets/l0/wyrd.toml` and the design sources under `datasets/l0/designs/` (copied micros;
VerilogEval `*_ref.sv` files from the cache, copied and renamed `<id>.sv`). One `[[design]]` per
design, `[recipe.l0] steps = [{ use = "loki-dataset", floors = ["f1","f2"] }]`, and
`[sweep] recipe = ["l0"]  design = [all]  arch = ["k6_frac_N10_frac_chain_mem32K_40nm",
"EArch"]`. VerilogEval's top is `RefModule` (set `top`). Run: `wyrd run datasets/l0`, then
`loki assemble --project datasets/l0 --out dataset`.

### 8.3 Assembler

`loki assemble` reads `wyrd.db` (`runs` table: `key, design, arch, status, run_dir`, W1 spec
section 4) and, for each run with status `ok`, copies `<run_dir>/*-loki-dataset/dataset/<design>/`
floors into `<out>/`, applying section 8.1's rule for `f2`/`f3`, writes `manifest.json` (6.9) and
the split. `loki check <dataset>` validates every file against section 6 and the invariants of
section 10.

## 9. Verification of every netlist

`loki.equiv.check_equiv(reference_blif, candidate_blif)` runs
`<odin3_root>/tools/equiv-check/equiv-check A B` (exit 0 equivalent, 1 not, 2 error, 4 unproven,
5 hard). Two comparisons per (design, floor), recorded in `meta.json` `equiv`:

1. `writer`: Odin III's own `write_blif --vtr` of the final design (floor F3: `write_blif
   --gates-as-names`, the plain dialect, because `--vtr` refuses library gates) against Loki's BLIF
   written with the original port names (the same writer with the identity naming). Proves Loki's
   writer preserves function.
2. `anon`: the reference BLIF (identity naming) against `deanonymise(netlist.blif, key.json)`,
   which maps the port signals back to the original port-bit names. Proves the anonymisation and
   the key.

`status` is `equivalent`, `differs` (a build `fail`), `unproven`, `error` or
`skipped:blackbox-names` (equiv-check exit 2 on a design with hard cells that it cannot match by
name; both sides come from one writer so this is rare). Designs with hard blocks use
`--match-unnamed`. `differs` and `error` fail the floor (a build `fail`) and the acceptance.
`loki check` reports every status other than `equivalent`, `unproven` and
`skipped:blackbox-names` as an error; those two are listed as warnings in the check output.

## 10. Invariants (`loki check`)

1. Every file validates against its schema (section 6); unknown keys are errors.
2. Node IDs in `graph.json` are unique and equal the `node_id` column of `labels.csv`, row for row.
3. Every edge endpoint is a node; every non-PI node with `fan_in > 0` has that many incoming
   edges.
4. Every BLIF signal and `.cname` name is `n<k>`, `k` unique; no other identifier appears.
5. `key.json` covers every net, cell and port name of the BLIF.
6. Every node has a labels row (label coverage 100%); every non-const node has `hdl_file` and
   `hdl_line` unless its `construct_type` is empty and `role` is `unknown` (counted).
7. Every `meta.json` `equiv` status is `equivalent`, `unproven` or `skipped:blackbox-names`
   (the last two are warnings).
8. `manifest.json` lists exactly the design directories present; the split of each design equals
   the split rule.

## 11. Acceptance test (`tests/test_acceptance_micros.py`, local, skips without odin3)

Over a fixed list of at most 12 micros chosen to cover every construct (2:1 mux, comparator,
adder, shift register, FSM, latch, flip-flop with synchronous reset, multiplier, hierarchy) then
over all 68: floor F2 builds without `fail`; every graph node has a labels row; `loki check`
passes; both equivalence results are `equivalent` (or `unproven` on at most 2 designs, listed);
`construct_type` is non-empty for at least 95% of `lut` and `ff` nodes over the run; a second
build is byte-identical. F1 is built for the same designs: no `differs`.

## 12. Not in L0

The hypothesis search (L1), clustering and graph models (L2), any model training, the VTR set
(task 13, after the micros and VerilogEval work), SystemVerilog
support (an Odin III front end, ADR D11), a Liberty reader, fine-grained per-gate provenance
inside ABC cones, GUI.

## 13. Decisions on the open questions (Peter, 2026-10-21)

1. SystemVerilog designs Odin III 1.0 rejects (`always_comb`, probe `Prob100_fsm3comb`): no
   preprocessor in L0; the manifest records them as `skipped` and the count is the first result of the
   run. Revisit after the SystemVerilog front end.
2. CI installs Odin III from the v1.0.0 GitHub release wheel
   (`https://github.com/drpaj12/odin3/releases/download/v1.0.0/odin3-1.0.0-py3-none-linux_x86_64.whl`;
   the ubuntu-24.04 runner matches its glibc), so the Odin III integration tests run in CI too. Locally,
   the same wheel or `PYTHONPATH=<odin3>/plugins/python` with `ODIN3_LIB`.
3. FSM flag carrier: pinned by a probe test in Task 6; if none exists, roles still work and only FSM
   state registers lose the seed.
4. Hard blocks in F1 are not equivalence-checked: a hard cell's type already says what it is (Peter).
   F1's equivalence check covers the soft logic around the hard cells only (hard cells are cut points
   with matching names); `meta.json` records `equiv: soft-only`. Recovering the original operator from
   hard pieces (adder chain length, a split multiplier's original width) is L1 / `unmap` work, by
   chain following and clustering, not L0.
5. LUT bit order: decided in Task 4 Step 6 against Odin III's own `write_blif`.
6. F2 and F3 are identical across archs: built once (from the first arch in sorted order); `loki check`
   verifies any other copies are byte-equal.
