# 3-3-inter-workload — Implementation Notes

## Question the fossil answers

For a set of web workloads, how much of each workload's JIT-compiled
IC-body inventory is shared with the others, and how much of each
workload's runtime execution weight lands on bodies that another
workload also compiled?

Two answers per pair (i, j), rendered in one heatmap:

- **Static Coverage** (lower triangle, symmetric): fraction of the
  union of executed IC-body identities that is common.
    `static[i][j] = |set_i ∩ set_j| / |set_i ∪ set_j|`
  Was called "Jaccard" in earlier iterations; renamed for label
  symmetry with the dynamic axis.
- **Dynamic Coverage** (upper triangle, asymmetric): fraction of
  workload j's execution weight that lands on bodies also present
  in workload i's set.
    `dynamic[i][j] = Σ_{k ∈ freqs_j ∧ k ∈ set_i} freqs_j[k]
                    / Σ_{k ∈ freqs_j} freqs_j[k]`
- Diagonal: executed-body count for that workload.

## Data source: SpiderMonkey Phase-3 instrumentation

Firefox is instrumented via a per-process JSONL sink at
`js/src/jit/Instr.{h,cpp}`. Enabled by the env vars:

- `JS_INSTR=all` (or a comma-set of channel names) turns instrumentation
  on. `all` enables every channel.
- `JS_INSTR_DIR=<dir>` output directory; one file per process named
  `<proc>.<pid>.jsonl` where `<proc>` is one of `parent`, `content`,
  `gpu`, `rdd`, `socket`, `gmplugin`, ...
- `JS_INSTR_MODE=structural|demand`. Structural leaves emitted code bytes
  clean. This fossil uses demand mode, which adds a per-JitScript entry-counter
  bump to the compiled Baseline prologue.
- `JS_INSTR_RUN_ID=<opaque>` recorded in the run-header event.

Channels used here:

- `InstrCh_IC` — emits `ic-body-emit`, `ic-instance-attach`,
  `ic-instance-detach`.
- `InstrCh_Demand` — gates `entries-flush` (per-live-stub snapshot
  with `enteredCount()`). Not to be confused with `JS_INSTR_MODE=demand`.
- `InstrCh_Snapshot` — gates `snapshot-marker` / `snapshot-*` events
  emitted around `entries-flush`.
- `InstrCh_Lifecycle` — gates `runtime-shutdown`, `pool-*`, `jitcode-*`.

Every emitted line carries a common header: `v`, `kind`, `seq`,
`ts_us`, `pid`, `proc`, `tid`, `rt`.

## Event kinds consumed by this fossil

- `ic-instance-attach` — one per time a compiled stub is wired into
  an IC chain. Carries `ic_body_id` (SHA-1 of the CacheIR source),
  `engine`, `source_class`. Emitted from the fallback path when a
  new stub is compiled.
- `ic-instance-detach` — one per time a stub is removed from a chain
  (transition, fold, overflow, script destroy, GC purge, etc.).
  Carries `ic_body_id`, `entered_count`, `is_fallback`.
- `entries-flush` — snapshot of every currently-live IC stub across
  every JitScript in every zone of a runtime. Carries `reason`, per-
  script rows with `ic_entries: [{site_local_id, ic_body_id,
  entered_count, is_fallback}]`.
- `baseline-entries-retire` — final compiled-Baseline prologue-entry count for
  a JitScript destroyed before terminal shutdown. The terminal
  `entries-flush` supplies the corresponding count for scripts still live at
  shutdown.

`enteredCount()` on an ICStub is bumped unconditionally by the emitted
stub code at `BaselineCacheIRCompiler.cpp:235-236`; it does not depend
on `JS_INSTR_MODE`.

## Getting entered_count at runtime shutdown

The naïve pipeline (attach → detach → sum entered_count) systematically
under-counts hot bodies: on a one-shot browsertime page load, most hot
stubs never detach, so their `entered_count` is never sampled. Only
~13% of the attached population was captured that way.

The fix: emit an `entries-flush` at process shutdown so every stub
alive at that moment contributes its final `enteredCount()`.

Two C++ hooks added:

### 1. `InstrSnapshot::AtRuntimeShutdown` (`js/src/jit/InstrSnapshot.{h,cpp}`)

Refactored `CollectAndEmitEntries` to take `JSRuntime*` (was `JSContext*`
via `cx->runtime()`). Exposed a public entry point:

```cpp
void InstrSnapshot::AtRuntimeShutdown(JSRuntime* rt) {
  CollectAndEmitEntries(rt, "runtime-shutdown");
}
```

Called from `JSInstr::RuntimeShutdown` (`Instr.cpp`) BEFORE the
lifecycle gate so it fires regardless of channel mask, as long as
`InstrCh_Demand` is on (self-gated inside CollectAndEmitEntries).

`RuntimeShutdown` itself is called from `JSRuntime::destroyRuntime`
(`vm/Runtime.cpp:208`), which is invoked before GC/script teardown, so
IC stubs are all still live and `enteredCount()` is authoritative.

### 2. `JitInstrReporter` observer hooks (`js/xpconnect/src/JitInstrReporter.{h,cpp}`)

`JSRuntime::destroyRuntime` is called reliably for helper runtimes
(rt=2, rt=3 etc. that hold no scripts) but not for the main runtime in
processes that get torn down abruptly. Browsertime's teardown reaches
XPCOM shutdown observers before it reaches destroyRuntime, so we
piggyback on that.

`JitInstrReporter` was already registered per-process as an
`nsIMemoryReporter` from `XPCJSRuntime::Initialize` (both parent and
content). Extended it to also implement `nsIObserver` and register for
two topics:

- `xpcom-shutdown` — fires in parent processes.
- `content-child-shutdown` — fires in content processes (from
  `ContentChild::ShutdownInternal` in `dom/ipc/ContentChild.cpp:3173`).
  Content processes never see `xpcom-shutdown`; they need this topic.

On first fire from either topic, the observer resolves
`XPCJSContext::Get()->Context()` → `JS_GetRuntime(cx)` → calls
`InstrSnapshot::AtRuntimeShutdown(rt)`, then removes itself from
both topics so a single process cannot double-flush.

Registration order in `Register()` matters: add observer while we
still hold a `RefPtr<JitInstrReporter>`, then hand the ref to
`RegisterStrongMemoryReporter` via
`RefPtr<nsIMemoryReporter>(reporter).forget()` (the base-class upcast
is required because `RegisterStrongMemoryReporter` wants
`already_AddRefed<nsIMemoryReporter>`).

Result: every JS-running process (parent + content) emits one
`entries-flush` at shutdown with real `enteredCount()` for every
still-live stub. ~35-49% of the attach set is captured this way; the
remainder is captured from `ic-instance-detach.entered_count` (see
next section).

## Reduction (`scripts/emit_ranks.py`)

Reads per-process JSONL files from `$JS_INSTR_DIR`. Splits by process
type using the filename prefix (`content.PID.jsonl` vs
`parent.PID.jsonl`). Ignores `gpu`, `rdd`, `socket`, etc.

Per process type, produces:

- `attaches`: `{ic_body_id : count}` — total `ic-instance-attach`
  events for each body. Cheap inventory signal.
- `entered`: `{ic_body_id : count}` — real execution counts,
  composed from two disjoint sources:
    - Sum of `ic-instance-detach.entered_count` for stubs that were
      unplugged during the run (they're gone by shutdown, so the
      flush cannot see them).
    - Sum of `entries-flush.ic_entries[].entered_count` from the
      shutdown flush (still-live stubs at shutdown; the flush is
      authoritative for them).
  These populations are disjoint: a stub is either alive at shutdown
  (in the flush) or gone (in a detach event), never both. Summing is
  exact for total lifetime executions per body.

Also emits `baseline.{content|parent}.compiles` and `.entered`. Compilation
events define the static semantic-identity set. Retired-script events and the
terminal live-script snapshot provide the function-entry weights used by
panel (b).

## Analysis (`analyses/ic_set.py`)

Two filters applied to make the two heatmap triangles comparable:

### Content-only

Parent-process ICs (browser chrome / frame scripts / telemetry) load
identically in every session and form a ~700-body constant floor. If
included, they inflate every pairwise intersection toward 1 and swamp
the site-JS overlap signal we're after. The AOT-sharing story around
parent-chrome ICs is real but orthogonal and belongs in a separate
analysis.

### Executed-only

An IC stub is compiled when the fallback fires on the site's first
hit. `enteredCount()` counts stub entries *after* attach. On a short
browsertime page load:

- Many sites fire exactly once during setup (module-level code,
  event init, one-time DOM queries). Fallback attaches a stub; the
  site is never touched again. Stub sits at `enteredCount=0`.
- IC chains evolve as new input shapes arrive. Older stubs go cold.
- No user interaction (no scrolling, no clicks, no repeating
  intervals) so nothing warms up cold stubs.

Filtering the static set to bodies with `entered_count > 0` puts both
triangles over the same population. Without it, the static Jaccard
counts many cold-attached bodies that never contribute to dynamic
weight, generating apparent paradoxes like `Jaccard(imdb, fandom) =
0.36` alongside `Coverage(fandom → imdb) = 1.00` (imdb's 447 attached
bodies include 300+ that never executed; the 143 that did execute are
almost entirely in fandom's set).

Output shape (string-valued so `fossil_figures.load_stdin` carries
them as `Metric.tag`):

```
{
  "hashes": "HEX,HEX,...",              # executed bodies (static set)
  "freqs":  "HEX=n;HEX=n;...",          # execution-weighted map
  "count":  <int>,
  "total_entered": <int>
}
```

## Collection (`fossil.toml`)

One variant per site. Same 8-site set as `3-2-intra-workload` so
per-site CDF shape (3-2) and per-pair overlap (3-3) can be cross-
referenced trivially:

- amazon, bing, cnn, example, fandom, imdb, stackoverflow, wikipedia
- (reddit was dropped: login/geoblock caused it to render nothing;
  its content IC set was identical to example.com's.)

Each variant expands to:

```
D=$(mktemp -d /tmp/amber-3-3.XXXXXX)
export JS_INSTR=all JS_INSTR_DIR=$D JS_INSTR_MODE=structural \
       JS_INSTR_RUN_ID=$(basename $D)
cd $FIREFOX && MOZ_DISABLE_CONTENT_SANDBOX=1 MOZCONFIG=... \
  ./mach browsertime --headless -n 1 -b firefox \
    --firefox.binaryPath $BIN_RELEASE <URL> 1>&2
python3 scripts/emit_ranks.py "$D" && rm -rf "$D"
```

No wrapper script. No signal handling. No PID scanning. No timing
races. Firefox's own XPCOM shutdown pipeline drives the flush.

## Figure (`figures/ic_jaccard.py`)

Ported from `frostmonkey/fossils/ic-frequency/figures/jaccard_combined.py`.

- Blues colormap on lower triangle for static coverage; OrRd on upper
  for dynamic. Norm ranges auto-scaled to the off-diagonal min/max
  per triangle to bring out variance.
- Diagonal: bold executed-body count on grey.
- Stacked colorbars on the right labelled "Static Coverage" and
  "Dynamic Coverage".
- Title: `Static (◣) / Dynamic (◥) Coverage    |U|=… |⋂|=…`

## Interpretation gotchas

1. **Static overlap is spread out; dynamic tends toward 1.** Even
   with executed-only filtering, dynamic coverage of small-into-large
   pairs saturates at ~1.00 because IC execution weight is heavily
   power-law and the top-hot bodies are essentially universal. Large
   corpora always contain small corpora's hot core.
2. **The interesting dynamic values are large-into-small.** E.g. a
   big workload's execution has some site-specific bodies that a
   small workload's set won't contain; those cells show meaningful
   drops (0.30-0.77 in the current figure).
3. **Attach-only bodies are silent.** A body attached but never
   executed contributes nothing to either triangle under the current
   filters. That's the right call for the "shared JIT work" story
   but hides the compile-time inventory question. If you want the
   compile-inventory question, remove the executed-only filter in
   `ic_set.py` and expect the paradoxes to reappear — they aren't
   bugs, they're the mismatch between attach-set and execute-set
   populations.
4. **The n-way intersection (`|⋂|` in the title) is the count of
   bodies present in EVERY variant's executed set.** In the current
   data (`|⋂|=134`), this is the AOT-sharing lower bound: a
   precompiled corpus of ~134 bodies would serve some fraction of
   every workload's hot path. Coverage numbers say what fraction.
5. **Longer page dwell would grow the executed set.** browsertime's
   "load event + immediate close" cycle catches attach fan-out but
   misses steady-state re-execution. A future variant with
   `--pageCompleteWaitTime 15000` or synthetic scroll/interaction
   would characterize warmer steady-state behavior.
