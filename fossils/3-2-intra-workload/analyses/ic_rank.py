#!/usr/bin/env python3
"""Pluck the IC-attach ranked_counts from the variant's reduced JSON."""

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
    if not ic["ranked_counts"]:
        print("ic_rank: FATAL: ic.ranked_counts is empty", file=sys.stderr)
        sys.exit(1)
    json.dump(ic, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
