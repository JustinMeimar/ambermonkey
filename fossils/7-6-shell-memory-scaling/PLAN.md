# 7-6 shell memory scaling

## What this measures

Peak resident set size and peak anonymous-executable residency of the
JS shell process as a function of N in-process worker JSRuntimes
running `worker_realistic.js`. Four variants at each N:

- `stock-base`      : `--no-ion` (baseline-only stock)
- `stock-full`      : (no policy flags) full-tier stock with Ion enabled
- `aot-restricted`  : `--aot --aot-only --no-ion` (AmberMonkey restricted execution)
- `aot-full`        : `--aot` (AmberMonkey with runtime tiering left on)

The shell process is identical between variants (same
`build-shell-release-aot` binary); only the runtime flags differ.

## The two comparisons

- **Restricted-execution deployment**: `stock-base` vs `aot-restricted`.
  Isolates the memory profile of the restricted-execution mode AmberMonkey
  is designed to support. Both variants have Ion off, so the delta
  attributes to AOT sharing plus the effect of forbidding runtime
  compilation of image misses (`--aot-only`).

- **Opportunistic sharing in a full-tier deployment**: `stock-full` vs
  `aot-full`. Both variants leave Ion, Baseline runtime codegen, and
  IC runtime codegen enabled; the AOT variant additionally consults
  `.text.aot` and serves matching artifacts from it. The delta
  isolates the memory benefit of AOT sharing in a deployment that has
  not adopted the restricted-execution policy.

## Metrics

Peak RSS is captured by a Python wrapper
(`scripts/measure_peak_rss.py`) using
`resource.getrusage(RUSAGE_CHILDREN).ru_maxrss`. Peak
anonymous-executable residency is polled from
`/proc/<pid>/smaps` every 50 ms while the child runs, summing `Rss`
across VMAs whose permissions contain `x` and whose pathname is
empty. Anonymous mmaps are where SpiderMonkey's `ExecutableAllocator`
places all JIT pools; the file-backed `.text.aot` section of the
engine library is intentionally excluded, so anon-exec isolates
dynamically-generated JIT code.

## Reading the output

Per iteration, `analyses/parse_rss.py` emits:
- `peak_rss_kb`, `peak_rss_mb`
- `peak_anon_exec_kb`, `peak_anon_exec_mb`
- `workers` (from variant name)
- `kind` (one of the four variant kinds)

`figures/memory_table.py` produces the primary anon-exec table plus
a companion RSS table (`memory-table.json`, `memory-table-rss.json`).
`figures/rss_scaling.py` produces an eight-series log-log line plot
(four variants x {anon-exec, RSS}).

## Invariants the analysis enforces

- Variant name matches `n<N>-(stock-base|stock-full|aot-restricted|aot-full)`.
- Each kind's flag contract is enforced whole-token so `--aot` and
  `--aot-only` are not confused: `stock-base` requires `--no-ion` and
  forbids AOT flags; `stock-full` forbids all four policy flags;
  `aot-restricted` requires all three AOT/no-ion flags; `aot-full`
  requires `--aot` and forbids `--aot-only`/`--no-ion`.
- Wrapper emitted `peak_rss_kb=<int>` and `peak_anon_exec_kb=<int>`
  on stderr; missing either invalidates the observation.

## Known constraints

- Requires enough helper threads in the shell to spawn N workers.
  Default SM helper-thread pool is small; large N may need
  `--thread-count=N` or may SKIP entirely (see `worker_realistic.js`).
- Helper-thread saturation on the measurement host shows up as
  serialization of a subset of workers around $N approx 128$;
  surrounding points retain linear scaling.
- `worker_realistic.js` is a mixed-operation microworkload, not a
  real application. Claims from this fossil are scoped to
  "per-runtime private JIT-code residency under this workload."

## Related quantities

- `.text.aot` size (the amortized shared cost) is a build-time
  scalar. See `7-5-cross-process-memory/scripts/aot_image_size.sh`.
- `7-5-cross-process-memory` would be the browser-side counterpart
  (process-tree PSS during AWSY tp6). Not currently developed.
