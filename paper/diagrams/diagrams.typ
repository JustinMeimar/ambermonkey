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

    // Pick one slot (counting from the top) to be the source of the
    // linked list. Slot k spans rows [n-slots-k, n-slots-k+1] in the
    // bottom-up y coordinate CeTZ uses.
    let source-slot = 2  // 3rd row from the top
    let slot-h = (bc-y1 - bc-y0) / n-slots
    let slot-cy = bc-y1 - slot-h * (source-slot + 0.5)

    // Two linked-list nodes to the right of the column.
    let node-w = 1.5
    let node-h = 0.75
    let gap    = 0.9              // gap between column and first node
    let inter  = 0.7              // gap between the two nodes

    let n1-x0 = bc-x1 + gap
    let n1-x1 = n1-x0 + node-w
    let n2-x0 = n1-x1 + inter
    let n2-x1 = n2-x0 + node-w

    let n1-y0 = slot-cy - node-h / 2
    let n1-y1 = slot-cy + node-h / 2
    let n2-y0 = n1-y0
    let n2-y1 = n1-y1

    rect(
      (n1-x0, n1-y0), (n1-x1, n1-y1),
      stroke: 0.7pt + dg.ink,
      fill: white,
      radius: 0.12,
    )
    rect(
      (n2-x0, n2-y0), (n2-x1, n2-y1),
      stroke: 0.7pt + dg.ink,
      fill: white,
      radius: 0.12,
    )

    // Edge from the bytecode slot to node 1, then node 1 to node 2.
    line(
      (bc-x1, slot-cy), (n1-x0, slot-cy),
      mark: (end: ">"),
      stroke: 0.7pt + dg.ink,
    )
    line(
      (n1-x1, slot-cy), (n2-x0, slot-cy),
      mark: (end: ">"),
      stroke: 0.7pt + dg.ink,
    )
  })
}

#figure(
  bytecode-list-figure,
  caption: [Bytecode column with a two-node linked list hanging off
    one slot. Placeholder layout — labels and semantics TBD.],
)
