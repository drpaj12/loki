# Call instructions for the Q-L10 run (controller)

Plan: `EXPERIMENT.md` (this directory). The controller makes the calls; the prepare lane made none. Same machinery as
`experiments/llm-full/CALL-INSTRUCTIONS.md`; only the call files and the collection differ.

## Setup

    . <RUN>/env.sh        # exports ODIN3_*, PYTHONPATH, QL10_OUT=<RUN>, PY (the loki-f3-exp venv python)
    $PY -B experiments/ql10-blocks/q10_synth_ext.py        # only if <RUN>/ext is missing (tier ext netlists)
    $PY -B experiments/ql10-blocks/q10_build.py blocks 2   # Loki blocks of every design (about 12 minutes with 2 jobs)
    $PY -B experiments/ql10-blocks/q10_build.py calls      # prompts, <RUN>/calls/, calls.jsonl, batches*.json

`<RUN>` is `work/ql10-out` of the workspace (absolute path in the controller's checkout). `build calls` is deterministic: the
sha256 of every prompt must equal `calls_table.csv` (column prompt_sha256). The extracted veval-L0 labels for the key are under
`<RUN>/veval/loki-veval-exp/dataset` (from `loki-veval-exp.tar.xz`, F: archive 2026-10-27; `QL10_VEVAL` overrides).

## Per-call prompt template

Paste the block between the rules as the subagent prompt, with `{CALL_FILE}` and `{OUTBOX_FILE}` replaced by the absolute paths
`<RUN>/<call_file>` and `<RUN>/<outbox_file>` of one entry of `batches.json`. Nothing else is added: no design id, block id, arm or
draw. One fresh subagent per call, model `sonnet`, no resumed or reused subagent.

-----
Read the file {CALL_FILE}. It holds a system message and a user message between two delimiter
lines. Follow the system message and carry out the user message. Then use the Write tool to write
your complete answer, exactly as the user message asks it to be formatted, to the file
{OUTBOX_FILE}. Do not read, write or list any other file, and do not use any other tool. When the
file is written, reply with the single word done.
-----

## Order

1. Pilot: `batches-pilot.json` (75 calls, 4 batches, draw 1 of 10 designs). Check the pilot for protocol failures only: how many
   replies lack `module Block_<k>` (the `assembly` outcome), refusals, tool use outside the two files, tokens per call from the meter.
   Run `q10_collect.py` (below); it scores only designs with replies.
2. Full run: `batches.json` (the pilot calls are not in it). Batches are 24 consecutive calls, never spanning a draw; the `group`
   field is `core` (vq and vbig, 3 draws) or `ext` (one draw), `ext` last. Smallest designs first inside a draw, arms interleaved.
3. A call whose D and D+h prompts are byte-equal appears once (`arms` = D and Dh): its one reply serves both arms.

## Per batch

1. Check the weekly meter (`cat ~/.claude/usage-state/latest.json`); stop at 85 percent.
2. Create `<RUN>/outbox` once.
3. For each call of the batch in `batches[i].calls[]` order, spawn the subagent with the template. Calls of a batch are independent
   and may run concurrently. Record in `<RUN>/dispatch-log.tsv`: call number, status, tool-call count, model id the subagent reports.
   Status is `ok` (outbox file written), `api_refused`, `no_file` (declined or chat reply, no file) or `not_run`.
4. Never retry or reword a call (pilot decision 13). A call that did not write its file stays missing.
5. After the batch apply the stop rule (EXPERIMENT.md): stop when `api_refused` plus `no_file` exceeds 12 and exceeds 10 percent of
   the calls made, or at the 85 percent meter.
6. Write the statuses you set as `<RUN>/status.csv` with columns `call,status`.

## After the calls (or after a stop)

    $PY -B experiments/ql10-blocks/q10_collect.py --status <RUN>/status.csv

Writes `<RUN>/results.csv` (one row per design, arm, draw: outcome, pass, blocks replied, blocks with block check `ok`, key
constructs and the ones recovered), `blocks.csv` (one row per block, arm, draw: module found, block check) and prints the outcome
counts; it exits 1 when any `timeout` or `compile-timeout` is present. Arm A comes from `experiments/llm-full/results/results.csv`
(no re-run). Run the transcript tool-use audit as for the full run (Read of the call file and Write of the outbox file only).

## Files

- `batches.json`, `batches-pilot.json`: calls with `call_file` and `outbox_file`, paths relative to `<RUN>`; per batch the token
  estimate (prompt bytes / 3.2 plus the system message, plus 113 + 0.36 x cells output tokens per call).
- `calls_table.csv`: call, design, block, arms, draw, pilot flag, prompt bytes, token estimates, prompt sha256.
- `blocks_summary.csv`, `designs.json`: the blocks of every design (kind, cells, guess, ports, prompt bytes for D and D+h).
- `dryrun_result.json`: the dry run (stub replies, no model).
