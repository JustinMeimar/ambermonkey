This fossil measures the end-to-end performance of the deployable
AmberMonkey corpus. The corpus is frozen before measurement and held out from
both evaluation workloads:

    /home/justin/spidermonkey/ambermonkey/corpi/default-corpus-release

It contains the TP6-derived IC corpus, deterministic self-hosted Baseline
functions, and the Baseline interpreter. It deliberately does not contain
guest Baseline functions from Speedometer 3 or JetStream 3. Adding artifacts
recorded from either evaluation workload would turn this into an oracle
experiment; oracle measurements belong in 7-4-indirection-overhead.

## Question and matrix

Under a restricted code-generation policy, how much performance does the
shipped, held-out corpus recover over interpretation, and how close does it
come to the default JIT configuration?

Run exactly these three policies on Speedometer 3 and JetStream 3:

| Policy | Configuration | Purpose |
| --- | --- | --- |
| `interp-only` | `JIT_OPTION_disableJitBackend=true` | Restricted lower bound |
| `am-strict` | `JIT_OPTION_aotOnly=true` | Shipped-corpus AmberMonkey result |
| `default` | ordinary JIT tiers | Full-JIT upper bound |

`am-strict` implies `useAOTImage` and disables Ion. A Baseline-function miss
remains in the Baseline interpreter and an IC miss uses the shared generic
fallback; it must never silently compile. `interp-only` also removes the
runtime-generated Baseline interpreter.

Only `am-strict` runs the AOT-capable, bootstrapped Firefox binary. `default`
and `interp-only` run the ordinary non-AOT release binary. Native regexp and
Wasm compilation are disabled in every row so their independent code
generators do not confound the Baseline comparison. The default row therefore
means the default JavaScript tier policy under those two matched controls. Ion
is set through the Firefox preference, not only `JIT_OPTION_ion`, because
`LoadStartupJSPrefs` overwrites the constructor-time environment value. The
harness removes inherited AOT/JIT environment options before every run.
It removes any inherited `MOZ_HEADLESS` value and then explicitly passes
`MOZ_HEADLESS=1` through Raptor. Firefox treats any present value, including
`0`, as enabling headless mode, so `1` is used to make the intent clear.

Each Fossil iteration is one fresh browser with one browser cycle and one page
cycle. Five independent browser runs per policy are the default. Raptor page
cycles are not treated as independent samples.

## Outputs

The analysis retains the suite score for every browser run, Speedometer
workload totals, JetStream geometric subtest scores, and the exact policy,
workload, controls, and source commit.

`figures/performance.py` plots each suite relative to its own interpreter-only
lower bound and reports log-space 95% confidence intervals over browser runs.
The main quantities are `am-strict / interp-only` (recovery) and
`am-strict / default` (fraction of default performance retained). The figure
requires all six variants, one source commit, and at least two samples per
variant.

## Prerequisite and collection

Pack `default-corpus-release` into
`build-browser-release-aot/js/src/jit/aot/AOTImage.inc`, touch
`js/src/jit/aot/AOTImageIncbin.cpp`, and rebuild `binaries` as documented by
7-1-aot-corpus-collector. The corpus and binary are build-coupled; do not
reuse a corpus after an AOT schema, slot-table, or code-generation change.

Then collect and render with:

    fossil --project ambermonkey bury 7-3-ambermonkey-perf
    fossil --project ambermonkey analyze 7-3-ambermonkey-perf \
      --analysis performance
    fossil --project ambermonkey figure 7-3-ambermonkey-perf \
      --figure performance

Before using a result in the paper, pair it with 7-2's coverage numbers and
verify the built image was produced from the frozen corpus. A result from an
empty or stale image is not an AmberMonkey measurement.
