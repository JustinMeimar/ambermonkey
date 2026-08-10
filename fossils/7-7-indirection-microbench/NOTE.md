# 7-7 status note

## What works end-to-end

- `bury` runs the microbench under `perf stat -j` and captures the three
  events. Confirmed with `nix-shell -p perf --run "fossil bury ..."`.
- `analyze -a cycles` parses the perf NDJSON out of the observation blob,
  validates counter running >= 99.5%, emits per-iter metrics.
- `figure --figure cycles-bars` renders a PDF bar chart.

## Bug fixes applied while shaking out

- `fossil.toml` variables are NOT recursively expanded. Nested `$EVENTS`
  inside `$RUN` stayed literal; inlined the event list into `RUN`.
- `parse_cycles.py` receives a JSON observation object on stdin (with
  `stdout` as a list of lines), not raw text. Switched to `json.load` +
  join. Also read `iteration` from the observation, not the manifest.

## HEAD-only numbers (4 iters, no NO_OPTS build yet)

- cycles/iter: 70-75 (~5% run-to-run spread)
- insns/iter: 242.118 (5 sig figs stable across runs)
- IPC: 3.25-3.47
- ref-cycles/iter: 56-60
- counter running: 100.00 across every event, every run

## Promise assessment

**Cautious yes on the plumbing. Yellow flag on signal-to-noise.**

The pipeline is boring and deterministic, which is what we want. The
instruction count is repeatable to five sig figs — that tells us the
workload itself is deterministic and any variance we see is
microarchitectural, not JS-level.

But the 5% cycle-count stddev is the concern. Rough back-of-envelope
for the ablation signal:

- `perf 1/n` + `perf 6/n` save one load per interrupt check.
- One load ~ 0.3-1 cycle amortized when L1-hot.
- Loop hits interrupt check every iter -> ~1 cyc/iter savings.
- That is ~1.4% of the 72 cyc/iter absolute; well below current noise.

At 30 iterations with 5% stddev, per-cell 95% CI is ~1.8% of the mean.
The head/no-opts gap could easily be inside the CI.

## Actions before running the real ablation

- [ ] Bump N in `interrupt_check.js` from 5e8 -> 5e9 (10x). Runtime goes
      from ~8.6s to ~86s per iter. Reduces per-invocation static overhead
      as a fraction of total but does NOT tighten cycles/iter noise if the
      noise is frequency drift.
- [ ] Pin the shell to a single core and lock frequency governor. The
      most likely dominant noise source given the numbers. Preflight
      script + `taskset` wrapper on the `RUN` variable.
- [ ] Build `NO_OPTS` shell (external). Path convention assumed by the
      fossil: `@FIREFOX/build-shell-release-aot-noopts/dist/bin/js`.
- [ ] After first no-opts run, re-check whether gap > CI. If not, either
      bump N further, add noop-subtraction, or switch to an op that
      exercises more of the reverted opts per iter.

## Non-actions (intentional)

- Not adding a preflight script yet; do it once we know what to check.
- Not changing analyzer to reject on cross-run cycle stddev; wait until
  we have real ablation data to calibrate a threshold.
- Not automating the two builds; still user's problem per prior scope
  decision.

## Open question for the ablation cell

The AOT image is baked into the shell at build time (`.text.aot`
section via `AOTImageIncbin.cpp`). To build a NO_OPTS shell we need
to either:

- (a) re-record the corpus at the reverted commit and rebuild, or
- (b) reuse the HEAD corpus if the image format is stable across the
      four reverted commits.

`perf 3/n` in particular ("ABI call relocations auto handled") looks
like it changes what's captured, so (b) is probably wrong. Confirm
before spending the corpus-recording time.
