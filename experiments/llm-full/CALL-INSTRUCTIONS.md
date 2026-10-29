# Call instructions for the full run (controller)

Plan: `EXPERIMENT.md` (this directory). The controller makes the calls; the prepare lane made none.

## Per-call prompt template

Paste the block between the rules as the subagent prompt, with `{CALL_FILE}` and `{OUTBOX_FILE}`
replaced by the absolute paths `<RUN>/<call_file>` and `<RUN>/<outbox_file>` of one entry of
`batches.json` (`<RUN>` is the absolute path of `experiments/llm-full/run` in the loki-full
worktree). Nothing else is added: no problem id, arm, draw or path of the dataset. One fresh
subagent per call, model `sonnet`, no resumed or reused subagent.

-----
Read the file {CALL_FILE}. It holds a system message and a user message between two delimiter
lines. Follow the system message and carry out the user message. Then use the Write tool to write
your complete answer, exactly as the user message asks it to be formatted, to the file
{OUTBOX_FILE}. Do not read, write or list any other file, and do not use any other tool. When the
file is written, reply with the single word done.
-----

## Per batch

1. Check the weekly meter (`cat ~/.claude/usage-state/latest.json`); stop at 85 percent.
2. Create the outbox directory once: `<RUN>/outbox`.
3. For each call of the batch in `batches.json` order (`batches[i].calls[]`), spawn the subagent with
   the template. Calls of a batch are independent and may run concurrently (the pilot ran 10 per
   batch). Record in `<RUN>/dispatch-log.tsv`: call number, status, tool-call count, model id the
   subagent reports. Status is `ok` (outbox file written), `api_refused` (API safeguard error, no
   model reply), `no_file` (declined or chat reply, no file) or `not_run`.
4. Never retry or reword a call (pilot decision 13). A call that did not write its file stays
   missing.
5. After the batch apply the stop rule (EXPERIMENT.md): stop when `api_refused` plus `no_file`
   exceeds 12 and exceeds 10 percent of the calls made, or at the 85 percent meter.
6. Write the statuses you set as `<RUN>/status.csv` with columns `call,status` (statuses other than
   `ok` only matter for the report; a call with no reply is `not_run` by default).

## After the calls (or after a stop)

    PY=<python with pytest-free stdlib; the pilot scripts need only iverilog on PATH>
    $PY -I experiments/llm-full/collect_full.py --status <RUN>/status.csv
    $PY -I experiments/llm-full/analyze_full.py --results <RUN>/results.csv --out <RUN>/summary.md

`collect_full.py` copies each outbox file to `responses/<arm>/<draw>/<problem>.txt`, collects and
scores per draw and writes `results.csv`; it exits 1 when any `timeout` or `compile-timeout` is
present (a valid run has 0). Run the transcript tool-use audit as for the pilot (Read of the call file
and Write of the outbox file only) and list any exception.

## Files

- `batches.json`: 54 batches, calls with `call_file` and `outbox_file`, paths relative to `<RUN>`.
- `<RUN>/calls.jsonl`: all 1233 calls (problem, arm, draw, hashes, sizes, call/outbox/reply paths).
- `<RUN>/calls/call-NNNN.txt`: the call files. Rebuild everything with `make_hints_full.py` then
  `build_full.py` (deterministic; `calls.jsonl` hashes must match the committed
  `prompt_sizes_full.csv`).
