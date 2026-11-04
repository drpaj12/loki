# Call instructions for the Q-L12 lut4 run (controller)

Plan: `EXPERIMENT.md` (this directory). The controller makes the calls; the prepare lane made none. Same machinery as
`experiments/ql12-k4k6/CALL-INSTRUCTIONS.md`; only the endpoint (lut4), the numbering and the run root differ.

## Setup

    . <RUN>/env.sh        # exports ODIN3_*, PYTHONPATH (this checkout), QL12_OUT=<RUN>, QL10_OUT, PY (the loki-f3-exp venv python)
    ODIN3_HEAVY_OK=1 odin3/tools/heavy-run $PY -B experiments/ql12-lut4/l4_census.py     # only if <RUN>/census-ve or <RUN>/census is missing
    ODIN3_HEAVY_OK=1 odin3/tools/heavy-run $PY -B experiments/ql12-lut4/l4_run.py blocks 2    # Loki blocks (2 jobs)
    ODIN3_HEAVY_OK=1 odin3/tools/heavy-run $PY -B experiments/ql12-lut4/l4_calls.py           # prompts, <RUN>/calls/, calls.jsonl, batches, tables

`<RUN>` is `work/ql12l4-out` of the workspace (absolute path in the controller's checkout). `l4_calls.py` is deterministic: the sha256 of every
prompt must equal `calls_table.csv` (column prompt_sha256; it re-hashes all call files and exits 1 on a mismatch), and the two frozen prompt
files in `experiments/ql12-k4k6/` (`block_prompt_lut.txt`, `a_prompt_lut.txt`) must have the sha256 in `EXPERIMENT.md` (also checked). The
netlists are Odin III builds with `abc --lut 4` in `<RUN>/census-ve/O-lut` (VerilogEval) and `<RUN>/census/O-lut` (processor modules).
`results/stubcheck.csv` (committed) lists the 7 problems whose netlist cannot pass the testbench; they have no call.

## Per-call template

Paste the block between the rules as the subagent prompt, with `{CALL_FILE}` and `{OUTBOX_FILE}` replaced by the absolute paths
`<RUN>/<call_file>` and `<RUN>/<outbox_file>` of one call. Nothing else is added: no design id, endpoint, arm, block id or draw. One fresh
subagent per call, model `sonnet`, no resumed or reused subagent.

-----
Read the file {CALL_FILE}. It holds a system message and a user message between two delimiter
lines. Follow the system message and carry out the user message. Then use the Write tool to write
your complete answer, exactly as the user message asks it to be formatted, to the file
{OUTBOX_FILE}. Do not read, write or list any other file, and do not use any other tool. When the
file is written, reply with the single word done.
-----

## Order

1. `experiments/ql12-lut4/run-batches.json`: `[[batch, [call, ...]], ...]`, 23 batches, 529 calls (arm A 121, arm D 408; the reduced run,
   `EXPERIMENT.md`). The call number n maps to `<RUN>/calls/call-NNNN.txt` and `<RUN>/outbox/resp-NNNN.txt` (4 digits); `batches.json` has the
   same batches with the file names and the token estimate per batch. `batches-D.json` is the same calls without arm A.
2. Batches are at most 24 consecutive calls, never spanning a draw; `group` is `core` (three draws) or `ext` (one draw, last). Inside a draw
   designs run smallest first; inside a design arm A comes first, then the blocks of D. The first 5 to 10 batches serve as the pilot: read
   them for protocol failures only (a D reply without `module Block_<k>`, an A reply without `module TopModule`, refusals, tool use outside the
   two files, tokens per call from the meter).
3. Designs over arm A's cap (a prompt body above 40000 B) have no A call (`a_limit.csv`): picorv32_pcpi_div, tinyriscv_div, tinyriscv_csr.
   Prob017_mux2to1v, Prob092_gatesv100 and Prob105_rotate100 (more than 64 blocks) have an A call and no D call.

## Per batch

1. Check the weekly meter (`cat ~/.claude/usage-state/latest.json`); stop at 85 percent.
2. Create `<RUN>/outbox` once.
3. For each call of the batch spawn the subagent with the template. Calls of a batch are independent and may run concurrently. Record in
   `<RUN>/dispatch-log.tsv`: call number, status, tool-call count, model id the subagent reports. Status is `ok` (outbox file written),
   `api_refused`, `no_file` (declined or chat reply, no file) or `not_run`.
4. Never retry or reword a call. A call that did not write its file stays missing.
5. After the batch apply the stop rule (`ql12-k4k6/EXPERIMENT.md`): stop when `api_refused` plus `no_file` exceeds 12 and exceeds 10 percent of the
   calls made, or at the 85 percent meter.
6. Write the statuses as `<RUN>/status.csv` with columns `call,status`.

## After the calls (or after a stop)

    ODIN3_HEAVY_OK=1 odin3/tools/heavy-run $PY -B experiments/ql12-lut4/l4_run.py collect --status <RUN>/status.csv   # results.csv, blocks.csv; exits 1 on a timeout
    ODIN3_HEAVY_OK=1 odin3/tools/heavy-run $PY -B experiments/ql12-lut4/l4_run.py astcfg                               # astcfg_rows.csv (AST and CFG, raw and flat)
    $PY -B experiments/ql12-lut4/l4_analyze.py                                                                          # results/summary.md, tests.csv, side_by_side.csv, provenance.csv

`results.csv` and `blocks.csv` have the columns of Q-L12. Run the transcript tool-use audit as for Q-L12 (Read of the call file and Write of the
outbox file only). Copy `results.csv`, `blocks.csv`, `astcfg_rows.csv`, `status.csv`, the dispatch log and the audit to `results/` of this directory.
`l4_analyze.py` reads the gates rows (Q-L10, full run) and the k6 rows (`ql12-k4k6/results`) for the side-by-side table.

## Files

- `run-batches.json`, `batches.json`, `batches-D.json`: calls per batch (`call_file` and `outbox_file` relative to `<RUN>`; per batch the token estimate).
- `calls_table.csv`: call, design, endpoint (`lut4`), arm, block, draw, group, prompt bytes, token estimates, prompt sha256 (of the text after the
  user-message delimiter). `counts.csv`: calls and tokens by arm; `counts_full.csv`: the same for the full call set and the reduced run.
  `a_limit.csv`: arm A prompt bytes per design and whether A runs.
- `blocks_summary.csv`, `designs.json`: the blocks of every design (kind, cells, ports, prompt bytes).
- `dryrun_result.json`: the dry run (stub replies, no model). `results/stubcheck.csv`: faithful decode of the whole netlist against the testbench.
  `results/netcheck.csv`: LUT / FF / adder counts and maximum LUT inputs of the lut4, k4 and k6 netlists.
