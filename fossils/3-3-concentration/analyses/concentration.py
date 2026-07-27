#!/usr/bin/env python3
"""Section 3.3 within-workload Pareto concentration.

Reads entries-flush events (demand mode) and computes cumulative
dynamic-coverage curves per artifact class:

  - IC body Pareto: rank distinct ic_body_id by summed entered_count
    across all site instances, then compute cumulative fraction of
    total exec vs cumulative fraction of corpus (bodies OR body-bytes).

  - Baseline function Pareto: rank scripts by their aggregate exec
    activity (sum of their IC entries' entered_count, since the
    script-level counter is not yet populated in demand mode), then
    cumulative fraction of exec vs cumulative fraction of corpus.

The paper's F-corpus left panels want:
  - "corpus fraction (sorted by exec desc)" on x
  - "cumulative dynamic coverage" on y
  - one line per artifact class per workload
"""

import json
import os
import sys
from collections import defaultdict

_HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "..", "scripts"))

from instr_stream import (  # noqa: E402
    iter_events,
    reconcile,
    variant_name,
)


def _stderr_lines(obs):
    err = obs.get("stderr", "")
    if isinstance(err, list):
        return err
    return err.splitlines() if err else []


def _cumcov(items, key=lambda x: x[1]):
    """Given a list of (id, exec_count[, size_bytes]) tuples, return
    the cumulative coverage curve as list of dicts:
      {rank, frac_corpus, frac_exec, frac_bytes}
    Sorted descending by exec count.
    """
    ranked = sorted(items, key=lambda x: -x[1])
    total_exec = sum(x[1] for x in ranked)
    total_bytes = sum((x[2] if len(x) > 2 else 0) for x in ranked)
    n = len(ranked)
    curve = []
    cum_exec = 0
    cum_bytes = 0
    for i, x in enumerate(ranked):
        cum_exec += x[1]
        if len(x) > 2:
            cum_bytes += x[2]
        curve.append({
            "rank":         i + 1,
            "frac_corpus":  (i + 1) / n if n else 0.0,
            "frac_exec":    cum_exec / total_exec if total_exec else 0.0,
            "frac_bytes":   cum_bytes / total_bytes if total_bytes else 0.0,
        })
    return {
        "corpus_size":  n,
        "total_exec":   total_exec,
        "total_bytes":  total_bytes,
        "curve":        curve,
    }


def _pareto_summary(curve_data):
    """Return the classic 80/20-style landmark: how many artifacts to
    reach 50%, 80%, 90%, 99% of exec."""
    landmarks = {}
    curve = curve_data["curve"]
    total = curve_data["total_exec"]
    if not total:
        return {"reached": {}, "top1_frac_exec": 0.0, "top5pct_frac_exec": 0.0}
    for pct in (50, 80, 90, 99):
        for row in curve:
            if row["frac_exec"] >= pct / 100.0:
                landmarks[f"reach_{pct}pct_exec"] = row["rank"]
                break
        else:
            landmarks[f"reach_{pct}pct_exec"] = curve_data["corpus_size"]
    top1 = curve[0]["frac_exec"] if curve else 0.0
    top5pct_rank = max(1, int(curve_data["corpus_size"] * 0.05))
    top5pct_frac = curve[top5pct_rank - 1]["frac_exec"] if curve else 0.0
    return {
        "reached":            landmarks,
        "top1_frac_exec":     top1,
        "top5pct_frac_exec":  top5pct_frac,
    }


def analyze(obs):
    events = list(iter_events(_stderr_lines(obs)))

    # Body metadata (bytes, cache_kind) from ic-body-emit.
    body_meta: dict[str, dict] = {}
    for e in events:
        if e.get("kind") == "ic-body-emit":
            body_meta.setdefault(e["ic_body_id"], {
                "body_bytes": int(e.get("body_bytes", 0)),
                "cache_kind": e.get("cache_kind", "unknown"),
            })

    # Baseline compile metadata (method_bytes) per script.
    script_meta: dict[int, dict] = {}
    for e in events:
        if e.get("kind") == "baseline-compile":
            script_meta.setdefault(int(e["script_local_id"]), {
                "method_bytes":   int(e.get("method_bytes", 0)),
                "metadata_bytes": int(e.get("metadata_bytes", 0)),
                "semantic_id":    e.get("semantic_id"),
            })

    # Aggregate exec counts from every entries-flush across all PIDs.
    body_exec: dict[str, int] = defaultdict(int)
    script_exec: dict[int, int] = defaultdict(int)
    n_flushes = 0
    for e in events:
        if e.get("kind") != "entries-flush":
            continue
        n_flushes += 1
        for s in e.get("scripts", []):
            sid = int(s["script_local_id"])
            # If the engine ever populates script-level entered_count,
            # use it; otherwise fall back to sum of IC entered counts.
            direct = int(s.get("entered_count", 0))
            ic_sum = sum(int(ic.get("entered_count", 0))
                         for ic in s.get("ic_entries", []))
            script_exec[sid] += max(direct, ic_sum)
            for ic in s.get("ic_entries", []):
                body_id = ic.get("ic_body_id", "")
                if not body_id or body_id.startswith("0000"):
                    continue  # fallback sentinel
                body_exec[body_id] += int(ic.get("entered_count", 0))

    ic_items = [
        (bid, body_exec[bid], body_meta.get(bid, {}).get("body_bytes", 0))
        for bid in body_exec
    ]
    bl_items = [
        (sid, script_exec[sid],
         script_meta.get(sid, {}).get("method_bytes", 0))
        for sid in script_exec if script_exec[sid] > 0
    ]

    ic_curve = _cumcov(ic_items)
    bl_curve = _cumcov(bl_items)

    return {
        "n_entries_flushes":        n_flushes,
        "ic_body_pareto":           ic_curve,
        "ic_body_pareto_summary":   _pareto_summary(ic_curve),
        "baseline_fn_pareto":       bl_curve,
        "baseline_fn_pareto_summary": _pareto_summary(bl_curve),
        # Compact per-cache-kind view of top IC bodies (paper appendix).
        "top_ic_bodies_by_exec": [
            {"ic_body_id": x[0][:12], "cache_kind":
                body_meta.get(x[0], {}).get("cache_kind"),
             "exec": x[1], "body_bytes": x[2]}
            for x in sorted(ic_items, key=lambda y: -y[1])[:20]
        ],
    }


def main():
    obs = json.load(sys.stdin)
    if isinstance(obs.get("observations"), list) and obs["observations"]:
        obs = obs["observations"][0]

    events = list(iter_events(_stderr_lines(obs)))
    violations, stats = reconcile(events)
    if violations and not os.environ.get(
            "FOSSIL_ALLOW_RECONCILIATION_FAILURES"):
        print("concentration.py: reconciliation failed", file=sys.stderr)
        for v in violations:
            print(f"  {v}", file=sys.stderr)
        print("  set FOSSIL_ALLOW_RECONCILIATION_FAILURES=1 to force",
              file=sys.stderr)
        sys.exit(1)

    result = analyze(obs)
    result["variant"] = variant_name()
    result["reconcile_stats"] = stats
    result["reconcile_violations"] = violations
    json.dump(result, sys.stdout, separators=(",", ":"))


if __name__ == "__main__":
    main()
