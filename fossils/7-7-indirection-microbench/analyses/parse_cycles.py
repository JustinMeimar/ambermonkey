#!/usr/bin/env python3

import json
import os
import sys

sys.path.insert(0, os.environ["FOSSIL_PROJECT_DIR"] + "/scripts")
from benchmarks import manifest

PREFIX = "parse_cycles"

VARIANTS = {"head", "no-opts"}
ITER_COUNT = 500_000_000
REQUIRED_EVENTS = ("cycles:u", "instructions:u", "ref-cycles:u")
MIN_RUNNING = 99.5


def parse_perf_ndjson(text):
    events = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        event = obj.get("event")
        val = obj.get("counter-value")
        if event is None or val is None:
            continue
        try:
            value = float(val)
        except (TypeError, ValueError):
            manifest.fail(PREFIX, f"non-numeric counter for {event}: {val!r}")
        running = obj.get("pcnt-running", 0.0)
        try:
            pcnt_running = float(running)
        except (TypeError, ValueError):
            pcnt_running = 0.0
        events[event] = {"value": value, "pcnt_running": pcnt_running}
    return events


def main():
    obs = json.load(sys.stdin)
    m = manifest.load(PREFIX)

    variant = m.get("variant")
    if variant not in VARIANTS:
        manifest.fail(PREFIX, f"unexpected variant {variant!r}")

    stdout = obs.get("stdout", "")
    obs_text = "\n".join(stdout) if isinstance(stdout, list) else stdout
    if not isinstance(obs_text, str) or not obs_text.strip():
        manifest.fail(PREFIX, "empty stdout; perf produced no JSON")
    events = parse_perf_ndjson(obs_text)
    for req in REQUIRED_EVENTS:
        if req not in events:
            manifest.fail(PREFIX, f"missing event {req} in perf output")
        if events[req]["pcnt_running"] < MIN_RUNNING:
            manifest.fail(
                PREFIX,
                f"{req} multiplexed at {events[req]['pcnt_running']:.2f}%"
                f" (< {MIN_RUNNING}%)",
            )

    cycles = events["cycles:u"]["value"]
    insns = events["instructions:u"]["value"]
    refcyc = events["ref-cycles:u"]["value"]

    metrics = {
        "cycles_user": cycles,
        "instructions_user": insns,
        "ref_cycles_user": refcyc,
        "cycles_per_iter": cycles / ITER_COUNT,
        "insns_per_iter": insns / ITER_COUNT,
        "ipc": (insns / cycles) if cycles else 0.0,
    }

    iteration = obs.get("iteration")
    iter_key = f"run_{int(iteration):02d}" if isinstance(iteration, int) else "run"

    out = {
        **metrics,
        "runs": {iter_key: metrics},
        "meta": {
            "variant": variant,
            "iter_count": ITER_COUNT,
            "commit": m.get("git", {}).get("commit", ""),
            "iterations": m.get("iterations"),
        },
    }
    json.dump(out, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
