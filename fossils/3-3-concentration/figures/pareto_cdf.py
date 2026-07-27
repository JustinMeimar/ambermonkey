#!/home/justin/tools/fossil/figures/.venv/bin/python
"""§3.3 within-workload Pareto CDF, two-panel figure.

Left panel:  CacheIR body cumulative dynamic coverage.
Right panel: Baseline function cumulative dynamic coverage.

Each workload (fossil variant) becomes one curve per panel. Consumes
the `ic_body_ranked_counts` and `baseline_fn_ranked_counts` sequences
emitted by concentration.py.
"""
import functools
import sys

from fossil_figures import (
    apply_style,
    compose,
    get_colors,
    load_stdin,
    ranked_cdf,
)


def main():
    apply_style(column="double")
    data = load_stdin()
    colors = get_colors(data.column_names)

    ic_panel = functools.partial(
        ranked_cdf,
        data,
        metric="ic_body_ranked_counts",
        xlabel="CacheIR bodies (ranked by exec count)",
        ylabel="Fraction of total IC executions",
        thresholds=[0.5, 0.9],
        log_x=True,
        colors=colors,
    )
    bl_panel = functools.partial(
        ranked_cdf,
        data,
        metric="baseline_fn_ranked_counts",
        xlabel="Baseline functions (ranked by exec count)",
        ylabel="Fraction of total baseline executions",
        thresholds=[0.5, 0.9],
        log_x=True,
        colors=colors,
    )
    fig = compose([ic_panel, bl_panel], ncols=2, share_y=True)
    fig.savefig(sys.argv[1])


if __name__ == "__main__":
    main()
