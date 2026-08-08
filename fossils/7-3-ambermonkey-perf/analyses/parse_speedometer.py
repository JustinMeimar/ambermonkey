#!/usr/bin/env python3
"""Parse one Speedometer observation while retaining browser-run samples.

Fossil folds maps recursively. Emitting the current observation beneath its
unique iteration key therefore preserves the independent browser runs for
figures, while top-level scalar leaves retain Fossil's mean/stddev summaries.
"""

import json
import os
from pathlib import Path
import re
import sys


EXPECTED_WORKLOADS = 20


def fail(message):
    print(f"parse_speedometer.py: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_manifest():
    run_dir = os.environ.get("FOSSIL_RUN_DIR")
    if not run_dir:
        fail("FOSSIL_RUN_DIR is required")
    path = Path(run_dir) / "manifest.json"
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read {path}: {exc}")


def command_flag(command, name):
    pattern = rf"(?:^|\s){re.escape(name)}=true(?=\s|$)"
    return re.search(pattern, command) is not None


def page_cycles_from(command):
    matches = re.findall(
        r"(?:^|\s)--page-cycles(?:=|\s+)(\d+)(?=\s|$)", command
    )
    if len(matches) != 1:
        fail("command must contain exactly one --page-cycles value")
    page_cycles = int(matches[0])
    if page_cycles < 1:
        fail("--page-cycles must be positive")
    return page_cycles


def validate_manifest(manifest):
    variant = manifest.get("variant")
    command = manifest.get("command")
    if not isinstance(variant, str) or not variant:
        fail(f"invalid manifest variant {variant!r}")
    if not isinstance(command, str) or not command:
        fail(f"{variant}: manifest command is missing")

    page_cycles = page_cycles_from(command)
    use_aot_image = command_flag(command, "JIT_OPTION_useAOTImage")
    aot_only = command_flag(command, "JIT_OPTION_aotOnly")
    jit_backend_disabled = command_flag(command, "JIT_OPTION_disableJitBackend")
    ion_disabled = (
        "--setpref javascript.options.ion=false" in command
        or re.search(r"(?:^|\s)JIT_OPTION_ion=false(?=\s|$)", command)
        is not None
    )

    if aot_only and not use_aot_image:
        fail(f"{variant}: aotOnly requires JIT_OPTION_useAOTImage=true")
    if variant == "interp-only" and not jit_backend_disabled:
        fail("interp-only: JIT backend was not disabled")

    if aot_only:
        aot_policy = "aot-only"
    elif use_aot_image:
        aot_policy = "runtime-fallback"
    else:
        aot_policy = "disabled"

    execution = {
        "aot_image": "enabled" if use_aot_image else "disabled",
        "aot_policy": aot_policy,
        "ion": (
            "unavailable"
            if jit_backend_disabled
            else "disabled" if ion_disabled else "enabled"
        ),
        "jit_backend": "disabled" if jit_backend_disabled else "enabled",
    }
    return variant, page_cycles, execution


def parse_raptor(observation):
    stdout = observation.get("stdout", "")
    text = "\n".join(stdout) if isinstance(stdout, list) else stdout
    try:
        raptor = json.loads(text)
        suites = raptor["suites"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        fail(f"malformed Raptor output: {exc}")

    if len(suites) != 1 or suites[0].get("name") != "speedometer3":
        fail("expected exactly one Speedometer 3 suite")
    return suites[0]


def positive_value(lookup, name):
    try:
        value = float(lookup[name]["value"])
    except (KeyError, TypeError, ValueError) as exc:
        fail(f"missing or invalid {name!r} metric: {exc}")
    if value <= 0:
        fail(f"{name!r} must be positive, found {value}")
    return value


observation = json.load(sys.stdin)
manifest = load_manifest()
variant, page_cycles, execution = validate_manifest(manifest)
suite = parse_raptor(observation)
try:
    lookup = {subtest["name"]: subtest for subtest in suite["subtests"]}
except (KeyError, TypeError) as exc:
    fail(f"malformed Speedometer subtests: {exc}")

workloads = {
    name.removesuffix("/total"): positive_value(lookup, name)
    for name in sorted(lookup)
    if name.endswith("/total")
}
if len(workloads) != EXPECTED_WORKLOADS:
    fail(f"expected {EXPECTED_WORKLOADS} workload totals, found {len(workloads)}")

score = positive_value(lookup, "score")
total_ms = positive_value(lookup, "total")
iteration = observation.get("iteration")
if not isinstance(iteration, int) or iteration < 1:
    fail(f"invalid observation iteration {iteration!r}")

sample = {
    "score": score,
    "total_ms": total_ms,
    "workloads_ms": workloads,
}
metrics = {
    "score": score,
    "total_ms": total_ms,
    "workloads_ms": workloads,
    "runs": {f"run_{iteration:02d}": sample},
    "meta": {
        "variant": variant,
        "commit": manifest.get("git", {}).get("commit", ""),
        "iterations": manifest.get("iterations"),
        "page_cycles": page_cycles,
        "execution": execution,
    },
}

json.dump(metrics, sys.stdout, sort_keys=True)
