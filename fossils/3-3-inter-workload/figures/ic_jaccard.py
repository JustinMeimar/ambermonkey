#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Three-panel heatmap for the alphabetical eight-workload TP6 subset.

Panel (a) uses the upper triangle for IC-body Jaccard and the lower triangle
for Baseline-function Jaccard. Panels (b) and (c) are full directional
matrices: row A is the candidate corpus and column B is the target workload.
Every panel uses the same blue-to-red scale and every cell is annotated.
"""

import sys
from decimal import ROUND_DOWN, Decimal

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from fossil_figures import apply_style, load_stdin


apply_style(column="double")
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42
data = load_stdin()
tp6_subset = (
    "amazon",
    "bing-search",
    "buzzfeed",
    "cnn",
    "ebay",
    "espn",
    "expedia",
    "facebook",
)
missing = [name for name in tp6_subset if name not in data.columns]
if missing:
    print(
        "artifact-overlap: missing selected TP6 workloads: " + ", ".join(missing),
        file=sys.stderr,
    )
    sys.exit(1)

columns = list(tp6_subset)
n = len(columns)


def tag(metric, key):
    if not metric.children or key not in metric.children:
        return ""
    return (metric.children[key].tag or "").strip()


def decode_set(metric, key):
    encoded = tag(metric, key)
    return set(encoded.split(",")) if encoded else set()


def decode_counter(metric, key):
    encoded = tag(metric, key)
    values = {}
    if encoded:
        for entry in encoded.split(";"):
            identity, count = entry.rsplit("=", 1)
            values[identity] = int(count)
    return values


def floor_2(value):
    """Format a non-negative matrix value without rounding it upward."""
    return format(
        Decimal(str(value)).quantize(Decimal("0.00"), rounding=ROUND_DOWN),
        ".2f",
    )


def text_color(cmap, norm, value):
    """Choose legible annotation text from the rendered cell luminance."""
    red, green, blue, _ = cmap(norm(value))
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return "white" if luminance < 0.48 else "black"


def jaccard_matrix(sets):
    matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            union = sets[i] | sets[j]
            matrix[i, j] = len(sets[i] & sets[j]) / len(union) if union else 0.0
    return matrix


def directional_coverage(source_sets, target_frequencies):
    matrix = np.zeros((n, n))
    for i, source in enumerate(source_sets):
        for j, target in enumerate(target_frequencies):
            total = sum(target.values())
            if total:
                matrix[i, j] = sum(
                    count for identity, count in target.items() if identity in source
                ) / total
    return matrix


metrics = [data.columns[column] for column in columns]
ic_sets = [decode_set(metric, "ic_hashes") for metric in metrics]
ic_frequencies = [decode_counter(metric, "ic_freqs") for metric in metrics]
baseline_sets = [decode_set(metric, "baseline_hashes") for metric in metrics]
baseline_frequencies = [decode_counter(metric, "baseline_freqs") for metric in metrics]

for column, ic_set, ic_freqs, baseline_set, baseline_freqs in zip(
    columns, ic_sets, ic_frequencies, baseline_sets, baseline_frequencies
):
    if not ic_set or not ic_freqs or not baseline_set or not baseline_freqs:
        print(f"artifact-overlap: incomplete metrics for {column}", file=sys.stderr)
        sys.exit(1)

ic_jaccard = jaccard_matrix(ic_sets)
baseline_jaccard = jaccard_matrix(baseline_sets)
baseline_coverage = directional_coverage(baseline_sets, baseline_frequencies)
ic_coverage = directional_coverage(ic_sets, ic_frequencies)

# One fixed blue-to-red scale makes overlap and coverage directly comparable
# across both artifact families and all three panels. Coverage is a bounded
# proportion, so a symmetric logit transform expands both tails without
# collapsing the broad middle into an ad hoc neutral band.
cmap = mpl.colormaps["RdBu_r"].copy()
scale_epsilon = 0.01
scale_ticks = np.array(
    [0.00, 0.02, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.98, 1.00]
)


def scale_forward(values):
    clipped = np.clip(np.asarray(values), scale_epsilon, 1.0 - scale_epsilon)
    logits = np.log(clipped / (1.0 - clipped))
    lower = np.log(scale_epsilon / (1.0 - scale_epsilon))
    upper = -lower
    return (logits - lower) / (upper - lower)


def scale_inverse(positions):
    lower = np.log(scale_epsilon / (1.0 - scale_epsilon))
    upper = -lower
    logits = lower + np.asarray(positions) * (upper - lower)
    return 1.0 / (1.0 + np.exp(-logits))


norm = mpl.colors.FuncNorm(
    (scale_forward, scale_inverse),
    vmin=0.0,
    vmax=1.0,
)

static_baseline = np.full((n, n), np.nan)
static_ic = np.full((n, n), np.nan)
for i in range(n):
    for j in range(n):
        if i > j:
            static_baseline[i, j] = baseline_jaccard[i, j]
        elif i < j:
            static_ic[i, j] = ic_jaccard[i, j]

display = [name.replace("google-", "g-") for name in columns]
fig, axes = plt.subplots(1, 3, figsize=(7.0, 3.35))
titles = (
    "(a) Static intersection\nBaseline ◣  /  IC ◥",
    "(b) Baseline\nfunction-entry coverage",
    "(c) Inline-cache\nstub-entry coverage",
)

for index, (axis, title) in enumerate(zip(axes, titles)):
    if index == 0:
        axis.imshow(
            static_baseline,
            cmap=cmap,
            norm=norm,
            interpolation="nearest",
            aspect="equal",
        )
        axis.imshow(
            static_ic,
            cmap=cmap,
            norm=norm,
            interpolation="nearest",
            aspect="equal",
        )
    else:
        matrix = baseline_coverage if index == 1 else ic_coverage
        axis.imshow(
            matrix, cmap=cmap, norm=norm, interpolation="nearest", aspect="equal"
        )

    # White borders keep the values easy to follow across a dense matrix.
    axis.set_xticks(np.arange(-0.5, n, 1), minor=True)
    axis.set_yticks(np.arange(-0.5, n, 1), minor=True)
    axis.grid(which="minor", color="white", linewidth=0.6)
    axis.tick_params(which="minor", bottom=False, left=False)
    axis.grid(False, which="major")
    axis.set_title(title, fontsize=7.4, pad=5)
    axis.set_xlim(-0.5, n - 0.5)
    axis.set_ylim(n - 0.5, -0.5)
    axis.set_xticks(range(n))
    axis.set_xticklabels(
        display,
        rotation=55,
        rotation_mode="anchor",
        ha="right",
        va="top",
        fontsize=5.0,
    )
    axis.tick_params(axis="x", length=0, pad=1)
    if index == 0:
        axis.set_yticks(range(n))
        axis.set_yticklabels(display, fontsize=5.0)
        axis.tick_params(axis="y", length=0, pad=1)
    else:
        axis.set_yticks([])
    for spine in axis.spines.values():
        spine.set_visible(False)

    for i in range(n):
        for j in range(n):
            if i == j:
                value = 1.0
                axis.add_patch(
                    plt.Rectangle(
                        (j - 0.5, i - 0.5),
                        1,
                        1,
                        facecolor=cmap(norm(value)),
                        edgecolor="white",
                        linewidth=0.6,
                    )
                )
                color = text_color(cmap, norm, value)
                weight = "bold"
            elif index == 0:
                value = baseline_jaccard[i, j] if i > j else ic_jaccard[i, j]
                color = text_color(cmap, norm, value)
                weight = "normal"
            else:
                matrix = baseline_coverage if index == 1 else ic_coverage
                value = matrix[i, j]
                color = text_color(cmap, norm, value)
                weight = "normal"
            axis.text(
                j,
                i,
                floor_2(value),
                ha="center",
                va="center",
                fontsize=4.0,
                fontweight=weight,
                color=color,
            )

axes[0].set_xlabel("Workload", fontsize=6.3, labelpad=3)
axes[0].set_ylabel("Workload", fontsize=6.3, labelpad=3)
axes[1].set_xlabel("Target workload", fontsize=6.3, labelpad=3)
axes[2].set_xlabel("Target workload", fontsize=6.3, labelpad=3)
axes[1].set_ylabel("Corpus workload", fontsize=6.3, labelpad=3)
axes[2].set_ylabel("Corpus workload", fontsize=6.3, labelpad=3)

fig.subplots_adjust(left=0.105, right=0.935, bottom=0.30, top=0.89, wspace=0.25)
color_axis = fig.add_axes([0.950, 0.30, 0.012, 0.57])
colorbar = fig.colorbar(
    mpl.cm.ScalarMappable(norm=norm, cmap=cmap), cax=color_axis
)
colorbar.set_ticks(scale_ticks)
colorbar.set_ticklabels(
    ["0", ".02", ".05", ".1", ".25", ".5", ".75", ".9", ".95", ".98", "1"]
)
colorbar.ax.tick_params(labelsize=5.0, length=2)
colorbar.set_label("Overlap or coverage", fontsize=6.3)

fig.savefig(sys.argv[1], dpi=300)
