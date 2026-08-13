# Handoff note

Work stopped on 2026-08-10 before collecting measurements. No paper files were edited.

## Current state

The new fossil is scaffolded in this directory:

- `fossil.toml` defines one `blocked` variant with ten observations.
- `scripts/run_block.py` makes each observation a randomized four-cell block: runtime clean, AOT clean, runtime timed, and AOT timed.
- Every cell uses the same AOT-capable release browser. The AOT treatment sets `JIT_OPTION_useAOTImage=true` and permits normal fallback on a miss.
- `analyses/parse_startup_cost.py` extracts Talos `cpstartup`, per-process timing phases, counters, timing overhead, compilation saved, and the net direct balance.
- `figures/cost_tables.py` emits `attachment-costs.json`, `startup-effects.json`, and `attachment-counts.json`.
- `PLAN.md` records the rationale and protocol.

The coordinated Firefox instrumentation is present as uncommitted work in `/home/justin/spidermonkey/firefox`. `JS_AOT_TIMING=1` enables it. Content-process shutdown writes one `AOT_TIMING` JSON record to inherited standard error. The record covers image compatibility, interpreter attachment, runtime indirection-table initialization, IC-corpus attachment, Baseline lookup and reconstruction, IC lookup and private attachment, runtime Baseline compilation, and runtime IC compilation. It also reports lookup, wrapper, byte, and stub counters.

Firefox files changed:

- `js/public/AOTTiming.h`
- `js/src/jit/AOTTiming.h`
- `js/src/jit/AOTTiming.cpp`
- `js/src/jit/AOTInstaller.cpp`
- `js/src/jit/BaselineCacheIRCompiler.cpp`
- `js/src/jit/BaselineCodeGen.cpp`
- `js/src/jit/Ion.cpp`
- `js/src/jit/moz.build`
- `js/src/moz.build`
- `js/xpconnect/src/AOTCoverageShutdown.cpp`

## Validation completed

- `./mach format` completed with zero errors and applied five fixes.
- Firefox `git diff --check` passed.
- All three fossil Python files pass `py_compile` when `PYTHONPYCACHEPREFIX` points into `/tmp`.
- `fossil bury 7-8-aot-attachment-cost --dry-run` expands the intended command.
- Synthetic parser checks passed for phase aggregation and `cpstartup` extraction.
- Synthetic figure input produced three valid JSON tables.
- The final Firefox build attempt configured successfully and entered the normal compile. It was stopped at the user's request while compiling unrelated DOM and media targets. The full build did not finish, so the instrumentation is not yet compile-validated.

The restricted agent shell did not expose Clang, Rust, GNU Make, or the libraries required to load Mozilla's `libclang`. The successful configuration used explicit tool paths and a temporary library directory. A normal Firefox development shell may not need these additions. The temporary directory was `/tmp/amber-firefox-build-libs`, with links for `libstdc++.so.6` and `libz.so.1` from the Mozilla sysroot.

## Resume here

1. Finish `./mach build binaries` with the AOT browser mozconfig. The partially completed object directory should make this incremental.
2. Fix any C++ errors and rerun `./mach format` plus `git diff --check`.
3. Run one block first with `fossil --project ambermonkey bury 7-8-aot-attachment-cost -n 1`. This performs four Talos `cpstartup` invocations.
4. Confirm the timed cells contain content-process `AOT_TIMING` records, clean cells contain none, and the AOT cell reports at least one interpreter wrapper.
5. Run the analyzer and table generator against that smoke record.
6. Add a compact attribution-summary table for the already computed `aot_work_added`, `compilation_saved`, `aot_residual_compilation`, and `net_direct_balance` metrics.
7. After the smoke result looks sound, collect all ten randomized blocks.

Do not start with the full ten-block run. The browser build and one-block record are the next gates.
