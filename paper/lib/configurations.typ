// Typst side of the execution-configuration registry.
// Reads paper/lib/json/configurations.json, which is emitted from
// fossils/configurations.toml by scripts/export_configurations.py.
//
// Never hardcode a configuration display name in the draft — resolve via
// these helpers so every consumer stays in sync with the registry.

#let _configs = json("json/configurations.json")

#let config-known(slug) = slug in _configs

#let _lookup(slug, field) = {
  assert(slug in _configs, message: "unknown configuration slug: " + slug)
  _configs.at(slug).at(field)
}

#let config-name(slug)  = _lookup(slug, "long")
#let config-short(slug) = _lookup(slug, "short")
#let config-prose(slug) = _lookup(slug, "prose")
#let config-color(slug) = rgb(_lookup(slug, "color"))
#let config-order(slug) = _lookup(slug, "order")

// Rewrite a JSON table so its first column swaps a slug for the long name.
// Use in place of table-from-json when the first column of the source JSON
// contains configuration slugs.
#let config-table-from-json(name) = {
  import "tables.typ": render-table
  let data = json("json/" + name)
  let rewritten = data
  rewritten.rows = data.rows.map(row => {
    let head = row.at(0)
    if config-known(head) {
      (config-name(head),) + row.slice(1)
    } else {
      row
    }
  })
  render-table(rewritten)
}
