// Shared document setup and visual language for the paper's CeTZ figures.

// Wrap each standalone figure in the paper's single-column page and text
// settings. Keeping these settings around the supplied body also makes the
// figure files safe to include from the directory-level scratchpad.
#let diagram-document(body) = {
  set page(
    paper: "us-letter",
    margin: (top: 2cm, bottom: 2cm, left: 2cm, right: 2cm),
    numbering: "1",
  )
  set text(
    font: ("Times New Roman", "TeX Gyre Termes"),
    size: 10pt,
    lang: "en",
  )
  set par(justify: true, leading: 0.5em)
  show figure.caption: set text(size: 8.5pt)

  body
}

// Conservative, print-safe palette: greys for structure, one accent for the
// hot path, and one contrast colour for external artifacts.
#let dg = (
  ink: luma(30),
  rule: luma(120),
  soft: luma(180),
  wash: luma(245),
  accent: rgb("#1f4e79"),
  accent-wash: rgb("#e8f0f7"),
  warm: rgb("#a5461a"),
  warm-wash: rgb("#f6ece7"),
  ok: rgb("#2f6b3a"),
)

// CeTZ accepts content directly, so these helpers keep labels consistent
// across figures.
#let dlabel(body) = text(size: 8pt, fill: dg.ink)[#body]
#let dtitle(body) = text(size: 8.5pt, weight: "bold", fill: dg.ink)[#body]
#let dsmall(body) = text(size: 7pt, fill: dg.ink)[#body]
#let dmono(body) = text(size: 7.5pt, font: "DejaVu Sans Mono")[#body]
#let dtiny(body) = text(size: 6.5pt, font: "DejaVu Sans Mono")[#body]
