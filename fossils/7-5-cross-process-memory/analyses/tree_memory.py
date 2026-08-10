#!/usr/bin/env python3

import json
import os
import sys

sys.path.insert(0, os.environ["FOSSIL_PROJECT_DIR"] + "/scripts")
from benchmarks import manifest

PREFIX = "tree_memory"

VARIANTS = {
    "stock": "build-browser-release/dist/bin/firefox",
    "aot":   "build-browser-release-aot/dist/bin/firefox",
}


def validate(m):
    variant = m.get("variant")
    if variant not in VARIANTS:
        manifest.fail(PREFIX, f"unexpected variant {variant!r}")
    cmd = m.get("command", "")
    if "./mach awsy-test" not in cmd:
        manifest.fail(PREFIX, f"{variant}: command must run ./mach awsy-test")
    if VARIANTS[variant] not in cmd:
        manifest.fail(PREFIX, f"{variant}: binary path {VARIANTS[variant]!r} not in command")
    for other, path in VARIANTS.items():
        if other != variant and path in cmd:
            manifest.fail(PREFIX, f"{variant}: unexpected other-binary path {path!r}")
    return variant


def bin_samples(samples, bin_seconds=0.5):
    """Group by half-second bins. Within a bin, sum a metric across pids;
    that per-bin sum is one observation of tree-wide residency."""
    bins = {}
    for row in samples:
        bucket = int(row["ts"] / bin_seconds)
        agg = bins.setdefault(bucket, {"pids": set(), "rss": 0, "pss": 0})
        pid = row["pid"]
        if pid in agg["pids"]:
            continue
        agg["pids"].add(pid)
        agg["rss"] += row["rss"]
        agg["pss"] += row["pss"]
    return sorted(bins.items())


def stats(values):
    if not values:
        return None
    values = sorted(values)
    n = len(values)
    return {
        "peak": max(values),
        "mean": sum(values) / n,
        "median": values[n // 2],
        "n": n,
    }


def main():
    m = manifest.load(PREFIX)
    variant = validate(m)
    obs = json.load(sys.stdin)
    stdout = obs.get("stdout", "")
    text = "\n".join(stdout) if isinstance(stdout, list) else stdout
    if not isinstance(text, str) or not text.strip():
        manifest.fail(PREFIX, "empty stdout; sampler + jq produced no JSON")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        manifest.fail(PREFIX, f"malformed sampler JSON: {exc}")
    samples = payload.get("samples")
    if not isinstance(samples, list) or not samples:
        manifest.fail(PREFIX, "no samples in observation")

    bins = bin_samples(samples)
    if not bins:
        manifest.fail(PREFIX, "no bins produced from samples")

    rss_sums_kb = [b[1]["rss"] for b in bins]
    pss_sums_kb = [b[1]["pss"] for b in bins]
    proc_counts = [len(b[1]["pids"]) for b in bins]

    rss = stats(rss_sums_kb)
    pss = stats(pss_sums_kb)

    def mb(kb):
        return round(kb / 1024, 3)

    iteration = obs.get("iteration")
    if not isinstance(iteration, int) or iteration < 1:
        manifest.fail(PREFIX, f"invalid iteration {iteration!r}")

    metrics = {
        "rss_sum_peak_mb":  mb(rss["peak"]),
        "rss_sum_mean_mb":  mb(rss["mean"]),
        "rss_sum_median_mb": mb(rss["median"]),
        "pss_sum_peak_mb":  mb(pss["peak"]),
        "pss_sum_mean_mb":  mb(pss["mean"]),
        "pss_sum_median_mb": mb(pss["median"]),
        "pss_over_rss_mean": round(pss["mean"] / rss["mean"], 4) if rss["mean"] else None,
        "sample_bins":       rss["n"],
        "peak_process_count": max(proc_counts),
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
