# 7-aot-corpus-collector — Implementation Notes

## Question the fossil answers

What is the AOT artifact corpus that the release browser compiles over
tp6, and how big is it? The run is also the corpus *producer*: the
recorded artifacts are the input to the packed AOT image.

## Why there is no selection policy here

The recorder observes the compile stream, not the execution stream. It
fires when baseline or an IC stub is compiled and writes the artifact;
nothing counts entries. There is no frequency to weight by, so the
policy is "use all" and the union is the corpus.

The union costs nothing to compute. Artifact names *are* identity
hashes, files are opened `O_EXCL`, and `EEXIST` is treated as success.
So every site and every content process can write into one directory and
the filesystem forms the union with no locking, no merge step and no
per-site subdirectory.

For ICs that identity covers `cacheKind`, the CacheIR bytes and the
field *types*, not the field values. Two sites compiling the same
CacheIR program against different shapes produce one artifact.

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

Self-hosted functions are recorded demand-driven, through the same
baseline path as page and chrome script, for whatever tp6 executes. The
exhaustive sweep that `--aot-record-self-hosted` performs in the shell
has no browser trigger and is deliberately not used: merging a
shell-recorded directory would mean reconciling two `configuration.aotb`
blobs, and the corpus we want is the one tp6 induces.

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
shell and `objdir/aot-record`. Pack the recorded dir directly:

    python3 js/src/jit/aot/PackAOTImage.py \
      --schema js/src/jit/AOTImageSchema.yaml \
      /tmp/amber-aot-corpus \
      build-browser-release-aot/js/src/jit/aot/AOTImage.inc
    touch js/src/jit/aot/AOTImageIncbin.cpp
    ./mach build binaries

`interp.aotb` and `configuration.aotb` are singletons rather than hashed
identities; the installer resolves the configuration with a unique
lookup, so exactly one of each belongs in the dir. One record dir gives
that for free.

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
