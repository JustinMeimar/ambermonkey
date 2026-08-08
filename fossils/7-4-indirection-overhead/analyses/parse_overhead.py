#!/usr/bin/env python3

import json
import math
import os
import re
import sys
from pathlib import Path


VARIANTS = {
    "jetstream3-baseline":     ("jetstream3",   False),
    "jetstream3-aot-oracle":   ("jetstream3",   True),
    "speedometer3-baseline":   ("speedometer3", False),
    "speedometer3-aot-oracle": ("speedometer3", True),
}

SPEEDOMETER_WORKLOADS = 20


def fail(msg):
    print(f"parse_overhead: {msg}", file=sys.stderr)
    raise SystemExit(1)


def load_manifest():
    run_dir = os.environ.get("FOSSIL_RUN_DIR")
    if not run_dir:
        fail("FOSSIL_RUN_DIR is required")
    try:
        return json.loads((Path(run_dir) / "manifest.json").read_text())
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read manifest.json: {exc}")


def validate(manifest):
    variant = manifest.get("variant")
    if variant not in VARIANTS:
        fail(f"unexpected variant {variant!r}")
    workload, aot_only = VARIANTS[variant]
    cmd = manifest.get("command", "")
    for pref in (
        "javascript.options.ion=false",
        "javascript.options.native_regexp=false",
        "javascript.options.wasm=false",
    ):
        if pref not in cmd:
            fail(f"{variant}: pref {pref} not set")
    if aot_only:
        if "JIT_OPTION_aotOnly=true" not in cmd:
            fail(f"{variant}: JIT_OPTION_aotOnly=true not set")
    elif "JIT_OPTION_aotOnly=true" in cmd:
        fail(f"{variant}: baseline variant must not set JIT_OPTION_aotOnly")
    expected_cycles = 3 if workload == "speedometer3" else 1
    if not re.search(rf"--page-cycles(?:=|\s+){expected_cycles}(?:\s|$)", cmd):
        fail(f"{variant}: expected --page-cycles {expected_cycles}")
    return variant, workload, aot_only


def load_raptor(obs):
    stdout = obs.get("stdout", "")
    text = "\n".join(stdout) if isinstance(stdout, list) else stdout
    if not text.strip():
        fail("empty stdout; raptor produced no JSON")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        fail(f"malformed raptor JSON: {exc}")


def parse_jetstream3(raptor, variant):
    suites = raptor.get("suites") or []
    if not suites:
        fail(f"{variant}: no suites[]")
    suite = suites[0]
    subtests = suite.get("subtests") or []
    if not subtests:
        fail(f"{variant}: no subtests[]")

    overall = suite.get("value")
    if not isinstance(overall, (int, float)):
        reps = suite.get("replicates") or []
        if reps and isinstance(reps[0], (int, float)):
            overall = reps[0]
        else:
            fail(f"{variant}: no suite-level score")

    firsts = [
        s["value"] for s in subtests
        if s.get("name", "").endswith("-First")
        and isinstance(s.get("value"), (int, float)) and s["value"] > 0
    ]
    if not firsts:
        fail(f"{variant}: no -First subtest values")
    startup_geomean_ms = math.exp(sum(math.log(v) for v in firsts) / len(firsts))
    return {
        "score": float(overall),
        "startup_score": 1000.0 / startup_geomean_ms,
        "startup_geomean_ms": startup_geomean_ms,
        "n_subtests": len(firsts),
    }


def parse_speedometer3(raptor, variant):
    suites = raptor.get("suites") or []
    if len(suites) != 1 or suites[0].get("name") != "speedometer3":
        fail(f"{variant}: expected exactly one speedometer3 suite")
    suite = suites[0]
    lookup = {s["name"]: s for s in suite["subtests"]}

    def positive(name):
        try:
            value = float(lookup[name]["value"])
        except (KeyError, TypeError, ValueError) as exc:
            fail(f"{variant}: missing or invalid {name!r}: {exc}")
        if value <= 0:
            fail(f"{variant}: {name!r} must be positive, got {value}")
        return value

    workloads = {
        name.removesuffix("/total"): positive(name)
        for name in sorted(lookup)
        if name.endswith("/total")
    }
    if len(workloads) != SPEEDOMETER_WORKLOADS:
        fail(f"{variant}: expected {SPEEDOMETER_WORKLOADS} workloads, got {len(workloads)}")
    return {
        "score": positive("score"),
        "total_ms": positive("total"),
        "workloads_ms": workloads,
    }


def main():
    obs = json.load(sys.stdin)
    manifest = load_manifest()
    variant, workload, aot_only = validate(manifest)

    raptor = load_raptor(obs)
    if workload == "jetstream3":
        metrics = parse_jetstream3(raptor, variant)
    else:
        metrics = parse_speedometer3(raptor, variant)

    iteration = obs.get("iteration")
    if not isinstance(iteration, int) or iteration < 1:
        fail(f"invalid iteration {iteration!r}")

    out = {
        **metrics,
        "runs": {f"run_{iteration:02d}": metrics},
        "meta": {
            "variant": variant,
            "workload": workload,
            "aot_only": aot_only,
            "commit": manifest.get("git", {}).get("commit", ""),
            "iterations": manifest.get("iterations"),
        },
    }
    json.dump(out, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
