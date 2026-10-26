# Loki LLM pilot: Gate-Breaker replica with and without Loki hints

Protocol written 2026-10-26, before any model call. This file is committed and pushed first; its
commit SHA is the protocol-provenance SHA for the results. A later change is a dated entry in
"Amendments" at the end; the old text stays.

Purpose chain (hub `docs/purpose.md`): Loki **L Q1.2** (does an LLM recover RTL from a gate netlist
better when given Loki's structural hints?), related L Q1.1 (recovery without hints) and L Q2.4
(the hint content comes from the round-5 word-first detector). Measure: functional recovery rate,
the fraction of attempts whose generated `TopModule` passes the reference testbench
(`Mismatches: 0 in M samples`, M > 0) in Icarus Verilog. Secondary: Loki-label agreement.

This is a pilot: 40 designs, one attempt per design per arm. It cannot support a claim about
absolute recovery rates. It supports only: does arm B differ from arm A, in which quartiles, and
are Loki's labels right. A difference under about 5 problems per arm is within single-draw noise.

## Frozen decisions (Peter 2026-10-26, "yes looks good to all recommendations")

1. Quartiles: the repo quartile files (`quartiles/{low,mid-low,mid-high,high}_quartile.txt`;
   41/36/36/31 = 144 problems). Q1 = low, Q2 = mid-low, Q3 = mid-high, Q4 = high.
2. K = 1 call per design per arm.
3. Arm C (memorisation control: interface line only, no netlist) is included: 40 short calls.
4. Prompt variant `cot` (`scripts/prompt_variants/cot/verilog-example-prefix_netlist-to-rtl_2-shot.txt`,
   md5 c1200cbb04126bcf47268fc484f18e56, 6862 bytes) for all arms.
5. Arm B keeps the two worked examples without hints.
6. `loki re --calib none` (no f3 calibration exists; committed claims use the uncalibrated rule).
7. Model: a fresh Claude subagent per problem per arm, spawned by the controller session (Agent
   tool, model sonnet); the model id is recorded; no `claude -p`, no external gateway, no API key.
   This supersedes section 7 of the brief. This lane (dispatch 1) makes no model call.
8. Arm B hints go through a name-translation step: Loki names (`c9`, `$n15`) are mapped to netlist
   names through ports and flip-flop pin nets; claims that name an unmappable net are dropped and
   counted per problem (`make_hints.py`, `hints_stats.csv`).
9. Citations: VTR 9 (TRETS 2025, doi 10.1145/3734798) and `rose2012vtr` (doi 10.1145/2145694.2145708)
   for runs on the VTR checkout (commit 3c9a4d23b2); Gate-Breaker pages resolved against IEEE
   Xplore before the paper uses them (staged entries in `briefs/citations-staged.md`). This pilot
   runs no VTR; its tools are Loki, Odin III (floor f3 mapping), Icarus Verilog 12.0.

## Sources (read in place, never executed; untrusted)

- `external/Gate-Breaker-verilog-eval`, branch `feature/netlist-to-rtl`, head
  d60f0b10458746e2fefc2a98fa2455b77a32e8be (MIT licence, NVIDIA Research Projects 2023-2024; the
  NVlabs verilog-eval fork). Called VE. Not vendored: the generated prompt files under `run/` are
  git-ignored; this repo keeps the scripts, `selection.csv` and the sha256 manifest.
- Faruque, Jamieson, Patooghy, Badawy, "Gate-Breaker", IPCCC 2025 (bib key `faruque2025gatebreaker`;
  pages unresolved: 363--370 in `joined.bib` against 1--8 in the Gate-Breaker README).
- Liu et al., VerilogEval, ICCAD 2023, doi 10.1109/ICCAD57390.2023.10323812 (`liu2023verilogeval`).

Python that reads VE text or Verilog runs with `python -I`; no VE script is run.

## Design

40 problems, 10 per quartile. Eligible: in the quartile file and `*_prompt.txt` <= 40000 bytes.
Rank by SHA-256 of `yggdrasil-llm-pilot-20261026:<problem>` ascending, take 10 per quartile, list
by netlist line count (`select.py` -> `selection.csv`; it reproduces the brief's table exactly).
A problem whose reference (as `TopModule`) fails the pre-flight is replaced by the next in rank
and logged as an amendment. The cap removed the largest netlists, so big designs are
under-represented (limitation).

## Arms and prompts (`build_prompts.py`)

Task `netlist-to-rtl`, `--examples=2`, no `--rules`, no `--explain` of `scripts/sv-generate`.

- System message: the `netlist-to-rtl` system message (one sentence; `common.SYSTEM_MSG`), no
  leading or trailing newline in the file written.
- User message, arm A: `prefix + "\nQuestion:\n" + prompt.strip() + "\n"`, then
  `rstrip() + "\n" + suffix`, then `"\nAnswer:\n"`. `prefix` is the whole cot prefix file;
  `suffix` asks for `[BEGIN]`...`[DONE]` and only code. Regression pin: for Prob024_hadd the arm A
  user message is 7986 characters with md5 ebc2f2899a6e55a4d8689c1ae3fac87e.
- Arm B: arm A with `prompt.strip() + "\n\n" + hints block + "\n"` in place of
  `prompt.strip() + "\n"`. The block is: a 5-line preface (the network of facts: Loki is a program,
  not a language model; the worked examples carried no hints; net names are the netlist's own;
  how many claims were removed), `[LOKI-HINTS-BEGIN]`, the Loki document, `[LOKI-HINTS-END]`, and
  the designer-prior sentence ("designers write RTL from familiar patterns. If a signal looks like a
  condition, it probably is one; if a register group looks like an FSM, it probably is one."). The
  prior is the only added instruction. The preface differs from brief 6.2 in one place: decision 8
  makes Loki-internal names absent, so the "Names such as c17 and $n18" sentence is replaced.
- Arm C: arm A with the prompt cut after the interface line (everything from "Gate-level netlist:"
  on is removed) and one sentence added: "No netlist is given for this problem. Use the interface
  above and your knowledge of common designs." The two worked examples stay.

Interface lines list port names only (no widths or directions) for the real problems; not "fixed".

## Hints (`make_hints.py`)

Per problem, on scratch copies only (the prompt netlist is never renamed):

1. Cell rename NOT/NAND/NOR to INV/NAND2/NOR2 (the cmos6 names; brief 6.1) at the start of each
   instantiation line. Fail the problem (no hints) if any cell line is left unrenamed.
2. `loki re <netlist.v> --floor f3 --calib none --detectors wordfirst,hard,ff_pattern,mux,arith,
   seqfn,fsm,bus,unit,role,wordgroup` (the f3 directory name is required), using the installed
   Odin III release library as is. No Odin III build, no heavy lock.
3. Translation of `reverse-provenance.json`. Mappable nets: ports of the original netlist and
   nets on flip-flop pins (DFF, DFFSR) of the original netlist; Loki reuses these names unchanged
   (checked: each mappable name must also occur as a wire in the original netlist). A claim
   (element) names the nets in its `ports` and `nets`; a bus names all its bit nets; an FSM names
   its state, control and reset nets. An object that names an unmappable net (an internal Loki net
   `$nN`) is dropped; an object that names no net is kept. Claims with empty `ports` and a `nets`
   map (flip-flop claims) show `nets` as ports: `q` as outputs, the others as inputs. Cell lists
   are never shown (cell names `cN` have no counterpart in the Yosys netlist). Conflict, parent
   and child ids that point at dropped claims are removed (conflicts become "more not listed").
   Coverage figures are recomputed from the kept claims; the "nets driven by uncovered cells" line
   is removed (Loki-internal names).
4. Document: `loki.rp.doc` text of the translated file, section 2 (how to read `design.v`) removed,
   at most 8000 characters; the document names what it omitted when it cuts.
5. Counts per problem to `hints_stats.csv`: claims, buses and FSMs total/kept/dropped, document
   bytes, whether Loki ran.

Known limits (reported in the results): hint precision is uncalibrated at f3; the FSM test
over-generates; roles are almost always `datapath`; no partitions (L2 needs a graph.json);
combinational internals cannot be named, so most claims about gates inside the logic are dropped.

## Calls (this dispatch builds the manifest; the controller makes the calls later)

`build_prompts.py` writes under `run/prompts/<arm>/<problem>/{system.txt,user.txt}` and
`calls.jsonl`, one JSON line per call: `order`, `problem`, `quartile`, `arm`, `system_file`,
`user_file`, `system_sha256`, `user_sha256`, `user_bytes`, `est_tokens` (bytes / 3.2). Order: the
40 problems by netlist line count ascending (ties by name); per problem the A and B calls in the
order given by the parity of the last hex digit of the problem's rank digest (even: A then B), then
arm C. 120 calls.

Blinding rules for each call: the model sees the system message and the user message and nothing
else: no `ref.sv`, no `test.sv`, no problem id, no dataset path, no files, no web, no memory, no
prior turns; one fresh subagent per call; no call sees another's output. The controller passes the
two files verbatim, records the model id the subagent reports, and writes the raw reply text to
`run/responses/<arm>/<problem>.txt` and optional metadata to `<problem>.meta.json` (model id,
tokens, seconds). A blinding probe (a prompt that is not a problem, asking which files the agent
can read and its model name) is run once and logged first. If the subagent type cannot be made
tool-less, that is a deviation to state in the results.

`collect.py` checks the response files against `calls.jsonl` (missing, unexpected, empty), extracts
the RTL as `sv-generate` does (lines between `[BEGIN]` and `[DONE]`, a fenced-block fallback that is
recorded but does not rescue the outcome), records which `// Step 1..4` comments appear
(`steps.csv`) and writes `run/records/<arm>/<problem>/{system.txt,user.txt,response.txt,
sample.sv,extract.json}`.

## Scoring (`score.py`)

As `VE/Makefile.in`: `iverilog -Wall -Winfloop -Wno-timescale -g2012 -s tb -o <bin> sample.sv
<problem>_test.sv <problem>_ref.sv`, then `timeout 30 ./<bin>` (vvp-compiled output is executed
with `vvp`; a 124 exit adds `TIMEOUT`). Icarus Verilog 12.0 (v13 is not supported by VE). The test
and reference files are read from VE in the scoring step only. Outcome codes in order: no-output
(no `[BEGIN]`/`[DONE]`), syntax, compile, runtime (Mismatches > 0 or no Mismatches line), timeout,
pass. The binary and logs go under `run/`, never into VE. A timeout on a reference-passing
problem is a harness fault. Negative controls: one deliberately wrong `TopModule` per quartile,
one syntax error and one no-output reply must not pass. `score.py preflight` checks every
reference as `TopModule`.

## Secondary measure: Loki-label agreement (`summarize.py`, arm B)

Counts, not rates: FSM candidate present against the L0 ground truth `fsm` flag
(`experiments/veval-l0/features.csv`; Prob151 absent), widest bus candidate against `buses_wide`,
share of claims labelled datapath; uptake (exploratory regex: a clocked state register read by its
own case or `?:` logic; a vector of the hinted width); right-for-the-wrong-reason counts.
Agreement is not a recovery measure.

## Reporting

Pass rate per quartile and overall for A, B, C; the paired A/B table (both pass, A only, B only,
neither); outcome-code counts per arm; label agreement counts; hint counts kept/dropped; tokens and
wall time. Paper numbers (Faruque et al. Table III: overall 0.751, Q4 0.534, O3-Mini) are quoted
for orientation only. Not comparable: different model and no sampling control, K = 1 against K =
10, a 40-problem subset with a size cap, the quartile files not the printed Table II bins, the
prompt text of the repo's current branch, no AST or CFG similarity.

Risks carried (brief section 12): data contamination of VerilogEval (hence arm C), hints that hurt
(a negative B minus A is a valid result), single-draw noise, model identity (the controller records
it), Yosys not installed here so netlist-versus-reference equivalence is not re-checked, the
under-representation of big designs. An optional port-renaming sensitivity run (5 problems) is not
part of this protocol unless Peter asks.

## Amendments

(none yet)
