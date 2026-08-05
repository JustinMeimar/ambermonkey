#!/home/justin/tools/fossil/figures/.venv/bin/python
"""JetStream 3 Startup-Geometric score per variant, normalized to
the stock runtime-lazy baseline.

Startup_geometric is JS3's first-iteration geo-mean across subtests,
i.e. the community-standard startup metric. Higher is better; the
normalization renders it as a ratio so the AOT/eager deltas read
directly as speedups.
"""

import sys

from fossil_figures import apply_style, load_stdin, comparison_bar

apply_style(column="double")
data = load_stdin()

baseline = "runtime-lazy"
if baseline not in data.column_names:
    baseline = data.column_names[0]

fig = comparison_bar(
    data,
    metrics=["startup_geomean"],
    normalize_to=baseline,
    ylabel=f"JS3 startup score (geomean of -First), relative to {baseline}",
    title="JetStream 3 first-iteration score",
)
fig.savefig(sys.argv[1])
