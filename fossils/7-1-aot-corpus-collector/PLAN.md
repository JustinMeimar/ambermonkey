
This fossil, when burried, should invoke the browser-release-aot
build on the tp6 workload and collect all of the Baseline artifacts,
including IC stubs, Baseline functions, the baseline interpreter,
as well as the self-hosted parent-process code.

The aot-recording flags on the release browser should produce all
the artifacts in a /tmp directory, and this fossil should run the
browser over the tp6 workload to produce the raw artifact dump.

Another script in this fossil will be responsible for applying the
corpus selection policy. For now we can just "use all". We will
build the aot-browser against this /tmp corpus
