# 7-6 shell memory scaling

## What this measures

Peak resident set size of the JS shell process as a function of N
in-process worker JSRuntimes running `worker_realistic.js`. Two
variants at each N:

- `stock`: `--no-ion` (baseline-only, no AOT).
- `aot`: `--aot --aot-only --no-ion` (AOT-loaded baseline, no
  fallback compilation).

The shell process is identical between variants (same
`build-shell-release-aot` binary); only the runtime flags differ. Peak
RSS is captured by a Python wrapper (`scripts/measure_peak_rss.py`)
using `resource.getrusage(RUSAGE_CHILDREN).ru_maxrss` because
`/usr/bin/time` is not installed on this host.

## The claim

Under stock, every JSRuntime allocates its own baseline interpreter,
its own IC pool, and its own compiled Baseline code. Total private JIT
bytes grow roughly linearly with N. Under AOT, the interpreter and
recorded IC / Baseline artifacts come from libxul's `.text.aot`
region, mapped file-backed and CoW-shared, so per-runtime private code
stays approximately constant as N grows.

Peak RSS overcounts the JIT contribution (it also includes GC heap,
stacks, self-hosted data, allocator slack), but the *delta* between
stock and AOT at fixed N is attributable to JIT-code residency
because everything else is identical.

## Related quantities

- `.text.aot` size (the amortized shared cost) is a build-time
  scalar. See `7-5-cross-process-memory/scripts/aot_image_size.sh`.
- `7-5-cross-process-memory` is the browser-side counterpart: same
  claim measured at process-tree PSS during AWSY tp6.

## Reading the output

Per iteration, `analyses/parse_rss.py` emits:
- `peak_rss_kb`, `peak_rss_mb`: peak RSS of the shell process
  (whole-process, dominated by non-JIT per-worker overhead).
- `peak_anon_exec_kb`, `peak_anon_exec_mb`: peak of the sum of Rss
  over anonymous executable VMAs in `/proc/self/smaps`, polled at
  50 ms cadence during the run. This is SpiderMonkey's dynamically
  allocated JIT code (baseline interpreter, compiled baseline, IC
  stubs).
- `workers`: parsed from the variant name.
- `aot`: boolean, from the variant name suffix.

`figures/rss_scaling.py` produces a log-log line plot with four
series: {stock, aot} x {total RSS (solid), anon exec (dashed)}. RSS
tracks non-JIT overhead and shows a modest reduction; anon exec
isolates the JIT-attributable slice and shows the large one.

## Invariants the analysis enforces

- Variant name matches `n<N>` or `n<N>-aot`.
- `--aot` and `--aot-only` present exactly when the variant name
  carries `-aot`.
- Wrapper emitted `peak_rss_kb=<int>` on stderr; if missing, the
  wrapper failed to run and the observation is invalid.

## Known constraints

- Requires enough helper threads in the shell to spawn N workers.
  Default SM helper-thread pool is small; large N may need
  `--thread-count=N` or may SKIP entirely (see worker_realistic.js).
- N=256+ is aspirational; if bottlenecked by helper threads, keep the
  fossil to N in {1, 4, 16, 64} and note the constraint in the paper.
