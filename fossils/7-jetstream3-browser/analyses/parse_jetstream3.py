#!/usr/bin/env python3
"""Reduce a raptor JS3 JSON result to the startup score only.

JetStream 3 emits per-subtest scores in four flavours (First, Worst,
Average, Geometric). Only First -- the first-iteration runtime -- is
the startup metric this fossil is scoped to. We compute the geometric
mean of the per-subtest -First values ourselves since raptor does not
pre-aggregate.

Emitted metrics:
    startup_geomean   geo-mean over <name>-First (higher is better)
    n_subtests        count of subtests contributing to the geomean
"""

import json
import math
import sys


def die(msg):
    print(f"parse_jetstream3: FATAL: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    obs = json.load(sys.stdin)
    stdout = obs.get("stdout", "")
    if isinstance(stdout, list):
        stdout = "\n".join(stdout)
    if not stdout.strip():
        die("empty stdout; raptor produced no JSON")

    raptor = json.loads(stdout)
    suites = raptor.get("suites") or []
    if not suites:
        die("no suites[] in raptor JSON")
    subtests = suites[0].get("subtests") or []
    if not subtests:
        die("no subtests[] in raptor JSON")

    firsts = [
        s["value"] for s in subtests
        if s.get("name", "").endswith("-First")
        and isinstance(s.get("value"), (int, float))
        and s["value"] > 0
    ]
    if not firsts:
        die("no -First subtest values found in raptor JSON")

    log_sum = sum(math.log(v) for v in firsts)
    startup_geomean = math.exp(log_sum / len(firsts))

    json.dump({
        "startup_geomean": startup_geomean,
        "n_subtests": len(firsts),
    }, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
