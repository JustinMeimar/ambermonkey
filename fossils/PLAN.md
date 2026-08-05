

Ok Claude. Here is the deal. We can not keep adding complexity to these fossils.
They need to be simple, reproducible measurements over my instrumented base
FireFox so that we can collect some data to motivate our paper.

First of all, there is this 3-1-jit-memory fossil which has been a complete
pain in the ass. We're going to skip this for now. We need to do these
measurements, rerun them. 

```
=== Intra-workload IC Distributions

Frequency weighted intra-workload stats for Baesline executions and IC
stub executions. The same for Baseline compilations. This is relevant
to improving no-dynamically-executable-memory performance.   

- WHY: A frontier with high dynamic coverage is good for "JITless"
  exection prospects - suggests we call built a small yet robust
  corpus.

#banded-cdf(width: 50%, placement: none)

TODO: Rerun - this is old data

=== Inter-workload IC Coverage

Inter-workload Static intersection of Baseline artifacts:
Characterizes IC stub generalization and Baseline function
generalization.

- WHY: 
  - High _static_ intersection suggests memory savings from cross-process sharing is possible.
  - High _dynamic_ intersection suggests no-JIT performance reclamation by a 
       finite corpus is possible.
       

#ic-jaccard(width: 50%, placement: none)

TODO: Rerun - this is old data (add there is an accounting bug as Matt pointed out.)
```

I need the figures to be the same aesthetically, no deviations. The
task is simply to recreate the banded CDF graph for IC distributions
within the workload, and do the Jaccard analysis for inter-workloads.

All of the legacy fossils are in: /home/justin/spidermonkey/frostmonkey/fossils

I am moving over CLEAN AND SIMPLE AND MAINTAINTABLE implementations to:

/home/justin/spidermonkey/ambermonkey/fossils

You are in the firefox v153 base with my instrumentation commits applied.

Do you understand the task? 

