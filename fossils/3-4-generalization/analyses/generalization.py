#!/usr/bin/env python3
"""Section 3.4 leave-one-workload-out generalization.

Reads every burial record under
  ~/.fossil/projects/ambermonkey/3-3-concentration/records/
and, for each held-out workload W, computes:

  dynamic_coverage(C, W)       = fraction of W's exec covered by C
  static_byte_coverage(C, W)   = fraction of W's live body bytes in C

where C is a corpus built from the union of the top-k artifact keys
from the OTHER workloads, weighted by their exec counts. We sweep k
from 1 to 100% and emit a curve per (held-out, artifact class) pair.

Artifact key: for IC bodies, the ic_body_id (SHA-1 over CacheIR body
code) is a stable cross-process identity. For baseline functions, we
would need a semantic_id (baseline-compile) hash -- included when
available.

This analyzer takes NO workload observation from stdin (the fossil
variant is a no-op echo). It reads sibling records directly.
"""

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

_HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "..", "scripts"))

from instr_stream import (  # noqa: E402
    iter_events,
    variant_name,
)

RECORDS_ROOT = Path.home() / ".fossil/projects/ambermonkey/3-3-concentration/records"


def _load_workload(record_dir: Path) -> dict:
    """Return workload keyed by stable cross-process identities.

    IC bodies: keyed by ic_body_id (SHA-1 over CacheIR body code).
    Baseline functions: keyed by semantic_id (SHA-1 over canonical
    bytecode). Sites without a matching baseline-compile event (never
    baseline-compiled) are skipped from baseline_fns.
    """
    manifest = json.loads((record_dir / "manifest.json").read_text())
    variant = manifest.get("variant", record_dir.name)
    results = json.loads((record_dir / "results.json").read_text())

    # ic_body_id -> (body_bytes, cache_kind)
    body_meta: dict[str, tuple] = {}
    # script_local_id -> (semantic_id, method_bytes)
    sid_to_semantic: dict[int, tuple] = {}
    # ic_body_id -> exec (summed across all sites/scripts)
    body_exec: dict[str, int] = defaultdict(int)
    # semantic_id -> exec (summed across scripts sharing this semantic)
    fn_exec: dict[str, int] = defaultdict(int)

    for obs in results.get("observations", []):
        stderr = obs.get("stderr", "")
        if isinstance(stderr, list):
            lines = stderr
        else:
            lines = stderr.splitlines()

        for e in iter_events(lines):
            k = e.get("kind")
            if k == "ic-body-emit":
                body_meta.setdefault(e["ic_body_id"],
                                     (int(e.get("body_bytes", 0)),
                                      e.get("cache_kind", "unknown")))
            elif k == "baseline-compile":
                sid = int(e["script_local_id"])
                sem = e.get("semantic_id", "")
                sid_to_semantic[sid] = (sem, int(e.get("method_bytes", 0)))
            elif k == "entries-flush":
                for s in e.get("scripts", []):
                    sid = int(s["script_local_id"])
                    direct = int(s.get("entered_count", 0))
                    ic_sum = 0
                    for ic in s.get("ic_entries", []):
                        bid = ic.get("ic_body_id", "")
                        cnt = int(ic.get("entered_count", 0))
                        if not bid.startswith("0000"):
                            body_exec[bid] += cnt
                        ic_sum += cnt
                    activity = max(direct, ic_sum)
                    if sid in sid_to_semantic:
                        sem, _ = sid_to_semantic[sid]
                        fn_exec[sem] += activity

    # Collapse per-semantic aggregates.
    fn_bytes: dict[str, int] = {}
    for sid, (sem, mb) in sid_to_semantic.items():
        fn_bytes[sem] = max(fn_bytes.get(sem, 0), mb)

    return {
        "variant":       variant,
        "ic_bodies":     {bid: (body_exec[bid],
                                body_meta.get(bid, (0, ""))[0],
                                body_meta.get(bid, (0, ""))[1])
                          for bid in body_exec if body_exec[bid] > 0},
        "baseline_fns":  {sem: (fn_exec[sem], fn_bytes.get(sem, 0))
                          for sem in fn_exec if fn_exec[sem] > 0},
    }


def _corpus_from_others(workloads: list[dict], held_out: str,
                        key_field: str, k: int) -> set:
    """Build a corpus of the top-k artifact keys drawn from the union
    of all workloads except held_out, ranked by total exec across the
    included set."""
    agg: dict[object, int] = defaultdict(int)
    for w in workloads:
        if w["variant"] == held_out:
            continue
        for key, (exec_ct, *_) in w[key_field].items():
            agg[key] += exec_ct
    return set(k_ for k_, _ in sorted(agg.items(),
                                       key=lambda x: -x[1])[:k])


def _cover(w_test: dict, corpus: set, key_field: str) -> dict:
    """Return dynamic_coverage and static_byte_coverage of `corpus`
    over the held-out workload's `key_field`."""
    total_exec = sum(v[0] for v in w_test[key_field].values())
    total_bytes = sum(v[1] for v in w_test[key_field].values())
    covered_exec = sum(v[0] for k, v in w_test[key_field].items()
                       if k in corpus)
    covered_bytes = sum(v[1] for k, v in w_test[key_field].items()
                        if k in corpus)
    return {
        "dynamic_coverage":       covered_exec / total_exec if total_exec else 0.0,
        "static_byte_coverage":   covered_bytes / total_bytes if total_bytes else 0.0,
        "unique_hits":            sum(1 for k in w_test[key_field] if k in corpus),
        "total_unique":           len(w_test[key_field]),
    }


def _sweep(workloads: list[dict], held_out: str, key_field: str) -> list[dict]:
    """Sweep corpus size k from 1..100% of the union artifact count
    (excluding held-out) and return coverage curve."""
    union: set = set()
    for w in workloads:
        if w["variant"] == held_out:
            continue
        union.update(w[key_field].keys())
    n = len(union)
    if n == 0:
        return []
    curve = []
    for pct in (5, 10, 25, 50, 75, 100):
        k = max(1, n * pct // 100)
        corpus = _corpus_from_others(workloads, held_out, key_field, k)
        cov = _cover(workloads[[w["variant"] for w in workloads].index(held_out)],
                     corpus, key_field)
        curve.append({"corpus_pct": pct, "corpus_size": k, **cov})
    return curve


def analyze():
    if not RECORDS_ROOT.exists():
        return {
            "error": f"records dir not found: {RECORDS_ROOT}",
            "advice": ("run at least two 3-3-concentration variants "
                       "before this analyzer can produce cross-workload "
                       "coverage."),
        }

    # Latest record per variant.
    latest: dict[str, Path] = {}
    for rd in sorted(RECORDS_ROOT.iterdir()):
        if not rd.is_dir():
            continue
        if not (rd / "manifest.json").exists():
            continue
        try:
            manifest = json.loads((rd / "manifest.json").read_text())
        except Exception:
            continue
        v = manifest.get("variant")
        if not v:
            continue
        if v not in latest or rd.name > latest[v].name:
            latest[v] = rd

    workloads = [_load_workload(rd) for rd in latest.values()]
    if len(workloads) < 2:
        return {
            "workloads_found": [w["variant"] for w in workloads],
            "error": "need >= 2 workloads for leave-one-out",
        }

    ic_curves = {}
    bl_curves = {}
    for w in workloads:
        held_out = w["variant"]
        ic_curves[held_out] = _sweep(workloads, held_out, "ic_bodies")
        bl_curves[held_out] = _sweep(workloads, held_out, "baseline_fns")

    per_workload_size = {
        w["variant"]: {
            "n_ic_bodies":    len(w["ic_bodies"]),
            "n_baseline_fns": len(w["baseline_fns"]),
            "ic_exec_total":  sum(v[0] for v in w["ic_bodies"].values()),
            "bl_exec_total":  sum(v[0] for v in w["baseline_fns"].values()),
        }
        for w in workloads
    }

    return {
        "workloads":              [w["variant"] for w in workloads],
        "per_workload_size":      per_workload_size,
        "ic_body_coverage":       ic_curves,
        "baseline_fn_coverage":   bl_curves,
    }


def main():
    # Read (and discard) any observation on stdin so fossil is happy.
    try:
        json.load(sys.stdin)
    except Exception:
        pass
    result = analyze()
    result["variant"] = variant_name()
    json.dump(result, sys.stdout, separators=(",", ":"))


if __name__ == "__main__":
    main()
