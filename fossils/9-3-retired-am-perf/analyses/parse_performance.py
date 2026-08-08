#!/usr/bin/env python3
"""Reduce one held-out browser run while retaining independent samples."""

import json
import os
from pathlib import Path
import re
import sys


WORKLOADS = ("speedometer3", "jetstream3")
POLICIES = ("interp-only", "am-strict", "default")
VARIANTS = {
    f"{workload}-{policy}": (workload, policy)
    for workload in WORKLOADS
    for policy in POLICIES
}
EXPECTED_SPEEDOMETER_WORKLOADS = 20


def fail(message):
    print(f"parse_performance: {message}", file=sys.stderr)
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


def has_option(command, option, setting):
    return (
        re.search(
            rf"{re.escape(option)}(?:=|\s+){re.escape(setting)}(?:\s|$)",
            command,
        )
        is not None
    )


def validate_manifest(manifest):
    variant = manifest.get("variant")
    if variant not in VARIANTS:
        fail(f"unexpected variant {variant!r}")
    workload, policy = VARIANTS[variant]
    command = manifest.get("command", "")

    if not has_option(command, "--browser-cycles", "1"):
        fail(f"{variant}: expected one browser cycle")
    if not has_option(command, "--page-cycles", "1"):
        fail(f"{variant}: expected one page cycle")
    if not re.search(rf"(?:^|\s)-t\s+{workload}(?:\s|$)", command):
        fail(f"{variant}: command does not run {workload}")

    for pref in (
        "javascript.options.baselinejit=true",
        "javascript.options.native_regexp=false",
        "javascript.options.wasm=false",
    ):
        if not has_option(command, "--setpref", pref):
            fail(f"{variant}: missing matched control {pref}")

    ion_on = policy == "default"
    ion_pref = f"javascript.options.ion={'true' if ion_on else 'false'}"
    if not has_option(command, "--setpref", ion_pref):
        fail(f"{variant}: missing {ion_pref}")

    expected_env = {
        "JIT_OPTION_disableJitBackend=true": policy == "interp-only",
        "JIT_OPTION_useAOTImage=true": policy == "am-strict",
        "JIT_OPTION_aotOnly=true": policy == "am-strict",
    }
    for setting, should_exist in expected_env.items():
        exists = has_option(command, "--setenv", setting)
        if exists != should_exist:
            state = "missing" if should_exist else "unexpected"
            fail(f"{variant}: {state} --setenv {setting}")

    uses_aot_build = "build-browser-release-aot" in command
    uses_aot_mozconfig = "browser-release-aot.mozconfig" in command
    should_use_aot_build = policy == "am-strict"
    if uses_aot_build != should_use_aot_build:
        build = "AOT release" if should_use_aot_build else "ordinary release"
        fail(f"{variant}: expected the {build} browser binary")
    if uses_aot_mozconfig != should_use_aot_build:
        config = "AOT release" if should_use_aot_build else "ordinary release"
        fail(f"{variant}: expected the {config} mozconfig")

    return variant, workload, policy


def load_raptor(observation):
    stdout = observation.get("stdout", "")
    text = "\n".join(stdout) if isinstance(stdout, list) else stdout
    if not isinstance(text, str) or not text.strip():
        fail("empty stdout; Raptor produced no JSON")
    try:
        raptor = json.loads(text)
    except json.JSONDecodeError as exc:
        fail(f"malformed Raptor JSON: {exc}")
    suites = raptor.get("suites") or []
    if len(suites) != 1:
        fail(f"expected exactly one Raptor suite, found {len(suites)}")
    return suites[0]


def positive(value, name):
    if not isinstance(value, (int, float)) or value <= 0:
        fail(f"{name} must be a positive number, found {value!r}")
    return float(value)


def parse_speedometer(suite):
    if suite.get("name") != "speedometer3":
        fail(f"expected speedometer3 suite, found {suite.get('name')!r}")
    lookup = {subtest["name"]: subtest for subtest in suite.get("subtests", [])}
    workloads = {
        name.removesuffix("/total"): positive(subtest.get("value"), name)
        for name, subtest in sorted(lookup.items())
        if name.endswith("/total")
    }
    if len(workloads) != EXPECTED_SPEEDOMETER_WORKLOADS:
        fail(
            f"expected {EXPECTED_SPEEDOMETER_WORKLOADS} Speedometer workload "
            f"totals, found {len(workloads)}"
        )
    return {
        "score": positive(lookup.get("score", {}).get("value"), "score"),
        "total_ms": positive(lookup.get("total", {}).get("value"), "total"),
        "workloads": workloads,
    }


def parse_jetstream(suite):
    if suite.get("name") != "jetstream3":
        fail(f"expected jetstream3 suite, found {suite.get('name')!r}")
    geometric = {
        subtest["name"].removesuffix("-Geometric"): positive(
            subtest.get("value"), subtest["name"]
        )
        for subtest in suite.get("subtests", [])
        if subtest.get("name", "").endswith("-Geometric")
        and isinstance(subtest.get("value"), (int, float))
        and subtest["value"] > 0
    }
    if not geometric:
        fail("JetStream suite contains no positive -Geometric subtests")
    return {
        "score": positive(suite.get("value"), "suite score"),
        "subtests": geometric,
        "n_subtests": len(geometric),
    }


def main():
    observation = json.load(sys.stdin)
    manifest = load_manifest()
    variant, workload, policy = validate_manifest(manifest)
    suite = load_raptor(observation)
    metrics = (
        parse_speedometer(suite)
        if workload == "speedometer3"
        else parse_jetstream(suite)
    )

    iteration = observation.get("iteration")
    if not isinstance(iteration, int) or iteration < 1:
        fail(f"invalid observation iteration {iteration!r}")

    output = {
        **metrics,
        "runs": {f"run_{iteration:02d}": metrics},
        "meta": {
            "variant": variant,
            "workload": workload,
            "policy": policy,
            "commit": manifest.get("git", {}).get("commit", ""),
            "iterations": manifest.get("iterations"),
            "browser_cycles": 1,
            "page_cycles": 1,
            "ion": policy == "default",
            "native_regexp": False,
            "wasm": False,
        },
    }
    json.dump(output, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
