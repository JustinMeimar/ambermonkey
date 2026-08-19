
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
