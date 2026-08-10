#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Grouped bar chart: for each variant, mean RSS-sum and mean PSS-sum
across iterations. Error bars are per-variant stddev of the mean.
The gap between the two bars for a single variant is the amount of
browser-tree memory that is CoW-shared under that variant."""

import sys

import matplotlib.pyplot as plt
import numpy as np

from fossil_figures import apply_style, load_stdin


VARIANTS = ("stock", "aot")
METRICS  = (("rss_sum_mean_mb", "RSS-sum"),
            ("pss_sum_mean_mb", "PSS-sum"))


def scalar(table, variant, metric):
    entry = table.get(variant, {}).get(metric)
    if entry is None:
        return None
    return entry.mean, entry.stddev


apply_style(column="single")
data = load_stdin()
table = data.flat_table()

n_variants = len(VARIANTS)
n_metrics = len(METRICS)
width = 0.35
x = np.arange(n_variants)

means_by_metric = {}
errs_by_metric = {}
skipped = []
for key, _ in METRICS:
    ms, es = [], []
    for v in VARIANTS:
        entry = scalar(table, v, key)
        if entry is None:
            skipped.append((v, key))
            ms.append(0.0)
            es.append(0.0)
        else:
            ms.append(entry[0])
            es.append(entry[1])
    means_by_metric[key] = ms
    errs_by_metric[key] = es

for v, key in skipped:
    print(f"tree_memory_bars: missing {key} for variant {v}", file=sys.stderr)

fig, ax = plt.subplots(figsize=(5.5, 3.2))
colors = ("#4c72b0", "#dd8452")
for i, (key, label) in enumerate(METRICS):
    offset = (i - (n_metrics - 1) / 2) * width
    ax.bar(x + offset, means_by_metric[key], width,
           yerr=errs_by_metric[key], label=label,
           color=colors[i], edgecolor="none")
    for xi, (m, e) in enumerate(zip(means_by_metric[key], errs_by_metric[key])):
        ax.text(x[xi] + offset, m + e + 20, f"{m:.0f}",
                ha="center", va="bottom", fontsize=8)

ax.set_xticks(x)
ax.set_xticklabels(VARIANTS)
ax.set_ylabel("Browser-tree memory (MB)")
ax.set_title("AWSY tp6: mean RSS-sum vs PSS-sum")
ax.legend(loc="upper right", frameon=False, fontsize=8)
ax.set_ylim(0, ax.get_ylim()[1] * 1.1)
fig.tight_layout()
fig.savefig(sys.stdout.buffer, format="pdf")
