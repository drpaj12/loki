# Raw replies of the LLM pilot (L Q1.2)

`re/raw/resp-NNN.txt` (118 files) and `standard/raw/resp-NNN.txt` (73 files) are the model's replies, byte for byte as the subagent wrote them, one per call. `NNN` is the call number of `dispatch-log-re.tsv` / `dispatch-log-standard.tsv`. A call with no file is a `no_file` or `api_refused` outcome in `status.csv`.

They are kept so the scores in `results.csv` can be re-derived and re-scored, for example with another equivalence checker. The prompts are not included: they are regenerated from the sources and scripts that EXPERIMENT.md names (section Sources, with their licences). A reply may quote parts of its prompt.

Model: claude-sonnet-5-5, through Claude Code subagent calls (2026-10-26 and 2026-10-27).
