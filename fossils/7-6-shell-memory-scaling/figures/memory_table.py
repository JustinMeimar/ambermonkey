#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Emit shell-memory-table.json for the paper's memory subsection.

Four variants per worker count. The table reports peak anonymous-executable
residency (the JIT-attributable slice) for all four, plus the two natural
reduction pairs:

  (stock-base -> aot-restricted)  restricted-execution deployment
  (stock-full -> aot-full)        opportunistic sharing in a full-tier deployment

A final `slope-mb-per-N` row carries the OLS slope of each column vs N
(fit on N > 1) so the paper can cite per-runtime marginal cost via cell-value.

Total RSS is dominated by non-JIT per-worker overhead and is emitted to a
companion JSON so the memory subsection can reference it separately."""

import re
import sys
from pathlib import Path

from fossil_figures import load_stdin, write_typst_table


VARIANT_RE = re.compile(r"^n(\d+)-(stock-base|stock-full|aot-restricted|aot-full)$")

KINDS = ("stock-base", "stock-full", "aot-restricted", "aot-full")


def scalar(metric, key):
    return metric.children[key].scalar.mean


def slope(pairs):
    """Ordinary least-squares slope of y vs x."""
    n = len(pairs)
    sx = sum(p[0] for p in pairs)
    sy = sum(p[1] for p in pairs)
    sxx = sum(p[0] * p[0] for p in pairs)
    sxy = sum(p[0] * p[1] for p in pairs)
    denom = n * sxx - sx * sx
    if denom == 0:
        return 0.0
    return (n * sxy - sx * sy) / denom


def reduction(base, aot):
    return 1.0 - aot / base if base > 0 else 0.0


def build_rows(by_n, metric_key):
    Ns = sorted(n for n, v in by_n.items() if all(k in v for k in KINDS))
    if not Ns:
        raise SystemExit(f"memory_table: no complete four-way rows for {metric_key}")

    rows = []
    for n in Ns:
        stock_base = by_n[n]["stock-base"][metric_key]
        stock_full = by_n[n]["stock-full"][metric_key]
        aot_rest   = by_n[n]["aot-restricted"][metric_key]
        aot_full   = by_n[n]["aot-full"][metric_key]
        rows.append([
            str(n),
            stock_base,
            aot_rest,
            reduction(stock_base, aot_rest),
            stock_full,
            aot_full,
            reduction(stock_full, aot_full),
        ])

    Ns_fit = [n for n in Ns if n > 1]
    if len(Ns_fit) >= 2:
        def col_slope(kind):
            return slope([(n, by_n[n][kind][metric_key]) for n in Ns_fit])
        s_base = col_slope("stock-base")
        s_full = col_slope("stock-full")
        s_rest = col_slope("aot-restricted")
        s_afull = col_slope("aot-full")
        rows.append([
            "slope-mb-per-N",
            s_base, s_rest, reduction(s_base, s_rest),
            s_full, s_afull, reduction(s_full, s_afull),
        ])
    return rows


def main():
    data = load_stdin()

    by_n = {}
    for variant, metric in data.columns.items():
        match = VARIANT_RE.match(variant)
        if not match:
            continue
        n = int(match.group(1))
        kind = match.group(2)
        by_n.setdefault(n, {})[kind] = {
            "anon": scalar(metric, "peak_anon_exec_mb"),
            "rss":  scalar(metric, "peak_rss_mb"),
        }

    anon_columns = [
        {"key": "workers",              "label": "N",                     "align": "right", "format": "str"},
        {"key": "stock_base_mb",        "label": "stock --no-ion",        "align": "right", "format": "float"},
        {"key": "aot_restricted_mb",    "label": "aot --aot-only",        "align": "right", "format": "float"},
        {"key": "restricted_reduction", "label": "restricted Δ",          "align": "right", "format": "percent"},
        {"key": "stock_full_mb",        "label": "stock default",         "align": "right", "format": "float"},
        {"key": "aot_full_mb",          "label": "aot",                   "align": "right", "format": "float"},
        {"key": "full_reduction",       "label": "full-tier Δ",           "align": "right", "format": "percent"},
    ]

    write_typst_table(
        Path(sys.argv[1]).with_suffix(".json"),
        columns=anon_columns,
        rows=build_rows(by_n, "anon"),
    )

    # Companion RSS table alongside the primary anon-exec output.
    rss_path = Path(sys.argv[1]).with_name("memory-table-rss.json")
    rss_columns = [dict(c) for c in anon_columns]
    for c in rss_columns[1:]:
        if c["key"].endswith("_mb"):
            c["label"] = c["label"] + " (RSS)"
    write_typst_table(
        rss_path,
        columns=rss_columns,
        rows=build_rows(by_n, "rss"),
    )


if __name__ == "__main__":
    main()
