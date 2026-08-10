# Minimal AmberMonkey performance comparison

## Objective

Measure the net performance effect of the AmberMonkey implementation that
exists on the pinned Firefox revision. Do not introduce switches for value
mirrors, native linking, call lowering, or other internal mechanisms.

The experiment has exactly two endpoints:

1. `runtime`: the AOT-enabled Firefox binary generates Baseline code at
   runtime.
2. `amber`: the same binary runs with `JIT_OPTION_aotOnly=true` and loads an
   oracle AOT image prepared for the measured workloads.

Both endpoints disable Ion, Wasm, and native RegExp compilation. The treatment
axis is therefore the complete production AmberMonkey path versus conventional
runtime Baseline generation under the same tier policy.

## Estimand and permitted claim

For each workload, estimate:

```text
score_ratio  = amber_score / runtime_score
cycle_ratio  = amber_cycles / runtime_cycles
```

This supports a claim of the following form:

> On an oracle workload corpus, production AmberMonkey changed end-to-end
> benchmark score by X% and Firefox-lifetime user-mode cycles by Y% relative to
> runtime-generated Baseline code.

This is a net implementation result. It includes indirection, AOT image lookup
and installation, code-layout effects, and runtime compilation work avoided by
AmberMonkey. It must not be described as the cycle cost of an individual table
access or as a decomposition of the AOT indirection mechanism.

## Scope

- Speedometer 3: five page cycles per browser invocation.
- JetStream 3: one page cycle per browser invocation.
- Ten paired blocks per suite.
- One AOT-enabled opt-nodebug Firefox build for both endpoints.
- One immutable oracle image containing the union of artifacts observed while
  recording both suites.
- All preparation, execution, records, analysis, and figures live in this
  fossil under the AmberMonkey repository.
- No Firefox source patch is required for this minimal experiment.

Fine-grained per-slot attribution is a separate experiment. It will require
instrumentation derived from `AOTIndirectionTable` and is not part of this
fossil.

## Preparation

Add a fossil-owned `scripts/prepare_oracle.py` that performs these steps and
writes `prepared/manifest.json`:

1. Resolve and record the Firefox revision, AmberMonkey revision, mozconfig,
   compiler version, linker version, CPU model, kernel, and Raptor revision.
2. Build the AOT-enabled opt-nodebug browser once.
3. Record Speedometer 3 and JetStream 3 into separate temporary corpus
   directories using the same preferences as the measurement.
4. Form a deterministic union of the two directories. Fail on conflicting
   artifact keys rather than selecting one silently.
5. Pack and embed the union as one AOT image.
6. Rebuild only what is required to place that image in the browser.
7. Preserve the complete browser installation used by both endpoints under
   `prepared/browser/`.
8. Run one untimed smoke pass of each suite with both
   `JIT_OPTION_aotOnly=true` and `JIT_OPTION_aotEnforce=true`. Preparation fails
   on an AOT miss, stale image, fallback, or crash.
9. Hash the preserved browser, embedded image, and corpus manifest. Record the
   hashes in `prepared/manifest.json`.

Preparation is separate from measurement. Recording, packing, rebuilding, and
validation never run inside a measured block.

## Machine preflight

Add `scripts/preflight.py`. It emits JSON and exits unsuccessfully unless all
of the following hold:

- logical CPU 2 is online;
- the experiment can bind the complete Firefox process tree to CPU 2;
- logical CPU 3 is offline, matching the paper's machine setup;
- the CPU-frequency governor for CPU 2 is `performance`;
- boost is disabled;
- `perf` can schedule `cycles:u` and `ref-cycles:u` together without
  multiplexing;
- the prepared browser and image hashes match `prepared/manifest.json`;
- no Firefox process from an earlier block remains alive.

The preflight record is part of the fossil output. Do not repair machine state
automatically.

## Measurement driver

Add `scripts/run_block.py` and expose two fossil variants, `speedometer3` and
`jetstream3`. Set `default_iterations = 10`. One fossil iteration is one paired
block for the selected suite.

For each block:

1. Derive and record a random seed.
2. Randomize the order of `runtime` and `amber`.
3. Give each endpoint a fresh profile and temporary directory.
4. Launch the preserved Firefox through a wrapper that binds Firefox and all
   descendants to CPU 2.
5. Place only the Firefox process tree under:

   ```text
   perf stat -j -e {cycles:u,ref-cycles:u}
   ```

   Raptor, Python, Node, and preparation processes are outside the counter
   boundary. The counter boundary begins at Firefox launch and ends when that
   Firefox process tree exits.
6. Run Raptor headlessly with one browser cycle. The Speedometer Raptor command
   requests five page cycles; JetStream requests one.
7. Require a normal Raptor exit, valid score output, valid non-multiplexed PMU
   counts, and no surviving Firefox processes.

Shared settings for both endpoints:

```text
javascript.options.ion=false
javascript.options.wasm=false
javascript.options.native_regexp=false
MOZ_DISABLE_CONTENT_SANDBOX=1
```

The `amber` endpoint additionally sets:

```text
JIT_OPTION_aotOnly=true
JIT_OPTION_aotEnforce=true
```

The `runtime` endpoint sets neither AOT option. It still uses the identical
prepared browser, so build-to-build variation is excluded.

## Raw JSON contract

Each block prints one JSON object for Fossil to record:

```json
{
  "schema_version": 1,
  "suite": "speedometer3",
  "block": 0,
  "seed": 1234,
  "order": ["amber", "runtime"],
  "runs": {
    "runtime": {
      "raptor": {},
      "score": 0.0,
      "cycles_user": 0,
      "ref_cycles_user": 0,
      "perf_running_percent": 100.0,
      "exit_status": 0
    },
    "amber": {
      "raptor": {},
      "score": 0.0,
      "cycles_user": 0,
      "ref_cycles_user": 0,
      "perf_running_percent": 100.0,
      "exit_status": 0
    }
  },
  "prepared_manifest_sha256": "..."
}
```

Keep the complete Raptor result object in `raptor`; do not retain only the
headline score. Store the raw `perf stat` JSON alongside the Fossil record.
Reject a block rather than substituting zero, omitting an event, or accepting a
partial result.

## Analysis and JSON table

Replace the existing parser with `analyses/parse_overhead.py` that preserves
the paired block structure. It must produce:

- one row per suite, block, and endpoint containing raw score and PMU counts;
- one paired row per suite and block containing score and cycle ratios;
- aggregate geometric-mean ratios for each suite;
- two-sided 95% paired bootstrap confidence intervals resampling whole blocks;
- the number of accepted and rejected blocks;
- manifest hashes and the fixed event set.

The figure script writes both a figure and its source table. The source table
is the primary artifact:

```text
figures/overhead-bars.json
```

Its top-level shape is:

```json
{
  "schema_version": 1,
  "estimand": "production AmberMonkey versus runtime-generated Baseline",
  "events": ["cycles:u", "ref-cycles:u"],
  "suites": {},
  "rows": [],
  "paired_rows": []
}
```

Use score as the primary result and `cycles:u` as the secondary corroborating
metric. Report `ref-cycles:u` as a frequency-control diagnostic. Do not add PMU
events after data collection begins.

## Acceptance criteria

The fossil is complete only when:

- all ten paired blocks for both suites pass;
- every AmberMonkey run uses the same validated oracle image and reports zero
  AOT misses;
- every endpoint uses the same preserved browser installation;
- every PMU event reports 100% running time;
- the raw records can regenerate the JSON table and figure without access to
  temporary files;
- rerunning the analysis is deterministic;
- the paper reports the result as a net AmberMonkey implementation comparison,
  not isolated indirection overhead.

If failures require replacement runs, preserve the failed records and append
replacement blocks with new block identifiers. Never overwrite an observed
result.
