# Abstract
“JavaScript engines offer restricted execution modes that prohibit
just-in-time (JIT) compilation of untrusted guest code.” -- but why

“We find that two classes of
Baseline-tier artifacts are amenable to ahead-of-time (AOT)
compilation, recovering native execution without compiling untrusted guest scripts“  -- unclear

“Inline-cache (IC) stubs are type
specialized, but their dynamic use concentrates in a recurring set: a
bounded corpus covers most stub-body requests. Both artifact classes
can therefore reside in an AOT image and be reused across runtimes.” -- you’re sort of burying the sales pitch of the paper here; call out contribution

## Introduction

- Another source of restricted execution is platform limitations. I do wonder if we should talk about that even though we’re _currently_ relying on trusted-initialization.
- We will need to re-run V8/Chrome jitless experimenation
- “With regular-expression and
WebAssembly compilation disabled, it provides restricted execution for
guest JavaScript. “ -- a footnote to explain limitations would be worthwhile here IMO.

* “We characterize the AOT availability and cross-workload reuse of
   SpiderMonkey's Baseline-tier artifacts. We find that application Baseline functions rarely recur across unrelated web workloads, whereas a recurring head of inline-cache (IC) bodies covers mo... “
  * One thing that, if we have time/space to characterize, is talking a bit about CDN scripts and shared frameworks. An immediate question a reviewer might ask is “But what about jQuery and React”
 
  * “default SpiderMonkey throughput” there’s something funky about the phrasing here; all of the variants need really clear names.
 
## Background:

- “This boundary removes the compiler” should be moved way up, and we should be trying to make the point that ‘Jit compilers are complicated and often that complexity is the root cause of the security bugs; that complexity tends not to exist in simpler layers and so JIT compilation is often required for exploitation”
- A question which occurs here: “Should we be characterizing IC transitions to generic mode? E.g. what fraction of IC stubs stop being served by an IC and instead are served by the fallback stub permanently”
- (NOT FOR PAPER) Reading Listing 1: It occurs to me that there’s a plausible SwEng reason to actually make ImmPtr crash on these kinds of pointers in debug builds, and then create a new helper `SemPtr` or “Semantic Pointer”

## Empirical Reuse

* Define / introduce tp6
* Define the various identities
* Figure 1: I don’t really follow panel (b)
* Can you characterize in more detail what’s going on with CNN because it’s surprising -- Why is CNN so well served;e.g. one possibility is that there’s basically no JS


## Ambermonkey Design

* Italicize Runtime indirection table
* Define “artifact prologue”
* What do you mean “most architectures keep the program counter in a dedicated register ,but 32-bit x86 stores it in frame” -- like architecturally this is just wrong (EIP), but I suspect you’re talking about return address or something? Very unclear sentence.
* “Capturing Runtime Pointers” -- May need a SM architecture primier to make some of this make sense
* I really appreciate your thoroughness in covering some of this, in particular around handling the patch sites and how that makes sense for debugger instrumentation. In a world where we need to cut the paper down, though, I would call out this paragraph as something we probably could drop eventually
* Corpus construction probably should actually be part of the design discussion at least.

## Experimental Methodology
- “We retain every successful run and discard a run only after a documented harness or system failure, in which case we repeat the complete block” -- This is sort of strange to call out because it makes it sound like the system is fuzzy or prone to failure -- I would drop this unless you explicitly list the kind of failure types and how they are benign to the actual implementation.
- “We apply the selection policy from Figure 1”... What policy and what figure? It's very unclear here, And at bare minimum you've got to textually describe the policy somewhere
- “... at least four tp6 sites. This rule yields 1347...” - This data seems to come from table 2 under the 10% column, which doesn't match the description of the text, which seems like it should actually be the 25% column data.

- You should set the stage on how large the Firefox binary is much earlier because one megabyte can seem very large or very small depending on what you hold it up against -- While you do bring up the size later, at this point in the paper no one has anything to compare against.

## Evaluation
- Figure 4 you can use much more informative labels on the rows of the chart, you have the room
- I really appreciate the discussion of retired instructions and instructions per cycle. I think that's really good
- We have to do something better about the memory tables to explain things. They're just not in great shape, period

- v8 v.s AM IC design, find microbenchamrks
