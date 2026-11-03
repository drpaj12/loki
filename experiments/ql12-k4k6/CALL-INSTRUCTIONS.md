# Call instructions for the Q-L12 run (controller)

Plan: `EXPERIMENT.md` (this directory). The controller makes the calls; the prepare lane made none. Same machinery as
`experiments/ql10-blocks/CALL-INSTRUCTIONS.md` and `experiments/llm-full/CALL-INSTRUCTIONS.md`; only the call files, the
endpoints and the collection differ.

## Setup

    . <RUN>/env.sh        # exports ODIN3_*, PYTHONPATH, QL12_OUT=<RUN>, QL10_OUT, PY (the loki-f3-exp venv python)
    $PY -B experiments/ql12-k4k6/q12_synth_ext.py          # only if <RUN>/census is missing (processor modules at k4, k6)
    $PY -B experiments/ql12-k4k6/q12_build.py blocks 2     # Loki blocks of every design, both endpoints (about 10 minutes, 2 jobs)
    $PY -B experiments/ql12-k4k6/q12_build.py calls        # prompts, <RUN>/calls/, calls.jsonl, batches.json, tables

`<RUN>` is `work/ql12-out` of the workspace (absolute path in the controller's checkout). `build calls` is deterministic: the
sha256 of every prompt must equal `calls_table.csv` (column prompt_sha256), and `block_prompt_lut.txt`, `a_prompt_lut.txt` must
have the sha256 in EXPERIMENT.md. The netlists are the l3-census builds (`work/l3-out/build/{O-lut,O-hard}/ve_<problem>`, read
only; `QL12_CENSUS` overrides) and, for the processor modules, `<RUN>/census`. `results/stubcheck.csv` (committed) lists the 7
designs (14 design-endpoint pairs) whose netlist cannot pass the testbench; they have no call.

## Per-call template

Paste the block between the rules as the subagent prompt, with `{CALL_FILE}` and `{OUTBOX_FILE}` replaced by the absolute paths
`<RUN>/<call_file>` and `<RUN>/<outbox_file>` of one entry of `batches.json`. Nothing else is added: no design id, endpoint, arm,
block id or draw. One fresh subagent per call, model `sonnet`, no resumed or reused subagent.

-----
Read the file {CALL_FILE}. It holds a system message and a user message between two delimiter
lines. Follow the system message and carry out the user message. Then use the Write tool to write
your complete answer, exactly as the user message asks it to be formatted, to the file
{OUTBOX_FILE}. Do not read, write or list any other file, and do not use any other tool. When the
file is written, reply with the single word done.
-----

## Order

1. Full run: `batches.json` (147 batches, 3462 calls, both arms and both endpoints). `batches-D.json` is the same calls without
   arm A (135 batches, 3221 calls, same call numbers), for running D first. There is no pilot batch file; the first batches are the
   smallest designs, so the first 5 to 10 batches serve as the pilot: read them for protocol failures only (replies without
   `module Block_<k>` for D or without `module TopModule` for A, refusals, tool use outside the two files, tokens per call from
   the meter) before going on.
2. Batches are 24 consecutive calls, never spanning a draw; the `group` field is `core` (three draws) or `ext` (one draw), `ext`
   last. Inside a draw designs run smallest first (total block prompt bytes); inside a design the arm A call comes first, then the
   blocks of D in order, so both arms and both endpoints advance together. The two endpoints of a design are separate calls.
3. A call whose prompt appears once is one call; there is no shared D/A call.
4. Designs over arm A's cap (a prompt body above 40000 B) have no A call (`a_limit.csv`): the processor modules at k4 and k6 except
   `tinyriscv_clint` at k4.

## Per batch

1. Check the weekly meter (`cat ~/.claude/usage-state/latest.json`); stop at 85 percent.
2. Create `<RUN>/outbox` once.
3. For each call of the batch in `batches[i].calls[]` order, spawn the subagent with the template. Calls of a batch are independent
   and may run concurrently. Record in `<RUN>/dispatch-log.tsv`: call number, status, tool-call count, model id the subagent reports.
   Status is `ok` (outbox file written), `api_refused`, `no_file` (declined or chat reply, no file) or `not_run`.
4. Never retry or reword a call. A call that did not write its file stays missing.
5. After the batch apply the stop rule (EXPERIMENT.md): stop when `api_refused` plus `no_file` exceeds 12 and exceeds 10 percent of
   the calls made, or at the 85 percent meter.
6. Write the statuses you set as `<RUN>/status.csv` with columns `call,status`.

## After the calls (or after a stop)

    $PY -B experiments/ql12-k4k6/q12_collect.py --status <RUN>/status.csv     # results.csv, blocks.csv; exits 1 on a timeout
    $PY -B experiments/ql12-k4k6/q12_astcfg.py                                 # astcfg_rows.csv (AST and CFG, raw and flat; hours for the large designs)
    $PY -B experiments/ql12-k4k6/q12_analyze.py                                # results/summary.md, tests.csv, provenance.csv

`results.csv`: one row per (design, endpoint, arm, draw): outcome, pass, blocks replied, blocks with block check `ok`, key
constructs and the ones with a right block. `blocks.csv`: one row per (block, draw): module found, block check. Run the transcript
tool-use audit as for the full run (Read of the call file and Write of the outbox file only). Copy the outputs to `results/` of the
experiment directory.

## Files

- `batches.json`, `batches-D.json`: calls with `call_file` and `outbox_file`, paths relative to `<RUN>`; per batch the token estimate
  (prompt bytes / 3.2 plus the system message, plus 113 + 0.36 x gate-level cells of the design, shared over blocks by LUT-cell share, per
  call output tokens).
- `calls_table.csv`: call, design, endpoint, arm, block, draw, group, prompt bytes, token estimates, prompt sha256. `counts.csv`: calls and
  tokens per endpoint and arm. `a_limit.csv`: arm A prompt bytes per design and endpoint and whether A runs.
- `blocks_summary.csv`, `designs.json`: the blocks of every design (kind, cells, ports, prompt bytes).
- `dryrun_result.json`: the dry run (stub replies, no model). `results/stubcheck.csv`: faithful decode of the whole netlist against the
  testbench.
