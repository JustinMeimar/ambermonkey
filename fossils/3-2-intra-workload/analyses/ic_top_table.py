#!/usr/bin/env python3
"""Top-N IC-attach stubs as a renderable table.

Same aggregation as ic_rank (content+parent merged), but emits a
column-schema-plus-rows JSON shape suitable for a Typst table
renderer. Columns: stub id (10-char prefix), invocation count,
proportion of total attaches, and cumulative CDF over the top-N.

The CDF column will not reach 1.0 when the tail is truncated -- that
is intentional and is the point of the table.
"""

import collections
import json
import sys


TOP_N = 20
ID_PREFIX = 10


def main():
    obs = json.load(sys.stdin)
    ob = obs.get("observations", [obs])[0]
    out = ob.get("stdout")
    if isinstance(out, list):
        out = "\n".join(out)
    reduced = json.loads(out.strip())
    ic = reduced["ic"]
    merged = collections.Counter()
    for proc in ("content", "parent"):
        merged.update(ic.get(proc, {}))
    if not merged:
        print("ic_top_table: FATAL: no IC-attach hashes", file=sys.stderr)
        sys.exit(1)

    total = sum(merged.values())
    top = merged.most_common(TOP_N)
    rows = []
    cdf = 0.0
    for stub_id, count in top:
        proportion = count / total
        cdf += proportion
        rows.append([stub_id[:ID_PREFIX], count, proportion, cdf])

    table = {
        "columns": [
            {"key": "stub",       "label": "Stub",        "align": "left",  "format": "str"},
            {"key": "count",      "label": "Invocations", "align": "right", "format": "int"},
            {"key": "proportion", "label": "Share",       "align": "right", "format": "percent"},
            {"key": "cdf",        "label": "CDF",         "align": "right", "format": "percent"},
        ],
        "rows": rows,
    }
    json.dump(table, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
