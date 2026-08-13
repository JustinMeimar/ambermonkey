❯ Well check for all the stupid shit. If it's code layout I am going to be ecstatic. But don't sugar coat nothing

● Ripping through the diagnostics.

  Searched for 1 pattern, listed 3 directories (ctrl+o to expand)

● No shell-release-aot.mozconfig — only shell-release. Which mozconfig does the AOT shell build actually use?

  Listed 1 directory (ctrl+o to expand)

● Drive.py uses frostmonkey/mozconfigs, not ambermonkey/mozconfigs. Diff the two mozconfigs actually consumed.

● Bash(ls /home/justin/spidermonkey/frostmonkey/mozconfigs/; echo "---"; diff
      /home/justin/spidermonkey/frostmonkey/mozconfigs/shell-release.mozconfig /home/justin/spi…)
  ⎿  browser-debug-aot.mozconfig
     browser-debug.mozconfig
     browser-release-aot.mozconfig
     … +14 lines (ctrl+o to expand)
  ⎿  Allowed by auto mode classifier

● Mozconfigs are IDENTICAL except --enable-aot and the OBJDIR name. Theory #2 (mozconfig asymmetry) is dead. Whatever the gap is, it's not
   compiler-flag drift.

  Read 1 file (ctrl+o to expand)

● Binary sizes, section layout, THP, and check that --aot is actually engaged.

● Bash(DEFAULT=/home/justin/spidermonkey/firefox/build-shell-release/dist/bin/js
      OPT=/home/justin/spidermonkey/firefox/build-shell-release-aot/dist/bin/js…)
  ⎿  === sizes ===
     -rwxr-xr-x 1 justin users 328307688 Aug  9 22:31 /home/justin/spidermonkey/firefox/build-shell-release-aot/dist/bin/js
     -rwxr-xr-x 1 justin users 325442064 Jul 26 20:02 /home/justin/spidermonkey/firefox/build-shell-release/dist/bin/js
     … +16 lines (ctrl+o to expand)
  ⎿  Allowed by auto mode classifier

● Statically linked shell (no libmozjs.so), so my "distance from mozjs" story is nonsense. .text sizes: default 24.7MB, opt 24.75MB — the
  ~1MB AOT blob is somewhere in the binary but not in a separate section. THP is madvise (not blanket-on), so both shells get 4K pages by
  default unless something explicitly madvises. Layout story is weaker than I claimed.

  Now verify --aot is actually engaged, and get HW counters.

● Bash(DEFAULT=/home/justin/spidermonkey/firefox/build-shell-release/dist/bin/js
      OPT=/home/justin/spidermonkey/firefox/build-shell-release-aot/dist/bin/js…)
  ⎿  === opt --help | grep aot ===
     Usage: /home/justin/spidermonkey/firefox/build-shell-release-aot/dist/bin/js [options] [[script] scriptArgs*]
       --aot-dump-blinterp                                Compile the baseline
     … +20 lines (ctrl+o to expand)
  ⎿  Allowed by auto mode classifier

● Bash(OPT=/home/justin/spidermonkey/firefox/build-shell-release-aot/dist/bin/js
      BENCH_INTERRUPT=/home/justin/spidermonkey/ambermonkey/fossils/7-7-indirection-microben…)
  ⎿  === bl-aot spew: does prop_load hit AOT or fall back to JIT? ===
     found tag: bl-aot
     [BaselineAOT] AOT image configuration mismatch; using runtime codegen
     … +10 lines (ctrl+o to expand)
  ⎿  Allowed by auto mode classifier

● Found it. Not sugar-coated.

  [BaselineAOT] AOT image configuration mismatch; using runtime codegen

  The AOT image is being rejected at load time. Your "AOT-opt" shell is silently falling back to runtime codegen. It has been the whole
  time. Neither of the two shells you've been benchmarking is actually running AOT-loaded code.

  So what have you actually been measuring? Let me confirm by finding the mismatch check.

● Bash(cd /home/justin/spidermonkey/firefox && grep -rn "configuration mismatch" js/src/jit/ 2>/dev/null | head -10)
  ⎿  js/src/jit/AOTInstaller.cpp:57:            "AOT image configuration mismatch; using runtime codegen");
  ⎿  Shell cwd was reset to /home/justin/spidermonkey/ambermonkey
  ⎿  Allowed by auto mode classifier

  Read 1 file (ctrl+o to expand)

● Bash(cd /home/justin/spidermonkey/firefox && grep -rn "CurrentAOTConfiguration\|AOTConfigurationMetadata" js/src/jit/*.{h,cpp}
      2>/dev/null | grep -v Generated | head…)
  ⎿  js/src/jit/AOTImage.h:340:struct AOTConfigurationMetadata {
     js/src/jit/AOTImage.h:349:  bool operator==(const AOTConfigurationMetadata& other) const = default;
     js/src/jit/AOTImage.h:352:AOTConfigurationMetadata CurrentAOTConfiguration();
     … +4 lines (ctrl+o to expand)
  ⎿  Shell cwd was reset to /home/justin/spidermonkey/ambermonkey
  ⎿  Allowed by auto mode classifier

  Read 2 files (ctrl+o to expand)

● Fingerprint compares 7 JitOptions. Which of those get changed by --blinterp-eager and --no-baseline?

● Bash(cd /home/justin/spidermonkey/firefox && grep -rn 'blinterp-eager\|no-baseline\b' js/src/shell/*.cpp js/src/jit/JitOptions.cpp
      2>/dev/null | head -30)
  ⎿  js/src/shell/js.cpp:13068:      !op.addBoolOption('\0', "no-baseline", "Disable baseline compiler") ||
     js/src/shell/js.cpp:13135:      !op.addBoolOption('\0', "blinterp-eager",
     js/src/shell/js.cpp:14257:  if (op.getBoolOption("blinterp-eager")) {
     … +3 lines (ctrl+o to expand)
  ⎿  Shell cwd was reset to /home/justin/spidermonkey/ambermonkey

  Read 1 file (ctrl+o to expand)

● --blinterp-eager / --no-baseline don't touch fingerprinted fields. So the mismatch is on one of the other 7. Let me inspect the corpus
  and see what was recorded.

  Listed 2 directories (ctrl+o to expand)

● Not a tracked task — diagnostic sweep. Try different flag combos to find one that doesn't mismatch.

● Bash(OPT=/home/justin/spidermonkey/firefox/build-shell-release-aot/dist/bin/js
      echo "=== no flags at all (except --aot) ==="…)
  ⎿  === no flags at all (except --aot) ===
     [BaselineAOT] AOT image configuration mismatch; using runtime codegen
     [BaselineAOT] AOT image configuration mismatch; using runtime codegen
     … +13 lines (ctrl+o to expand)

● Every flag combo mismatches. Not a runtime-flag issue — the corpus's baked-in fingerprint no longer matches the shell's compiled-in
  defaults. Something in the source drifted since the corpus was packed.

● Bash(cd /home/justin/spidermonkey/firefox && git log --oneline -20 js/src/jit/JitOptions.cpp js/src/jit/JitOptions.h 2>/dev/null | head
      -20; echo "---"; git log --on…)
  ⎿  55f2501a31bf impl: --aot-only needed for evals
     2ec7140ed874 update: flag to restrict aot baseline to self-hosted only
     cf6c9d5d307c patch 15/15: finalize AOT loading and configuration fingerprinting
     … +19 lines (ctrl+o to expand)
  ⎿  Shell cwd was reset to /home/justin/spidermonkey/ambermonkey

● Bash(cd /home/justin/spidermonkey/firefox && grep -n 'Configuration\|Metadata\|Fingerprint' js/src/jit/aot/PackAOTImage.py | head -20;
      echo "---"; grep -rn 'EncodeBl…)
  ⎿  ---
     js/src/jit/AOTRecorder.cpp:71:  if (!EncodeBlob_Configuration(blob, CurrentAOTConfiguration())) {
  ⎿  Shell cwd was reset to /home/justin/spidermonkey/ambermonkey

  Read 1 file, listed 1 directory (ctrl+o to expand)

● Bash(ls -la /home/justin/spidermonkey/ambermonkey/corpi/default-corpus-release/configuration.aotb; echo "---"; xxd
      /home/justin/spidermonkey/ambermonkey/corpi/defaul…)
  ⎿  -rw-r--r-- 1 justin users 72 Aug  5 15:55 /home/justin/spidermonkey/ambermonkey/corpi/default-corpus-release/configuration.aotb
     ---
     00000000: 414f 5442 0200 0000 0300 0000 0000 0000  AOTB............
     … +4 lines (ctrl+o to expand)

● Payload decodes as: disableInlining=0, spectreObjMit=1, spectreStringMit=1, baselineBatching=0, baselineJitWarmUp=100,
  baselineQueueCap=8, trialInliningWarmUp=500. Now the current defaults:

● Bash(cd /home/justin/spidermonkey/firefox && grep -nE
      'disableInlining|spectreObjectMitigations|spectreStringMitigations|baselineBatching|baselineJitWarmUpThreshold|…)
  ⎿  92:  SET_DEFAULT(disableInlining, false);
     176:  SET_DEFAULT(baselineBatching, false);
     225:  SET_DEFAULT(baselineJitWarmUpThreshold, 100);
     … +8 lines (ctrl+o to expand)
  ⎿  Shell cwd was reset to /home/justin/spidermonkey/ambermonkey
  ⎿  Allowed by auto mode classifier
  ⎿  Interrupted · What should Claude do instead?

❯ yeah bro clearly the AOT corpus i have on disk is not viable for the shell... it was dumped using the browser. But actually this kinda
  needs to be reusable for any shell-specific evals. I can't retrieve those ICs and other artifacts from just the shell

● The corpus was recorded from the browser, which defaults spectreObjectMitigations=1, spectreStringMitigations=1. The shell defaults them
   to 0. That's your mismatch — the other 5 fingerprinted fields match exactly. Two paths forward, cheapest first:

● Bash(cd /home/justin/spidermonkey/firefox && grep -n 'spectre-\|spectreMitigations\|SET_DEFAULT.*[Ss]pectre' js/src/shell/js.cpp
      js/src/jit/JitOptions.cpp 2>/dev/nul…)
  ⎿  js/src/jit/JitOptions.cpp:309:  SET_DEFAULT(spectreIndexMasking, false);
     js/src/jit/JitOptions.cpp:310:  SET_DEFAULT(spectreObjectMitigations, false);
     js/src/jit/JitOptions.cpp:311:  SET_DEFAULT(spectreStringMitigations, false);
     … +6 lines (ctrl+o to expand)
  ⎿  Shell cwd was reset to /home/justin/spidermonkey/ambermonkey
  ⎿  Allowed by auto mode classifier

  Read 1 file (ctrl+o to expand)

● Try --spectre-mitigations=on:

● Bash(OPT=/home/justin/spidermonkey/firefox/build-shell-release-aot/dist/bin/js
      echo "=== opt + --spectre-mitigations=on + --aot ==="…)
  ⎿  === opt + --spectre-mitigations=on + --aot ===
     found tag: bl-aot
     [BaselineAOT] AOT IC stubs loaded=1347 attempted=1347
     … +5 lines (ctrl+o to expand)
  ⎿  Allowed by auto mode classifier

● Confirmed. Root cause pinpointed.

  The corpus was recorded from a browser build where spectreObjectMitigations=1, spectreStringMitigations=1 (browser needs Spectre
  defenses for untrusted content). The shell defaults both to 0. Every other fingerprinted field matches exactly. That's why every flag
  combination we tried mismatched — the shell binary can never satisfy a browser-recorded corpus without opting into Spectre.

  Adding --spectre-mitigations=on fixes it: AOT IC stubs loaded=1347 attempted=1347, interpreter bytes=19111 installed from AOT image.
  Clean load.

  What this means for what we've been measuring

  All the previous numbers are void. Both default and opt shells were running runtime-JIT'd codegen the entire time. What we've actually
  been measuring is:

  - opt shell: runtime codegen using the modified macroassembler (perf 1/3/5/6/n applied to the shared codegen path, not just the AOT
  emission)
  - default shell: runtime codegen using the unmodified macroassembler

  Which is why control benches also showed the gap — the perf commits touch shared macroassembler code, not AOT-only paths. Still a real
  finding (perf commits speed up runtime codegen too), but not the AOT-indirection-cost story the fossil was built for.

  The structural problem you flagged

  You're right that this isn't cleanly fixable by re-recording — you fundamentally need the browser to hit real ICs, but the browser and
  shell disagree on Spectre defaults (and probably other defaults down the road). Two ways to reconcile:

  A. Pin the shell to browser defaults for AOT runs (cheap, correct). Add --spectre-mitigations=on to both FLAGS_AOT and FLAGS_DEFAULT so
  the ONLY difference between shells is --aot. Both shells then pay Spectre cost; the delta is pure AOT.

  B. Loosen the fingerprint (dangerous). The Spectre fields DO change baseline codegen — index bounds masking, object type check masking,
  value poisoning on IC transitions. If you load an AOT IC stub compiled without index masking into a shell that expects masking, you've
  silently disabled a mitigation the runtime thinks it has. Even for a research shell that's a footgun; it also means the loaded stubs
  won't match what the runtime fallback emits, so recording-time vs fallback-time codegen diverge. Not recommended.

  Long-term, if you want per-shell/per-corpus reuse, the honest fix is to make the fingerprint include what actually affects the encoded
  artifacts — then per-field decide whether a difference is a mismatch or safely coercible. That's a real design chunk though; probably
  not this session.

  Immediate action

  Update fossil.toml to add --spectre-mitigations=on to both flag sets, verify AOT loads on all 8 benches (via bl-aot spew), then bury.
  Want me to make the edit and run the confirmation?
❯ Well check for all the stupid shit. If it's code layout I am going to be ecstatic. But don't sugar coat nothing

● Ripping through the diagnostics.

  Searched for 1 pattern, listed 3 directories (ctrl+o to expand)

● No shell-release-aot.mozconfig — only shell-release. Which mozconfig does the AOT shell build actually use?

  Listed 1 directory (ctrl+o to expand)

● Drive.py uses frostmonkey/mozconfigs, not ambermonkey/mozconfigs. Diff the two mozconfigs actually consumed.

● Bash(ls /home/justin/spidermonkey/frostmonkey/mozconfigs/; echo "---"; diff
      /home/justin/spidermonkey/frostmonkey/mozconfigs/shell-release.mozconfig /home/justin/spi…)
  ⎿  browser-debug-aot.mozconfig
     browser-debug.mozconfig
     browser-release-aot.mozconfig
     … +14 lines (ctrl+o to expand)
  ⎿  Allowed by auto mode classifier

● Mozconfigs are IDENTICAL except --enable-aot and the OBJDIR name. Theory #2 (mozconfig asymmetry) is dead. Whatever the gap is, it's not
   compiler-flag drift.

  Read 1 file (ctrl+o to expand)

● Binary sizes, section layout, THP, and check that --aot is actually engaged.

● Bash(DEFAULT=/home/justin/spidermonkey/firefox/build-shell-release/dist/bin/js
      OPT=/home/justin/spidermonkey/firefox/build-shell-release-aot/dist/bin/js…)
  ⎿  === sizes ===
     -rwxr-xr-x 1 justin users 328307688 Aug  9 22:31 /home/justin/spidermonkey/firefox/build-shell-release-aot/dist/bin/js
     -rwxr-xr-x 1 justin users 325442064 Jul 26 20:02 /home/justin/spidermonkey/firefox/build-shell-release/dist/bin/js
     … +16 lines (ctrl+o to expand)
  ⎿  Allowed by auto mode classifier

● Statically linked shell (no libmozjs.so), so my "distance from mozjs" story is nonsense. .text sizes: default 24.7MB, opt 24.75MB — the
  ~1MB AOT blob is somewhere in the binary but not in a separate section. THP is madvise (not blanket-on), so both shells get 4K pages by
  default unless something explicitly madvises. Layout story is weaker than I claimed.

  Now verify --aot is actually engaged, and get HW counters.

● Bash(DEFAULT=/home/justin/spidermonkey/firefox/build-shell-release/dist/bin/js
      OPT=/home/justin/spidermonkey/firefox/build-shell-release-aot/dist/bin/js…)
  ⎿  === opt --help | grep aot ===
     Usage: /home/justin/spidermonkey/firefox/build-shell-release-aot/dist/bin/js [options] [[script] scriptArgs*]
       --aot-dump-blinterp                                Compile the baseline
     … +20 lines (ctrl+o to expand)
  ⎿  Allowed by auto mode classifier

● Bash(OPT=/home/justin/spidermonkey/firefox/build-shell-release-aot/dist/bin/js
      BENCH_INTERRUPT=/home/justin/spidermonkey/ambermonkey/fossils/7-7-indirection-microben…)
  ⎿  === bl-aot spew: does prop_load hit AOT or fall back to JIT? ===
     found tag: bl-aot
     [BaselineAOT] AOT image configuration mismatch; using runtime codegen
     … +10 lines (ctrl+o to expand)
  ⎿  Allowed by auto mode classifier

● Found it. Not sugar-coated.

  [BaselineAOT] AOT image configuration mismatch; using runtime codegen

  The AOT image is being rejected at load time. Your "AOT-opt" shell is silently falling back to runtime codegen. It has been the whole
  time. Neither of the two shells you've been benchmarking is actually running AOT-loaded code.

  So what have you actually been measuring? Let me confirm by finding the mismatch check.

● Bash(cd /home/justin/spidermonkey/firefox && grep -rn "configuration mismatch" js/src/jit/ 2>/dev/null | head -10)
  ⎿  js/src/jit/AOTInstaller.cpp:57:            "AOT image configuration mismatch; using runtime codegen");
  ⎿  Shell cwd was reset to /home/justin/spidermonkey/ambermonkey
  ⎿  Allowed by auto mode classifier

  Read 1 file (ctrl+o to expand)

● Bash(cd /home/justin/spidermonkey/firefox && grep -rn "CurrentAOTConfiguration\|AOTConfigurationMetadata" js/src/jit/*.{h,cpp}
      2>/dev/null | grep -v Generated | head…)
  ⎿  js/src/jit/AOTImage.h:340:struct AOTConfigurationMetadata {
     js/src/jit/AOTImage.h:349:  bool operator==(const AOTConfigurationMetadata& other) const = default;
     js/src/jit/AOTImage.h:352:AOTConfigurationMetadata CurrentAOTConfiguration();
     … +4 lines (ctrl+o to expand)
  ⎿  Shell cwd was reset to /home/justin/spidermonkey/ambermonkey
  ⎿  Allowed by auto mode classifier

  Read 2 files (ctrl+o to expand)

● Fingerprint compares 7 JitOptions. Which of those get changed by --blinterp-eager and --no-baseline?

● Bash(cd /home/justin/spidermonkey/firefox && grep -rn 'blinterp-eager\|no-baseline\b' js/src/shell/*.cpp js/src/jit/JitOptions.cpp
      2>/dev/null | head -30)
  ⎿  js/src/shell/js.cpp:13068:      !op.addBoolOption('\0', "no-baseline", "Disable baseline compiler") ||
     js/src/shell/js.cpp:13135:      !op.addBoolOption('\0', "blinterp-eager",
     js/src/shell/js.cpp:14257:  if (op.getBoolOption("blinterp-eager")) {
     … +3 lines (ctrl+o to expand)
  ⎿  Shell cwd was reset to /home/justin/spidermonkey/ambermonkey

  Read 1 file (ctrl+o to expand)

● --blinterp-eager / --no-baseline don't touch fingerprinted fields. So the mismatch is on one of the other 7. Let me inspect the corpus
  and see what was recorded.

  Listed 2 directories (ctrl+o to expand)

● Not a tracked task — diagnostic sweep. Try different flag combos to find one that doesn't mismatch.

● Bash(OPT=/home/justin/spidermonkey/firefox/build-shell-release-aot/dist/bin/js
      echo "=== no flags at all (except --aot) ==="…)
  ⎿  === no flags at all (except --aot) ===
     [BaselineAOT] AOT image configuration mismatch; using runtime codegen
     [BaselineAOT] AOT image configuration mismatch; using runtime codegen
     … +13 lines (ctrl+o to expand)

● Every flag combo mismatches. Not a runtime-flag issue — the corpus's baked-in fingerprint no longer matches the shell's compiled-in
  defaults. Something in the source drifted since the corpus was packed.

● Bash(cd /home/justin/spidermonkey/firefox && git log --oneline -20 js/src/jit/JitOptions.cpp js/src/jit/JitOptions.h 2>/dev/null | head
      -20; echo "---"; git log --on…)
  ⎿  55f2501a31bf impl: --aot-only needed for evals
     2ec7140ed874 update: flag to restrict aot baseline to self-hosted only
     cf6c9d5d307c patch 15/15: finalize AOT loading and configuration fingerprinting
     … +19 lines (ctrl+o to expand)
  ⎿  Shell cwd was reset to /home/justin/spidermonkey/ambermonkey

● Bash(cd /home/justin/spidermonkey/firefox && grep -n 'Configuration\|Metadata\|Fingerprint' js/src/jit/aot/PackAOTImage.py | head -20;
      echo "---"; grep -rn 'EncodeBl…)
  ⎿  ---
     js/src/jit/AOTRecorder.cpp:71:  if (!EncodeBlob_Configuration(blob, CurrentAOTConfiguration())) {
  ⎿  Shell cwd was reset to /home/justin/spidermonkey/ambermonkey

  Read 1 file, listed 1 directory (ctrl+o to expand)

● Bash(ls -la /home/justin/spidermonkey/ambermonkey/corpi/default-corpus-release/configuration.aotb; echo "---"; xxd
      /home/justin/spidermonkey/ambermonkey/corpi/defaul…)
  ⎿  -rw-r--r-- 1 justin users 72 Aug  5 15:55 /home/justin/spidermonkey/ambermonkey/corpi/default-corpus-release/configuration.aotb
     ---
     00000000: 414f 5442 0200 0000 0300 0000 0000 0000  AOTB............
     … +4 lines (ctrl+o to expand)

● Payload decodes as: disableInlining=0, spectreObjMit=1, spectreStringMit=1, baselineBatching=0, baselineJitWarmUp=100,
  baselineQueueCap=8, trialInliningWarmUp=500. Now the current defaults:

● Bash(cd /home/justin/spidermonkey/firefox && grep -nE
      'disableInlining|spectreObjectMitigations|spectreStringMitigations|baselineBatching|baselineJitWarmUpThreshold|…)
  ⎿  92:  SET_DEFAULT(disableInlining, false);
     176:  SET_DEFAULT(baselineBatching, false);
     225:  SET_DEFAULT(baselineJitWarmUpThreshold, 100);
     … +8 lines (ctrl+o to expand)
  ⎿  Shell cwd was reset to /home/justin/spidermonkey/ambermonkey
  ⎿  Allowed by auto mode classifier
  ⎿  Interrupted · What should Claude do instead?

❯ yeah bro clearly the AOT corpus i have on disk is not viable for the shell... it was dumped using the browser. But actually this kinda
  needs to be reusable for any shell-specific evals. I can't retrieve those ICs and other artifacts from just the shell

● The corpus was recorded from the browser, which defaults spectreObjectMitigations=1, spectreStringMitigations=1. The shell defaults them
   to 0. That's your mismatch — the other 5 fingerprinted fields match exactly. Two paths forward, cheapest first:

● Bash(cd /home/justin/spidermonkey/firefox && grep -n 'spectre-\|spectreMitigations\|SET_DEFAULT.*[Ss]pectre' js/src/shell/js.cpp
      js/src/jit/JitOptions.cpp 2>/dev/nul…)
  ⎿  js/src/jit/JitOptions.cpp:309:  SET_DEFAULT(spectreIndexMasking, false);
     js/src/jit/JitOptions.cpp:310:  SET_DEFAULT(spectreObjectMitigations, false);
     js/src/jit/JitOptions.cpp:311:  SET_DEFAULT(spectreStringMitigations, false);
     … +6 lines (ctrl+o to expand)
  ⎿  Shell cwd was reset to /home/justin/spidermonkey/ambermonkey
  ⎿  Allowed by auto mode classifier

  Read 1 file (ctrl+o to expand)

● Try --spectre-mitigations=on:

● Bash(OPT=/home/justin/spidermonkey/firefox/build-shell-release-aot/dist/bin/js
      echo "=== opt + --spectre-mitigations=on + --aot ==="…)
  ⎿  === opt + --spectre-mitigations=on + --aot ===
     found tag: bl-aot
     [BaselineAOT] AOT IC stubs loaded=1347 attempted=1347
     … +5 lines (ctrl+o to expand)
  ⎿  Allowed by auto mode classifier

● Confirmed. Root cause pinpointed.

  The corpus was recorded from a browser build where spectreObjectMitigations=1, spectreStringMitigations=1 (browser needs Spectre
  defenses for untrusted content). The shell defaults both to 0. Every other fingerprinted field matches exactly. That's why every flag
  combination we tried mismatched — the shell binary can never satisfy a browser-recorded corpus without opting into Spectre.

  Adding --spectre-mitigations=on fixes it: AOT IC stubs loaded=1347 attempted=1347, interpreter bytes=19111 installed from AOT image.
  Clean load.

  What this means for what we've been measuring

  All the previous numbers are void. Both default and opt shells were running runtime-JIT'd codegen the entire time. What we've actually
  been measuring is:

  - opt shell: runtime codegen using the modified macroassembler (perf 1/3/5/6/n applied to the shared codegen path, not just the AOT
  emission)
  - default shell: runtime codegen using the unmodified macroassembler

  Which is why control benches also showed the gap — the perf commits touch shared macroassembler code, not AOT-only paths. Still a real
  finding (perf commits speed up runtime codegen too), but not the AOT-indirection-cost story the fossil was built for.

  The structural problem you flagged

  You're right that this isn't cleanly fixable by re-recording — you fundamentally need the browser to hit real ICs, but the browser and
  shell disagree on Spectre defaults (and probably other defaults down the road). Two ways to reconcile:

  A. Pin the shell to browser defaults for AOT runs (cheap, correct). Add --spectre-mitigations=on to both FLAGS_AOT and FLAGS_DEFAULT so
  the ONLY difference between shells is --aot. Both shells then pay Spectre cost; the delta is pure AOT.

  B. Loosen the fingerprint (dangerous). The Spectre fields DO change baseline codegen — index bounds masking, object type check masking,
  value poisoning on IC transitions. If you load an AOT IC stub compiled without index masking into a shell that expects masking, you've
  silently disabled a mitigation the runtime thinks it has. Even for a research shell that's a footgun; it also means the loaded stubs
  won't match what the runtime fallback emits, so recording-time vs fallback-time codegen diverge. Not recommended.

  Long-term, if you want per-shell/per-corpus reuse, the honest fix is to make the fingerprint include what actually affects the encoded
  artifacts — then per-field decide whether a difference is a mismatch or safely coercible. That's a real design chunk though; probably
  not this session.

  Immediate action

  Update fossil.toml to add --spectre-mitigations=on to both flag sets, verify AOT loads on all 8 benches (via bl-aot spew), then bury.
  Want me to make the edit and run the confirmation?






  Read 1 file (ctrl+o to expand)

● Every caller guards on useAOTImage before calling IsAOTImageCompatible, so any failure inside it is exactly the "silently switched to
  runtime codegen" case. Converting all three failure paths to MOZ_CRASH will make --aot fail loudly.

● Update(~/spidermonkey/firefox/js/src/jit/AOTInstaller.cpp)
  ⎿  Added 24 lines, removed 8 lines
      43  static bool IsAOTImageCompatible(const AOTImage* image) {
      44    auto readerOpt = image->findUnique(AOTBlobKind::Configuration);
      45    if (readerOpt.isNothing()) {
      46 -    JitSpew(JitSpew_BaselineAOT, "AOT image lacks configuration metadata");
      47 -    return false;
      46 +    MOZ_CRASH("AOT image lacks configuration metadata");
      47    }
      48    AOTBlobReader reader = readerOpt.ref();
      49    AOTConfigurationMetadata recorded;
      50    if (!DecodeBlob_Configuration(reader, &recorded)) {
      52 -    JitSpew(JitSpew_BaselineAOT, "AOT image configuration decode failed");
      53 -    return false;
      51 +    MOZ_CRASH("AOT image configuration decode failed");
      52    }
      55 -  if (recorded != CurrentAOTConfiguration()) {
      56 -    JitSpew(JitSpew_BaselineAOT,
      57 -            "AOT image configuration mismatch; using runtime codegen");
      58 -    return false;
      53 +  AOTConfigurationMetadata current = CurrentAOTConfiguration();
      54 +  if (recorded != current) {
      55 +    fprintf(stderr,
      56 +            "AOT image configuration mismatch:\n"
      57 +            "  field                          recorded  current\n"
      58 +            "  disableInlining                %8u  %8u\n"
      59 +            "  spectreObjectMitigations       %8u  %8u\n"
      60 +            "  spectreStringMitigations       %8u  %8u\n"
      61 +            "  baselineBatching               %8u  %8u\n"
      62 +            "  baselineJitWarmUpThreshold     %8u  %8u\n"
      63 +            "  baselineQueueCapacity          %8u  %8u\n"
      64 +            "  trialInliningWarmUpThreshold   %8u  %8u\n",
      65 +            recorded.disableInlining, current.disableInlining,
      66 +            recorded.spectreObjectMitigations, current.spectreObjectMitigations,
      67 +            recorded.spectreStringMitigations, current.spectreStringMitigations,
      68 +            recorded.baselineBatching, current.baselineBatching,
      69 +            recorded.baselineJitWarmUpThreshold,
      70 +            current.baselineJitWarmUpThreshold,
      71 +            recorded.baselineQueueCapacity, current.baselineQueueCapacity,
      72 +            recorded.trialInliningWarmUpThreshold,
      73 +            current.trialInliningWarmUpThreshold);
      74 +    MOZ_CRASH("AOT image configuration mismatch");
      75    }
      76    return true;
      77  }

● Rebuild the AOT shell and verify the crash fires with a helpful diagnostic. Backgrounding the build since it's slow.

● Bash(cd /home/justin/spidermonkey/firefox && just build build-shell-release-aot 2>&1 | tail -20)
  ⎿  Running in the background (↓ to manage)
  ⎿  Allowed by auto mode classifier
  ⎿  Found 2 new diagnostic issues in 1 file (ctrl+o to expand)

● Pre-existing lint warnings, not mine. Waiting on build.

  Listed 1 directory (ctrl+o to expand)

● Build is harness-tracked; I'll be notified when done.

● Bash(echo "waiting")
  ⎿  waiting

● Background command "Rebuild AOT shell with new mismatch crash" completed (exit code 0)

● Build done. Verify the crash fires with a helpful diff on mismatch, and that the good-flags path still loads clean.

● Bash(OPT=/home/justin/spidermonkey/firefox/build-shell-release-aot/dist/bin/js
      echo "=== 1. bad path: --aot without --spectre-mitigations=on -> should crash with dif…)
  ⎿  === 1. bad path: --aot without --spectre-mitigations=on -> should crash with diff ===
     AOT image configuration mismatch:
       field                          recorded  current
     … +16 lines (ctrl+o to expand)
  ⎿  Allowed by auto mode classifier

● Diagnostic diff is printed. Verify the process actually aborts (my head pipe swallowed the exit code):

● Bash(OPT=/home/justin/spidermonkey/firefox/build-shell-release-aot/dist/bin/js
      $OPT --aot --blinterp-eager --no-baseline -e 'print(1+1)' >/tmp/aot-crash.out 2>&1…)
  ⎿  exit code: 139
     signal (rc>128): 11
       spectreStringMitigations              1         0
     … +4 lines (ctrl+o to expand)
  ⎿  Allowed by auto mode classifier

● Working as intended:

  - Bad path (--aot without --spectre-mitigations=on): prints per-field recorded-vs-current diff, then SIGSEGV (exit 139 = signal 11,
  MOZ_CRASH's release-mode hard abort). No silent fallback.
  - Good path (--aot --spectre-mitigations=on): loads clean, prints result.
  - No --aot: unchanged.

  Change is in js/src/jit/AOTInstaller.cpp:43-77 — IsAOTImageCompatible now MOZ_CRASHes on all three failure modes (missing metadata,
  decode failure, mismatch) instead of returning false. Every caller was already guarded on JitOptions.useAOTImage, so the crash only
  fires when --aot was explicitly requested.

  The mismatch diff prints to stderr before the crash so you immediately see WHICH fields diverged — in our case, spectreObjectMitigations
   and spectreStringMitigations are the browser-vs-shell delta. Any future drift (someone changes a JitOptions default, adds a new
  fingerprinted field, etc.) surfaces the same way.

  Ball's in your court on whether to (a) roll --spectre-mitigations=on into the fossil flags and re-run, or (b) rethink the
  fingerprint/corpus reusability question first.

✻ Sautéed for 2m 5s
