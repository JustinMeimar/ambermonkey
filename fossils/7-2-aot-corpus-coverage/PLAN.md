
AOT corpus coverage under browser workloads. Each firefox
process that touches the AOT image writes one coverage JSON at
shutdown (js/src/jit/AOTCoverage.cpp). A run collects one file
per pid; the reducer folds them into a single row of static +
dynamic coverage figures.

Static coverage: fraction of packed baseline-function and IC-stub
blobs that were actually installed / attached at least once. The
baseline-function "used" bit is set at TryInstallAOTBaselineScript
time (install implies used, cold or hot). The IC-stub "used" bit
requires an actual BaselineCacheIRCompiler attach against the
pre-loaded JitCode -- mere load into the runtime-wide table does
not count.

Dynamic weight: sum of per-artifact hit counters. Baseline uses
ICScript::warmUpCount clamped at JitOptions.normalIonWarmUpThreshold
so post-graduation Ion ticks do not inflate the number. IC stubs
use ICCacheIRStub::enteredCount() summed across every attached
static-JitCode-backed stub reachable from the live JitScript graph.

Variants: jetstream3 and speedometer3 are the two browser-level
workloads we motivate the paper against. Both run one page cycle
inside one browser cycle so a variant is a single startup+exercise
episode. default_iterations = 3 provides mean+stddev at the fossil
layer.

Shutdown-flush plumbing. The dynamic walk MUST run while zones and
IC stubs are still live. On jsshell that is JSRuntime::destroyRuntime.
In Firefox that hook fires too late in content procs -- by the time
destroyRuntime is called, the zones the walker iterates are already
gone, so ZonesIter yields nothing and every dyn count comes back as
zero (static "used" bits survive because they are set at install /
attach time, not by the walk). The fix, adapted from the empirical-
motivation branch's JitInstrReporter, is an nsIObserver in
js/xpconnect/src/AOTCoverageShutdown.cpp that listens for
"xpcom-shutdown" (parent) and "content-child-shutdown" (content) and
calls AOTCoverage::FlushAndWrite from there. Whichever hook fires
first wins -- FlushAndWrite is idempotent via a `flushed` flag on
State.

## Tables

`coverage_tables.py` folds buried records into the `{columns, rows}`
shape the typst `json-table` loader reads. Records are named on the
command line rather than taken as the last N, because a record is
pinned to whichever image was installed when it ran and nothing inside
the record says which image that was. `--last` would silently pool two
different corpora into one distribution.

Holding the workload fixed and varying the corpus is an ablation, and
`--delta` reports the second column minus the first:

    python3 scripts/coverage_tables.py --records records --delta \
      full=<record-id> ics-selfhosted=<record-id>

Holding the corpus fixed and varying the workload asks how far a corpus
generalizes; pass the two workload records with no `--delta`.

### Reading the IC columns

The lookup order in BaselineCacheIRCompiler is atoms zone, then the
per-zone stub cache, then compile, and the three counters follow it.
So `zone_cache_hit` is an AOT *miss* that a stub compiled earlier in
the same zone absorbed. It is not downstream of the image. Only
`compiled` is fresh work, which is why a workload can show a mediocre
`aot_hit_pct` and still compile very little.

`ic_shapes_raced` is the intersection of the served-by-AOT and
served-elsewhere shape sets unioned across processes, so a shape lands
there when one process got it from the image and another compiled it.
Raced shapes are counted as served and do not depress `coverage_pct`;
the number is reported so that a large one is visible rather than
silent.
