#!/usr/bin/env python3
"""Baseline-function coverage table. Metric names are unqualified -- the
table title carries the artifact context. tp6-Test cells are the median
across the eight held-out site variants with the min-max range in
brackets; suite cells are scalars."""

from _common import emit_aggregate

ROWS = [
    ("Corpus size",  "utilization.baseline_functions.total",    "count"),
    ("Installed",    "utilization.baseline_functions.used",     "count"),
    ("Utilization",  "utilization.baseline_functions.pct",      "percent"),
    ("AOT hit rate", "requests.baseline_functions.aot_hit_pct", "percent"),
]

if __name__ == "__main__":
    emit_aggregate("baseline_function_table", ROWS)
