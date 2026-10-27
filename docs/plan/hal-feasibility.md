# Loki vs HAL/DANA word recovery: feasibility (dispatch 1, 2026-10-26)

Purpose (hub docs/purpose.md): Loki **L Q2.4** (can words, control nets and FSMs be found first) and
L Q1.1. Measure (later steps): word recovery precision, recall and purity against the L0 provenance
ground truth, on the same netlists as Loki's word-first detector. No build was done here.

Sources read: `emsec/hal` shallow clone at master c923080 (2026-10-26, read-only, nothing run),
tag `v4.5.0` (e7fea566b51e), `README.md`, `install_dependencies.sh`, `Dockerfile`, `CMakeLists.txt`,
`cmake/detect_dependencies.cmake`, `plugins/dataflow_analysis/{README.md,CMakeLists.txt,src,python}`,
`plugins/gate_libraries/definitions/example_library.hgl`, `plugins/verilog_parser`; Crossref and
GitHub API for the citations.

## 1. Headless build route

- HAL core and the plugins we need have **no Qt dependency**. `find_package(Qt)` appears only in
  `plugins/{gui,gexf_writer,dot_viewer,logic_evaluator}`. Plugin switches are CMake options
  (`PL_DATAFLOW` default OFF, `PL_VERILOG_PARSER`, `PL_HGL_PARSER`, `PL_PYTHON_SHELL`,
  `PL_GATE_LIBRARIES` default ON). Plan: `cmake -G Ninja -DCMAKE_BUILD_TYPE=Release -DPL_DATAFLOW=ON`
  and leave `BUILD_ALL_PLUGINS=OFF` (the GUI is then not built). Whether other default-ON plugins pull
  in Qt is to be checked at configure time.
- Vendored in `deps/`: igraph 1.0.x, pybind11, spdlog 1.9.2, nlohmann_json, quazip, abc (all
  `USE_VENDORED_*` default ON).
- System deps required by `detect_dependencies.cmake`: RapidJSON (required), Z3 (required,
  `libz3-dev` is installed here), Python3 dev (installed), OpenMP (comes with gcc), Boost headers
  (`boost/spirit/x3` and `boost/fusion` in `src/netlist/boolean_function*.cpp`). Documented apt line
  (`install_dependencies.sh`, Ubuntu 24.04): build-essential cmake pkgconf libboost-all-dev
  qt6-base-dev libpython3-dev ccache ninja-build pybind11-dev rapidjson-dev libspdlog-dev libz3-dev
  z3 libreadline-dev libgraphviz-dev libomp-dev libsuitesparse-dev libsodium-dev ... .
- On this VM (Ubuntu 24.04, 12 cores, 23 GB): installed: cmake, ninja, g++, ccache, libz3-dev,
  libpython3-dev, flex, bison, qt6-base-dev. **Missing: `libboost-dev`, `rapidjson-dev`.** `sudo`
  needs a password, so Peter must run `sudo apt-get install libboost-dev rapidjson-dev` (about
  150 MB), or the lane downloads the two header-only libraries as source tarballs into
  `/tmp/claude-1000/hal-build` and passes `-DBOOST_ROOT` / `-DRapidJSON_DIR` (untested; Boost spirit
  is header-only). Pick the apt route if it can be done once.
- No prebuilt route: no pip wheel, no apt package from Ubuntu, no docker image in the repo (only a
  `Dockerfile` that builds from source; docker is not installed here). Releases are source tags
  (latest `v4.5.0`, 2025-09-23). The shipped Python bindings are the `hal_py` module built in
  the build tree and the `dataflow` plugin module.
- Estimate: build only the core, python bindings and 6 to 7 plugins in Release with `ninja -j8`
  about 10 to 25 min (vendored igraph and Z3-using code dominate), build tree 1 to 3 GB, source
  clone 271 MB. Memory per compile job under 2 GB. Estimates, not measured.
- Pin: tag `v4.5.0`, record the commit (e7fea566b51e) in the paper. Master has moved since.
- Heavy lock for the build: `flock -x /tmp/claude-1000/odin3-heavy.lock`.

## 2. Netlist formats and gate library

- Netlist input: HAL's Verilog parser (`plugins/verilog_parser`) and VHDL parser read **structural
  netlists whose instances are cells of a gate library** (named port connections, `wire`s,
  `assign` for aliasing). `-i file.v --gate-library <name or path>`. The gate library is an `.hgl`
  JSON file (`version: 4`; shipped definitions: NangateOpenCellLibrary, lsi_10k, XILINX_UNISIM and
  SIMPRIM, ice40ultra, example_library) or a Liberty file (`liberty_parser`). BLIF is not read.
- Loki's `netlist.v` is **not** usable: both f2 and f3 write behavioural `assign` expressions and
  `always @(posedge)` blocks, no cell instances. The `netlist.blif` of each floor is the faithful
  source: f2 is `.names` (LUT covers) and `.latch`; f3 is `.names` gates (BUF INV NAND2 NOR2)
  and `.latch` (DFFSR is a black box).
- Floor choice. The brief says "f2 cmos6", but in the L0 spec F2 is the LUT6 floor and **F3 is the
  cmos6 gate floor**. Round 5 uses f2 as the primary floor and reports f3. DANA only uses
  flip-flops and the combinational connectivity between them (the abstraction "contains only
  flip-flops and connections ... through combinational logic", `python_bindings.cpp`), so it does
  not need gate functions. Recommendation: run **f3 (cmos6) as the primary HAL floor**, because it is
  the real gate-level setting DANA was designed for, **and f2 (LUT) as the second**, via the
  generic `LUT1..LUT6` cells in a HAL library, because the round-5 ground truth and Loki numbers
  are on f2. Same words in both: word cells map through the node ids of `words.json`.
- Library description to write (about 80 lines of JSON each, in our repo, no third-party code):
  - `cmos6.hgl`: cells BUF (`c_buffer`), INV (`c_inverter`), NAND2, NOR2 (combinational, boolean
    function in the pin `function` field), DFF (`sequential`, `ff`, `ff_config` with `clocked_on` C,
    `next_state` D, pin types clock/data/state), DFFSR as an `ff` with set and reset pin types
    (needed so the control-signal grouping of DANA sees S and R; the o3lib says "black box", HAL
    allows the full ff_config). Pin names and port order are those of `lib/cmos6.o3lib` (A, B, Y;
    C, D, Q; S, R).
  - `lut6.hgl`: LUT1..LUT6 (`c_lut`, `lut_config` with `INIT` generic, as in `example_library.hgl`),
    `FF` (clock `C`, data `D`, state `Q`). The `INIT` value is passed as an instance parameter; the
    Verilog parser stores it as a `generic` data entry. The `INIT` can be derived from the cover.
  - Constants: GND / VCC cells (`ground` / `power` types) for const nodes.
- Converter (new, about 150 lines of Python, ours): `netlist.blif` -> HAL structural Verilog
  (`CELL u_<node> (.A(n1), .Y(n3))`), keeping Loki node names `nK` as instance names so the HAL gate
  name equals the L0 node id. The L0 `.cname` lines carry the node ids of the cells.

## 3. Running DANA headless and its output

- CLI (plugin README, `plugin_dataflow.cpp`): `hal -i design.v --gate-library cmos6.hgl --dataflow
  --path OUT/ [--sizes 4,8,16] [--bad_group_size N]` (`--volatile-mode --no-log` to avoid project
  files). The CLI writes `groups.txt` and `graph.dot` into `--path`. `--sizes` (expected register
  sizes) and `--bad_group_size` (minimum group size, default 8 in the GUI) are optional; we should
  report both a default run and one with `min_group_size=1`/`2` since our words are small (micro
  designs have 2 to 8 bit registers). Pre-register this setting.
- Python (preferred for scoring): `--python-script s.py` of `python_shell`, or `import hal_py` /
  `hal_plugins.dataflow`: `cfg = dataflow.Configuration(nl).with_gate_types(...)
  .with_control_pin_types(...).with_min_group_size(n)`, `res = dataflow.analyze(cfg)`,
  `res.get_groups()` (id -> set of gates), `res.get_group_control_nets(id, PinType.clock|enable|reset|set)`,
  `get_group_successors / predecessors`. The control-net output answers the control-net half of
  L Q2.4 and the successor graph is a register-to-register dataflow graph. FSMs are not detected by
  DANA (a separate `solve_fsm` plugin exists, not looked at here).
- `groups.txt` rows: `ID:n, Size:k, CLK: {net ids}, EN, R, S` then `Successors`, `Predecessors`, and
  the gate list. The exporter we write (Python, per design) emits `words_hal.json` =
  list of groups, each a list of L0 node ids, plus the control nets.
- Paper: DANA, TCHES 2020 (4), pp. 309-336, doi 10.46586/tches.v2020.i4.309-336. It groups
  flip-flops by shared control signals and by common predecessors/successors, and scores a group
  with a heuristic (preferring expected sizes).

## 4. Steps 2 and 3 with estimates

Pre-registration first: commit `docs/plan/hal-compare-prereg.md` before any HAL run, fixing the
sets (MI 68 at f2/f3; VT 33; BIG 13), the metrics (below), the DANA settings (`min_group_size` in
{default 8, 2}; `--sizes` empty; type consistency default; no GT-derived size hints), and what
counts as a win.

2. Build (once, step 0): HAL v4.5.0 as in section 1. Write `cmos6.hgl`, `lut6.hgl` and the
   BLIF -> Verilog converter; check each against the 68 micro designs: HAL must load every netlist
   (parser errors are reported as a count). Run DANA with `--python-script` over the round-5 set,
   smallest design first (micro, then VT, then BIG by FF count: stereovision3 120 FFs ... stereovision2
   13,926 FFs / 54,829 nodes), one process per design, 900 s timeout like the round-5 arms, 4 parallel
   jobs below 60 % memory. Export `words_hal.json` per design/floor.
3. Scoring: reuse `experiments/round5/r5lib.py` and the round-5 scorer for Loki's word-first
   candidates; add an adapter that turns a HAL group into a candidate (register word, bits =
   L0 node ids). Same GT (`words.json` `$dff` words with `footprint`, counted for width >= 2).
   Metrics: word precision (exact and subset), recall, purity (share of the group's bits in its
   majority GT word), and tiling as in round 5; control-net recovery precision/recall against the
   GT enable/reset nets. Compare to the word-first detector and the per-kind baselines.
4. Paper: a round subsection plus a related-work paragraph citing HAL, DANA (and the HAL TDSC paper
   optionally), the bib entries below into `docs/paper/joined.bib`.

Run time (estimates): the micro and VerilogEval designs are under 1000 gates, HAL start-up
dominates, 1 to 3 s each, so 101 designs x 2 floors x 2 DANA settings about 10 to 20 min wall.
DANA on 13,926 FFs: seconds to a few minutes (the paper reports netlists of 10^5 gates in
minutes). BIG set: about 15 min to 1 h. Parsing time for f3 stereovision2 (about 150k gates) is
the unknown. Scoring and write-up: a few agent-hours. Total agent work: **about 1 to 2 days** (build
and library debugging is the risk), token cost low (runs are CPU, not tokens).

Risks: (a) dependency install needs Peter's sudo; (b) HAL's Verilog parser needs exact port and
parameter syntax, handled by the converter; (c) DANA may drop small groups under its default
`min_group_size` (hence the second setting); (d) round-5 GT words of width 1 are not scored;
(e) HAL needs a clock pin type on the FF to find control nets, hence DFF in the `.hgl`.

## 5. Citations (verified 2026-10-26)

```bibtex
% Checked: 2026-10-26, https://github.com/emsec/hal README section "Academic Context" (gives this @misc and asks that it be preferred); GitHub API: MIT licence, repo created 2019-02-04, latest release v4.5.0 published 2025-09-23; tag v4.5.0 = e7fea566b51e (git ls-remote). Build exact tag/commit for the paper.
@misc{hal,
  author       = {{Embedded Security Group}},
  publisher    = {{Max Planck Institute for Security and Privacy}},
  title        = {{HAL} - The Hardware Analyzer},
  year         = {2019},
  howpublished = {\url{https://github.com/emsec/hal}},
  note         = {MIT licence. Release v4.5.0 (2025-09-23).}
}

% Checked: 2026-10-26, https://doi.org/10.46586/tches.v2020.i4.309-336 (Crossref: IACR TCHES, issued 2020-08-26, pages 309-336; authors Albartus, Hoffmann, Temme, Azriel, Paar) and https://eprint.iacr.org/2020/751 (HTTP 200). Volume 2020, issue 4 are in the DOI string. Same entry as the existing key in loki docs/paper/joined.bib.
@article{albartus2020dana,
  author  = {Albartus, Nils and Hoffmann, Max and Temme, Sebastian and Azriel, Leonid and Paar, Christof},
  title   = {{DANA}: Universal Dataflow Analysis for Gate-Level Netlist Reverse Engineering},
  journal = {IACR Transactions on Cryptographic Hardware and Embedded Systems (TCHES)},
  volume  = {2020},
  number  = {4},
  pages   = {309--336},
  year    = {2020},
  doi     = {10.46586/tches.v2020.i4.309-336}
}

% Checked: 2026-10-26, https://doi.org/10.1109/TDSC.2018.2812183 (Crossref: IEEE TDSC vol 16 no 3, pages 498-510, issued 2019-05-01; nine authors as below) and HAL README (author list; README itself says it prefers the @misc entry). Optional.
@article{fyrbiak2019hal,
  author  = {Marc Fyrbiak and Sebastian Wallat and Pawel Swierczynski and Max Hoffmann and Sebastian Hoppach and Matthias Wilhelm and Tobias Weidlich and Russell Tessier and Christof Paar},
  title   = {{HAL} -- The Missing Piece of the Puzzle for Hardware Reverse Engineering, Trojan Detection and Insertion},
  journal = {IEEE Transactions on Dependable and Secure Computing},
  volume  = {16},
  number  = {3},
  pages   = {498--510},
  year    = {2019},
  doi     = {10.1109/TDSC.2018.2812183}
}
```

Licence: HAL is MIT (`LICENSE`, copyright Ruhr University Bochum and Max Planck Institute for
Security and Privacy). We do not vendor HAL code; the repos carry only our `.hgl` files, the
converter and the scoring adapter, and the README credits HAL and DANA. The benchmark repo
`emsec/hal-benchmarks` is a separate repository and not used.

## Recommendation

**Go**, cost about 1 to 2 agent-days plus one `sudo apt-get install libboost-dev rapidjson-dev` by
Peter (or the header-tarball route). No VTR or Odin III source change is needed. Run the build and
the sweeps under the heavy lock when the Norns and Odin lanes are idle; the runs themselves are light.
