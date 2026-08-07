#!/usr/bin/env python3
"""Emit the AOT coverage evaluation table as JSON for the typst
json-table loader.

Registered as the `coverage-table` figure. Fossil always hands figure
scripts a .png output path, so we write to the sibling .json instead
and leave the .png uncreated.

Rows are the subset of the coverage reducer's metrics that the paper
argues from: how much of the shipped corpus a workload touched, how
its artifact requests were satisfied, and how many distinct CacheIR
programs the image could serve. Cells are pre-formatted mean ± stddev
strings because a variant column mixes counts and percentages, which
breaks per-column numeric formatting on the typst side.
"""

import json
import pathlib
import sys

ROWS = [
    ("Baseline corpus size",     "utilization.baseline_functions.total",    "count"),
    ("Baseline blobs used",      "utilization.baseline_functions.used",     "count"),
    ("Baseline utilization",     "utilization.baseline_functions.pct",      "percent"),
    ("Baseline AOT hit rate",    "requests.baseline_functions.aot_hit_pct", "percent"),
    ("IC corpus size",           "utilization.ic_stubs.total",              "count"),
    ("IC blobs used",            "utilization.ic_stubs.used",               "count"),
    ("IC utilization",           "utilization.ic_stubs.pct",                "percent"),
    ("IC served by AOT",         "requests.ic_stubs.aot_hit",               "count"),
    ("IC served by zone cache",  "requests.ic_stubs.zone_cache_hit",        "count"),
    ("IC compiles",              "requests.ic_stubs.compiled",              "count"),
    ("IC AOT hit rate",          "requests.ic_stubs.aot_hit_pct",           "percent"),
    ("IC shapes requested",      "workload.ic_shapes_requested",            "count"),
    ("IC shapes served by AOT",  "workload.ic_shapes_served",               "count"),
    ("IC workload coverage",     "workload.coverage_pct",                   "percent"),
]

VARIANT_LABELS = {
    "jetstream3": "JetStream 3",
    "speedometer3": "Speedometer 3",
}


def die(msg):
    sys.exit(f"coverage_table: {msg}")


def dig(node, path, variant):
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            die(f"{variant}: no {path!r}; record predates the request-time schema")
        node = node[part]
    return node


def fmt(mean, stddev, kind):
    if kind == "percent":
        return f"{mean:.1f}% ± {stddev:.1f}"
    if abs(mean) >= 1_000_000:
        return f"{mean/1e6:.2f}M ± {stddev/1e6:.2f}M"
    if abs(mean) >= 10_000:
        return f"{mean/1e3:.1f}k ± {stddev/1e3:.1f}k"
    return f"{mean:,.0f} ± {stddev:,.0f}"


def main():
    data = json.load(sys.stdin)
    variants = sorted(data)
    if not variants:
        die("no variants in analyzed input")

    columns = [{"key": "metric", "label": "Metric", "align": "left", "format": "str"}]
    for v in variants:
        columns.append({
            "key": v,
            "label": VARIANT_LABELS.get(v, v),
            "align": "right",
            "format": "str",
        })

    rows = []
    for label, path, kind in ROWS:
        row = [label]
        for v in variants:
            scalar = dig(data[v], path, v)
            row.append(fmt(scalar["mean"], scalar["stddev"], kind))
        rows.append(row)

    out = pathlib.Path(sys.argv[1]).with_suffix(".json")
    out.write_text(json.dumps({"columns": columns, "rows": rows}, indent=2) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
