#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Speedometer throughput for any set of variants, relative to interp-only."""

import math
import statistics
import sys

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
from fossil_figures import apply_style, get_colors, load_stdin

from common import (
    run_values,
    save_png_and_pdf,
    scalar_at,
    validate_data,
)


NORMALIZE_TO = "interp-only"


def tick_step(x_max):
    for limit, step in ((2.0, 0.25), (4.0, 0.5), (8.0, 1.0)):
        if x_max <= limit:
            return step
    return 2.0


apply_style(column="double")
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42
data = load_stdin()
validate_data(data, baseline=NORMALIZE_TO)

baseline = run_values(data.columns[NORMALIZE_TO], "score")
baseline_score = statistics.fmean(baseline)
rows = []
for variant in data.column_names:
    values = run_values(data.columns[variant], "score")
    score = statistics.fmean(values)
    per_run_ratios = [v / baseline_score for v in values]
    ratio_std = statistics.stdev(per_run_ratios) if len(per_run_ratios) > 1 else 0.0
    rows.append((variant, score, score / baseline_score, len(values), ratio_std))

# Keep the normalization anchor first. Sort every other configuration by
# throughput so arbitrary variant names still produce a useful plot.
rows.sort(key=lambda row: (row[0] != NORMALIZE_TO, row[2], row[0]))
variants = [row[0] for row in rows]
scores = [row[1] for row in rows]
ratios = [row[2] for row in rows]
run_counts = [row[3] for row in rows]
ratio_errs = [row[4] for row in rows]
colors = get_colors(variants)

y_positions = np.arange(len(variants))
height = max(3.0, 1.8 + 0.36 * len(variants))
fig, (bar_ax, score_ax, delta_ax) = plt.subplots(
    1,
    3,
    figsize=(7.0, height),
    sharey=True,
    gridspec_kw={"width_ratios": [5.6, 0.75, 1.05]},
)
fig.suptitle(
    "Speedometer 3 Throughput",
    fontsize=10.5,
    fontweight="bold",
    x=0.5,
    ha="center",
    y=0.965,
)

bar_ax.barh(
    y_positions,
    ratios,
    height=0.66,
    color=colors,
    edgecolor="none",
    xerr=ratio_errs,
    error_kw={"ecolor": "#333333", "elinewidth": 0.8, "capsize": 2.5},
)
bar_ax.axvline(1.0, color="black", linewidth=0.8, linestyle="--")
bar_ax.set_yticks(y_positions)
bar_ax.set_yticklabels(variants)
bar_ax.invert_yaxis()
step = tick_step(max(ratios))
x_max = math.ceil(max(ratios) / step) * step
bar_ax.set_xlim(0.0, x_max)
bar_ax.set_xticks(np.arange(0.0, x_max + step / 2, step))
bar_ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}×"))
bar_ax.set_xlabel(f"Speedup over {NORMALIZE_TO}", labelpad=9)
bar_ax.grid(axis="y", visible=False)

for table_ax in (score_ax, delta_ax):
    table_ax.set_xlim(0.0, 1.0)
    table_ax.set_xticks([])
    table_ax.tick_params(axis="y", left=False, labelleft=False)
    table_ax.grid(False)
    for side in ("top", "right", "bottom"):
        table_ax.spines[side].set_visible(False)
    table_ax.spines["left"].set_color("#D8D8D8")
    table_ax.spines["left"].set_linewidth(0.8)

score_ax.set_title("Score", fontsize=8.5, fontweight="bold", pad=9)
delta_ax.set_title("Change", fontsize=8.5, fontweight="bold", pad=9)

for y, score, ratio, variant in zip(y_positions, scores, ratios, variants):
    score_ax.text(0.5, y, f"{score:.2f}", ha="center", va="center", fontsize=8.5)
    change = "0.00%" if variant == NORMALIZE_TO else f"{(ratio - 1.0) * 100:+.2f}%"
    delta_ax.text(0.5, y, change, ha="center", va="center", fontsize=8.5)

page_cycles = {
    int(scalar_at(data.columns[variant], "meta", "page_cycles"))
    for variant in variants
}
if len(set(run_counts)) == 1:
    noun = "run" if run_counts[0] == 1 else "runs"
    run_note = f"n={run_counts[0]} browser {noun} per variant"
else:
    run_note = f"n={min(run_counts)}–{max(run_counts)} browser runs per variant"
if len(page_cycles) == 1:
    cycle_note = f"{next(iter(page_cycles))} page cycles per run"
else:
    cycle_note = (
        f"{min(page_cycles)}–{max(page_cycles)} page cycles per run "
        "across variants"
    )
fig.text(
    0.5,
    0.008,
    f"Ratios of browser-run means; {run_note}; {cycle_note}.",
    ha="center",
    va="bottom",
    fontsize=6.2,
)
fig.subplots_adjust(
    left=min(0.40, max(0.24, 0.16 + 0.006 * max(map(len, variants)))),
    right=0.99,
    bottom=0.27,
    top=0.83,
    wspace=0.04,
)
save_png_and_pdf(fig, sys.argv[1])
