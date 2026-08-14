#!/usr/bin/env python3
"""Baseline-interpreter coverage table. The image ships exactly one
interp blob and every AOT-using process loads it as part of image
attach; there is nothing per-blob to accumulate. Corpus size is
hardcoded here rather than plumbed through AOTCoverage.cpp -- the
runtime already emits n_procs, which is equivalent to "how many
processes loaded this blob".

tp6-Test cells report the median process count across the eight
held-out site variants; suite cells are scalars."""

import json
import pathlib
import statistics
import sys

from _common import (
    TP6_TEST_LABEL, TP6_TEST_SITES, VARIANT_LABELS,
    dig, die, fmt_aggregate, fmt_scalar,
)


def main():
    data = json.load(sys.stdin)
    if not data:
        die("baseline_interpreter_table", "no variants in analyzed input")

    columns = [
        {"key": "metric",       "label": "Metric",       "align": "left",  "format": "str"},
        {"key": "tp6_test",     "label": TP6_TEST_LABEL, "align": "right", "format": "str"},
        {"key": "speedometer3", "label": VARIANT_LABELS["speedometer3"], "align": "right", "format": "str"},
        {"key": "jetstream3",   "label": VARIANT_LABELS["jetstream3"],   "align": "right", "format": "str"},
    ]

    corpus_row = ["Corpus size", "1", "1", "1"]

    loaded_row = ["Processes loaded"]
    tp6_values = []
    for v in TP6_TEST_SITES:
        if v not in data:
            continue
        tp6_values.append(dig(data[v], "n_procs", v, "baseline_interpreter_table")["mean"])
    loaded_row.append(fmt_aggregate(tp6_values, "count"))
    for suite in ("speedometer3", "jetstream3"):
        if suite not in data:
            loaded_row.append("--")
            continue
        loaded_row.append(fmt_scalar(
            dig(data[suite], "n_procs", suite, "baseline_interpreter_table")["mean"],
            "count",
        ))

    out = pathlib.Path(sys.argv[1]).with_suffix(".json")
    out.write_text(json.dumps(
        {"columns": columns, "rows": [corpus_row, loaded_row]}, indent=2
    ) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
