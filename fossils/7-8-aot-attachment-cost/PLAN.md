# Runtime AOT attachment cost

## Question

This fossil measures costs that steady-state Speedometer throughput does not expose. It separates the content-process startup effect of enabling the AOT image from the lookup, wrapper allocation, metadata reconstruction, initialization, and residual compilation work performed inside SpiderMonkey.

The embedded image is part of `libxul`, so the experiment does not label a separate `mmap` interval as image loading. Instead, image attachment begins when SpiderMonkey validates and consumes an embedded artifact.

## Experimental design

We use Talos `cpstartup`, which creates 20 content processes per invocation and measures each process until it is ready to load a URL. Every cell uses the same AOT-capable release browser binary and the normal content sandbox. This controls for build differences and confines the treatment to runtime configuration.

One Fossil observation is one randomized block containing four cells:

| Cell | AOT image | Timing | Purpose |
| --- | --- | --- | --- |
| `runtime_clean` | disabled | disabled | end-to-end runtime-generated baseline |
| `aot_clean` | enabled | disabled | end-to-end AOT treatment |
| `runtime_timed` | disabled | enabled | runtime compilation attribution and timing overhead |
| `aot_timed` | enabled | enabled | AOT attachment attribution and timing overhead |

The driver randomizes the four cells independently within each block and records the seed and realized order. Ten blocks provide ten paired startup differences while each Talos invocation retains its 20 process-level replicates.

The AOT treatment enables `JIT_OPTION_useAOTImage` without strict AOT enforcement. Missing artifacts therefore use the normal runtime fallback. This measures the deployable configuration and lets the timing records quantify residual Baseline and inline-cache compilation.

## Instrumentation

Setting `JS_AOT_TIMING=1` enables fixed-size, process-global accumulators in SpiderMonkey. The content-process shutdown observer writes one `AOT_TIMING` JSON record to inherited standard error. The record contains call counts and elapsed nanoseconds for:

- image compatibility checks
- Baseline interpreter attachment
- runtime indirection table initialization
- inline-cache corpus attachment
- Baseline-function image lookup and metadata reconstruction
- inline-cache image lookup and private-stub attachment
- runtime Baseline and inline-cache compilation

Counters report image lookup hits and misses, wrapper counts, metadata and code bytes, and private inline-cache stub bytes. Clean cells do not enable these clocks. The difference between timed and clean cells estimates instrumentation overhead separately for runtime and AOT execution.

## Primary results

The primary end-to-end metric is the paired `aot_clean - runtime_clean` Talos `cpstartup` time. We report its mean and spread across blocks.

For attribution, we report mean milliseconds per content process for every timed phase. We also report AOT work added, runtime compilation saved, residual AOT compilation, and their net direct balance. Phase totals exclude shutdown serialization and should not be treated as an alternative wall-clock startup measurement.

## Running

Build the instrumented AOT browser first:

```sh
cd /home/justin/spidermonkey/firefox
PATH=/home/justin/.mozbuild/clang/bin:$PATH \
  MOZCONFIG=/home/justin/spidermonkey/ambermonkey/mozconfigs/browser-release-aot.mozconfig \
  ./mach build binaries
```

Then collect ten randomized blocks and generate the tables:

```sh
cd /home/justin/spidermonkey/ambermonkey
fossil --project ambermonkey bury 7-8-aot-attachment-cost
fossil --project ambermonkey figure 7-8-aot-attachment-cost --figure cost-tables
```

The driver fails if a clean cell emits timing data, a timed cell emits no content-process records, or the AOT cell does not attach its interpreter image. These checks prevent a successful-looking record from silently measuring the wrong configuration.
