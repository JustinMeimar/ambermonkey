# 7-aot-corpus-collector — Implementation Notes

## Question the fossil answers

What is the AOT artifact corpus that the release browser compiles over
tp6, and how big is it? The run is also the corpus *producer*: the
recorded artifacts are the input to the packed AOT image.

## Selection policy

The recorder observes the compile stream, not the execution stream. It
fires when baseline or an IC stub is compiled and writes the artifact;
nothing counts entries. There is no frequency to weight by, so within a
kind the only lever is how many sites shared the artifact.

**The corpus takes IC stubs from the sites and drops their baseline
functions.** 7-2 measured a tp6-derived corpus against speedometer3. IC
stubs served 99.6% of stub-code requests and covered 90.9% of the
distinct CacheIR programs the workload asked for. Recorded baseline
functions served 4.9% of baseline compile requests, and 65% of the
packed baseline corpus was never installed at all.

Baseline functions are also where the bytes are. The tp6 union is 26229
baseline functions against 1864 IC stubs in 73 MB total, which is why
the sweep reports baseline in MB and IC in KB. The dropped kind was
buying 4.9% for very nearly the whole image.

The drop is a flag on the selector, `--exclude-kind blfun`, not a
property of the scripts. `threshold_sweep.py` deliberately still indexes
both kinds: the per-site sharing curve for baseline functions is the
evidence for this policy, and it has to stay measurable to stay
falsifiable.

Baseline functions still enter the corpus, but only the self-hosted
library, and not by observation. See below.

The union costs nothing to compute. Artifact names *are* identity
hashes, files are opened `O_EXCL`, and `EEXIST` is treated as success.
So every site and every content process can write into one directory and
the filesystem forms the union with no locking, no merge step and no
per-site subdirectory.

For ICs that identity covers `cacheKind`, the CacheIR bytes and the
field *types*, not the field values. Two sites compiling the same
CacheIR program against different shapes produce one artifact. That is
also why they transfer: the identity is shape-free, so a program some
other workload compiles resolves to an artifact this one already
recorded.

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
recording dir, which still holds every per-site baseline function:

    python3 scripts/soft_intersection.py \
      /tmp/amber-aot-corpus /tmp/amber-aot-selected \
      --threshold 0.25 --budget 4000000 \
      --exclude-kind blfun \
      --self-hosted /tmp/amber-aot-selfhosted

    python3 js/src/jit/aot/PackAOTImage.py \
      --schema js/src/jit/AOTImageSchema.yaml \
      /tmp/amber-aot-selected \
      build-browser-release-aot/js/src/jit/aot/AOTImage.inc
    touch js/src/jit/aot/AOTImageIncbin.cpp
    ./mach build binaries

`interp.aotb` and `configuration.aotb` are singletons rather than hashed
identities; the installer resolves the configuration with a unique
lookup, so exactly one of each belongs in the dir. The selector picks
one of each and verifies the sites agree on the configuration.

## Tables

`threshold_sweep.py` answers which threshold to pick.
`corpus_tables.py` answers what a chosen corpus is made of, and how two
candidates differ as sets. Both emit the `{columns, rows}` shape the
typst `json-table` loader reads, with values left numeric.

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
