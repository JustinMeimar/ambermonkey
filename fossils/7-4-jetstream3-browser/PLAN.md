
Browser-driven JetStream 3 for the AmberMonkey 2x2. Sibling to
7-jetstream-startup which was the shell/synth fixture; the real
JS3 numbers live here.

The eval matrix is the same 2x2:

    Code delivery        Activation policy    Purpose
    ----------------     ------------------   -------------------------
    Runtime-generated    Normal/lazy          Stock baseline
    AOT image            Normal/lazy          Cost of AOT representation
    Runtime-generated    Eager                Benefit of tier policy
    AOT image            Eager                Combined AmberMonkey result

Startup story: JS3's Startup-Geometric is per-subtest first-iteration
runtime, aggregated as a geo-mean. It's the community-standard
startup measurement for browser JS. Also captured: Worst-Case and
Average phases as secondary metrics.

Requires the AOT release browser (build-browser-release-aot) to be
bootstrapped against the tp6 corpus from fossil 7-aot-corpus-collector.
Without a bootstrapped corpus the AOT variants will run as no-ops
(same as shell without --aot artifacts).
