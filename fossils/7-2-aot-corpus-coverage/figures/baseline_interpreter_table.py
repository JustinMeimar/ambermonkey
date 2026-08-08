#!/usr/bin/env python3
"""Baseline-interpreter coverage table. The image ships exactly one
interp blob and every AOT-using process loads it as part of image
attach; there is nothing per-blob to accumulate. Corpus size is
hardcoded here rather than plumbed through AOTCoverage.cpp -- the
runtime already emits n_procs, which is equivalent to "how many
processes loaded this blob"."""

import json
import pathlib
import sys

from _common import VARIANT_LABELS, dig, fmt


def main():
    data = json.load(sys.stdin)
    variants = sorted(data)
    if not variants:
        sys.exit("baseline_interpreter_table: no variants in analyzed input")

    columns = [{"key": "metric", "label": "Metric", "align": "left", "format": "str"}]
    for v in variants:
        columns.append({
            "key": v, "label": VARIANT_LABELS.get(v, v),
            "align": "right", "format": "str",
        })

    corpus_row = ["Corpus size"] + ["1" for _ in variants]
    loaded_row = ["Processes loaded"]
    for v in variants:
        scalar = dig(data[v], "n_procs", v, "baseline_interpreter_table")
        loaded_row.append(fmt(scalar["mean"], "count"))

    out = pathlib.Path(sys.argv[1]).with_suffix(".json")
    out.write_text(json.dumps(
        {"columns": columns, "rows": [corpus_row, loaded_row]}, indent=2
    ) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
