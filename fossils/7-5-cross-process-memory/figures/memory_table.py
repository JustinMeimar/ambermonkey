#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Emit per-benchmark peak-memory tables for the Octane suite.

Five configurations per benchmark:

    interp    --no-jit-backend
    baseline  --no-ion
    stock     (default)
    aot       --aot
    aot-only  --aot --aot-only

Three metrics captured; three tables emitted alongside the primary
output path:

    memory-table.json           full RSS (getrusage ru_maxrss)
    memory-table-anon.json      private-anonymous RSS (all anon VMAs)
    memory-table-anon-exec.json JIT slice (anon + executable VMAs)

Each table has rows = benchmarks (Octane order) plus a final `geomean`
row over the benchmark set. Columns: interp | baseline | stock | aot |
aot-only | (aot vs stock) | (aot-only vs stock) | (aot-only vs baseline).
The three reductions give (i) the drop-in reading, (ii) the strict-AOT
same-Ion reading, and (iii) the strict-AOT versus runtime-baseline
reading with Ion asymmetric."""

import math
import re
import sys
from pathlib import Path

from fossil_figures import load_stdin, write_typst_table


VARIANT_RE = re.compile(r"^(?P<bench>[a-z0-9-]+)-(?P<kind>interp|baseline|stock|aot-only|aot)$")

KINDS = ("interp", "baseline", "stock", "aot", "aot-only")

BENCH_ORDER = (
    "richards", "deltablue", "crypto", "raytrace", "earley-boyer", "regexp",
    "splay", "navier-stokes", "pdfjs", "mandreel", "gbemu", "code-load",
    "box2d", "zlib", "typescript",
)


def scalar(metric, key):
    return metric.children[key].scalar.mean


def reduction(base, aot):
    return 1.0 - aot / base if base > 0 else 0.0


def geomean(values):
    positive = [v for v in values if v > 0]
    if not positive:
        return 0.0
    return math.exp(sum(math.log(v) for v in positive) / len(positive))


def build_rows(by_bench, metric_key):
    complete = [b for b in BENCH_ORDER if b in by_bench and all(k in by_bench[b] for k in KINDS)]
    if not complete:
        raise SystemExit(f"memory_table: no complete five-way rows for {metric_key}")

    rows = []
    per_col = {k: [] for k in KINDS}
    reds_aot_vs_stock = []
    reds_only_vs_stock = []
    reds_only_vs_baseline = []
    for bench in complete:
        interp   = by_bench[bench]["interp"][metric_key]
        baseline = by_bench[bench]["baseline"][metric_key]
        stock    = by_bench[bench]["stock"][metric_key]
        aot      = by_bench[bench]["aot"][metric_key]
        aot_only = by_bench[bench]["aot-only"][metric_key]
        r_as = reduction(stock, aot)
        r_os = reduction(stock, aot_only)
        r_ob = reduction(baseline, aot_only)
        rows.append([bench, interp, baseline, stock, aot, aot_only, r_as, r_os, r_ob])
        per_col["interp"].append(interp)
        per_col["baseline"].append(baseline)
        per_col["stock"].append(stock)
        per_col["aot"].append(aot)
        per_col["aot-only"].append(aot_only)
        reds_aot_vs_stock.append(r_as)
        reds_only_vs_stock.append(r_os)
        reds_only_vs_baseline.append(r_ob)

    rows.append([
        "geomean",
        geomean(per_col["interp"]),
        geomean(per_col["baseline"]),
        geomean(per_col["stock"]),
        geomean(per_col["aot"]),
        geomean(per_col["aot-only"]),
        sum(reds_aot_vs_stock) / len(reds_aot_vs_stock),
        sum(reds_only_vs_stock) / len(reds_only_vs_stock),
        sum(reds_only_vs_baseline) / len(reds_only_vs_baseline),
    ])
    return rows


def columns_for(metric_label):
    return [
        {"key": "bench",                "label": "benchmark",                "align": "left",  "format": "str"},
        {"key": "interp_mb",            "label": f"interp {metric_label}",   "align": "right", "format": "float"},
        {"key": "baseline_mb",          "label": f"baseline {metric_label}", "align": "right", "format": "float"},
        {"key": "stock_mb",             "label": f"stock {metric_label}",    "align": "right", "format": "float"},
        {"key": "aot_mb",               "label": f"aot {metric_label}",      "align": "right", "format": "float"},
        {"key": "aot_only_mb",          "label": f"aot-only {metric_label}", "align": "right", "format": "float"},
        {"key": "reduction_aot_stock",  "label": "aot vs stock",             "align": "right", "format": "percent"},
        {"key": "reduction_only_stock", "label": "aot-only vs stock",        "align": "right", "format": "percent"},
        {"key": "reduction_only_base",  "label": "aot-only vs baseline",     "align": "right", "format": "percent"},
    ]


def main():
    data = load_stdin()

    by_bench = {}
    for variant, metric in data.columns.items():
        match = VARIANT_RE.match(variant)
        if not match:
            continue
        bench = match.group("bench")
        kind = match.group("kind")
        by_bench.setdefault(bench, {})[kind] = {
            "rss":       scalar(metric, "peak_rss_mb"),
            "anon":      scalar(metric, "peak_anon_mb"),
            "anon_exec": scalar(metric, "peak_anon_exec_mb"),
        }

    base = Path(sys.argv[1])
    write_typst_table(
        base.with_suffix(".json"),
        columns=columns_for("RSS"),
        rows=build_rows(by_bench, "rss"),
    )
    write_typst_table(
        base.with_name("memory-table-anon.json"),
        columns=columns_for("anon MB"),
        rows=build_rows(by_bench, "anon"),
    )
    write_typst_table(
        base.with_name("memory-table-anon-exec.json"),
        columns=columns_for("JIT MB"),
        rows=build_rows(by_bench, "anon_exec"),
    )


if __name__ == "__main__":
    main()
