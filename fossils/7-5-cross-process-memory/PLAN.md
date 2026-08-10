# 7-5 cross-process memory

## What this measures

Browser-tree resident memory at synchronised points during an AWSY tp6
run, quoted two ways:

- **RSS-sum**: naive sum of Rss across every firefox / plugin-container
  process in the tree. Overcounts pages that are shared via CoW because
  every process reports them at full weight.
- **PSS-sum**: sum of Pss across the same set. Shared pages are
  divided by the number of processes mapping them, so this is the true
  memory the tree costs the OS.

Two variants: stock browser vs AmberMonkey. We compare peak,
time-averaged, and median of RSS-sum and PSS-sum across the run.

## Why PSS matters for AmberMonkey

The AOT baseline interpreter blob is emitted into a `.text.aot`
section (see `js/src/jit/aot/AOTImageIncbin.cpp`), so it ships inside
the firefox binary as file-backed `PROT_EXEC` pages. At runtime
`InstallAOTBaselineInterpreter` wraps the region with
`JitCode::NewStatic()`, which bypasses `ExecutableAllocator` and never
memcpy's the blob into anonymous exec memory. The kernel can therefore
CoW-share the whole ~52 KB per-runtime block across every content
process that maps it.

- Under RSS the sharing win is invisible: every process bills the full
  52 KB.
- Under PSS the win shows up directly: 52 KB total across N processes
  instead of 52 KB * N.

Patched sites (profiler enter/exit toggle, code coverage counters)
break CoW on the pages they touch, so the measurement is only clean
when profiler and coverage instrumentation are off. Both are off in
the release/aot browser mozconfigs we use here.

## What this deliberately does not do

- **No engine instrumentation.** No `JS_INSTR`, no JSONL streams, no
  per-artifact attribution. See `3-1-jit-memory` for the version that
  tried to attribute per-tier resident bytes and became unwieldy.
- **No AWSY checkpoint alignment.** The sampler runs at a fixed 0.5 s
  cadence for the whole run. Peak / mean / median across the whole
  trace is the reported quantity. Adding checkpoint-anchored numbers
  is a later refinement if it turns out to matter.
- **No cross-run correlation of pids.** Every iteration gets a fresh
  process tree; we do not try to match "this pid was the compositor in
  run 1 and in run 2".

## Reading the output

`analyses/tree_memory.py` emits per-iteration:

- `rss_sum_peak_mb`, `pss_sum_peak_mb`: max over sample times of the
  per-time sum across the tree.
- `rss_sum_mean_mb`, `pss_sum_mean_mb`: mean over sample times of the
  per-time sum.
- `pss_over_rss`: ratio of mean PSS-sum to mean RSS-sum; how much of
  the naive resident footprint is actually shared.
- `sample_count`: number of 0.5 s samples that produced at least one
  firefox process.
- `peak_process_count`: max number of firefox / plugin-container
  processes seen at any one sample.

`figures/tree_memory_bars.py` produces a grouped bar chart: for each
variant, one bar for mean RSS-sum and one for mean PSS-sum with error
bars propagated from the per-iteration stddev.

## The shared-blob size scalar

The `.text.aot` section is folded into `.text` at link time, but the
`aot_image_start` and `aot_image_end` symbols bracket the image and
survive stripping-free. `scripts/aot_image_size.sh` prints the size
in bytes:

    scripts/aot_image_size.sh
    scripts/aot_image_size.sh path/to/other/libxul.so

This is the amount of executable memory that becomes CoW-shareable
across every AOT-using content process. Cite it as a scalar
(`constants.typ`) rather than measuring it at run time.

## Invariants the analysis enforces

- Variant name is `stock` or `aot` (validates against `command` in
  manifest).
- `command` contains `./mach awsy-test`.
- `command` mentions the correct binary path
  (`build-browser-release/dist/bin/firefox` for stock,
  `build-browser-release-aot/dist/bin/firefox` for aot).
- Samples file is non-empty and every line parses as JSON.
