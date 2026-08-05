#!/usr/bin/env python3
"""Derive the IC-attach ranked_counts for the pareto banded CDF.

Aggregates parent+content by-hash maps into one, then emits counts
sorted descending. The banded CDF asks "what fraction of dynamic IC
demand is served by the top-k stubs?", so cross-process aggregation
is the right shape.
"""

import collections
import json
import sys


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
        print("ic_rank: FATAL: no IC-attach hashes", file=sys.stderr)
        sys.exit(1)
    ranked = sorted(merged.values(), reverse=True)
    json.dump({"ranked_counts": ranked}, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
