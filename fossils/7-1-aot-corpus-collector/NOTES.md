# 7-aot-corpus-collector — Implementation Notes

## Question the fossil answers

What AOT artifact corpus does the release browser compile over the
tp6_train partition, how big is it, and how much of a held-out training
site does it already cover? The run is also the corpus *producer*: the
recorded artifacts are the input to the packed AOT image.

## Selection policy

The recorder observes the compile stream, not the execution stream. It
fires when baseline or an IC stub is compiled and writes the artifact;
nothing counts entries. There is no frequency to weight by.

The training partition is frozen alphabetically: `train.txt` lists the
first 24 tp6 sites, `test.txt` the last 8. Both files are checked in.
All 32 sites are recorded; the extra 8 held-out recordings are the
input to 7-2's tp6_test coverage variants, not to the packer.

**The corpus is the union of every supported IC-body identity observed
in the training sites.** No prevalence threshold, no request-count
weighting, no byte budget. Prior data motivates the two policy shapes
that remain:

- Baseline functions are dropped as a class, via `--exclude-kind blfun`.
  7-2 measured a tp6-derived corpus against Speedometer3: recorded
  baseline functions served 4.9% of baseline compile requests and 65%
  of the packed baseline corpus was never installed at all. The
  leave-one-site-out table this fossil now emits reproduces the same
  finding at training-set granularity.

- Self-hosted baseline functions are the one baseline set that
  transfers, and they enter the corpus in whole via `--self-hosted`,
  exempt from `--exclude-kind`. Their source is fixed at build time, so
  the training corpus does not gate them.

Within-kind selection is the union. Artifact names *are* identity
hashes, files are opened `O_EXCL`, and `EEXIST` is treated as success,
so a training subset union is the union of the subset's filenames.

Representability, not prevalence, is what rejects a body. Bodies whose
dependency forms the classifier cannot represent are dropped at pack
time. Their count and rejection reasons are a separate diagnostic; they
are not a selection decision.

For ICs the identity covers `cacheKind`, the CacheIR bytes and the
field *types*, not the field values. Two sites compiling the same
CacheIR program against different shapes produce one artifact. That is
also why they transfer: the identity is shape-free, so a program some
other workload compiles resolves to an artifact this one already
recorded.

`scripts/emit_composition.py` writes the union counts, the
singleton/recurrent split, and a threshold sweep as a diagnostic table.
The paper cites the sweep to show that the singleton tail is small
enough that pruning is unnecessary; nothing downstream in the pipeline
consumes a threshold.

## Recording

`JIT_OPTION_aotRecordDir` is read in `JitOptions.cpp`, and a non-empty
value implies both baseline and blinterp capture. Raptor passes it via
`--setenv`, which becomes browsertime's `--firefox.env`, so every
content process inherits it.

`useAOTImage` stays off. Every process compiles normally and the
recorder sees the whole compile stream; a run with the image installed
would skip the compiles it satisfies and under-record.

`MOZ_DISABLE_CONTENT_SANDBOX=1` is required or content processes cannot
write the dump.

### Self-hosted functions come from the shell, not from tp6

There is no browser trigger for the exhaustive self-hosted sweep.
`aotRecordDir` is the only AOT option read from the environment; the
sweep is a shell flag, `--aot-record-self-hosted`, which requires
`--aot-record=DIR` and runs before any file or `-e` argument. So a
raptor run only ever records the self-hosted functions tp6 happens to
call, demand-driven through the same baseline path as page script.

That is not what we want. Speedometer3 installed 47 self-hosted baseline
functions out of a corpus recorded from an entirely different workload,
which is the signal that this set transfers where page script does not:
it ships with the engine, so every workload runs the same bytes. Record
it exhaustively rather than hoping the recording workload reached it.

    build-shell-release-aot/dist/bin/js \
      --spectre-mitigations=on \
      --aot-record=/tmp/amber-aot-selfhosted \
      --aot-record-self-hosted \
      -e 'quit(0);'

Yielding 236 baseline functions in 434 KB, and no IC stubs, since the
sweep delazifies and compiles but never executes.

Pass that dir to `soft_intersection.py --self-hosted`. Its baseline
functions are copied in whole, exempt from `--budget` and from
`--exclude-kind`; its IC stubs are ignored, since the sites are the IC
evidence.

### Why the shell can stand in for the browser

`--spectre-mitigations=on` is the whole trick and it is not optional.
Measured 2026-08-06: of the seven fingerprinted `JitOptions`, the shell
and the browser disagree on exactly two, the object and string spectre
mitigations, which the shell defaults off and the browser turns on by
pref. Those bits change emitted code, so a default shell recording
produces blobs the browser will not install. With the flag the shell's
`configuration.aotb` and `interp.aotb` are byte-identical to the
browser's.

Artifact identity then transfers. The baseline identity hash is over
bytecode, script and function flags, slot counts and gcthing kinds, with
no addresses in it, and both binaries carry the same self-host stencil.
Checked directly: a bare `about:blank` browser start recorded 1039
baseline functions, 70 of which the shell's self-hosted sweep also
produced, and all 70 were byte-identical.

So there is no reason to teach the browser to run the sweep. The
alternative would be a new environment-triggered option firing in every
content process, against a one-flag shell invocation that is already
exhaustive and now verified equivalent. The `configuration.aotb`
comparison in the selector is what keeps this honest: it hard-fails if
the shell and the sites ever drift apart again.

## Why raptor rather than a hand-rolled proxy

`-t browsertime-tp6` runs all 32 subtests of
`testing/raptor/raptor/tests/tp6/desktop/browsertime-tp6.toml` in one
invocation. Raptor owns the mitmdump lifecycle and fetches the pagesets
from in-tree tooltool manifests, all public. An earlier version of this
fossil drove mitmdump directly against the mitm5 recordings an AWSY run
had left in the objdir; that reimplemented mozproxy, including a
workaround for its readiness bug, and pinned the workload to a stale
pageset generation.

Note that this is a *different* workload from 3-2 and 3-3, which hit
live sites rather than replay.

## Packing

`mach jit-aot build` does not apply: it is hardcoded to the stage-1
shell and `objdir/aot-record`. Pack the selected corpus, never the raw
recording dir, which still holds every per-site baseline function and
every held-out site's IC bodies:

    python3 scripts/select_corpus.py \
      /tmp/amber-aot-corpus /tmp/amber-aot-selected \
      --sites train.txt \
      --exclude-kind blfun \
      --self-hosted /tmp/amber-aot-selfhosted

    python3 js/src/jit/aot/PackAOTImage.py \
      --schema js/src/jit/AOTImageSchema.yaml \
      /tmp/amber-aot-selected \
      build-browser-release-aot/js/src/jit/aot/AOTImage.inc
    touch js/src/jit/aot/AOTImageIncbin.cpp
    ./mach build binaries

`--sites train.txt` restricts indexing to the 24 training subdirs. Any
held-out site's per-site subdir under `@CORPUS` is ignored, so recording
tp6_test never contaminates the pack.

`interp.aotb` and `configuration.aotb` are singletons rather than hashed
identities; the installer resolves the configuration with a unique
lookup, so exactly one of each belongs in the dir. The selector picks
one of each and verifies the training sites agree on the configuration.

## Tables

`emit_composition.py` writes the paper's `7-1-selection.json`: union
counts, singleton/recurrent split, and the diagnostic threshold sweep.
`loso.py` writes the paper's leave-one-site-out coverage table over the
24 training sites, for both IC bodies and baseline functions.
`corpus_tables.py` answers what a chosen corpus is made of and how two
candidates differ as sets; it is invoked ad hoc for ablations, not from
`fossil bury`.

    python3 scripts/corpus_tables.py \
      full=/path/to/corpus-a ics-selfhosted=/path/to/corpus-b \
      --image ics-selfhosted=build-browser-release-aot/js/src/jit/aot/AOTImage.inc

Set difference is exact without comparing contents, because artifact
names are identity hashes. That is what lets the `overlap` table state
that two corpora carry the same IC set, which is the control an
ablation over the baseline set needs.

Note that `du` on a corpus dir reports block usage, and these corpora
are thousands of files well under one block. Quote `artifact_bytes` or
`image_bytes`, never `du`.

## Operational constraints

1. **The corpus is build-coupled.** Every blob header carries
   `slotTableHash` and the packer rejects a directory that mixes two.
   Any change to the AOT slot table or its region layout invalidates
   every recorded artifact and the run must be repeated.

2. **Record with a browser built from the source you will pack into.**
   Build the AOT browser, record, pack, relink.

3. **Disk.** Raptor fetches roughly 800 MB of pagesets on first run.

## Known defect elsewhere

`js/src/jit/aot/SelectAOTCorpus.py` parses the blob header with a
48-byte layout, but the header has been 56 bytes since `linkSitesSize`
and `slotTableHash` were added. It would misread `codeSize` and every
field after it. Nothing calls it today, but it should be fixed or
deleted.
