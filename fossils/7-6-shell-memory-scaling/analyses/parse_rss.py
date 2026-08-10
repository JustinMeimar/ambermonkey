#!/usr/bin/env python3

import json
import os
import re
import sys

sys.path.insert(0, os.environ["FOSSIL_PROJECT_DIR"] + "/scripts")
from benchmarks import manifest

PREFIX = "shell_rss"

VARIANT_RE = re.compile(r"^n(\d+)(-aot)?$")
RSS_RE = re.compile(r"peak_rss_kb=(\d+)")
ANON_EXEC_RE = re.compile(r"peak_anon_exec_kb=(\d+)")


def validate(m):
    variant = m.get("variant", "")
    match = VARIANT_RE.match(variant)
    if not match:
        manifest.fail(PREFIX, f"unexpected variant {variant!r}")
    workers = int(match.group(1))
    is_aot = match.group(2) is not None
    cmd = m.get("command", "")
    aot_flag = "--aot " in cmd or cmd.endswith("--aot")
    only_flag = "--aot-only" in cmd
    if is_aot and not (aot_flag and only_flag):
        manifest.fail(PREFIX, f"{variant}: aot variant missing --aot / --aot-only")
    if not is_aot and (aot_flag or only_flag):
        manifest.fail(PREFIX, f"{variant}: stock variant must not enable AOT")
    if f"-- {workers}" not in cmd:
        manifest.fail(PREFIX, f"{variant}: worker arg {workers} not in command")
    return variant, workers, is_aot


def main():
    m = manifest.load(PREFIX)
    variant, workers, is_aot = validate(m)
    obs = json.load(sys.stdin)
    stderr = obs.get("stderr", "")
    lines = stderr if isinstance(stderr, list) else stderr.splitlines()

    peak = None
    anon = None
    for line in lines:
        mm = RSS_RE.search(line)
        if mm:
            peak = int(mm.group(1))
        mm = ANON_EXEC_RE.search(line)
        if mm:
            anon = int(mm.group(1))
    if peak is None:
        manifest.fail(PREFIX, "peak_rss_kb not found in stderr; wrapper failed")
    if anon is None:
        manifest.fail(PREFIX, "peak_anon_exec_kb not found in stderr; wrapper failed")

    iteration = obs.get("iteration")
    if not isinstance(iteration, int) or iteration < 1:
        manifest.fail(PREFIX, f"invalid iteration {iteration!r}")

    metrics = {
        "peak_rss_kb": peak,
        "peak_rss_mb": round(peak / 1024, 3),
        "peak_anon_exec_kb": anon,
        "peak_anon_exec_mb": round(anon / 1024, 3),
        "workers": workers,
        "aot": is_aot,
    }
    out = {
        **metrics,
        "runs": {f"run_{iteration:02d}": metrics},
        "meta": {
            "variant": variant,
            "commit": m.get("git", {}).get("commit", ""),
            "iterations": m.get("iterations"),
        },
    }
    json.dump(out, sys.stdout)


if __name__ == "__main__":
    main()
