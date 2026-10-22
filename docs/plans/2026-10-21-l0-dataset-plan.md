# Loki III L0 Dataset Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Loki III L0: a Wyrd III step plugin that turns Verilog designs into labelled, anonymised netlist datasets (one directory per design per floor), with Odin III's provenance as the answer key.

**Architecture:** A pure core (model, rules, labels, anonymiser, BLIF writer, graph builder, assembler) works on a `Netlist` value; four thin modules touch Odin III (`odin.py`, `snapshot.py`, `extract.py`, `build.py`). A `DatasetStep` Wyrd plugin runs `python -m loki.build` per (design, architecture); `loki assemble` merges the finished runs into `dataset/` with a manifest and a design-level split.

**Tech Stack:** Python 3.11+, the `odin3` cffi binding (imported only in `loki/odin.py`), `unittest`, `ruff`, `mypy --strict`, GitHub Actions; Wyrd (a dev dependency, for the step protocol tests only).

**Spec:** `docs/specs/2026-10-21-l0-dataset-design.md` (section numbers below refer to it). Read it first; it fixes schemas, the join, the rule table and the floors.

## Global Constraints

- Python 3.11+, no 3.12-only syntax. Runtime dependencies: the `odin3` wheel only (imported via `importlib.import_module` in `loki/odin.py`); `numpy` only if a feature needs it (none planned).
- `ruff check .` and `mypy --strict loki tests` clean. No `# noqa`, `# type: ignore` or similar suppressions without Peter's approval. Line length 100. Small functions.
- Tests are `unittest` under `tests/`; run with `python -m unittest discover -s tests -t . -v`. Tests that need Odin III use `@unittest.skipUnless(odin_available(), ...)` (helper in `tests/helpers.py`).
- Never commit to `main`; work on `feat/l0-<task>` branches, PR, squash merge on green CI. Commit and push after each green step.
- Output files are deterministic: sorted keys, `\n` line ends, UTF-8, `schema` = 1 (spec 6).
- Original names exist only in `key.json`; no other output file contains an original net, cell or port name (spec 6.1, 6.6).
- Names in outputs are `n<k>` from one shared counter (spec 6.1). Floors: `f1-k6`, `f1-earch`, `f2`, `f3` (spec 3).
- Odin III is used only through `plugins/python/odin3.py` (module `odin3`) and the tools `tools/equiv-check/equiv-check`; never edit the Odin III repo. A missing Odin III API is an open question, not a workaround.
- The roles/labels are an answer key, not a claim: never fill a label by guessing; an unmatched cell stays `unknown` (spec 5.3).
- Verified Odin III API names (v1.0.0, `odin3` commit 00203c56): `Design`, `Design.read_blif`, `Design.run_script`, `Design.top`, `Design.modules`, `Design.copy`, `Odin3.load_abc`, `Odin3.capture_log`, `Odin3.version`, `Odin3.abi_version`, `Module.nodes/nets/wires/ports/name`, `Node.type_name/name/params/ports/pins/sources/attr/id`, `Pin.net/bit`, `Net.name/aliases/pins/driver/id`, `Wire.name`, `Source(file,line,col,end_line,end_col)`, `Odin3Error`. Passes used: `read_arch`, `read_techlib`, `read_verilog --nolatches --vtr-compat`, `proc`, `fsm`, `opt`, `flatten`, `opt -full`, `wreduce`, `hardmap`, `lower`, `abc --lut 6`, `read_blif`, `write_blif --vtr`, `write_verilog`.

## Review Focus

- A design with an unused module or two instances of one module (`sub u1`, `sub u2`): labels of instance 2 must not take instance 1's construct or module path. Pinned in Task 5 (`test_two_instances_not_confused`) and Task 6.
- A primary output driven directly by a primary input, or two output bits on one net: the BLIF stays valid and function-preserving. Pinned in Task 4 (`test_output_aliases_buffered`).
- A constant-only design (VerilogEval `Prob001_zero`: no LUT at all): all files still written, labels cover the PI/PO/const nodes. Pinned in Task 7.
- A design Odin III cannot parse (SystemVerilog): recorded as `skipped` with the reason, build exits 0, assembler lists it, `loki check` passes. Pinned in Tasks 7 and 10.
- A module path or file name containing spaces, commas or quotes: CSV and JSON still round-trip. Pinned in Task 2 (`test_csv_quoting`).
- A design with a combinational loop or a flip-flop feedback loop: `level` terminates and `loops_cut` counts. Pinned in Task 5 (`test_level_with_loop`).
- Rebuilding the same design twice, or on another architecture for `f2`: byte-identical files. Pinned in Tasks 7 and 10.

---

### Task 1: Repository skeleton, CI, CLAUDE.md

**Files:**
- Create: `pyproject.toml`, `CLAUDE.md`, `README.md`, `.gitignore`, `.github/workflows/ci.yml`, `loki/__init__.py`, `tests/__init__.py`, `tests/helpers.py`, `tests/test_packaging.py`, `NOTICE`
- Modify: none (`LICENSE` exists, MIT)

**Interfaces:**
- Produces: `loki.__version__: str` (`"0.1.0"`); `tests.helpers.odin_available() -> bool` (true when `importlib.import_module("odin3")` works and `Odin3()` loads the library); `tests.helpers.odin3_root() -> Path | None` (from `$ODIN3_ROOT`, must contain `tools/equiv-check/equiv-check`).

- [ ] **Step 1: Failing test** `tests/test_packaging.py::PackagingTest.test_version_and_entry_point`: asserts `loki.__version__ == "0.1.0"` and, via `importlib.metadata.entry_points(group="wyrd.steps")`, that no entry point named `loki-dataset` exists yet is NOT asserted; instead assert `tomllib.load(pyproject)["project"]["requires-python"] == ">=3.11"` and that `[project.scripts]` has `loki = "loki.cli:main"`.
- [ ] **Step 2: Run** `python -m unittest tests.test_packaging -v`. Expected: FAIL (no module `loki`).
- [ ] **Step 3: Create the skeleton.** `pyproject.toml` modelled on Wyrd's (`/home/jamiespa/odin3-ws/wyrd/pyproject.toml`): setuptools, `name = "loki"`, `version = "0.1.0"`, `requires-python = ">=3.11"`, `dependencies = ["odin3"]`, `[project.scripts] loki = "loki.cli:main"`, `[project.entry-points."wyrd.steps"] loki-dataset = "loki.step:DatasetStep"`, ruff (`line-length = 100`, select `E F W I B UP SIM`), `[tool.mypy] strict = true`, `python_version = "3.11"`. `CLAUDE.md` follows Wyrd's (`wyrd/CLAUDE.md`): what Loki is, spec and plan paths, setup (`python3 -m venv .venv && .venv/bin/pip install ruff mypy`; Odin III for local runs via `PYTHONPATH=<odin3>/plugins/python`, `ODIN3_LIB=<odin3>/build/release/libodin3.so`, `ODIN3_ROOT=<odin3>`), the three commands (unittest, ruff, mypy), and the Global Constraints rules above in short form. `.github/workflows/ci.yml` copies Wyrd's (`/home/jamiespa/odin3-ws/wyrd/.github/workflows/ci.yml`) with `pip install ruff mypy` and `mypy --strict loki tests`; the unit step passes because Odin III tests skip. `NOTICE`: one paragraph naming VerilogEval (MIT, NVIDIA Research Projects) and Gate-Breaker (BSD-3-Clause) as sources of benchmark designs that Loki fetches but does not redistribute. `.gitignore`: `.venv/`, `__pycache__/`, `datasets/l0/designs/`, `datasets/l0/runs/`, `datasets/l0/wyrd.db`, `dataset/`, `*.egg-info/`.
- [ ] **Step 4: Run** unittest, `ruff check .`, `mypy --strict loki tests`. Expected: all clean (the entry point module `loki.step` does not exist yet; nothing imports it).
  CI (spec §13.2): the workflow also runs `pip install https://github.com/drpaj12/odin3/releases/download/v1.0.0/odin3-1.0.0-py3-none-linux_x86_64.whl` and sets `ODIN3_ROOT` to a checkout of drpaj12/odin3 at tag `v1.0.0` (for `tools/equiv-check`), so the Odin III integration tests run in CI; VTR-dependent tests still skip there.
- [ ] **Step 5: Commit** on branch `feat/l0-skeleton`, push, open PR, merge on green CI.

### Task 2: Data model and schemas

**Files:**
- Create: `loki/model.py`, `loki/schemas.py`, `tests/test_model.py`, `tests/test_schemas.py`

**Interfaces:**
- Produces in `loki/model.py` (all `@dataclass(frozen=True)`):
  `Span(file: str, line: int, col: int, end_line: int, end_col: int)`;
  `Net(id: int, names: tuple[str, ...])`;
  `Port(name: str, width: int, nets: tuple[int, ...])` (a final cell's or word cell's port, nets LSB first, 0 for an unconnected bit);
  `WordCell(id: int, type: str, name: str, params: dict[str, int | str], spans: tuple[Span, ...], inputs: tuple[Port, ...], outputs: tuple[Port, ...], fsm: bool)`;
  `InstanceSite(span: Span, name: str, module: str, parent_module: str)`;
  `FinalCell(id: int, kind: str, type: str, name: str, params: dict[str, int | str], spans: tuple[Span, ...], inputs: tuple[Port, ...], outputs: tuple[Port, ...])` with `kind` in `schemas.KINDS`;
  `PortBit(name: str, direction: str, net: int)` (`direction` `in` or `out`; `name` like `A[0]`, bits LSB first);
  `Netlist(top: str, nets: dict[int, Net], cells: tuple[FinalCell, ...], port_bits: tuple[PortBit, ...])`;
  `Snapshot(words: tuple[WordCell, ...], instances: tuple[InstanceSite, ...], top: str)`.
- Produces in `loki/schemas.py`: constants `SCHEMA = 1`, `KINDS = ("pi","po","lut","ff","const","hard","gate")`, `ROLES = ("datapath","control","mixed","io","const","unknown")`, `FLOORS = ("f1-k6","f1-earch","f2","f3")`, `LABEL_COLUMNS: tuple[str, ...]` (spec 6.5 header, exactly), `SPLIT_SEED = "loki-l0-2026"`; functions `validate_graph(obj: object) -> list[str]`, `validate_key(obj) -> list[str]`, `validate_meta(obj)`, `validate_design(obj)`, `validate_manifest(obj)`, `validate_labels_csv(text: str) -> list[str]` (each returns a list of error strings, empty if valid); `dump_json(obj: object) -> str` (sorted keys, indent 1, trailing `\n`); `split_of(design: str) -> str` (`"train"` or `"test"` per spec 6.9: first 8 bytes of `sha256(f"{SPLIT_SEED}:{design}")` big-endian, mod 100 < 80).

- [ ] **Step 1: Failing tests.** `test_schemas.py`: `test_label_columns_exact` asserts `",".join(LABEL_COLUMNS)` equals the spec's header string; `test_validate_graph_ok_and_errors` builds the spec 6.4 example, asserts `validate_graph(...) == []`, then asserts an unknown top-level key, a node kind `"foo"`, a role `"bar"`, a duplicate node id and an edge to a missing node each yield a non-empty error list mentioning the offender; `test_csv_quoting` writes a label row with `module_path='top/u 1,"x"'` through the csv writer used by `labels.py` later (here a local `csv` round trip) and asserts `validate_labels_csv` accepts it; `test_split_is_stable` asserts `split_of("micro_a") == split_of("micro_a")`, both values appear over 200 generated names, and the train share is within 70 to 90 percent; `test_dump_json_deterministic`.
- [ ] **Step 2: Run** `python -m unittest tests.test_schemas tests.test_model -v`. Expected: FAIL (modules missing).
- [ ] **Step 3: Implement** the dataclasses and validators. Validators are hand-written (no jsonschema dependency): check types, required keys, closed key sets, enum membership, id uniqueness, edge endpoints. `test_model.py::test_frozen_and_hashable` asserts `Span` is hashable and immutable.
- [ ] **Step 4: Run** the tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l0-model`), PR, merge.

### Task 3: Rule table and roles

**Files:**
- Create: `loki/rules.py`, `tests/test_rules.py`

**Interfaces:**
- Consumes: `WordCell`, `Port` from Task 2.
- Produces: `CONTROL_PORTS: dict[str, frozenset[str]]` (spec 7.1; keys are exact type names, e.g. `"$mux": {"S"}`, `"$dffe": {"EN","CLK"}`); `DATA_FORCED: frozenset[str]` (7.2); `NEUTRAL: frozenset[str]` (7.3); `assign_roles(words: Sequence[WordCell], po_nets: frozenset[int]) -> dict[int, str]` mapping `WordCell.id` to a role in `("datapath","control","mixed","unknown")` by the fixpoint of spec 7.5; `combine_roles(roles: Sequence[str]) -> str` (spec 7.5 last paragraph); class `UnlistedWordType(ValueError)` raised by `assign_roles` for a type in no list (message `unlisted word type <type>`).

- [ ] **Step 1: Failing tests** in `tests/test_rules.py` with hand-built `WordCell`s (no Odin III): `test_mux_select_is_control` (an `$eq` whose Y feeds `$mux` port `S` is `control`); `test_adder_input_is_datapath` (`$and` feeding `$add` port `A` is `datapath`); `test_mixed` (an `$eq` feeding both an `S` and an `$add`); `test_fsm_seed_and_next_state` (a `$dff` with `fsm=True` is `control`, the `$mux` chain on its `D` input is `control`); `test_po_is_data` (an `$and` whose Y net is in `po_nets` is `datapath`); `test_loop_terminates` (`$dff` Q feeds `$not` feeds the same `$dff` D, plus a PO: `datapath`, returns); `test_dead_logic_unknown`; `test_unlisted_type_raises`; `test_combine_roles` over the cases of spec 7.5 (all equal; control+datapath is mixed; unknown ignored unless all unknown; empty list is unknown).
- [ ] **Step 2: Run** `python -m unittest tests.test_rules -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the tables from spec 7 and `assign_roles` as an iterative fixpoint (explicit loop, no recursion): build `readers: dict[net, list[(WordCell, port_name)]]` once, iterate until a full pass changes nothing.
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l0-rules`), PR, merge.
- [ ] **Step 6 (after Task 6 lands): registry check.** Add `tests/test_rules_registry.py::test_control_ports_exist` (skips without Odin III): for each type in `CONTROL_PORTS` that appears in a small elaborated design covering `$mux`, `$dffe`, `$adff`, `$sdff`, `$dlatch` (a fixture in `tests/data/ctrl_ports.v`), every named port is among `Node.ports()` names; and `test_types_in_micros_are_listed` runs the common front on all 68 micros and asserts every word type found is in `NEUTRAL | DATA_FORCED | set(CONTROL_PORTS)`. A failure here means the tables are completed with the missing type and the matching spec 7 entry. Commit.

### Task 4: Anonymiser and BLIF writer

**Files:**
- Create: `loki/anon.py`, `loki/blifout.py`, `tests/test_anon.py`, `tests/test_blifout.py`

**Interfaces:**
- Consumes: `Netlist`, `FinalCell`, `Port`, `PortBit` (Task 2).
- Produces in `anon.py`: `@dataclass(frozen=True) Numbering(net: dict[int, str], cell: dict[int, str], pi: dict[str, str], po: dict[str, str])` (`pi`/`po` map the original port-bit name to its pseudo-cell name); `number(nl: Netlist) -> Numbering` (spec 6.1 order); `build_key(nl: Netlist, num: Numbering, design: str, floor: str, word_ids: dict[int, tuple[int, ...]]) -> dict[str, object]` (spec 6.6).
- Produces in `blifout.py`: `@dataclass(frozen=True) Naming(net: Callable[[int], str], cell: Callable[[FinalCell], str], po_buffer: Callable[[str], str])`; `identity_naming(nl) -> Naming` (original port-bit names on port nets, `w<id>` on other nets, `c<id>` on cells); `anon_naming(num: Numbering, nl) -> Naming`; `write_blif(nl: Netlist, naming: Naming) -> str` (spec 6.2); `deanonymise(blif: str, key: dict[str, object]) -> str` (maps only port signals back to original port-bit names).
- Constant `LUT_ROW_ORDER` in `blifout.py`: how the `LUT` parameter string (e.g. `'1001000000001001'` for `WIDTH` 4) indexes input patterns. Decided in Step 6 below; default `"index_lsb_first"` meaning string position `i` is the output for the pattern where `A[k]` = bit `k` of `i`.

- [ ] **Step 1: Failing tests** on hand-built netlists: `test_numbering_order_and_unique` (nets first by id, then non-port cells by id, then pi/po pseudo-cells; all names unique; `n0` is the lowest net id); `test_key_covers_everything`; `test_blif_lut_cover` (a 2-input AND `$lut` with `LUT="0001"` yields `.names n0 n1 n2` and exactly one row `11 1`); `test_blif_const_and_latch` (`.names` forms; `$_DFF_P_` gives `.latch d q re clk 3`, `$_DFF_N_` gives `fe`); `test_hard_subckt` (`adder` with ports `a`,`b` width 2 gives `.subckt adder a[0]=.. a[1]=.. b[0]=.. ...` and `.cname`); `test_output_aliases_buffered` (a PI that is also a PO, and two PO bits on one net: BLIF has a `.names <net> <po name>` / `1 1` buffer for each extra, `.outputs` lists distinct names); `test_no_original_names_in_anon_blif` (the original port names `A[0]` do not occur in the anonymised text); `test_deanonymise_roundtrip` (`write_blif(identity)` equals `deanonymise(write_blif(anon), key)` after normalising non-port names, compared structurally by parsing both into `(gate, inputs, output)` tuples and renaming internal nets by first-use order).
- [ ] **Step 2: Run** `python -m unittest tests.test_anon tests.test_blifout -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `number`, `build_key`, `write_blif`, `deanonymise`. Cover rows: one minterm row per `1` entry for a `$lut`; width 0 or all-zero tables follow spec 6.2. Output order: model, `.inputs`, `.outputs`, constants, `.names`, `.latch`, `.subckt`, each group sorted by anonymised name numeric part (deterministic).
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l0-anon`), PR, merge.
- [ ] **Step 6 (after Task 6): fix `LUT_ROW_ORDER`.** Add `tests/test_blif_vs_odin.py::test_lut_order_matches_write_blif` (skips without Odin III): read `tests/micro/verilog/micro/bm_DL_4_bit_comparator.v` through the F2 script, extract the `Netlist`, write Loki's BLIF with `identity_naming`, run Odin III `write_blif --vtr` on the same design, and require `equiv-check` exit 0. If it fails, flip `LUT_ROW_ORDER` to `"index_msb_first"` (string position `i` is the pattern where `A[k]` is bit `W-1-k` of `i`) and rerun; the test must pass with exactly one of the two. Record the result in a comment next to the constant and in spec 6.2.

### Task 5: Labels, graph and features

**Files:**
- Create: `loki/labels.py`, `loki/graph.py`, `tests/test_labels.py`, `tests/test_graph.py`

**Interfaces:**
- Consumes: Tasks 2 to 4.
- Produces in `labels.py`: `match_words(cell: FinalCell, words: Sequence[WordCell]) -> list[WordCell]` (spec 5.3: subset rule, ordered by `(-len(spans), id)`); `module_path(spans: Sequence[Span], instances: Sequence[InstanceSite], top: str) -> str` (spec 5.2); `bus_bit(cell: FinalCell, nl: Netlist) -> tuple[str, int]` (spec 5.4); `@dataclass(frozen=True) Label(node_id, kind, cell_type, construct_type, construct_types, n_construct_cells, module_path, bus_name, bit_index, role, hdl_file, hdl_line, hdl_col, hdl_end_line, hdl_end_col, n_spans)`; `build_labels(nl: Netlist, snap: Snapshot, num: Numbering, word_roles: dict[int, str], root: str) -> tuple[list[Label], dict[int, tuple[int, ...]]]` (second value: matched word ids per final cell id, for the key); `labels_to_csv(labels: Sequence[Label]) -> str` (header from `LABEL_COLUMNS`, Python `csv`, `lineterminator="\n"`).
- Produces in `graph.py`: `levels(nl: Netlist) -> tuple[dict[int, int], int]` (level per cell id and `loops_cut`); `build_graph(nl: Netlist, labels: Sequence[Label], num: Numbering, design: str, floor: str) -> tuple[dict[str, object], int]` (the spec 6.4 object and `loops_cut`).

- [ ] **Step 1: Failing tests** with hand-built values: `test_two_instances_not_confused` (two `WordCell` `$add` with spans `[def, inst1]` and `[def, inst2]`; a LUT with spans `[def, inst2]` matches only the second; its module path is `top/u2` given the two `InstanceSite`s); `test_match_order_and_primary` (a LUT whose spans cover a `$eq` (1 span) and a `$mux` (2 spans) gets `construct_types` `"$mux|$eq"`, primary `$mux` only if its first span equals the LUT's first span, else per spec 5.3); `test_no_match_is_unknown` (empty construct, role `unknown`); `test_bus_bit_from_alias` (alias `AeqB[0]` gives `("AeqB", 0)`; plain `x` gives `("x", -1)`; none gives `("", -1)`); `test_hdl_file_relative` (root stripping, `/` separators); `test_labels_cover_every_node` (one `Label` per graph node, same order); `test_level_chain` (PI, LUT, LUT, PO levels 0,1,2); `test_level_with_loop` (two LUTs in a combinational loop: terminates, `loops_cut >= 1`); `test_graph_edges_and_features` (fan_in, fan_out, lut_width, `lut_table` hex, edge `pin` names `I0..`); `test_graph_validates` (`validate_graph` returns `[]`); `test_csv_roundtrip_with_commas`.
- [ ] **Step 2: Run** `python -m unittest tests.test_labels tests.test_graph -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** `module_path`: walk from the top, repeatedly choose the `InstanceSite` whose `parent_module` equals the current module, whose `span` is in the span list and that was not yet used; append its `name`; continue with its `module`. `levels`: Kahn order over combinational edges; on a stall pick the lowest-ID remaining cell, count it, set its level to the max of its resolved inputs, continue. PO node level equals its driver's level + 1.
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l0-labels`), PR, merge.

### Task 6: Odin III adapter, snapshot, extraction (and the provenance probes)

**Files:**
- Create: `loki/odin.py`, `loki/snapshot.py`, `loki/extract.py`, `tests/test_odin_facts.py`, `tests/test_snapshot.py`, `tests/test_extract.py`, `tests/data/two_inst.v`, `tests/data/nested.v`, `tests/data/fsm2.v`, `tests/data/ctrl_ports.v`

**Interfaces:**
- Produces in `odin.py`: `odin_module() -> Any` (`importlib.import_module("odin3")`); `FRONT = "proc; fsm; opt; flatten; opt -full; wreduce"`; `floor_script(floor: str, files: Sequence[Path], arch_xml: Path | None, cmos6_lib: Path | None) -> tuple[str, str]` returning `(front_script, map_script)` (spec 3: `read_arch <xml>; read_verilog --nolatches --vtr-compat <files>; FRONT` and then `hardmap; lower; abc --lut 6` for `f1-*`, `lower; abc --lut 6` for `f2`; `f3` raises `NotImplementedError("f3 needs gate mapping")` until Task 12); `open_front(floor, files, top, arch_xml, cmos6_lib) -> Design` (runs the front script, loads ABC once, raises `OdinSkip(reason)` on `Odin3Error` with the captured first `error:` line); `class OdinSkip(Exception)`.
- Produces in `snapshot.py`: `take_snapshot(design) -> Snapshot` and `take_instances(design) -> tuple[InstanceSite, ...]` (instances must be read **before** `flatten`: `open_front` runs `read_verilog`, calls `take_instances`, then runs `FRONT`, then `take_snapshot`; the function `open_front` returns `(design, instances)`).
- Produces in `extract.py`: `extract_netlist(design, top_name: str) -> Netlist` (final top module only; port bits from `Module.ports()`; cells kinds: `$lut` `lut`, types starting `$_DFF` or `$_DLATCH` `ff`, `$_CONST0_`/`$_CONST1_` `const`, `$port_in` `pi`, `$port_out` `po`, any other hard cell type `hard`; raises `Unsupported(what)` for a surviving instance of a user module, a tristate type or an inout port).

- [ ] **Step 1: Failing probe tests** in `tests/test_odin_facts.py` (all `skipUnless(odin_available())`; each fact is spec 5.1, and each test names its fact): `test_sources_have_columns` (comparator micro: `$eq` word cell has one span with `line == 12` and `col < end_col`); `test_lower_keeps_spans` (every `$_XOR_`/`$_OR_` with `name` starting `$c<id>.` where `<id>` is the `$eq` word cell id has exactly the word cell's span); `test_lut_span_union` (a LUT of the comparator has a span list that is a union of word spans); `test_flatten_instance_spans` (`two_inst.v`: after `FRONT`, the cells from `sub u1` and `sub u2` have span lists `[def, inst1]` and `[def, inst2]` with `inst1 != inst2`); `test_nested_span_order` (`nested.v`: three levels `top -> mid -> leaf`; records the order of the instance spans in a flattened leaf cell and asserts `module_path` of Task 5 returns `top/m1/l1`; if the order is different from outermost first the test still passes because the algorithm walks the chain, and the test prints the order into the failure message of a deliberate `assertIn`); `test_attr_does_not_survive_lower` (set `loki:t` on a word cell, run `lower`, assert gates have no such attr; documents why no tags are used); `test_net_alias_names` (comparator micro after `abc`: some net `aliases()` contains `AeqB[0]`); `test_fsm_carrier` (`fsm2.v`, a two-state machine: finds where the `fsm` pass leaves a marker, one of: `Node.attr("fsm_encoding")`, `Wire` attribute through `Module.wire(name)` and `Wire.attr`; asserts exactly one of those is non-`None` for the state register and records which in `snapshot.FSM_CARRIER`; if none, the test asserts `FSM_CARRIER == "none"` and the spec's open question 3 applies); `test_hardmap_keeps_spans` (F1 on a micro with `+`/`*` such as `bm_base_multiply.v` and a `+`: the resulting `adder`/`multiply` hard cells carry spans equal to a snapshot word cell's, `type_name`s noted); `test_hard_port_names` (prints and asserts `Node.ports()` names of the hard cells so Task 4's `.subckt` formals are right).
- [ ] **Step 2: Run** `ODIN3_ROOT=... ODIN3_LIB=... PYTHONPATH=<odin3>/plugins/python python -m unittest tests.test_odin_facts -v`. Expected: FAIL (modules missing). On a machine without Odin III: SKIP.
- [ ] **Step 3: Implement** `odin.py`, `snapshot.py`, `extract.py`. `take_snapshot`: iterate `design.top().nodes()`, skip `$port_*`; `inputs`/`outputs` from `Node.ports()` by `direction`, nets via `Pin.net()` (id or 0); `fsm` per `FSM_CARRIER`; spans from `Node.sources()` as `Span`. `take_instances`: for every module of the design, each node whose `type_name` equals a module name (`design.module(type_name)` is not `None`); `parent_module` the containing module's name. `extract_netlist`: nets from every `Pin.net()` seen; names `[net.name, *net.aliases()]` without empties; port bits: for each `ModulePort`, the wire name and the pins of the port node, `PortBit(f"{wire}[{bit}]" if width > 1 else wire, direction, net)`.
- [ ] **Step 4: Run** the probes. Expected: PASS, or a failing probe that proves a spec fact wrong: then stop, edit the spec section 5.1 with the observed fact, and report it in the PR before going on.
- [ ] **Step 5: Add** `test_snapshot.py` (comparator micro: three snapshot cells `$eq,$gt,$lt` with the spans of the probe; `ctrl_ports.v` types present) and `test_extract.py` (comparator micro F2: `Netlist` has 3 `po` port bits named `AeqB`, `AgtB`, `AltB`, 8 `pi` bits `A[0]`..`B[3]`, 5 `lut` cells; a design with an instantiated black box raises `Unsupported`). Run, expect PASS.
- [ ] **Step 6: Run** ruff and mypy (`odin_module()` returns `Any`; the rest is typed). Expected: clean.
- [ ] **Step 7: Commit** (`feat/l0-odin`), PR, merge. Then execute Task 3 Step 6 and Task 4 Step 6.

### Task 7: Floor builder (`loki.build`), verification, one floor end to end

**Files:**
- Create: `loki/build.py`, `loki/equiv.py`, `tests/test_equiv.py`, `tests/test_build.py`

**Interfaces:**
- Consumes: Tasks 2 to 6.
- Produces in `equiv.py`: `@dataclass(frozen=True) EquivResult(status: str, tool_exit: int, detail: str)`; `check_equiv(a: str, b: str, odin3_root: Path, match_unnamed: bool) -> EquivResult` (writes both BLIFs to a temp dir, runs `sys.executable <odin3_root>/tools/equiv-check/equiv-check A B [--match-unnamed]` with a 300 s timeout; exit 0 `equivalent`, 1 `differs`, 4 `unproven`, 2 and 5 `error`; the `skipped:blackbox-names` status when exit 2 and the output contains `cannot name black box`).
- Produces in `build.py`: `build_floor(design: str, files: Sequence[Path], top: str | None, floor: str, arch_xml: Path | None, out_dir: Path, odin3_root: Path) -> FloorResult` (`FloorResult(status: str, reason: str, counts: dict[str, int], equiv: dict[str, EquivResult])`); `main(argv: Sequence[str] | None = None) -> int` (CLI of spec 8.1: `--design --files ... --top --arch-xml --floors --out`; writes `metrics.json` into the parent of `--out`; exit 0 when every floor is `ok` or `skipped`, 1 on `fail`).

- [ ] **Step 1: Failing tests.** `test_equiv.py` with a fake `equiv-check` script written to a temp dir (exit codes 0,1,2,4 and the black-box message): statuses map as in the interface. `test_build.py` (skip without Odin III): `test_f2_comparator` builds `bm_DL_4_bit_comparator.v` for `f2` into a temp dir, asserts the six files exist, `validate_graph`/`validate_key`/`validate_meta` return `[]`, `labels.csv` has one row per graph node, `meta.json` `equiv.writer.status` and `equiv.anon.status` are `equivalent`, the graph has 8 `pi`, 3 `po`, 5 `lut` nodes, and no original name (`AeqB`, `A[0]`) appears in `netlist.blif` or `netlist.v` or `graph.json` or `labels.csv`; `test_constant_only_design` (`Prob001_zero`-like `assign zero = 1'b0;` fixture in `tests/data/zero.v`): files written, labels cover pi/po/const nodes; `test_parse_failure_is_skipped` (`tests/data/sv_always_comb.v`): `status == "skipped"`, reason starts with `odin3:`, no floor directory, exit 0 from `main`; `test_deterministic` (build twice into two dirs, compare every file byte for byte); `test_verilog_names` (`netlist.v` contains only `n<k>` identifiers besides keywords and the module name `top`); `test_unmatched_counted`.
- [ ] **Step 2: Run** the tests. Expected: FAIL.
- [ ] **Step 3: Implement** `build_floor` as the pipeline of spec 4 (steps 1 to 8), `equiv.py`, `main`. `netlist.v`: new `Design.read_blif` (with the same techlib/arch script first, via `Design()` + `run_script`) then `run_script("write_verilog <path>")`. `meta.json` fields per spec 6.7 (`odin3_version` from `Odin3.version()`).
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l0-build`), PR, merge.

### Task 8: The Wyrd step plugin

**Files:**
- Create: `loki/step.py`, `tests/test_step.py`

**Interfaces:**
- Consumes: Wyrd's `Step` protocol, `RunSpec`, `StepSpec`, `Metric`, `Settings`, `arch_xml` (module `wyrd.model`, `wyrd.settings`, `wyrd.steps`). Wyrd is a **dev/test-only** dependency (`pip install -e ../wyrd`), imported under `typing.TYPE_CHECKING` where possible; `loki/step.py` imports `wyrd.model.Metric` at runtime (the step is only loaded by Wyrd).
- Produces: `class DatasetStep` with `name = "loki-dataset"`, `tools: tuple[str, ...] = ()`, `is_vpr = False`, `__init__(self, spec: StepSpec)` (reads `floors`, validates each is in `{"f1","f2","f3"}` else `ValueError("step 'loki-dataset': ...")`, default `["f1","f2"]`; `odin3_root` arg), `command(run, step_dir, settings) -> tuple[list[str], dict[str, str]]`, `collect(step_dir) -> list[Metric]`.

- [ ] **Step 1: Failing tests** (`tests/test_step.py`; skip the module with `unittest.SkipTest` when `wyrd` is not importable): `test_command_argv` builds a `RunSpec` (design `Design("d", (Path("/x/a.v"),), "top")`, arch `EArch`, an empty recipe) and `Settings` as Wyrd's tests do (`/home/jamiespa/odin3-ws/wyrd/tests/helpers.py`), asserts `argv[:3] == [sys.executable, "-m", "loki.build"]`, `--floors` equals `f1-earch,f2` (the step expands `f1` to `f1-<short arch>`), `--out` is `<step_dir>/dataset`, env contains `ODIN3_ROOT`; `test_floor_expansion_names` (`k6_frac_N10_frac_chain_mem32K_40nm` gives `f1-k6`; `EArch` gives `f1-earch`); `test_collect_reads_metrics_json` writes `{"nodes": 12, "luts": 5}` and expects two `Metric`; `test_collect_missing_file_empty`; `test_bad_floor_rejected`; `test_entry_point_loads` (when the package is installed: `importlib.metadata.entry_points(group="wyrd.steps")` has `loki-dataset` and `get_step(StepSpec("loki-dataset"))` from Wyrd returns a `DatasetStep`; skip if not installed).
- [ ] **Step 2: Run** `python -m unittest tests.test_step -v`. Expected: FAIL.
- [ ] **Step 3: Implement** per spec 8.1. Short arch name: `arch.split("_")[0].lower()`.
- [ ] **Step 4: Run** tests, ruff, mypy (mypy needs Wyrd importable: `pip install -e ../wyrd`; in CI add `pip install "wyrd @ git+https://github.com/drpaj12/wyrd"` before mypy). Expected: clean.
- [ ] **Step 5: Commit** (`feat/l0-step`), PR, merge.

### Task 9: Benchmarks and project generation

**Files:**
- Create: `loki/bench.py`, `tests/test_bench.py`, `tests/data/ve_sample/` (three tiny `*_ref.sv` files written by the test itself, not committed)

**Interfaces:**
- Produces: `VERILOG_EVAL = {"url": "https://github.com/NMSU-PEARL/verilog-eval", "commit": "d60f0b10458746e2fefc2a98fa2455b77a32e8be", "license": "MIT"}`; `discover_micros(odin3_root: Path) -> list[Path]` (sorted `*.v` of `tests/micro/verilog/micro`); `fetch_verilog_eval(cache: Path) -> list[Path]` (clone with `git clone --filter=blob:none`, `git checkout <commit>`, return the sorted `dataset_spec-to-rtl/*_ref.sv`; fails if the count is not 156); `design_id(path: Path, suite: str) -> str` (`micro_<stem>`, `ve_<Prob...>` with `_ref` stripped); `write_project(suite: str, odin3_root: Path, cache: Path, out: Path) -> Path` (copies sources into `out/designs/<id>/<id>.v|.sv`, writes `out/wyrd.toml` per spec 8.2 with `top = "RefModule"` for VerilogEval, sorted by id, and `design.json` for each design under `out/designs/<id>/design.json` with sha256 per spec 6.8).

- [ ] **Step 1: Failing tests:** `test_design_id`; `test_discover_micros_count` (skips without `ODIN3_ROOT`; expects 68 files); `test_write_project_toml` (micro suite with a temp fake odin3 root holding two `.v` files: output parses with `tomllib`, has two `[[design]]`, a `[recipe.l0]`, a sweep with both architectures and no absolute home paths other than the project's own); `test_design_json_valid` (`validate_design` returns `[]`; sha256 matches); `test_verilog_eval_count_guard` (monkeypatched glob returns 155 files: raises `RuntimeError`); `test_fetch_needs_network_skipped` (real fetch gated on `LOKI_NETWORK=1`; asserts 156 files).
- [ ] **Step 2: Run** tests. Expected: FAIL.
- [ ] **Step 3: Implement.** `wyrd.toml` follows `/home/jamiespa/odin3-ws/wyrd/docs/specs/2026-10-21-w1-runner-design.md` section 3 (design `files` relative to the project).
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS. Then run once with `LOKI_NETWORK=1` and note the count in the PR.
- [ ] **Step 5: Commit** (`feat/l0-bench`), PR, merge.

### Task 10: Assembler, manifest, split, `loki check`, CLI

> Build order (L1 spec section 17, Peter 2026-10-21): after this task, run L1 plan Task 1 (`words.json`, docs/plans/2026-10-21-l1-hypotheses-plan.md) before Task 11, so the L0 acceptance covers `words.json`.

**Files:**
- Create: `loki/assemble.py`, `loki/cli.py`, `tests/test_assemble.py`, `tests/test_check.py`, `tests/test_cli.py`

**Interfaces:**
- Produces in `assemble.py`: `assemble(project: Path, out: Path) -> dict[str, object]` (reads `<project>/wyrd.db` table `runs(key, design, arch, status, run_dir)`; for each `ok` run copies `<run_dir>/*-loki-dataset/dataset/<design>/` into `out` per spec 8.3; returns the manifest); `build_manifest(designs: Mapping[str, DesignEntry]) -> dict[str, object]`; `check_dataset(root: Path) -> list[str]` (spec 10 invariants, returns error strings).
- Produces in `cli.py`: `main(argv: Sequence[str] | None = None) -> int` with subcommands `bench init --suite --odin3-root --out [--cache]`, `assemble --project --out`, `check <dataset>`; exit 0 ok, 1 invariant errors, 2 usage.

- [ ] **Step 1: Failing tests** with a fake `wyrd.db` (created by the test with the W1 columns) and fake floor directories produced by running Task 7's pure parts on a hand-built `Netlist` (a helper `tests/helpers.write_fake_floor(dir, design, floor)` that calls `number`, `build_labels`, `build_graph`, `write_blif`): `test_assemble_copies_ok_runs_only` (a `fail` run is ignored); `test_f2_from_first_arch` (two runs for arches `EArch` and `k6_...`: `f2` comes from `EArch`... lexicographic order, `EArch` < `k6`: assert the chosen source); `test_f2_mismatch_reported` (differing `f2` bytes between the arch runs: `check_dataset` or `assemble` raises `ValueError("f2 differs between architectures")`); `test_manifest_sorted_and_split` (split equals `split_of`); `test_skipped_floor_listed` (a run whose `metrics.json` says skipped appears with `status: skipped` and reason read from `<run_dir>/*-loki-dataset/dataset/<design>/skipped.json`, which `build.py` writes `{"floor": ..., "reason": ...}` per skipped floor: add that write to Task 7's `build_floor` in this task and test it there); `test_check_detects_each_invariant` (one mutation per invariant of spec 10: renamed node id, extra edge endpoint, original name inserted in the BLIF, key missing a net, missing labels row, design directory not in the manifest, wrong split); `test_cli_usage_exit_2`.
- [ ] **Step 2: Run** tests. Expected: FAIL.
- [ ] **Step 3: Implement.** `check_dataset` reuses `schemas.validate_*`; the original-name test compares BLIF identifiers against the regex `^n[0-9]+$` (and the keywords of BLIF).
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l0-assemble`), PR, merge.

### Task 11: Acceptance test on the micros (L0 exit test)

**Files:**
- Create: `tests/test_acceptance_micros.py`, `docs/runbook-l0.md` (how to run: install, `loki bench init`, `wyrd run`, `loki assemble`, `loki check`, with the real outputs pasted in after the first run)
- Modify: `README.md`, `CLAUDE.md` (commands)

**Interfaces:**
- Consumes: everything above; `ODIN3_ROOT` and `ODIN3_LIB`; Wyrd installed (`wyrd` on `PATH`) with `~/.config/wyrd/machine.toml` (`wyrd config init`).

- [ ] **Step 1: Write the test** (`skipUnless(odin_available() and odin3_root() is not None)`): `test_micro_subset_f2` builds the 12 micros named in a constant `SUBSET` (choose by running `grep -l` over `tests/micro/verilog/micro` for: `bm_DL_2_1_mux`, `bm_DL_4_bit_comparator`, `bm_DL_four_bit_adder_continuous_assign`, `bm_DL_4_bit_shift_register`, `bm_DL_Dff_w_synch_reset`, `bm_DL_D_flipflop`, `bm_my_D_latch1`, `bm_base_multiply`, `bm_DL_74381_ALU`, `bm_DL_BCD_adder`, `bm_dag1_mod` (hierarchy), and one FSM-bearing micro found by `grep -l "case.*state\|fsm" ` in that directory) through `build_floor(..., "f2", ...)`; asserts per design `status == "ok"` and both equivalence statuses `equivalent`, and `check_dataset` on the assembled temp dataset returns `[]`. `test_all_micros_f2` runs all 68: no `fail`; at most 2 designs with an `unproven` equivalence (listed in the failure message); every design's labels have one row per graph node; across the run `construct_type != ""` for at least 95 percent of `lut` and `ff` nodes (print the achieved ratio); a second run of three designs is byte-identical. `test_micros_f1_no_differs`: F1 on `k6_frac_N10_frac_chain_mem32K_40nm` (needs `VTR_ROOT`; skip otherwise) for the same subset: statuses in `{equivalent, unproven, skipped:blackbox-names}`, never `differs`.
- [ ] **Step 2: Run** the test. Expected: PASS. If the 95 percent label threshold fails, do not lower it: read which cells are unmatched (`meta.json` `unmatched`, `labels.csv` rows with empty construct), find the cause (likely hard cells or `$_CONST` nodes with merged spans), fix the join in `labels.py` with a failing unit test first, and report the finding.
- [ ] **Step 3: Run the real flow once:** `loki bench init --suite micro --odin3-root $ODIN3_ROOT --out datasets/l0`, `wyrd run datasets/l0`, `loki assemble --project datasets/l0 --out dataset`, `loki check dataset`. Paste the manifest summary (counts per floor and status) into `docs/runbook-l0.md`.
- [ ] **Step 4: Run** ruff, mypy, the full unittest. Expected: clean.
- [ ] **Step 5: Commit** (`feat/l0-acceptance`), PR, merge. This is the L0 exit.

### Task 12: Floor F3, six-cell gates (gated on Odin III gate mapping)

**Gate:** start only when the Odin III PR for `docs/specs/2026-10-21-gatemap-design.md` is merged and `lib/cmos6.o3lib` exists on its `main`. Until then this task is not executed and the dataset has no `f3` directories.

**Files:**
- Modify: `loki/odin.py` (`floor_script` for `f3`), `loki/extract.py` (kind `gate`), `loki/blifout.py` (gate cells), `loki/rules.py` (no change expected), `tests/test_odin_facts.py`, `tests/test_build.py`, `docs/specs/2026-10-21-l0-dataset-design.md` (section 3 F3 row: the final script)
- Create: `tests/test_f3.py`

**Interfaces:**
- Consumes: Odin III scripts `abc --gates <library>` and `dfflibmap <library>` (names per the gate-mapping spec sections 4 and 6; verify they exist with `Odin3.passes()` before coding; a missing name stops the task).
- Produces: `floor_script("f3", ...)` returning the front and map scripts `read_techlib <cmos6.o3lib>; ... ; lower; abc --gates cmos6; dfflibmap cmos6` (library name per the gate-mapping spec; use the name the `.o3lib` declares, read from the file); `FinalCell.kind == "gate"` for `BUF`/`INV`/`NAND2`/`NOR2`, `ff` for `DFF`, `hard` (blackbox) for `DFFSR`, which `dfflibmap` never selects.

- [ ] **Step 1: Failing tests** (`tests/test_f3.py`, skip when `lib/cmos6.o3lib` or the pass `dfflibmap` is absent): `test_f3_comparator` builds the comparator micro for `f3`: only library cells, constants and ports remain; each gate node has a labels row with source spans (gate provenance is per cone, spec G-2 of the gate-mapping spec: `n_construct_cells` may exceed 1); both equivalence statuses `equivalent`; `test_f3_blif_gates_as_names` (gates written as `.names` of their function so `equiv-check` can run; the cover comes from the library cell's truth table read through `Node.params()` / the `.o3lib`, whichever the merged Odin III documents; if neither is reachable from Python, write the covers for the six cells from `lib/cmos6.o3lib` text with a small parser and test it against the file); `test_f3_flip_flops` (a `DFF` becomes `.latch`).
- [ ] **Step 2: Run** `python -m unittest tests.test_f3 -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the script, kind mapping and gate cover writing. Update spec section 3 with the exact script.
- [ ] **Step 4: Run** the acceptance test with `FLOORS` extended to `f3` (micros); no `differs`; `loki check`. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l0-f3`), PR, merge.

### Task 13: VerilogEval run and VTR designs (after Tasks 11 and 12)

**Files:**
- Modify: `loki/bench.py` (add `discover_vtr(vtr_root) -> list[Path]`), `loki/assemble.py` (record a
  failed `f3` run in the manifest like `f1-<arch>` and `f2`; see the backlog note), `docs/runbook-l0.md`
- Create: `tests/test_bench_vtr.py`

**Backlog from Task 12:** `assemble._record_failures` writes fail entries only for `f1-<arch>` and
`f2`; a failed `f3` run leaves no manifest entry (no schema change, no current effect: all F3 runs
are ok or skipped). Add `f3` when the assembler is next touched.

**Interfaces:**
- Produces: `discover_vtr(vtr_root: Path) -> list[Path]` returning the 14 small VTR designs that Odin III's equivalence sweep uses (read their list from `<odin3_root>/tools/vtr-qor` or `docs/` rather than guessing; the function takes the list file as a parameter); suite name `vtr`, design ids `vtr_<name>`, multi-file designs allowed.

- [ ] **Step 1: Failing test** `test_discover_vtr_uses_list` with a fake list file and fake tree. **Step 2:** run, expect FAIL. **Step 3:** implement. **Step 4:** run tests, ruff, mypy, expect PASS.
- [ ] **Step 5: Run the full datasets:** `loki bench init --suite verilog-eval` then `wyrd run`, `loki assemble`, `loki check`; record in `docs/runbook-l0.md` the counts: designs ok, skipped (with the top three reasons). The skip count is the finding for spec open question 1; report it to Peter. Then the same for the VTR suite on `f1-k6`, `f1-earch`, `f2` (smallest first; sweeps only when no other lane holds the heavy lock).
- [ ] **Step 6: Commit** (`feat/l0-vtr`), PR, merge.

---

## Self-review

- Spec coverage: floors (T6, T7, T12), join and roles (T3, T5), schemas (T2), anonymisation and BLIF (T4), Verilog (T7), Wyrd step and project (T8, T9), assembler, manifest, split, invariants (T10), acceptance (T11), benchmarks (T9, T13), CI and repo files (T1). Open questions 1 to 4 of the spec are carried by T13 Step 5, T1 (CI skip policy), T6 Step 3 and T7.
- Type consistency: `Netlist`, `Snapshot`, `Numbering`, `Label`, `FloorResult`, `EquivResult` are defined once (T2, T4, T5, T7) and used with those names later; `open_front` returns `(design, instances)` in T6 and `build_floor` (T7) uses that.
- Proportion: tasks give signatures, test names and assertions; bodies only where an algorithm is not determined (the module-path walk, levels).
