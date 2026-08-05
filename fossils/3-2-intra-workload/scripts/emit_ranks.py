#!/usr/bin/env python3
"""Reduce a JS_INSTR_DIR of per-process JSONL into two ranked-count
sequences on stdout, one for the IC-attach axis and one for the
baseline-compile axis.

Both are aggregated across all processes in the run (parent + content).
For the CDF story we want concentration of demand on the workload as a
whole, so cross-process aggregation is correct.

Output shape:
    {"ic":       {"ranked_counts": [n1, n2, ...]},
     "baseline": {"ranked_counts": [n1, n2, ...]}}

Crashes loudly on malformed JSON or events missing required fields.

Usage: emit_ranks.py DIR   (writes JSON to stdout)
"""

import collections
import json
import os
import sys


def die(msg):
    print(f"emit_ranks: FATAL: {msg}", file=sys.stderr)
    sys.exit(1)


def parse(path, ic_counts, bl_counts):
    with open(path) as f:
        for ln in f:
            if '"ic-instance-attach"' not in ln \
                    and '"baseline-compile"' not in ln:
                continue
            o = json.loads(ln)
            k = o["kind"]
            if k == "ic-instance-attach":
                ic_counts[o["ic_body_id"]] += 1
            elif k == "baseline-compile":
                bl_counts[o["semantic_id"]] += 1


def main(root):
    ic = collections.Counter()
    bl = collections.Counter()
    n_files = 0
    for fn in sorted(os.listdir(root)):
        if not fn.endswith(".jsonl"):
            continue
        n_files += 1
        parse(os.path.join(root, fn), ic, bl)
    if n_files == 0:
        die(f"no .jsonl files in {root}")
    if not ic:
        die("no ic-instance-attach events; InstrCh_IC disabled?")
    if not bl:
        die("no baseline-compile events; InstrCh_Baseline disabled?")
    out = {
        "ic": {"ranked_counts": [c for _, c in ic.most_common()]},
        "baseline": {"ranked_counts": [c for _, c in bl.most_common()]},
    }
    json.dump(out, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv[1])
