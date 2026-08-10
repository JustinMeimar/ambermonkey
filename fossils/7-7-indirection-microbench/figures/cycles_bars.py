#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Two-bar chart of cycles_per_iter for head vs no-opts. The delta between
bars is the marginal cost of the reverted perf opts on this microbench."""

import sys

import matplotlib.pyplot as plt
import numpy as np

from fossil_figures import apply_style, load_stdin


VARIANTS = ("head", "no-opts")
METRIC = "cycles_per_iter"
COLORS = ("#4c72b0", "#dd8452")


def scalar(table, column, metric):
    entry = table.get(column, {}).get(metric)
    if entry is None:
        return None
    return entry.mean, entry.stddev


apply_style(column="single")
data = load_stdin()
table = data.flat_table()

means = []
stds = []
labels = []
skipped = []
for v in VARIANTS:
    got = scalar(table, v, METRIC)
    if got is None:
        skipped.append(v)
        continue
    means.append(got[0])
    stds.append(got[1])
    labels.append(v)

for v in skipped:
    print(f"cycles_bars: skipping {v}; no {METRIC} data", file=sys.stderr)

if len(labels) < 1:
    raise SystemExit("cycles_bars: no cell has cycles_per_iter data")

fig, ax = plt.subplots(figsize=(4, 3))
x = np.arange(len(labels))
ax.bar(
    x, means, yerr=stds, width=0.5,
    color=COLORS[: len(labels)], edgecolor="none",
)
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.set_ylabel("cycles per iteration (user)")
ax.set_title("AOT indirection ablation: hot loop cycle cost")

for i, (m, s) in enumerate(zip(means, stds)):
    ax.text(x[i], m + s, f"{m:.2f}", ha="center", va="bottom", fontsize=8)

if len(labels) == 2 and means[0] > 0:
    ratio = means[1] / means[0]
    delta = means[1] - means[0]
    ax.text(
        0.5, 0.95,
        f"no-opts / head = {ratio:.3f} (+{delta:.2f} cyc/iter)",
        transform=ax.transAxes, ha="center", va="top", fontsize=8,
    )

fig.tight_layout()
fig.savefig(sys.argv[1])
