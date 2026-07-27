#!/usr/bin/env python3
"""Section 3.2 coupling census.

Reads ic-body-emit events and classifies every stub-field coupling
record into the paper's five buckets. Emits a per-cache-kind
breakdown suitable for the T-baseline coupling columns.

Buckets (from paper draft, §3.2):
  (a) compile-time constant       -- direct-relocatable + relocKind=none
  (b) incidentally coupled ref    -- eligibility=table
  (c) per-zone / per-realm        -- targetKind=ICScript
  (d) GC-managed                  -- relocKind=gcptr
  (e) private stub data           -- everything else

Buckets (b), (c), (d) are the AOT-eligibility surface: (b) requires
indirection-table lookup, (d) needs write barriers, (c) needs a
per-instance offset. (a) is baked in-code, (e) is per-stub-instance
scalar state that cannot be shared across processes.
"""

import json
import os
import sys
from collections import Counter, defaultdict

_HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "..", "scripts"))

from instr_stream import (  # noqa: E402
    iter_events,
    reconcile,
    variant_name,
)


BUCKETS = ("a_ct_const", "b_engine_ref", "c_per_zone", "d_gcptr",
           "e_stub_data")


def classify(rec: dict) -> str:
    """Return one of the 5 bucket keys."""
    elig = rec.get("eligibility", "")
    reloc = rec.get("reloc_kind", "")
    target = rec.get("target_kind", "")
    if target == "ICScript":
        return "c_per_zone"
    if elig == "table":
        return "b_engine_ref"
    if reloc == "gcptr":
        return "d_gcptr"
    if elig == "direct-relocatable" and reloc == "none":
        return "a_ct_const"
    return "e_stub_data"


def _stderr_lines(obs):
    err = obs.get("stderr", "")
    if isinstance(err, list):
        return err
    return err.splitlines() if err else []


def analyze(obs):
    events = list(iter_events(_stderr_lines(obs)))
    bodies = [e for e in events if e.get("kind") == "ic-body-emit"]

    # Per cache_kind aggregation.
    per_kind: dict[str, dict] = defaultdict(lambda: {
        "distinct_bodies":       0,
        "total_body_bytes":      0,
        "total_stub_data_bytes": 0,
        "coupling_records":      0,
        "buckets":               Counter({b: 0 for b in BUCKETS}),
        "target_kinds":          Counter(),
    })
    total = {
        "distinct_bodies":       0,
        "total_body_bytes":      0,
        "total_stub_data_bytes": 0,
        "coupling_records":      0,
        "buckets":               Counter({b: 0 for b in BUCKETS}),
        "target_kinds":          Counter(),
    }
    # Dedupe by ic_body_id -- the same body may be re-emitted across
    # processes; the coupling census counts each unique body once.
    seen_body_ids: set[str] = set()

    for e in bodies:
        body_id = e.get("ic_body_id", "")
        if body_id in seen_body_ids:
            continue
        seen_body_ids.add(body_id)
        kind = e.get("cache_kind", "unknown")
        body_bytes = int(e.get("body_bytes", 0))
        stub_bytes = int(e.get("stub_data_bytes", 0))
        coupling = e.get("coupling", []) or []

        k_stats = per_kind[kind]
        k_stats["distinct_bodies"] += 1
        k_stats["total_body_bytes"] += body_bytes
        k_stats["total_stub_data_bytes"] += stub_bytes
        total["distinct_bodies"] += 1
        total["total_body_bytes"] += body_bytes
        total["total_stub_data_bytes"] += stub_bytes

        for rec in coupling:
            bucket = classify(rec)
            k_stats["coupling_records"] += 1
            k_stats["buckets"][bucket] += 1
            k_stats["target_kinds"][rec.get("target_kind", "?")] += 1
            total["coupling_records"] += 1
            total["buckets"][bucket] += 1
            total["target_kinds"][rec.get("target_kind", "?")] += 1

    def _dump(rec):
        return {
            "distinct_bodies":       rec["distinct_bodies"],
            "total_body_bytes":      rec["total_body_bytes"],
            "total_stub_data_bytes": rec["total_stub_data_bytes"],
            "coupling_records":      rec["coupling_records"],
            "buckets":               dict(rec["buckets"]),
            "target_kinds":          dict(rec["target_kinds"]),
        }

    return {
        "per_cache_kind": {k: _dump(v) for k, v in sorted(per_kind.items())},
        "total":          _dump(total),
    }


def main():
    obs = json.load(sys.stdin)
    if isinstance(obs.get("observations"), list) and obs["observations"]:
        obs = obs["observations"][0]

    events = list(iter_events(_stderr_lines(obs)))
    violations, stats = reconcile(events)
    if violations and not os.environ.get(
            "FOSSIL_ALLOW_RECONCILIATION_FAILURES"):
        print("coupling.py: reconciliation failed -- refusing to emit output",
              file=sys.stderr)
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
