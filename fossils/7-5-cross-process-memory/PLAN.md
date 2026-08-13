# 7-5 per-process memory on Octane sub-benchmarks

## What this measures

Peak per-process resident memory of the JS shell (N=1) running each
Octane sub-benchmark to completion, in five configurations:

- `interp`   : `--no-jit-backend`   interpreter only, no JIT of any kind
- `baseline` : `--no-ion`           runtime Baseline codegen and runtime ICs, no Ion
- `stock`    : (no policy flags)    default: Baseline codegen, IC codegen, Ion
- `aot`      : `--aot`              AmberMonkey opportunistic, runtime tiering left on
- `aot-only` : `--aot --aot-only`   AmberMonkey strict: image only, misses interpret; the shell option sets useAOTImage=true and ion=false internally, so Ion is off in this configuration

Two metrics captured by the same wrapper:

- **peak RSS**: `getrusage(RUSAGE_CHILDREN).ru_maxrss`. Full resident set,
  includes file-backed pages (libxul .text, .text.aot image, mapped .rodata).
- **peak private-anonymous RSS**: sum of `Rss` across VMAs in
  `/proc/<pid>/smaps` whose pathname is empty. Anonymous mmaps are where
  SpiderMonkey's heap arenas, GC nursery, stacks, and
  `ExecutableAllocator` JIT pools land, so this is the private per-process
  allocation cost -- the quantity that CoW sharing of the .text.aot image
  does not touch and cannot amortize.

A companion `peak_anon_exec_kb` (anon-and-executable) isolates the JIT
slice for cross-reference against 7-6.

## Why the shape is (bench x config)

- Fossil 7-6 varies the number of in-process worker JSRuntimes for one
  synthetic workload; its story is per-runtime scaling.
- 7-5 varies the workload across a widely-known suite at N=1; its story
  is that the per-process JIT footprint AmberMonkey displaces is
  consistent across real workloads, not an artifact of one microbench.

Together they support two independent CGO claims: (i) per-process, AOT
replaces the dynamically generated Baseline+IC code with a shared
file-backed image (7-5), and (ii) that displacement compounds linearly
across worker runtimes (7-6).

## Configurations, precisely

| kind     | flags               | Baseline codegen | IC codegen | Ion   | .text.aot consulted |
|----------|---------------------|------------------|------------|-------|---------------------|
| interp   | `--no-jit-backend`  | no               | no         | no    | no                  |
| baseline | `--no-ion`          | yes (runtime)    | yes        | no    | no                  |
| stock    | (default)           | yes              | yes        | yes   | no                  |
| aot      | `--aot`             | opportunistic    | yes        | yes   | yes                 |
| aot-only | `--aot --aot-only`  | AOT only (misses interpret) | AOT only (misses interpret) | no (option forces ion=false) | yes |

The three reduction pairs the paper reports:

- (stock, aot): drop-in delta a stock browser sees when `--aot` is
  flipped on. Ion on in both.
- (stock, aot-only): strict-AOT delta. Ion is on in stock and off
  in aot-only (the option forces ion=false), so this pair jointly
  isolates the effect of forbidding runtime Baseline codegen,
  runtime IC codegen, and Ion.
- (baseline, aot-only): the symmetric AOT-vs-runtime-baseline pair.
  Ion is off in both configurations (baseline via `--no-ion`,
  aot-only via `--aot-only` forcing ion=false internally), so the
  delta attributes to AOT replacing runtime Baseline+IC codegen
  while everything Ion-related is held out symmetrically.

## Metrics reported

Per (bench, config, iteration):
- `peak_rss_kb`, `peak_rss_mb`
- `peak_anon_kb`, `peak_anon_mb`
- `peak_anon_exec_kb`, `peak_anon_exec_mb`

Three JSON tables emitted at figure time:
- `memory-table.json`           full RSS
- `memory-table-anon.json`      private-anonymous RSS (primary paper table)
- `memory-table-anon-exec.json` JIT slice for cross-reference against 7-6

Each table has rows = benchmarks (Octane order) plus a `geomean` row;
columns = interp | baseline | stock | aot | (aot vs baseline) |
(aot vs stock). The paired bar chart figure (`anon-exec-bars.pdf`
plus companion `anon-bars.pdf`) presents the same data sorted by the
`baseline` column descending so the largest per-process JIT pools
appear first.

## What this deliberately does not do

- No engine instrumentation. No JSONL streams, no per-artifact
  attribution.
- No process-tree sampling. N=1, one shell process per run; the
  browser process-tree measurement lived here previously and has been
  removed. If we later need CoW-across-processes numbers, add a
  separate fossil rather than overloading this one.
- No warmup runs. Octane runners self-warm internally.

## Invariants the analysis enforces

- Variant name matches `<bench>-<config>` with `bench` in the Octane 15
  and `config` in {interp, baseline, stock, aot, aot-only}.
- Whole-token flag contract per config: interp requires
  `--no-jit-backend` and forbids AOT flags; baseline requires
  `--no-ion` and forbids `--aot`, `--aot-only`, `--no-jit-backend`;
  stock forbids all four policy flags; aot requires `--aot` and forbids
  `--aot-only`, `--no-ion`, `--no-jit-backend`; aot-only requires both
  `--aot` and `--aot-only` and forbids `--no-ion`, `--no-jit-backend`.
- Wrapper emitted `peak_rss_kb`, `peak_anon_kb`, `peak_anon_exec_kb`
  on stderr; missing any invalidates the observation.

## Known constraints

- Peak-RSS from `ru_maxrss` is the child's high-water mark for the
  whole run. Anon-exec peaks may lag past code-cache resets; not an
  issue at Octane's typical few-second runs.
- `.text.aot` inclusion in RSS is workload-invariant (all `aot`
  variants map the same image); comparisons across benchmarks are
  informative, comparisons of RSS-delta against `stock` are not
  confounded by it.

## Related quantities

- `.text.aot` size (the amortized shared cost) is a build-time
  scalar. See `scripts/aot_image_size.sh`.
- `7-6-shell-memory-scaling` is the N-runtimes scaling counterpart on
  one synthetic workload.
