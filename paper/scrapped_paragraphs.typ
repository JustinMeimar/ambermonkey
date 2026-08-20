
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

In section III we contrast the cross-process reuse of Baseline function
compilation against Inline Cache stubs, establishing the primary empirical
contribution of this work. Across #inter-site-count websites drawn from
Mozilla's Firefox page-load benchmark suite @mozilla2026tp6, we first
quantiy the static intersection of Inline Cache stubs which occur in each
pair. Despite only a moderate static intersection of
#inter-ic-jaccard-median, defined as the same IC stub occuring in each
workload, the frequency weighted, or dynamic intersection was signifacntly
higher. Defined as the stub entries occuring into ICs from the static
intersection, weighted by all IC stub entires globally, the dynamic IC
intersection across separate sites achieved a median coverage of #inter-ic-coverage-median.

We attribute this partialy due to compilation granuality: Baseline
compilation operates at coarse, whole-function granularity, whereas each IC
body implements one operation case. Foremost, however, we attribute this
high dynamic coverage to the strucutred design of CacheIR.


