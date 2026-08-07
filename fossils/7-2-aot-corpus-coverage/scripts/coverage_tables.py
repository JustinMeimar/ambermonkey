#!/usr/bin/env python3
"""Fold buried coverage records into typst-ready tables on stdout.

Each record is named LABEL=RECORD, where RECORD is either a record
directory or a bare record id under --records. Naming records
explicitly rather than taking the last N is what makes an ablation
reproducible: a record is pinned to the image that was installed when
it ran, and nothing in the record says which image that was.

Two comparisons use this same shape. Holding the corpus fixed and
varying the workload asks how well a corpus generalizes. Holding the
workload fixed and varying the corpus asks what a corpus change cost,
and there --delta reports the second column minus the first.

Emits {"coverage": ..., "spread": ..., "meta": ...} where the first two
are in the {"columns": [...], "rows": [[...]]} shape the typst
json-table loader reads. `coverage` carries means, `spread` carries the
matching sample standard deviations. Values stay numeric.
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

# (row label, dotted path into the reducer summary, unit)
METRICS = [
    ("Baseline corpus size", "utilization.baseline_functions.total", ""),
    ("Baseline blobs used", "utilization.baseline_functions.used", ""),
    ("Baseline utilization", "utilization.baseline_functions.pct", "%"),
    ("Baseline installs from AOT", "requests.baseline_functions.aot_hit", ""),
    ("Baseline compiles", "requests.baseline_functions.compiled", ""),
    ("Baseline requests", "requests.baseline_functions.total", ""),
    ("Baseline AOT hit rate", "requests.baseline_functions.aot_hit_pct", "%"),
    ("Self-hosted baseline used", "self_hosted_used_baseline", ""),
    ("IC corpus size", "utilization.ic_stubs.total", ""),
    ("IC blobs used", "utilization.ic_stubs.used", ""),
    ("IC utilization", "utilization.ic_stubs.pct", "%"),
    ("IC requests", "requests.ic_stubs.total", ""),
    ("IC served by AOT", "requests.ic_stubs.aot_hit", ""),
    ("IC served by zone cache", "requests.ic_stubs.zone_cache_hit", ""),
    ("IC compiles", "requests.ic_stubs.compiled", ""),
    ("IC AOT hit rate", "requests.ic_stubs.aot_hit_pct", "%"),
    ("IC shapes requested", "workload.ic_shapes_requested", ""),
    ("IC shapes served by AOT", "workload.ic_shapes_served", ""),
    ("IC shapes raced", "workload.ic_shapes_raced", ""),
    ("IC workload coverage", "workload.coverage_pct", "%"),
    ("Firefox processes", "n_procs", ""),
]


def die(msg):
    sys.exit(f"coverage_tables: {msg}")


def resolve(value, records_root):
    path = Path(value)
    if path.is_dir():
        return path
    if records_root is not None:
        candidate = records_root / value
        if candidate.is_dir():
            return candidate
    die(f"no such record: {value}")


def peel(observation, label, iteration):
    """Recover the reducer's one-line JSON summary from an observation."""
    stdout = observation.get("stdout", "")
    if isinstance(stdout, list):
        stdout = "\n".join(stdout)
    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    if not lines:
        die(f"{label} iteration {iteration}: empty stdout, reducer did not run")
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError as e:
        die(f"{label} iteration {iteration}: stdout was not JSON: {e}")


def load(record, label):
    results = record / "results.json"
    if not results.is_file():
        die(f"{label}: {results} not found")
    observations = json.loads(results.read_text()).get("observations", [])
    if not observations:
        die(f"{label}: record has no observations")
    summaries = []
    for obs in observations:
        if obs.get("exit_code", 0) != 0:
            die(f"{label} iteration {obs.get('iteration')}: nonzero exit")
        summaries.append(peel(obs, label, obs.get("iteration")))
    return summaries


def dig(summary, path, label):
    node = summary
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            die(f"{label}: summary has no {path!r}; record predates the "
                f"request-time coverage schema")
        node = node[part]
    return node


def fold(summaries, path, label):
    values = [dig(s, path, label) for s in summaries]
    mean = statistics.fmean(values)
    spread = statistics.stdev(values) if len(values) > 1 else 0.0
    return mean, spread


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("record", nargs="+", metavar="LABEL=RECORD",
                    help="a buried record directory or id under a short label")
    ap.add_argument("--records", type=Path, default=None,
                    help="root to resolve bare record ids against")
    ap.add_argument("--delta", action="store_true",
                    help="append a column of the last label minus the first "
                         "(requires exactly two records)")
    args = ap.parse_args()

    labels, records = [], {}
    for pair in args.record:
        label, sep, value = pair.partition("=")
        if not sep or not label:
            die(f"record must be LABEL=RECORD, got {pair!r}")
        if label in records:
            die(f"duplicate label {label!r}")
        labels.append(label)
        records[label] = resolve(value, args.records)

    if args.delta and len(labels) != 2:
        die("--delta needs exactly two records")

    summaries = {label: load(records[label], label) for label in labels}

    columns = ["metric", "unit", *labels]
    if args.delta:
        columns.append("delta")

    means, spreads = [], []
    for name, path, unit in METRICS:
        folded = [fold(summaries[label], path, label) for label in labels]
        row = [name, unit, *(m for m, _ in folded)]
        if args.delta:
            row.append(folded[1][0] - folded[0][0])
        means.append(row)
        spreads.append([name, unit, *(s for _, s in folded)])

    json.dump({
        "coverage": {"columns": columns, "rows": means},
        "spread": {"columns": ["metric", "unit", *labels], "rows": spreads},
        "meta": {
            label: {
                "record": records[label].name,
                "iterations": len(summaries[label]),
            }
            for label in labels
        },
    }, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
