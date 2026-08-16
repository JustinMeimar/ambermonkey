#!/usr/bin/env python3
"""Summarise 3-3 inter-workload records into a paper-consumable JSON."""

import json
import os
import statistics
import sys
from collections import Counter

SITES = (
    "amazon", "bing-search", "buzzfeed", "cnn",
    "ebay", "espn", "expedia", "facebook",
)

RECORDS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "records"
)


def latest_record_per_site(records_dir):
    latest = {}
    for d in sorted(os.listdir(records_dir)):
        parts = d.split("_")
        site = "_".join(parts[3:-1])
        if site in SITES:
            latest[site] = d
    missing = [s for s in SITES if s not in latest]
    if missing:
        sys.exit(f"missing sites: {missing}")
    return latest


def load_counters(records_dir, latest):
    ic_sets, ic_freqs, bl_sets, bl_freqs = {}, {}, {}, {}
    for site in SITES:
        with open(os.path.join(records_dir, latest[site], "results.json")) as f:
            r = json.load(f)
        ic_req, ic_ent, bl_comp, bl_ent = Counter(), Counter(), Counter(), Counter()
        for obs in r.get("observations", []):
            stdout = obs.get("stdout")
            if isinstance(stdout, list):
                stdout = "\n".join(stdout)
            payload = json.loads(stdout.strip())
            ic_c = ((payload.get("ic") or {}).get("content") or {})
            bl_c = ((payload.get("baseline") or {}).get("content") or {})
            ic_req.update({k: int(v) for k, v in ic_c.get("attaches", {}).items()})
            ic_ent.update({k: int(v) for k, v in ic_c.get("entered", {}).items()})
            bl_comp.update({k: int(v) for k, v in bl_c.get("compiles", {}).items()})
            bl_ent.update({k: int(v) for k, v in bl_c.get("entered", {}).items()})
        ic_sets[site] = set(ic_req)
        ic_freqs[site] = ic_ent
        bl_sets[site] = set(bl_comp)
        bl_freqs[site] = bl_ent
    return ic_sets, ic_freqs, bl_sets, bl_freqs


def jaccard(a, b):
    u = a | b
    return len(a & b) / len(u) if u else 0.0


def coverage(source_set, target_freq):
    total = sum(target_freq.values())
    if not total:
        return 0.0
    return sum(c for k, c in target_freq.items() if k in source_set) / total


def matrix(fn, rows, cols):
    return [[fn(rows[a], cols[b]) for b in SITES] for a in SITES]


def off_diagonal(m):
    n = len(SITES)
    return [m[i][j] for i in range(n) for j in range(n) if i != j]


def per_target_range(m):
    n = len(SITES)
    ranges = {}
    for j, tgt in enumerate(SITES):
        vals = [m[i][j] for i in range(n) if i != j]
        ranges[tgt] = {"min": min(vals), "max": max(vals)}
    return ranges


def find_argmin_pair(m):
    n = len(SITES)
    best = None
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if best is None or m[i][j] < best[0]:
                best = (m[i][j], SITES[i], SITES[j])
    return {"value": best[0], "corpus": best[1], "target": best[2]}


def main():
    latest = latest_record_per_site(RECORDS_DIR)
    ic_sets, ic_freqs, bl_sets, bl_freqs = load_counters(RECORDS_DIR, latest)

    bl_j = matrix(jaccard, bl_sets, bl_sets)
    ic_j = matrix(jaccard, ic_sets, ic_sets)
    bl_cov = matrix(coverage, bl_sets, bl_freqs)
    ic_cov = matrix(coverage, ic_sets, ic_freqs)

    ic_off = off_diagonal(ic_cov)
    ge_thresh = 0.95
    ic_ge = sum(1 for v in ic_off if v >= ge_thresh)

    output = {
        "sites": list(SITES),
        "site_count": len(SITES),
        "off_diagonal_count": len(ic_off),
        "medians": {
            "baseline_jaccard": statistics.median(off_diagonal(bl_j)),
            "ic_jaccard": statistics.median(off_diagonal(ic_j)),
            "baseline_coverage": statistics.median(off_diagonal(bl_cov)),
            "ic_coverage": statistics.median(ic_off),
        },
        "baseline_coverage_per_target": per_target_range(bl_cov),
        "ic_coverage_per_target": per_target_range(ic_cov),
        "ic_coverage_threshold": ge_thresh,
        "ic_coverage_pairs_at_or_above_threshold": ic_ge,
        "ic_coverage_argmin": find_argmin_pair(ic_cov),
    }

    if len(sys.argv) > 1:
        with open(sys.argv[1], "w") as fh:
            json.dump(output, fh, indent=2, sort_keys=True)
            fh.write("\n")
    else:
        json.dump(output, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
