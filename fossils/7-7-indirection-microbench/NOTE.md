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

## Sibling microbenches (added this session)

Extended from a single microbench to five, one per hot site named in
the perf 1/n commit summary plus the two perf-3/5 targets. Only default
and opt variants are wired for the new benches (no-opt build not
available this session; interrupt-check keeps its no-opt variant as a
placeholder).

**Targeted** — each isolates one specific perf commit's hot site.

| bench             | isolates       | hot site                                   |
|-------------------|----------------|--------------------------------------------|
| `interrupt-check` | perf 1/n, 6/n  | loop back-edge interrupt flag              |
| `stack-check`     | perf 1/n       | function-entry stack limit                 |
| `prebarrier`      | perf 1/n       | SetProp pre-barrier guard                  |
| `vm-call`         | perf 5/n       | `callVMInternal` (2 loads+call -> 1 load+mem-call) |
| `abi-call`        | perf 3/n       | `callWithABI` to a local (non-preemptible) ABI fn |

**Control** — exercises IC entry paths that none of the four perf commits
touch. Purpose: measure the AOT indirection floor on ops that should NOT
benefit from value mirroring or callWithABI-relocation. If opt still
beats default on these, the win generalizes beyond the four targeted
opts (implying second-order factors — cache pressure, register
allocation shape, section layout — are contributing). If opt ≈ default
here, the four opts fully account for the gap on the targeted benches.

| bench             | exercises       | rationale                                 |
|-------------------|-----------------|-------------------------------------------|
| `arith`           | BinOp (Add, Mul, Sub) | no IC — dispatch-only cost floor     |
| `prop-load`       | GetProp IC (monomorphic) | IC-entry floor via property read  |
| `array-load`      | GetElem IC (dense array) | IC-entry floor via element read   |

**Verification followups (block quoting numbers from these):**

- `vm-call.js` uses `Object.keys(obj)` as a candidate VM-call op. Confirm
  with `IONFLAGS=bl-aot ./jsshell ...` that the emitted code for the
  hot iter goes through `callVMInternal` on both cells and that GC
  pressure from the fresh-array alloc isn't dominating. Fallback ops
  documented in the JS file's header comment.
- `abi-call.js` uses `typeof obj === "object"` as a candidate. Confirm
  it emits `callWithABI` to `js::TypeOfObject` (which perf 3/n moved
  to the LOCAL list) on `$JSSHELL_OPT`. Fallbacks documented in the
  header.

The stack-check and prebarrier benches are unambiguous — the stack
limit and prebarrier guard load fire per iter regardless of whether
any fast-path intrinsics are involved.

## Interpretation update: opt < default on interrupt-check

First-pass n=1 result: default = 81 cyc/iter, opt = 69 cyc/iter. This
is *opposite* to the naive "AOT indirection is a tax" model but is
consistent with the perf 1/n design. That commit's own table shows the
AOT interrupt check at 1 dependent load; the default codegen still
reaches the interrupt flag through the JSContext (~2 dependent loads).
Value mirroring can outperform default because it amortizes pointer
chasing into a fixed frame slot.

This reframes the paper narrative: value mirroring is not purely an
AOT-tax mitigation. It is a mechanism that can beat default on hot
loads. Confirm with a `perf annotate` / `objdump` diff on the two
shells' interrupt-check emission before quoting the flip.

## Naming update (post-first-pass)

Variants were renamed to `<bench>-<build>` where `build ∈ {default, opt,
no-opt}`. `head`→`opt`, `no-opts`→`no-opt`, and a third `default` cell
(non-AOT shell, native baseline codegen) was added. Figures were
regrouped: `cycles-bars` is now a grouped bar chart by microbench, and a
new `cycles-table` figure emits paper-ready JSON via `write_typst_table`
for `my-papers/phase-4/lib/json/`.

Numbers below were captured under the old two-variant scheme; retained
for pipeline calibration, not for the paper.

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
- [ ] Build `no-opt` shell (external). Path convention assumed by the
      fossil: `@FIREFOX/build-shell-release-aot-noopts/dist/bin/js`.
- [ ] Build `default` shell (external, non-AOT). Path assumed:
      `@FIREFOX/build-shell-release/dist/bin/js`. Deliberately a
      separate binary, not `$JSSHELL_OPT` without `--aot`, so nothing
      AOT-related (image incbin, section reservation, compile-time
      indirection in the macroassembler if present) leaks into the
      floor measurement.
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
