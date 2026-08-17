
#let fig-desc(body, title: "Figure description") = block(
  fill: luma(245),
  stroke: (left: 3pt + luma(180)),
  inset: (x: 12pt, y: 10pt),
  radius: 2pt,
  width: 100%,
  [
    #text(size: 9pt, weight: "bold", fill: luma(80), tracking: 0.5pt)[
      #upper(title)
    ]
    #v(4pt, weak: true)
    #body
  ],
)

#let eval-desc(body, title: "Evaluation") = block(
  fill: luma(245),
  stroke: (left: 3pt + luma(140)),
  inset: (x: 12pt, y: 10pt),
  radius: 2pt,
  width: 100%,
  [
    #text(size: 9pt, weight: "bold", fill: luma(80), tracking: 0.5pt)[
      #upper(title)
    ]
    #v(4pt, weak: true)
    #body
  ],
)

#let _overview-box(title, body, stroke: luma(145), fill: white) = block(
  width: 100%,
  inset: 6pt,
  stroke: 0.6pt + stroke,
  fill: fill,
  radius: 2pt,
  [
    #align(center)[#text(size: 7.5pt, weight: "bold")[#title]]
    #v(3pt)
    #text(size: 7pt)[#body]
  ],
)

#let ambermonkey-overview(placement: top) = [
  #figure(
    grid(
      columns: (1fr, auto, 1fr, auto, 1.15fr),
      gutter: 7pt,
      align: horizon,
      _overview-box(
        [1. Capture],
        [Baseline code generators #linebreak()
         $arrow.r$ AOT-aware assembler #linebreak()
         $arrow.r$ code and reconstruction metadata],
      ),
      text(size: 12pt)[$arrow.r$],
      _overview-box(
        [2. Build image],
        [Select and pack artifacts #linebreak()
         $arrow.r$ serialize typed metadata #linebreak()
         $arrow.r$ form page-aligned image],
        stroke: luma(85),
      ),
      text(size: 12pt)[$arrow.r$],
      _overview-box(
        [3. Bind runtimes],
        [*Shared:* one image-backed text range #linebreak()
         *Runtime A:* metadata + table A #linebreak()
         *Runtime B:* metadata + table B],
      ),
    ),
    kind: image,
    supplement: [Figure],
    caption: [AmberMonkey captures code from SpiderMonkey's existing Baseline
      code generators, packs selected artifacts into an immutable image, and
      binds runtime dependencies separately for each runtime. Runtime-private
      wrappers and tables refer to the same file-backed instruction ranges
      without copying their bytes.],
    placement: placement,
    scope: "parent",
  ) <fig-ambermonkey-overview>
]

#let cacheir-sharing-example(placement: top) = {
  show raw.where(block: true): set text(
    font: "DejaVu Sans Mono",
    size: 6.2pt,
  )

  let program = ```text
  object = GuardToObject(input)
  GuardShape(object, field 0)
  result = LoadFixedSlot(object, field 1)
  Return(result)
  ```

  [
    #figure(
      block(
        width: 100%,
        inset: (x: 6pt, y: 4pt),
        [
          #_overview-box(
            [Shared CacheIR identity],
            [
              #text(size: 6.7pt)[*Cache kind:* property load]
              #v(2pt)
              #raw(program.text, lang: "text", block: true, theme: none)
              #text(size: 6.7pt)[*Field layout:* shape, integer offset]
            ],
            fill: luma(247),
            stroke: luma(85),
          )
          #align(center)[
            #text(size: 6.7pt)[Baseline CacheIR compilation]
            #linebreak()
            #text(size: 10pt)[↓]
          ]
          #_overview-box(
            [One native stub body],
            [Loads both values from the current stub's private field vector.],
            fill: luma(238),
            stroke: luma(85),
          )
          #v(3pt)
          #align(center)[#text(size: 6.7pt)[Both IC sites call the same body]]
          #v(2pt)
          #grid(
            columns: (1fr, 1fr),
            gutter: 7pt,
            _overview-box(
              [Site A: private fields],
              [`field 0 = Shape A` #linebreak()
               `field 1 = offset 16`],
            ),
            _overview-box(
              [Site B: private fields],
              [`field 0 = Shape B` #linebreak()
               `field 1 = offset 32`],
            ),
          )
        ],
      ),
      kind: image,
      supplement: [Figure],
      caption: [CacheIR separates a fast path's structural identity from its
        site-specific values. The Baseline CacheIR compiler emits one native
        body for the shared program and field layout. Each IC site supplies a
        private field vector when it executes that body. Program syntax and
        values are schematic.],
      placement: placement,
      scope: "column",
    ) <fig-cacheir-sharing>
  ]
}

#let _image-layout-region(title, detail, fill: white, stroke: luma(145), inset: 4pt) = block(
  width: 100%,
  inset: inset,
  stroke: 0.6pt + stroke,
  fill: fill,
  radius: 1.5pt,
  [
    #align(center)[#text(size: 7.2pt, weight: "bold")[#title]]
    #v(1.5pt)
    #align(center)[#text(size: 6.7pt)[#detail]]
  ],
)

#let aot-image-layout(placement: none) = [
  #figure(
    block(
      width: 100%,
      inset: (x: 10pt, y: 5pt),
      grid(
        columns: (1fr,),
        row-gutter: 2.5pt,
        _image-layout-region(
          [Image header],
          [Format version, artifact count, and region offsets],
          fill: luma(247),
        ),
        _image-layout-region(
          [160-bit fingerprint],
          [Format, schema, artifact kinds, and identities],
        ),
        _image-layout-region(
          [Artifact directory],
          [Kind, identity, metadata range, and code range],
          fill: luma(247),
        ),
        _image-layout-region(
          [Schema-defined metadata blobs],
          [Fixed fields followed by typed arrays],
        ),
        _image-layout-region(
          [Page-alignment padding],
          [Code region begins at a 4 KiB boundary],
          fill: luma(247),
          inset: 2.5pt,
        ),
        _image-layout-region(
          [Code region],
          [Concatenated, 16-byte-aligned instruction bodies],
          fill: luma(235),
          stroke: luma(85),
        ),
      ),
    ),
    kind: image,
    supplement: [Figure],
    caption: [Packed AmberMonkey image. Directory entries map artifact
      identities to schema-defined metadata and instruction bodies. Page
      alignment places the immutable code in a distinct region.],
    placement: placement,
    scope: "column",
  ) <fig-aot-image-layout>
]

#let image-relocation-scaffold(placement: none) = {
  show raw.where(block: true): set text(
    font: "DejaVu Sans Mono",
    size: 7pt,
  )

  let source = ```asm
  .set link_site, 241452
  .section .text.aot,"ax",@progbits
  .incbin "AOTImage.inc", 0, link_site
  .long engine_symbol - . - 4
  .incbin "AOTImage.inc", link_site + 4
  ```

  [
    #figure(
      block(
        width: 100%,
        inset: (x: 8pt, y: 5pt),
        raw(source.text, lang: "asm", block: true, theme: none),
      ),
      kind: raw,
      supplement: [Listing],
      caption: [Equivalent assembly for one link site. The two `.incbin`
        directives omit the recorded 4-byte zero field, which `.long` replaces
        with a PC-relative relocation.],
      placement: placement,
    ) <lst-image-relocation>
  ]
}

#let _fig(path, caption, placement: none, width: auto, height: auto, scope: "column") = {
  let w = if width == auto and height == auto { 100% } else { width }
  figure(
    image(path, width: w, height: height),
    caption: caption,
    placement: placement,
    scope: scope,
  )
}

#let _listing-panel(title, source, lang, emphasis: none) = {
  show raw.line: line => {
    if emphasis != none and line.text.contains(emphasis) {
      let parts = line.text.split(emphasis)
      text(font: "DejaVu Sans Mono", size: 7pt, parts.first())
      text(
        font: "DejaVu Sans Mono",
        size: 7pt,
        weight: "bold",
        emphasis,
      )
      text(
        font: "DejaVu Sans Mono",
        size: 7pt,
        parts.slice(1).join(emphasis),
      )
    } else {
      line
    }
  }

  block(
    width: 100%,
    height: 1.15in,
    inset: (x: 5pt, y: 4pt),
    [
      #align(center)[
        #text(size: 7.5pt, weight: "bold")[#title]
      ]
      #v(5pt)
      #raw(source, lang: lang, block: true, theme: none, tab-size: 2)
    ],
  )
}

#let code-lowering-panel(placement: top) = {
  show raw.where(block: true): set text(
    font: "DejaVu Sans Mono",
    size: 7pt,
  )

  let generator = ```cpp
  void emitCheck(Masm& masm, Reg out) {
    auto* flag = cx->interruptFlag();
    masm.movePtr(ImmPtr(flag), out);
    masm.branch32(NonZero,
      Address(out, 0), &interrupt);
  }
  ```

  let capture = ```cpp
  void movePtr(ImmPtr p, Reg dst) {
    if (auto slot = findSlot(p)) {
      emitLoadSlot(*slot, dst);
      return;
    }
    reportUnknownPointer(p);
  }
  ```

  let emitted = ```asm
  # Before
  movabsq $flag, %rax
  cmpl    $0, (%rax)
  # After
  movq -24(%rbp), %r11  # table
  movq  48(%r11), %rax # slot
  cmpl  $0, (%rax)
  ```

  [
    #figure(
      grid(
        columns: (1fr, 1fr, 1fr),
        gutter: 10pt,
        align: top,
        _listing-panel(
          [(a) Baseline code generator],
          generator.text,
          "cpp",
          emphasis: "ImmPtr(flag)",
        ),
        _listing-panel(
          [(b) Simplified lowering],
          capture.text,
          "cpp",
          emphasis: "emitLoadSlot",
        ),
        _listing-panel([(c) Schematic x86-64], emitted.text, "asm"),
      ),
      kind: raw,
      supplement: [Listing],
      caption: [Simplified illustration of transparent runtime-pointer
        lowering. Panel (a) represents Baseline Interpreter code generation
        with no AOT-specific logic. The MacroAssembler reverse-maps its direct
        pointer in panel (b) and emits the RIT access shown in panel (c).
        Identifiers and offsets are schematic.],
      placement: placement,
      scope: "parent",
    ) <lst-code-lowering>
  ]
}

#let runtime-coupling-example(placement: top) = {
  show raw.where(block: true): set text(
    font: "DejaVu Sans Mono",
    size: 7pt,
  )

  let emphasis = "ImmPtr(&runtime->wellKnownSymbols())"
  show raw.line: line => {
    if line.text.contains(emphasis) {
      let parts = line.text.split(emphasis)
      text(font: "DejaVu Sans Mono", size: 7pt, parts.first())
      text(
        font: "DejaVu Sans Mono",
        size: 7pt,
        weight: "bold",
        emphasis,
      )
      text(
        font: "DejaVu Sans Mono",
        size: 7pt,
        parts.slice(1).join(emphasis),
      )
    } else {
      line
    }
  }

  let source = ```cpp
  LoadUint8Operand(masm, scratch1);
  masm.movePtr(
      ImmPtr(&runtime->wellKnownSymbols()), scratch2);
  masm.loadPtr(
      BaseIndex(scratch2, scratch1, ScalePointer), scratch1);
  // ...
  ```

  [
    #figure(
      block(
        width: 100%,
        inset: (top: 5pt, bottom: 5pt),
        raw(source.text, lang: "cpp", block: true, theme: none),
      ),
      kind: raw,
      supplement: [Listing],
      caption: [Excerpt from `emit_Symbol` in SpiderMonkey's generated Baseline
        Interpreter. `ImmPtr` embeds the address of the generating runtime's
        well-known-symbol table in the emitted instructions.],
      placement: placement,
    ) <lst-symbol-coupling>
  ]
}

#let sharability(width: auto, height: auto, placement: top) = [
  #_fig(
    "./figures/3-2-sharability.png",
    [Peak JIT residency at TabsOpen across the browser's content
     processes. Blue segments are sharable, red is unique memory.
     App = application baseline, Tr = trampolines, Ion = Ion code, IC = attached
     baseline IC bodies, BI = baseline interpreter, SH = self-hosted
     baseline, Tot = row-wise sum.],
    width: width,
    height: height,
    placement: placement,
  ) <fig-sharability>
]

#let banded-cdf(width: auto, height: auto, placement: top, scope: "column") = [
  #_fig(
    "./figures/3-3-banded-IC-CDF.png",
    [Ranked cumulative distribution of dynamic inline-cache (IC) stub-body
     attachments across eight web workloads. The solid curve reports the
     median, the band spans the per-rank minimum and maximum, and the dashed
     curves show the least and most concentrated workloads. A small subset of
     compiled bodies serves most dynamic attachments.],
    width: width,
    height: height,
    placement: placement,
    scope: scope,
  ) <fig-ic-cdf>
]

#let ic-jaccard(width: auto, height: auto, placement: top, scope: "column") = [
  #_fig(
    "./figures/3-4-ic-jaccard.png",
    [The lower triangle reports the Jaccard index of executed inline-cache
     bodies across eight sites. The upper triangle reports one direction of
     frequency-weighted coverage for each unordered site pair; the omitted
     reverse direction can differ.],
    width: width,
    height: height,
    placement: placement,
    scope: scope,
  ) <fig-ic-jaccard>
]

#let jitless-s3-perf(width: auto, height: auto, placement: top, scope: "column") = [
  #_fig(
    "./figures/7-1-jitless-s3-perf.png",
    [Speedometer 3.1 performance normalized to bytecode-only execution.
     AmberMonkey configurations progressively restore performance as AOT
     IC and Baseline artifacts are enabled. Error bars show variation across
     three browser runs with three internal page cycles per configuration.],
    width: width,
    height: height,
    placement: placement,
    scope: scope,
  ) <fig-jitless-s3-perf>
]
