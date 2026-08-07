#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Condensed AOT coverage summary table: rows are coverage figures,
columns are the two browser workloads. Each cell prints mean ± stddev
across default_iterations. Percentages carry a trailing '%'; raw
counts are grouped by thousands.
"""

import sys

from fossil_figures import apply_style, load_stdin, comparison_table

apply_style(column="single")
data = load_stdin()
table = data.flat_table()
columns = data.column_names


def fmt(scalar, *, unit=""):
    m, s = scalar.mean, scalar.stddev
    if unit == "%":
        return f"{m:.1f}% ± {s:.1f}"
    if abs(m) >= 1_000_000:
        return f"{m/1_000_000:.2f}M ± {s/1_000_000:.2f}M"
    if abs(m) >= 10_000:
        return f"{m/1_000:.1f}k ± {s/1_000:.1f}k"
    return f"{m:,.0f} ± {s:,.0f}"


ROWS = [
    ("Baseline corpus size",         "utilization.baseline_functions.total",   ""),
    ("Baseline blobs used",          "utilization.baseline_functions.used",    ""),
    ("Baseline utilization",         "utilization.baseline_functions.pct",     "%"),
    ("Baseline installs from AOT",   "requests.baseline_functions.aot_hit",    ""),
    ("Baseline compiles",            "requests.baseline_functions.compiled",   ""),
    ("Baseline AOT hit rate",        "requests.baseline_functions.aot_hit_pct", "%"),
    ("Self-hosted baseline used",    "self_hosted_used_baseline",              ""),
    ("IC corpus size",               "utilization.ic_stubs.total",             ""),
    ("IC blobs used",                "utilization.ic_stubs.used",              ""),
    ("IC utilization",               "utilization.ic_stubs.pct",               "%"),
    ("IC requests total",            "requests.ic_stubs.total",                ""),
    ("IC served by AOT",             "requests.ic_stubs.aot_hit",              ""),
    ("IC served by zone cache",      "requests.ic_stubs.zone_cache_hit",       ""),
    ("IC compiles",                  "requests.ic_stubs.compiled",             ""),
    ("IC AOT hit rate",              "requests.ic_stubs.aot_hit_pct",          "%"),
    ("IC shapes requested",          "workload.ic_shapes_requested",           ""),
    ("IC shapes served by AOT",      "workload.ic_shapes_served",              ""),
    ("IC shapes raced",              "workload.ic_shapes_raced",               ""),
    ("IC workload coverage",         "workload.coverage_pct",                  "%"),
    ("Firefox procs recorded",       "n_procs",                                ""),
]

row_labels = [label for label, _, _ in ROWS]
col_labels = [c.replace("speedometer3", "Speedometer 3")
              .replace("jetstream3", "JetStream 3")
              for c in columns]

cells = []
for _, path, unit in ROWS:
    row = []
    for col in columns:
        scalar = table[col].get(path)
        row.append(fmt(scalar, unit=unit) if scalar is not None else "—")
    cells.append(row)

fig = comparison_table(
    row_labels=row_labels,
    col_labels=col_labels,
    cells=cells,
    title="AOT corpus coverage on browser workloads (n=3)",
)
fig.savefig(sys.argv[1])
