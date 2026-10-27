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
4. (Superseded by decision 12.) Prompt variant `cot` (`scripts/prompt_variants/cot/verilog-example-prefix_netlist-to-rtl_2-shot.txt`,
   md5 c1200cbb04126bcf47268fc484f18e56, 6862 bytes) for all arms.
5. Arm B keeps the two worked examples without hints.
6. `loki re --calib none` (no f3 calibration exists; committed claims use the uncalibrated rule).
7. Model: a fresh Claude subagent per problem per arm, spawned by the controller session (Agent
   tool, model sonnet); the model id is recorded; no `claude -p`, no external gateway, no API key.
   This supersedes section 7 of the brief. This lane (dispatch 1) makes no model call.
8. (Superseded by decision 10 for the drop rule.) Arm B hints go through a name-translation step
   (`make_hints.py`, `netmap.py`, `hints_stats.csv`).
10. (Peter, after phase 1) Arm B passes EVERY claim Loki makes from the flat netlist alone (non-L0
   run: no provenance names, no L0 ground truth as input). Nothing is dropped. Loki-internal nets
   (`$nN`, `cN`) are resolved to an original netlist wire by random-simulation signature (512
   vectors; ports and flip-flop outputs free), a method ported from the reviewer's prototype
   `yield.py` (review of dispatch 1) into `netmap.py`. Nets with no equal wire get neutral helper
   names `w1`, `w2`, ... (not `h`: claim ids are `hN`), numbered by `$nN` integer then sorted `cN`,
   and a "Helper nets" section of the hints block defines each as a function of netlist wires and
   other helper nets from the driving Loki LUT (`w3 = NOT(reset)`). Loki's `rp_min_p` stays at its
   default 0.5 (claims below it are not claims Loki makes; agent default). Claims 792 of 792 named
   (name resolution counts in the fix-1 result). The hints block carries no `$nN`/`cN`/L0/
   provenance string (leak gate, `build_prompts.leak_hits`, 0 hits over all 120 prompts). Arm-B
   prompts may exceed the 40,000 B selection cap: the cap only filtered dataset prompts.
   Signature equality is strong evidence of equivalence, not a proof.
11. (Peter) Blinding deviation accepted: subagents keep the harness system prompt and tools; the
   pilot system message cannot replace it. State it in the results and the paper. All wall-clock
   timeouts are pinned in `score.py` (simulation 30 s, compile 60 s); a valid run has
   `timeout` and `compile-timeout` counts of 0 (report.json timeouts == 0).
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
by netlist line count (`pick_designs.py` -> `selection.csv`; it reproduces the brief's table exactly).
A problem whose reference (as `TopModule`) fails the pre-flight is replaced by the next in rank
and logged as an amendment. The cap removed the largest netlists, so big designs are
under-represented (limitation).

## Arms and prompts (`build_prompts.py`)

Task `netlist-to-rtl`, `--examples=2`, no `--rules`, no `--explain` of `scripts/sv-generate`.

- System message: the `netlist-to-rtl` system message (one sentence; `common.SYSTEM_MSG`), no
  leading or trailing newline in the file written.
- User message, arm A: `prefix + "\nQuestion:\n" + prompt.strip() + "\n"`, then
  `rstrip() + "\n" + suffix`, then `"\nAnswer:\n"`. `prefix` is the whole prefix file of the variant in `common.VARIANT`;
  `suffix` asks for `[BEGIN]`...`[DONE]` and only code. Regression pin: for Prob024_hadd the arm A
  user message was 7986 characters with md5 ebc2f2899a6e55a4d8689c1ae3fac87e under `cot` (superseded by decision 12; the `standard` pin is in the fix-2 section below).
- Arm B: arm A with `prompt.strip() + "\n\n" + hints block + "\n"` in place of
  `prompt.strip() + "\n"`. The block is: a 5-line preface (Loki is a program,
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
3. Naming (decision 10, `netmap.py`). Every net a claim names (elements' `ports` and `nets`, bus
   bits, FSM state/control/reset nets) that is not a declared wire or port of the original
   netlist is a Loki-internal net. It is mapped to an equal-signature original wire (preference:
   ports, then sorted names) or to a helper net `wK` defined in a "Helper nets" section. Nothing
   is dropped. Claims with empty `ports` and a `nets` map (flip-flop claims) show `nets` as
   ports: `q` as outputs, the others as inputs. Cell lists are never shown.
4. Document: `loki.rp.doc` text of the translated file, section 2 (how to read `design.v`) removed,
   never truncated (`MAX_CHARS` is effectively unbounded and `render_hints` raises if the document
   would be cut).
5. Counts per problem to `hints_stats.csv`: claims, claims fully named, buses, FSMs, internal
   names, names resolved to a wire, helper nets, document and block bytes. `--problems` reruns a
   subset and merges into the csv.

Known limits (reported in the results): hint precision is uncalibrated at f3; the FSM test
over-generates; roles are almost always `datapath`; no partitions (L2 needs a graph.json);
claims about combinational internals name wires by signature or via helper nets.

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
(no `[BEGIN]`/`[DONE]`), cheat (the sample names `RefModule`, `stimulus_gen` or `tb`, outside
comments and strings), syntax, compile, compile-timeout (60 s), runtime (Mismatches > 0), timeout,
no-result (not exactly one line matching `^Mismatches: N in M samples$`), pass. `gb_pass` is the
Gate-Breaker-equivalent pass reported beside ours (`gb_classify`, strings copied from
`scripts/sv-iv-analyze` lines 311-368 of the Gate-Breaker VerilogEval clone). Deviation: Gate-Breaker
has the same hole as the one closed here: its scorer does not forbid a sample that instantiates the
hidden `RefModule` (or prints its own "Mismatches: 0" line), so its pass rates can be inflated by such
samples; our `pass` rejects them and `gb_pass` does not. The binary and logs go under `run/`, never into VE. A timeout on a reference-passing
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

- 2026-10-26 (before any model call): `select.py` was named `pick_designs.py` (a `select.py` next to
  the scripts would shadow the standard-library `select` module). Prompts, hints and records live
  under `run/`, which is git-ignored; the repo keeps `selection.csv`, `hints_stats.csv`,
  `prompt_sizes.csv` (sha256 of every user message) and `dryrun_result.json`. Dry run (no model):
  the 40 references as `TopModule` pass 40/40 through `collect.py` and `score.py`; four wrong
  modules (one per quartile) fail with `runtime`, a syntax error gives `syntax`, a reply without
  markers gives `no-output`.
- 2026-10-26 (fix round 1): scorer fixes (cheat gate, anchored single result line, GB-equivalent
  pass, compile timeout), decision 10 naming, decisions 10 and 11 recorded. Hint stats: 792 of 792
  claims named; 641 internal names, 478 resolved to a wire, 185 helper nets (163 unresolved plus 22
  reached through definitions). Arm B totals 711,151 B (est 222,235 tokens at 3.2 B/token), largest
  call Prob055_conditional arm B 62,881 B.

12. (Peter 2026-10-26, "let's do it") Prompt variant `standard` for all arms, replacing `cot`.
   Reason: in call batch 1 (orders 1-10, `cot` variant), 6 of 10 calls were refused by the API
   safeguard `[reasoning_extraction]` (invalid_request; example request id
   req_011CgRYUzbGaQRVj2362dV1s). The refusal was per problem across all arms, even arm C
   (interface only): Prob003_step_one A/B/C and Prob005_notgate A/B/C. Four calls were answered
   (Prob023_vector100r A/B/C order 4-6, Prob013 A order 10); those 4 `cot` answers are discarded.
   `standard` is Gate-Breaker's own variant
   (`scripts/prompt_variants/standard/verilog-example-prefix_netlist-to-rtl_2-shot.txt`, md5
   e5c9110aadcb958b52750e40a8acb9b5, 3030 bytes): same task and examples, no numbered analysis
   steps, no step comments, no request for visible reasoning. It is not a rewording of `cot`.
   The `steps.csv` column loses its meaning (no step comments are asked); it is kept, expect zeros.
   The prefix md5 is verified in `build_prompts.py` (`PREFIX_MD5`) and the regression pin is
   re-pinned (see Result in the brief).
   Pins under `standard`: prefix 3030 bytes md5 e5c9110aadcb958b52750e40a8acb9b5; Prob024_hadd arm A
   user message 4154 characters, md5 3cf721c28b377e4bfe1719d424ec4c01 (old `cot` pin: 7986
   characters, md5 ebc2f2899a6e55a4d8689c1ae3fac87e).
