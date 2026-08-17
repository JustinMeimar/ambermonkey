// Value formatters for inline prose citations. Read the JSON with
// `json-field` / `cell-value` from lib/tables.typ; wrap the result in
// one of these to get a paper-ready string. Deliberately small:
// pct(json-field(...)) at each call site is clearer than an extra
// pct-field wrapper that saves a few characters and adds another name.

#let pct(x, digits: 0) = str(calc.round(x * 100, digits: digits)) + "%"
#let mb(bytes, digits: 2) = str(calc.round(bytes / 1e6, digits: digits)) + " MB"
// For quantities already expressed in MB (e.g., JSONs that pre-convert kB->MB).
#let mb-str(mb, digits: 2) = str(calc.round(mb, digits: digits)) + " MB"
#let kb(bytes) = str(calc.round(bytes / 1e3)) + " KB"
#let int-str(x) = str(int(x))
#let float-str(x, digits: 2) = str(calc.round(x, digits: digits))
#let words(n) = (
  "zero", "one", "two", "three", "four", "five",
  "six", "seven", "eight", "nine", "ten",
).at(int(n))

// A per-target {min, max} → "min%–max%" range shows up twice for the
// inter-workload coverage per-site cells; naming it beats inlining the
// three-step lookup at each call site.
#let range-pct(cell, digits: 0) = pct(cell.min, digits: digits) + "–" + pct(cell.max, digits: digits)
