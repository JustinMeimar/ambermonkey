#!/usr/bin/env python3
"""IC-stub coverage table. Metric names are unqualified -- the table
title carries the artifact context. The zone-cache bucket is folded
silently into the request total; only the AOT-vs-total ratio survives
as a display metric. tp6-Test cells are the median across the eight
held-out site variants with the min-max range in brackets; suite cells
are scalars."""

from _common import emit_aggregate

ROWS = [
    ("Corpus size",    "utilization.ic_stubs.total",    "count"),
    ("Attached",       "utilization.ic_stubs.used",     "count"),
    ("Utilization",    "utilization.ic_stubs.pct",      "percent"),
    ("Total attaches", "requests.ic_stubs.total",       "count"),
    ("AOT hit rate",   "requests.ic_stubs.aot_hit_pct", "percent"),
]

if __name__ == "__main__":
    emit_aggregate("ic_table", ROWS)
