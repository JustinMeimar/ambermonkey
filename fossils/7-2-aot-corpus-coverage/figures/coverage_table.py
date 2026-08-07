#!/usr/bin/env python3
"""Emit the coverage evaluation table as JSON for the typst json-table loader.

Registered as the `coverage-table` figure. fossil always hands figures a
.png path, so the table is written to the sibling .json instead and the
.png is left uncreated.

Rows are the subset of the reducer's metrics that the corpus coverage
evaluation argues from: how much of the shipped corpus a workload
touched, how its artifact requests were satisfied, and how many of the
distinct CacheIR programs it asked for the image could serve. Raw
install and compile counts for baseline, the self-hosted count (which
now equals the baseline count, since the corpus keeps no other baseline
functions), the raced-shape diagnostic and the process count are all
left out; they belong in prose, not in an evaluation table.
"""

import json
import pathlib
import sys

# (row label, dotted path into the folded metrics, unit)
ROWS = [
    ("Baseline corpus size", "utilization.baseline_functions.total", ""),
    ("Baseline blobs used", "utilization.baseline_functions.used", ""),
    ("Baseline utilization", "utilization.baseline_functions.pct", "%"),
    ("Baseline AOT hit rate", "requests.baseline_functions.aot_hit_pct", "%"),
    ("IC corpus size", "utilization.ic_stubs.total", ""),
    ("IC blobs used", "utilization.ic_stubs.used", ""),
    ("IC utilization", "utilization.ic_stubs.pct", "%"),
    ("IC served by AOT", "requests.ic_stubs.aot_hit", ""),
    ("IC served by zone cache", "requests.ic_stubs.zone_cache_hit", ""),
    ("IC compiles", "requests.ic_stubs.compiled", ""),
    ("IC AOT hit rate", "requests.ic_stubs.aot_hit_pct", "%"),
    ("IC shapes requested", "workload.ic_shapes_requested", ""),
    ("IC shapes served by AOT", "workload.ic_shapes_served", ""),
    ("IC workload coverage", "workload.coverage_pct", "%"),
]


def die(msg):
    sys.exit(f"coverage_table: {msg}")


def dig(node, path, variant):
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            die(f"{variant}: no {path!r}; record predates the request-time schema")
        node = node[part]
    return node


def main():
    data = json.load(sys.stdin)
    variants = sorted(data)
    if not variants:
        die("no variants in analyzed input")

    columns = ["metric", "unit", *variants]
    means, spread = [], []
    for label, path, unit in ROWS:
        scalar = [dig(data[v], path, v) for v in variants]
        means.append([label, unit, *(s["mean"] for s in scalar)])
        spread.append([label, unit, *(s["stddev"] for s in scalar)])

    out = pathlib.Path(sys.argv[1]).with_suffix(".json")
    out.write_text(json.dumps({
        "coverage": {"columns": columns, "rows": means},
        "stddev": {"columns": columns, "rows": spread},
    }, indent=2) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
