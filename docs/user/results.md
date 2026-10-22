# L0 results

Measured on 2026-10-22 with Odin III `main` at commit `158ced05`, library 1.0.0, 3 jobs (from
`docs/runbook-l0.md`).

- `wyrd run`: 136 runs (68 designs x 2 architectures), all `ok`, 71 s wall time.
- `loki assemble`: `assembled 68 designs into dataset`.
- `loki check dataset`: `loki check: 0 error(s)`.

Manifest summary (`dataset/manifest.json`, 43 MB on disk):

| Floor | ok | skipped | nodes (sum over ok designs) |
|---|---|---|---|
| f1-k6 | 66 | 2 | 7848 |
| f1-earch | 66 | 2 | 7848 |
| f2 | 66 | 2 | 13513 |

The split is 52 train and 16 test designs (seed `loki-l0-2026`). The two skipped designs are
`micro_adder_hard_block` and `micro_hard_adder_cin_propagation`: they instantiate the library cell
`adder` with a parameter, which Odin III's reader rejects.

The acceptance test (`tests.test_acceptance_micros`, about one minute, local only) requires that
every built floor has `equivalent` results for the `writer` and `anon` checks, and that label
coverage over `lut` and `ff` nodes is at least 0.95. It measured 9121 of 9121.
