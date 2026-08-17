# Review of “AmberMonkey: Reusable Ahead-of-Time Compilation for a Baseline JIT”

## Summary

This paper presents AmberMonkey, a system that captures selected SpiderMonkey Baseline-tier artifacts during a trusted build and embeds them in the engine as ahead-of-time (AOT) code. AmberMonkey separates immutable instructions from runtime-specific state using a per-runtime indirection table, native-linker relocations, and private metadata wrappers. The image contains a deterministic Baseline Interpreter, build-time-known self-hosted Baseline functions, and inline-cache (IC) bodies selected from a training corpus.

The paper makes two empirical observations that guide this design. Application Baseline functions show little exact reuse across unrelated workloads, whereas dynamic IC activity is concentrated in a recurring set of bodies. On held-out suites, the selected IC corpus serves 99.6% of IC attachment requests on Speedometer 3.1 and 70.3% on JetStream 3.0. Under a configuration that disables guest-code compilation, the paper reports a 51% Speedometer improvement over bytecode-only execution, reaching 57% of default SpiderMonkey throughput.

The core idea is relevant to CGO, and the prototype addresses difficult integration points in a production JavaScript engine. I particularly like the separation of artifact selection from runtime-state decoupling. The revision clarifies AOT-only miss behavior and now makes the abstract’s 7% indirection result consistent with the displayed microbenchmark. However, the evaluation does not yet isolate which parts of AmberMonkey produce the reported benefit, the indirection estimate remains explicitly preliminary, and the primary performance protocol is internally inconsistent. The paper also needs substantially stronger correctness and restricted-execution evidence. I therefore lean toward rejection in its current form, while viewing the work as a promising resubmission after a focused evaluation revision.

Per the review instruction, I take the memory-evaluation notes at face value and assume the authors will replace them with polished, supported conclusions. I do not count the present state of that section against the paper or recommendation.

## Strengths

1. **The problem is important and well motivated.** Restricted-execution configurations give up large amounts of JavaScript performance. Recovering native execution without placing a guest-driven compiler in the runtime path is a useful systems goal.

2. **The design engages with production-engine constraints.** The paper covers frame layout, stack walking, garbage collection, IC operands, profiler/debugger patch sites, native linking, and metadata reconstruction. This is more convincing than a stand-alone AOT compiler that bypasses the host engine’s normal interfaces.

3. **The artifact taxonomy is useful.** Separating deterministic engine code, build-time-known functions, and recurring IC bodies gives each class a defensible inclusion policy. The contrast between low Baseline-function reuse and high dynamic IC coverage is a clear empirical result.

4. **The held-out IC-coverage result is encouraging.** A 99.6% request hit rate on Speedometer 3.1 from a fixed tp6-derived corpus suggests that CacheIR body reuse is practically exploitable. The lower JetStream result is reported rather than hidden and helps establish the boundary of the approach.

5. **The paper generally states important implementation limits.** The x86-64 scope, unsupported movable garbage-collected pointers, trusted-image assumption, private preambles, and loss of sharing under instrumentation are all relevant limitations.

6. **AOT-only fallback semantics are now clear.** The paper explains that Baseline-function misses remain in the shared Baseline Interpreter, IC-body misses use the shared C++ fallback stub without attaching specialized code, and ineligible scripts remain in the C++ bytecode interpreter. This materially sharpens the restricted-execution boundary.

## Major concerns

### 1. The evaluation does not attribute the 51% restricted-execution improvement

The deployed image combines three mechanisms: the AOT Baseline Interpreter, 236 self-hosted Baseline functions, and 1,347 IC bodies. The main experiment compares the combined image only against bytecode-only execution, runtime Baseline, and the default JIT. It therefore establishes that the complete configuration helps, but not why.

This is especially important because the reported Baseline-function hit rate is below 1% on both held-out suites, while the Baseline Interpreter is deterministic and the IC corpus has high request coverage. A reader cannot tell whether nearly all of the 51% improvement comes from the interpreter, whether IC bodies materially improve throughput, or whether the self-hosted functions justify their implementation and image cost. Request coverage is not a substitute for performance attribution.

The paper needs an artifact ablation on the same restricted-execution workload:

- bytecode-only;
- AOT Baseline Interpreter only;
- interpreter plus self-hosted Baseline functions;
- interpreter plus IC bodies;
- the complete image.

Reporting per-component Speedometer results, not only the aggregate score, would also reveal whether the benefit is broad or concentrated. Without this evidence, the evaluation does not support the paper’s three-part artifact-selection argument.

### 2. The indirection result remains preliminary and lacks the promised ablation

The revision fixes the earlier claim mismatch: the abstract now reports a 7% geometric-mean overhead across eight microbenchmarks, which agrees with Figure 5 and identifies the evaluated scope. This is a meaningful improvement. The supporting experiment, however, still consists of one fresh process per configuration, and the evaluation itself labels the result preliminary. It provides no estimate of run-to-run variation.

The counters also include process startup and the initial tier transition. Long loops may amortize those costs, but convergence should be demonstrated rather than asserted. Eight hand-written kernels are useful diagnostic tests, but they do not establish end-to-end overhead on the held-out applications. In addition, the methodology says that generic indirection, value mirroring, native-linker resolution, and the complete lowering are compared, while Figure 5 presents only runtime-generated code against the complete AOT configuration.

The authors should repeat the experiment across independent processes and report uncertainty, instructions, cycles, and instructions per cycle. They should either provide the stated optimization ablation or remove the promise that these mechanisms are evaluated separately. An end-to-end comparison of default JIT against default JIT plus AOT would establish whether indirection remains measurable in realistic tiered execution. Until then, the abstract should identify the 7% result as preliminary or omit it as a headline quantitative conclusion.

### 3. Correctness and restricted-execution validation are too limited

AmberMonkey changes several correctness-sensitive interfaces: Baseline and stub frames, bailout and on-stack-replacement reconstruction, generator resume, garbage-collector tracing, profiler maps, debug traps, and runtime-pointer lowering. The design discussion is detailed, but the evaluation contains no correctness campaign. Performance on two suites is not adequate validation for this surface area.

At minimum, I would expect results from SpiderMonkey’s JIT test suites and Test262, together with stress configurations for garbage collection, barriers, generators, exceptions, bailout/on-stack replacement, and IC tracing. The paper should report how many tests ran, exclusions, failures, and whether AOT and ordinary Baseline executions were differentially compared. It should also quantify the dependency audit: how many embedded references fall into each resolution class and which artifacts are rejected. The paper already explains that capture stops on an unrecognized pointer; the missing evidence is how often that occurs and how complete the supported corpus is.

The restricted-execution claim also needs an explicit audit. The paper states that regular-expression and WebAssembly compilation are disabled and that deterministic bootstrap generation remains, but it does not demonstrate that guest execution cannot trigger another executable allocation or instruction patch. Dynamic debugging and profiling can patch image-backed pages, which also means the abstract’s unqualified description of the artifacts as immutable is too broad. The authors should define the threat model and policy precisely, enumerate all remaining code-generation and code-patching paths, and state which runtime modes preserve the guarantee. Because the performance experiments disable Firefox’s content sandbox, the paper should at least validate functional operation with the normal sandbox and explain why disabling it does not change the measured code paths.

### 4. Corpus construction and generalization need a stronger experimental design

The characterization begins with eight tp6 sites, while the final corpus is trained on 32 sites and admits IC bodies observed on at least 10% of them. The paper reports the image size at several thresholds, but it does not justify the selected 10% threshold using a validation set or show the coverage–size–performance tradeoff. It is therefore unclear whether this parameter was fixed before examining Speedometer and JetStream or selected because it produced the reported results.

The generalization evidence is also narrow. Speedometer is a useful held-out web suite, but it is close in domain to the tp6 training pages. JetStream provides an informative distribution shift and reaches only 70.3% IC hit rate, yet the paper does not measure restricted-execution performance on JetStream or explain which components cause the misses. A leave-one-site-out analysis over tp6, a separate validation set for the threshold, and more than one held-out web workload would make the corpus claim much more robust. Per-workload or per-component coverage distributions should accompany suite-wide totals so that large components cannot dominate dynamic request counts.

The collection protocol also needs clarification. Section III states that the initial eight-site characterization uses three cold page loads. The final 32-site corpus does not state the number of captures per site, how nondeterministic page behavior is handled, or whether identities must recur across repeated visits. These choices affect prevalence and reproducibility.

### 5. Experimental reporting is internally inconsistent

The methodology states that performance results use 10 independent browser runs, five Speedometer page cycles per run, randomized blocks, and 95% bootstrap confidence intervals. Figure 4 instead says that it uses three browser runs, three page cycles, and standard-deviation error bars. The coverage section reports means across three iterations. These may be distinct collections, but the paper does not distinguish them, and Figure 4 directly conflicts with the stated performance protocol.

These discrepancies matter because the 51% result is the paper’s principal performance claim. The final paper needs one consistent protocol and should report confidence intervals for the pairwise ratios described in the methodology. It should give the exact Firefox revision rather than only “153.0a1,” identify which comparisons use the same binary versus matched object-directory builds, and report the implementation size or patch scope. The use of non-PGO/non-LTO Firefox and a disabled content sandbox is acceptable for a controlled prototype experiment, but both choices limit external validity and should be discussed explicitly.

### 6. The novelty positioning is incomplete

The related-work section discusses only ShareJIT. That is not sufficient to establish the contribution of a system combining build-time capture, a per-runtime pointer table, embedded engine code, and reusable IC bodies. The paper cites V8 embedded builtins, Copy-and-Patch, CacheIR, and reusable inline caching elsewhere, but it does not synthesize those comparisons in Related Work.

The authors should explain more directly what is new relative to embedded builtins and isolate/root tables, prior shared-code caches, reusable ICs, build-time snapshots, and offline or remote JIT compilation. In particular, the per-runtime indirection table resembles established position-independent-code and engine-root-table techniques. The likely contribution is the systematic application to SpiderMonkey Baseline functions and CacheIR bodies while reconstructing production JIT metadata, not indirection by itself. The paper will be stronger if it states that distinction precisely and quantifies which dependencies required new treatment.

## Minor comments and author questions

1. The revision explains the behavior of Baseline-function and IC-body misses. The evaluation should now quantify their cost, especially the time spent in the C++ IC fallback on JetStream, where 29.7% of attachment requests miss the AOT corpus.

2. How are semantic identities protected against hash collision, and which compilation flags and script properties enter a Baseline-function identity? A concrete format description would improve reproducibility.

3. Reverse-mapping concrete pointer values at the MacroAssembler boundary appears vulnerable to semantic aliasing if two roles temporarily contain the same address but later diverge across runtimes. Does the implementation identify a dependency by its semantic origin as well as its captured numeric value?

4. The paper should report runtime image-attachment and metadata-reconstruction costs. AOT may remove compilation while adding lookup, wrapper allocation, and initialization work; steady-state Speedometer throughput does not expose startup costs.

5. The statement that runtime coupling is “incidental rather than semantic” should remain explicitly scoped to the captured artifact and operand forms. Unsupported movable cells and retargetable pointers show that this is not a general property of all Baseline-tier references.

6. The abstract says that the approach avoids patching instruction bytes, while the instrumentation section permits profiler and debugger patching. Qualify the abstract claim to normal non-instrumented execution.

7. The paper would benefit from a compact end-to-end example tracing one CacheIR body from capture through identity lookup, metadata reconstruction, attachment with private operands, and execution through the runtime indirection table.

8. The conclusion currently emphasizes preliminary observations but does not restate the principal restricted-execution result or its scope. The final conclusion should mirror the supported contributions and avoid claims not backed by an evaluation subsection.

9. There are many typographical and grammatical errors. These are fixable, but several occur in definitions and claims where they impede interpretation. A dedicated copy-editing pass is needed after the technical revision.

## Overall assessment

AmberMonkey contains a strong systems idea and substantial implementation work. The artifact-reuse characterization is interesting, and the use of immutable, image-backed Baseline artifacts could make restricted execution considerably less costly. The paper is closest to acceptance when it explains the production integration and when it contrasts Baseline-function reuse with IC-body reuse.

The current evidence does not yet support the full story. The combined performance result lacks artifact ablations, the 7% indirection result is based on one process per configuration, the primary performance protocol is contradictory, and correctness and restricted-execution validation are missing. These are central issues rather than presentation details. The revision has nevertheless improved the paper by reconciling the abstract with Figure 5 and defining AOT-only miss behavior. A further revision that adds the ablations, reconciles the statistics, broadens held-out evaluation, and provides a systematic correctness and code-generation audit could be competitive at CGO.

**Recommendation:** Weak reject (2/5)

**Confidence:** High (4/5)
