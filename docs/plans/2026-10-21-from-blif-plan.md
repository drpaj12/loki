# Loki III `loki graph from-blif` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `loki graph from-blif X.blif --out D` turns an unlabelled BLIF into one L0 floor
directory (`netlist.blif`, `netlist.v`, `graph.json`, `labels.csv`, `key.json`, `meta.json`) that
L2 and L1 read unchanged.

**Architecture:** Odin III's `read_blif` and `flatten` (through the binding, in `loki/odin.py`)
read the netlist; L0's `extract_netlist` reads it into a `Netlist`; a pure `normalise` turns
`$sop` cells into L0's `$lut` form and zero-input covers into constants; L0's numbering, labels
(with an empty snapshot), graph, writer and equivalence checks run unchanged through a
`write_floor` function split out of L0's `build_floor`.

**Tech Stack:** Python 3.11+, the `odin3` cffi binding (only in `loki/odin.py`), `unittest`,
`ruff`, `mypy --strict`; Odin III `tools/equiv-check/equiv-check`.

**Spec:** `docs/specs/2026-10-21-from-blif-design.md` (sections cited as spec 3, ...; agent
defaults FB-1 to FB-10). It builds on L0: `docs/specs/2026-10-21-l0-dataset-design.md` and
`docs/plans/2026-10-21-l0-dataset-plan.md` (cited as L0 Task n). Executors read all three.

**Order:** these tasks run after L0 Task 11 (the L0 exit). They need L0 Tasks 4, 5, 6, 7 and 10
merged on `main`; they may run in parallel with L0 Tasks 12 and 13 (spec 7).

## Global Constraints

- L0 plan's Global Constraints hold unchanged (Python 3.11+, `ruff`/`mypy --strict` clean with no
  suppressions, `unittest`, deterministic output, `schema` 1, `n<k>` names from one counter,
  original names only in `key.json`, `odin3` imported only in `loki/odin.py`, Odin III never
  edited, no guessed labels).
- No schema change: every output file validates with L0's `validate_*` as they are (spec 5).
- `SOP_MAX_INPUTS = 16` (FB-5). Design id `blif_<stem>` with `[^A-Za-z0-9_]` replaced by `_`
  (FB-8). `lib/vtr.o3lib` is read before every input (FB-3).
- Exit codes of `loki graph from-blif`: 0 ok, 1 `differs` or internal error, 2 usage, 3 input
  unreadable or unsupported (spec 4).
- Odin III passes used: `read_techlib`, `read_blif`, `flatten`, `write_blif --vtr`,
  `write_verilog` (all in v1.0.0, L0 plan's verified list plus `flatten`).
- Branches `feat/fromblif-<task>` from `origin/main`; update with `git merge origin/main`; PR and
  squash merge on green CI; commit and push after each green step.

## Review Focus

1. An OFF-set cover (`.names a b y` with row `11 0`, a NAND): the converted LUT is NAND, and
   both equivalence checks pass (Task 1 `test_sop_offset_cover`, Task 2 fixture
   `fb_offset.blif`).
2. A primary output driven straight by a primary input, and two outputs on one net: L0's writer
   adds its buffers, the files validate, equivalence holds (Task 2 fixture `fb_alias.blif`).
3. Input signal names that already look like `n<k>` (an anonymous netlist from another tool):
   numbering is independent of them, `key.json` maps them, `deanonymise` restores them (Task 2
   fixture `fb_nnames.blif`).
4. `.latch d q re clk 1` and `.latch d q 0` (no control, `$_FF_`): the init and the flip-flop
   survive anonymisation and the equivalence check (Task 1 `test_latch_init_written`, Task 2
   fixture `fb_latch.blif`).
5. An L0-built `netlist.blif` with output buffers fed back: the buffers become `lut` nodes and
   the run is still `ok` (Task 2 `test_l0_roundtrip_with_buffers`).

---

### Task 1: `$sop` normalisation and the writer's latch init (pure)

**Files:**
- Create: `loki/fromblif.py`, `tests/test_fromblif.py`
- Modify: `loki/blifout.py` (`.latch` init, `$_FF_`), `tests/test_blifout.py`,
  `docs/specs/2026-10-21-l0-dataset-design.md` (section 6.2: the latch init rule, FB-9)

**Interfaces:**
- Consumes: `Netlist`, `FinalCell`, `Port` (L0 Task 2); `LUT_ROW_ORDER`, `write_blif`,
  `identity_naming` (L0 Task 4).
- Produces in `loki/fromblif.py`:
  - `SOP_MAX_INPUTS = 16`
  - Errors: raises L0's `loki.extract.Unsupported` (L0 Task 6).
  - `sop_to_lut(width: int, cover: str) -> str`: the `LUT` parameter string (length `2**width`,
    characters `0`/`1`) in the layout `LUT_ROW_ORDER` names, from a `COVER` text (one row
    `pattern value` per line, pattern character `i` is input `A[i]`, `-` free), with Odin III's
    `$sop` meaning (spec 3 step 3). `width > SOP_MAX_INPUTS` raises `Unsupported`.
  - `normalise(nl: Netlist) -> Netlist`: every `FinalCell` with `type == "$sop"` becomes, when
    `WIDTH >= 1`, a cell of `type "$lut"`, `kind "lut"`, params `{"WIDTH": w, "LUT": ...}`, same
    id, ports and name; when `WIDTH == 0`, a `type "$_CONST0_"` or `"$_CONST1_"` cell of
    `kind "const"` with the same output port. Every cell's `spans` becomes `()` (FB-6). Other
    cells are kept.

- [ ] **Step 1: Write the failing tests** in `tests/test_fromblif.py` on hand-built values. A
  helper `minterms(nl, cell_id) -> set[str]` parses `write_blif(nl, identity_naming(nl))` and
  returns the cell's `.names` rows, so the tests hold for either `LUT_ROW_ORDER`:
  - `test_sop_on_set`: `sop_to_lut(2, "11 1")` gives one `1` and three `0`; its cell's minterms
    are `{"11 1"}`.
  - `test_sop_offset_cover`: `sop_to_lut(2, "11 0")` has three `1`s; minterms
    `{"00 1", "01 1", "10 1"}`.
  - `test_sop_dont_care`: `sop_to_lut(3, "1-1 1\n-11 1")` minterms `{"101 1", "111 1", "011 1"}`.
  - `test_sop_no_rows_is_zero`: `sop_to_lut(2, "")` is `"0000"`.
  - `test_sop_mixed_follows_on_rows`: `sop_to_lut(2, "11 1\n00 0")` equals `sop_to_lut(2, "11 1")`.
  - `test_sop_buffer_and_inverter`: width 1, `"1 1"` and `"0 1"`.
  - `test_sop_too_wide`: `sop_to_lut(17, "1" * 17 + " 1")` raises `Unsupported`.
  - `test_normalise_kinds_and_spans`: a `Netlist` with a `$sop` (WIDTH 2), a zero-input `$sop`
    with cover `"1"` and one with cover `""`, a `$_DFF_P_` with spans: after `normalise`, kinds
    `lut`, `const` (`$_CONST1_`), `const` (`$_CONST0_`), `ff`; every `spans == ()`; ids unchanged.
  In `tests/test_blifout.py`: `test_latch_init_written` (`$_DFF_P_` with `INIT` 1 gives
  `.latch d q re clk 1`; `INIT` 0 gives `0`; `INIT` 2 or 3 or missing gives `3`) and
  `test_ff_without_control` (`$_FF_`, `INIT` 0, gives `.latch d q 0`).
- [ ] **Step 2: Run** `python -m unittest tests.test_fromblif tests.test_blifout -v`. Expected:
  FAIL (no module `loki.fromblif`; the latch tests see `3`).
- [ ] **Step 3: Implement** `sop_to_lut` (enumerate the `2**width` patterns, match rows; no
  recursion), `normalise`, and the `blifout` latch rule; edit L0 spec 6.2's `.latch` bullet to
  "`<init>` is the cell's `INIT` when 0 or 1, else 3; `$_FF_` is `.latch <d> <q> <init>`".
- [ ] **Step 4: Run** the tests, the whole `python -m unittest discover -s tests -t . -v`,
  `ruff check .`, `mypy --strict loki tests`. Expected: PASS (L0's tests unchanged).
- [ ] **Step 5: Commit** (`feat/fromblif-normalise`), push, PR, merge on green CI.

### Task 2: Read a BLIF through Odin III and write the floor

**Files:**
- Modify: `loki/odin.py` (add `open_blif`), `loki/extract.py` (kinds for `$sop` and `$_FF_`,
  `Unsupported` for INOUT black-box pins), `loki/build.py` (split `write_floor` out of
  `build_floor`), `loki/fromblif.py` (add `from_blif`, `detect_floor`, `design_id`)
- Create: `tests/test_fromblif_odin.py`, `tests/data/fb_adder.blif`, `tests/data/fb_anon.blif`,
  `tests/data/fb_hier.blif`, `tests/data/fb_latch.blif`, `tests/data/fb_offset.blif`,
  `tests/data/fb_alias.blif`, `tests/data/fb_nnames.blif`, `tests/data/fb_hard.blif`,
  `tests/data/fb_implicit_bb.blif`, `tests/data/fb_wide.blif`

**Interfaces:**
- Consumes: Task 1; L0 `extract_netlist`, `number`, `build_labels`, `build_graph`,
  `check_equiv`, `build_floor`, `FloorResult`, `OdinSkip`, `Snapshot`.
- Produces:
  - `loki/odin.py`: `open_blif(path: Path, techlibs: Sequence[Path], odin3_root: Path) ->
    tuple[Any, list[str]]`: a `Design` after `read_techlib <odin3_root>/lib/vtr.o3lib`, each
    `read_techlib <lib>`, `read_blif <path>`, `flatten` (each through `run_script`, paths quoted
    as L0 does), and the list of script texts run (for `meta.json` `script`); raises `OdinSkip`
    with the first `error:` line on `Odin3Error`.
  - `loki/extract.py`: kind `lut` for `$sop` with `WIDTH >= 1`, `const` for `WIDTH == 0`, `ff`
    for `$_FF_`; `Unsupported("black box '<type>' has pins of unknown direction")` for a cell of
    a black-box type with an INOUT pin.
  - `loki/build.py`: `write_floor(nl: Netlist, snap: Snapshot, *, design: str, floor: str,
    out_dir: Path, script: list[str], odin3_root: Path, root: str, setup_script: str) ->
    FloorResult` (number, labels, graph, the six files, `netlist.v` via a new design that runs
    `setup_script` then `read_blif netlist.blif` and `write_verilog`, the two checks of L0 9);
    `build_floor` calls it.
  - `loki/fromblif.py`: `design_id(path: Path) -> str`; `detect_floor(path: Path, nl: Netlist)
    -> str | None` (spec 4 `--floor auto`; `None` when it cannot tell);
    `from_blif(blif: Path, out: Path, *, design: str | None, floor: str, techlibs:
    Sequence[Path], odin3_root: Path) -> FloorResult` (floor `"auto"` allowed; raises
    `ValueError("cannot tell the floor: give --floor")`).

- [ ] **Step 1: Write the fixtures and the failing tests** (`skipUnless(odin_available() and
  odin3_root() is not None)`). Fixtures: `fb_adder.blif` (4-bit ripple adder, named signals
  `a[0]..b[3]`, `s[0]..s[4]`); `fb_anon.blif` (the same, every signal `x<k>`); `fb_hier.blif` (top
  model instancing a `half` model twice with `.subckt`); `fb_latch.blif` (`.latch d q re clk 1`
  and `.latch e r 0`); `fb_offset.blif` (a NAND as `11 0`); `fb_alias.blif` (an output equal to an
  input, two outputs on one net); `fb_nnames.blif` (signals named `n0`, `n7`, `n3` in a scrambled
  order); `fb_hard.blif` (one `.subckt adder` with the `vtr.o3lib` ports); `fb_implicit_bb.blif`
  (`.subckt mystery a=x y=z`, no model); `fb_wide.blif` (a 17-input `.names`). Tests in
  `tests/test_fromblif_odin.py`:
  - `test_ok_cases`: for `fb_adder`, `fb_anon`, `fb_hier`, `fb_latch`, `fb_offset`, `fb_alias`,
    `fb_nnames` (floor `auto`, which is `f2`) and `fb_hard` (floor `f1-k6`): `status == "ok"`;
    the six files exist under `<out>/blif_<stem>/<floor>/`; `validate_graph`, `validate_key`,
    `validate_meta`, `validate_labels_csv` return `[]`; both `meta.json` equivalence statuses are
    `equivalent`; no input signal name (`a[0]`, `x3`, `half`) occurs in `netlist.blif`,
    `netlist.v`, `graph.json` or `labels.csv`, except the names `fb_nnames` shares with the
    numbering by design (checked through `key.json` instead).
  - `test_labels_without_provenance`: on `fb_adder`, every `lut` row has `construct_type == ""`,
    `role == "unknown"`, `hdl_line == -1`; `pi` rows have role `io` and `bus_name == "a"`
    (from `a[0]`); `meta.json` `unmatched` equals the number of `lut` + `ff` + `hard` nodes.
  - `test_refusals`: `fb_implicit_bb` and `fb_wide` raise `Unsupported`; `fb_hard` with floor
    `auto` raises `ValueError` (`cannot tell the floor`); a missing file raises `OdinSkip`.
  - `test_deterministic`: two runs of `fb_hier` give byte-identical files.
  - `test_l0_roundtrip`: build the comparator micro's `f2` floor with L0's `build_floor`, feed its
    `netlist.blif` to `from_blif` (floor `auto` from the path), and compare the multisets of
    `(kind, fan_in, fan_out, level, lut_width, lut_table, is_seq, is_const, hard_ports)` of the
    two `graph.json` files: equal.
  - `test_l0_roundtrip_with_buffers`: an L0 floor of a micro whose output is an input (L0
    `test_output_aliases_buffered` shape, built from `tests/data/` Verilog) fed back is `ok`, and
    the buffer `.names` appear as `lut` nodes.
- [ ] **Step 2: Run** `python -m unittest tests.test_fromblif_odin -v` with `ODIN3_LIB`,
  `ODIN3_ROOT`, `PYTHONPATH=<odin3>/plugins/python`. Expected: FAIL (`from_blif` undefined).
- [ ] **Step 3: Implement** `open_blif`, the extract kinds, `write_floor` (move code, no behaviour
  change: run L0's `tests.test_build` first and after), `design_id`, `detect_floor`, `from_blif`
  (pipeline of spec 3: open, extract, `normalise`, `write_floor` with
  `Snapshot((), (), top)`, `root=""`).
- [ ] **Step 4: Run** the new tests, the whole suite, ruff, mypy. Expected: PASS; L0's
  `tests.test_build` unchanged and green.
- [ ] **Step 5: Commit** (`feat/fromblif-read`), push, PR, merge on green CI.

### Task 3: CLI `loki graph from-blif`, `loki check` on a floor, docs

**Files:**
- Modify: `loki/cli.py` (subcommand `graph from-blif`; `check` accepts a floor directory),
  `loki/assemble.py` (split `check_floor` out of `check_dataset`), `tests/test_cli.py`,
  `tests/test_check.py`, `README.md`, `CLAUDE.md` (commands), `docs/specs/2026-10-21-l2-analysis-design.md`
  (section 14 item 2: "done: `loki graph from-blif`, spec `docs/specs/2026-10-21-from-blif-design.md`")

**Interfaces:**
- Consumes: `from_blif`, `detect_floor` (Task 2); L0 `check_dataset`, `cli.main`.
- Produces: `check_floor(path: Path) -> list[str]` in `loki/assemble.py` (L0 10 invariants 1 to
  6 for one floor directory; `words.json` validated only when present); `loki check <path>`
  calls `check_floor` when `<path>` holds a `graph.json`, else `check_dataset`. CLI exit codes
  per spec 4; summary line `from-blif: <design>/<floor>: N nodes, E edges, equiv <status>`.

- [ ] **Step 1: Write the failing tests.** `tests/test_cli.py`: `test_from_blif_ok` (skip without
  Odin III): `main(["graph", "from-blif", "tests/data/fb_adder.blif", "--out", tmp])` returns 0,
  stdout has `from-blif: blif_fb_adder/f2:` and `equiv equivalent`; `main(["check",
  tmp + "/blif_fb_adder/f2"])` returns 0. `test_from_blif_exit_codes`: no input path gives 2;
  `fb_hard.blif` without `--floor` gives 2; `fb_implicit_bb.blif` gives 3; an unreadable file
  gives 3. `tests/test_check.py`: `test_check_floor_matches_dataset_check` (on a fake floor from
  `tests.helpers.write_fake_floor`, `check_floor` returns `[]`, and each invariant mutation of
  L0's `test_check_detects_each_invariant` that concerns one floor is reported by `check_floor`
  too).
- [ ] **Step 2: Run** `python -m unittest tests.test_cli tests.test_check -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the subcommand (argparse sub-parser `graph` with `from-blif`;
  `--design`, `--floor` choices `f1-k6 f1-earch f2 f3 auto` default `auto`, `--techlib`
  repeatable, `--odin3-root` default `$ODIN3_ROOT`), `check_floor`, and the docs (README usage
  block, CLAUDE.md command list, L2 spec 14.2 status line).
- [ ] **Step 4: Run** the whole suite, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/fromblif-cli`), push, PR, merge on green CI.

---

## Self-review

- Spec coverage: section 2 choice (Task 2 `open_blif`), section 3 steps 1-2 (Task 2), 3 (Task 1
  `normalise`), 4 (Task 1), 5-7 (Task 2 `write_floor`), section 4 CLI (Task 3), section 5 label
  values (Task 2 `test_labels_without_provenance`), section 6 items 1-5 (Tasks 2, 1, 2, 3, 3),
  section 8 tests (Tasks 1-3), Review Focus 1-5 pinned in Tasks 1 and 2.
- Types: `sop_to_lut`, `normalise`, `SOP_MAX_INPUTS` (Task 1) used in Task 2; `from_blif`,
  `detect_floor`, `design_id`, `write_floor`, `open_blif` (Task 2) used in Task 3; `check_floor`
  (Task 3) only.
- Proportion: signatures, fixtures, test names and assertions; no bodies beyond the cover
  meaning, which the spec fixes.
