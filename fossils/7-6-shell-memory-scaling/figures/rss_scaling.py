#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Shell memory scaling with worker count. Four lines:

- solid: total peak RSS (whole shell process).
- dashed: peak anonymous-executable residency (SpiderMonkey's JIT
  pools -- baseline interpreter, compiled baseline, IC stubs).

Total RSS is dominated by non-JIT per-worker overhead (GC heap, stacks,
self-hosted data) that is identical under stock and aot. Anonymous exec
isolates the code that AOT actually eliminates. Log-scale y accommodates
both series in one axis."""

import re
import sys

import matplotlib.pyplot as plt

from fossil_figures import apply_style, load_stdin


VARIANT_RE = re.compile(r"^n(\d+)(-aot)?$")

STYLE = (
    ("stock", "rss",       "#4c72b0", "o", "-",  "stock RSS"),
    ("aot",   "rss",       "#dd8452", "s", "-",  "aot RSS"),
    ("stock", "anon_exec", "#4c72b0", "o", "--", "stock anon-exec"),
    ("aot",   "anon_exec", "#dd8452", "s", "--", "aot anon-exec"),
)

KEY = {"rss": "peak_rss_mb", "anon_exec": "peak_anon_exec_mb"}


def series(table, kind, key):
    out = []
    for variant, metrics in table.items():
        match = VARIANT_RE.match(variant)
        if not match:
            continue
        variant_kind = "aot" if match.group(2) else "stock"
        if variant_kind != kind:
            continue
        entry = metrics.get(KEY[key])
        if entry is None:
            continue
        out.append((int(match.group(1)), entry.mean, entry.stddev))
    out.sort()
    return out


apply_style(column="single")
data = load_stdin()
table = data.flat_table()

fig, ax = plt.subplots(figsize=(6.0, 3.6))
plotted = False
for kind, key, color, marker, ls, label in STYLE:
    points = series(table, kind, key)
    if not points:
        print(f"rss_scaling: no data for {label}", file=sys.stderr)
        continue
    xs = [n for n, _, _ in points]
    ys = [m for _, m, _ in points]
    es = [s for _, _, s in points]
    ax.errorbar(xs, ys, yerr=es, marker=marker, color=color,
                linestyle=ls, label=label, linewidth=1.4, markersize=5,
                capsize=3, markerfacecolor=color if ls == "-" else "white",
                markeredgecolor=color)
    plotted = True

if not plotted:
    raise SystemExit("rss_scaling: no data in any series")

ax.set_xscale("log", base=2)
ax.set_yscale("log")
ax.set_xlabel("Worker JSRuntimes (N)")
ax.set_ylabel("Memory (MB)")
ax.set_title("Shell peak memory vs worker count")
ax.legend(loc="upper left", frameon=False, fontsize=8, ncol=2)
ax.grid(True, which="both", axis="both", linestyle=":", alpha=0.4)
fig.tight_layout()
fig.savefig(sys.argv[1])
