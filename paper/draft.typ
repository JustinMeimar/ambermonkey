#import "lib/figures.typ": ambermonkey-overview, aot-image-layout, cacheir-sharing-example, code-lowering-panel, image-relocation-scaffold
#import "lib/tables.typ": table-from-json
#import "lib/configurations.typ": config-table-from-json
#import "constants.typ": *
#import "@preview/algo:0.3.6": code

#set page(
  paper: "us-letter",
  margin: (
    top: 2cm, bottom: 1.5cm,
    left: 1.9cm, right: 1.9cm
  ),
  columns: 2,
  numbering: "1",
)
#set text(
  font: ("Times New Roman", "TeX Gyre Termes"),
  size: 10pt,
  lang: "en"
)
#set par(
  justify: true,
  first-line-indent: 1em,
  spacing: 0.4em,
  leading: 0.5em,
)
#show figure.caption: set text(size: 8.5pt)

#let TODO(body) = box(
  stroke: 1.5pt + red,
  inset: 4pt,
  radius: 2pt,
  fill: rgb(255, 230, 230),
  text(fill: red, weight: "bold", size: 8pt)[TODO: #body]
)

#let NOTE(body) = box(
  stroke: 1.5pt + rgb(180, 140, 0),
  inset: 4pt,
  radius: 2pt,
  fill: rgb(255, 248, 220),
  text(fill: rgb(100, 80, 0), weight: "bold", size: 8pt)[NOTE: #body]
)

#let fig(path, caption, width: 100%, height: 100%, placement: top, scope: "column") = figure(
  image(path, width: width),
  caption: caption,
  placement: placement,
  scope: scope,
)

#let section(title) = {
  show heading: set text(size: 10pt, weight: "regular")
  show heading: set align(center)
  heading(
    level: 1,
    numbering: (..numbers) => numbering("I.", numbers.pos().last()),
    upper(title),
  )
}

#let subsection(title) = {
  show heading: set text(size: 10pt, style: "italic", weight: "regular")
  heading(
    level: 2,
    numbering: (..numbers) => numbering("A.", numbers.pos().last()),
    title,
  )
}

#place(
  top,
  scope: "parent",
  float: true,
  block(width: 100%)[
    #align(center)[
      #text(size: 17pt, weight: "bold")[
        AmberMonkey: Reusable AOT Artifacts from a Production JavaScript JIT
      ]
    ]
    #v(0.8em)
    #grid(
      columns: (1fr, 1fr, 1fr),
      align(center)[
        *DRAFT*  \
        #link("mailto:draft@draft.ca") \
        University of Alberta \
        Edmonton, Canada
      ],
      align(center)[
        *DRAFT*  \
        #link("mailto:draft@draft.ca") \
        University of Alberta \
        Edmonton, Canada
      ],
      align(center)[
        *DRAFT*  \
        #link("mailto:draft@draft.ca") \
        University of Alberta \
        Edmonton, Canada
      ],
    )
    #v(1em)
  ]
)

#pad(x: 0.2em)[
#text(weight: "medium", size: 10pt)[

$space$ JavaScript engines provide restricted-execution modes to disable
guest-controlled just-in-time (JIT) compilation. Restricted execution aims
to reduce an engine's attack surface. Disabling JIT compilation, however, can
substantially reduce performance. We find that the Baseline JIT can run ahead
of time (AOT) to generate inline-cache (IC) bodies and Baseline functions,
reclaiming performance lost under restricted settings. Our analysis shows that
dynamic IC requests concentrate in a small recurring set of stub bodies, making
their inclusion in a fixed AOT image feasible. Our #ic-stub-bytes corpus serves
#sp3-ic-hit-rate of IC-body requests on Speedometer 3.1 and #js3-ic-hit-rate on
JetStream 3.0.

We present AmberMonkey, a code-generation model that invokes SpiderMonkey's
Baseline JIT during a trusted build and embeds the generated code in the engine
executable. JIT-generated instructions normally embed addresses of data and
code in the current JavaScript runtime, tying those instructions to one
process. AmberMonkey keeps the instructions immutable by resolving engine
symbols at native link time and accessing per-runtime values through a _Runtime
Indirection Table_ (RIT). This indirection adds #indirection-overhead overhead
across our microbenchmarks. Under restricted execution, AmberMonkey improves
Speedometer 3.1 throughput by #sp3-aot-speedup over interpretation and reaches
#sp3-aot-default-fraction of default tiered-JIT throughput. Its immutable AOT
image also avoids redundant JIT compilation across runtimes, reducing engine
proportional set size (PSS) per content process by #jit-memory-reduction on
Speedometer 3.1.

]
]

#section[Introduction]
#linebreak() 

$space$ Restricted-execution modes prevent untrusted guest JavaScript from
triggering just-in-time (JIT) compilation. Platforms impose these modes to
satisfy executable-memory constraints or to reduce the compiler attack
surface exposed to guest-controlled inputs. JIT compilation remains a security
risk in contemporary JavaScript engines. A 2026 review of V8
bugs estimated that JIT compilers accounted for roughly 50% of the tracked
vulnerabilities @gross2026state. Disabling JIT compilation, however, can
substantially reduce application throughput. V8 initially reported a 40%
Speedometer 2.0 slowdown in its JITless configuration @gruber2019jitless. In
our experiments, an interpreter-only SpiderMonkey configuration reached 38%
of the throughput of the default tiered-JIT configuration on Speedometer
3.1. This gap motivates an ahead-of-time (AOT) code-generation model that
improves performance over interpretation without allowing guest-triggered
native-code generation.

V8 established prior art in bootstrapping runtime-generated code into its
engine binary with Embedded Builtins @gruber2018builtins. V8 previously
implemented most builtins in self-hosted JavaScript, platform-specific
assembly, or C++. It later ported performance-sensitive builtins to the
CodeStubAssembler and Torque, whose separate build pipeline generates native
bodies for embedding.

Embedded Builtins make their generated bodies immutable and process
independent, allowing isolates to share a fixed corpus. This representation
also supplies native engine routines under JITless execution
@gruber2018builtins @gruber2019jitless. Extending the corpus, however,
requires developers to implement each additional function or fast path
through V8’s builtin-specific Torque and CodeStubAssembler stack. Torque
reduces the burden of authoring CodeStubAssembler code, but the resulting
workflow remains separate from ordinary JavaScript and V8’s runtime JIT
generators.

AmberMonkey takes a distinct approach. We extend SpiderMonkey's MacroAssembler
with an AOT emission mode, allowing existing code generators to produce
reusable artifacts without a parallel backend, new implementation language,
or source annotations. AmberMonkey is therefore transparent to top-level
code-generation routines: it can be enabled with a
single switch to transform compatible Baseline functions, inline-cache (IC)
bodies, and internal JIT mechanisms into an AOT format.

This interface lets us construct an AOT corpus beyond a library of individually
implemented builtins. Adding artifacts does not require hand-authored
implementations. Applying AOT compilation to existing JavaScript raises an
empirical coverage question: only artifacts that recur frequently across
workloads can justify their binary footprint. We examine this question at two
compilation granularities: Baseline-compiled functions and IC bodies.

In Section III, we contrast the cross-workload reuse of Baseline functions
with that of inline-cache bodies, establishing the primary empirical
contribution of this work. Across #inter-site-count websites drawn from
Mozilla's Firefox page-load benchmark suite @mozilla2026tp6, we first measure
the _static intersection_ for each pair. This metric is the fraction of
distinct artifact identities observed in either workload that occur in both.
IC bodies have a median static intersection of #inter-ic-jaccard-median.

Static intersection gives frequent and infrequent bodies equal weight. We
therefore also measure the directional _dynamic intersection_ from a corpus
workload to a target workload. This metric is the fraction of body entries
in the target whose identity also occurs in the corpus. Across separate
sites, IC bodies achieve a median dynamic intersection of
#inter-ic-coverage-median. Baseline functions achieve only
#inter-baseline-coverage-median under the same dynamic measure. We attribute
this difference partly to compilation granularity: Baseline compilation
operates at coarse, whole-function granularity, whereas each IC body implements
one operation case. Primarily, however, we attribute the high dynamic
intersection to CacheIR's structured design.

CacheIR enables high cross-workload reuse by separating native stub code from
per-site data @demooij2023cacheir. This design deliberately enables IC stub
bodies to be shared across distinct IC sites within a JavaScript runtime.
AmberMonkey extends this notion from intra-process
sharing to cross-process sharing across JavaScript runtimes. We elaborate on
how the design decisions of CacheIR inform a feasible AOT corpus in Section
III.

The same analysis rules out complete application functions as a general
corpus unit. Baseline compilation can achieve speedups of 2–3× over
interpretation @titzer2024baseline and remains type generic, whereas optimizing
JIT code specializes to observed runtime types. This reduces one constraint on
reuse because runtime type behavior need not be replicated alongside function
identity. Our analysis nevertheless finds too little cross-workload reuse
among Baseline functions to justify their inclusion in the AOT corpus. Instead,
we compile #self-hosted-fn-count self-hosted JavaScript functions, including
builtins, that are available across all workloads. These functions require no
modification; a single pass through AmberMonkey produces their AOT
representations.

Recurring IC bodies and build-time-known self-hosted functions establish the
contents of a feasible AOT corpus. The remaining challenge is to make their
native code independent of the runtime that generated it. JIT compilers
generally assume that their native output will
execute in the process that generated it. By embedding absolute addresses of
engine routines, runtime data structures, and other generated code,
runtime-generated native code is coupled to its runtime. A reusable AOT format
must resolve these dependencies without affecting the semantics.

We introduce _AmberMonkey_, a code-generation model that invokes an existing
Baseline JIT during a trusted build and embeds its output in the engine
executable. By reusing production code generators, AmberMonkey avoids adding
another implementation of JavaScript execution semantics. The AOT image
contains the Baseline Interpreter, Baseline-compiled functions from the
engine's self-hosted library, and a fixed corpus of IC bodies observed across
workloads.

AmberMonkey keeps the generated instructions immutable by resolving engine
symbols at native link time and accessing runtime-specific values through a
per-runtime _Runtime Indirection Table_ (RIT). At load time, AmberMonkey
reconstructs JIT artifacts from the image-backed code and metadata.
The model applies to runtimes that can run their production code generators
during a trusted build, separate reusable code from site-specific data, and
refer to runtime dependencies without embedding their concrete addresses.

We implement AmberMonkey in SpiderMonkey on x86-64. We evaluate corpus coverage
on held-out workloads, restricted-execution throughput, the overhead of runtime
indirection, binary-size cost, and executable-memory sharing across browser
content processes. This paper makes the following contributions:

#linebreak()

1. We show that operation-level inline-cache (IC) bodies recur across distinct
   web workloads. The fixed corpus contains #ic-stub-count IC bodies and
   occupies #ic-stub-bytes. It serves #sp3-ic-hit-rate of IC-body attachment
   requests on Speedometer 3.1 and #js3-ic-hit-rate on JetStream 3.0. We
   identify the separation of executable code from site-specific data as the
   design property that enables this reuse, and show that CacheIR provides this
   separation.

   #linebreak()

2. We design and implement AmberMonkey: a transparent code-generation mode
   in SpiderMonkey's Baseline JIT for producing AOT artifacts. We
   automatically decouple embedded pointers by first assigning each a stable
   identity. AOT artifacts then obtain pointers through a _Runtime Indirection
   Table_ (RIT), which each runtime fills with live values. For a subset of
   symbols visible at link time, we offload relocations to the native linker
   at zero runtime cost.

   #linebreak()

3. We evaluate AmberMonkey in SpiderMonkey on x86-64. In the AOT-only
   configuration, AmberMonkey improves Speedometer 3.1 throughput by
   #sp3-aot-speedup over bytecode-only execution and reaches
   #sp3-aot-default-fraction of default tiered-JIT throughput. We also quantify
   indirection overhead, binary-size cost, and per-content-process engine
   proportional set size (PSS).


#section[The Complexity of Optimizing JavaScript]

#linebreak()

This section outlines the security considerations that shape AmberMonkey's
restricted-execution model. JIT compiler vulnerabilities motivate restricted
execution, but interpreters can also introduce semantic vulnerabilities.
JavaScript's intricate semantics affect both, while optimization adds further
correctness obligations. We therefore build AmberMonkey around existing
production code generators instead of introducing another implementation of
JavaScript semantics.


#subsection[Interpretation and Compilation]

JavaScript just-in-time (JIT) compilers expose a direct path from
attacker-controlled inputs to native instructions. An attacker can shape
both the bytecode being compiled and the run-time profiles that drive
speculative optimization. A missed side effect or invalid type assumption
can cause the compiler to emit instructions that violate the engine's
memory-safety invariants. Notably, implementing the compiler in a
memory-safe language does not prevent these logic errors, as generated
instructions perform the invalid access.

Automated bug finding has recently exposed security defects at scale.
Mozilla reported that an early evaluation of Anthropic's Mythos Preview
identified 271 vulnerabilities fixed in Firefox 150 @holley2026zerodays. One
month later, Nebula Security reported CVE-2026-10702 @nebula2026ionstack.
The high-severity vulnerability arose because SpiderMonkey's optimizing
compiler modeled an instruction that could allocate as a load. Global value
numbering could then reuse a stale pointer to object-property storage. The
resulting JIT miscompilation enabled arbitrary code execution in the content
process @nebula2026ionstack.

This example shows that optimized just-in-time (JIT) compilation remains a
source of vulnerabilities. However, treating JIT compilation as the sole
source of semantic bugs is a misconception. JavaScript’s intricate
semantics challenge both JIT compilers and interpreters; JIT compilers
compound this complexity with optimizations that must preserve semantics.
Microsoft’s DrumBrake WebAssembly interpreter, developed for JIT-disabled
execution, illustrates how interpreters can also fail. Researchers reported
23 remote-code-execution vulnerabilities involving type confusion,
reference-stack indexing, missing garbage-collection barriers, and incorrect
control-flow handling @wang2026enhancedinsecurity. Although DrumBrake
executes WebAssembly rather than JavaScript, these failures show that
replacing compilation with interpretation can shift, rather than eliminate,
the attack surface.

These examples motivate two design constraints. First, AmberMonkey admits only
artifacts generated during a trusted build. Guest execution may select and
parameterize those artifacts but cannot generate new instructions. Second,
AmberMonkey reuses production Baseline generators rather than introducing
another interpreter or compiler backend. We exclude optimizing-tier artifacts
because their profile-driven speculation and transformations enlarge the
trusted code-generation mechanism. This boundary reduces the system exposed to
guest-directed compilation, but defects in Baseline generators or captured
artifacts remain within AmberMonkey's trusted computing base.


#subsection[Restricted Execution]

We distinguish two forms of restricted execution. _No-runtime-code-generation_
prohibits allocating executable memory after the process starts. This policy
satisfies platforms that prohibit JIT executable memory @apple2024ios and is
exemplified by V8's JITless mode @gruber2019jitless.
_Initialization-only code generation_ permits an engine to generate a fixed
set of infrastructure artifacts before executing guest code, but prohibits
code generation whose contents or selection depend on guest programs or their
run-time behavior. Hereafter, _restricted execution_ refers to this second
policy unless stated otherwise.

AmberMonkey provides initialization-only code generation. Its AOT image is
fixed during the build, and guest execution cannot modify or extend it. At run
time, AmberMonkey disables Baseline-function, inline-cache (IC) body,
optimizing, and regular-expression compilation, but retains deterministic
trampoline and entry-preamble generation. JetStream 3.0 also retains
WebAssembly compilation because SpiderMonkey lacks a WebAssembly interpreter.
Our prototype does not move bootstrap generation into the AOT image or provide
a non-JIT WebAssembly path. We leave these extensions to future engineering
work because neither requires a change to AmberMonkey's artifact-selection or
runtime-independence design.

#linebreak()


#section[Structured Inline Caching Forms a Bounded AOT Corpus]

#linebreak()

$space$ Fixed-handler inline caches (ICs) bound their executable code by
generating their handler implementations before an application runs. This
property makes them directly compatible with restricted execution, but it
restricts native specialization to combinations anticipated by the fixed
handler set.
Dynamically translated ICs occupy a different design point. They can combine
the guards and fast operation for an observed case in one specialized native
instruction sequence, but their apparently open-ended output threatens to make
a fixed AOT image impractical.

This section shows that native IC specialization and a bounded AOT image are
compatible. Prior work reports that CacheIR improved Baseline Interpreter
performance over SpiderMonkey's C++ interpreter by 1.63× on Speedometer 2.1
and 1.95× on JetStream 2.1 @demooij2023cacheir. CacheIR separates the
structural program compiled into a native body from values private to an IC
site. We find that the resulting body identities recur across unrelated
workloads. AmberMonkey can therefore retain CacheIR's native specialization
under restricted execution while replacing guest-triggered compilation with a
lookup in a compact AOT corpus. Section VII measures the performance recovered
by this corpus.

#cacheir-sharing-example(placement: top)

#subsection[Inline Caching]

At its core, inline caching specializes a generic routine with one or more
guarded fast paths. Deutsch and Schiffman introduced the technique to improve
dynamic method dispatch in Smalltalk @deutsch1984smalltalk. When a dynamic
method is first invoked, a generic routine resolves the method based on the
receiver object's class. Assuming call-site _locality_, the implementation
caches the resolved method and attempts the same dispatch on subsequent
invocations. This fast path is guarded by the receiver class and falls back to
generic method lookup upon failure.
Hölzle, Chambers, and Ungar later extended this design with polymorphic inline
caches, which retain several receiver classes at one site @holzle1991pic.

Modern inline caching systems in JavaScript adapt this design for
polymorphic operators. SpiderMonkey associates an inline cache (IC) with
each supported bytecode in a script. Both the generated Baseline Interpreter
and Baseline-compiled functions dispatch to these ICs. Each IC is a linked
list of type-specialized stubs. Execution traverses this _IC chain_ until a
stub's guards match the observed operands, object shapes, or callee
@demooij2023cacheir.

SpiderMonkey lazily compiles specialized IC stubs through the fallback stub.
Each IC chain initially contains only this fallback. When no specialized stub
matches, the fallback computes the generic result and attempts to compile a
stub for the observed case. It prepends the new stub to the linked list so that
the most recently observed case is tested first. An attached _IC stub_ contains
chain linkage, an entry counter, and metadata holding CacheIR and site-specific
data. It also points to a native _stub body_ that implements its guards and fast
operation @demooij2023cacheir. This separation between an attached stub and its
executable body is central to AmberMonkey's AOT corpus.
@fig-interworkload-coverage previews the cross-workload comparison reported
at the end of this section.

#subsection[Executable Representation]

IC systems differ in whether run-time observations select pre-generated code
or trigger dynamic translation. In a _fixed-handler_ design, an observation
updates data or an opcode that selects machine code generated with the engine.
Brunthaler describes interpreter ICs that update a handler pointer or replace a
generic bytecode opcode with a pre-generated specialized opcode
@brunthaler2010quickening. The latter technique, called _quickening_, changes
the interpreted instruction without generating native instructions at run
time.

V8's Ignition interpreter also draws from a fixed set of bytecode handlers.
Each property IC site records observations and handler selections in a feedback
vector, so execution can adapt the site's data without extending Ignition's
executable handler set @alle2018codecaching. The native handler implementations
are therefore available before an application runs.

A _dynamically translated_ IC instead generates a native stub body for an
observed case. CacheIR uses this representation in SpiderMonkey. A CacheIR
generator describes the guards and fast operation, and the Baseline CacheIR
compiler lowers that description to native code @demooij2023cacheir. The
resulting body places the case's guards and operation in one type-specialized
instruction sequence.

At first glance, dynamically translated ICs appear incongruent with an AOT
formulation. Every IC site can invoke run-time code generation for its observed
cases, and a large program may contain millions of sites. SpiderMonkey bounds
each individual IC chain, but the number of distinct bodies across sites
remains an empirical question @demooij2023cacheir. Treating each site as a
distinct compilation unit would require an impractically large fixed image. An
AOT corpus is feasible only if those sites request a much smaller recurring set
of native bodies. CacheIR creates such identities by excluding site-specific
values from the body.


#subsection[CacheIR Enables IC Stub Sharing]

CacheIR explicitly separates code from data by representing an observed case as
a structural program paired with per-stub fields. The program describes guards
and fast-path operations, while the fields hold values specific to one site.
The Baseline CacheIR compiler emits instructions from the program, allowing
sites with different run-time data to share one native stub body. SpiderMonkey
already uses this representation to share Baseline stub bodies within a
JavaScript runtime @demooij2023cacheir.

@fig-cacheir-sharing illustrates this separation for property loads at two IC
sites. The receiver object enters the body as a run-time operand. Each attached
stub stores its own expected shape and slot offset at the same field indices.
The native body refers to these indices instead of embedding either site's
values, allowing sites with different receivers, shapes, and offsets to share
the same instructions. CacheIR immediates remain part of the program and thus
contribute to its executable identity.

SpiderMonkey's existing stub-code cache relies on this structural identity.
Before compiling a Baseline stub body, SpiderMonkey queries the cache using the
cache kind and exact CacheIR program. A hit attaches a new stub that holds
private fields and points to the existing body. A miss compiles the body once
and adds it to the cache @demooij2023cacheir. CacheIR thereby removes
site-specific data from the native body's identity within a runtime.


#subsection[Fixed-Corpus IC Attachment]

AmberMonkey replaces native compilation with a lookup in its fixed AOT corpus.
On an IC miss, SpiderMonkey still observes the operands, selects a CacheIR
program, and populates its stub fields. A corpus hit attaches a runtime-private
stub that points to the matching immutable body. If no AOT body matches, the
fallback computes the generic result and returns execution to the interpreter
without generating instructions.

The interpreter preserves semantic completeness, so corpus coverage affects
performance rather than correctness. Guest execution may select a precompiled
body and supply its private fields, but it cannot create or modify native
instructions. This execution model requires a recurring set of structural
identities; the following subsection measures whether such identities recur
across unrelated workloads.


#subsection[Cross-Workload Reuse]

Structural identity makes cross-site sharing possible, but a bounded corpus is
useful only if those identities recur across workloads. We test this condition
by comparing operation-level IC bodies with complete Baseline functions. A
Baseline-function identity incorporates a script's bytecode and compilation
configuration, while an IC-body identity contains only its cache kind and exact
CacheIR program.

Our experiments draw #tp6-site-count websites from Mozilla's tp6 page-load
benchmark suite @mozilla2026tp6. We use #tp6-train-site-count websites to
construct the corpus, which we call _tp6-Train_, and reserve the remaining
#tp6-test-site-count websites for held-out evaluation as _tp6-Test_.

We measure both static and directional dynamic intersection. For two workloads,
static intersection is the fraction of distinct artifact identities observed
in either workload that occur in both. For an ordered pair with corpus workload
$A$ and target workload $B$, dynamic intersection is the fraction of entries in
$B$ whose identity appeared in $A$. IC entries count executions of attached
nonfallback stubs; fallback execution is excluded. We record identities and
native-code entries during three cold page loads of the first #inter-site-count
alphabetically ordered tp6-Train workloads @mozilla2026tp6. This deterministic
subset was fixed without reference to the intersection results, and the
analysis retains only guest-script events from content processes. We pool the
three page loads rather than treating them as independent samples.
@fig-interworkload-coverage summarizes both measures.

Across workload pairs, Baseline functions have a median static intersection of
#inter-baseline-jaccard-median and a median dynamic intersection of
#inter-baseline-coverage-median. IC bodies have a median static intersection of
#inter-ic-jaccard-median and a median dynamic intersection of
#inter-ic-coverage-median. For #inter-ic-pairs-at-threshold of the
#inter-ic-offdiag-count ordered IC pairs, dynamic intersection is at least
#inter-ic-threshold-pct. Even the minimum pairwise IC dynamic intersection is
#inter-ic-min-value.

Exact reuse decreases as a compilation unit incorporates more application
context. A Baseline function combines an entire bytecode sequence, whereas an
IC body implements one operation case. CacheIR further removes shapes, offsets,
and other site-specific values from that body's identity. The measurements do
not imply that every IC body is universal, but they show that operation-level
structured bodies are a more suitable workload-derived corpus unit than
complete application functions.

Guided by this result, AmberMonkey's evaluated image contains the complete
union of #ic-stub-count bodies observed across the #tp6-train-site-count
tp6-Train workloads, occupying #ic-stub-bytes. The fixed corpus later serves
#sp3-ic-hit-rate of IC-body attachment requests on Speedometer 3.1 and
#js3-ic-hit-rate on JetStream 3.0, neither of which participates in corpus
construction. Section VI describes corpus construction, and Section VII
reports held-out coverage in detail. These attachment-request rates are
distinct from the dynamic intersection measured above.

This analysis identifies recurring IC bodies as useful AOT artifacts. The next
section addresses the separate problem of making their captured native code
independent of the runtime that generated it.

#figure(
  image("lib/figures/3-3-inter-workload-pannel.pdf", width: 100%),
  caption: [Cross-workload reuse across the first #inter-site-count tp6-Train
    workloads. (a) Pairwise static intersection: Baseline functions below the
    diagonal, IC bodies above. (b, c) Directional dynamic intersection from the
    corpus workload to the target. Operation-level ICs have substantially
    greater static and dynamic intersection than complete functions.],
  placement: top,
  scope: "parent",
) <fig-interworkload-coverage>


#section[AmberMonkey Design]

Rather than embedding runtime pointers directly in JIT code, AmberMonkey makes
them available through a per-runtime side table, the _Runtime Indirection Table_
(RIT). AOT artifacts access RIT entries at deterministic offsets that remain
stable across processes. Each runtime populates its RIT during JIT
initialization, allowing one AOT artifact to execute in multiple runtimes.
AmberMonkey resolves other external addresses through artifact-relative
references or native-linker relocations. This section describes these
resolution methods, how shared code accesses the current runtime's RIT, and
which runtime values the table can safely contain. We first illustrate the
runtime coupling that requires these mechanisms, then explain how dynamic
instrumentation affects code sharing.

#subsection[Runtime Coupling]

Baseline generation embeds concrete addresses of runtime-specific state in
native instructions. Panel (a) of @lst-code-lowering shows a simplified
Baseline generator that obtains the current runtime's interrupt flag and passes
its address to `ImmPtr`.

During generation, `ImmPtr` converts the generating runtime's flag address
into an immediate machine-code operand. Copying the emitted instructions
into a separately initialized process preserves that numeric address, which
does not identify the destination runtime's flag. The generated check requires
the current runtime's flag, not its address in the generating process. We call
this mismatch between a stable semantic role and its runtime-specific
representation _runtime coupling_.

#subsection[Resolving External Addresses]

We resolve each external address at the earliest stage that can identify it.
In the simplest case, artifact-local branches use PC-relative displacements
that remain valid when the artifact moves. AmberMonkey emits native-linker
relocations for engine functions and data with hidden visibility. Other shared
objects cannot interpose these definitions, so Firefox's linker can resolve the
references within the final library. Values that depend on a particular
runtime instead occupy fixed slots in its RIT. JIT initialization populates
these slots after creating the runtime-specific state and generated code.
@tab-runtime-dependencies summarizes these resolution methods.

#figure(
  table-from-json("0-0-runtime-dependencies.json"),
  caption: [Dependency resolution for Baseline artifacts. Runtime-generated
    targets are deterministic engine infrastructure created during trusted
    initialization, not guest-compiled code.],
  placement: top,
  scope: "column",
) <tab-runtime-dependencies>

The RIT resembles an ELF global offset table (GOT) because both store absolute
addresses in private data while keeping position-independent text shareable
@tis1995elf. A conventional GOT names symbols that a linker or loader can
resolve. Its standard relocations cannot name per-runtime contexts, runtime
caches, or JIT-generated entry points because these values have no linkable
symbols. We assign each such role a stable slot, then give every runtime a RIT
with the same layout and its own addresses.

#subsection[Accessing the RIT]

A shared artifact must locate the RIT without embedding a direct reference to
the table in its image. We considered a dedicated register, thread-local
storage (TLS), and SpiderMonkey's existing frame layouts. A dedicated register
would compete with registers already reserved for interpreter and IC state.
TLS could recover the current runtime, but a fixed TLS displacement would
couple the offline image to the platform's TLS layout and dynamic-library
loading order. AmberMonkey instead stores the RIT base at a fixed offset in the
active frame, while each table entry remains at a deterministic slot offset.

A Baseline frame records execution state for one invocation of the Baseline
Interpreter or a Baseline-compiled function. Its fields remain at fixed offsets
from the frame pointer regardless of which artifact is executing. AmberMonkey
adds the RIT base to this layout, allowing shared code to recover it with one
load while the Baseline frame remains active.

Inline-cache (IC) stubs initially execute with their caller's Baseline frame
active and therefore use the same RIT-base field. Some stubs call runtime
helpers that can trigger garbage collection. When a helper requires such a
call, SpiderMonkey creates a stub frame so stack walking can map the return
address to its bytecode location. Although a saved pointer keeps the caller's
Baseline frame reachable, obtaining the RIT base through it would require two
dependent loads. AmberMonkey copies the base into the stub frame during the
transition, allowing stub code to recover it from the active frame with one
load.

Every path that creates or reconstructs a Baseline frame initializes its
RIT-base field before shared code executes. At ordinary AOT entry, a
runtime-specific preamble loads the base into a temporary register and jumps to
the image-backed artifact. The artifact prologue then stores the base in its
Baseline frame. Runtime-generated Baseline code initializes the same field
because it may enter an image-backed IC stub. Likewise, bailout, on-stack
replacement, and generator-resume paths initialize the field when
reconstructing a frame.

Using a frame field avoids dedicating a register but repeats the base load for
each RIT access. V8 instead reserves a root register for isolate-relative
accesses @gruber2018builtins. SpiderMonkey faces the same register-pressure
trade-off for the Baseline Interpreter's bytecode program counter. While most
architectures keep the program counter in a dedicated register, the 32-bit x86
backend stores it in the frame because it lacks spare registers. Our x86-64
implementation retains SpiderMonkey's existing register contracts across
Baseline code and IC stubs. Because AArch64 provides a larger general-purpose
register set, a future port could evaluate pinning the RIT base. We have not
measured whether eliminating the base load would offset the resulting register
pressure.

The frame-based design adds one machine word to each Baseline frame and
materialized stub frame, as well as one base load to each generic RIT access. A
value lookup then loads the selected slot, while reading mutable storage through
that address requires a third dependent load. On x86-64, however, an indirect
call or jump can fold the slot read into the control-transfer instruction.

#subsection[Capturing Runtime Pointers]

AmberMonkey classifies embedded pointers at the MacroAssembler boundary,
keeping AOT capture transparent to higher-level code generators. During
capture, intercepted pointer operations reverse-map each concrete address
against the finite whitelist used to populate the RIT. A match selects either a
RIT slot or a native-linker relocation. An unrecognized pointer causes an AOT
validation build to report the missing entry and stop. Baseline and IC
generators can therefore continue to issue ordinary MacroAssembler operations
without AOT-specific logic. @lst-code-lowering illustrates this interception
and the resulting RIT access.

#code-lowering-panel(placement: top)

An address qualifies for the whitelist only if it remains fixed while its
runtime can execute AOT code. The address may differ across runtimes, and the
storage it names may remain mutable. For example, a RIT slot can hold the stable
address of a nursery cursor or profiler flag whose contents change during
execution. We call such an address _runtime-stable_.

Garbage-collected pointers additionally require a lifetime guarantee because
the immutable artifact cannot trace or update them. A SpiderMonkey atom is an
interned `JSString` cell allocated in a dedicated atoms zone. AmberMonkey admits
seven permanent common-name atoms, including the interned strings `"true"`,
`"false"`, `"null"`, and `"undefined"`. SpiderMonkey creates these atoms during
initialization and neither moves nor collects them. AmberMonkey excludes other
garbage-collected pointers that may move or be reclaimed.

#subsection[Dynamic Instrumentation]

SpiderMonkey uses patchable code to enable JavaScript debugging at run time.
The generated Baseline Interpreter contains debugger paths even in release
engine builds. This instrumentation supports debugging guest JavaScript and is
independent of native debugging support for the engine binary. A `toggledJump`
initially skips each path. On x86-64, enabling instrumentation changes the jump
into a same-sized comparison that falls through to the instrumented path.
Breakpoint and stepping sites separately replace patchable NOPs with calls to
the debug-trap handler.

AmberMonkey retains these patch sites in the image-backed Baseline Interpreter.
It does not install an image-backed Baseline function for a script already
marked as a debuggee. SpiderMonkey instead generates private code containing
the required debug instrumentation. Profiling follows a similar split.
Registering an image-backed range in the profiler's native-to-bytecode map does
not modify its instructions, whereas enabling profiler entry and exit
instrumentation patches its toggled jumps.

Patching an image-backed range reduces its sharing benefit. AmberMonkey
temporarily changes the containing `.text.aot` pages from read-execute to
read-write and restores read-execute permissions afterward. The first write
gives the process a private copy of each affected page. Debugging or profiling
therefore forfeits cross-process sharing for those pages, while unmodified
processes continue to share the original image.

#section[Implementation]

Loading an AmberMonkey artifact requires more than native instructions whose
runtime accesses pass through the RIT. SpiderMonkey's generators emit
instructions into an opaque MacroAssembler buffer while recording artifact
metadata against labels within that buffer. This metadata identifies return
addresses, debug traps, resume points, profiler sites, and IC transitions.
AmberMonkey resolves these labels to code offsets, serializes the offsets with
the instructions, and reconstructs the expected JIT objects around the
image-backed code. CacheIR records instead preserve the program and stub-layout
metadata needed for reconstruction. We obtain these records by reusing
SpiderMonkey's code generators through the transparent interception described
in Section IV. The following subsections describe the two-build image pipeline,
runtime installation and garbage-collection integration, and optimizations
that eliminate selected RIT accesses.

#subsection[Image Construction]

AmberMonkey constructs the deployed image through a recording build and a
final build. The recording build captures artifacts while executing the
self-hosted library and tp6-Train. A packing script serializes these artifacts,
and the final build embeds the resulting image in the engine library.
@fig-ambermonkey-overview summarizes this pipeline and subsequent runtime
installation.

#ambermonkey-overview(placement: top)

Each selected artifact contributes native instructions and the metadata needed
to reconstruct one SpiderMonkey JIT object. Baseline metadata identifies
control-transfer and instrumentation sites by code offset. CacheIR metadata
instead preserves the program, stub layout, and tracing information. The
packer organizes these records using the offset-based layout in
@fig-aot-image-layout. Its directory maps artifact identities to variable-sized
metadata blobs and 16-byte-aligned instruction bodies within a page-aligned
code region.

#aot-image-layout(placement: top)

AmberMonkey identifies each Baseline function with a 160-bit SHA-1 digest of
compiler-visible script state, including flags, frame and IC layout, scope
structure, and immutable bytecode metadata. SpiderMonkey's 32-bit script-data
hash only filters candidates, while installation requires full-digest equality.
The prototype does not compare canonical inputs after a
digest match, so a complete SHA-1 collision remains a limitation.

A declarative YAML schema defines the fixed fields and typed arrays for each
artifact kind. The schema generator emits padding-explicit C++ structures,
typed encoders and decoders, and compile-time checks for wire sizes, object
representations, and artifact-kind numbering. The packer incorporates the
explicit format version, schema, artifact kinds, and identities into a 160-bit
fingerprint. Schema changes therefore alter the fingerprint automatically,
while wire-format changes require an explicit version increment. A
schema-defined configuration record also captures code-generation options
embedded in the instructions. The loader rejects mismatched configurations,
including the three Spectre-mitigation options.

#subsection[Garbage-Collection Integration]

AmberMonkey preserves SpiderMonkey's JIT interfaces by representing each
image-backed instruction range with a `JitCode` wrapper. The garbage collector
manages this wrapper normally, while the static instructions remain owned by
the image and outlive the wrapper. Ordinary `JitCode` objects carry relocation
metadata for tracing embedded pointers and release their dynamically allocated
instructions during finalization.

AmberMonkey-backed `JitCode` objects require neither operation. Capture
excludes movable garbage-collected pointers, so the collector skips tracing
their instructions and finalization discards only the wrapper. The atoms-zone
code cache roots image-backed CacheIR wrappers for the runtime's lifetime,
while attached IC stubs retain ordinary tracing for their private fields.

#subsection[Optimizations]

AmberMonkey replaces some RIT accesses with native-linker relocations when a
slot names a non-interposable engine definition. During capture, the assembler
leaves a 4-byte PC-relative displacement initialized to zero and records its
offset and slot.
The packer splits the image around these sites. As shown in
@lst-image-relocation, the embedding shim copies the surrounding byte ranges
with `.incbin` and emits a linker relocation between them. Runtime-generated
and host-supplied addresses remain in the RIT.

#image-relocation-scaffold(placement: top)

AmberMonkey also mirrors the interrupt state, JIT stack limit, and count of
zones requiring pre-write barriers directly in scalar RIT slots. This removes
one dependent load from each check. Mutation paths update the mirrors, using
atomic stores when another thread may poll them. A nonzero barrier count falls
back to the precise per-zone test. We evaluate linker resolution and value
mirroring separately.

#subsection[Implementation Scope]

The x86-64 prototype covers the selected corpus and intercepted operand forms.
It adds one word to each Baseline or stub frame and a private preamble to each
image-backed Baseline artifact. Deterministic trampolines and entry preambles
remain generated during initialization. The prototype supports seven permanent
atom immediates but rejects movable garbage-collected pointers and retargetable
table entries.

The image is a trusted artifact compiled into the engine; an externally
replaceable image would require stronger validation and authentication.
Profiler or coverage instrumentation can also patch image-backed pages, making
the affected pages private and forfeiting their cross-process sharing.

#section[Experimental Methodology]

#subsection[Research Setup]

We evaluate AmberMonkey in Firefox 153.0a1 on x86-64. We compile the
default and AOT-enabled browsers from separate object directories using
Clang and LLD 21.1.8. Both are release builds with `-O2` optimization
and debug symbols. Profile-guided optimization (PGO) and link-time
optimization (LTO) are disabled in both builds.

Experiments run on an AMD Ryzen 5 7640U with 6 cores, 12 hardware
threads, and 32 GB of memory. The machine runs NixOS 26.05 with Linux
7.0.9. Web benchmarks are notoriously noisy @toufie2024osnoise, so
before collecting results we disable frequency boost, select the
`performance` frequency governor for every online processor, and take
logical processor 3 offline. This processor is the simultaneous
multithreading sibling of processor 2. We apply the same controls to
every configuration and run no other user workloads during collection.

We use the Raptor harness from the evaluated Firefox tree. Raptor
serves Speedometer 3.1 and JetStream 3.0 from the local machine. We
disable the Firefox content sandbox in every configuration so that
benchmark and AOT environment settings propagate identically to all
content processes. JetStream 3.0 retains SpiderMonkey's WebAssembly compiler,
so its results characterize restricted JavaScript execution rather than a
process with no run-time code generation.

We collect 10 independent browser runs for each configuration and
benchmark. Each Speedometer 3.1 run uses one fresh browser process and
profile for five page cycles. Each JetStream 3.0 run uses one fresh
browser process and profile for one page cycle; JetStream performs its
own repetitions within that cycle. We execute configurations in 10
randomized blocks, with each block containing one run of every
configuration. Internal benchmark iterations and page cycles are not
treated as independent samples.

For each suite, we report the arithmetic mean of its 10 independent
scores and a 95% nonparametric bootstrap confidence interval. For
pairwise comparisons, we compute a score ratio within each randomized
block and report the geometric mean of the 10 ratios with a 95%
bootstrap confidence interval. Ratios aggregated across heterogeneous
benchmark components also use the geometric mean.

#subsection[Corpus Construction]

During the recording build, we run tp6-Train and retain every distinct CacheIR
stub body that it attaches. Each record contains the cache kind and CacheIR
program that identify the body, plus the field types needed to reconstruct its
stub layout. This procedure yields #ic-stub-count bodies occupying
#ic-stub-bytes. We exclude application Baseline functions because their
identities rarely recur across workloads.

The image also contains all #self-hosted-fn-count self-hosted Baseline
functions, which are available during the build, and the deterministic
Baseline Interpreter. The packed image occupies #corpus-packed-size. We
finalize it before collecting tp6-Test, Speedometer 3.1, and JetStream 3.0
results.

#subsection[Execution Configurations]

@tab-execution-configurations defines the evaluated configurations.
Bytecode-only and AOT-only both disable run-time guest-code compilation
and retain deterministic bootstrap generation. They differ only in
whether the immutable AOT corpus supplies matching artifacts.

#figure(
  table-from-json("0-0-execution-configurations.json"),
  caption: [Execution configurations. Guest-code JIT includes Baseline-function,
    CacheIR stub-body, and optimizing compilation. Bootstrap generation comprises
    deterministic trampolines and entry preambles.],
  placement: top,
) <tab-execution-configurations>

For the indirection-cost ablation, we construct an exact corpus for the
measured workload so that every configuration executes the same
Baseline artifacts. This corpus is an experimental control rather than
a deployable configuration, and we exclude it from held-out coverage
results. We compare runtime-generated Baseline code against AOT code
with generic indirection, value mirroring, native-linker resolution, and the
complete x86-64 lowering.

#subsection[Measurement and Analysis]

We report identity coverage as the fraction of unique requested artifact
identities present in the AOT image. Request hit rate is the fraction
of dynamic artifact requests served by the AOT image. We report both
metrics per workload so that one benchmark cannot dominate the suite
summary. Generated-code bytes avoided, packed-image size, linked-binary
growth, and resident memory are reported as separate quantities.

// Before stabilizing this section:
// - Audit regular-expression and WebAssembly code generation before claiming
//   a process-wide restriction on guest-triggered executable-code generation.
// - Measure trampoline and entry-preamble generation before claiming a future
//   pure-JITless configuration.

#section[Evaluation]

We evaluate whether the fixed AOT corpus generalizes to held-out
workloads, how much performance it recovers under restricted execution,
and what overhead per-runtime indirection introduces. We then
report the image's binary-size cost and evaluate its effect on private
JIT memory and cross-process sharing.

#subsection[Corpus Coverage]

We first measure how well the corpus collected from tp6-Train generalizes to
tp6-Test, Speedometer 3.1, and JetStream 3.0. The tp6-Test set contains sites
from the same page-load suite that are disjoint from tp6-Train. Speedometer 3.1 models interactive web
applications, while JetStream 3.0 contains JavaScript and WebAssembly
workloads. None participates in corpus construction.

We report coverage separately for each of the three artifact
populations in the image. The Baseline Interpreter is a single
deterministic engine artifact that every AOT-using process loads at
startup (@tab-coverage-interp). Baseline-function and CacheIR stub
coverage are the workload-sensitive quantities and are reported in
@tab-coverage-blfun and @tab-coverage-ic. Utilization is the fraction
of corpus artifacts referenced during execution; AOT hit rate is the
fraction of dynamic requests served by the image. Values are means
across three iterations; run-to-run variance is below display
precision for these workloads and is omitted.

#figure(
  table-from-json("7-2-baseline-interpreter-table.json"),
  caption: [Baseline Interpreter coverage on tp6-Test, Speedometer 3.1, and
    JetStream 3.0. The image ships a single interpreter blob, which every
    AOT-using content process loads during image attachment.],
  placement: top,
) <tab-coverage-interp>

#figure(
  table-from-json("7-2-baseline-function-table.json"),
  caption: [Self-hosted Baseline-function coverage on tp6-Test, Speedometer
    3.1, and JetStream 3.0. Utilization: fraction of corpus functions
    installed at least once. AOT hit rate: fraction of dynamic requests
    served by the image.],
  placement: top,
) <tab-coverage-blfun>

#figure(
  table-from-json("7-2-ic-table.json"),
  caption: [CacheIR stub coverage on tp6-Test, Speedometer 3.1, and JetStream
    3.0. Utilization: fraction of corpus stubs attached at least once. Total
    attaches: every stub-attach request. AOT hit rate: fraction served by the
    image.],
  placement: top,
) <tab-coverage-ic>

The tp6-Train IC corpus serves #tp6-test-ic-hit-rate of requests on tp6-Test,
showing that it generalizes to disjoint sites from the same suite. It serves
#sp3-ic-hit-rate on Speedometer 3.1 and #js3-ic-hit-rate on JetStream 3.0.
JetStream's lower rate shows slightly less generalization to its scientific and
WebAssembly kernels.
Baseline-function coverage measures only build-time-known self-hosted functions,
not predictions of application functions.

#subsection[Restricted Execution]

@fig-amber-perf-speed3 reports Speedometer 3.1 speedup per workload for
each configuration, relative to the interpreter-only baseline; the rightmost
group is the geometric mean of the #sp3-workload-count workload ratios and
equals the aggregate-score ratio. #am execution reaches
#sp3-aot-ratio, #baseline-jit reaches #sp3-bl-ratio,
and #default-ion reaches #sp3-default-ratio. Both restricted
configurations disable guest-code JIT compilation, so their difference isolates
the performance recovered by the immutable corpus: #am recovers
#sp3-aot-over-bl-fraction of #baseline-jit throughput and reaches
#sp3-aot-default-fraction of default-tier throughput, a
#sp3-aot-speedup improvement over interpretation.

#fig(
  "lib/figures/7-3-amber-perf-speed3-workloads.pdf",
  [Speedometer 3.1 per-workload speedup over #interp-only-prose; the geomean
   of the 20 ratios is at the right. #am-ic omits AOT Baseline
   functions to isolate the IC corpus's contribution. #baseline-jit runs
   Ion-disabled runtime Baseline; #default-ion is unrestricted SpiderMonkey.
   Whiskers show per-run stdev.],
  placement: top,
  scope: "parent",
) <fig-amber-perf-speed3>

#subsection[Comparison with V8 Jitless]

V8 exposes a `--jitless` flag that disables all run-time code generation,
including its Sparkplug baseline compiler, Maglev, and TurboFan optimizing
tiers @gruber2019jitless. It serves as the closest production analogue to
AmberMonkey's restricted-execution configuration: both prohibit
guest-triggered JavaScript code emission and rely on precompiled artifacts plus
a generic interpreter to execute JavaScript. Unlike V8 Jitless, AmberMonkey
still generates deterministic infrastructure during initialization. We compare
the two engines on Speedometer 3.1 to place AmberMonkey's recovered throughput
on an absolute cross-engine footing rather than a purely intra-SpiderMonkey
ratio.

@tab-jitless-comparison reports Speedometer 3.1 scores for each engine's
default and restricted configuration, averaged over three runs. V8 Jitless
retains 66.2% of V8's default throughput, while AmberMonkey retains 57.5% of
SpiderMonkey's default throughput. Both restricted configurations sit in the
same neighborhood as fractions of their respective unrestricted tiers.

#figure(
  table-from-json("7-4-jitless-comparison.json"),
  caption: [Speedometer 3.1 scores (runs/minute, n=3) for each engine's
    default and restricted configuration. `Fraction of default` gives the
    restricted-to-default ratio within each engine.],
  placement: top,
) <tab-jitless-comparison>

#subsection[AOT Image Installation Cost]

We compare Firefox `cpstartup` on the same AOT-enabled binary with the AOT
image enabled and disabled; both retain fallback compilation. End-to-end
startup times are comparable across the two settings.
@tab-aot-attachment-cost reports per-artifact install and compile times from
the timed pairs.

#figure(
  table-from-json("aot-attachment-cost-attachment.json"),
  caption: [Per-artifact install and runtime-compile times during Firefox
    `cpstartup`, averaged across content processes. `ratio` is `µs/compile`
    over `µs/install`.],
  placement: top,
) <tab-aot-attachment-cost>

#subsection[Indirection Overhead]

We measure the steady-state cost of AOT indirection with Linux `perf stat`
hardware performance counters. Both configurations disable Ion compilation
and execute the same JavaScript source. The runtime configuration generates
Baseline machine code during execution, whereas the AOT configuration uses
`--aot-only` with an exact corpus containing the measured functions. We count
user-mode cycles, retired instructions, and reference cycles under the machine
controls described above. The analyzer rejects observations for which the
counters are missing or multiplexed.

Each microbenchmark spends nearly all of its execution in a fixed-count hot
loop. `perf stat` wraps the complete shell process, so its counts include
startup and the initial tier transition rather than sampling only the loop's
instruction addresses. The long loop amortizes these fixed costs; dividing by
the semantic iteration count yields an estimate that converges on steady-state
loop cost. We execute #indirection-repetitions fresh
#indirection-process-word per configuration. Figure labels report arithmetic
means, and whiskers show one standard deviation when multiple observations are
available. User cycles per iteration are the primary cost metric. Retired
instructions per iteration identify additional executed work, reference cycles
expose frequency drift, and instructions per cycle distinguish extra work from
reduced pipeline throughput.

We designed #indirection-benchmark-count microbenchmarks around the generated
code that AmberMonkey changes most directly. The
#indirection-targeted-count targeted kernels stress the loop interrupt check,
function-entry stack check, pre-barrier guard, VM-call path, and local ABI-call
path. These sites exercise value mirroring, the one-load VM-call lowering, and
native-linker relocation. The #indirection-control-count controls exercise
integer arithmetic, monomorphic property loads, and dense-array loads, whose
hot paths are not directly changed by those optimizations.

@fig-indirection-overhead reports the per-kernel measurements and their
geometric mean. #if indirection-reps == 1 [The preliminary pass
requires #indirection-ratio as many cycles for AOT Baseline code as for
runtime-generated Baseline code, an overhead of #indirection-overhead. With
only #indirection-repetitions process per configuration, we use this result to
validate the measurement and presentation pipeline rather than as the final
estimate.] else [Across the #indirection-benchmark-count kernels, AOT Baseline
code requires #indirection-ratio as many cycles as runtime-generated Baseline
code, a geometric-mean overhead of #indirection-overhead.]

Retired instructions and instructions per cycle (IPC) resolve where the
cycle cost comes from. AOT Baseline code retires
#indirection-ipi-overhead more instructions per iteration than
runtime-generated Baseline code, reflecting the extra loads that resolve
runtime pointers through the indirection table and mirrored scalars.
Under the same load, AOT execution reaches
#indirection-ipc-delta higher IPC, indicating that the added
instructions occupy previously idle pipeline slots rather than
extending the critical path. The cycle overhead is therefore an
instruction-count effect that partial front-end and load-store
parallelism absorb, not a loss of throughput on the original work.

#fig(
  "lib/figures/7-7-indirection-overhead.pdf",
  [#if indirection-reps == 1 [Preliminary ]User-mode cycles per iteration
   for runtime and AOT Baseline (Ion disabled, #indirection-repetitions
   fresh #indirection-process-word). Labels are means; whiskers show one
   stdev. The dotted rule separates #indirection-targeted-count
   optimization-sensitive sites from #indirection-control-count controls.
   GM is the geomean of the #indirection-benchmark-count AOT/runtime
   ratios.],
  placement: top,
) <fig-indirection-overhead>


#subsection[Cross-Process Memory Sharing]

We filter the `/proc/<pid>/smaps` entries for each Speedometer 3.1 Firefox
content process to isolate engine and JIT executable memory. We classify these
mappings as `.text.aot` (file-backed libxul pages) or anon-exec (private JIT
pages). @tab-sp3-memory reports the Peak sample across three iterations.

Under #am, `.text.aot` has a #sp3-aot-libxul-sharing RSS/PSS ratio across
#sp3-content-procs content processes. Adding the image increases its total RSS
by #sp3-image-rss-growth but its PSS by only #sp3-image-pss-growth, confirming
that processes share its physical pages. Against the tier-matched, Ion-disabled
#baseline-jit configuration, #am reduces engine PSS per process from
#sp3-runtime-per-proc-pss to #sp3-aot-per-proc-pss, a #jit-memory-reduction
reduction. We do not compare this reduction against the default configuration,
whose Ion tier changes the code profile.

#figure(
  config-table-from-json("cross-process-memory-sharing-aggregate.json"),
  caption: [Speedometer 3.1 engine memory at Peak, per configuration; means
    across three iterations. `.text.aot RSS/PSS` is the cross-process
    sharing ratio (higher = more shared). `engine PSS / proc` =
    (`.text.aot PSS` + `anon-exec PSS`) / n_procs.],
  placement: top,
) <tab-sp3-memory>


#subsection[Binary Size]

AmberMonkey increases the deployed Firefox engine binary by
#libxul-growth (#libxul-growth-pct), from #libxul-default-size to
#libxul-aot-size. We measure the file-backed `PT_LOAD` segments of
`libxul.so` with `readelf` in matched release builds; the Firefox
launcher does not contain SpiderMonkey. The embedded AOT image occupies
#aot-image-size, measured between `aot_image_start` and `aot_image_end`,
while the remaining #nonimage-growth comprises other linked code and
alignment overhead. The linker folds the `.text.aot` input section into
the executable `.text` output section.

#section[Related Work]

Partial evaluation can derive compilation by specializing an interpreter to a
fixed program @futamura1971partial. SpiderMonkey's Portable Baseline
Interpreter (PBL) executes JavaScript bytecode with CacheIR; Weval specializes
PBL for bytecode already present in a WebAssembly snapshot and combines it with
AOT IC stubs @fallin2025weval. AmberMonkey instead builds its image before guest
programs are known, so it selects engine artifacts that are deterministic or
recur across workloads rather than specializing guest bytecode.

_Reusable Inline Caching_ (RIC) carries context-independent IC information from
one execution into later executions and eagerly repopulates IC state to avoid
cold misses @choi2019ric. AmberMonkey currently attaches stubs only after a
run-time observation. Its AOT corpus makes eager attachment easier because the
native body is already materialized; the remaining problem is reconstructing
site-specific fields such as shapes and slot offsets.

ShareJIT provides Android Runtime processes with a global cache of
runtime-compiled methods and limits context-dependent optimization to improve sharing
@xu2018sharejit. AmberMonkey instead freezes selected Baseline artifacts during
a trusted build. Firefox processes map them through the engine library without
coordinating cache ownership or adding guest-generated instructions, while
private metadata and indirection tables supply per-runtime state.

GraalVM Native Image compiles reachable Java code under a closed-world
assumption, while Dart AOT produces architecture-specific machine code for a
specified Dart program @graalvm2026nativeimage @dart2025compile. Both know the
application at build time. AmberMonkey instead targets a browser engine whose
guest programs arrive after deployment and therefore precompiles reusable
engine artifacts rather than complete applications.

V8's embedded builtins place isolate-independent generated code in the
engine binary and keep isolate-specific state separate, eliminating private
builtin copies @gruber2018builtins. V8 Jitless instead disables run-time
executable memory and executes JavaScript without its JIT tiers
@gruber2019jitless. AmberMonkey applies file-backed sharing to Baseline
artifacts and uses a fixed corpus to recover native execution under a
similar restriction.

#section[Conclusion]

We have presented AmberMonkey, a generic formulation of AOT compilation for
a Baseline tier. Our preliminary evaluation indicated that three categories
of artifact may be ammenible to AOT compilation for separate reasons. IC
bodies recur across workloads. This recurrence enables a small corpus to
achieve high dynamic coverage on unseen workloads. In contrast, the
distribution for Baseline compiled functions we found much sparser across
workloads. Nonehteless, we identified a ubiquitous corpus of self-hosted
code, including JavaScript builtins, which we included in our corpus. Lastly
we identified deterministic artifacts, namely the Baseline Interpreter,
which we provided AOT to avoid redundant recompilations across processes.

#section[Future Work]

 
A model which decouples the JIT copmiling process from a respective
consumer process offers an interesting angle for offline optimization.

#linebreak()

1. _Eager IC stub attachment_: By using the initial engine invocation to
   collect profiling information regarding which IC stubs attach at
   particular script locations, we may be able to skip expsenive fallback
   stub routines through eager attachment. The utility of avoiding the
   fallback stub was elucidated by Choi et al @choi2019ric. An AOT format
   for IC stubs makes materializing the IC stub bodies convenient, however,
   a serializable format for stub paramaters such as Object Shapes forms a
   technical barrier.

#linebreak()

2. _Type Specialized Builtins_: Previous work done with V8's Torque DSL has
   demonstrated that type-specialized fast paths can improve the peformance
   of JavaScript builtins. Common operand-type patterns can establish early
   control flows independent from generic handlers, allowing more aggressive
   specialziation for Baseline code.

#pagebreak()

#bibliography("bib.yaml", style: "ieee")


#section("Draft Notes")

#NOTE("1) The 7% indirection overhead: This is done on some micro-benchmarks which specfically exercise the areas affected by AmberMonkey. Should we do a stock: `--no-ion` v.s AOT: `--aot-only` over Speedometer3 to isolate E2E Baseline tier indirection overhead? We will likely get a much lower number than 7%. Maybe 2-3%. Chase and I both found around 5% prior to slight 'optimziations'.")

#NOTE("2) Getting obvious stuff out of the way: Must run any performance benchmark with n=20 once settled upon. Experimental methodology lays out some principles I don't follow yet.")


#NOTE("4) We are missing performance metrics for how long AOT loading takes: deserialization, time filling the RIT (Runtime Indirection Table), etc.")

#NOTE("5) Related work is super incomplete.")

#NOTE("6) The Restricted Execution Performance (the main benchmark) for AmberMonkey is less strong than Ihoped for. We also have not yet turned off WASM and Regex. this could be bad.")

#NOTE("7) Figure 2. is low effort for now. I'd like to design the papers CENTRAL FIGURE here.")

#NOTE("8) The execution configurations introduced in the methodology don't necessarily line up with those used in the evaluation. There is generally too much inconsitency around what execution modes are used and their abbreviations.")

#NOTE("9) Corpus coverage for only JetStream and Speed3 is insufficient. Should add 1 or two more. Octane is a subset of JetStream unforunately. Sunspider old.")

#NOTE("11) The paper revolves around finding two baseline artifacts: IC stubs and Baseline compiled builtins, which work AOT for different reasons. Yet we only ever evaluated them in conjunction. I have separated their contributions months ago and its like 97% ICs and 3% self-hosted perf contribution.")

#NOTE("12) Can we call using the linker an optimization? Hmmm... 'Value Mirroring' sounds cool, but it breaks any GOT hardening esque hardening we could perform.")

#NOTE("15) There is a AI generated CGO review in an adjacent file.")
