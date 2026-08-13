# 7-7 indirection microbench

## What this measures

Per-iteration user-mode cycle cost of jsshell hot loops under three
build cells per microbench:

- `opt`: current AOT-enabled shell with all four perf commits applied
  (`perf 1/n` mirror-some-state, `perf 3/n` ABI reloc, `perf 5/n` callVM
  one-load, `perf 6/n` value-mirror-slots).
- `no-opt`: the same tree with those four commits reverted.
- `default`: non-AOT shell, JIT-generated baseline interpreter (native
  codegen with direct pointer references, no indirection chain).

Two deltas are meaningful:

- `no-opt` - `opt`: marginal cost of the four perf commits on this
  workload. Small signal; sensitive to noise floor.
- `opt` - `default`: residual AOT indirection overhead vs. vanilla
  baseline codegen. `default` is the theoretical floor `opt` is trying
  to approach. Expected to be a much larger delta and above the noise
  floor.

Absolute per-iter cycles is only meaningful relative to the other cells.

## Variant naming convention

Each variant is `<bench>-<build>`, where `<build>` is one of `default`,
`opt`, `no-opt`. Adding a new microbench means:

1. Drop a JS file in `microbenches/` that runs a known iteration count.
2. Add `BENCH_<UPPER>` to `[variables]` in `fossil.toml`.
3. Add three variants: `<bench>-default`, `<bench>-opt`, `<bench>-no-opt`.
4. Add `<bench>` to `ITER_COUNTS` in `analyses/parse_cycles.py`.

No figure edits required; both `cycles-bars` and `cycles-table` group
by bench automatically.

## Why this fossil is separate from 7-4

7-4 measures the E2E Speedometer / JetStream score delta of the entire
AmberMonkey diff. It cannot decompose the delta by mechanism. 7-7 uses
hand-authored microbenches so a small per-instruction effect is
measurable above the noise floor. Both fossils are needed to make a
defensible claim about the perf opts.

## Cell binaries

Referenced by path; built externally.

- `$JSSHELL_DEFAULT` = `@FIREFOX/build-shell-release/dist/bin/js`
- `$JSSHELL_OPT`     = `@FIREFOX/build-shell-release-aot/dist/bin/js`
- `$JSSHELL_NO_OPT`  = `@FIREFOX/build-shell-release-aot-noopts/dist/bin/js`

Building the AOT shells (including AOT-image capture at each git state)
is out of scope. This fossil assumes all three binaries exist and that
the two AOT shells pass jit-test on their embedded corpus before it runs.

## Measurement

Each variant runs one process under `perf stat`:

    perf stat --output=$T -j -e cycles:u,instructions:u,ref-cycles:u \
        $JSSHELL_<build> <flags> -f $BENCH_<bench>

`opt` and `no-opt` pass `--aot --blinterp-eager --no-baseline`.
`default` passes `--blinterp-eager --no-baseline` only (interpreter
tier held constant across all three; only the indirection changes).

perf stat wraps the entire process. Startup differs by a few ms (AOT
memcpy vs JIT-generate the ~21kb baseline blob); hot loops run tens of
seconds, so cross-cell delta is dominated by the loop.

## Analysis

`analyses/parse_cycles.py` splits the variant name into `(bench, build)`,
reads perf's newline-delimited JSON on stdin, validates that every event
ran at >= 99.5% (no multiplexing), and emits:

- `cycles_per_iter`  = cycles:u / ITER_COUNTS[bench]
- `insns_per_iter`   = instructions:u / ITER_COUNTS[bench]
- `ipc`              = insns / cycles

Rejection reasons: unknown bench, unknown build, any event missing, any
event multiplexed, or a JSON parse failure in the perf output.

## Figures

- `cycles-bars` (`figures/cycles_bars.py`): grouped bar chart, one
  x-axis group per microbench, three touching bars (default, opt,
  no-opt) per group. Mean ±stddev, numeric mean above each bar.

- `cycles-table` (`figures/cycles_table.py`): paper-ready JSON table
  via `write_typst_table`. One row per microbench, columns for the
  three cycles/iter values plus opt−default (AOT residual overhead)
  and no-opt−opt (marginal perf-commit cost), each as absolute cycles
  and as a ratio. Drops into `my-papers/phase-4/lib/json/` and is
  addressable from `draft.typ` via `cell-from-table` / `cell-value`.

## Acceptance criteria

- All three cell binaries exist and have differing build-ids.
- All 30 iterations produce non-multiplexed counters for all events.
- Per bench: `default < opt <= no-opt` on `cycles_per_iter` mean. If
  the ordering breaks, either the microbench does not exercise the
  reverted opts, the AOT indirection is a wash on this op, or the
  noise floor is above the signal.
- For the `no-opt - opt` claim specifically: per-cell stddev < gap.
  Otherwise the measurement is inconclusive; bump iterations or add
  noop subtraction. The `opt - default` gap should be large enough
  that noise is not a concern.

## Deliberately not included

- E2E workload timing (7-4).
- Modeled workload delta (per-op cycle cost × dynamic op count from
  7-2 coverage); future fossil.
- Cell-build automation. Externally managed.
- `perf annotate` qualitative pass. Exploratory, lives outside the
  fossil.

## Open items to verify before first run

- `perf` binary available on the measurement host (not in the default
  devshell as of writing; may need `nix-shell -p linuxPackages.perf`).
- `perf_event_paranoid <= 1` so `cycles:u` opens without root.
- CPU pinning / governor / boost handled by the harness or documented
  as manual preflight; match the machine setup used by 7-4.
- `$JSSHELL_DEFAULT` and `$JSSHELL_NO_OPT` build path convention agreed
  with the external build workflow.
