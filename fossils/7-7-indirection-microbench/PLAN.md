# 7-7 indirection microbench

## What this measures

Per-iteration user-mode cycle cost of a jsshell hot loop under two ablation cells:

- `head`: current AOT-enabled shell with all four perf commits applied
  (`perf 1/n` mirror-some-state, `perf 3/n` ABI reloc, `perf 5/n` callVM
  one-load, `perf 6/n` value-mirror-slots).
- `no-opts`: the same tree with those four commits reverted.

The delta between cells is the marginal cost of those perf opts on this
workload. The absolute per-iteration number is only meaningful relative to
the other cell.

## Why this fossil is separate from 7-4

7-4 measures the E2E Speedometer / JetStream score delta of the entire
AmberMonkey diff. It cannot decompose the delta by mechanism. 7-7 uses a
hand-authored microbench so a small per-instruction effect is measurable
above the noise floor. Both fossils are needed to make a defensible claim
about the perf opts.

## Chosen operation

`microbenches/interrupt_check.js`: an integer-add loop of 5e8 iterations.
Each iteration hits the interrupt-check slot and one bytecode dispatch, both
of which are affected by `perf 1/n` and `perf 6/n`. Other ops (GetProp,
callVM, ...) are orthogonal and can be swapped in as sibling files.

## Cell binaries

Referenced by path; built externally.

- `$JSSHELL_HEAD`   = `@FIREFOX/build-shell-release-aot/dist/bin/js`
- `$JSSHELL_NOOPTS` = `@FIREFOX/build-shell-release-aot-noopts/dist/bin/js`

Building both shells (including AOT-image capture at each git state) is out
of scope. This fossil assumes both binaries exist and pass jit-test on their
embedded corpus before it runs.

## Measurement

Each variant runs one process under `perf stat`:

    perf stat --output=$T -j -e cycles:u,instructions:u,ref-cycles:u \
        $JSSHELL_<cell> --aot --blinterp-eager --no-baseline -f $BENCH_JS

perf stat wraps the entire process (startup + JIT init + one measurement
call). Startup is nearly identical across cells because AOT is a memcpy,
not codegen, so the delta between cells is dominated by the hot loop.
No noop-subtraction in the first pass; add if precision demands it.

## Analysis

`analyses/parse_cycles.py` reads perf's newline-delimited JSON on stdin,
validates that every event ran at >= 99.5% (no multiplexing), and emits:

- `cycles_per_iter`  = cycles:u / ITER_COUNT
- `insns_per_iter`   = instructions:u / ITER_COUNT
- `ipc`              = insns / cycles

Rejection reasons: any event missing, any event multiplexed, or a JSON
parse failure in the perf output.

## Figure

`figures/cycles_bars.py` draws a two-bar chart of `cycles_per_iter` mean
+/- stddev for `head` vs `no-opts`, with the numeric mean printed above
each bar and the ratio annotated.

## Acceptance criteria

- Both cell binaries exist and have differing build-ids.
- All 30 iterations produce non-multiplexed counters for all three events.
- `no-opts` reports strictly higher `cycles_per_iter` mean than `head`. If
  it does not, either the microbench does not exercise the reverted opts,
  or the noise floor is above the signal.
- Per-cell stddev is smaller than the head-vs-no-opts gap. If not, the
  measurement is inconclusive; bump iterations or add noop subtraction.

## Deliberately not included

- E2E workload timing (7-4).
- Modeled workload delta (per-op cycle cost x dynamic op count from 7-2
  coverage); future fossil.
- More than one operation per fossil in this first pass. Sibling ops
  land as additional microbench files and new variants.
- Cell-build automation. Externally managed.
- `perf annotate` qualitative pass. Exploratory, lives outside the fossil.

## Open items to verify before first run

- `perf` binary available on the measurement host (not in the default
  devshell as of writing; may need `nix-shell -p linuxPackages.perf`).
- `perf_event_paranoid <= 1` so `cycles:u` opens without root.
- CPU pinning / governor / boost handled by the harness or documented
  as manual preflight; match the machine setup used by 7-4.
- `$JSSHELL_NOOPTS` build path convention agreed with the external
  build workflow.
