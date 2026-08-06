#!/usr/bin/env python3
"""Reduce a raptor JS3 JSON result to the metrics we care about.

JetStream 3 emits per-subtest scores in four flavours (First, Worst,
Average, Geometric). The suite-level ``value`` is the aggregate JS3
score (higher is better). The per-subtest ``-First`` values are
first-iteration wall times in milliseconds (lower is better).

Emitted metrics:
    overall_score        suite.value, the aggregate JS3 score (higher is better)
    startup_score        1000 / geomean(<name>-First ms), inverted so
                         higher is better and it composes with overall_score
                         on the same bar chart
    startup_geomean_ms   raw geomean over <name>-First values, in ms
                         (lower is better); kept for provenance
    n_subtests           count of subtests contributing to the geomean
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
    suite = suites[0]
    subtests = suite.get("subtests") or []
    if not subtests:
        die("no subtests[] in raptor JSON")

    overall = suite.get("value")
    if not isinstance(overall, (int, float)):
        reps = suite.get("replicates") or []
        if reps and isinstance(reps[0], (int, float)):
            overall = reps[0]
        else:
            die("no suite-level score in raptor JSON")

    firsts = [
        s["value"] for s in subtests
        if s.get("name", "").endswith("-First")
        and isinstance(s.get("value"), (int, float))
        and s["value"] > 0
    ]
    if not firsts:
        die("no -First subtest values found in raptor JSON")

    log_sum = sum(math.log(v) for v in firsts)
    startup_geomean_ms = math.exp(log_sum / len(firsts))
    startup_score = 1000.0 / startup_geomean_ms

    json.dump({
        "overall_score": overall,
        "startup_score": startup_score,
        "startup_geomean_ms": startup_geomean_ms,
        "n_subtests": len(firsts),
    }, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
