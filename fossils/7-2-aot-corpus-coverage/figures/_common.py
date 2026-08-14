"""Shared helpers for the coverage figure scripts.

Coverage now comes from three populations: eight tp6_test sites
(one variant per site), Speedometer 3.1, and JetStream 3.0. The
suite scripts emit two shapes:

  emit_aggregate: three columns -- tp6-Test (median [min-max] across
      the 8 site variants), Speedometer 3.1, JetStream 3.0 -- one row
      per metric. Used by ic_table / baseline_function_table /
      baseline_interpreter_table.

  emit_tp6_test_per_site: 8 rows (one per test site), columns are the
      metrics. Used by ic_per_site_tp6_test.

The tp6_test membership is a frozen tuple mirroring 7-1's test.txt.
Duplicating it here is deliberate: the partition is checked in and
never changes without a coordinated rebuild of both fossils, and this
avoids a cross-fossil filesystem dependency at figure-render time.
"""

import json
import pathlib
import statistics
import sys


TP6_TEST_SITES = (
    "reddit", "tumblr", "twitch", "twitter",
    "wikia", "wikipedia", "yahoo-mail", "youtube",
)

SUITE_VARIANTS = ("speedometer3", "jetstream3")

VARIANT_LABELS = {
    "jetstream3":   "JetStream 3.0",
    "speedometer3": "Speedometer 3.1",
    "reddit":       "Reddit",
    "tumblr":       "Tumblr",
    "twitch":       "Twitch",
    "twitter":      "Twitter",
    "wikia":        "Wikia",
    "wikipedia":    "Wikipedia",
    "yahoo-mail":   "Yahoo Mail",
    "youtube":      "YouTube",
}

TP6_TEST_LABEL = "tp6-Test"


def die(name, msg):
    sys.exit(f"{name}: {msg}")


def dig(node, path, variant, name):
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            die(name, f"{variant}: no {path!r}; record predates the request-time schema")
        node = node[part]
    return node


def fmt_scalar(mean, kind):
    if kind == "percent":
        return f"{mean:.1f}%"
    if abs(mean) >= 1_000_000:
        return f"{mean/1e6:.2f}M"
    if abs(mean) >= 10_000:
        return f"{mean/1e3:.1f}k"
    return f"{mean:,.0f}"


def fmt_aggregate(values, kind):
    """median [min-max], formatted per kind."""
    if not values:
        return "--"
    if len(values) == 1:
        return fmt_scalar(values[0], kind)
    m = statistics.median(values)
    lo = min(values)
    hi = max(values)
    return f"{fmt_scalar(m, kind)} [{fmt_scalar(lo, kind)}-{fmt_scalar(hi, kind)}]"


def _load_and_check(name):
    data = json.load(sys.stdin)
    if not data:
        die(name, "no variants in analyzed input")
    return data


def _tp6_test_values(data, path, name):
    """Extract the per-iteration mean from each tp6_test variant, in the
    frozen order defined by TP6_TEST_SITES. Missing variants are silently
    dropped so a partial rerun still renders, but a fully empty tp6_test
    set is not a valid render and returns []."""
    values = []
    for v in TP6_TEST_SITES:
        if v not in data:
            continue
        scalar = dig(data[v], path, v, name)
        values.append(scalar["mean"])
    return values


def emit_aggregate(name, rows_spec):
    """Three-column table: tp6-Test aggregate, Speedometer 3.1, JetStream 3.0.

    rows_spec is a list of (label, dotted_path, kind) tuples matching the
    reducer's summary schema (see reduce_coverage.py). Reads the cross-
    variant fold on stdin and writes a JSON table to
    sys.argv[1]'s .json sibling."""
    data = _load_and_check(name)

    columns = [
        {"key": "metric",       "label": "Metric",         "align": "left",  "format": "str"},
        {"key": "tp6_test",     "label": TP6_TEST_LABEL,   "align": "right", "format": "str"},
        {"key": "speedometer3", "label": VARIANT_LABELS["speedometer3"], "align": "right", "format": "str"},
        {"key": "jetstream3",   "label": VARIANT_LABELS["jetstream3"],   "align": "right", "format": "str"},
    ]

    rows = []
    for label, path, kind in rows_spec:
        row = [label]
        row.append(fmt_aggregate(_tp6_test_values(data, path, name), kind))
        for suite in ("speedometer3", "jetstream3"):
            if suite not in data:
                row.append("--")
                continue
            scalar = dig(data[suite], path, suite, name)
            row.append(fmt_scalar(scalar["mean"], kind))
        rows.append(row)

    out = pathlib.Path(sys.argv[1]).with_suffix(".json")
    out.write_text(json.dumps({"columns": columns, "rows": rows}, indent=2) + "\n")
    print(f"wrote {out}")


def emit_tp6_test_per_site(name, columns_spec):
    """Per-site table for tp6_test: 8 rows, one column per metric.

    columns_spec is a list of (key, label, dotted_path, kind) tuples.
    The leading Site column is added automatically."""
    data = _load_and_check(name)

    columns = [{"key": "site", "label": "Site", "align": "left", "format": "str"}]
    for key, label, _path, _kind in columns_spec:
        columns.append({"key": key, "label": label, "align": "right", "format": "str"})

    rows = []
    for site in TP6_TEST_SITES:
        if site not in data:
            continue
        row = [VARIANT_LABELS.get(site, site)]
        for _key, _label, path, kind in columns_spec:
            scalar = dig(data[site], path, site, name)
            row.append(fmt_scalar(scalar["mean"], kind))
        rows.append(row)

    out = pathlib.Path(sys.argv[1]).with_suffix(".json")
    out.write_text(json.dumps({"columns": columns, "rows": rows}, indent=2) + "\n")
    print(f"wrote {out}")
