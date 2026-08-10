#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Emit shell-memory-table.json for the paper's memory subsection.

One row per worker count with stock/aot totals for total RSS and
anonymous-executable residency, plus a percent reduction on anon-exec
(the JIT-attributable slice). A final `slope-mb-per-N` row carries
the OLS slope of each column vs N (fit on N > 1), so the paper can
cite per-runtime marginal cost via `cell-value`."""

import re
import sys
from pathlib import Path

from fossil_figures import load_stdin, write_typst_table


VARIANT_RE = re.compile(r"^n(\d+)(-aot)?$")


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


def main():
    data = load_stdin()

    by_n = {}
    for variant, metric in data.columns.items():
        match = VARIANT_RE.match(variant)
        if not match:
            continue
        n = int(match.group(1))
        kind = "aot" if match.group(2) else "stock"
        by_n.setdefault(n, {})[kind] = {
            "rss": scalar(metric, "peak_rss_mb"),
            "anon": scalar(metric, "peak_anon_exec_mb"),
        }

    Ns = sorted(n for n, v in by_n.items() if "stock" in v and "aot" in v)
    if not Ns:
        raise SystemExit("memory_table: no complete stock+aot pairs")

    def reduction(stock, aot):
        return 1.0 - aot / stock if stock > 0 else 0.0

    rows = []
    for n in Ns:
        stock = by_n[n]["stock"]
        aot = by_n[n]["aot"]
        rows.append([
            str(n),
            stock["rss"], aot["rss"], reduction(stock["rss"], aot["rss"]),
            stock["anon"], aot["anon"], reduction(stock["anon"], aot["anon"]),
        ])

    Ns_fit = [n for n in Ns if n > 1]
    if len(Ns_fit) >= 2:
        s_rss_stock = slope([(n, by_n[n]["stock"]["rss"]) for n in Ns_fit])
        s_rss_aot   = slope([(n, by_n[n]["aot"]["rss"])   for n in Ns_fit])
        s_ae_stock  = slope([(n, by_n[n]["stock"]["anon"]) for n in Ns_fit])
        s_ae_aot    = slope([(n, by_n[n]["aot"]["anon"])   for n in Ns_fit])
        rows.append([
            "slope-mb-per-N",
            s_rss_stock, s_rss_aot, reduction(s_rss_stock, s_rss_aot),
            s_ae_stock, s_ae_aot, reduction(s_ae_stock, s_ae_aot),
        ])

    write_typst_table(
        Path(sys.argv[1]).with_suffix(".json"),
        columns=[
            {"key": "workers",             "label": "N",              "align": "right", "format": "str"},
            {"key": "stock_rss_mb",        "label": "stock RSS",      "align": "right", "format": "float"},
            {"key": "aot_rss_mb",          "label": "aot RSS",        "align": "right", "format": "float"},
            {"key": "rss_reduction",       "label": "RSS Δ",          "align": "right", "format": "percent"},
            {"key": "stock_anon_exec_mb",  "label": "stock anon-exec", "align": "right", "format": "float"},
            {"key": "aot_anon_exec_mb",    "label": "aot anon-exec",   "align": "right", "format": "float"},
            {"key": "anon_exec_reduction", "label": "anon-exec Δ",     "align": "right", "format": "percent"},
        ],
        rows=rows,
    )


if __name__ == "__main__":
    main()
