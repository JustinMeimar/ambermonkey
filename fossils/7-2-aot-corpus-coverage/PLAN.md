
AOT corpus coverage under held-out browser workloads. Each firefox
process that touches the AOT image writes one coverage JSON at
shutdown (js/src/jit/AOTCoverage.cpp). A run collects one file
per pid; the reducer folds them into a single row of static +
dynamic coverage figures.

Three evaluation populations:

- **tp6_test**: the eight tp6 sites 7-1 holds out (`test.txt`). One
  raptor variant per site, so per-site coverage is directly
  observable. The figures fold the eight variants into a median plus
  min-max range so a single low-coverage site cannot vanish into a
  pooled aggregate.
- **speedometer3**: Speedometer 3.1, unseen interactive-web workloads.
- **jetstream3**: JetStream 3.0, unseen language-runtime and
  WebAssembly workloads (domain shift).

The image under test is the frozen tp6_train union built by 7-1. No
identity from any of these three populations contributed to the pack.

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

All tables are fed from the same `coverage` analysis fold. Fossil
hands each script the cross-variant fold on stdin and the script
writes a sibling `.json` for the typst `json-table` loader. Metric
names are unqualified because the table title already carries the
artifact context; cells are the mean across iterations only (variance
was zero to display precision).

Three tables cover the three artifact populations with the
three-population column layout (tp6-Test aggregate, Speedometer 3.1,
JetStream 3.0). tp6-Test cells report the median across the eight
site variants with the min-max range in brackets; suite cells are
scalar means.

- `baseline-function-table` — corpus size, installed, utilization,
  AOT hit rate.
- `baseline-interpreter-table` — corpus size (always 1, hardcoded in
  the figure script since AOTCoverage.cpp does not enumerate the
  interp blob kind) and number of AOT-using processes (`n_procs`).
  Loaded-in-N-procs is the strongest statement the current plumbing
  supports.
- `ic-table` — corpus size, attached, utilization, total attaches,
  AOT hit rate. Only weighted metrics; the unweighted identity-
  coverage fraction (`workload.coverage_pct` in the reducer) is
  still computed but not surfaced because AOT hit rate already
  answers the "how well does the corpus serve this workload"
  question and the two numbers together invited misinterpretation.

One fourth table surfaces the per-site tp6_test detail behind the
aggregate cell:

- `ic-per-site-tp6-test` — eight rows, one per tp6_test site, with
  attached / utilization / total attaches / AOT hit rate columns. The
  paper cites this alongside the aggregate ic-table so a reviewer can
  see every site rather than trust a median.

### Reading the IC columns

An IC attach request resolves in one of three ways -- AOT image, per-
zone stub cache, or fresh compile. The zone-cache bucket is folded
silently into the request total; the table reports only the AOT-vs-
total ratio because the zone bucket kept generating "wait, what is
that?" questions without carrying its weight. The raw count is still
in the reducer output for anyone debugging.

`ic_shapes_raced` is the intersection of the served-by-AOT and
served-elsewhere shape sets unioned across processes, so a shape lands
there when one process got it from the image and another compiled it.
Raced shapes are counted as served and do not depress `coverage_pct`;
the number is reported so that a large one is visible rather than
silent.
