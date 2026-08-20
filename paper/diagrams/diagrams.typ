// Scratchpad for CeTZ diagrams that will be embedded in the paper.
// Each diagram is a top-level `#figure` so it renders on its own page
// here, but can be lifted verbatim into `lib/figures.typ` (or imported
// from there) once it's finished.
//
//   typst compile diagrams/diagrams.typ

#import "@preview/cetz:0.3.4"
#import "@preview/cetz:0.3.4": canvas, draw

// --- Page / text setup ------------------------------------------------
// Single-column US-letter so diagrams have room to breathe while being
// sketched. Font stack mirrors draft.typ so glyph metrics match once the
// diagram is dropped into the paper.
#set page(
  paper: "us-letter",
  margin: (top: 2cm, bottom: 2cm, left: 2cm, right: 2cm),
  numbering: "1",
)
#set text(
  font: ("Times New Roman", "TeX Gyre Termes"),
  size: 10pt,
  lang: "en",
)
#set par(justify: true, leading: 0.5em)
#show figure.caption: set text(size: 8.5pt)

// --- Shared diagram palette ------------------------------------------
// Keep the palette conservative and print-safe: greys for structure,
// one accent for the "hot path", one contrast for external artifacts.
#let dg = (
  ink:     luma(30),
  rule:    luma(120),
  soft:    luma(180),
  wash:    luma(245),
  accent:  rgb("#1f4e79"),   // deep blue for the hot path
  warm:    rgb("#a5461a"),   // burnt orange for fossils / on-disk
  ok:      rgb("#2f6b3a"),   // muted green for "sharable"
)

// Font sizes used inside canvases. CeTZ takes raw content, so wrap
// labels through these helpers to keep sizing consistent across figures.
#let dlabel(body)  = text(size: 8pt, fill: dg.ink)[#body]
#let dtitle(body)  = text(size: 8.5pt, weight: "bold", fill: dg.ink)[#body]
#let dsmall(body)  = text(size: 7pt, fill: dg.ink)[#body]
#let dmono(body)   = text(size: 7.5pt, font: "DejaVu Sans Mono")[#body]
#let dtiny(body)   = text(size: 6.5pt, font: "DejaVu Sans Mono")[#body]

// --- Title -----------------------------------------------------------
#align(center)[
  #text(size: 14pt, weight: "bold")[AmberMonkey diagram scratchpad]
  #v(2pt)
  #text(size: 9pt, fill: dg.rule)[
    CeTZ sources — lift into `lib/figures.typ` once finalized.
  ]
]
#v(6pt)

// =====================================================================
// Diagram 1 — bytecode column with a linked list hanging off one slot.
// Canvas is sized to the paper's single-column width (~8.4cm text
// column at 1.9cm margins on US letter) so what we see here is what
// the paper gets. `w` / `h` are the working extents in cm.
// =====================================================================

#let bytecode-list-figure = {
  let w = 8.4
  let h = 4.6
  canvas({
    import draw: *

    // Bytecode column: 20% of the figure width, full height, sitting
    // flush against the LHS.
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

    // Horizontal slits carving the column into bytecode rows. We keep
    // top/bottom caps solid, so slits are the interior dividers only.
    let n-slots = 8
    for i in range(1, n-slots) {
      let y = bc-y0 + (bc-y1 - bc-y0) * i / n-slots
      line(
        (bc-x0, y), (bc-x1, y),
        stroke: 0.5pt + dg.rule,
      )
    }

    // Shared geometry for any linked list hanging off a slot.
    let slot-h = (bc-y1 - bc-y0) / n-slots
    let node-w = 1.5
    let node-h = 0.75
    let gap    = 1.3              // gap between column and first node
    let inter  = 1.4              // gap between the two nodes

    // Draw a two-node linked list emanating from `slot-idx` (0 = top).
    // `payload` is the per-site stub data that goes inside the first
    // node — this is what distinguishes two sites that share a stub
    // implementation.
    let draw-list(slot-idx, payload) = {
      let slot-cy = bc-y1 - slot-h * (slot-idx + 0.5)

      // Label the source slot inside the bytecode column.
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
      line(
        (n1-x1, slot-cy), (n2-x0, slot-cy),
        mark: (end: ">"), stroke: 0.7pt + dg.ink,
      )
    }

    // Second row from the top (bumped up one to make room for the
    // shared box below), and second row from the bottom. Two sites
    // guard different shapes at different fixed-slot offsets — that's
    // the entire per-site payload.
    let top-slot    = 1
    let bottom-slot = n-slots - 2
    draw-list(top-slot,    dtiny[shape 0xA1 \ slot\u{00A0}\u{00A0}8])
    draw-list(bottom-slot, dtiny[shape 0xB2 \ slot\u{00A0}16])

    // Shared box sitting between the two lists. It lives directly
    // beneath the first (unlabelled) node of each list, so arrows go
    // straight up and down.
    let top-cy    = bc-y1 - slot-h * (top-slot + 0.5)
    let bottom-cy = bc-y1 - slot-h * (bottom-slot + 0.5)
    let mid-cy    = (top-cy + bottom-cy) / 2

    let n1-x0 = bc-x1 + gap
    let n1-x1 = n1-x0 + node-w
    let n1-cx = (n1-x0 + n1-x1) / 2

    // Shift the middle box right of `n1-cx` so it clears the bytecode
    // column, and give it a bit more width/height so the CacheIR body
    // sits inside with margin instead of clipping the right edge.
    let box-w  = 4.4
    let box-h  = 1.3
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
    // Left-anchored CacheIR body so ops and operands line up columnwise
    // and the offsets tie visually to the per-site payloads above/below.
    content(
      (box-x0 + 0.2, mid-cy),
      anchor: "west",
      dtiny[
        GuardShape\u{00A0}\u{00A0}\u{00A0}\u{00A0}\u{00A0}shapeOffset 0 \
        LoadFixedSlot\u{00A0}\u{00A0}slotOffset\u{00A0}\u{00A0}8 \
        ReturnFromIC
      ],
    )

    // The shared box (fallback-stub implementation) dispatches out to
    // each per-site FB stub. Leave horizontally from its right edge
    // and enter each FB vertically at the edge nearest the box — the
    // bottom of the top FB, the top of the bottom FB — via a cubic
    // bezier with a right-then-up / right-then-down elbow.
    let n2-x0 = n1-x1 + inter
    let n2-x1 = n2-x0 + node-w
    let n2-cx = (n2-x0 + n2-x1) / 2
    let top-fb-bot    = top-cy - node-h / 2
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

#figure(
  bytecode-list-figure,
  caption: [Bytecode column with a two-node linked list hanging off
    one slot. Placeholder layout — labels and semantics TBD.],
)
