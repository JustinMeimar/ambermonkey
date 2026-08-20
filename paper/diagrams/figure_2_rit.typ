// Figure 2: Runtime Indirection Table and its consumers.

#import "@preview/cetz:0.3.4": canvas, draw
#import "shared.typ": diagram-document, dg, dlabel, dtitle, dsmall, dmono

#let ambermonkey-runtime-diagram = {
    let figure-w = 17.5
    let figure-h = 4.4
    let table-x0 = 5.3
    let table-x1 = 7.5
    let table-y0 = 0
    let table-y1 = 4.4
    let slot-h = 0.62
    let slot-one-y = table-y1 - 1.5 * slot-h
    let rotate-content = rotate

    canvas(length: 1cm, {
      import draw: *

      // Establish the full-width figure bounds while the remaining elements
      // are added incrementally.
      rect(
        (0, table-y0), (figure-w, figure-h),
        stroke: none,
        fill: none,
      )

      // Three offset, nearly square outlines represent concurrent VM
      // instances. The foreground VM exposes the runtime components relevant
      // to the indirection path.
      let vm-x0 = 0.55
      let vm-x1 = 3.85
      let vm-y0 = 0.55
      let vm-y1 = 3.75

      for layer in (2, 1) {
        let offset = 0.22 * layer
        rect(
          (vm-x0 + offset, vm-y0 + offset),
          (vm-x1 + offset, vm-y1 + offset),
          stroke: 0.7pt + dg.ink,
          fill: white,
          radius: 0.12,
        )
      }

      rect(
        (vm-x0, vm-y0), (vm-x1, vm-y1),
        stroke: 0.7pt + dg.ink,
        fill: white,
        radius: 0.12,
      )

      let component-w = 1.25
      let component-h = 0.9
      let component-left = vm-x0 + 0.3
      let component-right = vm-x1 - 0.3 - component-w
      let component-bottom = vm-y0 + 0.6
      let component-top = vm-y1 - 0.6 - component-h

      let draw-component(x, y, label) = {
        rect(
          (x, y), (x + component-w, y + component-h),
          stroke: 0.6pt + dg.ink,
          fill: dg.wash,
          radius: 0.1,
        )
        content(
          (x + component-w / 2, y + component-h / 2),
          dsmall(label),
        )
      }

      draw-component(component-left, component-top, [GC])
      draw-component(component-right, component-top, [Runtime])
      draw-component(component-left, component-bottom, [JIT])
      draw-component(component-right, component-bottom, [Interpreter])

      content(
        ((vm-x0 + vm-x1 + 0.44) / 2, vm-y0 - 0.42),
        dtitle[Concurrent VMs],
      )

      // Draw this pointer before the RIT layers so it passes behind them.
      line(
        (table-x0, slot-one-y),
        (component-right + component-w, component-top + component-h / 2),
        mark: (end: ">"),
        stroke: 1pt + dg.accent,
      )

      // A runtime-generated interpreter embeds %JSRuntime directly. Draw its
      // direct path before the RIT layers so the pointer passes behind them.
      line(
        (8.4, 0.72),
        (component-right + component-w, component-top + 0.2),
        mark: (end: ">"),
        stroke: 1pt + dg.accent,
      )

      // Two offset outlines behind the foreground table represent the
      // multiple RIT instances present at run time.
      for layer in (2, 1) {
        let offset = 0.22 * layer
        rect(
          (table-x0 + offset, table-y0 + offset),
          (table-x1 + offset, table-y1 + offset),
          stroke: 0.7pt + dg.ink,
          fill: white,
          radius: 0.12,
        )
      }

      content(
        ((table-x0 + table-x1 + 0.44) / 2, table-y0 - 0.42),
        dtitle[RITs],
      )

      rect(
        (table-x0, table-y0), (table-x1, table-y1),
        stroke: 0.7pt + dg.ink,
        fill: white,
        radius: 0.12,
      )

      // Three leading slots and slot 511 are explicit. The taller middle
      // region represents the omitted slots.
      for y in (
        table-y1 - slot-h,
        table-y1 - 2 * slot-h,
        table-y1 - 3 * slot-h,
        table-y0 + slot-h,
      ) {
        line(
          (table-x0, y), (table-x1, y),
          stroke: 0.6pt + dg.rule,
        )
      }

      let index-x = table-x0 - 0.18
      content((index-x, table-y1 - 0.5 * slot-h), anchor: "east", dlabel[0])
      content((index-x, table-y1 - 1.5 * slot-h), anchor: "east", dlabel[1])
      content((index-x, table-y1 - 2.5 * slot-h), anchor: "east", dlabel[2])
      content((index-x, table-y0 + 0.5 * slot-h), anchor: "east", dlabel[511])

      rect(
        (table-x0 + 0.18, slot-one-y - 0.22),
        (table-x1 - 0.18, slot-one-y + 0.22),
        stroke: none,
        fill: dg.accent-wash,
        radius: 0.08,
      )
      content(
        ((table-x0 + table-x1) / 2, slot-one-y),
        text(
          size: 7pt,
          font: "DejaVu Sans Mono",
          weight: "bold",
          fill: dg.accent,
        )[&JSRuntime],
      )

      content(
        ((table-x0 + table-x1) / 2, (table-y0 + table-y1 - 2 * slot-h) / 2),
        text(size: 11pt, fill: dg.rule)[⋮],
      )

      // The first highlighted load retrieves the per-runtime table pointer
      // from the frame. The second retrieves slot 1 from that table.
      let artifact-x0 = 8.8
      let artifact-x1 = 13.35
      let artifact-y0 = 2.8
      let artifact-y1 = 4.35
      let load-y = 3.25

      // Draw the relationship first so the arrow terminates cleanly at the
      // table and artifact boundaries.
      line(
        (artifact-x0, load-y), (table-x1, slot-one-y),
        mark: (end: ">"),
        stroke: 1pt + dg.accent,
      )

      rect(
        (artifact-x0, artifact-y0), (artifact-x1, artifact-y1),
        stroke: 0.7pt + dg.ink,
        fill: white,
        radius: 0.12,
      )
      content(
        ((artifact-x0 + artifact-x1) / 2, artifact-y1 + 0.35),
        dtitle[AOT Baseline Interpreter],
      )

      let code-x0 = artifact-x0 + 0.55
      let code-x1 = artifact-x1 - 0.35
      let line-gap = 0.45

      content(
        (code-x0, load-y + 2 * line-gap),
        anchor: "west",
        dmono[op_getprop:],
      )

      rect(
        (code-x0 - 0.15, load-y + line-gap - 0.25),
        (code-x1, load-y + line-gap + 0.25),
        stroke: none,
        fill: dg.warm-wash,
        radius: 0.08,
      )
      content(
        (code-x0, load-y + line-gap),
        anchor: "west",
        text(
          size: 7.5pt,
          font: "DejaVu Sans Mono",
          weight: "bold",
          fill: dg.warm,
        )[movq -24(%rbp), %r11],
      )
      rect(
        (code-x0 - 0.15, load-y - 0.25),
        (code-x1, load-y + 0.25),
        stroke: none,
        fill: dg.accent-wash,
        radius: 0.08,
      )
      content(
        (code-x0, load-y),
        anchor: "west",
        text(
          size: 7.5pt,
          font: "DejaVu Sans Mono",
          weight: "bold",
          fill: dg.accent,
        )[movq 8(%r11), %rax],
      )

      // Each runtime-generated Baseline Interpreter embeds its own runtime
      // address directly in the handler. Two offset outlines represent the
      // additional concurrent instances.
      let generated-x0 = 8.4
      let generated-x1 = 13.1
      let generated-y0 = 0.35
      let generated-y1 = 1.55

      for layer in (2, 1) {
        let offset = 0.22 * layer
        rect(
          (generated-x0 + offset, generated-y0 + offset),
          (generated-x1 + offset, generated-y1 + offset),
          stroke: 0.7pt + dg.ink,
          fill: white,
          radius: 0.12,
        )
      }

      rect(
        (generated-x0, generated-y0),
        (generated-x1, generated-y1),
        stroke: 0.7pt + dg.ink,
        fill: white,
        radius: 0.12,
      )
      content(
        ((generated-x0 + generated-x1 + 0.44) / 2, generated-y0 - 0.42),
        align(center)[#dtitle[Runtime-Generated \ Baseline Interpreters]],
      )

      let generated-code-x0 = generated-x0 + 0.55
      let generated-code-x1 = generated-x1 - 0.35
      let generated-load-y = 0.72

      content(
        (generated-code-x0, generated-load-y + 0.5),
        anchor: "west",
        dmono[op_getprop:],
      )
      rect(
        (generated-code-x0 - 0.15, generated-load-y - 0.25),
        (generated-code-x1, generated-load-y + 0.25),
        stroke: none,
        fill: dg.accent-wash,
        radius: 0.08,
      )
      content(
        (generated-code-x0, generated-load-y),
        anchor: "west",
        text(
          size: 7.5pt,
          font: "DejaVu Sans Mono",
          weight: "bold",
          fill: dg.accent,
        )[movabsq %JSRuntime, %rax],
      )

      // Reserve the far-right column for the program stack. Its entries are
      // intentionally schematic until the frame layout is introduced.
      let stack-x0 = 14.45
      let stack-x1 = 16.6
      let stack-y0 = 0
      let stack-y1 = 4.4
      let stack-slot-h = (stack-y1 - stack-y0) / 6

      for layer in (2, 1) {
        let offset = 0.22 * layer
        rect(
          (stack-x0 + offset, stack-y0 + offset),
          (stack-x1 + offset, stack-y1 + offset),
          stroke: 0.7pt + dg.ink,
          fill: white,
          radius: 0.12,
        )
      }

      rect(
        (stack-x0, stack-y0), (stack-x1, stack-y1),
        stroke: 0.7pt + dg.ink,
        fill: white,
        radius: 0.12,
      )
      for i in range(1, 6) {
        let y = stack-y0 + i * stack-slot-h
        line(
          (stack-x0, y), (stack-x1, y),
          stroke: 0.6pt + dg.rule,
        )
      }
      let rit-field-y = stack-y1 - 1.5 * stack-slot-h
      rect(
        (stack-x0 + 0.18, rit-field-y - 0.24),
        (stack-x1 - 0.18, rit-field-y + 0.24),
        stroke: none,
        fill: dg.warm-wash,
        radius: 0.08,
      )
      content(
        ((stack-x0 + stack-x1) / 2, rit-field-y),
        text(
          size: 7pt,
          font: "DejaVu Sans Mono",
          weight: "bold",
          fill: dg.warm,
        )[&RIT],
      )

      // Bracket the portion of the stack occupied by the Baseline frame.
      let frame-y0 = stack-y0 + stack-slot-h
      let frame-y1 = stack-y1 - stack-slot-h
      let bracket-x = stack-x0 - 0.16
      line(
        (bracket-x, frame-y0), (bracket-x, frame-y1),
        stroke: 0.7pt + dg.ink,
      )
      line(
        (bracket-x, frame-y0), (bracket-x + 0.16, frame-y0),
        stroke: 0.7pt + dg.ink,
      )
      line(
        (bracket-x, frame-y1), (bracket-x + 0.16, frame-y1),
        stroke: 0.7pt + dg.ink,
      )
      content(
        (bracket-x - 0.24, (frame-y0 + frame-y1) / 2),
        rotate-content(-90deg, dsmall[Baseline Frame]),
      )
      content(
        ((stack-x0 + stack-x1 + 0.44) / 2, stack-y0 - 0.42),
        dtitle[Program Stacks],
      )

      // The AOT handler loads the RIT pointer from its Baseline frame.
      line(
        (artifact-x1, load-y + line-gap), (stack-x0, rit-field-y),
        mark: (end: ">"),
        stroke: 1pt + dg.warm,
      )
    })
}

#diagram-document[
  #figure(ambermonkey-runtime-diagram)
]
