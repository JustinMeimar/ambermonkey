#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Split-triangle heatmap: Static Coverage below diagonal, Dynamic
Coverage above, per-variant executed-body count on the diagonal.

Lower triangle (i > j): symmetric static coverage over IC-body sets
    static[i][j] = |set_i ∩ set_j| / |set_i ∪ set_j|
    (formerly labelled Jaccard; renamed for symmetry with dynamic).
Upper triangle (i < j): asymmetric dynamic coverage
    dynamic[i][j] = sum_{k in freqs[j] and set[i]} freqs[j][k]
                    / sum_{k in freqs[j]} freqs[j][k]
    i.e. what fraction of variant j's execution weight lands on
    bodies that also appear in variant i's set. Diagonal is bold
    |executed_i|.
"""

import sys
from decimal import ROUND_DOWN, Decimal

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize

from fossil_figures import apply_style, font_sizes, load_stdin

apply_style(column="single")
fs = font_sizes()
data = load_stdin()
columns = data.column_names
n = len(columns)

if n < 2:
    print("Need at least 2 variants", file=sys.stderr)
    sys.exit(1)


def _tag(metric, key):
    if not metric.children or key not in metric.children:
        return ""
    return (metric.children[key].tag or "").strip()


def _floor_2(value):
    """Format a non-negative coverage value by rounding down."""
    return format(
        Decimal(str(value)).quantize(Decimal("0.00"), rounding=ROUND_DOWN),
        ".2f",
    )


hash_sets, freq_maps = {}, {}
for col in columns:
    m = data.columns[col]
    h = _tag(m, "hashes")
    hash_sets[col] = set(h.split(",")) if h else set()
    f = _tag(m, "freqs")
    d = {}
    if f:
        for entry in f.split(";"):
            k, v = entry.rsplit("=", 1)
            d[k] = int(v)
    freq_maps[col] = d

jaccard = np.zeros((n, n))
for i in range(n):
    for j in range(n):
        si, sj = hash_sets[columns[i]], hash_sets[columns[j]]
        u = len(si | sj)
        jaccard[i][j] = len(si & sj) / u if u else 0.0

coverage = np.zeros((n, n))
for i in range(n):
    corpus = hash_sets[columns[i]]
    for j in range(n):
        tgt = freq_maps[columns[j]]
        total = sum(tgt.values())
        if not total:
            continue
        coverage[i][j] = sum(v for k, v in tgt.items() if k in corpus) / total

universe, all_inter = set(), None
for s in hash_sets.values():
    universe |= s
    all_inter = s if all_inter is None else all_inter & s
all_inter = all_inter or set()

display = [c.capitalize() for c in columns]
cell = 0.52
w = cell * n + 1.6
h = cell * n + 0.9

cmap_j = plt.get_cmap("Blues")
cmap_c = plt.get_cmap("OrRd")
jac_off = jaccard[np.tril_indices(n, k=-1)]
cov_off = coverage[np.triu_indices(n, k=1)]
jac_lo = float(jac_off.min()) - 0.05 if jac_off.size else 0.0
jac_hi = float(jac_off.max()) + 0.05 if jac_off.size else 1.0
cov_lo = max(float(cov_off.min()) - 0.05, 0.0) if cov_off.size else 0.0
cov_hi = min(float(cov_off.max()) + 0.02, 1.0) if cov_off.size else 1.0
norm_j = Normalize(vmin=jac_lo, vmax=jac_hi)
norm_c = Normalize(vmin=cov_lo, vmax=cov_hi)

fig, ax = plt.subplots(figsize=(w, h))
ax.grid(False)
ax.set_axisbelow(False)
ax.imshow(np.full((n, n), np.nan), aspect="equal", cmap="Blues", vmin=0, vmax=1)

for i in range(n):
    for j in range(n):
        if i == j:
            ax.add_patch(plt.Rectangle(
                (j - 0.5, i - 0.5), 1, 1,
                facecolor="#e8e8e8", edgecolor="white", linewidth=1.5,
            ))
            ax.text(j, i, f"{len(hash_sets[columns[i]])}",
                    ha="center", va="center", fontweight="bold",
                    fontsize=fs["cell_bold"], color="#333333")
        elif i > j:
            v = jaccard[i][j]
            ax.add_patch(plt.Rectangle(
                (j - 0.5, i - 0.5), 1, 1,
                facecolor=cmap_j(norm_j(v)), edgecolor="white", linewidth=1.5,
            ))
            color = "white" if norm_j(v) > 0.6 else "black"
            ax.text(j, i, _floor_2(v),
                    ha="center", va="center", fontsize=fs["cell"], color=color)
        else:
            v = coverage[i][j]
            ax.add_patch(plt.Rectangle(
                (j - 0.5, i - 0.5), 1, 1,
                facecolor=cmap_c(norm_c(v)), edgecolor="white", linewidth=1.5,
            ))
            color = "white" if norm_c(v) > 0.6 else "black"
            ax.text(j, i, _floor_2(v),
                    ha="center", va="center", fontsize=fs["cell"], color=color)

ax.set_xlim(-0.5, n - 0.5)
ax.set_ylim(n - 0.5, -0.5)
ax.set_xticks(range(n))
ax.set_xticklabels(display, rotation=30, ha="right")
ax.set_yticks(range(n))
ax.set_yticklabels(display)
ax.tick_params(length=0)
for spine in ax.spines.values():
    spine.set_visible(False)

fig.subplots_adjust(right=0.82)
bbox = ax.get_position()
gap = 0.03
bar_w = 0.02
bar_h = (bbox.height - gap) / 2
x0 = bbox.x1 + 0.04

cax_j = fig.add_axes([x0, bbox.y0 + bar_h + gap, bar_w, bar_h])
cbar_j = fig.colorbar(mpl.cm.ScalarMappable(cmap=cmap_j, norm=norm_j), cax=cax_j)
cbar_j.set_label("Static Coverage", fontsize=fs["tick"])
cbar_j.ax.tick_params(labelsize=fs["tick"])

cax_c = fig.add_axes([x0, bbox.y0, bar_w, bar_h])
cbar_c = fig.colorbar(mpl.cm.ScalarMappable(cmap=cmap_c, norm=norm_c), cax=cax_c)
cbar_c.set_label("Dynamic Coverage", fontsize=fs["tick"])
cbar_c.ax.tick_params(labelsize=fs["tick"])

ax.set_title(
    f"Static (◣) / Dynamic (◥) Coverage"
    f"    |U|={len(universe)}  |$\\bigcap$|={len(all_inter)}",
    pad=10,
)

fig.savefig(sys.argv[1])
