#!/usr/bin/env python3
"""Peel the reducer's one-line JSON summary back out of the observation
and re-emit it so the fossil metric fold sees each leaf as a Scalar.

The heavy lifting is upstream in scripts/reduce_coverage.py: per-pid
dump aggregation is already done and lives in observation.stdout as a
single trailing JSON line. Here we just parse and pass through.
"""

import json
import sys


def die(msg):
    print(f"parse_coverage: FATAL: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    obs = json.load(sys.stdin)
    stdout = obs.get("stdout", "")
    if isinstance(stdout, list):
        stdout = "\n".join(stdout)

    # The reducer emits exactly one JSON blob on its final line;
    # raptor writes nothing to our stdout because we redirect its
    # output to stderr in the variant command. Take the last
    # non-empty line to be resilient to accidental trailing noise.
    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    if not lines:
        die("empty stdout; reducer did not run")

    try:
        summary = json.loads(lines[-1])
    except json.JSONDecodeError as e:
        die(f"reducer output was not JSON: {e}\nlast line: {lines[-1][:200]}")

    json.dump(summary, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
