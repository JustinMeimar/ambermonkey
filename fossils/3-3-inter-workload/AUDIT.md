# 3-3 measurement audit and rerun plan

The current figure should not yet be interpreted as site-code-only overlap.
Parent-process records are excluded, but the content-process stream still mixes
page code with self-hosted and potentially privileged browser code. The IC entry
accounting also needs stronger lifecycle guarantees. The following work should
be completed before collecting the final data.

## 1. Preserve raw logs for an audit run

`fossil.toml` currently runs `emit_ranks.py` and immediately removes the
instrumentation directory. The reduced JSON retains body-level counters but
discards the provenance and event ordering needed to audit source classes,
runtime shutdowns, and lost or duplicated IC entries.

For at least one audit collection:

- retain every per-process JSONL file;
- record the number and role of participating processes;
- report `entries-flush` counts and reasons per process/runtime;
- retain script, site, and source-class joins in the reduced output; and
- run the general instrumentation reconciler in addition to the fossil-specific
  reducer.

Raw logs may be deleted after the audit artifacts and validation summaries have
been reviewed. Final production runs may return to compact output once the
reducer emits enough diagnostics to make failures visible.

## 2. Exclude self-hosted code through `script_local_id`

SpiderMonkey already marks self-hosted scripts. `script-create` records
`script_local_id` and `source_class`, and `ic-instance-attach` records the same
classification directly. The current reducer drops these fields and aggregates
only by artifact identity.

The reducer should first build a per-process mapping from `script_local_id` to
`source_class`, then use it for every artifact path:

- Baseline compile events join through `script_local_id`;
- IC attach events use their direct source class and should agree with the
  script mapping;
- IC detach events join through `script_local_id`; and
- shutdown `entries-flush` script rows join through `script_local_id` before
  their nested IC entries are counted.

The site-code analysis should accept only the intended source class and report
excluded counts and weights. In particular, it should report the number of
self-hosted Baseline identities, IC identities, compile requests, and IC entries
removed from each workload. A sensitivity table comparing unfiltered and
self-hosted-excluded coverage should accompany the audit.

## 3. Add accurate privileged/browser-code classification

The current `ClassifyScript` implementation identifies self-hosted scripts but
labels every other script as `guest`. Its comment says Chrome code will be
reclassified later from `source_id`, but the 3-3 pipeline performs no such
reclassification. Consequently, content-process-only is not equivalent to
page-code-only: frame scripts, browser machinery, extensions, or other
privileged scripts may enter the site bucket.

Instrumentation should expose an authoritative guest-versus-privileged signal,
preferably derived from the script realm's principals at event emission. If
that cannot be added without violating SpiderMonkey's embedding boundary, the
Gecko-side harness must emit or retain sufficient source metadata for an exact
join. A filename hash without a maintained classification table is not enough.

The reducer should fail closed on `unknown` source classes rather than silently
treating them as guest. It should emit per-class totals for `guest`,
`self-hosted`, `chrome`/privileged, and unknown. The comment in `fossil.toml`
claiming browser Chrome is discarded should only be restored once this is
verified end to end.

## 4. Make IC lifetime accounting exact

The intended frequency is the sum of every optimized IC stub's lifetime entry
count. The present scheme adds detach-time counts for removed stubs to shutdown
snapshots for live stubs, but several paths need correction or validation:

- GC purge currently discards optimized stubs without harvesting their entry
  counts;
- script finalization cannot recover counts after the stub space has been
  swept;
- both the XPCOM shutdown observer and `JSRuntime::destroyRuntime` can request a
  terminal flush, but there is no shared per-runtime once guard; and
- the reducer accepts and sums every flush rather than enforcing exactly one
  terminal contribution per runtime and stub lifetime.

The instrumentation should harvest counts before every destructive unlink or
purge. Terminal snapshots should carry a runtime identity and be idempotent per
runtime. The reducer should reject duplicate terminal snapshots, missing
runtime snapshots, and entered bodies without a corresponding attachment.

A preserved-log test should exercise transition, fold, weak sweep, GC purge,
script destruction, worker/runtime shutdown, and normal content-process
shutdown. For each synthetic stub lifetime, its final reduced count must equal
the known number of entries exactly once.

## 5. Rerun the eight sites with a blank control

After the provenance and lifetime fixes, rerun the same first eight alphabetical
TP6 sites:

1. amazon
2. bing-search
3. buzzfeed
4. cnn
5. ebay
6. espn
7. expedia
8. facebook

Collect an otherwise identical `about:blank` control using the same binary,
preferences, profile lifecycle, cold/warm mode, browser-cycle count, dwell time,
and instrumentation settings. A minimal replayed page may be useful as a second
control, but it must not substitute for `about:blank`.

Report, per workload and source class:

- distinct Baseline and IC identities;
- Baseline compile requests and IC entry weight;
- intersection with the blank control;
- fraction of workload weight covered by the blank control;
- the eight-way intersection before and after filtering; and
- pairwise coverage before and after filtering.

The blank intersection is a diagnostic, not something to subtract blindly.
Sites legitimately exercise common builtins and generic CacheIR bodies, so an
artifact seen in the control may still be real transferable workload demand.
The control's purpose is to quantify the automatic floor and verify that source
classification removes browser activity without erasing legitimate shared JIT
work.

Only after these checks should the final coverage figure be regenerated and its
high IC-coverage region interpreted as workload-independent sharing.
