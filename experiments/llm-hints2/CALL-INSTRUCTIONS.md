# Call instructions for the hints-v2 run (controller)

Plan: `EXPERIMENT.md` (this directory). The prepare lane made no model call; the controller (or
Sonnet dispatcher subagents acting for it, as in llm-full) makes them.

## Per-call prompt template

Paste the block between the rules as the subagent prompt, with `{CALL_FILE}` and `{OUTBOX_FILE}`
replaced by the absolute paths `<RUN>/<call_file>` and `<RUN>/<outbox_file>` of one entry of
`batches.json` (`<RUN>` is the absolute path of `experiments/llm-hints2/run` in the loki-hints2
worktree). Nothing else is added: no problem id, arm, draw or path of the dataset. One fresh
subagent per call, model `sonnet`, no resumed or reused subagent.

-----
Read the file {CALL_FILE}. It holds a system message and a user message between two delimiter
lines. Follow the system message and carry out the user message. Then use the Write tool to write
your complete answer, exactly as the user message asks it to be formatted, to the file
{OUTBOX_FILE}. Do not read, write or list any other file, and do not use any other tool. When the
file is written, reply with the single word done.
-----

The answer has up to three parts (a `Notes:` section, the module between `[BEGIN]` and `[DONE]`,
and for hint arms a last line `CLAIMS-USED: ...`); the user message asks for them. The subagent
writes them all to the outbox file.

## Dispatch

33 batches of at most 24 calls (11 per draw; the last batch of each draw has 16 calls), 768 calls.
Use Sonnet dispatcher subagents, each running at most 6 consecutive batches (6 dispatchers), as in
the llm-full run. The first dispatcher first runs one blinding probe (not a problem: which tools
and files the subagent can see, its model name) and logs it to
`<RUN>/responses/blinding-probe-hints2.txt`.

## Per batch

1. Check the weekly meter (`cat ~/.claude/usage-state/latest.json`); stop at 85 percent (the
   plan's stop rule; the lane brief's own weekly stop is separate).
2. Create the outbox directory once: `<RUN>/outbox`.
3. For each call of the batch in `batches.json` order (`batches[i].calls[]`), spawn the subagent
   with the template. Calls of a batch are independent and may run concurrently. Record in
   `<RUN>/dispatch-log.tsv`: call number, status, tool-call count, model id the subagent reports.
   Status is `ok` (outbox file written), `api_refused`, `no_file` (declined or chat reply, no
   file) or `not_run`.
4. Never retry or reword a call. A call that did not write its file stays missing.
5. After the batch apply the stop rule (EXPERIMENT.md): stop when `api_refused` plus `no_file`
   exceeds 12 and exceeds 10 percent of the calls made, or at the 85 percent meter.
6. Write the statuses you set as `<RUN>/status.csv` with columns `call,status`.

## After the calls (or after a stop)

    PY=<python 3.11+ with iverilog on PATH; the scripts need only the standard library>
    $PY -I experiments/llm-hints2/collect_hints2.py --status <RUN>/status.csv
    $PY -I experiments/llm-hints2/analyze_hints2.py --results <RUN>/results.csv --out <RUN>/summary.md

`collect_hints2.py` copies each outbox file to `responses/<arm>/<draw>/<problem>.txt`, collects and
scores per draw and writes `results.csv` (with `claims_used` and `used`); it exits 1 when any
`timeout` or `compile-timeout` is present (a valid run has 0). Run the transcript tool-use audit as
for llm-full (Read of the call file and Write of the outbox file only) and list any exception.

## Files

- `batches.json`: 33 batches, calls with `call_file` and `outbox_file`, paths relative to `<RUN>`.
- `<RUN>/calls.jsonl`: all 768 calls (problem, arm, draw, hashes, sizes, call/outbox/reply paths).
- `<RUN>/calls/call-NNNN.txt`: the call files. Rebuild everything with `make_hints_v2.py --table
  ../../calib/intent-f3.json` then `build_hints2.py` (deterministic; `calls.jsonl` hashes must
  match the committed `prompt_sizes_hints2.csv`).
- `claim_kinds.json`: claim id to kind per arm and problem, for the per-kind analysis.
