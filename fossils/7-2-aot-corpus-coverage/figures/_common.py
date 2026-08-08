"""Shared helpers for the coverage figure scripts. The three tables all
walk the reducer's summary dict, format leaf Scalars, and drop the
result into the JSON path fossil expects (its .png slot with the suffix
swapped)."""

import json
import pathlib
import sys


VARIANT_LABELS = {
    "jetstream3": "JetStream 3.0",
    "speedometer3": "Speedometer 3.1",
}


def die(name, msg):
    sys.exit(f"{name}: {msg}")


def dig(node, path, variant, name):
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            die(name, f"{variant}: no {path!r}; record predates the request-time schema")
        node = node[part]
    return node


def fmt(mean, kind):
    if kind == "percent":
        return f"{mean:.1f}%"
    if abs(mean) >= 1_000_000:
        return f"{mean/1e6:.2f}M"
    if abs(mean) >= 10_000:
        return f"{mean/1e3:.1f}k"
    return f"{mean:,.0f}"


def emit(name, rows_spec):
    """rows_spec is a list of (label, dotted_path, kind) tuples. Reads the
    cross-variant fold on stdin and writes a JSON table to sys.argv[1]'s
    .json sibling."""
    data = json.load(sys.stdin)
    variants = sorted(data)
    if not variants:
        die(name, "no variants in analyzed input")

    columns = [{"key": "metric", "label": "Metric", "align": "left", "format": "str"}]
    for v in variants:
        columns.append({
            "key": v,
            "label": VARIANT_LABELS.get(v, v),
            "align": "right",
            "format": "str",
        })

    rows = []
    for label, path, kind in rows_spec:
        row = [label]
        for v in variants:
            scalar = dig(data[v], path, v, name)
            row.append(fmt(scalar["mean"], kind))
        rows.append(row)

    out = pathlib.Path(sys.argv[1]).with_suffix(".json")
    out.write_text(json.dumps({"columns": columns, "rows": rows}, indent=2) + "\n")
    print(f"wrote {out}")
