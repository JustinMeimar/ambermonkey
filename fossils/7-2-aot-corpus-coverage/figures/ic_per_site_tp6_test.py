#!/usr/bin/env python3
"""IC-stub coverage per tp6_test site. Eight rows, one per held-out
site, so a low-coverage site cannot be hidden by a pooled aggregate.
The columns match the ic_table metrics that vary at request time --
Corpus size and (identical) total omitted."""

from _common import emit_tp6_test_per_site

COLUMNS = [
    ("attached",     "Attached",       "utilization.ic_stubs.used",     "count"),
    ("utilization",  "Utilization",    "utilization.ic_stubs.pct",      "percent"),
    ("attaches",     "Total attaches", "requests.ic_stubs.total",       "count"),
    ("aot_hit_pct",  "AOT hit rate",   "requests.ic_stubs.aot_hit_pct", "percent"),
]

if __name__ == "__main__":
    emit_tp6_test_per_site("ic_per_site_tp6_test", COLUMNS)
