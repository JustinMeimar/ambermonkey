// Figure 2: Runtime Indirection Table and its consumers.

#import "@preview/cetz:0.3.4": canvas, draw
#import "shared.typ": diagram-document, dg, dlabel, dtitle, dmono

#diagram-document[
  #let runtime-indirection-table = {
    let figure-w = 17.5
    let figure-h = 4.4
    let table-x0 = 0.55
    let table-x1 = 3.35
    let table-y0 = 0
    let table-y1 = figure-h
    let slot-h = 0.62

    canvas(length: 1cm, {
      import draw: *

      // Establish the full-width figure bounds while the remaining elements
      // are added incrementally.
      rect(
        (0, table-y0), (figure-w, table-y1),
        stroke: none,
        fill: none,
      )

      content(
        ((table-x0 + table-x1) / 2, table-y1 + 0.35),
        dtitle[RIT],
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

      content(
        ((table-x0 + table-x1) / 2, (table-y0 + table-y1 - 2 * slot-h) / 2),
        text(size: 11pt, fill: dg.rule)[⋮],
      )

      // An ahead-of-time artifact accesses slot 1 through the RIT. The
      // highlighted RIP-relative load uses an 8-byte displacement because
      // each table entry is one 64-bit pointer.
      let artifact-x0 = 5.6
      let artifact-x1 = 10.7
      let artifact-y0 = 0.75
      let artifact-y1 = 3.55
      let load-y = 2.25
      let slot-one-y = table-y1 - 1.5 * slot-h

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

      let code-x0 = artifact-x0 + 0.55
      let code-x1 = artifact-x1 - 0.35
      let line-gap = 0.4

      content(
        (code-x0, load-y + line-gap),
        anchor: "west",
        dmono[pushq %rbp],
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
        )[movq RIT+8(%rip), %rax],
      )
      content(
        (code-x0, load-y - line-gap),
        anchor: "west",
        dmono[testq %rax, %rax],
      )
      content(
        (code-x0, load-y - 2 * line-gap),
        anchor: "west",
        dmono[je .fallback],
      )
      content(
        (code-x0, load-y - 3 * line-gap),
        anchor: "west",
        dmono[jmpq \*%rax],
      )
    })
  }

  #figure(runtime-indirection-table)
]
