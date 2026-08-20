// Figure 1: inline-cache attachment and shared CacheIR implementation.

#import "@preview/cetz:0.3.4": canvas, draw
#import "shared.typ": diagram-document, dg, dsmall, dtiny

// Exposed so `lib/figures.typ` can embed this exact canvas in the paper
// without pulling in the standalone page setup below.
#let ic-shared-diagram = {
  let w = 8.4
  let h = 4.6
  canvas({
      import draw: *

      // Bytecode column: 20% of the figure width and flush with the left edge.
      let bc-w = w * 0.20
      let bc-x0 = 0
      let bc-x1 = bc-x0 + bc-w
      let bc-y0 = 0
      let bc-y1 = h

      rect(
        (bc-x0, bc-y0), (bc-x1, bc-y1),
        stroke: 0.7pt + dg.ink,
        fill: dg.wash,
      )

      // Horizontal dividers carve the column into bytecode rows.
      let n-slots = 8
      for i in range(1, n-slots) {
        let y = bc-y0 + (bc-y1 - bc-y0) * i / n-slots
        line(
          (bc-x0, y), (bc-x1, y),
          stroke: 0.5pt + dg.rule,
        )
      }

      // Shared geometry for each linked list hanging from a bytecode slot.
      let slot-h = (bc-y1 - bc-y0) / n-slots
      let node-w = 1.5
      let node-h = 0.75
      let gap = 1.3
      let inter = 1.4

      // Draw a two-node list from `slot-idx` (zero is the top row).
      let draw-list(slot-idx, payload) = {
        let slot-cy = bc-y1 - slot-h * (slot-idx + 0.5)

        content(
          ((bc-x0 + bc-x1) / 2, slot-cy),
          dsmall[GetProp],
        )

        let n1-x0 = bc-x1 + gap
        let n1-x1 = n1-x0 + node-w
        let n2-x0 = n1-x1 + inter
        let n2-x1 = n2-x0 + node-w

        let n1-y0 = slot-cy - node-h / 2
        let n1-y1 = slot-cy + node-h / 2

        rect(
          (n1-x0, n1-y0), (n1-x1, n1-y1),
          stroke: 0.7pt + dg.ink, fill: white, radius: 0.12,
        )
        content(((n1-x0 + n1-x1) / 2, slot-cy), payload)

        rect(
          (n2-x0, n1-y0), (n2-x1, n1-y1),
          stroke: 0.7pt + dg.ink, fill: white, radius: 0.12,
        )
        content(((n2-x0 + n2-x1) / 2, slot-cy), dsmall[FB])

        line(
          (bc-x1, slot-cy), (n1-x0, slot-cy),
          mark: (end: ">"), stroke: 0.7pt + dg.ink,
        )
        // First stub → shared implementation is drawn once the box
        // exists, below. The FB has no direct edge from the first stub.
      }

      // The two sites guard different shapes at different fixed-slot offsets.
      let top-slot = 1
      let bottom-slot = n-slots - 2
      draw-list(top-slot, dtiny[shape 0xA1 \ slot\u{00A0}\u{00A0}8])
      draw-list(bottom-slot, dtiny[shape 0xB2 \ slot\u{00A0}16])

      // The shared CacheIR body sits between the two per-site lists.
      let top-cy = bc-y1 - slot-h * (top-slot + 0.5)
      let bottom-cy = bc-y1 - slot-h * (bottom-slot + 0.5)
      let mid-cy = (top-cy + bottom-cy) / 2

      let n1-x0 = bc-x1 + gap
      let n1-x1 = n1-x0 + node-w
      let n1-cx = (n1-x0 + n1-x1) / 2

      let box-w = 4.4
      let box-h = 1.3
      let box-cx = n1-cx + 0.4
      let box-x0 = box-cx - box-w / 2
      let box-x1 = box-cx + box-w / 2
      let box-y0 = mid-cy - box-h / 2
      let box-y1 = mid-cy + box-h / 2

      rect(
        (box-x0, box-y0), (box-x1, box-y1),
        stroke: 0.7pt + dg.ink,
        fill: dg.wash,
        radius: 0.12,
      )
      content(
        (box-x0 + 0.2, mid-cy),
        anchor: "west",
        dtiny[
          GuardShape\u{00A0}\u{00A0}\u{00A0}\u{00A0}\u{00A0}shapeOffset 0 \
          LoadFixedSlot\u{00A0}\u{00A0}slotOffset\u{00A0}\u{00A0}8 \
          ReturnFromIC
        ],
      )

      // Each first (per-site) stub feeds into the shared implementation
      // from the edge nearest it: the top-list stub drops down into the
      // box's top; the bottom-list stub rises into the box's bottom.
      let top-node-bot    = top-cy - node-h / 2
      let bottom-node-top = bottom-cy + node-h / 2
      line(
        (n1-cx, top-node-bot), (n1-cx, box-y1),
        mark: (end: ">"), stroke: 0.7pt + dg.ink,
      )
      line(
        (n1-cx, bottom-node-top), (n1-cx, box-y0),
        mark: (end: ">"), stroke: 0.7pt + dg.ink,
      )

      // The shared implementation dispatches to each fallback stub.
      let n2-x0 = n1-x1 + inter
      let n2-x1 = n2-x0 + node-w
      let n2-cx = (n2-x0 + n2-x1) / 2
      let top-fb-bot = top-cy - node-h / 2
      let bottom-fb-top = bottom-cy + node-h / 2

      bezier(
        (box-x1, mid-cy),
        (n2-cx, top-fb-bot),
        (n2-cx, mid-cy),
        (n2-cx, top-fb-bot - 0.4),
        mark: (end: ">"), stroke: 0.7pt + dg.ink,
      )
      bezier(
        (box-x1, mid-cy),
        (n2-cx, bottom-fb-top),
        (n2-cx, mid-cy),
        (n2-cx, bottom-fb-top + 0.4),
        mark: (end: ">"), stroke: 0.7pt + dg.ink,
      )
  })
}

// Standalone render for direct compilation of this file or through
// `diagrams.typ`. Not used when imported from `lib/figures.typ`.
#diagram-document[
  #figure(
    ic-shared-diagram,
    caption: [Bytecode column with a two-node linked list hanging off
      one slot. Placeholder layout — labels and semantics TBD.],
  )
]
