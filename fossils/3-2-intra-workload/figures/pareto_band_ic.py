#!/home/justin/tools/fossil/figures/.venv/bin/python
import sys

from fossil_figures import apply_style, load_stdin, ranked_cdf_band

apply_style(column="single")
data = load_stdin()
fig = ranked_cdf_band(
    data,
    metric="ranked_counts",
    xlabel="Unique IC stub bodies (ranked by frequency)",
    ylabel="Fraction of total attaches",
    thresholds=[0.9],
    log_x=True,
)
fig.savefig(sys.argv[1])
