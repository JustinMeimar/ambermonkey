
// Taken from the intro on 08-16
//
The design space for AOT systems is large. A new execution tier must
implement JavaScript semantics and coordinate with the surrounding runtime,
creating another correctness-sensitive attack surface. For this reason,
relying on an existing implementation is particularly convenitent for
JavaScript as misinterpreting its intricate specification can expose
vulnerabilities @wang2026enhancedinsecurity.

The first Futamura projection describes how one can derive compilation
through partial evaluation of an interpreter over a fixed program input
@futamura1971partial. This technique is attractive for AOT compilation since
it allows the interpreter to serve as a single source of semantic truth. The
Futamura projection, however, assumes that the guest program is available at
compile time. Browser workloads are dynamic, so a fixed browser image cannot
specialized over guest bytecode at run time without also requiring executable
memory.

The dynamic workload required of an engine running inside a browser prevents
prior techniques built upon SpiderMonkey from satisfying our aims. The
Portable Baseline Interpreter (PBL) handles JavaScript bytecode and CacheIR
in conjunction and was designed for partial evaluation in the WebAssembly
setting. Supplemented with a corpus of AOT Inline Cache stubs, Weval reports
a 2.77× geometric-mean speedup over the generic interpreter on Octane
@fallin2024weval. However, Weval wrelies on specializing program bytecode
present in a WebAssembly snapshot. Our AOT compilation step is constrained
to occur before any particular workload is anticipated

// Background subsection:


#subsection[Shareable Native Code]

An immutable AOT image can also share executable pages across processes. The
operating system maps instructions from the engine library as file-backed
read-execute pages. Processes can share the underlying physical pages while
their contents remain identical; patching an instruction triggers a private
copy of its page. V8 applies this principle to generated builtins by
embedding process-independent instructions in the engine binary and
retaining private metadata for each isolate @gruber2018builtins.

Sharing therefore requires a separation between immutable instructions and
private execution state. Artifact-local branches can use position-relative
references that remain valid when the image moves. References to runtime
heap objects, generated entry points, and mutable engine state instead
differ among runtimes. Leaving their concrete addresses in the instruction
stream prevents one file-backed artifact from serving each runtime
unchanged.


// From the SM tiers bg:

Firefox executes untrusted web JavaScript in sandboxed content processes
@mozilla2026processmodel. SpiderMonkey associates generated Baseline
infrastructure with a JavaScript runtime, while each Firefox process maps the
same engine library. SpiderMonkey also implements intrinsic functions using
_self-hosted JavaScript_. The build combines this source into data distributed
with the engine, making its function corpus known before deployment
@thrall2025selfhosted. Application scripts instead arrive after deployment and
cannot generally be predicted by the engine build.


// /From intro
//
interpreter-derived compilation's goal of avoiding an additional
semantic implementation, but reuse SpiderMonkey's production Baseline
generators during a trusted build. Adding a separate AOT backend would
introduce another implementation of JavaScript semantics. It would also need
to reproduce the production engine's garbage-collection, exception-handling,
stack-walking, and tiering interfaces.

>  Resuing without adding another compiler or interpreter


// form intro...


-Interpreter specialization provides another route to AOT compilation. The
first Futamura projection derives compiled code by specializing an in
terpreter for a fixed input program @futamura1971partial. Weval applies this
ap proach to jSpiderMonkey, deriving WebAssembly by specializing the
engine's inter preter for jguest bytecode and a fixed IC corpus stored in a
snapshot @fallin2025 weval. This preserves the interpreter as the source of
truth for bytecode executi on -semantics, but requires the guest program to
be available before AOT compilation.


// rip intro, higher code turn than a vibe coded claude plugin

V8 has demonstrated a prior art in the bootstrapping of runtime generated
code into it's engine binary with _Embedded Builtins_ @gruber2018builtins.
The project was initially designed to save memory by eliminating the
redundant recompilation of common JavaScript builtins across isolate
boundaies. By virute of an immutable, static representation, embedded
builtins also formed a natural basis for JITless execution
@gruber2019jitless. Beyond memory and JITless execution, the V8 team has
since expanded the scope of embedded buitlins towards perforamnce. Standard
library functions, such as `Array.map`, are optimized with fast paths
through a separetly maintained Torque DSL [CITE].

While V8s JITless mode has improved the performance of the engine
considerably under restricted execution environments, it notably does not
include arbitrary JIT artifacts on a statistical basis of cross-workload
occurence. One reason for this is that V8s Inline Caching system is data
driven, and therefore requires no runtime code generation in the first place.
A structured Inline Caching system, such as CacheIR used by SpiderMonkeyruntime,
requires runtime generation. 

Nonetheless, extending a code-generation model to integrate transparently
underneath a JIT compilation tier could allow for a more ergonomic and
performant AOT model. In terms of developer experience, such a model could
work automatically for all existing code generation routines, consume
regular JavaScript, and not require an expensive DSL or alternative
assembler to be produced.

More importantly however, building an AOT system from within existing code
generators allows for arbitrary JavaScript to be bootstraped into the engine
on a _statistical basis_. The consideration of including such JIT artifacts
into an AOT image immediately imposes the problem of coverage: only
artifacts that recur frequently across workloads could justify their binary
footprint. We examine this question at two compilation granularities:
Baseline-compiled functions and inline-cache (IC) bodies.


// I kinda liked this paragraph rip (08-19-2026)

The diffuse nature of JavaScript workloads affects compilation policy even
in environments where runtime code generation is enabled. Across 15,000
popular web pages, at least 70% of the functions in half of the JavaScript
files studied were unused @kupoluyi2022muzeel. Browser engines therefore
avoid expending compilation resources on cold code, preferring to invoke
Baseline compilation on demand rather than upfront. V8 and SpiderMonkey go
further by deferring full parsing and bytecode generation for many inner
functions until their first execution @v8preparser2019
@mozilla2026lazyparsing. These policies demonstrate two properties of guest
JavaScript code: it becomes known only after the engine is built, and much
of it never executes. Whole application functions are therefore an
unattractive default unit for a fixed AOT corpus.


// 

In Section III we contrast the cross-workload reuse of Baseline functions and
inline-cache (IC) bodies, establishing the primary empirical contribution of
this work. Across websites drawn from Mozilla's Firefox page-load benchmark
suite @mozilla2026tp6, we first quantify the static intersection of IC bodies
for each workload pair. We then weight the shared bodies by their frequency in
the target workload to obtain the directional dynamic intersection. The IC
bodies have a moderate static intersection but a substantially higher dynamic
intersection.

We attribute this contrast partly to compilation granularity: Baseline
compilation operates at coarse, whole-function granularity, whereas each IC
body implements one operation case. CacheIR's structured separation of native
stub code from site-specific data further enables this reuse.


// Candidate material removed from the introduction on 08-20-2026.
//
// Potential placement: AmberMonkey Design, near the first explanation of why
// the AOT transformation sits beneath existing code-generation interfaces.
// This contrast is too detailed for the introduction, but it may help the
// Design section distinguish the work from V8 Embedded Builtins.
//
// Paragraph outline:
// - V8 Embedded Builtins moved common generated routines into an immutable
//   engine image, initially to avoid redundant compilation across isolates.
// - The same immutable representation later supplied native routines under
//   V8's JITless mode.
// - V8 implements and maintains these routines through its builtin-specific
//   CodeStubAssembler and Torque pipeline.
// - Our design instead adds AOT generation beneath the interfaces used by
//   existing Baseline code generators. This placement lets the trusted build
//   capture Baseline functions, IC bodies, and engine infrastructure without
//   implementing each artifact through a separate code-generation path.
// - The distinction is the source of AOT artifacts, not the established use
//   of immutable engine code or indirection itself.
//
// Evidence and citations to retain when drafting:
// - Embedded Builtins and cross-isolate sharing: @gruber2018builtins.
// - Reuse of embedded routines in JITless execution: @gruber2019jitless.
// - Add a primary V8 source for the current CodeStubAssembler/Torque workflow
//   before making a detailed claim about its maintenance cost.


// Potential placement: end of the cross-workload-reuse analysis, after the
// contrast between Baseline functions and IC bodies.
//
// Paragraph outline:
// - Low reuse among complete application functions does not rule out every
//   Baseline function as an AOT artifact.
// - Self-hosted JavaScript functions are known when the engine is built and
//   recur in every runtime, so they do not require statistical selection.
// - This exception motivates two inclusion policies: deterministic or
//   build-time-known artifacts are included directly, while workload-derived
//   artifacts must demonstrate cross-workload reuse.
// - Keep the self-hosted function count and its measured contribution in the
//   empirical sections rather than the introduction.


// Potential placement: opening of AmberMonkey Design, before the pointer
// classification mechanism.
//
// Paragraph outline:
// - A separate AOT backend would need to reproduce more than instruction
//   selection. It would also need to preserve the production engine's frame,
//   garbage-collection, exception-handling, stack-walking, and tiering
//   interfaces.
// - Applying AOT generation beneath existing Baseline code-generation
//   interfaces retains these integration points.
// - This placement explains why the design covers Baseline functions, IC
//   bodies, and internally generated Baseline infrastructure without a new
//   implementation for each artifact class.


// Potential placement: cross-workload-reuse methodology, immediately before
// reporting pairwise results.
//
// Paragraph outline:
// - Static intersection measures which artifact identities recur in both
//   workloads and weights each identity equally.
// - Directional dynamic intersection weights the shared identities by their
//   frequency in the target workload.
// - The distinction explains how a moderate recurring set can cover most
//   run-time IC activity.
// - Report the exact values, benchmark selection, and limitations here rather
//   than in the introduction.
